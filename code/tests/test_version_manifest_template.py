"""Tests for docs/protocol/version_manifest_template.json

Regression tests ensuring the manifest schema stays complete as models
and fields evolve.
"""

import json
import unittest
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "docs" / "protocol" / "version_manifest_template.json"


class TestVersionManifestTemplate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_parses_as_json(self):
        self.assertIn("closed_source_models", self.data)
        self.assertIn("open_weight_models", self.data)

    def test_revised_active_roster_shape(self):
        self.assertEqual(len(self.data["closed_source_models"]), 7)
        self.assertEqual(len(self.data["open_weight_models"]), 1)

    def test_required_closed_model_fields(self):
        required = {
            "slot",
            "model_id",
            "provider",
            "api_id",
            "resolved_concrete_id",
            "pricing_input",
            "pricing_output",
            "batch_eligible",
            "batch_eligible_for_agent_loop",
            "batch_api_available",
            "batch_pricing_input",
            "batch_pricing_output",
            "docs_archive_url",
            "docs_archive_date",
            "account_tier",
            "rpm_limit",
            "tpm_limit",
            "batch_queue_limit",
            "throughput_checked_date",
            "estimated_wall_clock_hours",
            "cross_family_separation_group",
        }
        for model in self.data["closed_source_models"]:
            missing = required - set(model.keys())
            self.assertEqual(missing, set(), f"Closed model {model.get('model_id')} missing fields: {missing}")

    def test_open_weight_inherits_closed_model_fields(self):
        """Regression: open-weight entries must carry the same pricing/batch
        field names as closed-source entries, even if values are N/A."""
        inherited_required = {
            "api_id",
            "resolved_concrete_id",
            "pricing_input",
            "pricing_output",
            "batch_eligible",
            "batch_eligible_for_agent_loop",
            "batch_api_available",
            "batch_pricing_input",
            "batch_pricing_output",
            "docs_archive_url",
            "docs_archive_date",
            "account_tier",
            "rpm_limit",
            "tpm_limit",
            "batch_queue_limit",
            "throughput_checked_date",
            "estimated_wall_clock_hours",
        }
        for model in self.data["open_weight_models"]:
            missing = inherited_required - set(model.keys())
            self.assertEqual(
                missing,
                set(),
                f"Open-weight model {model.get('model_id')} missing inherited fields: {missing}",
            )

    def test_required_open_weight_reproducibility_fields(self):
        required = {
            "huggingface_repo",
            "commit_revision",
            "tokenizer_revision",
            "weight_sha256_files",
            "chat_template_url",
            "special_tokens",
            "stop_tokens",
            "stop_tokens_for_tool_use",
            "license",
            "inference_engine",
            "inference_engine_commit",
            "cuda_version",
            "nvidia_driver_version",
            "transformers_version",
            "tokenizers_version",
            "attention_backend",
            "flash_attention_version",
            "quantization_method",
            "quantization_recipe",
            "tensor_parallel",
            "default_generation_params",
            "native_function_calling",
            "wrapper_function_calling",
            "native_structured_output",
            "wrapper_structured_output",
            "thinking_mode_default",
            "thinking_mode_param_name",
            "agent_runtime_policy",
            "cross_family_separation_group",
        }
        for model in self.data["open_weight_models"]:
            missing = required - set(model.keys())
            self.assertEqual(
                missing,
                set(),
                f"Open-weight model {model.get('model_id')} missing repro fields: {missing}",
            )

    def test_cross_family_separation_group_values(self):
        expected = {
            "GPT-5.4": "openai",
            "Claude Opus 4.7": "anthropic",
            "Claude Sonnet 4.6": "anthropic",
            "Qwen3.5-Plus": "alibaba",
            "Kimi 2.6": "moonshot",
            "GLM-5": "zhipu",
            "DeepSeek V3.2": "deepseek",
            "gpt-oss-120b": "openai",
        }
        all_models = self.data["closed_source_models"] + self.data["open_weight_models"]
        for model in all_models:
            expected_group = expected.get(model["model_id"])
            self.assertEqual(
                model.get("cross_family_separation_group"),
                expected_group,
                f"{model['model_id']} cross_family_separation_group mismatch",
            )

    def test_agent_runtime_policy_nested_fields(self):
        required_policy_keys = {
            "context_window_used",
            "history_compaction_policy",
            "malformed_json_repair_policy",
            "tool_call_retry_policy",
            "max_retries_before_failure",
            "show_invalid_tool_output_to_model",
            "tool_call_timeout_seconds",
        }
        for model in self.data["open_weight_models"]:
            policy = model.get("agent_runtime_policy", {})
            missing = required_policy_keys - set(policy.keys())
            self.assertEqual(
                missing,
                set(),
                f"{model['model_id']} agent_runtime_policy missing: {missing}",
            )


if __name__ == "__main__":
    unittest.main()
