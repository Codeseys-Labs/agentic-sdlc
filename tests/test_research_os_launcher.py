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

    def test_generated_roles_use_runtime_model_assignment_contract(self) -> None:
        files = installer.build_files("example")
        agents = {path: text for path, text in files.items() if path.startswith(".codex/agents/")}
        self.assertEqual(len(agents), 17)
        for path, text in agents.items():
            with self.subTest(agent=path):
                self.assertNotIn("model_reasoning_effort =", text)
                for field in (
                    "requested_model_id",
                    "requested_effort",
                    "requested_context_form",
                    "resolution_state",
                    "resolved_model_id",
                    "resolved_effort",
                    "resolved_context_form",
                ):
                    self.assertIn(field, text)
                self.assertIn("inherited or unresolved", text)

    def test_generated_research_director_preserves_seeds_read_only_contract(self) -> None:
        director = installer.build_files("example")[".codex/agents/research_director.toml"]
        self.assertIn("Research Director is Seeds-read-only", director)
        self.assertIn("Seeds(<target>, ready --format json)", director)
        self.assertIn("Do not create, claim, update, close, or disposition Seeds", director)
        self.assertIn("SeedProposal {", director)
        self.assertNotIn("Check sd ready", director)
        self.assertNotIn("Claim or create a seeds issue", director)

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
