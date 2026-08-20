#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Seal and verify the four wave submissions `wave-verdict.py` consumes and nothing emitted.

Seed agentic-sdlc-4e5a is this module's whole contract. `wave-verdict.py` derives one terminal wave
state from eight completion conditions, and four of its inputs had no producer anywhere in this
bundle: the composer defined the schemas so it could validate them, so a real wave could not reach
`accepted` without hand-authored JSON. This module is the missing producer for exactly those four,
and for no fifth thing:

    artifact-manifest   agentic-sdlc/wave-artifact-manifest@1        condition 3
    review              agentic-sdlc/wave-review-submission@1        condition 4
    critic-findings     agentic-sdlc/wave-critic-findings@1          the critic's classification
    conductor-record    agentic-sdlc/wave-verdict-conductor-record@1 condition 8

TWO VERBS, FOUR KINDS, ONE DIGEST.

    define --kind K --submission BODY   validates one BODY against kind K's closed schema and emits
                                       the SEALED document: the body plus exactly one added key,
                                       `digest`.
    verify --kind K --submission SEALED re-derives a sealed document's digest from its own content
                                       and refuses when the two disagree. `--expect-digest` is the
                                       binding a conductor uses to prove it is reading the submission
                                       it recorded.

The verbs are the subcommands and the kind is a flag, because the two verbs' arguments, exits, and
digest contract are identical across all four kinds -- only the closed schema differs -- and because
`--kind` is the one value a caller must state, so a missing one is a grammar error rather than a
silently chosen default.

THE DIGEST IS THE SAME DERIVATION THE FAMILY USES, and there is only one way to compute it:

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

where `canonical` is this family's form -- `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=True`, `allow_nan=False`, and exactly one trailing newline. `define` REFUSES a body
that already carries a `digest`, so the one load-bearing value never has a second origin and a sealed
document fed back into `define` cannot nest one; the key is excluded BY NAME rather than by position;
and `define` NORMALIZES NOTHING, so the bytes digested are the bytes the caller wrote.

WHAT THE DIGEST IS FOR, stated because `wave-verdict.py` does not read it. None of the four
validators there requires a `digest`, and none of them closes its key set, which is why a sealed
document is accepted by the existing consumer byte-for-byte with no change on that side. The digest
serves the CONDUCTOR, not the verdict: it is how a submission recorded in the journal's `evidence`
can later be shown to be the same submission, and how `verify --expect-digest` refuses a hand-edited
one. A verdict derived over unsealed hand-authored JSON stays exactly as trustworthy as it was.

CLOSED SCHEMAS, AND STRICTER THAN THE CONSUMER ON PURPOSE. Every kind's key set is closed at every
level: an unrecognised field is refused rather than ignored, because a field this version cannot
honour is a meaning it cannot carry. Where `wave-verdict.py` would merely accumulate a named reason,
this module refuses to SEAL at all, because a producer that emits a document its own consumer will
block on has produced nothing:

  * a critic `kind` outside the eight issue 07 names is unclassifiable, and `wave-verdict.py` blocks
    on it, so it is never sealed here;
  * a review `verdict` outside the three, an `accepted` review with no evidence, and a self-review
    are each refused rather than emitted;
  * a manifest artifact path that is not a contained repository-relative path is refused, using the
    same lexical rule the verdict tool applies -- no absolute path, no backslash, no NUL, no `.` or
    `..` component, no empty component -- so a manifest cannot name `/etc/passwd` or climb out of the
    target;
  * every identifier must match `wave-journal.py`'s own id shape, so an id no journal could ever
    carry is refused here rather than becoming an unmatched cross-reference later.

HOW THE EXECUTION ENDED, which is the half Implementation Decision 61 was missing. Seed
agentic-sdlc-b3ba records that the decision closes wave outcomes at SIX values -- `accepted`,
`remediation-progress`, `blocked`, `aborted`, `failed`, `unknown-effect` -- of which `wave-verdict.py`
could derive only the first three, because the other three describe how an execution ENDED rather than
what its completion evidence shows and no consumed artifact recorded them. The conductor record is
where that fact belongs, because the conductor is the party that watched the execution end, so
`wave-verdict-conductor-record@1` carries three fields for it:

    ended_state        one of `aborted`, `completed`, `failed`, `unknown-effect`
    ended_reasons      the named reasons; non-empty for the three non-`completed` states and empty
                       for `completed`, so an aborted wave with no stated reason is unrepresentable
                       and a completed one cannot carry prose that argues with its own state
    last_proven_stage  where evidence stops; a non-empty string for the three non-`completed` states
                       and `null` for `completed`, because user story 91 wants failure output led by
                       effect state and last proven stage, and for a completed execution the last
                       proven stage is the execution

