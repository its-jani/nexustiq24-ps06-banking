import csv
import io
from datetime import datetime

from app.models import Transaction

REQUIRED_COLUMNS = ["date", "description", "payee", "amount", "channel"]

_DATE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
)


class IngestionError(ValueError):
    """Raised when the CSV cannot be parsed. Message lists offending rows."""


def parse_csv(source: io.IOBase | str) -> list[Transaction]:
    """Parse + validate a transaction CSV into Transactions, keeping 1-based rows.

    Required columns: date, description, payee, amount, channel (case-insensitive,
    extra columns ignored). Blank lines are skipped. Any structurally invalid row
    fails the whole ingestion with the offending row numbers listed — silently
    dropping rows from a fraud investigation would be worse than failing loudly.
    """
    if isinstance(source, str):
        source = io.StringIO(source)
    reader = csv.reader(source)
    try:
        header = next(reader)
    except StopIteration:
        raise IngestionError("CSV is empty (no header row).")

    header = [h.strip().lower() for h in header]
    seen = set()
    col_idx = {}
    for name in REQUIRED_COLUMNS:
        if name in header:
            col_idx[name] = header.index(name)
            seen.add(header.index(name))
    missing = [c for c in REQUIRED_COLUMNS if c not in col_idx]
    if missing:
        raise IngestionError(
            f"Missing required column(s): {', '.join(missing)}. "
            f"Found columns: {header or '(none)'}."
        )

    txs: list[Transaction] = []
    errors: list[str] = []
    for row_num, raw in enumerate(reader, start=2):
        if not any(field.strip() for field in raw):  # skip blank lines
            continue
        if not raw or max(col_idx.values()) >= len(raw):
            errors.append(f"row {row_num}: truncated row")
            continue

        when = _parse_date(raw[col_idx["date"]].strip(), row_num, errors)
        amount = _parse_amount(raw[col_idx["amount"]].strip(), row_num, errors)
        if when is None or amount is None:
            continue

        txs.append(Transaction(
            row=row_num,
            date=when,
            description=raw[col_idx["description"]].strip(),
            payee=raw[col_idx["payee"]].strip(),
            amount=amount,
            channel=raw[col_idx["channel"]].strip(),
        ))

    if errors:
        raise IngestionError("Invalid transaction data: " + "; ".join(errors))
    if not txs:
        raise IngestionError("CSV contains no transaction rows.")

    txs.sort(key=lambda t: t.date)
    return txs


def _parse_date(raw: str, row_num: int, errors: list[str]) -> datetime | None:
    if not raw:
        errors.append(f"row {row_num}: date is empty")
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    errors.append(f"row {row_num}: unparseable date '{raw}'")
    return None


def _parse_amount(raw: str, row_num: int, errors: list[str]) -> float | None:
    if not raw:
        errors.append(f"row {row_num}: amount is empty")
        return None
    # tolerate thousand separators and a leading $ sign
    cleaned = raw.strip().replace(",", "").lstrip("$")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        errors.append(f"row {row_num}: amount '{raw}' is not a number")
        return None