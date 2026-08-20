#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Capture, seal, and verify the PlanningSnapshot -- the OBSERVED half of the planning artifact chain.

`docs/plans/claude-code-first-harness/to-spec-handoff.md` places two artifacts first:

    MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope

and issue 16 ("Planning artifact chain and deterministic compiler", lines 28-34) says what this half
owns: the snapshot "records observed current state and its evidence independently from desired
state", and it "binds the physical repository/worktree identity; admitted commit, tree, dirty-state,
and custody summaries; queue and dependency state; selected distribution and activation receipts;
host capabilities; route and rightsizing evidence; applicable policies and ADRs; active or retained
wave artifacts; and named unknowns."

THE ONE PROPERTY THIS FILE EXISTS FOR. Seed `agentic-sdlc-5ee7` records that "a stale matched
plan+apply pair from an earlier cleaner tree plus a fresh passing gate receipt derives write-ready,
because no operand artifact carries head or time linkage that a read-only composer could check".
The remedy is split: this tool is where the ANCHOR is recorded, and the separate plan-admission check
is where it is enforced. So every sealed snapshot durably names the EXACT head it observed, and
`capture` RE-READS the head immediately before sealing: a head that moved between the first
observation and the seal is a named refusal, because a document naming one head while the tree moved
to another is precisely the stale-but-plausible artifact the seed is about.

NEVER RECORD A VALUE YOU DID NOT OBSERVE. This is the whole discipline of an observed-state artifact,
and it has three edges:

  * A dimension this tool cannot observe is a NAMED UNKNOWN -- it appears in `unknowns` by its own
    dotted name with the reason it could not be observed -- never a guess, a default, or a silent
    omission. Four of issue 16's dimensions are unobservable BY CONSTRUCTION here: the selected
    distribution receipt and the activation receipts live outside the repository under state
    directories this tool does not read, route and rightsizing evidence is a pre-spawn contract this
    tool does not resolve, and dependency state between queue records is a judgment rather than a
    read. Those four are named in every snapshot. A future version that genuinely observes one of
    them adds a field and a schema version; it does not quietly stop naming it.
  * The naming rule runs BOTH WAYS and is checked: a null-valued nullable dimension MUST be named,
    and a dimension carrying an observed value MUST NOT be named. "Unknown" and "recorded" are
    disjoint, so no consumer can read a value out of a dimension the snapshot also calls unknown.
  * The queue's ABSENCE is an explicit observed shape, not an unknown: `queue.state` is `absent`,
    its digest and record count are null, and neither is named. Absence observed is not absence of
    observation.

TWO COMMANDS, ONE DIGEST.

    capture  reads git and local evidence for one supplied repository and emits the SEALED snapshot:
             the observed body plus exactly one added key, `digest`.
    verify   reads a SEALED snapshot, re-derives its digest and its shape, and refuses when either
             disagrees. `--expect-digest` is the binding a downstream consumer uses.

The digest contract is this family's, and there is only one way to compute it:

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

where `canonical` is `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`,
`allow_nan=False`, and exactly one trailing newline. The `digest` key is excluded BY NAME rather than
by position, so the derivation does not depend on any ordering the encoder happens to produce, and
`capture` never accepts a supplied digest -- the value has exactly one origin.

ONE SCHEMA, ONE VALIDATOR. `capture` validates the body it just built with the SAME closed-schema
validators `verify` runs, so a capture bug becomes a refusal rather than a sealed document that
`verify` would later reject. The schema is CLOSED at every level: an unrecognised field is refused
rather than ignored, because a field this version does not understand is a meaning it cannot honour.
Every set-shaped list has ONE spelling -- `worktrees` ascending by path, `policy_digests` and
`wave_artifacts` ascending by path, `unknowns` ascending by dimension, each strictly, so a reordered
or repeated entry cannot be a second spelling that derives a different digest.

NO CLOCK. `stated_at` is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would stamp
honest evidence with a time that moves backwards. It is the family's fixed-width
`YYYY-MM-DDTHH:MM:SSZ` form whose lexicographic order is chronological. The instant is therefore the
caller's claim about when the observation happened; the HEAD is this tool's own observation, which is
why the anchor the seed asks for is the head and not the clock.

READ-ONLY, AND THE OUTPUT CANNOT LAND IN WHAT IT OBSERVES. `capture` runs git with a constructed
environment, no repository writes, and no lock acquisition. `--out` is refused when it names an
existing path of any kind (checked with `lstat`, so a dangling symlink is refused too), when its
parent is not an existing directory, and when it resolves inside the observed worktree or the
observed git directory -- a snapshot written into the tree it describes would change that tree's
dirty state and make its own record wrong. The file is created O_EXCL, so a racer cannot be
clobbered even after the pre-check.

ENVIRONMENT. Exactly three variables are read, all three only so a bare `git`/`uv` name can be
resolved to an executable: PATH, PATHEXT, SYSTEMROOT. Everything the child sees is CONSTRUCTED
(`GIT_CONFIG_GLOBAL`/`GIT_CONFIG_SYSTEM` are `os.devnull`, `GIT_CONFIG_NOSYSTEM` and
`GIT_ATTR_NOSYSTEM` are set, `GIT_OPTIONAL_LOCKS` is 0, locale is C), so no ambient `GIT_*` control
can move an observation and no operator config can rewrite what git reports. Passing `--git`/`--uv`
an absolute path removes even the PATH read.

FAIL CLOSED, AND NAME THE REASON. Every predicate accumulates named reasons against its own check
group; then ONE selection runs over ONE partition, so no input can yield two verdicts or none. A
bare "invalid" is useless to the human it asks, so every reason names the dimension and what was
wrong with it. Refusing is this module SUCCEEDING, which is why it exits 0.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. This module's exit space is 0, 2, and 1 only. A derived `refused` is a
RESULT (0), not a clean refusal (3), because the refusal happens before anything is written and there
was no effect to refuse before. 4 is unreachable: the single write is O_EXCL and all-or-nothing, so
there is no partial state to admit. Exit 2 covers a supplied file that cannot be read as ONE JSON
object -- unreadable, not a regular file, not JSON, not an object, a repeated key, a non-finite
number -- and arguments that are themselves unusable, such as a `--repository` that is not an
existing directory or an `--at` that is not the family's instant: that is the QUESTION being unusable
rather than the answer being "refused". 1 covers a derived result that could not be DELIVERED --
`--out` failing after the derivation, or a stdout that cannot receive the one result document --
because a snapshot sealed and not delivered is not a success. When `--out` succeeded and only stdout
failed, the stderr line says so, because the file outliving a nonzero exit is the one effect a
consumer could otherwise be surprised by.

RESIDUALS, STATED EXACTLY.

  * The digest is RE-DERIVATION, not a security boundary. A same-OS-user forger can write a
    self-consistent sealed document; what the check catches is drift, a hand-edit, and a mismatched
    pair of artifacts.
  * The HEAD is anchored between two observations; nothing else is. The index, working tree, queue,
    worktree list, and every digested file are read ONCE, so an edit landing after that read and
    before the seal is not detected. The snapshot's dirty-state and digests are true as of their own
    read, not as of the seal.
  * `verify` re-observes NO repository. It proves a document is internally consistent and is the
    document a digest names; it cannot prove the recorded head is the CURRENT head. Comparing the
    recorded head against the current head is the separate plan-admission check's job, and until that
    check exists the anchor is recorded but not enforced.
  * git's own reporting IS the observation. A lying executable on the supplied `--git` path, a
    same-UID racer, and a filesystem that reuses a device/inode pair are all undetected here.
  * `untracked` counts porcelain entries under `--untracked-files=all`, which is one entry per file.
    `staged`, `unstaged`, and `unmerged` count entries, not hunks or lines, and no path or content
    ever enters the document.
  * ADR APPLICABILITY IS A JUDGMENT, not an observation. The digested policy set is exactly the
    `policy/*.json` files present; the prose ADRs under `docs/adr/` are not digested here, and which
    decision applies to a wave is the compiler's and the reviewer's call.
  * There is no timeout on a git observation, deliberately: a bounded wait would turn a slow status
    in a large tree into a false refusal. A hung git hangs `capture`.
  * A sealed snapshot is EVIDENCE. It authorizes no dispatch, no write, no push, publication, PR
    mutation, merge, or deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
