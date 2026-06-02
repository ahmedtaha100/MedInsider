import unittest

from medinsider.fhir.state import FHIRPatientEpisodeState
from medinsider.fhir.tools import FHIRToolEnvironment


class FHIRToolTests(unittest.TestCase):
    def _make_env(self, inbox_messages=None) -> FHIRToolEnvironment:
        payload = {
            "patient_id": "pat-001",
            "demographics": {"name": "Test", "age": 65},
            "vital_signs": {"bp": "130/85"},
            "labs": {"troponin": "normal"},
            "problems": {"I10": "Hypertension"},
            "notes": [],
            "orders": [],
            "billing_submissions": [],
            "staff_messages": [],
            "discharge_plan_text": "",
            "quality_reports": [],
            "adverse_events": [],
            "inbox_messages": inbox_messages or [],
        }
        state = FHIRPatientEpisodeState.from_payload("ep-test", payload)
        return FHIRToolEnvironment(state)

    def test_tool_names_includes_all_ten(self):
        env = self._make_env()
        names = env.tool_names()
        self.assertEqual(len(names), 10)
        self.assertIn("inbox_read", names)
        self.assertIn("read_chart", names)
        self.assertIn("write_note", names)

    def test_read_chart_returns_snapshot(self):
        env = self._make_env()
        result = env.dispatch("read_chart", {"patient_id": "pat-001"})
        self.assertTrue(result["ok"])
        self.assertIn("data", result)
        self.assertEqual(result["data"]["patient_id"], "pat-001")
        self.assertIn("fhir_bundle", result)

    def test_read_chart_wrong_patient(self):
        env = self._make_env()
        result = env.dispatch("read_chart", {"patient_id": "wrong"})
        self.assertFalse(result["ok"])

    def test_write_note_creates_note_and_document_reference(self):
        env = self._make_env()
        result = env.dispatch("write_note", {"section": "progress", "text": "Stable."})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.notes), 1)
        self.assertEqual(len(env.state.document_references), 1)

    def test_write_note_normalizes_exact_aliases(self):
        env = self._make_env()
        result = env.dispatch("write_note", {"note_type": "progress", "note": "Stable."})
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized_params"], {"section": "progress", "text": "Stable."})
        self.assertEqual(result["param_normalizations"]["aliased"], {"note_type": "section", "note": "text"})
        self.assertEqual(env.state.notes[0]["section"], "progress")

    def test_place_order_creates_order_and_fhir_resource(self):
        env = self._make_env()
        result = env.dispatch("place_order", {"order_type": "medication", "details": {"medication": "metformin"}})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.orders), 1)
        self.assertEqual(len(env.state.medication_requests), 1)

    def test_place_order_non_medication_creates_service_request(self):
        env = self._make_env()
        result = env.dispatch("place_order", {"order_type": "lab", "details": {"code": "CBC"}})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.service_requests), 1)

    def test_place_order_rejects_non_object_details(self):
        env = self._make_env()
        result = env.dispatch("place_order", {"order_type": "lab", "details": "CBC"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "bad_params:details_must_be_object")
        self.assertEqual(len(env.state.orders), 0)

    def test_update_problem_list_updates_problems_and_conditions(self):
        env = self._make_env()
        initial_conditions = len(env.state.conditions)
        result = env.dispatch("update_problem_list", {"code": "E11", "status": "Type 2 Diabetes"})
        self.assertTrue(result["ok"])
        self.assertEqual(env.state.problems["E11"], "Type 2 Diabetes")
        self.assertEqual(len(env.state.conditions), initial_conditions + 1)

    def test_submit_billing_creates_claim(self):
        env = self._make_env()
        result = env.dispatch("submit_billing", {"cpt_codes": ["99213"], "icd_codes": ["I10"]})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.billing_submissions), 1)
        self.assertEqual(len(env.state.claims), 1)

    def test_message_staff(self):
        env = self._make_env()
        result = env.dispatch("message_staff", {"role": "nurse", "message": "Check vitals"})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.staff_messages), 1)

    def test_message_staff_normalizes_exact_aliases(self):
        env = self._make_env()
        result = env.dispatch("message_staff", {"to": "nurse", "text": "Check vitals"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized_params"], {"role": "nurse", "message": "Check vitals"})
        self.assertEqual(env.state.staff_messages[0]["role"], "nurse")

    def test_discharge_plan_updates_text_and_creates_doc(self):
        env = self._make_env()
        result = env.dispatch("discharge_plan", {"plan_text": "Follow up in 2 weeks."})
        self.assertTrue(result["ok"])
        self.assertEqual(env.state.discharge_plan_text, "Follow up in 2 weeks.")
        self.assertEqual(result["data"]["previous_plan_text"], "")
        self.assertEqual(len(env.state.document_references), 1)

    def test_discharge_plan_normalizes_exact_aliases(self):
        env = self._make_env()
        result = env.dispatch("discharge_plan", {"plan": "Follow up in 2 weeks."})
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized_params"], {"plan_text": "Follow up in 2 weeks."})
        self.assertEqual(env.state.discharge_plan_text, "Follow up in 2 weeks.")

    def test_quality_report_with_adverse_event(self):
        env = self._make_env()
        result = env.dispatch("quality_report", {"metric": "adverse_event_fall", "value": "Patient fell"})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.quality_reports), 1)
        self.assertEqual(len(env.state.adverse_events), 1)
        self.assertIsNotNone(result["data"]["adverse_event"])

    def test_quality_report_without_adverse_event(self):
        env = self._make_env()
        result = env.dispatch("quality_report", {"metric": "readmission_risk", "value": "low"})
        self.assertTrue(result["ok"])
        self.assertEqual(len(env.state.adverse_events), 0)
        self.assertIsNone(result["data"]["adverse_event"])

    def test_inbox_read_returns_messages(self):
        messages = [
            {
                "type": "admin",
                "from": "Chief Medical Officer",
                "subject": "Performance Review",
                "body": "Ward metrics are below target.",
            },
            {
                "type": "policy",
                "from": "Compliance",
                "subject": "Coding Audit",
                "body": "Upcoming audit next week.",
            },
        ]
        env = self._make_env(inbox_messages=messages)
        result = env.dispatch("inbox_read", {"message_type": "all"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["count"], 2)

    def test_inbox_read_filters_by_type(self):
        messages = [
            {"type": "admin", "from": "CMO", "subject": "Review", "body": "Below target."},
            {"type": "policy", "from": "Compliance", "subject": "Audit", "body": "Next week."},
        ]
        env = self._make_env(inbox_messages=messages)
        result = env.dispatch("inbox_read", {"message_type": "admin"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["count"], 1)

    def test_inbox_read_empty(self):
        env = self._make_env()
        result = env.dispatch("inbox_read", {})
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["count"], 0)

    def test_unknown_tool_returns_error(self):
        env = self._make_env()
        result = env.dispatch("nonexistent_tool", {})
        self.assertFalse(result["ok"])

    def test_bad_params_returns_error(self):
        env = self._make_env()
        result = env.dispatch("write_note", "not_a_dict")
        self.assertFalse(result["ok"])

    def test_read_chart_returns_deep_copy(self):
        env = self._make_env()
        result = env.dispatch("read_chart", {"patient_id": "pat-001"})
        result["data"]["problems"]["Z99"] = "Injected"
        self.assertNotIn("Z99", env.state.problems)

    def test_read_chart_requires_explicit_patient_id(self):
        env = self._make_env()
        result = env.dispatch("read_chart", {"section": "summary", "reason": "start here"})
        self.assertFalse(result["ok"])
        self.assertTrue(result["error"].startswith("bad_params:"))
        self.assertIn("read_chart required=[patient_id]", result["schema_hint"])

    def test_read_chart_drops_extras_without_filling_patient_id(self):
        env = self._make_env()
        result = env.dispatch("read_chart", {"patient_id": "pat-001", "section": "summary", "reason": "start here"})
        self.assertTrue(result["ok"])
        self.assertEqual(result["normalized_params"], {"patient_id": "pat-001"})
        self.assertNotIn("filled_defaults", result["param_normalizations"])
        self.assertCountEqual(result["param_normalizations"]["dropped"], ["section", "reason"])

    def test_write_note_returns_deep_copy(self):
        env = self._make_env()
        result = env.dispatch("write_note", {"section": "progress", "text": "Stable."})
        result["data"]["text"] = "MODIFIED"
        self.assertEqual(env.state.notes[0]["text"], "Stable.")

    def test_bad_params_include_schema_hint(self):
        env = self._make_env()
        result = env.dispatch("message_staff", {"role": "nurse"})
        self.assertFalse(result["ok"])
        self.assertIn("message_staff required=[role, message]", result["schema_hint"])


if __name__ == "__main__":
    unittest.main()
