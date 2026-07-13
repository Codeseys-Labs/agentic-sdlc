from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check-agentic-sdlc-prereqs.sh"
BASH = shutil.which("bash")


class PreflightCapabilityTests(unittest.TestCase):
    def run_preflight(self, *, github_required: bool) -> subprocess.CompletedProcess[str]:
        if not BASH:
            self.skipTest("Bash is required for prerequisite shell tests")
        with tempfile.TemporaryDirectory() as temp:
            bin_dir = Path(temp) / "bin"
            bin_dir.mkdir()
            for name in ("git", "sd"):
                executable = bin_dir / name
                executable.write_text("#!/bin/sh\nexit 0\n")
                executable.chmod(0o755)
            env = os.environ | {
                "PATH": str(bin_dir),
                "AGENTIC_SDLC_HOST_READY": "1",
                "AGENTIC_SDLC_GITHUB_REQUIRED": "1" if github_required else "0",
                "HOME": temp,
            }
            return subprocess.run(
                [BASH, str(SCRIPT)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

    def test_local_git_run_does_not_require_gh(self) -> None:
        result = self.run_preflight(github_required=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gh not found (GitHub publication adapter skipped", result.stdout)

    def test_selected_github_operation_requires_gh(self) -> None:
        result = self.run_preflight(github_required=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("MISSING:  gh (required)", result.stderr)


if __name__ == "__main__":
    unittest.main()
