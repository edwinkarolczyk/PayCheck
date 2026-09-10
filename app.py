from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from io_files import load_bank_statement, load_invoices, save_results
from matcher import MatchSettings, match_invoices


class PayCheckApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.1.0")
        self.geometry("1180x720")
        self.minsize(980, 620)

        self.invoices: list[dict] = []
        self.transactions: list[dict] = []
        self.results: list[dict] = []

        self.days_var = tk.IntVar(value=5)
        self.percent_var = tk.DoubleVar(value=3.0)
        self.amount_var = tk.DoubleVar(value=20.0)
        self.invoice_info_var = tk.StringVar(value="Nie wczytano Excela")
        self.bank_info_var = tk.StringVar(value="Nie wczytano wyciągu")
        self.summary_var = tk.StringVar(value="Wczytaj dane, aby rozpocząć.")

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        title = ttk.Label(root, text="PayCheck", font=("Segoe UI", 22, "bold"))
        title.pack(anchor="w")
        ttk.Label(root, text="Porównanie zobowiązań z Excela z wyciągiem bankowym").pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(0, 10))

        ttk.Button(controls, text="1. Wczytaj Excel", command=self._load_invoices).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="2. Wczytaj wyciąg", command=self._load_bank).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="3. Porównaj", command=self._compare).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="4. Zapisz wynik", command=self._save).pack(side="left")

        info = ttk.Frame(root)
        info.pack(fill="x", pady=(0, 10))
        ttk.Label(info, textvariable=self.invoice_info_var).pack(anchor="w")
        ttk.Label(info, textvariable=self.bank_info_var).pack(anchor="w")

        settings = ttk.LabelFrame(root, text="Tolerancja dopasowania", padding=10)
        settings.pack(fill="x", pady=(0, 10))

        ttk.Label(settings, text="Data ± dni:").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(settings, from_=0, to=60, width=8, textvariable=self.days_var).grid(row=0, column=1, padx=(5, 18))
        ttk.Label(settings, text="Kwota ± %:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(settings, from_=0, to=100, increment=0.5, width=8, textvariable=self.percent_var).grid(row=0, column=3, padx=(5, 18))
        ttk.Label(settings, text="Kwota min. ± zł:").grid(row=0, column=4, sticky="w")
        ttk.Spinbox(settings, from_=0, to=100000, increment=1, width=10, textvariable=self.amount_var).grid(row=0, column=5, padx=(5, 0))

        ttk.Label(root, textvariable=self.summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        columns = (
            "invoice_no", "counterparty", "date", "amount", "status",
            "score", "bank_date", "bank_amount", "diff",
        )
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        headings = {
            "invoice_no": "Nr faktury",
            "counterparty": "Kontrahent",
            "date": "Termin",
            "amount": "Kwota Excel",
            "status": "Status",
            "score": "Zgodność %",
            "bank_date": "Data bank",
            "bank_amount": "Kwota bank",
            "diff": "Różnica",
        }
        widths = {
            "invoice_no": 110,
            "counterparty": 220,
            "date": 95,
            "amount": 100,
            "status": 120,
            "score": 85,
            "bank_date": 95,
            "bank_amount": 100,
            "diff": 90,
        }
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _load_invoices(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz Excel z zobowiązaniami",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            self.invoices = load_invoices(path)
        except Exception as exc:
            messagebox.showerror("Błąd importu", str(exc))
            return
        self.invoice_info_var.set(f"Excel: {Path(path).name} — {len(self.invoices)} pozycji")
        self.results = []
        self._refresh_tree()

    def _load_bank(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz wyciąg bankowy",
            filetypes=[("Wyciąg bankowy", "*.xlsx *.csv"), ("Excel", "*.xlsx"), ("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            self.transactions = load_bank_statement(path)
        except Exception as exc:
            messagebox.showerror("Błąd importu", str(exc))
            return
        self.bank_info_var.set(f"Wyciąg: {Path(path).name} — {len(self.transactions)} operacji")
        self.results = []
        self._refresh_tree()

    def _compare(self) -> None:
        if not self.invoices:
            messagebox.showwarning("Brak danych", "Najpierw wczytaj Excel z zobowiązaniami.")
            return
        if not self.transactions:
            messagebox.showwarning("Brak danych", "Najpierw wczytaj wyciąg bankowy.")
            return

        settings = MatchSettings(
            days_tolerance=max(0, self.days_var.get()),
            amount_percent_tolerance=max(0.0, self.percent_var.get()),
            amount_absolute_tolerance=max(0.0, self.amount_var.get()),
        )
        self.results = match_invoices(self.invoices, self.transactions, settings)
        self._refresh_tree()

        paid = sum(r.get("status") == "OPŁACONA" for r in self.results)
        review = sum(r.get("status") == "DO SPRAWDZENIA" for r in self.results)
        missing = sum(r.get("status") == "BRAK" for r in self.results)
        self.summary_var.set(
            f"Razem: {len(self.results)} | Opłacone: {paid} | Do sprawdzenia: {review} | Brak: {missing}"
        )

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in self.results:
            self.tree.insert(
                "",
                "end",
                values=(
                    row.get("invoice_no", ""),
                    row.get("counterparty", ""),
                    row.get("date", ""),
                    row.get("amount", ""),
                    row.get("status", ""),
                    row.get("match_score", ""),
                    row.get("bank_date", ""),
                    row.get("bank_amount", ""),
                    row.get("amount_diff", ""),
                ),
            )

    def _save(self) -> None:
        if not self.results:
            messagebox.showwarning("Brak wyniku", "Najpierw wykonaj porównanie.")
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz wynik",
            defaultextension=".xlsx",
            initialfile="PayCheck_wynik.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            save_results(path, self.results)
        except Exception as exc:
            messagebox.showerror("Błąd zapisu", str(exc))
            return
        messagebox.showinfo("Zapisano", f"Wynik zapisano do:\n{path}")


if __name__ == "__main__":
    PayCheckApp().mainloop()
