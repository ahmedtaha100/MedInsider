# Environment Setup Verification 20260505

## Dependency Manifest

The canonical Python dependency manifest is `pyproject.toml`, not `requirements.txt`.

Observed project settings:

| Item | Verified value |
|---|---|
| Package name | `medinsider` |
| Python requirement | `>=3.10` |
| Runtime dependencies | `huggingface_hub>=0.31`, `matplotlib>=3.8` |
| Dev dependencies | `ruff>=0.4`, `pytest>=7.0`, `coverage[toml]>=7.4` |
| Console entry point | `medinsider-run = medinsider.cli:main` |

Fresh editable installs with dev extras completed successfully in a temporary clone using Python 3.11.

## Validation Tool Dependencies

The validation tool has a separate dependency manifest at `validation/medinsider_validation_space/requirements.txt`:

| Dependency | Version |
|---|---|
| `streamlit` | `1.57.0` |
| `huggingface_hub` | `1.13.0` |
| `httpx` | `0.28.1` |
| `requests` | `2.33.1` |

The validation Space Dockerfile uses `python:3.11-slim`, installs the requirements file, runs Streamlit on port 7860, and includes a basic health check.

## System-Level Requirements

Minimum local benchmark smoke path:

- Python 3.10 or newer
- `git`
- `make`
- A POSIX shell for the documented macOS/Linux commands

Additional optional requirements:

- Provider API keys for provider-backed runs (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or provider-specific variables such as `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY`, `ZHIPU_API_KEY`)
- A local OpenAI-compatible inference endpoint for `openweight` runs
- GPU/cloud resources for large open-weight runs
- Hugging Face credentials for backup or validation Space deployment
- LaTeX tooling only for rebuilding the manuscript PDF, not for running the benchmark

## Fresh Clone Result

Fresh setup command sequence:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

Result: install succeeded.

Direct smoke command:

```bash
make preflight-v2 smoke-v2
```

Result: passed. The smoke run selected 2 episodes, validated 1 paired twin, and produced 2 scored successful rows under `runs/make_smoke/`.

Stricter health check:

```bash
make reproduce
```

Result: failed during the full test suite, before manifest refresh and smoke execution. The failure is not a missing dependency; it is two restore-path assertions:

- `tests/test_fhir_pilot_runtime.py::FHIRPilotRuntimeTests::test_resume_after_restore_uses_relative_paths`
- `tests/test_hf_backup.py::HFBackupTests::test_restore_prefers_more_recent_valid_repo_and_rewrites_paths`

The captured run reported 476 passing tests and 2 failing tests under Python 3.11. This is a release blocker for the manuscript-level claim that `make reproduce` is the clean smoke path, unless the tests are fixed or the documented smoke target is narrowed.

## Setup Assessment

Dependency setup is mostly complete and clean. The earlier `huggingface_hub` gap is now covered in both the core `pyproject.toml` and the validation Space requirements.

Remaining setup blocker: `make reproduce` is not green in a fresh clone because it includes the full test suite. The direct scripted smoke path is green.