Those three keys were ADDITIVE to `wave-verdict.py`'s conductor-record validator, which requires
`journal_digest`, `verdict_destination`, `recorded_by`, and `recorded_at` and closes no key set. That
consumer now READS them and derives Decision 61's other three states from them: `unknown-effect`
dominates every other ending and every piece of completion evidence, two disagreeing peer endings are
refused rather than picked, one ending overrides an otherwise complete evidence set, and `completed`
overrides nothing. So the vocabulary this module closes is the vocabulary that consumer ranks, and the
two halves are checked against each other from both sides -- `SealedSubmissionRoundTripTests` in
`tests/test_wave_verdict.py` seals a record here for each ending and asserts the state it derives
there. This module still derives NO outcome itself: it seals how the execution ended and never says
what that makes the wave.

NO CLOCK. Every instant is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would refuse
honest input at random. `recorded_at` is the family's fixed-width `YYYY-MM-DDTHH:MM:SSZ` form, whose
lexicographic order is chronological. This module compares it against nothing -- ordering a record
against the journal's last entry is `wave-verdict.py`'s condition 8, which holds the journal.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. This module's exit space is 0, 2, and 1 only, for the same structural
reason `wave-verdict.py` gives: a command that causes no effect can neither refuse before one nor
admit one. Nothing here opens a file for writing, spawns a process, touches the network, or reads an
environment variable; it reads the one path it is given and prints one document. A REFUSED submission
is therefore a derived result (0), and 1 additionally covers a stdout that cannot receive that
document, because a submission sealed and not delivered is not a success.

RESIDUALS, STATED EXACTLY.

  * The digest is RE-DERIVATION, not a boundary against a same-OS-user forger. All four documents
    remain the same-user assertions `wave-verdict.py` calls them: sealing one proves it has not
    drifted since it was sealed, never that what it asserts is true.
  * A manifest's `sha256` values are the CALLER's measurements. This module validates their shape and
    never opens the target tree, so it cannot confirm that a declared artifact exists or hashes to
    the recorded value; `wave-verdict.py`'s condition 3 is the party that hashes the tree, and a
    producer that measured the same files would be one party asserting both sides of that check.
    Obtain them with `sha256sum` inside the target and paste them in.
  * Every field outside the closed vocabularies, the identifiers, the instant, and the digests is
    PROSE. A finding's `severity` and `recommended_disposition`, a review's `evidence` lines, and a
    record's `verdict_destination` are non-empty strings and nothing more, because `wave-verdict.py`
    reads them as prose too and a vocabulary invented here would be one no consumer checks.
  * `resolved` and `resolution` are validated on every finding kind, but `wave-verdict.py` reads them
    only for a blocking kind: it routes every seed-worthy kind to Seeds whether or not the critic
    called it resolved.
  * A sealed submission is EVIDENCE. It authorizes no dispatch, no write, no fan-in, no queue
    mutation, no push, publication, PR mutation, merge, or deployment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

RESULT_SCHEMA = "agentic-sdlc/wave-submission-result@1"

KIND_MANIFEST = "artifact-manifest"
KIND_REVIEW = "review"
KIND_CRITIC = "critic-findings"
KIND_CONDUCTOR = "conductor-record"
KINDS = (KIND_MANIFEST, KIND_CONDUCTOR, KIND_CRITIC, KIND_REVIEW)

#: The four schemas `wave-verdict.py` consumes, spelled exactly as it requires them.
SCHEMAS = {
    KIND_MANIFEST: "agentic-sdlc/wave-artifact-manifest@1",
    KIND_REVIEW: "agentic-sdlc/wave-review-submission@1",
    KIND_CRITIC: "agentic-sdlc/wave-critic-findings@1",
    KIND_CONDUCTOR: "agentic-sdlc/wave-verdict-conductor-record@1",
}

