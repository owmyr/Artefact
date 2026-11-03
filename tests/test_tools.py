"""Unit tests for Empório da Música deterministic agent tools (src/tools.py).

Why: Validates all mandatory business logic rules from AGENTS.md Section 4:
- Catalog availability filtering, out-of-stock/discontinued/coming-soon handling,
  empty category detection, and up to 3 suggested alternatives.
- Active vs. expired promotions and 5% PIX discount non-cumulativity.
- Credit card installment tier thresholds (R$ 50 / R$ 80 / R$ 100) and split payments (> R$ 2,000).
- LGPD identity verification guardrails and CDC return/exchange/warranty date calculations.
- Store policy lookup for address, dual phone numbers, freight rules, and accessory scope restrictions.
"""

from __future__ import annotations

import pytest

from src.tools import (
    AGENT_TOOLS,
    calculate_payment_options,
    consult_store_policies,
    execute_tool_call,
    get_order_status,
    search_catalog,
)


# ---------------------------------------------------------------------------
# 1. Catalog Search Tests (Availability, Promotions, Empty Categories)
# ---------------------------------------------------------------------------


def test_search_catalog_violoes_up_to_1000():
    """Verify Violões <= R$ 1000 returns 12 available items and marks 96 and 113 unavailable with alternatives."""
    result = search_catalog(category="Violões", max_price=1000.0)

    assert result["status"] == "ok"
    assert result["available_count"] == 12
    assert len(result["available_products"]) == 12

    # Ensure all available items are active, in stock, in category 5, and <= R$ 1000
    available_ids = {p["product_id"] for p in result["available_products"]}
    assert 96 not in available_ids
    assert 113 not in available_ids
    for prod in result["available_products"]:
        assert prod["is_available"] is True
        assert prod["status"] == "active"
        assert prod["stock_quantity"] > 0
        assert prod["category_id"] == 5
        assert prod["price_brl"] <= 1000.0

    # Verify unavailable products include product_id=96 (out_of_stock) and product_id=113 (discontinued)
    unavail_by_id = {p["product_id"]: p for p in result["unavailable_products"]}
    assert 96 in unavail_by_id
    assert 113 in unavail_by_id

    p96 = unavail_by_id[96]
    assert p96["name"] == "Giannini GF-3D Dreadnought Sunburst"
    assert p96["status"] == "active"
    assert p96["stock_quantity"] == 0
    assert p96["is_available"] is False
    assert p96["availability_status"] == "out_of_stock"
    assert 1 <= len(p96["suggested_alternatives"]) <= 3
    for alt in p96["suggested_alternatives"]:
        assert alt["is_available"] is True
        assert alt["category_id"] == 5

    p113 = unavail_by_id[113]
    assert p113["name"] == "Shelby SN-7C 7 Cordas Nylon Natural"
    assert p113["status"] == "discontinued"
    assert p113["is_available"] is False
    assert p113["availability_status"] == "discontinued"
    assert 1 <= len(p113["suggested_alternatives"]) <= 3
    for alt in p113["suggested_alternatives"]:
        assert alt["is_available"] is True
        assert alt["category_id"] == 5


def test_search_catalog_takamine_gd20_expired_promotion():
    """Verify Takamine GD20 (ID 95) reports expired 12% promo, R$ 2,199.00 table, and R$ 2,089.05 PIX."""
    result = search_catalog(query="Takamine GD20")

    assert len(result["available_products"]) == 1
    p95 = result["available_products"][0]

    assert p95["product_id"] == 95
    assert p95["name"] == "Takamine GD20 Dreadnought Natural"
    assert p95["price_brl"] == 2199.00
    assert p95["has_active_promotion"] is False
    assert p95["active_discount_percent"] is None
    assert p95["effective_price_brl"] == 2199.00
    assert p95["pix_price_brl"] == 2089.05

    exp_info = p95["expired_promotion_info"]
    assert exp_info is not None
    assert exp_info["is_active"] == 0
    assert exp_info["expired_discount_percent"] == 12.0
    assert exp_info["description"] == "Oferta Especial"
    assert exp_info["table_price_brl"] == 2199.00
    assert exp_info["pix_price_brl"] == 2089.05


