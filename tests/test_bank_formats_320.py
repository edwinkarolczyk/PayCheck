from pathlib import Path

from bank_formats_320 import parse_mt940
from io_files import _parse_bank_pdf_text


def test_mt940_debit_and_credit(tmp_path: Path):
    path = tmp_path / "bank.sta"
    path.write_text(
        ":20:START\n"
        ":61:260911D123,45NTRFNONREF\n"
        ":86:ORLEN STACJA PALIW\n"
        ":61:260912C2500,00NTRFNONREF\n"
        ":86:WYNAGRODZENIE\n",
        encoding="utf-8",
    )
    rows = parse_mt940(path)
    assert len(rows) == 2
    assert rows[0]["amount"] == -123.45
    assert rows[1]["amount"] == 2500.0
    assert "ORLEN" in rows[0]["counterparty"]


def test_pdf_uses_last_ledger_amount_when_description_contains_amount():
    text = (
        "11.09.2026 - Płatność kartą w SKLEP TEST na kwotę 3,00 PLN "
        "miasto Polska -3,00 PLN\n"
    )
    rows = _parse_bank_pdf_text(text)
    assert len(rows) == 1
    assert rows[0]["amount"] == -3.0
