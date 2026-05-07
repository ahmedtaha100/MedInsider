# Contamination And Versioning Policy

## Risk statement
Public benchmark artifacts can become training-contaminated over time as future models ingest released content.

## Dataset exposure model
MedInsider uses:
- public development split
- public validation split
- protected hidden-test split

Leaderboard and headline claims should prioritize protected-test evaluation when available.

## Release hygiene
- do not publish hidden-test manifest entries
- publish hidden-test digest only
- keep sensitive conflict scenarios gated or redacted by release tier policy

## Version dimensions
Maintain explicit versions for:
- scenario generator
- scenario set
- scorer
- evaluation protocol
- authority spec
- split policy

Version references are stored in:
- `benchmark_versions/version_manifest.json`

## Post-release contamination handling
If contamination evidence appears:
- flag affected version in leaderboard policy
- rotate held-out scenarios in next benchmark version
- rerun baseline and model anchors on new protected split

## Longitudinal API drift plan
- record exact API model identifiers and evaluation dates in model run manifests
- schedule periodic reruns on open-model anchor subset
- report drift as a versioned addendum, not as silent replacement of prior results

## Claim policy
Papers and reports must cite:
- benchmark version
- scorer version
- evaluation protocol version
- split policy version

Claims across versions must be labeled as cross-version comparisons.
