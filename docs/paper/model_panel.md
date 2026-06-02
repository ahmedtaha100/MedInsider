# Current Seven-Model Panel

Status note: this file reflects the active seven-model manuscript scope as of
`2026-05-05`, after targeted reruns and post-rerun scored-output locking.

## Active execution panel

| Model label | Provider / route | Resolved model ID | Authoritative run id(s) | Current evidence status |
|---|---|---|---|---|
| GPT-5.4 | OpenAI API | `gpt-5.4-2026-03-05` | `codex_openai_full_run` | complete |
| Claude Sonnet 4.6 | Anthropic API | `claude-sonnet-4-6` | `codex_sonnet46_full_run` | complete |
| Claude Opus 4.7 | Anthropic API | `claude-opus-4-7` | `codex_opus47_full_run` | complete after targeted rerun |
| Kimi 2.6 | Moonshot API | `kimi-k2.6` | `codex_kimi26_full_run` | complete after targeted rerun |
| GLM-5 | Zhipu API | `glm-5` | `codex_glm5_full_run` | complete after targeted rerun |
| DeepSeek V3.2 | DeepSeek API | `deepseek-chat` | `codex_deepseekv32_full_run` | complete |
| Gemma 4 | self-hosted openai-compatible | `google/gemma-4-31B-it` | `10` shard runs on recovered `2 x H200` | complete |

## Coverage

| Model | Scored episodes | Fully scored pairs | Notes |
|---|---:|---:|---|
| GPT-5.4 | `840` | `420` | complete run; HF backup provenance is posthoc |
| Claude Sonnet 4.6 | `840` | `420` | complete run |
| Claude Opus 4.7 | `840` | `420` | complete after targeted rerun; scored output locked on `2026-05-05` |
| Kimi 2.6 | `840` | `420` | complete after targeted rerun; scored output locked on `2026-05-05` |
| GLM-5 | `840` | `420` | complete after targeted rerun; prior max-call episode succeeded under unchanged cap |
| DeepSeek V3.2 | `840` | `420` | complete run; one transient HF verify flake cleared on retry |
| Gemma 4 | `840` | `420` | aggregate over `10` verified shard runs |

## Auxiliary add-on caveat

The coding probe and bounded structural mitigation are now integrated into the
current seven-model package, but they remain auxiliary rather than core:

- `Gemma 4` is complete for the main benchmark and was later backfilled for
  both auxiliary add-ons on the restored dual-endpoint H200 runtime.
- `Claude Sonnet 4.6`, `Claude Opus 4.7`, `Kimi 2.6`, and `GLM-5` have
  provider-error caveats in the coding probe.
- the structural mitigation remains a bounded four-model billing/quality
  `background_pressure` study, not a panel-wide mitigation suite.

## Manuscript-use rule

Safe wording:

> The current paper uses a fixed seven-model execution roster. All seven main
> benchmark lanes have `840` scored episodes and `420` fully scored pairs after
> targeted reruns. Auxiliary coding-probe and mitigation add-ons remain bounded
> evidence surfaces with their own caveats.
