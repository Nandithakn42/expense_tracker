"""Persistence layer: JSON storage (atomic writes) and CSV export."""

import csv
import json
import os
import tempfile
from pathlib import Path

from exceptions import CorruptDataError, StorageError
from models import Expense

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "expenses.json"
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def load(path=DEFAULT_PATH):
    """Return (expenses, budget). A missing file is fine; a corrupt one is backed up."""
    path = Path(path)
    if not path.exists():
        return [], None
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        expenses = [Expense.from_dict(item) for item in raw["expenses"]]
        budget = raw.get("budget")
        if budget is not None:
            budget = float(budget)
    except OSError as exc:
        raise StorageError(f"Could not read {path}: {exc}") from exc
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        _quarantine(path, exc)  # always raises
    return expenses, budget


def _quarantine(path: Path, cause: Exception):
    """Move an unreadable data file aside so it is never silently overwritten."""
    backup = path.with_name(f"{path.stem}.corrupt{path.suffix}")
    try:
        os.replace(path, backup)
    except OSError as exc:
        raise StorageError(f"{path.name} is corrupted and could not be backed up: {exc}") from cause
    raise CorruptDataError(
        f"{path.name} was unreadable ({cause}). Saved as {backup.name}; starting with a fresh file."
    ) from cause


def save(expenses, budget, path=DEFAULT_PATH) -> None:
    """Write data atomically: temp file first, then replace, so a crash can't corrupt it."""
    path = Path(path)
    payload = {"budget": budget, "expenses": [e.to_dict() for e in expenses]}
    tmp_path = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    except (OSError, TypeError, ValueError) as exc:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise StorageError(f"Could not save data to {path}: {exc}") from exc


def _safe_cell(text: str) -> str:
    """Stop spreadsheet apps from running text like '=1+1' as a formula."""
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def export_csv(expenses, path) -> int:
    """Write expenses to a CSV file. Returns the number of rows written."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "date", "category", "description", "amount"])
            for e in expenses:
                writer.writerow(
                    [e.id, e.date, _safe_cell(e.category), _safe_cell(e.description), f"{e.amount:.2f}"]
                )
    except OSError as exc:
        raise StorageError(f"Could not write {path}: {exc}") from exc
    return len(expenses)
