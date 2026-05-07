#!/usr/bin/env python

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def main(argv: list[str] | None = None) -> int:
    from medinsider.fhir.pilot_runtime import run_preflight
    from medinsider.fhir.run_phase4_v2 import parse_args, resolve_config

    args = parse_args(argv)
    config = resolve_config(args)
    report = run_preflight(config)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
