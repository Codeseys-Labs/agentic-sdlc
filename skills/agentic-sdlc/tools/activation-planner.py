#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Bounded Linux-only, one-entry instruction activation transaction.

The module deliberately supports no greenfield, readiness, Seeds, trust, Git, or
multi-file activation behavior.  A procedural grant is a same-user, single-use
record; it is not an authenticated approval.

Every result's reported `effect` is DERIVED, never chosen at the point of failure. Mutating
primitives admit each effect to `_Effects` at the instant it becomes true, and
`_report_failure` is the single point where any refusal's status, exit code, and effect are
settled from that ledger. Read `_Effects` before adding a mutating step or a raise site.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import types
import unicodedata
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PLAN_SCHEMA = "agentic-sdlc/activation-plan@2"
GRANT_SCHEMA = "agentic-sdlc/procedural-grant@1"
OPERATION_SCHEMA = "agentic-sdlc/activation-operation@2"
PROGRESS_SCHEMA = "agentic-sdlc/activation-progress@4"
COMMIT_SCHEMA = "agentic-sdlc/activation-commit@3"
RECEIPT_SCHEMA = "agentic-sdlc/activation-receipt@3"
ROLLBACK_SCHEMA = "agentic-sdlc/activation-rollback@3"
AUDIT_SCHEMA = "agentic-sdlc/activation-audit@2"
# @3 adds `admitted_effects`: the ordered ledger of what this invocation actually did, carried
# by every result rather than only by a refusal, so a consumer never has to know which statuses
# have it. The reported `effect` is derived from it -- see `_Effects` and `_report_failure`.
RESULT_SCHEMA = "agentic-sdlc/activation-result@3"
# ADR-0022 decision 2: the one tracked, public file inside the otherwise private state root.
REPO_MANIFEST_NAME = "repo.toml"
# ADR-0015's rendered model-task-map trio. Public like the manifest, but operator-named
# rather than exact, so the subtree admits any NAME under closed CUSTODY.
RIGHTSIZE_DIR_NAME = "rightsize"
# The tracked, public repository root. It holds `repo.toml`, `rightsize/`, and the
# machine-local plane pointers below; receipts and recovery journals live in the operator's
# own plane (ADR-0018).
STATE_DIR_NAME = ".agentic-sdlc"
# `plane.<sha256 of the plane root path>.json`: the one machine-local, engine-owned name
# family inside that otherwise public root, one per plane this checkout has ever put state
# in. It is the only witness that survives a rename of the checkout, because the plane key
# is derived from the absolute target path and the plane side is the only other place that
# path is recorded. See `_record_plane_pointer`.
PLANE_POINTER_PREFIX = "plane."
PLANE_POINTER_SCHEMA = "agentic-sdlc/activation-plane-pointer@1"
PLANE_SELECTION_ENV = "AGENTIC_SDLC_ACTIVATION_STATE"
PLANE_REPO_LOCAL = "repo-local"
# `${XDG_STATE_HOME:-~/.local/state}/ccodex/` per CONTEXT.md and issues/09; `activation/`
# separates this engine's state from every other ccodex consumer of the same plane.
PLANE_NAMESPACE = ("ccodex", "activation")
LEGACY_STATE_REASON = "target-local activation state predates the ccodex state plane"
UNSELECTED_PLANE_REASON = "activation state exists in a state plane this invocation did not select"
# Separate from the reason above because the remedy is different: nothing about the selection is
# wrong, the CHECKOUT moved. Reversing the rename or the state-home move makes the state
# reachable again, and no path is printed because a plane root carries the operator's home.
RECORDED_PLANE_REASON = "activation state exists in the state plane this checkout recorded, not in the one this invocation resolved"
# The recorded plane is not merely unselected, it is UNREACHABLE, so this one is not a refusal
# at all: see `_recorded_plane_entries` for why that is exit 4 and not exit 0 or exit 3.
RECORDED_PLANE_UNRESOLVED_REASON = "the state plane this checkout recorded cannot be resolved, so whether activation state exists there is unknown"
PLANE_PROBE_REASON = "cannot prove a state plane for this target holds no activation state"
PLANE_LABEL_REPO_LOCAL = "target-local plane"
PLANE_LABEL_DEFAULT = "ccodex state plane"
# A plane no environment variable names any more, reached only through this checkout's own
# pointer. Named separately so the operator can tell a selection they can undo from a rename or
# relocation they have to reverse; neither label prints a path, because these carry the
# operator's home.
PLANE_LABEL_RECORDED = "state plane recorded for this checkout"
PLANE_DEVICE_REASON = "activation state plane does not share the target filesystem"
PLANE_ANCESTOR_REASON = "activation state plane ancestor is unsafe"
_HEX32 = re.compile(r"[0-9a-f]{32}\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_TIME = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
_REL = re.compile(r"[^/\\\x00]+")
_AT_EMPTY_PATH = 0x1000
_STATX_MNT_ID = 0x1000
_STATX_BASIC_STATS = 0x07FF


class _StatxTimestamp(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_longlong), ("tv_nsec", ctypes.c_uint), ("__reserved", ctypes.c_int)]


class _Statx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint), ("stx_blksize", ctypes.c_uint), ("stx_attributes", ctypes.c_ulonglong),
        ("stx_nlink", ctypes.c_uint), ("stx_uid", ctypes.c_uint), ("stx_gid", ctypes.c_uint), ("stx_mode", ctypes.c_ushort),
        ("__spare0", ctypes.c_ushort), ("stx_ino", ctypes.c_ulonglong), ("stx_size", ctypes.c_ulonglong),
        ("stx_blocks", ctypes.c_ulonglong), ("stx_attributes_mask", ctypes.c_ulonglong),
        ("stx_atime", _StatxTimestamp), ("stx_btime", _StatxTimestamp), ("stx_ctime", _StatxTimestamp),
        ("stx_mtime", _StatxTimestamp), ("stx_rdev_major", ctypes.c_uint), ("stx_rdev_minor", ctypes.c_uint),
        ("stx_dev_major", ctypes.c_uint), ("stx_dev_minor", ctypes.c_uint), ("stx_mnt_id", ctypes.c_ulonglong),
        ("stx_dio_mem_align", ctypes.c_uint), ("stx_dio_offset_align", ctypes.c_uint), ("stx_subvol", ctypes.c_ulonglong),
        ("stx_atomic_write_unit_min", ctypes.c_uint), ("stx_atomic_write_unit_max", ctypes.c_uint),
        ("stx_atomic_write_segments_max", ctypes.c_uint), ("stx_dio_read_offset_align", ctypes.c_uint),
        ("__spare3", ctypes.c_ulonglong * 9),
    ]


class RootBinding:
    def __init__(self, path: Path, identity: dict[str, Any]):
        self.path = path
        self.identity = identity


class StatePlane:
    """Where one exact target's activation receipts and recovery journals live.

    Default is the operator's own plane, `<state home>/ccodex/activation/<key>`; the
    `repo-local` override selects the historical in-repository layout unchanged. Both
    hold the same closed surface, so exactly one of them is the plane for a given
    invocation and no record is ever split across the two.

    The layouts differ in one place only. In the plane, the setup anchor and the no-op
    audit are plane-root files (`intent.<id>.json`, `noop.<id>.json`); repo-local keeps
    them at the target root under their historical `.agentic-sdlc.` names, so the
    repository root's own whitelist neither widens nor changes.
    """

    def __init__(self, target: Path, root: Path, *, repo_local: bool, recorded: bool = False):
        self.target = target
        self.root = root
        self.repo_local = repo_local
        self.anchor_dir = target if repo_local else root
        self.anchor_prefix = f"{STATE_DIR_NAME}.intent." if repo_local else "intent."
        self.audit_prefix = f"{STATE_DIR_NAME}.noop." if repo_local else "noop."
        # A probe-only candidate reached through this checkout's own pointer rather than through
        # any environment variable. It changes the label and the refusal's reason, never the
        # layout: no pointer is ever written for the repo-local override.
        self.recorded = recorded

    @property
    def label(self) -> str:
        """Name the plane without printing a path that carries the operator's home.

        A recorded plane gets its own label so that a refusal distinguishes "you switched
        selection", which the operator can undo, from "this checkout moved", which they have to
        reverse.
        """
        if self.recorded:
            return PLANE_LABEL_RECORDED
        return PLANE_LABEL_REPO_LOCAL if self.repo_local else PLANE_LABEL_DEFAULT

    def anchor_name(self, operation_id: str) -> str:
        return f"{self.anchor_prefix}{operation_id}.json"

    def audit_name(self, operation_id: str) -> str:
        return f"{self.audit_prefix}{operation_id}.json"

    @property
    def receipts(self) -> Path:
        return self.root / "receipts"

    @property
    def transactions(self) -> Path:
        return self.root / "transactions"

    def operation_dir(self, operation_id: str) -> Path:
        return self.transactions / operation_id


class PrivateTransaction:
    """Pinned private namespace for every effectful transaction operation."""

    def __init__(self, target_path: Path, plane: StatePlane, target_fd: int, state_fd: int, receipts_fd: int, transactions_fd: int, operation_fd: int, grants_fd: int, stage_fd: int, backup_fd: int, discard_fd: int, progress_history_fd: int, identities: dict[str, dict[str, Any]], operation_id: str, files: dict[tuple[str, str], dict[str, Any]] | None = None):
        self.target_path = target_path
        self.plane = plane
        self.target_fd = target_fd
        self.state_fd = state_fd
        self.receipts_fd = receipts_fd
        self.transactions_fd = transactions_fd
        self.operation_fd = operation_fd
        self.grants_fd = grants_fd
        self.stage_fd = stage_fd
        self.backup_fd = backup_fd
        self.discard_fd = discard_fd
        self.progress_history_fd = progress_history_fd
        self.identities = identities
        self.operation_id = operation_id
        self.staged_custody: dict[str, Any] | None = None
        self.backup_custody: dict[str, Any] | None = None
        # Immutable metadata and every mutable record we publish are retained by
        # descriptor identity for the lifetime of a mutating command.
        self.files = files or {}

    def close(self) -> None:
        for fd in (self.progress_history_fd, self.discard_fd, self.backup_fd, self.stage_fd, self.grants_fd, self.operation_fd, self.transactions_fd, self.receipts_fd, self.state_fd, self.target_fd):
            try:
                os.close(fd)
            except OSError:
                pass

    def track_file(self, directory: str, name: str) -> dict[str, Any]:
        fd = getattr(self, f"{directory}_fd")
        _, identity = _read_stable_at(fd, name, f"pinned {directory}/{name}")
        self.files[(directory, name)] = identity
        return identity

    def untrack_file(self, directory: str, name: str) -> None:
        self.files.pop((directory, name), None)

    def assert_intact(self) -> None:
        for name, fd in (
            ("target", self.target_fd), ("state", self.state_fd), ("receipts", self.receipts_fd),
            ("transactions", self.transactions_fd), ("operation", self.operation_fd), ("grants", self.grants_fd),
            ("stage", self.stage_fd), ("backup", self.backup_fd), ("discard", self.discard_fd),
            ("progress_history", self.progress_history_fd),
        ):
            try:
                observed = _dir_identity_fd(fd)
            except ActivationError as exc:
                raise ActivationError("effect-unknown", f"pinned private {name} descriptor became unsafe", 4) from exc
            if observed != self.identities[name]:
                raise ActivationError("effect-unknown", f"pinned private {name} descriptor changed", 4)
        path_fds: dict[str, int] = {}
        try:
            path_fds["state"] = _open_plane_root(self.plane, self.target_fd)
            path_fds["receipts"] = open_component_dir(path_fds["state"], "receipts")
            path_fds["transactions"] = open_component_dir(path_fds["state"], "transactions")
            path_fds["operation"] = open_component_dir(path_fds["transactions"], self.operation_id)
            for name in ("grants", "stage", "backup", "discard", "progress-history"):
                path_fds[name.replace("-", "_")] = open_component_dir(path_fds["operation"], name)
            for name, current in path_fds.items():
                if _dir_identity_fd(current) != self.identities[name]:
                    raise ActivationError("effect-unknown", f"private {name} pathname no longer reaches pinned descriptor", 4)
        except (OSError, ActivationError) as exc:
            if isinstance(exc, ActivationError):
                raise
            raise ActivationError("effect-unknown", "private transaction namespace diverged", 4) from exc
        finally:
            for current in path_fds.values():
                os.close(current)
        try:
            operation_names = set(os.listdir(self.operation_fd))
            allowed_operation = {"operation.json", "progress.json", "progress.json.next", "progress-history", "commit.json", "rollback.json", "receipt.json.next", "grants", "stage", "backup", "discard"}
            if not operation_names <= allowed_operation:
                raise ActivationError("effect-unknown", "private transaction layout has unexpected witness", 4)
            if not {"operation.json", "progress.json", "progress-history", "grants", "stage", "backup", "discard"} <= operation_names:
                raise ActivationError("effect-unknown", "private transaction layout is incomplete", 4)
            if any(not re.fullmatch(r"[0-9]{4}\.json", name) for name in os.listdir(self.grants_fd)):
                raise ActivationError("effect-unknown", "private grants layout diverged", 4)
            if any(not re.fullmatch(r"[0-9]{20}\.json", name) for name in os.listdir(self.progress_history_fd)):
                raise ActivationError("effect-unknown", "private progress history layout diverged", 4)
            allowed_payloads = {"0000.payload", "0000.payload.next"}
            if any(name not in allowed_payloads for name in os.listdir(self.stage_fd)) or any(name != "0000.payload" for name in os.listdir(self.backup_fd)) or any(name != "0000.payload" for name in os.listdir(self.discard_fd)):
                raise ActivationError("effect-unknown", "private payload layout diverged", 4)
            if any(not re.fullmatch(r"[0-9a-f]{32}\.json", name) for name in os.listdir(self.receipts_fd)):
                raise ActivationError("effect-unknown", "private receipts layout diverged", 4)
        except OSError as exc:
            raise ActivationError("effect-unknown", "private transaction layout cannot be listed", 4) from exc
        for (directory, name), expected in self.files.items():
            fd = getattr(self, f"{directory}_fd")
            try:
                _, observed = _read_stable_at(fd, name, f"pinned {directory}/{name}")
            except ActivationError as exc:
                raise ActivationError("effect-unknown", f"private {directory}/{name} namespace diverged", 4) from exc
            if observed != expected:
                raise ActivationError("effect-unknown", f"private {directory}/{name} changed", 4)


_ACTIVE_PRIVATE: PrivateTransaction | None = None


@contextlib.contextmanager
def _pin_private(target: Path, operation_id: str) -> Iterator[PrivateTransaction]:
    global _ACTIVE_PRIVATE
    if _ACTIVE_PRIVATE is not None:
        if _ACTIVE_PRIVATE.operation_id != operation_id:
            raise ActivationError("effect-unknown", "different private transaction is already pinned", 4)
        _ACTIVE_PRIVATE.assert_intact()
        yield _ACTIVE_PRIVATE
        return
    private = _private_transaction(target, operation_id)
    _ACTIVE_PRIVATE = private
    try:
        private.assert_intact()
        yield private
    finally:
        _ACTIVE_PRIVATE = None
        private.close()


def _require_private(target: Path, operation_dir: Path) -> PrivateTransaction:
    private = _ACTIVE_PRIVATE
    if private is None or private.operation_id != operation_dir.name:
        raise ActivationError("effect-unknown", "mutating transaction has no pinned private descriptors", 4)
    private.assert_intact()
    return private


class ActivationError(ValueError):
    def __init__(self, status: str, reason: str, code: int = 1):
        super().__init__(reason)
        self.status, self.reason, self.code = status, reason, code


EFFECT_NONE = "none"
EFFECT_UNKNOWN = "effect_unknown"


class _Effects:
    """What THIS invocation has already done, so no refusal can be reported as no effect.

    Decision 9 separates "I refused before touching anything" (3) from "something happened and
    the result is partial or unknown" (4). Those are indistinguishable to an operator unless the
    engine tracks its own effects, so it records each one and escalates any later refusal.

    THE DEFECT THIS CLOSES, and it is the sixth instance of one class in this project. Every
    refusal in this module travels as an `ActivationError` through one `except` clause per
    command, and those clauses decided the reported effect from a DEFAULT argument or from the
    raise site's own `code`. 312 raise sites are reachable from `apply_command` and the recover
    verbs, so "the site decides" means 312 independent decisions, and every one of them that
    fires after a product is published reports `effect: none` over bytes on disk. MEASURED on
    the unmodified engine, with `.agentic-sdlc/receipts/` injected between publication and
    `write_commit`'s poststate capture -- the one window `_validate_private_state` is reachable
    in after publication, through `capture_git_observation` ->
    `validate_internal_status_records`:

        control, no injection      -> 0 committed  effect=committed     published=True
        repo-local state injected  -> 3 refused    effect=none          published=True

    Exit 3 promises no journal or product effect. `AGENTS.md` was on disk. The trigger needs
    concurrent external mutation of a managed path, which this bundle declares unsupported, so
    the severity was bounded -- but the HANDLER'S SHAPE was the defect, and the same shape
    reported `effect: none` for every `stale`, `foreign-state`, and schema refusal raised after
    publication too.

    WHERE each effect is recorded is the whole contract: at the instant it becomes true, never
    once the operation that caused it has returned successfully. A file exists from its `open`
    onward, so admitting its creation after the write completes leaves the failing case --
    created, not written -- classified as though nothing had happened. A rename has happened
    from the instant `renameat2` returns 0, so admitting publication after the readback that
    follows it classifies a failed readback as though the product were still private.

    Admission therefore lives in the PRIMITIVES -- `_mkdir_at`, `_mkdir_new_at`, `_safe_mkdir`,
    `_write_new_at`, `write_new_metadata`, `_replace_metadata`, `_renameat2`, `_renameat2_at`,
    and `stage_payload`'s own staging open -- and not at the call sites that use them. That is
    what makes the next mutating step admit its effect for free: a per-raise-site `try/except`
    is the shape that failed twice in this project, because the next site added reintroduces the
    defect.
    """

    def __init__(self) -> None:
        self.admitted: list[str] = []

    def admit(self, effect: str) -> int:
        """Record an effect at the moment it happens; the token allows only re-describing it."""
        self.admitted.append(effect)
        return len(self.admitted) - 1

    def revise(self, token: int, effect: str) -> None:
        """Sharpen an admitted effect's description. It can be re-described, never withdrawn."""
        self.admitted[token] = effect

    def any(self) -> bool:
        return bool(self.admitted)


_EFFECTS = _Effects()


@contextlib.contextmanager
def _effect_ledger() -> Iterator[_Effects]:
    """Install one fresh ledger for one command invocation, then restore the previous one.

    Module-scoped for the same reason `_ACTIVE_PRIVATE` is: the effects are admitted six frames
    below the command handler, and threading a parameter through every helper is precisely the
    per-site bookkeeping that a future helper forgets. Restoring rather than clearing keeps a
    nested invocation -- a test driving two commands in one process, or a handler that calls
    another -- from erasing an outer command's admitted effects.
    """
    global _EFFECTS
    previous = _EFFECTS
    _EFFECTS = _Effects()
    try:
        yield _EFFECTS
    finally:
        _EFFECTS = previous


def _admit(effect: str) -> int:
    return _EFFECTS.admit(effect)


def _revise(token: int, effect: str) -> None:
    _EFFECTS.revise(token, effect)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8") + b"\n"


def digest_record(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    answer: dict[str, Any] = {}
    for key, value in pairs:
        if key in answer:
            raise ValueError("duplicate JSON key")
        answer[key] = value
    return answer


def _constant(_: str) -> None:
    raise ValueError("nonstandard JSON constant")


def _no_float(_: str) -> None:
    raise ValueError("JSON floats are not admitted")


def _canonical_load_bytes(raw: bytes, label: str) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ActivationError("refused", f"{label} has UTF-8 BOM", 2)
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_no_float)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ActivationError("refused", f"malformed {label}", 2) from exc
    if not isinstance(value, dict) or canonical_bytes(value) != raw:
        raise ActivationError("refused", f"noncanonical {label}", 2)
    return value


def read_stable_file(path: Path, label: str, *, private: bool = False) -> tuple[bytes, dict[str, Any]]:
    flags = os.O_RDONLY | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ActivationError("refused", f"cannot open {label}", 1) from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ActivationError("refused", f"unsafe {label}")
        raw = bytearray()
        while part := os.read(fd, 1 << 20):
            raw.extend(part)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ActivationError("refused", f"unstable {label}")
    return bytes(raw), file_identity_from_stat(after, bytes(raw))


def load_canonical_json(path: Path, label: str = "record") -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = read_stable_file(path, label)
    return _canonical_load_bytes(raw, label), identity


def file_identity_from_stat(value: os.stat_result, raw: bytes | None = None) -> dict[str, Any]:
    return {
        "dev": value.st_dev, "ino": value.st_ino, "mode": stat.S_IMODE(value.st_mode), "nlink": value.st_nlink,
        "size": value.st_size, "mtime_ns": value.st_mtime_ns, "ctime_ns": value.st_ctime_ns,
        "sha256": hashlib.sha256(raw if raw is not None else Path("/proc/self/fd/0").read_bytes()).hexdigest(),
    }


_CUSTODY_KEYS = ("dev", "ino", "mode", "nlink", "size", "sha256")


def custody_identity(identity: dict[str, Any]) -> dict[str, Any]:
    """Identity stable through a rename but not an inode substitution."""
    return {key: identity[key] for key in _CUSTODY_KEYS}


def _validate_custody_identity(value: Any, label: str = "custody identity") -> dict[str, Any]:
    value = _exact(value, set(_CUSTODY_KEYS), label)
    for key in _CUSTODY_KEYS[:-1]:
        _integer(value[key], key)
    _hash(value["sha256"])
    return value


def _same_custody_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return custody_identity(left) == custody_identity(right)


def _file_identity(path: Path) -> dict[str, Any]:
    raw, identity = read_stable_file(path, str(path))
    return identity


_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(_Statx)]
_LIBC.statx.restype = ctypes.c_int


def _mount_id_fd(fd: int) -> int:
    if sys.platform != "linux":
        raise ActivationError("unsupported", "P2 requires Linux statx mount IDs")
    result = _LIBC.statx(fd, ctypes.c_char_p(b""), _AT_EMPTY_PATH, _STATX_BASIC_STATS | _STATX_MNT_ID, ctypes.byref(info := _Statx()))
    if result != 0 or not (info.stx_mask & _STATX_MNT_ID):
        raise ActivationError("unsupported", "statx mount IDs are unavailable")
    return int(info.stx_mnt_id)


def _dir_identity_fd(fd: int) -> dict[str, Any]:
    value = os.fstat(fd)
    if not stat.S_ISDIR(value.st_mode) or value.st_nlink < 1:
        raise ActivationError("unsupported", "unsafe directory descriptor")
    return {"dev": value.st_dev, "ino": value.st_ino, "mode": stat.S_IMODE(value.st_mode), "mount_id": _mount_id_fd(fd)}


def dir_identity(path: Path) -> dict[str, Any]:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError as exc:
        raise ActivationError("unsupported", f"missing directory {path}") from exc
    try:
        return _dir_identity_fd(fd)
    finally:
        os.close(fd)


def statx_fd(fd: int) -> dict[str, Any]:
    return _dir_identity_fd(fd)


def open_component_dir(parent_fd: int, name: str) -> int:
    return os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)


def open_regular_at(parent_fd: int, name: str) -> int:
    return os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)


def _read_stable_at(parent_fd: int, name: str, label: str) -> tuple[bytes, dict[str, Any]]:
    try:
        fd = open_regular_at(parent_fd, name)
    except OSError as exc:
        raise ActivationError("effect-unknown", f"cannot open pinned {label}", 4) from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ActivationError("effect-unknown", f"unsafe pinned {label}", 4)
        raw = bytearray()
        while part := os.read(fd, 1 << 20):
            raw.extend(part)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ActivationError("effect-unknown", f"unstable pinned {label}", 4)
    return bytes(raw), file_identity_from_stat(after, bytes(raw))


