# External User Friction Inventory 20260505

## Blockers

| Issue | Impact | Classification | Status |
|---|---|---|---|
| `make reproduce` fails in a fresh clone because two restore-path tests fail. | A reviewer following the manuscript-level one-command path will not reach the smoke run. | fix-now | Code/build-target decision required; documented in `docs/release/smoke_path_verification.md`. |
| Final paper-packet builder fails in a fresh clone because authoritative run roots are not present. | External users cannot regenerate all final paper CSVs from tracked files alone. | fix-before-public-release | Packaging or builder change required; documented in `docs/release/reproducibility_chain_verification.md`. |

## Significant Friction

| Issue | Impact | Classification | Status |
|---|---|---|---|
| The top-level README did not previously point to an external new-model guide. | Users could miss the config-only path for supported model adapters. | fix-before-public-release | Fixed by adding release entry-point links and `docs/release/new_model_onboarding.md`. |
| `--agent-type` CLI choices hide `openai_compatible` and `openweight`. | Users may think new provider lanes require code changes. | fix-before-public-release | Documented in `docs/release/new_model_onboarding.md`. |
| Croissant file lacked several explicit RAI fields requested for release review. | Dataset metadata looked incomplete for E&D requirements. | fix-before-public-release | Fixed in `submission/reviewer_bundle/croissant.json`; documented in `docs/release/croissant_rai_verification.md`. |
| No consolidated third-party asset/license inventory existed. | Release reviewers would need to infer provider/model terms manually. | fix-before-public-release | Fixed in `docs/asset_licenses.md`; upstream terms still require final human confirmation. |
| HF backup configs in historical full-run configs contain private repository targets. | External users need to deliberately configure their own backup repositories. | acceptable with documentation | `docs/release/new_model_onboarding.md` tells users to keep HF backup disabled until configured. |

## Minor Friction

| Issue | Impact | Classification | Status |
|---|---|---|---|
| The README remains informal in tone in its explanatory diagram. | Does not block running the benchmark, but may feel less polished for reviewers. | acceptable | Release-oriented entry points were added without rewriting the README wholesale. |
| Historical/legacy scripts remain in the tree. | Users may choose the wrong path if they skip README guidance. | acceptable | README identifies the v2/FHIR path as authoritative and marks legacy surfaces as not recommended. |
| Full provider-backed reproduction requires API keys and provider quota. | Expected limitation for external model runs. | acceptable | Documented as a provider requirement. |
| Local open-weight reproduction requires a compatible inference server and hardware. | Expected limitation for open-weight lanes. | acceptable | Documented in `docs/release/new_model_onboarding.md`. |

## Documentation Gaps Fixed In This Pass

| Gap | Fix |
|---|---|
| New model onboarding | Added `docs/release/new_model_onboarding.md`. |
| Environment setup summary | Added `docs/release/environment_setup.md`. |
| Cold-clone walkthrough | Added `docs/release/cold_clone_walkthrough.md`. |
| Smoke path verification | Added `docs/release/smoke_path_verification.md`. |
| Croissant RAI metadata verification | Added `docs/release/croissant_rai_verification.md` and updated `submission/reviewer_bundle/croissant.json`. |
| Reproducibility chain status | Added `docs/release/reproducibility_chain_verification.md`. |
| Asset licenses | Added `docs/asset_licenses.md`. |

## Currently Working

- Fresh clone and editable install with dev extras.
- Direct provider-free smoke path: `make preflight-v2 smoke-v2`.
- Manifest loading, pair validation, FHIR-shaped tool execution, action logging, scoring, and aggregate output generation on the smoke set.
- Config-based model onboarding for `openai`, `claude`, `openai_compatible`, and `openweight` adapters.
- Locked artifact hash checks in the release-preparation workspace.
- Validation tool dependency manifest and Dockerfile.
- Croissant metadata presence after this pass.

## Remaining Decisions

1. Fix the restore-path tests or narrow the `make reproduce` target before release.
2. Decide how external users should rebuild final paper CSVs: package authoritative run roots, provide a restore script/source, or change the packet builder to consume the locked CSV packet.
3. Confirm provider/model terms URLs in `docs/asset_licenses.md` immediately before public release.
