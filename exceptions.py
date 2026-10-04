"""Custom exceptions for the expense tracker.

A small hierarchy lets callers catch everything with ExpenseTrackerError,
or handle specific problems individually.
"""


class ExpenseTrackerError(Exception):
    """Base class for all application errors."""


class ValidationError(ExpenseTrackerError):
    """Raised when user input is invalid."""


class ExpenseNotFoundError(ExpenseTrackerError):
    """Raised when an expense ID does not exist."""

    def __init__(self, expense_id: int):
        super().__init__(f"No expense found with ID {expense_id}.")
        self.expense_id = expense_id


class StorageError(ExpenseTrackerError):
    """Raised when reading or writing data files fails."""


class CorruptDataError(StorageError):
    """Raised when the data file is unreadable and was safely backed up."""
