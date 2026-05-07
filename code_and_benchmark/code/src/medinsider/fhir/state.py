import base64
import copy
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _fhir_id() -> str:
    return uuid.uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FHIRResource:
    resource_type: str
    resource_id: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        safe_data = {k: v for k, v in copy.deepcopy(self.data).items() if k not in ("resourceType", "id")}
        return {
            "resourceType": self.resource_type,
            "id": self.resource_id,
            **safe_data,
        }


@dataclass
class FHIRPatientEpisodeState:
    episode_id: str
    patient_id: str
    encounter_id: str = ""

    patient: FHIRResource | None = None
    encounter: FHIRResource | None = None
    conditions: list[FHIRResource] = field(default_factory=list)
    observations: list[FHIRResource] = field(default_factory=list)
    medication_requests: list[FHIRResource] = field(default_factory=list)
    service_requests: list[FHIRResource] = field(default_factory=list)
    document_references: list[FHIRResource] = field(default_factory=list)
    procedures: list[FHIRResource] = field(default_factory=list)
    claims: list[FHIRResource] = field(default_factory=list)
    quality_metrics: list[FHIRResource] = field(default_factory=list)
    allergy_intolerances: list[FHIRResource] = field(default_factory=list)

    notes: list[dict[str, Any]] = field(default_factory=list)
    orders: list[dict[str, Any]] = field(default_factory=list)
    billing_submissions: list[dict[str, Any]] = field(default_factory=list)
    staff_messages: list[dict[str, Any]] = field(default_factory=list)
    discharge_plan_text: str = ""
    adverse_events: list[dict[str, Any]] = field(default_factory=list)
    inbox_messages: list[dict[str, Any]] = field(default_factory=list)

    demographics: dict[str, Any] = field(default_factory=dict)
    vital_signs: dict[str, Any] = field(default_factory=dict)
    labs: dict[str, Any] = field(default_factory=dict)
    problems: dict[str, str] = field(default_factory=dict)
    quality_reports: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_payload(cls, episode_id: str, payload: dict[str, Any]) -> "FHIRPatientEpisodeState":
        patient_id = payload.get("patient_id", "unknown")
        encounter_id = f"enc-{_fhir_id()}"

        state = cls(
            episode_id=episode_id,
            patient_id=patient_id,
            encounter_id=encounter_id,
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
            inbox_messages=copy.deepcopy(payload.get("inbox_messages", [])),
        )

        state.patient = FHIRResource(
            resource_type="Patient",
            resource_id=patient_id,
            data={
                "name": [{"text": payload.get("demographics", {}).get("name", "Unknown")}],
                "birthDate": payload.get("demographics", {}).get("birth_date", ""),
                "gender": payload.get("demographics", {}).get("gender", "unknown"),
            },
        )

        state.encounter = FHIRResource(
            resource_type="Encounter",
            resource_id=encounter_id,
            data={
                "status": "in-progress",
                "class": {"code": "IMP", "display": "inpatient encounter"},
                "subject": {"reference": f"Patient/{patient_id}"},
                "period": {"start": _now_iso()},
            },
        )

        if not isinstance(state.problems, dict):
            state.problems = {}

        for code, status in state.problems.items():
            state.conditions.append(
                FHIRResource(
                    resource_type="Condition",
                    resource_id=f"cond-{_fhir_id()}",
                    data={
                        "code": {"coding": [{"code": code, "display": status}]},
                        "clinicalStatus": {"coding": [{"code": "active"}]},
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "encounter": {"reference": f"Encounter/{encounter_id}"},
                    },
                )
            )

        for key, value in state.vital_signs.items() if isinstance(state.vital_signs, dict) else []:
            state.observations.append(
                FHIRResource(
                    resource_type="Observation",
                    resource_id=f"obs-{_fhir_id()}",
                    data={
                        "status": "final",
                        "code": {"text": key},
                        "valueString": str(value),
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "encounter": {"reference": f"Encounter/{encounter_id}"},
                        "category": [{"coding": [{"code": "vital-signs"}]}],
                    },
                )
            )

        for key, value in state.labs.items() if isinstance(state.labs, dict) else []:
            state.observations.append(
                FHIRResource(
                    resource_type="Observation",
                    resource_id=f"obs-{_fhir_id()}",
                    data={
                        "status": "final",
                        "code": {"text": key},
                        "valueString": str(value),
                        "subject": {"reference": f"Patient/{patient_id}"},
                        "encounter": {"reference": f"Encounter/{encounter_id}"},
                        "category": [{"coding": [{"code": "laboratory"}]}],
                    },
                )
            )

        for allergy in payload.get("allergy_intolerances", []):
            if isinstance(allergy, dict):
                state.add_allergy_intolerance(
                    substance=allergy.get("substance", allergy.get("code", "unknown")),
                    clinical_status=allergy.get("clinical_status", "active"),
                    criticality=allergy.get("criticality", "low"),
                )

        return state

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
            "inbox_messages": copy.deepcopy(self.inbox_messages),
        }

    def to_fhir_bundle(self) -> dict[str, Any]:
        entries = []
        if self.patient:
            entries.append({"resource": self.patient.to_dict()})
        if self.encounter:
            entries.append({"resource": self.encounter.to_dict()})
        for r in self.conditions:
            entries.append({"resource": r.to_dict()})
        for r in self.observations:
            entries.append({"resource": r.to_dict()})
        for r in self.medication_requests:
            entries.append({"resource": r.to_dict()})
        for r in self.service_requests:
            entries.append({"resource": r.to_dict()})
        for r in self.document_references:
            entries.append({"resource": r.to_dict()})
        for r in self.procedures:
            entries.append({"resource": r.to_dict()})
        for r in self.claims:
            entries.append({"resource": r.to_dict()})
        for r in self.quality_metrics:
            entries.append({"resource": r.to_dict()})
        for r in self.allergy_intolerances:
            entries.append({"resource": r.to_dict()})
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": entries,
        }

    def add_condition(self, code: str, status: str) -> FHIRResource:
        resource = FHIRResource(
            resource_type="Condition",
            resource_id=f"cond-{_fhir_id()}",
            data={
                "code": {"coding": [{"code": code, "display": status}]},
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
            },
        )
        self.conditions.append(resource)
        self.problems[code] = status
        return resource

    def add_observation(self, category: str, code_text: str, value: str) -> FHIRResource:
        resource = FHIRResource(
            resource_type="Observation",
            resource_id=f"obs-{_fhir_id()}",
            data={
                "status": "final",
                "code": {"text": code_text},
                "valueString": value,
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "category": [{"coding": [{"code": category}]}],
                "effectiveDateTime": _now_iso(),
            },
        )
        self.observations.append(resource)
        return resource

    def add_document_reference(self, doc_type: str, content: str) -> FHIRResource:
        resource = FHIRResource(
            resource_type="DocumentReference",
            resource_id=f"doc-{_fhir_id()}",
            data={
                "status": "current",
                "type": {"text": doc_type},
                "content": [
                    {
                        "attachment": {
                            "contentType": "text/plain",
                            "data": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                        }
                    }
                ],
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "context": [{"encounter": [{"reference": f"Encounter/{self.encounter_id}"}]}],
                "date": _now_iso(),
            },
        )
        self.document_references.append(resource)
        return resource

    def add_claim(self, cpt_codes: list[str], icd_codes: list[str]) -> FHIRResource:
        items = []
        for i, cpt in enumerate(cpt_codes, start=1):
            items.append({"sequence": i, "productOrService": {"coding": [{"code": cpt}]}})
        diagnosis = []
        for i, icd in enumerate(icd_codes, start=1):
            diagnosis.append({"sequence": i, "diagnosisCodeableConcept": {"coding": [{"code": icd}]}})
        resource = FHIRResource(
            resource_type="Claim",
            resource_id=f"claim-{_fhir_id()}",
            data={
                "status": "active",
                "type": {"coding": [{"code": "professional"}]},
                "patient": {"reference": f"Patient/{self.patient_id}"},
                "item": items,
                "diagnosis": diagnosis,
                "created": _now_iso(),
            },
        )
        self.claims.append(resource)
        return resource

    def add_medication_request(self, medication_code: str, details: dict[str, Any]) -> FHIRResource:
        safe_details = {
            k: v for k, v in copy.deepcopy(details).items() if k not in ("subject", "encounter", "status", "intent")
        }
        resource = FHIRResource(
            resource_type="MedicationRequest",
            resource_id=f"medrq-{_fhir_id()}",
            data={
                **safe_details,
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {"coding": [{"code": medication_code}]},
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "authoredOn": _now_iso(),
            },
        )
        self.medication_requests.append(resource)
        return resource

    def add_service_request(self, service_code: str, details: dict[str, Any]) -> FHIRResource:
        safe_details = {
            k: v for k, v in copy.deepcopy(details).items() if k not in ("subject", "encounter", "status", "intent")
        }
        resource = FHIRResource(
            resource_type="ServiceRequest",
            resource_id=f"srvrq-{_fhir_id()}",
            data={
                **safe_details,
                "status": "active",
                "intent": "order",
                "code": {"coding": [{"code": service_code}]},
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "authoredOn": _now_iso(),
            },
        )
        self.service_requests.append(resource)
        return resource

    def add_procedure(self, procedure_code: str, status: str = "completed") -> FHIRResource:
        resource = FHIRResource(
            resource_type="Procedure",
            resource_id=f"proc-{_fhir_id()}",
            data={
                "status": status,
                "code": {"coding": [{"code": procedure_code}]},
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "performedDateTime": _now_iso(),
            },
        )
        self.procedures.append(resource)
        return resource

    def add_quality_metric(self, metric: str, value: str) -> FHIRResource:
        resource = FHIRResource(
            resource_type="Observation",
            resource_id=f"qm-{_fhir_id()}",
            data={
                "status": "final",
                "category": [
                    {"coding": [{"system": "http://medinsider.benchmark/quality-metric", "code": "quality-metric"}]}
                ],
                "code": {"text": metric},
                "valueString": value,
                "subject": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "date": _now_iso(),
            },
        )
        self.quality_metrics.append(resource)
        return resource

    def add_allergy_intolerance(
        self, substance: str, clinical_status: str = "active", criticality: str = "low"
    ) -> FHIRResource:
        resource = FHIRResource(
            resource_type="AllergyIntolerance",
            resource_id=f"allergy-{_fhir_id()}",
            data={
                "clinicalStatus": {"coding": [{"code": clinical_status}]},
                "criticality": criticality,
                "code": {"coding": [{"code": substance, "display": substance}]},
                "patient": {"reference": f"Patient/{self.patient_id}"},
                "encounter": {"reference": f"Encounter/{self.encounter_id}"},
                "recordedDate": _now_iso(),
            },
        )
        self.allergy_intolerances.append(resource)
        return resource
