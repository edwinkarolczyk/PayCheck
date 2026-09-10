from __future__ import annotations

import re
from difflib import SequenceMatcher

from matcher import MatchSettings, normalize_text, parse_amount, parse_date


MONTHS = {
    "styczen": 1, "styczeń": 1,
    "luty": 2,
    "marzec": 3,
    "kwiecien": 4, "kwiecień": 4,
    "maj": 5,
    "czerwiec": 6,
    "lipiec": 7, "lipec": 7, "lip": 7,
    "sierpien": 8, "sierpień": 8,
    "wrzesien": 9, "wrzesień": 9,
    "pazdziernik": 10, "październik": 10,
    "listopad": 11,
    "grudzien": 12, "grudzień": 12,
}


def _sheet_month_year(name: str) -> tuple[int | None, int | None]:
    text = normalize_text(name)
    month = next((value for key, value in MONTHS.items() if normalize_text(key) in text), None)
    years = re.findall(r"(?<!\d)(20\d{2}|\d{2})(?!\d)", text)
    year = None
    if years:
        raw = int(years[-1])
        year = raw if raw >= 2000 else 2000 + raw
    return month, year


def _text_similarity(item: dict, transaction: dict) -> float:
    wanted = normalize_text(
        " ".join(
            str(item.get(key, "") or "")
            for key in ("institution", "display_name", "counterparty")
        )
    )
    got = normalize_text(
        " ".join(
            str(transaction.get(key, "") or "")
            for key in ("counterparty", "title", "description")
        )
    )
    if not wanted or not got:
        return 0.0
    wanted_tokens = [t for t in wanted.split() if len(t) >= 3]
    if any(token in got for token in wanted_tokens):
        return 1.0
    return SequenceMatcher(None, wanted, got).ratio()


def _same_sheet_month(item: dict, transaction: dict) -> bool:
    month, year = _sheet_month_year(str(item.get("source_sheet", "")))
    if month is None:
        return True
    tx_date = parse_date(transaction.get("date"))
    if tx_date is None:
        return True
    if tx_date.month != month:
        return False
    return year is None or tx_date.year == year


def _direction_matches(item: dict, actual: float) -> bool:
    entry_type = item.get("entry_type", "expense")
    if entry_type == "income":
        return actual > 0
    return actual < 0


def _budget_score(item: dict, transaction: dict, settings: MatchSettings) -> dict:
    expected = parse_amount(item.get("amount"))
    actual = parse_amount(transaction.get("amount"))
    if (
        expected is None
        or actual is None
        or not _same_sheet_month(item, transaction)
        or not _direction_matches(item, actual)
    ):
        return {"score": 0, "amount_diff": None}

    expected_abs = abs(expected)
    actual_abs = abs(actual)
    diff = abs(actual_abs - expected_abs)
    allowed = max(
        settings.amount_absolute_tolerance,
        expected_abs * settings.amount_percent_tolerance / 100,
    )
    amount_score = 1.0 if allowed <= 0 and diff == 0 else max(0.0, 1.0 - diff / max(allowed, 0.01))
    text_score = _text_similarity(item, transaction)
    score = round(amount_score * 70 + text_score * 30)
    return {
        "score": score,
        "amount_diff": round(actual_abs - expected_abs, 2),
    }


def match_budget(items: list[dict], transactions: list[dict], settings: MatchSettings) -> list[dict]:
    used: set[int] = set()
    results: list[dict] = []

    for item in items:
        best_idx = None
        best = {"score": 0, "amount_diff": None}
        for idx, transaction in enumerate(transactions):
            if idx in used:
                continue
            meta = _budget_score(item, transaction, settings)
            if meta["score"] > best["score"]:
                best_idx, best = idx, meta

        row = dict(item)
        if best_idx is None or best["score"] < 55:
            row.update({
                "status": "BRAK",
                "match_score": best["score"],
                "bank_date": "",
                "bank_amount": "",
                "bank_counterparty": "",
                "bank_title": "",
                "amount_diff": best.get("amount_diff", ""),
                "days_diff": "",
            })
        else:
            transaction = transactions[best_idx]
            used.add(best_idx)
            status = "OPŁACONA" if best["score"] >= 85 else "DO SPRAWDZENIA"
            row.update({
                "status": status,
                "match_score": best["score"],
                "bank_date": transaction.get("date", ""),
                "bank_amount": transaction.get("amount", ""),
                "bank_counterparty": transaction.get("counterparty", ""),
                "bank_title": transaction.get("title", ""),
                "amount_diff": best.get("amount_diff", ""),
                "days_diff": "",
            })
        results.append(row)

    return results
