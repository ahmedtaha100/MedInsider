import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from medinsider.agents import GeminiAgent, build_agent
from medinsider.api_wrappers import GeminiClient
from medinsider.fhir.logger import FHIRActionLogger
from medinsider.fhir.runner import FHIRScenarioRunner
from medinsider.logger import ActionLogger
from medinsider.runner import ScenarioRunner


class FakeResponse:
    def __init__(self, body: dict):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class GeminiWrapperTests(unittest.TestCase):
    def test_missing_key_raises_clear_error(self):
        with patch.dict(os.environ, {}, clear=True):
            client = GeminiClient()
            with self.assertRaises(RuntimeError) as ctx:
                client.next_action(
                    system_prompt="test",
                    messages=[{"role": "user", "content": "hello"}],
                    tool_names=["read_chart"],
                )
        self.assertIn("GOOGLE_API_KEY or GEMINI_API_KEY is not set", str(ctx.exception))

    def test_request_payload_uses_configured_model_and_json_mode(self):
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = {key.lower(): value for key, value in req.header_items()}
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": '{"action":"finish","params":{}}',
                                    }
                                ]
                            }
                        }
                    ]
                }
            )

        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gemini-test-key"}, clear=True):
            client = GeminiClient(model="gemini-2.5-pro")
            with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
                result = client.next_action(
                    system_prompt="Follow instructions exactly.",
                    messages=[
                        {"role": "user", "content": "hello"},
                        {"role": "assistant", "content": '{"action":"read_chart","params":{}}'},
                    ],
                    tool_names=["read_chart"],
                )

        payload = captured["payload"]
        self.assertEqual(
            captured["url"],
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent",
        )
        self.assertEqual(captured["headers"]["x-goog-api-key"], "gemini-test-key")
        self.assertEqual(captured["timeout"], 60)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(payload["generationConfig"]["maxOutputTokens"], 1024)
        self.assertEqual(payload["contents"][0]["role"], "user")
        self.assertEqual(payload["contents"][1]["role"], "model")
        self.assertIn("Allowed actions: read_chart,finish", payload["system_instruction"]["parts"][0]["text"])
        self.assertEqual(result, {"action": "finish", "params": {}})

    def test_response_parsing_supports_gemini_api_key_alias(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "alternate-key"}, clear=True):
            client = GeminiClient(model="gemini-2.5-pro")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": '{"action":"read_chart","params":{"patient_id":"pat-1"}}',
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ),
            ):
                result = client.next_action(
                    system_prompt="test",
                    messages=[{"role": "user", "content": "hello"}],
                    tool_names=["read_chart"],
                )
        self.assertEqual(result["action"], "read_chart")
        self.assertEqual(result["params"]["patient_id"], "pat-1")

    def test_blocked_response_raises_descriptive_error(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "gemini-test-key"}, clear=True):
            client = GeminiClient(model="gemini-2.5-pro")
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(
                    {
                        "candidates": [],
                        "promptFeedback": {
                            "blockReason": "SAFETY",
                        },
                    }
                ),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    client.next_action(
                        system_prompt="test",
                        messages=[{"role": "user", "content": "hello"}],
                        tool_names=["read_chart"],
                    )
        self.assertIn("gemini_unexpected_response", str(ctx.exception))
        self.assertIn("SAFETY", str(ctx.exception))

    def test_build_agent_supports_gemini_type_keyword(self):
        agent = build_agent(type="gemini", model="gemini-2.5-pro")
        self.assertIsInstance(agent, GeminiAgent)
        self.assertEqual(agent.client.model, "gemini-2.5-pro")

    def test_standard_runner_build_agent_supports_gemini(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ScenarioRunner(ActionLogger(str(Path(temp_dir) / "actions.jsonl")))
            agent = runner.build_agent("gemini", {"gemini_model": "gemini-2.5-pro"})
        self.assertIsInstance(agent, GeminiAgent)
        self.assertEqual(agent.client.model, "gemini-2.5-pro")

    def test_fhir_runner_build_agent_supports_gemini(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FHIRScenarioRunner(FHIRActionLogger(str(Path(temp_dir) / "fhir_actions.jsonl")))
            agent = runner.build_agent("gemini", {"gemini_model": "gemini-2.5-pro"})
        self.assertIsInstance(agent, GeminiAgent)
        self.assertEqual(agent.client.model, "gemini-2.5-pro")


if __name__ == "__main__":
    unittest.main()
