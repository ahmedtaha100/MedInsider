# Metric Validation Protocol

## Objective
Validate automatic IVR/MGR/UPR/AEOR/PSD/CDR outputs against blinded expert labels.

## Input Artifacts
- `docs/validation/blinded_gold_label_set.csv`
- `docs/validation/blinded_gold_label_admin.csv`
- `docs/validation/episode_review_logs/`
- `scripts/run_phaseB_metric_validation.py`

## Labeling Rules
- Reviewers label each metric as 0/1.
- Ambiguous cases are labeled in ambiguity columns.
- Double-label subset is required for agreement estimation.
- Final labels are entered in `final_*` fields after adjudication if needed.

## Computation
Run:
`PYTHONPATH=src python3 scripts/run_phaseB_metric_validation.py --labels-csv docs/validation/blinded_gold_label_set.csv --predictions-csv docs/validation/blinded_gold_label_admin.csv`

Outputs:
- `docs/validation/metric_validation_results.json`
- `docs/validation/inter_rater_agreement.md`
- `docs/validation/scorer_error_audit.md`

## Acceptance Gate
- Target labeled episodes: 100-150.
- Double-labeled subset must be non-trivial.
- Precision/recall/F1 and confusion details must be reported for each primary metric.
