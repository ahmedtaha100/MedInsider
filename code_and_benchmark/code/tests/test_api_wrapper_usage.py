import json
import os
import unittest
import urllib.error
from io import BytesIO
from unittest.mock import patch

from medinsider.api_wrappers import (
    MAX_JSON_OBJECT_CANDIDATES,
    ClaudeClient,
    GeminiClient,
    LocalInferenceClient,
    OpenAIClient,
    _extract_json_object_candidates,
    _parse_json_text,
)


class FakeResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class ApiWrapperUsageTests(unittest.TestCase):
    def test_parse_json_text_rejects_distinct_duplicate_objects(self):
        with self.assertRaises(json.JSONDecodeError):
            _parse_json_text('{"action":"read_chart","params":{}}\n{"action":"finish","params":{}}')

    def test_extract_json_candidates_caps_scan_work(self):
        text = "\n".join(f'{{"candidate": {index}}}' for index in range(MAX_JSON_OBJECT_CANDIDATES + 5))
        candidates = _extract_json_object_candidates(text)
        self.assertEqual(len(candidates), MAX_JSON_OBJECT_CANDIDATES)
        self.assertEqual(json.loads(candidates[-1])["candidate"], MAX_JSON_OBJECT_CANDIDATES - 1)

    def test_openai_client_tracks_resolved_model_and_usage(self):
        responses = [
            FakeResponse(
                {
                    "model": "gpt-5.4-2026-03-05",
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
                    "choices": [{"message": {"content": '{"action":"finish","params":{}}'}}],
                }
            ),
            FakeResponse(
                {
                    "model": "gpt-5.4-2026-03-05",
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
                    "choices": [{"message": {"content": '{"action":"finish","params":{}}'}}],
                }
            ),
        ]
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            client = OpenAIClient(model="gpt-5.4-2026-03-05")
            with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=responses):
                client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
                client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(client.resolved_model, "gpt-5.4-2026-03-05")
        self.assertEqual(client.last_usage, {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5})
        self.assertEqual(client.total_usage, {"input_tokens": 14, "output_tokens": 9, "total_tokens": 23})

    def test_openai_client_repairs_duplicate_json_action(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            client = OpenAIClient(model="gpt-5.4-2026-03-05")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "model": "gpt-5.4-2026-03-05",
                        "usage": {"prompt_tokens": 5, "completion_tokens": 4, "total_tokens": 9},
                        "choices": [
                            {
                                "message": {
                                    "content": (
                                        '{"action":"read_chart","params":{"patient_id":"pat-001"}}\n'
                                        '{"action":"read_chart","params":{"patient_id":"pat-001"}}'
                                    )
                                }
                            }
                        ],
                    }
                ),
            ):
                action = client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(action["action"], "read_chart")
        self.assertEqual(action["params"]["patient_id"], "pat-001")
        self.assertEqual(client.last_parse_mode, "duplicate_json")
        self.assertEqual(client.parse_repair_count, 1)

    def test_claude_client_tracks_resolved_model_and_usage(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = ClaudeClient(model="claude-sonnet-4-6")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "model": "claude-sonnet-4-6-20260301",
                        "usage": {"input_tokens": 9, "output_tokens": 4},
                        "content": [{"text": '{"action":"finish","params":{}}'}],
                    }
                ),
            ):
                client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(client.resolved_model, "claude-sonnet-4-6-20260301")
        self.assertEqual(client.last_usage, {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13})
        self.assertEqual(client.total_usage, {"input_tokens": 9, "output_tokens": 4, "total_tokens": 13})

    def test_claude_client_repairs_wrapped_fenced_json_action(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = ClaudeClient(model="claude-sonnet-4-6")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "model": "claude-sonnet-4-6-20260301",
                        "usage": {"input_tokens": 9, "output_tokens": 4},
                        "content": [
                            {"text": ('Use this exact action:\n``` JSON \n{"action":"finish","params":{}}\n```')}
                        ],
                    }
                ),
            ):
                action = client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(action["action"], "finish")
        self.assertGreaterEqual(client.parse_repair_count, 1)
        self.assertIn(client.last_parse_mode, {"fenced_json", "fence_line_repair", "extracted_json"})

    def test_claude_client_retries_without_temperature_when_model_deprecates_it(self):
        payloads: list[dict[str, object]] = []

        def fake_urlopen(request, timeout=None):
            payload = json.loads(request.data.decode("utf-8"))
            payloads.append(payload)
            if len(payloads) == 1:
                error_payload = json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "`temperature` is deprecated for this model.",
                        },
                    }
                ).encode("utf-8")
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    hdrs=None,
                    fp=BytesIO(error_payload),
                )
            return FakeResponse(
                {
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 10, "output_tokens": 4},
                    "content": [{"text": '{"action":"finish","params":{}}'}],
                }
            )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = ClaudeClient(model="claude-opus-4-7")
            with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
                action = client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])

        self.assertEqual(action["action"], "finish")
        self.assertEqual(client.resolved_model, "claude-opus-4-7")
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["temperature"], 0)
        self.assertNotIn("temperature", payloads[1])

    def test_claude_client_retries_without_temperature_on_broader_deprecation_wording(self):
        payloads: list[dict[str, object]] = []

        def fake_urlopen(request, timeout=None):
            payload = json.loads(request.data.decode("utf-8"))
            payloads.append(payload)
            if len(payloads) == 1:
                error_payload = json.dumps(
                    {
                        "type": "error",
                        "error": {
                            "type": "invalid_request_error",
                            "message": "For this model, temperature has been deprecated. Remove the field.",
                        },
                    }
                ).encode("utf-8")
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    hdrs=None,
                    fp=BytesIO(error_payload),
                )
            return FakeResponse(
                {
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 11, "output_tokens": 5},
                    "content": [{"text": '{"action":"finish","params":{}}'}],
                }
            )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = ClaudeClient(model="claude-opus-4-7")
            with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
                action = client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])

        self.assertEqual(action["action"], "finish")
        self.assertEqual(client.resolved_model, "claude-opus-4-7")
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["temperature"], 0)
        self.assertNotIn("temperature", payloads[1])

    def test_claude_client_retries_without_temperature_when_error_message_falls_after_long_prefix(self):
        payloads: list[dict[str, object]] = []

        def fake_urlopen(request, timeout=None):
            payload = json.loads(request.data.decode("utf-8"))
            payloads.append(payload)
            if len(payloads) == 1:
                error_payload = json.dumps(
                    {
                        "type": "error",
                        "request_id": "x" * 500,
                        "error": {
                            "type": "invalid_request_error",
                            "message": "temperature has been deprecated for this model",
                        },
                    }
                ).encode("utf-8")
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    hdrs=None,
                    fp=BytesIO(error_payload),
                )
            return FakeResponse(
                {
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 12, "output_tokens": 6},
                    "content": [{"text": '{"action":"finish","params":{}}'}],
                }
            )

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
            client = ClaudeClient(model="claude-opus-4-7")
            with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
                action = client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])

        self.assertEqual(action["action"], "finish")
        self.assertEqual(client.resolved_model, "claude-opus-4-7")
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["temperature"], 0)
        self.assertNotIn("temperature", payloads[1])

    def test_gemini_client_tracks_resolved_model_and_usage(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=True):
            client = GeminiClient(model="gemini-2.5-pro")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "modelVersion": "gemini-2.5-pro-002",
                        "usageMetadata": {
                            "promptTokenCount": 8,
                            "candidatesTokenCount": 5,
                            "totalTokenCount": 13,
                        },
                        "candidates": [{"content": {"parts": [{"text": '{"action":"finish","params":{}}'}]}}],
                    }
                ),
            ):
                client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(client.resolved_model, "gemini-2.5-pro-002")
        self.assertEqual(client.last_usage, {"input_tokens": 8, "output_tokens": 5, "total_tokens": 13})
        self.assertEqual(client.total_usage, {"input_tokens": 8, "output_tokens": 5, "total_tokens": 13})

    def test_local_inference_client_tracks_resolved_model_and_usage(self):
        client = LocalInferenceClient(model="openai/gpt-oss-120b", base_url="http://localhost:8000/v1")
        with patch(
            "medinsider.api_wrappers.urllib.request.urlopen",
            return_value=FakeResponse(
                {
                    "model": "openai/gpt-oss-120b-fp8",
                    "usage": {"prompt_tokens": 6, "completion_tokens": 3, "total_tokens": 9},
                    "choices": [{"message": {"content": '{"action":"finish","params":{}}'}}],
                }
            ),
        ):
            client.next_action("test", [{"role": "user", "content": "hello"}], ["read_chart"])
        self.assertEqual(client.resolved_model, "openai/gpt-oss-120b-fp8")
        self.assertEqual(client.last_usage, {"input_tokens": 6, "output_tokens": 3, "total_tokens": 9})
        self.assertEqual(client.total_usage, {"input_tokens": 6, "output_tokens": 3, "total_tokens": 9})


if __name__ == "__main__":
    unittest.main()
