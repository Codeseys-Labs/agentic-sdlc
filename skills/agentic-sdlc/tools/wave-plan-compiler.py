#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Compile and verify the WavePlan and its PlanDiff -- the DESIRED half of the planning chain.

`docs/plans/claude-code-first-harness/to-spec-handoff.md` fixes the chain this file sits in the
middle of:

    MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope

and issue 16 ("Planning artifact chain and deterministic compiler", lines 42-47) says what this half
owns: "One deterministic plan compiler consumes the MissionContract, admitted PlanningSnapshot,
selected typed submissions, repository policy, and execution-profile limits. It validates schemas,
provenance, evidence conflicts, graph acyclicity, dependencies, custody exclusivity, capability
feasibility, and closed authority/resource bounds, then emits the WavePlan and PlanDiff." The same
section forbids the other half of the job by name: this tool "does not call a model, choose among
contradictory facts, repair the repository, mutate a queue, resolve a runtime route, grant approval,
or execute a node".

THE PLAN AND ITS DIFF ARE ONE EMISSION. Issue 16 lines 57-61 treat the diff as inseparable from a
revision: "A change never mutates an approved WavePlan in place; it produces a new revision and
digest", and the diff "names every added, removed, or changed node, edge, artifact, custody
boundary, authority, route constraint, egress declaration, budget, gate, approval, retry, stop rule,
and terminal criterion". So `compile` has no mode that emits a plan without its diff, and the first
wave's diff is the delta from NO prior plan rather than an omitted document.

THE DIFF IS ALSO ASKABLE ON ITS OWN, and that is a THIRD command rather than a mode of `compile`.
`diff --plan --prior-plan` re-derives the delta between two ALREADY SEALED revisions, which is the
question a plan-admission gate holding two documents actually has, and it needs no submissions,
snapshot, or contract to answer. The two commands differ in exactly one way, deliberately:

  * `compile` REFUSES a zero delta. Sealing revision N+1 whose graph is revision N's would mint a new
    digest for the same plan and let a caller inflate a revision number, so "these submissions imply
    the plan you already have" is a refusal.
  * `diff` ANSWERS a zero delta, explicitly. "What changed between these two revisions?" has a true
    answer when the answer is "nothing", and refusing it would leave a caller unable to tell that
    apart from a diff that failed. So the emitted document carries `no_delta_reason`: null whenever it
    names at least one change, and a sentence naming the emptiness whenever `changes` is `[]`. The
    two fields are cross-checked in both directions, so an empty diff cannot stay silent about being
    empty and a populated one cannot claim to be empty.

A first wave is still not an empty diff: with no prior plan the whole graph is added, so an empty
`changes` beside a null `prior_plan_digest` stays refused.

BOTH COMMANDS PIN THE MISSION. A diff across two missions is meaningless -- the added and removed
nodes would be two different plans' nodes, not one plan's delta -- so `compile` refuses a
`--prior-plan` whose `inputs.mission_digest` is not the admitted contract's, and `diff` refuses two
plans that disagree about it. The consequence is deliberate and worth stating: revising the mission
contract ENDS a plan chain rather than continuing it, because the new plan's first revision is
compiled against a different contract.

DETERMINISM IS A PROPERTY OF THE BYTES, and it is checkable rather than aspirational. Identical inputs
produce byte-identical sealed documents, which holds because of four constructions and nothing else:
`--at` is a supplied argument (no clock), no environment variable is read at all (`os.environ` does
not appear in this file; the only `os` calls are path resolution and the exclusive write), every
emitted list is either explicitly `sorted()` or ordered by a supplied list's own order, and no
iteration order of a `set` or a `dict` reaches an emitted value. String hashing is randomized per
process, so a set iteration order that reached the bytes would make one digest depend on
`PYTHONHASHSEED`. Be precise about WHICH sort carries that: `synthesize_changes` returns
`sorted(changes, key=(kind, subject))`, and because those pairs are unique that one call totally
orders the array no matter how the walks inside it iterated. The `sorted()` calls inside it are the
same convention applied early and are individually unobservable behind it; the final one is the guard,
and neutralizing it is what a test catches. The one cwd-dependent value in this module is an output
PATH -- `--out` is resolved against the process's directory -- and no path reaches a sealed document.

THE SIX CHECKS, EACH A NAMED REFUSAL AND ITS OWN REPORTED GROUP. `compile` admits its inputs, then
asks six separate questions of them, and a violated one is a reason against the property it violated
rather than a "compilation failed":

  * `provenance` -- the submissions were made for THIS mission, and the snapshot's recorded head can
    be carried into the plan verbatim. The plan then binds the mission, snapshot, and submissions
    digests and the limits it was compiled under, so a consumer can tell which four facts produced it.
    Whether that head is still the repository's CURRENT head is plan admission's check: this tool runs
    no git and compares the head to nothing.
  * `authority-bounds` -- the mission's `admitted_classes` must be a PREFIX of the ordered ladder, and
    every workstream's class must be inside it and at or below the mission's ceiling. A wave cannot
    grant an authority its mission never did.
  * `graph` -- every dependency names a submitted workstream, nothing depends on itself, a repeated
    workstream id is refused before anything reasons about it, and the graph is acyclic. The
    acyclicity walk is ITERATIVE, because a long dependency chain is a legitimate plan shape and a
    recursive walk would trade a named refusal for a `RecursionError`.
  * `custody-exclusivity` -- one owner per worktree, and no two workstreams claiming overlapping
    files. Overlap includes containment: a claim on `src` and a claim on `src/app.py` are the same
    custody argued at two depths.
  * `capability-feasibility` -- every demand that maps onto a capability a PlanningSnapshot actually
    observes must be observed and must not be among the snapshot's named unknowns.
  * `resource-bounds` -- the workstream count within the admitted total, and the declared concurrency
    within the admitted concurrency.

NOTHING IS SEALED WHILE ONE REASON STANDS, and the derived pair is read back through the SAME closed
checks `verify` runs, so a synthesis bug becomes a refusal rather than a sealed document `verify`
would later reject. A plan bearing this family's digest is what a downstream admission gate binds, so
a plan that failed a check must not be bindable at all.

WHAT IS DERIVED RATHER THAN COPIED. A submission states what a role wants to do; the plan is this
file's decision about what document that becomes. A node's `output_schema` is derived from its
authority class, and its `wrong_output_class` from its authority class plus its position in the graph,
because a submitter grading its own blast radius is how a `derail` gets planned as a `retry`. The
`edges` are derived from the dependencies, so the plan cannot record two different graphs. Custody,
dependencies, objective, and authority are the submitter's, carried per workstream.

`--out` and `--diff-out` are written `O_EXCL` and fsynced, plan first, because the diff names the
plan's digest. A refusal writes nothing at all.

