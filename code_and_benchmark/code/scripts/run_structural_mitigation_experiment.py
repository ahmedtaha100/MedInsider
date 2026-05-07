#!/usr/bin/env python

import argparse
import csv
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from medinsider.fhir.pilot_runtime import load_run_config, run_phase4_v2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_MANIFEST = PROJECT_ROOT / "artifacts" / "v2_manifest.csv"
SELECTION_MANIFEST = PROJECT_ROOT / "artifacts" / "subsets" / "v2_mitigation_compliance_gate_background_manifest.csv"
RESEARCH_PACKAGE_DIR = PROJECT_ROOT / "docs" / "research_package"
PAPER_DIR = PROJECT_ROOT / "docs" / "paper"

TARGET_FAMILIES = {
    "coding_and_billing_pressure",
    "quality_metric_pressure",
}
TARGET_PRESSURE_CONDITION = "background_pressure"

MODEL_SPECS = [
    {
        "label": "GPT-5.4",
        "config_paths": ["configs/phase4_v2/full_run_openai.json"],
        "baseline_run_dir": "runs/codex_openai_full_run",
    },
    {
        "label": "Claude Sonnet 4.6",
        "config_paths": ["configs/phase4_v2/full_run_sonnet46.json"],
        "baseline_run_dir": "runs/codex_sonnet46_full_run",
    },
    {
        "label": "DeepSeek V3.2",
        "config_paths": ["configs/phase4_v2/full_run_deepseekv32.json"],
        "baseline_run_dir": "runs/codex_deepseekv32_full_run",
    },
    {
        "label": "Gemma 4",
        "config_paths": [
            "configs/phase4_v2/full_run_gemma4_gpu0.json",
            "configs/phase4_v2/full_run_gemma4_gpu1.json",
        ],
        "baseline_run_dir": "",
        "baseline_run_glob": "phase4_v2_full_run_gemma4_*",
    },
]

API_KEY_LABEL_TO_ENV = {
    "Anthropic": "ANTHROPIC_API_KEY",
    "OpenAI KEY": "OPENAI_API_KEY",
    "DeepSeek": "DEEPSEEK_API_KEY",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_label(value: str) -> str:
    return value.lower().replace(".", "").replace(" ", "_").replace("-", "_")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _load_api_keys_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"api_keys_file_missing:{path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        label, value = line.split(":", 1)
        env_name = API_KEY_LABEL_TO_ENV.get(label.strip())
        if env_name and value.strip():
            os.environ.setdefault(env_name, value.strip())


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _merge_rows(
    existing_rows: list[dict[str, Any]],
    updated_rows: list[dict[str, Any]],
    *,
    key_fields: list[str],
    ordered_labels: Iterable[str],
) -> list[dict[str, Any]]:
    def _row_key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(row.get(field, "")) for field in key_fields)

    updated_by_key = {_row_key(row): row for row in updated_rows}
    updated_labels = {str(row.get("model_label", "")) for row in updated_rows}
    kept_rows = [row for row in existing_rows if str(row.get("model_label", "")) not in updated_labels]
    combined = kept_rows + list(updated_by_key.values())
    label_order = {label: index for index, label in enumerate(ordered_labels)}
    return sorted(
        combined,
        key=lambda row: (
            label_order.get(str(row.get("model_label", "")), len(label_order)),
            *(_row_key(row)),
        ),
    )


def build_selection_manifest() -> list[dict[str, str]]:
    rows = _load_csv_rows(DATASET_MANIFEST)
    selected = [
        row
        for row in rows
        if row["scenario_family"] in TARGET_FAMILIES
        and row["condition"] == TARGET_PRESSURE_CONDITION
        and row["twin_role"] == "pressure"
    ]
    selected = sorted(selected, key=lambda row: row["episode_id"])
    manifest_rows = [
        {
            "episode_id": row["episode_id"],
            "pair_id": row["pair_id"],
            "scenario_family": row["scenario_family"],
            "condition": row["condition"],
            "twin_role": row["twin_role"],
            "pressure_condition": row["pressure_condition"],
            "selection_group": TARGET_PRESSURE_CONDITION,
            "selection_reason": "structural_mitigation_compliance_gate_billing_quality_background_only",
        }
        for row in selected
    ]
    _write_csv(
        SELECTION_MANIFEST,
        manifest_rows,
        [
            "episode_id",
            "pair_id",
            "scenario_family",
            "condition",
            "twin_role",
            "pressure_condition",
            "selection_group",
            "selection_reason",
        ],
    )
    return manifest_rows


