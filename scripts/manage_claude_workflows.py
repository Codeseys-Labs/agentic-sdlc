#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Inspect or explicitly enable installed Claude Code workflows for one target repository.

This is the separately authorized ENABLE step for the `workflow` entry kind. `lifecycle:install`
lands workflow bytes in the home plane (`<claude-home>/.claude/workflows/`) as owned lifecycle
entries, and the live host discovers workflows BY NAME only from a project's own
`.claude/workflows/`, read once at session start (measured 2026-08-24, recorded on
agentic-sdlc-4d2b) — so installing distributes bytes no session ever discovers, and enablement
is placing the workflow into a target repository's `.claude/workflows/`. Nothing here is
reachable from any install, gate, or `contributor:setup` path.

The ownership unit is ONE FILE in the TARGET repository: `<target>/.claude/workflows/<name>.js`,
recorded in a receipt keyed by workflow name and destination. The placed file is a COPY of the
owned installed bytes, never a symlink: a repo-committed `.claude/workflows/` entry must be
self-contained, because a link into the operator's home would embed a user-specific absolute
path (forbidden in distributable payload), break for every other clone of the target, and let a
later bundle refresh silently change what the target's sessions execute without any new per-repo
authorization. Activation refuses, by name, to place a workflow file that is absent, unowned, or
digest-drifted from its bundle ownership record, and refuses an occupied foreign destination;
deactivation removes only a copy whose bytes still match the receipt. Foreign and modified files
are preserved and reported, never guessed at. Because the host snapshots the workflow name
registry at session start, every completed activate/deactivate names that fact: the change takes
effect at the target's next session.

Exit vocabulary, mirrored from scripts/manage_claude_hooks.py:
  0  every completed answer, whether the mutating verb performed its effect (`activate`,
     `deactivate`), reported the requested end state already true (`already active`,
     `not managed`), or `status` merely read and reported per-workflow states in the returned
     MESSAGE, never in the exit code.
  2  a real refusal or failure: a malformed argument, an unreadable or foreign-shaped
     target/receipt file, an unowned or drifted workflow file, an occupied foreign
     destination, or a destination change detected mid-write.
