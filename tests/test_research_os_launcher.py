from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
SPEC = importlib.util.spec_from_file_location("research_os_installer", SCRIPT)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class ResearchOSLauncherTests(unittest.TestCase):
    def test_generated_makefile_uses_mise_uv_python(self) -> None:
        makefile = installer.core_files("example")["Makefile"]
        self.assertIn("PYTHON := mise x uv@0.11.17 -- uv run --python 3.12.11 python", makefile)
        self.assertNotIn("python3", makefile)

    def test_pinned_research_installer_task_runs_help(self) -> None:
        result = subprocess.run(
            ["mise", "-C", str(SCRIPT.parents[3]), "run", "research-os:install", "--", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--target", result.stdout)


if __name__ == "__main__":
    unittest.main()
