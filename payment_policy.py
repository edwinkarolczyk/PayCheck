from __future__ import annotations

import json
import os
from pathlib import Path

from budget_manager import payment_match_quality


def _settings_path() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck" / "payment_policy.json"


def load_transfer_tolerance(path: str | Path | None = None) -> float:
    target = Path(path) if path else _settings_path()
    if not target.exists():
        return 2.0
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        value = float(data.get("transfer_tolerance", 2.0))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 2.0
    return max(0.0, min(value, 5.0))


def save_transfer_tolerance(value: float, path: str | Path | None = None) -> float:
    value = max(0.0, min(float(value), 5.0))
    target = Path(path) if path else _settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"transfer_tolerance": value}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return value


def enforce_payment_precision(results: list[dict], transfer_limit: float = 2.0) -> int:
    changed = 0
    for row in results:
        if row.get("status") not in {"OPŁACONA", "DO SPRAWDZENIA"}:
            continue
        if row.get("bank_amount") in (None, ""):
            continue
        tx = {
            "date": row.get("bank_date", ""),
            "amount": row.get("bank_amount", ""),
            "counterparty": row.get("bank_counterparty", ""),
            "title": row.get("bank_title", ""),
            "description": row.get("bank_title", ""),
        }
        quality = payment_match_quality(row.get("amount"), tx, transfer_limit=transfer_limit)
        row["payment_type"] = quality["payment_type"]
        row["payment_tolerance"] = quality["tolerance"]
        row["payment_amount_ok"] = quality["amount_ok"]
        if row.get("status") == "OPŁACONA" and not quality["amount_ok"]:
            row["status"] = "DO SPRAWDZENIA"
            row["match_kind"] = f"RÓŻNICA KWOTY / {quality['payment_type']}"
            changed += 1
    return changed