VERDICT_DEFINED = "defined"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_DEFINED: (
        "the submission is well-formed and closed, and the sealed document is the one a wave verdict "
        "may consume; the submission is evidence and authorizes nothing"
    ),
    VERDICT_VERIFIED: (
        "the sealed submission re-derives its own digest and satisfies its closed schema, so it is "
        "the same submission it claims to be; the submission is evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "no submission was sealed and no digest was derived; the reasons name each field and what was "
        "wrong with it"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

DIGEST_KEY = "digest"

#: The closed bodies. Every key is REQUIRED, so an absence is always a named refusal and never a
#: default; `verify` reads each set plus `digest`.
BODY_KEYS = {
    KIND_MANIFEST: ("artifacts", "schema", "target", "wave_id"),
    KIND_REVIEW: (
        "evidence",
        "reasons",
        "reviewer_node_id",
        "schema",
        "subject_node_id",
        "verdict",
        "wave_id",
    ),
    KIND_CRITIC: ("findings", "schema", "wave_id"),
    KIND_CONDUCTOR: (
        "ended_reasons",
        "ended_state",
        "journal_digest",
        "last_proven_stage",
        "recorded_at",
        "recorded_by",
        "schema",
        "verdict_destination",
        "wave_id",
    ),
}

#: The two nested entry objects, also closed.
ARTIFACT_KEYS = ("path", "sha256")
FINDING_KEYS = (
    "affected_artifact",
    "evidence",
    "finding_id",
    "kind",
    "rationale",
    "recommended_disposition",
    "resolution",
    "resolved",
    "severity",
)

#: `wave-verdict.py`'s three, and only three, review verdicts.
REVIEW_ACCEPTED = "accepted"
REVIEW_VERDICTS = (REVIEW_ACCEPTED, "changes-requested", "rejected")

#: Issue 07's completion blockers and its seed-worthy set, as `wave-verdict.py` spells them. A kind
#: outside the union is unclassifiable there, so it is never sealed here.
BLOCKING_FINDING_KINDS = (
    "acceptance-criteria-violation",
    "corrupted-evidence",
    "failed-authoritative-gate",
    "safety-regression",
)
SEED_WORTHY_FINDING_KINDS = ("complexity", "documentation", "enhancement", "maintainability")
FINDING_KINDS = tuple(sorted(BLOCKING_FINDING_KINDS + SEED_WORTHY_FINDING_KINDS))

#: Implementation Decision 61's ended-state half: how the execution ENDED, closed at four tokens.
ENDED_COMPLETED = "completed"
ENDED_STATES = ("aborted", ENDED_COMPLETED, "failed", "unknown-effect")

CHECKS: dict[str, tuple[str, ...]] = {
    KIND_MANIFEST: ("closed-key-set", "wave-identity", "target", "declared-artifacts", "digest"),
    KIND_REVIEW: ("closed-key-set", "wave-identity", "review-parties", "verdict-and-reasons", "evidence", "digest"),
    KIND_CRITIC: ("closed-key-set", "wave-identity", "findings", "finding-classification", "digest"),
    KIND_CONDUCTOR: ("closed-key-set", "wave-identity", "journal-anchor", "recording", "ended-state", "digest"),
}

#: Carried in every document, because a conductor that files a sealed submission should carry what it
#: does not prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger; all four documents "
    "stay the same-user assertions the verdict tool calls them",
    "a manifest's sha256 values are the caller's measurements: this tool never opens the target tree, "
    "so wave-verdict.py's condition 3 remains the only party that hashes a declared artifact",
    "every field outside the closed vocabularies, the identifiers, the instant, and the digests is "
    "prose: a well-formed submission is not a true one",
    "wave-verdict.py reads `resolved` and `resolution` only for a blocking finding kind; a "
    "seed-worthy kind becomes a Seed whether or not the critic called it resolved",
    "the ended-state fields are recorded and not interpreted here: wave-verdict.py ranks them into "
    "aborted, failed, or unknown-effect, and this module never says what an ending makes the wave",
    "a sealed submission is evidence: it authorizes no dispatch, write, fan-in, queue mutation, push, "
    "publication, PR mutation, merge, or deployment",
)

