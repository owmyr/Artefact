# AGENTS.md — Empório da Música AI Customer Support Agent

## 1. Project Mission & Assessment Constraints
You are building a production-ready Python customer service agent for **Empório da Música**, a musical instrument store located in Campo Grande/MS.
- **Primary Language**: Python 3.11+ (type-annotated, modular, PEP 8 compliant).
- **Agent Customer-Facing Language**: Natural Brazilian Portuguese (`pt-BR`).
- **Repository Documentation Language**: English primary (with a Portuguese quick-start summary) in `README.md`.
- **Git Hygiene**: Never squash or force-push the entire project into a single commit. Verify each milestone with `pytest` before committing.

## 2. Canonical Directory Structure
Maintain this exact project layout:

```text
.
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── app.py                        # Streamlit Chat UI with telemetry sidebar
├── cli.py                        # Rich terminal chat interface
├── data/
│   ├── categories.csv
│   ├── customers.csv
│   ├── order_items.csv
│   ├── orders.csv
│   ├── products.csv
│   ├── promotions.csv
│   └── politicas_da_loja.pdf
├── src/
│   ├── __init__.py
│   ├── config.py                 # Env config & Gemini model cascade list
│   ├── database.py               # SQLite ingestion & v_product_catalog view
│   ├── policies_kb.py            # Section-preserved Markdown policy knowledge base
│   ├── tools.py                  # Deterministic Pydantic-typed agent tools
│   ├── llm_fallback.py           # Gemini Free-Tier multi-model fallback router
│   ├── prompts.py                # System prompt, persona, and guardrails
│   └── agent.py                  # Stateful ReAct loop + SQLite session memory
├── scripts/
│   ├── generate_examples.py      # Generates 5 multi-turn markdown transcripts
│   └── export_submission_pdf.py  # Compiles final executive summary PDF
├── examples/                     # 5 generated .md conversation logs
└── tests/
    ├── test_tools.py             # Unit tests for data/policy edge cases
    └── test_fallback.py          # Unit tests for 429/503 model fallback rotation
```

## 3. LLM & Free-Tier Multi-Model Fallback Invariants
- Use the official **`google-genai` SDK** (`from google import genai` and `from google.genai import types, errors`). Never use the deprecated `google-generativeai` package.
- **Prioritized Model Cascade**:
  `["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]`
- **Manual ReAct Loop Required**: Disable SDK automatic function calling (`automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)`). Every individual `generate_content` call inside the ReAct loop must pass through `GeminiFallbackRouter.generate_with_fallback()` so a `429 RESOURCE_EXHAUSTED` or `503 UNAVAILABLE` mid-turn switches seamlessly to the next model without re-running already-executed tools.
- **Cross-Model History Sanitization**: When appending model function calls to conversation history, construct clean `types.Part.from_function_call(name=..., args=...)` and `types.Part.from_function_response(name=..., response=...)` objects rather than passing raw model-specific thinking parts that could fail if a fallback switches model families mid-turn.

## 4. Mandatory Data & Business Logic Rules (Do Not Violate)

### 4.1 Product Availability Definition
- A product is available for immediate purchase **ONLY IF** `status == 'active' AND stock_quantity > 0`.
- `product_id=96` (*Giannini GF-3D Dreadnought Sunburst*, R$ 799.90) has `status='active'` but `stock_quantity=0` -> treat as **out of stock**.
- `product_id=136` (*Ibanez Bass 2X Electric Bass*) has `stock_quantity=13` but `status='discontinued'` -> treat as **discontinued** (never offer as available).
- `product_id=130` (*Kala KA-ABP-CTG Barítono Cedar*) has `stock_quantity=2` but `status='coming_soon'` -> treat as **coming soon / pre-release**.
- Categories 6 (*Instrumentos de Sopro - Madeiras*), 7 (*Instrumentos de Sopro - Metais*), and 8 (*Cordas Orquestrais*) have 0 products in `products.csv`.
- Whenever a user asks for an unavailable product or empty category, clearly report its status and proactively return up to 3 available alternatives in the same category and similar price range (Policy Section 7.3).

