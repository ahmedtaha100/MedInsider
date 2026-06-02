import json
import sys
from pathlib import Path

from medinsider.logger import ActionLogger
from medinsider.runner import ScenarioRunner


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    scenario_path = project_root / "scenarios/phase1/billing_conflict_episode.json"
    log_path = project_root / "logs/phase1_action_log.jsonl"
    summary_path = project_root / "logs/phase1_summary.json"

    logger = ActionLogger(str(log_path))
    runner = ScenarioRunner(logger)
    try:
        summary = runner.run(scenario_path=str(scenario_path), agent_type="scripted")
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(json.dumps({"error": str(exc), "scenario_path": str(scenario_path)}, indent=2), file=sys.stderr)
        return 1

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
