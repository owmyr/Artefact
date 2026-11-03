"""Streamlit Chat Interface with real-time LLM Cascade & Tool Telemetry for Empório da Música.

Why: Provides an interactive web interface for evaluators and customers to test the
stateful ReAct agent (`EmporioAgent`), inspect multi-model fallback cascade health,
switch or reset SQLite-backed conversation sessions, inspect available products via
a dedicated menu dialog, and audit deterministic tool invocations under every assistant turn.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import streamlit as st

from src.agent import EmporioAgent
from src.config import DB_PATH, GEMINI_API_KEY
from src.database import get_connection, init_database

QUICK_PROMPTS: list[tuple[str, str]] = [
    (
        "Violões até R$ 1.000",
        "Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1000?",
    ),
    (
        "Preço do Takamine GD20",
        "Quanto custa o Takamine GD20? Ele ainda está naquela promoção de 12% de desconto?",
    ),
    (
        "Política de Devolução",
        "Me arrependi da minha compra, posso devolver meu pedido? Como funciona a política de devolução?",
    ),
    (
        "Endereço, Contatos e Frete",
        "Qual o endereço da loja, telefones de contato, horário de funcionamento e opções de frete?",
    ),
    (
        "Consulta de Acessórios Avulsos",
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
                        "model_used": model_used or "gemini-3.8-flash",
                        "tool_calls": list(pending_tool_calls),
                        "fallback_events": [],
                    }
                )
                pending_tool_calls = []

        return ui_messages
    finally:
        conn.close()


def _fetch_available_products() -> list[dict[str, Any]]:
    """Query active, in-stock products from the v_product_catalog view.

    Why: Provides exact, pre-filtered data for the store Menu button without
    requiring the customer or evaluator to query through the ReAct loop first.
    """
    if not DB_PATH.exists():
        conn = init_database(DB_PATH)
        conn.close()

    conn = get_connection(DB_PATH)
    try:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT
                product_id,
                name,
                category_name,
                price_brl,
                pix_price_brl,
                active_discount_percent,
                active_promo_description,
                stock_quantity
            FROM v_product_catalog
            WHERE is_available = 1
            ORDER BY category_name ASC, price_brl ASC;
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@st.dialog("Menu de Produtos — Pronta Entrega", width="large")
def _render_product_menu_dialog() -> None:
    """Render interactive dialog showing all instruments currently available for purchase."""
    products = _fetch_available_products()
    if not products:
        st.info("Nenhum instrumento disponível no momento.")
        return

    st.markdown(
        f"Nosso catálogo possui **{len(products)} instrumentos disponíveis para compra imediata** "
        "com pronta entrega na loja física (Campo Grande, MS) e envio para todo o Brasil."
    )

    categories = sorted(list({str(p["category_name"]) for p in products}))
    col_cat, col_search = st.columns([1, 1])
    with col_cat:
        selected_cat = st.selectbox(
            "Filtrar por Categoria",
            options=["Todas as categorias"] + categories,
            index=0,
        )
    with col_search:
        search_query = st.text_input(
            "Buscar por modelo ou marca",
            placeholder="Ex.: Tagima, Fender, Giannini, Yamaha...",
        ).strip().lower()

    filtered = products
    if selected_cat != "Todas as categorias":
        filtered = [p for p in filtered if p["category_name"] == selected_cat]
    if search_query:
        filtered = [p for p in filtered if search_query in p["name"].lower()]

    st.caption(f"{len(filtered)} modelo(s) exibido(s):")

    formatted_rows = []
    for item in filtered:
        cond = (
            f"{item['active_discount_percent']:.0f}% OFF ({item['active_promo_description']})"
            if item.get("active_discount_percent")
            else "Tabela regular (5% OFF no PIX)"
        )
        formatted_rows.append(
            {
                "ID": item["product_id"],
                "Instrumento": item["name"],
                "Categoria": item["category_name"],
                "Preço Tabela": f"R$ {item['price_brl']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "Preço no PIX": f"R$ {item['pix_price_brl']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "Condição": cond,
                "Estoque": item["stock_quantity"],
            }
        )

    st.dataframe(
        formatted_rows,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### Consultar Instrumento no Atendimento")
    product_dict = {
        f"{p['name']} — R$ {p['price_brl']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."): p["name"]
        for p in filtered
    }
    if product_dict:
        selected_key = st.selectbox(
            "Selecione um instrumento para consultar detalhes no chat:",
            options=list(product_dict.keys()),
        )
        if st.button("Perguntar sobre este instrumento no chat", use_container_width=True):
            chosen_name = product_dict[selected_key]
            st.session_state.queued_prompt = (
                f"Gostaria de saber mais sobre o instrumento {chosen_name}, "
                "incluindo especificações técnicas, condições de parcelamento e frete."
            )
            st.rerun()


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
    """Render the Streamlit sidebar with catalog menu shortcut, cascade monitor, and session controls."""
    agent: EmporioAgent = st.session_state.agent

    with st.sidebar:
        st.markdown("## Painel de Controle e Telemetria")

        if not GEMINI_API_KEY:
            st.error(
                "Aviso: `GEMINI_API_KEY` não encontrada no `.env`. "
                "Configure sua chave para executar chamadas aos modelos Gemini."
            )

        # 1. Catalog Menu Button
        st.markdown("### Catálogo")
        if st.button("Abrir Menu de Produtos", use_container_width=True, type="primary"):
            _render_product_menu_dialog()

        st.divider()

        # 2. Session Management
        st.markdown("### Gerenciamento de Sessão")
        saved_sessions = _list_saved_sessions()
        for sid in saved_sessions:
            if sid not in st.session_state.known_sessions:
                st.session_state.known_sessions.append(sid)
        if st.session_state.session_id not in st.session_state.known_sessions:
            st.session_state.known_sessions.insert(0, st.session_state.session_id)

        selected_session = st.selectbox(
            "Sessão Ativa (session_id)",
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
            if st.button("Nova Conversa", use_container_width=True):
                new_sid = f"sessao-{uuid.uuid4().hex[:6]}"
                st.session_state.known_sessions.insert(0, new_sid)
                st.session_state.session_id = new_sid
                st.session_state.messages_by_session[new_sid] = []
                st.rerun()
        with col_clear:
            if st.button("Limpar Conversa", use_container_width=True):
                agent.clear_session(st.session_state.session_id)
                st.session_state.messages_by_session[st.session_state.session_id] = []
                st.rerun()

        st.divider()

        # 3. Active Model Cascade Monitor
        st.markdown("### Cascata de Modelos Gemini")
        last_model = st.session_state.last_model_used
        if last_model:
            st.success(f"**Último Turno:** `{last_model}`")
        else:
            st.info("**Último Turno:** *Aguardando primeira mensagem*")

        health_list = agent.router.get_health_status()
        for item in health_list:
            prio = item["priority"]
            m_name = item["model"]
            state = item["state"]
            rem_s = item["cooldown_remaining_s"]

            is_last = m_name == last_model
            active_badge = " [Ativo]" if is_last else ""

            if state == "ready":
                st.markdown(f"`#{prio}` **[Pronto]** {m_name}{active_badge}")
            elif state == "cooldown":
                st.markdown(
                    f"`#{prio}` **[Cooldown: {rem_s:.0f}s]** {m_name}{active_badge}"
                )
            elif state == "unconfigured":
                st.markdown(f"`#{prio}` **[Opcional]** {m_name} (Não configurado)")
            else:
                st.markdown(f"`#{prio}` **[Desativado]** {m_name}")

        if st.session_state.fallback_history:
            with st.expander(
                f"Eventos de Fallback ({len(st.session_state.fallback_history)})",
                expanded=False,
            ):
                st.json(st.session_state.fallback_history)
        else:
            st.caption("Nenhum evento de fallback (429/503) registrado nesta sessão.")

        st.divider()

        # 4. Quick Prompts for the Evaluator
        st.markdown("### Cenários de Teste Rápidos")
        st.caption("Clique para carregar a pergunta no atendimento:")
        for label, prompt_text in QUICK_PROMPTS:
            if st.button(label, use_container_width=True):
                st.session_state.queued_prompt = prompt_text
                st.rerun()


def _render_telemetry_expander(msg: dict[str, Any]) -> None:
    """Render the expandable telemetry panel under an assistant message."""
    model_used = msg.get("model_used") or "N/A"
    tool_calls: list[dict[str, Any]] = msg.get("tool_calls") or []
    fallback_events: list[dict[str, Any]] = msg.get("fallback_events") or []

    with st.expander("Telemetria da Resposta (Ferramentas e Modelo)", expanded=False):
        col1, col2, col3 = st.columns(3)
        col1.metric("Modelo Utilizado", model_used)
        col2.metric("Ferramentas Executadas", len(tool_calls))
        col3.metric("Fallbacks no Turno", len(fallback_events))

        if tool_calls:
            st.markdown("#### Chamadas de Ferramentas (tool_calls)")
            for idx, tc in enumerate(tool_calls, start=1):
                st.markdown(
                    f"**{idx}. `{tc.get('name', 'unknown')}`** "
                    f"*(solicitado por `{tc.get('model_requested', model_used)}`)*"
                )
                st.markdown("**Argumentos:**")
                st.json(tc.get("args", {}))
                st.markdown("**Retorno Estruturado:**")
                st.json(tc.get("result", {}))
        else:
            st.caption(
                "Nenhuma ferramenta precisou ser invocada neste turno (resposta direta com base nas políticas)."
            )

        if fallback_events:
            st.markdown("#### Eventos de Fallback (fallback_events)")
            st.json(fallback_events)


def main() -> None:
    """Entry point for the Streamlit Chat UI."""
    st.set_page_config(
        page_title="Empório da Música — Atendimento ao Cliente",
        layout="wide",
    )

    _init_session_state()
    _render_sidebar()

    # Branded Header with Action Button
    col_header, col_action = st.columns([3, 1])
    with col_header:
        st.title("Empório da Música — Atendimento ao Cliente")
        st.caption(
            "Loja especializada em instrumentos musicais | "
            "Rua 14 de Maio, 3200 — Centro, Campo Grande, MS | "
            "ReAct Agent + SQLite + Gemini Multi-Model Fallback"
        )
    with col_action:
        st.write("")
        if st.button("Menu de Produtos", use_container_width=True, type="primary"):
            _render_product_menu_dialog()

    current_sid: str = st.session_state.session_id
    messages: list[dict[str, Any]] = st.session_state.messages_by_session.setdefault(
        current_sid, []
    )

    # Welcome message when conversation is empty
    if not messages:
        with st.chat_message("assistant"):
            st.markdown(
                "Olá! Seja bem-vindo à **Empório da Música** (Campo Grande, MS).\n\n"
                "Nosso atendimento pode ajudar você com:\n"
                "- **Consulta ao catálogo** de instrumentos musicais, preços e estoque para pronta entrega;\n"
                "- **Condições de pagamento** (desconto de 5% à vista no PIX, parcelamento em até 12x sem juros e pagamento combinado);\n"
                "- **Acompanhamento de pedidos**, código de rastreamento e prazos de garantia ou devolução;\n"
                "- **Informações da loja**, horários de atendimento, endereço físico e prazos de frete.\n\n"
                "Para visualizar todos os instrumentos disponíveis para pronta entrega, clique no botão **Menu de Produtos** acima.\n\n"
                "Como posso ajudar você hoje?"
            )

    # Render conversation history
    for msg in messages:
        role = msg.get("role", "user")
        with st.chat_message(role):
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
        with st.chat_message("user"):
            st.markdown(active_prompt)

        # Execute ReAct loop via EmporioAgent
        agent: EmporioAgent = st.session_state.agent
        with st.chat_message("assistant"):
            with st.spinner("Consultando catálogo e políticas da loja..."):
                try:
                    result = agent.chat(
                        user_message=active_prompt,
                        session_id=current_sid,
                    )
                    assistant_text = (
                        result.get("response")
                        or "Não foi possível gerar uma resposta no momento."
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
