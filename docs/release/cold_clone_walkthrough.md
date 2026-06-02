# Cold Clone Walkthrough 20260601

## Method

A clean clone was set up with Python 3.11, installed with dev extras, and
tested without provider credentials.

## Working Reviewer Commands

```bash
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
make PYTHON=.venv/bin/python reproduce
make PYTHON=.venv/bin/python reviewer-test
```

Results:

| Check | Result |
|---|---|
| Editable install with dev extras | Passed |
| `make reproduce` | Passed |
| `make reviewer-test` | Passed |
| Provider-free smoke run | 2 / 2 successful scored episodes |
| Paper packet builder | Passed from bundled scored outputs |

## Internal Tests

The full pytest suite includes fixture-dependent/internal tests and is separated
from reviewer-safe checks:

```bash
make PYTHON=.venv/bin/python internal-test
```

Use `reproduce` and `reviewer-test` for clean-clone reviewer verification.

## Reuse Caveats

The adapter layer is reusable for OpenAI, Claude, OpenAI-compatible, and local
OpenAI-compatible endpoints. It is not a universal provider plugin system. Full
provider-backed reproduction requires external credentials, quota, and in the
open-weight case suitable inference hardware.
