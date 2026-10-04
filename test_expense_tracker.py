"""Run with:  python -m unittest -v"""

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import storage
import validators as v
from exceptions import (
    CorruptDataError,
    ExpenseNotFoundError,
    StorageError,
    ValidationError,
)
from tracker import ExpenseTracker


class ValidatorTests(unittest.TestCase):
    def test_amount_valid(self):
        self.assertEqual(v.validate_amount("1,250.456"), 1250.46)
        self.assertEqual(v.validate_amount(" 99 "), 99.0)

    def test_amount_invalid(self):
        for bad in ("", "abc", "0", "-5", "nan", "inf", "99999999999"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                v.validate_amount(bad)

    def test_category(self):
        self.assertEqual(v.validate_category("  food   & drinks "), "Food & Drinks")
        for bad in ("", "123", "food!", "x" * 31):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                v.validate_category(bad)

    def test_date(self):
        self.assertEqual(v.validate_date(""), date.today().isoformat())
        self.assertEqual(v.validate_date("2026-9-8"), "2026-09-08")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        for bad in ("2026-13-01", "yesterday", tomorrow):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                v.validate_date(bad)

    def test_month_and_id(self):
        self.assertEqual(v.validate_month("2026-09"), "2026-09")
        with self.assertRaises(ValidationError):
            v.validate_month("2026-13")
        self.assertEqual(v.validate_id("7"), 7)
        for bad in ("0", "-1", "x", "1.5"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                v.validate_id(bad)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "data.json"
        self.tracker = ExpenseTracker(self.path)

    def test_add_persists_and_reloads(self):
        e = self.tracker.add("250", "food", "Lunch", "2026-09-01")
        self.assertEqual((e.id, e.category, e.amount), (1, "Food", 250.0))
        reloaded = ExpenseTracker(self.path)
        self.assertEqual(reloaded.get(1), e)

    def test_no_duplicate_ids_after_deleting_middle_entry(self):
        for amount in (10, 20, 30):
            self.tracker.add(amount, "food")
        self.tracker.delete(2)
        self.assertEqual(self.tracker.add(40, "food").id, 4)
        ids = [e.id for e in self.tracker.expenses]
        self.assertEqual(len(ids), len(set(ids)))

    def test_invalid_add_changes_nothing(self):
        with self.assertRaises(ValidationError):
            self.tracker.add("-5", "food")
        self.assertEqual(self.tracker.expenses, [])

    def test_update_and_not_found(self):
        self.tracker.add(100, "food", date_str="2026-09-01")
        updated = self.tracker.update(1, amount="150", description="")
        self.assertEqual(updated.amount, 150.0)
        with self.assertRaises(ValidationError):
            self.tracker.update(1)
        with self.assertRaises(ExpenseNotFoundError):
            self.tracker.update(99, amount=5)
        with self.assertRaises(ExpenseNotFoundError):
            self.tracker.delete(99)

    def test_ids_given_as_strings_work(self):
        """The CLI passes IDs as text, e.g. 'edit 1'."""
        self.tracker.add(100, "food", date_str="2026-09-01")
        self.assertEqual(self.tracker.update("1", amount="5").amount, 5.0)
        self.assertEqual(self.tracker.delete("1").id, 1)
        with self.assertRaises(ValidationError):
            self.tracker.get("abc")

    def test_filters_sorting_and_totals(self):
        self.tracker.add(100, "food", "pizza", "2026-09-01")
        self.tracker.add(300, "travel", "bus pass", "2026-09-15")
        self.tracker.add(50, "food", "tea", "2026-08-20")
        self.assertEqual(len(self.tracker.list_expenses(category="FOOD")), 2)
        self.assertEqual(len(self.tracker.list_expenses(month="2026-09")), 2)
        self.assertEqual(len(self.tracker.list_expenses(keyword="BUS")), 1)
        by_amount = self.tracker.list_expenses(sort_by="amount")
        self.assertEqual([e.amount for e in by_amount], [300, 100, 50])
        self.assertEqual(self.tracker.totals_by_category(), {"Travel": 300.0, "Food": 150.0})
        self.assertEqual(self.tracker.totals_by_month(), {"2026-09": 400.0, "2026-08": 50.0})
        with self.assertRaises(ValidationError):
            self.tracker.list_expenses(sort_by="colour")

    def test_budget_status(self):
        self.assertIsNone(self.tracker.budget_status("2026-09")["budget"])
        self.tracker.set_budget(500)
        self.tracker.add(400, "food", date_str="2026-09-01")
        status = self.tracker.budget_status("2026-09")
        self.assertEqual((status["remaining"], status["percent"]), (100.0, 80.0))

    def test_failed_save_rolls_back(self):
        with mock.patch("storage.save", side_effect=StorageError("disk full")):
            with self.assertRaises(StorageError):
                self.tracker.add(10, "food")
        self.assertEqual(self.tracker.expenses, [])


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dir = Path(self._tmp.name)

    def test_corrupt_file_is_backed_up(self):
        path = self.dir / "data.json"
        path.write_text("{ not json", encoding="utf-8")
        with self.assertRaises(CorruptDataError):
            ExpenseTracker(path)
        self.assertFalse(path.exists())
        self.assertTrue((self.dir / "data.corrupt.json").exists())
        self.assertEqual(ExpenseTracker(path).expenses, [])  # fresh start works

    def test_wrong_structure_is_treated_as_corrupt(self):
        path = self.dir / "data.json"
        path.write_text('{"expenses": [{"id": "x"}]}', encoding="utf-8")
        with self.assertRaises(CorruptDataError):
            storage.load(path)

    def test_csv_export_blocks_formula_injection(self):
        tracker = ExpenseTracker(self.dir / "data.json")
        tracker.add(10, "food", "=HYPERLINK(\"evil\")")
        out = self.dir / "out.csv"
        self.assertEqual(storage.export_csv(tracker.expenses, out), 1)
        with out.open(newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["id", "date", "category", "description", "amount"])
        self.assertTrue(rows[1][3].startswith("'="))


if __name__ == "__main__":
    unittest.main()
