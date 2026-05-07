"""Frozen dataset splits for reproducibility.

Generates three splits from the scenario corpus:
- public_dev: Development set for model development (public, ~20%)
- public_validation: Validation set for paper claims (public, ~30%)
- hidden_test: Held-out test set for leaderboard (hidden, ~50%)

Split assignment is deterministic based on episode_id hash.
The public subset (dev + validation) must be sufficient to reproduce
every headline claim in the paper.
"""

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


def _split_bucket(episode_id: str, seed: int = 42) -> str:
    """Assign a deterministic split bucket based on episode_id hash."""
    digest = hashlib.sha256(f"{seed}:{episode_id}".encode()).hexdigest()
    value = int(digest[:8], 16) % 100

    if value < 20:
        return "public_dev"
    elif value < 50:
        return "public_validation"
    else:
        return "hidden_test"


def assign_splits(
    scenarios: list[dict[str, Any]],
    seed: int = 42,
) -> dict[str, list[dict[str, Any]]]:
    """Assign scenarios to splits.

    Uses pair_id (from metadata) when available so that paired twins always
    land in the same split. Falls back to episode_id for unpaired scenarios.
    """
    splits: dict[str, list[dict[str, Any]]] = {
        "public_dev": [],
        "public_validation": [],
        "hidden_test": [],
    }
    for s in scenarios:
        pair_id = str(s.get("metadata", {}).get("pair_id", "")).strip()
        episode_id = str(s.get("episode_id", "")).strip()
        split_key = pair_id if pair_id else episode_id
        if not split_key:
            raise ValueError(f"Scenario missing both pair_id and episode_id: {s}")
        bucket = _split_bucket(split_key, seed)
        splits[bucket].append(s)
    return splits


def generate_split_manifests(
    scenarios: list[dict[str, Any]],
    output_dir: str,
    seed: int = 42,
) -> dict[str, Any]:
    """Generate split manifest CSVs.

    Writes:
      output_dir/public_dev_manifest.csv
      output_dir/public_validation_manifest.csv
      output_dir/hidden_test_manifest.csv
      output_dir/split_summary.json
    """
    splits = assign_splits(scenarios, seed)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    columns = [
        "episode_id",
        "scenario_family",
        "condition",
        "alignment_label",
        "split",
    ]

    for split_name, split_scenarios in splits.items():
        manifest_path = out / f"{split_name}_manifest.csv"
        with manifest_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for s in split_scenarios:
                writer.writerow(
                    {
                        "episode_id": s.get("episode_id", ""),
                        "scenario_family": s.get("scenario_family", ""),
                        "condition": s.get("condition", ""),
                        "alignment_label": s.get("alignment_label", ""),
                        "split": split_name,
                    }
                )

    summary = {
        "seed": seed,
        "total": len(scenarios),
        "public_dev": len(splits["public_dev"]),
        "public_validation": len(splits["public_validation"]),
        "hidden_test": len(splits["hidden_test"]),
        "public_total": len(splits["public_dev"]) + len(splits["public_validation"]),
    }

    summary_path = out / "split_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return summary


def verify_public_subset_coverage(
    splits: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Verify that the public subset covers all families and conditions.

    The public subset (dev + validation) must be sufficient to reproduce
    every headline claim.
    """
    public = splits.get("public_dev", []) + splits.get("public_validation", [])

    families = {s.get("scenario_family", "") for s in public} - {""}
    conditions = {s.get("condition", "") for s in public} - {""}
    alignments = {s.get("alignment_label", "") for s in public} - {""}

    all_families: set[str] = set()
    all_conditions: set[str] = set()
    for split_scenarios in splits.values():
        for s in split_scenarios:
            fam = s.get("scenario_family", "")
            cond = s.get("condition", "")
            if fam:
                all_families.add(fam)
            if cond:
                all_conditions.add(cond)

    missing_families = all_families - families
    missing_conditions = all_conditions - conditions

    all_alignments: set[str] = set()
    for split_scenarios in splits.values():
        for s in split_scenarios:
            al = s.get("alignment_label", "")
            if al:
                all_alignments.add(al)
    missing_alignments = all_alignments - alignments

    return {
        "public_count": len(public),
        "families_covered": sorted(families),
        "conditions_covered": sorted(conditions),
        "alignments_covered": sorted(alignments),
        "missing_families": sorted(missing_families),
        "missing_conditions": sorted(missing_conditions),
        "missing_alignments": sorted(missing_alignments),
        "sufficient": (len(missing_families) == 0 and len(missing_conditions) == 0 and len(missing_alignments) == 0),
    }
