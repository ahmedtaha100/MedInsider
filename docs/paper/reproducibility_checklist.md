# Reproducibility checks

Run the commands in the [repository guide](../../README.md) from the root:

- `make reproduce`: provider-free preflight and two-episode environment/runner/scorer smoke.
- `make reproduce-tables`: reconstruct the main, legacy-tradeoff, and condition tables from frozen score rows, plus coding-probe accuracy from 93 retained parsed answers and 12 errors. Verify equality with the frozen tables; copy the remaining auxiliary summaries and probe run metadata to `reports/paper/`.
- `make validate-locks`: verify all 29 original artifact byte counts and hashes.
- `make validate-validation`: verify the released 120-row majority-label summary and reproduce all 30 kappa rows and response marginals from 20 anonymous joint-rating frequency rows.
- `make reviewer-test`: run table, lock, and validation checks, lint, the supported existing unit suite, and preflight. Run `make reproduce` separately for the smoke execution.

The anonymous supplement also supports `python code/scripts/replay_action_logs.py --logs action_logs` for all 5,880 main episodes and `python code/scripts/replay_action_logs.py --logs mitigation_logs --mitigation` for all 96 treatment episodes and the mitigation table. Both require complete hash and score agreement. To write the reconstructed mitigation table into the packet, pass `--mitigation-supplement mitigation_logs` to `code/scripts/build_final_supported_packet.py`.

These checks do not regenerate provider responses. The 480 original expert responses were privately verified; identifying exports and payload-linked individual ratings remain private. See [release limitations](limitations.md) and [completed expert agreement](../validation/inter_rater_agreement.md). The historical planning checklist remains in Git history.
