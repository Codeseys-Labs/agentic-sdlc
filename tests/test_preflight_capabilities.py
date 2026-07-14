from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tomllib
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
SHIPPED_TEXT_SUFFIXES = frozenset({".json", ".md", ".ps1", ".py", ".sh", ".toml", ".yaml", ".yml"})
EXCLUDED_SHIPPED_SURFACE_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".seeds",
        "__pycache__",
        "archive",
        "archives",
        "artifacts",
        "build",
        "dist",
        "history",
        "historical",
        "node_modules",
        "temp",
        "tmp",
        "tests",
    }
)
SEEDS_ACTION = r"(?:claim|create|update|close|sync|disposition)"
SEEDS_ACTION_LIST = rf"{SEEDS_ACTION}(?:\s*(?:/|or|,|and|-)\s*(?:{SEEDS_ACTION}|or\s+))*"
SEEDS_OBJECT = r"(?:Seeds?\s+(?:issue|item|record|state|queue)|Seed[-\s]queue)"
SEEDS_PSEUDO_OPERATION = re.compile(
    rf"\bSeeds\(\s*[^,()]+\s*,\s*{SEEDS_ACTION}\b", re.IGNORECASE
)
NEGATED_PSEUDO_OPERATION = re.compile(
    rf"\b(?:should|do|must)\s+not\s+(?:invoke|run)\s+Seeds\(\s*[^,()]+\s*,\s*{SEEDS_ACTION}\b|"
    rf"\bnever\s+(?:invoke|run)\s+Seeds\(\s*[^,()]+\s*,\s*{SEEDS_ACTION}\b",
    re.IGNORECASE,
)
SEEDS_ACTION_FIRST = re.compile(
    rf"\b{SEEDS_ACTION_LIST}\b\s+(?:a\s+|an\s+|the\s+)?{SEEDS_OBJECT}\b(?!\s+(?:migration[-\s]?guide|documentation|security[-\s]?gap)\b)",
    re.IGNORECASE,
)
SEEDS_ACTION_SUBJECT_FIRST = re.compile(
    rf"\b{SEEDS_OBJECT}\s+{SEEDS_ACTION_LIST}\b",
    re.IGNORECASE,
)
NEGATED_SEEDS_ACTION = re.compile(
    rf"\b(?:should|do|must)\s+not\s+{SEEDS_ACTION_LIST}\b|"
    rf"\b(?:cannot|never)\s+{SEEDS_ACTION_LIST}\b",
    re.IGNORECASE,
)
CLAUSE_BOUNDARY = re.compile(r"[.;]|\b(?:and|but)\b", re.IGNORECASE)
HYPHENATED_ACTION_SEPARATOR = re.compile(rf"\b({SEEDS_ACTION})-({SEEDS_ACTION})\b", re.IGNORECASE)
SD_COMMAND = re.compile(
    r"\bsd\s+(?:prime|ready|blocked|init|sync|create|claim|update|close|disposition)\b",
    re.IGNORECASE,
)
SD_WRAPPED_COMMAND = re.compile(
    r"\b(?:command|exec|env(?:\s+[A-Za-z_][A-Za-z0-9_]*=[^\s`]+)*|sh\s+-c|bash\s+-lc)\s+"
    r"(?:['\"])?(?:[A-Za-z_][A-Za-z0-9_]*=[^\s`]+\s+)*sd\s+"
    r"(?:prime|ready|blocked|init|sync|create|claim|update|close|disposition)\b",
    re.IGNORECASE,
)
SD_INLINE_COMMAND = re.compile(
    r"[`'\"]\s*sd\s+(?:prime|ready|blocked|init|sync|create|claim|update|close|disposition)\b",
    re.IGNORECASE,
)
SD_INSTRUCTION = re.compile(
    r"\b(?:check|execute|invoke|run|use)\s+(?:the\s+)?(?:command\s+)?"
    r"(?:\$\s*)?(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=[^\s`]+\s+)*`?"
    + SD_COMMAND.pattern,
    re.IGNORECASE,
)


def normalized_command_prefix(line: str) -> str:
    """Remove common shell and Markdown prefixes before checking a literal command."""
    command = line.strip()
    command = re.sub(r"^(?:[-*+]\s*)?`?\$?\s*", "", command)
    command = re.sub(r"^(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=[^\s`]+\s+)*", "", command)
    return command.lstrip("`").lstrip("'\"")


def clauses(line: str) -> list[str]:
    return [clause.strip() for clause in re.split(r"[;]|\b(?:and|but)\s+(?=\w+\s+(?:a\s+)?Seeds?)|,\s+(?=\w+\s+(?:a\s+)?Seeds?)", line, flags=re.IGNORECASE) if clause.strip()]


def normalized_seeds_guidance(clause: str) -> str:
    return HYPHENATED_ACTION_SEPARATOR.sub(r"\1/\2", clause)


