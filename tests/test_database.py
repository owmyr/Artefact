"""Unit tests for SQLite database schema, ingestion layer, and catalog views.

Why: Enforces that all availability rules, discount non-cumulativity, and deduplication
behave deterministically across edge-case products before agent tools are wired up.
"""

from __future__ import annotations

import json
import sqlite3
import pytest

from src.database import (
    get_connection,
    init_database,
    parse_specs,
)


@pytest.fixture(scope="module")
def db_conn():
    """Create an in-memory SQLite database populated with data from CSVs."""
    conn = init_database(db_path=":memory:", force_reload=True)
    yield conn
    conn.close()


def test_schema_and_row_counts(db_conn: sqlite3.Connection):
    """Verify that all core tables were created and populated with expected row counts."""
    cur = db_conn.cursor()
    tables = {
        "categories": 9,
        "customers": 50,
        "products": 65,
        "orders": 20,
        "order_items": 22,
        "promotions": 25,
    }
    for tbl, expected_count in tables.items():
        actual = cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        assert actual == expected_count, f"Table {tbl} expected {expected_count} rows, got {actual}"


def test_v_product_catalog_deduplication(db_conn: sqlite3.Connection):
    """Verify that v_product_catalog has exactly 65 rows (1 row per product_id)."""
    cur = db_conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM v_product_catalog").fetchone()[0]
    distinct = cur.execute("SELECT COUNT(DISTINCT product_id) FROM v_product_catalog").fetchone()[0]
    assert total == 65, f"Expected 65 rows in view, got {total}"
    assert distinct == 65, f"Expected 65 distinct product_ids in view, got {distinct}"


def test_violoes_under_1000_count(db_conn: sqlite3.Connection):
    """Verify that available Violões (category_id=5) <= R$ 1,000 equals exactly 12 items."""
    cur = db_conn.cursor()
    rows = cur.execute(
        """
        SELECT product_id, name, price_brl
        FROM v_product_catalog
        WHERE category_id = 5 AND price_brl <= 1000 AND is_available = 1
        """
    ).fetchall()
    assert len(rows) == 12, f"Expected 12 available violões <= R$ 1,000, got {len(rows)}"


def test_product_availability_flags(db_conn: sqlite3.Connection):
    """Verify specific edge-case products for availability flags."""
    cur = db_conn.cursor()

    # Product 96: active, but stock_quantity = 0 -> is_available = 0
    p96 = cur.execute(
        "SELECT status, stock_quantity, is_available FROM v_product_catalog WHERE product_id = 96"
    ).fetchone()
    assert p96["status"] == "active"
    assert p96["stock_quantity"] == 0
    assert p96["is_available"] == 0

    # Product 113: discontinued, stock_quantity = 0 -> is_available = 0
    p113 = cur.execute(
        "SELECT status, stock_quantity, is_available FROM v_product_catalog WHERE product_id = 113"
    ).fetchone()
    assert p113["status"] == "discontinued"
    assert p113["stock_quantity"] == 0
    assert p113["is_available"] == 0

    # Product 136: discontinued, but stock_quantity = 13 -> is_available = 0
    p136 = cur.execute(
        "SELECT status, stock_quantity, is_available FROM v_product_catalog WHERE product_id = 136"
    ).fetchone()
    assert p136["status"] == "discontinued"
    assert p136["stock_quantity"] == 13
    assert p136["is_available"] == 0

    # Product 130: coming_soon, stock_quantity = 2 -> is_available = 0
    p130 = cur.execute(
        "SELECT status, stock_quantity, is_available FROM v_product_catalog WHERE product_id = 130"
    ).fetchone()
    assert p130["status"] == "coming_soon"
    assert p130["stock_quantity"] == 2
    assert p130["is_available"] == 0

    # Available product (e.g. 81 Yamaha C40)
    p81 = cur.execute(
        "SELECT status, stock_quantity, is_available FROM v_product_catalog WHERE product_id = 81"
    ).fetchone()
    assert p81["status"] == "active"
    assert p81["stock_quantity"] > 0
    assert p81["is_available"] == 1


def test_active_promotions_and_pix_non_cumulativity(db_conn: sqlite3.Connection):
    """Verify that exactly 4 products have active promotions and 5% PIX does not stack."""
    cur = db_conn.cursor()
    active_promos = cur.execute(
        """
        SELECT product_id, price_brl, active_discount_percent, effective_price_brl, pix_price_brl
        FROM v_product_catalog
        WHERE active_discount_percent IS NOT NULL
        """
    ).fetchall()

    assert len(active_promos) == 4
    active_ids = {r["product_id"] for r in active_promos}
    assert active_ids == {90, 94, 121, 127}

    for p in active_promos:
        expected_effective = round(p["price_brl"] * (1.0 - p["active_discount_percent"] / 100.0), 2)
        assert p["effective_price_brl"] == expected_effective
        # Active promo means 5% PIX does not stack: pix_price_brl == effective_price_brl
        assert p["pix_price_brl"] == p["effective_price_brl"]


def test_expired_promotions_pricing(db_conn: sqlite3.Connection):
    """Verify that expired promotions revert to table price with 5% PIX discount."""
    cur = db_conn.cursor()
    p95 = cur.execute(
        """
        SELECT product_id, price_brl, active_discount_percent, expired_discount_percent,
               effective_price_brl, pix_price_brl
        FROM v_product_catalog
        WHERE product_id = 95
        """
    ).fetchone()

    assert p95["active_discount_percent"] is None
    assert p95["expired_discount_percent"] == 12.0
    assert p95["effective_price_brl"] == 2199.0
    expected_pix = round(2199.0 * 0.95, 2)  # 2089.05
    assert p95["pix_price_brl"] == expected_pix


def test_duplicate_promotions_handling(db_conn: sqlite3.Connection):
    """Verify that products with duplicate promotion rows appear only once in the catalog."""
    cur = db_conn.cursor()
    for pid in [93, 96, 99]:
        rows = cur.execute(
            "SELECT COUNT(*) FROM v_product_catalog WHERE product_id = ?", (pid,)
        ).fetchone()[0]
        assert rows == 1, f"Product {pid} appeared {rows} times in view instead of exactly 1"


def test_parse_specs_helper():
    """Verify defensive handling in parse_specs helper."""
    assert parse_specs(None) == {}
    assert parse_specs("") == {}
    assert parse_specs("invalid json") == {}
    assert parse_specs('{"top": "Spruce", "strings": "nylon"}') == {
        "top": "Spruce",
        "strings": "nylon",
    }
    assert parse_specs('["not", "a", "dict"]') == {}


def test_chat_history_table(db_conn: sqlite3.Connection):
    """Verify chat_history table operations."""
    cur = db_conn.cursor()
    cur.execute(
        """
        INSERT INTO chat_history (session_id, turn_index, role, content_json, model_used)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("sess_123", 0, "user", json.dumps({"text": "Olá"}), "gemini-2.5-flash"),
    )
    db_conn.commit()

    row = cur.execute(
        "SELECT * FROM chat_history WHERE session_id = ? AND turn_index = ?",
        ("sess_123", 0),
    ).fetchone()
    assert row is not None
    assert row["role"] == "user"
    assert json.loads(row["content_json"])["text"] == "Olá"
    assert row["model_used"] == "gemini-2.5-flash"
