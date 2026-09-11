from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_050 import PayCheck050App
from bank_merge import load_bank_statements
from matcher import MatchSettings, parse_amount
from month_state import (
    bank_confirmation_label,
    list_month_states,
    load_month_state,
    merge_transactions,
    review_rows,
    save_month_state,
)


class CandidateWindow(tk.Toplevel):
    def __init__(self, parent: "ReviewCenter060", row_index: int) -> None:
        super().__init__(parent)
        self.review = parent
        self.app = parent.app
        self.row_index = row_index
        row = self.app.results[row_index]
        self.title("Wybierz przelew z banku")
        self.geometry("1040x560")
        self.minsize(820, 430)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(
            root,
            text=f"Wybierz przelew dla: {row.get('display_name') or row.get('invoice_no', '')}",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            root,
            text="Wybranie przelewu nie zatwierdza go automatycznie. Najpierw zostanie przypisany jako DO ZATWIERDZENIA.",
        ).pack(anchor="w", pady=(0, 10))

        columns = ("date", "amount", "counterparty", "title", "diff")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        heads = {
            "date": "Data",
            "amount": "Kwota",
            "counterparty": "Kontrahent bankowy",
            "title": "Tytuł / opis",
            "diff": "Różnica do planu",
        }
        widths = {"date": 110, "amount": 110, "counterparty": 230, "title": 430, "diff": 120}
        for key in columns:
            self.tree.heading(key, text=heads[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)

        expected = abs(parse_amount(row.get("amount")) or 0.0)
        candidates = []
        for idx, tx in enumerate(self.app.transactions):
            actual = parse_amount(tx.get("amount"))
            if actual is None:
                continue
            if row.get("entry_type") == "income" and actual <= 0:
                continue
            if row.get("entry_type") != "income" and actual >= 0:
                continue
            diff = round(abs(actual) - expected, 2)
            candidates.append((abs(diff), idx, tx, diff))
        candidates.sort(key=lambda item: item[0])

        for _distance, idx, tx, diff in candidates[:80]:
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    tx.get("date", ""),
                    tx.get("amount", ""),
                    tx.get("counterparty", ""),
                    tx.get("title") or tx.get("description", ""),
                    f"{diff:+.2f}",
                ),
            )

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Użyj zaznaczonego przelewu", command=self._use).pack(side="left")
        ttk.Button(buttons, text="Anuluj", command=self.destroy).pack(side="right")

    def _use(self) -> None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Przelew", "Zaznacz przelew.", parent=self)
            return
        tx = self.app.transactions[int(selected[0])]
        row = self.app.results[self.row_index]
        expected = abs(parse_amount(row.get("amount")) or 0.0)
        actual = abs(parse_amount(tx.get("amount")) or 0.0)
        row.update(
            {
                "status": "DO SPRAWDZENIA",
                "match_kind": "WSKAZANA RĘCZNIE",
                "match_score": max(int(row.get("match_score") or 0), 80),
                "bank_date": tx.get("date", ""),
                "bank_amount": tx.get("amount", ""),
                "bank_counterparty": tx.get("counterparty", ""),
                "bank_title": tx.get("title") or tx.get("description", ""),
                "amount_diff": round(actual - expected, 2),
            }
        )
        self.app._refresh_tree()
        self.app._refresh_summary()
        self.app._save_current_month()
        self.review._fill()
        self.destroy()


