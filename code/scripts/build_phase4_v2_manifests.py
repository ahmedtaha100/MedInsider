#!/usr/bin/env python

import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = PROJECT_ROOT / "scenarios" / "phase2_v2" / "generated"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SUBSETS_DIR = ARTIFACTS_DIR / "subsets"

FAMILIES = [
    "coding_and_billing_pressure",
    "quality_metric_pressure",
    "readmission_pressure",
    "safety_event_pressure",
    "throughput_pressure",
]

SMOKE_SELECTIONS = [
    (
        "coding_and_billing_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "scripted_smoke_pair",
    ),
]

PILOT_SELECTIONS = [
    (
        "coding_and_billing_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "pilot_background_pair",
    ),
    (
        "quality_metric_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "pilot_background_pair",
    ),
    (
        "readmission_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "pilot_background_pair",
    ),
    (
        "safety_event_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "pilot_background_pair",
    ),
    (
        "throughput_pressure",
        "background_pressure",
        "000",
        "background_pressure_vs_neutral",
        "pilot_background_pair",
    ),
    ("coding_and_billing_pressure", "sham_placebo", "000", "sham_placebo_vs_neutral", "pilot_sham_pair"),
    ("quality_metric_pressure", "sham_placebo", "000", "sham_placebo_vs_neutral", "pilot_sham_pair"),
    ("readmission_pressure", "sham_placebo", "000", "sham_placebo_vs_neutral", "pilot_sham_pair"),
    ("safety_event_pressure", "sham_placebo", "000", "sham_placebo_vs_neutral", "pilot_sham_pair"),
    ("throughput_pressure", "sham_placebo", "000", "sham_placebo_vs_neutral", "pilot_sham_pair"),
    ("coding_and_billing_pressure", "reverse_incentive", "000", "aligned_vs_neutral", "pilot_aligned_pair"),
    ("quality_metric_pressure", "honesty_system_prompt", "000", "aligned_vs_neutral", "pilot_aligned_pair"),
    ("readmission_pressure", "reverse_incentive", "000", "aligned_vs_neutral", "pilot_aligned_pair"),
    ("safety_event_pressure", "honesty_system_prompt", "000", "aligned_vs_neutral", "pilot_aligned_pair"),
    ("throughput_pressure", "reverse_incentive", "000", "aligned_vs_neutral", "pilot_aligned_pair"),
]

LARGER_PILOT_SELECTIONS = (
    [
        (family, "background_pressure", sample_idx, "background_pressure_vs_neutral", "larger_pilot_background_pair")
        for sample_idx in ("000", "001", "002")
        for family in FAMILIES
    ]
    + [
        (family, "sham_placebo", sample_idx, "sham_placebo_vs_neutral", "larger_pilot_sham_pair")
        for sample_idx in ("000", "001", "002")
        for family in FAMILIES
    ]
    + [
        (family, "reverse_incentive", sample_idx, "aligned_vs_neutral", "larger_pilot_reverse_pair")
        for sample_idx in ("000", "001", "002")
        for family in FAMILIES
    ]
    + [
        (family, "honesty_system_prompt", sample_idx, "aligned_vs_neutral", "larger_pilot_honesty_pair")
        for sample_idx in ("000", "001", "002")
        for family in FAMILIES
    ]
)


def _load_scenarios() -> list[dict]:
    scenarios = []
    for path in sorted(GENERATED_DIR.glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        scenario["_path"] = path
        pair_id = str(scenario.get("metadata", {}).get("pair_id", ""))
        scenario["_sample_idx"] = pair_id.rsplit("-", 1)[-1] if pair_id else ""
        scenarios.append(scenario)
    return scenarios


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _dataset_rows(scenarios: list[dict]) -> list[dict]:
    rows = []
    for scenario in scenarios:
        metadata = scenario.get("metadata", {})
        rows.append(
            {
                "episode_id": scenario["episode_id"],
                "scenario_family": scenario["scenario_family"],
                "condition": scenario["condition"],
                "alignment_label": scenario["alignment_label"],
                "twin_role": metadata.get("twin_role", ""),
                "pair_id": metadata.get("pair_id", ""),
                "pressure_condition": metadata.get("pressure_condition", ""),
                "episode_length_min": scenario.get("episode_length_min", ""),
                "episode_length_max": scenario.get("episode_length_max", ""),
                "risk_tier": metadata.get("risk_tier", ""),
                "path": (Path("scenarios") / "phase2_v2" / "generated" / scenario["_path"].name).as_posix(),
            }
        )
    return rows


def _selection_rows(scenarios: list[dict], specs: list[tuple[str, str, str, str, str]]) -> list[dict]:
    index: dict[tuple[str, str, str, str], dict] = {}
    for scenario in scenarios:
        key = (
            scenario["scenario_family"],
            str(scenario.get("metadata", {}).get("pressure_condition", "")),
            str(scenario.get("_sample_idx", "")),
            str(scenario.get("metadata", {}).get("twin_role", "")),
        )
        if key in index:
            existing = index[key]
            raise ValueError(
                "selection_manifest_source_duplicate:"
                f"family={key[0]}:pressure_condition={key[1]}:"
                f"sample_idx={key[2]}:twin_role={key[3]}:"
                f"episode_ids={existing['episode_id']}|{scenario['episode_id']}"
            )
        index[key] = scenario
    rows: list[dict] = []
    for family, pressure_condition, sample_idx, selection_group, selection_reason in specs:
        for twin_role in ("neutral", "pressure"):
            key = (family, pressure_condition, sample_idx, twin_role)
            if key not in index:
                raise ValueError(
                    "selection_manifest_source_missing:"
                    + f"family={family}:pressure_condition={pressure_condition}:"
                    + f"sample_idx={sample_idx}:twin_role={twin_role}"
                )
            scenario = index[key]
            rows.append(
                {
                    "episode_id": scenario["episode_id"],
                    "pair_id": scenario["metadata"]["pair_id"],
                    "scenario_family": scenario["scenario_family"],
                    "condition": scenario["condition"],
                    "twin_role": scenario["metadata"]["twin_role"],
                    "pressure_condition": scenario["metadata"]["pressure_condition"],
                    "selection_group": selection_group,
                    "selection_reason": selection_reason,
                }
            )
    return rows


def main() -> None:
    scenarios = _load_scenarios()
    _write_csv(
        ARTIFACTS_DIR / "v2_manifest.csv",
        _dataset_rows(scenarios),
        [
            "episode_id",
            "scenario_family",
            "condition",
            "alignment_label",
            "twin_role",
            "pair_id",
            "pressure_condition",
            "episode_length_min",
            "episode_length_max",
            "risk_tier",
            "path",
        ],
    )
    _write_csv(
        SUBSETS_DIR / "v2_smoke_manifest.csv",
        _selection_rows(scenarios, SMOKE_SELECTIONS),
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
    _write_csv(
        SUBSETS_DIR / "v2_small_pilot_manifest.csv",
        _selection_rows(scenarios, PILOT_SELECTIONS),
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
    _write_csv(
        SUBSETS_DIR / "v2_larger_pilot_manifest.csv",
        _selection_rows(scenarios, LARGER_PILOT_SELECTIONS),
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


if __name__ == "__main__":
    main()
