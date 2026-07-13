#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install the Agentic SDLC skill bundle safely into Claude and Codex homes."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import copy
import ctypes
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


STATE_VERSION = 2
IDENTITY_VERSION = "stat-v2"


class LinuxStatxTimestamp(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_int64),
        ("tv_nsec", ctypes.c_uint32),
        ("__reserved", ctypes.c_int32),
    ]


class LinuxStatx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint32),
        ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64),
        ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32),
        ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16),
        ("__spare0", ctypes.c_uint16),
        ("stx_ino", ctypes.c_uint64),
        ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64),
        ("stx_attributes_mask", ctypes.c_uint64),
        ("stx_atime", LinuxStatxTimestamp),
        ("stx_btime", LinuxStatxTimestamp),
        ("stx_ctime", LinuxStatxTimestamp),
        ("stx_mtime", LinuxStatxTimestamp),
        ("stx_rdev_major", ctypes.c_uint32),
        ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32),
        ("stx_dev_minor", ctypes.c_uint32),
        ("stx_mnt_id", ctypes.c_uint64),
        ("stx_dio_mem_align", ctypes.c_uint32),
        ("stx_dio_offset_align", ctypes.c_uint32),
        ("__spare3", ctypes.c_uint64 * 12),
    ]


class WindowsFileId128(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16)]


class WindowsFileIdInformation(ctypes.Structure):
    _fields_ = [
        ("volume_serial", ctypes.c_uint64),
        ("file_id", WindowsFileId128),
    ]


class InstallerError(RuntimeError):
    """Raised for errors that make an installer command fatal."""


class DurabilityError(InstallerError):
    """Raised when a required persistence barrier cannot be confirmed."""


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

    @property
    def legacy_state_path(self) -> Path:
        root = self.state_root or legacy_state_directory(self.home)
        return root / "agentic-sdlc-installer" / "state.json"


@dataclass(frozen=True)
class Result:
    exit_code: int
    messages: tuple[str, ...]


@dataclass(frozen=True)
class PrivateArtifact:
    container: Path
    payload: Path
    identity: str


@dataclass(frozen=True)
class StagedCandidate:
    artifact: PrivateArtifact
    record: dict[str, Any]


class RecoveryConflict(RuntimeError):
    """Raised internally when an interrupted layout is not exactly recognizable."""


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


def legacy_state_directory(home: Path) -> Path:
    """Return the location used by the v1 installer for a configured home."""
    if platform_system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            try:
                if home.resolve() == Path.home().resolve():
                    return operational_path(Path(local_app_data))
            except OSError:
                pass
        return operational_path(home / "AppData" / "Local")
    xdg_state = os.environ.get("XDG_STATE_HOME")
    return operational_path(Path(xdg_state)) if xdg_state else operational_path(
        home / ".local" / "state"
    )


def empty_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "entries": {}, "transactions": {}}


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


def load_state(path: Path) -> dict[str, Any]:
    """Read v2 installer state. Structural and authority validation follows before use."""
    state = read_state_document(path)
    if state is None:
        return empty_state()
    if state.get("version") != STATE_VERSION:
        raise InstallerError(f"invalid state {path}")
    entries = state.get("entries")
    transactions = state.get("transactions")
    if not isinstance(entries, dict) or not isinstance(transactions, dict):
        raise InstallerError(f"invalid state {path}")
    if not all(isinstance(key, str) and isinstance(value, dict) for key, value in entries.items()):
        raise InstallerError(f"invalid state {path}")
    if not all(isinstance(key, str) and isinstance(value, dict) for key, value in transactions.items()):
        raise InstallerError(f"invalid state {path}")
    return state


def identity_token_valid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parts = value.split(":")
    return bool(
        len(parts) == 4
        and parts[0] == IDENTITY_VERSION
        and all(part.isdigit() for part in parts[1:3])
        and parts[3].replace(".", "", 1).isdigit()
    )


def stat_birth_identity(path: Path, *, follow_symlinks: bool = True) -> str | None:
    """Return a stable object-birth witness on the supported local platforms."""
    system = platform_system()
    if system == "Darwin":
        metadata = os.stat(path, follow_symlinks=follow_symlinks)
        birth_ns = getattr(metadata, "st_birthtime_ns", None)
        if birth_ns is not None:
            return str(birth_ns)
        birth = getattr(metadata, "st_birthtime", None)
        return str(birth) if birth is not None else None
    if system == "Windows":
        return str(os.stat(path, follow_symlinks=follow_symlinks).st_ctime_ns)
    if system != "Linux":
        return None
    statx = getattr(ctypes.CDLL(None, use_errno=True), "statx", None)
    if statx is None:
        return None
    statx.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.POINTER(LinuxStatx),
    ]
    statx.restype = ctypes.c_int
    metadata = LinuxStatx()
    statx_btime = 0x00000800
    at_fdcwd = -100
    at_symlink_nofollow = 0x00000100
    flags = 0 if follow_symlinks else at_symlink_nofollow
    if statx(
        at_fdcwd,
        os.fsencode(path),
        flags,
        statx_btime,
        ctypes.byref(metadata),
    ) != 0 or not metadata.stx_mask & statx_btime:
        return None
    return f"{metadata.stx_btime.tv_sec}.{metadata.stx_btime.tv_nsec}"


def windows_file_identity(path: Path) -> tuple[int, int, int] | None:
    if os.name != "nt":
        return None
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    get_information = kernel32.GetFileInformationByHandleEx
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    get_information.restype = wintypes.BOOL
    close_handle = kernel32.CloseHandle
    handle = create_file(
        str(path),
        0x00000080,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x02000000,
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        return None
    try:
        information = WindowsFileIdInformation()
        if not get_information(
            handle, 18, ctypes.byref(information), ctypes.sizeof(information)
        ):
            return None
        file_id = int.from_bytes(bytes(information.file_id.identifier), "little")
        return information.volume_serial, file_id, 0
    finally:
        close_handle(handle)


def stat_identity(path: Path) -> str:
    """Return a followed filesystem-object identity with a stable generation witness."""
    if platform_system() == "Windows":
        windows_identity = windows_file_identity(path)
        if windows_identity is not None:
            volume, file_index, creation = windows_identity
            return f"{IDENTITY_VERSION}:{volume}:{file_index}:{creation}"
    try:
        metadata = os.stat(path)
    except OSError as exc:
        raise InstallerError(f"cannot identify {path}: {exc}") from exc
    generation = stat_birth_identity(path)
    if generation is None:
        raise InstallerError(
            f"filesystem does not expose stable object identity for {path}"
        )
    return f"{IDENTITY_VERSION}:{metadata.st_dev}:{metadata.st_ino}:{generation}"


def link_identity(path: Path) -> str:
    """Return an identity for a link object without following its target."""
    try:
        metadata = os.lstat(path)
    except OSError as exc:
        raise InstallerError(f"cannot identify {path}: {exc}") from exc
    return f"{IDENTITY_VERSION}:{metadata.st_dev}:{metadata.st_ino}:{metadata.st_ctime_ns}"


def identity_matches(path: Path, expected: Any) -> bool:
    if not identity_token_valid(expected):
        return False
    try:
        return stat_identity(path) == expected
    except InstallerError:
        return False


def configured_root(entry: Entry, config: Config) -> Path:
    return config.home if entry.agent == "claude" else config.codex_home


def agent_root(entry: Entry, config: Config) -> Path:
    return config.home / ".claude" if entry.agent == "claude" else config.codex_home


def record_entry(record: dict[str, Any], key: str) -> Entry:
    return Entry(
        record["agent"],
        record["kind"],
        record.get("name", Path(key).name),
        Path(record["source"]),
    )


def destination_is_configured(key: str, record: dict[str, Any], config: Config) -> bool:
    """Return whether a record targets the currently configured agent home spelling."""
    expected = destination_for(record_entry(record, key), config)
    return os.path.normcase(os.path.abspath(key)) == os.path.normcase(os.path.abspath(expected))


def record_structure_valid(key: str, record: dict[str, Any]) -> bool:
    agent = record.get("agent")
    kind = record.get("kind")
    name = record.get("name", Path(key).name)
    source_value = record.get("source")
    source_valid = (
        isinstance(source_value, str)
        and bool(source_value)
        and Path(source_value).is_absolute()
    )
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
        and destination.is_absolute()
        and destination.name == name
        and destination.parent.name == collection
        and (agent == "codex" or destination.parent.parent.name == ".claude")
    )
    return bool(
        destination_valid
        and record.get("mode") in {"copy", "link", "junction"}
        and source_valid
        and isinstance(record.get("digest"), str)
        and len(record["digest"]) == 64
        and all(character in "0123456789abcdef" for character in record["digest"])
        and isinstance(record.get("removable", True), bool)
        and (
            record.get("mode") != "copy"
            or (
                record.get("destination_type") in {"file", "directory"}
                and identity_token_valid(record.get("destination_identity"))
            )
        )
        and identity_token_valid(record.get("root_identity"))
        and identity_token_valid(record.get("collection_identity"))
    )


