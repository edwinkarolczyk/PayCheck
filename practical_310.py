from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

from household_300 import load_envelopes, load_members, load_savings_accounts, save_envelope
from matcher import normalize_text, parse_amount


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


FEATURES = {
    "calendar": "Kalendarz płatności",
    "goals": "Cele",
    "limits": "Limity kategorii",
    "accounts": "Konta i banki",
    "annual": "Raport roczny",
    "intelligence": "Analiza / prognoza",
    "members": "Użytkownicy",
    "savings": "Oszczędności",
    "envelopes": "Koperty",
    "subscriptions": "Subskrypcje",
    "net_worth": "Majątek netto",
    "settlements": "Rozliczenia domowników",
    "safe_to_spend": "Bezpiecznie do wydania",
}

SIMPLE_FEATURES = {
    "calendar": True,
    "goals": True,
    "limits": False,
    "accounts": True,
    "annual": False,
    "intelligence": False,
    "members": True,
    "savings": True,
    "envelopes": False,
    "subscriptions": False,
    "net_worth": False,
    "settlements": True,
    "safe_to_spend": True,
}


def default_feature_settings() -> dict[str, bool]:
    return {key: True for key in FEATURES}


def load_feature_settings() -> dict[str, bool]:
    raw = _load("feature_visibility.json", {})
    data = default_feature_settings()
    if isinstance(raw, dict):
        for key in data:
            if key in raw:
                data[key] = bool(raw[key])
    return data


def save_feature_settings(settings: dict[str, bool]) -> None:
    current = default_feature_settings()
    for key in current:
        if key in settings:
            current[key] = bool(settings[key])
    _save("feature_visibility.json", current)


def apply_feature_preset(name: str) -> dict[str, bool]:
    if name == "simple":
        settings = dict(SIMPLE_FEATURES)
    else:
        settings = default_feature_settings()
    save_feature_settings(settings)
    return settings


# --- Automatyczne przypisywanie do domowników -------------------------------

def load_owner_rules() -> list[dict]:
    rows = _load("owner_rules.json", [])
    return rows if isinstance(rows, list) else []