def _load_canonical_json_at(parent_fd: int, name: str, label: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw, identity = _read_stable_at(parent_fd, name, label)
    return _canonical_load_bytes(raw, label), identity


def _mkdir_at(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        # Opening an already-present directory is not an effect of THIS invocation, so it
        # admits nothing: over-admitting would turn every ordinary re-entry into exit 4.
        pass
    else:
        _admit(f"created private directory {name}")
    child_fd = open_component_dir(parent_fd, name)
    try:
        os.fchmod(child_fd, 0o700)
        os.fsync(child_fd)
        os.fsync(parent_fd)
        return child_fd
    except BaseException:
        os.close(child_fd)
        raise


def _mkdir_new_at(parent_fd: int, name: str) -> int:
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError as exc:
        raise ActivationError("effect-unknown", f"private {name} already exists", 4) from exc
    # Admitted here rather than left to `_mkdir_at`: this call already created the directory, so
    # `_mkdir_at`'s own `mkdir` will take the FileExistsError branch and admit nothing.
    _admit(f"created private directory {name}")
    return _mkdir_at(parent_fd, name)


def _renameat2_at(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
    call = getattr(_LIBC, "renameat2", None)
    if call is None:
        raise ActivationError("unsupported", "Linux renameat2 is unavailable")
    result = call(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), flags)
    if result:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise ActivationError("stale", "publication compare-and-swap failed")
        raise ActivationError("effect-unknown", f"renameat2 failed: {os.strerror(error)}", 4)
    # The namespace changed the instant this returned 0 -- before the fsyncs, before any
    # readback. A publication is exactly this call, so admitting it later would let a failed
    # post-publication readback report a clean pre-effect refusal over live bytes.
    _admit(f"renamed {source} onto {destination} (flags {flags})")
    os.fsync(source_fd)
    if destination_fd != source_fd:
        os.fsync(destination_fd)


def _open_transaction_private(target_fd: int, plane: StatePlane, operation_id: str) -> int:
    state_fd = _open_plane_root(plane, target_fd)
    try:
        transactions_fd = open_component_dir(state_fd, "transactions")
    finally:
        os.close(state_fd)
    try:
        return open_component_dir(transactions_fd, operation_id)
    finally:
        os.close(transactions_fd)


def _open_live_parent_at(target_fd: int, relative: str) -> tuple[int, str]:
    pieces = _relative(relative).split("/")
    current = os.dup(target_fd)
    try:
        for part in pieces[:-1]:
            child = open_component_dir(current, part)
            os.close(current)
            current = child
        return current, pieces[-1]
    except BaseException:
        os.close(current)
        raise


def _capture_prestate_at(target_fd: int, relative: str) -> tuple[dict[str, Any], bytes | None]:
    parent_fd, name = _open_live_parent_at(target_fd, relative)
    try:
        try:
            value = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return {"kind": "absent", "identity": None}, None
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
            raise ActivationError("effect-unknown", "managed target is no longer a single-link regular file", 4)
        raw, identity = _read_stable_at(parent_fd, name, "managed target")
        return {"kind": "regular", "identity": identity}, raw
    finally:
        os.close(parent_fd)


def _private_transaction(target: Path, operation_id: str) -> PrivateTransaction:
    plane = _resolve_plane(target)
    target_fd = open_root_chain(target)
    try:
        state_fd = _open_plane_root(plane, target_fd)
        receipts_fd = open_component_dir(state_fd, "receipts")
        transactions_fd = open_component_dir(state_fd, "transactions")
        operation_fd = open_component_dir(transactions_fd, operation_id)
        grants_fd = open_component_dir(operation_fd, "grants")
        stage_fd = open_component_dir(operation_fd, "stage")
        backup_fd = open_component_dir(operation_fd, "backup")
        discard_fd = open_component_dir(operation_fd, "discard")
        progress_history_fd = open_component_dir(operation_fd, "progress-history")
        ptx = PrivateTransaction(target, plane, target_fd, state_fd, receipts_fd, transactions_fd, operation_fd, grants_fd, stage_fd, backup_fd, discard_fd, progress_history_fd, {}, operation_id)
        ptx.identities = {name: _dir_identity_fd(fd) for name, fd in (
            ("target", target_fd), ("state", state_fd), ("receipts", receipts_fd), ("transactions", transactions_fd),
            ("operation", operation_fd), ("grants", grants_fd), ("stage", stage_fd), ("backup", backup_fd), ("discard", discard_fd), ("progress_history", progress_history_fd),
        )}
        # Pin all extant transaction witnesses.  This is deliberately a closed
        # set: unknown names are classified by the existing state validator.
        for name in ("operation.json", "progress.json", "commit.json", "rollback.json", "receipt.json.next"):
            try:
                ptx.track_file("operation", name)
            except ActivationError:
                if name in {"operation.json", "progress.json"}:
                    raise
        for name in os.listdir(grants_fd):
            ptx.track_file("grants", name)
        for name in os.listdir(stage_fd):
            ptx.track_file("stage", name)
        for name in os.listdir(backup_fd):
            ptx.track_file("backup", name)
        for name in os.listdir(discard_fd):
            ptx.track_file("discard", name)
        for name in os.listdir(progress_history_fd):
            ptx.track_file("progress_history", name)
        try:
            ptx.track_file("receipts", f"{operation_id}.json")
        except ActivationError:
            pass
        return ptx
    except BaseException:
        for fd in (locals().get("progress_history_fd"), locals().get("discard_fd"), locals().get("backup_fd"), locals().get("stage_fd"), locals().get("grants_fd"), locals().get("operation_fd"), locals().get("transactions_fd"), locals().get("receipts_fd"), locals().get("state_fd"), target_fd):
            if isinstance(fd, int):
                try:
                    os.close(fd)
                except OSError:
                    pass
        raise


def open_root_chain(target: Path) -> int:
    if sys.platform != "linux" or not target.is_absolute():
        raise ActivationError("unsupported", "target must be an absolute Linux path")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        root_mount = _mount_id_fd(fd)
        for part in target.parts[1:]:
            child = open_component_dir(fd, part)
            os.close(fd)
            fd = child
            if _mount_id_fd(fd) != root_mount:
                raise ActivationError("unsupported", "target chain crosses a mount boundary")
        return fd
    except BaseException:
        os.close(fd)
        raise


def bind_target(target: Path) -> RootBinding:
    fd = open_root_chain(target)
    try:
        return RootBinding(target, _dir_identity_fd(fd))
    finally:
        os.close(fd)


def _state_home_candidates() -> list[Path]:
    """Every state home this engine can name, the selected one first.

    Setting `XDG_STATE_HOME` after a plane was written under the `$HOME/.local/state`
    fallback is a plane switch spelled differently, so the fallback stays nameable even
    when the variable is set and `_assert_unselected_planes_empty` probes it too. The
    order is load-bearing: `_state_home` is the head of this list and its refusals are
    unchanged.
    """
    candidates: list[Path] = []
    value = os.environ.get("XDG_STATE_HOME", "")
    if value:
        # The XDG spec says to ignore a relative value. Ignoring it silently would move
        # the plane somewhere the operator did not name, so refuse instead: the default
        # has to be unambiguous, and "unset" and "misset" are different states.
        if not Path(value).is_absolute():
            raise ActivationError("refused", "XDG_STATE_HOME is not an absolute path", 2)
        candidates.append(Path(value))
    home = os.environ.get("HOME", "")
    if home and Path(home).is_absolute():
        candidates.append(Path(home) / ".local" / "state")
    if not candidates:
        raise ActivationError("refused", "cannot resolve the ccodex XDG state plane", 2)
    return candidates


def _state_home() -> Path:
    return _state_home_candidates()[0]


def _assert_keyable_target(target: Path) -> None:
    """Refuse a target path that would key one checkout to two plane entries.

    `open_root_chain` opens every component `O_NOFOLLOW`, so an admitted target path
    carries no symlinked component and is already its own realpath; `.` and `..` are the
    only remaining way to spell one directory two ways, and the key is derived from the
    exact string.
    """
    if not target.is_absolute():
        raise ActivationError("unsupported", "target must be an absolute Linux path")
    if any(part in {".", ".."} for part in target.parts):
        raise ActivationError("refused", "target path is not in normal form", 2)


def _plane_key(target: Path) -> str:
    """Key on the exact absolute target path.

    It distinguishes a linked worktree from its parent, which the Git common directory
    would not (issues/09 requires a separately keyed receipt for each). It is
    deliberately NOT stable across a rename: every record in the plane pins
    `operation.target.path` and `_bind_operation_target` refuses when it differs, so a
    key that followed a rename would only carry an already-unusable journal into the
    renamed checkout and leave it permanently `effect-unknown`. A rename therefore yields
    a fresh empty key plus an orphaned entry no target can reach.

    Device+inode keying was rejected for the reverse failure: inode reuse after a
    checkout is deleted would hand an unrelated new directory a stale journal whose
    pinned path no longer exists, which is exactly the state no recovery decision can
    classify.
    """
    return hashlib.sha256(str(target).encode("utf-8")).hexdigest()


def _plane_root(target: Path) -> Path:
    return _state_home().joinpath(*PLANE_NAMESPACE, _plane_key(target))


def _plane_selection() -> str:
    value = os.environ.get(PLANE_SELECTION_ENV, "")
    if value and value != PLANE_REPO_LOCAL:
        raise ActivationError("refused", "invalid activation state plane selection", 2)
    return value


def _resolve_plane(target: Path) -> StatePlane:
    """Resolve the one plane for this invocation, creating nothing.

    The selection is environmental and no record binds the plane it was written into --
    binding one there would not help, because with the selection moved the engine never
    opens that record. `_assert_unselected_planes_empty` closes the hole from the other
    side instead: every plane this invocation did NOT select is probed for state, and
    finding any is a clean refusal.
    """
    _assert_keyable_target(target)
    if _plane_selection() == PLANE_REPO_LOCAL:
        return StatePlane(target, target / STATE_DIR_NAME, repo_local=True)
    return StatePlane(target, _plane_root(target), repo_local=False)


def _plane_pointer_name(root: Path) -> str:
    """Name a pointer after the plane it records, so the name binds the content."""
    return f"{PLANE_POINTER_PREFIX}{hashlib.sha256(str(root).encode('utf-8')).hexdigest()}.json"


def _plane_pointer_record(path: Path) -> Path:
    """The plane root one pointer records, or a `foreign-state` refusal.

    The recorded value must be an absolute path in normal form whose own digest is the
    filename, so a pointer cannot be renamed onto a different plane, and a forged name in the
    family cannot carry an arbitrary body. Nothing here trusts the value as a plane: it is
    only ever used as a probe destination and as a candidate root, never opened for writing.
    """
    try:
        record, _ = load_canonical_json(path, "plane pointer")
        record = _exact(record, {"schema", "plane"}, "plane pointer")
        value = record["plane"]
        if record["schema"] != PLANE_POINTER_SCHEMA or not isinstance(value, str) or not value:
            raise ActivationError("foreign-state", "invalid plane pointer")
        root = Path(value)
        if not root.is_absolute() or str(root) != value or any(part in {".", ".."} for part in root.parts):
            raise ActivationError("foreign-state", "invalid plane pointer")
        if _plane_pointer_name(root) != path.name:
            raise ActivationError("foreign-state", "plane pointer does not bind its plane")
    except ActivationError as exc:
        if exc.status == "foreign-state":
            raise
        raise ActivationError("foreign-state", "invalid plane pointer") from exc
    return root


def _assert_plane_pointer(path: Path, root: RootBinding) -> Path:
    """Admit one pointer under the SAME custody rules as `receipts`/`transactions`.

    Widening the `.agentic-sdlc/` whitelist by this name family is not a loosening of the
    rule the whitelist enforces: unlike `repo.toml` and `rightsize/`, which are Git-materialized
    and therefore only `_assert_cloneable_private_node`-clean, a pointer is written by this
    engine alone and is held to exact 0600, single-link, non-symlink, on-the-bound-mount
    custody -- the private rule. A committed copy of a pointer materializes at the caller's
    umask and is refused here by name rather than silently trusted, which is the intended
    behaviour: `.gitignore` records that this file is machine-local and never committed.
    """
    _assert_private_file(path, root, "plane pointer")
    return _plane_pointer_record(path)


def _plane_pointer_roots(target: Path, root: RootBinding) -> list[Path]:
    """Every plane root this checkout itself records, validated, in a stable order.

    This is the half of the candidate set that a rename cannot destroy, because it lives
    inside the directory being renamed. An absent state root, or one holding no pointer, is
    an empty list rather than a refusal: pointers postdate the plane, so a checkout activated
    before them has none, and that is the pre-pointer behaviour unchanged.
    """
    state = target / STATE_DIR_NAME
    try:
        names = sorted(item for item in os.listdir(state) if item.startswith(PLANE_POINTER_PREFIX))
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError as exc:
        raise ActivationError("refused", PLANE_PROBE_REASON, 3) from exc
    return [_assert_plane_pointer(state / name, root) for name in names]


def _plane_candidates(target: Path, root: RootBinding) -> list[StatePlane]:
    """Every plane one target's state could be in that this engine can name exactly.

    Three sources, and the third is what makes the set closed rather than merely broad:
    the repo-local override's fixed target subdirectory, one default-layout plane per
    nameable state home, and one per plane root this checkout's own pointers record. The
    pointers are load-bearing for the two cases the environment cannot describe -- a renamed
    checkout, whose key changed, and a state home relocated to a directory neither
    `XDG_STATE_HOME` nor `$HOME` names any more.

    SURVIVING MUTANT, reported rather than papered over: deleting the repo-local entry from
    this list leaves the suite green, because when it is the UNSELECTED plane
    `_validate_repository_state_root` has already refused the same two surfaces --
    `receipts`/`transactions` and the `.agentic-sdlc.intent.`/`.agentic-sdlc.noop.` families
    -- by `LEGACY_STATE_REASON`, and it runs first. No input distinguishes the two, so no
    honest test can. It stays for the same reason as the defensive raise in
    `_mkdir_plane_root`: `LEGACY_STATE_REASON` is a migration-era name for state that
    "predates the ccodex state plane", and the day that check is retired this list is the only
    thing standing between a repo-local journal and a clean `inactive` report.
    """
    planes = [StatePlane(target, target / STATE_DIR_NAME, repo_local=True)]
    seen: set[Path] = {planes[0].root}
    key = _plane_key(target)
    for home in _state_home_candidates():
        candidate = home.joinpath(*PLANE_NAMESPACE, key)
        if candidate not in seen:
            seen.add(candidate)
            planes.append(StatePlane(target, candidate, repo_local=False))
    for recorded in _plane_pointer_roots(target, root):
        # A recorded root is always a default-layout plane root: `_record_plane_pointer`
        # writes no pointer for the repo-local override, so no inference about layout is
        # needed here and none is made. The environment's own candidates are appended FIRST, so
        # a plane the environment can still name keeps its ordinary label and only a plane that
        # nothing but the pointer names is reported as recorded.
        if recorded not in seen:
            seen.add(recorded)
            planes.append(StatePlane(target, recorded, repo_local=False, recorded=True))
    return planes


def _plane_entries(path: Path, label: str) -> list[str]:
    """Names in one plane directory, where "cannot tell" is never reported as absence.

    Only `ENOENT` and `ENOTDIR` are absence -- nothing can exist under a non-directory.
    `EACCES`, `ELOOP`, and every other error mean the probe cannot see whether state is there,
    which is exactly the case that must not become `inactive`, so it refuses. Deliberately not
    `Path.exists()` or a bare `except OSError`: both turn an unreadable plane into an empty one.
    """
    try:
        return os.listdir(path)
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError as exc:
        raise ActivationError("refused", f"{PLANE_PROBE_REASON}: {label}", 3) from exc


def _recorded_plane_entries(plane: StatePlane) -> list[str]:
    """Names in a plane root ONLY this checkout's own pointer names, where absence is UNKNOWN.

    The asymmetry with `_plane_entries` is the whole point, and reversing one sentence of the
    previous round's reasoning is the change: "the probe reads the plane, not the pointer, so a
    pointer to a missing or empty plane yields `inactive` honestly" is true of EMPTY and false
    of MISSING. A pointer records that this checkout wrote its activation state into that exact
    absolute root. A root that cannot be listed -- gone, replaced by a non-directory, or
    unreadable -- is therefore not "no state"; it is a recorded write destination this
    invocation cannot reach, which is precisely "I cannot tell whether an effect exists".

    THE ORDINARY ARRANGEMENT THAT PRODUCES IT, and the reason a rename of the checkout alone was
    not the whole case: one `mv` of a home directory holding BOTH the checkout and the plane.
    That is the common layout -- a checkout under `$HOME`, the plane under
    `$HOME/.local/state` -- so a single move relocates both. The pointer's recorded root names a
    path that no longer exists, while the state itself moved with the home into a root the new
    key does not name and no pointer records. MEASURED before this function existed: `inspect`,
    `status`, and `plan` all reported `inactive` with `effect: none` at exit 0 over a published
    product with an unresolved journal, and a second apply was admitted. HEAD answered exit 4
    for the same operation.

    Exit 4, not the exit-3 refusal `_plane_entries` raises for an unreadable plane, because the
    two are different claims: exit 3 says "nothing happened here and I declined", and this
    invocation cannot say the first half. Deliberately no further detection mechanism -- every
    round of this ticket tried to make the engine KNOW and found another case where it cannot,
    so keeping "I cannot tell" available for exactly these cases IS the answer.

    A recorded root that DOES list is classified by the same rules as any other plane, so one
    that resolves and is genuinely EMPTY stays honestly `inactive` at exit 0 and admits the
    retry: there the engine can prove the absence. A checkout with no pointer at all reaches
    none of this, because `_plane_candidates` adds no recorded candidate for it.
    """
    try:
        return os.listdir(plane.root)
    except OSError as exc:
        raise ActivationError("effect-unknown", RECORDED_PLANE_UNRESOLVED_REASON, 4) from exc


def _plane_holds_state(plane: StatePlane) -> bool:
    """Does this plane hold any activation record for its target? Names only, no content.

    Presence rather than resolution state, for two reasons. A committed receipt in an
    unselected plane is the same double-apply hazard as an unresolved journal -- the
    selected plane would report `inactive` and admit a second effectful owner for a path
    another plane already owns. And classifying a foreign plane's records would mean
    validating them, which can itself fail `effect-unknown` over state this invocation
    never intends to touch; a presence probe can only ever produce a clean refusal.

    EXHAUSTIVE BY CONSTRUCTION for a default plane root, rather than by a list of the record
    kinds that exist today: nothing but this engine's own records is ever created in a key
    directory, so ANY entry is state. A list would have to be revisited every time a record kind
    is added -- and a probe that silently outgrows the surface it probes is how this defect
    class keeps coming back. An existing but EMPTY key directory is correctly not state: it is
    the crash window between creating the plane and writing its first record, in which nothing
    was published. For a RECORDED root the same empty directory is still not state, but a root
    that cannot be listed at all is no longer read as empty -- `_recorded_plane_entries` raises
    `effect-unknown` there, so this function does not always return.

    The repo-local root is shared with the tracked PUBLIC half of `.agentic-sdlc/`, so there the
    non-state names are excluded by name instead: `repo.toml` and `rightsize/` exist on every
    activated repository, and a pointer is a name FOR state elsewhere rather than state itself.
    Treating any of the three as state would refuse every default-plane invocation on an
    activated checkout. Anything else in that root is either state or a name
    `_validate_repository_state_root` refuses outright, so counting it as state is safe in both
    directions. The repo-local anchors sit at the target root, which is why the second listing
    is of `anchor_dir` rather than of the plane root.

    SURVIVING MUTANT, reported rather than papered over: replacing that final anchor/audit
    listing with `False` leaves the suite green, for the same reason the repo-local entry in
    `_plane_candidates` does. Reaching it requires the repo-local plane to be a candidate --
    which means it is NOT selected -- and `_validate_repository_state_root` has already refused
    exactly the `.agentic-sdlc.intent.`/`.agentic-sdlc.noop.` families by `LEGACY_STATE_REASON`
    before the probe runs. No input distinguishes the two, so no honest test can, and writing one
    that cannot fail would be worse than this note. The opposite direction IS reachable and
    tested: widening either exclusion above makes ordinary activated checkouts refuse.
    """
    entries = _recorded_plane_entries(plane) if plane.recorded else _plane_entries(plane.root, plane.label)
    if not plane.repo_local:
        return bool(entries)
    public = {REPO_MANIFEST_NAME, RIGHTSIZE_DIR_NAME}
    if any(name not in public and not name.startswith(PLANE_POINTER_PREFIX) for name in entries):
        return True
    return any(name.startswith(plane.anchor_prefix) or name.startswith(plane.audit_prefix) for name in _plane_entries(plane.anchor_dir, plane.label))


def _assert_unselected_planes_empty(target: Path, root: RootBinding, plane: StatePlane) -> None:
    """Refuse when a plane this invocation did not select holds state for this target.

    THE DEFECT THIS CLOSES: the plane came only from the environment, so crashing an apply
    after publication in the default plane and then selecting `repo-local` made the engine
    report `inactive` with `effect: none` at exit 0 over a published product with an
    unresolved journal, and admit a second apply. That is a positive claim of no-effect
    over an admitted partial effect. It was reachable through the engine's own documented
    remedy for a cross-device plane, which is what made a recorded comment insufficient.

    Symmetric by construction, not by two special cases: the reason names the plane that
    holds the state and the probe runs for both directions. The reverse direction
    (repo-local crash, then default selection) is ALSO refused earlier and by a different
    name -- `_validate_repository_state_root` raises `LEGACY_STATE_REASON` for exactly that
    surface -- so this check is the one that fires for the default-to-repo-local switch and
    for a state home that moved between the two nameable defaults.

    SELECTION IS NOT THE ONLY WAY TO MOVE A PLANE, and the first fix for the defect above
    learned it the expensive way: the key is derived from the absolute target path, so
    RENAMING the checkout -- or moving `XDG_STATE_HOME` to a third directory, or `HOME` --
    also resolves a fresh empty plane while the old one still holds the journal. Probing only
    the environment's own planes reported `inactive` with `effect: none` at exit 0 over a
    published product and admitted a second effectful apply, which is the same defect one
    surface along. `_plane_candidates` therefore includes every plane root this checkout's own
    pointers record, and a pointer is written before the plane receives any record. What
    remains outside the probe is state whose pointer AND journal were both destroyed, which is
    the pre-existing "the operator deleted the journal" limit rather than a new one.
    """
    for candidate in _plane_candidates(target, root):
        # A plane's identity is its root: the repo-local root's last component is
        # `.agentic-sdlc` and every default root's is a 64-char key digest, so equal roots
        # mean the same plane and no second field can distinguish them.
        if candidate.root == plane.root:
            continue
        if _plane_holds_state(candidate):
            if candidate.recorded:
                raise ActivationError("refused", RECORDED_PLANE_REASON, 3)
            raise ActivationError("refused", f"{UNSELECTED_PLANE_REASON}: {candidate.label}", 3)


def _assert_plane_device(plane: StatePlane, root: RootBinding) -> None:
    """Refuse a plane that cannot exchange objects with the target atomically.

    Publication is `renameat2` between the plane's `stage/` and the live product, and
    rollback is `RENAME_EXCHANGE` between the live product and `backup/`. Both are
    confined to one mounted filesystem -- measured: plain rename, `RENAME_EXCHANGE`, and
    `RENAME_NOREPLACE` all return `EXDEV` across devices -- so a cross-device plane cannot
    be made atomic by any amount of care. Equal `mount_id` as well as equal `st_dev`,
    because the kernel refuses a rename across two mounts of one superblock too.

    This is a clean refusal before any effect, and the remedy it names is the repo-local
    override, which keeps the state on the target's own filesystem by construction.
    """
    if plane.repo_local:
        return
    identity = _deepest_existing_dir_identity(plane.root)
    if identity["dev"] != root.identity["dev"] or identity["mount_id"] != root.identity["mount_id"]:
        raise ActivationError("refused", PLANE_DEVICE_REASON, 3)


def _deepest_existing_dir_identity(path: Path) -> dict[str, Any]:
    """Identity of the deepest existing ancestor, which is the device a child inherits.

    Only `ENOENT` walks up. A symlinked or non-directory ancestor is refused rather than
    skipped, because skipping it would compare the device of a node that is not the one a
    later `mkdir` would land in.
    """
    current = path
    while True:
        try:
            fd = os.open(current, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
        except FileNotFoundError as exc:
            if current.parent == current:
                raise ActivationError("refused", PLANE_ANCESTOR_REASON, 3) from exc
            current = current.parent
            continue
        except OSError as exc:
            raise ActivationError("refused", PLANE_ANCESTOR_REASON, 3) from exc
        try:
            return _dir_identity_fd(fd)
        finally:
            os.close(fd)


def _open_plane_root(plane: StatePlane, target_fd: int) -> int:
    """Open the plane root through one strict no-follow, single-mount chain."""
    if plane.repo_local:
        return open_component_dir(target_fd, STATE_DIR_NAME)
    return open_root_chain(plane.root)


def _relative(path: str) -> str:
    if not isinstance(path, str) or unicodedata.normalize("NFC", path) != path or not path or path.startswith("/") or "\\" in path:
        raise ActivationError("refused", "invalid relative path", 2)
    components = path.split("/")
    if any(item in {"", ".", ".."} or not _REL.fullmatch(item) for item in components):
        raise ActivationError("refused", "invalid relative path", 2)
    return path


def _exact(value: Any, keys: set[str], label: str, code: int = 2) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ActivationError("refused", f"invalid {label} schema", code)
    return value


def _integer(value: Any, label: str) -> int:
    if type(value) is not int or value < -(2**63) or value > 2**63 - 1:
        raise ActivationError("refused", f"invalid {label}", 2)
    return value


def _hash(value: Any, label: str = "digest") -> str:
    if not isinstance(value, str) or not _HEX64.fullmatch(value):
        raise ActivationError("refused", f"invalid {label}", 2)
    return value


def _id(value: Any, label: str = "id") -> str:
    if not isinstance(value, str) or not _HEX32.fullmatch(value):
        raise ActivationError("refused", f"invalid {label}", 2)
    return value


def _mount_id_path(path: Path, *, directory: bool = False) -> int:
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    if directory:
        flags |= os.O_DIRECTORY
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ActivationError("refused", f"cannot open {path} for mount check") from exc
    try:
        return _mount_id_fd(fd)
    finally:
        os.close(fd)


def capture_prestate(target: Path, relative: str) -> tuple[dict[str, Any], bytes | None]:
    path = target.joinpath(*_relative(relative).split("/"))
    _assert_safe_parent(target, relative)
    try:
        value = path.lstat()
    except FileNotFoundError:
        return {"kind": "absent", "identity": None}, None
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
        raise ActivationError("refused", "managed target is not a single-link regular file")
    if _mount_id_path(path) != bind_target(target).identity["mount_id"]:
        raise ActivationError("unsupported", "managed target crosses a mount boundary")
    raw, identity = read_stable_file(path, "managed target")
    return {"kind": "regular", "identity": identity}, raw


def _assert_safe_parent(target: Path, relative: str) -> None:
    current = target
    root = bind_target(target).identity
    for component in _relative(relative).split("/")[:-1]:
        current /= component
        try:
            value = current.lstat()
        except FileNotFoundError as exc:
            raise ActivationError("refused", "managed parent is missing") from exc
        if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode) or value.st_dev != root["dev"] or _mount_id_path(current, directory=True) != root["mount_id"]:
            raise ActivationError("refused", "unsafe managed parent")


def _tool_identity(path: Path) -> dict[str, Any]:
    _, identity = read_stable_file(path, "canonical tool")
    return {"path": str(path), "identity": identity}


def _load_generator():
    source = Path(__file__).with_name("instruction-generator.py")
    raw, identity = read_stable_file(source, "canonical generator")
    if _tool_identity(source)["identity"] != identity:
        raise ActivationError("refused", "canonical generator changed during custody check")
    module = types.ModuleType("_agentic_sdlc_p2_generator")
    module.__file__ = str(source)
    try:
        exec(compile(raw, str(source), "exec"), module.__dict__)
    except (SyntaxError, ValueError) as exc:
        raise ActivationError("unsupported", "cannot compile verified canonical generator") from exc
    return module


def render_and_bind_selected_output(target: Path, manifest: dict[str, Any], selected_path: str) -> tuple[dict[str, Any], dict[str, Any], bytes | None]:
    generator = _load_generator()
    observed: dict[str, Any] = {}
    old: bytes | None = None

    def reader(path: str):
        nonlocal old
        if path != selected_path or "seen" in observed:
            raise ActivationError("refused", "generator requested undeclared target")
        observed["seen"] = True
        prestate, old = capture_prestate(target, path)
        observed["prestate"] = prestate
        return prestate, old

    rendered = generator.render_selected(manifest, selected_path, reader)
    if "seen" not in observed:
        raise ActivationError("refused", "generator did not read selected target")
    content = rendered["content"]
    desired = {"mode": rendered["mode"], "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    return rendered, observed["prestate"], old


def _git_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_ATTR_NOSYSTEM": "1", "LC_ALL": "C", "LANG": "C"})
    return env


def _git(target: Path, *args: str) -> bytes:
    result = subprocess.run([
        "git", "--no-optional-locks", f"--git-dir={target / '.git'}", f"--work-tree={target}",
        "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *args,
    ], env=_git_env(), capture_output=True)
    if result.returncode:
        raise ActivationError("unsupported", "controlled Git observation failed")
    return result.stdout


class PorcelainRecord:
    def __init__(self, raw: bytes, kind: bytes, paths: tuple[bytes, ...]):
        self.raw = raw
        self.kind = kind
        self.paths = paths


def parse_porcelain_v2_z(raw: bytes) -> list[PorcelainRecord]:
    """Parse exact porcelain-v2 -z records without lossy whitespace splitting."""
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    records: list[PorcelainRecord] = []
    seen: set[bytes] = set()
    index = 0
    while index < len(fields):
        record = fields[index]
        if not record:
            raise ActivationError("refused", "malformed empty porcelain-v2 record")
        kind = record[:1]
        if kind in {b"?", b"!"}:
            if record[1:2] != b" " or not record[2:]:
                raise ActivationError("refused", "malformed porcelain-v2 path record")
            parsed = PorcelainRecord(record, kind, (record[2:],))
        elif kind == b"1":
            parts = record.split(b" ", 8)
            if len(parts) != 9 or parts[0] != b"1" or not parts[8]:
                raise ActivationError("refused", "malformed porcelain-v2 type-1 record")
            parsed = PorcelainRecord(record, kind, (parts[8],))
        elif kind == b"2":
            parts = record.split(b" ", 9)
            if len(parts) != 10 or parts[0] != b"2" or not parts[9] or index + 1 >= len(fields) or not fields[index + 1]:
                raise ActivationError("refused", "malformed porcelain-v2 type-2 record")
            parsed = PorcelainRecord(record + b"\0" + fields[index + 1], kind, (parts[9], fields[index + 1]))
            index += 1
        elif kind == b"u":
            parts = record.split(b" ", 10)
            if len(parts) != 11 or parts[0] != b"u" or not parts[10]:
                raise ActivationError("refused", "malformed porcelain-v2 unmerged record")
            parsed = PorcelainRecord(record, kind, (parts[10],))
        else:
            raise ActivationError("refused", "malformed porcelain-v2 record")
        if parsed.raw in seen:
            raise ActivationError("refused", "duplicate porcelain-v2 record")
        seen.add(parsed.raw)
        records.append(parsed)
        index += 1
    return records


def normalize_porcelain_v2_z(raw: bytes, *, filtered_internal: set[str]) -> bytes:
    filtered = {item.encode("utf-8") for item in filtered_internal}
    records = [record.raw for record in parse_porcelain_v2_z(raw) if not any(path in filtered for path in record.paths)]
    return b"".join(item + b"\0" for item in sorted(records))


def validate_internal_status_records(target: Path, raw: bytes) -> set[str]:
    """Return only status paths justified by validated private witnesses.

    A name is never sufficient to suppress a Git record: the whole private tree,
    including any root anchor/audit, has already passed its schema and custody
    checks before this function admits it to the projection.

    In the default plane the ONLY machine-local activation state in the worktree is the plane
    pointer family, so that is all this suppresses there. Full suppression survives for the
    repo-local override, which is the one selection that still materializes `receipts/`,
    `transactions/`, and the anchors inside the tree.
    """
    root = bind_target(target)
    # NOT an admission surface: `write_commit` reaches this through
    # `capture_git_observation` to capture the POSTSTATE, after the product is published.
    # A refusal raised from here is reported as `effect: none` over published bytes, so the
    # unselected-plane probe stays out of it -- see `_validate_private_state`.
    _validate_private_state(target, root, admission=False)
    repo_local = _resolve_plane(target).repo_local
    # Exact names, derived from the pointers that just passed custody and content validation --
    # never a prefix match on the family. A name in the family that is not a valid pointer never
    # reaches this function, because `_validate_repository_state_root` refuses it as
    # `foreign-state` first, so this set is the earned suppression and nothing wider.
    pointers = {f"{STATE_DIR_NAME}/{_plane_pointer_name(item)}" for item in _plane_pointer_roots(target, root)}
    filtered: set[str] = set()
    for parsed in parse_porcelain_v2_z(raw):
        try:
            paths = tuple(path.decode("utf-8", "strict") for path in parsed.paths)
        except UnicodeDecodeError as exc:
            raise ActivationError("refused", "invalid porcelain-v2 path encoding") from exc
        for path in paths:
            if path == f".agentic-sdlc/{REPO_MANIFEST_NAME}":
                # Tracked portable intent stays VISIBLE to the Git projection. Hiding it
                # would let a dirty manifest pass _require_clean, so an uncommitted edit
                # to repository policy could ride along inside an approved activation.
                continue
            if path == f".agentic-sdlc/{RIGHTSIZE_DIR_NAME}" or path.startswith(f".agentic-sdlc/{RIGHTSIZE_DIR_NAME}/"):
                # ADR-0015's rendered trio also stays VISIBLE, for a weaker but sufficient
                # reason. It is not load-bearing activation input the way the manifest is, so
                # nothing rides along; but suppressing a Git record has to be EARNED by the
                # path being machine-local private state, and this one is not. `receipts/`
                # and `transactions/` earn it -- per-checkout hashes, tool identities, trust,
                # and `.gitignore` names exactly those two. A human-readable recommendation a
                # reader may commit does not. Left visible, an uncommitted map obeys the
                # engine's ordinary clean-tree rule, which the reader clears by committing or
                # ignoring it. Hidden, activation would proceed against a tree carrying an
                # uncommitted artifact and the same file would behave differently tracked
                # than untracked, for no gain the engine can name.
                continue
            if path in pointers:
                # The one name in this root that EARNS suppression in the default plane: a
                # pointer is per-checkout machine-local state -- it names the operator's own
                # plane path -- exactly like `receipts/` was, and `.gitignore` names it for the
                # same reason. Left visible it would be a permanent untracked record that fails
                # `_require_clean` on every apply after the first, so the engine would break its
                # own repository; and unlike `repo.toml`, nothing riding along in it could change
                # what activation does, because the engine reads it only as a probe destination.
                filtered.add(path)
                continue
            if not repo_local:
                # INVARIANT, not a guard, and deliberately untested: in the default plane the
                # only `.agentic-sdlc/` records `_validate_private_state` admits at all --
                # `repo.toml`, `rightsize/`, and the pointer family -- have already `continue`d
                # above, and every other suppressible name lives outside the worktree. There is
                # therefore no input that distinguishes this line from its absence, so deleting
                # it leaves the suite green. It stays as the explicit statement that plane mode
                # suppresses nothing further, and as the fail-safe if the repository root's
                # whitelist is widened again.
                continue
            if path == ".agentic-sdlc" or path.startswith(".agentic-sdlc/"):
                filtered.add(path)
            elif re.fullmatch(r"\.agentic-sdlc\.noop\.[0-9a-f]{32}\.json", path):
                filtered.add(path)
        # An intent anchor is only a setup-time predecessor of operation.json;
        # it has no durable terminal layout and therefore stays visible to Git.
    return filtered


def capture_git_observation(target: Path) -> dict[str, Any]:
    git_dir = target / ".git"
    if not git_dir.is_dir() or git_dir.is_symlink():
        raise ActivationError("unsupported", "target lacks ordinary .git directory")
    root_identity = dir_identity(target)
    git_identity = dir_identity(git_dir)
    index = git_dir / "index"
    index_raw, index_identity = read_stable_file(index, "Git index")
    toplevel = _git(target, "rev-parse", "--show-toplevel").decode().strip()
    reported_git = _git(target, "rev-parse", "--absolute-git-dir").decode().strip()
    if toplevel != str(target) or reported_git != str(git_dir):
        raise ActivationError("unsupported", "target is not the primary Git worktree")
    head = _git(target, "rev-parse", "HEAD^{commit}").decode().strip()
    tree = _git(target, "rev-parse", "HEAD^{tree}").decode().strip()
    raw = _git(target, "status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none", "--no-renames")
    verify_raw, verify_identity = read_stable_file(index, "Git index")
    if index_raw != verify_raw or index_identity != verify_identity:
        raise ActivationError("refused", "Git index changed during observation")
    filtered = validate_internal_status_records(target, raw)
    normalized = normalize_porcelain_v2_z(raw, filtered_internal=filtered)
    return {
        "toplevel": str(target), "git_dir": str(git_dir), "git_dir_identity": git_identity,
        "head": head, "tree": tree, "index": index_identity,
        "porcelain_v2_z_base64": base64.b64encode(normalized).decode(), "porcelain_sha256": hashlib.sha256(normalized).hexdigest(), "filtered_internal": sorted(filtered),
    }


def _require_clean(observation: dict[str, Any], selected_path: str | None = None) -> None:
    records = [item for item in base64.b64decode(observation["porcelain_v2_z_base64"]).split(b"\0") if item]
    if selected_path is not None:
        selected = selected_path.encode("utf-8")
        records = [item for item in records if not (item[:1] in {b"1", b"?"} and item.rsplit(b" ", 1)[-1] == selected)]
    if records:
        raise ActivationError("refused", "Git worktree is not clean")


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    return _load_generator().validate_manifest(manifest)


def _validate_file_identity(value: Any) -> dict[str, Any]:
    value = _exact(value, {"dev", "ino", "mode", "nlink", "size", "mtime_ns", "ctime_ns", "sha256"}, "file identity")
    for key in {"dev", "ino", "mode", "nlink", "size", "mtime_ns", "ctime_ns"}:
        _integer(value[key], key)
    _hash(value["sha256"])
    return value


def _validate_dir_identity(value: Any, label: str = "directory identity") -> dict[str, Any]:
    value = _exact(value, {"dev", "ino", "mode", "mount_id"}, label)
    for key in value:
        _integer(value[key], key)
    if value["mode"] < 0 or value["mode"] > 0o7777:
        raise ActivationError("refused", f"invalid {label} mode", 2)
    return value


def _validate_prestate(value: Any) -> dict[str, Any]:
    value = _exact(value, {"kind", "identity"}, "prestate")
    if value["kind"] == "absent" and value["identity"] is None:
        return value
    if value["kind"] == "regular" and value["identity"] is not None:
        _validate_file_identity(value["identity"])
        return value
    raise ActivationError("refused", "invalid prestate", 2)


def _validate_desired(value: Any) -> dict[str, Any]:
    value = _exact(value, {"mode", "size", "sha256"}, "desired")
    if value["mode"] != 0o644 or _integer(value["size"], "desired size") < 0:
        raise ActivationError("refused", "invalid desired output", 2)
    _hash(value["sha256"])
    return value


def _validate_parents(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ActivationError("refused", "invalid parent identities", 2)
    for item in value:
        item = _exact(item, {"name", "identity"}, "parent identity")
        if item["name"] != ".":
            _relative(item["name"])
        _validate_dir_identity(item["identity"])
    return value


def _validate_target(value: Any) -> dict[str, Any]:
    value = _exact(value, {"path", "parent", "root"}, "target")
    if not isinstance(value["path"], str) or not Path(value["path"]).is_absolute() or unicodedata.normalize("NFC", value["path"]) != value["path"]:
        raise ActivationError("refused", "invalid target path", 2)
    _validate_dir_identity(value["parent"], "target parent")
    _validate_dir_identity(value["root"], "target root")
    return value


def _validate_payload(value: Any) -> dict[str, Any]:
    value = _exact(value, {"path", "identity"}, "payload identity")
    if not isinstance(value["path"], str) or not Path(value["path"]).is_absolute():
        raise ActivationError("refused", "invalid payload path", 2)
    _validate_file_identity(value["identity"])
    return value


def _validate_git(value: Any) -> dict[str, Any]:
    value = _exact(value, {"toplevel", "git_dir", "git_dir_identity", "head", "tree", "index", "porcelain_v2_z_base64", "porcelain_sha256", "filtered_internal"}, "Git observation")
    if not isinstance(value["toplevel"], str) or not isinstance(value["git_dir"], str):
        raise ActivationError("refused", "invalid Git paths", 2)
    _validate_dir_identity(value["git_dir_identity"], "Git directory")
    for key in ("head", "tree"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", value[key]):
            raise ActivationError("refused", f"invalid Git {key}", 2)
    _validate_file_identity(value["index"])
    if not isinstance(value["porcelain_v2_z_base64"], str) or not isinstance(value["filtered_internal"], list):
        raise ActivationError("refused", "invalid Git status", 2)
    try:
        raw = base64.b64decode(value["porcelain_v2_z_base64"], validate=True)
    except ValueError as exc:
        raise ActivationError("refused", "invalid Git status encoding", 2) from exc
    if hashlib.sha256(raw).hexdigest() != _hash(value["porcelain_sha256"]):
        raise ActivationError("refused", "invalid Git status digest", 2)
    return value


def _validate_operation(operation: dict[str, Any]) -> dict[str, Any]:
    operation = _exact(operation, {"schema", "operation_id", "kind", "target", "plan_digest", "manifest_sha256", "tool", "grant", "git_prestate", "entry"}, "operation")
    if operation["schema"] != OPERATION_SCHEMA or operation["kind"] != "apply":
        raise ActivationError("refused", "unsupported operation schema", 2)
    _id(operation["operation_id"]); _hash(operation["plan_digest"], "plan digest"); _hash(operation["manifest_sha256"], "manifest digest")
    _validate_target(operation["target"])
    tools = _exact(operation["tool"], {"executor", "generator"}, "operation tools")
    _validate_payload(tools["executor"]); _validate_payload(tools["generator"])
    grant = _exact(operation["grant"], {"grant_id", "document_digest"}, "operation grant")
    _id(grant["grant_id"]); _hash(grant["document_digest"])
    _validate_git(operation["git_prestate"])
    entry = _exact(operation["entry"], {"path", "action", "parents", "prestate", "desired", "stage_path", "backup_path", "discard_path"}, "operation entry")
    _relative(entry["path"])
    if entry["action"] not in {"create", "replace"}:
        raise ActivationError("refused", "invalid operation action", 2)
    _validate_parents(entry["parents"]); _validate_prestate(entry["prestate"]); _validate_desired(entry["desired"])
    if (entry["action"] == "create") != (entry["prestate"]["kind"] == "absent"):
        raise ActivationError("refused", "operation action/prestate mismatch", 2)
    if {entry["stage_path"], entry["backup_path"], entry["discard_path"]} != {"stage/0000.payload", "backup/0000.payload", "discard/0000.payload"}:
        raise ActivationError("refused", "invalid private operation paths", 2)
    return operation


def _validate_terminal_evidence(value: Any, operation: dict[str, Any], *, terminal: str) -> dict[str, Any]:
    value = _exact(value, {"backup", "discard"}, "terminal evidence")
    for name in ("backup", "discard"):
        item = value[name]
        if item is None:
            continue
        item = _exact(item, {"path", "identity", "provenance"}, f"terminal {name} evidence")
        expected_path = f"{name}/0000.payload"
        if item["path"] != expected_path:
            raise ActivationError("refused", f"invalid terminal {name} path", 2)
        _validate_file_identity(item["identity"])
        if item["identity"]["nlink"] != 1:
            raise ActivationError("refused", f"terminal {name} is not single-link", 2)
        if name == "backup":
            if item["provenance"] != "replace-prestate" or operation["entry"]["action"] != "replace":
                raise ActivationError("refused", "invalid terminal backup provenance", 2)
            prestate = operation["entry"]["prestate"]
            if prestate["kind"] != "regular" or prestate["identity"] is None or not _same_custody_identity(item["identity"], prestate["identity"]):
                raise ActivationError("refused", "terminal backup does not bind prestate", 2)
        elif item["provenance"] != "discarded-desired" or any(item["identity"][key] != operation["entry"]["desired"][key] for key in ("mode", "size", "sha256")):
            raise ActivationError("refused", "terminal discard does not bind desired payload", 2)
    if terminal == "committed":
        if value["discard"] is not None or (operation["entry"]["action"] == "replace") != (value["backup"] is not None):
            raise ActivationError("refused", "committed terminal evidence is incomplete", 2)
    elif terminal == "rolled-back" and (value["backup"] is not None or value["discard"] is None):
        raise ActivationError("refused", "rolled-back terminal evidence is incomplete", 2)
    return value


def _terminal_evidence(private: PrivateTransaction, operation: dict[str, Any], *, terminal: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {"backup": None, "discard": None}
    for name in ("backup", "discard"):
        try:
            _, identity = _private_payload_at(getattr(private, f"{name}_fd"), "0000.payload", private, f"sealed terminal {name}")
        except ActivationError:
            continue
        evidence[name] = {"path": f"{name}/0000.payload", "identity": identity, "provenance": "replace-prestate" if name == "backup" else "discarded-desired"}
    try:
        return _validate_terminal_evidence(evidence, operation, terminal=terminal)
    except ActivationError as exc:
        raise ActivationError("effect-unknown", f"terminal {terminal} evidence cannot be sealed: {exc.reason}", 4) from exc


def _validate_commit(value: Any, operation: dict[str, Any]) -> dict[str, Any]:
    value = _exact(value, {"schema", "operation_id", "operation_digest", "plan_digest", "entry", "git_poststate", "managed_status_delta", "terminal_evidence", "activation_complete", "readiness_assessed", "approval_authenticated"}, "commit")
    if value["schema"] != COMMIT_SCHEMA or value["operation_id"] != operation["operation_id"] or value["operation_digest"] != digest_record(operation) or value["plan_digest"] != operation["plan_digest"]:
        raise ActivationError("refused", "commit does not bind operation", 2)
    entry = _exact(value["entry"], {"path", "action", "poststate"}, "commit entry")
    if entry["path"] != operation["entry"]["path"] or entry["action"] != operation["entry"]["action"]:
        raise ActivationError("refused", "commit entry mismatch", 2)
    poststate = _validate_file_identity(entry["poststate"])
    desired = operation["entry"]["desired"]
    if any(poststate[key] != desired[key] for key in ("mode", "size", "sha256")):
        raise ActivationError("refused", "commit poststate does not bind desired output", 2)
    _validate_git(value["git_poststate"])
    _validate_terminal_evidence(value["terminal_evidence"], operation, terminal="committed")
    delta = _exact(value["managed_status_delta"], {"removed_records_base64", "added_records_base64"}, "managed Git delta")
    if not all(isinstance(delta[key], list) and all(isinstance(x, str) for x in delta[key]) for key in delta):
        raise ActivationError("refused", "invalid managed Git delta", 2)
    if value["activation_complete"] is not True or value["readiness_assessed"] is not False or value["approval_authenticated"] is not False:
        raise ActivationError("refused", "invalid commit claims", 2)
    return value


def _validate_rollback(value: Any, operation: dict[str, Any], operation_dir: Path) -> dict[str, Any]:
    value = _exact(value, {"schema", "operation_id", "operation_digest", "recovery_grant_digest", "restored_entry", "restored_suffix", "git_poststate", "terminal_evidence", "rollback_complete", "approval_authenticated"}, "rollback")
    if value["schema"] != ROLLBACK_SCHEMA or value["operation_id"] != operation["operation_id"] or value["operation_digest"] != digest_record(operation):
        raise ActivationError("refused", "rollback does not bind operation", 2)
    grant_digest = _hash(value["recovery_grant_digest"], "recovery grant digest")
    entry = _exact(value["restored_entry"], {"path", "prestate"}, "restored rollback entry")
    if entry["path"] != operation["entry"]["path"] or _validate_prestate(entry["prestate"]) != operation["entry"]["prestate"]:
        raise ActivationError("refused", "rollback entry does not restore operation prestate", 2)
    if value["restored_suffix"] != [operation["entry"]["path"]]:
        raise ActivationError("refused", "rollback restored suffix is not exact", 2)
    _validate_git(value["git_poststate"])
    _validate_terminal_evidence(value["terminal_evidence"], operation, terminal="rolled-back")
    if value["rollback_complete"] is not True or value["approval_authenticated"] is not False:
        raise ActivationError("refused", "invalid rollback claims", 2)
    matched = False
    for grant_path in (operation_dir / "grants").glob("*.json"):
        grant, _ = load_canonical_json(grant_path, "consumed grant")
        if grant.get("operation") == "apply":
            validate_grant(grant, operation="apply", enforce_expiry=False)
            continue
        validate_grant(grant, operation="recover", enforce_expiry=False)
        if digest_record(grant) == grant_digest:
            if grant["operation_id"] != operation["operation_id"] or grant["operation_digest"] != digest_record(operation) or grant["decision"] != "rollback":
                raise ActivationError("refused", "rollback recovery grant does not bind operation", 2)
            matched = True
    if not matched:
        raise ActivationError("refused", "rollback recovery grant is absent from ledger", 2)
    return value


def _validate_receipt(value: Any, operation: dict[str, Any], commit: dict[str, Any]) -> dict[str, Any]:
    value = _exact(value, {"schema", "operation_id", "operation_digest", "commit_digest", "plan_digest", "target", "entry", "custody", "terminal_evidence", "activation_complete", "readiness_assessed", "approval_authenticated"}, "receipt")
    if value["schema"] != RECEIPT_SCHEMA or value["operation_id"] != operation["operation_id"] or value["operation_digest"] != digest_record(operation) or value["commit_digest"] != digest_record(commit) or value["plan_digest"] != operation["plan_digest"]:
        raise ActivationError("refused", "receipt does not bind commit", 2)
    _validate_target(value["target"])
    if value["target"] != operation["target"]:
        raise ActivationError("refused", "receipt target mismatch", 2)
    entry = _exact(value["entry"], {"path", "action", "poststate"}, "receipt entry")
    if entry != commit["entry"]:
        raise ActivationError("refused", "receipt entry mismatch", 2)
    custody = _exact(value["custody"], {"operation_dir", "operation_record"}, "receipt custody")
    _validate_dir_identity(custody["operation_dir"], "receipt operation directory custody")
    _validate_custody_identity(custody["operation_record"], "receipt operation record custody")
    if _validate_terminal_evidence(value["terminal_evidence"], operation, terminal="committed") != commit["terminal_evidence"]:
        raise ActivationError("refused", "receipt terminal evidence mismatch", 2)
    if value["activation_complete"] is not True or value["readiness_assessed"] is not False or value["approval_authenticated"] is not False:
        raise ActivationError("refused", "invalid receipt claims", 2)
    return value


def _validate_progress(value: Any, operation: dict[str, Any]) -> dict[str, Any]:
    keys = {"schema", "operation_id", "operation_digest", "sequence", "phase", "direction", "publication_state", "rollback_state", "receipt_state", "cleanup_state", "grant_count", "effect", "effect_unknown", "reasons", "staged_identity", "staged_custody", "backup_identity", "backup_custody", "terminal_evidence"}
    value = _exact(value, keys, "progress")
    if value["schema"] != PROGRESS_SCHEMA or value["operation_id"] != operation["operation_id"] or value["operation_digest"] != digest_record(operation):
        raise ActivationError("refused", "progress does not bind operation", 2)
    if _integer(value["sequence"], "progress sequence") < 0 or value["grant_count"] != 1 or value["reasons"] != []:
        raise ActivationError("refused", "invalid progress", 2)
    if (value["staged_identity"] is None) != (value["staged_custody"] is None):
        raise ActivationError("refused", "incomplete staged custody", 2)
    if value["staged_identity"] is not None:
        _validate_file_identity(value["staged_identity"])
        _validate_custody_identity(value["staged_custody"], "staged custody")
        if custody_identity(value["staged_identity"]) != value["staged_custody"]:
            raise ActivationError("refused", "staged custody does not bind readback identity", 2)
    if (value["backup_identity"] is None) != (value["backup_custody"] is None):
        raise ActivationError("refused", "incomplete backup custody", 2)
    if value["backup_identity"] is not None:
        _validate_file_identity(value["backup_identity"])
        _validate_custody_identity(value["backup_custody"], "backup custody")
        if custody_identity(value["backup_identity"]) != value["backup_custody"]:
            raise ActivationError("refused", "backup custody does not bind readback identity", 2)
    fields = (value["direction"], value["publication_state"], value["rollback_state"], value["receipt_state"], value["cleanup_state"], value["effect"], value["effect_unknown"])
    phase = value["phase"]
    apply_private = ("apply", "not-started", "not-started", "absent", "not-started", "private_state_only", False)
    if phase == "setup":
        if fields != apply_private or value["staged_identity"] is not None or value["backup_identity"] is not None or value["terminal_evidence"] is not None:
            raise ActivationError("refused", "incoherent setup progress", 2)
    elif phase == "staged":
        if fields != apply_private or value["staged_identity"] is None or value["backup_identity"] is not None or value["terminal_evidence"] is not None:
            raise ActivationError("refused", "incoherent staged progress", 2)
    elif phase == "published":
        if fields != ("apply", "verified", "not-started", "absent", "not-started", "product_partial", False) or value["staged_identity"] is None or value["terminal_evidence"] is not None:
            raise ActivationError("refused", "incoherent published progress", 2)
        if value["backup_identity"] is not None and operation["entry"]["action"] != "replace":
            raise ActivationError("refused", "create published progress retains backup custody", 2)
    elif phase == "committed":
        if fields != ("apply", "verified", "not-started", "published", "complete", "committed", False) or value["staged_identity"] is None:
            raise ActivationError("refused", "incoherent committed progress", 2)
        if (operation["entry"]["action"] == "replace") != (value["backup_identity"] is not None):
            raise ActivationError("refused", "committed progress backup does not match operation", 2)
        _validate_terminal_evidence(value["terminal_evidence"], operation, terminal="committed")
    elif phase == "rolled-back":
        if fields not in {
            ("rollback", "not-started", "verified", "absent", "complete", "rolled_back", False),
            ("rollback", "verified", "verified", "absent", "complete", "rolled_back", False),
        } or value["staged_identity"] is None:
            raise ActivationError("refused", "incoherent rolled-back progress", 2)
        if value["backup_identity"] is not None:
            raise ActivationError("refused", "rolled-back progress retains backup custody", 2)
        _validate_terminal_evidence(value["terminal_evidence"], operation, terminal="rolled-back")
    else:
        raise ActivationError("refused", "invalid progress phase", 2)
    return value


def _validate_progress_history(entries: list[tuple[str, dict[str, Any]]], progress: dict[str, Any], operation: dict[str, Any]) -> None:
    if [name for name, _ in entries] != [f"{sequence:020d}.json" for sequence in range(progress["sequence"])]:
        raise ActivationError("refused", "progress history is not contiguous", 2)
    for sequence, (_, historic) in enumerate(entries):
        _validate_progress(historic, operation)
        if historic["sequence"] != sequence or historic["phase"] in {"committed", "rolled-back"}:
            raise ActivationError("refused", "invalid progress history witness", 2)
    if progress["sequence"] == 0:
        if progress["phase"] != "setup":
            raise ActivationError("refused", "progress lacks setup history", 2)
        return
    previous = entries[-1][1]
    if progress["phase"] == "committed":
        if previous["phase"] != "published":
            raise ActivationError("refused", "committed progress lacks published predecessor", 2)
    elif progress["phase"] == "rolled-back":
        if previous["phase"] not in {"staged", "published"} or progress["publication_state"] != previous["publication_state"]:
            raise ActivationError("refused", "rolled-back progress lacks coherent predecessor", 2)
    elif progress["phase"] == "staged" and previous["phase"] != "setup":
        raise ActivationError("refused", "staged progress lacks setup predecessor", 2)
    elif progress["phase"] == "published" and previous["phase"] not in {"staged", "published"}:
        raise ActivationError("refused", "published progress lacks publication predecessor", 2)


def _validate_progress_history_at(private: PrivateTransaction, progress: dict[str, Any], operation: dict[str, Any]) -> None:
    entries: list[tuple[str, dict[str, Any]]] = []
    for name in sorted(os.listdir(private.progress_history_fd)):
        historical, _ = _load_canonical_json_at(private.progress_history_fd, name, "progress history")
        entries.append((name, historical))
    try:
        _validate_progress_history(entries, progress, operation)
    except ActivationError as exc:
        raise ActivationError("effect-unknown", f"invalid pinned progress history: {exc.reason}", 4) from exc


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    keys = {"schema", "target", "tool", "manifest_sha256", "selected_path", "read_inputs", "git", "entries", "verified_outputs"}
    plan = _exact(plan, keys, "plan")
    if plan["schema"] != PLAN_SCHEMA:
        raise ActivationError("refused", "unsupported plan schema", 2)
    _validate_target(plan["target"])
    _hash(plan["manifest_sha256"])
    _relative(plan["selected_path"])
    tool = _exact(plan["tool"], {"executor", "generator"}, "plan tools")
    _validate_payload(tool["executor"]); _validate_payload(tool["generator"])
    _validate_git(plan["git"])
    if not isinstance(plan["read_inputs"], list) or len(plan["read_inputs"]) != 1:
        raise ActivationError("refused", "invalid plan read inputs", 2)
    input_item = _exact(plan["read_inputs"][0], {"path", "purpose", "prestate", "parents"}, "plan read input")
    if input_item["path"] != plan["selected_path"] or input_item["purpose"] != "target_prestate":
        raise ActivationError("refused", "invalid plan read input", 2)
    _validate_prestate(input_item["prestate"]); _validate_parents(input_item["parents"])
    if not isinstance(plan["entries"], list) or not isinstance(plan["verified_outputs"], list):
        raise ActivationError("refused", "invalid plan entries", 2)
    if len(plan["entries"]) == 1 and not plan["verified_outputs"]:
        entry = _exact(plan["entries"][0], {"path", "action", "parents", "prestate", "desired"}, "plan entry")
        if entry["path"] != plan["selected_path"] or entry["action"] not in {"create", "replace"}:
            raise ActivationError("refused", "invalid plan entry", 2)
        _validate_parents(entry["parents"]); _validate_prestate(entry["prestate"]); _validate_desired(entry["desired"])
        if (entry["action"] == "create") != (entry["prestate"]["kind"] == "absent"):
            raise ActivationError("refused", "plan action/prestate mismatch", 2)
    elif not plan["entries"] and len(plan["verified_outputs"]) == 1:
        verified = _exact(plan["verified_outputs"][0], {"path", "identity", "desired"}, "verified output")
        if verified["path"] != plan["selected_path"]:
            raise ActivationError("refused", "invalid verified output", 2)
        _validate_file_identity(verified["identity"]); _validate_desired(verified["desired"])
    else:
        raise ActivationError("refused", "plan must select exactly one effect or one no-op", 2)
    return plan


def validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return _validate_plan(plan)


def _parse_time(value: Any) -> datetime:
    if not isinstance(value, str) or not _TIME.fullmatch(value):
        raise ActivationError("refused", "invalid grant time", 2)
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def validate_grant(grant: dict[str, Any], *, operation: str, enforce_expiry: bool = True) -> dict[str, Any]:
    keys = {"schema", "grant_id", "operation", "target", "plan_digest", "operation_id", "operation_digest", "decision", "issued_at", "expires_at"}
    grant = _exact(grant, keys, "grant")
    if grant["schema"] != GRANT_SCHEMA or grant["operation"] != operation:
        raise ActivationError("refused", "grant does not bind this operation", 2)
    _id(grant["grant_id"])
    target = _exact(grant["target"], {"path", "root_dev", "root_ino"}, "grant target")
    if not isinstance(target["path"], str):
        raise ActivationError("refused", "invalid grant target", 2)
    _integer(target["root_dev"], "root_dev"); _integer(target["root_ino"], "root_ino")
    issued, expires = _parse_time(grant["issued_at"]), _parse_time(grant["expires_at"])
    if not issued < expires or (expires - issued).total_seconds() > 900 or (enforce_expiry and datetime.now(UTC) > expires):
        raise ActivationError("refused", "expired procedural grant")
    if operation == "apply":
        _hash(grant["plan_digest"], "plan digest")
        if any(grant[key] is not None for key in ("operation_id", "operation_digest", "decision")):
            raise ActivationError("refused", "invalid apply grant binding", 2)
    else:
        if grant["plan_digest"] is not None or grant["decision"] not in {"finish", "rollback"}:
            raise ActivationError("refused", "invalid recovery grant binding", 2)
        _id(grant["operation_id"]); _hash(grant["operation_digest"], "operation digest")
    return grant


def _safe_mkdir(path: Path) -> None:
    parent = path.parent
    parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.mkdir(path.name, 0o700, dir_fd=parent_fd)
        _admit(f"created directory {path}")
        child_fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            os.fchmod(child_fd, 0o700)
        finally:
            os.close(child_fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _open_parent_dirfd(target: Path, relative: str) -> tuple[int, str]:
    pieces = _relative(relative).split("/")
    root_fd = open_root_chain(target)
    try:
        current = os.dup(root_fd)
    finally:
        os.close(root_fd)
    try:
        for component in pieces[:-1]:
            child = open_component_dir(current, component)
            os.close(current)
            current = child
        return current, pieces[-1]
    except BaseException:
        os.close(current)
        raise


def _write_new_at(parent_fd: int, name: str, record: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Create one canonical private metadata record and bind its exact successor."""
    data = canonical_bytes(record)
    # A failure at the `open` itself admits nothing: an EEXIST or ENOENT here created no file,
    # so it stays the pre-effect refusal it is. Everything after the open is post-effect.
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
    token = _admit(f"created private metadata {name}")
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise ActivationError("effect-unknown", f"cannot write private metadata {name}", 4)
            offset += written
        os.fchmod(fd, 0o600)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent_fd)
    raw, identity = _read_stable_at(parent_fd, name, f"new metadata {name}")
    if raw != data or identity["mode"] != 0o600 or identity["sha256"] != hashlib.sha256(data).hexdigest():
        raise ActivationError("effect-unknown", f"new private metadata {name} lost custody", 4)
    _revise(token, f"wrote private metadata {name}")
    return data, identity


def _metadata_successor_read_at(private: PrivateTransaction, parent_fd: int, name: str, *, data: bytes, identity: dict[str, Any], label: str, before_rename: bool) -> dict[str, Any]:
    """Read one metadata successor through its pinned dirfd and bind its inode."""
    raw, observed = _private_payload_at(parent_fd, name, private, label)
    if (
        observed["mode"] != 0o600
        or raw != data
        or observed["sha256"] != hashlib.sha256(data).hexdigest()
        or (observed != identity if before_rename else not _same_custody_identity(observed, identity))
    ):
        phase = "before" if before_rename else "after"
        raise ActivationError("effect-unknown", f"metadata successor {name} changed {phase} rename", 4)
    return observed


def _publish_metadata_successor_at(private: PrivateTransaction, source_directory: str, source: str, destination_directory: str, destination: str, *, data: bytes, identity: dict[str, Any], label: str, flags: int) -> dict[str, Any]:
    """Publish a checked private *.next record without accepting substitution."""
    source_fd = getattr(private, f"{source_directory}_fd")
    destination_fd = getattr(private, f"{destination_directory}_fd")
    private.assert_intact()
    # A pre-rename mismatch deliberately leaves the substituted source in place
    # as evidence; no mutating recovery action can safely classify it.
    _metadata_successor_read_at(private, source_fd, source, data=data, identity=identity, label=f"{label} before rename", before_rename=True)
    _renameat2_at(source_fd, source, destination_fd, destination, flags)
    private.untrack_file(source_directory, source)
    # rename changes ctime, so post-publication custody binds the moved inode and
    # exact bytes rather than the predecessor's transient ctime.
    observed = _metadata_successor_read_at(private, destination_fd, destination, data=data, identity=identity, label=f"{label} after rename", before_rename=False)
    private.files[(destination_directory, destination)] = observed
    return observed


def write_new_metadata(path: Path, record: dict[str, Any], *, base: Path | None = None, relative: str | None = None) -> None:
    """Create one canonical record, optionally through a no-follow chain under `base`."""
    if base is None or relative is None:
        data = canonical_bytes(record)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
        token = _admit(f"created {path}")
        try:
            os.write(fd, data); os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(path, 0o600); _fsync_dir(path.parent)
        _revise(token, f"wrote {path}")
        return
    parent_fd, name = _open_parent_dirfd(base, relative)
    try:
        _write_new_at(parent_fd, name, record)
    finally:
        os.close(parent_fd)


def _replace_metadata(path: Path, record: dict[str, Any]) -> None:
    temp = path.with_name(path.name + ".next")
    if temp.exists():
        raise ActivationError("effect-unknown", "unexpected metadata temp", 4)
    write_new_metadata(temp, record)
    os.replace(temp, path)
    _admit(f"replaced {path}")
    _fsync_dir(path.parent)


def write_progress(operation_dir: Path, progress: dict[str, Any], target: Path | None = None) -> None:
    private = _ACTIVE_PRIVATE
    if private is not None and target is not None and private.operation_id == operation_dir.name:
        private.assert_intact()
        previous, predecessor_identity = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
        operation, _ = _load_canonical_json_at(private.operation_fd, "operation.json", "operation")
        _validate_operation(operation)
        _validate_progress(previous, operation)
        _validate_progress_history_at(private, previous, operation)
        progress = dict(progress, sequence=previous["sequence"] + 1)
        _validate_progress(progress, operation)
        try:
            os.stat("progress.json.next", dir_fd=private.operation_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ActivationError("effect-unknown", "unexpected pinned progress temp", 4)
        data, successor_identity = _write_new_at(private.operation_fd, "progress.json.next", progress)
        private.files[("operation", "progress.json.next")] = successor_identity
        # Bind both sides just before the exchange. A substituted current record
        # is never overwritten: the exchange is reversible and its exact moved
        # witness is checked before any history transition.
        _metadata_successor_read_at(private, private.operation_fd, "progress.json.next", data=data, identity=successor_identity, label="progress successor", before_rename=True)
        predecessor_data = canonical_bytes(previous)
        current_data, current_identity = _read_stable_at(private.operation_fd, "progress.json", "progress predecessor before exchange")
        if current_data != predecessor_data or current_identity != predecessor_identity:
            raise ActivationError("effect-unknown", "progress predecessor changed before exchange", 4)
        _renameat2_at(private.operation_fd, "progress.json.next", private.operation_fd, "progress.json", 2)
        private.untrack_file("operation", "progress.json")
        private.untrack_file("operation", "progress.json.next")
        current_data, current_identity = _read_stable_at(private.operation_fd, "progress.json", "progress successor after exchange")
        moved_data, moved_identity = _read_stable_at(private.operation_fd, "progress.json.next", "progress predecessor after exchange")
        successor_ok = current_data == data and _same_custody_identity(current_identity, successor_identity)
        predecessor_ok = moved_data == predecessor_data and _same_custody_identity(moved_identity, predecessor_identity)
        if not successor_ok or not predecessor_ok:
            _renameat2_at(private.operation_fd, "progress.json.next", private.operation_fd, "progress.json", 2)
            restored_current_data, restored_current_identity = _read_stable_at(private.operation_fd, "progress.json", "restored progress predecessor")
            restored_temp_data, restored_temp_identity = _read_stable_at(private.operation_fd, "progress.json.next", "restored progress successor")
            if (
                restored_current_data != moved_data
                or not _same_custody_identity(restored_current_identity, moved_identity)
                or restored_temp_data != current_data
                or not _same_custody_identity(restored_temp_identity, current_identity)
            ):
                raise ActivationError("effect-unknown", "progress exchange mismatch could not be restored", 4)
            private.track_file("operation", "progress.json")
            private.track_file("operation", "progress.json.next")
            private.assert_intact()
            raise ActivationError("effect-unknown", "progress exchange preserved substituted destination witness", 4)
        history_name = f"{previous['sequence']:020d}.json"
        try:
            os.stat(history_name, dir_fd=private.progress_history_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ActivationError("effect-unknown", "progress history destination already exists", 4)
        # Never discard the exchanged predecessor. A replacement at the temp
        # slot is preserved there and prevents a successful terminal result.
        moved_data, moved_identity = _read_stable_at(private.operation_fd, "progress.json.next", "progress predecessor before history")
        if moved_data != predecessor_data or not _same_custody_identity(moved_identity, predecessor_identity):
            private.track_file("operation", "progress.json")
            private.track_file("operation", "progress.json.next")
            private.assert_intact()
            raise ActivationError("effect-unknown", "progress predecessor changed before history retention", 4)
        _renameat2_at(private.operation_fd, "progress.json.next", private.progress_history_fd, history_name, 1)
        private.track_file("operation", "progress.json")
        private.track_file("progress_history", history_name)
        retained_data, retained_identity = _read_stable_at(private.progress_history_fd, history_name, "retained progress predecessor")
        if retained_data != predecessor_data or not _same_custody_identity(retained_identity, predecessor_identity):
            raise ActivationError("effect-unknown", "progress history retention lost predecessor custody", 4)
        observed, observed_identity = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
        if observed != progress or not _same_custody_identity(observed_identity, successor_identity):
            raise ActivationError("effect-unknown", "progress successor final readback failed", 4)
        _validate_progress_history_at(private, observed, operation)
        private.assert_intact()
        return
    path = operation_dir / "progress.json"
    if path.exists():
        previous, _ = load_canonical_json(path, "progress")
        progress = dict(progress, sequence=previous["sequence"] + 1)
        _replace_metadata(path, progress)
    elif target is None:
        write_new_metadata(path, progress)
    else:
        write_new_metadata(path, progress, base=_resolve_plane(target).root, relative=f"transactions/{operation_dir.name}/progress.json")


def _progress(operation: dict[str, Any], *, phase: str, effect: str, direction: str = "apply", reasons: list[str] | None = None, staged_identity: dict[str, Any] | None = None, backup_identity: dict[str, Any] | None = None, terminal_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    terminal = phase in {"committed", "rolled-back"}
    private = _ACTIVE_PRIVATE
    if private is not None and private.operation_id == operation["operation_id"]:
        if staged_identity is None:
            staged_identity = private.staged_custody
        if backup_identity is None:
            backup_identity = private.backup_custody
    publication_state = "verified" if phase in {"published", "committed"} else "not-started"
    if phase == "published" and backup_identity is None:
        progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress") if private is not None else (None, None)
        if progress is not None and progress["backup_identity"] is not None:
            backup_identity = progress["backup_identity"]
    if phase == "rolled-back":
        backup_identity = None
        if private is not None:
            previous, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
            publication_state = previous["publication_state"]
    return {"schema": PROGRESS_SCHEMA, "operation_id": operation["operation_id"], "operation_digest": digest_record(operation), "sequence": 0, "phase": phase, "direction": direction, "publication_state": publication_state, "rollback_state": "verified" if phase == "rolled-back" else "not-started", "receipt_state": "published" if phase == "committed" else "absent", "cleanup_state": "complete" if terminal else "not-started", "grant_count": 1, "effect": effect, "effect_unknown": False, "reasons": [], "staged_identity": staged_identity, "staged_custody": custody_identity(staged_identity) if staged_identity is not None else None, "backup_identity": backup_identity, "backup_custody": custody_identity(backup_identity) if backup_identity is not None else None, "terminal_evidence": terminal_evidence}


def classify_progress_witness(operation_dir: Path, operation: dict[str, Any]) -> tuple[str, list[str]]:
    _validate_operation(operation)
    target = Path(operation["target"]["path"])
    binding = _bind_operation_target(target, operation)
    plane = _resolve_plane(target)
    try:
        _validate_private_state(target, binding)
        progress_path = operation_dir / "progress.json"
        if not progress_path.exists() or progress_path.is_symlink():
            return "effect_unknown", ["transaction lacks canonical progress witness"]
        progress, _ = load_canonical_json(progress_path, "progress")
        _validate_progress(progress, operation)
        entries: list[tuple[str, dict[str, Any]]] = []
        history = operation_dir / "progress-history"
        if not history.is_dir() or history.is_symlink():
            return "effect_unknown", ["transaction lacks progress history witness"]
        for item in sorted(history.iterdir(), key=lambda candidate: candidate.name):
            historical, _ = load_canonical_json(item, "progress history")
            entries.append((item.name, historical))
        _validate_progress_history(entries, progress, operation)
    except ActivationError as exc:
        return "effect_unknown", [exc.reason]
    allowed = {"operation.json", "progress.json", "progress.json.next", "progress-history", "commit.json", "rollback.json", "receipt.json.next", "grants", "stage", "backup", "discard"}
    names = {entry.name for entry in operation_dir.iterdir()}
    if not names <= allowed:
        return "effect_unknown", ["unexpected transaction witness"]
    for folder in ("stage", "backup", "discard"):
        permitted = {"0000.payload", "0000.payload.next" if folder == "stage" else ""}
        if any(item.name not in permitted or not item.is_file() or item.is_symlink() for item in (operation_dir / folder).iterdir()):
            return "effect_unknown", ["unexpected private transaction witness"]
    if (operation_dir / "progress.json.next").exists():
        return "effect_unknown", ["progress temp requires manual witness classification"]
    if (operation_dir / "rollback.json").exists():
        try:
            rollback, _ = load_canonical_json(operation_dir / "rollback.json", "rollback")
            _validate_rollback(rollback, operation, operation_dir)
            verify_restored_suffix(operation, target)
            post = capture_git_observation(target)
            if not _same_git_projection(post, rollback["git_poststate"]) or not _same_git_projection(post, operation["git_prestate"]):
                return "effect_unknown", ["rollback Git witness no longer binds target"]
            if (operation_dir / "commit.json").exists() or (plane.receipts / f"{operation['operation_id']}.json").exists():
                return "effect_unknown", ["rollback conflicts with commit or receipt"]
            if progress["phase"] != "rolled-back":
                return "effect_unknown", ["rollback lacks coherent terminal progress"]
            _validate_terminal_evidence_snapshot(target, operation, progress["terminal_evidence"], terminal="rolled-back")
            _validate_terminal_evidence_snapshot(target, operation, rollback["terminal_evidence"], terminal="rolled-back")
            if progress["terminal_evidence"] != rollback["terminal_evidence"]:
                return "effect_unknown", ["rollback progress terminal evidence disagrees with rollback record"]
            return "rolled-back", []
        except ActivationError as exc:
            return "effect_unknown", [exc.reason]
    commit_path = operation_dir / "commit.json"
    if commit_path.exists():
        try:
            commit, _ = load_canonical_json(commit_path, "commit")
            _validate_commit(commit, operation)
            receipt_next = operation_dir / "receipt.json.next"
            final_receipt = plane.receipts / f"{operation['operation_id']}.json"
            if receipt_next.exists():
                next_record, _ = load_canonical_json(receipt_next, "staged receipt")
                _validate_receipt(next_record, operation, commit)
            if final_receipt.exists():
                final_record, _ = load_canonical_json(final_receipt, "receipt")
                _validate_receipt(final_record, operation, commit)
                if not receipt_next.exists() and progress["phase"] == "committed":
                    _validate_terminal_evidence_snapshot(target, operation, commit["terminal_evidence"], terminal="committed")
                    _validate_terminal_evidence_snapshot(target, operation, final_record["terminal_evidence"], terminal="committed")
                    if progress["terminal_evidence"] != commit["terminal_evidence"]:
                        return "effect_unknown", ["committed progress terminal evidence disagrees with commit"]
                    return "committed", []
        except ActivationError as exc:
            return "effect_unknown", [exc.reason]
        return "recovery-required", ["commit is durable; only finish is legal"]
    return "recovery-required", []


@contextlib.contextmanager
def activation_lock(target: Path) -> Iterator[None]:
    fd = open_root_chain(target)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _failpoint(name: str) -> None:
    if os.environ.get("AGENTIC_SDLC_FAILPOINT") == name:
        os._exit(97)


def _result(command: str, status: str, code: int, target: Path, *, effect: str, plan_digest: str | None = None, operation_id: str | None = None, operation_digest: str | None = None, receipt_digest: str | None = None, legal: list[str] | None = None, reasons: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    """Render one command result. `effect` is REQUIRED, and that is the structural half of the fix.

    It used to default to `"none"`, which is how every refusal in this module -- 312 raise sites
    reachable from `apply_command` and the recover verbs -- claimed no effect from one `except`
    clause that had never looked at what happened. There is no default to fall back on now: a
    success states the effect it completed, and a refusal gets its effect from `_report_failure`,
    which reads the ledger.
    """
    result = {"schema": RESULT_SCHEMA, "command": command, "status": status, "effect": effect, "exit_code": code, "target": str(target), "plan_digest": plan_digest, "operation_id": operation_id, "operation_digest": operation_digest, "receipt_digest": receipt_digest, "legal_recovery": legal or [], "reasons": reasons or [], "admitted_effects": list(_EFFECTS.admitted), "approval_authenticated": False}
    result.update(extra)
    return result


def _normalize_failure(command: str, exc: ActivationError) -> tuple[str, int]:
    """Per-command status and code for a refusal, BEFORE the ledger has its say.

    This is the only surviving per-command policy, and it is deliberately not about effects: it
    is about what each surface can honestly say when it cannot complete a READ. `recover inspect`
    is the one surface that widens `foreign-state` and a schema failure to `effect-unknown`,
    because a private tree it cannot parse is exactly the state that must not be reported as
    "nothing to recover". `_report_failure` may only escalate what this returns.
    """
    if command == "recover inspect":
        if exc.status == "inactive":
            return "inactive", 0
        if exc.status == "foreign-state" or exc.code == 2:
            return "effect-unknown", 4
    return exc.status, exc.code


def _report_failure(command: str, exc: ActivationError, target: Path) -> tuple[dict[str, Any], int]:
    """THE single escalation choke point: every refusal's effect is DERIVED here, by every command.

    Two inputs, and the rule between them is escalate-only:

    1. THE LEDGER IS THE FLOOR. Once this invocation has admitted any effect, no refusal may
       exit as a clean pre-effect refusal (3), a pre-effect internal failure (1), or a grammar
       or schema verdict (2), because on disk the result is partial or unknown. Decision 9's 4
       is the only honest answer, and `admitted_effects` names what already happened.
    2. A RAISE SITE MAY ONLY ESCALATE. `exc.code == 4` reports an unknown effect this invocation
       merely OBSERVED -- a prior crash's journal, a plane nothing can resolve -- which the
       ledger cannot know about because this process did not cause it. So a site can still widen
       an empty ledger to `effect_unknown`; what it can no longer do is claim `none` over
       something that happened. That direction is the whole defect, and it is now unreachable:
       the effect is not a parameter of any raise.

    This also unifies the residual the plane work recorded. At exit 4 `status` and
    `recover inspect` reported `effect: effect_unknown` while `plan` and `apply` reported
    `effect: none` from their shared handler; both statements were true, but the disagreement
    existed only because two handlers each decided the effect for themselves. One derivation
    point cannot disagree with itself, so the difference is gone rather than documented.
    """
    status, code = _normalize_failure(command, exc)
    effect = EFFECT_NONE
    if _EFFECTS.any():
        status, code, effect = "effect-unknown", 4, EFFECT_UNKNOWN
    elif code == 4:
        effect = EFFECT_UNKNOWN
    # `recover inspect` alone reports an inactive target with no reason, because "there is
    # nothing to recover" is its ordinary answer rather than a refusal. Every other command
    # keeps the reason it was given; suppressing it by STATUS instead of by command would have
    # silently dropped `recover finish`'s explanation of an inactive target.
    reasons = [] if (command == "recover inspect" and status == "inactive") else [exc.reason]
    return _result(command, status, code, Path(target), effect=effect, reasons=reasons), code


def _plan_data(target: Path, manifest_path: Path, selected_path: str) -> dict[str, Any]:
    manifest, _ = load_canonical_json(manifest_path, "manifest")
    _validate_manifest(manifest)
    selected_path = _relative(selected_path)
    root_fd = open_root_chain(target)
    try:
        root_identity = _dir_identity_fd(root_fd)
    finally:
        os.close(root_fd)
    root_binding = RootBinding(target, root_identity)
    _validate_private_state(target, root_binding)
    observation = capture_git_observation(target)
    _require_clean(observation, selected_path)
    rendered, prestate, _ = render_and_bind_selected_output(target, manifest, selected_path)
    if rendered["action"] != "no-op":
        _committed_path_owner(target, root_binding, selected_path)
    desired = {"mode": rendered["mode"], "size": len(rendered["content"]), "sha256": hashlib.sha256(rendered["content"]).hexdigest()}
    tools = {"executor": _tool_identity(Path(__file__)), "generator": _tool_identity(Path(__file__).with_name("instruction-generator.py"))}
    item = {"path": selected_path, "purpose": "target_prestate", "prestate": prestate, "parents": [{"name": ".", "identity": dir_identity(target)}]}
    target_data = {"path": str(target), "parent": dir_identity(target.parent), "root": root_identity}
    if rendered["action"] == "no-op":
        verified = [{"path": selected_path, "identity": prestate["identity"], "desired": desired}]
        entries: list[dict[str, Any]] = []
    else:
        entries = [{"path": selected_path, "action": rendered["action"], "parents": [{"name": ".", "identity": dir_identity(target)}], "prestate": prestate, "desired": desired}]
        verified = []
    return {"schema": PLAN_SCHEMA, "target": target_data, "tool": tools, "manifest_sha256": hashlib.sha256(canonical_bytes(manifest)).hexdigest(), "selected_path": selected_path, "read_inputs": [item], "git": observation, "entries": entries, "verified_outputs": verified}


def plan_command(target: Path, manifest_path: Path, selected_path: str) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            target = Path(target)
            plan = _plan_data(target, manifest_path, selected_path)
            return _result("plan", "planned", 0, target, effect=EFFECT_NONE, plan_digest=digest_record(plan), plan=plan), 0
        except ActivationError as exc:
            return _report_failure("plan", exc, Path(target))


def _private_identity_matches(path: Path, root: RootBinding) -> bool:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        return False
    try:
        value = os.fstat(fd)
        return value.st_dev == root.identity["dev"] and _mount_id_fd(fd) == root.identity["mount_id"]
    finally:
        os.close(fd)


def _assert_private_dir(path: Path, root: RootBinding, label: str) -> None:
    try:
        value = path.lstat()
    except OSError as exc:
        raise ActivationError("foreign-state", f"missing private {label}") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode) or stat.S_IMODE(value.st_mode) != 0o700 or value.st_dev != root.identity["dev"] or not _private_identity_matches(path, root):
        raise ActivationError("foreign-state", f"unsafe private {label}")


def _has_extended_acl(path: Path) -> bool:
    """Whether the node carries an extended ACL this module refuses to reason about.

    Needed because the traditional group bits double as the POSIX.1e *mask* when an
    extended ACL is present, so a mode-only rule cannot tell "group-write from the
    caller's umask" apart from "write granted to a named user". Detect the ACL directly
    instead of inferring it from the mode.

    `posix_acl_default` counts too: an inherited default ACL is only harmless today
    because `_mkdir_at` unconditionally chmods created subdirectories to 0700, which zeroes
    the inherited mask (measured: an inherited `user:other:rwx` shows `#effective:---`).
    That is an accident of the subtree modes, not an assertion, so refuse it here rather
    than depend on it. `nfs4_acl` counts because NFSv4/richacl does not maintain the
    POSIX mask-in-group-bits coupling at all, so on such a mount neither the mode rule nor
    the POSIX probe can see a foreign write grant; POSIX.1e is the only ACL surface this
    module reasons about, and anything else is refused rather than assumed absent.

    Only "this filesystem cannot carry an ACL" reports False. Every other failure refuses,
    because for this predicate a swallowed EACCES or ELOOP would fail OPEN.
    """
    try:
        attributes = os.listxattr(path, follow_symlinks=False)
    except OSError as exc:
        if exc.errno in (errno.ENOTSUP, errno.EOPNOTSUPP):
            return False
        raise ActivationError("foreign-state", "cannot read ACL state") from exc
    return any(name in attributes for name in ("system.posix_acl_access", "system.posix_acl_default", "system.nfs4_acl"))


def _assert_cloneable_private_node(path: Path, root: RootBinding, label: str, *, directory: bool) -> None:
    """Admit a node that Git materialized, refusing world-writable and foreign-owned ones.

    NOT a claim that no other user can write. Group-write is permitted -- see below -- so
    on a checkout whose group is shared (`chgrp -R devs`, a setgid project directory) a
    group member can modify the manifest in place. The engine still refuses to act on that
    edit, because the manifest is visible to the Git projection and an uncommitted change
    fails `_require_clean`; but the node itself is admitted, and `repository-contract.py`
    records the same limitation for readers. A `st_gid == os.getegid()` constraint would
    close it and would also refuse legitimate group-owned checkouts, so the exposure is
    recorded rather than silently traded away.

    ADR-0022 tracks `.agentic-sdlc/repo.toml`, and Git records no mode at all: a fresh
    clone creates both the state root and the manifest at the caller's umask. Measured
    shapes are directory 0755 / file 0644 at umask 022 and 0775 / 0664 at umask 002, so
    any rule that refuses group-write refuses ordinary clones on RHEL-family hosts and
    common CI images. Privacy stays enforced where the private data actually lives:
    `receipts/` and `transactions/` keep the strict exact-0700 `_assert_private_dir`.

    What this node must still prove:
      * it is the expected type and not a symlink, so custody cannot be redirected;
      * it is owned by the calling user -- the module carried no ownership check at all
        before, which an exact-0700 rule made moot only by accident, because a
        foreign-owned 0700 node denies us access and fails the identity probe anyway;
      * no other-write, so a world-writable node is refused at any umask;
      * no extended ACL, which is the fail-closed half of allowing group-write. A
        read-only ACL is refused too. That is stricter than strictly necessary and is
        deliberate: an ACL on an activation state root is unusual enough that refusing
        beats reasoning about mask arithmetic per entry.
      * it sits on the bound mount, by both `st_dev` and mount id.
    """
    try:
        value = path.lstat()
    except OSError as exc:
        raise ActivationError("foreign-state", f"missing {label}") from exc
    expected_type = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        stat.S_ISLNK(value.st_mode)
        or not expected_type(value.st_mode)
        or value.st_uid != os.geteuid()
        or stat.S_IMODE(value.st_mode) & 0o002
        or value.st_dev != root.identity["dev"]
        or _has_extended_acl(path)
        or not _private_identity_matches(path, root)
    ):
        raise ActivationError("foreign-state", f"unsafe {label}")
    if not directory and value.st_nlink != 1:
        raise ActivationError("foreign-state", f"unsafe {label}")


def _assert_state_root(path: Path, root: RootBinding) -> None:
    _assert_cloneable_private_node(path, root, "private state root", directory=True)


def _assert_repository_manifest(path: Path, root: RootBinding) -> None:
    _assert_cloneable_private_node(path, root, REPO_MANIFEST_NAME, directory=False)


def _assert_rightsize_artifacts(path: Path, root: RootBinding) -> None:
    """Admit ADR-0015's rendered trio: open NAMES, closed CUSTODY, cloneable modes.

    Cloneable rather than exact-0700 for the same reason `_assert_cloneable_private_node`
    gives the state root and the manifest. The reviewed writer creates this directory with a
    plain umask-respecting `mkdir` and replaces artifacts through `write_text`, so what
    `/sdlc-rightsize` itself produces is 0755/0644 at umask 022; and because the trio is a
    human-readable recommendation a reader may commit, a fresh clone re-materializes it at
    the caller's umask with no mode recorded at all. An exact-0700 rule here would refuse
    both the writer's own output and ordinary clones, which is the defect it would look like
    it was fixing. Privacy still lives where private data lives: `receipts/` and
    `transactions/` keep the strict exact-0700 `_assert_private_dir`.

    Names must stay open. `--output` is operator-chosen, the trio derives `<stem>.json`,
    `<stem>.md`, and `<stem>.evidence.json` from it, that stem may itself sit in a
    subdirectory the operator named, the saved run spec is a sibling, and an interrupted
    render strands a `.<name>.<pid>.tmp`. A closed inner whitelist would refuse legitimate
    output, so the whitelist widens by exactly one name at the state root and stops there.

    Only rightsizing STATE lives here. A task pack is an operator-authored input carrying its
    own fixture tree and resolves outside this root, which is what keeps the hand-edited
    corpus -- the part most likely to acquire a stray mode or symlink -- out of this walk.

    Custody does not open. Every node is proven non-symlink, expected-type, caller-owned,
    not other-writable, ACL-free, single-linked when a file, and on the bound mount, one
    level at a time into subdirectories. Symlink refusal is the load-bearing control for an
    open namespace: a symlink is the only way this subtree could redirect custody outward,
    and refusing it is also what keeps the walk loop-free without a visited set.

    Breadth is deliberately unbounded, matching `receipts/`: a cap would invent a refusal the
    engine cannot justify, and the cost is one lstat plus one listxattr per artifact on every
    caller of `_validate_private_state`.

    This subtree is advisory content the engine never reads. It is validated only so that
    admitting the name cannot smuggle a foreign-owned or redirected node into the private
    root -- never as a claim that the map itself carries authority.
    """
    _assert_cloneable_private_node(path, root, RIGHTSIZE_DIR_NAME, directory=True)
    pending = [path]
    while pending:
        for item in sorted(pending.pop().iterdir()):
            try:
                # lstat first so the recursion decision comes from the link itself. A node
                # swapped between this call and the validator's own lstat refuses either
                # way, because both types cannot satisfy one `expected_type`.
                directory = stat.S_ISDIR(item.lstat().st_mode)
            except OSError as exc:
                raise ActivationError("foreign-state", f"missing {RIGHTSIZE_DIR_NAME} artifact") from exc
            _assert_cloneable_private_node(item, root, f"{RIGHTSIZE_DIR_NAME} artifact", directory=directory)
            if directory:
                pending.append(item)


def _assert_private_file(path: Path, root: RootBinding, label: str, *, modes: set[int] = {0o600}) -> None:
    try:
        value = path.lstat()
    except OSError as exc:
        raise ActivationError("foreign-state", f"missing private {label}") from exc
    if stat.S_ISLNK(value.st_mode) or not stat.S_ISREG(value.st_mode) or value.st_nlink != 1 or stat.S_IMODE(value.st_mode) not in modes or value.st_dev != root.identity["dev"] or not _private_identity_matches(path, root):
        raise ActivationError("foreign-state", f"unsafe private {label}")


def _root_anchor_operation(target: Path, root: RootBinding, path: Path, plane: StatePlane) -> None:
    suffix = path.name.removeprefix(plane.anchor_prefix).removesuffix(".json")
    if not path.name.endswith(".json") or not _HEX32.fullmatch(suffix):
        raise ActivationError("foreign-state", "unknown activation anchor")
    _assert_private_file(path, root, "anchor")
    try:
        operation, _ = load_canonical_json(path, "anchor")
        _validate_operation(operation)
        if operation["operation_id"] != suffix:
            raise ActivationError("foreign-state", "anchor filename does not bind operation")
        _bind_operation_target(target, operation)
    except ActivationError as exc:
        if exc.status == "foreign-state":
            raise
        raise ActivationError("foreign-state", "invalid activation anchor") from exc


def _root_noop_audit(target: Path, root: RootBinding, path: Path, plane: StatePlane) -> None:
    suffix = path.name.removeprefix(plane.audit_prefix).removesuffix(".json")
    if not path.name.endswith(".json") or not _HEX32.fullmatch(suffix):
        raise ActivationError("foreign-state", "unknown activation audit")
    _assert_private_file(path, root, "audit")
    try:
        record, _ = load_canonical_json(path, "audit")
        record = _exact(record, {"schema", "operation_id", "kind", "target", "plan_digest", "manifest_sha256", "grant", "verified_outputs", "git_observation", "existing_receipt_digests", "effect", "approval_authenticated"}, "no-op audit")
        if record["schema"] != AUDIT_SCHEMA or record["operation_id"] != suffix or record["kind"] != "no-op" or record["effect"] != "audit_only" or record["approval_authenticated"] is not False:
            raise ActivationError("foreign-state", "invalid no-op audit witness")
        _validate_target(record["target"])
        if record["target"]["path"] != str(target) or record["target"]["root"] != root.identity or record["target"]["parent"] != dir_identity(target.parent):
            raise ActivationError("foreign-state", "audit target does not bind root")
        _hash(record["plan_digest"]); _hash(record["manifest_sha256"])
        grant = _exact(record["grant"], {"grant_id", "document_digest"}, "audit grant")
        _id(grant["grant_id"]); _hash(grant["document_digest"])
        if not isinstance(record["verified_outputs"], list) or not isinstance(record["existing_receipt_digests"], list) or not all(isinstance(item, str) and _HEX64.fullmatch(item) for item in record["existing_receipt_digests"]):
            raise ActivationError("foreign-state", "invalid no-op audit witness")
        _validate_git(record["git_observation"])
        observation = record["git_observation"]
        if observation["toplevel"] != str(target) or observation["git_dir"] != str(target / ".git") or observation["git_dir_identity"] != dir_identity(target / ".git"):
            raise ActivationError("foreign-state", "audit Git witness does not bind root")
    except ActivationError as exc:
        if exc.status == "foreign-state":
            raise
        raise ActivationError("foreign-state", "invalid no-op audit") from exc


def _validate_private_state(target: Path, root: RootBinding, *, admission: bool = True) -> None:
    """Validate this target's private state, and at admission also its plane selection.

    `admission=False` is for the ONE caller that runs after a product is already
    published: `validate_internal_status_records`, reached through
    `capture_git_observation` when `write_commit` captures the poststate.

    A refusal raised there used to surface through `apply_command` as `refused` with
    `effect: none` -- a no-effect claim over published bytes, MEASURED for
    `LEGACY_STATE_REASON` and true of the plane device/ancestor guards at this same site. That
    was a defect in `apply_command`'s handler rather than in this function, and it is CLOSED:
    every refusal now derives its effect at `_report_failure` from the effect ledger, so a
    refusal raised from here reports exit 4 `effect_unknown` and names the publication. See
    `test_a_post_publication_refusal_is_never_reported_as_a_clean_refusal`.

    The unselected-plane probe still does not run here, and the reason is unchanged by that
    fix: it is an admission decision, every admission surface calls this function directly
    before any effect, and nothing this caller observes could change the answer anyway.
    """
    plane = _resolve_plane(target)
    _assert_plane_device(plane, root)
    _validate_repository_state_root(target, root, plane)
    if admission:
        # Before any record of the SELECTED plane is read, let alone written: an unselected
        # plane holding state means this invocation cannot honestly report on this target,
        # and neither does one this checkout's own pointers name after a rename.
        _assert_unselected_planes_empty(target, root, plane)
    _validate_plane_records(target, root, plane)


def _validate_repository_state_root(target: Path, root: RootBinding, plane: StatePlane) -> None:
    """Admit the tracked, public half of `.agentic-sdlc/` plus the plane pointers, nothing else.

    The whitelist is load-bearing: `repo.toml`, `rightsize/`, and the `plane.<digest>.json`
    family are admitted, and any other name is `unknown private state path`. In the default
    plane `receipts/`, `transactions/`, and the two root anchor families are no longer part of
    it, so finding one is a live activation this engine did not write here. It is refused
    BY NAME and left exactly as found -- see `LEGACY_STATE_REASON`.

    The pointer family is the one addition, and it is admitted under stricter custody than
    either public name rather than under a relaxed rule: exact 0600, single-link, engine-written
    (`_assert_plane_pointer`). A name in the family that is not a valid pointer is
    `foreign-state`, so the widening cannot be used to smuggle an arbitrary file in under a
    matching name.
    """
    for candidate in target.iterdir():
        name = candidate.name
        if name == STATE_DIR_NAME:
            continue
        if name.startswith(f"{STATE_DIR_NAME}.intent.") or name.startswith(f"{STATE_DIR_NAME}.noop."):
            if not plane.repo_local:
                raise ActivationError("refused", LEGACY_STATE_REASON, 3)
    state = target / STATE_DIR_NAME
    if not state.exists() and not state.is_symlink():
        return
    _assert_state_root(state, root)
    # ACCEPTED COST, recorded for whoever hits `foreign-state` in a recovery: unlike the
    # other names, `rightsize/` holds operator-VISIBLE rendered artifacts, so a stray
    # `chmod o+w`, a symlink, or a foreign-owned file in there refuses activation AND
    # recovery, at every caller of this function. That is the deliberate price of one
    # namespace with one validator -- fix the offending node's custody rather than
    # special-casing recovery or exempting this subtree. `_assert_rightsize_artifacts` names
    # the offender, and task packs deliberately live outside this root to keep the
    # hand-edited half of rightsizing out of the walk.
    names = {item.name for item in state.iterdir()}
    pointers = sorted(name for name in names if name.startswith(PLANE_POINTER_PREFIX))
    allowed = {REPO_MANIFEST_NAME, RIGHTSIZE_DIR_NAME, *pointers}
    if plane.repo_local:
        allowed |= {"receipts", "transactions"}
    elif names & {"receipts", "transactions"}:
        # Never adopted and never removed. A receipt binds `custody.operation_dir` by
        # dev/ino and `custody.operation_record` by dev/ino, so no copy or move can carry
        # it: migrating would turn a valid committed activation into a permanently
        # `effect-unknown` target. The remedy is the repo-local override, which leaves the
        # state where its own custody already binds, or the operator's own deliberate
        # retirement of it -- an outward effect that needs its own authorization.
        raise ActivationError("refused", LEGACY_STATE_REASON, 3)
    if names - allowed:
        raise ActivationError("foreign-state", "unknown private state path")
    manifest = state / REPO_MANIFEST_NAME
    if manifest.exists() or manifest.is_symlink():
        _assert_repository_manifest(manifest, root)
    rightsize = state / RIGHTSIZE_DIR_NAME
    if rightsize.exists() or rightsize.is_symlink():
        _assert_rightsize_artifacts(rightsize, root)
    for name in pointers:
        _assert_plane_pointer(state / name, root)


def _assert_plane_ancestors(plane: StatePlane, root: RootBinding) -> None:
    """Admit the operator-owned directories the plane key hangs from.

    `<state home>` and `<state home>/ccodex` are shared with every other ccodex consumer
    and `activation/` with every other target, so they are admitted as *cloneable* nodes
    -- caller-owned, not other-writable, ACL-free, not symlinks, on the target's device --
    rather than held to an exact mode this engine has no right to impose on them. The
    check is not decoration: an other-writable ancestor would let another user rename this
    target's whole key directory away and substitute a forged one, which no mode on the
    key directory itself can prevent.
    """
    if plane.repo_local:
        return
    # Every ancestor is checked "if it exists", INCLUDING the state home, so that one call
    # serves both orders. `_validate_plane_records` reaches this only when the plane root
    # already exists, where every ancestor exists too and the condition is therefore not
    # weaker than an unconditional check. `_mkdir_plane_root` calls it BEFORE it creates
    # anything -- where a missing state home is the ordinary first-activation case and must
    # not be a refusal -- and again after, where they all exist. Before that first call
    # existed, the creating path detected a symlinked or other-writable EXISTING ancestor only
    # after it had already made directories under it.
    current = _state_home()
    ancestors = [(current, "state plane home")]
    for name in PLANE_NAMESPACE:
        current = current / name
        ancestors.append((current, f"state plane {name}"))
    for path, label in ancestors:
        if path.exists() or path.is_symlink():
            _assert_cloneable_private_node(path, root, label, directory=True)


def _validate_plane_records(target: Path, root: RootBinding, plane: StatePlane) -> None:
    """Validate the anchors, audits, receipts, and journals of the selected plane.

    Every custody helper is still passed the TARGET binding, even for plane nodes. That is
    exact rather than approximate: `_assert_plane_device` has already required the plane to
    share the target's `st_dev` and `mount_id` -- publication could not be atomic
    otherwise -- so "on the target's device and mount" is the strongest statement available
    and the one the engine actually depends on.
    """
    state = plane.root
    present = state.exists() or state.is_symlink()
    if not plane.repo_local:
        if not present:
            # No plane entry for this key: nothing has been activated here, exactly as an
            # absent `.agentic-sdlc/` meant before. The anchors live inside it, so there is
            # no witness anywhere else to miss.
            return
        _assert_plane_ancestors(plane, root)
        # Only this engine ever creates the key directory, so unlike a Git-materialized
        # root it is held to the exact 0700 rule its own children are held to.
        _assert_private_dir(state, root, "state plane")
        for item in state.iterdir():
            if item.name in {"receipts", "transactions"}:
                continue
            if item.name.startswith(plane.anchor_prefix) or item.name.startswith(plane.audit_prefix):
                continue
            raise ActivationError("foreign-state", "unknown state plane path")
    # Repo-local anchors sit at the target root, so this walk has to precede the
    # `present` return: an interrupted setup can leave one with no state root at all.
    for candidate in plane.anchor_dir.iterdir():
        name = candidate.name
        if name.startswith(plane.anchor_prefix):
            _root_anchor_operation(target, root, candidate, plane)
        elif name.startswith(plane.audit_prefix):
            _root_noop_audit(target, root, candidate, plane)
    if not present:
        return
    for name in ("receipts", "transactions"):
        if (state / name).exists() or (state / name).is_symlink():
            _assert_private_dir(state / name, root, name)
    receipts = state / "receipts"
    receipt_paths: list[Path] = []
    if receipts.exists():
        for item in receipts.iterdir():
            if not item.name.endswith(".json") or not _HEX32.fullmatch(item.name[:-5]):
                raise ActivationError("foreign-state", "unknown receipt")
            _assert_private_file(item, root, "receipt")
            receipt_paths.append(item)
    transactions = state / "transactions"
    operations: dict[str, tuple[Path, dict[str, Any]]] = {}
    if transactions.exists():
        for directory in transactions.iterdir():
            if not _HEX32.fullmatch(directory.name):
                raise ActivationError("foreign-state", "unknown transaction")
            _assert_private_dir(directory, root, "transaction")
            allowed = {"operation.json", "progress.json", "progress.json.next", "progress-history", "commit.json", "rollback.json", "receipt.json.next", "grants", "stage", "backup", "discard"}
            if {item.name for item in directory.iterdir()} - allowed:
                raise ActivationError("foreign-state", "unknown transaction witness")
            for metadata in {"operation.json", "progress.json", "progress.json.next", "commit.json", "rollback.json", "receipt.json.next"}:
                path = directory / metadata
                if path.exists() or path.is_symlink():
                    _assert_private_file(path, root, metadata)
            operation_path = directory / "operation.json"
            if not operation_path.exists():
                raise ActivationError("foreign-state", "transaction lacks operation")
            operation, _ = load_canonical_json(operation_path, "operation")
            _validate_operation(operation)
            if operation["operation_id"] != directory.name:
                raise ActivationError("foreign-state", "transaction directory does not bind operation")
            _bind_operation_target(target, operation)
            operations[operation["operation_id"]] = (directory, operation)
            for child in ("grants", "stage", "backup", "discard", "progress-history"):
                path = directory / child
                if not path.exists() and not path.is_symlink():
                    raise ActivationError("foreign-state", f"missing transaction {child}")
                _assert_private_dir(path, root, child)
            progress_path = directory / "progress.json"
            if not progress_path.exists():
                raise ActivationError("effect-unknown", "transaction lacks progress witness", 4)
            try:
                progress, _ = load_canonical_json(progress_path, "progress")
                _validate_progress(progress, operation)
            except ActivationError as exc:
                raise ActivationError("effect-unknown", f"invalid transaction progress witness: {exc.reason}", 4) from exc
            history_entries: list[tuple[str, dict[str, Any]]] = []
            for item in sorted((directory / "progress-history").iterdir(), key=lambda candidate: candidate.name):
                if not re.fullmatch(r"[0-9]{20}\.json", item.name):
                    raise ActivationError("foreign-state", "unknown progress history witness")
                _assert_private_file(item, root, "progress history")
                historical, _ = load_canonical_json(item, "progress history")
                history_entries.append((item.name, historical))
            _validate_progress_history(history_entries, progress, operation)
            for grant in (directory / "grants").iterdir():
                if not re.fullmatch(r"[0-9]{4}\.json", grant.name):
                    raise ActivationError("foreign-state", "unknown consumed grant")
                _assert_private_file(grant, root, "consumed grant")
                record, _ = load_canonical_json(grant, "consumed grant")
                # A grant already captured in the durable ledger is historical
                # authority evidence. Its original validity ordering and binding
                # remain strict, but normal clock passage cannot strand recovery.
                validate_grant(record, operation="apply" if record.get("operation") == "apply" else "recover", enforce_expiry=False)
            for child in ("stage", "backup", "discard"):
                permitted = {"0000.payload"}
                if child == "stage":
                    permitted.add("0000.payload.next")
                for payload in (directory / child).iterdir():
                    if payload.name not in permitted:
                        raise ActivationError("foreign-state", "unknown private payload")
                    _assert_private_file(payload, root, "private payload", modes={0o600, 0o644, stat.S_IMODE(payload.lstat().st_mode)})
    for receipt_path in receipt_paths:
        operation_id = receipt_path.stem
        if operation_id not in operations:
            raise ActivationError("foreign-state", "receipt has no operation witness")
        directory, operation = operations[operation_id]
        commit_path = directory / "commit.json"
        if not commit_path.exists():
            raise ActivationError("foreign-state", "receipt has no commit witness")
        commit, _ = load_canonical_json(commit_path, "commit")
        _validate_commit(commit, operation)
        record, _ = load_canonical_json(receipt_path, "receipt")
        _validate_receipt(record, operation, commit)


def _bind_operation_target(target: Path, operation: dict[str, Any]) -> RootBinding:
    binding = bind_target(target)
    if operation["target"]["path"] != str(target) or operation["target"]["root"] != binding.identity or operation["target"]["parent"] != dir_identity(target.parent):
        raise ActivationError("effect-unknown", "operation target does not bind locked recovery target", 4)
    return binding


def _operation_dirs(target: Path, root: RootBinding | None = None) -> list[Path]:
    if root is not None:
        _validate_private_state(target, root)
    directory = _resolve_plane(target).transactions
    return sorted((item for item in directory.iterdir() if item.is_dir() and not item.is_symlink()), key=lambda item: item.name) if directory.is_dir() and not directory.is_symlink() else []


def _committed_path_owner(target: Path, root: RootBinding, selected_path: str) -> None:
    """Refuse a second effectful owner for a path with a verified receipt."""
    for directory in _operation_dirs(target, root):
        try:
            operation, _ = load_canonical_json(directory / "operation.json", "operation")
            _validate_operation(operation)
            _bind_operation_target(target, operation)
            state, reasons = classify_progress_witness(directory, operation)
        except ActivationError as exc:
            raise ActivationError("effect-unknown", f"ambiguous transaction witness: {exc.reason}", 4) from exc
        if state == "effect_unknown":
            raise ActivationError("effect-unknown", "; ".join(reasons), 4)
        if state != "committed":
            continue
        committed, receipt = _validate_existing_terminal_operation(target, directory, operation)
        if committed != "committed" or receipt is None:
            raise ActivationError("effect-unknown", "committed receipt lacks a terminal binding", 4)
        if operation["entry"]["path"] == selected_path:
            raise ActivationError("unsupported", "a committed operation already manages the selected path")


def _scan_operation_exclusion(target: Path, root: RootBinding) -> None:
    """Refuse a fresh apply when any transaction is unresolved or unclassifiable."""
    for directory in _operation_dirs(target, root):
        try:
            operation, _ = load_canonical_json(directory / "operation.json", "operation")
            _validate_operation(operation)
            _bind_operation_target(target, operation)
            state, reasons = classify_progress_witness(directory, operation)
        except ActivationError as exc:
            raise ActivationError("effect-unknown", f"ambiguous transaction witness: {exc.reason}", 4) from exc
        if state == "effect_unknown":
            raise ActivationError("effect-unknown", "; ".join(reasons), 4)
        if state == "recovery-required":
            raise ActivationError("recovery-required", "valid recovery-required transaction blocks a new apply without consuming the new grant", 3)
        if state not in {"committed", "rolled-back"}:
            raise ActivationError("effect-unknown", "transaction has no validated terminal classification", 4)


def scan_grant_ledger(target: Path, grant: dict[str, Any]) -> None:
    root = bind_target(target)
    _validate_private_state(target, root)
    target_digest = digest_record(grant)
    plane = _resolve_plane(target)
    for path in plane.anchor_dir.glob(f"{plane.audit_prefix}*.json"):
        try:
            record, _ = load_canonical_json(path, "audit")
        except ActivationError:
            raise ActivationError("foreign-state", "invalid no-op audit")
        reference = record.get("grant", {})
        if reference.get("grant_id") == grant["grant_id"] or reference.get("document_digest") == target_digest:
            raise ActivationError("refused", "procedural grant already consumed")
    for operation_dir in _operation_dirs(target, root):
        grants = operation_dir / "grants"
        if not grants.is_dir():
            raise ActivationError("foreign-state", "malformed transaction state")
        for path in grants.glob("*.json"):
            record, _ = load_canonical_json(path, "consumed grant")
            if record.get("grant_id") == grant["grant_id"] or digest_record(record) == target_digest:
                raise ActivationError("refused", "procedural grant already consumed")


def _same_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left == right


def _revalidate_plan(plan: dict[str, Any], manifest_path: Path) -> tuple[dict[str, Any], bytes | None]:
    _validate_plan(plan)
    target = Path(plan["target"]["path"])
    binding = bind_target(target)
    if plan["target"]["root"] != binding.identity or plan["target"]["parent"] != dir_identity(target.parent):
        raise ActivationError("stale", "target identity changed")
    manifest, _ = load_canonical_json(manifest_path, "manifest")
    if hashlib.sha256(canonical_bytes(manifest)).hexdigest() != plan["manifest_sha256"]:
        raise ActivationError("stale", "manifest changed")
    if {"executor": _tool_identity(Path(__file__)), "generator": _tool_identity(Path(__file__).with_name("instruction-generator.py"))} != plan["tool"]:
        raise ActivationError("stale", "canonical tool identity changed")
    updated = _plan_data(target, manifest_path, plan["selected_path"])
    # Exact on every field except the Git observation's `filtered_internal`, which is DERIVED
    # from what the engine itself owns rather than an input the plan pins. It grows by one entry
    # the first time a plane pointer is written, so an exact comparison made a plan captured
    # before that write permanently `stale` with "plan inputs changed" when nothing about the
    # tree had changed. `_same_git_projection` is the same tolerance the rollback baseline check
    # already uses, and it hides nothing: a suppressed path that appears or disappears from
    # Git's own output changes the normalized porcelain bytes, and those stay exact here.
    if {key: value for key, value in updated.items() if key != "git"} != {key: value for key, value in plan.items() if key != "git"} or not _same_git_projection(updated["git"], plan["git"]):
        raise ActivationError("stale", "plan inputs changed")
    rendered, _, old = render_and_bind_selected_output(target, manifest, plan["selected_path"])
    return rendered, old


def _new_operation(plan: dict[str, Any], grant: dict[str, Any]) -> dict[str, Any]:
    operation_id = uuid.uuid4().hex
    entry = plan["entries"][0]
    return {"schema": OPERATION_SCHEMA, "operation_id": operation_id, "kind": "apply", "target": plan["target"], "plan_digest": digest_record(plan), "manifest_sha256": plan["manifest_sha256"], "tool": plan["tool"], "grant": {"grant_id": grant["grant_id"], "document_digest": digest_record(grant)}, "git_prestate": plan["git"], "entry": {**entry, "stage_path": "stage/0000.payload", "backup_path": "backup/0000.payload", "discard_path": "discard/0000.payload"}}


def _record_plane_pointer(target: Path, plane: StatePlane, root: RootBinding) -> None:
    """Bind this checkout to the plane about to hold its state, before that plane holds any.

    THE DEFECT THIS CLOSES, which the previous fix in this file introduced: the plane key is
    derived from the absolute target path, and the PLANE side was the only place that path was
    recorded. Renaming a checkout -- or moving `XDG_STATE_HOME` to a directory the environment
    no longer names, or moving `HOME` -- therefore resolved a fresh, empty plane while the old
    one still held an unresolved journal for a product that is still published in the tree. The
    engine reported `inactive` with `effect: none` at exit 0 and admitted a second effectful
    apply. Before the plane moved out of the tree the same rename was exit 4 `effect-unknown`,
    because the journal travelled with the checkout and failed `_bind_operation_target`; turning
    that honest "I cannot tell" into a confident "nothing here" was strictly worse than the
    selection hole it replaced. A rename is an ordinary operation, which is what made this
    blocking rather than residual.

    Ordering: written BEFORE the plane root, so no plane RECORD can exist without a pointer
    naming the plane that holds it. A crash in the window between the two leaves a pointer to a
    plane root that does not exist, or exists and is empty, which probes clean and correctly
    permits the next apply -- nothing was published and no journal was written.

    Create-only, and named after the digest of the plane root, so a relocation ADDS a pointer
    instead of rewriting one. That is what keeps it crash-consistent with no `*.next` window,
    and it means every plane this checkout has ever written to stays nameable rather than only
    the most recent one. Nothing removes a pointer: a receipt is durable, so the name of the
    plane holding it is too, and a pointer whose plane no longer holds anything is simply a
    candidate that probes empty.

    Not written for the repo-local override. That plane IS the target's own subdirectory, so it
    travels with a rename and cannot be orphaned by one: `_validate_repository_state_root`
    refuses it by `LEGACY_STATE_REASON` under any other selection, and after a rename
    `_bind_operation_target` refuses the moved journal itself at exit 4. Because no pointer ever
    records a repo-local root, `_plane_candidates` needs no inference about a recorded root's
    layout.

    NOT a claim that state cannot be lost. A pointer is machine-local, so `git clean -x`
    removes it exactly as it removed `.agentic-sdlc/receipts/` before the plane moved out of the
    tree; destroying both halves of the evidence has always defeated detection, and this makes
    that the only remaining way to.
    """
    if plane.repo_local:
        return
    state = target / STATE_DIR_NAME
    if not state.exists() and not state.is_symlink():
        _safe_mkdir(state)
    # The state root may be a Git-materialized directory, so it earns the cloneable rule and
    # not the private one -- exactly as `_validate_repository_state_root` admits it.
    _assert_state_root(state, root)
    name = _plane_pointer_name(plane.root)
    pointer = state / name
    if pointer.exists() or pointer.is_symlink():
        if _assert_plane_pointer(pointer, root) != plane.root:
            # Unreachable while the filename is the digest of the recorded root, and kept
            # because this is the one place that equality is load-bearing for a WRITE.
            raise ActivationError("foreign-state", "plane pointer does not bind its plane")
        return
    write_new_metadata(pointer, {"schema": PLANE_POINTER_SCHEMA, "plane": str(plane.root)}, base=target, relative=f"{STATE_DIR_NAME}/{name}")


def _mkdir_plane_root(plane: StatePlane, root: RootBinding, target_fd: int) -> int:
    """Create the plane root, then reopen it through the one strict chain.

    Missing operator-owned ancestors are created at 0700 but an existing one is never
    chmodded: `~/.local/state` and `~/.local/state/ccodex` are shared with every other
    ccodex consumer, and rewriting their modes would be a side effect on state this engine
    does not own. `_mkdir_at`'s unconditional 0700 is therefore reserved for the key
    directory and its children, which only this engine creates.

    Containment of those ancestors is asserted BEFORE the first `mkdir` as well as after it.
    The second call alone was not a pre-effect check on this path: `_validate_plane_records`
    runs `_assert_plane_ancestors` only when the plane root already exists, so on the creating
    path -- the only path that writes to an unvalidated ancestor -- an other-writable or
    symlinked existing ancestor was detected after this function had already created
    directories beneath it.
    """
    if plane.repo_local:
        return _mkdir_at(target_fd, STATE_DIR_NAME)
    _assert_plane_ancestors(plane, root)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        for part in plane.root.parts[1:-1]:
            try:
                child = open_component_dir(fd, part)
            except FileNotFoundError:
                os.mkdir(part, 0o700, dir_fd=fd)
                _admit(f"created state plane ancestor {part}")
                os.fsync(fd)
                child = open_component_dir(fd, part)
            os.close(fd)
            fd = child
        os.close(_mkdir_at(fd, plane.root.name))
    finally:
        os.close(fd)
    _assert_plane_ancestors(plane, root)
    state_fd = open_root_chain(plane.root)
    try:
        identity = _dir_identity_fd(state_fd)
        # DEFENSIVE, and deliberately untested: `_mkdir_at` has just set 0700 and
        # `_assert_plane_device` plus `open_root_chain` have already fixed the device and
        # mount, so the only way to reach this raise is a same-UID racer inside this
        # window -- the one adversary this module states it does not defend against. It is
        # kept because turning that race into a refusal is better than admitting an effect,
        # not because any input reaches it: deleting it leaves the suite green.
        if identity["mode"] != 0o700 or identity["dev"] != root.identity["dev"] or identity["mount_id"] != root.identity["mount_id"]:
            raise ActivationError("foreign-state", "unsafe private state plane")
        return state_fd
    except BaseException:
        os.close(state_fd)
        raise


def _make_layout(target: Path, operation: dict[str, Any]) -> Path:
    root_binding = _bind_operation_target(target, operation)
    _validate_private_state(target, root_binding)
    plane = _resolve_plane(target)
    _assert_plane_device(plane, root_binding)
    target_fd = open_root_chain(target)
    anchor = plane.anchor_name(operation["operation_id"])
    try:
        # Read-only, and it has to run before the POINTER as well as before the plane root.
        # A pointer is durable machine-local state that changes what every later invocation
        # reports about this target -- with one, a moved checkout is exit 4 `effect-unknown`
        # instead of `inactive` -- so writing one and then discovering the plane's own home is
        # other-writable turns an honest pre-effect refusal into an admitted effect. It is
        # cheaper to refuse before the write than to classify it afterwards. `_mkdir_plane_root`
        # still asserts the same containment on both sides of its own `mkdir`.
        _assert_plane_ancestors(plane, root_binding)
        # Before the plane root, so no record in it can be orphaned by a later rename.
        _record_plane_pointer(target, plane, root_binding)
        state_fd = _mkdir_plane_root(plane, root_binding, target_fd)
        try:
            # The anchor is the first witness of this operation, and it is written into the
            # directory it will be renamed INTO. The rename is `RENAME_NOREPLACE`, which is
            # confined to one filesystem, so an anchor outside the plane could not become
            # `operation.json` at all once the plane stops being a repository subdirectory.
            anchor_fd = target_fd if plane.repo_local else state_fd
            _write_new_at(anchor_fd, anchor, operation)
            _failpoint("setup")
            receipts_fd = _mkdir_at(state_fd, "receipts")
            transactions_fd = _mkdir_at(state_fd, "transactions")
            try:
                operation_fd = _mkdir_new_at(transactions_fd, operation["operation_id"])
                try:
                    grants_fd = _mkdir_new_at(operation_fd, "grants")
                    stage_fd = _mkdir_new_at(operation_fd, "stage")
                    backup_fd = _mkdir_new_at(operation_fd, "backup")
                    progress_history_fd = _mkdir_new_at(operation_fd, "progress-history")
                    discard_fd = _mkdir_new_at(operation_fd, "discard")
                    try:
                        _renameat2_at(anchor_fd, anchor, operation_fd, "operation.json", 1)
                        _write_new_at(operation_fd, "progress.json", _progress(operation, phase="setup", effect="private_state_only"))
                        return plane.operation_dir(operation["operation_id"])
                    finally:
                        os.close(progress_history_fd); os.close(discard_fd); os.close(backup_fd); os.close(stage_fd); os.close(grants_fd)
                finally:
                    os.close(operation_fd)
            finally:
                os.close(transactions_fd)
                os.close(receipts_fd)
        finally:
            os.close(state_fd)
    finally:
        os.close(target_fd)


def _consume_grant(operation_dir: Path, grant: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    names = os.listdir(private.grants_fd)
    if any(not re.fullmatch(r"[0-9]{4}\.json", name) for name in names):
        raise ActivationError("effect-unknown", "unexpected pinned grant witness", 4)
    number = len(names) + 1
    _write_new_at(private.grants_fd, f"{number:04d}.json", grant)
    private.track_file("grants", f"{number:04d}.json")
    private.assert_intact()


def stage_payload(operation_dir: Path, operation: dict[str, Any], content: bytes, target: Path) -> Path:
    private = _require_private(target, operation_dir)
    fd = os.open("0000.payload.next", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600, dir_fd=private.stage_fd)
    token = _admit("created the staged payload")
    try:
        os.write(fd, content)
        os.fchmod(fd, 0o644)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(private.stage_fd)
    _renameat2_at(private.stage_fd, "0000.payload.next", private.stage_fd, "0000.payload", 1)
    raw, identity = _read_stable_at(private.stage_fd, "0000.payload", "staged payload")
    if raw != content or identity["mode"] != 0o644:
        raise ActivationError("effect-unknown", "staged payload readback failed", 4)
    _revise(token, "wrote the staged payload")
    private.staged_custody = identity
    private.track_file("stage", "0000.payload")
    # Durable custody comes before the observable stage boundary: recovery may
    # offer a decision only for a payload whose exact object identity is bound.
    write_progress(operation_dir, _progress(operation, phase="staged", effect="private_state_only", staged_identity=identity), target)
    private.assert_intact()
    _failpoint("stage")
    return operation_dir / "stage" / "0000.payload"


def _renameat2(source: Path, destination: Path, flags: int) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    call = getattr(library, "renameat2", None)
    if call is None:
        raise ActivationError("unsupported", "Linux renameat2 is unavailable")
    result = call(-100, os.fsencode(source), -100, os.fsencode(destination), flags)
    if result:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise ActivationError("stale", "publication compare-and-swap failed")
        raise ActivationError("effect-unknown", f"renameat2 failed: {os.strerror(error)}", 4)
    _admit(f"renamed {source} onto {destination} (flags {flags})")


def _private_payload(path: Path, target: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read a private payload with the root's ordinary no-follow mount binding."""
    try:
        raw, identity = read_stable_file(path, label)
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            mount_id = _mount_id_fd(fd)
        finally:
            os.close(fd)
        root = bind_target(target).identity
        if identity["dev"] != root["dev"] or mount_id != root["mount_id"]:
            raise ActivationError("effect-unknown", f"{label} crossed the target mount", 4)
        return raw, identity
    except ActivationError as exc:
        if exc.code == 4:
            raise
        raise ActivationError("effect-unknown", f"unsafe {label} after exchange", 4) from exc


def _matches_prestate_payload(path: Path, target: Path, prestate: dict[str, Any], label: str) -> bool:
    if prestate["kind"] != "regular" or prestate["identity"] is None:
        return False
    raw, identity = _private_payload(path, target, label)
    expected = prestate["identity"]
    # rename changes ctime on Linux; the remaining identity fields are stable
    # through an exchange and bind the exact original object and its bytes.
    return all(identity[key] == expected[key] for key in ("dev", "ino", "mode", "nlink", "size", "sha256")) and len(raw) == expected["size"]


def _matches_desired_payload(path: Path, target: Path, desired: dict[str, Any], label: str) -> bool:
    raw, identity = _private_payload(path, target, label)
    return identity["mode"] == desired["mode"] and identity["size"] == desired["size"] and identity["sha256"] == desired["sha256"] and len(raw) == desired["size"]


def _private_payload_at(parent_fd: int, name: str, private: PrivateTransaction, label: str) -> tuple[bytes, dict[str, Any]]:
    """Read a pinned private file once, including its mount and stable identity."""
    try:
        fd = open_regular_at(parent_fd, name)
    except OSError as exc:
        raise ActivationError("effect-unknown", f"cannot open pinned {label}", 4) from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise ActivationError("effect-unknown", f"unsafe pinned {label}", 4)
        mount_id = _mount_id_fd(fd)
        raw = bytearray()
        while part := os.read(fd, 1 << 20):
            raw.extend(part)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ActivationError("effect-unknown", f"unstable pinned {label}", 4)
    identity = file_identity_from_stat(after, bytes(raw))
    root = private.identities["target"]
    if identity["dev"] != root["dev"] or mount_id != root["mount_id"]:
        raise ActivationError("effect-unknown", f"{label} crossed the target mount", 4)
    return bytes(raw), identity


def _matches_prestate_payload_at(parent_fd: int, name: str, private: PrivateTransaction, prestate: dict[str, Any], label: str) -> bool:
    if prestate["kind"] != "regular" or prestate["identity"] is None:
        return False
    raw, identity = _private_payload_at(parent_fd, name, private, label)
    expected = prestate["identity"]
    return all(identity[key] == expected[key] for key in ("dev", "ino", "mode", "nlink", "size", "sha256")) and len(raw) == expected["size"]


def _matches_desired_payload_at(parent_fd: int, name: str, private: PrivateTransaction, desired: dict[str, Any], label: str) -> bool:
    raw, identity = _private_payload_at(parent_fd, name, private, label)
    return identity["mode"] == desired["mode"] and identity["size"] == desired["size"] and identity["sha256"] == desired["sha256"] and len(raw) == desired["size"]


def _same_exchanged_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    # renameat2 exchange updates ctime, so compare the stable ordinary identity
    # fields plus the complete content digest after every exchange.
    return all(left[key] == right[key] for key in ("dev", "ino", "mode", "nlink", "size", "sha256"))


def _restore_exchange_mismatch_at(private: PrivateTransaction, private_fd: int, live_parent_fd: int, live_name: str, private_name: str, before: bytes, moved_identity: dict[str, Any], label: str) -> None:
    directory = "stage" if private_fd == private.stage_fd else "backup"
    _renameat2_at(private_fd, private_name, live_parent_fd, live_name, 2)
    private.untrack_file(directory, private_name)
    private.track_file(directory, private_name)
    raw, identity = _read_stable_at(live_parent_fd, live_name, f"restored {label}")
    if raw != before or not _same_custody_identity(identity, moved_identity):
        raise ActivationError("effect-unknown", f"{label} mismatch could not be restored live", 4)
    private.assert_intact()


def _restore_exchange_mismatch(live: Path, private: Path, target: Path, before: bytes, moved_identity: dict[str, Any], label: str) -> None:
    """Put a detected exchanged-in external object back live without deleting it."""
    _renameat2(private, live, 2)
    _fsync_dir(private.parent)
    _fsync_dir(live.parent)
    raw, identity = _private_payload(live, target, f"restored {label}")
    if raw != before or not _same_exchanged_identity(identity, moved_identity):
        raise ActivationError("effect-unknown", f"{label} mismatch could not be restored live", 4)


def _verify_staged_custody_before_publish(private: PrivateTransaction, operation: dict[str, Any]) -> None:
    raw, identity = _private_payload_at(private.stage_fd, "0000.payload", private, "staged publication payload")
    desired = operation["entry"]["desired"]
    if (
        len(raw) != desired["size"]
        or identity["mode"] != desired["mode"]
        or identity["sha256"] != desired["sha256"]
        or not _same_custody_identity(identity, _staged_identity(private, operation))
    ):
        raise ActivationError("effect-unknown", "staged payload no longer matches durable custody before publication", 4)


def _restore_create_publication_substitution(
    private: PrivateTransaction,
    live_parent_fd: int,
    live_name: str,
    stage_identity: dict[str, Any],
) -> None:
    _renameat2_at(live_parent_fd, live_name, private.stage_fd, "0000.payload", 1)
    private.track_file("stage", "0000.payload")
    try:
        os.stat(live_name, dir_fd=live_parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        pass
    else:
        raise ActivationError("effect-unknown", "substituted create product could not be removed from live namespace", 4)
    _, restored = _private_payload_at(private.stage_fd, "0000.payload", private, "restored substituted staged payload")
    if not _same_custody_identity(restored, stage_identity):
        raise ActivationError("effect-unknown", "substituted create product could not be restored to stage", 4)
    private.assert_intact()


def publish_create(operation_dir: Path, operation: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    live_parent_fd, live_name = _open_live_parent_at(private.target_fd, operation["entry"]["path"])
    try:
        try:
            os.stat(live_name, dir_fd=live_parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ActivationError("stale", "create target appeared")
        _verify_staged_custody_before_publish(private, operation)
        staged_identity = _staged_identity(private, operation)
        _renameat2_at(private.stage_fd, "0000.payload", live_parent_fd, live_name, 1)
        private.untrack_file("stage", "0000.payload")
        _, live_identity = _private_payload_at(live_parent_fd, live_name, private, "published create payload")
        if not _same_custody_identity(live_identity, staged_identity):
            _restore_create_publication_substitution(private, live_parent_fd, live_name, live_identity)
            raise ActivationError("effect-unknown", "create publication lost staged payload custody; substituted object restored to stage", 4)
    finally:
        os.close(live_parent_fd)
    private.assert_intact()


def publish_replace(operation_dir: Path, operation: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    live_parent_fd, live_name = _open_live_parent_at(private.target_fd, operation["entry"]["path"])
    try:
        prestate, old = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
        if prestate != operation["entry"]["prestate"] or old is None:
            raise ActivationError("stale", "replace target changed")
        external_identity = prestate["identity"]
        assert external_identity is not None
        _verify_staged_custody_before_publish(private, operation)
        staged_identity = _staged_identity(private, operation)
        _renameat2_at(private.stage_fd, "0000.payload", live_parent_fd, live_name, 2)
        private.track_file("stage", "0000.payload")
        live_raw, live_identity = _private_payload_at(live_parent_fd, live_name, private, "published replace payload")
        previous_raw, previous_identity = _private_payload_at(private.stage_fd, "0000.payload", private, "exchanged replace prestate")
        if (
            not _same_custody_identity(live_identity, staged_identity)
            or not _same_custody_identity(previous_identity, external_identity)
            or previous_raw != old
        ):
            _renameat2_at(private.stage_fd, "0000.payload", live_parent_fd, live_name, 2)
            private.track_file("stage", "0000.payload")
            restored_raw, restored_live = _private_payload_at(live_parent_fd, live_name, private, "restored replace publication live")
            restored_stage_raw, restored_stage = _private_payload_at(private.stage_fd, "0000.payload", private, "restored replace publication stage")
            if (
                restored_raw != old
                or not _same_custody_identity(restored_live, external_identity)
                or restored_stage_raw != live_raw
                or not _same_custody_identity(restored_stage, live_identity)
            ):
                raise ActivationError("effect-unknown", "replace publication substitution could not be restored", 4)
            private.assert_intact()
            raise ActivationError("effect-unknown", "replace publication lost custody; pre-exchange namespace was restored", 4)
        _renameat2_at(private.stage_fd, "0000.payload", private.backup_fd, "0000.payload", 1)
        private.untrack_file("stage", "0000.payload")
        _record_backup_custody(operation_dir, private, operation)
    finally:
        os.close(live_parent_fd)
    private.assert_intact()


def _staged_identity(private: PrivateTransaction, operation: dict[str, Any]) -> dict[str, Any]:
    if private.staged_custody is None:
        progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
        _validate_progress(progress, operation)
        _validate_progress_history_at(private, progress, operation)
        private.staged_custody = progress["staged_identity"]
    if private.staged_custody is None:
        raise ActivationError("effect-unknown", "durable staged custody is absent", 4)
    return private.staged_custody


def _require_staged_custody(identity: dict[str, Any], private: PrivateTransaction, operation: dict[str, Any], label: str) -> None:
    if not _same_custody_identity(identity, _staged_identity(private, operation)):
        raise ActivationError("effect-unknown", f"{label} does not retain staged payload custody", 4)


def _staged_witness_matches(private: PrivateTransaction, operation: dict[str, Any], label: str) -> bool:
    try:
        raw, identity = _private_payload_at(private.stage_fd, "0000.payload", private, label)
    except ActivationError:
        return False
    desired = operation["entry"]["desired"]
    return (
        len(raw) == desired["size"]
        and identity["mode"] == desired["mode"]
        and identity["sha256"] == desired["sha256"]
        and _same_custody_identity(identity, _staged_identity(private, operation))
    )


def _discard_exact_staged_payload(operation_dir: Path, operation: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    if not _staged_witness_matches(private, operation, "staged rollback payload"):
        raise ActivationError("effect-unknown", "staged payload no longer matches durable custody", 4)
    _renameat2_at(private.stage_fd, "0000.payload", private.discard_fd, "0000.payload", 1)
    private.untrack_file("stage", "0000.payload")
    private.track_file("discard", "0000.payload")
    _, identity = _private_payload_at(private.discard_fd, "0000.payload", private, "sealed staged rollback discard")
    if not _same_custody_identity(identity, _staged_identity(private, operation)):
        raise ActivationError("effect-unknown", "staged rollback discard lost desired custody", 4)
    private.assert_intact()


def readback_product(operation: dict[str, Any], target: Path) -> dict[str, Any]:
    private = _ACTIVE_PRIVATE
    _bind_operation_target(target, operation)
    if private is not None:
        private.assert_intact()
        prestate, raw = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
    else:
        prestate, raw = capture_prestate(target, operation["entry"]["path"])
    desired = operation["entry"]["desired"]
    if prestate["kind"] != "regular" or raw is None or hashlib.sha256(raw).hexdigest() != desired["sha256"] or len(raw) != desired["size"] or prestate["identity"]["mode"] != 0o644:
        raise ActivationError("effect-unknown", "published product readback failed", 4)
    if private is not None:
        _require_staged_custody(prestate["identity"], private, operation, "live product")
    return prestate["identity"]


def _git_records(observation: dict[str, Any]) -> list[bytes]:
    return [item for item in base64.b64decode(observation["porcelain_v2_z_base64"]).split(b"\0") if item]


def _record_path(record: bytes) -> str:
    parsed = parse_porcelain_v2_z(record + b"\0")
    if len(parsed) != 1 or len(parsed[0].paths) != 1:
        raise ActivationError("effect-unknown", "invalid normalized Git record", 4)
    try:
        return parsed[0].paths[0].decode("utf-8", "strict")
    except UnicodeDecodeError as exc:
        raise ActivationError("effect-unknown", "invalid normalized Git path encoding", 4) from exc


def derive_managed_git_delta(pre: dict[str, Any], post: dict[str, Any], selected_path: str) -> dict[str, Any]:
    for key in ("head", "tree", "index"):
        if pre[key] != post[key]:
            raise ActivationError("effect-unknown", "Git identity changed during transaction", 4)
    before = _git_records(pre)
    after = _git_records(post)
    previous_nonmanaged = sorted(record for record in before if _record_path(record) != selected_path)
    current_nonmanaged = sorted(record for record in after if _record_path(record) != selected_path)
    if previous_nonmanaged != current_nonmanaged:
        raise ActivationError("effect-unknown", "unrelated Git worktree state changed after publication", 4)
    removed = sorted(base64.b64encode(record).decode() for record in before if _record_path(record) == selected_path)
    added = sorted(base64.b64encode(record).decode() for record in after if _record_path(record) == selected_path)
    return {"removed_records_base64": removed, "added_records_base64": added}


def write_commit(operation_dir: Path, operation: dict[str, Any], poststate: dict[str, Any], target: Path) -> dict[str, Any]:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    # First terminal binding: no commit witness is published until live is exact.
    if readback_product(operation, target) != poststate:
        raise ActivationError("effect-unknown", "live product changed before commit evidence", 4)
    post = capture_git_observation(target)
    evidence = _terminal_evidence(private, operation, terminal="committed")
    commit = {"schema": COMMIT_SCHEMA, "operation_id": operation["operation_id"], "operation_digest": digest_record(operation), "plan_digest": operation["plan_digest"], "entry": {"path": operation["entry"]["path"], "action": operation["entry"]["action"], "poststate": poststate}, "git_poststate": post, "managed_status_delta": derive_managed_git_delta(operation["git_prestate"], post, operation["entry"]["path"]), "terminal_evidence": evidence, "activation_complete": True, "readiness_assessed": False, "approval_authenticated": False}
    _write_new_at(private.operation_fd, "commit.json", commit)
    private.track_file("operation", "commit.json")
    private.assert_intact()
    _failpoint("commit")
    return commit


def publish_receipt(operation_dir: Path, operation: dict[str, Any], commit: dict[str, Any], target: Path) -> dict[str, Any]:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    try:
        existing, _ = _load_canonical_json_at(private.receipts_fd, f"{operation['operation_id']}.json", "receipt")
    except ActivationError:
        existing = None
    if existing is not None:
        _validate_receipt(existing, operation, commit)
        return existing
    receipt = {"schema": RECEIPT_SCHEMA, "operation_id": operation["operation_id"], "operation_digest": digest_record(operation), "commit_digest": digest_record(commit), "plan_digest": operation["plan_digest"], "target": operation["target"], "entry": {"path": operation["entry"]["path"], "action": operation["entry"]["action"], "poststate": commit["entry"]["poststate"]}, "custody": {"operation_dir": private.identities["operation"], "operation_record": custody_identity(private.files[("operation", "operation.json")])}, "terminal_evidence": commit["terminal_evidence"], "activation_complete": True, "readiness_assessed": False, "approval_authenticated": False}
    data, identity = _write_new_at(private.operation_fd, "receipt.json.next", receipt)
    private.files[("operation", "receipt.json.next")] = identity
    _failpoint("receipt")
    _publish_metadata_successor_at(
        private, "operation", "receipt.json.next", "receipts", f"{operation['operation_id']}.json",
        data=data, identity=identity, label="receipt successor", flags=1,
    )
    readback, readback_identity = _load_canonical_json_at(private.receipts_fd, f"{operation['operation_id']}.json", "receipt")
    if readback != receipt or not _same_custody_identity(readback_identity, identity):
        raise ActivationError("effect-unknown", "receipt successor final readback failed", 4)
    private.assert_intact()
    return receipt


def _record_backup_custody(operation_dir: Path, private: PrivateTransaction, operation: dict[str, Any]) -> None:
    _, identity = _private_payload_at(private.backup_fd, "0000.payload", private, "transaction backup")
    if not _matches_prestate_payload_at(private.backup_fd, "0000.payload", private, operation["entry"]["prestate"], "transaction backup"):
        raise ActivationError("effect-unknown", "backup does not retain exact prestate custody", 4)
    private.backup_custody = identity
    private.track_file("backup", "0000.payload")
    # Durable progress binds both provenance and exact artifact identity before
    # any later cleanup can remove this private payload.
    write_progress(operation_dir, _progress(operation, phase="published", effect="product_partial", backup_identity=identity), private.target_path)


def _backup_custody(private: PrivateTransaction, operation: dict[str, Any]) -> dict[str, Any]:
    if private.backup_custody is None:
        progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
        _validate_progress(progress, operation)
        _validate_progress_history_at(private, progress, operation)
        expected = progress["backup_identity"]
        if expected is None:
            raise ActivationError("effect-unknown", "durable backup custody is absent", 4)
        private.backup_custody = expected
    return private.backup_custody


def _seal_private_payload_at(parent_fd: int, name: str, private: PrivateTransaction, label: str) -> dict[str, Any]:
    raw, identity = _private_payload_at(parent_fd, name, private, label)
    try:
        fd = open_regular_at(parent_fd, name)
    except OSError as exc:
        raise ActivationError("effect-unknown", f"cannot seal {label}", 4) from exc
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not _same_custody_identity(file_identity_from_stat(before, raw), identity):
            raise ActivationError("effect-unknown", f"{label} changed before sealing", 4)
        os.fsync(fd)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if not _same_custody_identity(file_identity_from_stat(after, raw), identity):
        raise ActivationError("effect-unknown", f"{label} changed while sealing", 4)
    os.fsync(parent_fd)
    private.track_file("backup" if parent_fd == private.backup_fd else "discard", name)
    private.assert_intact()
    return identity


def _cleanup_private_artifacts(operation_dir: Path, operation: dict[str, Any], target: Path | None = None) -> None:
    private = _require_private(target or _ACTIVE_PRIVATE.target_path, operation_dir)
    # Product-safety evidence is terminally sealed in place. Do not unlink a
    # mutable private pathname after checking it: POSIX supplies no inode-bound
    # unlink, so retaining it is narrower and truthful.
    for fd, label in ((private.backup_fd, "backup"), (private.discard_fd, "discard")):
        private.assert_intact()
        names = os.listdir(fd)
        if any(name != "0000.payload" for name in names):
            raise ActivationError("effect-unknown", "unexpected private artifact", 4)
        if names:
            observed = _seal_private_payload_at(fd, "0000.payload", private, f"sealed terminal {label}")
            if label == "backup" and not _same_custody_identity(observed, _backup_custody(private, operation)):
                raise ActivationError("effect-unknown", "backup custody changed before terminal sealing", 4)
    # Staging witnesses are not terminal product evidence. Remove them only via
    # an fd-relative rename into discard; if discard is occupied, retain both.
    names = os.listdir(private.stage_fd)
    if any(name not in {"0000.payload", "0000.payload.next"} for name in names):
        raise ActivationError("effect-unknown", "unexpected private artifact", 4)
    if names:
        raise ActivationError("effect-unknown", "unexpected staged witness at terminal sealing", 4)
    private.assert_intact()
    _failpoint("cleanup")


def _validate_retained_terminal_evidence(private: PrivateTransaction, operation: dict[str, Any], evidence: dict[str, Any], *, terminal: str) -> None:
    expected = _validate_terminal_evidence(evidence, operation, terminal=terminal)
    for name in ("backup", "discard"):
        fd = getattr(private, f"{name}_fd")
        names = os.listdir(fd)
        item = expected[name]
        if item is None:
            if names:
                raise ActivationError("effect-unknown", f"unexpected retained {name} witness", 4)
            continue
        if names != ["0000.payload"]:
            raise ActivationError("effect-unknown", f"retained {name} layout diverged", 4)
        _, observed = _private_payload_at(fd, "0000.payload", private, f"retained terminal {name}")
        if observed != item["identity"]:
            raise ActivationError("effect-unknown", f"retained {name} identity diverged", 4)
        os.fsync(fd)
    if os.listdir(private.stage_fd):
        raise ActivationError("effect-unknown", "terminal staging witness remains", 4)
    private.assert_intact()


def _finish_committed(operation_dir: Path, operation: dict[str, Any], target: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    commit, _ = _load_canonical_json_at(private.operation_fd, "commit.json", "commit")
    _validate_commit(commit, operation)
    if readback_product(operation, target) != commit["entry"]["poststate"]:
        raise ActivationError("effect-unknown", "committed product no longer matches commit", 4)
    receipt_name = f"{operation['operation_id']}.json"
    try:
        receipt, _ = _load_canonical_json_at(private.receipts_fd, receipt_name, "receipt")
    except ActivationError:
        try:
            receipt, _ = _load_canonical_json_at(private.operation_fd, "receipt.json.next", "staged receipt")
        except ActivationError:
            receipt = publish_receipt(operation_dir, operation, commit, target)
        else:
            _validate_receipt(receipt, operation, commit)
            staged_data = canonical_bytes(receipt)
            staged_identity = private.files.get(("operation", "receipt.json.next"))
            if staged_identity is None:
                _, staged_identity = _read_stable_at(private.operation_fd, "receipt.json.next", "staged receipt")
                private.files[("operation", "receipt.json.next")] = staged_identity
            _publish_metadata_successor_at(
                private, "operation", "receipt.json.next", "receipts", receipt_name,
                data=staged_data, identity=staged_identity, label="recovered receipt successor", flags=1,
            )
    else:
        _validate_receipt(receipt, operation, commit)
        private.track_file("receipts", receipt_name)
    if readback_product(operation, target) != commit["entry"]["poststate"]:
        raise ActivationError("effect-unknown", "live product changed after receipt publication", 4)
    _cleanup_private_artifacts(operation_dir, operation, target)
    _validate_retained_terminal_evidence(private, operation, commit["terminal_evidence"], terminal="committed")
    _validate_terminal_convergence(operation_dir, operation, commit, receipt, target)
    write_progress(operation_dir, _progress(operation, phase="committed", effect="committed", terminal_evidence=commit["terminal_evidence"]), target)
    _validate_terminal_convergence(operation_dir, operation, commit, receipt, target)
    _validate_retained_terminal_evidence(private, operation, commit["terminal_evidence"], terminal="committed")
    return commit, receipt


def _commit_operation(operation_dir: Path, operation: dict[str, Any], target: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    commit_path = operation_dir / "commit.json"
    if commit_path.exists():
        return _finish_committed(operation_dir, operation, target)
    poststate = readback_product(operation, target)
    write_progress(operation_dir, _progress(operation, phase="published", effect="product_partial"), target)
    commit = write_commit(operation_dir, operation, poststate, target)
    receipt = publish_receipt(operation_dir, operation, commit, target)
    # Second terminal binding: receipt publication itself cannot make a stale
    # live object successful. The receipt remains an immutable recovery witness.
    if readback_product(operation, target) != commit["entry"]["poststate"] or receipt["entry"]["poststate"] != commit["entry"]["poststate"]:
        raise ActivationError("effect-unknown", "live product changed after receipt publication", 4)
    _cleanup_private_artifacts(operation_dir, operation, target)
    _validate_retained_terminal_evidence(private, operation, commit["terminal_evidence"], terminal="committed")
    _validate_terminal_convergence(operation_dir, operation, commit, receipt, target)
    write_progress(operation_dir, _progress(operation, phase="committed", effect="committed", terminal_evidence=commit["terminal_evidence"]), target)
    _validate_terminal_convergence(operation_dir, operation, commit, receipt, target)
    _validate_retained_terminal_evidence(private, operation, commit["terminal_evidence"], terminal="committed")
    return commit, receipt


def _apply_effectful(plan: dict[str, Any], manifest_path: Path, grant: dict[str, Any]) -> tuple[dict[str, Any], int]:
    target = Path(plan["target"]["path"])
    rendered, _ = _revalidate_plan(plan, manifest_path)
    operation = _new_operation(plan, grant)
    operation_dir = _make_layout(target, operation)
    with _pin_private(target, operation["operation_id"]) as private:
        _consume_grant(operation_dir, grant, target)
        staged = stage_payload(operation_dir, operation, rendered["content"], target)
        if operation["entry"]["action"] == "create":
            publish_create(operation_dir, operation, target)
        else:
            publish_replace(operation_dir, operation, target)
        _failpoint("publish")
        commit, receipt = _commit_operation(operation_dir, operation, target)
    return _result("apply", "committed", 0, target, effect="committed", plan_digest=digest_record(plan), operation_id=operation["operation_id"], operation_digest=digest_record(operation), receipt_digest=digest_record(receipt)), 0


def _apply_noop(plan: dict[str, Any], manifest_path: Path, grant: dict[str, Any]) -> tuple[dict[str, Any], int]:
    target = Path(plan["target"]["path"])
    _revalidate_plan(plan, manifest_path)
    plane = _resolve_plane(target)
    operation_id = uuid.uuid4().hex
    audit = {"schema": AUDIT_SCHEMA, "operation_id": operation_id, "kind": "no-op", "target": plan["target"], "plan_digest": digest_record(plan), "manifest_sha256": plan["manifest_sha256"], "grant": {"grant_id": grant["grant_id"], "document_digest": digest_record(grant)}, "verified_outputs": plan["verified_outputs"], "git_observation": plan["git"], "existing_receipt_digests": [digest_record(load_canonical_json(item, "receipt")[0]) for item in plane.receipts.glob("*.json")] if plane.receipts.is_dir() else [], "effect": "audit_only", "approval_authenticated": False}
    if not plane.repo_local:
        # The audit is plane state too, so the plane root has to exist before it lands -- and
        # the pointer has to exist before the plane root, for the same reason as in
        # `_make_layout`. An audit alone IS state a plane switch or a rename must not step
        # over: it is the grant ledger.
        binding = bind_target(target)
        target_fd = open_root_chain(target)
        try:
            # Same order as `_make_layout`, for the same reason: refuse an unsafe plane home
            # before the pointer exists rather than admitting the pointer and reporting it.
            _assert_plane_ancestors(plane, binding)
            _record_plane_pointer(target, plane, binding)
            os.close(_mkdir_plane_root(plane, binding, target_fd))
        finally:
            os.close(target_fd)
    write_new_metadata(plane.anchor_dir / plane.audit_name(operation_id), audit)
    return _result("apply", "no-op", 0, target, effect="audit_only", plan_digest=digest_record(plan), operation_id=operation_id), 0


def apply_command(plan_path: Path, manifest_path: Path, grant_path: Path) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            plan, _ = load_canonical_json(plan_path, "plan")
            _validate_plan(plan)
            target = Path(plan["target"]["path"])
            binding = bind_target(target)
            _validate_private_state(target, binding)
            grant, _ = load_canonical_json(grant_path, "grant")
            validate_grant(grant, operation="apply")
            if grant["plan_digest"] != digest_record(plan) or grant["target"] != {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino}:
                raise ActivationError("refused", "grant does not bind exact plan target")
            with activation_lock(target):
                locked_binding = bind_target(target)
                _validate_private_state(target, locked_binding)
                _scan_operation_exclusion(target, locked_binding)
                scan_grant_ledger(target, grant)
                if plan["entries"]:
                    return _apply_effectful(plan, manifest_path, grant)
                return _apply_noop(plan, manifest_path, grant)
        except ActivationError as exc:
            target = Path(plan["target"]["path"]) if "plan" in locals() and isinstance(plan, dict) and isinstance(plan.get("target"), dict) else Path("/")
            return _report_failure("apply", exc, target)


def _load_operation(target: Path) -> tuple[Path, dict[str, Any]]:
    root = bind_target(target)
    _validate_private_state(target, root)
    directories = _operation_dirs(target, root)
    active: list[tuple[Path, dict[str, Any]]] = []
    for directory in directories:
        try:
            operation, _ = load_canonical_json(directory / "operation.json", "operation")
            _validate_operation(operation)
            _bind_operation_target(target, operation)
        except ActivationError as exc:
            raise ActivationError("effect-unknown", f"invalid operation witness: {exc.reason}", 4) from exc
        state, reasons = classify_progress_witness(directory, operation)
        if state == "effect_unknown":
            raise ActivationError("effect-unknown", "; ".join(reasons), 4)
        if state == "recovery-required": active.append((directory, operation))
    if len(active) != 1:
        raise ActivationError("effect-unknown" if active else "inactive", "no unique active transaction", 4 if active else 0)
    return active[0]


def classify_recovery(target: Path) -> tuple[Path, dict[str, Any], list[str]]:
    directory, operation = _load_operation(target)
    progress_path = directory / "progress.json"
    try:
        progress, _ = load_canonical_json(progress_path, "progress")
        _validate_progress(progress, operation)
    except ActivationError as exc:
        raise ActivationError("effect-unknown", f"invalid staged progress witness: {exc.reason}", 4) from exc
    staged_custody = progress["staged_custody"]
    commit_path = directory / "commit.json"
    if commit_path.exists():
        commit, _ = load_canonical_json(commit_path, "commit")
        _validate_commit(commit, operation)
        return directory, operation, ["finish"]
    live_state, raw = capture_prestate(target, operation["entry"]["path"])
    desired = operation["entry"]["desired"]
    live_desired = raw is not None and hashlib.sha256(raw).hexdigest() == desired["sha256"]
    stage = directory / "stage" / "0000.payload"
    backup = directory / "backup" / "0000.payload"
    legal: list[str] = []
    if live_desired:
        if staged_custody is None:
            raise ActivationError("effect-unknown", "published staged witness lacks durable custody", 4)
        live_identity = live_state["identity"]
        if live_identity is None or not _same_custody_identity(live_identity, staged_custody):
            raise ActivationError("effect-unknown", "published live witness does not retain durable staged custody", 4)
        legal.append("finish")
        if operation["entry"]["action"] == "create" or backup.exists(): legal.append("rollback")
    elif stage.exists() and live_state == operation["entry"]["prestate"]:
        if staged_custody is None:
            raise ActivationError("effect-unknown", "staged witness lacks durable custody", 4)
        try:
            stage_raw, stage_identity = read_stable_file(stage, "staged recovery payload")
        except ActivationError as exc:
            raise ActivationError("effect-unknown", "cannot inspect staged recovery custody", 4) from exc
        if (
            len(stage_raw) != desired["size"]
            or stage_identity["mode"] != desired["mode"]
            or stage_identity["sha256"] != desired["sha256"]
            or not _same_custody_identity(stage_identity, staged_custody)
        ):
            raise ActivationError("effect-unknown", "staged recovery witness does not match durable custody", 4)
        legal.extend(["finish", "rollback"])
    if not legal:
        raise ActivationError("effect-unknown", "witnesses do not match a recovery state", 4)
    return directory, operation, legal


def recover_inspect_command(target: Path) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            target = Path(target)
            directory, operation, legal = classify_recovery(target)
            return _result("recover inspect", "recovery-required", 3, target, effect="product_partial", operation_id=operation["operation_id"], operation_digest=digest_record(operation), legal=legal, operation=operation), 3
        except ActivationError as exc:
            return _report_failure("recover inspect", exc, Path(target))


def _validate_recovery_grant(target: Path, operation_dir: Path, operation: dict[str, Any], grant_path: Path, decision: str) -> dict[str, Any]:
    _validate_operation(operation)
    _bind_operation_target(target, operation)
    grant, _ = load_canonical_json(grant_path, "grant")
    validate_grant(grant, operation="recover")
    if grant["operation_id"] != operation["operation_id"] or grant["operation_digest"] != digest_record(operation) or grant["decision"] != decision or grant["target"] != {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino}:
        raise ActivationError("refused", "recovery grant does not bind exact decision")
    scan_grant_ledger(target, grant)
    _consume_grant(operation_dir, grant, target)
    return grant


def finish_operation(operation_dir: Path, operation: dict[str, Any]) -> tuple[dict[str, Any], int]:
    target = Path(operation["target"]["path"])
    _bind_operation_target(target, operation)
    if (operation_dir / "commit.json").exists():
        commit, receipt = _finish_committed(operation_dir, operation, target)
        return _result("recover finish", "committed", 0, target, effect="committed", operation_id=operation["operation_id"], operation_digest=digest_record(operation), receipt_digest=digest_record(receipt)), 0
    live_state, raw = capture_prestate(target, operation["entry"]["path"])
    desired = operation["entry"]["desired"]
    if raw is None or hashlib.sha256(raw).hexdigest() != desired["sha256"]:
        staged = operation_dir / "stage" / "0000.payload"
        if not staged.exists() or live_state != operation["entry"]["prestate"]:
            raise ActivationError("effect-unknown", "cannot safely finish", 4)
        if operation["entry"]["action"] == "create": publish_create(operation_dir, operation, target)
        else: publish_replace(operation_dir, operation, target)
    _failpoint("finish")
    commit, receipt = _commit_operation(operation_dir, operation, target)
    return _result("recover finish", "committed", 0, target, effect="committed", operation_id=operation["operation_id"], operation_digest=digest_record(operation), receipt_digest=digest_record(receipt)), 0


def rollback_create(operation_dir: Path, operation: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    live_parent_fd, live_name = _open_live_parent_at(private.target_fd, operation["entry"]["path"])
    try:
        state, raw = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
        if state["kind"] != "regular" or raw is None or not _matches_desired_payload_at(live_parent_fd, live_name, private, operation["entry"]["desired"], "create rollback live"):
            raise ActivationError("effect-unknown", "create rollback live object no longer matches desired output", 4)
        desired_identity = state["identity"]
        assert desired_identity is not None
        _require_staged_custody(desired_identity, private, operation, "create rollback live")
        _renameat2_at(live_parent_fd, live_name, private.discard_fd, "0000.payload", 1)
        private.track_file("discard", "0000.payload")
        try:
            moved_raw, moved_identity = _private_payload_at(private.discard_fd, "0000.payload", private, "create rollback discard")
            if moved_raw != raw or not _same_custody_identity(moved_identity, desired_identity):
                _restore_create_mismatch_at(private, live_parent_fd, live_name, desired_identity, raw)
                raise ActivationError("effect-unknown", "uncooperative same-UID writer replaced target during create rollback; external bytes were restored live", 4)
        except ActivationError:
            raise
    finally:
        os.close(live_parent_fd)
    private.assert_intact()


def _restore_create_mismatch_at(private: PrivateTransaction, live_parent_fd: int, live_name: str, moved_identity: dict[str, Any], before: bytes) -> None:
    try:
        _renameat2_at(private.discard_fd, "0000.payload", live_parent_fd, live_name, 1)
    except ActivationError as exc:
        # A no-replace conflict proves a newer finite live object exists. Do not
        # exchange it away: retain the moved older object in discard and report
        # that the rollback effect cannot be classified.
        if exc.status != "stale":
            raise
        discard_raw, discard_identity = _private_payload_at(private.discard_fd, "0000.payload", private, "retained create rollback witness")
        live_raw, live_identity = _read_stable_at(live_parent_fd, live_name, "newer create rollback live witness")
        if discard_raw != before or not _same_custody_identity(discard_identity, moved_identity):
            raise ActivationError("effect-unknown", "create rollback moved witness lost custody after restore conflict", 4)
        if live_raw == before and _same_custody_identity(live_identity, moved_identity):
            raise ActivationError("effect-unknown", "create rollback restore conflict lacks a newer live witness", 4)
        os.fsync(private.discard_fd)
        os.fsync(live_parent_fd)
        private.track_file("discard", "0000.payload")
        private.assert_intact()
        raise ActivationError("effect-unknown", "create rollback retained older discard and preserved newer live witness", 4) from exc
    private.untrack_file("discard", "0000.payload")
    raw, identity = _read_stable_at(live_parent_fd, live_name, "restored create rollback")
    if raw != before or not _same_custody_identity(identity, moved_identity):
        raise ActivationError("effect-unknown", "create rollback mismatch could not be restored live", 4)
    private.assert_intact()


def rollback_replace(operation_dir: Path, operation: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    live_parent_fd, live_name = _open_live_parent_at(private.target_fd, operation["entry"]["path"])
    try:
        live_state, live_raw = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
        desired = operation["entry"]["desired"]
        if live_state["kind"] != "regular" or live_raw is None or not _matches_desired_payload_at(live_parent_fd, live_name, private, desired, "replace rollback live"):
            raise ActivationError("effect-unknown", "cannot claim rollback against a continuously racing uncooperative same-UID writer", 4)
        if not _matches_prestate_payload_at(private.backup_fd, "0000.payload", private, operation["entry"]["prestate"], "replace rollback backup"):
            raise ActivationError("effect-unknown", "replace rollback backup no longer matches prestate", 4)
        live_identity = live_state["identity"]
        assert live_identity is not None
        _require_staged_custody(live_identity, private, operation, "replace rollback live")
        _renameat2_at(live_parent_fd, live_name, private.backup_fd, "0000.payload", 2)
        private.track_file("backup", "0000.payload")
        moved_raw, moved_identity = _private_payload_at(private.backup_fd, "0000.payload", private, "exchanged rollback desired payload")
        if moved_raw != live_raw or not _same_custody_identity(moved_identity, live_identity):
            _restore_exchange_mismatch_at(private, private.backup_fd, live_parent_fd, live_name, "0000.payload", live_raw, live_identity, "replace rollback")
            raise ActivationError("effect-unknown", "uncooperative same-UID writer replaced target during rollback exchange; external bytes were restored live", 4)
        _renameat2_at(private.backup_fd, "0000.payload", private.discard_fd, "0000.payload", 1)
        private.untrack_file("backup", "0000.payload")
        private.track_file("discard", "0000.payload")
    finally:
        os.close(live_parent_fd)
    private.assert_intact()


def verify_restored_suffix(operation: dict[str, Any], target: Path, private: PrivateTransaction | None = None) -> None:
    _bind_operation_target(target, operation)
    if private is None:
        state, raw = capture_prestate(target, operation["entry"]["path"])
    else:
        private.assert_intact()
        state, raw = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
    expected = operation["entry"]["prestate"]
    if expected["kind"] == "absent":
        if state["kind"] != "absent":
            raise ActivationError("effect-unknown", "rollback readback does not restore absence", 4)
        return
    identity = expected["identity"]
    if (
        state["kind"] != "regular"
        or raw is None
        or identity is None
        or not _same_custody_identity(state["identity"], identity)
        or len(raw) != identity["size"]
    ):
        raise ActivationError("effect-unknown", "rollback readback does not restore original custody and bytes", 4)


def _same_git_projection(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return {key: value for key, value in left.items() if key != "filtered_internal"} == {key: value for key, value in right.items() if key != "filtered_internal"}


def write_rollback(operation_dir: Path, operation: dict[str, Any], grant: dict[str, Any], target: Path) -> dict[str, Any]:
    private = _require_private(target, operation_dir)
    _bind_operation_target(target, operation)
    post = capture_git_observation(target)
    if not _same_git_projection(post, operation["git_prestate"]):
        raise ActivationError("effect-unknown", "rollback did not restore Git baseline", 4)
    evidence = _terminal_evidence(private, operation, terminal="rolled-back")
    record = {"schema": ROLLBACK_SCHEMA, "operation_id": operation["operation_id"], "operation_digest": digest_record(operation), "recovery_grant_digest": digest_record(grant), "restored_entry": {"path": operation["entry"]["path"], "prestate": operation["entry"]["prestate"]}, "restored_suffix": [operation["entry"]["path"]], "git_poststate": post, "terminal_evidence": evidence, "rollback_complete": True, "approval_authenticated": False}
    _write_new_at(private.operation_fd, "rollback.json", record)
    private.track_file("operation", "rollback.json")
    private.assert_intact()
    return record


def _validate_rollback_terminal_convergence(operation_dir: Path, operation: dict[str, Any], rollback: dict[str, Any], progress: dict[str, Any], target: Path) -> None:
    """Descriptor-bound final rollback snapshot; live restoration is observed last."""
    private = _require_private(target, operation_dir)
    _validate_operation(operation)
    pinned_operation, _ = _load_canonical_json_at(private.operation_fd, "operation.json", "operation")
    if pinned_operation != operation:
        raise ActivationError("effect-unknown", "rollback operation record changed", 4)
    pinned_rollback, _ = _load_canonical_json_at(private.operation_fd, "rollback.json", "rollback")
    if pinned_rollback != rollback:
        raise ActivationError("effect-unknown", "rollback record changed", 4)
    pinned_progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
    if pinned_progress != progress:
        raise ActivationError("effect-unknown", "rollback progress record changed", 4)
    _validate_progress_history_at(private, progress, operation)
    _validate_rollback(rollback, operation, operation_dir)
    _validate_progress(progress, operation)
    if (
        progress["phase"] != "rolled-back"
        or progress["direction"] != "rollback"
        or progress["effect"] != "rolled_back"
        or progress["cleanup_state"] != "complete"
        or progress["receipt_state"] != "absent"
        or progress["terminal_evidence"] != rollback["terminal_evidence"]
    ):
        raise ActivationError("effect-unknown", "rollback terminal progress does not bind rollback record", 4)
    _validate_retained_terminal_evidence(private, operation, rollback["terminal_evidence"], terminal="rolled-back")
    _validate_terminal_evidence_snapshot(target, operation, rollback["terminal_evidence"], terminal="rolled-back")
    private.assert_intact()
    post = capture_git_observation(target)
    if not _same_git_projection(post, rollback["git_poststate"]) or not _same_git_projection(post, operation["git_prestate"]):
        raise ActivationError("effect-unknown", "rollback final Git baseline diverged", 4)
    # Last filesystem observation before the rolled-back return: never let a
    # finite post-progress live replacement become a successful terminal claim.
    verify_restored_suffix(operation, target, private)


def _recover(target: Path, grant_path: Path, decision: str) -> tuple[dict[str, Any], int]:
    presented_grant, _ = load_canonical_json(grant_path, "grant")
    validate_grant(presented_grant, operation="recover")
    scan_grant_ledger(target, presented_grant)
    directory, operation, legal = classify_recovery(target)
    if decision not in legal: raise ActivationError("refused", "requested recovery decision is not legal")
    try:
        with _pin_private(target, operation["operation_id"]):
            grant = _validate_recovery_grant(target, directory, operation, grant_path, decision)
            if decision == "finish":
                return finish_operation(directory, operation)
            private = _require_private(target, directory)
            live_state, _ = _capture_prestate_at(private.target_fd, operation["entry"]["path"])
            if live_state == operation["entry"]["prestate"]:
                _discard_exact_staged_payload(directory, operation, target)
            elif operation["entry"]["action"] == "create":
                rollback_create(directory, operation, target)
            else:
                rollback_replace(directory, operation, target)
            _failpoint("rollback")
            verify_restored_suffix(operation, target)
            rollback = write_rollback(directory, operation, grant, target)
            _cleanup_private_artifacts(directory, operation, target)
            evidence = _terminal_evidence(private, operation, terminal="rolled-back")
            _validate_retained_terminal_evidence(private, operation, evidence, terminal="rolled-back")
            terminal_progress = _progress(operation, phase="rolled-back", effect="rolled_back", direction="rollback", terminal_evidence=evidence)
            write_progress(directory, terminal_progress, target)
            persisted_progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "rollback progress")
            _validate_rollback_terminal_convergence(directory, operation, rollback, persisted_progress, target)
            return _result("recover rollback", "rolled-back", 0, target, effect="rolled_back", operation_id=operation["operation_id"], operation_digest=digest_record(operation)), 0
    finally:
        pass


def recover_finish_command(target: Path, grant_path: Path) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            with activation_lock(Path(target)): return _recover(Path(target), grant_path, "finish")
        except ActivationError as exc:
            return _report_failure("recover finish", exc, Path(target))


def recover_rollback_command(target: Path, grant_path: Path) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            with activation_lock(Path(target)): return _recover(Path(target), grant_path, "rollback")
        except ActivationError as exc:
            return _report_failure("recover rollback", exc, Path(target))


def _validate_receipt_custody(private: PrivateTransaction, receipt: dict[str, Any]) -> None:
    custody = _exact(receipt.get("custody"), {"operation_dir", "operation_record"}, "receipt custody")
    _validate_dir_identity(custody["operation_dir"], "receipt operation directory custody")
    _validate_custody_identity(custody["operation_record"], "receipt operation record custody")
    operation_record = private.files.get(("operation", "operation.json"))
    if operation_record is None or (
        custody["operation_dir"] != private.identities["operation"]
        or custody["operation_record"] != custody_identity(operation_record)
    ):
        raise ActivationError("effect-unknown", "receipt custody no longer binds the operation namespace", 4)


def _validate_terminal_product(target: Path, operation: dict[str, Any], commit: dict[str, Any], receipt: dict[str, Any]) -> None:
    desired = operation["entry"]["desired"]
    poststate = commit["entry"]["poststate"]
    if receipt["entry"]["poststate"] != poststate or any(poststate[key] != desired[key] for key in ("mode", "size", "sha256")):
        raise ActivationError("effect-unknown", "terminal product witnesses disagree", 4)
    live = readback_product(operation, target)
    if live != poststate:
        raise ActivationError("effect-unknown", "live product no longer matches terminal poststate", 4)


def _validate_terminal_git_projection(target: Path, operation: dict[str, Any], commit: dict[str, Any]) -> None:
    current_git = capture_git_observation(target)
    derive_managed_git_delta(commit["git_poststate"], current_git, operation["entry"]["path"])


def _validate_terminal_live_binding(target: Path, operation: dict[str, Any], commit: dict[str, Any], receipt: dict[str, Any]) -> None:
    """Validate terminal live product and Git projection for intermediate checks."""
    _validate_terminal_product(target, operation, commit, receipt)
    _validate_terminal_git_projection(target, operation, commit)


def _validate_terminal_convergence(operation_dir: Path, operation: dict[str, Any], commit: dict[str, Any], receipt: dict[str, Any], target: Path) -> None:
    private = _require_private(target, operation_dir)
    _validate_receipt_custody(private, receipt)
    _validate_retained_terminal_evidence(private, operation, commit["terminal_evidence"], terminal="committed")
    pinned_operation, _ = _load_canonical_json_at(private.operation_fd, "operation.json", "operation")
    if pinned_operation != operation:
        raise ActivationError("effect-unknown", "terminal operation record changed", 4)
    pinned_commit, _ = _load_canonical_json_at(private.operation_fd, "commit.json", "commit")
    if pinned_commit != commit:
        raise ActivationError("effect-unknown", "terminal commit record changed", 4)
    pinned_receipt, _ = _load_canonical_json_at(private.receipts_fd, f"{operation['operation_id']}.json", "receipt")
    if pinned_receipt != receipt:
        raise ActivationError("effect-unknown", "terminal receipt record changed", 4)
    _validate_commit(commit, operation)
    _validate_receipt(receipt, operation, commit)
    private.assert_intact()
    _validate_terminal_git_projection(target, operation, commit)
    # Keep live product validation last: this is the final filesystem
    # observation before the caller forms a committed snapshot/result.
    _validate_terminal_product(target, operation, commit, receipt)


def _validate_terminal_evidence_snapshot(target: Path, operation: dict[str, Any], evidence: dict[str, Any], *, terminal: str) -> None:
    evidence = _validate_terminal_evidence(evidence, operation, terminal=terminal)
    plane = _resolve_plane(target)
    target_fd = open_root_chain(target)
    try:
        operation_fd = _open_transaction_private(target_fd, plane, operation["operation_id"])
    finally:
        os.close(target_fd)
    try:
        for name in ("backup", "discard"):
            item = evidence[name]
            fd = open_component_dir(operation_fd, name)
            try:
                names = os.listdir(fd)
                if item is None:
                    if names:
                        raise ActivationError("effect-unknown", f"unexpected retained {name} witness", 4)
                    continue
                if names != ["0000.payload"]:
                    raise ActivationError("effect-unknown", f"retained {name} layout diverged", 4)
                raw, identity = _read_stable_at(fd, "0000.payload", f"retained terminal {name}")
                if identity != item["identity"]:
                    raise ActivationError("effect-unknown", f"retained {name} identity diverged", 4)
                if identity["nlink"] != 1:
                    raise ActivationError("effect-unknown", f"retained {name} is unsafe", 4)
            finally:
                os.close(fd)
        stage_fd = open_component_dir(operation_fd, "stage")
        try:
            if os.listdir(stage_fd):
                raise ActivationError("effect-unknown", "terminal staging witness remains", 4)
        finally:
            os.close(stage_fd)
    finally:
        os.close(operation_fd)


def _validate_terminal_private_records(target: Path, operation: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        with _pin_private(target, operation["operation_id"]) as private:
            receipt, _ = _load_canonical_json_at(private.receipts_fd, f"{operation['operation_id']}.json", "receipt")
            _validate_receipt_custody(private, receipt)
            pinned_operation, _ = _load_canonical_json_at(private.operation_fd, "operation.json", "operation")
            if pinned_operation != operation:
                raise ActivationError("effect-unknown", "terminal operation pathname no longer binds its validated record", 4)
            progress, _ = _load_canonical_json_at(private.operation_fd, "progress.json", "progress")
            _validate_progress(progress, operation)
            _validate_progress_history_at(private, progress, operation)
            if progress["phase"] != "committed" or progress["cleanup_state"] != "complete":
                raise ActivationError("effect-unknown", "terminal commit lacks terminal cleanup", 4)
            commit, _ = _load_canonical_json_at(private.operation_fd, "commit.json", "commit")
            _validate_commit(commit, operation)
            _validate_receipt(receipt, operation, commit)
            if progress["terminal_evidence"] != commit["terminal_evidence"]:
                raise ActivationError("effect-unknown", "terminal progress evidence disagrees with commit", 4)
            _validate_terminal_evidence_snapshot(target, operation, commit["terminal_evidence"], terminal="committed")
            private.assert_intact()
            return commit, receipt
    except (OSError, ActivationError) as exc:
        if isinstance(exc, ActivationError):
            raise
        raise ActivationError("effect-unknown", "terminal private namespace diverged", 4) from exc


def _final_status_namespace_observation(target: Path, operation: dict[str, Any], commit: dict[str, Any], receipt: dict[str, Any]) -> None:
    """Read-only terminal snapshot; later cooperative-writer mutation is outside it."""
    try:
        with _pin_private(target, operation["operation_id"]) as private:
            _validate_terminal_convergence(private.plane.operation_dir(operation["operation_id"]), operation, commit, receipt, target)
    except (OSError, ActivationError) as exc:
        if isinstance(exc, ActivationError):
            raise
        raise ActivationError("effect-unknown", "terminal status namespace diverged", 4) from exc


def _validate_existing_terminal_operation(target: Path, directory: Path, operation: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    _validate_operation(operation)
    _bind_operation_target(target, operation)
    state, reasons = classify_progress_witness(directory, operation)
    if state == "effect_unknown":
        raise ActivationError("effect-unknown", "; ".join(reasons), 4)
    commit_path = directory / "commit.json"
    if not commit_path.exists():
        return state, None
    if state == "recovery-required":
        return state, None
    # All closed terminal records and the pinned private layout are validated
    # before observing the live object or Git projection.
    commit, receipt = _validate_terminal_private_records(target, operation)
    _validate_terminal_live_binding(target, operation, commit, receipt)
    # This must stay last: it binds records, private namespace, live product,
    # and Git projection into one read-only cooperative-writer status snapshot.
    _final_status_namespace_observation(target, operation, commit, receipt)
    return "committed", receipt


def status_command(target: Path) -> tuple[dict[str, Any], int]:
    with _effect_ledger():
        try:
            target = Path(target)
            root = bind_target(target)
            _validate_private_state(target, root)
            active = []
            committed = []
            for directory in _operation_dirs(target, root):
                try:
                    operation, _ = load_canonical_json(directory / "operation.json", "operation")
                    state, receipt = _validate_existing_terminal_operation(target, directory, operation)
                except ActivationError as exc:
                    # An unparseable or diverged terminal witness is an effect this command only
                    # OBSERVED, so it is escalated at the raise site's own code and reported
                    # through the one derivation point like every other refusal.
                    raise ActivationError("effect-unknown", exc.reason, 4) from exc
                if state == "recovery-required": active.append((operation, ["recovery required"]))
                elif state == "committed": committed.append((operation, receipt))
            if active:
                operation, reasons = active[0]
                return _result("status", "recovery-required", 3, target, effect="product_partial", operation_id=operation["operation_id"], operation_digest=digest_record(operation), legal=["finish", "rollback"], reasons=reasons), 3
            owners: dict[str, str] = {}
            for operation, _ in committed:
                path = operation["entry"]["path"]
                if path in owners:
                    raise ActivationError("effect-unknown", "multiple committed operations manage one path", 4)
                owners[path] = operation["operation_id"]
            if committed:
                operation, record = committed[-1]
                assert record is not None
                return _result("status", "committed", 0, target, effect="committed", operation_id=operation["operation_id"], operation_digest=digest_record(operation), receipt_digest=digest_record(record)), 0
            return _result("status", "inactive", 0, target, effect=EFFECT_NONE), 0
        except ActivationError as exc:
            return _report_failure("status", exc, Path(target))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan"); plan.add_argument("--target", type=Path, required=True); plan.add_argument("--manifest", type=Path, required=True); plan.add_argument("--entry", required=True)
    apply = commands.add_parser("apply"); apply.add_argument("--plan", type=Path, required=True); apply.add_argument("--manifest", type=Path, required=True); apply.add_argument("--grant", type=Path, required=True)
    status = commands.add_parser("status"); status.add_argument("--target", type=Path, required=True)
    recover = commands.add_parser("recover"); rec = recover.add_subparsers(dest="recovery", required=True)
    inspect = rec.add_parser("inspect"); inspect.add_argument("--target", type=Path, required=True)
    for decision in ("finish", "rollback"):
        item = rec.add_parser(decision); item.add_argument("--target", type=Path, required=True); item.add_argument("--grant", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "plan": result, code = plan_command(args.target, args.manifest, args.entry)
    elif args.command == "apply": result, code = apply_command(args.plan, args.manifest, args.grant)
    elif args.command == "status": result, code = status_command(args.target)
    elif args.recovery == "inspect": result, code = recover_inspect_command(args.target)
    elif args.recovery == "finish": result, code = recover_finish_command(args.target, args.grant)
    else: result, code = recover_rollback_command(args.target, args.grant)
    sys.stdout.buffer.write(canonical_bytes(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
