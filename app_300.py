from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from app_100 import BLUE, GREEN, ORANGE, PURPLE, RED, TEAL
from app_210 import PayCheck210App
from budget_200 import wallet_summary
from household_300 import (
    add_savings_movement,
    delete_asset,
    delete_debt,
    delete_envelope,
    delete_member,
    delete_savings_account,
    delete_subscription,
    household_overview,
    load_assets,
    load_debts,
    load_envelopes,
    load_members,
    load_savings_accounts,
    load_subscriptions,
    member_name,
    save_asset,
    save_debt,
    save_envelope,
    save_member,
    save_savings_account,
    save_subscription,
)


BG = "#D9DDE2"
PANEL = "#EEF1F4"
TEXT = "#22272B"


def _ask_money(parent, title: str, prompt: str, initial: float = 0.0) -> float | None:
    value = simpledialog.askstring(title, prompt, initialvalue=f"{initial:.2f}", parent=parent)
    if value is None:
        return None
    try:
        return float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        messagebox.showerror(title, "Podaj prawidłową kwotę.", parent=parent)
        return None


def _member_choice(parent, current: str = "") -> str | None:
    members = [row for row in load_members() if row.get("active", True)]
    choices = ["Wspólne"] + [row.get("name", "") for row in members]
    initial = member_name(current) if current else "Wspólne"
    value = simpledialog.askstring(
        "Właściciel",
        "Wpisz właściciela dokładnie jak poniżej:\n" + " / ".join(choices),
        initialvalue=initial,
        parent=parent,
    )
    if value is None:
        return None
    if value.strip().lower() == "wspólne":
        return ""
    for row in members:
        if row.get("name", "").strip().lower() == value.strip().lower():
            return row.get("id", "")
    messagebox.showerror("Właściciel", "Nie znaleziono takiego użytkownika.", parent=parent)
    return None


