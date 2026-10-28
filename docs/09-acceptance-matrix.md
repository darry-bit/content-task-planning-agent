# 题目 2：逐条验收对照

| 题目要求 | 实现/证据 | 结论 |
| --- | --- | --- |
| 帮运营人员在预算和截止时间内完成内容活动方案 | request 输入、Engine、最终计划/脚本/费用/预计完成时间 | 已实现 |
| 主题、预算、截止时间 | constraints.py；缺预算与缺截止时间案例 | 已实现 |
| 合成素材、工具费用和耗时表 | src/content_agent/data/rules.json；data/README.md | 已提供 |
| 素材检索、脚本生成、成本估算、方案保存 | tools.py 四工具；live 参数脚本由模型生成 | 已实现 |
| 模型选择动作 → 执行工具 → 观察 → 再选择 | agent.py；真实工具 Trace 与 response ID | 已真实运行 |
| 根据超限、错误或部分成功调整动作 | live 预算 12.70→7.10；估算故障后仅重试失败步骤 | 已真实验证 |
| 保留成功结果，不将失败记为成功 | 历史 failed 步骤与脚本版本；真实续跑 | 已验证 |
| 无可行方案说明原因/缺口 | live impossible：incomplete、缺口 3.70，无 plan.json | 已验证 |
| 正常完成、缺预算/时间、工具失败、预算超限 | manifest 中 12 组案例共同覆盖；至少三组要求已超过 | 已覆盖 |
| 至少两条不同执行路径 | 4 条真实基础路径，正常/故障/预算/停止不同 | 已提供 |
| 动作、参数、结果摘要、后续动作、公开依据 | trace.jsonl；不记录模型内部推理链 | 已提供 |
| 调用/步数上限且返回明确未完成状态 | max-steps、连续失败停止；真实故障后达到上限的检查点 | 已验证 |
| CLI/API/Notebook 三选一与复制命令 | Python CLI；README 的零安装、安装和真实调用命令 | 已提供 |
| Mock 入口且明确边界 | mock_model.py；每条输出/Trace 标记 mode | 已提供 |
| 代码、tests、examples、data、依赖与环境示例 | 同仓库目录、pyproject.toml、.env.example | 已提供 |
| docs/01–05 五份文档 | 需求、方案、评估、AI 使用、复盘 | 已提供 |
| 实际用时与未完成项 | 05-retrospective.md 记录可观察阶段历时和范围 | 已记录 |
| AI 辅助、个人贡献与验证 | 04-ai-usage.md 按实际角色说明，无虚构手写经历 | 已记录 |
| 重复执行、失败续跑（加分） | live-v1/bonus 与 bonus-v1，产物哈希一致 | 已真实验证 |
| 题号、GitHub URL、最终 commit SHA | SUBMISSION.md 与最终交付信息；远端 main | 交付时核对 |
| 不上传密钥/隐私 | 发布前检查当前文件和提交内容，密钥仅来自本机环境 | 已检查 |

机器核对入口：`python scripts/verify_submission.py`。这不替代评审对业务合理性、个人掌握程度和文案质量的判断；已知限制见评估与复盘。
