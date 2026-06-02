# New Model Onboarding

This guide describes the model-evaluation path that the current codebase actually supports. It assumes a fresh clone of the repository and uses the authoritative v2/FHIR runner.

All shell commands in this guide should be run from the bundle root: the directory containing `Makefile`, `pyproject.toml`, and the `code/` folder. Command paths are bundle-root-relative for `PYTHONPATH` and scripts. Run config paths are resolved by the runner relative to the `code/` package root, so a config stored at `code/configs/phase4_v2/my_model_smoke.json` is passed as `configs/phase4_v2/my_model_smoke.json`.

## Supported Adapter Paths

The runtime supports these agent types in `code/src/medinsider/fhir/pilot_runtime.py`:

| Agent type | Use case | Credential path |
|---|---|---|
| `scripted` | Provider-free smoke tests using reference actions. | None |
| `openai` | OpenAI API models supported by the built-in OpenAI adapter. | `OPENAI_API_KEY` |
| `claude` | Anthropic Claude models supported by the built-in Claude adapter. | `ANTHROPIC_API_KEY` |
| `openai_compatible` | Hosted providers or local servers that expose an OpenAI-compatible chat completions API. | `api_key_env` or inline `api_key` |
| `openweight` | Local/open-weight model served through an OpenAI-compatible endpoint, such as a vLLM server. | Optional `api_key`; usually local endpoint only |

Adding a model is config-only if the model can use one of these adapters. A provider with a non-OpenAI-compatible API requires a new adapter and is outside the current documentation-only release path.

The command-line `--agent-type` shortcut currently exposes only `scripted`, `openai`, and `claude`. Use `--run-config` for `openai_compatible` and `openweight` lanes.

## Minimal Config For An OpenAI-Compatible Provider

Create a JSON config under `code/configs/phase4_v2/`, for example `code/configs/phase4_v2/my_model_smoke.json`:

```json
{
  "run_name": "phase4_v2_my_model_smoke",
  "dataset_manifest": "artifacts/v2_manifest.csv",
  "selection_manifest": "artifacts/subsets/v2_smoke_manifest.csv",
  "output_root": "runs",
  "agent": {
    "type": "openai_compatible",
    "provider": "my_provider",
    "requested_model": "my-model-id",
    "base_url": "https://provider.example/v1",
    "api_key_env": "MY_PROVIDER_API_KEY",
    "max_tokens": 1024,
    "temperature": 0
  },
  "runtime": {
    "seed": 42,
    "context_window_pairs": 8,
    "request_timeout_seconds": 120,
    "max_episode_retries": 2,
    "retry_backoff_seconds": 1.0,
    "require_complete_pairs": true,
    "resume": true,
    "overwrite": false,
    "dry_run": false,
    "judge_enabled": false
  },
  "hf_backup": {
    "enabled": false
  }
}
```

Then run:

```bash
export MY_PROVIDER_API_KEY=...
PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/my_model_smoke.json \
  --preflight-only \
  --disable-hf-backup

PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/my_model_smoke.json \
  --run-id my_model_smoke \
  --disable-hf-backup \
  --no-resume
```

## Minimal Config For A Local Open-Weight Endpoint

Serve the model through an OpenAI-compatible local endpoint, then use `openweight`:

```json
{
  "run_name": "phase4_v2_my_openweight_smoke",
  "dataset_manifest": "artifacts/v2_manifest.csv",
  "selection_manifest": "artifacts/subsets/v2_smoke_manifest.csv",
  "output_root": "runs",
  "agent": {
    "type": "openweight",
    "provider": "local_vllm",
    "requested_model": "org/model-name",
    "base_url": "http://127.0.0.1:8000/v1",
    "max_tokens": 1024,
    "temperature": 0
  },
  "runtime": {
    "seed": 42,
    "context_window_pairs": 8,
    "request_timeout_seconds": 120,
    "max_episode_retries": 2,
    "retry_backoff_seconds": 1.0,
    "require_complete_pairs": true,
    "resume": true,
    "overwrite": false,
    "dry_run": false,
    "judge_enabled": false
  },
  "hf_backup": {
    "enabled": false
  }
}
```

Run the same `--preflight-only` and full runner commands shown above.

## Choosing The Episode Set

Use the smallest path first:

| Purpose | Selection manifest |
|---|---|
| Provider-free smoke | `code/artifacts/subsets/v2_smoke_manifest.csv` |
| Small pilot | `code/artifacts/subsets/v2_small_pilot_manifest.csv` |
| Full seven-condition benchmark lane | `code/artifacts/subsets/v2_full_run_manifest.csv` |

The full manifest contains 840 episodes, organized as 420 paired twins. Provider-backed full runs can be expensive and should be tested with the smoke and pilot manifests first.

## Outputs To Inspect

Every run writes to `code/runs/<run_id>/`:

| Path | Meaning |
|---|---|
| `manifest/run_manifest.json` | Effective run metadata |
| `manifest/preflight_report.json` | Manifest, selection, and environment checks |
| `logs/*.jsonl` | Per-episode tool-action traces |
| `scores/*.json` | Per-episode scorer payloads |
| `artifacts/scored_episode_results.csv` | Main row-level scored output |
| `artifacts/aggregate_scores.csv` | Aggregate model metrics |
| `summaries/pair_summary.csv` | Paired-twin summary |
| `summaries/failure_summary.json` | Runtime status counts |
| `summaries/token_usage_summary.json` | Token accounting when provider usage is available |

To compare a new model against the released seven-model panel, use `artifacts/aggregate_scores.csv` and `artifacts/scored_episode_results.csv` from the new run alongside `docs/paper/final_table3_seven_model_results.csv`.

## Hugging Face Backup

HF backup is optional for local evaluation. Keep it disabled until repository targets and `HF_TOKEN` are configured:

```bash
PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/my_model_smoke.json \
  --run-id my_model_smoke \
  --disable-hf-backup
```

For authoritative long runs, configure private or public backup repositories deliberately before enabling `--enable-hf-backup`.

## Current Reuse Caveats

The adapter layer is reusable for OpenAI, Claude, OpenAI-compatible, and local OpenAI-compatible endpoints. It is not a universal provider plugin system. For clean-clone reviewer checks, use `make reproduce` and `make reviewer-test`; see `docs/release/smoke_path_verification.md`.
