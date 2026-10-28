"""CLI entry point, replay protection and local checkpoints."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .agent import run_agent, summary
from .constraints import parse_time, validate_request
from .chat_model import create_live_model
from .mock_model import MockModel
from .storage import read_json, write_json, write_trace
from .tools import Engine, rules_fingerprint


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="内容任务规划 Agent；默认 Mock，只验证流程")
    cli.add_argument("--input", required=True, type=Path, help="输入 JSON")
    cli.add_argument("--output", required=True, type=Path, help="新建运行目录；非空目录须 --resume")
    cli.add_argument("--mode", choices=["mock", "live"], default="mock")
    cli.add_argument("--provider", choices=["openai", "deepseek", "dashscope"], default="openai",
                     help="live 供应商：OpenAI Responses / DeepSeek Chat / 百炼 Qwen Chat；mock 时不调用供应商")
    cli.add_argument("--max-steps", type=int, default=16, help="累计模型动作上限，1..50")
    cli.add_argument("--now", help="仅 Mock 可用的固定当前时间；必须带时区")
    cli.add_argument("--fail-once", choices=["search_assets", "generate_script", "estimate_cost", "save_plan"],
                     help="注入一次可观察故障；可在 live 模式用于真实模型恢复验收")
    cli.add_argument("--resume", action="store_true", help="从同一输出目录续跑或读取已完成结果")
    return cli


def execute(args) -> tuple[dict, int]:
    if not 1 <= args.max_steps <= 50:
        raise ValueError("--max-steps 必须在 1..50")
    if args.mode == "live" and args.now:
        raise ValueError("live 模式禁止 --now，必须使用实际时间")
    if args.resume and args.fail_once:
        raise ValueError("续跑不能重新注入故障；故障状态已保存在检查点")
    request = read_json(args.input)
    validation = validate_request(request)
    if args.output.exists() and (not args.output.is_dir() or any(args.output.iterdir())) and not args.resume:
        raise ValueError("输出目录非空，拒绝覆盖；续跑请使用 --resume，或换新目录")
    fixed = parse_time(args.now) if args.now else None
    clock = {"kind": "fixed", "value": fixed.isoformat()} if fixed else {"kind": "real"}
    now = (lambda: fixed) if fixed else (lambda: datetime.now(timezone.utc))
    if validation["status"] != "ready":
        if args.resume:
            raise ValueError("补充或修正输入后请使用新输出目录")
        args.output.mkdir(parents=True, exist_ok=True)
        result = {**validation, "mode": args.mode, "request": request, "steps": [],
                  "notice": "输入未齐全或不合法，未调用模型和业务工具"}
        write_json(args.output / "input.json", request)
        write_json(args.output / "output.json", result)
        write_trace(args.output / "trace.jsonl", [])
        return result, 3
    model = MockModel() if args.mode == "mock" else create_live_model(args.provider)
    if args.resume:
        state = read_json(args.output / "state.json")
        if (not isinstance(state, dict) or state.get("schema_version") != 1
                or state.get("request") != request or state.get("clock") != clock
                or state.get("model_identity") != model.identity):
            raise ValueError("检查点版本、输入、时钟或模型配置不匹配；请使用原配置或新目录")
        engine = Engine(request, args.output, now=now, state=state)
        if state.get("rules_fingerprint") != rules_fingerprint(engine.rules):
            raise ValueError("费用或素材规则已变化，不能复用旧检查点")
        if state["status"] == "completed":
            saved = read_json(args.output / "plan.json")
            if saved.get("plan") != state["plan"] or saved.get("cost") != state["final_cost"]:
                raise ValueError("已保存方案与检查点不一致，请检查运行目录")
            return read_json(args.output / "output.json"), 0
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        engine = Engine(request, args.output, now=now)
        engine.state.update(clock=clock, model_identity=model.identity)
        if args.fail_once:
            engine.state["failures_remaining"] = {args.fail_once: 1}
        write_json(args.output / "input.json", request)

    def checkpoint():
        # state.json is authoritative; Trace and output are regenerated from it.
        write_json(args.output / "state.json", engine.state)
        write_trace(args.output / "trace.jsonl", engine.state["events"])
        write_json(args.output / "output.json", summary(engine, model))

    checkpoint()
    result = run_agent(engine, model, max_steps=args.max_steps, checkpoint=checkpoint)
    return result, 0 if result["status"] == "completed" else 3


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        result, code = execute(args)
    except (ValueError, OSError, KeyError, TypeError) as error:
        result, code = {"status": "error", "reason": str(error)}, 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return code
