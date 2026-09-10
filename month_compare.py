from __future__ import annotations

from matcher import normalize_text, parse_amount


def _item_key(item: dict) -> str:
    name = normalize_text(item.get("display_name") or item.get("invoice_no"))
    institution = normalize_text(item.get("institution") or item.get("counterparty"))
    return f"{institution}|{name}"


def compare_months(previous: list[dict], current: list[dict]) -> list[dict]:
    prev_map = {_item_key(item): item for item in previous}
    curr_map = {_item_key(item): item for item in current}
    keys = sorted(set(prev_map) | set(curr_map))
    rows: list[dict] = []

    for key in keys:
        prev = prev_map.get(key)
        curr = curr_map.get(key)
        prev_amount = parse_amount(prev.get("amount")) if prev else None
        curr_amount = parse_amount(curr.get("amount")) if curr else None

        if prev and curr:
            diff = round((curr_amount or 0.0) - (prev_amount or 0.0), 2)
            percent = None
            if prev_amount not in (None, 0):
                percent = round(diff / abs(prev_amount) * 100, 1)
            status = "BEZ ZMIAN" if abs(diff) < 0.01 else ("WZROST" if diff > 0 else "SPADEK")
            source = curr
        elif curr:
            diff = curr_amount
            percent = None
            status = "NOWA"
            source = curr
        else:
            diff = -prev_amount if prev_amount is not None else None
            percent = None
            status = "BRAK W BIEŻĄCYM"
            source = prev

        rows.append(
            {
                "name": source.get("display_name") or source.get("invoice_no", ""),
                "institution": source.get("institution") or source.get("counterparty", ""),
                "previous_amount": prev_amount,
                "current_amount": curr_amount,
                "difference": diff,
                "percent_change": percent,
                "status": status,
            }
        )

    return rows
