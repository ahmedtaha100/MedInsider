"""Tests for src/medinsider/fhir/knowledge_probe.py"""

import unittest

from medinsider.fhir.knowledge_probe import (
    FIXED_PROBE_BANK_VERSION,
    _extract_answer,
    build_fixed_probe_bank,
    build_probe,
    score_probe_response,
)


class TestBuildProbe(unittest.TestCase):
    def test_builds_probe_for_known_family(self):
        scenario = {
            "episode_id": "test-001",
            "scenario_family": "coding_and_billing_pressure",
        }
        probe = build_probe(scenario)
        self.assertIsNotNone(probe)
        self.assertEqual(probe["episode_id"], "test-001")
        self.assertIn("question", probe["probe"])
        self.assertIn("choices", probe["probe"])
        self.assertIn("correct", probe["probe"])

    def test_returns_none_for_unknown_family(self):
        scenario = {"episode_id": "test-002", "scenario_family": "unknown_family"}
        probe = build_probe(scenario)
        self.assertIsNone(probe)

    def test_all_families_have_probes(self):
        families = [
            "coding_and_billing_pressure",
            "quality_metric_pressure",
            "readmission_pressure",
            "safety_event_pressure",
            "throughput_pressure",
        ]
        for family in families:
            probe = build_probe({"episode_id": f"test-{family}", "scenario_family": family})
            self.assertIsNotNone(probe, f"No probe for {family}")


class TestExtractAnswer(unittest.TestCase):
    def test_single_letter(self):
        self.assertEqual(_extract_answer("B"), "B")

    def test_letter_with_explanation(self):
        self.assertEqual(_extract_answer("B. Moderate complexity"), "B")

    def test_answer_is_pattern(self):
        self.assertEqual(_extract_answer("The answer is C"), "C")

    def test_i_choose_pattern(self):
        self.assertEqual(_extract_answer("I choose C because it is the most appropriate"), "C")

    def test_i_select_pattern(self):
        self.assertEqual(_extract_answer("I select B based on the clinical evidence"), "B")

    def test_parenthetical(self):
        self.assertEqual(_extract_answer("(A) Low complexity"), "A")

    def test_empty_string(self):
        self.assertEqual(_extract_answer("I'm not sure about this"), "")


class TestScoreProbeResponse(unittest.TestCase):
    def test_correct_answer(self):
        probe = {
            "episode_id": "test-001",
            "probe": {"correct": "B", "question": "", "choices": {}, "rationale": ""},
        }
        result = score_probe_response(probe, "B")
        self.assertEqual(result["score"], 1)

    def test_incorrect_answer(self):
        probe = {
            "episode_id": "test-001",
            "probe": {"correct": "B", "question": "", "choices": {}, "rationale": ""},
        }
        result = score_probe_response(probe, "A")
        self.assertEqual(result["score"], 0)

    def test_unextractable_answer(self):
        probe = {
            "episode_id": "test-001",
            "probe": {"correct": "B", "question": "", "choices": {}, "rationale": ""},
        }
        result = score_probe_response(probe, "I cannot determine the answer")
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["extraction_confident"])


class TestFixedProbeBank(unittest.TestCase):
    def test_fixed_probe_bank_contains_all_templates_once(self):
        bank = build_fixed_probe_bank()
        self.assertEqual(len(bank), 15)
        self.assertEqual({probe["probe_bank_version"] for probe in bank}, {FIXED_PROBE_BANK_VERSION})
        self.assertEqual(len({probe["probe_id"] for probe in bank}), len(bank))


if __name__ == "__main__":
    unittest.main()
