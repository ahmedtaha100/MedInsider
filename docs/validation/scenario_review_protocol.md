# Scenario Realism Review Protocol

Status note: `docs/validation/scenario_realism_results.csv` is an optional
pending worksheet. All rows are currently `review_status=pending`; this file is
not completed validation evidence for the submitted artifact.

## Objective
Evaluate scenario realism and policy clarity on a stratified sample across family, condition, alignment, and difficulty.

## Input Artifact
- `docs/validation/scenario_realism_results.csv`

## Required Coverage
- 5 scenario families
- 8 conditions (neutral, direct_incentive, background_pressure, background_pressure_minimal, reverse_incentive, honesty_system_prompt, sham_placebo, replacement_ablation)
- aligned + conflict
- obvious + borderline

## Review Questions
- Realism score (1-5)
- Is aligned behavior defensible?
- Is tempting shortcut realistic?
- Is violation definition clear?
- Is any institution-specific ambiguity present?
- Should scenario be revised?
- Benchmark realism class: realistic microcosm / stylized stress test / too artificial

## Process
1. Assign reviewers in the CSV.
2. Complete review fields and comments.
3. Mark `review_status` as `complete`.
4. Route disagreements to adjudication protocol.
5. Record accepted edits in revision logs.

## Acceptance Gate
- Target completed reviews: 150-250 scenarios.
- At least one reviewer from clinical and compliance backgrounds must review each stratum.
