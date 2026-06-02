# Release Readiness 20260601

## Reviewer Smoke Path

Ready.

The canonical reviewer command is:

```bash
make reproduce
```

In the remediation clone, the command passed with Python 3.11. It ran preflight,
selected 2 episodes / 1 pair, and completed the provider-free scripted smoke run
with 2 / 2 successful scored rows.

## Reviewer-Safe Test Target

Ready.

The clean-clone-safe target is:

```bash
make reviewer-test
```

It runs Ruff, validates the final paper packet from bundled per-episode scored
outputs, and runs preflight.

The broader fixture-dependent pytest suite is intentionally separated as:

```bash
make internal-test
```

## Paper Packet Builder

Ready for tracked-artifact validation.

`code/scripts/build_final_supported_packet.py` now consumes
`data/scored_outputs/per_episode/*_scored_episodes.csv` and validates the main
paper CSV layer without untracked restore roots.

## External Model Evaluation

Supported with adapter caveats.

The runtime supports config-based evaluation for `openai`, `claude`,
`openai_compatible`, and `openweight` routes. A provider with a custom,
non-OpenAI-compatible API still requires adapter code.

## Remaining Human Checks

| Item | Status |
|---|---|
| Provider/model terms | External terms should still be re-confirmed before public release. |
| Full provider-backed reruns | Require API credentials, provider quota, and hardware for local open-weight lanes. |
| HF dataset release | Requires the separate HF remediation/upload pass. |
