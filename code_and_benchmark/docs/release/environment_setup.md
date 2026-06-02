# Environment Setup Verification 20260601

## Dependency Manifest

The canonical Python dependency manifest is `pyproject.toml`.

| Item | Verified value |
|---|---|
| Package name | `medinsider` |
| Python requirement | `>=3.10` |
| Runtime dependencies | `huggingface_hub>=0.31`, `matplotlib>=3.8` |
| Dev dependencies | `ruff>=0.4`, `pytest>=7.0`, `coverage[toml]>=7.4` |
| Console entry point | `medinsider-run = medinsider.cli:main` |

Fresh editable install with dev extras completed successfully in the remediation
clone using Python 3.11.

## Validation Tool Dependencies

The validation tool has a separate dependency manifest at
`validation/medinsider_validation_space/requirements.txt`. The validation Space
Dockerfile uses `python:3.11-slim`, installs that requirements file, runs
Streamlit on port 7860, and includes a basic health check.

## System-Level Requirements

Minimum local benchmark smoke path:

- Python 3.10 or newer.
- `git`.
- `make`.
- A POSIX shell for the documented macOS/Linux commands.

Additional optional requirements:

- Provider API keys for provider-backed runs.
- A local OpenAI-compatible inference endpoint for `openweight` runs.
- GPU/cloud resources for large open-weight runs.
- Hugging Face credentials for backup or validation Space deployment.
- LaTeX tooling only for rebuilding manuscript PDFs, not for running the benchmark.

## Fresh Clone Commands

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make PYTHON=.venv/bin/python reproduce
make PYTHON=.venv/bin/python reproduce-tables
make PYTHON=.venv/bin/python validate-locks
make PYTHON=.venv/bin/python validate-validation
make PYTHON=.venv/bin/python reviewer-test
```

Verified results:

| Check | Result |
|---|---|
| Editable install with dev extras | Passed |
| `make reproduce` | Passed |
| `make reproduce-tables` | Passed |
| `make validate-locks` | Passed |
| `make validate-validation` | Passed |
| `make reviewer-test` | Passed |
| `ruff check code` | Passed |
| Paper packet builder | Passed |
| Provider-free smoke run | 2 / 2 successful scored episodes |

## Internal Suite

The full pytest suite is intentionally separated because it includes historical
and fixture-dependent tests:

```bash
make PYTHON=.venv/bin/python internal-test
```

Use `reproduce` and `reviewer-test` for clean-clone reviewer verification.
