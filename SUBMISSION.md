# 提交信息

- 题号：2
- 题目：内容任务规划 Agent
- GitHub：https://github.com/darry-bit/content-task-planning-agent
- 默认分支：main
- 可见性：Public（按用户最终更正）
- 最终 commit SHA：以 `git rev-parse HEAD` 或 GitHub main 分支当前提交为准；最终聊天交付同时提供完整 SHA。

## 最短评审步骤

```powershell
git clone https://github.com/darry-bit/content-task-planning-agent.git
cd content-task-planning-agent
python scripts/verify_submission.py
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

现有真实模型材料可离线审查，无需评审提供密钥；如需重新运行真实模型，按 README 配置 API 并更新截止时间。51 项测试与证据检查不调用外部模型。

验收对照、实际结果、AI 辅助与个人贡献分别见 docs/09、03、04。
