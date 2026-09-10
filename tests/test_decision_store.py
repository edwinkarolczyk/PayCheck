from decision_store import apply_decisions, load_decisions, remove_decision, save_decision


def _row():
    return {
        "source_type": "budget",
        "source_sheet": "Wrzesień 26",
        "source_row": 40,
        "display_name": "Pompa Ciepła",
        "institution": "Santander",
        "amount": 647.0,
        "status": "DO SPRAWDZENIA",
        "bank_date": "10.09.2026",
        "bank_amount": -646.60,
        "bank_counterparty": "SANTANDER",
        "bank_title": "Rata pompa ciepła",
        "amount_diff": -0.40,
    }


def test_approved_decision_is_remembered_and_applied(tmp_path):
    path = tmp_path / "decisions.json"
    row = _row()
    save_decision(row, "approved", path)

    fresh = _row()
    assert apply_decisions([fresh], path) == 1
    assert fresh["status"] == "OPŁACONA"
    assert fresh["manual_decision"] == "approved"
    assert load_decisions(path)


def test_rejected_decision_is_remembered_without_losing_undo_key(tmp_path):
    path = tmp_path / "decisions.json"
    row = _row()
    save_decision(row, "rejected", path)

    fresh = _row()
    assert apply_decisions([fresh], path) == 1
    assert fresh["status"] == "BRAK"
    assert fresh["manual_decision"] == "rejected"
    assert fresh["bank_amount"] == ""
    assert fresh["rejected_bank_amount"] == -646.60

    assert remove_decision(fresh, path) is True
    assert load_decisions(path) == {}
