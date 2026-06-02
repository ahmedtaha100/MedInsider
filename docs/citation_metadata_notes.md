# Citation Metadata Notes

This note records citation metadata cleanups identified after manuscript freeze.
It does not modify the frozen manuscript, bibliography source, or submitted PDF.

## Anthropic Agentic Misalignment

The manuscript bibliography URL/title/date are accurate, but the local frozen
BibTeX uses a corporate author. The source's own citation guidance uses named
authors beginning with Lynch et al. and `Anthropic Research, 2025`.

Recommended post-freeze bibliography update:

- Replace the corporate-author entry with the source-provided named-author
  citation metadata, or add an explicit note that the manuscript is citing the
  web page as an organizational page.

## ArXiv DOI Consistency

The following cited arXiv works have resolvable arXiv DOI fields that are not
present in the frozen `.bib`:

| Citation key | DOI to add in a post-freeze bibliography update |
|---|---|
| `healthbench2025` | `10.48550/arXiv.2505.08775` |
| `fhiragentbench2025` | `10.48550/arXiv.2509.19319` |
| `ehrchatqa2025` | `10.48550/arXiv.2509.23415` |

## ArXiv Version-Date Precision

`agentharm2025` uses April 2025 metadata in the frozen bibliography. If keeping
the April 2025 date, the post-freeze bibliography should explicitly identify
the revised arXiv version, `arXiv:2410.09024v3`. If citing the first submission
instead, use the original 2024 posting year.

## Model Identifier Provenance

Provider model-card or release-note citations were not added to the frozen
manuscript bibliography. The submitted artifact records model identifiers and
routes in the code bundle and scored-output provenance. Add provider/model-card
citations in a future manuscript revision where stable public citations exist.
