import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ActionLogger:
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.sequence = 0

    def reset(self) -> None:
        self.sequence = 0

    def log_tool_call(
        self,
        episode_id: str,
        tool_name: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        self.sequence += 1
        entry = {
            "sequence": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode_id": episode_id,
            "tool_name": tool_name,
            "params": params,
            "result": result,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return entry
