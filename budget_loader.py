from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


SUMMARY_PREFIXES = (
    "suma ",
    "koszt mies",
    "reszta",
    "saldo po",
    "dlug u",
    "dług u",
)

INCOME_PREFIXES = (
    "800+",
    "kasa dodatkowa",
    "wyplata",
    "wypłata",
    "pieniadze od",
    "pieniądze od",
)

BANK_NAMES = ("mbank", "santander", "alior", "velo", "pekao", "pko", "ing", "millennium")


def list_budget_sheets(path: str | Path) -> list[str]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _is_budget_sheet(ws) -> bool:
    headers = [str(ws.cell(1, col).value or "").strip().lower() for col in range(1, 5)]
    return (
        len(headers) >= 4
        and headers[1] == "instytucja"
        and headers[2] == "suma"
        and headers[3] == "miesiecznie"
    )


def _category(name: str, institution: str, entry_type: str) -> str:
    if entry_type == "income":
        return "Wpływy"

    text = f"{institution} {name}".lower()
    if any(bank in text for bank in BANK_NAMES):
        return "Raty / banki"
    if any(word in text for word in ("gaz", "prąd", "prad", "woda", "śmieci", "smieci", "internet", "telefon")):
        return "Dom i rachunki"
    if any(word in text for word in ("disney", "spotify", "spotyfly", "player", "1password", "subskrypc")):
        return "Subskrypcje"
    if any(word in text for word in ("audi", "lublin", "punto", "paliwo", "przegląd", "przeglad", "oc aut", "naprawa auta")):
        return "Samochody"
    if "ubezpiec" in text:
        return "Ubezpieczenia"
    if any(word in text for word in ("wakacje", "odkład", "odklad")):
        return "Oszczędności"
    if any(word in text for word in ("podatek", "grunt")):
        return "Podatki"
    return "Pozostałe"


def _bank_name(institution: str) -> str:
    text = institution.strip().lower()
    aliases = {
        "mbank": "mBank",
        "santander": "Santander",
        "alior": "Alior",
        "velo": "Velo",
        "velo bank": "Velo",
        "pekao": "Pekao",
        "pko": "PKO",
        "ing": "ING",
        "millennium": "Millennium",
    }
    for token, label in aliases.items():
        if token in text:
            return label
    return institution.strip()


def load_budget_sheet(path: str | Path, sheet_name: str) -> list[dict]:
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"Nie ma arkusza: {sheet_name}")
        ws = wb[sheet_name]
        if not _is_budget_sheet(ws):
            raise ValueError(
                "Wybrany arkusz nie ma układu budżetu: instytucja / Suma / Miesiecznie."
            )

        items: list[dict] = []
        for row_no, row in enumerate(ws.iter_rows(min_row=2, max_col=4, values_only=True), start=2):
            end_date, institution, name, monthly = row
            name_text = str(name or "").strip()
            if not name_text or not isinstance(monthly, (int, float)) or monthly <= 0:
                continue

            normalized = " ".join(name_text.lower().split())
            if any(normalized.startswith(prefix) for prefix in SUMMARY_PREFIXES):
                continue

            entry_type = "income" if any(normalized.startswith(prefix) for prefix in INCOME_PREFIXES) else "expense"
            institution_text = str(institution or "").strip()
            category = _category(name_text, institution_text, entry_type)
            bank = _bank_name(institution_text) if category == "Raty / banki" else ""
            search_name = " ".join(part for part in (institution_text, name_text) if part)

            items.append(
                {
                    "invoice_no": f"BUD-{row_no}",
                    "counterparty": search_name or name_text,
                    "display_name": name_text,
                    "institution": institution_text,
                    "amount": float(monthly),
                    "date": "",
                    "end_date": end_date if end_date else "",
                    "source_type": "budget",
                    "source_sheet": sheet_name,
                    "source_row": row_no,
                    "entry_type": entry_type,
                    "category": category,
                    "bank": bank,
                }
            )

        if not items:
            raise ValueError("W wybranym arkuszu nie znaleziono pozycji budżetowych do porównania.")
        return items
    finally:
        wb.close()
