# Artifacts Manifest For v2/FHIR Pilot

This directory contains the authoritative manifest surface for the v2/FHIR pilot path.

- `v2_manifest.csv` is the source-of-truth dataset manifest used by the real pilot runner.
- `subsets/v2_smoke_manifest.csv` is the checked-in smoke subset.
- `subsets/v2_small_pilot_manifest.csv` is the checked-in small pilot subset.

Refresh these files with:

```bash
PYTHONPATH=src python scripts/build_phase4_v2_manifests.py
```

These manifests resolve into the committed v2 scenario JSONs under `scenarios/phase2_v2/generated/`.
