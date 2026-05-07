# Claims, Assumptions, and Limitations for Current Evidence

> Status note (2026-05-05): this document is aligned to the post-rerun locked
> seven-model execution package plus the bounded coding-probe and
> structural-mitigation add-ons. It is not a statement of the broader original
> proposal.

## Claims That Remain Supported Now

| # | Claim | Evidence | Status |
|---|---|---|---|
| C1 | The benchmark measures integrity under institutional pressure in tool-mediated FHIR workflows. | `docs/protocol/PROTOCOL.md`, `docs/scoring/formal_scoring_spec_v1.md`, audited run artifacts | Supported now |
| C2 | The current package supports run-level analysis across the fixed seven-model execution roster, with all main-benchmark lanes complete after targeted reruns. | `docs/research_package/final_roster_status_matrix.csv`, authoritative run dirs, Gemma shard closeout report | Supported now |
| C3 | No research-critical run artifact is missing from the seven authoritative completed lanes. | package audit, `docs/research_package/final_truth_audit_summary.md`, `audit/rerun_plan/post_rerun_summary_20260505.md` | Supported now |
| C4 | The benchmark distinguishes compliance failures from integrity failures. | formal scoring spec plus scored outputs | Supported now |
| C5 | ATC is a co-primary metric inside the integrity package. | formal scoring spec plus current run outputs | Supported now |
| C6 | Within the audited closed-model v2/FHIR subset, workflow capability completion does not guarantee integrity-clean behavior on the same local tasks. | `docs/research_package/capability_control_within_scenario_source.csv`, `docs/research_package/capability_control_model_summary.csv` | Partially supported now |
| C7 | A bounded standalone coding-knowledge probe exists for the fixed roster. | `docs/research_package/coding_probe_model_summary.csv`, `docs/research_package/coding_probe_family_summary.csv`, `docs/research_package/coding_probe_question_results.csv` | Partially supported now |
| C8 | One bounded dedicated structural mitigation experiment exists. | `docs/research_package/structural_mitigation_comparison.csv`, `docs/research_package/structural_mitigation_summary.md`, `docs/research_package/structural_mitigation_execution_roster.csv` | Partially supported now |

## Claims That Must Be Narrowed

| Old claim | Safe narrowed version |
|---|---|
| The benchmark measures integrity under pressure, not just capability. | The benchmark measures integrity under pressure and records ATC as a co-primary; the current package also supports a narrower internal workflow-capability versus integrity analysis on a closed-model subset. |
| Capability and integrity can be decoupled. | Within the audited closed-model v2/FHIR subset, workflow capability completion does not guarantee integrity-clean behavior on the same local tasks. |
| Frontier models differ on integrity under pressure. | The fixed seven-model execution roster differs descriptively on integrity-under-pressure outcomes in the post-rerun locked scored outputs. |
| The project includes a coding probe. | The project includes a bounded fixed-bank coding probe for the full target roster, with provider-error caveats on four models. |
| The project includes a structural mitigation experiment. | The project includes one bounded `compliance_check_tool` experiment on the billing-and-quality `background_pressure` slice for four executed models; do not describe it as a broad mitigation suite. |

## Claims That Are Not Supported Yet

| Claim | Why not |
|---|---|
| Figure 1 cross-benchmark capability rank versus integrity rank | no MedAgentBench-backed or other external capability package exists locally |
| Broad unqualified decoupling headline | the current evidence is within-benchmark and closed-model only |
| Full uncaveated panel-wide auxiliary experiments | the main seven-model execution roster is evidenced now, but the coding probe and mitigation add-ons remain bounded and caveated |
| Ranking-distinctness against adjacent benchmarks | no adjacent-benchmark result layer exists locally |
| Uncaveated coding-knowledge probe claims | the current probe has provider-error caveats on four models even though the full target roster now has scored rows |
| Inter-rater kappa claims | no current annotation package is packaged |
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
| fully regenerated seven-model paper packet | supported now |
| ranking-distinctness study | not supported yet |
| expert-validation kappa claims | not supported yet |
