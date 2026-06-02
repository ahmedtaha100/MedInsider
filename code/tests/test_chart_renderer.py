"""Tests for src/medinsider/fhir/chart_renderer.py"""

import tempfile
import unittest
from pathlib import Path

from medinsider.fhir.chart_renderer import (
    render_action_log,
    render_patient_state,
    render_scenario_html,
    render_scenario_to_file,
)


def _sample_state():
    return {
        "patient_id": "p1",
        "demographics": {"age": 65, "sex": "M"},
        "problems": {"I10": "active", "E11.9": "active"},
        "vital_signs": {"bp": "130/85", "hr": "78"},
        "labs": {"troponin": "normal", "creatinine": "1.2"},
        "notes": [{"note_id": "admit-1", "section": "assessment", "text": "Initial assessment."}],
        "adverse_events": [{"event_id": "ae-1", "detail": "medication-related hypotension"}],
    }


def _sample_logs():
    return [
        {
            "tool_name": "read_chart",
            "params": {"patient_id": "p1"},
            "result": {"ok": True, "data": {}},
        },
        {
            "tool_name": "write_note",
            "params": {"section": "progress", "text": "Patient stable."},
            "result": {"ok": True, "data": {"text": "Patient stable."}},
        },
        {
            "tool_name": "submit_billing",
            "params": {"icd_codes": ["X99"]},
            "result": {"ok": False, "error": "unsupported_code"},
        },
    ]


class TestRenderPatientState(unittest.TestCase):
    def test_contains_key_sections(self):
        html = render_patient_state(_sample_state())
        self.assertIn("Demographics", html)
        self.assertIn("Active Problems", html)
        self.assertIn("I10", html)
        self.assertIn("Vital Signs", html)
        self.assertIn("Labs", html)
        self.assertIn("troponin", html)
        self.assertIn("Adverse Events", html)
        self.assertIn("ae-1", html)

    def test_empty_state(self):
        result = render_patient_state({})
        self.assertIn("No patient data", result)


class TestRenderActionLog(unittest.TestCase):
    def test_renders_table(self):
        html = render_action_log(_sample_logs())
        self.assertIn("<table>", html)
        self.assertIn("read_chart", html)
        self.assertIn("write_note", html)
        self.assertIn("unsupported_code", html)

    def test_empty_log(self):
        html = render_action_log([])
        self.assertIn("No actions recorded", html)


class TestRenderScenarioHtml(unittest.TestCase):
    def test_full_render(self):
        scenario = {
            "episode_id": "test-001",
            "scenario_family": "coding_and_billing_pressure",
            "condition": "direct_incentive",
            "patient_state": _sample_state(),
        }
        html = render_scenario_html(scenario, _sample_logs())
        self.assertIn("test-001", html)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Patient Chart", html)
        self.assertIn("Agent Actions", html)

    def test_metadata_hidden_by_default(self):
        scenario = {"episode_id": "test-002", "patient_state": {}, "metadata": {"pair_id": "p1"}}
        html = render_scenario_html(scenario)
        self.assertNotIn("Scenario Metadata", html)

    def test_metadata_shown_when_requested(self):
        scenario = {
            "episode_id": "test-003",
            "patient_state": {},
            "metadata": {"pair_id": "p1", "twin_role": "pressure"},
            "scenario_family": "safety_event_pressure",
            "condition": "direct_incentive",
            "alignment_label": "conflict",
        }
        html = render_scenario_html(scenario, include_metadata=True)
        self.assertIn("Scenario Metadata", html)
        self.assertIn("Pair ID", html)


class TestRenderToFile(unittest.TestCase):
    def test_writes_file(self):
        scenario = {"episode_id": "test-file", "patient_state": _sample_state()}
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "chart.html")
            render_scenario_to_file(scenario, path, _sample_logs())
            self.assertTrue(Path(path).exists())
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("test-file", content)


if __name__ == "__main__":
    unittest.main()
