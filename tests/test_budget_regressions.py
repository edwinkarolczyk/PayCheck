from datetime import datetime

from openpyxl import Workbook

from budget_loader import load_budget_sheet
from budget_matcher import match_budget
from matcher import MatchSettings, score_pair


def test_budget_end_date_is_not_used_as_payment_due_date(tmp_path):
    path = tmp_path / "budget.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Wrzesień 26"
    ws.append(["Data zakończenia", "instytucja", "Suma", "Miesiecznie"])
    ws.append([datetime(2029, 2, 12), "Velo bank", "Velo", 108])
    wb.save(path)

    items = load_budget_sheet(path, "Wrzesień 26")

    assert items[0]["date"] == ""
    assert items[0]["end_date"].date() == datetime(2029, 2, 12).date()


def test_budget_difference_ignores_bank_sign():
    items = [{
        "display_name": "Velo",
        "institution": "Velo bank",
        "counterparty": "Velo bank Velo",
        "amount": 108.0,
        "date": "",
        "source_sheet": "Wrzesień 26",
    }]
    transactions = [{
        "date": "10.09.2026",
        "counterparty": "Velo bank",
        "amount": -108.72,
        "title": "Rata Velo",
        "description": "Rata Velo",
    }]

    result = match_budget(items, transactions, MatchSettings())[0]

    assert result["amount_diff"] == 0.72


def test_standard_difference_ignores_bank_sign():
    invoice = {
        "counterparty": "Gmina",
        "amount": 50.0,
        "date": "10.09.2026",
        "invoice_no": "FV1",
    }
    transaction = {
        "counterparty": "Gmina",
        "amount": -50.0,
        "date": "10.09.2026",
        "title": "FV1",
    }

    result = score_pair(invoice, transaction, MatchSettings())

    assert result["amount_diff"] == 0.0
