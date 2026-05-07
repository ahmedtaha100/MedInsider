import argparse
import json
import sys
from pathlib import Path

from medinsider.logger import ActionLogger
from medinsider.runner import ScenarioRunner


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    if not (project_root / "pyproject.toml").exists():
        project_root = Path.cwd()
    default_log = project_root / "logs/action_log.jsonl"
    default_summary = project_root / "logs/summary.json"

    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--agent", default="scripted", choices=["scripted", "openai", "claude"])
    parser.add_argument("--log", default=str(default_log))
    parser.add_argument("--summary", default=str(default_summary))
    args = parser.parse_args()

    logger = ActionLogger(args.log)
    runner = ScenarioRunner(logger)
    try:
        summary = runner.run(args.scenario, agent_type=args.agent)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.summary).open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
