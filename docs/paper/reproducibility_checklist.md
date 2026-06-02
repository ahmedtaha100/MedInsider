# Reproducibility Checklist

Status note: this checklist reflects the current verified repository state as
of `2026-05-05`, after targeted reruns and post-rerun scored-output locking.

## For all papers

- [x] Claims can be narrowed to artifact-backed statements.
- [x] Limitations can be stated explicitly.
- [x] The scoring specification is on disk and self-contained.

## For datasets and benchmarks

- [x] Local code and local dataset artifacts are versioned in the repo.
- [x] Licensing files exist locally.
- [ ] Dataset is publicly released already.
- [ ] Croissant metadata is finished.
- [ ] Reviewer smoke bundle is finished.
- [ ] Public release package is complete.
- [ ] MIMIC-IV-FHIR real-chart subset is part of the current package.

## For experiments

- [x] Executed seven-model run manifests are pinned on disk.
- [x] Seeds and runtime settings are recorded in run manifests.
- [x] Run-level logs, episode artifacts, scored outputs, and pair summaries are preserved.
- [x] Backup and restore provenance exists for completed lanes.
- [ ] Expert validation has nonzero evaluated rows.
- [ ] Inter-rater kappa outputs exist.
- [x] Coding-knowledge probe outputs exist.
- [x] Dedicated structural mitigation outputs exist.
- [x] Paper-facing seven-model tables are regenerated.
- [ ] Paper-facing seven-model figures are fully materialized.

## For reproducibility

- [x] `make reproduce` exists for local v2/FHIR smoke reproduction.
- [x] Frozen manifests and run manifests are on disk.
- [x] Local authoritative smoke path is documented in `docs/protocol/v2_fhir_pilot_runbook.md`.
- [ ] Public subset is already packaged in final reviewer-facing form.
- [ ] All headline claims are currently reproducible from a packaged public release.

## For evaluation and validation

- [x] Integrity and compliance metrics are defined in the scoring spec and code.
- [x] `ATC` is present as a co-primary metric in current scored outputs.
- [ ] Expert validation with completed labels exists.
- [ ] Scorer validation with nonzero evaluated rows exists.
- [ ] Inter-rater agreement with real completed reviewer rows exists.

## Bottom line

Reproducibility is strong for the executed seven-model run package itself.
The coding probe and bounded structural mitigation are now reproducible from
repo-local artifacts. Submission-facing validation, release packaging, and
figure materialization remain incomplete and must be described as such.
