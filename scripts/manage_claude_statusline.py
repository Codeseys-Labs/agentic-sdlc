#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Inspect or explicitly activate the packaged Claude Code status line.

Exit vocabulary (Implementation Decision 9), one derivation point via the EXIT_* names below:
  0  every completed answer, whether the mutating verb performed its effect (`activate`,
     `deactivate`) or `status` merely read and reported one of its five distinguishable
     read-only states -- `active`, `inactive`, `unmanaged`, `conflict`, or a pending
     recovery -- in the returned MESSAGE, never in the exit code.
  2  a real refusal or failure: a malformed argument, an unreadable or foreign-owned
     settings/receipt file, a settings change detected mid-write, a statusline the bundle
     lifecycle does not currently own, or any other `StatuslineError`/`InstallerError`.

The command this activates is one BUNDLE LEDGER ROW (gh #10 phase 2): `bundle:install` publishes
`assets/claude/statusline-command.sh` to `<claude-home>/.claude/statusline/agentic-sdlc-statusline`
at mode 0o755, and `install_skill_bundle.exact_owned_statusline` is the only place this module gets
a command path from. Nothing here derives a path of its own, so a statusline that is absent,
unowned, drifted, or unexecutable is a named refusal instead of a `statusLine.command` pointing at
bytes no lifecycle owns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile
from typing import Any

import install_skill_bundle as installer


RECEIPT_VERSION = 2
LEGACY_RECEIPT_VERSION = 1
MANAGED_KEYS = ("type", "command")

# Single derivation point for this module's exit vocabulary; see the module docstring's table.
EXIT_OK = 0
EXIT_REFUSED = 2


class StatuslineError(RuntimeError):
    pass


class SettingsChangedError(StatuslineError):
    pass


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def state_root_for(home: Path) -> Path:
    """Derive this host's user-local state root from the GIVEN home, never from ``Path.home()``.

    Owned here rather than imported: both the statusline receipt and the bundle ledger this module
    reads live under this root, and ``install_skill_bundle.state_directory()`` is not the
    substitute, because it reads ``Path.home()`` and would ignore ``--home``.  ``--state-root``
    still overrides this entirely; this is only the fallback.
    """
    value = os.environ.get("XDG_STATE_HOME")
    return absolute(Path(value)) if value else absolute(home / ".local" / "state")


def settings_path(home: Path, claude_config_dir: Path | None) -> Path:
    root = absolute(claude_config_dir) if claude_config_dir else absolute(home / ".claude")
    return root / "settings.json"


def receipt_path(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-claude-statusline" / "receipt.json"


def assert_physical_parent(path: Path) -> None:
    if path.is_symlink():
        raise StatuslineError(f"path must not be a link: {path}")
    current = path.parent
    while not current.exists() and current != current.parent:
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise StatuslineError(f"path parent must be a physical directory: {current}")
    if hasattr(os, "getuid") and current.stat().st_uid != os.getuid():
        raise StatuslineError(f"path parent is not owned by the current user: {current}")


def digest_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_snapshot(path: Path) -> tuple[dict[str, Any], bytes | None]:
    assert_physical_parent(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        if path.is_symlink():
            raise StatuslineError(f"path must not be a link: {path}")
        return {"exists": False}, None
    except OSError as exc:
        raise StatuslineError(f"cannot open {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise StatuslineError(f"path must be a regular file: {path}")
        if hasattr(os, "getuid") and before.st_uid != os.getuid():
            raise StatuslineError(f"path is not owned by the current user: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            content = handle.read()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_uid,
        stat.S_IMODE(before.st_mode),
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_uid,
        stat.S_IMODE(after.st_mode),
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    if identity_before != identity_after:
        raise SettingsChangedError(f"path changed while it was being read: {path}")
    return {
        "exists": True,
        "identity": {
            "device": before.st_dev,
            "inode": before.st_ino,
            "uid": before.st_uid,
            "mode": stat.S_IMODE(before.st_mode),
            "size": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "ctime_ns": before.st_ctime_ns,
        },
        "sha256": digest_bytes(content),
    }, content


def load_settings(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot, content = file_snapshot(path)
    if content is None:
        return {}, snapshot
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StatuslineError(f"cannot read Claude settings {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StatuslineError(f"Claude settings must contain a JSON object: {path}")
    statusline = value.get("statusLine")
    if statusline is not None and not isinstance(statusline, dict):
        raise StatuslineError("Claude statusLine must be a JSON object")
    return value, snapshot


def json_bytes(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def sync_directory(path: Path) -> None:
    if os.name == "nt":
        # Windows cannot open a directory via os.open, so there is no stdlib
        # parent-directory durability barrier here (the install_skill_bundle.py
        # fsync_directory precedent): lifecycle transitions remain process-crash
        # recoverable, not power-loss durable, on Windows.
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_bytes(
    path: Path,
    content: bytes,
    mode: int,
    expected: dict[str, Any] | None = None,
) -> None:
    assert_physical_parent(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            # Mode bits are a POSIX concept and Windows lacks os.fchmod, so the call is
            # guarded by existence (mkstemp already created the file 0o600) and sits inside
            # the fdopen block so no exception can leave the descriptor open against the
            # finally's unlink, which Windows refuses with WinError 32 while a handle is
            # held (the install_skill_bundle.py atomic_write precedent).
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if expected is not None:
            current, _ = file_snapshot(path)
            if current != expected:
                raise SettingsChangedError(
                    f"Claude settings changed before replacement; preserving operator edit: {path}"
                )
        os.replace(temporary, path)
        sync_directory(path.parent)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def atomic_json(
    path: Path,
    value: dict[str, Any],
    mode: int,
    expected: dict[str, Any] | None = None,
) -> None:
    atomic_bytes(path, json_bytes(value), mode, expected)


def remove_durable(path: Path) -> None:
    path.unlink()
    sync_directory(path.parent)


def validate_previous(previous: Any) -> bool:
    if not isinstance(previous, dict) or set(previous) != set(MANAGED_KEYS):
        return False
    for record in previous.values():
        if not isinstance(record, dict) or not isinstance(record.get("present"), bool):
            return False
        if record["present"]:
            if set(record) != {"present", "value"} or not isinstance(record["value"], str):
                return False
        elif set(record) != {"present"}:
            return False
    return True


def validate_snapshot(value: Any, *, after: bool = False) -> bool:
    if not isinstance(value, dict) or not isinstance(value.get("exists"), bool):
        return False
    if not value["exists"]:
        return not after and set(value) == {"exists"}
    digest = value.get("sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        return False
    if after:
        return (
            set(value) == {"exists", "sha256", "uid", "mode"}
            and isinstance(value.get("uid"), int)
            and isinstance(value.get("mode"), int)
        )
    identity = value.get("identity")
    return isinstance(identity, dict) and set(identity) == {
        "device", "inode", "uid", "mode", "size", "mtime_ns", "ctime_ns"
    } and all(isinstance(item, int) for item in identity.values())


def legacy_receipt(value: dict[str, Any]) -> dict[str, Any] | None:
    if value.get("version") != LEGACY_RECEIPT_VERSION:
        return None
    managed = value.get("managed")
    previous = value.get("previous")
    if not isinstance(managed, dict) or not isinstance(previous, dict):
        return None
    converted: dict[str, dict[str, Any]] = {}
    for key in MANAGED_KEYS:
        if key not in managed or not isinstance(managed[key], str) or key not in previous:
            return None
        old = previous[key]
        converted[key] = {"present": False} if old == {"missing": True} else {"present": True, "value": old}
    return {
        "version": RECEIPT_VERSION,
        "phase": "committed",
        "settings": value.get("settings"),
        "managed": {key: managed[key] for key in MANAGED_KEYS},
        "previous": converted,
    }


def validate_receipt(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise StatuslineError(f"invalid statusline receipt: {path}")
    converted = legacy_receipt(value)
    if converted is not None:
        value = converted
    managed = value.get("managed")
    target = value.get("settings")
    if (
        value.get("version") != RECEIPT_VERSION
        or value.get("phase") not in {"committed", "pending"}
        or not isinstance(target, str)
        or not Path(target).is_absolute()
        or not isinstance(managed, dict)
        or set(managed) != set(MANAGED_KEYS)
        or not all(isinstance(managed[key], str) for key in MANAGED_KEYS)
        or not validate_previous(value.get("previous"))
    ):
        raise StatuslineError(f"invalid statusline receipt: {path}")
    if value["phase"] == "pending":
        if (
            value.get("operation") not in {"activate", "deactivate"}
            or not validate_snapshot(value.get("before"))
            or not validate_snapshot(value.get("after"), after=True)
        ):
            raise StatuslineError(f"invalid pending statusline transaction: {path}")
    return value


def load_receipt(path: Path) -> dict[str, Any] | None:
    snapshot, content = file_snapshot(path)
    del snapshot
    if content is None:
        return None
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StatuslineError(f"cannot read statusline receipt {path}: {exc}") from exc
    return validate_receipt(value, path)


def managed_values(command: Path) -> dict[str, str]:
    # Claude invokes statusLine.command through a shell. Quote even user-selected bin paths so
    # spaces and metacharacters remain one executable pathname rather than shell syntax.
    return {"type": "command", "command": shlex.quote(str(command))}


def previous_values(statusline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        key: ({"present": True, "value": statusline[key]} if key in statusline else {"present": False})
        for key in MANAGED_KEYS
    }


def after_snapshot(content: bytes, mode: int) -> dict[str, Any]:
    return {
        "exists": True,
        "sha256": digest_bytes(content),
        "uid": os.getuid() if hasattr(os, "getuid") else 0,
        "mode": mode,
    }


def matches_after(snapshot: dict[str, Any], after: dict[str, Any]) -> bool:
    if not snapshot.get("exists") or snapshot.get("sha256") != after.get("sha256"):
        return False
    identity = snapshot.get("identity", {})
    return identity.get("uid") == after.get("uid") and identity.get("mode") == after.get("mode")


def committed_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": RECEIPT_VERSION,
        "phase": "committed",
        "settings": receipt["settings"],
        "managed": receipt["managed"],
        "previous": receipt["previous"],
    }


def recover_pending(receipt_file: Path, receipt: dict[str, Any] | None, *, dry_run: bool) -> dict[str, Any] | None:
    if receipt is None or receipt.get("phase") != "pending":
        return receipt
    if dry_run:
        raise StatuslineError("a pending statusline transaction requires recovery; rerun without --dry-run")
    target = Path(receipt["settings"])
    current, _ = file_snapshot(target)
    operation = receipt["operation"]
    if matches_after(current, receipt["after"]):
        sync_directory(target.parent)
        if operation == "activate":
            committed = committed_receipt(receipt)
            atomic_json(receipt_file, committed, 0o600)
            return committed
        remove_durable(receipt_file)
        return None
    if current == receipt["before"]:
        if operation == "activate":
            remove_durable(receipt_file)
            return None
        committed = committed_receipt(receipt)
        atomic_json(receipt_file, committed, 0o600)
        return committed
    raise StatuslineError(
        f"pending statusline {operation} transaction conflicts with current settings; preserving both: {target}"
    )


def _activate(
    config: installer.Config,
    path: Path,
    state_root: Path,
    dry_run: bool,
) -> tuple[int, list[str]]:
    receipt_file = receipt_path(state_root)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    if receipt is not None:
        raise StatuslineError("a managed statusline activation receipt already exists")
    command = installer.exact_owned_statusline(config)
    settings, before = load_settings(path)
    statusline = settings.get("statusLine") or {}
    wanted = managed_values(command)
    for key, value in wanted.items():
        if key in statusline and statusline[key] != value:
            raise StatuslineError(f"foreign statusLine.{key} value would be overwritten")
    previous = previous_values(statusline)
    statusline.update(wanted)
    settings["statusLine"] = statusline
    mode = before.get("identity", {}).get("mode", 0o600)
    content = json_bytes(settings)
    pending = {
        "version": RECEIPT_VERSION,
        "phase": "pending",
        "operation": "activate",
        "settings": str(path),
        "managed": wanted,
        "previous": previous,
        "before": before,
        "after": after_snapshot(content, mode),
    }
    messages = [f"would activate: {path} -> {command}" if dry_run else f"activated: {path} -> {command}"]
    if dry_run:
        return 0, messages
    atomic_json(receipt_file, pending, 0o600)
    try:
        atomic_bytes(path, content, mode, before)
    except SettingsChangedError:
        remove_durable(receipt_file)
        raise
    atomic_json(receipt_file, committed_receipt(pending), 0o600)
    return 0, messages


def activate(
    config: installer.Config,
    path: Path,
    state_root: Path,
    dry_run: bool,
) -> tuple[int, list[str]]:
    with installer.installer_lock(config):
        return _activate(config, path, state_root, dry_run)


def restored_settings(settings: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    statusline = settings.get("statusLine") or {}
    for key, previous in receipt["previous"].items():
        if previous["present"]:
            statusline[key] = previous["value"]
        else:
            statusline.pop(key, None)
    if statusline:
        settings["statusLine"] = statusline
    else:
        settings.pop("statusLine", None)
    return settings


def _deactivate(
    path: Path,
    state_root: Path,
    dry_run: bool,
) -> tuple[int, list[str]]:
    receipt_file = receipt_path(state_root)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    if receipt is None:
        # Decision 9: deactivating an already-inactive statusline performs no effect and
        # names no refusal -- it is the requested end state, already true. EXIT_OK, never
        # EXIT_REFUSED; see the module docstring's exit table.
        return EXIT_OK, ["statusline is not managed"]
    if receipt.get("settings") != str(path):
        raise StatuslineError("statusline receipt targets a different Claude settings path")
    settings, before = load_settings(path)
    statusline = settings.get("statusLine") or {}
    managed = receipt["managed"]
    for key, value in managed.items():
        if statusline.get(key, object()) != value:
            raise StatuslineError(f"statusLine.{key} changed after activation; preserving operator edit")
    settings = restored_settings(settings, receipt)
    mode = before.get("identity", {}).get("mode", 0o600)
    content = json_bytes(settings)
    pending = {
        **committed_receipt(receipt),
        "phase": "pending",
        "operation": "deactivate",
        "before": before,
        "after": after_snapshot(content, mode),
    }
    messages = [f"would deactivate: {path}" if dry_run else f"deactivated: {path}"]
    if dry_run:
        return 0, messages
    atomic_json(receipt_file, pending, 0o600)
    try:
        atomic_bytes(path, content, mode, before)
    except SettingsChangedError:
        atomic_json(receipt_file, committed_receipt(pending), 0o600)
        raise
    remove_durable(receipt_file)
    return 0, messages


def deactivate(
    config: installer.Config,
    path: Path,
    state_root: Path,
    dry_run: bool,
) -> tuple[int, list[str]]:
    with installer.installer_lock(config):
        return _deactivate(path, state_root, dry_run)


def _status(path: Path, state_root: Path) -> tuple[int, list[str]]:
    settings, _ = load_settings(path)
    receipt = load_receipt(receipt_path(state_root))
    statusline = settings.get("statusLine") or {}
    # Decision 9: `_status` itself never mutates anything -- it only reads settings and the
    # receipt -- so every branch below is a successfully answered read-only query: EXIT_OK
    # regardless of which of the five states it names. (`status()`, the caller just below,
    # still takes `installer.installer_lock`, which DOES create the lock file and its parent
    # directory -- that is the one real effect this read path admits, and it is not one of the
    # five states named here.) The five states stay distinguished in the returned
    # MESSAGE, never in the exit code; a real read failure (corrupt settings, unreadable
    # receipt) raises StatuslineError before reaching this function and is reported at
    # EXIT_REFUSED by main() instead.
    if receipt is None:
        if statusline:
            return EXIT_OK, [f"unmanaged statusline: {path}"]
        return EXIT_OK, [f"statusline inactive: {path}"]
    if receipt.get("phase") == "pending":
        return EXIT_OK, [f"statusline {receipt['operation']} recovery pending: {path}"]
    managed = receipt["managed"]
    if receipt.get("settings") != str(path) or any(statusline.get(key, object()) != value for key, value in managed.items()):
        return EXIT_OK, [f"statusline conflict: {path}"]
    return EXIT_OK, [f"statusline active: {path} -> {managed['command']}"]


def status(
    config: installer.Config,
    path: Path,
    state_root: Path,
) -> tuple[int, list[str]]:
    with installer.installer_lock(config):
        return _status(path, state_root)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "activate", "deactivate"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def ledger_config(home: Path, state_root: Path) -> installer.Config:
    """The installer configuration this module borrows, for the ledger row and the shared lock.

    ``--home`` is the one input that selects the row, exactly as it selects it for
    ``bundle:install``: the destination is ``<home>/.claude/statusline/agentic-sdlc-statusline``.
    ``--claude-config-dir`` deliberately does NOT move it -- that option relocates the settings
    document this module writes, and the installer has no such option, so honouring it here would
    look for a row at a path no install ever wrote.

    ``dry_run`` is False even under ``--dry-run``: it governs the installer's own writes, none of
    which this module performs, and passing True would skip the shared lock and let a
    ``bundle:uninstall`` remove the command between resolving it and reporting it. Taking the lock
    creates the lock file and its parent directory, which ``_status`` names as the one real effect
    its read path admits. ``codex_home`` is unused on this path and is the Claude home rather than
    a second invented root; ``mode`` is unused too, because this module publishes nothing.
    """
    return installer.Config(
        Path(__file__).resolve().parents[1],
        home,
        home,
        "auto",
        False,
        "claude",
        state_root,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = absolute(args.home)
    state_root = absolute(args.state_root) if args.state_root else state_root_for(home)
    path = settings_path(home, args.claude_config_dir)
    config = ledger_config(home, state_root)
    try:
        code, messages = {
            "status": lambda: status(config, path, state_root),
            "activate": lambda: activate(config, path, state_root, args.dry_run),
            "deactivate": lambda: deactivate(config, path, state_root, args.dry_run),
        }[args.command]()
    except (StatuslineError, installer.InstallerError) as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
