#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install the Agentic SDLC skill bundle safely into Claude and Codex homes."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from typing import Any


STATE_VERSION = 1


class InstallerError(RuntimeError):
    """Raised for errors that make an installer command fatal."""


class SingleAgentAction(argparse.Action):
    """Reject duplicate selectors so fixed mise tasks cannot be overridden."""

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, value: str, option_string: str | None = None) -> None:
        if getattr(namespace, self.dest, None) is not None:
            parser.error(f"{option_string} may be specified only once")
        setattr(namespace, self.dest, value)


@dataclass(frozen=True)
class Entry:
    agent: str
    kind: str
    name: str
    source: Path


@dataclass(frozen=True)
class Config:
    repo_root: Path
    home: Path
    codex_home: Path
    mode: str
    dry_run: bool
    agent: str
    state_root: Path | None = None

    @property
    def state_path(self) -> Path:
        root = self.state_root or state_directory(self.home)
        return root / "agentic-sdlc-installer" / "state.json"


@dataclass(frozen=True)
class Result:
    exit_code: int
    messages: tuple[str, ...]


def platform_system() -> str:
    """Return the host system; a small seam for platform-selection tests."""
    return platform.system()


def state_directory(home: Path) -> Path:
    """Return a user-local state root without creating it."""
    if platform_system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data and home.resolve() == Path.home().resolve():
            return Path(local_app_data)
        return home / "AppData" / "Local"
    xdg_state = os.environ.get("XDG_STATE_HOME")
    return Path(xdg_state) if xdg_state else home / ".local" / "state"


