# Lexical Leakage Audit

Historical audit of the earlier 1,200-episode corpus (840 train and 360 test
episodes). These classifier results and the proposed redaction do not describe
the frozen v2 release of 840 episodes and are not evidence of leakage control
for its reported results. See the current [datasheet](../../DATASHEET.md).
The original audit is retained below as provenance.

Dataset source: `scenarios/phase2`
Train size: `840`
Test size: `360`

| Target | Raw Accuracy | Redacted Accuracy | Delta | Status |
|---|---:|---:|---:|---|
| scenario_family | 1.0000 | 0.6944 | 0.3056 | improved |
| condition | 1.0000 | 0.6917 | 0.3083 | improved |
| alignment_label | 1.0000 | 0.6250 | 0.3750 | improved |

Redaction removes explicit family/condition/alignment markers from prompt text.
If redacted accuracy remains high, add further paraphrase and structure randomization before final benchmark freeze.
