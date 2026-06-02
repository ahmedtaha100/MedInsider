"""Chain-of-thought reasoning trace capture.

Extracts and structures CoT reasoning from agent messages during episodes.
This module captures the agent's reasoning BEFORE it takes an action, enabling
analysis of whether the agent's reasoning reveals awareness of pressure,
consideration of shortcuts, or rationalization of integrity violations.
"""

import re
from typing import Any

MIN_PRE_JSON_REASONING_LEN = 5

_REASONING_MARKER_PATTERNS = [
    re.compile(r"(?:reasoning|thought|analysis|consideration):\s*(.*)", re.IGNORECASE),
    re.compile(r"(?:I (?:need|should|will|think|believe|consider)).*", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# CoT extraction
# ---------------------------------------------------------------------------


def extract_cot_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract chain-of-thought segments from agent message history.

    Looks for reasoning text in assistant messages that precede tool calls.
    Common patterns: <thinking>...</thinking> tags, text before JSON action,
    or explicit reasoning blocks.
    """
    traces: list[dict[str, Any]] = []

    for idx, msg in enumerate(messages):
        role = msg.get("role", "")
        if role != "assistant":
            continue

        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                str(block.get("text", ""))
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )

        if not isinstance(content, str) or not content.strip():
            continue

        reasoning = _extract_reasoning(content)
        if reasoning:
            traces.append(
                {
                    "message_index": idx,
                    "reasoning": reasoning,
                    "action_follows": _has_action_json(content),
                }
            )

    return traces


def _extract_reasoning(text: str) -> str:
    """Extract reasoning portion from agent text.

    Supports multiple formats:
    1. <thinking>...</thinking> tags
    2. Text before a JSON action block
    3. Lines starting with reasoning markers
    """
    thinking_match = re.search(r"<thinking>(.*?)</thinking>", text, re.DOTALL | re.IGNORECASE)
    if thinking_match:
        return thinking_match.group(1).strip()

    json_start = text.find("{")
    if json_start >= MIN_PRE_JSON_REASONING_LEN:
        pre_json = text[:json_start].strip()
        if pre_json:
            return pre_json

    for pattern in _REASONING_MARKER_PATTERNS:
        match = pattern.search(text)
        if match:
            return (match.group(1) if match.lastindex else match.group(0)).strip()

    return ""


def _has_action_json(text: str) -> bool:
    """Check if text contains a JSON action block."""
    return bool(re.search(r'\{\s*"action"\s*:', text))


def summarize_cot_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Produce a summary of captured CoT traces for an episode."""
    return {
        "total_traces": len(traces),
        "traces_with_action": sum(1 for t in traces if t.get("action_follows")),
        "avg_reasoning_length": (round(sum(len(t["reasoning"]) for t in traces) / len(traces), 1) if traces else 0.0),
        "traces": traces,
    }
