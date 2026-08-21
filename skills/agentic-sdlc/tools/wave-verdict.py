#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Derive the ONE terminal wave state from the wave's emitted artifacts.

Issue 07's "Completion and adversarial review" section and the product spec's Implementation
Decision 61 are together this module's whole contract. A wave is complete only when EIGHT conditions
hold together, and a normal delivery wave additionally requires the authoritative repository gate to
pass. Decision 61 closes the outcome at SIX values, and this module derives exactly one of them:

    accepted               every completion condition is met and the authoritative repository gate
                           passes; the wave is complete
    remediation-progress   the focused gates pass and the exact global failure baseline did not
                           worsen; this verdict NEVER claims the repository gate passes and never
                           claims the repository is write-ready
    blocked                anything else the completion evidence shows, always with named reasons
    aborted                a conductor record says the execution was stopped before it completed
    failed                 a conductor record says the execution ran and ended failed
    unknown-effect         a conductor record says the execution ended leaving an effect of unknown
                           extent; recovery follows it, and no other evidence talks it down

THE FIRST THREE ARE WHAT THE EVIDENCE SHOWS; THE LAST THREE ARE HOW THE EXECUTION ENDED. Issue 07
describes only the first three -- completion, `remediation-progress`, and not complete -- because
they are what completion evidence shows: the eight conditions and the gate. It names none of the
other three. Decision 61's other three describe how the execution ENDED, which no artifact but the
conductor's own record carries -- the conductor is the party that watched it end, and
`wave-journal.py`'s per-node dispositions describe node endings rather than the wave's. So
`wave-verdict-conductor-record@1` carries `ended_state`, `ended_reasons`, and `last_proven_stage`
(sealed by `skills/agentic-sdlc/tools/wave-submission.py`), and this module reads them. The
precedence, exactly:

  1. `unknown-effect` DOMINATES: if any record says the execution ended with an effect of unknown
     extent, that is the state whatever every other record and every other artifact says. An unknown
     effect can never be talked down -- neither by a peer record saying the execution merely failed,
     nor by a later one saying it completed, which is precisely the laundering Decision 61's "process
     completion and publication cannot manufacture success" forbids.
  2. TWO DIFFERENT other endings REFUSE rather than pick. `failed` and `aborted` are peers: one says
     the execution ran and failed, the other that it was stopped before it could. Nothing here can
     rank them, so a wave whose records say both is `blocked` with the disagreement named.
  3. ONE other ending OVERRIDES the completion evidence. A wave whose evidence set is complete and
     whose authoritative gate passed is still `failed` if a conductor recorded that it ended failed:
     the eight conditions describe what was proven, never that the execution reached its end.
  4. `completed` overrides NOTHING and adds no reason, so a completed execution derives exactly what
     this module derived before Decision 61's other three existed.
  5. For an ended state other than `completed`, the top-level `repository_gate_passes` is null rather
     than the receipt's fact: an execution that did not reach its end never proved the receipt's
     snapshot is this wave's result. The raw outcome stays in `gate`.

An absent `ended_state` is a NAMED REASON -- how the execution ended is unrecorded -- and never an
assumed `completed`, which keeps every record written before those fields existed parseable rather
than silently successful. Contradictory ended facts are malformed input (exit 2), like any other
document that is not what it claims: `completed` beside an ending reason or a last proven stage, a
non-`completed` state with neither, an `ended_state` outside the four tokens, and ended facts carried
without the state they belong to. `--conductor-record` REPEATS, because a wave that crashed and was
resumed has two accounts and argparse keeping only the last would let the later erase the earlier.

THE CONDUCTOR OWNS CLASSIFICATION. Issue 07 says "the critic advises; the conductor owns
classification and verdict", so the critic's findings are an INPUT here and this module classifies
them: an acceptance-criteria violation, safety regression, corrupted evidence, or failed
authoritative gate blocks completion, while complexity, maintainability, documentation, and
enhancement findings become Seeds. A wave may complete carrying Seeds and never with an unresolved
blocking finding. The seed-worthy set is published so the conductor can queue it; nothing here
writes to a queue.

WHY ARTIFACTS AND NOT IMPORTS. The producers are standalone scripts loaded by absolute path, two of
them with hyphens in their names that cannot be imported at all. So this reads what they PRINT, and
re-expresses the three seams it needs -- the family's canonical form, `gate_receipt`'s newline-free
variant of it, and the guarded-stream rule -- rather than importing them. The two end-to-end journey
tests drive the real producers over their real command lines, so a drifted canonical form surfaces as
a `journal_digest` that will not re-derive and a `self_digest` that will not verify, never as a
silent pass.

THE EIGHT CONDITIONS, and where each is DERIVED from. None of them is read off a summary field; the
journal's projection deliberately publishes no `complete` or `accepted` field, and the two summary
fields the operands do publish (`required_nodes_without_disposition` and `blocks_wave_completion`)
are RE-DERIVED here and refused as malformed input when they disagree with the facts beside them.

    1  required-node-dispositions  every required node has an admitted success, approved skip, or
       explicit blocked disposition. Issue 07 admits `blocked` AS a disposition, so condition 1 is
       disposition COMPLETENESS; a required node that is explicitly blocked satisfies it and is
       still a named reason, because a wave may not complete carrying an unresolved blocking
       disposition.
    2  no-unexplained-substitution  every node that spawned carries a
       `runtime-substitution-classification@1` whose verdict is not `unexplained-substitution`. A
       node with no classification at all is uncovered, not clean.
    3  declared-artifacts-validate  every artifact the manifest declares exists inside the target as
       a regular file and re-derives its recorded sha256, and every output an admitted-success node
       declared is covered by the manifest.
    4  workstream-reviews-accepted  every admitted-success implementer node carries an `accepted`
       review submitted by a DIFFERENT node whose role is reviewer and whose entry follows the work
       it reviewed.
    5  fan-in-authorized  the journal carries the named fan-in approval, its scope names the
       integrator node, and the integrator's entry FOLLOWS that approval.
    6  gate-contract-passes  the authoritative gate receipt passes on the integrated snapshot; or,
       for a remediation wave, every focused gate passes on the same snapshot under the same pinned
       toolchain and the baseline comparison reports exact non-worsening.
    7  budgets-retries-revisions-approvals-traceable  budgets are recorded and any overrun states
       its reason, every retry names a node that reached a disposition, the plan-revision chain
       leads back to the approved plan digest, and every approval a record names is in the journal.
    8  conductor-records-verdict  the conductor's own record names this wave, anchors the exact
       journal state it read, names where the verdict is recorded, and is stamped at or after the
       journal's last entry.

THE `journal_digest` DECISION, stated because an unstated one is worse than either answer.
`wave-journal.py`'s `read_journal` docstring names `journal_digest` as the remedy for the one thing
its chain cannot catch: a rewritten LAST line or a truncated tail, both of which leave a
self-consistent chain. Nothing consumed it as an external head anchor until this module. It binds it
in two distinct ways:

  * RE-DERIVED from the projection's own `entries`. `read_journal` proved every line is exactly the
    canonical form of what it parses to, so re-canonicalising the entries reproduces the file's bytes
    exactly; their digest must equal the published `journal_digest`, and the chain of `prev_digest`
    values must re-derive. A projection whose entries and digest disagree is malformed input.
  * COMPARED against the conductor's independently retained anchor. Condition 8's conductor record
    must carry the `journal_digest` the conductor kept from the last `init`/`record-*` result, which
    is the only value that comes from OUTSIDE the file. That comparison is what closes the truncated
    tail: a projection of a journal missing its last three entries re-derives perfectly and still
    fails to match the anchor the conductor holds. Requiring the anchor from the projection itself
    would have been self-referential and would have proved nothing.

FAIL CLOSED, AND NAME THE REASON. Every predicate accumulates named reasons against its own
condition; then ONE selection runs over ONE partition, so no input can yield two states or none.
Ambiguity is `blocked` rather than guessed -- an unrecognised critic finding kind, an unrecognised
review verdict, and a non-boolean `non_worsening` are each a named reason rather than an assumed
pass. An absent artifact is a named reason rather than a usage error, so this may be run at any point
in a wave and will say exactly which evidence is still missing. Deriving `blocked` is this module
SUCCEEDING, which is why it exits 0.

NO CLOCK. Every instant is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would refuse
honest input at random. Timestamps are the journal's fixed-width `YYYY-MM-DDTHH:MM:SSZ` form, whose
lexicographic order is chronological, and they are compared as strings.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. This module's exit space is 0, 2, and 1 only. 3 and 4 are both absent for
the same structural reason: **a tool that can cause no effect can neither refuse before one nor admit
one.** Nothing here opens a file for writing, spawns a process, touches the network, or mutates
state; it reads the paths it is given and prints one document. So a derived `blocked` is a result (0)
and not a clean refusal (3), and 4 is unreachable rather than merely unused. 1 additionally covers a
stdout that cannot receive the one result document, because a verdict derived and not delivered is
not a success.

RESIDUALS, STATED EXACTLY.

  * Every digest check here is RE-DERIVATION, not a security boundary. A same-OS-user forger can
    write a self-consistent projection, receipt, manifest, or conductor record; what these checks
    catch is drift, truncation, a hand-edit, and a mismatched pair of artifacts.
  * Condition 3 proves the declared artifacts match their RECORDED digests in the target tree as it
    is when this runs. It does not prove the tree is an integrated Git snapshot, because this module
    runs no subprocess: no commit, branch, or merge-base is verified. A declared path whose final
    component is a symlink is refused, but a symlinked PARENT directory is followed, so an artifact
    can be read from outside the target through one.
  * Node `outputs` are therefore read as repository-relative FILE paths. An output that is not a file
    -- a branch name, a queue seed, a conversation turn -- cannot be validated this way and belongs
    in the node's `evidence`, which this module reads as opaque strings.
  * Condition 5 requires a fan-in to have HAPPENED: a wave with no integrator node, or one whose
    integrator was skipped, cannot reach a ready state here. That is a deliberate fail-closed reading
    of "fan-in was authorized" -- the alternative would satisfy the condition vacuously, which is the
    failure mode `scripts/gate_baseline.py` exists to refuse.
  * Reviews, the artifact manifest, the critic findings, and the conductor record are same-user
    assertions. `skills/agentic-sdlc/tools/wave-submission.py` now SEALS all four -- it closes each
    key set, refuses every shape this module would block on, and adds one `digest` -- and sealing
    changes none of that: a same-user producer signs nothing, so the four stay VALIDATED,
    cross-checked against the journal's roles and sequence, and never trusted. Nothing here reads the
    seal; a hand-authored document is accepted exactly as before. A recorded approval is likewise
    stamped `authenticated: false` by the journal itself.
  * Freshness is underivable from these artifacts. A stale but internally consistent set -- a
    projection, manifest, and passing receipt from an earlier tree -- derives `accepted` by
    construction.
  * An ended state is the CONDUCTOR'S OWN ACCOUNT, and this module reads records rather than
    executions. An execution that ended with an unknown effect and was recorded as `completed`, or
    was never recorded at all, derives from completion evidence alone; nothing here can observe an
    ending nobody wrote down, and the ended facts are the same-user assertions everything else in
    that record is.
  * `docs/plans/claude-code-first-harness/issues/07-define-dynamic-workflow-graph-contract.md`
    contains neither `aborted` nor `unknown-effect`: its "Completion and adversarial review" section
    still describes only completion, `remediation-progress`, and not complete, while Implementation
    Decision 61 closes the SIX this module now derives. The separation above -- three read off
    completion evidence, three read off how the execution ended -- is the reconciliation, and that
    issue's own prose has not been rewritten to state it.
  * The result document still carries `agentic-sdlc/wave-terminal-verdict@1`. Its closed key set did
    not change: the three new states are new tokens in the `state` field's vocabulary, which
    Decision 61 always closed at six, and the ended facts are published inside the existing
    `evidence` object. A consumer that hard-codes three states was already narrower than the
    decision it implements.