def clause_has_seeds_mutation_guidance(clause: str) -> bool:
    clause = normalized_seeds_guidance(clause)
    pseudo_operations = list(SEEDS_PSEUDO_OPERATION.finditer(clause))
    if pseudo_operations:
        return any(
            not NEGATED_PSEUDO_OPERATION.search(clause[max(0, match.start() - 32):match.end()])
            for match in pseudo_operations
        )
    return not NEGATED_SEEDS_ACTION.search(clause) and any(
        pattern.search(clause) for pattern in (SEEDS_ACTION_FIRST, SEEDS_ACTION_SUBJECT_FIRST)
    )


def literal_guidance_lines(path: Path) -> list[tuple[int, str]]:
    """Return only Python string literals; other shipped text is scanned verbatim."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return list(enumerate(text.splitlines(), 1))
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return list(enumerate(text.splitlines(), 1))
    guidance: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            guidance.extend((node.lineno + offset, line) for offset, line in enumerate(node.value.splitlines() or [node.value]))
    return guidance


def shipped_surface_paths(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in SHIPPED_TEXT_SUFFIXES
        and not (set(path.relative_to(root).parts) & EXCLUDED_SHIPPED_SURFACE_PARTS)
    )


def is_conductor_owned_surface(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative.parts[:2] != ("agents", "codex") or relative.name != "conductor.toml":
        return False
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")).get("name") == "conductor"
    except tomllib.TOMLDecodeError:
        return False


def should_enforce_seeds_authority(path: Path, root: Path) -> bool:
    return not is_conductor_owned_surface(path, root)


def shipped_surface_violations(root: Path) -> list[str]:
    violations = []
    for path in shipped_surface_paths(root):
        relative = path.relative_to(root)
        for line_number, line in literal_guidance_lines(path):
            command = normalized_command_prefix(line)
            if (
                SD_INSTRUCTION.search(line)
                or SD_COMMAND.match(command)
                or SD_WRAPPED_COMMAND.search(line)
                or SD_INLINE_COMMAND.search(line)
            ):
                violations.append(
                    f"{relative.as_posix()}:{line_number}: bare operational sd invocation: {line.strip()}"
                )
            if should_enforce_seeds_authority(path, root) and any(
                clause_has_seeds_mutation_guidance(clause) for clause in clauses(line)
            ):
                violations.append(
                    f"{relative.as_posix()}:{line_number}: direct non-conductor Seeds queue mutation guidance: {line.strip()}"
                )
    return violations


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
    def test_shipped_surface_has_no_bare_sd_or_non_conductor_queue_mutation_guidance(self) -> None:
        violations = shipped_surface_violations(ROOT)
        self.assertEqual(violations, [], "\n".join(violations))

    def test_shipped_surface_discovers_recursive_shipped_paths_and_excludes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            included = {
                "README.md",
                "AGENTS.md",
                "CLAUDE.md",
                "commands/nested/runbook.md",
                "skills/example/references/reference.md",
                "skills/example/templates/template.md",
                "skills/codex-research-os/templates/research-os.md",
                "agents/claude/worker.md",
                "agents/codex/worker.toml",
                "agents/codex/research/director.toml",
            }
            excluded = {
                "tests/fixture.md",
                "history/old-runbook.md",
                "artifacts/report.md",
                "agents/codex/research/__pycache__/cached.toml",
            }
            for relative in included | excluded:
                path = fixture_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("shipped surface fixture\n", encoding="utf-8")

            discovered = {
                path.relative_to(fixture_root).as_posix()
                for path in shipped_surface_paths(fixture_root)
            }

        self.assertTrue(included <= discovered)
        self.assertFalse(excluded & discovered)

    def test_shipped_surface_contract_rejects_representative_leaks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "commands").mkdir()
            (fixture_root / "agents" / "codex" / "research").mkdir(parents=True)
            (fixture_root / "README.md").write_text(
                "Seeds(target, ready) names the provider-neutral notation.\n",
                encoding="utf-8",
            )
            (fixture_root / "commands" / "leak.md").write_text(
                "- Run `sd sync` after reconciliation.\n",
                encoding="utf-8",
            )
            (fixture_root / "agents" / "codex" / "research" / "director.toml").write_text(
                "Claim or create a Seeds issue before work.\n"
                "Use Seeds(<target>, close) after work.\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(len(violations), 3, "\n".join(violations))
        self.assertTrue(any("bare operational sd invocation" in item for item in violations))
        self.assertTrue(
            any("direct non-conductor Seeds queue mutation guidance" in item for item in violations)
        )

    def test_shipped_surface_scanner_normalizes_and_scopes_seeds_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "research" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "$ sd sync",
                        "Run the command sd ready.",
                        "env MODE=test sd ready",
                        "Seeds(target, create)",
                        "Seed-queue claim/create before work.",
                        "Seed-queue claim-create before work.",
                        "Do not wait; create a Seeds issue.",
                        "After notifying the conductor create a Seeds issue.",
                        "A worker claiming conductor authorization may create a Seeds issue.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            (fixture_root / "agents" / "codex" / "conductor.toml").write_text(
                'name = "conductor"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
                encoding="utf-8",
            )
            (fixture_root / "README.md").write_text(
                "\n".join(
                    (
                        "Create a chart comparing Seeds queue performance.",
                        "Update documentation about the Seeds queue.",
                        "Workers should not claim or create Seeds; emit a proposal only.",
                        "Workers do not claim or create Seeds; emit a proposal only.",
                        "Workers never claim or create Seeds; emit a proposal only.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(len(violations), 9, "\n".join(violations))
        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations), 3
        )
        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            6,
        )

    def test_shipped_surface_scanner_enforces_every_shipped_text_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            included = {
                "commands/worker-guidance.md": "Workers may create a Seeds issue.\n",
                "skills/example/templates/worker.md": "Workers may claim a Seeds item.\n",
                "skills/example/scripts/render.py": 'GUIDANCE = "Workers may update a Seeds record."\n',
                "skills/example/generated/rendered.md": "Workers may close a Seeds state.\n",
                "scripts/worker.sh": "env MODE=test sd sync\n",
                "scripts/worker.ps1": "sd create\n",
                "policies/worker.json": '{"guidance": "Workers may sync a Seeds queue."}\n',
                "agents/codex/worker.toml": "Workers may create a Seeds issue.\n",
            }
            excluded = {
                "build/worker.md": "Workers may create a Seeds issue.\n",
                "temp/worker.md": "Workers may create a Seeds issue.\n",
                "tmp/worker.md": "Workers may create a Seeds issue.\n",
                "archive/worker.md": "Workers may create a Seeds issue.\n",
                "tests/worker.md": "Workers may create a Seeds issue.\n",
            }
            for relative, content in included.items() | excluded.items():
                path = fixture_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(len(violations), 8, "\n".join(violations))
        self.assertTrue(any(item.startswith("skills/example/scripts/render.py:") for item in violations))
        self.assertTrue(any(item.startswith("policies/worker.json:") for item in violations))
        self.assertFalse(any("build/" in item or "temp/" in item or "tmp/" in item or "archive/" in item for item in violations))

    def test_only_exact_conductor_role_paths_may_state_conductor_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            surfaces = {
                "agents/codex/conductor.toml": 'name = "conductor"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
                "agents/codex/worker-conductor.toml": 'name = "worker-conductor"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
                "agents/codex/research/conductor.toml": 'name = "research_director"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
                "commands/conductor.md": "Conductor-only authority may create a Seeds issue.\n",
            }
            for relative, content in surfaces.items():
                path = fixture_root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            3,
            "\n".join(violations),
        )
        self.assertFalse(any(item.startswith("agents/codex/conductor.toml:") for item in violations))

    def test_negation_scopes_each_operation_and_accepts_negated_seeds_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Workers do not create Seeds, but claim a Seeds item.",
                        "Workers do not claim Seeds and create a Seeds issue.",
                        "Workers must not close Seeds; update a Seeds record.",
                        "Workers should not update Seeds, but close a Seeds state.",
                        "Workers never close Seeds, sync a Seeds queue.",
                        "Never invoke Seeds(repo.name, create).",
                        "Never invoke Seeds(<target>, claim).",
                        "Never invoke Seeds(target, update).",
                        "Never invoke Seeds(repo.name, close).",
                        "Never invoke sEeDs(REPO.Name, sYnC).",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            5,
            "\n".join(violations),
        )

    def test_pseudo_operations_cover_angle_target_target_repo_name_and_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Seeds(<target>, create).",
                        "Seeds(target, claim).",
                        "Seeds(repo.name, update).",
                        "sEeDs(REPO.Name, cLoSe).",
                        "Seeds(target, sync).",
                        "Never invoke Seeds(repo.name, create).",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            5,
            "\n".join(violations),
        )

    def test_bare_sd_invocations_reject_wrappers_inline_and_fenced_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            command = fixture_root / "commands" / "runbook.md"
            command.parent.mkdir(parents=True)
            command.write_text(
                "\n".join(
                    (
                        "command sd create",
                        "exec sd claim",
                        "env MODE=test sd update",
                        "sh -c 'sd close'",
                        'bash -lc "sd sync"',
                        "Run inline `sd create` only after review.",
                        "```sh",
                        "sd claim",
                        "```",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations),
            7,
            "\n".join(violations),
        )

    def test_queue_mutation_objects_are_rejected_without_topic_false_positives(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Create a chart comparing Seeds queue performance.",
                        "Create a Seeds queue migration-guide.",
                        "Update the Seeds queue documentation.",
                        "Close a Seeds security-gap.",
                        "Create a Seeds issue.",
                        "Claim a Seeds item.",
                        "Update a Seeds record.",
                        "Close a Seeds state.",
                        "Sync a Seeds queue.",
                        "Seeds queue sync is conductor-only.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            6,
            "\n".join(violations),
        )

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
