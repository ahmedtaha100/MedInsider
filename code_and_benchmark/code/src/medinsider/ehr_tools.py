import copy
import uuid
from datetime import datetime, timezone
from typing import Any

from medinsider.state import PatientEpisodeState


class ToolEnvironment:
    def __init__(self, state: PatientEpisodeState):
        self.state = state

    def tool_names(self) -> list[str]:
        return [
            "read_chart",
            "read_note",
            "write_note",
            "place_order",
            "update_problem_list",
            "submit_billing",
            "message_staff",
            "discharge_plan",
            "quality_report",
        ]

    def dispatch(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            "read_chart": self.read_chart,
            "read_note": self.read_note,
            "write_note": self.write_note,
            "place_order": self.place_order,
            "update_problem_list": self.update_problem_list,
            "submit_billing": self.submit_billing,
            "message_staff": self.message_staff,
            "discharge_plan": self.discharge_plan,
            "quality_report": self.quality_report,
        }
        if tool_name not in mapping:
            return {
                "ok": False,
                "tool": tool_name,
                "error": f"unknown_tool:{tool_name}",
            }
        if not isinstance(params, dict):
            return {
                "ok": False,
                "tool": tool_name,
                "error": "bad_params:params_must_be_object",
            }
        try:
            return mapping[tool_name](**params)
        except TypeError as exc:
            return {
                "ok": False,
                "tool": tool_name,
                "error": f"bad_params:{exc}",
            }

    def read_chart(self, patient_id: str) -> dict[str, Any]:
        if patient_id != self.state.patient_id:
            return {
                "ok": False,
                "tool": "read_chart",
                "error": "patient_not_found",
            }
        return {
            "ok": True,
            "tool": "read_chart",
            "data": self.state.chart_snapshot(),
        }

    def read_note(self, note_id: str) -> dict[str, Any]:
        for note in self.state.notes:
            if note.get("note_id") == note_id:
                return {
                    "ok": True,
                    "tool": "read_note",
                    "data": copy.deepcopy(note),
                }
        return {
            "ok": False,
            "tool": "read_note",
            "error": "note_not_found",
        }

    def write_note(self, section: str, text: str) -> dict[str, Any]:
        note_id = f"note-{uuid.uuid4().hex[:12]}"
        item = {
            "note_id": note_id,
            "section": section,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state.notes.append(item)
        return {
            "ok": True,
            "tool": "write_note",
            "data": copy.deepcopy(item),
        }

    def place_order(self, order_type: str, details: dict[str, Any]) -> dict[str, Any]:
        item = {
            "order_id": f"order-{uuid.uuid4().hex[:12]}",
            "order_type": order_type,
            "details": copy.deepcopy(details),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state.orders.append(item)
        return {
            "ok": True,
            "tool": "place_order",
            "data": copy.deepcopy(item),
        }

    def update_problem_list(self, code: str, status: str) -> dict[str, Any]:
        self.state.problems[code] = status
        return {
            "ok": True,
            "tool": "update_problem_list",
            "data": {
                "code": code,
                "status": status,
                "problems": dict(self.state.problems),
            },
        }

    def submit_billing(self, cpt_codes: list[str], icd_codes: list[str]) -> dict[str, Any]:
        item = {
            "billing_id": f"bill-{uuid.uuid4().hex[:12]}",
            "cpt_codes": list(cpt_codes),
            "icd_codes": list(icd_codes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state.billing_submissions.append(item)
        return {
            "ok": True,
            "tool": "submit_billing",
            "data": copy.deepcopy(item),
        }

    def message_staff(self, role: str, message: str) -> dict[str, Any]:
        item = {
            "message_id": f"msg-{uuid.uuid4().hex[:12]}",
            "role": role,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state.staff_messages.append(item)
        return {
            "ok": True,
            "tool": "message_staff",
            "data": copy.deepcopy(item),
        }

    def discharge_plan(self, plan_text: str) -> dict[str, Any]:
        previous_plan_text = self.state.discharge_plan_text
        self.state.discharge_plan_text = plan_text
        return {
            "ok": True,
            "tool": "discharge_plan",
            "data": {
                "plan_text": plan_text,
                "previous_plan_text": previous_plan_text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def quality_report(self, metric: str, value: str) -> dict[str, Any]:
        item = {
            "report_id": f"quality-{uuid.uuid4().hex[:12]}",
            "metric": metric,
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.state.quality_reports.append(item)
        adverse_event = None
        if metric.strip().lower().startswith("adverse_event_"):
            adverse_event = {
                "event_id": f"ae-{uuid.uuid4().hex[:12]}",
                "label": metric,
                "detail": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self.state.adverse_events.append(adverse_event)
        return {
            "ok": True,
            "tool": "quality_report",
            "data": {
                "report": copy.deepcopy(item),
                "adverse_event": copy.deepcopy(adverse_event) if adverse_event else None,
            },
        }
