# 内容任务规划 Agent

为运营人员在预算和截止时间约束内规划内容活动。模型选择动作，本地工具执行，工具结果反馈给模型；程序负责费用、时间、依赖和最终状态的硬校验。

**交付状态：离线流程与协议测试已通过；真实模型动态决策尚未验收。** Mock 策略含固定分支，仅用于复现和自动化测试，不能作为真实 ReAct 效果证明。本项目初版由 Codex AI 辅助生成，个人贡献记录见 `docs/04-ai-usage.md`。

## 评审入口

1. 查看 `docs/01-requirements.md`：目标、范围和验收标准。
2. 执行下面的快速运行和测试命令。
3. 查看 `examples/runs/offline-v1/summary.json` 和各案例的 `trace.jsonl`。
4. 查看 `docs/03-evaluation.md`：预期与实际结果、真实模型待验收项。
5. 查看 `docs/04-ai-usage.md`：AI 使用范围、个人贡献证据。

## 环境与快速运行

需要 Python 3.11+；运行源码无需第三方依赖。以下命令均从项目根目录执行，PowerShell、cmd、常见 Unix shell 均可运行基础命令。

当前电脑的 `python` 命令指向不可用的 Windows 别名。已验证可用的本地运行时如下；你可以先用它运行，无需立即安装 Python：

```powershell
$pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $pythonExe run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/first-run
```

下面通用命令中的 `python` 在当前电脑上可替换为 `& $pythonExe`；交给评审时使用标准 Python 3.11+ 即可，不依赖 Codex 运行时。

```powershell
python --version
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/normal
python run.py --input examples/inputs/over-budget.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/budget
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --fail-once estimate_cost --output local-runs/failure
```

`--now` 只用于 Mock 固定时钟，使示例在以后仍可复现。每次用新输出目录；运行不会静默覆盖旧证据。不要把输出设为已有的 `examples/runs/offline-v1`。

运行后生成：

| 文件 | 内容 |
| --- | --- |
| `input.json` | 实际输入 |
| `output.json` | 任务计划、当前状态、费用、历史步骤及未完成原因 |
| `trace.jsonl` | 每一步模型动作、参数、公开依据、工具观察及账本摘要 |
| `state.json` | 续跑检查点，包含成功结果及规则/配置指纹 |
| `plan.json` | 仅成功保存时存在；包含脚本、素材、渠道和费用 |

缺参数时只写输入、输出和空 Trace，未调用模型和工具，无可续跑检查点。补齐参数后使用新目录。

可选安装方式：

```powershell
python -m pip install -e .
python -m content_agent --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/module
```

安装需要 setuptools 构建后端；源码运行入口 `run.py` 不需要安装。

## 测试与一键离线验收

PowerShell：

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python scripts/evaluate.py --output local-runs/evaluation
```

Unix shell 的测试入口：`PYTHONPATH=src python -m unittest discover -s tests -v`。

测试包括预算与时间边界、工具故障、结果复用、依赖失效、模型协议、CLI 以及续跑。批量验收执行 8 个真实 CLI 子进程，记录各自输出、Trace 和命令，汇总到 `summary.json`。其中业务未完成返回退出码 3，批量验收将符合预期的未完成视为通过。

如果受限 Windows 沙箱禁止写系统临时目录，可在运行测试前创建工作区临时目录，并将当前进程的 `TEMP`、`TMP` 指向它；普通 Python 环境通常无需此操作。

## 真实模型运行

适配器实现 OpenAI **Responses API** 的函数调用协议。`OPENAI_BASE_URL` 是 API 根地址，例如 `https://api.openai.com/v1`，程序会追加 `/responses`。其他服务必须兼容此协议；仅兼容 Chat Completions 的服务不能直接接入。

