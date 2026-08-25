from __future__ import annotations

import importlib.util
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
ROOT = SCRIPT.parents[3]
STATIC_AGENTS = ROOT / "agents" / "codex" / "research"
SPEC = importlib.util.spec_from_file_location("research_os_installer", SCRIPT)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)

RUNTIME_FIELDS = (
    "schema_version",
    "requested_model_id",
    "requested_effort",
    "requested_context_form",
    "request_injection_status",
    "request_injection_evidence",
    "resolution_state",
    "resolved_provider",
    "resolved_model_id",
    "model_identity_basis",
    "model_readback_status",
    "model_readback_evidence",
    "effort_readback_status",
    "effort_readback_evidence",
    "effort_effective_divergence",
    "context_readback_status",
    "context_readback_evidence",
    "context_effective_divergence",
)


class ResearchOSLauncherTests(unittest.TestCase):
    maxDiff = None

    def generated_agents(self) -> dict[str, str]:
        return {
            path: text
            for path, text in installer.build_files("example").items()
            if path.startswith(".codex/agents/")
        }

    def assert_dispatch_contract(self, text: str) -> None:
        instructions = tomllib.loads(text)["developer_instructions"]
        for field in RUNTIME_FIELDS:
            self.assertIn(field, instructions)
        self.assertIn("canonical v1 top-level shape is exactly", instructions)
        self.assertIn("resolution_state`: must equal `resolved`", instructions)
        self.assertIn("Exact model and effort request injection is mandatory and immutable", instructions)
        self.assertIn("validated only for canonical internal consistency", instructions)
        self.assertIn("Effective effort and context may honestly be unavailable", instructions)
        self.assertIn("Prompt echoes, caller defaults, aliases, host defaults, copied requested values", instructions)
        self.assertIn("external authenticated harness is the sole spawn and admission authority", instructions)
        self.assertNotRegex(instructions, r"\b(?:request_injection|model_readback|effort_readback|context_readback)_source\b")
        self.assertIn("stop before spawn", instructions)
        self.assertIn("Exact model and effort request injection is mandatory and immutable", instructions)
        self.assertNotIn("resolved_effort", instructions)
        self.assertNotIn("resolved_context_form", instructions)
        self.assertNotIn("provider_readback_source", instructions)
        self.assertNotIn("provider_readback_evidence", instructions)
        data = tomllib.loads(text)
        self.assertNotIn("model", data)
        self.assertNotIn("model_reasoning_effort", data)

    def generated_scaffold(self, target: Path) -> Path:
        for relative, content in installer.build_files("example").items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return target / "scripts" / "validate_agent_configs.py"

    def run_validator(self, script: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script)],
            cwd=script.parents[1],
            text=True,
            capture_output=True,
            check=False,
        )

    def load_seeds_scanner(self):
        scanner_path = Path(__file__).parents[1] / "tests" / "test_preflight_capabilities.py"
        scanner_spec = importlib.util.spec_from_file_location("seeds_scanner", scanner_path)
        assert scanner_spec and scanner_spec.loader
        scanner = importlib.util.module_from_spec(scanner_spec)
        scanner_spec.loader.exec_module(scanner)
        return scanner

    def test_every_rendered_build_file_is_scanned_without_temp_output(self) -> None:
        scanner = self.load_seeds_scanner()

        violations = scanner.rendered_build_file_violations(installer.build_files("example"))

        self.assertEqual(violations, [], "\n".join(violations))

    def test_rendered_build_files_ignores_unresolved_dynamic_command_forms(self) -> None:
        scanner = self.load_seeds_scanner()

        files = {
            "scripts/worker.ps1": "& $seed_command $seed_action\nStart-Process -FilePath $seed_command -ArgumentList @('sync')\n",
            "scripts/worker.py": "subprocess.run([command, action])\n",
        }
        violations = scanner.rendered_build_file_violations(files)

        self.assertEqual(violations, [], "\n".join(violations))

    def test_generated_research_director_literal_guidance_has_no_mutation_leak(self) -> None:
        generated = installer.build_files("example")[".codex/agents/research_director.toml"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            generated_path = root / "skills" / "codex-research-os" / "generated" / "research_director.toml"
            generated_path.parent.mkdir(parents=True)
            generated_path.write_text(generated, encoding="utf-8")

            scanner = self.load_seeds_scanner()

            violations = scanner.shipped_surface_violations(root)

        self.assertEqual(violations, [], "\n".join(violations))

    def test_generated_makefile_uses_mise_uv_python(self) -> None:
        makefile = installer.core_files("example")["Makefile"]
        self.assertIn("PYTHON := mise x uv@0.11.17 -- uv run --python 3.12.11 python", makefile)
        self.assertNotIn("python3", makefile)

    def test_all_generated_roles_use_certified_runtime_assignment_boundary(self) -> None:
        agents = self.generated_agents()
        self.assertEqual(len(agents), 17)
        for path, text in agents.items():
            with self.subTest(agent=path):
                self.assert_dispatch_contract(text)

    def test_all_checked_in_roles_are_exact_generator_outputs(self) -> None:
        generated = self.generated_agents()
        static = tuple(sorted(STATIC_AGENTS.glob("*.toml")))
        self.assertEqual(len(static), 17)
        self.assertEqual({path.name for path in static}, {Path(path).name for path in generated})
        for path in static:
            with self.subTest(agent=path.name):
                expected = generated[f".codex/agents/{path.name}"]
                self.assertEqual(path.read_text(encoding="utf-8"), expected)
                self.assert_dispatch_contract(expected)

    def test_generated_research_director_preserves_one_exact_seeds_authority_block(self) -> None:
        director = installer.build_files("example")[".codex/agents/research_director.toml"]
        self.assertIn("Research Director is Seeds-read-only", director)
        self.assertIn("Seeds(<target>, prime)", director)
        self.assertIn("Seeds(<target>, ready --format json)", director)
        self.assertIn("Seeds(<target>, blocked --format json)", director)
        self.assertIn("MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec", director)
        self.assertIn("Do not create, claim, update, close, sync, or disposition Seeds", director)
        self.assertIn("exactly one typed `SeedProposal {", director)
        self.assertEqual(director.count("Seeds authority:"), 1)

    def test_generated_agent_validator_accepts_canonical_scaffold(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            script = self.generated_scaffold(Path(directory))
            result = self.run_validator(script)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validated 17 agent config(s).", result.stdout)

    def test_generated_agent_validator_rejects_static_pins_and_runtime_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.generated_scaffold(root)
            agent = root / ".codex" / "agents" / "experimentalist.toml"
            original = agent.read_text(encoding="utf-8")
            mutants = {
                "static model": original.replace('sandbox_mode = "', 'model = "gpt-5.6-terra"\nsandbox_mode = "', 1),
                "static effort": original.replace('sandbox_mode = "', 'model_reasoning_effort = "high"\nsandbox_mode = "', 1),
                "host default": original.replace("You are the experimentalist.", "Host default selects the model. You are the experimentalist.", 1),
                "requested-to-readback": original.replace("You are the experimentalist.", "requested_model_id becomes model readback. You are the experimentalist.", 1),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    agent.write_text(mutant, encoding="utf-8")
                    result = self.run_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    agent.write_text(original, encoding="utf-8")

    def test_generated_agent_validator_rejects_director_launcher_and_authority_mutants(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = self.generated_scaffold(root)
            director = root / ".codex" / "agents" / "research_director.toml"
            original = director.read_text(encoding="utf-8")
            mutants = {
                "alternate launcher": original.replace("You are the research director for this repository.", "You are the research director for this repository. Seeds(<target>, create title).", 1),
                "create grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may create Seeds.", 1),
                "claim grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may claim Seeds.", 1),
                "update grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may update Seeds.", 1),
                "close grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may close Seeds.", 1),
                "sync grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may sync Seeds.", 1),
                "disposition grant": original.replace("You are the research director for this repository.", "You are the research director for this repository. The Research Director may disposition Seeds.", 1),
            }
            for name, mutant in mutants.items():
                with self.subTest(mutant=name):
                    director.write_text(mutant, encoding="utf-8")
                    result = self.run_validator(script)
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    director.write_text(original, encoding="utf-8")

    def test_pinned_research_installer_task_runs_help(self) -> None:
        result = subprocess.run(
            ["mise", "-C", str(SCRIPT.parents[3]), "run", "research-os:install", "--", "--help"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--target", result.stdout)
        self.assertIn("required", result.stdout)

    def test_pinned_research_installer_task_refuses_an_implicit_target(self) -> None:
        result = subprocess.run(
            ["mise", "-C", str(SCRIPT.parents[3]), "run", "research-os:install"],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--target", result.stderr)

    def test_research_os_installer_is_standalone_with_packaged_policy_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            standalone = Path(directory) / "codex-research-os"
            shutil.copytree(SCRIPT.parents[1], standalone)
            result = subprocess.run(
                [sys.executable, str(standalone / "scripts" / "install_research_os.py"), "--dry-run", "--target", directory],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Research OS setup summary", result.stdout)

    def test_missing_target_refuses_at_exit_2_without_traceback(self) -> None:
        """SP-10: a supplied-but-missing `--target` is a named input refusal (2), not a crash (1)."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            self.assertFalse(missing.exists())
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--target", str(missing), "--dry-run"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, installer.EXIT_INPUT, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            # The launcher resolves `--target` before it opens it, so the refusal names the
            # resolved root. On Windows that is the long form of a path `tempfile` hands out in
            # 8.3 form (`RUNNER~1` -> `runneradmin`), so the supplied string is not what the
            # operator is shown; resolving here compares the two through the same normalization.
            self.assertIn(str(missing.resolve()), result.stderr)

    def test_present_but_not_a_directory_target_also_refuses_at_exit_2_without_traceback(self) -> None:
        """Positive control: the same wrap catches a present-but-invalid target (a regular file,
        not a directory) through its existing named `_open_root` path, not through a string
        match on "missing" — a present target still hits the module's own refusal, never 1."""
        with tempfile.TemporaryDirectory() as tmp:
            regular_file = Path(tmp) / "not-a-directory"
            regular_file.write_text("", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--target", str(regular_file), "--dry-run"],
                text=True,
                capture_output=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, installer.EXIT_INPUT, result.stdout + result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(regular_file.resolve()), result.stderr)

    def test_the_windows_unsafe_root_refusal_names_the_root(self) -> None:
        """The `nt` half of `_open_root` reaches the same operator as the POSIX half.

        `os.open(..., O_DIRECTORY)` fails with ENOTDIR and the POSIX refusal quotes that error
        with the root in it, so the path was always named there. The Windows branch decides the
        same thing from `lstat` and used to raise a bare sentence, which is why the launcher's
        present-but-invalid target refusal named no path on windows-2025 (agentic-sdlc-5ce7).
        Driving the branch under a forced `os.name` is the only way to hold it from here.
        """
        root = Path("C:\\Users\\runneradmin\\AppData\\Local\\Temp\\not-a-directory")
        regular_file = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_file_attributes=0)
        with mock.patch.object(installer.os, "name", "nt"), mock.patch.object(
            installer.os, "lstat", return_value=regular_file
        ):
            with self.assertRaises(installer.TargetRootError) as raised:
                installer._open_root(root)
        self.assertIn(str(root), str(raised.exception))


if __name__ == "__main__":
    unittest.main()
