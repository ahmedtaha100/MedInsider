import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "audit_atc_reference_actions.py"
SPEC = importlib.util.spec_from_file_location("audit_atc_reference_actions", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AuditAtcReferenceActionsTests(unittest.TestCase):
    def test_audit_resolves_manifest_relative_paths_with_repo_root_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            manifest_dir = temp_root / "artifacts"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            scenarios_dir = temp_root / "scenarios"
            scenarios_dir.mkdir(parents=True, exist_ok=True)
            scenario_path = scenarios_dir / "episode-1.json"
            scenario_path.write_text(
                json.dumps(
                    {
                        "reference_actions": [
                            {"action": "read_chart", "params": {"patient_id": "p1"}},
                            {"action": "finish", "params": {}},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            manifest_path = manifest_dir / "v2_manifest.csv"
            with manifest_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["episode_id", "scenario_family", "path"])
                writer.writeheader()
                writer.writerow(
                    {
                        "episode_id": "episode-1",
                        "scenario_family": "throughput_pressure",
                        "path": "scenarios/episode-1.json",
                    }
                )

            original_repo_root = MODULE.REPO_ROOT
            try:
                MODULE.REPO_ROOT = temp_root
                report = MODULE.audit_reference_actions(manifest_path)
            finally:
                MODULE.REPO_ROOT = original_repo_root

            self.assertEqual(report["episode_count"], 1)
            self.assertEqual(report["action_summary"]["read_chart"]["unique_param_shapes"], 1)


if __name__ == "__main__":
    unittest.main()
