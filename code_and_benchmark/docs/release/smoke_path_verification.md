# Smoke Path Verification 20260601

## Scope

This verification tested the provider-free local reviewer path in the
remediation clone. No provider credentials were used.

## `make reproduce`

Command:

```bash
make PYTHON=.venv/bin/python reproduce
```

Result: passed.

The target expands to:

```text
preflight-v2 -> smoke-v2
```

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
| `code/runs/reviewer_smoke/manifest/preflight_report.json` | Written |
| `code/runs/reviewer_smoke/manifest/run_manifest.json` | Written |
| `code/runs/reviewer_smoke/artifacts/scored_episode_results.csv` | 2 scored rows plus header |
| `code/runs/reviewer_smoke/artifacts/aggregate_scores.csv` | Written |
| `code/runs/reviewer_smoke/summaries/failure_summary.json` | `episode_count=2`, `success=2`, `scored_episode_count=2` |

## Reviewer-Safe Checks

Command:

```bash
make PYTHON=.venv/bin/python reviewer-test
```

Result: passed.

The reviewer-safe test target runs:

- `ruff check code`
- `code/scripts/build_final_supported_packet.py`
- `preflight-v2`

The full fixture-dependent pytest suite remains available as:

```bash
make PYTHON=.venv/bin/python internal-test
```
