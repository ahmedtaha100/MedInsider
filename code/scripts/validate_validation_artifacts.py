#!/usr/bin/env python3
"""Validate shipped MedInsider expert-validation summary artifacts."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

BUNDLE_ROOT = Path(__file__).resolve().parents[2]
VALIDATION_DIR = BUNDLE_ROOT / "docs/validation"


def read_csv(name: str) -> list[dict[str, str]]:
    with (VALIDATION_DIR / name).open(newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    summary = read_csv("validation_summary_120.csv")
    require(len(summary) == 120, f"validation_summary_120.csv rows = {len(summary)}", errors)
    majority = Counter(row["expert_majority_q2"] for row in summary)
    scorer = Counter(row["scorer_q2_verdict"] for row in summary)
    agreement = Counter(row["agreement"] for row in summary)
    require(majority == {"Yes": 90, "No": 30}, f"Q2 majority counts = {dict(majority)}", errors)
    require(scorer == {"Yes": 90, "No": 30}, f"scorer Q2 counts = {dict(scorer)}", errors)
    require(agreement == {"Yes": 120}, f"scorer/expert agreement counts = {dict(agreement)}", errors)

    dissent = read_csv("q2_dissent_adjudications.csv")
    require(len(dissent) == 9, f"q2_dissent_adjudications.csv rows = {len(dissent)}", errors)
    for row in dissent:
        votes = [row[f"R{i}_q2"] for i in range(1, 5)]
        counts = Counter(votes)
        require(
            sorted(counts.values()) == [1, 3],
            f"non-3-1 Q2 split for {row.get('episode_id')}: {dict(counts)}",
            errors,
        )
        require(row["adjudicated_label"] in {"Yes", "No"}, "missing adjudicated label", errors)

    kappa = read_csv("kappa_tables.csv")
    require(len(kappa) == 30, f"kappa_tables.csv rows = {len(kappa)}", errors)
    fleiss_q2 = [
        row
        for row in kappa
        if row["question"] == "Q2"
        and row["comparison_type"] == "fleiss"
        and row["comparison"] == "all_4_reviewers"
    ]
    require(len(fleiss_q2) == 1, f"Q2 Fleiss row count = {len(fleiss_q2)}", errors)
    if fleiss_q2:
        require(fleiss_q2[0]["kappa"] == "0.905", f"Q2 Fleiss kappa = {fleiss_q2[0]['kappa']}", errors)

    alias = VALIDATION_DIR / "kappa_tables_20260505.csv"
    require(alias.exists(), "kappa_tables_20260505.csv alias is missing", errors)
    if alias.exists():
        require(
            alias.read_bytes() == (VALIDATION_DIR / "kappa_tables.csv").read_bytes(),
            "kappa_tables_20260505.csv differs from kappa_tables.csv",
            errors,
        )

    results_text = (VALIDATION_DIR / "validation_results.md").read_text()
    expected_snippets = [
        "Loaded 480 submissions",
        "Yes 470 (97.9%)",
        "Yes 351 (73.1%)",
        "Yes 471 (98.1%)",
        "Yes 90 (75.0%), No 30 (25.0%)",
        "The 9 non-unanimous Q2 episodes were all 3-1 splits.",
        "| Any integrity metric | 90 | 90/90 (100.0%) | 30/30 (100.0%) | 120/120 (100.0%) |",
        "| IVR | 33 |",
        "| MGR | 29 |",
        "| AEOR | 25 |",
        "| CDR | 25 |",
        "| UPR | 3 |",
    ]
    for snippet in expected_snippets:
        require(snippet in results_text, f"validation_results.md missing snippet: {snippet}", errors)

    if errors:
        print("Validation artifact check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Validation artifact check passed: 120 episodes, Q2 labels, kappas, and summaries verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
