from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from matcher import normalize_text, parse_amount, parse_date


def default_decisions_path() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"
    return base / "decisions.json"


def load_decisions(path: str | Path | None = None) -> dict[str, dict]:
    target = Path(path) if path else default_decisions_path()
    if not target.exists():
        return {}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _item_part(row: dict) -> str:
    if row.get("source_type") == "budget" and row.get("source_row"):
        return f"budget:{row.get('source_sheet', '')}:{row.get('source_row')}"
    return "|".join(
        normalize_text(row.get(key, ""))
        for key in ("invoice_no", "display_name", "institution", "counterparty")
    )


def _transaction_part(row: dict) -> str:
    tx_date = parse_date(row.get("bank_date"))
    amount = parse_amount(row.get("bank_amount"))
    return "|".join(
        (
            tx_date.isoformat() if tx_date else str(row.get("bank_date", "") or ""),
            f"{abs(amount):.2f}" if amount is not None else "",
            normalize_text(row.get("bank_counterparty", "")),
            normalize_text(row.get("bank_title", "")),
        )
    )


def decision_key(row: dict) -> str:
    saved = row.get("_decision_key")
    if saved:
        return str(saved)
    return f"{_item_part(row)}::{_transaction_part(row)}"


def save_decision(
    row: dict,
    decision: str,
    path: str | Path | None = None,
) -> str:
    if decision not in {"approved", "rejected"}:
        raise ValueError("Nieznana decyzja ręczna.")
    key = decision_key(row)
    target = Path(path) if path else default_decisions_path()
    decisions = load_decisions(target)
    decisions[key] = {
        "decision": decision,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "name": row.get("display_name") or row.get("invoice_no", ""),
        "institution": row.get("institution") or row.get("counterparty", ""),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return key


def remove_decision(row: dict, path: str | Path | None = None) -> bool:
    key = decision_key(row)
    target = Path(path) if path else default_decisions_path()
    decisions = load_decisions(target)
    if key not in decisions:
        return False
    decisions.pop(key, None)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(decisions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def apply_decisions(results: list[dict], path: str | Path | None = None) -> int:
    decisions = load_decisions(path)
    applied = 0
    for row in results:
        # Ręczna decyzja dotyczy konkretnej pozycji i konkretnego dopasowanego przelewu.
        if not row.get("bank_date") and not row.get("bank_amount"):
            continue
        key = decision_key(row)
        saved = decisions.get(key)
        if not saved:
            continue
        row["_decision_key"] = key
        row["manual_decision"] = saved.get("decision", "")
        if saved.get("decision") == "approved":
            row["status"] = "OPŁACONA"
            applied += 1
        elif saved.get("decision") == "rejected":
            row["rejected_bank_date"] = row.get("bank_date", "")
            row["rejected_bank_amount"] = row.get("bank_amount", "")
            row["rejected_bank_counterparty"] = row.get("bank_counterparty", "")
            row["rejected_bank_title"] = row.get("bank_title", "")
            row["status"] = "BRAK"
            row["bank_date"] = ""
            row["bank_amount"] = ""
            row["bank_counterparty"] = ""
            row["bank_title"] = ""
            row["amount_diff"] = ""
            row["days_diff"] = ""
            applied += 1
    return applied
