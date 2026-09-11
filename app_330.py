from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from app_100 import BLUE, GREEN, ORANGE, TEAL
from app_320 import PayCheck320App
from bank_merge import load_bank_statements
from bank_profiles_330 import (
    all_profiles,
    import_table_with_profile,
    profile_summary,
    read_table_preview,
    save_learned_profile,
)
from month_state import merge_transactions


class BankProfileWizard(tk.Toplevel):
    FIELDS = (
        ("date", "Data operacji *"),
        ("amount", "Kwota *"),
        ("counterparty", "Kontrahent"),
        ("title", "Tytuł / opis"),
        ("type", "Typ operacji"),
        ("balance", "Saldo"),
        ("currency", "Waluta"),
    )

    def __init__(self, app: "PayCheck330App", path: str, on_saved) -> None:
        super().__init__(app)
        self.app = app
        self.path = path
        self.on_saved = on_saved
        self.title("Naucz PayCheck układu wyciągu")
        self.geometry("980x700")
        self.minsize(820, 600)

        headers, rows = read_table_preview(path)
        self.headers = headers
        self.rows = rows
        self.mapping_vars: dict[str, tk.StringVar] = {}

        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Naucz PayCheck tego wyciągu", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                "Wskaż znaczenie kolumn. Profil zostanie zapisany tylko lokalnie na tym komputerze. "
                "Pola oznaczone * są wymagane."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(3, 12))

        form = ttk.LabelFrame(root, text="Mapowanie kolumn", padding=10)
        form.pack(fill="x")
        for row_index, (key, label) in enumerate(self.FIELDS):
            ttk.Label(form, text=label).grid(row=row_index, column=0, sticky="w", pady=4)
            var = tk.StringVar(value="")
            self.mapping_vars[key] = var
            box = ttk.Combobox(form, textvariable=var, values=[""] + headers, state="readonly", width=48)
            box.grid(row=row_index, column=1, sticky="ew", padx=(12, 0), pady=4)
        form.columnconfigure(1, weight=1)

        preview_box = ttk.LabelFrame(root, text="Podgląd pierwszych wierszy", padding=8)
        preview_box.pack(fill="both", expand=True, pady=(12, 0))
        display_headers = headers[:8]
        self.preview = ttk.Treeview(preview_box, columns=display_headers, show="headings", height=8)
        for header in display_headers:
            self.preview.heading(header, text=header)
            self.preview.column(header, width=140, anchor="w")
        for raw in rows[:10]:
            self.preview.insert("", "end", values=[raw[i] if i < len(raw) else "" for i in range(len(display_headers))])
        self.preview.pack(fill="both", expand=True)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=(12, 0))
        ttk.Button(actions, text="Zapisz profil i importuj", command=self._save).pack(side="right")
        ttk.Button(actions, text="Anuluj", command=self.destroy).pack(side="right", padx=(0, 8))

    def _save(self) -> None:
        mapping = {key: var.get().strip() for key, var in self.mapping_vars.items() if var.get().strip()}
        if not mapping.get("date") or not mapping.get("amount"):
            messagebox.showwarning("Profil banku", "Wskaż kolumnę daty i kwoty.", parent=self)
            return
        default_name = f"{Path(self.path).stem} — mój układ"
        name = simpledialog.askstring("Profil banku", "Nazwa profilu:", initialvalue=default_name, parent=self)
        if not name:
            return
        bank = simpledialog.askstring("Profil banku", "Nazwa banku (opcjonalnie):", initialvalue="Mój bank", parent=self) or "Mój bank"
        try:
            profile = save_learned_profile(name, mapping, bank)
        except Exception as exc:
            messagebox.showerror("Profil banku", str(exc), parent=self)
            return
        self.destroy()
        self.on_saved(profile)


class BankProfilesWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck330App") -> None:
        super().__init__(app)
        self.app = app
        self.title("Profile banków")
        self.geometry("900x560")
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Profile banków", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Profile wbudowane są punktem startowym. Własne profile powstają po nauczeniu PayCheck układu CSV/XLSX.",
            wraplength=840,
        ).pack(anchor="w", pady=(2, 10))
        self.tree = ttk.Treeview(root, columns=("name", "bank", "type"), show="headings")
        self.tree.heading("name", text="Profil")
        self.tree.heading("bank", text="Bank")
        self.tree.heading("type", text="Rodzaj")
        self.tree.column("name", width=420)
        self.tree.column("bank", width=200)
        self.tree.column("type", width=140)
        for row in all_profiles():
            kind = "Wbudowany" if str(row.get("id", "")).startswith("builtin-") else "Nauczony lokalnie"
            self.tree.insert("", "end", values=(row.get("name", ""), row.get("bank", ""), kind))
        self.tree.pack(fill="both", expand=True)


