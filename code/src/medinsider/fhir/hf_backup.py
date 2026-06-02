import json
import os
import shutil
import tempfile
import time
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download, snapshot_download
except ImportError:  # pragma: no cover - exercised via validation paths
    CommitOperationAdd = None
    HfApi = None
    hf_hub_download = None
    snapshot_download = None


HF_TOKEN_ENV_NAMES = ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN")
HF_BACKUP_SUMMARY_FILENAME = "hf_backup_summary.json"
HF_BACKUP_STATE_FILENAME = "hf_backup_state.json"
HF_REQUIRED_MANIFEST_FILES = {
    "manifest/run_manifest.json",
    "manifest/preflight_report.json",
    "manifest/effective_run_config_redacted.json",
    "manifest/resolved_selection.csv",
    "manifest/dataset_manifest.csv",
    "manifest/selection_manifest.csv",
}
HF_EXCLUDED_BACKUP_FILES = {"manifest/effective_run_config.json"}
DEFAULT_HF_BACKUP_BATCH_SIZE = 5
HF_RETRY_ATTEMPTS = 5
HF_RETRY_BASE_DELAY_SECONDS = 2.0
HF_RETRYABLE_STATUS_CODES = {408, 409, 423, 425, 429, 500, 502, 503, 504}
METADATA_RELATIVE_PATHS = {
    f"manifest/{HF_BACKUP_STATE_FILENAME}",
    f"summaries/{HF_BACKUP_SUMMARY_FILENAME}",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def huggingface_hub_available() -> bool:
    return (
        CommitOperationAdd is not None
        and HfApi is not None
        and hf_hub_download is not None
        and snapshot_download is not None
    )


def _resolve_hf_token() -> tuple[str, str]:
    for env_name in HF_TOKEN_ENV_NAMES:
        value = os.getenv(env_name, "").strip()
        if value:
            return env_name, value
    return "", ""


def _backup_section(config: dict[str, Any]) -> Any:
    if "hf_backup" in config:
        return config.get("hf_backup")
    runtime = config.get("runtime", {})
    if isinstance(runtime, dict) and "hf_backup" in runtime:
        return runtime.get("hf_backup")
    return {}


def _string_or_empty(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


@dataclass(frozen=True)
class HFBackupSettings:
    enabled: bool
    strict: bool
    dry_run: bool
    verify_remote: bool
    batch_size: int
    primary_repo: str
    secondary_repo: str
    token_env_name: str
    token: str

    def repo_pairs(self) -> list[tuple[str, str]]:
        return [
            ("primary", self.primary_repo),
            ("secondary", self.secondary_repo),
        ]

    def public_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "strict": self.strict,
            "dry_run": self.dry_run,
            "verify_remote": self.verify_remote,
            "batch_size": self.batch_size,
            "primary_repo": self.primary_repo,
            "secondary_repo": self.secondary_repo,
            "token_env_name": self.token_env_name,
        }


def resolve_hf_backup_settings(config: dict[str, Any]) -> HFBackupSettings:
    section = _backup_section(config)
    if not isinstance(section, dict):
        section = {}
    token_env_name, token = _resolve_hf_token()
    return HFBackupSettings(
        enabled=_safe_bool(section.get("enabled", False), False),
        strict=_safe_bool(section.get("strict", False), False),
        dry_run=_safe_bool(section.get("dry_run", False), False),
        verify_remote=_safe_bool(section.get("verify_remote", True), True),
        batch_size=_safe_int(section.get("batch_size", DEFAULT_HF_BACKUP_BATCH_SIZE), DEFAULT_HF_BACKUP_BATCH_SIZE),
        primary_repo=_string_or_empty(section.get("primary_repo") or os.getenv("HF_BACKUP_PRIMARY_REPO", "")),
        secondary_repo=_string_or_empty(section.get("secondary_repo") or os.getenv("HF_BACKUP_SECONDARY_REPO", "")),
        token_env_name=token_env_name,
        token=token,
    )


def validate_hf_backup_settings(config: dict[str, Any]) -> list[str]:
    if "hf_backup" in config:
        section = config.get("hf_backup")
        if not isinstance(section, dict):
            return ["hf_backup_config_invalid"]
    else:
        runtime = config.get("runtime", {})
        if isinstance(runtime, dict) and "hf_backup" in runtime:
            section = runtime.get("hf_backup")
            if not isinstance(section, dict):
                return ["hf_backup_config_invalid"]
        else:
            section = {}

    errors: list[str] = []
    bool_fields = {
        "enabled": False,
        "strict": False,
        "dry_run": False,
        "verify_remote": True,
    }
    for field_name in bool_fields:
        raw_value = section.get(field_name, bool_fields[field_name])
        if not isinstance(raw_value, bool):
            errors.append(f"hf_backup_{field_name}_invalid")

    raw_batch_size = section.get("batch_size", DEFAULT_HF_BACKUP_BATCH_SIZE)
    try:
        batch_size = int(raw_batch_size)
    except (TypeError, ValueError):
        errors.append("hf_backup_batch_size_invalid")
        batch_size = DEFAULT_HF_BACKUP_BATCH_SIZE
    if batch_size <= 0:
        errors.append("hf_backup_batch_size_invalid")

    enabled = section.get("enabled", False) if isinstance(section.get("enabled", False), bool) else False
    if not enabled:
        return errors

    settings = resolve_hf_backup_settings(config)
    if not settings.primary_repo:
        errors.append("hf_backup_primary_repo_missing")
    if not settings.secondary_repo:
        errors.append("hf_backup_secondary_repo_missing")
    if not settings.dry_run and not settings.token:
        errors.append("hf_backup_token_missing")
    if not settings.dry_run and not huggingface_hub_available():
        errors.append("hf_backup_dependency_missing:huggingface_hub")
    return errors


def summarize_hf_backup_settings(config: dict[str, Any]) -> dict[str, Any]:
    return resolve_hf_backup_settings(config).public_dict()


def resolve_backup_repo_pairs(
    *,
    run_config_path: str | None = None,
    primary_repo: str | None = None,
    secondary_repo: str | None = None,
) -> list[tuple[str, str]]:
    from medinsider.fhir.pilot_runtime import load_run_config

    if run_config_path:
        settings = resolve_hf_backup_settings(load_run_config(run_config_path))
        primary = primary_repo or settings.primary_repo
        secondary = secondary_repo or settings.secondary_repo
    else:
        primary = primary_repo
        secondary = secondary_repo
    repo_pairs = [("primary", _string_or_empty(primary)), ("secondary", _string_or_empty(secondary))]
    return [(label, repo_id) for label, repo_id in repo_pairs if repo_id]


def _relative_paths_for_backup(run_dir: Path) -> list[str]:
    relative_paths: list[str] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(run_dir).as_posix()
        if relative in HF_EXCLUDED_BACKUP_FILES:
            continue
        if relative.endswith(".tmp"):
            continue
        relative_paths.append(relative)
    return relative_paths


def restore_required_files(run_dir: Path) -> list[str]:
    existing = set(_relative_paths_for_backup(run_dir))
    return sorted(path for path in HF_REQUIRED_MANIFEST_FILES if path in existing)


def _metadata_relative_paths() -> list[str]:
    return sorted(METADATA_RELATIVE_PATHS)


def build_backup_summary(state: dict[str, Any], settings: HFBackupSettings) -> dict[str, Any]:
    checkpoints = state.get("checkpoints", [])
    last_checkpoint = checkpoints[-1] if checkpoints else {}
    warnings = [checkpoint.get("warning", "") for checkpoint in checkpoints if checkpoint.get("warning")]
    return {
        "run_id": state.get("run_id", ""),
        "enabled": settings.enabled,
        "strict": settings.strict,
        "dry_run": settings.dry_run,
        "verify_remote": settings.verify_remote,
        "batch_size": settings.batch_size,
        "checkpoint_count": len(checkpoints),
        "last_checkpoint": last_checkpoint,
        "last_successful_checkpoint": state.get("last_successful_checkpoint", {}),
        "repos": state.get("repos", {}),
        "warnings": warnings,
        "warning_count": len(warnings),
        "updated_at_utc": state.get("updated_at_utc", ""),
    }


def create_empty_backup_state(run_id: str, settings: HFBackupSettings) -> dict[str, Any]:
    repos: dict[str, Any] = {}
    for label, repo_id in settings.repo_pairs():
        repos[label] = {
            "repo_id": repo_id,
            "last_success_at_utc": "",
            "last_checkpoint_sequence": 0,
            "last_revision": "",
            "last_commit_url": "",
            "last_error": "",
            "verified_file_count": 0,
            "last_status": "pending",
        }
    return {
        "run_id": run_id,
        "updated_at_utc": "",
        "checkpoint_sequence": 0,
        "last_attempted_completed_episodes": 0,
        "last_successful_checkpoint": {},
        "non_metadata_files": {},
        "repos": repos,
        "checkpoints": [],
    }


def _write_backup_state(
    state_path: Path,
    summary_path: Path,
    state: dict[str, Any],
    settings: HFBackupSettings,
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(build_backup_summary(state, settings), indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _backup_corrupt_json_file(path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = path.with_name(f"{path.name}.corrupt-{timestamp}.bak")
    shutil.copy2(path, backup_path)
    return backup_path


def _load_existing_backup_state(path: Path, run_id: str, settings: HFBackupSettings) -> dict[str, Any]:
    if not path.exists():
        return create_empty_backup_state(run_id, settings)
    try:
        payload = _read_json(path)
        if isinstance(payload, dict):
            return payload
        raise ValueError(f"backup_state_invalid_type:{type(payload).__name__}")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        backup_note = ""
        try:
            backup_path = _backup_corrupt_json_file(path)
            backup_note = f"; backed up to {backup_path}"
        except OSError as backup_exc:
            backup_note = f"; failed to back up corrupt state: {type(backup_exc).__name__}:{backup_exc}"
        warnings.warn(
            (f"hf_backup_state_reinitialized:{path}:{type(exc).__name__}:{exc}{backup_note}"),
            RuntimeWarning,
            stacklevel=2,
        )
        return create_empty_backup_state(run_id, settings)


def _file_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hf_error_status_code(exc: Exception) -> int | None:
    for candidate in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        try:
            if candidate is not None:
                return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def _is_retryable_hf_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionError)):
        return True
    status_code = _hf_error_status_code(exc)
    if status_code in HF_RETRYABLE_STATUS_CODES:
        return True
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "timeout",
            "timed out",
            "rate limit",
            "too many requests",
            "temporarily unavailable",
            "forcibly closed",
            "connection reset",
            "connection aborted",
            "aborted by the software",
            "connection error",
            "network error",
            "not a socket",
            "service unavailable",
            "bad gateway",
            "gateway timeout",
        )
    )


