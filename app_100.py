from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app_090 import PayCheck090App
from dashboard_100 import home_dashboard


BG = "#D9DDE2"
PANEL = "#EEF1F4"
TEXT = "#22272B"
MUTED = "#5D6770"
BLUE = "#1976D2"
GREEN = "#2E7D32"
ORANGE = "#EF8C00"
RED = "#C62828"
PURPLE = "#6A3FB5"
TEAL = "#167D83"


class PayCheck100App(PayCheck090App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 1.0.0 — Budżet domowy")
        self.geometry("1420x860")
        self.configure(bg=BG)
        self._apply_gray_theme()
        self._replace_legacy_dashboard()
        self._build_quick_actions()
        self._build_home_dashboard()
        self._refresh_home_dashboard()

    def _apply_gray_theme(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("TLabelframe", background=BG, foreground=TEXT)
        style.configure("TLabelframe.Label", background=BG, foreground=TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 7))
        style.configure("Treeview", rowheight=28, background="#FAFBFC", fieldbackground="#FAFBFC", foreground=TEXT)
        style.configure("Treeview.Heading", background="#C8CDD3", foreground=TEXT, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#BBD7F0")], foreground=[("selected", TEXT)])

        self.tree.tag_configure("paid", background="#D7EAD9", foreground="#17551C")
        self.tree.tag_configure("review", background="#FFE7B7", foreground="#805100")
        self.tree.tag_configure("missing", background="#F3CED1", foreground="#7A1820")

    def _replace_legacy_dashboard(self) -> None:
        if hasattr(self, "dashboard_frame"):
            self.dashboard_frame.pack_forget()

    def _action_button(self, parent, text: str, color: str, command) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg="white",
            activebackground=color,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=16,
            pady=9,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )

    def _build_quick_actions(self) -> None:
        parent = self.tree.master
        self.quick_frame = tk.Frame(parent, bg=BG)
        self.quick_frame.pack(fill="x", pady=(0, 8), before=self.tree)

        self._action_button(self.quick_frame, "Budżet", BLUE, self._show_budget_manager).pack(side="left", padx=(0, 7))
        self._action_button(self.quick_frame, "+ Aktualizuj wyciąg", TEAL, self._add_statements).pack(side="left", padx=(0, 7))
        self.review_quick = self._action_button(self.quick_frame, "Do zatwierdzenia", ORANGE, self._review_center_060)
        self.review_quick.pack(side="left", padx=(0, 7))
        self._action_button(self.quick_frame, "Raty", PURPLE, self._show_installment_manager).pack(side="left", padx=(0, 7))
        self._action_button(self.quick_frame, "Analiza", "#546E7A", self._show_dashboard).pack(side="left")

    def _card(self, parent, title: str, color: str):
        frame = tk.Frame(parent, bg=color, bd=0, highlightthickness=0)
        title_var = tk.StringVar(value=title)
        value_var = tk.StringVar(value="—")
        tk.Label(frame, textvariable=title_var, bg=color, fg="white", font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=12, pady=(9, 0))
        tk.Label(frame, textvariable=value_var, bg=color, fg="white", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=12, pady=(2, 9))
        return frame, value_var

    def _build_home_dashboard(self) -> None:
        parent = self.tree.master
        self.home = tk.Frame(parent, bg=BG)
        self.home.pack(fill="x", pady=(0, 10), before=self.tree)

        cards = tk.Frame(self.home, bg=BG)
        cards.pack(fill="x")
        specs = (
            ("income", "Wpływy", BLUE),
            ("expenses", "Plan wydatków", "#5B6670"),
            ("paid", "Potwierdzone", GREEN),
            ("remaining", "Zostało", RED),
            ("installments", "Raty / mies.", PURPLE),
            ("balance", "Bilans planu", TEAL),
        )
        self.home_vars = {}
        for key, title, color in specs:
            card, var = self._card(cards, title, color)
            card.pack(side="left", fill="x", expand=True, padx=(0, 7))
            self.home_vars[key] = var

        progress_box = tk.Frame(self.home, bg=PANEL)
        progress_box.pack(fill="x", pady=(8, 0))
        self.progress_label = tk.StringVar(value="Realizacja miesiąca: —")
        tk.Label(progress_box, textvariable=self.progress_label, bg=PANEL, fg=TEXT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(8, 4))
        self.progress = ttk.Progressbar(progress_box, maximum=100)
        self.progress.pack(fill="x", padx=12, pady=(0, 9))

        details = tk.Frame(self.home, bg=BG)
        details.pack(fill="x", pady=(8, 0))

        attention_box = tk.Frame(details, bg="#F6E5E7")
        attention_box.pack(side="left", fill="both", expand=True, padx=(0, 5))
        tk.Label(attention_box, text="Wymaga uwagi", bg="#F6E5E7", fg=RED, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(9, 3))
        self.attention_var = tk.StringVar(value="Brak danych")
        tk.Label(attention_box, textvariable=self.attention_var, justify="left", anchor="w", bg="#F6E5E7", fg=TEXT, font=("Segoe UI", 9)).pack(fill="x", padx=12, pady=(0, 9))

        installment_box = tk.Frame(details, bg="#EDE6F8")
        installment_box.pack(side="left", fill="both", expand=True, padx=(5, 0))
        tk.Label(installment_box, text="Najbliższe raty", bg="#EDE6F8", fg=PURPLE, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(9, 3))
        self.installment_var = tk.StringVar(value="Brak danych")
        tk.Label(installment_box, textvariable=self.installment_var, justify="left", anchor="w", bg="#EDE6F8", fg=TEXT, font=("Segoe UI", 9)).pack(fill="x", padx=12, pady=(0, 9))

    def _refresh_home_dashboard(self) -> None:
        data = home_dashboard(self.items, self.results)
        self.home_vars["income"].set(f"{data['income']:.2f} zł")
        self.home_vars["expenses"].set(f"{data['expenses']:.2f} zł")
        self.home_vars["paid"].set(f"{data['paid']:.2f} zł")
        self.home_vars["remaining"].set(f"{data['remaining']:.2f} zł")
        self.home_vars["installments"].set(f"{data['installment_monthly']:.2f} zł")
        self.home_vars["balance"].set(f"{data['balance_plan']:+.2f} zł")
        self.progress["value"] = data["progress"]
        self.progress_label.set(
            f"Realizacja miesiąca: {data['progress']:.1f}% | Do sprawdzenia: {data['review']:.2f} zł | Brak: {data['missing']:.2f} zł"
        )

        review_count = sum(row.get("status") == "DO SPRAWDZENIA" for row in self.results)
        self.review_quick.configure(text=f"Do zatwierdzenia ({review_count})")

        if data["attention"]:
            lines = []
            for row in data["attention"][:5]:
                marker = "●" if row["status"] == "BRAK" else "◆"
                label = "brak" if row["status"] == "BRAK" else "sprawdź"
                lines.append(f"{marker} {row['name']} — {row['amount']:.2f} zł ({label})")
            if len(data["attention"]) > 5:
                lines.append(f"… i jeszcze {len(data['attention']) - 5}")
            self.attention_var.set("\n".join(lines))
        else:
            self.attention_var.set("✓ Wszystkie pozycje są rozliczone lub nie wymagają decyzji.")

        if data["upcoming"]:
            lines = []
            for row in data["upcoming"][:5]:
                left = "? rat" if row["months_left"] is None else f"{row['months_left']} rat"
                lines.append(
                    f"{row['payment_day']:02d}. dzień • {row['name']} • {row['monthly']:.2f} zł • {left}"
                )
            self.installment_var.set("\n".join(lines))
        else:
            self.installment_var.set("Brak aktywnych rat.")

    def _compare(self) -> None:
        super()._compare()
        self._refresh_home_dashboard()

    def _restore_state(self, state: dict) -> None:
        super()._restore_state(state)
        if hasattr(self, "home_vars"):
            self._refresh_home_dashboard()

    def _sync_manual_installments(self) -> None:
        super()._sync_manual_installments()
        if hasattr(self, "home_vars"):
            self._refresh_home_dashboard()

    def _approve_selected(self) -> None:
        super()._approve_selected()
        self._refresh_home_dashboard()

    def _reject_selected(self) -> None:
        super()._reject_selected()
        self._refresh_home_dashboard()

    def _undo_selected(self) -> None:
        super()._undo_selected()
        self._refresh_home_dashboard()


if __name__ == "__main__":
    PayCheck100App().mainloop()
