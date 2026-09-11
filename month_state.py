from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path

from matcher import normalize_text, parse_amount, parse_date


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def months_dir() -> Path:
    return app_dir() / "months"


def _slug(value: str) -> str:
    text = normalize_text(value)
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "miesiac"


def state_path(month_label: str) -> Path:
    return months_dir() / f"{_slug(month_label)}.json"


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def transaction_key(tx: dict) -> tuple:
    tx_date = parse_date(tx.get("date"))
    amount = parse_amount(tx.get("amount"))
    return (
        tx_date.isoformat() if tx_date else str(tx.get("date", "") or ""),
        round(amount or 0.0, 2),
        normalize_text(tx.get("counterparty", "")),
        normalize_text(tx.get("title") or tx.get("description", "")),
    )


def merge_transactions(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], int]:
    merged = [dict(row) for row in existing]
    seen = {transaction_key(row) for row in merged}
    added = 0
    for tx in incoming:
        key = transaction_key(tx)
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(tx))
        added += 1
    return merged, added


def save_month_state(
    month_label: str,
    *,
    source_mode: str,
    budget_path: str | None,
    budget_sheet: str | None,
    items: list[dict],
    transactions: list[dict],
    results: list[dict],
    statement_files: list[str] | None = None,
) -> Path:
    target = state_path(month_label)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "month_label": month_label,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "source_mode": source_mode,
        "budget_path": budget_path or "",
        "budget_sheet": budget_sheet or "",
        "statement_files": sorted(set(statement_files or [])),
        "items": _json_value(items),
        "transactions": _json_value(transactions),
        "results": _json_value(results),
    }
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def load_month_state(month_label: str) -> dict | None:
    target = state_path(month_label)
    if not target.exists():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def list_month_states() -> list[dict]:
    root = months_dir()
    if not root.exists():
        return []
    states: list[dict] = []
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        states.append(
            {
                "month_label": data.get("month_label") or path.stem,
                "updated_at": data.get("updated_at", ""),
                "statement_count": len(data.get("statement_files", [])),
                "transaction_count": len(data.get("transactions", [])),
            }
        )
    return sorted(states, key=lambda row: str(row.get("updated_at", "")), reverse=True)


def bank_confirmation_label(row: dict) -> str:
    status = str(row.get("status", ""))
    has_bank = bool(row.get("bank_date") not in (None, "") or row.get("bank_amount") not in (None, ""))
    manual = row.get("manual_decision")

    if status == "OPŁACONA" and has_bank and manual == "approved":
        return "POTWIERDZONA RĘCZNIE"
    if status == "OPŁACONA" and has_bank:
        return "POTWIERDZONA W BANKU"
    if status == "OPŁACONA" and not has_bank:
        return "RĘCZNA — BRAK POTWIERDZENIA BANKU"
    if status == "DO SPRAWDZENIA":
        return "DO ZATWIERDZENIA"
    if status == "BRAK":
        return "BRAK POTWIERDZENIA W BANKU"
    return status


def review_rows(results: list[dict]) -> list[dict]:
    return [row for row in results if row.get("status") == "DO SPRAWDZENIA"]
