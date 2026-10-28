import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "input.json"
        self.request = {"theme": "校园咖啡", "budget": 10, "deadline": "2026-10-28T18:00:00+08:00"}
        self.source.write_text(json.dumps(self.request), encoding="utf-8")

    def cli(self, *extra):
        return subprocess.run([sys.executable, str(ROOT / "run.py"),
                               "--input", str(self.source), "--output", str(self.root / "run"),
                               "--now", "2026-10-28T10:00:00+08:00", *extra],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8")

    def test_cli_writes_trace_output_and_input_and_refuses_overwrite(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        output = json.loads((self.root / "run/output.json").read_text(encoding="utf-8"))
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["cost"]["projected_total"], "9.10")
        trace = (self.root / "run/trace.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(trace), 6)
        self.assertTrue((self.root / "run/input.json").exists())
        self.assertEqual(self.cli().returncode, 2)

    def test_resume_completed_run_is_idempotent_and_does_not_rewrite_trace(self):
        self.cli()
        before = (self.root / "run/state.json").read_bytes()
        result = self.cli("--resume")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / "run/state.json").read_bytes(), before)

    def test_resume_from_step_limit_preserves_successful_script(self):
        limited = self.cli("--max-steps", "2")
        self.assertEqual(limited.returncode, 3)
        resumed = self.cli("--resume")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        output = json.loads(resumed.stdout)
        self.assertEqual(output["cost"]["spent"], "1.10")
        generations = [step for step in output["steps"] if step["tool"] == "generate_script"]
        self.assertEqual(len(generations), 2)  # premium then economy, not a repeated premium

    def test_resume_rejects_different_request(self):
        self.cli("--max-steps", "2")
        self.source.write_text(json.dumps({**self.request, "budget": 11}), encoding="utf-8")
        self.assertEqual(self.cli("--resume").returncode, 2)

    def test_missing_budget_returns_needs_input_without_model_configuration(self):
        self.source.write_text(json.dumps({"theme": "咖啡", "deadline": self.request["deadline"]}), encoding="utf-8")
        result = self.cli()
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["missing"], ["budget"])
        self.assertEqual((self.root / "run/trace.jsonl").read_bytes(), b"")

    def test_live_rejects_simulated_clock(self):
        result = self.cli("--mode", "live")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--now", result.stdout)

    def test_past_deadline_is_incomplete(self):
        self.source.write_text(json.dumps({**self.request, "deadline": "2026-10-27T18:00:00+08:00"}), encoding="utf-8")
        result = self.cli()
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["status"], "incomplete")

    def test_resume_rejects_changed_rules_and_clock(self):
        self.cli("--max-steps", "2")
        checkpoint = self.root / "run/state.json"
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        state["rules_fingerprint"] = "changed"
        checkpoint.write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(self.cli("--resume").returncode, 2)

    def test_missing_saved_artifact_cannot_stay_completed(self):
        self.cli()
        (self.root / "run/plan.json").unlink()
        self.assertEqual(self.cli("--resume").returncode, 2)


if __name__ == "__main__":
    unittest.main()
