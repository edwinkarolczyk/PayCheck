from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_full import PayCheckFullApp, SimpleTableWindow
from budget_summary import summarize_budget
from finance_050 import (
    apply_rules,
    detect_anomalies,
    export_backup,
    forecast_month,
    import_backup,
    installment_plan,
    load_rules,
    payment_deadline_status,
    remember_rule,
)
from history_store import append_snapshot, load_history, make_snapshot


class ReviewCenter(tk.Toplevel):
    def __init__(self, app: "PayCheck050App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Centrum — Do sprawdzenia")
        self.geometry("1050x620")
        self.minsize(820, 480)

        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Centrum — Do sprawdzenia", font=("Segoe UI", 17, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Zatwierdzaj tylko dopasowania, które rzeczywiście odpowiadają pozycji budżetu.",
        ).pack(anchor="w", pady=(0, 8))

        columns = ("idx", "name", "inst", "plan", "bank", "title", "kind")
        self.tree = ttk.Treeview(root, columns=columns, show="headings")
        heads = {
            "idx": "#", "name": "Pozycja", "inst": "Instytucja", "plan": "Plan",
            "bank": "Kwota bank", "title": "Tytuł przelewu", "kind": "Rodzaj",
        }
        widths = {"idx": 45, "name": 170, "inst": 180, "plan": 90, "bank": 100, "title": 330, "kind": 110}
        for key in columns:
            self.tree.heading(key, text=heads[key])
            self.tree.column(key, width=widths[key], anchor="w")
        self.tree.pack(fill="both", expand=True)

        buttons = ttk.Frame(root)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="✓ Zatwierdź", command=self._approve).pack(side="left")
        ttk.Button(buttons, text="✗ Odrzuć", command=self._reject).pack(side="left", padx=8)
        ttk.Button(buttons, text="Odśwież", command=self._fill).pack(side="left")
        self._fill()

    def _fill(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for idx, row in enumerate(self.app.results):
            if row.get("status") != "DO SPRAWDZENIA":
                continue
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(
                    idx + 1,
                    row.get("display_name") or row.get("invoice_no", ""),
                    row.get("institution") or row.get("counterparty", ""),
                    row.get("amount", ""),
                    row.get("bank_amount", ""),
                    row.get("bank_title", ""),
                    row.get("match_kind", "ZWYKŁE"),
                ),
            )

    def _activate_main_row(self) -> bool:
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Do sprawdzenia", "Zaznacz pozycję.", parent=self)
            return False
        idx = int(selected[0])
        self.app.filter_mode = "Wszystkie"
        self.app._refresh_tree()
        if self.app.tree.exists(str(idx)):
            self.app.tree.selection_set(str(idx))
            self.app.tree.focus(str(idx))
        return True

    def _approve(self) -> None:
        if self._activate_main_row():
            self.app._approve_selected()
            self._fill()

    def _reject(self) -> None:
        if self._activate_main_row():
            self.app._reject_selected()
            self._fill()


