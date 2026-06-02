# Metric Validation Protocol

## Current Status

This Phase B protocol is retained as provenance for the pre-panel scorer-check
workflow. It is superseded for submitted-artifact review by the completed
four-reviewer validation outputs:

- `docs/validation/validation_results.md`
- `docs/validation/kappa_tables.csv`
- `docs/validation/validation_summary_120.csv`
- `docs/validation/q2_dissent_adjudications.csv`

The completed validation package contains 120 blinded episodes, four reviewers,
and 480 submitted labels. Use those files for paper and artifact review.

## Legacy Objective

The original Phase B objective was to validate automatic IVR/MGR/UPR/AEOR/PSD/CDR
outputs against blinded expert labels before the final four-reviewer panel was
completed.

## Legacy Inputs

- `docs/validation/blinded_gold_label_set.csv`
- `docs/validation/episode_review_logs/`
- `scripts/run_phaseB_metric_validation.py`

The older admin crosswalk/prediction CSV is not part of the submitted reviewer
bundle. Do not use the legacy command path as current validation evidence.

## Submitted Validation Evidence

The current validation evidence is the completed panel summary and kappa package:

- 120 validation episodes.
- Four reviewers.
- 480 total submissions.
- Q2 adjudicated majority labels: 90 positive and 30 negative.
- Q2 Fleiss kappa: 0.905.
- Scorer-vs-expert majority agreement for any integrity metric: 120/120.
