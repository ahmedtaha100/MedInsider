import json
import shutil
import tempfile
import unittest
import warnings
from contextlib import redirect_stdout
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from medinsider.fhir.hf_backup import (
    HF_BACKUP_STATE_FILENAME,
    HFBackupSettings,
    HFDualRepoBackupManager,
    HFHubClient,
    _is_retryable_hf_error,
    choose_restore_source,
    resolve_hf_backup_settings,
    restore_run_from_hf,
    rewrite_restored_run_paths,
    validate_hf_backup_settings,
    verify_hf_backup,
)
from medinsider.fhir.pilot_runtime import prepare_run_layout, write_json


class FakeHFClient:
    def __init__(self, failing_repos: set[str] | None = None):
        self.failing_repos = set(failing_repos or set())
        self.files: dict[str, dict[str, bytes]] = {}
        self.upload_calls: list[tuple[str, str]] = []
        self.commit_calls: list[tuple[str, tuple[str, ...]]] = []

    def ensure_repo(self, repo_id: str, private: bool = True) -> None:
        self.files.setdefault(repo_id, {})

    def commit_files(
        self,
        repo_id: str,
        files: list[tuple[Path, str]],
        commit_message: str,
    ) -> dict[str, str]:
        if repo_id in self.failing_repos:
            raise RuntimeError(f"forced_failure:{repo_id}")
        repo_files = self.files.setdefault(repo_id, {})
        committed_paths: list[str] = []
        for local_path, path_in_repo in files:
            repo_files[path_in_repo] = Path(local_path).read_bytes()
            self.upload_calls.append((repo_id, path_in_repo))
            committed_paths.append(path_in_repo)
        self.commit_calls.append((repo_id, tuple(committed_paths)))
        call_count = len(self.commit_calls)
        return {
            "revision": f"{repo_id}-rev-{call_count}",
            "commit_url": f"https://hf.co/datasets/{repo_id}/commit/{call_count}",
        }

    def upload_file(self, repo_id: str, local_path: Path, path_in_repo: str, commit_message: str) -> dict[str, str]:
        return self.commit_files(repo_id, [(local_path, path_in_repo)], commit_message)

    def list_files(self, repo_id: str, prefix: str) -> list[str]:
        return sorted(path for path in self.files.get(repo_id, {}) if path.startswith(f"{prefix}/"))

    def download_text(self, repo_id: str, path_in_repo: str) -> str:
        return self.files[repo_id][path_in_repo].decode("utf-8")

    def download_file(self, repo_id: str, path_in_repo: str, local_path: Path) -> Path:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(self.files[repo_id][path_in_repo])
        return local_path

    def snapshot_download_run(self, repo_id: str, run_id: str, local_dir: Path) -> Path:
        for path_in_repo, payload in self.files.get(repo_id, {}).items():
            if not path_in_repo.startswith(f"{run_id}/"):
                continue
            target = local_dir / path_in_repo
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        return local_dir


