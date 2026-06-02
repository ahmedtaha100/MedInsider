import argparse
import json
from pathlib import Path

from medinsider.fhir.review_sampling import generate_clinician_review_sample


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--output", default="scenarios/phase2/artifacts/clinician_review_sample.jsonl")
    parser.add_argument("--target-size", type=int, default=75)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = Path(args.dataset_dir)
    output = Path(args.output)

    if not dataset_dir.is_absolute():
        dataset_dir = project_root / dataset_dir
    if not output.is_absolute():
        output = project_root / output

    summary = generate_clinician_review_sample(
        dataset_dir=str(dataset_dir),
        output_path=str(output),
        target_size=args.target_size,
        seed=args.seed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
