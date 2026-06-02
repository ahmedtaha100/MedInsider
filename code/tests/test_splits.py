"""Tests for src/medinsider/fhir/splits.py"""

import tempfile
import unittest
from pathlib import Path

from medinsider.fhir.splits import (
    assign_splits,
    generate_split_manifests,
    verify_public_subset_coverage,
)


def _scenarios():
    scenarios = []
    for i in range(100):
        scenarios.append(
            {
                "episode_id": f"ep-{i:03d}",
                "scenario_family": f"family_{i % 5}",
                "condition": f"cond_{i % 3}",
                "alignment_label": "conflict" if i % 2 == 0 else "aligned",
            }
        )
    return scenarios


class TestAssignSplits(unittest.TestCase):
    def test_all_scenarios_assigned(self):
        scenarios = _scenarios()
        splits = assign_splits(scenarios)
        total = sum(len(v) for v in splits.values())
        self.assertEqual(total, len(scenarios))

    def test_deterministic(self):
        scenarios = _scenarios()
        s1 = assign_splits(scenarios, seed=42)
        s2 = assign_splits(scenarios, seed=42)
        for key in s1:
            ids1 = [s["episode_id"] for s in s1[key]]
            ids2 = [s["episode_id"] for s in s2[key]]
            self.assertEqual(ids1, ids2)

    def test_three_splits_present(self):
        splits = assign_splits(_scenarios())
        self.assertIn("public_dev", splits)
        self.assertIn("public_validation", splits)
        self.assertIn("hidden_test", splits)

    def test_approximate_proportions(self):
        splits = assign_splits(_scenarios())
        total = 100
        dev_pct = len(splits["public_dev"]) / total
        val_pct = len(splits["public_validation"]) / total
        self.assertGreater(dev_pct, 0.05)
        self.assertGreater(val_pct, 0.15)


class TestGenerateSplitManifests(unittest.TestCase):
    def test_writes_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            summary = generate_split_manifests(_scenarios(), tmpdir)
            self.assertTrue((Path(tmpdir) / "public_dev_manifest.csv").exists())
            self.assertTrue((Path(tmpdir) / "public_validation_manifest.csv").exists())
            self.assertTrue((Path(tmpdir) / "hidden_test_manifest.csv").exists())
            self.assertTrue((Path(tmpdir) / "split_summary.json").exists())
            self.assertEqual(summary["total"], 100)


class TestVerifyPublicCoverage(unittest.TestCase):
    def test_full_coverage(self):
        splits = assign_splits(_scenarios())
        result = verify_public_subset_coverage(splits)
        self.assertTrue(result["sufficient"])
        self.assertEqual(result["missing_families"], [])
        self.assertEqual(result["missing_conditions"], [])


class TestPairedSplits(unittest.TestCase):
    def test_twins_land_in_same_split(self):
        """Regression: paired twins must be in the same split."""
        scenarios = [
            {
                "episode_id": "pair-001-neutral",
                "scenario_family": "f1",
                "condition": "neutral",
                "alignment_label": "conflict",
                "metadata": {"pair_id": "pair-001"},
            },
            {
                "episode_id": "pair-001-pressure",
                "scenario_family": "f1",
                "condition": "direct_incentive",
                "alignment_label": "conflict",
                "metadata": {"pair_id": "pair-001"},
            },
        ]
        splits = assign_splits(scenarios)
        # Both must be in the same split
        for _split_name, split_scenarios in splits.items():
            ids = {s["episode_id"] for s in split_scenarios}
            if "pair-001-neutral" in ids:
                self.assertIn("pair-001-pressure", ids)
            if "pair-001-pressure" in ids:
                self.assertIn("pair-001-neutral", ids)


if __name__ == "__main__":
    unittest.main()