RESULT_SCHEMA = "agentic-sdlc/planning-snapshot-result@1"

VERDICT_CAPTURED = "captured"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_CAPTURED: (
        "the observed state is closed and well-formed, the recorded head is the head that was still "
        "current when the document was sealed, and the sealed document carries the one digest a wave "
        "plan may bind; the snapshot is evidence and authorizes nothing"
    ),
    VERDICT_VERIFIED: (
        "the sealed document re-derives its own digest and satisfies the closed schema, so it is the "
        "same snapshot it claims to be; whether its recorded head is still current is NOT checked "
        "here, and the snapshot is evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "no snapshot was sealed, no digest was derived, and nothing was written; the reasons name "
        "each dimension and what was wrong with it"
    ),
}

# Implementation Decision 9, minus the two codes this command's all-or-nothing write cannot use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

DIGEST_KEY = "digest"

#: The closed body: every key is REQUIRED, so an absence is always a named refusal and never a
#: default. `capture` builds exactly this set; `verify` reads it plus `digest`.
BODY_KEYS = (
    "dirty_state",
    "head",
    "host_capabilities",
    "policy_digests",
    "queue",
    "repository",
    "schema",
    "stated_at",
    "unknowns",
    "wave_artifacts",
    "worktrees",
)
SEALED_KEYS = tuple(sorted(BODY_KEYS + (DIGEST_KEY,)))

#: Every nested object, also closed.
REPOSITORY_KEYS = ("git_dir", "git_dir_device", "git_dir_inode", "worktree_path")
HEAD_KEYS = ("branch", "commit_sha", "tree_sha")
DIRTY_KEYS = ("staged", "unmerged", "unstaged", "untracked")
QUEUE_KEYS = ("path", "records", "sha256", "state")
CAPABILITY_KEYS = ("git", "python", "uv")
WORKTREE_KEYS = ("branch", "head", "path")
FILE_DIGEST_KEYS = ("path", "sha256")
UNKNOWN_KEYS = ("dimension", "reason")

#: The queue has exactly three observable shapes and each one fixes what may be null.
QUEUE_STATES = ("absent", "present", "unreadable")
QUEUE_PATH = ".seeds/issues.jsonl"

POLICY_GLOB_DIR = "policy"
WAVE_ARTIFACT_GLOB_DIR = ".sdlc"

#: Named unknowns are a CLOSED vocabulary of dimension names, because a downstream consumer that
#: refuses to plan around a specific missing dimension has to be able to name it exactly. A name may
#: be suffixed with ":<detail>" for a per-path dimension, where the detail is the path that could not
#: be digested.
UNKNOWN_DIMENSIONS = (
    "activation_receipts",
    "dependency_state",
    "distribution_receipt",
    "head.branch",
    "host_capabilities.git",
    "host_capabilities.uv",
    "policy_digests",
    "queue.records",
    "queue.sha256",
    "route_and_rightsizing_evidence",
    "wave_artifacts",
    "worktrees.branch",
    "worktrees.head",
)

#: Only these two bases are PER-PATH dimensions: `observe_file_digests` is the one call site that
#: ever emits a ":<detail>" suffix, and only for these two directories. Every other base names a
#: single scalar or object field with no per-path detail to append, so a suffix there is not a
#: refinement of the same dimension -- it is a DIFFERENT string, and the nullable-naming and
#: queue-state cross-checks below compare dimension names EXACTLY, so a suffixed alias of e.g.
#: `head.branch` would silently fail to be recognised as `head.branch` at all.
DETAILED_UNKNOWN_DIMENSIONS = ("policy_digests", "wave_artifacts")

#: The four dimensions this tool NEVER observes. Every snapshot names all four, and `verify` refuses
#: one that does not: silence about them would read as "nothing to report" rather than "not observed".
REQUIRED_UNKNOWNS = {
    "activation_receipts": (
        "activation receipts live outside the observed repository under an operator state directory "
        "this tool does not read, so no receipt was observed"
    ),
    "dependency_state": (
        "dependency edges between queue records are a judgment over record bodies, not a read, and "
        "this tool records no record body, so no dependency state was observed"
    ),
    "distribution_receipt": (
        "the selected distribution receipt lives outside the observed repository under an operator "
        "state directory this tool does not read, so no receipt was observed"
    ),
    "route_and_rightsizing_evidence": (
        "an exact runtime route is resolved by the separate pre-spawn contract, not by an observation "
        "of the repository, so no route or rightsizing evidence was observed"
    ),
}

#: A nullable dimension is named in `unknowns` if and only if its value is null. `queue.sha256` and
#: `queue.records` are absent here because the queue's own state fixes their rule; see `check_queue`.
NULLABLE_DIMENSIONS = (
    "head.branch",
    "host_capabilities.git",
    "host_capabilities.uv",
    "worktrees.branch",
    "worktrees.head",
)

SHAPE_CHECKS = (
    "closed-key-set",
    "repository-identity",
    "head-observation",
    "dirty-state",
    "worktree-custody",
    "queue-state",
    "host-capabilities",
    "policy-digests",
    "wave-artifacts",
    "named-unknowns",
)
#: `head-stability` and `output-path` exist only for `capture`: `verify` re-observes nothing and
#: writes nothing, so reporting them as "met" there would claim a check that never ran.
CAPTURE_CHECKS = SHAPE_CHECKS + ("head-stability", "output-path", "digest")
VERIFY_CHECKS = SHAPE_CHECKS + ("digest",)
ALL_CHECKS = tuple(dict.fromkeys(CAPTURE_CHECKS + VERIFY_CHECKS))
CHECKS_BY_COMMAND = {"capture": CAPTURE_CHECKS, "verify": VERIFY_CHECKS}

#: Carried in every document, because a consumer that binds the digest should carry what it does not
#: prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "only the head is anchored between two observations: the index, working tree, queue, worktree "
    "list, and digested files are read once, so an edit landing after that read and before the seal "
    "is not detected",
    "verify re-observes no repository, so a verified snapshot may still name a head that is no "
    "longer current; comparing the recorded head against the current head is plan admission's job",
    "git's own reporting is the observation: a lying executable on the supplied --git path, a "
    "same-UID racer, and a reused device/inode pair are undetected",
    "the digested policy set is exactly the policy/*.json files present; which ADR applies to a wave "
    "is a judgment this tool does not make",
    "a sealed snapshot is evidence: it authorizes no dispatch, no write, and no outward effect",
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
#: A git object name is 40 hexadecimal characters under SHA-1 and 64 under SHA-256; both are admitted
#: because a repository's object format is the repository's choice, not this tool's.
_OBJECT_NAME = re.compile(r"([0-9a-f]{40}|[0-9a-f]{64})\Z")
_VERSION = re.compile(r"[0-9]+(\.[0-9]+)*([-+.][0-9A-Za-z.+-]+)?\Z")
_BRANCH_REF = re.compile(r"refs/heads/(.+)\Z", re.DOTALL)


