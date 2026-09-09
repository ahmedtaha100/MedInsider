# Descriptive uncertainty from frozen results

The three default tables reproduce the existing 2026-07-27 analysis of the
released scores. An optional fourth table adds paired mitigation intervals
computed on 2026-09-06 from recovered original outputs. Neither path changes
the original estimates or reruns model inference.

From the repository root:

```bash
python -m pip install -e ".[analysis]"
python code/scripts/reproduce_uncertainty.py
```

The script first verifies the original 29 artifact locks, then writes these
three tables to `reports/uncertainty/`:

- `main_pair_cluster_bootstrap_ci.csv`: 49 model/metric means and 95% intervals.
- `background_pressure_paired_bootstrap_delta_ci.csv`: 49 means and paired
  pressure-minus-neutral deltas for the background-pressure condition.
- `agreement_sensitivity_gwet_ac1.csv`: three aggregate agreement sensitivity
  estimates for the expert-review questions.

For the main table, each of the 420 matched pairs contributes the mean of its
two episode scores. The percentile bootstrap samples 420 complete pairs with
replacement for each of 20,000 draws. The background analysis samples its 60
matched pairs and averages the within-pair differences. Both use the 2.5th and
97.5th percentiles with NumPy's default linear interpolation, sorted pair IDs,
and `default_rng`. Seeds are `20260727 + model_index` for main intervals and
`20260727 + 100 + model_index` for background deltas. Model order is GPT-5.4,
Sonnet, Opus, Kimi, GLM, DeepSeek, Gemma. Sampling is computed in batches of 500.

Gwet AC1 uses observed pairwise agreement from the frozen
[`kappa_tables.csv`](../../validation/kappa_tables.csv) and the category
marginals documented in [`validation_results.md`](../../validation/validation_results.md).
For category proportions p and q categories, chance agreement is
`sum(p * (1 - p)) / (q - 1)` and AC1 is `(observed - chance) / (1 - chance)`.
Q1 and Q2 retain Yes/No/Unclear. Q3 uses the 119-item Fleiss subset, excluding
the item with one Scorer-hidden response and three Yes responses: 468 Yes and
8 No ratings. The original responses have since been privately verified, and
the released joint-rating pattern counts reproduce these aggregate inputs.
These remain descriptive sensitivity estimates; item-level intervals are
outside this release.

The intervals describe variation over the fixed empirical pair distribution.
They are unadjusted for multiple comparisons and do not estimate decoding,
provider, rerun, or clinical-population uncertainty. Resampling synthetic pairs
does not make the benchmark a random sample of clinical practice. A zero-width
PSD interval reflects its untriggered rules in this corpus. AC1 complements
the reported Fleiss kappa values and does not remove scorer anchoring or
establish independent expert validation.

The three default tables' numerical cells match the archived 2026-07-27 outputs exactly.
Interval notes describe this release's scope and the recovered aggregate
evidence. Original result CSVs and hash locks are unchanged.

## Mitigation comparison

With the anonymous supplement's `mitigation_logs/` directory available, run:

```bash
python code/scripts/reproduce_uncertainty.py --mitigation-supplement mitigation_logs
```

The existing table builder verifies the supplement manifest, compact score
hashes, 24 matched IDs per model and equality with the frozen mitigation
summary. The helper then also writes `mitigation_paired_bootstrap.csv`: 20
rows for four models and the five metrics in that summary. Resampling draws
24 matched baseline/treatment episode IDs with replacement, using the same
20,000-replicate percentile procedure, sorted episode IDs and seeds
`20260727 + 3000 + model_index` in the seven-model order above.

The contrast is treatment minus baseline. The `published_*` fields retain the
original numerical estimates; `paired_delta_mean` averages episode differences
before rounding the aggregate means. Episode scores retain their recorded
precision. These can differ because the published deltas subtract
separately rounded means (for example, GPT ATC is -0.0695 in the original table,
while its paired mean is -0.069446 to six decimals).

GPT IVR and Gemma MGR intervals reach zero. Only 24 episodes from two families
are available per model. These unadjusted intervals describe empirical case
variation, not decoding, provider or population uncertainty. A zero-width
interval means the observed differences are constant; it does not establish a
guaranteed null effect or remove the small-sample limitation.
