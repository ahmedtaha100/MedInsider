import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RunPhase4V2ScriptTests(unittest.TestCase):
    def _providerless_env(self) -> dict[str, str]:
        env = os.environ.copy()
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
            env.pop(name, None)
        return env

    def test_script_smoke_run_produces_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts/run_phase4_v2.py"),
                "--mode",
                "smoke",
                "--agent-type",
                "scripted",
                "--output-root",
                str(Path(temp_dir) / "runs"),
                "--run-id",
                "script_smoke",
                "--overwrite",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60)

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = Path(temp_dir) / "runs" / "script_smoke"
            self.assertTrue((run_dir / "artifacts" / "episode_results.csv").exists())
            self.assertTrue((run_dir / "summaries" / "failure_summary.json").exists())

    def test_script_smoke_run_supports_hf_backup_dry_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = [
                sys.executable,
                str(REPO_ROOT / "scripts/run_phase4_v2.py"),
                "--mode",
                "smoke",
                "--agent-type",
                "scripted",
                "--output-root",
                str(Path(temp_dir) / "runs"),
                "--run-id",
                "script_smoke_hf_backup",
                "--overwrite",
                "--enable-hf-backup",
                "--hf-backup-dry-run",
                "--hf-backup-batch-size",
                "1",
                "--hf-backup-primary-repo",
                "anonymous/primary-hf-backup",
                "--hf-backup-secondary-repo",
                "anonymous/secondary-hf-backup",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=60)

            self.assertEqual(result.returncode, 0, result.stderr)
            run_dir = Path(temp_dir) / "runs" / "script_smoke_hf_backup"
            self.assertTrue((run_dir / "summaries" / "hf_backup_summary.json").exists())
            self.assertTrue((run_dir / "manifest" / "hf_backup_state.json").exists())

    def test_preflight_script_returns_nonzero_on_validation_failure(self):
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/preflight_phase4_v2.py"),
            "--mode",
            "smoke",
            "--agent-type",
            "openai",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=self._providerless_env(),
            timeout=60,
        )

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('"ok": false', result.stdout.lower())
        self.assertIn("missing_provider_env:openai", result.stdout)

    def test_runner_preflight_only_returns_nonzero_on_validation_failure(self):
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/run_phase4_v2.py"),
            "--mode",
            "smoke",
            "--agent-type",
            "openai",
            "--preflight-only",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=self._providerless_env(),
            timeout=60,
        )

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('"ok": false', result.stdout.lower())
        self.assertIn("missing_provider_env:openai", result.stdout)

    def test_hf_backup_enable_and_disable_flags_are_mutually_exclusive(self):
        cmd = [
            sys.executable,
            str(REPO_ROOT / "scripts/run_phase4_v2.py"),
            "--mode",
            "smoke",
            "--agent-type",
            "scripted",
            "--enable-hf-backup",
            "--disable-hf-backup",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            env=self._providerless_env(),
            timeout=60,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not allowed with argument", result.stderr)


if __name__ == "__main__":
    unittest.main()
