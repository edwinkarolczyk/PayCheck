from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_100 import GREEN, ORANGE, RED, TEAL
from app_310 import PayCheck310App
from bank_merge import load_bank_statements
from budget_200 import wallet_summary
from daily_320 import (
    close_month,
    load_monthly_automation,
    month_close_check,
    net_worth_trend,
    plan_12_months,
    run_monthly_allocations,
    snapshot_net_worth,
    today_overview,
)
from month_state import merge_transactions
from practical_310 import FEATURES, SIMPLE_FEATURES, load_feature_settings


FEATURES.update({
    "today": "Dzisiaj / ten miesiąc",
    "month_close": "Zamknięcie miesiąca",
    "plan_12m": "Plan 12 miesięcy",
    "monthly_allocations": "Miesięczne odkładanie",
    "net_worth_history": "Historia majątku netto",
})
SIMPLE_FEATURES.update({
    "today": True,
    "month_close": True,
    "plan_12m": False,
    "monthly_allocations": True,
    "net_worth_history": False,
})


class TodayCenter(tk.Toplevel):
    def __init__(self, app: "PayCheck320App") -> None:
        super().__init__(app)
        self.app = app
        self.title("PayCheck — Dzisiaj / ten miesiąc")
        self.geometry("1180x740")
        self.minsize(900, 580)

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Dzisiaj / ten miesiąc", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Najpierw rzeczy wymagające działania. Szczegółowe moduły zostają w tle i nie musisz ich otwierać codziennie.",
        ).pack(anchor="w", pady=(2, 10))

        settings = load_feature_settings()
        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self.today_tab = ttk.Frame(notebook, padding=12)
        notebook.add(self.today_tab, text="Dzisiaj")
        self._build_today()

        if settings.get("month_close", True):
            self.close_tab = ttk.Frame(notebook, padding=12)
            notebook.add(self.close_tab, text="Zamknięcie miesiąca")
            self._build_close()
        if settings.get("plan_12m", True):
            self.plan_tab = ttk.Frame(notebook, padding=12)
            notebook.add(self.plan_tab, text="Plan 12 miesięcy")
            self._build_plan()
        if settings.get("monthly_allocations", True):
            self.alloc_tab = ttk.Frame(notebook, padding=12)
            notebook.add(self.alloc_tab, text="Odkładanie")
            self._build_allocations()
        if settings.get("net_worth_history", True):
            self.worth_tab = ttk.Frame(notebook, padding=12)
            notebook.add(self.worth_tab, text="Historia majątku")
            self._build_worth()

        self.refresh()

    def _build_today(self) -> None:
        cards = ttk.Frame(self.today_tab)
        cards.pack(fill="x", pady=(0, 10))
        self.today_vars: dict[str, tk.StringVar] = {}
        for key, label in (
            ("safe", "Bezpiecznie do wydania"),
            ("overdue", "Po terminie"),
            ("review", "Do zatwierdzenia"),
            ("week", "Płatności w 7 dni"),
        ):
            box = ttk.LabelFrame(cards, text=label, padding=10)
            box.pack(side="left", fill="x", expand=True, padx=(0, 7))
            var = tk.StringVar(value="—")
            self.today_vars[key] = var
            ttk.Label(box, textvariable=var, font=("Segoe UI", 16, "bold")).pack(anchor="w")

        self.action_tree = ttk.Treeview(
            self.today_tab,
            columns=("kind", "date", "name", "amount", "status"),
            show="headings",
        )
        for key, label, width in (
            ("kind", "Rodzaj", 130), ("date", "Termin", 110),
            ("name", "Pozycja", 300), ("amount", "Kwota", 120), ("status", "Status", 150),
        ):
            self.action_tree.heading(key, text=label)
            self.action_tree.column(key, width=width, anchor="w")
        self.action_tree.pack(fill="both", expand=True)

    def _build_close(self) -> None:
        self.close_status = tk.StringVar(value="—")
        ttk.Label(self.close_tab, textvariable=self.close_status, font=("Segoe UI", 14, "bold"), wraplength=900).pack(anchor="w", pady=(0, 14))
        ttk.Button(self.close_tab, text="Zamknij miesiąc", command=self._close_month).pack(anchor="w")
        ttk.Label(
            self.close_tab,
            text="Zamknięcie zapisuje punkt kontrolny miesiąca. Nie usuwa ani nie blokuje danych.",
        ).pack(anchor="w", pady=(8, 0))

    def _build_plan(self) -> None:
        self.plan_tree = ttk.Treeview(
            self.plan_tab,
            columns=("month", "installments", "subscriptions", "debts", "savings", "envelopes", "total"),
            show="headings",
        )
        for key, label, width in (
            ("month", "Miesiąc", 100), ("installments", "Raty", 110),
            ("subscriptions", "Subskrypcje", 120), ("debts", "Długi", 110),
            ("savings", "Oszczędności", 120), ("envelopes", "Koperty", 110),
            ("total", "Stałe obciążenie", 140),
        ):
            self.plan_tree.heading(key, text=label)
            self.plan_tree.column(key, width=width, anchor="w")
        self.plan_tree.pack(fill="both", expand=True)

    def _build_allocations(self) -> None:
        self.alloc_status = tk.StringVar(value="—")
        ttk.Label(self.alloc_tab, textvariable=self.alloc_status, font=("Segoe UI", 12, "bold"), wraplength=850).pack(anchor="w", pady=(0, 12))
        ttk.Button(self.alloc_tab, text="Wykonaj miesięczne odkładanie", command=self._run_allocations).pack(anchor="w")
        ttk.Label(
            self.alloc_tab,
            text="Operację można wykonać tylko raz dla danego miesiąca. Zasila aktywne koperty i konta oszczędnościowe ich ustaloną kwotą miesięczną.",
            wraplength=900,
        ).pack(anchor="w", pady=(8, 0))

    def _build_worth(self) -> None:
        self.worth_tree = ttk.Treeview(self.worth_tab, columns=("date", "gross", "debts", "net"), show="headings")
        for key, label, width in (
            ("date", "Data", 130), ("gross", "Aktywa", 180),
            ("debts", "Długi", 180), ("net", "Majątek netto", 190),
        ):
            self.worth_tree.heading(key, text=label)
            self.worth_tree.column(key, width=width, anchor="w")
        self.worth_tree.pack(fill="both", expand=True)
        ttk.Button(self.worth_tab, text="Zapisz punkt teraz", command=self._snapshot_worth).pack(anchor="w", pady=(8, 0))

    def _wallet_total(self) -> float:
        wallets = wallet_summary(self.app.transactions)
        return sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))

    def _close_month(self) -> None:
        check = month_close_check(self.app.items, self.app.results)
        if check["can_close"]:
            row = close_month(self.app.items, self.app.results)
            messagebox.showinfo("Zamknięcie miesiąca", f"Zamknięto: {row['month']}", parent=self)
        else:
            text = "\n".join("• " + item for item in check["blockers"])
            messagebox.showwarning(
                "Miesiąc nie jest gotowy",
                "Najpierw uporządkuj:\n" + text,
                parent=self,
            )
        self.refresh()

    def _run_allocations(self) -> None:
        result = run_monthly_allocations()
        if result.get("already_done"):
            messagebox.showinfo("Odkładanie", f"Dla {result['period']} odkładanie było już wykonane.", parent=self)
        else:
            messagebox.showinfo(
                "Odkładanie",
                f"Odłożono łącznie {result['total']:.2f} zł\n"
                f"Oszczędności: {result['savings']:.2f} zł\nKoperty: {result['envelopes']:.2f} zł",
                parent=self,
            )
        self.refresh()
        self.app._refresh_household_cards()
        self.app._refresh_practical_card()

    def _snapshot_worth(self) -> None:
        snapshot_net_worth(self._wallet_total())
        self.refresh()

    def refresh(self) -> None:
        overview = today_overview(self.app.items, self.app.results, self._wallet_total())
        self.today_vars["safe"].set(f"{overview['safe']['safe']:.2f} zł")
        self.today_vars["overdue"].set(str(len(overview["overdue"])))
        self.today_vars["review"].set(str(len(overview["review"])))
        self.today_vars["week"].set(str(len(overview["week"])))

        self.action_tree.delete(*self.action_tree.get_children())
        for row in overview["overdue"]:
            self.action_tree.insert("", "end", values=("Płatność", row.get("due") or "—", row.get("name", ""), f"{row.get('amount', 0):.2f} zł", "PO TERMINIE"))
        for row in overview["week"]:
            self.action_tree.insert("", "end", values=("Płatność", row.get("due") or "—", row.get("name", ""), f"{row.get('amount', 0):.2f} zł", "W TYM TYGODNIU"))
        for row in overview["review"]:
            self.action_tree.insert("", "end", values=("Sprawdź", row.get("bank_date") or "—", row.get("display_name") or row.get("invoice_no", ""), f"{abs(float(row.get('amount') or 0)):.2f} zł", "DO ZATWIERDZENIA"))

        if hasattr(self, "close_status"):
            check = month_close_check(self.app.items, self.app.results)
            if check["can_close"]:
                self.close_status.set(f"{check['month']}: gotowy do zamknięcia ✓")
            else:
                self.close_status.set(f"{check['month']}: " + " | ".join(check["blockers"]))

        if hasattr(self, "plan_tree"):
            self.plan_tree.delete(*self.plan_tree.get_children())
            for row in plan_12_months():
                self.plan_tree.insert("", "end", values=(
                    row["label"], f"{row['installments']:.2f} zł", f"{row['subscriptions']:.2f} zł",
                    f"{row['debts']:.2f} zł", f"{row['savings']:.2f} zł", f"{row['envelopes']:.2f} zł",
                    f"{row['fixed_total']:.2f} zł",
                ))

        if hasattr(self, "alloc_status"):
            state = load_monthly_automation()
            period = __import__("datetime").date.today().strftime("%Y-%m")
            done = state.get(period, {})
            if done.get("done"):
                self.alloc_status.set(f"{period}: wykonane — {float(done.get('total') or 0):.2f} zł")
            else:
                self.alloc_status.set(f"{period}: jeszcze nie wykonano miesięcznego odkładania")

        if hasattr(self, "worth_tree"):
            self.worth_tree.delete(*self.worth_tree.get_children())
            for row in reversed(net_worth_trend(36)):
                self.worth_tree.insert("", "end", values=(row.get("date", ""), f"{row.get('gross', 0):.2f} zł", f"{row.get('debts', 0):.2f} zł", f"{row.get('net', 0):+.2f} zł"))

        self.app._refresh_today_badge()


