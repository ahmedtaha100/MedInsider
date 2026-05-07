"""Tests for src/medinsider/fhir/validation_extensions.py"""

import unittest

from medinsider.fhir.validation_extensions import (
    assign_tier,
    cohens_kappa,
    compute_dual_kappa_floor,
    extract_atc_labels,
    extract_ivr_labels,
    tier_distribution,
    validate_with_atc,
)


class TestAssignTier(unittest.TestCase):
    def test_tier_a_high_risk_direct(self):
        s = {
            "alignment_label": "conflict",
            "scenario_family": "coding_and_billing_pressure",
            "condition": "direct_incentive",
        }
        self.assertEqual(assign_tier(s), "A")

    def test_tier_b_conflict_moderate(self):
        s = {"alignment_label": "conflict", "scenario_family": "readmission_pressure", "condition": "direct_incentive"}
        self.assertEqual(assign_tier(s), "B")

    def test_tier_c_aligned(self):
        s = {
            "alignment_label": "aligned",
            "scenario_family": "coding_and_billing_pressure",
            "condition": "direct_incentive",
        }
        self.assertEqual(assign_tier(s), "C")

    def test_tier_c_sham(self):
        s = {
            "alignment_label": "conflict",
            "scenario_family": "coding_and_billing_pressure",
            "condition": "sham_placebo",
        }
        self.assertEqual(assign_tier(s), "C")

    def test_tier_c_reverse(self):
        s = {
            "alignment_label": "conflict",
            "scenario_family": "safety_event_pressure",
            "condition": "reverse_incentive",
        }
        self.assertEqual(assign_tier(s), "C")


class TestTierDistribution(unittest.TestCase):
    def test_distribution(self):
        scenarios = [
            {
                "alignment_label": "conflict",
                "scenario_family": "coding_and_billing_pressure",
                "condition": "direct_incentive",
            },
            {"alignment_label": "aligned", "scenario_family": "coding_and_billing_pressure", "condition": "neutral"},
            {
                "alignment_label": "conflict",
                "scenario_family": "readmission_pressure",
                "condition": "background_pressure",
            },
        ]
        dist = tier_distribution(scenarios)
        self.assertEqual(dist["A"], 1)
        self.assertEqual(dist["B"], 1)
        self.assertEqual(dist["C"], 1)


class TestCohensKappa(unittest.TestCase):
    def test_perfect_agreement(self):
        pairs = [(1, 1), (0, 0), (1, 1), (0, 0)]
        k = cohens_kappa(pairs)
        self.assertIsNotNone(k)
        self.assertAlmostEqual(k, 1.0)

    def test_no_agreement(self):
        pairs = [(1, 0), (0, 1), (1, 0), (0, 1)]
        k = cohens_kappa(pairs)
        self.assertIsNotNone(k)
        self.assertLess(k, 0)

    def test_empty(self):
        self.assertIsNone(cohens_kappa([]))


class TestDualKappaFloor(unittest.TestCase):
    def test_both_pass(self):
        good_pairs = [(1, 1), (0, 0), (1, 1), (0, 0), (1, 1)]
        result = compute_dual_kappa_floor(good_pairs, good_pairs)
        self.assertTrue(result["overall_pass"])

    def test_one_fails(self):
        good = [(1, 1), (0, 0), (1, 1), (0, 0)]
        bad = [(1, 0), (0, 1), (1, 0), (0, 1)]
        result = compute_dual_kappa_floor(good, bad)
        self.assertFalse(result["overall_pass"])
        self.assertIsNotNone(result["recommendation"])


class TestExtractLabels(unittest.TestCase):
    def test_extract_ivr(self):
        rows = [
            {"reviewer_1_ivr": "1", "reviewer_2_ivr": "1"},
            {"reviewer_1_ivr": "0", "reviewer_2_ivr": "0"},
            {"reviewer_1_ivr": "", "reviewer_2_ivr": "1"},
        ]
        pairs = extract_ivr_labels(rows)
        self.assertEqual(len(pairs), 2)

    def test_extract_atc(self):
        rows = [
            {"reviewer_1_atc": "yes", "reviewer_2_atc": "yes"},
            {"reviewer_1_atc": "no", "reviewer_2_atc": "yes"},
        ]
        pairs = extract_atc_labels(rows)
        self.assertEqual(len(pairs), 2)

    def test_extract_uppercase_columns(self):
        """Regression: handles reviewer_1_IVR and reviewer_1_ATC column names."""
        rows = [
            {"reviewer_1_IVR": "1", "reviewer_2_IVR": "0"},
            {"reviewer_1_ATC": "yes", "reviewer_2_ATC": "no"},
        ]
        ivr_pairs = extract_ivr_labels(rows)
        atc_pairs = extract_atc_labels(rows)
        self.assertEqual(len(ivr_pairs), 1)
        self.assertEqual(len(atc_pairs), 1)


class TestValidateWithAtc(unittest.TestCase):
    def test_full_validation(self):
        rows = [
            {"reviewer_1_ivr": "1", "reviewer_2_ivr": "1", "reviewer_1_atc": "1", "reviewer_2_atc": "1"},
            {"reviewer_1_ivr": "0", "reviewer_2_ivr": "0", "reviewer_1_atc": "0", "reviewer_2_atc": "0"},
            {"reviewer_1_ivr": "1", "reviewer_2_ivr": "1", "reviewer_1_atc": "1", "reviewer_2_atc": "1"},
            {"reviewer_1_ivr": "0", "reviewer_2_ivr": "0", "reviewer_1_atc": "0", "reviewer_2_atc": "0"},
        ]
        result = validate_with_atc(rows)
        self.assertTrue(result["overall_pass"])


if __name__ == "__main__":
    unittest.main()
