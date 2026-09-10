from matcher import MatchSettings, match_invoices, score_pair


def test_close_amount_and_date_match():
    invoice = {
        "counterparty": "Metalbox Sp. z o.o.",
        "amount": 1000,
        "date": "10.09.2026",
        "invoice_no": "FV/120/26",
    }
    transaction = {
        "counterparty": "METALBOX SP Z O O",
        "amount": 985,
        "date": "12.09.2026",
        "title": "Zapłata FV/120/26",
    }
    meta = score_pair(invoice, transaction, MatchSettings())
    assert meta["score"] >= 70


def test_same_transaction_is_not_used_twice():
    invoices = [
        {"counterparty": "ABC", "amount": 100, "date": "10.09.2026", "invoice_no": "1"},
        {"counterparty": "ABC", "amount": 100, "date": "10.09.2026", "invoice_no": "2"},
    ]
    transactions = [
        {"counterparty": "ABC", "amount": 100, "date": "10.09.2026", "title": "przelew"}
    ]
    results = match_invoices(invoices, transactions, MatchSettings(review_score=1))
    matched = [row for row in results if row["status"] != "BRAK"]
    assert len(matched) == 1
