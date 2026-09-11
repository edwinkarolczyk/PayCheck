import dashboard_100


def test_home_dashboard_totals(monkeypatch):
    monkeypatch.setattr(
        dashboard_100,
        "load_installments",
        lambda: [
            {"name": "Dach", "bank": "mBank", "monthly": 150, "active": True, "end_date": "2026-12-01", "payment_day": 10},
            {"name": "TV", "bank": "Alior", "monthly": 50, "active": False, "end_date": "2026-12-01", "payment_day": 12},
        ],
    )
    items = [
        {"entry_type": "income", "amount": 5000},
        {"entry_type": "expense", "amount": 1000},
        {"entry_type": "expense", "amount": 500},
    ]
    results = [
        {"entry_type": "expense", "amount": 1000, "status": "OPŁACONA", "display_name": "Czynsz"},
        {"entry_type": "expense", "amount": 500, "status": "BRAK", "display_name": "Prąd"},
    ]
    data = dashboard_100.home_dashboard(items, results)
    assert data["income"] == 5000
    assert data["expenses"] == 1500
    assert data["paid"] == 1000
    assert data["remaining"] == 500
    assert data["balance_plan"] == 3500
    assert data["installment_monthly"] == 150
    assert data["installment_count"] == 1
    assert data["banks"] == {"mBank": 150.0}
    assert data["attention"][0]["name"] == "Prąd"


def test_home_dashboard_progress_never_exceeds_100(monkeypatch):
    monkeypatch.setattr(dashboard_100, "load_installments", lambda: [])
    items = [{"entry_type": "expense", "amount": 100}]
    results = [{"entry_type": "expense", "amount": 120, "status": "OPŁACONA"}]
    data = dashboard_100.home_dashboard(items, results)
    assert data["progress"] == 100.0
    assert data["remaining"] == 0.0
