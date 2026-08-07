#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install lifecycle-owned Agentic SDLC operator commands into an existing user PATH."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Iterator


STATE_VERSION = 1
COMMANDS = ("agentic-sdlc-statusline", "ocx-launch", "ocx-ultracode")


class OperatorToolsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    repo_root: Path
    home: Path
    bin_dir: Path
    state_root: Path
    dry_run: bool = False
    require_path: bool = True

    @property
    def state_path(self) -> Path:
        return self.state_root / "agentic-sdlc-operator-tools" / "state.json"

    @property
    def lock_path(self) -> Path:
        return self.state_root / "agentic-sdlc-operator-tools" / "lock"


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def state_root_for(home: Path) -> Path:
    value = os.environ.get("XDG_STATE_HOME")
    return absolute(Path(value)) if value else absolute(home / ".local" / "state")


def default_bin_dir(home: Path) -> Path:
    value = os.environ.get("XDG_BIN_HOME")
    return absolute(Path(value)) if value else absolute(home / ".local" / "bin")


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def path_entries() -> set[str]:
    return {
        os.path.normcase(os.path.abspath(os.path.expanduser(entry)))
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }


def validate_bin_dir(config: Config) -> None:
    bin_dir = config.bin_dir
    if not bin_dir.is_absolute():
        raise OperatorToolsError("bin directory must be absolute")
    if bin_dir == Path(bin_dir.anchor) or bin_dir == config.repo_root or config.repo_root in bin_dir.parents:
        raise OperatorToolsError(f"unsafe operator-tools bin directory: {bin_dir}")
    if config.require_path and os.path.normcase(str(bin_dir)) not in path_entries():
        raise OperatorToolsError(f"operator-tools bin directory is not on PATH: {bin_dir}")
    current = bin_dir
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise OperatorToolsError(f"operator-tools bin ancestor is not a physical directory: {current}")
    if hasattr(os, "getuid") and current.stat().st_uid != os.getuid():
        raise OperatorToolsError(f"operator-tools bin ancestor is not owned by the current user: {current}")
    if bin_dir.exists():
        if bin_dir.is_symlink() or not bin_dir.is_dir():
            raise OperatorToolsError(f"operator-tools bin must be a physical directory: {bin_dir}")
        if hasattr(os, "getuid") and bin_dir.stat().st_uid != os.getuid():
            raise OperatorToolsError(f"operator-tools bin is not owned by the current user: {bin_dir}")


def desired_files(config: Config) -> dict[str, bytes]:
    statusline = config.repo_root / "assets" / "claude" / "statusline-command.sh"
    launcher = config.repo_root / "scripts" / "opencodex-claude.sh"
    templates = config.repo_root / "assets" / "launchers"
    for path in (statusline, launcher, templates / "ocx-launch.in", templates / "ocx-ultracode.in"):
        if not path.is_file():
            raise OperatorToolsError(f"required operator-tools source is missing: {path}")
    quoted_launcher = "'" + str(launcher).replace("'", "'\\''") + "'"
    return {
        "agentic-sdlc-statusline": statusline.read_bytes(),
        "ocx-launch": (templates / "ocx-launch.in").read_text(encoding="utf-8").replace("@CANONICAL_LAUNCHER@", quoted_launcher).encode(),
        "ocx-ultracode": (templates / "ocx-ultracode.in").read_text(encoding="utf-8").replace("@CANONICAL_LAUNCHER@", quoted_launcher).encode(),
    }


def empty_state() -> dict[str, object]:
    return {"version": STATE_VERSION, "entries": {}}


def load_state(path: Path) -> dict[str, object]:
    if not path.exists():
        return empty_state()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorToolsError(f"cannot read operator-tools state {path}: {exc}") from exc
    if value.get("version") != STATE_VERSION or not isinstance(value.get("entries"), dict):
        raise OperatorToolsError(f"invalid operator-tools state: {path}")
    for key, record in value["entries"].items():
        if (
            not isinstance(key, str)
            or Path(key).name not in COMMANDS
            or not isinstance(record, dict)
            or record.get("digest") is None
            or record.get("path") != key
        ):
            raise OperatorToolsError(f"invalid operator-tools ownership record: {key}")
    return value


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_state(config: Config, state: dict[str, object]) -> None:
    if config.dry_run:
        return
    content = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode()
    atomic_write(config.state_path, content, 0o600)


