"""Non-LLM baseline agents for benchmark comparison.

Provides deterministic, rule-based agents that establish performance floors:

1. RuleBasedCompliantAgent: Always follows the safest clinical path. Never
   upcodes, always documents adverse events, never skips safety checks.
   Expected: high ATC, zero integrity violations, but may over-document.

2. DocumentOnlyAgent: Only reads the chart and writes notes. Never places
   orders, never submits billing, never reports quality metrics.
   Expected: no billing/order violations, but low ATC (incomplete care).

3. RetrievalGroundedAgent: Reads the chart, then takes actions only for
   items explicitly present in the patient state. No inference beyond
   what's directly stated.
   Expected: moderate ATC, zero fabrication, may miss implicit care needs.

These baselines are required for the paper's "is integrity just capability?"
decoupling argument.
"""

from typing import Any


class RuleBasedCompliantAgent:
    """Always-compliant baseline that follows every safety rule."""

    def generate_actions(self, scenario: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate a deterministic action sequence from scenario state."""
        state = scenario.get("patient_state", {})
        patient_id = state.get("patient_id", "unknown")
        problems = state.get("problems", {})
        adverse_events = state.get("adverse_events", [])
        notes = state.get("notes", [])

        actions: list[dict[str, Any]] = []

        # Always read the chart first
        actions.append({"action": "read_chart", "params": {"patient_id": patient_id}})

        # Read existing notes
        for note in notes:
            note_id = note.get("note_id", "")
            if note_id:
                actions.append({"action": "read_note", "params": {"note_id": note_id}})

        # Check inbox if available
        if state.get("inbox_messages"):
            actions.append({"action": "inbox_read", "params": {"message_type": "all"}})

        # Document all active problems honestly
        problem_text = ", ".join(f"{code}: {status}" for code, status in problems.items())
        actions.append(
            {
                "action": "write_note",
                "params": {
                    "section": "assessment",
                    "text": f"Active problems reviewed: {problem_text}. All findings documented as present in chart.",
                },
            }
        )

        # Document adverse events explicitly
        for event in adverse_events:
            detail = event.get("detail", "adverse event")
            actions.append(
                {
                    "action": "quality_report",
                    "params": {
                        "metric": f"adverse_event_{event.get('event_id', 'unknown')}_disclosure",
                        "value": "documented",
                    },
                }
            )
            actions.append(
                {
                    "action": "write_note",
                    "params": {
                        "section": "events",
                        "text": f"Adverse event documented: {detail}",
                    },
                }
            )

        # Place a safe order (lab follow-up)
        actions.append(
            {
                "action": "place_order",
                "params": {"order_type": "lab", "details": {"test": "follow-up panel"}},
            }
        )

        # Message staff
        actions.append(
            {
                "action": "message_staff",
                "params": {"role": "care_manager", "message": "Safety checks completed."},
            }
        )

        # Submit billing with only supported codes
        active_codes = [code for code, status in problems.items() if status == "active"]
        if active_codes:
            actions.append(
                {
                    "action": "submit_billing",
                    "params": {"cpt_codes": ["99222"], "icd_codes": active_codes},
                }
            )

        # Discharge plan with full disclosure
        actions.append(
            {
                "action": "discharge_plan",
                "params": {
                    "plan_text": "Discharge with follow-up. All active problems, "
                    "pending results, and adverse events disclosed.",
                },
            }
        )

        actions.append({"action": "finish", "params": {}})
        return actions


class DocumentOnlyAgent:
    """Read-and-document baseline that never takes clinical actions."""

    def generate_actions(self, scenario: dict[str, Any]) -> list[dict[str, Any]]:
        state = scenario.get("patient_state", {})
        patient_id = state.get("patient_id", "unknown")

        actions: list[dict[str, Any]] = []
        actions.append({"action": "read_chart", "params": {"patient_id": patient_id}})

        for note in state.get("notes", []):
            note_id = note.get("note_id", "")
            if note_id:
                actions.append({"action": "read_note", "params": {"note_id": note_id}})

        actions.append(
            {
                "action": "write_note",
                "params": {
                    "section": "progress",
                    "text": "Chart reviewed. Clinical status documented as observed.",
                },
            }
        )

        actions.append({"action": "finish", "params": {}})
        return actions


class RetrievalGroundedAgent:
    """Only acts on information explicitly present in patient state."""

    def generate_actions(self, scenario: dict[str, Any]) -> list[dict[str, Any]]:
        state = scenario.get("patient_state", {})
        patient_id = state.get("patient_id", "unknown")
        problems = state.get("problems", {})
        adverse_events = state.get("adverse_events", [])

        actions: list[dict[str, Any]] = []
        actions.append({"action": "read_chart", "params": {"patient_id": patient_id}})

        # Only document what's explicitly in the chart
        if problems:
            codes = [f"{c}: {s}" for c, s in problems.items()]
            actions.append(
                {
                    "action": "write_note",
                    "params": {
                        "section": "assessment",
                        "text": f"Chart-grounded assessment: {', '.join(codes)}",
                    },
                }
            )

        # Report adverse events that are explicitly listed
        for event in adverse_events:
            actions.append(
                {
                    "action": "quality_report",
                    "params": {
                        "metric": f"adverse_event_{event.get('event_id', 'unknown')}_disclosure",
                        "value": "documented",
                    },
                }
            )

        # Only bill for explicitly active problems
        active = [c for c, s in problems.items() if s == "active"]
        if active:
            actions.append(
                {
                    "action": "submit_billing",
                    "params": {"cpt_codes": ["99222"], "icd_codes": active},
                }
            )

        actions.append(
            {
                "action": "discharge_plan",
                "params": {"plan_text": "Discharge based on chart-documented findings only."},
            }
        )

        actions.append({"action": "finish", "params": {}})
        return actions
