# MedInsider

**Dataset:** [ahmedtaha100/medinsider](https://huggingface.co/datasets/ahmedtaha100/medinsider)

MedInsider evaluates documentation integrity in synthetic clinical workflows
under institutional pressure. This repository contains the benchmark implementation, the 840-episode v2
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
make reviewer-test
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
- `make unit-test` (the supported offline unit suite)
- `make test-all` (alias for `make reviewer-test`)

The supported tests run against the released code and available fixtures.
Obsolete tests for unpublished legacy fixtures are excluded from this release.

On Windows PowerShell, create and activate the environment with
`py -3.11 -m venv .venv` and `.venv\Scripts\Activate.ps1`. After the same
editable install, GNU Make can run the targets above. Without Make, run the
equivalent commands directly:

```powershell
python code/scripts/preflight_phase4_v2.py --mode smoke --agent-type scripted
python code/scripts/run_phase4_v2.py --mode smoke --agent-type scripted --run-id reviewer_smoke --output-root runs --overwrite --disable-hf-backup
python code/scripts/build_final_supported_packet.py --output-root reports/paper
python code/scripts/validate_locked_scoring_targets.py
python code/scripts/validate_validation_artifacts.py
python -m pytest -q
python -m ruff check code
```

## Reproducibility Scope

`make reproduce` verifies the local benchmark path end-to-end on a 2-episode
smoke run: preflight, EHR environment, runner, scorer, and artifact writing.

`make reproduce-tables` rebuilds the main seven-model table, legacy tradeoff
summary, and condition breakdown from the frozen per-episode scored CSVs,
asserts equality with their released counterparts, and writes the packet under
`reports/paper/`. It also reconstructs coding-probe accuracy from the retained
105 question records (93 parsed answers and 12 errors) in
`data/scored_outputs/probes/coding_probe_question_results.csv`, using the frozen
probe bank and scorer. Original provider-payload extraction cannot be checked
from these parsed answers; token counts and other run metadata remain frozen.
The mitigation table is copied from its frozen summary; its 96 treatment logs
are not included. `make validate-locks` checks the original 29 artifact hashes and sizes.
`make validate-validation` checks the 120-row majority-label summary against the
released aggregate validation evidence. The original 480 individual reviewer
responses are not included.

These checks do not regenerate model responses. Model aliases, provider
implementations, and sampling can change new outputs. A provider-backed run
requires your own credentials and may incur costs. The experiment's recorded
results and scorer semantics remain frozen.

The anonymous supplement includes 5,862 of the 5,880 original tool-action logs.
After extracting its `action_logs/` directory, independently rescore them with:

```bash
python code/scripts/replay_action_logs.py --logs action_logs --allow-missing
```

Expected output is `"status": "incomplete"`, with 5,862 matches, 18 missing
logs, and zero score or hash mismatches. Without `--allow-missing`, incomplete
coverage exits with status 1. The missing logs belong to final targeted retries;
older attempts are not substituted. These are tool-action logs, not full
provider conversations.

To reproduce the archived descriptive pair-bootstrap intervals and aggregate
agreement sensitivity values from frozen outputs:

```bash
python -m pip install -e ".[analysis]"
python code/scripts/reproduce_uncertainty.py
```

Outputs go to `reports/uncertainty/`. The [analysis note](docs/paper/uncertainty/README.md)
documents the fixed seeds, 20,000 resamples, and interpretation limits.

The legacy `refused_misaligned_pressure` field is a conflict-label/zero-violation
proxy, not an observed refusal rate. Expert results are source/model-blinded,
scorer-assisted agreement. Read the [metric definitions](docs/paper/definitions.md),
[validation account](docs/validation/inter_rater_agreement.md), and
[limitations](docs/paper/limitations.md) when interpreting the unchanged numbers.

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

The `path` values inside `data/manifests/v2_manifest.csv` are relative to the
`data/` tree and are mirrored under `code/`. For example, resolve
`scenarios/phase2_v2/generated/<episode>.json` as
`data/scenarios/phase2_v2/generated/<episode>.json` or
`code/scenarios/phase2_v2/generated/<episode>.json`, not as a repository-root
path.

Count scenario JSON files under the `generated/` directory above. The broader
`data/scenarios/` tree also contains non-scenario artifact JSON, including the
generation summary.

Frozen table backing CSVs (original manuscript numbering; filenames remain
stable even where the Findings manuscript places a table in an appendix):

- Table 2 kappa statistics: `docs/validation/kappa_tables.csv`
- Table 3 scorer agreement: `docs/validation/validation_summary_120.csv`
- Table 4 seven-model results: `docs/paper/final_table3_seven_model_results.csv`
- Table 5 legacy tradeoff proxy/incomplete completion: `docs/paper/final_table4_refusal_partial.csv`
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

The hosted dataset is available at
[ahmedtaha100/medinsider](https://huggingface.co/datasets/ahmedtaha100/medinsider).
It contains the standalone scenario corpus, dataset manifests, Croissant
metadata, datasheet, licenses, and dataset documentation.

This GitHub repository contains the runnable code-and-benchmark bundle. Locked
scored outputs, validation summaries, reproduction scripts, and reviewer smoke
tests live here.

This public repository identifies its authors. For double-blind review, use the
separately prepared history-free anonymous supplement rather than linking this
repository or the named dataset from the manuscript.

## Licenses

Code is Apache 2.0 (`LICENSE`). Data and documentation artifacts are CC BY 4.0
(`DATA_LICENSE`). Third-party asset notes are in `docs/asset_licenses.md`.
Post-freeze citation metadata notes are in `docs/citation_metadata_notes.md`.
