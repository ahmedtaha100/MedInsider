# MedInsider

This repository hosts the MedInsider code and benchmark bundle. The runnable
benchmark lives in `code_and_benchmark/`; that folder contains the benchmark
implementation, the 840-episode v2 scenario corpus, locked manifests, final
table CSVs, validation artifacts, and licenses.

## Reviewer Quick Start

Run this from the repository root. The smoke path is provider-free: it does not
call OpenAI, Anthropic, Hugging Face, or any other external model API.

```bash
cd code_and_benchmark
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
make reproduce
```

Expected result:

- install completes without manual dependency setup;
- preflight reports `"ok": true`;
- `make reproduce` exits with status 0;
- 2/2 smoke episodes are scored successfully;
- reviewer smoke artifacts are written under `code/runs/reviewer_smoke/`.

The canonical reviewer command is `make reproduce`. A developer test suite is
available via `make test-all`, but it includes fixture-dependent tests that may
fail in clean clones; reviewers do not need to run it.

## Reproducibility Scope

`make reproduce` verifies the local benchmark path end-to-end on a 2-episode
smoke run: preflight, EHR environment, runner, scorer, and artifact writing.

Full reported table values are already materialized in the bundled CSVs listed
below. Re-running a provider-backed model lane requires your own API credentials
and may incur provider costs.

## Running With Your Own API

From `code_and_benchmark/`, use the smallest smoke manifest first.

OpenAI:

```bash
export OPENAI_API_KEY=...
PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/smoke_openai.json \
  --preflight-only \
  --disable-hf-backup

PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/smoke_openai.json \
  --run-id openai_smoke \
  --disable-hf-backup \
  --no-resume
```

Anthropic:

```bash
export ANTHROPIC_API_KEY=...
PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/smoke_claude.json \
  --preflight-only \
  --disable-hf-backup

PYTHONPATH=code/src python code/scripts/run_phase4_v2.py \
  --run-config configs/phase4_v2/smoke_claude.json \
  --run-id claude_smoke \
  --disable-hf-backup \
  --no-resume
```

For OpenAI-compatible providers or local servers, copy
`code/configs/phase4_v2/smoke_scripted.json`, change the `agent` block, and
follow `docs/release/new_model_onboarding.md`.

Outputs are written to `code/runs/<run_id>/`; the main scored file is
`code/runs/<run_id>/artifacts/scored_episode_results.csv`.

## What To Inspect

Corpus and manifests:

- Full scenario corpus: `code_and_benchmark/data/scenarios/phase2_v2/generated/`
- Main manifest: `code_and_benchmark/data/manifests/v2_manifest.csv`
- Full-run manifest: `code_and_benchmark/data/manifests/subsets/v2_full_run_manifest.csv`
- Smoke manifest: `code_and_benchmark/data/manifests/subsets/v2_smoke_manifest.csv`

Table backing CSVs:

- Table 1 kappa statistics: `code_and_benchmark/docs/validation/kappa_tables.csv`
- Table 2 scorer agreement: `code_and_benchmark/docs/validation/validation_summary_120.csv`
- Table 3 seven-model results: `code_and_benchmark/docs/paper/final_table3_seven_model_results.csv`
- Table 4 refusal/partial results: `code_and_benchmark/docs/paper/final_table4_refusal_partial.csv`
- Table 5 condition breakdown: `code_and_benchmark/docs/paper/final_table5_condition_breakdown.csv`
- Table 6 coding probe: `code_and_benchmark/docs/paper/final_table6_coding_probe.csv`
- Table 7 mitigation: `code_and_benchmark/docs/paper/final_table7_mitigation.csv`

Per-episode scored outputs:

- Seven-model scored CSVs: `code_and_benchmark/data/scored_outputs/per_episode/`
- Directory guide: `code_and_benchmark/data/scored_outputs/per_episode/README.md`

Validation artifacts:

- Validation summary: `code_and_benchmark/docs/validation/validation_results.md`
- 120-row Table 2 label summary: `code_and_benchmark/docs/validation/validation_summary_120.csv`
- Expert panel description: `code_and_benchmark/docs/validation/expert_panel.md`
- Review protocols: `code_and_benchmark/docs/validation/metric_validation_protocol.md`
- Validation tool source: `code_and_benchmark/validation/medinsider_validation_space/`

## Validation Tool Smoke Test

The Streamlit validation tool can be inspected locally without Hugging Face
write credentials:

```bash
cd code_and_benchmark/validation/medinsider_validation_space
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py --server.headless true --server.port 8502
```

Then open `http://localhost:8502/`.

## Evaluating A New Model

See `code_and_benchmark/docs/release/new_model_onboarding.md`. The short path is:

1. Copy `code_and_benchmark/code/configs/phase4_v2/smoke_scripted.json`.
2. Change the model identifier and adapter settings in the copied config.
3. Run the documented preflight command.
4. Run the smoke benchmark and inspect the scored CSV under the new run id.

## Dataset Release

This repository contains the runnable code-and-benchmark bundle. The
standalone dataset release is intended to be hosted separately on Hugging Face
or another dataset host after review.

## Licenses

Code is Apache 2.0 (`code_and_benchmark/LICENSE`). Data and documentation
artifacts are CC BY 4.0 (`code_and_benchmark/DATA_LICENSE`). Third-party asset
notes are in `code_and_benchmark/docs/asset_licenses.md`.
