# External User Friction Inventory 20260601

## Resolved In This Remediation Pass

| Issue | Resolution |
|---|---|
| `make reproduce` previously failed before smoke execution. | `make reproduce` now runs only the reviewer smoke path and passes in the remediation clone. |
| Final paper-packet builder previously required untracked run roots. | Builder now validates from bundled per-episode scored outputs. |
| Reviewer-facing docs referenced missing research-package files. | Docs now point to shipped `docs/paper`, `docs/validation`, `data/manifests`, and `data/scored_outputs` paths. |
| Validation docs exposed stale zero-row/admin-crosswalk artifacts. | Legacy Phase B artifacts are marked superseded; current evidence points to completed validation summaries and kappa tables. |

## Remaining Friction

| Issue | Impact | Status |
|---|---|---|
| `--agent-type` CLI choices expose only `scripted`, `openai`, and `claude`. | Users may need `--run-config` for `openai_compatible` and `openweight` lanes. | Documented in `docs/release/new_model_onboarding.md`. |
| Full provider-backed reproduction requires external API keys and quota. | Expected limitation for model reruns. | Documented provider requirement. |
| Local open-weight reproduction requires a compatible inference server and hardware. | Expected limitation for open-weight lanes. | Documented in onboarding guide. |
| HF dataset release still needs separate metadata/path/PDF/viewer remediation. | Dataset-host surface can still confuse reviewers until updated. | Tracked as HF remediation work. |

## Currently Working

- Fresh editable install with dev extras.
- `make reproduce`.
- `make reviewer-test`.
- Packet validation from `data/scored_outputs/per_episode`.
- Config-based model onboarding for supported adapter routes.
