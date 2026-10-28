"""Bounded model -> action -> observation loop, independent of model policy."""
import copy

from .constraints import money


class ModelError(Exception):
    """A public, redacted model-service or response-protocol error."""


def summary(engine, model) -> dict:
    state = engine.state
    plan = state["plan"]
    tasks = [
        {"id": "search_assets", "depends_on": [], "status": "succeeded" if state["catalog"] else "pending"},
        {"id": "generate_script", "depends_on": ["search_assets"], "status": "succeeded" if plan else "pending"},
        {"id": "estimate_cost", "depends_on": ["generate_script"], "status": "succeeded" if state["estimate"] else "pending"},
        {"id": "save_plan", "depends_on": ["estimate_cost"], "status": "succeeded" if state["saved_path"] else "pending"},
    ]
    cost = state.get("final_cost") or (engine.check() if plan else {
        "spent": money(engine.spent()), "projected_total": None,
        "budget_gap": None, "time_gap_minutes": None,
    })
    return copy.deepcopy({
        "status": state["status"], "reason": state["reason"],
        "stop_code": state.get("stop_code"), "mode": model.mode,
        "model_identity": model.identity, "request": state["request"],
        "task_plan": tasks, "plan": plan, "steps": state["steps"],
        "cost": cost, "ledger": state["ledger"],
        "elapsed_minutes": state["elapsed_minutes"],
        "saved_path": state["saved_path"], "trace_path": "trace.jsonl",
        "notice": "Mock 只验证流程，不证明真实模型决策。所有业务素材/价格/耗时均为合成数据；未实际制作或发布。",
    })


def run_agent(engine, model, *, max_steps=16, checkpoint=None) -> dict:
    state = engine.state
    checkpoint = checkpoint or (lambda: None)
    if state["status"] == "completed":
        return summary(engine, model)
    state.update(status="running", reason="", stop_code=None)
    failures = 0
    while len(state["events"]) < max_steps:
        try:
            action = model.decide(engine.context())
        except ModelError as error:
            state.update(status="incomplete", reason=str(error), stop_code="MODEL_ERROR")
            state["events"].append({"seq": len(state["events"]) + 1,
                                    "model_error": str(error), "mode": model.mode})
            checkpoint()
            return summary(engine, model)
        valid = (isinstance(action, dict) and isinstance(action.get("tool"), str)
                 and isinstance(action.get("arguments"), dict)
                 and isinstance(action.get("reason"), str) and 0 < len(action["reason"]) <= 1000)
        if not valid:
            action = {"tool": "invalid_action", "arguments": {}, "reason": "模型动作结构无效"}
        if action["tool"] == "finish":
            observation = {"ok": True, "data": {"stopped": True}, "fee": "0.00", "minutes": 0}
            state.update(status="incomplete", reason=action["reason"], stop_code="MODEL_STOP")
        else:
            observation = engine.execute(action["tool"], action["arguments"])
        state["events"].append({
            "seq": len(state["events"]) + 1, "mode": model.mode,
            "action": copy.deepcopy(action), "observation": observation,
            "spent_after": money(engine.spent()),
            "elapsed_minutes_after": state["elapsed_minutes"],
        })
        failures = 0 if observation["ok"] else failures + 1
        if failures >= 3:
            state.update(status="incomplete", reason="连续三次动作失败，已停止并保留成功结果", stop_code="REPEATED_FAILURE")
        checkpoint()
        if state["status"] != "running":
            return summary(engine, model)
    state.update(status="incomplete", reason="达到模型动作上限，已保留状态，可提高上限后续跑", stop_code="STEP_LIMIT")
    checkpoint()
    return summary(engine, model)
