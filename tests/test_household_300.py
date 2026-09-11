from pathlib import Path

import household_300 as h


def _sandbox(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APPDATA", str(tmp_path))


def test_members_and_savings_are_local(monkeypatch, tmp_path):
    _sandbox(monkeypatch, tmp_path)
    member = h.save_member({"name": "Ala", "monthly_income": 5000})
    account = h.save_savings_account({"name": "Poduszka", "owner_id": member["id"], "balance": 1000, "monthly_target": 500})
    h.add_savings_movement(account["id"], 250, "test")

    saved = h.savings_summary()
    assert saved["total"] == 1250
    assert saved["monthly_target"] == 500
    assert h.member_name(member["id"]) == "Ala"
    assert (tmp_path / "PayCheck" / "members.json").exists()
    assert (tmp_path / "PayCheck" / "savings_accounts.json").exists()


def test_envelopes_and_subscriptions(monkeypatch, tmp_path):
    _sandbox(monkeypatch, tmp_path)
    h.save_envelope({"name": "Wakacje", "balance": 1200, "monthly": 300, "target": 5000})
    h.save_subscription({"name": "Streaming", "monthly": 40, "payment_day": 12})

    envelopes = h.envelope_summary()
    subscriptions = h.subscriptions_summary()
    assert envelopes["total"] == 1200
    assert envelopes["monthly"] == 300
    assert subscriptions["monthly"] == 40
    assert subscriptions["annual"] == 480


def test_net_worth(monkeypatch, tmp_path):
    _sandbox(monkeypatch, tmp_path)
    h.save_savings_account({"name": "Lokata", "balance": 10000})
    h.save_asset({"name": "Auto", "value": 30000})
    h.save_debt({"name": "Kredyt", "balance": 15000, "monthly": 700})

    worth = h.net_worth(5000)
    assert worth["gross"] == 45000
    assert worth["debts"] == 15000
    assert worth["net"] == 30000


def test_household_overview(monkeypatch, tmp_path):
    _sandbox(monkeypatch, tmp_path)
    h.save_member({"name": "A", "monthly_income": 4000})
    h.save_member({"name": "B", "monthly_income": 3000})
    h.save_debt({"name": "Rata", "balance": 8000, "monthly": 500})
    data = h.household_overview(0)
    assert data["members_count"] == 2
    assert data["household_income"] == 7000
    assert data["debt_monthly"] == 500
    assert data["offline"] is True
    assert data["api_ready"] is True
