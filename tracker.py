"""Business logic. No printing or input() here, so it is easy to test and reuse."""

from collections import defaultdict
from dataclasses import replace
from datetime import date
from pathlib import Path

import storage
import validators as v
from exceptions import ExpenseNotFoundError, StorageError, ValidationError
from models import Expense

SORT_FIELDS = ("date", "amount", "category", "id")


class ExpenseTracker:
    def __init__(self, path=storage.DEFAULT_PATH):
        self.path = Path(path)
        self.expenses, self.budget = storage.load(self.path)

    # ---- internal helpers -------------------------------------------------

    def _next_id(self) -> int:
        return max((e.id for e in self.expenses), default=0) + 1

    def _snapshot(self):
        return list(self.expenses), self.budget

    def _save(self, snapshot) -> None:
        """Persist changes; if saving fails, roll memory back to match the disk."""
        try:
            storage.save(self.expenses, self.budget, self.path)
        except StorageError:
            self.expenses, self.budget = snapshot
            raise

    # ---- create / read / update / delete ---------------------------------

    def add(self, amount, category, description="", date_str=None) -> Expense:
        expense = Expense(
            id=self._next_id(),
            amount=v.validate_amount(amount),
            category=v.validate_category(category),
            description=v.validate_description(description),
            date=v.validate_date(date_str),
        )
        snapshot = self._snapshot()
        self.expenses.append(expense)
        self._save(snapshot)
        return expense

    def get(self, expense_id) -> Expense:
        expense_id = v.validate_id(expense_id)  # accepts "3" from the CLI as well as 3
        for expense in self.expenses:
            if expense.id == expense_id:
                return expense
        raise ExpenseNotFoundError(expense_id)

    def update(self, expense_id, amount=None, category=None, description=None, date_str=None) -> Expense:
        """Change only the fields that are provided (not None)."""
        current = self.get(expense_id)
        changes = {}
        if amount is not None:
            changes["amount"] = v.validate_amount(amount)
        if category is not None:
            changes["category"] = v.validate_category(category)
        if description is not None:
            changes["description"] = v.validate_description(description)
        if date_str is not None:
            changes["date"] = v.validate_date(date_str)
        if not changes:
            raise ValidationError("Nothing to update. Provide at least one field.")

        updated = replace(current, **changes)
        snapshot = self._snapshot()
        self.expenses = [updated if e.id == current.id else e for e in self.expenses]
        self._save(snapshot)
        return updated

    def delete(self, expense_id) -> Expense:
        removed = self.get(expense_id)
        snapshot = self._snapshot()
        self.expenses = [e for e in self.expenses if e.id != removed.id]
        self._save(snapshot)
        return removed

    # ---- queries ----------------------------------------------------------

    def list_expenses(self, category=None, month=None, keyword=None, sort_by="date", descending=True):
        if sort_by not in SORT_FIELDS:
            raise ValidationError(f"Sort field must be one of: {', '.join(SORT_FIELDS)}.")

        results = self.expenses
        if category:
            cat = v.validate_category(category)
            results = [e for e in results if e.category == cat]
        if month:
            m = v.validate_month(month)
            results = [e for e in results if e.date.startswith(m)]
        if keyword:
            kw = keyword.strip().lower()
            results = [e for e in results if kw in e.description.lower() or kw in e.category.lower()]

        return sorted(results, key=lambda e: (getattr(e, sort_by), e.id), reverse=descending)

    @staticmethod
    def total(expenses) -> float:
        return round(sum(e.amount for e in expenses), 2)

    def totals_by_category(self, month=None) -> dict:
        totals = defaultdict(float)
        for e in self.list_expenses(month=month):
            totals[e.category] += e.amount
        ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
        return {cat: round(amount, 2) for cat, amount in ranked}

    def totals_by_month(self) -> dict:
        totals = defaultdict(float)
        for e in self.expenses:
            totals[e.date[:7]] += e.amount
        return {month: round(totals[month], 2) for month in sorted(totals, reverse=True)}

    # ---- budget -----------------------------------------------------------

    def set_budget(self, amount) -> float:
        value = v.validate_amount(amount)
        snapshot = self._snapshot()
        self.budget = value
        self._save(snapshot)
        return value

    def budget_status(self, month=None) -> dict:
        month = v.validate_month(month) if month else date.today().strftime("%Y-%m")
        spent = self.total(self.list_expenses(month=month))
        if self.budget is None:
            return {"month": month, "spent": spent, "budget": None, "remaining": None, "percent": None}
        return {
            "month": month,
            "spent": spent,
            "budget": self.budget,
            "remaining": round(self.budget - spent, 2),
            "percent": round(spent / self.budget * 100, 1),
        }