@contextmanager
def lifecycle_lock(config: Config) -> Iterator[None]:
    if config.dry_run:
        yield
        return
    config.lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(config.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def exact_owned_statusline(config: Config) -> Path:
    path = config.bin_dir / "agentic-sdlc-statusline"
    state = load_state(config.state_path)
    record = state["entries"].get(str(path))  # type: ignore[index]
    if not isinstance(record, dict) or not path.is_file() or path.is_symlink():
        raise OperatorToolsError("the packaged statusline is not an installed owned operator tool")
    if digest_file(path) != record.get("digest"):
        raise OperatorToolsError("the installed statusline differs from its ownership receipt")
    return path


def _install(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    desired = desired_files(config)
    state = load_state(config.state_path)
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    messages: list[str] = []
    partial = False
    for name, content in desired.items():
        path = config.bin_dir / name
        key = str(path)
        wanted = digest_bytes(content)
        record = entries.get(key)
        if path.exists() or path.is_symlink():
            if path.is_symlink() or not path.is_file():
                partial = True; messages.append(f"conflict: {path}"); continue
            actual = digest_file(path)
            if record is None:
                if actual == wanted:
                    messages.append(f"adopted (preserved on uninstall): {path}")
                    if not config.dry_run:
                        entries[key] = {"path": key, "digest": actual, "removable": "false"}
                        write_state(config, state)
                else:
                    partial = True; messages.append(f"conflict: {path}")
                continue
            if actual != record.get("digest"):
                partial = True; messages.append(f"conflict: {path}"); continue
            if actual == wanted:
                messages.append(f"ok: {path}"); continue
            if config.dry_run:
                messages.append(f"would refresh: {path}"); continue
            atomic_write(path, content, 0o755)
            entries[key] = {"path": key, "digest": wanted, "removable": record.get("removable", "true")}
            write_state(config, state); messages.append(f"refreshed: {path}"); continue
        if config.dry_run:
            messages.append(f"would install: {path}"); continue
        config.bin_dir.mkdir(parents=True, exist_ok=True)
        atomic_write(path, content, 0o755)
        entries[key] = {"path": key, "digest": wanted, "removable": "true"}
        write_state(config, state); messages.append(f"installed: {path}")
    return (1 if partial else 0), messages


def install(config: Config) -> tuple[int, list[str]]:
    with lifecycle_lock(config):
        return _install(config)


def status(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    state = load_state(config.state_path)
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    messages: list[str] = []
    partial = False
    for name in COMMANDS:
        path = config.bin_dir / name
        record = entries.get(str(path))
        if record is None:
            partial = True; messages.append(f"unmanaged: {path}")
        elif not path.is_file() or path.is_symlink():
            partial = True; messages.append(f"absent/conflict: {path}")
        elif digest_file(path) != record.get("digest"):
            partial = True; messages.append(f"conflict: {path}")
        else:
            messages.append(f"ok: {path}")
    return (1 if partial else 0), messages


def _uninstall(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    state = load_state(config.state_path)
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    messages: list[str] = []
    partial = False
    for name in COMMANDS:
        path = config.bin_dir / name; key = str(path); record = entries.get(key)
        if record is None:
            continue
        if not path.exists() and not path.is_symlink():
            if not config.dry_run:
                entries.pop(key); write_state(config, state)
            messages.append(f"absent: {path}"); continue
        if path.is_symlink() or not path.is_file() or digest_file(path) != record.get("digest"):
            partial = True; messages.append(f"conflict: {path}"); continue
        if record.get("removable") == "false":
            messages.append(f"kept: {path} (adopted pre-existing entry)"); continue
        if config.dry_run:
            messages.append(f"would remove: {path}"); continue
        path.unlink(); entries.pop(key); write_state(config, state); messages.append(f"removed: {path}")
    return (1 if partial else 0), messages


def uninstall(config: Config) -> tuple[int, list[str]]:
    with lifecycle_lock(config):
        return _uninstall(config)


def self_test(repo_root: Path) -> tuple[int, list[str]]:
    with tempfile.TemporaryDirectory(prefix="agentic-sdlc-operator-tools-") as temp:
        root = Path(temp); home = root / "home"; bin_dir = home / ".local" / "bin"
        config = Config(repo_root, home, bin_dir, root / "state", require_path=False)
        installed = install(config); checked = status(config); removed = uninstall(config)
        if installed[0] or checked[0] or removed[0] or any((bin_dir / name).exists() for name in COMMANDS):
            return 1, installed[1] + checked[1] + removed[1] + ["operator-tools self-test failed"]
    return 0, ["operator-tools self-test passed"]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "status", "uninstall", "self-test"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--bin-dir", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        print("fatal: operator tools are currently supported on Unix, WSL, and macOS only", file=sys.stderr)
        return 2
    if args.command == "self-test":
        code, messages = self_test(repo_root)
    else:
        home = absolute(args.home)
        config = Config(
            repo_root,
            home,
            absolute(args.bin_dir) if args.bin_dir else default_bin_dir(home),
            absolute(args.state_root) if args.state_root else state_root_for(home),
            args.dry_run,
        )
        try:
            code, messages = {"install": install, "status": status, "uninstall": uninstall}[args.command](config)
        except OperatorToolsError as exc:
            print(f"fatal: {exc}", file=sys.stderr)
            return 2
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
