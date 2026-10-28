# 验收结果与局限

## 供应商扩展验证

2026-10-28 按用户已有渠道增加 DeepSeek 与百炼 Qwen Chat 适配，46 项测试通过（初版为 37 项）。新增协议测试覆盖供应商参数、凭据隔离、业务空间地址配置、无效响应、错误脱敏及检查点身份；受控响应 CLI 集成测试走过超预算反馈循环。日志见 `examples/verification/unittest-providers.txt`。这些均未访问真实模型，不能算作真实模型验收。

## 实际执行环境

2026-10-28，Windows，Python 3.12.14。运行源码无第三方依赖。测试使用工作区临时目录，因为当前沙箱的系统临时目录无法正常写入和清理；切换目录后通过，未跳过测试。

测试命令：`PYTHONPATH=src python -m unittest discover -s tests -v`（PowerShell 设置语法见 README）。共 37 项通过；最终日志位于 `examples/verification/unittest.txt`。构建安装与安装后的 `python -m content_agent` 入口也已执行并通过，记录见 `examples/verification/package-check.json`。

## 必选验收：8 组实际 CLI 运行

批量执行命令：`python scripts/evaluate.py --output examples/runs/offline-v1`。该目录已包含证据，再次验证请换新输出目录。

所有案例模式均为 **mock**，固定业务时钟为 `2026-10-28T10:00:00+08:00`。实际执行时间另记录于 `summary.json`，不把模拟业务时钟当作真实执行时刻。

| 案例目录 | 预期 | 实际 | 关键数值或观察 |
| --- | --- | --- | --- |
| normal | 成功保存 | completed | 总费用 12.70，制作费 12，已发生工具费 0.70 |
| missing-budget | 要求补充预算 | needs_input | missing=[budget]，空 Trace，无模型调用 |
| missing-deadline | 要求补充截止时间 | needs_input | missing=[deadline]，空 Trace，无模型调用 |
| tool-failure | 失败后调整动作 | completed | 估算注入故障后，仅重试估算；脚本版本仍为 1 |
| over-budget | 原方案超限后换方案 | completed | 12.70 → 9.10；新方案 economy/video，版本 2 |
| impossible | 无可行方案 | incomplete | 最后候选预计 7.50，相对预算 3 缺口 4.50；未保存 |
| time-tight | 选择耗时较短的方案 | completed | 最终 economy/post，费用 7.50，满足 10:45 截止 |
| time-impossible | 时间不足 | incomplete | 相对 10:05 截止时间缺口 36 分钟；未保存 |

每个案例目录保存 `input.json`、`output.json`、`trace.jsonl` 和 `command.json`。执行过业务步骤的案例另有 `state.json`；成功案例有 `plan.json`。总览见 `examples/runs/offline-v1/summary.json`。

## 两条可检查的离线路径

正常：search_assets → generate_script → estimate_cost → save_plan。

超预算：search_assets → generate_script(premium/video) → estimate_cost(12.70, infeasible) → generate_script(economy/video) → estimate_cost(9.10, feasible) → save_plan。

超预算第二次估算时已发生工具费为 1.00，制作费为 8.00，预留保存费为 0.10；保存后已发生工具费为 1.10，总费用保持 9.10。不能把 12.70 与 9.10 相加。

这两条路径来自固定 Mock 策略，**不证明模型具有动态决策能力**。它们验证的是执行器、反馈结构、约束和证据记录。

## 加分项：失败步骤续跑与重复执行

实际材料位于 `examples/runs/bonus-v1/`：

1. `before-resume/`：估算故障后达到 3 步上限，状态 incomplete；成功脚本已存在，估算失败仍为 failed。
2. `resume/`：从检查点重试估算并保存，最终脚本版本 1，总费用 12.70。生成脚本仅成功执行一次。
3. 再次 `--resume`：退出码 0，state、trace、plan、output 四个文件的 SHA-256 不变。

三个进程退出码实际为 3 → 0 → 0。摘要及哈希位于 `examples/runs/bonus-v1/summary.json`。复现命令见 README。

## 测试覆盖与审查修复

- 金额使用 Decimal，覆盖零预算、负值、非有限值、小数边界、保存预留费用。
- 时间包含时区、模拟工具耗时、实际当前时间和制作剩余时间；估算通过后若时钟推进，保存仍会被阻止。
- 未检索不能生成；未生成不能估算；未估算或方案变化后不能保存。
- 文件写失败返回 WRITE_FAILED，不报告已保存；模拟失败不收费。
- 未知工具、额外参数和渠道非法类型均转为工具错误，不信任模型参数。
- 模型服务的 HTTP、协议、不完整响应和多工具异常有明确边界；协议替身测试不访问外网。
- 模型 finish 不能直接宣称成功；连续三次失败或累计动作达上限会明确停止。
- 检查点校验输入、时钟、规则和模型身份，完成结果复用时还检查保存文件。

审查发现并修复：渠道参数为 dict/list 时字典查询引发 TypeError。先增加失败用例，再加入显式字符串校验；相关测试通过。此修改由 AI 完成，不列为用户个人贡献。

## 真实模型验收：尚未完成

尚未配置或调用真实模型；没有真实模型 Trace，无法据此宣称满足最终考核的模型决策要求。

用户本地配置后，至少运行两条不同路径，例如正常路径与注入工具失败的恢复路径。检查：模型是否看见失败、是否保留脚本、是否选择重试或合理停止；如果模型没能恢复，保留失败记录并据此修改。供应商模型可能直接选择低成本方案，不保证必然先走超预算分支。

不要只截屏，不要编辑 Trace 伪造路径。将去除敏感信息的真实输入、输出、Trace 和实际结论放入 `examples/`，并补充本节。

## 已知限制

合成目录只有两项，不代表真实检索效果；Mock 文案为模板，不代表真实内容质量。未验证不同真实模型兼容性、内容事实正确性或商业素材授权。实际模型 API 费用不计入模拟单位。续跑为单机顺序检查点，未保证任意强制中断或并发写入时的事务一致性。尚无 GitHub URL、用户实践证据和最终远端提交 SHA。
