"""Configuration and environment management for Empório da Música support agent.

Why: Centralizes filesystem locations, API credentials, and LLM model cascades
in a single typed module to prevent hardcoding across database, tools, and UI.
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Base project paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
DB_PATH: Path = BASE_DIR / "emporio.db"

# Data file paths
CATEGORIES_CSV: Path = DATA_DIR / "categories.csv"
CUSTOMERS_CSV: Path = DATA_DIR / "customers.csv"
ORDERS_CSV: Path = DATA_DIR / "orders.csv"
ORDER_ITEMS_CSV: Path = DATA_DIR / "order_items.csv"
PRODUCTS_CSV: Path = DATA_DIR / "products.csv"
PROMOTIONS_CSV: Path = DATA_DIR / "promotions.csv"

# Handle potential accented or unaccented filename for store policies
POLICIES_PDF_ACCENTED: Path = DATA_DIR / "políticas_da_loja.pdf"
POLICIES_PDF_UNACCENTED: Path = DATA_DIR / "politicas_da_loja.pdf"
POLICIES_PDF: Path = (
    POLICIES_PDF_ACCENTED if POLICIES_PDF_ACCENTED.exists() else POLICIES_PDF_UNACCENTED
)

# Load environment variables from .env file if present
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Google Gemini API key
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

# Prioritized Free-Tier Gemini Model Fallback Cascade (per AGENTS.md invariant)
DEFAULT_MODEL_CASCADE: list[str] = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

_raw_models: str | None = os.getenv("GEMINI_MODELS")
if _raw_models and _raw_models.strip():
    GEMINI_MODEL_CASCADE: list[str] = [
        model.strip() for model in _raw_models.split(",") if model.strip()
    ]
else:
    GEMINI_MODEL_CASCADE = list(DEFAULT_MODEL_CASCADE)
