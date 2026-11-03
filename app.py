"""Streamlit Chat Interface with real-time LLM Cascade & Tool Telemetry for Empório da Música.

Why: Provides an interactive web interface for evaluators and customers to test the
stateful ReAct agent (`EmporioAgent`), inspect multi-model fallback cascade health,
switch or reset SQLite-backed conversation sessions, trigger one-click evaluation
scenarios, and audit deterministic tool invocations under every assistant turn.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import streamlit as st

from src.agent import EmporioAgent
from src.config import DB_PATH, GEMINI_API_KEY, GEMINI_MODEL_CASCADE
from src.database import get_connection, init_database

QUICK_PROMPTS: list[tuple[str, str]] = [
    (
        "🎸 Violões até R$ 1000",
        "Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1000?",
    ),
    (
        "🏷️ Preço do Takamine GD20",
        "Quanto custa o Takamine GD20? Ele ainda está naquela promoção de 12% de desconto?",
    ),
    (
        "🔄 Política de Devolução",
        "Me arrependi da minha compra, posso devolver meu pedido? Como funciona a política de devolução?",
    ),
    (
        "📍 Endereço, Contatos e Frete",
        "Qual o endereço da loja, telefones de contato, horário de funcionamento e opções de frete?",
    ),
    (
        "🚫 Pedido de Encordoamento/Pedal",
        "Preciso comprar um jogo de cordas de aço 0.10, um cabo P10 e um pedal de overdrive. Vocês têm?",
    ),
]


def _list_saved_sessions() -> list[str]:
    """Query distinct `session_id` values persisted in the SQLite `chat_history` table.

    Why: Enables the sidebar session selector to switch seamlessly between historical
    and active customer conversations stored in SQLite.
    """
    if not DB_PATH.exists():
        conn = init_database(DB_PATH)
        conn.close()
        return ["default"]

    conn = get_connection(DB_PATH)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT session_id, MAX(id) AS last_id
            FROM chat_history
            GROUP BY session_id
            ORDER BY last_id DESC;
            """
        ).fetchall()
        sessions = [str(r["session_id"]) for r in rows if r["session_id"]]
        if "default" not in sessions:
            sessions.insert(0, "default")
        return sessions
    finally:
        conn.close()


