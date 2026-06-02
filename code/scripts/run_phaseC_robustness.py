import argparse
import json

from medinsider.phaseC_robustness import run_phaseC_pipeline_cli


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase C pressure realism and robustness pipeline")
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--experiments-dir", default="experiments/robustness")
    parser.add_argument("--docs-dir", default="docs")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-paraphrase-scenarios", type=int, default=180)
    args = parser.parse_args()

    summary = run_phaseC_pipeline_cli(
        dataset_dir=args.dataset_dir,
        experiments_dir=args.experiments_dir,
        docs_dir=args.docs_dir,
        seed=args.seed,
        max_paraphrase_scenarios=args.max_paraphrase_scenarios,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
