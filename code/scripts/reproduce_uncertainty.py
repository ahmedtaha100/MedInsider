"""Reproduce the archived pair-bootstrap intervals and aggregate Gwet AC1 values.

Reads frozen scores and validation aggregates; never calls a model provider.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from build_final_supported_packet import MODEL_SPECS, TABLE_METRICS
from validate_locked_scoring_targets import main as validate_locks

ROOT = Path(__file__).resolve().parents[2]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def complete_pairs(rows: list[dict[str, str]]) -> dict[str, dict[str, dict[str, str]]]:
    pairs: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_role = pairs.setdefault(row["pair_id"], {})
        if row["twin_role"] in by_role:
            raise ValueError(f"Duplicate twin: {row['episode_id']}")
        by_role[row["twin_role"]] = row
    if len(rows) != 840 or len(pairs) != 420 or any(set(p) != {"neutral", "pressure"} for p in pairs.values()):
        raise ValueError("Expected 840 rows forming 420 complete pairs")
    return dict(sorted(pairs.items()))


def bootstrap(values: np.ndarray, reps: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    draws = np.empty((reps, values.shape[1]), dtype=float)
    for start in range(0, reps, 500):
        size = min(500, reps - start)
        indices = rng.integers(0, len(values), size=(size, len(values)))
        draws[start:start + size] = values[indices].mean(axis=1)
    return np.quantile(draws, 0.025, axis=0), np.quantile(draws, 0.975, axis=0)


def agreement_rows() -> list[dict]:
    # Category marginals are documented in the frozen validation_results.md.
    # Q3 excludes the item with one Scorer-hidden response and three Yes responses.
    specs = (
        ("Q1", "scenario validity", (470, 8, 2), "Yes|No|Unclear",
         "published aggregate counts; all 120 items retained",
         "point estimate only; raw Q1 item-response table is unavailable"),
        ("Q2", "integrity violation", (351, 128, 1), "Yes|No|Unclear",
         "nine dissent rows are explicit; the other 111 item rows are reconstructed from the published "
         "statement that they were unanimous",
         "point estimate only; episode-level intervals are outside this release"),
        ("Q3", "scorer agreement", (468, 8), "Yes|No",
         "119-item Fleiss subset after excluding the item containing the single Scorer-hidden response; "
         "retained visible counts reconstructed from the published reviewer marginals and pairwise mismatch counts",
         "point estimate only; raw Q3 item-response table is unavailable"),
    )
    fleiss = {r["question"]: r for r in read_csv(ROOT / "docs/validation/kappa_tables.csv")
              if r["comparison_type"] == "fleiss"}
    rows = []
    for question, label, counts, categories, count_note, interval_note in specs:
        record = fleiss[question]
        observed = int(record["agreement_count"]) / (int(record["n_episodes"]) * 6)
        proportions = np.array(counts, dtype=float) / sum(counts)
        chance = float(np.sum(proportions * (1.0 - proportions)) / (len(counts) - 1))
        rows.append(dict(question=question, label=label, observed_agreement=f"{observed:.6f}",
                         gwet_ac1=f"{(observed - chance) / (1.0 - chance):.6f}",
                         ac1_chance_agreement=f"{chance:.6f}", categories=categories,
                         category_counts="|".join(map(str, counts)), count_note=count_note,
                         interval_note=interval_note))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=ROOT / "reports/uncertainty")
    parser.add_argument("--bootstrap-reps", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=20_260_727)
    args = parser.parse_args()
    if args.bootstrap_reps < 1:
        parser.error("--bootstrap-reps must be positive")
    if validate_locks():
        raise SystemExit(1)
    main_rows, delta_rows = [], []
    common_pair_ids = None
    for model_index, spec in enumerate(MODEL_SPECS):
        pairs = complete_pairs(read_csv(ROOT / "data/scored_outputs/per_episode" / spec["scored_file"]))
        if common_pair_ids is not None and tuple(pairs) != common_pair_ids:
            raise ValueError("Model pair IDs differ")
        common_pair_ids = tuple(pairs)
        pair_means = np.array([[np.mean([float(pair[role][metric]) for role in ("neutral", "pressure")])
                                for metric in TABLE_METRICS] for pair in pairs.values()], dtype=float)
        low, high = bootstrap(pair_means, args.bootstrap_reps, args.seed + model_index)
        estimates = pair_means.mean(axis=0)
        for index, metric in enumerate(TABLE_METRICS):
            interpretation = "co-primary task completion" if metric == "ATC" else "diagnostic subtype"
            if metric == "PSD":
                interpretation = ("structurally non-informative in v2: generated initial states do not "
                                  "seed a diagnosis code covered by CONTRAINDICATION_RULES")
            main_rows.append(dict(model=spec["model_display"], metric=metric, estimate=f"{estimates[index]:.6f}",
                                  ci_95_lower=f"{low[index]:.6f}", ci_95_upper=f"{high[index]:.6f}",
                                  n_pairs=420, n_episodes=840, bootstrap_reps=args.bootstrap_reps,
                                  seed=args.seed + model_index, resampling_unit="neutral_pressure_pair",
                                  interpretation=interpretation))
        background = [pair for pair in pairs.values() if pair["pressure"]["condition"] == "background_pressure"]
        if len(background) != 60:
            raise ValueError("Expected 60 background-pressure pairs")
        neutral = np.array([[float(pair["neutral"][m]) for m in TABLE_METRICS] for pair in background])
        pressure = np.array([[float(pair["pressure"][m]) for m in TABLE_METRICS] for pair in background])
        deltas = pressure - neutral
        seed = args.seed + 100 + model_index
        low, high = bootstrap(deltas, args.bootstrap_reps, seed)
        for index, metric in enumerate(TABLE_METRICS):
            delta_rows.append(dict(model=spec["model_display"], metric=metric,
                                   neutral_mean=f"{neutral[:, index].mean():.6f}",
                                   pressure_mean=f"{pressure[:, index].mean():.6f}",
                                   paired_delta_pressure_minus_neutral=f"{deltas[:, index].mean():.6f}",
                                   ci_95_lower=f"{low[index]:.6f}", ci_95_upper=f"{high[index]:.6f}",
                                   n_pairs=60, bootstrap_reps=args.bootstrap_reps, seed=seed,
                                   resampling_unit="matched_pair"))
    write_csv(args.output_root / "main_pair_cluster_bootstrap_ci.csv", main_rows)
    write_csv(args.output_root / "background_pressure_paired_bootstrap_delta_ci.csv", delta_rows)
    write_csv(args.output_root / "agreement_sensitivity_gwet_ac1.csv", agreement_rows())
    print(f"Reproduced 49 main intervals, 49 paired-delta intervals and 3 AC1 values in {args.output_root}")


if __name__ == "__main__":
    main()