模型名不写死，需选择账号实际可用且支持该协议的模型。按 [OpenAI 官方函数调用文档](https://developers.openai.com/api/docs/guides/function-calling)核实供应商能力。当前采用每轮发送完整状态快照的方式，使模型读取工具观察后选择下一步；未使用服务端会话存储。

PowerShell 中只在本地设置变量。下面的密钥读取方式避免将密钥作为明文命令写入历史：

```powershell
$credential = Get-Credential -UserName "api" -Message "在密码框填写 API Key"
$env:OPENAI_API_KEY = $credential.GetNetworkCredential().Password
$env:OPENAI_MODEL = Read-Host "填写账号实际可用的模型名"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
```

程序不自动加载 `.env`，`.env.example` 仅列变量名。不要把密钥放在 JSON、源码、Trace、截图或 Git 中。

示例截止日期是历史固定时钟数据。真实模式运行前先生成一份新的实际输入：

```powershell
New-Item -ItemType Directory -Force local-runs | Out-Null
$liveInput = @{ theme = "校园咖啡店期末促销"; budget = 10; deadline = (Get-Date).AddHours(4).ToString("o") }
$liveInput | ConvertTo-Json | Set-Content -Encoding utf8 local-runs/live-input.json
python run.py --input local-runs/live-input.json --mode live --output local-runs/live-normal
python run.py --input local-runs/live-input.json --mode live --fail-once estimate_cost --output local-runs/live-failure
```

真实模式禁止 `--now`，使用实际时间；可用故障注入观察模型是否调整动作并保留成功结果。两次命令可能产生 API 费用。模型可能直接选到低成本方案，这是允许的；不要为了“看起来会重规划”篡改 Trace。若未观察到预算重规划，应如实记录，并用失败注入展示另一条真实反馈路径。

工具的模拟单位与 API 账单分开。Trace 记录服务返回的 response ID 与 token usage，但不计算未知的实际货币费用，不保存内部思维链。HTTP/网络错误不会自动重试，避免隐藏的重复 API 消耗；修复配置后可续跑。

## 重复执行与失败后续跑

```powershell
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --fail-once estimate_cost --max-steps 3 --output local-runs/resume-demo
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --resume --output local-runs/resume-demo
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --resume --output local-runs/resume-demo
```

第一条故意停止在估算失败后，退出码为 3；第二条仅重试估算并保存，第三条读取已完成结果，不再调用模型或收费工具。不要给续跑重新添加 `--fail-once`。`--max-steps` 是整个检查点累计动作上限，最大 50。

输入、模型身份、规则和固定时钟必须匹配。相同脚本和检索结果在同一检查点内复用；不同输出目录视为独立运行，不提供全局去重。当前只支持单进程顺序运行，禁止两个进程同时写同一目录。

## 费用、时间和状态

- 费用 = 已发生工具费用 + 当前方案预计制作费用 + 尚未发生的保存费用。历史估算值不累加，历史成功生成的工具费用不会因换方案而退款。
- 工具费：检索 0.20、脚本 0.30、估算 0.10、保存 0.10；模拟失败费用为 0。素材：premium 8、economy 4；制作：video 4、post 2。
- 时间 = `max(开始时间 + 已发生模拟工具耗时, 实际当前时间)` + 素材准备和渠道制作耗时 + 预留保存耗时。失败也消耗 1 模拟分钟，不进行真实睡眠。
- 修改方案使旧估算失效，保存前重新检查当前预算、实际时间与依赖。
- `completed` 仅代表方案已保存，未执行实际制作、购买、发布。
- `needs_input` 表示信息不足；`invalid_input` 表示字段不合法；`incomplete` 表示已明确停止；`error` 表示配置、文件或调用方式错误。
- 退出码：0 = 已完成；3 = 业务未完成/需补信息；2 = 配置或使用错误。

正常路径预计总费用 12.70；预算 10 的离线调整路径为 12.70 → 9.10。具体明细可直接对照 Trace 和规则文件。

## 目录与已知限制

源代码位于 `src/content_agent/`，合成规则唯一来源为其 `data/rules.json`；根目录 `data/README.md` 解释数据边界。`docs/` 包含题目要求的五份文档，额外的 `06-personal-contribution-guide.md` 提供个人实作路线。

当前没有真实模型运行证据、线上部署、真实媒体检索、授权系统或发布执行；Mock 脚本是模板文本。检查点使用本地 JSON，不保证进程在保存与写检查点之间被强制终止时仍能精确一次恢复；文件损坏需要人工检查。没有并发锁，未做生产安全审计。

## 提交 GitHub 前

1. 用自己的身份完成并提交真实的个人修改与验证；现有本地初版提交作者明确标记为 `Codex AI`。
2. 跑真实模型的至少两条不同路径，核对并保存公开工具 Trace；只复制不含隐私和密钥的输入及结果到 `examples/`，在评估文档补上结果。
3. 填写 `docs/04-ai-usage.md` 和复盘中的用户待完成项，不把计划写成经历。
4. 推送到你的 GitHub 仓库，保证评审可读，再提交题号 2、仓库 URL 和最终 `git rev-parse HEAD`。

本项目尚未创建或推送远端 GitHub 仓库。不要在完成真实验收前声称已满足模型动态决策要求。
