#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Read-only worktree-custody preflight the wave chain runs before `git worktree add`.

Seed `agentic-sdlc-f103`, the narrowed remainder of `agentic-sdlc-p3`
(`docs/research/2026-08-21-product-ladder-audit.md`, the p3 section): `git worktree add` is a
conductor recipe in PROSE ONLY (`commands/sdlc-wave.md`, `references/worktree-lifecycle.md`);
nothing executable checked, before this tool, that a claimed custody destination is under
`<target>/.worktrees/`, is free of a symlink/mount-crossing/special-node component, is either
absent or an empty directory, and is not already an active or drifted git worktree registration.

THE PRIMITIVE WAS EXTRACTED, NOT INVENTED. The retired activation planner owned exactly this shape
of check for its own one-entry write set: `S_ISLNK` refusal, `st_dev` equality, and mount-id
containment via Linux `statx(..., STATX_MNT_ID)`. This module was already an INDEPENDENT
re-expression of that primitive rather than an import of it, so the deletion of the planner left
this tool's own checks intact. The re-expression is against a different write set --
a worktree custody directory rather than a private state root -- following this repository's own
documented convention of re-expression across tool boundaries rather than a cross-tool import. The
precedent is historical rather than live: `wave-plan-compiler.py`'s `_relative_path` restated
`wave-plan-admission.py`'s `_relative_custody` rather than importing it, and both tools were removed
by ADR-0030, which is exactly why re-expression was the right call -- this module's
`_custody_spelling_reason` still owns the rule in full and did not lose it when its two neighbours
went. Each such tool is independently auditable without chasing an import across `tools/`, and none
can be silently widened by editing a shared helper one of the others does not review. The one
precedent for a cross-tool LOAD in this directory (the retired repository contract writer's
`_load_reader`) was for a SCHEMA constant a diverging copy would have made two competing
definitions of one document shape; this is a validation PREDICATE, the kind the family
already re-expresses.

WHY A NEW TOOL RATHER THAN A NEW VERB ON AN EXISTING ONE. The alternative considered was a verb on
`wave-plan-admission.py`, which admitted a COMPILED `WavePlan` against sealed
`planning-snapshot`/`mission-contract` documents; a bare `--target`/`--custody` pair with no plan,
snapshot, or mission was outside what it read, and folding this primitive into it would have forced
every caller -- including a conductor about to run its very first `git worktree add` before any plan
exists -- to assemble three sealed documents just to ask "is this one directory safe to create a
worktree in". ADR-0030 has since removed that tool entirely, so the rejected host no longer exists
and this module's independence is what kept the check. The retired activation planner was the
primitive's origin but was scoped to one manifest entry's private state root and carried no notion
of a Seed, a worktree, or a wave at all; adding worktree custody to that 4,300-line engine would
have widened its own selection surface for an unrelated concern, and it is gone while this question
remains. A small, single-purpose tool is this directory's own norm for a new primitive
(`offline-inspect.py`, `pass-budget.py`), not perpetual growth of one of the existing large ones.

