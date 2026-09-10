from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from advanced_features import (
    dashboard,
    detect_split_and_grouped,
    filter_results,
    item_history,
    remember_alias,
    trend_for_item,
)
from alias_apply import apply_alias_matches
from app_budget import PayCheckApp
from app_history import BudgetSummaryWindow, HistoryWindow, PayCheckHistoryApp
from budget_loader import list_budget_sheets, load_budget_sheet
from budget_summary import summarize_budget
from decision_store import apply_decisions
from history_store import (
    append_snapshot,
    compare_snapshots,
    load_history,
    make_snapshot,
    previous_snapshot,
)
from matcher import MatchSettings


class SimpleTableWindow(tk.Toplevel):
    def __init__(self, parent, title: str, columns: list[tuple[str, str, int]], rows: list[tuple]):
        super().__init__(parent)
        self.title(title)
        self.geometry("950x600")
        self.minsize(760, 440)
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=title, font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
        keys = tuple(key for key, _label, _width in columns)
        tree = ttk.Treeview(root, columns=keys, show="headings")
        for key, label, width in columns:
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for values in rows:
            tree.insert("", "end", values=values)
        scroll = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")


class DashboardWindow(tk.Toplevel):
    def __init__(self, parent, sheet: str, data: dict, previous: dict | None = None):
        super().__init__(parent)
        self.title(f"Dashboard — {sheet}")
        self.geometry("820x520")
        self.minsize(680, 430)
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=f"Dashboard — {sheet}", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                f"Planowane wydatki: {data['planned']:.2f} zł\n"
                f"Opłacone: {data['paid']:.2f} zł ({data['paid_percent']:.1f}%)\n"
                f"Do sprawdzenia: {data['review']:.2f} zł\n"
                f"Brak płatności: {data['missing']:.2f} zł\n"
                f"Pozycje opłacone: {data['paid_count']} / {data['total_count']}"
            ),
            font=("Segoe UI", 12),
            justify="left",
        ).pack(anchor="w", pady=(18, 14))

        if previous:
            diff = data["planned"] - previous["planned"]
            pct = (diff / previous["planned"] * 100) if previous["planned"] else 0.0
            ttk.Separator(root).pack(fill="x", pady=10)
            ttk.Label(
                root,
                text=(
                    f"Poprzedni miesiąc: {previous['sheet']} — {previous['planned']:.2f} zł\n"
                    f"Zmiana planowanych wydatków: {diff:+.2f} zł ({pct:+.1f}%)"
                ),
                font=("Segoe UI", 11, "bold"),
                justify="left",
            ).pack(anchor="w")

        ttk.Label(
            root,
            text="Płatności dzielone i łączone są liczone jako DO SPRAWDZENIA do ręcznego zatwierdzenia.",
            wraplength=760,
        ).pack(anchor="w", pady=(20, 0))