#: `wave-journal.py`'s own id shape, re-expressed: an id outside it is one no journal could carry.
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class InputError(Exception):
    """A supplied file cannot be read as one JSON object (exit 2).

    Deliberately separate from a named reason: unusable input means the QUESTION could not be asked,
    while a reason means it was asked and the answer is "refused".
    """


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def submission_digest(document: dict[str, Any]) -> str:
    """The ONE digest derivation: sha256 over the canonical bytes of the document minus `digest`.

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN` and `Infinity` by default; no honest submission carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _reject_nonfinite_values(document: Any) -> None:
    """A post-parse walk, because a huge literal like `1e400` is a float `json` never hands here.

    `parse_constant` only sees the three bare words. `1e400` is an ordinary number token that
    `float()` overflows to `inf`, which `canonical_bytes` would then refuse with `allow_nan=False` --
    an internal failure at emit time rather than a named input error at read time. The walk is
    ITERATIVE because a deeply nested document would otherwise exhaust the interpreter's stack, which
    is a crash rather than a classified exit.
    """
    stack: list[Any] = [document]
    while stack:
        value = stack.pop()
        if isinstance(value, float) and not math.isfinite(value):
            raise InputError("a supplied document carries a non-finite number, which no submission may carry")
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a submission carrying two `verdict`s
    parses to whichever the writer put second. That is a document with two meanings, and it would
    also give the one digest two possible values.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"a supplied document repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


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
    _reject_nonfinite_values(value)
    return value


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the document can say which part of the schema is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree.
    """

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.groups: dict[str, list[str]] = {slug: [] for slug in CHECKS[kind]}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in CHECKS[self.kind]:
            flat.extend(self.groups[slug])
        return flat

    def verdict(self, command: str) -> str:
        """Exactly one verdict, always.

        The selection is one partition over one value, so two verdicts are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no verdict --
        and it is a named reason rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command == "define":
            return VERDICT_DEFINED
        if command == "verify":
            return VERDICT_VERIFIED
        self.note(
            "closed-key-set",
            f"no verdict follows from the command {command!r}, and an underivable verdict is a "
            "refusal rather than a guess",
        )
        return VERDICT_REFUSED


# ---- field predicates ----------------------------------------------------------------------------
# Each returns the well-formed value, or None having noted its own named reason. Returning None means
# "this field cannot be reasoned about further", which is how a cross-field check below knows to stay
# silent instead of printing a second reason about the same mistake.


def _text(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        assessment.note(
            slug,
            f"{what}'s {key} is not a non-empty string (found {value!r}), so what it states cannot be "
            "read",
        )
        return None
    return value


def _identifier(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or not _ID.match(value):
        assessment.note(
            slug,
            f"{what}'s {key} is not an id of the shape wave-journal.py records -- an alphanumeric "
            f"first character then up to 63 more of [A-Za-z0-9._-] -- (found {value!r}), so no "
            "journal could carry the node or wave it names",
        )
        return None
    return value


def _string_list(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str
) -> list[str] | None:
    value = container.get(key)
    if not isinstance(value, list):
        assessment.note(slug, f"{what}'s {key} is not a list (found {value!r})")
        return None
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            assessment.note(
                slug,
                f"{what}'s {key} carries an entry at position {index} that is not a non-empty string "
                f"(found {item!r})",
            )
            return None
    return list(value)


def _closed_entry(
    assessment: Assessment, slug: str, value: Any, keys: tuple[str, ...], what: str
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        assessment.note(slug, f"{what} is not a JSON object (found {value!r}), so its fields cannot be read")
        return None
    missing = sorted(set(keys) - set(value))
    unknown = sorted(set(value) - set(keys))
    for name in missing:
        assessment.note(slug, f"{what} carries no {name}, which this schema requires of every entry")
    for name in unknown:
        assessment.note(
            slug,
            f"{what} carries the unknown field {name!r}; the entry is a closed object, so an "
            "unrecognised field is refused rather than ignored",
        )
    if missing or unknown:
        return None
    return value


def _instant(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or not _TIME.match(value):
        assessment.note(
            slug,
            f"{what}'s {key} is not a YYYY-MM-DDTHH:MM:SSZ instant (found {value!r}); this tool reads "
            "no clock, so the instant is the caller's to state exactly",
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


def _choice(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, allowed: tuple[str, ...], what: str
) -> str | None:
    value = container.get(key)
    if not isinstance(value, str) or value not in allowed:
        assessment.note(
            slug,
            f"{what}'s {key} is {value!r}, which is not one of {list(allowed)}; the vocabulary is "
            "closed, so an unrecognised value is refused rather than carried to a consumer that "
            "would block on it",
        )
        return None
    return value


def contained_relative(raw: str) -> str | None:
    """The declared path, or None when it is not a contained repository-relative path.

    Re-expressed from `wave-verdict.py`'s `_contained_relative` rather than imported -- that module's
    name has a hyphen, so no `import` statement can name it -- and deliberately identical: lexical
    containment only, refusing an absolute path, a backslash, a NUL, and a `.`, `..`, or empty
    component before any filesystem call. A path this rejects is one the verdict tool would refuse to
    validate, so it is refused here instead of sealed.
    """
    if not raw or raw.startswith("/") or "\\" in raw or "\0" in raw:
        return None
    parts = PurePosixPath(raw).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


# ---- check groups --------------------------------------------------------------------------------


def check_key_set(assessment: Assessment, document: dict[str, Any], kind: str, command: str) -> None:
    """The closed schema itself: exactly these keys, no more and no fewer.

    `define` and `verify` differ by exactly one key, and the difference is checked in both
    directions: a body handed to `define` may NOT carry a derived digest, and a document handed to
    `verify` MUST.
    """
    expected = set(BODY_KEYS[kind]) | ({DIGEST_KEY} if command == "verify" else set())
    present = set(document)
    for key in sorted(expected - present):
        assessment.note(
            "closed-key-set",
            f"the {kind} submission carries no {key}, which the closed {SCHEMAS[kind]} schema requires",
        )
    for key in sorted(present - expected):
        if command == "define" and key == DIGEST_KEY:
            assessment.note(
                "closed-key-set",
                "the body handed to define already carries a digest, which is DERIVED from the body "
                "and never supplied: accepting one would give the single load-bearing value a second "
                "origin, and a sealed document fed back in would nest one",
            )
            continue
        assessment.note(
            "closed-key-set",
            f"the {kind} submission carries the unknown field {key!r}; {SCHEMAS[kind]} is a closed "
            "schema, so a field this version cannot honour is refused rather than ignored",
        )
    schema = document.get("schema")
    if "schema" in document and schema != SCHEMAS[kind]:
        assessment.note(
            "closed-key-set",
            f"the submission declares schema {schema!r}, not the {SCHEMAS[kind]} that --kind {kind} "
            "selects, so which document this is cannot be established from the document itself",
        )


def check_wave_identity(assessment: Assessment, document: dict[str, Any], kind: str) -> str | None:
    """One wave id, in the shape a journal carries.

    Every one of the four is bound to a wave by `wave-verdict.py`'s `assess_binding`, which composes
    the submissions against ONE wave and blocks when two disagree. An id no journal could carry could
    never match, so it is refused here.
    """
    return _identifier(assessment, "wave-identity", document, "wave_id", f"the {kind} submission")


def check_manifest(assessment: Assessment, document: dict[str, Any]) -> list[str] | None:
    """Condition 3's declaration: one target, and the artifacts declared inside it.

    Two things are refused that the verdict tool would only note. An EMPTY artifact list is refused
    because a manifest that declares nothing validates nothing, and a DUPLICATE path is refused
    because the same file declared with two digests is a document with two meanings -- the verdict
    tool hashes the file once and one of the two declarations would silently never be tested.
    """
    _text(assessment, "target", document, "target", "the artifact-manifest submission")
    entries = document.get("artifacts")
    if not isinstance(entries, list):
        assessment.note(
            "declared-artifacts",
            f"the artifact-manifest submission's artifacts is not a list (found {entries!r})",
        )
        return None
    if not entries:
        assessment.note(
            "declared-artifacts",
            "the artifact-manifest submission declares no artifact at all, and a manifest that "
            "declares nothing validates nothing",
        )
        return None
    declared: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(entries):
        what = f"the artifact-manifest submission's artifact at position {index}"
        entry = _closed_entry(assessment, "declared-artifacts", item, ARTIFACT_KEYS, what)
        if entry is None:
            continue
        relative = _text(assessment, "declared-artifacts", entry, "path", what)
        _digest_value(assessment, "declared-artifacts", entry.get("sha256"), f"{what}'s sha256")
        if relative is None:
            continue
        contained = contained_relative(relative)
        if contained is None:
            assessment.note(
                "declared-artifacts",
                f"{what} declares path {relative!r}, which is not a contained repository-relative "
                "path: an absolute path, a backslash, a NUL, and a `.`, `..`, or empty component are "
                "each refused, so a manifest cannot name a file outside its target",
            )
            continue
        if contained in seen:
            assessment.note(
                "declared-artifacts",
                f"{what} declares path {contained!r}, which an earlier entry already declares; one "
                "file recorded twice can carry two digests, and only one of them would ever be "
                "tested against the tree",
            )
            continue
        seen.add(contained)
        declared.append(contained)
    return declared if not assessment.groups["declared-artifacts"] else None


def check_review(assessment: Assessment, document: dict[str, Any]) -> str | None:
    """Condition 4's acceptance, refused here in every shape that could never be an acceptance.

    Issue 07 has reviewers "inspect immutable workstream results and never repair them", so a node
    accepting its own workstream is refused rather than sealed. `reasons` is required PRESENT and its
    emptiness is tied to the verdict: a rejection with no reason states nothing a workstream could
    act on, and an acceptance carrying reasons argues with its own verdict. The two node ids are
    checked for shape only; whether the journal carries them, and whether the reviewer holds the
    reviewer role and reviewed work that already existed, is condition 4's own cross-check.
    """
    subject = _identifier(assessment, "review-parties", document, "subject_node_id", "the review submission")
    reviewer = _identifier(assessment, "review-parties", document, "reviewer_node_id", "the review submission")
    if subject is not None and reviewer is not None and subject == reviewer:
        assessment.note(
            "review-parties",
            f"node {subject} is both the subject and the reviewer: issue 07 has reviewers inspect "
            "results they did not produce, so a self-review is not an acceptance and is not sealed",
        )
    verdict = _choice(assessment, "verdict-and-reasons", document, "verdict", REVIEW_VERDICTS, "the review submission")
    reasons = _string_list(assessment, "verdict-and-reasons", document, "reasons", "the review submission")
    if verdict is not None and reasons is not None:
        if verdict == REVIEW_ACCEPTED and reasons:
            assessment.note(
                "verdict-and-reasons",
                "the review is accepted and carries reasons; an acceptance states no reason against "
                "the work it accepts, so the two fields would argue with each other",
            )
        if verdict != REVIEW_ACCEPTED and not reasons:
            assessment.note(
                "verdict-and-reasons",
                f"the review is {verdict} and carries no reason, so it states nothing the workstream "
                "could act on",
            )
    evidence = _string_list(assessment, "evidence", document, "evidence", "the review submission")
    if evidence is not None and not evidence:
        assessment.note(
            "evidence",
            "the review carries no evidence, so its verdict is asserted rather than recorded; "
            "wave-verdict.py refuses an accepted review with an empty evidence list by name",
        )
    return verdict


def check_critic(assessment: Assessment, document: dict[str, Any]) -> None:
    """The critic's findings, each classifiable and each carrying what issue 07 requires of it.

    A kind outside the eight is refused rather than sealed, because `wave-verdict.py` classifies an
    unrecognised kind as unclassifiable and blocks on it: emitting one would be producing a document
    whose only effect is to block the wave that reads it. `resolved` and `resolution` are tied
    together in both directions -- a resolved finding names the remediation node, an unresolved one
    names none -- so a claim of resolution always has somewhere for the verdict tool to look.
    """
    entries = document.get("findings")
    if not isinstance(entries, list):
        assessment.note("findings", f"the critic-findings submission's findings is not a list (found {entries!r})")
        return
    if not entries:
        assessment.note(
            "findings",
            "the critic-findings submission carries no finding at all; an adversarial review that "
            "found nothing states that in a finding of its own rather than in an empty list, so an "
            "empty document cannot be read as either a clean review or an unrun one",
        )
        return
    seen: set[str] = set()
    for index, item in enumerate(entries):
        what = f"the critic-findings submission's finding at position {index}"
        entry = _closed_entry(assessment, "findings", item, FINDING_KEYS, what)
        if entry is None:
            continue
        finding_id = _identifier(assessment, "findings", entry, "finding_id", what)
        if finding_id is not None:
            if finding_id in seen:
                assessment.note(
                    "findings",
                    f"{what} declares finding_id {finding_id!r}, which an earlier finding already "
                    "declares; two findings with one id cannot be dispositioned separately",
                )
            seen.add(finding_id)
        for key in ("affected_artifact", "rationale", "recommended_disposition", "severity"):
            _text(assessment, "findings", entry, key, what)
        evidence = _string_list(assessment, "findings", entry, "evidence", what)
        if evidence is not None and not evidence:
            assessment.note(
                "findings",
                f"{what} carries no evidence: issue 07 requires every finding to carry severity, "
                "evidence, affected artifact, recommended disposition, and rationale",
            )
        _choice(assessment, "finding-classification", entry, "kind", FINDING_KINDS, what)
        resolved = entry.get("resolved")
        if not isinstance(resolved, bool):
            assessment.note(
                "finding-classification",
                f"{what}'s resolved is not a boolean (found {resolved!r}), so whether this finding is "
                "outstanding cannot be read",
            )
            continue
        resolution = entry.get("resolution")
        if resolved:
            if not isinstance(resolution, str) or not _ID.match(resolution):
                assessment.note(
                    "finding-classification",
                    f"{what} is resolved and its resolution is {resolution!r} rather than the id of "
                    "the remediation node that resolved it, so the claim would be an assertion with "
                    "nothing for a verdict to check it against",
                )
        elif resolution is not None:
            assessment.note(
                "finding-classification",
                f"{what} is unresolved and still names resolution {resolution!r}; an outstanding "
                "finding has no remediation node, so the two fields would argue with each other",
            )


def check_conductor_record(assessment: Assessment, document: dict[str, Any]) -> str | None:
    """Condition 8's record, plus Implementation Decision 61's ended-state facts.

    The `journal_digest` is the load-bearing field: `wave-verdict.py` compares it against the
    projection it derives, and it is the one anchor that comes from outside the journal file, so a
    rewritten head or a truncated tail is caught by it. The ended-state fields are the ones no
    consumed artifact carried: `ended_state` closed at four tokens, `ended_reasons` non-empty for
    every state but `completed`, and `last_proven_stage` present for exactly those same three,
    because "how it ended" without "where evidence stops" is what user story 91 refuses.
    """
    _digest_value(
        assessment,
        "journal-anchor",
        document.get("journal_digest"),
        "the conductor record's journal_digest",
    )
    _identifier(assessment, "recording", document, "recorded_by", "the conductor record")
    _text(assessment, "recording", document, "verdict_destination", "the conductor record")
    _instant(assessment, "recording", document, "recorded_at", "the conductor record")
    ended = _choice(assessment, "ended-state", document, "ended_state", ENDED_STATES, "the conductor record")
    reasons = _string_list(assessment, "ended-state", document, "ended_reasons", "the conductor record")
    stage = document.get("last_proven_stage")
    if ended is None:
        return None
    if ended == ENDED_COMPLETED:
        if reasons:
            assessment.note(
                "ended-state",
                "the conductor record says the execution completed and still names ended_reasons; a "
                "completed execution has no ending reason, and prose that argues with the state it "
                "sits beside is how terminal language manufactures success",
            )
        if stage is not None:
            assessment.note(
                "ended-state",
                f"the conductor record says the execution completed and names last_proven_stage "
                f"{stage!r}; for a completed execution the last proven stage is the execution, so the "
                "field is null",
            )
        return ended
    if reasons is not None and not reasons:
        assessment.note(
            "ended-state",
            f"the conductor record says the execution ended {ended} and names no reason, so nothing "
            "states what ended it",
        )
    if not isinstance(stage, str) or not stage:
        assessment.note(
            "ended-state",
            f"the conductor record says the execution ended {ended} and its last_proven_stage is "
            f"{stage!r} rather than a non-empty string; an operator reading this needs where evidence "
            "stops, not only that it stopped",
        )
    return ended


def check_digest(
    assessment: Assessment, document: dict[str, Any], command: str, expect: str | None
) -> str | None:
    """The digest clause. `define` derives it; `verify` re-derives it and compares both bindings.

    `define` has no digest to check -- the body may not carry one, which `check_key_set` refuses by
    name -- so the derivation happens once, after the whole body is admitted, in `derive_command`.
    """
    if command == "define":
        return None
    recorded = _digest_value(assessment, "digest", document.get(DIGEST_KEY), "the submission's digest")
    if recorded is None:
        return None
    derived = submission_digest(document)
    if derived != recorded:
        assessment.note(
            "digest",
            f"the submission records digest {recorded} and its own content derives {derived}, so the "
            "document has been edited since it was sealed",
        )
        return None
    if expect is not None and derived != expect:
        assessment.note(
            "digest",
            f"the submission's digest {derived} is not the {expect} this caller requires, so this is "
            "not the submission that was recorded",
        )
        return None
    return derived


def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    """Load the supplied document, validate against the selected kind's closed schema, seal or verify."""
    command = args.command
    kind = args.kind
    document = load_document(args.submission, f"{kind} submission")

    assessment = Assessment(kind)
    check_key_set(assessment, document, kind, command)
    wave_id = check_wave_identity(assessment, document, kind)
    review_verdict = None
    ended_state = None
    declared: list[str] | None = None
    if kind == KIND_MANIFEST:
        declared = check_manifest(assessment, document)
    elif kind == KIND_REVIEW:
        review_verdict = check_review(assessment, document)
    elif kind == KIND_CRITIC:
        check_critic(assessment, document)
    elif kind == KIND_CONDUCTOR:
        ended_state = check_conductor_record(assessment, document)
    derived = check_digest(assessment, document, command, getattr(args, "expect_digest", None))

    verdict = assessment.verdict(command)
    sealed: dict[str, Any] | None = None
    digest: str | None = None
    if verdict == VERDICT_DEFINED:
        # Sealed only once the body is fully admitted: an illegal submission is unrepresentable in
        # the emitted document rather than emitted with a warning beside it.
        digest = submission_digest(document)
        sealed = dict(document)
        sealed[DIGEST_KEY] = digest
    elif verdict == VERDICT_VERIFIED:
        digest = derived
        sealed = dict(document)
    return {
        "schema": RESULT_SCHEMA,
        "command": command,
        "kind": kind,
        "submission_schema": SCHEMAS[kind],
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "submission": sealed,
        "digest": digest,
        # Republished ONLY for an admitted submission, so no consumer can read a partially admitted
        # one out of a refusal.
        "wave_id": wave_id if sealed is not None else None,
        "review_verdict": review_verdict if sealed is not None else None,
        "ended_state": ended_state if sealed is not None else None,
        "declared_artifacts": declared if sealed is not None else None,
        "checks": [
            {"met": not assessment.groups[slug], "reasons": assessment.groups[slug], "slug": slug}
            for slug in CHECKS[kind]
        ],
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }


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
    advisory_stderr()(f"wave-submission.py: {message}\n")


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence, so a stdout that cannot receive it is
    not a lost convenience -- the question was answered and the answer did not arrive. That is an
    internal failure to deliver (exit 1). `canonical_bytes` is `ensure_ascii=True`, so the payload is
    ASCII and a text stream with no `.buffer` -- what an importing caller's
    `redirect_stdout(StringIO())` installs -- receives byte-identical characters rather than being
    made to fail.
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
    if emit_to is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "result could not be delivered; nothing was sealed and nothing was recorded"
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
            "have reached the consumer, so the result was derived but not delivered"
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
    "as one JSON object, or the arguments themselves are unusable; 1 an unexpected internal failure, "
    "INCLUDING a stdout that cannot receive the one result document, because a submission sealed and "
    "not delivered is not a success. Implementation Decision 9's 3 and 4 do not apply: a command "
    "that causes no effect can neither refuse before one nor admit one."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="wave-submission.py",
        description=(
            "Seal and verify the four wave submissions wave-verdict.py consumes: the artifact "
            "manifest (condition 3), a review (condition 4), the critic's findings, and the "
            "conductor record (condition 8). Read-only, offline, subprocess-free, clock-free, and "
            "effect-free: it authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    define = commands.add_parser(
        "define",
        description=(
            "Validate one submission BODY against the selected kind's closed schema and emit the "
            "sealed document: the body plus exactly one added key, `digest`. The body may not carry "
            "a digest, and nothing is normalized, so the digested bytes are the bytes the caller "
            "wrote. A refused body is not sealed at all."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED submission's digest from its own content, re-check the closed "
            "schema, and refuse when either disagrees. --expect-digest is the binding a conductor "
            "uses to prove it is reading the submission it recorded."
        ),
        epilog=EPILOG,
    )
    for command in (define, verify):
        command.add_argument(
            "--kind",
            required=True,
            choices=list(KINDS),
            help="which of the four submissions this document is; there is no default",
        )
        command.add_argument(
            "--submission",
            required=True,
            help="the submission document to read",
        )
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the submission's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no submission "
            "could ever match it"
        )
        return EXIT_INPUT
    try:
        result = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