SEVEN CHECKS, EACH ITS OWN NAMED SLUG, NONE OF THEM SILENT ON AN UNEVALUATED PATH:

    custody-spelling        the one canonical relative form this family admits, which
                             `wave-plan-admission.py` sealed before ADR-0030 removed it: no leading
                             `/` or drive letter, no backslash, no NUL, no empty/`.`/`..` segment.
                             A custody path carries the `.worktrees/` prefix
                             (`references/worktree-lifecycle.md` owns that substrate rule), so
                             `--custody` is read the same way.
    custody-root             the custody string's first segment must be `.worktrees` and it must
                             name at least one directory beneath it -- `.worktrees` itself is not
                             a custody destination.
    path-integrity           walking the target root down through every custody segment via
                             `O_NOFOLLOW|O_DIRECTORY` opens, no EXISTING component may be a
                             symlink or a non-directory special node (regular file, device, socket,
                             FIFO); a component that does not exist yet is not a violation -- that
                             is exactly the directory `git worktree add` would create.
    destination-vacancy      the exact custody DESTINATION itself, not an ancestor component, must
                             be either absent or an EMPTY directory: `git worktree add` tolerates a
                             pre-existing empty directory but refuses a non-empty one
                             (`references/worktree-lifecycle.md`'s verified fact 5), so a
                             destination holding even one entry -- including a bare dotfile -- is
                             refused here, matching that; a destination that does not exist yet, or
                             an ancestor that does not exist yet, is vacant and refuses nothing.
    mount-containment        every opened component's `(st_dev, mount_id)` must equal the target
                             root's own, so a bind mount or a foreign filesystem grafted under
                             `.worktrees/` cannot smuggle the custody destination onto a device the
                             conductor never asked to write. Refused, never silently passed, when
                             this host cannot answer the question for the target root OR for any
                             individual custody component (non-Linux, or `statx` without
                             `STATX_MNT_ID`) -- the retired planner's own `_mount_id_fd` raised
                             rather than falling back to `st_dev` alone, and so does this one;
                             an unanswerable CHILD is named and refused, never silently treated as a
                             match against the root.
    registration-occupied     the exact custody path must not already be an ACTIVE `git worktree
                             list --porcelain` registration (its directory still present).
    registration-drifted     the exact custody path must not be a REGISTERED-BUT-VANISHED entry --
                             `git worktree list --porcelain` still reports it, its directory is
                             gone, and a bare `add` would refuse "missing but already registered
                             worktree" (verified in `references/worktree-lifecycle.md`'s Step 1
                             table); this preflight names that in advance rather than letting the
                             wave chain hit git's own error message.

A check that could not run because an EARLIER check already refused is reported with an explicit
`"unevaluated"` status and a stated reason -- never folded into `"met"`. A `"met"` status is a
claim this tool actually looked and found nothing wrong; an unevaluated path was never looked at,
and conflating the two is exactly the silent-pass defect this family's own review history calls
out repeatedly.

READ-ONLY, OFFLINE (BEYOND ONE LOCAL `git worktree list`), AND EFFECT-FREE. This tool opens
directories to inspect them and runs exactly one read-only `git worktree list --porcelain -z`
against `--target`; it creates nothing, deletes nothing, and never itself runs `git worktree add`.
Implementation Decision 9's exit vocabulary here is therefore the three-class subset a genuinely
effect-free gate is entitled to: 0 for a clear result (the wave chain may proceed), 2 for a
grammar/schema/input error (the question itself could not be asked), and 3 for a clean refusal --
and because this tool never causes an effect, EVERY refusal it can name is "before" one, so 3 is
never conditional the way it was in `wave-plan-admission.py`, whose own report was sealed either way
(removed by ADR-0030), nor reserved for a query tool that treats its own refusal as a successful
answer the way `offline-inspect.py`'s `EXIT_NOT_READY` does. 1 remains reserved for a genuinely
unexpected internal failure and is not deliberately reachable; 4 does not apply, by Decision 9's own
definition of it: a tool that causes no effect can neither admit a partial one.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

SCHEMA = "agentic-sdlc/worktree-custody-preflight-result@1"

#: The one segment every admissible custody path must start with. Re-expressed from
#: `references/worktree-lifecycle.md` "The substrate, in one line", which owns the rule, not
#: imported from any tool.
CUSTODY_ROOT = ".worktrees"

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
EXIT_REFUSED = 3

MET = "met"
REFUSED = "refused"
UNEVALUATED = "unevaluated"

#: Exactly the seven checks this tool runs, in the order the result document lists them. Fixed as
#: a tuple rather than derived from a dict's insertion order, so a future edit that reorders a
#: dict-literal cannot silently reorder -- or drop -- a row of the report.
CHECK_SLUGS: tuple[str, ...] = (
    "custody-spelling",
    "custody-root",
    "path-integrity",
    "destination-vacancy",
    "mount-containment",
    "registration-occupied",
    "registration-drifted",
)


