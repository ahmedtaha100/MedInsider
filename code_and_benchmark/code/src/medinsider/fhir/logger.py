import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FHIRActionLogger:
    def __init__(self, log_path: str):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence: dict[str, int] = {}

    def reset(self, episode_id: str) -> None:
        self._sequence[episode_id] = 0

    def log(
        self,
        episode_id: str,
        tool_name: str,
        params: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        seq = self._sequence.get(episode_id, 0)
        entry = {
            "sequence": seq,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode_id": episode_id,
            "tool_name": tool_name,
            "params": params,
            "result": result,
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        self._sequence[episode_id] = seq + 1
