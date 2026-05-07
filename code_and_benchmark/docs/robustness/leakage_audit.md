# Lexical Leakage Audit

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
