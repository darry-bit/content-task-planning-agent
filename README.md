# 内容任务规划 Agent · 题目 2

帮助运营人员在预算和截止时间内完成内容活动方案。支持素材检索、脚本生成、成本估算和方案保存；模型根据工具观察重新选择动作，程序负责依赖、费用和最终状态校验。

**已完成真实 DeepSeek 验收、离线回归、失败续跑及重复执行验证。** 真实模型为 `deepseek-flash`；百炼 Qwen 和 OpenAI 入口也已实现并经过协议测试，尚未声称它们完成真实调用。项目使用合成业务数据，未实际购买素材或发布内容。

仓库：[darry-bit/content-task-planning-agent](https://github.com/darry-bit/content-task-planning-agent)。提交信息见 [SUBMISSION.md](SUBMISSION.md)。AI 使用与个人贡献如实记录在 [docs/04-ai-usage.md](docs/04-ai-usage.md)。

## 评审入口

1. [逐条验收对照表](docs/09-acceptance-matrix.md)：每个题目要求对应代码、测试或实际证据。
2. [实际评估结果](docs/03-evaluation.md)：12 组材料、4 条真实模型路径与已知限制。
3. [真实预算重规划 Trace](examples/runs/live-v1/budget-replan/trace.jsonl)：预计费用 12.70 → 7.10，实际切换方案后重新估算并保存。
4. [真实故障恢复 Trace](examples/runs/live-v1/tool-failure/trace.jsonl)：保留成功脚本，只重试失败的估算。
5. [真实失败续跑与幂等证据](examples/runs/live-v1/bonus/summary.json)：退出码 3 → 0 → 0，重复读取时四个产物哈希不变。

## 环境与零安装运行

Python 3.11+，仅使用标准库，运行源码不需要安装依赖。以下命令从项目根目录执行。

```powershell
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/demo
python scripts/evaluate.py --output local-runs/offline-evaluation
python scripts/verify_submission.py
```

`--now` 只在 Mock 下可用，使历史案例可复现。输出目录必须为空；不要覆盖仓库中的实际证据。批量离线验收包含正常、缺预算、缺截止时间、工具故障、超预算、无可行方案及时间约束。

当前作者电脑的 `python` 命令指向不可用的 Windows 别名，可使用已经验证的内置运行时：

```powershell
$pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $pythonExe run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/first-run
```

其他命令中的 `python` 同样可替换为 `& $pythonExe`。评审使用普通 Python 即可，不依赖 Codex。

## 安装方式与自动化测试

```powershell
python -m pip install -e .
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
python -m content_agent --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --output local-runs/module-demo
```

未安装时也可以用 `run.py`；Unix 测试命令为 `PYTHONPATH=src python -m unittest discover -s tests -v`。测试不调用真实 API。安装的构建后端为 setuptools，运行依赖为空。

`verify_submission.py` 检查全部案例状态、费用账本、保存结果、截止时间、失败恢复、真实模型 response ID、不同 live 路径，以及续跑产物哈希；完整清单为 `examples/manifest.json`。该工具检查证据一致性，不把 Mock 当成真实模型效果。

## 实际输入与输出

```json
{"theme":"校园咖啡店期末活动","budget":10,"deadline":"2026-10-28T18:00:00+08:00"}
```

主题、预算和带时区的截止时间为必填；缺失返回 needs_input，不猜测、不调用业务工具。预算最多两位小数，单位为模拟单位。

每次运行生成 `input.json`、`output.json`、`trace.jsonl`、`state.json`；只有实际保存成功才生成 `plan.json` 并报告 completed。缺参数案例无执行检查点，Trace 为空。输出包含工具依赖计划、每次步骤真实状态、当前方案、脚本、费用账本、预估完成时间及保存位置或未完成原因。

## 真实模型复现

无需部署模型，直接调用平台 API。密钥从环境变量读取，不写入输入、Trace 或 Git；程序不会自动加载 `.env`。每轮 API 调用可能产生实际费用。

| 供应商 | 参数 | 环境变量 |
| --- | --- | --- |
| DeepSeek | `--provider deepseek` | `DEEPSEEK_API_KEY`、`DEEPSEEK_MODEL`，可选 `DEEPSEEK_BASE_URL` |
| 百炼 Qwen | `--provider dashscope` | `DASHSCOPE_API_KEY`、`DASHSCOPE_MODEL`、控制台实际 `DASHSCOPE_BASE_URL` |
| OpenAI | `--provider openai` | `OPENAI_API_KEY`、`OPENAI_MODEL`，可选 `OPENAI_BASE_URL` |

本项目实际验收使用 `DEEPSEEK_MODEL=deepseek-flash` 和 `https://api.deepseek.com`。按本地可用模型配置；两家协议细节与安全输入方法见 [供应商指南](docs/08-provider-setup.md)。

仓库中的真实输入保留执行当时的日期。重跑前应创建新的实际截止时间，不要在 live 模式使用 `--now`：

```powershell
New-Item -ItemType Directory -Force local-runs | Out-Null
$env:DEEPSEEK_MODEL = "deepseek-flash"
# 确保 DEEPSEEK_API_KEY 已在当前进程或新终端中继承；不要将密钥写入命令历史。
$inputData = @{theme="校园咖啡店期末活动";budget=10;deadline=(Get-Date).AddHours(6).ToString("o")}
$inputData | ConvertTo-Json | Set-Content -Encoding utf8 local-runs/live-input.json
python run.py --input local-runs/live-input.json --mode live --provider deepseek --output local-runs/live-normal
python run.py --input local-runs/live-input.json --mode live --provider deepseek --fail-once estimate_cost --output local-runs/live-failure
```

真实预算重规划案例的输入明确提出“先出 premium/video 初稿，取得工具估算后如超限允许降级”。这是合成运营偏好，未强制模型选择降级方案；实际模型根据 12.70 的观察改用 economy/post，重新估算为 7.10。不要修改实际 Trace 来迎合预期。

## 重复执行、失败续跑与退出码

```powershell
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --fail-once estimate_cost --max-steps 3 --output local-runs/resume
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --resume --output local-runs/resume
python run.py --input examples/inputs/normal.json --mode mock --now 2026-10-28T10:00:00+08:00 --resume --output local-runs/resume
```

首条故意在失败后达到上限；第二条保留已成功脚本并续跑；第三条读取完成结果，不再调用模型或收费工具。真实模式也支持同样流程。输入、规则、时钟和模型身份必须匹配；续跑不能再次注入故障。`--max-steps` 为累计动作上限，最大 50。

退出码 0：完成；3：业务未完成、需补信息或模型服务错误；2：配置、文件或调用方式错误。模型 finish 只能结束为未完成，不能自行宣称保存成功。连续三次动作失败会停止，历史失败不会改写成成功。

## 费用和时间口径

总费用 = 已发生工具费用 + 当前方案预计制作费用 + 尚未发生的保存费用。历史估算值不累加；换方案不会退还已发生工具费。检索/脚本/估算/保存分别收费 0.20/0.30/0.10/0.10，模拟失败不收费。

素材 premium/economy 分别为 8/4；渠道 video/post 制作费为 4/2。正常离线路径费用 12.70，离线预算调整为 9.10；真实模型自主选择低成本路径为 6.70，真实预算调整为 7.10。真实 API 账单与模拟单位分开，usage 记录于 Trace。

预计完成时间使用 `max(开始时间 + 已发生模拟工具耗时, 实际当前时间) + 剩余制作耗时 + 保存耗时`；保存前再次检查。修改方案会使旧估算失效。工具仅模拟业务耗时，不真实睡眠。

## 结构、取舍与边界

`src/content_agent/`：执行器、工具、约束、模型适配器、CLI；`tests/`：可执行测试；`examples/`：输入、真实输出及 Trace；`docs/01..05`：需求、方案、评估、AI 使用和复盘。合成规则唯一来源为 `src/content_agent/data/rules.json`，随包发布，根目录 `data/README.md` 解释数据边界。

单 Agent 和 CLI 聚焦核心链路；框架不作加分依据，因此不增加界面、多 Agent 或生产 Runtime。Mock 的固定策略仅用于确定性测试；live 的下一动作来自模型。脚本生成工具登记模型提供的脚本，不隐含额外模型调用。

已知限制：素材目录仅两项；文案仍需运营核实事实与权益；未实现真实媒体检索、授权审核、制作与发布。检查点适用于单进程顺序执行，不保证断电或并发下精确一次。当前真实效果只验证 DeepSeek；不宣称所有供应商或模型都能得到相同路径。
