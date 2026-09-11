from datetime import date

from budget_manager import (
    budget_overview,
    classify_payment_type,
    installment_overview,
    installment_summary,
    payment_match_quality,
)
from payment_policy import enforce_payment_precision


def test_blik_is_matched_to_the_cent():
    tx = {"amount": -100.02, "title": "BLIK płatność", "counterparty": "Sklep"}
    quality = payment_match_quality(100.00, tx)
    assert quality["payment_type"] == "BLIK"
    assert quality["tolerance"] == 0.01
    assert quality["amount_ok"] is False


def test_transfer_default_and_custom_tolerance():
    tx = {"amount": -104.0, "title": "Przelew za usługę", "counterparty": "Firma"}
    assert payment_match_quality(100.0, tx, transfer_limit=2.0)["amount_ok"] is False
    assert payment_match_quality(100.0, tx, transfer_limit=5.0)["amount_ok"] is True


def test_payment_precision_downgrades_paid_blik_with_wrong_amount():
    rows = [{
        "display_name": "Zakup",
        "amount": 50.0,
        "status": "OPŁACONA",
        "bank_date": "10.09.2026",
        "bank_amount": -50.02,
        "bank_counterparty": "Sklep",
        "bank_title": "BLIK płatność",
    }]
    changed = enforce_payment_precision(rows, 2.0)
    assert changed == 1
    assert rows[0]["status"] == "DO SPRAWDZENIA"
    assert rows[0]["payment_type"] == "BLIK"


def test_installment_remaining_months_and_amount():
    items = [{
        "display_name": "Rata testowa",
        "institution": "mBank",
        "bank": "mBank",
        "category": "Raty / banki",
        "amount": 100.0,
        "end_date": "2027-01-15",
    }]
    rows = installment_overview(items, [], today=date(2026, 9, 11))
    assert rows[0]["months_left"] == 5
    assert rows[0]["estimated_left"] == 500.0
    summary = installment_summary(rows)
    assert summary["active"] == 1
    assert summary["monthly"] == 100.0


def test_budget_overview_plan_execution():
    items = [
        {"display_name": "Wypłata", "amount": 5000.0, "entry_type": "income", "category": "Wpływy"},
        {"display_name": "Prąd", "amount": 200.0, "entry_type": "expense", "category": "Dom i rachunki"},
        {"display_name": "Rata", "amount": 300.0, "entry_type": "expense", "category": "Raty / banki"},
    ]
    results = [
        {"display_name": "Prąd", "amount": 200.0, "entry_type": "expense", "status": "OPŁACONA"},
        {"display_name": "Rata", "amount": 300.0, "entry_type": "expense", "status": "BRAK"},
    ]
    data = budget_overview(items, results)
    assert data["income"] == 5000.0
    assert data["expenses"] == 500.0
    assert data["paid"] == 200.0
    assert data["missing"] == 300.0
    assert data["balance_plan"] == 4500.0


def test_payment_type_detects_income():
    assert classify_payment_type({"amount": 1000.0, "title": "Wynagrodzenie"}) == "WPŁYW"
