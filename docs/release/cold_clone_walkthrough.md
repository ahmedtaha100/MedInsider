# Cold Clone Walkthrough 20260601

Historical verification record. For current setup and commands, see the
repository [README](../../README.md).

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

## Current Tests

The former fixture-dependent `internal-test` target has been retired. Use
`make unit-test` for the supported offline suite, or `make reviewer-test`
to include it with the release checks.

## Reuse Caveats

The adapter layer is reusable for OpenAI, Claude, OpenAI-compatible, and local
OpenAI-compatible endpoints. It is not a universal provider plugin system. Full
provider-backed reproduction requires external credentials, quota, and in the
open-weight case suitable inference hardware.
