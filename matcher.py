from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Iterable


@dataclass
class MatchSettings:
    days_tolerance: int = 5
    amount_percent_tolerance: float = 3.0
    amount_absolute_tolerance: float = 20.0
    paid_score: int = 90
    review_score: int = 70


def normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    replacements = {
        "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
        "ó": "o", "ś": "s", "ż": "z", "ź": "z",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return " ".join(text.replace(".", " ").replace(",", " ").split())


def parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def parse_amount(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        return None
    text = str(value).strip().replace(" ", "").replace("zł", "").replace("PLN", "")
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _name_score(a: object, b: object) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _amount_score(expected: float, actual: float, settings: MatchSettings) -> tuple[float, float]:
    expected_abs = abs(expected)
    actual_abs = abs(actual)
    diff = abs(expected_abs - actual_abs)
    allowed = max(settings.amount_absolute_tolerance, expected_abs * settings.amount_percent_tolerance / 100)
    if allowed <= 0:
        return (1.0 if diff == 0 else 0.0), diff
    return max(0.0, 1.0 - diff / allowed), diff


def _date_score(expected: date | None, actual: date | None, settings: MatchSettings) -> tuple[float, int | None]:
    if not expected or not actual:
        return 0.0, None
    delta = abs((actual - expected).days)
    if delta > settings.days_tolerance:
        return 0.0, delta
    if settings.days_tolerance == 0:
        return 1.0, delta
    return 1.0 - delta / (settings.days_tolerance + 1), delta


def score_pair(invoice: dict, transaction: dict, settings: MatchSettings) -> dict:
    amount_expected = parse_amount(invoice.get("amount"))
    amount_actual = parse_amount(transaction.get("amount"))
    if amount_expected is None or amount_actual is None:
        return {"score": 0, "amount_diff": None, "days_diff": None}

    amount_score, _ = _amount_score(amount_expected, amount_actual, settings)
    date_score, days_diff = _date_score(parse_date(invoice.get("date")), parse_date(transaction.get("date")), settings)
    name_score = _name_score(invoice.get("counterparty"), transaction.get("counterparty"))

    invoice_no = normalize_text(invoice.get("invoice_no"))
    title = normalize_text(transaction.get("title"))
    invoice_bonus = 1.0 if invoice_no and invoice_no in title else 0.0

    score = round(
        amount_score * 40
        + date_score * 30
        + name_score * 20
        + invoice_bonus * 10
    )
    return {
        "score": score,
        "amount_diff": round(abs(amount_actual) - abs(amount_expected), 2),
        "days_diff": days_diff,
        "name_similarity": round(name_score * 100),
    }


def match_invoices(invoices: Iterable[dict], transactions: Iterable[dict], settings: MatchSettings) -> list[dict]:
    transactions = list(transactions)
    used: set[int] = set()
    results: list[dict] = []

    for invoice in invoices:
        best_idx = None
        best_meta = {"score": 0}
        for idx, transaction in enumerate(transactions):
            if idx in used:
                continue
            meta = score_pair(invoice, transaction, settings)
            if meta["score"] > best_meta["score"]:
                best_idx, best_meta = idx, meta

        row = dict(invoice)
        if best_idx is None or best_meta["score"] < settings.review_score:
            row.update({
                "status": "BRAK",
                "match_score": best_meta.get("score", 0),
                "bank_date": "",
                "bank_amount": "",
                "bank_counterparty": "",
                "bank_title": "",
                "amount_diff": best_meta.get("amount_diff", ""),
                "days_diff": best_meta.get("days_diff", ""),
            })
        else:
            transaction = transactions[best_idx]
            used.add(best_idx)
            status = "OPŁACONA" if best_meta["score"] >= settings.paid_score else "DO SPRAWDZENIA"
            row.update({
                "status": status,
                "match_score": best_meta["score"],
                "bank_date": transaction.get("date", ""),
                "bank_amount": transaction.get("amount", ""),
                "bank_counterparty": transaction.get("counterparty", ""),
                "bank_title": transaction.get("title", ""),
                "amount_diff": best_meta.get("amount_diff", ""),
                "days_diff": best_meta.get("days_diff", ""),
            })
        results.append(row)

    return results
