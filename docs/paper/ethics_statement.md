# Ethics statement

## Synthetic cases and expert review

All clinical cases, demographics, laboratory values, and chart narratives are synthetic. The authors report that the benchmark experiments required no IRB approval because they involved no human subjects or patient-derived data.

Four professional reviewers supplied the ratings analyzed in the validation study. The author-confirmed record states that written/electronic consent preceded labeling, each reviewer received a USD 800 flat fee, and reviewers could decline or stop; none withdrew. No reviewer authored scenarios or scorer code, and no employment, supervisory, or family relationship with the authors was reported beyond compensated review.

No formal institutional determination was sought or obtained. Synthetic clinical cases and expert participation are distinct aspects of the study; this statement does not assert an institutional approval or exemption. The available consent record does not establish permission to release individual response rows.

## Model routes

Provider-hosted lanes used their documented API routes. Gemma 4 used `google/gemma-4-31B-it` through an OpenAI-compatible endpoint on two H200 GPUs. Exact run configurations are retained under `code/configs/phase4_v2/`. New users must use routes and licenses applicable to their selected model; this release does not attest blanket compliance with every provider's terms.

## Use and limits

MedInsider measures documentation integrity in a synthetic stress test. Its pressure prompts may be misused as examples of shortcuts; they are evaluation cases, not operational instructions. All 840 scenarios are released; there is no undisclosed 50% test partition. Transparent scoring supports inspection, but passing the benchmark does not certify clinical safety, regulatory compliance, or readiness for patient care.
