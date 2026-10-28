# 评估：实际结果、失败与限制

## 执行环境与方法

2026-10-28，Windows，Python 3.12.14。源码运行仅依赖标准库。先执行确定性单元/CLI 测试，再调用真实 DeepSeek API。合成业务数据与真实模型调用严格区分。

当前测试共 51 项，日志 `examples/verification/unittest-final.txt`；题目逐项证据检查见 `examples/verification/submission-check.json`。初版 37 项与供应商扩展 46 项日志保留为真实阶段记录。`examples/manifest.json` 汇总全部 12 个基础案例。

## 4 条真实模型路径

模型：DeepSeek 官方 API 实际返回的可用模型 `deepseek-flash`，使用非思考工具调用；密钥来自本机环境变量，未保存。每轮 Trace 保留 response ID、公开动作依据、参数、usage 与工具观察，不保存内部思维链。

| 案例 | 预期 | 实际 | 证据 |
| --- | --- | --- | --- |
| 正常完成 | 满足约束并保存 | completed；economy/post；6.70 | `examples/runs/live-v1/normal/` |
| 工具失败 | 模型观察失败，保留成功结果后恢复 | completed；估算失败后重试；脚本版本 1；6.70 | `examples/runs/live-v1/tool-failure/` |
| 预算超限 | 观察超限后自主降级并重新估算 | 12.70 → 7.10；premium/video → economy/post；版本 2；completed | `examples/runs/live-v1/budget-replan/` |
| 无可行方案 | 明确未完成及缺口 | incomplete；预计 6.70，相对预算 3 缺口 3.70；未保存 | `examples/runs/live-v1/impossible/` |

四组基础真实案例共 19 次模型调用，服务返回 total_tokens 合计 57733；用量不等于实际货币账单。详见 `examples/runs/live-v1/summary.json`。另有真实续跑的独立调用，不包含在此合计中。

正常路径：search_assets → generate_script → estimate_cost → save_plan。

故障路径：search_assets → generate_script → estimate_cost(failed) → estimate_cost(succeeded) → save_plan。

预算路径：search_assets → generate_script(premium/video) → estimate_cost(12.70, infeasible) → generate_script(economy/post) → estimate_cost(7.10, feasible) → save_plan。

预算输入是合成运营偏好：要求先给出高品质初稿，报价超限时允许模型降级。程序没有强制第二个方案；模型实际根据超限观察选择 economy/post。保留原始 Trace，包括模型公开依据中的个别措辞错误，未润色运行日志。

## 8 组离线验收

固定业务时钟为 2026-10-28T10:00:00+08:00，实际执行时间另记录。Mock 仅验证流程，不证明模型推理。

| 案例 | 预期/实际 | 关键观察 |
| --- | --- | --- |
| normal | completed / completed | 总费用 12.70 |
| missing-budget | needs_input / needs_input | missing=[budget]，空 Trace，无工具调用 |
| missing-deadline | needs_input / needs_input | missing=[deadline]，空 Trace，无工具调用 |
| tool-failure | completed / completed | 保留脚本，估算失败后恢复 |
| over-budget | completed / completed | 12.70 → 9.10，方案版本变化 |
| impossible | incomplete / incomplete | 最后候选 7.50，预算缺口 4.50，无保存 |
| time-tight | completed / completed | 改为较快的 economy/post |
| time-impossible | incomplete / incomplete | 时间缺口 36 分钟，无保存 |

输入、输出、Trace、命令及状态位于 `examples/runs/offline-v1/`。至少三组材料覆盖全部必选点的要求已满足。

## 加分项：真实与离线续跑、重复执行

`examples/runs/live-v1/bonus/` 保存估算故障后达到上限的检查点，以及从该检查点继续的实际结果。真实退出码 3 → 0 → 0；续跑没有重复生成脚本，版本仍为 1，总费用 6.70。重复读取完成结果时，state、trace、plan、output 四个文件 SHA-256 不变，没有新的模型调用。

对应离线证据位于 `examples/runs/bonus-v1/`，最终费用 12.70。前后状态、完整 Trace 与哈希均保留，验收脚本会重新核对哈希。

## 失败与修复

系统 Python 别名和沙箱临时目录不可用，改用可执行的 Python 与工作区临时目录，未跳过测试。参数审查发现渠道为 dict/list 时抛 TypeError；先写回归测试，再加类型校验，错误进入工具观察。文件写失败、过期截止时间、旧估算、无效模型调用、HTTP 错误及动作上限均有测试。

最终首轮全量测试曾出现一个 plan.json 前置产物缺失，日志保留于 `examples/verification/unittest-final-attempt1.txt`。为该用例增加初次 CLI 运行成功断言后，单独及完整 51 项测试通过；首次缺失原因未能稳定复现，不据此宣称修复了已知生产缺陷。

## 局限

文案是模型生成草稿，可能引入用户未给出的活动细节，需运营核实后发布。合成目录不代表真实素材检索或授权，完成只表示方案保存。当前仅验证一家的一个真实模型；百炼和 OpenAI 为协议测试。API 模型结果具有随机性，复现应检查约束和行为，不能要求文案逐字一致。

单机 JSON 检查点不等于事务系统；未实现并发控制或任意强制中断后的精确一次语义。真实模型 API 费用不属于模拟预算，保留 token usage 供核对平台账单。