class InputError(Exception):
    """The question itself could not be asked: exit 2. Raised before any of the seven checks run."""


class MountUnsupported(Exception):
    """This host or filesystem cannot answer the mount-id question at all."""


# ---- statx / mount-id plumbing --------------------------------------------------------------------
# Re-expressed from the retired planner's own `_Statx`/`_mount_id_fd` (see the module docstring's
# provenance note). The struct layout is the Linux kernel's `struct statx` ABI, not this project's
# own design, so an independent copy is a second binding to one fixed kernel contract rather than a
# second definition of a rule that could drift from the first.

_AT_EMPTY_PATH = 0x1000
_STATX_MNT_ID = 0x1000
_STATX_BASIC_STATS = 0x07FF


class _StatxTimestamp(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_longlong), ("tv_nsec", ctypes.c_uint), ("__reserved", ctypes.c_int)]


class _Statx(ctypes.Structure):
    _fields_ = [
        ("stx_mask", ctypes.c_uint), ("stx_blksize", ctypes.c_uint), ("stx_attributes", ctypes.c_ulonglong),
        ("stx_nlink", ctypes.c_uint), ("stx_uid", ctypes.c_uint), ("stx_gid", ctypes.c_uint),
        ("stx_mode", ctypes.c_ushort), ("__spare0", ctypes.c_ushort), ("stx_ino", ctypes.c_ulonglong),
        ("stx_size", ctypes.c_ulonglong), ("stx_blocks", ctypes.c_ulonglong),
        ("stx_attributes_mask", ctypes.c_ulonglong), ("stx_atime", _StatxTimestamp),
        ("stx_btime", _StatxTimestamp), ("stx_ctime", _StatxTimestamp), ("stx_mtime", _StatxTimestamp),
        ("stx_rdev_major", ctypes.c_uint), ("stx_rdev_minor", ctypes.c_uint), ("stx_dev_major", ctypes.c_uint),
        ("stx_dev_minor", ctypes.c_uint), ("stx_mnt_id", ctypes.c_ulonglong),
        ("stx_dio_mem_align", ctypes.c_uint), ("stx_dio_offset_align", ctypes.c_uint),
        ("stx_subvol", ctypes.c_ulonglong), ("stx_atomic_write_unit_min", ctypes.c_uint),
        ("stx_atomic_write_unit_max", ctypes.c_uint), ("stx_atomic_write_segments_max", ctypes.c_uint),
        ("stx_dio_read_offset_align", ctypes.c_uint), ("__spare3", ctypes.c_ulonglong * 9),
    ]


_LIBC = ctypes.CDLL(None, use_errno=True)
_LIBC.statx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(_Statx)]
_LIBC.statx.restype = ctypes.c_int


def _mount_id_fd(fd: int) -> int:
    """The exact kernel mount id backing `fd`, or a raised `MountUnsupported`.

    Named and shaped like the retired planner's own `_mount_id_fd` so the provenance is
    legible, and monkeypatchable by a test importing this module directly -- the seam an
    unprivileged mount-crossing test needs, since no ordinary CI host can bind-mount a second real
    filesystem under a throwaway fixture repository.
    """
    if sys.platform != "linux":
        raise MountUnsupported("this host is not Linux, so statx mount IDs are unavailable")
    info = _Statx()
    result = _LIBC.statx(fd, ctypes.c_char_p(b""), _AT_EMPTY_PATH, _STATX_BASIC_STATS | _STATX_MNT_ID, ctypes.byref(info))
    if result != 0 or not (info.stx_mask & _STATX_MNT_ID):
        raise MountUnsupported("statx mount IDs are unavailable on this host or filesystem")
    return int(info.stx_mnt_id)


# ---- custody-spelling and custody-root: pure string checks ----------------------------------------


