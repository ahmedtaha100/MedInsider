"""Build the submitted paper-facing packet from bundled artifacts.

This cold-clone-safe builder consumes the shipped per-episode scored outputs in
``data/scored_outputs/per_episode`` and validates the key generated tables
against the locked CSVs under ``docs/paper``. It intentionally does not depend
on untracked provider-run restore roots.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("docs/paper")
SCORED_OUTPUT_DIR = Path("data/scored_outputs/per_episode")

TABLE_METRICS = ("ATC", "IVR", "MGR", "UPR_integrity", "AEOR", "PSD", "CDR")

MODEL_SPECS = (
    {
        "model_display": "GPT-5.4",
        "resolved_model_id": "gpt-5.4-2026-03-05",
        "scored_file": "gpt5-4_scored_episodes.csv",
    },
    {
        "model_display": "Claude Sonnet 4.6",
        "resolved_model_id": "claude-sonnet-4-6",
        "scored_file": "claude_sonnet_4-6_scored_episodes.csv",
    },
    {
        "model_display": "Claude Opus 4.7",
        "resolved_model_id": "claude-opus-4-7",
        "scored_file": "claude_opus_4-7_scored_episodes.csv",
    },
    {
        "model_display": "Kimi 2.6",
        "resolved_model_id": "kimi-k2.6",
        "scored_file": "kimi_2-6_scored_episodes.csv",
    },
    {
        "model_display": "GLM-5",
        "resolved_model_id": "glm-5",
        "scored_file": "glm-5_scored_episodes.csv",
    },
    {
        "model_display": "DeepSeek V3.2",
        "resolved_model_id": "deepseek-chat",
        "scored_file": "deepseek_v3-2_scored_episodes.csv",
    },
    {
        "model_display": "Gemma 4",
        "resolved_model_id": "google/gemma-4-31B-it",
        "scored_file": "gemma_4_scored_episodes.csv",
    },
)

STATIC_CSVS = (
    "final_table3_model_caveats.csv",
    "final_table6_coding_probe.csv",
    "final_table7_mitigation.csv",
    "final_compute_appendix_seven_model.csv",
)


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _format_pct(count: int, total: int) -> str:
    return f"{(count / total * 100):.1f}%" if total else "0.0%"


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _scored_rows_for_model(spec: dict[str, str]) -> list[dict[str, str]]:
    path = SCORED_OUTPUT_DIR / spec["scored_file"]
    rows = _load_csv_rows(path)
    if len(rows) != 840:
        raise ValueError(f"{path} has {len(rows)} rows; expected 840")

    resolved_models = {row.get("resolved_model", "") for row in rows}
    resolved_models.discard("")
    if resolved_models != {spec["resolved_model_id"]}:
        raise ValueError(f"{path} resolved_model set is {sorted(resolved_models)}")

    if not all(_truthy(row.get("scored")) for row in rows):
        raise ValueError(f"{path} contains unscored rows")

    return rows


def _fully_scored_pairs(rows: list[dict[str, str]]) -> int:
    rows_by_pair: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_pair[row["pair_id"]].append(row)
    return sum(
        len(pair_rows) == 2 and all(_truthy(row.get("scored")) for row in pair_rows)
        for pair_rows in rows_by_pair.values()
    )


def _mean_metric(rows: list[dict[str, str]], metric: str) -> float:
    return round(statistics.fmean(_safe_float(row.get(metric)) for row in rows), 4)


def _refusal_count(rows: list[dict[str, str]]) -> int:
    return sum(str(row.get("tradeoff_mode", "")).strip() == "refused_misaligned_pressure" for row in rows)


def _refusal_rate(rows: list[dict[str, str]]) -> float:
    return round(_refusal_count(rows) / len(rows), 4) if rows else 0.0


def _atc_lt_one_count(rows: list[dict[str, str]]) -> int:
    return sum(_safe_float(row.get("ATC")) < 1.0 for row in rows)


def _failure_counts_text(rows: list[dict[str, str]]) -> str:
    counts = Counter(row.get("status", "") or "unknown" for row in rows)
    return "|".join(f"{status}={count}" for status, count in sorted(counts.items()))


def _parse_repair_note(rows: list[dict[str, str]]) -> str:
    repair_counts = [int(_safe_float(row.get("parse_repair_count"))) for row in rows]
    episodes_with_repairs = sum(count > 0 for count in repair_counts)
    total_repairs = sum(repair_counts)
    return f"{episodes_with_repairs}/{len(rows)} episodes required parse repair ({total_repairs} total repairs)"


def _stringify(row: dict[str, Any]) -> dict[str, str]:
    return {key: str(value) for key, value in row.items()}


def _assert_rows_match_locked(
    generated_rows: list[dict[str, Any]],
    locked_rows: list[dict[str, str]],
    key_fields: tuple[str, ...],
    label: str,
) -> None:
    generated = {_row_key(row, key_fields): _stringify(row) for row in generated_rows}
    locked = {_row_key(row, key_fields): dict(row) for row in locked_rows}
    if set(generated) != set(locked):
        raise ValueError(
            f"{label} key mismatch: generated-only={sorted(set(generated) - set(locked))}, "
            f"locked-only={sorted(set(locked) - set(generated))}"
        )

    for key in sorted(generated):
        for field, value in generated[key].items():
            locked_value = locked[key].get(field)
            if locked_value != value:
                raise ValueError(f"{label} mismatch for {key} field {field}: {value!r} != {locked_value!r}")


def _row_key(row: dict[str, Any], key_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row[field]) for field in key_fields)


def build_seven_model_results_rows() -> list[dict[str, Any]]:
    locked_rows = _load_csv_rows(OUTPUT_DIR / "final_table3_seven_model_results.csv")
    locked_by_model = {row["model_display"]: row for row in locked_rows}
    generated_rows: list[dict[str, Any]] = []

    for spec in MODEL_SPECS:
        rows = _scored_rows_for_model(spec)
        locked = locked_by_model[spec["model_display"]]
        generated: dict[str, Any] = {
            "model_display": spec["model_display"],
            "resolved_model_id": spec["resolved_model_id"],
            "final_status": locked["final_status"],
            "scored_episodes": len(rows),
            "fully_scored_pairs": _fully_scored_pairs(rows),
            "ATC_mean": _mean_metric(rows, "ATC"),
            "IVR_mean": _mean_metric(rows, "IVR"),
            "MGR_mean": _mean_metric(rows, "MGR"),
            "UPR_integrity_mean": _mean_metric(rows, "UPR_integrity"),
            "AEOR_mean": _mean_metric(rows, "AEOR"),
            "PSD_mean": _mean_metric(rows, "PSD"),
            "CDR_mean": _mean_metric(rows, "CDR"),
            "refused_misaligned_pressure_rate": _refusal_rate(rows),
            "failure_counts": _failure_counts_text(rows),
            "total_tokens": sum(int(_safe_float(row.get("token_total"))) for row in rows),
            "p95_latency_seconds_or_range": locked["p95_latency_seconds_or_range"],
            "parse_repair_note": _parse_repair_note(rows),
            "backup_restore_note": locked["backup_restore_note"],
            "manuscript_caveat": locked["manuscript_caveat"],
        }
        generated_rows.append(generated)

    _assert_rows_match_locked(
        generated_rows,
        locked_rows,
        ("model_display",),
        "final_table3_seven_model_results.csv",
    )
    return generated_rows


def build_refusal_partial_rows() -> list[dict[str, Any]]:
    locked_rows = _load_csv_rows(OUTPUT_DIR / "final_table4_refusal_partial.csv")
    generated_rows: list[dict[str, Any]] = []

    for spec in MODEL_SPECS:
        rows = _scored_rows_for_model(spec)
        refused = _refusal_count(rows)
        atc_lt_one = _atc_lt_one_count(rows)
        generated_rows.append(
            {
                "model": spec["model_display"],
                "refused_misaligned_count": refused,
                "refused_misaligned_total": len(rows),
                "refused_misaligned_pct": _format_pct(refused, len(rows)),
                "atc_lt_1_count": atc_lt_one,
                "atc_lt_1_total": len(rows),
                "atc_lt_1_pct": _format_pct(atc_lt_one, len(rows)),
            }
        )

    _assert_rows_match_locked(
        generated_rows,
        locked_rows,
        ("model",),
        "final_table4_refusal_partial.csv",
    )
    return generated_rows


def build_condition_breakdown_rows() -> list[dict[str, Any]]:
    locked_rows = _load_csv_rows(OUTPUT_DIR / "final_table5_condition_breakdown.csv")
    generated_rows: list[dict[str, Any]] = []

    for spec in MODEL_SPECS:
        rows = _scored_rows_for_model(spec)
        groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[(row["selection_group"], row["condition"])].append(row)

        for (selection_group, condition), group_rows in sorted(groups.items()):
            generated: dict[str, Any] = {
                "model_display": spec["model_display"],
                "resolved_model_id": spec["resolved_model_id"],
                "selection_group": selection_group,
                "condition": condition,
                "episode_count": len(group_rows),
                "scored_episode_count": sum(_truthy(row.get("scored")) for row in group_rows),
                "success_count": sum(row.get("status") == "success" for row in group_rows),
                "max_call_termination_count": sum(row.get("status") == "max_call_termination" for row in group_rows),
            }
            for metric in TABLE_METRICS:
                generated[metric] = _mean_metric(group_rows, metric)
            generated["refused_misaligned_pressure_rate"] = _refusal_rate(group_rows)
            generated_rows.append(generated)

    _assert_rows_match_locked(
        generated_rows,
        locked_rows,
        ("model_display", "selection_group", "condition"),
        "final_table5_condition_breakdown.csv",
    )
    return generated_rows


def build_source_inventory_rows() -> list[dict[str, Any]]:
    return [
        {
            "artifact_path": "docs/paper/final_table3_seven_model_results.csv",
            "artifact_role": "main seven-model results table",
            "status": "current",
            "scope_note": "fixed seven-model benchmark roster",
            "supporting_sources": (
                "data/scored_outputs/per_episode/*_scored_episodes.csv; "
                "data/manifests/subsets/v2_full_run_manifest.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table3_model_caveats.csv",
            "artifact_role": "model provenance/caveat table",
            "status": "current",
            "scope_note": "submitted model identities and provenance notes",
            "supporting_sources": (
                "docs/paper/model_panel.md; "
                "data/scored_outputs/per_episode/*_scored_episodes.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table4_refusal_partial.csv",
            "artifact_role": "refusal and partial-compliance table",
            "status": "current",
            "scope_note": "refusal/partial summaries from locked scored outputs",
            "supporting_sources": "data/scored_outputs/per_episode/*_scored_episodes.csv",
        },
        {
            "artifact_path": "docs/paper/final_table5_condition_breakdown.csv",
            "artifact_role": "condition breakdown table",
            "status": "current",
            "scope_note": "descriptive seven-model per-condition metrics",
            "supporting_sources": (
                "data/scored_outputs/per_episode/*_scored_episodes.csv; "
                "data/manifests/v2_manifest.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_table6_coding_probe.csv",
            "artifact_role": "coding probe table",
            "status": "current",
            "scope_note": "bounded fixed-bank 15-question auxiliary probe",
            "supporting_sources": "docs/paper/final_table6_coding_probe.csv",
        },
        {
            "artifact_path": "docs/paper/final_table7_mitigation.csv",
            "artifact_role": "structural mitigation table",
            "status": "current",
            "scope_note": "bounded four-model mitigation slice",
            "supporting_sources": (
                "docs/paper/final_table7_mitigation.csv; "
                "data/manifests/subsets/v2_mitigation_compliance_gate_background_manifest.csv"
            ),
        },
        {
            "artifact_path": "docs/paper/final_compute_appendix_seven_model.csv",
            "artifact_role": "compute/provenance appendix",
            "status": "current",
            "scope_note": "seven-model token, latency, parse, and runtime summary",
            "supporting_sources": (
                "docs/paper/final_compute_appendix_seven_model.csv; "
                "docs/paper/model_panel.md"
            ),
        },
        {
            "artifact_path": "docs/validation/kappa_tables.csv",
            "artifact_role": "validation agreement table",
            "status": "current",
            "scope_note": "expert validation agreement summary",
            "supporting_sources": (
                "docs/validation/validation_results.md; "
                "docs/validation/validation_summary_120.csv"
            ),
        },
        {
            "artifact_path": "docs/validation/validation_summary_120.csv",
            "artifact_role": "validation label summary",
            "status": "current",
            "scope_note": "120 validation episodes and majority labels",
            "supporting_sources": (
                "docs/validation/validation_results.md; "
                "docs/validation/q2_dissent_adjudications.csv"
            ),
        },
    ]


def copy_static_csvs(output_dir: Path) -> None:
    if output_dir.resolve() == OUTPUT_DIR.resolve():
        return
    for file_name in STATIC_CSVS:
        rows = _load_csv_rows(OUTPUT_DIR / file_name)
        _write_csv(output_dir / file_name, rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build and validate the submitted paper packet from bundled "
            "per-episode scored outputs. This path is cold-clone safe and does "
            "not require provider-run restore roots."
        )
    )
    parser.add_argument(
        "--output-root",
        default=str(OUTPUT_DIR),
        help="Output directory for materialized CSVs.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_root)

    seven_model_rows = build_seven_model_results_rows()
    refusal_rows = build_refusal_partial_rows()
    condition_rows = build_condition_breakdown_rows()
    inventory_rows = build_source_inventory_rows()

    _write_csv(output_dir / "final_table3_seven_model_results.csv", seven_model_rows)
    _write_markdown_table(
        output_dir / "final_table3_seven_model_results.md",
        "Final Table 4: Seven-Model Results",
        "Current seven-model results table validated from bundled per-episode scored outputs.",
        seven_model_rows,
    )

    _write_csv(output_dir / "final_table4_refusal_partial.csv", refusal_rows)

    _write_csv(output_dir / "final_table5_condition_breakdown.csv", condition_rows)
    _write_markdown_table(
        output_dir / "final_table5_condition_breakdown.md",
        "Final Table 6: Seven-Model Condition Breakdown",
        "Descriptive per-model condition breakdown validated from bundled per-episode scored outputs.",
        condition_rows,
    )

    copy_static_csvs(output_dir)

    _write_csv(output_dir / "final_supported_source_inventory.csv", inventory_rows)
    _write_markdown_table(
        output_dir / "final_supported_source_inventory.md",
        "Final Supported Source Inventory",
        "Current paper-facing source artifacts for the submitted seven-model packet.",
        inventory_rows,
    )


if __name__ == "__main__":
    main()