class PayCheck320App(PayCheck310App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 3.2.0 — Domowy system finansów offline")
        self._build_today_ui()
        self._extend_today_menu()
        self._apply_feature_visibility()
        self._snapshot_worth_safely()
        self._refresh_today_badge()

    def _build_today_ui(self) -> None:
        self.today_button = self._action_button(self.quick_frame, "Dzisiaj", ORANGE, self._show_today)
        self.today_button.pack(side="left", padx=(7, 0))
        self.today_badge = tk.StringVar(value="")

    def _extend_today_menu(self) -> None:
        menu = self.nametowidget(self.cget("menu"))
        daily = tk.Menu(menu, tearoff=False)
        daily.add_command(label="Dzisiaj / ten miesiąc", command=self._show_today)
        daily.add_command(label="Miesięczne odkładanie", command=self._run_allocations_quick)
        menu.insert_cascade(1, label="Dzisiaj", menu=daily)

    def _feature_for_button(self, text: str) -> str | None:
        if text == "Dzisiaj":
            return "today"
        return super()._feature_for_button(text)

    def _show_today(self) -> None:
        TodayCenter(self)

    def _run_allocations_quick(self) -> None:
        result = run_monthly_allocations()
        if result.get("already_done"):
            messagebox.showinfo("Odkładanie", f"Dla {result['period']} zostało już wykonane.")
        else:
            messagebox.showinfo("Odkładanie", f"Odłożono {result['total']:.2f} zł.")
        self._refresh_household_cards()
        self._refresh_practical_card()

    def _snapshot_worth_safely(self) -> None:
        try:
            wallets = wallet_summary(self.transactions)
            wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
            snapshot_net_worth(wallet_total)
        except Exception:
            pass

    def _refresh_today_badge(self) -> None:
        if not hasattr(self, "today_button"):
            return
        try:
            wallets = wallet_summary(self.transactions)
            wallet_total = sum(float(row.get("balance") or 0) for row in wallets if row.get("active", True))
            data = today_overview(self.items, self.results, wallet_total)
            count = data["action_count"]
            self.today_button.configure(text=f"Dzisiaj ({count})" if count else "Dzisiaj ✓")
        except Exception:
            self.today_button.configure(text="Dzisiaj")

    def _add_statements(self) -> None:
        if self.source_mode != "budget" or not self.items or not self.budget_sheet:
            messagebox.showinfo("Miesiąc", "Najpierw wczytaj budżet i wybierz miesiąc.")
            return
        paths = filedialog.askopenfilenames(
            title=f"Dodaj wyciągi do {self.budget_sheet}",
            filetypes=[
                ("Wyciągi bankowe", "*.xlsx *.csv *.pdf *.sta *.mt940 *.940 *.txt"),
                ("MT940 / STA", "*.sta *.mt940 *.940 *.txt"),
                ("PDF", "*.pdf"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
            ],
        )
        if not paths:
            return
        try:
            incoming, info = load_bank_statements(list(paths))
        except Exception as exc:
            messagebox.showerror("Błąd importu", str(exc))
            return

        self.transactions, added = merge_transactions(self.transactions, incoming)
        for path in paths:
            name = Path(path).name
            if name not in self.statement_files:
                self.statement_files.append(name)
        self.bank_info_var.set(
            f"{self.budget_sheet}: {len(self.statement_files)} plików wyciągów, "
            f"{len(self.transactions)} unikalnych operacji | nowo dodane: {added} | "
            f"duplikaty w nowych plikach: {info.get('duplicates', 0)}"
        )
        if self.transactions:
            self._compare()
        else:
            self._save_current_month()
        self._update_month_header(new_transactions=added)

    def _compare(self) -> None:
        super()._compare()
        self._refresh_today_badge()

    def _restore_state(self, state: dict) -> None:
        super()._restore_state(state)
        self._snapshot_worth_safely()
        self._refresh_today_badge()


if __name__ == "__main__":
    PayCheck320App().mainloop()
