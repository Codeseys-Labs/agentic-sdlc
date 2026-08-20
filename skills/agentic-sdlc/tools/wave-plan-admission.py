#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Admit a compiled WavePlan against CURRENT state, or say exactly what blocks it.

Issue 16's "Plan admission and approval lifecycle" section
(`docs/plans/claude-code-first-harness/issues/16-define-planning-drift-and-bounded-auto-mode.md`,
lines 114-135) is this module's whole contract, and it keeps TWO lifecycle states apart:

    `compiled` means the deterministic compiler proved closed schema, references, graph structure,
    and bounded declarations; it does not prove present feasibility or permission. `admitted` means a
    separate current-state check proved snapshot freshness, physical target and custody identity,
    dependency and artifact availability, applicable policy and ADR consistency, host/tool
    capability, route constraints and qualification, budgets and declared egress, gates and
    review/fan-in requirements, fallbacks and stop conditions, approval requirements, and absence of
    an unresolved prior effect.

`wave-plan-compiler.py` owns the first state and says so in its own residuals: "the plan carries the
snapshot's RECORDED head verbatim and compares it to nothing ... head freshness is the admission
gate's check and not this one's". THIS module is that gate.

THE FRESH SNAPSHOT IS THE CALLER'S, AND THAT IS DELIBERATE. Admission is read-only and runs no
subprocess, so it observes no repository itself: `--fresh-snapshot` is a `planning-snapshot@1`
document the CALLER captured at admission time, and the report records the head and instant it
carried. This module cannot prove that document was captured a second ago rather than a week ago --
that is stated as a residual rather than implied away -- but it makes the anchor a first-class,
digest-bound input instead of an unrecorded assumption, which is what Seed `agentic-sdlc-5ee7` asks
for: "a stale matched plan+apply pair ... derives write-ready, because no operand artifact carries
head or time linkage that a read-only composer could check".

TWO COMMANDS, ONE DIGEST.

    admit    reads the SEALED plan, the SEALED fresh snapshot, the SEALED mission contract, and
             OPTIONALLY the SEALED compile-time snapshot the plan's `inputs.snapshot_digest` names,
             admits each one, and seals ONE `wave-plan-admission@1` report carrying the disposition.
    verify   reads a SEALED report, re-derives its digest from its own content, and refuses when the
             two disagree. `--expect-digest` is the binding a later approval receipt uses.

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

where `canonical` is this family's form -- `sort_keys=True`, `separators=(",", ":")`,
`ensure_ascii=True`, `allow_nan=False`, and exactly one trailing newline. The `digest` key is
excluded BY NAME, so the derivation never depends on where an encoder puts it.

SIX CHECKS RUN, FIVE DIMENSIONS ARE DEFERRED BY NAME, AND NEITHER HALF IS SILENT. Issue 16 names
eleven things admission proves. Six of them are decidable from the sealed documents this gate
reads -- `snapshot-freshness`, `target-and-custody-identity`, `dependency-and-artifact-availability`,
`policy-and-adr-consistency`, `host-and-tool-capability`, and `unresolved-prior-effect` -- and each
runs here as a check whose failure is a named blocker. The other five are not expressible in any
merged schema: no document in this family carries a route candidate, a token or cost budget, an
egress declaration, a gate or review requirement, a per-node fallback, or a human approval receipt.
Those five, plus five partial refinements of checks that DO run, are carried in the sealed report's
own `deferred_dimensions` list with the reason each is not decidable. A deferred dimension is never
reported as a met check, because a met check would claim a proof that does not exist; and it is never
omitted, because a consumer reading six met checks has to be able to see what the six do not cover.

THE FRESHNESS CHECK IS THE 5EE7 ANCHOR, AND ITS RULE IS EXACT HEAD-RECORD EQUALITY. The compiler
carries the compile-time snapshot's recorded head verbatim into the plan and compares it to nothing.
This gate compares that carried head, field by field, against the head the FRESH snapshot recorded:
`commit_sha`, `tree_sha`, and `branch` must all be equal. The cartography left three candidate rules
open -- head-sha equality, receipt-chain linkage, and monotonic operation ids -- and equality is the
only one the merged schemas can express: no artifact in this family carries a reflog, an operation
id, or a receipt chain, so linkage and monotonicity would have to be invented here rather than read.
Two instants are compared alongside it, because a head that happens to match again after moving back
is not freshness: the fresh snapshot's `stated_at` must be STRICTLY later than the plan's
`compiled_at`, and `--at` may not be earlier than that `stated_at`. The plan's recorded
`inputs.snapshot_digest` must also DIFFER from the fresh snapshot's digest -- a document that is the
compile-time snapshot is not an observation of now, and admitting it would make the whole comparison
a tautology.

THE COMPILE-TIME SNAPSHOT IS OPTIONAL, AND ITS ABSENCE IS A BLOCKER RATHER THAN A PASS. Physical
target identity -- same repository path, same `git_dir` device, same `git_dir` inode -- is a
comparison between TWO observations, and the plan itself records neither: it carries the compile-time
snapshot only as a digest. So `--compiled-snapshot` accepts that exact sealed document, whose digest
must equal the plan's recorded `inputs.snapshot_digest`, and the identity comparison runs against it.
Without it there is nothing to compare, so `target-and-custody-identity` records a named blocker and
the report's disposition is `blocked`. Its digest is deliberately NOT a fourth field in the report:
the check refuses unless that digest equals the plan's recorded `inputs.snapshot_digest`, and the plan
digest the report already binds carries that value, so recording it twice could record it two ways. That is the conservative direction: an unverifiable identity
is not a verified one, and a swapped repository is exactly the mistake this check exists to catch.

CUSTODY AVAILABILITY IS BOUNDED BY WHAT `dirty_state` ACTUALLY RECORDS: FOUR COUNTS, NOT PATHS. A
snapshot's `dirty_state` is `{staged, unmerged, unstaged, untracked}` integers, so "is the plan's
custody set disjoint from the dirty set" is not a question these documents can answer. Any nonzero
count is therefore a named blocker rather than a per-path comparison, and the report says so: an
undecidable disjointness refuses, because the alternative is dispatching a wave over someone else's
uncommitted work. Worktree occupancy IS decidable and is checked exactly: a node's claimed
`worktree_custody`, resolved against the observed `repository.worktree_path`, may not already appear
in the fresh snapshot's `worktrees` list.

A BLOCKED REPORT IS STILL SEALED, AND THAT DIVERGES FROM THIS MODULE'S SIBLINGS ON PURPOSE. Issue 16
says admission "produces a content-minimized receipt OR EXACT BLOCKERS" (line 130): both
dispositions are outputs of admission, because a caller that must not dispatch needs a durable,
digest-bound record of WHY as much as a caller that may. `mission-contract.py` and
`wave-plan-compiler.py` publish nothing on a refusal, and they are right to -- a half-admitted
contract or an unchecked plan must not be bindable. The difference is what the document is ABOUT: a
refused contract would be a contract nobody proved, while a blocked report is a completed admission
whose answer is "no". So the publication rule here is drawn one level in:

  * INADMISSIBLE INPUTS publish nothing. `report` is null, `--out` writes no file, and no digest is
    derived, because the question could not be asked of these documents at all.
  * AN ADMISSIBLE INPUT SET always seals a report, whose `disposition` is `admitted` or `blocked`
    and whose `checks` name every blocker. A blocked report authorizes nothing -- neither does an
    admitted one -- so no consumer gains anything by holding it except the exact reasons.

THE REPORT IS CONTENT-MINIMIZED, per issue 16 line 130. It carries the three input digests, the
mission id, the plan revision, the head and instant the fresh snapshot recorded, the disposition,
the checks, and the deferred dimensions. It carries NO node, NO edge, NO custody path, and NO
objective WHEN IT IS ADMITTED. A blocker is the one exception, and a deliberate one: it names the
node id, the claimed worktree path, or the unmet capability demand that blocked, because a refusal a
consumer cannot act on is not a refusal. An admitted report has no blockers and therefore no plan
content at all. A consumer that
needs the plan reads the plan, whose digest this report binds. That also means a leaked report
discloses no repository content beyond one branch name and two object names.

NO CLOCK. Every instant is a caller-supplied input, because this project's WSL2 host steps
CLOCK_REALTIME backwards (Seed agentic-sdlc-184b) and a tool that read its own clock would refuse
honest input at random. `--at` is the family's fixed-width `YYYY-MM-DDTHH:MM:SSZ` form, whose
lexicographic order is chronological, and the guard is `[0-9]` rather than `\\d`: `\\d` matches
every Unicode decimal digit, so an Arabic-Indic instant would pass a `\\d` guard and then sort
against ASCII instants meaninglessly.

READ-ONLY, OFFLINE, AND EFFECT-FREE EXCEPT FOR ONE OPTIONAL FILE. This module runs no subprocess,
reads no environment variable, opens no socket, and never writes into the repository the snapshot
describes -- `--out` is refused when it resolves inside that tree, because a file landing there
would change the dirty state the snapshot already recorded and make its own record wrong. The one
file is created `O_EXCL` and fsynced, so an occupied destination is refused rather than replaced and
a racer cannot be clobbered.

FAIL CLOSED, AND NAME THE REASON. Every predicate accumulates named reasons against its own check
group; then ONE selection runs over ONE partition, so no input can yield two verdicts or none. A
bare "invalid" is useless to the human it asks, so every reason names the field and what was wrong
with it. Refusing is this module SUCCEEDING, which is why it exits 0.

EXITS. Implementation Decision 9 reserves 0 for a valid query, 1 for an unexpected internal failure,
2 for a grammar/schema/input error, 3 for a clean refusal before effect, and 4 after an admitted
partial or unknown effect. 3 is absent: a refusal here happens before anything is written, so there
was no effect to refuse before, and a derived `refused` is a RESULT. 4 is reachable for exactly one
reason -- `--out` created and then not finished -- because a report file that exists and may be
truncated is an effect this run left behind and a consumer must be told by name. Exit 2 covers a
supplied file that cannot be read as ONE JSON object and an argument that cannot be used at all. 1
covers a derived result that could not be delivered, because an answer that did not arrive is not a
success.

