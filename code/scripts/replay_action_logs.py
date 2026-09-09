#!/usr/bin/env python3
"""Replay saved tool actions against frozen scores without calling a provider."""

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code/src"))
from medinsider.fhir.pilot_runtime import _score_fields  # noqa: E402
from medinsider.fhir.scoring import score_episode_from_files  # noqa: E402


def digest(path: Path, normalize_lf: bool = False) -> str:
    payload = path.read_bytes()
    return hashlib.sha256(payload.replace(b"\r\n", b"\n") if normalize_lf else payload).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs", type=Path, required=True, help="Extracted action-log supplement directory")
    parser.add_argument("--allow-missing", action="store_true",
                        help="Verify available logs; still report incomplete coverage")
    parser.add_argument("--mitigation", action="store_true",
                        help="Replay the separate 96-episode mitigation supplement and verify its published table")
    args = parser.parse_args()
    manifest = json.loads((args.logs / "manifest.json").read_text(encoding="utf-8"))
    if manifest["format_version"] != 1:
        parser.error("unsupported action-log manifest version")
    tables = sorted((ROOT / "data/scored_outputs/per_episode").glob("*_scored_episodes.csv"))
    scenarios = ROOT / "data/scenarios/phase2_v2/generated"
    inputs = tables + list(scenarios.glob("*.json")) + [
        ROOT / "code/src/medinsider/fhir/scoring.py",
        ROOT / "code/src/medinsider/fhir/pilot_runtime.py",
    ]
    if args.mitigation:
        from build_final_supported_packet import build_mitigation_rows

        build_mitigation_rows(args.logs)  # Verifies all 68 published numeric fields and treatment CSV hashes.
        tables = sorted((args.logs / "scored_outputs").glob("*_scored_episodes.csv"))
        selection = ROOT / "data/manifests/subsets/v2_mitigation_compliance_gate_background_manifest.csv"
        with selection.open(encoding="utf-8", newline="") as handle:
            episode_ids = {row["episode_id"] for row in csv.DictReader(handle)}
        inputs = [ROOT / "data/scored_outputs/per_episode" / path.name for path in tables]
        inputs += [scenarios / f"{episode_id}.json" for episode_id in sorted(episode_ids)]
        inputs += [selection, ROOT / "docs/paper/final_table7_mitigation.csv",
                   ROOT / "code/src/medinsider/fhir/scoring.py", ROOT / "code/src/medinsider/fhir/pilot_runtime.py"]
    source_errors = sum(
        manifest["public_files"].get(path.relative_to(ROOT).as_posix()) != digest(path, path.suffix == ".py")
        for path in inputs
    )
    if len(tables) != (4 if args.mitigation else 7) or len(inputs) != (32 if args.mitigation else 849) or source_errors:
        print(json.dumps({"status": "input_mismatch", "source_hash_errors": source_errors}))
        return 1
    totals = Counter(expected=0, matched=0, missing=0, mismatched=0, hash_errors=0,
                     numeric_cells_compared=0, numeric_cells_mismatched=0,
                     label_mismatches=0, needs_judge_mismatches=0)
    models = {}
    for table in tables:
        model = table.name.removesuffix("_scored_episodes.csv")
        counts = Counter(expected=0, matched=0, missing=0, mismatched=0, hash_errors=0)
        with table.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                counts["expected"] += 1
                key = f"{model}/{row['episode_id']}.jsonl"
                log = args.logs / key
                if not log.is_file():
                    counts["missing"] += 1
                    counts["hash_errors"] += key in manifest["log_files"]
                    continue
                if manifest["log_files"].get(key) != digest(log):
                    counts["hash_errors"] += 1
                    continue
                score = _score_fields(score_episode_from_files(
                    str(scenarios / f"{row['episode_id']}.json"), str(log)))
                numeric = [key for key in score if key not in {"tradeoff_mode", "needs_judge"}]
                differences = sum(float(row[key]) != float(score[key]) for key in numeric)
                label_diff = row["tradeoff_mode"] != score["tradeoff_mode"]
                judge_diff = (row["needs_judge"].lower() == "true") != score["needs_judge"]
                totals["numeric_cells_compared"] += len(numeric)
                totals["numeric_cells_mismatched"] += differences
                totals["label_mismatches"] += label_diff
                totals["needs_judge_mismatches"] += judge_diff
                counts["mismatched" if differences or label_diff or judge_diff else "matched"] += 1
        totals.update(counts)
        models[model] = dict(counts)
    failed = totals["mismatched"] or totals["hash_errors"] or totals["expected"] != (96 if args.mitigation else 5880)
    if args.mitigation:
        totals["published_numeric_fields_compared"] = 68
    status = "mismatch" if failed else "incomplete" if totals["missing"] else "complete"
    print(json.dumps({"status": status, **totals, "models": models}, indent=2))
    return int(bool(failed or (totals["missing"] and not args.allow_missing)))


if __name__ == "__main__":
    raise SystemExit(main())
