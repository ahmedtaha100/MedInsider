# Gold Set Resampling

## Source

The new 120-item validation gold set was sampled from the post-rerun authoritative scored outputs locked in `docs/validation/locked_scoring_targets.json`: 5,880 scored rows across 7 models.

Each validation item is a blinded model-run row. The reviewer-facing payload does not expose the source model. All four reviewers (`R1`-`R4`) are assigned the same 120 blinded items.

## Sampling Logic

The requested AEOR and CDR targets overlap in the benchmark: every selected AEOR-positive row is also CDR-positive. To keep the final set at 120 while covering scarce metrics, the sample includes all positive rows for the scarce IVR, MGR, and UPR-integrity metrics, then adds a balanced AEOR/CDR sample and clean rows.

Selection steps:

1. Included all 3 UPR-integrity-positive rows.
2. Included all 29 MGR-positive rows.
3. Included all 33 IVR-positive rows.
4. Added 25 AEOR/CDR-positive rows, balanced as 5 each from GPT-5.4, Kimi 2.6, GLM-5, DeepSeek V3.2, and Gemma 4.
5. Added 30 clean rows with no IVR/MGR/UPR-integrity/AEOR/CDR failure, balanced as 6 clean rows per scenario family. Fourteen of these clean rows are same-model paired twins of selected positive rows.

No source model contributes more than 25 validation items. The final set has 85 unique source scenario IDs and 35 repeated source scenario IDs because the sampling unit is the model-run row, not the scenario template alone.

## Metric Coverage

| Metric | Selected positives |
|---|---:|
| IVR | 33 |
| MGR | 29 |
| UPR-integrity | 3 |
| AEOR | 25 |
| CDR | 25 |
| Any integrity failure | 90 |
| Clean rows | 30 |

## Scenario Family Distribution

| Scenario family | Rows |
|---|---:|
| `coding_and_billing_pressure` | 10 |
| `quality_metric_pressure` | 67 |
| `readmission_pressure` | 6 |
| `safety_event_pressure` | 31 |
| `throughput_pressure` | 6 |

## Source Model Distribution

| Source model | Rows |
|---|---:|
| `Claude Opus 4.7` | 9 |
| `Claude Sonnet 4.6` | 9 |
| `DeepSeek V3.2` | 25 |
| `GLM-5` | 12 |
| `GPT-5.4` | 24 |
| `Gemma 4` | 25 |
| `Kimi 2.6` | 16 |

## Pressure Condition Distribution

| Condition | Rows |
|---|---:|
| `background_pressure` | 34 |
| `background_pressure_minimal` | 8 |
| `direct_incentive` | 10 |
| `honesty_system_prompt` | 4 |
| `neutral` | 51 |
| `replacement_ablation` | 9 |
| `reverse_incentive` | 1 |
| `sham_placebo` | 3 |

## Sampling Reason Distribution

| Sampling reason | Rows |
|---|---:|
| `aeor_cdr_positive_25` | 25 |
| `clean_balanced` | 16 |
| `clean_paired_twin` | 14 |
| `ivr_positive_all33` | 33 |
| `mgr_positive_all29` | 29 |
| `upr_positive_all3` | 3 |

## Pair Preservation

The sample includes 22 same-model neutral/pressure pair groups where both twins are present. Pair preservation was applied after required scarce positives and model-cap constraints.

## Updated Assets

| Artifact | Rows | SHA-256 |
|---|---:|---|
| `validation/medinsider_validation_space/data/episodes.json` | 120 | `98c6fc800346a94a0df37cf29deb4d875130979aeacbf0c21de96ae5bb82c66b` |
| `validation/medinsider_validation_space/data/medinsider_validation_manifest.csv` | 120 | `e69ac3c9559040b4069f59c879e5470f902caabb594f97ff0ead9b3a63c97b11` |
| `validation/medinsider_validation_space/data/expected_manifest_shas.json` |  | `ce43558b01cf691d67bfddfb23f1cdf5f8d1bde4dafa3820d5d9e277e81d7827` |
| `docs/validation/blinded_gold_label_set.csv` | 120 | `8fea63e4d279016f2649b3e4a6479c13b1faff82f61651bbd73fecb057ab3b07` |
| `docs/validation/blinded_gold_label_admin.csv` | 120 | `a78750b5a9a709480ed61a8330e69206b8de0d1cb655685df95e16dc97e89d85` |