class HouseholdCenter(tk.Toplevel):
    def __init__(self, app: "PayCheck300App") -> None:
        super().__init__(app)
        self.app = app
        self.title("PayCheck — Gospodarstwo domowe")
        self.geometry("1250x760")
        self.minsize(980, 620)

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Gospodarstwo domowe", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Wszystkie dane są przechowywane lokalnie na tym komputerze. Internet nie jest wymagany.",
        ).pack(anchor="w", pady=(2, 10))

        self.summary = tk.StringVar()
        ttk.Label(root, textvariable=self.summary, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True)
        self.tabs = {}
        for key, label in (
            ("members", "Użytkownicy"),
            ("savings", "Oszczędności"),
            ("envelopes", "Koperty"),
            ("subscriptions", "Subskrypcje"),
            ("worth", "Majątek netto"),
        ):
            frame = ttk.Frame(nb, padding=10)
            nb.add(frame, text=label)
            self.tabs[key] = frame

        self._build_members()
        self._build_savings()
        self._build_envelopes()
        self._build_subscriptions()
        self._build_worth()
        self.refresh()

    @staticmethod
    def _tree(parent, columns: list[tuple[str, str, int]]):
        keys = tuple(row[0] for row in columns)
        tree = ttk.Treeview(parent, columns=keys, show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def _build_members(self):
        tab = self.tabs["members"]
        self.members_tree = self._tree(tab, [
            ("name", "Osoba", 220), ("income", "Dochód mies.", 150), ("status", "Status", 100)
        ])
        bar = ttk.Frame(tab); bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj osobę", command=self._add_member).pack(side="left")
        ttk.Button(bar, text="Edytuj", command=self._edit_member).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń", command=self._delete_member).pack(side="left")

    def _build_savings(self):
        tab = self.tabs["savings"]
        self.savings_tree = self._tree(tab, [
            ("name", "Konto / skarbonka", 240), ("owner", "Właściciel", 140),
            ("kind", "Typ", 150), ("balance", "Stan", 130), ("monthly", "Cel / mies.", 130)
        ])
        bar = ttk.Frame(tab); bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj konto", command=self._add_savings).pack(side="left")
        ttk.Button(bar, text="Wpłata / wypłata", command=self._movement).pack(side="left", padx=6)
        ttk.Button(bar, text="Edytuj", command=self._edit_savings).pack(side="left")
        ttk.Button(bar, text="Usuń", command=self._delete_savings).pack(side="left", padx=6)

    def _build_envelopes(self):
        tab = self.tabs["envelopes"]
        self.envelopes_tree = self._tree(tab, [
            ("name", "Koperta", 220), ("owner", "Właściciel", 140), ("balance", "Odłożono", 130),
            ("monthly", "Co miesiąc", 130), ("target", "Cel", 130), ("progress", "Postęp", 100)
        ])
        bar = ttk.Frame(tab); bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj kopertę", command=self._add_envelope).pack(side="left")
        ttk.Button(bar, text="Edytuj", command=self._edit_envelope).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń", command=self._delete_envelope).pack(side="left")

    def _build_subscriptions(self):
        tab = self.tabs["subscriptions"]
        self.sub_tree = self._tree(tab, [
            ("name", "Subskrypcja", 230), ("owner", "Właściciel", 140), ("monthly", "Miesięcznie", 130),
            ("annual", "Rocznie", 130), ("day", "Dzień płatności", 130)
        ])
        bar = ttk.Frame(tab); bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj", command=self._add_subscription).pack(side="left")
        ttk.Button(bar, text="Edytuj", command=self._edit_subscription).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń", command=self._delete_subscription).pack(side="left")

    def _build_worth(self):
        tab = self.tabs["worth"]
        cards = ttk.Frame(tab); cards.pack(fill="x", pady=(0, 10))
        self.worth_vars = {}
        for key, label in (("gross", "Aktywa razem"), ("debts", "Długi"), ("net", "Majątek netto")):
            box = ttk.LabelFrame(cards, text=label, padding=10); box.pack(side="left", fill="x", expand=True, padx=(0, 7))
            var = tk.StringVar(value="—"); self.worth_vars[key] = var
            ttk.Label(box, textvariable=var, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.asset_tree = self._tree(tab, [
            ("type", "Rodzaj", 110), ("name", "Nazwa", 220), ("owner", "Właściciel", 140),
            ("kind", "Typ", 150), ("value", "Wartość / saldo", 160)
        ])
        bar = ttk.Frame(tab); bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Aktywo", command=self._add_asset).pack(side="left")
        ttk.Button(bar, text="+ Dług", command=self._add_debt).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń zaznaczone", command=self._delete_worth_item).pack(side="left")

    def _selected_id(self, tree):
        sel = tree.selection()
        return sel[0] if sel else None

    def _add_member(self, row=None):
        name = simpledialog.askstring("Użytkownik", "Imię / nazwa profilu:", initialvalue=(row or {}).get("name", ""), parent=self)
        if not name: return
        income = _ask_money(self, "Użytkownik", "Domyślny miesięczny dochód:", float((row or {}).get("monthly_income") or 0))
        if income is None: return
        save_member({**(row or {}), "name": name, "monthly_income": income, "active": True})
        self.refresh()

    def _edit_member(self):
        rid = self._selected_id(self.members_tree)
        row = next((r for r in load_members() if r.get("id") == rid), None)
        if row: self._add_member(row)

    def _delete_member(self):
        rid = self._selected_id(self.members_tree)
        if rid and messagebox.askyesno("Użytkownicy", "Usunąć profil? Powiązane rekordy zachowają swoje ID.", parent=self):
            delete_member(rid); self.refresh()

    def _add_savings(self, row=None):
        row = row or {}
        name = simpledialog.askstring("Oszczędności", "Nazwa konta / skarbonki:", initialvalue=row.get("name", ""), parent=self)
        if not name: return
        owner = _member_choice(self, row.get("owner_id", ""))
        if owner is None: return
        kind = simpledialog.askstring("Oszczędności", "Typ, np. Poduszka / Lokata / Gotówka:", initialvalue=row.get("kind", "Oszczędności"), parent=self) or "Oszczędności"
        balance = _ask_money(self, "Oszczędności", "Aktualny stan:", float(row.get("balance") or 0))
        if balance is None: return
        monthly = _ask_money(self, "Oszczędności", "Ile chcesz odkładać miesięcznie:", float(row.get("monthly_target") or 0))
        if monthly is None: return
        save_savings_account({**row, "name": name, "owner_id": owner, "kind": kind, "balance": balance, "monthly_target": monthly, "active": True})
        self.refresh()

    def _edit_savings(self):
        rid = self._selected_id(self.savings_tree)
        row = next((r for r in load_savings_accounts() if r.get("id") == rid), None)
        if row: self._add_savings(row)

    def _delete_savings(self):
        rid = self._selected_id(self.savings_tree)
        if rid and messagebox.askyesno("Oszczędności", "Usunąć konto oszczędnościowe?", parent=self):
            delete_savings_account(rid); self.refresh()

    def _movement(self):
        rid = self._selected_id(self.savings_tree)
        if not rid:
            messagebox.showinfo("Oszczędności", "Najpierw zaznacz konto.", parent=self); return
        amount = _ask_money(self, "Wpłata / wypłata", "Kwota: dodatnia = wpłata, ujemna = wypłata:", 0)
        if amount is None or amount == 0: return
        note = simpledialog.askstring("Wpłata / wypłata", "Opis (opcjonalnie):", parent=self) or ""
        add_savings_movement(rid, amount, note)
        self.refresh()

    def _add_envelope(self, row=None):
        row = row or {}
        name = simpledialog.askstring("Koperta", "Nazwa, np. Wakacje / OC / Serwis auta:", initialvalue=row.get("name", ""), parent=self)
        if not name: return
        owner = _member_choice(self, row.get("owner_id", ""))
        if owner is None: return
        balance = _ask_money(self, "Koperta", "Aktualnie odłożono:", float(row.get("balance") or 0));
        if balance is None: return
        monthly = _ask_money(self, "Koperta", "Odkładaj miesięcznie:", float(row.get("monthly") or 0));
        if monthly is None: return
        target = _ask_money(self, "Koperta", "Cel kwotowy (0 = bez celu):", float(row.get("target") or 0));
        if target is None: return
        save_envelope({**row, "name": name, "owner_id": owner, "balance": balance, "monthly": monthly, "target": target, "active": True})
        self.refresh()

    def _edit_envelope(self):
        rid = self._selected_id(self.envelopes_tree)
        row = next((r for r in load_envelopes() if r.get("id") == rid), None)
        if row: self._add_envelope(row)

    def _delete_envelope(self):
        rid = self._selected_id(self.envelopes_tree)
        if rid and messagebox.askyesno("Koperty", "Usunąć kopertę?", parent=self):
            delete_envelope(rid); self.refresh()

    def _add_subscription(self, row=None):
        row = row or {}
        name = simpledialog.askstring("Subskrypcja", "Nazwa:", initialvalue=row.get("name", ""), parent=self)
        if not name: return
        owner = _member_choice(self, row.get("owner_id", ""))
        if owner is None: return
        monthly = _ask_money(self, "Subskrypcja", "Koszt miesięczny:", float(row.get("monthly") or 0))
        if monthly is None: return
        day = simpledialog.askinteger("Subskrypcja", "Dzień płatności (1-31, 0 = nieznany):", initialvalue=int(row.get("payment_day") or 0), minvalue=0, maxvalue=31, parent=self)
        if day is None: return
        save_subscription({**row, "name": name, "owner_id": owner, "monthly": monthly, "payment_day": day, "active": True})
        self.refresh()

    def _edit_subscription(self):
        rid = self._selected_id(self.sub_tree)
        row = next((r for r in load_subscriptions() if r.get("id") == rid), None)
        if row: self._add_subscription(row)

    def _delete_subscription(self):
        rid = self._selected_id(self.sub_tree)
        if rid and messagebox.askyesno("Subskrypcje", "Usunąć subskrypcję?", parent=self):
            delete_subscription(rid); self.refresh()

    def _add_asset(self):
        name = simpledialog.askstring("Majątek", "Nazwa aktywa, np. Samochód / Gotówka:", parent=self)
        if not name: return
        owner = _member_choice(self)
        if owner is None: return
        kind = simpledialog.askstring("Majątek", "Typ aktywa:", initialvalue="Inne", parent=self) or "Inne"
        value = _ask_money(self, "Majątek", "Szacowana wartość:", 0)
        if value is None: return
        save_asset({"name": name, "owner_id": owner, "kind": kind, "value": value, "active": True}); self.refresh()

    def _add_debt(self):
        name = simpledialog.askstring("Dług", "Nazwa zobowiązania:", parent=self)
        if not name: return
        owner = _member_choice(self)
        if owner is None: return
        balance = _ask_money(self, "Dług", "Pozostałe saldo zadłużenia:", 0)
        if balance is None: return
        monthly = _ask_money(self, "Dług", "Miesięczna rata / spłata:", 0)
        if monthly is None: return
        save_debt({"name": name, "owner_id": owner, "balance": balance, "monthly": monthly, "active": True}); self.refresh()

    def _delete_worth_item(self):
        rid = self._selected_id(self.asset_tree)
        if not rid: return
        if rid.startswith("A:"): delete_asset(rid[2:])
        elif rid.startswith("D:"): delete_debt(rid[2:])
        self.refresh()

    def refresh(self):
        wallets = wallet_summary(self.app.transactions)
        wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
        overview = household_overview(wallet_total)
        self.summary.set(
            f"Domownicy: {overview['members_count']}  |  Oszczędności: {overview['savings']['total']:.2f} zł  |  "
            f"Koperty: {overview['envelopes']['total']:.2f} zł  |  Subskrypcje: {overview['subscriptions']['monthly']:.2f} zł / mies."
        )

        self.members_tree.delete(*self.members_tree.get_children())
        for row in load_members():
            self.members_tree.insert("", "end", iid=row["id"], values=(row.get("name", ""), f"{float(row.get('monthly_income') or 0):.2f} zł", "Aktywny" if row.get("active", True) else "Nieaktywny"))

        self.savings_tree.delete(*self.savings_tree.get_children())
        for row in load_savings_accounts():
            self.savings_tree.insert("", "end", iid=row["id"], values=(row.get("name", ""), member_name(row.get("owner_id", "")), row.get("kind", ""), f"{float(row.get('balance') or 0):.2f} zł", f"{float(row.get('monthly_target') or 0):.2f} zł"))

        self.envelopes_tree.delete(*self.envelopes_tree.get_children())
        for row in load_envelopes():
            target = float(row.get("target") or 0); balance = float(row.get("balance") or 0)
            progress = balance / target * 100 if target else 0
            self.envelopes_tree.insert("", "end", iid=row["id"], values=(row.get("name", ""), member_name(row.get("owner_id", "")), f"{balance:.2f} zł", f"{float(row.get('monthly') or 0):.2f} zł", "—" if not target else f"{target:.2f} zł", "—" if not target else f"{progress:.0f}%"))

        self.sub_tree.delete(*self.sub_tree.get_children())
        for row in load_subscriptions():
            monthly = float(row.get("monthly") or 0)
            self.sub_tree.insert("", "end", iid=row["id"], values=(row.get("name", ""), member_name(row.get("owner_id", "")), f"{monthly:.2f} zł", f"{monthly * 12:.2f} zł", row.get("payment_day") or "—"))

        worth = overview["net_worth"]
        self.worth_vars["gross"].set(f"{worth['gross']:.2f} zł")
        self.worth_vars["debts"].set(f"{worth['debts']:.2f} zł")
        self.worth_vars["net"].set(f"{worth['net']:+.2f} zł")
        self.asset_tree.delete(*self.asset_tree.get_children())
        for row in load_assets():
            self.asset_tree.insert("", "end", iid="A:" + row["id"], values=("Aktywo", row.get("name", ""), member_name(row.get("owner_id", "")), row.get("kind", ""), f"{float(row.get('value') or 0):.2f} zł"))
        for row in load_debts():
            self.asset_tree.insert("", "end", iid="D:" + row["id"], values=("Dług", row.get("name", ""), member_name(row.get("owner_id", "")), "Zobowiązanie", f"-{float(row.get('balance') or 0):.2f} zł"))

        self.app._refresh_household_cards()


class PayCheck300App(PayCheck210App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 3.0.0 — Domowy system finansów offline")
        self.geometry("1500x920")
        self._build_household_actions()
        self._build_household_cards()
        self._extend_household_menu()
        self._refresh_household_cards()

    def _build_household_actions(self):
        self._action_button(self.quick_frame, "Dom", "#455A64", self._show_household).pack(side="left", padx=(7, 0))
        self._action_button(self.quick_frame, "Oszczędności", GREEN, self._show_household).pack(side="left", padx=(7, 0))

    def _build_household_cards(self):
        self.household_strip = tk.Frame(self.tree.master, bg=BG)
        self.household_strip.pack(fill="x", pady=(0, 8), before=self.tree)
        self.household_vars = {}
        for key, label, color in (
            ("savings", "Oszczędności", GREEN),
            ("envelopes", "Koperty", TEAL),
            ("subscriptions", "Subskrypcje / mies.", ORANGE),
            ("net", "Majątek netto", PURPLE),
        ):
            box = tk.Frame(self.household_strip, bg=color)
            box.pack(side="left", fill="x", expand=True, padx=(0, 7))
            var = tk.StringVar(value="—"); self.household_vars[key] = var
            tk.Label(box, text=label, bg=color, fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
            tk.Label(box, textvariable=var, bg=color, fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=(1, 7))

    def _extend_household_menu(self):
        menu = self.nametowidget(self.cget("menu"))
        household = tk.Menu(menu, tearoff=False)
        household.add_command(label="Panel domowy", command=self._show_household)
        household.add_command(label="Użytkownicy", command=self._show_household)
        household.add_command(label="Oszczędności i koperty", command=self._show_household)
        household.add_command(label="Subskrypcje", command=self._show_household)
        household.add_command(label="Majątek netto", command=self._show_household)
        menu.insert_cascade(1, label="Dom", menu=household)

    def _show_household(self):
        HouseholdCenter(self)

    def _refresh_household_cards(self):
        if not hasattr(self, "household_vars"):
            return
        wallets = wallet_summary(self.transactions)
        wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
        data = household_overview(wallet_total)
        self.household_vars["savings"].set(f"{data['savings']['total']:.2f} zł")
        self.household_vars["envelopes"].set(f"{data['envelopes']['total']:.2f} zł")
        self.household_vars["subscriptions"].set(f"{data['subscriptions']['monthly']:.2f} zł")
        self.household_vars["net"].set(f"{data['net_worth']['net']:+.2f} zł")

    def _compare(self) -> None:
        super()._compare()
        self._refresh_household_cards()

    def _restore_state(self, state: dict) -> None:
        super()._restore_state(state)
        self._refresh_household_cards()


if __name__ == "__main__":
    PayCheck300App().mainloop()
