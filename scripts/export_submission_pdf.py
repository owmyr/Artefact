"""Compile the final Executive Summary and Conversation Examples PDF for Google Forms submission.

Why: Generates a clean, well-formatted PDF document (`Olmir Stocker Neto - AI Engineer –
Full-Stack para Aplicações com IA Generativa.pdf`) using `fpdf2` with strict Latin-1/CP1252
text sanitization so Portuguese accents render natively while emojis and unsupported Unicode
glyphs are safely replaced without encoding errors.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from fpdf import FPDF

BASE_DIR: Path = Path(__file__).resolve().parent.parent
EXAMPLES_DIR: Path = BASE_DIR / "examples"
OUTPUT_PDF_NAME: str = (
    "Olmir Stocker Neto - AI Engineer \u2013 Full-Stack para Aplica\u00e7\u00f5es com IA Generativa.pdf"
)
OUTPUT_PDF_PATH: Path = BASE_DIR / OUTPUT_PDF_NAME
GITHUB_REPO_URL: str = "https://github.com/owmyr/Artefact"
LIVE_DEMO_URL: str = "https://olmir-artefact.streamlit.app/"

# Mapping of non-Latin-1 Unicode punctuation, arrows, and emojis to clean Latin-1 equivalents
_UNICODE_REPLACEMENTS: dict[str, str] = {
    "\u2013": "-",  # en-dash
    "\u2014": " - ",  # em-dash
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2022": "-",  # bullet
    "\u2026": "...",
    "\u2192": "->",
    "\u2190": "<-",
    "\u2194": "<->",
    "\u2264": "<=",
    "\u2265": ">=",
    "\u2705": "[OK] ",
    "\u274c": "[X] ",
    "\u26a0\ufe0f": "[!] ",
    "\u26a0": "[!] ",
    "\u2139\ufe0f": "[i] ",
    "\U0001f3b8": "",  # guitar emoji
    "\U0001f3b6": "",  # musical notes
    "\U0001f3b5": "",
    "\U0001f4cb": "",  # clipboard
    "\U0001f4ac": "",  # speech bubble
    "\U0001f9d1\u200d\U0001f3a4": "",  # singer
    "\U0001f50d": "",  # magnifying glass
    "\U0001f3f7\ufe0f": "",
    "\U0001f3f7": "",
    "\U0001f4b0": "",
    "\U0001f4b3": "",
    "\U0001f91d": "",
    "\U0001f504": "",
    "\U0001f512": "",
    "\U0001f4e6": "",
    "\U0001f69a": "",
    "\U0001f4cd": "",
    "\U0001f4de": "",
    "\U0001f552": "",
    "\U0001f6f5": "",
    "\U0001f6e1\ufe0f": "",
    "\U0001f6e1": "",
    "\U0001f4a1": "",
    "\U0001f389": "",
    "\U0001f916": "",
    "\U0001f6e0\ufe0f": "",
    "\U0001f6e0": "",
    "\u26a1": "",
}


def sanitize_latin1(text: str) -> str:
    """Sanitize arbitrary UTF-8 string into clean Latin-1 compatible text for FPDF core fonts.

    Why: Standard PDF core fonts (Helvetica/Courier) support ISO-8859-1 (Latin-1), which covers
    all Portuguese accented characters (á, é, í, ó, ú, ã, õ, â, ê, ô, ç, etc.) but raises
    `FPDFUnicodeEncodingException` on emojis or typographic dashes.
    """
    if not text:
        return ""
    cleaned = text
    for src, target in _UNICODE_REPLACEMENTS.items():
        cleaned = cleaned.replace(src, target)

    # Strip remaining variation selectors or zero-width joiners
    cleaned = cleaned.replace("\ufe0f", "").replace("\u200d", "")

    # Strip markdown strikethrough tildes
    cleaned = cleaned.replace("~~", "")

    # Encode to latin-1 replacing any remaining unsupported codepoints cleanly
    return cleaned.encode("latin-1", errors="ignore").decode("latin-1")


def strip_markdown_inline(text: str) -> str:
    """Remove inline Markdown bold/italic/code markers for clean paragraph rendering."""
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    cleaned = re.sub(r"\*(.*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"`(.*?)`", r"\1", cleaned)
    return sanitize_latin1(cleaned).strip()


class SubmissionPDF(FPDF):
    """Custom FPDF class with branded running header and page-numbered footer."""

    def header(self) -> None:
        """Render top running header on every page after page 1."""
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 110, 125)
        header_text = sanitize_latin1(
            "Olmir Stocker Neto | AI Engineer - Full-Stack para Aplicações com IA Generativa | Empório da Música"
        )
        self.cell(0, 6, header_text, align="L", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(210, 215, 225)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self) -> None:
        """Render bottom page number and clickable repository link."""
        self.set_y(-13)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(110, 120, 135)
        self.cell(
            0,
            8,
            sanitize_latin1(f"Página {self.page_no()}/{{nb}}  |  {GITHUB_REPO_URL}"),
            align="C",
            link=GITHUB_REPO_URL,
        )

    def section_banner(self, title: str) -> None:
        """Render a navy-blue section heading bar."""
        self.ln(3)
        self.set_fill_color(22, 48, 82)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.cell(
            0,
            8,
            sanitize_latin1(f"  {title}"),
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )
        self.set_text_color(25, 30, 38)
        self.ln(2)

    def sub_heading(self, title: str) -> None:
        """Render a secondary bold subheading."""
        self.ln(1.5)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(22, 48, 82)
        self.multi_cell(0, 5.5, sanitize_latin1(title), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(25, 30, 38)
        self.ln(0.5)

    def body_paragraph(self, text: str) -> None:
        """Render a standard body paragraph."""
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(30, 35, 42)
        self.multi_cell(0, 4.8, sanitize_latin1(text), new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def bullet_item(self, label: str, description: str) -> None:
        """Render a formatted bullet point with bold lead-in label."""
        self.set_font("Helvetica", "", 9.2)
        self.set_text_color(30, 35, 42)
        combined = f"  - {label}: {description}" if label else f"  - {description}"
        self.multi_cell(0, 4.6, sanitize_latin1(combined), new_x="LMARGIN", new_y="NEXT")
        self.ln(0.8)

    def code_block(self, code_text: str) -> None:
        """Render a monospace shaded block for shell commands or telemetry."""
        self.set_fill_color(242, 244, 248)
        self.set_draw_color(210, 215, 225)
        self.set_font("Courier", "", 8.2)
        self.set_text_color(25, 35, 50)
        for raw_line in code_text.strip().splitlines():
            safe_line = sanitize_latin1(raw_line)
            self.multi_cell(
                0,
                4.3,
                f"  {safe_line}",
                fill=True,
                new_x="LMARGIN",
                new_y="NEXT",
            )
        self.set_text_color(30, 35, 42)
        self.ln(2)


def _render_cover_and_executive_summary(pdf: SubmissionPDF) -> None:
    """Render the Cover Banner, GitHub Link Callout, and Executive Summary."""
    # Cover Header Banner
    pdf.set_fill_color(15, 36, 64)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(
        0,
        11,
        sanitize_latin1("  EMPÓRIO DA MÚSICA — AI CUSTOMER SUPPORT AGENT"),
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(
        0,
        7,
        sanitize_latin1(
            "  Technical Case Submission | Stateful ReAct Agent + SQLite + Gemini Multi-Model Fallback"
        ),
        fill=True,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(3)

    # Candidate Metadata Box
    pdf.set_fill_color(240, 245, 252)
    pdf.set_draw_color(35, 85, 155)
    pdf.set_text_color(20, 30, 45)
    pdf.set_font("Helvetica", "B", 10)
    today_str = date.today().strftime("%Y-%m-%d")
    meta_lines = [
        "Candidate Name: Olmir Stocker Neto",
        "Role: AI Engineer - Full-Stack para Aplicações com IA Generativa",
        f"Submission Date: {today_str}",
    ]
    for line in meta_lines:
        pdf.cell(
            0,
            6,
            sanitize_latin1(f"  {line}"),
            border="LR",
            fill=True,
            new_x="LMARGIN",
            new_y="NEXT",
        )

    # Prominent Clickable GitHub Repository & Live Demo Links
    pdf.set_font("Helvetica", "B", 10.2)
    pdf.set_text_color(15, 82, 186)
    pdf.cell(
        0,
        6.5,
        sanitize_latin1(f"  Public GitHub Repository: {GITHUB_REPO_URL}  (Click to Open)"),
        border="LR",
        fill=True,
        link=GITHUB_REPO_URL,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        7,
        sanitize_latin1(f"  Live Interactive Cloud Demo: {LIVE_DEMO_URL}  (Click to Test Online)"),
        border="LRB",
        fill=True,
        link=LIVE_DEMO_URL,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(25, 30, 38)
    pdf.ln(2)

    # Section 1: Architecture Overview
    pdf.section_banner("1. EXECUTIVE SUMMARY & SYSTEM ARCHITECTURE")
    pdf.body_paragraph(
        "This submission implements a production-ready, zero-hallucination AI Customer Support Agent "
        "for Empório da Música (Campo Grande/MS). Rather than relying on naive vector RAG (which fails "
        "on numeric price filtering and stock counts) or raw Text-to-SQL (which introduces prompt injection "
        "and join-omission risks), the system uses a Stateful Manual ReAct Architecture backed by "
        "validated Pydantic tools and a precomputed SQLite relational view (`v_product_catalog`)."
    )
    pdf.bullet_item(
        "User Interfaces (`app.py` & `cli.py`)",
        "Streamlit Web UI with live model-cascade telemetry sidebar, session switcher, and per-turn tool "
        "audit expanders, plus an interactive Rich CLI (`/models`, `/new`, `/exit`).",
    )
    pdf.bullet_item(
        "Manual ReAct Agent + SQLite Memory (`src/agent.py`)",
        "Executes up to 5 reasoning/tool iterations per turn with SDK automatic function calling disabled, "
        "persisting multi-turn conversations in the SQLite `chat_history` table.",
    )
    pdf.bullet_item(
        "Deterministic Tool Layer (`src/tools.py`)",
        "Four Pydantic-validated tools (`search_catalog`, `calculate_payment_options`, `get_order_status`, "
        "`consult_store_policies`) perform all SQL queries, price/discount math, and CDC date calculations.",
    )
    pdf.bullet_item(
        "Section-Preserved Policy KB (`src/policies_kb.py`)",
        "Extracts all 10 sections of `politicas_da_loja.pdf` into structured Markdown with intact SLA "
        "and credit card installment tables, avoiding fixed-token chunking table fractures.",
    )

    # Section 2: Gemini Multi-Model Fallback Router
    pdf.section_banner("2. GEMINI FREE-TIER MULTI-MODEL FALLBACK ROUTER (src/llm_fallback.py)")
    pdf.body_paragraph(
        "To guarantee 100% uptime when evaluated with a Google AI Studio Free-Tier API key (where RPM "
        "and RPD quotas are enforced independently per model ID), `GeminiFallbackRouter` routes every "
        "ReAct step across a prioritized 7-model capability cascade:"
    )
    pdf.code_block(
        "1. gemini-3.8-flash -> 2. gemini-3.6-flash -> 3. gemini-3-flash-preview ->\n"
        "4. gemini-3.5-flash-lite -> 5. gemini-3.1-flash-lite -> 6. gemini-2.5-flash -> 7. gemini-2.5-flash-lite"
    )
    pdf.bullet_item(
        "Cooldown State Machine",
        "HTTP 429 RPM limit sets a 60s cooldown; HTTP 429 daily quota (RPD/PerDay) sets a 3600s cooldown; "
        "HTTP 503/500/504 retries once after 1.5s then sets a 30s cooldown; HTTP 404/400 disables the model.",
    )
    pdf.bullet_item(
        "Mid-Turn Failover & History Sanitization",
        "If the primary model executes a tool on Iteration 1 and hits HTTP 429 on Iteration 2, "
        "the next model synthesizes the final response from clean `Part.from_function_call` / "
        "`Part.from_function_response` objects without re-running the already-executed tool.",
    )

    # Section 3: EDA Anomalies Discovered & Solved
    pdf.section_banner("3. EXPLORATORY DATA ANALYSIS (EDA) ANOMALIES DISCOVERED & SOLVED")
    pdf.bullet_item(
        "1. Stock vs. Status Anomalies (`products.csv`)",
        "Enforced `is_available = (status == 'active' AND stock_quantity > 0)`. Caught `product_id=96` "
        "(Giannini GF-3D, `active` but `stock=0` -> out of stock, leaving exactly 12 available acoustic "
        "guitars <= R$ 1,000), `product_id=136` (Ibanez Bass 2X, `stock=13` but `discontinued`), "
        "`product_id=113` (Shelby SN-7C, `discontinued`), and `product_id=130` (Kala Barítono, `coming_soon`). "
        "All return up to 3 in-stock alternatives in the same category and price range (Section 7.3).",
    )
    pdf.bullet_item(
        "2. Empty Catalog Categories (`categories.csv`)",
        "Categories 6 (Sopro - Madeiras), 7 (Sopro - Metais), and 8 (Cordas Orquestrais) have 0 products "
        "in `products.csv`. Queries for wind/orchestral instruments report the empty category transparently "
        "and suggest available alternatives.",
    )
    pdf.bullet_item(
        "3. Promotion Deduplication & Expired Campaigns (`promotions.csv`)",
        "Only 4 of 25 rows have `is_active=1` (IDs 12, 14, 19, 24 on products 127, 121, 90, 94). Duplicate "
        "inactive rows (products 93, 96, 99) are deduplicated via `ROW_NUMBER()` in `v_product_catalog`. "
        "Expired promotions (e.g., `product_id=95` Takamine GD20, 12% expired) are disclosed transparently "
        "with current table price (R$ 2,199.00) + 5% PIX (R$ 2,089.05). The 5% PIX discount never stacks "
        "with active promotions (Section 6.2).",
    )
    pdf.bullet_item(
        "4. Policy Manual Internal Discrepancies Resolved",
        "Both contact numbers — `(67) 3341-4444` (Section 1.2 General/Store) and `(67) 3321-4500` "
        "(Section 7 Dedicated Remote WhatsApp) — are always presented together. Credit card installments "
        "enforce the specific tiered minimums in Section 3.1 (1x-3x min R$ 50; 4x-6x min R$ 80; 7x-12x min "
        "R$ 100) and Split Payment (PIX + Card) for purchases > R$ 2,000.00.",
    )
    pdf.bullet_item(
        "5. LGPD Verification & CDC Date Windows (`orders.csv`)",
        "`get_order_status` requires `order_id` + customer identity verification (Section 9 LGPD) and "
        "deterministically computes 7-day Right of Regret (from delivery), 30-day Store Defect Exchange "
        "(from purchase), and 90-day Legal Warranty windows.",
    )

    # Section 4: Environment Setup & Execution Instructions
    pdf.section_banner("4. QUICK SETUP, LIVE DEMO & AI ENGINEERING WORKFLOW")
    pdf.bullet_item(
        "Adversarial Multi-Model AI Workflow",
        "Every architectural plan and prompt was reviewed by Claude Sonnet, implemented via Google Antigravity, "
        "and adversarially audited (Red Team feedback & optimization) by GLM 5.3 through OpenCode.",
    )
    pdf.code_block(
        "# Live Cloud Demo (Zero Setup): https://olmir-artefact.streamlit.app/\n"
        "git clone https://github.com/owmyr/Artefact.git && cd Artefact\n"
        "python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt\n"
        "cp .env.example .env   # Set GEMINI_API_KEY=your_google_ai_studio_key\n"
        "pytest -v              # Run all 35 unit & fallback tests\n"
        "streamlit run app.py   # Launch Web Chat UI with Telemetry Sidebar\n"
        "python cli.py          # (Optional) Launch Interactive Rich Terminal CLI"
    )


def _render_markdown_transcript(pdf: SubmissionPDF, md_path: Path) -> None:
    """Parse and render one of the 5 `examples/*.md` conversation logs cleanly into the PDF."""
    raw_content = md_path.read_text(encoding="utf-8")
    lines = raw_content.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            pdf.ln(1)
            continue

        if stripped == "---":
            pdf.ln(1)
            pdf.set_draw_color(210, 215, 225)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
            continue

        # Top-level Scenario Title (# Cenário ...)
        if stripped.startswith("# "):
            title_text = strip_markdown_inline(stripped[2:])
            pdf.section_banner(title_text)
            continue

        # Section headers (## ... or ### ...)
        if stripped.startswith("## ") or stripped.startswith("### "):
            level_text = re.sub(r"^#+\s*", "", stripped)
            pdf.sub_heading(strip_markdown_inline(level_text))
            continue

        # Speaker / Telemetry subheaders (#### ...)
        if stripped.startswith("#### "):
            role_text = strip_markdown_inline(stripped[5:])
            pdf.ln(1)
            if "Cliente (User)" in role_text:
                pdf.set_fill_color(232, 242, 254)
                pdf.set_font("Helvetica", "B", 9.5)
                pdf.set_text_color(15, 60, 130)
                pdf.cell(
                    0,
                    6,
                    sanitize_latin1(f"  [USER] {role_text}"),
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            elif "Assistente" in role_text:
                pdf.set_fill_color(235, 248, 238)
                pdf.set_font("Helvetica", "B", 9.5)
                pdf.set_text_color(20, 100, 45)
                pdf.cell(
                    0,
                    6,
                    sanitize_latin1(f"  [AGENT] {role_text}"),
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            else:
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(70, 80, 95)
                pdf.cell(
                    0,
                    5.5,
                    sanitize_latin1(role_text),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            pdf.set_text_color(25, 30, 38)
            pdf.ln(0.8)
            continue

        # Blockquote user prompt (> ...)
        if stripped.startswith(">"):
            quote_text = strip_markdown_inline(stripped.lstrip(">").strip())
            pdf.set_font("Helvetica", "BI", 9.5)
            pdf.set_text_color(20, 50, 100)
            pdf.multi_cell(
                0,
                5,
                sanitize_latin1(f'"{quote_text}"'),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.set_text_color(25, 30, 38)
            pdf.ln(1)
            continue

        # Bullet or numbered list items
        if stripped.startswith("- ") or stripped.startswith("* ") or re.match(r"^\d+\.\s", stripped):
            clean_item = strip_markdown_inline(stripped)
            # Check if it's a tool call line
            if any(
                tool_name in clean_item
                for tool_name in (
                    "search_catalog(",
                    "calculate_payment_options(",
                    "get_order_status(",
                    "consult_store_policies(",
                )
            ):
                pdf.set_font("Courier", "", 8.2)
                pdf.set_fill_color(244, 246, 250)
                pdf.multi_cell(
                    0,
                    4.5,
                    sanitize_latin1(f"  {clean_item}"),
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(
                    0,
                    4.5,
                    sanitize_latin1(f"  {clean_item}"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
            pdf.ln(0.4)
            continue

        # Standard paragraph line
        pdf.set_font("Helvetica", "", 9.2)
        pdf.set_text_color(30, 35, 42)
        pdf.multi_cell(
            0,
            4.6,
            strip_markdown_inline(stripped),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(0.8)


def generate_submission_pdf(output_path: Path = OUTPUT_PDF_PATH) -> Path:
    """Build and save the complete submission PDF document."""
    pdf = SubmissionPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=14, top=14, right=14)
    pdf.alias_nb_pages()

    # Page 1+: Executive Summary & Technical Architecture
    pdf.add_page()
    _render_cover_and_executive_summary(pdf)

    # Appendix: All 5 Multi-Turn Conversation Transcripts
    example_files = sorted(EXAMPLES_DIR.glob("0*.md"))
    if not example_files:
        raise FileNotFoundError(f"No example transcripts found in {EXAMPLES_DIR}")

    for idx, md_file in enumerate(example_files, start=1):
        pdf.add_page()
        if idx == 1:
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(15, 36, 64)
            pdf.cell(
                0,
                8,
                sanitize_latin1(
                    "APPENDIX: 5 MULTI-TURN CONVERSATION TRANSCRIPTS (examples/01_*.md - 05_*.md)"
                ),
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(1)
        _render_markdown_transcript(pdf, md_file)

    pdf.output(str(output_path))
    return output_path


if __name__ == "__main__":
    saved_path = generate_submission_pdf()
    size_kb = saved_path.stat().st_size / 1024.0
    print(f"Submission PDF generated successfully: {saved_path.name} ({size_kb:.1f} KB)")
