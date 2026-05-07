# run_phaseB_metric_validation.py FLOWCHART

```text
START
  |
  v
Parse CLI args
  |
  v
Load blinded label CSV + admin prediction CSV
  |
  v
Run metric validation vs predicted scorer outputs
  |
  v
Write docs/validation/metric_validation_results.md + .json
  |
  v
Run inter-rater agreement computation
  |
  v
Write docs/validation/inter_rater_agreement.md
  |
  v
Run scorer error audit (top-k mismatches)
  |
  v
Write docs/validation/scorer_error_audit.md
  |
  v
Print JSON summary
  |
  v
END
```
