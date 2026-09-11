from __future__ import annotations

import base64
import json
import tkinter as tk
import uuid
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from license_340 import PRODUCT, canonical_payload


def _b64e(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def load_private_key(path: str) -> Ed25519PrivateKey:
    raw = Path(path).read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("To nie jest prywatny klucz Ed25519 PayCheck.")
    return key


def make_license_key(private_key: Ed25519PrivateKey, payload: dict) -> str:
    raw = canonical_payload(payload)
    signature = private_key.sign(raw)
    return f"{_b64e(raw)}.{_b64e(signature)}"


class OwnerKeygen(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PayCheck Owner Keygen — Edwin K.")
        self.geometry("760x650")
        self.minsize(680, 590)
        self.private_key_path = tk.StringVar()
        self.customer = tk.StringVar()
        self.license_type = tk.StringVar(value="HOME")
        self.expires = tk.StringVar()
        self.machine = tk.StringVar()
        self.features = tk.StringVar(value="all")
        self.output = tk.StringVar()
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        ttk.Label(root, text="PayCheck — Owner Keygen", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(
            root,
            text="Narzędzie właściciela: Edwin K. Klucz prywatny trzymaj poza repozytorium i poza komputerem klienta.",
            wraplength=700,
        ).pack(anchor="w", pady=(3, 14))

        form = ttk.LabelFrame(root, text="Licencja", padding=12)
        form.pack(fill="x")

        self._row(form, 0, "Klucz prywatny", self.private_key_path, browse=True)
        self._row(form, 1, "Klient / właściciel licencji", self.customer)

        ttk.Label(form, text="Typ licencji").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(
            form,
            textvariable=self.license_type,
            values=["HOME", "FAMILY", "PRO"],
            state="readonly",
            width=28,
        ).grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=5)

        self._row(form, 3, "Ważna do YYYY-MM-DD", self.expires)
        self._row(form, 4, "ID komputera (opcjonalnie)", self.machine)
        self._row(form, 5, "Funkcje", self.features)
        form.columnconfigure(1, weight=1)

        ttk.Label(
            root,
            text=(
                "Puste pole daty = licencja bezterminowa. Puste ID komputera = licencja nieprzypisana do urządzenia. "
                "Jeśli klient poda ID z PayCheck, wpisz je tutaj."
            ),
            wraplength=700,
        ).pack(anchor="w", pady=(10, 8))

        actions = ttk.Frame(root)
        actions.pack(fill="x")
        ttk.Button(actions, text="Generuj licencję", command=self._generate).pack(side="left")
        ttk.Button(actions, text="Kopiuj klucz", command=self._copy).pack(side="left", padx=7)
        ttk.Button(actions, text="Zapisz .pcl", command=self._save).pack(side="left")

        box = ttk.LabelFrame(root, text="Klucz licencyjny", padding=8)
        box.pack(fill="both", expand=True, pady=(12, 0))
        self.text = tk.Text(box, wrap="word", height=12, font=("Consolas", 9))
        self.text.pack(fill="both", expand=True)

    def _row(self, parent, row: int, label: str, variable: tk.StringVar, browse: bool = False) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
        ttk.Entry(frame, textvariable=variable).pack(side="left", fill="x", expand=True)
        if browse:
            ttk.Button(frame, text="Wybierz", command=self._choose_private_key).pack(side="left", padx=(6, 0))

    def _choose_private_key(self) -> None:
        path = filedialog.askopenfilename(
            title="Wybierz prywatny klucz właściciela",
            filetypes=[("PEM", "*.pem"), ("Wszystkie pliki", "*.*")],
        )
        if path:
            self.private_key_path.set(path)

    def _payload(self) -> dict:
        customer = self.customer.get().strip()
        if not customer:
            raise ValueError("Podaj klienta / właściciela licencji.")
        expires = self.expires.get().strip()
        if expires:
            date.fromisoformat(expires)
        return {
            "product": PRODUCT,
            "license_id": "LIC-" + uuid.uuid4().hex[:12].upper(),
            "customer": customer,
            "type": self.license_type.get().strip() or "HOME",
            "issued": date.today().isoformat(),
            "expires": expires,
            "machine_id": self.machine.get().strip(),
            "features": self.features.get().strip() or "all",
            "issuer": "Edwin K.",
        }

    def _generate(self) -> None:
        try:
            key_path = self.private_key_path.get().strip()
            if not key_path:
                raise ValueError("Wybierz prywatny klucz właściciela.")
            private_key = load_private_key(key_path)
            payload = self._payload()
            key_text = make_license_key(private_key, payload)
        except Exception as exc:
            messagebox.showerror("Keygen", str(exc), parent=self)
            return
        self.output.set(key_text)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", key_text)

    def _copy(self) -> None:
        value = self.text.get("1.0", "end").strip()
        if not value:
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        messagebox.showinfo("Keygen", "Klucz skopiowany do schowka.", parent=self)

    def _save(self) -> None:
        value = self.text.get("1.0", "end").strip()
        if not value:
            messagebox.showinfo("Keygen", "Najpierw wygeneruj licencję.", parent=self)
            return
        path = filedialog.asksaveasfilename(
            title="Zapisz licencję PayCheck",
            defaultextension=".pcl",
            filetypes=[("PayCheck License", "*.pcl"), ("Plik tekstowy", "*.txt")],
            initialfile="PayCheck_License.pcl",
        )
        if not path:
            return
        Path(path).write_text(value, encoding="utf-8")
        messagebox.showinfo("Keygen", f"Zapisano:\n{path}", parent=self)


if __name__ == "__main__":
    OwnerKeygen().mainloop()