class HFBackupTests(unittest.TestCase):
    def _settings(self, **overrides) -> HFBackupSettings:
        values = {
            "enabled": True,
            "strict": False,
            "dry_run": False,
            "verify_remote": True,
            "batch_size": 1,
            "primary_repo": "anonymous/primary-backup",
            "secondary_repo": "anonymous/secondary-backup",
            "token_env_name": "HF_TOKEN",
            "token": "test-token",
        }
        values.update(overrides)
        return HFBackupSettings(**values)

    def _build_run_tree(self, run_dir: Path) -> dict[str, Path]:
        layout = prepare_run_layout(run_dir)
        write_json(layout["manifest"] / "run_manifest.json", {"run_id": run_dir.name})
        write_json(layout["manifest"] / "preflight_report.json", {"ok": True})
        write_json(layout["manifest"] / "effective_run_config.json", {"agent": {"type": "scripted"}})
        write_json(layout["manifest"] / "effective_run_config_redacted.json", {"agent": {"type": "scripted"}})
        (layout["manifest"] / "resolved_selection.csv").write_text(
            "episode_id,selection_group\nepisode-1,default\n",
            encoding="utf-8",
        )
        (layout["manifest"] / "dataset_manifest.csv").write_text(
            "episode_id,path\nepisode-1,scenario.json\n",
            encoding="utf-8",
        )
        (layout["manifest"] / "selection_manifest.csv").write_text(
            "episode_id,selection_group\nepisode-1,default\n",
            encoding="utf-8",
        )
        (layout["logs"] / "episode-1.jsonl").write_text(
            json.dumps({"tool_name": "read_chart", "result": {"ok": True}}) + "\n",
            encoding="utf-8",
        )
        write_json(layout["scores"] / "episode-1.json", {"primary": {}, "atc": {"score": 1.0}})
        episode_artifact = {
            "episode_id": "episode-1",
            "pair_id": "pair-1",
            "scenario_family": "coding_and_billing_pressure",
            "condition": "neutral",
            "twin_role": "neutral",
            "pressure_condition": "background_pressure",
            "alignment_label": "aligned",
            "risk_tier": "medium",
            "selection_group": "default",
            "selection_reason": "test_fixture",
            "status": "success",
            "runtime_status": "success",
            "status_detail": "",
            "scored": True,
            "attempts_used": 1,
            "retry_count": 0,
            "agent_type": "scripted",
            "provider": "scripted",
            "requested_model": "",
            "resolved_model": "",
            "seed": 42,
            "request_timeout_seconds": 60,
            "max_episode_retries": 0,
            "retry_backoff_seconds": 0.0,
            "started_at_utc": "2026-04-17T00:00:00+00:00",
            "ended_at_utc": "2026-04-17T00:00:01+00:00",
            "duration_seconds": 1.0,
            "tool_calls": 1,
            "termination_reason": "finish",
            "token_input": 0,
            "token_output": 0,
            "token_total": 0,
            "log_path": str(layout["logs"] / "episode-1.jsonl"),
            "log_path_relative": "logs/episode-1.jsonl",
            "score_path": str(layout["scores"] / "episode-1.json"),
            "score_path_relative": "scores/episode-1.json",
            "resume_fingerprint": {"dataset_manifest_hash": "abc"},
            "needs_judge": False,
            "IVR": "",
            "MGR": "",
            "UPR": "",
            "UPR_integrity": "",
            "UPR_compliance": "",
            "AEOR": "",
            "PSD": "",
            "CDR": "",
            "ATC": 1.0,
            "deception_language_score": "",
            "tradeoff_mode": "",
        }
        write_json(layout["episode_artifacts"] / "episode-1.json", episode_artifact)
        (layout["artifacts"] / "episode_results.csv").write_text(
            "episode_id,status,scored,log_path,log_path_relative,score_path,score_path_relative\n"
            f"episode-1,success,True,{layout['logs'] / 'episode-1.jsonl'},logs/episode-1.jsonl,"
            f"{layout['scores'] / 'episode-1.json'},scores/episode-1.json\n",
            encoding="utf-8",
        )
        (layout["artifacts"] / "scored_episode_results.csv").write_text(
            "episode_id,status,ATC\nepisode-1,success,1.0\n",
            encoding="utf-8",
        )
        (layout["artifacts"] / "aggregate_scores.csv").write_text(
            "selection_group,condition,episode_count,scored_episode_count,success_count,max_call_termination_count,IVR,MGR,UPR,AEOR,PSD,CDR,ATC\n"
            "default,neutral,1,1,1,0,0,0,0,0,0,0,1\n",
            encoding="utf-8",
        )
        write_json(layout["summaries"] / "failure_summary.json", {"status_counts": {"success": 1}})
        write_json(layout["summaries"] / "latency_summary.json", {"episode_count": 1})
        write_json(layout["summaries"] / "token_usage_summary.json", {"episode_count": 1})
        (layout["summaries"] / "pair_summary.csv").write_text(
            "pair_id,scenario_family,pressure_condition,selection_group,neutral_status,pressure_status,neutral_scored,pressure_scored\n",
            encoding="utf-8",
        )
        return layout

    def test_resolve_hf_backup_settings_uses_env_repo_values(self):
        config = {
            "hf_backup": {
                "enabled": True,
                "dry_run": True,
                "batch_size": 7,
            }
        }
        with patch.dict(
            "os.environ",
            {
                "HF_BACKUP_PRIMARY_REPO": "anonymous/primary",
                "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary",
            },
            clear=False,
        ):
            settings = resolve_hf_backup_settings(config)
        self.assertTrue(settings.enabled)
        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.batch_size, 7)
        self.assertEqual(settings.primary_repo, "anonymous/primary")
        self.assertEqual(settings.secondary_repo, "anonymous/secondary")

    def test_resolve_hf_backup_settings_supports_runtime_fallback(self):
        config = {
            "runtime": {
                "hf_backup": {
                    "enabled": True,
                    "dry_run": True,
                    "batch_size": 7,
                }
            }
        }
        with patch.dict(
            "os.environ",
            {
                "HF_BACKUP_PRIMARY_REPO": "anonymous/primary",
                "HF_BACKUP_SECONDARY_REPO": "anonymous/secondary",
            },
            clear=False,
        ):
            settings = resolve_hf_backup_settings(config)
        self.assertTrue(settings.enabled)
        self.assertTrue(settings.dry_run)
        self.assertEqual(settings.batch_size, 7)
        self.assertEqual(settings.primary_repo, "anonymous/primary")
        self.assertEqual(settings.secondary_repo, "anonymous/secondary")

    def test_validate_hf_backup_settings_rejects_invalid_top_level_value(self):
        errors = validate_hf_backup_settings({"hf_backup": "enabled"})
        self.assertEqual(errors, ["hf_backup_config_invalid"])

    def test_validate_hf_backup_settings_rejects_null_top_level_value(self):
        errors = validate_hf_backup_settings({"hf_backup": None})
        self.assertEqual(errors, ["hf_backup_config_invalid"])

    def test_checkpoint_uploads_changed_files_to_both_repos(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            (Path(temp_dir) / "apikeys.txt").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")
            client = FakeHFClient()
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=client)

            checkpoint = manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)

            self.assertEqual(checkpoint["status"], "success")
            self.assertIn("hf_run/manifest/run_manifest.json", client.files["anonymous/primary-backup"])
            self.assertIn("hf_run/manifest/run_manifest.json", client.files["anonymous/secondary-backup"])
            uploaded_paths = set(client.files["anonymous/primary-backup"])
            self.assertNotIn("apikeys.txt", uploaded_paths)
            self.assertIn("hf_run/manifest/effective_run_config_redacted.json", uploaded_paths)
            self.assertNotIn("hf_run/manifest/effective_run_config.json", uploaded_paths)
            self.assertTrue((layout["manifest"] / "hf_backup_state.json").exists())
            self.assertTrue((layout["summaries"] / "hf_backup_summary.json").exists())
            self.assertEqual(len(client.commit_calls), 4)
            self.assertGreater(len(client.commit_calls[0][1]), 2)

    def test_checkpoint_records_partial_failure_when_one_repo_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient(failing_repos={"anonymous/secondary-backup"})
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=client)

            checkpoint = manager.checkpoint("episode_batch_1", completed_episodes=1, force=True)

            self.assertEqual(checkpoint["status"], "partial_failure")
            self.assertEqual(checkpoint["repo_results"]["primary"]["status"], "success")
            self.assertEqual(checkpoint["repo_results"]["secondary"]["status"], "failed")

    def test_checkpoint_raises_in_strict_mode_when_both_repos_fail(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient(failing_repos={"anonymous/primary-backup", "anonymous/secondary-backup"})
            manager = HFDualRepoBackupManager(
                self._settings(strict=True),
                layout,
                run_id="hf_run",
                client=client,
            )

            with self.assertRaisesRegex(RuntimeError, "hf_backup_strict_failure"):
                manager.checkpoint("episode_batch_1", completed_episodes=1, force=True)

    def test_checkpoint_retries_non_metadata_files_after_failed_attempt(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient(failing_repos={"anonymous/primary-backup", "anonymous/secondary-backup"})
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=client)

            first = manager.checkpoint("episode_batch_1", completed_episodes=1, force=True)
            first_call_count = len(client.upload_calls)
            client.failing_repos.clear()

            second = manager.checkpoint("episode_batch_2", completed_episodes=2, force=True)
            second_calls = client.upload_calls[first_call_count:]
            uploaded_paths = {path_in_repo for _, path_in_repo in second_calls}

            self.assertEqual(first["status"], "failed")
            self.assertEqual(second["status"], "success")
            self.assertIn("hf_run/manifest/run_manifest.json", uploaded_paths)
            self.assertIn("hf_run/logs/episode-1.jsonl", uploaded_paths)
            self.assertIn("hf_run/scores/episode-1.json", uploaded_paths)

    def test_checkpoint_skips_remote_verification_when_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient()

            def fail_list_files(repo_id: str, prefix: str) -> list[str]:
                raise AssertionError("list_files should not be called when verify_remote is disabled")

            client.list_files = fail_list_files  # type: ignore[assignment]
            manager = HFDualRepoBackupManager(
                self._settings(verify_remote=False),
                layout,
                run_id="hf_run",
                client=client,
            )

            checkpoint = manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)

            self.assertEqual(checkpoint["status"], "success")
            self.assertTrue(all(result["status"] == "success" for result in checkpoint["repo_results"].values()))
            self.assertTrue(all(result["verified"] for result in checkpoint["repo_results"].values()))
            self.assertTrue(all(result["verified_file_count"] == 0 for result in checkpoint["repo_results"].values()))

    def test_restore_prefers_more_recent_valid_repo_and_rewrites_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_run_dir = Path(temp_dir) / "source" / "restore_case"
            layout = self._build_run_tree(source_run_dir)
            run_manifest_path = layout["manifest"] / "run_manifest.json"
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            run_manifest.update(
                {
                    "output_dir": str(source_run_dir),
                    "dataset_manifest": str(Path(temp_dir) / "external_dataset_manifest.csv"),
                    "selection_manifest": str(Path(temp_dir) / "external_selection_manifest.csv"),
                    "manifest_files": {
                        "preflight_report_json": str(layout["manifest"] / "preflight_report.json"),
                        "dataset_manifest_csv": str(layout["manifest"] / "dataset_manifest.csv"),
                    },
                    "output_files": {
                        "episode_results_csv": str(layout["artifacts"] / "episode_results.csv"),
                        "failure_summary_json": str(layout["summaries"] / "failure_summary.json"),
                    },
                }
            )
            run_manifest_path.write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
            client = FakeHFClient()
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="restore_case", client=client)
            manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)

            client.failing_repos.add("anonymous/primary-backup")
            (layout["logs"] / "episode-2.jsonl").write_text(
                json.dumps({"tool_name": "write_note", "result": {"ok": True}}) + "\n",
                encoding="utf-8",
            )
            manager.checkpoint("episode_batch_2", completed_episodes=2, force=True)

            restored_root = Path(temp_dir) / "restored"
            report = restore_run_from_hf(
                "restore_case",
                restored_root,
                [
                    ("primary", "anonymous/primary-backup"),
                    ("secondary", "anonymous/secondary-backup"),
                ],
                token="test-token",
                client=client,
            )

            restored_run_dir = restored_root / "restore_case"
            restored_episode = json.loads(
                (restored_run_dir / "artifacts" / "episodes" / "episode-1.json").read_text(encoding="utf-8")
            )
            restored_manifest = json.loads(
                (restored_run_dir / "manifest" / "run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(report["ok"])
            self.assertEqual(report["selected_repo"], "anonymous/secondary-backup")
            self.assertEqual(report["selected_sequence"], 2)
            self.assertTrue(Path(restored_episode["log_path"]).exists())
            self.assertTrue((restored_run_dir / "manifest" / "run_manifest.json").exists())
            self.assertTrue((restored_run_dir / "logs" / "episode-2.jsonl").exists())
            self.assertEqual(restored_manifest["output_dir"], str(restored_run_dir))
            self.assertEqual(
                restored_manifest["dataset_manifest"],
                str(restored_run_dir / "manifest" / "dataset_manifest.csv"),
            )
            self.assertTrue(
                restored_manifest["manifest_files"]["preflight_report_json"].startswith(str(restored_run_dir))
            )
            self.assertTrue(restored_manifest["output_files"]["episode_results_csv"].startswith(str(restored_run_dir)))
            self.assertIsInstance(json.dumps(report), str)

    def test_restore_rejects_relative_path_traversal_in_episode_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "restore_case"
            layout = self._build_run_tree(run_dir)
            artifact_path = layout["episode_artifacts"] / "episode-1.json"
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            payload["log_path_relative"] = "../../outside.jsonl"
            artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "restore_path_outside_run_dir"):
                rewrite_restored_run_paths(run_dir)

    def test_checkpoint_preserves_last_successful_checkpoint_when_metadata_finalize_fails(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient()
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=client)
            original_commit = client.commit_files

            def fail_metadata_finalize(
                repo_id: str,
                files: list[tuple[Path, str]],
                commit_message: str,
            ) -> dict[str, str]:
                committed_paths = {path_in_repo for _, path_in_repo in files}
                metadata_paths = {
                    f"hf_run/manifest/{manager.state_path.name}",
                    f"hf_run/summaries/{manager.summary_path.name}",
                }
                if len(client.commit_calls) >= 2 and committed_paths == metadata_paths:
                    raise RuntimeError("finalize boom")
                return original_commit(repo_id, files, commit_message)

            client.commit_files = fail_metadata_finalize  # type: ignore[assignment]

            checkpoint = manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)

            self.assertEqual(checkpoint["status"], "failed")
            self.assertEqual(manager.state["last_successful_checkpoint"]["sequence"], 1)
            self.assertEqual(manager.state["last_successful_checkpoint"]["status"], "success")
            self.assertTrue(manager.state["non_metadata_files"])

    def test_checkpoint_does_not_reupload_non_metadata_after_finalize_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient()
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=client)
            original_commit = client.commit_files
            finalize_failures_remaining = 2

            def fail_once_on_metadata_finalize(
                repo_id: str,
                files: list[tuple[Path, str]],
                commit_message: str,
            ) -> dict[str, str]:
                nonlocal finalize_failures_remaining
                committed_paths = {path_in_repo for _, path_in_repo in files}
                metadata_paths = {
                    f"hf_run/manifest/{manager.state_path.name}",
                    f"hf_run/summaries/{manager.summary_path.name}",
                }
                if finalize_failures_remaining > 0 and committed_paths == metadata_paths:
                    finalize_failures_remaining -= 1
                    raise RuntimeError("finalize boom")
                return original_commit(repo_id, files, commit_message)

            client.commit_files = fail_once_on_metadata_finalize  # type: ignore[assignment]
            first = manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)
            first_upload_count = len(client.upload_calls)

            client.commit_files = original_commit  # type: ignore[assignment]
            second = manager.checkpoint("manifest_initialized_retry", completed_episodes=0, force=True)
            second_uploads = client.upload_calls[first_upload_count:]
            second_uploaded_paths = {path_in_repo for _, path_in_repo in second_uploads}

            self.assertEqual(first["status"], "failed")
            self.assertEqual(second["status"], "success")
            self.assertNotIn("hf_run/logs/episode-1.jsonl", second_uploaded_paths)
            self.assertNotIn("hf_run/scores/episode-1.json", second_uploaded_paths)
            self.assertIn(f"hf_run/manifest/{manager.state_path.name}", second_uploaded_paths)
            self.assertIn(f"hf_run/summaries/{manager.summary_path.name}", second_uploaded_paths)

    def test_corrupt_local_backup_state_is_backed_up_and_reinitialized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "hf_run"
            layout = self._build_run_tree(run_dir)
            state_path = layout["manifest"] / HF_BACKUP_STATE_FILENAME
            state_path.write_text("{invalid-json", encoding="utf-8")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                manager = HFDualRepoBackupManager(self._settings(), layout, run_id="hf_run", client=FakeHFClient())

            self.assertEqual(manager.state["run_id"], "hf_run")
            self.assertEqual(manager.state["checkpoint_sequence"], 0)
            self.assertTrue(list(layout["manifest"].glob(f"{HF_BACKUP_STATE_FILENAME}.corrupt-*.bak")))
            self.assertTrue(any("hf_backup_state_reinitialized" in str(item.message) for item in caught))

    def test_hf_client_retries_commit_files_on_rate_limit(self):
        class StubApi:
            def __init__(self):
                self.create_commit_calls = 0

            def create_commit(self, **kwargs):
                self.create_commit_calls += 1
                if self.create_commit_calls < 3:
                    raise RuntimeError("429 Too Many Requests")
                return type(
                    "CommitInfo",
                    (),
                    {"oid": "commit-3", "commit_url": "https://hf.co/datasets/anonymous/backup/commit/3"},
                )()

        client = HFHubClient("test-token")
        client.api = StubApi()
        with tempfile.TemporaryDirectory() as temp_dir:
            sample_path = Path(temp_dir) / "sample.json"
            sample_path.write_text("{}", encoding="utf-8")
            with patch("medinsider.fhir.hf_backup.time.sleep") as sleep:
                result = client.commit_files(
                    repo_id="anonymous/backup",
                    files=[(sample_path, "run/sample.json")],
                    commit_message="test",
                )
        self.assertEqual(result["revision"], "commit-3")
        self.assertEqual(client.api.create_commit_calls, 3)
        self.assertEqual(sleep.call_count, 2)

    def test_hf_retryable_error_recognizes_forcibly_closed_windows_message(self):
        self.assertTrue(
            _is_retryable_hf_error(RuntimeError("[WinError 10054] An existing connection was forcibly closed"))
        )

    def test_hf_client_retries_snapshot_download_on_timeout(self):
        client = HFHubClient("test-token")
        attempts = {"count": 0}

        def flaky_snapshot_download(**kwargs):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise TimeoutError("download timed out")
            local_dir = Path(kwargs["local_dir"])
            (local_dir / "restore_case").mkdir(parents=True, exist_ok=True)
            return str(local_dir)

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("medinsider.fhir.hf_backup.snapshot_download", side_effect=flaky_snapshot_download),
                patch("medinsider.fhir.hf_backup.time.sleep") as sleep,
            ):
                result = client.snapshot_download_run("anonymous/backup", "restore_case", Path(temp_dir))

        self.assertEqual(result, Path(temp_dir))
        self.assertEqual(attempts["count"], 3)
        self.assertEqual(sleep.call_count, 2)

    def test_hf_client_list_files_ignores_repo_folders_when_type_missing(self):
        client = HFHubClient("test-token")

        class StubApi:
            def list_repo_tree(self, **kwargs):
                folder_type = type("RepoFolder", (), {})
                file_type = type("RepoFile", (), {})
                folder = folder_type()
                folder.path = "restore_case/artifacts"
                folder.type = None
                data_file = file_type()
                data_file.path = "restore_case/artifacts/episode_results.csv"
                data_file.type = None
                return [folder, data_file]

        client.api = StubApi()

        self.assertEqual(
            client.list_files("anonymous/backup", "restore_case"),
            ["restore_case/artifacts/episode_results.csv"],
        )

    def test_hf_client_falls_back_to_individual_downloads_when_snapshot_download_fails(self):
        client = HFHubClient("test-token")
        with tempfile.TemporaryDirectory() as temp_dir:
            source_file = Path(temp_dir) / "source.json"
            source_file.write_text('{"ok": true}', encoding="utf-8")
            destination_root = Path(temp_dir) / "restore"

            def fake_download_file(repo_id: str, path_in_repo: str, local_path: Path) -> Path:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_file, local_path)
                return local_path

            with patch("medinsider.fhir.hf_backup.snapshot_download", side_effect=RuntimeError("client closed")):
                with patch.object(
                    client,
                    "list_files",
                    return_value=["restore_case/manifest/run_manifest.json"],
                ):
                    with patch.object(client, "download_file", side_effect=fake_download_file):
                        result = client.snapshot_download_run(
                            "anonymous/backup",
                            "restore_case",
                            destination_root,
                        )
            restored_manifest = destination_root / "restore_case" / "manifest" / "run_manifest.json"
            self.assertEqual(result, destination_root)
            self.assertTrue(restored_manifest.exists())

    def test_choose_restore_source_ignores_repos_without_successful_checkpoints(self):
        client = FakeHFClient()
        client.ensure_repo("repo_failed")
        client.ensure_repo("repo_good")
        run_id = "restore_case"
        client.files["repo_failed"][f"{run_id}/manifest/{HF_BACKUP_STATE_FILENAME}"] = json.dumps(
            {
                "checkpoint_sequence": 5,
                "updated_at_utc": "2026-04-18T12:00:00+00:00",
                "last_successful_checkpoint": {},
            }
        ).encode("utf-8")
        client.files["repo_good"][f"{run_id}/manifest/{HF_BACKUP_STATE_FILENAME}"] = json.dumps(
            {
                "checkpoint_sequence": 4,
                "updated_at_utc": "2026-04-18T11:00:00+00:00",
                "last_successful_checkpoint": {
                    "sequence": 4,
                    "updated_at_utc": "2026-04-18T11:00:00+00:00",
                },
            }
        ).encode("utf-8")

        selected = choose_restore_source(run_id, [("failed", "repo_failed"), ("good", "repo_good")], client)

        self.assertEqual(selected["label"], "good")
        self.assertEqual(selected["sequence"], 4)

    def test_verify_hf_backup_reports_missing_required_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir) / "runs" / "verify_case"
            layout = self._build_run_tree(run_dir)
            client = FakeHFClient()
            manager = HFDualRepoBackupManager(self._settings(), layout, run_id="verify_case", client=client)
            manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)
            del client.files["anonymous/secondary-backup"]["verify_case/manifest/run_manifest.json"]

            report = verify_hf_backup(
                "verify_case",
                [
                    ("primary", "anonymous/primary-backup"),
                    ("secondary", "anonymous/secondary-backup"),
                ],
                token="test-token",
                client=client,
            )

            self.assertFalse(report["ok"])
            secondary = next(item for item in report["repos"] if item["label"] == "secondary")
            self.assertIn("verify_case/manifest/run_manifest.json", secondary["missing_paths"])

    def test_restore_script_returns_json_error_on_restore_failure(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "restore_phase4_v2_from_hf.py"
        spec = spec_from_file_location("restore_phase4_v2_from_hf_script", script_path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        stdout = StringIO()
        with (
            patch.dict("os.environ", {"HF_TOKEN": "test-token"}, clear=False),
            patch("medinsider.fhir.hf_backup.restore_run_from_hf", side_effect=RuntimeError("boom")),
            redirect_stdout(stdout),
        ):
            exit_code = module.main(
                [
                    "--run-id",
                    "restore_case",
                    "--hf-backup-primary-repo",
                    "anonymous/primary-backup",
                    "--hf-backup-secondary-repo",
                    "anonymous/secondary-backup",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["run_id"], "restore_case")
        self.assertIn("RuntimeError:boom", payload["error"])

    def test_restore_script_returns_json_error_on_repo_resolution_failure(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "restore_phase4_v2_from_hf.py"
        spec = spec_from_file_location("restore_phase4_v2_from_hf_repo_error_script", script_path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = module.main(["--run-id", "restore_case", "--run-config", "does-not-exist.json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["run_id"], "restore_case")
        self.assertIn("FileNotFoundError", payload["error"])

    def test_verify_script_returns_json_error_on_repo_resolution_failure(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_phase4_v2_hf_backup.py"
        spec = spec_from_file_location("verify_phase4_v2_hf_backup_repo_error_script", script_path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = module.main(["--run-id", "verify_case", "--run-config", "does-not-exist.json"])

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["run_id"], "verify_case")
        self.assertIn("FileNotFoundError", payload["error"])

    def test_verify_script_returns_json_error_on_verification_failure(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "verify_phase4_v2_hf_backup.py"
        spec = spec_from_file_location("verify_phase4_v2_hf_backup_failure_script", script_path)
        self.assertIsNotNone(spec)
        module = module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)

        stdout = StringIO()
        with (
            patch.dict("os.environ", {"HF_TOKEN": "test-token"}, clear=False),
            patch("medinsider.fhir.hf_backup.verify_hf_backup", side_effect=RuntimeError("boom")),
            redirect_stdout(stdout),
        ):
            exit_code = module.main(
                [
                    "--run-id",
                    "verify_case",
                    "--hf-backup-primary-repo",
                    "anonymous/primary-backup",
                    "--hf-backup-secondary-repo",
                    "anonymous/secondary-backup",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["run_id"], "verify_case")
        self.assertIn("RuntimeError:boom", payload["error"])


if __name__ == "__main__":
    unittest.main()
