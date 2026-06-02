# MedInsider Protocol: Submitted Artifact State

Status note: this file records the reviewer-facing submitted artifact state as
of 2026-06-01. It describes the code-and-benchmark bundle at commit
`cc49e23226d3ba98bdeb3ff81f6bffed6825c412` and the frozen final paper tables.
It is not a record of older restore trees or pre-final rerun status.

## Fixed Executed Roster

The final benchmark roster is seven models. Each final lane has 840 scored
episodes and 420 fully scored neutral-pressure pairs in the shipped summary
tables and per-episode scored outputs.

| Model | Resolved model id | Final state | Scored episodes | Fully scored pairs |
|---|---|---|---:|---:|
| GPT-5.4 | `gpt-5.4-2026-03-05` | complete | 840 | 420 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | complete | 840 | 420 |
| Claude Opus 4.7 | `claude-opus-4-7` | complete | 840 | 420 |
| Kimi 2.6 | `kimi-k2.6` | complete | 840 | 420 |
| GLM-5 | `glm-5` | complete | 840 | 420 |
| DeepSeek V3.2 | `deepseek-chat` | complete | 840 | 420 |
| Gemma 4 | `google/gemma-4-31B-it` | complete | 840 | 420 |

Primary evidence:

- `docs/paper/final_table3_seven_model_results.csv`
- `docs/paper/final_table3_model_caveats.csv`
- `docs/paper/model_panel.md`
- `data/scored_outputs/per_episode/*_scored_episodes.csv`

## Benchmark Corpus

The fixed v2 corpus contains 840 generated scenario JSON files and 420
neutral-pressure pairs. The scenario count is for:

- `data/scenarios/phase2_v2/generated/*.json`
- `code/scenarios/phase2_v2/generated/*.json`

A broad recursive count under `data/scenarios/` can include non-scenario
artifact JSON files, such as the generation summary. Use the generated
directory when checking the corpus count.

Corpus manifests:

- `data/manifests/v2_manifest.csv`
- `data/manifests/subsets/v2_full_run_manifest.csv`
- `data/scenarios/phase2_v2/artifacts/v2_generation_summary.json`

## Reproducibility Surfaces

The reviewer smoke reproduction is the supported cold-clone entry point:

- `make reproduce`

The smoke path runs preflight, selects a tiny fixed subset, and exercises the
runner without token-backed model calls.

The full per-episode locked scored outputs are shipped under:

- `data/scored_outputs/per_episode/`

The final paper CSVs are shipped under:

- `docs/paper/`

The reviewer package also includes:

- `DATASHEET.md`
- `croissant.json`
- `LICENSE`
- `DATA_LICENSE`

## Validation Evidence

The submitted validation summaries are:

- `docs/validation/validation_results.md`
- `docs/validation/kappa_tables.csv`
- `docs/validation/validation_summary_120.csv`
- `docs/validation/inter_rater_agreement.md`
- `docs/validation/adjudication_protocol.md`
- `docs/validation/q2_dissent_adjudications.csv`

These files document 120 validation episodes, four reviewers, 480 submissions,
and the reported agreement summaries.

## Auxiliary Analyses

The coding probe is a bounded 15-question auxiliary analysis, not a standalone
clinical capability benchmark. Its shipped paper table is:

- `docs/paper/final_table6_coding_probe.csv`

The structural mitigation analysis is a bounded four-model slice with one
intervention family. Its shipped paper table is:

- `docs/paper/final_table7_mitigation.csv`

## Excluded Lanes

These lanes are not part of the submitted seven-model roster:

| Lane | State | Reason |
|---|---|---|
| Qwen3.5-Plus | excluded this cycle | invalid Alibaba-compatible credentials on the attempted route |
| gpt-oss-120b | excluded this cycle | native OpenAI route returned `404 model_not_found` |
| Gemini | excluded before authoritative execution | not part of final roster |
| Scout | excluded before authoritative execution | not part of final roster |

## What This Protocol Does Not Claim

This submitted bundle does not claim:

- provider API reruns are possible without external credentials
- Hugging Face dataset-host artifacts include scored outputs or validation
  response rows
- the bounded mitigation slice generalizes beyond the tested scenarios, models,
  and intervention
- the coding probe measures broad model capability outside its fixed 15-question
  bank
- old local provider-run restore roots are part of the submitted reviewer
  package

## Manuscript-Use Rule

Use the final shipped CSVs, validation summaries, scenario manifests, and
per-episode scored outputs listed above as the artifact evidence. Do not use
obsolete restore-root paths, old pre-final model counts, or missing internal
research-package paths as final-paper support.
