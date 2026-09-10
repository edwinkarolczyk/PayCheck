from __future__ import annotations

import json
from datetime import date, datetime

from finance_050 import (
    apply_rules,
    detect_anomalies,
    export_backup,
    forecast_month,
    import_backup,
    installment_plan,
    payment_deadline_status,
    remember_rule,
)


def _budget_row(name="Prąd", amount=150.0):
    return {
        "display_name": name,
        "institution": "Tauron",
        "counterparty": f"Tauron {name}",
        "amount": amount,
        "entry_type": "expense",
        "source_type": "budget",
        "source_sheet": "Wrzesień 26",
        "status": "BRAK",
    }


def test_rule_is_remembered_and_applied(tmp_path):
    path = tmp_path / "rules.json"
    row = _budget_row()
    row.update({"bank_counterparty": "TAURON", "bank_title": "Rachunek prąd"})
    remember_rule(row, path)

    result = _budget_row()
    tx = {"date": "08.09.2026", "amount": -150.0, "counterparty": "TAURON", "title": "Rachunek prąd"}
    changed = apply_rules([result], [tx], path)

    assert changed == 1
    assert result["status"] == "OPŁACONA"
    assert result["match_kind"] == "REGUŁA"


def test_anomaly_detects_large_growth():
    row = _budget_row(amount=160.0)
    history = [
        {"rows": [{"name": "Prąd", "institution": "Tauron", "amount": 100.0}]},
        {"rows": [{"name": "Prąd", "institution": "Tauron", "amount": 105.0}]},
    ]
    alerts = detect_anomalies([row], history, threshold_percent=25.0)
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "WZROST"


def test_forecast_separates_paid_and_remaining():
    rows = [
        {**_budget_row("A", 100), "status": "OPŁACONA", "bank_amount": -98.0},
        {**_budget_row("B", 200), "status": "DO SPRAWDZENIA"},
        {**_budget_row("C", 300), "status": "BRAK"},
    ]
    data = forecast_month(rows)
    assert data["planned"] == 600.0
    assert data["paid_actual"] == 98.0
    assert data["remaining"] == 500.0
    assert data["projected"] == 598.0


def test_deadline_inferred_from_history():
    row = _budget_row()
    history = [
        {"rows": [{"name": "Prąd", "institution": "Tauron", "bank_date": "10.07.2026"}]},
        {"rows": [{"name": "Prąd", "institution": "Tauron", "bank_date": "12.08.2026"}]},
    ]
    status = payment_deadline_status(history, row, today=date(2026, 9, 15))
    assert status.startswith("PO TERMINIE")


def test_installment_plan_uses_end_date():
    items = [{
        "display_name": "Pompa Ciepła",
        "bank": "Santander",
        "amount": 647.0,
        "end_date": datetime(2027, 1, 15),
    }]
    rows = installment_plan(items, as_of=date(2026, 9, 10))
    assert rows[0]["months_left"] == 5
    assert rows[0]["estimated_left"] == 3235.0


def test_backup_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    source_dir = tmp_path / "appdata" / "PayCheck"
    source_dir.mkdir(parents=True)
    (source_dir / "history.json").write_text(json.dumps([{"ok": True}]), encoding="utf-8")
    backup = tmp_path / "backup.zip"
    export_backup(backup)

    (source_dir / "history.json").write_text("[]", encoding="utf-8")
    restored = import_backup(backup)

    assert restored == 1
    assert json.loads((source_dir / "history.json").read_text(encoding="utf-8")) == [{"ok": True}]
