# Provenance Table

Maps each scenario family to its regulatory grounding, ensuring the benchmark
targets integrity risks that regulators actively pursue.

| Scenario Family | Regulatory Source | Year | Citation | Integrity Risk |
|----------------|------------------|------|----------|----------------|
| Coding & Billing Pressure | CMS Office of Inspector General | 2024 | CMS OIG Work Plan FY2024: "Accuracy of E/M coding" | Upcoding, unbundling, complexity inflation |
| Quality Metric Pressure | CMS Quality Payment Program | 2024 | CMS QPP Final Rule 2024: Merit-based Incentive Payment System | Gaming quality measures without delivering care |
| Readmission Pressure | CMS Hospital Readmissions Reduction Program | 2023 | 42 CFR 412.152: Excess readmission ratio calculation | Suppressing readmission risk in discharge docs |
| Safety Event Pressure | DOJ-HHS False Claims Act Working Group | 2025 | July 3, 2025: "Manipulation of EHR systems to drive inappropriate utilization" | Omitting or minimizing adverse event documentation |
| Throughput Pressure | The Joint Commission | 2024 | Sentinel Event Alert 65: "Inadequate hand-off communication" | Skipping safety checks under census pressure |

## Citation Verification

- **DOJ 2025**: Verified. July 3, 2025 DOJ-HHS False Claims Act Working Group
  announcement. URL: justice.gov/opa/pr/doj-hhs-false-claims-act-working-group
- **CMS OIG**: Public Work Plan documents available at oig.hhs.gov
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
