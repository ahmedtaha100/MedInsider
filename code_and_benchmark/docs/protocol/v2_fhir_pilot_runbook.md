# v2/FHIR Pilot Runbook

## Authoritative Path

Use the v2/FHIR manifest-driven path for all real pilot work:

- dataset manifest: `artifacts/v2_manifest.csv`
- smoke subset: `artifacts/subsets/v2_smoke_manifest.csv`
- small pilot subset: `artifacts/subsets/v2_small_pilot_manifest.csv`
- preflight: `scripts/preflight_phase4_v2.py`
- runner: `scripts/run_phase4_v2.py`

Do not use `scripts/run_phase4_experiments.py` for real benchmark runs. It is legacy/experiment-oriented.

## Required Environment Variables

- `scripted`: none
- `openai`: `OPENAI_API_KEY`
- `claude`: `ANTHROPIC_API_KEY`
- optional HF backup: `HF_TOKEN` or `HUGGINGFACE_HUB_TOKEN`
- optional HF backup repo targets: `HF_BACKUP_PRIMARY_REPO`, `HF_BACKUP_SECONDARY_REPO`

Judge usage is off by default in the checked-in configs. Enable it explicitly with `--run-judge-pipeline` only if you want post-run judge analysis.

## Refresh Manifests

If you regenerate or modify the committed v2 scenario JSONs, refresh the authoritative manifests:

```bash
PYTHONPATH=src python scripts/build_phase4_v2_manifests.py
```

## Preflight

Scripted smoke:

```bash
PYTHONPATH=src python scripts/preflight_phase4_v2.py --mode smoke --agent-type scripted
```

Scripted small pilot:

```bash
PYTHONPATH=src python scripts/preflight_phase4_v2.py --mode pilot --agent-type scripted
```

OpenAI small pilot:

```bash
export OPENAI_API_KEY=...
PYTHONPATH=src python scripts/preflight_phase4_v2.py --mode pilot --agent-type openai
```

Claude small pilot:

```bash
export ANTHROPIC_API_KEY=...
PYTHONPATH=src python scripts/preflight_phase4_v2.py --mode pilot --agent-type claude
```

Preflight checks:

- dataset manifest exists and resolves to scenario JSONs
- selection manifest resolves against the dataset manifest
- selected neutral/pressure pairs pass pair-integrity validation
- required provider environment variables exist
- runtime settings are sane
- output root is writable
- checked-in subset expectations match the intended pilot shape

The checked-in small pilot is the operational 15-pair subset for launch-path validation.
It is not the larger statistical pilot described elsewhere in planning material.

## Smoke Run

```bash
PYTHONPATH=src python scripts/run_phase4_v2.py --mode smoke --agent-type scripted
```

Optional provider-backed smoke:

```bash
export OPENAI_API_KEY=...
PYTHONPATH=src python scripts/run_phase4_v2.py --mode smoke --agent-type openai
```

## Small Pilot Run

Scripted:

```bash
PYTHONPATH=src python scripts/run_phase4_v2.py --mode pilot --agent-type scripted
```

OpenAI:

```bash
export OPENAI_API_KEY=...
PYTHONPATH=src python scripts/run_phase4_v2.py --mode pilot --agent-type openai
```

Claude:

```bash
export ANTHROPIC_API_KEY=...
PYTHONPATH=src python scripts/run_phase4_v2.py --mode pilot --agent-type claude
```

## Optional Hugging Face Backup

HF backup is disabled by default. When enabled, the authoritative runtime mirrors
the current run into two private HF dataset repos in deterministic run-ID-prefixed
paths:

- `<run_id>/manifest/...`
- `<run_id>/logs/...`
- `<run_id>/scores/...`
- `<run_id>/summaries/...`
- `<run_id>/artifacts/...`

Checkpoint sync happens:

- after manifest / preflight files are written
- after each configured batch of completed episodes
- at final completion

Enable it with CLI flags:

```bash
export HF_TOKEN=...
export HF_BACKUP_PRIMARY_REPO=your-org/medinsider-primary-backup
export HF_BACKUP_SECONDARY_REPO=your-org/medinsider-secondary-backup
PYTHONPATH=src python scripts/run_phase4_v2.py \
  --mode pilot \
  --agent-type openai \
  --enable-hf-backup \
  --hf-backup-batch-size 5
```

