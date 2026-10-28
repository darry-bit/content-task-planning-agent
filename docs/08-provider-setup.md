# DeepSeek 与阿里云百炼：本地真实验收

项目最终共 51 项测试，已通过本机环境变量调用真实 DeepSeek 并保存验收。以下说明用于重新运行或切换百炼；百炼当前只声明协议测试范围。网页聊天账号不等于 API 已开通，请使用 API 控制台中可用的模型和密钥。

## 先使用 DeepSeek

以下为 PowerShell 命令，从项目根目录执行。当前电脑使用已验证的 Codex 内置 Python；其他电脑可替换为标准 Python 3.11+。

```powershell
$pythonExe = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$credential = Get-Credential -UserName "deepseek" -Message "在密码框填写 DeepSeek API Key"
$env:DEEPSEEK_API_KEY = $credential.GetNetworkCredential().Password
$env:DEEPSEEK_MODEL = Read-Host "填写 DeepSeek 控制台实际可用、支持工具调用的模型名"
$env:DEEPSEEK_BASE_URL = "https://api.deepseek.com"
New-Item -ItemType Directory -Force local-runs | Out-Null
$inputData = @{ theme = "校园咖啡店期末促销"; budget = 10; deadline = (Get-Date).AddHours(4).ToString("o") }
$inputData | ConvertTo-Json | Set-Content -Encoding utf8 local-runs/live-input.json
$runTag = Get-Date -Format "yyyyMMdd-HHmmss"
& $pythonExe run.py --input local-runs/live-input.json --mode live --provider deepseek --output "local-runs/deepseek-$runTag-normal"
& $pythonExe run.py --input local-runs/live-input.json --mode live --provider deepseek --fail-once estimate_cost --output "local-runs/deepseek-$runTag-failure"
```

在凭据窗口的密码框输入 API Key；模型名按当前控制台填写，不从旧示例猜测。适配器按 [DeepSeek 官方 Chat Completions 文档](https://api-docs.deepseek.com/api/create-chat-completion/)关闭思考模式以支持 required 工具选择。没有请求内部推理过程，也没有启用 beta strict。

两次运行可能产生实际 API 费用。正常案例不要求模型先走昂贵路径；失败案例观察它是否只重试估算、复用成功脚本，或给出合理停止原因。

## 切换阿里云百炼 Qwen

沿用上面创建的实际输入和 `$pythonExe`，再配置百炼：

```powershell
$credential = Get-Credential -UserName "dashscope" -Message "在密码框填写百炼 API Key"
$env:DASHSCOPE_API_KEY = $credential.GetNetworkCredential().Password
$env:DASHSCOPE_MODEL = Read-Host "填写百炼实际可用、支持非思考工具调用的 Qwen 模型名"
$env:DASHSCOPE_BASE_URL = Read-Host "粘贴控制台当前地域/业务空间的 OpenAI 兼容 API 根地址"
$runTag = Get-Date -Format "yyyyMMdd-HHmmss"
& $pythonExe run.py --input local-runs/live-input.json --mode live --provider dashscope --output "local-runs/dashscope-$runTag-normal"
& $pythonExe run.py --input local-runs/live-input.json --mode live --provider dashscope --fail-once estimate_cost --output "local-runs/dashscope-$runTag-failure"
```

地址必须与 API Key 对应的业务空间和地域匹配。当前 [百炼兼容接口文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)提供按 WorkspaceId 和地域区分的根地址，应从你的控制台复制实际值；不要把花括号占位符直接粘贴进去。根地址末尾通常为 `/compatible-mode/v1`，不要再追加 `/chat/completions`。

按 [百炼官方 Function Calling 文档](https://help.aliyun.com/zh/model-studio/qwen-function-calling)，Qwen 的 required 不能保证工具调用，因此适配器采用 auto、关闭思考和并行调用，并校验返回值。若选到仅支持思考、其他模型家族或不支持这些参数的模型，应重新选择适配范围内的模型，而不是伪造完成结果。

## 查看结果与排查

成功运行退出码为 0；业务未完成或模型调用失败保留输出并返回 3；缺少配置或使用方式错误返回 2。

| 现象 | 检查项 |
| --- | --- |
| 缺少某家环境变量 | 核对 `--provider`，不要把另一家的密钥填进来 |
| HTTP 401/403 | API Key、业务空间、地域及访问权限 |
| HTTP 400 | 模型名、工具调用能力、非思考模式参数及 API 根地址 |
| HTTP 429 | 额度或限流，稍后手动续跑；程序不会隐式重试 |
| 只有文本/多个工具/响应截断 | 会明确停止且不执行该轮工具；核对模型工具协议后续跑 |
| 输出目录非空 | 换新目录，或在原配置下添加 `--resume` |
| 时间不足 | 更新实际输入的截止时间，并使用新目录 |

如需协助排错，只提供 HTTP 状态码、脱敏后的错误或 Trace，别粘贴密钥、认证头或环境变量全集。

## 把实际验收变成贡献证据

亲自核对两条路径：步骤真实状态、预算计算、失败后成功脚本是否保留、是否满足截止时间。将不含敏感数据的实际输入、输出和 Trace 复制到 `examples/runs/` 的新目录，再在 `03-evaluation.md` 补充供应商、模型、日期、预期、实测和局限。

API 接入与本次实际验收由 AI 执行；用户的选题、范围、渠道、验收与交付决策据实记录。将来自己运行或修改时再追加实际证据。协议替身测试不能充当真实模型 Trace，现有 DeepSeek live 目录保存的是实际调用。
