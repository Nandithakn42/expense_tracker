"""Data model for a single expense."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Expense:
    id: int
    amount: float
    category: str
    description: str
    date: str  # ISO format: YYYY-MM-DD

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Expense":
        """Build an Expense from a stored record, rejecting malformed data."""
        try:
            return cls(
                id=int(data["id"]),
                amount=float(data["amount"]),
                category=str(data["category"]),
                description=str(data.get("description", "")),
                date=str(data["date"]),
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"Malformed expense record: {data!r}") from exc
