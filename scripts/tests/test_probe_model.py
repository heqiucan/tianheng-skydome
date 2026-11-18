"""Offline protocol and leak-prevention tests: no real credentials or network."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("probe_model", Path(__file__).parents[1] / "probe_model.py")
probe_model = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe_model)


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.key = Path(self.temp.name) / "key.txt"
        self.fake_secret = "fictional-secret-never-send-this"
        self.key.write_text("\ufeff" + self.fake_secret + "\n", encoding="utf-8")
        self.requests = []

    def tool_response(self):
        return {
            "choices": [{"finish_reason": "tool_calls", "message": {
                "role": "assistant", "content": None,
                "reasoning_content": "PRIVATE REASONING MUST NOT BE SAVED",
                "tool_calls": [{"id": "call-1", "type": "function", "function": {
                    "name": "query_sensor_data",
                    "arguments": json.dumps({"location_id": probe_model.LOCATION_ID}),
                }}],
            }}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25,
                      "unexpected": self.fake_secret},
        }

    def final_response(self):
        return {"choices": [{"finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps({
                "location_id": probe_model.LOCATION_ID,
                "temperature_c": 78, "smoke_alert": True, "is_simulated": True,
            }),
        }}]}

    def test_success_requires_real_tool_protocol_and_grounded_second_response(self):
        def transport(url, key, payload, timeout):
            self.requests.append(payload)
            self.assertEqual(key, self.fake_secret)
            self.assertEqual(timeout, 60)
            if len(self.requests) == 1:
                return self.tool_response()
            protocol = payload["messages"]
            self.assertEqual(protocol[2]["reasoning_content"], "PRIVATE REASONING MUST NOT BE SAVED")
            self.assertEqual(protocol[3]["tool_call_id"], "call-1")
            self.assertEqual(json.loads(protocol[3]["content"])["temperature_c"], 78)
            return self.final_response()

        result, code = probe_model.probe(self.key, transport=transport)
        self.assertEqual(code, 0)
        self.assertTrue(result["verified"])
        self.assertTrue(result["tool_executed"])
        self.assertEqual(result["request_count"], 2)
        serialized = json.dumps(result)
        self.assertNotIn(self.fake_secret, serialized)
        self.assertNotIn("PRIVATE REASONING", serialized)
        self.assertEqual(result["scope"], "isolated_tool_probe")

    def test_rejects_wrong_endpoint_before_loading_key_or_network(self):
        for endpoint in (
            "http://open.bigmodel.cn/api/paas/v4",
            "https://open.bigmodel.cn.evil.example/api/paas/v4",
            "https://user:password@open.bigmodel.cn/api/paas/v4",
            "https://open.bigmodel.cn/api/coding/paas/v4",
            "https://open.bigmodel.cn/api/paas/v4?key=secret",
        ):
            result, code = probe_model.probe(self.key, base_url=endpoint,
                transport=lambda *args: self.fail("network must not be used"))
            self.assertEqual(code, 2)
            self.assertEqual(result["request_count"], 0)
            self.assertFalse(result["configured"])

    def test_text_claiming_a_tool_call_is_not_tool_execution(self):
        def transport(*args):
            return {"choices": [{"message": {"content": "I called query_sensor_data; temperature is 78."}}]}
        result, code = probe_model.probe(self.key, transport=transport)
        self.assertNotEqual(code, 0)
        self.assertEqual(result["request_count"], 1)
        self.assertFalse(result["tool_executed"])
        self.assertFalse(result["verified"])

    def test_unknown_tool_or_injected_arguments_are_never_executed(self):
        for field, value in (("name", "delete_everything"), ("arguments", '{"location_id":"other"}')):
            response = self.tool_response()
            response["choices"][0]["message"]["tool_calls"][0]["function"][field] = value
            result, code = probe_model.probe(self.key, transport=lambda *args: response)
            self.assertNotEqual(code, 0)
            self.assertFalse(result["tool_executed"])
            self.assertEqual(result["request_count"], 1)

    def test_wrong_final_fact_is_not_verified(self):
        count = 0
        def transport(*args):
            nonlocal count
            count += 1
            if count == 1:
                return self.tool_response()
            response = self.final_response()
            response["choices"][0]["message"]["content"] = '{"temperature_c":42,"is_simulated":false}'
            return response
        result, code = probe_model.probe(self.key, transport=transport)
        self.assertNotEqual(code, 0)
        self.assertTrue(result["tool_executed"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["error_category"], "ungrounded_final")

    def test_unexpected_exception_never_leaks_original_message(self):
        def transport(*args):
            raise RuntimeError(self.fake_secret + " PRIVATE RESPONSE")
        result, code = probe_model.probe(self.key, transport=transport)
        self.assertNotEqual(code, 0)
        self.assertNotIn(self.fake_secret, json.dumps(result))
        self.assertNotIn("PRIVATE RESPONSE", json.dumps(result))
        self.assertEqual(result["request_count"], 1)

    def test_failure_does_not_retry_or_increase_tokens(self):
        def transport(url, key, payload, timeout):
            self.requests.append(payload)
            raise probe_model.ProbeError("quota_or_rate_limit", "Safe fixed text", 4, 429)
        result, code = probe_model.probe(self.key, transport=transport)
        self.assertEqual(code, 4)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0]["max_tokens"], 1536)
        self.assertEqual(result["http_status"], 429)


if __name__ == "__main__":
    unittest.main()
