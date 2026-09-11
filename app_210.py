from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from annual_report import annual_report, available_years, export_annual_report_xlsx
from app_100 import BLUE, GREEN, ORANGE, PURPLE, RED, TEAL
from app_200 import PayCheck200App


class AnnualReportWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck210App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Raport roczny")
        self.geometry("1220x760")
        self.minsize(960, 620)
        self.year_var = tk.StringVar()
        self.report: dict = {}

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)

        top = ttk.Frame(root)
        top.pack(fill="x")
        ttk.Label(top, text="Raport roczny", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(top, text="Rok:").pack(side="left", padx=(24, 6))
        years = available_years()
        self.year_box = ttk.Combobox(top, textvariable=self.year_var, values=[str(y) for y in years], state="readonly", width=8)
        self.year_box.pack(side="left")
        self.year_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Button(top, text="Eksportuj do Excel", command=self._export).pack(side="right")

        if years:
            self.year_var.set(str(years[0]))

        self.cards = tk.Frame(root, bg="#D9DDE2")
        self.cards.pack(fill="x", pady=(14, 10))
        self.card_vars: dict[str, tk.StringVar] = {}
        for key, title, color in (
            ("income", "Wpływy", BLUE),
            ("expenses", "Wydatki", "#5B6670"),
            ("paid", "Potwierdzone", GREEN),
            ("review", "Do sprawdzenia", ORANGE),
            ("missing", "Brak", RED),
            ("balance", "Bilans", TEAL),
        ):
            box = tk.Frame(self.cards, bg=color)
            box.pack(side="left", fill="x", expand=True, padx=(0, 6))
            var = tk.StringVar(value="—")
            self.card_vars[key] = var
            tk.Label(box, text=title, bg=color, fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=10, pady=(8, 0))
            tk.Label(box, textvariable=var, bg=color, fg="white", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=10, pady=(2, 8))

        note = ttk.Frame(root)
        note.pack(fill="x", pady=(0, 10))
        self.summary_var = tk.StringVar(value="Brak zapisanych miesięcy.")
        ttk.Label(note, textvariable=self.summary_var, font=("Segoe UI", 10, "bold")).pack(anchor="w")

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True)

        self.month_tab = ttk.Frame(notebook)
        self.cat_tab = ttk.Frame(notebook)
        self.insight_tab = ttk.Frame(notebook)
        notebook.add(self.month_tab, text="Miesiące")
        notebook.add(self.cat_tab, text="Kategorie")
        notebook.add(self.insight_tab, text="Wnioski")

        self.month_tree = self._tree(
            self.month_tab,
            ("month", "income", "expenses", "paid", "review", "missing", "balance"),
            {
                "month": ("Miesiąc", 120), "income": ("Wpływy", 120), "expenses": ("Wydatki", 120),
                "paid": ("Potwierdzone", 125), "review": ("Do sprawdzenia", 125),
                "missing": ("Brak", 110), "balance": ("Bilans", 120),
            },
        )
        self.cat_tree = self._tree(
            self.cat_tab,
            ("category", "amount", "share"),
            {"category": ("Kategoria", 360), "amount": ("Kwota roczna", 170), "share": ("Udział", 120)},
        )
        self.insight_text = tk.Text(self.insight_tab, wrap="word", height=16, bg="#FAFBFC", fg="#22272B", relief="flat", padx=14, pady=14, font=("Segoe UI", 10))
        self.insight_text.pack(fill="both", expand=True, padx=10, pady=10)
        self.insight_text.configure(state="disabled")

        self.refresh()

    @staticmethod
    def _tree(parent, columns, heads):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for key in columns:
            label, width = heads[key]
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def refresh(self) -> None:
        years = available_years()
        self.year_box["values"] = [str(y) for y in years]
        if not years:
            self.report = {}
            self.summary_var.set("Brak zapisanych miesięcy do raportu rocznego.")
            return
        if not self.year_var.get():
            self.year_var.set(str(years[0]))
        year = int(self.year_var.get())
        self.report = annual_report(year)

        for key in ("income", "expenses", "paid", "review", "missing", "balance"):
            sign = "+" if key == "balance" and self.report[key] > 0 else ""
            self.card_vars[key].set(f"{sign}{self.report[key]:.2f} zł")
        self.summary_var.set(
            f"Zapisane miesiące: {self.report['months_count']} | Śr. wpływy: {self.report['average_income']:.2f} zł / mies. | "
            f"Śr. wydatki: {self.report['average_expenses']:.2f} zł / mies."
        )

        self.month_tree.delete(*self.month_tree.get_children())
        for row in self.report["months"]:
            self.month_tree.insert("", "end", values=(
                row["month_name"], f"{row['income']:.2f} zł", f"{row['expenses']:.2f} zł",
                f"{row['paid']:.2f} zł", f"{row['review']:.2f} zł", f"{row['missing']:.2f} zł", f"{row['balance']:+.2f} zł",
            ))

        self.cat_tree.delete(*self.cat_tree.get_children())
        for row in self.report["categories"]:
            self.cat_tree.insert("", "end", values=(row["category"], f"{row['amount']:.2f} zł", f"{row['share']:.1f}%"))

        self.insight_text.configure(state="normal")
        self.insight_text.delete("1.0", "end")
        if self.report["insights"]:
            for text in self.report["insights"]:
                self.insight_text.insert("end", f"• {text}\n\n")
        else:
            self.insight_text.insert("end", "Za mało danych, aby przygotować wnioski roczne.")
        self.insight_text.configure(state="disabled")

    def _export(self) -> None:
        if not self.report:
            messagebox.showinfo("Raport roczny", "Brak danych do eksportu.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Zapisz raport roczny",
            defaultextension=".xlsx",
            initialfile=f"PayCheck_Raport_{self.report['year']}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if not path:
            return
        try:
            export_annual_report_xlsx(self.report, path)
        except Exception as exc:
            messagebox.showerror("Raport roczny", str(exc), parent=self)
            return
        messagebox.showinfo("Raport roczny", f"Zapisano raport:\n{path}", parent=self)


class PayCheck210App(PayCheck200App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 2.1.0 — Menedżer budżetu domowego")
        self._extend_annual_report_ui()

    def _extend_annual_report_ui(self) -> None:
        self._action_button(self.quick_frame, "Rok", PURPLE, self._show_annual_report).pack(side="left", padx=(7, 0))
        menu = self.nametowidget(self.cget("menu"))
        report_menu = tk.Menu(menu, tearoff=False)
        report_menu.add_command(label="Podsumowanie roczne", command=self._show_annual_report)
        report_menu.add_command(label="Eksport roczny do Excel", command=self._export_current_year)
        menu.insert_cascade(4, label="Raporty", menu=report_menu)

    def _show_annual_report(self) -> None:
        AnnualReportWindow(self)

    def _export_current_year(self) -> None:
        years = available_years()
        if not years:
            messagebox.showinfo("Raport roczny", "Brak zapisanych miesięcy do raportu.")
            return
        report = annual_report(years[0])
        path = filedialog.asksaveasfilename(
            title="Zapisz raport roczny",
            defaultextension=".xlsx",
            initialfile=f"PayCheck_Raport_{report['year']}.xlsx",
            filetypes=[("Excel", "*.xlsx")],
        )
        if path:
            export_annual_report_xlsx(report, path)


if __name__ == "__main__":
    PayCheck210App().mainloop()
