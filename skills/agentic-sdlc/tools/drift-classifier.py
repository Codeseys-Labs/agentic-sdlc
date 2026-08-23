#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Classify observed drift against one sealed WavePlan into issue 16's four closed outcomes.

Issue 16's "Drift taxonomy and boundary checks" section fixes the whole job (line numbers are into
`docs/plans/claude-code-first-harness/issues/16-define-planning-drift-and-bounded-auto-mode.md`):

    :72-73  "Plan drift is any observed difference between current state and a load-bearing
             MissionContract, PlanningSnapshot, approved WavePlan, admitted artifact, or approval
             invariant."
    :74     "The classifier has four closed outcomes."
    :79     "Ambiguous classification is `hard-stop`, never compatible."

THE OUTCOME IS A TABLE LOOKUP, NOT A JUDGEMENT. `TABLE` maps each of the sixteen change kinds the
PlanDiff vocabulary names to exactly one of the four outcomes, and every row carries the issue-16
clause it is grounded in as DATA, published into the classification. A table is the shape this
question has: scattered conditionals would let two branches disagree about one kind, and a caller
auditing "why is a budget change replan-required" would have to read control flow instead of one row.
The kinds are re-expressed here rather than imported -- a sibling tool is consumed as documents, and a
shared constant would hide the day the two vocabularies diverged.

THE SEVERITY FOLD IS THE ONLY DERIVATION OVER THE SET. The overall outcome is the MAXIMUM severity
across the observed changes, over the semantic order

    compatible < revalidation-required < replan-required < hard-stop

which is deliberately NOT the alphabetical order of the same four strings (alphabetically `hard-stop`
sorts second). `SEVERITY` is the only thing that orders them, so an alphabetical sort could never be
mistaken for this fold. One hard-stop among a hundred compatible changes is a hard-stop: :106-107 says
"No acknowledgement, retry, old approval, or unaffected gate can downgrade the stop."

THE SAFETY RULE, APPLIED FOUR WAYS. :79 is unconditional, so every input this tool cannot interpret
UNAMBIGUOUSLY is classified `hard-stop` rather than refused and rather than tolerated:

  * an unknown change kind -- a string outside the closed sixteen;
  * a subject the bound plan does not name -- no node, edge, custody path, or mission of that name;
  * a plan-digest mismatch -- the observation says it watched a plan whose digest is not this one, so
    which plan the sentences are about is unknown;
  * an empty or uninterpretable change entry -- an entry that is not an object of three non-empty
    strings states something this tool cannot read.

These are OUTCOMES, not refusals, and the difference is load-bearing: refusing would leave the caller
holding no sealed document at the exact moment it most needs one to stop on, and :102-103 requires a
hard-stop to be RECORDED with its blocker.

AN EMPTY OBSERVED LIST IS ITS OWN VERDICT. `no-drift` is a fifth VERDICT, never a fifth outcome and
never a silent `compatible`: :74-75 says `compatible` "means the change is unrelated or explicitly
tolerated and all affected invariants still hold", which is a statement ABOUT a change, and there is
no change to say it about. So an empty list seals `overall_outcome: null` beside a `no_drift_reason`
sentence, exactly as `plan-diff@1` makes an empty diff explicit, and the two fields are cross-checked
in both directions so neither can be sealed disagreeing with the other. An empty list whose binding
does not hold is still `hard-stop`: zero observations about an unknown plan is not "no drift".

`compatible` IS REPRESENTABLE AND UNREACHABLE FROM THIS TABLE, and that is a stated limit rather than
an oversight, for TWO independent reasons. Every one of the sixteen kinds names a plan-bound dimension
by construction, so none is "unrelated"; and "explicitly tolerated" (:74) needs a tolerance declaration
that no artifact in this chain carries yet. Separately, the compiler's own PlanDiff marks a prose-only
node change `semantic: false`, but `observed-drift@1`'s three-field change entry drops that flag
entirely, so a prose-only `changed-node` reaches this table exactly like a semantic one and lands on
its REPLAN row rather than `compatible` -- an over-escalation that fails closed rather than a wrong
`compatible`. `RESIDUALS` says so, so closing either gap has to change the residual in the same change.