Useful options:

- `--hf-backup-strict`: abort the run if both repos fail for a checkpoint
- `--hf-backup-dry-run`: exercise the local checkpoint/metadata path without remote uploads
- `--hf-backup-primary-repo ...`
- `--hf-backup-secondary-repo ...`

The run writes local backup metadata to:

- `manifest/hf_backup_state.json`
- `summaries/hf_backup_summary.json`

These files are also backed up remotely and are used by the restore tooling.

HF backup is intended for the current benchmark artifact set. Do not use these
HF dataset repos as a storage path for real PHI or regulated production data.

### What Gets Uploaded

The backup mirrors the run directory content needed for restore/audit, including:

- manifest files: effective config, run manifest, preflight report, resolved selection, copied dataset manifest, copied selection manifest
- per-episode logs
- per-episode score JSONs
- per-episode artifact JSONs used by resume
- aggregate CSVs and summary JSONs
- backup state / summary metadata

Files intentionally excluded:

- anything outside the run directory, including `apikeys.txt`
- environment dumps or token-bearing config
- temporary `*.tmp` files

### Verify Backup Health

```bash
export HF_TOKEN=...
PYTHONPATH=src python scripts/verify_phase4_v2_hf_backup.py \
  --run-id your_run_id \
  --hf-backup-primary-repo your-org/medinsider-primary-backup \
  --hf-backup-secondary-repo your-org/medinsider-secondary-backup
```

### Restore A Run

```bash
export HF_TOKEN=...
PYTHONPATH=src python scripts/restore_phase4_v2_from_hf.py \
  --run-id your_run_id \
  --output-root runs \
  --hf-backup-primary-repo your-org/medinsider-primary-backup \
  --hf-backup-secondary-repo your-org/medinsider-secondary-backup \
  --overwrite
```

The restore command chooses the most recent valid checkpoint between the primary
and secondary repos, recreates `runs/<run_id>/...`, rewrites local absolute paths
inside restored episode artifacts, and leaves the run in a shape that the existing
resume logic can reuse.

## Resume vs Overwrite

By default, the checked-in configs use resume behavior.

- rerun the same `run_id` with resume enabled to skip already completed episode artifacts
- restored runs keep the same `run_id`, so `--resume` continues from the latest restored checkpoint
- pass `--overwrite` to delete the existing run directory and rebuild it from scratch
- pass `--run-id <name>` if you want a stable run directory name

Examples:

```bash
PYTHONPATH=src python scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id local_smoke
PYTHONPATH=src python scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id local_smoke --overwrite
```

## Interpreting Outputs

Each run writes:

```text
runs/<run_id>/
  manifest/
  logs/
  scores/
  summaries/
  artifacts/
```

Most useful files:

- `manifest/run_manifest.json`: effective config, hashes, git SHA, selected subset metadata
- `manifest/preflight_report.json`: go/no-go validation result
- `artifacts/episode_results.csv`: one row per episode with runtime status and metrics
- `artifacts/aggregate_scores.csv`: condition-level means for the run
- `summaries/failure_summary.json`: status counts across the run
- `summaries/latency_summary.json`: end-to-end timing summary
- `summaries/token_usage_summary.json`: provider token totals when available
- `summaries/pair_summary.csv`: neutral vs pressure pair comparison rows

ATC note:

- ATC is deterministic, but it is no longer scored by literal equality against
  the canned `reference_actions` prose in the scenario JSONs.
- The authoritative scorer uses explicit tool-specific assertions derived from
  scenario family and chart state, so provider traces can earn ATC credit for
  clinically aligned actions without being fed scorer-target template strings.
- To audit how brittle the legacy `reference_actions` scaffold is across the
  full corpus, run `PYTHONPATH=src python scripts/audit_atc_reference_actions.py`.

Status taxonomy:

- `success`
- `api_failure`
- `timeout`
- `malformed_action_json`
- `invalid_action_schema`
- `unsupported_tool`
- `dispatch_failure`
- `min_call_constraint_violation`
- `max_call_termination`
- `scorer_failure`

## Local Validation

Scripted smoke is covered by automated tests and can also be run directly:

```bash
PYTHONPATH=src python -m unittest tests.test_fhir_pilot_runtime tests.test_run_phase4_v2_script -v
```
