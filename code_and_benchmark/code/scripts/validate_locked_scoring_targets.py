#!/usr/bin/env python3
"""Validate the submitted MedInsider locked-artifact manifest."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

BUNDLE_ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = BUNDLE_ROOT / "docs/validation/locked_scoring_targets.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_rows(path: Path) -> int:
    with path.open(newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def iter_records(obj: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        if "path" in obj:
            records.append(obj)
        for value in obj.values():
            records.extend(iter_records(value))
    elif isinstance(obj, list):
        for value in obj:
            records.extend(iter_records(value))
    return records


def main() -> int:
    lock = json.loads(LOCK_PATH.read_text())
    records = iter_records(lock)
    errors: list[str] = []

    for record in records:
        rel_path = Path(record["path"])
        path = BUNDLE_ROOT / rel_path
        if not path.exists():
            errors.append(f"missing: {rel_path}")
            continue
        expected_bytes = record.get("bytes")
        if expected_bytes is not None and path.stat().st_size != expected_bytes:
            errors.append(
                f"bytes mismatch: {rel_path} expected {expected_bytes} got {path.stat().st_size}"
            )
        expected_sha = record.get("sha256")
        if expected_sha is not None:
            actual_sha = sha256(path)
            if actual_sha != expected_sha:
                errors.append(f"sha256 mismatch: {rel_path} expected {expected_sha} got {actual_sha}")
        expected_rows = record.get("rows")
        if expected_rows is not None:
            if path.suffix != ".csv":
                errors.append(f"row count requested for non-csv path: {rel_path}")
            else:
                actual_rows = csv_rows(path)
                if actual_rows != expected_rows:
                    errors.append(
                        f"row mismatch: {rel_path} expected {expected_rows} got {actual_rows}"
                    )

    if errors:
        print("Lock validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Lock validation passed: {len(records)} locked paths verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
