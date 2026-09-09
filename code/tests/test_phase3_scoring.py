import json
import tempfile
import unittest
from pathlib import Path

from medinsider.fhir.paired_scenario import generate_v2_dataset
from medinsider.scoring import score_batch


class Phase3ScoringTests(unittest.TestCase):
    def test_score_batch_resolves_manifest_paths_from_artifacts_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = Path(temp_dir) / "phase2"
            summary = generate_v2_dataset(str(dataset_dir), seed=1)
            manifest_csv = Path(summary["manifest_path"])
            rows = manifest_csv.read_text(encoding="utf-8").splitlines()
            header = rows[0].split(",")
            first = rows[1].split(",")
            first_row = dict(zip(header, first, strict=True))
            episode_id = first_row["episode_id"]

            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / f"{episode_id}.jsonl").write_text("", encoding="utf-8")

            output_csv = Path(temp_dir) / "scores.csv"
            output_json = Path(temp_dir) / "scores.json"
            batch = score_batch(
                manifest_csv=str(manifest_csv),
                logs_dir=str(logs_dir),
                output_csv=str(output_csv),
                output_json=str(output_json),
                allow_missing_logs=True,
            )

            self.assertEqual(batch["row_count"], 1)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_json.exists())
            self.assertFalse(batch["is_complete"])

    def test_score_batch_resolves_nested_subset_manifest_without_path_column(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = Path(temp_dir) / "phase2"
            generated_dir = dataset_dir / "generated"
            subset_dir = dataset_dir / "artifacts" / "subsets"
            logs_dir = Path(temp_dir) / "logs"
            generated_dir.mkdir(parents=True, exist_ok=True)
            subset_dir.mkdir(parents=True, exist_ok=True)
            logs_dir.mkdir(parents=True, exist_ok=True)

            scenario = {
                "episode_id": "ep-legacy-001",
                "scenario_family": "quality_metric_pressure",
                "condition": "neutral",
                "alignment_label": "aligned",
                "patient_state": {
                    "problems": {},
                    "labs": {},
                    "adverse_events": [],
                },
            }
            (generated_dir / "ep-legacy-001.json").write_text(json.dumps(scenario, indent=2), encoding="utf-8")
            manifest_csv = subset_dir / "pilot_subset.csv"
            manifest_csv.write_text("episode_id\nep-legacy-001\n", encoding="utf-8")
            (logs_dir / "ep-legacy-001.jsonl").write_text("", encoding="utf-8")

            output_csv = Path(temp_dir) / "scores.csv"
            output_json = Path(temp_dir) / "scores.json"
            batch = score_batch(
                manifest_csv=str(manifest_csv),
                logs_dir=str(logs_dir),
                output_csv=str(output_csv),
                output_json=str(output_json),
                allow_missing_logs=True,
            )

            self.assertEqual(batch["row_count"], 1)
            self.assertTrue(output_csv.exists())
            self.assertTrue(output_json.exists())

    def test_score_batch_reports_missing_logs_in_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = Path(temp_dir) / "phase2"
            summary = generate_v2_dataset(str(dataset_dir), seed=2)
            manifest_csv = Path(summary["manifest_path"])
            rows = manifest_csv.read_text(encoding="utf-8").splitlines()
            expected_row_count = len(rows) - 1
            header = rows[0].split(",")
            first = rows[1].split(",")
            second = rows[2].split(",")
            first_row = dict(zip(header, first, strict=True))
            second_row = dict(zip(header, second, strict=True))

            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / f"{first_row['episode_id']}.jsonl").write_text("", encoding="utf-8")

            output_csv = Path(temp_dir) / "scores.csv"
            output_json = Path(temp_dir) / "scores.json"
            batch = score_batch(
                manifest_csv=str(manifest_csv),
                logs_dir=str(logs_dir),
                output_csv=str(output_csv),
                output_json=str(output_json),
                allow_missing_logs=True,
            )

            self.assertEqual(batch["manifest_row_count"], expected_row_count)
            self.assertEqual(batch["row_count"], 1)
            self.assertEqual(batch["missing_logs_count"], expected_row_count - 1)
            self.assertIn(second_row["episode_id"], batch["missing_logs"])
            self.assertFalse(batch["is_complete"])

    def test_score_batch_raises_when_logs_are_missing_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = Path(temp_dir) / "phase2"
            summary = generate_v2_dataset(str(dataset_dir), seed=3)
            manifest_csv = Path(summary["manifest_path"])
            rows = manifest_csv.read_text(encoding="utf-8").splitlines()
            header = rows[0].split(",")
            first = rows[1].split(",")
            first_row = dict(zip(header, first, strict=True))

            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            (logs_dir / f"{first_row['episode_id']}.jsonl").write_text("", encoding="utf-8")

            output_csv = Path(temp_dir) / "scores.csv"
            output_json = Path(temp_dir) / "scores.json"
            with self.assertRaises(FileNotFoundError):
                score_batch(
                    manifest_csv=str(manifest_csv),
                    logs_dir=str(logs_dir),
                    output_csv=str(output_csv),
                    output_json=str(output_json),
                )

    def test_score_batch_raises_when_manifest_references_missing_scenario(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = Path(temp_dir) / "phase2"
            summary = generate_v2_dataset(str(dataset_dir), seed=4)
            manifest_csv = Path(summary["manifest_path"])
            lines = manifest_csv.read_text(encoding="utf-8").splitlines()
            header = lines[0].split(",")
            path_index = header.index("path")
            first = lines[1].split(",")
            first[path_index] = "generated/does_not_exist.json"
            lines[1] = ",".join(first)
            manifest_csv.write_text("\n".join(lines) + "\n", encoding="utf-8")

            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            output_csv = Path(temp_dir) / "scores.csv"
            output_json = Path(temp_dir) / "scores.json"
            with self.assertRaises(FileNotFoundError):
                score_batch(
                    manifest_csv=str(manifest_csv),
                    logs_dir=str(logs_dir),
                    output_csv=str(output_csv),
                    output_json=str(output_json),
                    allow_missing_logs=True,
                )


if __name__ == "__main__":
    unittest.main()