def load_state(path: Path) -> dict[str, Any]:
    """Read and validate installer ownership state, returning an empty state initially."""
    if not path.exists():
        return {"version": STATE_VERSION, "entries": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read state {path}: {exc}") from exc
    if not isinstance(state, dict) or state.get("version") != STATE_VERSION:
        raise InstallerError(f"invalid state {path}")
    entries = state.get("entries")
    if not isinstance(entries, dict) or not all(isinstance(key, str) and isinstance(value, dict) for key, value in entries.items()):
        raise InstallerError(f"invalid state {path}")
    return state


def destination_is_configured(key: str, record: dict[str, Any], config: Config) -> bool:
    """Return whether a record targets the currently configured agent home."""
    name = record.get("name", Path(key).name)
    entry = Entry(record["agent"], record["kind"], name, Path(record["source"]))
    expected = destination_for(entry, config)
    return os.path.normcase(os.path.abspath(key)) == os.path.normcase(os.path.abspath(expected))


def validate_owned_entries(config: Config, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reject malformed records while preserving entries from previously configured homes."""
    entries = state["entries"]
    for key, record in entries.items():
        agent = record.get("agent")
        kind = record.get("kind")
        name = record.get("name", Path(key).name)
        identity_valid = (
            agent in {"claude", "codex"}
            and kind in {"skill", "agent", "command"}
            and not (agent == "codex" and kind == "command")
            and isinstance(name, str)
            and name not in {"", ".", ".."}
            and Path(name).name == name
        )
        collection = {"skill": "skills", "agent": "agents", "command": "commands"}.get(kind)
        destination = Path(key)
        destination_valid = (
            identity_valid
            and destination.name == name
            and destination.parent.name == collection
            and (agent == "codex" or destination.parent.parent.name == ".claude")
        )
        valid = (
            destination_valid
            and record.get("mode") in {"copy", "link", "junction"}
            and isinstance(record.get("source"), str)
            and bool(record["source"])
            and isinstance(record.get("digest"), str)
            and len(record["digest"]) == 64
            and isinstance(record.get("removable", True), bool)
        )
        if not valid:
            raise InstallerError(f"invalid ownership record for {key}")
    return entries


def write_state(path: Path, state: dict[str, Any], dry_run: bool) -> None:
    """Atomically replace the state file, unless dry-run was requested."""
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".state-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def discover_entries(repo_root: Path) -> list[Entry]:
    """Discover every supported top-level bundle payload in a stable order."""
    entries: list[Entry] = []
    for skill_file in sorted((repo_root / "skills").glob("*/SKILL.md")):
        entries.extend(
            (
                Entry("claude", "skill", skill_file.parent.name, skill_file.parent),
                Entry("codex", "skill", skill_file.parent.name, skill_file.parent),
            )
        )
    for source in sorted((repo_root / "agents" / "claude").glob("*.md")):
        entries.append(Entry("claude", "agent", source.name, source))
    for source in sorted((repo_root / "commands").glob("*.md")):
        entries.append(Entry("claude", "command", source.name, source))
    for source in sorted((repo_root / "agents" / "codex").glob("*.toml")):
        entries.append(Entry("codex", "agent", source.name, source))
    return entries


def destination_for(entry: Entry, config: Config) -> Path:
    root = config.home / ".claude" if entry.agent == "claude" else config.codex_home
    collection = {"skill": "skills", "agent": "agents", "command": "commands"}[entry.kind]
    return root / collection / entry.name


def digest(path: Path) -> str:
    """Hash a file or directory byte-for-byte, including relative file names."""
    hasher = hashlib.sha256()
    if path.is_dir() and not path.is_symlink():
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(path).as_posix().encode("utf-8")
            if child.is_dir() and not child.is_symlink():
                hasher.update(b"D\0" + relative + b"\0")
            elif child.is_file() or child.is_symlink():
                hasher.update(b"F\0" + relative + b"\0")
                hasher.update(child.read_bytes())
    else:
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def text_bytes_equal(left: bytes, right: bytes) -> bool:
    """Treat UTF-8 text with host-specific line endings as equivalent."""
    if left == right:
        return True
    try:
        return left.decode("utf-8").replace("\r\n", "\n") == right.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return False


def content_equivalent(left: Path, right: Path) -> bool:
    """Compare files or trees, allowing only UTF-8 CRLF/LF differences."""
    if left.is_dir() != right.is_dir():
        return False
    if left.is_file():
        return right.is_file() and text_bytes_equal(left.read_bytes(), right.read_bytes())
    left_files = {path.relative_to(left).as_posix(): path for path in left.rglob("*") if path.is_file()}
    right_files = {path.relative_to(right).as_posix(): path for path in right.rglob("*") if path.is_file()}
    if left_files.keys() != right_files.keys():
        return False
    return all(text_bytes_equal(left_files[name].read_bytes(), right_files[name].read_bytes()) for name in left_files)


def current_link_target(path: Path) -> Path | None:
    if not path.is_symlink():
        return None
    try:
        return path.resolve(strict=True)
    except OSError:
        return None


def is_junction(path: Path) -> bool:
    """Return whether path is a Windows directory junction on supported Python versions."""
    return bool(getattr(path, "is_junction", lambda: False)())


def remove_path(path: Path) -> None:
    """Remove a single owned destination, never a collection directory."""
    if is_junction(path):
        path.rmdir()
    elif path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination, follow_symlinks=False)


def make_junction(source: Path, destination: Path) -> None:
    """Create a Windows directory junction, rejecting cmd.exe metacharacters."""
    unsafe = "&|<>()^%!\""
    if any(character in str(source) or character in str(destination) for character in unsafe):
        raise OSError("junction paths contain unsupported cmd.exe metacharacters")
    subprocess.run(
        ["cmd", "/d", "/v:off", "/c", "mklink", "/J", str(destination), str(source)],
        check=True,
        capture_output=True,
        text=True,
    )


def make_file_symlink(source: Path, destination: Path) -> None:
    destination.symlink_to(source, target_is_directory=False)


def make_unix_symlink(source: Path, destination: Path) -> None:
    destination.symlink_to(source, target_is_directory=source.is_dir())


def link_item(source: Path, destination: Path) -> str:
    """Link a payload and return its concrete ownership mode."""
    if platform_system() == "Windows":
        if source.is_dir():
            make_junction(source, destination)
            return "junction"
        make_file_symlink(source, destination)
        return "link"
    make_unix_symlink(source, destination)
    return "link"


def entry_record(
    entry: Entry, mode: str, *, removable: bool = True, installed_digest: str | None = None
) -> dict[str, str | bool]:
    return {
        "agent": entry.agent,
        "kind": entry.kind,
        "name": entry.name,
        "source": str(entry.source.resolve()),
        "mode": mode,
        "digest": installed_digest or digest(entry.source),
        "removable": removable,
    }


def link_identity_matches(destination: Path, record: dict[str, Any]) -> bool:
    """Match an owned link even when its recorded source no longer exists."""
    mode = record.get("mode")
    source_value = record.get("source")
    if not isinstance(source_value, str) or not source_value:
        return False
    source = Path(source_value)
    if mode == "junction" and is_junction(destination):
        try:
            return os.path.samefile(destination, source)
        except OSError:
            return destination.resolve(strict=False) == source
    if mode == "link" and destination.is_symlink():
        try:
            return os.path.samefile(destination, source)
        except OSError:
            raw_target = Path(os.readlink(destination))
            target = raw_target if raw_target.is_absolute() else destination.parent / raw_target
            return target.resolve(strict=False) == source
    return False


def entry_matches_record(destination: Path, record: dict[str, Any]) -> bool:
    """Whether the on-disk entry still has the exact owned identity."""
    mode = record.get("mode")
    if mode in {"link", "junction"}:
        return link_identity_matches(destination, record)
    if mode == "copy" and destination.exists() and not destination.is_symlink():
        return digest(destination) == record.get("digest")
    return False


def marketplace_overlap(home: Path) -> bool:
    """Detect an installed local marketplace for this bundle without touching it."""
    root = home / ".claude" / "plugins"
    known_names = {"agentic-sdlc", "agentic-sdlc-orchestrator"}
    for collection in (root / "marketplaces", root / "cache"):
        if collection.exists() and any((collection / name).exists() for name in known_names):
            return True
    for manifest in (root / "installed_plugins.json", root / "known_marketplaces.json"):
        if not manifest.exists():
            continue
        try:
            text = manifest.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(name in text for name in known_names):
            return True
    return False


def create_destination(entry: Entry, destination: Path, config: Config) -> str:
    """Create a new entry according to mode; auto alone may fall back to copy."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if config.mode == "copy":
        copy_item(entry.source, destination)
        return "copy"
    try:
        return link_item(entry.source, destination)
    except (OSError, subprocess.CalledProcessError):
        if config.mode == "link":
            raise
        copy_item(entry.source, destination)
        return "copy"


def install(config: Config) -> Result:
    """Install selected entries, adopting only exact legacy entries and reporting conflicts."""
    state = load_state(config.state_path)
    owned = validate_owned_entries(config, state)
    messages: list[str] = []
    partial = False
    claude_blocked = config.agent in {"all", "claude"} and marketplace_overlap(config.home)

    for entry in discover_entries(config.repo_root):
        if config.agent != "all" and entry.agent != config.agent:
            continue
        destination = destination_for(entry, config)
        key = str(destination)
        record = owned.get(key)

        if entry.agent == "claude" and claude_blocked:
            partial = True
            messages.append(f"marketplace overlap: {destination}")
            continue

        if isinstance(record, dict) and not entry_matches_record(destination, record):
            partial = True
            messages.append(f"conflict: {destination}")
            continue

        if destination.exists() or destination.is_symlink():
            if isinstance(record, dict):
                if record.get("mode") == "copy":
                    if record.get("removable", True) is False:
                        messages.append(f"ok (preserved on uninstall): {destination}")
                    elif config.dry_run:
                        messages.append(f"would refresh: {destination}")
                    else:
                        remove_path(destination)
                        copy_item(entry.source, destination)
                        owned[key] = entry_record(entry, "copy")
                        messages.append(f"refreshed: {destination}")
                else:
                    recorded_source = Path(str(record.get("source", "")))
                    desired_source = entry.source.resolve()
                    if recorded_source != desired_source:
                        if config.dry_run:
                            messages.append(f"would retarget: {destination}")
                        else:
                            remove_path(destination)
                            try:
                                mode = create_destination(entry, destination, config)
                            except (OSError, subprocess.CalledProcessError) as exc:
                                try:
                                    link_item(recorded_source, destination)
                                except (OSError, subprocess.CalledProcessError):
                                    pass
                                raise InstallerError(f"cannot retarget {destination}: {exc}") from exc
                            owned[key] = entry_record(entry, mode)
                            messages.append(f"retargeted: {destination} ({mode})")
                    else:
                        messages.append(f"ok: {destination}")
                continue

            target = current_link_target(destination)
            if target == entry.source.resolve():
                if not config.dry_run:
                    owned[key] = entry_record(entry, "link")
                messages.append(f"adopted: {destination}")
                continue
            if not destination.is_symlink() and destination.exists() and content_equivalent(destination, entry.source):
                if not config.dry_run:
                    owned[key] = entry_record(entry, "copy", removable=False, installed_digest=digest(destination))
                messages.append(f"adopted (preserved on uninstall): {destination}")
                continue
            partial = True
            messages.append(f"conflict: {destination}")
            continue

        if config.dry_run:
            messages.append(f"would install: {destination}")
            continue
        try:
            mode = create_destination(entry, destination, config)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InstallerError(f"cannot install {destination}: {exc}") from exc
        owned[key] = entry_record(entry, mode)
        messages.append(f"installed: {destination} ({mode})")

    write_state(config.state_path, state, config.dry_run)
    return Result(1 if partial else 0, tuple(messages))


def status(config: Config) -> Result:
    """Report exact ownership health, preserving every on-disk entry."""
    state = load_state(config.state_path)
    owned = validate_owned_entries(config, state)
    messages: list[str] = []
    partial = False
    for key, record in owned.items():
        if config.agent != "all" and record.get("agent") != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        destination = Path(key)
        if not destination.exists() and not destination.is_symlink():
            partial = True
            messages.append(f"absent: {destination}")
        elif entry_matches_record(destination, record):
            messages.append(f"ok: {destination}")
        else:
            partial = True
            messages.append(f"conflict: {destination}")
    return Result(1 if partial else 0, tuple(messages))


def uninstall(config: Config) -> Result:
    """Remove only entries that still exactly match recorded ownership."""
    state = load_state(config.state_path)
    owned = validate_owned_entries(config, state)
    messages: list[str] = []
    partial = False
    for key, record in list(owned.items()):
        if config.agent != "all" and record.get("agent") != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        destination = Path(key)
        if not destination.exists() and not destination.is_symlink():
            if not config.dry_run:
                owned.pop(key)
            messages.append(f"absent: {destination}")
            continue
        if not entry_matches_record(destination, record):
            partial = True
            messages.append(f"conflict: {destination}")
            continue
        if record.get("removable", True) is False:
            messages.append(f"kept: {destination} (adopted pre-existing entry)")
            continue
        if config.dry_run:
            messages.append(f"would remove: {destination}")
            continue
        try:
            remove_path(destination)
        except OSError as exc:
            raise InstallerError(f"cannot remove {destination}: {exc}") from exc
        owned.pop(key)
        messages.append(f"removed: {destination}")
    write_state(config.state_path, state, config.dry_run)
    return Result(1 if partial else 0, tuple(messages))


def self_test(config: Config) -> Result:
    """Exercise an isolated lifecycle without writing to the caller's homes or state."""
    with tempfile.TemporaryDirectory(prefix="agentic-sdlc-installer-") as temporary:
        root = Path(temporary)
        isolated = Config(
            config.repo_root,
            root / "home",
            root / "codex",
            config.mode,
            False,
            "all",
            root / "state",
        )
        installed = install(isolated)
        checked = status(isolated)
        removed = uninstall(isolated)
        if installed.exit_code or checked.exit_code or removed.exit_code:
            return Result(1, installed.messages + checked.messages + removed.messages + ("self-test failed",))
    return Result(0, ("self-test passed",))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "status", "uninstall", "self-test"), nargs="?", default="install")
    parser.add_argument("--agent", choices=("all", "claude", "codex"), action=SingleAgentAction)
    parser.add_argument("--mode", choices=("auto", "link", "copy"), default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--codex-home", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = args.home.expanduser()
    codex_home_value = args.codex_home
    if codex_home_value is None:
        environment_value = os.environ.get("CODEX_HOME")
        if environment_value is not None and not environment_value.strip():
            print("fatal: CODEX_HOME must not be empty", file=sys.stderr)
            return 2
        codex_home_value = Path(environment_value) if environment_value else home / ".codex"
    codex_home = codex_home_value.expanduser().resolve()
    config_repo_root = Path(__file__).resolve().parents[1]
    if codex_home == config_repo_root:
        print("fatal: Codex home must not be the repository root", file=sys.stderr)
        return 2
    config = Config(config_repo_root, home, codex_home, args.mode, args.dry_run, args.agent or "all")
    try:
        operation = {"install": install, "status": status, "uninstall": uninstall, "self-test": self_test}[args.command]
        result = operation(config)
    except InstallerError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2
    for message in result.messages:
        print(message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
