#!/usr/bin/env python3
"""Expense Tracker CLI.

Run with no arguments for an interactive menu, or use a command:

    python main.py add 250 food -d "Lunch"
    python main.py list --month 2026-09 --sort amount
    python main.py summary
"""

import argparse
import sys
from functools import wraps
from pathlib import Path

import reports
import storage
import validators as v
from exceptions import (
    CorruptDataError,
    ExpenseNotFoundError,
    ExpenseTrackerError,
    StorageError,
    ValidationError,
)
from tracker import SORT_FIELDS, ExpenseTracker


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def handle_errors(func):
    """Decorator: turn known errors into friendly messages. Returns an exit code."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            func(*args, **kwargs)
            return 0
        except ExpenseNotFoundError as exc:
            print(f"Not found: {exc}", file=sys.stderr)
        except ValidationError as exc:
            print(f"Invalid input: {exc}", file=sys.stderr)
        except StorageError as exc:
            print(f"Storage problem: {exc}", file=sys.stderr)
        except ExpenseTrackerError as exc:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    return wrapper


def confirm(question: str) -> bool:
    return input(f"{question} [y/N]: ").strip().lower() in ("y", "yes")


def show_budget_alert(tracker: ExpenseTracker, month: str) -> None:
    alert = reports.budget_alert(tracker.budget_status(month))
    if alert:
        print(alert)


# ---------------------------------------------------------------------------
# Command-line mode (argparse)
# ---------------------------------------------------------------------------

@handle_errors
def cmd_add(tracker, args):
    e = tracker.add(args.amount, args.category, args.description, args.date)
    print(f"Added #{e.id}: {reports.money(e.amount)} for {e.category} on {e.date}")
    show_budget_alert(tracker, e.date[:7])


@handle_errors
def cmd_list(tracker, args):
    expenses = tracker.list_expenses(
        category=args.category,
        month=args.month,
        keyword=args.search,
        sort_by=args.sort,
        descending=not args.asc,
    )
    print(reports.format_table(expenses))


@handle_errors
def cmd_edit(tracker, args):
    e = tracker.update(
        args.id,
        amount=args.amount,
        category=args.category,
        description=args.description,
        date_str=args.date,
    )
    print(f"Updated #{e.id}: {reports.money(e.amount)} | {e.category} | {e.date} | {e.description}")


@handle_errors
def cmd_delete(tracker, args):
    expense = tracker.get(args.id)  # raises ExpenseNotFoundError early
    if not args.yes and not confirm(
        f"Delete #{expense.id} ({reports.money(expense.amount)}, {expense.category})?"
    ):
        print("Cancelled.")
        return
    tracker.delete(args.id)
    print(f"Deleted #{expense.id}.")


@handle_errors
def cmd_summary(tracker, args):
    if args.monthly:
        print(reports.format_breakdown("Spending by month", tracker.totals_by_month()))
    else:
        title = f"Spending by category ({args.month})" if args.month else "Spending by category (all time)"
        print(reports.format_breakdown(title, tracker.totals_by_category(args.month)))


@handle_errors
def cmd_budget(tracker, args):
    if args.amount is not None:
        print(f"Monthly budget set to {reports.money(tracker.set_budget(args.amount))}.")
    print(reports.format_budget(tracker.budget_status(args.month)))


@handle_errors
def cmd_export(tracker, args):
    path = Path(args.path)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    count = storage.export_csv(tracker.expenses, path)
    print(f"Exported {count} expense(s) to {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="expense-tracker", description="Track expenses from the terminal.")
    parser.add_argument("--file", type=Path, default=storage.DEFAULT_PATH, help="data file location")
    sub = parser.add_subparsers(dest="command", metavar="command")

    p = sub.add_parser("add", help="add an expense")
    p.add_argument("amount")
    p.add_argument("category")
    p.add_argument("-d", "--description", default="")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.set_defaults(handler=cmd_add)

    p = sub.add_parser("list", help="list expenses")
    p.add_argument("-c", "--category")
    p.add_argument("-m", "--month", help="YYYY-MM")
    p.add_argument("-s", "--search", help="keyword in description or category")
    p.add_argument("--sort", choices=SORT_FIELDS, default="date")
    p.add_argument("--asc", action="store_true", help="oldest/smallest first")
    p.set_defaults(handler=cmd_list)

    p = sub.add_parser("edit", help="edit an expense")
    p.add_argument("id")
    p.add_argument("--amount")
    p.add_argument("--category")
    p.add_argument("--description")
    p.add_argument("--date")
    p.set_defaults(handler=cmd_edit)

    p = sub.add_parser("delete", help="delete an expense")
    p.add_argument("id")
    p.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    p.set_defaults(handler=cmd_delete)

    p = sub.add_parser("summary", help="spending breakdown")
    p.add_argument("-m", "--month", help="YYYY-MM")
    p.add_argument("--monthly", action="store_true", help="group by month instead of category")
    p.set_defaults(handler=cmd_summary)

    p = sub.add_parser("budget", help="show or set the monthly budget")
    p.add_argument("amount", nargs="?", help="new monthly budget")
    p.add_argument("-m", "--month", help="YYYY-MM (default: this month)")
    p.set_defaults(handler=cmd_budget)

    p = sub.add_parser("export", help="export to CSV")
    p.add_argument("path", nargs="?", default="expenses_export.csv")
    p.set_defaults(handler=cmd_export)

    return parser


# ---------------------------------------------------------------------------
# Interactive mode
# ---------------------------------------------------------------------------

def ask(prompt: str, validator):
    """Keep asking until the validator accepts the answer."""
    while True:
        try:
            return validator(input(prompt))
        except ValidationError as exc:
            print(f"  ! {exc}")


def ask_optional(prompt: str, validator):
    """Like ask(), but a blank answer returns None."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return validator(raw)
        except ValidationError as exc:
            print(f"  ! {exc}")