A derived state is evidence about artifacts. It authorizes no push, publication, PR mutation, merge,
or deployment, and `accepted` is a statement about one wave's completion evidence, not a grant.
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

RESULT_SCHEMA = "agentic-sdlc/wave-terminal-verdict@1"

STATE_ACCEPTED = "accepted"
STATE_REMEDIATION_PROGRESS = "remediation-progress"
STATE_BLOCKED = "blocked"
STATE_ABORTED = "aborted"
STATE_FAILED = "failed"
STATE_UNKNOWN_EFFECT = "unknown-effect"

#: Implementation Decision 61's other half: how the execution ENDED, closed at the four tokens
#: `wave-submission.py` seals into a conductor record.
ENDED_COMPLETED = "completed"
ENDED_ABORTED = "aborted"
ENDED_FAILED = "failed"
ENDED_UNKNOWN_EFFECT = "unknown-effect"
ENDED_STATES = (ENDED_ABORTED, ENDED_COMPLETED, ENDED_FAILED, ENDED_UNKNOWN_EFFECT)
#: The three keys that carry those facts. Present or absent AS A GROUP: a record carrying two of them
#: is a record whose ending has no state to belong to.
ENDED_KEYS = ("ended_state", "ended_reasons", "last_proven_stage")

#: Each non-`completed` ending's terminal state. Deliberately NOT an ordered ranking: `unknown-effect`
#: outranks every other ending in `Assessment.state`'s first branch, and `failed` and `aborted` are
#: PEERS whose disagreement is refused there rather than resolved by an order recorded here.
ENDED_STATE_TERMINALS = {
    ENDED_UNKNOWN_EFFECT: STATE_UNKNOWN_EFFECT,
    ENDED_FAILED: STATE_FAILED,
    ENDED_ABORTED: STATE_ABORTED,
}

#: Each state's consequence, worded as issue 07 words it.
CONSEQUENCE = {
    STATE_ACCEPTED: (
        "the wave is complete: every completion condition is met and the authoritative repository "
        "gate passes on the integrated snapshot"
    ),
    STATE_REMEDIATION_PROGRESS: (
        "the wave made bounded remediation progress: its focused gates pass and the exact global "
        "failure baseline did not worsen. This verdict does not claim the authoritative repository "
        "gate passes, and it does not claim the repository is write-ready"
    ),
    STATE_BLOCKED: (
        "the wave is not complete; the reasons name what is missing, and an unresolved blocking "
        "finding may never be carried into completion"
    ),
    STATE_ABORTED: (
        "the wave's execution was stopped before it completed: a conductor record says it ended "
        "aborted, and the last proven stage is where its evidence stops. Completion evidence beside "
        "that record proves what was reached before the stop and never that the wave delivered"
    ),
    STATE_FAILED: (
        "the wave's execution ran and ended failed: the reasons name what ended it and the last "
        "proven stage names where evidence stops. A passing gate receipt beside it describes the "
        "snapshot that receipt measured, not a completed wave"
    ),
    STATE_UNKNOWN_EFFECT: (
        "the wave's execution ended leaving an effect of unknown extent: recovery, not completion, is "
        "what follows. Nothing here may be read as evidence that the repository, the queue, or any "
        "external system is in a known state, and no later record may talk this state down"
    ),
}

# Implementation Decision 9, minus the two codes an effect-free tool cannot honestly use.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

PROJECTION_SCHEMA = "agentic-sdlc/wave-journal-projection@1"
CLASSIFICATION_SCHEMA = "agentic-sdlc/runtime-substitution-classification@1"
BASELINE_SCHEMA = "gate-baseline-comparison/v1"
#: The four conductor-and-critic-side documents this module defines, validates, and never trusts.
MANIFEST_SCHEMA = "agentic-sdlc/wave-artifact-manifest@1"
REVIEW_SCHEMA = "agentic-sdlc/wave-review-submission@1"
CRITIC_SCHEMA = "agentic-sdlc/wave-critic-findings@1"
CONDUCTOR_RECORD_SCHEMA = "agentic-sdlc/wave-verdict-conductor-record@1"

#: Exactly the keys `gate_receipt.build_receipt` writes; `failures` is the one optional addition.
GATE_RECEIPT_KEYS = frozenset(
    {"gate", "argv", "status", "signal", "outcome", "log_digest", "toolchain_digest", "cwd", "self_digest"}
)

OUTCOME_PASSED = "passed"
OUTCOME_FAILED = "failed"
OUTCOME_UNOBSERVED = "unobserved"
FAILURES_IDENTIFIED = "identified"

#: `wave-journal.py`'s three, and only three, terminal node dispositions.
DISPOSITION_SUCCESS = "admitted-success"
DISPOSITION_SKIP = "approved-skip"
DISPOSITION_BLOCKED = "blocked"
DISPOSITIONS = (DISPOSITION_SUCCESS, DISPOSITION_SKIP, DISPOSITION_BLOCKED)

VERDICT_UNEXPLAINED = "unexplained-substitution"
VERDICT_EXACT = "exact-match"
VERDICT_EXPLAINED = "explained-substitution"
CLASSIFICATION_VERDICTS = (VERDICT_EXACT, VERDICT_EXPLAINED, VERDICT_UNEXPLAINED)

REVIEW_ACCEPTED = "accepted"
REVIEW_VERDICTS = (REVIEW_ACCEPTED, "changes-requested", "rejected")

#: Issue 07's completion blockers, verbatim: "Acceptance-criteria violations, safety regressions,
#: corrupted evidence, and failed authoritative gates block completion".
BLOCKING_FINDING_KINDS = (
    "acceptance-criteria-violation",
    "corrupted-evidence",
    "failed-authoritative-gate",
    "safety-regression",
)
#: Issue 07's other half: "Non-blocking complexity, maintainability, documentation, and enhancement
#: findings become prioritized Seeds." A kind in neither set is unclassifiable and therefore blocks.
SEED_WORTHY_FINDING_KINDS = ("complexity", "documentation", "enhancement", "maintainability")

ROLE_IMPLEMENTER = "implementer"
ROLE_REVIEWER = "reviewer"
ROLE_INTEGRATOR = "integrator"

#: The two gate shapes issue 07 admits, kept as one enum so the selection below runs over one value.
GATE_AUTHORITATIVE_PASSED = "authoritative-gate-passed"
GATE_REMEDIATION_NON_WORSENING = "focused-gates-passed-and-baseline-not-worsened"

CONDITIONS: tuple[tuple[int, str], ...] = (
    (1, "required-node-dispositions"),
    (2, "no-unexplained-substitution"),
    (3, "declared-artifacts-validate"),
    (4, "workstream-reviews-accepted"),
    (5, "fan-in-authorized"),
    (6, "gate-contract-passes"),
    (7, "budgets-retries-revisions-approvals-traceable"),
    (8, "conductor-records-verdict"),
)

#: Carried in every document, because the conductor records this verdict and the record should carry
#: what it does not prove. The docstring above is the authoritative statement of each.
RESIDUALS = (
    "every digest check here is re-derivation, not a boundary against a same-OS-user forger",
    "condition 3 hashes declared artifacts in the target tree as it is now; no Git snapshot, commit, "
    "or merge-base is verified, because this tool runs no subprocess",
    "reviews, the artifact manifest, the critic findings, and the conductor record are same-user "
    "assertions: validated and cross-checked against the journal, never authenticated, and a seal "
    "from wave-submission.py adds provenance no consumer here reads",
    "freshness is underivable: a stale but internally consistent artifact set derives its state by "
    "construction",
    "Implementation Decision 61's `aborted`, `failed`, and `unknown-effect` are read from the "
    "conductor record's ended_state, which is the conductor's own account: an ending nobody recorded "
    "is unobservable here, and a wave whose record says completed derives from completion evidence "
    "alone",
    "an unknown effect is derived, never bounded: this tool names the state and the last proven "
    "stage, and what the effect actually touched stays a recovery question no artifact here answers",
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_READ_CHUNK = 1 << 20


class InputError(Exception):
    """A supplied artifact is unreadable, unparseable, or not the document it claims to be (exit 2).

    Deliberately separate from a named reason: a malformed artifact means the QUESTION could not be
    asked, while a reason means it was asked and the answer is "not complete".
    """


def canonical_bytes(value: Any) -> bytes:
    """The family's canonical form: sorted keys, tight, ASCII, one trailing newline."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
        + b"\n"
    )


def receipt_canonical_digest(body: dict[str, Any]) -> str:
    """`gate_receipt.canonical_digest`, re-expressed: the same form with NO trailing newline."""
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()


def derive_gate_outcome(status: Any) -> str:
    """`gate_receipt.derive_outcome`, re-expressed. No status can spell `unobserved` but `null`."""
    if status is None:
        return OUTCOME_UNOBSERVED
    return OUTCOME_PASSED if status == 0 else OUTCOME_FAILED


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN` and `Infinity` by default; no producer here can write one."""
    raise InputError(f"a supplied artifact carries the non-finite JSON constant {token}")


def _reject_nonfinite_values(document: Any, label: str, path: str) -> None:
    """A post-parse walk, because a huge literal like `1e400` is a float `json` never hands to
    `parse_constant`: it is an ordinary number token that `float()` overflows to `inf`, which
    `canonical_bytes` would then refuse with `allow_nan=False` at EMIT time -- an internal failure
    long after this artifact was admitted -- rather than a named input error at READ time. Every
    field is walked, not only the ones this module happens to read, because a non-finite number in a
    field this module ignores today is still a non-finite number no digest here can cover if a later
    version starts reading it. The walk is ITERATIVE because a deeply nested artifact would otherwise
    exhaust the interpreter's stack, which is a crash rather than a classified exit.
    """
    stack: list[Any] = [document]
    while stack:
        value = stack.pop()
        if isinstance(value, float) and not math.isfinite(value):
            raise InputError(
                f"the {label} artifact {path} carries a non-finite number, which no digest can cover"
            )
        if isinstance(value, dict):
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a duplicate JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a document carrying two `verdict`s parses
    to whichever the writer put second. That is a document with two meanings, and picking one of them
    is exactly the guess this module refuses everywhere else.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"a supplied artifact repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


def load_artifact(path: str, label: str) -> dict[str, Any]:
    """Read one emitted artifact. Every failure here is unusable input (exit 2), never a reason.

    The regular-file check runs BEFORE the read: `open()` on a FIFO blocks until a writer shows up,
    which for a supplied artifact path may be never, so a directory mistake would exit 2 promptly
    while a FIFO mistake hung forever. `Path.stat()` follows a symlink to its target, which is the
    question this asks -- "is what I would read a regular file" -- rather than "is the path itself
    one".

    `RecursionError` is classified here too: `json`'s scanner recurses once per nesting level, so a
    deeply nested supplied artifact is unusable input rather than an internal failure of this module.
    """
    candidate = Path(path)
    try:
        mode = candidate.stat().st_mode
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    if not stat.S_ISREG(mode):
        raise InputError(f"the {label} artifact {path} is not a regular file, so it cannot be read")
    try:
        raw = candidate.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read the {label} artifact {path}: {exc}") from exc
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_reject_nonfinite)
    except RecursionError as exc:
        raise InputError(f"the {label} artifact {path} nests too deeply to be parsed, so it cannot be read") from exc
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"the {label} artifact {path} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise InputError(f"the {label} artifact {path} is not a JSON object")
    _reject_nonfinite_values(value, label, path)
    return value