FOUR DOCUMENTS IN, TWO OUT, AND NO IMPORTS BETWEEN TOOLS.

    --mission      a SEALED agentic-sdlc/mission-contract@1     (mission-contract.py's output)
    --snapshot     a SEALED agentic-sdlc/planning-snapshot@1     (planning-snapshot.py's output)
    --submissions  a SEALED agentic-sdlc/workstream-submissions@1 (this file defines it; see below)
    --prior-plan   a SEALED agentic-sdlc/wave-plan@1, optional; absent means "first wave"
    --limits       an agentic-sdlc/execution-profile-limits@1 policy object, optional

`diff` takes two of those documents and nothing else: `--plan` and `--prior-plan`, both SEALED
wave-plan@1. It writes no file -- the sealed diff and its digest are published in the one result
document -- because a standalone diff is handed no PlanningSnapshot and so could not apply the "not
inside the tree it plans over" rule that `compile --diff-out` enforces, and two paths to one artifact
under two different rules is the weaker of the two.

The sibling tools are consumed as DOCUMENTS, never as modules: nothing here imports
`mission-contract.py` or `planning-snapshot.py`, so their internal vocabularies cannot silently
become this file's, and each input is admitted by re-deriving the one digest the family publishes.
Only the fields this compiler consumes are required of a sibling's document; the rest of a sibling's
schema is that sibling's business, and a field this tool needs and cannot find is named rather than
defaulted.

WHAT WORKSTREAM SUBMISSIONS ARE. Issue 16 lines 38-41 put parallel investigator nodes upstream of
the graph -- "Cartographer, researcher, diagnostic, planner, documentarian, and critic nodes may
investigate in parallel and submit typed evidence or recommendations; none edits the candidate graph
directly or settles truth by role label". `workstream-submissions@1` is the typed form of what those
nodes submit: a list of candidate workstreams, each declaring an id, one objective sentence, the
worktree custody path it wants, the files it wants custody of, the workstream ids it depends on, its
capability demands from a CLOSED set, and one authority class from the mission contract's ladder. It
is a SUBMISSION, not a plan: nothing in it is admitted by having been submitted, the ids are the
submitter's, and the six compiler checks below are where custody exclusivity, acyclicity, capability
feasibility, and the authority ceiling are actually checked against the snapshot and the contract.

NO CLOCK, NO ROUTE, NO NETWORK, NO WRITE INTO WHAT IT DESCRIBES. `--at` is required and supplied:
this tool reads no clock, so two runs over the same inputs produce the same bytes and the same
digest, which is the whole point of calling it deterministic. It resolves no runtime route -- issue
16 keeps that in the separate pre-spawn contract, and a planning preference is not a
`RuntimeAssignment` -- so no node carries a model or an effort. `--out` and `--diff-out` refuse an
occupied destination and refuse to land inside the repository the snapshot describes, because writing
a plan into the tree it plans over changes that tree's dirty state and makes the snapshot's own
record of it wrong.

THE DIGEST CONTRACT IS THIS FAMILY'S, and there is only one way to compute it:

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

where `canonical` is `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`,
`allow_nan=False`, and exactly one trailing newline. The `digest` key is excluded BY NAME rather
than by position, so the derivation does not depend on any ordering the encoder happens to produce.

EXIT CODES. 0 a result was derived, a named refusal included; 2 a supplied file cannot be read as
one JSON object or the arguments themselves are unusable; 1 a derived result that could not be
delivered; 4 a file this run created was left incomplete or unpaired, which is the one partial effect
two exclusive writes can produce.
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

MISSION_SCHEMA = "agentic-sdlc/mission-contract@1"
SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
SUBMISSIONS_SCHEMA = "agentic-sdlc/workstream-submissions@1"
PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
DIFF_SCHEMA = "agentic-sdlc/plan-diff@1"
LIMITS_SCHEMA = "agentic-sdlc/execution-profile-limits@1"
RESULT_SCHEMA = "agentic-sdlc/wave-plan-compiler-result@1"

VERDICT_COMPILED = "compiled"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_COMPILED: (
        "the inputs were admitted, every check this command runs passed, and each document it sealed -- "
        "a WavePlan with its PlanDiff under `compile`, one PlanDiff under `diff` -- carries the one "
        "digest a later admission gate may bind; a compiled document is evidence and authorizes no "
        "node, no write, and no outward effect"
    ),
    VERDICT_VERIFIED: (
        "the sealed document re-derives its own digest and satisfies its closed schema, so it is the "
        "same plan or diff it claims to be; whether its inputs are still current is plan admission's "
        "separate check, and the document is evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "no WavePlan and no PlanDiff were sealed, no digest was derived, and nothing was written; the "
        "reasons name each input or field and what was wrong with it"
    ),
}

# Implementation Decision 9, minus 3: a derived `refused` is a RESULT, not a clean refusal before
# effect, because the refusal happens before anything is written and there was nothing to refuse before.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
#: Reachable for exactly one reason: `compile` may write TWO files, so a plan on disk beside a diff
#: that never landed is a real partial effect rather than a hypothetical one.
EXIT_PARTIAL = 4

DIGEST_KEY = "digest"

#: The mission contract's authority ladder. Re-expressed rather than imported: a sibling tool is
#: consumed as documents, and a shared constant would hide the day the two vocabularies diverged.
AUTHORITY_CLASSES = (
    "read-only-advisory",
    "owned-worktree-write",
    "authorized-fan-in",
    "outward-effect",
)

#: The CLOSED capability vocabulary a submission or a node may demand. Closed because "capability
#: feasibility" is a check against observed host capabilities, and an open string could never be
#: infeasible. Each member is either a host capability the PlanningSnapshot actually observes
#: (`host_capabilities.git`, `.python`, `.uv`) or a bounded orchestration capability the harness
#: itself provides.
CAPABILITY_DEMANDS = (
    "advisory-artifact-write",
    "git-worktree-write",
    "python-execution",
    "repository-gate-execution",
    "repository-read",
    "seeds-queue-read",
    "subagent-dispatch",
    "uv-python-toolchain",
)

#: The wrong-output blast-radius classes the rightsizing skill routes on. A node declares which one
#: its wrong output would be, because that is what makes a review requirement derivable rather than
#: chosen.
WRONG_OUTPUT_CLASSES = ("degrade", "derail", "retry")

#: Issue 16 lines 57-61 enumerate exactly what a PlanDiff must name. This is that enumeration, one
#: member per named thing, so a diff cannot describe a change the issue did not ask it to classify.
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

#: The default execution profile: "four concurrent nodes, 64 total nodes" from the handoff's "One
#: wave, one DAG" section, and recursion OFF -- the handoff says "Recursive spawn remains off by
#: default even when numeric caps are raised", so the default generation count is 0, not 1.
DEFAULT_LIMITS = {
    "max_concurrent_nodes": 4,
    "max_total_nodes": 64,
    "recursive_spawn_generations": 0,
}
LIMITS_KEYS = tuple(sorted(DEFAULT_LIMITS))

#: --- the closed bodies -------------------------------------------------------------------------
#: Every key is REQUIRED in each, so an absence is always a named refusal and never a default.

SUBMISSIONS_BODY_KEYS = (
    "declared_concurrency",
    "mission_id",
    "schema",
    "stated_at",
    "submission_id",
    "workstreams",
)
WORKSTREAM_KEYS = (
    "authority_class",
    "capability_demands",
    "dependencies",
    "file_custody",
    "id",
    "objective",
    "worktree_custody",
)

PLAN_BODY_KEYS = (
    "compiled_at",
    "declared_concurrency",
    "edges",
    "head",
    "inputs",
    "limits",
    "mission_id",
    "nodes",
    "revision",
    "schema",
    "supersedes",
)
#: The snapshot's OWN head record, carried VERBATIM into the plan rather than re-observed: this tool
#: runs no git, so the only head it can honestly bind is the one the admitted snapshot recorded. The
#: key set is the snapshot's, because a subset would silently drop the branch a later admission gate
#: compares. Whether that head is still the CURRENT head is that gate's check, never this one's.
PLAN_HEAD_KEYS = ("branch", "commit_sha", "tree_sha")
#: A node declares no model and no effort BY CONSTRUCTION: issue 16 keeps the exact runtime route
#: unresolved until the separate pre-spawn contract admits it, so a field for one here would be a
#: planning preference masquerading as a `RuntimeAssignment`.
NODE_KEYS = (
    "authority_class",
    "capability_demands",
    "dependencies",
    "file_custody",
    "node_id",
    "objective",
    "output_schema",
    "worktree_custody",
    "wrong_output_class",
)
EDGE_KEYS = ("from", "to")
#: The prior plan is NOT repeated here: `supersedes` in the body is the one record of that one fact,
#: and a document recording it twice could record it two different ways.
PLAN_INPUT_KEYS = (
    "mission_digest",
    "snapshot_digest",
    "submissions_digest",
)

#: `no_delta_reason` is what makes an empty diff EXPLICIT. An empty `changes` array on its own is
#: ambiguous -- "these two revisions are identical" and "this diff was never computed" look the same --
#: and a consumer binding the digest cannot ask a follow-up question. So the field is required in both
#: directions: a sentence when `changes` is `[]`, and null whenever a change is named.
DIFF_BODY_KEYS = (
    "changes",
    "compiled_at",
    "mission_id",
    "no_delta_reason",
    "plan_digest",
    "prior_plan_digest",
    "schema",
)
#: The one sentence an empty diff carries. Fixed rather than composed, so two runs over two identical
#: plan pairs seal the same bytes.
NO_DELTA = (
    "the two revisions are identical in every dimension this schema names: no node, edge, custody "
    "boundary, or authority was added, removed, or changed, so this diff is empty on purpose"
)
CHANGE_KEYS = ("consequence", "evidence", "kind", "semantic", "subject")

SUBMISSIONS_SEALED_KEYS = tuple(sorted(SUBMISSIONS_BODY_KEYS + (DIGEST_KEY,)))
PLAN_SEALED_KEYS = tuple(sorted(PLAN_BODY_KEYS + (DIGEST_KEY,)))
DIFF_SEALED_KEYS = tuple(sorted(DIFF_BODY_KEYS + (DIGEST_KEY,)))

#: The sibling fields this compiler CONSUMES, by dotted name. Only these are required of a sibling's
#: document: the rest of its schema is its own business, and this list is what the checks below read.
MISSION_REQUIRED = (
    "authority.admitted_classes",
    "authority.ceiling",
    "completion_contract.success_criteria",
    "completion_contract.terminal_criteria",
    "mission_id",
    "revision",
    "scope.in_scope",
    "scope.non_goals",
    "stated_at",
    "stop_conditions",
)
SNAPSHOT_REQUIRED = (
    "head.commit_sha",
    "head.tree_sha",
    "host_capabilities",
    "repository.worktree_path",
    "stated_at",
    "unknowns",
)

CHECKS: tuple[str, ...] = (
    "mission-contract",
    "planning-snapshot",
    "workstream-submissions",
    #: `diff`'s two input positions are reported SEPARATELY -- `plan` for the newer revision and
    #: `prior-plan` for the older -- because both are wave-plan@1 and a caller handed a refusal about
    #: "the wave plan" would not learn which of its two documents was the malformed one.
    "plan",
    "prior-plan",
    "execution-profile-limits",
    "output-path",
    "provenance",
    "authority-bounds",
    "graph",
    "custody-exclusivity",
    "capability-feasibility",
    "resource-bounds",
    "closed-key-set",
    "wave-plan-shape",
    "plan-diff-shape",
    "digest",
)

COMPILE_CHECKS = (
    "mission-contract",
    "planning-snapshot",
    "workstream-submissions",
    "prior-plan",
    "execution-profile-limits",
    "output-path",
    "provenance",
    "authority-bounds",
    "graph",
    "custody-exclusivity",
    "capability-feasibility",
    "resource-bounds",
)
#: The six compiler checks, reported separately from input admission so a caller learns WHICH property
#: of an admissible input set was violated rather than that "compilation failed".
COMPILER_CHECKS = COMPILE_CHECKS[6:]
PLAN_VERIFY_CHECKS = ("closed-key-set", "wave-plan-shape", "digest")
DIFF_VERIFY_CHECKS = ("closed-key-set", "plan-diff-shape", "digest")
#: `diff` admits two sealed plans (`plan`, `prior-plan`), pins them to one mission (`provenance`), and
#: reads its own derived document back through the same closed shape `verify --diff` runs.
DIFF_COMMAND_CHECKS = ("plan", "prior-plan", "provenance", "closed-key-set", "plan-diff-shape")
#: The two input positions `diff` admits, and the whole basis of its `inputs_admitted`.
DIFF_INPUT_SLUGS = ("plan", "prior-plan")

#: Which OBSERVED host capability each demand needs. Only the three the PlanningSnapshot actually
#: observes appear: `host_capabilities.{git,python,uv}`. The five omitted demands are harness
#: capabilities no snapshot field reports, so this compiler cannot find them infeasible and says so in
#: `RESIDUALS` rather than pretending it checked them.
DEMAND_CAPABILITY = {
    "git-worktree-write": "git",
    "python-execution": "python",
    "repository-gate-execution": "uv",
    "uv-python-toolchain": "uv",
}

#: A node's output schema, DERIVED from its authority class rather than submitted: what a role hands
#: back is fixed by what it was allowed to do, and a submitter choosing its own output schema could
#: promise a document no consumer reads. This tool validates none of these schemas -- each belongs to
#: the role tool that emits it -- so the field records what to expect, not a proof it will arrive.
AUTHORITY_OUTPUT_SCHEMA = {
    "read-only-advisory": "agentic-sdlc/advisory-submission@1",
    "owned-worktree-write": "agentic-sdlc/worktree-submission@1",
    "authorized-fan-in": "agentic-sdlc/fan-in-submission@1",
    "outward-effect": "agentic-sdlc/outward-effect-submission@1",
}

#: The wrong-output blast radius of the two authority classes whose radius does not depend on the
#: graph. A fan-in or an outward effect is `derail` because its wrong output has already left the
#: node's own custody; an owned-worktree write is `degrade` because it is contained by that custody.
#: `read-only-advisory` is derived from the graph instead (see `derive_wrong_output_class`).
AUTHORITY_WRONG_OUTPUT = {
    "owned-worktree-write": "degrade",
    "authorized-fan-in": "derail",
    "outward-effect": "derail",
}

#: Carried in every document, because a consumer that binds the digest should carry what it does not
#: prove.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "a compiled plan is EVIDENCE: it authorizes no node, no dispatch, no write into the repository it "
    "plans over, and no outward effect; operation-specific approval and runtime admission are separate",
    "an admitted input document is proved to be internally consistent and to be the document its "
    "digest names; whether the state it records is still current is plan admission's separate check",
    "the plan carries the snapshot's RECORDED head verbatim and compares it to nothing: this tool runs "
    "no git, so head freshness is the admission gate's check and not this one's",
    "a node's exact runtime route stays unresolved here by construction: no node carries a model or "
    "an effort, and the pre-spawn contract is the only place one is admitted",
    "custody exclusivity is compared WITHIN each kind: worktree claims against worktree claims and "
    "file claims against file claims. A file claim that falls inside another node's worktree path is "
    "not detected here, because the two are declared against different roots",
    "capability feasibility covers only the three capabilities a PlanningSnapshot observes (git, "
    "python, uv); the other demands in the closed set name harness capabilities no snapshot field "
    "reports, so they are admitted as declared rather than checked",
    "every field outside the closed vocabularies, the instants, and the digests is prose: a "
    "well-formed plan is not an achievable one, and no objective is checked against any evidence",
    "the PlanDiff names a change to a node, an edge, a custody boundary, or an authority. The change "
    "kinds artifact, budget, gate, approval, egress, retry, route-constraint, stop-rule, and "
    "terminal-criterion are UNREACHABLE: a wave-plan@1 node has no field any of them could change, so "
    "the vocabulary is wider than what this revision of the schema can name",
    "two plans are diffable only within one mission: both revisions must bind the same mission "
    "contract digest, so revising the contract ENDS a plan chain rather than continuing it, and the "
    "first plan compiled against the new contract is revision 1 of a new chain",
    "an empty diff means the two supplied revisions are identical in the dimensions above; it is not "
    "a statement that nothing about the wave changed, because a dimension this schema cannot carry "
    "could have changed without any change being nameable",
    "determinism here is over the SEALED documents: identical inputs seal identical bytes. The result "
    "document additionally carries the absolute output paths of this run, which depend on the process "
    "directory a relative --out was resolved against, and no path reaches a sealed document",
    "--diff-out may be supplied without --out: the diff it writes still names a plan_digest for a plan "
    "this run did not put on disk, and exit is 0. Pairing the two files is the caller's request to "
    "make, not this tool's to enforce; --out given alongside --diff-out IS ordered plan-first so that "
    "pair is never left half-written",
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
#: A git object name is 40 (sha1) or 64 (sha256) lowercase hex characters. Both are admitted because
#: the repository's object format is the repository's choice, not this compiler's.
_OBJECT_NAME = re.compile(r"([0-9a-f]{40}|[0-9a-f]{64})\Z")
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

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it, and
    the same function covers all four sealed artifact kinds this tool reads or writes.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest artifact carries one."""
    raise InputError(f"a supplied document carries the non-finite JSON constant {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a plan carrying two `nodes` parses to
    whichever the writer put second. That is a document with two meanings, and picking one of them
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

    `parse_constant` catches the `NaN`/`Infinity` spellings, and nothing else: the literal `1e400` is
    a perfectly ordinary JSON number that overflows to `inf` during parsing without ever passing
    through that hook. It has to be refused because `canonical_bytes` runs with `allow_nan=False`, so
    an infinity reaching the digest derivation would raise out of this module as a traceback instead
    of being classified.

    The walk is ITERATIVE. A plan is a graph document whose nesting is written by whoever supplied it,
    and a recursive walk would trade a classified refusal for a `RecursionError` on exactly the
    hostile input this check exists for.
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
    for a supplied path may be never, so a directory mistake would exit 2 promptly while a FIFO
    mistake hung forever. `Path.stat()` follows a symlink to its target, which is the question this
    asks -- "is what I would read a regular file" -- rather than "is the path itself one".

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

    Reasons are held PER CHECK GROUP so the result can say which part of the job is unmet, and the
    flat `reasons` list is generated from the same store, so the two can never disagree. The flat list
    walks EVERY group rather than the command's own subset: a reason noted against a group this
    command does not report must still reach the verdict.
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

    def verdict(self, command: str) -> str:
        """Exactly one verdict, always.

        The selection is one partition over one value, so two verdicts are unrepresentable. The final
        branch is defence in depth against this module's own worst failure -- returning no verdict --
        and it is a named reason rather than an `assert`, which `python -O` would strip.
        """
        if self.reasons():
            return VERDICT_REFUSED
        if command in ("compile", "diff"):
            return VERDICT_COMPILED
        if command == "verify":
            return VERDICT_VERIFIED
        self.note(
            "closed-key-set",
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
            slug,
            f"{what} is not a non-empty string (found {value!r}), so what it records cannot be read",
        )
        return None
    return value


def _identifier(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    """An id that names a graph vertex, a custody owner, or a document. Bounded so a diff can quote it.

    Deliberately narrow: an id carrying whitespace, a path separator, or a leading punctuation mark
    would be quoted back into diffs, custody comparisons, and refusal text where it is indistinguish-
    able from the surrounding prose.
    """
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not _IDENTIFIER.match(value):
        assessment.note(
            slug,
            f"{what} {value!r} is not an identifier of unreserved characters (letters, digits, and "
            "then any of . _ -), so it cannot be quoted back unambiguously",
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


def _object_name(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    """A git object name, in the two widths a repository's object format can produce."""
    if not isinstance(value, str) or not _OBJECT_NAME.match(value):
        assessment.note(
            slug,
            f"{what} is not 40 or 64 lowercase hexadecimal characters (found {value!r}), so it cannot "
            "be a git object name",
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
            slug,
            f"{what} is not the closed key set {sorted(keys)}: "
            f"missing {missing}, unexpected {extra}",
        )
        return None
    return value


def _string_list(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str, *, allow_empty: bool = True
) -> list[str] | None:
    value = container.get(key)
    if not isinstance(value, list):
        assessment.note(slug, f"{what} is not a JSON array (found {value!r})")
        return None
    if not value and not allow_empty:
        assessment.note(slug, f"{what} is empty, and an empty list here records nothing")
        return None
    for index, entry in enumerate(value):
        if not isinstance(entry, str) or not entry:
            assessment.note(slug, f"{what} at position {index} is not a non-empty string (found {entry!r})")
            return None
    if list(value) != sorted(value) or len(set(value)) != len(value):
        assessment.note(
            slug,
            f"{what} is not a strictly ascending set (found {list(value)}); a repeat or a reordering "
            "would give one meaning two digests",
        )
        return None
    return list(value)


def _closed_vocabulary(
    assessment: Assessment, slug: str, values: list[str], vocabulary: tuple[str, ...], what: str
) -> list[str] | None:
    unknown = [value for value in values if value not in vocabulary]
    if unknown:
        assessment.note(
            slug,
            f"{what} names {unknown}, which {list(vocabulary)} does not contain; an open vocabulary "
            "here could never be infeasible",
        )
        return None
    return values


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


def _relative_path(assessment: Assessment, slug: str, value: str, what: str) -> str | None:
    """A declared custody path: repository-relative, forward-slashed, and not an escape.

    Custody is compared BY STRING between workstreams, so the spellings have to be normalized by
    refusal rather than by rewriting: `a/b`, `./a/b`, and `a//b` naming one file while comparing as
    three would make custody exclusivity unenforceable.
    """
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        assessment.note(slug, f"{what} {value!r} is absolute; custody is declared relative to the repository root")
        return None
    if "\\" in value:
        assessment.note(slug, f"{what} {value!r} carries a backslash; custody paths are forward-slashed")
        return None
    if "\x00" in value:
        assessment.note(slug, f"{what} {value!r} carries a NUL character, which no filesystem path may contain")
        return None
    segments = value.split("/")
    if any(segment in ("", ".", "..") for segment in segments):
        assessment.note(
            slug,
            f"{what} {value!r} carries an empty, `.`, or `..` segment, so two spellings of it would "
            "compare as different custody",
        )
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
            f"{what} declares schema {declared!r} rather than {schema!r}, so it is not the document "
            "kind this input position consumes",
        )
        return None
    if keys is not None:
        found = tuple(sorted(document))
        if found != keys:
            missing = [name for name in keys if name not in document]
            extra = [name for name in found if name not in keys]
            assessment.note(
                slug,
                f"{what} is not the closed sealed key set {list(keys)}: missing {missing}, unexpected {extra}",
            )
            return None
    recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), f"{what}'s recorded digest")
    if recorded is None:
        return None
    derived = document_digest(document)
    if recorded != derived:
        assessment.note(
            slug,
            f"{what} records digest {recorded} which its own content does not re-derive ({derived}): "
            "the document has been edited since it was sealed, or the digest was written by something "
            "other than this family's derivation",
        )
        return None
    return recorded


