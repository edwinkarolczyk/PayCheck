from __future__ import annotations

from collections import defaultdict

from matcher import parse_amount


def summarize_budget(items: list[dict]) -> dict:
    categories: dict[str, float] = defaultdict(float)
    banks: dict[str, float] = defaultdict(float)
    income_total = 0.0
    expense_total = 0.0

    for item in items:
        amount = parse_amount(item.get("amount"))
        if amount is None:
            continue
        amount = abs(amount)
        category = str(item.get("category") or "Pozostałe")
        categories[category] += amount

        if item.get("entry_type") == "income":
            income_total += amount
        else:
            expense_total += amount

        bank = str(item.get("bank") or "").strip()
        if bank:
            banks[bank] += amount

    return {
        "income_total": round(income_total, 2),
        "expense_total": round(expense_total, 2),
        "balance": round(income_total - expense_total, 2),
        "categories": dict(sorted((name, round(value, 2)) for name, value in categories.items())),
        "banks": dict(sorted((name, round(value, 2)) for name, value in banks.items())),
        "installments_total": round(sum(banks.values()), 2),
    }
