# Smoke Path Verification 20260505

## Scope

This verification simulated a fresh external checkout and tested the provider-free local path. No provider credentials were used.

## `make reproduce`

Command:

```bash
make reproduce
```

Result: failed.

The target expands to:

```text
lint -> test -> refresh-manifests -> preflight-v2 -> smoke-v2
```

`ruff check` and `ruff format --check` passed. The full test suite then failed before manifest refresh or smoke execution:

```text
2 failed, 476 passed
```

Failing tests:

| Test | Failure surface |
|---|---|
| `tests/test_fhir_pilot_runtime.py::FHIRPilotRuntimeTests::test_resume_after_restore_uses_relative_paths` | Restored episode `log_path` did not start with restored run directory. |
| `tests/test_hf_backup.py::HFBackupTests::test_restore_prefers_more_recent_valid_repo_and_rewrites_paths` | Restored manifest `manifest_files.preflight_report_json` did not start with restored run directory. |

Interpretation: this is a restore-path test failure, not a provider-credential failure or dependency-install failure.

## Direct Provider-Free Smoke Path

Command:

```bash
make preflight-v2 smoke-v2
```

Result: passed.

Preflight evidence:

| Field | Value |
|---|---:|
| `ok` | `true` |
| Selected episodes | 2 |
| Selected pairs | 1 |
| Validated pairs | 1 |
| Provider credentials required | No |
| HF backup enabled | No |

Smoke output evidence:

| Output | Result |
|---|---|
| `runs/make_smoke/manifest/preflight_report.json` | Written |
| `runs/make_smoke/manifest/run_manifest.json` | Written |
| `runs/make_smoke/logs/*.jsonl` | 2 episode traces |
| `runs/make_smoke/scores/*.json` | 2 score payloads |
| `runs/make_smoke/artifacts/scored_episode_results.csv` | 2 scored rows plus header |
| `runs/make_smoke/artifacts/aggregate_scores.csv` | Written |
| `runs/make_smoke/summaries/failure_summary.json` | `episode_count=2`, `success=2`, `scored_episode_count=2` |

## External Reviewer Guidance

Until the restore-path tests are fixed, the clean provider-free command for reviewers is:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make preflight-v2 smoke-v2
```

`make reproduce` should not be represented as fully green in a fresh clone unless the two restore-path tests are resolved or the Makefile target is deliberately narrowed. That would be a code or build-target decision and was not changed in this documentation-only pass.
