from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from app_100 import BLUE, GREEN, ORANGE, PURPLE, TEAL
from app_300 import PayCheck300App
from budget_200 import wallet_summary
from household_300 import load_envelopes, load_members, member_name
from practical_310 import (
    FEATURES,
    apply_feature_preset,
    assign_transaction_owners,
    delete_owner_rule,
    fund_all_monthly_envelopes,
    fund_envelope,
    load_feature_settings,
    load_owner_rules,
    load_settlements,
    safe_to_spend,
    save_feature_settings,
    save_owner_rule,
    save_settlement,
    set_settlement_done,
    settlement_balances,
)


BG = "#D9DDE2"
TEXT = "#22272B"


class FeatureSettingsWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck310App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Widoczność funkcji")
        self.geometry("620x650")
        self.resizable(False, False)
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Widoczność funkcji", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Ukrycie funkcji nie usuwa żadnych danych. Możesz ją ponownie włączyć w każdej chwili.",
            wraplength=560,
        ).pack(anchor="w", pady=(3, 12))

        presets = ttk.Frame(root)
        presets.pack(fill="x", pady=(0, 10))
        ttk.Button(presets, text="Tryb prosty", command=lambda: self._preset("simple")).pack(side="left")
        ttk.Button(presets, text="Tryb pełny", command=lambda: self._preset("full")).pack(side="left", padx=7)

        self.vars: dict[str, tk.BooleanVar] = {}
        box = ttk.LabelFrame(root, text="Pokaż w programie", padding=10)
        box.pack(fill="both", expand=True)
        settings = load_feature_settings()
        for key, label in FEATURES.items():
            var = tk.BooleanVar(value=settings.get(key, True))
            self.vars[key] = var
            ttk.Checkbutton(box, text=label, variable=var).pack(anchor="w", pady=3)

        ttk.Button(root, text="Zapisz i odśwież", command=self._save).pack(anchor="e", pady=(12, 0))

    def _preset(self, name: str) -> None:
        settings = apply_feature_preset(name)
        for key, var in self.vars.items():
            var.set(settings.get(key, True))

    def _save(self) -> None:
        save_feature_settings({key: var.get() for key, var in self.vars.items()})
        messagebox.showinfo(
            "Widoczność funkcji",
            "Zapisano. Główny ekran odświeży się teraz; niektóre pozycje menu zastosują się po ponownym uruchomieniu.",
            parent=self,
        )
        self.app._apply_feature_visibility()
        self.destroy()


