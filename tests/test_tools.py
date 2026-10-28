import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path

from content_agent.tools import Engine


NOW = datetime(2026, 10, 28, 2, tzinfo=timezone.utc)
REQUEST = {"theme": "校园咖啡", "budget": 20, "deadline": "2026-10-28T18:00:00+08:00"}
SCRIPT = {"headline": "期末一起加油", "body": "到店了解活动规则，用咖啡为复习加油。", "call_to_action": "查看店内活动说明"}


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.engine = Engine(REQUEST, Path(self.folder.name), now=lambda: NOW)

    def generate(self, asset_id="premium", channel="video"):
        self.engine.execute("search_assets", {})
        return self.engine.execute("generate_script", {
            "asset_id": asset_id, "channel": channel, "script": SCRIPT})

    def test_cannot_save_without_successful_dependencies(self):
        self.assertEqual(self.engine.execute("save_plan", {})["error"]["code"], "DEPENDENCY_MISSING")
        self.assertFalse((Path(self.folder.name) / "plan.json").exists())

    def test_estimate_includes_tool_fees_and_save_reservation(self):
        self.generate()
        result = self.engine.execute("estimate_cost", {})
        self.assertEqual(result["data"]["projected_total"], "12.70")
        self.assertTrue(self.engine.execute("save_plan", {})["ok"])
        saved = json.loads((Path(self.folder.name) / "plan.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["cost"]["projected_total"], "12.70")

    def test_new_script_invalidates_old_estimate(self):
        self.generate()
        self.engine.execute("estimate_cost", {})
        self.generate("economy")
        self.assertIsNone(self.engine.state["estimate"])
        self.assertEqual(self.engine.execute("save_plan", {})["error"]["code"], "DEPENDENCY_MISSING")

    def test_duplicate_generation_does_not_charge_or_create_new_version(self):
        self.generate()
        before = self.engine.context()["spent"]
        result = self.generate()
        self.assertTrue(result["reused"])
        self.assertEqual(self.engine.context()["spent"], before)
        self.assertEqual(self.engine.state["plan"]["version"], 1)

    def test_failure_keeps_successful_script_and_does_not_charge_failed_call(self):
        self.generate()
        self.engine.state["failures_remaining"] = {"estimate_cost": 1}
        before = self.engine.context()["spent"]
        failed = self.engine.execute("estimate_cost", {})
        self.assertFalse(failed["ok"])
        self.assertEqual(self.engine.context()["spent"], before)
        self.assertEqual(self.engine.state["plan"]["script"], SCRIPT)
        self.assertTrue(self.engine.execute("estimate_cost", {})["ok"])
        self.assertEqual(self.engine.state["steps"][-2]["status"], "failed")

    def test_save_rechecks_budget_and_real_clock(self):
        self.engine.state["request"]["budget"] = 10
        self.generate()
        self.engine.execute("estimate_cost", {})
        blocked = self.engine.execute("save_plan", {})
        self.assertEqual(blocked["error"]["code"], "CONSTRAINT_VIOLATION")
        self.assertEqual(blocked["error"]["details"]["budget_gap"], "2.70")

    def test_unexpected_arguments_and_unknown_assets_are_rejected(self):
        self.engine.execute("search_assets", {})
        self.assertFalse(self.engine.execute("save_plan", {"path": "outside"})["ok"])
        self.assertFalse(self.engine.execute("generate_script", {
            "asset_id": "invented", "channel": "video", "script": SCRIPT})["ok"])
        self.assertFalse(self.engine.execute("unknown", {})["ok"])

    def test_untrusted_argument_types_become_observations(self):
        self.engine.execute("search_assets", {})
        for patch in [{"channel": {}}, {"channel": []}, {"asset_id": {}}, {"script": []}]:
            with self.subTest(patch=patch):
                result = self.engine.execute("generate_script", {
                    "asset_id": "premium", "channel": "video", "script": SCRIPT, **patch})
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], "INVALID_ARGUMENTS")

    def test_clock_moving_after_estimate_blocks_save(self):
        self.generate()
        self.engine.execute("estimate_cost", {})
        self.engine.now = lambda: datetime(2026, 10, 29, tzinfo=timezone.utc)
        self.assertFalse(self.engine.execute("save_plan", {})["ok"])
        self.assertFalse((self.engine.output / "plan.json").exists())

    def test_file_write_failure_is_failed_and_fee_is_rolled_back(self):
        from unittest.mock import patch
        self.generate()
        self.engine.execute("estimate_cost", {})
        before = self.engine.context()["spent"]
        with patch("content_agent.tools.write_json", side_effect=OSError("disk error")):
            result = self.engine.execute("save_plan", {})
        self.assertEqual(result["error"]["code"], "WRITE_FAILED")
        self.assertEqual(self.engine.context()["spent"], before)
        self.assertIsNone(self.engine.state["saved_path"])


if __name__ == "__main__":
    unittest.main()
