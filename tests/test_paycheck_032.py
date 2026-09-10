from advanced_features import (
    dashboard,
    detect_split_and_grouped,
    filter_results,
    item_history,
    trend_for_item,
)
from matcher import MatchSettings


def test_filters_statuses_and_manual_rows():
    rows = [
        {"status": "OPŁACONA"},
        {"status": "DO SPRAWDZENIA", "manual_decision": "approved"},
        {"status": "BRAK"},
    ]
    assert len(filter_results(rows, "Wszystkie")) == 3
    assert len(filter_results(rows, "Opłacone")) == 1
    assert len(filter_results(rows, "Do sprawdzenia")) == 1
    assert len(filter_results(rows, "Brak")) == 1
    assert len(filter_results(rows, "Ręczne")) == 1


def test_split_payment_is_suggested_for_review():
    results = [{
        "display_name": "Rata",
        "institution": "Bank",
        "amount": 100.0,
        "source_type": "budget",
        "source_sheet": "Wrzesień 26",
        "entry_type": "expense",
        "status": "BRAK",
        "bank_date": "",
    }]
    transactions = [
        {"date": "05.09.2026", "amount": -60.0, "counterparty": "Bank", "title": "część 1"},
        {"date": "06.09.2026", "amount": -40.0, "counterparty": "Bank", "title": "część 2"},
    ]
    changed = detect_split_and_grouped(results, transactions, MatchSettings(amount_absolute_tolerance=1))
    assert changed == 1
    assert results[0]["status"] == "DO SPRAWDZENIA"
    assert results[0]["match_kind"] == "PODZIELONA"
    assert results[0]["bank_amount"] == 100.0


def test_grouped_payment_marks_multiple_items_for_review():
    results = [
        {"display_name": "Internet", "amount": 70.0, "source_type": "budget", "source_sheet": "Wrzesień 26", "entry_type": "expense", "status": "BRAK", "bank_date": ""},
        {"display_name": "Telefon", "amount": 30.0, "source_type": "budget", "source_sheet": "Wrzesień 26", "entry_type": "expense", "status": "BRAK", "bank_date": ""},
    ]
    transactions = [
        {"date": "08.09.2026", "amount": -100.0, "counterparty": "Operator", "title": "rachunek"},
    ]
    changed = detect_split_and_grouped(results, transactions, MatchSettings(amount_absolute_tolerance=1))
    assert changed == 2
    assert all(row["match_kind"] == "ŁĄCZONA" for row in results)
    assert all(row["status"] == "DO SPRAWDZENIA" for row in results)


def test_item_history_and_trend():
    history = [
        {"created_at": "2026-07-01T10:00:00", "source_sheet": "Lipiec 26", "rows": [{"name": "Prąd", "institution": "Tauron", "amount": 100, "status": "OPŁACONA", "bank_amount": -100}]},
        {"created_at": "2026-08-01T10:00:00", "source_sheet": "Sierpień 26", "rows": [{"name": "Prąd", "institution": "Tauron", "amount": 120, "status": "OPŁACONA", "bank_amount": -120}]},
        {"created_at": "2026-09-01T10:00:00", "source_sheet": "Wrzesień 26", "rows": [{"name": "Prąd", "institution": "Tauron", "amount": 150, "status": "BRAK", "bank_amount": ""}]},
    ]
    row = {"display_name": "Prąd", "institution": "Tauron"}
    assert len(item_history(history, row)) == 3
    trend = trend_for_item(history, row, 3)
    assert trend["average"] == 123.33
    assert trend["change_percent"] == 25.0


def test_dashboard_counts_only_expenses():
    rows = [
        {"entry_type": "expense", "amount": 100, "status": "OPŁACONA"},
        {"entry_type": "expense", "amount": 50, "status": "DO SPRAWDZENIA"},
        {"entry_type": "expense", "amount": 25, "status": "BRAK"},
        {"entry_type": "income", "amount": 6300, "status": "OPŁACONA"},
    ]
    data = dashboard(rows)
    assert data["planned"] == 175.0
    assert data["paid"] == 100.0
    assert data["review"] == 50.0
    assert data["missing"] == 25.0
