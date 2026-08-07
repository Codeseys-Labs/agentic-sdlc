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
from typing import Any, Iterator


STATE_VERSION = 2
LEGACY_STATE_VERSION = 1
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
    return {"version": STATE_VERSION, "entries": {}, "pending": None}


def valid_record(record: Any, key: str) -> bool:
    return (
        isinstance(record, dict)
        and set(record) == {"path", "digest", "removable"}
        and record.get("path") == key
        and isinstance(record.get("digest"), str)
        and len(record["digest"]) == 64
        and record.get("removable") in {"true", "false"}
    )


def validate_pending(config: Config, state: dict[str, object]) -> None:
    pending = state.get("pending")
    if pending is None:
        return
    if not isinstance(pending, dict) or pending.get("operation") not in {"install", "refresh", "uninstall"}:
        raise OperatorToolsError(f"invalid operator-tools pending operation: {config.state_path}")
    key = pending.get("path")
    if not isinstance(key, str) or Path(key).parent != config.bin_dir or Path(key).name not in COMMANDS:
        raise OperatorToolsError(f"invalid operator-tools pending path: {key}")
    before, after = pending.get("before"), pending.get("after")
    if before is not None and not valid_record(before, key):
        raise OperatorToolsError(f"invalid operator-tools pending before record: {key}")
    if after is not None and not valid_record(after, key):
        raise OperatorToolsError(f"invalid operator-tools pending after record: {key}")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    operation = pending["operation"]
    valid = (
        operation == "install" and before is None and after is not None and key not in entries
    ) or (
        operation == "refresh" and before is not None and after is not None
        and entries.get(key) == before and before["digest"] != after["digest"]
        and before["removable"] == after["removable"]
    ) or (
        operation == "uninstall" and before is not None and after is None and entries.get(key) == before
    )
    if not valid:
        raise OperatorToolsError(f"invalid operator-tools pending transition: {key}")