def _required_fields(
    assessment: Assessment, slug: str, document: dict[str, Any], dotted: tuple[str, ...], what: str
) -> None:
    """Require only the sibling fields THIS compiler consumes, each named by its dotted path.

    A sibling's document is admitted for what this tool reads out of it, not re-validated against the
    sibling's whole schema; that would make this file a second implementation of a schema it does not
    own, and the two would drift.
    """
    for name in dotted:
        container: Any = document
        walked: list[str] = []
        for part in name.split("."):
            walked.append(part)
            if not isinstance(container, dict) or part not in container:
                assessment.note(
                    slug,
                    f"{what} has no {'.'.join(walked)}, and this compiler consumes it, so its absence "
                    "cannot be defaulted",
                )
                container = None
                break
            container = container[part]
        if container is None:
            continue
        if container == "" or container == [] or container == {}:
            assessment.note(slug, f"{what} records {name} as empty ({container!r}), which states nothing")


# ---- the workstream-submissions shape ------------------------------------------------------------


def check_submissions(assessment: Assessment, document: dict[str, Any]) -> list[dict[str, Any]]:
    """The full closed shape of this file's own input schema. Returns the WELL-FORMED workstreams.

    Every field is checked here BECAUSE this file owns the schema; the two sibling artifacts get only
    the fields this compiler consumes. What is deliberately NOT checked here is every cross-workstream
    property the compiler checks own: acyclicity, custody exclusivity, capability feasibility against
    the snapshot's observed host capabilities, and the mission contract's authority ceiling. A
    submission that passes this check is well-formed, not admitted into a plan.

    Only workstreams this function found NOTHING wrong with are returned, so a compiler check never
    reasons about a field that already has its own named reason and never prints a second reason about
    one mistake.
    """
    slug = "workstream-submissions"
    _identifier(assessment, slug, document, "submission_id", "the submissions' submission_id")
    _identifier(assessment, slug, document, "mission_id", "the submissions' mission_id")
    _instant(assessment, slug, document, "stated_at", "the submissions' stated_at")
    _positive_integer(assessment, slug, document, "declared_concurrency", "the submissions' declared_concurrency")
    workstreams = document.get("workstreams")
    if not isinstance(workstreams, list) or not workstreams:
        assessment.note(
            slug,
            f"the submissions' workstreams is not a non-empty JSON array (found {workstreams!r}); a "
            "submission with no workstream proposes nothing",
        )
        return []
    ids: list[str] = []
    admitted: list[dict[str, Any]] = []
    for index, entry in enumerate(workstreams):
        before = len(assessment.groups[slug])
        where = f"workstream at position {index}"
        if not isinstance(entry, dict):
            assessment.note(slug, f"the submissions' {where} is not a JSON object (found {entry!r})")
            continue
        found = tuple(sorted(entry))
        if found != WORKSTREAM_KEYS:
            missing = [name for name in WORKSTREAM_KEYS if name not in entry]
            extra = [name for name in found if name not in WORKSTREAM_KEYS]
            assessment.note(
                slug,
                f"the submissions' {where} is not the closed key set {list(WORKSTREAM_KEYS)}: missing "
                f"{missing}, unexpected {extra}",
            )
            continue
        identifier = _identifier(assessment, slug, entry, "id", f"the submissions' {where} id")
        if identifier is not None:
            ids.append(identifier)
            where = f"workstream {identifier!r}"
        _text(assessment, slug, entry, "objective", f"the submissions' {where} objective")
        _member(
            assessment, slug, entry, "authority_class", AUTHORITY_CLASSES,
            f"the submissions' {where} authority_class",
        )
        demands = _string_list(
            assessment, slug, entry, "capability_demands",
            f"the submissions' {where} capability_demands", allow_empty=False,
        )
        if demands is not None:
            _closed_vocabulary(
                assessment, slug, demands, CAPABILITY_DEMANDS,
                f"the submissions' {where} capability_demands",
            )
        _string_list(assessment, slug, entry, "dependencies", f"the submissions' {where} dependencies")
        custody = _string_list(assessment, slug, entry, "file_custody", f"the submissions' {where} file_custody")
        if custody is not None:
            for position, path in enumerate(custody):
                _relative_path(assessment, slug, path, f"the submissions' {where} file_custody at position {position}")
        worktree = entry.get("worktree_custody")
        if worktree is None:
            # An advisory workstream owns no worktree. Null is the declaration of that, so its absence
            # of custody is stated rather than implied by an empty string.
            pass
        elif not isinstance(worktree, str) or not worktree:
            assessment.note(
                slug,
                f"the submissions' {where} worktree_custody is neither null nor a non-empty string "
                f"(found {worktree!r})",
            )
        else:
            _relative_path(assessment, slug, worktree, f"the submissions' {where} worktree_custody")
        if len(assessment.groups[slug]) == before:
            admitted.append(entry)
    if len(set(ids)) != len(ids):
        repeated = sorted({name for name in ids if ids.count(name) > 1})
        assessment.note(
            slug,
            f"the submissions declare the workstream id(s) {repeated} more than once, so a dependency "
            "naming one of them names two workstreams",
        )
    if ids != sorted(ids):
        assessment.note(
            slug,
            f"the submissions' workstreams are not ordered by id (found {ids}); a reordering that "
            "changes no meaning would change the digest",
        )
    return admitted


# ---- the two output shapes -----------------------------------------------------------------------


def check_plan(
    assessment: Assessment,
    document: dict[str, Any],
    *,
    key_slug: str = "closed-key-set",
    slug: str = "wave-plan-shape",
) -> None:
    """The complete closed shape of a sealed wave-plan@1, read by `verify` and by the compiler itself.

    The two slugs are parameters because the SAME shape is read in two places: `verify --plan` reports
    it as the document under test, and `compile --prior-plan` reports it against the input position it
    arrived in, so a caller can tell which of its two plans was malformed.
    """
    keys = tuple(sorted(document))
    if keys != PLAN_SEALED_KEYS:
        missing = [name for name in PLAN_SEALED_KEYS if name not in document]
        extra = [name for name in keys if name not in PLAN_SEALED_KEYS]
        assessment.note(
            key_slug,
            f"the wave plan is not the closed sealed key set {list(PLAN_SEALED_KEYS)}: missing "
            f"{missing}, unexpected {extra}",
        )
        return
    if document.get("schema") != PLAN_SCHEMA:
        assessment.note(slug, f"the wave plan declares schema {document.get('schema')!r} rather than {PLAN_SCHEMA!r}")
    _instant(assessment, slug, document, "compiled_at", "the wave plan's compiled_at")
    _identifier(assessment, slug, document, "mission_id", "the wave plan's mission_id")
    revision = _positive_integer(assessment, slug, document, "revision", "the wave plan's revision")
    supersedes = document.get("supersedes")
    if supersedes is not None:
        supersedes = _digest_value(assessment, slug, supersedes, "the wave plan's supersedes")
    if revision is not None:
        # The revision chain, checked one link at a time: revision 1 follows nothing, and every later
        # revision names exactly what it supersedes, because issue 16 forbids editing a plan in place.
        if revision == 1 and document.get("supersedes") is not None:
            assessment.note(
                slug,
                "the wave plan is revision 1 and also names a superseded plan; a first revision "
                "follows no prior plan",
            )
        if revision > 1 and document.get("supersedes") is None:
            assessment.note(
                slug,
                f"the wave plan is revision {revision} and names no superseded plan, so what it is a "
                "revision OF is not recorded",
            )
    inputs = _closed_object(assessment, slug, document, "inputs", PLAN_INPUT_KEYS, "the wave plan's inputs")
    if inputs is not None:
        for key in PLAN_INPUT_KEYS:
            _digest_value(assessment, slug, inputs.get(key), f"the wave plan's inputs.{key}")
    head = _closed_object(assessment, slug, document, "head", PLAN_HEAD_KEYS, "the wave plan's head")
    if head is not None:
        _object_name(assessment, slug, head.get("commit_sha"), "the wave plan's head.commit_sha")
        _object_name(assessment, slug, head.get("tree_sha"), "the wave plan's head.tree_sha")
        branch = head.get("branch")
        if branch is not None and (not isinstance(branch, str) or not branch):
            assessment.note(
                slug,
                f"the wave plan's head.branch is {branch!r}, which is neither a non-empty branch name "
                "nor null; a detached head has no branch, and null is how the snapshot says that",
            )
    limits = check_limits_object(assessment, slug, document, "the wave plan's limits")
    concurrency = _positive_integer(
        assessment, slug, document, "declared_concurrency", "the wave plan's declared_concurrency"
    )
    if concurrency is not None and limits is not None and concurrency > limits["max_concurrent_nodes"]:
        assessment.note(
            slug,
            f"the wave plan declares {concurrency} concurrent nodes against its own recorded ceiling of "
            f"{limits['max_concurrent_nodes']}, so the document contradicts itself",
        )
    identifiers = check_nodes(assessment, slug, document, limits)
    check_edges(assessment, slug, document, identifiers)