def save_owner_rule(phrase: str, owner_id: str) -> dict:
    phrase = str(phrase or "").strip()
    if not phrase:
        raise ValueError("Fraza reguły jest wymagana.")
    members = {row.get("id") for row in load_members()}
    if owner_id and owner_id not in members:
        raise ValueError("Nie znaleziono użytkownika.")
    rows = load_owner_rules()
    normalized = normalize_text(phrase)
    for row in rows:
        if normalize_text(row.get("phrase", "")) == normalized:
            row["phrase"] = phrase
            row["owner_id"] = owner_id
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            _save("owner_rules.json", rows)
            return row
    row = {
        "id": f"REG-{uuid.uuid4().hex[:10].upper()}",
        "phrase": phrase,
        "owner_id": owner_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(row)
    _save("owner_rules.json", rows)
    return row


def delete_owner_rule(rule_id: str) -> bool:
    rows = load_owner_rules()
    new_rows = [row for row in rows if row.get("id") != rule_id]
    if len(new_rows) == len(rows):
        return False
    _save("owner_rules.json", new_rows)
    return True


def owner_for_transaction(tx: dict) -> str:
    haystack = normalize_text(" ".join(str(tx.get(k, "") or "") for k in ("counterparty", "description", "title", "source_file")))
    best = ""
    best_len = -1
    for rule in load_owner_rules():
        phrase = normalize_text(rule.get("phrase", ""))
        if phrase and phrase in haystack and len(phrase) > best_len:
            best = str(rule.get("owner_id") or "")
            best_len = len(phrase)
    return best


def assign_transaction_owners(transactions: list[dict]) -> list[dict]:
    result = []
    for tx in transactions:
        row = dict(tx)
        row["owner_id"] = owner_for_transaction(row)
        result.append(row)
    return result


# --- Rozliczenia domowników --------------------------------------------------

def load_settlements() -> list[dict]:
    rows = _load("settlements.json", [])
    return rows if isinstance(rows, list) else []


def save_settlement(data: dict) -> dict:
    row = dict(data)
    row["id"] = row.get("id") or f"ROZ-{uuid.uuid4().hex[:10].upper()}"
    row["date"] = str(row.get("date") or date.today().isoformat())
    row["description"] = str(row.get("description") or "").strip()
    row["payer_id"] = str(row.get("payer_id") or "")
    row["for_id"] = str(row.get("for_id") or "")
    row["amount"] = round(abs(float(row.get("amount") or 0)), 2)
    row["settled"] = bool(row.get("settled", False))
    if not row["description"] or row["amount"] <= 0:
        raise ValueError("Opis i kwota są wymagane.")
    rows = load_settlements()
    for idx, old in enumerate(rows):
        if old.get("id") == row["id"]:
            rows[idx] = row
            break
    else:
        rows.append(row)
    _save("settlements.json", rows)
    return row


def set_settlement_done(row_id: str, done: bool = True) -> bool:
    rows = load_settlements()
    for row in rows:
        if row.get("id") == row_id:
            row["settled"] = bool(done)
            _save("settlements.json", rows)
            return True
    return False


def settlement_balances() -> dict[str, float]:
    balances: dict[str, float] = {}
    for row in load_settlements():
        if row.get("settled"):
            continue
        payer = str(row.get("payer_id") or "")
        beneficiary = str(row.get("for_id") or "")
        amount = float(row.get("amount") or 0)
        if payer:
            balances[payer] = round(balances.get(payer, 0.0) + amount, 2)
        if beneficiary:
            balances[beneficiary] = round(balances.get(beneficiary, 0.0) - amount, 2)
    return balances


# --- Szybkie zasilanie kopert -----------------------------------------------

def fund_envelope(envelope_id: str, amount: float) -> dict:
    amount = round(float(amount or 0), 2)
    if amount == 0:
        raise ValueError("Kwota nie może wynosić 0.")
    rows = load_envelopes()
    row = next((item for item in rows if item.get("id") == envelope_id), None)
    if not row:
        raise ValueError("Nie znaleziono koperty.")
    row = dict(row)
    row["balance"] = round(float(row.get("balance") or 0) + amount, 2)
    if row["balance"] < 0:
        raise ValueError("Koperta nie może mieć ujemnego salda.")
    return save_envelope(row)


def fund_all_monthly_envelopes() -> float:
    total = 0.0
    for row in load_envelopes():
        if not row.get("active", True):
            continue
        amount = float(row.get("monthly") or 0)
        if amount > 0:
            fund_envelope(row["id"], amount)
            total += amount
    return round(total, 2)


# --- Ile można bezpiecznie wydać --------------------------------------------

def safe_to_spend(items: list[dict], results: list[dict], wallet_total: float = 0.0) -> dict:
    income = sum(abs(parse_amount(row.get("amount")) or 0.0) for row in items if row.get("entry_type") == "income")
    planned_expenses = sum(abs(parse_amount(row.get("amount")) or 0.0) for row in items if row.get("entry_type") != "income")
    paid = sum(
        abs(parse_amount(row.get("bank_amount")) or parse_amount(row.get("amount")) or 0.0)
        for row in results
        if row.get("entry_type") != "income" and row.get("status") == "OPŁACONA"
    )
    unpaid = max(0.0, planned_expenses - paid)
    savings_target = sum(float(row.get("monthly_target") or 0) for row in load_savings_accounts() if row.get("active", True))
    envelopes_target = sum(float(row.get("monthly") or 0) for row in load_envelopes() if row.get("active", True))
    base = float(wallet_total) if wallet_total else income
    safe = max(0.0, base - unpaid - savings_target - envelopes_target)
    return {
        "base": round(base, 2),
        "income": round(income, 2),
        "unpaid": round(unpaid, 2),
        "savings_target": round(savings_target, 2),
        "envelopes_target": round(envelopes_target, 2),
        "safe": round(safe, 2),
    }