def _candidate_agent_base_config(config_paths: list[str]) -> dict[str, Any]:
    last_error = ""
    for relative_path in config_paths:
        config = load_run_config(PROJECT_ROOT / relative_path)
        agent = dict(config.get("agent", {}))
        base_url = str(agent.get("base_url", "")).strip()
        if base_url and ("127.0.0.1" in base_url or "localhost" in base_url):
            if not _openai_compatible_endpoint_reachable(base_url):
                last_error = f"endpoint_unreachable:{base_url}"
                continue
        return config
    if last_error:
        raise RuntimeError(last_error)
    raise RuntimeError("no_candidate_agent_config")


def _openai_compatible_endpoint_reachable(base_url: str) -> bool:
    req = urllib.request.Request(f"{base_url.rstrip('/')}/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _build_mitigation_config(base_config: dict[str, Any], label: str) -> tuple[Path, dict[str, Any]]:
    config = {
        "run_name": f"phase4_v2_mitigation_compliance_gate_{_sanitize_label(label)}",
        "dataset_manifest": DATASET_MANIFEST.as_posix(),
        "selection_manifest": SELECTION_MANIFEST.as_posix(),
        "output_root": "runs",
        "agent": dict(base_config["agent"]),
        "runtime": dict(base_config.get("runtime", {})),
        "hf_backup": {
            "enabled": False,
            "strict": False,
            "dry_run": False,
            "verify_remote": False,
            "batch_size": 5,
            "primary_repo": "",
            "secondary_repo": "",
        },
        "selection_expectations": {
            "pair_counts_by_group": {
                TARGET_PRESSURE_CONDITION: 24,
            },
            "require_all_families": False,
            "allowed_pressure_conditions": [TARGET_PRESSURE_CONDITION],
        },
    }
    config["runtime"]["require_complete_pairs"] = False
    config["runtime"]["resume"] = False
    config["runtime"]["overwrite"] = False
    config["runtime"]["judge_enabled"] = False
    config["runtime"]["structural_mitigation"] = "compliance_check_tool"
    config_path = PROJECT_ROOT / "configs" / "phase4_v2" / f"mitigation_compliance_gate_{_sanitize_label(label)}.json"
    _write_json(config_path, config)
    return config_path, config


def _load_scored_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return _load_csv_rows(path)


def _load_baseline_rows_for_spec(spec: dict[str, Any], episode_ids: set[str]) -> list[dict[str, Any]]:
    baseline_run_dir = str(spec.get("baseline_run_dir", "")).strip()
    if baseline_run_dir:
        return _filter_background_subset(
            _load_scored_rows(PROJECT_ROOT / baseline_run_dir / "artifacts" / "scored_episode_results.csv"),
            episode_ids,
        )

    baseline_run_glob = str(spec.get("baseline_run_glob", "")).strip()
    if not baseline_run_glob:
        return []

    combined_rows: list[dict[str, Any]] = []
    for run_dir in sorted((PROJECT_ROOT / "runs").glob(baseline_run_glob)):
        if not run_dir.is_dir():
            continue
        combined_rows.extend(_load_scored_rows(run_dir / "artifacts" / "scored_episode_results.csv"))
    return _filter_background_subset(combined_rows, episode_ids)


def _as_float(value: Any) -> float:
    text = str(value).strip()
    return float(text) if text else 0.0


def _mean(rows: list[dict[str, Any]], key: str) -> float | None:
    if not rows:
        return None
    return round(sum(_as_float(row.get(key, 0.0)) for row in rows) / len(rows), 4)


def _tradeoff_proxy_rate(rows: list[dict[str, Any]]) -> float | None:
    if not rows:
        return None
    hits = sum(1 for row in rows if str(row.get("tradeoff_mode", "")).strip() == "refused_misaligned_pressure")
    return round(hits / len(rows), 4)


def _filter_background_subset(rows: list[dict[str, Any]], episode_ids: set[str]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("episode_id") in episode_ids and row.get("condition") == TARGET_PRESSURE_CONDITION
    ]


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "episode_count": len(rows),
        "IVR": _mean(rows, "IVR"),
        "ATC": _mean(rows, "ATC"),
        "MGR": _mean(rows, "MGR"),
        "UPR_integrity": _mean(rows, "UPR_integrity"),
        "refused_misaligned_pressure_rate": _tradeoff_proxy_rate(rows),
    }


def _summary_delta(baseline: dict[str, Any], mitigation: dict[str, Any], key: str) -> float | None:
    left = baseline.get(key)
    right = mitigation.get(key)
    if left is None or right is None:
        return None
    return round(float(right) - float(left), 4)


def _display_cell(value: Any) -> str:
    if value is None:
        return "NA"
    text = str(value).strip()
    return text if text else "NA"


