# Splits And Freeze Manifest

Historical v1.0 split proposal. The public-dev, public-validation, and private
hidden-test partitions below were not used for the frozen v2 results. All 840
v2 scenarios are released; see the current [datasheet](../../DATASHEET.md) and
[manifests](../../README.md#what-to-inspect). The original proposal is retained below.

## Split policy
MedInsider v1.0 uses three splits:
- `public_dev`
- `public_validation`
- `hidden_test` (private)

Assignments are stratified by:
- `scenario_family`
- `condition`
- `alignment_label`

Default fractions:
- `public_dev`: 0.50
- `public_validation`: 0.25
- `hidden_test`: 0.25

## Reproducible generation
Run:

```bash
PYTHONPATH=src python3 scripts/build_phaseA_artifacts.py \
  --dataset-dir scenarios/phase2 \
  --benchmark-version 1.0.0 \
  --seed 42
```

## Output locations
Public manifests:
- `scenarios/phase2/artifacts/phaseA_public_dev_manifest.csv`
- `scenarios/phase2/artifacts/phaseA_public_validation_manifest.csv`

Private manifest:
- `scenarios/phase2/private/hidden_test_manifest.csv`

Public integrity outputs:
- `scenarios/phase2/artifacts/phaseA_hidden_test_manifest.sha256`
- `scenarios/phase2/artifacts/phaseA_split_summary.csv`
- `scenarios/phase2/artifacts/phaseA_freeze_manifest.json`

## Access policy
- hidden-test manifest is not committed to public releases
- hidden-test scoring is controlled evaluation only
- hidden-test digest is published to support freeze integrity verification

## Freeze references
Freeze metadata and component versions are recorded in:
- `benchmark_versions/version_manifest.json`