@handle_errors
def menu_add(tracker):
    amount = ask("Amount: ", v.validate_amount)
    category = ask("Category (e.g. Food, Travel): ", v.validate_category)
    description = ask("Description (optional): ", v.validate_description)
    date_str = ask("Date YYYY-MM-DD (blank = today): ", v.validate_date)
    e = tracker.add(amount, category, description, date_str)
    print(f"Added #{e.id}: {reports.money(e.amount)} for {e.category} on {e.date}")
    show_budget_alert(tracker, e.date[:7])


@handle_errors
def menu_view(tracker):
    category = ask_optional("Filter by category (blank = all): ", v.validate_category)
    month = ask_optional("Filter by month YYYY-MM (blank = all): ", v.validate_month)
    print(reports.format_table(tracker.list_expenses(category=category, month=month)))


@handle_errors
def menu_edit(tracker):
    expense = tracker.get(ask("Expense ID to edit: ", v.validate_id))
    print(f"Current: {reports.money(expense.amount)} | {expense.category} | {expense.date} | {expense.description}")
    print("Press Enter to keep a value.")
    amount = ask_optional("New amount: ", v.validate_amount)
    category = ask_optional("New category: ", v.validate_category)
    description = ask_optional("New description: ", v.validate_description)
    date_str = ask_optional("New date: ", v.validate_date)
    updated = tracker.update(expense.id, amount, category, description, date_str)
    print(f"Updated #{updated.id}.")


@handle_errors
def menu_delete(tracker):
    expense = tracker.get(ask("Expense ID to delete: ", v.validate_id))
    if confirm(f"Delete #{expense.id} ({reports.money(expense.amount)}, {expense.category})?"):
        tracker.delete(expense.id)
        print("Deleted.")
    else:
        print("Cancelled.")


@handle_errors
def menu_summary(tracker):
    print(reports.format_breakdown("Spending by category (all time)", tracker.totals_by_category()))
    print()
    print(reports.format_breakdown("Spending by month", tracker.totals_by_month()))


@handle_errors
def menu_budget(tracker):
    print(reports.format_budget(tracker.budget_status()))
    new_budget = ask_optional("New monthly budget (blank = keep): ", v.validate_amount)
    if new_budget is not None:
        print(f"Budget set to {reports.money(tracker.set_budget(new_budget))}.")


@handle_errors
def menu_export(tracker):
    raw = input("Export file name [expenses_export.csv]: ").strip() or "expenses_export.csv"
    path = Path(raw)
    if path.suffix.lower() != ".csv":
        path = path.with_suffix(".csv")
    print(f"Exported {storage.export_csv(tracker.expenses, path)} expense(s) to {path}")


MENU = {
    "1": ("Add expense", menu_add),
    "2": ("View expenses", menu_view),
    "3": ("Edit expense", menu_edit),
    "4": ("Delete expense", menu_delete),
    "5": ("Summary", menu_summary),
    "6": ("Monthly budget", menu_budget),
    "7": ("Export to CSV", menu_export),
}


def interactive_menu(tracker: ExpenseTracker) -> None:
    while True:
        print("\n=== Expense Tracker ===")
        for key, (label, _) in MENU.items():
            print(f"  {key}. {label}")
        print("  0. Exit")
        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye!")
            return
        if choice not in MENU:
            print("Please enter a number from the menu.")
            continue
        print()
        MENU[choice][1](tracker)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def load_tracker(path: Path) -> ExpenseTracker:
    try:
        return ExpenseTracker(path)
    except CorruptDataError as exc:
        print(f"Warning: {exc}", file=sys.stderr)
        return ExpenseTracker(path)  # the bad file was moved aside, so this starts fresh


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tracker = load_tracker(args.file)
        if args.command is None:
            interactive_menu(tracker)
            return 0
        return args.handler(tracker, args)
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130
    except StorageError as exc:
        print(f"Fatal storage error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
