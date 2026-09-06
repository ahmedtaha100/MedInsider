# Expert agreement

The completed study contains 120 payloads rated by four reviewers, yielding 480 responses. It supersedes the earlier unfilled two-reviewer planning template.

| Question | Yes responses | Fleiss kappa | Interpretation |
| --- | --- | --- | --- |
| Q1: clinical validity | 470/480 (97.9%) | -0.018 | Dominant Yes prevalence; high raw agreement does not remove scorer/design uncertainty |
| Q2: integrity violation | 351/480 (73.1%) | 0.905 | 111 unanimous payloads and nine 3-1 splits |
| Q3: scorer agreement | 471/480 (98.1%) | -0.017 | Eight No responses and one Scorer hidden response |

Q2 had nine dissenting individual ratings. The eight Q3 No responses are a different count. The scorer matched all 120 Q2 majority labels (90 positive, 30 negative). Q2 displayed the scorer's selected option; these are scorer-assisted judgments, not an unanchored validation set.

Exact pairwise counts and statistics remain in [kappa_tables.csv](kappa_tables.csv) and [kappa_tables_20260505.csv](kappa_tables_20260505.csv). [validation_summary_120.csv](validation_summary_120.csv) supports the majority-label comparison. `make validate-validation` verifies that summary and reconstructs all 30 kappa rows and response marginals from 20 anonymous joint-rating frequency rows. These question-specific aggregates were derived from the 480 privately verified original responses; they omit payload IDs, reviewer identities, timestamps and cross-question links. Identifying exports and payload-linked individual ratings remain private. Earlier availability statements in the frozen validation report describe the historical release.
