import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "build_phase4_v2_manifests.py"
SPEC = importlib.util.spec_from_file_location("build_phase4_v2_manifests", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BuildPhase4V2ManifestTests(unittest.TestCase):
    def test_larger_pilot_selections_cover_required_conditions_and_families(self):
        specs = MODULE.LARGER_PILOT_SELECTIONS
        self.assertEqual(len(specs), 60)

        families = {family for family, _, _, _, _ in specs}
        pressure_conditions = {pressure_condition for _, pressure_condition, _, _, _ in specs}
        sample_ids = {sample_idx for _, _, sample_idx, _, _ in specs}

        self.assertEqual(
            families,
            {
                "coding_and_billing_pressure",
                "quality_metric_pressure",
                "readmission_pressure",
                "safety_event_pressure",
                "throughput_pressure",
            },
        )
        self.assertEqual(
            pressure_conditions,
            {
                "background_pressure",
                "sham_placebo",
                "reverse_incentive",
                "honesty_system_prompt",
            },
        )
        self.assertEqual(sample_ids, {"000", "001", "002"})

    def test_selection_rows_rejects_duplicate_source_keys(self):
        scenarios = [
            {
                "episode_id": "episode-a",
                "scenario_family": "coding_and_billing_pressure",
                "_sample_idx": "000",
                "metadata": {
                    "pair_id": "pair-a",
                    "pressure_condition": "background_pressure",
                    "twin_role": "neutral",
                },
                "condition": "neutral",
                "alignment_label": "neutral",
            },
            {
                "episode_id": "episode-b",
                "scenario_family": "coding_and_billing_pressure",
                "_sample_idx": "000",
                "metadata": {
                    "pair_id": "pair-b",
                    "pressure_condition": "background_pressure",
                    "twin_role": "neutral",
                },
                "condition": "neutral",
                "alignment_label": "neutral",
            },
        ]

        with self.assertRaisesRegex(ValueError, "selection_manifest_source_duplicate"):
            MODULE._selection_rows(
                scenarios,
                [
                    (
                        "coding_and_billing_pressure",
                        "background_pressure",
                        "000",
                        "background_pressure_vs_neutral",
                        "duplicate_test",
                    )
                ],
            )


if __name__ == "__main__":
    unittest.main()
