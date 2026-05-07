"""Tests for src/medinsider/fhir/paired_scenario.py"""

import csv
import json
import random
import tempfile
import unittest
from pathlib import Path

from medinsider.fhir.paired_scenario import (
    FAMILIES,
    PER_CELL,
    PRESSURE_CONDITIONS,
    generate_paired_scenario,
    generate_v2_dataset,
)


class TestGeneratePairedScenario(unittest.TestCase):
    def test_twins_have_identical_patient_state(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", "direct_incentive", 0, 0, rng)
        self.assertEqual(
            neutral["patient_state"]["patient_id"],
            pressure["patient_state"]["patient_id"],
        )
        self.assertEqual(
            neutral["patient_state"]["problems"],
            pressure["patient_state"]["problems"],
        )
        self.assertEqual(
            neutral["patient_state"]["labs"],
            pressure["patient_state"]["labs"],
        )

    def test_twins_have_identical_constraints(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("safety_event_pressure", "direct_incentive", 0, 0, rng)
        self.assertEqual(
            neutral["ground_truth_constraints"],
            pressure["ground_truth_constraints"],
        )

    def test_twins_have_identical_reference_actions(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("readmission_pressure", "background_pressure", 0, 0, rng)
        self.assertEqual(
            neutral["reference_actions"],
            pressure["reference_actions"],
        )

    def test_twins_have_identical_shortcut_cue(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", "direct_incentive", 0, 0, rng)
        self.assertEqual(
            neutral["tempting_misaligned_shortcut"],
            pressure["tempting_misaligned_shortcut"],
        )

    def test_only_framing_differs(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("quality_metric_pressure", "direct_incentive", 0, 0, rng)
        self.assertEqual(neutral["condition"], "neutral")
        self.assertEqual(pressure["condition"], "direct_incentive")
        self.assertNotEqual(neutral["incentive_framing"], pressure["incentive_framing"])
        self.assertNotEqual(neutral["system_prompt"], pressure["system_prompt"])

    def test_twins_share_pair_id(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("readmission_pressure", "background_pressure", 1, 5, rng)
        self.assertEqual(
            neutral["metadata"]["pair_id"],
            pressure["metadata"]["pair_id"],
        )

    def test_twin_roles_correct(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", "direct_incentive", 0, 0, rng)
        self.assertEqual(neutral["metadata"]["twin_role"], "neutral")
        self.assertEqual(pressure["metadata"]["twin_role"], "pressure")

    def test_background_pressure_twin_has_inbox(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("quality_metric_pressure", "background_pressure", 0, 0, rng)
        neutral_inbox = neutral["patient_state"].get("inbox_messages", [])
        pressure_inbox = pressure["patient_state"].get("inbox_messages", [])
        self.assertEqual(len(neutral_inbox), 0)
        self.assertGreater(len(pressure_inbox), 0)

    def test_all_pressure_conditions_valid(self):
        rng = random.Random(42)
        for cond in PRESSURE_CONDITIONS:
            neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", cond, 0, 0, rng)
            self.assertEqual(neutral["condition"], "neutral")
            self.assertEqual(pressure["condition"], cond)

    def test_safety_event_reference_actions_are_honest(self):
        """Regression: reference actions must use honest baseline (conflict=False)."""
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("safety_event_pressure", "direct_incentive", 0, 0, rng)
        for twin in (neutral, pressure):
            for action in twin["reference_actions"]:
                params = action.get("params", {})
                text = params.get("text", "") + params.get("value", "")
                self.assertNotIn("No adverse event", text)
                self.assertNotIn("no_adverse_event", text)

    def test_honesty_prompt_includes_guardrail_cue(self):
        """Regression: honesty_system_prompt must include the guardrail cue."""
        rng = random.Random(42)
        _, pressure = generate_paired_scenario("coding_and_billing_pressure", "honesty_system_prompt", 0, 0, rng)
        self.assertIn("Integrity guardrail cue:", pressure["system_prompt"])

    def test_aligned_pressure_conditions_have_aligned_label(self):
        """reverse_incentive and honesty_system_prompt are aligned pressure."""
        rng = random.Random(42)
        for cond in ("reverse_incentive", "honesty_system_prompt"):
            _, pressure = generate_paired_scenario("coding_and_billing_pressure", cond, 0, 0, rng)
            self.assertEqual(pressure["alignment_label"], "aligned")

    def test_conflict_pressure_conditions_have_conflict_label(self):
        """direct_incentive, background_pressure etc. are conflict pressure."""
        rng = random.Random(42)
        for cond in ("direct_incentive", "background_pressure", "sham_placebo"):
            _, pressure = generate_paired_scenario("coding_and_billing_pressure", cond, 0, 0, rng)
            self.assertEqual(pressure["alignment_label"], "conflict")


class TestGenerateV2Dataset(unittest.TestCase):
    def test_generates_correct_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = generate_v2_dataset(tmpdir, seed=42)
            expected = len(FAMILIES) * len(PRESSURE_CONDITIONS) * PER_CELL * 2
            self.assertEqual(summary["total_scenarios"], expected)
            self.assertEqual(summary["neutral_count"], expected // 2)
            self.assertEqual(summary["pressure_count"], expected // 2)

    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_v2_dataset(tmpdir, seed=42)
            generated = Path(tmpdir) / "generated"
            artifacts = Path(tmpdir) / "artifacts"
            self.assertTrue(generated.exists())
            self.assertTrue(artifacts.exists())
            self.assertTrue((artifacts / "v2_manifest.csv").exists())
            self.assertTrue((artifacts / "v2_generation_summary.json").exists())
            json_files = list(generated.glob("*.json"))
            self.assertGreater(len(json_files), 0)

    def test_manifest_has_twin_role_and_pair_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_v2_dataset(tmpdir, seed=42)
            manifest = Path(tmpdir) / "artifacts" / "v2_manifest.csv"
            with manifest.open("r") as f:
                reader = csv.DictReader(f)
                row = next(reader)
                self.assertIn("pair_id", row)
                self.assertIn("twin_role", row)
                self.assertIn("pressure_condition", row)

    def test_scenario_files_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_v2_dataset(tmpdir, seed=42)
            generated = Path(tmpdir) / "generated"
            for path in list(generated.glob("*.json"))[:5]:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn("episode_id", data)
                self.assertIn("patient_state", data)
                self.assertIn("alignment_label", data)

    def test_no_episode_id_collisions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generate_v2_dataset(tmpdir, seed=42)
            generated = Path(tmpdir) / "generated"
            ids = [p.stem for p in generated.glob("*.json")]
            self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
