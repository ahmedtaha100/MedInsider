# Distribution Realism Audit

Dataset: `.`
Scenario count: `840`

## Distribution Summary

### Family counts
- coding_and_billing_pressure: 168
- quality_metric_pressure: 168
- readmission_pressure: 168
- safety_event_pressure: 168
- throughput_pressure: 168

### Condition counts
- background_pressure: 60
- background_pressure_minimal: 60
- direct_incentive: 60
- honesty_system_prompt: 60
- neutral: 420
- replacement_ablation: 60
- reverse_incentive: 60
- sham_placebo: 60

### Alignment counts
- aligned: 120
- conflict: 720

### Demographics and events
- Mean age: 64.02
- Sex distribution: {'F': 420, 'M': 420}
- Adverse-event scenario rate: 0.200

### Troponin distribution by family
- coding_and_billing_pressure: {'normal': 112, 'pending': 56}
- quality_metric_pressure: {'normal': 168}
- readmission_pressure: {'normal': 112, 'pending': 56}
- safety_event_pressure: {'normal': 168}
- throughput_pressure: {'normal': 168}

## Interpretation
- Current distributions are balanced across family, condition, and alignment by construction.
- This benchmark should be framed as a stylized stress test for integrity failures unless expert realism review upgrades the claim.
- Final realism class label from experts remains pending and should be recorded in `scenario_realism_results.csv`.
