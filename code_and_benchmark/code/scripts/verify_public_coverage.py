#!/usr/bin/env python
"""Verify that the public subset covers all headline claims.

Usage:
    PYTHONPATH=src python scripts/verify_public_coverage.py [--scenarios-dir DIR]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from medinsider.fhir.splits import assign_splits, verify_public_subset_coverage


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify public subset coverage")
    parser.add_argument(
        "--scenarios-dir",
        default="scenarios/phase2_v2/generated",
        help="Directory containing scenario JSON files",
    )
    args = parser.parse_args()

    scenarios_path = Path(args.scenarios_dir)
    if not scenarios_path.exists():
        print(f"Error: {scenarios_path} does not exist")
        sys.exit(1)

    scenarios = []
    for path in sorted(scenarios_path.glob("*.json")):
        scenarios.append(json.loads(path.read_text(encoding="utf-8")))

    if not scenarios:
        print(f"Error: no JSON files found in {scenarios_path}")
        sys.exit(1)

    print(f"Loaded {len(scenarios)} scenarios from {scenarios_path}")

    splits = assign_splits(scenarios)
    for name, items in splits.items():
        print(f"  {name}: {len(items)} scenarios")

    result = verify_public_subset_coverage(splits)

    print(f"\nPublic subset: {result['public_count']} scenarios")
    print(f"Families covered: {result['families_covered']}")
    print(f"Conditions covered: {result['conditions_covered']}")
    print(f"Alignments covered: {result['alignments_covered']}")

    if result["missing_families"]:
        print(f"\nMISSING families: {result['missing_families']}")
    if result["missing_conditions"]:
        print(f"MISSING conditions: {result['missing_conditions']}")

    if result["sufficient"]:
        print("\nVERDICT: PASS — public subset is sufficient for all headline claims")
    else:
        print("\nVERDICT: FAIL — public subset has coverage gaps")
        sys.exit(1)


if __name__ == "__main__":
    main()
