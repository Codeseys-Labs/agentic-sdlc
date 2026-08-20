#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Validate the common receipt envelope and check a receipt set's typed correlation graph.

`docs/plans/claude-code-first-harness/to-spec-handoff.md` "Evidence family" and issue 20's "Typed
receipts, effect journals, and correlation" are this module's whole contract. Two sentences of theirs
are the design:

    "Each kind has an independently versioned closed payload plus a common envelope for receipt kind
    and ID ... typed ancestor references ... and integrity digest."

    "Correlation is a typed evidence graph, not one overloaded correlation string. ... Missing,
    duplicate, dangling, cyclic where acyclicity is required, or kind-incompatible references are
    reported as evidence defects and cannot be repaired by display code."

So there are exactly two commands, and the split between them is the load-bearing design choice.

    verify       one document. The envelope's key set is closed and complete, every field is
                 well-formed, and the recorded content digest re-derives from the body beside it.
    check-graph  a JSONL set of receipt documents. Every typed ancestor reference must resolve, and
                 every defect is reported as one named finding carrying the implicated receipt ids.

VERIFY DERIVES NO RELATIONAL FACT, AND check-graph DERIVES NO SHAPE FACT IT DID NOT FIRST ADMIT.
`check-graph` runs the SAME envelope check over every line before it derives one finding, so any
relational property `verify` refused would be unreachable as a finding: a receipt naming the same
ancestor twice with the same relation, or naming ITSELF, is well-formed as a document and is a
`duplicate` or a `cyclic` FINDING, never an envelope refusal. That is why the ancestor list is not
order- or duplicate-constrained the way a set-shaped field elsewhere in this family is. In the other
direction, a set containing one line this module cannot admit as a receipt is not a graph: it is
refused with that line named, and NO finding is derived from it, because a dangling reference
derived from a set with an unreadable member would be manufactured rather than observed.

THE CLOSED ENVELOPE is exactly seven fields plus the body they describe:

    schema           `agentic-sdlc/receipt-envelope@1`, the envelope contract itself. A family's own
                     payload version lives inside `body` and is not this schema.
    receipt_kind     one of the six families the handoff names, closed.
    receipt_id       this receipt's own identity, one lowercase ASCII token.
    stated_at        the caller's fixed-width `YYYY-MM-DDTHH:MM:SSZ` instant.
    emitting_plane   the plane that emitted it, one lowercase ASCII token. NOT closed; see below.
    content_digest   sha256 over the canonical bytes of `body`.
    ancestors        typed ancestor references, each naming the ancestor's `receipt_id`, the
                     `expected_kind` the child believes it has, and the `relation` it holds.
    body             the family's independently versioned payload, OPAQUE to this module.

Every key is required and an unrecognised key is refused rather than ignored, at the top level and
inside every reference, because a field this version cannot honour is a meaning it cannot check.

