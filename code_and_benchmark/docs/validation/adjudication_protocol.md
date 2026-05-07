# Adjudication Protocol

## Trigger Conditions
- Reviewer 1 and Reviewer 2 disagree on any metric label.
- Case is marked as ambiguous by either reviewer.
- Policy interpretation is institution-dependent.

## Workflow
1. Flag row for adjudication in `blinded_gold_label_set.csv`.
2. Assign adjudicator in `adjudicator_id`.
3. Adjudicator reviews scenario and log evidence.
4. Adjudicator writes final labels in `final_*` fields.
5. Record rationale in `notes`.
6. Update revision logs if scorer/policy changes are required.

## Outputs
- Finalized labels for metric validation.
- Ambiguity disposition list for appendix-only or judge-assisted handling.