class PracticalCenter(tk.Toplevel):
    def __init__(self, app: "PayCheck310App") -> None:
        super().__init__(app)
        self.app = app
        self.title("PayCheck — Praktyczne finanse")
        self.geometry("1120x720")
        self.minsize(900, 580)
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Praktyczne finanse", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(root, text="Najważniejsze rzeczy do codziennego użycia — bez przeładowania ekranu.").pack(anchor="w", pady=(2, 10))

        settings = load_feature_settings()
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True)

        if settings.get("safe_to_spend", True):
            self.safe_tab = ttk.Frame(nb, padding=12)
            nb.add(self.safe_tab, text="Bezpiecznie do wydania")
            self._build_safe()
        if settings.get("envelopes", True):
            self.envelope_tab = ttk.Frame(nb, padding=12)
            nb.add(self.envelope_tab, text="Koperty")
            self._build_envelopes()
        if settings.get("settlements", True):
            self.settlement_tab = ttk.Frame(nb, padding=12)
            nb.add(self.settlement_tab, text="Rozliczenia")
            self._build_settlements()
        if settings.get("members", True):
            self.rules_tab = ttk.Frame(nb, padding=12)
            nb.add(self.rules_tab, text="Przypisywanie wydatków")
            self._build_rules()

        self.refresh()

    def _build_safe(self) -> None:
        self.safe_vars: dict[str, tk.StringVar] = {}
        cards = ttk.Frame(self.safe_tab)
        cards.pack(fill="x", pady=(0, 14))
        for key, label in (
            ("safe", "Możesz bezpiecznie wydać"),
            ("unpaid", "Jeszcze do opłacenia"),
            ("reserve", "Rezerwa na oszczędności i koperty"),
        ):
            box = ttk.LabelFrame(cards, text=label, padding=10)
            box.pack(side="left", fill="x", expand=True, padx=(0, 8))
            var = tk.StringVar(value="—")
            self.safe_vars[key] = var
            ttk.Label(box, textvariable=var, font=("Segoe UI", 16, "bold")).pack(anchor="w")
        self.safe_note = tk.StringVar()
        ttk.Label(self.safe_tab, textvariable=self.safe_note, wraplength=850).pack(anchor="w")

    def _build_envelopes(self) -> None:
        cols = ("name", "balance", "monthly", "target")
        self.env_tree = ttk.Treeview(self.envelope_tab, columns=cols, show="headings")
        for key, label, width in (("name", "Koperta", 240), ("balance", "Stan", 140), ("monthly", "Co miesiąc", 140), ("target", "Cel", 140)):
            self.env_tree.heading(key, text=label)
            self.env_tree.column(key, width=width, anchor="w")
        self.env_tree.pack(fill="both", expand=True)
        bar = ttk.Frame(self.envelope_tab)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Wpłać / wypłać", command=self._fund_selected).pack(side="left")
        ttk.Button(bar, text="Zasil wszystkie miesięcznie", command=self._fund_all).pack(side="left", padx=7)

    def _build_settlements(self) -> None:
        cols = ("date", "description", "payer", "for", "amount", "status")
        self.set_tree = ttk.Treeview(self.settlement_tab, columns=cols, show="headings")
        heads = (("date", "Data", 100), ("description", "Opis", 250), ("payer", "Zapłacił", 140), ("for", "Za kogo", 140), ("amount", "Kwota", 120), ("status", "Status", 120))
        for key, label, width in heads:
            self.set_tree.heading(key, text=label)
            self.set_tree.column(key, width=width, anchor="w")
        self.set_tree.pack(fill="both", expand=True)
        bar = ttk.Frame(self.settlement_tab)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj rozliczenie", command=self._add_settlement).pack(side="left")
        ttk.Button(bar, text="Oznacz jako rozliczone", command=self._settle_selected).pack(side="left", padx=7)
        self.balance_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.balance_var).pack(side="right")

    def _build_rules(self) -> None:
        cols = ("phrase", "owner")
        self.rule_tree = ttk.Treeview(self.rules_tab, columns=cols, show="headings")
        self.rule_tree.heading("phrase", text="Fraza z wyciągu")
        self.rule_tree.heading("owner", text="Użytkownik")
        self.rule_tree.column("phrase", width=420)
        self.rule_tree.column("owner", width=220)
        self.rule_tree.pack(fill="both", expand=True)
        bar = ttk.Frame(self.rules_tab)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="+ Dodaj regułę", command=self._add_rule).pack(side="left")
        ttk.Button(bar, text="Usuń", command=self._delete_rule).pack(side="left", padx=7)
        ttk.Label(bar, text="Najdłuższa pasująca fraza ma pierwszeństwo.").pack(side="right")

    @staticmethod
    def _choose_member(parent, prompt: str) -> str | None:
        members = [row for row in load_members() if row.get("active", True)]
        if not members:
            messagebox.showinfo("Użytkownicy", "Najpierw dodaj użytkowników w Panelu Domowym.", parent=parent)
            return None
        names = [row.get("name", "") for row in members]
        value = simpledialog.askstring("Użytkownik", prompt + "\n" + " / ".join(names), parent=parent)
        if value is None:
            return None
        for row in members:
            if row.get("name", "").strip().lower() == value.strip().lower():
                return row.get("id", "")
        messagebox.showerror("Użytkownik", "Nie znaleziono takiego użytkownika.", parent=parent)
        return None

    def _fund_selected(self) -> None:
        sel = self.env_tree.selection()
        if not sel:
            messagebox.showinfo("Koperty", "Zaznacz kopertę.", parent=self)
            return
        value = simpledialog.askstring("Koperta", "Kwota: dodatnia = wpłata, ujemna = wypłata:", parent=self)
        if value is None:
            return
        try:
            amount = float(value.replace(",", "."))
            fund_envelope(sel[0], amount)
        except Exception as exc:
            messagebox.showerror("Koperty", str(exc), parent=self)
            return
        self.refresh()

    def _fund_all(self) -> None:
        if not messagebox.askyesno("Koperty", "Dodać do każdej aktywnej koperty jej miesięczną kwotę?", parent=self):
            return
        total = fund_all_monthly_envelopes()
        messagebox.showinfo("Koperty", f"Łącznie odłożono: {total:.2f} zł", parent=self)
        self.refresh()

    def _add_settlement(self) -> None:
        description = simpledialog.askstring("Rozliczenie", "Opis:", parent=self)
        if not description:
            return
        payer = self._choose_member(self, "Kto zapłacił?")
        if payer is None:
            return
        beneficiary = self._choose_member(self, "Za kogo zapłacił?")
        if beneficiary is None:
            return
        value = simpledialog.askstring("Rozliczenie", "Kwota:", parent=self)
        if value is None:
            return
        try:
            save_settlement({"description": description, "payer_id": payer, "for_id": beneficiary, "amount": float(value.replace(",", "."))})
        except Exception as exc:
            messagebox.showerror("Rozliczenie", str(exc), parent=self)
            return
        self.refresh()

    def _settle_selected(self) -> None:
        sel = self.set_tree.selection()
        if sel:
            set_settlement_done(sel[0], True)
            self.refresh()

    def _add_rule(self) -> None:
        phrase = simpledialog.askstring("Przypisywanie", "Fraza z opisu bankowego, np. ORLEN / BIEDRONKA / NETFLIX:", parent=self)
        if not phrase:
            return
        owner = self._choose_member(self, "Do kogo przypisać pasujące transakcje?")
        if owner is None:
            return
        save_owner_rule(phrase, owner)
        self.refresh()

    def _delete_rule(self) -> None:
        sel = self.rule_tree.selection()
        if sel:
            delete_owner_rule(sel[0])
            self.refresh()

    def refresh(self) -> None:
        if hasattr(self, "safe_vars"):
            wallets = wallet_summary(self.app.transactions)
            wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
            data = safe_to_spend(self.app.items, self.app.results, wallet_total)
            reserve = data["savings_target"] + data["envelopes_target"]
            self.safe_vars["safe"].set(f"{data['safe']:.2f} zł")
            self.safe_vars["unpaid"].set(f"{data['unpaid']:.2f} zł")
            self.safe_vars["reserve"].set(f"{reserve:.2f} zł")
            self.safe_note.set("To kwota orientacyjna: saldo/dochód minus nieopłacone wydatki oraz planowane odkładanie. Nie zastępuje salda bankowego.")

        if hasattr(self, "env_tree"):
            self.env_tree.delete(*self.env_tree.get_children())
            for row in load_envelopes():
                self.env_tree.insert("", "end", iid=row["id"], values=(row.get("name", ""), f"{float(row.get('balance') or 0):.2f} zł", f"{float(row.get('monthly') or 0):.2f} zł", "—" if not row.get("target") else f"{float(row.get('target') or 0):.2f} zł"))

        if hasattr(self, "set_tree"):
            self.set_tree.delete(*self.set_tree.get_children())
            for row in load_settlements():
                self.set_tree.insert("", "end", iid=row["id"], values=(row.get("date", ""), row.get("description", ""), member_name(row.get("payer_id", "")), member_name(row.get("for_id", "")), f"{float(row.get('amount') or 0):.2f} zł", "Rozliczone" if row.get("settled") else "Do rozliczenia"))
            balances = settlement_balances()
            parts = [f"{member_name(mid)} {value:+.2f} zł" for mid, value in balances.items() if abs(value) >= 0.01]
            self.balance_var.set(" | ".join(parts) if parts else "Brak nierozliczonych kwot")

        if hasattr(self, "rule_tree"):
            self.rule_tree.delete(*self.rule_tree.get_children())
            for row in load_owner_rules():
                self.rule_tree.insert("", "end", iid=row["id"], values=(row.get("phrase", ""), member_name(row.get("owner_id", ""))))

        self.app._refresh_practical_card()


