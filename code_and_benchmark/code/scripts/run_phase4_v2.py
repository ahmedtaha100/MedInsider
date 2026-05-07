#!/usr/bin/env python

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


if __name__ == "__main__":
    from medinsider.fhir.run_phase4_v2 import main

    raise SystemExit(main())
