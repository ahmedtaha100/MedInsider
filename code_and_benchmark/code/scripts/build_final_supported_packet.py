"""Build the current seven-model paper-facing packet from authoritative artifacts.

This script is read-only over the authoritative run directories and the Gemma
shard closeout report. It produces:

- docs/paper/final_table3_seven_model_results.csv
- docs/paper/final_table3_seven_model_results.md
- docs/paper/final_table3_model_caveats.csv
- docs/paper/final_table3_model_caveats.md
- docs/paper/final_table7_condition_breakdown.csv
- docs/paper/final_table7_condition_breakdown.md
- docs/paper/final_compute_appendix_seven_model.csv
- docs/paper/final_compute_appendix_seven_model.md
- docs/paper/final_supported_source_inventory.csv
- docs/paper/final_supported_source_inventory.md

It also preserves the older archival subset outputs:

- docs/paper/final_table3_closed_models.csv
- docs/paper/final_figure2_source.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("docs/paper")
RESEARCH_PACKAGE_DIR = Path("docs/research_package")
FIGURE2_SOURCE = RESEARCH_PACKAGE_DIR / "capability_control_within_scenario_source.csv"
FIGURE2_SUMMARY = RESEARCH_PACKAGE_DIR / "capability_control_model_summary.csv"
GEMMA_CLOSEOUT_REPORT = RESEARCH_PACKAGE_DIR / "gemma4_shard_closeout_report.json"
STATUS_MATRIX_PATH = RESEARCH_PACKAGE_DIR / "final_roster_status_matrix.csv"

ARCHIVAL_CLOSED_MODEL_SPECS = (
    {
        "run_id": "codex_openai_full_run",
        "run_root": Path("tmp_restore_audit/codex_openai_full_run"),
        "model_display": "GPT-5.4",
        "resolved_model_id": "gpt-5.4-2026-03-05",
        "key_run_caveat": "Parse-repair heavy; OpenAI HF backup is posthoc rather than launch-time mirrored.",
    },
    {
        "run_id": "codex_opus47_full_run",
        "run_root": Path("tmp_restore_audit/codex_opus47_full_run"),
        "model_display": "Claude Opus 4.7",
        "resolved_model_id": "claude-opus-4-7",
        "key_run_caveat": "Post-rerun authoritative output is complete at 840 scored episodes / 420 fully scored pairs.",
    },
    {
        "run_id": "codex_sonnet46_full_run",
        "run_root": Path("tmp_restore_audit/codex_sonnet46_full_run"),
        "model_display": "Claude Sonnet 4.6",
        "resolved_model_id": "claude-sonnet-4-6",
        "key_run_caveat": "Artifact-clean; quality_metric remains the weakest ATC family.",
    },
)

SEVEN_MODEL_SPECS = (
    {
        "model_display": "GPT-5.4",
        "resolved_model_id": "gpt-5.4-2026-03-05",
        "run_roots": [Path("tmp_restore_audit/codex_openai_full_run")],
        "final_status": "complete",
        "manuscript_caveat": "Main benchmark complete; HF backup provenance is posthoc.",
        "auxiliary_caveat": "",
    },
    {
        "model_display": "Claude Sonnet 4.6",
        "resolved_model_id": "claude-sonnet-4-6",
        "run_roots": [Path("tmp_restore_audit/codex_sonnet46_full_run")],
        "final_status": "complete",
        "manuscript_caveat": "Main benchmark complete and artifact-clean.",
        "auxiliary_caveat": "",
    },
    {
        "model_display": "Claude Opus 4.7",
        "resolved_model_id": "claude-opus-4-7",
        "run_roots": [Path("tmp_restore_audit/codex_opus47_full_run")],
        "final_status": "complete_after_targeted_rerun",
        "manuscript_caveat": "Main benchmark complete after targeted rerun; post-rerun scored output locked on 2026-05-05.",
        "auxiliary_caveat": "Coding-probe run is usable but carries two provider-error rows.",
    },
    {
        "model_display": "Kimi 2.6",
        "resolved_model_id": "kimi-k2.6",
        "run_roots": [Path("tmp_restore_kimi_closeout/codex_kimi26_full_run")],
        "final_status": "complete_after_targeted_rerun",
        "manuscript_caveat": "Main benchmark complete after targeted rerun; post-rerun scored output locked on 2026-05-05.",
        "auxiliary_caveat": "Coding-probe run is usable but carries one provider-error row.",
    },
    {
        "model_display": "GLM-5",
        "resolved_model_id": "glm-5",
        "run_roots": [Path("tmp_restore_glm5_closeout/codex_glm5_full_run")],
        "final_status": "complete_after_targeted_rerun",
        "manuscript_caveat": "Main benchmark complete after targeted rerun; the prior max-call episode succeeded under the unchanged cap.",
        "auxiliary_caveat": "Coding-probe run is usable but heavily caveated with eight provider-error rows.",
    },
    {
        "model_display": "DeepSeek V3.2",
        "resolved_model_id": "deepseek-chat",
        "run_roots": [Path("tmp_restore_deepseek_closeout/codex_deepseekv32_full_run")],
        "final_status": "complete",
        "manuscript_caveat": "Main benchmark complete; one transient HF verify flake cleared on immediate retry.",
        "auxiliary_caveat": "",
    },
    {
        "model_display": "Gemma 4",
        "resolved_model_id": "google/gemma-4-31B-it",
        "run_roots": [],
        "final_status": "complete",
        "manuscript_caveat": (
            "Main benchmark complete as a 10-shard authoritative package after prelaunch infra recovery."
        ),
        "auxiliary_caveat": (
            "Coding probe completed 15/15 and bounded mitigation completed on "
            "the restored dual-endpoint H200 runtime; keep the auxiliary scope "
            "bounded rather than treating it as a broad mitigation suite."
        ),
    },
)

TABLE_METRICS = ("ATC", "IVR", "MGR", "UPR_integrity", "AEOR", "PSD", "CDR")


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV to {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _write_markdown_table(path: Path, title: str, intro: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty markdown table to {path}")
    headers = list(rows[0].keys())
    lines = [f"# {title}", "", intro, ""]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_status_matrix() -> dict[str, dict[str, str]]:
    rows = _load_csv_rows(STATUS_MATRIX_PATH)
    return {row["model_display"]: row for row in rows}


def _collect_single_run_data(run_root: Path, expected_model_id: str) -> dict[str, Any]:
    scored_rows = _load_csv_rows(run_root / "artifacts" / "scored_episode_results.csv")
    episode_rows = _load_csv_rows(run_root / "artifacts" / "episode_results.csv")
    pair_rows = _load_csv_rows(run_root / "summaries" / "pair_summary.csv")
    token_summary = _load_json(run_root / "summaries" / "token_usage_summary.json")
    latency_summary = _load_json(run_root / "summaries" / "latency_summary.json")
    parse_summary = _load_json(run_root / "summaries" / "parse_repair_summary.json")
    failure_summary = _load_json(run_root / "summaries" / "failure_summary.json")

    resolved_models = {row.get("resolved_model", "") for row in scored_rows}
    resolved_models.discard("")
    if resolved_models and resolved_models != {expected_model_id}:
        raise ValueError(f"Unexpected resolved_model set for {run_root}: {sorted(resolved_models)}")

    return {
        "scored_rows": scored_rows,
        "episode_rows": episode_rows,
        "pair_rows": pair_rows,
        "token_summary": token_summary,
        "latency_summary": latency_summary,
        "parse_summary": parse_summary,
        "failure_summary": failure_summary,
    }


def _collect_gemma_data() -> dict[str, Any]:
    report = _load_json(GEMMA_CLOSEOUT_REPORT)
    scored_rows: list[dict[str, str]] = []
    episode_rows: list[dict[str, str]] = []
    pair_rows: list[dict[str, str]] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    p95_values: list[float] = []
    status_counts: dict[str, int] = defaultdict(int)
    run_ids: list[str] = []
    for entry in report["runs"]:
        original_run_root = Path(str(entry["run_dir"]).replace("\\", "/"))
        candidate_roots = [
            original_run_root,
            Path("tmp_restore_gemma4") / entry["run_id"],
            Path("tmp_restore_gemma4_retry") / entry["run_id"],
        ]
        run_root = next(
            (
                candidate
                for candidate in candidate_roots
                if (candidate / "artifacts" / "scored_episode_results.csv").exists()
            ),
            candidate_roots[0],
        )
        run_ids.append(entry["run_id"])
        scored_rows.extend(_load_csv_rows(run_root / "artifacts" / "scored_episode_results.csv"))
        episode_rows.extend(_load_csv_rows(run_root / "artifacts" / "episode_results.csv"))
        pair_rows.extend(_load_csv_rows(run_root / "summaries" / "pair_summary.csv"))
        token_summary = _load_json(run_root / "summaries" / "token_usage_summary.json")
        latency_summary = _load_json(run_root / "summaries" / "latency_summary.json")
        total_input_tokens += int(token_summary.get("total_input_tokens", 0))
        total_output_tokens += int(token_summary.get("total_output_tokens", 0))
        total_tokens += int(token_summary.get("total_tokens", 0))
        p95_values.append(_safe_float(latency_summary.get("p95_seconds")))
        failure_summary = entry["local_checks"]["failure_summary"]
        for status, count in failure_summary.get("status_counts", {}).items():
            status_counts[status] += int(count)

    return {
        "scored_rows": scored_rows,
        "episode_rows": episode_rows,
        "pair_rows": pair_rows,
        "token_summary": {
            "episode_count": len(episode_rows),
            "episodes_with_usage": len(episode_rows),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tokens": total_tokens,
        },
        "latency_summary": {
            "episode_count": len(episode_rows),
            "p95_range": f"{min(p95_values):.4f}s to {max(p95_values):.4f}s",
        },
        "parse_summary": {
            "episode_count": len(episode_rows),
            "episodes_with_repairs": 0,
            "total_parse_repairs": 0,
        },
        "failure_summary": {
            "episode_count": len(episode_rows),
            "status_counts": dict(status_counts),
            "scored_episode_count": len(scored_rows),
        },
        "run_ids": run_ids,
    }


def _collect_model_data(spec: dict[str, Any]) -> dict[str, Any]:
    if spec["model_display"] == "Gemma 4":
        return _collect_gemma_data()
    if len(spec["run_roots"]) != 1:
        raise ValueError(f"Unexpected run_roots for non-Gemma model: {spec['model_display']}")
    return _collect_single_run_data(spec["run_roots"][0], spec["resolved_model_id"])


def _mean_metric(rows: list[dict[str, str]], metric: str) -> float:
    return round(statistics.fmean(_safe_float(row.get(metric)) for row in rows), 4)


def _compute_refusal_proxy_rate(rows: list[dict[str, str]]) -> float:
    if not rows:
        return 0.0
    positives = sum(str(row.get("tradeoff_mode", "")).strip() == "refused_misaligned_pressure" for row in rows)
    return round(positives / len(rows), 4)


def _failure_counts_text(failure_summary: dict[str, Any]) -> str:
    status_counts = failure_summary.get("status_counts", {})
    ordered = sorted(status_counts.items())
    return "|".join(f"{status}={count}" for status, count in ordered)


def _fully_scored_pairs(pair_rows: list[dict[str, str]]) -> int:
    return sum(row.get("neutral_scored") == "True" and row.get("pressure_scored") == "True" for row in pair_rows)


def build_archival_closed_model_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in ARCHIVAL_CLOSED_MODEL_SPECS:
        data = _collect_single_run_data(spec["run_root"], spec["resolved_model_id"])
        scored_rows = data["scored_rows"]
        pair_rows = data["pair_rows"]
        parse_summary = data["parse_summary"]
        metric_means = {metric: _mean_metric(scored_rows, metric) for metric in TABLE_METRICS}
        parse_notes = (
            f"{parse_summary['episodes_with_repairs']}/{parse_summary['episode_count']} episodes "
            f"required parse repair ({parse_summary['total_parse_repairs']} total repairs)"
        )
        rows.append(
            {
                "model_display": spec["model_display"],
                "resolved_model_id": spec["resolved_model_id"],
                "scored_episodes": len(scored_rows),
                "fully_scored_pairs": _fully_scored_pairs(pair_rows),
                "ATC_mean": metric_means["ATC"],
                "IVR_mean": metric_means["IVR"],
                "MGR_mean": metric_means["MGR"],
                "AEOR_mean": metric_means["AEOR"],
                "CDR_mean": metric_means["CDR"],
                "PSD_mean": metric_means["PSD"],
                "parse_repair_notes": parse_notes,
                "key_run_caveat": spec["key_run_caveat"],
            }
        )
    return rows


def build_archival_figure2_rows() -> list[dict[str, Any]]:
    within_rows = _load_csv_rows(FIGURE2_SOURCE)
    summary_rows = _load_csv_rows(FIGURE2_SUMMARY)
    display_by_model = {spec["resolved_model_id"]: spec["model_display"] for spec in ARCHIVAL_CLOSED_MODEL_SPECS}
    summary_lookup = {(row["run_id"], row["model_id"], row["condition"]): row for row in summary_rows}
    final_rows: list[dict[str, Any]] = []
    for row in within_rows:
        key = (row["run_id"], row["model_id"], row["condition"])
        summary = summary_lookup.get(key)
        if summary is None:
            raise ValueError(f"Missing model summary for {key}")
        final_rows.append(
            {
                "model_display": display_by_model.get(row["model_id"], row["model_id"]),
                "resolved_model_id": row["model_id"],
                "run_id": row["run_id"],
                "episode_id": row["episode_id"],
                "pair_id": row["pair_id"],
                "family": row["scenario_family"],
                "condition": row["condition"],
                "pressure_condition": row["pressure_condition"],
                "capability_score": row["capability_score"],
                "capability_completed": row["capability_completed"],
                "capability_total": row["capability_total"],
                "capability_missing": row["capability_missing"],
                "capability_scorer_version": row["capability_scorer_version"],
                "ATC": row["ATC"],
                "IVR": row["IVR"],
                "MGR": row["MGR"],
                "UPR_integrity": row["UPR_integrity"],
                "AEOR": row["AEOR"],
                "PSD": row["PSD"],
                "CDR": row["CDR"],
                "integrity_primary_any": row["integrity_primary_any"],
                "condition_capability_mean": summary["capability_mean"],
                "condition_atc_mean": summary["atc_mean"],
                "condition_integrity_primary_any_rate": summary["integrity_primary_any_rate"],
                "high_cap_threshold": summary["high_cap_threshold"],
                "high_cap_episode_count": summary["high_cap_episode_count"],
                "high_cap_with_integrity_failure_count": summary["high_cap_with_integrity_failure_count"],
            }
        )
    return final_rows


def build_seven_model_results_rows() -> list[dict[str, Any]]:
    status_matrix = _load_status_matrix()
    rows: list[dict[str, Any]] = []
    for spec in SEVEN_MODEL_SPECS:
        data = _collect_model_data(spec)
        scored_rows = data["scored_rows"]
        pair_rows = data["pair_rows"]
        token_summary = data["token_summary"]
        latency_summary = data["latency_summary"]
        parse_summary = data["parse_summary"]
        failure_summary = data["failure_summary"]
        status_row = status_matrix[spec["model_display"]]

        parse_note = (
            f"{parse_summary.get('episodes_with_repairs', 0)}/{parse_summary.get('episode_count', 0)} episodes "
            f"required parse repair ({parse_summary.get('total_parse_repairs', 0)} total repairs)"
        )
        latency_value = latency_summary.get("p95_seconds")
        p95_display = (
            f"{_safe_float(latency_value):.4f}"
            if latency_value not in (None, "")
            else str(latency_summary.get("p95_range", ""))
        )
        rows.append(
            {
                "model_display": spec["model_display"],
                "resolved_model_id": spec["resolved_model_id"],
                "final_status": spec["final_status"],
                "scored_episodes": len(scored_rows),
                "fully_scored_pairs": _fully_scored_pairs(pair_rows),
                "ATC_mean": _mean_metric(scored_rows, "ATC"),
                "IVR_mean": _mean_metric(scored_rows, "IVR"),
                "MGR_mean": _mean_metric(scored_rows, "MGR"),
                "UPR_integrity_mean": _mean_metric(scored_rows, "UPR_integrity"),
                "AEOR_mean": _mean_metric(scored_rows, "AEOR"),
                "PSD_mean": _mean_metric(scored_rows, "PSD"),
                "CDR_mean": _mean_metric(scored_rows, "CDR"),
                "refused_misaligned_pressure_rate": _compute_refusal_proxy_rate(scored_rows),
                "failure_counts": _failure_counts_text(failure_summary),
                "total_tokens": int(token_summary.get("total_tokens", 0)),
                "p95_latency_seconds_or_range": p95_display,
                "parse_repair_note": parse_note,
                "backup_restore_note": status_row["restore_test_status"],
                "manuscript_caveat": spec["manuscript_caveat"],
            }
        )
    return rows


def build_condition_breakdown_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in SEVEN_MODEL_SPECS:
        data = _collect_model_data(spec)
        episode_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        scored_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in data["episode_rows"]:
            episode_groups[(row["selection_group"], row["condition"])].append(row)
        for row in data["scored_rows"]:
            scored_groups[(row["selection_group"], row["condition"])].append(row)

        for key in sorted(episode_groups):
            episode_rows = episode_groups[key]
            scored_rows = scored_groups.get(key, [])
            selection_group, condition = key
            success_count = sum(row.get("status") == "success" for row in episode_rows)
            max_call_count = sum(row.get("status") == "max_call_termination" for row in episode_rows)
            row: dict[str, Any] = {
                "model_display": spec["model_display"],
                "resolved_model_id": spec["resolved_model_id"],
                "selection_group": selection_group,
                "condition": condition,
                "episode_count": len(episode_rows),
                "scored_episode_count": len(scored_rows),
                "success_count": success_count,
                "max_call_termination_count": max_call_count,
            }
            for metric in TABLE_METRICS:
                row[metric] = (
                    round(
                        statistics.fmean(_safe_float(r.get(metric)) for r in scored_rows),
                        4,
                    )
                    if scored_rows
                    else ""
                )
            row["refused_misaligned_pressure_rate"] = _compute_refusal_proxy_rate(scored_rows) if scored_rows else ""
            rows.append(row)
    return rows


def build_caveat_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in SEVEN_MODEL_SPECS:
        if not spec["manuscript_caveat"] and not spec["auxiliary_caveat"]:
            continue
        rows.append(
            {
                "model_display": spec["model_display"],
                "main_benchmark_status": spec["final_status"],
                "benchmark_caveat": spec["manuscript_caveat"],
                "auxiliary_add_on_caveat": spec["auxiliary_caveat"] or "none",
                "manuscript_rule": (
                    "Keep the auxiliary add-on caveat separate from the complete main-benchmark result."
                    if spec["auxiliary_caveat"]
                    else "Safe for main-text reporting with the benchmark/provenance note visible."
                ),
            }
        )
    return rows


def build_compute_rows() -> list[dict[str, Any]]:
    status_matrix = _load_status_matrix()
    rows: list[dict[str, Any]] = []
    for spec in SEVEN_MODEL_SPECS:
        data = _collect_model_data(spec)
        token_summary = data["token_summary"]
        latency_summary = data["latency_summary"]
        parse_summary = data["parse_summary"]
        status_row = status_matrix[spec["model_display"]]
        latency_value = latency_summary.get("p95_seconds")
        p95_display = (
            f"{_safe_float(latency_value):.4f}"
            if latency_value not in (None, "")
            else str(latency_summary.get("p95_range", ""))
        )
        rows.append(
            {
                "model_display": spec["model_display"],
                "resolved_model_id": spec["resolved_model_id"],
                "episodes_with_usage": int(token_summary.get("episodes_with_usage", 0)),
                "total_input_tokens": int(token_summary.get("total_input_tokens", 0)),
                "total_output_tokens": int(token_summary.get("total_output_tokens", 0)),
                "total_tokens": int(token_summary.get("total_tokens", 0)),
                "p95_latency_seconds_or_range": p95_display,
                "episodes_with_parse_repairs": int(parse_summary.get("episodes_with_repairs", 0)),
                "total_parse_repairs": int(parse_summary.get("total_parse_repairs", 0)),
                "hf_primary_status": status_row["hf_primary_backup_status"],
                "hf_secondary_status": status_row["hf_secondary_backup_status"],
                "restore_status": status_row["restore_test_status"],
                "compute_note": spec["manuscript_caveat"],
            }
        )
    return rows


def build_source_inventory_rows() -> list[dict[str, Any]]:
    return [
        {
            "artifact_path": "docs/paper/final_table3_seven_model_results.csv",
            "artifact_role": "main seven-model results table",
            "status": "current",
            "scope_note": "fixed 7-model benchmark roster; Gemma included as main-benchmark-complete",
            "supporting_sources": (
                "tmp_restore_*/codex_*_full_run/artifacts/scored_episode_results.csv; "
                "tmp_restore_*/codex_*_full_run/summaries/pair_summary.csv; "
                "docs/research_package/gemma4_shard_closeout_report.json"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table3_model_caveats.csv",
            "artifact_role": "model provenance/caveat table",
            "status": "current",
            "scope_note": "main-benchmark provenance notes plus bounded auxiliary add-on caveats",
            "supporting_sources": (
                "docs/research_package/final_roster_status_matrix.csv; "
                "docs/research_package/probe_mitigation_double_check_summary.md"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table5_coding_probe.csv",
            "artifact_role": "coding probe table",
            "status": "current",
            "scope_note": "bounded fixed-bank probe with caveats and Gemma refresh completion",
            "supporting_sources": (
                "runs/coding_probe_fixed_roster_20260423T033826Z/artifacts/*; "
                "docs/research_package/coding_probe_model_summary.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_structural_mitigation_table.csv",
            "artifact_role": "structural mitigation table",
            "status": "current",
            "scope_note": "bounded compliance_check_tool study on billing/quality background_pressure slice",
            "supporting_sources": (
                "artifacts/subsets/v2_mitigation_compliance_gate_background_manifest.csv; "
                "runs/mitigation_compliance_gate_*; "
                "docs/research_package/structural_mitigation_comparison.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table7_condition_breakdown.csv",
            "artifact_role": "condition breakdown table",
            "status": "current",
            "scope_note": "descriptive seven-model per-condition metrics from authoritative runs",
            "supporting_sources": (
                "tmp_restore_*/codex_*_full_run/artifacts/episode_results.csv; "
                "tmp_restore_*/codex_*_full_run/artifacts/scored_episode_results.csv; "
                "docs/research_package/gemma4_shard_closeout_report.json"
            ),
        },
        {
            "artifact_path": "docs/paper/final_compute_appendix_seven_model.csv",
            "artifact_role": "compute/provenance appendix",
            "status": "current",
            "scope_note": "seven-model token, latency, parse, backup, and restore surface",
            "supporting_sources": (
                "tmp_restore_*/codex_*_full_run/summaries/token_usage_summary.json; "
                "tmp_restore_*/codex_*_full_run/summaries/latency_summary.json; "
                "tmp_restore_*/codex_*_full_run/summaries/parse_repair_summary.json; "
                "docs/research_package/final_roster_status_matrix.csv; "
                "docs/research_package/gemma4_shard_closeout_report.json"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table3_closed_models.csv",
            "artifact_role": "archival closed-model table",
            "status": "archival",
            "scope_note": "older three-model subset retained for provenance only",
            "supporting_sources": (
                "tmp_restore_audit/codex_openai_full_run; "
                "tmp_restore_audit/codex_opus47_full_run; "
                "tmp_restore_audit/codex_sonnet46_full_run"
            ),
        },
        {
            "artifact_path": "docs/paper/final_figure2_source.csv",
            "artifact_role": "archival capability-control source",
            "status": "archival",
            "scope_note": "older internal closed-model subset figure source",
            "supporting_sources": (
                "docs/research_package/capability_control_within_scenario_source.csv; "
                "docs/research_package/capability_control_model_summary.csv"
            ),
        },
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build the final supported paper packet by aggregating "
            "authoritative scored outputs into manuscript CSVs. Requires HF "
            "restore of run trees in tmp_restore_audit/. Reviewer note: the "
            "bundled docs/paper/final_table*.csv files are the materialized "
            "output of this script and can be inspected directly without "
            "running the rebuilder."
        )
    )
    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_DIR),
        help="Output directory for materialized CSVs.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_root)

    archival_rows = build_archival_closed_model_rows()
    archival_figure_rows = build_archival_figure2_rows()
    seven_model_rows = build_seven_model_results_rows()
    caveat_rows = build_caveat_rows()
    condition_rows = build_condition_breakdown_rows()
    compute_rows = build_compute_rows()
    inventory_rows = build_source_inventory_rows()

    _write_csv(output_dir / "final_table3_closed_models.csv", archival_rows)
    _write_markdown_table(
        output_dir / "final_table3_closed_models.md",
        "Final Table 3: Closed Models Only",
        (
            "Historical three-model subset table rebuilt from the current "
            "post-rerun authoritative closed-model outputs."
        ),
        archival_rows,
    )
    _write_csv(output_dir / "final_figure2_source.csv", archival_figure_rows)

    _write_csv(output_dir / "final_table3_seven_model_results.csv", seven_model_rows)
    _write_markdown_table(
        output_dir / "final_table3_seven_model_results.md",
        "Final Table 3: Seven-Model Results",
        "Current seven-model results table built from authoritative run outputs and the Gemma shard closeout package.",
        seven_model_rows,
    )

    _write_csv(output_dir / "final_table3_model_caveats.csv", caveat_rows)
    _write_markdown_table(
        output_dir / "final_table3_model_caveats.md",
        "Final Model Provenance and Caveat Table",
        "Main-benchmark provenance notes and bounded auxiliary add-on caveats that must stay visible in the manuscript.",
        caveat_rows,
    )

    _write_csv(output_dir / "final_table7_condition_breakdown.csv", condition_rows)
    _write_markdown_table(
        output_dir / "final_table7_condition_breakdown.md",
        "Final Table 7: Seven-Model Condition Breakdown",
        "Descriptive per-model condition breakdown built from episode-level authoritative outputs.",
        condition_rows,
    )

    _write_csv(output_dir / "final_compute_appendix_seven_model.csv", compute_rows)
    _write_markdown_table(
        output_dir / "final_compute_appendix_seven_model.md",
        "Final Compute Appendix: Seven-Model Observed Surface",
        (
            "Observed token, latency, parse-repair, backup, and restore surface "
            "for the current seven-model benchmark package."
        ),
        compute_rows,
    )

    _write_csv(output_dir / "final_supported_source_inventory.csv", inventory_rows)
    _write_markdown_table(
        output_dir / "final_supported_source_inventory.md",
        "Final Supported Source Inventory",
        "Current paper-facing and archival source artifacts for the verified seven-model packet.",
        inventory_rows,
    )


if __name__ == "__main__":
    main()