def _custody_spelling_reason(custody: Any) -> str | None:
    """`None` when `custody` is the family's one canonical relative spelling; a named reason else.

    Re-expressed from `wave-plan-admission.py`'s `_relative_custody`, which itself restated
    `wave-plan-compiler.py`'s `_relative_path` before ADR-0030 removed both: no leading `/` or drive
    letter, no backslash, no NUL, no empty/`.`/`..` segment. The reasoning applies here unchanged --
    custody is compared by STRING, so two spellings of one directory would compare as two different
    custodies unless every caller is refused down to one spelling. This function is now the only
    place in the repository that states the rule.
    """
    if not isinstance(custody, str) or not custody:
        return f"--custody {custody!r} is empty; a custody path names one directory under {CUSTODY_ROOT}/"
    if custody.startswith("/") or (len(custody) > 1 and custody[1] == ":"):
        return f"--custody {custody!r} is absolute rather than repository-relative"
    if "\\" in custody:
        return f"--custody {custody!r} carries a backslash; custody paths are forward-slashed"
    if "\x00" in custody:
        return f"--custody {custody!r} carries a NUL character, which no filesystem path may contain"
    segments = custody.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        return (
            f"--custody {custody!r} carries an empty, '.', or '..' segment: two spellings of it would "
            "compare as different custody"
        )
    return None


def _custody_root_reason(segments: list[str]) -> str | None:
    """`None` when the (already well-spelled) custody resolves under `<target>/.worktrees/`."""
    if segments[0] != CUSTODY_ROOT or len(segments) < 2:
        joined = "/".join(segments)
        return (
            f"--custody {joined!r} does not resolve under {CUSTODY_ROOT}/: its first segment must be "
            f"{CUSTODY_ROOT!r} and it must name at least one directory beneath it"
        )
    return None


# ---- path-integrity and mount-containment: the physical walk --------------------------------------


def _open_target_root(target: Path) -> tuple[int, dict[str, int | None]]:
    """Open `--target` itself (symlinks followed, exactly once, at this one boundary) and its identity.

    `--target` is the caller's own established repository root -- the wave chain's own
    `git rev-parse --show-toplevel`, not a component this tool is asked to validate -- so it is
    opened plainly rather than walked component-by-component from `/`; the retired planner's own
    `open_root_chain` did walk from `/`, but for its OWN target argument, which this module
    does not re-derive. Everything BELOW this root -- `.worktrees` and every custody segment -- is
    walked with `O_NOFOLLOW` and is what the two checks below actually decide.
    """
    try:
        fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    except FileNotFoundError as exc:
        raise InputError(f"the supplied --target {str(target)!r} does not exist") from exc
    except NotADirectoryError as exc:
        raise InputError(f"the supplied --target {str(target)!r} is not a directory") from exc
    except OSError as exc:
        raise InputError(f"the supplied --target {str(target)!r} cannot be opened: {exc}") from exc
    try:
        dev = os.fstat(fd).st_dev
        try:
            mount_id: int | None = _mount_id_fd(fd)
        except MountUnsupported:
            mount_id = None
        return fd, {"dev": dev, "mount_id": mount_id}
    except BaseException:
        os.close(fd)
        raise


