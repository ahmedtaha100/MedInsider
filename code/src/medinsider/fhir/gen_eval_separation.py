"""Generator/evaluator separation enforcement.

Ensures that the model used to generate agent episodes is from a DIFFERENT
model family than the model(s) used for evaluation (scoring judges). This
prevents confounded results where the generator "knows" the evaluator's
patterns and can game the scoring.

The authoritative v2/FHIR execution path now excludes Gemini and Scout from
the active roster. The canonical judge routing therefore centers on the
supported closed/API panel plus retained compatibility aliases for blocked
or historical lanes.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Model family registry
# ---------------------------------------------------------------------------

MODEL_FAMILIES: dict[str, list[str]] = {
    "openai": [
        "gpt-5.4",
        "gpt-5.4-2026-03-05",
        "gpt-oss-120b",
        "openai/gpt-oss-120b",
    ],
    "anthropic": [
        "claude-opus-4-7",
        "claude-sonnet-4-6",
    ],
    "alibaba": [
        "qwen3.5-plus",
        "qwen3.5-plus-2026-02-15",
        "qwen-plus",
    ],
    "moonshot": [
        "kimi-k2.6",
    ],
    "zhipu": [
        "glm-5",
    ],
    "deepseek": [
        "deepseek-chat",
        "deepseek-reasoner",
    ],
}

# Reverse lookup: model_id -> family
_MODEL_TO_FAMILY: dict[str, str] = {}
for _family, _models in MODEL_FAMILIES.items():
    for _model in _models:
        _MODEL_TO_FAMILY[_model.lower()] = _family

JUDGE_ROUTING: dict[str, tuple[str, str]] = {
    "gpt-5.4": ("claude-opus-4-7", "claude-sonnet-4-6"),
    "gpt-5.4-2026-03-05": ("claude-opus-4-7", "claude-sonnet-4-6"),
    "gpt-oss-120b": ("claude-opus-4-7", "claude-sonnet-4-6"),
    "openai/gpt-oss-120b": ("claude-opus-4-7", "claude-sonnet-4-6"),
    "claude-opus-4-7": ("gpt-5.4", "deepseek-chat"),
    "claude-sonnet-4-6": ("gpt-5.4", "deepseek-chat"),
    "qwen3.5-plus": ("gpt-5.4", "claude-opus-4-7"),
    "qwen3.5-plus-2026-02-15": ("gpt-5.4", "claude-opus-4-7"),
    "qwen-plus": ("gpt-5.4", "claude-opus-4-7"),
    "kimi-k2.6": ("gpt-5.4", "claude-opus-4-7"),
    "glm-5": ("gpt-5.4", "claude-opus-4-7"),
    "deepseek-chat": ("gpt-5.4", "claude-opus-4-7"),
    "deepseek-reasoner": ("gpt-5.4", "claude-opus-4-7"),
}


def get_model_family(model_id: str) -> str:
    """Return the model family for a given model ID.

    Returns "unknown" if the model is not in the registry.
    """

    normalized = model_id.lower().strip()
    if normalized in _MODEL_TO_FAMILY:
        return _MODEL_TO_FAMILY[normalized]
    # Substring fallback: require minimum 4 chars to avoid short-token false positives
    matches = [
        (len(m), family) for family, models in MODEL_FAMILIES.items() for m in models if len(m) >= 4 and m in normalized
    ]
    if matches:
        return max(matches)[1]
    return "unknown"


def validate_separation(
    generator_model: str,
    evaluator_models: list[str],
) -> dict[str, Any]:
    """Validate that generator and evaluator models are from different families.

    Returns a validation result dict with pass/fail status and details.
    """

    gen_family = get_model_family(generator_model)
    eval_families = {m: get_model_family(m) for m in evaluator_models}

    conflicts = [model for model, family in eval_families.items() if family == gen_family and family != "unknown"]

    # Reject exact model identity even if both are unknown
    identity_conflicts = [
        model for model in evaluator_models if model.lower().strip() == generator_model.lower().strip()
    ]
    conflicts = list(set(conflicts + identity_conflicts))

    return {
        "valid": len(conflicts) == 0,
        "generator_model": generator_model,
        "generator_family": gen_family,
        "evaluator_models": eval_families,
        "conflicts": conflicts,
        "recommendation": (
            None if not conflicts else f"Replace evaluator(s) {conflicts} - same family '{gen_family}' as generator"
        ),
    }


def assigned_judges_for(agent_model: str) -> tuple[str, str]:
    """Return the canonical (primary, calibration) judge pair for an agent model."""

    normalized = agent_model.lower().strip()
    if normalized in JUDGE_ROUTING:
        return JUDGE_ROUTING[normalized]
    raise ValueError(f"unknown_agent_model:{agent_model}")


def stamp_episode_metadata(
    episode_metadata: dict[str, Any],
    generator_model: str,
) -> dict[str, Any]:
    """Add generator model family metadata to an episode."""

    episode_metadata["generator_model"] = generator_model
    episode_metadata["generator_family"] = get_model_family(generator_model)
    return episode_metadata


def stamp_score_metadata(
    score: dict[str, Any],
    evaluator_model: str,
) -> dict[str, Any]:
    """Add evaluator model family metadata to a score."""

    if "metadata" not in score:
        score["metadata"] = {}
    score["metadata"]["evaluator_model"] = evaluator_model
    score["metadata"]["evaluator_family"] = get_model_family(evaluator_model)
    return score
