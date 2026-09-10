from __future__ import annotations

from pathlib import Path

from io_files import load_bank_statement
from matcher import normalize_text, parse_amount, parse_date


def _transaction_key(tx: dict) -> tuple:
    tx_date = parse_date(tx.get("date"))
    amount = parse_amount(tx.get("amount"))
    return (
        tx_date.isoformat() if tx_date else str(tx.get("date", "")),
        round(abs(amount), 2) if amount is not None else None,
        normalize_text(tx.get("counterparty")),
        normalize_text(tx.get("title") or tx.get("description")),
    )


def load_bank_statements(paths: list[str]) -> tuple[list[dict], dict]:
    merged: list[dict] = []
    seen: set[tuple] = set()
    duplicates = 0
    per_file: list[tuple[str, int]] = []

    for raw_path in paths:
        rows = load_bank_statement(raw_path)
        accepted = 0
        for tx in rows:
            row = dict(tx)
            row["source_file"] = Path(raw_path).name
            key = _transaction_key(row)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            merged.append(row)
            accepted += 1
        per_file.append((Path(raw_path).name, accepted))

    return merged, {
        "files": len(paths),
        "transactions": len(merged),
        "duplicates": duplicates,
        "per_file": per_file,
    }
