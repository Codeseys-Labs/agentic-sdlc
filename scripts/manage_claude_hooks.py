#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Inspect or explicitly wire installed Claude Code agent hooks into settings.

This is the separately authorized ENABLE step for the `hook` entry kind. `lifecycle:install` lands
hook bytes as owned lifecycle entries and never touches settings; nothing here is reachable from
any install, gate, or `contributor:setup` path. The ownership unit is ONE ELEMENT of a settings
`hooks.<Event>` array (the platform merges those arrays across scopes and a user's own entries
legitimately live beside ours), so activation appends exactly one matcher-group element and
records it in a receipt, and deactivation removes only an element deep-equal to that receipt.
Foreign or modified elements are preserved and reported, never guessed at. Activation refuses,
by name, to wire a hook file that is absent, unowned, or digest-drifted from its bundle
ownership record: enabling a path the lifecycle does not currently own would turn a foreign
file into injected session context.

Exit vocabulary, mirrored from scripts/manage_claude_statusline.py:
  0  every completed answer, whether the mutating verb performed its effect (`activate`,
     `deactivate`), reported the requested end state already true (`already active`,
     `not managed`), or `status` merely read and reported per-hook states in the returned
     MESSAGE, never in the exit code.
  2  a real refusal or failure: a malformed argument, an unreadable or foreign-shaped
     settings/receipt file, an unowned or drifted hook file, or a settings change detected
     mid-write.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shlex
import sys
from typing import Any, Iterator

import install_skill_bundle as installer
import manage_claude_statusline as settings_io


RECEIPT_VERSION = 1
HOOK_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
HOOK_SHEBANG = "#!/bin/sh"
HOOK_HEADER_PREFIX = "# hook: "
HOOK_EVENT_PREFIX = "# hook-event: "
HOOK_MATCHER_PREFIX = "# hook-matcher: "
#: The closed event/matcher vocabulary this activator can wire; one entry per supported event.
#: scripts/validate_bundle.py holds the same table for the authored-shape gate.
HOOK_EVENT_MATCHERS = {
    "SessionStart": frozenset({"startup", "resume", "clear", "compact", "fork"}),
}
COMMITTED_RECEIPT_FIELDS = frozenset(
    {"version", "phase", "settings", "hook", "event", "element", "hook_digest",
     "created_hooks_key", "created_event_key"}
)
PENDING_RECEIPT_FIELDS = COMMITTED_RECEIPT_FIELDS | {"operation", "before", "after"}

# Single derivation point for this module's exit vocabulary; see the module docstring's table.
EXIT_OK = 0
EXIT_REFUSED = 2


class HooksError(RuntimeError):
    pass