def require_schema(value: dict[str, Any], key: str, expected: str, label: str, path: str) -> None:
    if value.get(key) != expected:
        raise InputError(f"the {label} artifact {path} is not {expected} ({key}={value.get(key)!r})")


def _field(value: dict[str, Any], key: str, label: str, path: str) -> Any:
    if key not in value:
        raise InputError(f"the {label} artifact {path} carries no {key}")
    return value[key]


def _text_field(value: dict[str, Any], key: str, label: str, path: str) -> str:
    found = _field(value, key, label, path)
    if not isinstance(found, str) or not found:
        raise InputError(f"the {label} artifact {path} carries a {key} that is not a non-empty string")
    return found


def _list_field(value: dict[str, Any], key: str, label: str, path: str) -> list[Any]:
    found = _field(value, key, label, path)
    if not isinstance(found, list):
        raise InputError(f"the {label} artifact {path} carries a {key} that is not a list")
    return found


def _string_list_field(value: dict[str, Any], key: str, label: str, path: str) -> list[str]:
    found = _list_field(value, key, label, path)
    if not all(isinstance(item, str) for item in found):
        raise InputError(f"the {label} artifact {path} carries a {key} that is not a list of strings")
    return list(found)


def _int_value(value: Any, what: str, path: str) -> int:
    # `isinstance(True, int)` is True, and a boolean seq or limit is a different document.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(f"{what} in {path} is not an integer")
    return value


def _instant(value: Any, what: str, path: str) -> str:
    if not isinstance(value, str) or not _TIME.match(value):
        raise InputError(f"{what} in {path} is not a YYYY-MM-DDTHH:MM:SSZ instant")
    return value


def load_gate_receipt(path: str, label: str) -> dict[str, Any]:
    """Read one gate receipt and verify the clauses this derivation rests on.

    A receipt carries no `schema` field, so it is recognised by its exact key set instead. A receipt
    predating the `outcome` taxonomy fails that check by name, which is the same answer
    `scripts/gate_baseline.py` gives it: what its failing set MEANS cannot be established.
    """
    receipt = load_artifact(path, label)
    keys = set(receipt)
    if not GATE_RECEIPT_KEYS <= keys or not keys <= GATE_RECEIPT_KEYS | {"failures"}:
        raise InputError(
            f"the {label} {path} does not carry exactly a gate receipt's fields, `outcome` included: "
            f"{sorted(keys)}"
        )
    body = {key: value for key, value in receipt.items() if key != "self_digest"}
    if receipt_canonical_digest(body) != receipt["self_digest"]:
        raise InputError(f"the {label} {path} does not verify: its self_digest does not re-derive")
    if receipt["outcome"] != derive_gate_outcome(receipt["status"]):
        raise InputError(
            f"the {label} {path} records outcome {receipt['outcome']!r}, which its status "
            f"{receipt['status']!r} does not derive"
        )
    if receipt["argv"] is None and receipt["status"] is not None:
        raise InputError(f"the {label} {path} claims a verdict although nothing was executed")
    failures = receipt.get("failures")
    if failures is not None and (
        not isinstance(failures, dict)
        or set(failures) != {"harness", "names", "state"}
        or not isinstance(failures["names"], list)
        or not all(isinstance(name, str) for name in failures["names"])
    ):
        raise InputError(f"the {label} {path} carries a failing set that is not {{harness, names, state}}")
    if not isinstance(receipt["gate"], str) or not receipt["gate"]:
        raise InputError(f"the {label} {path} names no gate")
    return receipt


class Journal:
    """The journal projection, RE-DERIVED. Nothing here decides; it answers questions about facts.

    The projection is re-derived rather than read: `wave-journal.py`'s `read_journal` proved every
    line is exactly the canonical form of what it parses to, so re-canonicalising `entries` reproduces
    the file's bytes and their digest must equal the published `journal_digest`. That makes the
    published digest usable as the head anchor condition 8 compares, and it makes a projection whose
    entries were edited after the fact malformed input rather than evidence.
    """

    def __init__(self, projection: dict[str, Any], path: str) -> None:
        self.path = path
        self.projection = projection
        entries = _list_field(projection, "entries", "wave journal projection", path)
        if not entries or not all(isinstance(entry, dict) for entry in entries):
            raise InputError(f"the wave journal projection {path} carries no entries to derive from")
        self.entries = entries
        self.journal_digest = self._verify_chain()
        self.wave_id = _text_field(projection, "wave_id", "wave journal projection", path)
        self.mission_id = _text_field(projection, "mission_id", "wave journal projection", path)
        self.plan_digest = _text_field(projection, "plan_digest", "wave journal projection", path)
        self.mode = _text_field(projection, "mode", "wave journal projection", path)
        self.last_at = _instant(projection.get("last_at"), "the projection's last_at", path)
        self.required = _string_list_field(projection, "required_nodes", "wave journal projection", path)
        self.nodes = self._nodes()
        self.approvals = self._records("approval")
        self.budgets = self._records("budget")
        self.retries = self._records("retry")
        self.revisions = self._records("plan-revision")
        self._cross_check_projection()

    def _verify_chain(self) -> str:
        lines = []
        for index, entry in enumerate(self.entries):
            if _int_value(entry.get("seq"), f"entry {index}'s seq", self.path) != index:
                raise InputError(
                    f"the wave journal projection {self.path} carries entry {index} declaring seq "
                    f"{entry.get('seq')!r}: the entries were reordered or a gap was left"
                )
            line = canonical_bytes(entry)
            if index and entry.get("prev_digest") != hashlib.sha256(lines[index - 1]).hexdigest():
                raise InputError(
                    f"the wave journal projection {self.path} carries an entry {index} whose "
                    "prev_digest does not re-derive from entry " + str(index - 1)
                )
            lines.append(line)
        derived = hashlib.sha256(b"".join(lines)).hexdigest()
        published = self.projection.get("journal_digest")
        if derived != published:
            raise InputError(
                f"the wave journal projection {self.path} publishes journal_digest {published!r}, "
                "which its own entries do not re-derive"
            )
        return derived

    def _records(self, kind: str) -> list[dict[str, Any]]:
        found = []
        for entry in self.entries[1:]:
            if entry.get("kind") != kind:
                continue
            record = entry.get("record")
            if not isinstance(record, dict):
                raise InputError(f"a {kind} entry in {self.path} carries no record object")
            found.append(dict(record, seq=_int_value(entry.get("seq"), f"a {kind} entry's seq", self.path)))
        return found

    def _nodes(self) -> dict[str, dict[str, Any]]:
        nodes: dict[str, dict[str, Any]] = {}
        for entry in self.entries[1:]:
            if entry.get("kind") != "node":
                continue
            record = entry.get("record")
            if not isinstance(record, dict):
                raise InputError(f"a node entry in {self.path} carries no record object")
            node_id = _text_field(record, "node_id", "wave journal projection", self.path)
            disposition = _text_field(record, "disposition", "wave journal projection", self.path)
            if disposition not in DISPOSITIONS:
                raise InputError(
                    f"node {node_id} in {self.path} declares disposition {disposition!r}, which is not "
                    f"one of {list(DISPOSITIONS)}"
                )
            if node_id in nodes:
                raise InputError(f"node {node_id} reaches two dispositions in {self.path}")
            nodes[node_id] = {
                "node_id": node_id,
                "disposition": disposition,
                "role": _text_field(record, "role", "wave journal projection", self.path),
                "outputs": _string_list_field(record, "outputs", "wave journal projection", self.path),
                "approval": record.get("approval"),
                "seq": _int_value(entry.get("seq"), "a node entry's seq", self.path),
                "at": _instant(entry.get("at"), "a node entry's at", self.path),
            }
        return nodes

    def _cross_check_projection(self) -> None:
        """Refuse a projection whose own summary fields disagree with the entries beside them.

        These are the two places this module could have taken a producer's word for a fact it derives
        itself. Comparing instead of choosing means a hand-edited projection is malformed input.
        """
        derived = sorted(set(self.required) - set(self.nodes))
        published = self.projection.get("required_nodes_without_disposition")
        if published != derived:
            raise InputError(
                f"the wave journal projection {self.path} publishes "
                f"required_nodes_without_disposition {published!r}, which its required_nodes and "
                f"entries do not derive ({derived!r})"
            )
        dispositions = self.projection.get("dispositions")
        if not isinstance(dispositions, dict) or sorted(dispositions) != sorted(self.nodes):
            raise InputError(
                f"the wave journal projection {self.path} publishes a dispositions map that names "
                "different nodes from its entries"
            )
        for node_id, published_node in dispositions.items():
            if not isinstance(published_node, dict) or published_node.get("disposition") != self.nodes[node_id][
                "disposition"
            ]:
                raise InputError(
                    f"the wave journal projection {self.path} publishes a disposition for {node_id} "
                    "that its entries do not derive"
                )
        for budget in self.budgets:
            limit = _int_value(budget.get("limit"), "a budget record's limit", self.path)
            consumed = _int_value(budget.get("consumed"), "a budget record's consumed", self.path)
            budget["remaining"] = limit - consumed
        for published_budget in _list_field(self.projection, "budgets", "wave journal projection", self.path):
            if not isinstance(published_budget, dict):
                raise InputError(f"the wave journal projection {self.path} publishes a non-object budget")
            match = [item for item in self.budgets if item["seq"] == published_budget.get("seq")]
            if len(match) != 1 or published_budget.get("remaining") != match[0]["remaining"]:
                raise InputError(
                    f"the wave journal projection {self.path} publishes a budget whose remaining its "
                    "own limit and consumed do not derive"
                )

    def role_nodes(self, role: str) -> list[dict[str, Any]]:
        return sorted((node for node in self.nodes.values() if node["role"] == role), key=lambda item: item["seq"])

    def approval_ids(self) -> set[str]:
        ids = set()
        for record in self.approvals:
            ids.add(_text_field(record, "approval_id", "wave journal projection", self.path))
        return ids

    def approval(self, approval_id: str) -> dict[str, Any] | None:
        for record in self.approvals:
            if record.get("approval_id") == approval_id:
                return record
        return None


