from month_state import (
    bank_confirmation_label,
    load_month_state,
    merge_transactions,
    review_rows,
    save_month_state,
)


def test_month_state_persists_month_and_transactions(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    save_month_state(
        "Wrzesień 26",
        source_mode="budget",
        budget_path="budget.xlsx",
        budget_sheet="Wrzesień 26",
        items=[{"display_name": "Prąd", "amount": 150.0}],
        transactions=[{"date": "10.09.2026", "amount": -150.0, "counterparty": "Tauron"}],
        results=[{"display_name": "Prąd", "status": "OPŁACONA", "bank_amount": -150.0}],
        statement_files=["wyciag1.pdf"],
    )

    state = load_month_state("Wrzesień 26")
    assert state is not None
    assert state["budget_sheet"] == "Wrzesień 26"
    assert len(state["transactions"]) == 1
    assert state["statement_files"] == ["wyciag1.pdf"]


def test_merge_transactions_keeps_existing_and_skips_duplicate():
    existing = [
        {"date": "10.09.2026", "amount": -50.0, "counterparty": "Gmina", "title": "Śmieci"}
    ]
    incoming = [
        {"date": "10.09.2026", "amount": -50.0, "counterparty": "Gmina", "title": "Śmieci"},
        {"date": "11.09.2026", "amount": -150.0, "counterparty": "Tauron", "title": "Prąd"},
    ]

    merged, added = merge_transactions(existing, incoming)
    assert len(merged) == 2
    assert added == 1


def test_bank_confirmation_labels_are_explicit():
    auto = {"status": "OPŁACONA", "bank_date": "10.09.2026", "bank_amount": -100.0}
    manual = {
        "status": "OPŁACONA",
        "bank_date": "10.09.2026",
        "bank_amount": -100.0,
        "manual_decision": "approved",
    }
    no_bank = {"status": "BRAK", "bank_date": "", "bank_amount": ""}

    assert bank_confirmation_label(auto) == "POTWIERDZONA W BANKU"
    assert bank_confirmation_label(manual) == "POTWIERDZONA RĘCZNIE"
    assert bank_confirmation_label(no_bank) == "BRAK POTWIERDZENIA W BANKU"


def test_review_rows_only_returns_uncertain_matches():
    rows = [
        {"status": "OPŁACONA"},
        {"status": "DO SPRAWDZENIA", "display_name": "Velo"},
        {"status": "BRAK"},
    ]
    assert [row["display_name"] for row in review_rows(rows)] == ["Velo"]
