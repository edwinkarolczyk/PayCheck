from history_store import append_snapshot, compare_snapshots, load_history, make_snapshot


def test_history_detects_newly_paid(tmp_path):
    path = tmp_path / "history.json"
    old = make_snapshot(
        [{"source_type": "budget", "source_sheet": "Wrzesień 26", "source_row": 2, "display_name": "Prąd", "amount": 150, "status": "BRAK"}],
        source_mode="budget",
        source_label="Wrzesień 26",
        source_sheet="Wrzesień 26",
    )
    new = make_snapshot(
        [{"source_type": "budget", "source_sheet": "Wrzesień 26", "source_row": 2, "display_name": "Prąd", "amount": 150, "status": "OPŁACONA", "bank_amount": -150}],
        source_mode="budget",
        source_label="Wrzesień 26",
        source_sheet="Wrzesień 26",
    )
    changes = compare_snapshots(old, new)
    assert changes["newly_paid"] == ["Prąd"]
    assert changes["changed"] == 1


def test_history_does_not_duplicate_identical_snapshot(tmp_path):
    path = tmp_path / "history.json"
    snapshot = make_snapshot(
        [{"invoice_no": "FV1", "counterparty": "ABC", "amount": 100, "status": "OPŁACONA", "bank_amount": -100}],
        source_mode="standard",
        source_label="faktury.xlsx",
    )
    append_snapshot(snapshot, path)
    append_snapshot(snapshot, path)
    assert len(load_history(path)) == 1
