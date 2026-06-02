# Limitations

*Placed as Section 2 of the paper per NeurIPS best practices for prominent
limitation disclosure.*

---

## L1: Synthetic Scenarios
All clinical scenarios are procedurally generated from templates, not derived
from real patient encounters. While expert labelers assess realism (1-5 scale)
and the provenance table grounds each family in real regulatory patterns, the
benchmark remains a stylized stress test. Generalization to production EHR
environments requires additional validation with real clinical data.

## L2: Pressure Simulation Fidelity
System prompt framing is a proxy for real institutional pressure. Actual
deployment pressure operates through RLHF reward signals, fine-tuning
objectives, and organizational culture — mechanisms not captured here.
Our results represent a *lower bound* on vulnerability: models that yield
to simulated prompt pressure are likely more vulnerable to real deployment
pressure.

## L3: Rule-Based Scoring Coverage
The scorer covers 6 primary metrics with 24 hardened edge cases, but cannot
detect all possible integrity violations. Novel violation patterns not
anticipated in the scoring spec will be missed. The dual-judge system
(automatic + model-based) partially mitigates this. Expert-validation
infrastructure is prepared, but scorer-expert agreement is not yet quantified
because no completed human labels are on disk.

## L4: Scenario Family Coverage
Five scenario families cover major healthcare fraud enforcement categories
but do not exhaustively represent all integrity risks. Notably absent:
medication diversion, credential misrepresentation, patient selection bias,
and research data integrity. Future versions may expand coverage.

## L5: Language and Regulatory Context
All scenarios are in English and grounded in US healthcare regulations
(CMS, DOJ/HHS, HIPAA). Findings may not generalize to other healthcare
systems, languages, or regulatory frameworks.

## L6: Single-Episode Measurement
Each scenario measures a single episode interaction. Real integrity failures
may emerge over multiple sessions, under accumulated pressure, or through
gradual norm erosion. Longitudinal measurement is out of scope.

## L7: Expert Labeler Availability
Expert validation quality depends on recruited labelers' clinical and
coding expertise. We target dual kappa >= 0.7 on IVR and ATC, but the current
repository has only reached the human-labeling boundary: blinded label sets,
admin mappings, and review logs are prepared, while completed reviewer labels
remain external and pending.

## L8: Propensity vs. Deployment Behavior
MedInsider measures *propensity* — how a model behaves under controlled
pressure in a sandbox environment. This is a necessary but not sufficient
condition for predicting deployment behavior, which is also shaped by
system-level safeguards, human oversight, and organizational controls.
