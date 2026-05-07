# Benchmark Freeze Policy

## Scope
This policy defines how MedInsider benchmark v1.0 is frozen before final large-scale evaluation and paper claims.

## Freeze boundary
At freeze time, the following components are immutable for the benchmark version:
- scenario definitions
- split assignments
- authority records
- scoring rules
- reporting protocol for main claims

## Freeze trigger
Freeze occurs only after:
- expert realism review protocol is complete
- metric validation protocol is complete
- ambiguity routing policy is declared
- split manifests and private hidden-test manifest are generated

## Frozen artifacts
Freeze requires these artifacts:
- `scenarios/phase2/artifacts/phaseA_public_dev_manifest.csv`
- `scenarios/phase2/artifacts/phaseA_public_validation_manifest.csv`
- private hidden-test manifest at `scenarios/phase2/private/hidden_test_manifest.csv`
- hidden-test digest at `scenarios/phase2/artifacts/phaseA_hidden_test_manifest.sha256`
- freeze manifest `scenarios/phase2/artifacts/phaseA_freeze_manifest.json`
- authority records `scenarios/phase2/authority/phase2_authority_records.jsonl`
- version manifest `benchmark_versions/version_manifest.json`

## Post-freeze change control
Any post-freeze modification to scenarios, splits, scoring, or authority files requires:
- benchmark version bump
- changelog entry describing reason and impact
- rerun of affected analyses
- regenerated freeze manifest and version manifest

Results from a post-freeze changed benchmark must not be reported as the same benchmark version.

## Hidden-test governance
- hidden-test manifest is private and not included in public release
- public release includes only hidden-test manifest digest and split summary statistics
- hidden-test evaluation access is controlled and logged

## Claim discipline
- fully automatic scoring claims exclude records marked `non_automatically_scorable`
- ambiguous cases are routed to judge-assisted or appendix-only reporting
- final claims must cite the frozen benchmark version and scorer version