class BankImportPreview(tk.Toplevel):
    def __init__(self, app: "PayCheck330App", rows: list[dict], info: dict, accept) -> None:
        super().__init__(app)
        self.rows = rows
        self.accept = accept
        self.title("Podgląd importu bankowego")
        self.geometry("1180x650")
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        profile = info.get("profile") or {}
        ttk.Label(root, text="Podgląd importu", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text=(
                f"Profil: {profile.get('name', '—')} | Pewność rozpoznania: {info.get('confidence', 0)}% | "
                f"Operacje: {len(rows)}"
            ),
        ).pack(anchor="w", pady=(2, 10))

        tree = ttk.Treeview(root, columns=("date", "amount", "party", "title", "type", "internal"), show="headings")
        for key, label, width in (
            ("date", "Data", 110), ("amount", "Kwota", 110), ("party", "Kontrahent", 220),
            ("title", "Opis", 390), ("type", "Typ", 150), ("internal", "Własny", 80),
        ):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        for row in rows[:100]:
            tree.insert("", "end", values=(
                row.get("date", ""), row.get("amount", ""), row.get("counterparty", ""),
                row.get("title", ""), row.get("payment_type", ""),
                "TAK" if row.get("is_internal_transfer") else "",
            ))
        tree.pack(fill="both", expand=True)
        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Button(bar, text="Importuj", command=self._accept).pack(side="right")
        ttk.Button(bar, text="Anuluj", command=self.destroy).pack(side="right", padx=(0, 8))

    def _accept(self) -> None:
        self.destroy()
        self.accept(self.rows)


class PayCheck330App(PayCheck320App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 3.3.0 — Domowy system finansów offline")
        self._extend_bank_profile_menu()

    def _extend_bank_profile_menu(self) -> None:
        menu = self.nametowidget(self.cget("menu"))
        bank = tk.Menu(menu, tearoff=False)
        bank.add_command(label="Profile banków", command=lambda: BankProfilesWindow(self))
        bank.add_command(label="Naucz układu pliku CSV/XLSX", command=self._learn_bank_file)
        menu.add_cascade(label="Banki", menu=bank)

    def _learn_bank_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz przykładowy wyciąg CSV/XLSX",
            filetypes=[("CSV / Excel", "*.csv *.xlsx"), ("CSV", "*.csv"), ("Excel", "*.xlsx")],
        )
        if not path:
            return
        BankProfileWizard(self, path, lambda _profile: messagebox.showinfo("Profil banku", "Profil zapisany. Następny taki plik zostanie rozpoznany automatycznie."))

    def _commit_bank_rows(self, rows: list[dict], paths: list[str]) -> None:
        self.transactions, added = merge_transactions(self.transactions, rows)
        for path in paths:
            name = Path(path).name
            if name not in self.statement_files:
                self.statement_files.append(name)
        self.bank_info_var.set(
            f"{self.budget_sheet}: {len(self.statement_files)} plików wyciągów, "
            f"{len(self.transactions)} unikalnych operacji | nowo dodane: {added}"
        )
        if self.transactions:
            self._compare()
        else:
            self._save_current_month()
        self._update_month_header(new_transactions=added)

    def _import_profiled_file(self, path: str, rest_paths: list[str]) -> None:
        try:
            rows, info = import_table_with_profile(path)
        except ValueError:
            BankProfileWizard(
                self,
                path,
                lambda profile: self._import_after_learning(path, profile, rest_paths),
            )
            return
        BankImportPreview(
            self,
            rows,
            info,
            lambda accepted: self._finish_mixed_import(accepted, [path], rest_paths),
        )

    def _import_after_learning(self, path: str, profile: dict, rest_paths: list[str]) -> None:
        try:
            rows, info = import_table_with_profile(path, profile)
        except Exception as exc:
            messagebox.showerror("Import bankowy", str(exc))
            return
        BankImportPreview(
            self,
            rows,
            info,
            lambda accepted: self._finish_mixed_import(accepted, [path], rest_paths),
        )

    def _finish_mixed_import(self, first_rows: list[dict], first_paths: list[str], rest_paths: list[str]) -> None:
        combined = list(first_rows)
        used_paths = list(first_paths)
        if rest_paths:
            try:
                more, _info = load_bank_statements(rest_paths)
            except Exception as exc:
                messagebox.showerror("Import bankowy", str(exc))
                return
            combined.extend(more)
            used_paths.extend(rest_paths)
        self._commit_bank_rows(combined, used_paths)

    def _add_statements(self) -> None:
        if self.source_mode != "budget" or not self.items or not self.budget_sheet:
            messagebox.showinfo("Miesiąc", "Najpierw wczytaj budżet i wybierz miesiąc.")
            return
        paths = list(filedialog.askopenfilenames(
            title=f"Dodaj wyciągi do {self.budget_sheet}",
            filetypes=[
                ("Wyciągi bankowe", "*.xlsx *.csv *.pdf *.sta *.mt940 *.940 *.txt"),
                ("MT940 / STA", "*.sta *.mt940 *.940 *.txt"),
                ("PDF", "*.pdf"), ("Excel", "*.xlsx"), ("CSV", "*.csv"),
            ],
        ))
        if not paths:
            return

        first = paths[0]
        suffix = Path(first).suffix.lower()
        if suffix in {".csv", ".xlsx"}:
            try:
                summary = profile_summary(first)
            except Exception:
                summary = {"ready": False}
            if summary.get("ready"):
                self._import_profiled_file(first, paths[1:])
                return
            BankProfileWizard(
                self,
                first,
                lambda profile: self._import_after_learning(first, profile, paths[1:]),
            )
            return

        try:
            incoming, info = load_bank_statements(paths)
        except Exception as exc:
            messagebox.showerror("Błąd importu", str(exc))
            return
        self._commit_bank_rows(incoming, paths)


if __name__ == "__main__":
    PayCheck330App().mainloop()
