from __future__ import annotations

import json
import os
from itertools import combinations
from pathlib import Path

from matcher import MatchSettings, normalize_text, parse_amount, parse_date


def _app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def _alias_path() -> Path:
    return _app_dir() / "aliases.json"


def _item_key(row: dict) -> str:
    return "|".join(
        (
            normalize_text(row.get("institution", "")),
            normalize_text(row.get("display_name") or row.get("invoice_no", "")),
        )
    )


def _tx_signature(tx: dict) -> str:
    return normalize_text(
        " ".join(
            str(tx.get(key, "") or "")
            for key in ("counterparty", "title", "description")
        )
    )


def load_aliases(path: str | Path | None = None) -> dict[str, list[str]]:
    target = Path(path) if path else _alias_path()
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def remember_alias(row: dict, path: str | Path | None = None) -> str:
    text = normalize_text(
        " ".join(
            str(row.get(key, "") or "")
            for key in ("bank_counterparty", "bank_title")
        )
    )
    if not text:
        raise ValueError("Brak opisu bankowego do zapamiętania.")
    key = _item_key(row)
    target = Path(path) if path else _alias_path()
    aliases = load_aliases(target)
    values = aliases.setdefault(key, [])
    if text not in values:
        values.append(text)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(aliases, ensure_ascii=False, indent=2), encoding="utf-8")
    return text


def alias_bonus(item: dict, transaction: dict, aliases: dict[str, list[str]]) -> int:
    saved = aliases.get(_item_key(item), [])
    if not saved:
        return 0
    text = _tx_signature(transaction)
    return 30 if any(alias and alias in text for alias in saved) else 0


def filter_results(results: list[dict], mode: str) -> list[dict]:
    if mode == "Wszystkie":
        return list(results)
    if mode == "Opłacone":
        return [r for r in results if r.get("status") == "OPŁACONA"]
    if mode == "Do sprawdzenia":
        return [r for r in results if r.get("status") == "DO SPRAWDZENIA"]
    if mode == "Brak":
        return [r for r in results if r.get("status") == "BRAK"]
    if mode == "Ręczne":
        return [r for r in results if r.get("manual_decision")]
    return list(results)


def item_history(history: list[dict], row: dict) -> list[dict]:
    name = normalize_text(row.get("display_name") or row.get("invoice_no", ""))
    institution = normalize_text(row.get("institution") or row.get("counterparty", ""))
    found: list[dict] = []
    for snap in history:
        for old in snap.get("rows", []):
            if normalize_text(old.get("name", "")) == name and normalize_text(old.get("institution", "")) == institution:
                found.append({
                    "created_at": snap.get("created_at", ""),
                    "sheet": snap.get("source_sheet") or snap.get("source_label", ""),
                    "amount": old.get("amount", ""),
                    "status": old.get("status", ""),
                    "bank_amount": old.get("bank_amount", ""),
                })
                break
    return found


def _direction_ok(item: dict, tx: dict) -> bool:
    amount = parse_amount(tx.get("amount"))
    if amount is None:
        return False
    return amount > 0 if item.get("entry_type") == "income" else amount < 0


def _same_month(item: dict, tx: dict) -> bool:
    sheet = normalize_text(item.get("source_sheet", ""))
    months = {
        "styczen": 1, "luty": 2, "marzec": 3, "kwiecien": 4,
        "maj": 5, "czerwiec": 6, "lipiec": 7, "sierpien": 8,
        "wrzesien": 9, "pazdziernik": 10, "listopad": 11, "grudzien": 12,
    }
    wanted = next((m for n, m in months.items() if n in sheet), None)
    date = parse_date(tx.get("date"))
    return wanted is None or date is None or date.month == wanted


def _used_tx_keys(results: list[dict]) -> set[tuple]:
    used = set()
    for row in results:
        if row.get("bank_date") in (None, ""):
            continue
        used.add((str(row.get("bank_date")), round(abs(parse_amount(row.get("bank_amount")) or 0), 2)))
    return used


