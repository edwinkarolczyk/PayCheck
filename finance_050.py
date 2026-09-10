from __future__ import annotations

import json
import os
import shutil
import statistics
import zipfile
from datetime import date, datetime
from pathlib import Path

from matcher import normalize_text, parse_amount, parse_date


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def rules_path() -> Path:
    return app_dir() / "rules.json"


def load_rules(path: str | Path | None = None) -> list[dict]:
    target = Path(path) if path else rules_path()
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def _row_key(row: dict) -> str:
    return "|".join((
        normalize_text(row.get("institution") or row.get("counterparty")),
        normalize_text(row.get("display_name") or row.get("invoice_no")),
    ))


def remember_rule(row: dict, path: str | Path | None = None) -> dict:
    phrase = normalize_text(" ".join(str(row.get(k, "") or "") for k in ("bank_counterparty", "bank_title")))
    if not phrase:
        raise ValueError("Brak opisu bankowego, z którego można utworzyć regułę.")
    rule = {"item_key": _row_key(row), "phrase": phrase, "enabled": True}
    target = Path(path) if path else rules_path()
    rules = load_rules(target)
    if not any(r.get("item_key") == rule["item_key"] and r.get("phrase") == phrase for r in rules):
        rules.append(rule)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return rule


def apply_rules(results: list[dict], transactions: list[dict], path: str | Path | None = None) -> int:
    rules = [r for r in load_rules(path) if r.get("enabled", True)]
    if not rules:
        return 0
    used = {
        (str(r.get("bank_date")), str(r.get("bank_amount")), normalize_text(r.get("bank_title")))
        for r in results if r.get("bank_date") not in (None, "")
    }
    changed = 0
    for row in results:
        matching_rules = [r for r in rules if r.get("item_key") == _row_key(row)]
        if not matching_rules:
            continue
        for tx in transactions:
            tx_key = (str(tx.get("date")), str(tx.get("amount")), normalize_text(tx.get("title")))
            if tx_key in used:
                continue
            text = normalize_text(" ".join(str(tx.get(k, "") or "") for k in ("counterparty", "title", "description")))
            rule = next((r for r in matching_rules if r.get("phrase") and r["phrase"] in text), None)
            if not rule:
                continue
            actual = parse_amount(tx.get("amount"))
            expected = parse_amount(row.get("amount"))
            if actual is None or expected is None:
                continue
            if row.get("entry_type") == "income" and actual <= 0:
                continue
            if row.get("entry_type") != "income" and actual >= 0:
                continue
            row.update({
                "status": "OPŁACONA",
                "match_score": 100,
                "match_kind": "REGUŁA",
                "bank_date": tx.get("date", ""),
                "bank_amount": tx.get("amount", ""),
                "bank_counterparty": tx.get("counterparty", ""),
                "bank_title": tx.get("title", ""),
                "amount_diff": round(abs(actual) - abs(expected), 2),
            })
            used.add(tx_key)
            changed += 1
            break
    return changed


def _history_amounts(history: list[dict], row: dict, limit: int = 6) -> list[float]:
    name = normalize_text(row.get("display_name") or row.get("invoice_no"))
    inst = normalize_text(row.get("institution") or row.get("counterparty"))
    values: list[float] = []
    for snap in history:
        for old in snap.get("rows", []):
            if normalize_text(old.get("name")) == name and normalize_text(old.get("institution")) == inst:
                amount = parse_amount(old.get("amount"))
                if amount is not None:
                    values.append(abs(amount))
                break
    return values[-limit:]


def detect_anomalies(results: list[dict], history: list[dict], threshold_percent: float = 25.0) -> list[dict]:
    alerts = []
    for row in results:
        current = abs(parse_amount(row.get("amount")) or 0)
        previous = _history_amounts(history, row, 6)
        if len(previous) < 2:
            continue
        baseline_values = previous[:-1] if abs(previous[-1] - current) < 0.01 else previous
        if not baseline_values:
            continue
        avg = sum(baseline_values) / len(baseline_values)
        if avg <= 0:
            continue
        change = (current - avg) / avg * 100
        if abs(change) >= threshold_percent:
            alerts.append({
                "name": row.get("display_name") or row.get("invoice_no", ""),
                "current": round(current, 2),
                "average": round(avg, 2),
                "change_percent": round(change, 1),
                "kind": "WZROST" if change > 0 else "SPADEK",
            })
    return sorted(alerts, key=lambda x: abs(x["change_percent"]), reverse=True)


def forecast_month(results: list[dict]) -> dict:
    expenses = [r for r in results if r.get("entry_type") != "income"]
    planned = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses)
    paid = sum(abs(parse_amount(r.get("bank_amount")) or parse_amount(r.get("amount")) or 0) for r in expenses if r.get("status") == "OPŁACONA")
    review = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses if r.get("status") == "DO SPRAWDZENIA")
    missing = sum(abs(parse_amount(r.get("amount")) or 0) for r in expenses if r.get("status") == "BRAK")
    remaining = review + missing
    return {"planned": round(planned, 2), "paid_actual": round(paid, 2), "remaining": round(remaining, 2), "projected": round(paid + remaining, 2)}


def inferred_due_day(history: list[dict], row: dict) -> int | None:
    name = normalize_text(row.get("display_name") or row.get("invoice_no"))
    inst = normalize_text(row.get("institution") or row.get("counterparty"))
    days = []
    for snap in history:
        for old in snap.get("rows", []):
            if normalize_text(old.get("name")) == name and normalize_text(old.get("institution")) == inst:
                d = parse_date(old.get("bank_date"))
                if d:
                    days.append(d.day)
                break
    return int(round(statistics.median(days[-6:]))) if days else None


def payment_deadline_status(history: list[dict], row: dict, today: date | None = None) -> str:
    if row.get("status") == "OPŁACONA":
        return "OPŁACONE"
    due = inferred_due_day(history, row)
    if due is None:
        return "BRAK HISTORII TERMINU"
    today = today or date.today()
    delta = due - today.day
    if delta < 0:
        return f"PO TERMINIE {abs(delta)} DNI"
    if delta == 0:
        return "TERMIN DZISIAJ"
    return f"DO ZAPŁATY ZA {delta} DNI"


def installment_plan(items: list[dict], as_of: date | None = None) -> list[dict]:
    as_of = as_of or date.today()
    rows = []
    for item in items:
        if not item.get("bank"):
            continue
        end = parse_date(item.get("end_date"))
        monthly = abs(parse_amount(item.get("amount")) or 0)
        if not end or monthly <= 0:
            continue
        months = max(0, (end.year - as_of.year) * 12 + end.month - as_of.month + 1)
        rows.append({
            "name": item.get("display_name", ""),
            "bank": item.get("bank", ""),
            "monthly": monthly,
            "end": end.isoformat(),
            "months_left": months,
            "estimated_left": round(monthly * months, 2),
        })
    return sorted(rows, key=lambda r: (r["end"], r["name"]))


def export_backup(destination: str | Path) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    names = ("history.json", "decisions.json", "aliases.json", "rules.json")
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            source = app_dir() / name
            if source.exists():
                zf.write(source, arcname=name)
    return destination


def import_backup(source: str | Path) -> int:
    allowed = {"history.json", "decisions.json", "aliases.json", "rules.json"}
    target_dir = app_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(source, "r") as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if name not in allowed:
                continue
            data = zf.read(info)
            json.loads(data.decode("utf-8"))
            (target_dir / name).write_bytes(data)
            restored += 1
    return restored