### 4.2 Promotions & PIX Discount Non-Cumulativity (Policy Section 6.2 & 7.3)
- `promotions.csv` contains 25 rows, but only **4 are active (`is_active == 1`)**: `promotion_id` 12 (`product_id=127`, 10%), 14 (`product_id=121`, 20%), 19 (`product_id=90`, 18%), and 24 (`product_id=94`, 8%).
- Products `93`, `96`, and `99` have duplicate inactive rows in `promotions.csv`. SQL views and queries must deduplicate promotions so products never appear twice.
- **Expired Promotion Rule**: If a product has `is_active == 0` (e.g., `product_id=95`, *Takamine GD20 Dreadnought Natural*, R$ 2,199.00, which had a 12% expired promotion), the tool and agent must transparently inform the customer that the promotion has expired and quote the current table price (`R$ 2,199.00`) plus the 5% PIX discount (`R$ 2,089.05`).
- **Active Promotion Rule**: Display original price, discount %, and promotional price side-by-side. The 5% PIX discount **never stacks** with an active promotion (`is_active == 1`).

### 4.3 Installment Tiers & Split Payments (Policy Section 3 & 3.1)
- Credit card installments are interest-free up to 12x with tiered minimum installment values:
  - **1x to 3x**: minimum installment **R$ 50.00**
  - **4x to 6x**: minimum installment **R$ 80.00**
  - **7x to 12x**: minimum installment **R$ 100.00**
- Combining payment methods (e.g., PIX + Credit Card) is allowed **only** for purchases above **R$ 2,000.00**.

### 4.4 Returns, Exchanges & Warranty Windows (Policy Section 4 & 8)
- **Right of Regret (`Direito de Arrependimento` - Section 4.1)**: Up to **7 calendar days** after product receipt (`estimated_delivery` on `delivered` orders). Store pays return shipping; refund in up to 10 business days.
- **Preference Exchange (Section 4.3)**: Up to **7 calendar days** in original packaging.
- **Defect Exchange with Store (Section 4.2)**: Up to **30 calendar days** from purchase (`order_date`). After 30 days, warranty is handled with the manufacturer (store can intermediate).
- **Legal Warranty (Section 8.1)**: **90 calendar days** from receipt against manufacturing defects.
- **Non-Eligible Items (Section 4.4)**: Custom-setup instruments, final-sale clearance items, and wind instrument mouthpieces (*boquilhas*) for hygiene reasons.

### 4.5 Store Scope & Contact Discrepancy Handling (Policy Section 1, 1.2, 5, 7, 9)
- **Strict Scope**: Empório da Música sells **exclusively musical instruments**. Politely refuse requests for accessories (strings/cordas avulsas, picks/palhetas, cables/cabos, cases, pedals/pedais, amplifiers/amplificadores) and suggest looking for partner accessory stores.
- **Contact Numbers**: The manual lists `(67) 3341-4444` in Section 1.2 (General Phone/WhatsApp) and `(67) 3321-4500` in Section 7 (Dedicated Remote WhatsApp Support). Always provide both numbers clearly when asked for contact details.
- **LGPD (Section 9)**: Require `order_id` plus customer verification (name, email, or phone) or lookup by exact email/phone before disclosing order details.

## 5. Verification Standard
Before finishing any milestone prompt:
1. Run `pytest` to verify all unit tests pass.
2. Ensure no API keys or `.env` files are staged in Git (`.gitignore` must exclude `.env`, `__pycache__/`, `.venv/`, and `*.pyc`).

---
trigger: glob
description: "Enforce pytest execution and type safety whenever Python files are modified"
globs: "*.py"
---

- Whenever you create or modify a `.py` file in `src/` or `tests/`, run `pytest -q` in the terminal before declaring the task complete.
- Never hardcode `GEMINI_API_KEY`; always load it via `src/config.py` from `.env`.
- Keep all tool outputs deterministic, structured, and self-explanatory so the LLM never has to perform mental arithmetic on prices, discounts, or date windows.