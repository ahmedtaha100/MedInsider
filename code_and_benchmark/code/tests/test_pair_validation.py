import random
import unittest

from medinsider.fhir.pair_validation import validate_pair_integrity, validate_selected_pairs
from medinsider.fhir.paired_scenario import generate_paired_scenario


class PairValidationTests(unittest.TestCase):
    def test_validate_pair_integrity_accepts_background_pressure_pair(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", "background_pressure", 0, 0, rng)
        self.assertEqual(validate_pair_integrity(neutral, pressure), [])

    def test_validate_pair_integrity_rejects_unexpected_patient_state_difference(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("coding_and_billing_pressure", "direct_incentive", 0, 0, rng)
        pressure["patient_state"]["labs"]["troponin"] = "positive"
        errors = validate_pair_integrity(neutral, pressure)
        self.assertIn("unexpected_payload_difference", errors)

    def test_validate_selected_pairs_requires_complete_pairs(self):
        rng = random.Random(42)
        neutral, pressure = generate_paired_scenario("quality_metric_pressure", "background_pressure", 0, 0, rng)
        report = validate_selected_pairs([neutral, pressure], require_complete_pairs=True)
        self.assertTrue(report["ok"])

        incomplete = validate_selected_pairs([neutral], require_complete_pairs=True)
        self.assertFalse(incomplete["ok"])
        self.assertTrue(any("pair_group_size_invalid" in error for error in incomplete["errors"]))


if __name__ == "__main__":
    unittest.main()
