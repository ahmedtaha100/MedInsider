import json
import random
from pathlib import Path

from medinsider.fhir.scenario_blueprints import FAMILIES


def generate_clinician_review_sample(
    dataset_dir: str,
    output_path: str,
    target_size: int = 75,
    seed: int = 42,
) -> dict:
    rng = random.Random(seed)
    generated_dir = Path(dataset_dir) / "generated"
    scenarios = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(generated_dir.glob("*.json"))]

    conflict_pressure = [
        scenario
        for scenario in scenarios
        if scenario.get("alignment_label") == "conflict" and scenario.get("metadata", {}).get("twin_role") == "pressure"
    ]
    priority = [
        scenario
        for scenario in conflict_pressure
        if scenario["scenario_family"] in {"coding_and_billing_pressure", "safety_event_pressure"}
    ]
    secondary = [scenario for scenario in conflict_pressure if scenario not in priority]

    rng.shuffle(priority)
    rng.shuffle(secondary)

    selected = priority[:target_size]
    if len(selected) < target_size:
        selected.extend(secondary[: target_size - len(selected)])

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for scenario in selected:
            record = {
                "episode_id": scenario["episode_id"],
                "scenario_family": scenario["scenario_family"],
                "condition": scenario["condition"],
                "alignment_label": scenario["alignment_label"],
                "pair_id": scenario.get("metadata", {}).get("pair_id"),
                "pressure_condition": scenario.get("metadata", {}).get("pressure_condition"),
                "risk_tier": scenario.get("metadata", {}).get("risk_tier"),
                "case_skeleton": scenario["case_skeleton"],
                "care_plan": scenario["care_plan"],
                "incentive_framing": scenario["incentive_framing"],
                "tempting_misaligned_shortcut": scenario["tempting_misaligned_shortcut"],
                "ground_truth_constraints": scenario["ground_truth_constraints"],
            }
            handle.write(json.dumps(record) + "\n")

    summary = {
        "target_size": target_size,
        "selected_size": len(selected),
        "output_path": str(output),
        "priority_family_counts": {
            family: sum(1 for scenario in selected if scenario["scenario_family"] == family) for family in FAMILIES
        },
    }
    summary_path = output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary
