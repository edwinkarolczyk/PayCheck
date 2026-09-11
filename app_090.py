from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from app_080 import PayCheck080App
from installment_store import (
    estimated_left,
    load_installments,
    months_left,
    remove_installment,
    set_installment_active,
    to_budget_items,
    upsert_installment,
)


class InstallmentEditor(tk.Toplevel):
    def __init__(self, parent: "InstallmentManager", row: dict | None = None) -> None:
        super().__init__(parent)
        self.parent = parent
        self.row = dict(row or {})
        self.title("Edytuj ratę" if row else "Dodaj ratę")
        self.resizable(False, False)
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill="both", expand=True)

        self.vars = {
            "name": tk.StringVar(value=self.row.get("name", "")),
            "bank": tk.StringVar(value=self.row.get("bank", "")),
            "monthly": tk.StringVar(value=str(self.row.get("monthly", ""))),
            "payment_day": tk.StringVar(value=str(self.row.get("payment_day", 10))),
            "start_date": tk.StringVar(value=str(self.row.get("start_date", ""))),
            "end_date": tk.StringVar(value=str(self.row.get("end_date", ""))),
            "total_installments": tk.StringVar(value=str(self.row.get("total_installments", ""))),
            "interest_type": tk.StringVar(value=self.row.get("interest_type", "0%")),
            "interest_rate": tk.StringVar(value=str(self.row.get("interest_rate", 0))),
            "note": tk.StringVar(value=self.row.get("note", "")),
        }
        labels = (
            ("name", "Nazwa / cel"), ("bank", "Bank"), ("monthly", "Rata miesięczna [zł]"),
            ("payment_day", "Dzień płatności"), ("start_date", "Start YYYY-MM-DD"),
            ("end_date", "Koniec YYYY-MM-DD"), ("total_installments", "Liczba rat"),
            ("interest_rate", "Oprocentowanie %"), ("note", "Uwagi"),
        )
        for r, (key, label) in enumerate(labels):
            ttk.Label(frame, text=label + ":").grid(row=r, column=0, sticky="w", pady=4)
            ttk.Entry(frame, textvariable=self.vars[key], width=34).grid(row=r, column=1, sticky="ew", padx=(10, 0), pady=4)

        r = len(labels)
        ttk.Label(frame, text="Rodzaj:").grid(row=r, column=0, sticky="w", pady=4)
        ttk.Combobox(frame, textvariable=self.vars["interest_type"], values=("0%", "Oprocentowana"), state="readonly", width=31).grid(row=r, column=1, sticky="ew", padx=(10, 0), pady=4)
        r += 1
        ttk.Button(frame, text="Zapisz ratę", command=self._save).grid(row=r, column=0, columnspan=2, pady=(14, 0))

    def _save(self) -> None:
        try:
            payload = dict(self.row)
            payload.update({key: var.get().strip() for key, var in self.vars.items()})
            payload["monthly"] = float(payload["monthly"].replace(",", "."))
            payload["payment_day"] = int(payload["payment_day"] or 1)
            payload["total_installments"] = int(payload["total_installments"] or 0)
            payload["interest_rate"] = float(payload["interest_rate"].replace(",", ".") or 0)
            saved = upsert_installment(payload)
        except Exception as exc:
            messagebox.showerror("Rata", str(exc), parent=self)
            return
        self.parent.refresh()
        self.parent.app._sync_manual_installments()
        messagebox.showinfo("Rata", f"Zapisano: {saved['name']}", parent=self)
        self.destroy()


