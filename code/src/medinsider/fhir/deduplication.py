"""Semantic deduplication for scenario corpus.

Detects near-duplicate scenarios using text similarity on key scenario fields.
Uses token-level Jaccard similarity as a lightweight, dependency-free approach.
For production use with sentence embeddings, this module provides the interface
that can be backed by any embedding model.

Deduplication is applied WITHIN each (family x condition) cell to ensure
diversity while preserving the balanced design.
"""

import re
from typing import Any


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric tokens (3+ chars)."""
    return {t for t in re.findall(r"[a-z0-9]{3,}", text.lower())}


def _scenario_text(scenario: dict[str, Any]) -> str:
    """Extract the text fingerprint of a scenario for similarity comparison."""
    parts = [
        scenario.get("case_skeleton", ""),
        scenario.get("care_plan", ""),
        scenario.get("tempting_misaligned_shortcut", ""),
    ]
    return " ".join(parts)


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def find_duplicates(
    scenarios: list[dict[str, Any]],
    threshold: float = 0.85,
) -> list[tuple[str, str, float]]:
    """Find near-duplicate scenario pairs above the similarity threshold.

    Returns list of (episode_id_a, episode_id_b, similarity) tuples.
    """
    fingerprints: list[tuple[str, set[str]]] = []
    for s in scenarios:
        eid = s.get("episode_id", "")
        tokens = _tokenize(_scenario_text(s))
        fingerprints.append((eid, tokens))

    duplicates: list[tuple[str, str, float]] = []
    for i in range(len(fingerprints)):
        for j in range(i + 1, len(fingerprints)):
            sim = jaccard_similarity(fingerprints[i][1], fingerprints[j][1])
            if sim >= threshold:
                duplicates.append((fingerprints[i][0], fingerprints[j][0], round(sim, 4)))

    return duplicates


def find_duplicates_by_cell(
    scenarios: list[dict[str, Any]],
    threshold: float = 0.85,
) -> dict[str, Any]:
    """Find duplicates within each (family x condition) cell.

    Returns a summary with per-cell duplicate counts and flagged pairs.
    """
    cells: dict[str, list[dict[str, Any]]] = {}
    for s in scenarios:
        key = f"{s.get('scenario_family', '')}::{s.get('condition', '')}"
        cells.setdefault(key, []).append(s)

    all_duplicates: list[tuple[str, str, float]] = []
    cell_summaries: dict[str, int] = {}

    for cell_key, cell_scenarios in cells.items():
        dupes = find_duplicates(cell_scenarios, threshold)
        cell_summaries[cell_key] = len(dupes)
        all_duplicates.extend(dupes)

    return {
        "total_scenarios": len(scenarios),
        "total_cells": len(cells),
        "total_duplicates": len(all_duplicates),
        "duplicates_by_cell": cell_summaries,
        "flagged_pairs": all_duplicates,
        "threshold": threshold,
    }


def deduplicate(
    scenarios: list[dict[str, Any]],
    threshold: float = 0.85,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Remove near-duplicate scenarios WITHIN each (family x condition) cell.

    Preserves balanced design by never removing across cell boundaries.
    Returns (kept_scenarios, removed_scenarios).
    """
    cells: dict[str, list[int]] = {}
    for i, s in enumerate(scenarios):
        key = f"{s.get('scenario_family', '')}::{s.get('condition', '')}"
        cells.setdefault(key, []).append(i)

    fingerprints = [_tokenize(_scenario_text(s)) for s in scenarios]
    removed_indices: set[int] = set()

    for _cell_key, indices in cells.items():
        for a_pos in range(len(indices)):
            i = indices[a_pos]
            if i in removed_indices:
                continue
            for b_pos in range(a_pos + 1, len(indices)):
                j = indices[b_pos]
                if j in removed_indices:
                    continue
                sim = jaccard_similarity(fingerprints[i], fingerprints[j])
                if sim >= threshold:
                    removed_indices.add(j)

    kept = [s for i, s in enumerate(scenarios) if i not in removed_indices]
    removed = [s for i, s in enumerate(scenarios) if i in removed_indices]
    return kept, removed
