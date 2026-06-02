# Closed-Source API Budget (Frozen Planning Estimate)

Last updated: April 10, 2026

This document supersedes the earlier `compute_budget_draft.md` for the
closed-source API portion. GPU costs for open-weight models are tracked
separately and depend on the open-weight stability audit.

---

## Critical pricing rule

**Agent episodes use REAL-TIME (standard) API pricing, NOT batch.**
Multi-turn 13-call agent loops require synchronous request-response.
**Judges, probes, and controls use BATCH pricing (50% off)** because they
are independent one-shot calls.

---

## Token assumptions per call type

| Call type | Input tokens | Output tokens |
|-----------|--------------|---------------|
| Agent episode (full multi-turn loop) | ~10,000 | ~1,200 |
| Judge call (one-shot scoring) | ~8,000 | ~300 |
| Knowledge probe / capability control call | ~500 | ~100 |

These are estimates. Exact token counts will be measured during the
statistical pilot and the final compute appendix will report measured values.

---

## Prompt caching assumption (EXPLICIT)

The budget below assumes **NO prompt caching on agent episodes** in the
baseline estimate. Rationale: each MedInsider episode has a unique patient
state + unique scenario + unique incentive framing in the system prompt,
so the shared prefix across episodes within a condition is only the
~300-token operational context preamble.

If prompt caching is enabled for that preamble on all four closed-source
models, the potential savings are non-trivial but still modest relative
to the total agent-episode budget:

Calculation basis: 300 cached tokens × 10,080 episodes × 13 calls
= 39.3M cached input tokens per model.

- **GPT-5.4**: 39.3M × $2.50/M × 0.90 (90% discount on cached input)
  ≈ **~$88 saved**
- **Claude Opus 4.7**: 39.3M × $5.00/M × 0.90 ≈ **~$177 saved**
- **Claude Sonnet 4.6**: 39.3M × $3.00/M × 0.90 ≈ **~$106 saved**
- **Gemini 2.5 Pro**: 39.3M × $1.25/M × 0.90 ≈ **~$44 gross; net ~$20-40
  after context-cache storage fees**

Total potential savings with caching enabled: **~$390-$410** (~8% of the
~$5,000 planning number). Not insignificant, but not load-bearing for
the budget decision.

The available discounts per provider:

- **OpenAI GPT-5.4**: cached input at $0.25/M (90% off standard $2.50)
- **Anthropic Opus 4.7 / Sonnet 4.6**: cache reads at 10% of base input price
- **Google Gemini 2.5 Pro**: context caching available with storage fees

Per PROTOCOL.md: "Agent episodes assume no prompt caching in the baseline
budget. If caching is enabled during pipeline optimization, the actual
caching configuration and resulting cost savings are reported in the
final compute appendix."

---

## Rate-limit / quota / access-tier feasibility (MUST CHECK)

Budget is not the only feasibility constraint. Before experiment freeze,
verify that the ACTUAL API account tier supports the throughput needed
to complete the closed-model runs before May 6:

- **OpenAI GPT-5.4**: check tier RPM (requests per minute) and TPM (tokens
  per minute) limits on the account settings page. At 10,080 episodes ×
  13 calls each = ~131,000 API calls. At (for example) 500 RPM, that is
  ~262 minutes = ~4.4 hours. Batch queue limits apply for judge calls.
- **Anthropic Opus 4.7 / Sonnet 4.6**: check usage tier rate limits. Combined
  Opus + Sonnet runs = ~20,160 episodes × 13 = ~262,000 calls. Batch API
  has its own throughput constraints.
- **Google Gemini 2.5 Pro**: check Vertex AI or AI Studio quotas. Batch
  API targets 24-hour turnaround for non-urgent work.

**Action items:**

1. Log into each provider console and record current tier + limits
2. Compute wall-clock time to complete the run at those limits
3. If any provider is a bottleneck, request a tier upgrade NOW (some
   take days to process)
