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
    "node@22.23.2",
    "bun@1.4.0",
    "npm:@os-eco/seeds-cli@0.5.15",
]
SHIPPED_TEXT_SUFFIXES = frozenset({".json", ".md", ".mjs", ".ps1", ".py", ".sh", ".toml", ".yaml", ".yml"})
EXCLUDED_SHIPPED_SURFACE_PARTS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".seeds",
        # A linked worktree checked out beneath the repo is another commit's tree, not this
        # one's shipped surface. Walking into it also breaks every root-relative exemption
        # (commands/sdlc-init.md is conductor-owned at the root but not at
        # .worktrees/<name>/commands/sdlc-init.md), so it reports violations that do not
        # exist in what this commit actually ships.
        ".worktrees",
        # Same reasoning for the harness-created agent worktrees under .claude/worktrees/
        # (and .claude/ generally is host-local session config, not shipped surface).
        ".claude",
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
SEEDS_ACTION = r"(?:init|claim|create|update|close|sync|disposition)"
SEEDS_QUOTE_DELIMITERS = str.maketrans("", "", "'\"`‘’“”")
SEEDS_ACTION_LIST = rf"{SEEDS_ACTION}(?:\s*(?:/|or|,|and|-)\s*{SEEDS_ACTION})*"
SEEDS_OBJECT = r"(?:Seeds?\s+(?:issues?|items?|records?|states?|queues?(?:[-\s]states?)?)|Seed[-\s]queues?(?:[-\s]states?)?)"
SEEDS_PSEUDO_OPERATION = re.compile(
    rf"\bSeeds\(\s*[^,()]+\s*,\s*(?P<action>{SEEDS_ACTION})\b", re.IGNORECASE
)
NEGATED_PSEUDO_OPERATION = re.compile(
    r"\b(?:(?:should|do|must)\s+not|never)\s+(?:invoke|run|call|use|execute)\s*`?\s*$",
    re.IGNORECASE,
)
SEEDS_DESCRIPTIVE_SUBJECT = r"(?:semantics|lifecycle|terminology)"
NEUTRAL_DESCRIPTIVE_TOPIC_PROSE = re.compile(
    rf"^\s+{SEEDS_DESCRIPTIVE_SUBJECT}\s+(?:is|are)\s+provider-neutral[.!?]\s*$",
    re.IGNORECASE,
)
SEEDS_ACTION_FIRST = re.compile(
    rf"\b(?P<actions>{SEEDS_ACTION_LIST})\b\s+(?:a\s+|an\s+|the\s+)?{SEEDS_OBJECT}\b"
    r"(?!\s+(?:dashboard|chart|guide|docs?|documentation|security(?:[-\s]gap)?|migration[-\s]?guide)\b)",
    re.IGNORECASE,
)
SEEDS_ACTION_SUBJECT_FIRST = re.compile(
    rf"\b{SEEDS_OBJECT}\s+(?P<actions>{SEEDS_ACTION_LIST})\b"
    r"(?!\s+(?:dashboard|chart|guide|docs?|documentation|security(?:[-\s]gap)?|migration[-\s]?guide)\b)",
    re.IGNORECASE,
)
NEGATED_SEEDS_ACTION = re.compile(
    r"\b(?:(?:should|do|must)\s+not|cannot|never)\s*$", re.IGNORECASE
)
SD_ACTION = r"(?:prime|ready|blocked|init|sync|create|claim|update|close|disposition)"
SD_EXECUTABLE = r"sd(?:\.(?:exe|cmd|bat|com|ps1|sh))?"
SD_COMMAND = re.compile(
    rf"\b{SD_EXECUTABLE}\b(?:['\"])?\s+['\"]?{SD_ACTION}\b", re.IGNORECASE
)
SD_QUOTED_COMMAND = re.compile(
    rf"(?:^|\s)['\"](?:[^'\"]*[\\/])?{SD_EXECUTABLE}['\"]\s+['\"]?{SD_ACTION}\b",
    re.IGNORECASE,
)
SD_START_PROCESS = re.compile(
    rf"\bStart-Process\b.*?\b{SD_EXECUTABLE}\b.*?\b{SD_ACTION}\b",
    re.IGNORECASE,
)
POWERSHELL_COMMAND_VARIABLE = re.compile(
    r"^\s*\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*['\"](?P<value>[^'\"]+)['\"]\s*$",
    re.IGNORECASE,
)
POWERSHELL_CALL_VARIABLE = re.compile(
    r"\&\s*(?P<command>\$(?P<variable>[A-Za-z_][A-Za-z0-9_]*)|['\"](?P<literal>[^'\"]+)['\"])\s+"
    r"(?P<action>\$(?P<action_variable>[A-Za-z_][A-Za-z0-9_]*)|['\"](?P<action_literal>[^'\"]+)['\"])",
    re.IGNORECASE,
)
POWERSHELL_START_PROCESS_VARIABLE = re.compile(
    r"\bStart-Process\b.*?-FilePath\s+(?P<command>\$(?P<variable>[A-Za-z_][A-Za-z0-9_]*)|['\"](?P<literal>[^'\"]+)['\"]).*?"
    r"-ArgumentList\s+(?P<action>@\(\s*['\"](?P<array_literal>[^'\"]+)['\"]\s*\)|\$(?P<action_variable>[A-Za-z_][A-Za-z0-9_]*)|['\"](?P<action_literal>[^'\"]+)['\"])",
    re.IGNORECASE,
)
PYTHON_SUBPROCESS_CALL = frozenset({"run", "call", "check_call", "check_output", "Popen"})
CANONICAL_CONDUCTOR_PATH = Path("agents/codex/conductor.toml")
CANONICAL_CONDUCTOR_ROLE = "conductor"
CANONICAL_RECONCILIATION_PATH = Path(
    "skills/agentic-sdlc/references/sdlc-loop.md"
)
ACTOR_SCOPED_INIT_PATH = Path("commands/sdlc-init.md")


def normalized_command_prefix(line: str) -> str:
    """Remove common shell and Markdown prefixes before checking a literal command."""
    command = line.strip()
    command = re.sub(r"^(?:[-*+]\s*)?`?\$?\s*", "", command)
    command = re.sub(r"^(?:env\s+)?(?:[A-Za-z_][A-Za-z0-9_]*=[^\s`]+\s+)*", "", command)
    return command.lstrip("`").lstrip("'\"")


