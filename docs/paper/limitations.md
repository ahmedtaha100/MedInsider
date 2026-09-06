# Limitations

## Clinical and pressure scope

The corpus is a synthetic English-language, US-oriented adult inpatient stress test, assembled from fixed template banks. It is not a representative sample of patient records, specialties, institutions, or real documentation failures. Prompt and inbox conditions model particular contextual changes; the observed rates are not a lower bound on real deployment risk. Both twins retain shortcut cues, and the seven non-neutral conditions include aligned and sham controls.

The benchmark scores agent-produced records before any subsequent human review, approval or override. It does not measure how those interventions change outcomes. Its fixed prompts do not establish robustness to optimized jailbreaks or adaptive attacks.

## Scoring and interpretation

The released deterministic scorer implements specific tool/phrase/code rules. It cannot detect every clinical inconsistency and does not infer intent. Per-episode rates with no scoring opportunity are zero, so low violation rates must be read alongside task completion. PSD is structurally untriggered; AEOR and CDR flag the same episode sets; UPR-integrity has only three positive rows. See [operational definitions](definitions.md).

The frozen `refused_misaligned_pressure` field is a conflict-label/zero-violation proxy that includes neutral rows. It does not measure observed refusal, resistance, or provider motivation. Frozen numeric values remain available for provenance under their original filenames.

## Expert agreement

Four reviewers rated 120 payloads (85 distinct episode IDs, 64 pair IDs). Source/model identities were hidden, but the scorer's Q2 answer was marked, so the findings establish scorer-assisted agreement and may reflect anchoring. No free-text explanations were supplied. The 120/120 scorer-majority match includes only 30 negative payloads; subtype coverage against the global Q2 verdict is not subtype-specific validation. High Q1/Q3 raw agreement coexists with low prevalence-sensitive kappa.

Retained responses do not preserve separate pre-marker and post-marker Q2 judgments, so they cannot establish whether answers changed after scorer exposure or quantify anchoring. The reported study contains no scorer-hidden re-review.

## Experimental and reproduction scope

Reported model estimates are descriptive single-run summaries. Changes in model aliases, provider implementations, sampling, or infrastructure may change a new run. The 15-question coding probe has incomplete response coverage for some models and does not measure multi-step tool behavior. The compliance gate was tested on 24 background-pressure episodes per model in two families and four models; its effects do not establish general mitigation efficacy.

The release reconstructs the main and condition tables from scored rows and verifies frozen artifacts and validation summaries. Its anonymous supplement supports frozen rescoring of all 5,880 main-run and 96 mitigation action logs, including reconstruction of the mitigation table. Anonymous joint-rating counts reproduce expert agreement statistics; identifying exports and payload-linked individual ratings remain private. Tool-action logs do not contain full provider conversations, and replay does not regenerate provider responses. Multi-session behavior, optimized jailbreak baselines, real-EHR validation, and broader mitigation studies are outside this release.
