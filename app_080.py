from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_060 import PayCheck060App
from budget_manager import (
    bank_overview,
    budget_overview,
    installment_overview,
    installment_summary,
    transaction_overview,
)
from payment_policy import (
    enforce_payment_precision,
    load_transfer_tolerance,
    save_transfer_tolerance,
)


class BudgetManagerWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck080App") -> None:
        super().__init__(app)
        self.app = app
        self.title(f"Zarządzanie budżetem — {app.budget_sheet or 'miesiąc'}")
        self.geometry("1120x720")
        self.minsize(900, 560)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(
            root,
            text=f"Budżet domowy — {app.budget_sheet or 'wybrany miesiąc'}",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            root,
            text="Plan, wykonanie, banki, raty i wszystkie operacje z wyciągów w jednym miejscu.",
        ).pack(anchor="w", pady=(0, 10))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self._build_overview(notebook)
        self._build_categories(notebook)
        self._build_banks(notebook)
        self._build_installments(notebook)
        self._build_transactions(notebook)

    def _table(self, parent, columns, rows, height=16):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        keys = tuple(key for key, _label, _width in columns)
        tree = ttk.Treeview(frame, columns=keys, show="headings", height=height)
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for row in rows:
            tree.insert("", "end", values=row)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _build_overview(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Podsumowanie")
        data = budget_overview(self.app.items, self.app.results)

        cards = ttk.Frame(tab, padding=12)
        cards.pack(fill="x")
        values = (
            ("Wpływy", data["income"]),
            ("Plan wydatków", data["expenses"]),
            ("Opłacone", data["paid"]),
            ("Do sprawdzenia", data["review"]),
            ("Brak potwierdzenia", data["missing"]),
            ("Zostało", data["remaining"]),
        )
        for label, value in values:
            box = ttk.LabelFrame(cards, text=label, padding=10)
            box.pack(side="left", padx=(0, 8), fill="x", expand=True)
            ttk.Label(box, text=f"{value:.2f} zł", font=("Segoe UI", 12, "bold")).pack()

        ttk.Label(
            tab,
            text=f"Planowany bilans miesiąca: {data['balance_plan']:+.2f} zł",
            font=("Segoe UI", 13, "bold"),
            padding=12,
        ).pack(anchor="w")

        inst_rows = installment_overview(self.app.items, self.app.results)
        inst = installment_summary(inst_rows)
        ttk.Label(
            tab,
            text=(
                f"Aktywne raty: {inst['active']} | miesięcznie: {inst['monthly']:.2f} zł | "
                f"szac. pozostało: {inst['estimated_left']:.2f} zł | "
                f"kończą się w 3 mies.: {inst['ending_within_3_months']}"
            ),
            padding=(12, 4),
        ).pack(anchor="w")

    def _build_categories(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Kategorie")
        data = budget_overview(self.app.items, self.app.results)
        rows = [(name, f"{amount:.2f} zł") for name, amount in data["categories"].items()]
        self._table(tab, [("category", "Kategoria", 360), ("amount", "Plan miesięczny", 160)], rows)

    def _build_banks(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Banki / raty")
        rows = [
            (
                row["bank"],
                row["active"],
                f"{row['monthly']:.2f} zł",
                row["paid"],
                row["missing"],
            )
            for row in bank_overview(self.app.items, self.app.results)
        ]
        self._table(
            tab,
            [
                ("bank", "Bank", 180),
                ("active", "Aktywne zobowiązania", 160),
                ("monthly", "Miesięcznie", 130),
                ("paid", "Opłacone w miesiącu", 150),
                ("missing", "Brak potwierdzenia", 150),
            ],
            rows,
        )

    def _build_installments(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Raty")
        rows = []
        for row in installment_overview(self.app.items, self.app.results):
            months = "—" if row["months_left"] is None else row["months_left"]
            left = "—" if row["estimated_left"] is None else f"{row['estimated_left']:.2f} zł"
            note = "ZAKOŃCZONA" if row["finished"] else ("KOŃCZY SIĘ WKRÓTCE" if row["ends_soon"] else "")
            rows.append(
                (
                    row["name"], row["bank"], f"{row['monthly']:.2f} zł", row["end_date"] or "—",
                    months, left, row["status"], note,
                )
            )
        self._table(
            tab,
            [
                ("name", "Rata", 190),
                ("bank", "Bank", 130),
                ("monthly", "Miesięcznie", 110),
                ("end", "Koniec", 110),
                ("months", "Pozostało rat", 105),
                ("left", "Szac. pozostało", 130),
                ("status", "Ten miesiąc", 140),
                ("note", "Uwagi", 150),
            ],
            rows,
        )

    def _build_transactions(self, notebook) -> None:
        tab = ttk.Frame(notebook)
        notebook.add(tab, text="Transakcje")
        rows = [
            (
                row["date"],
                f"{row['amount']:.2f}",
                row["type"],
                f"±{row['tolerance']:.2f} zł",
                row["counterparty"],
                row["title"],
                row["source_file"],
            )
            for row in transaction_overview(self.app.transactions, self.app.transfer_tolerance)
        ]
        self._table(
            tab,
            [
                ("date", "Data", 95),
                ("amount", "Kwota", 100),
                ("type", "Typ", 125),
                ("tol", "Tolerancja", 100),
                ("party", "Kontrahent", 190),
                ("title", "Opis", 300),
                ("file", "Wyciąg", 150),
            ],
            rows,
        )


class PaymentPolicyWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck080App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Zasady dopasowania płatności")
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Tolerancje według typu płatności", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        fixed = (
            ("BLIK", "±0,01 zł — praktycznie co do grosza"),
            ("Karta", "±0,01 zł"),
            ("Polecenie zapłaty", "±1,00 zł"),
            ("Rata / kredyt", "±1,00 zł"),
        )
        row_no = 1
        for label, value in fixed:
            ttk.Label(frame, text=label + ":").grid(row=row_no, column=0, sticky="w", pady=4)
            ttk.Label(frame, text=value).grid(row=row_no, column=1, sticky="w", padx=(12, 0))
            row_no += 1

        ttk.Label(frame, text="Przelew bankowy:").grid(row=row_no, column=0, sticky="w", pady=(10, 4))
        self.value = tk.DoubleVar(value=app.transfer_tolerance)
        ttk.Spinbox(frame, from_=0, to=5, increment=0.5, width=8, textvariable=self.value).grid(row=row_no, column=1, sticky="w", padx=(12, 0), pady=(10, 4))
        row_no += 1
        ttk.Label(frame, text="Zakres 0–5 zł. Domyślnie 2 zł.", foreground="#555555").grid(row=row_no, column=0, columnspan=2, sticky="w")
        row_no += 1
        ttk.Button(frame, text="Zapisz", command=self._save).grid(row=row_no, column=0, columnspan=2, pady=(14, 0))

    def _save(self) -> None:
        try:
            value = float(self.value.get())
        except (TypeError, ValueError):
            messagebox.showerror("Zasady płatności", "Podaj poprawną tolerancję.", parent=self)
            return
        self.app.transfer_tolerance = save_transfer_tolerance(value)
        if self.app.results:
            self.app._compare()
        self.destroy()


class PayCheck080App(PayCheck060App):
    def __init__(self) -> None:
        self.transfer_tolerance = load_transfer_tolerance()
        super().__init__()
        self.title("PayCheck 0.8.0")
        self._extend_budget_ui()

    def _extend_budget_ui(self) -> None:
        top = self.month_frame.winfo_children()[0]
        ttk.Button(top, text="Zarządzanie budżetem", command=self._show_budget_manager).pack(side="left", padx=(8, 0))

        menu = self.nametowidget(self.cget("menu"))
        budget = tk.Menu(menu, tearoff=False)
        budget.add_command(label="Otwórz menedżer budżetu", command=self._show_budget_manager)
        budget.add_command(label="Podsumowanie miesiąca", command=self._show_dashboard)
        budget.add_separator()
        budget.add_command(label="Raty i terminy końca", command=self._show_budget_manager)
        budget.add_command(label="Zasady BLIK / przelew / karta", command=self._show_payment_policy)
        menu.insert_cascade(1, label="Budżet", menu=budget)

    def _compare(self) -> None:
        super()._compare()
        if not self.results:
            return
        changed = enforce_payment_precision(self.results, self.transfer_tolerance)
        if changed:
            self._refresh_tree()
            self._refresh_summary()
            self._save_current_month()
            self._update_month_header()
            self.summary_var.set(
                self.summary_var.get()
                + f" | Do zatwierdzenia przez dokładność kwoty: {changed}"
            )

    def _show_budget_manager(self) -> None:
        if self.source_mode != "budget" or not self.items:
            messagebox.showinfo("Budżet", "Najpierw wczytaj budżet i wybierz miesiąc.")
            return
        BudgetManagerWindow(self)

    def _show_payment_policy(self) -> None:
        PaymentPolicyWindow(self)


if __name__ == "__main__":
    PayCheck080App().mainloop()
