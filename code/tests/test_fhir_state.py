import unittest

from medinsider.fhir.state import FHIRPatientEpisodeState, FHIRResource


class FHIRStateTests(unittest.TestCase):
    def _base_payload(self) -> dict:
        return {
            "patient_id": "pat-001",
            "demographics": {"name": "Test Patient", "age": 65, "gender": "male"},
            "vital_signs": {"bp": "130/85", "hr": "78"},
            "labs": {"troponin": "normal", "creatinine": "1.2"},
            "problems": {"I10": "Hypertension", "E11": "Type 2 Diabetes"},
            "notes": [],
            "orders": [],
            "billing_submissions": [],
            "staff_messages": [],
            "discharge_plan_text": "",
            "quality_reports": [],
            "adverse_events": [],
            "inbox_messages": [],
        }

    def test_from_payload_creates_patient_and_encounter(self):
        state = FHIRPatientEpisodeState.from_payload("ep-001", self._base_payload())
        self.assertEqual(state.patient_id, "pat-001")
        self.assertEqual(state.episode_id, "ep-001")
        self.assertIsNotNone(state.patient)
        self.assertEqual(state.patient.resource_type, "Patient")
        self.assertIsNotNone(state.encounter)
        self.assertEqual(state.encounter.resource_type, "Encounter")

    def test_from_payload_creates_conditions_from_problems(self):
        state = FHIRPatientEpisodeState.from_payload("ep-002", self._base_payload())
        self.assertEqual(len(state.conditions), 2)
        codes = {c.data["code"]["coding"][0]["code"] for c in state.conditions}
        self.assertEqual(codes, {"I10", "E11"})

    def test_from_payload_creates_observations_from_vitals_and_labs(self):
        state = FHIRPatientEpisodeState.from_payload("ep-003", self._base_payload())
        vital_obs = [o for o in state.observations if o.data["category"][0]["coding"][0]["code"] == "vital-signs"]
        lab_obs = [o for o in state.observations if o.data["category"][0]["coding"][0]["code"] == "laboratory"]
        self.assertEqual(len(vital_obs), 2)
        self.assertEqual(len(lab_obs), 2)

    def test_chart_snapshot_returns_deep_copy(self):
        state = FHIRPatientEpisodeState.from_payload("ep-004", self._base_payload())
        snap = state.chart_snapshot()
        snap["problems"]["Z99"] = "Added after snapshot"
        self.assertNotIn("Z99", state.problems)

    def test_from_payload_does_not_alias_mutable_collections(self):
        payload = self._base_payload()
        state = FHIRPatientEpisodeState.from_payload("ep-005", payload)
        payload["problems"]["Z99"] = "Injected"
        self.assertNotIn("Z99", state.problems)

    def test_to_fhir_bundle_includes_all_resources(self):
        state = FHIRPatientEpisodeState.from_payload("ep-006", self._base_payload())
        bundle = state.to_fhir_bundle()
        self.assertEqual(bundle["resourceType"], "Bundle")
        types = {e["resource"]["resourceType"] for e in bundle["entry"]}
        self.assertIn("Patient", types)
        self.assertIn("Encounter", types)
        self.assertIn("Condition", types)
        self.assertIn("Observation", types)

    def test_add_condition_updates_problems_and_fhir(self):
        state = FHIRPatientEpisodeState.from_payload("ep-007", self._base_payload())
        initial_count = len(state.conditions)
        state.add_condition("J44.1", "COPD")
        self.assertEqual(len(state.conditions), initial_count + 1)
        self.assertEqual(state.problems["J44.1"], "COPD")

    def test_add_claim_creates_fhir_claim(self):
        state = FHIRPatientEpisodeState.from_payload("ep-008", self._base_payload())
        state.add_claim(["99213"], ["I10"])
        self.assertEqual(len(state.claims), 1)
        claim = state.claims[0]
        self.assertEqual(claim.resource_type, "Claim")
        self.assertEqual(claim.data["item"][0]["productOrService"]["coding"][0]["code"], "99213")

    def test_add_document_reference(self):
        state = FHIRPatientEpisodeState.from_payload("ep-009", self._base_payload())
        state.add_document_reference("progress-note", "Patient is stable.")
        self.assertEqual(len(state.document_references), 1)
        self.assertEqual(state.document_references[0].resource_type, "DocumentReference")

    def test_fhir_resource_to_dict(self):
        r = FHIRResource(resource_type="Patient", resource_id="p1", data={"name": [{"text": "John"}]})
        d = r.to_dict()
        self.assertEqual(d["resourceType"], "Patient")
        self.assertEqual(d["id"], "p1")
        self.assertEqual(d["name"][0]["text"], "John")

    def test_empty_payload_creates_valid_state(self):
        state = FHIRPatientEpisodeState.from_payload("ep-010", {})
        self.assertEqual(state.patient_id, "unknown")
        self.assertEqual(len(state.conditions), 0)
        self.assertIsNotNone(state.patient)

    def test_add_medication_request(self):
        state = FHIRPatientEpisodeState.from_payload("ep-011", self._base_payload())
        state.add_medication_request("metformin", {"dosage": "500mg"})
        self.assertEqual(len(state.medication_requests), 1)
        self.assertEqual(state.medication_requests[0].resource_type, "MedicationRequest")

    def test_add_quality_metric(self):
        state = FHIRPatientEpisodeState.from_payload("ep-012", self._base_payload())
        state.add_quality_metric("readmission_risk", "low")
        self.assertEqual(len(state.quality_metrics), 1)
        self.assertEqual(state.quality_metrics[0].resource_type, "Observation")
        self.assertEqual(state.quality_metrics[0].data["code"]["text"], "readmission_risk")
        self.assertEqual(state.quality_metrics[0].data["valueString"], "low")

    def test_to_dict_strips_override_keys(self):
        res = FHIRResource(
            resource_type="Patient",
            resource_id="pat-001",
            data={"resourceType": "Evil", "id": "hacked", "name": "legit"},
        )
        d = res.to_dict()
        self.assertEqual(d["resourceType"], "Patient")
        self.assertEqual(d["id"], "pat-001")
        self.assertEqual(d["name"], "legit")

    def test_from_payload_non_dict_problems(self):
        payload = self._base_payload()
        payload["problems"] = ["not", "a", "dict"]
        state = FHIRPatientEpisodeState.from_payload("ep-013", payload)
        self.assertEqual(state.problems, {})
        self.assertEqual(len(state.conditions), 0)

    def test_add_allergy_intolerance(self):
        state = FHIRPatientEpisodeState.from_payload("ep-014", self._base_payload())
        resource = state.add_allergy_intolerance("penicillin", "active", "high")
        self.assertEqual(len(state.allergy_intolerances), 1)
        self.assertEqual(resource.resource_type, "AllergyIntolerance")
        self.assertEqual(resource.data["code"]["coding"][0]["code"], "penicillin")
        self.assertEqual(resource.data["criticality"], "high")

    def test_from_payload_with_allergies(self):
        payload = self._base_payload()
        payload["allergy_intolerances"] = [
            {"substance": "penicillin", "criticality": "high"},
            {"substance": "sulfa", "clinical_status": "active"},
        ]
        state = FHIRPatientEpisodeState.from_payload("ep-015", payload)
        self.assertEqual(len(state.allergy_intolerances), 2)
        bundle = state.to_fhir_bundle()
        allergy_entries = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "AllergyIntolerance"]
        self.assertEqual(len(allergy_entries), 2)


if __name__ == "__main__":
    unittest.main()