def run_experiment(run_suffix: str, selected_models: set[str] | None = None) -> dict[str, Any]:
    selection_rows = build_selection_manifest()
    episode_ids = {row["episode_id"] for row in selection_rows}

    execution_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    active_model_specs = [spec for spec in MODEL_SPECS if selected_models is None or spec["label"] in selected_models]

    for spec in active_model_specs:
        label = spec["label"]
        status = "completed"
        blocked_reason = ""
        run_id = ""
        run_dir = ""
        try:
            base_config = _candidate_agent_base_config(spec["config_paths"])
            config_path, _ = _build_mitigation_config(base_config, label)
            config = load_run_config(config_path)
            run_id = f"mitigation_compliance_gate_{_sanitize_label(label)}_{run_suffix}"
            config["run_id"] = run_id
            result = run_phase4_v2(config)
            run_dir = (
                str((PROJECT_ROOT / result["run_dir"]).resolve())
                if not Path(result["run_dir"]).is_absolute()
                else result["run_dir"]
            )
        except Exception as exc:
            status = "blocked"
            blocked_reason = f"{type(exc).__name__}:{exc}"

        execution_rows.append(
            {
                "model_label": label,
                "status": status,
                "run_id": run_id,
                "run_dir": run_dir,
                "blocked_reason": blocked_reason,
            }
        )

        if status != "completed":
            comparison_rows.append(
                {
                    "model_label": label,
                    "status": status,
                    "baseline_episode_count": "",
                    "mitigation_episode_count": "",
                    "baseline_IVR": "",
                    "mitigation_IVR": "",
                    "delta_IVR": "",
                    "baseline_ATC": "",
                    "mitigation_ATC": "",
                    "delta_ATC": "",
                    "baseline_MGR": "",
                    "mitigation_MGR": "",
                    "delta_MGR": "",
                    "baseline_UPR_integrity": "",
                    "mitigation_UPR_integrity": "",
                    "delta_UPR_integrity": "",
                    "baseline_refused_misaligned_pressure_rate": "",
                    "mitigation_refused_misaligned_pressure_rate": "",
                    "delta_refused_misaligned_pressure_rate": "",
                    "scope_note": blocked_reason,
                }
            )
            continue

        baseline_rows = _load_baseline_rows_for_spec(spec, episode_ids)
        mitigation_rows = _filter_background_subset(
            _load_scored_rows(Path(run_dir) / "artifacts" / "scored_episode_results.csv"),
            episode_ids,
        )
        baseline_summary = _metric_summary(baseline_rows)
        mitigation_summary = _metric_summary(mitigation_rows)

        comparison_rows.append(
            {
                "model_label": label,
                "status": status,
                "baseline_episode_count": baseline_summary["episode_count"],
                "mitigation_episode_count": mitigation_summary["episode_count"],
                "baseline_IVR": baseline_summary["IVR"],
                "mitigation_IVR": mitigation_summary["IVR"],
                "delta_IVR": _summary_delta(baseline_summary, mitigation_summary, "IVR"),
                "baseline_ATC": baseline_summary["ATC"],
                "mitigation_ATC": mitigation_summary["ATC"],
                "delta_ATC": _summary_delta(baseline_summary, mitigation_summary, "ATC"),
                "baseline_MGR": baseline_summary["MGR"],
                "mitigation_MGR": mitigation_summary["MGR"],
                "delta_MGR": _summary_delta(baseline_summary, mitigation_summary, "MGR"),
                "baseline_UPR_integrity": baseline_summary["UPR_integrity"],
                "mitigation_UPR_integrity": mitigation_summary["UPR_integrity"],
                "delta_UPR_integrity": _summary_delta(baseline_summary, mitigation_summary, "UPR_integrity"),
                "baseline_refused_misaligned_pressure_rate": baseline_summary["refused_misaligned_pressure_rate"],
                "mitigation_refused_misaligned_pressure_rate": mitigation_summary["refused_misaligned_pressure_rate"],
                "delta_refused_misaligned_pressure_rate": _summary_delta(
                    baseline_summary,
                    mitigation_summary,
                    "refused_misaligned_pressure_rate",
                ),
                "scope_note": (
                    "billing and quality background-pressure episodes only; "
                    "refusal metric operationalized as refused_misaligned_pressure tradeoff proxy"
                ),
            }
        )

    execution_fields = ["model_label", "status", "run_id", "run_dir", "blocked_reason"]
    comparison_fields = [
        "model_label",
        "status",
        "baseline_episode_count",
        "mitigation_episode_count",
        "baseline_IVR",
        "mitigation_IVR",
        "delta_IVR",
        "baseline_ATC",
        "mitigation_ATC",
        "delta_ATC",
        "baseline_MGR",
        "mitigation_MGR",
        "delta_MGR",
        "baseline_UPR_integrity",
        "mitigation_UPR_integrity",
        "delta_UPR_integrity",
        "baseline_refused_misaligned_pressure_rate",
        "mitigation_refused_misaligned_pressure_rate",
        "delta_refused_misaligned_pressure_rate",
        "scope_note",
    ]

    ordered_labels = [spec["label"] for spec in MODEL_SPECS]
    merged_execution_rows = _merge_rows(
        _load_csv_rows(RESEARCH_PACKAGE_DIR / "structural_mitigation_execution_roster.csv"),
        execution_rows,
        key_fields=["model_label"],
        ordered_labels=ordered_labels,
    )
    merged_comparison_rows = _merge_rows(
        _load_csv_rows(RESEARCH_PACKAGE_DIR / "structural_mitigation_comparison.csv"),
        comparison_rows,
        key_fields=["model_label"],
        ordered_labels=ordered_labels,
    )

    _write_csv(
        RESEARCH_PACKAGE_DIR / "structural_mitigation_execution_roster.csv", merged_execution_rows, execution_fields
    )
    _write_csv(RESEARCH_PACKAGE_DIR / "structural_mitigation_comparison.csv", merged_comparison_rows, comparison_fields)
    _write_csv(PAPER_DIR / "final_structural_mitigation_table.csv", merged_comparison_rows, comparison_fields)

    summary_lines = [
        "# Structural Mitigation Summary",
        "",
        "- Mitigation: `compliance_check_tool`",
        "- Structural form: real gated `compliance_check` tool enforced before `submit_billing` and `quality_report`",
        "- Scope: background-pressure pressure episodes only",
        "- Families: coding_and_billing_pressure, quality_metric_pressure",
        "- Target clean-model slice: GPT-5.4, Claude Sonnet 4.6, DeepSeek V3.2, Gemma 4 if reachable",
        "",
        "## Results",
        "",
        "| Model | Status | Baseline IVR | Mitigation IVR | Delta IVR | Baseline ATC | Mitigation ATC | Delta ATC |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in merged_comparison_rows:
        summary_lines.append(
            f"| {row['model_label']} | {row['status']} | {_display_cell(row['baseline_IVR'])} | "
            f"{_display_cell(row['mitigation_IVR'])} | {_display_cell(row['delta_IVR'])} | "
            f"{_display_cell(row['baseline_ATC'])} | {_display_cell(row['mitigation_ATC'])} | "
            f"{_display_cell(row['delta_ATC'])} |"
        )
    summary_lines.extend(
        [
            "",
            "Refusal-overcorrection is reported here as the existing "
            "`refused_misaligned_pressure` tradeoff-mode proxy rather than a "
            "new post hoc metric.",
            "",
        ]
    )
    blocked_models = [row["model_label"] for row in merged_comparison_rows if row["status"] != "completed"]
    if blocked_models:
        summary_lines.extend(
            [
                "Blocked models in this mitigation packet should be reported as "
                "infrastructure blockers rather than as mitigation failures.",
                "",
            ]
        )
    else:
        summary_lines.extend(
            [
                "The current bounded mitigation packet now includes Gemma 4 after "
                "the restored dual-endpoint H200 runtime was brought back online.",
                "",
            ]
        )
    (RESEARCH_PACKAGE_DIR / "structural_mitigation_summary.md").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    _write_json(
        RESEARCH_PACKAGE_DIR / "structural_mitigation_manifest.json",
        {
            "generated_at_utc": utc_now(),
            "selection_manifest": SELECTION_MANIFEST.as_posix(),
            "target_families": sorted(TARGET_FAMILIES),
            "pressure_condition": TARGET_PRESSURE_CONDITION,
            "execution_rows": merged_execution_rows,
        },
    )

    return {
        "selection_manifest": str(SELECTION_MANIFEST),
        "execution_rows": merged_execution_rows,
        "comparison_rows": merged_comparison_rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the bounded structural mitigation experiment.")
    parser.add_argument("--api-keys-file", default="", help="Optional path to apikeys.txt for provider env loading.")
    parser.add_argument(
        "--models",
        nargs="+",
        default=[],
        help='Optional model-label filter (for example: --models "Gemma 4").',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.api_keys_file:
        _load_api_keys_file(Path(args.api_keys_file))
    run_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    selected_models = {label.strip() for label in args.models if label.strip()} or None
    result = run_experiment(run_suffix, selected_models=selected_models)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
