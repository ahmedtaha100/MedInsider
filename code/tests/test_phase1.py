import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from medinsider.agents import ScriptedAgent
from medinsider.api_wrappers import OpenAIClient
from medinsider.ehr_tools import ToolEnvironment
from medinsider.logger import ActionLogger
from medinsider.runner import ScenarioRunner
from medinsider.state import PatientEpisodeState

REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_SCENARIO = str(REPO_ROOT / "scenarios/phase1/billing_conflict_episode.json")
INVALID_SHORT_SCENARIO = str(REPO_ROOT / "scenarios/phase1/invalid_short_episode.json")


class Phase1RunnerTests(unittest.TestCase):
    def test_runner_generates_parseable_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "action_log.jsonl")
            logger = ActionLogger(log_path)
            runner = ScenarioRunner(logger)
            summary = runner.run(VALID_SCENARIO, agent_type="scripted")

            self.assertEqual(summary["tool_calls"], 9)
            self.assertEqual(summary["termination_reason"], "finish")
            self.assertTrue(os.path.exists(log_path))

            with open(log_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            self.assertEqual(len(lines), 10)
            first = json.loads(lines[0])
            self.assertEqual(first["episode_id"], "phase1-billing-001")
            self.assertEqual(first["tool_name"], "read_chart")
            last = json.loads(lines[-1])
            self.assertEqual(last["tool_name"], "finish")

    def test_runner_enforces_minimum_call_constraint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "action_log.jsonl")
            logger = ActionLogger(log_path)
            runner = ScenarioRunner(logger)
            with self.assertRaises(ValueError) as ctx:
                runner.run(INVALID_SHORT_SCENARIO, agent_type="scripted")
            self.assertIn("episode_tool_call_constraint_violation", str(ctx.exception))

    def test_dispatch_bad_params_returns_error(self):
        state = PatientEpisodeState.from_payload(
            "episode-x",
            {
                "patient_id": "patient-x",
            },
        )
        env = ToolEnvironment(state)
        result = env.dispatch("read_chart", {"wrong_key": "patient-x"})
        self.assertFalse(result["ok"])
        self.assertTrue(result["error"].startswith("bad_params:"))

    def test_generated_ids_do_not_reuse_seeded_ids(self):
        state = PatientEpisodeState.from_payload(
            "episode-y",
            {
                "patient_id": "patient-y",
                "notes": [{"note_id": "note-aaaaaaaaaaaa", "section": "a", "text": "b"}],
                "orders": [{"order_id": "order-aaaaaaaaaaaa", "order_type": "lab", "details": {}}],
                "billing_submissions": [{"billing_id": "bill-aaaaaaaaaaaa", "cpt_codes": [], "icd_codes": []}],
                "staff_messages": [{"message_id": "msg-aaaaaaaaaaaa", "role": "rn", "message": "x"}],
                "quality_reports": [{"report_id": "quality-aaaaaaaaaaaa", "metric": "m", "value": "v"}],
            },
        )
        env = ToolEnvironment(state)

        note_result = env.write_note("progress", "new note")
        order_result = env.place_order("lab", {"test": "cbc"})
        bill_result = env.submit_billing(["99232"], ["I10"])
        msg_result = env.message_staff("care_manager", "follow-up")
        quality_result = env.quality_report("metric", "value")

        self.assertNotEqual(note_result["data"]["note_id"], "note-aaaaaaaaaaaa")
        self.assertNotEqual(order_result["data"]["order_id"], "order-aaaaaaaaaaaa")
        self.assertNotEqual(bill_result["data"]["billing_id"], "bill-aaaaaaaaaaaa")
        self.assertNotEqual(msg_result["data"]["message_id"], "msg-aaaaaaaaaaaa")
        self.assertNotEqual(quality_result["data"]["report"]["report_id"], "quality-aaaaaaaaaaaa")

    def test_quality_report_can_record_adverse_event(self):
        state = PatientEpisodeState.from_payload(
            "episode-ae",
            {
                "patient_id": "patient-ae",
                "adverse_events": [],
            },
        )
        env = ToolEnvironment(state)
        result = env.quality_report("adverse_event_fall", "Patient slipped in room")
        self.assertIsNotNone(result["data"]["adverse_event"])
        self.assertEqual(len(state.adverse_events), 1)
        self.assertEqual(state.adverse_events[0]["label"], "adverse_event_fall")

    def test_tool_return_data_is_not_live_reference(self):
        state = PatientEpisodeState.from_payload(
            "episode-live",
            {
                "patient_id": "patient-live",
                "notes": [{"note_id": "n0", "section": "s", "text": "t"}],
            },
        )
        env = ToolEnvironment(state)

        read_result = env.read_note("n0")
        read_result["data"]["text"] = "changed"
        self.assertEqual(state.notes[0]["text"], "t")

        write_result = env.write_note("progress", "new")
        write_result["data"]["text"] = "changed"
        self.assertNotEqual(state.notes[-1]["text"], "changed")

        order_result = env.place_order("lab", {"panel": {"name": "cmp"}})
        order_result["data"]["details"]["panel"]["name"] = "mutated"
        self.assertEqual(state.orders[-1]["details"]["panel"]["name"], "cmp")

    def test_runner_logs_agent_output_error_without_json_crash(self):
        class BrokenAgent:
            def next_action(self, system_prompt, messages, tool_names):
                raise ValueError("bad_action_json")

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "action_log.jsonl")
            logger = ActionLogger(log_path)
            runner = ScenarioRunner(logger)
            runner.build_agent = lambda agent_type, scenario: BrokenAgent()

            with self.assertRaises(ValueError) as ctx:
                runner.run(VALID_SCENARIO, agent_type="scripted")
            self.assertIn("episode_tool_call_constraint_violation", str(ctx.exception))

            with open(log_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertEqual(lines[-1]["tool_name"], "__agent__")
            self.assertIn("agent_action_error", lines[-1]["result"]["error"])

    def test_state_from_payload_does_not_alias_mutable_collections(self):
        payload = {
            "patient_id": "patient-z",
            "notes": [],
            "orders": [],
            "billing_submissions": [],
            "staff_messages": [],
            "quality_reports": [],
            "adverse_events": [],
            "problems": {"I10": "active"},
        }
        state = PatientEpisodeState.from_payload("episode-z", payload)
        state.notes.append({"note_id": "n1"})
        state.problems["E11"] = "active"
        self.assertEqual(payload["notes"], [])
        self.assertEqual(payload["problems"], {"I10": "active"})

    def test_discharge_plan_returns_previous_value(self):
        state = PatientEpisodeState.from_payload("episode-d", {"patient_id": "patient-d"})
        env = ToolEnvironment(state)
        first = env.discharge_plan("first plan")
        second = env.discharge_plan("second plan")
        self.assertEqual(first["data"]["previous_plan_text"], "")
        self.assertEqual(second["data"]["previous_plan_text"], "first plan")

    def test_openai_client_handles_unexpected_response_shape(self):
        class FakeResponse:
            def __init__(self, body: bytes):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return self.body

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = OpenAIClient()
            with patch(
                "medinsider.api_wrappers.urllib.request.urlopen",
                return_value=FakeResponse(b'{"choices": []}'),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    client.next_action(
                        system_prompt="test",
                        messages=[{"role": "user", "content": "hello"}],
                        tool_names=["read_chart"],
                    )
                self.assertIn("openai_unexpected_response", str(ctx.exception))

    def test_logger_sequence_resets_per_episode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "action_log.jsonl")
            logger = ActionLogger(log_path)
            runner = ScenarioRunner(logger)

            runner.run(VALID_SCENARIO, agent_type="scripted")
            runner.run(VALID_SCENARIO, agent_type="scripted")

            with open(log_path, "r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f if line.strip()]

            self.assertEqual(lines[0]["sequence"], 1)
            self.assertEqual(lines[9]["sequence"], 10)
            self.assertEqual(lines[10]["sequence"], 1)
            self.assertEqual(lines[19]["sequence"], 10)

    def test_update_problem_list_response_is_not_live_reference(self):
        state = PatientEpisodeState.from_payload(
            "episode-p",
            {
                "patient_id": "patient-p",
                "problems": {"I10": "active"},
            },
        )
        env = ToolEnvironment(state)
        result = env.update_problem_list("E11", "active")
        result["data"]["problems"]["Z99"] = "active"
        self.assertNotIn("Z99", state.problems)

    def test_chart_snapshot_returns_copied_collections(self):
        state = PatientEpisodeState.from_payload(
            "episode-s",
            {
                "patient_id": "patient-s",
                "problems": {"I10": "active"},
                "notes": [{"note_id": "a"}],
            },
        )
        snapshot = state.chart_snapshot()
        snapshot["problems"]["E11"] = "active"
        snapshot["notes"].append({"note_id": "b"})
        self.assertNotIn("E11", state.problems)
        self.assertEqual(len(state.notes), 1)

    def test_runner_starts_with_user_message_for_agent(self):
        class CaptureAgent:
            def __init__(self):
                self.first_messages = None

            def next_action(self, system_prompt, messages, tool_names):
                if self.first_messages is None:
                    self.first_messages = list(messages)
                return {"action": "finish", "params": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = os.path.join(temp_dir, "action_log.jsonl")
            logger = ActionLogger(log_path)
            runner = ScenarioRunner(logger, min_calls=0, max_calls=20)
            agent = CaptureAgent()
            runner.build_agent = lambda agent_type, scenario: agent
            with open(VALID_SCENARIO, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            scenario["episode_length_min"] = 0
            scenario["episode_length_max"] = 1
            scenario_path = os.path.join(temp_dir, "scenario.json")
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f)
            runner.run(scenario_path, agent_type="scripted")
            self.assertTrue(agent.first_messages)
            self.assertEqual(agent.first_messages[0]["role"], "user")

    def test_runner_invalid_constraint_error_contains_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(VALID_SCENARIO, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            scenario["episode_length_min"] = 50
            scenario["episode_length_max"] = 1
            scenario_path = os.path.join(temp_dir, "invalid_constraints.json")
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f)

            logger = ActionLogger(os.path.join(temp_dir, "action_log.jsonl"))
            runner = ScenarioRunner(logger)
            with self.assertRaises(ValueError) as ctx:
                runner.run(scenario_path, agent_type="scripted")
            self.assertIn("invalid_episode_constraints:effective_min=", str(ctx.exception))

    def test_runner_context_window_is_limited(self):
        class WindowAgent:
            def __init__(self):
                self.message_counts = []
                self.turn = 0

            def next_action(self, system_prompt, messages, tool_names):
                self.message_counts.append(len(messages))
                self.turn += 1
                if self.turn == 1:
                    return {"action": "read_chart", "params": {"patient_id": "patient-001"}}
                return {"action": "finish", "params": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(VALID_SCENARIO, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            scenario["episode_length_min"] = 0
            scenario["episode_length_max"] = 10
            scenario_path = os.path.join(temp_dir, "window_scenario.json")
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f)

            logger = ActionLogger(os.path.join(temp_dir, "action_log.jsonl"))
            runner = ScenarioRunner(logger, min_calls=0, max_calls=20, context_window_pairs=1)
            agent = WindowAgent()
            runner.build_agent = lambda agent_type, scenario: agent
            runner.run(scenario_path, agent_type="scripted")
            self.assertTrue(agent.message_counts)
            self.assertLessEqual(max(agent.message_counts), 3)

    def test_runner_context_window_can_be_zero(self):
        class WindowAgent:
            def __init__(self):
                self.message_counts = []
                self.turn = 0

            def next_action(self, system_prompt, messages, tool_names):
                self.message_counts.append(len(messages))
                self.turn += 1
                if self.turn == 1:
                    return {"action": "read_chart", "params": {"patient_id": "patient-001"}}
                return {"action": "finish", "params": {}}

        with tempfile.TemporaryDirectory() as temp_dir:
            with open(VALID_SCENARIO, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            scenario["episode_length_min"] = 0
            scenario["episode_length_max"] = 10
            scenario_path = os.path.join(temp_dir, "window_zero_scenario.json")
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f)

            logger = ActionLogger(os.path.join(temp_dir, "action_log.jsonl"))
            runner = ScenarioRunner(logger, min_calls=0, max_calls=20, context_window_pairs=0)
            agent = WindowAgent()
            runner.build_agent = lambda agent_type, scenario: agent
            runner.run(scenario_path, agent_type="scripted")
            self.assertTrue(agent.message_counts)
            self.assertLessEqual(max(agent.message_counts), 1)

    def test_runner_resets_reused_scripted_agent_index(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(VALID_SCENARIO, "r", encoding="utf-8") as f:
                scenario = json.load(f)
            scenario["episode_length_min"] = 0
            scenario["episode_length_max"] = 5
            scenario["scripted_actions"] = [
                {"action": "read_chart", "params": {"patient_id": scenario["patient_state"]["patient_id"]}},
                {"action": "finish", "params": {}},
            ]
            scenario_path = os.path.join(temp_dir, "reused_scripted_agent.json")
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f)

            logger = ActionLogger(os.path.join(temp_dir, "action_log.jsonl"))
            runner = ScenarioRunner(logger, min_calls=0, max_calls=20)
            reused_agent = ScriptedAgent(scenario["scripted_actions"])
            runner.build_agent = lambda agent_type, scenario: reused_agent

            first = runner.run(scenario_path, agent_type="scripted")
            second = runner.run(scenario_path, agent_type="scripted")

            self.assertEqual(first["tool_calls"], 1)
            self.assertEqual(second["tool_calls"], 1)

    def test_cli_returns_clean_error_for_missing_scenario(self):
        cmd = [
            sys.executable,
            "-m",
            "medinsider.cli",
            "--scenario",
            str(REPO_ROOT / "does_not_exist.json"),
            "--agent",
            "scripted",
        ]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error:", result.stderr)


if __name__ == "__main__":
    unittest.main()
