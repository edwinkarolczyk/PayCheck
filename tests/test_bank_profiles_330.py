from bank_profiles_330 import classify_payment_type, convert_with_mapping, detect_profile


def test_detects_generic_polish_bank_profile():
    headers = ["Data operacji", "Kwota", "Kontrahent", "Tytuł", "Saldo"]
    result = detect_profile(headers)
    assert result["ready"] is True
    assert result["confidence"] >= 80
    assert result["mapping"]["date"] == "Data operacji"
    assert result["mapping"]["amount"] == "Kwota"


def test_payment_type_classification():
    assert classify_payment_type("Płatność BLIK sklep") == "BLIK"
    assert classify_payment_type("Płatność kartą VISA") == "KARTA"
    assert classify_payment_type("Polecenie zapłaty energia") == "POLECENIE ZAPŁATY"
    assert classify_payment_type("Przelew wychodzący") == "PRZELEW"


def test_conversion_preserves_raw_bank_fields():
    headers = ["Data operacji", "Kwota", "Kontrahent", "Opis", "Saldo"]
    rows = [["2026-09-10", "-123,45", "SKLEP", "Płatność kartą VISA", "1000,00"]]
    mapping = {
        "date": "Data operacji",
        "amount": "Kwota",
        "counterparty": "Kontrahent",
        "title": "Opis",
        "balance": "Saldo",
    }
    result = convert_with_mapping(headers, rows, mapping, profile_name="Test Bank", source_file="test.csv")
    assert len(result) == 1
    tx = result[0]
    assert tx["payment_type"] == "KARTA"
    assert tx["bank_profile"] == "Test Bank"
    assert tx["source_file"] == "test.csv"
    assert tx["bank_raw"]["Kwota"] == "-123,45"
    assert tx["bank_raw_amount"] == "-123,45"
    assert tx["bank_raw_date"] == "2026-09-10"


def test_internal_transfer_hint():
    headers = ["Data", "Kwota", "Opis"]
    rows = [["2026-09-10", "-500,00", "Przelew własny między rachunkami"]]
    mapping = {"date": "Data", "amount": "Kwota", "title": "Opis"}
    result = convert_with_mapping(headers, rows, mapping, profile_name="Test")
    assert result[0]["is_internal_transfer"] is True
