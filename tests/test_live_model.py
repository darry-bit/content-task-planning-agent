import json
import unittest
from urllib.error import HTTPError

from content_agent.agent import ModelError
from content_agent.live_model import ResponsesModel


def response(arguments=None):
    return {"id": "resp_test", "status": "completed", "usage": {"total_tokens": 50}, "output": [
        {"type": "reasoning", "summary": []},
        {"type": "function_call", "name": "search_assets", "call_id": "call_test",
         "arguments": json.dumps(arguments if arguments is not None else {"reason": "先查询素材"})},
    ]}


class LiveModelTests(unittest.TestCase):
    def test_responses_protocol_and_sequential_strict_tools(self):
        captured = {}

        def transport(request, timeout):
            captured.update(json.loads(request.data))
            self.assertEqual(request.full_url, "https://api.openai.com/v1/responses")
            self.assertEqual(timeout, 45)
            return response()

        model = ResponsesModel("test-key", "test-model", transport=transport)
        action = model.decide({"request": {"theme": "咖啡"}})
        self.assertEqual(action["tool"], "search_assets")
        self.assertEqual(action["arguments"], {})
        self.assertEqual(action["reason"], "先查询素材")
        self.assertFalse(captured["parallel_tool_calls"])
        self.assertEqual(captured["tool_choice"], "required")
        self.assertFalse(captured["store"])
        for tool in captured["tools"]:
            self.assertTrue(tool["strict"])
            self.assertFalse(tool["parameters"]["additionalProperties"])
            self.assertEqual(set(tool["parameters"]["required"]), set(tool["parameters"]["properties"]))
        self.assertNotIn("test-key", json.dumps(action))

    def test_http_error_is_redacted(self):
        def failing(request, timeout):
            raise HTTPError(request.full_url, 401, "secret-provider-body", {}, None)

        model = ResponsesModel("test-key", "test-model", transport=failing)
        with self.assertRaises(ModelError) as caught:
            model.decide({})
        self.assertIn("401", str(caught.exception))
        self.assertNotIn("secret-provider-body", str(caught.exception))

    def test_refusal_incomplete_malformed_or_multiple_calls_fail_clearly(self):
        cases = [{"output": []}, {"output": "invalid"}, {"output": [None]},
                 {**response(), "status": "incomplete"}, response([]), response({"reason": 3})]
        multiple = response()
        multiple["output"].append(multiple["output"][-1])
        cases.append(multiple)
        for payload in cases:
            with self.subTest(payload=payload):
                model = ResponsesModel("test-key", "test-model", transport=lambda *args: payload)
                with self.assertRaises(ModelError):
                    model.decide({})

    def test_requires_explicit_credentials_and_secure_endpoint(self):
        for key, model, endpoint in [("", "model", "https://api.openai.com/v1"),
                                     ("key", "", "https://api.openai.com/v1"),
                                     ("key", "model", "http://example.com"),
                                     ("key", "model", "https://user:pass@example.com/v1")]:
            with self.subTest(endpoint=endpoint):
                with self.assertRaises(ValueError):
                    ResponsesModel(key, model, base_url=endpoint)


if __name__ == "__main__":
    unittest.main()
