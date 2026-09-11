from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / "PayCheck"


def _load(name: str, default):
    path = app_dir() / name
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return data


def _save(name: str, value) -> None:
    path = app_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def _money(value) -> float:
    if isinstance(value, str):
        value = value.replace(" ", "").replace(",", ".")
    return round(float(value or 0), 2)


def _upsert(name: str, row: dict, prefix: str, required: str = "name") -> dict:
    rows = _load(name, [])
    if not isinstance(rows, list):
        rows = []
    item = dict(row)
    item["id"] = item.get("id") or _id(prefix)
    item[required] = str(item.get(required, "")).strip()
    if not item[required]:
        raise ValueError("Nazwa jest wymagana.")
    item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    for index, old in enumerate(rows):
        if old.get("id") == item["id"]:
            rows[index] = item
            break
    else:
        item.setdefault("created_at", item["updated_at"])
        rows.append(item)
    _save(name, rows)
    return item


def _delete(name: str, row_id: str) -> bool:
    rows = _load(name, [])
    if not isinstance(rows, list):
        return False
    new_rows = [row for row in rows if row.get("id") != row_id]
    if len(new_rows) == len(rows):
        return False
    _save(name, new_rows)
    return True


# --- Gospodarstwo domowe -----------------------------------------------------

def load_members() -> list[dict]:
    rows = _load("members.json", [])
    return rows if isinstance(rows, list) else []


def save_member(data: dict) -> dict:
    row = dict(data)
    row["name"] = str(row.get("name", "")).strip()
    row["color"] = str(row.get("color") or "#1976D2")
    row["monthly_income"] = _money(row.get("monthly_income"))
    row["active"] = bool(row.get("active", True))
    return _upsert("members.json", row, "OSOBA")


def delete_member(member_id: str) -> bool:
    return _delete("members.json", member_id)


def member_name(member_id: str) -> str:
    if not member_id:
        return "Wspólne"
    for row in load_members():
        if row.get("id") == member_id:
            return row.get("name") or "Wspólne"
    return "Wspólne"


# --- Oszczędności ------------------------------------------------------------

def load_savings_accounts() -> list[dict]:
    rows = _load("savings_accounts.json", [])
    return rows if isinstance(rows, list) else []


def save_savings_account(data: dict) -> dict:
    row = dict(data)
    row["balance"] = _money(row.get("balance"))
    row["monthly_target"] = _money(row.get("monthly_target"))
    row["owner_id"] = str(row.get("owner_id") or "")
    row["kind"] = str(row.get("kind") or "Oszczędności")
    row["active"] = bool(row.get("active", True))
    return _upsert("savings_accounts.json", row, "OSZ")


def delete_savings_account(row_id: str) -> bool:
    return _delete("savings_accounts.json", row_id)


def load_savings_movements() -> list[dict]:
    rows = _load("savings_movements.json", [])
    return rows if isinstance(rows, list) else []


