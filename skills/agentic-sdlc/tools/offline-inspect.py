#!/usr/bin/env python3
"""Emit a deterministic, read-only activation preview for one local target."""

from __future__ import annotations

import argparse
import errno
import json
import os
import stat
import sys
from pathlib import Path

SCHEMA = "agentic-sdlc/offline-inspect@1"

# EXITS, as one derivation point (product-spec Implementation Decision 9; the machine-readable
# `exit_codes` map that used to restate it went with the acquisition engine, so this comment and
# the constants below are now the only statement of it). This command opens nothing
# for writing, spawns no process, touches no network, and mutates no target, so 3 and 4 are
# UNREACHABLE rather than merely unused: a command that can cause no effect can neither refuse
# before one nor admit a partial one. `skills/agentic-sdlc/tools/wave-verdict.py` states the same
# rule for the same reason.
#
# NOT_READY is therefore NOT 1. A completed inspection that names a refusal is this command
# SUCCEEDING at the question it was asked, so it may not occupy the code reserved for an unexpected
# internal failure: reporting a derived verdict and a crash at the same 1 leaves a caller unable to
# tell them apart. It keeps a NONZERO code so an existing shell caller still sees a signal, taken
# from OUTSIDE the reserved 0-4 block exactly as `scripts/gate_baseline.py`'s `EXIT_WORSENED` is
# ("The comparison ran and names at least one newly-failing test. Never inside the reserved block.").
#
# MEASURED RESIDUAL, not a claim: 1 here is the uncaught-exception class only. Every unreadable
# target, missing target, and permission-denied target measured on 2026-08-21 lands on 2 through
# `InspectionError`, and a stdout that cannot receive the one result document exits 120 -- the
# interpreter's own flush-at-exit failure, outside this table entirely. That residual is recorded
# rather than asserted as the contract.
#: Every inspected item was adoptable, mergeable, or skippable: preview readiness is READY.
EXIT_READY = 0
#: An unexpected internal failure. A stdout that cannot receive the one result document is NOT
#: here: it exits 120 via the interpreter's flush-at-exit, per the measured residual above.
EXIT_INTERNAL = 1
#: The target or the command line itself is unusable, so no inspection happened.
EXIT_INPUT = 2
#: The inspection RAN and names at least one refusal: preview readiness is NOT_READY. Deliberately
#: outside the reserved block, and deliberately never 0, 1, or 2.
EXIT_NOT_READY = 5

MARKER_START = "<!-- agentic-sdlc:start -->"
MARKER_END = "<!-- agentic-sdlc:end -->"
CANONICAL_INSTRUCTION_CONTENT = {
    "AGENTS.md": (
        "## intent\nProject intent for the wave.\n\n"
        "## gate\nRun `mise run check` before any commit.\n\n"
        "## substrate\nGit-worktree waves only.\n\n"
        "## seeds\nSeeds(<target>, prime|ready|blocked).\n\n"
        "## doctrine\nSee skills/agentic-sdlc/SKILL.md for the doctrine."
    ),
    "CLAUDE.md": (
        "## Claude command routing\n"
        "- /sdlc-init\n"
        "- /sdlc-frame\n"
        "- /sdlc-wave\n"
        "- /sdlc-mission"
    ),
}
CLAUDE_PREAMBLE = "@AGENTS.md\n"
EXCLUDED_SURFACES = [
    "PRIME apply",
    "workflow overlay",
    "gateway",
    "routing",
    "Seeds",
    "archives",
    "V7",
    "config",
    "queue mutation",
]


class InspectionError(Exception):
    """The target cannot be inspected safely."""


class NoAtimeError(Exception):
    """A file cannot be read while preserving its access time."""


def read_noatime(path: Path) -> bytes:
    noatime = getattr(os, "O_NOATIME", None)
    if noatime is None:
        raise NoAtimeError
    flags = os.O_RDONLY | noatime | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES, errno.EOPNOTSUPP, errno.ENOTSUP):
            raise NoAtimeError from exc
        raise
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError(errno.EINVAL, "not a regular file")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def node_mode(path: Path) -> int | None:
    try:
        return path.lstat().st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise InspectionError(f"cannot inspect target path: {path}") from exc


def regular_directory(path: Path, label: str) -> None:
    mode = node_mode(path)
    if mode is None or not stat.S_ISDIR(mode):
        raise InspectionError(f"{label} must be an existing directory")


def valid_git_head(path: Path) -> bool:
    try:
        raw = read_noatime(path / "HEAD")
    except (NoAtimeError, OSError):
        return False
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeError:
        return False
    if len(lines) != 1 or not lines[0] or "\x00" in lines[0]:
        return False
    value = lines[0]
    if value.startswith("ref: refs/"):
        return len(value) > len("ref: refs/") and not value.endswith("/")
    return len(value) in (40, 64) and all(character in "0123456789abcdefABCDEF" for character in value)


