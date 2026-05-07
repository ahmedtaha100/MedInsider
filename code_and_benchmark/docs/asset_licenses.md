# Asset And License Inventory

This inventory is for release review. It separates locally distributed assets from external services, evaluated models, and cited works. Items marked "confirm before public release" were not vendored locally and should be checked against upstream terms at release time.

## Repository Licenses

| Asset | Location | License status |
|---|---|---|
| Source code | `src/`, `scripts/`, `tests/` | Apache License 2.0, root `LICENSE` |
| Scenario corpus and benchmark data | `scenarios/`, `artifacts/`, `docs/`, `benchmark_versions/` where present | CC BY 4.0, root `DATA_LICENSE` |
| Reviewer bundle code | `submission/reviewer_bundle/code/` | Apache License 2.0 copy included in bundle |
| Reviewer bundle data | `submission/reviewer_bundle/data/` | CC BY 4.0 copy included in bundle |
| Validation tool source | `validation/medinsider_validation_space/` | Covered by repository code license unless otherwise separated before release |

## Evaluated Model And Provider Terms

These entries identify provider/model terms that govern access to evaluated systems. The benchmark does not redistribute provider model weights except where a user separately obtains an open-weight model.

| Model or provider surface | Local use in benchmark | Terms/license URL |
|---|---|---|
| OpenAI API models | Provider-backed runs through `openai` adapter | https://openai.com/policies/terms-of-use |
| Anthropic Claude models | Provider-backed runs through `claude` adapter | https://www.anthropic.com/legal/commercial-terms |
| Moonshot/Kimi API | Provider-backed `openai_compatible` lane | https://platform.moonshot.ai/ |
| Zhipu/GLM API | Provider-backed `openai_compatible` lane | https://open.bigmodel.cn/ |
| DeepSeek API | Provider-backed `openai_compatible` lane | https://cdn.deepseek.com/policies/en-US/deepseek-terms-of-use.html |
| Google Gemma | Open-weight lane served through local endpoint | https://ai.google.dev/gemma/terms |
| Hugging Face Hub/Spaces | Backup and validation deployment infrastructure | https://huggingface.co/terms-of-service |

Release note: confirm current provider terms before public release, especially for providers whose terms pages may vary by region or account type.

## Cited Benchmarks And External References

The manuscript cites adjacent benchmarks and policy sources for comparison and motivation. No third-party benchmark datasets are redistributed in MedInsider unless explicitly listed in the repository data license.

| Source | Use | License status |
|---|---|---|
| MedAgentBench | Cited related benchmark | Upstream license not vendored here; confirm before reusing artifacts |
| FHIR-AgentBench | Cited related benchmark | Upstream license not vendored here; confirm before reusing artifacts |
| HealthBench | Cited related benchmark | Upstream license not vendored here; confirm before reusing artifacts |
| CARES and other clinical-agent evaluations cited in the manuscript | Related-work citation only | Upstream license not vendored here |
| DOJ/HHS and CMS source material | Policy/regulatory motivation and scenario-template grounding | U.S. government source material is generally public domain; confirm specific pages before redistributing verbatim excerpts |
| Joint Commission safety-reporting standards | Scenario motivation and citation | External standards content is not redistributed as benchmark data |

## Direct Python Dependencies

Direct dependencies in `pyproject.toml`:

| Dependency | Purpose | License note |
|---|---|---|
| `huggingface_hub` | Hub backup and dataset/Space integration | Apache 2.0 |
| `matplotlib` | Plotting/report support | PSF-compatible/BSD-style license family |
| `ruff` | Dev lint/format checks | MIT |
| `pytest` | Test runner | MIT |
| `coverage[toml]` | Test coverage tooling | Apache 2.0 |

Validation Space dependencies:

| Dependency | Purpose | License note |
|---|---|---|
| `streamlit` | Reviewer UI | Apache 2.0 |
| `huggingface_hub` | HF response storage | Apache 2.0 |
| `httpx` | HTTP client support | BSD-3-Clause |
| `requests` | HTTP client support | Apache 2.0 |

No non-permissive direct Python dependency was identified in the release audit. A full transitive software bill of materials should be generated before a formal public release.