TWO DOCUMENTS IN, ONE OUT, AND NO IMPORTS BETWEEN TOOLS.

    --plan      a SEALED agentic-sdlc/wave-plan@1        (wave-plan-compiler.py's output)
    --observed  a SEALED agentic-sdlc/observed-drift@1   (this file defines it; see OBSERVED_BODY_KEYS)

`classify` seals one agentic-sdlc/drift-classification@1 and publishes it in its one result document;
`--out` additionally writes it, O_EXCL and fsynced. `verify` re-derives a sealed classification from
its own content: closed key set, every field, the three cross-checks the fold has to satisfy, and its
one digest.

READ-ONLY, OFFLINE, CLOCK-FREE, SUBPROCESS-FREE. No model call, no git, no route resolution, no
environment read, and no repair: :110-112 says "Drift detection never repairs, resets, rebases, checks
out, stashes, overwrites, removes, reauthenticates, reroutes, or rewrites a queue." `--at` is a
supplied argument because this tool reads no clock. A sealed classification is EVIDENCE: it authorizes
no dispatch, no replan, and no continuation.

EXITS. 0 a result was derived, a named refusal included; 2 a supplied file cannot be read as one JSON
object or an argument is itself unusable; 1 a derived result that could not be DELIVERED. 3 and 4 are
unreachable: a refusal happens before anything is written, and the single `--out` write is O_EXCL, so
a creation that then failed is reported by name and counted as an undelivered result rather than as an
admitted partial effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
OBSERVED_SCHEMA = "agentic-sdlc/observed-drift@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/drift-classification@1"
RESULT_SCHEMA = "agentic-sdlc/drift-classifier-result@1"

VERDICT_CLASSIFIED = "classified"
VERDICT_NO_DRIFT = "no-drift"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

CONSEQUENCE = {
    VERDICT_CLASSIFIED: (
        "one drift classification was sealed: every observed change carries its own outcome and the "
        "issue-16 clause that outcome is grounded in, and the overall outcome is the maximum severity "
        "among them; it is evidence for a human disposition and authorizes no dispatch and no replan"
    ),
    VERDICT_NO_DRIFT: (
        "the observed-drift document names no change against the bound plan, so the sealed "
        "classification records an explicit no-drift observation rather than a compatible "
        "classification; it states that nothing was observed, not that nothing changed"
    ),
    VERDICT_VERIFIED: (
        "the sealed classification re-derives from its own content: its closed key set, every field, "
        "the severity fold, and its one digest; whether its observations are still current is a fresh "
        "observation's question, never this one's"
    ),
    VERDICT_REFUSED: (
        "no classification was sealed, no digest was derived, and nothing was written; the reasons name "
        "each input or field and what was wrong with it"
    ),
}

EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

DIGEST_KEY = "digest"

#: Issue 16 lines 57-61 enumerate exactly what a PlanDiff must name, and `wave-plan-compiler.py`'s
#: `CHANGE_KINDS` is that enumeration. RE-EXPRESSED, not imported: this tool consumes that tool's
#: sealed documents, and a shared constant would hide the day the two vocabularies diverged.
CHANGE_KINDS = tuple(
    sorted(
        (
            "added-edge",
            "added-node",
            "approval",
            "artifact",
            "authority",
            "budget",
            "changed-node",
            "custody-boundary",
            "egress",
            "gate",
            "removed-edge",
            "removed-node",
            "retry",
            "route-constraint",
            "stop-rule",
            "terminal-criterion",
        )
    )
)

#: The four closed outcomes of :74-79, IN SEMANTIC SEVERITY ORDER. This tuple's ORDER is the fold, so
#: it is deliberately not sorted: alphabetically `hard-stop` would sort second and a maximum over that
#: order would call an authority boundary less severe than a replan.
OUTCOMES_BY_SEVERITY = ("compatible", "revalidation-required", "replan-required", "hard-stop")
#: The same four as a closed VOCABULARY, sorted, for admitting a field value. Two names for one set,
#: because one of the two questions is about order and the other is about membership.
OUTCOMES = tuple(sorted(OUTCOMES_BY_SEVERITY))
SEVERITY = {name: rank for rank, name in enumerate(OUTCOMES_BY_SEVERITY)}
HARD_STOP = "hard-stop"

#: :79, quoted once and cited by every one of the four ambiguity grounds below, because they are four
#: applications of ONE rule and a paraphrase in any of them would be this tool inventing a fifth.
AMBIGUOUS = 'issue 16:79 "Ambiguous classification is `hard-stop`, never compatible."'

# ---- THE TABLE -----------------------------------------------------------------------------------
# Sixteen kinds, one outcome each, and the issue-16 clause the row is grounded in carried as DATA so
# the sealed classification publishes its own reasoning. Three of the four outcomes appear; the
# absence of `compatible` is stated in `RESIDUALS` rather than papered over with a plausible row.
#
# Fourteen rows are grounded in the replan EXAMPLE LIST at :96-98 -- "changes to mission or terminal
# criteria, nodes or edges, repository base or owned paths, dependencies, custody, required artifacts,
# policies or gates, capability demands, route constraints, egress, budgets, retries, fallback,
# integration, or review" -- which is very nearly the PlanDiff vocabulary itself. That lopsidedness is
# the issue's, not this table's: the two kinds the example list does NOT name (`approval`, `authority`)
# are exactly the two rows that land elsewhere, and `stop-rule` is the one row grounded in the general
# definition at :77 instead of an example.

REPLAN = "replan-required"
REVALIDATION = "revalidation-required"

#: :77, quoted once. Every replan row cites it, because the example list at :96-98 is examples OF this
#: sentence and a row grounded only in an example would not say what the outcome MEANS.
_CLAUSE_77 = '"replan-required means graph semantics or a plan-bound invariant changed"'
_DEFINITION = f"issue 16:77 {_CLAUSE_77}"
_GRAPH = f'issue 16:96 lists "nodes or edges" among the changes that produce a new revision, and {_DEFINITION}'


def _example(quoted: str) -> str:
    """One replan row's ground: the exact phrase from the :96-98 example list, plus the definition."""
    return (
        f'issue 16:96-98 lists "{quoted}" among the changes that produce a new PlanningSnapshot, '
        f"WavePlan revision, and PlanDiff, and {_DEFINITION}"
    )


TABLE: dict[str, tuple[str, str]] = {
    "added-edge": (REPLAN, f"{_GRAPH}; an added edge is an ordering the approved graph did not have"),
    "added-node": (REPLAN, f"{_GRAPH}; an added node is work the approved graph did not contain"),
    #: NOT hard-stop. :106 forbids an "old approval" DOWNGRADING a stop, which is a different rule from
    #: classifying approval drift itself; :91-93 puts approval validity inside revalidation, and :93's
    #: "Otherwise it becomes replan-required" is the escalation the RENEWAL decides, not this table.
    "approval": (
        REVALIDATION,
        'issue 16:91-93 permits continuing "without a new plan approval only when the semantic digest '
        'is unchanged and the existing approval explicitly remains valid under refreshed evidence", '
        'and :75-76 "revalidation-required means plan semantics are unchanged but one or more '
        'freshness, identity, capability, or admission facts must be renewed"; an approval is an '
        "admission fact",
    ),
    "artifact": (REPLAN, _example("required artifacts")),
    #: The one hard-stop row. The replan example list at :96-98 names no authority dimension at all,
    #: while :77-79 and :105 name authority twice.
    "authority": (
        HARD_STOP,
        'issue 16:77-79 "hard-stop means continuation would cross an authority, ownership, security, '
        'credential, destructive/outward-effect, or unknown-effect boundary", and :105 includes '
        '"authority expansion" by name; the replan example list at :96-98 names no authority dimension',
    ),
    "budget": (REPLAN, _example("budgets")),
    "changed-node": (REPLAN, f"{_GRAPH}; a changed node is replaced in a new revision, never edited"),
    #: Replan rather than hard-stop, and the boundary is real: :104's "foreign or ambiguous ownership"
    #: is an OBSERVATION about who owns a path, while this kind names a change to the plan's own
    #: declared custody boundary, which :97 lists as "custody". `RESIDUALS` states the half this
    #: vocabulary cannot express.
    "custody-boundary": (REPLAN, _example("custody")),
    #: Replan rather than hard-stop, on the same split: :105's "new destructive or outward effect" is
    #: an observed effect, while this kind names the plan's declared egress, which :98 lists as
    #: "egress". `RESIDUALS` states the half this vocabulary cannot express.
    "egress": (REPLAN, _example("egress")),
    "gate": (REPLAN, _example("policies or gates")),
    "removed-edge": (REPLAN, f"{_GRAPH}; a removed edge lets two nodes run concurrently that could not"),
    "removed-node": (REPLAN, f"{_GRAPH}; a removed node releases whatever custody it held"),
    "retry": (REPLAN, _example("retries")),
    "route-constraint": (REPLAN, _example("route constraints")),
    #: The one row grounded in the general definition instead of an example: the :96-98 list does not
    #: name a stop rule, and a stop rule is what closes a plan's bounds, so changing one changes a
    #: plan-bound invariant.
    "stop-rule": (
        REPLAN,
        f"{_DEFINITION}; the replan example list at :96-98 does not name a stop rule, and a stop rule "
        "is what closes the plan's bounds, so changing one changes a plan-bound invariant",
    ),
    "terminal-criterion": (REPLAN, _example("mission or terminal criteria")),
}

#: This file's own input schema: a list of observed changes bound to the plan digest they were observed
#: against. `observed_at` is when the OBSERVATION happened and `classified_at` is when this tool ran;
#: :81-88 checks drift "against fresh bounded observations" at named boundaries, and collapsing the two
#: instants would make a stale observation indistinguishable from a fresh one.
OBSERVED_BODY_KEYS = ("changes", "observation_id", "observed_at", "plan_digest", "schema")
#: Three fields per observed change, and no more. There is deliberately no `semantic` boolean and no
#: caller-supplied severity: the outcome is THIS tool's derivation from the kind, and a field for it
#: would let an observer grade its own drift.
OBSERVED_CHANGE_KEYS = ("kind", "observation", "subject")

CLASSIFICATION_BODY_KEYS = (
    "assessments",
    "binding",
    "classified_at",
    "mission_id",
    "no_drift_reason",
    "observation_id",
    "observed_at",
    "overall_outcome",
    "plan_digest",
    "plan_revision",
    "schema",
)
#: `kind`, `subject`, and `observation` are each a non-empty string OR null: an uninterpretable entry is
#: classified rather than refused, and null is how the document says "this entry did not state one".
ASSESSMENT_KEYS = ("grounds", "kind", "observation", "outcome", "subject")
#: The observation's OWN claim about which plan it watched, kept beside the plan's real digest rather
#: than instead of it. `plan_digest` at the top level is the plan this classification is about; there is
#: no second copy of it here, because a document recording one fact twice can record it two ways.
BINDING_KEYS = ("bound", "ground", "observed_plan_digest")

OBSERVED_SEALED_KEYS = tuple(sorted(OBSERVED_BODY_KEYS + (DIGEST_KEY,)))
CLASSIFICATION_SEALED_KEYS = tuple(sorted(CLASSIFICATION_BODY_KEYS + (DIGEST_KEY,)))

#: The sibling fields this tool CONSUMES from a wave-plan@1, by dotted name. Only these are required of
#: it: the rest of that schema is `wave-plan-compiler.py`'s business, and re-validating it here would
#: make this file a second implementation of a schema it does not own.
PLAN_REQUIRED = ("edges", "mission_id", "nodes", "revision")

#: The one sentence an empty observation carries. Fixed rather than composed, so two runs over two
#: identical inputs seal identical bytes.
NO_DRIFT = (
    "the observed-drift document names no change at all, so this is an explicit no-drift observation "
    "over the bound plan; it records that nothing was observed at this boundary, which is not the same "
    "statement as a compatible classification of a change and not a claim that nothing changed"
)

CHECKS: tuple[str, ...] = ("wave-plan", "observed-drift", "drift-classification", "output-path", "digest")
CLASSIFY_CHECKS = ("wave-plan", "observed-drift", "output-path")
VERIFY_CHECKS = ("drift-classification", "digest")
#: The two input positions of `classify`. A reason against either means nothing downstream may be
#: reasoned about, because the table needs the kinds and the subject set needs the plan.
INPUT_SLUGS = ("wave-plan", "observed-drift")

RESIDUALS = (
    "`compatible` is representable in this schema and unreachable from this table, for TWO independent "
    "reasons. Every one of the sixteen kinds names a plan-bound dimension by construction, so no kind "
    'is issue 16:74\'s "unrelated"; and "explicitly tolerated" needs a tolerance declaration that no '
    "artifact in this planning chain carries yet. Separately, the compiler's own PlanDiff marks a "
    "prose-only node change `semantic: false`, but `observed-drift@1`'s three-field change entry drops "
    "that flag entirely, so a genuinely prose-only `changed-node` reaches this table exactly like a "
    "semantic one and lands on its REPLAN row rather than `compatible`; this fails closed -- it never "
    "wrongly reports `compatible` -- but it over-escalates rather than reading the compiler's own "
    "distinction. Adding a tolerance declaration or carrying the semantic flag is a schema change, and "
    "either has to change this residual",
    "the kind vocabulary cannot split three pairs issue 16 classifies differently. `custody-boundary` "
    'is the plan\'s DECLARED boundary (:97 "custody", replan) and not :104\'s observed "foreign or '
    'ambiguous ownership" (hard-stop); `egress` is the plan\'s DECLARED egress (:98 "egress", replan) '
    'and not :105\'s observed "new destructive or outward effect" (hard-stop); `stop-rule` is the '
    "plan's DECLARED stop-rule set (:77, replan, this table's own grounding) and not :104's \"credential "
    'or security-boundary change" (hard-stop) -- removing or narrowing a rule that guards exactly that '
    "boundary is itself the change :104 names. An observer who sees the hard-stop half of any of the "
    "three pairs cannot say so through this vocabulary and must stop out of band",
    "`authority` is classified hard-stop in both directions. :105 names \"authority expansion\", and a "
    "narrowing is not an expansion, but the kind carries no direction, so the safety rule at :79 "
    "resolves the ambiguity upward rather than admitting a narrowing as benign",
    "the two ambiguities just stated are resolved in OPPOSITE directions, and that asymmetry is itself "
    "worth stating on its own: `authority`'s direction ambiguity resolves UPWARD to hard-stop for both "
    "directions, matching :79's rule that ambiguous classification is hard-stop; the three declared-vs-"
    "observed pairs above instead resolve DOWNWARD to their table row's severity (replan-required, "
    "never hard-stop); that downward resolution is this tool's own stipulation about which reading of "
    "the kind name the vocabulary encodes, not an ambiguous classification :79 governs, so it is "
    "disclosed here rather than licensed by :79. Each stipulation individually matches the compiler's "
    "own vocabulary and is disclosed above; only the asymmetry between the two policies was previously "
    "undocumented",
    "a subject is admitted if the plan names it ANYWHERE -- as a node, an edge, a custody path, or the "
    "mission. That a `custody-boundary` change names a node id rather than a path, or an `added-edge` "
    "names a node rather than an edge, is not checked: the plan names both spellings and no row of the "
    "table depends on which one arrived",
    "two observations of one (kind, subject) pair are classified twice and both reach the fold. That "
    "cannot change the maximum, so it is left as recorded rather than deduplicated: two sentences about "
    "one dimension are two observations, and dropping one would delete evidence",
    "the digest is RE-DERIVATION, not a security boundary. A same-OS-user forger can write a "
    "self-consistent sealed document; what these checks catch is drift, a hand-edit, and a mismatched "
    "pair of artifacts",
    "this tool observes nothing itself. It classifies the sentences it was handed, so an observation "
    "that missed a change, or that was true when taken and is false now, is classified exactly as "
    "written; issue 16:87-88 says the check \"creates evidence only and does not install a watcher or "
    'claim detection between those boundaries"',
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[0-9A-Za-z][0-9A-Za-z._-]*\Z")


class InputError(Exception):
    """A supplied file or argument cannot be used at all (exit 2).

    Deliberately separate from a named reason: unusable input means the QUESTION could not be asked,
    while a reason means it was asked and the answer is "refused".
    """


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight separators, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def document_digest(document: dict[str, Any]) -> str:
    """The ONE digest derivation: sha256 over the canonical bytes of the document minus `digest`.

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it, and one
    function covers all three sealed artifact kinds this tool reads or writes.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest artifact carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so an observation carrying two `changes`
    arrays parses to whichever the writer put second. That is a document with two meanings, and picking
    one of them would also give the one digest two possible values.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"a supplied document repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


def _assert_finite(value: Any, where: str) -> None:
    """Refuse a non-finite float that no constant token announced.

    `parse_constant` catches the `NaN`/`Infinity` spellings, and nothing else: the literal `1e400` is an
    ordinary JSON number that overflows to `inf` during parsing without ever passing through that hook.
    It has to be refused because `canonical_bytes` runs with `allow_nan=False`, so an infinity reaching
    the digest derivation would raise out of this module as a traceback instead of being classified.

    The walk is ITERATIVE. Nesting is written by whoever supplied the file, and a recursive walk would
    trade a classified refusal for a `RecursionError` on exactly the hostile input this check exists for.
    """
    stack: list[tuple[Any, str]] = [(value, where)]
    while stack:
        item, path = stack.pop()
        if isinstance(item, float) and not math.isfinite(item):
            raise InputError(f"{path} carries the non-finite number {item!r}, which no digest can cover")
        if isinstance(item, dict):
            stack.extend((entry, f"{path} at key {key!r}") for key, entry in item.items())
        elif isinstance(item, list):
            stack.extend((entry, f"{path} at position {index}") for index, entry in enumerate(item))


def load_document(path: str, label: str) -> dict[str, Any]:
    """Read one supplied document. Every failure here is unusable input (exit 2), never a reason.

    The regular-file check runs BEFORE the read: opening a FIFO blocks until a writer shows up, which
    for a supplied path may be never, so a directory mistake would exit 2 promptly while a FIFO mistake
    hung forever. `Path.stat()` follows a symlink to its target, which is the question this asks.

    `RecursionError` is classified here too: `json`'s scanner recurses once per nesting level, so a
    deeply nested supplied file is unusable input rather than an internal failure of this module.
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
    except RecursionError as exc:
        raise InputError(f"the {label} {path} nests too deeply to be parsed, so it cannot be read") from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} {path} is not a JSON object")
    _assert_finite(value, f"the {label} {path}")
    return value


class Assessment:
    """The accumulating evidence. Nothing here decides; `verdict` derives from the reasons.

    Reasons are held PER CHECK GROUP so the result can say which part of the job is unmet, and the flat
    `reasons` list is generated from the same store, so the two can never disagree. The flat list walks
    EVERY group rather than the command's own subset: a reason noted against a group this command does
    not report must still reach the verdict.
    """

    def __init__(self, order: tuple[str, ...]) -> None:
        self.order = order
        self.groups: dict[str, list[str]] = {slug: [] for slug in CHECKS}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in CHECKS:
            flat.extend(self.groups[slug])
        return flat

    def document(self) -> list[dict[str, Any]]:
        return [
            {"met": not self.groups[slug], "reasons": self.groups[slug], "slug": slug}
            for slug in CHECKS
            if slug in self.order or self.groups[slug]
        ]

    def verdict(self, command: str, *, no_drift: bool) -> str:
        """Exactly one verdict, always.

        The selection is one partition over one value, so two verdicts are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no verdict --
        and it is a named reason rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command == "classify":
            return VERDICT_NO_DRIFT if no_drift else VERDICT_CLASSIFIED
        if command == "verify":
            return VERDICT_VERIFIED
        self.note(
            "drift-classification",
            f"no verdict follows from the command {command!r}, and an underivable verdict is a refusal "
            "rather than a guess",
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
            slug, f"{what} is not a non-empty string (found {value!r}), so what it records cannot be read"
        )
        return None
    return value


def _identifier(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    """An id that names a document. Bounded so a refusal and a sealed field can quote it unambiguously."""
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not _IDENTIFIER.match(value):
        assessment.note(
            slug,
            f"{what} {value!r} is not an identifier of unreserved characters (letters, digits, and then "
            "any of . _ -), so it cannot be quoted back unambiguously",
        )
        return None
    return value


def _instant(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not _TIME.match(value):
        assessment.note(slug, f"{what} {value!r} is not a YYYY-MM-DDTHH:MM:SSZ instant")
        return None
    return value


def _digest_value(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    if not isinstance(value, str) or not _HEX64.match(value):
        assessment.note(
            slug,
            f"{what} is not 64 lowercase hexadecimal characters (found {value!r}), so it cannot be a "
            "sha256 content digest",
        )
        return None
    return value


def _positive_integer(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> int | None:
    value = container.get(key)
    # `isinstance(True, int)` is True, so booleans are excluded by type: `"revision": true` is a
    # mistake, not the number 1.
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        assessment.note(slug, f"{what} is not an integer of at least 1 (found {value!r})")
        return None
    return value


def _closed_object(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, keys: tuple[str, ...], what: str
) -> dict[str, Any] | None:
    value = container.get(key)
    if not isinstance(value, dict):
        assessment.note(slug, f"{what} is not a JSON object (found {value!r})")
        return None
    found = tuple(sorted(value))
    if found != tuple(sorted(keys)):
        missing = [name for name in sorted(keys) if name not in value]
        extra = [name for name in found if name not in keys]
        assessment.note(
            slug, f"{what} is not the closed key set {sorted(keys)}: missing {missing}, unexpected {extra}"
        )
        return None
    return value


def _member(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, vocabulary: tuple[str, ...], what: str
) -> str | None:
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if value not in vocabulary:
        assessment.note(slug, f"{what} {value!r} is not one of {list(vocabulary)}")
        return None
    return value


def _sealed_input(
    assessment: Assessment, slug: str, document: dict[str, Any], schema: str, keys: tuple[str, ...] | None, what: str
) -> str | None:
    """Admit one SEALED input: its declared schema string, then its own digest. Returns the digest.

    Both halves are named refusals rather than exit codes: the file was readable and was one JSON
    object, so the question was asked and the answer is "refused".
    """
    declared = document.get("schema")
    if declared != schema:
        assessment.note(
            slug,
            f"{what} declares schema {declared!r} rather than {schema!r}, so it is not the document kind "
            "this input position consumes",
        )
        return None
    if keys is not None:
        found = tuple(sorted(document))
        if found != keys:
            missing = [name for name in keys if name not in document]
            extra = [name for name in found if name not in keys]
            assessment.note(
                slug, f"{what} is not the closed sealed key set {list(keys)}: missing {missing}, unexpected {extra}"
            )
            return None
    recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), f"{what}'s recorded digest")
    if recorded is None:
        return None
    derived = document_digest(document)
    if recorded != derived:
        assessment.note(
            slug,
            f"{what} records digest {recorded} which its own content does not re-derive ({derived}): the "
            "document has been edited since it was sealed, or the digest was written by something other "
            "than this family's derivation",
        )
        return None
    return recorded


def _required_fields(
    assessment: Assessment, slug: str, document: dict[str, Any], dotted: tuple[str, ...], what: str
) -> None:
    """Require only the sibling fields THIS tool consumes, each named by its dotted path.

    An empty LIST is admitted where an empty string or object is not: a one-node plan legitimately
    carries `edges: []`, so treating an empty array as "states nothing" would refuse a valid plan.
    """
    for name in dotted:
        container: Any = document
        walked: list[str] = []
        for part in name.split("."):
            walked.append(part)
            if not isinstance(container, dict) or part not in container:
                assessment.note(
                    slug,
                    f"{what} has no {'.'.join(walked)}, and this tool consumes it, so its absence cannot "
                    "be defaulted",
                )
                container = None
                break
            container = container[part]
        if container is None:
            continue
        if container == "" or container == {}:
            assessment.note(slug, f"{what} records {name} as empty ({container!r}), which states nothing")


# ---- the plan's subject set ----------------------------------------------------------------------


def plan_subjects(assessment: Assessment, plan: dict[str, Any]) -> set[str] | None:
    """Every name the plan can be drifting ABOUT, in the spellings the PlanDiff vocabulary uses.

    Four spellings, and each is the one `wave-plan-compiler.py`'s diff synthesis emits for its kinds:

      * a node id, for the node and authority kinds;
      * `"<from> -> <to>"`, for the edge kinds -- the compiler's own `f"{edge[0]} -> {edge[1]}"`;
      * a declared custody path, worktree or file, for `custody-boundary`;
      * the mission id, for the wave-wide dimensions (approval, budget, gate, terminal criterion, and
        the rest) whose subject is the wave rather than one vertex of it.

    Returns None having noted its reasons when the plan's own shape cannot be read, because a subject
    check against a half-read plan would hard-stop every change for the plan's mistake rather than its own.
    """
    slug = "wave-plan"
    subjects: set[str] = set()
    mission_id = _identifier(assessment, slug, plan, "mission_id", "the wave plan's mission_id")
    if mission_id is not None:
        subjects.add(mission_id)
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        assessment.note(
            slug, f"the wave plan's nodes is not a non-empty JSON array (found {nodes!r}), so it names no node"
        )
        return None
    for index, node in enumerate(nodes):
        where = f"the wave plan's node at position {index}"
        if not isinstance(node, dict):
            assessment.note(slug, f"{where} is not a JSON object (found {node!r})")
            return None
        node_id = _identifier(assessment, slug, node, "node_id", f"{where}'s node_id")
        if node_id is None:
            return None
        subjects.add(node_id)
        worktree = node.get("worktree_custody")
        if isinstance(worktree, str) and worktree:
            subjects.add(worktree)
        files = node.get("file_custody")
        if isinstance(files, list):
            subjects.update(entry for entry in files if isinstance(entry, str) and entry)
    edges = plan.get("edges")
    if not isinstance(edges, list):
        assessment.note(slug, f"the wave plan's edges is not a JSON array (found {edges!r})")
        return None
    for index, edge in enumerate(edges):
        where = f"the wave plan's edge at position {index}"
        if not isinstance(edge, dict) or tuple(sorted(edge)) != ("from", "to"):
            assessment.note(slug, f"{where} is not a JSON object of exactly `from` and `to` (found {edge!r})")
            return None
        origin, target = edge.get("from"), edge.get("to")
        if not isinstance(origin, str) or not origin or not isinstance(target, str) or not target:
            assessment.note(slug, f"{where} does not name two non-empty endpoints (found {origin!r} -> {target!r})")
            return None
        # The compiler's own spelling, character for character: an edge subject a caller copied out of a
        # PlanDiff has to compare equal to the one derived here, or every edge change would hard-stop.
        subjects.add(f"{origin} -> {target}")
    return subjects


# ---- this file's own input schema ----------------------------------------------------------------


def check_observed(assessment: Assessment, document: dict[str, Any]) -> dict[str, Any] | None:
    """The full closed shape of `observed-drift@1`, minus the change entries themselves.

    The ENTRIES are deliberately not validated here. A malformed entry is a hard-stop OUTCOME under
    :79, not a refusal, so validating it in this function -- whose every finding is a reason -- would
    convert the safety rule into a refusal and leave the caller with no sealed document to stop on.
    What IS a refusal here is the envelope: an unreadable `plan_digest`, `observed_at`, or
    `observation_id` means this tool cannot tell WHICH plan or WHEN, and a hard-stop about an unknown
    document is not a classification.
    """
    slug = "observed-drift"
    observation_id = _identifier(assessment, slug, document, "observation_id", "the observation's observation_id")
    observed_at = _instant(assessment, slug, document, "observed_at", "the observation's observed_at")
    plan_digest = _digest_value(assessment, slug, document.get("plan_digest"), "the observation's plan_digest")
    changes = document.get("changes")
    if not isinstance(changes, list):
        assessment.note(
            slug,
            f"the observation's changes is not a JSON array (found {changes!r}); an absent list is not an "
            "empty one, because an empty list is an explicit no-drift statement and this is a malformed "
            "document",
        )
        changes = None
    if observation_id is None or observed_at is None or plan_digest is None or changes is None:
        return None
    return {
        "changes": changes,
        "observation_id": observation_id,
        "observed_at": observed_at,
        "plan_digest": plan_digest,
    }


# ---- the classification --------------------------------------------------------------------------


def classify_entry(entry: Any, subjects: set[str], binding_ground: str | None) -> dict[str, Any]:
    """One observed change to one assessment. This is the whole of the safety rule, in one place.

    The order of the questions is the order of what can be known: an entry that is not three non-empty
    strings cannot have its kind looked up, and a kind outside the sixteen cannot have a row. Each
    unanswerable question adds its ground and forces `hard-stop`; only an entry that answered all of them
    reaches `TABLE`, and the row is then the whole outcome.

    `binding_ground`, when present, is the document-level ambiguity every entry inherits: if which plan
    was observed is unknown, no per-change grounding holds, so the row is not consulted at all.
    """
    grounds: list[str] = []
    kind = entry.get("kind") if isinstance(entry, dict) else None
    subject = entry.get("subject") if isinstance(entry, dict) else None
    observation = entry.get("observation") if isinstance(entry, dict) else None
    # Only a non-empty string survives into the sealed assessment; anything else becomes null, which is
    # how the document says "this entry did not state one" without inventing a value for it.
    kind = kind if isinstance(kind, str) and kind else None
    subject = subject if isinstance(subject, str) and subject else None
    observation = observation if isinstance(observation, str) and observation else None
    stated = kind is not None and subject is not None and observation is not None
    if not isinstance(entry, dict) or tuple(sorted(entry)) != OBSERVED_CHANGE_KEYS or not stated:
        grounds.append(
            f"this entry is not a JSON object of exactly {list(OBSERVED_CHANGE_KEYS)}, each a non-empty "
            f"string (found {entry!r}), so what it observed cannot be read; {AMBIGUOUS}"
        )
    elif kind not in CHANGE_KINDS:
        grounds.append(
            f"the change kind {kind!r} is outside the closed sixteen {list(CHANGE_KINDS)}, so no row of "
            f"the taxonomy table covers it; {AMBIGUOUS}"
        )
    elif subject not in subjects:
        grounds.append(
            f"the bound plan names no {subject!r}: not as a node, not as an edge, not as a declared "
            f"custody path, and not as its mission, so which invariant this change is about is unknown; "
            f"{AMBIGUOUS}"
        )
    if binding_ground is not None:
        grounds.append(binding_ground)
    if grounds:
        outcome = HARD_STOP
    else:
        outcome, ground = TABLE[str(kind)]
        grounds.append(ground)
    return {"grounds": grounds, "kind": kind, "observation": observation, "outcome": outcome, "subject": subject}


def fold_severity(assessments: list[dict[str, Any]]) -> str | None:
    """The overall outcome: the MAXIMUM severity among the assessments, or None for an empty list.

    `SEVERITY` is the only order consulted, and it is the semantic one, not the alphabetical one. The
    empty case returns None rather than the lowest outcome, because the lowest outcome is a claim about a
    change and there is no change: `no_drift_reason` carries that statement instead.
    """
    if not assessments:
        return None
    return max((entry["outcome"] for entry in assessments), key=lambda outcome: SEVERITY[outcome])


def synthesize_classification(
    *,
    at: str,
    plan_digest: str,
    plan_revision: int,
    mission_id: str,
    observed: dict[str, Any],
    subjects: set[str],
) -> dict[str, Any]:
    """The sealed classification, bound to the exact plan digest it was derived against.

    `overall_outcome` and `no_drift_reason` are DERIVED here rather than passed in, so the one place that
    writes both cannot seal them disagreeing. An unbound observation is `hard-stop` even with an empty
    change list: zero observations about an unknown plan is not "no drift", it is "no idea".
    """
    bound = observed["plan_digest"] == plan_digest
    binding_ground = None
    if not bound:
        binding_ground = (
            f"the observation says it watched the plan whose digest is {observed['plan_digest']}, and this "
            f"classification's plan is {plan_digest}; which plan these sentences are about is unknown, and "
            f"neither document can be trusted to describe the other; {AMBIGUOUS}"
        )
    assessments = [classify_entry(entry, subjects, binding_ground) for entry in observed["changes"]]
    overall = fold_severity(assessments)
    no_drift_reason = None
    if overall is None:
        if bound:
            no_drift_reason = NO_DRIFT
        else:
            overall = HARD_STOP
    body = {
        "schema": CLASSIFICATION_SCHEMA,
        "assessments": assessments,
        "binding": {"bound": bound, "ground": binding_ground, "observed_plan_digest": observed["plan_digest"]},
        "classified_at": at,
        "mission_id": mission_id,
        "no_drift_reason": no_drift_reason,
        "observation_id": observed["observation_id"],
        "observed_at": observed["observed_at"],
        "overall_outcome": overall,
        "plan_digest": plan_digest,
        "plan_revision": plan_revision,
    }
    # The plan's mission and revision are carried; the plan itself is NOT, because a classification
    # embedding a whole plan would be a second copy of the document its digest already names.
    sealed = dict(body)
    sealed[DIGEST_KEY] = document_digest(body)
    return sealed


# ---- verify: re-derive one sealed classification from its own content -----------------------------


def check_classification(assessment: Assessment, document: dict[str, Any]) -> None:
    """Every field of a sealed `drift-classification@1`, then the cross-checks the fold implies.

    The cross-checks are the whole reason `verify` exists as more than a digest re-derivation: a digest
    proves the bytes were not edited, and these prove the bytes were DERIVED. Each is stated in both
    directions, so neither half can be sealed silently disagreeing with the other:

      1. `overall_outcome` is the maximum severity among the assessments, recomputed here from the same
         `SEVERITY` order rather than trusted;
      2. `no_drift_reason` is a sentence exactly when the assessments are empty AND the binding holds,
         and `overall_outcome` is null exactly when `no_drift_reason` is a sentence;
      3. an unbound observation is `hard-stop` in EVERY assessment and in `overall_outcome`, regardless
         of how many assessments were observed -- not only when the list happens to be empty -- and an
         assessment that did not state its kind, subject, or observation is `hard-stop`, because those
         are the safety rule's own outputs;
      4. `bound` is exactly the equality of the binding's `observed_plan_digest` and this document's own
         `plan_digest`, recomputed here rather than trusted, because that equality is the one fact
         `synthesize_classification` derives it from;
      5. an assessment's `outcome` cannot sit below the content-derivable lower bound its own `kind`
         implies: a kind outside the closed sixteen must be `hard-stop`, and a kind inside it must be at
         least as severe as `TABLE[kind][0]`, because ambiguity can only raise the severity the table
         assigns, never lower it.
    """
    slug = "drift-classification"
    found = tuple(sorted(document))
    if found != CLASSIFICATION_SEALED_KEYS:
        missing = [name for name in CLASSIFICATION_SEALED_KEYS if name not in document]
        extra = [name for name in found if name not in CLASSIFICATION_SEALED_KEYS]
        assessment.note(
            slug,
            f"the classification is not the closed sealed key set {list(CLASSIFICATION_SEALED_KEYS)}: "
            f"missing {missing}, unexpected {extra}",
        )
        return
    if document.get("schema") != CLASSIFICATION_SCHEMA:
        assessment.note(
            slug,
            f"the classification declares schema {document.get('schema')!r} rather than "
            f"{CLASSIFICATION_SCHEMA!r}",
        )
    _identifier(assessment, slug, document, "mission_id", "the classification's mission_id")
    _identifier(assessment, slug, document, "observation_id", "the classification's observation_id")
    _instant(assessment, slug, document, "classified_at", "the classification's classified_at")
    _instant(assessment, slug, document, "observed_at", "the classification's observed_at")
    plan_digest = _digest_value(assessment, slug, document.get("plan_digest"), "the classification's plan_digest")
    _positive_integer(assessment, slug, document, "plan_revision", "the classification's plan_revision")

    binding = _closed_object(assessment, slug, document, "binding", BINDING_KEYS, "the classification's binding")
    bound: bool | None = None
    if binding is not None:
        bound = binding.get("bound")
        if not isinstance(bound, bool):
            assessment.note(slug, f"the binding's bound is not a JSON boolean (found {bound!r})")
            bound = None
        observed_plan_digest = _digest_value(
            assessment, slug, binding.get("observed_plan_digest"), "the binding's observed_plan_digest"
        )
        ground = binding.get("ground")
        if bound is True and ground is not None:
            assessment.note(
                slug,
                f"the binding holds and still carries the ground {ground!r}; a ground here is the record of "
                "an ambiguity, so a bound observation has none",
            )
        if bound is False and (not isinstance(ground, str) or not ground):
            assessment.note(
                slug,
                f"the binding does not hold and names no ground (found {ground!r}); an unbound observation "
                "must record why the plan it watched is unknown",
            )
        # `bound` is not a separate opinion: `synthesize_classification` derives it from exactly this
        # equality (line ~833), so a sealed document where the two disagree is a hand-edited one, not a
        # possible output of that derivation.
        if bound is not None and observed_plan_digest is not None and plan_digest is not None:
            digests_equal = observed_plan_digest == plan_digest
            if digests_equal != bound:
                assessment.note(
                    slug,
                    f"the binding's observed_plan_digest {observed_plan_digest} and the classification's "
                    f"plan_digest {plan_digest} are {'equal' if digests_equal else 'not equal'}, but bound "
                    f"is recorded as {bound!r}; bound is exactly that digest equality, not a separate claim",
                )

    assessments = document.get("assessments")
    if not isinstance(assessments, list):
        assessment.note(slug, f"the classification's assessments is not a JSON array (found {assessments!r})")
        return
    outcomes: list[str] = []
    for index, entry in enumerate(assessments):
        where = f"the classification's assessment at position {index}"
        if not isinstance(entry, dict) or tuple(sorted(entry)) != ASSESSMENT_KEYS:
            assessment.note(slug, f"{where} is not a JSON object of exactly {list(ASSESSMENT_KEYS)} (found {entry!r})")
            return
        outcome = _member(assessment, slug, entry, "outcome", OUTCOMES, f"{where}'s outcome")
        grounds = entry.get("grounds")
        if not isinstance(grounds, list) or not grounds or any(not isinstance(one, str) or not one for one in grounds):
            assessment.note(
                slug,
                f"{where}'s grounds is not a non-empty array of non-empty strings (found {grounds!r}); an "
                "outcome with no ground is an assertion rather than a classification",
            )
        stated = []
        for key in ("kind", "observation", "subject"):
            value = entry.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                assessment.note(slug, f"{where}'s {key} is neither a non-empty string nor null (found {value!r})")
            stated.append(value is not None)
        if not all(stated) and outcome is not None and outcome != HARD_STOP:
            assessment.note(
                slug,
                f"{where} did not state its kind, subject, or observation and is classified {outcome!r}; an "
                f"entry this tool could not read is the safety rule's own case, and {AMBIGUOUS}",
            )
        # The content-derivable lower bound: `classify_entry` can only ever emit `TABLE[kind][0]` or
        # escalate it to hard-stop for an ambiguity -- it never emits anything LESS severe than the row --
        # so this outcome is checked against that same floor without needing the plan this document does
        # not carry.
        kind = entry.get("kind")
        if outcome is not None and isinstance(kind, str):
            if kind not in CHANGE_KINDS and outcome != HARD_STOP:
                assessment.note(
                    slug,
                    f"{where}'s kind {kind!r} is outside the closed sixteen {list(CHANGE_KINDS)} and its "
                    f"outcome is recorded as {outcome!r} rather than {HARD_STOP!r}; no row of the taxonomy "
                    f"table covers it, and {AMBIGUOUS}",
                )
            elif kind in CHANGE_KINDS:
                floor = TABLE[kind][0]
                if SEVERITY[outcome] < SEVERITY[floor]:
                    assessment.note(
                        slug,
                        f"{where}'s kind {kind!r} has a table outcome of {floor!r} and its recorded outcome "
                        f"is {outcome!r}, a lower severity; ambiguity can only raise the severity the table "
                        "assigns a kind, never lower it",
                    )
        if outcome is None:
            return
        outcomes.append(outcome)

    overall = document.get("overall_outcome")
    reason = document.get("no_drift_reason")
    expected = fold_severity([{"outcome": one} for one in outcomes])
    if outcomes:
        if overall != expected:
            assessment.note(
                slug,
                f"the classification records overall_outcome {overall!r} while the maximum severity among "
                f"its own assessments is {expected!r}; the overall outcome is a fold over the assessments, "
                "not a separate opinion about them",
            )
        if reason is not None:
            assessment.note(
                slug,
                f"the classification names {len(outcomes)} assessment(s) and still carries the "
                f"no_drift_reason {reason!r}; that sentence states that nothing was observed",
            )
    elif bound is True:
        if overall is not None:
            assessment.note(
                slug,
                f"the classification names no assessment and records overall_outcome {overall!r}; an outcome "
                "is a statement about a change, and an empty observation has none to make it about",
            )
        if reason != NO_DRIFT:
            assessment.note(
                slug,
                f"the classification names no assessment and its no_drift_reason is {reason!r} rather than "
                "this tool's one fixed sentence; an empty observation that does not say so is "
                "indistinguishable from a classification that was never derived",
            )
    # NOT an `elif`: this rule holds for an unbound observation regardless of how many assessments it
    # carries, so it must run whether or not the `if outcomes:` branch above also ran. Confining it to the
    # empty-list branch left every non-empty case unchecked, which is exactly the gap issue 16:79 forbids.
    if bound is False:
        if not outcomes:
            if reason is not None:
                assessment.note(
                    slug,
                    f"the classification's binding does not hold and it still carries the no_drift_reason "
                    f"{reason!r}; there is no plan to state no-drift about",
                )
            if overall != HARD_STOP:
                assessment.note(
                    slug,
                    f"the classification observed nothing against a plan it cannot identify and records "
                    f"overall_outcome {overall!r}; zero observations about an unknown plan is not no-drift, "
                    f"and {AMBIGUOUS}",
                )
        elif any(one != HARD_STOP for one in outcomes) or overall != HARD_STOP:
            assessment.note(
                slug,
                f"the classification's binding does not hold and records outcomes {outcomes!r} with "
                f"overall_outcome {overall!r}; an unbound observation is hard-stop in every assessment and "
                f"overall regardless of how many were observed, and {AMBIGUOUS}",
            )


def check_digest(assessment: Assessment, document: dict[str, Any], expect: str | None) -> str | None:
    """The recorded digest re-derives from the content, and optionally IS the one a caller expected."""
    slug = "digest"
    recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the classification's recorded digest")
    if recorded is None:
        return None
    derived = document_digest(document)
    if recorded != derived:
        assessment.note(
            slug,
            f"the classification records digest {recorded} which its own content does not re-derive "
            f"({derived}): it has been edited since it was sealed, or the digest was written by something "
            "other than this family's derivation",
        )
        return None
    if expect is not None and expect != recorded:
        assessment.note(
            slug,
            f"the classification's digest is {recorded} and --expect-digest named {expect}; this is not the "
            "document that digest names",
        )
        return None
    return recorded


# ---- input admission -----------------------------------------------------------------------------


def check_output_path(assessment: Assessment, option: str, out: str | None) -> Path | None:
    """`--out` may not exist and needs a real parent directory to land in.

    `O_EXCL` at write time is the enforcement; this check exists so a caller learns about an occupied
    destination BEFORE anything is derived, and a racer that created the path in between is refused
    there rather than clobbered here.
    """
    if out is None:
        return None
    target = Path(os.path.abspath(out))
    try:
        target.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        assessment.note("output-path", f"the {option} path {target} cannot be inspected: {exc}")
        return None
    else:
        assessment.note(
            "output-path",
            f"the {option} path {target} already exists; this command overwrites nothing, so an occupied "
            "destination is refused rather than replaced",
        )
        return None
    if not target.parent.is_dir():
        assessment.note(
            "output-path",
            f"the {option} path {target} has no existing directory to be written into, so the sealed "
            "classification would have nowhere to land",
        )
        return None
    return target


def admit_inputs(args: argparse.Namespace, assessment: Assessment) -> dict[str, Any]:
    """Read and admit both documents. Unusable files raise `InputError` out of here (exit 2)."""
    plan = load_document(args.plan, "wave plan")
    plan_digest = _sealed_input(assessment, "wave-plan", plan, PLAN_SCHEMA, None, "the wave plan")
    _required_fields(assessment, "wave-plan", plan, PLAN_REQUIRED, "the wave plan")
    revision = _positive_integer(assessment, "wave-plan", plan, "revision", "the wave plan's revision")
    subjects = plan_subjects(assessment, plan) if plan_digest is not None else None

    document = load_document(args.observed, "observed drift")
    observed_digest = _sealed_input(
        assessment, "observed-drift", document, OBSERVED_SCHEMA, OBSERVED_SEALED_KEYS, "the observation"
    )
    observed = check_observed(assessment, document) if observed_digest is not None else None
    return {
        "digests": {"observed_digest": observed_digest, "plan_digest": plan_digest},
        "mission_id": plan.get("mission_id"),
        "observed": observed,
        "out": check_output_path(assessment, "--out", args.out),
        "plan_digest": plan_digest,
        "revision": revision,
        "subjects": subjects,
    }


# ---- the one result document ---------------------------------------------------------------------


def derive_command(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None]:
    """Classify one observation (`classify`) or re-derive one sealed classification (`verify`).

    Returns the one result document together with the destination it is to be written to, which is kept
    OUT of the result until the write has actually happened, so a null `out` always means no file of
    this run's making exists.

    A freshly derived classification is READ BACK through the same `check_classification` and
    `check_digest` that `verify` runs. A synthesis bug then becomes a refusal rather than a sealed
    document `verify` would later reject, which matters because a downstream consumer binds this digest.
    """
    command = args.command
    classification: dict[str, Any] | None = None
    candidate: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    digest: str | None = None
    admitted: dict[str, Any] = {}
    no_drift = False
    if command == "classify":
        assessment = Assessment(CLASSIFY_CHECKS)
        admitted = admit_inputs(args, assessment)
        observed, subjects = admitted["observed"], admitted["subjects"]
        mission_id, revision = admitted["mission_id"], admitted["revision"]
        ready = not any(assessment.groups[slug] for slug in INPUT_SLUGS)
        if ready and observed is not None and subjects is not None and revision is not None:
            candidate = synthesize_classification(
                at=args.at,
                plan_digest=str(admitted["plan_digest"]),
                plan_revision=revision,
                mission_id=str(mission_id),
                observed=observed,
                subjects=subjects,
            )
            check_classification(assessment, candidate)
            check_digest(assessment, candidate, None)
            no_drift = candidate["no_drift_reason"] is not None
    else:
        assessment = Assessment(VERIFY_CHECKS)
        document = load_document(args.classification, "drift classification")
        check_classification(assessment, document)
        digest = check_digest(assessment, document, args.expect_digest)

    verdict = assessment.verdict(command, no_drift=no_drift)
    if verdict == VERDICT_VERIFIED and document is not None:
        # Republished ONLY for an admitted document, and from the ALREADY LOADED bytes: a refusal
        # publishes none of it, so no consumer can read a partially admitted classification out of one.
        classification = document
    elif verdict in (VERDICT_CLASSIFIED, VERDICT_NO_DRIFT) and candidate is not None:
        classification, digest = candidate, candidate[DIGEST_KEY]
    inputs_admitted: bool | None = None
    if command == "classify":
        inputs_admitted = not any(assessment.groups[slug] for slug in INPUT_SLUGS)
    result = {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "inputs_admitted": inputs_admitted,
        "inputs": admitted.get("digests") if inputs_admitted else None,
        "classification": classification,
        "classification_digest": digest,
        # READ OUT of the sealed document rather than recomputed: it is the one value a caller acts on,
        # so it is projected to the top level, and projecting it twice from two derivations is how the
        # two could disagree.
        "overall_outcome": None if classification is None else classification["overall_outcome"],
        "out": None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }
    target = admitted.get("out") if classification is not None and command == "classify" else None
    return result, target


# ---- delivery ------------------------------------------------------------------------------------


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Catching the failed write is not enough: the bytes stay PENDING in the stream's buffer and CPython
    flushes `sys.stdout`/`sys.stderr` once more while finalizing; that second failure replaces the
    process exit code with 120, which is outside this module's closed exit set. The identity check is
    load-bearing because `main` is importable: only the stream that actually failed may be dropped.
    """
    if getattr(sys, name, None) is stream:
        setattr(sys, name, None)


def guarded_sink(name: str, stream: object) -> Callable[[str], None]:
    """Wrap one already-settled display stream so a failed write costs the channel, never the code."""
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
    advisory_stderr()(f"drift-classifier.py: {message}\n")


#: The three outcomes of one exclusive write. Kept apart because they have different consequences: a
#: file that was never created leaves nothing behind, while one created and then not finished is a path
#: a consumer must be told about by name.
WRITE_DONE = "written"
WRITE_NOTHING = "nothing-created"
WRITE_PARTIAL = "created-but-incomplete"


def write_document(target: Path, document: dict[str, Any]) -> str:
    """Write the sealed classification to a fresh path, or say exactly what was left behind."""
    payload = canonical_bytes(document)
    try:
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as exc:
        report_input_error(
            f"cannot create the --out path {target}: {exc}; the classification was derived and nothing was "
            "written, so no existing file was touched"
        )
        return WRITE_NOTHING
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        report_input_error(
            f"cannot write the --out path {target}: {exc}; that path now exists and may be incomplete, so "
            "treat it as unusable evidence rather than as this run's document"
        )
        return WRITE_PARTIAL
    return WRITE_DONE


def deliver_document(result: dict[str, Any], target: Path | None) -> int:
    """Write the sealed classification when a destination was given, and classify any failure.

    Both failures are exit 1 rather than 4: the classification WAS derived and is published in the
    result document either way, so what went wrong is delivery of a copy, not an admitted partial effect
    on anything a consumer already had. The `created-but-incomplete` path is named on stderr by
    `write_document`, because a file outliving a nonzero exit is the one thing a caller could be
    surprised by.
    """
    if target is None or result.get("classification") is None:
        return EXIT_OK
    state = write_document(target, result["classification"])
    if state == WRITE_DONE:
        result["out"] = str(target)
        return EXIT_OK
    return EXIT_INTERNAL


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence, so a stdout that cannot receive it is not a
    lost convenience -- the question was answered and the answer did not arrive. `canonical_bytes` is
    `ensure_ascii=True`, so the payload is ASCII and a text stream with no `.buffer` -- what an importing
    caller's `redirect_stdout(StringIO())` installs -- receives byte-identical characters.
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
            "this process was handed no stdout to write its one result document to, so the derived result "
            "could not be delivered"
        )
        return EXIT_INTERNAL
    try:
        emit_to(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        # Abandoned BEFORE returning: the classification below is worthless if the interpreter's shutdown
        # flush of the same broken stream replaces this exit code with 120.
        abandon_broken_stream("stdout", stream)
        report_input_error(
            f"cannot write the result document to stdout: {exc}; an unknown prefix of it may already have "
            "reached the consumer, so the result was derived but not delivered"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules.

    `error` writes usage through `print_usage`, which FALLS BACK TO STDOUT when `sys.stderr is None`:
    under `2>&-` a grammar error would keep exit 2 while putting usage bytes where this module's one
    result document lives. And argparse swallows a failed write while leaving its bytes pending, which is
    enough for the shutdown flush to replace the usage error's 2 with 120.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            # argparse resolved `sys.stderr`/`sys.stdout` itself and got None: this process was handed no
            # such stream, so the line is dropped rather than redirected onto the other.
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
    "Exit codes: 0 a result was derived, a named refusal included; 2 a supplied file cannot be read as one "
    "JSON object, or the arguments themselves are unusable; 1 a derived result that could not be "
    "delivered, because an answer that did not arrive is not a success. Implementation Decision 9's 3 does "
    "not apply -- a refusal happens before anything is written -- and 4 is unreachable, because the single "
    "--out write is O_EXCL and the classification is published in the result document either way."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="drift-classifier.py",
        description=(
            "Classify observed drift against one sealed WavePlan into issue 16's four closed outcomes -- "
            "compatible, revalidation-required, replan-required, hard-stop -- by a table over the sixteen "
            "PlanDiff change kinds, folded to the maximum severity observed. Anything ambiguous is "
            "hard-stop; an empty observation is an explicit no-drift verdict. Read-only, offline, "
            "clock-free, and subprocess-free: it observes nothing, repairs nothing, and authorizes nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    classify = commands.add_parser(
        "classify",
        description=(
            "Admit a SEALED wave-plan@1 and a SEALED observed-drift@1, classify every observed change "
            "against the taxonomy table, and seal one drift-classification@1 whose overall outcome is the "
            "maximum severity among them. An unknown kind, a subject the plan does not name, a plan-digest "
            "mismatch, and an unreadable entry are each hard-stop rather than a refusal, because a caller "
            "at a boundary needs a document to stop on."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED drift-classification@1 from its own content: its closed key set, every "
            "field, the severity fold, the no-drift and binding cross-checks, and its one digest. This "
            "observes nothing, so whether its observations are still current is a fresh observation's "
            "question."
        ),
        epilog=EPILOG,
    )
    classify.add_argument("--plan", required=True, help=f"the SEALED {PLAN_SCHEMA} revision drift is measured against")
    classify.add_argument("--observed", required=True, help=f"the SEALED {OBSERVED_SCHEMA} document to classify")
    classify.add_argument(
        "--at", required=True, help="the YYYY-MM-DDTHH:MM:SSZ instant of this classification; this tool reads no clock"
    )
    classify.add_argument(
        "--out",
        default=None,
        help=(
            "where the sealed classification is additionally written, O_EXCL and fsynced: it must not "
            "exist; a refusal writes nothing, and the document is published in the result either way"
        ),
    )
    verify.add_argument("--classification", required=True, help=f"the SEALED {CLASSIFICATION_SCHEMA} document")
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the document's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no document could "
            "ever match it"
        )
        return EXIT_INPUT
    at = getattr(args, "at", None)
    if at is not None and not _TIME.match(at):
        # The instant is an ARGUMENT, so a malformed one means the question could not be asked. This tool
        # reads no clock, so there is nothing to fall back to. Read by ATTRIBUTE rather than by command
        # name, so a later command taking an instant inherits the guard instead of skipping it.
        report_input_error(
            f"--at {args.at!r} is not a YYYY-MM-DDTHH:MM:SSZ instant, so no classification could state when "
            "it was derived"
        )
        return EXIT_INPUT
    try:
        result, target = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    code = deliver_document(result, target)
    result["exit_code"] = code
    delivered = emit_result(result)
    # A result document that did not arrive outranks a file that did: the exit code has to be the worst
    # thing that happened, and a consumer reading no result at all learns nothing from a 0.
    return code if delivered == EXIT_OK else delivered


if __name__ == "__main__":
    raise SystemExit(main())