"""

from __future__ import annotations

import argparse
import contextlib
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterator

import install_skill_bundle as installer
import manage_claude_statusline as settings_io


RECEIPT_VERSION = 1
WORKFLOW_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
WORKFLOW_HEADER_PREFIX = "// workflow: "
#: Mode for a freshly placed copy: a repo-visible document the host reads, never an executable.
ENABLED_FILE_MODE = 0o644
COMMITTED_RECEIPT_FIELDS = frozenset(
    {"version", "phase", "target", "workflow", "workflow_digest",
     "created_claude_dir", "created_workflows_dir"}
)
PENDING_RECEIPT_FIELDS = COMMITTED_RECEIPT_FIELDS | {"operation", "before", "after"}
#: Requirement from the agentic-sdlc-de40 seed: the step's output states the session-start
#: snapshot fact, because a mid-session placement or removal is invisible to the registry.
SESSION_SNAPSHOT_NOTE = (
    "note: the Workflow name registry is read at session start; this change takes effect at the"
    " target's next Claude Code session"
)

# Single derivation point for this module's exit vocabulary; see the module docstring's table.
EXIT_OK = 0
EXIT_REFUSED = 2


class WorkflowsError(RuntimeError):
    pass


def receipts_root(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-claude-workflows"


def receipt_path(state_root: Path, name: str, destination: Path) -> Path:
    # One receipt per (workflow, destination): the same workflow may be enabled in many target
    # repositories, so the destination participates in the key. The digest prefix keeps the
    # filename bounded; the loaded receipt's exact `target` value is still verified by callers.
    key = hashlib.sha256(str(destination).encode("utf-8")).hexdigest()[:16]
    return receipts_root(state_root) / f"{name}.{key}.json"


def installer_state_path(state_root: Path) -> Path:
    return state_root / "agentic-sdlc-installer" / "state.json"


def enabled_destination(target: Path, name: str) -> Path:
    return target / ".claude" / "workflows" / f"{name}.js"


@contextmanager
def workflows_lock(state_root: Path, dry_run: bool) -> Iterator[None]:
    """Serialize write-capable workflow-manager commands for one operator state root."""
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


def validate_after(value: Any) -> bool:
    # A deactivate transaction's end state is file ABSENCE, which the statusline validator's
    # `after=True` shape deliberately excludes for a settings file that always exists.
    if value == {"exists": False}:
        return True
    return settings_io.validate_snapshot(value, after=True)


def snapshot_matches_after(snapshot: dict[str, Any], after: dict[str, Any]) -> bool:
    if after == {"exists": False}:
        return snapshot == {"exists": False}
    return settings_io.matches_after(snapshot, after)


def validate_receipt(value: Any, path: Path) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowsError(f"invalid workflow receipt: {path}")
    phase = value.get("phase")
    digest = value.get("workflow_digest")
    target = value.get("target")
    name = value.get("workflow")
    if (
        value.get("version") != RECEIPT_VERSION
        or phase not in {"committed", "pending"}
        or not isinstance(target, str)
        or not Path(target).is_absolute()
        or not isinstance(name, str)
        or not WORKFLOW_NAME_PATTERN.fullmatch(name)
        or Path(target).name != f"{name}.js"
        or not isinstance(digest, str)
        or len(digest) != 64
        or not isinstance(value.get("created_claude_dir"), bool)
        or not isinstance(value.get("created_workflows_dir"), bool)
    ):
        raise WorkflowsError(f"invalid workflow receipt: {path}")
    if phase == "committed":
        if set(value) != COMMITTED_RECEIPT_FIELDS:
            raise WorkflowsError(f"invalid workflow receipt: {path}")
        return value
    if (
        set(value) != PENDING_RECEIPT_FIELDS
        or value.get("operation") not in {"activate", "deactivate"}
        or not settings_io.validate_snapshot(value.get("before"))
        or not validate_after(value.get("after"))
    ):
        raise WorkflowsError(f"invalid pending workflow transaction: {path}")
    return value


def load_receipt(path: Path) -> dict[str, Any] | None:
    snapshot, content = settings_io.file_snapshot(path)
    del snapshot
    if content is None:
        return None
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowsError(f"cannot read workflow receipt {path}: {exc}") from exc
    return validate_receipt(value, path)


def committed_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: receipt[key] for key in COMMITTED_RECEIPT_FIELDS - {"phase"}} | {"phase": "committed"}


def remove_created_directories(receipt: dict[str, Any]) -> None:
    """Remove only the containers this manager created, and only while they are empty."""
    destination = Path(receipt["target"])
    pairs = (
        (destination.parent, receipt["created_workflows_dir"]),
        (destination.parent.parent, receipt["created_claude_dir"]),
    )
    for directory, created in pairs:
        if not created:
            return
        try:
            # rmdir refuses a non-empty directory, so a foreign sibling that appeared after
            # activation stops the cleanup and is preserved rather than guessed at.
            os.rmdir(directory)
        except OSError:
            return
        with contextlib.suppress(OSError):
            settings_io.sync_directory(directory.parent)


def recover_pending(receipt_file: Path, receipt: dict[str, Any] | None, *, dry_run: bool) -> dict[str, Any] | None:
    if receipt is None or receipt.get("phase") != "pending":
        return receipt
    if dry_run:
        raise WorkflowsError("a pending workflow transaction requires recovery; rerun without --dry-run")
    target = Path(receipt["target"])
    current, _ = settings_io.file_snapshot(target)
    operation = receipt["operation"]
    if snapshot_matches_after(current, receipt["after"]):
        if target.parent.is_dir():
            settings_io.sync_directory(target.parent)
        if operation == "activate":
            committed = committed_receipt(receipt)
            settings_io.atomic_json(receipt_file, committed, 0o600)
            return committed
        remove_created_directories(receipt)
        settings_io.remove_durable(receipt_file)
        return None
    if current == receipt["before"]:
        if operation == "activate":
            settings_io.remove_durable(receipt_file)
            return None
        committed = committed_receipt(receipt)
        settings_io.atomic_json(receipt_file, committed, 0o600)
        return committed
    raise WorkflowsError(
        f"pending workflow {operation} transaction conflicts with the current file; preserving both: {target}"
    )


def parse_workflow_header(name: str, content: bytes, source: Path) -> None:
    """Check the installed workflow's declared-name header before its bytes are enabled anywhere.

    The full authored grammar (meta literal, parseability, no module loads, no pins) is the
    validator's gate over the repository bytes, and the digest check in `owned_workflow_content`
    ties the installed bytes to what that gate admitted. What is re-checked here is the one line
    that IS this manager's contract: the file self-declares the name it will be enabled under.
    """
    def refuse(reason: str) -> WorkflowsError:
        return WorkflowsError(
            f"installed workflow {name} has an invalid header ({reason}); refusing to enable it: {source}"
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise refuse("not UTF-8 text") from exc
    first_line = text.split("\n", 1)[0].rstrip("\r")
    if not first_line.startswith(WORKFLOW_HEADER_PREFIX):
        raise refuse(f"line 1 must start with '{WORKFLOW_HEADER_PREFIX}'")
    if first_line[len(WORKFLOW_HEADER_PREFIX):].strip() != name:
        raise refuse("line 1 must declare the installed workflow name")


def owned_workflow_content(name: str, workflows_dir: Path, state_path: Path) -> tuple[Path, bytes]:
    """Return the installed workflow path and bytes, or refuse an absent/unowned/drifted file."""
    source = workflows_dir / f"{name}.js"
    if not os.path.lexists(source):
        raise WorkflowsError(f"installed workflow is absent: {source} (run: mise run lifecycle:install -- --agent claude)")
    record = installer.load_state(state_path)["entries"].get(str(source))
    if record is None or record.get("kind") != "workflow":
        raise WorkflowsError(f"workflow is not owned by the bundle lifecycle: {source} (run: mise run lifecycle:install -- --agent claude)")
    try:
        content = source.read_bytes()
    except OSError as exc:
        raise WorkflowsError(f"cannot read installed workflow {source}: {exc}") from exc
    # Both halves are required: `entry_matches_record` proves the source's mode/target shape is
    # still the published one, and the live-bytes digest proves the CONTENT this manager would
    # copy into a target repository is still the recorded bytes even for a link whose source
    # drifted after install.
    if not installer.entry_matches_record(source, record) or settings_io.digest_bytes(content) != record.get("digest"):
        raise WorkflowsError(f"installed workflow drifted from its ownership record: {source}; refusing to enable unowned bytes")
    return source, content


def _activate(name: str, target: Path, workflows_dir: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    destination = enabled_destination(target, name)
    receipt_file = receipt_path(state_root, name, destination)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    if receipt is not None and receipt.get("target") != str(destination):
        raise WorkflowsError(f"workflow {name} receipt targets a different destination path")
    source, content = owned_workflow_content(name, workflows_dir, installer_state_path(state_root))
    parse_workflow_header(name, content, source)
    before, existing = settings_io.file_snapshot(destination)
    refreshing = False
    notes: list[str] = []
    if existing is not None:
        if existing == content:
            # The requested end state is already true. `receipt is None` here means the
            # byte-identical copy is someone else's file; writing a receipt would claim
            # ownership of bytes this manager never placed, so nothing is written either way.
            return EXIT_OK, [f"already active: {destination}"]
        if receipt is None:
            raise WorkflowsError(f"destination is occupied by a foreign workflow file; preserving it: {destination}")
        if settings_io.digest_bytes(existing) != receipt["workflow_digest"]:
            raise WorkflowsError(
                f"enabled workflow copy was modified after activation; preserving operator edit:"
                f" {destination} (run deactivate to release the receipt)"
            )
        # The enabled copy still matches its receipt while the owned source moved on: replacing
        # it destroys nothing of the operator's, exactly the installer's owned-copy refresh rule.
        refreshing = True
    if receipt is not None:
        # The eventual deactivate must restore the ORIGINAL prestate, so the flags recorded at
        # first activation survive every refresh and re-placement.
        created_claude_dir = receipt["created_claude_dir"]
        created_workflows_dir = receipt["created_workflows_dir"]
        if existing is None:
            notes.append(f"note: replacing an existing receipt for workflow {name} whose enabled copy was already gone")
    else:
        created_claude_dir = not (target / ".claude").exists()
        created_workflows_dir = not destination.parent.exists()
    mode = before.get("identity", {}).get("mode", ENABLED_FILE_MODE)
    pending = {
        "version": RECEIPT_VERSION,
        "phase": "pending",
        "operation": "activate",
        "target": str(destination),
        "workflow": name,
        "workflow_digest": settings_io.digest_bytes(content),
        "created_claude_dir": created_claude_dir,
        "created_workflows_dir": created_workflows_dir,
        "before": before,
        "after": settings_io.after_snapshot(content, mode),
    }
    verb = "refresh" if refreshing else "activate"
    past = "refreshed" if refreshing else "activated"
    messages = [f"would {verb}: {destination} <- {source}" if dry_run else f"{past}: {destination} <- {source}"]
    messages.extend(notes)
    messages.append(SESSION_SNAPSHOT_NOTE)
    if dry_run:
        return EXIT_OK, messages
    settings_io.atomic_json(receipt_file, pending, 0o600)
    try:
        settings_io.atomic_bytes(destination, content, mode, before)
    except settings_io.SettingsChangedError:
        # Disarm without losing history: a prior committed receipt still owns the untouched copy.
        if receipt is not None:
            settings_io.atomic_json(receipt_file, receipt, 0o600)
        else:
            settings_io.remove_durable(receipt_file)
        raise
    settings_io.atomic_json(receipt_file, committed_receipt(pending), 0o600)
    return EXIT_OK, messages


def activate(name: str, target: Path, workflows_dir: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    with workflows_lock(state_root, dry_run):
        return _activate(name, target, workflows_dir, state_root, dry_run)


def _deactivate(name: str, target: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    destination = enabled_destination(target, name)
    receipt_file = receipt_path(state_root, name, destination)
    receipt = recover_pending(receipt_file, load_receipt(receipt_file), dry_run=dry_run)
    if receipt is None:
        # Deactivating an unmanaged workflow performs no effect and names no refusal -- it is
        # the requested end state, already true. EXIT_OK, never EXIT_REFUSED.
        return EXIT_OK, [f"workflow {name} is not managed for this target"]
    if receipt.get("target") != str(destination):
        raise WorkflowsError(f"workflow {name} receipt targets a different destination path")
    before, existing = settings_io.file_snapshot(destination)
    if existing is None or settings_io.digest_bytes(existing) != receipt["workflow_digest"]:
        # No copy byte-identical to the receipt's is left, so there is nothing of ours to
        # remove: whatever occupies the destination is foreign or operator-modified and is
        # preserved untouched. Only the receipt is released, so a stuck receipt never deadlocks
        # deactivation and the operator's own edits are never guessed at.
        if dry_run:
            return EXIT_OK, [f"would release: the managed copy of workflow {name} is already absent or modified"]
        settings_io.remove_durable(receipt_file)
        return EXIT_OK, [
            f"released: the managed copy of workflow {name} was removed or modified after "
            f"activation; every remaining file is preserved: {destination}"
        ]
    pending = {
        **committed_receipt(receipt),
        "phase": "pending",
        "operation": "deactivate",
        "before": before,
        "after": {"exists": False},
    }
    messages = [f"would deactivate: {destination}" if dry_run else f"deactivated: {destination}"]
    messages.append(SESSION_SNAPSHOT_NOTE)
    if dry_run:
        return EXIT_OK, messages
    settings_io.atomic_json(receipt_file, pending, 0o600)
    current, _ = settings_io.file_snapshot(destination)
    if current != before:
        settings_io.atomic_json(receipt_file, committed_receipt(receipt), 0o600)
        raise settings_io.SettingsChangedError(
            f"workflow file changed before removal; preserving operator edit: {destination}"
        )
    settings_io.remove_durable(destination)
    remove_created_directories(receipt)
    settings_io.remove_durable(receipt_file)
    return EXIT_OK, messages


def deactivate(name: str, target: Path, state_root: Path, dry_run: bool) -> tuple[int, list[str]]:
    with workflows_lock(state_root, dry_run):
        return _deactivate(name, target, state_root, dry_run)


def owned_workflow_names(state_path: Path, workflows_dir: Path) -> dict[str, dict[str, Any]]:
    names: dict[str, dict[str, Any]] = {}
    entries = installer.load_state(state_path)["entries"]
    for key, record in entries.items():
        source = Path(key)
        if record.get("kind") == "workflow" and source.parent == workflows_dir:
            names[source.stem] = record
    return names


def target_receipts(state_root: Path, target: Path) -> dict[str, dict[str, Any]]:
    """Load every receipt whose destination lives in this target's workflow collection."""
    directory = target / ".claude" / "workflows"
    results: dict[str, dict[str, Any]] = {}
    for path in sorted(receipts_root(state_root).glob("*.json")):
        receipt = load_receipt(path)
        if receipt is not None and Path(receipt["target"]).parent == directory:
            results[receipt["workflow"]] = receipt
    return results