class PayCheck050App(PayCheckFullApp):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 0.5.0")
        self._build_dashboard_strip()
        self._extend_menu()
        self._update_dashboard_strip()

    def _build_dashboard_strip(self) -> None:
        parent = self.tree.master
        self.dashboard_frame = ttk.LabelFrame(parent, text="Dashboard", padding=8)
        self.dashboard_frame.pack(fill="x", pady=(0, 8), before=self.tree)
        self.card_vars = {
            "planned": tk.StringVar(value="Plan: —"),
            "paid": tk.StringVar(value="Opłacone: —"),
            "remaining": tk.StringVar(value="Zostało: —"),
            "review": tk.StringVar(value="Do sprawdzenia: —"),
            "alert": tk.StringVar(value="Anomalie: —"),
        }
        for var in self.card_vars.values():
            ttk.Label(self.dashboard_frame, textvariable=var, font=("Segoe UI", 10, "bold"), padding=(10, 5)).pack(side="left")

    def _extend_menu(self) -> None:
        menu = self.nametowidget(self.cget("menu"))

        control = tk.Menu(menu, tearoff=False)
        control.add_command(label="Centrum — Do sprawdzenia", command=self._review_center)
        control.add_command(label="Anomalie kosztów", command=self._show_anomalies)
        control.add_command(label="Prognoza końca miesiąca", command=self._show_forecast)
        control.add_command(label="Terminy / zaległości", command=self._show_deadlines)
        control.add_separator()
        control.add_command(label="Utwórz regułę z zaznaczonej płatności", command=self._remember_rule)
        control.add_command(label="Pokaż reguły automatyczne", command=self._show_rules)
        control.add_separator()
        control.add_command(label="Wykres kategorii", command=self._chart_categories)
        control.add_command(label="Wykres historii budżetu", command=self._chart_history)
        menu.add_cascade(label="Kontrola", menu=control)

        installments = tk.Menu(menu, tearoff=False)
        installments.add_command(label="Plan spłaty rat", command=self._show_installments)
        menu.add_cascade(label="Raty", menu=installments)

        backup = tk.Menu(menu, tearoff=False)
        backup.add_command(label="Eksportuj backup", command=self._export_backup)
        backup.add_command(label="Importuj backup", command=self._import_backup)
        menu.add_cascade(label="Backup", menu=backup)

    def _compare(self) -> None:
        super()._compare()
        if not self.results:
            self._update_dashboard_strip()
            return

        rule_count = apply_rules(self.results, self.transactions)
        if rule_count:
            self._refresh_tree()
            self._refresh_summary()
            self.summary_var.set(self.summary_var.get() + f" | reguły: {rule_count}")
            snapshot = make_snapshot(
                self.results,
                source_mode=self.source_mode,
                source_label=self.budget_sheet or self.invoice_info_var.get(),
                source_sheet=self.budget_sheet,
            )
            append_snapshot(snapshot)
        self._update_dashboard_strip()

    def _update_dashboard_strip(self) -> None:
        if not getattr(self, "results", None):
            for key, text in {
                "planned": "Plan: —", "paid": "Opłacone: —", "remaining": "Zostało: —",
                "review": "Do sprawdzenia: —", "alert": "Anomalie: —",
            }.items():
                self.card_vars[key].set(text)
            return
        data = forecast_month(self.results)
        alerts = detect_anomalies(self.results, load_history())
        review_count = sum(r.get("status") == "DO SPRAWDZENIA" for r in self.results)
        self.card_vars["planned"].set(f"Plan: {data['planned']:.2f} zł")
        self.card_vars["paid"].set(f"Opłacone: {data['paid_actual']:.2f} zł")
        self.card_vars["remaining"].set(f"Zostało: {data['remaining']:.2f} zł")
        self.card_vars["review"].set(f"Do sprawdzenia: {review_count}")
        self.card_vars["alert"].set(f"Anomalie: {len(alerts)}")

    def _review_center(self) -> None:
        if not self.results:
            messagebox.showinfo("Do sprawdzenia", "Najpierw wykonaj porównanie.")
            return
        ReviewCenter(self)

    def _remember_rule(self) -> None:
        row = self._selected_row()
        if row is None:
            return
        try:
            remember_rule(row)
        except ValueError as exc:
            messagebox.showerror("Reguła", str(exc))
            return
        messagebox.showinfo("Reguła", "Reguła została zapisana. Przy kolejnych porównaniach będzie używana automatycznie.")

    def _show_rules(self) -> None:
        rules = load_rules()
        rows = [("TAK" if r.get("enabled", True) else "NIE", r.get("item_key", ""), r.get("phrase", "")) for r in rules]
        SimpleTableWindow(
            self, "Reguły automatyczne",
            [("enabled", "Aktywna", 80), ("item", "Pozycja", 280), ("phrase", "Rozpoznawany opis", 520)],
            rows,
        )

    def _show_anomalies(self) -> None:
        if not self.results:
            messagebox.showinfo("Anomalie", "Najpierw wykonaj porównanie.")
            return
        alerts = detect_anomalies(self.results, load_history())
        rows = [(a["name"], a["current"], a["average"], f"{a['change_percent']:+.1f}%", a["kind"]) for a in alerts]
        SimpleTableWindow(
            self, "Anomalie kosztów — próg 25%",
            [("name", "Pozycja", 250), ("current", "Teraz", 100), ("avg", "Średnia", 100), ("change", "Zmiana", 100), ("kind", "Typ", 110)],
            rows,
        )

    def _show_forecast(self) -> None:
        if not self.results:
            messagebox.showinfo("Prognoza", "Najpierw wykonaj porównanie.")
            return
        data = forecast_month(self.results)
        messagebox.showinfo(
            "Prognoza końca miesiąca",
            f"Plan: {data['planned']:.2f} zł\nJuż opłacone: {data['paid_actual']:.2f} zł\nJeszcze może wyjść: {data['remaining']:.2f} zł\nPrognozowany koszt: {data['projected']:.2f} zł",
        )

    def _show_deadlines(self) -> None:
        if not self.results:
            messagebox.showinfo("Terminy", "Najpierw wykonaj porównanie.")
            return
        history = load_history()
        rows = []
        for row in self.results:
            if row.get("entry_type") == "income":
                continue
            rows.append((
                row.get("display_name") or row.get("invoice_no", ""),
                row.get("amount", ""),
                row.get("status", ""),
                payment_deadline_status(history, row),
            ))
        SimpleTableWindow(
            self, "Terminy i zaległości",
            [("name", "Pozycja", 280), ("amount", "Kwota", 100), ("status", "Płatność", 150), ("deadline", "Termin z historii", 240)],
            rows,
        )

    def _show_installments(self) -> None:
        if self.source_mode != "budget" or not self.items:
            messagebox.showinfo("Raty", "Najpierw wczytaj budżet.")
            return
        rows = installment_plan(self.items)
        values = [(r["name"], r["bank"], f"{r['monthly']:.2f}", r["end"], r["months_left"], f"{r['estimated_left']:.2f}") for r in rows]
        SimpleTableWindow(
            self, "Plan spłaty rat",
            [("name", "Rata", 190), ("bank", "Bank", 130), ("monthly", "Miesięcznie", 100), ("end", "Koniec", 105), ("months", "Miesięcy", 85), ("left", "Szac. pozostało", 130)],
            values,
        )

    def _export_backup(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Eksport backupu PayCheck", defaultextension=".zip",
            initialfile="PayCheck_backup.zip", filetypes=[("ZIP", "*.zip")],
        )
        if not path:
            return
        export_backup(path)
        messagebox.showinfo("Backup", f"Backup zapisano:\n{path}")

    def _import_backup(self) -> None:
        path = filedialog.askopenfilename(title="Import backupu PayCheck", filetypes=[("ZIP", "*.zip")])
        if not path:
            return
        if not messagebox.askyesno("Import backupu", "Import zastąpi lokalne pliki historii, decyzji, aliasów i reguł, jeśli znajdują się w backupie. Kontynuować?"):
            return
        try:
            count = import_backup(path)
        except Exception as exc:
            messagebox.showerror("Backup", f"Nie udało się zaimportować backupu:\n{exc}")
            return
        messagebox.showinfo("Backup", f"Przywrócono plików: {count}. Uruchom ponownie PayCheck, aby wszystkie dane zostały odświeżone.")

    def _chart_categories(self) -> None:
        if self.source_mode != "budget" or not self.items:
            messagebox.showinfo("Wykres", "Najpierw wczytaj budżet.")
            return
        summary = summarize_budget(self.items)
        labels = [k for k in summary["categories"] if k != "Wpływy"]
        values = [summary["categories"][k] for k in labels]
        self._chart_bar("Wydatki według kategorii", labels, values)

    def _chart_history(self) -> None:
        history = [h for h in load_history() if h.get("source_mode") == "budget"]
        labels, values = [], []
        for snap in history[-12:]:
            amount = sum(float(r.get("amount") or 0) for r in snap.get("rows", []) if r.get("status") in {"OPŁACONA", "DO SPRAWDZENIA", "BRAK"})
            labels.append(snap.get("source_sheet") or snap.get("source_label", ""))
            values.append(amount)
        self._chart_bar("Historia budżetu — do 12 zapisów", labels, values)

    def _chart_bar(self, title: str, labels: list[str], values: list[float]) -> None:
        if not labels:
            messagebox.showinfo("Wykres", "Brak danych do pokazania.")
            return
        try:
            from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
            from matplotlib.figure import Figure
        except ImportError:
            messagebox.showerror("Wykres", "Brak biblioteki matplotlib. Uruchom ponownie run.bat, aby doinstalować zależności.")
            return
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("980x620")
        fig = Figure(figsize=(9, 5), dpi=100)
        ax = fig.add_subplot(111)
        ax.bar(labels, values)
        ax.set_title(title)
        ax.set_ylabel("zł")
        ax.tick_params(axis="x", rotation=35)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    PayCheck050App().mainloop()