def _walk_custody(root_fd: int, root_identity: dict[str, int | None], segments: list[str]) -> dict[str, tuple[str, str | None]]:
    """Walk `segments` under `root_fd`, refusing the first symlink/special node or mount crossing.

    Stops at the FIRST problem of either kind, in the retired planner's own style of
    raising immediately rather than accumulating; the three checks below are then classified from
    why the walk stopped, so a check that never got the chance to look past an earlier refusal is
    reported `unevaluated`, never `met`. `destination-vacancy` is decided in the SAME iteration
    that opens the exact final segment -- before that segment's own mount check runs -- so its
    answer never depends on whether that segment also happens to cross a mount boundary.
    """
    mount_supported = root_identity["mount_id"] is not None
    path_reason: str | None = None
    mount_reason: str | None = None
    vacancy_reason: str | None = None
    vacancy_determined = False
    stopped_for: str | None = None
    last_index = len(segments) - 1
    current = os.dup(root_fd)
    walked: list[str] = []
    try:
        for index, segment in enumerate(segments):
            walked.append(segment)
            where = "/".join(walked)
            try:
                child = os.open(
                    segment, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW, dir_fd=current
                )
            except FileNotFoundError:
                # Nothing below here exists yet -- exactly what `git worktree add` would create.
                # Whether this segment IS the destination or merely an ancestor of it, the
                # destination itself cannot exist either, so it is vacant.
                vacancy_determined = True
                break
            except NotADirectoryError:
                # O_DIRECTORY|O_NOFOLLOW reports ENOTDIR for a symlink exactly as it does for a plain
                # non-directory node (measured on Linux 6.18: ELOOP appears only WITHOUT O_DIRECTORY),
                # so the enforcement above is already fail-closed either way; this lstat is diagnostic
                # wording only; a race between it and the open above cannot loosen or narrow that
                # decision.
                try:
                    probe = os.lstat(segment, dir_fd=current)
                    is_link = stat.S_ISLNK(probe.st_mode)
                except OSError:
                    is_link = False
                if is_link:
                    path_reason = f"{where!r} is a symlink; a custody path component must be a real directory"
                else:
                    path_reason = (
                        f"{where!r} exists and is not a directory (a regular file, device, socket, or "
                        "FIFO cannot be a custody path component)"
                    )
                stopped_for = "path-integrity"
                break
            except OSError as exc:
                path_reason = f"{where!r} cannot be inspected: {exc}"
                stopped_for = "path-integrity"
                break
            try:
                if index == last_index:
                    # The custody DESTINATION itself already exists as a real directory (path
                    # integrity above already excluded a symlink or special node). It is admissible
                    # only if it holds nothing at all -- `git worktree add`'s own tolerance for a
                    # pre-existing directory is for an EMPTY one.
                    try:
                        entries = os.listdir(child)
                    except OSError as exc:
                        vacancy_reason = f"{where!r} cannot be inspected for occupancy: {exc}"
                    else:
                        if entries:
                            sample = sorted(entries)[0]
                            vacancy_reason = (
                                f"{where!r} already exists and is not empty (it contains {sample!r}); "
                                "`git worktree add` accepts only an absent or empty destination"
                            )
                        else:
                            vacancy_reason = None
                    vacancy_determined = True
                if mount_supported:
                    child_dev = os.fstat(child).st_dev
                    try:
                        child_mount = _mount_id_fd(child)
                    except MountUnsupported:
                        # A CHILD whose mount id cannot be answered is refused by name, never
                        # silently treated as matching the root: falling back to `child_mount = None`
                        # and skipping the comparison (the prior shape of this branch) let an
                        # unanswerable component pass mount-containment outright.
                        mount_reason = (
                            f"{where!r} cannot be checked for mount containment: statx mount IDs are "
                            "unavailable for it"
                        )
                        stopped_for = "mount-containment"
                        break
                    if (child_dev, child_mount) != (root_identity["dev"], root_identity["mount_id"]):
                        mount_reason = f"{where!r} crosses a mount boundary from the target root"
                        stopped_for = "mount-containment"
                        break
            finally:
                os.close(current)
                current = child
    finally:
        os.close(current)

    if path_reason is not None:
        path_status: tuple[str, str | None] = (REFUSED, path_reason)
    else:
        path_status = (MET, None)

    if vacancy_determined:
        vacancy_status: tuple[str, str | None] = (
            (REFUSED, vacancy_reason) if vacancy_reason is not None else (MET, None)
        )
    elif path_reason is not None:
        vacancy_status = (
            UNEVALUATED,
            "not verified: the walk stopped at an earlier path-integrity refusal before reaching the "
            "destination",
        )
    else:
        vacancy_status = (
            UNEVALUATED,
            "not verified: the walk stopped at an earlier mount-containment refusal before reaching "
            "the destination",
        )

    if not mount_supported:
        mount_status: tuple[str, str | None] = (
            REFUSED,
            "this host cannot verify mount containment: statx mount IDs are unavailable",
        )
    elif mount_reason is not None:
        mount_status = (REFUSED, mount_reason)
    elif stopped_for == "path-integrity":
        mount_status = (
            UNEVALUATED,
            "not verified: the walk stopped at an earlier path-integrity refusal before reaching the "
            "rest of the custody path",
        )
    else:
        mount_status = (MET, None)

    return {
        "path-integrity": path_status,
        "destination-vacancy": vacancy_status,
        "mount-containment": mount_status,
    }