def status(target: Path, workflows_dir: Path, state_root: Path, only: str | None) -> tuple[int, list[str]]:
    records = owned_workflow_names(installer_state_path(state_root), workflows_dir)
    receipts = target_receipts(state_root, target)
    names = sorted(set(records) | set(receipts))
    if only is not None:
        names = [name for name in names if name == only]
    directory = target / ".claude" / "workflows"
    messages: list[str] = []
    active = inactive = conflict = 0
    for name in names:
        record = records.get(name)
        source = workflows_dir / f"{name}.js"
        if record is None:
            installed_state = "unowned"
        elif not os.path.lexists(source):
            installed_state = "absent (run: mise run lifecycle:install -- --agent claude)"
        elif not installer.entry_matches_record(source, record):
            installed_state = "drifted from its ownership record"
        else:
            installed_state = "installed"
        receipt = receipts.get(name)
        if receipt is None:
            enabled_state = "inactive"
            inactive += 1
        elif receipt.get("phase") == "pending":
            enabled_state = f"{receipt['operation']} recovery pending"
            conflict += 1
        else:
            snapshot, content = settings_io.file_snapshot(enabled_destination(target, name))
            del snapshot
            if content is not None and settings_io.digest_bytes(content) == receipt["workflow_digest"]:
                enabled_state = "active"
                active += 1
            else:
                enabled_state = "receipt without its enabled copy (run deactivate to release it)"
                conflict += 1
        messages.append(f"workflow {name}: {installed_state}, {enabled_state}")
    if directory.is_dir():
        owned_files = {f"{name}.js" for name in receipts}
        foreign = sum(1 for path in sorted(directory.iterdir()) if path.name not in owned_files)
        if foreign:
            messages.append(f"foreign workflow files in {directory}: {foreign} (preserved)")
    # lifecycle:status doctrine: always end with one terminal line, so a silent exit 0 is a defect.
    if names:
        messages.append(f"{active} active, {inactive} inactive, {conflict} conflict")
    else:
        messages.append("no owned workflows for this plane (run: mise run lifecycle:install -- --agent claude)")
    return EXIT_OK, messages


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "activate", "deactivate"))
    parser.add_argument("--workflow", help="workflow name (required for activate and deactivate; per-workflow, never all)")
    parser.add_argument("--target", type=Path, required=True, help="target repository whose .claude/workflows/ is the enablement surface")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--claude-config-dir", type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = settings_io.absolute(args.home)
    root = settings_io.absolute(args.claude_config_dir) if args.claude_config_dir else home / ".claude"
    workflows_dir = root / "workflows"
    state_root = settings_io.absolute(args.state_root) if args.state_root else installer.state_directory()
    target = settings_io.absolute(args.target)
    try:
        if not target.is_dir():
            raise WorkflowsError(f"target is not a directory: {target}")
        if target / ".claude" / "workflows" == workflows_dir:
            raise WorkflowsError(f"target selects the installed home plane itself; choose a project repository: {target}")
        if args.command in {"activate", "deactivate"}:
            if not args.workflow or not WORKFLOW_NAME_PATTERN.fullmatch(args.workflow):
                raise WorkflowsError(f"{args.command} requires --workflow <lowercase-slug-name>")
            if args.command == "activate":
                code, messages = activate(args.workflow, target, workflows_dir, state_root, args.dry_run)
            else:
                code, messages = deactivate(args.workflow, target, state_root, args.dry_run)
        else:
            code, messages = status(target, workflows_dir, state_root, args.workflow)
    except (WorkflowsError, settings_io.StatuslineError, installer.InstallerError) as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_REFUSED
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