class HFHubClient:
    def __init__(self, token: str):
        if not huggingface_hub_available():
            raise RuntimeError("huggingface_hub is required for live HF backup")
        self.token = token
        self.api = HfApi(token=token)

    def _call_with_retry(self, fn, *, operation_name: str):
        last_exc: Exception | None = None
        for attempt in range(1, HF_RETRY_ATTEMPTS + 1):
            try:
                return fn()
            except Exception as exc:  # pragma: no cover - exercised via tests with stubs
                last_exc = exc
                if attempt >= HF_RETRY_ATTEMPTS or not _is_retryable_hf_error(exc):
                    raise
                time.sleep(HF_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc
        raise RuntimeError(f"hf_backup_{operation_name}_failed_without_exception")

    def ensure_repo(self, repo_id: str, private: bool = True) -> None:
        self._call_with_retry(
            lambda: self.api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True),
            operation_name="ensure_repo",
        )

    def commit_files(
        self,
        repo_id: str,
        files: list[tuple[Path, str]],
        commit_message: str,
    ) -> dict[str, str]:
        if not files:
            return {"revision": "", "commit_url": ""}
        operations = [
            CommitOperationAdd(path_in_repo=path_in_repo, path_or_fileobj=str(local_path))
            for local_path, path_in_repo in files
        ]
        info = self._call_with_retry(
            lambda: self.api.create_commit(
                repo_id=repo_id,
                repo_type="dataset",
                operations=operations,
                commit_message=commit_message,
            ),
            operation_name="create_commit",
        )
        return {
            "revision": str(getattr(info, "oid", "") or ""),
            "commit_url": str(getattr(info, "commit_url", "") or ""),
        }

    def upload_file(self, repo_id: str, local_path: Path, path_in_repo: str, commit_message: str) -> dict[str, str]:
        return self.commit_files(
            repo_id=repo_id,
            files=[(local_path, path_in_repo)],
            commit_message=commit_message,
        )

    def list_files(self, repo_id: str, prefix: str) -> list[str]:
        paths: list[str] = []
        entries = self._call_with_retry(
            lambda: self.api.list_repo_tree(
                repo_id=repo_id,
                repo_type="dataset",
                path_in_repo=prefix,
                recursive=True,
                expand=False,
            ),
            operation_name="list_repo_tree",
        )
        for entry in entries:
            path = str(getattr(entry, "path", "") or "")
            entry_type = str(getattr(entry, "type", "") or "").lower()
            if not entry_type:
                class_name = entry.__class__.__name__.lower()
                if "folder" in class_name or "directory" in class_name:
                    entry_type = "folder"
                elif "file" in class_name:
                    entry_type = "file"
            if path and entry_type not in {"directory", "folder"}:
                paths.append(path)
        return sorted(set(paths))

    def download_text(self, repo_id: str, path_in_repo: str) -> str:
        downloaded = self._call_with_retry(
            lambda: hf_hub_download(
                repo_id=repo_id,
                filename=path_in_repo,
                repo_type="dataset",
                token=self.token,
            ),
            operation_name="download_text",
        )
        return Path(downloaded).read_text(encoding="utf-8")

    def download_file(self, repo_id: str, path_in_repo: str, local_path: Path) -> Path:
        downloaded = self._call_with_retry(
            lambda: hf_hub_download(
                repo_id=repo_id,
                filename=path_in_repo,
                repo_type="dataset",
                token=self.token,
            ),
            operation_name="download_file",
        )
        local_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(downloaded, local_path)
        return local_path

    def _download_run_files_individually(self, repo_id: str, run_id: str, local_dir: Path) -> Path:
        file_paths = [path for path in self.list_files(repo_id, run_id) if path.startswith(f"{run_id}/")]
        if not file_paths:
            raise FileNotFoundError(f"restore_source_missing:{repo_id}:{run_id}")
        for path_in_repo in file_paths:
            relative_path = Path(path_in_repo).relative_to(run_id)
            self.download_file(repo_id, path_in_repo, local_dir / run_id / relative_path)
        return local_dir

    def snapshot_download_run(self, repo_id: str, run_id: str, local_dir: Path) -> Path:
        try:
            self._call_with_retry(
                lambda: snapshot_download(
                    repo_id=repo_id,
                    repo_type="dataset",
                    token=self.token,
                    local_dir=str(local_dir),
                    allow_patterns=[f"{run_id}/**", f"{run_id}/*"],
                ),
                operation_name="snapshot_download",
            )
            return local_dir
        except Exception as snapshot_exc:
            try:
                return self._download_run_files_individually(repo_id, run_id, local_dir)
            except Exception as fallback_exc:
                raise RuntimeError(
                    "hf_backup_restore_download_failed:"
                    f"snapshot={type(snapshot_exc).__name__}:{snapshot_exc};"
                    f"fallback={type(fallback_exc).__name__}:{fallback_exc}"
                ) from fallback_exc


