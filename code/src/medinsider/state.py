import copy
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PatientEpisodeState:
    episode_id: str
    patient_id: str
    demographics: dict[str, Any] = field(default_factory=dict)
    vital_signs: dict[str, Any] = field(default_factory=dict)
    labs: dict[str, Any] = field(default_factory=dict)
    problems: dict[str, str] = field(default_factory=dict)
    notes: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    billing_submissions: list[dict[str, Any]] = field(default_factory=list)
    staff_messages: list[dict[str, Any]] = field(default_factory=list)
    discharge_plan_text: str = ""
    quality_reports: list[dict[str, Any]] = field(default_factory=list)
    adverse_events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, episode_id: str, payload: dict[str, Any]) -> "PatientEpisodeState":
        return cls(
            episode_id=episode_id,
            patient_id=payload.get("patient_id", "unknown"),
            demographics=copy.deepcopy(payload.get("demographics", {})),
            vital_signs=copy.deepcopy(payload.get("vital_signs", {})),
            labs=copy.deepcopy(payload.get("labs", {})),
            problems=copy.deepcopy(payload.get("problems", {})),
            notes=copy.deepcopy(payload.get("notes", [])),
            orders=copy.deepcopy(payload.get("orders", [])),
            billing_submissions=copy.deepcopy(payload.get("billing_submissions", [])),
            staff_messages=copy.deepcopy(payload.get("staff_messages", [])),
            discharge_plan_text=payload.get("discharge_plan_text", ""),
            quality_reports=copy.deepcopy(payload.get("quality_reports", [])),
            adverse_events=copy.deepcopy(payload.get("adverse_events", [])),
        )

    def chart_snapshot(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "patient_id": self.patient_id,
            "demographics": copy.deepcopy(self.demographics),
            "vital_signs": copy.deepcopy(self.vital_signs),
            "labs": copy.deepcopy(self.labs),
            "problems": copy.deepcopy(self.problems),
            "notes": copy.deepcopy(self.notes),
            "orders": copy.deepcopy(self.orders),
            "billing_submissions": copy.deepcopy(self.billing_submissions),
            "staff_messages": copy.deepcopy(self.staff_messages),
            "discharge_plan_text": self.discharge_plan_text,
            "quality_reports": copy.deepcopy(self.quality_reports),
            "adverse_events": copy.deepcopy(self.adverse_events),
        }
