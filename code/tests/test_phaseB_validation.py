import csv
import json
import tempfile
import unittest
from pathlib import Path

from medinsider.fhir.paired_scenario import generate_v2_dataset
from medinsider.phaseB_validation import (
    build_episode_labeling_package,
    build_scenario_realism_sample,
    generate_distribution_realism_audit,
    run_inter_rater_agreement,
    run_metric_validation,
    run_scorer_error_audit,
)


class PhaseBValidationTests(unittest.TestCase):
    def _dataset_dir(self, base_dir: str) -> str:
        dataset_dir = Path(base_dir) / "phase2"
        generate_v2_dataset(str(dataset_dir), seed=7)
        return str(dataset_dir)

    def test_build_scenario_realism_sample_has_balanced_coverage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_csv = Path(temp_dir) / "scenario_realism_results.csv"
            summary = build_scenario_realism_sample(
                dataset_dir=self._dataset_dir(temp_dir),
                output_csv=str(output_csv),
                target_size=100,
                seed=5,
            )
            self.assertEqual(summary["selected_size"], 100)
            self.assertEqual(len(summary["family_counts"]), 5)
            self.assertEqual(len(summary["condition_counts"]), 8)
            self.assertGreater(summary["alignment_counts"].get("aligned", 0), 0)
            self.assertGreater(summary["alignment_counts"].get("conflict", 0), 0)
            self.assertTrue(output_csv.exists())

    def test_build_episode_labeling_package_writes_logs_and_predictions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_csv = Path(temp_dir) / "blinded_gold_label_set.csv"
            admin_output_csv = Path(temp_dir) / "blinded_gold_label_admin.csv"
            logs_dir = Path(temp_dir) / "episode_review_logs"
            summary = build_episode_labeling_package(
                dataset_dir=self._dataset_dir(temp_dir),
                output_csv=str(output_csv),
                admin_output_csv=str(admin_output_csv),
                logs_dir=str(logs_dir),
                target_size=20,
                double_label_size=8,
                seed=9,
            )
            self.assertEqual(summary["selected_size"], 20)
            self.assertEqual(summary["double_label_size"], 8)
            self.assertTrue(output_csv.exists())
            self.assertTrue(admin_output_csv.exists())
            self.assertEqual(len(list(logs_dir.glob("*.jsonl"))), 20)

            rows = list(csv.DictReader(output_csv.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(len(rows), 20)
            self.assertNotIn("predicted_ivr", rows[0])
            self.assertNotIn("scenario_family", rows[0])
            self.assertIn(rows[0]["secondary_reviewer_required"], {"yes", "no"})
            self.assertEqual(sum(1 for row in rows if row["secondary_reviewer_required"] == "yes"), 8)

            admin_rows = list(csv.DictReader(admin_output_csv.read_text(encoding="utf-8").splitlines()))
            self.assertEqual(len(admin_rows), 20)
            self.assertIn(admin_rows[0]["predicted_ivr"], {"0", "1"})
            self.assertIn(admin_rows[0]["predicted_aeor"], {"0", "1"})
            self.assertNotEqual(admin_rows[0]["scenario_family_hidden"], "")

            first_log = sorted(logs_dir.glob("*.jsonl"))[0]
            first_entry = json.loads(first_log.read_text(encoding="utf-8").splitlines()[0])
            self.assertIn("blind_id", first_entry)
            self.assertNotIn("episode_id", first_entry)

    def test_metric_validation_pending_and_labeled_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels_csv = Path(temp_dir) / "labels.csv"
            predictions_csv = Path(temp_dir) / "predictions.csv"
            fieldnames = [
                "blind_id",
                "final_ivr",
                "final_mgr",
                "final_upr",
                "final_aeor",
                "final_psd",
                "final_cdr",
                "final_ambiguity",
                "reviewer_1_ivr",
                "reviewer_2_ivr",
                "reviewer_1_mgr",
                "reviewer_2_mgr",
                "reviewer_1_upr",
                "reviewer_2_upr",
                "reviewer_1_aeor",
                "reviewer_2_aeor",
                "reviewer_1_psd",
                "reviewer_2_psd",
                "reviewer_1_cdr",
                "reviewer_2_cdr",
                "reviewer_1_atc",
                "reviewer_2_atc",
                "final_atc",
                "reviewer_1_ambiguity",
                "reviewer_2_ambiguity",
                "scenario_family",
                "condition",
                "alignment_label",
            ]
            with labels_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "final_ivr": "1",
                        "final_mgr": "0",
                        "final_upr": "0",
                        "final_aeor": "1",
                        "final_psd": "0",
                        "final_cdr": "1",
                        "final_atc": "1",
                        "final_ambiguity": "0",
                        "reviewer_1_ivr": "1",
                        "reviewer_2_ivr": "1",
                        "reviewer_1_mgr": "0",
                        "reviewer_2_mgr": "1",
                        "reviewer_1_upr": "0",
                        "reviewer_2_upr": "0",
                        "reviewer_1_aeor": "1",
                        "reviewer_2_aeor": "1",
                        "reviewer_1_psd": "0",
                        "reviewer_2_psd": "0",
                        "reviewer_1_cdr": "1",
                        "reviewer_2_cdr": "0",
                        "reviewer_1_atc": "1",
                        "reviewer_2_atc": "1",
                        "reviewer_1_ambiguity": "0",
                        "reviewer_2_ambiguity": "0",
                        "scenario_family": "coding_and_billing_pressure",
                        "condition": "incentive",
                        "alignment_label": "conflict",
                    }
                )

            prediction_fieldnames = [
                "blind_id",
                "predicted_ivr",
                "predicted_mgr",
                "predicted_upr",
                "predicted_aeor",
                "predicted_psd",
                "predicted_cdr",
                "predicted_atc",
                "predicted_ambiguity",
            ]
            with predictions_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=prediction_fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "predicted_ivr": "1",
                        "predicted_mgr": "1",
                        "predicted_upr": "0",
                        "predicted_aeor": "1",
                        "predicted_psd": "0",
                        "predicted_cdr": "0",
                        "predicted_atc": "1",
                        "predicted_ambiguity": "0",
                    }
                )

            metric_md = Path(temp_dir) / "metric_validation_results.md"
            metric_json = Path(temp_dir) / "metric_validation_results.json"
            agreement_md = Path(temp_dir) / "inter_rater_agreement.md"
            audit_md = Path(temp_dir) / "scorer_error_audit.md"

            metric_summary = run_metric_validation(
                labels_csv=str(labels_csv),
                output_markdown=str(metric_md),
                output_json=str(metric_json),
                predictions_csv=str(predictions_csv),
            )
            self.assertGreater(metric_summary["evaluated_rows"], 0)
            self.assertEqual(metric_summary["min_evaluated_rows"], 1)
            self.assertEqual(metric_summary["ambiguity_evaluated_rows"], 1)
            self.assertTrue(metric_md.exists())
            self.assertTrue(metric_json.exists())

            agreement_summary = run_inter_rater_agreement(
                labels_csv=str(labels_csv),
                output_markdown=str(agreement_md),
            )
            self.assertEqual(agreement_summary["metrics"]["IVR"]["n"], 1)
            self.assertIsNone(agreement_summary["metrics"]["IVR"]["kappa"])
            self.assertTrue(agreement_md.exists())

            audit_summary = run_scorer_error_audit(
                labels_csv=str(labels_csv),
                output_markdown=str(audit_md),
                top_k=10,
                predictions_csv=str(predictions_csv),
            )
            self.assertEqual(audit_summary["audited_rows"], 1)
            self.assertEqual(audit_summary["total_mismatch_rows"], 1)
            self.assertTrue(audit_md.exists())

            with self.assertRaises(FileNotFoundError):
                run_metric_validation(
                    labels_csv=str(labels_csv),
                    output_markdown=str(metric_md),
                    output_json=str(metric_json),
                    predictions_csv=str(Path(temp_dir) / "missing_predictions.csv"),
                )

            with self.assertRaises(ValueError):
                run_metric_validation(
                    labels_csv=str(labels_csv),
                    output_markdown=str(metric_md),
                    output_json=str(metric_json),
                    predictions_csv=None,
                )

            with self.assertRaises(ValueError):
                run_scorer_error_audit(
                    labels_csv=str(labels_csv),
                    output_markdown=str(audit_md),
                    top_k=10,
                    predictions_csv=None,
                )

    def test_metric_validation_rejects_duplicate_prediction_blind_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels_csv = Path(temp_dir) / "labels.csv"
            predictions_csv = Path(temp_dir) / "predictions.csv"
            metric_md = Path(temp_dir) / "metric_validation_results.md"
            metric_json = Path(temp_dir) / "metric_validation_results.json"

            with labels_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "final_ivr",
                        "final_mgr",
                        "final_upr",
                        "final_aeor",
                        "final_psd",
                        "final_cdr",
                        "final_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "final_ivr": "1",
                        "final_mgr": "0",
                        "final_upr": "0",
                        "final_aeor": "1",
                        "final_psd": "0",
                        "final_cdr": "1",
                        "final_ambiguity": "0",
                    }
                )

            with predictions_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "predicted_ivr",
                        "predicted_mgr",
                        "predicted_upr",
                        "predicted_aeor",
                        "predicted_psd",
                        "predicted_cdr",
                        "predicted_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "predicted_ivr": "1",
                        "predicted_mgr": "0",
                        "predicted_upr": "0",
                        "predicted_aeor": "1",
                        "predicted_psd": "0",
                        "predicted_cdr": "1",
                        "predicted_ambiguity": "0",
                    }
                )
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "predicted_ivr": "0",
                        "predicted_mgr": "1",
                        "predicted_upr": "1",
                        "predicted_aeor": "0",
                        "predicted_psd": "1",
                        "predicted_cdr": "0",
                        "predicted_ambiguity": "1",
                    }
                )

            with self.assertRaisesRegex(ValueError, "duplicate blind_id"):
                run_metric_validation(
                    labels_csv=str(labels_csv),
                    output_markdown=str(metric_md),
                    output_json=str(metric_json),
                    predictions_csv=str(predictions_csv),
                )

    def test_metric_validation_rejects_unmatched_blind_id(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels_csv = Path(temp_dir) / "labels.csv"
            predictions_csv = Path(temp_dir) / "predictions.csv"
            metric_md = Path(temp_dir) / "metric_validation_results.md"
            metric_json = Path(temp_dir) / "metric_validation_results.json"
            audit_md = Path(temp_dir) / "scorer_error_audit.md"

            with labels_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "final_ivr",
                        "final_mgr",
                        "final_upr",
                        "final_aeor",
                        "final_psd",
                        "final_cdr",
                        "final_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "final_ivr": "1",
                        "final_mgr": "0",
                        "final_upr": "0",
                        "final_aeor": "1",
                        "final_psd": "0",
                        "final_cdr": "1",
                        "final_ambiguity": "0",
                    }
                )

            with predictions_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "predicted_ivr",
                        "predicted_mgr",
                        "predicted_upr",
                        "predicted_aeor",
                        "predicted_psd",
                        "predicted_cdr",
                        "predicted_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-x",
                        "predicted_ivr": "1",
                        "predicted_mgr": "0",
                        "predicted_upr": "0",
                        "predicted_aeor": "1",
                        "predicted_psd": "0",
                        "predicted_cdr": "1",
                        "predicted_ambiguity": "0",
                    }
                )

            with self.assertRaisesRegex(ValueError, "missing blind_id values"):
                run_metric_validation(
                    labels_csv=str(labels_csv),
                    output_markdown=str(metric_md),
                    output_json=str(metric_json),
                    predictions_csv=str(predictions_csv),
                )

            with self.assertRaisesRegex(ValueError, "missing blind_id values"):
                run_scorer_error_audit(
                    labels_csv=str(labels_csv),
                    output_markdown=str(audit_md),
                    top_k=10,
                    predictions_csv=str(predictions_csv),
                )

    def test_metric_validation_empty_pairs_use_zero_scores(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels_csv = Path(temp_dir) / "labels.csv"
            predictions_csv = Path(temp_dir) / "predictions.csv"
            metric_md = Path(temp_dir) / "metric_validation_results.md"
            metric_json = Path(temp_dir) / "metric_validation_results.json"

            with labels_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "final_ivr",
                        "final_mgr",
                        "final_upr",
                        "final_aeor",
                        "final_psd",
                        "final_cdr",
                        "final_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "final_ivr": "",
                        "final_mgr": "",
                        "final_upr": "",
                        "final_aeor": "",
                        "final_psd": "",
                        "final_cdr": "",
                        "final_ambiguity": "",
                    }
                )

            with predictions_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "predicted_ivr",
                        "predicted_mgr",
                        "predicted_upr",
                        "predicted_aeor",
                        "predicted_psd",
                        "predicted_cdr",
                        "predicted_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "predicted_ivr": "",
                        "predicted_mgr": "",
                        "predicted_upr": "",
                        "predicted_aeor": "",
                        "predicted_psd": "",
                        "predicted_cdr": "",
                        "predicted_ambiguity": "",
                    }
                )

            summary = run_metric_validation(
                labels_csv=str(labels_csv),
                output_markdown=str(metric_md),
                output_json=str(metric_json),
                predictions_csv=str(predictions_csv),
            )
            self.assertEqual(summary["evaluated_rows"], 0)
            self.assertEqual(summary["metrics"]["IVR"]["precision"], 0.0)
            self.assertEqual(summary["metrics"]["IVR"]["recall"], 0.0)
            self.assertEqual(summary["metrics"]["IVR"]["f1"], 0.0)
            self.assertEqual(summary["metrics"]["IVR"]["accuracy"], 0.0)

    def test_metric_validation_uses_none_for_undefined_precision_and_recall(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            labels_csv = Path(temp_dir) / "labels.csv"
            predictions_csv = Path(temp_dir) / "predictions.csv"
            metric_md = Path(temp_dir) / "metric_validation_results.md"
            metric_json = Path(temp_dir) / "metric_validation_results.json"

            with labels_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "final_ivr",
                        "final_mgr",
                        "final_upr",
                        "final_aeor",
                        "final_psd",
                        "final_cdr",
                        "final_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "final_ivr": "0",
                        "final_mgr": "0",
                        "final_upr": "0",
                        "final_aeor": "0",
                        "final_psd": "0",
                        "final_cdr": "0",
                        "final_ambiguity": "0",
                    }
                )

            with predictions_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "blind_id",
                        "predicted_ivr",
                        "predicted_mgr",
                        "predicted_upr",
                        "predicted_aeor",
                        "predicted_psd",
                        "predicted_cdr",
                        "predicted_ambiguity",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "blind_id": "row-1",
                        "predicted_ivr": "0",
                        "predicted_mgr": "0",
                        "predicted_upr": "0",
                        "predicted_aeor": "0",
                        "predicted_psd": "0",
                        "predicted_cdr": "0",
                        "predicted_ambiguity": "0",
                    }
                )

            summary = run_metric_validation(
                labels_csv=str(labels_csv),
                output_markdown=str(metric_md),
                output_json=str(metric_json),
                predictions_csv=str(predictions_csv),
            )
            self.assertIsNone(summary["metrics"]["IVR"]["precision"])
            self.assertIsNone(summary["metrics"]["IVR"]["recall"])
            self.assertIsNone(summary["metrics"]["IVR"]["f1"])
            self.assertEqual(summary["metrics"]["IVR"]["accuracy"], 1.0)

    def test_generate_distribution_realism_audit_outputs_expected_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_md = Path(temp_dir) / "distribution_realism_audit.md"
            output_csv = Path(temp_dir) / "distribution_realism_counts.csv"
            summary = generate_distribution_realism_audit(
                dataset_dir=self._dataset_dir(temp_dir),
                output_markdown=str(output_md),
                output_csv=str(output_csv),
            )
            self.assertEqual(summary["scenario_count"], 840)
            self.assertTrue(output_md.exists())
            self.assertTrue(output_csv.exists())
            md_text = output_md.read_text(encoding="utf-8")
            self.assertIn("Distribution Realism Audit", md_text)
            csv_rows = list(csv.DictReader(output_csv.read_text(encoding="utf-8").splitlines()))
            self.assertTrue(any(row["group"] == "family" for row in csv_rows))
            self.assertTrue(any(row["group"] == "condition" for row in csv_rows))
            self.assertTrue(any(row["group"] == "alignment" for row in csv_rows))


if __name__ == "__main__":
    unittest.main()