def check_limits_object(
    assessment: Assessment, slug: str, container: dict[str, Any], what: str
) -> dict[str, int] | None:
    """The `limits` block of a sealed plan: a closed object, then the three values."""
    limits = _closed_object(assessment, slug, container, "limits", LIMITS_KEYS, what)
    if limits is None:
        return None
    return _limit_values(assessment, slug, limits, what)


def _limit_values(assessment: Assessment, slug: str, limits: dict[str, Any], what: str) -> dict[str, int] | None:
    """The execution profile: two positive ceilings and a recursion generation count where 0 is off."""
    admitted: dict[str, int] = {}
    for key in ("max_concurrent_nodes", "max_total_nodes"):
        value = _positive_integer(assessment, slug, limits, key, f"{what}.{key}")
        if value is not None:
            admitted[key] = value
    generations = limits.get("recursive_spawn_generations")
    if not isinstance(generations, int) or isinstance(generations, bool) or generations < 0:
        assessment.note(
            slug,
            f"{what}.recursive_spawn_generations is not an integer of at least 0 (found {generations!r}); "
            "0 is recursion OFF, which is the default the handoff requires",
        )
    else:
        admitted["recursive_spawn_generations"] = generations
    concurrent = admitted.get("max_concurrent_nodes")
    total = admitted.get("max_total_nodes")
    if concurrent is not None and total is not None and concurrent > total:
        assessment.note(
            slug,
            f"{what} admits {concurrent} concurrent nodes out of {total} total, so the concurrency "
            "ceiling can never be reached and one of the two is wrong",
        )
    return admitted if len(admitted) == len(LIMITS_KEYS) else None


def check_nodes(
    assessment: Assessment, slug: str, document: dict[str, Any], limits: dict[str, int] | None
) -> list[str]:
    """Every node's closed shape. Returns the declared node ids in the order they appear."""
    nodes = document.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        assessment.note(
            slug,
            f"the wave plan's nodes is not a non-empty JSON array (found {nodes!r}); a plan with no "
            "node is not one wave's executable graph",
        )
        return []
    if limits is not None and len(nodes) > limits["max_total_nodes"]:
        assessment.note(
            slug,
            f"the wave plan carries {len(nodes)} nodes against its own recorded ceiling of "
            f"{limits['max_total_nodes']}, so the document contradicts itself",
        )
    identifiers: list[str] = []
    for index, entry in enumerate(nodes):
        where = f"node at position {index}"
        if not isinstance(entry, dict):
            assessment.note(slug, f"the wave plan's {where} is not a JSON object (found {entry!r})")
            continue
        found = tuple(sorted(entry))
        if found != NODE_KEYS:
            missing = [name for name in NODE_KEYS if name not in entry]
            extra = [name for name in found if name not in NODE_KEYS]
            assessment.note(
                slug,
                f"the wave plan's {where} is not the closed key set {list(NODE_KEYS)}: missing "
                f"{missing}, unexpected {extra}",
            )
            continue
        node_id = _identifier(assessment, slug, entry, "node_id", f"the wave plan's {where} node_id")
        if node_id is not None:
            identifiers.append(node_id)
            where = f"node {node_id!r}"
        _text(assessment, slug, entry, "objective", f"the wave plan's {where} objective")
        _text(assessment, slug, entry, "output_schema", f"the wave plan's {where} output_schema")
        _member(
            assessment, slug, entry, "authority_class", AUTHORITY_CLASSES,
            f"the wave plan's {where} authority_class",
        )
        _member(
            assessment, slug, entry, "wrong_output_class", WRONG_OUTPUT_CLASSES,
            f"the wave plan's {where} wrong_output_class",
        )
        demands = _string_list(
            assessment, slug, entry, "capability_demands",
            f"the wave plan's {where} capability_demands", allow_empty=False,
        )
        if demands is not None:
            _closed_vocabulary(
                assessment, slug, demands, CAPABILITY_DEMANDS,
                f"the wave plan's {where} capability_demands",
            )
        _string_list(assessment, slug, entry, "dependencies", f"the wave plan's {where} dependencies")
        custody = _string_list(assessment, slug, entry, "file_custody", f"the wave plan's {where} file_custody")
        if custody is not None:
            for position, path in enumerate(custody):
                _relative_path(assessment, slug, path, f"the wave plan's {where} file_custody at position {position}")
        worktree = entry.get("worktree_custody")
        if worktree is None:
            pass
        elif not isinstance(worktree, str) or not worktree:
            assessment.note(
                slug,
                f"the wave plan's {where} worktree_custody is neither null nor a non-empty string "
                f"(found {worktree!r})",
            )
        else:
            _relative_path(assessment, slug, worktree, f"the wave plan's {where} worktree_custody")
    if len(set(identifiers)) != len(identifiers):
        repeated = sorted({name for name in identifiers if identifiers.count(name) > 1})
        assessment.note(
            slug,
            f"the wave plan declares the node id(s) {repeated} more than once, so an edge naming one "
            "of them names two nodes",
        )
    if identifiers != sorted(identifiers):
        assessment.note(
            slug,
            f"the wave plan's nodes are not ordered by node_id (found {identifiers}); a reordering "
            "that changes no meaning would change the digest",
        )
    return identifiers


