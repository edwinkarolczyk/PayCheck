from __future__ import annotations

import json
import os
import uuid
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from installment_store import load_installments, months_left
from matcher import normalize_text, parse_amount, parse_date


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def _load_json(name: str, default):
    path = app_dir() / name
    if not path.exists():
        return default
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return value


def _save_json(name: str, value) -> None:
    path = app_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


# --- 1.1 Kalendarz płatności -------------------------------------------------

def payment_calendar(items: list[dict], results: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    result_map = {}
    for row in results:
        key = (normalize_text(row.get("institution", "")), normalize_text(row.get("display_name") or row.get("invoice_no", "")))
        result_map[key] = row
    rows = []
    for item in items:
        if item.get("entry_type") == "income":
            continue
        key = (normalize_text(item.get("institution", "")), normalize_text(item.get("display_name") or item.get("invoice_no", "")))
        matched = result_map.get(key, {})
        payment_day = int(item.get("payment_day") or 0)
        due = None
        explicit = parse_date(item.get("date"))
        if explicit:
            due = explicit
        elif payment_day:
            try:
                due = date(today.year, today.month, min(payment_day, 28))
            except ValueError:
                due = None
        status = matched.get("status", "BRAK")
        if status == "OPŁACONA":
            label = "ZAPŁACONE"
        elif due and due < today:
            label = "PO TERMINIE"
        elif due and (due - today).days <= 7:
            label = "W TYM TYGODNIU"
        else:
            label = "CZEKA"
        rows.append({
            "name": item.get("display_name") or item.get("invoice_no", ""),
            "institution": item.get("institution", ""),
            "amount": abs(parse_amount(item.get("amount")) or 0.0),
            "due": due.isoformat() if due else "",
            "status": label,
            "category": item.get("category", "Pozostałe"),
        })
    return sorted(rows, key=lambda r: (r["status"] == "ZAPŁACONE", r["due"] or "9999-12-31", r["name"]))


# --- 1.2 Cele i oszczędności -------------------------------------------------

def load_goals() -> list[dict]:
    data = _load_json("goals.json", [])
    return data if isinstance(data, list) else []


def save_goal(data: dict) -> dict:
    rows = load_goals()
    row = dict(data)
    row["id"] = row.get("id") or f"CEL-{uuid.uuid4().hex[:8].upper()}"
    row["name"] = str(row.get("name", "")).strip()
    row["target"] = round(float(row.get("target") or 0), 2)
    row["saved"] = round(float(row.get("saved") or 0), 2)
    row["deadline"] = str(row.get("deadline") or "")
    row["active"] = bool(row.get("active", True))
    if not row["name"] or row["target"] <= 0:
        raise ValueError("Nazwa celu i kwota docelowa są wymagane.")
    for idx, old in enumerate(rows):
        if old.get("id") == row["id"]:
            rows[idx] = row
            break
    else:
        rows.append(row)
    _save_json("goals.json", rows)
    return row


def delete_goal(goal_id: str) -> bool:
    rows = load_goals()
    new_rows = [row for row in rows if row.get("id") != goal_id]
    if len(new_rows) == len(rows):
        return False
    _save_json("goals.json", new_rows)
    return True


def goal_overview(today: date | None = None) -> list[dict]:
    today = today or date.today()
    result = []
    for row in load_goals():
        target = float(row.get("target") or 0)
        saved = float(row.get("saved") or 0)
        missing = max(0.0, target - saved)
        deadline = parse_date(row.get("deadline"))
        months = None
        monthly_needed = None
        if deadline:
            months = max(1, (deadline.year - today.year) * 12 + deadline.month - today.month + 1)
            monthly_needed = round(missing / months, 2)
        result.append({**row, "missing": round(missing, 2), "progress": round(saved / target * 100, 1) if target else 0.0, "months_left": months, "monthly_needed": monthly_needed})
    return result


# --- 1.3 Limity kategorii ----------------------------------------------------

def load_limits() -> dict[str, float]:
    data = _load_json("category_limits.json", {})
    if not isinstance(data, dict):
        return {}
    return {str(k): float(v) for k, v in data.items() if float(v or 0) > 0}


def set_limit(category: str, amount: float) -> None:
    limits = load_limits()
    category = str(category).strip()
    amount = float(amount)
    if not category:
        raise ValueError("Podaj kategorię.")
    if amount <= 0:
        limits.pop(category, None)
    else:
        limits[category] = round(amount, 2)
    _save_json("category_limits.json", limits)


def category_limit_status(items: list[dict], results: list[dict]) -> list[dict]:
    limits = load_limits()
    spent = defaultdict(float)
    for row in results:
        if row.get("entry_type") == "income":
            continue
        if row.get("status") == "OPŁACONA":
            spent[str(row.get("category") or "Pozostałe")] += abs(parse_amount(row.get("bank_amount")) or parse_amount(row.get("amount")) or 0.0)
    planned = defaultdict(float)
    for item in items:
        if item.get("entry_type") != "income":
            planned[str(item.get("category") or "Pozostałe")] += abs(parse_amount(item.get("amount")) or 0.0)
    rows = []
    for category in sorted(set(limits) | set(planned) | set(spent)):
        limit = limits.get(category, 0.0)
        used = round(spent.get(category, 0.0), 2)
        percent = round(used / limit * 100, 1) if limit else 0.0
        rows.append({"category": category, "limit": limit, "spent": used, "planned": round(planned.get(category, 0.0), 2), "percent": percent, "warning": limit > 0 and percent >= 80, "over": limit > 0 and percent >= 100})
    return rows


# --- 1.4 Inteligentna analiza -----------------------------------------------

def detect_duplicate_transactions(transactions: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for tx in transactions:
        key = (
            str(parse_date(tx.get("date")) or tx.get("date", "")),
            round(abs(parse_amount(tx.get("amount")) or 0.0), 2),
            normalize_text(tx.get("counterparty", "")),
        )
        groups[key].append(tx)
    duplicates = []
    for key, rows in groups.items():
        if len(rows) > 1 and key[1] > 0:
            duplicates.append({"date": key[0], "amount": key[1], "counterparty": rows[0].get("counterparty", ""), "count": len(rows)})
    return duplicates


def spending_anomalies(results: list[dict], history: list[dict]) -> list[dict]:
    historic = defaultdict(list)
    for snap in history:
        seen = set()
        for row in snap.get("rows", []):
            key = (normalize_text(row.get("institution", "")), normalize_text(row.get("name", "")))
            if key in seen:
                continue
            seen.add(key)
            value = abs(parse_amount(row.get("amount")) or 0.0)
            if value:
                historic[key].append(value)
    alerts = []
    for row in results:
        if row.get("entry_type") == "income":
            continue
        key = (normalize_text(row.get("institution", "")), normalize_text(row.get("display_name") or row.get("invoice_no", "")))
        values = historic.get(key, [])[-6:]
        current = abs(parse_amount(row.get("amount")) or 0.0)
        if len(values) >= 2:
            avg = sum(values) / len(values)
            pct = ((current - avg) / avg * 100) if avg else 0.0
            if abs(pct) >= 25:
                alerts.append({"name": row.get("display_name") or row.get("invoice_no", ""), "current": current, "average": round(avg, 2), "change_percent": round(pct, 1), "kind": "WZROST" if pct > 0 else "SPADEK"})
    return alerts


# --- 1.5 Prognoza ------------------------------------------------------------

def next_month_forecast(items: list[dict], history: list[dict]) -> dict:
    current_income = sum(abs(parse_amount(i.get("amount")) or 0.0) for i in items if i.get("entry_type") == "income")
    current_expenses = sum(abs(parse_amount(i.get("amount")) or 0.0) for i in items if i.get("entry_type") != "income")
    category_history = defaultdict(list)
    for snap in history[-12:]:
        month_cat = defaultdict(float)
        for row in snap.get("rows", []):
            category = str(row.get("category") or "Pozostałe")
            month_cat[category] += abs(parse_amount(row.get("amount")) or 0.0)
        for cat, value in month_cat.items():
            category_history[cat].append(value)
    forecast_categories = {}
    for cat, values in category_history.items():
        if values:
            forecast_categories[cat] = round(sum(values[-3:]) / min(3, len(values)), 2)
    projected = round(sum(forecast_categories.values()) or current_expenses, 2)
    return {"income": round(current_income, 2), "current_expenses": round(current_expenses, 2), "projected_expenses": projected, "projected_balance": round(current_income - projected, 2), "categories": dict(sorted(forecast_categories.items(), key=lambda kv: kv[1], reverse=True))}


# --- 1.6 Portfele / banki ----------------------------------------------------

def load_wallets() -> list[dict]:
    data = _load_json("wallets.json", [])
    return data if isinstance(data, list) else []


def save_wallet(data: dict) -> dict:
    rows = load_wallets()
    row = dict(data)
    row["id"] = row.get("id") or f"KONTO-{uuid.uuid4().hex[:8].upper()}"
    row["name"] = str(row.get("name", "")).strip()
    row["bank"] = str(row.get("bank", "")).strip()
    row["balance"] = round(float(row.get("balance") or 0), 2)
    row["active"] = bool(row.get("active", True))
    if not row["name"]:
        raise ValueError("Nazwa konta jest wymagana.")
    for idx, old in enumerate(rows):
        if old.get("id") == row["id"]:
            rows[idx] = row
            break
    else:
        rows.append(row)
    _save_json("wallets.json", rows)
    return row


def delete_wallet(wallet_id: str) -> bool:
    rows = load_wallets()
    new_rows = [row for row in rows if row.get("id") != wallet_id]
    if len(rows) == len(new_rows):
        return False
    _save_json("wallets.json", new_rows)
    return True


def wallet_summary(transactions: list[dict]) -> list[dict]:
    result = []
    for wallet in load_wallets():
        bank = normalize_text(wallet.get("bank", ""))
        incoming = outgoing = 0.0
        for tx in transactions:
            source = normalize_text(tx.get("source_file", ""))
            party = normalize_text(tx.get("counterparty", ""))
            if bank and bank not in source and bank not in party:
                continue
            amount = parse_amount(tx.get("amount")) or 0.0
            if amount >= 0:
                incoming += amount
            else:
                outgoing += abs(amount)
        result.append({**wallet, "income": round(incoming, 2), "expenses": round(outgoing, 2), "month_change": round(incoming - outgoing, 2)})
    return result


# --- 1.7 Centrum zobowiązań --------------------------------------------------

def obligations_overview(today: date | None = None) -> list[dict]:
    today = today or date.today()
    rows = []
    for item in load_installments():
        left = months_left(item, today)
        rows.append({
            "name": item.get("name", ""),
            "bank": item.get("bank", ""),
            "monthly": float(item.get("monthly") or 0),
            "payment_day": item.get("payment_day", ""),
            "end_date": item.get("end_date", ""),
            "months_left": left,
            "annual_cost": round(float(item.get("monthly") or 0) * 12, 2),
            "interest_type": item.get("interest_type", ""),
            "active": bool(item.get("active", True)),
        })
    return sorted(rows, key=lambda r: (not r["active"], r["months_left"] if r["months_left"] is not None else 9999, r["name"]))


# --- 2.0 Dashboard ------------------------------------------------------------

def dashboard_200(items: list[dict], results: list[dict], transactions: list[dict], history: list[dict]) -> dict:
    income = sum(abs(parse_amount(i.get("amount")) or 0.0) for i in items if i.get("entry_type") == "income")
    expenses = sum(abs(parse_amount(i.get("amount")) or 0.0) for i in items if i.get("entry_type") != "income")
    paid = sum(abs(parse_amount(r.get("bank_amount")) or parse_amount(r.get("amount")) or 0.0) for r in results if r.get("entry_type") != "income" and r.get("status") == "OPŁACONA")
    remaining = max(0.0, expenses - paid)
    review_count = sum(r.get("status") == "DO SPRAWDZENIA" for r in results)
    overdue_count = sum(r["status"] == "PO TERMINIE" for r in payment_calendar(items, results))
    goals = goal_overview()
    goals_saved = sum(float(g.get("saved") or 0) for g in goals if g.get("active", True))
    wallets = wallet_summary(transactions)
    wallet_total = sum(float(w.get("balance") or 0) for w in wallets if w.get("active", True))
    duplicates = detect_duplicate_transactions(transactions)
    anomalies = spending_anomalies(results, history)
    forecast = next_month_forecast(items, history)
    return {
        "income": round(income, 2),
        "expenses": round(expenses, 2),
        "paid": round(paid, 2),
        "remaining": round(remaining, 2),
        "balance_plan": round(income - expenses, 2),
        "review_count": review_count,
        "overdue_count": overdue_count,
        "goals_saved": round(goals_saved, 2),
        "wallet_total": round(wallet_total, 2),
        "duplicate_count": len(duplicates),
        "anomaly_count": len(anomalies),
        "forecast": forecast,
    }
