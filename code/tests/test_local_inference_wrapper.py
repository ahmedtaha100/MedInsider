import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from medinsider.agents import LocalInferenceAgent, build_agent
from medinsider.api_wrappers import LocalInferenceClient
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


class LocalInferenceWrapperTests(unittest.TestCase):
    def test_request_payload_and_response_parsing(self):
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = {key.lower(): value for key, value in req.header_items()}
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"action":"finish","params":{}}',
                            }
                        }
                    ]
                }
            )

        client = LocalInferenceClient(
            model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
            base_url="http://localhost:8000/v1",
            api_key="local-token",
        )
        with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
            result = client.next_action(
                system_prompt="Follow instructions exactly.",
                messages=[{"role": "user", "content": "hello"}],
                tool_names=["read_chart"],
            )

        payload = captured["payload"]
        self.assertEqual(captured["url"], "http://localhost:8000/v1/chat/completions")
        self.assertEqual(captured["headers"]["authorization"], "Bearer local-token")
        self.assertEqual(captured["timeout"], 60)
        self.assertEqual(payload["model"], "meta-llama/Llama-4-Scout-17B-16E-Instruct")
        self.assertEqual(payload["response_format"]["type"], "json_object")
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["max_tokens"], 1024)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(result, {"action": "finish", "params": {}})

    def test_request_payload_supports_temperature_override(self):
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"action":"finish","params":{}}',
                            }
                        }
                    ]
                }
            )

        client = LocalInferenceClient(
            model="kimi-k2.6",
            base_url="https://api.moonshot.ai/v1",
            temperature=1,
        )
        with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
            client.next_action(
                system_prompt="Follow instructions exactly.",
                messages=[{"role": "user", "content": "hello"}],
                tool_names=["read_chart"],
            )

        self.assertEqual(captured["payload"]["temperature"], 1)

    def test_request_payload_supports_thinking_override(self):
        captured: dict[str, object] = {}

        def fake_urlopen(req, timeout):
            captured["payload"] = json.loads(req.data.decode("utf-8"))
            return FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"action":"finish","params":{}}',
                            }
                        }
                    ]
                }
            )

        client = LocalInferenceClient(
            model="kimi-k2.6",
            base_url="https://api.moonshot.ai/v1",
            temperature=0.6,
            thinking={"type": "disabled"},
        )
        with patch("medinsider.api_wrappers.urllib.request.urlopen", side_effect=fake_urlopen):
            client.next_action(
                system_prompt="Follow instructions exactly.",
                messages=[{"role": "user", "content": "hello"}],
                tool_names=["read_chart"],
            )

        self.assertEqual(captured["payload"]["temperature"], 0.6)
        self.assertEqual(captured["payload"]["thinking"], {"type": "disabled"})

    def test_network_error_is_wrapped(self):
        client = LocalInferenceClient(
            model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
            base_url="http://localhost:8000/v1",
        )
        with patch(
            "medinsider.api_wrappers.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection refused"),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                client.next_action(
                    system_prompt="test",
                    messages=[{"role": "user", "content": "hello"}],
                    tool_names=["read_chart"],
                )
        self.assertIn("local_inference_network_error", str(ctx.exception))

    def test_build_agent_supports_openweight_type_keyword(self):
        agent = build_agent(
            type="openweight",
            model="meta-llama/Llama-4-Scout-17B-16E-Instruct",
            base_url="http://localhost:8000/v1",
        )
        self.assertIsInstance(agent, LocalInferenceAgent)
        self.assertEqual(agent.client.model, "meta-llama/Llama-4-Scout-17B-16E-Instruct")
        self.assertEqual(agent.client.base_url, "http://localhost:8000/v1")

    def test_build_agent_supports_openai_compatible_type_keyword(self):
        agent = build_agent(
            type="openai_compatible",
            model="qwen3.5-plus-2026-02-15",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        self.assertIsInstance(agent, LocalInferenceAgent)
        self.assertEqual(agent.client.model, "qwen3.5-plus-2026-02-15")
        self.assertEqual(agent.client.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_build_agent_supports_openai_compatible_thinking(self):
        agent = build_agent(
            type="openai_compatible",
            model="kimi-k2.6",
            base_url="https://api.moonshot.ai/v1",
            temperature=0.6,
            thinking={"type": "disabled"},
        )
        self.assertIsInstance(agent, LocalInferenceAgent)
        self.assertEqual(agent.client.thinking, {"type": "disabled"})

    def test_build_agent_requires_non_empty_openweight_model(self):
        with self.assertRaises(ValueError) as ctx:
            build_agent(type="openweight", model="   ")
        self.assertIn("openweight_model", str(ctx.exception))

    def test_build_agent_requires_non_empty_openai_compatible_model(self):
        with self.assertRaises(ValueError) as ctx:
            build_agent(type="openai_compatible", model="   ")
        self.assertIn("openai_compatible_model", str(ctx.exception))

    def test_build_agent_requires_openai_compatible_base_url(self):
        with self.assertRaises(ValueError) as ctx:
            build_agent(type="openai_compatible", model="kimi-k2.6")
        self.assertIn("openai_compatible_base_url", str(ctx.exception))

    def test_standard_runner_build_agent_supports_openweight(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ScenarioRunner(ActionLogger(str(Path(temp_dir) / "actions.jsonl")))
            agent = runner.build_agent(
                "openweight",
                {
                    "openweight_model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
                    "openweight_base_url": "http://localhost:8000/v1",
                },
            )
        self.assertIsInstance(agent, LocalInferenceAgent)
        self.assertEqual(agent.client.model, "meta-llama/Llama-4-Scout-17B-16E-Instruct")

    def test_standard_runner_requires_openweight_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = ScenarioRunner(ActionLogger(str(Path(temp_dir) / "actions.jsonl")))
            with self.assertRaises(ValueError) as ctx:
                runner.build_agent("openweight", {})
        self.assertIn("openweight_model", str(ctx.exception))

    def test_fhir_runner_build_agent_supports_openweight(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FHIRScenarioRunner(FHIRActionLogger(str(Path(temp_dir) / "fhir_actions.jsonl")))
            agent = runner.build_agent(
                "openweight",
                {
                    "openweight_model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
                    "openweight_base_url": "http://localhost:8000/v1",
                },
            )
        self.assertIsInstance(agent, LocalInferenceAgent)
        self.assertEqual(agent.client.model, "meta-llama/Llama-4-Scout-17B-16E-Instruct")

    def test_fhir_runner_requires_openweight_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = FHIRScenarioRunner(FHIRActionLogger(str(Path(temp_dir) / "fhir_actions.jsonl")))
            with self.assertRaises(ValueError) as ctx:
                runner.build_agent("openweight", {})
        self.assertIn("openweight_model", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
