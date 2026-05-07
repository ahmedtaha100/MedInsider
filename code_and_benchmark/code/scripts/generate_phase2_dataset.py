import argparse
import json
from pathlib import Path

from medinsider.fhir.paired_scenario import generate_v2_dataset


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="scenarios/phase2")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir

    summary = generate_v2_dataset(str(output_dir), seed=args.seed)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