def clauses(line: str) -> list[str]:
    """Split prose boundaries without splitting a Seeds(target, action) call."""
    clauses = []
    start = depth = 0
    for index, character in enumerate(line):
        if character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif depth == 0 and character in ",;":
            if clause := line[start:index].strip():
                clauses.append(clause)
            start = index + 1
    if clause := line[start:].strip():
        clauses.append(clause)
    return clauses


def _safe_string_sequence(node: ast.AST, values: dict[str, str]) -> list[str] | None:
    if not isinstance(node, (ast.List, ast.Tuple)):
        return None
    sequence = [_safe_string_expression(element, values) for element in node.elts]
    return sequence if all(value is not None for value in sequence) else None


def python_subprocess_lines(tree: ast.Module) -> list[tuple[int, str]]:
    """Return direct static subprocess commands without executing Python guidance."""
    values: dict[str, str] = {}
    _assignment_strings(tree.body, values)
    guidance = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
            continue
        if node.func.attr not in PYTHON_SUBPROCESS_CALL:
            continue
        arguments = node.args[0] if node.args else next(
            (keyword.value for keyword in node.keywords if keyword.arg == "args"), None
        )
        if arguments is None:
            continue
        command = _safe_string_sequence(arguments, values)
        if command:
            guidance.append((node.lineno, " ".join(command)))
    return guidance


def static_powershell_command_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Return static command-variable executions without evaluating PowerShell."""
    values: dict[str, str] = {}
    guidance = []
    for line_number, line in lines:
        if assignment := POWERSHELL_COMMAND_VARIABLE.match(line):
            values[assignment.group("name").lower()] = assignment.group("value")
            continue
        if call := POWERSHELL_CALL_VARIABLE.search(line):
            command = call.group("literal") or values.get((call.group("variable") or "").lower())
            action = call.group("action_literal") or values.get((call.group("action_variable") or "").lower())
            if command and action and (call.group("variable") or call.group("action_variable")):
                guidance.append((line_number, f"{command} {action}"))
            continue
        if start := POWERSHELL_START_PROCESS_VARIABLE.search(line):
            command = start.group("literal") or values.get((start.group("variable") or "").lower())
            action = (
                start.group("array_literal")
                or start.group("action_literal")
                or values.get((start.group("action_variable") or "").lower())
            )
            if command and action and (start.group("variable") or start.group("action_variable")):
                guidance.append((line_number, f"{command} {action}"))
    return guidance


def _deduplicated_lines(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return list(dict.fromkeys(lines))


def guidance_command_violations(relative: Path, lines: list[tuple[int, str]]) -> list[str]:
    scanned_lines = list(lines)
    if relative.suffix == ".ps1":
        scanned_lines.extend(static_powershell_command_lines(lines))
    elif any(
        POWERSHELL_COMMAND_VARIABLE.match(line)
        or POWERSHELL_CALL_VARIABLE.search(line)
        or POWERSHELL_START_PROCESS_VARIABLE.search(line)
        for _, line in lines
    ):
        scanned_lines.extend(static_powershell_command_lines(lines))
    violations = []
    for line_number, line in _deduplicated_lines(scanned_lines):
        command = normalized_command_prefix(line)
        if SD_COMMAND.search(command) or SD_QUOTED_COMMAND.search(command) or SD_START_PROCESS.search(line):
            violations.append(
                f"{relative.as_posix()}:{line_number}: bare operational sd invocation: {line.strip()}"
            )
    return violations


def is_sd_command_sequence(values: list[str]) -> bool:
    return len(values) >= 2 and is_sd_executable(values[0]) and is_sd_action(values[1])


def command_sequence_violations(relative: Path, lines: list[tuple[int, str]]) -> list[str]:
    violations = []
    for line_number, line in lines:
        values = line.split()
        if is_sd_command_sequence(values) and not SD_COMMAND.search(normalized_command_prefix(line)):
            violations.append(
                f"{relative.as_posix()}:{line_number}: bare operational sd invocation: {line.strip()}"
            )
        for index in range(len(values) - 2):
            if values[index:index + 2] == ["mise", "exec"] and "--" in values[index + 2:]:
                separator = values.index("--", index + 2)
                if is_sd_command_sequence(values[separator + 1:]) and not SD_COMMAND.search(normalized_command_prefix(line)):
                    violations.append(
                        f"{relative.as_posix()}:{line_number}: bare operational sd invocation: {line.strip()}"
                    )
    return violations


def action_names(actions: str) -> list[str]:
    return [match.group(0).lower() for match in re.finditer(SEEDS_ACTION, actions, re.IGNORECASE)]


def is_sd_executable(value: str) -> bool:
    return bool(re.search(rf"(?:^|[\\/]){SD_EXECUTABLE}$", value, re.IGNORECASE))


def is_sd_action(value: str) -> bool:
    return bool(re.fullmatch(SD_ACTION, value, re.IGNORECASE))


def operation_is_negated(text: str, action_start: int) -> bool:
    return bool(NEGATED_SEEDS_ACTION.search(text[:action_start]))


def pseudo_operation_is_negated(text: str, action_start: int) -> bool:
    return bool(NEGATED_PSEUDO_OPERATION.search(text[:action_start]))


def is_neutral_descriptive_topic_prose(text: str, action_end: int) -> bool:
    return bool(NEUTRAL_DESCRIPTIVE_TOPIC_PROSE.match(text[action_end:]))


def seeds_mutation_operations(text: str) -> list[str]:
    normalized = text.translate(SEEDS_QUOTE_DELIMITERS)
    operations = []
    for match in SEEDS_PSEUDO_OPERATION.finditer(normalized):
        if not pseudo_operation_is_negated(normalized, match.start()):
            operations.append(match.group("action").lower())
    for pattern in (SEEDS_ACTION_FIRST, SEEDS_ACTION_SUBJECT_FIRST):
        for match in pattern.finditer(normalized):
            if not operation_is_negated(normalized, match.start("actions")) and not is_neutral_descriptive_topic_prose(
                normalized, match.end("actions")
            ):
                operations.extend(action_names(match.group("actions")))
    return operations


def clause_has_seeds_mutation_guidance(clause: str) -> bool:
    return bool(seeds_mutation_operations(clause))


def _safe_string_expression(node: ast.AST, values: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return values.get(node.id)
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return values.get(f"{node.value.id}.{node.attr}")
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _safe_string_expression(node.left, values)
        right = _safe_string_expression(node.right, values)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                rendered = _safe_string_expression(value.value, values)
                if rendered is None:
                    return None
                parts.append(rendered)
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format":
        template = _safe_string_expression(node.func.value, values)
        if template is None or node.args or any(keyword.arg is None for keyword in node.keywords):
            return None
        replacements = {}
        for keyword in node.keywords:
            replacement = _safe_string_expression(keyword.value, values)
            if replacement is None:
                return None
            replacements[keyword.arg] = replacement
        try:
            return template.format(**replacements)
        except (IndexError, KeyError, ValueError):
            return None
    return None


def _safe_string_mapping(node: ast.AST, values: dict[str, str]) -> dict[str, str] | None:
    if isinstance(node, ast.Name):
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
        if node.args or any(keyword.arg is None for keyword in node.keywords):
            return None
        rendered = {}
        for keyword in node.keywords:
            value = _safe_string_expression(keyword.value, values)
            if value is None:
                return None
            rendered[keyword.arg] = value
        return rendered
    if not isinstance(node, ast.Dict):
        return None
    rendered = {}
    for key, value in zip(node.keys, node.values):
        if key is None:
            return None
        rendered_key = _safe_string_expression(key, values)
        rendered_value = _safe_string_expression(value, values)
        if rendered_key is None or rendered_value is None:
            return None
        rendered[rendered_key] = rendered_value
    return rendered


def _assignment_strings(nodes: list[ast.stmt], values: dict[str, str]) -> None:
    for node in nodes:
        if isinstance(node, ast.Assign):
            value = _safe_string_expression(node.value, values)
            if value is not None:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        values[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = _safe_string_expression(node.value, values) if node.value else None
            if value is not None:
                values[node.target.id] = value


def rendered_build_file_lines(tree: ast.Module) -> list[tuple[int, str]]:
    """Safely reconstruct direct and helper-mediated static build_files output without execution."""
    module_values: dict[str, str] = {}
    _assignment_strings(tree.body, module_values)
    functions = {
        function.name: function
        for function in tree.body
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def render(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        values: dict[str, str],
        active: frozenset[str] = frozenset(),
    ) -> tuple[int, dict[str, str]] | None:
        if function.name in active:
            return None
        active = active | {function.name}
        for statement in function.body:
            if isinstance(statement, ast.Return) and statement.value is not None:
                direct = _safe_string_mapping(statement.value, values)
                if direct is not None:
                    return statement.lineno, direct
                if isinstance(statement.value, ast.Call) and isinstance(statement.value.func, ast.Name):
                    helper = functions.get(statement.value.func.id)
                    if helper is None or len(statement.value.args) != len(helper.args.args):
                        return None
                    helper_values = values.copy()
                    for parameter, argument in zip(helper.args.args, statement.value.args):
                        value = _safe_string_expression(argument, values)
                        if value is None:
                            return None
                        helper_values[parameter.arg] = value
                    return render(helper, helper_values, active)
            elif isinstance(statement, ast.Assign):
                _assignment_strings([statement], values)
        return None

    function = functions.get("build_files")
    if function is None:
        return []
    values = module_values.copy()
    for argument in function.args.args:
        values[argument.arg] = f"<{argument.arg}>"
    result = render(function, values)
    if result is None:
        return []
    line_number, rendered = result
    return [
        (line_number + offset, line)
        for content in rendered.values()
        for offset, line in enumerate(content.splitlines() or [content])
    ]


def literal_guidance_lines(path: Path) -> list[tuple[int, str]]:
    """Return literal and safely reconstructed Python guidance without executing it."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return list(enumerate(text.splitlines(), 1))
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return list(enumerate(text.splitlines(), 1))
    guidance = []
    formatted_string_constants = {
        id(value)
        for formatted in ast.walk(tree)
        if isinstance(formatted, ast.JoinedStr)
        for value in formatted.values
        if isinstance(value, ast.Constant) and isinstance(value.value, str)
    }
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in formatted_string_constants
        ):
            guidance.extend((node.lineno + offset, line) for offset, line in enumerate(node.value.splitlines() or [node.value]))
    guidance.extend(rendered_build_file_lines(tree))
    guidance.extend(python_subprocess_lines(tree))
    return guidance


