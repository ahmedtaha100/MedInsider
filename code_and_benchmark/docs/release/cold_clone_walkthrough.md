# Cold Clone Walkthrough 20260505

## Method

I created a temporary fresh checkout from the current repository, set up a new virtual environment, installed the package with dev extras, read the top-level README as a first-time user, and ran the documented local health paths.

No provider credentials were used.

## What A New User Sees First

The top-level `README.md` introduces MedInsider as a benchmark for documentation and care integrity under institutional pressure. It identifies the authoritative v2/FHIR path:

- `artifacts/v2_manifest.csv`
- `scripts/run_phase4_v2.py`
- `scripts/preflight_phase4_v2.py`
- `src/medinsider/fhir/scoring.py`
- `docs/protocol/v2_fhir_pilot_runbook.md`

The README also distinguishes the legacy experiment surface from the current v2/FHIR runner.

## What Worked

| Check | Result |
|---|---|
| Fresh clone | Worked |
| Python environment setup | Worked with Python 3.11 |
| `python -m pip install -e ".[dev]"` | Worked |
| `make preflight-v2 smoke-v2` | Worked |
| Manifest loading | Worked |
| Scripted FHIR tool-loop execution | Worked |
| Local action-log and score generation | Worked |
| Provider-free scored output | Worked, 2/2 smoke episodes scored successfully |

## What Was Confusing

1. The README's high-level explanation is accessible but informal for a NeurIPS reviewer or external benchmark user.
2. The README did not previously point to a dedicated "evaluate your own model" guide.
3. The command-line `--agent-type` shortcut exposes only `scripted`, `openai`, and `claude`, while the runtime also supports `openai_compatible` and `openweight` through `--run-config`.
4. `make reproduce` sounds like the smoke path, but it also runs the full test suite. In a fresh clone, that target currently fails two restore-path tests before reaching the smoke run.
5. The paper-packet builder depends on retained authoritative run directories that are not present in a clean clone from tracked files alone.

## Missing Or Unclear Pieces Found

| Area | Issue | Status after this pass |
|---|---|---|
| New-model onboarding | No single external-user guide existed. | Added `docs/release/new_model_onboarding.md`. |
| Environment setup | Python and validation-tool dependencies were split across files but not summarized for release users. | Added `docs/release/environment_setup.md`. |
| License inventory | Root code/data licenses existed, but third-party assets and provider terms were not inventoried in one place. | Added `docs/asset_licenses.md`. |
| Croissant RAI metadata | Croissant existed but did not expose all requested RAI fields explicitly. | Updated `submission/reviewer_bundle/croissant.json` and documented verification. |
| Smoke/reproduce distinction | Direct smoke passed, stricter `make reproduce` failed. | Documented in `docs/release/smoke_path_verification.md`; code/build-target decision remains. |

## Cold-Clone Assessment

An external user can install the repo and run the provider-free smoke path. The repo is not yet fully "one-command reproducible" through `make reproduce`, because that target is blocked by two restore-path tests.

The most important reusability path, evaluating a new model, is supported for OpenAI, Claude, OpenAI-compatible APIs, and local OpenAI-compatible endpoints through config files. The path needed clearer documentation, which this pass adds.
