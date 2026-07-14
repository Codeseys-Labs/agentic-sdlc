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
    "research-os:install",
    "test",
    "self-test",
    "check",
    "hooks:install",
    "setup",
}
MIN_MISE_VERSION = "2026.4.27"
UV_VERSION = "0.11.17"
PYTHON_VERSION = "3.12.11"
LEFTHOOK_VERSION = "2.1.10"
NODE_VERSION = "22.22.3"
BUN_VERSION = "1.3.10"
SEEDS_VERSION = "0.5.14"
SEEDS_TOOL = "npm:@os-eco/seeds-cli"
LOCK_ARTIFACTS = {
    "uv": {
        "backend": "aqua:astral-sh/uv",
        "platforms": {
            "linux-x64": ("https://github.com/astral-sh/uv/releases/download/0.11.17/uv-x86_64-unknown-linux-musl.tar.gz", "4231a429d4e0f7c1937d8916658c08a7706cd7872afebeb87203a18c2e0dc28e", "github-attestations"),
            "macos-arm64": ("https://github.com/astral-sh/uv/releases/download/0.11.17/uv-aarch64-apple-darwin.tar.gz", "2a162f6b90ff3691a2f9cae1622e066a3ce592e110f66670cdcc841324b28226", "github-attestations"),
            "macos-x64": ("https://github.com/astral-sh/uv/releases/download/0.11.17/uv-x86_64-apple-darwin.tar.gz", "6c66e41eaf4d15abeda58d3f268161b6e3f742d98390341b174a7cfc1b48841d", "github-attestations"),
            "windows-x64": ("https://github.com/astral-sh/uv/releases/download/0.11.17/uv-x86_64-pc-windows-msvc.zip", "35fc29e03e62f3cda769bc12773f3cb70ce305d0d36c0d8bd0c117dd0b3fcd14", "github-attestations"),
        },
    },
    "lefthook": {
        "backend": "aqua:evilmartians/lefthook",
        "platforms": {
            "linux-x64": ("https://github.com/evilmartians/lefthook/releases/download/v2.1.10/lefthook_2.1.10_Linux_x86_64.gz", "0b14162a0bb2f0c64ae0759f6102f6e19c4d00981666a8ac73d4f5a6878ada4f", "github-attestations"),
            "macos-arm64": ("https://github.com/evilmartians/lefthook/releases/download/v2.1.10/lefthook_2.1.10_MacOS_arm64.gz", "1dd4dc7b4c50efb1f9d9122cd6535c793738d6e59751c228d49f768ec9dbb604", "github-attestations"),
            "macos-x64": ("https://github.com/evilmartians/lefthook/releases/download/v2.1.10/lefthook_2.1.10_MacOS_x86_64.gz", "49d905f28ca46442cb236060058b252da650b5f7b864bd275b61aa46945e8c4a", "github-attestations"),
            "windows-x64": ("https://github.com/evilmartians/lefthook/releases/download/v2.1.10/lefthook_2.1.10_Windows_x86_64.gz", "beabbce824641ae71229ed11dd8634f47148921cb649d25c90441b737481494a", "github-attestations"),
        },
    },
    "node": {
        "backend": "core:node",
        "platforms": {
            "linux-x64": ("https://nodejs.org/dist/v22.22.3/node-v22.22.3-linux-x64.tar.gz", "c7a10d6816da8eaaa7534dd73c71c6e2b2c391dbbf845e364902d156615dd1b8", None),
            "macos-arm64": ("https://nodejs.org/dist/v22.22.3/node-v22.22.3-darwin-arm64.tar.gz", "0da7ff74ef8611328c8212f17943368713a2ad953fb7d89a8c8a0eae87c23207", None),
            "macos-x64": ("https://nodejs.org/dist/v22.22.3/node-v22.22.3-darwin-x64.tar.gz", "45830ba752fa0d892c6dcd640946669801293cac820a33591ded40ac075198ec", None),
            "windows-x64": ("https://nodejs.org/dist/v22.22.3/node-v22.22.3-win-x64.zip", "6c8d54f635feff4df76c2ca80f45332eb2ff57d25226edce36592e51a177ee33", None),
        },
    },
    "bun": {
        "backend": "core:bun",
        "platforms": {
            "linux-x64": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-linux-x64.zip", "f57bc0187e39623de716ba3a389fda5486b2d7be7131a980ba54dc7b733d2e08", None),
            "linux-x64-baseline": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-linux-x64-baseline.zip", "41201a8c5ee74a9dcbb1ce25a1104f1f929838b57a845aa78d98379b0ce7cde2", None),
            "linux-x64-musl": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-linux-x64-musl.zip", "48a6c32277d343db0148ce066336472ffd380358a4d26bb1329714742492d824", None),
            "linux-x64-musl-baseline": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-linux-x64-musl-baseline.zip", "a7bc4cdea1ef255a83adbf39c7aafcd30e09f2b8f74deec4b10ee318bc024d1f", None),
            "macos-arm64": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-darwin-aarch64.zip", "82034e87c9d9b4398ea619aee2eed5d2a68c8157e9a6ae2d1052d84d533ccd8d", None),
            "macos-x64": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-darwin-x64.zip", "c1d90bf6140f20e572c473065dc6b37a4b036349b5e9e4133779cc642ad94323", None),
            "macos-x64-baseline": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-darwin-x64-baseline.zip", "f9686c4e4e760db4cde77a0f1fad05e552648b9c9cbfa4f7fc9a7ec26b9f3267", None),
            "windows-x64": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-windows-x64.zip", "7a77b3e245e2e26965c93089a4a1332e8a326d3364c89fae1d1fd99cdd3cd73d", None),
            "windows-x64-baseline": ("https://github.com/oven-sh/bun/releases/download/bun-v1.3.10/bun-windows-x64-baseline.zip", "715709c69b176e20994533d3292bd0b7c32de9c0c5575b916746ec6b2aa38346", None),
        },
    },
}
TASK_COMMANDS = {
    "validate": "--script scripts/validate_bundle.py",
    "bundle:install": "--script scripts/install_skill_bundle.py install",
    "bundle:status": "--script scripts/install_skill_bundle.py status",
    "bundle:uninstall": "--script scripts/install_skill_bundle.py uninstall",
    "bundle:install:claude": "--script scripts/install_skill_bundle.py install --agent claude",
    "bundle:install:codex": "--script scripts/install_skill_bundle.py install --agent codex",
    "bundle:install:all-hosts": "--script scripts/run_all_hosts.py install",
    "bundle:status:all-hosts": "--script scripts/run_all_hosts.py status",
    "research-os:install": "--script skills/codex-research-os/scripts/install_research_os.py",
    "test": "python -m unittest discover -s tests",
    "self-test": "--script scripts/install_skill_bundle.py self-test",
}
VALIDATOR_WRAPPER = """#!/usr/bin/env bash
# Compatibility entrypoint; the authoritative task is `mise run validate`.
set -euo pipefail
root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec mise -C "$root" exec -- uv run --python 3.12.11 --script scripts/validate_bundle.py "$@"
"""
BUMP_PREFIX = """#!/bin/bash
# Bump every version-carrying manifest in one shot (targets declared in .version-bump.json).
#   bump-version.sh <new-version>   # write all targets + update .version-bump.json current
#   bump-version.sh --check         # exit 1 if any target disagrees with current
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$repo_root/.version-bump.json"

command -v mise >/dev/null 2>&1 || {
  echo "error: mise 2026.4.27+ is required to update version manifests" >&2
  exit 2
}

mise -C "$repo_root" exec -- uv run --python 3.12.11 python - "$manifest" "$repo_root" "${1:-}" <<'PY'
"""
EXPECTED_WORKFLOW = """name: validate-bundle

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    name: mise check (${{ matrix.os }})
    strategy:
      fail-fast: false
      matrix:
        os:
          - blacksmith-2vcpu-ubuntu-2404
          - blacksmith-6vcpu-macos-latest
          - blacksmith-2vcpu-windows-2025
    runs-on: ${{ matrix.os }}
    steps:
      # actions/checkout v4.3.1
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
      # jdx/mise-action v2.4.7
      - uses: jdx/mise-action@c37c93293d6b742fc901e1406b8f764f6fb19dac
        with:
          install: true
      - name: Run authoritative check
        run: mise run check
"""


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
    if value not in {"|", ">", "|-", ">-"} and not re.fullmatch(r"[|>](?:[+-]?[1-9]|[1-9][+-]?)", value):
        return value
    continuation: list[str] = []
    lines = metadata[match.end() :].splitlines()
    if lines and not lines[0]:
        lines = lines[1:]
    for line in lines:
        if not line.strip():
            continuation.append("")
            continue
        if not line.startswith((" ", "\t")):
            break
        continuation.append(line.strip())
    return " ".join(continuation).strip()


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
        config = tomllib.loads(path.read_text(encoding="utf-8"))
        tasks = config.get("tasks", {})
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.toml is invalid: {exc}")
        return
    for task in sorted(REQUIRED_TASKS - set(tasks)):
        result.error(f"mise.toml missing task {task}")

    if config.get("min_version") != MIN_MISE_VERSION:
        result.error(f"mise.toml must require mise {MIN_MISE_VERSION}")
    settings = config.get("settings", {})
    if settings.get("locked") is not True:
        result.error("mise.toml must enable locked tool resolution")
    if settings.get("npm", {}).get("package_manager") != "npm":
        result.error("mise.toml npm.package_manager must equal npm")
    expected_tools = {
        "uv": UV_VERSION,
        "lefthook": LEFTHOOK_VERSION,
        "node": NODE_VERSION,
        "bun": BUN_VERSION,
        SEEDS_TOOL: {"version": SEEDS_VERSION, "depends": ["node"]},
    }
    if config.get("tools") != expected_tools:
        result.error(f"mise.toml tools must equal {expected_tools}")
    seeds = config.get("tools", {}).get(SEEDS_TOOL, {})
    if seeds.get("depends") != ["node"]:
        result.error("mise.toml Seeds tool must depend on node")

    for name, suffix in TASK_COMMANDS.items():
        task = tasks.get(name, {})
        windows_suffix = suffix
        if name == "bundle:install:all-hosts":
            windows_suffix = "--script scripts/install_skill_bundle.py install"
        elif name == "bundle:status:all-hosts":
            windows_suffix = "--script scripts/install_skill_bundle.py status"
        for field, executable, command_suffix in (
            ("run", "uv", suffix),
            ("run_windows", "uv.exe", windows_suffix),
        ):
            expected = f"{executable} run --python {PYTHON_VERSION} {command_suffix}"
            if task.get(field) != expected:
                result.error(f"mise.toml task {name}.{field} must equal {expected!r}")
    expected_check = {
        "description": "Run validation, installer tests, and lifecycle self-test",
        "depends": ["validate", "test", "self-test"],
    }
    if tasks.get("check") != expected_check:
        result.error("mise.toml check must contain only its description and exact validate/test/self-test dependencies")

    lock_path = root / "mise.lock"
    if not lock_path.is_file():
        result.error("mise.lock is required")
        return
    try:
        lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.error(f"mise.lock is invalid: {exc}")
        return
    locked_tools = lock.get("tools", {})
    expected_versions = {
        "uv": UV_VERSION,
        "lefthook": LEFTHOOK_VERSION,
        "node": NODE_VERSION,
        "bun": BUN_VERSION,
        SEEDS_TOOL: SEEDS_VERSION,
    }
    for name, version in expected_versions.items():
        entries = locked_tools.get(name, [])
        if len(entries) != 1 or entries[0].get("version") != version:
            result.error(f"mise.lock must resolve {name} {version}")
            continue
        entry = entries[0]
        if name == SEEDS_TOOL:
            if entry.get("backend") != SEEDS_TOOL:
                result.error(f"mise.lock {name} backend must equal {SEEDS_TOOL}")
            if set(entry) != {"version", "backend"}:
                result.error(f"mise.lock {name} must contain version and backend only")
            continue

        expected_lock = LOCK_ARTIFACTS[name]
        if entry.get("backend") != expected_lock["backend"]:
            result.error(f"mise.lock {name} backend must equal {expected_lock['backend']}")
        platforms = {
            key.removeprefix("platforms."): value
            for key, value in entry.items()
            if key.startswith("platforms.")
        }
        expected_platforms = expected_lock["platforms"]
        if set(platforms) != set(expected_platforms):
            result.error(f"mise.lock {name} platforms must equal {sorted(expected_platforms)}")
        for platform, record in platforms.items():
            expected_record = expected_platforms.get(platform)
            if expected_record is None:
                continue
            expected_url, checksum, provenance = expected_record
            if record.get("url") != expected_url:
                result.error(f"mise.lock {name} {platform} URL must equal {expected_url}")
            if record.get("checksum") != f"sha256:{checksum}":
                result.error(f"mise.lock {name} {platform} checksum must equal the generated lock")
            expected_fields = {"checksum", "url"}
            if provenance is not None:
                expected_fields.add("provenance")
                if record.get("provenance") != provenance:
                    result.error(f"mise.lock {name} {platform} provenance must equal {provenance}")
            if set(record) != expected_fields:
                result.error(f"mise.lock {name} {platform} must contain only generated artifact metadata")


