# Ethics Statement

## IRB and Human Subjects

This benchmark uses **synthetic clinical scenarios** — no real patient data is
collected, stored, or processed. All patient demographics, vital signs, lab
values, and clinical narratives are procedurally generated from templates.
No IRB review was required because no human subjects are involved in data
collection.

Expert labelers (physicians and compliance/coding specialists) evaluate
synthetic scenarios and agent outputs. Their participation is voluntary
professional consultation, not human-subjects research. Labelers are
compensated at fair-market rates and may withdraw at any time.

## Provider Terms of Service

All model evaluations use official API endpoints in compliance with each
provider's terms of service:

- **OpenAI**: Usage complies with OpenAI's Usage Policies. Benchmark
  scenarios do not contain real patient information or violate the
  restricted-use provisions for medical advice.
- **Anthropic**: Usage complies with Anthropic's Acceptable Use Policy.
  Scenarios are clearly synthetic and used for safety research.
- **Google**: Usage complies with Google Cloud AI/ML terms. No real
  clinical data is transmitted.
- **Open-weight models**: Run on self-hosted infrastructure under each
  model's license (Llama Community License, Apache 2.0, etc.).

## Dual-Use Considerations

MedInsider is designed to **detect** integrity failures in medical AI agents,
not to **teach** models how to game clinical systems. However, we acknowledge
dual-use risk:

**Risk**: The scenario templates and shortcut prompts could theoretically be
used to fine-tune models toward integrity violations.

**Mitigations**:
1. **Scenario design**: Shortcut prompts describe general pressure patterns,
   not step-by-step exploitation instructions.
2. **Hidden test set**: 50% of scenarios are held out and not publicly
   released, limiting exposure of evaluation targets.
3. **Scoring transparency**: The scoring spec is public so that model
   developers can proactively test and fix integrity failures.
4. **Responsible disclosure**: If we discover that a specific model exhibits
   severe integrity failures (e.g., systematic adverse event suppression),
   we will notify the model provider before public disclosure.

## Broader Impact

This benchmark serves the public interest by:
- Providing the first standardized measurement of integrity propensity in
  medical AI agents under institutional pressure.
- Enabling model developers to identify and fix integrity failures before
  clinical deployment.
- Supporting regulatory bodies (DOJ, HHS) in understanding AI-mediated
  compliance risks.
- Contributing to the safety evaluation ecosystem alongside capability
  benchmarks.

We do not claim that passing MedInsider guarantees safe clinical deployment.
The benchmark measures one dimension of safety (integrity under pressure)
and should be used alongside clinical validation, human oversight, and
regulatory approval processes.
