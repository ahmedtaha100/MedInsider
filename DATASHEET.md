# MedInsider Datasheet

## Motivation

MedInsider is designed to evaluate whether tool-mediated medical LLM agents preserve documentation integrity under institutional pressure. It focuses on action-log-verifiable discrepancies between what an agent observed or did and what it documented.

## Composition

The full manifest contains 840 paired-twin episodes organized as 420 neutral/pressure pairs across five scenario families and eight incentive conditions. This reviewer bundle includes the full manifests and a small scenario sample for inspection and local smoke testing.

## Collection and Generation

Scenarios are synthetic and regulatory-grounded. They are not real patient records and should not be treated as deployment traces. Each episode is generated as structured JSON for a simulated FHIR-shaped environment.

## Preprocessing

Manifests and scenario JSON are included in repository-relative paths. The smoke path runs only the local scripted agent and does not require model-provider credentials.

## Uses

Appropriate uses include benchmark review, inspection of scenario structure, local smoke testing, and evaluation-method critique. The bundle is not a clinical decision-support tool and is not a human-validated certification instrument.

## Distribution

Code is distributed under Apache License 2.0. Data and benchmark artifacts are distributed under Creative Commons Attribution 4.0 International.

## Maintenance

The anonymous authors will maintain the public release package, metadata, and hosted artifacts according to conference requirements and post-review release commitments.
