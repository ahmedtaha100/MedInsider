# Provenance Table

Maps each scenario family to its regulatory grounding, ensuring the benchmark
targets integrity risks that regulators actively pursue.

| Scenario Family | Regulatory Source | Year | Citation | Integrity Risk |
|----------------|------------------|------|----------|----------------|
| Coding & Billing Pressure | HHS Office of Inspector General | 2024 | [HHS-OIG June 2024 Work Plan](https://oig.hhs.gov/documents/root/11322/Work-Plan-June-2024.xlsx): Audit of Medicare Emergency Department Evaluation and Management Services (W-00-21-35877; W-00-22-35877) | Upcoding, unbundling, complexity inflation |
| Quality Metric Pressure | CMS Quality Payment Program | 2024 | CMS QPP Final Rule 2024: Merit-based Incentive Payment System | Gaming quality measures without delivering care |
| Readmission Pressure | CMS Hospital Readmissions Reduction Program | 2023 | 42 CFR 412.152: Excess readmission ratio calculation | Suppressing readmission risk in discharge docs |
| Safety Event Pressure | DOJ-HHS False Claims Act Working Group | 2025 | [2025-07-02 announcement](https://www.justice.gov/opa/pr/doj-hhs-false-claims-act-working-group): "Manipulation of EHR systems to drive inappropriate utilization" (updated 2025-07-03) | Omitting or minimizing adverse event documentation |
| Throughput Pressure | The Joint Commission | 2017 | [Sentinel Event Alert 58: "Inadequate hand-off communication"](https://www.jointcommission.org/en-us/knowledge-library/newsletters/sentinel-event-alert/issue-58) | Skipping safety checks under census pressure |

## Citation Verification

- **DOJ 2025**: The linked release was announced on 2025-07-02 and updated on
  2025-07-03.
- **HHS-OIG**: The linked June 2024 Work Plan identifies the E/M documentation
  audit and its project numbers. This is family-level regulatory grounding,
  not a claim that the synthetic scenarios implement that audit's payment rules.
- **CMS QPP**: Federal Register final rules available at cms.gov
- **Joint Commission**: Sentinel Event Alerts available at jointcommission.org

## Relationship to Scoring Metrics

| Family | Primary Metrics Targeted |
|--------|------------------------|
| Coding & Billing | UPR (integrity + compliance), IVR |
| Quality Metric | MGR, CDR |
| Readmission | CDR, IVR |
| Safety Event | AEOR, CDR, IVR |
| Throughput | PSD, CDR |
