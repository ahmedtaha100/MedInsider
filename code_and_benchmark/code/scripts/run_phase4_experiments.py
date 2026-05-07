"""LEGACY experiment-oriented wrapper.

This script is kept for backward compatibility but is not the authoritative
surface for real v2/FHIR benchmark runs. Use scripts/run_phase4_v2.py instead.
"""

import argparse
import json
from pathlib import Path

from medinsider.phase4_v2_experiments import run_judge_pipeline, run_phase4_experiments


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--output-dir", default="experiments/phase4/results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-scenarios", type=int, default=None)
    parser.add_argument("--run-judge-pipeline", action="store_true")
    parser.add_argument("--judge-output-dir", default=None)
    parser.add_argument("--calibration-fraction", type=float, default=0.1)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir)

    if not dataset_dir.is_absolute():
        dataset_dir = project_root / dataset_dir
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    summary = run_phase4_experiments(
        dataset_dir=str(dataset_dir),
        output_dir=str(output_dir),
        seed=args.seed,
        max_scenarios=args.max_scenarios,
    )
    if args.run_judge_pipeline:
        judge_output_dir = Path(args.judge_output_dir) if args.judge_output_dir else output_dir
        if not judge_output_dir.is_absolute():
            judge_output_dir = project_root / judge_output_dir
        summary["judge_pipeline"] = run_judge_pipeline(
            episode_csv=summary["episode_scores_csv"],
            output_dir=str(judge_output_dir),
            calibration_fraction=args.calibration_fraction,
            seed=args.seed,
        )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
