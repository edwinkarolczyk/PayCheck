from __future__ import annotations

from collections import defaultdict
from datetime import date

from installment_store import load_installments, months_left
from matcher import parse_amount


def _amount(row: dict) -> float:
    return abs(parse_amount(row.get("amount")) or 0.0)


def home_dashboard(items: list[dict], results: list[dict]) -> dict:
    income = sum(_amount(row) for row in items if row.get("entry_type") == "income")
    expenses = sum(_amount(row) for row in items if row.get("entry_type") != "income")

    paid = sum(
        _amount(row)
        for row in results
        if row.get("entry_type") != "income" and row.get("status") == "OPŁACONA"
    )
    review = sum(
        _amount(row)
        for row in results
        if row.get("entry_type") != "income" and row.get("status") == "DO SPRAWDZENIA"
    )
    missing = sum(
        _amount(row)
        for row in results
        if row.get("entry_type") != "income" and row.get("status") == "BRAK"
    )

    installments = [row for row in load_installments() if row.get("active", True)]
    installment_monthly = round(sum(float(row.get("monthly") or 0) for row in installments), 2)
    installment_left = 0.0
    for row in installments:
        left = months_left(row)
        if left is not None:
            installment_left += left * float(row.get("monthly") or 0)

    by_bank: dict[str, float] = defaultdict(float)
    for row in installments:
        bank = str(row.get("bank") or "Inny bank").strip() or "Inny bank"
        by_bank[bank] += float(row.get("monthly") or 0)

    attention = []
    for row in results:
        if row.get("status") not in {"BRAK", "DO SPRAWDZENIA"}:
            continue
        attention.append(
            {
                "name": row.get("display_name") or row.get("invoice_no", ""),
                "amount": _amount(row),
                "status": row.get("status", ""),
            }
        )

    upcoming = []
    today = date.today()
    for row in installments:
        left = months_left(row, today)
        upcoming.append(
            {
                "name": row.get("name", ""),
                "bank": row.get("bank", ""),
                "monthly": round(float(row.get("monthly") or 0), 2),
                "payment_day": int(row.get("payment_day") or 1),
                "months_left": left,
            }
        )
    upcoming.sort(key=lambda row: (row["payment_day"], row["name"].lower()))

    progress = 0.0 if expenses <= 0 else min(100.0, paid / expenses * 100)
    remaining = max(0.0, expenses - paid)

    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "paid": round(paid, 2),
        "review": round(review, 2),
        "missing": round(missing, 2),
        "remaining": round(remaining, 2),
        "balance_plan": round(income - expenses, 2),
        "progress": round(progress, 1),
        "installment_monthly": installment_monthly,
        "installment_left": round(installment_left, 2),
        "installment_count": len(installments),
        "banks": dict(sorted((name, round(value, 2)) for name, value in by_bank.items())),
        "attention": attention,
        "upcoming": upcoming,
    }
