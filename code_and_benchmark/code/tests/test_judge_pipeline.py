import csv
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from medinsider.fhir.judge_pipeline import JudgePipeline, _categorical_kappa
from medinsider.phase4_v2_experiments import run_judge_pipeline


class MockJudgeAgent:
    def __init__(self, model: str):
        self.model = model

    def complete_json(self, system_prompt: str, prompt: str) -> dict[str, object]:
        match = re.search(r"Case\s+(\d+)", prompt)
        if not match:
            raise AssertionError("judge prompt did not include case marker")
        case_index = int(match.group(1))
        primary_scores = {
            0: 0,
            1: 1,
            2: 2,
            3: 0,
            4: 1,
            5: 2,
        }
        calibration_scores = {
            0: 0,
            1: 2,
            2: 2,
            3: 0,
            4: 2,
            5: 2,
        }
        if self.model == "claude-opus-4-7":
            score = primary_scores[case_index]
        elif self.model == "claude-sonnet-4-6":
            score = calibration_scores[case_index]
        else:
            score = primary_scores[case_index]
        return {"score": score, "reasoning": f"{self.model}-case-{case_index}"}


def _expected_kappa(pairs: list[tuple[int, int]], labels: tuple[int, ...] = (0, 1, 2)) -> float | None:
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(1 for left, right in pairs if left == right) / n
    left_counts = {label: 0 for label in labels}
    right_counts = {label: 0 for label in labels}
    for left, right in pairs:
        left_counts[left] += 1
        right_counts[right] += 1
    expected = sum((left_counts[label] / n) * (right_counts[label] / n) for label in labels)
    if expected >= 1.0:
        return None
    return (observed - expected) / (1 - expected)


