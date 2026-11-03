"""Stateful ReAct customer service agent with SQLite session memory for Empório da Música.

Why: Implements an explicit, manual ReAct tool-execution loop (`max_iterations=5`)
with SDK automatic function calling disabled. Every LLM invocation passes through
`GeminiFallbackRouter.generate_with_fallback()`, while conversation history is
sanitized across model families (`gemini-2.5-*` and `gemini-2.0-*`) and persisted
in the SQLite `chat_history` table by `session_id`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from google.genai import types

from src.config import DB_PATH
from src.database import get_connection, init_database
from src.llm_fallback import GeminiFallbackRouter
from src.prompts import SYSTEM_INSTRUCTION
from src.tools import (
    calculate_payment_options,
    consult_store_policies,
    execute_tool_call,
    get_order_status,
    search_catalog,
)

logger = logging.getLogger(__name__)


class EmporioAgent:
    """Stateful ReAct customer support agent backed by Gemini fallback routing and SQLite memory.

    Why: Separates tool execution from model generation so that if a Free-Tier rate limit
    (HTTP 429) or server overload (HTTP 503) occurs after a tool has already executed,
    the fallback model synthesizes the final answer from the sanitized conversation history
    without re-running the tool.
    """

    def __init__(
        self,
        router: Optional[GeminiFallbackRouter] = None,
        db_path: Optional[Path | str] = None,
        max_iterations: int = 5,
    ) -> None:
        """Initialize the agent with a `GeminiFallbackRouter` and SQLite database path.

        Why: Supports dependency injection of a custom router or temporary database in
        unit tests while defaulting to production settings.
        """
        self.router: GeminiFallbackRouter = router or GeminiFallbackRouter()
        self.db_path: Path = Path(db_path) if db_path is not None else DB_PATH
        self.max_iterations: int = max_iterations

        self.tools = [
            search_catalog,
            calculate_payment_options,
            get_order_status,
            consult_store_policies,
        ]
        self.config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=self.tools,
            temperature=0.1,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        self._ensure_db_ready()

    def _ensure_db_ready(self) -> None:
        """Ensure the SQLite database and `chat_history` table exist before session operations."""
        if not self.db_path.exists():
            conn = init_database(self.db_path)
            conn.close()
            return
        conn = get_connection(self.db_path)
        try:
            cur = conn.cursor()
            table_ok = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history';"
            ).fetchone()
            if not table_ok:
                conn.close()
                conn = init_database(self.db_path)
        finally:
            conn.close()

    def load_session_history(self, session_id: str) -> list[types.Content]:
        """Load and reconstruct sanitized `types.Content` turns for `session_id` from SQLite.

        Why: Restores multi-turn context across user requests while guaranteeing that all
        parts are clean text, `from_function_call`, or `from_function_response` objects
        compatible with every model in the Gemini cascade.
        """
        conn = get_connection(self.db_path)
        try:
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT role, content_json
                FROM chat_history
                WHERE session_id = ?
                ORDER BY turn_index ASC, id ASC;
                """,
                (session_id,),
            ).fetchall()

            contents: list[types.Content] = []
            for row in rows:
                role = str(row["role"])
                raw_json = str(row["content_json"])
                try:
                    payload = json.loads(raw_json)
                except json.JSONDecodeError:
                    continue

                reconstructed_parts = self._deserialize_parts(payload)
                if reconstructed_parts:
                    contents.append(types.Content(role=role, parts=reconstructed_parts))
            return contents
        finally:
            conn.close()

    def _append_turn_to_db(
        self,
        session_id: str,
        role: str,
        parts_payload: list[dict[str, Any]],
        model_used: Optional[str] = None,
    ) -> None:
        """Persist a single conversation turn into the SQLite `chat_history` table.

        Why: Maintains a durable audit trail of user messages, tool calls, tool responses,
        and assistant answers indexed by `session_id` and sequential `turn_index`.
        """
        conn = get_connection(self.db_path)
        try:
            cur = conn.cursor()
            row = cur.execute(
                "SELECT COALESCE(MAX(turn_index), -1) + 1 AS next_idx FROM chat_history WHERE session_id = ?;",
                (session_id,),
            ).fetchone()
            next_idx = int(row["next_idx"]) if row else 0
            cur.execute(
                """
                INSERT INTO chat_history (session_id, turn_index, role, content_json, model_used)
                VALUES (?, ?, ?, ?, ?);
                """,
                (
                    session_id,
                    next_idx,
                    role,
                    json.dumps(parts_payload, ensure_ascii=False),
                    model_used,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_session(self, session_id: str = "default") -> None:
        """Delete all stored conversation history for the given `session_id`.

        Why: Enables UI and CLI 'New Conversation / Clear History' actions.
        """
        conn = get_connection(self.db_path)
        try:
            conn.execute("DELETE FROM chat_history WHERE session_id = ?;", (session_id,))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _deserialize_parts(payload: Any) -> list[types.Part]:
        """Convert serialized JSON part dictionaries back into clean `types.Part` instances.

        Why: Avoids storing or reloading model-specific `thought_signature` metadata
        that would break cross-model fallback between `gemini-2.5-*` and `gemini-2.0-*`.
        """
        if not isinstance(payload, list):
            return []

        parts: list[types.Part] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            part_type = item.get("type")
            if part_type == "text" and item.get("text") is not None:
                parts.append(types.Part.from_text(text=str(item["text"])))
            elif part_type == "function_call" and item.get("name"):
                fc_part = types.Part.from_function_call(
                    name=str(item["name"]),
                    args=dict(item.get("args") or {}),
                )
                sig_raw = item.get("thought_signature")
                if sig_raw:
                    if isinstance(sig_raw, str):
                        try:
                            fc_part.thought_signature = bytes.fromhex(sig_raw)
                        except ValueError:
                            fc_part.thought_signature = sig_raw.encode("latin-1")
                    elif isinstance(sig_raw, bytes):
                        fc_part.thought_signature = sig_raw
                parts.append(fc_part)
            elif part_type == "function_response" and item.get("name"):
                parts.append(
                    types.Part.from_function_response(
                        name=str(item["name"]),
                        response=dict(item.get("response") or {}),
                    )
                )
        return parts

    @staticmethod
    def _extract_function_calls_with_signatures(
        response: types.GenerateContentResponse,
    ) -> list[tuple[types.FunctionCall, bytes | None]]:
        """Extract all function calls and their optional thought_signature from response.

        Why: In Gemini 3 series models, function call continuations require the associated
        thought_signature byte token to authenticate model reasoning continuity.
        """
        calls: list[tuple[types.FunctionCall, bytes | None]] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                fc = getattr(part, "function_call", None)
                if fc is not None and getattr(fc, "name", None):
                    sig = getattr(part, "thought_signature", None)
                    calls.append((fc, sig))
        if not calls and getattr(response, "function_calls", None):
            for fc in response.function_calls:
                calls.append((fc, None))
        return calls

    @staticmethod
    def _extract_function_calls(
        response: types.GenerateContentResponse,
    ) -> list[types.FunctionCall]:
        """Extract all function calls requested by the model from `GenerateContentResponse`.

        Why: Supports both `response.function_calls` and candidate part inspection so
        mocked responses and live SDK responses are handled identically.
        """
        return [fc for fc, _ in EmporioAgent._extract_function_calls_with_signatures(response)]

    @staticmethod
    def _extract_text(response: types.GenerateContentResponse) -> str:
        """Extract clean assistant text from `GenerateContentResponse` ignoring thinking parts."""
        text_chunks: list[str] = []
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                if getattr(part, "thought", False):
                    continue
                part_text = getattr(part, "text", None)
                if part_text:
                    text_chunks.append(str(part_text))
        if text_chunks:
            return "".join(text_chunks).strip()

        direct_text = getattr(response, "text", None)
        if isinstance(direct_text, str) and direct_text.strip():
            return direct_text.strip()
        return ""

    def chat(self, user_message: str, session_id: str = "default") -> dict[str, Any]:
        """Process a customer message through the stateful ReAct loop with model fallback.

        Why: Orchestrates session history retrieval, manual tool execution, cross-model
        history sanitization, and SQLite persistence, returning response text alongside
        model and tool telemetry.

        Args:
            user_message: Customer message in Brazilian Portuguese.
            session_id: Unique conversation identifier (defaults to `"default"`).

        Returns:
            Dictionary with keys:
            `{"response": str, "model_used": str, "tool_calls": list[dict], "fallback_events": list[dict]}`.
        """
        contents = self.load_session_history(session_id)

        user_part = types.Part.from_text(text=user_message)
        contents.append(types.Content(role="user", parts=[user_part]))
        self._append_turn_to_db(
            session_id=session_id,
            role="user",
            parts_payload=[{"type": "text", "text": user_message}],
            model_used=None,
        )

        executed_tool_calls: list[dict[str, Any]] = []
        all_fallback_events: list[dict[str, Any]] = []
        last_model_used: str = ""
        final_text: str = ""

        for _iteration in range(self.max_iterations):
            response, model_used, step_fallbacks = self.router.generate_with_fallback(
                contents=contents,
                config=self.config,
            )
            last_model_used = model_used
            all_fallback_events.extend(step_fallbacks)

            function_calls_with_sigs = self._extract_function_calls_with_signatures(response)

            if not function_calls_with_sigs:
                final_text = self._extract_text(response)
                if final_text:
                    assistant_part = types.Part.from_text(text=final_text)
                    contents.append(types.Content(role="model", parts=[assistant_part]))
                    self._append_turn_to_db(
                        session_id=session_id,
                        role="model",
                        parts_payload=[{"type": "text", "text": final_text}],
                        model_used=last_model_used,
                    )
                break

            # Sanitize assistant tool-call turn: construct clean Part.from_function_call objects
            # while preserving thought_signature tokens for Gemini 3 continuity.
            clean_fc_parts: list[types.Part] = []
            serialized_fc_parts: list[dict[str, Any]] = []
            clean_fr_parts: list[types.Part] = []
            serialized_fr_parts: list[dict[str, Any]] = []

            for fc, sig in function_calls_with_sigs:
                fc_name = str(fc.name)
                fc_args = dict(fc.args) if fc.args else {}

                fc_part = types.Part.from_function_call(name=fc_name, args=fc_args)
                if sig is not None:
                    fc_part.thought_signature = sig
                clean_fc_parts.append(fc_part)

                serialized_item: dict[str, Any] = {
                    "type": "function_call",
                    "name": fc_name,
                    "args": fc_args,
                }
                if sig is not None:
                    serialized_item["thought_signature"] = (
                        sig.hex() if isinstance(sig, bytes) else str(sig)
                    )
                serialized_fc_parts.append(serialized_item)

                tool_output = execute_tool_call(fc_name, fc_args)
                executed_tool_calls.append(
                    {
                        "name": fc_name,
                        "args": fc_args,
                        "result": tool_output,
                        "model_requested": model_used,
                    }
                )

                clean_fr_parts.append(
                    types.Part.from_function_response(
                        name=fc_name,
                        response={"result": tool_output},
                    )
                )
                serialized_fr_parts.append(
                    {
                        "type": "function_response",
                        "name": fc_name,
                        "response": {"result": tool_output},
                    }
                )

            contents.append(types.Content(role="model", parts=clean_fc_parts))
            self._append_turn_to_db(
                session_id=session_id,
                role="model",
                parts_payload=serialized_fc_parts,
                model_used=model_used,
            )

            contents.append(types.Content(role="user", parts=clean_fr_parts))
            self._append_turn_to_db(
                session_id=session_id,
                role="user",
                parts_payload=serialized_fr_parts,
                model_used=model_used,
            )
        else:
            # If max_iterations was reached while still requesting tools, request a final synthesis
            response, model_used, step_fallbacks = self.router.generate_with_fallback(
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.1,
                ),
            )
            last_model_used = model_used
            all_fallback_events.extend(step_fallbacks)
            final_text = self._extract_text(response)
            if final_text:
                self._append_turn_to_db(
                    session_id=session_id,
                    role="model",
                    parts_payload=[{"type": "text", "text": final_text}],
                    model_used=last_model_used,
                )

        return {
            "response": final_text,
            "model_used": last_model_used,
            "tool_calls": executed_tool_calls,
            "fallback_events": all_fallback_events,
        }
