# Scenario Authority Specification

## Purpose
Scenario authority records define per-episode source-of-truth constraints for:
- automated scoring interpretation
- expert adjudication
- paper case evidence

## Record format
Authority records are stored as JSONL:
- file: `scenarios/phase2/authority/phase2_authority_records.jsonl`
- one JSON object per episode

Each record contains:
- `authority_spec_version`
- `benchmark_version`
- `episode_id`
- `source_scenario_path`
- `scenario_family`
- `condition`
- `alignment_label`
- `supported_diagnoses`
- `unsupported_diagnoses`
- `evidence_required_for_billing`
- `required_adverse_event_documentation`
- `contraindications_must_check`
- `minimum_acceptable_discharge_criteria`
- `acceptable_note_claims`
- `unacceptable_note_claims`
- `ambiguity_status`
- `ambiguity_reasons`
- `automatic_scoring_claim_eligible`
- `automatic_metric_eligibility`
- `routing_policy`

## Ambiguity policy
`ambiguity_status` values:
- `automatically_scorable`
- `non_automatically_scorable`

Rules:
- records marked `non_automatically_scorable` are excluded from fully automatic scoring claims
- those records are routed to judge-assisted or appendix-only reporting

## Authority file usage
Authority records are the source of truth for:
- accepted vs unsupported diagnosis claims
- billing evidence expectations
- adverse event documentation requirements
- contraindication checks
- discharge documentation minimums

## Versioning
Any change to authority schema or derivation logic requires:
- authority spec version bump
- benchmark version bump when claim-impacting
- regenerated authority records and freeze/version manifests

## Summary file
Authority summary is stored at:
- `scenarios/phase2/authority/phase2_authority_summary.json`
