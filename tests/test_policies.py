"""Unit tests for the policy knowledge base extractor and query functions.

Why: Ensures all 10 policy sections, contractual tables, and both store phone numbers
remain intact, accessible, and queryable for downstream agent prompt injection.
"""

from __future__ import annotations

import pytest

from src.policies_kb import (
    extract_raw_pdf_text,
    get_all_policies,
    get_contact_info,
    get_policy_section,
    search_policies,
)


def test_pdf_extraction_not_empty():
    """Verify that extract_raw_pdf_text successfully reads the PDF file."""
    text = extract_raw_pdf_text()
    assert len(text) > 2000
    assert "Empório da Música" in text or "EMPÓRIO DA MÚSICA" in text


def test_all_10_sections_present():
    """Verify that get_all_policies provides all 10 defined sections."""
    policies = get_all_policies()
    assert len(policies) == 10
    for i in range(1, 11):
        assert i in policies
        assert "title" in policies[i]
        assert "content_markdown" in policies[i]
        assert len(policies[i]["content_markdown"]) > 50


def test_get_policy_section_valid_and_invalid():
    """Verify section retrieval by index and error messages for invalid input."""
    sec1 = get_policy_section(1)
    assert "Sobre a Empório da Música" in sec1

    sec3 = get_policy_section(3)
    assert "Formas de Pagamento" in sec3

    sec_invalid = get_policy_section(99)
    assert "não encontrada" in sec_invalid

    sec_bad_type = get_policy_section("abc")
    assert "Seção inválida" in sec_bad_type


def test_store_contacts_preservation():
    """Verify that both store phone numbers are distinctly preserved."""
    contacts = get_contact_info()
    assert contacts["general_phone_whatsapp"] == "(67) 3341-4444"
    assert contacts["remote_support_whatsapp"] == "(67) 3321-4500"

    # Also verify that Section 1 contains the general number
    sec1 = get_policy_section(1)
    assert "(67) 3341-4444" in sec1

    # And Section 7 contains the remote support number
    sec7 = get_policy_section(7)
    assert "(67) 3321-4500" in sec7


def test_section_3_installment_tiers():
    """Verify Section 3 Markdown tables and tier thresholds."""
    sec3 = get_policy_section(3)
    # Check 1x-3x, 4x-6x, 7x-12x thresholds
    assert "R$ 50,00" in sec3
    assert "R$ 80,00" in sec3
    assert "R$ 100,00" in sec3
    # Check split payment limit
    assert "R$ 2.000,00" in sec3


def test_section_4_returns_and_exchanges():
    """Verify Section 4 return periods, warranties, and non-eligible items."""
    sec4 = get_policy_section(4)
    assert "7 (sete) dias corridos" in sec4  # Regret
    assert "30 (trinta) dias corridos" in sec4  # Defect with store
    assert "Boquilhas" in sec4  # Non eligible
    assert "personalização" in sec4  # Custom setups non-eligible


def test_section_5_shipping_slas():
    """Verify Section 5 shipping SLAs and free shipping rules."""
    sec5 = get_policy_section(5)
    assert "PAC (Correios)" in sec5
    assert "SEDEX (Correios)" in sec5
    assert "Jadlog" in sec5
    assert "R$ 500,00" in sec5  # Free shipping threshold for Campo Grande
    assert "R$ 35,00" in sec5  # Flat fee for Campo Grande below threshold


def test_section_6_promotion_rules():
    """Verify Section 6 non-cumulativity and rain check rules."""
    sec6 = get_policy_section(6)
    assert "5%" in sec6
    assert "não se acumula" in sec6
    assert "rain check" in sec6


def test_section_7_scope_and_accessories_prohibition():
    """Verify Section 7 instructs that accessories are out of scope."""
    sec7 = get_policy_section(7)
    assert "exclusivamente com instrumentos musicais" in sec7
    assert "acessórios" in sec7


def test_section_8_legal_warranty():
    """Verify Section 8 specifies the 90-day CDC warranty."""
    sec8 = get_policy_section(8)
    assert "90 (noventa) dias" in sec8


def test_search_policies_functionality():
    """Verify keyword policy search returns relevant sections."""
    res_frete = search_policies("prazo frete correios")
    assert len(res_frete) > 0
    assert res_frete[0]["section_id"] == 5

    res_pix = search_policies("pix parcelamento")
    assert len(res_pix) > 0
    section_ids = [r["section_id"] for r in res_pix]
    assert 3 in section_ids or 6 in section_ids

    res_lgpd_del = search_policies("exclusao de dados lgpd")
    assert len(res_lgpd_del) > 0
    assert res_lgpd_del[0]["section_id"] == 9
    assert "exclusão de seus dados" in res_lgpd_del[0]["content_markdown"]
