from __future__ import annotations

import json

from annual_report import annual_report, available_years


def _state(label, items, results):
    return {
        "month_label": label,
        "budget_sheet": label,
        "items": items,
        "results": results,
        "transactions": [],
    }


def test_annual_report_aggregates_months(tmp_path):
    january = _state(
        "Styczeń 26",
        [
            {"display_name": "Pensja", "amount": 5000, "entry_type": "income", "category": "Wpływy"},
            {"display_name": "Rata", "amount": 1000, "entry_type": "expense", "category": "Raty"},
            {"display_name": "Paliwo", "amount": 400, "entry_type": "expense", "category": "Transport"},
        ],
        [
            {"display_name": "Rata", "amount": 1000, "entry_type": "expense", "status": "OPŁACONA"},
            {"display_name": "Paliwo", "amount": 400, "entry_type": "expense", "status": "BRAK"},
        ],
    )
    february = _state(
        "Luty 26",
        [
            {"display_name": "Pensja", "amount": 5100, "entry_type": "income", "category": "Wpływy"},
            {"display_name": "Rata", "amount": 1000, "entry_type": "expense", "category": "Raty"},
        ],
        [
            {"display_name": "Rata", "amount": 1000, "entry_type": "expense", "status": "DO SPRAWDZENIA"},
        ],
    )
    (tmp_path / "jan.json").write_text(json.dumps(january, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "feb.json").write_text(json.dumps(february, ensure_ascii=False), encoding="utf-8")

    assert available_years(tmp_path) == [2026]
    report = annual_report(2026, tmp_path)
    assert report["months_count"] == 2
    assert report["income"] == 10100.0
    assert report["expenses"] == 2400.0
    assert report["paid"] == 1000.0
    assert report["review"] == 1000.0
    assert report["missing"] == 400.0
    assert report["balance"] == 7700.0
    assert report["categories"][0]["category"] == "Raty"
    assert report["categories"][0]["amount"] == 2000.0
