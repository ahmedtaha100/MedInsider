import argparse
import json
from pathlib import Path

from medinsider.phase5_analysis import run_phase5_analysis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase4-results-dir", default="experiments/phase4/results")
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--output-dir", default="experiments/phase5")
    parser.add_argument("--baseline", default="model_panel")
    parser.add_argument("--robustness-subset-size", type=int, default=150)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    phase4_results_dir = Path(args.phase4_results_dir)
    dataset_dir = Path(args.dataset_dir)
    output_dir = Path(args.output_dir)

    if not phase4_results_dir.is_absolute():
        phase4_results_dir = project_root / phase4_results_dir
    if not dataset_dir.is_absolute():
        dataset_dir = project_root / dataset_dir
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    summary = run_phase5_analysis(
        phase4_results_dir=str(phase4_results_dir),
        dataset_dir=str(dataset_dir),
        output_dir=str(output_dir),
        baseline=args.baseline,
        robustness_subset_size=args.robustness_subset_size,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
