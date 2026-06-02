# Code and Benchmark Bundle Verification 20260506

## Result

PASS. The packaged reviewer bundle installed in a fresh Python 3.11 virtual environment and `make reproduce` completed successfully with the provider-free smoke path.

## Fresh-Copy Smoke Evidence

- Verification copy: `.verification_tmp/reviewer_bundle_check` under the submission build directory.
- Install command: `python -m pip install -e ".[dev]"`.
- Reproduction command: `make reproduce`.
- Preflight: `ok=true`, 2 selected episodes, 1 validated pair, HF backup disabled.
- Smoke run: 2 / 2 successful episodes and 2 / 2 scored episodes in `code/runs/reviewer_smoke` inside the verification copy.

## Table Artifact Checks

| Table source | Check |
|---|---|
| `docs/paper/final_table3_seven_model_results.csv` | 7 model rows present; GPT-5.4 scored episodes = 840, pairs = 420, ATC = 0.7045. |
| `docs/paper/final_table4_refusal_partial.csv` | 7 model rows present; Table 4 frozen from scored outputs and matched manuscript counts exactly during build. |
| `docs/paper/final_table5_condition_breakdown.csv` | 98 rows present. |
| `docs/paper/final_table6_coding_probe.csv` | 7 model rows present. |
| `docs/paper/final_table7_mitigation.csv` | 4 rows present. |

## Anonymization Check

Required grep commands returned no matches:

```bash
identity/path grep over repository root
identity/path grep over dataset_release
```

Code bundle grep clean: True. Dataset release grep clean: True.

## Hugging Face Read-Only Context

The build used read-only Hugging Face API access to enumerate the project artifacts and confirm recoverability context. Repo IDs are anonymized here because the release bundles must not expose the author account.

| Artifact | Type | Accessible | Files | Bytes | Relevance |
|---|---|---:|---:|---:|---|
| `ANON-AUTHOR/medinsider-validation` | space | yes | 13 | 2022104 | deployed validation tool; source mirrored locally and copied into reviewer bundle after anonymization |
| `ANON-AUTHOR/medinsider-research-backup-primary` | dataset | yes | 21372 | 135442259 | private full-run backup; useful only as recovery source if local authoritative scored outputs are incomplete |
| `ANON-AUTHOR/medinsider-research-backup-secondary` | dataset | yes | 21372 | 135442259 | private mirror of primary; verification context only |
| `ANON-AUTHOR/medinsider-validation-responses` | dataset | yes | 7 | 112972 | private reviewer response dataset; aggregate/adjudicated outputs copied from local docs, raw responses not shipped |
| `ANON-AUTHOR/medinsider-validation-live-20260430` | space | yes | 15 | 1192001 | stale superseded validation Space; excluded |

No Hugging Face write operation was performed.

## Notes

- Release configs have `hf_backup.enabled=false` and no primary/secondary repository identifiers, except the scripted smoke config which has no HF backup block.
- Copied rerun `hf_backup_state.json` files were removed from the reviewer bundle because they only carried private backup provenance.
- The live repo still has some already-tracked scratch/profile files matching the new `.gitignore` patterns; this verification did not untrack or modify them because only `.gitignore` was allowed as a live-repo change.
