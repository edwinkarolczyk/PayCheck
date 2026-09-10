from budget_matcher import match_budget
from budget_summary import summarize_budget
from matcher import MatchSettings


def test_budget_summary_separates_income_expenses_and_banks():
    items = [
        {"display_name": "wypłata", "amount": 6300.0, "entry_type": "income", "category": "Wpływy", "bank": ""},
        {"display_name": "Pompa Ciepła", "amount": 647.0, "entry_type": "expense", "category": "Raty / banki", "bank": "Santander"},
        {"display_name": "Dach", "amount": 150.0, "entry_type": "expense", "category": "Raty / banki", "bank": "mBank"},
        {"display_name": "Prąd", "amount": 150.0, "entry_type": "expense", "category": "Dom i rachunki", "bank": ""},
    ]

    summary = summarize_budget(items)

    assert summary["income_total"] == 6300.0
    assert summary["expense_total"] == 947.0
    assert summary["installments_total"] == 797.0
    assert summary["banks"]["Santander"] == 647.0
    assert summary["banks"]["mBank"] == 150.0


def test_income_matches_only_positive_bank_transaction():
    item = {
        "display_name": "wypłata",
        "counterparty": "wypłata",
        "institution": "",
        "amount": 6300.0,
        "entry_type": "income",
        "source_sheet": "Wrzesień 26",
    }
    transactions = [
        {"date": "10.09.2026", "amount": -6300.0, "counterparty": "Przelew", "title": "wydatek"},
        {"date": "10.09.2026", "amount": 6300.0, "counterparty": "Pracodawca", "title": "wypłata"},
    ]

    result = match_budget([item], transactions, MatchSettings())[0]

    assert result["status"] != "BRAK"
    assert result["bank_amount"] == 6300.0
