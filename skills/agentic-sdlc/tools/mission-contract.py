#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Define, validate, and digest the MissionContract -- the first link in the planning artifact chain.

`docs/plans/claude-code-first-harness/to-spec-handoff.md` section "Planning artifact chain" is this
module's whole contract. It places one artifact first:

    MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope

and says the `MissionContract` "owns the durable objective, scope, constraints, authority classes,
completion contract, and stop conditions". Issue 16's "Planning artifact chain and deterministic
compiler" says the same thing with a different field list -- "objective, success and terminal
criteria, non-goals, constraints, authority ceiling, and mission-level stop conditions" -- and both
are honoured here: scope carries `non_goals`, the completion contract carries `success_criteria` and
`terminal_criteria`, and authority carries BOTH the admitted classes and the single ceiling they
derive. Where the two documents disagree is recorded in this docstring rather than silently resolved:
the handoff says "authority classes" (plural, a set) and issue 16 says "authority ceiling"
(singular), so this schema requires both and refuses a contract whose stated ceiling its own admitted
classes do not derive.

TWO COMMANDS, ONE DIGEST.

    define   reads a contract BODY, validates it against the closed schema, and emits the SEALED
             document: the body plus exactly one added key, `digest`.
    verify   reads a SEALED document, re-derives its digest from its own content, and refuses when
             the two disagree. `--expect-digest` is the binding a downstream consumer uses.

THE DIGEST IS THE LOAD-BEARING PART, because the wave-plan compiler and its admission gate bind it.
The contract is exact and there is only one way to compute it:

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

where `canonical` is this family's form -- `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=True`, `allow_nan=False`, and exactly one trailing newline. Three deliberate choices
make a second way to compute it unreachable:

  * `define` REFUSES a body that already carries a `digest`. A supplied digest would be a second
    origin for the one value, and a sealed document fed back into `define` would otherwise nest one.
  * `define` NORMALIZES NOTHING. A set-shaped field must already be in its canonical form -- the
    authority ladder in ladder order, `stop_conditions` sorted -- so the bytes that are digested are
    the bytes the caller wrote. A tool that quietly sorted its input would make the caller's own
    digest of that input disagree with this one, which is exactly two ways.
  * The `digest` key is EXCLUDED by name rather than by position or by being appended last, so the
    derivation does not depend on any ordering the JSON encoder happens to produce.

Input whitespace, key order, and non-ASCII spelling therefore cannot move the digest: the value is
derived from the parsed document re-encoded in the canonical form, never from the file's bytes.

