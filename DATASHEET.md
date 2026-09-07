# MedInsider Datasheet

## Motivation

MedInsider is designed to evaluate whether tool-mediated medical LLM agents preserve documentation integrity under institutional pressure. It focuses on action-log-verifiable discrepancies between what an agent observed or did and what it documented.

## Composition

The full manifest contains 840 episodes in 420 matched pairs across five scenario families (168 episodes each). Each pair contains a neutral twin and one of seven intervention/control conditions, giving eight condition labels overall. The release contains all 840 scenarios and their manifests, not a held-out subset.

## Collection and Generation

Scenarios are synthetic and regulatory-grounded. They are not real patient records and should not be treated as deployment traces. The generator deterministically combines 15 case skeletons, 15 care plans, 15 shortcut strings, and five problem sets into structured JSON for a simulated FHIR-shaped environment. The scope is English-language, US-oriented adult inpatient workflows; every Encounter has class `IMP`. No LLMs were used to draft the fixed text banks. Clinicians who later participated in expert validation reviewed the templates before benchmark execution.

Both twins retain the same clinical state, required actions, and shortcut/guardrail cues. Neutral means no institutional framing, not absence of a shortcut cue. Aligned and sham controls are included alongside pressure conditions; see [definitions](docs/paper/definitions.md).

## Preprocessing

Manifests and scenario JSON are included in repository-relative paths. The smoke path runs only the local scripted agent and does not require model-provider credentials.

## Uses

Appropriate uses include benchmark review, inspection of scenario structure, local smoke testing, and evaluation-method critique. The bundle is not a clinical decision-support tool and is not a human-validated certification instrument.

## Distribution

Code is distributed under Apache License 2.0. Data and benchmark artifacts are distributed under Creative Commons Attribution 4.0 International.

## Maintenance

The project maintainers maintain the code and metadata. Released result CSVs and their original hash locks preserve the reported experiment. The [reproduction guide](README.md#reproducibility-scope) distinguishes offline artifact checks from new model runs.