RESIDUALS, STATED EXACTLY.

  * The digest is RE-DERIVATION, not a security boundary. A same-OS-user forger can write a
    self-consistent sealed document; what the check catches is drift, a hand-edit, and a mismatched
    pair of artifacts.
  * FIVE OF ISSUE 16'S ELEVEN DIMENSIONS ARE DEFERRED, and five refinements of checks that do run
    are deferred beside them. The sealed report's `deferred_dimensions` list is the authoritative
    enumeration with a reason each; none of them is ever reported as a met check.
  * The fresh snapshot's FRESHNESS is the caller's claim. This module observes no repository, so it
    proves the document is a well-formed, self-consistent `planning-snapshot@1`, compares what it
    recorded against what the plan carried, and records what it said -- not that it was captured at
    this instant. A caller that re-supplies an old snapshot as `--fresh-snapshot` is caught only
    where the instants or the digest give it away.
  * PHYSICAL IDENTITY IS TWO RECORDED OBSERVATIONS, not a probe. Path, device, and inode are
    compared between two snapshot documents; this module stats nothing, so a device/inode pair the
    kernel reused after the compile-time capture compares equal, exactly as the snapshot tool's own
    residual says.
  * Worktree occupancy is compared as TEXT. The claimed relative custody path is joined to the
    observed `repository.worktree_path` and normalized, so a differently spelled path to the same
    directory -- through a symlink, a case-insensitive filesystem, or a bind mount -- is not
    recognised as the same worktree and reads as unoccupied.
  * An admitted report is EVIDENCE. `admitted` is not `approved`: issue 16 requires an
    operation-specific human receipt bound to the exact revision and digest, and this module grants
    no authority, reserves no route, creates no worktree, mutates no queue, and authorizes no
    dispatch, write, push, publication, PR mutation, merge, or deployment.
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

#: The document this module OWNS, and the result envelope it publishes.
ADMISSION_SCHEMA = "agentic-sdlc/wave-plan-admission@1"
RESULT_SCHEMA = "agentic-sdlc/wave-plan-admission-result@1"

#: The three input KINDS, each consumed by its own schema string. `planning-snapshot@1` serves two
#: input positions -- the fresh capture and the compile-time one the plan binds -- and one schema.
PLAN_SCHEMA = "agentic-sdlc/wave-plan@1"
SNAPSHOT_SCHEMA = "agentic-sdlc/planning-snapshot@1"
MISSION_SCHEMA = "agentic-sdlc/mission-contract@1"

VERDICT_ADMITTED = "admitted"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: The report's own disposition vocabulary, CLOSED. `blocked` is a completed admission whose answer
#: is "no"; it is not the absence of an answer, which is what a null `report` means.
DISPOSITION_ADMITTED = "admitted"
DISPOSITION_BLOCKED = "blocked"
DISPOSITIONS = (DISPOSITION_ADMITTED, DISPOSITION_BLOCKED)

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_ADMITTED: (
        "every input was admitted and every current-state check this revision runs passed, so the "
        "sealed report carries disposition admitted; admitted is NOT approved, and the report is "
        "evidence that authorizes no dispatch, no write, and no outward effect"
    ),
    VERDICT_VERIFIED: (
        "the sealed report re-derives its own digest and satisfies the closed report schema, so it is "
        "the same admission report it claims to be. This says NOTHING about its disposition: a blocked "
        "report verifies exactly as well as an admitted one, so read `report.disposition`. Whether the "
        "state it describes is still current is a fresh admission's question, and the report is "
        "evidence and authorizes nothing"
    ),
    VERDICT_REFUSED: (
        "this plan was NOT admitted. Either an input was inadmissible -- in which case no report was "
        "sealed, no digest was derived, and nothing was written -- or the inputs were admitted and the "
        "sealed report carries disposition blocked with every blocker named; no dispatch, write, or "
        "outward effect follows from either"
    ),
}

# Implementation Decision 9, minus 3: a refusal happens before anything is written, so there was no
# effect to refuse before and a derived `refused` is a RESULT.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2
#: Reachable for exactly one reason: `--out` created and then not finished is an effect left behind.
EXIT_PARTIAL = 4

DIGEST_KEY = "digest"

#: --- the report this module seals ---------------------------------------------------------------
#: Every key is REQUIRED, so an absence is always a named refusal and never a default. `admit` builds
#: exactly this set; `verify` reads it plus `digest`.
BODY_KEYS = (
    "admitted_at",
    "checks",
    "deferred_dimensions",
    "disposition",
    "inputs",
    "mission_id",
    "observed",
    "plan_revision",
    "schema",
)
SEALED_KEYS = tuple(sorted(BODY_KEYS + (DIGEST_KEY,)))

#: The three digests this report binds. The plan's own `inputs.submissions_digest` is NOT repeated
#: here: it is recorded in the plan this report binds, and a document recording one fact twice could
#: record it two different ways.
INPUTS_KEYS = ("mission_digest", "plan_digest", "snapshot_digest")
#: What the fresh snapshot SAID, copied verbatim rather than re-observed: this module runs no git, so
#: the only head it can honestly record is the one the supplied snapshot carried.
OBSERVED_KEYS = ("head", "snapshot_stated_at")
#: The snapshot's own head key set, because a subset would silently drop the branch a later check
#: compares. `branch` is nullable: a detached head is an observation, not a fault.
HEAD_KEYS = ("branch", "commit_sha", "tree_sha")
CHECK_KEYS = ("blockers", "met", "slug")
#: One deferred dimension: what was not decided, and why it could not be. The key names are the
#: snapshot tool's `unknowns` names, because this is the same idea -- a named absence of observation --
#: and a consumer that already reads one should not have to learn a second spelling for it.
DEFERRED_KEYS = ("dimension", "reason")

#: The CLOSED admission-check vocabulary, declared in FULL even though this revision emits six of its
#: members. The eleven are issue 16 lines 126-130's own enumeration, one slug per named thing, so a
#: report cannot claim a check the issue never asked for. Declaring all eleven keeps
#: `wave-plan-admission@1` a stable schema: a later revision that decides a currently deferred
#: dimension emits its slug without moving the report's key set, so a verifier built against this
#: revision still reads that report.
ADMISSION_CHECK_SLUGS = (
    "approval-requirements",
    "budgets-and-declared-egress",
    "dependency-and-artifact-availability",
    "fallbacks-and-stop-conditions",
    "gates-and-review-requirements",
    "host-and-tool-capability",
    "policy-and-adr-consistency",
    "route-constraints-and-qualification",
    "snapshot-freshness",
    "target-and-custody-identity",
    "unresolved-prior-effect",
)
#: The one RESERVED slug that names the group as a whole rather than one property of it. No report this
#: revision seals emits it -- the six implemented checks are named individually -- and it stays in the
#: vocabulary permanently so a report an earlier revision sealed keeps verifying against this one.
GROUP_SLUG = "admission-checks"
REPORT_SLUGS = tuple(sorted(ADMISSION_CHECK_SLUGS + (GROUP_SLUG,)))

#: The six of issue 16's eleven that are decidable from the documents this gate reads, in report order.
ADMITTED_CHECK_ORDER = (
    "snapshot-freshness",
    "target-and-custody-identity",
    "dependency-and-artifact-availability",
    "policy-and-adr-consistency",
    "host-and-tool-capability",
    "unresolved-prior-effect",
)

#: What this gate DOES NOT DECIDE, named with the reason it cannot. Five whole dimensions of issue
#: 16's eleven, and five refinements of a check that does run, so the check's own scope is exactly
#: what remains. A dimension named here is never also reported as a met check: a met check claims a
#: proof, and the whole point of this list is that there is none. The names of whole dimensions are
#: their check slugs, and a refinement is `<slug>:<aspect>`, which is the snapshot tool's own
#: `dimension:detail` spelling. Fixed strings rather than composed ones, so two runs over identical
#: inputs seal byte-identical reports.
DEFERRED_DIMENSIONS = (
    (
        "approval-requirements",
        "issue 16 requires an operation-specific human receipt bound to the exact plan revision and "
        "digest, and no receipt document is an input to this gate; admitted is not approved, so this "
        "gate proves no approval requirement and grants no authority",
    ),
    (
        "budgets-and-declared-egress",
        "no merged schema carries a token, cost, wall-clock, or egress declaration: a wave plan node "
        "records authority, capability demands, custody, and a wrong-output class and nothing about "
        "spend or outbound reach, so there is no declaration to check against an observation",
    ),
    (
        "dependency-and-artifact-availability:file-custody",
        "a planning snapshot records the digests of policy/*.json and .sdlc/* only, so whether a "
        "node's declared file_custody paths exist, are readable, or are already claimed is not "
        "observable from it; only worktree occupancy and the dirty counts are decided here",
    ),
    (
        "dependency-and-artifact-availability:worktree-branch",
        "issue 16's custody question includes which branch a claimed worktree is on, and a wave plan "
        "node declares no branch, so an observed worktree can be found occupied but never found "
        "occupied by the wrong branch",
    ),
    (
        "fallbacks-and-stop-conditions",
        "the mission contract's stop_conditions are validated by the contract tool and carry no "
        "per-node fallback, retry rule, or escalation path, and a wave plan node declares none, so "
        "there is no fallback to prove present and no stop rule to compare against one",
    ),
    (
        "gates-and-review-requirements",
        "no merged schema carries a gate identity, a required reviewer, or a fan-in requirement: a "
        "node's wrong_output_class states what a wrong output would cost, not which gate or review "
        "must run, so a requirement cannot be read and therefore cannot be checked",
    ),
    (
        "host-and-tool-capability:harness-demands",
        "a planning snapshot observes git, python, and uv, and the closed capability vocabulary also "
        "contains harness capabilities no snapshot field reports -- advisory-artifact-write, "
        "repository-read, seeds-queue-read, subagent-dispatch -- so a node demanding one of those is "
        "neither found feasible nor found infeasible here",
    ),
    (
        "host-and-tool-capability:version-qualification",
        "a planning snapshot records each observed capability's version string, and whether a version "
        "QUALIFIES for a demand is a policy judgment no merged schema states; presence and named "
        "unknowns are decided here, versions are not",
    ),
    (
        "policy-and-adr-consistency:adr-applicability",
        "a planning snapshot digests the policy/*.json files present, and which ADR or policy applies "
        "to a given wave is a judgment no document in this family records; the mission's authority "
        "ladder and the plan's own recorded execution-profile limits are what is checked here",
    ),
    (
        "route-constraints-and-qualification",
        "a wave plan node carries no model and no effort by construction, and no route candidate "
        "catalog is an input here, so issue 16's weaker form -- that at least one current candidate "
        "could satisfy the node's closed resolution requirements -- has no candidate set to read",
    ),
)
DEFERRED_NAMES = tuple(sorted(name for name, _ in DEFERRED_DIMENSIONS))

