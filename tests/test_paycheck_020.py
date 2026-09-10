from bank_merge import load_bank_statements
import bank_merge
from month_compare import compare_months


def test_multi_statement_merge_deduplicates(monkeypatch):
    samples = {
        "a.pdf": [
            {"date": "10.09.2026", "amount": -50.0, "counterparty": "Gmina", "title": "Śmieci"},
            {"date": "10.09.2026", "amount": -100.0, "counterparty": "ABC", "title": "FV1"},
        ],
        "b.pdf": [
            {"date": "10.09.2026", "amount": -50.0, "counterparty": "Gmina", "title": "Śmieci"},
            {"date": "11.09.2026", "amount": -120.0, "counterparty": "XYZ", "title": "FV2"},
        ],
    }
    monkeypatch.setattr(bank_merge, "load_bank_statement", lambda path: samples[path])

    rows, info = load_bank_statements(["a.pdf", "b.pdf"])

    assert len(rows) == 3
    assert info["files"] == 2
    assert info["duplicates"] == 1
    assert {row["source_file"] for row in rows} == {"a.pdf", "b.pdf"}


def test_month_compare_detects_growth_drop_and_new_item():
    previous = [
        {"display_name": "Prąd", "institution": "Tauron", "amount": 100.0},
        {"display_name": "Internet", "institution": "Operator", "amount": 130.0},
    ]
    current = [
        {"display_name": "Prąd", "institution": "Tauron", "amount": 150.0},
        {"display_name": "Telefon", "institution": "Operator", "amount": 25.0},
    ]

    rows = compare_months(previous, current)
    by_name = {row["name"]: row for row in rows}

    assert by_name["Prąd"]["status"] == "WZROST"
    assert by_name["Prąd"]["difference"] == 50.0
    assert by_name["Prąd"]["percent_change"] == 50.0
    assert by_name["Internet"]["status"] == "BRAK W BIEŻĄCYM"
    assert by_name["Telefon"]["status"] == "NOWA"
