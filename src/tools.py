"""Deterministic, Pydantic-typed customer support tools for Empório da Música.

Why: Grounds the Gemini LLM agent in validated SQLite queries and deterministic
financial/calendar calculations so the model never performs mental arithmetic
on prices, PIX non-cumulativity, installment tiers, or CDC return/warranty windows.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from src.config import DB_PATH
from src.database import get_connection, init_database, parse_specs
from src.policies_kb import (
    STORE_POLICY_SECTIONS,
    get_all_policies,
    get_contact_info,
    search_policies,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic Schemas for Deterministic Tool Validation
# ---------------------------------------------------------------------------


class SearchCatalogInput(BaseModel):
    """Validated parameters for catalog search queries.

    Why: Enforces type constraints and non-negative price bounds before
    executing relational filters against v_product_catalog.
    """

    query: Optional[str] = Field(
        default=None,
        description="Termo livre de busca (modelo, marca, tipo de corda, madeira, etc.).",
    )
    category: Optional[str] = Field(
        default=None,
        description="Nome ou tipo da categoria de instrumento (ex: Violões, Guitarras, Sopro, Ukuleles).",
    )
    max_price: Optional[float] = Field(
        default=None,
        description="Preço máximo em reais (R$).",
    )
    min_price: Optional[float] = Field(
        default=None,
        description="Preço mínimo em reais (R$).",
    )
    only_available: bool = Field(
        default=False,
        description="Se True, oculta itens indisponíveis da lista principal.",
    )


class CalculatePaymentInput(BaseModel):
    """Validated parameters for payment and installment calculations.

    Why: Ensures price_brl is a positive float and has_active_promotion is a boolean
    before computing tiered credit card installments and PIX discounts.
    """

    price_brl: float = Field(..., gt=0, description="Valor do produto ou compra em R$.")
    has_active_promotion: bool = Field(
        default=False,
        description="True se o produto já possui promoção ativa (is_active=1), impedindo cumulatividade do PIX.",
    )


class GetOrderStatusInput(BaseModel):
    """Validated parameters for LGPD-compliant order lookup.

    Why: Standardizes optional order_id, customer identity verification string,
    and ISO reference date for deterministic return/warranty deadline calculations.
    """

    order_id: Optional[int] = Field(
        default=None,
        description="Número identificador do pedido (ex: 1, 8, 18).",
    )
    customer_identifier: Optional[str] = Field(
        default=None,
        description="Nome, e-mail ou telefone do cliente para verificação de titularidade (LGPD).",
    )
    reference_date: str = Field(
        default="2026-03-25",
        description="Data de referência no formato YYYY-MM-DD para cálculo de prazos de troca e garantia.",
    )


# ---------------------------------------------------------------------------
# Internal Normalization & Database Helpers
# ---------------------------------------------------------------------------

_STOPWORDS: set[str] = {
    "a",
    "o",
    "as",
    "os",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "um",
    "uma",
    "uns",
    "umas",
    "para",
    "por",
    "com",
    "sem",
    "ate",
    "entre",
    "sobre",
    "que",
    "qual",
    "quais",
    "tem",
    "ter",
    "quero",
    "busco",
    "procuro",
    "instrumento",
    "instrumentos",
}

_STEM_ALIASES: dict[str, list[str]] = {
    "violao": ["violao", "violoes"],
    "violoes": ["violao", "violoes"],
    "guitarra": ["guitarra", "guitarras"],
    "guitarras": ["guitarra", "guitarras"],
    "baixo": ["baixo", "baixos", "contrabaixo", "bass"],
    "baixos": ["baixo", "baixos", "contrabaixo", "bass"],
    "contrabaixo": ["baixo", "baixos", "contrabaixo", "bass"],
    "bateria": ["bateria", "baterias", "percussao"],
    "baterias": ["bateria", "baterias", "percussao"],
    "teclado": ["teclado", "teclados", "sintetizador", "synth", "arranjador"],
    "teclados": ["teclado", "teclados", "sintetizador", "synth", "arranjador"],
    "piano": ["piano", "pianos", "teclado", "teclados"],
    "pianos": ["piano", "pianos", "teclado", "teclados"],
    "ukulele": ["ukulele", "ukuleles"],
    "ukuleles": ["ukulele", "ukuleles"],
    "sopro": ["sopro", "madeiras", "metais", "flauta", "clarinete", "saxofone", "trompete", "trombone", "tuba", "trompa"],
    "madeira": ["madeira", "madeiras", "sopro"],
    "madeiras": ["madeira", "madeiras", "sopro"],
    "metal": ["metal", "metais", "sopro"],
    "metais": ["metal", "metais", "sopro"],
    "orquestral": ["orquestral", "orquestrais", "violino", "viola", "violoncelo"],
    "orquestrais": ["orquestral", "orquestrais", "violino", "viola", "violoncelo"],
    "aco": ["aco", "steel"],
    "steel": ["aco", "steel"],
    "eletrico": ["eletrico", "eletrica", "eletroacustico", "electronics"],
    "eletroacustico": ["eletrico", "eletroacustico"],
}

_EMPTY_CATEGORY_KEYWORDS: dict[int, list[str]] = {
    6: [
        "sopro",
        "madeira",
        "madeiras",
        "flauta",
        "flautas",
        "clarinete",
        "clarinetes",
        "saxofone",
        "saxofones",
        "sax",
        "oboe",
        "oboes",
        "fagote",
    ],
    7: [
        "sopro",
        "metal",
        "metais",
        "trompete",
        "trompetes",
        "trombone",
        "trombones",
        "tuba",
        "tubas",
        "trompa",
        "trompas",
    ],
    8: [
        "cordas orquestrais",
        "orquestral",
        "orquestrais",
        "violino",
        "violinos",
        "viola de arco",
        "violoncelo",
        "violoncelos",
        "cello",
        "contrabaixo acustico",
    ],
}


def _normalize_text(text: str | None) -> str:
    """Strip diacritics, lowercase, and normalize whitespace for accent-insensitive search.

    Why: Brazilian Portuguese queries frequently omit or vary accents (e.g., 'violao' vs 'violão',
    'baritono' vs 'barítono'). Normalizing both query and corpus guarantees deterministic matching.
    """
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    ascii_only = decomposed.encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", ascii_only.lower()).strip()


def _ensure_db_connection() -> sqlite3.Connection:
    """Return an active SQLite connection, initializing schema and seed data if missing.

    Why: Ensures tools work out-of-the-box in fresh environments or test runners without
    requiring a separate manual database bootstrap step.
    """
    if not DB_PATH.exists():
        return init_database(DB_PATH)
    conn = get_connection(DB_PATH)
    cur = conn.cursor()
    view_exists = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='view' AND name='v_product_catalog';"
    ).fetchone()
    if not view_exists:
        conn.close()
        return init_database(DB_PATH)
    return conn


def _availability_metadata(status: str, stock_quantity: int) -> tuple[bool, str, str]:
    """Compute boolean availability, machine status code, and Portuguese label.

    Why: Enforces Section 4.1 of AGENTS.md where a product is available ONLY IF
    status == 'active' AND stock_quantity > 0, distinguishing out-of-stock,
    discontinued, and coming-soon items.
    """
    if status == "active" and stock_quantity > 0:
        return True, "available", "Disponível para pronta entrega"
    if status == "active" and stock_quantity <= 0:
        return False, "out_of_stock", "Fora de estoque (esgotado temporariamente)"
    if status == "discontinued":
        return False, "discontinued", "Produto descontinuado (fora de linha)"
    if status == "coming_soon":
        return False, "coming_soon", "Em breve (pré-lançamento, ainda não disponível para venda imediata)"
    return False, "unavailable", f"Indisponível (status={status}, estoque={stock_quantity})"


def _format_product_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    """Transform a v_product_catalog row into the canonical tool output dictionary.

    Why: Pre-attaches all mandatory pricing, PIX non-cumulativity, and active/expired
    promotion explanations so the agent never guesses or miscalculates discounts.
    """
    data = dict(row)
    status = str(data["status"])
    stock_qty = int(data["stock_quantity"])
    is_avail, avail_status, avail_label_pt = _availability_metadata(status, stock_qty)

    price_brl = round(float(data["price_brl"]), 2)
    active_disc = (
        float(data["active_discount_percent"])
        if data.get("active_discount_percent") is not None
        else None
    )
    has_active_promo = bool(active_disc is not None and active_disc > 0)

    effective_price = round(float(data["effective_price_brl"]), 2)
    pix_price = round(float(data["pix_price_brl"]), 2)

    expired_disc = (
        float(data["expired_discount_percent"])
        if data.get("expired_discount_percent") is not None
        else None
    )
    expired_desc = data.get("expired_promo_description")

    expired_promotion_info: Optional[dict[str, Any]] = None
    if expired_disc is not None and not has_active_promo:
        expired_promotion_info = {
            "is_active": 0,
            "status": "expired",
            "expired_discount_percent": expired_disc,
            "description": expired_desc,
            "campaign_description": expired_desc,
            "table_price_brl": price_brl,
            "pix_price_brl": pix_price,
            "pix_discount_percent": 5.0,
            "message": (
                f"A promoção '{expired_desc}' de {expired_disc:.0f}% expirou (is_active=0). "
                f"O preço atual de tabela é R$ {price_brl:.2f} e o valor à vista no PIX "
                f"(com 5% de desconto) é R$ {pix_price:.2f}."
            ),
        }

    return {
        "product_id": int(data["product_id"]),
        "name": str(data["name"]),
        "category_id": int(data["category_id"]),
        "category_name": str(data["category_name"] or ""),
        "description": str(data["description"] or ""),
        "specs": parse_specs(data.get("specs")),
        "status": status,
        "stock_quantity": stock_qty,
        "is_available": is_avail,
        "availability_status": avail_status,
        "availability_label_pt": avail_label_pt,
        "price_brl": price_brl,
        "has_active_promotion": has_active_promo,
        "active_discount_percent": active_disc,
        "active_promotion_description": data.get("active_promo_description"),
        "effective_price_brl": effective_price,
        "pix_price_brl": pix_price,
        "pix_discount_percent": 0.0 if has_active_promo else 5.0,
        "expired_discount_percent": expired_disc,
        "expired_promotion_info": expired_promotion_info,
    }


def _find_alternatives_for_product(
    conn: sqlite3.Connection,
    category_id: int,
    target_price: float,
    exclude_product_id: Optional[int] = None,
    limit: int = 3,
    product_name: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Query up to 3 available alternative products in the same category and similar price range.

    Why: Implements Policy Section 7.3 and AGENTS.md Section 4.1 by automatically finding
    in-stock substitutes ordered by subtype affinity (e.g., 7-string, Dreadnought) and price
    proximity whenever a product is unavailable.
    """
    cur = conn.cursor()
    name_norm = _normalize_text(product_name)
    is_seven_string = 1 if "7 cordas" in name_norm else 0
    is_dreadnought = 1 if "dreadnought" in name_norm else 0

    order_clause = """
        CASE
            WHEN ? = 1 AND lower(name) LIKE '%7 cordas%' THEN 0
            WHEN ? = 1 AND lower(name) LIKE '%dreadnought%' AND ABS(effective_price_brl - ?) <= 250 THEN 0
            ELSE 1
        END ASC,
        ABS(effective_price_brl - ?) ASC,
        effective_price_brl ASC
    """

    if exclude_product_id is not None:
        rows = cur.execute(
            f"""
            SELECT *
            FROM v_product_catalog
            WHERE category_id = ?
              AND is_available = 1
              AND product_id != ?
            ORDER BY {order_clause}
            LIMIT ?;
            """,
            (
                category_id,
                exclude_product_id,
                is_seven_string,
                is_dreadnought,
                target_price,
                target_price,
                limit,
            ),
        ).fetchall()
    else:
        rows = cur.execute(
            f"""
            SELECT *
            FROM v_product_catalog
            WHERE category_id = ?
              AND is_available = 1
            ORDER BY {order_clause}
            LIMIT ?;
            """,
            (
                category_id,
                is_seven_string,
                is_dreadnought,
                target_price,
                target_price,
                limit,
            ),
        ).fetchall()

    return [_format_product_row(r) for r in rows]