def git_common_directory(path: Path) -> Path | None:
    commondir_path = path / "commondir"
    mode = node_mode(commondir_path)
    if mode is None or not stat.S_ISREG(mode):
        return None
    try:
        raw = read_noatime(commondir_path)
    except (NoAtimeError, OSError):
        return None
    try:
        lines = raw.decode("utf-8", errors="strict").splitlines()
    except UnicodeError:
        return None
    if len(lines) != 1 or not lines[0] or "\x00" in lines[0]:
        return None
    common = Path(lines[0])
    return common if common.is_absolute() else path / common


def git_metadata_directory(path: Path) -> bool:
    mode = node_mode(path)
    if mode is None or not stat.S_ISDIR(mode):
        return False
    head_mode = node_mode(path / "HEAD")
    if head_mode is None or not stat.S_ISREG(head_mode) or not valid_git_head(path):
        return False
    common = git_common_directory(path)
    storage = common if common is not None else path
    objects_mode = node_mode(storage / "objects")
    refs_mode = node_mode(storage / "refs")
    if objects_mode is None or not stat.S_ISDIR(objects_mode):
        return False
    return refs_mode is not None and stat.S_ISDIR(refs_mode)


def gitfile_target(target: Path, path: Path) -> Path | None:
    try:
        raw = read_noatime(path)
    except NoAtimeError:
        return None
    except OSError:
        return None
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeError:
        return None
    lines = text.splitlines()
    if len(lines) != 1 or not lines[0].startswith("gitdir: "):
        return None
    value = lines[0][len("gitdir: "):]
    if not value or "\x00" in value:
        return None
    gitdir = Path(value)
    if not gitdir.is_absolute():
        gitdir = target / gitdir
    return gitdir


def git_baseline(target: Path) -> dict[str, str]:
    path = target / ".git"
    mode = node_mode(path)
    if mode is None:
        return {"id": "git-baseline", "action": "create"}
    if stat.S_ISDIR(mode):
        valid = git_metadata_directory(path)
    elif stat.S_ISREG(mode):
        gitdir = gitfile_target(target, path)
        valid = gitdir is not None and git_metadata_directory(gitdir)
    else:
        return {"id": "git-baseline", "action": "refuse", "reason": "unsafe-node"}
    if valid:
        return {"id": "git-baseline", "action": "adopt"}
    return {"id": "git-baseline", "action": "refuse", "reason": "invalid-git-metadata"}


def marker_status(text: str) -> str:
    starts = text.count(MARKER_START)
    ends = text.count(MARKER_END)
    if starts == 0 and ends == 0:
        return "absent"
    if starts == 1 and ends == 1 and text.index(MARKER_START) < text.index(MARKER_END):
        return "well-formed"
    if starts > 1 or ends > 1:
        return "duplicate-marker"
    return "malformed-marker"


def marked_body(text: str) -> str:
    start = text.index(MARKER_START) + len(MARKER_START)
    end = text.index(MARKER_END)
    return text[start:end].strip("\n")


def instruction_item(target: Path, name: str) -> dict[str, str]:
    item_id = f"instructions:{name}"
    path = target / name
    mode = node_mode(path)
    if mode is None:
        return {"id": item_id, "action": "create"}
    if not stat.S_ISREG(mode):
        return {"id": item_id, "action": "refuse", "reason": "unsafe-node"}
    try:
        text = read_noatime(path).decode("utf-8", errors="strict")
    except NoAtimeError:
        return {"id": item_id, "action": "refuse", "reason": "no-atime-unavailable"}
    except UnicodeError:
        return {"id": item_id, "action": "refuse", "reason": "non-utf8"}
    except OSError:
        return {"id": item_id, "action": "refuse", "reason": "unreadable"}
    status = marker_status(text)
    if status in ("duplicate-marker", "malformed-marker"):
        return {"id": item_id, "action": "refuse", "reason": status}
    if status == "absent":
        return {"id": item_id, "action": "merge"}
    canonical = marked_body(text) == CANONICAL_INSTRUCTION_CONTENT[name]
    if name == "CLAUDE.md":
        canonical = canonical and text.startswith(CLAUDE_PREAMBLE)
    return {"id": item_id, "action": "adopt" if canonical else "merge"}


def inspect(target: Path) -> tuple[dict[str, object], int]:
    regular_directory(target, "target")
    items: list[dict[str, object]] = [
        git_baseline(target),
        instruction_item(target, "AGENTS.md"),
        instruction_item(target, "CLAUDE.md"),
        {"id": "excluded-surfaces", "action": "skip", "scope": EXCLUDED_SURFACES},
    ]
    refusal = next((item for item in items if item["action"] == "refuse"), None)
    if refusal is None:
        readiness = {"state": "READY", "reason": "no_refusals"}
        exit_code = EXIT_READY
    else:
        readiness = {
            "state": "NOT_READY",
            "reason": f"{refusal['id']}/{refusal['reason']}",
        }
        exit_code = EXIT_NOT_READY
    return {
        "schema": SCHEMA,
        "target": os.path.abspath(target),
        "items": items,
        "preview_readiness": readiness,
    }, exit_code


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result, exit_code = inspect(arguments.target)
    except InspectionError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return EXIT_INPUT
    json.dump(result, sys.stdout, ensure_ascii=True, separators=(",", ":"))
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