TWO VOCABULARIES ARE CLOSED, and one deliberately is not.

  RECEIPT KINDS are the six families of the handoff's "Evidence family" and issue 20's identical
  list: `distribution-activation`, `route-credential-lifecycle`, `probe-qualification`,
  `workflow-wave-node-attempt`, `integration-completion`, and `incident-recovery`. A reference states
  the kind it EXPECTS, so an unclosed kind vocabulary would make `kind-incompatible` uncheckable.

  RELATIONS are six, each grounded in one sentence rather than invented: `contained-by` (the spine
  "derives paths and fan-out"), `derived-from` ("referenced evidence"), `references-evidence` (the
  same sentence's other half, kept distinct because naming evidence is not deriving from it),
  `supersedes` (migration "writes a new typed artifact ... and keeps the original"), `retries` (the
  wave view's "retries"), and `remediates` (the "incident or recovery" family). Every one of them
  points at an ANCESTOR, and ancestry is acyclic, so acyclicity is required of the whole graph --
  which is what "cyclic where acyclicity is required" resolves to here.

  EMITTING PLANE is an open token, on purpose. This repository's planes are named but their set is
  not closed by any document and it moves: ADR-0014 removed `ccodex`'s private plane and the
  separately named `claude-subscription` route, and `scripts/muse-claude.sh` is now the only launcher
  with one. A closed list here would have refused an honest receipt from a plane that existed when it
  was written and would refuse again at every addition. What correlation actually needs is that one
  plane has ONE SPELLING, which the token shape gives.

WHAT THIS ENVELOPE DOES NOT OWN YET. Issue 20's envelope sentence also lists producer and schema
versions, physical subject and scope, plan and approval digests, start and close times, terminal
status, effect state, blockers, bounded next action, redaction profile, and artifact references.
They are deliberately outside this increment's closed set: no receipt family payload exists in this
repository yet, and a closed schema that required fields no producer writes would refuse every
receipt that will ever be written against it. They arrive with the first family that has them, as
`receipt-envelope@2` or as closed payload fields, not as loose optional keys here.

THE DIGEST SEALS THE BODY, and only the body:

    content_digest = sha256( canonical( body ) )

where `canonical` is this family's form -- `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=True`, `allow_nan=False`, and exactly one trailing newline. Body-only sealing is what
lets a consumer bind a payload it has not copied, which is issue 20's "derives paths and fan-out
without copying the artifacts". Its cost is stated in the residuals rather than hidden: an edited
envelope field does not disturb this digest.

FINDINGS ARE A CLOSED FIVE-TOKEN SET and a finding is a REPORT, not a refusal. `dangling` (a
reference whose target is not in the set), `duplicate` (one receipt naming the same ancestor twice
with the same relation), `kind-incompatible` (the target's own kind is not the kind the reference
expects), `cyclic` (a reference loop), and `duplicate-id` (one receipt id carried by two documents).
A repeated receipt id makes every reference naming it AMBIGUOUS, so resolution is not derived over
such a set at all: `resolution_checked` is false and the absence of a `dangling` finding then means
"not checked" rather than "clean". A consumer that read an empty finding list as clean without
reading that field would be the display code issue 20 forbids from repairing a defect.

CYCLE DETECTION IS ITERATIVE. The walk is an explicit-stack depth-first search with an explicit
grey/black colouring, because a receipt chain is as long as a mission is old and a recursive walk
would raise `RecursionError` on a deep chain -- turning an honest graph into an internal failure.

NO CLOCK. `stated_at` is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would refuse
honest input at random. Nothing here orders receipts by time: ancestry is the order, and the instant
is checked for shape only.

FAIL CLOSED, AND NAME THE REASON. Every predicate accumulates named reasons against its own check
group; then ONE selection runs over ONE partition, so no input can yield two verdicts or none. Every
reason names the field and what was wrong with it. Refusing is this module SUCCEEDING, so it exits 0.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. This module's exit space is 0, 2, and 1 only, and 3 and 4 are absent for
the same structural reason: **a tool that can cause no effect can neither refuse before one nor admit
one.** Nothing here opens a file for output, spawns a process, touches the network, or mutates state.
Exit 2 is reserved for supplied input that cannot be read as receipt documents at all -- unreadable,
not a regular file, not UTF-8, not JSON, not an object, a repeated JSON key, a non-finite number, a
blank JSONL line, an empty set, or JSON nested deeper than this interpreter can decode -- because
that is the QUESTION being unusable rather than the answer being "refused". 1 additionally covers a
stdout that cannot receive the one result document, because a graph checked and not reported is not
a success.

RESIDUALS, STATED EXACTLY.

  * The content digest seals the BODY. An edited `stated_at`, `emitting_plane`, or ancestor list
    leaves it re-deriving. A consumer that must bind the envelope records the receipt id and content
    digest pair in its own evidence, or a later family adds its own envelope seal.
  * The digest is RE-DERIVATION, not a security boundary. A same-OS-user forger can write a
    self-consistent receipt; what this catches is drift, a hand-edit, and a mismatched pair.
  * A `cyclic` finding names the receipts on ONE detected loop, not every simple cycle through them:
    enumerating all of them is exponential in the graph, and one named loop is what a human repairs.
  * The graph is exactly the supplied set. A reference to a receipt that exists in another file is
    reported `dangling`, because this module reads no file it was not given.
  * `body` is OPAQUE. This module proves a payload is sealed and unchanged; it never proves the
    payload is well-formed for its family, and it reads no field inside it.
  * A verified receipt and a clean graph are EVIDENCE. They grant no approval, admission, completion,
    or outward authority, and no finding here authorizes a repair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA = "agentic-sdlc/receipt-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/receipt-envelope-result@1"

VERDICT_VERIFIED = "verified"
VERDICT_GRAPH_CLEAN = "graph-clean"
VERDICT_GRAPH_DEFECTIVE = "graph-defective"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_VERIFIED: (
        "the receipt carries the closed receipt-envelope@1 field set and its content digest "
        "re-derives from the body beside it; the receipt is evidence and grants no approval, "
        "admission, completion, or outward authority"
    ),
    VERDICT_GRAPH_CLEAN: (
        "every supplied receipt is a well-formed envelope and every typed ancestor reference "
        "resolves to a receipt of the kind it expects, with no duplicate, dangling, cyclic, or "
        "kind-incompatible reference and no repeated receipt id; a clean graph is evidence and "
        "authorizes nothing"
    ),
    VERDICT_GRAPH_DEFECTIVE: (
        "every supplied receipt is a well-formed envelope, and the typed evidence graph over them "
        "carries the named findings; a finding is an evidence defect that display code may not "
        "repair, and it must be resolved where the receipt was written"
    ),
    VERDICT_REFUSED: (
        "no receipt was admitted and no graph was checked; the reasons name each field and what was "
        "wrong with it, and no finding was derived because a set with an unadmitted member is not a "
        "graph"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The six receipt families, from the handoff's "Evidence family" and issue 20's identical list.
RECEIPT_KINDS = (
    "distribution-activation",
    "incident-recovery",
    "integration-completion",
    "probe-qualification",
    "route-credential-lifecycle",
    "workflow-wave-node-attempt",
)

#: The six relations a child may hold to a direct typed ancestor. Every one points at an ancestor,
#: so every one participates in the acyclicity requirement.
RELATIONS = (
    "contained-by",
    "derived-from",
    "references-evidence",
    "remediates",
    "retries",
    "supersedes",
)

FINDING_CYCLIC = "cyclic"
FINDING_DANGLING = "dangling"
FINDING_DUPLICATE = "duplicate"
FINDING_DUPLICATE_ID = "duplicate-id"
FINDING_KIND_INCOMPATIBLE = "kind-incompatible"
FINDINGS = (
    FINDING_CYCLIC,
    FINDING_DANGLING,
    FINDING_DUPLICATE,
    FINDING_DUPLICATE_ID,
    FINDING_KIND_INCOMPATIBLE,
)

DIGEST_KEY = "content_digest"
BODY_KEY = "body"

#: The closed envelope: every key is REQUIRED, so an absence is always a named refusal.
ENVELOPE_KEYS = (
    "ancestors",
    "body",
    "content_digest",
    "emitting_plane",
    "receipt_id",
    "receipt_kind",
    "schema",
    "stated_at",
)

#: One typed ancestor reference, also closed: who, what kind it is believed to be, and how.
REFERENCE_KEYS = ("expected_kind", "receipt_id", "relation")

#: The closed finding record. Every key is present in every finding, so a consumer reads one shape.
FINDING_KEYS = (
    "ancestor_receipt_id",
    "detail",
    "finding",
    "implicated_receipt_ids",
    "receipt_id",
    "relation",
)

CHECKS: tuple[str, ...] = (
    "closed-key-set",
    "identity-and-instant",
    "emitting-plane",
    "ancestor-references",
    "content-digest",
)

#: Carried in every document, because a consumer that binds a receipt should carry what it does not
#: prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the content digest seals the body only: an edited stated_at, emitting_plane, or ancestor list "
    "leaves it re-deriving, so a consumer that must bind the envelope records the receipt id and "
    "content digest pair in its own evidence",
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "a cyclic finding names the receipts on one detected loop, not every simple cycle through them",
    "the graph is exactly the supplied set: a reference to a receipt recorded in another file is "
    "reported dangling, because this module reads no file it was not given",
    "the body is opaque: a sealed payload is not a payload proved well-formed for its family",
    "a verified receipt and a clean graph are evidence: they grant no approval, admission, "
    "completion, or outward authority, and no finding authorizes a repair",
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_TOKEN = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")

#: `parse_constant` never sees an overflowing literal: `1e400` becomes `inf` inside the float parser,
#: so the value walk below is the second half of the same guard rather than a duplicate of it.
_INFINITY = float("inf")


class InputError(Exception):
    """Supplied input cannot be read as receipt documents (exit 2).

    Deliberately separate from a named reason: unusable input means the QUESTION could not be asked,
    while a reason means it was asked and the answer is "refused".
    """


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def body_digest(body: dict[str, Any], subject: str) -> str:
    """The ONE digest derivation: sha256 over the canonical bytes of the body.

    The re-encode can exhaust the interpreter's stack on a body the decoder accepted, and a
    `RecursionError` escaping here would be a traceback where this module owes a classified exit.
    """
    try:
        return hashlib.sha256(canonical_bytes(body)).hexdigest()
    except RecursionError as exc:
        raise InputError(
            f"{subject} carries a body nested too deeply to re-encode canonically, so its content "
            f"digest cannot be derived: {exc}"
        ) from exc


def _reject_nonfinite_constant(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest receipt carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _reject_nonfinite_values(value: Any, subject: str) -> None:
    """Refuse a number that BECAME non-finite while parsing, which `parse_constant` cannot see.

    `json.loads('{"n": 1e400}')` yields `inf` without ever calling `parse_constant`, and `inf` would
    then reach `json.dumps(..., allow_nan=False)` inside the digest derivation as a `ValueError`. The
    walk is iterative because the decoder admits nesting far deeper than a recursive walk survives.
    """
    stack: list[Any] = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, float) and not -_INFINITY < current < _INFINITY:
            raise InputError(
                f"{subject} carries the non-finite number {current!r}, which no canonical document "
                "can encode"
            )
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a receipt carrying two `receipt_id`s
    parses to whichever the writer put second. That is a document with two meanings, and picking one
    of them is exactly the guess this module refuses everywhere else.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"a supplied document repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


def read_regular_file(path: str, label: str) -> str:
    """Read one supplied path as UTF-8 text. Every failure here is unusable input (exit 2).

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
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputError(f"the {label} {path} is not UTF-8 text: {exc}") from exc


def parse_json_object(text: str, subject: str) -> dict[str, Any]:
    """Parse one JSON object, with both non-finite guards and the repeated-key guard applied."""
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_reject_nonfinite_constant)
    except RecursionError as exc:
        raise InputError(
            f"{subject} nests JSON deeper than this interpreter can decode, so it cannot be read as "
            f"one receipt document: {exc}"
        ) from exc
    except ValueError as exc:
        raise InputError(f"{subject} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"{subject} is not a JSON object")
    _reject_nonfinite_values(value, subject)
    return value


def load_receipt(path: str) -> dict[str, Any]:
    return parse_json_object(read_regular_file(path, "receipt"), f"the receipt {path}")


def load_receipt_set(path: str) -> list[tuple[int, dict[str, Any]]]:
    """Read a JSONL receipt set: one receipt document per line, numbered from 1.

    An empty set is refused rather than reported clean, because a caller pointing at the wrong path
    would otherwise read "no defects" out of a file with no receipts in it.
    """
    text = read_regular_file(path, "receipt set")
    documents: list[tuple[int, dict[str, Any]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise InputError(
                f"line {number} of the receipt set {path} is blank, and every line of a JSONL "
                "receipt set is exactly one receipt document"
            )
        documents.append((number, parse_json_object(line, f"line {number} of the receipt set {path}")))
    if not documents:
        raise InputError(
            f"the receipt set {path} carries no receipt document, and an empty set would report a "
            "clean graph that proves nothing"
        )
    return documents


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the document can say which part of the envelope is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree.
    """

    def __init__(self) -> None:
        self.groups: dict[str, list[str]] = {slug: [] for slug in CHECKS}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in CHECKS:
            flat.extend(self.groups[slug])
        return flat

    def verdict(self, command: str, findings: list[dict[str, Any]]) -> str:
        """Exactly one verdict, always.

        The selection is one partition over one value, so two verdicts are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no verdict --
        and it is a named reason rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command == "verify":
            return VERDICT_VERIFIED
        if command == "check-graph":
            return VERDICT_GRAPH_DEFECTIVE if findings else VERDICT_GRAPH_CLEAN
        self.note(
            "closed-key-set",
            f"no verdict follows from the command {command!r}, and an underivable verdict is a "
            "refusal rather than a guess",
        )
        return VERDICT_REFUSED


# ---- envelope predicates -------------------------------------------------------------------------
# Each returns the well-formed value, or None having noted its own named reason. Returning None means
# "this field cannot be reasoned about further", which is how the graph checker below knows to derive
# nothing from it.


def _token(assessment: Assessment, slug: str, document: dict[str, Any], key: str, subject: str) -> str | None:
    """One lowercase ASCII token. The shape is what makes cross-document comparison exact.

    An id or plane spelled with a capital, a space, or an Arabic-Indic digit is a DIFFERENT string
    that reads like the same identity, and correlation compares these values literally: a reference
    to `Wave-1` would be reported dangling beside a receipt id of `wave-1` with no field named. The
    character class is written `[a-z0-9]` and never `\\w` or `\\d`, both of which admit Unicode.
    """
    value = document.get(key)
    if not isinstance(value, str) or not _TOKEN.match(value):
        assessment.note(
            slug,
            f"{subject}'s {key} is not a lowercase ASCII token of letters, ASCII digits, and interior "
            f"hyphens (found {value!r}); correlation compares this value literally, so one identity "
            "must have exactly one spelling",
        )
        return None
    return value


def _instant(assessment: Assessment, slug: str, document: dict[str, Any], subject: str) -> str | None:
    value = document.get("stated_at")
    if not isinstance(value, str) or not _TIME.match(value):
        assessment.note(
            slug,
            f"{subject}'s stated_at is not a YYYY-MM-DDTHH:MM:SSZ instant (found {value!r}); this "
            "tool reads no clock, so the instant is the caller's to state exactly",
        )
        return None
    return value


def _closed_vocabulary(
    assessment: Assessment, slug: str, value: Any, key: str, vocabulary: tuple[str, ...], subject: str
) -> str | None:
    if not isinstance(value, str) or value not in vocabulary:
        assessment.note(
            slug,
            f"{subject}'s {key} is {value!r}, which is not one of the closed vocabulary "
            f"{list(vocabulary)}; a reference states the kind it expects, so free text here would "
            "make an incompatible reference uncheckable",
        )
        return None
    return value


def check_key_set(assessment: Assessment, document: dict[str, Any], subject: str) -> None:
    """The closed envelope itself: exactly these keys, no more and no fewer."""
    present = set(document)
    for key in sorted(set(ENVELOPE_KEYS) - present):
        assessment.note(
            "closed-key-set",
            f"{subject} carries no {key}, which the closed receipt-envelope@1 field set requires of "
            "every receipt family",
        )
    for key in sorted(present - set(ENVELOPE_KEYS)):
        assessment.note(
            "closed-key-set",
            f"{subject} carries the unknown field {key!r}; receipt-envelope@1 is a closed envelope, "
            "so a field this version cannot honour is refused rather than ignored, and a family's "
            "own payload fields belong inside body",
        )
    schema = document.get("schema")
    if "schema" in document and schema != ENVELOPE_SCHEMA:
        assessment.note(
            "closed-key-set",
            f"{subject} declares schema {schema!r}, not {ENVELOPE_SCHEMA}, so which envelope field "
            "set and which digest derivation it is about is not established; a family payload's own "
            "version belongs inside body",
        )


def check_identity(assessment: Assessment, document: dict[str, Any], subject: str) -> tuple[str | None, str | None]:
    slug = "identity-and-instant"
    receipt_id = _token(assessment, slug, document, "receipt_id", subject)
    _instant(assessment, slug, document, subject)
    kind = _closed_vocabulary(
        assessment, slug, document.get("receipt_kind"), "receipt_kind", RECEIPT_KINDS, subject
    )
    return receipt_id, kind


def check_plane(assessment: Assessment, document: dict[str, Any], subject: str) -> None:
    _token(assessment, "emitting-plane", document, "emitting_plane", subject)


def check_ancestors(
    assessment: Assessment, document: dict[str, Any], subject: str
) -> list[dict[str, str]] | None:
    """Every typed ancestor reference, checked for SHAPE only.

    An empty list is admitted: the first receipt of a lifecycle has no ancestor. Order and repetition
    are NOT constrained here, and that is deliberate -- `check-graph` runs this same check over every
    line, so an envelope refusal for a repeated or self-naming reference would make the `duplicate`
    and `cyclic` findings unreachable.
    """
    slug = "ancestor-references"
    value = document.get("ancestors")
    if not isinstance(value, list):
        assessment.note(
            slug,
            f"{subject}'s ancestors is not a JSON list (found {value!r}); a receipt with no ancestor "
            "states the empty list, because an absent list and no ancestors are different claims",
        )
        return None
    references: list[dict[str, str]] = []
    for index, item in enumerate(value):
        where = f"{subject}'s ancestors[{index}]"
        if not isinstance(item, dict):
            assessment.note(slug, f"{where} is not a JSON object (found {item!r}), so it names no ancestor")
            continue
        unknown = sorted(set(item) - set(REFERENCE_KEYS))
        missing = sorted(set(REFERENCE_KEYS) - set(item))
        for key in missing:
            assessment.note(
                slug,
                f"{where} carries no {key}; a typed ancestor reference names the ancestor's "
                "receipt_id, the expected_kind it is believed to have, and the relation held",
            )
        for key in unknown:
            assessment.note(
                slug,
                f"{where} carries the unknown field {key!r}; a typed ancestor reference is a closed "
                "object, so an unrecognised field is refused rather than ignored",
            )
        if missing or unknown:
            continue
        ancestor_id = _token(assessment, slug, item, "receipt_id", where)
        expected = _closed_vocabulary(
            assessment, slug, item.get("expected_kind"), "expected_kind", RECEIPT_KINDS, where
        )
        relation = _closed_vocabulary(assessment, slug, item.get("relation"), "relation", RELATIONS, where)
        if ancestor_id is None or expected is None or relation is None:
            continue
        references.append({"expected_kind": expected, "receipt_id": ancestor_id, "relation": relation})
    if len(references) != len(value):
        return None
    return references


def check_content_digest(assessment: Assessment, document: dict[str, Any], subject: str) -> str | None:
    """Re-derive the one digest over the body. A recorded digest the body does not derive is refused."""
    slug = "content-digest"
    body = document.get(BODY_KEY)
    if not isinstance(body, dict) or not body:
        assessment.note(
            slug,
            f"{subject}'s body is not a non-empty JSON object (found {body!r}); the content digest "
            "seals the family payload, and an absent payload seals nothing",
        )
        return None
    recorded = document.get(DIGEST_KEY)
    if not isinstance(recorded, str) or not _HEX64.match(recorded):
        assessment.note(
            slug,
            f"{subject}'s content_digest is not 64 lowercase hexadecimal characters (found "
            f"{recorded!r}), so it cannot be a sha256 over any canonical body",
        )
        return None
    derived = body_digest(body, subject)
    if recorded != derived:
        assessment.note(
            slug,
            f"{subject} records content_digest {recorded} which its own body does not re-derive "
            f"({derived}): the body has been edited since the receipt was sealed, or the digest was "
            "written by something other than this derivation",
        )
        return None
    return derived


def check_envelope(
    assessment: Assessment, document: dict[str, Any], subject: str
) -> tuple[str | None, str | None, list[dict[str, str]] | None, str | None]:
    """One receipt against the closed envelope. The only shape check either command runs."""
    check_key_set(assessment, document, subject)
    receipt_id, kind = check_identity(assessment, document, subject)
    check_plane(assessment, document, subject)
    references = check_ancestors(assessment, document, subject)
    digest = check_content_digest(assessment, document, subject)
    return receipt_id, kind, references, digest


# ---- the typed correlation graph -----------------------------------------------------------------


def finding(
    name: str,
    detail: str,
    implicated: list[str],
    *,
    receipt_id: str | None = None,
    ancestor_receipt_id: str | None = None,
    relation: str | None = None,
) -> dict[str, Any]:
    """One finding record, always the same closed key set so a consumer reads one shape."""
    return {
        "ancestor_receipt_id": ancestor_receipt_id,
        "detail": detail,
        "finding": name,
        "implicated_receipt_ids": implicated,
        "receipt_id": receipt_id,
        "relation": relation,
    }


def _finding_order(record: dict[str, Any]) -> tuple[Any, ...]:
    """A total order over findings, so one set of receipts reports one byte-identical finding list."""
    return (
        record["finding"],
        tuple(record["implicated_receipt_ids"]),
        record["receipt_id"] or "",
        record["ancestor_receipt_id"] or "",
        record["relation"] or "",
    )


def duplicate_id_findings(carried_by: dict[str, list[int]]) -> list[dict[str, Any]]:
    records = []
    for receipt_id in sorted(carried_by):
        lines = carried_by[receipt_id]
        if len(lines) < 2:
            continue
        records.append(
            finding(
                FINDING_DUPLICATE_ID,
                f"the receipt id {receipt_id} is carried by the documents on lines "
                f"{', '.join(str(line) for line in lines)}; every reference naming it is therefore "
                "ambiguous, so no dangling, kind-incompatible, or cyclic finding is derived over "
                "this set",
                [receipt_id],
                receipt_id=receipt_id,
            )
        )
    return records


def duplicate_reference_findings(receipts: list[tuple[str, list[dict[str, str]]]]) -> list[dict[str, Any]]:
    """One receipt naming the same ancestor twice with the same relation.

    Intrinsic to a single document, so it is derived even over a set with a repeated receipt id: no
    reference has to RESOLVE for this defect to be visible.
    """
    records = []
    for receipt_id, references in receipts:
        counts: dict[tuple[str, str], int] = {}
        for reference in references:
            key = (reference["receipt_id"], reference["relation"])
            counts[key] = counts.get(key, 0) + 1
        for (ancestor_id, relation), count in sorted(counts.items()):
            if count < 2:
                continue
            records.append(
                finding(
                    FINDING_DUPLICATE,
                    f"the receipt {receipt_id} names the ancestor {ancestor_id} {count} times with "
                    f"the relation {relation}; one typed edge has one spelling, and a repeated edge "
                    "would double this ancestor's fan-out in every projection",
                    sorted({receipt_id, ancestor_id}),
                    receipt_id=receipt_id,
                    ancestor_receipt_id=ancestor_id,
                    relation=relation,
                )
            )
    return records


def resolution_findings(
    kinds: dict[str, str], receipts: list[tuple[str, list[dict[str, str]]]]
) -> list[dict[str, Any]]:
    """Every reference resolves, and resolves to a receipt of the kind the reference expects."""
    records = []
    for receipt_id, references in receipts:
        for reference in references:
            ancestor_id = reference["receipt_id"]
            relation = reference["relation"]
            expected = reference["expected_kind"]
            if ancestor_id not in kinds:
                records.append(
                    finding(
                        FINDING_DANGLING,
                        f"the receipt {receipt_id} names the ancestor {ancestor_id} with the "
                        f"relation {relation}, and no receipt in this set carries that id; the "
                        "reference resolves to nothing here",
                        [receipt_id, ancestor_id],
                        receipt_id=receipt_id,
                        ancestor_receipt_id=ancestor_id,
                        relation=relation,
                    )
                )
                continue
            actual = kinds[ancestor_id]
            if actual != expected:
                records.append(
                    finding(
                        FINDING_KIND_INCOMPATIBLE,
                        f"the receipt {receipt_id} expects the ancestor {ancestor_id} to be a "
                        f"{expected} receipt and it is a {actual} receipt; the reference resolves to "
                        "a receipt of another kind, so the child's typed claim about its own "
                        "ancestry is wrong",
                        [receipt_id, ancestor_id],
                        receipt_id=receipt_id,
                        ancestor_receipt_id=ancestor_id,
                        relation=relation,
                    )
                )
    return records


def detect_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Every loop the walk finds, each as an ordered id list. ITERATIVE, never recursive.

    An explicit-stack depth-first search with an explicit colouring: a node on the current path is
    grey, a node whose subtree is finished is black. An edge into a grey node is a back edge, and the
    loop is the current path from that node onward. Recursion is what this deliberately avoids -- a
    receipt chain is as long as a mission is old, and `RecursionError` on an honest graph would be an
    internal failure where this module owes a report.

    Each loop is canonicalised by rotating its smallest id to the front, so two back edges into the
    same loop report it once and the report does not depend on which id the walk started from.
    """
    grey, black = 1, 2
    state: dict[str, int] = {}
    loops: dict[tuple[str, ...], list[str]] = {}
    for start in sorted(edges):
        if state.get(start):
            continue
        state[start] = grey
        path = [start]
        stack: list[tuple[str, Any]] = [(start, iter(sorted(edges[start])))]
        while stack:
            node, remaining = stack[-1]
            descended = False
            for target in remaining:
                colour = state.get(target, 0)
                if colour == grey:
                    loop = path[path.index(target) :]
                    pivot = loop.index(min(loop))
                    rotated = loop[pivot:] + loop[:pivot]
                    loops[tuple(rotated)] = rotated
                elif colour != black:
                    state[target] = grey
                    path.append(target)
                    stack.append((target, iter(sorted(edges.get(target, set())))))
                    descended = True
                    break
            if not descended:
                stack.pop()
                state[node] = black
                path.pop()
    return [loops[key] for key in sorted(loops)]


def cycle_findings(edges: dict[str, set[str]]) -> list[dict[str, Any]]:
    records = []
    for loop in detect_cycles(edges):
        closed = " -> ".join([*loop, loop[0]])
        records.append(
            finding(
                FINDING_CYCLIC,
                f"these receipts reference each other in a closed loop ({closed}); every relation "
                "names an ancestor and ancestry is acyclic, so no receipt on this loop can be an "
                "ancestor of the others",
                list(loop),
                receipt_id=loop[0],
            )
        )
    return records


def check_graph(
    receipts: list[tuple[int, str, str, list[dict[str, str]]]]
) -> tuple[list[dict[str, Any]], bool]:
    """Derive every finding over an already-admitted receipt set. Returns (findings, resolved).

    `resolved` is false exactly when a repeated receipt id made every reference to it ambiguous. The
    flag is published rather than implied, because an empty finding list that meant "not checked"
    would be the display code issue 20 forbids from smoothing over a defect.
    """
    carried_by: dict[str, list[int]] = {}
    for line, receipt_id, _kind, _references in receipts:
        carried_by.setdefault(receipt_id, []).append(line)
    # Sorted by the KEY only: two documents carrying one receipt id would otherwise put their
    # reference lists into the comparison, and a list of dicts has no order at all.
    ordered = [
        (receipt_id, references)
        for _line, receipt_id, _kind, references in sorted(receipts, key=lambda item: (item[1], item[0]))
    ]

    records = duplicate_id_findings(carried_by)
    records.extend(duplicate_reference_findings(ordered))
    resolved = not any(len(lines) > 1 for lines in carried_by.values())
    if resolved:
        kinds = {receipt_id: kind for _line, receipt_id, kind, _references in receipts}
        records.extend(resolution_findings(kinds, ordered))
        edges: dict[str, set[str]] = {receipt_id: set() for receipt_id in kinds}
        for receipt_id, references in ordered:
            edges[receipt_id].update(
                reference["receipt_id"] for reference in references if reference["receipt_id"] in kinds
            )
        records.extend(cycle_findings(edges))
    unique = {_finding_order(record): record for record in records}
    return [unique[key] for key in sorted(unique)], resolved


# ---- commands ------------------------------------------------------------------------------------


def derive_verify(args: argparse.Namespace) -> tuple[Assessment, dict[str, Any]]:
    document = load_receipt(args.receipt)
    assessment = Assessment()
    receipt_id, kind, _references, digest = check_envelope(assessment, document, "the receipt")
    admitted = not assessment.reasons()
    return assessment, {
        "receipt_id": receipt_id if admitted else None,
        "receipt_kind": kind if admitted else None,
        "content_digest": digest if admitted else None,
        "receipts_checked": None,
        "resolution_checked": None,
        "findings": [],
    }


def derive_check_graph(args: argparse.Namespace) -> tuple[Assessment, dict[str, Any]]:
    documents = load_receipt_set(args.receipts)
    assessment = Assessment()
    admitted: list[tuple[int, str, str, list[dict[str, str]]]] = []
    for line, document in documents:
        receipt_id, kind, references, _digest = check_envelope(
            assessment, document, f"the receipt on line {line}"
        )
        if receipt_id is not None and kind is not None and references is not None:
            admitted.append((line, receipt_id, kind, references))
    if assessment.reasons():
        # A set with a member this module cannot admit as a receipt is not a graph: deriving a
        # dangling reference from it would manufacture a defect out of an unreadable neighbour.
        return assessment, {
            "receipt_id": None,
            "receipt_kind": None,
            "content_digest": None,
            "receipts_checked": None,
            "resolution_checked": None,
            "findings": [],
        }
    findings, resolved = check_graph(admitted)
    return assessment, {
        "receipt_id": None,
        "receipt_kind": None,
        "content_digest": None,
        "receipts_checked": len(admitted),
        "resolution_checked": resolved,
        "findings": findings,
    }


def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    command = args.command
    if command == "verify":
        assessment, payload = derive_verify(args)
    else:
        assessment, payload = derive_check_graph(args)
    verdict = assessment.verdict(command, payload["findings"])
    return {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        # The receipt itself is never republished: the result names and digests it instead, which is
        # what lets a projection derive paths without copying the artifact.
        "receipt_id": payload["receipt_id"],
        "receipt_kind": payload["receipt_kind"],
        "content_digest": payload["content_digest"],
        "receipts_checked": payload["receipts_checked"],
        "resolution_checked": payload["resolution_checked"],
        "findings": payload["findings"],
        "checks": [
            {"met": not assessment.groups[slug], "reasons": assessment.groups[slug], "slug": slug}
            for slug in CHECKS
        ],
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }


# ---- delivery ------------------------------------------------------------------------------------


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
    advisory_stderr()(f"receipt-envelope.py: {message}\n")


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
            "result could not be delivered; nothing was verified and no graph was reported"
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
    "Exit codes: 0 a result was derived, a named refusal and a reported finding included; 2 supplied "
    "input cannot be read as receipt documents, or the arguments themselves are unusable; 1 an "
    "unexpected internal failure, INCLUDING a stdout that cannot receive the one result document, "
    "because a graph checked and not reported is not a success. Implementation Decision 9's 3 and 4 "
    "do not apply: a command that causes no effect can neither refuse before one nor admit one."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="receipt-envelope.py",
        description=(
            "Validate the common immutable-receipt envelope and check a receipt set's typed "
            "correlation graph. Read-only, offline, subprocess-free, and effect-free: a receipt is "
            "evidence and this tool authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser(
        "verify",
        description=(
            f"Check one document against the closed {ENVELOPE_SCHEMA} field set and re-derive its "
            "content digest from the body beside it. Shape only: a repeated or self-naming ancestor "
            "reference is a graph finding, not an envelope refusal."
        ),
        epilog=EPILOG,
    )
    verify.add_argument("--receipt", required=True, help=f"the {ENVELOPE_SCHEMA} document to read")
    graph = commands.add_parser(
        "check-graph",
        description=(
            "Check the typed evidence graph over a JSONL receipt set: every ancestor reference must "
            "resolve to a receipt of the kind it expects, with no duplicate, dangling, cyclic, or "
            f"kind-incompatible reference and no repeated receipt id. Findings are exactly "
            f"{list(FINDINGS)} and every one names the implicated receipt ids."
        ),
        epilog=EPILOG,
    )
    graph.add_argument(
        "--receipts",
        required=True,
        help=f"a JSONL file whose every line is one {ENVELOPE_SCHEMA} document",
    )
    args = parser.parse_args(argv)
    try:
        result = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
