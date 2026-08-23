"""Constrained stdlib guard for the checkout-development ``ccodex sdlc`` reader.

This is a production control for the process that renders the read-only report.  It blocks the
stdlib mutation, lock, child-process, and socket routes that the installed lifecycle modules use.
It deliberately is not an adversarial same-UID sandbox: a caller that can replace this checkout or
the interpreter can bypass it.  Its job is narrower and testable: keep the inspection process from
accidentally reaching a lifecycle writer while it imports the existing state adapters.
"""

from __future__ import annotations

import builtins
import importlib.util
import io
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any, Callable


class ReadOnlyViolation(RuntimeError):
    """Raised when a guarded process attempts an effectful stdlib operation."""


_INSTALLED = False


def _blocked(operation: str) -> Callable[..., Any]:
    def deny(*_args: Any, **_kwargs: Any) -> Any:
        raise ReadOnlyViolation(f"ccodex sdlc read-only guard rejected {operation}")

    return deny


def _read_only_open(original: Callable[..., Any], operation: str) -> Callable[..., Any]:
    def guarded(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if any(flag in mode for flag in ("w", "a", "x", "+")):
            raise ReadOnlyViolation(f"ccodex sdlc read-only guard rejected {operation}")
        return original(file, mode, *args, **kwargs)

    return guarded


def _read_only_os_open(original: Callable[..., int]) -> Callable[..., int]:
    write_flags = (
        os.O_WRONLY
        | os.O_RDWR
        | os.O_APPEND
        | os.O_CREAT
        | os.O_TRUNC
        | getattr(os, "O_TMPFILE", 0)
    )

    def guarded(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if flags & write_flags:
            raise ReadOnlyViolation("ccodex sdlc read-only guard rejected os.open for writing")
        return original(path, flags, *args, **kwargs)

    return guarded


def install() -> None:
    """Install one process-local guard before any lifecycle adapter is imported."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True

    builtins.open = _read_only_open(builtins.open, "open for writing")  # type: ignore[assignment]
    io.open = _read_only_open(io.open, "io.open for writing")  # type: ignore[assignment]
    os.open = _read_only_os_open(os.open)  # type: ignore[assignment]

    for name in (
        "mkdir",
        "makedirs",
        "mkfifo",
        "mknod",
        "remove",
        "unlink",
        "rmdir",
        "rename",
        "replace",
        "link",
        "symlink",
        "chmod",
        "chown",
        "lchown",
        "utime",
        "fchmod",
        "fchown",
        "ftruncate",
        "truncate",
        "write",
        "fsync",
        "fdatasync",
        "system",
        "popen",
        "fork",
        "forkpty",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "posix_spawn",
        "posix_spawnp",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "startfile",
    ):
        if hasattr(os, name):
            setattr(os, name, _blocked(f"os.{name}"))

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        setattr(subprocess, name, _blocked(f"subprocess.{name}"))
    for name in ("mkstemp", "mkdtemp", "NamedTemporaryFile", "TemporaryFile", "TemporaryDirectory"):
        setattr(tempfile, name, _blocked(f"tempfile.{name}"))
    for name in ("copy", "copy2", "copyfile", "copytree", "move", "rmtree", "chown"):
        if hasattr(shutil, name):
            setattr(shutil, name, _blocked(f"shutil.{name}"))
    for name in ("socket", "socketpair", "create_connection", "fromfd"):
        if hasattr(socket, name):
            setattr(socket, name, _blocked(f"socket.{name}"))

    for name in (
        "mkdir",
        "touch",
        "unlink",
        "rmdir",
        "rename",
        "replace",
        "chmod",
        "symlink_to",
        "hardlink_to",
        "link_to",
        "write_bytes",
        "write_text",
    ):
        if hasattr(Path, name):
            setattr(Path, name, _blocked(f"pathlib.Path.{name}"))

    try:
        import fcntl
    except ImportError:
        fcntl = None  # type: ignore[assignment]
    if fcntl is not None:
        for name in ("flock", "lockf", "fcntl"):
            if hasattr(fcntl, name):
                setattr(fcntl, name, _blocked(f"fcntl.{name}"))
    if hasattr(os, "lockf"):
        os.lockf = _blocked("os.lockf")  # type: ignore[assignment]
    try:
        import msvcrt
    except ImportError:
        msvcrt = None  # type: ignore[assignment]
    if msvcrt is not None and hasattr(msvcrt, "locking"):
        msvcrt.locking = _blocked("msvcrt.locking")  # type: ignore[assignment]


def load_sibling(script_path: Path, module_stem: str) -> ModuleType:
    """Load one named sibling by absolute file path, never through ambient ``sys.path``."""
    candidate = script_path.parent / f"{module_stem}.py"
    if candidate.is_symlink() or not candidate.is_file():
        raise ReadOnlyViolation(f"ccodex sdlc cannot safely import adapter: {candidate}")
    module_name = f"_ccodex_sdlc_readonly_{module_stem}"
    spec = importlib.util.spec_from_file_location(module_name, candidate)
    if spec is None or spec.loader is None:
        raise ReadOnlyViolation(f"ccodex sdlc cannot load adapter: {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def block_lifecycle_mutators(*modules: ModuleType) -> None:
    """Make legacy lifecycle entrypoints unavailable to this guarded reader process."""
    names = {
        "install",
        "_install",
        "uninstall",
        "_uninstall",
        "retire_aliases",
        "_retire_aliases",
        "migrate_v1_state",
        "_migrate_v1_state",
        "recover_transactions",
        "recover_pending",
        "execute_recovery",
        "write_state",
        "persist_state",
        "atomic_write",
        "durable_mkdir",
        "durable_unlink",
        "lifecycle_lock",
        "installer_lock",
        "arm",
        "arm_pending",
        "commit_pending",
        "self_test",
        "status",
        "_status",
        # Landed after this set was first pinned (agentic-sdlc-7c7d): the transactional writers
        # `install_skill_bundle` uses to arm, publish, and commit an entry's own transition.
        # Harmless while the reader never loads that module for anything but `readonly_projection`
        # -- and the process-global primitive blocks would stop each at its first write anyway --
        # but the set is closed here rather than left to predate whatever lifecycle writer lands
        # next.  Every name is applied with `hasattr`, so a retired writer is simply skipped.
        "publish",
        "rename_absent",
        "reserve_private_artifact",
        "save_owned_entry",
        "transactional_create",
        "transactional_delete",
        "transactional_replace",
    }
    for module in modules:
        for name in names:
            if hasattr(module, name):
                setattr(module, name, _blocked(f"{module.__name__}.{name}"))
