from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime
from pathlib import Path

from matcher import normalize_text, parse_date

MONTHS = {
    "styczen": 1, "luty": 2, "marzec": 3, "kwiecien": 4, "maj": 5, "czerwiec": 6,
    "lipiec": 7, "sierpien": 8, "wrzesien": 9, "pazdziernik": 10, "listopad": 11, "grudzien": 12,
}


def default_path() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck" / "installments.json"


def load_installments(path: str | Path | None = None) -> list[dict]:
    target = Path(path) if path else default_path()
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def save_installments(rows: list[dict], path: str | Path | None = None) -> None:
    target = Path(path) if path else default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_installment(data: dict, path: str | Path | None = None) -> dict:
    rows = load_installments(path)
    row = dict(data)
    row["id"] = row.get("id") or f"RATA-{uuid.uuid4().hex[:8].upper()}"
    row["name"] = str(row.get("name", "")).strip()
    row["bank"] = str(row.get("bank", "")).strip()
    row["monthly"] = round(float(row.get("monthly") or 0), 2)
    row["payment_day"] = max(1, min(31, int(row.get("payment_day") or 1)))
    row["start_date"] = str(row.get("start_date") or "")
    row["end_date"] = str(row.get("end_date") or "")
    row["interest_type"] = str(row.get("interest_type") or "0%")
    row["interest_rate"] = float(row.get("interest_rate") or 0)
    row["total_installments"] = int(row.get("total_installments") or 0)
    row["active"] = bool(row.get("active", True))
    row["note"] = str(row.get("note", ""))
    if not row["name"] or row["monthly"] <= 0:
        raise ValueError("Nazwa raty i miesięczna kwota są wymagane.")
    replaced = False
    for idx, old in enumerate(rows):
        if old.get("id") == row["id"]:
            rows[idx] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)
    save_installments(rows, path)
    return row


def remove_installment(installment_id: str, path: str | Path | None = None) -> bool:
    rows = load_installments(path)
    new_rows = [row for row in rows if row.get("id") != installment_id]
    if len(new_rows) == len(rows):
        return False
    save_installments(new_rows, path)
    return True


def set_installment_active(installment_id: str, active: bool, path: str | Path | None = None) -> bool:
    rows = load_installments(path)
    changed = False
    for row in rows:
        if row.get("id") == installment_id:
            row["active"] = bool(active)
            changed = True
            break
    if changed:
        save_installments(rows, path)
    return changed


def _sheet_month_year(label: str) -> tuple[int | None, int | None]:
    text = normalize_text(label)
    month = next((value for key, value in MONTHS.items() if key in text), None)
    match = re.search(r"(?<!\d)(20\d{2}|\d{2})(?!\d)", text)
    year = None
    if match:
        raw = int(match.group(1))
        year = raw if raw >= 2000 else 2000 + raw
    return month, year


def active_for_month(row: dict, month_label: str) -> bool:
    if not row.get("active", True):
        return False
    month, year = _sheet_month_year(month_label)
    if not month or not year:
        return True
    current = date(year, month, 1)
    start = parse_date(row.get("start_date"))
    end = parse_date(row.get("end_date"))
    if start and current < date(start.year, start.month, 1):
        return False
    if end and current > date(end.year, end.month, 1):
        return False
    return True


def months_left(row: dict, today: date | None = None) -> int | None:
    end = parse_date(row.get("end_date"))
    if not end:
        return None
    now = today or date.today()
    diff = (end.year - now.year) * 12 + end.month - now.month
    return max(0, diff + 1)


def estimated_left(row: dict, today: date | None = None) -> float | None:
    left = months_left(row, today)
    if left is None:
        return None
    return round(left * float(row.get("monthly") or 0), 2)


def to_budget_items(rows: list[dict], month_label: str) -> list[dict]:
    items = []
    for idx, row in enumerate(rows, start=1):
        if not active_for_month(row, month_label):
            continue
        items.append({
            "invoice_no": f"MAN-{row.get('id', idx)}",
            "counterparty": " ".join(part for part in (row.get("bank", ""), row.get("name", "")) if part),
            "display_name": row.get("name", ""),
            "institution": row.get("bank", ""),
            "amount": float(row.get("monthly") or 0),
            "date": "",
            "end_date": row.get("end_date", ""),
            "source_type": "budget",
            "source_sheet": month_label,
            "source_row": f"manual:{row.get('id', idx)}",
            "entry_type": "expense",
            "category": "Raty / banki",
            "bank": row.get("bank", ""),
            "manual_installment_id": row.get("id", ""),
            "payment_day": row.get("payment_day", 1),
        })
    return items
