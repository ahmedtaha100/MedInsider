import json
from pathlib import Path

from medinsider.scoring import score_episode


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    scenario = json.loads((project_root / "scenarios/phase3/fixtures/demo_scenario.json").read_text(encoding="utf-8"))
    logs = [
        json.loads(line)
        for line in (project_root / "scenarios/phase3/fixtures/demo_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    score = score_episode(scenario, logs)
    output_path = project_root / "scenarios/phase3/fixtures/demo_score_output.json"
    output_path.write_text(json.dumps(score, indent=2), encoding="utf-8")
    print(json.dumps(score, indent=2))


if __name__ == "__main__":
    main()
