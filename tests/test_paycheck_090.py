from datetime import date

from installment_store import (
    active_for_month,
    estimated_left,
    load_installments,
    months_left,
    remove_installment,
    set_installment_active,
    to_budget_items,
    upsert_installment,
)


def test_installment_crud_and_month_projection(tmp_path):
    path = tmp_path / "installments.json"
    row = upsert_installment({
        "name": "Pompa ciepła",
        "bank": "Santander",
        "monthly": 646.60,
        "payment_day": 10,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "interest_type": "0%",
        "active": True,
    }, path)

    rows = load_installments(path)
    assert len(rows) == 1
    assert rows[0]["id"] == row["id"]
    assert active_for_month(rows[0], "Wrzesień 26") is True
    assert active_for_month(rows[0], "Styczeń 27") is False

    items = to_budget_items(rows, "Wrzesień 26")
    assert len(items) == 1
    assert items[0]["manual_installment_id"] == row["id"]
    assert items[0]["amount"] == 646.60

    assert set_installment_active(row["id"], False, path) is True
    assert to_budget_items(load_installments(path), "Wrzesień 26") == []
    assert remove_installment(row["id"], path) is True
    assert load_installments(path) == []


def test_remaining_installments_and_estimated_amount():
    row = {"end_date": "2026-12-31", "monthly": 100.0}
    assert months_left(row, date(2026, 9, 11)) == 4
    assert estimated_left(row, date(2026, 9, 11)) == 400.0
