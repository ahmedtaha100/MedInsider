import json
from copy import deepcopy
from pathlib import Path
from typing import Any

INBOX_PRESSURE_CONDITIONS = {"background_pressure", "background_pressure_minimal"}


def load_scenario(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_for_pair_compare(scenario: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(scenario)
    normalized["episode_id"] = "__pair_episode__"
    normalized["condition"] = "__pair_condition__"
    normalized["alignment_label"] = "__pair_alignment__"
    normalized["incentive_framing"] = "__pair_framing__"
    normalized["system_prompt"] = "__pair_system_prompt__"
    metadata = normalized.setdefault("metadata", {})
    metadata["twin_role"] = "__pair_twin_role__"
    patient_state = normalized.setdefault("patient_state", {})
    patient_state.pop("inbox_messages", None)
    return normalized


def validate_pair_integrity(neutral: dict[str, Any], pressure: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    neutral_meta = neutral.get("metadata", {})
    pressure_meta = pressure.get("metadata", {})
    pair_id = str(neutral_meta.get("pair_id", "")).strip()
    pressure_pair_id = str(pressure_meta.get("pair_id", "")).strip()
    if not pair_id or pair_id != pressure_pair_id:
        errors.append("pair_id_mismatch")

    if neutral.get("condition") != "neutral":
        errors.append(f"neutral_condition_invalid:{neutral.get('condition', '')}")
    expected_pressure_condition = str(pressure_meta.get("pressure_condition", "")).strip()
    if not expected_pressure_condition:
        errors.append("pressure_condition_missing")
    elif pressure.get("condition") != expected_pressure_condition:
        errors.append(f"pressure_condition_mismatch:{pressure.get('condition', '')}:{expected_pressure_condition}")

    if neutral_meta.get("twin_role") != "neutral":
        errors.append(f"neutral_twin_role_invalid:{neutral_meta.get('twin_role', '')}")
    if pressure_meta.get("twin_role") != "pressure":
        errors.append(f"pressure_twin_role_invalid:{pressure_meta.get('twin_role', '')}")

    if neutral.get("scenario_family") != pressure.get("scenario_family"):
        errors.append("scenario_family_mismatch")
    if neutral.get("reference_actions") != pressure.get("reference_actions"):
        errors.append("reference_actions_mismatch")
    if neutral.get("ground_truth_constraints") != pressure.get("ground_truth_constraints"):
        errors.append("ground_truth_constraints_mismatch")

    shared_fields = (
        "case_skeleton",
        "care_plan",
        "tempting_misaligned_shortcut",
        "episode_length_min",
        "episode_length_max",
    )
    for field in shared_fields:
        if neutral.get(field) != pressure.get(field):
            errors.append(f"shared_field_mismatch:{field}")

    neutral_inbox = list(neutral.get("patient_state", {}).get("inbox_messages", []))
    pressure_inbox = list(pressure.get("patient_state", {}).get("inbox_messages", []))
    pressure_condition = str(pressure.get("condition", "")).strip()

    if pressure_condition in INBOX_PRESSURE_CONDITIONS:
        if neutral_inbox:
            errors.append("neutral_inbox_not_empty")
        if not pressure_inbox:
            errors.append("pressure_inbox_missing")
    else:
        if neutral_inbox:
            errors.append("neutral_inbox_not_empty")
        if pressure_inbox:
            errors.append("pressure_inbox_unexpected")

    if _normalize_for_pair_compare(neutral) != _normalize_for_pair_compare(pressure):
        errors.append("unexpected_payload_difference")

    return errors


def validate_pair_group(scenarios: list[dict[str, Any]]) -> list[str]:
    if len(scenarios) != 2:
        return [f"pair_group_size_invalid:{len(scenarios)}"]

    by_role = {scenario.get("metadata", {}).get("twin_role"): scenario for scenario in scenarios}
    neutral = by_role.get("neutral")
    pressure = by_role.get("pressure")
    if neutral is None or pressure is None:
        return ["pair_roles_incomplete"]
    return validate_pair_integrity(neutral, pressure)


def validate_selected_pairs(
    selected_scenarios: list[dict[str, Any]],
    require_complete_pairs: bool = True,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for scenario in selected_scenarios:
        pair_id = str(scenario.get("metadata", {}).get("pair_id", "")).strip()
        key = pair_id or str(scenario.get("episode_id", "")).strip()
        grouped.setdefault(key, []).append(scenario)

    errors: list[str] = []
    validated_pairs = 0
    for pair_id, scenarios in sorted(grouped.items()):
        if len(scenarios) == 1 and not require_complete_pairs:
            continue
        pair_errors = validate_pair_group(scenarios)
        if pair_errors:
            for error in pair_errors:
                errors.append(f"{pair_id}:{error}")
            continue
        validated_pairs += 1

    return {
        "ok": not errors,
        "validated_pairs": validated_pairs,
        "group_count": len(grouped),
        "errors": errors,
    }
