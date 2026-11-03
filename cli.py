"""Rich interactive terminal interface for the Empório da Música Support Agent.

Why: Enables developers and evaluators to converse with `EmporioAgent` directly in
the terminal with clean Markdown rendering, tool-execution telemetry panels, active
Gemini model status indicators, and slash commands (`/new`, `/models`, `/exit`).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.agent import EmporioAgent
from src.config import GEMINI_API_KEY

console = Console()


def _render_banner(session_id: str) -> None:
    """Display the branded Empório da Música welcome banner and CLI commands."""
    banner_md = (
        "# Empório da Música — Atendimento ao Cliente (Campo Grande, MS)\n"
        "Rua 14 de Maio, 3200 — Centro, Campo Grande, MS\n\n"
        f"**Sessão Ativa:** `{session_id}`\n\n"
        "**Comandos disponíveis:**\n"
        "- `/new`    — Inicia uma nova conversa (reinicia a sessão SQLite)\n"
        "- `/models` — Exibe o status da cascata de modelos Gemini (cooldowns e disponibilidade)\n"
        "- `/exit`   — Encerra o atendimento no terminal"
    )
    console.print(
        Panel(
            Markdown(banner_md),
            border_style="bright_cyan",
            title="[bold cyan]Empório da Música CLI[/bold cyan]",
            subtitle="[dim]ReAct Agent + SQLite + Multi-Model Fallback[/dim]",
        )
    )


def _render_models_table(agent: EmporioAgent, last_model: str | None = None) -> None:
    """Render a Rich table displaying the health and cooldown state of the Gemini model cascade."""
    table = Table(
        title="Status da Cascata de Modelos Gemini (Fallback Router)",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Prioridade", justify="center", style="cyan")
    table.add_column("Modelo Gemini", style="bold white")
    table.add_column("Status", justify="center")
    table.add_column("Cooldown Restante", justify="right")
    table.add_column("Último Turno", justify="center")

    for item in agent.router.get_health_status():
        state = item["state"]
        if state == "ready":
            status_badge = "[bold green][PRONTO][/bold green]"
        elif state == "cooldown":
            status_badge = "[bold yellow][COOLDOWN][/bold yellow]"
        elif state == "unconfigured":
            status_badge = "[dim][OPCIONAL][/dim]"
        else:
            status_badge = "[bold red][DESATIVADO][/bold red]"

        cooldown_str = (
            f"{item['cooldown_remaining_s']:.1f}s"
            if item["cooldown_remaining_s"] > 0
            else "—"
        )
        active_marker = "[bold green][ATIVO][/bold green]" if item["model"] == last_model else ""

        table.add_row(
            f"#{item['priority']}",
            str(item["model"]),
            status_badge,
            cooldown_str,
            active_marker,
        )

    console.print(table)


def _render_turn_telemetry(result: dict[str, Any]) -> None:
    """Render Rich panels for executed tool calls and fallback events before the final response."""
    tool_calls: list[dict[str, Any]] = result.get("tool_calls") or []
    fallback_events: list[dict[str, Any]] = result.get("fallback_events") or []

    if fallback_events:
        fb_lines = []
        for fb in fallback_events:
            fb_lines.append(
                f"• Modelo [bold yellow]{fb.get('model')}[/bold yellow] "
                f"(HTTP {fb.get('status_code')}: {fb.get('reason')}) -> "
                f"[cyan]{fb.get('action')}[/cyan]"
            )
        console.print(
            Panel(
                "\n".join(fb_lines),
                title="[bold yellow]Rotação Automática de Modelo (Fallback)[/bold yellow]",
                border_style="yellow",
            )
        )

    if tool_calls:
        tc_lines = []
        for idx, tc in enumerate(tool_calls, start=1):
            args_str = json.dumps(tc.get("args", {}), ensure_ascii=False)
            tc_lines.append(
                f"[bold green]{idx}. {tc.get('name')}({args_str})[/bold green] "
                f"[dim](solicitado por {tc.get('model_requested', 'gemini')})[/dim]"
            )
        console.print(
            Panel(
                "\n".join(tc_lines),
                title=f"[bold green]Ferramentas Executadas ({len(tool_calls)})[/bold green]",
                border_style="green",
            )
        )


def run_cli(initial_session_id: str = "cli-default") -> None:
    """Run the interactive Rich terminal loop for the Empório da Música agent."""
    if not GEMINI_API_KEY:
        console.print(
            "[bold yellow]Aviso:[/bold yellow] `GEMINI_API_KEY` não detectada no `.env`."
        )

    agent = EmporioAgent()
    session_id = initial_session_id
    last_model_used: str | None = None

    _render_banner(session_id)

    while True:
        try:
            user_input = console.input("\n[bold bright_blue]Você > [/bold bright_blue]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold cyan]Atendimento encerrado. Até logo![/bold cyan]")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("/exit", "/quit", "sair"):
            console.print("[bold cyan]Obrigado por consultar a Empório da Música. Até logo![/bold cyan]")
            break

        if cmd == "/new":
            agent.clear_session(session_id)
            session_id = f"cli-{uuid.uuid4().hex[:6]}"
            console.print(
                Panel(
                    f"Sessão reiniciada com sucesso. Novo `session_id`: [bold cyan]{session_id}[/bold cyan]",
                    title="[bold cyan]Nova Conversa[/bold cyan]",
                    border_style="cyan",
                )
            )
            continue

        if cmd == "/models":
            _render_models_table(agent, last_model=last_model_used)
            continue

        with console.status(
            "[bold cyan]Consultando catálogo e políticas da loja...[/bold cyan]",
            spinner="dots",
        ):
            try:
                result = agent.chat(user_message=user_input, session_id=session_id)
            except Exception as exc:
                console.print(
                    Panel(
                        f"[bold red]Erro durante o processamento:[/bold red] {exc}",
                        border_style="red",
                    )
                )
                continue

        last_model_used = result.get("model_used") or "desconhecido"
        response_text = result.get("response") or "(Sem resposta)"

        _render_turn_telemetry(result)

        model_badge = f"[bold magenta]Modelo: {last_model_used}[/bold magenta]"
        console.print(
            Panel(
                Markdown(response_text),
                title="[bold bright_cyan]Empório da Música[/bold bright_cyan]",
                subtitle=model_badge,
                border_style="bright_cyan",
            )
        )


def main() -> None:
    """Parse CLI arguments and launch the interactive chat loop."""
    parser = argparse.ArgumentParser(
        description="Empório da Música — Interface de Terminal Interativa (Rich CLI)"
    )
    parser.add_argument(
        "--session-id",
        default="cli-default",
        help="Identificador da sessão SQLite (padrão: cli-default)",
    )
    args = parser.parse_args()
    run_cli(initial_session_id=args.session_id)


if __name__ == "__main__":
    main()
