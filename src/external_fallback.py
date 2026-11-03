"""Zero-local-install external fallback provider (Groq Cloud / Remote Ollama) for Empório da Música.

Why: Enables an ultra-resilient fallback model that executes with 0 MB of local disk
space and 0% local RAM/VRAM utilization. Bridges OpenAI-compatible chat completion APIs
(Groq `llama-3.3-70b-versatile` or Remote `OLLAMA_HOST`) with Google GenAI `types.Content`
turns and ReAct tool schemas, guaranteeing business continuity when all Google AI Studio
quotas are exhausted.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable, Optional

import httpx
from google.genai import types

from src import config as settings

logger = logging.getLogger(__name__)

# Pre-defined schemas for store tools ensuring 100% schema accuracy for OpenAI-compatible APIs
STORE_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search_catalog": {
        "type": "function",
        "function": {
            "name": "search_catalog",
            "description": "Busca instrumentos musicais no catálogo por texto livre, categoria e faixa de preço.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca textual (marca, modelo ou tipo de instrumento).",
                    },
                    "category": {
                        "type": "string",
                        "description": "Nome exato da categoria para filtrar.",
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Preço máximo em reais (BRL).",
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Preço mínimo em reais (BRL).",
                    },
                    "only_available": {
                        "type": "boolean",
                        "description": "Se True, filtra apenas produtos com status 'active' e estoque > 0.",
                    },
                },
            },
        },
    },
    "calculate_payment_options": {
        "type": "function",
        "function": {
            "name": "calculate_payment_options",
            "description": "Calcula opções de pagamento detalhadas (à vista com desconto PIX de 5% se não houver promoção ativa, parcelamento no cartão sem juros de até 12x com regras de parcela mínima, e regras de pagamento combinado).",
            "parameters": {
                "type": "object",
                "properties": {
                    "price_brl": {
                        "type": "number",
                        "description": "Preço do produto em reais (BRL).",
                    },
                    "has_active_promotion": {
                        "type": "boolean",
                        "description": "Indica se o produto já está com promoção ativa (o desconto de 5% do PIX não é cumulativo).",
                    },
                },
                "required": ["price_brl"],
            },
        },
    },
    "get_order_status": {
        "type": "function",
        "function": {
            "name": "get_order_status",
            "description": "Consulta o status e histórico de um pedido do cliente, validando prazos de devolução por arrependimento (7 dias) e troca por defeito (30 dias).",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "ID numérico do pedido.",
                    },
                    "customer_identifier": {
                        "type": "string",
                        "description": "Identificador do cliente (email, telefone ou nome) para validação LGPD.",
                    },
                    "reference_date": {
                        "type": "string",
                        "description": "Data base para cálculo de prazos no formato YYYY-MM-DD (padrão: 2026-03-25).",
                    },
                },
            },
        },
    },
    "consult_store_policies": {
        "type": "function",
        "function": {
            "name": "consult_store_policies",
            "description": "Consulta as políticas oficiais da loja Empório da Música (formas de pagamento, parcelamento, trocas e devoluções, garantias, LGPD e atendimento).",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Tópico da política a ser consultada (ex: 'pagamento', 'troca', 'garantia', 'contato', 'lgpd', 'frete').",
                    },
                },
                "required": ["topic"],
            },
        },
    },
}


class ExternalFallbackProvider:
    """OpenAI-compatible fallback client supporting Groq Cloud and Remote Ollama hosts.

    Why: Serves as an external safety net when all Google Gemini models are exhausted,
    translating between Google GenAI typed objects and standard OpenAI chat completion JSON.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        model: Optional[str] = None,
        http_client: Optional[httpx.Client] = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize provider endpoint, authentication, and HTTP client.

        Why: Supports dependency injection of custom endpoints, models, or mock clients
        for isolated unit testing while resolving environment defaults.
        """
        self.ollama_host: str = (
            host if host is not None else settings.OLLAMA_HOST
        ).strip()
        self.groq_api_key: str = (
            api_key if api_key is not None else settings.GROQ_API_KEY
        ).strip()
        self.timeout: float = timeout
        self.http_client: httpx.Client = http_client or httpx.Client(timeout=self.timeout)

        # Resolve mode: Remote Ollama takes precedence if host is configured, otherwise Groq
        if self.ollama_host:
            clean_host = self.ollama_host.rstrip("/")
            if not clean_host.endswith("/v1"):
                self.endpoint_url = f"{clean_host}/v1/chat/completions"
            else:
                self.endpoint_url = f"{clean_host}/chat/completions"
            self.model: str = model or settings.OLLAMA_MODEL or "llama3.3"
            self.headers: dict[str, str] = {"Content-Type": "application/json"}
            self.provider_name: str = f"ollama/{self.model}"
        elif self.groq_api_key:
            self.endpoint_url = "https://api.groq.com/openai/v1/chat/completions"
            self.model = model or settings.GROQ_MODEL or "llama-3.3-70b-versatile"
            self.headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            }
            self.provider_name = f"groq/{self.model}"
        else:
            self.endpoint_url = ""
            self.model = ""
            self.headers = {}
            self.provider_name = "external/disabled"

    def is_available(self) -> bool:
        """Return True if an external endpoint (Groq API key or Ollama host) is configured."""
        return bool(self.endpoint_url)

    @staticmethod
    def _extract_system_instruction(config: types.GenerateContentConfig) -> Optional[str]:
        """Extract plain string system instruction from `types.GenerateContentConfig`."""
        sys_inst = getattr(config, "system_instruction", None)
        if not sys_inst:
            return None
        if isinstance(sys_inst, str):
            return sys_inst
        if isinstance(sys_inst, list):
            texts: list[str] = []
            for item in sys_inst:
                if isinstance(item, str):
                    texts.append(item)
                elif hasattr(item, "text") and item.text:
                    texts.append(str(item.text))
            return "\n".join(texts)
        if hasattr(sys_inst, "text") and sys_inst.text:
            return str(sys_inst.text)
        return str(sys_inst)

    @classmethod
    def convert_tools_to_openai(cls, tools: list[Any]) -> list[dict[str, Any]]:
        """Convert tool callables or objects to OpenAI JSON schema function definitions.

        Why: Guarantees compatibility with OpenAI/Groq function calling specifications.
        """
        openai_tools: list[dict[str, Any]] = []
        for tool in tools:
            name = getattr(tool, "__name__", str(tool))
            if name in STORE_TOOL_SCHEMAS:
                openai_tools.append(STORE_TOOL_SCHEMAS[name])
                continue

            # Fallback: introspect generic callable
            doc = inspect.getdoc(tool) or f"Execute {name}."
            openai_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": doc.split("\n")[0],
                        "parameters": {
                            "type": "object",
                            "properties": {},
                        },
                    },
                }
            )
        return openai_tools

    @classmethod
    def convert_contents_to_openai_messages(
        cls,
        contents: list[types.Content],
        system_instruction: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Translate Google GenAI `types.Content` turns into OpenAI chat completion messages.

        Why: Reconstructs exact conversational history and tool-call linkages for models
        expecting standard OpenAI role messages (`system`, `user`, `assistant`, `tool`).
        """
        messages: list[dict[str, Any]] = []
        pending_ids_by_name: dict[str, list[str]] = {}

        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        for turn_idx, content in enumerate(contents):
            role = content.role
            parts = getattr(content, "parts", None) or []

            if role == "user":
                # Check for tool responses
                has_function_response = False
                for part_idx, part in enumerate(parts):
                    fr = getattr(part, "function_response", None)
                    if fr is not None:
                        has_function_response = True
                        fn_name = str(fr.name)
                        id_queue = pending_ids_by_name.get(fn_name)
                        call_id = (
                            id_queue.pop(0)
                            if id_queue
                            else f"call_{turn_idx}_{part_idx}_{fn_name}"
                        )
                        resp_payload = getattr(fr, "response", {})
                        if not isinstance(resp_payload, (dict, list, str)):
                            resp_payload = {"result": str(resp_payload)}
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call_id,
                                "name": fn_name,
                                "content": json.dumps(resp_payload, ensure_ascii=False),
                            }
                        )
                if not has_function_response:
                    text_parts = [
                        getattr(p, "text", "") for p in parts if getattr(p, "text", None)
                    ]
                    messages.append(
                        {
                            "role": "user",
                            "content": "\n".join(text_parts),
                        }
                    )

            elif role == "model":
                # Check for tool calls
                fc_calls: list[dict[str, Any]] = []
                text_chunks: list[str] = []
                for part_idx, part in enumerate(parts):
                    fc = getattr(part, "function_call", None)
                    if fc is not None:
                        fn_name = str(fc.name)
                        call_id = f"call_{turn_idx}_{part_idx}_{fn_name}"
                        pending_ids_by_name.setdefault(fn_name, []).append(call_id)
                        args = getattr(fc, "args", {}) or {}
                        fc_calls.append(
                            {
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": fn_name,
                                    "arguments": json.dumps(dict(args), ensure_ascii=False),
                                },
                            }
                        )
                    else:
                        txt = getattr(part, "text", None)
                        if txt:
                            text_chunks.append(str(txt))

                assistant_msg: dict[str, Any] = {"role": "assistant"}
                if text_chunks:
                    assistant_msg["content"] = "\n".join(text_chunks)
                else:
                    assistant_msg["content"] = None

                if fc_calls:
                    assistant_msg["tool_calls"] = fc_calls

                messages.append(assistant_msg)

        return messages

    @classmethod
    def convert_openai_response_to_gemini(
        cls, response_data: dict[str, Any]
    ) -> types.GenerateContentResponse:
        """Convert an OpenAI-compatible JSON response dictionary into a `types.GenerateContentResponse`.

        Why: Ensures `EmporioAgent` digests the response using standard `google-genai` types
        without needing model-specific branching in the ReAct loop.
        """
        choices = response_data.get("choices") or []
        if not choices:
            raise ValueError(f"OpenAI-compatible response has no choices: {response_data}")

        choice_msg = choices[0].get("message") or {}
        parts: list[types.Part] = []

        tool_calls = choice_msg.get("tool_calls")
        if tool_calls and isinstance(tool_calls, list):
            for tc in tool_calls:
                fn = tc.get("function") or {}
                fn_name = fn.get("name", "")
                args_raw = fn.get("arguments", "{}")
                if isinstance(args_raw, str):
                    try:
                        args_dict = json.loads(args_raw)
                    except json.JSONDecodeError:
                        args_dict = {}
                elif isinstance(args_raw, dict):
                    args_dict = args_raw
                else:
                    args_dict = {}

                parts.append(types.Part.from_function_call(name=fn_name, args=args_dict))

        content_text = choice_msg.get("content")
        if content_text:
            parts.append(types.Part.from_text(text=str(content_text)))

        if not parts:
            parts.append(types.Part.from_text(text=""))

        content = types.Content(role="model", parts=parts)
        candidate = types.Candidate(content=content)
        return types.GenerateContentResponse(candidates=[candidate])

    def generate_content(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        """Execute chat completion against the external provider and return typed response.

        Why: Dispatches HTTP request to Groq or Remote Ollama and translates response.
        """
        if not self.is_available():
            raise RuntimeError(
                "ExternalFallbackProvider is not configured (neither GROQ_API_KEY nor OLLAMA_HOST is set)."
            )

        sys_inst = self._extract_system_instruction(config)
        messages = self.convert_contents_to_openai_messages(
            contents, system_instruction=sys_inst
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": getattr(config, "temperature", 0.1) or 0.1,
        }

        tools = getattr(config, "tools", None)
        if tools and isinstance(tools, list):
            payload["tools"] = self.convert_tools_to_openai(tools)
            payload["tool_choice"] = "auto"

        logger.info(
            "Calling external fallback provider '%s' at %s with %d messages.",
            self.provider_name,
            self.endpoint_url,
            len(messages),
        )

        response = self.http_client.post(
            self.endpoint_url,
            headers=self.headers,
            json=payload,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"External fallback provider '{self.provider_name}' failed with HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        return self.convert_openai_response_to_gemini(data)