class PayCheckFullApp(PayCheckHistoryApp):
    FILTERS = ("Wszystkie", "Opłacone", "Do sprawdzenia", "Brak", "Ręczne")

    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.3.2")
        self.filter_mode = "Wszystkie"
        self._build_full_menu()

    def _build_full_menu(self) -> None:
        menu = tk.Menu(self)

        budget_menu = tk.Menu(menu, tearoff=False)
        budget_menu.add_command(label="Podsumowanie budżetu", command=self._show_budget_summary)
        budget_menu.add_command(label="Dashboard miesiąca", command=self._show_dashboard)
        budget_menu.add_command(label="Porównaj miesiące", command=self._compare_months)
        menu.add_cascade(label="Budżet", menu=budget_menu)

        filter_menu = tk.Menu(menu, tearoff=False)
        for value in self.FILTERS:
            filter_menu.add_command(label=value, command=lambda v=value: self._set_filter(v))
        menu.add_cascade(label="Filtr", menu=filter_menu)

        decision_menu = tk.Menu(menu, tearoff=False)
        decision_menu.add_command(label="✓ Uznaj zaznaczone za opłacone", command=self._approve_selected)
        decision_menu.add_command(label="✗ Odrzuć zaznaczone dopasowanie", command=self._reject_selected)
        decision_menu.add_separator()
        decision_menu.add_command(label="Cofnij ręczną decyzję", command=self._undo_selected)
        menu.add_cascade(label="Decyzja", menu=decision_menu)

        learning_menu = tk.Menu(menu, tearoff=False)
        learning_menu.add_command(label="Zapamiętaj kontrahenta / opis", command=self._remember_alias)
        menu.add_cascade(label="Pamięć", menu=learning_menu)

        history_menu = tk.Menu(menu, tearoff=False)
        history_menu.add_command(label="Historia porównań", command=self._show_history)
        history_menu.add_command(label="Historia zaznaczonej pozycji", command=self._show_item_history)
        history_menu.add_separator()
        history_menu.add_command(label="Trend 3 miesiące", command=lambda: self._show_trend(3))
        history_menu.add_command(label="Trend 6 miesięcy", command=lambda: self._show_trend(6))
        history_menu.add_command(label="Trend 12 miesięcy", command=lambda: self._show_trend(12))
        menu.add_cascade(label="Historia / trendy", menu=history_menu)

        self.config(menu=menu)

    def _settings(self) -> MatchSettings:
        return MatchSettings(
            days_tolerance=max(0, self.days_var.get()),
            amount_percent_tolerance=max(0.0, self.percent_var.get()),
            amount_absolute_tolerance=max(0.0, self.amount_var.get()),
        )

    def _compare(self) -> None:
        # Bazowe dopasowanie bez zapisu historii; historia ma uwzględniać już wszystkie nowe mechanizmy.
        PayCheckApp._compare(self)
        if not self.results:
            return

        settings = self._settings()
        aliases = apply_alias_matches(self.results, self.transactions, settings)
        complex_matches = 0
        if self.source_mode == "budget":
            complex_matches = detect_split_and_grouped(self.results, self.transactions, settings)
        remembered = apply_decisions(self.results)
        self._refresh_tree()
        self._refresh_summary(remembered)

        extras = []
        if aliases:
            extras.append(f"pamięć kontrahentów: {aliases}")
        if complex_matches:
            extras.append(f"dzielone/łączone: {complex_matches}")
        if extras:
            self.summary_var.set(self.summary_var.get() + " | " + " | ".join(extras))

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
            names = ", ".join(changes["newly_paid"][:6])
            self.summary_var.set(
                self.summary_var.get()
                + f" | Nowo opłacone: {len(changes['newly_paid'])} ({names})"
            )

    def _set_filter(self, mode: str) -> None:
        self.filter_mode = mode
        self._refresh_tree()
        self.summary_var.set(self.summary_var.get().split(" | Widok:")[0] + f" | Widok: {mode}")

    def _refresh_tree(self) -> None:
        if not hasattr(self, "tree"):
            return
        self.tree.delete(*self.tree.get_children())
        visible = filter_results(self.results, getattr(self, "filter_mode", "Wszystkie"))
        for row in visible:
            original_index = self.results.index(row)
            name = row.get("display_name") or row.get("invoice_no", "")
            institution = row.get("institution") or row.get("counterparty", "")
            status = row.get("status", "")
            tag = {"OPŁACONA": "paid", "DO SPRAWDZENIA": "review", "BRAK": "missing"}.get(status, "")
            kind = row.get("match_kind")
            status_text = f"{status} ({kind})" if kind else status
            self.tree.insert(
                "",
                "end",
                iid=str(original_index),
                values=(
                    name,
                    institution,
                    row.get("date", ""),
                    row.get("amount", ""),
                    status_text,
                    row.get("match_score", ""),
                    row.get("bank_date", ""),
                    row.get("bank_amount", ""),
                    row.get("amount_diff", ""),
                ),
                tags=(tag,) if tag else (),
            )

    def _selected_row(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("PayCheck", "Zaznacz najpierw pozycję w tabeli.")
            return None
        try:
            index = int(selected[0])
        except ValueError:
            return None
        return self.results[index] if 0 <= index < len(self.results) else None

    def _remember_alias(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        if not row.get("bank_counterparty") and not row.get("bank_title"):
            messagebox.showinfo("Pamięć", "Ta pozycja nie ma dopasowanego opisu bankowego.")
            return
        try:
            remember_alias(row)
        except ValueError as exc:
            messagebox.showerror("Pamięć", str(exc))
            return
        messagebox.showinfo(
            "Pamięć kontrahentów",
            "Zapamiętano ten opis bankowy dla wybranej pozycji. Będzie miał priorytet w kolejnych miesiącach.",
        )

    def _show_item_history(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        entries = item_history(load_history(), row)
        if not entries:
            messagebox.showinfo("Historia pozycji", "Brak zapisanej historii dla tej pozycji.")
            return
        rows = [
            (
                e.get("sheet", ""),
                str(e.get("created_at", "")).replace("T", " "),
                e.get("amount", ""),
                e.get("status", ""),
                e.get("bank_amount", ""),
            )
            for e in entries
        ]
        SimpleTableWindow(
            self,
            f"Historia — {row.get('display_name') or row.get('invoice_no', '')}",
            [
                ("month", "Miesiąc", 150),
                ("date", "Sprawdzenie", 170),
                ("amount", "Plan", 100),
                ("status", "Status", 150),
                ("bank", "Bank", 100),
            ],
            rows,
        )

    def _show_trend(self, months: int) -> None:
        row = self._selected_row()
        if row is None:
            return
        trend = trend_for_item(load_history(), row, months)
        if not trend["count"]:
            messagebox.showinfo("Trend", "Brak danych historycznych dla tej pozycji.")
            return
        change = "brak danych" if trend["change_percent"] is None else f"{trend['change_percent']:+.1f}%"
        messagebox.showinfo(
            f"Trend {months} miesięcy",
            (
                f"{row.get('display_name') or row.get('invoice_no', '')}\n\n"
                f"Dostępne miesiące: {trend['count']}\n"
                f"Średnia: {trend['average']:.2f} zł\n"
                f"Minimum: {trend['min']:.2f} zł\n"
                f"Maksimum: {trend['max']:.2f} zł\n"
                f"Ostatnia zmiana: {change}"
            ),
        )

    def _previous_budget(self) -> dict | None:
        if not self.budget_path or not self.budget_sheet:
            return None
        sheets = list_budget_sheets(self.budget_path)
        try:
            index = sheets.index(self.budget_sheet)
        except ValueError:
            return None
        for name in reversed(sheets[:index]):
            try:
                items = load_budget_sheet(self.budget_path, name)
            except Exception:
                continue
            summary = summarize_budget(items)
            return {"sheet": name, "planned": summary["expense_total"]}
        return None

    def _show_dashboard(self) -> None:
        if self.source_mode != "budget" or not self.results:
            messagebox.showinfo("Dashboard", "Wczytaj budżet i wykonaj porównanie płatności.")
            return
        DashboardWindow(
            self,
            self.budget_sheet or "wybrany miesiąc",
            dashboard(self.results),
            self._previous_budget(),
        )


if __name__ == "__main__":
    PayCheckFullApp().mainloop()
