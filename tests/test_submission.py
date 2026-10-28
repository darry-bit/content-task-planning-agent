import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.verify_submission import check_case, verify


ROOT = Path(__file__).resolve().parents[1]


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        shutil.copytree(ROOT / "examples/runs/offline-v1/normal", self.root / "normal")
        self.case = {"name": "normal", "directory": "normal", "mode": "mock",
                     "expected_status": "completed", "checks": []}

    def test_complete_case_has_consistent_saved_result_and_ledger(self):
        self.assertEqual(check_case(self.root, self.case), [])

    def test_tampered_ledger_is_detected(self):
        path = self.root / "normal/output.json"
        output = json.loads(path.read_text(encoding="utf-8"))
        output["cost"]["spent"] = "99.00"
        path.write_text(json.dumps(output), encoding="utf-8")
        self.assertTrue(any("ledger" in error for error in check_case(self.root, self.case)))

    def test_mock_trace_cannot_be_used_as_live_evidence(self):
        case = {**self.case, "mode": "live"}
        self.assertTrue(any("live" in error for error in check_case(self.root, case)))

    def test_missing_evidence_returns_errors_without_crashing(self):
        (self.root / "normal/trace.jsonl").unlink()
        self.assertTrue(check_case(self.root, self.case))

    def test_real_manifest_covers_required_cases_and_two_live_paths(self):
        manifest = json.loads((ROOT / "examples/manifest.json").read_text(encoding="utf-8"))
        result = verify(ROOT, manifest)
        self.assertTrue(result["passed"], result["errors"])
        incomplete = copy.deepcopy(manifest)
        incomplete["cases"] = [case for case in incomplete["cases"] if case["mode"] != "live"]
        self.assertFalse(verify(ROOT, incomplete)["passed"])


if __name__ == "__main__":
    unittest.main()
