from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from app_330 import PayCheck330App
from license_340 import OWNER_LABEL, install_license_key, license_status, machine_id


class LicenseWindow(tk.Toplevel):
    def __init__(self, app: "PayCheck340App") -> None:
        super().__init__(app)
        self.app = app
        self.title("PayCheck — Licencja")
        self.geometry("720x520")
        self.resizable(False, False)

        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="Licencja PayCheck", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(root, text=f"Właściciel programu: {OWNER_LABEL}").pack(anchor="w", pady=(2, 12))

        self.status_var = tk.StringVar()
        status_box = ttk.LabelFrame(root, text="Status", padding=12)
        status_box.pack(fill="x")
        ttk.Label(status_box, textvariable=self.status_var, font=("Segoe UI", 12, "bold"), wraplength=640).pack(anchor="w")

        machine_box = ttk.LabelFrame(root, text="ID tego komputera", padding=12)
        machine_box.pack(fill="x", pady=(12, 0))
        self.machine_var = tk.StringVar(value=machine_id())
        ttk.Entry(machine_box, textvariable=self.machine_var, state="readonly", font=("Consolas", 10)).pack(side="left", fill="x", expand=True)
        ttk.Button(machine_box, text="Kopiuj", command=self._copy_machine).pack(side="left", padx=(8, 0))
        ttk.Label(
            root,
            text="Jeśli licencja ma być przypisana do urządzenia, wyślij ten identyfikator sprzedawcy przed wygenerowaniem klucza.",
            wraplength=670,
        ).pack(anchor="w", pady=(6, 12))

        actions = ttk.LabelFrame(root, text="Aktywacja", padding=12)
        actions.pack(fill="x")
        ttk.Button(actions, text="Wklej klucz licencyjny", command=self._paste_key).pack(side="left")
        ttk.Button(actions, text="Wczytaj plik .pcl", command=self._load_file).pack(side="left", padx=8)

        ttk.Label(
            root,
            text=(
                "PayCheck działa przez 7 dni w trybie próbnym. Po wygaśnięciu triala dane pozostają na komputerze, "
                "ale operacje zmieniające dane wymagają aktywnej licencji."
            ),
            wraplength=670,
        ).pack(anchor="w", pady=(14, 0))
        self.refresh()

    def refresh(self) -> None:
        status = license_status()
        if status["mode"] == "licensed":
            lic = status.get("license") or {}
            expiry = lic.get("expires") or "bezterminowo"
            device = "przypisana do urządzenia" if lic.get("machine_id") else "bez przypisania do urządzenia"
            self.status_var.set(
                f"AKTYWNA — {lic.get('type', 'HOME')}\n"
                f"Klient: {lic.get('customer', '—')}\n"
                f"Ważna do: {expiry}\n"
                f"Licencja: {lic.get('license_id', '—')} — {device}"
            )
        elif status["mode"] == "trial":
            self.status_var.set(
                f"TRIAL — pozostało {status.get('days_left', 0)} dni\n"
                f"Koniec triala: {status.get('trial_end', '—')}"
            )
        else:
            self.status_var.set("TRIAL WYGASŁ — tryb tylko do odczytu. Wprowadź licencję, aby ponownie włączyć zapis.")

    def _copy_machine(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.machine_var.get())
        messagebox.showinfo("Licencja", "ID komputera skopiowane do schowka.", parent=self)

    def _activate(self, key_text: str) -> None:
        try:
            payload = install_license_key(key_text)
        except Exception as exc:
            messagebox.showerror("Licencja", str(exc), parent=self)
            return
        messagebox.showinfo(
            "Licencja",
            f"Aktywowano PayCheck dla: {payload.get('customer', '—')}\nTyp: {payload.get('type', 'HOME')}",
            parent=self,
        )
        self.app._refresh_license_state()
        self.refresh()

    def _paste_key(self) -> None:
        value = simpledialog.askstring("Aktywacja", "Wklej klucz licencyjny:", parent=self)
        if value:
            self._activate(value)

    def _load_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Wybierz licencję PayCheck",
            filetypes=[("PayCheck License", "*.pcl"), ("Plik tekstowy", "*.txt"), ("Wszystkie", "*.*")],
        )
        if not path:
            return
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            messagebox.showerror("Licencja", str(exc), parent=self)
            return
        self._activate(value)


