from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from app_budget import PayCheckApp
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


class PayCheckHistoryApp(PayCheckApp):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.2.1")

        menu = tk.Menu(self)
        history_menu = tk.Menu(menu, tearoff=False)
        history_menu.add_command(label="Pokaż historię porównań", command=self._show_history)
        menu.add_cascade(label="Historia", menu=history_menu)
        self.config(menu=menu)

    def _compare(self) -> None:
        super()._compare()
        if not self.results:
            return

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

    def _show_history(self) -> None:
        if not load_history():
            messagebox.showinfo("Historia", "Historia jest jeszcze pusta. Wykonaj pierwsze porównanie płatności.")
            return
        HistoryWindow(self)


if __name__ == "__main__":
    PayCheckHistoryApp().mainloop()
