import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from medinsider.fhir.paired_scenario import (
    ALIGNED_PRESSURE_CONDITIONS,
    CONDITIONS_V2,
    FAMILIES,
    PER_CELL,
    PRESSURE_CONDITIONS,
)

ALIGNMENTS = ["aligned", "conflict"]

REQUIRED_FIELDS = [
    "episode_id",
    "scenario_family",
    "condition",
    "alignment_label",
    "episode_length_min",
    "episode_length_max",
    "case_skeleton",
    "care_plan",
    "incentive_framing",
    "tempting_misaligned_shortcut",
    "ground_truth_constraints",
    "system_prompt",
    "patient_state",
]

REQUIRED_CONSTRAINT_FIELDS = [
    "falsification",
    "upcoding",
    "omission",
    "cherry_picking",
    "aligned_behavior",
    "prohibited_behavior",
    "expected_mode",
]


def _signature(scenario: dict[str, Any]) -> str:
    payload = {
        "scenario_family": scenario.get("scenario_family"),
        "condition": scenario.get("condition"),
        "alignment_label": scenario.get("alignment_label"),
        "case_skeleton": scenario.get("case_skeleton"),
        "care_plan": scenario.get("care_plan"),
        "incentive_framing": scenario.get("incentive_framing"),
        "tempting_misaligned_shortcut": scenario.get("tempting_misaligned_shortcut"),
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _expected_alignment(condition: str) -> str:
    if condition == "neutral":
        return "conflict"
    if condition in ALIGNED_PRESSURE_CONDITIONS:
        return "aligned"
    return "conflict"


def validate_dataset(dataset_dir: str) -> dict[str, Any]:
    root = Path(dataset_dir)
    generated_dir = root / "generated"
    artifacts_dir = root / "artifacts"
    scenarios = []
    errors: list[str] = []

    for path in sorted(generated_dir.glob("*.json")):
        try:
            scenario = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"json_decode_error:{path.name}:{exc}")
            continue
        scenarios.append((path, scenario))

    seen_episode_ids = set()
    seen_signatures = {}
    coverage = {family: {condition: 0 for condition in CONDITIONS_V2} for family in FAMILIES}

    for path, scenario in scenarios:
        missing_fields = [field for field in REQUIRED_FIELDS if field not in scenario]
        if missing_fields:
            errors.append(f"missing_fields:{path.name}:{','.join(missing_fields)}")
            continue

        episode_id = scenario["episode_id"]
        if episode_id in seen_episode_ids:
            errors.append(f"duplicate_episode_id:{episode_id}")
        seen_episode_ids.add(episode_id)

        family = scenario["scenario_family"]
        condition = scenario["condition"]
        alignment = scenario["alignment_label"]
        if family not in FAMILIES:
            errors.append(f"invalid_family:{path.name}:{family}")
        if condition not in CONDITIONS_V2:
            errors.append(f"invalid_condition:{path.name}:{condition}")
        if alignment not in ALIGNMENTS:
            errors.append(f"invalid_alignment:{path.name}:{alignment}")
        elif condition in CONDITIONS_V2 and alignment != _expected_alignment(condition):
            errors.append(f"unexpected_alignment:{path.name}:{condition}:{alignment}")

        twin_role = scenario.get("metadata", {}).get("twin_role")
        expected_twin_role = "neutral" if condition == "neutral" else "pressure"
        if twin_role is not None and twin_role != expected_twin_role:
            errors.append(f"unexpected_twin_role:{path.name}:{condition}:{twin_role}")

        min_calls = scenario["episode_length_min"]
        max_calls = scenario["episode_length_max"]
        if not isinstance(min_calls, int) or not isinstance(max_calls, int):
            errors.append(f"invalid_episode_bounds_type:{path.name}")
        elif min_calls < 6 or max_calls > 20 or min_calls > max_calls:
            errors.append(f"invalid_episode_bounds:{path.name}:{min_calls}:{max_calls}")

        constraints = scenario.get("ground_truth_constraints", {})
        missing_constraints = [field for field in REQUIRED_CONSTRAINT_FIELDS if field not in constraints]
        if missing_constraints:
            errors.append(f"missing_constraints:{path.name}:{','.join(missing_constraints)}")

        signature = _signature(scenario)
        if signature in seen_signatures:
            errors.append(f"duplicate_signature:{path.name}:{seen_signatures[signature]}")
        else:
            seen_signatures[signature] = path.name

        if family in coverage and condition in coverage[family]:
            coverage[family][condition] += 1

    expected_total = len(FAMILIES) * len(PRESSURE_CONDITIONS) * PER_CELL * 2
    actual_total = len(scenarios)
    if actual_total != expected_total:
        errors.append(f"invalid_total_count:expected_{expected_total}:actual_{actual_total}")

    expected_condition_counts = {"neutral": len(PRESSURE_CONDITIONS) * PER_CELL}
    expected_condition_counts.update({condition: PER_CELL for condition in PRESSURE_CONDITIONS})
    for family in FAMILIES:
        for condition in CONDITIONS_V2:
            observed = coverage[family][condition]
            expected = expected_condition_counts[condition]
            if observed != expected:
                errors.append(f"coverage_mismatch:{family}:{condition}:expected_{expected}:actual_{observed}")

    report = {
        "dataset_dir": str(root),
        "total_files": actual_total,
        "expected_total": expected_total,
        "error_count": len(errors),
        "errors": errors,
        "coverage": coverage,
        "status": "valid" if not errors else "invalid",
    }

    report_path = artifacts_dir / "phase2_validation_report.json"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    counts_path = artifacts_dir / "phase2_coverage_counts.csv"
    with counts_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario_family", "condition", "count"])
        for family in FAMILIES:
            for condition in CONDITIONS_V2:
                writer.writerow([family, condition, coverage[family][condition]])

    report["report_path"] = str(report_path)
    report["coverage_path"] = str(counts_path)
    return report
