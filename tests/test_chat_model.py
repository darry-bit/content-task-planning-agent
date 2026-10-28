import json
import unittest
from urllib.error import HTTPError
from unittest.mock import patch

from content_agent.agent import ModelError
from content_agent.chat_model import ChatCompletionsModel, create_live_model


def response(arguments=None):
    return {"id": "chat-test", "usage": {"total_tokens": 80}, "choices": [{
        "finish_reason": "tool_calls", "message": {
            "role": "assistant", "reasoning_content": "DO NOT LOG PRIVATE REASONING",
            "tool_calls": [{"type": "function", "id": "call-1", "function": {
                "name": "search_assets", "arguments": json.dumps(arguments if arguments is not None else {"reason": "先检索素材"})}}]}}]}


class ChatModelTests(unittest.TestCase):
    def test_deepseek_chat_protocol_disables_thinking_and_avoids_beta_strict(self):
        def transport(request, timeout):
            self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
            body = json.loads(request.data)
            self.assertEqual(body["thinking"], {"type": "disabled"})
            self.assertEqual(body["tool_choice"], "required")
            self.assertNotIn("parallel_tool_calls", body)
            self.assertNotIn("enable_thinking", body)
            self.assertEqual(body["messages"][0]["role"], "system")
            for tool in body["tools"]:
                self.assertEqual(tool["type"], "function")
                self.assertNotIn("strict", tool["function"])
            return response()

        model = ChatCompletionsModel("test-key", "test-model", provider="deepseek",
                                     base_url="https://api.deepseek.com", transport=transport)
        action = model.decide({"request": {"theme": "咖啡"}, "events": []})
        self.assertEqual(action["tool"], "search_assets")
        self.assertEqual(action["arguments"], {})
        self.assertNotIn("DO NOT LOG", json.dumps(action))
        self.assertNotIn("test-key", json.dumps(action))

    def test_dashscope_uses_qwen_parameters_and_business_space_endpoint(self):
        def transport(request, timeout):
            self.assertEqual(request.full_url, "https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/chat/completions")
            body = json.loads(request.data)
            self.assertFalse(body["enable_thinking"])
            self.assertFalse(body["parallel_tool_calls"])
            self.assertEqual(body["tool_choice"], "auto")
            self.assertNotIn("thinking", body)
            return response()

        model = ChatCompletionsModel("test-key", "test-model", provider="dashscope",
             base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1", transport=transport)
        self.assertEqual(model.decide({})["reason"], "先检索素材")

    def test_incomplete_text_only_or_multiple_calls_do_not_execute_any_tool(self):
        cases = [{}, {"choices": []}, {"choices": [None]}, response([]), response({"reason": ""})]
        truncated = response()
        truncated["choices"][0]["finish_reason"] = "length"
        cases.append(truncated)
        text_only = response()
        text_only["choices"][0]["message"]["tool_calls"] = []
        cases.append(text_only)
        multiple = response()
        multiple["choices"][0]["message"]["tool_calls"] *= 2
        cases.append(multiple)
        for payload in cases:
            with self.subTest(payload=payload):
                model = ChatCompletionsModel("key", "model", provider="deepseek",
                                            base_url="https://api.deepseek.com", transport=lambda *args: payload)
                with self.assertRaises(ModelError):
                    model.decide({})

    def test_factory_does_not_mix_keys_and_requires_explicit_model(self):
        with patch.dict("os.environ", {"OPENAI_API_KEY": "other-key", "OPENAI_MODEL": "other-model"}, clear=True):
            with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
                create_live_model("deepseek")
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "key", "DEEPSEEK_MODEL": "actual-model"}, clear=True):
            model = create_live_model("deepseek")
            self.assertEqual(model.model, "actual-model")
            self.assertIn("deepseek", model.identity)

    def test_dashscope_requires_base_url_from_console(self):
        with patch.dict("os.environ", {"DASHSCOPE_API_KEY": "key", "DASHSCOPE_MODEL": "model"}, clear=True):
            with self.assertRaisesRegex(ValueError, "DASHSCOPE_BASE_URL"):
                create_live_model("dashscope")

    def test_providers_have_different_checkpoint_identities(self):
        models = [ChatCompletionsModel("key", "model", provider=provider,
                  base_url="https://example.com/v1", transport=lambda *args: response())
                  for provider in ["deepseek", "dashscope"]]
        self.assertNotEqual(models[0].identity, models[1].identity)

    def test_chat_http_errors_keep_credentials_and_service_body_private(self):
        def failing(request, timeout):
            raise HTTPError(request.full_url, 429, "sensitive-body", {}, None)
        model = ChatCompletionsModel("test-key", "model", provider="deepseek",
                                    base_url="https://api.deepseek.com", transport=failing)
        with self.assertRaises(ModelError) as caught:
            model.decide({})
        self.assertIn("429", str(caught.exception))
        self.assertNotIn("sensitive-body", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
