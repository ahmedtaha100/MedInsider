#!/usr/bin/env python
"""Generate the v2 paired-twin scenario corpus.

Usage:
    PYTHONPATH=src python scripts/generate_v2_paired_dataset.py [--output-dir DIR] [--seed N]

Defaults:
    --output-dir scenarios/phase2
    --seed 42
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from medinsider.fhir.paired_scenario import generate_v2_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate v2 paired-twin scenario corpus")
    parser.add_argument("--output-dir", default="scenarios/phase2", help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    print(f"Generating v2 paired-twin dataset to {args.output_dir} (seed={args.seed})...")
    summary = generate_v2_dataset(args.output_dir, seed=args.seed)

    print(f"Total scenarios: {summary['total_scenarios']}")
    print(f"Total pairs: {summary['total_pairs']}")
    print(f"Neutral twins: {summary['neutral_count']}")
    print(f"Pressure twins: {summary['pressure_count']}")
    print(f"Families: {summary['families']}")
    print(f"Conditions: {summary['conditions']}")
    print(f"Manifest: {summary['manifest_path']}")
    print("Done.")


if __name__ == "__main__":
    main()