class InputError(Exception):
    """A supplied file or argument cannot be used at all (exit 2).

    Deliberately separate from a named reason: unusable input means the QUESTION could not be asked,
    while a reason means it was asked and the answer is "refused".
    """


class ObservationError(Exception):
    """One observation could not be made. Always converted into a named reason by its caller."""


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def snapshot_digest(document: dict[str, Any]) -> str:
    """The ONE digest derivation: sha256 over the canonical bytes of the document minus `digest`.

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest snapshot carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a snapshot carrying two `head`s parses
    to whichever the writer put second. That is a document with two meanings, and picking one of them
    would also give the one digest two possible values.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"a supplied document repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


def _assert_finite(value: Any, where: str) -> None:
    """Refuse a non-finite float that no constant token announced.

    `parse_constant` catches the `NaN`/`Infinity` spellings, and nothing else: the literal `1e400`
    is a perfectly ordinary JSON number that overflows to `inf` during parsing without ever passing
    through that hook. It has to be refused because `canonical_bytes` runs with `allow_nan=False`, so
    an infinity reaching the digest derivation would raise out of this module as a traceback instead
    of being classified.
    """
    if isinstance(value, float) and not math.isfinite(value):
        raise InputError(f"{where} carries the non-finite number {value!r}, which no digest can cover")
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_finite(item, f"{where} at key {key!r}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_finite(item, f"{where} at position {index}")


def load_document(path: str, label: str) -> dict[str, Any]:
    """Read one supplied document. Every failure here is unusable input (exit 2), never a reason.

    The regular-file check runs BEFORE the read: opening a FIFO blocks until a writer shows up, which
    for a supplied path may be never, so a directory mistake would exit 2 promptly while a FIFO
    mistake hung forever. `Path.stat()` follows a symlink to its target, which is the question this
    asks -- "is what I would read a regular file" -- rather than "is the path itself one".
    """
    candidate = Path(path)
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise InputError(f"cannot read the {label} {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise InputError(f"the {label} {path} is not a regular file, so it cannot be read")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read the {label} {path}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_nonfinite)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} {path} is not a JSON object")
    _assert_finite(value, f"the {label} {path}")
    return value


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the document can say which part of the schema is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree. The flat
    list walks EVERY group rather than the command's own subset: a reason noted against a group this
    command does not report must still reach the verdict.
    """

    def __init__(self, command: str) -> None:
        self.order = CHECKS_BY_COMMAND.get(command, ALL_CHECKS)
        self.groups: dict[str, list[str]] = {slug: [] for slug in ALL_CHECKS}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in ALL_CHECKS:
            flat.extend(self.groups[slug])
        return flat

    def document(self) -> list[dict[str, Any]]:
        return [
            {"met": not self.groups[slug], "reasons": self.groups[slug], "slug": slug}
            for slug in ALL_CHECKS
            if slug in self.order or self.groups[slug]
        ]

    def verdict(self, command: str) -> str:
        """Exactly one verdict, always.

        The selection is one partition over one value, so two verdicts are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no verdict --
        and it is a named reason rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command == "capture":
            return VERDICT_CAPTURED
        if command == "verify":
            return VERDICT_VERIFIED
        self.note(
            "closed-key-set",
            f"no verdict follows from the command {command!r}, and an underivable verdict is a "
            "refusal rather than a guess",
        )
        return VERDICT_REFUSED


class Unknowns:
    """The named-unknown collector: one dimension, one reason, one spelling.

    Naming the same dimension twice with the SAME reason is idempotent, because two observations can
    legitimately fail for one stated cause. Naming it twice with DIFFERENT reasons is this module
    contradicting itself, so it is recorded as such rather than resolved by picking one.
    """

    def __init__(self) -> None:
        self.named: dict[str, str] = {}
        self.conflicts: list[str] = []

    def name(self, dimension: str, reason: str) -> None:
        existing = self.named.get(dimension)
        if existing is None:
            self.named[dimension] = reason
            return
        if existing != reason:
            self.conflicts.append(
                f"the unknown dimension {dimension!r} was named twice with different reasons "
                f"({existing!r} and {reason!r}), so what was unobservable about it is not established"
            )

    def entries(self) -> list[dict[str, str]]:
        return [
            {"dimension": dimension, "reason": self.named[dimension]}
            for dimension in sorted(self.named)
        ]


# ---- field predicates ----------------------------------------------------------------------------
# Each returns the well-formed value, or None having noted its own named reason. Returning None means
# "this dimension cannot be reasoned about further", which is how a cross-field check below knows to
# stay silent instead of printing a second reason about the same mistake.


def _text(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        assessment.note(
            slug,
            f"{what} is not a non-empty string (found {value!r}), so what it records cannot be read",
        )
        return None
    return value


def _absolute_path(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    """An absolute path in EITHER path family, so a Linux snapshot is readable on Windows and back.

    `pathlib.Path` is the reading host's flavour, and the question here is about the WRITING host's
    filesystem, which the reading host cannot re-observe.
    """
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not (PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()):
        assessment.note(
            slug,
            f"{what} is {value!r}, which is not an absolute path in either path family; a physical "
            "identity that has to be resolved against some other directory is not an identity",
        )
        return None
    return value


def _count(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> int | None:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        assessment.note(
            slug,
            f"{what} is not an integer of at least 0 (found {value!r}); a count that is not a count "
            "cannot summarize anything",
        )
        return None
    return value


def _object_name(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    if not isinstance(value, str) or not _OBJECT_NAME.match(value):
        assessment.note(
            slug,
            f"{what} is not 40 or 64 lowercase hexadecimal characters (found {value!r}), so it cannot "
            "be a git object name",
        )
        return None
    return value


def _digest_value(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    if not isinstance(value, str) or not _HEX64.match(value):
        assessment.note(
            slug,
            f"{what} is not 64 lowercase hexadecimal characters (found {value!r}), so it cannot be a "
            "sha256 over any canonical document",
        )
        return None
    return value


def _instant(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or not _TIME.match(value):
        assessment.note(
            slug,
            f"{what} is not a YYYY-MM-DDTHH:MM:SSZ instant (found {value!r}); this tool reads no "
            "clock, so the instant is the caller's to state exactly",
        )
        return None
    return value


def _closed_object(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, keys: tuple[str, ...], what: str
) -> dict[str, Any] | None:
    value = container.get(key)
    if not isinstance(value, dict):
        assessment.note(
            slug,
            f"{what} is not a JSON object (found {value!r}), so its {', '.join(keys)} cannot be read",
        )
        return None
    for name in sorted(set(keys) - set(value)):
        assessment.note(slug, f"{what} carries no {name}, which {SNAPSHOT_SCHEMA} requires")
    for name in sorted(set(value) - set(keys)):
        assessment.note(
            slug,
            f"{what} carries the unknown field {name!r}; it is a closed object, so an unrecognised "
            "field is refused rather than ignored",
        )
    if set(value) != set(keys):
        return None
    return value


def _closed_list(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, keys: tuple[str, ...], what: str
) -> list[dict[str, Any]] | None:
    """A list of closed objects. An empty list is admitted: nothing observed is an observation."""
    value = container.get(key)
    if not isinstance(value, list):
        assessment.note(slug, f"{what} is not a JSON list (found {value!r}), so its entries cannot be read")
        return None
    entries: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        entry = _closed_object(assessment, slug, {"item": item}, "item", keys, f"{what} at position {index}")
        if entry is None:
            return None
        entries.append(entry)
    return entries


def _strictly_ascending(
    assessment: Assessment, slug: str, entries: list[dict[str, Any]], key: str, what: str
) -> None:
    order = [entry.get(key) for entry in entries]
    if not all(isinstance(item, str) for item in order):
        return
    if any(later <= earlier for earlier, later in zip(order, order[1:])):
        assessment.note(
            slug,
            f"{what} is not sorted strictly ascending by {key} (found {order}); one observed set has "
            "one spelling, and a reordered or repeated entry is a second spelling of it that would "
            "derive a different digest",
        )


# ---- check groups --------------------------------------------------------------------------------


def check_key_set(assessment: Assessment, document: dict[str, Any], command: str) -> None:
    """The closed schema itself: exactly these keys, no more and no fewer.

    `capture` and `verify` differ by exactly one key, and the difference is checked in both
    directions: a body `capture` built may NOT carry a digest, and a document handed to `verify` MUST.
    """
    expected = set(SEALED_KEYS) if command == "verify" else set(BODY_KEYS)
    present = set(document)
    for key in sorted(expected - present):
        assessment.note(
            "closed-key-set",
            f"the planning snapshot carries no {key}, which the closed {SNAPSHOT_SCHEMA} schema "
            "requires of every snapshot",
        )
    for key in sorted(present - expected):
        if command == "capture" and key == DIGEST_KEY:
            assessment.note(
                "closed-key-set",
                "the observed body already carries a digest, which is DERIVED from the body and never "
                "supplied: accepting one would give the single load-bearing value a second origin",
            )
            continue
        assessment.note(
            "closed-key-set",
            f"the planning snapshot carries the unknown field {key!r}; {SNAPSHOT_SCHEMA} is a closed "
            "schema, so a field this version cannot honour is refused rather than ignored",
        )
    schema = document.get("schema")
    if "schema" in document and schema != SNAPSHOT_SCHEMA:
        assessment.note(
            "closed-key-set",
            f"the planning snapshot declares schema {schema!r}, not {SNAPSHOT_SCHEMA}, so which field "
            "set and which digest derivation it is about is not established",
        )
    _instant(assessment, "closed-key-set", document, "stated_at", "the planning snapshot's stated_at")


def check_repository(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "repository-identity"
    repository = _closed_object(
        assessment, slug, document, "repository", REPOSITORY_KEYS, "the planning snapshot's repository"
    )
    if repository is None:
        return
    _absolute_path(assessment, slug, repository, "worktree_path", "the planning snapshot's repository.worktree_path")
    _absolute_path(assessment, slug, repository, "git_dir", "the planning snapshot's repository.git_dir")
    _count(assessment, slug, repository, "git_dir_device", "the planning snapshot's repository.git_dir_device")
    _count(assessment, slug, repository, "git_dir_inode", "the planning snapshot's repository.git_dir_inode")


def check_head(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "head-observation"
    head = _closed_object(assessment, slug, document, "head", HEAD_KEYS, "the planning snapshot's head")
    if head is None:
        return
    _object_name(assessment, slug, head.get("commit_sha"), "the planning snapshot's head.commit_sha")
    _object_name(assessment, slug, head.get("tree_sha"), "the planning snapshot's head.tree_sha")
    branch = head.get("branch")
    if branch is not None and (not isinstance(branch, str) or not branch):
        assessment.note(
            slug,
            f"the planning snapshot's head.branch is {branch!r}, which is neither a non-empty branch "
            "name nor null; a detached head has no branch to record, and null is how that is said",
        )


def check_dirty_state(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "dirty-state"
    dirty = _closed_object(
        assessment, slug, document, "dirty_state", DIRTY_KEYS, "the planning snapshot's dirty_state"
    )
    if dirty is None:
        return
    for key in DIRTY_KEYS:
        _count(assessment, slug, dirty, key, f"the planning snapshot's dirty_state.{key}")


def check_worktrees(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "worktree-custody"
    entries = _closed_list(
        assessment, slug, document, "worktrees", WORKTREE_KEYS, "the planning snapshot's worktrees"
    )
    if entries is None:
        return
    for index, entry in enumerate(entries):
        what = f"the planning snapshot's worktrees at position {index}"
        _absolute_path(assessment, slug, entry, "path", f"{what} path")
        head = entry.get("head")
        if head is not None:
            _object_name(assessment, slug, head, f"{what} head")
        branch = entry.get("branch")
        if branch is not None and (not isinstance(branch, str) or not branch):
            assessment.note(
                slug,
                f"{what} branch is {branch!r}, which is neither a non-empty branch name nor null",
            )
    _strictly_ascending(assessment, slug, entries, "path", "the planning snapshot's worktrees")


def check_queue(assessment: Assessment, document: dict[str, Any], named: set[str]) -> None:
    """The queue's three shapes, and which of them may leave a value null.

    ABSENT is an observed shape: there is no queue, so there is no digest and no count, and neither
    is a named unknown. UNREADABLE is the opposite: a queue exists and could not be read, so both are
    unknown BY NAME. PRESENT always has a digest -- the bytes were read to compute it -- while the
    record count may be unknown by name, because a line that is not one JSON object makes the count
    underivable without making the file's digest any less exact.
    """
    slug = "queue-state"
    queue = _closed_object(assessment, slug, document, "queue", QUEUE_KEYS, "the planning snapshot's queue")
    if queue is None:
        return
    path = _text(assessment, slug, queue, "path", "the planning snapshot's queue.path")
    if path is not None and path != QUEUE_PATH:
        assessment.note(
            slug,
            f"the planning snapshot's queue.path is {path!r}, not {QUEUE_PATH!r}; this schema records "
            "the one queue the flagship skill owns, and another path would be another question",
        )
    state = queue.get("state")
    if state not in QUEUE_STATES:
        assessment.note(
            slug,
            f"the planning snapshot's queue.state is {state!r}, which is not one of the closed "
            f"vocabulary {list(QUEUE_STATES)}",
        )
        return
    digest = queue.get("sha256")
    records = queue.get("records")
    if state == "present":
        _digest_value(assessment, slug, digest, "the planning snapshot's queue.sha256")
        if "queue.sha256" in named:
            assessment.note(
                slug,
                "the planning snapshot records a present queue's sha256 and also names queue.sha256 "
                "as unknown; an observed value and an unobserved dimension are disjoint",
            )
        if records is not None:
            _count(assessment, slug, queue, "records", "the planning snapshot's queue.records")
        if (records is None) != ("queue.records" in named):
            assessment.note(
                slug,
                f"the planning snapshot's queue.records is {records!r} while unknowns "
                f"{'names' if 'queue.records' in named else 'does not name'} queue.records: a null "
                "count must say by name why it could not be derived, and a derived count is not "
                "unknown",
            )
        return
    for key, value in (("sha256", digest), ("records", records)):
        if value is not None:
            assessment.note(
                slug,
                f"the planning snapshot's queue.state is {state!r} yet queue.{key} is {value!r}; a "
                "queue that was not read has nothing observed about its contents",
            )
        expected = state == "unreadable"
        if (f"queue.{key}" in named) != expected:
            assessment.note(
                slug,
                f"the planning snapshot's queue.state is {state!r} and unknowns "
                f"{'names' if f'queue.{key}' in named else 'does not name'} queue.{key}: an "
                "unreadable queue names both by name, and an absent queue names neither, because "
                "absence observed is not absence of observation",
            )


def check_capabilities(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "host-capabilities"
    capabilities = _closed_object(
        assessment, slug, document, "host_capabilities", CAPABILITY_KEYS,
        "the planning snapshot's host_capabilities",
    )
    if capabilities is None:
        return
    python = _text(assessment, slug, capabilities, "python", "the planning snapshot's host_capabilities.python")
    if python is not None and not _VERSION.match(python):
        assessment.note(
            slug,
            f"the planning snapshot's host_capabilities.python is {python!r}, which is not a version "
            "string; the interpreter that made the observations reports its own version exactly",
        )
    for key in ("git", "uv"):
        value = capabilities.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not _VERSION.match(value):
            assessment.note(
                slug,
                f"the planning snapshot's host_capabilities.{key} is {value!r}, which is neither a "
                "version string nor null",
            )


def check_file_digests(assessment: Assessment, document: dict[str, Any], key: str, slug: str) -> None:
    entries = _closed_list(
        assessment, slug, document, key, FILE_DIGEST_KEYS, f"the planning snapshot's {key}"
    )
    if entries is None:
        return
    for index, entry in enumerate(entries):
        what = f"the planning snapshot's {key} at position {index}"
        path = _text(assessment, slug, entry, "path", f"{what} path")
        if path is not None and (path.startswith("/") or "\\" in path or ".." in path.split("/")):
            assessment.note(
                slug,
                f"{what} path is {path!r}, which is not a forward-slash relative path inside the "
                "observed repository; a digest of something outside the repository is not a "
                "repository observation",
            )
        _digest_value(assessment, slug, entry.get("sha256"), f"{what} sha256")
    _strictly_ascending(assessment, slug, entries, "path", f"the planning snapshot's {key}")


def check_unknowns(assessment: Assessment, document: dict[str, Any]) -> set[str]:
    """The named-unknown list itself, and the four dimensions no snapshot may leave unnamed."""
    slug = "named-unknowns"
    entries = _closed_list(
        assessment, slug, document, "unknowns", UNKNOWN_KEYS, "the planning snapshot's unknowns"
    )
    if entries is None:
        return set()
    names: set[str] = set()
    for index, entry in enumerate(entries):
        what = f"the planning snapshot's unknowns at position {index}"
        dimension = _text(assessment, slug, entry, "dimension", f"{what} dimension")
        _text(assessment, slug, entry, "reason", f"{what} reason")
        if dimension is None:
            continue
        base = dimension.split(":", 1)[0]
        if base not in UNKNOWN_DIMENSIONS:
            assessment.note(
                slug,
                f"{what} dimension is {dimension!r}, whose name {base!r} is not one of the closed "
                f"vocabulary {list(UNKNOWN_DIMENSIONS)}; a consumer that refuses to plan around a "
                "missing dimension has to be able to name it exactly, so free text is refused",
            )
            continue
        if dimension != base and not dimension[len(base) + 1:]:
            assessment.note(
                slug,
                f"{what} dimension is {dimension!r}, which carries an empty detail after its colon",
            )
            continue
        if dimension != base and base not in DETAILED_UNKNOWN_DIMENSIONS:
            assessment.note(
                slug,
                f"{what} dimension is {dimension!r}, which suffixes {base!r} with a detail; only "
                f"{list(DETAILED_UNKNOWN_DIMENSIONS)} are per-path dimensions this tool ever digests "
                "one file at a time, so a detail on any other dimension is not a refinement of it -- "
                "it is a different name, and admitting it would let a snapshot record a value for "
                f"{base!r} while a decorated alias of the same dimension is separately called unknown",
            )
            continue
        names.add(dimension)
    _strictly_ascending(assessment, slug, entries, "dimension", "the planning snapshot's unknowns")
    for dimension in sorted(REQUIRED_UNKNOWNS):
        if dimension not in names:
            assessment.note(
                slug,
                f"the planning snapshot does not name {dimension} as unknown; this tool observes it "
                "in no case, so leaving it unnamed would read as nothing to report rather than not "
                "observed",
            )
    return names


def check_nullable_naming(assessment: Assessment, document: dict[str, Any], named: set[str]) -> None:
    """The both-ways rule: a null value is named, and a named dimension holds no value.

    Each probe returns None when the document's own shape check already refused that dimension, so a
    single mistake is named once rather than twice.
    """
    slug = "named-unknowns"
    head = document.get("head")
    worktrees = document.get("worktrees")
    capabilities = document.get("host_capabilities")

    def branch_missing() -> bool | None:
        if not isinstance(head, dict) or "branch" not in head:
            return None
        return head["branch"] is None

    def worktree_field_missing(field: str) -> Callable[[], bool | None]:
        def probe() -> bool | None:
            if not isinstance(worktrees, list) or not all(
                isinstance(entry, dict) and field in entry for entry in worktrees
            ):
                return None
            return any(entry[field] is None for entry in worktrees)

        return probe

    def capability_missing(field: str) -> Callable[[], bool | None]:
        def probe() -> bool | None:
            if not isinstance(capabilities, dict) or field not in capabilities:
                return None
            return capabilities[field] is None

        return probe

    probes: dict[str, Callable[[], bool | None]] = {
        "head.branch": branch_missing,
        "host_capabilities.git": capability_missing("git"),
        "host_capabilities.uv": capability_missing("uv"),
        "worktrees.branch": worktree_field_missing("branch"),
        "worktrees.head": worktree_field_missing("head"),
    }
    for dimension in NULLABLE_DIMENSIONS:
        missing = probes[dimension]()
        if missing is None:
            continue
        if missing and dimension not in named:
            assessment.note(
                slug,
                f"the planning snapshot records no value for {dimension} and does not name it as "
                "unknown; an unobserved dimension is named by name, never silently omitted",
            )
        if not missing and dimension in named:
            assessment.note(
                slug,
                f"the planning snapshot names {dimension} as unknown while also recording a value "
                "for it; an observed value and an unobserved dimension are disjoint",
            )


def check_shape(assessment: Assessment, document: dict[str, Any], command: str) -> None:
    """The whole closed schema, run identically by both commands over the same document."""
    check_key_set(assessment, document, command)
    check_repository(assessment, document)
    check_head(assessment, document)
    check_dirty_state(assessment, document)
    check_worktrees(assessment, document)
    named = check_unknowns(assessment, document)
    check_queue(assessment, document, named)
    check_capabilities(assessment, document)
    check_file_digests(assessment, document, "policy_digests", "policy-digests")
    check_file_digests(assessment, document, "wave_artifacts", "wave-artifacts")
    check_nullable_naming(assessment, document, named)


# ---- observation ---------------------------------------------------------------------------------


#: The only environment this tool reads, and only so a bare `git`/`uv` name resolves to an
#: executable. PATHEXT and SYSTEMROOT are the Windows halves of that same resolution.
EXEC_RESOLUTION_ENV = ("PATH", "PATHEXT", "SYSTEMROOT")


def child_environment() -> dict[str, str]:
    """A CONSTRUCTED child environment: exec resolution carried across, everything else asserted.

    No ambient `GIT_*` variable survives, because one of them -- `GIT_INDEX_FILE`, `GIT_DIR`,
    `GIT_WORK_TREE`, `GIT_CEILING_DIRECTORIES` -- would change what git reports, and an observation
    an operator's shell can move is not an observation. Config is pointed at the null device rather
    than merely unset, so a system or global file cannot rename a branch or alias a subcommand.
    """
    environment = {key: os.environ[key] for key in EXEC_RESOLUTION_ENV if key in os.environ}
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


class Repository:
    """One supplied repository, observed through one supplied git executable."""

    def __init__(self, root: Path, git: str) -> None:
        self.root = root
        self.git = git

    def run(self, *args: str, allow_nonzero: bool = False) -> tuple[int, bytes]:
        command = [
            self.git,
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.untrackedCache=false",
            *args,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(self.root),
                env=child_environment(),
                stdin=subprocess.DEVNULL,
                capture_output=True,
                check=False,
            )
        except OSError as exc:
            raise ObservationError(f"cannot run the supplied git {self.git!r}: {exc}") from exc
        if completed.returncode != 0 and not allow_nonzero:
            raise ObservationError(
                f"git {' '.join(args)} exited {completed.returncode} in {self.root}, so the "
                "observation it would have made was not made"
            )
        return completed.returncode, completed.stdout

    def line(self, *args: str) -> str:
        _, raw = self.run(*args)
        return decode(raw, f"git {' '.join(args)}").strip("\n")


def decode(raw: bytes, what: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ObservationError(f"the output of {what} is not UTF-8, so it cannot be recorded: {exc}") from exc


def probe_version(binary: str, args: tuple[str, ...], position: int) -> str | None:
    """One version probe. An unusable binary is an honest None, which its caller names as unknown."""
    try:
        completed = subprocess.run(
            [binary, *args],
            env=child_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    try:
        fields = completed.stdout.decode("utf-8").split()
    except UnicodeDecodeError:
        return None
    if len(fields) <= position:
        return None
    candidate = fields[position]
    return candidate if _VERSION.match(candidate) else None


def observe_head(repository: Repository) -> dict[str, Any]:
    """The anchor. `capture` runs this twice and refuses if the two disagree."""
    commit = repository.line("rev-parse", "HEAD")
    tree = repository.line("rev-parse", "HEAD^{tree}")
    code, raw = repository.run("symbolic-ref", "--quiet", "--short", "HEAD", allow_nonzero=True)
    branch = decode(raw, "git symbolic-ref HEAD").strip("\n") if code == 0 else None
    return {"branch": branch or None, "commit_sha": commit, "tree_sha": tree}


def porcelain_records(raw: bytes) -> list[bytes]:
    """Split `status --porcelain=v2 -z` into records without lossy whitespace splitting.

    A type-2 (rename/copy) record carries its origin path in the FOLLOWING NUL field, so a naive
    split would count that path as an extra record. `--no-renames` means git does not emit one here,
    and the branch is kept anyway: a version that emitted one would be miscounted, not refused.
    """
    fields = raw.split(b"\0")
    if fields and fields[-1] == b"":
        fields.pop()
    records: list[bytes] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        if not record:
            raise ObservationError("git status emitted an empty porcelain-v2 record")
        kind = record[:1]
        if kind not in {b"1", b"2", b"?", b"u", b"!"}:
            raise ObservationError(f"git status emitted an unrecognised porcelain-v2 record kind {kind!r}")
        if kind == b"2":
            if index + 1 >= len(fields):
                raise ObservationError("git status emitted a truncated porcelain-v2 rename record")
            index += 1
        records.append(record)
        index += 1
    return records


def observe_dirty_state(repository: Repository) -> dict[str, int]:
    """Counts only. No path and no content ever enters the document."""
    _, raw = repository.run("status", "--porcelain=v2", "-z", "--untracked-files=all", "--no-renames")
    staged = unstaged = untracked = unmerged = 0
    for record in porcelain_records(raw):
        kind = record[:1]
        if kind == b"?":
            untracked += 1
            continue
        if kind == b"u":
            unmerged += 1
            continue
        if kind == b"!":
            continue
        fields = record.split(b" ", 8)
        if len(fields) != 9 or len(fields[1]) != 2:
            raise ObservationError("git status emitted a malformed porcelain-v2 tracked record")
        if fields[1][:1] != b".":
            staged += 1
        if fields[1][1:] != b".":
            unstaged += 1
    return {"staged": staged, "unmerged": unmerged, "unstaged": unstaged, "untracked": untracked}


def observe_worktrees(repository: Repository, unknowns: Unknowns) -> list[dict[str, Any]]:
    """Every worktree git reports, main included, because custody is about the whole set.

    `-z` rather than line parsing: git does not quote paths in the line form, so a path containing a
    newline would be parsed as two worktrees. A consumer tells this checkout apart from the rest by
    comparing `repository.worktree_path`.
    """
    _, raw = repository.run("worktree", "list", "--porcelain", "-z")
    entries: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for field in decode(raw, "git worktree list").split("\0"):
        if not field:
            if current is not None:
                entries.append(current)
                current = None
            continue
        name, _, value = field.partition(" ")
        if name == "worktree":
            if current is not None:
                entries.append(current)
            current = {"branch": None, "head": None, "path": value}
            continue
        if current is None:
            raise ObservationError(f"git worktree list reported {name!r} before naming a worktree")
        if name == "HEAD":
            current["head"] = value
        elif name == "branch":
            match = _BRANCH_REF.match(value)
            current["branch"] = match.group(1) if match else value
    if current is not None:
        entries.append(current)
    if any(entry["head"] is None for entry in entries):
        unknowns.name(
            "worktrees.head",
            "git worktree list reported a worktree with no HEAD, which is the shape of a bare "
            "worktree, so that worktree's head was not observed",
        )
    if any(entry["branch"] is None for entry in entries):
        unknowns.name(
            "worktrees.branch",
            "git worktree list reported a detached or bare worktree, which has no branch to observe",
        )
    return sorted(entries, key=lambda entry: entry["path"])


def observe_queue(root: Path, unknowns: Unknowns) -> dict[str, Any]:
    """The queue's digest and record count, from ONE read of ONE set of bytes.

    The digest and the count come from the same buffer deliberately: a second pass over the file
    could see a different queue, and then the document would carry a count that its own digest does
    not cover.
    """
    queue = root / QUEUE_PATH
    record: dict[str, Any] = {"path": QUEUE_PATH, "records": None, "sha256": None, "state": "absent"}
    try:
        mode = queue.lstat().st_mode
    except FileNotFoundError:
        return record
    except OSError as exc:
        record["state"] = "unreadable"
        reason = f"the queue at {QUEUE_PATH} cannot be inspected: {exc}"
        unknowns.name("queue.sha256", reason)
        unknowns.name("queue.records", reason)
        return record
    if not stat.S_ISREG(mode):
        record["state"] = "unreadable"
        reason = f"the queue at {QUEUE_PATH} is not a regular file, so its bytes were not read"
        unknowns.name("queue.sha256", reason)
        unknowns.name("queue.records", reason)
        return record
    try:
        raw = queue.read_bytes()
    except OSError as exc:
        record["state"] = "unreadable"
        reason = f"the queue at {QUEUE_PATH} cannot be read: {exc}"
        unknowns.name("queue.sha256", reason)
        unknowns.name("queue.records", reason)
        return record
    record["state"] = "present"
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    count = 0
    for number, line in enumerate(raw.split(b"\n"), start=1):
        if not line.strip():
            continue
        try:
            # The queue is FOREIGN state, not the question being asked, so a line this tool cannot
            # parse makes the count unknown by name rather than making the invocation an input error.
            parsed = json.loads(line.decode("utf-8"), parse_constant=_reject_nonfinite)
        except (UnicodeDecodeError, ValueError, InputError):
            parsed = None
        if not isinstance(parsed, dict):
            unknowns.name(
                "queue.records",
                f"line {number} of the queue at {QUEUE_PATH} is not one JSON object, so a record "
                "count cannot be derived from the bytes this digest covers",
            )
            return record
        count += 1
    record["records"] = count
    return record


def observe_file_digests(root: Path, directory: str, dimension: str, unknowns: Unknowns) -> list[dict[str, str]]:
    """sha256 of every `*.json` directly inside one repository directory.

    A missing directory yields an empty list, which is an OBSERVATION: the glob ran and found
    nothing. An unreadable directory, and any entry that is not a regular file, is named as unknown
    instead -- a symlink is never followed out of the repository to be digested under a repository
    path.
    """
    target = root / directory
    try:
        names = sorted(item.name for item in target.iterdir())
    except FileNotFoundError:
        return []
    except OSError as exc:
        unknowns.name(dimension, f"the directory {directory} cannot be listed: {exc}")
        return []
    entries: list[dict[str, str]] = []
    for name in names:
        if not name.endswith(".json"):
            continue
        relative = f"{directory}/{name}"
        candidate = target / name
        try:
            mode = candidate.lstat().st_mode
        except OSError as exc:
            unknowns.name(f"{dimension}:{relative}", f"{relative} cannot be inspected: {exc}")
            continue
        if not stat.S_ISREG(mode):
            unknowns.name(
                f"{dimension}:{relative}",
                f"{relative} is not a regular file, so it was not digested and no link out of the "
                "repository was followed",
            )
            continue
        try:
            raw = candidate.read_bytes()
        except OSError as exc:
            unknowns.name(f"{dimension}:{relative}", f"{relative} cannot be read: {exc}")
            continue
        entries.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest()})
    return entries


def observe(args: argparse.Namespace, assessment: Assessment) -> dict[str, Any] | None:
    """Build the observed body, or None having noted why the observation could not be completed."""
    root = Path(args.repository)
    repository = Repository(root, args.git)
    unknowns = Unknowns()
    for dimension, reason in REQUIRED_UNKNOWNS.items():
        unknowns.name(dimension, reason)
    try:
        git_version = probe_version(args.git, ("--version",), 2)
        toplevel = repository.line("rev-parse", "--show-toplevel")
        common = repository.line("rev-parse", "--git-common-dir")
        first = observe_head(repository)
        dirty = observe_dirty_state(repository)
        worktrees = observe_worktrees(repository, unknowns)
    except ObservationError as exc:
        assessment.note("repository-identity", str(exc))
        return None
    if not toplevel:
        assessment.note(
            "repository-identity",
            f"git reported no worktree top level for {root}, so the physical identity of what was "
            "observed is not established",
        )
        return None
    git_dir = Path(os.path.abspath(str(root / common)))
    try:
        identity = git_dir.stat()
    except OSError as exc:
        assessment.note("repository-identity", f"cannot stat the git directory {git_dir}: {exc}")
        return None
    if git_version is None:
        unknowns.name(
            "host_capabilities.git",
            f"the supplied git {args.git!r} did not report a parsable version, so the version that "
            "made these observations was not observed",
        )
    uv_version = probe_version(args.uv, ("--version",), 1)
    if uv_version is None:
        unknowns.name(
            "host_capabilities.uv",
            f"the supplied uv {args.uv!r} did not report a parsable version, so no uv capability was "
            "observed",
        )
    if first["branch"] is None:
        unknowns.name(
            "head.branch",
            "git reported no symbolic ref for HEAD, which is the shape of a detached head, so there "
            "was no branch name to observe",
        )
    body = {
        "dirty_state": dirty,
        "head": first,
        "host_capabilities": {
            "git": git_version,
            "python": ".".join(str(part) for part in sys.version_info[:3]),
            "uv": uv_version,
        },
        "policy_digests": observe_file_digests(Path(toplevel), POLICY_GLOB_DIR, "policy_digests", unknowns),
        "queue": observe_queue(Path(toplevel), unknowns),
        "repository": {
            "git_dir": str(git_dir),
            "git_dir_device": identity.st_dev,
            "git_dir_inode": identity.st_ino,
            "worktree_path": toplevel,
        },
        "schema": SNAPSHOT_SCHEMA,
        "stated_at": args.at,
        "unknowns": unknowns.entries(),
        "wave_artifacts": observe_file_digests(
            Path(toplevel), WAVE_ARTIFACT_GLOB_DIR, "wave_artifacts", unknowns
        ),
        "worktrees": worktrees,
    }
    for conflict in unknowns.conflicts:
        assessment.note("named-unknowns", conflict)
    try:
        # THE ANCHOR. Re-read last, so the head this document names is the head that was still
        # current when it was sealed rather than the head that was current when observation started.
        second = observe_head(repository)
    except ObservationError as exc:
        assessment.note("head-stability", f"the head could not be re-read before sealing: {exc}")
        return None
    for key in HEAD_KEYS:
        if first[key] != second[key]:
            assessment.note(
                "head-stability",
                f"head.{key} was {first[key]!r} when the observation began and {second[key]!r} when "
                "the snapshot was about to be sealed: a snapshot that named one head while the "
                "repository moved to another is exactly the stale-but-plausible artifact this "
                "document exists to make impossible",
            )
    # `unknowns` was frozen into the body above; it is rebuilt here rather than mutated so the
    # re-read cannot add an unknown that the digested body does not carry.
    return body


def check_output_path(assessment: Assessment, out: str | None, body: dict[str, Any] | None) -> Path | None:
    """`--out` may not exist, may not land in the observed repository, and needs a real parent."""
    slug = "output-path"
    if out is None:
        return None
    target = Path(os.path.abspath(out))
    try:
        target.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        assessment.note(slug, f"the --out path {target} cannot be inspected: {exc}")
        return None
    else:
        assessment.note(
            slug,
            f"the --out path {target} already exists; this command overwrites nothing, so an "
            "occupied destination is refused rather than replaced",
        )
        return None
    parent = target.parent
    if not parent.is_dir():
        assessment.note(
            slug,
            f"the --out path {target} has no existing directory to be written into, so the derived "
            "snapshot would have nowhere to land",
        )
        return None
    if body is None:
        return target
    repository = body.get("repository")
    if not isinstance(repository, dict):
        return target
    resolved = Path(os.path.realpath(str(parent)))
    for key in ("git_dir", "worktree_path"):
        value = repository.get(key)
        if not isinstance(value, str):
            continue
        observed = Path(os.path.realpath(value))
        if resolved == observed or observed in resolved.parents:
            assessment.note(
                slug,
                f"the --out path {target} resolves inside the observed {key} {observed}; writing the "
                "snapshot into what it describes would change that tree's dirty state and make the "
                "document's own record of it wrong",
            )
            return None
    return target


def check_digest(assessment: Assessment, document: dict[str, Any], command: str, expect: str | None) -> str | None:
    """Re-derive the one digest. A recorded digest its own content does not derive is a refusal.

    For `capture` there is nothing recorded yet, so the derivation happens once the body is otherwise
    admitted (in `derive_command`) and this group only carries the `--expect-digest` comparison.
    """
    slug = "digest"
    derived: str | None = None
    if command == "verify":
        recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the planning snapshot's digest")
        derived = snapshot_digest(document)
        if recorded is not None and recorded != derived:
            assessment.note(
                slug,
                f"the planning snapshot records digest {recorded} which its own content does not "
                f"re-derive ({derived}): the document has been edited since it was sealed, or the "
                "digest was written by something other than this derivation",
            )
    if expect is not None and derived is not None and expect != derived:
        assessment.note(
            slug,
            f"--expect-digest {expect} is not this snapshot's content digest {derived}, so the "
            "supplied document is not the snapshot the caller meant to bind",
        )
    return derived


def derive_command(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None]:
    """Observe or read, validate against the closed schema, then seal or verify."""
    command = args.command
    assessment = Assessment(command)
    target: Path | None = None
    if command == "capture":
        document = observe(args, assessment)
        if document is not None:
            check_shape(assessment, document, command)
        target = check_output_path(assessment, args.out, document)
    else:
        document = load_document(args.snapshot, "planning snapshot")
        check_shape(assessment, document, command)
    derived = check_digest(assessment, document or {}, command, getattr(args, "expect_digest", None))

    verdict = assessment.verdict(command)
    sealed: dict[str, Any] | None = None
    digest: str | None = None
    if document is not None and verdict == VERDICT_CAPTURED:
        # Sealed only once the observed body is fully admitted: an illegal snapshot is unrepresentable
        # in the emitted document rather than emitted with a warning beside it.
        digest = snapshot_digest(document)
        sealed = dict(document)
        sealed[DIGEST_KEY] = digest
    elif document is not None and verdict == VERDICT_VERIFIED:
        digest = derived
        sealed = dict(document)
    result = {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "snapshot": sealed,
        "digest": digest,
        # Republished ONLY for an admitted snapshot. A refusal publishes none of the observation, so
        # no consumer can read a partially admitted snapshot out of one.
        "head": sealed["head"] if sealed is not None else None,
        "out": str(target) if sealed is not None and target is not None else None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }
    return result, (target if sealed is not None else None)


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Catching the failed write is not enough: the bytes stay PENDING in the stream's buffer and
    CPython flushes `sys.stdout`/`sys.stderr` once more while finalizing; that second failure
    replaces the process exit code with 120, which is outside this module's closed exit set. Dropping
    the module attribute is how CPython itself represents a stream this process does not have (`2>&-`
    starts the interpreter with `sys.stderr is None`), and it loses no byte the failed write had not
    already lost. The identity check is load-bearing because `main` is importable: only the stream
    that actually failed may be dropped, never a caller's replacement.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Callable[[str], None]:
    """Wrap one already-settled display stream so a failed write costs the channel, never the code.

    The first failure retires the channel -- silently, because there is by definition nowhere left to
    report it -- and every later line is a no-op. Flushing is not optional: it is what makes a broken
    channel announce itself HERE, where the failure can still be contained, rather than during
    finalization where it becomes exit 120.
    """
    if stream is None:  # `2>&-` / `1>&-`: this process was handed no such stream
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
        except (OSError, ValueError):  # EPIPE/ENOSPC, or a stream closed underneath us
            live[0] = False
            abandon_broken_stream(name, stream)

    return emit


def advisory_stderr() -> Callable[[str], None]:
    """Settle this module's display-only sink for diagnostics and argparse's own usage lines."""
    return guarded_sink("stderr", sys.stderr)


def report_input_error(message: str) -> None:
    advisory_stderr()(f"planning-snapshot.py: {message}\n")


def write_snapshot(target: Path, sealed: dict[str, Any]) -> bool:
    """Write the sealed snapshot exclusively. A losing race costs the delivery, never the file."""
    payload = canonical_bytes(sealed)
    try:
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as exc:
        report_input_error(
            f"cannot create the --out path {target}: {exc}; the snapshot was derived and nothing was "
            "written, so no existing file was touched"
        )
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        report_input_error(
            f"cannot write the --out path {target}: {exc}; the snapshot was derived but its file may "
            "be incomplete, so treat that path as unusable evidence"
        )
        return False
    return True


def emit_result(result: dict[str, Any], wrote: Path | None) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence, so a stdout that cannot receive it is
    not a lost convenience -- the question was answered and the answer did not arrive. That is an
    internal failure to deliver (exit 1), and when `--out` already succeeded the message says so,
    because a file that outlives a nonzero exit is the one effect a consumer could be surprised by.
    `canonical_bytes` is `ensure_ascii=True`, so the payload is ASCII and a text stream with no
    `.buffer` -- what an importing caller's `redirect_stdout(StringIO())` installs -- receives
    byte-identical characters rather than being made to fail.
    """
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
    written = f"; the sealed snapshot WAS written to {wrote}" if wrote is not None else ""
    if emit_to is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            f"result could not be delivered{written}"
        )
        return EXIT_INTERNAL
    try:
        emit_to(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        # Abandoned BEFORE returning: the classification below is worthless if the interpreter's
        # shutdown flush of the same broken stream replaces this exit code with 120.
        abandon_broken_stream("stdout", stream)
        report_input_error(
            f"cannot write the result document to stdout: {exc}; an unknown prefix of it may already "
            f"have reached the consumer, so the result was derived but not delivered{written}"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules.

    `error` writes usage through `print_usage`, which FALLS BACK TO STDOUT when `sys.stderr is None`:
    under `2>&-` a grammar error would keep exit 2 while putting usage bytes where this module's one
    result document lives. And argparse swallows a failed write while leaving its bytes pending,
    which is enough for the shutdown flush to replace the usage error's 2 with 120.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            # argparse resolved `sys.stderr`/`sys.stdout` itself and got None: this process was
            # handed no such stream, so the line is dropped rather than redirected onto the other.
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
    "Exit codes: 0 a result was derived, a named refusal included; 2 a supplied file cannot be read "
    "as one JSON object, or the arguments themselves are unusable; 1 a derived result that could not "
    "be delivered, because a snapshot sealed and not delivered is not a success. Implementation "
    "Decision 9's 3 and 4 do not apply: a refusal happens before anything is written, and the one "
    "write is exclusive and all-or-nothing, so there is no partial effect to admit."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="planning-snapshot.py",
        description=(
            "Capture, seal, and verify the PlanningSnapshot -- the observed half of the planning "
            "artifact chain MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> "
            "AutoEnvelope. Read-only against the observed repository: it never writes there, and it "
            "authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser(
        "capture",
        description=(
            "Observe one repository through git and the local filesystem and emit the SEALED "
            "snapshot: the observed body plus exactly one added key, `digest`. A dimension that "
            "could not be observed is named in `unknowns` rather than guessed or omitted, and the "
            "head is re-read immediately before sealing so the document names the head that was "
            "still current when it was sealed."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED snapshot's digest and shape from its own content and refuse when "
            "either disagrees. This re-observes no repository: whether the recorded head is still "
            "current is plan admission's separate check."
        ),
        epilog=EPILOG,
    )
    capture.add_argument("--repository", required=True, help="the repository worktree to observe")
    capture.add_argument(
        "--at",
        required=True,
        help="the YYYY-MM-DDTHH:MM:SSZ instant of this observation; this tool reads no clock",
    )
    capture.add_argument(
        "--out",
        default=None,
        help=(
            "write the sealed snapshot to this path, which must not exist and must be outside the "
            "observed repository; the result document always goes to stdout"
        ),
    )
    capture.add_argument("--git", default="git", help="the git executable to observe through")
    capture.add_argument("--uv", default="uv", help="the uv executable to probe for a version")
    verify.add_argument("--snapshot", required=True, help=f"the {SNAPSHOT_SCHEMA} document to read")
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the snapshot's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no snapshot "
            "could ever match it"
        )
        return EXIT_INPUT
    if args.command == "capture":
        if not _TIME.match(args.at):
            report_input_error(
                f"--at {args.at!r} is not a YYYY-MM-DDTHH:MM:SSZ instant, so no snapshot could state "
                "when it was observed"
            )
            return EXIT_INPUT
        if not Path(args.repository).is_dir():
            report_input_error(
                f"--repository {args.repository!r} is not an existing directory, so there is nothing "
                "to observe"
            )
            return EXIT_INPUT
    try:
        result, target = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    wrote: Path | None = None
    if target is not None:
        # Written BEFORE the result document: a consumer that reads a `captured` verdict naming an
        # `out` path must be able to open it, so the file lands first or the result is not delivered.
        if not write_snapshot(target, result["snapshot"]):
            return EXIT_INTERNAL
        wrote = target
    return emit_result(result, wrote)


if __name__ == "__main__":
    raise SystemExit(main())