def derived_edges(nodes: list[Any]) -> list[dict[str, str]]:
    """The ONE edge set a plan's dependencies imply: one edge per (dependency -> dependent), sorted.

    Derived rather than trusted, because `edges` and `nodes[].dependencies` record the same fact and a
    document whose two records disagree has two graphs.
    """
    edges: list[dict[str, str]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("node_id")
        dependencies = node.get("dependencies")
        if not isinstance(node_id, str) or not isinstance(dependencies, list):
            continue
        for dependency in dependencies:
            if isinstance(dependency, str):
                edges.append({"from": dependency, "to": node_id})
    return sorted(edges, key=lambda edge: (edge["from"], edge["to"]))


def check_edges(assessment: Assessment, slug: str, document: dict[str, Any], identifiers: list[str]) -> None:
    """`edges` must be exactly the dependency edges, in one canonical order, over declared nodes."""
    edges = document.get("edges")
    if not isinstance(edges, list):
        assessment.note(slug, f"the wave plan's edges is not a JSON array (found {edges!r})")
        return
    for index, entry in enumerate(edges):
        if not isinstance(entry, dict) or tuple(sorted(entry)) != EDGE_KEYS:
            assessment.note(
                slug,
                f"the wave plan's edge at position {index} is not an object with exactly the keys "
                f"{list(EDGE_KEYS)} (found {entry!r})",
            )
            return
        for key in EDGE_KEYS:
            value = entry.get(key)
            if not isinstance(value, str) or not value:
                assessment.note(
                    slug,
                    f"the wave plan's edge at position {index} names {key}={value!r}, which is not a "
                    "non-empty node id",
                )
                return
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        return
    expected = derived_edges(nodes)
    if list(edges) != expected:
        assessment.note(
            slug,
            f"the wave plan's edges {list(edges)} are not the canonical edge set its nodes' "
            f"dependencies imply ({expected}), so the plan records two different graphs",
        )
        return
    known = set(identifiers)
    for edge in expected:
        for key in EDGE_KEYS:
            if edge[key] not in known:
                assessment.note(
                    slug,
                    f"the wave plan's edge {edge} names {edge[key]!r}, which is not a node this plan "
                    "declares, so the edge points outside the graph",
                )
                return


def check_diff(assessment: Assessment, document: dict[str, Any]) -> None:
    """The complete closed shape of a sealed plan-diff@1, read by `verify` and by the compiler itself."""
    keys = tuple(sorted(document))
    if keys != DIFF_SEALED_KEYS:
        missing = [name for name in DIFF_SEALED_KEYS if name not in document]
        extra = [name for name in keys if name not in DIFF_SEALED_KEYS]
        assessment.note(
            "closed-key-set",
            f"the plan diff is not the closed sealed key set {list(DIFF_SEALED_KEYS)}: missing "
            f"{missing}, unexpected {extra}",
        )
        return
    slug = "plan-diff-shape"
    if document.get("schema") != DIFF_SCHEMA:
        assessment.note(slug, f"the plan diff declares schema {document.get('schema')!r} rather than {DIFF_SCHEMA!r}")
    _instant(assessment, slug, document, "compiled_at", "the plan diff's compiled_at")
    _identifier(assessment, slug, document, "mission_id", "the plan diff's mission_id")
    plan_digest = _digest_value(assessment, slug, document.get("plan_digest"), "the plan diff's plan_digest")
    prior = document.get("prior_plan_digest")
    if prior is not None:
        prior = _digest_value(assessment, slug, prior, "the plan diff's prior_plan_digest")
    if plan_digest is not None and prior is not None and plan_digest == prior:
        # `compile --diff` refuses this pairing at synthesis time (see `run_diff`'s "provenance"
        # check), but a hand-sealed plan-diff@1 document reaches `verify` without ever going through
        # that synthesis, so the same refusal has to live here too.
        assessment.note(
            slug,
            f"the plan diff's plan_digest and prior_plan_digest are both {plan_digest}; one document "
            "is not two revisions, and a diff of a plan against itself would describe a plan "
            "superseding itself",
        )
    changes = document.get("changes")
    empty_reason = document.get("no_delta_reason")
    if not isinstance(changes, list):
        assessment.note(slug, f"the plan diff's changes is not a JSON array (found {changes!r})")
        return
    if not changes:
        if document.get("prior_plan_digest") is None:
            assessment.note(
                slug,
                "the plan diff names no prior plan and no changes; a first wave adds its whole graph, so "
                "there is no revision pair this emptiness could be about",
            )
            return
        if not isinstance(empty_reason, str) or not empty_reason:
            # An empty `changes` alone cannot tell "identical revisions" from "never computed", and a
            # consumer that bound the digest has no follow-up question to ask.
            assessment.note(
                slug,
                f"the plan diff records no changes and its no_delta_reason is {empty_reason!r}; an empty "
                "diff must SAY it is empty on purpose, because otherwise a diff that was never computed "
                "and two identical revisions are the same document",
            )
        return
    if empty_reason is not None:
        assessment.note(
            slug,
            f"the plan diff names {len(changes)} change(s) and also records the no_delta_reason "
            f"{empty_reason!r}, so it claims both a delta and no delta",
        )
    seen: list[tuple[str, str]] = []
    for index, entry in enumerate(changes):
        where = f"change at position {index}"
        if not isinstance(entry, dict):
            assessment.note(slug, f"the plan diff's {where} is not a JSON object (found {entry!r})")
            continue
        found = tuple(sorted(entry))
        if found != CHANGE_KEYS:
            missing = [name for name in CHANGE_KEYS if name not in entry]
            extra = [name for name in found if name not in CHANGE_KEYS]
            assessment.note(
                slug,
                f"the plan diff's {where} is not the closed key set {list(CHANGE_KEYS)}: missing "
                f"{missing}, unexpected {extra}",
            )
            continue
        kind = _member(assessment, slug, entry, "kind", CHANGE_KINDS, f"the plan diff's {where} kind")
        subject = _text(assessment, slug, entry, "subject", f"the plan diff's {where} subject")
        _text(assessment, slug, entry, "evidence", f"the plan diff's {where} evidence")
        _text(assessment, slug, entry, "consequence", f"the plan diff's {where} consequence")
        semantic = entry.get("semantic")
        if not isinstance(semantic, bool):
            # Issue 16 keeps semantic changes and mere reordering/prose separate, so this is the one
            # field a consumer reads to tell them apart and it may not be a truthy stand-in.
            assessment.note(
                slug,
                f"the plan diff's {where} semantic is not a JSON boolean (found {semantic!r}); whether "
                "a change alters meaning is the one thing this field records",
            )
        if kind is not None and subject is not None:
            seen.append((kind, subject))
        if kind in ("changed-node", "removed-edge", "removed-node") and document.get("prior_plan_digest") is None:
            assessment.note(
                slug,
                f"the plan diff's {where} is a {kind} while the diff names no prior plan; there is "
                "nothing for a first wave to have removed or changed",
            )
    if len(set(seen)) != len(seen):
        repeated = sorted({pair for pair in seen if seen.count(pair) > 1})
        assessment.note(
            slug,
            f"the plan diff records the (kind, subject) pair(s) {repeated} more than once, so one "
            "change is classified twice",
        )
    if seen != sorted(seen):
        assessment.note(
            slug,
            "the plan diff's changes are not ordered by (kind, subject), and an order this compiler "
            "did not derive would give one delta more than one digest",
        )


# ---- input admission -----------------------------------------------------------------------------


def check_limits_document(assessment: Assessment, document: dict[str, Any]) -> dict[str, int] | None:
    """Admit a supplied execution profile. It is POLICY, not a sealed planning artifact.

    So it carries no digest, and a `digest` key on it is refused as an unexpected key rather than
    silently ignored: a caller that sealed one would otherwise believe this tool checked a seal it
    never looked at.
    """
    slug = "execution-profile-limits"
    declared = document.get("schema")
    if declared != LIMITS_SCHEMA:
        assessment.note(
            slug,
            f"the execution profile declares schema {declared!r} rather than {LIMITS_SCHEMA!r}, so it "
            "is not the document kind --limits consumes",
        )
        return None
    expected = tuple(sorted(LIMITS_KEYS + ("schema",)))
    found = tuple(sorted(document))
    if found != expected:
        missing = [name for name in expected if name not in document]
        extra = [name for name in found if name not in expected]
        assessment.note(
            slug,
            f"the execution profile is not the closed key set {list(expected)}: missing {missing}, "
            f"unexpected {extra}; it is repository policy and carries no digest",
        )
        return None
    return _limit_values(assessment, slug, document, "the execution profile")


def check_output_path(
    assessment: Assessment, slug: str, option: str, out: str | None, snapshot: dict[str, Any] | None
) -> Path | None:
    """`--out`/`--diff-out` may not exist, need a real parent, and may not land in the snapshot's tree.

    Containment is measured against the repository the SNAPSHOT describes, because that is the tree
    this compilation is about: writing a plan into it would change the dirty state the snapshot
    already recorded, and the snapshot's own record of it would be wrong from the moment the file
    landed.
    """
    if out is None:
        return None
    target = Path(os.path.abspath(out))
    try:
        target.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        assessment.note(slug, f"the {option} path {target} cannot be inspected: {exc}")
        return None
    else:
        assessment.note(
            slug,
            f"the {option} path {target} already exists; this command overwrites nothing, so an "
            "occupied destination is refused rather than replaced",
        )
        return None
    parent = target.parent
    if not parent.is_dir():
        assessment.note(
            slug,
            f"the {option} path {target} has no existing directory to be written into, so the compiled "
            "document would have nowhere to land",
        )
        return None
    if snapshot is None:
        return target
    repository = snapshot.get("repository")
    if not isinstance(repository, dict):
        return target
    resolved = Path(os.path.realpath(str(parent)))
    for key in ("git_dir", "worktree_path"):
        value = repository.get(key)
        if not isinstance(value, str) or not value:
            continue
        observed = Path(os.path.realpath(value))
        if resolved == observed or observed in resolved.parents:
            assessment.note(
                slug,
                f"the {option} path {target} resolves inside the snapshot's observed {key} {observed}; "
                "writing a plan into the tree it plans over would change that tree's dirty state and "
                "make the snapshot's own record of it wrong",
            )
            return None
    return target


def admit_inputs(args: argparse.Namespace, assessment: Assessment) -> dict[str, Any]:
    """Read and admit every supplied document. Returns what a later phase will compile FROM.

    Unusable files raise `InputError` out of here (exit 2). Everything else -- a wrong schema string, a
    digest its content does not re-derive, a consumed field that is absent, a malformed submission --
    is a named reason against the input position it arrived in.
    """
    mission = load_document(args.mission, "mission contract")
    mission_digest = _sealed_input(
        assessment, "mission-contract", mission, MISSION_SCHEMA, None, "the mission contract"
    )
    _required_fields(assessment, "mission-contract", mission, MISSION_REQUIRED, "the mission contract")

    snapshot = load_document(args.snapshot, "planning snapshot")
    snapshot_digest = _sealed_input(
        assessment, "planning-snapshot", snapshot, SNAPSHOT_SCHEMA, None, "the planning snapshot"
    )
    _required_fields(assessment, "planning-snapshot", snapshot, SNAPSHOT_REQUIRED, "the planning snapshot")

    submissions = load_document(args.submissions, "workstream submissions")
    submissions_digest = _sealed_input(
        assessment,
        "workstream-submissions",
        submissions,
        SUBMISSIONS_SCHEMA,
        SUBMISSIONS_SEALED_KEYS,
        "the workstream submissions",
    )
    workstreams: list[dict[str, Any]] = []
    if submissions_digest is not None:
        workstreams = check_submissions(assessment, submissions)

    prior: dict[str, Any] | None = None
    prior_digest: str | None = None
    if args.prior_plan is not None:
        prior = load_document(args.prior_plan, "prior wave plan")
        prior_digest = _sealed_input(
            assessment, "prior-plan", prior, PLAN_SCHEMA, PLAN_SEALED_KEYS, "the prior wave plan"
        )
        if prior_digest is None:
            prior = None
        else:
            check_plan(assessment, prior, key_slug="prior-plan", slug="prior-plan")

    if args.limits is None:
        # The handoff's defaults, applied rather than guessed: four concurrent, 64 total, recursion off.
        limits: dict[str, int] | None = dict(DEFAULT_LIMITS)
    else:
        limits = check_limits_document(assessment, load_document(args.limits, "execution profile"))

    admitted_snapshot = snapshot if snapshot_digest is not None else None
    out = check_output_path(assessment, "output-path", "--out", args.out, admitted_snapshot)
    diff_out = check_output_path(assessment, "output-path", "--diff-out", args.diff_out, admitted_snapshot)
    if out is not None and diff_out is not None and out == diff_out:
        assessment.note(
            "output-path",
            f"--out and --diff-out name the same path {out}; the plan and its diff are two documents "
            "and one of them would have to overwrite the other",
        )
    return {
        "digests": {
            "mission_digest": mission_digest,
            "prior_plan_digest": prior_digest,
            "snapshot_digest": snapshot_digest,
            "submissions_digest": submissions_digest,
        },
        "limits": limits,
        "out": out,
        "diff_out": diff_out,
        "prior_plan_supplied": args.prior_plan is not None,
        "mission": mission,
        "snapshot": snapshot,
        "submissions": submissions,
        "prior_plan": prior,
        "workstreams": workstreams,
    }


# ---- the compiler checks -------------------------------------------------------------------------
# Each one runs ONLY over inputs that were admitted and over workstreams `check_submissions` found
# nothing wrong with, so one mistake produces one reason, in the group that names the property it
# violated rather than a single "compilation failed".


def pinned_to_one_mission(
    assessment: Assessment,
    slug: str,
    *,
    expected: str | None,
    plan: dict[str, Any] | None,
    what: str,
) -> None:
    """A plan being diffed must bind the SAME mission contract digest as the plan it is compared to.

    A diff across two missions is not a delta: its added and removed nodes would be two different
    plans' nodes rather than one plan's change, and a consumer binding that digest would read a
    revision chain that never existed. The consequence is deliberate -- revising the mission contract
    ends a plan chain instead of continuing it -- and `RESIDUALS` says so, because the alternative is a
    diff whose two halves answer to different authority, scope, and stop conditions.
    """
    if plan is None or expected is None:
        return
    inputs = plan.get("inputs")
    bound = inputs.get("mission_digest") if isinstance(inputs, dict) else None
    if bound == expected:
        return
    assessment.note(
        slug,
        f"{what} binds mission contract digest {bound!r} while this comparison's mission contract is "
        f"{expected}; a diff across two missions is not a delta, because the nodes on either side "
        "answer to different authority, scope, and stop conditions",
    )


def check_provenance(
    assessment: Assessment,
    mission: dict[str, Any],
    snapshot: dict[str, Any],
    submissions: dict[str, Any],
    *,
    prior: dict[str, Any] | None = None,
    mission_digest: str | None = None,
) -> dict[str, Any] | None:
    """The linkage between the three inputs, and the head the plan will carry VERBATIM.

    Returns the snapshot's head object to be copied unchanged into the plan, or None when it cannot be
    carried. Nothing here judges FRESHNESS: comparing a recorded head against the repository's current
    head needs a git observation, this tool makes none, and plan admission owns that comparison.
    """
    slug = "provenance"
    mission_id = mission.get("mission_id")
    submitted_for = submissions.get("mission_id")
    if isinstance(mission_id, str) and isinstance(submitted_for, str) and mission_id != submitted_for:
        assessment.note(
            slug,
            f"the workstream submissions name mission_id {submitted_for!r} while the mission contract is "
            f"{mission_id!r}, so the submissions were made for a different mission and the plan would "
            "bind two of them",
        )
    pinned_to_one_mission(
        assessment, slug, expected=mission_digest, plan=prior, what="the --prior-plan wave plan"
    )
    head = snapshot.get("head")
    if not isinstance(head, dict):
        assessment.note(
            slug,
            f"the planning snapshot's head is not a JSON object (found {head!r}), so the plan has no "
            "recorded head to carry",
        )
        return None
    found = tuple(sorted(head))
    if found != PLAN_HEAD_KEYS:
        assessment.note(
            slug,
            f"the planning snapshot's head is not the key set {list(PLAN_HEAD_KEYS)} (found "
            f"{list(found)}), so it cannot be carried verbatim: a subset would drop what a later "
            "admission gate compares, and an unknown key would be a meaning this plan cannot honour",
        )
        return None
    if _object_name(assessment, slug, head.get("commit_sha"), "the planning snapshot's head.commit_sha") is None:
        return None
    if _object_name(assessment, slug, head.get("tree_sha"), "the planning snapshot's head.tree_sha") is None:
        return None
    branch = head.get("branch")
    if branch is not None and (not isinstance(branch, str) or not branch):
        assessment.note(
            slug,
            f"the planning snapshot's head.branch is {branch!r}, which is neither a non-empty branch "
            "name nor null, so what the plan would carry is unreadable",
        )
        return None
    return dict(head)


def admitted_ladder(assessment: Assessment, mission: dict[str, Any]) -> tuple[list[str], str] | None:
    """The mission's authority ladder: an admitted PREFIX of the classes, and a ceiling inside it.

    A prefix rather than an arbitrary set, because the ladder is ordered: admitting `outward-effect`
    while refusing `owned-worktree-write` would describe an authority that can push but not write, and
    the mission contract does not mean that. Re-derived here rather than trusted, since a sibling's
    document is consumed for what this tool reads out of it.
    """
    slug = "authority-bounds"
    authority = mission.get("authority")
    if not isinstance(authority, dict):
        assessment.note(slug, f"the mission contract's authority is not a JSON object (found {authority!r})")
        return None
    admitted = authority.get("admitted_classes")
    if not isinstance(admitted, list) or not admitted or not all(isinstance(name, str) for name in admitted):
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes is not a non-empty array of strings "
            f"(found {admitted!r}), so no workstream's class can be placed inside it",
        )
        return None
    if list(admitted) != list(AUTHORITY_CLASSES[: len(admitted)]):
        assessment.note(
            slug,
            f"the mission contract admits the authority classes {list(admitted)}, which is not a prefix "
            f"of the ladder {list(AUTHORITY_CLASSES)}; the ladder is ordered, so a gap in it would admit "
            "a wider authority while refusing a narrower one",
        )
        return None
    ceiling = authority.get("ceiling")
    if not isinstance(ceiling, str) or ceiling not in admitted:
        assessment.note(
            slug,
            f"the mission contract's authority.ceiling {ceiling!r} is not one of the classes it admits "
            f"({list(admitted)}), so what the mission's own limit is cannot be read",
        )
        return None
    return list(admitted), ceiling


def check_authority(assessment: Assessment, mission: dict[str, Any], workstreams: list[dict[str, Any]]) -> None:
    """Every workstream's class inside the admitted prefix and at or below the mission's ceiling."""
    slug = "authority-bounds"
    ladder = admitted_ladder(assessment, mission)
    if ladder is None:
        return
    admitted, ceiling = ladder
    limit = AUTHORITY_CLASSES.index(ceiling)
    for entry in workstreams:
        identifier = entry["id"]
        declared = entry["authority_class"]
        if declared not in admitted:
            assessment.note(
                slug,
                f"workstream {identifier!r} declares authority class {declared!r}, which this mission "
                f"does not admit ({list(admitted)}); a wave cannot grant an authority its mission never "
                "did",
            )
            continue
        if AUTHORITY_CLASSES.index(declared) > limit:
            assessment.note(
                slug,
                f"workstream {identifier!r} declares authority class {declared!r}, which is above the "
                f"mission's ceiling {ceiling!r}; raising the ceiling is a mission-contract revision, not "
                "a compilation",
            )


