"""Tests for src/medinsider/fhir/gen_eval_separation.py"""

import unittest

from medinsider.fhir.gen_eval_separation import (
    JUDGE_ROUTING,
    assigned_judges_for,
    get_model_family,
    stamp_episode_metadata,
    stamp_score_metadata,
    validate_separation,
)


class TestGetModelFamily(unittest.TestCase):
    def test_known_model(self):
        self.assertEqual(get_model_family("gpt-5.4"), "openai")
        self.assertEqual(get_model_family("claude-opus-4-7"), "anthropic")
        self.assertEqual(get_model_family("qwen3.5-plus-2026-02-15"), "alibaba")

    def test_unknown_model(self):
        self.assertEqual(get_model_family("unknown-model-xyz"), "unknown")

    def test_case_insensitive(self):
        self.assertEqual(get_model_family("GPT-5.4"), "openai")

    def test_short_token_no_false_positive(self):
        """Regression: short token must not match unrelated models."""
        self.assertEqual(get_model_family("custom-finetune-xyz"), "unknown")

    def test_longest_match_wins(self):
        self.assertEqual(get_model_family("prefix-qwen3.5-plus-2026-02-15-custom"), "alibaba")


class TestValidateSeparation(unittest.TestCase):
    def test_valid_separation(self):
        result = validate_separation("gpt-5.4", ["claude-opus-4-7", "claude-sonnet-4-6"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["conflicts"], [])

    def test_invalid_same_family(self):
        result = validate_separation("claude-opus-4-7", ["claude-sonnet-4-6"])
        self.assertFalse(result["valid"])
        self.assertIn("claude-sonnet-4-6", result["conflicts"])

    def test_unknown_not_conflict(self):
        result = validate_separation("gpt-5.4", ["custom-model"])
        self.assertTrue(result["valid"])

    def test_gpt_oss_is_openai_family(self):
        """Regression: gpt-oss-120b must be classified as OpenAI family."""
        self.assertEqual(get_model_family("gpt-oss-120b"), "openai")

    def test_gpt_oss_conflicts_with_gpt_5_4(self):
        """Regression: provider-hosted gpt-oss agent cannot use GPT-5.4 judge."""
        result = validate_separation("gpt-oss-120b", ["gpt-5.4"])
        self.assertFalse(result["valid"])
        self.assertIn("gpt-5.4", result["conflicts"])

    def test_deepseek_is_separate_family(self):
        self.assertEqual(get_model_family("deepseek-chat"), "deepseek")
        result = validate_separation("deepseek-chat", ["gpt-5.4", "claude-opus-4-7"])
        self.assertTrue(result["valid"])


class TestJudgeRouting(unittest.TestCase):
    def test_assigned_judges_cover_active_roster(self):
        expected = {
            "gpt-5.4": ("claude-opus-4-7", "claude-sonnet-4-6"),
            "claude-opus-4-7": ("gpt-5.4", "deepseek-chat"),
            "claude-sonnet-4-6": ("gpt-5.4", "deepseek-chat"),
            "qwen3.5-plus-2026-02-15": ("gpt-5.4", "claude-opus-4-7"),
            "kimi-k2.6": ("gpt-5.4", "claude-opus-4-7"),
            "glm-5": ("gpt-5.4", "claude-opus-4-7"),
            "deepseek-chat": ("gpt-5.4", "claude-opus-4-7"),
            "gpt-oss-120b": ("claude-opus-4-7", "claude-sonnet-4-6"),
        }
        for agent_model, judge_pair in expected.items():
            self.assertEqual(assigned_judges_for(agent_model), judge_pair)
            validation = validate_separation(agent_model, list(judge_pair))
            self.assertTrue(validation["valid"], agent_model)

    def test_runtime_id_aliases_map_to_same_judges(self):
        self.assertEqual(
            assigned_judges_for("gpt-5.4-2026-03-05"),
            ("claude-opus-4-7", "claude-sonnet-4-6"),
        )
        self.assertEqual(
            assigned_judges_for("qwen-plus"),
            ("gpt-5.4", "claude-opus-4-7"),
        )
        self.assertEqual(
            assigned_judges_for("openai/gpt-oss-120b"),
            ("claude-opus-4-7", "claude-sonnet-4-6"),
        )

    def test_judge_routing_registry_includes_active_roster_aliases(self):
        self.assertIn("gpt-5.4", JUDGE_ROUTING)
        self.assertIn("gpt-5.4-2026-03-05", JUDGE_ROUTING)
        self.assertIn("qwen-plus", JUDGE_ROUTING)
        self.assertIn("deepseek-reasoner", JUDGE_ROUTING)


class TestStampMetadata(unittest.TestCase):
    def test_stamp_episode(self):
        meta = {}
        result = stamp_episode_metadata(meta, "gpt-5.4")
        self.assertEqual(result["generator_family"], "openai")

    def test_stamp_score(self):
        score = {"episode_id": "test"}
        result = stamp_score_metadata(score, "claude-opus-4-7")
        self.assertEqual(result["metadata"]["evaluator_family"], "anthropic")


if __name__ == "__main__":
    unittest.main()
