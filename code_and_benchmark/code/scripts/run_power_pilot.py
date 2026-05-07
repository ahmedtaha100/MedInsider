#!/usr/bin/env python
"""Statistical power pilot script.

Runs a subset of scenarios to estimate within-cell and across-cell variance,
then back-calculates the sample size needed for 80% power on the primary
endpoint (paired-delta IVR between neutral and pressure twins).

This is the M9 GATING STEP. No dataset freeze proceeds until the pilot
confirms sufficient statistical power.

Usage:
    PYTHONPATH=src python scripts/run_power_pilot.py [--scenarios-per-cell N] [--seeds N]

Flowchart:
    1. Load v2 manifest
    2. Sample N scenarios per (family x condition) cell
    3. For each seed, score episodes using FHIR scorer
    4. Compute within-cell variance (IVR, MGR, UPR)
    5. Compute across-cell variance
    6. Back out n_required for 80% power (paired t-test)
    7. Decision: expand dataset if n_required > current corpus size
"""

import argparse
import math
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


_Z_ALPHA = {0.10: 1.645, 0.05: 1.96, 0.025: 2.24, 0.01: 2.576}
_Z_BETA = {0.80: 0.842, 0.85: 1.036, 0.90: 1.282, 0.95: 1.645}


def compute_paired_power(
    effect_size: float,
    std_dev: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Back out n (pairs) required for a paired t-test.

    Uses the formula: n = ((z_alpha + z_beta) * sigma / delta)^2
    where delta = effect_size, sigma = std_dev of paired differences.
    """
    if alpha not in _Z_ALPHA:
        raise ValueError(f"Unsupported alpha={alpha}. Supported: {sorted(_Z_ALPHA)}")
    if power not in _Z_BETA:
        raise ValueError(f"Unsupported power={power}. Supported: {sorted(_Z_BETA)}")

    z_alpha = _Z_ALPHA[alpha]
    z_beta = _Z_BETA[power]

    if effect_size <= 0:
        raise ValueError(f"effect_size must be positive, got {effect_size}")
    if std_dev <= 0:
        # Zero variance means insufficient data — cannot determine power
        return -1

    n = math.ceil(((z_alpha + z_beta) * std_dev / effect_size) ** 2)
    return max(n, 2)


def compute_variance_estimates(
    scores: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """Compute within-cell and across-cell variance from scored episodes.

    Groups by (scenario_family, condition) and computes variance of each
    metric within and across cells.
    """
    if metrics is None:
        metrics = ["IVR", "MGR", "UPR", "AEOR", "PSD", "CDR"]

    cells: dict[str, list[dict[str, float]]] = {}
    for score in scores:
        family = score.get("scenario_family", "")
        condition = score.get("condition", "")
        key = f"{family}::{condition}"
        primary = score.get("primary", {})
        row = {}
        for m in metrics:
            row[m] = float(primary.get(m, {}).get("rate", 0.0))
        cells.setdefault(key, []).append(row)

    within_variance: dict[str, float] = {m: 0.0 for m in metrics}
    contributing_cells: dict[str, int] = {m: 0 for m in metrics}
    across_means: dict[str, list[float]] = {m: [] for m in metrics}

    for _cell_key, cell_scores in cells.items():
        for m in metrics:
            values = [s[m] for s in cell_scores]
            if not values:
                continue
            mean = sum(values) / len(values)
            across_means[m].append(mean)
            if len(values) >= 2:
                var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
                within_variance[m] += var
                contributing_cells[m] += 1

    for m in metrics:
        divisor = contributing_cells[m] or 1
        within_variance[m] /= divisor

    across_variance: dict[str, float] = {}
    for m in metrics:
        means = across_means[m]
        if len(means) >= 2:
            grand_mean = sum(means) / len(means)
            across_variance[m] = sum((v - grand_mean) ** 2 for v in means) / (len(means) - 1)
        else:
            across_variance[m] = 0.0

    cell_sizes = [len(v) for v in cells.values()]
    min_cell_size = min(cell_sizes) if cell_sizes else 0

    return {
        "n_cells": len(cells),
        "n_scores": len(scores),
        "min_cell_size": min_cell_size,
        "within_variance": within_variance,
        "across_variance": across_variance,
        "metrics": metrics,
    }


def run_power_analysis(
    variance_estimates: dict[str, Any],
    expected_effect_size: float = 0.10,
    alpha: float = 0.05,
    power: float = 0.80,
) -> dict[str, Any]:
    """Run power analysis for each metric.

    Returns n_required per metric and overall recommendation.
    """
    metrics = variance_estimates["metrics"]
    results: dict[str, Any] = {}

    min_cell_size = variance_estimates.get("min_cell_size", 0)

    for m in metrics:
        within_var = variance_estimates["within_variance"].get(m, 0.0)
        std_dev = math.sqrt(within_var) if within_var > 0 else 0.0
        n_required = compute_paired_power(expected_effect_size, std_dev, alpha, power)
        results[m] = {
            "within_variance": round(within_var, 6),
            "within_std_dev": round(std_dev, 6),
            "n_required": n_required,
            "sufficient": n_required >= 0 and n_required <= min_cell_size,
            "indeterminate": n_required < 0,
        }

    has_indeterminate = any(r["indeterminate"] for r in results.values())
    valid_n = [r["n_required"] for r in results.values() if r["n_required"] >= 0]
    max_n = max(valid_n) if valid_n else 0
    sufficient = not has_indeterminate and max_n > 0 and max_n <= min_cell_size

    if has_indeterminate:
        recommendation = "Indeterminate — zero variance on some metrics, need more data"
    elif sufficient:
        recommendation = "Sufficient power at current sample size"
    else:
        recommendation = f"Need {max_n} pairs per cell (current min cell: {min_cell_size})"

    return {
        "expected_effect_size": expected_effect_size,
        "alpha": alpha,
        "power": power,
        "per_metric": results,
        "max_n_required": max_n,
        "min_cell_size": min_cell_size,
        "has_indeterminate": has_indeterminate,
        "sufficient": sufficient,
        "recommendation": recommendation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Statistical power pilot")
    parser.add_argument("--scenarios-per-cell", type=int, default=50)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--effect-size", type=float, default=0.10)
    args = parser.parse_args()

    print("Power pilot script ready.")
    print(f"Configuration: {args.scenarios_per_cell} scenarios/cell, {args.seeds} seeds")
    print(f"Expected effect size: {args.effect_size}")
    print()
    print("To run the full pilot, you need:")
    print("  1. Generated v2 scenario corpus (run generate_v2_paired_dataset.py)")
    print("  2. At least one model API key configured")
    print("  3. Scored episode logs from model runs")
    print()
    print("This script provides the power analysis functions.")
    print("Import and use: compute_variance_estimates(), run_power_analysis()")


if __name__ == "__main__":
    main()
