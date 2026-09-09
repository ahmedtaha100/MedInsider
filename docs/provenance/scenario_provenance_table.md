# Scenario provenance: frozen v2 and historical plan

Status reviewed: 2026-09-07. The v1.0 planning material below is retained for provenance.

## Evidence in the frozen v2 corpus

The released corpus contains 840 scenarios across coding and billing, quality metrics, readmission, safety events, and throughput (168 episodes per family). Scenarios contain chart state, reference actions, constraints, condition framing, and paired-generation metadata. They do not contain per-scenario regulatory citations, NCCI edit-pair references, MIPS measure identifiers, drug-label revision dates, or regulatory-source edition fields. The generated metadata records the assembly engine, pair, condition, twin role, and risk tier; it does not establish a version-pinned regulatory review.

The family-level regulatory framing is described in the [paper provenance table](../paper/provenance_table.md). [The datasheet](../../DATASHEET.md) records the author-confirmed no-LLM drafting and pre-execution clinician template review. These facts do not establish the citation and update-review procedures proposed below. The frozen corpus has no contraindication-skipping family and does not trigger the scorer's recognized contraindication states; see [metric definitions](../paper/definitions.md).

## Historical v1.0 regulatory-source targets

The following table preserves the original design targets. Its source editions, chapter names, example mappings, and proposed per-scenario citation coverage are unverified planning entries, not evidence supplied by the frozen release.

| Planned Scenario Family | Regulatory Domain | Planned Source(s) — Unverified Editions | Planned Citation Level |
|---|---|---|---|
| Coding/billing pressure | CPT/ICD-10 coding guidelines | AMA CPT Professional Edition 2024; CMS National Correct Coding Initiative (NCCI) Edits FY2025; HHS-OIG Work Plan FY2025 — Coding and Billing chapter | Per-scenario: specific NCCI edit pairs cited |
| Quality metric pressure | CMS quality measure specifications | CMS Merit-based Incentive Payment System (MIPS) 2024 Quality Measure Specifications; CMS Hospital Inpatient Quality Reporting (IQR) Program FY2025 | Per-scenario: specific MIPS measure ID cited |
| Adverse event omission | Joint Commission sentinel event reporting | The Joint Commission Sentinel Event Policy, revised 2024; CMS Conditions of Participation 42 CFR §482.13 (Patient Rights — reporting requirements) | Per-scenario: sentinel event type cited |
| Contraindication skipping | FDA drug labeling and safety | FDA-approved prescribing information (drug-specific, version-pinned to label revision date); FDA MedWatch Safety Alerts (as applicable) | Per-scenario: specific drug + contraindication cited |
| Discharge safety pressure | CMS Conditions of Participation | 42 CFR §482.43 (Condition of Participation: Discharge Planning); CMS Hospital Readmissions Reduction Program (HRRP) FY2025 | Per-scenario: specific discharge requirement cited |
| EHR manipulation (cross-cutting) | DOJ False Claims Act enforcement | DOJ-HHS False Claims Act Working Group announcement, 2025-07-02 (justice.gov/opa/pr/doj-hhs-false-claims-act-working-group; page updated 2025-07-03); HHS-OIG Work Plan FY2025 — Electronic Health Records chapter | Framing anchor for all families |

## Historical citation-specificity proposal

The Tier A/B/C scheme and example below are proposed design conventions. The released scenarios do not implement these citation tiers, and the example is not a verified NCCI rule or a released scenario mapping.

For Tier A scenarios: citations must be specific enough that a reviewer can independently verify the ground truth. Examples:

- GOOD: "Scenario 47 tests NCCI procedure-to-procedure edit between CPT 99213 and CPT 99214 (same-day E/M upcoding)"
- BAD: "We tested coding integrity"

For Tier B scenarios: family-level citation is sufficient.
For Tier C scenarios: family-level citation is sufficient; these are false-positive test cases.

## Historical version-pinning proposal

The original plan called for sources to be pinned to the edition/fiscal-year used during construction, with the following response to later source updates. The frozen metadata does not document implementation of this process:

1. The version used is recorded in the scenario metadata
2. The scenario is reviewed against the updated source
3. Any scenario whose ground truth changes under the updated source is flagged and either revised or removed

## DOJ 2025 Citation — Verified

On 2025-07-02, the U.S. Department of Justice and the Department of Health and Human Services announced the DOJ-HHS False Claims Act Working Group. The DOJ page was updated on 2025-07-03. Its enforcement priorities include EHR manipulation that drives inappropriate use of Medicare-covered products and services.

Sources:

- DOJ: https://www.justice.gov/opa/pr/doj-hhs-false-claims-act-working-group
- HHS: https://www.hhs.gov/press-room/hhs-doj-false-claims-act-working-group.html

This announcement supports MedInsider's motivation for examining documentation integrity. It does not validate individual synthetic cases or establish that a benchmark discrepancy is a legal violation.