def test_search_catalog_taylor_110e_active_promotion_no_pix_stacking():
    """Verify Taylor 110e (ID 94) reports active 8% promo, R$ 5,519.08 promo price, and no extra PIX discount."""
    result = search_catalog(query="Taylor 110e")

    assert len(result["available_products"]) == 1
    p94 = result["available_products"][0]

    assert p94["product_id"] == 94
    assert p94["name"] == "Taylor 110e Dreadnought Natural"
    assert p94["price_brl"] == 5999.00
    assert p94["has_active_promotion"] is True
    assert p94["active_discount_percent"] == 8.0
    assert p94["effective_price_brl"] == 5519.08
    # Non-cumulative rule: PIX price equals promotional price (no extra 5% off)
    assert p94["pix_price_brl"] == 5519.08
    assert p94["expired_promotion_info"] is None


def test_search_catalog_empty_category_sopro_and_discontinued_ibanez():
    """Verify empty category Sopro (Categories 6 & 7) and discontinued Ibanez Bass 2X (ID 136)."""
    # 1. Empty category Sopro (Categories 6 and 7)
    sopro_res = search_catalog(category="Sopro")
    assert sopro_res["status"] == "empty_category"
    assert sopro_res["available_count"] == 0
    empty_cat_ids = {c["category_id"] for c in sopro_res["empty_categories"]}
    assert {6, 7}.issubset(empty_cat_ids)
    assert 1 <= len(sopro_res["suggested_alternatives"]) <= 3
    for alt in sopro_res["suggested_alternatives"]:
        assert alt["is_available"] is True

    # 2. Discontinued Ibanez Bass 2X (product_id=136, stock_quantity=13 but status='discontinued')
    ibanez_res = search_catalog(query="Ibanez Bass 2X")
    assert ibanez_res["available_count"] == 0
    assert len(ibanez_res["unavailable_products"]) == 1

    p136 = ibanez_res["unavailable_products"][0]
    assert p136["product_id"] == 136
    assert p136["status"] == "discontinued"
    assert p136["stock_quantity"] == 13
    assert p136["is_available"] is False
    assert p136["availability_status"] == "discontinued"

    # Must suggest up to 3 available alternatives from Baixos (category_id=2)
    assert 1 <= len(p136["suggested_alternatives"]) <= 3
    assert 1 <= len(ibanez_res["suggested_alternatives"]) <= 3
    for alt in p136["suggested_alternatives"]:
        assert alt["is_available"] is True
        assert alt["category_id"] == 2
        assert alt["product_id"] != 136


def test_search_catalog_coming_soon_kala_baritono():
    """Verify coming_soon product Kala KA-ABP-CTG (ID 130) is unavailable and returns Ukulele alternatives."""
    res = search_catalog(query="Kala KA-ABP-CTG")
    assert res["available_count"] == 0
    assert len(res["unavailable_products"]) == 1

    p130 = res["unavailable_products"][0]
    assert p130["product_id"] == 130
    assert p130["status"] == "coming_soon"
    assert p130["availability_status"] == "coming_soon"
    assert p130["is_available"] is False
    assert len(p130["suggested_alternatives"]) == 3
    for alt in p130["suggested_alternatives"]:
        assert alt["is_available"] is True
        assert alt["category_id"] == 9


# ---------------------------------------------------------------------------
# 2. Payment Calculation Tests (PIX, Installment Tiers, Split Payment)
# ---------------------------------------------------------------------------


def test_calculate_payment_options_tiers_and_promotions():
    """Test calculate_payment_options across R$ 159.90, R$ 849.00, and R$ 2,199.00 (with/without active promo)."""
    # Case 1: R$ 159.90 (1x-3x valid since >= R$ 50; 4x is R$ 39.98 < R$ 80 -> max 3x; split False)
    opt_159 = calculate_payment_options(price_brl=159.90, has_active_promotion=False)
    assert opt_159["pix_price_brl"] == round(159.90 * 0.95, 2)
    assert opt_159["pix"]["discount_percent"] == 5.0
    assert opt_159["max_installments"] == 3
    assert len(opt_159["valid_installments"]) == 3
    assert opt_159["valid_installments"][-1]["installment_value_brl"] == 53.30
    assert opt_159["split_payment_allowed"] is False

    # Case 2: R$ 849.00 (1x-8x valid since 849/8 = R$ 106.12 >= R$ 100; 9x is R$ 94.33 < R$ 100 -> max 8x; split False)
    opt_849 = calculate_payment_options(price_brl=849.00, has_active_promotion=False)
    assert opt_849["pix_price_brl"] == 806.55
    assert opt_849["max_installments"] == 8
    assert len(opt_849["valid_installments"]) == 8
    assert opt_849["valid_installments"][-1]["installments"] == 8
    assert opt_849["valid_installments"][-1]["installment_value_brl"] == 106.12
    assert opt_849["split_payment_allowed"] is False

    # Case 3a: R$ 2,199.00 without active promotion (PIX 5% -> R$ 2,089.05; max 12x of R$ 183.25; split True)
    opt_2199_no_promo = calculate_payment_options(price_brl=2199.00, has_active_promotion=False)
    assert opt_2199_no_promo["pix_price_brl"] == 2089.05
    assert opt_2199_no_promo["pix"]["discount_percent"] == 5.0
    assert opt_2199_no_promo["max_installments"] == 12
    assert opt_2199_no_promo["valid_installments"][-1]["installment_value_brl"] == 183.25
    assert opt_2199_no_promo["split_payment_allowed"] is True

    # Case 3b: R$ 2,199.00 with active promotion (PIX no extra discount -> R$ 2,199.00; max 12x; split True)
    opt_2199_active_promo = calculate_payment_options(price_brl=2199.00, has_active_promotion=True)
    assert opt_2199_active_promo["pix_price_brl"] == 2199.00
    assert opt_2199_active_promo["pix"]["discount_percent"] == 0.0
    assert opt_2199_active_promo["max_installments"] == 12
    assert opt_2199_active_promo["split_payment_allowed"] is True


