#!/usr/bin/env python3
"""Emit a deterministic, read-only activation preview for one local target."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

SCHEMA = "agentic-sdlc/offline-inspect@1"

#: The ONE reader of `.git` metadata, shared with the receipted lifecycle verbs (agentic-sdlc-7a2b,
#: W4). It is a plain sibling of this file inside the skill payload, so it travels with an installed
#: copy exactly as this tool does -- which is why the shared module lives here rather than under the
#: distribution's `scripts/`, where a copy-mode install could not reach it. There is deliberately no
#: fallback copy of the shape checks in this file: two readers of one subject is the defect the
#: extraction removed, and an absent sibling is a named refusal instead.
DETECTOR_NAME = "git_project_detector.py"

# EXITS, as one derivation point (product-spec Implementation Decision 9; the machine-readable
# `exit_codes` map that used to restate it went with the acquisition engine, so this comment and
# the constants below are now the only statement of it). This command opens nothing
# for writing, spawns no process, touches no network, and mutates no target, so 3 and 4 are
# UNREACHABLE rather than merely unused: a command that can cause no effect can neither refuse
# before one nor admit a partial one. That follows from Decision 9's own definitions of 3 and 4, so
# it needs no precedent to lean on.
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


def load_detector() -> ModuleType:
    """Load the shared `.git` reader from beside this file, or refuse by name.

    An exact physical sibling, never resolved through ambient `sys.path` and never followed through a
    link: the same admission shape the distribution's own modules use for their siblings. A missing
    or linked sibling is an input failure (exit 2), because nothing was inspected.
    """
    path = Path(__file__).resolve().with_name(DETECTOR_NAME)
    if path.is_symlink() or not path.is_file():
        raise InspectionError(f"the shared git-metadata reader is absent or is a link: {path}")
    specification = importlib.util.spec_from_file_location("_offline_inspect_git_detector", path)
    if specification is None or specification.loader is None:
        raise InspectionError(f"the shared git-metadata reader cannot be loaded: {path}")
    module = importlib.util.module_from_spec(specification)
    # Registered BEFORE execution, not as bookkeeping: `dataclasses` resolves a decorated class's
    # module through `sys.modules`, so a module holding a `@dataclass` and executed unregistered dies
    # with `'NoneType' object has no attribute '__dict__'`.
    sys.modules[specification.name] = module
    try:
        specification.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - an import failure here inspected nothing
        raise InspectionError(f"the shared git-metadata reader failed to load: {path}: {exc}") from exc
    return module


def node_mode(path: Path) -> int | None:
    """This tool's own stat helper, kept for the INSTRUCTION items after the git shape checks moved.

    It differs from the shared reader's identically-named helper in exactly one way, and the
    difference is the contract: an unreadable path here is an input failure this command reports at
    exit 2 (`InspectionError`), where the shared reader propagates the `OSError` for its caller to
    classify. `git_baseline` restores this behaviour at its own boundary.
    """
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


def git_baseline(target: Path, detector: ModuleType) -> dict[str, str]:
    """Render the shared reader's verdict in this tool's own three-action vocabulary.

    The four verdicts map one-to-one onto what this tool already said, which is why the extraction
    changed no output: `absent` is a baseline this activation would `create`, `admitted` is one it
    would `adopt`, and the two refusals keep their own names. An `OSError` escaping the reader is
    re-raised as this command's input failure, so a permission-denied target still lands on exit 2
    exactly as the measured residual at the top of this file records.
    """
    try:
        admission = detector.admit(target)
    except OSError as exc:
        raise InspectionError(f"cannot inspect target path: {target / '.git'}") from exc
    if admission.verdict == detector.ABSENT:
        return {"id": "git-baseline", "action": "create"}
    if admission.verdict == detector.ADMITTED:
        return {"id": "git-baseline", "action": "adopt"}
    return {"id": "git-baseline", "action": "refuse", "reason": admission.verdict}


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


def instruction_item(target: Path, name: str, detector: ModuleType) -> dict[str, str]:
    """Preview one instruction file, reading it through the shared atime-preserving reader.

    The reader's `kind` IS this tool's refusal reason for the two failures it distinguishes
    (`no-atime-unavailable`, `unreadable`), so the vocabulary is carried across the seam rather than
    re-derived from the prose of an exception.
    """
    item_id = f"instructions:{name}"
    path = target / name
    mode = node_mode(path)
    if mode is None:
        return {"id": item_id, "action": "create"}
    if not stat.S_ISREG(mode):
        return {"id": item_id, "action": "refuse", "reason": "unsafe-node"}
    try:
        text = detector.read_without_atime(path).decode("utf-8", errors="strict")
    except detector.MetadataUnreadable as exc:
        return {"id": item_id, "action": "refuse", "reason": exc.kind}
    except UnicodeError:
        return {"id": item_id, "action": "refuse", "reason": "non-utf8"}
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
    detector = load_detector()
    items: list[dict[str, object]] = [
        git_baseline(target, detector),
        instruction_item(target, "AGENTS.md", detector),
        instruction_item(target, "CLAUDE.md", detector),
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