def validate_owned_entries(config: Config, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reject malformed v2 ownership records before any destination is examined."""
    del config
    entries = state["entries"]
    for key, record in entries.items():
        if not record_structure_valid(key, record):
            raise InstallerError(f"invalid ownership record for {key}")
    return entries


def artifact_fields_valid(
    tx: dict[str, Any], destination: Path, role: str, *, required: bool
) -> bool:
    container_value = tx.get(f"{role}_container")
    payload_value = tx.get(f"{role}_payload")
    identity_value = tx.get(f"{role}_identity")
    if not required:
        return container_value is None and payload_value is None and identity_value is None
    if not all(isinstance(value, str) and value for value in (container_value, payload_value)):
        return False
    container = Path(container_value)
    payload = Path(payload_value)
    prefix = f".{destination.name}.{role}-"
    return bool(
        container.is_absolute()
        and container.parent == destination.parent
        and container.name.startswith(prefix)
        and payload == container / "payload"
        and identity_token_valid(identity_value)
    )


def validate_transactions(config: Config, state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Reject malformed transaction journals before any destination is examined."""
    del config
    transactions = state["transactions"]
    for key, tx in transactions.items():
        operation = tx.get("operation")
        phase = tx.get("phase")
        destination = Path(key)
        old_record = tx.get("old_record")
        new_record = tx.get("new_record")
        old_owned = tx.get("old_owned")
        basic_valid = (
            operation in {"create", "replace", "delete"}
            and phase in {"armed", "cleanup", "abort-cleanup"}
            and tx.get("key") == key
            and tx.get("destination") == key
            and destination.is_absolute()
            and isinstance(old_owned, bool)
            and key not in state["entries"]
        )
        if not basic_valid:
            raise InstallerError(f"invalid transaction record for {key}")
        if operation == "create":
            records_valid = (
                phase in {"armed", "abort-cleanup"}
                and old_record is None
                and old_owned is False
                and isinstance(new_record, dict)
                and record_structure_valid(key, new_record)
            )
            reference_record = new_record
            artifacts_valid = artifact_fields_valid(tx, destination, "stage", required=True) and artifact_fields_valid(
                tx, destination, "backup", required=False
            )
        elif operation == "replace":
            records_valid = (
                isinstance(old_record, dict)
                and record_structure_valid(key, old_record)
                and isinstance(new_record, dict)
                and record_structure_valid(key, new_record)
                and old_record["root_identity"] == new_record["root_identity"]
                and old_record["collection_identity"] == new_record["collection_identity"]
            )
            reference_record = new_record
            artifacts_valid = artifact_fields_valid(tx, destination, "stage", required=True) and artifact_fields_valid(
                tx, destination, "backup", required=True
            )
        else:
            records_valid = (
                isinstance(old_record, dict)
                and record_structure_valid(key, old_record)
                and old_owned is True
                and new_record is None
            )
            reference_record = old_record
            artifacts_valid = artifact_fields_valid(tx, destination, "stage", required=False) and artifact_fields_valid(
                tx, destination, "backup", required=True
            )
        reference_valid = (
            isinstance(reference_record, dict)
            and destination.parent.name
            == {"skill": "skills", "agent": "agents", "command": "commands"}.get(
                reference_record.get("kind")
            )
        )
        if not records_valid or not artifacts_valid or not reference_valid:
            raise InstallerError(f"invalid transaction record for {key}")
    return transactions


def validate_state(config: Config, state: dict[str, Any]) -> None:
    validate_owned_entries(config, state)
    validate_transactions(config, state)


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
    if platform_system() == "Windows":
        # Windows has no stdlib parent-directory durability barrier. Lifecycle
        # transactions remain process-crash recoverable, not power-loss durable.
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
    """Create a directory chain and flush every new parent entry where supported."""
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


def fsync_file(path: Path) -> None:
    """Flush a staged regular file without changing its published mode."""
    original_mode = stat.S_IMODE(path.stat().st_mode)
    changed_mode = platform_system() == "Windows" and not original_mode & stat.S_IWUSR
    if changed_mode:
        path.chmod(original_mode | stat.S_IWUSR)
    try:
        mode = "r+b" if platform_system() == "Windows" else "rb"
        with path.open(mode) as handle:
            flush_descriptor(handle.fileno(), full=True)
    finally:
        if changed_mode:
            path.chmod(original_mode)
            if platform_system() != "Windows":
                with path.open("rb") as handle:
                    flush_descriptor(handle.fileno(), full=True)


def fsync_tree(path: Path) -> None:
    """Flush staged file content before publishing it by rename."""
    if path.is_symlink() or is_junction(path):
        return
    if path.is_dir():
        for child in path.rglob("*"):
            if child.is_file() and not child.is_symlink():
                fsync_file(child)
        for directory in sorted(
            (child for child in path.rglob("*") if child.is_dir()),
            key=lambda child: len(child.parts),
            reverse=True,
        ):
            fsync_directory(directory)
        fsync_directory(path)
        return
    fsync_file(path)


def write_state(path: Path, state: dict[str, Any], dry_run: bool) -> None:
    """Durably and atomically replace the state file, unless this is a dry-run."""
    if dry_run:
        return
    durable_mkdir(path.parent)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".state-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            flush_descriptor(handle.fileno(), full=True)
        os.replace(temporary, path)
        temporary = None
        fsync_directory(path.parent)
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


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
    root = agent_root(entry, config)
    collection = {"skill": "skills", "agent": "agents", "command": "commands"}[entry.kind]
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


def authority_tokens(entry: Entry, destination: Path, config: Config) -> tuple[str, str]:
    assert_safe_collection(entry, destination, config)
    root = configured_root(entry, config)
    collection = destination.parent
    if not root.is_dir() or not collection.is_dir():
        raise InstallerError(f"configured roots are unavailable for {destination}")
    return stat_identity(root), stat_identity(collection)


def record_authority_matches(key: str, record: dict[str, Any], config: Config) -> bool:
    entry = record_entry(record, key)
    destination = Path(key)
    assert_safe_collection(entry, destination, config)
    return identity_matches(configured_root(entry, config), record.get("root_identity")) and identity_matches(
        destination.parent, record.get("collection_identity")
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
    """Hash bytes and node types without following nested links."""
    hasher = hashlib.sha256()
    if path.is_dir() and not path.is_symlink() and not is_junction(path):
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(path).as_posix().encode("utf-8")
            kind = nested_entry_type(child)
            hasher.update(kind.encode("ascii") + b"\0" + relative + b"\0")
            if kind == "F":
                hasher.update(child.read_bytes())
            elif kind == "L":
                hasher.update(os.fsencode(os.readlink(child)))
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


def create_destination(entry: Entry, destination: Path, config: Config) -> str:
    """Create a staged entry according to mode; auto alone may fall back to copy."""
    if config.mode == "copy":
        copy_item(entry.source, destination)
        return "copy"
    try:
        return link_item(entry.source, destination)
    except (OSError, subprocess.CalledProcessError):
        if config.mode == "link":
            raise
        if path_present(destination):
            remove_path(destination)
        copy_item(entry.source, destination)
        return "copy"


def entry_record(
    entry: Entry,
    mode: str,
    root_identity: str | None = None,
    collection_identity: str | None = None,
    *,
    removable: bool = True,
    installed_digest: str | None = None,
    installed_path: Path | None = None,
) -> dict[str, Any]:
    if root_identity is None or collection_identity is None:
        raise InstallerError("entry_record requires root and collection identities")
    record: dict[str, Any] = {
        "agent": entry.agent,
        "kind": entry.kind,
        "name": entry.name,
        "source": str(entry.source.resolve()),
        "mode": mode,
        "digest": installed_digest or digest(entry.source),
        "removable": removable,
        "root_identity": root_identity,
        "collection_identity": collection_identity,
    }
    if mode == "copy":
        if installed_path is None:
            raise InstallerError("copy entry_record requires an installed path")
        record["destination_type"] = (
            "directory"
            if installed_path.is_dir() and not installed_path.is_symlink()
            else "file"
        )
        record["destination_identity"] = (
            link_identity(installed_path)
            if installed_path.is_symlink()
            else stat_identity(installed_path)
        )
    return record


def link_identity_matches(
    destination: Path,
    record: dict[str, Any],
    *,
    link_origin: Path | None = None,
) -> bool:
    """Match an owned link, optionally interpreting relative text at its live origin."""
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
        raw_target = Path(os.readlink(destination))
        if link_origin is None or raw_target.is_absolute():
            try:
                return os.path.samefile(destination, source)
            except OSError:
                pass
        base = link_origin.parent if link_origin is not None else destination.parent
        target = raw_target if raw_target.is_absolute() else base / raw_target
        return target.resolve(strict=False) == source
    return False


def copy_record_identity_matches(destination: Path, record: dict[str, Any]) -> bool:
    expected_type = record.get("destination_type")
    current_type = (
        "directory"
        if destination.is_dir() and not destination.is_symlink()
        else "file"
    )
    return current_type == expected_type and identity_matches(
        destination, record.get("destination_identity")
    )


def entry_matches_record(
    destination: Path,
    record: dict[str, Any],
    *,
    link_origin: Path | None = None,
) -> bool:
    """Whether the on-disk entry still has the exact recorded identity."""
    mode = record.get("mode")
    if mode in {"link", "junction"}:
        return link_identity_matches(destination, record, link_origin=link_origin)
    if mode == "copy" and destination.exists() and not destination.is_symlink():
        if not copy_record_identity_matches(destination, record):
            return False
        try:
            return digest(destination) == record.get("digest")
        except OSError:
            return False
    return False


def v1_record_structure_valid(key: str, record: dict[str, Any]) -> bool:
    agent = record.get("agent")
    kind = record.get("kind")
    name = record.get("name", Path(key).name)
    collection = {"skill": "skills", "agent": "agents", "command": "commands"}.get(kind)
    destination = Path(key)
    source = record.get("source")
    digest_value = record.get("digest")
    return bool(
        agent in {"claude", "codex"}
        and kind in {"skill", "agent", "command"}
        and not (agent == "codex" and kind == "command")
        and isinstance(name, str)
        and name not in {"", ".", ".."}
        and Path(name).name == name
        and destination.is_absolute()
        and destination.name == name
        and destination.parent.name == collection
        and (agent == "codex" or destination.parent.parent.name == ".claude")
        and record.get("mode") in {"copy", "link", "junction"}
        and isinstance(source, str)
        and bool(source)
        and Path(source).is_absolute()
        and isinstance(digest_value, str)
        and len(digest_value) == 64
        and all(character in "0123456789abcdef" for character in digest_value)
        and isinstance(record.get("removable", True), bool)
    )


def v1_entry_matches_record(destination: Path, record: dict[str, Any]) -> bool:
    if record.get("mode") in {"link", "junction"}:
        return link_identity_matches(destination, record)
    if record.get("mode") == "copy" and destination.exists() and not destination.is_symlink():
        expected_directory = record.get("kind") == "skill"
        if destination.is_dir() != expected_directory:
            return False
        try:
            return digest(destination) == record.get("digest")
        except OSError:
            return False
    return False


def known_state_documents(config: Config) -> list[tuple[dict[str, Any], Path]]:
    documents: list[tuple[dict[str, Any], Path]] = []
    seen: set[str] = set()
    for path in (config.state_path, config.legacy_state_path):
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        document = read_state_document(path)
        if document is not None:
            documents.append((document, path))
    return documents


def combined_v1_state(documents: list[tuple[dict[str, Any], Path]]) -> dict[str, Any] | None:
    entries: dict[str, Any] = {}
    found = False
    for document, path in documents:
        if document.get("version") != 1:
            continue
        found = True
        current = document.get("entries")
        if not isinstance(current, dict):
            raise InstallerError(f"invalid state {path}")
        for key, record in current.items():
            existing = entries.get(key)
            if existing is not None and existing != record:
                raise InstallerError(f"conflicting v1 ownership record for {key}")
            entries[key] = record
    return {"version": 1, "entries": entries} if found else None


def same_physical_path(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def load_config_state(config: Config) -> dict[str, Any]:
    documents = known_state_documents(config)
    outstanding = combined_v1_state(documents)
    if outstanding is not None:
        return outstanding
    current = next((document for document, path in documents if path == config.state_path), None)
    for document, path in documents:
        if path != config.state_path and not same_physical_path(path, config.state_path):
            raise InstallerError(f"unexpected state location {path}")
    if current is None:
        return empty_state()
    return load_state(config.state_path)


def inspect_v1_state(config: Config, state: dict[str, Any]) -> Result:
    del config
    entries = state.get("entries")
    if not isinstance(entries, dict):
        raise InstallerError("invalid state v1")
    messages = ["state v1 requires explicit migration: use install --migrate-state"]
    partial = False
    for key, record in entries.items():
        if not isinstance(key, str) or not isinstance(record, dict) or not v1_record_structure_valid(
            key, record
        ):
            raise InstallerError(f"invalid v1 ownership record for {key}")
        destination = Path(key)
        if v1_entry_matches_record(destination, record):
            messages.append(f"migration candidate: {destination}")
        else:
            partial = True
            messages.append(f"migration conflict: {destination}")
    return Result(1 if partial or entries else 0, tuple(messages))


def upgrade_v1_record(key: str, record: dict[str, Any]) -> dict[str, Any]:
    destination = Path(key)
    entry = record_entry(record, key)
    collection = destination.parent
    root = collection.parent.parent if entry.agent == "claude" else collection.parent
    agent_directory = collection.parent
    if (
        not root.is_dir()
        or not collection.is_dir()
        or collection.is_symlink()
        or is_junction(collection)
        or (
            entry.agent == "claude"
            and (agent_directory.is_symlink() or is_junction(agent_directory))
        )
    ):
        raise InstallerError(f"cannot migrate unsafe roots for {destination}")
    if not v1_entry_matches_record(destination, record):
        raise InstallerError(f"cannot migrate changed destination {destination}")
    return entry_record(
        entry,
        str(record["mode"]),
        stat_identity(root),
        stat_identity(collection),
        removable=bool(record.get("removable", True)),
        installed_digest=str(record["digest"]),
        installed_path=destination if record.get("mode") == "copy" else None,
    )


def record_physical_identity(record: dict[str, Any]) -> tuple[str, str, str, str] | None:
    destination_identity = record.get("destination_identity")
    if record.get("mode") != "copy" or not isinstance(destination_identity, str):
        return None
    return (
        str(record.get("agent")),
        str(record.get("kind")),
        str(record.get("destination_type")),
        destination_identity,
    )


def preferred_migration_key(
    left: str, right: str, left_record: dict[str, Any], config: Config
) -> str:
    left_selected = destination_is_configured(left, left_record, config)
    right_selected = destination_is_configured(right, left_record, config)
    if left_selected != right_selected:
        return left if left_selected else right
    return min(left, right)


def add_migrated_entry(
    migrated: dict[str, Any], key: str, upgraded: dict[str, Any], config: Config
) -> str:
    existing = migrated["entries"].get(key)
    if existing is not None and existing != upgraded:
        raise InstallerError(f"v1 record conflicts with current v2 state: {Path(key)}")
    physical = record_physical_identity(upgraded)
    if physical is not None:
        for existing_key, existing_record in list(migrated["entries"].items()):
            if existing_key == key or record_physical_identity(existing_record) != physical:
                continue
            if existing_record != upgraded:
                raise InstallerError(
                    f"v1 alias conflicts with current v2 state: {Path(key)}"
                )
            chosen = preferred_migration_key(existing_key, key, upgraded, config)
            if chosen == existing_key:
                return existing_key
            migrated["entries"].pop(existing_key)
            break
    migrated["entries"][key] = upgraded
    return key


def _migrate_v1_state(config: Config) -> Result:
    documents = known_state_documents(config)
    v1_documents = [
        (document, path) for document, path in documents if document.get("version") == 1
    ]
    if not v1_documents:
        current = next(
            (document for document, path in documents if path == config.state_path), None
        )
        if current is not None:
            validate_state(config, load_state(config.state_path))
        return Result(0, ("state is already current",))

    current_document = next(
        (document for document, path in documents if path == config.state_path), None
    )
    if current_document is not None and current_document.get("version") == STATE_VERSION:
        migrated = copy.deepcopy(load_state(config.state_path))
        validate_state(config, migrated)
    elif current_document is None or current_document.get("version") == 1:
        migrated = empty_state()
    else:
        raise InstallerError(f"invalid state {config.state_path}")

    source_witnesses: list[tuple[Path, str, bytes]] = []
    messages: list[str] = []
    for document, source_path in v1_documents:
        entries = document.get("entries")
        if not isinstance(entries, dict):
            raise InstallerError(f"invalid state {source_path}")
        try:
            source_witnesses.append(
                (source_path, stat_identity(source_path), source_path.read_bytes())
            )
        except OSError as exc:
            raise InstallerError(f"cannot inspect migration source {source_path}: {exc}") from exc
        for key, record in entries.items():
            if not isinstance(key, str) or not isinstance(record, dict) or not v1_record_structure_valid(
                key, record
            ):
                raise InstallerError(f"invalid v1 ownership record for {key}")
            upgraded = upgrade_v1_record(key, record)
            migrated_key = add_migrated_entry(migrated, key, upgraded, config)
            messages.append(
                f"would migrate: {Path(migrated_key)}"
                if config.dry_run
                else f"migrated: {Path(migrated_key)}"
            )

    validate_state(config, migrated)
    if config.dry_run:
        return Result(0, tuple(messages or ["state is already current"]))

    write_state(config.state_path, migrated, False)
    for source_path, expected_identity, expected_bytes in source_witnesses:
        if source_path == config.state_path or same_physical_path(
            source_path, config.state_path
        ):
            continue
        if not identity_matches(source_path, expected_identity):
            raise InstallerError(f"migration source changed before retirement: {source_path}")
        try:
            if source_path.read_bytes() != expected_bytes:
                raise InstallerError(
                    f"migration source changed before retirement: {source_path}"
                )
            source_path.unlink()
            fsync_directory(source_path.parent)
        except OSError as exc:
            raise InstallerError(f"cannot retire migration source {source_path}: {exc}") from exc
    return Result(0, tuple(messages or ["state is already current"]))


def migrate_v1_state(config: Config) -> Result:
    with installer_lock(config):
        return _migrate_v1_state(config)


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
    container = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.{role}-", dir=destination.parent)
    )
    os.chmod(container, 0o700)
    fsync_directory(container)
    fsync_directory(container.parent)
    return PrivateArtifact(container, container / "payload", stat_identity(container))


def artifact_from_transaction(tx: dict[str, Any], role: str) -> PrivateArtifact | None:
    container = tx.get(f"{role}_container")
    if container is None:
        return None
    return PrivateArtifact(
        Path(container), Path(tx[f"{role}_payload"]), tx[f"{role}_identity"]
    )


def container_status(artifact: PrivateArtifact) -> str:
    if not path_present(artifact.container):
        return "missing"
    if (
        artifact.container.is_symlink()
        or is_junction(artifact.container)
        or not artifact.container.is_dir()
        or not identity_matches(artifact.container, artifact.identity)
    ):
        return "foreign"
    return "owned"


def artifact_payload_status(
    artifact: PrivateArtifact,
    record: dict[str, Any],
    *,
    link_origin: Path | None = None,
) -> str:
    status = container_status(artifact)
    if status == "foreign":
        return "foreign"
    if status == "missing":
        return "absent"
    try:
        children = list(artifact.container.iterdir())
    except OSError:
        return "foreign"
    if any(child.name != "payload" for child in children):
        return "foreign"
    if not path_present(artifact.payload):
        return "absent"
    return (
        "exact"
        if entry_matches_record(artifact.payload, record, link_origin=link_origin)
        else "foreign"
    )


def cleanup_private_artifact(
    artifact: PrivateArtifact,
    record: dict[str, Any] | None = None,
    *,
    link_origin: Path | None = None,
) -> None:
    """Delete only an exact payload, then remove its now-empty private container."""
    status = container_status(artifact)
    if status == "missing":
        return
    if status != "owned":
        raise RecoveryConflict(f"private container identity changed: {artifact.container}")
    try:
        children = list(artifact.container.iterdir())
    except OSError as exc:
        raise RecoveryConflict(f"cannot inspect private container: {artifact.container}") from exc
    if any(child.name != "payload" for child in children):
        raise RecoveryConflict(f"foreign content in private container: {artifact.container}")
    if path_present(artifact.payload):
        if record is None or artifact_payload_status(
            artifact, record, link_origin=link_origin
        ) != "exact":
            raise RecoveryConflict(f"private payload changed: {artifact.payload}")
        remove_path(artifact.payload)
    if not identity_matches(artifact.container, artifact.identity):
        raise RecoveryConflict(f"private container identity changed: {artifact.container}")
    try:
        artifact.container.rmdir()
    except OSError as exc:
        raise RecoveryConflict(
            f"private container is not empty: {artifact.container}"
        ) from exc
    fsync_directory(artifact.container.parent)


def stage_candidate(
    entry: Entry,
    destination: Path,
    config: Config,
    root_token: str,
    collection_token: str,
) -> StagedCandidate:
    artifact = reserve_private_artifact(destination, "stage")
    try:
        mode = create_destination(entry, artifact.payload, config)
        fsync_tree(artifact.payload)
        fsync_directory(artifact.container)
        installed_digest = digest(artifact.payload) if mode == "copy" else digest(entry.source)
        record = entry_record(
            entry,
            mode,
            root_token,
            collection_token,
            installed_digest=installed_digest,
            installed_path=artifact.payload if mode == "copy" else None,
        )
        if artifact_payload_status(artifact, record) != "exact":
            raise InstallerError(f"staged candidate validation failed for {destination}")
        return StagedCandidate(artifact, record)
    except Exception as exc:
        try:
            cleanup_private_artifact(artifact)
        except Exception as cleanup_exc:
            raise InstallerError(
                f"cannot stage {destination}: {exc}; private artifact requires repair: {artifact.container} ({cleanup_exc})"
            ) from exc
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot stage {destination}: {exc}") from exc


def transaction_record(
    operation: str,
    key: str,
    *,
    old_record: dict[str, Any] | None,
    old_owned: bool,
    new_record: dict[str, Any] | None,
    stage: PrivateArtifact | None,
    backup: PrivateArtifact | None,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "phase": "armed",
        "key": key,
        "destination": key,
        "old_record": copy.deepcopy(old_record),
        "old_owned": old_owned,
        "new_record": copy.deepcopy(new_record),
        "stage_container": str(stage.container) if stage else None,
        "stage_payload": str(stage.payload) if stage else None,
        "stage_identity": stage.identity if stage else None,
        "backup_container": str(backup.container) if backup else None,
        "backup_payload": str(backup.payload) if backup else None,
        "backup_identity": backup.identity if backup else None,
    }


def state_with_transaction(state: dict[str, Any], key: str, tx: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(state)
    candidate["entries"].pop(key, None)
    candidate["transactions"][key] = tx
    return candidate


def resolved_state(
    state: dict[str, Any], key: str, active_record: dict[str, Any] | None
) -> dict[str, Any]:
    candidate = copy.deepcopy(state)
    candidate["transactions"].pop(key, None)
    if active_record is None:
        candidate["entries"].pop(key, None)
    else:
        candidate["entries"][key] = copy.deepcopy(active_record)
    return candidate


def _identity_parts(token: str) -> tuple[int, int]:
    parts = token.split(":")
    return int(parts[1]), int(parts[2])


def _open_verified_directory(path: Path, expected_identity: str | None) -> int:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        opened = os.fstat(descriptor)
        current = os.stat(path)
        if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
            raise RecoveryConflict(f"directory changed while opening: {path}")
        if expected_identity is not None and (
            (opened.st_dev, opened.st_ino) != _identity_parts(expected_identity)
            or not identity_matches(path, expected_identity)
        ):
            raise RecoveryConflict(f"directory identity changed: {path}")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _windows_rename_noreplace(
    source: Path,
    destination: Path,
    source_parent_identity: str | None,
    destination_parent_identity: str | None,
) -> None:
    if os.name != "nt":
        os.rename(source, destination)
        return
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    set_information = kernel32.SetFileInformationByHandle
    set_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
    ]
    set_information.restype = wintypes.BOOL

    invalid = wintypes.HANDLE(-1).value
    delete_access = 0x00010000
    read_attributes = 0x00000080
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    backup_semantics = 0x02000000
    open_reparse_point = 0x00200000

    def open_handle(path: Path, access: int, share: int = share_all) -> int:
        handle = create_file(
            str(path),
            access,
            share,
            None,
            open_existing,
            backup_semantics | open_reparse_point,
            None,
        )
        if handle == invalid:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    source_handle = open_handle(source, delete_access | read_attributes)
    destination_parent_handle = open_handle(
        destination.parent,
        read_attributes,
        0x00000001 | 0x00000002,
    )
    try:
        if source_parent_identity is not None and not identity_matches(
            source.parent, source_parent_identity
        ):
            raise RecoveryConflict(f"directory identity changed: {source.parent}")
        if destination_parent_identity is not None and not identity_matches(
            destination.parent, destination_parent_identity
        ):
            raise RecoveryConflict(f"directory identity changed: {destination.parent}")
        destination_name = str(destination)
        destination_bytes = destination_name.encode("utf-16-le")

        class FileRenameInfoEx(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("RootDirectory", wintypes.HANDLE),
                ("FileNameLength", wintypes.DWORD),
                ("FileName", wintypes.WCHAR * (len(destination_name) + 1)),
            ]

        information = FileRenameInfoEx(
            0,
            None,
            len(destination_bytes),
            destination_name,
        )
        information_size = FileRenameInfoEx.FileName.offset + len(destination_bytes) + 2
        if not set_information(
            source_handle, 22, ctypes.byref(information), information_size
        ):
            error = ctypes.get_last_error()
            if error in {80, 183}:
                raise FileExistsError(error, os.strerror(error), str(destination))
            raise ctypes.WinError(error)
    finally:
        close_handle(destination_parent_handle)
        close_handle(source_handle)


def _rename_noreplace(
    source: Path,
    destination: Path,
    *,
    source_parent_identity: str | None = None,
    destination_parent_identity: str | None = None,
) -> None:
    """Rename between verified directory objects without replacing the destination."""
    system = platform_system()
    if system == "Windows":
        _windows_rename_noreplace(
            source,
            destination,
            source_parent_identity,
            destination_parent_identity,
        )
        return

    source_descriptor = _open_verified_directory(
        source.parent, source_parent_identity
    )
    destination_descriptor = _open_verified_directory(
        destination.parent, destination_parent_identity
    )
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if system == "Darwin":
            renameatx_np = getattr(libc, "renameatx_np", None)
            if renameatx_np is None:
                raise OSError("atomic no-replace rename is unavailable on this platform")
            renameatx_np.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameatx_np.restype = ctypes.c_int
            result = renameatx_np(
                source_descriptor,
                os.fsencode(source.name),
                destination_descriptor,
                os.fsencode(destination.name),
                0x00000004,  # RENAME_EXCL
            )
        elif system == "Linux":
            renameat2 = getattr(libc, "renameat2", None)
            if renameat2 is None:
                raise OSError(
                    "atomic no-replace rename requires glibc 2.28 or newer"
                )
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            result = renameat2(
                source_descriptor,
                os.fsencode(source.name),
                destination_descriptor,
                os.fsencode(destination.name),
                1,  # RENAME_NOREPLACE
            )
        else:
            raise OSError("atomic no-replace rename is unavailable on this platform")

        if result != 0:
            error_number = ctypes.get_errno()
            raise OSError(error_number, os.strerror(error_number), str(destination))
        os.fsync(source_descriptor)
        if destination_descriptor != source_descriptor:
            os.fsync(destination_descriptor)
    finally:
        os.close(destination_descriptor)
        os.close(source_descriptor)


def transaction_parent_identity(tx: dict[str, Any], parent: Path) -> str | None:
    for role in ("stage", "backup"):
        if tx.get(f"{role}_container") == str(parent):
            return tx.get(f"{role}_identity")
    record = tx.get("new_record") or tx.get("old_record")
    destination = Path(tx["destination"])
    if isinstance(record, dict) and parent == destination.parent:
        return record.get("collection_identity")
    return None


def rename_absent(
    source: Path,
    destination: Path,
    *,
    authority: tuple[dict[str, Any], Config] | None = None,
) -> None:
    if path_present(destination):
        raise RecoveryConflict(f"rename destination is no longer absent: {destination}")
    if not path_present(source):
        raise RecoveryConflict(f"rename source is absent: {source}")
    source_identity = None
    destination_identity = None
    if authority is not None:
        tx, config = authority
        require_transaction_authority(tx, config)
        source_identity = transaction_parent_identity(tx, source.parent)
        destination_identity = transaction_parent_identity(tx, destination.parent)
    try:
        _rename_noreplace(
            source,
            destination,
            source_parent_identity=source_identity,
            destination_parent_identity=destination_identity,
        )
    except FileExistsError as exc:
        raise RecoveryConflict(
            f"rename destination is no longer absent: {destination}"
        ) from exc


def transaction_selects_config(tx: dict[str, Any], config: Config) -> bool:
    record = tx.get("new_record") or tx.get("old_record")
    if not isinstance(record, dict):
        return False
    if config.agent != "all" and record.get("agent") != config.agent:
        return False
    return destination_is_configured(tx["key"], record, config)


def transaction_authority_matches(tx: dict[str, Any], config: Config) -> bool:
    records = [
        record for record in (tx.get("old_record"), tx.get("new_record")) if isinstance(record, dict)
    ]
    if not records:
        return False
    try:
        return all(record_authority_matches(tx["key"], record, config) for record in records)
    except InstallerError:
        return False


def destination_status(destination: Path, record: dict[str, Any]) -> str:
    if not path_present(destination):
        return "absent"
    return "exact" if entry_matches_record(destination, record) else "foreign"


def classify_recovery(tx: dict[str, Any], config: Config) -> str:
    """Classify only layouts whose witnesses and payload identities are exact."""
    if not transaction_authority_matches(tx, config):
        return "conflict"
    operation = tx["operation"]
    phase = tx["phase"]
    destination = Path(tx["destination"])
    old_record = tx.get("old_record")
    new_record = tx.get("new_record")
    stage = artifact_from_transaction(tx, "stage")
    backup = artifact_from_transaction(tx, "backup")

    if operation == "create":
        assert isinstance(new_record, dict) and stage is not None
        live = destination_status(destination, new_record)
        staged = artifact_payload_status(stage, new_record)
        stage_container = container_status(stage)
        if live == "exact" and staged == "absent" and stage_container in {
            "owned",
            "missing",
        } and phase == "armed":
            return "create-finalize"
        if phase == "armed" and live == "absent" and staged == "exact":
            return "create-advance-abort-cleanup"
        if phase == "abort-cleanup" and live == "absent" and (
            stage_container == "missing" or staged in {"exact", "absent"}
        ):
            return "create-cleanup"
        return "conflict"

    if operation == "replace":
        assert isinstance(old_record, dict) and isinstance(new_record, dict)
        assert stage is not None and backup is not None
        live_old = destination_status(destination, old_record)
        live_new = destination_status(destination, new_record)
        staged = artifact_payload_status(stage, new_record)
        backup_status = artifact_payload_status(
            backup, old_record, link_origin=destination
        )
        if phase == "armed":
            if live_old == "exact" and staged == "exact" and backup_status == "absent":
                return "replace-abort"
            if live_old == "absent" and live_new == "absent" and staged == "exact" and backup_status == "exact":
                return "replace-restore"
            if live_new == "exact" and staged == "absent" and backup_status == "exact":
                return "replace-advance-cleanup"
            return "conflict"
        stage_container = container_status(stage)
        backup_container = container_status(backup)
        if phase == "abort-cleanup":
            stage_clean = stage_container == "missing" or staged in {"exact", "absent"}
            backup_clean = backup_container == "missing" or backup_status in {"exact", "absent"}
            if live_old == "exact" and stage_clean and backup_clean:
                return "replace-abort-cleanup"
            return "conflict"
        stage_clean = stage_container == "missing" or staged in {"exact", "absent"}
        backup_clean = backup_container == "missing" or backup_status in {"exact", "absent"}
        if live_new == "exact" and stage_clean and backup_clean:
            return "replace-cleanup"
        return "conflict"

    assert operation == "delete" and isinstance(old_record, dict) and backup is not None
    live = destination_status(destination, old_record)
    backup_status = artifact_payload_status(
        backup, old_record, link_origin=destination
    )
    if phase == "armed":
        if live == "exact" and backup_status == "absent":
            return "delete-abort"
        if live == "absent" and backup_status == "exact":
            return "delete-advance-cleanup"
        return "conflict"
    if phase == "cleanup" and live == "absent" and (
        container_status(backup) == "missing" or backup_status in {"exact", "absent"}
    ):
        return "delete-cleanup"
    return "conflict"


def require_transaction_authority(tx: dict[str, Any], config: Config) -> None:
    if not transaction_authority_matches(tx, config):
        raise RecoveryConflict(f"root/collection identity changed: {tx['destination']}")


def execute_recovery(config: Config, state: dict[str, Any], key: str) -> None:
    tx = state["transactions"][key]
    action = classify_recovery(tx, config)
    if action == "conflict":
        raise RecoveryConflict(f"interrupted conflict: {tx['destination']}")
    destination = Path(tx["destination"])
    stage = artifact_from_transaction(tx, "stage")
    backup = artifact_from_transaction(tx, "backup")
    old_record = tx.get("old_record")
    new_record = tx.get("new_record")

    require_transaction_authority(tx, config)
    if action == "create-advance-abort-cleanup":
        candidate = copy.deepcopy(state)
        candidate["transactions"][key]["phase"] = "abort-cleanup"
        persist_state(config, state, candidate)
        execute_recovery(config, state, key)
        return
    if action == "create-cleanup":
        assert stage is not None
        if path_present(destination):
            raise RecoveryConflict(
                f"destination appeared during create cleanup: {destination}"
            )
        cleanup_private_artifact(stage, new_record)
        persist_state(config, state, resolved_state(state, key, None))
        return
    if action == "create-finalize":
        assert stage is not None and isinstance(new_record, dict)
        if destination_status(destination, new_record) != "exact":
            raise RecoveryConflict(f"new destination changed: {destination}")
        cleanup_private_artifact(stage, new_record)
        persist_state(config, state, resolved_state(state, key, new_record))
        return
    if action == "replace-restore":
        assert backup is not None and isinstance(old_record, dict)
        require_transaction_authority(tx, config)
        if destination_status(destination, old_record) != "absent":
            raise RecoveryConflict(f"destination changed before restore: {destination}")
        if artifact_payload_status(
            backup, old_record, link_origin=destination
        ) != "exact":
            raise RecoveryConflict(f"backup changed before restore: {backup.payload}")
        rename_absent(
            backup.payload, destination, authority=(tx, config)
        )
        action = "replace-abort"
    if action == "replace-abort":
        assert stage is not None and backup is not None
        assert isinstance(old_record, dict)
        require_transaction_authority(tx, config)
        if destination_status(destination, old_record) != "exact":
            raise RecoveryConflict(f"old destination changed: {destination}")
        cleanup_state = copy.deepcopy(state)
        cleanup_state["transactions"][key]["phase"] = "abort-cleanup"
        persist_state(config, state, cleanup_state)
        cleanup_private_artifact(stage, new_record)
        cleanup_private_artifact(
            backup, old_record, link_origin=destination
        )
        active = old_record if tx["old_owned"] else None
        persist_state(config, state, resolved_state(state, key, active))
        return
    if action == "replace-abort-cleanup":
        assert stage is not None and backup is not None
        assert isinstance(old_record, dict)
        require_transaction_authority(tx, config)
        if destination_status(destination, old_record) != "exact":
            raise RecoveryConflict(f"old destination changed: {destination}")
        cleanup_private_artifact(stage, new_record)
        cleanup_private_artifact(
            backup, old_record, link_origin=destination
        )
        active = old_record if tx["old_owned"] else None
        persist_state(config, state, resolved_state(state, key, active))
        return
    if action == "replace-advance-cleanup":
        candidate = copy.deepcopy(state)
        candidate["transactions"][key]["phase"] = "cleanup"
        persist_state(config, state, candidate)
        execute_recovery(config, state, key)
        return
    if action == "replace-cleanup":
        assert stage is not None and backup is not None and isinstance(new_record, dict)
        require_transaction_authority(tx, config)
        if destination_status(destination, new_record) != "exact":
            raise RecoveryConflict(f"new destination changed: {destination}")
        cleanup_private_artifact(stage, new_record)
        cleanup_private_artifact(
            backup, old_record, link_origin=destination
        )
        persist_state(config, state, resolved_state(state, key, new_record))
        return
    if action == "delete-abort":
        assert backup is not None and isinstance(old_record, dict)
        require_transaction_authority(tx, config)
        if destination_status(destination, old_record) != "exact":
            raise RecoveryConflict(f"old destination changed: {destination}")
        cleanup_private_artifact(
            backup, old_record, link_origin=destination
        )
        persist_state(config, state, resolved_state(state, key, old_record))
        return
    if action == "delete-advance-cleanup":
        candidate = copy.deepcopy(state)
        candidate["transactions"][key]["phase"] = "cleanup"
        persist_state(config, state, candidate)
        execute_recovery(config, state, key)
        return
    assert action == "delete-cleanup" and backup is not None
    require_transaction_authority(tx, config)
    if path_present(destination):
        raise RecoveryConflict(f"destination appeared during delete cleanup: {destination}")
    cleanup_private_artifact(
        backup, old_record, link_origin=destination
    )
    persist_state(config, state, resolved_state(state, key, None))


def recover_transactions(
    config: Config, state: dict[str, Any], *, read_only: bool
) -> tuple[list[str], bool]:
    """Recover selected exact transactions, or report and preserve conflicts."""
    messages: list[str] = []
    partial = False
    for key in list(state["transactions"]):
        tx = state["transactions"].get(key)
        if tx is None or not transaction_selects_config(tx, config):
            continue
        action = classify_recovery(tx, config)
        if action == "conflict":
            partial = True
            messages.append(f"interrupted conflict: {tx['destination']}")
            continue
        if read_only:
            partial = True
            messages.append(f"would recover: {tx['destination']}")
            continue
        try:
            execute_recovery(config, state, key)
        except RecoveryConflict:
            partial = True
            messages.append(f"interrupted conflict: {tx['destination']}")
        except Exception as exc:
            try:
                durable = load_state(config.state_path)
                validate_state(config, durable)
                durable_tx = durable["transactions"].get(key)
                if durable_tx is None:
                    state.clear()
                    state.update(durable)
                    for artifact in (
                        artifact_from_transaction(tx, "stage"),
                        artifact_from_transaction(tx, "backup"),
                    ):
                        if artifact is not None:
                            cleanup_private_artifact(artifact)
                    messages.append(f"recovered: {tx['destination']}")
                    continue
                state.clear()
                state.update(durable)
            except Exception:
                pass
            raise InstallerError(f"cannot recover {tx['destination']}: {exc}") from exc
        else:
            messages.append(f"recovered: {tx['destination']}")
    return messages, partial


def recover_durable_after_failure(
    config: Config,
    key: str,
    artifacts: tuple[
        tuple[PrivateArtifact, dict[str, Any], Path | None], ...
    ],
) -> None:
    """Reload the durable journal after an exception and make only exact recovery moves."""
    try:
        durable = load_state(config.state_path)
        validate_state(config, durable)
        tx = durable["transactions"].get(key)
        if tx is not None and transaction_selects_config(tx, config):
            execute_recovery(config, durable, key)
            return
        for artifact, record, link_origin in artifacts:
            cleanup_private_artifact(
                artifact, record, link_origin=link_origin
            )
    except Exception:
        # The durable journal or an identity-bound artifact is intentionally left for repair.
        return


def transactional_create(
    entry: Entry,
    destination: Path,
    config: Config,
    state: dict[str, Any],
    root_token: str,
    collection_token: str,
) -> str:
    key = str(destination)
    try:
        staged = stage_candidate(entry, destination, config, root_token, collection_token)
    except InstallerError as exc:
        raise InstallerError(f"cannot install {destination}: {exc}") from exc
    tx = transaction_record(
        "create",
        key,
        old_record=None,
        old_owned=False,
        new_record=staged.record,
        stage=staged.artifact,
        backup=None,
    )
    try:
        if not record_authority_matches(key, staged.record, config) or path_present(destination):
            raise RecoveryConflict(f"destination or authority changed: {destination}")
        if artifact_payload_status(staged.artifact, staged.record) != "exact":
            raise RecoveryConflict(f"staged candidate changed: {staged.artifact.payload}")
        persist_state(config, state, state_with_transaction(state, key, tx))
        require_transaction_authority(tx, config)
        if path_present(destination):
            raise RecoveryConflict(f"destination appeared before publish: {destination}")
        rename_absent(
            staged.artifact.payload, destination, authority=(tx, config)
        )
        require_transaction_authority(tx, config)
        if destination_status(destination, staged.record) != "exact":
            raise RecoveryConflict(f"published destination validation failed: {destination}")
        cleanup_private_artifact(staged.artifact, staged.record)
        persist_state(config, state, resolved_state(state, key, staged.record))
        return str(staged.record["mode"])
    except Exception as exc:
        if not isinstance(exc, DurabilityError):
            recover_durable_after_failure(
                config, key, ((staged.artifact, staged.record, None),)
            )
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot install {destination}: {exc}") from exc


def transactional_replace(
    entry: Entry,
    destination: Path,
    config: Config,
    state: dict[str, Any],
    old_record: dict[str, Any],
    *,
    old_owned: bool,
    action_name: str,
) -> str:
    key = str(destination)
    root_token = old_record["root_identity"]
    collection_token = old_record["collection_identity"]
    try:
        staged = stage_candidate(entry, destination, config, root_token, collection_token)
    except InstallerError as exc:
        raise InstallerError(f"cannot {action_name} {destination}: {exc}") from exc
    try:
        backup = reserve_private_artifact(destination, "backup")
    except Exception as exc:
        recover_durable_after_failure(
            config, key, ((staged.artifact, staged.record, None),)
        )
        raise InstallerError(f"cannot {action_name} {destination}: {exc}") from exc
    tx = transaction_record(
        "replace",
        key,
        old_record=old_record,
        old_owned=old_owned,
        new_record=staged.record,
        stage=staged.artifact,
        backup=backup,
    )
    try:
        if not record_authority_matches(key, old_record, config):
            raise RecoveryConflict(f"root/collection identity changed: {destination}")
        if destination_status(destination, old_record) != "exact":
            raise RecoveryConflict(f"old destination changed: {destination}")
        if artifact_payload_status(staged.artifact, staged.record) != "exact":
            raise RecoveryConflict(f"staged candidate changed: {staged.artifact.payload}")
        if artifact_payload_status(backup, old_record) != "absent":
            raise RecoveryConflict(f"backup is not empty: {backup.container}")
        persist_state(config, state, state_with_transaction(state, key, tx))
        require_transaction_authority(tx, config)
        if destination_status(destination, old_record) != "exact":
            raise RecoveryConflict(f"old destination changed before backup: {destination}")
        require_transaction_authority(tx, config)
        rename_absent(destination, backup.payload, authority=(tx, config))
        require_transaction_authority(tx, config)
        if artifact_payload_status(
            backup, old_record, link_origin=destination
        ) != "exact":
            raise RecoveryConflict(f"backup validation failed: {backup.payload}")
        require_transaction_authority(tx, config)
        if path_present(destination):
            raise RecoveryConflict(f"destination appeared before publish: {destination}")
        rename_absent(
            staged.artifact.payload, destination, authority=(tx, config)
        )
        require_transaction_authority(tx, config)
        if destination_status(destination, staged.record) != "exact" or artifact_payload_status(
            backup, old_record, link_origin=destination
        ) != "exact":
            raise RecoveryConflict(f"replacement validation failed: {destination}")
        cleanup_state = copy.deepcopy(state)
        cleanup_state["transactions"][key]["phase"] = "cleanup"
        persist_state(config, state, cleanup_state)
        cleanup_private_artifact(staged.artifact, staged.record)
        cleanup_private_artifact(
            backup, old_record, link_origin=destination
        )
        persist_state(config, state, resolved_state(state, key, staged.record))
        return str(staged.record["mode"])
    except Exception as exc:
        if not isinstance(exc, DurabilityError):
            recover_durable_after_failure(
                config,
                key,
                (
                    (staged.artifact, staged.record, None),
                    (backup, old_record, destination),
                ),
            )
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot {action_name} {destination}: {exc}") from exc


def transactional_delete(
    destination: Path,
    config: Config,
    state: dict[str, Any],
    record: dict[str, Any],
) -> None:
    key = str(destination)
    try:
        backup = reserve_private_artifact(destination, "backup")
    except Exception as exc:
        raise InstallerError(f"cannot remove {destination}: {exc}") from exc
    tx = transaction_record(
        "delete",
        key,
        old_record=record,
        old_owned=True,
        new_record=None,
        stage=None,
        backup=backup,
    )
    try:
        if not record_authority_matches(key, record, config):
            raise RecoveryConflict(f"root/collection identity changed: {destination}")
        if destination_status(destination, record) != "exact":
            raise RecoveryConflict(f"owned destination changed: {destination}")
        persist_state(config, state, state_with_transaction(state, key, tx))
        require_transaction_authority(tx, config)
        if destination_status(destination, record) != "exact":
            raise RecoveryConflict(f"owned destination changed before backup: {destination}")
        require_transaction_authority(tx, config)
        rename_absent(destination, backup.payload, authority=(tx, config))
        require_transaction_authority(tx, config)
        if artifact_payload_status(
            backup, record, link_origin=destination
        ) != "exact":
            raise RecoveryConflict(f"backup validation failed: {backup.payload}")
        cleanup_state = copy.deepcopy(state)
        cleanup_state["transactions"][key]["phase"] = "cleanup"
        persist_state(config, state, cleanup_state)
        cleanup_private_artifact(
            backup, record, link_origin=destination
        )
        persist_state(config, state, resolved_state(state, key, None))
    except Exception as exc:
        if not isinstance(exc, DurabilityError):
            recover_durable_after_failure(
                config, key, ((backup, record, destination),)
            )
        if isinstance(exc, InstallerError):
            raise
        raise InstallerError(f"cannot remove {destination}: {exc}") from exc


def save_owned_entry(
    config: Config,
    state: dict[str, Any],
    key: str,
    record: dict[str, Any],
) -> None:
    """Persist one state-only ownership change after an immediate exact recheck."""
    if not record_authority_matches(key, record, config):
        raise InstallerError(f"root/collection identity changed: {key}")
    if not entry_matches_record(Path(key), record):
        raise InstallerError(f"destination changed before adoption: {key}")
    candidate = copy.deepcopy(state)
    candidate["entries"][key] = copy.deepcopy(record)
    persist_state(config, state, candidate)


def _install(config: Config) -> Result:
    """Install selected entries with per-entry crash-consistent transactions."""
    state = load_config_state(config)
    if state.get("version") == 1:
        return inspect_v1_state(config, state)
    validate_state(config, state)
    messages, partial = recover_transactions(config, state, read_only=config.dry_run)
    claude_blocked = config.agent in {"all", "claude"} and marketplace_overlap(config.home)

    for entry in discover_entries(config.repo_root):
        if config.agent != "all" and entry.agent != config.agent:
            continue
        destination = destination_for(entry, config)
        key = str(destination)

        if entry.agent == "claude" and claude_blocked:
            partial = True
            messages.append(f"marketplace overlap: {destination}")
            continue
        if key in state["transactions"]:
            partial = True
            continue

        assert_safe_collection(entry, destination, config)
        record = state["entries"].get(key)
        if isinstance(record, dict):
            if not record_authority_matches(key, record, config):
                partial = True
                messages.append(f"root/collection conflict: {destination}")
                continue
            if not entry_matches_record(destination, record):
                partial = True
                messages.append(f"conflict: {destination}")
                continue
            if record.get("mode") == "copy":
                if record.get("removable", True) is False:
                    messages.append(f"ok (preserved on uninstall): {destination}")
                elif config.dry_run:
                    messages.append(f"would refresh: {destination}")
                else:
                    transactional_replace(
                        entry,
                        destination,
                        config,
                        state,
                        record,
                        old_owned=True,
                        action_name="refresh",
                    )
                    messages.append(f"refreshed: {destination}")
            else:
                recorded_source = Path(str(record.get("source", "")))
                desired_source = entry.source.resolve()
                if recorded_source != desired_source:
                    if config.dry_run:
                        messages.append(f"would retarget: {destination}")
                    else:
                        mode = transactional_replace(
                            entry,
                            destination,
                            config,
                            state,
                            record,
                            old_owned=True,
                            action_name="retarget",
                        )
                        messages.append(f"retargeted: {destination} ({mode})")
                else:
                    messages.append(f"ok: {destination}")
            continue

        if path_present(destination):
            root_token, collection_token = authority_tokens(entry, destination, config)
            legacy_mode = legacy_link_mode(destination, entry.source)
            if legacy_mode is not None:
                legacy_record = entry_record(
                    entry, legacy_mode, root_token, collection_token
                )
                if config.mode == "copy":
                    if config.dry_run:
                        messages.append(f"would replace link with copy: {destination}")
                    else:
                        transactional_replace(
                            entry,
                            destination,
                            config,
                            state,
                            legacy_record,
                            old_owned=False,
                            action_name="replace link with copy",
                        )
                        messages.append(f"replaced link with copy: {destination}")
                else:
                    if not config.dry_run:
                        save_owned_entry(config, state, key, legacy_record)
                    messages.append(f"adopted: {destination}")
                continue
            if not destination.is_symlink() and destination.exists() and content_equivalent(
                destination, entry.source
            ):
                adopted_record = entry_record(
                    entry,
                    "copy",
                    root_token,
                    collection_token,
                    removable=False,
                    installed_digest=digest(destination),
                    installed_path=destination,
                )
                if not config.dry_run:
                    save_owned_entry(config, state, key, adopted_record)
                messages.append(f"adopted (preserved on uninstall): {destination}")
                continue
            partial = True
            messages.append(f"conflict: {destination}")
            continue

        if config.dry_run:
            messages.append(f"would install: {destination}")
            continue
        try:
            ensure_collection(entry, destination, config)
            root_token, collection_token = authority_tokens(entry, destination, config)
            mode = transactional_create(
                entry, destination, config, state, root_token, collection_token
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InstallerError(f"cannot install {destination}: {exc}") from exc
        messages.append(f"installed: {destination} ({mode})")

    return Result(1 if partial else 0, tuple(messages))


def install(config: Config) -> Result:
    if config.dry_run:
        return _install(config)
    with installer_lock(config):
        return _install(config)


def status(config: Config) -> Result:
    """Report ownership and pending recovery health without writing anything."""
    state = load_config_state(config)
    if state.get("version") == 1:
        return inspect_v1_state(config, state)
    validate_state(config, state)
    messages, partial = recover_transactions(config, state, read_only=True)
    for key, record in state["entries"].items():
        if config.agent != "all" and record.get("agent") != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        destination = Path(key)
        if not record_authority_matches(key, record, config):
            partial = True
            messages.append(f"root/collection conflict: {destination}")
        elif not path_present(destination):
            partial = True
            messages.append(f"absent: {destination}")
        elif entry_matches_record(destination, record):
            messages.append(f"ok: {destination}")
        else:
            partial = True
            messages.append(f"conflict: {destination}")
    return Result(1 if partial else 0, tuple(messages))


def _uninstall(config: Config) -> Result:
    """Transactionally remove only entries with exact ownership and ancestor identities."""
    state = load_config_state(config)
    if state.get("version") == 1:
        return inspect_v1_state(config, state)
    validate_state(config, state)
    messages, partial = recover_transactions(config, state, read_only=config.dry_run)
    for key in list(state["entries"]):
        record = state["entries"].get(key)
        if record is None:
            continue
        if config.agent != "all" and record.get("agent") != config.agent:
            continue
        if not destination_is_configured(key, record, config):
            continue
        destination = Path(key)
        if not record_authority_matches(key, record, config):
            partial = True
            messages.append(f"root/collection conflict: {destination}")
            continue
        if not path_present(destination):
            if not config.dry_run:
                if not record_authority_matches(key, record, config):
                    partial = True
                    messages.append(f"root/collection conflict: {destination}")
                    continue
                persist_state(config, state, resolved_state(state, key, None))
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
        transactional_delete(destination, config, state, record)
        messages.append(f"removed: {destination}")
    return Result(1 if partial else 0, tuple(messages))


def uninstall(config: Config) -> Result:
    if config.dry_run:
        return _uninstall(config)
    with installer_lock(config):
        return _uninstall(config)


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
    parser.add_argument(
        "command",
        choices=("install", "status", "uninstall", "self-test"),
        nargs="?",
        default="install",
    )
    parser.add_argument("--migrate-state", action="store_true")
    parser.add_argument("--agent", choices=("all", "claude", "codex"), action=SingleAgentAction)
    parser.add_argument("--mode", choices=("auto", "link", "copy"), default="auto")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--codex-home", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    home = operational_path(args.home)
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
    config = Config(config_repo_root, home, codex_home, args.mode, args.dry_run, args.agent or "all")
    if args.migrate_state and args.command != "install":
        print("fatal: --migrate-state is valid only with install", file=sys.stderr)
        return 2
    try:
        operation = (
            migrate_v1_state
            if args.migrate_state
            else {
                "install": install,
                "status": status,
                "uninstall": uninstall,
                "self-test": self_test,
            }[args.command]
        )
        result = operation(config)
    except InstallerError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2
    for message in result.messages:
        print(message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
