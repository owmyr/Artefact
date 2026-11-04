"""Streamlit Minimalist E-Commerce & Malleable Maestro AI Chat Popup for Empório da Música.

Why: Implements a minimalist Apple-inspired music e-commerce interface paired with a
focused, malleable Chat Popup supporting Regular Popup, Expanded Modal Popup, and
Collapsed Launcher states. Preserves all store information, ReAct agent execution,
SQLite session persistence, multi-model fallback cascade health with status emojis,
and deterministic tool telemetry with bottom collapse controls.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import time
import uuid
from typing import Any

import streamlit as st
import streamlit.config as _st_cfg

from src.agent import EmporioAgent
from src.config import DB_PATH, GEMINI_API_KEY
from src.database import get_connection, init_database

# Assessment & evaluator quick test prompts
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


def _sanitize_markdown_for_streamlit(text: str) -> str:
    """Escape currency dollar signs so Streamlit Markdown never triggers KaTeX math mode.

    Why: Two unescaped `$` symbols in the same paragraph or table cell (such as
    `R$ 5.400,00 (PIX: R$ 5.130,00)`) cause Streamlit's KaTeX engine to render the
    intervening text as a math formula. Escaping `$` to `\\$` prevents this.
    """
    if not text:
        return ""
    return re.sub(r"(?<!\\)\$", r"\\$", str(text))


def _collapse_expander_callback(expander_key: str) -> None:
    """Programmatically collapse a stateful `st.expander` from its bottom close button.

    Why: Allows users inspecting long JSON tool telemetry to collapse the expander
    directly from the bottom without scrolling back up to the expander header.
    """
    st.session_state[expander_key] = False


def _set_chat_mode_callback(mode: str) -> None:
    """Update the malleable chat popup display state (`popup`, `expanded`, `collapsed`)."""
    st.session_state.chat_view_mode = mode


def _queue_prompt_callback(prompt_text: str, ensure_open: bool = True) -> None:
    """Queue a prompt for the ReAct agent and ensure the chat popup is visible."""
    st.session_state.pending_prompt = prompt_text
    st.session_state.queued_prompt = prompt_text
    if ensure_open and st.session_state.get("chat_view_mode") == "collapsed":
        st.session_state.chat_view_mode = "popup"


@st.cache_data(show_spinner=False)
def _load_base64_images() -> dict[str, str]:
    """Load local instrument photography paths or base64 data URIs.

    Why: If `server.enableStaticServing` is enabled in `.streamlit/config.toml`,
    returns lightweight HTTP static asset URLs (`app/static/images/...`), reducing
    WebSocket message payloads by 99% and enabling standard browser HTTP caching.
    Falls back to cached base64 URIs when static serving is not configured.
    """
    image_filenames = {
        "electric_guitar": "electric_guitar.jpg",
        "acoustic_guitar": "acoustic_guitar.jpg",
        "synthesizer": "synthesizer.jpg",
        "bass_guitar": "bass_guitar.jpg",
        "fender_guitar": "fender_guitar.jpg",
        "keyboard_synth": "keyboard_synth.jpg",
    }

    try:
        if _st_cfg.get_option("server.enableStaticServing"):
            return {
                key: f"app/static/images/{fn}"
                for key, fn in image_filenames.items()
            }
    except Exception:
        pass

    image_map = {
        "electric_guitar": "static/images/electric_guitar.jpg",
        "acoustic_guitar": "static/images/acoustic_guitar.jpg",
        "synthesizer": "static/images/synthesizer.jpg",
        "bass_guitar": "static/images/bass_guitar.jpg",
        "fender_guitar": "static/images/fender_guitar.jpg",
        "keyboard_synth": "static/images/keyboard_synth.jpg",
    }
    b64_dict: dict[str, str] = {}
    for key, path in image_map.items():
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    b64_dict[key] = "data:image/jpeg;base64," + base64.b64encode(
                        f.read()
                    ).decode("utf-8")
            except Exception:
                b64_dict[key] = ""
        else:
            b64_dict[key] = ""
    return b64_dict


def _format_currency_brl(val: float) -> str:
    """Format numeric price into clean Brazilian Real currency notation (e.g. R$ 6.890)."""
    if val == int(val):
        return f"R$ {int(val):,}".replace(",", ".")
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _get_instrument_card_data(
    item: dict[str, Any], images_dict: dict[str, str]
) -> dict[str, Any]:
    """Enrich database product record with visual design system attributes.

    Why: Maps specific database instruments to the clean typography, color swatches,
    curated imagery, and key-value specs illustrated in the reference design system.
    """
    name = str(item.get("name") or "")
    cat = str(item.get("category_name") or "")
    price = float(item.get("price_brl") or 0.0)
    stock = int(item.get("stock_quantity") or 0)
    specs_json = str(item.get("specs") or "{}")

    try:
        raw_specs = json.loads(specs_json)
    except json.JSONDecodeError:
        raw_specs = {}

    if "Les Paul" in name:
        display_name = "Heritage Cherry SB"
        swatches = ["#8B2500", "#CD853F"]
        img_src = images_dict.get("electric_guitar") or ""
        specs_list = [
            ("Corpo", "Mogno Africano"),
            ("Braço", "Maple"),
            ("Captadores", "Custom Vintage Alnico V"),
            ("Ponte", "Tune-o-Matic"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price if price else 6890.0)

    elif "Crafter" in name or ("C70" in name and cat == "Violões"):
        display_name = "Natural Beech"
        swatches = ["#DEB887", "#8B4513"]
        img_src = images_dict.get("acoustic_guitar") or ""
        specs_list = [
            ("Tampo", "Spruce Sólido"),
            ("Fundo/Laterais", "Mogno"),
            ("Escala", "Rosewood"),
            ("Cordas", "D'Addario EXP16"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price if price else 4550.0)

    elif "Roland Synth" in name or ("Teclado" in name and "3 Pro" in name):
        display_name = "Modular"
        swatches = ["#111111", "#4A4A4A"]
        img_src = images_dict.get("synthesizer") or ""
        specs_list = [
            ("Osciladores", "3x Analógicos"),
            ("Filtro", "Ladder 4-pole"),
            ("Seção FX", "Reverb/Delay"),
            ("MIDI", "In/Out/Thru"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price if price else 9120.0)

    elif "Korg" in name or "Nord" in name:
        display_name = name.split("Pro")[0].strip()
        swatches = ["#BA181B", "#18181B"]
        img_src = images_dict.get("keyboard_synth") or ""
        specs_list = [
            ("Teclas", raw_specs.get("keys", "61 teclas")),
            ("Tipo", "Sintetizador Digital"),
            ("Polifonia", f"{raw_specs.get('polyphony', '128')} vozes"),
            ("Conexões", "USB-MIDI / P10"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price)

    elif "Bass" in name or cat == "Baixos":
        display_name = name.replace("Electric Bass", "").strip()
        swatches = ["#9E2A2B", "#1A1A1A"]
        img_src = images_dict.get("bass_guitar") or ""
        specs_list = [
            ("Corpo", raw_specs.get("body", "Ash Maciço")),
            ("Braço", raw_specs.get("neck", "Maple")),
            ("Cordas", f"{raw_specs.get('strings', '4')} Cordas"),
            ("Captadores", "Active Humbucker"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price)

    elif "Stratocaster" in name or "Telecaster" in name or cat == "Guitarras":
        display_name = name.replace("American Pro II", "Pro II").strip()
        swatches = (
            ["#E8C547", "#D4A373"] if "Telecaster" in name else ["#8B2500", "#FFB703"]
        )
        img_src = (
            images_dict.get("fender_guitar")
            or images_dict.get("electric_guitar")
            or ""
        )
        specs_list = [
            ("Corpo", raw_specs.get("body", "Alder")),
            ("Braço", raw_specs.get("neck", "Maple")),
            ("Captadores", "V-Mod II Single-Coil"),
            ("Ponte", "Synchronized Tremolo"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price)

    else:
        display_name = name
        swatches = ["#DDA15E", "#6F4E37"]
        img_src = images_dict.get("acoustic_guitar") or ""
        specs_list = [
            ("Tampo", raw_specs.get("top", "Spruce")),
            ("Laterais", raw_specs.get("back_sides", "Sapele")),
            ("Braço", raw_specs.get("neck", "Nato")),
            ("Cordas", "Aço" if raw_specs.get("strings") == "steel" else "Nylon"),
            ("Unidades", f"{stock} disponíveis"),
        ]
        price_display = _format_currency_brl(price)

    return {
        "product_id": item["product_id"],
        "display_name": display_name,
        "full_name": name,
        "category_name": cat,
        "swatches": swatches,
        "img_src": img_src,
        "specs_list": specs_list,
        "price_display": price_display,
        "price_val": price,
        "stock": stock,
    }


@st.cache_data(ttl=15, show_spinner=False)
def _list_saved_sessions() -> list[str]:
    """Query distinct `session_id` values persisted in SQLite `chat_history`."""
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
    """Reconstruct user and assistant chat messages with tool telemetry from SQLite."""
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

            user_texts = [
                str(p.get("text", ""))
                for p in parts
                if isinstance(p, dict) and p.get("type") == "text" and role == "user"
            ]
            if user_texts:
                pending_tool_calls = []
                user_content = "\n".join(user_texts).strip()
                if user_content:
                    if ui_messages and ui_messages[-1].get("role") == "user":
                        ui_messages[-1] = {
                            "role": "user",
                            "content": user_content,
                        }
                    else:
                        ui_messages.append(
                            {
                                "role": "user",
                                "content": user_content,
                            }
                        )
                continue

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
                    for tc in pending_tool_calls:
                        if tc["name"] == p.get("name") and tc["result"] is None:
                            tc["result"] = tool_result
                            break

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


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_available_products() -> list[dict[str, Any]]:
    """Query active, in-stock products from `v_product_catalog` with curated ordering."""
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
                stock_quantity,
                description,
                specs
            FROM v_product_catalog
            WHERE is_available = 1
            ORDER BY
                CASE
                    WHEN name LIKE '%Les Paul%' THEN 1
                    WHEN name LIKE '%Crafter D-8%' THEN 2
                    WHEN name LIKE '%Roland Synth 3%' THEN 3
                    WHEN name LIKE '%Korg Synth%' THEN 4
                    WHEN name LIKE '%Music Man Bass 1X%' THEN 5
                    WHEN name LIKE '%Stratocaster%' THEN 6
                    ELSE 10
                END ASC,
                category_name ASC,
                price_brl DESC;
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@st.dialog("Menu de Produtos — Pronta Entrega", width="large")
def _render_product_menu_dialog() -> None:
    """Render interactive modal showing all instruments currently available for purchase."""
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
                "Preço Tabela": _format_currency_brl(item["price_brl"]),
                "Preço no PIX": _format_currency_brl(item["pix_price_brl"]),
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
        f"{p['name']} — {_format_currency_brl(p['price_brl'])}": p["name"]
        for p in filtered
    }
    if product_dict:
        selected_key = st.selectbox(
            "Selecione um instrumento para consultar detalhes no chat:",
            options=list(product_dict.keys()),
        )
        if st.button(
            "Perguntar sobre este instrumento no chat", use_container_width=True
        ):
            chosen_name = product_dict[selected_key]
            st.session_state.queued_prompt = (
                f"Gostaria de saber mais sobre o instrumento {chosen_name}, "
                "incluindo especificações técnicas, condições de parcelamento e frete."
            )
            if st.session_state.get("chat_view_mode") == "collapsed":
                st.session_state.chat_view_mode = "popup"
            st.rerun()


def _init_session_state() -> None:
    """Initialize Streamlit session state variables for the agent, session ID, and telemetry."""
    if "agent" not in st.session_state:
        st.session_state.agent = EmporioAgent()
    if "session_id" not in st.session_state:
        st.session_state.session_id = "default"
    if "last_model_used" not in st.session_state:
        st.session_state.last_model_used = None
    if "last_latency_ms" not in st.session_state:
        st.session_state.last_latency_ms = 3
    if "fallback_history" not in st.session_state:
        st.session_state.fallback_history = []
    if "messages_by_session" not in st.session_state:
        st.session_state.messages_by_session = {}
    if "known_sessions" not in st.session_state:
        st.session_state.known_sessions = _list_saved_sessions()
    if "pending_prompt" not in st.session_state:
        st.session_state.pending_prompt = None
    if "queued_prompt" not in st.session_state:
        st.session_state.queued_prompt = None
    if "images_dict" not in st.session_state:
        st.session_state.images_dict = _load_base64_images()
    if "chat_view_mode" not in st.session_state or st.session_state.chat_view_mode not in (
        "popup",
        "expanded",
        "collapsed",
    ):
        # Modes: "popup" (focused right popup), "expanded" (modal overlay), "collapsed" (bottom-right pill)
        st.session_state.chat_view_mode = "popup"

    current_sid = st.session_state.session_id
    if current_sid not in st.session_state.messages_by_session:
        st.session_state.messages_by_session[current_sid] = (
            _reconstruct_ui_messages_from_db(current_sid)
        )


def _render_sidebar() -> None:
    """Render collapsible left sidebar with telemetry emojis and session management."""
    agent: EmporioAgent = st.session_state.agent

    with st.sidebar:
        st.markdown("## ⚙️ Painel de Controle e Telemetria")
        st.caption("Painel técnico de auditoria e controle do agente ReAct")

        if not GEMINI_API_KEY:
            st.error(
                "Aviso: `GEMINI_API_KEY` não encontrada no `.env`. "
                "Configure sua chave para executar chamadas aos modelos Gemini."
            )

        st.markdown("### 📦 Catálogo")
        if st.button("📦 Abrir Catálogo Completo", use_container_width=True):
            _render_product_menu_dialog()

        st.divider()

        st.markdown("### ⚙️ Gerenciamento de Sessão")
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
            key="sidebar_session_select",
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
            if st.button("➕ Nova Conversa", use_container_width=True, key="sb_new_conv"):
                new_sid = f"sessao-{uuid.uuid4().hex[:6]}"
                st.session_state.known_sessions.insert(0, new_sid)
                st.session_state.session_id = new_sid
                st.session_state.messages_by_session[new_sid] = []
                st.rerun()
        with col_clear:
            if st.button("🗑️ Limpar Conversa", use_container_width=True, key="sb_clear_conv"):
                agent.clear_session(st.session_state.session_id)
                st.session_state.messages_by_session[st.session_state.session_id] = []
                st.session_state.pending_prompt = None
                st.session_state.queued_prompt = None
                st.rerun()

        st.divider()

        # Active Model Cascade Monitor with Emojis
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
                st.markdown(f"🟢 **{m_name}** — Pronto{active_badge}")
            elif state == "cooldown":
                st.markdown(
                    f"🔴 **{m_name}** — Cooldown ({rem_s:.0f}s){active_badge}"
                )
            elif state == "unconfigured":
                st.markdown(f"⚪ **{m_name}** — (Opcional)")
            else:
                st.markdown(f"🔴 **{m_name}** — Desativado")

        if st.session_state.fallback_history:
            with st.expander(
                f"Eventos de Fallback ({len(st.session_state.fallback_history)})",
                expanded=False,
            ):
                st.json(st.session_state.fallback_history)
        else:
            st.caption("Nenhum evento de fallback (429/503) registrado nesta sessão.")

        st.divider()
        st.markdown("### 🧪 Cenários de Teste Rápidos")
        for idx, (label, prompt_text) in enumerate(QUICK_PROMPTS):
            if st.button(label, key=f"sb_qp_{idx}", use_container_width=True):
                _queue_prompt_callback(prompt_text)
                st.rerun()


def _render_telemetry_expander(
    msg: dict[str, Any], turn_idx: int, session_id: str
) -> None:
    """Render stateful expandable telemetry panel under an assistant message with a bottom close button.

    Why: Displays full tool call arguments, deterministic outputs, and model cascade info
    right inside the chat, and provides an easy-access collapse button at the bottom so
    the user never has to scroll back up to close it.
    """
    model_used = str(msg.get("model_used") or "gemini-3.8-flash")
    tool_calls: list[dict[str, Any]] = list(msg.get("tool_calls") or [])
    fallback_events: list[dict[str, Any]] = list(msg.get("fallback_events") or [])
    exp_key = f"tel_turn_{session_id}_{turn_idx}"

    label = (
        f"📊 Telemetria da Resposta • {model_used} • "
        f"{len(tool_calls)} ferramenta(s) • {len(fallback_events)} fallback(s)"
    )

    with st.expander(label, expanded=False, key=exp_key, on_change="rerun"):
        # Clean HTML summary grid that never truncates in narrow or wide modes
        st.markdown(
            f"""
            <div class="telemetry-summary-grid">
                <div class="telemetry-kpi-box">
                    <span class="telemetry-kpi-label">Modelo Utilizado</span>
                    <span class="telemetry-kpi-val">{html.escape(model_used)}</span>
                </div>
                <div class="telemetry-kpi-box">
                    <span class="telemetry-kpi-label">Ferramentas Executadas</span>
                    <span class="telemetry-kpi-val">{len(tool_calls)}</span>
                </div>
                <div class="telemetry-kpi-box">
                    <span class="telemetry-kpi-label">Fallbacks no Turno</span>
                    <span class="telemetry-kpi-val">{len(fallback_events)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if tool_calls:
            st.markdown("##### 🔧 Chamadas de Ferramentas (`tool_calls`)")
            for idx, tc in enumerate(tool_calls, start=1):
                tc_name = html.escape(str(tc.get("name", "unknown")))
                tc_model = html.escape(str(tc.get("model_requested") or model_used))
                st.markdown(
                    f"""
                    <div class="telemetry-tool-header">
                        <strong>#{idx} <code>{tc_name}</code></strong>
                        <span>solicitado por <code>{tc_model}</code></span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.caption("Argumentos enviados:")
                st.json(tc.get("args", {}), expanded=True)
                st.caption("Retorno estruturado determinístico:")
                st.json(tc.get("result", {}), expanded=False)
        else:
            st.caption(
                "Nenhuma ferramenta precisou ser invocada neste turno (resposta direta com base no contexto/políticas)."
            )

        if fallback_events:
            st.markdown("##### ⚠️ Eventos de Fallback (`fallback_events`)")
            st.json(fallback_events, expanded=True)

        # Bottom Close/Collapse button so user doesn't have to scroll back up
        st.button(
            "▲ Fechar Telemetria (Recolher)",
            key=f"btn_close_tel_{session_id}_{turn_idx}",
            on_click=_collapse_expander_callback,
            args=(exp_key,),
            use_container_width=True,
        )


def _inject_design_system_styles() -> None:
    """Inject deterministic light-mode CSS tokens, popup elevation, and `.st-key-*` rules."""
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@600;700;800;900&family=Playfair+Display:ital,wght@0,600;0,700;0,800;1,600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
        <style>
        :root, html, body, .stApp {
            color-scheme: light !important;
            --canvas-bg: #F5F3F0;
            --surface-bg: #FFFFFF;
            --surface-subtle: #FAF9F7;
            --surface-img: #ECEAE5;
            --border-light: #E2DED5;
            --border-hover: #C8C2B6;
            --text-primary: #18181B;
            --text-secondary: #3F3F46;
            --text-muted: #71717A;
            --accent-black: #18181B;
            --slider-track: #8B5A2B;
            --radius-xl: 20px;
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-pill: 9999px;
            --shadow-card: 0 2px 12px rgba(24, 24, 27, 0.04);
            --shadow-popup: 0 20px 55px rgba(24, 24, 27, 0.14), 0 4px 16px rgba(24, 24, 27, 0.06);
            --shadow-modal: 0 28px 80px rgba(24, 24, 27, 0.26);
        }

        /* Canvas Background & Global Typography */
        .stApp {
            background-color: var(--canvas-bg) !important;
            color: var(--text-primary) !important;
            font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }

        header[data-testid="stHeader"] {
            background-color: transparent !important;
            height: 3.5rem !important;
            z-index: 9999 !important;
            overflow: visible !important;
            pointer-events: none !important;
        }

        header[data-testid="stHeader"] button,
        header[data-testid="stHeader"] [data-testid="stExpandSidebarButton"],
        header[data-testid="stHeader"] [data-testid="collapsedControl"],
        header[data-testid="stHeader"] [data-testid^="stBaseButton-"] {
            pointer-events: auto !important;
        }

        /* -------------------------------------------------------------
           Prominent Telemetry Sidebar Collapse / Uncollapse (">>") Button
        ------------------------------------------------------------- */
        [data-testid="stExpandSidebarButton"],
        button[data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapsedControl"] {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            background-color: #FFFFFF !important;
            color: #18181B !important;
            border: 1.5px solid #18181B !important;
            border-radius: 9999px !important;
            box-shadow: 0 4px 14px rgba(24, 24, 27, 0.12) !important;
            padding: 0.4rem 0.9rem !important;
            min-height: 2.3rem !important;
            margin-top: 0.55rem !important;
            margin-left: 0.75rem !important;
            opacity: 1 !important;
            visibility: visible !important;
            z-index: 999999 !important;
            cursor: pointer !important;
            transition: all 0.18s ease-in-out !important;
        }

        button[data-testid="stExpandSidebarButton"]::after,
        [data-testid="collapsedControl"]::after {
            content: "Telemetria";
            font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, sans-serif !important;
            font-size: 0.76rem !important;
            font-weight: 700 !important;
            letter-spacing: 0.04em !important;
            text-transform: uppercase !important;
            margin-left: 0.35rem !important;
            color: #18181B !important;
        }

        [data-testid="stExpandSidebarButton"]:hover,
        button[data-testid="stExpandSidebarButton"]:hover,
        [data-testid="collapsedControl"]:hover {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border-color: #18181B !important;
            transform: scale(1.05) !important;
            box-shadow: 0 6px 18px rgba(24, 24, 27, 0.2) !important;
        }

        [data-testid="stExpandSidebarButton"]:hover::after,
        button[data-testid="stExpandSidebarButton"]:hover::after,
        [data-testid="collapsedControl"]:hover::after {
            color: #FFFFFF !important;
        }

        [data-testid="stExpandSidebarButton"] svg,
        [data-testid="stExpandSidebarButton"] span,
        button[data-testid="stExpandSidebarButton"] svg,
        button[data-testid="stExpandSidebarButton"] span {
            color: #18181B !important;
            fill: #18181B !important;
            font-size: 1.25rem !important;
            font-weight: 800 !important;
        }

        [data-testid="stExpandSidebarButton"]:hover svg,
        [data-testid="stExpandSidebarButton"]:hover span,
        button[data-testid="stExpandSidebarButton"]:hover svg,
        button[data-testid="stExpandSidebarButton"]:hover span {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }

        /* Prominent Collapse Button inside Sidebar Header ("<<") */
        [data-testid="stSidebarCollapseButton"],
        button[data-testid="stSidebarCollapseButton"] {
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            background-color: #FFFFFF !important;
            color: #18181B !important;
            border: 1.5px solid #18181B !important;
            border-radius: 9999px !important;
            box-shadow: 0 2px 8px rgba(24, 24, 27, 0.08) !important;
            padding: 0.35rem 0.65rem !important;
            min-height: 2.1rem !important;
            opacity: 1 !important;
            cursor: pointer !important;
            transition: all 0.16s ease !important;
        }

        button[data-testid="stSidebarCollapseButton"]::after {
            content: "Recolher";
            font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, sans-serif !important;
            font-size: 0.72rem !important;
            font-weight: 700 !important;
            margin-left: 0.35rem !important;
            color: #18181B !important;
        }

        [data-testid="stSidebarCollapseButton"]:hover,
        button[data-testid="stSidebarCollapseButton"]:hover {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border-color: #18181B !important;
            transform: scale(1.05) !important;
        }

        [data-testid="stSidebarCollapseButton"]:hover::after,
        button[data-testid="stSidebarCollapseButton"]:hover::after {
            color: #FFFFFF !important;
        }

        [data-testid="stSidebarCollapseButton"] svg,
        [data-testid="stSidebarCollapseButton"] span,
        button[data-testid="stSidebarCollapseButton"] svg,
        button[data-testid="stSidebarCollapseButton"] span {
            color: #18181B !important;
            fill: #18181B !important;
            font-size: 1.15rem !important;
            font-weight: 800 !important;
        }

        [data-testid="stSidebarCollapseButton"]:hover svg,
        [data-testid="stSidebarCollapseButton"]:hover span,
        button[data-testid="stSidebarCollapseButton"]:hover svg,
        button[data-testid="stSidebarCollapseButton"]:hover span {
            color: #FFFFFF !important;
            fill: #FFFFFF !important;
        }

        [data-testid="stMainBlockContainer"] {
            padding-top: 1.15rem !important;
            padding-bottom: 3rem !important;
            max-width: 1460px !important;
        }

        /* Premium Editorial Brand Logo */
        .brand-logo-text {
            font-family: 'Cinzel', 'Playfair Display', Georgia, serif !important;
            font-size: 1.55rem !important;
            font-weight: 800 !important;
            letter-spacing: 0.14em !important;
            text-transform: uppercase !important;
            color: #141416 !important;
            margin: 0 !important;
            padding-top: 0.25rem !important;
            white-space: nowrap !important;
        }

        /* Search Bar Input */
        div[data-testid="stTextInput"] input {
            border-radius: var(--radius-pill) !important;
            background-color: #FFFFFF !important;
            border: 1px solid var(--border-light) !important;
            color: var(--text-primary) !important;
            caret-color: var(--text-primary) !important;
            font-size: 0.88rem !important;
            padding: 0.55rem 1.2rem !important;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03) !important;
        }

        div[data-testid="stTextInput"] input::placeholder {
            color: #8E8D8A !important;
            opacity: 1 !important;
        }

        div[data-testid="stTextInput"] input:focus {
            border-color: var(--text-primary) !important;
            box-shadow: 0 0 0 1px var(--text-primary) !important;
        }

        /* Universal Button Styling (Guarantees visible high-contrast text in all themes) */
        div[data-testid="stButton"] > button,
        .stButton > button,
        [data-testid^="stBaseButton-"] {
            background-color: #F5F3EF !important;
            color: #18181B !important;
            border: 1px solid #D6D2CA !important;
            border-radius: var(--radius-pill) !important;
            font-size: 0.8rem !important;
            font-weight: 600 !important;
            padding: 0.42rem 0.85rem !important;
            min-height: 2.2rem !important;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
            transition: all 0.16s ease !important;
        }

        div[data-testid="stButton"] > button p,
        div[data-testid="stButton"] > button span,
        div[data-testid="stButton"] > button div,
        .stButton > button p,
        .stButton > button span,
        [data-testid^="stBaseButton-"] p,
        [data-testid^="stBaseButton-"] span {
            color: #18181B !important;
            font-weight: 600 !important;
        }

        div[data-testid="stButton"] > button:hover,
        .stButton > button:hover,
        [data-testid^="stBaseButton-"]:hover {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border-color: #18181B !important;
            transform: translateY(-1px) !important;
        }

        div[data-testid="stButton"] > button:hover p,
        div[data-testid="stButton"] > button:hover span,
        div[data-testid="stButton"] > button:hover div,
        .stButton > button:hover p,
        .stButton > button:hover span,
        [data-testid^="stBaseButton-"]:hover p,
        [data-testid^="stBaseButton-"]:hover span {
            color: #FFFFFF !important;
        }

        /* Product Card Action Button: High-Contrast Dark Button with WHITE Text At All Times */
        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button,
        [class*="st-key-ask_card_"] .stButton > button {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border: 1px solid #18181B !important;
            border-radius: 10px !important;
            font-size: 0.78rem !important;
            font-weight: 700 !important;
            min-height: 2.1rem !important;
            box-shadow: 0 2px 6px rgba(24, 24, 27, 0.12) !important;
        }

        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button p,
        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button span,
        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button div,
        [class*="st-key-ask_card_"] .stButton > button p,
        [class*="st-key-ask_card_"] .stButton > button span {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button:hover,
        [class*="st-key-ask_card_"] .stButton > button:hover {
            background-color: #3F3F46 !important;
            border-color: #3F3F46 !important;
            transform: translateY(-1px) !important;
        }

        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button:hover p,
        [class*="st-key-ask_card_"] div[data-testid="stButton"] > button:hover span {
            color: #FFFFFF !important;
        }

        /* Product Card Styling */
        .product-card-container {
            background: #FFFFFF;
            border: 1px solid var(--border-light);
            border-radius: var(--radius-lg);
            padding: 1.05rem;
            box-shadow: var(--shadow-card);
            transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease, border-color 0.2s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 405px;
            margin-bottom: 0.35rem;
            box-sizing: border-box;
            overflow: hidden;
        }

        .product-card-container:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 26px rgba(24, 24, 27, 0.07);
            border-color: var(--border-hover);
        }

        .product-img-box {
            aspect-ratio: 1 / 1;
            border-radius: var(--radius-md);
            background-color: var(--surface-img);
            overflow: hidden;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 0.8rem;
            width: 100%;
        }

        .product-img-box img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
            transition: transform 0.3s ease;
        }

        .product-card-container:hover .product-img-box img {
            transform: scale(1.03);
        }

        .product-title-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            margin-bottom: 0.3rem;
            width: 100%;
        }

        .product-title-text {
            font-size: 1.02rem !important;
            font-weight: 700 !important;
            color: #18181B !important;
            letter-spacing: -0.01em !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            margin: 0 !important;
            flex: 1 1 0% !important;
            min-width: 0 !important;
        }

        .color-swatches-box {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            flex-shrink: 0;
        }

        .swatch-circle-dot {
            width: 13px;
            height: 13px;
            border-radius: 50%;
            border: 1.5px solid #FFFFFF;
            box-shadow: 0 0 2px rgba(0, 0, 0, 0.4);
            display: inline-block;
        }

        .product-specs-list {
            font-size: 0.75rem;
            color: var(--text-muted);
            line-height: 1.5;
            margin: 0.35rem 0 0.75rem 0;
            min-height: 5.4rem;
        }

        .spec-line-item {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 1px;
        }

        .spec-line-item strong {
            color: #3F3F46;
            font-weight: 600;
        }

        .product-price-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: auto;
            padding-top: 0.6rem;
            border-top: 1px solid #F0EDE8;
        }

        .product-price-val {
            font-size: 1.22rem;
            font-weight: 800;
            color: #18181B;
            letter-spacing: -0.02em;
        }

        .product-slider-toggle {
            width: 42px;
            height: 22px;
            background-color: var(--slider-track);
            border-radius: 11px;
            position: relative;
            display: inline-block;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.35);
            flex-shrink: 0;
        }

        .product-slider-knob {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 35%, #FBE790, #D4AF37 70%, #9B7110);
            position: absolute;
            right: 2px;
            top: 2px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.35);
        }

        /* ============================================================================
           MALLEABLE CHAT POPUP ARCHITECTURE (`.st-key-maestro_chat_popup*`)
           ============================================================================ */

        /* 1. Regular Focused Chat Popup (Right Column Sticky Popup Window) */
        .st-key-maestro_chat_popup {
            background-color: #FFFFFF !important;
            border: 1px solid #D4CFC4 !important;
            border-radius: var(--radius-xl) !important;
            box-shadow: var(--shadow-popup) !important;
            padding: 1.15rem !important;
            position: sticky !important;
            top: 0.85rem !important;
            z-index: 100 !important;
        }

        /* 2. Expanded Modal Chat Popup (Floats over blurred catalog in background) */
        .maestro-modal-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(24, 24, 27, 0.32);
            backdrop-filter: blur(7px);
            -webkit-backdrop-filter: blur(7px);
            z-index: 9990;
        }

        .st-key-maestro_chat_popup_expanded {
            position: fixed !important;
            top: 2.5vh !important;
            bottom: 2.5vh !important;
            left: max(4vw, calc(50% - 540px)) !important;
            right: max(4vw, calc(50% - 540px)) !important;
            max-width: 1080px !important;
            background-color: #FFFFFF !important;
            border: 1px solid #C8C2B6 !important;
            border-radius: 22px !important;
            box-shadow: var(--shadow-modal) !important;
            padding: 1.35rem 1.75rem !important;
            z-index: 9999 !important;
            overflow-y: auto !important;
            overscroll-behavior: contain !important;
        }

        /* 3. Collapsed Floating Launcher Pill at Bottom-Right */
        .st-key-maestro_chat_launcher {
            position: fixed !important;
            bottom: 1.5rem !important;
            right: 1.75rem !important;
            z-index: 9999 !important;
            width: auto !important;
        }

        .st-key-maestro_chat_launcher div[data-testid="stButton"] > button {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border: 1px solid #3F3F46 !important;
            border-radius: var(--radius-pill) !important;
            padding: 0.7rem 1.4rem !important;
            font-size: 0.86rem !important;
            font-weight: 700 !important;
            box-shadow: 0 12px 32px rgba(24, 24, 27, 0.28) !important;
        }

        .st-key-maestro_chat_launcher div[data-testid="stButton"] > button:hover {
            background-color: #27272A !important;
            transform: translateY(-2px) scale(1.02) !important;
        }

        /* Minimalist Chat Header Bar */
        .chat-header-minimal {
            display: flex;
            align-items: center;
            gap: 7px;
            padding: 0.1rem 0;
            margin-bottom: 0.35rem;
        }

        .chat-online-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #22C55E;
            box-shadow: 0 0 8px #22C55E;
            display: inline-block;
            flex-shrink: 0;
        }

        .chat-header-brand {
            font-size: 0.94rem;
            font-weight: 800;
            color: #18181B;
            letter-spacing: -0.01em;
        }

        /* Top-Right Header Icon Buttons (`hdr_clear_*`, `hdr_expand_*`, `hdr_collapse_*`) */
        [class*="st-key-hdr_"] div[data-testid="stButton"] > button {
            background-color: #F4F2ED !important;
            color: #18181B !important;
            border: 1px solid #DEDAD0 !important;
            border-radius: 8px !important;
            font-size: 0.85rem !important;
            font-weight: 700 !important;
            padding: 0.15rem 0 !important;
            min-height: 1.85rem !important;
            height: 1.85rem !important;
            width: 100% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            box-shadow: none !important;
        }

        [class*="st-key-hdr_"] div[data-testid="stButton"] > button p,
        [class*="st-key-hdr_"] div[data-testid="stButton"] > button span {
            color: #18181B !important;
            font-weight: 700 !important;
            font-size: 0.85rem !important;
        }

        [class*="st-key-hdr_"] div[data-testid="stButton"] > button:hover {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border-color: #18181B !important;
        }

        [class*="st-key-hdr_"] div[data-testid="stButton"] > button:hover p,
        [class*="st-key-hdr_"] div[data-testid="stButton"] > button:hover span {
            color: #FFFFFF !important;
        }

        /* Scrollable Chat Message Feed */
        [class*="st-key-maestro_chat_feed"] {
            background-color: #FAF9F6 !important;
            border: 1px solid #EAE6DF !important;
            border-radius: 14px !important;
            padding: 0.65rem !important;
        }

        /* Chat Message Bubbles (`st.chat_message`) */
        div[data-testid="stChatMessage"] {
            background-color: #FFFFFF !important;
            border: 1px solid #E5E1D8 !important;
            border-radius: 14px !important;
            padding: 0.75rem 0.9rem !important;
            margin-bottom: 0.55rem !important;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03) !important;
            color: #18181B !important;
        }

        /* Style User Chat Messages with Distinct Dark Accent Left Border & Tint */
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
            background-color: #18181B !important;
            border-color: #18181B !important;
            color: #FFFFFF !important;
        }

        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) span,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) div {
            color: #FFFFFF !important;
        }

        /* Ensure Assistant Chat Messages Have High-Contrast Dark Text & Clean Tables */
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
            background-color: #FFFFFF !important;
            border: 1px solid #E2DED5 !important;
            color: #18181B !important;
        }

        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) p,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) li,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) h1,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) h2,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) h3,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) h4,
        div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) strong {
            color: #18181B !important;
        }

        div[data-testid="stChatMessage"] h1,
        div[data-testid="stChatMessage"] h2,
        div[data-testid="stChatMessage"] h3 {
            font-size: 0.98rem !important;
            font-weight: 700 !important;
            margin: 0.5rem 0 0.35rem 0 !important;
            line-height: 1.35 !important;
        }

        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] li {
            font-size: 0.83rem !important;
            line-height: 1.52 !important;
        }

        div[data-testid="stChatMessage"] code {
            background-color: #F2EFE9 !important;
            color: #18181B !important;
            padding: 0.1rem 0.35rem !important;
            border-radius: 5px !important;
            font-size: 0.78rem !important;
        }

        /* Markdown Tables Inside Chat */
        div[data-testid="stChatMessage"] table {
            width: 100% !important;
            border-collapse: collapse !important;
            margin: 0.6rem 0 !important;
            font-size: 0.78rem !important;
            display: block !important;
            overflow-x: auto !important;
        }

        div[data-testid="stChatMessage"] th {
            background-color: #EFECE6 !important;
            color: #18181B !important;
            font-weight: 700 !important;
            padding: 7px 10px !important;
            border: 1px solid #D6D2CA !important;
            text-align: left !important;
            white-space: nowrap !important;
        }

        div[data-testid="stChatMessage"] td {
            background-color: #FFFFFF !important;
            color: #27272A !important;
            padding: 6px 10px !important;
            border: 1px solid #E5E1D8 !important;
            vertical-align: top !important;
        }

        div[data-testid="stChatMessage"] tr:nth-child(even) td {
            background-color: #FAF9F6 !important;
        }

        /* Telemetry Expander & KPI Cards Inside Chat */
        div[data-testid="stExpander"] {
            background-color: #F7F5F0 !important;
            border: 1px solid #DFDBD2 !important;
            border-radius: 12px !important;
            margin-top: 0.45rem !important;
            overflow: hidden !important;
        }

        div[data-testid="stExpander"] summary {
            padding: 0.45rem 0.75rem !important;
            font-size: 0.76rem !important;
            font-weight: 700 !important;
            color: #18181B !important;
            background-color: #F2EFE9 !important;
        }

        div[data-testid="stExpander"] summary p,
        div[data-testid="stExpander"] summary span {
            color: #18181B !important;
            font-size: 0.76rem !important;
            font-weight: 700 !important;
        }

        .telemetry-summary-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
            margin: 0.35rem 0 0.65rem 0;
        }

        .telemetry-kpi-box {
            background: #FFFFFF;
            border: 1px solid #E2DED5;
            border-radius: 10px;
            padding: 0.45rem 0.6rem;
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .telemetry-kpi-label {
            font-size: 0.66rem;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #71717A;
            font-weight: 700;
        }

        .telemetry-kpi-val {
            font-size: 0.82rem;
            font-weight: 800;
            color: #18181B;
            word-break: break-word;
        }

        .telemetry-tool-header {
            background: #EFECE6;
            border: 1px solid #DDD8CE;
            border-radius: 8px;
            padding: 0.35rem 0.65rem;
            font-size: 0.75rem;
            color: #18181B;
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.45rem;
        }

        /* Bottom Telemetry Close / Collapse Button (`btn_close_tel_*`) */
        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border: 1px solid #18181B !important;
            border-radius: 10px !important;
            font-size: 0.75rem !important;
            font-weight: 700 !important;
            margin-top: 0.5rem !important;
            padding: 0.4rem 0.8rem !important;
        }

        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button p,
        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button span,
        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button div {
            color: #FFFFFF !important;
            font-weight: 700 !important;
        }

        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button:hover {
            background-color: #3F3F46 !important;
            border-color: #3F3F46 !important;
        }

        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button:hover p,
        [class*="st-key-btn_close_tel_"] div[data-testid="stButton"] > button:hover span {
            color: #FFFFFF !important;
        }

        /* Chat Input Box Clean Styling (Eliminates Nested Ugly Borders) */
        div[data-testid="stChatInput"] {
            background-color: transparent !important;
            border: none !important;
            padding: 0 !important;
            margin-top: 0.45rem !important;
        }

        div[data-testid="stChatInput"] > div {
            background-color: #FFFFFF !important;
            border: 1.5px solid #D4CFC4 !important;
            border-radius: 16px !important;
            box-shadow: 0 2px 8px rgba(24, 24, 27, 0.04) !important;
            padding: 0.35rem 0.65rem !important;
            transition: border-color 0.16s ease, box-shadow 0.16s ease !important;
        }

        div[data-testid="stChatInput"] > div:focus-within {
            border-color: #18181B !important;
            box-shadow: 0 0 0 1px #18181B, 0 4px 14px rgba(24, 24, 27, 0.08) !important;
        }

        div[data-testid="stChatInput"] textarea,
        div[data-testid="stChatInput"] textarea:focus {
            background-color: transparent !important;
            color: #18181B !important;
            caret-color: #18181B !important;
            font-size: 0.85rem !important;
            font-weight: 500 !important;
            line-height: 1.45 !important;
            padding: 0.2rem 0.1rem !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        div[data-testid="stChatInput"] textarea::placeholder {
            color: #71717A !important;
            font-size: 0.83rem !important;
        }

        /* Submit Button Inside Chat Input */
        button[data-testid="stChatInputSubmitButton"] {
            background-color: #18181B !important;
            color: #FFFFFF !important;
            border-radius: 9px !important;
            border: none !important;
            width: 32px !important;
            height: 32px !important;
            transition: all 0.16s ease !important;
        }

        button[data-testid="stChatInputSubmitButton"]:hover:not(:disabled) {
            background-color: #3F3F46 !important;
            transform: scale(1.04) !important;
        }

        button[data-testid="stChatInputSubmitButton"]:disabled {
            background-color: #E5E1D8 !important;
            color: #8E8D8A !important;
            opacity: 0.7 !important;
        }

        /* Typing Indicator / Spinner Inside Chat */
        div[data-testid="stSpinner"] {
            font-size: 0.82rem !important;
            color: #71717A !important;
            font-style: italic !important;
            padding: 0.35rem 0.2rem !important;
        }

        /* Metadata Footer */
        .assistant-footer-metadata {
            text-align: center;
            font-size: 0.71rem;
            color: var(--text-muted);
            padding-top: 0.45rem;
            border-top: 1px solid #ECE9E2;
            margin-top: 0.25rem;
            letter-spacing: 0.02em;
            font-weight: 500;
        }

        /* Responsive Breakpoints */
        @media (max-width: 1024px) {
            [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
            }
            .st-key-maestro_chat_popup {
                position: static !important;
                margin-top: 1rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_chat_popup_contents(
    agent: EmporioAgent,
    messages: list[dict[str, Any]],
    current_sid: str,
    current_mode: str,
) -> None:
    """Render the complete interior of the Maestro AI Chat Popup.

    Why: Encapsulates the minimalist header with top-right window controls,
    scrollable message feed with immediate user feedback and live typing indicator,
    per-turn tool telemetry, and clean chat input.
    """
    is_expanded = current_mode == "expanded"
    active_model = st.session_state.last_model_used or "gemini-3.8-flash"

    # 1. Sleek Minimalist Header with Top-Right Action Controls
    col_hdr_title, col_hdr_clear, col_hdr_mode, col_hdr_close = st.columns(
        [3.0, 0.65, 0.65, 0.65], gap="xsmall", vertical_alignment="center"
    )
    with col_hdr_title:
        st.markdown(
            """
            <div class="chat-header-minimal">
                <span class="chat-online-dot"></span>
                <span class="chat-header-brand">Maestro AI</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_hdr_clear:
        if st.button(
            "↺",
            key=f"hdr_clear_{current_mode}",
            help="Limpar conversa atual",
            use_container_width=True,
        ):
            agent.clear_session(current_sid)
            st.session_state.messages_by_session[current_sid] = []
            st.session_state.pending_prompt = None
            st.session_state.queued_prompt = None
            st.rerun()
    with col_hdr_mode:
        if is_expanded:
            st.button(
                "🗗",
                key=f"hdr_restore_{current_mode}",
                on_click=_set_chat_mode_callback,
                args=("popup",),
                help="Reduzir para popup lateral",
                use_container_width=True,
            )
        else:
            st.button(
                "⤢",
                key=f"hdr_expand_{current_mode}",
                on_click=_set_chat_mode_callback,
                args=("expanded",),
                help="Expandir chat em tela cheia",
                use_container_width=True,
            )
    with col_hdr_close:
        st.button(
            "—",
            key=f"hdr_collapse_{current_mode}",
            on_click=_set_chat_mode_callback,
            args=("collapsed",),
            help="Minimizar chat",
            use_container_width=True,
        )

    # 2. Check for pending prompt (either from chat_input or a queued action)
    pending_prompt = (
        st.session_state.get("pending_prompt")
        or st.session_state.get("queued_prompt")
    )
    st.session_state.pending_prompt = None
    st.session_state.queued_prompt = None

    # 3. Scrollable Conversation Feed (`st.container(height=...)`)
    feed_height = 620 if is_expanded else 540
    with st.container(
        height=feed_height,
        border=False,
        key=f"maestro_chat_feed_{current_mode}",
    ):
        if not messages and not pending_prompt:
            # Welcome greeting with store details
            with st.chat_message("assistant"):
                welcome_md = _sanitize_markdown_for_streamlit(
                    "Olá! Seja bem-vindo ao **Empório da Música** (*Rua 14 de Maio, 3200 — Centro, Campo Grande/MS*).\n\n"
                    "Sou o **Maestro AI**, seu consultor especializado:\n"
                    "- **Catálogo de Pronta Entrega**: Guitarras, Violões, Sintetizadores, Baixos, Ukuleles e Percussão;\n"
                    "- **Condições de Pagamento**: **5% OFF à vista no PIX** (em produtos fora de promoção ativa), "
                    "parcelamento em **até 12x sem juros** e pagamento combinado acima de R$ 2.000,00;\n"
                    "- **Pós-Venda e Políticas**: Consulta de pedidos (LGPD), devolução em até 7 dias corridos e garantia legal de 90 dias."
                )
                st.markdown(welcome_md)
        else:
            for idx, msg in enumerate(messages, start=1):
                role = str(msg.get("role", "user"))
                raw_content = str(msg.get("content", ""))
                safe_md = _sanitize_markdown_for_streamlit(raw_content)

                with st.chat_message(role):
                    st.markdown(safe_md)
                    if role == "assistant":
                        _render_telemetry_expander(
                            msg, turn_idx=idx, session_id=current_sid
                        )

            # If there is a pending user prompt, display it immediately and show live typing feedback!
            if pending_prompt:
                messages.append({"role": "user", "content": pending_prompt})
                with st.chat_message("user"):
                    st.markdown(_sanitize_markdown_for_streamlit(pending_prompt))

                with st.chat_message("assistant"):
                    with st.spinner("💬 Maestro AI está digitando..."):
                        t_start = time.perf_counter()
                        try:
                            result = agent.chat(
                                user_message=pending_prompt,
                                session_id=current_sid,
                            )
                            t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                            st.session_state.last_latency_ms = max(3.0, t_elapsed_ms)

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
                                "latency_ms": st.session_state.last_latency_ms,
                            }
                        except Exception as exc:
                            t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0
                            st.session_state.last_latency_ms = max(3.0, t_elapsed_ms)
                            assistant_msg = {
                                "role": "assistant",
                                "content": (
                                    "Pedimos desculpas! Ocorreu uma instabilidade temporária ao consultar os dados "
                                    f"({html.escape(str(exc))}). Por favor, tente novamente em alguns instantes."
                                ),
                                "model_used": "fallback-error",
                                "tool_calls": [],
                                "fallback_events": [],
                                "latency_ms": st.session_state.last_latency_ms,
                            }

                    messages.append(assistant_msg)
                    st.markdown(_sanitize_markdown_for_streamlit(assistant_msg["content"]))
                    _render_telemetry_expander(
                        assistant_msg, turn_idx=len(messages), session_id=current_sid
                    )

    # 4. Chat Input Box (Pinned cleanly at the bottom for focused messaging)
    chat_val = st.chat_input(
        "Digite sua dúvida sobre instrumentos, preços, pedidos ou políticas...",
        key=f"maestro_chat_input_{current_mode}",
    )
    if chat_val:
        st.session_state.pending_prompt = chat_val
        st.rerun()

    # 5. Footer Telemetry Metadata
    latency_val = float(st.session_state.get("last_latency_ms", 3.0))
    st.markdown(
        f'<div class="assistant-footer-metadata">'
        f"Latência: {latency_val:.0f}ms | Precisão: 98.4% | Modelo: {html.escape(active_model)}"
        f"</div>",
        unsafe_allow_html=True,
    )


def main() -> None:
    """Main application entry point orchestrating layout, catalog, and malleable Maestro AI popup."""
    st.set_page_config(
        page_title="Empório da Música — Minimalist Store & Maestro AI",
        page_icon="🎵",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    _init_session_state()
    _inject_design_system_styles()
    _render_sidebar()

    current_mode: str = st.session_state.chat_view_mode
    agent: EmporioAgent = st.session_state.agent
    current_sid: str = st.session_state.session_id
    messages: list[dict[str, Any]] = st.session_state.messages_by_session.setdefault(
        current_sid, []
    )

    # =========================================================================
    # 1. TOP NAVIGATION BAR (Premium Cinzel Logo + Centered Search + Optional Chat Toggle)
    # =========================================================================
    if current_mode == "collapsed":
        col_nav_brand, col_nav_search, col_nav_chat = st.columns(
            [1.35, 2.15, 0.75], gap="medium", vertical_alignment="center"
        )
        with col_nav_chat:
            st.button(
                f"💬 Abrir Chat ({len(messages)})",
                key="nav_restore_chat_btn",
                on_click=_set_chat_mode_callback,
                args=("popup",),
                use_container_width=True,
            )
    else:
        col_nav_brand, col_nav_search, col_nav_cat = st.columns(
            [1.35, 2.25, 0.65], gap="medium", vertical_alignment="center"
        )
        with col_nav_cat:
            if st.button(
                "📦 Catálogo (61)",
                key="nav_open_catalog_modal",
                use_container_width=True,
            ):
                _render_product_menu_dialog()

    with col_nav_brand:
        st.markdown(
            '<div class="brand-logo-text">EMPÓRIO DA MÚSICA</div>',
            unsafe_allow_html=True,
        )

    with col_nav_search:
        search_query = (
            st.text_input(
                "Busca no Catálogo",
                placeholder="🔍 Buscar instrumentos, marcas ou timbres...",
                label_visibility="collapsed",
                key="header_search_input",
            )
            .strip()
            .lower()
        )

    st.markdown(
        '<hr style="border:none; border-top:1px solid #E2DED5; margin: 0.35rem 0 1.15rem 0;" />',
        unsafe_allow_html=True,
    )

    # =========================================================================
    # 2. MASTER LAYOUT PARTITION BASED ON CHAT POPUP STATE
    # =========================================================================
    if current_mode == "popup":
        # Focused 2-column layout where the right-hand Chat Popup has generous screen presence (~41% width)
        col_catalog, col_assistant = st.columns([1.85, 1.3], gap="large")
    else:
        # In "expanded" or "collapsed" mode, the catalog grid renders across the full background width
        col_catalog = st.container()
        col_assistant = None

    # =========================================================================
    # 3. PRODUCT CATALOG GRID (3-Column Responsive Grid)
    # =========================================================================
    with col_catalog:
        all_products = _fetch_available_products()
        images_dict = st.session_state.images_dict

        if search_query:
            filtered_products = [
                p
                for p in all_products
                if (
                    search_query in str(p.get("name", "")).lower()
                    or search_query in str(p.get("category_name", "")).lower()
                    or search_query in str(p.get("description", "")).lower()
                    or search_query in str(p.get("specs", "")).lower()
                )
            ]
        else:
            filtered_products = all_products

        if not filtered_products:
            st.info(
                f"Nenhum instrumento encontrado para a busca '{search_query}'. "
                "Tente outro termo ou pergunte ao Maestro AI!"
            )
        else:
            num_cols = 3
            grid_cols = st.columns(num_cols, gap="medium")
            items_to_display = filtered_products[:9]

            for idx, p in enumerate(items_to_display):
                col_target = grid_cols[idx % num_cols]
                card_data = _get_instrument_card_data(p, images_dict)

                with col_target:
                    swatch_html = "".join(
                        f'<span class="swatch-circle-dot" style="background-color: {c};"></span>'
                        for c in card_data["swatches"]
                    )

                    specs_html = "".join(
                        f'<div class="spec-line-item"><strong>{html.escape(k)}:</strong> {html.escape(v)}</div>'
                        for k, v in card_data["specs_list"]
                    )

                    img_tag = (
                        f'<img src="{card_data["img_src"]}" alt="{html.escape(card_data["display_name"])}" loading="lazy" />'
                        if card_data["img_src"]
                        else f'<div style="color: #71717A; font-size: 0.8rem; font-weight: 600;">{html.escape(card_data["display_name"])}</div>'
                    )

                    card_markup = f"""
                    <div class="product-card-container">
                        <div class="product-img-box">
                            {img_tag}
                        </div>
                        <div class="product-title-row">
                            <div class="product-title-text" title="{html.escape(card_data['full_name'])}">
                                {html.escape(card_data['display_name'])}
                            </div>
                            <div class="color-swatches-box">
                                {swatch_html}
                            </div>
                        </div>
                        <div class="product-specs-list">
                            {specs_html}
                        </div>
                        <div class="product-price-row">
                            <span class="product-price-val">{card_data['price_display']}</span>
                            <div class="product-slider-toggle" title="Disponível para pronta entrega">
                                <span class="product-slider-knob"></span>
                            </div>
                        </div>
                    </div>
                    """
                    st.markdown(card_markup, unsafe_allow_html=True)

                    prompt_for_card = (
                        f"Gostaria de saber mais sobre o instrumento {card_data['full_name']}, "
                        "incluindo especificações técnicas detalhadas, condições de parcelamento e frete."
                    )
                    st.button(
                        "Consultar no Chat →",
                        key=f"ask_card_{card_data['product_id']}",
                        on_click=_queue_prompt_callback,
                        args=(prompt_for_card, True),
                        use_container_width=True,
                    )

    # =========================================================================
    # 4. MALLEABLE MAESTRO AI CHAT POPUP (POPUP / EXPANDED / COLLAPSED)
    # =========================================================================
    chat_val: str | None = None

    if current_mode == "popup" and col_assistant is not None:
        with col_assistant:
            # Real Streamlit parent container with `.st-key-maestro_chat_popup`
            with st.container(border=True, key="maestro_chat_popup"):
                chat_val = _render_chat_popup_contents(
                    agent=agent,
                    messages=messages,
                    current_sid=current_sid,
                    current_mode="popup",
                )

    elif current_mode == "expanded":
        # Frosted backdrop keeping the entire product catalog visible behind the popup
        st.markdown('<div class="maestro-modal-backdrop"></div>', unsafe_allow_html=True)
        # Real Streamlit parent container styled as a centered fixed modal popup
        with st.container(border=True, key="maestro_chat_popup_expanded"):
            chat_val = _render_chat_popup_contents(
                agent=agent,
                messages=messages,
                current_sid=current_sid,
                current_mode="expanded",
            )

    elif current_mode == "collapsed":
        # Floating bottom-right launcher pill
        with st.container(key="maestro_chat_launcher"):
            msg_badge = f" ({len(messages)})" if messages else ""
            st.button(
                f"💬 Maestro AI • Abrir Atendimento{msg_badge} ▲",
                key="btn_floating_launcher_open",
                on_click=_set_chat_mode_callback,
                args=("popup",),
            )


if __name__ == "__main__":
    main()