# ---------------------------------------------------------------------------
# 3. Order Status & LGPD Verification Tests
# ---------------------------------------------------------------------------


def test_get_order_status_lgpd_guardrails():
    """Verify LGPD guardrail blocks unverified order_id lookup and mismatched customer identity."""
    # Calling with only order_id and no customer_identifier must trigger LGPD verification prompt
    unverified = get_order_status(order_id=1)
    assert unverified["verified"] is False
    assert unverified["status"] == "lgpd_verification_required"

    # Calling with wrong customer name for order #1 must fail verification
    wrong_person = get_order_status(order_id=1, customer_identifier="Ana Carolina Ferreira")
    assert wrong_person["verified"] is False
    assert wrong_person["status"] == "lgpd_verification_failed"

    # Calling with a 3-letter substring or single first name must fail LGPD verification
    short_substring = get_order_status(order_id=1, customer_identifier="oli")
    assert short_substring["verified"] is False
    assert short_substring["status"] == "lgpd_verification_failed"

    single_first_name = get_order_status(order_id=1, customer_identifier="Pedro")
    assert single_first_name["verified"] is False
    assert single_first_name["status"] == "lgpd_verification_failed"

    # Calling with two matching name tokens ("Pedro Oliveira") succeeds
    two_tokens = get_order_status(order_id=1, customer_identifier="Pedro Oliveira")
    assert two_tokens["verified"] is True
    assert two_tokens["order_id"] == 1


def test_get_order_status_order_1_delivered():
    """Test delivered Order #1 (Pedro Henrique Oliveira) against reference_date 2026-03-25."""
    order1 = get_order_status(
        order_id=1,
        customer_identifier="Pedro Henrique Oliveira",
        reference_date="2026-03-25",
    )

    assert order1["verified"] is True
    assert order1["order_id"] == 1
    assert order1["status"] == "delivered"
    assert order1["order_date"] == "2025-10-15"
    assert order1["estimated_delivery"] == "2025-10-25"
    assert order1["tracking_code"] == "BRAB1234567BR"
    assert order1["total_brl"] == 11499.0
    assert order1["payment_method"] == "pix"
    assert len(order1["items"]) == 1
    assert order1["items"][0]["product_id"] == 93
    assert "Martin D-28" in order1["items"][0]["product_name"]

    # Order #1 was delivered 2025-10-25 (151 days before 2026-03-25) -> 7-day, 30-day, and 90-day windows expired
    elig = order1["policy_eligibility"]
    assert elig["days_since_order"] == 161
    assert elig["days_since_delivery"] == 151
    assert elig["right_of_regret"]["eligible"] is False
    assert elig["preference_exchange"]["eligible"] is False
    assert elig["defect_exchange_store"]["eligible"] is False
    assert elig["legal_warranty"]["eligible"] is False


