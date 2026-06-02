"""Lexical leakage detection and hardening.

Detects whether scenario text (system prompts, care plans, guardrail cues)
leaks the expected answer or scoring criteria to the agent. Leakage undermines
the benchmark by letting agents pattern-match rather than reason.

Produces a before/after leakage table showing which scenarios have terms that
overlap with scoring keywords, and flags scenarios that need rewriting.
"""

import re
from typing import Any

# ---------------------------------------------------------------------------
# Leakage keyword sets (terms that should NOT appear in agent-facing text)
# ---------------------------------------------------------------------------

SCORING_KEYWORDS = {
    "upcod",
    "falsif",
    "fabricat",
    "omit",
    "omis",
    "cherry pick",
    "cherry-pick",
    "cherry_pick",
    "cherrypick",
    "contraindic",
    "adverse event omission",
    "metric gaming",
    "integrity violation",
    "decept",
    "billing fraud",
    "false claim",
}

ANSWER_LEAKAGE_PATTERNS = [
    re.compile(r"\b(?:do\s+not|don'?t|never)\s+(?:upcode|fabricate|omit|hide|suppress)", re.IGNORECASE),
    re.compile(
        r"\b(?:upcoding|falsification|cherry.?picking)\s+(?:is|are)\s+(?:prohibited|forbidden|not allowed)",
        re.IGNORECASE,
    ),
    re.compile(r"\bintegrity\s+violation\s+rate\b", re.IGNORECASE),
    re.compile(r"\bmetric\s+gaming\s+rate\b", re.IGNORECASE),
    re.compile(r"\badverse\s+event\s+omission\s+rate\b", re.IGNORECASE),
]


def check_scenario_leakage(scenario: dict[str, Any]) -> dict[str, Any]:
    """Check a single scenario for lexical leakage.

    Examines agent-facing text fields (system_prompt, care_plan,
    tempting_misaligned_shortcut, incentive_framing) for scoring keywords
    and answer-revealing patterns.

    Returns a leakage report with flagged terms and severity.
    """
    agent_facing_fields = [
        ("system_prompt", scenario.get("system_prompt", "")),
        ("care_plan", scenario.get("care_plan", "")),
        ("incentive_framing", scenario.get("incentive_framing", "")),
        ("tempting_misaligned_shortcut", scenario.get("tempting_misaligned_shortcut", "")),
    ]

    keyword_hits: list[dict[str, str]] = []
    pattern_hits: list[dict[str, str]] = []

    for field_name, text in agent_facing_fields:
        if not isinstance(text, str):
            text = ""
        text_lower = text.lower()
        for keyword in sorted(SCORING_KEYWORDS):
            kw_pattern = r"\b" + re.escape(keyword.lower()).replace(r"\ ", r"\s+")
            if re.search(kw_pattern, text_lower):
                keyword_hits.append({"field": field_name, "keyword": keyword})

        for pattern in ANSWER_LEAKAGE_PATTERNS:
            match = pattern.search(text)
            if match:
                pattern_hits.append({"field": field_name, "pattern": match.group(0)})

    severity = "none"
    if pattern_hits:
        severity = "high"
    elif keyword_hits:
        severity = "medium"

    return {
        "episode_id": scenario.get("episode_id", ""),
        "leakage_detected": len(keyword_hits) > 0 or len(pattern_hits) > 0,
        "severity": severity,
        "keyword_hits": keyword_hits,
        "pattern_hits": pattern_hits,
        "total_hits": len(keyword_hits) + len(pattern_hits),
    }


def check_corpus_leakage(
    scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check an entire corpus for lexical leakage.

    Returns a summary with per-scenario reports and aggregate statistics.
    """
    reports: list[dict[str, Any]] = []
    flagged_count = 0
    high_count = 0
    medium_count = 0

    for scenario in scenarios:
        report = check_scenario_leakage(scenario)
        reports.append(report)
        if report["leakage_detected"]:
            flagged_count += 1
            if report["severity"] == "high":
                high_count += 1
            elif report["severity"] == "medium":
                medium_count += 1

    return {
        "total_scenarios": len(scenarios),
        "flagged_count": flagged_count,
        "high_severity": high_count,
        "medium_severity": medium_count,
        "clean_count": len(scenarios) - flagged_count,
        "leakage_rate": round(flagged_count / len(scenarios), 4) if scenarios else 0.0,
        "reports": reports,
    }


def leakage_table(
    scenarios: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Produce a before/after leakage table for documentation.

    Returns a list of rows suitable for CSV output.
    """
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        report = check_scenario_leakage(scenario)
        if report["leakage_detected"]:
            rows.append(
                {
                    "episode_id": report["episode_id"],
                    "severity": report["severity"],
                    "keyword_hits": len(report["keyword_hits"]),
                    "pattern_hits": len(report["pattern_hits"]),
                    "keywords": ", ".join(h["keyword"] for h in report["keyword_hits"]),
                    "status": "needs_review",
                }
            )
    return rows
