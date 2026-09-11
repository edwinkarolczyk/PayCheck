from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from license_public_340 import PUBLIC_KEY_PEM

TRIAL_DAYS = 7
OWNER_LABEL = "Edwin K."
PRODUCT = "PayCheck"


def app_dir() -> Path:
    return Path(os.getenv("APPDATA") or Path.home()) / PRODUCT


def license_path() -> Path:
    return app_dir() / "license.json"


def trial_state_path() -> Path:
    return app_dir() / "license_state.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def machine_id() -> str:
    raw = "|".join(
        [
            platform.system(),
            platform.machine(),
            platform.node(),
            os.getenv("COMPUTERNAME", ""),
            str(uuid.getnode()),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest().upper()
    return "PC-" + "-".join((digest[:6], digest[6:12], digest[12:18]))


def _public_key() -> Ed25519PublicKey:
    key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Nieprawidłowy klucz publiczny licencji.")
    return key


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical_payload(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def decode_license_key(key_text: str) -> dict:
    value = "".join(str(key_text or "").split())
    if "." not in value:
        raise ValueError("Nieprawidłowy format klucza licencyjnego.")
    payload_part, signature_part = value.split(".", 1)
    payload_raw = _b64d(payload_part)
    signature = _b64d(signature_part)
    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Nie udało się odczytać danych licencji.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Nieprawidłowe dane licencji.")
    try:
        _public_key().verify(signature, canonical_payload(payload))
    except InvalidSignature as exc:
        raise ValueError("Podpis licencji jest nieprawidłowy.") from exc
    return payload


def validate_payload(payload: dict, *, today: date | None = None) -> dict:
    today = today or date.today()
    if payload.get("product") != PRODUCT:
        return {"valid": False, "reason": "Licencja jest przeznaczona dla innego produktu."}

    bound_machine = str(payload.get("machine_id") or "").strip()
    if bound_machine and bound_machine != machine_id():
        return {"valid": False, "reason": "Licencja jest przypisana do innego komputera."}

    expires = str(payload.get("expires") or "").strip()
    if expires:
        try:
            expiry = date.fromisoformat(expires)
        except ValueError:
            return {"valid": False, "reason": "Licencja ma nieprawidłową datę ważności."}
        if today > expiry:
            return {"valid": False, "reason": f"Licencja wygasła {expiry.isoformat()}."}

    return {"valid": True, "reason": "OK"}


def install_license_key(key_text: str) -> dict:
    payload = decode_license_key(key_text)
    check = validate_payload(payload)
    if not check["valid"]:
        raise ValueError(check["reason"])
    _save_json(license_path(), {"key": "".join(key_text.split()), "installed_at": datetime.now().isoformat(timespec="seconds")})
    return payload


def load_installed_license() -> dict | None:
    raw = _load_json(license_path(), {})
    key = str(raw.get("key") or "").strip() if isinstance(raw, dict) else ""
    if not key:
        return None
    try:
        payload = decode_license_key(key)
    except ValueError:
        return None
    check = validate_payload(payload)
    if not check["valid"]:
        return None
    return payload


def _trial_state(today: date | None = None) -> dict:
    today = today or date.today()
    now = datetime.now()
    state = _load_json(trial_state_path(), {})
    if not isinstance(state, dict):
        state = {}

    first_run = state.get("first_run")
    if not first_run:
        first_run = today.isoformat()
        state["first_run"] = first_run

    state["last_seen"] = now.isoformat(timespec="seconds")
    _save_json(trial_state_path(), state)
    return state


def license_status(today: date | None = None) -> dict:
    today = today or date.today()
    payload = load_installed_license()
    if payload:
        return {
            "mode": "licensed",
            "write_allowed": True,
            "trial": False,
            "days_left": None,
            "license": payload,
            "label": f"{payload.get('type', 'HOME')} — {payload.get('customer', '')}".strip(" —"),
        }

    state = _trial_state(today)
    try:
        first = date.fromisoformat(str(state.get("first_run")))
    except ValueError:
        first = today
    end = first + timedelta(days=TRIAL_DAYS - 1)
    days_left = (end - today).days + 1
    active = days_left > 0
    return {
        "mode": "trial" if active else "readonly",
        "write_allowed": active,
        "trial": True,
        "days_left": max(0, days_left),
        "trial_end": end.isoformat(),
        "license": None,
        "label": f"TRIAL — {max(0, days_left)} dni" if active else "TRIAL WYGASŁ — tylko odczyt",
    }