def test_get_order_status_order_8_shipped():
    """Test shipped Order #8 (Ana Carolina Ferreira) tracking and upon-delivery eligibility."""
    order8 = get_order_status(
        order_id=8,
        customer_identifier="Ana Carolina Ferreira",
        reference_date="2026-03-25",
    )

    assert order8["verified"] is True
    assert order8["order_id"] == 8
    assert order8["status"] == "shipped"
    assert order8["order_date"] == "2026-02-15"
    assert order8["estimated_delivery"] == "2026-02-28"
    assert order8["tracking_code"] == "BRJL5544332BR"
    assert order8["total_brl"] == 349.9
    assert order8["payment_method"] == "debit"
    assert order8["items"][0]["product_id"] == 120
    assert "Kala KA-C" in order8["items"][0]["product_name"]

    # Shipped order can exercise 7-day right of regret upon delivery
    elig = order8["policy_eligibility"]
    assert elig["right_of_regret"]["eligible"] is True
    assert elig["legal_warranty"]["eligible"] is True


def test_get_order_status_order_18_cancelled():
    """Test cancelled Order #18 (Gustavo Teixeira Nunes) cancellation reason and non-eligibility."""
    order18 = get_order_status(
        order_id=18,
        customer_identifier="Gustavo Teixeira Nunes",
        reference_date="2026-03-25",
    )

    assert order18["verified"] is True
    assert order18["order_id"] == 18
    assert order18["status"] == "cancelled"
    assert order18["order_date"] == "2026-02-08"
    assert order18["total_brl"] == 459.9
    assert order18["payment_method"] == "credit_12x"
    assert order18["tracking_code"] is None
    assert order18["notes"] == "Item fora de estoque no momento do pedido"
    assert order18["items"][0]["product_id"] == 85

    elig = order18["policy_eligibility"]
    assert elig["right_of_regret"]["eligible"] is False
    assert elig["defect_exchange_store"]["eligible"] is False
    assert elig["legal_warranty"]["eligible"] is False


# ---------------------------------------------------------------------------
# 4. Store Policies Consultation Tests
# ---------------------------------------------------------------------------


def test_consult_store_policies_address_contacts_freight_and_accessories():
    """Verify consult_store_policies for store address, both phone numbers, freight rules, and accessory scope."""
    # 1. Store address
    addr_res = consult_store_policies("endereco")
    assert 1 in addr_res["section_ids"]
    assert "Rua 14 de Maio, 3200" in addr_res["combined_markdown"]
    assert "Campo Grande" in addr_res["combined_markdown"]
    assert "79202-333" in addr_res["combined_markdown"]

    # 2. Both contact phone numbers ((67) 3341-4444 and (67) 3321-4500)
    contact_res = consult_store_policies("whatsapp telefone contato")
    assert 1 in contact_res["section_ids"]
    assert 7 in contact_res["section_ids"]
    assert "(67) 3341-4444" in contact_res["combined_markdown"]
    assert "(67) 3321-4500" in contact_res["combined_markdown"]
    assert contact_res["contact_info"]["general_phone_whatsapp"] == "(67) 3341-4444"
    assert contact_res["contact_info"]["remote_support_whatsapp"] == "(67) 3321-4500"

    # 3. Freight rules (Campo Grande R$ 500 free / R$ 35 flat fee, PAC, SEDEX, Jadlog)
    freight_res = consult_store_policies("frete")
    assert 5 in freight_res["section_ids"]
    assert "R$ 500,00" in freight_res["combined_markdown"]
    assert "R$ 35,00" in freight_res["combined_markdown"]
    assert "PAC (Correios)" in freight_res["combined_markdown"]
    assert "SEDEX (Correios)" in freight_res["combined_markdown"]
    assert "Jadlog" in freight_res["combined_markdown"]

    # 4. Accessory scope restrictions
    acc_res = consult_store_policies("acessorios")
    assert 1 in acc_res["section_ids"] or 7 in acc_res["section_ids"]
    assert "exclusivamente com instrumentos musicais" in acc_res["combined_markdown"]
    assert acc_res["scope_restriction"]["sells_only_musical_instruments"] is True


def test_execute_tool_call_dispatcher_and_exports():
    """Verify AGENT_TOOLS list, execute_tool_call dispatcher, and google-genai declaration compatibility."""
    from google.genai import Client, types

    assert len(AGENT_TOOLS) == 4
    client = Client(api_key="test_key_for_schema_inspection")
    declarations = [
        types.FunctionDeclaration.from_callable(client=client, callable=fn)
        for fn in AGENT_TOOLS
    ]
    assert [d.name for d in declarations] == [
        "search_catalog",
        "calculate_payment_options",
        "get_order_status",
        "consult_store_policies",
    ]

    res = execute_tool_call("calculate_payment_options", {"price_brl": 500.0})
    assert res["pix_price_brl"] == 475.0

    unknown = execute_tool_call("non_existent_tool", {})
    assert unknown["status"] == "error"

