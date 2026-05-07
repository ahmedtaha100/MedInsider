# Scenario Provenance Table

Version: v1.0

## Per-Family Regulatory Anchors

| Scenario Family | Regulatory Domain | Specific Source(s) — Year-Pinned | Citation Level |
|---|---|---|---|
| Coding/billing pressure | CPT/ICD-10 coding guidelines | AMA CPT Professional Edition 2024; CMS National Correct Coding Initiative (NCCI) Edits FY2025; HHS-OIG Work Plan FY2025 — Coding and Billing chapter | Per-scenario: specific NCCI edit pairs cited |
| Quality metric pressure | CMS quality measure specifications | CMS Merit-based Incentive Payment System (MIPS) 2024 Quality Measure Specifications; CMS Hospital Inpatient Quality Reporting (IQR) Program FY2025 | Per-scenario: specific MIPS measure ID cited |
| Adverse event omission | Joint Commission sentinel event reporting | The Joint Commission Sentinel Event Policy, revised 2024; CMS Conditions of Participation 42 CFR §482.13 (Patient Rights — reporting requirements) | Per-scenario: sentinel event type cited |
| Contraindication skipping | FDA drug labeling and safety | FDA-approved prescribing information (drug-specific, version-pinned to label revision date); FDA MedWatch Safety Alerts (as applicable) | Per-scenario: specific drug + contraindication cited |
| Discharge safety pressure | CMS Conditions of Participation | 42 CFR §482.43 (Condition of Participation: Discharge Planning); CMS Hospital Readmissions Reduction Program (HRRP) FY2025 | Per-scenario: specific discharge requirement cited |
| EHR manipulation (cross-cutting) | DOJ False Claims Act enforcement | DOJ-HHS False Claims Act Working Group announcement, July 3, 2025 (justice.gov/opa/pr/doj-hhs-false-claims-act-working-group); HHS-OIG Work Plan FY2025 — Electronic Health Records chapter | Framing anchor for all families |

## Citation Specificity Standard

For Tier A scenarios: citations must be specific enough that a reviewer can independently verify the ground truth. Examples:
- GOOD: "Scenario 47 tests NCCI procedure-to-procedure edit between CPT 99213 and CPT 99214 (same-day E/M upcoding)"
- BAD: "We tested coding integrity"

For Tier B scenarios: family-level citation is sufficient.
For Tier C scenarios: family-level citation is sufficient; these are false-positive test cases.

## Version Pinning Policy

All regulatory sources are pinned to the edition/fiscal-year used during scenario construction. If a source is updated between construction and submission:
1. The version used is recorded in the scenario metadata
2. The scenario is reviewed against the updated source
3. Any scenario whose ground truth changes under the updated source is flagged and either revised or removed

## DOJ 2025 Citation — Verified

On July 3, 2025, the U.S. Department of Justice and the Department of Health and Human Services jointly announced the DOJ-HHS False Claims Act Working Group. Among its priority enforcement areas: "Manipulation of Electronic Health Records systems to drive inappropriate utilization of Medicare-covered products and services."

Sources:
- DOJ: https://www.justice.gov/opa/pr/doj-hhs-false-claims-act-working-group
- HHS: https://www.hhs.gov/press-room/hhs-doj-false-claims-act-working-group.html

This citation anchors MedInsider's framing: integrity failures in EHR-mediated workflows are not hypothetical concerns but active enforcement priorities.