def detect_split_and_grouped(
    results: list[dict], transactions: list[dict], settings: MatchSettings
) -> int:
    """Conservative detector. Suggested matches remain DO SPRAWDZENIA."""
    changed = 0
    used = _used_tx_keys(results)
    missing = [r for r in results if r.get("status") == "BRAK" and r.get("source_type") == "budget"]
    free = [
        tx for tx in transactions
        if (str(tx.get("date")), round(abs(parse_amount(tx.get("amount")) or 0), 2)) not in used
    ]

    # One budget item paid with 2-3 transfers.
    for row in missing:
        expected = abs(parse_amount(row.get("amount")) or 0)
        allowed = max(settings.amount_absolute_tolerance, expected * settings.amount_percent_tolerance / 100)
        candidates = [tx for tx in free if _direction_ok(row, tx) and _same_month(row, tx)]
        match = None
        for size in (2, 3):
            for combo in combinations(candidates[:20], size):
                total = sum(abs(parse_amount(tx.get("amount")) or 0) for tx in combo)
                if abs(total - expected) <= allowed:
                    match = combo
                    break
            if match:
                break
        if not match:
            continue
        total = sum(abs(parse_amount(tx.get("amount")) or 0) for tx in match)
        row.update({
            "status": "DO SPRAWDZENIA",
            "match_kind": "PODZIELONA",
            "match_score": 80,
            "bank_date": ", ".join(str(tx.get("date", "")) for tx in match),
            "bank_amount": round(total, 2),
            "bank_counterparty": " + ".join(str(tx.get("counterparty", "")) for tx in match),
            "bank_title": "Płatność podzielona: " + " | ".join(str(tx.get("title", "")) for tx in match),
            "amount_diff": round(total - expected, 2),
        })
        for tx in match:
            if tx in free:
                free.remove(tx)
        changed += 1

    # One transfer paying 2-3 budget items.
    missing = [r for r in results if r.get("status") == "BRAK" and r.get("source_type") == "budget"]
    for tx in list(free):
        amount = abs(parse_amount(tx.get("amount")) or 0)
        possible = [r for r in missing if _direction_ok(r, tx) and _same_month(r, tx)]
        selected = None
        for size in (2, 3):
            for combo in combinations(possible[:20], size):
                expected = sum(abs(parse_amount(r.get("amount")) or 0) for r in combo)
                allowed = max(settings.amount_absolute_tolerance, expected * settings.amount_percent_tolerance / 100)
                if abs(amount - expected) <= allowed:
                    selected = combo
                    break
            if selected:
                break
        if not selected:
            continue
        names = ", ".join(str(r.get("display_name", "")) for r in selected)
        for row in selected:
            row.update({
                "status": "DO SPRAWDZENIA",
                "match_kind": "ŁĄCZONA",
                "match_score": 78,
                "bank_date": tx.get("date", ""),
                "bank_amount": tx.get("amount", ""),
                "bank_counterparty": tx.get("counterparty", ""),
                "bank_title": f"Płatność łączona dla: {names}",
                "amount_diff": "",
            })
            changed += 1
        free.remove(tx)
        missing = [r for r in missing if r not in selected]
    return changed


def trend_for_item(history: list[dict], row: dict, limit: int) -> dict:
    entries = item_history(history, row)[-limit:]
    amounts = [parse_amount(e.get("amount")) for e in entries]
    amounts = [abs(v) for v in amounts if v is not None]
    if not amounts:
        return {"count": 0, "average": 0.0, "min": 0.0, "max": 0.0, "change_percent": None}
    change = None
    if len(amounts) >= 2 and amounts[-2] != 0:
        change = round((amounts[-1] - amounts[-2]) / amounts[-2] * 100, 1)
    return {
        "count": len(amounts),
        "average": round(sum(amounts) / len(amounts), 2),
        "min": round(min(amounts), 2),
        "max": round(max(amounts), 2),
        "change_percent": change,
    }


def dashboard(results: list[dict]) -> dict:
    expenses = [r for r in results if r.get("entry_type") != "income"]
    planned = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses)
    paid_rows = [r for r in expenses if r.get("status") == "OPŁACONA"]
    paid = sum(abs(parse_amount(r.get("amount")) or 0) for r in paid_rows)
    review = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses if r.get("status") == "DO SPRAWDZENIA")
    missing = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses if r.get("status") == "BRAK")
    return {
        "planned": round(planned, 2),
        "paid": round(paid, 2),
        "review": round(review, 2),
        "missing": round(missing, 2),
        "paid_count": len(paid_rows),
        "total_count": len(expenses),
        "paid_percent": round((paid / planned * 100) if planned else 0.0, 1),
    }
