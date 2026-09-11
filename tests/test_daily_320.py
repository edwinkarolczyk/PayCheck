from datetime import date

import daily_320


def test_today_overview_and_close_check(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_320, "app_dir", lambda: tmp_path)
    items = [
        {
            "display_name": "Prąd",
            "institution": "Energia",
            "amount": 120.0,
            "entry_type": "expense",
            "payment_day": 5,
            "source_sheet": "Wrzesień 26",
        }
    ]
    results = [
        {
            "display_name": "Prąd",
            "institution": "Energia",
            "amount": 120.0,
            "entry_type": "expense",
            "status": "BRAK",
        }
    ]
    today = date(2026, 9, 11)
    overview = daily_320.today_overview(items, results, today=today)
    assert len(overview["overdue"]) == 1
    check = daily_320.month_close_check(items, results, today=today)
    assert check["can_close"] is False
    assert check["month"] == "Wrzesień 26"


def test_close_month_when_all_paid(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_320, "app_dir", lambda: tmp_path)
    items = [{"display_name": "Internet", "institution": "ISP", "amount": 80.0, "entry_type": "expense", "payment_day": 15}]
    results = [{"display_name": "Internet", "institution": "ISP", "amount": 80.0, "entry_type": "expense", "status": "OPŁACONA", "bank_amount": -80.0}]
    row = daily_320.close_month(items, results, today=date(2026, 9, 11))
    assert row["missing"] == 0
    assert row["review"] == 0
    assert daily_320.load_month_closures()[0]["month"] == "2026-09"


def test_plan_12_months_has_twelve_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_320, "app_dir", lambda: tmp_path)
    monkeypatch.setattr(daily_320, "load_installments", lambda: [])
    monkeypatch.setattr(daily_320, "load_subscriptions", lambda: [])
    monkeypatch.setattr(daily_320, "load_envelopes", lambda: [])
    monkeypatch.setattr(daily_320, "load_savings_accounts", lambda: [])
    monkeypatch.setattr(daily_320, "load_debts", lambda: [])
    rows = daily_320.plan_12_months(date(2026, 9, 11))
    assert len(rows) == 12
    assert rows[0]["label"] == "2026-09"
    assert rows[-1]["label"] == "2027-08"
