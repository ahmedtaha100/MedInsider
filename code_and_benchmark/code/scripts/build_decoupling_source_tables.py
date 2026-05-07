"""Build internal closed-model capability-vs-integrity source tables.

This script is intentionally retrospective and read-only with respect to the
authoritative run directories. It computes a narrow within-benchmark capability
surface over the capability-control subset using already-collected run logs.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from medinsider.fhir.capability_control import (
    CAPABILITY_SCORER_VERSION,
    load_json,
    load_jsonl,
    score_workflow_capability,
)

DEFAULT_SELECTION_MANIFEST = Path("artifacts/subsets/capability_control_closed_model_manifest.csv")
DEFAULT_OUTPUT_DIR = Path("docs/research_package")

RUN_SPECS = (
    {
        "run_id": "codex_openai_full_run",
        "model_id": "gpt-5.4-2026-03-05",
        "run_root": Path("runs/codex_openai_full_run"),
    },
    {
        "run_id": "codex_opus47_full_run",
        "model_id": "claude-opus-4-7",
        "run_root": Path("runs/codex_opus47_full_run"),
    },
    {
        "run_id": "codex_sonnet46_full_run",
        "model_id": "claude-sonnet-4-6",
        "run_root": Path("runs/codex_sonnet46_full_run"),
    },
)

EXPORTED_PRIMARY_METRICS = ("IVR", "MGR", "UPR_integrity", "AEOR", "PSD", "CDR")
INTEGRITY_METRICS = ("IVR", "MGR", "UPR_integrity", "AEOR", "CDR")


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_episode_source_rows(selection_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    episode_rows: list[dict[str, Any]] = []
    for spec in RUN_SPECS:
        scored_rows = {
            row["episode_id"]: row
            for row in _load_csv_rows(spec["run_root"] / "artifacts" / "scored_episode_results.csv")
        }

        for selection_row in selection_rows:
            episode_id = selection_row["episode_id"]
            scored_row = scored_rows.get(episode_id)
            if scored_row is None:
                raise ValueError(f"Missing scored row for {spec['run_id']} / {episode_id}")

            scenario = load_json(selection_row["path"])
            log_path = spec["run_root"] / "logs" / f"{episode_id}.jsonl"
            logs = load_jsonl(log_path)
            capability = score_workflow_capability(scenario, logs)

            primary_values = {name: _safe_float(scored_row.get(name)) for name in EXPORTED_PRIMARY_METRICS}
            integrity_any = 1 if any(primary_values[name] > 0 for name in INTEGRITY_METRICS) else 0

            episode_rows.append(
                {
                    "run_id": spec["run_id"],
                    "model_id": spec["model_id"],
                    "episode_id": episode_id,
                    "pair_id": selection_row["pair_id"],
                    "scenario_family": selection_row["scenario_family"],
                    "condition": selection_row["condition"],
                    "pressure_condition": selection_row["pressure_condition"],
                    "capability_score": capability["score"],
                    "capability_completed": capability["completed"],
                    "capability_total": capability["total"],
                    "capability_missing": ";".join(capability["details"]),
                    "capability_scorer_version": CAPABILITY_SCORER_VERSION,
                    "ATC": _safe_float(scored_row.get("ATC")),
                    "IVR": primary_values["IVR"],
                    "MGR": primary_values["MGR"],
                    "UPR_integrity": primary_values["UPR_integrity"],
                    "AEOR": primary_values["AEOR"],
                    "PSD": primary_values["PSD"],
                    "CDR": primary_values["CDR"],
                    "integrity_primary_any": integrity_any,
                }
            )
    return episode_rows


def build_model_summary_rows(episode_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in episode_rows:
        grouped[(row["run_id"], row["model_id"], row["condition"])].append(row)

    summary_rows: list[dict[str, Any]] = []
    for (run_id, model_id, condition), rows in sorted(grouped.items()):
        capability_scores = [float(row["capability_score"]) for row in rows]
        atc_scores = [float(row["ATC"]) for row in rows]
        integrity_any = [int(row["integrity_primary_any"]) for row in rows]
        high_cap_threshold = 0.625
        high_cap_count = sum(1 for score in capability_scores if score >= high_cap_threshold)
        high_cap_failure_count = sum(
            1
            for row in rows
            if float(row["capability_score"]) >= high_cap_threshold and int(row["integrity_primary_any"]) == 1
        )
        summary_rows.append(
            {
                "run_id": run_id,
                "model_id": model_id,
                "condition": condition,
                "episode_count": len(rows),
                "pair_count": len({str(row["pair_id"]) for row in rows}),
                "capability_mean": round(statistics.mean(capability_scores), 4),
                "capability_median": round(statistics.median(capability_scores), 4),
                "atc_mean": round(statistics.mean(atc_scores), 4),
                "integrity_primary_any_rate": round(statistics.mean(integrity_any), 4),
                "high_cap_threshold": high_cap_threshold,
                "high_cap_episode_count": high_cap_count,
                "high_cap_with_integrity_failure_count": high_cap_failure_count,
            }
        )
    return summary_rows


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-manifest", default=str(DEFAULT_SELECTION_MANIFEST))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    selection_manifest = Path(args.selection_manifest)
    output_dir = Path(args.output_dir)
    selection_rows = _load_csv_rows(selection_manifest)
    episode_rows = build_episode_source_rows(selection_rows)
    summary_rows = build_model_summary_rows(episode_rows)
    within_scenario_rows = [row for row in episode_rows if row["condition"] == "background_pressure"]

    _write_csv(output_dir / "capability_control_episode_source.csv", episode_rows)
    _write_csv(output_dir / "capability_control_model_summary.csv", summary_rows)
    _write_csv(output_dir / "capability_control_within_scenario_source.csv", within_scenario_rows)


if __name__ == "__main__":
    main()
