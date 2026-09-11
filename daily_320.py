from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path

from budget_200 import payment_calendar
from household_300 import (
    add_savings_movement,
    load_debts,
    load_envelopes,
    load_savings_accounts,
    load_subscriptions,
    net_worth,
)
from installment_store import load_installments
from matcher import parse_amount, parse_date
from practical_310 import fund_envelope, safe_to_spend


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def _load(name: str, default):
    path = app_dir() / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save(name: str, value) -> None:
    path = app_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def current_month_key(items: list[dict], today: date | None = None) -> str:
    today = today or date.today()
    for row in items:
        sheet = str(row.get("source_sheet") or "").strip()
        if sheet:
            return sheet
    return f"{today.year:04d}-{today.month:02d}"


def today_overview(
    items: list[dict],
    results: list[dict],
    wallet_total: float = 0.0,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    calendar = payment_calendar(items, results, today=today)
    overdue = [row for row in calendar if row.get("status") == "PO TERMINIE"]
    week = [row for row in calendar if row.get("status") == "W TYM TYGODNIU"]
    waiting = [row for row in calendar if row.get("status") == "CZEKA"]
    review = [row for row in results if row.get("status") == "DO SPRAWDZENIA"]
    missing = [row for row in results if row.get("status") == "BRAK"]
    safe = safe_to_spend(items, results, wallet_total)
    return {
        "date": today.isoformat(),
        "overdue": overdue,
        "week": week,
        "waiting": waiting,
        "review": review,
        "missing": missing,
        "safe": safe,
        "action_count": len(overdue) + len(review),
    }


def month_close_check(items: list[dict], results: list[dict], today: date | None = None) -> dict:
    today = today or date.today()
    overview = today_overview(items, results, today=today)
    blockers = []
    if overview["review"]:
        blockers.append(f"{len(overview['review'])} pozycji do zatwierdzenia")
    if overview["overdue"]:
        blockers.append(f"{len(overview['overdue'])} płatności po terminie")
    if overview["missing"]:
        blockers.append(f"{len(overview['missing'])} pozycji bez potwierdzenia")
    return {
        "can_close": not blockers,
        "blockers": blockers,
        "month": current_month_key(items, today),
    }


def load_month_closures() -> list[dict]:
    rows = _load("month_closures.json", [])
    return rows if isinstance(rows, list) else []


def close_month(items: list[dict], results: list[dict], *, force: bool = False, today: date | None = None) -> dict:
    today = today or date.today()
    check = month_close_check(items, results, today)
    if not check["can_close"] and not force:
        raise ValueError("Nie można zamknąć miesiąca: " + "; ".join(check["blockers"]))
    month = check["month"]
    rows = load_month_closures()
    row = {
        "month": month,
        "closed_at": datetime.now().isoformat(timespec="seconds"),
        "forced": bool(force),
        "blockers_at_close": list(check["blockers"]),
        "results_total": len(results),
        "paid": sum(r.get("status") == "OPŁACONA" for r in results),
        "review": sum(r.get("status") == "DO SPRAWDZENIA" for r in results),
        "missing": sum(r.get("status") == "BRAK" for r in results),
    }
    rows = [old for old in rows if old.get("month") != month]
    rows.append(row)
    _save("month_closures.json", rows[-120:])
    return row


def load_net_worth_history() -> list[dict]:
    rows = _load("net_worth_history.json", [])
    return rows if isinstance(rows, list) else []


def snapshot_net_worth(wallet_total: float = 0.0, today: date | None = None) -> dict:
    today = today or date.today()
    worth = net_worth(wallet_total)
    row = {
        "date": today.isoformat(),
        "gross": round(float(worth.get("gross") or 0), 2),
        "debts": round(float(worth.get("debts") or 0), 2),
        "net": round(float(worth.get("net") or 0), 2),
    }
    rows = [old for old in load_net_worth_history() if old.get("date") != row["date"]]
    rows.append(row)
    rows.sort(key=lambda x: x.get("date", ""))
    _save("net_worth_history.json", rows[-730:])
    return row


def net_worth_trend(limit: int = 24) -> list[dict]:
    return load_net_worth_history()[-max(1, limit):]


def _month_add(year: int, month: int, offset: int) -> tuple[int, int]:
    idx = (year * 12 + month - 1) + offset
    return idx // 12, idx % 12 + 1


def plan_12_months(today: date | None = None) -> list[dict]:
    today = today or date.today()
    installments = [r for r in load_installments() if r.get("active", True)]
    subscriptions = [r for r in load_subscriptions() if r.get("active", True)]
    envelopes = [r for r in load_envelopes() if r.get("active", True)]
    savings = [r for r in load_savings_accounts() if r.get("active", True)]
    debts = [r for r in load_debts() if r.get("active", True)]
    rows = []
    for offset in range(12):
        year, month = _month_add(today.year, today.month, offset)
        fixed = 0.0
        installments_total = 0.0
        for row in installments:
            end = parse_date(row.get("end_date"))
            start = parse_date(row.get("start_date"))
            month_start = date(year, month, 1)
            if start and (start.year, start.month) > (year, month):
                continue
            if end and (end.year, end.month) < (year, month):
                continue
            installments_total += abs(parse_amount(row.get("monthly")) or 0.0)
        subscriptions_total = sum(abs(parse_amount(r.get("monthly")) or 0.0) for r in subscriptions)
        envelope_total = sum(abs(parse_amount(r.get("monthly")) or 0.0) for r in envelopes)
        savings_total = sum(abs(parse_amount(r.get("monthly_target")) or 0.0) for r in savings)
        debt_total = sum(abs(parse_amount(r.get("monthly")) or 0.0) for r in debts)
        fixed = installments_total + subscriptions_total + envelope_total + savings_total + debt_total
        rows.append({
            "year": year,
            "month": month,
            "label": f"{year:04d}-{month:02d}",
            "installments": round(installments_total, 2),
            "subscriptions": round(subscriptions_total, 2),
            "envelopes": round(envelope_total, 2),
            "savings": round(savings_total, 2),
            "debts": round(debt_total, 2),
            "fixed_total": round(fixed, 2),
        })
    return rows


def load_monthly_automation() -> dict:
    data = _load("monthly_automation.json", {})
    return data if isinstance(data, dict) else {}


def run_monthly_allocations(period: str | None = None, today: date | None = None) -> dict:
    today = today or date.today()
    period = period or f"{today.year:04d}-{today.month:02d}"
    state = load_monthly_automation()
    if state.get(period, {}).get("done"):
        return {**state[period], "already_done": True}

    envelope_total = 0.0
    for row in load_envelopes():
        if not row.get("active", True):
            continue
        amount = float(row.get("monthly") or 0)
        if amount > 0:
            fund_envelope(row["id"], amount)
            envelope_total += amount

    savings_total = 0.0
    for row in load_savings_accounts():
        if not row.get("active", True):
            continue
        amount = float(row.get("monthly_target") or 0)
        if amount > 0:
            add_savings_movement(row["id"], amount, f"Automatyczne odkładanie {period}", when=today.isoformat())
            savings_total += amount

    result = {
        "done": True,
        "period": period,
        "envelopes": round(envelope_total, 2),
        "savings": round(savings_total, 2),
        "total": round(envelope_total + savings_total, 2),
        "done_at": datetime.now().isoformat(timespec="seconds"),
        "already_done": False,
    }
    state[period] = result
    _save("monthly_automation.json", state)
    return result
