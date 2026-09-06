# Reproducibility checks

Run the commands in the [repository guide](../../README.md) from the root:

- `make reproduce`: provider-free preflight and two-episode environment/runner/scorer smoke.
- `make reproduce-tables`: reconstruct three table families from frozen scored rows; copy the other frozen auxiliary summaries to `reports/paper/`.
- `make validate-locks`: verify all 29 original artifact byte counts and hashes.
- `make validate-validation`: verify the released 120-row majority-label summary.
- `make reviewer-test`: run table, lock, and validation checks, lint, the supported existing unit suite, and preflight. Run `make reproduce` separately for the smoke execution.

These checks do not regenerate provider responses or the unavailable original 480-response expert export. See [release limitations](limitations.md) and [completed expert agreement](../validation/inter_rater_agreement.md). The historical planning checklist remains in Git history.