# ---- registration-occupied and registration-drifted: one read-only `git worktree list` -----------


#: The only environment this tool reads, and only so a bare `git` name resolves to an executable.
#: Re-expressed from the retired planning snapshot's own `EXEC_RESOLUTION_ENV`/`child_environment`.
_EXEC_RESOLUTION_ENV = ("PATH", "PATHEXT", "SYSTEMROOT")


def _child_environment() -> dict[str, str]:
    """A constructed child environment: exec resolution carried across, everything else asserted.

    No ambient `GIT_*` variable survives, and config is pointed at the null device rather than
    merely unset, so an operator's shell or a system/global git config cannot change what this
    read-only observation reports.
    """
    environment = {key: os.environ[key] for key in _EXEC_RESOLUTION_ENV if key in os.environ}
    environment.update(
        {
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return environment


def _list_worktrees(git: str, target: Path) -> list[str]:
    """Every `worktree <path>` line `git worktree list --porcelain -z` reports, in order.

    `-z` rather than the line form, exactly as the retired snapshot's `observe_worktrees` read it:
    the line form does not quote paths, so a path containing a newline would parse as two worktrees.
    Only the path is read; HEAD, branch, and `prunable` are not this tool's question -- occupied
    versus drifted is decided by whether the reported path still exists on disk, checked
    separately and read-only.
    """
    try:
        completed = subprocess.run(
            [git, "--no-optional-locks", "-c", "core.fsmonitor=false", "worktree", "list", "--porcelain", "-z"],
            cwd=str(target),
            env=_child_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise InputError(f"cannot run the supplied --git {git!r}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise InputError(
            f"git worktree list exited {completed.returncode} in {target}, so the registration state "
            f"could not be observed{': ' + detail if detail else ''}"
        )
    try:
        text = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"git worktree list output is not UTF-8, so it could not be recorded: {exc}") from exc
    paths: list[str] = []
    for field in text.split("\0"):
        if not field:
            continue
        name, _, value = field.partition(" ")
        if name == "worktree":
            paths.append(value)
    return paths


def _registration_reasons(git: str, target: Path, custody: str) -> tuple[str | None, str | None]:
    """`(occupied_reason, drifted_reason)`, at most one of them non-`None`.

    Compared as normalized TEXT against the observed list, exactly as `wave-plan-admission.py`'s
    `check_custody_availability` did before ADR-0030 removed it, and carrying the same residual it
    named: a differently spelled path to the same directory (a symlink, a case-insensitive
    filesystem, a bind mount) would read as unoccupied. That residual is accepted here rather than
    solved, for the same reason it was accepted there.
    """
    claimed = os.path.normpath(os.path.join(str(target), custody))
    for path in _list_worktrees(git, target):
        if os.path.normpath(path) != claimed:
            continue
        if os.path.isdir(path):
            return (
                f"--custody {custody!r} is already registered as an active git worktree at {path!r}",
                None,
            )
        return (
            None,
            f"--custody {custody!r} is registered as a git worktree at {path!r} whose directory no "
            "longer exists; `git worktree prune` must run before a new worktree can be added at this "
            "path",
        )
    return None, None


# ---- orchestration ----------------------------------------------------------------------------


def _met(reason: str | None) -> dict[str, Any]:
    return {"status": REFUSED, "reason": reason} if reason is not None else {"status": MET, "reason": None}


def _unevaluated(reason: str) -> dict[str, Any]:
    return {"status": UNEVALUATED, "reason": reason}


def _from_pair(pair: tuple[str, str | None]) -> dict[str, Any]:
    status, reason = pair
    return {"status": status, "reason": reason}


def run_preflight(target: Path, custody: Any, *, git: str = "git") -> dict[str, Any]:
    """Run all seven checks, gating a later one behind an earlier refusal rather than guessing at it.

    Every one of `CHECK_SLUGS` is ALWAYS present in the returned document, in that fixed order,
    with an explicit status -- `met`, `refused`, or `unevaluated` -- and a reason for every status
    but `met`. Nothing is silently dropped and nothing unevaluated is reported as passing.
    """
    checks: dict[str, dict[str, Any]] = {}

    spelling_reason = _custody_spelling_reason(custody)
    checks["custody-spelling"] = _met(spelling_reason)
    if spelling_reason is not None:
        reason = "the custody spelling was refused, so this could not be checked against it"
        for slug in CHECK_SLUGS[1:]:
            checks[slug] = _unevaluated(reason)
        return _result(target, custody, checks)

    segments = custody.split("/")
    root_reason = _custody_root_reason(segments)
    checks["custody-root"] = _met(root_reason)
    if root_reason is not None:
        reason = f"the custody path does not resolve under {CUSTODY_ROOT}/, so this could not be checked"
        for slug in CHECK_SLUGS[2:]:
            checks[slug] = _unevaluated(reason)
        return _result(target, custody, checks)

    root_fd, root_identity = _open_target_root(target)
    try:
        walked = _walk_custody(root_fd, root_identity, segments)
    finally:
        os.close(root_fd)
    checks["path-integrity"] = _from_pair(walked["path-integrity"])
    checks["destination-vacancy"] = _from_pair(walked["destination-vacancy"])
    checks["mount-containment"] = _from_pair(walked["mount-containment"])

    if walked["path-integrity"][0] != MET:
        reason = "the custody path failed path-integrity, so its registration could not be safely inspected"
        checks["registration-occupied"] = _unevaluated(reason)
        checks["registration-drifted"] = _unevaluated(reason)
        return _result(target, custody, checks)

    occupied_reason, drifted_reason = _registration_reasons(git, target, custody)
    checks["registration-occupied"] = _met(occupied_reason)
    checks["registration-drifted"] = _met(drifted_reason)
    return _result(target, custody, checks)


def _result(target: Path, custody: Any, checks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ordered = [{"slug": slug, **checks[slug]} for slug in CHECK_SLUGS]
    clear = all(entry["status"] == MET for entry in ordered)
    return {
        "schema": SCHEMA,
        "target": str(target),
        "custody": custody,
        "custody_root": CUSTODY_ROOT,
        "disposition": "clear" if clear else "refused",
        "checks": ordered,
    }


# ---- process boundary: streams, argparse, exit codes -----------------------------------------


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process already reported as failed.

    Re-expressed from `mission-contract.py`'s helper of the same name and the same reasoning:
    dropping the module attribute is how CPython represents a stream this process was not handed,
    and it loses no byte the failed write had not already lost.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Callable[[str], None]:
    """Wrap one already-settled display stream so a failed write costs the channel, never the code."""
    if stream is None:
        return lambda line: None
    emit_to = getattr(stream, "write", None)
    if not callable(emit_to):
        return lambda line: None
    flush = getattr(stream, "flush", None)
    live = [True]

    def emit(line: str) -> None:
        if not live[0]:
            return
        try:
            emit_to(line)
            if callable(flush):
                flush()
        except (OSError, ValueError):
            live[0] = False
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    return guarded_sink("stderr", sys.stderr)


def report_input_error(message: str) -> None:
    advisory_stderr()(f"worktree-custody-preflight.py: {message}\n")


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII-safe, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or classify the failure instead of inheriting 1 or 120."""
    payload = canonical_bytes(result)
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    emit_to: Any = None
    flush: Any = None
    body: Any = payload
    if buffer is not None and callable(getattr(buffer, "write", None)):
        emit_to, flush = buffer.write, getattr(buffer, "flush", None)
    elif stream is not None and callable(getattr(stream, "write", None)):
        emit_to, flush, body = stream.write, getattr(stream, "flush", None), payload.decode("ascii")
    if emit_to is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "result could not be delivered"
        )
        return EXIT_INTERNAL
    try:
        emit_to(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        abandon_broken_stream("stdout", stream)
        report_input_error(f"cannot write the result document to stdout: {exc}")
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules (re-expressed from the family's own `_Parser`).

    `error` writes usage through this module's own guarded sink rather than argparse's default
    `print_usage`, which falls back to stdout when `sys.stderr is None` and would otherwise put
    usage bytes where this module's one result document lives.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            return
        if file is sys.stdout or file is sys.__stdout__:
            guarded_sink("stdout", file)(message)
            return
        guarded_sink("stderr", file)(message)

    def error(self, message: str) -> Any:
        note = advisory_stderr()
        note(self.format_usage())
        note(f"{self.prog}: error: {message}\n")
        raise SystemExit(EXIT_INPUT)


EPILOG = (
    "Exit codes: 0 every one of the seven checks named above is met -- the destination is vacant "
    "(absent, or an existing directory with nothing in it), free of a symlink/mount-crossing/"
    "special-node component, and neither an active nor a drifted git worktree registration -- but "
    "this tool does not read branch occupancy, a separate resource, so `git worktree add` can still "
    "refuse on that one even after exit 0; 2 the supplied --target or --custody could not even be "
    "asked about (a missing or unusable target, an unusable git, or a grammar error); 3 at least one "
    "check names a clean refusal. This tool never runs `git worktree add` and changes nothing on "
    "disk, so a refusal here always precedes the effect it is refusing. Implementation Decision 9's "
    "4 does not apply: this tool causes no effect, admitted or partial, so it can never report one."
)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog="worktree-custody-preflight.py",
        description=(
            "Read-only preflight the wave chain runs before `git worktree add`: verifies the "
            "claimed custody destination resolves under <target>/.worktrees/, that no path "
            "component is a symlink, mount-crossing, or special node, that the destination itself "
            "is absent or an empty directory, and that the destination is neither an active nor a "
            "drifted git worktree registration. The custody primitive it re-expresses (S_ISLNK, "
            "st_dev, mount-id containment) came from the retired activation planner; it runs no "
            "`git worktree add`, writes nothing, and authorizes nothing."
        ),
        epilog=EPILOG,
    )
    parser.add_argument(
        "--target", required=True, help="the absolute repository root `git worktree add` would run against"
    )
    parser.add_argument(
        "--custody",
        required=True,
        help=f"the repository-relative custody path, e.g. {CUSTODY_ROOT}/<seed-id>-<slug>",
    )
    parser.add_argument("--git", default="git", help="the git executable to observe the registration through")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    target_raw = args.target
    if not isinstance(target_raw, str) or not target_raw:
        report_input_error("--target is empty")
        return EXIT_INPUT
    target_path = Path(target_raw)
    if not target_path.is_absolute():
        report_input_error(f"--target {target_raw!r} is not an absolute path")
        return EXIT_INPUT
    try:
        result = run_preflight(target_path, args.custody, git=args.git)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    delivered = emit_result(result)
    if delivered != EXIT_OK:
        return delivered
    return EXIT_OK if result["disposition"] == "clear" else EXIT_REFUSED


if __name__ == "__main__":
    raise SystemExit(main())