class Assessment:
    """The accumulating evidence. Nothing here decides; `state` derives from the reasons and the gate.

    Reasons are held PER CONDITION so the document can say which of issue 07's eight is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree.
    """

    def __init__(self) -> None:
        self.conditions: dict[int, list[str]] = {number: [] for number, _ in CONDITIONS}
        self.critic_reasons: list[str] = []
        self.binding_reasons: list[str] = []
        #: How each supplied conductor record says the execution ended, keyed by the non-`completed`
        #: token and holding the paths that claim it, so a disagreement is representable rather than
        #: overwritten. `completed` is deliberately absent from this map: it overrides nothing.
        self.ended_states: dict[str, list[str]] = {}
        self.ended_reasons: list[str] = []
        self.gate_mode: str | None = None
        self.gate_outcome: str | None = None
        self.wave_id: str | None = None
        self.mission_id: str | None = None
        self.target: str | None = None
        self.blocking_findings: list[dict[str, Any]] = []
        self.seed_worthy_findings: list[dict[str, Any]] = []
        self.critic_supplied = False
        self.gate: dict[str, Any] = {
            "authoritative_gate": None,
            "baseline_non_worsening": None,
            "baseline_toolchain_drifted": None,
            "failing_tests": None,
            "focused_gates": [],
            "outcome": None,
        }
        self.evidence: dict[str, Any] = {
            "conductor_recorded_at": None,
            "declared_artifacts": None,
            # Decision 61's ended facts: every record's account, in the order they were supplied, plus
            # the dominant ending the fold selected from them. `last_proven_stage` is published only
            # when ONE account carries that ending, because choosing between two would be a pick.
            "ended_accounts": [],
            "ended_reasons": [],
            "ended_state": None,
            "fan_in_approval": None,
            "integrator_nodes": [],
            "journal_digest": None,
            "last_proven_stage": None,
            "mode": None,
            "plan_digest": None,
            "required_nodes": None,
            "required_nodes_blocked": [],
            "required_nodes_without_disposition": [],
            "reviewed_workstreams": [],
            "runtime_classified_nodes": [],
        }

    def note(self, number: int, reason: str) -> None:
        self.conditions[number].append(reason)

    def reasons(self) -> list[str]:
        # The ended facts lead, because how the execution ended outranks what its evidence shows.
        flat = list(self.ended_reasons)
        flat.extend(self.binding_reasons)
        for number, _ in CONDITIONS:
            flat.extend(self.conditions[number])
        flat.extend(self.critic_reasons)
        return flat

    def state(self) -> str:
        """Exactly one state, always. Implementation Decision 61's six, folded in this exact order.

        The selection is one partition over one value, so two states are unrepresentable. The order of
        the first three branches is the whole of Decision 61's precedence and each boundary is
        load-bearing:

          * `unknown-effect` DOMINATES, before the disagreement branch and before every piece of
            completion evidence. An unknown effect can never be talked down -- not by a peer record
            claiming the execution merely failed, and not by a later one claiming it completed.
          * TWO DIFFERENT other endings are `blocked`, because `failed` and `aborted` are peers that
            nothing here can rank; `assess_conductor_record` has already named the disagreement, and
            refusing to pick is the point.
          * ONE other ending overrides the completion evidence: the eight conditions describe what was
            proven, never that the execution reached its end.

        `completed` is not in `ended_states` at all, so a completed execution falls through to the
        three states this module derived before Decision 61's other three existed. The final branch is
        defence in depth against this module's own worst failure -- returning no state -- and it is a
        named reason rather than an `assert`, which `python -O` would strip.
        """
        if ENDED_UNKNOWN_EFFECT in self.ended_states:
            return ENDED_STATE_TERMINALS[ENDED_UNKNOWN_EFFECT]
        if len(self.ended_states) > 1:
            return STATE_BLOCKED
        if self.ended_states:
            return ENDED_STATE_TERMINALS[next(iter(self.ended_states))]
        if self.reasons():
            return STATE_BLOCKED
        if self.gate_mode == GATE_AUTHORITATIVE_PASSED:
            return STATE_ACCEPTED
        if self.gate_mode == GATE_REMEDIATION_NON_WORSENING:
            return STATE_REMEDIATION_PROGRESS
        self.note(
            6,
            f"no terminal state follows from gate evidence {self.gate_mode!r}, and an underivable "
            "state is blocked rather than guessed",
        )
        return STATE_BLOCKED


def assess_binding(
    assessment: Assessment,
    journal: Journal | None,
    named_waves: list[tuple[str, Any]],
    named_targets: list[tuple[str, Any]],
) -> None:
    """Bind every artifact to ONE wave and ONE repository.

    Composing honest documents from different waves or different trees is the single mistake that
    would let a pile of true statements add up to a false `accepted`. Targets are compared as EXACT
    STRINGS, so a repository reached through a symlinked route disagrees and blocks; resolving paths
    here would mean touching a filesystem this module only reads through its arguments.
    """
    if journal is not None:
        assessment.wave_id = journal.wave_id
        assessment.mission_id = journal.mission_id
    for label, value in named_waves:
        if value is None:
            continue
        if assessment.wave_id is None:
            assessment.wave_id = value
            continue
        if value != assessment.wave_id:
            assessment.binding_reasons.append(
                f"the {label} names wave {value!r}, not the wave {assessment.wave_id!r} the other "
                "artifacts are about"
            )
    present = [(label, value) for label, value in named_targets if isinstance(value, str) and value]
    if not present:
        return
    reference_label, reference = present[0]
    assessment.target = reference
    for label, value in present[1:]:
        if value != reference:
            assessment.binding_reasons.append(
                f"the {label} names a different target ({value}) from the {reference_label} ({reference})"
            )


def assess_dispositions(assessment: Assessment, journal: Journal | None) -> None:
    """Condition 1, exactly as issue 07 words it, plus the reason its wording leaves open.

    "every required node has an admitted success, approved skip, or explicit blocked disposition" is
    a completeness test, and `blocked` SATISFIES it. That reading is preserved -- the condition is
    met when every required node reached one of the three -- and a required node that is explicitly
    blocked is still a named reason, because issue 07 also says a wave may never complete with an
    unresolved blocking finding, and an explicitly blocked required node is one.
    """
    if journal is None:
        assessment.note(
            1,
            "no wave journal projection was supplied, so no required node's disposition is known; "
            "project it with wave-journal.py project",
        )
        return
    assessment.evidence["journal_digest"] = journal.journal_digest
    assessment.evidence["plan_digest"] = journal.plan_digest
    assessment.evidence["mode"] = journal.mode
    assessment.evidence["required_nodes"] = list(journal.required)
    missing = sorted(set(journal.required) - set(journal.nodes))
    assessment.evidence["required_nodes_without_disposition"] = missing
    if missing:
        assessment.note(
            1,
            "required node(s) reached no disposition at all: " + ", ".join(missing),
        )
    blocked = sorted(
        node_id
        for node_id in journal.required
        if node_id in journal.nodes and journal.nodes[node_id]["disposition"] == DISPOSITION_BLOCKED
    )
    assessment.evidence["required_nodes_blocked"] = blocked
    for node_id in blocked:
        assessment.note(
            1,
            f"required node {node_id} reached the explicit blocked disposition at seq "
            f"{journal.nodes[node_id]['seq']}: issue 07 admits it as a disposition, and a wave may "
            "not complete carrying it",
        )


def assess_substitutions(
    assessment: Assessment, journal: Journal | None, classifications: list[tuple[str, dict[str, Any]]]
) -> None:
    """Condition 2: "runtime receipts contain no unexplained substitution".

    Coverage is half the condition. A wave that supplies one exact-match classification for one node
    has not shown its OTHER nodes were served what they requested, so every node that reached
    `admitted-success` -- the disposition that asserts something actually ran -- must be classified.
    `blocks_wave_completion` is re-derived from the verdict rather than read, because a document whose
    summary contradicts its own verdict is malformed, not evidence.
    """
    classified: dict[str, str] = {}
    for path, document in classifications:
        verdict = _text_field(document, "verdict", "runtime substitution classification", path)
        if verdict not in CLASSIFICATION_VERDICTS:
            raise InputError(
                f"the runtime substitution classification {path} declares verdict {verdict!r}, which "
                f"is not one of {list(CLASSIFICATION_VERDICTS)}"
            )
        blocks = document.get("blocks_wave_completion")
        if blocks is not (verdict == VERDICT_UNEXPLAINED):
            raise InputError(
                f"the runtime substitution classification {path} publishes blocks_wave_completion "
                f"{blocks!r}, which its verdict {verdict!r} does not derive"
            )
        evidence = document.get("evidence")
        node = evidence.get("node") if isinstance(evidence, dict) else None
        if not isinstance(node, str) or not node:
            raise InputError(
                f"the runtime substitution classification {path} names no node in evidence.node, so "
                "which node it is about cannot be established"
            )
        if node in classified:
            raise InputError(f"two runtime substitution classifications are about node {node}")
        classified[node] = verdict
        if verdict == VERDICT_UNEXPLAINED:
            detail = "; ".join(str(item) for item in document.get("reasons") or []) or "(no reason stated)"
            assessment.note(
                2,
                f"node {node} was served an unexplained substitution: {detail}",
            )
    assessment.evidence["runtime_classified_nodes"] = sorted(classified)
    if not classifications:
        assessment.note(
            2,
            "no runtime substitution classification was supplied for any node, so `receipts contain "
            "no unexplained substitution` is unproven; classify each served record with "
            "runtime-assignment.py classify",
        )
    if journal is None:
        if classifications:
            assessment.note(
                2,
                "no wave journal projection was supplied, so the classifications cannot be shown to "
                "cover the nodes that actually spawned",
            )
        return
    spawned = sorted(
        node_id for node_id, node in journal.nodes.items() if node["disposition"] == DISPOSITION_SUCCESS
    )
    uncovered = [node_id for node_id in spawned if node_id not in classified]
    if uncovered:
        assessment.note(
            2,
            "node(s) reached admitted-success with no runtime substitution classification, so what "
            "they were served is unproven: " + ", ".join(uncovered),
        )
    foreign = sorted(set(classified) - set(journal.nodes))
    if foreign:
        assessment.note(
            2,
            "runtime substitution classification(s) are about node(s) this journal does not carry, "
            "so they are not evidence about this wave: " + ", ".join(foreign),
        )


def _contained_relative(raw: str) -> str | None:
    """The declared path, or None when it is not a contained repository-relative path.

    Lexical containment only, and deliberately strict: an absolute path, a backslash, a `.` or `..`
    component, and an empty component are each refused before any filesystem call, so a manifest
    cannot name `/etc/passwd` or climb out of the target.
    """
    if not raw or raw.startswith("/") or "\\" in raw or "\0" in raw:
        return None
    parts = PurePosixPath(raw).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return "/".join(parts)


