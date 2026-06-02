# Claims, Assumptions, and Limitations for Current Evidence

> Status note (2026-06-01): this document is aligned to the submitted
> code-and-benchmark bundle, the final seven-model paper tables, the bundled
> per-episode scored outputs, and the validation summaries. It is not a
> statement of older internal restore trees or missing research-package files.

## Claims That Remain Supported Now

| # | Claim | Evidence | Status |
|---|---|---|---|
| C1 | The benchmark measures integrity under institutional pressure in tool-mediated FHIR workflows. | `docs/protocol/PROTOCOL.md`, `docs/scoring/formal_scoring_spec_v1.md`, `data/manifests/v2_manifest.csv`, `data/scored_outputs/per_episode/` | Supported now |
| C2 | The current package supports run-level analysis across the fixed seven-model execution roster, with all main-benchmark lanes complete. | `docs/paper/final_table3_seven_model_results.csv`, `docs/paper/final_table3_model_caveats.csv`, `data/scored_outputs/per_episode/` | Supported now |
| C3 | The submitted paper-table layer is backed by shipped CSVs and per-episode scored outputs. | `docs/paper/final_supported_source_inventory.csv`, `docs/paper/`, `data/scored_outputs/per_episode/` | Supported now |
| C4 | The benchmark distinguishes compliance failures from integrity failures. | `docs/scoring/formal_scoring_spec_v1.md`, `docs/paper/definitions.md`, `data/scored_outputs/per_episode/` | Supported now |
| C5 | ATC is a co-primary metric inside the integrity package. | `docs/scoring/formal_scoring_spec_v1.md`, `docs/paper/final_table3_seven_model_results.csv` | Supported now |
| C6 | Within the submitted v2/FHIR corpus, task-completion and integrity-clean behavior differ descriptively on the same local tasks. | `docs/paper/final_table3_seven_model_results.csv`, `docs/paper/final_table5_condition_breakdown.csv`, `data/scored_outputs/per_episode/` | Supported now |
| C7 | A bounded standalone coding-knowledge probe exists for the fixed roster. | `docs/paper/final_table6_coding_probe.csv` | Supported now as an auxiliary bounded probe |
| C8 | One bounded dedicated structural mitigation experiment exists. | `docs/paper/final_table7_mitigation.csv`, `data/manifests/subsets/v2_mitigation_compliance_gate_background_manifest.csv` | Supported now as an auxiliary bounded experiment |
| C9 | Expert validation summaries and agreement tables are included. | `docs/validation/validation_results.md`, `docs/validation/kappa_tables.csv`, `docs/validation/validation_summary_120.csv` | Supported now at the summary-table level |

## Claims That Must Be Narrowed

| Old claim | Safe narrowed version |
|---|---|
| The benchmark measures integrity under pressure, not just capability. | The benchmark measures integrity under pressure and records ATC as a co-primary; the current package also supports a narrower internal workflow-capability versus integrity analysis on a closed-model subset. |
| Capability and integrity can be decoupled. | Within the submitted v2/FHIR corpus, task-completion and integrity-clean behavior differ descriptively on the same local tasks. |
| Frontier models differ on integrity under pressure. | The fixed seven-model execution roster differs descriptively on integrity-under-pressure outcomes in the post-rerun locked scored outputs. |
| The project includes a coding probe. | The project includes a bounded fixed-bank coding probe for the fixed roster; treat it as auxiliary, not as a broad capability benchmark. |
| The project includes a structural mitigation experiment. | The project includes one bounded `compliance_check_tool` experiment on the billing-and-quality `background_pressure` slice for four executed models; do not describe it as a broad mitigation suite. |

## Claims That Are Not Supported Yet

| Claim | Why not |
|---|---|
| Figure 1 cross-benchmark capability rank versus integrity rank | no MedAgentBench-backed or other external capability package exists locally |
| Broad unqualified decoupling headline | the current evidence is within-benchmark and closed-model only |
| Full uncaveated panel-wide auxiliary experiments | the main seven-model execution roster is evidenced now, but the coding probe and mitigation add-ons remain bounded |
| Ranking-distinctness against adjacent benchmarks | no adjacent-benchmark result layer exists locally |
| Uncaveated coding-knowledge capability claims | the current probe is a fixed 15-question auxiliary bank |
| Raw 480-response validation release claims | validation summaries and agreement tables are included, but raw reviewer submissions are not included until separately packaged |
| MIMIC-IV-FHIR anchor claims | no current real-chart subset artifacts are packaged |
| Broader mitigation-suite claims | only one bounded `compliance_check_tool` study plus the honesty-system-prompt condition are evidenced |

## Assumptions That Still Apply

| # | Assumption | Current handling |
|---|---|---|
| A1 | Pressure framing is a stylized lower-bound proxy for deployment pressure. | Keep explicitly as a limitation. |
| A2 | Synthetic scenarios can still support a valid integrity-under-pressure benchmark. | Keep explicitly as a limitation. |
| A3 | Deterministic scoring plus preserved action logs are sufficient for current run-level analysis. | Supported for the audited package. |
| A4 | The internal capability subset is a within-benchmark workflow-capability surface, not an external capability benchmark. | Must be stated every time Figure 2 or CLM2 appears. |

## Self-Sufficiency Check for Current Paper Text

| Item | Current status |
|---|---|
| closed-model integrity-under-pressure story | supported now |
| seven-model execution inventory | supported now |
| FHIR-native tool-mediated benchmark description | supported now |
| compliance-versus-integrity distinction | supported now |
| ATC as co-primary | supported now |
| narrowed internal Figure 2 | partially supported now |
| bounded coding-knowledge probe | partially supported now |
| bounded structural mitigation experiment | partially supported now |
| Figure 1 cross-benchmark decoupling | not supported yet |
| fully regenerated seven-model paper packet | supported at the shipped CSV/output level; cold-clone regeneration depends on the packet builder path |
| ranking-distinctness study | not supported yet |
| expert-validation kappa summaries | supported now |
| raw validation response release | not supported yet |