class PayCheck340App(PayCheck330App):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck 3.4.0 — Domowy system finansów offline")
        self._license_state = license_status()
        self._build_license_footer()
        self._extend_license_menu()
        self._refresh_license_state()
        if self._license_state["mode"] == "readonly":
            self.after(350, self._show_trial_expired)

    def _build_license_footer(self) -> None:
        self.license_footer = tk.StringVar()
        footer = ttk.Frame(self)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, text="PayCheck © Edwin K. — właściciel", font=("Segoe UI", 8, "bold")).pack(side="left", padx=10, pady=4)
        ttk.Label(footer, textvariable=self.license_footer, font=("Segoe UI", 8)).pack(side="right", padx=10, pady=4)

    def _extend_license_menu(self) -> None:
        menu = self.nametowidget(self.cget("menu"))
        license_menu = tk.Menu(menu, tearoff=False)
        license_menu.add_command(label="Status / aktywacja licencji", command=self._show_license)
        license_menu.add_command(label="Pokaż ID komputera", command=self._show_machine_id)
        menu.add_cascade(label="Licencja", menu=license_menu)

    def _show_license(self) -> None:
        LicenseWindow(self)

    def _show_machine_id(self) -> None:
        value = machine_id()
        self.clipboard_clear()
        self.clipboard_append(value)
        messagebox.showinfo("ID komputera", f"{value}\n\nID zostało skopiowane do schowka.")

    def _refresh_license_state(self) -> None:
        self._license_state = license_status()
        self.license_footer.set(self._license_state.get("label", ""))
        if self._license_state["mode"] == "readonly":
            self.title("PayCheck 3.4.0 — TRYB TYLKO DO ODCZYTU")
        else:
            self.title("PayCheck 3.4.0 — Domowy system finansów offline")

    def _write_allowed(self, action: str = "tej operacji") -> bool:
        self._refresh_license_state()
        if self._license_state.get("write_allowed"):
            return True
        messagebox.showwarning(
            "Wymagana licencja",
            f"Trial PayCheck wygasł. Do wykonania {action} potrzebna jest aktywna licencja.\n\n"
            "Twoje dane nie zostały usunięte — program działa w trybie tylko do odczytu.",
        )
        return False

    def _show_trial_expired(self) -> None:
        messagebox.showinfo(
            "PayCheck — koniec triala",
            "7-dniowy okres próbny zakończył się. Dane pozostają dostępne do podglądu, ale zapis nowych zmian wymaga licencji.",
        )
        self._show_license()

    # Główne punkty zapisu blokowane po trialu. Odczyt, raporty i historia pozostają dostępne.
    def _add_statements(self) -> None:
        if self._write_allowed("importu nowego wyciągu"):
            super()._add_statements()

    def _choose_budget(self) -> None:
        if self._write_allowed("wczytania / utworzenia nowego miesiąca"):
            super()._choose_budget()

    def _approve_selected(self) -> None:
        if self._write_allowed("zatwierdzenia płatności"):
            super()._approve_selected()

    def _reject_selected(self) -> None:
        if self._write_allowed("odrzucenia dopasowania"):
            super()._reject_selected()

    def _undo_selected(self) -> None:
        if self._write_allowed("cofnięcia decyzji"):
            super()._undo_selected()

    def _run_allocations_quick(self) -> None:
        if self._write_allowed("miesięcznego odkładania"):
            super()._run_allocations_quick()

    def _learn_bank_file(self) -> None:
        if self._write_allowed("zapisu nowego profilu bankowego"):
            super()._learn_bank_file()


if __name__ == "__main__":
    PayCheck340App().mainloop()
