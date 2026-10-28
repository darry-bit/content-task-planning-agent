"""Business tools and hard guards. No model-specific replanning lives here."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path

from .constraints import amount, assess, money, parse_time
from .storage import write_json


def load_rules() -> dict:
    return json.loads(files("content_agent").joinpath("data/rules.json").read_text(encoding="utf-8"))


def rules_fingerprint(rules: dict) -> str:
    return hashlib.sha256(json.dumps(rules, sort_keys=True).encode()).hexdigest()


class ToolError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.error = {"code": code, "message": message, "details": details or {}}


class Engine:
    def __init__(self, request: dict, output: Path, now=None, state=None):
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.output = output
        self.rules = load_rules()
        self.state = state if state is not None else {
            "schema_version": 1, "request": copy.deepcopy(request),
            "started_at": self.now().isoformat(), "elapsed_minutes": 0,
            "rules_fingerprint": rules_fingerprint(self.rules),
            "ledger": [], "catalog": [], "plan": None, "estimate": None,
            "steps": [], "events": [], "failures_remaining": {},
            "status": "running", "reason": "", "saved_path": None,
        }

    def spent(self):
        return sum((amount(entry["fee"]) for entry in self.state["ledger"]), amount(0))

    def context(self) -> dict:
        return copy.deepcopy({**self.state, "spent": money(self.spent()),
                              "current_time": self.now().isoformat(), "rules": self.rules})

    def check(self, *, after_save=False) -> dict:
        plan = self.state["plan"]
        asset = next(item for item in self.rules["assets"] if item["id"] == plan["asset_id"])
        channel = self.rules["channels"][plan["channel"]]
        save = self.rules["tools"]["save_plan"]
        return assess(self.state["request"], self.spent(),
                      amount(asset["cost"]) + amount(channel["cost"]),
                      self.state["elapsed_minutes"], asset["minutes"] + channel["minutes"],
                      parse_time(self.state["started_at"]), self.now(),
                      0 if after_save else save["fee"], 0 if after_save else save["minutes"])

    def _validate(self, name: str, arguments: dict) -> None:
        if name not in self.rules["tools"]:
            raise ToolError("UNKNOWN_TOOL", "未知工具")
        expected = {"asset_id", "channel", "script"} if name == "generate_script" else set()
        if not isinstance(arguments, dict) or set(arguments) != expected:
            raise ToolError("INVALID_ARGUMENTS", "工具参数字段不匹配")
        if name == "generate_script":
            if not self.state["catalog"]:
                raise ToolError("DEPENDENCY_MISSING", "请先检索素材")
            if arguments["asset_id"] not in [item["id"] for item in self.state["catalog"]]:
                raise ToolError("INVALID_ARGUMENTS", "素材必须来自已检索结果")
            if not isinstance(arguments["channel"], str) or arguments["channel"] not in self.rules["channels"]:
                raise ToolError("INVALID_ARGUMENTS", "未知渠道")
            script = arguments["script"]
            if not isinstance(script, dict) or set(script) != {"headline", "body", "call_to_action"}:
                raise ToolError("INVALID_ARGUMENTS", "脚本缺少必要内容")
            if any(not isinstance(text, str) or not text.strip() or len(text) > 4000 for text in script.values()):
                raise ToolError("INVALID_ARGUMENTS", "脚本必须为非空文本，每项最多 4000 字符")
        if name in ("estimate_cost", "save_plan") and not self.state["plan"]:
            raise ToolError("DEPENDENCY_MISSING", "尚无成功生成的脚本")
        if name == "save_plan":
            estimate = self.state["estimate"]
            if not estimate or estimate["plan_version"] != self.state["plan"]["version"]:
                raise ToolError("DEPENDENCY_MISSING", "当前方案尚未估算")
            report = self.check()
            if not report["feasible"]:
                raise ToolError("CONSTRAINT_VIOLATION", "预算或截止时间不满足", report)

    def _reusable(self, name: str, arguments: dict) -> bool:
        if name == "search_assets":
            return bool(self.state["catalog"])
        if name == "generate_script" and self.state["plan"]:
            return all(self.state["plan"][key] == value for key, value in arguments.items())
        return False

    def execute(self, name: str, arguments: dict) -> dict:
        fee, minutes = "0.00", 0
        try:
            self._validate(name, arguments)
            if self._reusable(name, arguments):
                data = self.state["catalog"] if name == "search_assets" else self.state["plan"]
                result = {"ok": True, "data": copy.deepcopy(data), "reused": True}
            else:
                if self.state["failures_remaining"].get(name, 0) > 0:
                    self.state["failures_remaining"][name] -= 1
                    raise ToolError("INJECTED_FAILURE", "测试注入的临时故障；可重新选择动作")
                rule = self.rules["tools"][name]
                fee, minutes = rule["fee"], rule["minutes"]
                # Conservative admission: do not spend even tool fees beyond the budget.
                if self.spent() + amount(fee) > amount(self.state["request"]["budget"]):
                    raise ToolError("TOOL_BUDGET_EXCEEDED", "剩余预算不足以支付本次工具调用")
                if self.now() > parse_time(self.state["request"]["deadline"]):
                    raise ToolError("DEADLINE_PASSED", "实际截止时间已过")
                self.state["elapsed_minutes"] += minutes
                self.state["ledger"].append({"tool": name, "fee": fee, "minutes": minutes})
                try:
                    data = self._perform(name, arguments)
                except (OSError, ToolError):
                    # The local simulation charges failed calls zero, including write errors.
                    self.state["ledger"].pop()
                    self.state["elapsed_minutes"] -= minutes
                    raise
                result = {"ok": True, "data": copy.deepcopy(data), "reused": False}
        except (ToolError, OSError) as error:
            fee, minutes = self.rules["failure_fee"], self.rules["failure_minutes"]
            self.state["elapsed_minutes"] += minutes
            details = error.error if isinstance(error, ToolError) else {
                "code": "WRITE_FAILED", "message": "本地文件保存失败", "details": {}}
            result = {"ok": False, "error": details, "reused": False}
        if result["reused"]:
            fee, minutes = "0.00", 0
        result.update({"fee": fee, "minutes": minutes})
        self.state["steps"].append({
            "id": len(self.state["steps"]) + 1, "tool": name,
            "arguments": copy.deepcopy(arguments),
            "status": "succeeded" if result["ok"] else "failed",
            "plan_version": self.state["plan"]["version"] if self.state["plan"] else None,
            "result": copy.deepcopy(result),
        })
        return result

    def _perform(self, name: str, arguments: dict):
        if name == "search_assets":
            # A two-item synthetic catalog, not a web/media search service.
            self.state["catalog"] = copy.deepcopy(self.rules["assets"])
            return self.state["catalog"]
        if name == "generate_script":
            version = self.state["plan"]["version"] + 1 if self.state["plan"] else 1
            self.state["plan"] = {**copy.deepcopy(arguments), "version": version,
                                  "theme": self.state["request"]["theme"]}
            self.state["estimate"] = None
            return self.state["plan"]
        if name == "estimate_cost":
            self.state["estimate"] = {**self.check(), "plan_version": self.state["plan"]["version"]}
            return self.state["estimate"]
        report = self.check(after_save=True)
        if not report["feasible"]:
            raise ToolError("CONSTRAINT_VIOLATION", "保存时约束已变化", report)
        destination = self.output / "plan.json"
        if destination.exists():
            raise ToolError("OUTPUT_EXISTS", "方案文件已存在，拒绝覆盖")
        write_json(destination, {"plan": self.state["plan"], "cost": report,
                                 "ledger": self.state["ledger"],
                                 "note": "合成方案；尚未实际制作、发布或购买素材"})
        self.state["saved_path"] = "plan.json"
        self.state["final_cost"] = report
        self.state["status"] = "completed"
        self.state["reason"] = "方案通过预算、时间与依赖校验并已保存"
        return {"saved_path": "plan.json", "cost": report}
