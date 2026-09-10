from io_files import _parse_bank_pdf_text


def test_parse_bank_pdf_text_from_statement_layout():
    text = """
    Ostatnie 90 dni
    DATA TRANSAKCJI DATA KSIĘGOWANIA OPIS TRANSAKCJI KWOTA TRANSAKCJI SALDO PO TRANSAKCJI
    10.09.2026 - Operacja kartą 5375 **** **** 2166 na kwotę 3,00 PLN w metalbox, olkusz, PL -3,00 PLN -
    10.09.2026 10.09.2026 Przelew na rachunek: 16 1560 0013 2383 1536 3000 0010,
    Odbiorca: KAROLCZYK EDWIN,
    Tytuł: Przelew własny -1 000,00 PLN 1 702,21 PLN
    10.09.2026 10.09.2026 Przelew z rachunku: 38 1560 0013 2383 1536 3000 0002,
    Nadawca: KAROLCZYK EDWIN,
    Tytuł: BLIK: /OP/T/XIII/P24-ZSC-H8V-N3C 09212000 010001410000021897 -646,60 PLN 2 702,21 PLN
    """

    rows = _parse_bank_pdf_text(text)

    assert len(rows) == 3
    assert rows[0]["date"] == "10.09.2026"
    assert rows[0]["amount"] == 3.00
    assert "metalbox" in rows[0]["counterparty"].lower()

    assert rows[1]["amount"] == -1000.00
    assert rows[1]["counterparty"] == "KAROLCZYK EDWIN"
    assert rows[1]["title"] == "Przelew własny"

    assert rows[2]["amount"] == -646.60
    assert rows[2]["counterparty"] == "KAROLCZYK EDWIN"
    assert rows[2]["title"].startswith("BLIK:")


def test_parse_bank_pdf_text_rejects_non_statement_text():
    try:
        _parse_bank_pdf_text("Dokument bez transakcji")
    except ValueError as exc:
        assert "Nie znaleziono transakcji" in str(exc)
    else:
        raise AssertionError("Parser powinien zgłosić brak transakcji")