def _find_alternatives_for_empty_category(
    conn: sqlite3.Connection,
    empty_category_ids: list[int],
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return up to 3 available catalog alternatives when a searched category has 0 products.

    Why: Categories 6 (Sopro Madeiras), 7 (Sopro Metais), and 8 (Cordas Orquestrais) have
    0 products in products.csv. Suggesting available acoustic/melodic instruments from the
    store catalog fulfills Policy Section 7.3 cleanly.
    """
    cur = conn.cursor()
    # Map empty categories to closest available musical categories in the store:
    # Cordas Orquestrais (8) -> Violões (5) & Ukuleles (9)
    # Sopro (6, 7) -> Teclados e Pianos (4), Violões (5), Ukuleles (9)
    preferred_cats = [5, 9] if 8 in empty_category_ids else [4, 5, 9]
    placeholders = ",".join("?" for _ in preferred_cats)

    sql = f"""
        SELECT *
        FROM v_product_catalog
        WHERE is_available = 1
          AND category_id IN ({placeholders})
    """
    params: list[Any] = list(preferred_cats)

    if min_price is not None:
        sql += " AND effective_price_brl >= ?"
        params.append(min_price)
    if max_price is not None:
        sql += " AND effective_price_brl <= ?"
        params.append(max_price)

    sql += " ORDER BY price_brl ASC LIMIT ?;"
    params.append(limit)

    rows = cur.execute(sql, params).fetchall()
    if not rows:
        rows = cur.execute(
            "SELECT * FROM v_product_catalog WHERE is_available = 1 ORDER BY price_brl ASC LIMIT ?;",
            (limit,),
        ).fetchall()

    return [_format_product_row(r) for r in rows]


def _detect_empty_categories(
    conn: sqlite3.Connection,
    query: Optional[str],
    category: Optional[str],
) -> list[dict[str, Any]]:
    """Check whether the user's category or query targets an empty category (6, 7, or 8).

    Why: Since v_product_catalog only contains rows for products present in products.csv,
    categories with 0 products must be explicitly inspected against the categories table.
    """
    combined = _normalize_text(f"{category or ''} {query or ''}")
    if not combined:
        return []

    cur = conn.cursor()
    cat_rows = cur.execute(
        """
        SELECT c.category_id, c.name, c.description, COUNT(p.product_id) AS product_count
        FROM categories c
        LEFT JOIN products p ON c.category_id = p.category_id
        GROUP BY c.category_id, c.name, c.description
        HAVING COUNT(p.product_id) = 0
        ORDER BY c.category_id ASC;
        """
    ).fetchall()

    matched_empty: list[dict[str, Any]] = []
    tokens = set(re.findall(r"[a-z0-9]+", combined))

    for row in cat_rows:
        cid = int(row["category_id"])
        cname_norm = _normalize_text(row["name"])
        cdesc_norm = _normalize_text(row["description"])
        kw_list = _EMPTY_CATEGORY_KEYWORDS.get(cid, [])

        is_match = False
        if combined in cname_norm or cname_norm in combined:
            is_match = True
        elif any(kw in combined for kw in kw_list):
            is_match = True
        elif any(tok in cname_norm.split() or tok in cdesc_norm.split() for tok in tokens if len(tok) > 3):
            is_match = True

        if is_match:
            matched_empty.append(
                {
                    "category_id": cid,
                    "category_name": str(row["name"]),
                    "description": str(row["description"] or ""),
                    "product_count": 0,
                    "status": "empty_category",
                    "message": (
                        f"A categoria '{row['name']}' (ID {cid}) está atualmente com 0 produtos "
                        "cadastrados/disponíveis em nosso estoque."
                    ),
                }
            )

    return matched_empty


def _row_matches_category(row: sqlite3.Row, category_filter: str) -> bool:
    """Evaluate case- and accent-insensitive category match against a catalog row.

    Why: Handles singular/plural variations (e.g. 'Violão' vs 'Violões', 'Guitarra' vs 'Guitarras')
    and partial category names accurately.
    """
    cat_norm = _normalize_text(category_filter)
    if not cat_norm:
        return True

    row_cat_norm = _normalize_text(row["category_name"])
    if cat_norm in row_cat_norm or row_cat_norm in cat_norm:
        return True

    cat_tokens = [t for t in re.findall(r"[a-z0-9]+", cat_norm) if t not in _STOPWORDS]
    if not cat_tokens:
        return True

    for tok in cat_tokens:
        variants = _STEM_ALIASES.get(tok, [tok])
        if any(v in row_cat_norm for v in variants):
            return True

    return False


def _build_searchable_blob(row: sqlite3.Row) -> str:
    """Concatenate and normalize all searchable text fields of a catalog row.

    Why: Allows single-pass accent-insensitive matching across product name, description,
    category name, JSON specs, and translated Portuguese spec attributes.
    """
    specs_dict = parse_specs(row["specs"])
    specs_values = " ".join(f"{k} {v}" for k, v in specs_dict.items())

    # Add Portuguese translations for common English spec values in products.csv
    extra_terms: list[str] = []
    strings_val = str(specs_dict.get("strings", "")).lower()
    if strings_val == "steel":
        extra_terms.extend(["aco", "cordas de aco"])
    elif strings_val == "nylon":
        extra_terms.extend(["nylon", "nailon", "cordas de nylon"])

    elec_val = str(specs_dict.get("electronics", "")).lower()
    if elec_val == "yes":
        extra_terms.extend(["eletrico", "eletroacustico"])
    elif elec_val == "no":
        extra_terms.extend(["acustico"])

    raw_blob = " ".join(
        [
            str(row["product_id"]),
            str(row["name"] or ""),
            str(row["description"] or ""),
            str(row["category_name"] or ""),
            str(row["specs"] or ""),
            specs_values,
            " ".join(extra_terms),
        ]
    )
    return _normalize_text(raw_blob)


def _row_matches_query(row: sqlite3.Row, query_filter: str) -> bool:
    """Evaluate whether a catalog row matches a free-text user query.

    Why: Supports exact model lookups (e.g., 'Takamine GD20', 'Taylor 110e', 'Ibanez Bass 2X',
    'Giannini GF-3D', 'Shelby SN-7C', 'Kala KA-ABP-CTG') as well as multi-term attribute searches.
    """
    q_norm = _normalize_text(query_filter)
    if not q_norm:
        return True

    blob = _build_searchable_blob(row)
    if q_norm in blob:
        return True

    # Tokenize keeping hyphenated model codes and alphanumeric tokens
    raw_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", q_norm)
    tokens = [t for t in raw_tokens if t not in _STOPWORDS]
    if not tokens:
        return True

    for tok in tokens:
        variants = _STEM_ALIASES.get(tok, [tok])
        # Also allow prefix/stem match for plural words ending in 's'
        if len(tok) > 4 and tok.endswith("s"):
            variants = list(set(variants + [tok[:-1]]))
        if not any(v in blob for v in variants):
            return False

    return True


# ---------------------------------------------------------------------------
# Public Agent Tools (Compatible with google-genai Function Declarations)
# ---------------------------------------------------------------------------


def search_catalog(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    only_available: bool = False,
) -> dict[str, Any]:
    """Search the Empório da Música instrument catalog with availability and promotion rules.

    Why: Provides deterministic catalog filtering across `v_product_catalog`, separating
    available products (`status == 'active' and stock_quantity > 0`) from unavailable ones,
    attaching active/expired promotion pricing and up to 3 available alternatives whenever
    an item is unavailable or a category is empty.

    Args:
        query: Free-text search term matching product name, description, category, or specs.
        category: Category name filter (e.g., 'Violões', 'Guitarras', 'Baixos', 'Ukuleles', 'Sopro').
        max_price: Optional maximum price filter in BRL (R$).
        min_price: Optional minimum price filter in BRL (R$).
        only_available: If True, omits unavailable products from `unavailable_products` when available matches exist.

    Returns:
        Dictionary with `available_products`, `unavailable_products`, `suggested_alternatives`,
        `empty_categories`, counts, and explanatory status messages.
    """
    validated = SearchCatalogInput(
        query=query,
        category=category,
        max_price=max_price,
        min_price=min_price,
        only_available=only_available,
    )

    conn = _ensure_db_connection()
    try:
        cur = conn.cursor()
        all_rows = cur.execute(
            "SELECT * FROM v_product_catalog ORDER BY price_brl ASC, product_id ASC;"
        ).fetchall()

        matched_rows: list[sqlite3.Row] = []
        for row in all_rows:
            if validated.category and not _row_matches_category(row, validated.category):
                continue
            if validated.query and not _row_matches_query(row, validated.query):
                continue

            price_val = float(row["price_brl"])
            effective_val = float(row["effective_price_brl"])
            if validated.min_price is not None and max(price_val, effective_val) < validated.min_price:
                continue
            if validated.max_price is not None and min(price_val, effective_val) > validated.max_price:
                continue

            matched_rows.append(row)

        # Fallback for multi-model queries in a single tool call (e.g. "Giannini GF-3D e Shelby SN-7C")
        if not matched_rows and validated.query:
            sub_queries = [
                sq.strip()
                for sq in re.split(r"(?:,|;|\b(?:e|ou|and|or)\b)", validated.query, flags=re.IGNORECASE)
                if sq.strip()
            ]
            if len(sub_queries) > 1:
                seen_row_ids: set[int] = set()
                for sq in sub_queries:
                    for row in all_rows:
                        pid = int(row["product_id"])
                        if pid in seen_row_ids:
                            continue
                        if validated.category and not _row_matches_category(row, validated.category):
                            continue
                        if not _row_matches_query(row, sq):
                            continue
                        price_val = float(row["price_brl"])
                        effective_val = float(row["effective_price_brl"])
                        if validated.min_price is not None and max(price_val, effective_val) < validated.min_price:
                            continue
                        if validated.max_price is not None and min(price_val, effective_val) > validated.max_price:
                            continue
                        seen_row_ids.add(pid)
                        matched_rows.append(row)

        available_products: list[dict[str, Any]] = []
        unavailable_products: list[dict[str, Any]] = []
        top_level_alternatives: list[dict[str, Any]] = []
        seen_alt_ids: set[int] = set()

        for row in matched_rows:
            prod = _format_product_row(row)
            if prod["is_available"]:
                available_products.append(prod)
            else:
                alts = _find_alternatives_for_product(
                    conn=conn,
                    category_id=prod["category_id"],
                    target_price=prod["price_brl"],
                    exclude_product_id=prod["product_id"],
                    limit=3,
                    product_name=prod["name"],
                )
                prod["suggested_alternatives"] = alts
                unavailable_products.append(prod)
                for alt in alts:
                    if alt["product_id"] not in seen_alt_ids and len(top_level_alternatives) < 3:
                        seen_alt_ids.add(alt["product_id"])
                        top_level_alternatives.append(alt)

        empty_categories = _detect_empty_categories(conn, validated.query, validated.category)
        if empty_categories and not available_products and not top_level_alternatives:
            empty_cids = [c["category_id"] for c in empty_categories]
            top_level_alternatives = _find_alternatives_for_empty_category(
                conn=conn,
                empty_category_ids=empty_cids,
                max_price=validated.max_price,
                min_price=validated.min_price,
                limit=3,
            )

        if validated.only_available and available_products:
            returned_unavailable: list[dict[str, Any]] = []
        else:
            returned_unavailable = unavailable_products

        # Determine high-level status and guidance message
        if empty_categories and not available_products and not returned_unavailable:
            cat_names = ", ".join(c["category_name"] for c in empty_categories)
            status_code = "empty_category"
            message = (
                f"Não há produtos disponíveis em estoque para a(s) categoria(s): {cat_names} "
                "(0 produtos cadastrados). Confira até 3 sugestões de instrumentos disponíveis no catálogo."
            )
        elif not available_products and returned_unavailable:
            first_unavail = returned_unavailable[0]
            status_code = first_unavail["availability_status"]
            message = (
                f"O produto '{first_unavail['name']}' encontra-se indisponível "
                f"({first_unavail['availability_label_pt']}). "
                "Foram selecionadas até 3 alternativas disponíveis na mesma categoria e faixa de preço similar."
            )
        elif available_products:
            status_code = "ok"
            message = (
                f"Encontrados {len(available_products)} produto(s) disponível(is)"
                + (
                    f" e {len(returned_unavailable)} produto(s) indisponível(is)."
                    if returned_unavailable
                    else "."
                )
            )
        else:
            status_code = "no_results"
            message = "Nenhum instrumento encontrado com os filtros informados."

        return {
            "status": status_code,
            "message": message,
            "filters_applied": {
                "query": validated.query,
                "category": validated.category,
                "min_price": validated.min_price,
                "max_price": validated.max_price,
                "only_available": validated.only_available,
            },
            "available_count": len(available_products),
            "unavailable_count": len(returned_unavailable),
            "available_products": available_products,
            "unavailable_products": returned_unavailable,
            "empty_categories": empty_categories,
            "suggested_alternatives": top_level_alternatives,
        }
    finally:
        conn.close()


def calculate_payment_options(
    price_brl: float,
    has_active_promotion: bool = False,
) -> dict[str, Any]:
    """Deterministically calculate payment options, PIX discounts, and credit card installments.

    Why: Implements Policy Sections 3, 3.1, and 6.2 without floating-point guesswork by the LLM:
    - PIX: 5% discount (`round(price_brl * 0.95, 2)`) ONLY when `has_active_promotion` is False.
    - Credit Card: 1x to 12x interest-free with tiered minimums (1-3x >= R$ 50, 4-6x >= R$ 80, 7-12x >= R$ 100).
    - Split Payment (PIX + Card): Allowed strictly when `price_brl > 2000.00`.

    Args:
        price_brl: Product or purchase price in Brazilian Reais (R$).
        has_active_promotion: True if the product already has an active promotion (`is_active == 1`).

    Returns:
        Dictionary containing PIX, debit, boleto, valid credit card installment tiers, and split payment eligibility.
    """
    validated = CalculatePaymentInput(
        price_brl=price_brl,
        has_active_promotion=has_active_promotion,
    )
    base_price = round(float(validated.price_brl), 2)
    promo_active = bool(validated.has_active_promotion)

    if promo_active:
        pix_price = base_price
        pix_discount_pct = 0.0
    else:
        pix_price = round(base_price * 0.95, 2)
        pix_discount_pct = 5.0

    pix_discount_amount = round(base_price - pix_price, 2)

    valid_installments: list[dict[str, Any]] = []
    rejected_installments: list[dict[str, Any]] = []

    for n in range(1, 13):
        if n <= 3:
            min_required = 50.0
            tier_label = "1x a 3x (mínimo R$ 50,00/parcela)"
        elif n <= 6:
            min_required = 80.0
            tier_label = "4x a 6x (mínimo R$ 80,00/parcela)"
        else:
            min_required = 100.0
            tier_label = "7x a 12x (mínimo R$ 100,00/parcela)"

        installment_val = round(base_price / n, 2)
        is_valid = (base_price / n) >= min_required or installment_val >= min_required

        entry = {
            "installments": n,
            "installment_value_brl": installment_val,
            "total_brl": base_price,
            "interest_free": True,
            "min_required_brl": min_required,
            "tier": tier_label,
            "valid": is_valid,
            "formatted": f"{n}x de R$ {installment_val:.2f} sem juros",
        }
        if is_valid:
            valid_installments.append(entry)
        else:
            rejected_installments.append(entry)

    max_installments = valid_installments[-1]["installments"] if valid_installments else 1
    max_installment_value = (
        valid_installments[-1]["installment_value_brl"] if valid_installments else base_price
    )
    split_payment_allowed = base_price > 2000.00

    return {
        "price_brl": base_price,
        "base_price_brl": base_price,
        "has_active_promotion": promo_active,
        "pix_price_brl": pix_price,
        "pix_discount_percent": pix_discount_pct,
        "pix": {
            "price_brl": pix_price,
            "discount_percent": pix_discount_pct,
            "discount_amount_brl": pix_discount_amount,
            "is_cumulative_with_promotion": False,
            "notes": (
                "Promoção ativa: o desconto de 5% no PIX não é cumulativo (Seção 6.2)."
                if promo_active
                else "Pagamento à vista via PIX com 5% de desconto sobre o preço de tabela (Seção 3)."
            ),
        },
        "debit_card": {
            "price_brl": base_price,
            "notes": "Pagamento à vista no Cartão de Débito (principais bandeiras aceitas).",
        },
        "boleto": {
            "price_brl": base_price,
            "clearing_business_days": 3,
            "notes": "Pagamento à vista via Boleto Bancário (compensação em até 3 dias úteis).",
        },
        "credit_card": {
            "interest_free": True,
            "max_installments": max_installments,
            "max_installment_value_brl": max_installment_value,
            "summary": (
                f"Até {max_installments}x de R$ {max_installment_value:.2f} sem juros no Cartão de Crédito"
            ),
            "valid_installments": valid_installments,
            "rejected_installments": rejected_installments,
            "tier_minimums_brl": {
                "1x_to_3x": 50.0,
                "4x_to_6x": 80.0,
                "7x_to_12x": 100.0,
            },
        },
        "max_installments": max_installments,
        "valid_installments": valid_installments,
        "installments": valid_installments,
        "split_payment_allowed": split_payment_allowed,
        "split_payment": {
            "allowed": split_payment_allowed,
            "threshold_brl": 2000.00,
            "notes": (
                "Permitida a combinação de formas de pagamento (ex: entrada via PIX + saldo no Cartão em até 12x) "
                "pois o valor supera R$ 2.000,00 (Seção 3.1)."
                if split_payment_allowed
                else "Combinação de formas de pagamento (split payment) não disponível: "
                "permitida exclusivamente para compras acima de R$ 2.000,00 (Seção 3.1)."
            ),
        },
    }


def _verify_customer_match(
    customer_row: sqlite3.Row | dict[str, Any],
    identifier: str,
) -> bool:
    """Check whether `identifier` matches a customer's name, email, or phone.

    Why: Enforces Section 9 (LGPD) identity verification before disclosing order history.
    """
    ident_clean = identifier.strip()
    if not ident_clean:
        return False

    # 1. Email check (case-insensitive exact or embedded email)
    cust_email = str(customer_row["email"]).strip().lower()
    if cust_email and (ident_clean.lower() == cust_email or cust_email in ident_clean.lower()):
        return True

    # 2. Phone check (compare numeric digits, minimum 8 digits to avoid trivial false positives)
    ident_digits = re.sub(r"\D", "", ident_clean)
    cust_digits = re.sub(r"\D", "", str(customer_row["phone"]))
    if len(ident_digits) >= 8 and (
        ident_digits == cust_digits
        or cust_digits.endswith(ident_digits)
        or ident_digits.endswith(cust_digits)
    ):
        return True

    # 3. Name check (accent-insensitive token/substring match, minimum 3 chars)
    ident_norm = _normalize_text(ident_clean)
    cust_name_norm = _normalize_text(str(customer_row["name"]))
    if len(ident_norm) >= 3:
        if ident_norm in cust_name_norm or cust_name_norm in ident_norm:
            return True
        ident_tokens = [t for t in ident_norm.split() if len(t) >= 2]
        cust_tokens = set(cust_name_norm.split())
        if ident_tokens and all(t in cust_tokens for t in ident_tokens):
            return True

    return False


def _parse_iso_date(date_str: Optional[str]) -> Optional[date]:
    """Parse an ISO YYYY-MM-DD date string safely."""
    if not date_str or not str(date_str).strip():
        return None
    try:
        return datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _compute_order_policy_eligibility(
    status: str,
    order_date_str: str,
    estimated_delivery_str: Optional[str],
    reference_date_str: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Calculate exact CDC & store policy windows relative to `reference_date`.

    Why: Precomputes exact calendar deadlines and boolean eligibility for:
    - Right of Regret (Section 4.1): 7 calendar days from receipt (`estimated_delivery`).
    - Preference Exchange (Section 4.3): 7 calendar days from receipt.
    - Defect Exchange with Store (Section 4.2): 30 calendar days from `order_date`.
    - Legal Warranty (Section 8.1): 90 calendar days from receipt.
    """
    ref_dt = _parse_iso_date(reference_date_str) or date(2026, 3, 25)
    order_dt = _parse_iso_date(order_date_str)
    delivery_dt = _parse_iso_date(estimated_delivery_str)

    days_since_order = (ref_dt - order_dt).days if order_dt else None
    days_since_delivery = (ref_dt - delivery_dt).days if delivery_dt else None

    store_defect_deadline = (order_dt + timedelta(days=30)).isoformat() if order_dt else None
    regret_deadline = (delivery_dt + timedelta(days=7)).isoformat() if delivery_dt else None
    preference_deadline = regret_deadline
    legal_warranty_deadline = (delivery_dt + timedelta(days=90)).isoformat() if delivery_dt else None

    if status == "delivered" and delivery_dt is not None and order_dt is not None:
        regret_ok = 0 <= (ref_dt - delivery_dt).days <= 7
        pref_ok = regret_ok
        store_defect_ok = 0 <= (ref_dt - order_dt).days <= 30
        legal_warranty_ok = 0 <= (ref_dt - delivery_dt).days <= 90

        return {
            "reference_date": ref_dt.isoformat(),
            "order_status": status,
            "days_since_order": days_since_order,
            "days_since_delivery": days_since_delivery,
            "right_of_regret": {
                "eligible": regret_ok,
                "window_days": 7,
                "deadline_date": regret_deadline,
                "return_shipping_paid_by_store": True,
                "refund_business_days": 10,
                "explanation": (
                    f"Dentro do prazo de 7 dias corridos após a entrega ({estimated_delivery_str} até {regret_deadline}). "
                    "Frete de devolução custeado pela loja e reembolso em até 10 dias úteis (Seção 4.1)."
                    if regret_ok
                    else f"Prazo de 7 dias corridos para Direito de Arrependimento encerrado em {regret_deadline} "
                    f"(entrega ocorreu em {estimated_delivery_str}, há {days_since_delivery} dias - Seção 4.1)."
                ),
            },
            "preference_exchange": {
                "eligible": pref_ok,
                "window_days": 7,
                "deadline_date": preference_deadline,
                "explanation": (
                    f"Elegível para troca por preferência (cor/modelo/tamanho) até {preference_deadline}, "
                    "desde que lacrado na embalagem original (Seção 4.3)."
                    if pref_ok
                    else f"Prazo de 7 dias corridos para troca por preferência encerrado em {preference_deadline} (Seção 4.3)."
                ),
            },
            "defect_exchange_store": {
                "eligible": store_defect_ok,
                "window_days": 30,
                "deadline_date": store_defect_deadline,
                "manufacturer_intermediation_available": True,
                "explanation": (
                    f"Elegível para troca direta com a loja por defeito de fabricação até {store_defect_deadline} "
                    "(30 dias corridos da compra - Seção 4.2)."
                    if store_defect_ok
                    else f"Prazo de 30 dias corridos da compra ({order_date_str}) para troca direta na loja "
                    f"encerrou em {store_defect_deadline} (há {days_since_order} dias da compra). "
                    "Após 30 dias, o acionamento é via assistência técnica do fabricante, "
                    "podendo a Empório da Música intermediar o processo (Seção 4.2)."
                ),
            },
            "legal_warranty": {
                "eligible": legal_warranty_ok,
                "window_days": 90,
                "deadline_date": legal_warranty_deadline,
                "contractual_manufacturer_warranty_note": (
                    "Garantia contratual do fabricante varia de 6 meses a 2 anos conforme certificado (Seção 8.2)."
                ),
                "explanation": (
                    f"Garantia legal de 90 dias corridos vigente até {legal_warranty_deadline} "
                    "contra defeitos de fabricação (Seção 8.1)."
                    if legal_warranty_ok
                    else f"Garantia legal de 90 dias corridos (CDC) encerrada em {legal_warranty_deadline} "
                    f"({days_since_delivery} dias após a entrega). Verificar cobertura residual da garantia "
                    "contratual do fabricante (6 meses a 2 anos - Seção 8.2)."
                ),
            },
        }

    if status in ("shipped", "confirmed", "pending"):
        store_defect_ok = bool(order_dt and 0 <= (ref_dt - order_dt).days <= 30)
        return {
            "reference_date": ref_dt.isoformat(),
            "order_status": status,
            "days_since_order": days_since_order,
            "days_since_delivery": None,
            "right_of_regret": {
                "eligible": True,
                "window_days": 7,
                "deadline_date": regret_deadline,
                "return_shipping_paid_by_store": True,
                "refund_business_days": 10,
                "explanation": (
                    "O pedido ainda não foi entregue (status atual: "
                    f"'{status}', previsão: {estimated_delivery_str or 'a definir'}). "
                    "O cliente pode solicitar o cancelamento ou exercer o Direito de Arrependimento em até "
                    "7 dias corridos a partir da data efetiva de recebimento do produto, com frete de devolução "
                    "pago pela loja e reembolso em até 10 dias úteis (Seção 4.1)."
                ),
            },
            "preference_exchange": {
                "eligible": True,
                "window_days": 7,
                "deadline_date": preference_deadline,
                "explanation": (
                    "O prazo de 7 dias corridos para troca por preferência passará a contar a partir do "
                    "recebimento do produto na embalagem original (Seção 4.3)."
                ),
            },
            "defect_exchange_store": {
                "eligible": True,
                "window_days": 30,
                "deadline_date": store_defect_deadline,
                "manufacturer_intermediation_available": True,
                "explanation": (
                    f"Troca por defeito de fabricação com a loja é de 30 dias corridos da compra ({order_date_str} "
                    f"até {store_defect_deadline}) e o produto conta com seguro de carga contra avarias no transporte "
                    "(Seções 4.2 e 5.2)."
                    if store_defect_ok
                    else "O produto ainda está em trânsito/processamento; eventuais avarias no transporte "
                    "são cobertas pelo seguro de carga e pela garantia no ato do recebimento (Seções 4.2 e 5.2)."
                ),
            },
            "legal_warranty": {
                "eligible": True,
                "window_days": 90,
                "deadline_date": legal_warranty_deadline,
                "explanation": (
                    "A garantia legal de 90 dias corridos (Seção 8.1) iniciará na data efetiva de entrega do produto."
                ),
            },
        }

    # status == "cancelled" or other non-active order status
    return {
        "reference_date": ref_dt.isoformat(),
        "order_status": status,
        "days_since_order": days_since_order,
        "days_since_delivery": None,
        "right_of_regret": {
            "eligible": False,
            "window_days": 7,
            "deadline_date": None,
            "explanation": f"Pedido cancelado ({notes or 'sem observações adicionais'}). Não aplicável para devolução.",
        },
        "preference_exchange": {
            "eligible": False,
            "window_days": 7,
            "deadline_date": None,
            "explanation": "Pedido cancelado. Não aplicável para troca.",
        },
        "defect_exchange_store": {
            "eligible": False,
            "window_days": 30,
            "deadline_date": None,
            "explanation": "Pedido cancelado. Não aplicável para troca por defeito.",
        },
        "legal_warranty": {
            "eligible": False,
            "window_days": 90,
            "deadline_date": None,
            "explanation": "Pedido cancelado. Garantia não aplicável.",
        },
    }


def _build_order_dict(
    conn: sqlite3.Connection,
    order_row: sqlite3.Row,
    reference_date: str,
) -> dict[str, Any]:
    """Assemble full order record with customer metadata, items, and policy eligibility."""
    cur = conn.cursor()
    oid = int(order_row["order_id"])

    items_rows = cur.execute(
        """
        SELECT
            oi.product_id,
            oi.quantity,
            p.name AS product_name,
            p.price_brl,
            p.status AS product_status,
            c.name AS category_name
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        LEFT JOIN categories c ON p.category_id = c.category_id
        WHERE oi.order_id = ?
        ORDER BY oi.product_id ASC;
        """,
        (oid,),
    ).fetchall()

    items = [
        {
            "product_id": int(r["product_id"]),
            "product_name": str(r["product_name"]),
            "name": str(r["product_name"]),
            "category_name": str(r["category_name"] or ""),
            "quantity": int(r["quantity"]),
            "unit_price_brl": round(float(r["price_brl"]), 2),
            "subtotal_brl": round(float(r["price_brl"]) * int(r["quantity"]), 2),
        }
        for r in items_rows
    ]

    status = str(order_row["status"])
    order_date = str(order_row["order_date"])
    tracking_code = (
        str(order_row["tracking_code"]).strip()
        if order_row["tracking_code"] is not None and str(order_row["tracking_code"]).strip()
        else None
    )
    estimated_delivery = (
        str(order_row["estimated_delivery"]).strip()
        if order_row["estimated_delivery"] is not None
        and str(order_row["estimated_delivery"]).strip()
        else None
    )
    notes = (
        str(order_row["notes"]).strip()
        if order_row["notes"] is not None and str(order_row["notes"]).strip()
        else None
    )

    eligibility = _compute_order_policy_eligibility(
        status=status,
        order_date_str=order_date,
        estimated_delivery_str=estimated_delivery,
        reference_date_str=reference_date,
        notes=notes,
    )

    status_labels_pt = {
        "delivered": "Entregue",
        "shipped": "Enviado / Em trânsito",
        "confirmed": "Confirmado (aguardando envio)",
        "pending": "Pendente de confirmação/pagamento",
        "cancelled": "Cancelado",
    }

    return {
        "verified": True,
        "lgpd_verified": True,
        "order_id": oid,
        "status": status,
        "order_status": status,
        "status_label_pt": status_labels_pt.get(status, status),
        "order_date": order_date,
        "total_brl": round(float(order_row["total_brl"]), 2),
        "payment_method": str(order_row["payment_method"]),
        "tracking_code": tracking_code,
        "estimated_delivery": estimated_delivery,
        "notes": notes,
        "cancellation_reason": notes if status == "cancelled" else None,
        "customer": {
            "customer_id": int(order_row["customer_id"]),
            "name": str(order_row["customer_name"]),
            "email": str(order_row["customer_email"]),
            "phone": str(order_row["customer_phone"]),
            "city": str(order_row["customer_city"]),
        },
        "items": items,
        "ordered_items": items,
        "policy_eligibility": eligibility,
        "regret_eligible": eligibility["right_of_regret"]["eligible"],
        "preference_exchange_eligible": eligibility["preference_exchange"]["eligible"],
        "defect_exchange_store_eligible": eligibility["defect_exchange_store"]["eligible"],
        "legal_warranty_eligible": eligibility["legal_warranty"]["eligible"],
    }


def get_order_status(
    order_id: Optional[int] = None,
    customer_identifier: Optional[str] = None,
    reference_date: str = "2026-03-25",
) -> dict[str, Any]:
    """Retrieve order status, tracking, items, and return/warranty eligibility with LGPD verification.

    Why: Enforces Policy Section 9 (LGPD) by requiring either `order_id` verified against
    `customer_identifier` (name, email, or phone) OR lookup by exact customer email/phone
    before disclosing personal order records, and deterministically computes return/exchange/warranty
    windows relative to `reference_date`.

    Args:
        order_id: Numeric order ID (e.g., 1, 8, 18).
        customer_identifier: Customer name, e-mail, or phone number for LGPD verification.
        reference_date: ISO reference date (YYYY-MM-DD), defaults to '2026-03-25'.

    Returns:
        Dictionary containing LGPD verification status, order metadata, ordered items,
        and precomputed policy eligibility windows.
    """
    validated = GetOrderStatusInput(
        order_id=order_id,
        customer_identifier=customer_identifier,
        reference_date=reference_date,
    )

    ident = (validated.customer_identifier or "").strip()

    # Case 1: Neither order_id nor customer_identifier provided
    if validated.order_id is None and not ident:
        return {
            "status": "lgpd_verification_required",
            "verified": False,
            "lgpd_verified": False,
            "action_required": "ask_customer_verification",
            "message": (
                "Por segurança e em conformidade com a LGPD (Seção 9.2), solicite ao cliente "
                "o número do pedido (order_id) acompanhado do nome completo, e-mail ou telefone "
                "cadastrado (ou informe o e-mail/telefone exato do titular)."
            ),
        }

    # Case 2: Only order_id provided without customer_identifier -> LGPD Guardrail block
    if validated.order_id is not None and not ident:
        return {
            "status": "lgpd_verification_required",
            "verified": False,
            "lgpd_verified": False,
            "order_id": validated.order_id,
            "action_required": "ask_customer_verification",
            "message": (
                f"Para consultar o pedido #{validated.order_id}, em conformidade com a LGPD (Seção 9.2), "
                "solicite ao cliente que confirme seu nome completo, e-mail ou telefone cadastrado."
            ),
        }

    conn = _ensure_db_connection()
    try:
        cur = conn.cursor()

        # Case 3: Both order_id and customer_identifier provided
        if validated.order_id is not None:
            order_row = cur.execute(
                """
                SELECT
                    o.*,
                    c.name AS customer_name,
                    c.email AS customer_email,
                    c.phone AS customer_phone,
                    c.city AS customer_city
                FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = ?;
                """,
                (validated.order_id,),
            ).fetchone()

            if not order_row:
                return {
                    "status": "not_found",
                    "verified": False,
                    "lgpd_verified": False,
                    "order_id": validated.order_id,
                    "message": f"Pedido #{validated.order_id} não foi encontrado no sistema.",
                }

            customer_info = {
                "name": order_row["customer_name"],
                "email": order_row["customer_email"],
                "phone": order_row["customer_phone"],
            }
            if not _verify_customer_match(customer_info, ident):
                return {
                    "status": "lgpd_verification_failed",
                    "verified": False,
                    "lgpd_verified": False,
                    "order_id": validated.order_id,
                    "action_required": "ask_customer_verification",
                    "message": (
                        f"Os dados informados ('{ident}') não conferem com o cadastro do titular do "
                        f"pedido #{validated.order_id}. Por proteção de dados (LGPD - Seção 9.2), "
                        "solicite o nome completo, e-mail ou telefone exato utilizado na compra."
                    ),
                }

            return _build_order_dict(conn, order_row, validated.reference_date)

        # Case 4: Only customer_identifier provided (order_id is None)
        # Allow direct lookup ONLY if identifier is an exact email or exact phone number
        # matching a unique customer with orders; otherwise prompt for order_id / verification.
        ident_lower = ident.lower()
        ident_digits = re.sub(r"\D", "", ident)

        all_customers = cur.execute("SELECT * FROM customers;").fetchall()
        exact_email_or_phone_customers: list[sqlite3.Row] = []

        for c_row in all_customers:
            c_email = str(c_row["email"]).strip().lower()
            c_digits = re.sub(r"\D", "", str(c_row["phone"]))
            if ident_lower == c_email or (len(ident_digits) >= 10 and ident_digits == c_digits):
                exact_email_or_phone_customers.append(c_row)

        if len(exact_email_or_phone_customers) != 1:
            return {
                "status": "lgpd_verification_required",
                "verified": False,
                "lgpd_verified": False,
                "customer_identifier": ident,
                "action_required": "ask_order_id_or_exact_contact",
                "message": (
                    "Para consulta sem o número do pedido, a LGPD (Seção 9.2) exige o e-mail ou "
                    "telefone exato e exclusivo do titular, ou o número do pedido (order_id) "
                    "acompanhado do nome completo."
                ),
            }

        matched_customer = exact_email_or_phone_customers[0]
        order_rows = cur.execute(
            """
            SELECT
                o.*,
                c.name AS customer_name,
                c.email AS customer_email,
                c.phone AS customer_phone,
                c.city AS customer_city
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.customer_id = ?
            ORDER BY o.order_date DESC, o.order_id DESC;
            """,
            (matched_customer["customer_id"],),
        ).fetchall()

        if not order_rows:
            return {
                "status": "no_orders_found",
                "verified": True,
                "lgpd_verified": True,
                "customer": {
                    "customer_id": int(matched_customer["customer_id"]),
                    "name": str(matched_customer["name"]),
                    "email": str(matched_customer["email"]),
                    "phone": str(matched_customer["phone"]),
                    "city": str(matched_customer["city"]),
                },
                "orders": [],
                "message": f"Nenhum pedido encontrado para o cliente {matched_customer['name']}.",
            }

        built_orders = [_build_order_dict(conn, r, validated.reference_date) for r in order_rows]
        primary_order = dict(built_orders[0])
        primary_order["orders"] = built_orders
        primary_order["total_orders_found"] = len(built_orders)
        return primary_order
    finally:
        conn.close()


_TOPIC_SECTION_MAP: dict[str, list[int]] = {
    # Section 1 & 7: Store identity, address, contacts, scope & accessories restriction
    "endereco": [1, 2],
    "localizacao": [1, 2],
    "rua": [1],
    "cep": [1],
    "cnpj": [1],
    "sobre": [1],
    "historia": [1],
    "missao": [1],
    "contato": [1, 7],
    "telefone": [1, 7],
    "telefones": [1, 7],
    "numero": [1, 7],
    "whatsapp": [1, 7],
    "email": [1, 7],
    "atendimento": [2, 7],
    "suporte": [1, 7],
    "escopo": [1, 7],
    "acessorio": [1, 7],
    "acessorios": [1, 7],
    "corda": [1, 7],
    "cordas": [1, 7],
    "encordoamento": [1, 7],
    "palheta": [1, 7],
    "palhetas": [1, 7],
    "cabo": [1, 7],
    "cabos": [1, 7],
    "case": [1, 7],
    "cases": [1, 7],
    "capa": [1, 7],
    "bag": [1, 7],
    "pedal": [1, 7],
    "pedais": [1, 7],
    "amplificador": [1, 7],
    "amplificadores": [1, 7],
    "cubo": [1, 7],
    "baqueta": [1, 7],
    "baquetas": [1, 7],
    "correia": [1, 7],
    # Section 2: Opening hours
    "horario": [2, 1],
    "horarios": [2, 1],
    "funcionamento": [2, 1],
    "expediente": [2],
    "aberto": [2],
    "fechado": [2],
    "sabado": [2],
    "domingo": [2],
    "feriado": [2],
    "feriados": [2],
    # Section 3 & 6: Payments, installments, PIX, promotions
    "pagamento": [3, 6],
    "pagamentos": [3, 6],
    "parcelamento": [3],
    "parcela": [3],
    "parcelas": [3],
    "pix": [3, 6],
    "cartao": [3],
    "credito": [3],
    "debito": [3],
    "boleto": [3],
    "juros": [3],
    "split": [3],
    "combinacao": [3],
    # Section 4 & 8: Returns, exchanges, regret, defects, non-eligible items
    "troca": [4, 8],
    "trocas": [4, 8],
    "devolucao": [4],
    "devolucoes": [4],
    "arrependimento": [4],
    "defeito": [4, 8],
    "reembolso": [4],
    "estorno": [4],
    "boquilha": [4],
    "boquilhas": [4],
    "luthieria": [4, 8],
    "personalizacao": [4],
    # Section 5: Shipping, freight, Campo Grande, carriers
    "frete": [5],
    "entrega": [5],
    "entregas": [5],
    "envio": [5],
    "correios": [5],
    "pac": [5],
    "sedex": [5],
    "jadlog": [5],
    "motoboy": [5],
    "rastreamento": [5],
    "rastreio": [5],
    "prazo": [4, 5],
    # Section 6: Promotions and non-cumulativity
    "promocao": [6, 3, 7],
    "promocoes": [6, 3, 7],
    "desconto": [6, 3],
    "descontos": [6, 3],
    "cumulativo": [6, 3],
    "black friday": [6, 2],
    "aniversario": [6, 2],
    # Section 8: Warranty
    "garantia": [8, 4],
    "garantias": [8, 4],
    "cdc": [4, 8],
    "fabricante": [4, 8],
    "assistencia": [4, 8],
    # Section 9: LGPD
    "lgpd": [9],
    "privacidade": [9],
    "dados": [9],
    "seguranca": [9],
    "sigilo": [9],
    "cpf": [9],
    # Section 10: Final provisions
    "disposicoes": [10],
    "versao": [10],
}


def consult_store_policies(topic: str) -> dict[str, Any]:
    """Retrieve relevant store policy sections from `src/policies_kb.py` matching `topic`.

    Why: Provides grounded policy sections (address, dual phone numbers, payment/installments,
    returns/regret, freight SLAs, promotions, warranty, LGPD, and strict instrument-only scope)
    with a full-manual fallback when a query spans multiple topics or is broad.

    Args:
        topic: Topic keyword or question (e.g., 'endereco', 'horario', 'pagamento', 'troca',
            'devolucao', 'arrependimento', 'frete', 'promocao', 'whatsapp', 'garantia',
            'lgpd', 'acessorios', 'escopo').

    Returns:
        Dictionary with matched policy sections, combined Markdown text, explicit contact
        numbers, and scope restriction notes.
    """
    norm_topic = _normalize_text(topic)
    all_policies = get_all_policies()

    matched_section_ids: list[int] = []

    if norm_topic:
        # Check direct multi-word and single-token mappings
        for key, sec_ids in _TOPIC_SECTION_MAP.items():
            if key in norm_topic:
                for sid in sec_ids:
                    if sid not in matched_section_ids:
                        matched_section_ids.append(sid)

        tokens = re.findall(r"[a-z0-9]+", norm_topic)
        for tok in tokens:
            for key, sec_ids in _TOPIC_SECTION_MAP.items():
                if tok == key or (len(tok) > 4 and tok.rstrip("s") == key.rstrip("s")):
                    for sid in sec_ids:
                        if sid not in matched_section_ids:
                            matched_section_ids.append(sid)

        # Also incorporate results from policies_kb.search_policies (with both raw and normalized query)
        for q_variant in {topic, norm_topic}:
            for hit in search_policies(q_variant):
                sid = int(hit["section_id"])
                if sid not in matched_section_ids:
                    matched_section_ids.append(sid)

    # Full-manual fallback if query is broad, spans >= 5 sections, or had no specific match
    full_manual_triggers = {"tudo", "todas", "completo", "manual", "geral", "politicas", "regras"}
    tokens_set = set(re.findall(r"[a-z0-9]+", norm_topic))
    used_full_fallback = False

    if (
        not matched_section_ids
        or len(matched_section_ids) >= 5
        or bool(tokens_set & full_manual_triggers and len(tokens_set) <= 2)
    ):
        matched_section_ids = list(all_policies.keys())
        used_full_fallback = True

    sections_payload = [
        {
            "section_id": sid,
            "title": all_policies[sid]["title"],
            "content_markdown": all_policies[sid]["content_markdown"],
        }
        for sid in matched_section_ids
    ]

    combined_markdown = "\n\n".join(s["content_markdown"] for s in sections_payload)
    contacts = get_contact_info()

    return {
        "topic": topic,
        "section_ids": matched_section_ids,
        "matched_sections": sections_payload,
        "combined_markdown": combined_markdown,
        "used_full_manual_fallback": used_full_fallback,
        "contact_info": contacts,
        "scope_restriction": {
            "sells_only_musical_instruments": True,
            "prohibited_accessories": [
                "cordas avulsas / encordoamentos",
                "palhetas",
                "cabos",
                "cases / capas / bags",
                "pedais de efeito",
                "amplificadores / cubos",
            ],
            "guidance": (
                "A Empório da Música trabalha exclusivamente com instrumentos musicais (Seções 1 e 7.1). "
                "Não comercializamos acessórios avulsos; oriente educadamente o cliente a procurar lojas parceiras."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Tool Registry & Dispatcher for Manual ReAct Loop
# ---------------------------------------------------------------------------

AGENT_TOOLS: list[Callable[..., dict[str, Any]]] = [
    search_catalog,
    calculate_payment_options,
    get_order_status,
    consult_store_policies,
]

TOOL_REGISTRY: dict[str, Callable[..., dict[str, Any]]] = {
    func.__name__: func for func in AGENT_TOOLS
}


def execute_tool_call(tool_name: str, tool_args: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Execute a registered agent tool deterministically by name and arguments.

    Why: Centralizes error handling for manual ReAct tool execution in `src/agent.py`
    so invalid tool names or bad arguments return structured JSON rather than crashing.
    """
    func = TOOL_REGISTRY.get(tool_name)
    if func is None:
        return {
            "status": "error",
            "error": f"Ferramenta desconhecida: '{tool_name}'. Ferramentas válidas: {list(TOOL_REGISTRY.keys())}",
        }
    try:
        kwargs = tool_args or {}
        return func(**kwargs)
    except Exception as exc:
        logger.error("Error executing tool %s with args %s: %s", tool_name, tool_args, exc)
        return {
            "status": "error",
            "tool": tool_name,
            "error": str(exc),
        }
