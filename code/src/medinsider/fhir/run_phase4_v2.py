import argparse
import json
from typing import Any

from medinsider.fhir.pilot_runtime import (
    load_default_run_config,
    load_run_config,
    merge_run_config_overrides,
    run_phase4_v2,
    run_preflight,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Authoritative MedInsider v2/FHIR pilot runner.")
    parser.add_argument("--run-config", default=None, help="Path to a run config JSON file.")
    parser.add_argument("--mode", choices=["smoke", "pilot"], default="smoke")
    parser.add_argument("--agent-type", choices=["scripted", "openai", "claude"], default="scripted")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-root", default=None)
    parser.add_argument("--dataset-manifest", default=None)
    parser.add_argument("--selection-manifest", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--resume", dest="resume", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-judge-pipeline", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    hf_backup_group = parser.add_mutually_exclusive_group()
    hf_backup_group.add_argument("--enable-hf-backup", action="store_true")
    hf_backup_group.add_argument("--disable-hf-backup", action="store_true")
    parser.add_argument("--hf-backup-strict", action="store_true")
    parser.add_argument("--hf-backup-dry-run", action="store_true")
    parser.add_argument("--hf-backup-batch-size", type=int, default=None)
    parser.add_argument("--hf-backup-primary-repo", default=None)
    parser.add_argument("--hf-backup-secondary-repo", default=None)
    return parser.parse_args(argv)


def resolve_config(args: argparse.Namespace) -> dict[str, Any]:
    config = (
        load_run_config(args.run_config) if args.run_config else load_default_run_config(args.mode, args.agent_type)
    )
    if args.enable_hf_backup:
        hf_backup_enabled: bool | None = True
    elif args.disable_hf_backup:
        hf_backup_enabled = False
    else:
        hf_backup_enabled = None
    return merge_run_config_overrides(
        config,
        run_id=args.run_id,
        output_root=args.output_root,
        overwrite=True if args.overwrite else None,
        resume=args.resume,
        dry_run=True if args.dry_run else None,
        judge_enabled=True if args.run_judge_pipeline else None,
        dataset_manifest=args.dataset_manifest,
        selection_manifest=args.selection_manifest,
        hf_backup_enabled=hf_backup_enabled,
        hf_backup_strict=True if args.hf_backup_strict else None,
        hf_backup_batch_size=args.hf_backup_batch_size,
        hf_backup_primary_repo=args.hf_backup_primary_repo,
        hf_backup_secondary_repo=args.hf_backup_secondary_repo,
        hf_backup_dry_run=True if args.hf_backup_dry_run else None,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = resolve_config(args)
    if args.preflight_only:
        report = run_preflight(config)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1
    print(json.dumps(run_phase4_v2(config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
