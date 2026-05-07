import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from medinsider.fhir.hf_backup import rewrite_restored_run_paths
from medinsider.fhir.pilot_runtime import (
    _classify_summary,
    _relative_to_run_dir,
    build_parse_repair_summary,
    build_run_id,
    load_default_run_config,
    merge_run_config_overrides,
    run_phase4_v2,
    run_preflight,
)


class BrokenAgent:
    def next_action(self, system_prompt, messages, tool_names):
        return "not-a-dict"


class TimeoutAgent:
    def next_action(self, system_prompt, messages, tool_names):
        raise RuntimeError("openai_timeout:deadline_exceeded")


class FHIRPilotRuntimeTests(unittest.TestCase):
    def test_build_run_id_includes_unique_suffix(self):
        first = build_run_id("example run")
        second = build_run_id("example run")
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("example_run_"))
        self.assertGreaterEqual(len(first.rsplit("_", 1)[-1]), 6)

    def test_preflight_smoke_scripted_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="preflight_smoke",
            )
            report = run_preflight(config)
            self.assertTrue(report["ok"])
            self.assertEqual(report["selected_summary"]["episode_count"], 2)

    def test_preflight_openai_requires_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "openai"),
                output_root=temp_dir,
                run_id="preflight_openai",
            )
            with patch.dict("os.environ", {}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertTrue(any("missing_provider_env:openai" in error for error in report["errors"]))

    def test_preflight_openai_requires_requested_model(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "openai"),
                output_root=temp_dir,
                run_id="preflight_openai_missing_model",
            )
            config["agent"]["requested_model"] = ""
            with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("missing_requested_model:openai", report["errors"])

    def test_preflight_openai_compatible_requires_env_and_base_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="preflight_openai_compatible",
            )
            config["agent"] = {
                "type": "openai_compatible",
                "provider": "alibaba",
                "requested_model": "qwen3.5-plus-2026-02-15",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key_env": "DASHSCOPE_API_KEY",
                "max_tokens": 1024,
            }
            with patch.dict("os.environ", {}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any("missing_provider_env:openai_compatible:DASHSCOPE_API_KEY" in error for error in report["errors"])
            )

    def test_preflight_openai_compatible_rejects_non_numeric_temperature(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="preflight_openai_compatible_bad_temperature",
            )
            config["agent"] = {
                "type": "openai_compatible",
                "provider": "moonshot",
                "requested_model": "kimi-k2.6",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key_env": "MOONSHOT_API_KEY",
                "max_tokens": 1024,
                "temperature": "oops",
            }
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("openai_compatible_temperature_invalid", report["errors"])

    def test_preflight_openai_compatible_rejects_invalid_thinking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="preflight_openai_compatible_bad_thinking",
            )
            config["agent"] = {
                "type": "openai_compatible",
                "provider": "moonshot",
                "requested_model": "kimi-k2.6",
                "base_url": "https://api.moonshot.ai/v1",
                "api_key_env": "MOONSHOT_API_KEY",
                "max_tokens": 1024,
                "temperature": 0.6,
                "thinking": "disabled",
            }
            with patch.dict("os.environ", {"MOONSHOT_API_KEY": "test-key"}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("openai_compatible_thinking_invalid", report["errors"])

    def test_preflight_rejects_incomplete_pair_manifest(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            selection_manifest = Path(temp_dir) / "broken_selection.csv"
            selection_manifest.write_text(
                "\n".join(
                    [
                        "episode_id,pair_id,scenario_family,condition,twin_role,pressure_condition,selection_group,selection_reason",
                        "v2-coding_billing-bgpr-000-neutral,v2-coding_billing-bgpr-000,coding_and_billing_pressure,neutral,neutral,background_pressure,background_pressure_vs_neutral,test_only_neutral",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="broken_pair_manifest",
                selection_manifest=str(selection_manifest),
            )
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertTrue(any("pair_group_size_invalid" in error for error in report["errors"]))

    def test_preflight_requires_manifest_paths_in_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="missing_manifest_config",
            )
            config.pop("dataset_manifest", None)
            config.pop("selection_manifest", None)
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("dataset_manifest_missing_config", report["errors"])
            self.assertIn("selection_manifest_missing_config", report["errors"])

    def test_preflight_rejects_non_numeric_runtime_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="bad_runtime_settings",
            )
            config["runtime"]["max_episode_retries"] = "oops"
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("runtime_max_episode_retries_invalid", report["errors"])

    def test_preflight_rejects_invalid_call_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="bad_call_limits",
            )
            config["runtime"]["min_calls"] = 9
            config["runtime"]["max_calls"] = 4
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("runtime_call_limits_invalid", report["errors"])

    def test_preflight_rejects_non_numeric_seed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="bad_seed",
            )
            config["runtime"]["seed"] = "oops"
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("runtime_seed_invalid", report["errors"])

    def test_preflight_rejects_non_numeric_agent_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "claude"),
                output_root=temp_dir,
                run_id="bad_agent_limits",
            )
            config["agent"]["max_tokens"] = "oops"
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("claude_max_tokens_invalid", report["errors"])

    def test_preflight_validates_hf_backup_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="hf_backup_preflight",
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
            )
            with patch.dict(
                "os.environ",
                {
                    "HF_BACKUP_PRIMARY_REPO": "anonymous/primary-hf-backup",
                    "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary-hf-backup",
                },
                clear=False,
            ):
                report = run_preflight(config)
            self.assertTrue(report["ok"])
            self.assertTrue(report["hf_backup"]["enabled"])
            self.assertEqual(report["hf_backup"]["primary_repo"], "anonymous/primary-hf-backup")

    def test_preflight_rejects_hf_backup_without_repo_targets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="hf_backup_missing_repos",
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
            )
            with patch.dict("os.environ", {}, clear=True):
                report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("hf_backup_primary_repo_missing", report["errors"])
            self.assertIn("hf_backup_secondary_repo_missing", report["errors"])

    def test_preflight_rejects_null_hf_backup_config_without_throwing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="hf_backup_null_config",
            )
            config["hf_backup"] = None
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("hf_backup_config_invalid", report["errors"])

    def test_preflight_reports_dataset_manifest_errors_without_throwing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_manifest = Path(temp_dir) / "dataset.csv"
            dataset_manifest.write_text(
                "\n".join(
                    [
                        "episode_id,scenario_family,condition,alignment_label,twin_role,pair_id,pressure_condition,path",
                        "episode-1,coding_and_billing_pressure,neutral,aligned,neutral,pair-1,background_pressure,missing.json",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            selection_manifest = Path(temp_dir) / "selection.csv"
            selection_manifest.write_text(
                "\n".join(
                    [
                        "episode_id,selection_group",
                        "episode-1,default",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="bad_manifest_report",
                dataset_manifest=str(dataset_manifest),
                selection_manifest=str(selection_manifest),
            )
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertTrue(any(error.startswith("dataset_manifest_error:") for error in report["errors"]))

    def test_preflight_rejects_malformed_selection_expectations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="bad_selection_expectations",
            )
            config["selection_expectations"] = {
                "pair_counts_by_group": "oops",
                "require_all_families": "yes",
                "allowed_pressure_conditions": "background_pressure",
            }
            report = run_preflight(config)
            self.assertFalse(report["ok"])
            self.assertIn("selection_expectations_pair_counts_invalid", report["errors"])
            self.assertIn("selection_expectations_require_all_families_invalid", report["errors"])
            self.assertIn("selection_expectations_allowed_pressure_conditions_invalid", report["errors"])

    def test_run_phase4_v2_smoke_creates_expected_layout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="smoke_success",
                overwrite=True,
            )
            summary = run_phase4_v2(config)
            run_dir = Path(summary["run_dir"])
            for directory in ("manifest", "logs", "scores", "summaries", "artifacts"):
                self.assertTrue((run_dir / directory).exists(), directory)
            self.assertTrue((run_dir / "artifacts" / "episode_results.csv").exists())
            self.assertTrue((run_dir / "artifacts" / "aggregate_scores.csv").exists())
            self.assertTrue((run_dir / "artifacts" / "scored_episode_results.csv").exists())
            self.assertTrue((run_dir / "summaries" / "pair_summary.csv").exists())
            self.assertTrue((run_dir / "summaries" / "parse_repair_summary.json").exists())
            self.assertTrue((run_dir / "manifest" / "run_manifest.json").exists())
            rows = list(
                csv.DictReader((run_dir / "artifacts" / "episode_results.csv").read_text(encoding="utf-8").splitlines())
            )
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row["status"] == "success" for row in rows))
            self.assertTrue(all(row["scored"] == "True" for row in rows))
            self.assertTrue(all(Path(row["score_path"]).exists() for row in rows))
            self.assertTrue(all(row["parse_repair_count"] == "0" for row in rows))
            self.assertTrue(all(row["last_parse_mode"] == "direct" for row in rows))

            run_manifest = json.loads((run_dir / "manifest" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(run_manifest["run_id"], "smoke_success")
            self.assertEqual(run_manifest["selected_summary"]["episode_count"], 2)
            self.assertEqual(run_manifest["status_counts"], {"success": 2})
            self.assertTrue(run_manifest["dataset_manifest_hash"])
            self.assertTrue(run_manifest["selection_manifest_hash"])
            self.assertIn("parse_repair_summary_json", run_manifest["output_files"])

    def test_run_phase4_v2_smoke_writes_hf_backup_metadata_in_dry_run_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="smoke_hf_backup",
                overwrite=True,
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
                hf_backup_batch_size=1,
            )
            with patch.dict(
                "os.environ",
                {
                    "HF_BACKUP_PRIMARY_REPO": "anonymous/primary-hf-backup",
                    "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary-hf-backup",
                },
                clear=False,
            ):
                summary = run_phase4_v2(config)

            run_dir = Path(summary["run_dir"])
            self.assertTrue((run_dir / "manifest" / "hf_backup_state.json").exists())
            self.assertTrue((run_dir / "summaries" / "hf_backup_summary.json").exists())
            run_manifest = json.loads((run_dir / "manifest" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(run_manifest["hf_backup"]["enabled"])
            self.assertGreaterEqual(run_manifest["hf_backup"]["checkpoint_count"], 2)

    def test_manifest_files_redact_sensitive_agent_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="manifest_redaction",
                overwrite=True,
            )
            config["agent"]["api_key"] = "SECRET-123"
            config["agent"]["apiKey"] = "SECRET-456"
            config["agent"]["api-key"] = "SECRET-789"

            summary = run_phase4_v2(config)

            run_dir = Path(summary["run_dir"])
            effective_config = json.loads(
                (run_dir / "manifest" / "effective_run_config.json").read_text(encoding="utf-8")
            )
            redacted_config = json.loads(
                (run_dir / "manifest" / "effective_run_config_redacted.json").read_text(encoding="utf-8")
            )
            run_manifest = json.loads((run_dir / "manifest" / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(effective_config["agent"]["api_key"], "SECRET-123")
            self.assertEqual(redacted_config["agent"]["api_key"], "<redacted>")
            self.assertEqual(redacted_config["agent"]["apiKey"], "<redacted>")
            self.assertEqual(redacted_config["agent"]["api-key"], "<redacted>")
            self.assertEqual(run_manifest["agent"]["api_key"], "<redacted>")
            self.assertEqual(run_manifest["agent"]["apiKey"], "<redacted>")
            self.assertEqual(run_manifest["agent"]["api-key"], "<redacted>")

    def test_resume_reuses_existing_episode_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_case",
                overwrite=True,
            )
            first = run_phase4_v2(base_config)
            episode_path = Path(first["run_dir"]) / "artifacts" / "episodes" / "v2-coding_billing-bgpr-000-neutral.json"
            started_at = json.loads(episode_path.read_text(encoding="utf-8"))["started_at_utc"]

            resumed_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_case",
                resume=True,
            )
            run_phase4_v2(resumed_config)
            resumed_started_at = json.loads(episode_path.read_text(encoding="utf-8"))["started_at_utc"]
            self.assertEqual(started_at, resumed_started_at)

    def test_resume_with_hf_backup_does_not_restart_checkpoint_sequence_from_zero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_hf_backup_case",
                overwrite=True,
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
                hf_backup_batch_size=1,
            )
            env = {
                "HF_BACKUP_PRIMARY_REPO": "anonymous/primary-hf-backup",
                "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary-hf-backup",
            }
            with patch.dict("os.environ", env, clear=False):
                first = run_phase4_v2(base_config)
            state_path = Path(first["run_dir"]) / "manifest" / "hf_backup_state.json"
            first_state = json.loads(state_path.read_text(encoding="utf-8"))

            resumed_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_hf_backup_case",
                resume=True,
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
                hf_backup_batch_size=1,
            )
            with patch.dict("os.environ", env, clear=False):
                run_phase4_v2(resumed_config)
            resumed_state = json.loads(state_path.read_text(encoding="utf-8"))

            self.assertEqual(first_state["last_attempted_completed_episodes"], 2)
            self.assertEqual(resumed_state["last_attempted_completed_episodes"], 2)
            self.assertEqual(resumed_state["checkpoint_sequence"], first_state["checkpoint_sequence"] + 1)
            self.assertEqual(resumed_state["last_successful_checkpoint"]["reason"], "final_completion")

    def test_overwrite_with_hf_backup_on_populated_run_dir_still_initializes_checkpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir)
            populated_run_dir = run_root / "overwrite_hf_backup_case"
            populated_run_dir.mkdir(parents=True, exist_ok=True)
            (populated_run_dir / "stale.txt").write_text("stale", encoding="utf-8")

            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="overwrite_hf_backup_case",
                overwrite=True,
                hf_backup_enabled=True,
                hf_backup_dry_run=True,
                hf_backup_batch_size=1,
            )
            env = {
                "HF_BACKUP_PRIMARY_REPO": "anonymous/primary-hf-backup",
                "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary-hf-backup",
            }
            with patch.dict("os.environ", env, clear=False):
                summary = run_phase4_v2(config)

            run_dir = Path(summary["run_dir"])
            self.assertFalse((run_dir / "stale.txt").exists())
            state = json.loads((run_dir / "manifest" / "hf_backup_state.json").read_text(encoding="utf-8"))
            checkpoint_reasons = [checkpoint["reason"] for checkpoint in state["checkpoints"]]

            self.assertIn("manifest_initialized", checkpoint_reasons)
            self.assertEqual(state["checkpoints"][0]["reason"], "manifest_initialized")

    def test_resume_after_restore_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_root = Path(temp_dir) / "original_runs"
            restored_root = Path(temp_dir) / "restored_runs"
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=str(original_root),
                run_id="restore_resume_case",
                overwrite=True,
            )
            summary = run_phase4_v2(base_config)
            original_run_dir = Path(summary["run_dir"])
            restored_run_dir = restored_root / "restore_resume_case"
            shutil.copytree(original_run_dir, restored_run_dir)
            rewrite_restored_run_paths(restored_run_dir)
            shutil.rmtree(original_root)

            episode_path = restored_run_dir / "artifacts" / "episodes" / "v2-coding_billing-bgpr-000-neutral.json"
            restored_started_at = json.loads(episode_path.read_text(encoding="utf-8"))["started_at_utc"]

            resumed_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=str(restored_root),
                run_id="restore_resume_case",
                resume=True,
            )
            run_phase4_v2(resumed_config)
            resumed_payload = json.loads(episode_path.read_text(encoding="utf-8"))
            resumed_started_at = resumed_payload["started_at_utc"]
            self.assertEqual(restored_started_at, resumed_started_at)
            self.assertTrue(str(Path(resumed_payload["log_path"])).startswith(str(restored_run_dir)))
            self.assertTrue(str(Path(resumed_payload["score_path"])).startswith(str(restored_run_dir)))

    def test_resume_reruns_invalid_episode_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_invalid_case",
                overwrite=True,
            )
            summary = run_phase4_v2(base_config)
            episode_path = (
                Path(summary["run_dir"]) / "artifacts" / "episodes" / "v2-coding_billing-bgpr-000-neutral.json"
            )
            episode_payload = json.loads(episode_path.read_text(encoding="utf-8"))
            original_started_at = episode_payload["started_at_utc"]
            score_path = Path(episode_payload["score_path"])

            episode_payload["ended_at_utc"] = ""
            episode_path.write_text(json.dumps(episode_payload, indent=2), encoding="utf-8")
            score_path.unlink()

            resumed_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_invalid_case",
                resume=True,
            )
            resumed_summary = run_phase4_v2(resumed_config)
            repaired_payload = json.loads(episode_path.read_text(encoding="utf-8"))

            self.assertNotEqual(original_started_at, repaired_payload["started_at_utc"])
            self.assertTrue(repaired_payload["ended_at_utc"])
            self.assertTrue(Path(repaired_payload["score_path"]).exists())

            run_manifest = json.loads(
                (Path(resumed_summary["run_dir"]) / "manifest" / "run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(run_manifest["resume_warnings"]), 1)
            self.assertIn("resume_artifact_invalid", run_manifest["resume_warnings"][0])

    def test_resume_reruns_when_execution_fingerprint_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_fingerprint_case",
                overwrite=True,
            )
            summary = run_phase4_v2(base_config)
            episode_path = (
                Path(summary["run_dir"]) / "artifacts" / "episodes" / "v2-coding_billing-bgpr-000-neutral.json"
            )
            original_payload = json.loads(episode_path.read_text(encoding="utf-8"))

            resumed_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="resume_fingerprint_case",
                resume=True,
            )
            resumed_config["runtime"]["request_timeout_seconds"] = 30
            resumed_summary = run_phase4_v2(resumed_config)
            repaired_payload = json.loads(episode_path.read_text(encoding="utf-8"))

            self.assertNotEqual(original_payload["started_at_utc"], repaired_payload["started_at_utc"])
            self.assertNotEqual(
                original_payload["resume_fingerprint"]["request_timeout_seconds"],
                repaired_payload["resume_fingerprint"]["request_timeout_seconds"],
            )

            run_manifest = json.loads(
                (Path(resumed_summary["run_dir"]) / "manifest" / "run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(run_manifest["resume_warnings"]), 2)
            self.assertTrue(
                all("resume_fingerprint_mismatch" in warning for warning in run_manifest["resume_warnings"])
            )

    def test_overwrite_clears_existing_run_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="overwrite_case",
                overwrite=True,
            )
            summary = run_phase4_v2(base_config)
            sentinel = Path(summary["run_dir"]) / "manifest" / "sentinel.txt"
            sentinel.write_text("sentinel", encoding="utf-8")

            overwrite_config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="overwrite_case",
                overwrite=True,
            )
            run_phase4_v2(overwrite_config)
            self.assertFalse(sentinel.exists())

    def test_failure_taxonomy_handles_invalid_action_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="invalid_action_case",
                overwrite=True,
            )
            with patch("medinsider.fhir.pilot_runtime.create_agent", return_value=BrokenAgent()):
                summary = run_phase4_v2(config)
            self.assertEqual(summary["failure_summary"]["status_counts"].get("invalid_action_schema"), 2)

    def test_failure_taxonomy_classifies_structured_timeout_codes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="timeout_case",
                overwrite=True,
            )
            with patch("medinsider.fhir.pilot_runtime.create_agent", return_value=TimeoutAgent()):
                summary = run_phase4_v2(config)
            self.assertEqual(summary["failure_summary"]["status_counts"].get("timeout"), 2)

    def test_merge_run_config_overrides_normalizes_invalid_hf_backup_section_for_cli_overrides(self):
        config = merge_run_config_overrides(
            {
                "runtime": {},
                "hf_backup": None,
            },
            hf_backup_enabled=True,
            hf_backup_primary_repo="anonymous/primary-backup",
        )
        self.assertEqual(
            config["hf_backup"],
            {
                "enabled": True,
                "primary_repo": "anonymous/primary-backup",
            },
        )

    def test_merge_run_config_overrides_preserves_runtime_hf_backup_defaults(self):
        config = merge_run_config_overrides(
            {
                "runtime": {
                    "hf_backup": {
                        "enabled": True,
                        "primary_repo": "anonymous/primary-backup",
                        "secondary_repo": "anonymous/secondary-backup",
                        "dry_run": True,
                    }
                }
            },
            hf_backup_batch_size=7,
        )
        self.assertEqual(
            config["hf_backup"],
            {
                "enabled": True,
                "primary_repo": "anonymous/primary-backup",
                "secondary_repo": "anonymous/secondary-backup",
                "dry_run": True,
                "batch_size": 7,
            },
        )

    def test_relative_to_run_dir_falls_back_to_absolute_path_for_external_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            run_dir = temp_root / "run"
            external_path = temp_root / "external" / "episode.json"
            run_dir.mkdir(parents=True, exist_ok=True)
            external_path.parent.mkdir(parents=True, exist_ok=True)
            external_path.write_text("{}", encoding="utf-8")

            relative_or_absolute = _relative_to_run_dir(run_dir, external_path)

            self.assertEqual(relative_or_absolute, external_path.resolve().as_posix())

    def test_failure_taxonomy_defaults_unclassified_agent_errors_to_api_failure(self):
        status, detail = _classify_summary(
            {
                "agent_error": "agent_action_error:RuntimeError:boom",
                "termination_reason": "agent_error",
            },
            [],
        )
        self.assertEqual(status, "api_failure")
        self.assertEqual(detail, "agent_action_error:RuntimeError:boom")

    def test_parse_repair_summary_marks_repaired_episodes_explicitly(self):
        summary = build_parse_repair_summary(
            [
                {
                    "provider": "openai",
                    "resolved_model": "gpt-test",
                    "requested_model": "gpt-test",
                    "agent_type": "openai",
                    "parse_repair_count": 2,
                    "last_parse_mode": "direct",
                },
                {
                    "provider": "openai",
                    "resolved_model": "gpt-test",
                    "requested_model": "gpt-test",
                    "agent_type": "openai",
                    "parse_repair_count": 0,
                    "last_parse_mode": "direct",
                },
            ]
        )

        self.assertEqual(summary["episodes_with_repairs"], 1)
        self.assertEqual(summary["last_parse_mode_counts"], {"direct": 1, "repaired (direct)": 1})
        bucket = summary["by_provider_model"][0]
        self.assertEqual(bucket["episodes_with_repairs"], 1)
        self.assertEqual(bucket["last_parse_mode_counts"], {"direct": 1, "repaired (direct)": 1})

    def test_dry_run_writes_manifest_only(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = merge_run_config_overrides(
                load_default_run_config("smoke", "scripted"),
                output_root=temp_dir,
                run_id="dry_run_case",
                dry_run=True,
                overwrite=True,
            )
            summary = run_phase4_v2(config)
            run_dir = Path(summary["run_dir"])
            self.assertTrue(summary["dry_run"])
            self.assertTrue((run_dir / "manifest" / "run_manifest.json").exists())
            self.assertFalse((run_dir / "artifacts" / "episode_results.csv").exists())


if __name__ == "__main__":
    unittest.main()
