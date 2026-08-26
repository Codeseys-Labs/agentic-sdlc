#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install the Agentic SDLC skill bundle safely into Claude and Codex homes.

OWNERSHIP IS BYTE IDENTITY, NOT PHYSICAL IDENTITY. An ownership record names its destination, its
mode, and the digest of the bytes this lifecycle published there. Every removal, refresh, and
retarget is justified by re-reading those bytes and comparing that digest -- there is no
`stat`/`statx` birth-timestamp witness, no device/inode ownership token, and no settlement probe
anywhere in this module. The one place a `stat` result is compared against another is
`_readonly_read_file`'s torn-read guard, which compares a `(dev, ino, size, mtime_ns, ctime_ns)`
tuple across a read to detect a state file rewritten mid-read; it decides only whether that
read-only snapshot is stable, and no `stat` result here ever justifies a mutation. Two consequences
follow, and both are stated rather than implied:

* A destination the operator MODIFIED is still refused. Any content an operator adds, edits, or
  retargets changes the tree digest or the link target, `entry_matches_record` answers False, and
  status reports a conflict while install and uninstall preserve the destination untouched. That
  direction is the trust boundary and it stays fail-closed.
* A destination the operator replaced with a BYTE-IDENTICAL copy of the bundle's own payload is now
  removed by uninstall, where the retired witness layer refused it. That is an accepted, honestly
  weaker doctrine: the bytes removed are exactly the published payload, so the removal destroys
  no information of the operator's own — only, at most, their intent to keep a copy at that
  path. AGENTS.md records the same weakening.

The retired layer also refused to run at all on a filesystem that exposes no birth timestamp (NFS,
several FUSE and overlay mounts) and on a libc without `renameat2`, so this module now installs
markdown on hosts where `cp -r` has always worked. A same-UID racer that mutates a managed path
while a write command holds the lock remains out of scope, as it always was.

Crash consistency is one `pending` slot: a write arms the intended transition durably, moves the
bytes, then commits. The shape arrived here as a mirror of `scripts/install_operator_tools.py`, whose
PATH plane was deleted at gh #10 phase 4; this module is now the ONLY copy, so the `Mirrors ...`
notes below record where each rule came from rather than pointing at live code to compare against. A later run reads the live
bytes and decides commit or abort by comparing them to the armed `before`/`after` records. Bytes
that match neither are reported and preserved, never guessed at.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any, Iterator


STATE_VERSION = 4
#: Every payload kind this lifecycle owns, mapped to the collection directory it lands in under
#: the configured agent root. This table IS the entry-kind surface for placement: staging, refresh,
#: retarget, adoption, status, and uninstall are all kind-agnostic and read it rather than branching
#: per kind. Two things a kind can still need beyond a row here, both declared in their own table
#: below rather than in an `if` somewhere: how `discover_entries` finds its payload, and a POSIX
#: mode the published bytes must carry (`POSIX_MODE_FOR_KIND`).
COLLECTION_FOR_KIND = {
    "skill": "skills",
    "agent": "agents",
    "command": "commands",
    "workflow": "workflows",
    "hook": "hooks",
    "statusline": "statusline",
}
#: Kinds only Claude Code discovers. A Codex plane owns no record of them.
CLAUDE_ONLY_KINDS = frozenset({"command", "workflow", "hook", "statusline"})
#: The one kind published as a directory tree. Every other kind is a single file, so a record's kind
#: decides the node type its destination must have and no record field has to carry it.
DIRECTORY_KINDS = frozenset({"skill"})
#: The POSIX mode one kind's published payload must carry, keyed by kind. Every other kind inherits
#: its source file's mode through `copy_item`, which is what `statusline` cannot do: the tracked
#: source is mode 100644 and the published file IS the `statusLine.command` Claude Code executes
#: (gh #10 phase 2, critique-b row V6). A mode is only meaningful on bytes this lifecycle owns, so a
#: kind listed here is published as a COPY whatever `--mode` asks for -- a link would carry the
#: source's own 0644 and no `chmod` here could change that without editing the tracked tree.
POSIX_MODE_FOR_KIND = {"statusline": 0o755}
#: Derived, never a second list: exactly the kinds whose required mode forces copy publication.
COPY_ONLY_KINDS = frozenset(POSIX_MODE_FOR_KIND)
#: The `statusline` kind's single payload: one tracked source file, published under the name Claude
#: Code's `statusLine.command` names. The installed name differs from the source name on purpose --
#: `statusline-command.sh` describes the bundle's asset, `agentic-sdlc-statusline` is what an
#: operator sees in their own settings document.
STATUSLINE_SOURCE_RELATIVE = Path("assets") / "claude" / "statusline-command.sh"
STATUSLINE_COMMAND_NAME = "agentic-sdlc-statusline"
#: The closed key set of one ownership record.
RECORD_FIELDS = frozenset({"agent", "kind", "name", "source", "mode", "digest", "removable"})
#: The three transitions the `pending` slot can describe.
PENDING_OPERATIONS = frozenset({"install", "refresh", "uninstall"})
#: The only two spellings `--agent` accepts. `all` is deliberately absent: a lifecycle verb selects
#: exactly one plane, with no default and no wildcard, so an operator can never move bytes into a
#: plane they did not name. `Config.agent` still admits `all` as a LIBRARY value for the read-only
#: whole-box projection and the isolated self-test, neither of which is an operator's placement.
AGENT_SELECTORS = ("claude", "codex")
#: The verbs a selector binds. `self-test` is exempt: it installs into a throwaway home of its own
#: and is a pinned gate leaf (`mise run self-test`) that names no plane.
SELECTOR_REQUIRED_COMMANDS = frozenset({"install", "status", "uninstall"})


class InstallerError(RuntimeError):
    """Raised for errors that make an installer command fatal."""


class DurabilityError(InstallerError):
    """Raised when a required persistence barrier cannot be confirmed."""


class PublicationConflict(InstallerError):
    """Raised when a destination stopped being exactly what a publication step proved it was."""


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_root", operational_path(self.repo_root))
        object.__setattr__(self, "home", operational_path(self.home))
        object.__setattr__(self, "codex_home", operational_path(self.codex_home))
        if self.state_root is not None:
            object.__setattr__(self, "state_root", operational_path(self.state_root))

    @property
    def state_path(self) -> Path:
        root = self.state_root or state_directory()
        return root / "agentic-sdlc-installer" / "state.json"


@dataclass(frozen=True)
class Result:
    exit_code: int
    messages: tuple[str, ...]


@dataclass(frozen=True)
class PrivateArtifact:
    """A private 0700 container beside a destination, holding at most one `payload` child."""

    container: Path
    payload: Path


def conflict_messages(destination: Path, reason: str, *, label: str = "conflict") -> tuple[str, str]:
    """Name an untouched collision and give the operator a safe next step."""
    return (
        f"{label}: {destination}",
        f"preserved: {destination} ({reason}; inspect and resolve it before retrying)",
    )


def marketplace_messages(config: Config) -> tuple[str, str]:
    """Explain the one Claude-plane blocker without repeating it for every entry."""
    root = config.home / ".claude"
    return (
        f"marketplace overlap: {root}",
        "preserved: "
        f"{root} (Claude direct install is blocked; use the marketplace or remove its overlap before retrying)",
    )


def operation_summary(operation: str, messages: tuple[str, ...]) -> str:
    """Return the terminal, human-readable lifecycle summary for a write operation."""
    if operation == "install":
        installed = sum(message.startswith("installed:") or message.startswith("retargeted:") for message in messages)
        refreshed = sum(message.startswith("refreshed:") for message in messages)
        adopted = sum(message.startswith("adopted") or message.startswith("replaced link with copy:") for message in messages)
        unchanged = sum(message.startswith("ok:") for message in messages)
        planned = sum(message.startswith("would ") for message in messages)
        conflicts = sum(
            message.startswith(("conflict:", "interrupted conflict:", "marketplace overlap:"))
            for message in messages
        )
        return (
            "install summary: "
            f"{installed} installed, {refreshed} refreshed, {adopted} adopted, "
            f"{unchanged} unchanged, {planned} planned, {conflicts} conflict"
        )
    if operation == "uninstall":
        removed = sum(message.startswith("removed:") for message in messages)
        kept = sum(message.startswith("kept:") for message in messages)
        absent = sum(message.startswith("absent:") for message in messages)
        planned = sum(message.startswith("would ") for message in messages)
        conflicts = sum(message.startswith(("conflict:", "interrupted conflict:")) for message in messages)
        return (
            "uninstall summary: "
            f"{removed} removed, {kept} kept, {absent} absent, {planned} planned, {conflicts} conflict"
        )
    raise ValueError(f"unsupported lifecycle summary operation: {operation}")