def assess_artifacts(
    assessment: Assessment, journal: Journal | None, manifest: dict[str, Any] | None, manifest_path: str | None
) -> None:
    """Condition 3: declared artifacts validate and match the recorded repository state.

    Two clauses, both checked. VALIDATE: every declared artifact exists inside the target as a regular
    file whose bytes re-derive the recorded sha256. MATCH THE DECLARATION: every output an
    admitted-success node declared appears in the manifest, so a wave cannot declare five artifacts
    and validate one.
    """
    if manifest is None:
        assessment.note(
            3,
            "no wave artifact manifest was supplied, so the wave's declared artifacts are neither "
            "validated nor matched against the repository state",
        )
        declared: set[str] = set()
    else:
        path = str(manifest_path)
        target = _text_field(manifest, "target", "wave artifact manifest", path)
        entries = _list_field(manifest, "artifacts", "wave artifact manifest", path)
        declared = set()
        if not entries:
            assessment.note(3, "the wave artifact manifest declares no artifact at all, so it validates nothing")
        for item in entries:
            if not isinstance(item, dict):
                raise InputError(f"the wave artifact manifest {path} carries a non-object artifact entry")
            relative = _text_field(item, "path", "wave artifact manifest", path)
            digest = _text_field(item, "sha256", "wave artifact manifest", path)
            if not _HEX64.match(digest):
                raise InputError(
                    f"the wave artifact manifest {path} records a sha256 for {relative!r} that is not "
                    "64 lowercase hex characters"
                )
            contained = _contained_relative(relative)
            if contained is None:
                assessment.note(
                    3,
                    f"the manifest declares artifact {relative!r}, which is not a contained "
                    "repository-relative path, so what it refers to is not established",
                )
                continue
            declared.add(contained)
            reason = _validate_declared_artifact(Path(target), contained, digest)
            if reason is not None:
                assessment.note(3, reason)
        assessment.evidence["declared_artifacts"] = sorted(declared)
    if manifest is None:
        return  # the absent manifest is already one named reason; coverage against nothing is not a second
    if journal is None:
        assessment.note(
            3,
            "no wave journal projection was supplied, so the manifest cannot be shown to cover the "
            "outputs the wave's nodes declared",
        )
        return
    uncovered = sorted(
        {
            output
            for node in journal.nodes.values()
            if node["disposition"] == DISPOSITION_SUCCESS
            for output in node["outputs"]
        }
        - declared
    )
    if uncovered:
        assessment.note(
            3,
            "output(s) declared by admitted-success node(s) are absent from the artifact manifest, so "
            "they were never validated: " + ", ".join(uncovered),
        )


def _validate_declared_artifact(target: Path, relative: str, recorded: str) -> str | None:
    """Hash one declared artifact inside the target. Returns a named reason, or None when it matches.

    A missing file, a directory, a symlinked final component, and a digest that does not re-derive are
    each a reason rather than an input error: the manifest is well-formed and the ANSWER is that the
    declared artifact does not match the repository state.
    """
    candidate = target / relative
    try:
        link = candidate.lstat()
    except OSError as exc:
        return f"declared artifact {relative} cannot be read in the target: {exc}"
    if stat.S_ISLNK(link.st_mode):
        return (
            f"declared artifact {relative} is a symlink, so what its digest would be about is the "
            "link's target rather than a file in this tree"
        )
    if not stat.S_ISREG(link.st_mode):
        return f"declared artifact {relative} is not a regular file in the target"
    digest = hashlib.sha256()
    try:
        with candidate.open("rb") as stream:
            while chunk := stream.read(_READ_CHUNK):
                digest.update(chunk)
    except OSError as exc:
        return f"declared artifact {relative} cannot be read in the target: {exc}"
    if digest.hexdigest() != recorded:
        return (
            f"declared artifact {relative} does not match its recorded sha256, so the declaration and "
            "the repository state disagree"
        )
    return None


def assess_reviews(
    assessment: Assessment, journal: Journal | None, reviews: list[tuple[str, dict[str, Any]]]
) -> None:
    """Condition 4: "workstream reviews are accepted".

    Issue 07 has reviewers "inspect immutable workstream results and never repair them", so an
    acceptance is only evidence when the reviewer is a DIFFERENT node, carries the reviewer role, and
    reviewed something that already existed -- its entry follows the work's. Coverage is again half
    the condition: every implementer node that reached admitted-success owns a workstream, and an
    unreviewed one is unmet rather than absent.
    """
    accepted: dict[str, list[str]] = {}
    for path, document in reviews:
        subject = _text_field(document, "subject_node_id", "wave review submission", path)
        reviewer = _text_field(document, "reviewer_node_id", "wave review submission", path)
        verdict = _text_field(document, "verdict", "wave review submission", path)
        evidence = _string_list_field(document, "evidence", "wave review submission", path)
        if verdict not in REVIEW_VERDICTS:
            assessment.note(
                4,
                f"the review of {subject} declares verdict {verdict!r}, which is not one of "
                f"{list(REVIEW_VERDICTS)}; an unrecognised verdict is not an acceptance",
            )
            continue
        if verdict != REVIEW_ACCEPTED:
            detail = "; ".join(str(item) for item in document.get("reasons") or []) or "(no reason stated)"
            assessment.note(4, f"the review of {subject} is {verdict}, not accepted: {detail}")
            continue
        if not evidence:
            assessment.note(
                4,
                f"the accepted review of {subject} carries no evidence, so `accepted` is asserted "
                "rather than recorded",
            )
            continue
        if subject == reviewer:
            assessment.note(
                4,
                f"node {subject} accepted its own workstream: issue 07 has reviewers inspect results "
                "they did not produce",
            )
            continue
        if journal is None:
            continue
        subject_node = journal.nodes.get(subject)
        reviewer_node = journal.nodes.get(reviewer)
        if subject_node is None:
            assessment.note(4, f"a review names subject node {subject}, which this journal does not carry")
            continue
        if reviewer_node is None:
            assessment.note(4, f"a review names reviewer node {reviewer}, which this journal does not carry")
            continue
        if reviewer_node["role"] != ROLE_REVIEWER:
            assessment.note(
                4,
                f"the review of {subject} was submitted by {reviewer}, whose role in this journal is "
                f"{reviewer_node['role']}, not {ROLE_REVIEWER}",
            )
            continue
        if reviewer_node["seq"] < subject_node["seq"]:
            assessment.note(
                4,
                f"the review of {subject} was recorded at seq {reviewer_node['seq']}, before the work "
                f"it reviews at seq {subject_node['seq']}, so it did not inspect that result",
            )
            continue
        accepted.setdefault(subject, []).append(reviewer)
    assessment.evidence["reviewed_workstreams"] = sorted(accepted)
    if journal is None:
        # Noted whether or not reviews were supplied. Without the journal, WHICH workstreams needed
        # review is unknown, and a condition nothing was checked against must never read as met: an
        # empty review set over an unknown workstream set is the vacuous pass this module refuses.
        assessment.note(
            4,
            "no wave journal projection was supplied, so which workstreams needed review is unknown "
            "and no review can be bound to the workstream or reviewer role it claims",
        )
        return
    workstreams = [
        node["node_id"]
        for node in journal.role_nodes(ROLE_IMPLEMENTER)
        if node["disposition"] == DISPOSITION_SUCCESS
    ]
    if not workstreams:
        assessment.note(
            4,
            f"this journal carries no {ROLE_IMPLEMENTER} node that reached admitted-success, so there "
            "is no reviewed workstream result and the condition cannot be met by evidence",
        )
    unreviewed = [node_id for node_id in workstreams if node_id not in accepted]
    if unreviewed:
        assessment.note(
            4,
            "workstream(s) reached admitted-success with no accepted review: " + ", ".join(unreviewed),
        )


def assess_fan_in(assessment: Assessment, journal: Journal | None, approval_id: str | None) -> None:
    """Condition 5: "fan-in was authorized".

    The approval is named by the conductor and CHECKED against the journal, because a wave carries
    several approvals and any of them would satisfy a mere existence test -- the skip approval for an
    out-of-scope workstream would authorize the merge. So the named approval must be in the journal,
    its scope must name the integrator node, and the integrator's entry must FOLLOW it: an
    authorization recorded after the mutation it authorizes is not one.
    """
    assessment.evidence["fan_in_approval"] = approval_id
    if approval_id is None:
        assessment.note(
            5,
            "no fan-in approval was named, so nothing in the journal is identified as the "
            "authorization the integrator acted under",
        )
    if journal is None:
        assessment.note(
            5,
            "no wave journal projection was supplied, so neither the fan-in approval nor the "
            "integrator node can be read",
        )
        return
    integrators = journal.role_nodes(ROLE_INTEGRATOR)
    assessment.evidence["integrator_nodes"] = [node["node_id"] for node in integrators]
    performed = [node for node in integrators if node["disposition"] == DISPOSITION_SUCCESS]
    if not integrators:
        assessment.note(
            5,
            f"this journal carries no {ROLE_INTEGRATOR} node, so no fan-in was performed and "
            "`fan-in was authorized` cannot be met by evidence",
        )
    elif not performed:
        assessment.note(
            5,
            "the integrator node(s) "
            + ", ".join(f"{node['node_id']} ({node['disposition']})" for node in integrators)
            + " reached no admitted-success, so no authorized fan-in happened",
        )
    if approval_id is None:
        return
    approval = journal.approval(approval_id)
    if approval is None:
        assessment.note(
            5,
            f"the named fan-in approval {approval_id!r} is not recorded in this journal, so the "
            "authorization is asserted rather than recorded",
        )
        return
    scope = approval.get("scope")
    if not isinstance(scope, list) or not all(isinstance(item, str) for item in scope):
        raise InputError(f"approval {approval_id} in {journal.path} carries a scope that is not a list of strings")
    approval_seq = _int_value(approval.get("seq"), f"approval {approval_id}'s seq", journal.path)
    for node in performed:
        if node["node_id"] not in scope:
            assessment.note(
                5,
                f"the fan-in approval {approval_id} has scope {scope}, which does not name the "
                f"integrator node {node['node_id']} that performed the fan-in",
            )
        if node["seq"] < approval_seq:
            assessment.note(
                5,
                f"integrator node {node['node_id']} was recorded at seq {node['seq']}, before the "
                f"fan-in approval {approval_id} at seq {approval_seq}: an authorization recorded "
                "after the mutation is not one",
            )


