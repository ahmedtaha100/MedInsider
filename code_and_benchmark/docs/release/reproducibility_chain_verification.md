# Reproducibility Chain Verification 20260505

## Scope

This check verified the artifact chain referenced by the paper and release materials without modifying scored outputs, scenario files, scoring code, or locked manifests.

## Manifests

| Artifact | Status |
|---|---|
| Dataset manifest `artifacts/v2_manifest.csv` | Present |
| Full-run selection manifest `artifacts/subsets/v2_full_run_manifest.csv` | Present |
| Smoke selection manifest `artifacts/subsets/v2_smoke_manifest.csv` | Present |
| Small-pilot selection manifest `artifacts/subsets/v2_small_pilot_manifest.csv` | Present |
| Mitigation selection manifest `artifacts/subsets/v2_mitigation_compliance_gate_background_manifest.csv` | Present |
| Validation manifest `validation/medinsider_validation_space/data/medinsider_validation_manifest.csv` | Present |

## Locked Artifact Hashes

Source lock file:

```text
docs/validation/locked_scoring_targets.json
```

Hash verification over the lock file passed for 27 artifacts with 0 errors.

Checked groups:

| Group | Count | Row count evidence |
|---|---:|---|
| Single-run scored outputs | 6 | Each CSV has 840 scored rows |
| Gemma shard scored outputs | 10 | Each shard CSV has 84 scored rows |
| Paper table targets | 5 | Main result/caveat/condition/compute/roster CSVs present |
| Validation assets | 3 | Gold-label set/admin CSVs have 120 rows |
| Validation tool assets | 3 | Tool manifest has 120 rows; JSON assets match locked hashes |

The six single-run scored outputs cover GPT, Sonnet, Opus, Kimi, GLM, and DeepSeek lanes. The Gemma lane is represented by 10 locked shards of 84 rows each.

## Paper Table Targets

The lock hash check passed for:

- `docs/paper/final_table3_seven_model_results.csv`
- `docs/paper/final_table3_model_caveats.csv`
- `docs/paper/final_table7_condition_breakdown.csv`
- `docs/paper/final_compute_appendix_seven_model.csv`
- `docs/research_package/final_roster_status_matrix.csv`

These are the locked CSV artifacts used by the manuscript's main benchmark tables and release packet.

## Validation Artifacts

Current validation artifacts are present:

- `docs/validation/blinded_gold_label_set.csv`
- `docs/validation/blinded_gold_label_admin.csv`
- `docs/validation/metric_validation_results.json`
- `docs/validation/validation_summary_120.csv`
- `docs/validation/q2_dissent_adjudications.csv`
- `docs/validation/kappa_tables.csv`
- `docs/validation/validation_results.md`
- `docs/validation/gold_set_resampling.md`

The locked validation tool assets also passed hash verification:

- `validation/medinsider_validation_space/data/medinsider_validation_manifest.csv`
- `validation/medinsider_validation_space/data/episodes.json`
- `validation/medinsider_validation_space/data/expected_manifest_shas.json`

## Paper Packet Builder

Command tested in a fresh clone:

```bash
python scripts/build_final_supported_packet.py
```

Result: failed in the fresh clone.

Failure:

```text
FileNotFoundError: runs/codex_openai_full_run/artifacts/scored_episode_results.csv
```

The script depends on retained authoritative run or restore directories such as `tmp_restore_*/codex_*_full_run/` and Gemma restore roots. Those directories are available in the working release-preparation workspace but are not guaranteed to exist in a clean clone from tracked files alone.

Interpretation: the locked CSV outputs are present and hash-clean in the working tree, but the packet builder is not fully cold-clone reproducible unless the required authoritative run roots are packaged, restored automatically, or the builder is changed to consume the locked CSV packet directly.

## Assessment

The locked artifact chain is internally consistent in the release-preparation workspace. The external-user reproducibility chain has one significant gap: rebuilding the final paper packet from a clean clone requires run-root artifacts that are not currently part of the tracked cold-clone surface.
