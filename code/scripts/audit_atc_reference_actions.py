import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_value(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    return value


def audit_reference_actions(dataset_manifest: Path) -> dict[str, Any]:
    dataset_manifest = dataset_manifest.resolve()
    with dataset_manifest.open(encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))
    per_action: dict[str, Counter[str]] = defaultdict(Counter)
    per_family: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    examples: dict[str, dict[str, Any]] = {}

    for row in manifest_rows:
        raw_path = Path(row["path"])
        if raw_path.is_absolute():
            scenario_path = raw_path
        else:
            scenario_path = (dataset_manifest.parent / raw_path).resolve()
            if not scenario_path.exists():
                scenario_path = (REPO_ROOT / raw_path).resolve()
        if not scenario_path.exists():
            raise FileNotFoundError(f"scenario_missing:{row['path']}")
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        family = str(row.get("scenario_family", ""))
        for ref in scenario.get("reference_actions", []):
            action = str(ref.get("action", ""))
            if action == "finish":
                continue
            params = _normalize_value(ref.get("params", {}))
            encoded = json.dumps(params, sort_keys=True)
            per_action[action][encoded] += 1
            per_family[family][action][encoded] += 1
            examples.setdefault(action, params)

    action_summary = {}
    for action, counter in sorted(per_action.items()):
        action_summary[action] = {
            "unique_param_shapes": len(counter),
            "total_occurrences": sum(counter.values()),
            "most_common": [
                {
                    "count": count,
                    "params": json.loads(params),
                }
                for params, count in counter.most_common(5)
            ],
            "example": examples.get(action, {}),
        }

    family_summary = {}
    for family, action_counters in sorted(per_family.items()):
        family_summary[family] = {}
        for action, counter in sorted(action_counters.items()):
            family_summary[family][action] = {
                "unique_param_shapes": len(counter),
                "total_occurrences": sum(counter.values()),
            }

    return {
        "dataset_manifest": str(dataset_manifest),
        "episode_count": len(manifest_rows),
        "action_summary": action_summary,
        "family_summary": family_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ATC reference-action diversity across the v2 corpus.")
    parser.add_argument(
        "--dataset-manifest",
        default="artifacts/v2_manifest.csv",
        help="Path to the authoritative v2 dataset manifest.",
    )
    parser.add_argument(
        "--write-json",
        default="",
        help="Optional path to also write the audit report as JSON.",
    )
    args = parser.parse_args()

    report = audit_reference_actions(Path(args.dataset_manifest))
    print(json.dumps(report, indent=2))
    if args.write_json:
        Path(args.write_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
