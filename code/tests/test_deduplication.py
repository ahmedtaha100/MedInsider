"""Tests for src/medinsider/fhir/deduplication.py"""

import unittest

from medinsider.fhir.deduplication import (
    deduplicate,
    find_duplicates,
    find_duplicates_by_cell,
    jaccard_similarity,
)


class TestJaccardSimilarity(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(jaccard_similarity({"a", "b"}, {"a", "b"}), 1.0)

    def test_disjoint(self):
        self.assertEqual(jaccard_similarity({"a"}, {"b"}), 0.0)

    def test_partial(self):
        sim = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        self.assertAlmostEqual(sim, 0.5)

    def test_empty(self):
        self.assertEqual(jaccard_similarity(set(), set()), 1.0)
        self.assertEqual(jaccard_similarity({"a"}, set()), 0.0)


class TestFindDuplicates(unittest.TestCase):
    def test_no_duplicates(self):
        scenarios = [
            {
                "episode_id": "a",
                "case_skeleton": "Patient with chest pain",
                "care_plan": "Trend troponins",
                "tempting_misaligned_shortcut": "Upcode",
            },
            {
                "episode_id": "b",
                "case_skeleton": "Patient with diabetes",
                "care_plan": "Insulin management",
                "tempting_misaligned_shortcut": "Skip checks",
            },
        ]
        dupes = find_duplicates(scenarios, threshold=0.85)
        self.assertEqual(len(dupes), 0)

    def test_identical_scenarios(self):
        s = {
            "episode_id": "a",
            "case_skeleton": "Patient with chest pain observation",
            "care_plan": "Trend troponins",
            "tempting_misaligned_shortcut": "Upcode billing",
        }
        scenarios = [s, {**s, "episode_id": "b"}]
        dupes = find_duplicates(scenarios, threshold=0.85)
        self.assertEqual(len(dupes), 1)
        self.assertGreaterEqual(dupes[0][2], 0.85)


class TestDeduplicate(unittest.TestCase):
    def test_removes_duplicates(self):
        s = {
            "episode_id": "a",
            "case_skeleton": "Patient with chest pain observation",
            "care_plan": "Trend troponins",
            "tempting_misaligned_shortcut": "Upcode billing",
        }
        scenarios = [
            s,
            {**s, "episode_id": "b"},
            {
                "episode_id": "c",
                "case_skeleton": "Totally different case",
                "care_plan": "Different plan",
                "tempting_misaligned_shortcut": "Different shortcut",
            },
        ]
        kept, removed = deduplicate(scenarios, threshold=0.85)
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0]["episode_id"], "b")
        self.assertEqual(len(kept), 2)


class TestFindDuplicatesByCell(unittest.TestCase):
    def test_cell_grouping(self):
        scenarios = [
            {
                "episode_id": "a",
                "scenario_family": "f1",
                "condition": "c1",
                "case_skeleton": "Patient admitted",
                "care_plan": "Plan A",
                "tempting_misaligned_shortcut": "X",
            },
            {
                "episode_id": "b",
                "scenario_family": "f1",
                "condition": "c1",
                "case_skeleton": "Patient admitted",
                "care_plan": "Plan A",
                "tempting_misaligned_shortcut": "X",
            },
            {
                "episode_id": "c",
                "scenario_family": "f2",
                "condition": "c1",
                "case_skeleton": "Different case",
                "care_plan": "Different plan",
                "tempting_misaligned_shortcut": "Y",
            },
        ]
        result = find_duplicates_by_cell(scenarios, threshold=0.85)
        self.assertGreater(result["total_duplicates"], 0)
        self.assertEqual(result["duplicates_by_cell"]["f1::c1"], 1)


class TestCrossCellPreservation(unittest.TestCase):
    def test_identical_scenarios_in_different_cells_both_kept(self):
        """Regression: deduplicate must not remove across cell boundaries."""
        base = {
            "case_skeleton": "Patient with chest pain observation after ED evaluation",
            "care_plan": "Trend troponins and manage blood pressure",
            "tempting_misaligned_shortcut": "Submit higher complexity codes",
        }
        scenarios = [
            {**base, "episode_id": "a", "scenario_family": "f1", "condition": "c1"},
            {**base, "episode_id": "b", "scenario_family": "f2", "condition": "c1"},
        ]
        kept, removed = deduplicate(scenarios, threshold=0.85)
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(removed), 0)


if __name__ == "__main__":
    unittest.main()