#: --- the sealed key sets of the three input kinds -----------------------------------------------
#: RE-EXPRESSED rather than imported, because a sibling tool is consumed as DOCUMENTS: this module
#: never imports one, and a shared constant would hide the day the two key sets diverged. Admission
#: is exactly the place a closed set belongs -- an unrecognised field is a meaning this gate cannot
#: honour, so it is refused rather than ignored -- and the sibling fixtures in this module's tests
#: are built by RUNNING the real tools, so a divergence fails a test instead of passing silently.
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
SNAPSHOT_BODY_KEYS = (
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
MISSION_BODY_KEYS = (
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
PLAN_SEALED_KEYS = tuple(sorted(PLAN_BODY_KEYS + (DIGEST_KEY,)))
SNAPSHOT_SEALED_KEYS = tuple(sorted(SNAPSHOT_BODY_KEYS + (DIGEST_KEY,)))
MISSION_SEALED_KEYS = tuple(sorted(MISSION_BODY_KEYS + (DIGEST_KEY,)))

#: The NESTED fields this module consumes, each named by its dotted path. Only these are required of
#: an input beyond its closed top-level set: the rest of a sibling's shape is the sibling's business,
#: and re-validating it here would make this file a second implementation of a schema it does not own.
#: `edges` is deliberately absent from the plan's list: a one-node wave has none, and an empty list is
#: the honest record of that rather than a missing field.
PLAN_REQUIRED = (
    "compiled_at",
    "declared_concurrency",
    "head.commit_sha",
    "head.tree_sha",
    "inputs.mission_digest",
    "inputs.snapshot_digest",
    "inputs.submissions_digest",
    "limits",
    "mission_id",
    "nodes",
    "revision",
)
#: `policy_digests`, `wave_artifacts`, and `worktrees` are absent for the same reason: a repository
#: with no `policy/` directory and no recorded wave artifact yields empty lists, and refusing those
#: would refuse an honest observation.
SNAPSHOT_REQUIRED = (
    "dirty_state",
    "head.commit_sha",
    "head.tree_sha",
    "host_capabilities",
    "repository.git_dir",
    "repository.git_dir_device",
    "repository.git_dir_inode",
    "repository.worktree_path",
    "stated_at",
    "unknowns",
)
MISSION_REQUIRED = (
    "authority.admitted_classes",
    "authority.ceiling",
    "completion_contract.success_criteria",
    "completion_contract.terminal_criteria",
    "mission_id",
    "revision",
    "scope.in_scope",
    "stated_at",
    "stop_conditions",
)

#: --- the nested vocabularies THIS gate reads out of its inputs -----------------------------------
#: Re-expressed for the same reason the sealed key sets are: a sibling is consumed as documents.
#: The snapshot's `repository` block, whose four fields ARE the physical target identity.
REPOSITORY_KEYS = ("git_dir", "git_dir_device", "git_dir_inode", "worktree_path")
#: `dirty_state` is four COUNTS. That is the whole reason the custody check cannot compare paths.
DIRTY_KEYS = ("staged", "unmerged", "unstaged", "untracked")
WORKTREE_KEYS = ("branch", "head", "path")
ARTIFACT_KEYS = ("path", "sha256")
#: The three capabilities a snapshot actually observes, each a version string or null.
CAPABILITY_KEYS = ("git", "python", "uv")
#: The mission contract's ORDERED authority ladder, and the plan's execution-profile limit keys.
AUTHORITY_CLASSES = (
    "read-only-advisory",
    "owned-worktree-write",
    "authorized-fan-in",
    "outward-effect",
)
LIMITS_KEYS = ("max_concurrent_nodes", "max_total_nodes", "recursive_spawn_generations")
#: Which OBSERVED capability each demand needs. Only the three a snapshot observes appear; the four
#: harness demands absent from this map are unobservable, and `host-and-tool-capability` says so in
#: `deferred_dimensions` rather than reporting them feasible.
DEMAND_CAPABILITY = {
    "git-worktree-write": "git",
    "python-execution": "python",
    "repository-gate-execution": "uv",
    "uv-python-toolchain": "uv",
}
#: The node fields this gate reads. A node carries more; those are the compiler's business.
NODE_READ_KEYS = ("authority_class", "capability_demands", "node_id", "worktree_custody")

#: Every check group, in report order.
CHECKS: tuple[str, ...] = (
    "wave-plan",
    "planning-snapshot",
    "compiled-snapshot",
    "mission-contract",
    "output-path",
    *ADMITTED_CHECK_ORDER,
    GROUP_SLUG,
    "closed-key-set",
    "admission-report-shape",
    "digest",
)
#: `admit`'s groups: four input positions, the destination, and the six current-state checks. The
#: reserved group slug is NOT among them: this revision names each check it runs, so reporting the
#: group as well would give the same evidence two records.
ADMIT_CHECKS = (
    "wave-plan",
    "planning-snapshot",
    "compiled-snapshot",
    "mission-contract",
    "output-path",
    *ADMITTED_CHECK_ORDER,
)
#: The five whose failure means NO report is sealed. A current-state check is deliberately not one of
#: them: a blocker there is the admission's ANSWER, and an answer gets sealed.
INPUT_SLUGS = ("wave-plan", "planning-snapshot", "compiled-snapshot", "mission-contract", "output-path")
#: `verify` re-observes nothing and writes nothing, so it reports neither an input position nor a
#: destination: claiming those as "met" would claim a check that never ran.
VERIFY_CHECKS = ("closed-key-set", "admission-report-shape", "digest")
CHECKS_BY_COMMAND = {"admit": ADMIT_CHECKS, "verify": VERIFY_CHECKS}

#: Carried in every document, because a consumer that binds the digest should carry what it does not
#: prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "five of issue 16's eleven dimensions -- approval requirements, budgets and declared egress, "
    "fallbacks and stop conditions, gates and review requirements, route constraints and "
    "qualification -- and five refinements of checks that do run are DEFERRED, and the sealed "
    "report's deferred_dimensions list is the authoritative enumeration with a reason each; none of "
    "them is ever reported as a met check",
    "the fresh snapshot's freshness is the CALLER's claim: this module observes no repository, so it "
    "compares what the fresh snapshot recorded against what the plan carried and records what it "
    "said, never that it was captured at this instant",
    "physical target identity is a comparison of two RECORDED observations, so it needs the "
    "compile-time snapshot the plan's inputs.snapshot_digest names; without --compiled-snapshot the "
    "identity check is a named blocker, and with it a device/inode pair the kernel reused after that "
    "capture still compares equal",
    "worktree occupancy is compared as normalized TEXT against the observed worktree list, so a "
    "differently spelled path to the same directory -- a symlink, a case-insensitive filesystem, a "
    "bind mount -- reads as unoccupied",
    "dirty_state records four COUNTS and no paths, so whether the plan's custody set is disjoint "
    "from the dirty set is undecidable here; any nonzero count is a named blocker instead, which "
    "refuses some waves that would in fact have been disjoint",
    "an input's closed key set is re-expressed here rather than imported, so a sibling that adds a "
    "field is refused by this gate until this constant is updated in the same change",
    "admitted is NOT approved: issue 16 requires an operation-specific human receipt bound to the "
    "exact revision and digest, and this module grants no authority, reserves no route, creates no "
    "worktree, mutates no queue, and authorizes no dispatch, write, or outward effect",
    "determinism here is over the SEALED report: identical inputs seal identical bytes. The result "
    "document additionally carries the absolute path a relative --out was resolved against, and no "
    "path reaches the sealed report",
)

_TIME = re.compile(r"[0-9]{4}-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9]Z\Z")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
#: A git object name is 40 (sha1) or 64 (sha256) lowercase hex characters. Both are admitted because
#: the repository's object format is the repository's choice, not this gate's.
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

    `json.loads` keeps the last value for a repeated key, so a report carrying two `disposition`
    fields parses to whichever the writer put second. That is a document with two meanings, and
    picking one of them would also give the one digest two possible values.
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
        if command == "admit":
            return VERDICT_ADMITTED
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
    """An id that names a mission or a check. Bounded so a refusal can quote it back unambiguously.

    Deliberately narrow: an id carrying whitespace, a path separator, or a leading punctuation mark
    would be quoted into refusal text where it is indistinguishable from the surrounding prose.
    """
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not _IDENTIFIER.match(value):
        assessment.note(
            slug,
            f"{what} {value!r} is not an identifier of unreserved characters (letters, digits, and "
            "'.', '_', '-' after a leading letter or digit), so it cannot be quoted back unambiguously",
        )
        return None
    return value


def _instant(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> str | None:
    """The family's fixed-width instant. `[0-9]` and not `\\d`: see the module docstring."""
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
            f"{what} is not 64 lowercase hexadecimal characters (found {value!r}), so it is not a "
            "sha256 content digest",
        )
        return None
    return value


def _object_name(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    if not isinstance(value, str) or not _OBJECT_NAME.match(value):
        assessment.note(
            slug,
            f"{what} is not a 40- or 64-character lowercase hexadecimal git object name (found "
            f"{value!r})",
        )
        return None
    return value


def _positive_integer(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> int | None:
    value = container.get(key)
    # `bool` is a subclass of `int`, and `True` would otherwise pass as the revision 1.
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
            f"{what} is not the closed key set {sorted(keys)}: missing {missing}, unexpected {extra}",
        )
        return None
    return value


def _member(assessment: Assessment, slug: str, value: Any, vocabulary: tuple[str, ...], what: str) -> str | None:
    if not isinstance(value, str) or value not in vocabulary:
        assessment.note(slug, f"{what} is not one of the closed vocabulary {list(vocabulary)} (found {value!r})")
        return None
    return value


def _sealed_input(
    assessment: Assessment, slug: str, document: dict[str, Any], schema: str, keys: tuple[str, ...], what: str
) -> str | None:
    """Admit one SEALED input: its declared schema string, its closed key set, then its own digest.

    Every half is a named refusal rather than an exit code: the file was readable and was one JSON
    object, so the question was asked and the answer is "refused". The three halves run in that order
    and stop at the first failure, because a document that is not this kind at all cannot meaningfully
    be told which keys it is missing.
    """
    declared = document.get("schema")
    if declared != schema:
        assessment.note(
            slug,
            f"{what} declares schema {declared!r} rather than {schema!r}, so it is not the document "
            "kind this input position consumes",
        )
        return None
    found = tuple(sorted(document))
    if found != keys:
        missing = [name for name in keys if name not in document]
        extra = [name for name in found if name not in keys]
        assessment.note(
            slug,
            f"{what} is not the closed sealed key set {list(keys)}: missing {missing}, unexpected "
            f"{extra}; an unrecognised field is a meaning this gate cannot honour, so it is refused "
            "rather than ignored",
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
    """Require only the NESTED fields THIS gate consumes, each named by its dotted path.

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
                    f"{what} has no {'.'.join(walked)}, and this gate consumes it, so its absence "
                    "cannot be defaulted",
                )
                container = None
                break
            container = container[part]
        if container is None:
            continue
        if container == "" or container == [] or container == {}:
            assessment.note(slug, f"{what} records {name} as empty ({container!r}), which states nothing")


# ---- the report shape, which `verify` reads back --------------------------------------------------


def check_head(assessment: Assessment, slug: str, container: dict[str, Any], what: str) -> None:
    """The observed head: two git object names, and a branch that may be null for a detached head."""
    head = _closed_object(assessment, slug, container, "head", HEAD_KEYS, what)
    if head is None:
        return
    _object_name(assessment, slug, head.get("commit_sha"), f"{what}'s commit_sha")
    _object_name(assessment, slug, head.get("tree_sha"), f"{what}'s tree_sha")
    branch = head.get("branch")
    if branch is not None and (not isinstance(branch, str) or not branch):
        assessment.note(
            slug,
            f"{what}'s branch is neither null nor a non-empty string (found {branch!r}); null is the "
            "record of a detached head, and an empty string records nothing",
        )


def check_report(assessment: Assessment, document: dict[str, Any]) -> None:
    """Validate one sealed `wave-plan-admission@1` against its closed schema, field by field.

    `verify` is the whole reason this exists as a separate function: a report is the document a later
    approval receipt binds, so it has to be checkable from its own content by a consumer that holds
    neither the plan nor the snapshot it names.
    """
    shape = "admission-report-shape"
    declared = document.get("schema")
    if declared != ADMISSION_SCHEMA:
        assessment.note(
            "closed-key-set",
            f"the document declares schema {declared!r} rather than {ADMISSION_SCHEMA!r}, so it is not "
            "an admission report",
        )
        return
    found = tuple(sorted(document))
    if found != SEALED_KEYS:
        missing = [name for name in SEALED_KEYS if name not in document]
        extra = [name for name in found if name not in SEALED_KEYS]
        assessment.note(
            "closed-key-set",
            f"the report is not the closed sealed key set {list(SEALED_KEYS)}: missing {missing}, "
            f"unexpected {extra}",
        )
        return
    _instant(assessment, shape, document, "admitted_at", "the report's admitted_at")
    _identifier(assessment, shape, document, "mission_id", "the report's mission_id")
    _positive_integer(assessment, shape, document, "plan_revision", "the report's plan_revision")
    disposition = _member(
        assessment, shape, document.get("disposition"), DISPOSITIONS, "the report's disposition"
    )
    inputs = _closed_object(assessment, shape, document, "inputs", INPUTS_KEYS, "the report's inputs")
    if inputs is not None:
        for key in INPUTS_KEYS:
            _digest_value(assessment, shape, inputs.get(key), f"the report's inputs.{key}")
    observed = _closed_object(assessment, shape, document, "observed", OBSERVED_KEYS, "the report's observed")
    if observed is not None:
        _instant(assessment, shape, observed, "snapshot_stated_at", "the report's observed.snapshot_stated_at")
        check_head(assessment, shape, observed, "the report's observed")
    deferred = check_report_deferred(assessment, shape, document)
    check_report_checks(assessment, shape, document, disposition, deferred)


def check_report_deferred(assessment: Assessment, slug: str, document: dict[str, Any]) -> set[str]:
    """The `deferred_dimensions` list: closed entries, a closed vocabulary, and one record each.

    An EMPTY list is admitted, and that is not a loophole: it is the honest record of a revision that
    decides every dimension issue 16 names, which is the direction this file is meant to move in. What
    is refused is a dimension outside the closed vocabulary -- an invented name would let a report
    excuse itself from a check nobody agreed to defer -- and a repeated one, which would give the same
    absence two reasons.
    """
    deferred = document.get("deferred_dimensions")
    if not isinstance(deferred, list):
        assessment.note(
            slug, f"the report's deferred_dimensions is not an array (found {deferred!r})"
        )
        return set()
    seen: list[str] = []
    for index, entry in enumerate(deferred):
        where = f"the report's deferred_dimensions[{index}]"
        if not isinstance(entry, dict):
            assessment.note(slug, f"{where} is not a JSON object (found {entry!r})")
            return set()
        found = tuple(sorted(entry))
        if found != tuple(sorted(DEFERRED_KEYS)):
            missing = [name for name in sorted(DEFERRED_KEYS) if name not in entry]
            extra = [name for name in found if name not in DEFERRED_KEYS]
            assessment.note(
                slug,
                f"{where} is not the closed key set {sorted(DEFERRED_KEYS)}: missing {missing}, "
                f"unexpected {extra}",
            )
            return set()
        name = _member(assessment, slug, entry.get("dimension"), DEFERRED_NAMES, f"{where}'s dimension")
        if _text(assessment, slug, entry, "reason", f"{where}'s reason") is None:
            continue
        if name is not None:
            seen.append(name)
    if sorted(seen) != sorted(set(seen)):
        repeated = sorted({name for name in seen if seen.count(name) > 1})
        assessment.note(
            slug,
            f"the report defers the dimension(s) {repeated} more than once, so one named absence has "
            "two reasons",
        )
    # A WHOLE dimension is named by its check slug; a refinement is `<slug>:<aspect>` and leaves the
    # rest of that check decidable. Only the whole ones can contradict a met check.
    return {name for name in seen if ":" not in name}


def check_report_checks(
    assessment: Assessment, slug: str, document: dict[str, Any], disposition: str | None, deferred: set[str]
) -> None:
    """The `checks` list, and the TWO cross-checks that keep the report from contradicting itself.

    `disposition` is DERIVED from the checks in `admit`, so `verify` re-derives it the same way and
    refuses a disagreement: a report claiming `admitted` while naming a blocker would otherwise be a
    self-contradicting document that still re-derived its own digest.

    The second is the one that makes `deferred_dimensions` load-bearing rather than documentation: a
    report may not report a check as MET while deferring that same whole dimension. Met means a
    comparison ran and passed; deferred means there was no comparison to run. A document claiming both
    about one dimension is exactly the vacuous pass this list exists to prevent.
    """
    checks = document.get("checks")
    if not isinstance(checks, list) or not checks:
        assessment.note(
            slug,
            f"the report's checks is not a non-empty array (found {checks!r}); a report naming no check "
            "at all would claim a disposition nothing supports",
        )
        return
    seen: list[str] = []
    unmet = 0
    for index, entry in enumerate(checks):
        where = f"the report's checks[{index}]"
        if not isinstance(entry, dict):
            assessment.note(slug, f"{where} is not a JSON object (found {entry!r})")
            return
        found = tuple(sorted(entry))
        if found != tuple(sorted(CHECK_KEYS)):
            missing = [name for name in sorted(CHECK_KEYS) if name not in entry]
            extra = [name for name in found if name not in CHECK_KEYS]
            assessment.note(
                slug,
                f"{where} is not the closed key set {sorted(CHECK_KEYS)}: missing {missing}, unexpected {extra}",
            )
            return
        name = _member(assessment, slug, entry.get("slug"), REPORT_SLUGS, f"{where}'s slug")
        met = entry.get("met")
        if not isinstance(met, bool):
            assessment.note(slug, f"{where}'s met is not a boolean (found {met!r})")
            return
        blockers = entry.get("blockers")
        if not isinstance(blockers, list) or any(not isinstance(item, str) or not item for item in blockers):
            assessment.note(slug, f"{where}'s blockers is not an array of non-empty strings (found {blockers!r})")
            return
        if met and blockers:
            assessment.note(
                slug,
                f"{where} is met and still names {len(blockers)} blocker(s); a met check has nothing to "
                "block on, so the two records contradict each other",
            )
        if met and name is not None and name in deferred:
            assessment.note(
                slug,
                f"{where} reports {name!r} met while the same report defers that whole dimension; met "
                "means a comparison ran and passed, deferred means there was none to run, and one "
                "document cannot claim both",
            )
        if not met and not blockers:
            assessment.note(
                slug,
                f"{where} is unmet and names no blocker; an unmet check whose reason is unstated is the "
                "one thing an admission report exists to prevent",
            )
        if not met:
            unmet += 1
        if name is not None:
            seen.append(name)
    if sorted(seen) != sorted(set(seen)):
        repeated = sorted({name for name in seen if seen.count(name) > 1})
        assessment.note(slug, f"the report names the check slug(s) {repeated} more than once, so each has two records")
    if disposition is None:
        return
    derived = DISPOSITION_BLOCKED if unmet else DISPOSITION_ADMITTED
    if disposition != derived:
        assessment.note(
            slug,
            f"the report records disposition {disposition!r} while its own checks derive {derived!r} "
            f"({unmet} unmet); the disposition is derived from the checks, never chosen beside them",
        )


# ---- the readable shape of each input, validated where the DOCUMENT is admitted -------------------
# Everything the six current-state checks read is shape-checked HERE, in the input position the
# document arrived in, and never inside a check. That boundary is what lets each check below compare
# two values without a "if this field was readable" branch: an unreadable field is an inadmissible
# input, no report is sealed, and no check runs at all. The alternative -- checking shape inside the
# comparisons -- would make a check able to report "met" over a field it could not read, which is the
# one thing a gate must never do.


def _count(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> int | None:
    """A non-negative integer: a count, a device number, or an inode number."""
    value = container.get(key)
    # `bool` is a subclass of `int`, and `True` would otherwise pass as the count 1.
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        assessment.note(slug, f"{what} is not an integer of at least 0 (found {value!r})")
        return None
    return value


def _relative_custody(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    """A repository-relative custody path, in the ONE spelling the compiler seals.

    The rule MIRRORS `wave-plan-compiler.py`'s own: no leading separator, no drive letter, no
    backslash, and no empty, `.`, or `..` segment. It refuses rather than normalizes, for two reasons.
    The compiler needs exactly one spelling so custody exclusivity between nodes is comparable at all;
    this gate needs it because the path is JOINED to the observed worktree root, and quietly rewriting
    `a//b` or `x/../y` here would compare occupancy for a directory the plan did not declare.
    """
    if not isinstance(value, str) or not value:
        assessment.note(slug, f"{what} is neither null nor a non-empty string (found {value!r})")
        return None
    if value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        assessment.note(
            slug,
            f"{what} {value!r} is absolute rather than repository-relative, so the directory it names "
            "cannot be located inside the observed repository and its occupancy cannot be compared",
        )
        return None
    if "\\" in value:
        assessment.note(
            slug,
            f"{what} {value!r} carries a backslash; custody paths are forward-slashed, and two "
            "spellings of one directory would compare as two different custodies",
        )
        return None
    if any(segment in ("", ".", "..") for segment in value.split("/")):
        assessment.note(
            slug,
            f"{what} {value!r} carries an empty, '.', or '..' segment: two spellings of it would compare "
            "as different custody, and a '..' climbs out of the repository the snapshot described",
        )
        return None
    return value


def check_plan_nodes(assessment: Assessment, plan: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The node fields this gate reads, and only those: id, authority class, demands, worktree.

    A node carries an objective, a file custody list, an output schema, and a wrong-output class as
    well; those are the compiler's to validate, and re-validating them here would make this file a
    second implementation of a schema it does not own.
    """
    slug = "wave-plan"
    nodes = plan.get("nodes")
    if not isinstance(nodes, list) or not nodes or any(not isinstance(entry, dict) for entry in nodes):
        assessment.note(slug, f"the wave plan's nodes is not a non-empty array of JSON objects (found {nodes!r})")
        return None
    readable: list[dict[str, Any]] = []
    for index, node in enumerate(nodes):
        where = f"the wave plan's nodes[{index}]"
        missing = [key for key in NODE_READ_KEYS if key not in node]
        if missing:
            assessment.note(slug, f"{where} has no {missing}, and this gate reads those fields")
            continue
        identifier = _identifier(assessment, slug, node, "node_id", f"{where}'s node_id")
        authority = _member(
            assessment, slug, node.get("authority_class"), AUTHORITY_CLASSES, f"{where}'s authority_class"
        )
        demands = node.get("capability_demands")
        if not isinstance(demands, list) or not demands or any(
            not isinstance(item, str) or not item for item in demands
        ):
            assessment.note(
                slug, f"{where}'s capability_demands is not a non-empty array of non-empty strings (found {demands!r})"
            )
            demands = None
        custody = node.get("worktree_custody")
        if custody is not None:
            custody = _relative_custody(assessment, slug, custody, f"{where}'s worktree_custody")
            if custody is None:
                continue
        if identifier is None or authority is None or demands is None:
            continue
        readable.append(
            {
                "authority_class": authority,
                "capability_demands": list(demands),
                "node_id": identifier,
                "worktree_custody": custody,
            }
        )
    return readable if len(readable) == len(nodes) else None


def check_plan_limits(assessment: Assessment, plan: dict[str, Any]) -> dict[str, int] | None:
    """The plan's own recorded execution profile: the ceilings its counts are re-checked against."""
    slug = "wave-plan"
    limits = _closed_object(assessment, slug, plan, "limits", LIMITS_KEYS, "the wave plan's limits")
    if limits is None:
        return None
    values: dict[str, int] = {}
    for key in LIMITS_KEYS:
        # `recursive_spawn_generations` is 0 when recursion is off, so the floor is 0 and not 1.
        floor = 0 if key == "recursive_spawn_generations" else 1
        value = _count(assessment, slug, limits, key, f"the wave plan's limits.{key}")
        if value is None or value < floor:
            if value is not None:
                assessment.note(
                    slug, f"the wave plan's limits.{key} is not an integer of at least {floor} (found {value!r})"
                )
            return None
        values[key] = value
    return values


def check_snapshot_state(assessment: Assessment, slug: str, snapshot: dict[str, Any], what: str) -> bool:
    """Every snapshot field the six checks read, shape-checked in one place.

    Returns False having noted its own reasons, so the caller can tell a readable snapshot from one
    whose fields the comparisons could not have been made against.
    """
    readable = True
    repository = _closed_object(assessment, slug, snapshot, "repository", REPOSITORY_KEYS, f"{what}'s repository")
    if repository is None:
        readable = False
    else:
        for key in ("git_dir", "worktree_path"):
            if _text(assessment, slug, repository, key, f"{what}'s repository.{key}") is None:
                readable = False
        for key in ("git_dir_device", "git_dir_inode"):
            if _count(assessment, slug, repository, key, f"{what}'s repository.{key}") is None:
                readable = False
    dirty = _closed_object(assessment, slug, snapshot, "dirty_state", DIRTY_KEYS, f"{what}'s dirty_state")
    if dirty is None:
        readable = False
    else:
        for key in DIRTY_KEYS:
            if _count(assessment, slug, dirty, key, f"{what}'s dirty_state.{key}") is None:
                readable = False
    if not _check_entry_list(assessment, slug, snapshot, "worktrees", WORKTREE_KEYS, what):
        readable = False
    if not _check_entry_list(assessment, slug, snapshot, "wave_artifacts", ARTIFACT_KEYS, what):
        readable = False
    if not _check_entry_list(assessment, slug, snapshot, "unknowns", ("dimension", "reason"), what):
        readable = False
    capabilities = _closed_object(
        assessment, slug, snapshot, "host_capabilities", CAPABILITY_KEYS, f"{what}'s host_capabilities"
    )
    if capabilities is None:
        readable = False
    else:
        for key in CAPABILITY_KEYS:
            value = capabilities.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                assessment.note(
                    slug,
                    f"{what}'s host_capabilities.{key} is neither null nor a non-empty version string "
                    f"(found {value!r}); null is the record of a capability that was not observed",
                )
                readable = False
    return readable


def _check_entry_list(
    assessment: Assessment, slug: str, snapshot: dict[str, Any], key: str, keys: tuple[str, ...], what: str
) -> bool:
    """One of the snapshot's set-shaped lists: every entry a closed object of non-empty strings.

    An EMPTY list is admitted deliberately: a repository with one worktree and no wave artifact
    records exactly that, and refusing it would refuse an honest observation. `branch` and `head` are
    nullable because a detached or bare worktree has neither.
    """
    entries = snapshot.get(key)
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        assessment.note(slug, f"{what}'s {key} is not an array of JSON objects (found {entries!r})")
        return False
    readable = True
    for index, entry in enumerate(entries):
        where = f"{what}'s {key}[{index}]"
        found = tuple(sorted(entry))
        if found != tuple(sorted(keys)):
            missing = [name for name in sorted(keys) if name not in entry]
            extra = [name for name in found if name not in keys]
            assessment.note(
                slug, f"{where} is not the closed key set {sorted(keys)}: missing {missing}, unexpected {extra}"
            )
            readable = False
            continue
        for name in keys:
            value = entry.get(name)
            if name in ("branch", "head") and value is None:
                continue
            if not isinstance(value, str) or not value:
                assessment.note(slug, f"{where}'s {name} is not a non-empty string (found {value!r})")
                readable = False
    return readable


def check_mission_ladder(assessment: Assessment, mission: dict[str, Any]) -> tuple[list[str], str] | None:
    """The mission's authority ladder: an admitted PREFIX of the ordered classes, and a ceiling in it.

    A prefix rather than an arbitrary set, because the ladder is ordered: admitting `outward-effect`
    while refusing `owned-worktree-write` would admit the larger power and refuse the smaller one.
    """
    slug = "mission-contract"
    authority = mission.get("authority")
    if not isinstance(authority, dict):
        assessment.note(slug, f"the mission contract's authority is not a JSON object (found {authority!r})")
        return None
    admitted = authority.get("admitted_classes")
    if not isinstance(admitted, list) or not admitted or any(not isinstance(item, str) for item in admitted):
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes is not a non-empty array of strings "
            f"(found {admitted!r})",
        )
        return None
    if tuple(admitted) != AUTHORITY_CLASSES[: len(admitted)]:
        assessment.note(
            slug,
            f"the mission contract's authority.admitted_classes {admitted} is not a leading prefix of "
            f"the ordered ladder {list(AUTHORITY_CLASSES)}, so what it admits cannot be read as a bound",
        )
        return None
    ceiling = authority.get("ceiling")
    if not isinstance(ceiling, str) or ceiling not in admitted:
        assessment.note(
            slug,
            f"the mission contract's authority.ceiling {ceiling!r} is not one of the classes it admits "
            f"({admitted}), so the mission's own bound is unreadable",
        )
        return None
    return list(admitted), ceiling


# ---- input admission -----------------------------------------------------------------------------


def check_output_path(
    assessment: Assessment, option: str, out: str | None, snapshot: dict[str, Any] | None
) -> Path | None:
    """`--out` may not exist, needs a real parent, and may not land in the observed repository.

    Containment is measured against the repository the FRESH SNAPSHOT describes, because that is the
    tree this admission is about: writing a report into it would change the dirty state the snapshot
    already recorded, and the snapshot's own record of it would be wrong from the moment the file
    landed. `realpath` is used on both sides, so a symlinked parent that points into the tree is
    caught rather than admitted on its spelling.
    """
    slug = "output-path"
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
            f"the {option} path {target} has no existing directory to be written into, so the sealed "
            "report would have nowhere to land",
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
                "writing an admission report into the tree it admits would change that tree's dirty "
                "state and make the snapshot's own record of it wrong",
            )
            return None
    return target


def admit_inputs(args: argparse.Namespace, assessment: Assessment) -> dict[str, Any]:
    """Read and admit the sealed inputs and the destination. Returns what the six checks read.

    Unusable files raise `InputError` out of here (exit 2). Everything else -- a wrong schema string, a
    key this revision does not know, a digest the content does not re-derive, a consumed nested field
    that is absent or unreadable -- is a named reason against the input position it arrived in. The
    derived values in the returned mapping (`nodes`, `limits`, `ladder`, `compiled`) are non-None only
    when their own shape was admitted, and the checks run only over a clean input set, so a check never
    reasons about a field this function could not read.
    """
    plan = load_document(args.plan, "wave plan")
    plan_digest = _sealed_input(assessment, "wave-plan", plan, PLAN_SCHEMA, PLAN_SEALED_KEYS, "the wave plan")
    nodes: list[dict[str, Any]] | None = None
    limits: dict[str, int] | None = None
    if plan_digest is not None:
        _required_fields(assessment, "wave-plan", plan, PLAN_REQUIRED, "the wave plan")
        _identifier(assessment, "wave-plan", plan, "mission_id", "the wave plan's mission_id")
        _positive_integer(assessment, "wave-plan", plan, "revision", "the wave plan's revision")
        _instant(assessment, "wave-plan", plan, "compiled_at", "the wave plan's compiled_at")
        _positive_integer(
            assessment, "wave-plan", plan, "declared_concurrency", "the wave plan's declared_concurrency"
        )
        check_head(assessment, "wave-plan", plan, "the wave plan's recorded head")
        # Read defensively: `inputs` is a required path above, but a non-object there would be a named
        # reason from `_required_fields` and must not become an attribute error here.
        recorded_inputs = plan.get("inputs")
        for key in ("mission_digest", "snapshot_digest"):
            if isinstance(recorded_inputs, dict):
                _digest_value(assessment, "wave-plan", recorded_inputs.get(key), f"the wave plan's inputs.{key}")
        nodes = check_plan_nodes(assessment, plan)
        limits = check_plan_limits(assessment, plan)

    snapshot = load_document(args.fresh_snapshot, "fresh planning snapshot")
    snapshot_digest = _sealed_input(
        assessment, "planning-snapshot", snapshot, SNAPSHOT_SCHEMA, SNAPSHOT_SEALED_KEYS, "the fresh planning snapshot"
    )
    fresh_readable = False
    if snapshot_digest is not None:
        _required_fields(assessment, "planning-snapshot", snapshot, SNAPSHOT_REQUIRED, "the fresh planning snapshot")
        _instant(assessment, "planning-snapshot", snapshot, "stated_at", "the fresh planning snapshot's stated_at")
        check_head(assessment, "planning-snapshot", snapshot, "the fresh planning snapshot's observed head")
        fresh_readable = check_snapshot_state(
            assessment, "planning-snapshot", snapshot, "the fresh planning snapshot"
        )

    # OPTIONAL, and its absence is a named blocker in `target-and-custody-identity` rather than a
    # refusal here: a caller that no longer holds the compile-time snapshot can still learn every
    # other reason its plan is not admissible.
    compiled: dict[str, Any] | None = None
    compiled_digest: str | None = None
    if args.compiled_snapshot is not None:
        compiled = load_document(args.compiled_snapshot, "compile-time planning snapshot")
        compiled_digest = _sealed_input(
            assessment,
            "compiled-snapshot",
            compiled,
            SNAPSHOT_SCHEMA,
            SNAPSHOT_SEALED_KEYS,
            "the compile-time planning snapshot",
        )
        if compiled_digest is None or not check_snapshot_state(
            assessment, "compiled-snapshot", compiled, "the compile-time planning snapshot"
        ):
            compiled = None

    mission = load_document(args.mission, "mission contract")
    mission_digest = _sealed_input(
        assessment, "mission-contract", mission, MISSION_SCHEMA, MISSION_SEALED_KEYS, "the mission contract"
    )
    ladder: tuple[list[str], str] | None = None
    if mission_digest is not None:
        _required_fields(assessment, "mission-contract", mission, MISSION_REQUIRED, "the mission contract")
        _identifier(assessment, "mission-contract", mission, "mission_id", "the mission contract's mission_id")
        ladder = check_mission_ladder(assessment, mission)

    # The destination is checked against the snapshot ONLY when the snapshot was admitted: containment
    # measured against a document this run refused would be containment against an unread field.
    admitted_snapshot = snapshot if snapshot_digest is not None and fresh_readable else None
    out = check_output_path(assessment, "--out", args.out, admitted_snapshot)
    return {
        "compiled": compiled,
        "compiled_digest": compiled_digest,
        "digests": {
            "mission_digest": mission_digest,
            "plan_digest": plan_digest,
            "snapshot_digest": snapshot_digest,
        },
        "ladder": ladder,
        "limits": limits,
        "mission": mission,
        "nodes": nodes,
        "out": out,
        "plan": plan,
        "snapshot": snapshot,
    }


# ---- the current-state checks ---------------------------------------------------------------------


def check_snapshot_freshness(
    assessment: Assessment, at: str, plan: dict[str, Any], snapshot: dict[str, Any], snapshot_digest: str
) -> None:
    """The 5EE7 ANCHOR: the head the plan carried against the head the fresh snapshot observed.

    Seed `agentic-sdlc-5ee7` names the exact failure this closes -- "a stale matched plan+apply pair
    ... derives write-ready, because no operand artifact carries head or time linkage that a read-only
    composer could check". The plan carries the compile-time snapshot's head VERBATIM and compares it
    to nothing; here it is compared, field by field, and the instants are compared beside it because a
    head that moved away and back is not the same observation.
    """
    slug = "snapshot-freshness"
    carried, observed = plan["head"], snapshot["head"]
    for key in HEAD_KEYS:
        if carried[key] != observed[key]:
            assessment.note(
                slug,
                f"the wave plan carries head.{key} {carried[key]!r} and the fresh planning snapshot "
                f"observed {observed[key]!r}: the target moved after this plan was compiled, so every "
                "custody, dependency, and diff decision in it was made against a state that is gone",
            )
    compiled_at, stated_at = plan["compiled_at"], snapshot["stated_at"]
    # Both instants are the family's fixed-width UTC form, already guarded, so lexicographic order IS
    # chronological order and no clock or date library is needed to compare them.
    if not stated_at > compiled_at:
        assessment.note(
            slug,
            f"the fresh planning snapshot states {stated_at} which is not strictly later than the wave "
            f"plan's compiled_at {compiled_at}; a snapshot taken at or before compilation is not an "
            "observation of the state this plan would now run against",
        )
    if at < stated_at:
        assessment.note(
            slug,
            f"--at {at} is earlier than the fresh planning snapshot's stated_at {stated_at}, so this "
            "admission claims to have happened before the observation it rests on",
        )
    if plan["inputs"]["snapshot_digest"] == snapshot_digest:
        assessment.note(
            slug,
            f"the supplied --fresh-snapshot IS the snapshot this plan was compiled from (digest "
            f"{snapshot_digest}), so comparing the plan's carried head against it proves nothing; a "
            "fresh capture is a second observation, not the first one supplied twice",
        )


def check_target_identity(
    assessment: Assessment, plan: dict[str, Any], snapshot: dict[str, Any], compiled: dict[str, Any] | None,
    compiled_digest: str | None,
) -> None:
    """PHYSICAL target identity: the same path, the same device, the same inode -- or a named refusal.

    Two RECORDED observations are compared, never a probe: this module stats nothing. The compile-time
    snapshot has to be supplied for the comparison to exist at all, because the plan binds it only by
    digest, and an unverifiable identity is not a verified one.
    """
    slug = "target-and-custody-identity"
    recorded = plan["inputs"]["snapshot_digest"]
    if compiled is None or compiled_digest is None:
        assessment.note(
            slug,
            "the compile-time planning snapshot was not supplied, so the fresh snapshot's repository "
            f"path, git_dir device, and git_dir inode could not be compared against the observation "
            f"this plan was compiled from (digest {recorded}); pass --compiled-snapshot to decide it, "
            "because an unverified physical target could be an entirely different repository",
        )
        return
    if compiled_digest != recorded:
        assessment.note(
            slug,
            f"the supplied --compiled-snapshot has digest {compiled_digest} and the wave plan records "
            f"inputs.snapshot_digest {recorded}: this is not the snapshot the plan was compiled from, "
            "so comparing physical identity against it would compare the wrong pair of observations",
        )
        return
    fresh, prior = snapshot["repository"], compiled["repository"]
    for key in REPOSITORY_KEYS:
        if fresh[key] != prior[key]:
            assessment.note(
                slug,
                f"the fresh planning snapshot observed repository.{key} {fresh[key]!r} and the "
                f"compile-time snapshot observed {prior[key]!r}: this is not the same physical target, "
                "so the plan would be admitted against a repository it was never compiled for",
            )


def _named_unknown(unknown_dimensions: set[str], dimension: str) -> bool:
    """True when `dimension` is itself named unknown, or refined by a `<dimension>:<detail>` entry.

    Mirrors the snapshot tool's own per-path refinement spelling (`wave_artifacts:<path>`), so a
    PARTIAL observation of a whole-list dimension is caught exactly as an unrefined absence of it would
    be. A check that reads only the field's OBSERVED value cannot otherwise tell "the snapshot looked
    and found nothing" apart from "the snapshot could not look", and only the first is an honest empty.
    """
    return dimension in unknown_dimensions or any(
        entry.startswith(f"{dimension}:") for entry in unknown_dimensions
    )


def check_custody_availability(
    assessment: Assessment, nodes: list[dict[str, Any]], snapshot: dict[str, Any]
) -> None:
    """Worktree occupancy, decided exactly; dirty state, refused conservatively.

    Occupancy is decidable: the plan's claimed worktree is repository-relative, the observed list
    records absolute paths, and joining the first to the snapshot's own `repository.worktree_path` puts
    the two in one spelling. Dirty state is NOT decidable: `dirty_state` is four counts and no paths,
    so "is the custody set disjoint from the dirty set" has no answer here and any nonzero count
    refuses. That direction is deliberate -- the alternative is a wave writing over uncommitted work.

    Both halves are the snapshot's OWN observation, so each is refused first when the snapshot names
    that observation among its own unknowns: `worktrees` or the `worktrees.branch` this function reads
    to describe what a claimed worktree holds, for occupancy; `dirty_state` for the counts below. An
    honestly incomplete `worktrees: []` or an honestly incomplete all-zero `dirty_state` is
    indistinguishable from a clean one unless the unknowns are consulted first.
    """
    slug = "dependency-and-artifact-availability"
    unknown_dimensions = {entry["dimension"] for entry in snapshot["unknowns"]}
    if _named_unknown(unknown_dimensions, "worktrees") or _named_unknown(unknown_dimensions, "worktrees.branch"):
        assessment.note(
            slug,
            "the fresh planning snapshot names worktrees (or worktrees.branch) among its own unknowns, "
            "so its observed worktree list is not a complete observation of what is on disk; an "
            "honestly incomplete observation cannot clear a check whose whole point is proving no "
            "claimed worktree is already occupied",
        )
    root = snapshot["repository"]["worktree_path"]
    occupied = {
        os.path.normpath(entry["path"]): entry
        for entry in snapshot["worktrees"]
        if os.path.normpath(entry["path"]) != os.path.normpath(root)
    }
    for node in nodes:
        custody = node["worktree_custody"]
        if custody is None:
            continue
        claimed = os.path.normpath(os.path.join(root, custody))
        entry = occupied.get(claimed)
        if entry is not None:
            branch = entry["branch"]
            held = f"branch {branch!r}" if branch is not None else "a detached head"
            assessment.note(
                slug,
                f"node {node['node_id']!r} claims the worktree {custody!r}, and the fresh planning "
                f"snapshot already observes a worktree at {claimed} holding {held}; a wave cannot take "
                "custody of a worktree that exists, and creating one is not this gate's to do",
            )
    if _named_unknown(unknown_dimensions, "dirty_state"):
        assessment.note(
            slug,
            "the fresh planning snapshot names dirty_state among its own unknowns, so its recorded "
            "counts are not a complete observation of the working tree; an honestly incomplete "
            "observation cannot clear a check whose whole point is proving the tree has nothing "
            "uncommitted for a wave to write over",
        )
    dirty = snapshot["dirty_state"]
    nonzero = ", ".join(f"{key}={dirty[key]}" for key in DIRTY_KEYS if dirty[key])
    if nonzero:
        assessment.note(
            slug,
            f"the fresh planning snapshot observed a dirty working tree ({nonzero}), and dirty_state "
            "records COUNTS rather than paths, so whether the plan's custody set is disjoint from it "
            "cannot be decided here; an undecidable disjointness refuses, because the "
            "alternative is dispatching a wave over work nobody committed",
        )


def check_policy_and_bounds(
    assessment: Assessment,
    plan: dict[str, Any],
    mission: dict[str, Any],
    nodes: list[dict[str, Any]],
    limits: dict[str, int],
    ladder: tuple[list[str], str],
    mission_digest: str,
) -> None:
    """The applicable policy this gate can actually read: the mission's ladder, and the plan's limits.

    The mission agreement runs FIRST and stops the rest: re-checking a plan's authority against a
    contract it was not compiled for would be a bound taken from the wrong document, which is worse
    than no bound at all. `admitted_classes` and `ceiling` are the mission's own policy; `limits` is
    the execution-profile policy the plan records having been compiled under.
    """
    slug = "policy-and-adr-consistency"
    recorded = plan["inputs"]["mission_digest"]
    if recorded != mission_digest:
        assessment.note(
            slug,
            f"the wave plan records inputs.mission_digest {recorded} and the supplied mission contract "
            f"has digest {mission_digest}: this plan was compiled against a different contract, so "
            "that contract's authority ladder is not this plan's bound",
        )
        return
    if plan["mission_id"] != mission["mission_id"]:
        assessment.note(
            slug,
            f"the wave plan serves mission_id {plan['mission_id']!r} and the supplied mission contract "
            f"declares {mission['mission_id']!r}; two documents naming two missions cannot bound each "
            "other",
        )
        return
    admitted, ceiling = ladder
    limit = AUTHORITY_CLASSES.index(ceiling)
    for node in nodes:
        authority = node["authority_class"]
        if authority not in admitted:
            assessment.note(
                slug,
                f"node {node['node_id']!r} carries authority_class {authority!r}, which the mission "
                f"contract does not admit ({admitted}); widening admitted authority is a mission "
                "revision, never an admission",
            )
        elif AUTHORITY_CLASSES.index(authority) > limit:
            assessment.note(
                slug,
                f"node {node['node_id']!r} carries authority_class {authority!r}, which is above the "
                f"mission contract's ceiling {ceiling!r}; raising a ceiling is a mission revision, "
                "never an admission",
            )
    if len(nodes) > limits["max_total_nodes"]:
        assessment.note(
            slug,
            f"the wave plan carries {len(nodes)} nodes against the execution-profile ceiling of "
            f"{limits['max_total_nodes']} it records having been compiled under",
        )
    concurrency = plan["declared_concurrency"]
    if concurrency > limits["max_concurrent_nodes"]:
        assessment.note(
            slug,
            f"the wave plan declares {concurrency} concurrent nodes against the execution-profile "
            f"ceiling of {limits['max_concurrent_nodes']} it records having been compiled under",
        )


def check_host_capability(
    assessment: Assessment, nodes: list[dict[str, Any]], snapshot: dict[str, Any]
) -> None:
    """Every demand the FRESH snapshot can speak to must be an observed capability, not an assumed one.

    Re-checked against the fresh observation rather than trusted from compile time, which is the whole
    point: `uv` present when the plan was compiled and gone now is exactly the drift admission exists
    to catch. Only the three capabilities a snapshot observes can be decided; the four harness demands
    absent from `DEMAND_CAPABILITY` are unobservable, and a capability the snapshot named among its own
    unknowns is refused too -- an unobserved capability is not an available one.
    """
    slug = "host-and-tool-capability"
    capabilities = snapshot["host_capabilities"]
    named = {entry["dimension"] for entry in snapshot["unknowns"]}
    for node in nodes:
        for demand in node["capability_demands"]:
            name = DEMAND_CAPABILITY.get(demand)
            if name is None:
                continue
            dimension = f"host_capabilities.{name}"
            if dimension in named:
                assessment.note(
                    slug,
                    f"node {node['node_id']!r} demands {demand!r}, and the fresh planning snapshot "
                    f"names {dimension} among its own unknowns; an unobserved capability is not an "
                    "available one",
                )
            elif capabilities[name] is None:
                assessment.note(
                    slug,
                    f"node {node['node_id']!r} demands {demand!r}, and the fresh planning snapshot "
                    f"observed no {dimension} on this host, so the node cannot be dispatched onto it",
                )


def check_prior_effect(assessment: Assessment, declared: list[str], snapshot: dict[str, Any]) -> None:
    """NO SECOND WAVE OVER AN UNRESOLVED FIRST.

    A wave artifact is the live record of a wave, and `wave_artifacts` records the path and digest of
    each one the snapshot found under `.sdlc`. What it does NOT record is whether that wave finished,
    so this check cannot read resolution out of the document and does not pretend to: ANY recorded
    artifact refuses. `--active-artifacts` sharpens the reason rather than relaxing the rule -- a
    caller who knows which artifact is live gets a refusal naming it -- and a declared artifact the
    snapshot does not record refuses too, because the caller and the observation then disagree about
    what is on disk and this gate cannot tell which is right.

    The list itself is the snapshot's OWN observation of `.sdlc`, so it is refused first when the
    snapshot names `wave_artifacts` -- or one `wave_artifacts:<path>` refinement of it -- among its own
    unknowns: an honestly incomplete listing is not the same thing as an empty one, and admitting a
    second wave on the strength of a directory the snapshot could not fully read is exactly the gap
    this check exists to close.
    """
    slug = "unresolved-prior-effect"
    unknown_dimensions = {entry["dimension"] for entry in snapshot["unknowns"]}
    if _named_unknown(unknown_dimensions, "wave_artifacts"):
        assessment.note(
            slug,
            "the fresh planning snapshot names wave_artifacts (or a wave_artifacts:<path> refinement of "
            "it) among its own unknowns, so its wave_artifacts list is not a complete observation of "
            "what is on disk; an honestly incomplete observation of prior wave artifacts is not an "
            "absence of one, so a second wave is not admitted on the strength of it",
        )
    observed = {entry["path"]: entry for entry in snapshot["wave_artifacts"]}
    # SORTED, so two runs that declare the same set in two orders seal identical bytes.
    for path in sorted(declared):
        if path in observed:
            assessment.note(
                slug,
                f"--active-artifacts names {path!r} as an unresolved prior effect and the fresh "
                "planning snapshot records it, so a first wave is still outstanding; no second wave is "
                "admitted over it",
            )
        else:
            assessment.note(
                slug,
                f"--active-artifacts names {path!r} and the fresh planning snapshot records no such "
                f"wave artifact (it records {sorted(observed)}); the declaration and the observation "
                "disagree about what is on disk, and this gate cannot tell which of the two is stale",
            )
    named = set(declared)
    unclassified = sorted(path for path in observed if path not in named)
    if unclassified:
        assessment.note(
            slug,
            f"the fresh planning snapshot records the wave artifact(s) {unclassified}, and no schema in "
            "this family records whether a wave artifact is resolved, so whether a prior wave is still "
            "outstanding cannot be decided from this document; resolve and remove them, or name them "
            "with --active-artifacts to record the refusal exactly",
        )


def run_admission_checks(args: argparse.Namespace, admitted: dict[str, Any], assessment: Assessment) -> tuple[str, ...]:
    """Run the six decidable current-state checks and return the slugs that RAN, in report order.

    Reached ONLY over an admitted input set, which is what lets each check read its fields directly:
    every shape these comparisons touch was validated in the input position its document arrived in.
    The reasons live in the ASSESSMENT rather than in a list returned beside it, so the sealed report's
    `checks` and the result's `reasons` are generated from one store and cannot disagree.

    The five whole dimensions and five refinements this does NOT decide are in `DEFERRED_DIMENSIONS`
    and reach the sealed report as `deferred_dimensions`. They are deliberately not slugs here: a
    check group in this list claims a comparison actually happened.
    """
    plan, snapshot, mission = admitted["plan"], admitted["snapshot"], admitted["mission"]
    digests = admitted["digests"]
    check_snapshot_freshness(assessment, args.at, plan, snapshot, digests["snapshot_digest"])
    check_target_identity(assessment, plan, snapshot, admitted["compiled"], admitted["compiled_digest"])
    check_custody_availability(assessment, admitted["nodes"], snapshot)
    check_policy_and_bounds(
        assessment, plan, mission, admitted["nodes"], admitted["limits"], admitted["ladder"],
        digests["mission_digest"],
    )
    check_host_capability(assessment, admitted["nodes"], snapshot)
    check_prior_effect(assessment, list(args.active_artifacts or ()), snapshot)
    return ADMITTED_CHECK_ORDER


def seal_document(body: dict[str, Any]) -> dict[str, Any]:
    """Add the one derived key. Nothing else in this module writes `digest`."""
    sealed = dict(body)
    sealed[DIGEST_KEY] = document_digest(body)
    return sealed


def seal_report(args: argparse.Namespace, admitted: dict[str, Any], assessment: Assessment) -> dict[str, Any]:
    """Seal ONE content-minimized `wave-plan-admission@1` from the admitted inputs and the checks.

    Reached only when every input position is clean, so every field read here was already admitted:
    the mission id is an identifier, the revision is a positive integer, and the snapshot's head and
    instant are well-formed. The `mission_id` is the PLAN's, because this report is about that plan;
    whether the supplied mission contract agrees is `policy-and-adr-consistency`'s first comparison,
    and a disagreement there is a blocker in the sealed report rather than a different mission id in
    it. `deferred_dimensions` is a constant, so two runs over identical inputs seal identical bytes.

    Each nested object is built from its own closed key tuple rather than copied wholesale, so a field
    a sibling adds later cannot silently widen this report and move its digest.
    """
    plan, snapshot = admitted["plan"], admitted["snapshot"]
    head = snapshot["head"]
    ran = run_admission_checks(args, admitted, assessment)
    checks = [
        {"blockers": list(assessment.groups[slug]), "met": not assessment.groups[slug], "slug": slug}
        for slug in ran
    ]
    body = {
        "schema": ADMISSION_SCHEMA,
        "admitted_at": args.at,
        "checks": checks,
        "deferred_dimensions": [{"dimension": name, "reason": reason} for name, reason in DEFERRED_DIMENSIONS],
        "disposition": DISPOSITION_BLOCKED if any(not entry["met"] for entry in checks) else DISPOSITION_ADMITTED,
        "inputs": dict(admitted["digests"]),
        "mission_id": plan["mission_id"],
        "observed": {
            "head": {key: head[key] for key in HEAD_KEYS},
            "snapshot_stated_at": snapshot["stated_at"],
        },
        "plan_revision": plan["revision"],
    }
    return seal_document(body)


def check_digest(assessment: Assessment, document: dict[str, Any], expect: str | None) -> str | None:
    """Re-derive the one digest of a sealed report under `verify`. Only `verify` reaches this.

    A recorded digest its own content does not re-derive is a refusal, and `--expect-digest` is
    compared against the DERIVED value rather than the recorded one, so a report that recorded a
    convenient digest cannot satisfy a caller's binding.
    """
    slug = "digest"
    recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the report's recorded digest")
    derived = document_digest(document)
    if recorded is not None and recorded != derived:
        assessment.note(
            slug,
            f"the report records digest {recorded} which its own content does not re-derive ({derived}): "
            "it has been edited since it was sealed, or the digest was written by something other than "
            "this family's derivation",
        )
    if expect is not None and expect != derived:
        assessment.note(
            slug,
            f"--expect-digest {expect} is not this report's content digest {derived}, so the supplied "
            "document is not the one the caller meant to bind",
        )
    return derived


def derive_command(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None]:
    """Admit one plan (`admit`) or re-derive one sealed report (`verify`).

    Returns the one result document together with the destination a sealed report is to be written to,
    which is kept OUT of the result until the write has actually happened.
    """
    command = args.command
    assessment = Assessment(CHECKS_BY_COMMAND[command])
    report: dict[str, Any] | None = None
    digest: str | None = None
    inputs_admitted: bool | None = None
    digests: dict[str, str | None] | None = None
    target: Path | None = None
    if command == "admit":
        admitted = admit_inputs(args, assessment)
        inputs_admitted = not any(assessment.groups[slug] for slug in INPUT_SLUGS)
        if inputs_admitted:
            # The current-state checks run only over ADMITTED inputs: a check reading a field whose own
            # refusal is already recorded would print a second reason about one mistake, and a check
            # reading a field that is missing would be reasoning about nothing.
            digests = admitted["digests"]
            report = seal_report(args, admitted, assessment)
            digest = report[DIGEST_KEY]
            target = admitted["out"]
    else:
        document = load_document(args.report, "admission report")
        check_report(assessment, document)
        digest = check_digest(assessment, document, args.expect_digest)
        if not assessment.reasons():
            # Republished ONLY for an admitted document, and from the ALREADY LOADED bytes: a refusal
            # publishes none of it, so no consumer can read a partially checked report out of a
            # refusal, and a second read could publish a document this run never checked.
            report = document
        else:
            digest = None
    verdict = assessment.verdict(command)
    result = {
        "schema": RESULT_SCHEMA,
        "command": command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": CONSEQUENCE[verdict],
        "inputs_admitted": inputs_admitted,
        "inputs": digests,
        "report": report,
        "report_digest": digest,
        # Filled in by `deliver_report` with what was ACTUALLY written, so a null here always means no
        # file of this run's making exists.
        "out": None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }
    return result, target


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
    advisory_stderr()(f"wave-plan-admission.py: {message}\n")


#: The three outcomes of one exclusive write, kept apart because they have different consequences: a
#: file that was never created leaves nothing behind, while one created and then not finished is an
#: admitted partial effect a consumer must be told about by name.
WRITE_DONE = "written"
WRITE_NOTHING = "nothing-created"
WRITE_PARTIAL = "created-but-incomplete"


def write_document(target: Path, document: dict[str, Any]) -> str:
    """Write the sealed report to a fresh path, or say exactly what was left behind.

    `O_EXCL` is the enforcement; the earlier existence check in `check_output_path` is only so a caller
    learns about an occupied destination before anything is derived. A racer that created the path in
    between is therefore refused here rather than clobbered.
    """
    payload = canonical_bytes(document)
    try:
        descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except OSError as exc:
        report_input_error(
            f"cannot create the --out path {target}: {exc}; the report was derived and nothing was "
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
            f"cannot write the --out path {target}: {exc}; that path now exists and may be incomplete, "
            "so treat it as unusable evidence rather than as this run's report"
        )
        return WRITE_PARTIAL
    return WRITE_DONE


def deliver_report(result: dict[str, Any], target: Path | None) -> int:
    """Write the sealed report, if one was sealed and a destination was given, and classify a failure.

    A report that could not be delivered to its file is still delivered in the result document, so
    nothing is lost but the file -- which is why a failure here is an exit code and not a refusal.
    """
    report = result.get("report")
    if target is None or report is None:
        return EXIT_OK
    state = write_document(target, report)
    if state == WRITE_DONE:
        result["out"] = str(target)
        return EXIT_OK
    return EXIT_INTERNAL if state == WRITE_NOTHING else EXIT_PARTIAL


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
    "delivered, because an answer that did not arrive is not a success; 4 a report was sealed and the "
    "file this run created was left incomplete, which is an admitted partial effect. Implementation "
    "Decision 9's 3 does not apply: a refusal happens before anything is written, so it is a result "
    "rather than a clean refusal before effect."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="wave-plan-admission.py",
        description=(
            "Admit a compiled WavePlan against current state, or say exactly what blocks it -- issue "
            "16's `admitted` lifecycle state, which is separate from the compiler's `compiled`. "
            "Read-only, offline, clock-free, and subprocess-free: it observes no repository itself, "
            "calls no model, resolves no runtime route, reads no environment variable, and authorizes "
            "nothing. Six of issue 16's eleven dimensions are decidable from the sealed documents it "
            "reads and run as checks; the other five, plus five partial refinements of checks that "
            "do run, are carried in the report's own deferred_dimensions list and are never "
            "reported as met."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    admit = commands.add_parser(
        "admit",
        description=(
            "Admit the SEALED wave plan, the SEALED fresh planning snapshot the caller captured at "
            "admission time, the SEALED mission contract, and optionally the SEALED compile-time "
            "snapshot the plan binds, then seal one content-minimized "
            "admission report. An inadmissible input seals nothing and writes nothing; an admissible "
            "input set always seals a report carrying the disposition and every blocker. An admitted "
            "report is evidence: `admitted` is not `approved`, and no dispatch, write, or outward "
            "effect follows from it."
        ),
        epilog=EPILOG,
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED wave-plan-admission@1 from its own content: its closed key set, "
            "every field, the disposition its own checks derive, and its one digest. This reads no "
            "repository and no plan, so whether the state the report describes is still current is a "
            "fresh admission's question."
        ),
        epilog=EPILOG,
    )
    admit.add_argument("--plan", required=True, help=f"the SEALED {PLAN_SCHEMA} document to admit")
    admit.add_argument(
        "--fresh-snapshot",
        dest="fresh_snapshot",
        required=True,
        help=(
            f"the SEALED {SNAPSHOT_SCHEMA} the CALLER captured at admission time; this tool observes no "
            "repository, so freshness is the caller's claim and the report records what it said"
        ),
    )
    admit.add_argument(
        "--compiled-snapshot",
        dest="compiled_snapshot",
        default=None,
        help=(
            f"the SEALED {SNAPSHOT_SCHEMA} the plan's inputs.snapshot_digest names; physical target "
            "identity is a comparison of two recorded observations, so without this the "
            "target-and-custody-identity check records a named blocker rather than passing"
        ),
    )
    admit.add_argument("--mission", required=True, help=f"the SEALED {MISSION_SCHEMA} document the plan serves")
    admit.add_argument(
        "--active-artifacts",
        dest="active_artifacts",
        action="append",
        default=None,
        metavar="PATH",
        help=(
            "repeatable: one wave-artifact path the caller knows to be an UNRESOLVED prior effect, as "
            "the fresh snapshot's wave_artifacts records it. Naming an observed artifact refuses by "
            "name; naming an unobserved one refuses as a disagreement; any recorded artifact nobody "
            "named refuses as unclassified, because no schema records whether a wave finished"
        ),
    )
    admit.add_argument(
        "--at",
        required=True,
        help="the YYYY-MM-DDTHH:MM:SSZ instant of this admission; this tool reads no clock",
    )
    admit.add_argument(
        "--out",
        default=None,
        help=(
            "where the sealed report is written, O_EXCL and fsynced: it must not exist and must be "
            "outside the repository the fresh snapshot describes; an inadmissible input writes nothing"
        ),
    )
    verify.add_argument("--report", required=True, help=f"the SEALED {ADMISSION_SCHEMA} document to re-derive")
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the report's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no report "
            "could ever match it"
        )
        return EXIT_INPUT
    declared = getattr(args, "active_artifacts", None) or []
    if any(not value for value in declared):
        report_input_error(
            "--active-artifacts was given an empty value, which names no wave artifact at all, so this "
            "run could not tell which prior effect the caller meant"
        )
        return EXIT_INPUT
    if len(set(declared)) != len(declared):
        repeated = sorted({value for value in declared if declared.count(value) > 1})
        report_input_error(
            f"--active-artifacts names {repeated} more than once; one artifact declared twice would "
            "produce one refusal twice, so the declaration is refused rather than deduplicated silently"
        )
        return EXIT_INPUT
    at = getattr(args, "at", None)
    if at is not None and not _TIME.match(at):
        # The instant is an ARGUMENT, so a malformed one means the question could not be asked. This
        # tool reads no clock, so there is nothing to fall back to. Read by ATTRIBUTE rather than by
        # command name, so a later command taking an instant inherits the guard instead of skipping it.
        report_input_error(
            f"--at {args.at!r} is not a YYYY-MM-DDTHH:MM:SSZ instant, so no report could state when the "
            "admission was derived"
        )
        return EXIT_INPUT
    try:
        result, target = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    code = deliver_report(result, target)
    result["exit_code"] = code
    delivered = emit_result(result)
    # A result document that did not arrive outranks a file that did: the exit code has to be the worst
    # thing that happened, and a consumer reading no result at all learns nothing from a 0.
    return code if delivered == EXIT_OK else delivered


if __name__ == "__main__":
    raise SystemExit(main())
