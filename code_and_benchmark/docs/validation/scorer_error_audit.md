# Scorer Error Audit

Labels file: `docs/validation/blinded_gold_label_set.csv`
Current validation report: `docs/validation/validation_results.md`
Requested top-k in legacy Phase B workflow: `10`

The completed four-reviewer validation report found no scorer-vs-expert
mismatches for the any-integrity-metric verdict against adjudicated Q2 majority:
120 / 120 correct.

The older admin prediction CSV used by the Phase B helper workflow is not
included in the submitted reviewer bundle. Use `validation_results.md`,
`validation_summary_120.csv`, and `q2_dissent_adjudications.csv` as the current
validation evidence.
