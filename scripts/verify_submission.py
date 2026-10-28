"""Verify assignment evidence, including genuine-mode paths and accounting."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CHECKS = {"normal", "missing_budget", "missing_deadline", "tool_failure", "budget_replan", "budget_gap"}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check_case(root: Path, case: dict) -> list[str]:
    errors = []
    try:
        directory = root / case["directory"]
        output, request = read(directory / "output.json"), read(directory / "input.json")
        events = [json.loads(line) for line in (directory / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        if output["status"] != case["expected_status"]:
            errors.append("unexpected final status")
        if output["mode"] != case["mode"]:
            errors.append("live/mock mode mismatch")
        if case["mode"] == "live":
            actions = [event for event in events if "action" in event]
            if not actions or any(event.get("mode") != "live" or not event["action"].get("model_response", {}).get("id") for event in actions):
                errors.append("live evidence lacks model response IDs or genuine-mode actions")
        if output["status"] == "completed":
            saved = read(directory / "plan.json")
            if saved["plan"] != output["plan"] or saved["cost"] != output["cost"]:
                errors.append("saved result differs from final output")
            if Decimal(output["cost"]["projected_total"]) > Decimal(str(request["budget"])):
                errors.append("completed result exceeds budget")
            if datetime.fromisoformat(output["cost"]["projected_finish"]) > datetime.fromisoformat(request["deadline"]):
                errors.append("completed result exceeds deadline")
        elif (directory / "plan.json").exists():
            errors.append("unfinished case has a saved success artifact")
        if "ledger" in output:
            spent = sum((Decimal(item["fee"]) for item in output["ledger"]), Decimal(0))
            if spent != Decimal(output["cost"]["spent"]):
                errors.append("ledger sum differs from spent")
        steps = output.get("steps", [])
        estimates = [event["observation"]["data"] for event in events
                     if event.get("action", {}).get("tool") == "estimate_cost" and event["observation"]["ok"]]
        for check in case.get("checks", []):
            if check in ("missing_budget", "missing_deadline"):
                field = check.removeprefix("missing_")
                if field not in output.get("missing", []) or events or steps:
                    errors.append(f"missing {field} must stop before tool/model calls")
            if check == "tool_failure":
                failures = [index for index, step in enumerate(steps) if step["status"] == "failed"]
                if not failures or not any(step["status"] == "succeeded" for step in steps[failures[0] + 1:]):
                    errors.append("failure was not retained with later successful recovery")
                if sum(step["tool"] == "generate_script" for step in steps) != 1:
                    errors.append("successful script was unnecessarily regenerated after failure")
            if check == "budget_replan":
                if not (len(estimates) >= 2 and Decimal(estimates[0]["budget_gap"]) > 0
                        and estimates[-1]["feasible"] and output["plan"]["version"] >= 2):
                    errors.append("missing observed budget violation and feasible revised plan")
            if check == "budget_gap" and Decimal(output["cost"]["budget_gap"]) <= 0:
                errors.append("missing numeric budget gap")
            if check == "time_gap" and output["cost"]["time_gap_minutes"] <= 0:
                errors.append("missing numeric time gap")
        if (directory / "state.json").exists() and read(directory / "state.json")["events"] != events:
            errors.append("trace differs from checkpoint")
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        errors.append(f"invalid/missing evidence: {type(error).__name__}")
    return errors


def verify(root: Path, manifest: dict) -> dict:
    errors, results, covered, live_paths = [], [], set(), set()
    for case in manifest["cases"]:
        failures = check_case(root, case)
        results.append({"case": case["name"], "passed": not failures, "errors": failures})
        errors.extend(f"{case['name']}: {error}" for error in failures)
        if not failures:
            covered.update(case.get("checks", []))
            if case["mode"] == "live":
                events = [json.loads(line) for line in (root / case["directory"] / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
                live_paths.add(tuple((event.get("action", {}).get("tool"), event.get("observation", {}).get("ok")) for event in events))
    if REQUIRED_CHECKS - covered:
        errors.append("missing required coverage: " + ", ".join(sorted(REQUIRED_CHECKS - covered)))
    if len(live_paths) < 2:
        errors.append("at least two different live execution paths are required")
    for name in ["README.md", "pyproject.toml", ".env.example", "docs/01-requirements.md",
                 "docs/02-solution.md", "docs/03-evaluation.md", "docs/04-ai-usage.md", "docs/05-retrospective.md"]:
        if not (root / name).is_file():
            errors.append("missing delivery file: " + name)
    for path in manifest.get("bonus_summaries", []):
        try:
            bonus = read(root / path)
            if not bonus["successful_script_preserved"] or not bonus["repeated_execution_artifact_hashes_unchanged"]:
                errors.append("bonus recovery/replay failed: " + path)
            for filename, expected in bonus["sha256"].items():
                artifact = root / Path(path).parent / "resume" / filename
                if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
                    errors.append("bonus artifact hash mismatch: " + str(artifact.relative_to(root)))
        except (OSError, ValueError, KeyError, TypeError):
            errors.append("missing bonus evidence: " + path)
    return {"passed": not errors, "checked_cases": len(results), "different_live_paths": len(live_paths),
            "covered": sorted(covered), "cases": results, "errors": errors,
            "note": "Checks local evidence consistency; remote repository visibility and commit SHA are verified separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()
    result = verify(args.root, read(args.root / "examples/manifest.json"))
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(json.dumps({**result, "checked_at_utc": datetime.now(timezone.utc).isoformat()},
                                    ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