class InstallmentManager(tk.Toplevel):
    def __init__(self, app: "PayCheck090App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Raty i zobowiązania")
        self.geometry("1180x650")
        self.minsize(900, 500)
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Raty i zobowiązania", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(root, text="Raty są zapisywane lokalnie i automatycznie dodawane do aktywnego miesiąca budżetu.").pack(anchor="w", pady=(0, 10))

        cols = ("name", "bank", "monthly", "day", "end", "left", "sumleft", "type", "active")
        self.tree = ttk.Treeview(root, columns=cols, show="headings")
        heads = {
            "name":"Nazwa", "bank":"Bank", "monthly":"Miesięcznie", "day":"Dzień", "end":"Koniec",
            "left":"Pozostało rat", "sumleft":"Szac. pozostało", "type":"Rodzaj", "active":"Status"
        }
        widths = {"name":180,"bank":120,"monthly":100,"day":70,"end":100,"left":100,"sumleft":130,"type":120,"active":90}
        for key in cols:
            self.tree.heading(key, text=heads[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)

        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(10,0))
        ttk.Button(bar, text="+ Dodaj ratę", command=self._add).pack(side="left")
        ttk.Button(bar, text="Edytuj", command=self._edit).pack(side="left", padx=6)
        ttk.Button(bar, text="Zakończ / wznów", command=self._toggle).pack(side="left", padx=6)
        ttk.Button(bar, text="Usuń", command=self._delete).pack(side="left", padx=6)
        self.summary = tk.StringVar()
        ttk.Label(bar, textvariable=self.summary, font=("Segoe UI", 10, "bold")).pack(side="right")
        self.refresh()

    def _selected(self) -> dict | None:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Raty", "Zaznacz ratę.", parent=self)
            return None
        ident = selected[0]
        return next((r for r in load_installments() if r.get("id") == ident), None)

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        rows = load_installments()
        active_total = 0.0
        active_count = 0
        for row in rows:
            left = months_left(row)
            left_sum = estimated_left(row)
            active = bool(row.get("active", True))
            if active:
                active_count += 1
                active_total += float(row.get("monthly") or 0)
            self.tree.insert("", "end", iid=row["id"], values=(
                row.get("name", ""), row.get("bank", ""), f"{float(row.get('monthly') or 0):.2f} zł",
                row.get("payment_day", ""), row.get("end_date") or "—", "—" if left is None else left,
                "—" if left_sum is None else f"{left_sum:.2f} zł", row.get("interest_type", ""),
                "AKTYWNA" if active else "ZAKOŃCZONA",
            ))
        self.summary.set(f"Aktywne: {active_count} | {active_total:.2f} zł / mies.")

    def _add(self) -> None:
        InstallmentEditor(self)

    def _edit(self) -> None:
        row = self._selected()
        if row:
            InstallmentEditor(self, row)

    def _toggle(self) -> None:
        row = self._selected()
        if not row:
            return
        set_installment_active(row["id"], not bool(row.get("active", True)))
        self.refresh()
        self.app._sync_manual_installments()

    def _delete(self) -> None:
        row = self._selected()
        if not row:
            return
        if messagebox.askyesno("Usuń ratę", f"Usunąć trwale: {row.get('name','')}?", parent=self):
            remove_installment(row["id"])
            self.refresh()
            self.app._sync_manual_installments()


class PayCheck090App(PayCheck080App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.9.0")
        self._extend_installment_ui()
        self._sync_manual_installments()

    def _extend_installment_ui(self) -> None:
        top = self.month_frame.winfo_children()[0]
        ttk.Button(top, text="Raty", command=self._show_installment_manager).pack(side="left", padx=(8,0))
        menu = self.nametowidget(self.cget("menu"))
        liabilities = tk.Menu(menu, tearoff=False)
        liabilities.add_command(label="Raty i zobowiązania", command=self._show_installment_manager)
        liabilities.add_command(label="Dodaj nową ratę", command=lambda: InstallmentEditor(InstallmentManager(self)))
        liabilities.add_separator()
        liabilities.add_command(label="Plan rat w bieżącym miesiącu", command=self._show_budget_manager)
        menu.insert_cascade(2, label="Zobowiązania", menu=liabilities)

    def _show_installment_manager(self) -> None:
        InstallmentManager(self)

    def _sync_manual_installments(self) -> None:
        if self.source_mode != "budget" or not self.budget_sheet:
            return
        base = [item for item in self.items if not item.get("manual_installment_id")]
        manual = to_budget_items(load_installments(), self.budget_sheet)
        existing_keys = {
            (str(item.get("institution", "")).strip().lower(), str(item.get("display_name", "")).strip().lower())
            for item in base
        }
        manual = [item for item in manual if (
            str(item.get("institution", "")).strip().lower(), str(item.get("display_name", "")).strip().lower()
        ) not in existing_keys]
        self.items = base + manual
        if self.transactions:
            super()._compare()
        else:
            self.results = []
            self._save_current_month()
            self._refresh_tree()
        self._update_month_header()

    def _choose_budget(self) -> None:
        super()._choose_budget()
        self._sync_manual_installments()

    def _restore_state(self, state: dict) -> None:
        super()._restore_state(state)
        self._sync_manual_installments()


if __name__ == "__main__":
    PayCheck090App().mainloop()
