"""Pure validation and deterministic budget/time calculations."""
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def amount(value: object) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite() or number < 0:
        raise ValueError("费用必须为非负有限数")
    return number


def money(value: object) -> str:
    return str(amount(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("时间必须带时区，如 +08:00")
    return parsed


def validate_request(request: object) -> dict:
    if not isinstance(request, dict):
        return {"status": "invalid_input", "reason": "输入必须为 JSON 对象"}
    missing = [key for key in ("theme", "budget", "deadline")
               if key not in request or request[key] is None or request[key] == ""]
    if missing:
        return {"status": "needs_input", "missing": missing}
    try:
        if not isinstance(request["theme"], str) or not request["theme"].strip():
            raise ValueError("theme 必须为非空文本")
        if len(request["theme"]) > 1000:
            raise ValueError("theme 长度不能超过 1000")
        if isinstance(request["budget"], bool) or not isinstance(request["budget"], (int, float)):
            raise ValueError("budget 必须为数值")
        budget = amount(request["budget"])
        if budget > 1000000 or budget != budget.quantize(Decimal("0.01")):
            raise ValueError("budget 最大 1000000，最多两位小数")
        parse_time(request["deadline"])
    except (ValueError, TypeError, InvalidOperation, OverflowError) as error:
        return {"status": "invalid_input", "reason": str(error)}
    return {"status": "ready"}


def assess(request: dict, spent: object, production_cost: object,
           elapsed_minutes: int, production_minutes: int,
           started_at: datetime, now: datetime, save_fee: object,
           save_minutes: int) -> dict:
    total = amount(spent) + amount(production_cost) + amount(save_fee)
    # Simulated business minutes and real elapsed time are checked independently.
    execution_end = max(started_at + timedelta(minutes=elapsed_minutes), now)
    finish = execution_end + timedelta(minutes=production_minutes + save_minutes)
    deadline = parse_time(request["deadline"])
    gap = max(Decimal(0), total - amount(request["budget"]))
    seconds_late = max(0, (finish - deadline).total_seconds())
    return {
        "spent": money(spent), "production_cost": money(production_cost),
        "save_fee_reserved": money(save_fee), "projected_total": money(total),
        "budget_gap": money(gap),
        "projected_finish": finish.isoformat(),
        "time_gap_minutes": round(seconds_late / 60, 3),
        "feasible": gap == 0 and seconds_late == 0,
    }
