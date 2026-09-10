from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path


def default_history_path() -> Path:
    base = Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"
    return base / "history.json"


def load_history(path: str | Path | None = None) -> list[dict]:
    target = Path(path) if path else default_history_path()
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _item_key(row: dict) -> str:
    if row.get("source_type") == "budget" and row.get("source_row"):
        return f"budget:{row.get('source_sheet', '')}:{row.get('source_row')}"
    return "|".join(
        str(row.get(key, "") or "").strip().lower()
        for key in ("invoice_no", "display_name", "institution", "counterparty", "amount")
    )


def make_snapshot(
    results: list[dict],
    *,
    source_mode: str,
    source_label: str,
    source_sheet: str | None = None,
) -> dict:
    rows = []
    for row in results:
        rows.append(
            {
                "key": _item_key(row),
                "name": row.get("display_name") or row.get("invoice_no", ""),
                "institution": row.get("institution") or row.get("counterparty", ""),
                "amount": row.get("amount", ""),
                "status": row.get("status", ""),
                "match_score": row.get("match_score", ""),
                "bank_date": str(row.get("bank_date", "") or ""),
                "bank_amount": row.get("bank_amount", ""),
            }
        )

    paid = sum(row["status"] == "OPŁACONA" for row in rows)
    review = sum(row["status"] == "DO SPRAWDZENIA" for row in rows)
    missing = sum(row["status"] == "BRAK" for row in rows)
    context = f"{source_mode}:{source_sheet or source_label}"
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "context": context,
        "source_mode": source_mode,
        "source_label": source_label,
        "source_sheet": source_sheet or "",
        "summary": {
            "total": len(rows),
            "paid": paid,
            "review": review,
            "missing": missing,
        },
        "rows": rows,
    }


def previous_snapshot(history: list[dict], snapshot: dict) -> dict | None:
    context = snapshot.get("context")
    for item in reversed(history):
        if item.get("context") == context:
            return item
    return None


def compare_snapshots(previous: dict | None, current: dict) -> dict:
    if not previous:
        return {"newly_paid": [], "became_missing": [], "changed": 0}

    old = {row.get("key"): row for row in previous.get("rows", [])}
    new = {row.get("key"): row for row in current.get("rows", [])}
    newly_paid = []
    became_missing = []
    changed = 0

    for key, row in new.items():
        before = old.get(key, {})
        old_status = before.get("status")
        new_status = row.get("status")
        if old_status != new_status:
            changed += 1
        if new_status == "OPŁACONA" and old_status != "OPŁACONA":
            newly_paid.append(row.get("name", key))
        if new_status == "BRAK" and old_status not in (None, "BRAK"):
            became_missing.append(row.get("name", key))

    return {
        "newly_paid": newly_paid,
        "became_missing": became_missing,
        "changed": changed,
    }


def append_snapshot(snapshot: dict, path: str | Path | None = None, limit: int = 200) -> None:
    target = Path(path) if path else default_history_path()
    history = load_history(target)

    # Nie zapisuj drugi raz identycznego wyniku dla tego samego kontekstu.
    previous = previous_snapshot(history, snapshot)
    if previous:
        old_rows = [(r.get("key"), r.get("status"), r.get("bank_amount")) for r in previous.get("rows", [])]
        new_rows = [(r.get("key"), r.get("status"), r.get("bank_amount")) for r in snapshot.get("rows", [])]
        if old_rows == new_rows:
            return

    history.append(snapshot)
    history = history[-max(1, limit):]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
