# Ready for Human Labeling

Status note: this file originally marked the human-labeling boundary. The
four-reviewer validation engagement is now complete, and the completed outputs
are recorded under `docs/validation/validation_results.md`,
`docs/validation/kappa_tables.csv`, and
`docs/validation/validation_summary_120.csv`. The 9 non-unanimous 3-1
adjudications are separately recorded in
`docs/validation/q2_dissent_adjudications.csv`.

## Locked scoring target

The post-rerun authoritative scored outputs are locked for validation in:

- `docs/validation/locked_scoring_targets.json`

Do not modify the authoritative scored outputs, regenerated paper table CSVs, or
validation assets listed in that lock before validation completes. If any scored
output must change, invalidate the lock and create a replacement lock before
assigning or continuing reviewer labels.

## Assets prepared now

- blinded episode label set:
  - `docs/validation/blinded_gold_label_set.csv`
  - `120` blinded episode rows
- admin crosswalk with model predictions and hidden metadata:
  - `docs/validation/blinded_gold_label_admin.csv`
  - `120` rows
- per-episode review logs:
  - `docs/validation/episode_review_logs/`
  - `120` JSONL files
- stratified scenario realism sample:
  - `docs/validation/scenario_realism_results.csv`
  - `200` scenario rows
- realism/distribution summary:
  - `docs/validation/distribution_realism_counts.csv`
  - `docs/design/distribution_realism_audit.md`
- validation asset summary:
  - `docs/validation/phaseB_validation_assets_summary.json`
- validation tool reviewer assignment:
  - Option A full overlap
  - `R1`, `R2`, `R3`, and `R4` each receive the same `120` episodes
  - expected total label submissions: `480`

## Human actions completed

1. The four-reviewer full-overlap panel completed 480 / 480 submissions.
2. Non-unanimous Q2 cases were adjudicated by majority rule.
3. Kappa tables and scorer-vs-expert validation summaries were generated.

## Completed outputs

- `docs/validation/validation_results.md`
- `docs/validation/kappa_tables.csv`
- `docs/validation/validation_summary_120.csv`
- `docs/validation/q2_dissent_adjudications.csv`

## Current truth

- validation packaging is real and was used for the completed four-reviewer panel
- scorer validation against adjudicated expert majority is complete for the
  120-episode validation set
- post-validation manuscript revisions should use the completed outputs listed
  above
