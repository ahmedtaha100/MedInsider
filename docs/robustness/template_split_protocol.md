# Template Split Protocol

Historical split proposal for the earlier 1,200-episode corpus. These split
counts and the private holdout were not used for the frozen v2 results, which
cover 840 released episodes in 420 pairs. See the current
[datasheet](../../DATASHEET.md). The original proposal is retained below as provenance.

This split is template-aware and keeps template groups in a single split.

- Dataset source: `scenarios/phase2`
- Template groups: `675`
- Episode assignments: `1200`
- Public dev episodes: `720`
- Public validation episodes: `205`
- Holdout private episodes: `275`

Use `template_split == holdout_private` for final blinded reporting.