def _reconstruct_ui_messages_from_db(session_id: str) -> list[dict[str, Any]]:
    """Reconstruct user and assistant chat messages with tool telemetry from SQLite.

    Why: Ensures that switching sessions in the Streamlit sidebar restores not only
    the visible text messages, but also the `model_used` and `tool_calls` executed
    during each assistant turn.
    """
    conn = get_connection(DB_PATH)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT role, content_json, model_used
            FROM chat_history
            WHERE session_id = ?
            ORDER BY turn_index ASC, id ASC;
            """,
            (session_id,),
        ).fetchall()

        ui_messages: list[dict[str, Any]] = []
        pending_tool_calls: list[dict[str, Any]] = []

        for row in rows:
            role = str(row["role"])
            model_used = str(row["model_used"] or "")
            try:
                parts = json.loads(str(row["content_json"]))
            except json.JSONDecodeError:
                continue

            if not isinstance(parts, list):
                continue

            # Check if this row is a user text message
            user_texts = [
                str(p.get("text", ""))
                for p in parts
                if isinstance(p, dict) and p.get("type") == "text" and role == "user"
            ]
            if user_texts:
                pending_tool_calls = []
                ui_messages.append(
                    {
                        "role": "user",
                        "content": "\n".join(user_texts),
                    }
                )
                continue

            # Check if this row contains model function calls
            for p in parts:
                if not isinstance(p, dict):
                    continue
                p_type = p.get("type")
                if p_type == "function_call":
                    pending_tool_calls.append(
                        {
                            "name": str(p.get("name", "")),
                            "args": dict(p.get("args") or {}),
                            "result": None,
                            "model_requested": model_used,
                        }
                    )
                elif p_type == "function_response":
                    resp_obj = p.get("response") or {}
                    tool_result = (
                        resp_obj.get("result", resp_obj)
                        if isinstance(resp_obj, dict)
                        else resp_obj
                    )
                    # Attach result to the first matching pending tool call without a result
                    for tc in pending_tool_calls:
                        if tc["name"] == p.get("name") and tc["result"] is None:
                            tc["result"] = tool_result
                            break

            # Check if this row is the final assistant text response
            model_texts = [
                str(p.get("text", ""))
                for p in parts
                if isinstance(p, dict) and p.get("type") == "text" and role == "model"
            ]
            if model_texts:
                ui_messages.append(
                    {
                        "role": "assistant",
                        "content": "\n".join(model_texts),
                        "model_used": model_used or "gemini-2.5-flash",
                        "tool_calls": list(pending_tool_calls),
                        "fallback_events": [],
                    }
                )
                pending_tool_calls = []

        return ui_messages
    finally:
        conn.close()


def _init_session_state() -> None:
    """Initialize Streamlit session state variables for the agent, session ID, and telemetry."""
    if "agent" not in st.session_state:
        st.session_state.agent = EmporioAgent()
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"
    if "last_model_used" not in st.session_state:
        st.session_state.last_model_used = None
    if "fallback_history" not in st.session_state:
        st.session_state.fallback_history = []
    if "messages_by_session" not in st.session_state:
        st.session_state.messages_by_session = {}
    if "known_sessions" not in st.session_state:
        st.session_state.known_sessions = _list_saved_sessions()
    if "queued_prompt" not in st.session_state:
        st.session_state.queued_prompt = None

    current_sid = st.session_state.session_id
    if current_sid not in st.session_state.messages_by_session:
        st.session_state.messages_by_session[current_sid] = (
            _reconstruct_ui_messages_from_db(current_sid)
        )


def _render_sidebar() -> None:
    """Render the Streamlit sidebar with cascade monitor, session controls, and quick prompts."""
    agent: EmporioAgent = st.session_state.agent

    with st.sidebar:
        st.markdown("## ⚙️ Painel de Controle & Telemetria")

        if not GEMINI_API_KEY:
            st.error(
                "⚠️ `GEMINI_API_KEY` não encontrada no `.env`. Configure sua chave para executar chamadas ao Gemini."
            )

        # 1. Session Management
        st.markdown("### 💬 Gerenciamento de Sessão")
        saved_sessions = _list_saved_sessions()
        for sid in saved_sessions:
            if sid not in st.session_state.known_sessions:
                st.session_state.known_sessions.append(sid)
        if st.session_state.session_id not in st.session_state.known_sessions:
            st.session_state.known_sessions.insert(0, st.session_state.session_id)

        selected_session = st.selectbox(
            "Sessão Ativa (`session_id`)",
            options=st.session_state.known_sessions,
            index=st.session_state.known_sessions.index(st.session_state.session_id),
        )
        if selected_session != st.session_state.session_id:
            st.session_state.session_id = selected_session
            if selected_session not in st.session_state.messages_by_session:
                st.session_state.messages_by_session[selected_session] = (
                    _reconstruct_ui_messages_from_db(selected_session)
                )
            st.rerun()

        col_new, col_clear = st.columns(2)
        with col_new:
            if st.button("➕ Nova Conversa", use_container_width=True):
                new_sid = f"sessao-{uuid.uuid4().hex[:6]}"
                st.session_state.known_sessions.insert(0, new_sid)
                st.session_state.session_id = new_sid
                st.session_state.messages_by_session[new_sid] = []
                st.rerun()
        with col_clear:
            if st.button("🗑️ Limpar Atual", use_container_width=True):
                agent.clear_session(st.session_state.session_id)
                st.session_state.messages_by_session[st.session_state.session_id] = []
                st.rerun()

        st.divider()

        # 2. Active Model Cascade Monitor
        st.markdown("### 🤖 Cascata de Modelos Gemini")
        last_model = st.session_state.last_model_used
        if last_model:
            st.success(f"**Último Turno:** `{last_model}`")
        else:
            st.info("**Último Turno:** *Aguardando 1ª mensagem*")

        health_list = agent.router.get_health_status()
        for item in health_list:
            prio = item["priority"]
            m_name = item["model"]
            state = item["state"]
            rem_s = item["cooldown_remaining_s"]

            is_last = m_name == last_model
            active_badge = " 👈 *(Ativo)*" if is_last else ""

            if state == "ready":
                st.markdown(f"`#{prio}` 🟢 **{m_name}** — Pronto{active_badge}")
            elif state == "cooldown":
                st.markdown(
                    f"`#{prio}` 🟡 **{m_name}** — Cooldown ({rem_s:.0f}s){active_badge}"
                )
            else:
                st.markdown(f"`#{prio}` 🔴 **{m_name}** — Desativado")

        if st.session_state.fallback_history:
            with st.expander(
                f"⚡ Eventos de Fallback ({len(st.session_state.fallback_history)})",
                expanded=False,
            ):
                st.json(st.session_state.fallback_history)
        else:
            st.caption("Nenhum evento de fallback (429/503) registrado nesta sessão.")

        st.divider()

        # 3. Quick Prompts for the Evaluator
        st.markdown("### ⚡ Prompts Rápidos (Avaliador)")
        st.caption("Clique para enviar automaticamente ao agente:")
        for label, prompt_text in QUICK_PROMPTS:
            if st.button(label, use_container_width=True):
                st.session_state.queued_prompt = prompt_text
                st.rerun()


def _render_telemetry_expander(msg: dict[str, Any]) -> None:
    """Render the expandable telemetry panel under an assistant message."""
    model_used = msg.get("model_used") or "N/A"
    tool_calls: list[dict[str, Any]] = msg.get("tool_calls") or []
    fallback_events: list[dict[str, Any]] = msg.get("fallback_events") or []

    with st.expander("🔍 Telemetria da Resposta (Tools & Modelo)", expanded=False):
        col1, col2, col3 = st.columns(3)
        col1.metric("Modelo Utilizado", model_used)
        col2.metric("Tools Executadas", len(tool_calls))
        col3.metric("Fallbacks no Turno", len(fallback_events))

        if tool_calls:
            st.markdown("#### 🛠️ Chamadas de Ferramentas (`tool_calls`)")
            for idx, tc in enumerate(tool_calls, start=1):
                st.markdown(
                    f"**{idx}. `{tc.get('name', 'unknown')}`** "
                    f"*(solicitado por `{tc.get('model_requested', model_used)}`)*"
                )
                st.markdown("**Argumentos:**")
                st.json(tc.get("args", {}))
                st.markdown("**Saída Determinística (JSON):**")
                st.json(tc.get("result", {}))
        else:
            st.caption(
                "Nenhuma ferramenta precisou ser invocada neste turno (resposta direta/guardrail)."
            )

        if fallback_events:
            st.markdown("#### ⚠️ Eventos de Fallback (`fallback_events`)")
            st.json(fallback_events)


def main() -> None:
    """Entry point for the Streamlit Chat UI."""
    st.set_page_config(
        page_title="Empório da Música — Assistente Virtual",
        page_icon="🎸",
        layout="wide",
    )

    _init_session_state()
    _render_sidebar()

    # Branded Header
    st.title("🎸 Empório da Música — Assistente Virtual (Campo Grande/MS)")
    st.caption(
        "Atendimento inteligente especializado em instrumentos musicais | "
        "Rua 14 de Maio, 3200 — Centro, Campo Grande/MS | "
        "ReAct Agent + SQLite + Gemini Multi-Model Fallback"
    )

    current_sid: str = st.session_state.session_id
    messages: list[dict[str, Any]] = st.session_state.messages_by_session.setdefault(
        current_sid, []
    )

    # Welcome message when conversation is empty
    if not messages:
        with st.chat_message("assistant", avatar="🎸"):
            st.markdown(
                "Olá! Seja muito bem-vindo(a) à **Empório da Música** (*Sua música começa aqui*! 🎶).\n\n"
                "Sou o assistente virtual da nossa loja em Campo Grande/MS. Posso ajudar você a:\n"
                "- 🎸 **Consultar nosso catálogo** de instrumentos musicais, preços, especificações e estoque;\n"
                "- 💳 **Simular pagamentos** (desconto de 5% no PIX, parcelamento sem juros em até 12x e pagamento combinado);\n"
                "- 📦 **Acompanhar seus pedidos**, códigos de rastreio e prazos de troca ou garantia;\n"
                "- 📋 **Tirar dúvidas sobre nossas políticas**, endereço, horários e frete.\n\n"
                "Como posso ajudar você hoje?"
            )

    # Render conversation history
    for msg in messages:
        role = msg.get("role", "user")
        avatar = "🎸" if role == "assistant" else "🧑‍🎤"
        with st.chat_message(role, avatar=avatar):
            st.markdown(msg.get("content", ""))
            if role == "assistant":
                _render_telemetry_expander(msg)

    # Check if a quick-prompt button was clicked or user typed in chat_input
    chat_input_val = st.chat_input(
        "Digite sua dúvida sobre instrumentos, preços, pedidos ou políticas da loja..."
    )
    active_prompt: str | None = None
    if st.session_state.queued_prompt:
        active_prompt = st.session_state.queued_prompt
        st.session_state.queued_prompt = None
    elif chat_input_val:
        active_prompt = chat_input_val

    if active_prompt:
        # Render user message immediately
        messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user", avatar="🧑‍🎤"):
            st.markdown(active_prompt)

        # Execute ReAct loop via EmporioAgent
        agent: EmporioAgent = st.session_state.agent
        with st.chat_message("assistant", avatar="🎸"):
            with st.spinner("Consultando catálogo, políticas e processando resposta..."):
                try:
                    result = agent.chat(
                        user_message=active_prompt,
                        session_id=current_sid,
                    )
                    assistant_text = (
                        result.get("response")
                        or "Desculpe, não consegui gerar uma resposta no momento."
                    )
                    model_used = result.get("model_used", "")
                    tool_calls = result.get("tool_calls", [])
                    fallback_events = result.get("fallback_events", [])

                    st.session_state.last_model_used = model_used
                    if fallback_events:
                        st.session_state.fallback_history.extend(fallback_events)

                    assistant_msg = {
                        "role": "assistant",
                        "content": assistant_text,
                        "model_used": model_used,
                        "tool_calls": tool_calls,
                        "fallback_events": fallback_events,
                    }
                    messages.append(assistant_msg)
                    st.markdown(assistant_text)
                    _render_telemetry_expander(assistant_msg)

                except Exception as exc:
                    st.error(f"Erro ao processar solicitação: {exc}")

        st.rerun()


if __name__ == "__main__":
    main()
