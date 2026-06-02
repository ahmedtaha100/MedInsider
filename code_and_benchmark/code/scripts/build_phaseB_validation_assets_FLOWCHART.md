# build_phaseB_validation_assets.py FLOWCHART

```text
START
  |
  v
Parse CLI args
  |
  v
Ensure docs/validation and docs/design directories exist
  |
  v
Build stratified scenario realism sample
  |
  v
Write docs/validation/scenario_realism_results.csv
  |
  v
Build stratified episode labeling package
  |
  v
Generate blinded logs + docs/validation/blinded_gold_label_set.csv
  |
  v
Write docs/validation/internal_validation_predictions.csv (coordinator-only predictions)
  |
  v
Run distribution realism audit
  |
  v
Write docs/design/distribution_realism_audit.md
  |
  v
Write docs/validation/distribution_realism_counts.csv
  |
  v
Write docs/validation/phaseB_validation_assets_summary.json
  |
  v
END
```
