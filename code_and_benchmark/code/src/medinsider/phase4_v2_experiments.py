"""Legacy experiment-oriented v2 helper.

This module predates the authoritative manifest-driven pilot runner in
medinsider.fhir.pilot_runtime / scripts.run_phase4_v2. It remains available for
backward compatibility and judge-pipeline experiments, but it is not the
default execution path for real pilot runs.
"""

import argparse
import csv
import json
import math
import os
import random
import statistics
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from medinsider.agents import ScriptedAgent
from medinsider.agents import build_agent as create_agent
from medinsider.fhir.judge_pipeline import JudgePipeline
from medinsider.fhir.logger import FHIRActionLogger
from medinsider.fhir.paired_scenario import CONDITIONS_V2
from medinsider.fhir.runner import FHIRScenarioRunner
from medinsider.fhir.scoring import load_jsonl
from medinsider.fhir.scoring import score_episode as score_fhir_episode

CONDITIONS = tuple(CONDITIONS_V2)
DEFAULT_OPENWEIGHT_BASE_URL = "http://localhost:8000/v1"
PRIMARY_METRICS = ["IVR", "MGR", "UPR", "AEOR", "PSD", "CDR", "ATC"]
COVERAGE_COLUMNS = ["model", "condition", "seed", "episode_count"]

MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "gpt-5.4": {
        "agent_type": "openai",
        "runtime_model": "gpt-5.4-2026-03-05",
    },
    "claude-sonnet-4-6": {
        "agent_type": "claude",
        "runtime_model": "claude-sonnet-4-6",
    },
    "claude-opus-4-7": {
        "agent_type": "claude",
        "runtime_model": "claude-opus-4-7",
    },
    "gemini-2.5-pro": {
        "agent_type": "gemini",
        "runtime_model": "gemini-2.5-pro",
    },
    "llama-4-scout": {
        "agent_type": "openweight",
        "runtime_model": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    },
    "qwen3.5-122b-a10b": {
        "agent_type": "openweight",
        "runtime_model": "Qwen/Qwen3.5-122B-A10B",
    },
    "gpt-oss-120b": {
        "agent_type": "openweight",
        "runtime_model": "openai/gpt-oss-120b",
    },
    "gemma-4-31b-it": {
        "agent_type": "openweight",
        "runtime_model": "google/gemma-4-31B-it",
    },
    "kimi-k2.5": {
        "agent_type": "openweight",
        "runtime_model": "moonshotai/Kimi-K2.5",
    },
    "glm-5": {
        "agent_type": "openweight",
        "runtime_model": "zai-org/GLM-5",
    },
}

EPISODE_COLUMNS = [
    "scenario_id",
    "episode_id",
    "pair_id",
    "twin_role",
    "pressure_condition",
    "scenario_family",
    "condition",
    "alignment_label",
    "model",
    "model_api_id",
    "agent_type",
    "baseline",
    "seed",
    "tool_calls",
    "termination_reason",
    "needs_judge",
    "IVR",
    "MGR",
    "UPR",
    "UPR_integrity",
    "UPR_compliance",
    "AEOR",
    "PSD",
    "CDR",
    "ATC",
    "deception_language_score",
    "tradeoff_mode",
    "log_path",
]

AGGREGATE_COLUMNS = [
    "model",
    "model_api_id",
    "agent_type",
    "baseline",
    "condition",
    "seed",
    "episode_count",
    "needs_judge_count",
    "needs_judge_rate",
]
for metric_name in PRIMARY_METRICS:
    AGGREGATE_COLUMNS.extend([metric_name, f"{metric_name}_ci_low", f"{metric_name}_ci_high"])


def _load_phase2_scenarios(dataset_dir: str) -> list[dict[str, Any]]:
    generated = Path(dataset_dir) / "generated"
    scenarios = []
    for path in sorted(generated.glob("*.json")):
        scenario = json.loads(path.read_text(encoding="utf-8"))
        scenario["_source_path"] = str(path)
        scenarios.append(scenario)
    return scenarios


