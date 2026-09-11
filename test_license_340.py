from __future__ import annotations

import base64
import json
from datetime import date

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import license_340


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _signed_key(private_key: Ed25519PrivateKey, payload: dict) -> str:
    raw = license_340.canonical_payload(payload)
    return f"{_b64e(raw)}.{_b64e(private_key.sign(raw))}"


def _test_keypair(monkeypatch):
    private = Ed25519PrivateKey.generate()
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(license_340, "PUBLIC_KEY_PEM", public_pem)
    return private


def test_signed_license_is_verified(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    private = _test_keypair(monkeypatch)
    payload = {
        "product": "PayCheck",
        "license_id": "LIC-TEST",
        "customer": "Jan Testowy",
        "type": "HOME",
        "issued": "2026-09-11",
        "expires": "",
        "machine_id": "",
        "features": "all",
        "issuer": "Edwin K.",
    }
    key = _signed_key(private, payload)
    installed = license_340.install_license_key(key)
    assert installed["customer"] == "Jan Testowy"
    status = license_340.license_status(date(2026, 9, 11))
    assert status["mode"] == "licensed"
    assert status["write_allowed"] is True


def test_modified_license_is_rejected(monkeypatch):
    private = _test_keypair(monkeypatch)
    payload = {
        "product": "PayCheck",
        "license_id": "LIC-TEST",
        "customer": "Jan Testowy",
        "type": "HOME",
        "issued": "2026-09-11",
        "expires": "",
        "machine_id": "",
        "features": "all",
        "issuer": "Edwin K.",
    }
    key = _signed_key(private, payload)
    left, signature = key.split(".", 1)
    raw = json.loads(base64.urlsafe_b64decode(left + "=" * (-len(left) % 4)).decode("utf-8"))
    raw["type"] = "PRO"
    changed = _b64e(json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    with pytest.raises(ValueError, match="Podpis"):
        license_340.decode_license_key(changed + "." + signature)


def test_trial_expires_after_seven_days(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    start = license_340.license_status(date(2026, 9, 1))
    assert start["mode"] == "trial"
    assert start["days_left"] == 7

    last_day = license_340.license_status(date(2026, 9, 7))
    assert last_day["mode"] == "trial"
    assert last_day["days_left"] == 1

    expired = license_340.license_status(date(2026, 9, 8))
    assert expired["mode"] == "readonly"
    assert expired["write_allowed"] is False