def receipts_root(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-claude-hooks"


def receipt_path(state_root: Path, name: str) -> Path:
    return receipts_root(state_root) / f"{name}.json"


def installer_state_path(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-installer" / "state.json"


@contextmanager
def hooks_lock(state_root: Path, dry_run: bool) -> Iterator[None]:
    """Serialize write-capable hook-manager commands for one operator state root."""
    if dry_run:
        yield
        return
    root = receipts_root(state_root)
    root.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(root / "manager.lock", os.O_RDWR | os.O_CREAT, 0o600)
    host_is_windows = os.name == "nt"
    try:
        if host_is_windows:
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if host_is_windows:
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def load_settings(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot, content = settings_io.file_snapshot(path)
    if content is None:
        return {}, snapshot
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HooksError(f"cannot read Claude settings {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise HooksError(f"Claude settings must contain a JSON object: {path}")
    hooks = value.get("hooks")
    if "hooks" in value and not isinstance(hooks, dict):
        raise HooksError(f"Claude settings hooks must be a JSON object; preserving the foreign shape: {path}")
    return value, snapshot


def hook_command(destination: Path) -> str:
    # Claude invokes a hook command through a shell. `sh <path>` keeps the entry independent of
    # the installed file's execute bit, and quoting keeps spaces one pathname, not shell syntax.
    return f"sh {shlex.quote(str(destination))}"


def managed_element(matcher: str, destination: Path) -> dict[str, Any]:
    return {"matcher": matcher, "hooks": [{"type": "command", "command": hook_command(destination)}]}


def validate_element(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {"matcher", "hooks"}:
        return False
    if not isinstance(value["matcher"], str) or not isinstance(value["hooks"], list):
        return False
    if len(value["hooks"]) != 1:
        return False
    inner = value["hooks"][0]
    return (
        isinstance(inner, dict)
        and set(inner) == {"type", "command"}
        and inner["type"] == "command"
        and isinstance(inner["command"], str)
    )


def validate_receipt(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HooksError(f"invalid hook receipt: {path}")
    phase = value.get("phase")
    digest = value.get("hook_digest")
    if (
        value.get("version") != RECEIPT_VERSION
        or phase not in {"committed", "pending"}
        or not isinstance(value.get("settings"), str)
        or not Path(value["settings"]).is_absolute()
        or not isinstance(value.get("hook"), str)
        or not HOOK_NAME_PATTERN.fullmatch(value["hook"])
        or value.get("event") not in HOOK_EVENT_MATCHERS
        or not validate_element(value.get("element"))
        or not isinstance(digest, str)
        or len(digest) != 64
        or not isinstance(value.get("created_hooks_key"), bool)
        or not isinstance(value.get("created_event_key"), bool)
    ):
        raise HooksError(f"invalid hook receipt: {path}")
    if phase == "committed":
        if set(value) != COMMITTED_RECEIPT_FIELDS:
            raise HooksError(f"invalid hook receipt: {path}")
        return value
    if (
        set(value) != PENDING_RECEIPT_FIELDS
        or value.get("operation") not in {"activate", "deactivate"}
        or not settings_io.validate_snapshot(value.get("before"))
        or not settings_io.validate_snapshot(value.get("after"), after=True)
    ):
        raise HooksError(f"invalid pending hook transaction: {path}")
    return value


def load_receipt(path: Path) -> dict[str, Any] | None:
    snapshot, content = settings_io.file_snapshot(path)
    del snapshot
    if content is None:
        return None
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HooksError(f"cannot read hook receipt {path}: {exc}") from exc
    return validate_receipt(value, path)


def committed_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt[key] for key in COMMITTED_RECEIPT_FIELDS - {"phase"}} | {"phase": "committed"}


def recover_pending(receipt_file: Path, receipt: dict[str, Any] | None, *, dry_run: bool) -> dict[str, Any] | None:
    if receipt is None or receipt.get("phase") != "pending":
        return receipt
    if dry_run:
        raise HooksError("a pending hook transaction requires recovery; rerun without --dry-run")
    target = Path(receipt["settings"])
    current, _ = settings_io.file_snapshot(target)
    operation = receipt["operation"]
    if settings_io.matches_after(current, receipt["after"]):
        settings_io.sync_directory(target.parent)
        if operation == "activate":
            committed = committed_receipt(receipt)
            settings_io.atomic_json(receipt_file, committed, 0o600)
            return committed
        settings_io.remove_durable(receipt_file)
        return None
    if current == receipt["before"]:
        if operation == "activate":
            settings_io.remove_durable(receipt_file)
            return None
        committed = committed_receipt(receipt)
        settings_io.atomic_json(receipt_file, committed, 0o600)
        return committed
    raise HooksError(
        f"pending hook {operation} transaction conflicts with current settings; preserving both: {target}"
    )


def parse_hook_header(name: str, content: bytes, destination: Path) -> tuple[str, str]:
    """Parse the installed hook's declared event and matcher from its four header lines."""
    def refuse(reason: str) -> HooksError:
        return HooksError(f"installed hook {name} has an invalid header ({reason}); refusing to wire it: {destination}")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise refuse("not UTF-8 text") from exc
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if len(lines) < 4 or lines[0] != HOOK_SHEBANG:
        raise refuse(f"line 1 must be exactly '{HOOK_SHEBANG}'")
    if lines[1] != f"{HOOK_HEADER_PREFIX}{name}":
        raise refuse("line 2 must declare the installed hook name")
    if not lines[2].startswith(HOOK_EVENT_PREFIX):
        raise refuse("line 3 must declare the hook event")
    event = lines[2][len(HOOK_EVENT_PREFIX) :].strip()
    if event not in HOOK_EVENT_MATCHERS:
        raise refuse(f"unknown hook-event '{event}'")
    if not lines[3].startswith(HOOK_MATCHER_PREFIX):
        raise refuse("line 4 must declare the hook matcher")
    tokens = [token.strip() for token in lines[3][len(HOOK_MATCHER_PREFIX) :].split("|")]
    for token in tokens:
        if token not in HOOK_EVENT_MATCHERS[event]:
            raise refuse(f"unknown hook-matcher token '{token}'")
    return event, "|".join(tokens)


def owned_hook_content(name: str, hooks_dir: Path, state_path: Path) -> tuple[Path, bytes]:
    """Return the installed hook path and bytes, or refuse an absent/unowned/drifted file."""
    destination = hooks_dir / f"{name}.sh"
    if not os.path.lexists(destination):
        raise HooksError(f"installed hook is absent: {destination} (run: mise run lifecycle:install -- --agent claude)")
    record = installer.load_state(state_path)["entries"].get(str(destination))
    if record is None or record.get("kind") != "hook":
        raise HooksError(f"hook is not owned by the bundle lifecycle: {destination} (run: mise run lifecycle:install -- --agent claude)")
    try:
        content = destination.read_bytes()
    except OSError as exc:
        raise HooksError(f"cannot read installed hook {destination}: {exc}") from exc
    # Both halves are required: `entry_matches_record` proves the destination's mode/target shape
    # is still the published one, and the live-bytes digest proves the CONTENT the activator would
    # inject is still the recorded bytes even for a link whose source drifted after install.
    if not installer.entry_matches_record(destination, record) or settings_io.digest_bytes(content) != record.get("digest"):
        raise HooksError(f"installed hook drifted from its ownership record: {destination}; refusing to enable unowned bytes")
    return destination, content


def _activate(name: str, settings_path: Path, hooks_dir: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    receipt_file = receipt_path(state_root, name)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    destination, content = owned_hook_content(name, hooks_dir, installer_state_path(state_root))
    event, matcher = parse_hook_header(name, content, destination)
    element = managed_element(matcher, destination)
    settings, before = load_settings(settings_path)
    hooks_value = settings.get("hooks")
    created_hooks_key = "hooks" not in settings
    hooks_obj = hooks_value if isinstance(hooks_value, dict) else {}
    event_value = hooks_obj.get(event)
    if event in hooks_obj and not isinstance(event_value, list):
        raise HooksError(f"Claude settings hooks.{event} must be a JSON array; preserving the foreign shape: {settings_path}")
    created_event_key = event not in hooks_obj
    event_list = event_value if isinstance(event_value, list) else []
    if any(existing == element for existing in event_list):
        # The requested end state is already true. `receipt is None` here means the deep-equal
        # element is someone else's bytes; writing a receipt would claim ownership of an element
        # this manager never appended, so nothing is written in either case.
        return EXIT_OK, [f"already active: hooks.{event} element for {destination}"]
    event_list = [*event_list, element]
    hooks_obj = dict(hooks_obj)
    hooks_obj[event] = event_list
    settings["hooks"] = hooks_obj
    mode = before.get("identity", {}).get("mode", 0o600)
    content_bytes = settings_io.json_bytes(settings)
    pending = {
        "version": RECEIPT_VERSION,
        "phase": "pending",
        "operation": "activate",
        "settings": str(settings_path),
        "hook": name,
        "event": event,
        "element": element,
        "hook_digest": settings_io.digest_bytes(content),
        "created_hooks_key": created_hooks_key,
        "created_event_key": created_event_key,
        "before": before,
        "after": settings_io.after_snapshot(content_bytes, mode),
    }
    messages = [
        f"would activate: {settings_path} hooks.{event} -> {destination}"
        if dry_run
        else f"activated: {settings_path} hooks.{event} -> {destination}"
    ]
    if receipt is not None:
        messages.append(f"note: replacing an existing receipt for hook {name} whose settings element was already gone")
    if dry_run:
        return EXIT_OK, messages
    settings_io.atomic_json(receipt_file, pending, 0o600)
    try:
        settings_io.atomic_bytes(settings_path, content_bytes, mode, before)
    except settings_io.SettingsChangedError:
        settings_io.remove_durable(receipt_file)
        raise
    settings_io.atomic_json(receipt_file, committed_receipt(pending), 0o600)
    return EXIT_OK, messages


def activate(name: str, settings_path: Path, hooks_dir: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    with hooks_lock(state_root, dry_run):
        return _activate(name, settings_path, hooks_dir, state_root, dry_run)


def _deactivate(name: str, settings_path: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    receipt_file = receipt_path(state_root, name)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    if receipt is None:
        # Deactivating an unmanaged hook performs no effect and names no refusal -- it is the
        # requested end state, already true. EXIT_OK, never EXIT_REFUSED.
        return EXIT_OK, [f"hook {name} is not managed"]
    if receipt.get("settings") != str(settings_path):
        raise HooksError(f"hook {name} receipt targets a different Claude settings path")
    settings, before = load_settings(settings_path)
    event = receipt["event"]
    element = receipt["element"]
    hooks_value = settings.get("hooks")
    hooks_obj = hooks_value if isinstance(hooks_value, dict) else {}
    event_value = hooks_obj.get(event)
    event_list = event_value if isinstance(event_value, list) else []
    index = next((i for i, existing in enumerate(event_list) if existing == element), None)
    if index is None:
        # No element deep-equal to the receipt's exists, so there is nothing of ours left to
        # remove: every remaining hooks.<event> element is foreign or operator-modified and is
        # preserved untouched. Only the receipt is released, so a stuck receipt never deadlocks
        # deactivation and the operator's own edits are never guessed at.
        if dry_run:
            return EXIT_OK, [f"would release: managed hooks.{event} element for hook {name} is already absent"]
        settings_io.remove_durable(receipt_file)
        return EXIT_OK, [
            f"released: managed hooks.{event} element for hook {name} was removed or modified after "
            f"activation; every remaining element is preserved: {settings_path}"
        ]
    event_list = [existing for i, existing in enumerate(event_list) if i != index]
    hooks_obj = dict(hooks_obj)
    hooks_obj[event] = event_list
    if not event_list and receipt["created_event_key"]:
        hooks_obj.pop(event)
    settings["hooks"] = hooks_obj
    if not hooks_obj and receipt["created_hooks_key"]:
        settings.pop("hooks")
    mode = before.get("identity", {}).get("mode", 0o600)
    content_bytes = settings_io.json_bytes(settings)
    pending = {
        **committed_receipt(receipt),
        "phase": "pending",
        "operation": "deactivate",
        "before": before,
        "after": settings_io.after_snapshot(content_bytes, mode),
    }
    messages = [f"would deactivate: {settings_path} hooks.{event}" if dry_run else f"deactivated: {settings_path} hooks.{event}"]
    if dry_run:
        return EXIT_OK, messages
    settings_io.atomic_json(receipt_file, pending, 0o600)
    try:
        settings_io.atomic_bytes(settings_path, content_bytes, mode, before)
    except settings_io.SettingsChangedError:
        settings_io.atomic_json(receipt_file, committed_receipt(pending), 0o600)
        raise
    settings_io.remove_durable(receipt_file)
    return EXIT_OK, messages


def deactivate(name: str, settings_path: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    with hooks_lock(state_root, dry_run):
        return _deactivate(name, settings_path, state_root, dry_run)


def owned_hook_names(state_path: Path, hooks_dir: Path) -> dict[str, dict[str, Any]]:
    names: dict[str, dict[str, Any]] = {}
    entries = installer.load_state(state_path)["entries"]
    for key, record in entries.items():
        destination = Path(key)
        if record.get("kind") == "hook" and destination.parent == hooks_dir:
            names[destination.stem] = record
    return names


def status(settings_path: Path, hooks_dir: Path, state_root: Path, only: str | None) -> tuple[int, list[str]]:
    settings, _ = load_settings(settings_path)
    records = owned_hook_names(installer_state_path(state_root), hooks_dir)
    receipt_names = {path.stem for path in receipts_root(state_root).glob("*.json")}
    names = sorted(set(records) | receipt_names)
    if only is not None:
        names = [name for name in names if name == only]
    hooks_obj = settings.get("hooks") if isinstance(settings.get("hooks"), dict) else {}
    messages: list[str] = []
    receipts: list[dict[str, Any]] = []
    active = inactive = conflict = 0
    for name in names:
        receipt = load_receipt(receipt_path(state_root, name))
        if receipt is not None:
            receipts.append(receipt)
        destination = hooks_dir / f"{name}.sh"
        record = records.get(name)
        if record is None:
            installed_state = "unowned"
        elif not os.path.lexists(destination):
            installed_state = "absent (run: mise run lifecycle:install -- --agent claude)"
        elif not installer.entry_matches_record(destination, record):
            installed_state = "drifted from its ownership record"
        else:
            installed_state = "installed"
        if receipt is None:
            wired_state = "inactive"
            inactive += 1
        elif receipt.get("phase") == "pending":
            wired_state = f"{receipt['operation']} recovery pending"
            conflict += 1
        else:
            event_value = hooks_obj.get(receipt["event"])
            event_list = event_value if isinstance(event_value, list) else []
            if any(existing == receipt["element"] for existing in event_list):
                wired_state = "active"
                active += 1
            else:
                wired_state = "receipt without its settings element (run deactivate to release it)"
                conflict += 1
        messages.append(f"hook {name}: {installed_state}, {wired_state}")
    for event in sorted(hooks_obj):
        event_value = hooks_obj.get(event)
        if not isinstance(event_value, list):
            continue
        owned_elements = [receipt["element"] for receipt in receipts if receipt.get("event") == event]
        foreign = sum(1 for existing in event_value if not any(existing == owned for owned in owned_elements))
        if foreign:
            messages.append(f"foreign hooks.{event} elements: {foreign} (preserved)")
    # lifecycle:status doctrine: always end with one terminal line, so a silent exit 0 is a defect.
    if names:
        messages.append(f"{active} active, {inactive} inactive, {conflict} conflict")
    else:
        messages.append("no owned hooks for this plane (run: mise run lifecycle:install -- --agent claude)")
    return EXIT_OK, messages


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "activate", "deactivate"))
    parser.add_argument("--hook", help="hook name (required for activate and deactivate; per-hook, never all)")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = settings_io.absolute(args.home)
    root = settings_io.absolute(args.claude_config_dir) if args.claude_config_dir else home / ".claude"
    settings_path = root / "settings.json"
    hooks_dir = root / "hooks"
    state_root = settings_io.absolute(args.state_root) if args.state_root else installer.state_directory()
    try:
        if args.command in {"activate", "deactivate"}:
            if not args.hook or not HOOK_NAME_PATTERN.fullmatch(args.hook):
                raise HooksError(f"{args.command} requires --hook <lowercase-slug-name>")
            if args.command == "activate":
                code, messages = activate(args.hook, settings_path, hooks_dir, state_root, args.dry_run)
            else:
                code, messages = deactivate(args.hook, settings_path, state_root, args.dry_run)
        else:
            code, messages = status(settings_path, hooks_dir, state_root, args.hook)
    except (HooksError, settings_io.StatuslineError, installer.InstallerError) as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
