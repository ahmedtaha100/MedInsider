import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from medinsider.phaseA_governance import (
    AUTHORITY_SPEC_VERSION,
    FREEZE_POLICY_VERSION,
    SCENARIO_SET_VERSION,
    SPLIT_POLICY_VERSION,
    build_phase_a_artifacts,
)


def _load_scenario_generation_metadata(dataset_dir: Path) -> dict:
    summary_path = dataset_dir / "artifacts" / "v2_generation_summary.json"
    if not summary_path.exists():
        return {}
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _write_version_manifest(
    output_path: Path,
    benchmark_version: str,
    scorer_version: str,
    evaluation_protocol_version: str,
    phase_a_summary: dict,
    dataset_dir: Path,
) -> Path:
    generation_metadata = _load_scenario_generation_metadata(dataset_dir)
    frozen_at = datetime.now(UTC).isoformat()
    version_manifest = {
        "benchmark_version": benchmark_version,
        "scenario_set_version": SCENARIO_SET_VERSION,
        "scenario_generator_version": "paired_scenario_v2.0.0",
        "scorer_version": scorer_version,
        "evaluation_protocol_version": evaluation_protocol_version,
        "split_policy_version": SPLIT_POLICY_VERSION,
        "authority_spec_version": AUTHORITY_SPEC_VERSION,
        "freeze_policy_version": FREEZE_POLICY_VERSION,
        "frozen_at_utc": frozen_at,
        "scenario_generation_seed": generation_metadata.get("seed"),
        "phase2_total_scenarios": generation_metadata.get("total_scenarios"),
        "phase_a_outputs": {
            "freeze_manifest_path": phase_a_summary["freeze_manifest_path"],
            "public_dev_manifest_path": phase_a_summary["public_dev_manifest_path"],
            "public_validation_manifest_path": phase_a_summary["public_validation_manifest_path"],
            "hidden_test_manifest_path": phase_a_summary["hidden_test_manifest_path"],
            "hidden_test_manifest_sha256_path": phase_a_summary["hidden_test_manifest_sha256_path"],
            "split_summary_path": phase_a_summary["split_summary_path"],
            "authority_records_path": phase_a_summary["authority_records_path"],
            "authority_summary_path": phase_a_summary["authority_summary_path"],
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(version_manifest, indent=2), encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase A governance and freeze artifacts.")
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--benchmark-version", default="2.0.0")
    parser.add_argument("--scorer-version", default="fhir_scoring_v2.0.0")
    parser.add_argument("--evaluation-protocol-version", default="eval_protocol_v2.0.0")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dev-fraction", type=float, default=0.5)
    parser.add_argument("--validation-fraction", type=float, default=0.25)
    parser.add_argument(
        "--version-manifest-path",
        default="benchmark_versions/version_manifest.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir)
    phase_a_summary = build_phase_a_artifacts(
        dataset_dir=str(dataset_dir),
        benchmark_version=args.benchmark_version,
        seed=args.seed,
        dev_fraction=args.dev_fraction,
        validation_fraction=args.validation_fraction,
    )
    version_manifest_path = _write_version_manifest(
        output_path=Path(args.version_manifest_path),
        benchmark_version=args.benchmark_version,
        scorer_version=args.scorer_version,
        evaluation_protocol_version=args.evaluation_protocol_version,
        phase_a_summary=phase_a_summary,
        dataset_dir=dataset_dir,
    )
    output = {
        "phase_a_summary": phase_a_summary,
        "version_manifest_path": str(version_manifest_path),
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
