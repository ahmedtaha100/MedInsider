import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import time
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from medinsider.agents import build_agent as create_agent
from medinsider.fhir.hf_backup import (
    HFDualRepoBackupManager,
    resolve_hf_backup_settings,
    summarize_hf_backup_settings,
    validate_hf_backup_settings,
)
from medinsider.fhir.judge_pipeline import JudgePipeline
from medinsider.fhir.logger import FHIRActionLogger
from medinsider.fhir.mitigations import ComplianceCheckScenarioRunner
from medinsider.fhir.pair_validation import load_scenario, validate_selected_pairs
from medinsider.fhir.runner import FHIRScenarioRunner
from medinsider.fhir.scoring import load_jsonl, score_episode

SUPPORTED_AGENT_TYPES = {"scripted", "openai", "claude", "openweight", "openai_compatible"}
SUPPORTED_STRUCTURAL_MITIGATIONS = {"", "compliance_check_tool"}
ENV_VARS_BY_AGENT = {
    "openai": ["OPENAI_API_KEY"],
    "claude": ["ANTHROPIC_API_KEY"],
}
DEFAULT_OUTPUT_ROOT = "runs"
REQUIRED_DATASET_COLUMNS = {
    "episode_id",
    "scenario_family",
    "condition",
    "alignment_label",
    "twin_role",
    "pair_id",
    "pressure_condition",
    "path",
}
REQUIRED_SELECTION_COLUMNS = {"episode_id", "selection_group"}
SCORABLE_STATUSES = {"success", "max_call_termination"}
RETRYABLE_STATUSES = {"api_failure", "timeout"}
PRIMARY_METRICS = ["IVR", "MGR", "UPR", "AEOR", "PSD", "CDR", "ATC"]
MESSAGE_CODE_STATUS = {
    "jsondecodeerror": "malformed_action_json",
    "bad_action_json": "malformed_action_json",
    "invalid_action_type": "invalid_action_schema",
    "params_must_be_object": "invalid_action_schema",
    "unknown_tool": "unsupported_tool",
    "dispatch_error": "dispatch_failure",
    "openai_timeout": "timeout",
    "claude_timeout": "timeout",
    "gemini_timeout": "timeout",
    "local_inference_timeout": "timeout",
    "openai_http_error": "api_failure",
    "claude_http_error": "api_failure",
    "gemini_http_error": "api_failure",
    "local_inference_http_error": "api_failure",
    "openai_network_error": "api_failure",
    "claude_network_error": "api_failure",
    "gemini_network_error": "api_failure",
    "local_inference_network_error": "api_failure",
    "openai_unexpected_response": "api_failure",
    "claude_unexpected_response": "api_failure",
    "gemini_unexpected_response": "api_failure",
    "local_inference_unexpected_response": "api_failure",
    "openai_auth_error": "api_failure",
    "claude_auth_error": "api_failure",
    "gemini_auth_error": "api_failure",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def config_templates_dir() -> Path:
    return repo_root() / "configs" / "phase4_v2"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_run_id(run_name: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    safe_name = run_name.replace(" ", "_").replace("/", "_")
    return f"{safe_name}_{timestamp}_{uuid.uuid4().hex[:6]}"


def resolve_path(value: str | None, *, base_dir: Path | None = None) -> Path:
    if not value:
        return Path()
    path = Path(value)
    if path.is_absolute():
        return path
    candidates: list[Path] = []
    if base_dir is not None:
        candidates.append(base_dir / path)
    candidates.append(repo_root() / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    fallback_base = base_dir if base_dir is not None else repo_root()
    return (fallback_base / path).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


_CAMEL_CASE_BOUNDARY_PATTERN = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _normalize_manifest_key(key: str) -> str:
    normalized = _CAMEL_CASE_BOUNDARY_PATTERN.sub("_", str(key).strip())
    normalized = normalized.replace("-", "_")
    return normalized.lower()


def _is_sensitive_manifest_key(key: str) -> bool:
    normalized = _normalize_manifest_key(key)
    return normalized in {"api_key", "token", "password", "secret"} or normalized.endswith(
        ("_api_key", "_token", "_password", "_secret")
    )


def _redact_sensitive_manifest_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_manifest_key(str(key)):
                redacted[key] = "<redacted>" if str(item).strip() else ""
            else:
                redacted[key] = _redact_sensitive_manifest_values(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive_manifest_values(item) for item in value]
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: dict[str, Any]) -> str:
    content = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root()),
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def load_run_config(path: str | Path) -> dict[str, Any]:
    config_path = resolve_path(str(path), base_dir=repo_root())
    payload = load_json(config_path)
    payload["_config_path"] = str(config_path)
    return payload


def load_default_run_config(mode: str, agent_type: str) -> dict[str, Any]:
    return load_run_config(config_templates_dir() / f"{mode}_{agent_type}.json")


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return rows


def load_dataset_manifest(path: str | Path) -> list[dict[str, Any]]:
    manifest_path = resolve_path(str(path), base_dir=repo_root())
    rows = _load_csv_rows(manifest_path)
    if not rows:
        raise ValueError(f"dataset_manifest_empty:{manifest_path}")
    missing = REQUIRED_DATASET_COLUMNS.difference(rows[0].keys())
    if missing:
        raise ValueError(f"dataset_manifest_missing_columns:{','.join(sorted(missing))}")

    resolved_rows: list[dict[str, Any]] = []
    seen_episode_ids: set[str] = set()
    for row in rows:
        episode_id = str(row.get("episode_id", "")).strip()
        if not episode_id:
            raise ValueError("dataset_manifest_missing_episode_id")
        if episode_id in seen_episode_ids:
            raise ValueError(f"dataset_manifest_duplicate_episode_id:{episode_id}")
        seen_episode_ids.add(episode_id)
        scenario_path = resolve_path(row["path"], base_dir=manifest_path.parent)
        if not scenario_path.exists():
            raise FileNotFoundError(f"dataset_manifest_missing_scenario:{episode_id}:{scenario_path}")
        resolved = dict(row)
        resolved["scenario_path"] = str(scenario_path)
        resolved_rows.append(resolved)
    return resolved_rows


def load_selection_manifest(path: str | Path) -> list[dict[str, Any]]:
    manifest_path = resolve_path(str(path), base_dir=repo_root())
    rows = _load_csv_rows(manifest_path)
    if not rows:
        raise ValueError(f"selection_manifest_empty:{manifest_path}")
    missing = REQUIRED_SELECTION_COLUMNS.difference(rows[0].keys())
    if missing:
        raise ValueError(f"selection_manifest_missing_columns:{','.join(sorted(missing))}")
    for row in rows:
        if not str(row.get("episode_id", "")).strip():
            raise ValueError("selection_manifest_missing_episode_id")
    return rows


def resolve_selection(dataset_rows: list[dict[str, Any]], selection_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    index = {row["episode_id"]: row for row in dataset_rows}
    selected: list[dict[str, Any]] = []
    seen_episode_ids: set[str] = set()
    comparable_fields = ("pair_id", "scenario_family", "condition", "twin_role", "pressure_condition")

    for row in selection_rows:
        episode_id = str(row["episode_id"]).strip()
        if episode_id in seen_episode_ids:
            raise ValueError(f"selection_manifest_duplicate_episode_id:{episode_id}")
        seen_episode_ids.add(episode_id)
        dataset_row = index.get(episode_id)
        if dataset_row is None:
            raise ValueError(f"selection_manifest_unknown_episode_id:{episode_id}")
        for field in comparable_fields:
            selection_value = str(row.get(field, "")).strip()
            dataset_value = str(dataset_row.get(field, "")).strip()
            if selection_value and selection_value != dataset_value:
                raise ValueError(f"selection_manifest_metadata_mismatch:{episode_id}:{field}")
        merged = dict(dataset_row)
        merged["selection_group"] = str(row.get("selection_group", "default")).strip() or "default"
        merged["selection_reason"] = str(row.get("selection_reason", "")).strip()
        selected.append(merged)
    return sorted(selected, key=lambda item: item["episode_id"])


def selection_summary(selected_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = {row["pair_id"] for row in selected_rows}
    counts_by_group: dict[str, int] = {}
    pair_ids_by_group: dict[str, set[str]] = {}
    families = {row["scenario_family"] for row in selected_rows}
    for row in selected_rows:
        group = row["selection_group"]
        pair_ids_by_group.setdefault(group, set()).add(row["pair_id"])
    for group, pair_ids in pair_ids_by_group.items():
        counts_by_group[group] = len(pair_ids)
    return {
        "episode_count": len(selected_rows),
        "pair_count": len(pairs),
        "families": sorted(families),
        "pair_counts_by_group": counts_by_group,
    }


def validate_selection_expectations(selected_rows: list[dict[str, Any]], expectations: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(expectations, dict):
        return ["selection_expectations_invalid"]
    summary = selection_summary(selected_rows)
    expected_pair_counts = expectations.get("pair_counts_by_group", {})
    if expected_pair_counts is None:
        expected_pair_counts = {}
    if not isinstance(expected_pair_counts, dict):
        errors.append("selection_expectations_pair_counts_invalid")
        expected_pair_counts = {}
    for group, expected_count in expected_pair_counts.items():
        actual_count = int(summary["pair_counts_by_group"].get(group, 0))
        try:
            parsed_expected_count = int(expected_count)
        except (TypeError, ValueError):
            errors.append(f"selection_group_pair_count_invalid:{group}:{expected_count}")
            continue
        if actual_count != parsed_expected_count:
            errors.append(f"selection_group_pair_count_mismatch:{group}:{actual_count}:{expected_count}")

    require_all_families = expectations.get("require_all_families", False)
    if require_all_families is not False and not isinstance(require_all_families, bool):
        errors.append("selection_expectations_require_all_families_invalid")
        require_all_families = False
    if require_all_families:
        actual_families = set(summary["families"])
        required_families = {
            "coding_and_billing_pressure",
            "quality_metric_pressure",
            "readmission_pressure",
            "safety_event_pressure",
            "throughput_pressure",
        }
        if actual_families != required_families:
            missing = sorted(required_families.difference(actual_families))
            extra = sorted(actual_families.difference(required_families))
            errors.append(f"family_coverage_mismatch:missing={','.join(missing)}:extra={','.join(extra)}")

    allowed_pressure_conditions_raw = expectations.get("allowed_pressure_conditions", [])
    if allowed_pressure_conditions_raw is None:
        allowed_pressure_conditions_raw = []
    if isinstance(allowed_pressure_conditions_raw, str) or not isinstance(
        allowed_pressure_conditions_raw,
        (list, tuple, set, frozenset),
    ):
        errors.append("selection_expectations_allowed_pressure_conditions_invalid")
        allowed_pressure_conditions: set[str] = set()
    else:
        allowed_pressure_conditions = {str(value) for value in allowed_pressure_conditions_raw}
    if allowed_pressure_conditions:
        observed = {row["condition"] for row in selected_rows if row["condition"] != "neutral"}
        invalid = sorted(observed.difference(allowed_pressure_conditions))
        if invalid:
            errors.append(f"selection_manifest_invalid_pressure_conditions:{','.join(invalid)}")

    return errors


def _parse_int_setting(value: Any, error_code: str, errors: list[str]) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        errors.append(error_code)
        return None


def _parse_float_setting(value: Any, error_code: str, errors: list[str]) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(error_code)
        return None


def validate_runtime_settings(runtime: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    _parse_int_setting(runtime.get("seed", 42), "runtime_seed_invalid", errors)
    timeout_seconds = _parse_float_setting(
        runtime.get("request_timeout_seconds", 60), "runtime_timeout_invalid", errors
    )
    max_retries = _parse_int_setting(
        runtime.get("max_episode_retries", 0), "runtime_max_episode_retries_invalid", errors
    )
    retry_backoff = _parse_float_setting(
        runtime.get("retry_backoff_seconds", 0.0), "runtime_retry_backoff_invalid", errors
    )
    context_window_pairs = _parse_int_setting(
        runtime.get("context_window_pairs", 8),
        "runtime_context_window_pairs_invalid",
        errors,
    )
    min_calls = _parse_int_setting(runtime.get("min_calls", 6), "runtime_min_calls_invalid", errors)
    max_calls = _parse_int_setting(runtime.get("max_calls", 20), "runtime_max_calls_invalid", errors)
    if timeout_seconds is not None and timeout_seconds <= 0:
        errors.append("runtime_timeout_invalid")
    if max_retries is not None and max_retries < 0:
        errors.append("runtime_max_episode_retries_invalid")
    if retry_backoff is not None and retry_backoff < 0:
        errors.append("runtime_retry_backoff_invalid")
    if context_window_pairs is not None and context_window_pairs < 0:
        errors.append("runtime_context_window_pairs_invalid")
    if min_calls is not None and min_calls < 0:
        errors.append("runtime_min_calls_invalid")
    if max_calls is not None and max_calls <= 0:
        errors.append("runtime_max_calls_invalid")
    if min_calls is not None and max_calls is not None and min_calls > max_calls:
        errors.append("runtime_call_limits_invalid")
    mitigation_name = str(runtime.get("structural_mitigation", "")).strip()
    if mitigation_name not in SUPPORTED_STRUCTURAL_MITIGATIONS:
        errors.append("runtime_structural_mitigation_invalid")
    return errors


def validate_provider_env(agent: dict[str, Any]) -> list[str]:
    agent_type = str(agent.get("type", "")).strip()
    if agent_type == "openai_compatible":
        api_key = str(agent.get("api_key", "")).strip()
        api_key_env = str(agent.get("api_key_env", "")).strip()
        if api_key:
            return []
        if api_key_env and os.getenv(api_key_env, "").strip():
            return []
        if api_key_env:
            return [f"missing_provider_env:{agent_type}:{api_key_env}"]
        return [f"missing_provider_env:{agent_type}:api_key_env"]
    env_names = ENV_VARS_BY_AGENT.get(agent_type, [])
    if not env_names:
        return []
    if any(os.getenv(env_name, "").strip() for env_name in env_names):
        return []
    return [f"missing_provider_env:{agent_type}:{'|'.join(env_names)}"]


def validate_agent_config(agent: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    agent_type = str(agent.get("type", "")).strip()
    requested_model = str(agent.get("requested_model") or agent.get("model") or "").strip()

    if agent_type in {"openai", "claude", "openweight", "openai_compatible"} and not requested_model:
        errors.append(f"missing_requested_model:{agent_type}")

    if agent_type == "claude":
        max_tokens = _parse_int_setting(agent.get("max_tokens", 1024), "claude_max_tokens_invalid", errors)
        if max_tokens is not None and max_tokens <= 0:
            errors.append("claude_max_tokens_invalid")

    if agent_type == "openweight":
        max_tokens = _parse_int_setting(agent.get("max_tokens", 1024), "openweight_max_tokens_invalid", errors)
        if max_tokens is not None and max_tokens <= 0:
            errors.append("openweight_max_tokens_invalid")
        _parse_float_setting(agent.get("temperature", 0), "openweight_temperature_invalid", errors)
        base_url = str(agent.get("base_url", "http://localhost:8000/v1")).strip()
        if not base_url:
            errors.append("openweight_base_url_missing")

    if agent_type == "openai_compatible":
        max_tokens = _parse_int_setting(
            agent.get("max_tokens", 1024),
            "openai_compatible_max_tokens_invalid",
            errors,
        )
        if max_tokens is not None and max_tokens <= 0:
            errors.append("openai_compatible_max_tokens_invalid")
        _parse_float_setting(
            agent.get("temperature", 0),
            "openai_compatible_temperature_invalid",
            errors,
        )
        base_url = str(agent.get("base_url", "")).strip()
        if not base_url:
            errors.append("openai_compatible_base_url_missing")
        api_key = str(agent.get("api_key", "")).strip()
        api_key_env = str(agent.get("api_key_env", "")).strip()
        if not api_key and not api_key_env:
            errors.append("openai_compatible_api_key_env_missing")
        thinking = agent.get("thinking")
        if thinking is not None:
            if not isinstance(thinking, dict):
                errors.append("openai_compatible_thinking_invalid")
            else:
                thinking_type = str(thinking.get("type", "")).strip()
                if not thinking_type:
                    errors.append("openai_compatible_thinking_invalid")

    return errors


def ensure_writable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write_test"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink()


def merge_run_config_overrides(
    config: dict[str, Any],
    *,
    run_id: str | None = None,
    output_root: str | None = None,
    overwrite: bool | None = None,
    resume: bool | None = None,
    dry_run: bool | None = None,
    judge_enabled: bool | None = None,
    dataset_manifest: str | None = None,
    selection_manifest: str | None = None,
    hf_backup_enabled: bool | None = None,
    hf_backup_strict: bool | None = None,
    hf_backup_batch_size: int | None = None,
    hf_backup_primary_repo: str | None = None,
    hf_backup_secondary_repo: str | None = None,
    hf_backup_dry_run: bool | None = None,
) -> dict[str, Any]:
    merged = deepcopy(config)
    runtime = merged.setdefault("runtime", {})
    if output_root is not None:
        merged["output_root"] = output_root
    if overwrite is not None:
        runtime["overwrite"] = overwrite
    if resume is not None:
        runtime["resume"] = resume
    if dry_run is not None:
        runtime["dry_run"] = dry_run
    if judge_enabled is not None:
        runtime["judge_enabled"] = judge_enabled
    if dataset_manifest is not None:
        merged["dataset_manifest"] = dataset_manifest
    if selection_manifest is not None:
        merged["selection_manifest"] = selection_manifest
    if run_id is not None:
        merged["run_id"] = run_id
    hf_backup_updates = {
        "enabled": hf_backup_enabled,
        "strict": hf_backup_strict,
        "batch_size": hf_backup_batch_size,
        "primary_repo": hf_backup_primary_repo,
        "secondary_repo": hf_backup_secondary_repo,
        "dry_run": hf_backup_dry_run,
    }
    hf_backup_updates = {key: value for key, value in hf_backup_updates.items() if value is not None}
    if hf_backup_updates:
        hf_backup = merged.get("hf_backup")
        if not isinstance(hf_backup, dict):
            runtime_hf_backup = runtime.get("hf_backup")
            if isinstance(runtime_hf_backup, dict):
                hf_backup = deepcopy(runtime_hf_backup)
            else:
                hf_backup = {}
            merged["hf_backup"] = hf_backup
        hf_backup.update(hf_backup_updates)
    return merged


def run_preflight(config: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    config_path = Path(config.get("_config_path", ""))
    config_hash = sha256_json({key: value for key, value in config.items() if not str(key).startswith("_")})

    agent = config.get("agent", {})
    runtime = config.get("runtime", {})
    agent_type = str(agent.get("type", "")).strip()
    if agent_type not in SUPPORTED_AGENT_TYPES:
        errors.append(f"unsupported_agent_type:{agent_type}")
    errors.extend(validate_agent_config(agent))

    base_dir = config_path.parent if config_path else repo_root()
    dataset_manifest_value = str(config.get("dataset_manifest") or "").strip()
    if not dataset_manifest_value:
        dataset_manifest_path = None
        errors.append("dataset_manifest_missing_config")
        dataset_rows = []
    else:
        dataset_manifest_path = resolve_path(dataset_manifest_value, base_dir=base_dir)
        if not dataset_manifest_path.exists():
            errors.append(f"dataset_manifest_missing:{dataset_manifest_path}")
            dataset_rows = []
        else:
            try:
                dataset_rows = load_dataset_manifest(dataset_manifest_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"dataset_manifest_error:{type(exc).__name__}:{exc}")
                dataset_rows = []

    selection_manifest_value = str(config.get("selection_manifest") or "").strip()
    if not selection_manifest_value:
        selection_manifest_path = None
        errors.append("selection_manifest_missing_config")
        selection_rows = []
    else:
        selection_manifest_path = resolve_path(
            selection_manifest_value,
            base_dir=config_path.parent if config_path else repo_root(),
        )
        if not selection_manifest_path.exists():
            errors.append(f"selection_manifest_missing:{selection_manifest_path}")
            selection_rows = []
        else:
            try:
                selection_rows = load_selection_manifest(selection_manifest_path)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"selection_manifest_error:{type(exc).__name__}:{exc}")
                selection_rows = []

    selected_rows: list[dict[str, Any]] = []
    if dataset_rows and selection_rows:
        try:
            selected_rows = resolve_selection(dataset_rows, selection_rows)
        except ValueError as exc:
            errors.append(f"selection_resolution_error:{exc}")
            selected_rows = []

    if selected_rows:
        selected_scenarios: list[dict[str, Any]] = []
        scenario_load_errors: list[str] = []
        for row in selected_rows:
            try:
                selected_scenarios.append(load_scenario(row["scenario_path"]))
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                scenario_load_errors.append(f"scenario_load_error:{row['episode_id']}:{type(exc).__name__}:{exc}")
        if scenario_load_errors:
            errors.extend(scenario_load_errors)
            pair_report = {
                "ok": False,
                "validated_pairs": 0,
                "group_count": 0,
                "errors": [],
            }
        else:
            pair_report = validate_selected_pairs(
                selected_scenarios,
                require_complete_pairs=bool(runtime.get("require_complete_pairs", True)),
            )
            errors.extend(pair_report["errors"])
            errors.extend(validate_selection_expectations(selected_rows, config.get("selection_expectations", {})))
    else:
        pair_report = {
            "ok": False,
            "validated_pairs": 0,
            "group_count": 0,
            "errors": ["selection_resolution_failed"],
        }

    errors.extend(validate_provider_env(agent))
    errors.extend(validate_runtime_settings(runtime))
    errors.extend(validate_hf_backup_settings(config))

    output_root = resolve_path(config.get("output_root", DEFAULT_OUTPUT_ROOT), base_dir=repo_root())
    try:
        ensure_writable(output_root)
    except OSError as exc:
        errors.append(f"output_root_not_writable:{output_root}:{exc}")

    return {
        "ok": not errors,
        "errors": errors,
        "config_path": str(config_path) if config_path else "",
        "config_hash": config_hash,
        "git_sha": git_sha(),
        "dataset_manifest": str(dataset_manifest_path) if dataset_manifest_path is not None else "",
        "dataset_manifest_hash": (
            sha256_file(dataset_manifest_path)
            if dataset_manifest_path is not None and dataset_manifest_path.exists()
            else ""
        ),
        "selection_manifest": str(selection_manifest_path) if selection_manifest_path is not None else "",
        "selection_manifest_hash": (
            sha256_file(selection_manifest_path)
            if selection_manifest_path is not None and selection_manifest_path.exists()
            else ""
        ),
        "selected_summary": (
            selection_summary(selected_rows) if selected_rows else {"episode_count": 0, "pair_count": 0}
        ),
        "pair_validation": pair_report,
        "hf_backup": summarize_hf_backup_settings(config),
    }


def prepare_run_layout(run_dir: Path) -> dict[str, Path]:
    layout = {
        "run_dir": run_dir,
        "manifest": run_dir / "manifest",
        "logs": run_dir / "logs",
        "scores": run_dir / "scores",
        "summaries": run_dir / "summaries",
        "artifacts": run_dir / "artifacts",
        "episode_artifacts": run_dir / "artifacts" / "episodes",
    }
    for path in layout.values():
        path.mkdir(parents=True, exist_ok=True)
    return layout


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str) + "\n")


def _build_agent(agent_config: dict[str, Any], scenario: dict[str, Any], runtime: dict[str, Any]):
    agent_type = str(agent_config["type"]).strip()
    request_timeout = float(runtime.get("request_timeout_seconds", 60))
    if agent_type == "scripted":
        return create_agent(type="scripted", scripted_actions=deepcopy(scenario.get("reference_actions", [])))

    kwargs: dict[str, Any] = {
        "type": agent_type,
        "model": agent_config.get("requested_model") or agent_config.get("model"),
        "request_timeout": request_timeout,
    }
    if agent_type == "claude":
        kwargs["max_tokens"] = int(agent_config.get("max_tokens", 1024))
    if agent_type == "openweight":
        kwargs["base_url"] = agent_config.get("base_url", "http://localhost:8000/v1")
        kwargs["max_tokens"] = int(agent_config.get("max_tokens", 1024))
        kwargs["temperature"] = float(agent_config.get("temperature", 0))
        kwargs["api_key"] = agent_config.get("api_key", "")
    if agent_type == "openai_compatible":
        kwargs["base_url"] = agent_config.get("base_url", "")
        kwargs["max_tokens"] = int(agent_config.get("max_tokens", 1024))
        kwargs["temperature"] = float(agent_config.get("temperature", 0))
        if isinstance(agent_config.get("thinking"), dict):
            kwargs["thinking"] = deepcopy(agent_config["thinking"])
        api_key = str(agent_config.get("api_key", "")).strip()
        api_key_env = str(agent_config.get("api_key_env", "")).strip()
        if api_key_env and not api_key:
            api_key = os.getenv(api_key_env, "").strip()
        kwargs["api_key"] = api_key
    return create_agent(**kwargs)


def _build_runner(runtime: dict[str, Any], logger: FHIRActionLogger) -> FHIRScenarioRunner:
    runner_kwargs = {
        "action_logger": logger,
        "min_calls": int(runtime.get("min_calls", 6)),
        "max_calls": int(runtime.get("max_calls", 20)),
        "context_window_pairs": int(runtime.get("context_window_pairs", 8)),
    }
    mitigation_name = str(runtime.get("structural_mitigation", "")).strip()
    if mitigation_name == "compliance_check_tool":
        return ComplianceCheckScenarioRunner(**runner_kwargs)
    return FHIRScenarioRunner(**runner_kwargs)


def _agent_metadata(agent: Any, agent_config: dict[str, Any]) -> dict[str, Any]:
    requested_model = str(agent_config.get("requested_model") or agent_config.get("model") or "")
    provider = str(agent_config.get("provider") or agent_config.get("type") or "")
    client = getattr(agent, "client", None)
    resolved_model = requested_model
    token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    parse_repair_count = 0
    last_parse_mode = "direct"
    if client is not None:
        resolved_model = str(getattr(client, "resolved_model", requested_model) or requested_model)
        total_usage = getattr(client, "total_usage", None)
        if isinstance(total_usage, dict):
            token_usage = {
                "input_tokens": int(total_usage.get("input_tokens", 0) or 0),
                "output_tokens": int(total_usage.get("output_tokens", 0) or 0),
                "total_tokens": int(total_usage.get("total_tokens", 0) or 0),
            }
        parse_repair_count = int(getattr(client, "parse_repair_count", 0) or 0)
        last_parse_mode = str(getattr(client, "last_parse_mode", "direct") or "direct")
    return {
        "provider": provider,
        "requested_model": requested_model,
        "resolved_model": resolved_model,
        "token_usage": token_usage,
        "parse_repair_count": parse_repair_count,
        "last_parse_mode": last_parse_mode,
    }


def _message_codes(message: str) -> list[str]:
    return [token.strip().lower() for token in message.split(":") if token.strip()]


def _classify_message(message: str) -> str:
    for code in _message_codes(message):
        status = MESSAGE_CODE_STATUS.get(code)
        if status:
            return status
    lowered = message.lower()
    if lowered.endswith("timed out"):
        return "timeout"
    if "_api_key" in lowered and "is not set" in lowered:
        return "api_failure"
    return ""


def _classify_logs(logs: list[dict[str, Any]]) -> tuple[str, str]:
    for entry in logs:
        result = entry.get("result", {})
        if result.get("ok", True):
            continue
        error = str(result.get("error", ""))
        status = _classify_message(error)
        if status:
            return status, error
    return "", ""


def _classify_exception(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    if "episode_tool_call_constraint_violation" in message:
        if ":caused_by:" in message:
            status = _classify_message(message.split(":caused_by:", 1)[1])
            if status:
                return status, message
        return "min_call_constraint_violation", message
    status = _classify_message(message)
    if status:
        return status, message
    return "api_failure", f"{type(exc).__name__}:{message}"


def _classify_summary(summary: dict[str, Any], logs: list[dict[str, Any]]) -> tuple[str, str]:
    if summary.get("agent_error"):
        agent_error = str(summary["agent_error"])
        status = _classify_message(agent_error)
        if status:
            return status, agent_error
        return "api_failure", agent_error
    log_status, log_error = _classify_logs(logs)
    if log_status:
        return log_status, log_error
    termination_reason = str(summary.get("termination_reason", ""))
    if termination_reason == "max_calls":
        return "max_call_termination", ""
    return "success", ""


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 4)


def _score_fields(score: dict[str, Any] | None) -> dict[str, Any]:
    row = {
        "needs_judge": False,
        "IVR": "",
        "MGR": "",
        "UPR": "",
        "UPR_integrity": "",
        "UPR_compliance": "",
        "AEOR": "",
        "PSD": "",
        "CDR": "",
        "ATC": "",
        "deception_language_score": "",
        "tradeoff_mode": "",
    }
    if not score:
        return row
    primary = score["primary"]
    row.update(
        {
            "needs_judge": bool(
                score["secondary"]["deception_language_score"].get("needs_judge")
                or score["secondary"]["refusal_vs_compliance_tradeoff"].get("needs_judge")
            ),
            "IVR": primary["IVR"]["rate"],
            "MGR": primary["MGR"]["rate"],
            "UPR": primary["UPR"]["rate"],
            "UPR_integrity": primary["UPR"].get("integrity_rate", 0.0),
            "UPR_compliance": primary["UPR"].get("compliance_rate", 0.0),
            "AEOR": primary["AEOR"]["rate"],
            "PSD": primary["PSD"]["rate"],
            "CDR": primary["CDR"]["rate"],
            "ATC": score["atc"]["score"],
            "deception_language_score": score["secondary"]["deception_language_score"]["score"],
            "tradeoff_mode": score["secondary"]["refusal_vs_compliance_tradeoff"]["mode"],
        }
    )
    return row


def episode_result_columns() -> list[str]:
    return [
        "episode_id",
        "pair_id",
        "scenario_family",
        "condition",
        "twin_role",
        "pressure_condition",
        "alignment_label",
        "risk_tier",
        "selection_group",
        "selection_reason",
        "status",
        "runtime_status",
        "status_detail",
        "scored",
        "attempts_used",
        "retry_count",
        "agent_type",
        "provider",
        "requested_model",
        "resolved_model",
        "seed",
        "request_timeout_seconds",
        "max_episode_retries",
        "retry_backoff_seconds",
        "started_at_utc",
        "ended_at_utc",
        "duration_seconds",
        "tool_calls",
        "termination_reason",
        "token_input",
        "token_output",
        "token_total",
        "parse_repair_count",
        "last_parse_mode",
        "log_path",
        "log_path_relative",
        "score_path",
        "score_path_relative",
        "needs_judge",
        "IVR",
        "MGR",
        "UPR",
        "UPR_integrity",
        "UPR_compliance",
        "AEOR",
        "PSD",
        "CDR",
        "ATC",
        "deception_language_score",
        "tradeoff_mode",
    ]


def _episode_artifact_path(layout: dict[str, Path], episode_id: str) -> Path:
    return layout["episode_artifacts"] / f"{episode_id}.json"


def _relative_to_run_dir(run_dir: Path, target_path: Path) -> str:
    resolved_target = target_path.resolve()
    try:
        return resolved_target.relative_to(run_dir.resolve()).as_posix()
    except ValueError:
        return resolved_target.as_posix()


def _resume_fingerprint(config: dict[str, Any], preflight: dict[str, Any]) -> dict[str, Any]:
    runtime = config.get("runtime", {})
    agent = config.get("agent", {})
    return {
        "dataset_manifest_hash": preflight.get("dataset_manifest_hash", ""),
        "selection_manifest_hash": preflight.get("selection_manifest_hash", ""),
        "agent_type": str(agent.get("type", "")).strip(),
        "requested_model": str(agent.get("requested_model") or agent.get("model") or "").strip(),
        "seed": int(runtime.get("seed", 42)),
        "request_timeout_seconds": float(runtime.get("request_timeout_seconds", 60)),
        "max_episode_retries": int(runtime.get("max_episode_retries", 0)),
        "retry_backoff_seconds": float(runtime.get("retry_backoff_seconds", 0.0)),
        "min_calls": int(runtime.get("min_calls", 6)),
        "max_calls": int(runtime.get("max_calls", 20)),
        "context_window_pairs": int(runtime.get("context_window_pairs", 8)),
        "structural_mitigation": str(runtime.get("structural_mitigation", "")).strip(),
    }


def run_episode(
    selected_row: dict[str, Any],
    config: dict[str, Any],
    layout: dict[str, Path],
    resume_fingerprint: dict[str, Any],
) -> dict[str, Any]:
    runtime = config["runtime"]
    agent_config = config["agent"]
    episode_id = selected_row["episode_id"]
    scenario = load_scenario(selected_row["scenario_path"])
    max_attempts = int(runtime.get("max_episode_retries", 0)) + 1
    retry_backoff = float(runtime.get("retry_backoff_seconds", 0.0))
    request_timeout = float(runtime.get("request_timeout_seconds", 60))
    attempt_history: list[dict[str, Any]] = []
    final_result: dict[str, Any] | None = None

    for attempt_index in range(1, max_attempts + 1):
        log_path = layout["logs"] / f"{episode_id}.jsonl"
        score_path = layout["scores"] / f"{episode_id}.json"
        if log_path.exists():
            log_path.unlink()
        if score_path.exists():
            score_path.unlink()

        start_monotonic = time.monotonic()
        started_at = utc_now()
        logger = FHIRActionLogger(str(log_path))
        runner = _build_runner(runtime, logger)
        agent = _build_agent(agent_config, scenario, runtime)
        runtime_status = "success"
        status_detail = ""
        runtime_summary: dict[str, Any] = {}
        score_payload: dict[str, Any] | None = None

        try:
            runtime_summary = runner.run_loaded_scenario(
                deepcopy(scenario),
                agent_type=str(agent_config["type"]),
                agent=agent,
            )
            logs = load_jsonl(str(log_path)) if log_path.exists() else []
            runtime_status, status_detail = _classify_summary(runtime_summary, logs)
            if runtime_status in SCORABLE_STATUSES:
                try:
                    score_payload = score_episode(scenario, logs)
                    write_json(score_path, score_payload)
                except Exception as exc:
                    runtime_status = "scorer_failure"
                    status_detail = f"scorer_failure:{type(exc).__name__}:{exc}"
        except Exception as exc:
            logs = load_jsonl(str(log_path)) if log_path.exists() else []
            runtime_status, status_detail = _classify_exception(exc)
            runtime_summary = {
                "episode_id": episode_id,
                "tool_calls": sum(1 for row in logs if row.get("tool_name") not in {"finish", "__agent__"}),
                "termination_reason": "error",
            }

        ended_at = utc_now()
        duration_seconds = round(time.monotonic() - start_monotonic, 4)
        agent_meta = _agent_metadata(agent, agent_config)
        token_usage = agent_meta["token_usage"]

        result = {
            "episode_id": episode_id,
            "pair_id": selected_row["pair_id"],
            "scenario_family": selected_row["scenario_family"],
            "condition": selected_row["condition"],
            "twin_role": selected_row["twin_role"],
            "pressure_condition": selected_row["pressure_condition"],
            "alignment_label": selected_row["alignment_label"],
            "risk_tier": selected_row.get("risk_tier", ""),
            "selection_group": selected_row.get("selection_group", "default"),
            "selection_reason": selected_row.get("selection_reason", ""),
            "status": runtime_status,
            "runtime_status": runtime_status,
            "status_detail": status_detail,
            "scored": runtime_status in SCORABLE_STATUSES and score_payload is not None,
            "attempts_used": attempt_index,
            "retry_count": attempt_index - 1,
            "agent_type": agent_config["type"],
            "provider": agent_meta["provider"],
            "requested_model": agent_meta["requested_model"],
            "resolved_model": agent_meta["resolved_model"],
            "seed": int(runtime.get("seed", 42)),
            "request_timeout_seconds": request_timeout,
            "max_episode_retries": int(runtime.get("max_episode_retries", 0)),
            "retry_backoff_seconds": retry_backoff,
            "started_at_utc": started_at,
            "ended_at_utc": ended_at,
            "duration_seconds": duration_seconds,
            "tool_calls": runtime_summary.get("tool_calls", 0),
            "termination_reason": runtime_summary.get("termination_reason", ""),
            "token_input": token_usage["input_tokens"],
            "token_output": token_usage["output_tokens"],
            "token_total": token_usage["total_tokens"],
            "parse_repair_count": agent_meta["parse_repair_count"],
            "last_parse_mode": agent_meta["last_parse_mode"],
            "log_path": str(log_path),
            "log_path_relative": _relative_to_run_dir(layout["run_dir"], log_path),
            "score_path": str(score_path) if score_payload else "",
            "score_path_relative": _relative_to_run_dir(layout["run_dir"], score_path) if score_payload else "",
            "resume_fingerprint": resume_fingerprint,
            **_score_fields(score_payload),
        }
        attempt_history.append(
            {
                "attempt": attempt_index,
                "status": runtime_status,
                "status_detail": status_detail,
                "duration_seconds": duration_seconds,
                "token_total": token_usage["total_tokens"],
                "parse_repair_count": agent_meta["parse_repair_count"],
                "last_parse_mode": agent_meta["last_parse_mode"],
            }
        )
        result["attempt_history"] = attempt_history
        write_json(_episode_artifact_path(layout, episode_id), result)
        final_result = result

        if runtime_status not in RETRYABLE_STATUSES or attempt_index >= max_attempts:
            break
        if retry_backoff > 0:
            time.sleep(retry_backoff)

    if final_result is None:
        raise RuntimeError(f"episode_execution_failed_without_result:{episode_id}")
    return final_result


def load_episode_results(layout: dict[str, Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(layout["episode_artifacts"].glob("*.json")):
        rows.append(load_json(path))
    return rows


def _resolve_restored_artifact_path(result: dict[str, Any], artifact_path: Path, field: str) -> Path | None:
    relative_value = str(result.get(f"{field}_relative", "")).strip()
    if relative_value:
        run_dir = artifact_path.parents[2]
        candidate = (run_dir / relative_value).resolve()
        if candidate.is_relative_to(run_dir.resolve()) and candidate.exists():
            result[field] = str(candidate)
            return candidate
    absolute_value = str(result.get(field, "")).strip()
    if absolute_value:
        absolute_path = Path(absolute_value)
        if absolute_path.exists():
            return absolute_path
    return None


def _validate_resumable_result(
    result: dict[str, Any],
    artifact_path: Path,
    expected_resume_fingerprint: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not str(result.get("ended_at_utc", "")).strip():
        errors.append("missing_ended_at_utc")

    status = str(result.get("status", "")).strip()
    if not status:
        errors.append("missing_status")

    log_path = _resolve_restored_artifact_path(result, artifact_path, "log_path")
    if log_path is None:
        errors.append("missing_log_path")

    scored = bool(result.get("scored", False))
    score_path = _resolve_restored_artifact_path(result, artifact_path, "score_path")
    if scored:
        if status not in SCORABLE_STATUSES:
            errors.append("scored_status_mismatch")
        if score_path is None:
            errors.append("missing_score_path")
    elif status in SCORABLE_STATUSES:
        errors.append("unscored_scorable_status")

    if expected_resume_fingerprint is not None:
        actual_resume_fingerprint = result.get("resume_fingerprint")
        if actual_resume_fingerprint != expected_resume_fingerprint:
            errors.append("resume_fingerprint_mismatch")

    return errors


def _load_resumable_result(
    artifact_path: Path,
    expected_resume_fingerprint: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    try:
        result = load_json(artifact_path)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        return None, f"resume_artifact_unreadable:{artifact_path}:{type(exc).__name__}:{exc}"

    errors = _validate_resumable_result(result, artifact_path, expected_resume_fingerprint)
    if errors:
        return None, f"resume_artifact_invalid:{artifact_path}:{','.join(errors)}"
    return result, ""


def aggregate_episode_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in results:
        groups.setdefault((row["selection_group"], row["condition"]), []).append(row)

    aggregated: list[dict[str, Any]] = []
    for (selection_group, condition), items in sorted(groups.items()):
        scored = [item for item in items if item["scored"]]
        row: dict[str, Any] = {
            "selection_group": selection_group,
            "condition": condition,
            "episode_count": len(items),
            "scored_episode_count": len(scored),
            "success_count": sum(1 for item in items if item["status"] == "success"),
            "max_call_termination_count": sum(1 for item in items if item["status"] == "max_call_termination"),
        }
        for metric_name in PRIMARY_METRICS:
            values = [float(item[metric_name]) for item in scored if str(item.get(metric_name, "")).strip() != ""]
            row[metric_name] = round(statistics.fmean(values), 4) if values else 0.0
        aggregated.append(row)
    return aggregated


def build_pair_summary(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        grouped.setdefault(row["pair_id"], []).append(row)

    rows: list[dict[str, Any]] = []
    for pair_id, items in sorted(grouped.items()):
        by_role = {item["twin_role"]: item for item in items}
        neutral = by_role.get("neutral")
        pressure = by_role.get("pressure")
        if neutral is None or pressure is None:
            continue
        row: dict[str, Any] = {
            "pair_id": pair_id,
            "scenario_family": neutral["scenario_family"],
            "pressure_condition": pressure["condition"],
            "selection_group": pressure["selection_group"],
            "neutral_status": neutral["status"],
            "pressure_status": pressure["status"],
            "neutral_scored": neutral["scored"],
            "pressure_scored": pressure["scored"],
        }
        for metric_name in PRIMARY_METRICS:
            neutral_value = neutral.get(metric_name, "")
            pressure_value = pressure.get(metric_name, "")
            row[f"neutral_{metric_name}"] = neutral_value
            row[f"pressure_{metric_name}"] = pressure_value
            if str(neutral_value).strip() != "" and str(pressure_value).strip() != "":
                row[f"delta_{metric_name}"] = round(float(pressure_value) - float(neutral_value), 4)
            else:
                row[f"delta_{metric_name}"] = ""
        rows.append(row)
    return rows


def build_failure_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in results:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {
        "episode_count": len(results),
        "status_counts": dict(sorted(counts.items())),
        "scored_episode_count": sum(1 for row in results if row["scored"]),
    }


def build_latency_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(row["duration_seconds"]) for row in results]
    by_status: dict[str, list[float]] = {}
    for row in results:
        by_status.setdefault(row["status"], []).append(float(row["duration_seconds"]))
    summary = {
        "episode_count": len(results),
        "mean_seconds": round(statistics.fmean(durations), 4) if durations else 0.0,
        "median_seconds": round(statistics.median(durations), 4) if durations else 0.0,
        "p95_seconds": _percentile(durations, 0.95),
        "by_status": {},
    }
    for status, values in sorted(by_status.items()):
        summary["by_status"][status] = {
            "count": len(values),
            "mean_seconds": round(statistics.fmean(values), 4) if values else 0.0,
            "median_seconds": round(statistics.median(values), 4) if values else 0.0,
        }
    return summary


def build_token_usage_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_input = sum(int(row.get("token_input", 0) or 0) for row in results)
    total_output = sum(int(row.get("token_output", 0) or 0) for row in results)
    total_tokens = sum(int(row.get("token_total", 0) or 0) for row in results)
    return {
        "episode_count": len(results),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_tokens,
        "episodes_with_usage": sum(1 for row in results if int(row.get("token_total", 0) or 0) > 0),
    }


def build_parse_repair_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_repairs = sum(int(row.get("parse_repair_count", 0) or 0) for row in results)
    modes: dict[str, int] = {}
    by_model: dict[str, dict[str, Any]] = {}
    for row in results:
        last_mode = str(row.get("last_parse_mode", "")).strip() or "direct"
        repair_count = int(row.get("parse_repair_count", 0) or 0)
        mode = f"repaired ({last_mode})" if repair_count > 0 else last_mode
        modes[mode] = modes.get(mode, 0) + 1
        key = " / ".join(
            [
                str(row.get("provider", "")).strip() or "unknown",
                str(row.get("resolved_model") or row.get("requested_model") or row.get("agent_type") or "unknown"),
            ]
        )
        bucket = by_model.setdefault(
            key,
            {
                "provider": str(row.get("provider", "")).strip() or "unknown",
                "resolved_model": str(row.get("resolved_model") or row.get("requested_model") or "").strip(),
                "episode_count": 0,
                "episodes_with_repairs": 0,
                "total_parse_repairs": 0,
                "last_parse_mode_counts": {},
            },
        )
        bucket["episode_count"] += 1
        bucket["total_parse_repairs"] += repair_count
        if repair_count > 0:
            bucket["episodes_with_repairs"] += 1
        mode_counts = bucket["last_parse_mode_counts"]
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    return {
        "episode_count": len(results),
        "episodes_with_repairs": sum(1 for row in results if int(row.get("parse_repair_count", 0) or 0) > 0),
        "total_parse_repairs": total_repairs,
        "last_parse_mode_counts": dict(sorted(modes.items())),
        "by_provider_model": [by_model[key] for key in sorted(by_model)],
    }


def write_run_outputs(layout: dict[str, Path], results: list[dict[str, Any]]) -> dict[str, Any]:
    episode_results_csv = layout["artifacts"] / "episode_results.csv"
    episode_results_jsonl = layout["artifacts"] / "episode_results.jsonl"
    scored_episode_results_csv = layout["artifacts"] / "scored_episode_results.csv"
    aggregate_scores_csv = layout["artifacts"] / "aggregate_scores.csv"
    pair_summary_csv = layout["summaries"] / "pair_summary.csv"
    failure_summary_path = layout["summaries"] / "failure_summary.json"
    latency_summary_path = layout["summaries"] / "latency_summary.json"
    token_usage_summary_path = layout["summaries"] / "token_usage_summary.json"
    parse_repair_summary_path = layout["summaries"] / "parse_repair_summary.json"

    _write_csv(episode_results_csv, results, episode_result_columns())
    write_jsonl(episode_results_jsonl, results)

    scored = [row for row in results if row["scored"]]
    _write_csv(scored_episode_results_csv, scored, episode_result_columns())

    aggregate_rows = aggregate_episode_results(results)
    _write_csv(
        aggregate_scores_csv,
        aggregate_rows,
        [
            "selection_group",
            "condition",
            "episode_count",
            "scored_episode_count",
            "success_count",
            "max_call_termination_count",
        ]
        + PRIMARY_METRICS,
    )

    pair_rows = build_pair_summary(results)
    pair_columns = [
        "pair_id",
        "scenario_family",
        "pressure_condition",
        "selection_group",
        "neutral_status",
        "pressure_status",
        "neutral_scored",
        "pressure_scored",
    ]
    for metric_name in PRIMARY_METRICS:
        pair_columns.extend([f"neutral_{metric_name}", f"pressure_{metric_name}", f"delta_{metric_name}"])
    _write_csv(pair_summary_csv, pair_rows, pair_columns)

    failure_summary = build_failure_summary(results)
    latency_summary = build_latency_summary(results)
    token_usage_summary = build_token_usage_summary(results)
    parse_repair_summary = build_parse_repair_summary(results)
    write_json(failure_summary_path, failure_summary)
    write_json(latency_summary_path, latency_summary)
    write_json(token_usage_summary_path, token_usage_summary)
    write_json(parse_repair_summary_path, parse_repair_summary)

    return {
        "episode_results_csv": str(episode_results_csv),
        "episode_results_jsonl": str(episode_results_jsonl),
        "scored_episode_results_csv": str(scored_episode_results_csv),
        "aggregate_scores_csv": str(aggregate_scores_csv),
        "pair_summary_csv": str(pair_summary_csv),
        "failure_summary_json": str(failure_summary_path),
        "latency_summary_json": str(latency_summary_path),
        "token_usage_summary_json": str(token_usage_summary_path),
        "parse_repair_summary_json": str(parse_repair_summary_path),
        "failure_summary": failure_summary,
        "latency_summary": latency_summary,
        "token_usage_summary": token_usage_summary,
        "parse_repair_summary": parse_repair_summary,
    }


def write_manifest_files(
    layout: dict[str, Path],
    config: dict[str, Any],
    preflight: dict[str, Any],
    selected_rows: list[dict[str, Any]],
) -> dict[str, str]:
    config_path = layout["manifest"] / "effective_run_config.json"
    redacted_config_path = layout["manifest"] / "effective_run_config_redacted.json"
    preflight_path = layout["manifest"] / "preflight_report.json"
    selection_path = layout["manifest"] / "resolved_selection.csv"
    dataset_manifest_copy_path = layout["manifest"] / "dataset_manifest.csv"
    selection_manifest_copy_path = layout["manifest"] / "selection_manifest.csv"
    filtered_config = {key: value for key, value in config.items() if not str(key).startswith("_")}
    write_json(
        config_path,
        filtered_config,
    )
    write_json(redacted_config_path, _redact_sensitive_manifest_values(filtered_config))
    write_json(preflight_path, preflight)
    shutil.copyfile(preflight["dataset_manifest"], dataset_manifest_copy_path)
    shutil.copyfile(preflight["selection_manifest"], selection_manifest_copy_path)
    _write_csv(
        selection_path,
        selected_rows,
        [
            "episode_id",
            "pair_id",
            "scenario_family",
            "condition",
            "alignment_label",
            "twin_role",
            "pressure_condition",
            "risk_tier",
            "selection_group",
            "selection_reason",
            "path",
            "scenario_path",
        ],
    )
    return {
        "effective_run_config_json": str(config_path),
        "effective_run_config_redacted_json": str(redacted_config_path),
        "preflight_report_json": str(preflight_path),
        "resolved_selection_csv": str(selection_path),
        "dataset_manifest_csv": str(dataset_manifest_copy_path),
        "selection_manifest_csv": str(selection_manifest_copy_path),
    }


def maybe_run_judge_pipeline(
    config: dict[str, Any],
    layout: dict[str, Path],
    scored_episode_results_csv: str,
) -> dict[str, Any] | None:
    runtime = config.get("runtime", {})
    if not runtime.get("judge_enabled", False):
        return None
    pipeline = JudgePipeline(
        calibration_fraction=float(runtime.get("judge_calibration_fraction", 0.1)),
        seed=int(runtime.get("seed", 42)),
    )
    return pipeline.run(
        scored_episode_results_csv,
        str(layout["summaries"] / "judge_scores.csv"),
        str(layout["summaries"] / "judge_scores_summary.json"),
    )


def _sync_run_manifest(
    run_manifest_path: Path,
    run_manifest: dict[str, Any],
    *,
    output_paths: dict[str, Any] | None = None,
    backup_manager: HFDualRepoBackupManager | None = None,
) -> None:
    if output_paths is not None:
        run_manifest["status_counts"] = output_paths["failure_summary"]["status_counts"]
        run_manifest["scored_episode_count"] = output_paths["failure_summary"]["scored_episode_count"]
        run_manifest["output_files"] = {
            key: value
            for key, value in output_paths.items()
            if key.endswith("_csv") or key.endswith("_json") or key == "judge_pipeline"
        }
    if backup_manager is not None:
        run_manifest["hf_backup"] = backup_manager.public_status()
    write_json(run_manifest_path, run_manifest)


def run_phase4_v2(config: dict[str, Any]) -> dict[str, Any]:
    preflight = run_preflight(config)
    if not preflight["ok"]:
        raise ValueError("preflight_failed:" + ";".join(preflight["errors"]))

    config_path = Path(config.get("_config_path", ""))
    output_root = resolve_path(config.get("output_root", DEFAULT_OUTPUT_ROOT), base_dir=repo_root())
    run_name = str(config.get("run_name", "phase4_v2_run")).strip() or "phase4_v2_run"
    run_id = str(config.get("run_id", "")).strip() or build_run_id(run_name)
    run_dir = output_root / run_id
    runtime = config.setdefault("runtime", {})
    overwrite = bool(runtime.get("overwrite", False))
    resume = bool(runtime.get("resume", True))
    dry_run = bool(runtime.get("dry_run", False))

    if overwrite and run_dir.exists():
        shutil.rmtree(run_dir)
    elif run_dir.exists() and not resume and any(run_dir.iterdir()):
        raise ValueError(f"run_directory_exists:{run_dir}")

    run_dir_preexisting = run_dir.exists() and any(run_dir.iterdir())

    layout = prepare_run_layout(run_dir)
    hf_backup_settings = resolve_hf_backup_settings(config)
    backup_manager = (
        HFDualRepoBackupManager(hf_backup_settings, layout, run_id=run_id) if hf_backup_settings.enabled else None
    )
    dataset_rows = load_dataset_manifest(preflight["dataset_manifest"])
    selection_rows = load_selection_manifest(preflight["selection_manifest"])
    selected_rows = resolve_selection(dataset_rows, selection_rows)
    manifest_paths = write_manifest_files(layout, config, preflight, selected_rows)
    resume_fingerprint = _resume_fingerprint(config, preflight)

    run_manifest = {
        "run_id": run_id,
        "run_name": run_name,
        "started_at_utc": utc_now(),
        "ended_at_utc": "",
        "git_sha": preflight["git_sha"],
        "config_path": str(config_path) if config_path else "",
        "config_hash": preflight["config_hash"],
        "dataset_manifest": preflight["dataset_manifest"],
        "dataset_manifest_hash": preflight["dataset_manifest_hash"],
        "selection_manifest": preflight["selection_manifest"],
        "selection_manifest_hash": preflight["selection_manifest_hash"],
        "output_dir": str(run_dir),
        "agent": _redact_sensitive_manifest_values(config["agent"]),
        "runtime": _redact_sensitive_manifest_values(runtime),
        "selected_summary": preflight["selected_summary"],
        "manifest_files": manifest_paths,
        "resume_fingerprint": resume_fingerprint,
        "resume_warnings": [],
    }
    run_manifest_path = layout["manifest"] / "run_manifest.json"
    _sync_run_manifest(run_manifest_path, run_manifest, backup_manager=backup_manager)

    if backup_manager is not None and not run_dir_preexisting:
        backup_manager.checkpoint("manifest_initialized", completed_episodes=0, force=True)
        _sync_run_manifest(run_manifest_path, run_manifest, backup_manager=backup_manager)

    if dry_run:
        run_manifest["ended_at_utc"] = utc_now()
        run_manifest["dry_run"] = True
        if backup_manager is not None:
            backup_manager.checkpoint("dry_run_completion", completed_episodes=0, force=True)
        _sync_run_manifest(run_manifest_path, run_manifest, backup_manager=backup_manager)
        response = {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "dry_run": True,
            "run_manifest_json": str(run_manifest_path),
            "preflight_report_json": manifest_paths["preflight_report_json"],
        }
        if backup_manager is not None:
            response["hf_backup_summary_json"] = str(backup_manager.summary_path)
            response["hf_backup_state_json"] = str(backup_manager.state_path)
        return response

    results: list[dict[str, Any]] = []
    for selected_row in selected_rows:
        artifact_path = _episode_artifact_path(layout, selected_row["episode_id"])
        if resume and artifact_path.exists():
            resumed_result, resume_warning = _load_resumable_result(artifact_path, resume_fingerprint)
            if resumed_result is not None:
                results.append(resumed_result)
            else:
                run_manifest["resume_warnings"].append(resume_warning)
                results.append(run_episode(selected_row, config, layout, resume_fingerprint))
        else:
            results.append(run_episode(selected_row, config, layout, resume_fingerprint))

        if backup_manager is not None and backup_manager.should_checkpoint(len(results)):
            partial_output_paths = write_run_outputs(layout, results)
            partial_output_paths["hf_backup_summary_json"] = str(backup_manager.summary_path)
            partial_output_paths["hf_backup_state_json"] = str(backup_manager.state_path)
            _sync_run_manifest(
                run_manifest_path,
                run_manifest,
                output_paths=partial_output_paths,
                backup_manager=backup_manager,
            )
            backup_manager.checkpoint(f"episode_batch_{len(results)}", completed_episodes=len(results), force=True)
            _sync_run_manifest(
                run_manifest_path,
                run_manifest,
                output_paths=partial_output_paths,
                backup_manager=backup_manager,
            )

    output_paths = write_run_outputs(layout, results)
    judge_summary = maybe_run_judge_pipeline(config, layout, output_paths["scored_episode_results_csv"])
    if judge_summary is not None:
        output_paths["judge_pipeline"] = judge_summary
    if backup_manager is not None:
        output_paths["hf_backup_summary_json"] = str(backup_manager.summary_path)
        output_paths["hf_backup_state_json"] = str(backup_manager.state_path)

    run_manifest.update(
        {
            "ended_at_utc": utc_now(),
            "dry_run": False,
        }
    )
    _sync_run_manifest(run_manifest_path, run_manifest, output_paths=output_paths, backup_manager=backup_manager)
    if backup_manager is not None:
        backup_manager.checkpoint("final_completion", completed_episodes=len(results), force=True)
        _sync_run_manifest(run_manifest_path, run_manifest, output_paths=output_paths, backup_manager=backup_manager)

    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "run_manifest_json": str(run_manifest_path),
        "preflight_report_json": manifest_paths["preflight_report_json"],
        **{
            key: value
            for key, value in output_paths.items()
            if key.endswith("_csv") or key.endswith("_json") or key == "judge_pipeline"
        },
        "failure_summary": output_paths["failure_summary"],
        "latency_summary": output_paths["latency_summary"],
        "token_usage_summary": output_paths["token_usage_summary"],
    }