def with_operation_summary(operation: str, result: Result) -> Result:
    """Keep lifecycle output inspectable by always ending write commands in one summary."""
    return Result(result.exit_code, result.messages + (operation_summary(operation, result.messages),))


def platform_system() -> str:
    """Return the host system; a small seam for platform-selection tests."""
    return platform.system()


def operational_path(path: Path) -> Path:
    """Make a path absolute without resolving aliases, links, junctions, or 8.3 spelling."""
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def path_present(path: Path) -> bool:
    """Return whether a path exists, including dangling links and junctions."""
    return path.exists() or path.is_symlink() or is_junction(path)


def state_directory() -> Path:
    """Return the operator's user-local state root without creating it."""
    if platform_system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return operational_path(Path(local_app_data))
        return operational_path(Path.home() / "AppData" / "Local")
    xdg_state = os.environ.get("XDG_STATE_HOME")
    return operational_path(Path(xdg_state)) if xdg_state else operational_path(
        Path.home() / ".local" / "state"
    )


def empty_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "entries": {}, "pending": None}


def read_state_document(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallerError(f"cannot read state {path}: {exc}") from exc
    if not isinstance(state, dict):
        raise InstallerError(f"invalid state {path}")
    return state


def load_document_state(document: dict[str, Any] | None, path: Path) -> dict[str, Any]:
    """Admit exactly the current ownership schema, and name the remedy for any other.

    Earlier schemas carried physical-identity witnesses and a per-entry transaction journal that no
    longer exist, so there is nothing here that could faithfully convert one: a record whose
    witnesses this module cannot check is not an ownership claim this module can honour. No release
    of this bundle has ever been published, so every document in existence was written by a
    development checkout on its author's own machine, and removing it plus reinstalling reproduces
    it exactly. That is the named remedy rather than a silent rewrite.
    """
    if document is None:
        return empty_state()
    version = document.get("version")
    if version != STATE_VERSION:
        raise InstallerError(
            f"state {path} was written by a different installer schema (version {version!r}, "
            f"expected {STATE_VERSION}); remove it and reinstall to rebuild it"
        )
    entries = document.get("entries")
    if set(document) != {"version", "entries", "pending"} or not isinstance(entries, dict):
        raise InstallerError(f"invalid state {path}")
    if not all(isinstance(key, str) and isinstance(value, dict) for key, value in entries.items()):
        raise InstallerError(f"invalid state {path}")
    return {"version": STATE_VERSION, "entries": entries, "pending": document["pending"]}


def load_state(path: Path) -> dict[str, Any]:
    """Read the current ownership document. This function never writes."""
    return load_document_state(read_state_document(path), path)


def configured_root(entry: Entry, config: Config) -> Path:
    return config.home if entry.agent == "claude" else config.codex_home


def agent_root(entry: Entry, config: Config) -> Path:
    return config.home / ".claude" if entry.agent == "claude" else config.codex_home


def entry_collection(kind: Any) -> str | None:
    """Map one owned payload kind to its destination collection, or None if unsupported.

    `workflow` is a Claude Code Dynamic Workflow document that lands in
    `<claude-home>/.claude/workflows/`. The lifecycle owns its bytes, its digest, and its
    ownership record — nothing more. Installing, refreshing, retargeting, adopting, or removing a
    workflow never runs it, never enables it, never reloads a host, and never grants it any
    authority: enabling or executing the real host overlay is a separately authorized
    user-configuration effect. That is why the workflow kind needs no execution machinery here.

    `hook` is an agent-CLI hook script that lands in `<claude-home>/.claude/hooks/`. The same
    boundary holds, and for hooks it is load-bearing twice over: that directory is not a Claude
    Code auto-discovery surface (hooks run only from settings configuration), so installing,
    refreshing, adopting, or removing one never runs it and never enables it. Wiring one into
    `settings.json` is the separately authorized `claude:hooks:activate` step
    (`scripts/manage_claude_hooks.py`), which this lifecycle never reaches.

    `statusline` is the packaged status-line script, landing in `<claude-home>/.claude/statusline/`.
    Same boundary again: installing it names nothing in `settings.json` and runs nothing, and
    pointing `statusLine.command` at it is the separately authorized `claude:statusline:activate`
    step. It is the one kind whose published bytes carry a mode this lifecycle sets rather than
    inherits, because that file is executed directly rather than read.
    """
    return COLLECTION_FOR_KIND.get(kind) if isinstance(kind, str) else None


def record_entry(record: dict[str, Any], key: str) -> Entry:
    return Entry(
        record["agent"],
        record["kind"],
        record.get("name", Path(key).name),
        Path(record["source"]),
    )


def destination_is_configured(key: str, record: dict[str, Any], config: Config) -> bool:
    """Return whether a record targets the currently configured agent home spelling.

    A record whose kind has no destination on its own plane has no configured destination either,
    so it answers False rather than raising: `validate_owned_entries` already refuses such a
    record with a named error, and this predicate must stay a predicate for the read-only callers.
    """
    try:
        expected = destination_for(record_entry(record, key), config)
    except InstallerError:
        return False
    return os.path.normcase(os.path.abspath(key)) == os.path.normcase(os.path.abspath(expected))


def record_structure_valid(key: str, record: dict[str, Any]) -> bool:
    """Admit exactly the closed seven-field ownership record, keyed by its own destination."""
    if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
        return False
    agent = record["agent"]
    kind = record["kind"]
    name = record["name"]
    source_value = record["source"]
    digest_value = record["digest"]
    # `collection is not None` is the kind test, and it comes first on purpose: a malformed
    # document can carry an unhashable `kind` (a JSON list or object), and a bare `in` against a
    # set or dict raises TypeError on one. Short-circuiting through the isinstance-guarded lookup
    # keeps that a refused record rather than a traceback. `isinstance(agent, str)` guards the same
    # hazard for the agent field one line below.
    collection = entry_collection(kind)
    identity_valid = (
        isinstance(agent, str)
        and agent in {"claude", "codex"}
        and collection is not None
        and not (agent == "codex" and kind in CLAUDE_ONLY_KINDS)
        and isinstance(name, str)
        and name not in {"", ".", ".."}
        and Path(name).name == name
    )
    destination = Path(key)
    destination_valid = (
        identity_valid
        and destination.is_absolute()
        and destination.name == name
        and destination.parent.name == collection
        and (agent == "codex" or destination.parent.parent.name == ".claude")
    )
    return bool(
        destination_valid
        and record["mode"] in {"copy", "link", "junction"}
        and isinstance(source_value, str)
        and bool(source_value)
        and Path(source_value).is_absolute()
        and isinstance(digest_value, str)
        and len(digest_value) == 64
        and all(character in "0123456789abcdef" for character in digest_value)
        and isinstance(record["removable"], bool)
    )


def validate_owned_entries(config: Config, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reject malformed ownership records before any destination is examined."""
    del config
    entries = state["entries"]
    for key, record in entries.items():
        if not record_structure_valid(key, record):
            raise InstallerError(f"invalid ownership record for {key}")
    return entries


def validate_pending(config: Config, state: dict[str, Any]) -> None:
    """Reject any armed transition that is not one of the three this lifecycle can resolve.

    Adapted from the deleted `install_operator_tools.validate_pending`: the same closed operation
    set, the same before/after record validation, and the same three transition rules cross-checked
    against the live `entries` map. The record validator was the one deliberate divergence, because a
    bundle record names an agent, a kind, and a source rather than a single command path.
    """
    del config
    pending = state.get("pending")
    if pending is None:
        return
    if not isinstance(pending, dict) or set(pending) != {"operation", "path", "before", "after"}:
        raise InstallerError("invalid pending lifecycle transition")
    operation = pending["operation"]
    key = pending["path"]
    if operation not in PENDING_OPERATIONS:
        raise InstallerError(f"invalid pending lifecycle operation: {operation!r}")
    if not isinstance(key, str) or not Path(key).is_absolute():
        raise InstallerError(f"invalid pending lifecycle path: {key!r}")
    before, after = pending["before"], pending["after"]
    for role, value in (("before", before), ("after", after)):
        if value is not None and not record_structure_valid(key, value):
            raise InstallerError(f"invalid pending {role} record for {key}")
    entries = state["entries"]
    valid = (
        (operation == "install" and before is None and after is not None and key not in entries)
        # A refresh does NOT require the two records to differ. The retired command plane could demand
        # that because it only rewrote a command whose bytes changed; a copy-mode bundle entry is
        # refreshed on every run so its published bytes track a source this lifecycle cannot diff
        # cheaply, and the armed transition is then before == after. Requiring inequality here would
        # refuse the ordinary refresh path outright.
        or (
            operation == "refresh"
            and before is not None
            and after is not None
            and entries.get(key) == before
        )
        or (operation == "uninstall" and before is not None and after is None and entries.get(key) == before)
    )
    if not valid:
        raise InstallerError(f"invalid pending lifecycle transition for {key}")


def validate_state(config: Config, state: dict[str, Any]) -> None:
    validate_owned_entries(config, state)
    validate_pending(config, state)


def flush_descriptor(descriptor: int, *, full: bool) -> None:
    """Flush one descriptor using the strongest supported host primitive."""
    try:
        if platform_system() == "Darwin" and full:
            import fcntl

            full_fsync = getattr(fcntl, "F_FULLFSYNC", 51)
            fcntl.fcntl(descriptor, full_fsync)
        else:
            os.fsync(descriptor)
    except OSError as exc:
        raise DurabilityError(f"cannot flush filesystem metadata: {exc}") from exc


def fsync_directory(path: Path) -> None:
    """Flush one directory entry. Adapted from the deleted `install_operator_tools.sync_directory`."""
    if platform_system() == "Windows":
        # Windows has no stdlib parent-directory durability barrier. Lifecycle
        # transitions remain process-crash recoverable, not power-loss durable.
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise DurabilityError(f"cannot open directory for flush {path}: {exc}") from exc
    try:
        flush_descriptor(descriptor, full=False)
    finally:
        os.close(descriptor)


def durable_mkdir(path: Path) -> None:
    """Create a directory chain and flush every new parent entry where supported.

    Adapted from the deleted `install_operator_tools.durable_mkdir`, with this module's pre-existing
    tolerance for a concurrently created directory retained.
    """
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            break
        current = parent
    for directory in reversed(missing):
        try:
            directory.mkdir()
        except FileExistsError:
            if not directory.is_dir():
                raise
        fsync_directory(directory)
        fsync_directory(directory.parent)


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    """Replace one file's bytes atomically and durably, never in place.

    Lifted from the deleted `install_operator_tools.atomic_write`:
    `durable_mkdir` the parent, `mkstemp` a sibling, `fchmod` it, write and flush, `F_FULLFSYNC` on
    Darwin and `fsync` elsewhere, `os.replace` into place, then flush the parent directory. This
    spelling routes the two flushes through `flush_descriptor`/`fsync_directory` so a barrier
    failure raises `DurabilityError` and stops the mutation, which is this module's contract.

    One divergence from the donor: the donor's plane fails closed on native Windows, this module
    does not, and `os.fchmod` does not exist there. The call is guarded by existence (`mkstemp`
    already creates the file 0o600, the only mode the one caller passes) and sits inside the
    `fdopen` block so no exception can leave the descriptor open against the `finally` unlink,
    which Windows refuses with WinError 32 while a handle is held.
    """
    durable_mkdir(path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            if hasattr(os, "fchmod"):
                os.fchmod(descriptor, mode)
            handle.write(content)
            handle.flush()
            flush_descriptor(handle.fileno(), full=True)
        os.replace(temporary, path)
        temporary = ""
        fsync_directory(path.parent)
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def write_state(path: Path, state: dict[str, Any], dry_run: bool) -> None:
    """Durably and atomically replace one state document, unless this is a dry-run."""
    if dry_run:
        return
    content = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write(path, content, 0o600)


def persist_state(config: Config, state: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Persist a complete state transition, then update the caller's in-memory view."""
    write_state(config.state_path, candidate, config.dry_run)
    state.clear()
    state.update(candidate)


@contextmanager
def installer_lock(config: Config) -> Iterator[None]:
    """Serialize write-capable lifecycle commands for one operator state file."""
    if config.dry_run:
        yield
        return
    lock_path = config.state_path.with_name("installer.lock")
    durable_mkdir(lock_path.parent)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
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


def statusline_entry(repo_root: Path) -> Entry | None:
    """The one `statusline` payload, or None when this tree does not carry the source.

    Every other kind is discovered by a glob, so an absent source directory yields nothing; this
    kind names one file, and a tree without it -- an extracted release payload built before the
    kind existed, or a caller's pruned fixture -- must stay discoverable rather than raise.
    """
    source = repo_root / STATUSLINE_SOURCE_RELATIVE
    if not source.is_file() or source.is_symlink():
        return None
    return Entry("claude", "statusline", STATUSLINE_COMMAND_NAME, source)


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
    # Workflow documents are Claude-only bytes; installing one never runs or enables it.
    for source in sorted((repo_root / "workflows").glob("*.js")):
        entries.append(Entry("claude", "workflow", source.name, source))
    # Hook scripts are Claude-only bytes too; installing one never runs or enables it.
    for source in sorted((repo_root / "hooks").glob("*.sh")):
        entries.append(Entry("claude", "hook", source.name, source))
    # The statusline script is Claude-only bytes as well. Installing it writes no settings document
    # and starts nothing: pointing `statusLine.command` at it is the separately authorized
    # `claude:statusline:activate` step (`scripts/manage_claude_statusline.py`).
    statusline = statusline_entry(repo_root)
    if statusline is not None:
        entries.append(statusline)
    return entries


def destination_for(entry: Entry, config: Config) -> Path:
    root = agent_root(entry, config)
    collection = entry_collection(entry.kind)
    if collection is None:
        raise InstallerError(f"unsupported entry kind: {entry.kind}")
    if entry.agent == "codex" and entry.kind in CLAUDE_ONLY_KINDS:
        raise InstallerError(f"{entry.kind} entries have no Codex destination: {entry.name}")
    return root / collection / entry.name


def assert_safe_collection(entry: Entry, destination: Path, config: Config) -> None:
    """Reject mutable roots below the explicitly configured home boundary."""
    collection = destination.parent
    current_agent_root = collection.parent
    expected_root = agent_root(entry, config)
    if is_junction(collection) or collection.is_symlink():
        raise InstallerError(f"collection root must not be a link: {collection}")
    if collection.exists() and not collection.is_dir():
        raise InstallerError(f"collection root must be a directory: {collection}")
    configured_boundary = configured_root(entry, config)
    agent_root_is_boundary = os.path.normcase(
        os.path.abspath(current_agent_root)
    ) == os.path.normcase(os.path.abspath(configured_boundary))
    if (
        not agent_root_is_boundary
        and (is_junction(current_agent_root) or current_agent_root.is_symlink())
    ):
        raise InstallerError(f"agent root must not be a link: {current_agent_root}")
    if current_agent_root.exists() and not current_agent_root.is_dir():
        raise InstallerError(f"agent root must be a directory: {current_agent_root}")
    if os.path.normcase(os.path.abspath(current_agent_root)) != os.path.normcase(
        os.path.abspath(expected_root)
    ):
        raise InstallerError(f"destination escapes configured agent root: {destination}")


def ensure_collection(entry: Entry, destination: Path, config: Config) -> None:
    """Create only already-validated configured roots and collection directories."""
    assert_safe_collection(entry, destination, config)
    durable_mkdir(configured_root(entry, config))
    current_agent_root = agent_root(entry, config)
    if not current_agent_root.exists():
        durable_mkdir(current_agent_root)
    assert_safe_collection(entry, destination, config)
    if not destination.parent.exists():
        durable_mkdir(destination.parent)
    assert_safe_collection(entry, destination, config)


def record_authority_matches(key: str, record: dict[str, Any], config: Config) -> bool:
    """Whether a record's destination still sits inside this configured, physical collection.

    `assert_safe_collection` is the boundary and it RAISES, so a collection that became a link or a
    destination that escapes the configured agent root reaches the caller as a named
    `InstallerError` rather than a bare False. What this predicate answers is the remaining
    question: does the record still describe a destination under the home this command was pointed
    at, with both its configured root and its collection present as directories? A record retained
    for an earlier configured home answers False.
    """
    entry = record_entry(record, key)
    destination = Path(key)
    assert_safe_collection(entry, destination, config)
    return (
        destination_is_configured(key, record, config)
        and configured_root(entry, config).is_dir()
        and destination.parent.is_dir()
    )


def nested_entry_type(path: Path) -> str:
    if path.is_symlink() or is_junction(path):
        return "L"
    if path.is_dir():
        return "D"
    if path.is_file():
        return "F"
    raise InstallerError(f"unsupported bundle entry type: {path}")


def digest(path: Path) -> str:
    """Hash bytes and node types without following nested links.

    Every variable-length payload is length-prefixed so the stream is prefix-free: paths cannot
    carry NUL and the length field is bare digits, so no file's content can impersonate a
    sibling's header. Without the prefix, deleting `b` and appending its serialized record to
    `a` yields the identical stream, and this digest is the sole ownership check.
    """
    hasher = hashlib.sha256()
    if path.is_dir() and not path.is_symlink() and not is_junction(path):
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(path).as_posix().encode("utf-8")
            kind = nested_entry_type(child)
            if kind == "F":
                payload = child.read_bytes()
            elif kind == "L":
                payload = os.fsencode(os.readlink(child))
            else:
                payload = b""
            hasher.update(
                kind.encode("ascii") + b"\0" + relative + b"\0" + b"%d\0" % len(payload)
            )
            hasher.update(payload)
    elif path.is_symlink() or is_junction(path):
        hasher.update(b"L\0" + os.fsencode(os.readlink(path)))
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


def tree_manifest(path: Path) -> dict[str, tuple[str, bytes]]:
    manifest: dict[str, tuple[str, bytes]] = {}
    for child in path.rglob("*"):
        relative = child.relative_to(path).as_posix()
        kind = nested_entry_type(child)
        if kind == "F":
            value = child.read_bytes()
        elif kind == "L":
            value = os.fsencode(os.readlink(child))
        else:
            value = b""
        manifest[relative] = kind, value
    return manifest


def content_equivalent(left: Path, right: Path) -> bool:
    """Compare files or typed trees, allowing only UTF-8 CRLF/LF differences."""
    if left.is_symlink() or right.is_symlink() or is_junction(left) or is_junction(right):
        return False
    if left.is_dir() != right.is_dir():
        return False
    if left.is_file():
        return right.is_file() and text_bytes_equal(left.read_bytes(), right.read_bytes())
    left_manifest = tree_manifest(left)
    right_manifest = tree_manifest(right)
    if left_manifest.keys() != right_manifest.keys():
        return False
    return all(
        left_manifest[name][0] == right_manifest[name][0]
        and (
            text_bytes_equal(left_manifest[name][1], right_manifest[name][1])
            if left_manifest[name][0] == "F"
            else left_manifest[name][1] == right_manifest[name][1]
        )
        for name in left_manifest
    )


def current_link_target(path: Path) -> Path | None:
    if not path.is_symlink():
        return None
    try:
        return path.resolve(strict=True)
    except OSError:
        return None


def legacy_link_mode(destination: Path, source: Path) -> str | None:
    """Return the concrete mode when an unowned destination links to source."""
    if is_junction(destination):
        try:
            return "junction" if os.path.samefile(destination, source) else None
        except OSError:
            return None
    return "link" if current_link_target(destination) == source.resolve() else None


def is_junction(path: Path) -> bool:
    """Return whether path is a Windows directory junction on supported Python versions."""
    return bool(getattr(path, "is_junction", lambda: False)())


def is_directory_object(path: Path) -> bool:
    """Whether a path is a real directory rather than a link or junction that points at one."""
    return path.is_dir() and not path.is_symlink() and not is_junction(path)


def replaces_as_directory(path: Path) -> bool:
    """Whether the kernel's replacing rename counts this path as a directory.

    Ownership asks whether an entry is a directory or a link; a MOVE asks something narrower,
    and on Windows the two answers differ. `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING` refuses
    a directory on either side, and a junction or a directory symlink is a directory-type reparse
    point to it, so `os.replace` on one raises `Access is denied` where it would have succeeded
    onto an absent name. Link-mode ownership publishes exactly such a payload, so treating it as
    a file chose the one-call fast path for a move Windows cannot perform: measured on
    windows-2025 as a raw `[WinError 5]` out of a link retarget (agentic-sdlc-5ce7, CI run
    32774680436). The rename-aside pair the docstring already promised for "a directory on either
    side" handles it, because the second rename then lands on an absent name.
    """
    if is_directory_object(path):
        return True
    if platform_system() != "Windows":
        return False
    return is_junction(path) or (path.is_symlink() and path.is_dir())


def remove_path(path: Path) -> None:
    """Remove a path; live destinations are never passed here by lifecycle mutations."""
    if is_junction(path):
        path.rmdir()
    elif path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_item(source: Path, destination: Path) -> None:
    if source.is_dir() and not source.is_symlink():
        shutil.copytree(source, destination, symlinks=True)
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


def apply_posix_mode(path: Path, mode: int) -> None:
    """Set one staged payload's POSIX mode explicitly, and prove the owner-execute bit took.

    `copy_item` preserves the SOURCE's mode and the tracked statusline source is 100644, so a
    payload published by copy alone would be a non-executable `statusLine.command`: Claude Code
    could not run it while a check that only reads `settings.json` still passed. The mode is
    therefore set here rather than inherited, and read back, because every later reader of this
    row -- `exact_owned_statusline` and the operator's own settings document -- assumes the file
    can be executed. On POSIX a mode that did not take is a refused publication rather than a
    silently broken feature; a Windows filesystem carries no owner-execute bit at all (`chmod`
    can neither grant nor take it, measured on windows-2025 in agentic-sdlc-5ce7's probe), and
    native Windows statusline activation is uncertified and fails closed, so there the readback
    is honestly unavailable rather than failed.
    """
    os.chmod(path, mode)
    if platform_system() == "Windows":
        return
    if not stat.S_IMODE(path.stat().st_mode) & stat.S_IXUSR:
        raise InstallerError(
            f"staged payload did not keep the owner-execute bit this kind requires: {path}"
        )


def effective_mode(entry: Entry, config: Config) -> str:
    """The publication mode this entry actually gets, which `--mode` cannot always choose.

    A kind whose payload must carry an explicit POSIX mode can only be published as a copy: a link
    resolves to the tracked source and would carry that file's own mode.
    """
    return "copy" if entry.kind in COPY_ONLY_KINDS else config.mode


def posix_mode_satisfied(destination: Path, kind: str) -> bool:
    """Whether a file this lifecycle did not publish already carries its kind's required mode.

    Only the adoption paths ask: a candidate whose CONTENT matches the payload but which cannot be
    executed is not the entry this kind promises, so it is preserved and named as a collision
    instead of adopted into a row whose reader would then refuse it. A kind with no required mode,
    and any host that carries no owner-execute bit, answers True -- the question does not apply.
    """
    required_mode = POSIX_MODE_FOR_KIND.get(kind)
    if required_mode is None or platform_system() == "Windows":
        return True
    try:
        return bool(stat.S_IMODE(destination.stat().st_mode) & stat.S_IXUSR)
    except OSError:
        return False


def publish_copy(entry: Entry, destination: Path) -> str:
    """Copy one payload and apply its kind's required POSIX mode. The only copy publication."""
    copy_item(entry.source, destination)
    required_mode = POSIX_MODE_FOR_KIND.get(entry.kind)
    if required_mode is not None:
        apply_posix_mode(destination, required_mode)
    return "copy"


def create_destination(entry: Entry, destination: Path, config: Config) -> str:
    """Create a staged entry according to mode; auto alone may fall back to copy."""
    if effective_mode(entry, config) == "copy":
        return publish_copy(entry, destination)
    try:
        return link_item(entry.source, destination)
    except (OSError, subprocess.CalledProcessError):
        if config.mode == "link":
            raise
        if path_present(destination):
            remove_path(destination)
        return publish_copy(entry, destination)


def entry_record(
    entry: Entry,
    mode: str,
    *,
    removable: bool = True,
    installed_digest: str | None = None,
) -> dict[str, Any]:
    """Build the closed seven-field ownership record for one published entry."""
    return {
        "agent": entry.agent,
        "kind": entry.kind,
        "name": entry.name,
        "source": str(entry.source.resolve()),
        "mode": mode,
        "digest": installed_digest or digest(entry.source),
        "removable": removable,
    }


def link_target_matches(destination: Path, record: dict[str, Any]) -> bool:
    """Whether an owned link or junction still points at exactly its recorded source."""
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
    """Whether the bytes on disk are still exactly the bytes this lifecycle published.

    This is the whole ownership test, and it is byte identity: mode agreement, plus the recorded
    link target for a link or junction, plus `digest(destination) == record["digest"]` for a copy.
    A destination the operator edited, retargeted, or replaced with different content answers False
    and is preserved. A destination the operator replaced with a byte-identical copy of the bundle's
    own payload answers True and is treated as owned -- see this module's docstring for why that
    weaker doctrine is accepted rather than hidden.
    """
    mode = record.get("mode")
    if mode in {"link", "junction"}:
        return link_target_matches(destination, record)
    if mode == "copy" and destination.exists() and not destination.is_symlink():
        # A record's kind decides its node type: skills are trees, every other kind is one file.
        # Checking it keeps an empty directory from matching an empty file's digest.
        if is_directory_object(destination) != (record.get("kind") in DIRECTORY_KINDS):
            return False
        try:
            return digest(destination) == record.get("digest")
        except OSError:
            return False
    return False


def exact_owned_statusline(config: Config) -> Path:
    """The installed statusline command path, or a refusal naming why there is none.

    The LEDGER ROW is the answer, which is the whole point of the `statusline` kind: the path an
    operator's `statusLine.command` names must be one this lifecycle currently owns, so
    `scripts/manage_claude_statusline.py` asks here instead of deriving a path of its own. Four
    refusals, each fail-closed and each about a document or a file rather than about intent: an
    interrupted lifecycle transition (the ledger is mid-flight and its rows are not yet the
    truth), no row of this kind at this destination, bytes that drifted from the row, and a file
    the host cannot execute. The last one is not redundant with the digest: ownership is byte
    identity and carries no mode, so a payload someone chmod-ed to 0644 still matches its record
    while Claude Code can no longer run it. Every later `bundle install` republishes the row and
    restores the mode, which is why this refusal names that command.

    The destination sits under the configured home rather than in the versioned mise tree, so an
    activated `statusLine.command` keeps resolving across a `mise prune` of the release directory.
    """
    entry = statusline_entry(config.repo_root)
    if entry is None:
        raise InstallerError(
            "this tree carries no statusline payload to install or activate:"
            f" {config.repo_root / STATUSLINE_SOURCE_RELATIVE} is absent"
        )
    destination = destination_for(entry, config)
    state = load_config_state(config)
    if state.get("pending") is not None:
        raise InstallerError(
            "the bundle lifecycle holds an interrupted pending operation; resolve it"
            " (mise run lifecycle:install -- --agent claude) before activating the statusline"
        )
    record = state["entries"].get(str(destination))
    if not isinstance(record, dict) or record.get("kind") != "statusline":
        raise InstallerError(
            f"the packaged statusline is not an installed bundle entry: {destination}"
            " (run: mise run lifecycle:install -- --agent claude)"
        )
    if not entry_matches_record(destination, record):
        raise InstallerError(
            f"the installed statusline drifted from its ownership record: {destination};"
            " refusing to name unowned bytes as statusLine.command"
        )
    if not os.access(destination, os.X_OK):
        raise InstallerError(
            f"the installed statusline is not executable: {destination}; reinstall it"
            " (mise run lifecycle:install -- --agent claude) rather than naming a file Claude Code"
            " cannot run as statusLine.command"
        )
    return destination


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


def reserve_private_artifact(destination: Path, role: str) -> PrivateArtifact:
    """Reserve one private 0700 container beside a destination, on the destination's own device.

    Same-directory placement is load-bearing: `os.replace` is only a rename within one filesystem,
    so a container anywhere else could not publish its payload atomically.
    """
    container = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.{role}-", dir=destination.parent)
    )
    os.chmod(container, 0o700)
    fsync_directory(container)
    fsync_directory(container.parent)
    return PrivateArtifact(container, container / "payload")


def discard_private_artifact(artifact: PrivateArtifact) -> None:
    """Remove a container this command created and did not publish. Best effort by design."""
    try:
        if path_present(artifact.payload):
            remove_path(artifact.payload)
        artifact.container.rmdir()
        fsync_directory(artifact.container.parent)
    except OSError:
        return


def unique_sibling(destination: Path, role: str) -> Path:
    """Return an unused private sibling NAME beside a destination, without creating it."""
    for _ in range(64):
        candidate = destination.with_name(f".{destination.name}.{role}-{os.urandom(8).hex()}")
        if not path_present(candidate):
            return candidate
    raise InstallerError(f"cannot reserve a private sibling name beside {destination}")


def leftover_messages(destination: Path) -> list[str]:
    """Name every private sibling an interrupted publication could have left beside a destination.

    Nothing here removes one. A container or an aside copy is the only place the previous bytes can
    still be, so naming it is what lets an operator finish by hand; deleting it on their behalf
    would be this lifecycle throwing away the evidence of its own interruption.

    The wording deliberately avoids the word "publication": it is one of the authority-shaped tokens
    `tests/test_lifecycle_exit_conformance.py` scans every rendered lifecycle line for, and a report
    line carrying one without a denial marker reads as an authorization claim.
    """
    messages: list[str] = []
    collection = destination.parent
    if not collection.is_dir():
        return messages
    for role in ("stage", "old", "removed", "backup"):
        prefix = f".{destination.name}.{role}-"
        for candidate in sorted(collection.glob(f"{prefix}*")):
            messages.append(
                f"leftover: {candidate} (an interrupted write left this private sibling; "
                "inspect and remove it by hand)"
            )
    return messages


def rename_absent(source: Path, destination: Path) -> None:
    """Move source onto a destination this call proved absent, refusing rather than clobbering.

    The presence check and the rename are two syscalls, so this narrows a window rather than closing
    one: a same-UID racer that creates the destination in between is out of scope here exactly as it
    is everywhere else in this module.
    """
    if path_present(destination):
        raise PublicationConflict(f"rename destination is no longer absent: {destination}")
    if not path_present(source):
        raise PublicationConflict(f"rename source is absent: {source}")
    os.replace(source, destination)
    fsync_directory(destination.parent)


def publish(payload: Path, destination: Path) -> None:
    """Move a staged payload onto its destination with the strongest move the kernel offers.

    A destination that is absent, and a file-or-link destination being replaced by a file-or-link
    payload, are both ONE `os.replace`: there is no window in which the destination does not exist.
    A directory on either side cannot be replaced in one call on any supported platform, so those go
    through a rename-aside pair, and the interval between the two renames is the one window this
    design accepts. A crash inside it leaves the destination absent with the previous tree parked in
    a named `.<name>.old-*` sibling; the armed `pending` slot makes the next run report the
    interruption, and `leftover_messages` names the sibling so the operator can finish by hand.
    """
    if not path_present(destination):
        rename_absent(payload, destination)
        return
    if not replaces_as_directory(payload) and not replaces_as_directory(destination):
        os.replace(payload, destination)
        fsync_directory(destination.parent)
        return
    aside = unique_sibling(destination, "old")
    os.replace(destination, aside)
    try:
        os.replace(payload, destination)
    except OSError as exc:
        try:
            os.replace(aside, destination)
        except OSError as restore_exc:
            raise InstallerError(
                f"cannot publish {destination}: {exc}; the previous entry is parked at {aside} "
                f"and could not be restored ({restore_exc})"
            ) from exc
        raise PublicationConflict(f"cannot publish {destination}: {exc}") from exc
    fsync_directory(destination.parent)
    remove_path(aside)
    fsync_directory(destination.parent)


def pending_slot(operation: str, key: str, before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "operation": operation,
        "path": key,
        "before": copy.deepcopy(before),
        "after": copy.deepcopy(after),
    }


def arm_pending(
    config: Config,
    state: dict[str, Any],
    operation: str,
    key: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    """Record the intended transition durably BEFORE the bytes move.

    Adapted from the deleted `install_operator_tools.arm`, plus this module's own pre-write
    validation so an inadmissible transition is refused rather than persisted.
    """
    candidate = copy.deepcopy(state)
    candidate["pending"] = pending_slot(operation, key, before, after)
    validate_pending(config, candidate)
    persist_state(config, state, candidate)


def resolved_pending_state(state: dict[str, Any], outcome: str) -> dict[str, Any]:
    """Apply or discard the armed transition and clear the slot."""
    candidate = copy.deepcopy(state)
    pending = candidate["pending"]
    assert isinstance(pending, dict)
    key = pending["path"]
    if outcome == "commit":
        if pending["operation"] in {"install", "refresh"}:
            candidate["entries"][key] = copy.deepcopy(pending["after"])
        else:
            candidate["entries"].pop(key, None)
    candidate["pending"] = None
    return candidate


def commit_pending(config: Config, state: dict[str, Any]) -> None:
    """Adapted from the deleted `install_operator_tools.commit_pending`."""
    persist_state(config, state, resolved_pending_state(state, "commit"))


def state_without_entry(state: dict[str, Any], key: str) -> dict[str, Any]:
    candidate = copy.deepcopy(state)
    candidate["entries"].pop(key, None)
    return candidate


def recover_pending(
    config: Config, state: dict[str, Any], *, read_only: bool
) -> tuple[list[str], bool]:
    """Resolve one interrupted transition by reading the bytes that are actually live.

    Adapted from the deleted `install_operator_tools.recover_pending`: the same three operations, the
    same abort-if-`before`/commit-if-`after` comparison, and the same refusal to guess when the live
    bytes match neither. Two things diverged, both deliberately. This
    resolution makes NO filesystem move at all -- it only decides whether the armed record becomes
    ownership -- because `publish` already made the byte-level outcome unambiguous. And bytes that
    match neither side are REPORTED and preserved rather than raised, which is this module's
    established answer for every collision and is what keeps a partly published tree inspectable.
    """
    pending = state.get("pending")
    if pending is None:
        return [], False
    assert isinstance(pending, dict)
    destination = Path(pending["path"])
    operation = pending["operation"]
    before = pending["before"]
    after = pending["after"]
    if not read_only and destination.parent.is_dir():
        # The barrier makes the interrupted rename durable before recovery commits state on it.
        # A read-only caller (status, --dry-run) commits nothing, and a barrier failure would
        # otherwise turn a report into a DurabilityError.
        fsync_directory(destination.parent)
    outcome: str | None = None
    if operation == "install":
        if not path_present(destination):
            outcome = "abort"
        elif isinstance(after, dict) and entry_matches_record(destination, after):
            outcome = "commit"
    elif operation == "refresh":
        if isinstance(before, dict) and entry_matches_record(destination, before):
            outcome = "abort"
        elif isinstance(after, dict) and entry_matches_record(destination, after):
            outcome = "commit"
    else:
        if isinstance(before, dict) and entry_matches_record(destination, before):
            outcome = "abort"
        elif not path_present(destination):
            outcome = "commit"
    if outcome is None:
        messages = list(
            conflict_messages(
                destination,
                "interrupted lifecycle state is no longer exact",
                label="interrupted conflict",
            )
        )
        return messages + leftover_messages(destination), True
    if read_only:
        return [f"would recover {outcome}: {destination}"] + leftover_messages(destination), True
    persist_state(config, state, resolved_pending_state(state, outcome))
    return [f"recovered {outcome}: {destination}"] + leftover_messages(destination), False


def stage_payload(
    entry: Entry, destination: Path, config: Config
) -> tuple[PrivateArtifact, str, str]:
    """Create this entry's payload inside a private sibling container, ready to be published."""
    artifact = reserve_private_artifact(destination, "stage")
    try:
        mode = create_destination(entry, artifact.payload, config)
        installed_digest = digest(artifact.payload) if mode == "copy" else digest(entry.source)
        return artifact, mode, installed_digest
    except BaseException as exc:
        discard_private_artifact(artifact)
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot stage {destination}: {exc}") from exc


def transactional_create(
    entry: Entry, destination: Path, config: Config, state: dict[str, Any]
) -> str:
    """Publish one absent destination: stage, arm, publish, validate, commit."""
    key = str(destination)
    artifact, mode, installed_digest = stage_payload(entry, destination, config)
    record = entry_record(entry, mode, installed_digest=installed_digest)
    try:
        if path_present(destination):
            raise PublicationConflict(f"destination appeared before publish: {destination}")
        if key in state["entries"]:
            # A recorded destination that no longer exists is what an interrupted publication leaves,
            # and a caller may republish it directly rather than through `_install`'s own retirement.
            # Retire the stale record in its own atomic write FIRST, so the armed slot is an ordinary
            # install whose abort answer is "the destination is absent" -- arming a refresh over an
            # already-absent destination would match neither recorded record and dead-end.
            persist_state(config, state, state_without_entry(state, key))
        arm_pending(config, state, "install", key, None, record)
        publish(artifact.payload, destination)
        if not entry_matches_record(destination, record):
            raise PublicationConflict(f"published destination validation failed: {destination}")
        commit_pending(config, state)
    except BaseException as exc:
        discard_private_artifact(artifact)
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot install {destination}: {exc}") from exc
    discard_private_artifact(artifact)
    return mode


def transactional_replace(
    entry: Entry,
    destination: Path,
    config: Config,
    state: dict[str, Any],
    old_record: dict[str, Any],
    *,
    action_name: str,
) -> str:
    """Publish over one destination whose current bytes this call re-proves first."""
    key = str(destination)
    artifact, mode, installed_digest = stage_payload(entry, destination, config)
    record = entry_record(entry, mode, installed_digest=installed_digest)
    try:
        if not entry_matches_record(destination, old_record):
            raise PublicationConflict(f"old destination changed: {destination}")
        owned = state["entries"].get(key) == old_record
        arm_pending(
            config,
            state,
            "refresh" if owned else "install",
            key,
            old_record if owned else None,
            record,
        )
        publish(artifact.payload, destination)
        if not entry_matches_record(destination, record):
            raise PublicationConflict(f"{action_name} validation failed: {destination}")
        commit_pending(config, state)
    except BaseException as exc:
        discard_private_artifact(artifact)
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot {action_name} {destination}: {exc}") from exc
    discard_private_artifact(artifact)
    return mode


def transactional_delete(
    destination: Path, config: Config, state: dict[str, Any], record: dict[str, Any]
) -> None:
    """Remove one owned destination: arm, rename it aside atomically, commit, then delete the aside.

    The aside rename is what makes the removal a single namespace transition. A crash between it and
    the commit leaves the destination absent, which the next run's `recover_pending` commits, and the
    parked copy named by `leftover_messages` rather than silently orphaned.
    """
    key = str(destination)
    if not entry_matches_record(destination, record):
        raise PublicationConflict(f"owned destination changed: {destination}")
    aside = unique_sibling(destination, "removed")
    arm_pending(config, state, "uninstall", key, record, None)
    try:
        rename_absent(destination, aside)
        commit_pending(config, state)
    except BaseException as exc:
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot remove {destination}: {exc}") from exc
    remove_path(aside)
    fsync_directory(aside.parent)


def save_owned_entry(
    config: Config,
    state: dict[str, Any],
    key: str,
    record: dict[str, Any],
) -> None:
    """Persist one state-only ownership change after an immediate exact recheck."""
    destination = Path(key)
    if not record_authority_matches(key, record, config):
        raise InstallerError(f"destination is not under the configured collection: {key}")
    if not entry_matches_record(destination, record):
        raise InstallerError(f"destination changed before adoption: {key}")
    candidate = copy.deepcopy(state)
    candidate["entries"][key] = copy.deepcopy(record)
    persist_state(config, state, candidate)


def load_config_state(config: Config) -> dict[str, Any]:
    """Read THE ownership document this configuration selects.

    There is exactly one state location, so a document anywhere else is another program's file and
    not this lifecycle's business: a configured-home-relative mirror under the selected home was
    compatibility state for a generation that never shipped, and reading it turned an unrelated
    project's `<root>/.local/state/agentic-sdlc-installer/state.json` into a fatal error on every
    verb the moment a configured root was a repository.
    """
    return load_state(config.state_path)


def _install(config: Config) -> Result:
    """Install selected entries, arming each transition durably before it moves bytes."""
    state = load_config_state(config)
    validate_state(config, state)
    messages, partial = recover_pending(config, state, read_only=config.dry_run)
    pending = state.get("pending")
    blocked_key = pending["path"] if isinstance(pending, dict) else None
    claude_blocked = config.agent in {"all", "claude"} and marketplace_overlap(config.home)
    if claude_blocked:
        partial = True
        messages.extend(marketplace_messages(config))

    for entry in discover_entries(config.repo_root):
        if config.agent != "all" and entry.agent != config.agent:
            continue
        destination = destination_for(entry, config)
        key = str(destination)

        if entry.agent == "claude" and claude_blocked:
            continue
        if key == blocked_key:
            partial = True
            continue

        assert_safe_collection(entry, destination, config)
        record = state["entries"].get(key)
        if isinstance(record, dict) and not path_present(destination):
            # A crash between the armed record's commit and the next command leaves exactly this
            # shape: a recorded destination that does not exist. `status` reports it `absent`;
            # install republishes it instead of calling it a conflict, which is what makes the
            # window converge without a per-entry journal.
            if not config.dry_run:
                persist_state(config, state, state_without_entry(state, key))
            record = None
        if isinstance(record, dict):
            if not entry_matches_record(destination, record):
                partial = True
                messages.extend(conflict_messages(destination, "owned entry changed"))
                continue
            if record["mode"] == "copy":
                if record["removable"] is False:
                    messages.append(f"ok (preserved on uninstall): {destination}")
                elif config.dry_run:
                    messages.append(f"would refresh: {destination}")
                else:
                    transactional_replace(
                        entry, destination, config, state, record, action_name="refresh"
                    )
                    messages.append(f"refreshed: {destination}")
            else:
                recorded_source = Path(str(record["source"]))
                desired_source = entry.source.resolve()
                if recorded_source != desired_source:
                    if config.dry_run:
                        messages.append(f"would retarget: {destination}")
                    else:
                        mode = transactional_replace(
                            entry, destination, config, state, record, action_name="retarget"
                        )
                        messages.append(f"retargeted: {destination} ({mode})")
                else:
                    messages.append(f"ok: {destination}")
            continue

        if path_present(destination):
            legacy_mode = legacy_link_mode(destination, entry.source)
            if legacy_mode is not None:
                legacy_record = entry_record(entry, legacy_mode)
                if effective_mode(entry, config) == "copy":
                    if config.dry_run:
                        messages.append(f"would replace link with copy: {destination}")
                    else:
                        transactional_replace(
                            entry,
                            destination,
                            config,
                            state,
                            legacy_record,
                            action_name="replace link with copy",
                        )
                        messages.append(f"replaced link with copy: {destination}")
                else:
                    if not config.dry_run:
                        save_owned_entry(config, state, key, legacy_record)
                    messages.append(f"adopted: {destination}")
                continue
            if (
                not destination.is_symlink()
                and destination.exists()
                and content_equivalent(destination, entry.source)
                and posix_mode_satisfied(destination, entry.kind)
            ):
                adopted_record = entry_record(
                    entry, "copy", removable=False, installed_digest=digest(destination)
                )
                if not config.dry_run:
                    save_owned_entry(config, state, key, adopted_record)
                messages.append(f"adopted (preserved on uninstall): {destination}")
                continue
            partial = True
            messages.extend(conflict_messages(destination, "a non-bundle entry already exists"))
            continue

        if config.dry_run:
            messages.append(f"would install: {destination}")
            continue
        try:
            ensure_collection(entry, destination, config)
            mode = transactional_create(entry, destination, config, state)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InstallerError(f"cannot install {destination}: {exc}") from exc
        messages.append(f"installed: {destination} ({mode})")

    return Result(1 if partial else 0, tuple(messages))


def install(config: Config) -> Result:
    if config.dry_run:
        return with_operation_summary("install", _install(config))
    with installer_lock(config):
        return with_operation_summary("install", _install(config))


def status_summary(counts: dict[str, int]) -> str:
    """Render the terminal status line so status is never silent."""
    if not any(counts.values()):
        return "no owned entries for this host (run: mise run lifecycle:install)"
    return f"{counts['ok']} ok, {counts['conflict']} conflict, {counts['absent']} absent"


def _readonly_json_document(content: bytes, path: Path) -> dict[str, Any]:
    """Decode a state document without duplicate-key or non-finite ambiguity."""
    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON value {value!r}")

    try:
        value = json.loads(
            content.decode("utf-8"), object_pairs_hook=reject_duplicate, parse_constant=reject_constant
        )
    except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
        # Parser diagnostics can repeat arbitrary keys and values from hostile state.  The
        # consumer receives the closed malformed-state finding instead.
        raise InstallerError("bundle state is malformed") from exc
    if not isinstance(value, dict):
        raise InstallerError("bundle state is malformed")
    return value


def _readonly_read_file(path: Path) -> tuple[str, bytes | None, str | None]:
    """Return a stable regular-file snapshot or a read-only evidence failure."""
    try:
        before = os.lstat(path)
    except FileNotFoundError:
        return "absent", None, None
    except OSError:
        return "unreadable", None, None
    if stat.S_ISLNK(before.st_mode):
        return "symlinked", None, None
    if not stat.S_ISREG(before.st_mode):
        return "unsupported", None, None
    try:
        content = path.read_bytes()
        after = os.lstat(path)
    except OSError:
        return "unreadable", None, None
    before_witness = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
    after_witness = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    if before_witness != after_witness:
        return "racy", None, None
    return "present", content, None


def _readonly_finding(code: str, message: str, path: Path | str) -> dict[str, str]:
    return {"code": code, "component": "bundle", "message": message, "path": str(path)}


def _readonly_locator(category: str, record: dict[str, Any], ordinal: int) -> str:
    """Return a deterministic public locator without reproducing state-owned names or paths."""
    return f"bundle-{category}://{record['agent']}/{record['kind']}/{ordinal}"


def readonly_projection(config: Config) -> dict[str, object]:
    """Read the canonical bundle lifecycle evidence without locks, migration, repair, or writes.

    One configuration selects exactly one state document, so this reports one state path and can
    never report an ambiguity between two of its own: the second, configured-home-relative location
    is gone, and with it the `state-ambiguous` verdict that only that mirror could produce here.
    """
    state_path = config.state_path
    findings: list[dict[str, str]] = []
    entries: list[dict[str, str]] = []
    recovery: list[dict[str, str]] = []
    document: dict[str, Any] | None = None
    projection_state = "absent"

    observed, content, _detail = _readonly_read_file(state_path)
    if observed == "present":
        assert content is not None
        try:
            document = _readonly_json_document(content, state_path)
        except InstallerError:
            findings.append(_readonly_finding("state-malformed", "bundle state is malformed", state_path))
            projection_state = "unreadable"
    elif observed != "absent":
        findings.append(_readonly_finding(f"state-{observed}", f"bundle state is {observed}", state_path))
        projection_state = "unreadable" if observed == "unreadable" else "blocked"

    if document is not None:
        state = document
        if set(state) != {"version", "entries", "pending"}:
            findings.append(_readonly_finding("state-malformed", "bundle state has an unknown field", state_path))
            projection_state = "unreadable"
        elif state.get("version") != STATE_VERSION:
            findings.append(
                _readonly_finding(
                    "state-unsupported",
                    "bundle state version is not readable by this installer schema",
                    state_path,
                )
            )
            projection_state = "blocked"
        else:
            try:
                validate_state(config, state)
            except InstallerError:
                findings.append(_readonly_finding("state-malformed", "bundle state is malformed", state_path))
                projection_state = "unreadable"
            else:
                owned_entries = state["entries"]
                assert isinstance(owned_entries, dict)
                selected_entries: list[tuple[dict[str, Any], Path, str]] = []
                for key in sorted(owned_entries):
                    record = owned_entries[key]
                    assert isinstance(key, str) and isinstance(record, dict)
                    if not destination_is_configured(key, record, config):
                        # The lifecycle intentionally retains ownership records for earlier
                        # configured homes. They are outside this operator projection, not a
                        # foreign target for the current query, so a read-only report must leave
                        # them unselected rather than inventing a conflict or touching them.
                        continue
                    destination = Path(key)
                    if not path_present(destination):
                        entry_state = "absent"
                    elif entry_matches_record(destination, record):
                        entry_state = "owned"
                    else:
                        entry_state = "foreign"
                    selected_entries.append((record, destination, entry_state))
                for ordinal, (record, _destination, entry_state) in enumerate(selected_entries, start=1):
                    locator = _readonly_locator("entry", record, ordinal)
                    entries.append(
                        {
                            "name": f"{record['agent']}-{record['kind']}-{ordinal}",
                            "path": locator,
                            "state": entry_state,
                        }
                    )
                    if entry_state != "owned":
                        findings.append(
                            _readonly_finding(
                                "owned-entry-conflict",
                                f"owned bundle entry is {entry_state}",
                                locator,
                            )
                        )
                        if projection_state not in {"blocked", "unreadable"}:
                            projection_state = "degraded"
                pending = state["pending"]
                selected_pending = pending_selects_config(pending, config)
                if selected_pending is not None:
                    locator = _readonly_locator("transition", selected_pending, 1)
                    recovery.append(
                        {
                            "action": "lifecycle-dry-run",
                            "component": "bundle",
                            "path": locator,
                            "state": "pending",
                        }
                    )
                    findings.append(
                        _readonly_finding(
                            "pending-recovery",
                            "bundle has an interrupted lifecycle transition; only a lifecycle dry run may propose recovery",
                            locator,
                        )
                    )
                    projection_state = "blocked"
                if projection_state == "absent" and (selected_entries or selected_pending is not None):
                    projection_state = "healthy"

    return {
        "entries": entries,
        "findings": findings,
        "recovery": recovery,
        "state": projection_state,
        "state_paths": [str(state_path)],
    }


def pending_selects_config(pending: Any, config: Config) -> dict[str, Any] | None:
    """Return the armed transition's own record when it targets this configured plane, else None.

    Callers reach this only after `validate_pending`, so the record it returns is safe to use for
    selection but must never become report text: `_readonly_locator` renders it instead.
    """
    if not isinstance(pending, dict):
        return None
    key = pending.get("path")
    for record in (pending.get("after"), pending.get("before")):
        if not isinstance(record, dict) or not isinstance(key, str):
            continue
        if config.agent != "all" and record.get("agent") != config.agent:
            continue
        if destination_is_configured(key, record, config):
            return record
    return None


def status(config: Config) -> Result:
    """Report ownership and pending recovery health without writing anything."""
    state = load_config_state(config)
    validate_state(config, state)
    messages, partial = recover_pending(config, state, read_only=True)
    counts = {"ok": 0, "conflict": 0, "absent": 0}
    if config.agent in {"all", "claude"} and marketplace_overlap(config.home):
        partial = True
        counts["conflict"] += 1
        messages.extend(marketplace_messages(config))
    for key, record in state["entries"].items():
        if config.agent != "all" and record["agent"] != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        destination = Path(key)
        # The collection boundary is asserted BEFORE the destination is examined, so a collection an
        # operator replaced with a link is refused by name rather than followed to whatever it now
        # points at. This is the one check that byte identity cannot substitute for.
        assert_safe_collection(record_entry(record, key), destination, config)
        if not path_present(destination):
            partial = True
            counts["absent"] += 1
            messages.append(f"absent: {destination}")
        elif entry_matches_record(destination, record):
            counts["ok"] += 1
            messages.append(f"ok: {destination}")
        else:
            partial = True
            counts["conflict"] += 1
            messages.extend(conflict_messages(destination, "owned entry changed"))
    messages.append(status_summary(counts))
    return Result(1 if partial else 0, tuple(messages))


def _uninstall(config: Config) -> Result:
    """Remove only destinations whose bytes are still exactly the ones this lifecycle published."""
    state = load_config_state(config)
    validate_state(config, state)
    messages, partial = recover_pending(config, state, read_only=config.dry_run)
    pending = state.get("pending")
    blocked_key = pending["path"] if isinstance(pending, dict) else None
    for key in list(state["entries"]):
        record = state["entries"].get(key)
        if record is None:
            continue
        if config.agent != "all" and record["agent"] != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        if key == blocked_key:
            partial = True
            continue
        destination = Path(key)
        # See `status`: the collection boundary is asserted before the destination is read, so a
        # retargeted collection link cannot redirect a removal at whatever it now points at.
        assert_safe_collection(record_entry(record, key), destination, config)
        if not path_present(destination):
            if not config.dry_run:
                persist_state(config, state, state_without_entry(state, key))
            messages.append(f"absent: {destination}")
            continue
        if not entry_matches_record(destination, record):
            partial = True
            messages.extend(conflict_messages(destination, "owned entry changed"))
            continue
        if record["removable"] is False:
            messages.append(f"kept: {destination} (adopted pre-existing entry)")
            continue
        if config.dry_run:
            messages.append(f"would remove: {destination}")
            continue
        transactional_delete(destination, config, state, record)
        messages.append(f"removed: {destination}")
    return Result(1 if partial else 0, tuple(messages))


def uninstall(config: Config) -> Result:
    if config.dry_run:
        return with_operation_summary("uninstall", _uninstall(config))
    with installer_lock(config):
        return with_operation_summary("uninstall", _uninstall(config))


def self_test(config: Config) -> Result:
    """Exercise an isolated lifecycle without writing to the caller's homes or state.

    The isolated configuration selects `all`, which is a LIBRARY value with no CLI spelling: the
    read-only report and this self-test are the two callers that legitimately describe both planes
    at once, and neither is an operator choosing where bytes land.
    """
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
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Configured roots: Claude entries use --claude-home/.claude; Codex entries use "
            "--codex-home (or CODEX_HOME). --agent is required on install, status, and uninstall, "
            "and selects exactly one plane: there is no default and no wildcard. "
            "Status and --dry-run never write state or bundle entries."
        ),
    )
    parser.add_argument(
        "command",
        choices=("install", "status", "uninstall", "self-test"),
        nargs="?",
        default="install",
        help="lifecycle action (default: install)",
    )
    parser.add_argument(
        "--agent",
        choices=AGENT_SELECTORS,
        action=SingleAgentAction,
        help="select one configured plane; required on install, status, and uninstall",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "link", "copy"),
        default="auto",
        help="installation mode: auto (default), strict link, or copy",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report install or removal changes without writing",
    )
    parser.add_argument(
        "--claude-home",
        "--home",
        dest="claude_home",
        type=Path,
        default=Path.home(),
        metavar="PATH",
        help="Claude user home; entries are placed under PATH/.claude (default: current home)",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        metavar="PATH",
        help="Codex root; default: CODEX_HOME or --claude-home/.codex",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = operational_path(args.claude_home)
    codex_home_value = args.codex_home
    if codex_home_value is None:
        environment_value = os.environ.get("CODEX_HOME")
        if environment_value is not None and not environment_value.strip():
            print("fatal: CODEX_HOME must not be empty", file=sys.stderr)
            return 2
        codex_home_value = Path(environment_value) if environment_value else home / ".codex"
    codex_home = operational_path(codex_home_value)
    config_repo_root = Path(__file__).resolve().parents[1]
    try:
        codex_is_repo = codex_home.resolve(strict=False) == config_repo_root
    except OSError:
        codex_is_repo = False
    if codex_is_repo:
        print("fatal: Codex home must not be the repository root", file=sys.stderr)
        return 2
    if args.agent is None:
        if args.command in SELECTOR_REQUIRED_COMMANDS:
            print(
                f"fatal: {args.command} requires --agent; select one plane:"
                f" {' or '.join(f'--agent {name}' for name in AGENT_SELECTORS)}",
                file=sys.stderr,
            )
            return 2
        # `self-test` is the one command that names no plane: it installs into a throwaway home of
        # its own, so the library wildcard is correct there and reachable nowhere else.
        selected_agent = "all"
    else:
        selected_agent = args.agent
    config = Config(config_repo_root, home, codex_home, args.mode, args.dry_run, selected_agent)
    try:
        result = {
            "install": install,
            "status": status,
            "uninstall": uninstall,
            "self-test": self_test,
        }[args.command](config)
    except InstallerError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2
    for message in result.messages:
        print(message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
