from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import os
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from typing import Iterable

import httpx
from huggingface_hub import HfApi, hf_hub_download

DEFAULT_REPO = "ANON-AUTHOR/medinsider-validation-responses"
DEFAULT_DATA_DIR = "validation_data"
COMMON_PATH = Path(__file__).resolve().parents[2] / "validation" / "medinsider_validation_space" / "common.py"
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
        f"Generated UTC: {datetime.now(UTC).isoformat()}",
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
    date = datetime.now(UTC).strftime("%Y%m%d")
    output_path = output_dir / f"kappa_report_{date}.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute MedInsider reviewer agreement from HF response exports.")
    parser.add_argument("--repo-id", default=DEFAULT_REPO)
    parser.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    parser.add_argument("--manifest", type=Path, default=Path("artifacts/subsets/medinsider_validation_manifest.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("docs/validation"))
    args = parser.parse_args()
    try:
        output = compute_report(args.repo_id, args.data_dir, args.manifest, args.output_dir)
    except RuntimeError as exc:
        raise SystemExit(f"error: {exc}") from None
    print(output)


if __name__ == "__main__":
    main()
