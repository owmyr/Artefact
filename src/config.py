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
    POLICIES_PDF_ACCENTED
    if POLICIES_PDF_ACCENTED.exists() and POLICIES_PDF_ACCENTED.stat().st_size > 1024
    else POLICIES_PDF_UNACCENTED
)

# Load environment variables from .env file if present
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _get_env_or_secret(key: str, default: str = "") -> str:
    """Retrieve configuration from environment variable or Streamlit secrets.

    Why: Allows seamless configuration via either local .env or Streamlit Cloud secrets.
    """
    val = os.getenv(key)
    if val is not None and val.strip():
        return val.strip()
    try:
        import streamlit as st

        if hasattr(st, "secrets") and key in st.secrets:
            secret_val = st.secrets[key]
            if secret_val:
                return str(secret_val).strip()
    except Exception:
        pass
    return default


# Google Gemini API key
GEMINI_API_KEY: str = _get_env_or_secret("GEMINI_API_KEY", "")

# External OpenAI-compatible Fallback Settings (Groq Cloud or Remote Ollama)
GROQ_API_KEY: str = _get_env_or_secret("GROQ_API_KEY", "")
GROQ_MODEL: str = _get_env_or_secret("GROQ_MODEL", "llama-3.3-70b-versatile")
OLLAMA_HOST: str = _get_env_or_secret("OLLAMA_HOST", "")
OLLAMA_MODEL: str = _get_env_or_secret("OLLAMA_MODEL", "llama3.3")

# Prioritized Free-Tier Gemini Model Fallback Cascade optimized by model capability
DEFAULT_MODEL_CASCADE: list[str] = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_raw_models: str | None = os.getenv("GEMINI_MODELS")
if _raw_models and _raw_models.strip():
    GEMINI_MODEL_CASCADE: list[str] = [
        model.strip() for model in _raw_models.split(",") if model.strip()
    ]
else:
    GEMINI_MODEL_CASCADE = list(DEFAULT_MODEL_CASCADE)


class Settings:
    """Typed namespace proxy exposing module-level configuration attributes.

    Why: Allows both `from src import config as settings` and `from src.config import settings`
    patterns across the codebase without duplicating environment resolution.
    """

    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    DB_PATH: Path = DB_PATH
    CATEGORIES_CSV: Path = CATEGORIES_CSV
    CUSTOMERS_CSV: Path = CUSTOMERS_CSV
    ORDERS_CSV: Path = ORDERS_CSV
    ORDER_ITEMS_CSV: Path = ORDER_ITEMS_CSV
    PRODUCTS_CSV: Path = PRODUCTS_CSV
    PROMOTIONS_CSV: Path = PROMOTIONS_CSV
    POLICIES_PDF: Path = POLICIES_PDF
    GEMINI_API_KEY: str = GEMINI_API_KEY
    GROQ_API_KEY: str = GROQ_API_KEY
    GROQ_MODEL: str = GROQ_MODEL
    OLLAMA_HOST: str = OLLAMA_HOST
    OLLAMA_MODEL: str = OLLAMA_MODEL
    DEFAULT_MODEL_CASCADE: list[str] = DEFAULT_MODEL_CASCADE
    GEMINI_MODEL_CASCADE: list[str] = GEMINI_MODEL_CASCADE


settings = Settings()

