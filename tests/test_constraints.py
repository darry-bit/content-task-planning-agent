import unittest
from datetime import datetime, timezone

from content_agent.constraints import assess, validate_request


NOW = datetime(2026, 10, 28, 2, tzinfo=timezone.utc)
REQUEST = {"theme": "校园咖啡", "budget": 10, "deadline": "2026-10-28T12:00:00+08:00"}


class ConstraintTests(unittest.TestCase):
    def test_missing_fields_are_returned_without_defaults(self):
        self.assertEqual(validate_request({"theme": "咖啡"})["missing"], ["budget", "deadline"])

    def test_invalid_budget_and_dates_are_rejected(self):
        for value in [-1, True, "10", float("inf"), float("nan")]:
            with self.subTest(value=value):
                self.assertEqual(validate_request({**REQUEST, "budget": value})["status"], "invalid_input")
        for value in ["2026-10-28T12:00:00", "明天", None]:
            with self.subTest(value=value):
                self.assertNotEqual(validate_request({**REQUEST, "deadline": value})["status"], "ready")

    def test_zero_budget_is_valid(self):
        self.assertEqual(validate_request({**REQUEST, "budget": 0})["status"], "ready")

    def test_budget_includes_save_fee_and_uses_decimal_arithmetic(self):
        report = assess(REQUEST, "0.6", "9.3", 0, 1, NOW, NOW, "0.1", 1)
        self.assertEqual(report["projected_total"], "10.00")
        self.assertTrue(report["feasible"])
        exceeded = assess(REQUEST, "0.6", "9.31", 0, 1, NOW, NOW, "0.1", 1)
        self.assertEqual(exceeded["budget_gap"], "0.01")

    def test_deadline_checks_simulated_and_real_time(self):
        report = assess(REQUEST, 0, 1, 119, 1, NOW, NOW, 0, 1)
        self.assertEqual(report["time_gap_minutes"], 1)
        self.assertFalse(report["feasible"])
        late = datetime(2026, 10, 28, 5, tzinfo=timezone.utc)
        self.assertFalse(assess(REQUEST, 0, 1, 0, 1, NOW, late, 0, 1)["feasible"])

    def test_theme_must_be_nonempty_text(self):
        self.assertEqual(validate_request({**REQUEST, "theme": 123})["status"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