4. Document tier, limits, and expected wall-clock in `version_manifest.json`

The verification checklist with per-provider load estimates and
tier-upgrade lead times is tracked in
[`docs/protocol/rate_limit_feasibility.md`](../protocol/rate_limit_feasibility.md).
Tier-upgrade requests have a 1-week lead time and must be submitted
before experiment freeze.

---

## Cost estimate (rounded planning figures)

All per-model costs below are ROUNDED PLANNING FIGURES based on
~10,000 input + ~1,200 output tokens per episode at standard pricing.
Exact costs will vary with actual token counts measured during the pilot.

| Component | Volume | Pricing basis | Est. cost (rounded) |
|-----------|--------|---------------|---------------------|
| Agent: GPT-5.4 (standard) | ~10,080 | $2.50/$15.00 | ~$435 |
| Agent: Opus 4.7 (standard) | ~10,080 | $5.00/$25.00 | ~$810 |
| Agent: Sonnet 4.6 (standard) | ~10,080 | $3.00/$15.00 | ~$485 |
| Agent: Gemini 2.5 Pro (standard) | ~10,080 | $1.25/$10.00 | ~$250 |
| **Agent subtotal** | **40,320** | | **~$1,980** |
| Judges: Opus 4.7 primary (batch) | ~24,200 | $2.50/$12.50 | ~$575 |
| Judges: GPT-5.4 calibration (batch) | ~12,100 | $1.25/$7.50 | ~$150 |
| **Judge subtotal** | **~36,300** | | **~$725** |
| Probes + controls (batch avg) | ~20,000 | batch rates | ~$40 |
| **Subtotal** | | | **~$2,745** |
| 3x pilot uncertainty multiplier on judges | | | +~$1,450 |
| 20% buffer | | | ~$550 |
| **TOTAL CLOSED-SOURCE API** | | | **~$4,750** |

Calculation worked example (judge primary line):
24,200 calls × (8,000 input tokens × $2.50/M + 300 output tokens × $12.50/M)
= 24,200 × ($0.020 + $0.00375) = 24,200 × $0.02375 ≈ **$575**.

**Planning number for budget appendix: ~$5,000**
**Budget ceiling (safe upper bound): ~$6,500**

The judge cost above uses the planning assumption of ~20% ambiguity /
~10% calibration. If the pilot measures a higher rate (up to ~50% combined),
the judge subtotal could reach ~$2,000-$2,500; the 3x uncertainty multiplier
above covers that scenario.

The judge cost range depends on the ambiguity rate the statistical pilot
measures. The 20% ambiguity / 10% calibration rates are planning
estimates, NOT frozen assumptions. Document the actual pilot-measured
rates when available.

---

## Stratified pilot-reporting requirement for judge volumes

The pilot MUST report ambiguity rates STRATIFIED by:

- **Scenario family** (coding_and_billing_pressure, quality_metric_pressure,
  readmission_pressure, safety_event_pressure, throughput_pressure)
- **Condition** (all 8, but especially Background Pressure vs Neutral)
- **Tier** (A, B, C)

This matters because:

1. If ambiguity concentrates in one family, the judge cost estimate
   changes and the methods section must explain why
2. If ambiguity is higher under pressure than under neutral, that is
   itself a finding worth reporting
3. Tier B episodes are expected to have higher ambiguity than Tier A
   by construction — the pilot should confirm this

**The pilot report template should include:**

- Overall ambiguity rate (pooled)
- Ambiguity rate per family (5 rows)
- Ambiguity rate per condition (8 rows)
- Ambiguity rate per tier (3 rows)
- Cross-tabulation: family × condition (5 × 8 = 40 cells)
- Resulting judge call volume estimate (updated from pilot data)

---

## GPU costs for open-weight models

NOT estimated here. This depends on the open-weight audit results
(hardware footprint, inference throughput, rental pricing). It will
be computed in a separate exercise after the audit returns.

See `docs/protocol/PROTOCOL.md` "Pre-freeze action items".
