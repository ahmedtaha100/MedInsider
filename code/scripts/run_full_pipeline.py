"""Research pipeline helper.

This script remains available for legacy multi-phase reproduction work, but the
authoritative executable path for real v2/FHIR pilot runs is
scripts/run_phase4_v2.py with artifacts/v2_manifest.csv.
"""

import argparse
import json
from pathlib import Path

from medinsider.fhir.paired_scenario import generate_v2_dataset
from medinsider.fhir.review_sampling import generate_clinician_review_sample
from medinsider.logger import ActionLogger
from medinsider.phase2_validation import validate_dataset
from medinsider.phase4_v2_experiments import run_judge_pipeline, run_phase4_experiments
from medinsider.phase5_analysis import run_phase5_analysis
from medinsider.runner import ScenarioRunner
from medinsider.scoring import score_episode


def _run_phase1(project_root: Path) -> dict:
    scenario_path = project_root / "scenarios/phase1/billing_conflict_episode.json"
    log_path = project_root / "logs/phase1_action_log.jsonl"
    summary_path = project_root / "logs/phase1_summary.json"

    logger = ActionLogger(str(log_path))
    runner = ScenarioRunner(logger)
    summary = runner.run(scenario_path=str(scenario_path), agent_type="scripted")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return {
        "scenario": str(scenario_path),
        "log_path": str(log_path),
        "summary_path": str(summary_path),
        "result": summary,
    }


def _run_phase2(project_root: Path, seed: int) -> dict:
    dataset_dir = project_root / "scenarios/phase2"
    generation = generate_v2_dataset(str(dataset_dir), seed=seed)
    validation = validate_dataset(str(dataset_dir))
    clinician = generate_clinician_review_sample(
        dataset_dir=str(dataset_dir),
        output_path=str(dataset_dir / "artifacts/clinician_review_sample.jsonl"),
        target_size=75,
        seed=seed,
    )
    return {
        "dataset_dir": str(dataset_dir),
        "generation": generation,
        "validation": validation,
        "clinician_review_sample": clinician,
    }


def _run_phase3(project_root: Path) -> dict:
    scenario_path = project_root / "scenarios/phase3/fixtures/demo_scenario.json"
    log_path = project_root / "scenarios/phase3/fixtures/demo_log.jsonl"
    output_path = project_root / "scenarios/phase3/fixtures/demo_score_output.json"

    scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    logs = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    score = score_episode(scenario, logs)
    output_path.write_text(json.dumps(score, indent=2), encoding="utf-8")
    return {
        "scenario_path": str(scenario_path),
        "log_path": str(log_path),
        "output_path": str(output_path),
        "score": score,
    }


def _run_phase4(project_root: Path, seed: int) -> dict:
    dataset_dir = project_root / "scenarios/phase2"
    output_dir = project_root / "experiments/phase4/results"
    experiments_summary = run_phase4_experiments(
        dataset_dir=str(dataset_dir),
        output_dir=str(output_dir),
        seed=seed,
        max_scenarios=None,
    )
    judge_summary = run_judge_pipeline(
        episode_csv=experiments_summary["episode_scores_csv"],
        output_dir=str(output_dir),
        seed=seed,
    )
    return {
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "summary": experiments_summary,
        "judge_pipeline": judge_summary,
    }


def _run_phase5(project_root: Path, seed: int) -> dict:
    summary = run_phase5_analysis(
        phase4_results_dir=str(project_root / "experiments/phase4/results"),
        dataset_dir=str(project_root / "scenarios/phase2"),
        output_dir=str(project_root / "experiments/phase5"),
        baseline="model_panel",
        robustness_subset_size=150,
        seed=seed,
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]

    summary = {
        "phase1": _run_phase1(project_root),
        "phase2": _run_phase2(project_root, args.seed),
        "phase3": _run_phase3(project_root),
        "phase4": _run_phase4(project_root, args.seed),
        "phase5": _run_phase5(project_root, args.seed),
    }

    output_path = project_root / "experiments/full_pipeline_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"summary_path": str(output_path)}, indent=2))


if __name__ == "__main__":
    main()
