from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


_MT940_AMOUNT = re.compile(r"^:61:(\d{6})(?:\d{4})?([CD])([0-9,]+)")


def _decode_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Nie udało się odczytać pliku MT940/STA.")


def _date_yyMMdd(value: str) -> str:
    parsed = datetime.strptime(value, "%y%m%d")
    return parsed.strftime("%d.%m.%Y")


def _clean_description(value: str) -> str:
    value = value.replace("?00", " ").replace("?20", " ").replace("?21", " ")
    value = value.replace("?22", " ").replace("?23", " ").replace("?24", " ")
    value = re.sub(r"\?\d{2}", " ", value)
    return " ".join(value.split()).strip()


def _counterparty_from_86(value: str) -> str:
    cleaned = _clean_description(value)
    for marker in ("NAZWA KONTRAHENTA", "KONTRAHENT", "ODBIORCA", "NADAWCA"):
        pos = cleaned.upper().find(marker)
        if pos >= 0:
            tail = cleaned[pos + len(marker):].lstrip(" :;-")
            if tail:
                return tail[:120]
    return cleaned[:120]


def parse_mt940(path: str | Path) -> list[dict]:
    lines = [line.rstrip() for line in _decode_text(path).splitlines()]
    transactions: list[dict] = []
    current: dict | None = None
    for line in lines:
        match = _MT940_AMOUNT.match(line)
        if match:
            if current:
                transactions.append(current)
            amount = float(match.group(3).replace(",", "."))
            if match.group(2) == "D":
                amount = -amount
            current = {
                "date": _date_yyMMdd(match.group(1)),
                "amount": amount,
                "counterparty": "",
                "title": "",
                "description": "",
                "source": "MT940",
            }
            continue
        if current is not None and line.startswith(":86:"):
            description = line[4:].strip()
            current["description"] = _clean_description(description)
            current["title"] = current["description"]
            current["counterparty"] = _counterparty_from_86(description)
        elif current is not None and line and not line.startswith(":"):
            current["description"] = _clean_description(
                (current.get("description", "") + " " + line).strip()
            )
            current["title"] = current["description"]
            if not current.get("counterparty"):
                current["counterparty"] = _counterparty_from_86(current["description"])
    if current:
        transactions.append(current)
    transactions = [row for row in transactions if row.get("amount") is not None]
    if not transactions:
        raise ValueError("Nie znaleziono transakcji w pliku MT940/STA.")
    return transactions