def build_hf_client(token: str) -> HFHubClient:
    return HFHubClient(token)


class HFDualRepoBackupManager:
    def __init__(
        self,
        settings: HFBackupSettings,
        layout: dict[str, Path],
        run_id: str,
        *,
        client: HFHubClient | Any | None = None,
    ):
        self.settings = settings
        self.layout = layout
        self.run_id = run_id
        self.run_dir = layout["run_dir"]
        self.state_path = layout["manifest"] / HF_BACKUP_STATE_FILENAME
        self.summary_path = layout["summaries"] / HF_BACKUP_SUMMARY_FILENAME
        self.client = client if client is not None else (None if settings.dry_run else build_hf_client(settings.token))
        self.state = _load_existing_backup_state(self.state_path, run_id, settings)
        self.last_attempted_completed_episodes = int(self.state.get("last_attempted_completed_episodes", 0) or 0)
        _write_backup_state(self.state_path, self.summary_path, self.state, settings)

    def metadata_paths(self) -> dict[str, Path]:
        return {"state_json": self.state_path, "summary_json": self.summary_path}

    def public_status(self) -> dict[str, Any]:
        summary = build_backup_summary(self.state, self.settings)
        return {
            **self.settings.public_dict(),
            "checkpoint_count": summary["checkpoint_count"],
            "last_checkpoint": summary["last_checkpoint"],
            "last_successful_checkpoint": summary["last_successful_checkpoint"],
            "warning_count": summary["warning_count"],
            "repos": summary["repos"],
            "summary_json": str(self.summary_path),
            "state_json": str(self.state_path),
        }

    def should_checkpoint(self, completed_episodes: int) -> bool:
        if not self.settings.enabled:
            return False
        return (completed_episodes - self.last_attempted_completed_episodes) >= self.settings.batch_size

    def _current_non_metadata_hashes(self) -> dict[str, str]:
        hashes: dict[str, str] = {}
        for relative in _relative_paths_for_backup(self.run_dir):
            if relative in METADATA_RELATIVE_PATHS:
                continue
            hashes[relative] = _file_sha256(self.run_dir / relative)
        return hashes

    def _write_pending_state(
        self,
        sequence: int,
        reason: str,
        completed_episodes: int,
        non_metadata_hashes: dict[str, str],
        changed_non_metadata_files: list[str],
    ) -> dict[str, Any]:
        checkpoint = {
            "sequence": sequence,
            "reason": reason,
            "created_at_utc": utc_now(),
            "completed_episodes": completed_episodes,
            "changed_non_metadata_files": changed_non_metadata_files,
            "expected_file_count": len(non_metadata_hashes) + len(METADATA_RELATIVE_PATHS),
            "status": "pending",
            "repo_results": {},
        }
        checkpoints = [*self.state.get("checkpoints", []), checkpoint]
        self.state.update(
            {
                "checkpoint_sequence": sequence,
                "last_attempted_completed_episodes": completed_episodes,
                "updated_at_utc": utc_now(),
                "checkpoints": checkpoints,
            }
        )
        _write_backup_state(self.state_path, self.summary_path, self.state, self.settings)
        return checkpoint

    def _path_in_repo(self, relative_path: str) -> str:
        return f"{self.run_id}/{relative_path}"

    def _upload_paths(
        self,
        repo_id: str,
        relative_paths: list[str],
        *,
        reason: str,
        sequence: int,
    ) -> dict[str, str]:
        files = [(self.run_dir / relative_path, self._path_in_repo(relative_path)) for relative_path in relative_paths]
        return self.client.commit_files(
            repo_id=repo_id,
            files=files,
            commit_message=f"[medinsider] {self.run_id} checkpoint {sequence} ({reason})",
        )

    def _verify_remote_files(self, repo_id: str, expected_relative_paths: list[str]) -> dict[str, Any]:
        remote_paths = set(self.client.list_files(repo_id=repo_id, prefix=self.run_id))
        expected_paths = {self._path_in_repo(relative_path) for relative_path in expected_relative_paths}
        missing = sorted(expected_paths.difference(remote_paths))
        return {
            "ok": not missing,
            "missing_paths": missing,
            "verified_file_count": len(expected_paths) - len(missing),
        }

    def checkpoint(self, reason: str, completed_episodes: int, *, force: bool = False) -> dict[str, Any]:
        if not self.settings.enabled:
            return {"enabled": False}
        if not force and not self.should_checkpoint(completed_episodes):
            return {"enabled": True, "skipped": True}

        self.last_attempted_completed_episodes = completed_episodes
        non_metadata_hashes = self._current_non_metadata_hashes()
        previous_hashes = self.state.get("non_metadata_files", {})
        changed_non_metadata_files = sorted(
            [
                relative_path
                for relative_path, digest in non_metadata_hashes.items()
                if previous_hashes.get(relative_path) != digest
            ]
        )
        sequence = int(self.state.get("checkpoint_sequence", 0) or 0) + 1
        checkpoint = self._write_pending_state(
            sequence,
            reason,
            completed_episodes,
            non_metadata_hashes,
            changed_non_metadata_files,
        )
        metadata_relative_paths = _metadata_relative_paths()
        expected_relative_paths = sorted([*non_metadata_hashes.keys(), *metadata_relative_paths])

        repo_results: dict[str, Any] = {}
        if self.settings.dry_run:
            for label, repo_id in self.settings.repo_pairs():
                repo_results[label] = {
                    "repo_id": repo_id,
                    "status": "dry_run",
                    "uploaded_file_count": len(changed_non_metadata_files) + len(metadata_relative_paths),
                    "verified": True,
                    "verified_file_count": len(expected_relative_paths),
                    "revision": "",
                    "commit_url": "",
                    "error": "",
                }
        else:
            for label, repo_id in self.settings.repo_pairs():
                try:
                    self.client.ensure_repo(repo_id, private=True)
                    upload_result = self._upload_paths(
                        repo_id,
                        [*changed_non_metadata_files, *metadata_relative_paths],
                        reason=reason,
                        sequence=sequence,
                    )
                    if self.settings.verify_remote:
                        verification = self._verify_remote_files(repo_id, expected_relative_paths)
                        status = "success" if verification["ok"] else "verification_failed"
                        error = ""
                        if not verification["ok"]:
                            error = "hf_backup_missing_remote_files:" + ",".join(verification["missing_paths"])
                    else:
                        verification = {"ok": True, "missing_paths": [], "verified_file_count": 0}
                        status = "success"
                        error = ""
                    repo_results[label] = {
                        "repo_id": repo_id,
                        "status": status,
                        "uploaded_file_count": len(changed_non_metadata_files) + len(metadata_relative_paths),
                        "verified": verification["ok"],
                        "verified_file_count": verification["verified_file_count"],
                        "revision": upload_result["revision"],
                        "commit_url": upload_result["commit_url"],
                        "error": error,
                    }
                except Exception as exc:  # pragma: no cover - exercised via fake clients in tests
                    repo_results[label] = {
                        "repo_id": repo_id,
                        "status": "failed",
                        "uploaded_file_count": 0,
                        "verified": False,
                        "verified_file_count": 0,
                        "revision": "",
                        "commit_url": "",
                        "error": f"{type(exc).__name__}:{exc}",
                    }

        main_pass_successful_labels = [
            label for label, result in repo_results.items() if result["status"] in {"success", "dry_run"}
        ]
        successful_labels = main_pass_successful_labels
        if len(successful_labels) == len(repo_results):
            overall_status = "success" if not self.settings.dry_run else "dry_run"
            warning = ""
        elif successful_labels:
            overall_status = "partial_failure"
            warning = "hf_backup_partial_failure"
        else:
            overall_status = "failed"
            warning = "hf_backup_both_repos_failed"

        checkpoint["status"] = overall_status
        checkpoint["repo_results"] = repo_results
        checkpoint["updated_at_utc"] = utc_now()
        if warning:
            checkpoint["warning"] = warning
        else:
            checkpoint.pop("warning", None)
        self.state["updated_at_utc"] = checkpoint["updated_at_utc"]
        self.state["checkpoints"][-1] = checkpoint

        if successful_labels:
            self.state["last_successful_checkpoint"] = {
                "sequence": sequence,
                "reason": reason,
                "completed_episodes": completed_episodes,
                "updated_at_utc": checkpoint["updated_at_utc"],
                "status": overall_status,
            }
        else:
            self.state["last_successful_checkpoint"] = {}

        for label, result in repo_results.items():
            repo_state = self.state["repos"][label]
            repo_state["last_status"] = result["status"]
            repo_state["last_error"] = result["error"]
            if result["status"] in {"success", "dry_run"}:
                repo_state["last_success_at_utc"] = checkpoint["updated_at_utc"]
                repo_state["last_checkpoint_sequence"] = sequence
                repo_state["last_revision"] = result["revision"]
                repo_state["last_commit_url"] = result["commit_url"]
                repo_state["verified_file_count"] = result["verified_file_count"]
        if overall_status == "dry_run":
            self.state["non_metadata_files"] = non_metadata_hashes
        elif len(main_pass_successful_labels) == len(repo_results):
            self.state["non_metadata_files"] = non_metadata_hashes

        _write_backup_state(self.state_path, self.summary_path, self.state, self.settings)

        if not self.settings.dry_run:
            for _label, result in repo_results.items():
                if result["status"] != "success":
                    continue
                repo_id = result["repo_id"]
                try:
                    upload_result = self._upload_paths(
                        repo_id,
                        metadata_relative_paths,
                        reason=reason,
                        sequence=sequence,
                    )
                    result["revision"] = upload_result["revision"]
                    result["commit_url"] = upload_result["commit_url"]
                    if self.settings.verify_remote:
                        verification = self._verify_remote_files(repo_id, expected_relative_paths)
                        result["verified"] = verification["ok"]
                        result["verified_file_count"] = verification["verified_file_count"]
                        if not verification["ok"]:
                            result["status"] = "verification_failed"
                            result["error"] = "hf_backup_missing_remote_files:" + ",".join(
                                verification["missing_paths"]
                            )
                except Exception as exc:  # pragma: no cover - exercised via fake clients in tests
                    result["status"] = "failed"
                    result["verified"] = False
                    result["verified_file_count"] = 0
                    result["revision"] = ""
                    result["commit_url"] = ""
                    result["error"] = f"hf_backup_metadata_finalize_failed:{type(exc).__name__}:{exc}"

            successful_labels = [
                label for label, result in repo_results.items() if result["status"] in {"success", "dry_run"}
            ]
            if len(successful_labels) == len(repo_results):
                overall_status = "success"
                warning = ""
            elif successful_labels:
                overall_status = "partial_failure"
                warning = "hf_backup_partial_failure"
            else:
                overall_status = "failed"
                warning = "hf_backup_both_repos_failed"

            checkpoint["status"] = overall_status
            checkpoint["repo_results"] = repo_results
            if warning:
                checkpoint["warning"] = warning
            else:
                checkpoint.pop("warning", None)
            self.state["checkpoints"][-1] = checkpoint
            if successful_labels:
                self.state["last_successful_checkpoint"] = {
                    "sequence": sequence,
                    "reason": reason,
                    "completed_episodes": completed_episodes,
                    "updated_at_utc": checkpoint["updated_at_utc"],
                    "status": overall_status,
                }
            for label, result in repo_results.items():
                repo_state = self.state["repos"][label]
                repo_state["last_status"] = result["status"]
                repo_state["last_error"] = result["error"]
                if result["status"] in {"success", "dry_run"}:
                    repo_state["last_success_at_utc"] = checkpoint["updated_at_utc"]
                    repo_state["last_checkpoint_sequence"] = sequence
                    repo_state["last_revision"] = result["revision"]
                    repo_state["last_commit_url"] = result["commit_url"]
                    repo_state["verified_file_count"] = result["verified_file_count"]
            if overall_status == "success":
                self.state["non_metadata_files"] = non_metadata_hashes
            _write_backup_state(self.state_path, self.summary_path, self.state, self.settings)

        if self.settings.strict and not main_pass_successful_labels:
            raise RuntimeError(
                "hf_backup_strict_failure:" + ";".join(result["error"] for result in repo_results.values())
            )
        return checkpoint