def check_graph(assessment: Assessment, workstreams: list[dict[str, Any]]) -> None:
    """Dependencies that resolve, no self-dependency, and one acyclic graph -- walked ITERATIVELY.

    The acyclicity walk is Kahn's algorithm over an explicit queue. A recursive depth-first walk would
    trade a named refusal for a `RecursionError` on a long chain, which is a perfectly legitimate plan
    shape: a 5000-node dependency chain is acyclic and must compile, not crash.
    """
    slug = "graph"
    known = {entry["id"] for entry in workstreams}
    dependencies: dict[str, list[str]] = {}
    for entry in workstreams:
        identifier = entry["id"]
        resolved: list[str] = []
        for dependency in entry["dependencies"]:
            if dependency == identifier:
                assessment.note(
                    slug,
                    f"workstream {identifier!r} declares itself as its own dependency, so it could never "
                    "become ready",
                )
                continue
            if dependency not in known:
                assessment.note(
                    slug,
                    f"workstream {identifier!r} depends on {dependency!r}, which these submissions do "
                    "not declare; a dependency on a workstream nobody submitted can never be satisfied",
                )
                continue
            resolved.append(dependency)
        dependencies[identifier] = resolved
    outstanding = {identifier: len(deps) for identifier, deps in dependencies.items()}
    dependents: dict[str, list[str]] = {identifier: [] for identifier in dependencies}
    for identifier, deps in dependencies.items():
        for dependency in deps:
            dependents[dependency].append(identifier)
    ready = [identifier for identifier, count in sorted(outstanding.items()) if count == 0]
    settled = 0
    while ready:
        identifier = ready.pop()
        settled += 1
        for dependent in dependents[identifier]:
            outstanding[dependent] -= 1
            if outstanding[dependent] == 0:
                ready.append(dependent)
    if settled != len(dependencies):
        cyclic = sorted(identifier for identifier, count in outstanding.items() if count > 0)
        assessment.note(
            slug,
            f"the submitted dependencies are cyclic: the workstream(s) {cyclic} can never become ready "
            "because each waits on another in the same cycle, so this is not one wave's executable graph",
        )


def check_custody(assessment: Assessment, workstreams: list[dict[str, Any]]) -> None:
    """Custody is EXCLUSIVE: one owner per worktree, and no two nodes claiming overlapping files.

    Overlap is not just equality. A claim on `src` and a claim on `src/app.py` are the same custody
    argued at two depths, and two nodes writing under one directory is exactly the concurrent-write
    collision worktree isolation exists to prevent. Ancestors are looked up rather than compared
    pairwise: a proper string prefix always sorts before what it contains, so walking the claims in
    sorted order means every containing directory is already recorded when its contents arrive.
    """
    slug = "custody-exclusivity"
    for kind, key in (("worktree", "worktree_custody"), ("file", "file_custody")):
        claims: list[tuple[str, str]] = []
        for entry in workstreams:
            declared = entry[key]
            if key == "worktree_custody":
                if isinstance(declared, str):
                    claims.append((declared, entry["id"]))
                continue
            claims.extend((path, entry["id"]) for path in declared)
        owners: dict[str, str] = {}
        for path, owner in sorted(claims):
            held = owners.get(path)
            if held is not None and held != owner:
                assessment.note(
                    slug,
                    f"workstreams {held!r} and {owner!r} both claim {kind} custody of {path!r}; custody "
                    "is exclusive, so one of the two would be writing inside the other's boundary",
                )
                continue
            segments = path.split("/")
            for depth in range(1, len(segments)):
                ancestor = "/".join(segments[:depth])
                container = owners.get(ancestor)
                if container is not None and container != owner:
                    assessment.note(
                        slug,
                        f"workstream {owner!r} claims {kind} custody of {path!r}, which is inside "
                        f"{ancestor!r} already claimed by {container!r}; a directory's owner owns what "
                        "is under it, so the two claims are the same custody at two depths",
                    )
                    break
            owners.setdefault(path, owner)


def check_capabilities(
    assessment: Assessment, snapshot: dict[str, Any], workstreams: list[dict[str, Any]]
) -> None:
    """Every demand the snapshot can speak to must be an OBSERVED capability, not an assumed one.

    Only `host_capabilities.{git,python,uv}` are observed by a PlanningSnapshot, so only the demands
    that map onto one of them can be found infeasible here. A capability the snapshot listed among its
    named unknowns is refused as well: an unobserved capability is not an available one, and issue 16
    stops compilation on unsupported capability rather than planning around it.
    """
    slug = "capability-feasibility"
    capabilities = snapshot.get("host_capabilities")
    if not isinstance(capabilities, dict):
        assessment.note(
            slug,
            f"the planning snapshot's host_capabilities is not a JSON object (found {capabilities!r}), "
            "so no demand can be checked against an observation",
        )
        return
    unknown_dimensions: set[str] = set()
    unknowns = snapshot.get("unknowns")
    if isinstance(unknowns, list):
        for entry in unknowns:
            if isinstance(entry, dict) and isinstance(entry.get("dimension"), str):
                unknown_dimensions.add(entry["dimension"])
    for entry in workstreams:
        identifier = entry["id"]
        for demand in entry["capability_demands"]:
            name = DEMAND_CAPABILITY.get(demand)
            if name is None:
                continue
            dimension = f"host_capabilities.{name}"
            if dimension in unknown_dimensions:
                assessment.note(
                    slug,
                    f"workstream {identifier!r} demands {demand!r}, and the planning snapshot names "
                    f"{dimension} among its own unknowns; an unobserved capability is not an available "
                    "one",
                )
                continue
            if capabilities.get(name) is None:
                assessment.note(
                    slug,
                    f"workstream {identifier!r} demands {demand!r}, and the planning snapshot observed "
                    f"no {dimension} on this host; a node cannot be planned onto a capability that is "
                    "not there",
                )


def check_bounds(
    assessment: Assessment, workstreams: list[dict[str, Any]], limits: dict[str, int], concurrency: int | None
) -> None:
    """The two closed resource bounds: how many nodes this wave may hold, and how many may run at once."""
    slug = "resource-bounds"
    if len(workstreams) > limits["max_total_nodes"]:
        assessment.note(
            slug,
            f"the submissions propose {len(workstreams)} workstreams against the admitted ceiling of "
            f"{limits['max_total_nodes']} total nodes; raising the ceiling is an execution-profile "
            "decision, not a compilation",
        )
    if concurrency is not None and concurrency > limits["max_concurrent_nodes"]:
        assessment.note(
            slug,
            f"the submissions declare {concurrency} concurrent workstreams against the admitted ceiling "
            f"of {limits['max_concurrent_nodes']}; a wave cannot widen its own concurrency",
        )


#: What `inputs_admitted` is derived from. `output-path` is deliberately NOT here: a destination this
#: command refuses says nothing about whether the documents it read were admissible, and conflating
#: the two would hide an admitted input set behind an occupied `--out`.
INPUT_SLUGS = (
    "mission-contract",
    "planning-snapshot",
    "workstream-submissions",
    "prior-plan",
    "execution-profile-limits",
)


# ---- synthesis -----------------------------------------------------------------------------------
# The plan is DERIVED from admitted submissions, never copied from them: a submitter states what it
# wants to do and what it wants custody of, and this file decides what document that becomes.


#: The node fields whose change alters no meaning. Issue 16 keeps "reordering or prose changes that do
#: not alter semantics" separate, and reordering is unrepresentable here -- every list in a plan has one
#: canonical order -- so prose is the whole non-semantic category.
PROSE_NODE_KEYS = ("objective",)


def derive_wrong_output_class(authority_class: str, has_dependents: bool) -> str:
    """A node's blast radius, DERIVED from its authority and its position in the graph.

    An advisory node writes nothing, so the damage its wrong output can do is entirely a function of
    who reads it: with a dependent, a wrong map or wrong recommendation steers every node downstream
    (`derail`); with none, nothing consumes it and re-running is the whole cost (`retry`). Every other
    class has a radius fixed by its authority. Derived rather than submitted, because a submitter
    grading its own blast radius is how a `derail` gets planned as a `retry`.
    """
    fixed = AUTHORITY_WRONG_OUTPUT.get(authority_class)
    if fixed is not None:
        return fixed
    return "derail" if has_dependents else "retry"


