from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import math

from matcher import normalize_text, parse_amount, parse_date


KNOWN_BANKS = {
    "mbank": "mBank",
    "santander": "Santander",
    "alior": "Alior",
    "velo": "Velo",
    "pekao": "Pekao",
    "pko": "PKO",
    "ing": "ING",
    "millennium": "Millennium",
}


def classify_payment_type(tx: dict) -> str:
    amount = parse_amount(tx.get("amount")) or 0.0
    text = normalize_text(
        " ".join(
            str(tx.get(key, "") or "")
            for key in ("counterparty", "title", "description")
        )
    )
    if amount > 0:
        return "WPŁYW"
    if "blik" in text:
        return "BLIK"
    if any(token in text for token in ("karta", "card", "visa", "mastercard")):
        return "KARTA"
    if any(token in text for token in ("polecenie zaplaty", "polecenie zapłaty", "direct debit")):
        return "POLECENIE ZAPŁATY"
    if any(token in text for token in ("rata", "kredyt", "pozyczka", "pożyczka")):
        return "RATA / KREDYT"
    if any(token in text for token in ("przelew", "transfer")):
        return "PRZELEW"
    return "PRZELEW / INNE"


def payment_amount_tolerance(payment_type: str) -> float:
    kind = str(payment_type or "").upper()
    if kind == "BLIK":
        return 0.01
    if kind == "KARTA":
        return 0.01
    if kind == "POLECENIE ZAPŁATY":
        return 1.00
    if kind == "RATA / KREDYT":
        return 1.00
    if kind.startswith("PRZELEW"):
        return 2.00
    return 2.00


def payment_match_quality(expected: object, tx: dict, transfer_limit: float = 2.0) -> dict:
    planned = abs(parse_amount(expected) or 0.0)
    actual = abs(parse_amount(tx.get("amount")) or 0.0)
    kind = classify_payment_type(tx)
    tolerance = payment_amount_tolerance(kind)
    if kind.startswith("PRZELEW"):
        tolerance = max(0.0, min(float(transfer_limit), 5.0))
    diff = round(actual - planned, 2)
    return {
        "payment_type": kind,
        "tolerance": tolerance,
        "difference": diff,
        "amount_ok": abs(diff) <= tolerance + 1e-9,
    }


def _result_key(row: dict) -> tuple[str, str]:
    return (
        normalize_text(row.get("institution") or row.get("counterparty", "")),
        normalize_text(row.get("display_name") or row.get("invoice_no", "")),
    )


def budget_overview(items: list[dict], results: list[dict]) -> dict:
    income = 0.0
    expenses = 0.0
    categories: dict[str, float] = defaultdict(float)
    for item in items:
        amount = abs(parse_amount(item.get("amount")) or 0.0)
        if item.get("entry_type") == "income":
            income += amount
        else:
            expenses += amount
            categories[str(item.get("category") or "Pozostałe")] += amount

    paid = review = missing = 0.0
    for row in results:
        if row.get("entry_type") == "income":
            continue
        amount = abs(parse_amount(row.get("amount")) or 0.0)
        status = row.get("status")
        if status == "OPŁACONA":
            paid += amount
        elif status == "DO SPRAWDZENIA":
            review += amount
        elif status == "BRAK":
            missing += amount

    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "balance_plan": round(income - expenses, 2),
        "paid": round(paid, 2),
        "review": round(review, 2),
        "missing": round(missing, 2),
        "remaining": round(max(0.0, expenses - paid), 2),
        "categories": dict(sorted((k, round(v, 2)) for k, v in categories.items())),
    }


def bank_overview(items: list[dict], results: list[dict]) -> list[dict]:
    result_map = {_result_key(row): row for row in results}
    data: dict[str, dict] = {}
    for item in items:
        bank = str(item.get("bank") or "").strip()
        if not bank:
            text = normalize_text(item.get("institution", ""))
            bank = next((label for token, label in KNOWN_BANKS.items() if token in text), "")
        if not bank:
            continue
        rec = data.setdefault(bank, {"bank": bank, "monthly": 0.0, "active": 0, "paid": 0, "missing": 0})
        rec["monthly"] += abs(parse_amount(item.get("amount")) or 0.0)
        rec["active"] += 1
        matched = result_map.get(_result_key(item), {})
        if matched.get("status") == "OPŁACONA":
            rec["paid"] += 1
        elif matched.get("status") == "BRAK":
            rec["missing"] += 1
    rows = []
    for bank in sorted(data):
        row = dict(data[bank])
        row["monthly"] = round(row["monthly"], 2)
        rows.append(row)
    return rows


def _parse_end_date(value: object) -> date | None:
    parsed = parse_date(value)
    if parsed:
        return parsed
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def _months_until(today: date, end: date) -> int:
    if end < today:
        return 0
    months = (end.year - today.year) * 12 + (end.month - today.month)
    if end.day >= today.day:
        months += 1
    return max(0, months)


def installment_overview(items: list[dict], results: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    result_map = {_result_key(row): row for row in results}
    rows: list[dict] = []
    for item in items:
        if str(item.get("category") or "") != "Raty / banki" and not item.get("bank"):
            continue
        monthly = abs(parse_amount(item.get("amount")) or 0.0)
        end = _parse_end_date(item.get("end_date"))
        months_left = _months_until(today, end) if end else None
        estimated_left = round(monthly * months_left, 2) if months_left is not None else None
        matched = result_map.get(_result_key(item), {})
        rows.append(
            {
                "name": item.get("display_name") or item.get("invoice_no", ""),
                "bank": item.get("bank") or item.get("institution", ""),
                "monthly": round(monthly, 2),
                "end_date": end.isoformat() if end else "",
                "months_left": months_left,
                "estimated_left": estimated_left,
                "status": matched.get("status", "BRAK") if results else "—",
                "ends_soon": months_left is not None and 0 < months_left <= 3,
                "finished": months_left == 0 if months_left is not None else False,
            }
        )
    rows.sort(key=lambda row: (row["months_left"] is None, row["months_left"] or math.inf, row["bank"], row["name"]))
    return rows


def transaction_overview(transactions: list[dict], transfer_limit: float = 2.0) -> list[dict]:
    rows = []
    for tx in transactions:
        kind = classify_payment_type(tx)
        tolerance = payment_amount_tolerance(kind)
        if kind.startswith("PRZELEW"):
            tolerance = max(0.0, min(float(transfer_limit), 5.0))
        rows.append(
            {
                "date": tx.get("date", ""),
                "amount": parse_amount(tx.get("amount")) or 0.0,
                "type": kind,
                "tolerance": tolerance,
                "counterparty": tx.get("counterparty", ""),
                "title": tx.get("title") or tx.get("description", ""),
                "source_file": tx.get("source_file", ""),
            }
        )
    return rows


def installment_summary(rows: list[dict]) -> dict:
    monthly = sum(row.get("monthly", 0.0) for row in rows if not row.get("finished"))
    known_left = sum((row.get("estimated_left") or 0.0) for row in rows if row.get("estimated_left") is not None)
    known = sum(row.get("estimated_left") is not None for row in rows)
    soon = sum(bool(row.get("ends_soon")) for row in rows)
    return {
        "active": sum(not row.get("finished") for row in rows),
        "monthly": round(monthly, 2),
        "estimated_left": round(known_left, 2),
        "known_end_dates": known,
        "ending_within_3_months": soon,
    }