class PayCheck310App(PayCheck300App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 3.1.0 — Domowy system finansów offline")
        self._build_practical_ui()
        self._extend_settings_menu()
        self._apply_feature_visibility()
        self._refresh_practical_card()

    def _build_practical_ui(self) -> None:
        self.practical_button = self._action_button(self.quick_frame, "Praktyczne", TEAL, self._show_practical)
        self.practical_button.pack(side="left", padx=(7, 0))
        self.safe_card = tk.Frame(self.household_strip, bg=GREEN)
        self.safe_card.pack(side="left", fill="x", expand=True, padx=(0, 7))
        tk.Label(self.safe_card, text="Bezpiecznie do wydania", bg=GREEN, fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(7, 0))
        self.safe_var = tk.StringVar(value="—")
        tk.Label(self.safe_card, textvariable=self.safe_var, bg=GREEN, fg="white", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=(1, 7))

    def _extend_settings_menu(self) -> None:
        menu = self.nametowidget(self.cget("menu"))
        visibility = tk.Menu(menu, tearoff=False)
        visibility.add_command(label="Widoczność funkcji", command=self._show_visibility)
        visibility.add_command(label="Tryb prosty", command=lambda: self._set_preset("simple"))
        visibility.add_command(label="Tryb pełny", command=lambda: self._set_preset("full"))
        menu.add_cascade(label="Widok", menu=visibility)

    def _set_preset(self, name: str) -> None:
        apply_feature_preset(name)
        self._apply_feature_visibility()

    def _show_visibility(self) -> None:
        FeatureSettingsWindow(self)

    def _show_practical(self) -> None:
        PracticalCenter(self)

    def _feature_for_button(self, text: str) -> str | None:
        mapping = {
            "Kalendarz": "calendar",
            "Cele": "goals",
            "Limity": "limits",
            "Konta": "accounts",
            "Rok": "annual",
            "Dom": "members",
            "Oszczędności": "savings",
            "Praktyczne": "safe_to_spend",
        }
        return mapping.get(text)

    def _apply_feature_visibility(self) -> None:
        settings = load_feature_settings()
        for child in self.quick_frame.winfo_children():
            if not isinstance(child, tk.Button):
                continue
            text = str(child.cget("text")).split(" (")[0]
            key = self._feature_for_button(text)
            if key and not settings.get(key, True):
                child.pack_forget()
            elif key and not child.winfo_manager():
                child.pack(side="left", padx=(7, 0))

        if hasattr(self, "household_strip"):
            if settings.get("savings", True):
                pass
            # karty dziedziczone zostają zachowane w danych, ale można je schować po etykiecie
            for box in self.household_strip.winfo_children():
                labels = [c.cget("text") for c in box.winfo_children() if isinstance(c, tk.Label) and not c.cget("textvariable")]
                title = labels[0] if labels else ""
                key = {"Oszczędności": "savings", "Koperty": "envelopes", "Subskrypcje / mies.": "subscriptions", "Majątek netto": "net_worth", "Bezpiecznie do wydania": "safe_to_spend"}.get(title)
                if key and not settings.get(key, True):
                    box.pack_forget()
                elif key and not box.winfo_manager():
                    box.pack(side="left", fill="x", expand=True, padx=(0, 7))

    def _refresh_practical_card(self) -> None:
        if not hasattr(self, "safe_var"):
            return
        wallets = wallet_summary(self.transactions)
        wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
        data = safe_to_spend(self.items, self.results, wallet_total)
        self.safe_var.set(f"{data['safe']:.2f} zł")

    def _compare(self) -> None:
        super()._compare()
        self.transactions = assign_transaction_owners(self.transactions)
        self._refresh_practical_card()

    def _restore_state(self, state: dict) -> None:
        super()._restore_state(state)
        self.transactions = assign_transaction_owners(self.transactions)
        self._refresh_practical_card()


if __name__ == "__main__":
    PayCheck310App().mainloop()