def load_remote_backup_state(run_id: str, repo_id: str, client: HFHubClient | Any) -> dict[str, Any]:
    return json.loads(client.download_text(repo_id, f"{run_id}/manifest/{HF_BACKUP_STATE_FILENAME}"))


def choose_restore_source(
    run_id: str,
    repo_ids: list[tuple[str, str]],
    client: HFHubClient | Any,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for label, repo_id in repo_ids:
        try:
            state = load_remote_backup_state(run_id, repo_id, client)
        except Exception as exc:
            candidates.append(
                {
                    "label": label,
                    "repo_id": repo_id,
                    "ok": False,
                    "error": f"{type(exc).__name__}:{exc}",
                    "state": {},
                    "sequence": -1,
                    "updated_at_utc": "",
                }
            )
            continue
        checkpoint = state.get("last_successful_checkpoint", {})
        candidates.append(
            {
                "label": label,
                "repo_id": repo_id,
                "ok": True,
                "error": "",
                "state": state,
                "has_successful_checkpoint": bool(checkpoint),
                "sequence": int(checkpoint.get("sequence", -1) or -1),
                "updated_at_utc": str(checkpoint.get("updated_at_utc") or ""),
            }
        )
    viable = [
        candidate for candidate in candidates if candidate["ok"] and candidate.get("has_successful_checkpoint", False)
    ]
    if not viable:
        raise RuntimeError("hf_backup_restore_source_unavailable")
    viable.sort(key=lambda item: (item["sequence"], item["updated_at_utc"], item["label"]), reverse=True)
    selected = dict(viable[0])
    selected.pop("state", None)
    selected["candidates"] = [
        {key: value for key, value in candidate.items() if key != "state"} for candidate in candidates
    ]
    return selected


def verify_restored_run_layout(run_dir: Path) -> list[str]:
    errors: list[str] = []
    for relative_path in sorted(HF_REQUIRED_MANIFEST_FILES):
        if not (run_dir / relative_path).exists():
            errors.append(f"missing_required_restore_file:{relative_path}")
    return errors


def _restore_relative_path(run_dir: Path, relative_path: str) -> Path:
    resolved_run_dir = run_dir.resolve()
    resolved_candidate = (run_dir / relative_path).resolve()
    if not resolved_candidate.is_relative_to(resolved_run_dir):
        raise ValueError(f"restore_path_outside_run_dir:{relative_path}")
    return resolved_candidate


def _rewrite_nested_restored_paths(
    value: Any,
    *,
    original_run_dir: Path | None,
    restored_run_dir: Path,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _rewrite_nested_restored_paths(
                item,
                original_run_dir=original_run_dir,
                restored_run_dir=restored_run_dir,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _rewrite_nested_restored_paths(
                item,
                original_run_dir=original_run_dir,
                restored_run_dir=restored_run_dir,
            )
            for item in value
        ]
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or original_run_dir is None:
        return value
    candidate = Path(stripped)
    if not candidate.is_absolute():
        return value
    try:
        relative = candidate.resolve().relative_to(original_run_dir.resolve())
    except ValueError:
        return value
    return str((restored_run_dir / relative).resolve())


def rewrite_restored_run_paths(run_dir: Path) -> None:
    from medinsider.fhir.pilot_runtime import (
        _episode_artifact_path,
        load_episode_results,
        prepare_run_layout,
        write_json,
        write_run_outputs,
    )

    layout = prepare_run_layout(run_dir)
    run_manifest_path = layout["manifest"] / "run_manifest.json"
    if run_manifest_path.exists():
        run_manifest = _read_json(run_manifest_path)
        original_output_dir = str(run_manifest.get("output_dir", "")).strip()
        original_run_dir = Path(original_output_dir) if original_output_dir else None
        run_manifest = _rewrite_nested_restored_paths(
            run_manifest,
            original_run_dir=original_run_dir,
            restored_run_dir=run_dir,
        )
        run_manifest["output_dir"] = str(run_dir)
        dataset_manifest_copy = layout["manifest"] / "dataset_manifest.csv"
        if dataset_manifest_copy.exists():
            run_manifest["dataset_manifest"] = str(dataset_manifest_copy)
        selection_manifest_copy = layout["manifest"] / "selection_manifest.csv"
        if selection_manifest_copy.exists():
            run_manifest["selection_manifest"] = str(selection_manifest_copy)
        write_json(run_manifest_path, run_manifest)

    for artifact_path in sorted(layout["episode_artifacts"].glob("*.json")):
        payload = _read_json(artifact_path)
        log_relative = str(payload.get("log_path_relative", "")).strip()
        if log_relative:
            payload["log_path"] = str(_restore_relative_path(run_dir, log_relative))
        score_relative = str(payload.get("score_path_relative", "")).strip()
        if score_relative:
            payload["score_path"] = str(_restore_relative_path(run_dir, score_relative))
        write_json(_episode_artifact_path(layout, payload["episode_id"]), payload)

    results = load_episode_results(layout)
    if results:
        write_run_outputs(layout, results)


def restore_run_from_hf(
    run_id: str,
    destination_root: Path,
    repo_ids: list[tuple[str, str]],
    *,
    token: str,
    overwrite: bool = False,
    client: HFHubClient | Any | None = None,
) -> dict[str, Any]:
    backup_client = client if client is not None else build_hf_client(token)
    selected = choose_restore_source(run_id, repo_ids, backup_client)
    destination_root.mkdir(parents=True, exist_ok=True)
    run_dir = destination_root / run_id
    if run_dir.exists():
        if not overwrite:
            raise ValueError(f"restore_destination_exists:{run_dir}")
        shutil.rmtree(run_dir)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        backup_client.snapshot_download_run(selected["repo_id"], run_id, temp_root)
        source_dir = temp_root / run_id
        if not source_dir.exists():
            raise FileNotFoundError(f"restore_source_missing:{selected['repo_id']}:{run_id}")
        shutil.copytree(source_dir, run_dir)

    rewrite_restored_run_paths(run_dir)
    validation_errors = verify_restored_run_layout(run_dir)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "selected_repo": selected["repo_id"],
        "selected_label": selected["label"],
        "selected_sequence": selected["sequence"],
        "candidate_repos": selected["candidates"],
        "validation_errors": validation_errors,
        "ok": not validation_errors,
    }


def verify_hf_backup(
    run_id: str,
    repo_ids: list[tuple[str, str]],
    *,
    token: str,
    client: HFHubClient | Any | None = None,
) -> dict[str, Any]:
    backup_client = client if client is not None else build_hf_client(token)
    reports: list[dict[str, Any]] = []
    for label, repo_id in repo_ids:
        try:
            state = load_remote_backup_state(run_id, repo_id, backup_client)
            required_paths = set(HF_REQUIRED_MANIFEST_FILES | METADATA_RELATIVE_PATHS)
            remote_paths = set(backup_client.list_files(repo_id, run_id))
            expected_paths = {f"{run_id}/{relative_path}" for relative_path in required_paths}
            missing = sorted(expected_paths.difference(remote_paths))
            reports.append(
                {
                    "label": label,
                    "repo_id": repo_id,
                    "ok": not missing,
                    "missing_paths": missing,
                    "checkpoint_sequence": state.get("checkpoint_sequence", 0),
                    "last_successful_checkpoint": state.get("last_successful_checkpoint", {}),
                }
            )
        except Exception as exc:
            reports.append(
                {
                    "label": label,
                    "repo_id": repo_id,
                    "ok": False,
                    "missing_paths": [],
                    "error": f"{type(exc).__name__}:{exc}",
                    "checkpoint_sequence": 0,
                    "last_successful_checkpoint": {},
                }
            )
    return {
        "run_id": run_id,
        "repos": reports,
        "ok": all(report["ok"] for report in reports),
    }