def shipped_surface_paths(root: Path) -> list[Path]:
    paths = []
    for directory, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name not in EXCLUDED_SHIPPED_SURFACE_PARTS]
        base = Path(directory)
        paths.extend(
            base / name
            for name in files
            if (base / name).suffix in SHIPPED_TEXT_SUFFIXES
        )
    return sorted(paths)


def is_conductor_owned_surface(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if relative != CANONICAL_CONDUCTOR_PATH:
        return False
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")).get("name") == CANONICAL_CONDUCTOR_ROLE
    except (OSError, tomllib.TOMLDecodeError):
        return False


def is_actor_scoped_init_guidance(relative: Path, operation: str) -> bool:
    return relative == ACTOR_SCOPED_INIT_PATH and operation == "init"


def is_canonical_reconciliation_guidance(relative: Path, line: str, operation: str) -> bool:
    return False


def should_enforce_seeds_authority(path: Path, root: Path) -> bool:
    return not is_conductor_owned_surface(path, root)


def guidance_violations(
    relative: Path,
    lines: list[tuple[int, str]],
    *,
    enforce_seeds_authority: bool,
) -> list[str]:
    violations = guidance_command_violations(relative, lines)
    if relative.suffix != ".py":
        violations.extend(command_sequence_violations(relative, lines))
    for line_number, line in lines:
        if enforce_seeds_authority:
            operations = seeds_mutation_operations(line)
            if operations and not all(
                is_actor_scoped_init_guidance(relative, operation)
                or is_canonical_reconciliation_guidance(relative, line, operation)
                for operation in operations
            ):
                violations.append(
                    f"{relative.as_posix()}:{line_number}: direct non-conductor Seeds queue mutation guidance: {line.strip()}"
                )
    return violations


def rendered_build_file_violations(files: dict[str, str]) -> list[str]:
    """Scan every in-memory build_files output without creating a temporary tree."""
    violations = []
    for name, content in files.items():
        relative = Path(name)
        violations.extend(
            guidance_violations(
                relative,
                list(enumerate(content.splitlines(), 1)),
                enforce_seeds_authority=True,
            )
        )
    return violations


def shipped_surface_violations(root: Path) -> list[str]:
    violations = []
    for path in shipped_surface_paths(root):
        relative = path.relative_to(root)
        violations.extend(
            guidance_violations(
                relative,
                literal_guidance_lines(path),
                enforce_seeds_authority=should_enforce_seeds_authority(path, root),
            )
        )
    return violations


@unittest.skipIf(BASH is None or os.name == "nt", "Bash wrapper fixture requires POSIX")
class ExactRuntimeWrapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        # RESOLVED ONCE, HERE, because the wrapper derives its own target from `pwd -P` -- the
        # PHYSICAL cwd. On macOS `$TMPDIR` is under `/var/folders/...` and `/var` is a symlink to
        # `/private/var`, so `mkdtemp()` hands back the unresolved spelling and the argv the wrapper
        # records carries the resolved one; the two are the same directory and the assertion still
        # fails. Resolving the root is the only place that makes `pwd -P` and `self.target` agree.
        self.root = Path(self.temporary.name).resolve()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.node_root = self.root / "exact node"
        (self.node_root / "bin").mkdir(parents=True)
        self.launcher = self.root / "installed launcher.mjs"
        self.launcher.write_text("fixture\n", encoding="utf-8")
        self.calls = self.root / "node-calls.jsonl"
        self.target = self.root / "target with spaces"
        self.target.mkdir()
        self._write_executable(
            self.node_root / "bin" / "node",
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            f"with Path({str(self.calls)!r}).open('a', encoding='utf-8') as stream:\n"
            "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "raise SystemExit(int(os.environ.get('FAKE_CHILD_STATUS', '0')))\n",
        )
        self._write_executable(
            self.bin / "mise",
            f"#!{sys.executable}\n"
            "import sys\n"
            f"print({str(self.node_root)!r}) if sys.argv[1:] == ['--no-config', 'where', 'node@22.23.2'] else sys.exit(2)\n",
        )
        self._write_executable(self.bin / "git", "#!/bin/sh\nexit 0\n")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def environment(self, **overrides: str) -> dict[str, str]:
        return os.environ | {
            "PATH": str(self.bin) + os.pathsep + os.defpath,
            "AGENTIC_SDLC_LAUNCHER": str(self.launcher),
            "AGENTIC_SDLC_HOST_READY": "1",
            **overrides,
        }

    def source(self, command: str, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, "-c", f'. "$1"; shift; {command}', "wrapper-test", str(SCRIPT), *args],
            cwd=ROOT,
            env=env or self.environment(),
            text=True,
            capture_output=True,
            check=False,
        )

    def calls_read(self) -> list[list[str]]:
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]

    def test_front_doors_delegate_exact_inspect_init_and_record_argv(self) -> None:
        digest = "a" * 64
        invocations = (
            (
                'agentic_sdlc_seeds "$@"',
                (str(self.target), "ready", "--format", "json"),
                [str(self.launcher), "inspect", "--target", str(self.target), "ready", "--format", "json"],
            ),
            (
                'agentic_sdlc_seeds_init "$@"',
                (str(self.target),),
                [str(self.launcher), "record", "--target", str(self.target), "--queue-writer", "conductor", "--expect-queue", "absent", "init"],
            ),
            (
                'agentic_sdlc_seeds_record "$@"',
                (str(self.target), digest, "update", "seed-1", "--title", "two words"),
                [str(self.launcher), "record", "--target", str(self.target), "--queue-writer", "conductor", "--expect-queue", digest, "update", "seed-1", "--title", "two words"],
            ),
        )
        for command, arguments, expected in invocations:
            with self.subTest(command=command):
                result = self.source(command, *arguments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.calls_read()[-1], expected)

    def test_front_doors_reject_bad_arity_without_starting_node(self) -> None:
        for command, arguments in (
            ('agentic_sdlc_seeds "$@"', (str(self.target),)),
            ('agentic_sdlc_seeds_init "$@"', (str(self.target), "extra")),
            ('agentic_sdlc_seeds_record "$@"', (str(self.target), "absent")),
        ):
            with self.subTest(command=command):
                before = self.calls_read()
                result = self.source(command, *arguments)
                self.assertEqual(result.returncode, 2)
                self.assertIn("usage:", result.stderr)
                self.assertEqual(self.calls_read(), before)

    def test_front_door_preserves_exact_launcher_failure_status(self) -> None:
        result = self.source(
            'agentic_sdlc_seeds_init "$@"',
            str(self.target),
            env=self.environment(FAKE_CHILD_STATUS="23"),
        )
        self.assertEqual(result.returncode, 23, result.stderr)

    def test_executable_preflight_uses_exact_receipt_inspection_front_door(self) -> None:
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            cwd=self.target,
            env=self.environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("locked Seeds 0.5.15 active receipt", result.stdout)
        self.assertIn(
            [str(self.launcher), "inspect", "--target", str(self.target), "--version"],
            self.calls_read(),
        )

    def test_help_exits_zero_without_running_the_check(self) -> None:
        # Positive control for test_unknown_argument_is_a_grammar_error: a query that IS
        # recognized reaches 0, not 2, and never starts the exact-node front door.
        result = subprocess.run(
            [BASH, str(SCRIPT), "--help"],
            cwd=self.target,
            env=self.environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage:", result.stdout)
        self.assertNotIn("ok:", result.stdout)
        self.assertNotIn("locked Seeds", result.stdout)
        self.assertEqual(self.calls_read(), [])

    def test_unknown_argument_is_a_grammar_error(self) -> None:
        result = subprocess.run(
            [BASH, str(SCRIPT), "--zzz-not-a-flag"],
            cwd=self.target,
            env=self.environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("unknown argument", result.stderr)
        self.assertEqual(self.calls_read(), [])

    def test_completed_check_naming_a_missing_prerequisite_is_not_the_internal_failure_code(self) -> None:
        # The negative half: a completed, read-only check that names a MISSING prerequisite
        # must not collide with Decision 9's unexpected-internal-failure code (1).
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            cwd=self.target,
            env=self.environment(AGENTIC_SDLC_LAUNCHER=str(self.root / "no-such-launcher.mjs")),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 5, result.stderr)
        self.assertNotEqual(result.returncode, 1)
        self.assertIn("MISSING: installed flagship Seeds launcher", result.stderr)

    def test_completed_check_with_nothing_missing_stays_zero(self) -> None:
        # Positive control for the previous test: the same code path (missing == 0 branch)
        # still answers 0 when nothing is actually missing, so the mapping distinguishes two
        # real states rather than just banning the number 1.
        result = subprocess.run(
            [BASH, str(SCRIPT)],
            cwd=self.target,
            env=self.environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("locked Seeds 0.5.15 active receipt", result.stdout)


@unittest.skip("replaced by receipt-based installed launcher fixtures")
class PreflightCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        if not BASH:
            self.skipTest("Bash is required for prerequisite shell tests")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = Path(self.temp_dir.name)
        self.bin_dir = self.temp / "ambient-bin"
        self.bin_dir.mkdir()
        self.exact_root = self.temp / "mise installs" / "npm-os-eco-seeds-cli" / "0.5.15"
        self.exact_bun_root = self.temp / "mise installs" / "bun" / "1.4.0"
        (self.exact_bun_root).mkdir(parents=True)
        (self.exact_root / "bin").mkdir(parents=True)
        self.target = self.temp / "target repo with spaces ;$&[]"
        self.target.mkdir()
        self.hostile_temp_root = self.target / "inherited TEMP root"
        self.hostile_temp_root.mkdir()
        self.hostile_npmrc = self.hostile_temp_root / ".npmrc"
        self.hostile_npmrc.write_text("registry=https://inherited-temp.invalid/\n")
        (self.target / "mise.toml").write_text(
            '[tools]\n"npm:@os-eco/seeds-cli" = "9.9.9"\nnode = "0.0.1"\n'
        )
        self.target_npmrc = self.target / ".npmrc"
        self.target_npmrc.write_text(
            "registry=https://target.invalid/\n@os-eco:registry=https://target.invalid/\n"
        )
        self.ambient_npmrc = self.temp / "ambient.npmrc"
        self.ambient_npmrc.write_text("registry=https://ambient.invalid/\n")
        self.mise_data_dir = self.temp / "isolated-mise-data"
        self.mise_cache_dir = self.temp / "isolated-mise-cache"
        self.mise_data_dir.mkdir()
        self.mise_cache_dir.mkdir()
        self.log = self.temp / "calls.jsonl"
        self.ambient_log = self.temp / "ambient-sd-called"
        self.sd_log = self.temp / "exact-sd.jsonl"
        self.fake_mise_mode = self.temp / "fake-mise-mode"
        self.fake_sd_version = self.temp / "fake-sd-version"
        self.fake_mise_mode.write_text("correct")
        self.fake_sd_status = self.temp / "fake-sd-status"
        self.fake_sd_status.write_text("0")
        self._write_executable("git", "#!/bin/sh\nexit 0\n")
        os.symlink(shutil.which("tr"), self.bin_dir / "tr")
        os.symlink(shutil.which("rm"), self.bin_dir / "rm")
        os.symlink(shutil.which("mktemp"), self.bin_dir / "mktemp")
        os.symlink(shutil.which("env"), self.bin_dir / "env")
        os.symlink(shutil.which("cat"), self.bin_dir / "cat")
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

                with Path({str(self.sd_log)!r}).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
                if sys.argv[1:] == ["--version"]:
                    print(Path({str(self.fake_sd_version)!r}).read_text(encoding="utf-8"))
                raise SystemExit(int(Path({str(self.fake_sd_status)!r}).read_text(encoding="utf-8")))
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
                npm_environment = {{
                    name: value
                    for name, value in os.environ.items()
                    if name.lower().startswith("npm_config_")
                }}
                with Path({str(self.log)!r}).open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({{
                        "argv": argv,
                        "cwd": os.getcwd(),
                        "npm_package_manager": os.environ.get("MISE_NPM_PACKAGE_MANAGER"),
                        "seeds_root": os.environ.get("AGENTIC_SDLC_SEEDS_ROOT"),
                        "npm_environment": npm_environment,
                        "environment": {{
                            name: value
                            for name, value in os.environ.items()
                            if name in {{"TMPDIR", "TEMP", "TMP", "HOME", "MISE_DATA_DIR", "MISE_CACHE_DIR"}}
                        }},
                        "npm_config_files": {{
                            name: {{
                                "exists": Path(value).is_file(),
                                "contents": Path(value).read_text(encoding="utf-8") if Path(value).is_file() else None,
                            }}
                            for name, value in npm_environment.items()
                            if name in {{"NPM_CONFIG_USERCONFIG", "NPM_CONFIG_GLOBALCONFIG"}}
                        }},
                        "mise_cd": argv[argv.index("--cd") + 1] if "--cd" in argv else None,
                        "mise_cd_has_npmrc": (
                            Path(argv[argv.index("--cd") + 1]) / ".npmrc"
                        ).is_file() if "--cd" in argv else None,
                    }}) + "\\n")

                mode = Path({str(self.fake_mise_mode)!r}).read_text(encoding="utf-8")
                root = {str(self.exact_root)!r}
                if "where" in argv:
                    if mode == "windows-paths" and argv[-1].startswith("npm:"):
                        print(r"C:\\Mise\\Installs\\Seeds")
                    elif argv[-1] == "bun@1.4.0":
                        print({str(self.exact_bun_root)!r})
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
                    selected_bin = {str(self.bin_dir)!r}
                else:
                    selected_bin = str(Path(root) / "bin")
                env = os.environ.copy()
                env["PATH"] = selected_bin + os.pathsep + env["PATH"]

                if command and command[0] == "node" and command[1:2] == ["-e"]:
                    node_program = command[2]
                    target = command[3]
                    node_args = command[4:]
                    if "shell: false" not in node_program or "spawn(" not in node_program:
                        raise SystemExit(2)
                    if mode == "wrong-version":
                        Path({str(self.fake_sd_version)!r}).write_text("0.5.13")
                    exact_sd = Path(selected_bin) / "sd"
                    completed = subprocess.run(
                        [str(exact_sd), *node_args], cwd=target, env=env, check=False
                    )
                elif command == ["sh", "-c", "command -v sd"]:
                    if mode == "windows-paths":
                        print(r"c:/mise/installs/seeds/BIN/sd")
                    else:
                        print(str(Path(selected_bin) / "sd"))
                    raise SystemExit(0)
                else:
                    completed = subprocess.run(command, env=env, check=False)
                raise SystemExit(completed.returncode)
                """
            )
        )
        executable.chmod(0o755)

    def _environment(self, *, github_required: bool, mode: str = "correct") -> dict[str, str]:
        self.fake_mise_mode.write_text(mode)
        self.fake_sd_version.write_text("0.5.15")
        self.fake_sd_status.write_text("0")
        return os.environ | {
            "PATH": str(self.bin_dir) + os.pathsep + os.defpath,
            "AGENTIC_SDLC_HOST_READY": "1",
            "AGENTIC_SDLC_GITHUB_REQUIRED": "1" if github_required else "0",
            "HOME": str(self.temp),
            "NPM_CONFIG_REGISTRY": "https://ambient.invalid/",
            "NPM_CONFIG_USERCONFIG": str(self.ambient_npmrc),
            "NPM_CONFIG__OS_ECO_REGISTRY": "https://scoped-ambient.invalid/",
            "npm_config_mixed_case": "https://mixed-case.invalid/",
            "TMPDIR": str(self.hostile_temp_root),
            "TEMP": str(self.hostile_temp_root),
            "TMP": str(self.hostile_temp_root),
            "MISE_DATA_DIR": str(self.mise_data_dir),
            "MISE_CACHE_DIR": str(self.mise_cache_dir),
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
        self.assertEqual(argv[0], "--no-config")
        self.assertEqual(argv[1:3], ["--cd", call["mise_cd"]])
        self.assertNotEqual(call["mise_cd"], str(self.target))
        self.assertTrue(str(call["mise_cd"]).startswith("/var/tmp/agentic-sdlc-seeds."))
        self.assertFalse(call["mise_cd_has_npmrc"])
        self.assertEqual(argv[3], "exec")
        self.assertEqual(argv[4:7], EXACT_RUNTIMES)
        self.assertEqual(argv[7], "--")
        self.assertEqual(argv[8:10], ["node", "-e"])
        self.assertIn("shell: false", argv[10])
        self.assertIn("spawn(", argv[10])
        self.assertNotIn("sh -c", argv[10])
        self.assertEqual(argv[11], str(self.target))

    def assert_neutral_npm_environment(self, call: dict[str, object]) -> None:
        self.assertEqual(
            call["npm_environment"],
            {
                "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
                "NPM_CONFIG_USERCONFIG": call["npm_environment"]["NPM_CONFIG_USERCONFIG"],
                "NPM_CONFIG_GLOBALCONFIG": call["npm_environment"]["NPM_CONFIG_GLOBALCONFIG"],
                "NPM_CONFIG_STRICT_SSL": "true",
            },
        )
        self.assertNotEqual(
            call["npm_environment"]["NPM_CONFIG_USERCONFIG"],
            call["npm_environment"]["NPM_CONFIG_GLOBALCONFIG"],
        )
        self.assertNotIn("TMPDIR", call["environment"])
        self.assertNotIn("TEMP", call["environment"])
        self.assertNotIn("TMP", call["environment"])
        for name in ("NPM_CONFIG_USERCONFIG", "NPM_CONFIG_GLOBALCONFIG"):
            self.assertEqual(call["npm_config_files"][name], {"exists": True, "contents": ""})

    def test_ambient_wrong_sd_is_ignored_and_exact_mise_seeds_is_required(self) -> None:
        result = self.run_preflight(github_required=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.ambient_log.exists(), "ambient sd must never execute")
        calls = self._mise_calls()
        self.assertGreaterEqual(len(calls), 2)
        exact_calls = [call for call in calls if "exec" in call["argv"]]
        self.assertEqual(len(exact_calls), 1)
        for call in exact_calls:
            self.assert_exact_contract(call)
            self.assert_neutral_npm_environment(call)
        self.assertIn("ok:       Seeds 0.5.15", result.stdout)

    def test_wrong_exact_version_fails_closed(self) -> None:
        result = self.run_preflight(github_required=False, mode="wrong-version")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Seeds version", result.stderr)

    def test_wrong_or_separator_ambiguous_provenance_fails_closed(self) -> None:
        result = self.run_preflight(github_required=False, mode="wrong-provenance")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Seeds version", result.stderr)

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
        exact_calls = [call for call in calls if "exec" in call["argv"]]
        self.assertEqual(len(exact_calls), 1)
        self.assert_exact_contract(exact_calls[0])
        self.assertEqual(exact_calls[0]["argv"][11:], [str(self.target), *arguments])
        self.assert_neutral_npm_environment(exact_calls[0])
        self.assertEqual(self._sd_calls(), [{"argv": arguments, "cwd": str(self.target)}])

    def test_relative_dot_target_keeps_target_cwd_and_neutral_acquisition(self) -> None:
        result = subprocess.run(
            [BASH, "-c", '. "$1"; agentic_sdlc_seeds . ready', "test-shell", str(SCRIPT)],
            cwd=self.target,
            env=self._environment(github_required=False),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self._mise_calls()
        exact_calls = [call for call in calls if "exec" in call["argv"]]
        self.assertEqual(len(exact_calls), 1)
        self.assertEqual(exact_calls[0]["argv"][:4], ["--no-config", "--cd", exact_calls[0]["mise_cd"], "exec"])
        self.assert_neutral_npm_environment(exact_calls[0])
        self.assertEqual(self._sd_calls(), [{"argv": ["ready"], "cwd": str(self.target)}])

    def test_cleanup_removes_neutral_state_after_exact_seeds_failure(self) -> None:
        environment = self._environment(github_required=False)
        self.fake_sd_status.write_text("23")
        result = subprocess.run(
            [BASH, "-c", '. "$1"; agentic_sdlc_seeds "$2" ready', "test-shell", str(SCRIPT), str(self.target)],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 23, result.stderr)
        calls = self._mise_calls()
        exact_call = next(call for call in calls if "exec" in call["argv"])
        self.assertFalse(Path(exact_call["mise_cd"]).exists())

    def test_local_git_run_does_not_require_gh(self) -> None:
        self._write_executable("gh", "#!/bin/sh\nexit 127\n")
        (self.bin_dir / "gh").unlink()
        result = self.run_preflight(github_required=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok:       Seeds 0.5.15", result.stdout)

    def test_selected_github_operation_requires_gh(self) -> None:
        env = self._environment(github_required=True)
        self._write_executable("gh", "#!/bin/sh\nexit 127\n")
        result = subprocess.run(
            [BASH, str(SCRIPT)], cwd=self.target, env=env, text=True,
            capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ok:       gh", result.stdout)


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

    def test_shipped_surface_scanner_rejects_quoted_authority_tokens_without_broadening_topics(self) -> None:
        quoted_mutations = (
            "Workers may 'create' Seeds issues.",
            "Workers may `claim` Seeds items.",
            "Workers may ‘update’ Seeds records.",
            "Workers may “close” Seeds states.",
            "Workers may sync `Seeds queues`.",
            "Workers may disposition ‘Seeds queue-states’.",
        )
        benign = (
            "The quoted topic verb `create` is Seeds terminology.",
            "The phrase ‘Seeds issues’ is a documentation topic.",
            "Workers must not 'create' Seeds issues.",
            "Workers never `claim` Seeds items.",
            "Workers cannot ‘update’ Seeds records.",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text("\n".join((*quoted_mutations, *benign)) + "\n", encoding="utf-8")

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            len(quoted_mutations),
            "\n".join(violations),
        )

    def test_shipped_surface_scanner_rejects_plural_seeds_authority_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Workers may create Seeds issues.",
                        "Workers may claim Seeds items.",
                        "Workers may update Seeds records.",
                        "Workers may close Seeds states.",
                        "Workers may sync Seeds queues.",
                        "Workers may update Seeds queue-states.",
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
                "agents/codex/worker-conductor.toml": 'name = "conductor"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
                "agents/codex/research/conductor.toml": 'name = "conductor"\ndeveloper_instructions = "Conductor-only authority may create a Seeds issue."\n',
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

    def test_modal_positive_operations_after_negation_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Workers must not init a Seeds queue, but may create a Seeds issue.",
                        "Workers never create a Seeds issue, and may claim a Seeds item.",
                        "Workers must not claim a Seeds item, but may update a Seeds record.",
                        "Workers should not update a Seeds record; may close a Seeds state.",
                        "Workers never close a Seeds state, and may sync a Seeds queue-state.",
                        "Workers may init a Seeds queue.",
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

    def test_sdlc_init_activation_guidance_remains_allowed(self) -> None:
        violations = shipped_surface_violations(ROOT)
        self.assertFalse(
            any(item.startswith("commands/sdlc-init.md:") for item in violations),
            "\n".join(violations),
        )

    def test_sdlc_loop_forbids_standalone_sync_reconciliation(self) -> None:
        loop = (
            ROOT / "skills" / "agentic-sdlc" / "references" / "sdlc-loop.md"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Seeds(<target>, sync)", loop)
        self.assertIn("Standalone sync", loop)
        self.assertIn("compare-and-swap launcher seam", loop)

    def test_bare_sd_invocations_reject_posix_mise_and_powershell_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            command = fixture_root / "commands" / "runbook.md"
            command.parent.mkdir(parents=True)
            command.write_text(
                "\n".join(
                    (
                        "/opt/seeds/bin/sd create",
                        "command /opt/seeds/bin/sd claim",
                        "exec ./tools/sd update",
                        "env MODE=test ./tools/sd close",
                        "mise exec node@22.23.2 -- sd sync",
                        "& sd.exe create",
                        r"& 'C:\\Seeds\\sd.cmd' claim",
                        "Start-Process sd.exe -ArgumentList update",
                        r"Start-Process -FilePath 'C:\\Seeds\\sd.bat' -ArgumentList 'close'",
                        "Start-Process sd.exe -ArgumentList @('update')",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations),
            10,
            "\n".join(violations),
        )

    def test_bare_sd_invocations_reject_quoted_and_static_powershell_wrappers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            command = fixture_root / "commands" / "runbook.md"
            command.parent.mkdir(parents=True)
            command.write_text(
                "\n".join(
                    (
                        'mise exec -- "sd" "create"',
                        "mise exec -- 'sd' 'claim'",
                        r"& 'C:\\Seeds\\sd.exe' 'update'",
                        r"$seed_command = 'C:\\Seeds\\sd.exe'",
                        "$seed_action = 'close'",
                        "& $seed_command $seed_action",
                        "& $seed_command 'disposition'",
                        "$sync_action = 'sync'",
                        "Start-Process -FilePath $seed_command -ArgumentList $sync_action",
                        "Start-Process -FilePath $seed_command -ArgumentList 'init'",
                        "$start_action = 'create'",
                        "Start-Process -FilePath $seed_command -ArgumentList $start_action",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations),
            8,
            "\n".join(violations),
        )

    def test_bare_sd_invocations_reject_asymmetrically_quoted_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            command = fixture_root / "commands" / "runbook.md"
            command.parent.mkdir(parents=True)
            command.write_text(
                "\n".join(
                    (
                        'sd "create"',
                        "/opt/seeds/bin/sd 'claim'",
                        'mise exec -- sd "sync"',
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations),
            3,
            "\n".join(violations),
        )

    def test_python_scanner_rejects_safe_subprocess_argument_lists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            script = fixture_root / "skills" / "example" / "scripts" / "worker.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "\n".join(
                    (
                        "import subprocess",
                        'COMMAND = "sd"',
                        'ACTION = "close"',
                        'subprocess.run(["sd", "create"])',
                        'subprocess.check_call(("/opt/seeds/bin/sd", "claim"))',
                        "subprocess.Popen(args=[COMMAND, ACTION])",
                        'subprocess.run(["mise", "exec", "--", "sd", "sync"])',
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("bare operational sd invocation" in item for item in violations),
            4,
            "\n".join(violations),
        )

    def test_python_scanner_does_not_follow_recursive_build_files_helpers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            script = fixture_root / "skills" / "example" / "scripts" / "render.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "\n".join(
                    (
                        "def helper(project_name):",
                        "    return helper(project_name)",
                        "def build_files(project_name):",
                        "    return helper(project_name)",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertFalse(violations, "\n".join(violations))

    def test_python_scanner_reconstructs_static_build_files_helpers_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            script = fixture_root / "skills" / "example" / "scripts" / "render.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                "\n".join(
                    (
                        'PREFIX = "Workers may "',
                        'ACTION = "create"',
                        'OBJECT = " a Seeds issue "',
                        "def helper(project_name):",
                        "    return {'generated.md': PREFIX + ACTION + OBJECT + project_name}",
                        "def build_files(project_name):",
                        "    return helper(project_name)",
                        "def untrusted_dynamic_code():",
                        "    raise RuntimeError('scanner must not execute generated code')",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            1,
            "\n".join(violations),
        )

    def test_pseudo_operation_negations_cover_call_use_and_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Workers do not call Seeds(target, create).",
                        "Workers never use Seeds(<target>, claim).",
                        "Workers must not execute Seeds(repo.name, update).",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertFalse(violations, "\n".join(violations))

    def test_pseudo_operation_negations_cover_call_use_execute_and_inline_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Workers should not call `Seeds(target, create)`.",
                        "Workers should not use `Seeds(<target>, claim)`.",
                        "Workers should not execute `Seeds(repo.name, update)`.",
                        "Workers never invoke `Seeds(target, close)`.",
                        "Workers may invoke `Seeds(target, sync)`.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            1,
            "\n".join(violations),
        )

    def test_python_scanner_reconstructs_safe_constant_expressions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            script = fixture_root / "skills" / "example" / "scripts" / "render.py"
            script.parent.mkdir(parents=True)
            script.write_text(
                'PREFIX = "Workers may "\nGUIDANCE = PREFIX + "create a Seeds issue."\n',
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            1,
            "\n".join(violations),
        )

    def test_python_scanner_checks_every_rendered_build_files_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            installer = (
                fixture_root
                / "skills"
                / "codex-research-os"
                / "scripts"
                / "install_research_os.py"
            )
            installer.parent.mkdir(parents=True)
            installer.write_text(
                "def build_files(project_name):\n"
                "    return {'generated.md': f'Workers may create a Seeds issue {project_name}.'}\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            1,
            "\n".join(violations),
        )

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

    def test_static_authority_prose_is_rejected_without_broad_copular_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Seeds queue sync semantics are that workers are authorized.",
                        "Seeds queue claim lifecycle is owned by workers.",
                        "Seeds queue create terminology grants workers permission.",
                        "Seeds queue create terminology grants workers access.",
                        "Seeds queue create permission is granted to workers.",
                        "Seeds queue claim authorization is granted to workers.",
                        "Seeds queue sync access is allowed to workers.",
                        "Seeds queue create command is available to workers.",
                        "Seeds queue claim execution is allowed for workers.",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            9,
            "\n".join(violations),
        )

    def test_exact_neutral_descriptive_grammar_preserves_provider_neutral_terminal_predicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join(
                    (
                        "Seeds queue sync semantics are provider-neutral.",
                        "Seeds queue claim lifecycle is provider-neutral!",
                        "Seeds queue create terminology is provider-neutral?",
                    )
                )
                + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        self.assertFalse(violations, "\n".join(violations))

    def test_neutral_descriptive_exemption_requires_exact_terminal_is_or_are_forms(self) -> None:
        exempt = (
            "Seeds queue sync semantics are provider-neutral.",
            "Seeds queue sync semantics is provider-neutral.",
        )
        non_exempt = {
            "Seeds queue sync semantics was provider-neutral.": ["sync"],
            "Seeds queue sync semantics were provider-neutral.": ["sync"],
            "Seeds queue sync semantics be provider-neutral.": ["sync"],
            "Seeds queue sync semantics been provider-neutral.": ["sync"],
            "Seeds queue sync semantics being provider-neutral.": ["sync"],
            "Seeds queue sync semantics are provider-neutral but workers are authorized.": ["sync"],
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            worker = fixture_root / "agents" / "codex" / "worker.toml"
            worker.parent.mkdir(parents=True)
            worker.write_text(
                "\n".join((*exempt, *non_exempt)) + "\n",
                encoding="utf-8",
            )

            violations = shipped_surface_violations(fixture_root)

        for sentence in exempt:
            with self.subTest(sentence=sentence):
                self.assertEqual(seeds_mutation_operations(sentence), [])
        for sentence, operations in non_exempt.items():
            with self.subTest(sentence=sentence):
                self.assertEqual(seeds_mutation_operations(sentence), operations)
        self.assertEqual(
            sum("direct non-conductor Seeds queue mutation guidance" in item for item in violations),
            len(non_exempt),
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
                        "Seeds queue sync semantics are provider-neutral.",
                        "Seeds queue claim lifecycle is provider-neutral.",
                        "Seeds queue sync terminology is provider-neutral.",
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

    def test_docs_define_locked_receipt_and_process_scoped_contract(self) -> None:
        skill = (ROOT / "skills" / "agentic-sdlc" / "SKILL.md").read_text()
        reference = (
            ROOT
            / "skills"
            / "agentic-sdlc"
            / "references"
            / "seeds-worktrees.md"
        ).read_text()
        # These assertions pin DOCTRINE PHRASES, not layout. Matching raw text made a line
        # rewrap look like a doctrine deletion: a prose pass split "same-UID TOCTOU" across a
        # newline and the gate went red while the claim was still fully present. Collapsing
        # whitespace keeps the pin on the words, which is the thing worth defending.
        skill = " ".join(skill.split())
        reference = " ".join(reference.split())
        for content in (skill, reference):
            self.assertIn("mise --locked install", content)
            self.assertIn("same-UID TOCTOU", content)
            self.assertIn("exact clean Git", content)
            self.assertIn("engines.bun", content)
            self.assertIn("--no-env-file", content)
            self.assertIn("--no-install", content)
            self.assertIn("shell:false", content)
            self.assertNotIn("sh -c", content)

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
