# Benchmark Comparison Table for Current Paper Scope

This table is benchmark-positioning prose only. It should not be used as
empirical evidence for unsupported ranking-distinctness or cross-benchmark
decoupling claims.

| Dimension | MedInsider current package | MedAgentBench | EHR-ChatQA | AgentHarm | MACHIAVELLI |
|---|---|---|---|---|---|
| Domain | Medical EHR | Medical EHR | Medical EHR | General agent | Text games |
| Primary measure | Integrity under pressure | Task completion | QA accuracy | Harmful compliance | Ethical violations |
| Pressure simulation | Yes | No | No | Yes | Yes |
| Paired design | Yes | No | No | No | No |
| FHIR tools | Yes | Yes | No | No | No |
| Action-log verifiability | Yes | task dependent | limited | limited | game logs |
| Integrity metrics | IVR, MGR, UPR, AEOR, PSD, CDR | No | No | harm-focused | ethics-focused |
| Capability-control evidence in the current repo | Narrow internal within-benchmark workflow-capability subset only | native task capability benchmark | not applicable | not applicable | not applicable |
| Cross-benchmark decoupling evidence in the current repo | Not yet supported | not applicable | not applicable | not applicable | not applicable |
| Regulatory grounding | Yes | limited | limited | No | No |
| Mitigation evidence in the current package | Honesty-system-prompt condition only | No | No | benchmark dependent | No |
| Reproducibility status in the current package | hash-pinned audited closed-model package | benchmark dependent | benchmark dependent | benchmark dependent | benchmark dependent |

## Safe positioning notes

1. MedInsider's current repository evidence supports benchmark positioning and
   the audited closed-model package.
2. It does not currently support empirical ranking-distinctness or cross-
   benchmark correlation claims.
3. The current capability-control layer is internal and within-benchmark, not
   MedAgentBench-backed.
