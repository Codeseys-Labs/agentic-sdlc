#!/usr/bin/env python3
"""Durable, local-only acquisition of one unpublished release candidate.

This module is deliberately a lifecycle engine rather than another dispatcher.  The public
grammar remains owned by ``release_candidate.py``; all target roots are explicit plan inputs.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import types
from typing import Callable, Mapping, Sequence


POLICY_NAME = "release-candidate-acquisition.v1.json"
POLICY_SCHEMA = "release-candidate-acquisition-policy/v1"
EFFECTS = [
    "xdg-data-candidate-publish",
    "xdg-data-candidate-stage",
    "xdg-state-grant-consumption",
    "xdg-state-journal",
    "xdg-state-receipt",
    "xdg-state-writer-lock",
]
PHASES = ["opened", "pinned", "staged", "published", "receipted", "installed-unselected"]
INTERPRETER_RELATIVE = "runtime/python/bin/python3.12"
RENAME_NOREPLACE = 1
AT_EMPTY_PATH = 0x1000
STATX_BASIC_STATS = 0x07FF
STATX_BTIME = 0x0800
SYS_RENAMEAT2_X86_64 = 316
SYS_STATX_X86_64 = 332
AT_FDCWD = -100
ZERO_SHA = "0" * 64
_TEST_FAULT_HOOK: Callable[[str], None] | None = None
_TEST_RACE_HOOK: Callable[[str], None] | None = None
_TEST_EXTERNAL_RACE_HOOK: Callable[[str, Path, int], None] | None = None
_TEST_FIRST_EFFECT_HOOK: Callable[[str], None] | None = None
_TEST_RECEIPT_HOOK: Callable[[str], None] | None = None

BOOTSTRAP_RE = re.compile(
    r"\.agentic-sdlc-acquisition-v1-(op-[0-9a-f]{32})-"
    r"([0-9a-f]{64})-([0-9a-f]{64})\.opened\.json"
)
RECOVERY_MARKER_RE = re.compile(
    r"\.agentic-sdlc-acquisition-recovery-v1-(op-[0-9a-f]{32})-"
    r"([0-9a-f]{64})-([0-9a-f]{64})\.used"
)


@dataclass(frozen=True)
class AcquisitionFailure(Exception):
    code: str
    exit_code: int = 3
    operation_id: str | None = None
    journal_locator: str | None = None
    last_phase: str = "absent"
    classification: str = "exact"


@dataclass
class RootPin:
    path: Path
    fd: int
    identity: tuple[int, int, int, int, int, int]
    prestate_sha256: str

    def close(self) -> None:
        os.close(self.fd)


@dataclass
class DirPin:
    """An opened lifecycle directory whose fd, not its display path, owns custody."""

    fd: int
    identity: tuple[int, int, int, int]
    display_path: Path
    parent_fd: int
    name: str

    def close(self) -> None:
        os.close(self.fd)


@dataclass
class ExternalFilePin:
    """A bounded external file retained through the operation that consumes it."""

    path: Path
    fd: int
    identity: tuple[int, int, int, int, int]
    item: os.stat_result
    parent_fd: int
    name: str
    ancestors: list[DirPin]
    root_fd: int

    def close(self) -> None:
        os.close(self.fd)
        _close_pins(self.ancestors)
        os.close(self.root_fd)


def _dir_identity(item: os.stat_result) -> tuple[int, int, int, int]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_uid,
        stat.S_IMODE(item.st_mode),
    )


def _sync_fd(fd: int, code: str, *, partial: bool = False) -> None:
    try:
        os.fsync(fd)
    except OSError:
        _fail(code, 4 if partial else 3, classification="unavailable")


def _recheck_dir(pin: DirPin, code: str, *, partial: bool) -> None:
    try:
        current = os.fstat(pin.fd)
        named = os.stat(pin.name, dir_fd=pin.parent_fd, follow_symlinks=False)
    except OSError:
        _fail(code, 4 if partial else 3, classification="unavailable")
    if (
        not stat.S_ISDIR(current.st_mode)
        or not stat.S_ISDIR(named.st_mode)
        or _dir_identity(current) != pin.identity
        or (named.st_dev, named.st_ino) != (current.st_dev, current.st_ino)
        or current.st_uid != os.geteuid()
    ):
        _fail(code, 4 if partial else 3, classification="unavailable")


def _open_dir_at(
    parent_fd: int,
    name: str,
    display_path: Path,
    *,
    create: bool,
    partial: bool,
    allowed_modes: tuple[int, ...] = (0o700,),
) -> tuple[DirPin, bool]:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in {".", ".."}:
        _fail("lifecycle-name", 4 if partial else 3)
    created = False
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(name, flags, dir_fd=parent_fd)
    except FileNotFoundError:
        if not create:
            raise
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
            _sync_fd(parent_fd, "directory-parent-sync", partial=partial)
            fd = os.open(name, flags, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            _fail("lifecycle-path-race", 4 if partial else 3, classification="unavailable")
        except OSError:
            _fail("lifecycle-path", 4 if partial else 3, classification="unavailable")
    except OSError:
        _fail("lifecycle-path", 4 if partial else 3, classification="unavailable")
    item = os.fstat(fd)
    if (
        not stat.S_ISDIR(item.st_mode)
        or item.st_uid != os.geteuid()
        or stat.S_IMODE(item.st_mode) not in allowed_modes
    ):
        os.close(fd)
        _fail("lifecycle-path-conflict", 4 if partial else 3)
    return DirPin(
        fd,
        _dir_identity(item),
        display_path / name,
        parent_fd,
        name,
    ), created


def _create_dir_exclusive_at(
    parent: DirPin,
    name: str,
    *,
    partial: bool,
) -> DirPin:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in {".", ".."}:
        _fail("lifecycle-name", 4 if partial else 3)
    try:
        os.mkdir(name, 0o700, dir_fd=parent.fd)
    except FileExistsError:
        _fail("foreign-stage", 4 if partial else 3)
    except OSError:
        _fail("stage-create", 4 if partial else 3, classification="unavailable")
    _sync_fd(parent.fd, "stage-parent-sync", partial=partial)
    pin, created = _open_dir_at(
        parent.fd,
        name,
        parent.display_path,
        create=False,
        partial=partial,
    )
    if created:
        pin.close()
        _fail("stage-create", 4 if partial else 3, classification="unavailable")
    return pin


def _open_chain(
    root: RootPin | DirPin,
    parts: Sequence[str],
    *,
    create: bool,
    partial: bool,
) -> tuple[list[DirPin], bool]:
    pins: list[DirPin] = []
    parent_fd = root.fd
    display = root.path if isinstance(root, RootPin) else root.display_path
    any_created = False
    try:
        for part in parts:
            pin, created = _open_dir_at(parent_fd, part, display, create=create, partial=partial)
            pins.append(pin)
            parent_fd = pin.fd
            display = pin.display_path
            any_created = any_created or created
        return pins, any_created
    except Exception:
        for pin in reversed(pins):
            pin.close()
        raise


def _optional_chain(root: RootPin | DirPin, parts: Sequence[str]) -> list[DirPin] | None:
    try:
        pins, _created = _open_chain(root, parts, create=False, partial=False)
        return pins
    except FileNotFoundError:
        return None


def _close_pins(pins: Sequence[DirPin] | None) -> None:
    if pins is not None:
        for pin in reversed(pins):
            pin.close()


def _fd_path(fd: int) -> Path:
    return Path(f"/proc/self/fd/{fd}")


def _stat_at(parent: DirPin, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        _fail("lifecycle-stat", 3)


def _read_at(
    parent: DirPin,
    name: str,
    limit: int,
    code: str,
    *,
    partial: bool,
    allowed_modes: tuple[int, ...] = (0o600,),
) -> bytes:
    fd = None
    try:
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), dir_fd=parent.fd)
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) not in allowed_modes
            or before.st_size <= 0
            or before.st_size > limit
        ):
            _fail(code, 4 if partial else 3)
        chunks: list[bytes] = []
        total = 0
        while chunk := os.read(fd, min(1024 * 1024, limit + 1 - total)):
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                _fail(code, 4 if partial else 3)
        if _identity(os.fstat(fd)) != _identity(before):
            _fail(f"{code}-race", 4 if partial else 3, classification="unavailable")
        _recheck_dir(parent, f"{code}-parent-race", partial=partial)
        return b"".join(chunks)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail(code, 4 if partial else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)
    raise AssertionError("unreachable")


def _read_root_at(
    root: RootPin,
    name: str,
    limit: int,
    code: str,
    *,
    partial: bool,
) -> bytes:
    fd: int | None = None
    try:
        fd = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=root.fd,
        )
        before = os.fstat(fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_size <= 0
            or before.st_size > limit
        ):
            _fail(code, 4 if partial else 3, classification="unavailable")
        chunks: list[bytes] = []
        total = 0
        while True:
            allowance = limit + 1 - total
            if allowance <= 0:
                _fail(code, 4 if partial else 3, classification="unavailable")
            chunk = os.read(fd, min(1024 * 1024, allowance))
            if not chunk:
                break
            chunks.append(chunk); total += len(chunk)
        named = os.stat(name, dir_fd=root.fd, follow_symlinks=False)
        if (
            total != before.st_size
            or _identity(os.fstat(fd)) != _identity(before)
            or _identity(named) != _identity(before)
        ):
            _fail(f"{code}-race", 4 if partial else 3, classification="unavailable")
        _recheck_root(root, "xdg-state-home")
        return b"".join(chunks)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail(code, 4 if partial else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)
    raise AssertionError("unreachable")


def _sync_existing_at(parent: DirPin, name: str, *, partial: bool) -> None:
    fd: int | None = None
    try:
        fd = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent.fd,
        )
        before = os.fstat(fd)
        named = os.stat(name, dir_fd=parent.fd, follow_symlinks=False)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.geteuid()
            or stat.S_IMODE(before.st_mode) != 0o600
            or _identity(named) != _identity(before)
        ):
            _fail("receipt-existing", 4 if partial else 3, classification="unavailable")
        os.fsync(fd)
        _recheck_dir(parent, "receipt-parent-race", partial=partial)
        _sync_fd(parent.fd, "receipt-parent-sync", partial=partial)
        if _identity(os.fstat(fd)) != _identity(before):
            _fail("receipt-existing", 4 if partial else 3, classification="unavailable")
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("receipt-existing", 4 if partial else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)


def _receipt_checkpoint(point: str) -> None:
    if _TEST_RECEIPT_HOOK is not None:
        _TEST_RECEIPT_HOOK(point)


def _write_no_replace_at(
    parent: DirPin,
    name: str,
    raw: bytes,
    *,
    partial: bool,
    hook_prefix: str | None = None,
) -> None:
    fd = None
    if hook_prefix is not None:
        _receipt_checkpoint(f"{hook_prefix}-before-create")
    try:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=parent.fd,
        )
        if hook_prefix is not None:
            _receipt_checkpoint(f"{hook_prefix}-after-create")
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            offset += written
        if hook_prefix is not None:
            _receipt_checkpoint(f"{hook_prefix}-after-write")
        os.fsync(fd)
        if hook_prefix is not None:
            _receipt_checkpoint(f"{hook_prefix}-after-file-fsync")
        _recheck_dir(parent, "write-parent-race", partial=partial)
        _sync_fd(parent.fd, "write-parent-sync", partial=partial)
        if hook_prefix is not None:
            _receipt_checkpoint(f"{hook_prefix}-after-parent-fsync")
    except FileExistsError:
        _fail("no-replace-conflict", 4 if partial else 3)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("durable-write", 4 if partial else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)


def _replace_at(parent: DirPin, temp_name: str, final_name: str, raw: bytes, *, partial: bool) -> None:
    _write_no_replace_at(parent, temp_name, raw, partial=partial)
    try:
        os.rename(temp_name, final_name, src_dir_fd=parent.fd, dst_dir_fd=parent.fd)
        _recheck_dir(parent, "replace-parent-race", partial=partial)
        _sync_fd(parent.fd, "replace-parent-sync", partial=partial)
    except OSError:
        _fail("replace-unknown", 4 if partial else 3, classification="unavailable")


def _rename_noreplace_at(source: DirPin, source_name: str, destination: DirPin, destination_name: str, *, partial: bool) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(
        SYS_RENAMEAT2_X86_64,
        source.fd,
        os.fsencode(source_name),
        destination.fd,
        os.fsencode(destination_name),
        RENAME_NOREPLACE,
    )
    if result != 0:
        error = ctypes.get_errno()
        if error in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}:
            _fail("renameat2-unavailable", 4 if partial else 3)
        if error == errno.EEXIST:
            _fail("publish-conflict", 4 if partial else 3)
        _fail("publish-unknown", 4 if partial else 3, classification="unavailable")
    _recheck_dir(source, "rename-source-race", partial=partial)
    _recheck_dir(destination, "rename-destination-race", partial=partial)
    _sync_fd(source.fd, "rename-source-sync", partial=partial)
    if source.fd != destination.fd:
        _sync_fd(destination.fd, "rename-destination-sync", partial=partial)


def _copy_fd_at(source_fd: int, expected: os.stat_result, destination: DirPin, name: str) -> None:
    fd = None
    try:
        fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=destination.fd,
        )
        os.lseek(source_fd, 0, os.SEEK_SET)
        total = 0
        while chunk := os.read(source_fd, 1024 * 1024):
            total += len(chunk)
            offset = 0
            while offset < len(chunk):
                written = os.write(fd, chunk[offset:])
                if written <= 0:
                    raise OSError(errno.EIO, "short write")
                offset += written
        if total != expected.st_size or _identity(os.fstat(source_fd)) != _identity(expected):
            _fail("archive-mutated", 4, classification="unavailable")
        os.fsync(fd)
        _recheck_dir(destination, "stage-copy-race", partial=True)
        _sync_fd(destination.fd, "stage-copy-sync", partial=True)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("stage-write", 4, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)


def _purge_owned_stage_directory(directory: DirPin) -> None:
    """Remove only the descriptor-pinned private admission scratch tree."""
    try:
        names = os.listdir(directory.fd)
    except OSError:
        _fail("stage-private-cleanup", 4, classification="unavailable")
    for name in names:
        try:
            item = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            if stat.S_ISDIR(item.st_mode):
                child, _created = _open_dir_at(
                    directory.fd,
                    name,
                    directory.display_path,
                    create=False,
                    partial=True,
                    allowed_modes=(0o700, 0o755),
                )
                try:
                    _purge_owned_stage_directory(child)
                finally:
                    child.close()
                os.rmdir(name, dir_fd=directory.fd)
            else:
                os.unlink(name, dir_fd=directory.fd)
        except AcquisitionFailure:
            raise
        except OSError:
            _fail("stage-private-cleanup", 4, classification="unavailable")
    _sync_fd(directory.fd, "stage-private-sync", partial=True)


class _StatxTimestamp(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_int64), ("tv_nsec", ctypes.c_uint32), ("reserved", ctypes.c_int32)]


class _Statx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint32), ("stx_blksize", ctypes.c_uint32),
        ("stx_attributes", ctypes.c_uint64), ("stx_nlink", ctypes.c_uint32),
        ("stx_uid", ctypes.c_uint32), ("stx_gid", ctypes.c_uint32),
        ("stx_mode", ctypes.c_uint16), ("spare0", ctypes.c_uint16),
        ("stx_ino", ctypes.c_uint64), ("stx_size", ctypes.c_uint64),
        ("stx_blocks", ctypes.c_uint64), ("stx_attributes_mask", ctypes.c_uint64),
        ("stx_atime", _StatxTimestamp), ("stx_btime", _StatxTimestamp),
        ("stx_ctime", _StatxTimestamp), ("stx_mtime", _StatxTimestamp),
        ("stx_rdev_major", ctypes.c_uint32), ("stx_rdev_minor", ctypes.c_uint32),
        ("stx_dev_major", ctypes.c_uint32), ("stx_dev_minor", ctypes.c_uint32),
        ("stx_mnt_id", ctypes.c_uint64), ("stx_dio_mem_align", ctypes.c_uint32),
        ("stx_dio_offset_align", ctypes.c_uint32), ("spare3", ctypes.c_uint64 * 12),
    ]


def _fail(code: str, exit_code: int = 3, **evidence: object) -> None:
    raise AcquisitionFailure(code, exit_code, **evidence)


def _canonical(value: object) -> bytes:
    try:
        return (json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("ascii")
    except (TypeError, ValueError, UnicodeError):
        _fail("json-noncanonical", 2)
    raise AssertionError("unreachable")


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _seal(record: dict[str, object]) -> bytes:
    record.pop("record_sha256", None)
    record["record_sha256"] = _sha_bytes(_canonical(record))
    return _canonical(record)


def _strict_object(raw: bytes, limit: int, code: str) -> dict[str, object]:
    if not raw or len(raw) > limit:
        _fail(code, 2)
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                _fail("json-duplicate", 2)
            result[key] = value
        return result
    def nonfinite(_value: str) -> object:
        _fail("json-nonfinite", 2)
        raise AssertionError
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=pairs, parse_constant=nonfinite)
    except AcquisitionFailure:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        _fail(code, 2)
    if not isinstance(value, dict) or raw != _canonical(value):
        _fail("json-noncanonical", 2)
    return value


def _strict_state_object(
    raw: bytes, limit: int, code: str, *, partial: bool
) -> dict[str, object]:
    try:
        return _strict_object(raw, limit, code)
    except AcquisitionFailure:
        _fail(code, 4 if partial else 3, classification="unavailable")
    raise AssertionError("unreachable")


def _load_validator(script_root: Path):
    path = script_root / "scripts" / "validate_bundle.py"
    name = "_release_candidate_acquisition_validator"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    yaml_stub = False
    if "yaml" not in sys.modules:
        try:
            __import__("yaml")
        except ModuleNotFoundError:
            sys.modules["yaml"] = types.ModuleType("yaml")
            yaml_stub = True
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            _fail("validator-unavailable", 3)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    except (OSError, ImportError, AttributeError):
        sys.modules.pop(name, None)
        _fail("validator-unavailable", 3)
    finally:
        if yaml_stub:
            sys.modules.pop("yaml", None)


def _load_policy(candidate) -> tuple[dict[str, object], object, Path]:
    root = candidate.source_root_for_script()
    path = root / "policy" / POLICY_NAME
    try:
        raw = path.read_bytes()
    except OSError:
        _fail("policy-unavailable", 3)
    policy = _strict_object(raw, 2 * 1024 * 1024, "policy-invalid")
    validator = _load_validator(root)
    if (
        policy.get("schema_version") != POLICY_SCHEMA
        or _sha_bytes(raw) != validator.RELEASE_CANDIDATE_ACQUISITION_POLICY_SHA256
    ):
        _fail("policy-identity", 3)
    result = validator.Validation()
    validator.validate_release_candidate_acquisition_policy(root, result)
    if result.errors:
        _fail("policy-invalid", 3)
    return policy, validator, root


def _record_errors(validator, kind: str, raw: bytes, policy: dict[str, object], **context: object) -> list[str]:
    return validator.validate_release_candidate_acquisition_record(kind, raw, policy, **context)


def _external_checkpoint(point: str, code: str, path: Path, fd: int) -> None:
    if _TEST_EXTERNAL_RACE_HOOK is not None:
        _TEST_EXTERNAL_RACE_HOOK(f"{point}:{code}", path, fd)


def _recheck_external_file(pin: ExternalFilePin, code: str) -> None:
    try:
        current = os.fstat(pin.fd)
        named = os.stat(pin.name, dir_fd=pin.parent_fd, follow_symlinks=False)
        for ancestor in pin.ancestors:
            opened = os.fstat(ancestor.fd)
            routed = os.stat(
                ancestor.name,
                dir_fd=ancestor.parent_fd,
                follow_symlinks=False,
            )
            if (
                not stat.S_ISDIR(opened.st_mode)
                or not stat.S_ISDIR(routed.st_mode)
                or _dir_identity(opened) != ancestor.identity
                or (routed.st_dev, routed.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                _fail(f"{code}-race", 2)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail(f"{code}-race", 2)
    if (
        _identity(current) != pin.identity
        or _identity(named) != pin.identity
        or not stat.S_ISREG(current.st_mode)
    ):
        _fail(f"{code}-race", 2)


def _open_external_file(
    path: Path,
    limit: int,
    code: str,
    *,
    allowed_modes: tuple[int, ...] = (0o400, 0o600),
) -> ExternalFilePin:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or str(path) != os.path.normpath(str(path))
        or path.name in {"", ".", ".."}
    ):
        _fail(code, 2)
    root_fd: int | None = None
    ancestors: list[DirPin] = []
    fd: int | None = None
    try:
        directory_flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        root_fd = os.open(path.anchor, directory_flags)
        parent_fd = root_fd
        display = Path(path.anchor)
        for part in path.parts[1:-1]:
            if part in {"", ".", ".."}:
                _fail(code, 2)
            named = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
            child_fd = os.open(part, directory_flags, dir_fd=parent_fd)
            opened = os.fstat(child_fd)
            if (
                not stat.S_ISDIR(named.st_mode)
                or not stat.S_ISDIR(opened.st_mode)
                or (named.st_dev, named.st_ino) != (opened.st_dev, opened.st_ino)
            ):
                os.close(child_fd)
                _fail(f"{code}-race", 2)
            pin = DirPin(
                child_fd,
                _dir_identity(opened),
                display / part,
                parent_fd,
                part,
            )
            ancestors.append(pin)
            parent_fd = child_fd
            display = pin.display_path
        fd = os.open(
            path.name,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        _external_checkpoint("external-after-open", code, path, fd)
        item = os.fstat(fd)
        if (
            not stat.S_ISREG(item.st_mode)
            or item.st_uid != os.geteuid()
            or stat.S_IMODE(item.st_mode) not in allowed_modes
            or item.st_size <= 0
            or item.st_size > limit
        ):
            _fail(code, 2)
        pin = ExternalFilePin(
            path,
            fd,
            _identity(item),
            item,
            parent_fd,
            path.name,
            ancestors,
            root_fd,
        )
        fd = None
        root_fd = None
        ancestors = []
        _external_checkpoint("external-after-stat", code, path, pin.fd)
        _recheck_external_file(pin, code)
        return pin
    except AcquisitionFailure:
        raise
    except OSError:
        _fail(code, 2)
    finally:
        if fd is not None:
            os.close(fd)
        _close_pins(ancestors)
        if root_fd is not None:
            os.close(root_fd)
    raise AssertionError("unreachable")


def _read_external_bytes(pin: ExternalFilePin, limit: int, code: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    try:
        os.lseek(pin.fd, 0, os.SEEK_SET)
        while True:
            allowance = limit + 1 - total
            if allowance <= 0:
                _fail(code, 2)
            chunk = os.read(pin.fd, min(1024 * 1024, allowance))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total != pin.item.st_size:
            _fail(f"{code}-race", 2)
        _external_checkpoint("external-after-read", code, pin.path, pin.fd)
        _recheck_external_file(pin, code)
        os.lseek(pin.fd, 0, os.SEEK_SET)
        return b"".join(chunks)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail(code, 2)
    raise AssertionError("unreachable")


def _absolute_physical(path: Path, *, regular: bool | None, code: str) -> tuple[Path, os.stat_result]:
    if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
        _fail(code, 2)
    try:
        resolved = path.resolve(strict=True)
        item = path.lstat()
    except OSError:
        _fail(code, 2)
    if resolved != path or stat.S_ISLNK(item.st_mode):
        _fail(code, 2)
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            if current.is_symlink():
                _fail(code, 2)
        except OSError:
            _fail(code, 2)
    if regular is True and not stat.S_ISREG(item.st_mode):
        _fail(code, 2)
    if regular is False and not stat.S_ISDIR(item.st_mode):
        _fail(code, 2)
    return path, item


def _statx_fd(fd: int) -> tuple[int, int]:
    libc = ctypes.CDLL(None, use_errno=True)
    value = _Statx()
    result = libc.syscall(SYS_STATX_X86_64, fd, ctypes.c_char_p(b""), AT_EMPTY_PATH, STATX_BASIC_STATS | STATX_BTIME, ctypes.byref(value))
    if result != 0 or not value.stx_mask & STATX_BTIME:
        _fail("statx-unavailable", 3)
    return int(value.stx_btime.tv_sec), int(value.stx_btime.tv_nsec)


def _root_pin(path: Path, code: str) -> RootPin:
    admitted, item = _absolute_physical(path, regular=False, code=code)
    if item.st_uid != os.geteuid() or stat.S_IMODE(item.st_mode) != 0o700:
        _fail(f"{code}-owner-mode", 3)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(admitted, flags)
        opened = os.fstat(fd)
    except OSError:
        _fail(code, 3)
    if (item.st_dev, item.st_ino, item.st_uid, stat.S_IMODE(item.st_mode)) != (opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode)):
        os.close(fd)
        _fail(f"{code}-race", 3)
    bsec, bnsec = _statx_fd(fd)
    identity = (opened.st_dev, opened.st_ino, opened.st_uid, stat.S_IMODE(opened.st_mode), bsec, bnsec)
    digest = _sha_bytes(_canonical({"birth_seconds": bsec, "birth_nanoseconds": bnsec, "device": opened.st_dev, "inode": opened.st_ino, "mode": stat.S_IMODE(opened.st_mode), "uid": opened.st_uid}))
    return RootPin(admitted, fd, identity, digest)


def _recheck_root(pin: RootPin, code: str) -> None:
    try:
        current = os.fstat(pin.fd)
        named = os.stat(pin.path, follow_symlinks=False)
        bsec, bnsec = _statx_fd(pin.fd)
    except OSError:
        _fail(f"{code}-race", 3)
    identity = (current.st_dev, current.st_ino, current.st_uid, stat.S_IMODE(current.st_mode), bsec, bnsec)
    if (
        identity != pin.identity
        or not stat.S_ISDIR(named.st_mode)
        or (named.st_dev, named.st_ino) != identity[:2]
    ):
        _fail(f"{code}-race", 3)


def _archive_pin(path: Path, limit: int) -> tuple[ExternalFilePin, str]:
    pin = _open_external_file(
        path,
        limit,
        "archive-path",
        allowed_modes=(0o400, 0o600, 0o644),
    )
    digest = hashlib.sha256()
    total = 0
    try:
        while chunk := os.read(pin.fd, min(1024 * 1024, limit + 1 - total)):
            total += len(chunk)
            if total > limit:
                _fail("archive-path", 2)
            digest.update(chunk)
        if total != pin.item.st_size:
            _fail("archive-mutated", 3)
        _external_checkpoint("external-after-read", "archive-path", path, pin.fd)
        _recheck_external_file(pin, "archive-path")
        os.lseek(pin.fd, 0, os.SEEK_SET)
        return pin, digest.hexdigest()
    except Exception:
        pin.close()
        raise


def _identity(item: os.stat_result) -> tuple[int, int, int, int, int]:
    return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns


def _trust_root(path: Path, candidate, source_root: Path, *, structural: bool = False) -> tuple[Path, str]:
    expected = source_root / "policy" / "release-candidate.v1.json"
    pin = _open_external_file(
        path,
        2 * 1024 * 1024,
        "trust-root",
        allowed_modes=(0o400, 0o600, 0o644),
    )
    if path != expected.resolve(strict=True):
        pin.close()
        _fail("trust-root", 3)
    try:
        raw = _read_external_bytes(pin, 2 * 1024 * 1024, "trust-root")
        expected_raw = raw
        if structural:
            snapshot = candidate.admit_source(source_root)
            _policy, expected_raw = candidate._policy_from_snapshot(snapshot)
    except (OSError, candidate.CandidateError):
        _fail("trust-root", 3)
    finally:
        pin.close()
    if raw != expected_raw:
        _fail("trust-root", 3)
    return path, _sha_bytes(raw)


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _effects_sha() -> str:
    return _sha_bytes(_canonical(EFFECTS))


def _operation_for_plan(plan_sha: str) -> str:
    return "op-" + plan_sha[:32]


def _locator(operation: str, journal_sha256: str) -> str:
    value = f"journal:v1:{operation}:{journal_sha256}"
    if not re.fullmatch(r"journal:v1:op-[0-9a-f]{32}:[0-9a-f]{64}", value):
        _fail("journal-locator", 2)
    return value


def _locator_identity(value: str) -> tuple[str, str]:
    match = re.fullmatch(
        r"journal:v1:(op-[0-9a-f]{32}):([0-9a-f]{64})", value
        if isinstance(value, str) else ""
    )
    if match is None:
        _fail("journal-locator", 2)
    return match.group(1), match.group(2)


def _bootstrap_name(operation: str, grant_sha: str, nonce: str) -> str:
    name = (
        f".agentic-sdlc-acquisition-v1-{operation}-{grant_sha}-"
        f"{_sha_bytes(nonce.encode('ascii'))}.opened.json"
    )
    if BOOTSTRAP_RE.fullmatch(name) is None:
        _fail("grant-refused", 3)
    return name


def _bootstrap_entries(state: RootPin) -> list[tuple[str, re.Match[str]]]:
    try:
        names = os.listdir(state.fd)
    except OSError:
        _fail("bootstrap-state", 3, classification="unavailable")
    matches = [
        (name, match)
        for name in names
        if (match := BOOTSTRAP_RE.fullmatch(name)) is not None
    ]
    if len(matches) > 10000:
        _fail("bootstrap-state", 3)
    return matches


def _bootstrap_nonce_consumed(state: RootPin, nonce: str) -> bool:
    digest = _sha_bytes(nonce.encode("ascii"))
    return any(match.group(3) == digest for _name, match in _bootstrap_entries(state))


def _recovery_marker_name(operation: str, grant_sha: str, nonce: str) -> str:
    name = (
        f".agentic-sdlc-acquisition-recovery-v1-{operation}-{grant_sha}-"
        f"{_sha_bytes(nonce.encode('ascii'))}.used"
    )
    if RECOVERY_MARKER_RE.fullmatch(name) is None:
        _fail("grant-refused", 3)
    return name


def _root_recovery_consumed(state: RootPin, *, partial: bool) -> set[str]:
    try:
        names = os.listdir(state.fd)
    except OSError:
        _fail("grant-state", 4 if partial else 3, classification="unavailable")
    matches = [name for name in names if RECOVERY_MARKER_RE.fullmatch(name)]
    if len(matches) > 10000:
        _fail("grant-state", 4 if partial else 3)
    result: set[str] = set()
    for name in matches:
        raw = _read_root_at(
            state, name, 65536, "grant-state", partial=partial
        )
        record = _strict_state_object(
            raw, 65536, "grant-state", partial=partial
        )
        if set(record) != {"grant_sha256", "nonce", "operation_id"}:
            _fail("grant-state", 4 if partial else 3)
        nonce = record.get("nonce")
        if not isinstance(nonce, str):
            _fail("grant-state", 4 if partial else 3)
        result.add(nonce)
    return result


def _write_root_no_replace(
    root: RootPin,
    name: str,
    raw: bytes,
    *,
    partial: bool,
) -> None:
    fd: int | None = None
    try:
        fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=root.fd,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            offset += written
        os.fsync(fd)
        _sync_fd(root.fd, "grant-root-parent-sync", partial=partial)
        named = os.stat(name, dir_fd=root.fd, follow_symlinks=False)
        if _identity(named) != _identity(os.fstat(fd)):
            _fail("grant-state-race", 4 if partial else 3, classification="unavailable")
        _recheck_root(root, "xdg-state-home")
    except FileExistsError:
        _fail("grant-refused", 4 if partial else 3)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("grant-state", 4 if partial else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)


def _first_effect_checkpoint(
    point: str,
    *,
    effected: bool,
    operation: str,
    locator: str,
    exact_opened: bool = False,
) -> None:
    if _TEST_FIRST_EFFECT_HOOK is None:
        return
    try:
        _TEST_FIRST_EFFECT_HOOK(point)
    except Exception:
        raise AcquisitionFailure(
            "first-effect-fault",
            4 if effected else 3,
            operation,
            locator,
            "opened" if exact_opened else "absent",
            "exact" if exact_opened else "unavailable",
        ) from None


def _write_first_bootstrap(
    state: RootPin,
    name: str,
    raw: bytes,
    operation: str,
    locator: str,
) -> None:
    fd: int | None = None
    _first_effect_checkpoint(
        "first-before-create",
        effected=False,
        operation=operation,
        locator=locator,
    )
    try:
        fd = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=state.fd,
        )
        _first_effect_checkpoint(
            "first-after-create",
            effected=True,
            operation=operation,
            locator=locator,
        )
        offset = 0
        while offset < len(raw):
            written = os.write(fd, raw[offset:])
            if written <= 0:
                raise OSError(errno.EIO, "short write")
            offset += written
        _first_effect_checkpoint(
            "first-after-write",
            effected=True,
            operation=operation,
            locator=locator,
        )
        os.fsync(fd)
        _first_effect_checkpoint(
            "first-after-file-fsync",
            effected=True,
            operation=operation,
            locator=locator,
        )
        _sync_fd(state.fd, "bootstrap-parent-sync", partial=True)
        _first_effect_checkpoint(
            "first-after-parent-fsync",
            effected=True,
            operation=operation,
            locator=locator,
            exact_opened=True,
        )
        named = os.stat(name, dir_fd=state.fd, follow_symlinks=False)
        if _identity(named) != _identity(os.fstat(fd)):
            _fail("bootstrap-race", 4, classification="unavailable")
        _recheck_root(state, "xdg-state-home")
    except FileExistsError:
        _fail("grant-refused", 3)
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("bootstrap-write", 4 if fd is not None else 3, classification="unavailable")
    finally:
        if fd is not None:
            os.close(fd)


def _read_record(
    path: Path, limit: int, code: str
) -> tuple[bytes, dict[str, object], ExternalFilePin]:
    pin = _open_external_file(path, limit, code)
    try:
        raw = _read_external_bytes(pin, limit, code)
        return raw, _strict_object(raw, limit, code), pin
    except Exception:
        pin.close()
        raise


def _assessment(kind: str, classification: str, phase: str, operation_id: str, locator: str) -> bytes:
    if classification == "unavailable":
        effect = "unknown"
    else:
        effect = "none" if phase == "absent" else "complete" if phase == "installed-unselected" else "partial"
    next_action = ["acquire", "recover", "inspect", "--xdg-state-home", "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>"]
    if kind == "recover-inspect" and classification == "exact" and phase != "installed-unselected":
        next_action = ["acquire", "recover", "finish", "--xdg-state-home", "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>", "--grant", "<absolute-grant>"]
    record: dict[str, object] = {
        "assessment_kind": kind, "classification": classification, "effect_state": effect,
        "journal_locator": locator, "last_proven_phase": phase, "next_action": next_action,
        "operation_id": operation_id, "record_sha256": "", "schema_version": "release-candidate-acquisition-assessment/v1",
    }
    return _seal(record)


def _diagnostic(failure: AcquisitionFailure) -> bytes:
    classification = failure.classification if failure.classification in {"exact", "unavailable"} else "unavailable"
    phase = failure.last_phase
    effect = "partial" if classification == "exact" and phase in PHASES[:-1] else "unknown"
    record: dict[str, object] = {
        "classification": classification, "effect_state": effect,
        "journal_locator": failure.journal_locator or "unavailable",
        "last_proven_phase": phase, "next_action": ["acquire", "recover", "inspect", "--xdg-state-home", "<absolute-xdg-state-home>", "--journal-locator", "<journal-locator>"],
        "operation_id": failure.operation_id or "op-00000000000000000000000000000000",
        "record_sha256": "", "schema_version": "release-candidate-acquisition-exit4-diagnostic/v1",
    }
    return _seal(record)


def plan(arguments, candidate, policy: dict[str, object], validator, source_root: Path) -> int:
    candidate._require_linux_x64()
    limits = policy["limits"]
    assert isinstance(limits, dict)
    archive_pin, archive_sha = _archive_pin(
        arguments.archive, int(limits["max_archive_bytes"])
    )
    data = state = None
    try:
        trust_path, trust_sha = _trust_root(arguments.trust_root, candidate, source_root)
        data = _root_pin(arguments.xdg_data_home, "xdg-data-home")
        state = _root_pin(arguments.xdg_state_home, "xdg-state-home")
        _recheck_root(data, "xdg-data-home")
        _recheck_root(state, "xdg-state-home")
        _recheck_external_file(archive_pin, "archive-path")
        if _identity(os.fstat(archive_pin.fd)) != archive_pin.identity:
            _fail("archive-mutated", 3)
        record: dict[str, object] = {
            "archive_absolute_path": str(arguments.archive), "archive_sha256": archive_sha,
            "archive_size_bytes": archive_pin.item.st_size, "created_at": _timestamp(),
            "effects_sha256": _effects_sha(), "planned_effects": list(EFFECTS), "record_sha256": "",
            "schema_version": "release-candidate-acquisition-plan/v1",
            "trust_root_absolute_path": str(trust_path), "trust_root_sha256": trust_sha,
            "xdg_data_home_absolute_path": str(data.path), "xdg_data_prestate_sha256": data.prestate_sha256,
            "xdg_state_home_absolute_path": str(state.path), "xdg_state_prestate_sha256": state.prestate_sha256,
        }
        raw = _seal(record)
        if _record_errors(validator, "acquisition_plan", raw, policy):
            _fail("plan-record", 1)
        sys.stdout.buffer.write(raw)
        return 0
    finally:
        archive_pin.close()
        if data is not None:
            data.close()
        if state is not None:
            state.close()


def _load_plan(
    path: Path, policy: dict[str, object], validator
) -> tuple[bytes, dict[str, object], ExternalFilePin]:
    limits = policy["limits"]
    assert isinstance(limits, dict)
    raw, record, pin = _read_record(
        path, int(limits["max_plan_bytes"]), "plan-input"
    )
    if _record_errors(validator, "acquisition_plan", raw, policy):
        pin.close()
        _fail("plan-input", 2)
    return raw, record, pin


def _plan_pins(record: Mapping[str, object]) -> tuple[RootPin, RootPin]:
    data = _root_pin(Path(str(record["xdg_data_home_absolute_path"])), "xdg-data-home")
    try:
        state = _root_pin(Path(str(record["xdg_state_home_absolute_path"])), "xdg-state-home")
    except Exception:
        data.close()
        raise
    if data.prestate_sha256 != record["xdg_data_prestate_sha256"] or state.prestate_sha256 != record["xdg_state_prestate_sha256"]:
        data.close(); state.close()
        _fail("xdg-prestate-mismatch", 3)
    return data, state


def inspect(arguments, candidate, policy: dict[str, object], validator, source_root: Path) -> int:
    candidate._require_linux_x64()
    raw, record, plan_pin = _load_plan(arguments.plan, policy, validator)
    plan_sha = _sha_bytes(raw)
    archive_pin, archive_sha = _archive_pin(
        Path(str(record["archive_absolute_path"])),
        int(policy["limits"]["max_archive_bytes"]),
    )
    data = state = None
    try:
        trust_path, trust_sha = _trust_root(Path(str(record["trust_root_absolute_path"])), candidate, source_root)
        data, state = _plan_pins(record)
        _recheck_external_file(plan_pin, "plan-input")
        if archive_sha != record["archive_sha256"] or archive_pin.item.st_size != record["archive_size_bytes"] or trust_sha != record["trust_root_sha256"] or str(trust_path) != record["trust_root_absolute_path"]:
            _fail("plan-evidence-mismatch", 3)
        installed, operation, journal_sha = _installed_exact(
            data, state, record, plan_sha, policy, validator, candidate
        )
        phase = "installed-unselected" if installed else "absent"
        sys.stdout.buffer.write(_assessment("inspect", "exact", phase, operation, _locator(operation, journal_sha)))
        return 0
    finally:
        archive_pin.close()
        plan_pin.close()
        if data is not None: data.close()
        if state is not None: state.close()










def _entry(operation: str, plan: Mapping[str, object], plan_sha: str, phase: str, sequence: int, previous: str | None, root_sha: str, interpreter_sha: str) -> dict[str, object]:
    record: dict[str, object] = {
        "allowed_effects": list(EFFECTS), "archive_absolute_path": plan["archive_absolute_path"],
        "archive_sha256": plan["archive_sha256"], "archive_size_bytes": plan["archive_size_bytes"],
        "candidate_root_sha256": root_sha, "effect_state": "complete" if phase == "installed-unselected" else "partial",
        "effects_sha256": plan["effects_sha256"], "interpreter_relative_path": INTERPRETER_RELATIVE,
        "interpreter_sha256": interpreter_sha, "operation_id": operation, "phase": phase,
        "plan_sha256": plan_sha, "previous_entry_sha256": previous, "record_sha256": "",
        "recorded_at": _timestamp(), "schema_version": "release-candidate-acquisition-journal-entry/v1", "sequence": sequence,
    }
    _seal(record)
    return record


def _journal(operation: str, plan: Mapping[str, object], plan_sha: str, entries: list[dict[str, object]]) -> bytes:
    record: dict[str, object] = {
        "allowed_effects": list(EFFECTS), "archive_absolute_path": plan["archive_absolute_path"],
        "archive_sha256": plan["archive_sha256"], "archive_size_bytes": plan["archive_size_bytes"],
        "effects_sha256": plan["effects_sha256"], "entries": entries, "operation_id": operation,
        "plan_sha256": plan_sha, "record_sha256": "", "schema_version": "release-candidate-acquisition-operation-journal/v1",
    }
    return _seal(record)




def _append_entry(
    operation: str,
    plan: Mapping[str, object],
    plan_sha: str,
    entries: list[dict[str, object]],
    phase: str,
    root_sha: str,
    interpreter_sha: str,
) -> bytes:
    previous = None if not entries else _sha_bytes(_canonical(entries[-1]))
    entries.append(
        _entry(
            operation,
            plan,
            plan_sha,
            phase,
            len(entries),
            previous,
            root_sha,
            interpreter_sha,
        )
    )
    return _journal(operation, plan, plan_sha, entries)


def _persist_journal_at(
    journals: DirPin,
    operation: str,
    raw: bytes,
    *,
    initial: bool,
    partial: bool,
) -> str:
    name = f"{operation}.json"
    if initial:
        _write_no_replace_at(journals, name, raw, partial=partial)
    else:
        _replace_at(journals, f".{operation}.journal.tmp", name, raw, partial=partial)
    return _locator(operation, _sha_bytes(raw))


def _planned_terminal_journals(
    operation: str,
    plan: Mapping[str, object],
    plan_sha: str,
    published_entries: list[dict[str, object]],
    root_sha: str,
    interpreter_sha: str,
    *,
    recorded_at: str | None = None,
) -> tuple[list[dict[str, object]], bytes, list[dict[str, object]], bytes]:
    receipted_entries = [dict(item) for item in published_entries]
    receipted_raw = _append_entry(
        operation,
        plan,
        plan_sha,
        receipted_entries,
        "receipted",
        root_sha,
        interpreter_sha,
    )
    if recorded_at is not None:
        receipted_entries[-1]["recorded_at"] = recorded_at
        _seal(receipted_entries[-1])
        receipted_raw = _journal(operation, plan, plan_sha, receipted_entries)
    terminal_entries = [dict(item) for item in receipted_entries]
    terminal_raw = _append_entry(
        operation,
        plan,
        plan_sha,
        terminal_entries,
        "installed-unselected",
        root_sha,
        interpreter_sha,
    )
    # Recovery can reconstruct the exact planned terminal entry from the receipted prefix.
    terminal_entries[-1]["recorded_at"] = receipted_entries[-1]["recorded_at"]
    _seal(terminal_entries[-1])
    terminal_raw = _journal(operation, plan, plan_sha, terminal_entries)
    return receipted_entries, receipted_raw, terminal_entries, terminal_raw


def _receipt_raw(
    *,
    archive_sha: str,
    candidate_root: Path,
    operation: str,
    plan_sha: str,
    terminal_raw: bytes,
    installed_at: str,
) -> bytes:
    receipt: dict[str, object] = {
        "activation": "absent",
        "archive_sha256": archive_sha,
        "candidate_root_absolute_physical_path": str(candidate_root),
        "effect_state": "complete",
        "installed_at": installed_at,
        "journal_sha256": _sha_bytes(terminal_raw),
        "operation_id": operation,
        "plan_sha256": plan_sha,
        "public_channel": None,
        "record_sha256": "",
        "release_claim": "none",
        "schema_version": "release-candidate-acquisition-receipt/v1",
        "selection": "absent",
        "support": "unsupported",
        "terminal_phase": "installed-unselected",
    }
    return _seal(receipt)


def _fault_after_phase(
    phase: str, operation: str, locator: str
) -> None:
    if _TEST_FAULT_HOOK is None:
        return
    try:
        _TEST_FAULT_HOOK(phase)
    except Exception:
        if phase == "installed-unselected":
            return
        raise AcquisitionFailure(
            "fault-injected", 4, operation, locator, phase, "exact"
        ) from None


def _race_checkpoint(name: str) -> None:
    if _TEST_RACE_HOOK is not None:
        _TEST_RACE_HOOK(name)




def _probe_renameat2() -> None:
    # Capability probes occur before journal/product effects but are themselves temporary writes,
    # so probe only the syscall ABI with invalid descriptors; EFAULT/ENOENT proves availability.
    libc = ctypes.CDLL(None, use_errno=True)
    result = libc.syscall(SYS_RENAMEAT2_X86_64, -1, ctypes.c_char_p(b"x"), -1, ctypes.c_char_p(b"y"), RENAME_NOREPLACE)
    if result == 0 or ctypes.get_errno() not in {errno.EBADF, errno.ENOENT}:
        _fail("renameat2-unavailable", 3)






def _tree_sha_fd(root: DirPin, *, partial: bool) -> str:
    inventory: list[dict[str, object]] = []

    def walk(directory: DirPin, prefix: str) -> None:
        _recheck_dir(directory, "tree-directory-race", partial=partial)
        try:
            names = sorted(os.listdir(directory.fd), key=lambda item: item.encode("utf-8"))
        except (OSError, UnicodeError):
            _fail("tree-read", 4 if partial else 3, classification="unavailable")
        for name in names:
            if not name or "/" in name or name in {".", ".."}:
                _fail("tree-name", 4 if partial else 3, classification="unavailable")
            relative = f"{prefix}/{name}" if prefix else name
            try:
                item = os.stat(name, dir_fd=directory.fd, follow_symlinks=False)
            except OSError:
                _fail("tree-race", 4 if partial else 3, classification="unavailable")
            if stat.S_ISREG(item.st_mode):
                fd = None
                try:
                    fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory.fd)
                    opened = os.fstat(fd)
                    digest = hashlib.sha256()
                    while chunk := os.read(fd, 1024 * 1024):
                        digest.update(chunk)
                    if _identity(opened) != _identity(os.fstat(fd)) or _identity(item) != _identity(opened):
                        _fail("tree-file-race", 4 if partial else 3, classification="unavailable")
                except AcquisitionFailure:
                    raise
                except OSError:
                    _fail("tree-file", 4 if partial else 3, classification="unavailable")
                finally:
                    if fd is not None:
                        os.close(fd)
                inventory.append({"mode": stat.S_IMODE(item.st_mode), "path": relative, "sha256": digest.hexdigest(), "type": "file"})
            elif stat.S_ISDIR(item.st_mode):
                child, _created = _open_dir_at(
                    directory.fd,
                    name,
                    directory.display_path,
                    create=False,
                    partial=partial,
                    allowed_modes=(0o700, 0o755),
                )
                try:
                    inventory.append({"mode": stat.S_IMODE(item.st_mode), "path": relative, "type": "dir"})
                    walk(child, relative)
                finally:
                    child.close()
            elif stat.S_ISLNK(item.st_mode):
                try:
                    target = os.readlink(name, dir_fd=directory.fd)
                except OSError:
                    _fail("tree-link-race", 4 if partial else 3, classification="unavailable")
                inventory.append({"path": relative, "target": target, "type": "symlink"})
            else:
                _fail("candidate-root-special", 4 if partial else 3, classification="unavailable")
        _recheck_dir(directory, "tree-directory-race", partial=partial)

    walk(root, "")
    return _sha_bytes(_canonical(inventory))


def _stage_candidate(stage: DirPin, archive_fd: int, archive_item: os.stat_result, plan: Mapping[str, object], candidate, source_root: Path) -> tuple[str, str]:
    _copy_fd_at(archive_fd, archive_item, stage, "candidate.tar.gz")
    private, _created = _open_dir_at(
        stage.fd, ".admission", stage.display_path, create=True, partial=True
    )
    snapshot = candidate.admit_source(source_root)
    host_policy, host_policy_raw = candidate._policy_from_snapshot(snapshot)
    archive = _fd_path(stage.fd) / "candidate.tar.gz"
    private_path = _fd_path(private.fd)
    raw = candidate._inflate_gzip(archive, private_path, int(host_policy["limits"]["max_uncompressed_bytes"]))
    manifest, members, manifest_raw = candidate._archive_admission(raw, Path(str(plan["archive_absolute_path"])).name, host_policy, host_policy_raw)
    extracted = candidate._manual_extract(raw, manifest, members, manifest_raw, host_policy, private_path)
    candidate._recompute_extracted(extracted, manifest)
    try:
        os.rename(
            extracted.name,
            "root",
            src_dir_fd=private.fd,
            dst_dir_fd=stage.fd,
        )
        _sync_fd(stage.fd, "stage-root-sync", partial=True)
        _purge_owned_stage_directory(private)
        private.close()
        os.rmdir(".admission", dir_fd=stage.fd)
        _sync_fd(stage.fd, "stage-clean-sync", partial=True)
        root, _created = _open_dir_at(
            stage.fd, "root", stage.display_path, create=False, partial=True,
            allowed_modes=(0o755,),
        )
        try:
            root_sha = _tree_sha_fd(root, partial=True)
            interpreter_sha = _candidate_file_sha(
                root, INTERPRETER_RELATIVE.split("/"), partial=True
            )
            return root_sha, interpreter_sha
        finally:
            root.close()
    finally:
        try:
            os.fstat(private.fd)
        except OSError:
            pass
        else:
            private.close()


def _authority(plan: Mapping[str, object], plan_sha: str, decision: str, operation: str, journal_path: Path | None = None, journal_sha: str | None = None) -> dict[str, object]:
    result: dict[str, object] = {
        "archive_absolute_path": plan["archive_absolute_path"], "archive_sha256": plan["archive_sha256"],
        "archive_size_bytes": plan["archive_size_bytes"], "decision": decision,
        "effects_sha256": plan["effects_sha256"], "operation_id": operation,
        "original_effects": list(EFFECTS), "plan_sha256": plan_sha,
        "trust_root_absolute_path": plan["trust_root_absolute_path"], "trust_root_sha256": plan["trust_root_sha256"],
        "xdg_data_home_absolute_path": plan["xdg_data_home_absolute_path"], "xdg_data_prestate_sha256": plan["xdg_data_prestate_sha256"],
        "xdg_state_home_absolute_path": plan["xdg_state_home_absolute_path"], "xdg_state_prestate_sha256": plan["xdg_state_prestate_sha256"],
    }
    if journal_path is not None:
        result["journal_absolute_physical_path"] = str(journal_path)
        result["journal_sha256"] = journal_sha
    return result




def _read_consumed_at(grants: DirPin | None, *, partial: bool) -> set[str]:
    if grants is None:
        return set()
    result: set[str] = set()
    try:
        names = os.listdir(grants.fd)
    except OSError:
        _fail("grant-state", 4 if partial else 3, classification="unavailable")
    if len(names) > 10000:
        _fail("grant-state", 4 if partial else 3)
    for name in names:
        if not re.fullmatch(r"[0-9a-f]{64}\.used", name):
            _fail("grant-state", 4 if partial else 3)
        raw = _read_at(grants, name, 65536, "grant-state", partial=partial)
        value = _strict_object(raw, 65536, "grant-state")
        if set(value) != {"grant_sha256", "nonce", "operation_id"}:
            _fail("grant-state", 4 if partial else 3)
        nonce = value.get("nonce")
        if not isinstance(nonce, str):
            _fail("grant-state", 4 if partial else 3)
        result.add(nonce)
    return result


def _foreign_stage_present(data: RootPin, operation: str) -> bool:
    chain = _optional_chain(
        data, ["agentic-sdlc", "acquisition", "staging"]
    )
    if chain is None:
        return False
    try:
        return _stat_at(chain[-1], operation) is not None
    finally:
        _close_pins(chain)


def _candidate_file_sha(
    root: DirPin, relative: Sequence[str], *, partial: bool
) -> str:
    directories = list(relative[:-1])
    pins: list[DirPin] = []
    parent = root
    try:
        for name in directories:
            pin, _created = _open_dir_at(
                parent.fd,
                name,
                parent.display_path,
                create=False,
                partial=partial,
                allowed_modes=(0o755,),
            )
            pins.append(pin)
            parent = pin
        raw = _read_at(
            parent,
            relative[-1],
            512 * 1024 * 1024,
            "candidate-file",
            partial=partial,
            allowed_modes=(0o644, 0o755),
        )
        return _sha_bytes(raw)
    finally:
        _close_pins(pins)


def _open_candidate_file_fd(
    root: DirPin,
    relative: Sequence[str],
    *,
    partial: bool,
    allowed_modes: tuple[int, ...],
) -> int:
    pins: list[DirPin] = []
    parent = root
    try:
        for name in relative[:-1]:
            pin, _created = _open_dir_at(
                parent.fd,
                name,
                parent.display_path,
                create=False,
                partial=partial,
                allowed_modes=(0o755,),
            )
            pins.append(pin); parent = pin
        fd = os.open(
            relative[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent.fd,
        )
        item = os.fstat(fd)
        if (
            not stat.S_ISREG(item.st_mode)
            or item.st_uid != os.geteuid()
            or stat.S_IMODE(item.st_mode) not in allowed_modes
        ):
            os.close(fd)
            _fail("candidate-file", 4 if partial else 3)
        return fd
    except AcquisitionFailure:
        raise
    except OSError:
        _fail("candidate-file", 4 if partial else 3, classification="unavailable")
    finally:
        _close_pins(pins)
    raise AssertionError("unreachable")


def _installed_exact(
    data: RootPin,
    state: RootPin,
    plan: Mapping[str, object],
    plan_sha: str,
    policy: dict[str, object],
    validator,
    candidate,
) -> tuple[bool, str, str]:
    state_receipts = _optional_chain(state, ["agentic-sdlc", "acquisition", "receipts"])
    state_journals = _optional_chain(state, ["agentic-sdlc", "acquisition", "journals"])
    data_candidates = _optional_chain(data, ["agentic-sdlc", "acquisition", "candidates"])
    try:
        receipt_name = f"{plan['archive_sha256']}.json"
        receipt_present = state_receipts is not None and _stat_at(state_receipts[-1], receipt_name) is not None
        candidate_present = data_candidates is not None and _stat_at(data_candidates[-1], str(plan["archive_sha256"])) is not None
        if not receipt_present and not candidate_present:
            return False, _operation_for_plan(plan_sha), ZERO_SHA
        if not receipt_present or not candidate_present or state_journals is None:
            _fail("installed-conflict", 3)
        assert state_receipts is not None and data_candidates is not None
        receipt_raw = _read_at(
            state_receipts[-1], receipt_name, int(policy["limits"]["max_receipt_bytes"]),
            "receipt-conflict", partial=False,
        )
        receipt = _strict_state_object(receipt_raw, int(policy["limits"]["max_receipt_bytes"]), "receipt-conflict", partial=False)
        if _record_errors(validator, "immutable_receipt", receipt_raw, policy):
            _fail("receipt-conflict", 3)
        operation = str(receipt.get("operation_id"))
        journal_raw = _read_at(
            state_journals[-1], f"{operation}.json", int(policy["limits"]["max_journal_bytes"]),
            "journal-conflict", partial=False,
        )
        journal = _strict_state_object(journal_raw, int(policy["limits"]["max_journal_bytes"]), "journal-conflict", partial=False)
        if (
            _record_errors(validator, "operation_journal", journal_raw, policy)
            or _sha_bytes(journal_raw) != receipt.get("journal_sha256")
            or journal.get("operation_id") != operation
            or journal.get("plan_sha256") != plan_sha
            or journal.get("archive_sha256") != plan["archive_sha256"]
        ):
            _fail("journal-conflict", 3)
        entries = journal.get("entries")
        if not isinstance(entries, list) or not entries or entries[-1].get("phase") != "installed-unselected":
            _fail("journal-incomplete", 3)
        terminal = entries[-1]
        if (
            receipt.get("archive_sha256") != plan["archive_sha256"]
            or receipt.get("plan_sha256") != plan_sha
            or receipt.get("candidate_root_absolute_physical_path")
            != str(data.path / "agentic-sdlc" / "acquisition" / "candidates" / str(plan["archive_sha256"]) / "root")
        ):
            _fail("receipt-conflict", 3)
        container, _created = _open_dir_at(
            data_candidates[-1].fd,
            str(plan["archive_sha256"]),
            data_candidates[-1].display_path,
            create=False,
            partial=False,
        )
        try:
            archive_raw = _read_at(
                container, "candidate.tar.gz", int(policy["limits"]["max_archive_bytes"]),
                "installed-archive", partial=False,
            )
            if _sha_bytes(archive_raw) != plan["archive_sha256"]:
                _fail("installed-archive", 3)
            root, _created = _open_dir_at(
                container.fd, "root", container.display_path, create=False,
                partial=False, allowed_modes=(0o755,),
            )
            try:
                root_sha = _tree_sha_fd(root, partial=False)
                if root_sha != terminal.get("candidate_root_sha256"):
                    _fail("installed-root-modified", 3)
                interpreter_sha = _candidate_file_sha(
                    root, INTERPRETER_RELATIVE.split("/"), partial=False
                )
                if interpreter_sha != terminal.get("interpreter_sha256"):
                    _fail("installed-interpreter-modified", 3)
                manifest_raw = _read_at(
                    root, "manifest.json", 64 * 1024 * 1024, "installed-manifest",
                    partial=False, allowed_modes=(0o644,),
                )
                manifest = candidate.strict_json_object(manifest_raw, "installed-manifest")
                host_policy = candidate.load_policy(candidate.source_root_for_script() / "policy" / "release-candidate.v1.json")
                candidate.validate_manifest(manifest, host_policy)
                match = candidate.ARCHIVE_NAME.fullmatch(Path(str(plan["archive_absolute_path"])).name)
                if match is None or manifest.get("candidate_id") != match.group(1):
                    _fail("installed-candidate-identity", 3)
            finally:
                root.close()
        finally:
            container.close()
        return True, operation, _sha_bytes(journal_raw)
    finally:
        _close_pins(state_receipts)
        _close_pins(state_journals)
        _close_pins(data_candidates)


def _validate_grant(
    raw: bytes,
    grant: dict[str, object],
    kind: str,
    policy: dict[str, object],
    validator,
    authority: dict[str, object],
    consumed: set[str],
) -> None:
    errors = _record_errors(
        validator,
        kind,
        raw,
        policy,
        now_utc=_timestamp(),
        consumed_nonces=consumed,
        effective_uid=os.geteuid(),
        expected_authority=authority,
    )
    if errors:
        _fail("grant-refused", 3)


def _load_grant(
    path: Path,
    kind: str,
    policy: dict[str, object],
    validator,
    authority: dict[str, object],
    consumed: set[str],
) -> tuple[bytes, dict[str, object], ExternalFilePin]:
    limits = policy["limits"]
    assert isinstance(limits, dict)
    raw, grant, pin = _read_record(
        path, int(limits["max_grant_bytes"]), "grant-input"
    )
    try:
        _validate_grant(raw, grant, kind, policy, validator, authority, consumed)
    except Exception:
        pin.close()
        raise
    return raw, grant, pin




def apply_hardened(arguments, candidate, policy: dict[str, object], validator, source_root: Path) -> int:
    """Effect-free admission followed by descriptor-custodied journaled acquisition."""
    candidate._require_linux_x64()
    plan_raw, plan_record, plan_pin = _load_plan(
        arguments.plan, policy, validator
    )
    plan_sha = _sha_bytes(plan_raw)
    data, state = _plan_pins(plan_record)
    archive_pin: ExternalFilePin | None = None
    grant_pin: ExternalFilePin | None = None
    lock_fd: int | None = None
    opened: list[DirPin] = []
    operation = "op-00000000000000000000000000000000"
    locator = _locator(operation, ZERO_SHA)
    phase = "absent"
    effects_started = False
    try:
        _probe_renameat2()
        archive_pin, archive_sha = _archive_pin(
            Path(str(plan_record["archive_absolute_path"])),
            int(policy["limits"]["max_archive_bytes"]),
        )
        trust_path, trust_sha = _trust_root(
            Path(str(plan_record["trust_root_absolute_path"])),
            candidate,
            source_root,
            structural=True,
        )
        if (
            archive_sha != plan_record["archive_sha256"]
            or archive_pin.item.st_size != plan_record["archive_size_bytes"]
            or trust_sha != plan_record["trust_root_sha256"]
            or str(trust_path) != plan_record["trust_root_absolute_path"]
        ):
            _fail("plan-evidence-mismatch", 3)

        grant_raw, grant_preview, grant_pin = _read_record(
            arguments.grant, int(policy["limits"]["max_grant_bytes"]), "grant-input"
        )
        operation = str(grant_preview.get("operation_id", operation))
        if not re.fullmatch(r"op-[0-9a-f]{32}", operation):
            _fail("grant-refused", 3)
        locator = _locator(operation, ZERO_SHA)
        authority = _authority(plan_record, plan_sha, "apply", operation)
        # All schema, freshness, UID, root, archive, trust, effects and plan bindings are
        # admitted before any target directory or lock may be created.
        _validate_grant(
            grant_raw,
            grant_preview,
            "apply_grant",
            policy,
            validator,
            authority,
            set(),
        )
        installed, installed_operation, installed_journal_sha = _installed_exact(
            data, state, plan_record, plan_sha, policy, validator, candidate
        )
        if installed:
            sys.stdout.buffer.write(
                _assessment(
                    "inspect",
                    "exact",
                    "installed-unselected",
                    installed_operation,
                    _locator(installed_operation, installed_journal_sha),
                )
            )
            return 0
        nonce = str(grant_preview.get("nonce"))
        if _bootstrap_nonce_consumed(state, nonce):
            _fail("grant-refused", 3)
        if _foreign_stage_present(data, operation):
            _fail("foreign-stage", 3)

        # The already-existing explicit state-root descriptor is the writer lock.
        # flock has no namespace effect and serializes the final read-only admission
        # immediately before the first durable no-replace bootstrap.
        try:
            fcntl.flock(state.fd, fcntl.LOCK_EX)
        except OSError:
            _fail("writer-lock", 3, classification="unavailable")
        _recheck_root(data, "xdg-data-home")
        _recheck_root(state, "xdg-state-home")
        _recheck_external_file(plan_pin, "plan-input")
        _recheck_external_file(grant_pin, "grant-input")
        _recheck_external_file(archive_pin, "archive-path")
        if _identity(os.fstat(archive_pin.fd)) != archive_pin.identity:
            _fail("archive-mutated", 3, classification="unavailable")
        trust_path, trust_sha = _trust_root(
            Path(str(plan_record["trust_root_absolute_path"])),
            candidate,
            source_root,
            structural=True,
        )
        if (
            trust_sha != plan_record["trust_root_sha256"]
            or str(trust_path) != plan_record["trust_root_absolute_path"]
        ):
            _fail("plan-evidence-mismatch", 3)
        if _bootstrap_nonce_consumed(state, nonce):
            _fail("grant-refused", 3)
        if _foreign_stage_present(data, operation):
            _fail("foreign-stage", 3)
        _validate_grant(
            grant_raw,
            grant_preview,
            "apply_grant",
            policy,
            validator,
            authority,
            set(),
        )

        entries: list[dict[str, object]] = []
        journal_raw = _append_entry(
            operation, plan_record, plan_sha, entries, "opened", ZERO_SHA, ZERO_SHA
        )
        if _record_errors(validator, "operation_journal", journal_raw, policy):
            _fail("journal-record", 3, classification="unavailable")
        locator = _locator(operation, _sha_bytes(journal_raw))
        grant_sha = _sha_bytes(grant_raw)
        bootstrap_name = _bootstrap_name(operation, grant_sha, nonce)
        _write_first_bootstrap(
            state, bootstrap_name, journal_raw, operation, locator
        )
        effects_started = True
        phase = "opened"

        state_chain, _created = _open_chain(
            state,
            ["agentic-sdlc", "acquisition"],
            create=True,
            partial=True,
        )
        opened.extend(state_chain)
        state_root = state_chain[-1]
        journals, _created = _open_dir_at(
            state_root.fd,
            "journals",
            state_root.display_path,
            create=True,
            partial=True,
        )
        opened.append(journals)
        receipts, _created = _open_dir_at(
            state_root.fd,
            "receipts",
            state_root.display_path,
            create=True,
            partial=True,
        )
        opened.append(receipts)
        grants, _created = _open_dir_at(
            state_root.fd,
            "grants",
            state_root.display_path,
            create=True,
            partial=True,
        )
        opened.append(grants)
        _race_checkpoint("state-before-journal")
        _recheck_dir(state_root, "state-root-race", partial=True)
        _recheck_dir(journals, "journals-race", partial=True)
        _recheck_dir(receipts, "receipts-race", partial=True)
        _recheck_dir(grants, "grants-race", partial=True)
        locator = _persist_journal_at(
            journals, operation, journal_raw, initial=True, partial=True
        )
        _fault_after_phase(phase, operation, locator)
        _race_checkpoint("state-after-journal")
        _recheck_dir(journals, "journals-race", partial=True)

        data_chain, _created = _open_chain(
            data, ["agentic-sdlc", "acquisition"], create=True, partial=True
        )
        opened.extend(data_chain)
        data_root = data_chain[-1]
        staging, _created = _open_dir_at(
            data_root.fd,
            "staging",
            data_root.display_path,
            create=True,
            partial=True,
        )
        opened.append(staging)
        candidates, _created = _open_dir_at(
            data_root.fd,
            "candidates",
            data_root.display_path,
            create=True,
            partial=True,
        )
        opened.append(candidates)
        _race_checkpoint("data-after-journal")
        _recheck_dir(data_root, "data-root-race", partial=True)
        _recheck_dir(staging, "staging-race", partial=True)
        _recheck_dir(candidates, "candidates-race", partial=True)
        stage = _create_dir_exclusive_at(staging, operation, partial=True)
        opened.append(stage)
        root_sha, interpreter_sha = _stage_candidate(
            stage,
            archive_pin.fd,
            archive_pin.item,
            plan_record,
            candidate,
            source_root,
        )
        journal_raw = _append_entry(
            operation,
            plan_record,
            plan_sha,
            entries,
            "pinned",
            root_sha,
            interpreter_sha,
        )
        locator = _persist_journal_at(
            journals, operation, journal_raw, initial=False, partial=True
        )
        phase = "pinned"; _fault_after_phase(phase, operation, locator)
        journal_raw = _append_entry(
            operation,
            plan_record,
            plan_sha,
            entries,
            "staged",
            root_sha,
            interpreter_sha,
        )
        locator = _persist_journal_at(
            journals, operation, journal_raw, initial=False, partial=True
        )
        phase = "staged"; _fault_after_phase(phase, operation, locator)

        stage.close(); opened.remove(stage)
        _rename_noreplace_at(
            staging,
            operation,
            candidates,
            str(plan_record["archive_sha256"]),
            partial=True,
        )
        journal_raw = _append_entry(
            operation,
            plan_record,
            plan_sha,
            entries,
            "published",
            root_sha,
            interpreter_sha,
        )
        locator = _persist_journal_at(
            journals, operation, journal_raw, initial=False, partial=True
        )
        phase = "published"; _fault_after_phase(phase, operation, locator)

        receipt_time = _timestamp()
        receipted_entries, receipted_raw, terminal_entries, terminal_raw = (
            _planned_terminal_journals(
                operation,
                plan_record,
                plan_sha,
                entries,
                root_sha,
                interpreter_sha,
                recorded_at=receipt_time,
            )
        )
        receipt_raw = _receipt_raw(
            archive_sha=str(plan_record["archive_sha256"]),
            candidate_root=(
                data.path
                / "agentic-sdlc"
                / "acquisition"
                / "candidates"
                / str(plan_record["archive_sha256"])
                / "root"
            ),
            operation=operation,
            plan_sha=plan_sha,
            terminal_raw=terminal_raw,
            installed_at=receipt_time,
        )
        if _record_errors(validator, "immutable_receipt", receipt_raw, policy):
            _fail("receipt-record", 4, classification="unavailable")
        _write_no_replace_at(
            receipts,
            f"{plan_record['archive_sha256']}.json",
            receipt_raw,
            partial=True,
            hook_prefix="receipt",
        )
        _receipt_checkpoint("receipt-before-receipted")
        locator = _persist_journal_at(
            journals, operation, receipted_raw, initial=False, partial=True
        )
        phase = "receipted"; _fault_after_phase(phase, operation, locator)
        locator = _persist_journal_at(
            journals, operation, terminal_raw, initial=False, partial=True
        )
        phase = "installed-unselected"; _fault_after_phase(phase, operation, locator)
        sys.stdout.write(
            "action=acquire effect-state=complete "
            f"archive-sha256={plan_record['archive_sha256']} "
            f"operation-id={operation} journal-locator={locator} "
            f"receipt-locator=receipt:{plan_record['archive_sha256']}\n"
        )
        return 0
    except AcquisitionFailure as failure:
        if failure.exit_code == 4 or effects_started or phase != "absent":
            enriched = AcquisitionFailure(
                failure.code,
                4,
                failure.operation_id or operation,
                failure.journal_locator or locator,
                failure.last_phase if failure.last_phase != "absent" else phase,
                failure.classification,
            )
            sys.stderr.buffer.write(_diagnostic(enriched))
            return 4
        raise
    except Exception:
        if effects_started or phase != "absent":
            sys.stderr.buffer.write(
                _diagnostic(
                    AcquisitionFailure(
                        "internal", 4, operation, locator, phase, "unavailable"
                    )
                )
            )
            return 4
        raise
    finally:
        if archive_pin is not None:
            archive_pin.close()
        if grant_pin is not None:
            grant_pin.close()
        plan_pin.close()
        if lock_fd is not None:
            os.close(lock_fd)
        _close_pins(opened)
        data.close()
        state.close()




def _load_journal_at(
    state: RootPin,
    locator_value: str,
    policy: dict[str, object],
    validator,
    *,
    partial: bool,
) -> tuple[bytes, dict[str, object], str, Path]:
    operation, expected_sha = _locator_identity(locator_value)
    chain: list[DirPin] | None = None
    journal_path: Path
    try:
        try:
            chain = _open_chain(
                state,
                ["agentic-sdlc", "acquisition", "journals"],
                create=False,
                partial=partial,
            )[0]
        except FileNotFoundError:
            chain = None
        if chain is not None and _stat_at(chain[-1], f"{operation}.json") is not None:
            raw = _read_at(
                chain[-1],
                f"{operation}.json",
                int(policy["limits"]["max_journal_bytes"]),
                "journal-input",
                partial=partial,
            )
            journal_path = (
                state.path
                / "agentic-sdlc"
                / "acquisition"
                / "journals"
                / f"{operation}.json"
            )
        else:
            matches = [
                name
                for name, match in _bootstrap_entries(state)
                if match.group(1) == operation
            ]
            if len(matches) != 1:
                _fail(
                    "journal-unavailable",
                    4 if matches else (4 if partial else 3),
                    operation_id=operation,
                    journal_locator=locator_value,
                    classification="unavailable",
                )
            try:
                raw = _read_root_at(
                    state,
                    matches[0],
                    int(policy["limits"]["max_journal_bytes"]),
                    "journal-input",
                    partial=True,
                )
            except AcquisitionFailure as failure:
                raise AcquisitionFailure(
                    failure.code,
                    4,
                    operation,
                    locator_value,
                    "absent",
                    "unavailable",
                ) from None
            journal_path = state.path / matches[0]
        journal = _strict_state_object(
            raw,
            int(policy["limits"]["max_journal_bytes"]),
            "journal-input",
            partial=chain is None or partial,
        )
        if (
            _sha_bytes(raw) != expected_sha
            or journal.get("operation_id") != operation
            or _record_errors(validator, "operation_journal", raw, policy)
        ):
            _fail(
                "journal-unavailable",
                4 if chain is None or partial else 3,
                operation_id=operation,
                journal_locator=locator_value,
                classification="unavailable",
            )
        entries = journal.get("entries")
        if not isinstance(entries, list) or not entries:
            _fail("journal-unavailable", 4 if partial else 3)
        return raw, journal, str(entries[-1]["phase"]), journal_path
    finally:
        _close_pins(chain)


def _load_current_journal_at(
    state: RootPin,
    operation: str,
    policy: dict[str, object],
    validator,
) -> tuple[bytes, dict[str, object], str]:
    chain = _open_chain(
        state,
        ["agentic-sdlc", "acquisition", "journals"],
        create=False,
        partial=True,
    )[0]
    try:
        raw = _read_at(
            chain[-1],
            f"{operation}.json",
            int(policy["limits"]["max_journal_bytes"]),
            "journal-readback",
            partial=True,
        )
        journal = _strict_object(
            raw, int(policy["limits"]["max_journal_bytes"]), "journal-readback"
        )
        if (
            journal.get("operation_id") != operation
            or _record_errors(validator, "operation_journal", raw, policy)
        ):
            _fail("journal-readback", 4, classification="unavailable")
        entries = journal["entries"]
        assert isinstance(entries, list)
        return raw, journal, str(entries[-1]["phase"])
    finally:
        _close_pins(chain)


def _validate_acquired_root(
    root: DirPin,
    terminal: Mapping[str, object],
    candidate,
    *,
    partial: bool,
) -> tuple[str, str, str]:
    root_sha = _tree_sha_fd(root, partial=partial)
    if root_sha != terminal.get("candidate_root_sha256"):
        _fail("candidate-root-mismatch", 4 if partial else 3, classification="unavailable")
    interpreter_sha = _candidate_file_sha(
        root, INTERPRETER_RELATIVE.split("/"), partial=partial
    )
    if interpreter_sha != terminal.get("interpreter_sha256"):
        _fail("private-runtime-mismatch", 4 if partial else 3, classification="unavailable")
    manifest_raw = _read_at(
        root,
        "manifest.json",
        64 * 1024 * 1024,
        "candidate-manifest",
        partial=partial,
        allowed_modes=(0o644,),
    )
    manifest = candidate.strict_json_object(manifest_raw, "candidate-manifest")
    host_policy = candidate.load_policy(
        candidate.source_root_for_script() / "policy" / "release-candidate.v1.json"
    )
    try:
        candidate.validate_manifest(manifest, host_policy)
    except candidate.CandidateError:
        _fail("candidate-manifest", 4 if partial else 3, classification="unavailable")
    inventory = manifest.get("inventory")
    if not isinstance(inventory, list):
        _fail("candidate-manifest", 4 if partial else 3)
    index = {
        item.get("path"): item
        for item in inventory
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    identities: list[str] = []
    for relative in (
        "scripts/release_candidate.py",
        "scripts/release_candidate_acquisition.py",
    ):
        expected = index.get(relative)
        if not isinstance(expected, dict) or not isinstance(expected.get("sha256"), str):
            _fail("candidate-dispatch-identity", 4 if partial else 3)
        actual = _candidate_file_sha(root, relative.split("/"), partial=partial)
        if actual != expected["sha256"]:
            _fail("candidate-dispatch-identity", 4 if partial else 3, classification="unavailable")
        identities.append(actual)
    return interpreter_sha, identities[0], identities[1]


def _open_candidate_container(
    data: RootPin,
    operation: str,
    archive_sha: str,
    *,
    partial: bool,
) -> tuple[list[DirPin], DirPin, bool]:
    data_root = _open_chain(
        data, ["agentic-sdlc", "acquisition"], create=False, partial=partial
    )[0]
    pins = list(data_root)
    candidates, _created = _open_dir_at(
        data_root[-1].fd,
        "candidates",
        data_root[-1].display_path,
        create=False,
        partial=partial,
    )
    pins.append(candidates)
    candidate_item = _stat_at(candidates, archive_sha)
    if candidate_item is not None:
        container, _created = _open_dir_at(
            candidates.fd,
            archive_sha,
            candidates.display_path,
            create=False,
            partial=partial,
        )
        pins.append(container)
        return pins, container, True
    staging, _created = _open_dir_at(
        data_root[-1].fd,
        "staging",
        data_root[-1].display_path,
        create=False,
        partial=partial,
    )
    pins.append(staging)
    container, _created = _open_dir_at(
        staging.fd,
        operation,
        staging.display_path,
        create=False,
        partial=partial,
    )
    pins.append(container)
    return pins, container, False


def _recover_terminal_exact(
    state: RootPin,
    journal_raw: bytes,
    journal: Mapping[str, object],
    policy: dict[str, object],
    validator,
    candidate,
    *,
    partial: bool,
) -> tuple[str, RootPin]:
    entries = journal.get("entries")
    if not isinstance(entries, list) or not entries or entries[-1].get("phase") != "installed-unselected":
        _fail("recovery-not-terminal", 4 if partial else 3)
    operation = str(journal["operation_id"])
    receipts = _open_chain(
        state, ["agentic-sdlc", "acquisition", "receipts"],
        create=False, partial=partial,
    )[0]
    try:
        receipt_raw = _read_at(
            receipts[-1],
            f"{journal['archive_sha256']}.json",
            int(policy["limits"]["max_receipt_bytes"]),
            "recovery-receipt",
            partial=partial,
        )
        receipt = _strict_object(
            receipt_raw, int(policy["limits"]["max_receipt_bytes"]), "recovery-receipt"
        )
        if (
            _record_errors(validator, "immutable_receipt", receipt_raw, policy)
            or receipt.get("journal_sha256") != _sha_bytes(journal_raw)
            or receipt.get("operation_id") != operation
        ):
            _fail("recovery-receipt", 4 if partial else 3, classification="unavailable")
    finally:
        _close_pins(receipts)
    root_path = Path(str(receipt["candidate_root_absolute_physical_path"]))
    try:
        data_home = root_path.parents[4]
    except IndexError:
        _fail("recovery-root-path", 4 if partial else 3)
    data = _root_pin(data_home, "xdg-data-home")
    plan = {
        "archive_absolute_path": journal["archive_absolute_path"],
        "archive_sha256": journal["archive_sha256"],
    }
    installed, installed_operation, installed_sha = _installed_exact(
        data,
        state,
        plan,
        str(journal["plan_sha256"]),
        policy,
        validator,
        candidate,
    )
    if not installed or installed_operation != operation or installed_sha != _sha_bytes(journal_raw):
        data.close()
        _fail("recovery-final-readback", 4 if partial else 3, classification="unavailable")
    return _locator(operation, installed_sha), data






def recover_inspect_hardened(arguments, candidate, policy: dict[str, object], validator) -> int:
    candidate._require_linux_x64()
    state = _root_pin(arguments.xdg_state_home, "xdg-state-home")
    data: RootPin | None = None
    try:
        raw, journal, phase, _journal_path = _load_journal_at(
            state, arguments.journal_locator, policy, validator, partial=False
        )
        operation = str(journal["operation_id"])
        locator = arguments.journal_locator
        if phase == "installed-unselected":
            locator, data = _recover_terminal_exact(
                state,
                raw,
                journal,
                policy,
                validator,
                candidate,
                partial=False,
            )
        sys.stdout.buffer.write(
            _assessment("recover-inspect", "exact", phase, operation, locator)
        )
        return 0
    finally:
        if data is not None:
            data.close()
        state.close()


def _finish_private_hardened(
    arguments,
    candidate,
    policy: dict[str, object],
    validator,
    state: RootPin,
    data: RootPin,
    journal_raw: bytes,
    journal: dict[str, object],
    phase: str,
    journal_path: Path,
    grant_raw: bytes,
    grant: dict[str, object],
    root_sha: str,
    interpreter_sha: str,
) -> tuple[str, str]:
    operation = str(journal["operation_id"])
    locator = arguments.journal_locator
    state_root_chain = _open_chain(
        state, ["agentic-sdlc", "acquisition"], create=False, partial=True
    )[0]
    opened = list(state_root_chain)
    try:
        try:
            fcntl.flock(state.fd, fcntl.LOCK_EX)
        except OSError:
            _fail("writer-lock", 4, classification="unavailable")
        _recheck_root(state, "xdg-state-home")
        state_root = state_root_chain[-1]
        journals, _created = _open_dir_at(
            state_root.fd, "journals", state_root.display_path,
            create=False, partial=True,
        )
        receipts, _created = _open_dir_at(
            state_root.fd, "receipts", state_root.display_path,
            create=False, partial=True,
        )
        grants, _created = _open_dir_at(
            state_root.fd, "grants", state_root.display_path,
            create=False, partial=True,
        )
        opened.extend([journals, receipts, grants])
        current_raw = _read_at(
            journals,
            f"{operation}.json",
            int(policy["limits"]["max_journal_bytes"]),
            "journal-moved",
            partial=True,
        )
        if current_raw != journal_raw:
            _fail("journal-moved", 4, classification="unavailable")
        consumed = _read_consumed_at(grants, partial=True)
        authority = _authority(
            grant,
            str(journal["plan_sha256"]),
            "finish",
            operation,
            journal_path,
            _sha_bytes(journal_raw),
        )
        _validate_grant(
            grant_raw,
            grant,
            "recover_finish_grant",
            policy,
            validator,
            authority,
            consumed,
        )
        grant_sha = _sha_bytes(grant_raw)
        _write_no_replace_at(
            grants,
            f"{grant_sha}.used",
            _canonical(
                {
                    "grant_sha256": grant_sha,
                    "nonce": grant["nonce"],
                    "operation_id": operation,
                }
            ),
            partial=True,
        )
        entries = [dict(item) for item in journal["entries"]]
        plan = {
            "archive_absolute_path": grant["archive_absolute_path"],
            "archive_sha256": grant["archive_sha256"],
            "archive_size_bytes": grant["archive_size_bytes"],
            "effects_sha256": grant["effects_sha256"],
        }
        if phase in {"pinned", "staged"}:
            data_root = _open_chain(
                data, ["agentic-sdlc", "acquisition"],
                create=False, partial=True,
            )[0]
            opened.extend(data_root)
            staging, _created = _open_dir_at(
                data_root[-1].fd, "staging", data_root[-1].display_path,
                create=False, partial=True,
            )
            candidates, _created = _open_dir_at(
                data_root[-1].fd, "candidates", data_root[-1].display_path,
                create=False, partial=True,
            )
            opened.extend([staging, candidates])
            _rename_noreplace_at(
                staging,
                operation,
                candidates,
                str(grant["archive_sha256"]),
                partial=True,
            )
            published_raw = _append_entry(
                operation,
                plan,
                str(journal["plan_sha256"]),
                entries,
                "published",
                root_sha,
                interpreter_sha,
            )
            locator = _persist_journal_at(
                journals, operation, published_raw, initial=False, partial=True
            )
            phase = "published"
        if phase == "published":
            receipt_name = f"{grant['archive_sha256']}.json"
            existing_receipt_raw: bytes | None = None
            existing_receipt = _stat_at(receipts, receipt_name)
            if existing_receipt is not None:
                existing_receipt_raw = _read_at(
                    receipts,
                    receipt_name,
                    int(policy["limits"]["max_receipt_bytes"]),
                    "receipt-existing",
                    partial=True,
                )
                existing_record = _strict_state_object(
                    existing_receipt_raw,
                    int(policy["limits"]["max_receipt_bytes"]),
                    "receipt-existing",
                    partial=True,
                )
                installed_at = str(existing_record.get("installed_at", ""))
            else:
                installed_at = _timestamp()
            receipted_entries, receipted_raw, _terminal_entries, terminal_raw = (
                _planned_terminal_journals(
                    operation,
                    plan,
                    str(journal["plan_sha256"]),
                    entries,
                    root_sha,
                    interpreter_sha,
                    recorded_at=installed_at,
                )
            )
            receipt_raw = _receipt_raw(
                archive_sha=str(grant["archive_sha256"]),
                candidate_root=(
                    data.path
                    / "agentic-sdlc"
                    / "acquisition"
                    / "candidates"
                    / str(grant["archive_sha256"])
                    / "root"
                ),
                operation=operation,
                plan_sha=str(journal["plan_sha256"]),
                terminal_raw=terminal_raw,
                installed_at=installed_at,
            )
            if _record_errors(validator, "immutable_receipt", receipt_raw, policy):
                _fail("receipt-record", 4, classification="unavailable")
            if existing_receipt_raw is None:
                _write_no_replace_at(
                    receipts, receipt_name, receipt_raw, partial=True
                )
            elif existing_receipt_raw != receipt_raw:
                _fail("receipt-conflict", 4, classification="unavailable")
            else:
                # Exact bytes from a pre-fsync crash window are made durable in
                # place. The immutable receipt inode and contents are unchanged.
                _sync_existing_at(receipts, receipt_name, partial=True)
            locator = _persist_journal_at(
                journals, operation, receipted_raw, initial=False, partial=True
            )
            entries = receipted_entries
            phase = "receipted"
        if phase == "receipted":
            published_entries = [dict(item) for item in entries[:-1]]
            _receipted_entries, _receipted_raw, _terminal_entries, terminal_raw = (
                _planned_terminal_journals(
                    operation,
                    plan,
                    str(journal["plan_sha256"]),
                    published_entries,
                    root_sha,
                    interpreter_sha,
                    recorded_at=str(entries[-1]["recorded_at"]),
                )
            )
            receipt_raw = _read_at(
                receipts,
                f"{grant['archive_sha256']}.json",
                int(policy["limits"]["max_receipt_bytes"]),
                "receipt-readback",
                partial=True,
            )
            receipt = _strict_object(
                receipt_raw,
                int(policy["limits"]["max_receipt_bytes"]),
                "receipt-readback",
            )
            if receipt.get("journal_sha256") != _sha_bytes(terminal_raw):
                _fail("receipt-readback", 4, classification="unavailable")
            locator = _persist_journal_at(
                journals, operation, terminal_raw, initial=False, partial=True
            )
            phase = "installed-unselected"
        if phase != "installed-unselected":
            _fail("recovery-incomplete", 4)
        return locator, phase
    finally:
        _close_pins(opened)


def _recover_opened_external(
    arguments,
    candidate,
    policy: dict[str, object],
    validator,
    source_root: Path,
    state: RootPin,
    data: RootPin,
    journal_raw: bytes,
    journal: dict[str, object],
    journal_path: Path,
    grant_raw: bytes,
    grant: dict[str, object],
    grant_pin: ExternalFilePin,
) -> tuple[bytes, dict[str, object], str]:
    """Resume exact opened evidence before an acquired private root exists."""
    operation = str(journal["operation_id"])
    plan = {
        "archive_absolute_path": grant["archive_absolute_path"],
        "archive_sha256": grant["archive_sha256"],
        "archive_size_bytes": grant["archive_size_bytes"],
        "effects_sha256": grant["effects_sha256"],
        "trust_root_absolute_path": grant["trust_root_absolute_path"],
        "trust_root_sha256": grant["trust_root_sha256"],
        "xdg_data_home_absolute_path": grant["xdg_data_home_absolute_path"],
        "xdg_data_prestate_sha256": grant["xdg_data_prestate_sha256"],
        "xdg_state_home_absolute_path": grant["xdg_state_home_absolute_path"],
        "xdg_state_prestate_sha256": grant["xdg_state_prestate_sha256"],
    }
    opened: list[DirPin] = []
    archive_pin: ExternalFilePin | None = None
    try:
        try:
            fcntl.flock(state.fd, fcntl.LOCK_EX)
        except OSError:
            _fail("writer-lock", 4, classification="unavailable")
        _recheck_root(state, "xdg-state-home")
        _recheck_root(data, "xdg-data-home")
        _recheck_external_file(grant_pin, "grant-input")
        current_raw, current, current_phase, current_path = _load_journal_at(
            state, arguments.journal_locator, policy, validator, partial=True
        )
        if (
            current_raw != journal_raw
            or current != journal
            or current_phase != "opened"
            or current_path != journal_path
        ):
            _fail("journal-moved", 4, classification="unavailable")
        consumed = _root_recovery_consumed(state, partial=True)
        grants_chain = _optional_chain(
            state, ["agentic-sdlc", "acquisition", "grants"]
        )
        try:
            consumed.update(
                _read_consumed_at(
                    None if grants_chain is None else grants_chain[-1],
                    partial=True,
                )
            )
        finally:
            _close_pins(grants_chain)
        authority = _authority(
            plan,
            str(journal["plan_sha256"]),
            "finish",
            operation,
            journal_path,
            _sha_bytes(journal_raw),
        )
        _validate_grant(
            grant_raw,
            grant,
            "recover_finish_grant",
            policy,
            validator,
            authority,
            consumed,
        )
        if _foreign_stage_present(data, operation):
            _fail("foreign-stage", 4)
        archive_pin, archive_sha = _archive_pin(
            Path(str(grant["archive_absolute_path"])),
            int(policy["limits"]["max_archive_bytes"]),
        )
        trust_path, trust_sha = _trust_root(
            Path(str(grant["trust_root_absolute_path"])),
            candidate,
            source_root,
            structural=True,
        )
        if (
            archive_sha != grant["archive_sha256"]
            or archive_pin.item.st_size != grant["archive_size_bytes"]
            or trust_sha != grant["trust_root_sha256"]
            or str(trust_path) != grant["trust_root_absolute_path"]
        ):
            _fail("recovery-evidence", 4, classification="unavailable")
        grant_sha = _sha_bytes(grant_raw)
        marker_name = _recovery_marker_name(
            operation, grant_sha, str(grant["nonce"])
        )
        _write_root_no_replace(
            state,
            marker_name,
            _canonical(
                {
                    "grant_sha256": grant_sha,
                    "nonce": grant["nonce"],
                    "operation_id": operation,
                }
            ),
            partial=True,
        )

        state_chain, _created = _open_chain(
            state, ["agentic-sdlc", "acquisition"], create=True, partial=True
        )
        opened.extend(state_chain); state_root = state_chain[-1]
        journals, _created = _open_dir_at(
            state_root.fd, "journals", state_root.display_path,
            create=True, partial=True,
        )
        receipts, _created = _open_dir_at(
            state_root.fd, "receipts", state_root.display_path,
            create=True, partial=True,
        )
        grants, _created = _open_dir_at(
            state_root.fd, "grants", state_root.display_path,
            create=True, partial=True,
        )
        opened.extend([journals, receipts, grants])
        if _stat_at(journals, f"{operation}.json") is None:
            _persist_journal_at(
                journals, operation, journal_raw, initial=True, partial=True
            )
        else:
            routed_raw = _read_at(
                journals,
                f"{operation}.json",
                int(policy["limits"]["max_journal_bytes"]),
                "journal-moved",
                partial=True,
            )
            if routed_raw != journal_raw:
                _fail("journal-moved", 4, classification="unavailable")

        data_chain, _created = _open_chain(
            data, ["agentic-sdlc", "acquisition"], create=True, partial=True
        )
        opened.extend(data_chain); data_root = data_chain[-1]
        staging, _created = _open_dir_at(
            data_root.fd, "staging", data_root.display_path,
            create=True, partial=True,
        )
        candidates, _created = _open_dir_at(
            data_root.fd, "candidates", data_root.display_path,
            create=True, partial=True,
        )
        opened.extend([staging, candidates])
        stage = _create_dir_exclusive_at(staging, operation, partial=True)
        opened.append(stage)
        root_sha, interpreter_sha = _stage_candidate(
            stage,
            archive_pin.fd,
            archive_pin.item,
            plan,
            candidate,
            source_root,
        )
        entries = [dict(item) for item in journal["entries"]]
        pinned_raw = _append_entry(
            operation, plan, str(journal["plan_sha256"]), entries,
            "pinned", root_sha, interpreter_sha,
        )
        _persist_journal_at(
            journals, operation, pinned_raw, initial=False, partial=True
        )
        staged_raw = _append_entry(
            operation, plan, str(journal["plan_sha256"]), entries,
            "staged", root_sha, interpreter_sha,
        )
        _persist_journal_at(
            journals, operation, staged_raw, initial=False, partial=True
        )
        stage.close(); opened.remove(stage)
        _rename_noreplace_at(
            staging,
            operation,
            candidates,
            str(grant["archive_sha256"]),
            partial=True,
        )
        published_raw = _append_entry(
            operation, plan, str(journal["plan_sha256"]), entries,
            "published", root_sha, interpreter_sha,
        )
        _persist_journal_at(
            journals, operation, published_raw, initial=False, partial=True
        )
        installed_at = _timestamp()
        _receipted_entries, receipted_raw, _terminal_entries, terminal_raw = (
            _planned_terminal_journals(
                operation,
                plan,
                str(journal["plan_sha256"]),
                entries,
                root_sha,
                interpreter_sha,
                recorded_at=installed_at,
            )
        )
        receipt_raw = _receipt_raw(
            archive_sha=str(grant["archive_sha256"]),
            candidate_root=(
                data.path / "agentic-sdlc" / "acquisition" / "candidates"
                / str(grant["archive_sha256"]) / "root"
            ),
            operation=operation,
            plan_sha=str(journal["plan_sha256"]),
            terminal_raw=terminal_raw,
            installed_at=installed_at,
        )
        if _record_errors(validator, "immutable_receipt", receipt_raw, policy):
            _fail("receipt-record", 4, classification="unavailable")
        _write_no_replace_at(
            receipts,
            f"{grant['archive_sha256']}.json",
            receipt_raw,
            partial=True,
        )
        _persist_journal_at(
            journals, operation, receipted_raw, initial=False, partial=True
        )
        _persist_journal_at(
            journals, operation, terminal_raw, initial=False, partial=True
        )
        return _load_current_journal_at(state, operation, policy, validator)
    finally:
        if archive_pin is not None:
            archive_pin.close()
        _close_pins(opened)


def recover_finish_hardened(arguments, candidate, policy: dict[str, object], validator, source_root: Path) -> int:
    candidate._require_linux_x64()
    state = _root_pin(arguments.xdg_state_home, "xdg-state-home")
    data: RootPin | None = None
    container_pins: list[DirPin] | None = None
    root: DirPin | None = None
    interpreter_fd: int | None = None
    grant_pin: ExternalFilePin | None = None
    admitted_recovery = False
    try:
        journal_raw, journal, phase, journal_path = _load_journal_at(
            state, arguments.journal_locator, policy, validator, partial=False
        )
        operation = str(journal["operation_id"])
        if phase == "installed-unselected":
            locator, data = _recover_terminal_exact(
                state, journal_raw, journal, policy, validator, candidate,
                partial=False,
            )
            sys.stdout.buffer.write(
                _assessment("recover-inspect", "exact", phase, operation, locator)
            )
            return 0
        grant_raw, grant, grant_pin = _read_record(
            arguments.grant,
            int(policy["limits"]["max_grant_bytes"]),
            "grant-input",
        )
        plan = {
            "archive_absolute_path": grant.get("archive_absolute_path"),
            "archive_sha256": grant.get("archive_sha256"),
            "archive_size_bytes": grant.get("archive_size_bytes"),
            "effects_sha256": grant.get("effects_sha256"),
            "trust_root_absolute_path": grant.get("trust_root_absolute_path"),
            "trust_root_sha256": grant.get("trust_root_sha256"),
            "xdg_data_home_absolute_path": grant.get("xdg_data_home_absolute_path"),
            "xdg_data_prestate_sha256": grant.get("xdg_data_prestate_sha256"),
            "xdg_state_home_absolute_path": grant.get("xdg_state_home_absolute_path"),
            "xdg_state_prestate_sha256": grant.get("xdg_state_prestate_sha256"),
        }
        authority = _authority(
            plan,
            str(journal["plan_sha256"]),
            "finish",
            operation,
            journal_path,
            _sha_bytes(journal_raw),
        )
        consumed = _root_recovery_consumed(state, partial=False)
        grants_chain = _optional_chain(
            state, ["agentic-sdlc", "acquisition", "grants"]
        )
        try:
            consumed.update(
                _read_consumed_at(
                    None if grants_chain is None else grants_chain[-1],
                    partial=False,
                )
            )
        finally:
            _close_pins(grants_chain)
        _validate_grant(
            grant_raw,
            grant,
            "recover_finish_grant",
            policy,
            validator,
            authority,
            consumed,
        )
        if str(arguments.xdg_state_home) != grant.get("xdg_state_home_absolute_path"):
            _fail("grant-refused", 3)
        _recheck_external_file(grant_pin, "grant-input")
        admitted_recovery = True
        data = _root_pin(
            Path(str(grant["xdg_data_home_absolute_path"])), "xdg-data-home"
        )
        if (
            data.prestate_sha256 != grant.get("xdg_data_prestate_sha256")
            or state.prestate_sha256 != grant.get("xdg_state_prestate_sha256")
        ):
            _fail("xdg-prestate-mismatch", 3)
        if phase == "opened":
            new_raw, new_journal, new_phase = _recover_opened_external(
                arguments,
                candidate,
                policy,
                validator,
                source_root,
                state,
                data,
                journal_raw,
                journal,
                journal_path,
                grant_raw,
                grant,
                grant_pin,
            )
            if new_phase != "installed-unselected":
                _fail("recovery-incomplete", 4, classification="unavailable")
            locator, final_data = _recover_terminal_exact(
                state,
                new_raw,
                new_journal,
                policy,
                validator,
                candidate,
                partial=True,
            )
            final_data.close()
            sys.stdout.buffer.write(
                _assessment(
                    "recover-inspect", "exact", new_phase, operation, locator
                )
            )
            return 0
        container_pins, container, _published = _open_candidate_container(
            data, operation, str(grant["archive_sha256"]), partial=True
        )
        root, _created = _open_dir_at(
            container.fd, "root", container.display_path,
            create=False, partial=True, allowed_modes=(0o755,),
        )
        entries = journal["entries"]
        assert isinstance(entries, list)
        terminal = entries[-1]
        interpreter_sha, _script_sha, _module_sha = _validate_acquired_root(
            root, terminal, candidate, partial=True
        )
        root_sha = str(terminal["candidate_root_sha256"])
        source_item = source_root.stat()
        root_item = os.fstat(root.fd)
        inside_acquired_root = (
            source_item.st_dev,
            source_item.st_ino,
        ) == (root_item.st_dev, root_item.st_ino)
        if inside_acquired_root:
            locator, new_phase = _finish_private_hardened(
                arguments,
                candidate,
                policy,
                validator,
                state,
                data,
                journal_raw,
                journal,
                phase,
                journal_path,
                grant_raw,
                grant,
                root_sha,
                interpreter_sha,
            )
            sys.stdout.buffer.write(
                _assessment("recover-inspect", "exact", new_phase, operation, locator)
            )
            return 0

        interpreter_fd = _open_candidate_file_fd(
            root,
            INTERPRETER_RELATIVE.split("/"),
            partial=False,
            allowed_modes=(0o755,),
        )
        environment = {"LANG": "C", "LC_ALL": "C", "TZ": "UTC"}
        _recheck_external_file(grant_pin, "grant-input")
        try:
            completed = subprocess.run(
                [
                    f"/proc/self/fd/{interpreter_fd}",
                    "-I",
                    "-B",
                    f"/proc/self/fd/{root.fd}/scripts/release_candidate.py",
                    "acquire",
                    "recover",
                    "finish",
                    "--xdg-state-home",
                    str(state.path),
                    "--journal-locator",
                    arguments.journal_locator,
                    "--grant",
                    str(arguments.grant),
                ],
                cwd=f"/proc/self/fd/{root.fd}",
                env=environment,
                pass_fds=(interpreter_fd, root.fd),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            _fail(
                "recovery-child-uncertain",
                4,
                operation_id=operation,
                journal_locator=arguments.journal_locator,
                last_phase=phase,
                classification="unavailable",
            )
        # Candidate output and exit status are never authority.  Re-admit every final byte.
        del completed
        new_raw, new_journal, new_phase = _load_current_journal_at(
            state, operation, policy, validator
        )
        if new_phase != "installed-unselected":
            _fail("recovery-child-incomplete", 4, classification="unavailable")
        locator, final_data = _recover_terminal_exact(
            state,
            new_raw,
            new_journal,
            policy,
            validator,
            candidate,
            partial=True,
        )
        final_data.close()
        sys.stdout.buffer.write(
            _assessment("recover-inspect", "exact", new_phase, operation, locator)
        )
        return 0
    except AcquisitionFailure as failure:
        if failure.exit_code == 4 or admitted_recovery:
            failed_operation = "op-00000000000000000000000000000000"
            failed_phase = "absent"
            if "journal" in locals():
                failed_operation = str(
                    journal.get("operation_id", failed_operation)
                )
            if "phase" in locals():
                failed_phase = phase
            enriched = AcquisitionFailure(
                failure.code,
                4,
                failure.operation_id or failed_operation,
                failure.journal_locator or arguments.journal_locator,
                failure.last_phase
                if failure.last_phase != "absent"
                else failed_phase,
                "unavailable" if failure.classification != "exact" else failure.classification,
            )
            sys.stderr.buffer.write(_diagnostic(enriched))
            return 4
        raise
    finally:
        if interpreter_fd is not None:
            os.close(interpreter_fd)
        if grant_pin is not None:
            grant_pin.close()
        if root is not None:
            root.close()
        _close_pins(container_pins)
        if data is not None:
            data.close()
        state.close()


def run(arguments, *, candidate) -> int:
    try:
        policy, validator, source_root = _load_policy(candidate)
        if arguments.acquire_action == "plan":
            return plan(arguments, candidate, policy, validator, source_root)
        if arguments.acquire_action == "inspect":
            return inspect(arguments, candidate, policy, validator, source_root)
        if arguments.acquire_action == "apply":
            return apply_hardened(arguments, candidate, policy, validator, source_root)
        if arguments.acquire_action == "recover" and arguments.recover_action == "inspect":
            return recover_inspect_hardened(arguments, candidate, policy, validator)
        if arguments.acquire_action == "recover" and arguments.recover_action == "finish":
            return recover_finish_hardened(arguments, candidate, policy, validator, source_root)
        _fail("usage", 2)
    except AcquisitionFailure as failure:
        if failure.exit_code == 4:
            sys.stderr.buffer.write(_diagnostic(failure))
        else:
            # Stable codes contain no path, environment, credential, or untrusted content.
            print(f"release-candidate-acquisition: {failure.code}", file=sys.stderr)
        return failure.exit_code
    except Exception:
        print("release-candidate-acquisition: internal", file=sys.stderr)
        return 1
    return 1
