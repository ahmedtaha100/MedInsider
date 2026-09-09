from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from statistics import mean
from typing import Iterable

DEFAULT_REPO = "ANON-AUTHOR/medinsider-validation-responses"
DEFAULT_DATA_DIR = "validation_data"
BUNDLE_ROOT = Path(__file__).resolve().parents[3]
COMMON_PATH = BUNDLE_ROOT / "validation" / "medinsider_validation_space" / "common.py"
HF_RETRIES = 5
HF_BACKOFF = 2.0


def load_common_constants() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    spec = importlib.util.spec_from_file_location("medinsider_validation_common", COMMON_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load shared validation constants from {COMMON_PATH}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.REVIEWERS), tuple(module.Q2_CATEGORIES), tuple(module.Q3_CATEGORIES)


REVIEWERS, Q2_CATEGORIES, Q3_CATEGORIES = load_common_constants()


def retry_hf_call(operation_name: str, fn):
    import httpx

    last_error: Exception | None = None
    for attempt in range(HF_RETRIES):
        try:
            return fn()
        except (httpx.TransportError, OSError, TimeoutError) as exc:
            last_error = exc
            if attempt < HF_RETRIES - 1:
                time.sleep(HF_BACKOFF**attempt)
                continue
            raise RuntimeError(f"HF {operation_name} failed after {HF_RETRIES} attempts: {exc}") from exc
    raise RuntimeError(f"HF {operation_name} failed: {last_error}")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cohen_kappa(a: list[str], b: list[str], categories: Iterable[str]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    cats = list(categories)
    n = len(a)
    observed = sum(1 for x, y in zip(a, b, strict=True) if x == y) / n
    counts_a = Counter(a)
    counts_b = Counter(b)
    expected = sum((counts_a[c] / n) * (counts_b[c] / n) for c in cats)
    if math.isclose(1.0, expected):
        return None
    return (observed - expected) / (1 - expected)


def fleiss_kappa(rows: list[list[str]], categories: Iterable[str]) -> float | None:
    if not rows:
        return None
    cats = list(categories)
    n_items = len(rows)
    n_raters = len(rows[0])
    if n_raters < 2 or any(len(row) != n_raters for row in rows):
        return None

    p_i = []
    category_totals = Counter()
    for row in rows:
        counts = Counter(row)
        category_totals.update(counts)
        p_i.append((sum(count * count for count in counts.values()) - n_raters) / (n_raters * (n_raters - 1)))
    p_bar = sum(p_i) / n_items
    total_ratings = n_items * n_raters
    p_e = sum((category_totals[c] / total_ratings) ** 2 for c in cats)
    if math.isclose(1.0, p_e):
        return None
    return (p_bar - p_e) / (1 - p_e)


def majority(values: list[str]) -> str | None:
    counts = Counter(values)
    if not counts:
        return None
    top = counts.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None
    return top[0][0]


def download_response_rows(repo_id: str, data_dir: str, token: str | None) -> list[dict[str, str]]:
    from huggingface_hub import HfApi, hf_hub_download

    api = HfApi(token=token)
    files = retry_hf_call(
        "response file listing",
        lambda: api.list_repo_files(repo_id=repo_id, repo_type="dataset", token=token),
    )
    rows: list[dict[str, str]] = []
    for file_path in files:
        if not file_path.startswith(f"{data_dir}/reviews_") or not file_path.endswith(".csv"):
            continue
        local_path = retry_hf_call(
            f"response file download for {file_path}",
            lambda file_path=file_path: hf_hub_download(
                repo_id=repo_id,
                repo_type="dataset",
                filename=file_path,
                token=token,
            ),
        )
        rows.extend(read_csv(Path(local_path)))
    return rows


def compute_pattern_report(pattern_path: Path, output_dir: Path) -> Path:
    """Reproduce agreement from question-specific joint-rating frequencies, without item identities."""
    questions = {"Q1": "Scenario validity", "Q2": "Integrity violation", "Q3": "Scorer agreement"}
    patterns: dict[str, list[tuple[list[str], int]]] = defaultdict(list)
    for row in read_csv(pattern_path):
        question = row["question"]
        values = [row[reviewer] for reviewer in REVIEWERS]
        allowed = {"Yes", "No", "Scorer hidden" if question == "Q3" else "Unclear"}
        count = int(row["count"])
        if question not in questions or not set(values) <= allowed or not 1 <= count <= 120:
            raise ValueError("Invalid question, rating, or count in aggregate patterns")
        patterns[question].append((values, count))
    if set(patterns) != set(questions) or any(sum(n for _, n in rows) != 120 for rows in patterns.values()):
        raise ValueError("Expected 120 four-rater patterns per question")

    kappa_rows: list[dict] = []
    marginal_rows: list[dict] = []
    for question, label in questions.items():
        # Each question is expanded independently; no cross-question item linkage is available.
        matrix = [values for values, count in patterns[question] for _ in range(count)]
        categories = ["Yes", "No"] if question == "Q3" else ["Yes", "No", "Unclear"]

        def append_row(comparison_type, comparison, group, kappa, n, count, agreement,
                       *, question=question, label=label):
            if kappa is None:
                raise ValueError(f"Undefined kappa for {question}/{comparison}")
            bands = [(0, "Poor"), (0.2, "Slight"), (0.4, "Fair"), (0.6, "Moderate"),
                     (0.8, "Substantial"), (float("inf"), "Almost perfect")]
            kappa_rows.append({
                "question": question, "question_label": label, "comparison_type": comparison_type,
                "comparison": comparison, "reviewer_group": group, "kappa": f"{kappa:.3f}",
                "landis_koch": next(name for bound, name in bands if kappa <= bound),
                "n_episodes": n, "agreement_count": count, "agreement_rate": f"{agreement:.6f}",
                "agreement_pct": f"{agreement * 100:.1f}%",
            })

        pairs = {}
        for left, right in combinations(range(len(REVIEWERS)), 2):
            values = [(row[left], row[right]) for row in matrix
                      if row[left] in categories and row[right] in categories]
            n = len(values)
            count = sum(a == b for a, b in values)
            kappa = cohen_kappa([a for a, _ in values], [b for _, b in values], categories)
            comparison = f"{REVIEWERS[left]}-{REVIEWERS[right]}"
            pairs[comparison] = (kappa, n, count, count / n)
            append_row("pairwise", comparison, "pair", *pairs[comparison])
        complete = [row for row in matrix if all(value in categories for value in row)]
        count = sum(sum(a == b for a, b in combinations(row, 2)) for row in complete)
        append_row("fleiss", "all_4_reviewers", "all", fleiss_kappa(complete, categories),
                   len(complete), count, count / (len(complete) * 6))
        for comparison, group in [("R1-R2", "IM-IM"), ("R3-R4", "CPMA-CPMA")]:
            append_row("intra_profession", comparison, group, *pairs[comparison])
        cross_names = ["R1-R3", "R1-R4", "R2-R3", "R2-R4"]
        cross = [pairs[name] for name in cross_names]
        append_row("inter_profession_average", ";".join(cross_names), "IM-vs-CPMA mean",
                   mean(row[0] for row in cross), mean(float(row[1]) for row in cross), "",
                   mean(row[3] for row in cross))
        for index, reviewer in enumerate((*REVIEWERS, "all")):
            counts = Counter(row[index] for row in matrix) if reviewer != "all" else Counter(
                value for row in matrix for value in row)
            marginal_rows.append({"question": question, "reviewer_group": reviewer,
                                  **{value: counts[value] for value in ("Yes", "No", "Unclear", "Scorer hidden")},
                                  "total": sum(counts.values())})

    locked = read_csv(BUNDLE_ROOT / "docs/validation/kappa_tables.csv")
    if len(kappa_rows) != len(locked):
        raise ValueError("Agreement table row count differs from the frozen table")
    numeric = {"kappa", "n_episodes", "agreement_count", "agreement_rate", "agreement_pct"}
    for actual, expected in zip(kappa_rows, locked, strict=True):
        for field, value in expected.items():
            observed = str(actual[field])
            if field in numeric and observed and value:
                matches = float(observed.removesuffix("%")) == float(value.removesuffix("%"))
            else:
                matches = observed == value
            if not matches:
                raise ValueError(f"Frozen agreement mismatch: {expected['question']}/{expected['comparison']}/{field}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, rows in [("kappa_tables.csv", kappa_rows), ("response_marginals.csv", marginal_rows)]:
        with (output_dir / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    return output_dir / "kappa_tables.csv"


def compute_report(repo_id: str, data_dir: str, manifest_path: Path, output_dir: Path) -> Path:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if repo_id == DEFAULT_REPO and not token:
        raise RuntimeError(
            f"HF_TOKEN or HUGGINGFACE_TOKEN is required to read private validation response repo {DEFAULT_REPO}."
        )
    manifest = read_csv(manifest_path)
    double_episode_ids = {
        row["episode_id"] for row in manifest if row.get("is_double_labeled", "").strip().lower() == "true"
    }
    responses = [
        row
        for row in download_response_rows(repo_id, data_dir, token)
        if row.get("episode_id") in double_episode_ids and row.get("reviewer_id") in REVIEWERS
    ]

    by_episode: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in responses:
        episode_id = row["episode_id"]
        reviewer_id = row["reviewer_id"]
        if reviewer_id in by_episode[episode_id]:
            raise ValueError(f"Duplicate response row for episode_id={episode_id} reviewer_id={reviewer_id}.")
        by_episode[episode_id][reviewer_id] = row

    lines = [
        "# MedInsider Validation Kappa Report",
        "",
        f"Generated UTC: {datetime.now(timezone.utc).isoformat()}",
        f"HF response repo: `{repo_id}`",
        f"Double-labeled target episodes: {len(double_episode_ids)}",
        f"Downloaded double-labeled response rows: {len(responses)}",
        "",
        "## Pairwise Cohen's Kappa",
        "",
        "| Question | Reviewer Pair | Shared Episodes | Kappa |",
        "|---|---:|---:|---:|",
    ]

    for question, field, categories in [
        ("Q2 integrity violation", "q2_integrity_violation", Q2_CATEGORIES),
        ("Q3 scorer agreement", "q3_scorer_agreement", Q3_CATEGORIES),
    ]:
        for left, right in combinations(REVIEWERS, 2):
            left_values: list[str] = []
            right_values: list[str] = []
            for reviewer_rows in by_episode.values():
                if left in reviewer_rows and right in reviewer_rows:
                    l_value = reviewer_rows[left].get(field, "")
                    r_value = reviewer_rows[right].get(field, "")
                    if l_value in categories and r_value in categories:
                        left_values.append(l_value)
                        right_values.append(r_value)
            value = cohen_kappa(left_values, right_values, categories)
            rendered = "NA" if value is None else f"{value:.4f}"
            lines.append(f"| {question} | {left} vs {right} | {len(left_values)} | {rendered} |")

    lines.extend(
        [
            "",
            "## Fleiss' Kappa",
            "",
            "| Question | Complete Episodes | Kappa |",
            "|---|---:|---:|",
        ]
    )

    for question, field, categories in [
        ("Q2 integrity violation", "q2_integrity_violation", Q2_CATEGORIES),
        ("Q3 scorer agreement", "q3_scorer_agreement", Q3_CATEGORIES),
    ]:
        matrix: list[list[str]] = []
        for reviewer_rows in by_episode.values():
            if all(reviewer in reviewer_rows for reviewer in REVIEWERS):
                values = [reviewer_rows[reviewer].get(field, "") for reviewer in REVIEWERS]
                if all(value in categories for value in values):
                    matrix.append(values)
        value = fleiss_kappa(matrix, categories)
        rendered = "NA" if value is None else f"{value:.4f}"
        lines.append(f"| {question} | {len(matrix)} | {rendered} |")

    q3_majorities: list[str] = []
    for reviewer_rows in by_episode.values():
        values = [
            reviewer_rows[reviewer].get("q3_scorer_agreement", "")
            for reviewer in REVIEWERS
            if reviewer in reviewer_rows
        ]
        agreed = majority([value for value in values if value in Q3_CATEGORIES])
        if agreed is not None:
            q3_majorities.append(agreed)
    usable = [value for value in q3_majorities if value != "Scorer hidden"]
    agree_count = sum(1 for value in usable if value == "Yes")
    rate = agree_count / len(usable) if usable else None

    lines.extend(
        [
            "",
            "## Agreement With Automated Scorer",
            "",
            f"Q3 majority usable episodes: {len(usable)}",
            f"Q3 majority agreement rate: {'NA' if rate is None else f'{rate:.4f}'}",
            "",
            "Note: test responses can make these values meaningless; use this report only after expert labels are"
            " complete.",
            "",
        ]
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_path = output_dir / f"kappa_report_{date}.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute MedInsider agreement from aggregate patterns or HF exports.")
    parser.add_argument("--pattern-counts", type=Path, help="Offline question-specific joint-rating count CSV")
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/subsets/medinsider_validation_manifest.csv"))
    parser.add_argument("--output-dir", type=Path,
                        help="Defaults to reports/validation for patterns, docs/validation for HF")
    args = parser.parse_args()
    output_dir = args.output_dir or Path("reports/validation" if args.pattern_counts else "docs/validation")
    try:
        output = (compute_pattern_report(args.pattern_counts, output_dir) if args.pattern_counts else
                  compute_report(args.repo_id, args.data_dir, args.manifest, output_dir))
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from None
    print(output)


if __name__ == "__main__":
    main()