def validate_gate_graph(root: Path, result: Validation) -> None:
    wrapper = root / "scripts" / "validate-bundle.sh"
    if not wrapper.is_file() or wrapper.read_text(encoding="utf-8") != VALIDATOR_WRAPPER:
        result.error("scripts/validate-bundle.sh must be the exec-only pinned mise/uv wrapper")

    bump = root / "scripts" / "bump-version.sh"
    if not bump.is_file():
        result.error("scripts/bump-version.sh is required")
    else:
        bump_text = bump.read_text(encoding="utf-8")
        if not bump_text.startswith(BUMP_PREFIX) or not bump_text.endswith("\nPY\n"):
            result.error("scripts/bump-version.sh must use only the pinned mise/uv Python launcher")
        heredoc_end = bump_text.rfind("\nPY\n")
        if heredoc_end != len(bump_text) - 4:
            result.error("scripts/bump-version.sh must end at the pinned Python heredoc")

    hooks = root / "lefthook.yml"
    expected_hooks = """pre-commit:
  commands:
    validate:
      run: mise run validate

pre-push:
  commands:
    test:
      run: mise run test
    self-test:
      run: mise run self-test
"""
    if not hooks.is_file() or hooks.read_text(encoding="utf-8") != expected_hooks:
        result.error("lefthook.yml must contain the documented best-effort gate subsets")

    workflow = root / ".github" / "workflows" / "validate.yml"
    if not workflow.is_file():
        result.error(".github/workflows/validate.yml is required")
    else:
        workflow_text = workflow.read_text(encoding="utf-8")
        if workflow_text != EXPECTED_WORKFLOW:
            result.error("CI workflow must equal the single authoritative mise run check graph")

    claude = root / "CLAUDE.md"
    if not claude.is_file() or not claude.read_text(encoding="utf-8").startswith("@AGENTS.md\n"):
        result.error("CLAUDE.md must begin with @AGENTS.md")


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
    validate_gate_graph(root, result)
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
