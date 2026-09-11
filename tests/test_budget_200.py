from __future__ import annotations

from datetime import date

import budget_200


def test_payment_calendar_marks_overdue():
    items = [{"display_name": "Internet", "institution": "ISP", "amount": 100, "entry_type": "expense", "payment_day": 5, "category": "Dom"}]
    results = [{"display_name": "Internet", "institution": "ISP", "amount": 100, "entry_type": "expense", "status": "BRAK"}]
    rows = budget_200.payment_calendar(items, results, today=date(2026, 9, 11))
    assert rows[0]["status"] == "PO TERMINIE"
    assert rows[0]["due"] == "2026-09-05"


def test_goal_overview_and_monthly_needed(tmp_path, monkeypatch):
    monkeypatch.setattr(budget_200, "app_dir", lambda: tmp_path)
    budget_200.save_goal({"name": "Wakacje", "target": 1200, "saved": 300, "deadline": "2026-11-30"})
    rows = budget_200.goal_overview(today=date(2026, 9, 1))
    assert rows[0]["missing"] == 900
    assert rows[0]["months_left"] == 3
    assert rows[0]["monthly_needed"] == 300


def test_category_limit_warns_at_80_percent(tmp_path, monkeypatch):
    monkeypatch.setattr(budget_200, "app_dir", lambda: tmp_path)
    budget_200.set_limit("Paliwo", 1000)
    items = [{"category": "Paliwo", "amount": 1000, "entry_type": "expense"}]
    results = [{"category": "Paliwo", "amount": 850, "bank_amount": -850, "entry_type": "expense", "status": "OPŁACONA"}]
    row = budget_200.category_limit_status(items, results)[0]
    assert row["percent"] == 85.0
    assert row["warning"] is True
    assert row["over"] is False


def test_duplicate_transactions_detected():
    tx = [
        {"date": "2026-09-10", "amount": -49.99, "counterparty": "Sklep"},
        {"date": "2026-09-10", "amount": -49.99, "counterparty": "Sklep"},
    ]
    rows = budget_200.detect_duplicate_transactions(tx)
    assert len(rows) == 1
    assert rows[0]["count"] == 2


def test_next_month_forecast_uses_recent_history():
    items = [
        {"amount": 5000, "entry_type": "income"},
        {"amount": 2000, "entry_type": "expense"},
    ]
    history = [
        {"rows": [{"category": "Dom", "amount": 1000}]},
        {"rows": [{"category": "Dom", "amount": 1200}]},
        {"rows": [{"category": "Dom", "amount": 1400}]},
    ]
    data = budget_200.next_month_forecast(items, history)
    assert data["projected_expenses"] == 1200
    assert data["projected_balance"] == 3800


def test_wallet_crud_and_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(budget_200, "app_dir", lambda: tmp_path)
    saved = budget_200.save_wallet({"name": "Główne", "bank": "mBank", "balance": 2500})
    rows = budget_200.wallet_summary([
        {"source_file": "mbank_wrzesien.csv", "counterparty": "", "amount": 3000},
        {"source_file": "mbank_wrzesien.csv", "counterparty": "", "amount": -1000},
    ])
    assert rows[0]["income"] == 3000
    assert rows[0]["expenses"] == 1000
    assert budget_200.delete_wallet(saved["id"]) is True


def test_dashboard_200_basic(tmp_path, monkeypatch):
    monkeypatch.setattr(budget_200, "app_dir", lambda: tmp_path)
    items = [
        {"amount": 4000, "entry_type": "income", "display_name": "Wypłata"},
        {"amount": 1000, "entry_type": "expense", "display_name": "Czynsz", "institution": "Dom"},
    ]
    results = [{"amount": 1000, "bank_amount": -1000, "entry_type": "expense", "display_name": "Czynsz", "institution": "Dom", "status": "OPŁACONA"}]
    data = budget_200.dashboard_200(items, results, [], [])
    assert data["income"] == 4000
    assert data["expenses"] == 1000
    assert data["paid"] == 1000
    assert data["remaining"] == 0