def load_state(path: Path, config: Config | None = None) -> dict[str, object]:
    if not path.exists():
        return empty_state()
    if path.is_symlink():
        raise OperatorToolsError(f"operator-tools state must not be a link: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OperatorToolsError(f"cannot read operator-tools state {path}: {exc}") from exc
    if value.get("version") == LEGACY_STATE_VERSION and isinstance(value.get("entries"), dict):
        value = {"version": STATE_VERSION, "entries": value["entries"], "pending": None}
    if value.get("version") != STATE_VERSION or not isinstance(value.get("entries"), dict) or "pending" not in value:
        raise OperatorToolsError(f"invalid operator-tools state: {path}")
    for key, record in value["entries"].items():
        if not isinstance(key, str) or Path(key).name not in COMMANDS or not valid_record(record, key):
            raise OperatorToolsError(f"invalid operator-tools ownership record: {key}")
    if config is not None:
        validate_pending(config, value)
    return value


def sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def durable_mkdir(path: Path, mode: int = 0o700) -> None:
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        directory.mkdir(mode=mode)
        sync_directory(directory)
        sync_directory(directory.parent)


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    durable_mkdir(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(content)
            handle.flush()
            if sys.platform == "darwin":
                import fcntl
                fcntl.fcntl(handle.fileno(), fcntl.F_FULLFSYNC)
            else:
                os.fsync(handle.fileno())
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def durable_unlink(path: Path) -> None:
    path.unlink()
    sync_directory(path.parent)


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
    durable_mkdir(config.lock_path.parent)
    descriptor = os.open(config.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        import fcntl
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def live_matches(path: Path, record: dict[str, str]) -> bool:
    return path.is_file() and not path.is_symlink() and digest_file(path) == record["digest"]


def recover_pending(config: Config, state: dict[str, object], *, read_only: bool) -> str | None:
    pending = state.get("pending")
    if pending is None:
        return None
    assert isinstance(pending, dict)
    path = Path(pending["path"])
    operation = pending["operation"]
    before = pending.get("before")
    after = pending.get("after")
    if path.parent.exists():
        sync_directory(path.parent)
    outcome: str | None = None
    if operation == "install":
        if not path.exists() and not path.is_symlink():
            outcome = "abort"
        elif isinstance(after, dict) and live_matches(path, after):
            outcome = "commit"
    elif operation == "refresh":
        if isinstance(before, dict) and live_matches(path, before):
            outcome = "abort"
        elif isinstance(after, dict) and live_matches(path, after):
            outcome = "commit"
    elif operation == "uninstall":
        if isinstance(before, dict) and live_matches(path, before):
            outcome = "abort"
        elif not path.exists() and not path.is_symlink():
            outcome = "commit"
    if outcome is None:
        raise OperatorToolsError(f"interrupted operator-tools {operation} conflicts with current file: {path}")
    if read_only:
        return f"would recover {outcome}: {path}"
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    key = str(path)
    if outcome == "commit":
        if operation in {"install", "refresh"}:
            entries[key] = after  # type: ignore[assignment]
        else:
            entries.pop(key, None)
    state["pending"] = None
    write_state(config, state)
    return f"recovered {outcome}: {path}"


def exact_owned_statusline(config: Config) -> Path:
    path = config.bin_dir / "agentic-sdlc-statusline"
    state = load_state(config.state_path, config)
    if state.get("pending") is not None:
        raise OperatorToolsError("the operator-tools lifecycle has an interrupted pending operation")
    record = state["entries"].get(str(path))  # type: ignore[index]
    if not isinstance(record, dict) or not live_matches(path, record):
        raise OperatorToolsError("the packaged statusline is not an installed owned operator tool")
    return path


def arm(config: Config, state: dict[str, object], operation: str, path: Path, before: Any, after: Any) -> None:
    state["pending"] = {
        "operation": operation,
        "path": str(path),
        "before": before,
        "after": after,
    }
    write_state(config, state)


def commit_pending(config: Config, state: dict[str, object]) -> None:
    pending = state["pending"]
    assert isinstance(pending, dict)
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    key = pending["path"]
    if pending["operation"] in {"install", "refresh"}:
        entries[key] = pending["after"]
    else:
        entries.pop(key, None)
    state["pending"] = None
    write_state(config, state)


def _install(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    desired = desired_files(config)
    state = load_state(config.state_path, config)
    messages: list[str] = []
    if state.get("pending") is not None:
        if config.dry_run:
            messages.append(recover_pending(config, state, read_only=True) or "")
            return 1, messages
        messages.append(recover_pending(config, state, read_only=False) or "")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
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
            after = {"path": key, "digest": wanted, "removable": record["removable"]}
            arm(config, state, "refresh", path, record, after)
            atomic_write(path, content, 0o755)
            commit_pending(config, state)
            messages.append(f"refreshed: {path}"); continue
        if config.dry_run:
            messages.append(f"would install: {path}"); continue
        durable_mkdir(config.bin_dir)
        after = {"path": key, "digest": wanted, "removable": "true"}
        arm(config, state, "install", path, None, after)
        atomic_write(path, content, 0o755)
        commit_pending(config, state)
        messages.append(f"installed: {path}")
    return (1 if partial else 0), messages


def install(config: Config) -> tuple[int, list[str]]:
    with lifecycle_lock(config):
        return _install(config)


def _status(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    state = load_state(config.state_path, config)
    messages: list[str] = []
    partial = False
    if state.get("pending") is not None:
        try:
            messages.append(recover_pending(config, state, read_only=True) or "")
        except OperatorToolsError as exc:
            messages.append(str(exc))
        partial = True
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    for name in COMMANDS:
        path = config.bin_dir / name
        record = entries.get(str(path))
        if record is None:
            partial = True; messages.append(f"unmanaged: {path}")
        elif not live_matches(path, record):
            partial = True; messages.append(f"conflict: {path}")
        else:
            messages.append(f"ok: {path}")
    return (1 if partial else 0), messages


def status(config: Config) -> tuple[int, list[str]]:
    with lifecycle_lock(config):
        return _status(config)


def _uninstall(config: Config) -> tuple[int, list[str]]:
    validate_bin_dir(config)
    state = load_state(config.state_path, config)
    messages: list[str] = []
    if state.get("pending") is not None:
        if config.dry_run:
            messages.append(recover_pending(config, state, read_only=True) or "")
            return 1, messages
        messages.append(recover_pending(config, state, read_only=False) or "")
    entries: dict[str, dict[str, str]] = state["entries"]  # type: ignore[assignment]
    partial = False
    for name in COMMANDS:
        path = config.bin_dir / name; key = str(path); record = entries.get(key)
        if record is None:
            continue
        if not path.exists() and not path.is_symlink():
            if not config.dry_run:
                entries.pop(key); write_state(config, state)
            messages.append(f"absent: {path}"); continue
        if not live_matches(path, record):
            partial = True; messages.append(f"conflict: {path}"); continue
        if record.get("removable") == "false":
            messages.append(f"kept: {path} (adopted pre-existing entry)"); continue
        if config.dry_run:
            messages.append(f"would remove: {path}"); continue
        arm(config, state, "uninstall", path, record, None)
        durable_unlink(path)
        commit_pending(config, state)
        messages.append(f"removed: {path}")
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
