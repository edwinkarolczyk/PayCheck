from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook, load_workbook


INVOICE_ALIASES = {
    "counterparty": ("kontrahent", "odbiorca", "firma", "nazwa"),
    "amount": ("kwota", "do zaplaty", "do zapłaty", "wartosc", "wartość"),
    "date": ("termin", "data platnosci", "data płatności", "data"),
    "invoice_no": ("nr faktury", "numer faktury", "faktura", "numer"),
}

BANK_ALIASES = {
    "counterparty": ("odbiorca", "kontrahent", "nadawca", "nazwa", "opis kontrahenta"),
    "amount": ("kwota", "wartosc", "wartość", "kwota operacji"),
    "date": ("data operacji", "data ksiegowania", "data księgowania", "data"),
    "title": ("tytul", "tytuł", "opis", "tytul operacji", "tytuł operacji"),
}


def _normalize_header(value: object) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _map_headers(headers: list[object], aliases: dict[str, tuple[str, ...]]) -> dict[str, int]:
    normalized = [_normalize_header(h) for h in headers]
    mapping: dict[str, int] = {}
    for key, choices in aliases.items():
        for idx, header in enumerate(normalized):
            if header in choices:
                mapping[key] = idx
                break
    return mapping


def _rows_from_xlsx(path: str | Path) -> tuple[list[object], list[list[object]]]:
    wb = load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    iterator = ws.iter_rows(values_only=True)
    try:
        headers = list(next(iterator))
    except StopIteration:
        return [], []
    return headers, [list(row) for row in iterator]


def _rows_from_csv(path: str | Path) -> tuple[list[str], list[list[str]]]:
    raw = Path(path).read_bytes()
    text = None
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ValueError("Nie udało się odczytać kodowania pliku CSV.")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        rows = list(csv.reader(text.splitlines(), dialect))
    except csv.Error:
        rows = list(csv.reader(text.splitlines(), delimiter=";"))

    if not rows:
        return [], []
    return rows[0], rows[1:]


def _read_table(path: str | Path) -> tuple[list[object], list[list[object]]]:
    suffix = Path(path).suffix.lower()
    if suffix == ".xlsx":
        return _rows_from_xlsx(path)
    if suffix == ".csv":
        return _rows_from_csv(path)
    raise ValueError("Obsługiwane formaty: XLSX i CSV.")


def _convert_rows(
    headers: list[object],
    rows: Iterable[list[object]],
    aliases: dict[str, tuple[str, ...]],
    required: tuple[str, ...],
) -> list[dict]:
    mapping = _map_headers(headers, aliases)
    missing = [key for key in required if key not in mapping]
    if missing:
        raise ValueError("Brak wymaganych kolumn: " + ", ".join(missing))

    converted: list[dict] = []
    for row in rows:
        if not any(value not in (None, "") for value in row):
            continue
        item = {}
        for key, idx in mapping.items():
            item[key] = row[idx] if idx < len(row) else ""
        converted.append(item)
    return converted


def load_invoices(path: str | Path) -> list[dict]:
    headers, rows = _read_table(path)
    return _convert_rows(
        headers,
        rows,
        INVOICE_ALIASES,
        ("counterparty", "amount", "date"),
    )


def load_bank_statement(path: str | Path) -> list[dict]:
    headers, rows = _read_table(path)
    return _convert_rows(
        headers,
        rows,
        BANK_ALIASES,
        ("counterparty", "amount", "date"),
    )


def save_results(path: str | Path, results: list[dict]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Wynik"

    columns = [
        ("invoice_no", "Nr faktury"),
        ("counterparty", "Kontrahent"),
        ("date", "Termin"),
        ("amount", "Kwota z Excela"),
        ("status", "Status"),
        ("match_score", "Zgodność %"),
        ("bank_date", "Data z banku"),
        ("bank_amount", "Kwota z banku"),
        ("amount_diff", "Różnica kwoty"),
        ("days_diff", "Różnica dni"),
        ("bank_counterparty", "Kontrahent z banku"),
        ("bank_title", "Tytuł przelewu"),
    ]
    ws.append([label for _, label in columns])
    for result in results:
        ws.append([result.get(key, "") for key, _ in columns])

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for column_cells in ws.columns:
        width = min(
            45,
            max(12, max(len(str(cell.value or "")) for cell in column_cells) + 2),
        )
        ws.column_dimensions[column_cells[0].column_letter].width = width

    wb.save(path)
