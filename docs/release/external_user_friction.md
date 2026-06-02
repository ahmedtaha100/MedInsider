# External User Friction Inventory 20260601

## Reviewer-Facing Status

| Area | Status |
|---|---|
| Reviewer smoke path | `make reproduce` runs the provider-free smoke path. |
| Paper-packet builder | Validates from bundled per-episode scored outputs. |
| Reviewer-facing evidence paths | Point to shipped `docs/paper`, `docs/validation`, `data/manifests`, and `data/scored_outputs` paths. |
| Validation summaries | Current evidence points to completed validation summaries, kappa tables, and adjudication files. |

## Remaining Friction

| Issue | Impact | Status |
|---|---|---|
| `--agent-type` CLI choices expose only `scripted`, `openai`, and `claude`. | Users may need `--run-config` for `openai_compatible` and `openweight` lanes. | Documented in `docs/release/new_model_onboarding.md`. |
| Full provider-backed reproduction requires external API keys and quota. | Expected limitation for model reruns. | Documented provider requirement. |
| Local open-weight reproduction requires a compatible inference server and hardware. | Expected limitation for open-weight lanes. | Documented in onboarding guide. |

## Currently Working

- Fresh editable install with dev extras.
- `make reproduce`.
- `make reviewer-test`.
- Packet validation from `data/scored_outputs/per_episode`.
- Config-based model onboarding for supported adapter routes.
