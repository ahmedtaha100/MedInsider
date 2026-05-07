# Release Readiness 20260505

## 1. Can a NeurIPS reviewer cleanly run the smoke path?

Partially.

Yes for the direct provider-free smoke path:

```bash
make preflight-v2 smoke-v2
```

Evidence: fresh-clone preflight passed with `ok=true`, selected 2 episodes and 1 pair, and the smoke run produced 2/2 successful scored rows under `runs/make_smoke/`.

No for the stricter repository target:

```bash
make reproduce
```

Evidence: in a fresh Python 3.11 clone, `make reproduce` failed during the full test suite with 476 passing tests and 2 failing restore-path tests. The smoke path itself was not reached from that target.

Release decision needed: either fix the two restore-path tests or document `make preflight-v2 smoke-v2` as the reviewer smoke command.

## 2. Can an external user evaluate their own model on the benchmark?

Yes, with adapter-surface caveats.

The runtime supports config-based model evaluation for:

- `openai`
- `claude`
- `openai_compatible`
- `openweight`

The onboarding path is documented in `docs/release/new_model_onboarding.md`. Users can evaluate a new model without code changes if the model fits one of those adapter types. A provider with a custom, non-OpenAI-compatible API requires adapter code and is outside the current config-only path.

## 3. Are all licenses documented?

Mostly yes after this pass.

Local repository licensing is documented:

- Code: Apache 2.0 via `LICENSE`
- Data/docs/benchmark artifacts: CC BY 4.0 via `DATA_LICENSE`
- Reviewer bundle: includes license copies

This pass added `docs/asset_licenses.md` with provider/model terms, validation tool coverage, direct dependency licenses, and cited-source notes.

Caveat: upstream provider terms and cited benchmark licenses should be re-confirmed before public release because they are external and can change.

## 4. Is the Croissant file present with RAI metadata?

Yes.

Croissant file:

```text
submission/reviewer_bundle/croissant.json
```

This pass added explicit RAI metadata fields for intended use, out-of-scope use, known limitations, misuse risks, sensitive data status, and data collection methodology. Details are in `docs/release/croissant_rai_verification.md`.

## 5. Does the manuscript's claim of reusable infrastructure hold up?

Yes, with caveats.

The core benchmark infrastructure is reusable: scenario manifests, FHIR-shaped runtime, runner, scoring engine, smoke path, validation payloads, and config-based model adapters are present. The direct smoke path verifies local execution without provider credentials.

Caveats:

- The one-command `make reproduce` target is not green in a fresh clone because it includes two failing restore-path tests.
- Rebuilding final paper CSV packets from a clean clone requires authoritative run roots that are not guaranteed to be present from tracked files alone.
- Full seven-model reproduction requires provider access, API quota, and in the open-weight case compatible inference hardware.

## 6. Remaining Blockers Requiring Human Decision

| Blocker | Required decision |
|---|---|
| `make reproduce` fails two restore-path tests. | Fix tests/runtime restore path, or change release docs/manuscript to cite the direct smoke command. |
| Paper-packet builder depends on non-cold-clone run roots. | Package run roots, provide a documented HF restore path, or change builder to consume locked CSV artifacts. |
| Provider/model terms are external. | Confirm terms before public release. |
| HF backup repository targets in checked-in configs are release-specific. | Replace with placeholders or document that users must provide their own HF backup repos. |

## Overall Assessment

Release state: minor-to-substantial edits needed before public release, depending on whether the one-command reproduction claim remains in the paper.

The benchmark can be used locally through the direct smoke path and can evaluate new models through supported adapters. The largest release-readiness issue is that the stricter `make reproduce` command and final packet builder are not fully cold-clone reproducible today.