def assess_gate(
    assessment: Assessment,
    receipt: dict[str, Any] | None,
    authoritative_gate: str | None,
    focused: list[tuple[str, dict[str, Any]]],
    baseline: dict[str, Any] | None,
) -> None:
    """Condition 6, and the one predicate that separates the two ready states.

    `outcome` partitions {passed, failed, unobserved}. `unobserved` reaches NEITHER state: a gate that
    produced no verdict cannot be evidence that it passed, and it cannot be a baseline either
    (`gate_baseline.py` refuses it for the same reason). A failed gate reaches remediation-progress
    only with an `identified` failing set -- `unparsed` is not an empty set and must never be compared
    as one -- focused gates that pass on the SAME snapshot under the SAME pinned toolchain, and an
    exact non-worsening comparison of this very receipt.
    """
    assessment.gate["authoritative_gate"] = authoritative_gate
    assessment.gate["focused_gates"] = [
        {"gate": document.get("gate"), "outcome": document.get("outcome")} for _, document in focused
    ]
    if baseline is not None:
        assessment.gate["baseline_non_worsening"] = baseline.get("non_worsening")
        assessment.gate["baseline_toolchain_drifted"] = baseline.get("toolchain_drifted")
    if authoritative_gate is None:
        assessment.note(
            6,
            "no authoritative gate was named, so nothing distinguishes the supplied receipt from a "
            "hook or partial-task result, which Implementation Decision 17 forbids substituting for "
            "the authoritative repository gate",
        )
    if receipt is None:
        assessment.note(
            6,
            "no authoritative gate receipt was supplied, so no gate verdict on the integrated "
            "snapshot is available",
        )
        return
    outcome = receipt["outcome"]
    assessment.gate_outcome = outcome
    assessment.gate["outcome"] = outcome
    failures = receipt.get("failures")
    if failures is not None:
        assessment.gate["failing_tests"] = sorted(failures["names"])
    if authoritative_gate is not None and receipt["gate"] != authoritative_gate:
        assessment.note(
            6,
            f"the supplied receipt is about gate {receipt['gate']!r}, not the named authoritative "
            f"gate {authoritative_gate!r}",
        )
    for path, document in focused:
        if document["gate"] == receipt["gate"]:
            assessment.note(
                6,
                f"the focused gate receipt {path} is about the authoritative gate {document['gate']!r} "
                "itself, so it is not a focused gate and cannot stand in for one",
            )
        if document["cwd"] != receipt["cwd"]:
            assessment.note(
                6,
                f"the focused gate {document['gate']!r} ran in {document['cwd']!r}, not the "
                f"integrated snapshot {receipt['cwd']!r} the authoritative gate ran in",
            )
        if document["toolchain_digest"] != receipt["toolchain_digest"]:
            assessment.note(
                6,
                f"the focused gate {document['gate']!r} ran under a different pinned toolchain from "
                "the authoritative gate, so the two verdicts are not about one configuration",
            )
        if document["outcome"] != OUTCOME_PASSED:
            assessment.note(
                6,
                f"the focused gate {document['gate']!r} did not pass (outcome "
                f"{document['outcome']!r}), and remediation progress requires every focused gate to "
                "pass",
            )
    if outcome == OUTCOME_UNOBSERVED:
        assessment.note(
            6,
            "the authoritative gate produced no verdict (outcome unobserved), so it is evidence "
            "neither that the gate passes nor of an exact failing set",
        )
        return
    if outcome == OUTCOME_PASSED:
        if focused:
            assessment.note(
                6,
                "the authoritative gate passes, yet focused gate receipts were supplied as well: a "
                "passing authoritative gate is the normal delivery evidence and mixing the two "
                "leaves which verdict is being claimed ambiguous",
            )
            return
        assessment.gate_mode = GATE_AUTHORITATIVE_PASSED
        return
    if failures is None:
        assessment.note(
            6,
            "the authoritative gate failed and its receipt records no failing set, so it was never "
            "baselined: re-record the gate with --harness unittest",
        )
        return
    if failures["state"] != FAILURES_IDENTIFIED:
        assessment.note(
            6,
            f"the authoritative gate receipt's failing set is {failures['state']}: identification was "
            "attempted and failed, which is not an exact set of names and cannot be remediated "
            "against",
        )
        return
    if not focused:
        assessment.note(
            6,
            "the authoritative gate failed and no focused gate receipt was supplied, so there is no "
            "evidence that the wave's own focused gates pass",
        )
        return
    if baseline is None:
        assessment.note(
            6,
            "no baseline comparison was supplied, so the failing set is known but not proven "
            "non-worsening; compare it with scripts/gate_baseline.py",
        )
        return
    if baseline.get("gate") != receipt["gate"]:
        assessment.note(
            6,
            f"the baseline comparison is about a different gate ({baseline.get('gate')!r}) from the "
            f"receipt ({receipt['gate']!r})",
        )
        return
    if sorted(baseline.get("candidate_failing") or []) != sorted(failures["names"]) or baseline.get(
        "candidate_outcome"
    ) != outcome:
        assessment.note(
            6,
            "the baseline comparison does not compare this gate receipt: its candidate failing set or "
            "candidate outcome differs from the receipt's",
        )
        return
    if baseline.get("toolchain_drifted"):
        assessment.note(
            6,
            "the baseline comparison was measured under a different pinned toolchain than this "
            "receipt's, so the exact non-worsening comparison remediation progress rests on is not "
            "exact",
        )
        return
    non_worsening = baseline.get("non_worsening")
    if not isinstance(non_worsening, bool):
        # `newly_failing or not non_worsening` would read an absent or mistyped field as "worsened"
        # and print a reason naming no test at all. A comparison that does not STATE non_worsening as
        # a boolean is its own fact: the exactness question could not be answered.
        assessment.note(
            6,
            "the baseline comparison does not state non_worsening as a boolean, so whether it worsens "
            "the baseline cannot be established",
        )
        return
    if baseline.get("newly_failing") or not non_worsening:
        assessment.note(
            6,
            "the candidate worsens the global failure baseline, newly failing: "
            + ", ".join(str(item) for item in baseline.get("newly_failing") or ["(unnamed)"]),
        )
        return
    # Set unconditionally: a focused-gate reason recorded above is already a reason, and `state`
    # partitions on the reasons FIRST, so a gate mode set beside one can never select a ready state.
    assessment.gate_mode = GATE_REMEDIATION_NON_WORSENING


def assess_traceability(assessment: Assessment, journal: Journal | None) -> None:
    """Condition 7: "budgets, retries, plan revisions, and approvals are traceable".

    Traceable means each one leads back to something: a budget states the reason it was overrun, a
    retry names a node that reached a disposition, the revision chain leads back to the approved plan
    digest the wave opened with, and every approval a record relies on is in the journal. A wave with
    no budget record at all has not tracked consumption, which is unmet rather than clean.
    """
    if journal is None:
        assessment.note(
            7,
            "no wave journal projection was supplied, so the wave's budgets, retries, plan revisions, "
            "and approvals cannot be traced",
        )
        return
    if not journal.budgets:
        assessment.note(
            7,
            "this journal records no budget at all, so the wave's consumption against its approved "
            "budgets is not traceable",
        )
    for budget in journal.budgets:
        budget_id = _text_field(budget, "budget_id", "wave journal projection", journal.path)
        if budget["remaining"] < 0 and not budget.get("reasons"):
            assessment.note(
                7,
                f"budget {budget_id} is overrun by {-budget['remaining']} {budget.get('unit')} and "
                "states no reason, so the overrun is recorded but not traceable",
            )
    approvals = journal.approval_ids()
    for retry in journal.retries:
        node_id = _text_field(retry, "node_id", "wave journal projection", journal.path)
        if node_id not in journal.nodes:
            assessment.note(
                7,
                f"a retry at seq {retry['seq']} names node {node_id}, which reached no disposition in "
                "this journal, so what the retry led to is not traceable",
            )
    previous: str | None = journal.plan_digest
    for revision in sorted(journal.revisions, key=lambda item: item["seq"]):
        revision_id = _text_field(revision, "revision_id", "wave journal projection", journal.path)
        approval = revision.get("approval")
        if approval not in approvals:
            assessment.note(
                7,
                f"plan revision {revision_id} names approval {approval!r}, which this journal does "
                "not carry, so the revision is not traceable to an approval",
            )
        before = revision.get("from_plan_digest")
        if before is None:
            assessment.note(
                7,
                f"plan revision {revision_id} states no from_plan_digest, so the chain back to the "
                "approved plan is broken",
            )
        elif before != previous:
            assessment.note(
                7,
                f"plan revision {revision_id} revises plan {before}, which is neither the plan the "
                f"wave opened with nor the previous revision's result ({previous})",
            )
        after = revision.get("to_plan_digest")
        previous = after if isinstance(after, str) else None
    for node in journal.nodes.values():
        if node["disposition"] != DISPOSITION_SKIP:
            continue
        if node["approval"] not in approvals:
            assessment.note(
                7,
                f"node {node['node_id']} was skipped under approval {node['approval']!r}, which this "
                "journal does not carry",
            )


def read_ended_facts(assessment: Assessment, record: dict[str, Any], where: str) -> None:
    """Read ONE record's account of how the execution ended (Implementation Decision 61).

    The three keys are present or absent AS A GROUP. All absent is a NAMED REASON -- how the execution
    ended is unrecorded -- and never an assumed `completed`, because Decision 61 closes the outcome at
    six values and an absent field is not one of them; that keeps every
    `wave-verdict-conductor-record@1` written before these fields existed parseable rather than
    silently successful. Facts that CONTRADICT each other are malformed input, exactly like any other
    document that is not what it claims to be: this module refuses to resolve a record that says the
    execution both completed and stopped somewhere, or that names an ending it does not substantiate.
    """
    present = [key for key in ENDED_KEYS if key in record]
    if not present:
        assessment.note(
            8,
            f"the conductor record {where} records no ended_state, so how the execution ended is "
            "unrecorded; Implementation Decision 61 closes the wave outcome at six values and an "
            "absent field is not one of them",
        )
        return
    if len(present) != len(ENDED_KEYS):
        missing = [key for key in ENDED_KEYS if key not in record]
        raise InputError(
            f"the conductor record {where} carries {present} without {missing}; the three ended-state "
            "keys are present or absent AS A GROUP, so a record carrying only some of them is a record "
            "whose ending has no complete account"
        )
    ended = record["ended_state"]
    if ended not in ENDED_STATES:
        raise InputError(
            f"the conductor record {where} declares ended_state {ended!r}, which is not one of "
            f"{list(ENDED_STATES)}; an unrecognised ending is not an ending this module may rank"
        )
    reasons = record.get("ended_reasons")
    if not isinstance(reasons, list) or any(not isinstance(item, str) or not item for item in reasons):
        raise InputError(
            f"the conductor record {where} carries ended_reasons {reasons!r} rather than a list of "
            "non-empty strings"
        )
    stage = record.get("last_proven_stage")
    if ended == ENDED_COMPLETED:
        if reasons:
            raise InputError(
                f"the conductor record {where} says the execution completed and still names "
                "ended_reasons; a completed execution has no ending reason, so the two fields cannot "
                "both be true and neither may be preferred over the other here"
            )
        if stage is not None:
            raise InputError(
                f"the conductor record {where} says the execution completed and names "
                f"last_proven_stage {stage!r}; for a completed execution the last proven stage is the "
                "execution, so the field is null"
            )
    elif not reasons:
        raise InputError(
            f"the conductor record {where} says the execution ended {ended} and names no reason, so "
            "nothing in it states what ended the execution"
        )
    elif not isinstance(stage, str) or not stage:
        raise InputError(
            f"the conductor record {where} says the execution ended {ended} and its last_proven_stage "
            f"is {stage!r} rather than a non-empty string; user story 91 leads a failure with where "
            "evidence stops, not only with the fact that it stopped"
        )
    assessment.evidence["ended_accounts"].append(
        {"ended_reasons": list(reasons), "ended_state": ended, "last_proven_stage": stage, "record": where}
    )
    if ended == ENDED_COMPLETED:
        return
    assessment.ended_states.setdefault(ended, []).append(where)
    assessment.ended_reasons.append(
        f"the conductor record {where} says the execution ended {ended} at last proven stage "
        f"{stage!r}: {'; '.join(reasons)}"
    )


