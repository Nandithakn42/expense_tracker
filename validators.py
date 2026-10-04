"""Input validation. Every function returns a clean value or raises ValidationError."""

import math
import re
from datetime import date, datetime

from exceptions import ValidationError

MAX_AMOUNT = 10_000_000
MAX_CATEGORY_LEN = 30
MAX_DESCRIPTION_LEN = 100
CATEGORY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z &\-]*$")
DATE_FORMAT = "%Y-%m-%d"
MONTH_FORMAT = "%Y-%m"


def validate_amount(raw) -> float:
    """Positive number, at most 2 decimal places kept. Commas are allowed (1,250.50)."""
    text = str(raw).strip().replace(",", "")
    if not text:
        raise ValidationError("Amount cannot be empty.")
    try:
        amount = float(text)
    except ValueError:
        raise ValidationError(f"'{raw}' is not a valid number.") from None
    if math.isnan(amount) or math.isinf(amount):
        raise ValidationError("Amount must be a real number.")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if amount > MAX_AMOUNT:
        raise ValidationError(f"Amount cannot exceed {MAX_AMOUNT:,}.")
    return round(amount, 2)


def validate_category(raw) -> str:
    """Letters, spaces, '&' and '-' only. Normalised to Title Case."""
    text = " ".join(str(raw).split())
    if not text:
        raise ValidationError("Category cannot be empty.")
    if len(text) > MAX_CATEGORY_LEN:
        raise ValidationError(f"Category must be {MAX_CATEGORY_LEN} characters or fewer.")
    if not CATEGORY_PATTERN.match(text):
        raise ValidationError("Category may only contain letters, spaces, '&' and '-'.")
    return text.title()


def validate_description(raw) -> str:
    """Optional free text, printable characters only."""
    text = "" if raw is None else str(raw).strip()
    if len(text) > MAX_DESCRIPTION_LEN:
        raise ValidationError(f"Description must be {MAX_DESCRIPTION_LEN} characters or fewer.")
    if not text.isprintable():
        raise ValidationError("Description contains invalid characters.")
    return text


def validate_date(raw=None, allow_future: bool = False) -> str:
    """YYYY-MM-DD. Blank means today. Future dates are rejected by default."""
    text = "" if raw is None else str(raw).strip()
    if not text:
        return date.today().isoformat()
    try:
        parsed = datetime.strptime(text, DATE_FORMAT).date()
    except ValueError:
        raise ValidationError(
            f"'{text}' is not a valid date. Use YYYY-MM-DD (e.g. 2026-09-28)."
        ) from None
    if parsed > date.today() and not allow_future:
        raise ValidationError("Date cannot be in the future.")
    return parsed.isoformat()


def validate_month(raw) -> str:
    """YYYY-MM."""
    text = str(raw).strip()
    try:
        return datetime.strptime(text, MONTH_FORMAT).strftime(MONTH_FORMAT)
    except ValueError:
        raise ValidationError(f"'{text}' is not a valid month. Use YYYY-MM (e.g. 2026-09).") from None


def validate_id(raw) -> int:
    """Positive integer."""
    try:
        value = int(str(raw).strip())
    except ValueError:
        raise ValidationError(f"'{raw}' is not a valid ID. IDs are whole numbers.") from None
    if value <= 0:
        raise ValidationError("ID must be a positive number.")
    return value
