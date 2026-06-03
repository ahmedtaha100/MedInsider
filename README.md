# MedInsider

**Anonymous hosted dataset:** https://huggingface.co/datasets/anon-submission7979/medinsider

This repository is the anonymized reviewer supplementary bundle for
MedInsider. It contains the benchmark implementation, the 840-episode v2
scenario corpus, locked manifests, final table CSVs, validation artifacts, and
licenses.

## Reviewer Quick Start

Run these commands from the repository root. The smoke path is provider-free:
it does not call OpenAI, Anthropic, Hugging Face, or any other external model
API.

```bash
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

The canonical reviewer command is `make reproduce`. Additional reviewer-safe
checks are available as:

- `make reproduce-tables`
- `make validate-locks`
- `make validate-validation`
- `make reviewer-test`
- `make test-all` (alias for `make reviewer-test`)

Historical internal pytest tests depend on non-public fixture roots and are not
part of the public reviewer bundle. Use the reviewer-safe targets above for
clean-clone verification.

## Reproducibility Scope

`make reproduce` verifies the local benchmark path end-to-end on a 2-episode
smoke run: preflight, EHR environment, runner, scorer, and artifact writing.

Full reported table values are already materialized in the bundled CSVs listed
below. Re-running a provider-backed model lane requires your own API credentials
and may incur provider costs.

## Running With Your Own API

Use the smallest smoke manifest first.

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

- Full scenario corpus: `data/scenarios/phase2_v2/generated/`
- Main manifest: `data/manifests/v2_manifest.csv`
- Full-run manifest: `data/manifests/subsets/v2_full_run_manifest.csv`
- Smoke manifest: `data/manifests/subsets/v2_smoke_manifest.csv`

Count scenario JSON files under the `generated/` directory above. The broader
`data/scenarios/` tree also contains non-scenario artifact JSON, including the
generation summary.

Table backing CSVs:

- Table 2 kappa statistics: `docs/validation/kappa_tables.csv`
- Table 3 scorer agreement: `docs/validation/validation_summary_120.csv`
- Table 4 seven-model results: `docs/paper/final_table3_seven_model_results.csv`
- Table 5 refusal/partial results: `docs/paper/final_table4_refusal_partial.csv`
- Table 6 condition breakdown: `docs/paper/final_table5_condition_breakdown.csv`
- Table 7 coding probe: `docs/paper/final_table6_coding_probe.csv`
- Table 8 mitigation: `docs/paper/final_table7_mitigation.csv`

Per-episode scored outputs:

- Seven-model scored CSVs: `data/scored_outputs/per_episode/`
- Directory guide: `data/scored_outputs/per_episode/README.md`

Validation artifacts:

- Validation summary: `docs/validation/validation_results.md`
- 120-row Table 3 label summary: `docs/validation/validation_summary_120.csv`
- Expert panel description: `docs/validation/expert_panel.md`
- Review protocols: `docs/validation/metric_validation_protocol.md`
- Validation tool source: `validation/medinsider_validation_space/`

## Simulated FHIR/EHR Environment

The synthetic FHIR/EHR tool environment is included in the runnable benchmark
code and can be imported after the editable install above. It is a synthetic
benchmark environment, not a clinical system.

- State object: `code/src/medinsider/fhir/state.py`
- Tool environment: `code/src/medinsider/fhir/tools.py`
- Usage examples: `code/tests/test_fhir_tools.py`
- Runbook: `docs/protocol/v2_fhir_pilot_runbook.md`

Minimal import path:

```python
from medinsider.fhir import FHIRPatientEpisodeState, FHIRToolEnvironment

state = FHIRPatientEpisodeState.from_payload("example-episode", patient_state)
env = FHIRToolEnvironment(state)
result = env.dispatch("read_chart", {"patient_id": patient_state["patient_id"]})
```

Supported tool actions include `read_chart`, `read_note`, `write_note`,
`place_order`, `update_problem_list`, `submit_billing`, `message_staff`,
`discharge_plan`, `quality_report`, and `inbox_read`.

## Validation Tool Smoke Test

The Streamlit validation tool can be inspected locally without Hugging Face
write credentials:

```bash
cd validation/medinsider_validation_space
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py --server.headless true --server.port 8502
```

Then open `http://localhost:8502/`.

## Evaluating A New Model

See `docs/release/new_model_onboarding.md`. The short path is:

1. Copy `code/configs/phase4_v2/smoke_scripted.json`.
2. Change the model identifier and adapter settings in the copied config.
3. Run the documented preflight command.
4. Run the smoke benchmark and inspect the scored CSV under the new run id.

## Dataset Release

The anonymous hosted dataset is available at
https://huggingface.co/datasets/anon-submission7979/medinsider.
It contains the standalone scenario corpus, dataset manifests, Croissant
metadata, datasheet, licenses, and dataset documentation.

This GitHub repository contains the runnable code-and-benchmark bundle. Locked
scored outputs, validation summaries, reproduction scripts, and reviewer smoke
tests live here.

## Licenses

Code is Apache 2.0 (`LICENSE`). Data and documentation artifacts are CC BY 4.0
(`DATA_LICENSE`). Third-party asset notes are in `docs/asset_licenses.md`.
Post-freeze citation metadata notes are in `docs/citation_metadata_notes.md`.
