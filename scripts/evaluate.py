"""Run offline acceptance cases and retain actual CLI artifacts. No API calls."""
import argparse
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOCK = "2026-10-28T10:00:00+08:00"
CASES = [
    ("normal", "normal.json", [], "completed"),
    ("missing-budget", "missing-budget.json", [], "needs_input"),
    ("missing-deadline", "missing-deadline.json", [], "needs_input"),
    ("tool-failure", "normal.json", ["--fail-once", "estimate_cost"], "completed"),
    ("over-budget", "over-budget.json", [], "completed"),
    ("impossible", "impossible.json", [], "incomplete"),
    ("time-tight", "time-tight.json", [], "completed"),
    ("time-impossible", "time-impossible.json", [], "incomplete"),
]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "local-runs/evaluation")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("输出目录非空，请使用新目录，避免覆盖验收证据")
    output.mkdir(parents=True, exist_ok=True)
    records = []
    for name, filename, extra, expected in CASES:
        arguments = ["run.py", "--input", f"examples/inputs/{filename}",
                     "--mode", "mock", "--now", CLOCK, "--output", str(output / name), *extra]
        run = subprocess.run([sys.executable, *arguments], cwd=ROOT, capture_output=True,
                             encoding="utf-8", text=True)
        actual = json.loads(run.stdout)
        passed = actual["status"] == expected and run.returncode == (0 if expected == "completed" else 3)
        cost = actual.get("cost", {})
        records.append({"case": name, "expected": expected, "actual": actual["status"],
                        "exit_code": run.returncode, "passed": passed,
                        "projected_total": cost.get("projected_total"),
                        "budget_gap": cost.get("budget_gap"), "time_gap_minutes": cost.get("time_gap_minutes")})
        if (output / name).exists():
            write(output / name / "command.json", {"argv": ["python", *arguments],
                  "python_version": platform.python_version(), "stderr": run.stderr,
                  "exit_code": run.returncode, "clock_is_simulated": True})
        print(f"{name}: {actual['status']} {'PASS' if passed else 'FAIL'}")
    write(output / "summary.json", {"mode": "mock", "fixed_now": CLOCK,
          "executed_at_utc": datetime.now(timezone.utc).isoformat(),
          "real_model_verified": False, "cases": records})
    return 0 if all(record["passed"] for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
