"""SQLite ingestion layer, schema definitions, and catalog view for Empório da Música.

Why: Provides a fast, deterministic, relational persistence layer for store
inventory, customer orders, and promotion metadata. Guarantees that agent
reasoning is grounded in validated SQL views with business rules precomputed.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import (
    CATEGORIES_CSV,
    CUSTOMERS_CSV,
    DB_PATH,
    ORDER_ITEMS_CSV,
    ORDERS_CSV,
    PRODUCTS_CSV,
    PROMOTIONS_CSV,
)

logger = logging.getLogger(__name__)


def parse_specs(specs_str: str | None) -> dict[str, Any]:
    """Safely parse a product specifications JSON string into a Python dictionary.

    Why: Protects against corrupted or missing JSON fields in product records,
    ensuring downstream filters and agent tools receive well-formed dicts.
    """
    if not specs_str or not isinstance(specs_str, str):
        return {}
    try:
        data = json.loads(specs_str)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Create and return a configured SQLite connection with row factories enabled.

    Why: Enables dictionary-style column access and activates foreign key constraints
    at the session level to preserve referential integrity.
    """
    path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create relational tables and indexes required by the Empório da Música store.

    Why: Establishes strong types, primary keys, and foreign keys before ingesting
    CSV data, ensuring data integrity across orders, products, and promotions.
    """
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            city TEXT NOT NULL
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            price_brl REAL NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            description TEXT,
            stock_quantity INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL,
            specs TEXT,
            created_at TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (category_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL,
            total_brl REAL NOT NULL,
            payment_method TEXT NOT NULL,
            tracking_code TEXT,
            estimated_delivery TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (customer_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS order_items (
            order_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            product_id INTEGER NOT NULL,
            PRIMARY KEY (order_id, product_id),
            FOREIGN KEY (order_id) REFERENCES orders (order_id),
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS promotions (
            promotion_id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            discount_percent REAL NOT NULL,
            description TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        );
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            turn_index INTEGER NOT NULL,
            role TEXT NOT NULL,
            content_json TEXT NOT NULL,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # Performance and query optimization indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_products_status_stock ON products(status, stock_quantity);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_promotions_product ON promotions(product_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_promotions_active ON promotions(is_active);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history(session_id, turn_index);")

    conn.commit()


def create_views(conn: sqlite3.Connection) -> None:
    """Create the deduplicated v_product_catalog view.

    Why: Encapsulates all business rules regarding product availability, active/expired
    promotions, price calculations, and PIX discounts into a single relational view
    so the LLM agent does not need to perform manual arithmetic or filtering.
    """
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS v_product_catalog;")

    view_sql = """
    CREATE VIEW v_product_catalog AS
    WITH active_promos AS (
        SELECT
            product_id,
            discount_percent,
            description,
            ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY promotion_id DESC) as rn
        FROM promotions
        WHERE is_active = 1
    ),
    expired_promos AS (
        SELECT
            product_id,
            discount_percent,
            description,
            ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY promotion_id DESC) as rn
        FROM promotions
        WHERE is_active = 0
          AND product_id NOT IN (SELECT product_id FROM promotions WHERE is_active = 1)
    )
    SELECT
        p.product_id,
        p.name,
        p.category_id,
        c.name AS category_name,
        p.price_brl,
        p.description,
        p.stock_quantity,
        p.status,
        p.specs,
        p.created_at,
        CASE
            WHEN p.status = 'active' AND p.stock_quantity > 0 THEN 1
            ELSE 0
        END AS is_available,
        ap.discount_percent AS active_discount_percent,
        ap.description AS active_promo_description,
        ep.discount_percent AS expired_discount_percent,
        ep.description AS expired_promo_description,
        CASE
            WHEN ap.discount_percent IS NOT NULL AND (p.status = 'active' AND p.stock_quantity > 0)
            THEN ROUND(p.price_brl * (1.0 - ap.discount_percent / 100.0), 2)
            ELSE p.price_brl
        END AS effective_price_brl,
        CASE
            WHEN ap.discount_percent IS NOT NULL AND ap.discount_percent > 0
            THEN (
                CASE
                    WHEN (p.status = 'active' AND p.stock_quantity > 0)
                    THEN ROUND(p.price_brl * (1.0 - ap.discount_percent / 100.0), 2)
                    ELSE p.price_brl
                END
            )
            ELSE ROUND(p.price_brl * 0.95, 2)
        END AS pix_price_brl,
        json_extract(p.specs, '$.top') AS spec_top,
        json_extract(p.specs, '$.back_sides') AS spec_back_sides,
        json_extract(p.specs, '$.neck') AS spec_neck,
        json_extract(p.specs, '$.strings') AS spec_strings,
        json_extract(p.specs, '$.scale') AS spec_scale,
        json_extract(p.specs, '$.electronics') AS spec_electronics,
        json_extract(p.specs, '$.color') AS spec_color,
        json_extract(p.specs, '$.body') AS spec_body,
        json_extract(p.specs, '$.type') AS spec_type
    FROM products p
    LEFT JOIN categories c ON p.category_id = c.category_id
    LEFT JOIN active_promos ap ON p.product_id = ap.product_id AND ap.rn = 1
    LEFT JOIN expired_promos ep ON p.product_id = ep.product_id AND ep.rn = 1;
    """

    cur.execute(view_sql)
    conn.commit()


def ingest_csv_data(conn: sqlite3.Connection, force: bool = False) -> None:
    """Ingest CSV files from data/ into their corresponding SQLite tables.

    Why: Loads raw seed files into relational tables while populating foreign
    keys cleanly. Uses REPLACE/INSERT logic guarded by row counts so restarts are idempotent.
    """
    cur = conn.cursor()

    # Ingest categories
    if force or cur.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        if CATEGORIES_CSV.exists():
            df_cat = pd.read_csv(CATEGORIES_CSV)
            df_cat.to_sql("categories", conn, if_exists="append", index=False)

    # Ingest customers
    if force or cur.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0:
        if CUSTOMERS_CSV.exists():
            df_cust = pd.read_csv(CUSTOMERS_CSV)
            df_cust.to_sql("customers", conn, if_exists="append", index=False)

    # Ingest products
    if force or cur.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
        if PRODUCTS_CSV.exists():
            df_prod = pd.read_csv(PRODUCTS_CSV)
            df_prod.to_sql("products", conn, if_exists="append", index=False)

    # Ingest orders
    if force or cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
        if ORDERS_CSV.exists():
            df_orders = pd.read_csv(ORDERS_CSV)
            df_orders.to_sql("orders", conn, if_exists="append", index=False)

    # Ingest order items
    if force or cur.execute("SELECT COUNT(*) FROM order_items").fetchone()[0] == 0:
        if ORDER_ITEMS_CSV.exists():
            df_items = pd.read_csv(ORDER_ITEMS_CSV)
            df_items.to_sql("order_items", conn, if_exists="append", index=False)

    # Ingest promotions
    if force or cur.execute("SELECT COUNT(*) FROM promotions").fetchone()[0] == 0:
        if PROMOTIONS_CSV.exists():
            df_promos = pd.read_csv(PROMOTIONS_CSV)
            df_promos.to_sql("promotions", conn, if_exists="append", index=False)

    conn.commit()


def init_database(db_path: Path | str | None = None, force_reload: bool = False) -> sqlite3.Connection:
    """Initialize SQLite database with schema, data ingestion, and business views.

    Why: Single entrypoint to ensure database schema, seed data, and analytical views
    are completely ready before any agent operation begins.
    """
    conn = get_connection(db_path)
    if force_reload:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = OFF;")
        cur.execute("DROP VIEW IF EXISTS v_product_catalog;")
        for tbl in ["order_items", "orders", "promotions", "products", "customers", "categories", "chat_history"]:
            cur.execute(f"DROP TABLE IF EXISTS {tbl};")
        cur.execute("PRAGMA foreign_keys = ON;")
        conn.commit()

    create_schema(conn)
    ingest_csv_data(conn, force=force_reload)
    create_views(conn)
    return conn


if __name__ == "__main__":
    print("Initializing database...")
    db = init_database(force_reload=True)
    cur = db.cursor()

    # Verification 1: Total products in v_product_catalog == 65
    total_count = cur.execute("SELECT COUNT(*) FROM v_product_catalog").fetchone()[0]
    print(f"1. Total products in v_product_catalog: {total_count} (Expected: 65)")
    assert total_count == 65, f"Expected 65 products, got {total_count}"

    # Verification 2: Available Violões (category_id = 5) with price_brl <= 1000 and is_available = 1 == 12 items
    violoes = cur.execute(
        """
        SELECT product_id, name, price_brl, is_available
        FROM v_product_catalog
        WHERE category_id = 5 AND price_brl <= 1000 AND is_available = 1
        ORDER BY price_brl ASC;
        """
    ).fetchall()
    print(f"2. Available Violões <= R$ 1.000: {len(violoes)} (Expected: 12)")
    for v in violoes:
        print(f"   - [ID {v['product_id']}] {v['name']}: R$ {v['price_brl']:.2f} (available: {v['is_available']})")
    assert len(violoes) == 12, f"Expected 12 violões, got {len(violoes)}"

    # Check excluded items (96 and 113)
    excluded = cur.execute(
        """
        SELECT product_id, name, price_brl, status, stock_quantity, is_available
        FROM v_product_catalog
        WHERE product_id IN (96, 113);
        """
    ).fetchall()
    print("   Excluded items check (Stock=0 or Discontinued):")
    for ex in excluded:
        print(f"   - [ID {ex['product_id']}] {ex['name']}: status={ex['status']}, stock={ex['stock_quantity']}, is_available={ex['is_available']}")
        assert ex["is_available"] == 0, f"Product {ex['product_id']} should have is_available=0"

    # Verification 3: Active promotions == 4 items (product_id 90, 94, 121, 127)
    active_promos = cur.execute(
        """
        SELECT product_id, name, price_brl, active_discount_percent, effective_price_brl, pix_price_brl
        FROM v_product_catalog
        WHERE active_discount_percent IS NOT NULL
        ORDER BY product_id ASC;
        """
    ).fetchall()
    print(f"3. Active promotions: {len(active_promos)} (Expected: 4)")
    for ap in active_promos:
        print(
            f"   - [ID {ap['product_id']}] {ap['name']}: R$ {ap['price_brl']:.2f} -> "
            f"Discount {ap['active_discount_percent']}% -> Promo: R$ {ap['effective_price_brl']:.2f} "
            f"(PIX: R$ {ap['pix_price_brl']:.2f})"
        )
    active_ids = {p["product_id"] for p in active_promos}
    assert len(active_promos) == 4, f"Expected 4 active promotions, got {len(active_promos)}"
    assert active_ids == {90, 94, 121, 127}, f"Unexpected active promo IDs: {active_ids}"

    # Verification 4: Expired promotion check on Product 95 (Takamine GD20)
    p95 = cur.execute(
        """
        SELECT product_id, name, price_brl, active_discount_percent, expired_discount_percent, effective_price_brl, pix_price_brl
        FROM v_product_catalog
        WHERE product_id = 95;
        """
    ).fetchone()
    print(
        f"4. Expired promo check (ID 95): {p95['name']} | Table Price: R$ {p95['price_brl']:.2f} | "
        f"Active Promo: {p95['active_discount_percent']} | Expired Promo: {p95['expired_discount_percent']}% | "
        f"Effective: R$ {p95['effective_price_brl']:.2f} | PIX: R$ {p95['pix_price_brl']:.2f}"
    )
    assert p95["active_discount_percent"] is None
    assert p95["expired_discount_percent"] == 12.0
    assert p95["effective_price_brl"] == 2199.0
    assert p95["pix_price_brl"] == 2089.05

    print("\nAll database verifications passed successfully!")
    db.close()
