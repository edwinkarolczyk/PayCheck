from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_budget import PayCheckApp
from budget_summary import summarize_budget
from decision_store import apply_decisions, remove_decision, save_decision
from history_store import (
    append_snapshot,
    compare_snapshots,
    load_history,
    make_snapshot,
    previous_snapshot,
)


class HistoryWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.title("Historia porównań — PayCheck")
        self.geometry("980x620")
        self.minsize(820, 480)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Historia porównań", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Zapisywana lokalnie na tym komputerze. Podwójne identyczne porównania nie są dopisywane.",
        ).pack(anchor="w", pady=(0, 10))

        columns = ("date", "source", "total", "paid", "review", "missing")
        self.tree = ttk.Treeview(root, columns=columns, show="headings", height=14)
        headings = {
            "date": "Data sprawdzenia",
            "source": "Miesiąc / źródło",
            "total": "Razem",
            "paid": "Opłacone",
            "review": "Do sprawdzenia",
            "missing": "Brak",
        }
        widths = {"date": 165, "source": 250, "total": 75, "paid": 85, "review": 110, "missing": 75}
        for key in columns:
            self.tree.heading(key, text=headings[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)

        self.details_var = tk.StringVar(value="Wybierz wpis historii, aby zobaczyć zmiany.")
        ttk.Label(root, textvariable=self.details_var, wraplength=930).pack(anchor="w", pady=(10, 0))

        self.history = load_history()
        for index, item in enumerate(reversed(self.history)):
            summary = item.get("summary", {})
            source = item.get("source_sheet") or item.get("source_label") or "—"
            self.tree.insert(
                "",
                "end",
                iid=str(len(self.history) - 1 - index),
                values=(
                    str(item.get("created_at", "")).replace("T", " "),
                    source,
                    summary.get("total", 0),
                    summary.get("paid", 0),
                    summary.get("review", 0),
                    summary.get("missing", 0),
                ),
            )
        self.tree.bind("<<TreeviewSelect>>", self._show_details)

    def _show_details(self, _event=None) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        index = int(selected[0])
        current = self.history[index]
        previous = None
        for candidate in reversed(self.history[:index]):
            if candidate.get("context") == current.get("context"):
                previous = candidate
                break
        changes = compare_snapshots(previous, current)
        newly = ", ".join(changes["newly_paid"]) or "brak"
        missing = ", ".join(changes["became_missing"]) or "brak"
        self.details_var.set(
            f"Zmiany od poprzedniego sprawdzenia: {changes['changed']} | "
            f"Nowo opłacone: {newly} | Nowo brakujące: {missing}"
        )


class BudgetSummaryWindow(tk.Toplevel):
    def __init__(self, parent: tk.Misc, sheet_name: str, items: list[dict]) -> None:
        super().__init__(parent)
        self.title(f"Podsumowanie budżetu — {sheet_name}")
        self.geometry("860x650")
        self.minsize(720, 520)

        summary = summarize_budget(items)
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        ttk.Label(root, text=f"Podsumowanie — {sheet_name}", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                f"Wpływy: {summary['income_total']:.2f} zł   |   "
                f"Wydatki: {summary['expense_total']:.2f} zł   |   "
                f"Bilans: {summary['balance']:+.2f} zł"
            ),
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(6, 12))

        ttk.Label(root, text="Kategorie", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        cat_tree = ttk.Treeview(root, columns=("category", "amount"), show="headings", height=10)
        cat_tree.heading("category", text="Kategoria")
        cat_tree.heading("amount", text="Suma miesięczna")
        cat_tree.column("category", width=360, anchor="w")
        cat_tree.column("amount", width=160, anchor="e")
        for name, amount in summary["categories"].items():
            cat_tree.insert("", "end", values=(name, f"{amount:.2f} zł"))
        cat_tree.pack(fill="x", pady=(4, 14))

        ttk.Label(root, text="Raty według banku", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        bank_tree = ttk.Treeview(root, columns=("bank", "amount"), show="headings", height=7)
        bank_tree.heading("bank", text="Bank")
        bank_tree.heading("amount", text="Suma rat")
        bank_tree.column("bank", width=360, anchor="w")
        bank_tree.column("amount", width=160, anchor="e")
        if summary["banks"]:
            for bank, amount in summary["banks"].items():
                bank_tree.insert("", "end", values=(bank, f"{amount:.2f} zł"))
        else:
            bank_tree.insert("", "end", values=("Brak rozpoznanych rat bankowych", "0.00 zł"))
        bank_tree.pack(fill="x", pady=(4, 8))

        ttk.Label(
            root,
            text=f"Łączna suma rat bankowych: {summary['installments_total']:.2f} zł",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(2, 0))


class PayCheckHistoryApp(PayCheckApp):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.2.2")

        menu = tk.Menu(self)
        budget_menu = tk.Menu(menu, tearoff=False)
        budget_menu.add_command(label="Podsumowanie budżetu", command=self._show_budget_summary)
        menu.add_cascade(label="Budżet", menu=budget_menu)

        decision_menu = tk.Menu(menu, tearoff=False)
        decision_menu.add_command(label="✓ Uznaj zaznaczone za opłacone", command=self._approve_selected)
        decision_menu.add_command(label="✗ Odrzuć zaznaczone dopasowanie", command=self._reject_selected)
        decision_menu.add_separator()
        decision_menu.add_command(label="Cofnij ręczną decyzję", command=self._undo_selected)
        menu.add_cascade(label="Decyzja", menu=decision_menu)

        history_menu = tk.Menu(menu, tearoff=False)
        history_menu.add_command(label="Pokaż historię porównań", command=self._show_history)
        menu.add_cascade(label="Historia", menu=history_menu)
        self.config(menu=menu)

        self.row_menu = tk.Menu(self, tearoff=False)
        self.row_menu.add_command(label="✓ Uznaj za opłacone", command=self._approve_selected)
        self.row_menu.add_command(label="✗ Odrzuć dopasowanie", command=self._reject_selected)
        self.row_menu.add_separator()
        self.row_menu.add_command(label="Cofnij ręczną decyzję", command=self._undo_selected)
        self.tree.bind("<Button-3>", self._show_row_menu)

    def _compare(self) -> None:
        super()._compare()
        if not self.results:
            return

        remembered = apply_decisions(self.results)
        if remembered:
            self._refresh_tree()
            self._refresh_summary(remembered)

        source_label = self.budget_sheet or self.invoice_info_var.get()
        snapshot = make_snapshot(
            self.results,
            source_mode=self.source_mode,
            source_label=source_label,
            source_sheet=self.budget_sheet,
        )
        history = load_history()
        previous = previous_snapshot(history, snapshot)
        changes = compare_snapshots(previous, snapshot)
        append_snapshot(snapshot)

        if previous and changes["newly_paid"]:
            names = ", ".join(changes["newly_paid"][:8])
            if len(changes["newly_paid"]) > 8:
                names += f" i {len(changes['newly_paid']) - 8} więcej"
            self.summary_var.set(
                self.summary_var.get()
                + f" | Od ostatniego sprawdzenia opłacono: {len(changes['newly_paid'])} ({names})"
            )

    def _refresh_summary(self, remembered: int = 0) -> None:
        paid = sum(r.get("status") == "OPŁACONA" for r in self.results)
        review = sum(r.get("status") == "DO SPRAWDZENIA" for r in self.results)
        missing = sum(r.get("status") == "BRAK" for r in self.results)
        text = f"Razem: {len(self.results)} | Opłacone: {paid} | Do sprawdzenia: {review} | Brak: {missing}"
        if remembered:
            text += f" | Pamięć decyzji: {remembered}"
        self.summary_var.set(text)

    def _selected_row(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Decyzja", "Zaznacz najpierw pozycję w tabeli.")
            return None
        index = self.tree.index(selected[0])
        if index < 0 or index >= len(self.results):
            return None
        return self.results[index]

    def _show_row_menu(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree.focus(iid)
            self.row_menu.tk_popup(event.x_root, event.y_root)

    def _approve_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if not row.get("bank_date") and not row.get("bank_amount"):
            messagebox.showinfo("Decyzja", "Ta pozycja nie ma dopasowanego przelewu do zatwierdzenia.")
            return
        if row.get("status") not in {"DO SPRAWDZENIA", "OPŁACONA"}:
            messagebox.showinfo("Decyzja", "Ręczne zatwierdzanie dotyczy dopasowanych płatności.")
            return

        save_decision(row, "approved")
        row["manual_decision"] = "approved"
        row["status"] = "OPŁACONA"
        self._refresh_tree()
        self._refresh_summary(1)
        messagebox.showinfo(
            "Zapamiętano",
            "To dopasowanie zostało uznane za opłacone i będzie pamiętane przy następnym porównaniu.",
        )

    def _reject_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if not row.get("bank_date") and not row.get("bank_amount"):
            messagebox.showinfo("Decyzja", "Ta pozycja nie ma dopasowanego przelewu do odrzucenia.")
            return
        if row.get("status") not in {"DO SPRAWDZENIA", "OPŁACONA"}:
            messagebox.showinfo("Decyzja", "Można odrzucić tylko istniejące dopasowanie płatności.")
            return

        key = save_decision(row, "rejected")
        row["_decision_key"] = key
        row["manual_decision"] = "rejected"
        row["rejected_bank_date"] = row.get("bank_date", "")
        row["rejected_bank_amount"] = row.get("bank_amount", "")
        row["rejected_bank_counterparty"] = row.get("bank_counterparty", "")
        row["rejected_bank_title"] = row.get("bank_title", "")
        row["status"] = "BRAK"
        row["bank_date"] = ""
        row["bank_amount"] = ""
        row["bank_counterparty"] = ""
        row["bank_title"] = ""
        row["amount_diff"] = ""
        row["days_diff"] = ""
        self._refresh_tree()
        self._refresh_summary(1)
        messagebox.showinfo(
            "Zapamiętano",
            "To dopasowanie zostało odrzucone i nie będzie ponownie uznawane przy tym samym przelewie.",
        )

    def _undo_selected(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if not row.get("manual_decision") and not row.get("_decision_key"):
            messagebox.showinfo("Decyzja", "Dla tej pozycji nie ma ręcznej decyzji do cofnięcia.")
            return
        if not remove_decision(row):
            messagebox.showinfo("Decyzja", "Nie znaleziono zapisanej decyzji dla tej pozycji.")
            return

        messagebox.showinfo("Decyzja", "Ręczna decyzja została cofnięta. PayCheck przeliczy dopasowania ponownie.")
        self._compare()

    def _show_budget_summary(self) -> None:
        if self.source_mode != "budget" or not self.items:
            messagebox.showinfo("Budżet", "Najpierw wczytaj plik budżetu i wybierz miesiąc.")
            return
        BudgetSummaryWindow(self, self.budget_sheet or "wybrany miesiąc", self.items)

    def _show_history(self) -> None:
        if not load_history():
            messagebox.showinfo("Historia", "Historia jest jeszcze pusta. Wykonaj pierwsze porównanie płatności.")
            return
        HistoryWindow(self)


if __name__ == "__main__":
    PayCheckHistoryApp().mainloop()
