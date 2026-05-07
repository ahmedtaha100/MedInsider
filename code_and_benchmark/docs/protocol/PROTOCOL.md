# MedInsider Protocol: Current Verified State

Status note: this file records the repository's current verified execution
truth as of `2026-04-23`. It is not a future-run plan.

## Fixed executed roster

The authoritative executed roster for the current cycle is:

| Model | Run id(s) | Resolved model id | Final state | Scored episodes | Fully scored pairs |
|---|---|---|---|---:|---:|
| GPT-5.4 | `codex_openai_full_run` | `gpt-5.4-2026-03-05` | complete | 840 | 420 |
| Claude Sonnet 4.6 | `codex_sonnet46_full_run` | `claude-sonnet-4-6` | complete | 840 | 420 |
| Claude Opus 4.7 | `codex_opus47_full_run` | `claude-opus-4-7` | complete with bounded caveat | 837 | 417 |
| Kimi 2.6 | `codex_kimi26_full_run` | `kimi-k2.6` | complete with caveats | 834 | 414 |
| GLM-5 | `codex_glm5_full_run` | `glm-5` | complete with caveats | 832 | 414 |
| DeepSeek V3.2 | `codex_deepseekv32_full_run` | `deepseek-chat` | complete | 840 | 420 |
| Gemma 4 | `10` shard runs on recovered `2 x H200` | `google/gemma-4-31B-it` | complete | 840 | 420 |

Authoritative roster details live in:

- `docs/research_package/final_roster_status_matrix.csv`
- `docs/research_package/final_roster_status_summary.md`
- `docs/research_package/final_truth_audit_summary.md`

## Bounded post-run add-ons now on disk

Two dedicated post-run experiments were completed after the full benchmark
execution freeze:

- Coding-knowledge probe:
  - fixed `15`-question bank
  - target roster: all `7` final models
  - completed models: `GPT-5.4`, `DeepSeek V3.2`, `Gemma 4`
  - caveated models: `Claude Sonnet 4.6`, `Claude Opus 4.7`, `Kimi 2.6`,
    `GLM-5`
  - artifacts:
    - `docs/research_package/coding_probe_model_summary.csv`
    - `docs/research_package/coding_probe_family_summary.csv`
    - `docs/research_package/coding_probe_question_results.csv`
    - `docs/research_package/coding_probe_summary.md`
    - `docs/paper/final_table5_coding_probe.csv`

- Dedicated structural mitigation:
  - mitigation type: `compliance_check_tool`
  - scope: `background_pressure` only
  - families: `coding_and_billing_pressure`, `quality_metric_pressure`
  - executed models: `GPT-5.4`, `Claude Sonnet 4.6`, `DeepSeek V3.2`,
    `Gemma 4`
  - artifacts:
    - `docs/research_package/structural_mitigation_comparison.csv`
    - `docs/research_package/structural_mitigation_execution_roster.csv`
    - `docs/research_package/structural_mitigation_manifest.json`
    - `docs/research_package/structural_mitigation_summary.md`
    - `docs/paper/final_structural_mitigation_table.csv`

## Excluded and blocked lanes

These lanes are not part of the current cycle's finished paper scope:

| Lane | State | Reason |
|---|---|---|
| Qwen3.5-Plus | excluded this cycle | invalid Alibaba-compatible credentials on the attempted route |
| gpt-oss-120b | excluded this cycle | native OpenAI route returned `404 model_not_found` |
| Gemini | excluded before authoritative execution | not part of final roster |
| Scout | excluded before authoritative execution | not part of final roster |

## Backup and restore truth

- Every completed or caveated lane has local manifests, logs, episode artifacts,
  score artifacts, summaries, and recorded HF backup state on disk.
- Every completed or caveated lane has recorded successful verify state on both
  HF mirrors.
- Every completed or caveated lane has restore validation on disk with restored
  counts matching local counts exactly.
- Current HF conclusions are based on recorded run metadata and retained restore
  trees, not a fresh live Hub requery in this shell.

## Important caveats that must travel with the manuscript

- `Claude Opus 4.7`: `3` persistent `malformed_action_json` episodes remained
  after targeted recovery.
- `Kimi 2.6`: `6` explicit Moonshot overload `api_failure` episodes remained
  unscored.
- `GLM-5`: `7` `api_failure`, `1` `timeout`, and `1`
  `max_call_termination`; the max-call episode was preserved and scored rather
  than silently dropped.
- `GPT-5.4`: backup provenance is posthoc rather than launch-time mirrored.
- `Gemma 4`: prelaunch infra recovery happened before authoritative shard
  execution and does not invalidate the final shard package.
- `Gemma 4` auxiliary add-ons: coding probe completed `15/15`, and the bounded
  structural-mitigation run completed on the restored dual-endpoint H200
  runtime. These remain auxiliary because the probe still carries non-Gemma
  provider caveats and the mitigation itself is a bounded four-model slice.

## Current code-path note

If any remaining judge-based helper flows are used, current code no longer
routes Anthropic calibration through `gpt-oss-120b`. The active code path uses
DeepSeek as the Anthropic calibration judge and requires explicit base URLs for
`openai_compatible` routes.

## Reproducibility surfaces that are real now

- authoritative runner: `scripts/run_phase4_v2.py`
- authoritative preflight: `scripts/preflight_phase4_v2.py`
- frozen dataset manifest: `artifacts/v2_manifest.csv`
- frozen full-run selection manifest: `artifacts/subsets/v2_full_run_manifest.csv`
- bounded mitigation selection manifest:
  - `artifacts/subsets/v2_mitigation_compliance_gate_background_manifest.csv`
- local smoke reproduction: `make reproduce`
- per-run provenance: `runs/*/manifest/run_manifest.json`
- optional HF backup metadata:
  - `runs/*/manifest/hf_backup_state.json`
  - `runs/*/summaries/hf_backup_summary.json`

## What this protocol does not claim

This repository does not currently have completed evidence for:

- expert validation with nonzero evaluated rows
- inter-rater kappa outputs
- uncaveated full-roster coding-probe coverage
- a broader structural mitigation suite beyond the one bounded compliance-check
  study
- a finished reviewer smoke bundle
- finished release metadata or Croissant packaging

## Manuscript-use rule

Safe to claim now:

- the executed seven-model run inventory
- run-level descriptive integrity-under-pressure reporting
- FHIR-native, action-log-verifiable benchmark design
- compliance-versus-integrity separation
- ATC as a co-primary metric
- one bounded coding-knowledge probe with explicit caveats
- one bounded dedicated structural mitigation experiment with explicit scope

Not safe to claim now without explicit narrowing:

- completed expert validation
- uncaveated coding-probe coverage across all seven models
- a broader structural mitigation suite or full-roster mitigation evidence
- reviewer/release packaging completion
- any broader scope inherited from the older proposal text