class JudgePipelineTests(unittest.TestCase):
    def _write_log(self, path: Path, case_index: int) -> None:
        entry = {
            "tool_name": "write_note",
            "params": {
                "section": "progress",
                "text": f"Case {case_index} note: minimize nothing, document clearly.",
            },
            "result": {
                "ok": True,
                "tool": "write_note",
                "data": {
                    "section": "progress",
                    "text": f"Case {case_index} note: minimize nothing, document clearly.",
                },
            },
        }
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

    def test_run_judge_pipeline_writes_scores_and_summary_kappa(self):
        built_models: list[str] = []

        def fake_build_agent(*, type=None, model=None, **kwargs):
            self.assertIn(type, {"claude", "openai"})
            self.assertIsNotNone(model)
            built_models.append(model)
            return MockJudgeAgent(model)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            episode_csv = temp_root / "episode_scores.csv"
            output_dir = temp_root / "judge_outputs"
            rows = []
            for case_index in range(6):
                log_path = temp_root / f"case_{case_index}.jsonl"
                self._write_log(log_path, case_index)
                rows.append(
                    {
                        "scenario_id": f"scenario-{case_index}",
                        "episode_id": f"episode-{case_index}",
                        "model": "gpt-5.4",
                        "condition": "neutral",
                        "seed": "42",
                        "needs_judge": "True",
                        "deception_language_score": "0",
                        "log_path": str(log_path),
                    }
                )
            rows.append(
                {
                    "scenario_id": "scenario-skip",
                    "episode_id": "episode-skip",
                    "model": "gpt-5.4",
                    "condition": "neutral",
                    "seed": "42",
                    "needs_judge": "False",
                    "deception_language_score": "0",
                    "log_path": str(temp_root / "skip.jsonl"),
                }
            )

            with episode_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "scenario_id",
                        "episode_id",
                        "model",
                        "condition",
                        "seed",
                        "needs_judge",
                        "deception_language_score",
                        "log_path",
                    ],
                )
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)

            with patch("medinsider.fhir.judge_pipeline.build_agent", side_effect=fake_build_agent):
                summary = run_judge_pipeline(
                    str(episode_csv),
                    str(output_dir),
                    calibration_fraction=1.0,
                    seed=7,
                )

            judge_rows = list(
                csv.DictReader((output_dir / "judge_scores.csv").read_text(encoding="utf-8").splitlines())
            )
            self.assertEqual(len(judge_rows), 6)
            self.assertEqual(summary["flagged_episode_count"], 6)
            self.assertEqual(summary["primary_judge_count"], 6)
            self.assertEqual(summary["calibration_sample_count"], 6)
            self.assertTrue((output_dir / "judge_scores_summary.json").exists())

            for row in judge_rows:
                self.assertEqual(row["primary_judge_model"], "claude-opus-4-7")
                self.assertEqual(row["calibration_judge_model"], "claude-sonnet-4-6")
                self.assertEqual(row["calibration_sampled"], "True")
                self.assertNotEqual(row["primary_judge_score"], "")
                self.assertNotEqual(row["calibration_judge_score"], "")

            expected_pairs = [(0, 0), (1, 2), (2, 2), (0, 0), (1, 2), (2, 2)]
            expected_kappa = round(_expected_kappa(expected_pairs), 4)
            self.assertEqual(summary["calibration_kappa"], expected_kappa)

            summary_payload = json.loads((output_dir / "judge_scores_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary_payload["calibration_kappa"], expected_kappa)
            self.assertEqual(set(built_models), {"claude-opus-4-7", "claude-sonnet-4-6"})

    def test_calibration_sampling_is_keyed_by_model_condition_and_episode(self):
        pipeline = JudgePipeline(calibration_fraction=0.5, seed=7)
        selected = pipeline._calibration_episode_ids(
            [
                {"model": "gpt-5.4", "condition": "neutral", "episode_id": "shared"},
                {"model": "gpt-5.4", "condition": "neutral", "episode_id": "unique-gpt"},
                {"model": "claude-sonnet-4-6", "condition": "neutral", "episode_id": "shared"},
                {"model": "claude-sonnet-4-6", "condition": "neutral", "episode_id": "unique-claude"},
            ]
        )

        self.assertIn(("gpt-5.4", "neutral", "shared"), selected)
        self.assertNotIn(("gpt-5.4", "neutral", "unique-gpt"), selected)
        self.assertIn(("claude-sonnet-4-6", "neutral", "unique-claude"), selected)
        self.assertNotIn(("claude-sonnet-4-6", "neutral", "shared"), selected)

    def test_anthropic_models_use_deepseek_calibration_judge_via_openai_compatible(self):
        built_kwargs: list[dict[str, object]] = []

        def fake_build_agent(**kwargs):
            built_kwargs.append(dict(kwargs))
            return MockJudgeAgent(str(kwargs["model"]))

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            episode_csv = temp_root / "episode_scores.csv"
            output_dir = temp_root / "judge_outputs"
            log_path = temp_root / "case_0.jsonl"
            self._write_log(log_path, 0)

            with episode_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "scenario_id",
                        "episode_id",
                        "model",
                        "condition",
                        "seed",
                        "needs_judge",
                        "deception_language_score",
                        "log_path",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "scenario_id": "scenario-0",
                        "episode_id": "episode-0",
                        "model": "claude-opus-4-7",
                        "condition": "neutral",
                        "seed": "42",
                        "needs_judge": "True",
                        "deception_language_score": "0",
                        "log_path": str(log_path),
                    }
                )

            with patch.dict(
                "os.environ", {"OPENAI_API_KEY": "test-openai", "DEEPSEEK_API_KEY": "test-deepseek"}, clear=True
            ):
                with patch("medinsider.fhir.judge_pipeline.build_agent", side_effect=fake_build_agent):
                    summary = run_judge_pipeline(
                        str(episode_csv),
                        str(output_dir),
                        calibration_fraction=1.0,
                        seed=7,
                    )

            self.assertEqual(summary["primary_judge_count"], 1)
            self.assertEqual(summary["calibration_sample_count"], 1)

            judge_rows = list(
                csv.DictReader((output_dir / "judge_scores.csv").read_text(encoding="utf-8").splitlines())
            )
            self.assertEqual(len(judge_rows), 1)
            self.assertEqual(judge_rows[0]["primary_judge_model"], "gpt-5.4")
            self.assertEqual(judge_rows[0]["calibration_judge_model"], "deepseek-chat")

            self.assertEqual(
                built_kwargs,
                [
                    {
                        "type": "openai",
                        "model": "gpt-5.4-2026-03-05",
                    },
                    {
                        "type": "openai_compatible",
                        "model": "deepseek-chat",
                        "base_url": "https://api.deepseek.com/v1",
                        "max_tokens": 1024,
                        "api_key": "test-deepseek",
                    },
                ],
            )

    def test_kappa_rejects_unexpected_score_labels(self):
        with self.assertRaises(ValueError) as ctx:
            _categorical_kappa([(0, 3)])

        self.assertIn("invalid_judge_score_pair", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
