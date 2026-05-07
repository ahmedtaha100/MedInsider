import argparse
import json
from pathlib import Path

from medinsider.phaseB_validation import (
    build_episode_labeling_package,
    build_scenario_realism_sample,
    generate_distribution_realism_audit,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Phase B validation assets.")
    parser.add_argument("--dataset-dir", default=".")
    parser.add_argument("--validation-dir", default="docs/validation")
    parser.add_argument("--design-dir", default="docs/design")
    parser.add_argument("--scenario-sample-size", type=int, default=200)
    parser.add_argument("--episode-sample-size", type=int, default=120)
    parser.add_argument("--double-label-size", type=int, default=40)
    parser.add_argument("--overwrite-logs", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    validation_dir = Path(args.validation_dir)
    design_dir = Path(args.design_dir)
    validation_dir.mkdir(parents=True, exist_ok=True)
    design_dir.mkdir(parents=True, exist_ok=True)

    realism_summary = build_scenario_realism_sample(
        dataset_dir=args.dataset_dir,
        output_csv=str(validation_dir / "scenario_realism_results.csv"),
        target_size=args.scenario_sample_size,
        seed=args.seed,
    )

    labeling_summary = build_episode_labeling_package(
        dataset_dir=args.dataset_dir,
        output_csv=str(validation_dir / "blinded_gold_label_set.csv"),
        admin_output_csv=str(validation_dir / "blinded_gold_label_admin.csv"),
        logs_dir=str(validation_dir / "episode_review_logs"),
        target_size=args.episode_sample_size,
        double_label_size=args.double_label_size,
        seed=args.seed,
        overwrite_logs=args.overwrite_logs,
    )

    realism_audit_summary = generate_distribution_realism_audit(
        dataset_dir=args.dataset_dir,
        output_markdown=str(design_dir / "distribution_realism_audit.md"),
        output_csv=str(validation_dir / "distribution_realism_counts.csv"),
    )

    summary = {
        "dataset_dir": args.dataset_dir,
        "scenario_sample": realism_summary,
        "episode_labeling": labeling_summary,
        "distribution_realism": realism_audit_summary,
    }

    summary_path = validation_dir / "phaseB_validation_assets_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
