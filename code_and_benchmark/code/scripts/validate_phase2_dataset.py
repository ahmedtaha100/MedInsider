import argparse
import json
from pathlib import Path

from medinsider.phase2_validation import validate_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    dataset_dir = Path(args.dataset_dir)
    if not dataset_dir.is_absolute():
        dataset_dir = project_root / dataset_dir

    report = validate_dataset(str(dataset_dir))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