MAKE AN ILLEGAL CONTRACT UNREPRESENTABLE. A refused contract is not emitted at all: `contract` and
`digest` are `null` and every field of the refused document stays unpublished, so no consumer can
read a partially admitted contract out of a refusal. The schema is CLOSED and validated against an
explicit key set at every level -- an unrecognised field is refused rather than ignored, because a
field this version does not understand is a meaning it cannot honour. Two vocabularies are closed
because downstream admission leans on them and free text would make admission guess:

  AUTHORITY CLASSES are a four-rung LADDER, ascending, each rung grounded in one sentence of the
  harness: `read-only-advisory` (issue 07: "Cartographers, researchers, and planners are read-only
  advisory nodes"), `owned-worktree-write` ("Implementers own isolated workstreams and worktrees"),
  `authorized-fan-in` ("One already-authorized integrator performs fan-in after accepted reviews"),
  and `outward-effect` (the handoff's publication, push, PR mutation, merge, and deployment set).
  `admitted_classes` must be a CONTIGUOUS PREFIX of that ladder in ladder order: authority that
  admits a worktree write without admitting a read is not a shape any node can hold, so it is
  unrepresentable rather than warned about. The `ceiling` is stated AND re-derived from the prefix,
  and a disagreement is a named refusal, exactly as the digest is.

  STOP CONDITIONS are a closed ten-token set, kept sorted and deduplicated so one set has one
  spelling. Four are MANDATORY and a contract omitting any of them is refused by name, because
  ADR-0025 and issue 16 make them non-waivable: an authority change and a scope change "always
  return for human disposition", hard-stop drift "immediately prevents the affected dispatch", and a
  partial or unknown prior effect "requires human disposition first". A contract that could omit one
  would be a contract that grants what no contract may grant. ADR-0030 superseded ADR-0025 but
  explicitly retained this rule, which is ADR-0019 doctrine; the citation above stands as its origin.

NO CLOCK. Every instant is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would refuse
honest input at random. `stated_at` is the family's fixed-width `YYYY-MM-DDTHH:MM:SSZ` form, whose
lexicographic order is chronological, and it is compared as a string. A revision chain is therefore
checked against the PREDECESSOR the caller supplies: revision N+1 must follow revision N, must
supersede that exact digest, must name the same mission, and must not be stamped before it. A
non-monotonic chain is refused by name rather than reordered.

FAIL CLOSED, AND NAME THE REASON. Every predicate accumulates named reasons against its own check
group; then ONE selection runs over ONE partition, so no input can yield two verdicts or none. A
bare "invalid" is useless to the human it asks, so every reason names the field and what was wrong
with it. Refusing is this module SUCCEEDING, which is why it exits 0.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. This module's exit space is 0, 2, and 1 only. 3 and 4 are both absent for
the same structural reason: **a tool that can cause no effect can neither refuse before one nor admit
one.** Nothing here opens a file for output, spawns a process, touches the network, or mutates state;
it reads the paths it is given and prints one document. So a derived `refused` is a result (0) and
not a clean refusal (3), and 4 is unreachable rather than merely unused. Exit 2 is reserved for a
supplied file that cannot be read as ONE JSON object -- unreadable, not a regular file, not JSON,
not an object, a repeated key, a non-finite constant, a number that OVERFLOWS to a non-finite float
(`1e400` is ordinary JSON number syntax and never reaches `parse_constant`) -- because that is the
QUESTION being unusable rather than the answer being "refused". 1 additionally covers a stdout that
cannot receive the one result document, because a contract sealed and not delivered is not a
success.

RESIDUALS, STATED EXACTLY.

  * The digest is RE-DERIVATION, not a security boundary. A same-OS-user forger can write a
    self-consistent sealed document; what the check catches is drift, a hand-edit, and a mismatched
    pair of artifacts.
  * Every field except the two closed vocabularies, the instants, and the digests is PROSE. This
    module proves a contract is well-formed and closed; it cannot prove an objective is achievable, a
    constraint is respected, or a success criterion is measurable.
  * The revision chain is only as long as the predecessor the caller supplies. One `--supersedes`
    hop is checked; an ancestry is not walked, so a chain is verified one link at a time.
  * A sealed contract is EVIDENCE. It authorizes no dispatch, no write, no push, publication, PR
    mutation, merge, or deployment, and its authority ceiling is a bound on what a later approval may
    grant, never a grant.
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
from pathlib import Path
from typing import Any

CONTRACT_SCHEMA = "agentic-sdlc/mission-contract@1"
RESULT_SCHEMA = "agentic-sdlc/mission-contract-result@1"

VERDICT_DEFINED = "defined"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_DEFINED: (
        "the contract is well-formed and closed, and the sealed document carries the one digest a "
        "wave plan may bind; the contract is evidence and authorizes nothing"
    ),
    VERDICT_VERIFIED: (
        "the sealed document re-derives its own digest and satisfies the closed schema, so it is the "
        "same contract it claims to be; the contract is evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "no contract was sealed and no digest was derived; the reasons name each field and what was "
        "wrong with it"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

#: The authority ladder, ASCENDING. `admitted_classes` must be a contiguous prefix of it.
AUTHORITY_LADDER = (
    "read-only-advisory",
    "owned-worktree-write",
    "authorized-fan-in",
    "outward-effect",
)

#: The four stop conditions no contract may omit; ADR-0025 and issue 16 make each non-waivable.
MANDATORY_STOP_CONDITIONS = (
    "authority-expansion-required",
    "hard-stop-drift",
    "scope-change-required",
    "unknown-or-partial-effect",
)
#: The six a mission may additionally declare, each grounded in issue 16's own stop language.
OPTIONAL_STOP_CONDITIONS = (
    "approval-invalid-or-expired",
    "budget-exhausted",
    "capability-unsupported",
    "contradictory-or-missing-evidence",
    "custody-conflict",
    "unresolved-runtime-assignment",
)
STOP_CONDITIONS = tuple(sorted(MANDATORY_STOP_CONDITIONS + OPTIONAL_STOP_CONDITIONS))

DIGEST_KEY = "digest"

#: The closed body: every key is REQUIRED, so an absence is always a named refusal and never a
#: default. `define` reads exactly this set; `verify` reads it plus `digest`.
BODY_KEYS = (
    "authority",
    "completion_contract",
    "constraints",
    "mission_id",
    "objective",
    "revision",
    "schema",
    "scope",
    "stated_at",
    "stop_conditions",
    "supersedes",
)
SEALED_KEYS = tuple(sorted(BODY_KEYS + (DIGEST_KEY,)))

#: The two nested objects, also closed.
SCOPE_KEYS = ("in_scope", "non_goals")
AUTHORITY_KEYS = ("admitted_classes", "ceiling")
COMPLETION_KEYS = ("success_criteria", "terminal_criteria")

CHECKS: tuple[str, ...] = (
    "closed-key-set",
    "identity-and-instant",
    "objective-and-scope",
    "constraints",
    "authority-ladder",
    "completion-contract",
    "stop-conditions",
    "revision-chain",
    "digest",
)

#: Carried in every document, because a consumer that binds the digest should carry what it does not
#: prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "every field outside the two closed vocabularies, the instants, and the digests is prose: a "
    "well-formed contract is not an achievable one",
    "one --supersedes hop is checked; an ancestry is not walked, so a chain is verified one link at "
    "a time",
    "a sealed contract is evidence: its authority ceiling bounds what a later approval may grant and "
    "never grants it",
)

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


def contract_digest(document: dict[str, Any]) -> str:
    """The ONE digest derivation: sha256 over the canonical bytes of the document minus `digest`.

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN` and `Infinity` by default; no honest contract carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _finite_number(token: str) -> float:
    """The OTHER way a non-finite float gets in: an ordinary JSON number that overflows.

    `parse_constant` fires only for the three literal tokens `NaN`, `Infinity`, and `-Infinity`.
    `1e400` is not one of them -- it is valid JSON number syntax that `float()` rounds to `inf` --
    so it slipped past that hook, reached `canonical_bytes`, and made its `allow_nan=False` raise a
    `ValueError` no caller of it catches: a traceback at exit 1 from `verify`, or from `define`
    re-deriving a `--supersedes` predecessor's digest, at ANY nesting depth. The rejection belongs
    HERE, at the parse hook, for the same reason: it is per number token, so depth and which of the
    two supplied documents carried it change nothing, and no digest derivation ever sees the value.
    """
    value = float(token)
    if not math.isfinite(value):
        raise InputError(
            f"a supplied document carries the non-finite JSON number {token}, which parses to "
            f"{value}: no honest contract carries one, and no canonical form can encode it"
        )
    return value


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a contract carrying two `revision`s
    parses to whichever the writer put second. That is a document with two meanings, and picking one
    of them is exactly the guess this module refuses everywhere else -- and it would also give the
    one digest two possible values.
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
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_pairs,
            parse_constant=_reject_nonfinite,
            parse_float=_finite_number,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} {path} is not a JSON object")
    return value


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the document can say which part of the schema is unmet, and
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


def _text(assessment: Assessment, slug: str, document: dict[str, Any], key: str) -> str | None:
    value = document.get(key)
    if not isinstance(value, str) or not value:
        assessment.note(
            slug,
            f"the mission contract's {key} is not a non-empty string (found {value!r}), so what it "
            "states cannot be read",
        )
        return None
    return value


def _prose_list(assessment: Assessment, slug: str, document: dict[str, Any], key: str) -> list[str] | None:
    value = document.get(key)
    if not isinstance(value, list) or not value:
        assessment.note(
            slug,
            f"the mission contract's {key} is not a non-empty list (found {value!r}); a mission that "
            "states none of them has no stated boundary at all",
        )
        return None
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            assessment.note(
                slug,
                f"the mission contract's {key} carries an entry at position {index} that is not a "
                f"non-empty string (found {item!r})",
            )
            return None
    return list(value)


def _closed_object(
    assessment: Assessment, slug: str, document: dict[str, Any], key: str, keys: tuple[str, ...]
) -> dict[str, Any] | None:
    value = document.get(key)
    if not isinstance(value, dict):
        assessment.note(
            slug,
            f"the mission contract's {key} is not a JSON object (found {value!r}), so its "
            f"{', '.join(keys)} cannot be read",
        )
        return None
    unknown = sorted(set(value) - set(keys))
    missing = sorted(set(keys) - set(value))
    for name in missing:
        assessment.note(slug, f"the mission contract's {key} carries no {name}, which mission-contract@1 requires")
    for name in unknown:
        assessment.note(
            slug,
            f"the mission contract's {key} carries the unknown field {name!r}; {key} is a closed "
            "object, so an unrecognised field is refused rather than ignored",
        )
    if missing or unknown:
        return None
    return value


def _instant(assessment: Assessment, slug: str, document: dict[str, Any], key: str) -> str | None:
    value = document.get(key)
    if not isinstance(value, str) or not _TIME.match(value):
        assessment.note(
            slug,
            f"the mission contract's {key} is not a YYYY-MM-DDTHH:MM:SSZ instant (found {value!r}); "
            "this tool reads no clock, so the instant is the caller's to state exactly",
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


# ---- check groups --------------------------------------------------------------------------------


def check_key_set(assessment: Assessment, document: dict[str, Any], command: str) -> None:
    """The closed schema itself: exactly these keys, no more and no fewer.

    `define` and `verify` differ by exactly one key, and the difference is checked in both
    directions: a body handed to `define` may NOT carry a derived digest, and a document handed to
    `verify` MUST.
    """
    expected = set(SEALED_KEYS) if command == "verify" else set(BODY_KEYS)
    present = set(document)
    for key in sorted(expected - present):
        assessment.note(
            "closed-key-set",
            f"the mission contract carries no {key}, which the closed mission-contract@1 schema "
            "requires of every contract",
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
            f"the mission contract carries the unknown field {key!r}; mission-contract@1 is a closed "
            "schema, so a field this version cannot honour is refused rather than ignored",
        )
    schema = document.get("schema")
    if "schema" in document and schema != CONTRACT_SCHEMA:
        assessment.note(
            "closed-key-set",
            f"the mission contract declares schema {schema!r}, not {CONTRACT_SCHEMA}, so which "
            "field set and which digest derivation it is about is not established",
        )


def check_identity(assessment: Assessment, document: dict[str, Any]) -> tuple[str | None, str | None]:
    mission_id = _text(assessment, "identity-and-instant", document, "mission_id")
    stated_at = _instant(assessment, "identity-and-instant", document, "stated_at")
    return mission_id, stated_at


def check_objective_and_scope(assessment: Assessment, document: dict[str, Any]) -> None:
    _text(assessment, "objective-and-scope", document, "objective")
    scope = _closed_object(assessment, "objective-and-scope", document, "scope", SCOPE_KEYS)
    if scope is None:
        return
    for key in SCOPE_KEYS:
        _prose_list(assessment, "objective-and-scope", scope, key)


def check_constraints(assessment: Assessment, document: dict[str, Any]) -> None:
    _prose_list(assessment, "constraints", document, "constraints")


def check_completion_contract(assessment: Assessment, document: dict[str, Any]) -> None:
    completion = _closed_object(
        assessment, "completion-contract", document, "completion_contract", COMPLETION_KEYS
    )
    if completion is None:
        return
    for key in COMPLETION_KEYS:
        _prose_list(assessment, "completion-contract", completion, key)


def check_authority(assessment: Assessment, document: dict[str, Any]) -> str | None:
    """The ladder. Returns the derived ceiling, or None.

    Three distinct mistakes are named distinctly, because "the classes are wrong" would leave the
    caller guessing which of the three it made: a token outside the vocabulary, a sequence that is
    not strictly ascending in LADDER ORDER (which covers both a reordering and a duplicate), and a
    strictly ascending sequence that is not a contiguous prefix starting at the lowest rung.
    """
    slug = "authority-ladder"
    authority = _closed_object(assessment, slug, document, "authority", AUTHORITY_KEYS)
    if authority is None:
        return None
    classes = authority.get("admitted_classes")
    if not isinstance(classes, list) or not classes:
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes is not a non-empty list (found "
            f"{classes!r}); every mission admits at least {AUTHORITY_LADDER[0]}",
        )
        return None
    unknown = [item for item in classes if not isinstance(item, str) or item not in AUTHORITY_LADDER]
    for item in unknown:
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes names {item!r}, which is not one of "
            f"the closed authority ladder {list(AUTHORITY_LADDER)}; downstream admission reads this "
            "vocabulary exactly, so free text is refused",
        )
    ceiling = authority.get("ceiling")
    if not isinstance(ceiling, str) or ceiling not in AUTHORITY_LADDER:
        assessment.note(
            slug,
            f"the mission contract's authority.ceiling is {ceiling!r}, which is not one of the closed "
            f"authority ladder {list(AUTHORITY_LADDER)}",
        )
        ceiling = None
    if unknown:
        return None
    rungs = [AUTHORITY_LADDER.index(item) for item in classes]
    if any(later <= earlier for earlier, later in zip(rungs, rungs[1:])):
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes {classes} is not strictly ascending "
            "in ladder order; one admitted set has one spelling, and a reordered or repeated rung is "
            "a second spelling of it that would derive a different digest",
        )
        return None
    if rungs != list(range(len(rungs))):
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes {classes} is not a contiguous prefix "
            f"of the ladder {list(AUTHORITY_LADDER)} starting at {AUTHORITY_LADDER[0]}: authority "
            "that admits a higher rung without every rung beneath it is not a shape any node can "
            "hold",
        )
        return None
    derived = AUTHORITY_LADDER[rungs[-1]]
    if ceiling is not None and ceiling != derived:
        assessment.note(
            slug,
            f"the mission contract states authority.ceiling {ceiling!r}, which its own "
            f"authority.admitted_classes {classes} do not derive ({derived!r})",
        )
        return None
    return None if ceiling is None else derived


def check_stop_conditions(assessment: Assessment, document: dict[str, Any]) -> list[str] | None:
    """The closed set, its one canonical spelling, and the floor no contract may go beneath."""
    slug = "stop-conditions"
    value = document.get("stop_conditions")
    if not isinstance(value, list) or not value:
        assessment.note(
            slug,
            f"the mission contract's stop_conditions is not a non-empty list (found {value!r}); a "
            "mission with no stop condition would be a mission with no stop",
        )
        return None
    unknown = [item for item in value if not isinstance(item, str) or item not in STOP_CONDITIONS]
    for item in unknown:
        assessment.note(
            slug,
            f"the mission contract's stop_conditions names {item!r}, which is not one of the closed "
            f"vocabulary {list(STOP_CONDITIONS)}; downstream admission reads this vocabulary exactly, "
            "so free text is refused",
        )
    if unknown:
        return None
    if any(later <= earlier for earlier, later in zip(value, value[1:])):
        assessment.note(
            slug,
            f"the mission contract's stop_conditions {value} is not sorted ascending without "
            "duplicates; one set has one spelling, and a reordered or repeated token is a second "
            "spelling of it that would derive a different digest",
        )
        return None
    for token in MANDATORY_STOP_CONDITIONS:
        if token not in value:
            assessment.note(
                slug,
                f"the mission contract's stop_conditions omit {token}, which no contract may waive: "
                "ADR-0025 and issue 16 return an authority change, a scope change, hard-stop drift, "
                "and a partial or unknown effect for human disposition in every case",
            )
    return list(value)


def check_revision_chain(
    assessment: Assessment,
    document: dict[str, Any],
    stated_at: str | None,
    mission_id: str | None,
    prior: dict[str, Any] | None,
    prior_path: str | None,
) -> tuple[int | None, str | None]:
    """The one hop this module can check, and the only place a sequence is compared.

    A revision beyond the first is meaningless without its predecessor, so an unsupplied predecessor
    is a named reason rather than an unchecked pass. The instants are the caller's, so the ONLY
    monotonicity claim made here is between two supplied documents.
    """
    slug = "revision-chain"
    revision = document.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        assessment.note(
            slug,
            f"the mission contract's revision is not an integer of at least 1 (found {revision!r}); "
            "the first contract of a mission is revision 1",
        )
        revision = None
    supersedes = document.get("supersedes")
    if revision == 1:
        if supersedes is not None:
            assessment.note(
                slug,
                f"the mission contract is revision 1 yet its supersedes names {supersedes!r}: the "
                "first contract of a mission supersedes nothing, so supersedes must be null",
            )
            supersedes = None
    elif revision is not None:
        supersedes = _digest_value(
            assessment, slug, supersedes, f"the mission contract's supersedes for revision {revision}"
        )
    if prior is None:
        if revision is not None and revision > 1:
            assessment.note(
                slug,
                f"the mission contract is revision {revision} and no predecessor was supplied, so the "
                "chain cannot be checked; pass the prior sealed contract with --supersedes",
            )
        return revision, supersedes
    where = str(prior_path)
    if revision == 1:
        assessment.note(
            slug,
            f"a predecessor was supplied ({where}) for a contract that is revision 1, which "
            "supersedes nothing; drop --supersedes or state the later revision",
        )
        return revision, supersedes
    prior_digest = _digest_value(assessment, slug, prior.get(DIGEST_KEY), f"the prior mission contract's digest")
    if prior_digest is not None and prior_digest != contract_digest(prior):
        assessment.note(
            slug,
            f"the prior mission contract {where} does not re-derive its own digest, so it is not the "
            "contract this revision claims to supersede",
        )
        prior_digest = None
    prior_revision = prior.get("revision")
    if isinstance(prior_revision, bool) or not isinstance(prior_revision, int) or prior_revision < 1:
        assessment.note(
            slug,
            f"the prior mission contract {where} states revision {prior_revision!r}, which is not an "
            "integer of at least 1, so this revision has nothing to follow",
        )
    elif revision is not None and revision != prior_revision + 1:
        assessment.note(
            slug,
            f"the mission contract is revision {revision}, which does not immediately follow the "
            f"supplied predecessor's revision {prior_revision}; a chain is verified one link at a time",
        )
    if supersedes is not None and prior_digest is not None and supersedes != prior_digest:
        assessment.note(
            slug,
            f"the mission contract's supersedes {supersedes} is not the supplied predecessor's digest "
            f"{prior_digest}, so the two documents are not one chain",
        )
    prior_mission = prior.get("mission_id")
    if mission_id is not None and prior_mission != mission_id:
        assessment.note(
            slug,
            f"the mission contract names mission_id {mission_id!r} and its predecessor names "
            f"{prior_mission!r}: a revision belongs to the mission it revises",
        )
    prior_at = prior.get("stated_at")
    if stated_at is not None and isinstance(prior_at, str) and _TIME.match(prior_at) and stated_at < prior_at:
        assessment.note(
            slug,
            f"the mission contract's stated_at {stated_at} is before its predecessor's {prior_at}: a "
            "revision sequence must be monotonic in the instants the caller states, and this tool "
            "reads no clock that could correct one",
        )
    return revision, supersedes


def check_digest(
    assessment: Assessment, document: dict[str, Any], command: str, expect: str | None
) -> str | None:
    """Re-derive the one digest. A recorded digest its own content does not derive is a refusal.

    For `define` there is nothing recorded yet, so the derivation happens once the body is otherwise
    admitted (in `derive_command`) and this group only carries the `--expect-digest` comparison. For
    `verify` the recorded value is the whole point: it is compared against the derivation over the
    document beside it.
    """
    slug = "digest"
    derived: str | None = None
    if command == "verify":
        recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the mission contract's digest")
        derived = contract_digest(document)
        if recorded is not None and recorded != derived:
            assessment.note(
                slug,
                f"the mission contract records digest {recorded} which its own content does not "
                f"re-derive ({derived}): the document has been edited since it was sealed, or the "
                "digest was written by something other than this derivation",
            )
    if expect is not None and derived is not None and expect != derived:
        assessment.note(
            slug,
            f"--expect-digest {expect} is not this contract's content digest {derived}, so the "
            "supplied document is not the contract the caller meant to bind",
        )
    return derived


def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    """Load the supplied documents, validate against the closed schema, then seal or verify."""
    command = args.command
    document = load_document(args.contract, "mission contract")
    prior = None
    if args.supersedes is not None:
        prior = load_document(args.supersedes, "prior mission contract")

    assessment = Assessment()
    check_key_set(assessment, document, command)
    mission_id, stated_at = check_identity(assessment, document)
    check_objective_and_scope(assessment, document)
    check_constraints(assessment, document)
    ceiling = check_authority(assessment, document)
    check_completion_contract(assessment, document)
    stop_conditions = check_stop_conditions(assessment, document)
    revision, supersedes = check_revision_chain(
        assessment, document, stated_at, mission_id, prior, args.supersedes
    )
    derived = check_digest(assessment, document, command, getattr(args, "expect_digest", None))

    verdict = assessment.verdict(command)
    sealed: dict[str, Any] | None = None
    digest: str | None = None
    if verdict == VERDICT_DEFINED:
        # Sealed only once the body is fully admitted: an illegal contract is unrepresentable in the
        # emitted document rather than emitted with a warning beside it.
        digest = contract_digest(document)
        sealed = dict(document)
        sealed[DIGEST_KEY] = digest
    elif verdict == VERDICT_VERIFIED:
        digest = derived
        sealed = dict(document)
    return {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "contract": sealed,
        "digest": digest,
        # Republished ONLY for an admitted contract. A refusal publishes none of the contract's
        # fields, so no consumer can read a partially admitted contract out of one.
        "mission_id": mission_id if sealed is not None else None,
        "authority_ceiling": ceiling if sealed is not None else None,
        "stop_conditions": stop_conditions if sealed is not None else None,
        "revision": revision if sealed is not None else None,
        "supersedes": supersedes if sealed is not None else None,
        "checks": [
            {"met": not assessment.groups[slug], "reasons": assessment.groups[slug], "slug": slug}
            for slug in CHECKS
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
    advisory_stderr()(f"mission-contract.py: {message}\n")


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
    "INCLUDING a stdout that cannot receive the one result document, because a contract sealed and "
    "not delivered is not a success. Implementation Decision 9's 3 and 4 do not apply: a command "
    "that causes no effect can neither refuse before one nor admit one."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="mission-contract.py",
        description=(
            "Define, validate, and digest the MissionContract -- the first link in the planning "
            "artifact chain MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> "
            "AutoEnvelope. Read-only, offline, subprocess-free, and effect-free: it authorizes "
            "nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    define = commands.add_parser(
        "define",
        description=(
            "Validate one contract BODY against the closed mission-contract@1 schema and emit the "
            "sealed document: the body plus exactly one added key, `digest`. The body may not carry "
            "a digest, and nothing is normalized, so the digested bytes are the bytes the caller "
            "wrote. A refused body is not sealed at all."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED document's digest from its own content and refuse when the two "
            "disagree. --expect-digest is the binding a downstream wave-plan compiler or admission "
            "gate uses."
        ),
        epilog=EPILOG,
    )
    for command in (define, verify):
        command.add_argument(
            "--contract",
            required=True,
            help=f"the {CONTRACT_SCHEMA} document to read",
        )
        command.add_argument(
            "--supersedes",
            default=None,
            help=(
                "the prior SEALED contract this revision follows; required for every revision beyond "
                "the first, and refused for revision 1"
            ),
        )
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the contract's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no contract "
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