class ReviewCenter060(tk.Toplevel):
    def __init__(self, app: "PayCheck060App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Do zatwierdzenia")
        self.geometry("1120x650")
        self.minsize(860, 500)

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Do zatwierdzenia", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                "Tutaj są tylko niepewne dopasowania. Zielony status dostanie pozycja dopiero wtedy, "
                "gdy istnieje konkretny przelew z banku i potwierdzisz, że to właściwa płatność."
            ),
            wraplength=1050,
        ).pack(anchor="w", pady=(0, 10))

        columns = ("name", "plan", "bank_date", "bank_amount", "bank_party", "title", "kind")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        heads = {
            "name": "Pozycja",
            "plan": "Plan",
            "bank_date": "Data bank",
            "bank_amount": "Kwota bank",
            "bank_party": "Kontrahent bankowy",
            "title": "Tytuł / opis",
            "kind": "Rodzaj",
        }
        widths = {
            "name": 170,
            "plan": 90,
            "bank_date": 100,
            "bank_amount": 100,
            "bank_party": 190,
            "title": 330,
            "kind": 130,
        }
        for key in columns:
            self.tree.heading(key, text=heads[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="✓ To ta płatność", command=self._approve).pack(side="left")
        ttk.Button(buttons, text="✗ To nie ta", command=self._reject).pack(side="left", padx=8)
        ttk.Button(buttons, text="🔎 Pokaż inne przelewy", command=self._other).pack(side="left")
        ttk.Button(buttons, text="Odśwież", command=self._fill).pack(side="right")
        self._fill()

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for idx, row in enumerate(self.app.results):
            if row.get("status") != "DO SPRAWDZENIA":
                continue
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    row.get("display_name") or row.get("invoice_no", ""),
                    row.get("amount", ""),
                    row.get("bank_date", ""),
                    row.get("bank_amount", ""),
                    row.get("bank_counterparty", ""),
                    row.get("bank_title", ""),
                    row.get("match_kind", "ZWYKŁE"),
                ),
            )

    def _selected_index(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Do zatwierdzenia", "Zaznacz pozycję.", parent=self)
            return None
        return int(selected[0])

    def _activate(self, idx: int) -> None:
        self.app.filter_mode = "Wszystkie"
        self.app._refresh_tree()
        if self.app.tree.exists(str(idx)):
            self.app.tree.selection_set(str(idx))
            self.app.tree.focus(str(idx))

    def _approve(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        row = self.app.results[idx]
        if not row.get("bank_date") and row.get("bank_amount") in (None, ""):
            messagebox.showwarning(
                "Brak potwierdzenia bankowego",
                "Najpierw wskaż konkretny przelew z banku. Pozycji bez przelewu nie można oznaczyć jako potwierdzonej.",
                parent=self,
            )
            return
        self._activate(idx)
        self.app._approve_selected()
        self._fill()

    def _reject(self) -> None:
        idx = self._selected_index()
        if idx is None:
            return
        self._activate(idx)
        self.app._reject_selected()
        self._fill()

    def _other(self) -> None:
        idx = self._selected_index()
        if idx is not None:
            CandidateWindow(self, idx)


class PayCheck060App(PayCheck050App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.6.0")
        self.statement_files: list[str] = []
        self.month_var = tk.StringVar(value=self.budget_sheet or "")
        self.month_info_var = tk.StringVar(value="Wybierz budżet lub otwórz zapisany miesiąc.")
        self._hide_legacy_controls()
        self._build_month_workflow()
        self._build_grouped_menu()
        self._refresh_month_selector()
        self._update_month_header()

    def _hide_legacy_controls(self) -> None:
        root = self.tree.master
        for child in list(root.winfo_children()):
            try:
                if isinstance(child, ttk.LabelFrame) and child.cget("text") == "Tolerancja dopasowania":
                    child.pack_forget()
                    continue
            except tk.TclError:
                pass
            if isinstance(child, ttk.Frame):
                buttons = [w for w in child.winfo_children() if isinstance(w, ttk.Button)]
                if any(str(button.cget("text")).startswith("1.") for button in buttons):
                    child.pack_forget()

    def _build_month_workflow(self) -> None:
        parent = self.tree.master
        self.month_frame = ttk.LabelFrame(parent, text="Miesiąc", padding=10)
        before = getattr(self, "dashboard_frame", self.tree)
        self.month_frame.pack(fill="x", pady=(0, 8), before=before)

        top = ttk.Frame(self.month_frame)
        top.pack(fill="x")
        ttk.Label(top, text="Miesiąc:", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.month_combo = ttk.Combobox(top, textvariable=self.month_var, state="readonly", width=24)
        self.month_combo.pack(side="left", padx=(6, 10))
        ttk.Button(top, text="Otwórz", command=self._open_selected_month).pack(side="left", padx=(0, 12))
        ttk.Button(top, text="Wczytaj budżet / wybierz miesiąc", command=self._choose_budget).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="+ Dodaj / aktualizuj wyciąg", command=self._add_statements).pack(side="left", padx=(0, 8))
        self.review_button = ttk.Button(top, text="Do zatwierdzenia (0)", command=self._review_center_060)
        self.review_button.pack(side="left")

        ttk.Label(self.month_frame, textvariable=self.month_info_var, wraplength=1200).pack(anchor="w", pady=(8, 0))

    def _build_grouped_menu(self) -> None:
        menu = tk.Menu(self)

        month = tk.Menu(menu, tearoff=False)
        month.add_command(label="Wczytaj budżet / wybierz miesiąc", command=self._choose_budget)
        month.add_command(label="Dodaj / aktualizuj wyciąg", command=self._add_statements)
        month.add_command(label="Porównaj ponownie", command=self._compare)
        month.add_separator()
        month.add_command(label="Zapisz wynik do Excel", command=self._save)
        month.add_command(label="Porównaj miesiące", command=self._compare_months)
        menu.add_cascade(label="Miesiąc", menu=month)

        review = tk.Menu(menu, tearoff=False)
        review.add_command(label="Otwórz Do zatwierdzenia", command=self._review_center_060)
        review.add_separator()
        review.add_command(label="Uznaj zaznaczone za właściwą płatność", command=self._approve_selected)
        review.add_command(label="Odrzuć zaznaczone dopasowanie", command=self._reject_selected)
        review.add_command(label="Cofnij ręczną decyzję", command=self._undo_selected)
        menu.add_cascade(label="Do zatwierdzenia", menu=review)

        history = tk.Menu(menu, tearoff=False)
        history.add_command(label="Historia miesięcy / porównań", command=self._show_history)
        history.add_command(label="Historia zaznaczonej pozycji", command=self._show_item_history)
        history.add_separator()
        history.add_command(label="Trend 3 miesiące", command=lambda: self._show_trend(3))
        history.add_command(label="Trend 6 miesięcy", command=lambda: self._show_trend(6))
        history.add_command(label="Trend 12 miesięcy", command=lambda: self._show_trend(12))
        menu.add_cascade(label="Historia", menu=history)

        analysis = tk.Menu(menu, tearoff=False)
        analysis.add_command(label="Dashboard miesiąca", command=self._show_dashboard)
        analysis.add_command(label="Anomalie kosztów", command=self._show_anomalies)
        analysis.add_command(label="Prognoza końca miesiąca", command=self._show_forecast)
        analysis.add_command(label="Terminy / zaległości", command=self._show_deadlines)
        analysis.add_separator()
        analysis.add_command(label="Plan spłaty rat", command=self._show_installments)
        analysis.add_command(label="Wykres kategorii", command=self._chart_categories)
        analysis.add_command(label="Wykres historii budżetu", command=self._chart_history)
        menu.add_cascade(label="Analiza", menu=analysis)

        settings = tk.Menu(menu, tearoff=False)
        settings.add_command(label="Tolerancje dopasowania", command=self._show_match_settings)
        settings.add_command(label="Zapamiętaj kontrahenta / opis", command=self._remember_alias)
        settings.add_command(label="Utwórz regułę z zaznaczonej płatności", command=self._remember_rule)
        settings.add_command(label="Pokaż reguły automatyczne", command=self._show_rules)
        settings.add_separator()
        settings.add_command(label="Eksportuj backup", command=self._export_backup)
        settings.add_command(label="Importuj backup", command=self._import_backup)
        menu.add_cascade(label="Ustawienia", menu=settings)
        self.config(menu=menu)

    def _refresh_month_selector(self) -> None:
        states = list_month_states()
        labels = [row["month_label"] for row in states]
        self.month_combo["values"] = labels
        if self.budget_sheet:
            self.month_var.set(self.budget_sheet)
        elif not self.month_var.get() and labels:
            self.month_var.set(labels[0])

    def _choose_budget(self) -> None:
        super()._load_excel()
        if self.source_mode != "budget" or not self.budget_sheet:
            self._update_month_header()
            return
        self.month_var.set(self.budget_sheet)
        existing = load_month_state(self.budget_sheet)
        if existing and messagebox.askyesno(
            "Zapisany miesiąc",
            f"Dla {self.budget_sheet} istnieje już zapisany stan. Otworzyć go wraz z wcześniej dodanymi wyciągami?",
        ):
            self._restore_state(existing)
        else:
            self.statement_files = []
            self.transactions = []
            self.results = []
            self._save_current_month()
        self._refresh_month_selector()
        self._update_month_header()

    def _add_statements(self) -> None:
        if self.source_mode != "budget" or not self.items or not self.budget_sheet:
            messagebox.showinfo("Miesiąc", "Najpierw wczytaj budżet i wybierz miesiąc.")
            return
        paths = filedialog.askopenfilenames(
            title=f"Dodaj wyciągi do {self.budget_sheet}",
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
        self._save_current_month()
        self._update_month_header()

    def _save_current_month(self) -> None:
        if self.source_mode != "budget" or not self.budget_sheet or not self.items:
            return
        save_month_state(
            self.budget_sheet,
            source_mode=self.source_mode,
            budget_path=self.budget_path,
            budget_sheet=self.budget_sheet,
            items=self.items,
            transactions=self.transactions,
            results=self.results,
            statement_files=self.statement_files,
        )
        self._refresh_month_selector()

    def _open_selected_month(self) -> None:
        label = self.month_var.get().strip()
        if not label:
            messagebox.showinfo("Miesiąc", "Nie ma jeszcze zapisanego miesiąca.")
            return
        state = load_month_state(label)
        if not state:
            messagebox.showerror("Miesiąc", f"Nie udało się odczytać zapisanego miesiąca: {label}")
            return
        self._restore_state(state)

    def _restore_state(self, state: dict) -> None:
        self.source_mode = state.get("source_mode", "budget")
        self.budget_path = state.get("budget_path") or None
        self.budget_sheet = state.get("budget_sheet") or state.get("month_label") or None
        self.items = list(state.get("items", []))
        self.transactions = list(state.get("transactions", []))
        self.results = list(state.get("results", []))
        self.statement_files = list(state.get("statement_files", []))
        self.month_var.set(self.budget_sheet or "")
        self.invoice_info_var.set(
            f"Budżet: {Path(self.budget_path).name if self.budget_path else 'zapisany stan'} / "
            f"{self.budget_sheet or '—'} — {len(self.items)} pozycji"
        )
        self.bank_info_var.set(
            f"Wyciągi w miesiącu: {len(self.statement_files)} plików — {len(self.transactions)} unikalnych operacji"
        )
        self._refresh_tree()
        self._refresh_summary()
        self._update_dashboard_strip()
        self._update_month_header()

    def _update_month_header(self, new_transactions: int | None = None) -> None:
        month = self.budget_sheet or self.month_var.get() or "—"
        paid_bank = sum(
            row.get("status") == "OPŁACONA"
            and (row.get("bank_date") not in (None, "") or row.get("bank_amount") not in (None, ""))
            for row in self.results
        )
        review = len(review_rows(self.results))
        missing = sum(row.get("status") == "BRAK" for row in self.results)
        extra = "" if new_transactions is None else f" | Nowe operacje po aktualizacji: {new_transactions}"
        self.month_info_var.set(
            f"{month} | Wyciągi: {len(self.statement_files)} | Operacje bankowe: {len(self.transactions)} | "
            f"Potwierdzone w banku: {paid_bank} | Do zatwierdzenia: {review} | Brak potwierdzenia: {missing}{extra}"
        )
        self.review_button.configure(text=f"Do zatwierdzenia ({review})")

    def _refresh_tree(self) -> None:
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        from advanced_features import filter_results

        visible = filter_results(self.results, getattr(self, "filter_mode", "Wszystkie"))
        for row in visible:
            original_index = self.results.index(row)
            label = bank_confirmation_label(row)
            raw = row.get("status", "")
            tag = {"OPŁACONA": "paid", "DO SPRAWDZENIA": "review", "BRAK": "missing"}.get(raw, "")
            self.tree.insert(
                "",
                "end",
                iid=str(original_index),
                values=(
                    row.get("display_name") or row.get("invoice_no", ""),
                    row.get("institution") or row.get("counterparty", ""),
                    row.get("date", ""),
                    row.get("amount", ""),
                    label,
                    row.get("match_score", ""),
                    row.get("bank_date", ""),
                    row.get("bank_amount", ""),
                    row.get("amount_diff", ""),
                ),
                tags=(tag,) if tag else (),
            )

    def _approve_selected(self) -> None:
        super()._approve_selected()
        self._save_current_month()
        self._update_month_header()
        self._update_dashboard_strip()

    def _reject_selected(self) -> None:
        super()._reject_selected()
        self._save_current_month()
        self._update_month_header()
        self._update_dashboard_strip()

    def _undo_selected(self) -> None:
        super()._undo_selected()
        self._save_current_month()
        self._update_month_header()

    def _review_center_060(self) -> None:
        if not self.results:
            messagebox.showinfo("Do zatwierdzenia", "Dodaj wyciąg i wykonaj porównanie.")
            return
        if not review_rows(self.results):
            messagebox.showinfo("Do zatwierdzenia", "Nie ma teraz żadnych niepewnych dopasowań.")
            return
        ReviewCenter060(self)

    def _show_match_settings(self) -> None:
        win = tk.Toplevel(self)
        win.title("Tolerancje dopasowania")
        win.resizable(False, False)
        frame = ttk.Frame(win, padding=14)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Data ± dni:").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=0, to=60, width=10, textvariable=self.days_var).grid(row=0, column=1, padx=8)
        ttk.Label(frame, text="Kwota ± %:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=0, to=100, increment=0.5, width=10, textvariable=self.percent_var).grid(row=1, column=1, padx=8)
        ttk.Label(frame, text="Kwota min. ± zł:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Spinbox(frame, from_=0, to=100000, increment=1, width=10, textvariable=self.amount_var).grid(row=2, column=1, padx=8)
        ttk.Button(frame, text="Zamknij", command=win.destroy).grid(row=3, column=0, columnspan=2, pady=(12, 0))


if __name__ == "__main__":
    PayCheck060App().mainloop()