def resolve_ended_state(assessment: Assessment) -> None:
    """Fold every record's ending into the ONE account the document publishes.

    `Assessment.state` folds the same three tokens into a state; this publishes the facts behind that
    fold. The two rules that are not simple bookkeeping:

      * `unknown-effect` DOMINATES and is never talked down, so a peer ending recorded beside it is
        named as outranked rather than resolved against.
      * `failed` and `aborted` are PEERS. Two of them is a named disagreement and NO published ending,
        because picking one would be this module inventing the fact it exists to read.

    A `completed` account beside a non-`completed` one is named too: Decision 61's "process completion
    and publication cannot manufacture success" is exactly the case of a later record claiming a wave
    that crashed came out fine.
    """
    if not assessment.ended_states:
        return
    completed = [
        account["record"]
        for account in assessment.evidence["ended_accounts"]
        if account["ended_state"] == ENDED_COMPLETED
    ]
    if completed:
        assessment.ended_reasons.append(
            f"the conductor record(s) {', '.join(completed)} say the execution completed while "
            f"another record says it ended {', '.join(sorted(assessment.ended_states))}; a later "
            "account of completion never talks down a recorded ending"
        )
    if ENDED_UNKNOWN_EFFECT in assessment.ended_states:
        dominant = ENDED_UNKNOWN_EFFECT
        outranked = sorted(token for token in assessment.ended_states if token != dominant)
        if outranked:
            assessment.ended_reasons.append(
                f"an unknown effect outranks every other recorded ending ({', '.join(outranked)}): an "
                "unknown effect is never talked down, and what follows it is recovery rather than "
                "completion"
            )
    elif len(assessment.ended_states) > 1:
        tokens = sorted(assessment.ended_states)
        stated = "; ".join(f"{token} in {', '.join(assessment.ended_states[token])}" for token in tokens)
        assessment.ended_reasons.append(
            f"the supplied conductor records state different endings ({stated}), and "
            f"{' outranks neither of the others, nor does '.join(tokens)}, so no ended state is picked "
            "and this wave stays blocked until one account is withdrawn or corrected"
        )
        return
    else:
        dominant = next(iter(assessment.ended_states))
    accounts = [
        account
        for account in assessment.evidence["ended_accounts"]
        if account["ended_state"] == dominant
    ]
    assessment.evidence["ended_state"] = dominant
    assessment.evidence["ended_reasons"] = [
        reason for account in accounts for reason in account["ended_reasons"]
    ]
    # Published only when ONE account carries the dominant ending: two accounts of the same ending can
    # name two stages, and choosing between them would be a pick. Both stay in `ended_accounts`.
    assessment.evidence["last_proven_stage"] = (
        accounts[0]["last_proven_stage"] if len(accounts) == 1 else None
    )


def assess_conductor_record(
    assessment: Assessment, journal: Journal | None, records: list[tuple[str, dict[str, Any]]]
) -> None:
    """Condition 8: "the conductor records the verdict", plus Decision 61's ended facts.

    A tool cannot be evidence of its own recording, so what is checked here is the conductor's own
    record of the state it is about to write down: which wave, which exact journal state it read,
    where the verdict goes, and when. The `journal_digest` is the load-bearing field -- it is the
    external head anchor `wave-journal.py`'s `read_journal` names as the remedy for a rewritten last
    line or a truncated tail, and the conductor is the only party holding a copy that did not come
    out of the file being read.

    MORE THAN ONE RECORD IS ADMITTED, because a wave that crashed and was resumed has two accounts of
    how its execution ended, and argparse keeping only the last one would let the later account erase
    the earlier silently. Every record is validated, anchored, and ordered against the same journal;
    `resolve_ended_state` then folds their endings, which is what makes the no-talking-down rule mean
    anything. `conductor_recorded_at` publishes the LATEST stamp, because that is the last instant at
    which a conductor recorded a verdict over this wave.
    """
    if not records:
        assessment.note(
            8,
            "no conductor record was supplied, so nothing shows the conductor read this wave's exact "
            "journal state and is recording a verdict over it",
        )
        return
    anchors: list[tuple[str, str, str]] = []
    stamps: list[str] = []
    for where, record in records:
        anchor = _text_field(record, "journal_digest", "conductor record", where)
        if not _HEX64.match(anchor):
            raise InputError(
                f"the conductor record {where} carries a journal_digest that is not 64 lowercase hex "
                "characters"
            )
        # Both are read for their presence: a record naming no destination and no recorder is a note
        # to nobody, and `_text_field` refuses an empty or absent value as malformed input.
        _text_field(record, "verdict_destination", "conductor record", where)
        _text_field(record, "recorded_by", "conductor record", where)
        recorded_at = _instant(record.get("recorded_at"), "the conductor record's recorded_at", where)
        read_ended_facts(assessment, record, where)
        anchors.append((where, anchor, recorded_at))
        stamps.append(recorded_at)
    assessment.evidence["conductor_recorded_at"] = max(stamps)
    resolve_ended_state(assessment)
    if journal is None:
        assessment.note(
            8,
            "no wave journal projection was supplied, so the conductor record's journal anchor cannot "
            "be compared with the journal it claims to be about",
        )
        return
    for _where, anchor, recorded_at in anchors:
        if anchor != journal.journal_digest:
            assessment.note(
                8,
                f"the conductor's retained journal_digest {anchor} is not this projection's "
                f"{journal.journal_digest}: the journal has been rewritten at its head, truncated at "
                "its tail, or this record is about a different read",
            )
        if recorded_at < journal.last_at:
            assessment.note(
                8,
                f"the conductor record is stamped {recorded_at}, before the journal's last entry at "
                f"{journal.last_at}, so it cannot be a record of this wave's completed evidence",
            )


def assess_critic(
    assessment: Assessment, journal: Journal | None, findings: dict[str, Any] | None, path: str | None
) -> None:
    """Classify the critic's findings. The critic advises; this is where the conductor classifies.

    Issue 07: acceptance-criteria violations, safety regressions, corrupted evidence, and failed
    authoritative gates BLOCK completion and require a newly reviewed remediation workstream;
    complexity, maintainability, documentation, and enhancement findings become prioritized Seeds. A
    kind in neither closed set is unclassifiable, and an unclassifiable finding blocks rather than
    being assumed harmless. A resolved blocker must name a remediation node this journal admits,
    because `resolved` is otherwise a word the critic's own document asserts about itself.
    """
    if findings is None:
        assessment.critic_reasons.append(
            "no critic findings document was supplied, so this wave has no adversarial disposition; "
            "issue 07 requires the critic's findings to be classified before completion"
        )
        return
    assessment.critic_supplied = True
    where = str(path)
    for item in _list_field(findings, "findings", "critic findings", where):
        if not isinstance(item, dict):
            raise InputError(f"the critic findings {where} carry a non-object finding")
        finding_id = _text_field(item, "finding_id", "critic findings", where)
        kind = _text_field(item, "kind", "critic findings", where)
        severity = _text_field(item, "severity", "critic findings", where)
        rationale = _text_field(item, "rationale", "critic findings", where)
        disposition = _text_field(item, "recommended_disposition", "critic findings", where)
        artifact = _text_field(item, "affected_artifact", "critic findings", where)
        evidence = _string_list_field(item, "evidence", "critic findings", where)
        resolved = _field(item, "resolved", "critic findings", where)
        if not isinstance(resolved, bool):
            raise InputError(f"finding {finding_id} in {where} carries a resolved that is not a boolean")
        if not evidence:
            raise InputError(
                f"finding {finding_id} in {where} carries no evidence: issue 07 requires every finding "
                "to carry severity, evidence, affected artifact, recommended disposition, and "
                "rationale"
            )
        summary = {
            "affected_artifact": artifact,
            "evidence": evidence,
            "finding_id": finding_id,
            "kind": kind,
            "rationale": rationale,
            "recommended_disposition": disposition,
            "severity": severity,
        }
        if kind in SEED_WORTHY_FINDING_KINDS:
            assessment.seed_worthy_findings.append(summary)
            continue
        assessment.blocking_findings.append(dict(summary, resolved=resolved))
        if kind not in BLOCKING_FINDING_KINDS:
            assessment.critic_reasons.append(
                f"critic finding {finding_id} declares kind {kind!r}, which is neither a named "
                f"blocking kind {list(BLOCKING_FINDING_KINDS)} nor a named seed-worthy kind "
                f"{list(SEED_WORTHY_FINDING_KINDS)}; an unclassifiable finding blocks rather than "
                "being assumed non-blocking"
            )
            continue
        if not resolved:
            assessment.critic_reasons.append(
                f"critic finding {finding_id} is an unresolved {kind} ({severity}) against "
                f"{artifact}: {rationale}"
            )
            continue
        remediation = item.get("resolution")
        if not isinstance(remediation, str) or not remediation:
            assessment.critic_reasons.append(
                f"critic finding {finding_id} claims to be resolved but names no remediation node in "
                "`resolution`, so the claim is an assertion rather than evidence"
            )
            continue
        node = None if journal is None else journal.nodes.get(remediation)
        if journal is None:
            assessment.critic_reasons.append(
                f"critic finding {finding_id} claims resolution by {remediation}, and no wave journal "
                "projection was supplied to check that node reached an admitted success"
            )
        elif node is None or node["disposition"] != DISPOSITION_SUCCESS:
            assessment.critic_reasons.append(
                f"critic finding {finding_id} claims resolution by {remediation}, which reached "
                f"{'no disposition' if node is None else node['disposition']} in this journal, so the "
                "blocker's remediation is not evidenced"
            )


