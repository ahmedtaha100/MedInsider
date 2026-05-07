#!/usr/bin/env python

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore an authoritative v2/FHIR run from HF backup.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", default="runs")
    parser.add_argument("--run-config", default=None)
    parser.add_argument("--hf-backup-primary-repo", default=None)
    parser.add_argument("--hf-backup-secondary-repo", default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def _repo_pairs(args: argparse.Namespace) -> list[tuple[str, str]]:
    from medinsider.fhir.hf_backup import resolve_backup_repo_pairs

    return resolve_backup_repo_pairs(
        run_config_path=args.run_config,
        primary_repo=args.hf_backup_primary_repo,
        secondary_repo=args.hf_backup_secondary_repo,
    )


def main(argv: list[str] | None = None) -> int:
    from medinsider.fhir.hf_backup import HF_TOKEN_ENV_NAMES, restore_run_from_hf

    args = parse_args(argv)
    token = ""
    for env_name in HF_TOKEN_ENV_NAMES:
        token = str(os.getenv(env_name, "")).strip()
        if token:
            break
    try:
        repo_pairs = _repo_pairs(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "run_id": args.run_id,
                    "error": f"{type(exc).__name__}:{exc}",
                },
                indent=2,
            )
        )
        return 1
    if not token:
        print(json.dumps({"ok": False, "run_id": args.run_id, "error": "hf_backup_token_missing"}, indent=2))
        return 1
    if not repo_pairs:
        print(json.dumps({"ok": False, "run_id": args.run_id, "error": "hf_backup_repo_missing"}, indent=2))
        return 1

    try:
        report = restore_run_from_hf(
            args.run_id,
            Path(args.output_root),
            repo_pairs,
            token=token,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "run_id": args.run_id,
                    "error": f"{type(exc).__name__}:{exc}",
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
