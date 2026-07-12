#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate Agentic SDLC bundle metadata and lifecycle contracts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


SECRET_PATTERN = re.compile(
    r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA|OPENSSH) PRIVATE KEY|amazon\.com/[a-z]|\.a2z\.com|aws\.dev/"
)
TEXT_SUFFIXES = {".md", ".sh", ".ps1", ".toml", ".json", ".yml", ".yaml", ".py"}
REQUIRED_TASKS = {
    "bundle:install",
    "bundle:status",
    "bundle:uninstall",
    "bundle:install:claude",
    "bundle:install:codex",
    "bundle:install:all-hosts",
    "bundle:status:all-hosts",
    "test",
    "self-test",
    "check",
    "hooks:install",
    "setup",
}


class Validation:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)


def frontmatter(text: str) -> str:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    return match.group(1) if match else ""


def metadata_value(metadata: str, name: str) -> str:
    match = re.search(rf"^{re.escape(name)}:\s*(.*)$", metadata, re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    if value not in {"|", ">", "|-", ">-"}:
        return value
    continuation = metadata[match.end() :].splitlines()
    return " ".join(line.strip() for line in continuation if line.startswith("  ")).strip()


def validate_skills(root: Path, result: Validation) -> None:
    for skill in sorted((root / "skills").glob("*/SKILL.md")):
        directory = skill.parent.name
        text = skill.read_text(encoding="utf-8")
        metadata = frontmatter(text)
        if metadata_value(metadata, "name") != directory:
            result.error(f"{directory}: name does not match directory")
        description = metadata_value(metadata, "description")
        if not description:
            result.error(f"{directory}: missing description")
        elif len(description) > 1024:
            result.error(f"{directory}: description exceeds 1024 characters")
        for reference in sorted(set(re.findall(r"\breferences/[A-Za-z0-9._-]+\.md", text))):
            if not (skill.parent / reference).is_file():
                result.error(f"{directory}: missing {reference}")


def validate_python(root: Path, result: Validation) -> None:
    installer = root / "scripts" / "install_skill_bundle.py"
    if not installer.is_file():
        result.error("scripts/install_skill_bundle.py is required")
    for source in root.rglob("*.py"):
        if ".git" in source.parts or "__pycache__" in source.parts:
            continue
        try:
            compile(source.read_text(encoding="utf-8"), str(source), "exec")
        except (OSError, SyntaxError, UnicodeError) as exc:
            result.error(f"Python source failed to compile: {source.relative_to(root)}: {exc}")
    if shutil.which("git"):
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "*.pyc"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        if tracked:
            result.error("Python bytecode must not be committed")


def validate_agents(root: Path, result: Validation) -> None:
    for agent in sorted((root / "agents" / "claude").glob("*.md")):
        text = agent.read_text(encoding="utf-8")
        if not re.search(r"^name:", text, re.MULTILINE):
            result.error(f"{agent}: missing name")
        if not re.search(r"^description:", text, re.MULTILINE):
            result.error(f"{agent}: missing description")
    for agent in sorted((root / "agents" / "codex").glob("**/*.toml")):
        try:
            data = tomllib.loads(agent.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            result.error(f"{agent}: invalid TOML: {exc}")
            continue
        if not data.get("name") or not data.get("description"):
            result.error(f"{agent}: missing metadata")


def validate_mise(root: Path, result: Validation) -> None:
    path = root / "mise.toml"
    if not path.is_file():
        result.error("mise.toml is required")
        return
    try:
        tasks = tomllib.loads(path.read_text(encoding="utf-8")).get("tasks", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.toml is invalid: {exc}")
        return
    for task in sorted(REQUIRED_TASKS - set(tasks)):
        result.error(f"mise.toml missing task {task}")


def validate_versions(root: Path, result: Validation) -> None:
    manifest_path = root / ".version-bump.json"
    if not manifest_path.is_file():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = manifest["current"]
        targets = manifest["targets"]
        for target in targets:
            value: object = json.loads((root / target["file"]).read_text(encoding="utf-8"))
            for key in (part for part in target["jq"].strip(".").split(".") if part):
                value = value[int(key)] if key.isdigit() else value[key]  # type: ignore[index]
            if value != expected:
                result.error(f"version drift: {target['file']} {target['jq']} = {value} (expect {expected})")
    except (KeyError, IndexError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result.error(f"invalid version manifest contract: {exc}")


def validate_scripts(root: Path, result: Validation) -> None:
    bash = shutil.which("bash") if sys.platform != "win32" else None
    if bash:
        for script in sorted((root / "scripts").glob("*.sh")):
            completed = subprocess.run([bash, "-n", str(script)], check=False, capture_output=True, text=True)
            if completed.returncode:
                result.error(f"{script} does not parse: {completed.stderr.strip()}")

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    if powershell:
        for script in sorted((root / "scripts").glob("*.ps1")):
            escaped = str(script).replace("'", "''")
            command = f"[System.Management.Automation.Language.Parser]::ParseFile('{escaped}',[ref]$null,[ref]$null)"
            completed = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode:
                result.error(f"{script} does not parse: {completed.stderr.strip()}")


def validate_manifests(root: Path, result: Validation) -> None:
    manifests = (
        ".claude-plugin/plugin.json",
        ".claude-plugin/marketplace.json",
        ".codex-plugin/plugin.json",
        ".agents/plugins/marketplace.json",
        "gemini-extension.json",
    )
    for name in manifests:
        path = root / name
        if not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            result.error(f"invalid JSON: {name}: {exc}")


def validate_cao_retirement(root: Path, result: Validation) -> None:
    message = "CAO has been retired; use native Frame/Wave/Mission instead.\n"
    expected_profile_names = {
        "claude-ultracode-workflow.md",
        "codex-implementer.md",
        "codex-macro-orchestrator.md",
        "codex-planner.md",
        "codex-reviewer.md",
    }
    profiles_dir = root / "cao-profiles"
    actual_profile_names = {
        path.name for path in profiles_dir.iterdir() if path.is_file()
    } if profiles_dir.is_dir() else set()
    if actual_profile_names != expected_profile_names:
        result.error(
            "CAO profile tombstone inventory mismatch: "
            f"expected {sorted(expected_profile_names)}, got {sorted(actual_profile_names)}"
        )

    expected_cao_named_files = {
        root / "scripts" / "install-cao-kit.sh",
        root / "skills" / "agentic-sdlc-orchestrator" / "references" / "cao-profiles.md",
        root / "skills" / "agentic-sdlc-orchestrator" / "references" / "cao-operations.md",
        *(profiles_dir / name for name in sorted(expected_profile_names)),
    }
    actual_cao_named_files = {
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "tests" not in path.relative_to(root).parts
        and (
            "cao" in path.name.lower()
            or "cao-profiles" in path.relative_to(root).parts
        )
    }
    if actual_cao_named_files != expected_cao_named_files:
        result.error(
            "CAO named-file inventory mismatch: "
            f"expected {sorted(str(path.relative_to(root)) for path in expected_cao_named_files)}, "
            f"got {sorted(str(path.relative_to(root)) for path in actual_cao_named_files)}"
        )

    tombstone_files = expected_cao_named_files
    script = root / "scripts" / "install-cao-kit.sh"
    if not script.is_file() or script.read_text(encoding="utf-8") != "#!/usr/bin/env bash\nset -euo pipefail\n\nprintf '%s\\n' '" + message.rstrip() + "' >&2\nexit 2\n":
        result.error(f"CAO retirement tombstone mismatch: {script.relative_to(root)}")
    for path in sorted(tombstone_files - {script}):
        if not path.is_file() or path.read_text(encoding="utf-8") != message:
            result.error(f"CAO retirement tombstone mismatch: {path.relative_to(root)}")

    wrapper = root / "scripts" / "install-skill-bundle.sh"
    if not wrapper.is_file():
        result.error(f"CAO retirement wrapper missing: {wrapper.relative_to(root)}")
    else:
        wrapper_text = wrapper.read_text(encoding="utf-8")
        guard = "if [ \"${INSTALL_CAO:-0}\" = \"1\" ]; then\n  printf '%s\\n' \"$retirement_message\" >&2\n  exit 2\nfi"
        if guard not in wrapper_text:
            result.error("CAO retirement wrapper must guard before native installer work")

    active_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and "tests" not in path.relative_to(root).parts
        and path not in tombstone_files
        and path != root / "scripts" / "validate_bundle.py"
    ]
    forbidden_command = re.compile(r"\b(?:cao|cao-server)\s+[a-z][a-z0-9_-]*\b")
    forbidden_install_flag = "INSTALL_CAO=1"
    wrapper_path = root / "scripts" / "install-skill-bundle.sh"
    allowed_install_flag_lines = {
        root / "README.md": {
            "`INSTALL_CAO=1` is a retired compatibility path and exits 2 before native installation."
        },
        root / "AGENTS.md": {
            "positional `status`, `uninstall`, `self-test`, legacy `--copy`, and retired `INSTALL_CAO=1`"
        },
    }
    for path in sorted(active_files):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if forbidden_command.search(text):
            result.error(f"active CAO command or claim remains: {path.relative_to(root)}")
        if path != wrapper_path:
            allowed_lines = allowed_install_flag_lines.get(path, set())
            if any(
                forbidden_install_flag in line and line.strip() not in allowed_lines
                for line in text.splitlines()
            ):
                result.error(f"active INSTALL_CAO invocation remains: {path.relative_to(root)}")


def validate_policy(root: Path, result: Validation) -> None:
    validate_cao_retirement(root, result)
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or ".git" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if path.name != "validate_bundle.py" and SECRET_PATTERN.search(text):
            result.error(f"possible secret or internal hostname found: {path.relative_to(root)}")


def validate(root: Path) -> Validation:
    result = Validation()
    validate_skills(root, result)
    validate_python(root, result)
    validate_agents(root, result)
    validate_mise(root, result)
    validate_versions(root, result)
    validate_scripts(root, result)
    validate_manifests(root, result)
    validate_policy(root, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = validate(args.root.resolve())
    for warning in result.warnings:
        print(f"warn:  {warning}")
    for error in result.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"\nvalidate-bundle: {len(result.errors)} error(s), {len(result.warnings)} warning(s)")
    return 1 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