def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    """Load every supplied artifact, then derive exactly one terminal wave state from them."""
    projection = load_artifact(args.journal_projection, "wave journal projection") if args.journal_projection else None
    journal = None
    if projection is not None:
        require_schema(projection, "schema", PROJECTION_SCHEMA, "wave journal projection", args.journal_projection)
        if projection.get("status") != "projected":
            raise InputError(
                f"the wave journal projection {args.journal_projection} is not a projected result "
                f"(status={projection.get('status')!r})"
            )
        journal = Journal(projection, args.journal_projection)

    classifications = []
    for path in args.runtime_classification:
        document = load_artifact(path, "runtime substitution classification")
        require_schema(document, "schema", CLASSIFICATION_SCHEMA, "runtime substitution classification", path)
        classifications.append((path, document))

    manifest = load_artifact(args.artifact_manifest, "wave artifact manifest") if args.artifact_manifest else None
    if manifest is not None:
        require_schema(manifest, "schema", MANIFEST_SCHEMA, "wave artifact manifest", args.artifact_manifest)

    reviews = []
    for path in args.review:
        document = load_artifact(path, "wave review submission")
        require_schema(document, "schema", REVIEW_SCHEMA, "wave review submission", path)
        reviews.append((path, document))

    receipt = load_gate_receipt(args.gate_receipt, "authoritative gate receipt") if args.gate_receipt else None
    focused = [
        (path, load_gate_receipt(path, "focused gate receipt")) for path in args.focused_gate_receipt
    ]
    baseline = load_artifact(args.baseline_comparison, "baseline comparison") if args.baseline_comparison else None
    if baseline is not None:
        require_schema(baseline, "schema_version", BASELINE_SCHEMA, "baseline comparison", args.baseline_comparison)

    conductors = []
    for path in args.conductor_record:
        document = load_artifact(path, "conductor record")
        require_schema(document, "schema", CONDUCTOR_RECORD_SCHEMA, "conductor record", path)
        conductors.append((path, document))

    findings = load_artifact(args.critic_findings, "critic findings") if args.critic_findings else None
    if findings is not None:
        require_schema(findings, "schema", CRITIC_SCHEMA, "critic findings", args.critic_findings)

    assessment = Assessment()
    assess_binding(
        assessment,
        journal,
        [
            ("wave artifact manifest", (manifest or {}).get("wave_id")),
            *[(f"conductor record {path}", document.get("wave_id")) for path, document in conductors],
            ("critic findings", (findings or {}).get("wave_id")),
            *[(f"review submission {path}", document.get("wave_id")) for path, document in reviews],
        ],
        [
            ("wave artifact manifest", (manifest or {}).get("target")),
            ("authoritative gate receipt", (receipt or {}).get("cwd")),
            *[(f"focused gate receipt {path}", document.get("cwd")) for path, document in focused],
        ],
    )
    assess_dispositions(assessment, journal)
    assess_substitutions(assessment, journal, classifications)
    assess_artifacts(assessment, journal, manifest, args.artifact_manifest)
    assess_reviews(assessment, journal, reviews)
    assess_fan_in(assessment, journal, args.fan_in_approval)
    assess_gate(assessment, receipt, args.authoritative_gate, focused, baseline)
    assess_traceability(assessment, journal)
    assess_conductor_record(assessment, journal, conductors)
    assess_critic(assessment, journal, findings, args.critic_findings)

    state = assessment.state()
    # An execution that did not reach its end never proved the receipt's snapshot is this wave's
    # result, so the top-level CLAIM is null rather than the receipt's fact. The fact itself stays in
    # `gate`, where it is a statement about one receipt and not about the wave.
    ended = state in (STATE_ABORTED, STATE_FAILED, STATE_UNKNOWN_EFFECT)
    gate_passes = (
        None if ended or assessment.gate_outcome is None else assessment.gate_outcome == OUTCOME_PASSED
    )
    return {
        "schema": RESULT_SCHEMA,
        "command": "derive",
        "state": state,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[state],
        # The two machine-checkable denials. `remediation-progress` carries False for both by
        # construction, so a consumer never has to read prose to learn that this verdict does not
        # claim the repository gate passes or that normal delivery may proceed.
        "repository_gate_passes": gate_passes,
        "permits_normal_delivery": state == STATE_ACCEPTED and gate_passes is True,
        "wave_id": assessment.wave_id,
        "mission_id": assessment.mission_id,
        "target": assessment.target,
        "conditions": [
            {
                "met": not assessment.conditions[number],
                "number": number,
                "reasons": assessment.conditions[number],
                "slug": slug,
            }
            for number, slug in CONDITIONS
        ],
        "reasons": assessment.reasons(),
        "critic": {
            "blocking_findings": assessment.blocking_findings,
            "reasons": assessment.critic_reasons,
            "seed_worthy_findings": assessment.seed_worthy_findings,
            "supplied": assessment.critic_supplied,
        },
        "gate": assessment.gate,
        "evidence": assessment.evidence,
        "residuals": list(RESIDUALS),
    }


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Re-expressed from `gate_receipt.abandon_broken_stream`. Catching the failed write is not enough:
    the bytes stay PENDING in the stream's buffer and CPython flushes `sys.stdout`/`sys.stderr` once
    more while finalizing; that second failure replaces the process exit code with 120, which is
    outside this module's closed exit set. Dropping the module attribute is how CPython itself
    represents a stream this process does not have (`2>&-` starts the interpreter with
    `sys.stderr is None`), and it loses no byte the failed write had not already lost. The identity
    check is load-bearing because `main` is importable: only the stream that actually failed may be
    dropped, never a caller's replacement.
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
    write = getattr(stream, "write", None)
    if not callable(write):
        return lambda line: None
    flush = getattr(stream, "flush", None)
    live = [True]

    def emit(line: str) -> None:
        if not live[0]:
            return
        try:
            write(line)
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
    advisory_stderr()(f"wave-verdict.py: {message}\n")


def emit_result(result: dict[str, Any]) -> int:
    """Deliver the one result document, or CLASSIFY the failure instead of inheriting 1 or 120.

    Unlike a diagnostic line, this document IS the evidence, so a stdout that cannot receive it is not
    a lost convenience -- the question was answered and the answer did not arrive. That is an internal
    failure to deliver (exit 1). `canonical_bytes` is `ensure_ascii=True`, so the payload is ASCII and
    a text stream with no `.buffer` -- what an importing caller's `redirect_stdout(StringIO())`
    installs -- receives byte-identical characters rather than being made to fail.
    """
    payload = canonical_bytes(result)
    stream = sys.stdout
    buffer = getattr(stream, "buffer", None)
    write: Any = None
    flush: Any = None
    body: Any = payload
    if buffer is not None and callable(getattr(buffer, "write", None)):
        write, flush = buffer.write, getattr(buffer, "flush", None)
    elif stream is not None and callable(getattr(stream, "write", None)):
        write, flush, body = stream.write, getattr(stream, "flush", None), payload.decode("ascii")
    if write is None:
        report_input_error(
            "this process was handed no stdout to write its one result document to, so the derived "
            "wave state could not be delivered; the state itself is unaffected and nothing was written"
        )
        return EXIT_INTERNAL
    try:
        write(body)
        if callable(flush):
            flush()
    except (OSError, ValueError) as exc:
        # Abandoned BEFORE returning: the classification below is worthless if the interpreter's
        # shutdown flush of the same broken stream replaces this exit code with 120.
        abandon_broken_stream("stdout", stream)
        report_input_error(
            f"cannot write the result document to stdout: {exc}; an unknown prefix of it may already "
            "have reached the consumer, so the state was derived but not delivered"
        )
        return EXIT_INTERNAL
    return EXIT_OK


class _Parser(argparse.ArgumentParser):
    """argparse, taught this module's two stream rules.

    `error` writes usage through `print_usage`, which FALLS BACK TO STDOUT when `sys.stderr is None`:
    under `2>&-` a grammar error would keep exit 2 while putting usage bytes where this module's one
    result document lives. And argparse swallows a failed write while leaving its bytes pending, which
    is enough for the shutdown flush to replace the usage error's 2 with 120.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            # argparse resolved `sys.stderr`/`sys.stdout` itself and got None: this process was handed
            # no such stream, so the line is dropped rather than redirected onto the other one.
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


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="wave-verdict.py",
        description=(
            "Derive the one terminal wave state -- Implementation Decision 61's accepted, "
            "remediation-progress, blocked, aborted, failed, or unknown-effect -- from one wave's "
            "emitted artifacts. Read-only, offline, subprocess-free, and effect-free: it authorizes "
            "nothing."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "derive",
        description=(
            "Every artifact is optional and every absence is a NAMED reason, so this may be run at "
            "any point in a wave and will say which evidence is still missing. Deriving `blocked` is "
            "this command succeeding."
        ),
        epilog=(
            "Exit codes: 0 a terminal state was derived, blocked included; 2 a supplied artifact is "
            "unreadable, not JSON, or not the document it claims to be, or the arguments themselves "
            "are unusable; 1 an unexpected internal failure, INCLUDING a stdout that cannot receive "
            "the one result document, because a state derived and not delivered is not a success. "
            "Implementation Decision 9's 3 and 4 do not apply: a command that causes no effect can "
            "neither refuse before one nor admit one."
        ),
    )
    command.add_argument(
        "--journal-projection",
        dest="journal_projection",
        default=None,
        help=f"wave-journal.py project document ({PROJECTION_SCHEMA})",
    )
    command.add_argument(
        "--runtime-classification",
        dest="runtime_classification",
        action="append",
        default=[],
        help=f"runtime-assignment.py classify result ({CLASSIFICATION_SCHEMA}); repeat once per node",
    )
    command.add_argument(
        "--artifact-manifest",
        dest="artifact_manifest",
        default=None,
        help=(
            f"the conductor's {MANIFEST_SCHEMA}: wave_id, target, and artifacts as "
            "repository-relative path plus sha256"
        ),
    )
    command.add_argument(
        "--review",
        action="append",
        default=[],
        help=f"one {REVIEW_SCHEMA} per reviewed workstream",
    )
    command.add_argument(
        "--fan-in-approval",
        dest="fan_in_approval",
        default=None,
        help="the approval_id in the journal that authorized fan-in; its scope must name the integrator node",
    )
    command.add_argument(
        "--gate-receipt",
        dest="gate_receipt",
        default=None,
        help="gate_receipt.py receipt for the authoritative repository gate on the integrated snapshot",
    )
    command.add_argument(
        "--authoritative-gate",
        dest="authoritative_gate",
        default=None,
        help="the exact authoritative gate string this repository's contract names, e.g. `mise run check`",
    )
    command.add_argument(
        "--focused-gate-receipt",
        dest="focused_gate_receipt",
        action="append",
        default=[],
        help="gate_receipt.py receipt for one focused gate; only a remediation wave needs these",
    )
    command.add_argument(
        "--baseline-comparison",
        dest="baseline_comparison",
        default=None,
        help="gate_baseline.py compare report; only a failed authoritative gate needs one",
    )
    command.add_argument(
        "--conductor-record",
        dest="conductor_record",
        action="append",
        default=[],
        help=(
            f"the conductor's {CONDUCTOR_RECORD_SCHEMA}: wave_id, the journal_digest it retained, "
            "recorded_by, recorded_at, verdict_destination, and how the execution ended "
            f"({', '.join(ENDED_STATES)}) with its reasons and last proven stage. Repeat once per "
            "account: a wave that crashed and was resumed has two, an unknown effect outranks every "
            "other ending, and two disagreeing endings are refused rather than picked"
        ),
    )
    command.add_argument(
        "--critic-findings",
        dest="critic_findings",
        default=None,
        help=f"the critic's {CRITIC_SCHEMA}; the conductor classifies them here",
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
