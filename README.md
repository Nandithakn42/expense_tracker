# Expense Tracker (Python CLI)

A command-line expense tracker with an interactive menu, budgets, CSV export and JSON storage. Python 3.9+, standard library only.

## Run

```bash
python main.py            # interactive menu
python main.py <command>  # direct commands
python -m unittest -v     # run tests
```

## Commands

| Command | Example |
|---|---|
| add | `python main.py add 250 food -d "Lunch" --date 2026-09-10` |
| list | `python main.py list -m 2026-09 -c food -s lunch --sort amount --asc` |
| edit | `python main.py edit 3 --amount 300 --description "Fixed"` |
| delete | `python main.py delete 3` (`-y` skips confirmation) |
| summary | `python main.py summary` / `summary -m 2026-09` / `summary --monthly` |
| budget | `python main.py budget 5000` sets it, `python main.py budget` shows status |
| export | `python main.py export report.csv` |

Use a different data file with `python main.py --file other.json list` (the option goes before the command).

## Project structure

| File | Responsibility |
|---|---|
| `main.py` | argparse commands, interactive menu, error-handling decorator |
| `tracker.py` | `ExpenseTracker` class: add, update, delete, filter, totals, budget |
| `validators.py` | Input validation (amount, category, date, month, ID) |
| `storage.py` | Atomic JSON save/load, corrupt-file backup, CSV export |
| `reports.py` | Table, bar-chart and budget text formatting |
| `models.py` | `Expense` dataclass |
| `exceptions.py` | Custom exception hierarchy |
| `test_expense_tracker.py` | Unit tests |

## Design notes

- **Validation happens in the tracker**, so bad data is rejected no matter which front end calls it.
- **Failed saves roll back** in-memory changes so memory never disagrees with the file.
- **Atomic writes** (temp file, then replace) prevent a crash from corrupting your data.
- **Corrupt data file** is moved to `*.corrupt.json` instead of being overwritten.
- **CSV export** prefixes cells starting with `=`, `+`, `-`, `@` to prevent spreadsheet formula injection.
- Data is stored in `data/expenses.json` next to the code. Change the currency symbol in `reports.py`.
