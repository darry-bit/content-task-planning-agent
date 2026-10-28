"""Local, atomic checkpoint writes; no model-supplied output paths."""
import json
from pathlib import Path


def read_json(path: Path) -> object:
    def reject_constant(value):
        raise ValueError(f"JSON 不允许 {value}")
    return json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)


def write_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_trace(path: Path, events: list) -> None:
    temporary = path.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n"
                                 for event in events), encoding="utf-8")
    temporary.replace(path)
