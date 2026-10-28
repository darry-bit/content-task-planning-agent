"""Provider-specific Chat Completions tool calling; no hidden model fallback.

Sources: https://api-docs.deepseek.com/api/create-chat-completion/
https://help.aliyun.com/zh/model-studio/qwen-function-calling
"""
import json
import os

from .agent import ModelError
from .live_model import PROMPT, ResponsesModel, tool_definitions


class ChatCompletionsModel(ResponsesModel):
    def __init__(self, api_key: str, model: str, *, provider: str, base_url: str, transport=None):
        if provider not in ("deepseek", "dashscope"):
            raise ValueError("Chat 适配器仅支持 deepseek 或 dashscope")
        if "{" in base_url or "}" in base_url:
            raise ValueError("请将 API 根地址中的业务空间占位符替换为控制台实际地址")
        super().__init__(api_key, model, base_url=base_url, transport=transport)
        self.provider = provider
        self.endpoint = base_url.rstrip("/") + "/chat/completions"
        self.identity = f"live:chat:{provider}:{self.endpoint}:{self.model}:nonthinking-v1"

    def decide(self, context: dict) -> dict:
        tools = []
        for definition in tool_definitions():
            # DeepSeek strict schemas require its beta endpoint; do not enable implicitly.
            function = {key: value for key, value in definition.items() if key not in ("type", "strict")}
            tools.append({"type": "function", "function": function})
        body = {"model": self.model,
                "messages": [{"role": "system", "content": PROMPT + "\n每轮只选择一个工具；需停止时调用 finish。"},
                             {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
                "tools": tools, "stream": False, "max_tokens": 4096}
        if self.provider == "deepseek":
            body.update(thinking={"type": "disabled"}, tool_choice="required")
        else:
            # Qwen does not guarantee required tool choice; use auto and validate output.
            body.update(enable_thinking=False, tool_choice="auto", parallel_tool_calls=False)
        response = self._send(body)
        try:
            choices = response["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            if choice["finish_reason"] != "tool_calls":
                raise ValueError
            calls = choice["message"]["tool_calls"]
            if not isinstance(calls, list) or len(calls) != 1 or calls[0]["type"] != "function":
                raise ValueError
            function = calls[0]["function"]
            arguments = json.loads(function["arguments"])
            if not isinstance(arguments, dict) or not isinstance(function["name"], str):
                raise ValueError
            reason = arguments.pop("reason")
            if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
                raise ValueError
        except (KeyError, TypeError, ValueError, IndexError):
            raise ModelError("Chat 响应未返回单个有效工具调用，可能被截断或只回复文本；未执行工具，请核对模型工具调用能力后续跑") from None
        # reasoning_content and ordinary prose are deliberately excluded from Trace.
        return {"tool": function["name"], "arguments": arguments, "reason": reason,
                "model_response": {"id": response.get("id"), "usage": response.get("usage")}}


def create_live_model(provider: str):
    prefixes = {"openai": "OPENAI", "deepseek": "DEEPSEEK", "dashscope": "DASHSCOPE"}
    if provider not in prefixes:
        raise ValueError("未知模型供应商")
    prefix = prefixes[provider]
    required = [f"{prefix}_API_KEY", f"{prefix}_MODEL"]
    if provider == "dashscope":
        required.append("DASHSCOPE_BASE_URL")
    missing = [name for name in required if not os.environ.get(name, "").strip()]
    if missing:
        raise ValueError("请在本地配置环境变量：" + ", ".join(missing))
    key, model = (os.environ[f"{prefix}_{suffix}"] for suffix in ("API_KEY", "MODEL"))
    if provider == "openai":
        return ResponsesModel(key, model, base_url=os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1")
    base_url = os.environ.get(f"{prefix}_BASE_URL") or "https://api.deepseek.com"
    return ChatCompletionsModel(key, model, provider=provider, base_url=base_url.strip())
