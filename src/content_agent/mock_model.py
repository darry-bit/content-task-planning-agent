"""Explicitly scripted offline policy. It is NOT evidence of LLM reasoning."""


class MockModel:
    mode = "mock"
    identity = "mock:scripted-v1"

    def decide(self, context: dict) -> dict:
        def action(tool, reason, arguments=None):
            return {"tool": tool, "arguments": arguments or {}, "reason": reason}

        events = context["events"]
        if events and not events[-1].get("observation", {"ok": True})["ok"]:
            last = events[-1]
            if last["observation"]["error"]["code"] == "INJECTED_FAILURE":
                return action(last["action"]["tool"], "观察到临时工具故障，保留成功成果，只重试失败步骤",
                              last["action"]["arguments"])
            return action("finish", "工具执行受阻，已保留成功成果；请检查最后一次工具错误")
        if not context["catalog"]:
            return action("search_assets", "先获取可用素材及费用、耗时")
        plan, estimate = context["plan"], context["estimate"]
        if not plan:
            candidate = ("premium", "video")
        elif not estimate:
            return action("estimate_cost", "当前脚本已成功，估算费用和截止时间可行性")
        elif estimate["feasible"]:
            return action("save_plan", "估算满足预算和时间要求，申请保存并由程序再次校验")
        else:
            alternatives = [("premium", "video"), ("economy", "video"), ("economy", "post")]
            index = alternatives.index((plan["asset_id"], plan["channel"])) + 1
            if index == len(alternatives):
                return action("finish", f"所有演示候选方案均不可行；预算缺口 {estimate['budget_gap']}，时间缺口 {estimate['time_gap_minutes']} 分钟")
            candidate = alternatives[index]
        return action("generate_script", "根据当前工具观察选择素材与渠道；这是离线规则策略", {
            "asset_id": candidate[0], "channel": candidate[1],
            "script": {
                "headline": f"{context['request']['theme']}：一起参与",
                "body": "用选定素材介绍活动亮点，展示参与步骤和规则。价格、优惠和授权信息须由运营确认。",
                "call_to_action": "查看活动说明，按规则参与",
            },
        })