def add_savings_movement(account_id: str, amount: float, note: str = "", when: str | None = None) -> dict:
    amount = _money(amount)
    accounts = load_savings_accounts()
    account = next((row for row in accounts if row.get("id") == account_id), None)
    if not account:
        raise ValueError("Nie znaleziono konta oszczędnościowego.")
    account["balance"] = _money(account.get("balance")) + amount
    save_savings_account(account)
    rows = load_savings_movements()
    movement = {
        "id": _id("RUCH"),
        "account_id": account_id,
        "date": when or date.today().isoformat(),
        "amount": amount,
        "note": str(note or "").strip(),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    rows.append(movement)
    _save("savings_movements.json", rows[-5000:])
    return movement


def savings_summary() -> dict:
    accounts = [row for row in load_savings_accounts() if row.get("active", True)]
    total = sum(_money(row.get("balance")) for row in accounts)
    monthly_target = sum(_money(row.get("monthly_target")) for row in accounts)
    by_owner: dict[str, float] = {}
    for row in accounts:
        key = row.get("owner_id") or "shared"
        by_owner[key] = round(by_owner.get(key, 0.0) + _money(row.get("balance")), 2)
    return {
        "total": round(total, 2),
        "monthly_target": round(monthly_target, 2),
        "accounts": accounts,
        "by_owner": by_owner,
    }


# --- Koperty / fundusze celowe ----------------------------------------------

def load_envelopes() -> list[dict]:
    rows = _load("envelopes.json", [])
    return rows if isinstance(rows, list) else []


def save_envelope(data: dict) -> dict:
    row = dict(data)
    row["balance"] = _money(row.get("balance"))
    row["monthly"] = _money(row.get("monthly"))
    row["target"] = _money(row.get("target"))
    row["owner_id"] = str(row.get("owner_id") or "")
    row["active"] = bool(row.get("active", True))
    return _upsert("envelopes.json", row, "KOP")


def delete_envelope(row_id: str) -> bool:
    return _delete("envelopes.json", row_id)


def envelope_summary() -> dict:
    rows = [row for row in load_envelopes() if row.get("active", True)]
    total = sum(_money(row.get("balance")) for row in rows)
    monthly = sum(_money(row.get("monthly")) for row in rows)
    target = sum(_money(row.get("target")) for row in rows)
    return {"rows": rows, "total": round(total, 2), "monthly": round(monthly, 2), "target": round(target, 2)}


# --- Subskrypcje -------------------------------------------------------------

def load_subscriptions() -> list[dict]:
    rows = _load("subscriptions.json", [])
    return rows if isinstance(rows, list) else []


def save_subscription(data: dict) -> dict:
    row = dict(data)
    row["monthly"] = _money(row.get("monthly"))
    row["payment_day"] = int(row.get("payment_day") or 0)
    row["owner_id"] = str(row.get("owner_id") or "")
    row["active"] = bool(row.get("active", True))
    return _upsert("subscriptions.json", row, "SUB")


def delete_subscription(row_id: str) -> bool:
    return _delete("subscriptions.json", row_id)


def subscriptions_summary() -> dict:
    rows = [row for row in load_subscriptions() if row.get("active", True)]
    monthly = sum(_money(row.get("monthly")) for row in rows)
    return {"rows": rows, "monthly": round(monthly, 2), "annual": round(monthly * 12, 2)}


# --- Majątek / zobowiązania własne ------------------------------------------

def load_assets() -> list[dict]:
    rows = _load("assets.json", [])
    return rows if isinstance(rows, list) else []


def save_asset(data: dict) -> dict:
    row = dict(data)
    row["value"] = _money(row.get("value"))
    row["owner_id"] = str(row.get("owner_id") or "")
    row["kind"] = str(row.get("kind") or "Aktywo")
    row["active"] = bool(row.get("active", True))
    return _upsert("assets.json", row, "MAJ")


def delete_asset(row_id: str) -> bool:
    return _delete("assets.json", row_id)


def load_debts() -> list[dict]:
    rows = _load("debts.json", [])
    return rows if isinstance(rows, list) else []


def save_debt(data: dict) -> dict:
    row = dict(data)
    row["balance"] = _money(row.get("balance"))
    row["monthly"] = _money(row.get("monthly"))
    row["owner_id"] = str(row.get("owner_id") or "")
    row["active"] = bool(row.get("active", True))
    return _upsert("debts.json", row, "DLUG")


def delete_debt(row_id: str) -> bool:
    return _delete("debts.json", row_id)


def net_worth(wallet_total: float = 0.0) -> dict:
    assets = [row for row in load_assets() if row.get("active", True)]
    debts = [row for row in load_debts() if row.get("active", True)]
    savings = savings_summary()["total"]
    asset_total = sum(_money(row.get("value")) for row in assets)
    debt_total = sum(_money(row.get("balance")) for row in debts)
    gross = round(_money(wallet_total) + savings + asset_total, 2)
    return {
        "wallets": round(_money(wallet_total), 2),
        "savings": round(savings, 2),
        "assets": round(asset_total, 2),
        "debts": round(debt_total, 2),
        "gross": gross,
        "net": round(gross - debt_total, 2),
    }


# --- Dashboard gospodarstwa --------------------------------------------------

def household_overview(wallet_total: float = 0.0) -> dict:
    members = [row for row in load_members() if row.get("active", True)]
    savings = savings_summary()
    envelopes = envelope_summary()
    subscriptions = subscriptions_summary()
    worth = net_worth(wallet_total)
    income = sum(_money(row.get("monthly_income")) for row in members)
    debt_monthly = sum(_money(row.get("monthly")) for row in load_debts() if row.get("active", True))
    return {
        "members": members,
        "members_count": len(members),
        "household_income": round(income, 2),
        "savings": savings,
        "envelopes": envelopes,
        "subscriptions": subscriptions,
        "net_worth": worth,
        "debt_monthly": round(debt_monthly, 2),
        "offline": True,
        "api_ready": True,
    }
