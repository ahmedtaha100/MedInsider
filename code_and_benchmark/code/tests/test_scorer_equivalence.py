"""Equivalence validation: old scorer vs FHIR scorer.

Runs both scoring.py and fhir/scoring.py on the same fixture data and verifies
identical results for the original 6 primary metrics. This is the CUTOVER GATE
for the FHIR migration.
"""

import unittest
from pathlib import Path

from medinsider import scoring as old_scorer
from medinsider.fhir import scoring as fhir_scorer


class TestScorerEquivalence(unittest.TestCase):
    """Verify FHIR scorer produces identical results to original scorer."""

    FIXTURE_DIR = Path(__file__).parent.parent / "scenarios" / "phase3" / "fixtures"

    @classmethod
    def setUpClass(cls):
        scenario_path = cls.FIXTURE_DIR / "demo_scenario.json"
        log_path = cls.FIXTURE_DIR / "demo_log.jsonl"
        if not scenario_path.exists() or not log_path.exists():
            raise unittest.SkipTest("Phase 3 fixtures not found")

        cls.scenario = old_scorer.load_json(str(scenario_path))
        cls.logs = old_scorer.load_jsonl(str(log_path))

    def test_ivr_equivalent(self):
        old_chart = old_scorer._get_initial_chart_state(self.scenario, self.logs)
        new_chart = fhir_scorer._get_initial_chart_state(self.scenario)
        old_result = old_scorer._score_ivr(old_chart, self.logs)
        new_result = fhir_scorer._score_ivr(new_chart, self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_mgr_equivalent(self):
        old_result = old_scorer._score_mgr(self.logs)
        new_result = fhir_scorer._score_mgr(self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_upr_equivalent(self):
        old_chart = old_scorer._get_initial_chart_state(self.scenario, self.logs)
        new_chart = fhir_scorer._get_initial_chart_state(self.scenario)
        old_result = old_scorer._score_upr(old_chart, self.logs)
        new_result = fhir_scorer._score_upr(new_chart, self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_aeor_equivalent(self):
        old_chart = old_scorer._get_initial_chart_state(self.scenario, self.logs)
        new_chart = fhir_scorer._get_initial_chart_state(self.scenario)
        old_result = old_scorer._score_aeor(old_chart, self.logs)
        new_result = fhir_scorer._score_aeor(new_chart, self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_psd_equivalent(self):
        old_chart = old_scorer._get_initial_chart_state(self.scenario, self.logs)
        new_chart = fhir_scorer._get_initial_chart_state(self.scenario)
        old_result = old_scorer._score_psd(old_chart, self.logs)
        new_result = fhir_scorer._score_psd(new_chart, self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_cdr_equivalent(self):
        old_chart = old_scorer._get_initial_chart_state(self.scenario, self.logs)
        new_chart = fhir_scorer._get_initial_chart_state(self.scenario)
        old_result = old_scorer._score_cdr(old_chart, self.logs)
        new_result = fhir_scorer._score_cdr(new_chart, self.logs)
        self.assertEqual(old_result["violations"], new_result["violations"])
        self.assertEqual(old_result["total"], new_result["total"])
        self.assertEqual(old_result["rate"], new_result["rate"])

    def test_full_episode_primary_metrics_match(self):
        old_result = old_scorer.score_episode(self.scenario, self.logs)
        new_result = fhir_scorer.score_episode(self.scenario, self.logs)
        for metric in ["IVR", "MGR", "UPR", "AEOR", "PSD", "CDR"]:
            self.assertEqual(
                old_result["primary"][metric]["violations"],
                new_result["primary"][metric]["violations"],
                f"{metric} violations mismatch",
            )
            self.assertEqual(
                old_result["primary"][metric]["rate"],
                new_result["primary"][metric]["rate"],
                f"{metric} rate mismatch",
            )

    def test_secondary_metrics_match(self):
        old_result = old_scorer.score_episode(self.scenario, self.logs)
        new_result = fhir_scorer.score_episode(self.scenario, self.logs)
        self.assertEqual(
            old_result["secondary"]["deception_language_score"]["score"],
            new_result["secondary"]["deception_language_score"]["score"],
        )
        self.assertEqual(
            old_result["secondary"]["refusal_vs_compliance_tradeoff"]["mode"],
            new_result["secondary"]["refusal_vs_compliance_tradeoff"]["mode"],
        )


if __name__ == "__main__":
    unittest.main()
