from __future__ import annotations

import practical_310
import household_300


def _use_tmp_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))


def test_feature_visibility_presets(tmp_path, monkeypatch):
    _use_tmp_appdata(tmp_path, monkeypatch)
    full = practical_310.apply_feature_preset("full")
    assert all(full.values())
    simple = practical_310.apply_feature_preset("simple")
    assert simple["savings"] is True
    assert simple["net_worth"] is False
    assert practical_310.load_feature_settings() == simple


def test_owner_rule_uses_longest_phrase(tmp_path, monkeypatch):
    _use_tmp_appdata(tmp_path, monkeypatch)
    a = household_300.save_member({"name": "A"})
    b = household_300.save_member({"name": "B"})
    practical_310.save_owner_rule("orlen", a["id"])
    practical_310.save_owner_rule("orlen krakow", b["id"])
    tx = {"counterparty": "ORLEN KRAKOW 123", "description": "paliwo"}
    assert practical_310.owner_for_transaction(tx) == b["id"]


def test_settlement_balances(tmp_path, monkeypatch):
    _use_tmp_appdata(tmp_path, monkeypatch)
    a = household_300.save_member({"name": "A"})
    b = household_300.save_member({"name": "B"})
    row = practical_310.save_settlement({"description": "Zakupy", "payer_id": a["id"], "for_id": b["id"], "amount": 80})
    balances = practical_310.settlement_balances()
    assert balances[a["id"]] == 80
    assert balances[b["id"]] == -80
    practical_310.set_settlement_done(row["id"], True)
    assert practical_310.settlement_balances() == {}


def test_fund_envelope_and_all_monthly(tmp_path, monkeypatch):
    _use_tmp_appdata(tmp_path, monkeypatch)
    env = household_300.save_envelope({"name": "OC", "balance": 100, "monthly": 50, "target": 1000})
    practical_310.fund_envelope(env["id"], 25)
    assert household_300.load_envelopes()[0]["balance"] == 125
    assert practical_310.fund_all_monthly_envelopes() == 50
    assert household_300.load_envelopes()[0]["balance"] == 175


def test_safe_to_spend_reserves_unpaid_and_savings(tmp_path, monkeypatch):
    _use_tmp_appdata(tmp_path, monkeypatch)
    household_300.save_savings_account({"name": "Poduszka", "monthly_target": 300, "balance": 0})
    household_300.save_envelope({"name": "OC", "monthly": 100, "balance": 0})
    items = [
        {"entry_type": "income", "amount": 5000},
        {"entry_type": "expense", "amount": 1200},
        {"entry_type": "expense", "amount": 800},
    ]
    results = [
        {"entry_type": "expense", "amount": 1200, "bank_amount": -1200, "status": "OPŁACONA"},
        {"entry_type": "expense", "amount": 800, "status": "BRAK"},
    ]
    data = practical_310.safe_to_spend(items, results)
    assert data["unpaid"] == 800
    assert data["savings_target"] == 300
    assert data["envelopes_target"] == 100
    assert data["safe"] == 3800
