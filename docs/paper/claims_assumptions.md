# Claims and evidence limits

Updated 2026-09-06 for the ML4H Findings manuscript. The original result values
remain frozen; these interpretations apply to the executed study.

| Claim | Evidence | Scope |
|---|---|---|
| Documentation discrepancies can be operationalized without inferring intent. | Frozen scorer, scenario state, tool-action logs, and [metric definitions](definitions.md). | Literal rules over a synthetic EHR simulation; no inference of intent or clinical deployment safety. |
| Task completion and documentation integrity diverge in the seven-model panel. | `final_table3_seven_model_results.csv` and the seven per-episode score tables. | Descriptive within-benchmark comparison, not cross-benchmark capability rankings or population failure rates. |
| A compliance gate reduces discrepancies on the tested subset. | `final_table7_mitigation.csv`. | Four models, 24 background-pressure episodes each, two families, with model-specific completion tradeoffs. |
| Scorer-assisted expert review supports aggregate integrity labels on sampled payloads. | [Majority labels](../validation/validation_summary_120.csv), [kappas](../validation/kappa_tables.csv), and [validation account](../validation/inter_rater_agreement.md). | 120 payloads, 85 unique episode IDs, 64 pair IDs; scorer choice was visible. Agreement is not independent accuracy validation. |

Pressure framing is a stylized contextual manipulation. There is no evidence
that it is a lower bound on deployment pressure or real-world misconduct.
Neutral twins retain the shared shortcut cue. The non-neutral conditions also
include controls and integrity-supporting interventions.

The legacy `refused_misaligned_pressure` label is a conflict-label/zero-flag
proxy. It does not establish refusal or resistance. PSD is structurally
untriggered, AEOR and CDR flag the same episode sets, and UPR-integrity has only
three positive outputs. Report ATC alongside integrity rates because no-action
and no-opportunity zeros can obscure incomplete work.

The 15-item coding probe is an auxiliary knowledge check with unanswered items,
not a test of multi-step tool competence. The pair-bootstrap intervals describe
resampling of the fixed benchmark pairs, not provider or between-run variability.

The release supports exact reconstruction of the main, legacy-tradeoff, and
condition tables from frozen score rows. The auxiliary probe and mitigation
tables are copied from frozen summaries. The anonymous supplement supplies
5,862 of 5,880 original action logs for independent rescoring; 18 final retry
logs and the original 480-response reviewer export remain unavailable.
See the [reproduction checklist](reproducibility_checklist.md) and
[limitations](limitations.md).