def synthesize_nodes(workstreams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One node per admitted workstream, ordered by node id, with custody carried per workstream.

    The node id is the submitted workstream id VERBATIM. A derived name would have to be collision-free
    against every other derived name, and it would break the one traceable link between the submission a
    role made and the node a reviewer reads.
    """
    depended_on: set[str] = set()
    for entry in workstreams:
        depended_on.update(dependency for dependency in entry["dependencies"] if dependency != entry["id"])
    nodes: list[dict[str, Any]] = []
    for entry in workstreams:
        identifier = entry["id"]
        authority_class = entry["authority_class"]
        nodes.append(
            {
                "node_id": identifier,
                "objective": entry["objective"],
                "authority_class": authority_class,
                "capability_demands": list(entry["capability_demands"]),
                "dependencies": sorted(
                    dependency for dependency in entry["dependencies"] if dependency != identifier
                ),
                "file_custody": list(entry["file_custody"]),
                "worktree_custody": entry["worktree_custody"],
                "output_schema": AUTHORITY_OUTPUT_SCHEMA[authority_class],
                "wrong_output_class": derive_wrong_output_class(authority_class, identifier in depended_on),
            }
        )
    return sorted(nodes, key=lambda node: node["node_id"])


def seal_document(body: dict[str, Any]) -> dict[str, Any]:
    """Add the one derived key. The digest has exactly one origin, and it is this function."""
    sealed = dict(body)
    sealed[DIGEST_KEY] = document_digest(body)
    return sealed


def synthesize_plan(
    *,
    at: str,
    mission_id: str,
    head: dict[str, Any],
    limits: dict[str, int],
    concurrency: int,
    digests: dict[str, str | None],
    nodes: list[dict[str, Any]],
    prior: dict[str, Any] | None,
) -> dict[str, Any]:
    """The sealed WavePlan. A revision NEVER edits its predecessor: it names it and takes the next number."""
    revision = 1
    supersedes = None
    if prior is not None:
        recorded = prior.get("revision")
        revision = (recorded if isinstance(recorded, int) and not isinstance(recorded, bool) else 0) + 1
        supersedes = prior.get(DIGEST_KEY)
    body = {
        "schema": PLAN_SCHEMA,
        "compiled_at": at,
        "mission_id": mission_id,
        "revision": revision,
        "supersedes": supersedes,
        "head": dict(head),
        "declared_concurrency": concurrency,
        "inputs": {
            "mission_digest": digests["mission_digest"],
            "snapshot_digest": digests["snapshot_digest"],
            "submissions_digest": digests["submissions_digest"],
        },
        "limits": dict(limits),
        "nodes": nodes,
        "edges": derived_edges(nodes),
    }
    return seal_document(body)


def _change(kind: str, subject: str, evidence: str, consequence: str, *, semantic: bool) -> dict[str, Any]:
    return {
        "kind": kind,
        "subject": subject,
        "evidence": evidence,
        "consequence": consequence,
        "semantic": semantic,
    }


def _nodes_by_id(document: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if document is None:
        return {}
    nodes = document.get("nodes")
    if not isinstance(nodes, list):
        return {}
    return {node["node_id"]: node for node in nodes if isinstance(node, dict) and isinstance(node.get("node_id"), str)}


def _custody_owners(nodes: dict[str, dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Every custody boundary a plan draws, as path -> (kind, owning node).

    ONE path can be held twice, in exactly one way: a file claim equal to another node's worktree claim,
    which `check_custody` compares within each kind and `RESIDUALS` declares as its limit. The later
    writer wins, and which node that is is DETERMINED rather than incidental -- a plan's `nodes` array is
    required to ascend by `node_id`, so this mapping's insertion order IS sorted order and the greater
    node id owns the path in every process. A `sorted()` here was tried and removed: it could not change
    any output the ascending-order rule admits, so the rule is the guard and this comment is the record.
    """
    owners: dict[str, tuple[str, str]] = {}
    for node_id, node in nodes.items():
        worktree = node.get("worktree_custody")
        if isinstance(worktree, str):
            owners[worktree] = ("worktree", node_id)
        custody = node.get("file_custody")
        if isinstance(custody, list):
            for path in custody:
                if isinstance(path, str):
                    owners[path] = ("file", node_id)
    return owners


def _edges_of(document: dict[str, Any] | None) -> set[tuple[str, str]]:
    if document is None:
        return set()
    edges = document.get("edges")
    if not isinstance(edges, list):
        return set()
    return {
        (edge["from"], edge["to"])
        for edge in edges
        if isinstance(edge, dict) and isinstance(edge.get("from"), str) and isinstance(edge.get("to"), str)
    }


def synthesize_changes(plan: dict[str, Any], prior: dict[str, Any] | None) -> list[dict[str, Any]]:
    """The delta this schema can name: nodes, edges, custody boundaries, and authorities.

    A first wave's diff is the delta from NO prior plan -- its whole graph added -- rather than an
    omitted document, because issue 16 makes the diff inseparable from the revision. Ordered by
    `(kind, subject)`, which is the only order this compiler derives, so one delta has one digest.

    THE FINAL SORT IS THE DETERMINISM GUARD. `(kind, subject)` pairs are unique -- `check_diff` refuses a
    repeated one -- so that one call totally orders the array whatever order the walks below iterated in.
    The `sorted(...)` calls inside are the same convention applied early; neutralizing one of them
    changes no emitted byte, which is exactly why the return value is where the guarantee lives.
    """
    changes: list[dict[str, Any]] = []
    current = _nodes_by_id(plan)
    previous = _nodes_by_id(prior)
    for node_id in sorted(set(current) - set(previous)):
        node = current[node_id]
        changes.append(
            _change(
                "added-node",
                node_id,
                f"an admitted workstream declaring authority class {node['authority_class']!r} and "
                f"capability demands {node['capability_demands']}",
                f"one {node['wrong_output_class']}-class node enters this wave and may do no more than "
                f"{node['authority_class']!r} permits",
                semantic=True,
            )
        )
    for node_id in sorted(set(previous) - set(current)):
        changes.append(
            _change(
                "removed-node",
                node_id,
                "the prior revision declared this node and these submissions do not",
                "the node leaves the wave, and whatever custody it held is released",
                semantic=True,
            )
        )
    for node_id in sorted(set(current) & set(previous)):
        node, before = current[node_id], previous[node_id]
        differing = sorted(key for key in NODE_KEYS if node.get(key) != before.get(key))
        if differing:
            changes.append(
                _change(
                    "changed-node",
                    node_id,
                    f"the fields {differing} differ from the prior revision's node",
                    "the node is replaced in this revision; the prior revision is superseded, never edited",
                    semantic=any(key not in PROSE_NODE_KEYS for key in differing),
                )
            )
    for node_id in sorted(current):
        node = current[node_id]
        before = previous.get(node_id)
        if before is None or before.get("authority_class") != node["authority_class"]:
            changes.append(
                _change(
                    "authority",
                    node_id,
                    f"the node's admitted authority class is {node['authority_class']!r}"
                    + ("" if before is None else f", where the prior revision had {before.get('authority_class')!r}"),
                    "the node may take no action outside that class, and raising it is a mission-contract "
                    "revision rather than a compilation",
                    semantic=True,
                )
            )
    held, released = _custody_owners(current), _custody_owners(previous)
    for path in sorted(set(held) | set(released)):
        now, before = held.get(path), released.get(path)
        if now == before:
            continue
        if now is None:
            evidence = f"the prior revision gave {before[1]!r} {before[0]} custody of it and no node claims it now"
            consequence = "the boundary is released, so no node in this wave may write that path"
        elif before is None:
            evidence = f"declared {now[0]} custody of node {now[1]!r}"
            consequence = f"no node other than {now[1]!r} may write inside that boundary"
        else:
            evidence = f"{now[0]} custody moves from node {before[1]!r} to node {now[1]!r}"
            consequence = f"the previous owner loses write access to it and {now[1]!r} gains it"
        changes.append(_change("custody-boundary", path, evidence, consequence, semantic=True))
    for edge in sorted(_edges_of(plan) - _edges_of(prior)):
        changes.append(
            _change(
                "added-edge",
                f"{edge[0]} -> {edge[1]}",
                f"node {edge[1]!r} declares {edge[0]!r} among its dependencies",
                f"{edge[1]!r} may not start until {edge[0]!r} has produced its output",
                semantic=True,
            )
        )
    for edge in sorted(_edges_of(prior) - _edges_of(plan)):
        changes.append(
            _change(
                "removed-edge",
                f"{edge[0]} -> {edge[1]}",
                "the prior revision ordered these two nodes and this revision does not",
                f"{edge[1]!r} no longer waits on {edge[0]!r}, so the two may run concurrently",
                semantic=True,
            )
        )
    return sorted(changes, key=lambda entry: (entry["kind"], entry["subject"]))


def synthesize_diff(
    *, at: str, mission_id: str, plan: dict[str, Any], prior: dict[str, Any] | None, changes: list[dict[str, Any]]
) -> dict[str, Any]:
    """The sealed PlanDiff, bound to the exact plan digest it describes.

    `no_delta_reason` is derived from the changes rather than passed in, so the two fields cannot be
    sealed disagreeing with each other in the one place that writes both.
    """
    body = {
        "schema": DIFF_SCHEMA,
        "compiled_at": at,
        "mission_id": mission_id,
        "plan_digest": plan[DIGEST_KEY],
        "prior_plan_digest": None if prior is None else prior.get(DIGEST_KEY),
        "changes": changes,
        "no_delta_reason": None if changes else NO_DELTA,
    }
    return seal_document(body)


def compile_wave(
    args: argparse.Namespace, assessment: Assessment, admitted: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Run the six compiler checks, then seal the plan and its diff. Returns (plan, diff) or (None, None).

    Every check runs before any of them decides the outcome, so one compilation reports every property
    it violated rather than the first. Nothing is sealed while a single reason stands: a document
    carrying this family's digest is what a later admission gate binds, and a plan that failed a check
    must not be bindable at all.
    """
    mission = admitted["mission"]
    snapshot = admitted["snapshot"]
    submissions = admitted["submissions"]
    workstreams = admitted["workstreams"]
    limits = admitted["limits"]
    prior = admitted["prior_plan"]
    head = check_provenance(
        assessment,
        mission,
        snapshot,
        submissions,
        prior=prior,
        mission_digest=admitted["digests"]["mission_digest"],
    )
    check_authority(assessment, mission, workstreams)
    check_graph(assessment, workstreams)
    check_custody(assessment, workstreams)
    check_capabilities(assessment, snapshot, workstreams)
    concurrency = submissions.get("declared_concurrency")
    if not isinstance(concurrency, int) or isinstance(concurrency, bool):
        concurrency = None
    if limits is not None:
        check_bounds(assessment, workstreams, limits, concurrency)
    if any(assessment.groups[slug] for slug in COMPILER_CHECKS):
        return None, None
    if head is None or limits is None or concurrency is None or not workstreams:
        # Defence in depth against this module's own worst failure: sealing a plan out of inputs a check
        # above declined to admit. Reaching here means a check returned nothing AND noted no reason.
        assessment.note(
            "provenance",
            "the compiler checks passed but the values a plan is built from are not all present, so no "
            "WavePlan was sealed; this is a defect in this tool rather than in the supplied inputs",
        )
        return None, None
    mission_id = mission.get("mission_id")
    if not isinstance(mission_id, str):
        assessment.note("provenance", f"the mission contract's mission_id is not a string (found {mission_id!r})")
        return None, None
    plan = synthesize_plan(
        at=args.at,
        mission_id=mission_id,
        head=head,
        limits=limits,
        concurrency=concurrency,
        digests=admitted["digests"],
        nodes=synthesize_nodes(workstreams),
        prior=prior,
    )
    changes = synthesize_changes(plan, prior)
    if not changes:
        assessment.note(
            "provenance",
            "these submissions imply exactly the plan the prior revision already records, so there is no "
            "delta to name; a revision that changes nothing is not a revision",
        )
        return None, None
    diff = synthesize_diff(at=args.at, mission_id=mission_id, plan=plan, prior=prior, changes=changes)
    # ONE SCHEMA, ONE VALIDATOR: the derived documents are read back through the same closed checks
    # `verify` runs, so a synthesis bug becomes a refusal rather than a sealed document `verify` would
    # later reject.
    check_plan(assessment, plan)
    check_diff(assessment, diff)
    if assessment.reasons():
        return None, None
    return plan, diff


def derive_diff(
    args: argparse.Namespace, assessment: Assessment
) -> tuple[dict[str, Any] | None, dict[str, str | None]]:
    """Re-derive the PlanDiff between two ALREADY SEALED revisions. Returns (diff, the digests it bound).

    Both documents are admitted the same way `compile` admits a `--prior-plan` -- declared schema,
    closed sealed key set, re-derived digest, then the whole wave-plan shape -- but into two SEPARATE
    reported groups, so a caller learns which of its two plans was the malformed one.

    Unlike `compile`, an empty delta is an ANSWER here rather than a refusal: "what changed between
    these two revisions" is true when nothing did, and the emitted document says so by name in
    `no_delta_reason` instead of leaving a consumer to read an empty array. What stays refused is the
    same sealed document supplied as both revisions, which would describe a plan superseding itself.
    """
    digests: dict[str, str | None] = {"mission_digest": None, "plan_digest": None, "prior_plan_digest": None}
    plan = load_document(args.plan, "wave plan")
    plan_digest = _sealed_input(assessment, "plan", plan, PLAN_SCHEMA, PLAN_SEALED_KEYS, "the wave plan")
    if plan_digest is not None:
        check_plan(assessment, plan, key_slug="plan", slug="plan")
    prior = load_document(args.prior_plan, "prior wave plan")
    prior_digest = _sealed_input(
        assessment, "prior-plan", prior, PLAN_SCHEMA, PLAN_SEALED_KEYS, "the prior wave plan"
    )
    if prior_digest is not None:
        check_plan(assessment, prior, key_slug="prior-plan", slug="prior-plan")
    if any(assessment.groups[slug] for slug in DIFF_INPUT_SLUGS):
        # The provenance and delta below read fields whose own refusals are already recorded; running
        # them anyway would print a second reason about one mistake.
        return None, digests
    slug = "provenance"
    inputs = plan.get("inputs")
    bound = inputs.get("mission_digest") if isinstance(inputs, dict) else None
    digests = {
        "mission_digest": bound if isinstance(bound, str) else None,
        "plan_digest": plan_digest,
        "prior_plan_digest": prior_digest,
    }
    mission_id = plan.get("mission_id")
    if mission_id != prior.get("mission_id"):
        assessment.note(
            slug,
            f"the two plans name mission_id {mission_id!r} and {prior.get('mission_id')!r}; a diff across "
            "two missions is not a delta between two revisions of one plan",
        )
    pinned_to_one_mission(
        assessment, slug, expected=digests["mission_digest"], plan=prior, what="the --prior-plan wave plan"
    )
    if plan_digest == prior_digest:
        assessment.note(
            slug,
            f"both --plan and --prior-plan are the sealed plan {plan_digest}; one document is not two "
            "revisions, and a diff of it against itself would describe a plan superseding itself",
        )
    if assessment.groups[slug]:
        return None, digests
    if not isinstance(mission_id, str):
        # Defence in depth: `check_plan` admitted the shape above, so an unusable mission_id here is a
        # defect in this module rather than in either supplied document.
        assessment.note(slug, f"the wave plan's mission_id is not a string (found {mission_id!r})")
        return None, digests
    diff = synthesize_diff(
        at=args.at,
        mission_id=mission_id,
        plan=plan,
        prior=prior,
        changes=synthesize_changes(plan, prior),
    )
    # Read back through the SAME closed shape `verify --diff` runs, so a synthesis bug is a refusal here
    # rather than a sealed document a later `verify` would reject.
    check_diff(assessment, diff)
    if assessment.reasons():
        return None, digests
    return diff, digests


def check_digest(assessment: Assessment, document: dict[str, Any], expect: str | None) -> str | None:
    """Re-derive the one digest of a sealed document under `verify`. Only `verify` reaches this.

    A recorded digest its own content does not re-derive is a refusal, and `--expect-digest` is
    compared against the DERIVED value rather than the recorded one, so a document that recorded a
    convenient digest cannot satisfy a caller's binding.
    """
    slug = "digest"
    recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the document's recorded digest")
    derived = document_digest(document)
    if recorded is not None and recorded != derived:
        assessment.note(
            slug,
            f"the document records digest {recorded} which its own content does not re-derive "
            f"({derived}): it has been edited since it was sealed, or the digest was written by "
            "something other than this family's derivation",
        )
    if expect is not None and expect != derived:
        assessment.note(
            slug,
            f"--expect-digest {expect} is not this document's content digest {derived}, so the supplied "
            "document is not the one the caller meant to bind",
        )
    return derived


def derive_command(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Path | None]]:
    """Compile one wave (`compile`), diff two sealed revisions (`diff`), or re-derive one (`verify`).

    Returns the one result document together with the destinations a compiled pair is to be written to,
    which are kept OUT of the result until the write has actually happened. Only `compile` has
    destinations: `diff` publishes its one document in the result and writes no file.
    """
    command = args.command
    plan: dict[str, Any] | None = None
    diff: dict[str, Any] | None = None
    digest: str | None = None
    document: dict[str, Any] | None = None
    admitted: dict[str, Any] = {}
    derived: tuple[dict[str, Any] | None, dict[str, Any] | None] = (None, None)
    diff_digests: dict[str, str | None] | None = None
    if command == "compile":
        assessment = Assessment(COMPILE_CHECKS)
        admitted = admit_inputs(args, assessment)
        if not any(assessment.groups[slug] for slug in INPUT_SLUGS):
            # The compiler checks run only over ADMITTED inputs: a check reading a field whose own
            # refusal is already recorded would print a second reason about one mistake, and a check
            # reading a field that is missing would be reasoning about nothing.
            derived = compile_wave(args, assessment, admitted)
    elif command == "diff":
        assessment = Assessment(DIFF_COMMAND_CHECKS)
        standalone, diff_digests = derive_diff(args, assessment)
        derived = (None, standalone)
    else:
        which = "plan" if args.plan is not None else "diff"
        assessment = Assessment(PLAN_VERIFY_CHECKS if which == "plan" else DIFF_VERIFY_CHECKS)
        document = load_document(args.plan or args.diff, f"wave {which}" if which == "plan" else "plan diff")
        if which == "plan":
            check_plan(assessment, document)
        else:
            check_diff(assessment, document)
        digest = check_digest(assessment, document, args.expect_digest)

    verdict = assessment.verdict(command)
    plan_digest: str | None = None
    diff_digest: str | None = None
    if command == "verify" and verdict == VERDICT_VERIFIED and document is not None:
        # Republished ONLY for an admitted document, and from the ALREADY LOADED bytes: a refusal
        # publishes none of it, so no consumer can read a partially admitted plan or diff out of a
        # refusal, and a second read could publish a document this run never checked.
        if args.plan is not None:
            plan, plan_digest = document, digest
        else:
            diff, diff_digest = document, digest
    elif verdict == VERDICT_COMPILED:
        # Published only for a `compiled` verdict, so a refusal never hands a consumer a plan that
        # failed a check and could still be bound by its digest. `diff` seals one document rather than
        # two, so each digest follows its own document rather than the pair.
        plan, diff = derived
        if plan is not None:
            plan_digest = plan[DIGEST_KEY]
        if diff is not None:
            diff_digest = diff[DIGEST_KEY]
    inputs_admitted: bool | None = None
    digests: dict[str, str | None] | None = None
    if command == "compile":
        inputs_admitted = not any(assessment.groups[slug] for slug in INPUT_SLUGS)
        digests = admitted.get("digests") if inputs_admitted else None
    elif command == "diff":
        inputs_admitted = not any(assessment.groups[slug] for slug in DIFF_INPUT_SLUGS)
        digests = diff_digests if inputs_admitted else None
    targets: dict[str, Path | None] = {"out": None, "diff_out": None}
    if plan is not None and diff is not None and command == "compile":
        targets = {"out": admitted.get("out"), "diff_out": admitted.get("diff_out")}
    result = {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "inputs_admitted": inputs_admitted,
        "inputs": digests,
        "limits": admitted.get("limits") if inputs_admitted else None,
        "plan": plan,
        "diff": diff,
        "plan_digest": plan_digest,
        "diff_digest": diff_digest,
        # Filled in by `deliver_documents` with what was ACTUALLY written, so a null here always means
        # no file of this run's making exists.
        "out": None,
        "diff_out": None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }
    return result, targets


# ---- delivery ------------------------------------------------------------------------------------


def abandon_broken_stream(name: str, stream: object) -> None:
    """Stop the interpreter retrying a write this process has ALREADY reported as failed.

    Catching the failed write is not enough: the bytes stay PENDING in the stream's buffer and CPython
    flushes `sys.stdout`/`sys.stderr` once more while finalizing; that second failure replaces the
    process exit code with 120, which is outside this module's closed exit set. Dropping the module
    attribute is how CPython itself represents a stream this process does not have (`2>&-` starts the
    interpreter with `sys.stderr is None`), and it loses no byte the failed write had not already lost.
    The identity check is load-bearing because `main` is importable: only the stream that actually
    failed may be dropped, never a caller's replacement.
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
    advisory_stderr()(f"wave-plan-compiler.py: {message}\n")


#: The three outcomes of one exclusive write, kept apart because they have different consequences: a
#: file that was never created leaves nothing behind, while one created and then not finished is an
#: admitted partial effect a consumer must be told about by name.
WRITE_DONE = "written"
WRITE_NOTHING = "nothing-created"
WRITE_PARTIAL = "created-but-incomplete"


def write_document(target: Path, document: dict[str, Any], option: str) -> str:
    """Write one sealed document to a fresh path, or say exactly what was left behind.

    `O_EXCL` is the enforcement; the earlier existence check is only so a caller learns about an
    occupied destination before anything is derived. A racer that created the path in between is
    therefore refused here rather than clobbered.
    """
    payload = canonical_bytes(document)
    try:
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as exc:
        report_input_error(
            f"cannot create the {option} path {target}: {exc}; the document was derived and nothing was "
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
            f"cannot write the {option} path {target}: {exc}; that path now exists and may be "
            "incomplete, so treat it as unusable evidence rather than as this run's document"
        )
        return WRITE_PARTIAL
    return WRITE_DONE


def deliver_documents(result: dict[str, Any], targets: dict[str, Path | None]) -> int:
    """Write the compiled pair, in the order a consumer reads them, and classify any failure.

    The plan goes first: the diff names the plan's digest, so a diff file beside no plan file would
    point at a document that does not exist. A plan that could not be created at all stops the pair --
    there is no half-delivery worth leaving on disk -- and the result document still carries both
    documents, so nothing is lost but the files.
    """
    plan, diff = result.get("plan"), result.get("diff")
    if plan is None or diff is None:
        return EXIT_OK
    code = EXIT_OK
    out = targets.get("out")
    if out is not None:
        state = write_document(out, plan, "--out")
        if state == WRITE_DONE:
            result["out"] = str(out)
        else:
            return EXIT_INTERNAL if state == WRITE_NOTHING else EXIT_PARTIAL
    diff_out = targets.get("diff_out")
    if diff_out is not None:
        state = write_document(diff_out, diff, "--diff-out")
        if state == WRITE_DONE:
            result["diff_out"] = str(diff_out)
        elif result["out"] is None:
            code = EXIT_INTERNAL if state == WRITE_NOTHING else EXIT_PARTIAL
        else:
            # The plan file is already on disk, so whatever happened to the diff, this run has left an
            # effect behind and says so with the code reserved for exactly that.
            report_input_error(
                f"the compiled plan was written to {result['out']} and its diff was not, so the pair on "
                "disk is incomplete; neither file is this run's delivered evidence"
            )
            code = EXIT_PARTIAL
    return code


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
    result document lives. And argparse swallows a failed write while leaving its bytes pending, which
    is enough for the shutdown flush to replace the usage error's 2 with 120.
    """

    def _print_message(self, message: str, file: Any = None) -> None:
        if not message:
            return
        if file is None:
            # argparse resolved `sys.stderr`/`sys.stdout` itself and got None: this process was handed
            # no such stream, so the line is dropped rather than redirected onto the other.
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
    "Exit codes: 0 a result was derived, a named refusal included; 2 a supplied file cannot be read as "
    "one JSON object, or the arguments themselves are unusable; 1 a derived result that could not be "
    "delivered, because an answer that did not arrive is not a success; 4 a document was derived and a "
    "file this run created was left incomplete or unpaired, which is an admitted partial effect. "
    "Implementation Decision 9's 3 does not apply: a refusal happens before anything is written, so it "
    "is a result rather than a clean refusal before effect."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="wave-plan-compiler.py",
        description=(
            "Compile, diff, and verify the WavePlan and its PlanDiff -- the third and fourth links in "
            "the planning artifact chain MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> "
            "AutoEnvelope. Read-only, offline, clock-free, and subprocess-free: it calls no model, "
            "resolves no runtime route, reads no environment variable, and authorizes nothing. "
            "Identical inputs seal byte-identical documents."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    compile_command = commands.add_parser(
        "compile",
        description=(
            "Admit the MissionContract, PlanningSnapshot, workstream submissions, optional prior plan, "
            "and execution-profile limits, then check provenance, authority bounds, graph acyclicity and "
            "dependencies, custody exclusivity, capability feasibility, and the closed resource bounds, "
            "and seal one WavePlan together with its PlanDiff. Any violated property is a named refusal "
            "and nothing is sealed. A compiled plan is evidence; it authorizes no node and no effect."
        ),
        epilog=EPILOG,
    )
    diff_command = commands.add_parser(
        "diff",
        description=(
            "Re-derive the PlanDiff between two SEALED wave-plan@1 revisions, which is the question a "
            "gate holding two documents already has. Both plans must bind the same mission contract "
            "digest, and the same sealed document supplied twice is refused. Two identical revisions "
            "yield an EXPLICITLY empty diff whose no_delta_reason says so, because 'nothing changed' is "
            "an answer; `compile` refuses that case instead, since sealing a new revision of an "
            "unchanged plan would mint a second digest for one plan. Writes no file: the sealed diff and "
            "its digest are published in the one result document."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED wave-plan@1 or plan-diff@1 from its own content: its closed key set, "
            "every field, a plan's dependency/edge agreement, and its one digest. This reads no "
            "repository, so whether the document's inputs are still current is plan admission's "
            "separate check."
        ),
        epilog=EPILOG,
    )
    compile_command.add_argument("--mission", required=True, help=f"the SEALED {MISSION_SCHEMA} document")
    compile_command.add_argument("--snapshot", required=True, help=f"the SEALED {SNAPSHOT_SCHEMA} document")
    compile_command.add_argument("--submissions", required=True, help=f"the SEALED {SUBMISSIONS_SCHEMA} document")
    compile_command.add_argument(
        "--limits",
        default=None,
        help=(
            f"the {LIMITS_SCHEMA} policy document; without it the defaults are "
            f"{DEFAULT_LIMITS['max_concurrent_nodes']} concurrent nodes, "
            f"{DEFAULT_LIMITS['max_total_nodes']} total nodes, and recursion off"
        ),
    )
    compile_command.add_argument(
        "--prior-plan",
        dest="prior_plan",
        default=None,
        help=f"the SEALED {PLAN_SCHEMA} revision this compilation follows; absent means first wave",
    )
    compile_command.add_argument(
        "--at",
        required=True,
        help="the YYYY-MM-DDTHH:MM:SSZ instant of this compilation; this tool reads no clock",
    )
    compile_command.add_argument(
        "--out",
        default=None,
        help=(
            "where the compiled WavePlan is written, O_EXCL and fsynced: it must not exist and must be "
            "outside the repository the snapshot describes; a refusal writes nothing"
        ),
    )
    compile_command.add_argument(
        "--diff-out",
        dest="diff_out",
        default=None,
        help="where the compiled PlanDiff would be written, under the same two rules as --out",
    )
    diff_command.add_argument(
        "--plan", required=True, help=f"the newer SEALED {PLAN_SCHEMA} revision"
    )
    diff_command.add_argument(
        "--prior-plan",
        dest="prior_plan",
        required=True,
        help=f"the older SEALED {PLAN_SCHEMA} revision it is compared against",
    )
    diff_command.add_argument(
        "--at",
        required=True,
        help="the YYYY-MM-DDTHH:MM:SSZ instant of this derivation; this tool reads no clock",
    )
    artifact = verify.add_mutually_exclusive_group(required=True)
    artifact.add_argument("--plan", default=None, help=f"the SEALED {PLAN_SCHEMA} document to re-derive")
    artifact.add_argument("--diff", default=None, help=f"the SEALED {DIFF_SCHEMA} document to re-derive")
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
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no document "
            "could ever match it"
        )
        return EXIT_INPUT
    at = getattr(args, "at", None)
    if at is not None and not _TIME.match(at):
        # The instant is an ARGUMENT, so a malformed one means the question could not be asked. This
        # tool reads no clock, so there is nothing to fall back to. Read by ATTRIBUTE rather than by
        # command name, so a later command taking an instant inherits the guard instead of skipping it.
        report_input_error(
            f"--at {args.at!r} is not a YYYY-MM-DDTHH:MM:SSZ instant, so no plan could state when it "
            "was compiled"
        )
        return EXIT_INPUT
    try:
        result, targets = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    code = deliver_documents(result, targets)
    result["exit_code"] = code
    delivered = emit_result(result)
    # A result document that did not arrive outranks a file that did: the exit code has to be the worst
    # thing that happened, and a consumer reading no result at all learns nothing from a 0.
    return code if delivered == EXIT_OK else delivered


if __name__ == "__main__":
    raise SystemExit(main())
