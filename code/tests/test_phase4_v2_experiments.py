import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from medinsider.agents import ScriptedAgent
from medinsider.fhir.paired_scenario import CONDITIONS_V2, generate_v2_dataset
from medinsider.phase4_v2_experiments import main, resolve_conditions, run_phase4_experiments


class Phase4V2ExperimentsTests(unittest.TestCase):
    def _dataset_dir(self, base_dir: str) -> Path:
        dataset_dir = Path(base_dir) / "phase2"
        generate_v2_dataset(str(dataset_dir), seed=7)
        return dataset_dir

    def _reference_actions_for(self, dataset_dir: Path, condition: str) -> list[dict]:
        generated_dir = dataset_dir / "generated"
        for path in sorted(generated_dir.glob("*.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            if scenario["condition"] == condition:
                return scenario["reference_actions"]
        raise AssertionError(f"No scenario found for condition {condition}")

    def test_smoke_run_with_mocked_client(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir = Path(temp_dir) / "results"
            mock_agent = ScriptedAgent(self._reference_actions_for(dataset_dir, "neutral"))

            with patch("medinsider.phase4_v2_experiments.create_agent", return_value=mock_agent):
                summary = run_phase4_experiments(
                    dataset_dir=str(dataset_dir),
                    output_dir=str(output_dir),
                    models=["gpt-5.4"],
                    conditions=["neutral"],
                    seed=11,
                    max_scenarios=1,
                )

            self.assertEqual(summary["episode_rows"], 1)
            self.assertTrue(Path(summary["episode_scores_csv"]).exists())
            self.assertTrue(Path(summary["aggregated_results_csv"]).exists())

    def test_all_v2_conditions_are_recognized(self):
        self.assertEqual(resolve_conditions(None), list(CONDITIONS_V2))

    def test_csv_headers_include_primary_metrics_and_atc(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir = Path(temp_dir) / "results"
            summary = run_phase4_experiments(
                dataset_dir=str(dataset_dir),
                output_dir=str(output_dir),
                models=["gpt-5.4"],
                conditions=["neutral"],
                seed=13,
                max_scenarios=1,
                dry_run=True,
            )

            with Path(summary["episode_scores_csv"]).open("r", encoding="utf-8") as handle:
                episode_header = next(csv.reader(handle))
            with Path(summary["aggregated_results_csv"]).open("r", encoding="utf-8") as handle:
                aggregate_header = next(csv.reader(handle))

            for field in ["IVR", "MGR", "UPR", "AEOR", "PSD", "CDR", "ATC"]:
                self.assertIn(field, episode_header)
                self.assertIn(field, aggregate_header)

    def test_seed_is_recorded_in_episode_and_aggregate_csvs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir = Path(temp_dir) / "results"
            summary = run_phase4_experiments(
                dataset_dir=str(dataset_dir),
                output_dir=str(output_dir),
                models=["gpt-5.4"],
                conditions=["neutral"],
                seed=17,
                max_scenarios=1,
                dry_run=True,
            )

            episode_rows = list(
                csv.DictReader(Path(summary["episode_scores_csv"]).read_text(encoding="utf-8").splitlines())
            )
            aggregate_rows = list(
                csv.DictReader(Path(summary["aggregated_results_csv"]).read_text(encoding="utf-8").splitlines())
            )
            coverage_rows = list(
                csv.DictReader((output_dir / "model_condition_coverage.csv").read_text(encoding="utf-8").splitlines())
            )

            self.assertEqual(episode_rows[0]["seed"], "17")
            self.assertEqual(aggregate_rows[0]["seed"], "17")
            self.assertEqual(coverage_rows[0]["seed"], "17")

    def test_same_seed_reproduces_subsampled_episode_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir_a = Path(temp_dir) / "results_a"
            output_dir_b = Path(temp_dir) / "results_b"

            summary_a = run_phase4_experiments(
                dataset_dir=str(dataset_dir),
                output_dir=str(output_dir_a),
                models=["gpt-5.4"],
                conditions=["neutral"],
                seed=11,
                max_scenarios=1,
                dry_run=True,
            )
            summary_b = run_phase4_experiments(
                dataset_dir=str(dataset_dir),
                output_dir=str(output_dir_b),
                models=["gpt-5.4"],
                conditions=["neutral"],
                seed=11,
                max_scenarios=1,
                dry_run=True,
            )

            episode_rows_a = list(
                csv.DictReader(Path(summary_a["episode_scores_csv"]).read_text(encoding="utf-8").splitlines())
            )
            episode_rows_b = list(
                csv.DictReader(Path(summary_b["episode_scores_csv"]).read_text(encoding="utf-8").splitlines())
            )

            self.assertEqual(len(episode_rows_a), 1)
            self.assertEqual(len(episode_rows_b), 1)
            self.assertEqual(episode_rows_a[0]["scenario_id"], episode_rows_b[0]["scenario_id"])
            self.assertEqual(episode_rows_a[0]["seed"], episode_rows_b[0]["seed"])

    def test_module_main_dry_run_succeeds(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir = Path(temp_dir) / "results"
            with redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "--dataset-dir",
                        str(dataset_dir),
                        "--output-dir",
                        str(output_dir),
                        "--models",
                        "gpt-5.4",
                        "--conditions",
                        "neutral",
                        "--max-scenarios",
                        "1",
                        "--dry-run",
                    ]
                )
            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "episode_scores.csv").exists())

    def test_module_main_can_run_judge_pipeline(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_dir = self._dataset_dir(temp_dir)
            output_dir = Path(temp_dir) / "results"
            stream = io.StringIO()
            with patch(
                "medinsider.phase4_v2_experiments.run_judge_pipeline",
                return_value={"judge_scores_csv": str(output_dir / "judge_scores.csv")},
            ) as judge_mock:
                with redirect_stdout(stream):
                    exit_code = main(
                        [
                            "--dataset-dir",
                            str(dataset_dir),
                            "--output-dir",
                            str(output_dir),
                            "--models",
                            "gpt-5.4",
                            "--conditions",
                            "neutral",
                            "--max-scenarios",
                            "1",
                            "--dry-run",
                            "--run-judge-pipeline",
                        ]
                    )

            self.assertEqual(exit_code, 0)
            payload = json.loads(stream.getvalue())
            self.assertIn("judge_pipeline", payload)
            judge_mock.assert_called_once_with(
                episode_csv=str(output_dir / "episode_scores.csv"),
                output_dir=str(output_dir),
                calibration_fraction=0.1,
                seed=42,
            )


if __name__ == "__main__":
    unittest.main()
