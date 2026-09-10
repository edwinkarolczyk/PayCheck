from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from bank_merge import load_bank_statements
from budget_loader import list_budget_sheets, load_budget_sheet
from budget_matcher import match_budget
from io_files import load_invoices, save_results
from matcher import MatchSettings, match_invoices
from month_compare import compare_months


class SheetDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, sheets: list[str], title: str = "Wybierz arkusz") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result: str | None = None
        self.transient(parent)
        self.grab_set()

        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Wybierz miesiąc / arkusz z budżetu:").pack(anchor="w", pady=(0, 8))
        self.combo = ttk.Combobox(frame, values=sheets, state="readonly", width=34)
        self.combo.pack(fill="x")
        if sheets:
            self.combo.current(len(sheets) - 1)

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Anuluj", command=self.destroy).pack(side="right")
        ttk.Button(buttons, text="Wybierz", command=self._accept).pack(side="right", padx=(0, 8))
        self.bind("<Return>", lambda _event: self._accept())
        self.wait_window(self)

    def _accept(self) -> None:
        value = self.combo.get().strip()
        if value:
            self.result = value
        self.destroy()


class MonthCompareWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, left_name: str, right_name: str, rows: list[dict]) -> None:
        super().__init__(parent)
        self.title(f"Porównanie miesięcy: {left_name} → {right_name}")
        self.geometry("980x620")
        self.minsize(820, 480)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(
            root,
            text=f"{left_name}  →  {right_name}",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 8))

        total_left = sum((r.get("previous_amount") or 0) for r in rows)
        total_right = sum((r.get("current_amount") or 0) for r in rows)
        total_diff = total_right - total_left
        ttk.Label(
            root,
            text=(
                f"Suma poprzednio: {total_left:.2f} zł | Suma bieżąco: {total_right:.2f} zł | "
                f"Zmiana: {total_diff:+.2f} zł"
            ),
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        columns = ("name", "institution", "prev", "curr", "diff", "percent", "status")
        tree = ttk.Treeview(root, columns=columns, show="headings")
        headings = {
            "name": "Pozycja",
            "institution": "Instytucja",
            "prev": left_name,
            "curr": right_name,
            "diff": "Różnica",
            "percent": "Zmiana %",
            "status": "Status",
        }
        widths = {"name": 190, "institution": 180, "prev": 105, "curr": 105, "diff": 100, "percent": 90, "status": 125}
        for key in columns:
            tree.heading(key, text=headings[key])
            tree.column(key, width=widths[key], anchor="w")

        tree.tag_configure("up", background="#F8D7DA", foreground="#842029")
        tree.tag_configure("down", background="#D9F2D9", foreground="#145A14")
        tree.tag_configure("new", background="#FFF0BF", foreground="#7A4B00")
        tree.tag_configure("same", background="#F2F2F2", foreground="#333333")

        for row in rows:
            status = row.get("status", "")
            tag = {
                "WZROST": "up",
                "SPADEK": "down",
                "NOWA": "new",
                "BRAK W BIEŻĄCYM": "down",
                "BEZ ZMIAN": "same",
            }.get(status, "same")
            percent = row.get("percent_change")
            tree.insert(
                "",
                "end",
                values=(
                    row.get("name", ""),
                    row.get("institution", ""),
                    "" if row.get("previous_amount") is None else f"{row['previous_amount']:.2f}",
                    "" if row.get("current_amount") is None else f"{row['current_amount']:.2f}",
                    "" if row.get("difference") is None else f"{row['difference']:+.2f}",
                    "" if percent is None else f"{percent:+.1f}%",
                    status,
                ),
                tags=(tag,),
            )

        scroll = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")


class PayCheckApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.2.0")
        self.geometry("1320x760")
        self.minsize(1050, 660)

        self.items: list[dict] = []
        self.transactions: list[dict] = []
        self.results: list[dict] = []
        self.source_mode = "standard"
        self.budget_path: str | None = None
        self.budget_sheet: str | None = None

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

        ttk.Label(root, text="PayCheck", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Porównanie faktur lub miesięcznego budżetu z wieloma wyciągami bankowymi",
        ).pack(anchor="w", pady=(0, 12))

        controls = ttk.Frame(root)
        controls.pack(fill="x", pady=(0, 10))
        ttk.Button(controls, text="1. Wczytaj Excel", command=self._load_excel).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="2. Wczytaj wyciągi", command=self._load_bank).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="3. Porównaj płatności", command=self._compare).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="4. Zapisz wynik", command=self._save).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="5. Porównaj miesiące", command=self._compare_months).pack(side="left")

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
        ttk.Spinbox(settings, from_=0, to=100000, increment=1, width=10, textvariable=self.amount_var).grid(row=0, column=5)
        ttk.Label(
            settings,
            text=(
                "Budżet bez terminu płatności: transakcje są porównywane z miesiącem wybranego arkusza. "
                "Możesz wczytać kilka wyciągów jednocześnie; duplikaty są pomijane."
            ),
            wraplength=1180,
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(8, 0))

        ttk.Label(root, textvariable=self.summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        columns = ("name", "institution", "date", "amount", "status", "score", "bank_date", "bank_amount", "diff")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        headings = {
            "name": "Pozycja / faktura",
            "institution": "Instytucja / kontrahent",
            "date": "Termin",
            "amount": "Kwota Excel",
            "status": "Status",
            "score": "Zgodność %",
            "bank_date": "Data bank",
            "bank_amount": "Kwota bank",
            "diff": "Różnica",
        }
        widths = {"name": 180, "institution": 230, "date": 95, "amount": 100, "status": 125, "score": 85, "bank_date": 95, "bank_amount": 100, "diff": 90}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")

        self.tree.tag_configure("paid", background="#D9F2D9", foreground="#145A14")
        self.tree.tag_configure("review", background="#FFF0BF", foreground="#7A4B00")
        self.tree.tag_configure("missing", background="#F8D7DA", foreground="#842029")

        scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _load_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz Excel z fakturami lub budżetem",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return

        self.budget_path = None
        self.budget_sheet = None
        try:
            self.items = load_invoices(path)
            self.source_mode = "standard"
            source_desc = f"Excel: {Path(path).name} — {len(self.items)} pozycji"
        except Exception:
            try:
                sheets = list_budget_sheets(path)
                dialog = SheetDialog(self, sheets)
                if not dialog.result:
                    return
                self.items = load_budget_sheet(path, dialog.result)
                self.source_mode = "budget"
                self.budget_path = path
                self.budget_sheet = dialog.result
                source_desc = (
                    f"Budżet: {Path(path).name} / {dialog.result} — "
                    f"{len(self.items)} pozycji miesięcznych"
                )
            except Exception as exc:
                messagebox.showerror("Błąd importu", str(exc))
                return

        self.invoice_info_var.set(source_desc)
        self.results = []
        self._refresh_tree()

    def _load_bank(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Wybierz jeden lub kilka wyciągów bankowych",
            filetypes=[
                ("Wyciągi bankowe", "*.xlsx *.csv *.pdf"),
                ("PDF", "*.pdf"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
            ],
        )
        if not paths:
            return
        try:
            self.transactions, info = load_bank_statements(list(paths))
        except Exception as exc:
            messagebox.showerror("Błąd importu", str(exc))
            return
        self.bank_info_var.set(
            f"Wyciągi: {info['files']} plików — {info['transactions']} operacji | "
            f"pominięte duplikaty: {info['duplicates']}"
        )
        self.results = []
        self._refresh_tree()

    def _compare(self) -> None:
        if not self.items:
            messagebox.showwarning("Brak danych", "Najpierw wczytaj Excel.")
            return
        if not self.transactions:
            messagebox.showwarning("Brak danych", "Najpierw wczytaj co najmniej jeden wyciąg bankowy.")
            return

        settings = MatchSettings(
            days_tolerance=max(0, self.days_var.get()),
            amount_percent_tolerance=max(0.0, self.percent_var.get()),
            amount_absolute_tolerance=max(0.0, self.amount_var.get()),
        )
        if self.source_mode == "budget":
            self.results = match_budget(self.items, self.transactions, settings)
        else:
            self.results = match_invoices(self.items, self.transactions, settings)

        self._refresh_tree()
        paid = sum(r.get("status") == "OPŁACONA" for r in self.results)
        review = sum(r.get("status") == "DO SPRAWDZENIA" for r in self.results)
        missing = sum(r.get("status") == "BRAK" for r in self.results)
        self.summary_var.set(
            f"Razem: {len(self.results)} | Opłacone: {paid} | Do sprawdzenia: {review} | Brak: {missing}"
        )

    def _compare_months(self) -> None:
        if self.source_mode != "budget" or not self.budget_path or not self.budget_sheet:
            messagebox.showinfo(
                "Porównanie miesięcy",
                "Najpierw wczytaj plik budżetu i wybierz bieżący arkusz.",
            )
            return

        try:
            sheets = list_budget_sheets(self.budget_path)
            dialog = SheetDialog(self, sheets, title="Wybierz miesiąc do porównania")
            if not dialog.result:
                return
            other_items = load_budget_sheet(self.budget_path, dialog.result)
            rows = compare_months(other_items, self.items)
        except Exception as exc:
            messagebox.showerror("Błąd porównania miesięcy", str(exc))
            return

        MonthCompareWindow(self, dialog.result, self.budget_sheet, rows)

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for row in self.results:
            name = row.get("display_name") or row.get("invoice_no", "")
            institution = row.get("institution") or row.get("counterparty", "")
            status = row.get("status", "")
            tag = {"OPŁACONA": "paid", "DO SPRAWDZENIA": "review", "BRAK": "missing"}.get(status, "")
            self.tree.insert(
                "",
                "end",
                values=(
                    name,
                    institution,
                    row.get("date", ""),
                    row.get("amount", ""),
                    status,
                    row.get("match_score", ""),
                    row.get("bank_date", ""),
                    row.get("bank_amount", ""),
                    row.get("amount_diff", ""),
                ),
                tags=(tag,) if tag else (),
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