def resolve_models(models: list[str] | None) -> list[str]:
    if models is None:
        return list(MODEL_PROFILES)
    unknown = [model for model in models if model not in MODEL_PROFILES]
    if unknown:
        raise ValueError(f"unknown_models:{','.join(sorted(unknown))}")
    return models


def resolve_conditions(conditions: list[str] | None) -> list[str]:
    if conditions is None:
        return list(CONDITIONS)
    unknown = [condition for condition in conditions if condition not in CONDITIONS]
    if unknown:
        raise ValueError(f"unknown_conditions:{','.join(sorted(unknown))}")
    return conditions


def _selected_scenarios(
    scenarios: list[dict[str, Any]],
    conditions: list[str],
    max_scenarios: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {condition: [] for condition in conditions}
    for scenario in sorted(scenarios, key=lambda row: row["episode_id"]):
        condition = str(scenario.get("condition", ""))
        if condition not in grouped:
            continue
        grouped[condition].append(scenario)

    selected: list[dict[str, Any]] = []
    for condition in conditions:
        condition_scenarios = list(grouped[condition])
        if max_scenarios is not None and len(condition_scenarios) > max_scenarios:
            rng = random.Random(f"{seed}:{condition}")
            rng.shuffle(condition_scenarios)
            condition_scenarios = sorted(
                condition_scenarios[:max_scenarios],
                key=lambda row: row["episode_id"],
            )
        selected.extend(condition_scenarios)
    if not selected:
        raise ValueError("no_scenarios_selected")
    return selected


def _sanitize_identifier(value: str) -> str:
    return value.replace("/", "__").replace("\\", "__")


def _dry_run_agent(scenario: dict[str, Any]) -> ScriptedAgent:
    return ScriptedAgent(deepcopy(scenario.get("reference_actions", [])))


def _build_runtime_agent(
    model_name: str,
    scenario: dict[str, Any],
    *,
    dry_run: bool,
    openweight_base_url: str,
):
    if dry_run:
        return _dry_run_agent(scenario)

    profile = MODEL_PROFILES[model_name]
    kwargs: dict[str, Any] = {"model": profile["runtime_model"]}
    if profile["agent_type"] == "openweight":
        kwargs["base_url"] = profile.get("base_url", openweight_base_url)
    if profile["agent_type"] == "claude":
        kwargs["max_tokens"] = profile.get("max_tokens", 1024)
    if profile["agent_type"] == "gemini":
        kwargs["max_output_tokens"] = profile.get("max_output_tokens", 1024)
    return create_agent(type=profile["agent_type"], **kwargs)


def _mean_confidence_interval(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    mean_value = statistics.fmean(values)
    if len(values) == 1:
        return round(mean_value, 4), round(mean_value, 4), round(mean_value, 4)
    sample_stdev = statistics.stdev(values)
    margin = 1.96 * (sample_stdev / math.sqrt(len(values)))
    return (
        round(mean_value, 4),
        round(max(0.0, mean_value - margin), 4),
        round(min(1.0, mean_value + margin), 4),
    )


def _episode_log_path(output_root: Path, model_name: str, episode_id: str, seed: int) -> Path:
    model_dir = output_root / "logs" / _sanitize_identifier(model_name)
    model_dir.mkdir(parents=True, exist_ok=True)
    return model_dir / f"{_sanitize_identifier(episode_id)}_seed{seed}.jsonl"


def _score_row(
    scenario: dict[str, Any],
    score: dict[str, Any],
    summary: dict[str, Any],
    model_name: str,
    seed: int,
    log_path: Path,
) -> dict[str, Any]:
    primary = score["primary"]
    metadata = scenario.get("metadata", {})
    needs_judge = bool(
        score["secondary"]["deception_language_score"].get("needs_judge")
        or score["secondary"]["refusal_vs_compliance_tradeoff"].get("needs_judge")
    )
    profile = MODEL_PROFILES[model_name]
    return {
        "scenario_id": scenario["episode_id"],
        "episode_id": scenario["episode_id"],
        "pair_id": metadata.get("pair_id", ""),
        "twin_role": metadata.get("twin_role", ""),
        "pressure_condition": metadata.get("pressure_condition", scenario.get("condition", "")),
        "scenario_family": scenario.get("scenario_family", ""),
        "condition": scenario.get("condition", ""),
        "alignment_label": scenario.get("alignment_label", ""),
        "model": model_name,
        "model_api_id": profile["runtime_model"],
        "agent_type": summary["agent_type"],
        "baseline": "model_panel",
        "seed": seed,
        "tool_calls": summary.get("tool_calls", 0),
        "termination_reason": summary.get("termination_reason", ""),
        "needs_judge": needs_judge,
        "IVR": primary["IVR"]["rate"],
        "MGR": primary["MGR"]["rate"],
        "UPR": primary["UPR"]["rate"],
        "UPR_integrity": primary["UPR"].get("integrity_rate", 0.0),
        "UPR_compliance": primary["UPR"].get("compliance_rate", 0.0),
        "AEOR": primary["AEOR"]["rate"],
        "PSD": primary["PSD"]["rate"],
        "CDR": primary["CDR"]["rate"],
        "ATC": score["atc"]["score"],
        "deception_language_score": score["secondary"]["deception_language_score"]["score"],
        "tradeoff_mode": score["secondary"]["refusal_vs_compliance_tradeoff"]["mode"],
        "log_path": str(log_path),
    }


def _aggregate_rows(episode_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in episode_rows:
        grouped[(row["model"], row["condition"])].append(row)

    rows: list[dict[str, Any]] = []
    for (model_name, condition), items in sorted(grouped.items()):
        first = items[0]
        aggregate = {
            "model": model_name,
            "model_api_id": first["model_api_id"],
            "agent_type": first["agent_type"],
            "baseline": "model_panel",
            "condition": condition,
            "seed": first["seed"],
            "episode_count": len(items),
            "needs_judge_count": sum(1 for item in items if str(item["needs_judge"]).lower() == "true"),
            "needs_judge_rate": round(
                sum(1 for item in items if str(item["needs_judge"]).lower() == "true") / len(items),
                4,
            ),
        }
        for metric_name in PRIMARY_METRICS:
            mean_value, ci_low, ci_high = _mean_confidence_interval([float(item[metric_name]) for item in items])
            aggregate[metric_name] = mean_value
            aggregate[f"{metric_name}_ci_low"] = ci_low
            aggregate[f"{metric_name}_ci_high"] = ci_high
        rows.append(aggregate)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def run_phase4_experiments(
    dataset_dir: str,
    output_dir: str,
    seed: int = 42,
    max_scenarios: int | None = None,
    *,
    models: list[str] | None = None,
    conditions: list[str] | None = None,
    dry_run: bool = False,
    openweight_base_url: str | None = None,
) -> dict[str, Any]:
    selected_models = resolve_models(models)
    selected_conditions = resolve_conditions(conditions)
    scenarios = _selected_scenarios(
        _load_phase2_scenarios(dataset_dir),
        selected_conditions,
        max_scenarios,
        seed,
    )

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    openweight_base_url = openweight_base_url or os.getenv("OPENWEIGHT_BASE_URL", DEFAULT_OPENWEIGHT_BASE_URL)

    episode_rows: list[dict[str, Any]] = []
    for model_name in selected_models:
        profile = MODEL_PROFILES[model_name]
        agent_type = "scripted" if dry_run else profile["agent_type"]
        for scenario in scenarios:
            scenario_for_run = deepcopy(scenario)
            log_path = _episode_log_path(output_root, model_name, scenario_for_run["episode_id"], seed)
            if log_path.exists():
                log_path.unlink()
            logger = FHIRActionLogger(str(log_path))
            runner = FHIRScenarioRunner(logger)
            agent = _build_runtime_agent(
                model_name,
                scenario_for_run,
                dry_run=dry_run,
                openweight_base_url=openweight_base_url,
            )
            summary = runner.run_loaded_scenario(
                scenario_for_run,
                agent_type=agent_type,
                agent=agent,
            )
            summary["agent_type"] = agent_type
            score = score_fhir_episode(scenario_for_run, load_jsonl(str(log_path)))
            episode_rows.append(_score_row(scenario_for_run, score, summary, model_name, seed, log_path))

    aggregate_rows = _aggregate_rows(episode_rows)

    episode_csv = output_root / "episode_scores.csv"
    aggregate_csv = output_root / "aggregated_results.csv"
    coverage_csv = output_root / "model_condition_coverage.csv"
    _write_csv(episode_csv, episode_rows, EPISODE_COLUMNS)
    _write_csv(aggregate_csv, aggregate_rows, AGGREGATE_COLUMNS)

    coverage_rows = []
    counts_by_pair: dict[tuple[str, str], int] = defaultdict(int)
    for row in episode_rows:
        counts_by_pair[(row["model"], row["condition"])] += 1
    for model_name in selected_models:
        for condition in selected_conditions:
            coverage_rows.append(
                {
                    "model": model_name,
                    "condition": condition,
                    "seed": seed,
                    "episode_count": counts_by_pair[(model_name, condition)],
                }
            )
    _write_csv(coverage_csv, coverage_rows, COVERAGE_COLUMNS)

    summary = {
        "seed": seed,
        "dry_run": dry_run,
        "dataset_dir": str(Path(dataset_dir)),
        "output_dir": str(output_root),
        "selected_models": selected_models,
        "selected_conditions": selected_conditions,
        "scenario_count": len(scenarios),
        "model_count": len(selected_models),
        "episode_rows": len(episode_rows),
        "aggregate_rows": len(aggregate_rows),
        "episode_scores_csv": str(episode_csv),
        "aggregated_results_csv": str(aggregate_csv),
        "coverage_csv": str(coverage_csv),
    }
    summary_path = output_root / "phase4_experiment_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


run_experiments = run_phase4_experiments


def run_judge_pipeline(
    episode_csv: str,
    output_dir: str,
    *,
    calibration_fraction: float = 0.1,
    seed: int = 42,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    pipeline = JudgePipeline(calibration_fraction=calibration_fraction, seed=seed)
    return pipeline.run(
        episode_csv,
        str(output_root / "judge_scores.csv"),
        str(output_root / "judge_scores_summary.json"),
    )


def _parse_csv_arg(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MedInsider phase-4 v2 experiments.")
    parser.add_argument("--dataset-dir", default="scenarios/phase2")
    parser.add_argument("--output-dir", default="experiments/phase4/results")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--models", default=None, help="Comma-separated model keys from MODEL_PROFILES.")
    parser.add_argument("--conditions", default=None, help="Comma-separated v2 condition names.")
    parser.add_argument("--max-scenarios", type=int, default=None)
    parser.add_argument("--openweight-base-url", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-judge-pipeline", action="store_true")
    parser.add_argument("--judge-output-dir", default=None)
    parser.add_argument("--calibration-fraction", type=float, default=0.1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = run_phase4_experiments(
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        seed=args.seed,
        models=_parse_csv_arg(args.models),
        conditions=_parse_csv_arg(args.conditions),
        max_scenarios=args.max_scenarios,
        dry_run=args.dry_run,
        openweight_base_url=args.openweight_base_url,
    )
    if args.run_judge_pipeline:
        summary["judge_pipeline"] = run_judge_pipeline(
            episode_csv=summary["episode_scores_csv"],
            output_dir=args.judge_output_dir or args.output_dir,
            calibration_fraction=args.calibration_fraction,
            seed=args.seed,
        )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
