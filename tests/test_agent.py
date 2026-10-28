import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from content_agent.agent import run_agent
from content_agent.mock_model import MockModel
from content_agent.tools import Engine


NOW = datetime(2026, 10, 28, 2, tzinfo=timezone.utc)
REQUEST = {"theme": "校园咖啡", "budget": 20, "deadline": "2026-10-28T18:00:00+08:00"}


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.engine = Engine(REQUEST, Path(self.folder.name), now=lambda: NOW)

    def test_normal_path_saves_and_reports_exact_cost(self):
        result = run_agent(self.engine, MockModel())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["cost"]["projected_total"], "12.70")
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(len(self.engine.state["events"]), 4)

    def test_budget_feedback_produces_another_plan(self):
        self.engine.state["request"]["budget"] = 10
        result = run_agent(self.engine, MockModel())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["plan"]["asset_id"], "economy")
        self.assertEqual(result["plan"]["version"], 2)
        self.assertEqual(result["cost"]["projected_total"], "9.10")
        estimates = [event["observation"]["data"] for event in self.engine.state["events"]
                     if event["action"]["tool"] == "estimate_cost"]
        self.assertFalse(estimates[0]["feasible"])
        self.assertTrue(estimates[1]["feasible"])

    def test_tool_failure_is_observed_then_successful_script_is_reused(self):
        self.engine.state["failures_remaining"] = {"estimate_cost": 1}
        result = run_agent(self.engine, MockModel())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["plan"]["version"], 1)
        self.assertTrue(any(step["status"] == "failed" for step in result["steps"]))

    def test_no_feasible_plan_returns_numeric_gap_and_no_saved_file(self):
        self.engine.state["request"]["budget"] = 3
        result = run_agent(self.engine, MockModel())
        self.assertEqual(result["status"], "incomplete")
        self.assertGreater(float(result["cost"]["budget_gap"]), 0)
        self.assertFalse((self.engine.output / "plan.json").exists())

    def test_time_feedback_selects_faster_channel(self):
        self.engine.state["request"]["deadline"] = "2026-10-28T10:45:00+08:00"
        result = run_agent(self.engine, MockModel())
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["plan"]["channel"], "post")

    def test_step_limit_and_resume_preserve_prior_results(self):
        limited = run_agent(self.engine, MockModel(), max_steps=2)
        self.assertEqual(limited["status"], "incomplete")
        self.assertEqual(limited["stop_code"], "STEP_LIMIT")
        resumed = run_agent(self.engine, MockModel(), max_steps=16)
        self.assertEqual(resumed["status"], "completed")
        self.assertEqual(resumed["plan"]["version"], 1)
        self.assertEqual(resumed["cost"]["projected_total"], "12.70")

    def test_untrusted_action_cannot_claim_completion(self):
        class PrematureFinish:
            mode = "test"
            identity = "test:premature"

            def decide(self, context):
                return {"tool": "finish", "arguments": {}, "reason": "任务已完成"}

        result = run_agent(self.engine, PrematureFinish())
        self.assertEqual(result["status"], "incomplete")
        self.assertIsNone(result["saved_path"])

    def test_invalid_actions_are_bounded(self):
        class BadModel:
            mode = "test"
            identity = "test:bad"

            def decide(self, context):
                return {"tool": "made_up", "arguments": {}, "reason": "测试"}

        result = run_agent(self.engine, BadModel(), max_steps=16)
        self.assertEqual(result["stop_code"], "REPEATED_FAILURE")
        self.assertEqual(len(self.engine.state["events"]), 3)


if __name__ == "__main__":
    unittest.main()
