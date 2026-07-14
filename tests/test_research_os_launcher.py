from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
STATIC_RESEARCH_DIRECTOR = (
    Path(__file__).parents[1] / "agents" / "codex" / "research" / "research_director.toml"
)
SEEDS_READ_ONLY_GUIDANCE = """Seeds authority:
- Research Director is Seeds-read-only.
- Inspect `Seeds(<target>, ready --format json)` through the exact launcher contract in the loaded `agentic-sdlc-orchestrator` skill before substantive orchestration when Seeds is available.
- Do not create, claim, update, close, or disposition Seeds.
- For work that outlives the session, emit a typed `SeedProposal { title: str, summary: str, acceptance_criteria: list[str], priority: str, blocking: bool, scope: list[str], evidence: list[str], dependencies: list[str], recommended_owner: str }` for conductor triage."""
SPEC = importlib.util.spec_from_file_location("research_os_installer", SCRIPT)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class ResearchOSLauncherTests(unittest.TestCase):
    def test_research_director_seeds_authority_is_static_template_parity(self) -> None:
        static = tomllib.loads(STATIC_RESEARCH_DIRECTOR.read_text(encoding="utf-8"))["developer_instructions"]
        generated = tomllib.loads(
            installer.build_files("example")[".codex/agents/research_director.toml"]
        )["developer_instructions"]

        self.assertTrue(generated.startswith(static))
        self.assertEqual(
            generated.removeprefix(static).strip(), installer.clean(installer.COMMON_AGENT_RULES).strip()
        )
        self.assertIn("Research Director is Seeds-read-only.", generated)
        self.assertIn("Seeds(<target>, ready --format json)", generated)
        self.assertNotIn("claim or create tracked work", generated.lower())
        self.assertIn(SEEDS_READ_ONLY_GUIDANCE.strip(), generated)

    def test_generated_research_director_literal_guidance_has_no_mutation_leak(self) -> None:
        generated = installer.build_files("example")[".codex/agents/research_director.toml"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            generated_path = root / "skills" / "codex-research-os" / "generated" / "research_director.toml"
            generated_path.parent.mkdir(parents=True)
            generated_path.write_text(generated, encoding="utf-8")

            scanner_path = Path(__file__).parents[1] / "tests" / "test_preflight_capabilities.py"
            scanner_spec = importlib.util.spec_from_file_location("seeds_scanner", scanner_path)
            assert scanner_spec and scanner_spec.loader
            scanner = importlib.util.module_from_spec(scanner_spec)
            scanner_spec.loader.exec_module(scanner)

            violations = scanner.shipped_surface_violations(root)

        self.assertEqual(violations, [], "\n".join(violations))

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
