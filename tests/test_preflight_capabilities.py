from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "check-agentic-sdlc-prereqs.sh"
BASH = None if os.name == "nt" else shutil.which("bash")
EXACT_RUNTIMES = [
    "node@22.22.3",
    "bun@1.3.10",
    "npm:@os-eco/seeds-cli@0.5.14",
]
OWNED_DOCS = [
    ROOT / "commands" / "sdlc-init.md",
    ROOT / "commands" / "sdlc-frame.md",
    ROOT / "commands" / "sdlc-wave.md",
    ROOT / "commands" / "sdlc-mission.md",
    ROOT / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md",
    ROOT
    / "skills"
    / "agentic-sdlc-orchestrator"
    / "references"
    / "seeds-worktrees.md",
    ROOT / "README.md",
    ROOT / "AGENTS.md",
]


class PreflightCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        if not BASH:
            self.skipTest("Bash is required for prerequisite shell tests")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = Path(self.temp_dir.name)
        self.bin_dir = self.temp / "ambient-bin"
        self.bin_dir.mkdir()
        self.exact_root = self.temp / "mise installs" / "npm-os-eco-seeds-cli" / "0.5.14"
        (self.exact_root / "bin").mkdir(parents=True)
        self.target = self.temp / "target repo with spaces"
        self.target.mkdir()
        (self.target / "mise.toml").write_text(
            '[tools]\n"npm:@os-eco/seeds-cli" = "9.9.9"\nnode = "0.0.1"\n'
        )
        self.log = self.temp / "calls.jsonl"
        self.ambient_log = self.temp / "ambient-sd-called"
        self.sd_log = self.temp / "exact-sd.jsonl"
        self._write_executable("git", "#!/bin/sh\nexit 0\n")
        os.symlink(shutil.which("tr"), self.bin_dir / "tr")
        os.symlink(shutil.which("sh"), self.bin_dir / "sh")
        self._write_executable(
            "sd",
            f"#!/bin/sh\nprintf called > {self._shell_quote(self.ambient_log)}\nprintf '9.9.9\\n'\n",
        )
        self._write_exact_sd()
        self._write_fake_mise()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @staticmethod
    def _shell_quote(path: Path) -> str:
        return "'" + str(path).replace("'", "'\\''") + "'"

    def _write_executable(self, name: str, content: str) -> Path:
        executable = self.bin_dir / name
        executable.write_text(content)
        executable.chmod(0o755)
        return executable

    def _write_exact_sd(self) -> None:
        executable = self.exact_root / "bin" / "sd"
        executable.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json
                import os
                from pathlib import Path
                import sys

                with Path(os.environ["FAKE_SD_LOG"]).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
                if sys.argv[1:] == ["--version"]:
                    print(os.environ.get("FAKE_SD_VERSION", "0.5.14"))
                """
            )
        )
        executable.chmod(0o755)

    def _write_fake_mise(self) -> None:
        executable = self.bin_dir / "mise"
        executable.write_text(
            textwrap.dedent(
                f"""\
                #!{sys.executable}
                import json
                import os
                from pathlib import Path
                import subprocess
                import sys

                argv = sys.argv[1:]
                with Path(os.environ["FAKE_MISE_LOG"]).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({{
                        "argv": argv,
                        "cwd": os.getcwd(),
                        "npm_package_manager": os.environ.get("MISE_NPM_PACKAGE_MANAGER"),
                    }}) + "\\n")

                mode = os.environ.get("FAKE_MISE_MODE", "correct")
                root = os.environ["FAKE_MISE_ROOT"]
                if "where" in argv:
                    if mode == "windows-paths":
                        print(r"C:\\Mise\\Installs\\Seeds")
                    else:
                        print(root)
                    raise SystemExit(0)
                if "exec" not in argv or "--" not in argv:
                    raise SystemExit(2)

                separator = argv.index("--")
                command = argv[separator + 1:]
                target = argv[argv.index("--cd") + 1]
                os.chdir(target)
                if mode == "wrong-provenance":
                    selected_bin = os.environ["FAKE_AMBIENT_BIN"]
                else:
                    selected_bin = str(Path(root) / "bin")
                env = os.environ.copy()
                env["PATH"] = selected_bin + os.pathsep + env["PATH"]

                if command == ["sh", "-c", "command -v sd"]:
                    if mode == "windows-paths":
                        print(r"c:/mise/installs/seeds/BIN/sd")
                    else:
                        print(str(Path(selected_bin) / "sd"))
                    raise SystemExit(0)
                if command and command[0] == "sd":
                    if mode == "wrong-version":
                        env["FAKE_SD_VERSION"] = "0.5.13"
                    sd_path = Path(root) / "bin" / "sd" if mode == "wrong-provenance" else Path(selected_bin) / "sd"
                    completed = subprocess.run(
                        [str(sd_path), *command[1:]], env=env, check=False
                    )
                else:
                    completed = subprocess.run(command, env=env, check=False)
                raise SystemExit(completed.returncode)
                """
            )
        )
        executable.chmod(0o755)

    def _environment(self, *, github_required: bool, mode: str = "correct") -> dict[str, str]:
        return os.environ | {
            "PATH": str(self.bin_dir) + os.pathsep + os.defpath,
            "AGENTIC_SDLC_HOST_READY": "1",
            "AGENTIC_SDLC_GITHUB_REQUIRED": "1" if github_required else "0",
            "HOME": str(self.temp),
            "FAKE_MISE_LOG": str(self.log),
            "FAKE_MISE_ROOT": str(self.exact_root),
            "FAKE_MISE_MODE": mode,
            "FAKE_AMBIENT_BIN": str(self.bin_dir),
            "FAKE_SD_LOG": str(self.sd_log),
        }

    def run_preflight(
        self, *, github_required: bool, mode: str = "correct"
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(SCRIPT)],
            cwd=self.target,
            env=self._environment(github_required=github_required, mode=mode),
            text=True,
            capture_output=True,
            check=False,
        )

    def _mise_calls(self) -> list[dict[str, object]]:
        if not self.log.exists():
            return []
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def _sd_calls(self) -> list[dict[str, object]]:
        if not self.sd_log.exists():
            return []
        return [json.loads(line) for line in self.sd_log.read_text().splitlines()]

    def assert_exact_contract(self, call: dict[str, object]) -> None:
        argv = call["argv"]
        self.assertEqual(call["npm_package_manager"], "npm")
        self.assertEqual(argv[:4], ["--no-config", "--cd", str(self.target), "exec"])
        self.assertEqual(argv[4:7], EXACT_RUNTIMES)
        self.assertEqual(argv[7], "--")
        self.assertNotEqual(argv[8:9], ["mise"])

    def test_ambient_wrong_sd_is_ignored_and_exact_mise_seeds_is_required(self) -> None:
        result = self.run_preflight(github_required=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.ambient_log.exists(), "ambient sd must never execute")
        calls = self._mise_calls()
        self.assertGreaterEqual(len(calls), 3)
        exact_calls = [call for call in calls if "exec" in call["argv"]]
        self.assertGreaterEqual(len(exact_calls), 3)
        for call in exact_calls[:3]:
            self.assert_exact_contract(call)
        self.assertIn("ok:       Seeds 0.5.14", result.stdout)

    def test_wrong_exact_version_fails_closed(self) -> None:
        result = self.run_preflight(github_required=False, mode="wrong-version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Seeds version", result.stderr)

    def test_wrong_or_separator_ambiguous_provenance_fails_closed(self) -> None:
        result = self.run_preflight(github_required=False, mode="wrong-provenance")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Seeds provenance", result.stderr)

    def test_windows_provenance_comparison_is_case_insensitive_and_separator_normalized(self) -> None:
        result = self.run_preflight(github_required=False, mode="windows-paths")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_target_cwd_hostile_config_and_argument_boundaries(self) -> None:
        arguments = ["create", "title with spaces", "*", "--metadata=a=b c"]
        shell = '. "$1"; shift; agentic_sdlc_seeds "$@"'
        result = subprocess.run(
            [BASH, "-c", shell, "test-shell", str(SCRIPT), str(self.target), *arguments],
            cwd=ROOT,
            env=self._environment(github_required=False),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.ambient_log.exists(), "ambient sd must never execute")
        calls = self._mise_calls()
        self.assertEqual(len(calls), 1)
        self.assert_exact_contract(calls[0])
        self.assertEqual(calls[0]["argv"][8:], ["sd", *arguments])
        self.assertEqual(self._sd_calls(), [{"argv": arguments, "cwd": str(self.target)}])

    def test_local_git_run_does_not_require_gh(self) -> None:
        self._write_executable("gh", "#!/bin/sh\nexit 127\n")
        (self.bin_dir / "gh").unlink()
        env = self._environment(github_required=False)
        env["PATH"] = str(self.bin_dir)
        result = subprocess.run(
            [BASH, str(SCRIPT)], cwd=self.target, env=env, text=True,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("gh not found (GitHub publication adapter skipped", result.stdout)

    def test_selected_github_operation_requires_gh(self) -> None:
        env = self._environment(github_required=True)
        env["PATH"] = str(self.bin_dir)
        result = subprocess.run(
            [BASH, str(SCRIPT)], cwd=self.target, env=env, text=True,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("MISSING:  gh (required)", result.stderr)


class SeedsDocumentationContractTests(unittest.TestCase):
    def test_owned_docs_have_no_unqualified_operational_sd_calls(self) -> None:
        operational_sd = re.compile(r"(?<![\w:@-])sd\s+(?:prime|ready|blocked|init|sync)\b")
        violations = []
        for path in OWNED_DOCS:
            for line_number, line in enumerate(path.read_text().splitlines(), 1):
                if operational_sd.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
        self.assertEqual(violations, [], "\n".join(violations))

    def test_docs_define_exact_posix_and_process_scoped_windows_contract(self) -> None:
        skill = (ROOT / "skills" / "agentic-sdlc-orchestrator" / "SKILL.md").read_text()
        reference = (
            ROOT
            / "skills"
            / "agentic-sdlc-orchestrator"
            / "references"
            / "seeds-worktrees.md"
        ).read_text()
        exact = (
            "MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec "
            "node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sd <args>"
        )
        self.assertIn(exact, skill)
        self.assertIn("Seeds(<target>, <args...>)", skill)
        self.assertIn(exact, reference)
        self.assertIn("$env:MISE_NPM_PACKAGE_MANAGER", reference)
        self.assertIn("try {", reference)
        self.assertIn("finally {", reference)

    def test_readme_and_agents_name_mise_as_only_bootstrap_prerequisite(self) -> None:
        for path in (ROOT / "README.md", ROOT / "AGENTS.md"):
            content = path.read_text()
            normalized = " ".join(content.split())
            self.assertRegex(normalized, r"(?i)mise(?:\s+2026\.4\.27\+?|\s+2026\.4\.27 or newer)? is the only bootstrap prerequisite")
            self.assertNotRegex(normalized, r"(?i)documented Seeds distribution")
            self.assertNotRegex(normalized, r"(?i)(install|installed|installation)[^.]*Seeds[^.]*separat")

    def test_docs_disclose_npm_lock_integrity_limitation(self) -> None:
        for path in (ROOT / "README.md", ROOT / "AGENTS.md"):
            content = path.read_text()
            normalized = " ".join(content.split())
            self.assertIn(
                "Seeds lock proves the exact version and npm backend, not tarball or transitive dependency integrity",
                normalized,
            )


if __name__ == "__main__":
    unittest.main()
