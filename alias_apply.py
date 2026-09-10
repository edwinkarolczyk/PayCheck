from __future__ import annotations

from advanced_features import alias_bonus, load_aliases
from budget_matcher import _same_sheet_month
from matcher import MatchSettings, parse_amount


def apply_alias_matches(
    results: list[dict], transactions: list[dict], settings: MatchSettings
) -> int:
    aliases = load_aliases()
    if not aliases:
        return 0

    used = {
        (str(row.get("bank_date")), round(abs(parse_amount(row.get("bank_amount")) or 0), 2))
        for row in results
        if row.get("bank_date") not in (None, "")
    }
    changed = 0

    for row in results:
        if row.get("status") == "OPŁACONA":
            continue
        expected = abs(parse_amount(row.get("amount")) or 0)
        allowed = max(
            settings.amount_absolute_tolerance,
            expected * settings.amount_percent_tolerance / 100,
        )
        best = None
        for tx in transactions:
            tx_key = (
                str(tx.get("date")),
                round(abs(parse_amount(tx.get("amount")) or 0), 2),
            )
            if tx_key in used or alias_bonus(row, tx, aliases) <= 0:
                continue
            if row.get("source_type") == "budget" and not _same_sheet_month(row, tx):
                continue
            actual = parse_amount(tx.get("amount"))
            if actual is None:
                continue
            if row.get("entry_type") == "income" and actual <= 0:
                continue
            if row.get("entry_type", "expense") != "income" and actual >= 0:
                continue
            diff = abs(abs(actual) - expected)
            if best is None or diff < best[0]:
                best = (diff, tx, tx_key)

        if best is None:
            continue
        diff, tx, tx_key = best
        status = "OPŁACONA" if diff <= allowed else "DO SPRAWDZENIA"
        row.update(
            {
                "status": status,
                "match_score": 100 if status == "OPŁACONA" else 82,
                "match_kind": "ALIAS",
                "bank_date": tx.get("date", ""),
                "bank_amount": tx.get("amount", ""),
                "bank_counterparty": tx.get("counterparty", ""),
                "bank_title": tx.get("title", ""),
                "amount_diff": round(abs(parse_amount(tx.get("amount")) or 0) - expected, 2),
            }
        )
        used.add(tx_key)
        changed += 1

    return changed
