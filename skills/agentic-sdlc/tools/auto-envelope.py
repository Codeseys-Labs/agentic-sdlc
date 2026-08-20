#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Define, validate, and digest the AutoEnvelope -- the LAST link in the planning artifact chain.

`docs/plans/claude-code-first-harness/to-spec-handoff.md` fixes the chain and puts this artifact at
the end of it:

    MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope

and issue 16's "Default-off bounded auto-mode envelope" section says what the artifact is: "The
resulting immutable `AutoEnvelope` binds the plan and PlanningSnapshot digests, physical targets and
custody, allowed authority/effect classes, route constraints and fallbacks, egress, tools,
graph-change allowlist, concurrency and recursive-execution limits, retry policy,
node/time/call/token/cost budgets, validity conditions, checkpoints, and stop rules."

DEFAULT-OFF IS THE WHOLE DESIGN, AND IT IS A PROPERTY OF THE SCHEMA RATHER THAN OF A CALLER'S
DISCIPLINE. Issue 16 opens with "Agentic SDLC bounded auto mode is disabled by default and enabled
only by operation-specific human approval for one exact WavePlan revision", so this module makes an
absence REFUSE:

  * EVERY field of the body is REQUIRED. There is no defaulting layer at all, because a defaulted
    field is a permission nobody wrote down. A missing `egress_allowlist` does not mean "no egress",
    it means the envelope does not say, and an envelope that does not say is refused.
  * The only values that look like permissive defaults are the RESTRICTIVE ones: recursion
    generations must be present and must be 0, the egress posture must be present and must be
    `none`, and `route_constraints.require_resolved_assignment` must be present and must be `true`.
    Each is required-and-pinned rather than defaulted, so the emitted bytes state it.
  * A field may be present and EMPTY only where empty is the most restrictive reading of it:
    `tool_allowlist` and `graph_change_allowlist` may be `[]` (nothing is allowed), while
    `checkpoints` and `stop_rules` may not (an envelope with no checkpoint and no stop is
    unbounded, which is the thing this schema exists to make unrepresentable).

THE ENVELOPE'S TWO COMMANDS, ONE DIGEST -- the same shape mission-contract.py's `define`/`verify`
pair has. A third and fourth command, `admit-transition` and `verify-receipt`, are described further
down; they never write an envelope.

    define   reads an envelope BODY, validates it against the closed schema, and emits the SEALED
             document: the body plus exactly one added key, `digest`.
    verify   reads a SEALED document, re-derives its digest from its own content, and refuses when
             the two disagree. `--expect-digest` is the binding a later consumer uses.

    digest = sha256( canonical( sealed document MINUS its `digest` key ) )

`canonical` is this family's form -- `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=True`,
`allow_nan=False`, and exactly one trailing newline -- and the `digest` key is excluded BY NAME, so
the derivation never depends on where an encoder puts it. `define` REFUSES a body that already
carries a digest, by name: a supplied digest is a second origin for the one load-bearing value, and
a sealed document fed back into `define` would otherwise nest one. `define` NORMALIZES NOTHING; a
set-shaped field must arrive in its canonical form (ascending, no repeats) so the bytes digested are
the bytes the caller wrote.

THE THIRD COMMAND: admit-transition, THE ENVELOPE-RELATIVE HALF OF ADMISSION.

    admit-transition  reads one SEALED envelope and one UNSEALED proposed-transition body, asks at one
                      supplied instant whether the envelope admits that exact transition, and emits a
                      SEALED typed receipt either way.

`agentic-sdlc/autonomous-transition@1` is ONE proposed autonomous action and nothing else. It binds
the envelope by digest, and it states -- in ten required fields, none of which defaults -- the
transition's kind, the authority class it claims, the effect class it claims, the one tool class it
declares, the egress it declares, and the concurrency/recursion/retry state it proposes to leave
behind. The document is a PROPOSAL, so it arrives UNSEALED and this command derives its digest, for
the same reason `define` refuses a pre-sealed body: the one load-bearing value gets one origin.

EVERY ADMISSION CHECK IS A MEMBERSHIP TEST AGAINST A LIST THE ENVELOPE ALREADY WROTE DOWN, and the
default is off in the only sense that matters -- an unlisted value refuses. Naming a tool class the
envelope did not list, an effect class it did not list, a kind outside its graph-change allowlist, an
egress destination it left empty, or a concurrency the plan-narrowing limit does not reach is refused
by name, one reason per mistake. So is an envelope this command cannot trust: `admit-transition`
RE-VALIDATES the supplied envelope against the whole closed auto-envelope@1 schema and folds every
reason that earns into its own check group, because an allowlist read out of an inadmissible envelope
is not an allowlist. When the envelope is inadmissible the membership checks fall SILENT rather than
comparing against a field they cannot trust.

THE WINDOW IS STRICTLY INSIDE, AND THAT IS A CHOICE. `--at` must be strictly after `not_before` and
strictly before `not_after`. No document in this family says whether an envelope's window is closed,
half-open, or open at its ends, and default-off resolves the silence one way: at a boundary instant
the window is not DEMONSTRABLY open, so the answer is "refused" rather than a guess that happens to
be permissive. Both edges are refusals with their own named reasons, and both are pinned by tests.

STOP RULES ARE CHECKED AGAINST THE KIND, INDEPENDENTLY OF THE ALLOWLIST. `STOP_RULE_KIND_SURFACE`
records which change kinds each of the envelope's twelve always-stop conditions NAMES, and a kind a
carried stop rule names is refused in its own group. For a valid envelope this is redundant with the
graph-change allowlist -- the twelve widenings cannot be listed there in the first place -- and the
redundancy is the point: the two checks answer different questions ("this envelope did not list it"
versus "no envelope could, because the condition always stops"), so a later widening of one leaves
the other standing. Seven of the twelve rules name a kind, between them naming each of the twelve
widenings exactly once; the remaining FIVE name none. `expired-validity` is the window check above,
and the other four -- `failed-drift-classification`, `lost-attribution`,
`missing-transition-receipt`, `partial-or-unknown-prior-effect` -- are conditions about live state
that no pair of documents can settle, so they are RESIDUALS rather than silent passes. The one
exception this command can honestly enforce is `missing-transition-receipt` in its `--out` form: an
occupied output path means the receipt cannot be recorded, and a transition whose receipt cannot be
recorded is refused rather than admitted with a warning beside it.

THE RECEIPT IS ITS OWN SEALED DOCUMENT, `agentic-sdlc/autonomous-transition-receipt@1`, with six body
keys -- schema, the envelope digest, the transition digest, the verdict, the named reasons, and the
supplied instant -- plus the derived `digest`. It restates nothing else. The kind, the claimed classes,
and the two ids are all recoverable from the documents the two digests bind, and restating one here
would give it a second origin and a day when the two disagree. A REFUSAL gets a receipt too: "this
transition was refused at this instant, for these reasons" is exactly the evidence a later audit needs,
and a refusal that left no record would be indistinguishable from a transition nobody proposed.
`verify-receipt` re-derives that digest, so a receipt found on disk can be checked by the tool that
wrote it rather than by a consumer's reimplementation of the derivation.

RECORDED RESIDUAL, NOT SILENTLY DONE: this receipt does NOT adopt the merged
`agentic-sdlc/receipt-envelope@1` ancestor form. That module owns a wider envelope contract, and
folding this receipt into it is T4's extension to make -- one schema change, reviewed once, with that
module's own field set and its own tests. Doing it here would mean this file quietly deciding the
shape of another module's contract, so the choice is recorded and left open instead.

WHAT THIS MODULE STILL DOES NOT DO, DELIBERATELY -- the ENVELOPE-RELATIVE / PLAN-RELATIVE line.

Admission here is ENVELOPE-relative, end to end: every question is answerable from the envelope's and
the transition's own bytes. A PLAN-relative check needs the documents the envelope binds only BY
DIGEST -- the WavePlan's nodes, edges, budgets, and admitted fallbacks, and a fresh PlanningSnapshot.
Nothing here reads those, so nothing here can silently compare against them. In particular this
module never proves that:

  * `concurrency_limits.max_concurrent_nodes` is within the plan's own admitted concurrency (issue
    16: auto mode "cannot add or widen ... budgets"). That comparison needs the plan in hand, and no
    command in this file reads it.
  * the plan or snapshot digests this envelope names are the CURRENT ones, or that the plan revision
    is the one a human approved.
  * a named tool, effect, or graph change is reachable in that plan at all.

BUDGETS ARE BOUND BY DIGEST, NOT COPIED. Issue 16 lists "node/time/call/token/cost budgets" among
what the envelope binds, and it binds them the way it binds everything else about the plan: through
`bound_plan.plan_digest`. Restating those five numbers here would give each one a second origin, and
the day the two disagreed there would be no rule for which one governs. `checkpoints` therefore
carries a `budget-remaining` recheck -- the obligation to look -- while the numbers stay in the plan
and its execution-profile limits. The one limit this document does state, concurrency, is stated
because an envelope may NARROW the plan's concurrency for autonomous work, and `admit-transition`
refuses a transition that exceeds the narrowed number. Refusing a WIDENING of the plan's own admitted
concurrency is the other direction, and it needs the plan in hand.

THE FIVE CLOSED VOCABULARIES, AND WHY EACH IS CLOSED. An open string here would be a permission
spelled in prose, which is exactly what issue 16 forbids: "Rephrased prose, agent confidence,
apparent urgency, a passing local check, or unused budget cannot make an unlisted change
permissible."

  AUTHORITY CLASSES are the mission contract's four-rung LADDER, re-expressed here rather than
  imported. `allowed_authority_classes` must be a PREFIX of it -- the ladder is ordered, so a gap
  would admit a high rung while withholding a lower one it depends on -- and the prefix may not
  extend past `owned-worktree-write`. The two top rungs are NON-DELEGABLE by issue 16's own words:
  "Auto mode cannot add or widen ... integration authority ... or outward effects", and
  "publication/push/PR/merge/deployment ... always stop. Those gates are non-delegable even when the
  envelope predicts them." An envelope naming them would be a document claiming an authority no
  approval of it could grant, so it is refused rather than sealed and later ignored.

  EFFECT CLASSES are what an autonomous transition may CAUSE. The vocabulary deliberately INCLUDES
  the forbidden effects rather than leaving them unspellable, so an envelope naming one is refused
  with the doctrine reason instead of "unknown token": issue 16 enumerates them, and a caller who
  wrote `outward-effect` deserves the sentence that forbids it.

  TOOL CLASSES are classes, not host tool names. This bundle is host-agnostic (AGENTS.md: "Keep
  skills host-agnostic"), and `Bash` or `Edit` are one host's spelling of a capability; a class
  survives the host and is what an admission check can reason about.

  GRAPH CHANGE KINDS are the wave-plan compiler's sixteen PlanDiff change kinds, re-expressed rather
  than imported. `graph_change_allowlist` may name only the four an autonomous transition can cause
  under issue 16's inside-the-envelope list -- dispatch, preapproved retry, reorder of independent
  nodes, bounded read-only node addition, decomposition preserving declared outputs, and exact
  qualified fallback selection all land on `added-node`, `added-edge`, `changed-node`, and `retry`.
  The other twelve are the widenings issue 16 names: approval, authority, budget, custody-boundary,
  egress, gate, route-constraint, stop-rule, terminal-criterion, artifact (decomposition must
  "preserv[e] its declared outputs"), removed-node and removed-edge (a removal changes dependencies
  the plan's approval rests on).

  STOP RULE KINDS are the twelve always-stop conditions issue 16 names, and `stop_rules` must carry
  ALL twelve. This is the one field whose content is fixed, and it is a field rather than a constant
  because the writer must enumerate the stops in the bytes a human approves; completing a partial
  list on the writer's behalf is the default-permissive behavior this schema refuses.

CROSS-FIELD CONTRADICTIONS ARE REFUSALS, not silently ranked. A field set can be individually
well-formed and jointly incoherent, and the incoherence is where a permission hides:

  * a `file-writer` or `version-control-write` tool beside a ladder that stops at
    `read-only-advisory` -- the tool would be the write authority the ladder withheld;
  * a `network-fetch` tool beside the `none` egress posture -- the tool's only purpose is the egress
    the envelope forbids;
  * an `owned-worktree-file-write` effect beside that same read-only ladder;
  * `retry` in the graph-change allowlist while `retry_policy` admits one attempt per node, or the
    reverse -- the two fields would describe two different envelopes. The check is a BICONDITIONAL,
    so both directions are named.

INSTANTS ARE SUPPLIED, NEVER READ. `stated_at` and both ends of the validity window arrive in the
body; this module calls no clock, so `define` is deterministic and byte-reproducible. The window is
checked three ways: both ends are real calendar instants (the grammar admits `2026-13-45`, the
calendar does not), the start is STRICTLY before the end (a zero-width window is a document that
authorizes nothing while looking like it authorizes something), and the window opens no earlier than
`stated_at` (an envelope cannot be retroactively valid). Its duration is bounded by
`MAX_VALIDITY_SECONDS`, calibrated to issue 16's "one exact WavePlan revision": a grant outliving the
revision it was approved for is a standing grant.

DETERMINISM IS A PROPERTY OF THE BYTES. No clock, no environment variable, no subprocess, no
network, no filesystem write, and no set or dict iteration order reaches an emitted value.

EXIT CODES, AND WHY A REFUSAL IS 0. A refusal is an ANSWER: the question was asked and the answer is
"this envelope is not admissible", so it is a result document at exit 0 with a verdict and named
reasons. Exit 2 is for input or grammar this module could not ask a question about at all. Exit 1 is
internal only, INCLUDING a stdout that cannot receive the one result document, because an envelope
sealed and not delivered is not a success. Implementation Decision 9's 3 and 4 do not apply: this
command causes no effect, so it can neither refuse before one nor admit one.

A SEALED ENVELOPE IS EVIDENCE, NEVER AUTHORIZATION. It records what a human MAY approve for one
plan revision. It does not enable auto mode, grant a host permission, or bypass a prompt -- issue
16: "AutoEnvelope approval never changes host permissions or bypasses a permission prompt" -- and it
is independent of Claude Code's native permission Auto mode, its background classifier, the
recursive-execution profile, OCX Ultracode, and `--yolo`. An ADMITTED transition receipt is evidence
in exactly the same way: it records that one envelope admitted one proposal at one instant, and it
authorizes no dispatch, no write, no fan-in, and no outward effect. The act itself still needs
whatever authorization it needed before the receipt existed.
"""

import argparse
import datetime
import hashlib
import json
import math
import re
import stat
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ENVELOPE_SCHEMA = "agentic-sdlc/auto-envelope@1"
RESULT_SCHEMA = "agentic-sdlc/auto-envelope-result@1"

VERDICT_DEFINED = "defined"
VERDICT_VERIFIED = "verified"
VERDICT_REFUSED = "refused"

#: Each verdict's consequence, worded so a consumer never has to infer authority from a verdict name.
CONSEQUENCE = {
    VERDICT_DEFINED: (
        "the body was admitted against the closed auto-envelope@1 schema and the sealed document "
        "carries the one digest a later approval or transition check may bind; a defined envelope is "
        "evidence, it does not enable auto mode, and it authorizes no dispatch, no write, no host "
        "permission, and no outward effect"
    ),
    VERDICT_VERIFIED: (
        "the sealed document re-derives its own digest and satisfies its closed schema, so it is the "
        "same envelope it claims to be; whether the plan and snapshot it names are current, approved, "
        "and still within their validity window is a separate check this command does not run"
    ),
    VERDICT_REFUSED: (
        "no envelope was sealed, no digest was derived, and nothing was written; the reasons name each "
        "field and what was wrong with it, and bounded auto mode stays off"
    ),
}

# Implementation Decision 9, minus 3 and 4: this command causes no effect, so a refusal is a RESULT.
EXIT_OK = 0
EXIT_INTERNAL = 1
EXIT_INPUT = 2

DIGEST_KEY = "digest"

#: The mission contract's authority ladder, ASCENDING. Re-expressed rather than imported: a sibling
#: tool is consumed as documents, and a shared constant would hide the day the two vocabularies
#: diverged.
AUTHORITY_CLASSES = (
    "read-only-advisory",
    "owned-worktree-write",
    "authorized-fan-in",
    "outward-effect",
)

#: The highest rung an AutoEnvelope may admit. Issue 16: "Auto mode cannot add or widen ...
#: integration authority ... or outward effects", and publication/push/PR/merge/deployment "always
#: stop. Those gates are non-delegable even when the envelope predicts them."
AUTO_AUTHORITY_CEILING = "owned-worktree-write"

#: The closed vocabulary of effects an autonomous transition may CAUSE. The forbidden members are
#: spellable on purpose, so naming one earns the doctrine reason rather than "unknown token".
EFFECT_CLASSES = (
    "advisory-artifact-write",
    "credential-access",
    "destructive-action",
    "egress-network-call",
    "evidence-record-append",
    "fan-in-mutation",
    "outward-effect",
    "owned-worktree-file-write",
    "permission-change",
    "repository-read",
    "subagent-dispatch",
)

#: Issue 16: "Credential or security-boundary change, foreign or ambiguous ownership, corrupted
#: evidence, new destructive or outward effect, publication/push/PR/merge/deployment, authority
#: expansion, and partial or unknown prior effect always stop."
NON_DELEGABLE_EFFECTS = (
    "credential-access",
    "destructive-action",
    "egress-network-call",
    "fan-in-mutation",
    "outward-effect",
    "permission-change",
)

#: Effects that cannot happen without the ladder's write rung.
WRITE_EFFECTS = ("owned-worktree-file-write",)

#: Tool CLASSES, not one host's tool names; see the module docstring.
TOOL_CLASSES = (
    "advisory-artifact-writer",
    "file-reader",
    "file-writer",
    "gate-runner",
    "network-fetch",
    "repository-search",
    "shell-command",
    "subagent-spawner",
    "version-control-read",
    "version-control-write",
)
#: Tool classes that cannot be exercised without the ladder's write rung.
WRITE_TOOLS = ("file-writer", "version-control-write")
#: Tool classes whose only purpose is the egress a `none` posture forbids.
EGRESS_TOOLS = ("network-fetch",)

#: The wave-plan compiler's sixteen PlanDiff change kinds, re-expressed rather than imported.
CHANGE_KINDS = (
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

#: The four an autonomous transition can cause under issue 16's inside-the-envelope list.
AUTONOMOUS_CHANGE_KINDS = ("added-edge", "added-node", "changed-node", "retry")
#: The twelve widenings issue 16 forbids. Written out rather than derived, so the partition is
#: auditable by reading and a test can prove the two tuples cover the sixteen exactly once.
NON_DELEGABLE_CHANGE_KINDS = (
    "approval",
    "artifact",
    "authority",
    "budget",
    "custody-boundary",
    "egress",
    "gate",
    "removed-edge",
    "removed-node",
    "route-constraint",
    "stop-rule",
    "terminal-criterion",
)

#: Issue 16: "Every transition rechecks remaining budgets, current evidence, drift, and the narrower
#: authority inherited by children." Those four are MANDATORY; the fifth is optional.
CHECKPOINT_KINDS = (
    "authority-inheritance",
    "budget-remaining",
    "drift-recheck",
    "evidence-recheck",
    "validity-recheck",
)
MANDATORY_CHECKPOINT_KINDS = (
    "authority-inheritance",
    "budget-remaining",
    "drift-recheck",
    "evidence-recheck",
)

#: The twelve always-stop conditions, from issue 16's two hard-stop sentences. `stop_rules` must
#: carry all twelve; see the module docstring for why that is a field and not a constant.
STOP_RULE_KINDS = (
    "ambiguous-ownership",
    "authority-expansion",
    "budget-exhaustion",
    "corrupted-evidence",
    "credential-or-security-boundary-change",
    "expired-validity",
    "failed-drift-classification",
    "lost-attribution",
    "missing-transition-receipt",
    "new-destructive-or-outward-effect",
    "partial-or-unknown-prior-effect",
    "publication-push-pr-merge-deployment",
)

#: The only egress posture auto-envelope@1 can express. Bounded auto mode inherits no egress
#: destination and no data class, so `none` is not a default here -- it is the whole vocabulary.
EGRESS_POSTURES = ("none",)

#: Recursive spawn is a SEPARATE capability. Issue 16: "Bounded auto mode is independent of ... the
#: optional recursive-execution profile ... Enabling one does not enable, approve, weaken, or
#: configure another." An envelope raising it would be one capability configuring another.
MAX_RECURSION_GENERATIONS = 0
#: Bounded counts. The per-node ceiling is issue 16's "preauthorized retry" read narrowly: a retry
#: is one preapproved second attempt over proven no-effect, not an autonomous retry loop.
MAX_ATTEMPTS_PER_NODE_CEILING = 2
MAX_TOTAL_RETRIES_CEILING = 8
#: The handoff's "One wave, one DAG" section states four concurrent nodes as the wave default; an
#: envelope may narrow that for autonomous work and can never widen the plan's own admitted value;
#: that second comparison needs the plan, which no command here reads.
MAX_CONCURRENT_NODES_CEILING = 4
#: Calibrated to issue 16's "one exact WavePlan revision": 24 hours. A grant that outlives the
#: revision it was approved for is a standing grant, which approval-per-revision forbids.
MAX_VALIDITY_SECONDS = 86400

BODY_KEYS = (
    "allowed_authority_classes",
    "allowed_effect_classes",
    "bound_plan",
    "checkpoints",
    "concurrency_limits",
    "egress_allowlist",
    "envelope_id",
    "graph_change_allowlist",
    "retry_policy",
    "route_constraints",
    "schema",
    "stated_at",
    "stop_rules",
    "tool_allowlist",
    "validity_window",
)
SEALED_KEYS = tuple(sorted(BODY_KEYS + (DIGEST_KEY,)))

#: Every nested object is closed too, so an unrecognised field one level down is refused rather than
#: carried into the digest as a meaning this version cannot honour.
BOUND_PLAN_KEYS = ("plan_digest", "plan_revision", "snapshot_digest")
ROUTE_CONSTRAINT_KEYS = (
    "allow_fallback_selection",
    "allow_route_family_change",
    "require_resolved_assignment",
)
EGRESS_KEYS = ("data_classes", "destinations", "posture")
CONCURRENCY_KEYS = ("max_concurrent_nodes", "max_recursion_generations")
RETRY_KEYS = ("max_attempts_per_node", "max_total_retries", "require_proven_no_effect")
WINDOW_KEYS = ("not_after", "not_before")
CHECKPOINT_KEYS = ("kind", "requires_human_disposition")

CHECKS: tuple[str, ...] = (
    "closed-key-set",
    "identity-and-instant",
    "bound-plan",
    "authority-ladder",
    "effect-classes",
    "route-constraints",
    "egress-allowlist",
    "tool-allowlist",
    "graph-change-allowlist",
    "concurrency-and-recursion",
    "retry-policy",
    "validity-window",
    "checkpoints",
    "stop-rules",
    "digest",
)

#: Carried in every document, because a consumer that binds the digest should carry what it does not
#: prove. The module docstring above is the authoritative statement of each.
RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "the plan and snapshot are bound BY DIGEST only: this module reads neither document, so it "
    "cannot say the digests are current, approved, or mutually consistent",
    "node, time, call, token, and cost budgets live in the WavePlan and its execution-profile "
    "limits; this envelope binds them through the plan digest and states only the concurrency it "
    "may narrow",
    "define and verify admit no proposed autonomous transition and produce no transition receipt; "
    "that is admit-transition's question, and a well-formed envelope is not an approved one",
    "the validity window is checked for shape, ordering, and duration against supplied instants; "
    "whether the window is OPEN right now needs a clock this module never reads",
    "a sealed envelope is evidence: it does not enable auto mode, change a host permission, or "
    "bypass a permission prompt, and it is independent of native Auto mode, Ultracode, and --yolo",
)

# ---- the proposed transition, its receipt, and the admission vocabulary ---------------------------

TRANSITION_SCHEMA = "agentic-sdlc/autonomous-transition@1"
RECEIPT_SCHEMA = "agentic-sdlc/autonomous-transition-receipt@1"
TRANSITION_RESULT_SCHEMA = "agentic-sdlc/autonomous-transition-result@1"

VERDICT_ADMITTED = "admitted"

#: ONE proposed autonomous action. Every key is REQUIRED and none defaults, for the same reason the
#: envelope's are: a defaulted field would be a permission nobody proposed and nobody approved.
TRANSITION_BODY_KEYS = (
    "bound_envelope",
    "claimed_authority_class",
    "claimed_effect_class",
    "declared_egress",
    "declared_tool",
    "kind",
    "proposed_deltas",
    "schema",
    "stated_at",
    "transition_id",
)
#: The transition names the envelope by DIGEST and by ID. The digest is the binding; the id is what
#: makes a mismatch legible, because two digests differ in a way no human reads.
BOUND_ENVELOPE_KEYS = ("envelope_digest", "envelope_id")

#: The proposed state AFTER the transition, stated absolutely rather than as a signed increment. A
#: signed delta would be uncheckable here: the CURRENT counts live in the WavePlan, which no command in
#: this file reads, so `+1` could not be resolved against any limit. An absolute after-value is
#: checkable against the envelope's own ceilings with nothing but these two documents.
DELTA_KEYS = (
    "attempts_for_node_after",
    "concurrent_nodes_after",
    "recursion_generations_after",
    "total_retries_after",
)

#: The receipt's whole body: the two digests it binds, the verdict, the named reasons, and the instant
#: the question was asked at. Nothing is restated from either bound document; see the module docstring.
RECEIPT_BODY_KEYS = ("at", "envelope_digest", "reasons", "schema", "transition_digest", "verdict")
RECEIPT_SEALED_KEYS = tuple(sorted(RECEIPT_BODY_KEYS + (DIGEST_KEY,)))

#: Which change kinds each always-stop condition NAMES. The seven rules below name each of the twelve
#: non-delegable change kinds exactly once; the other five name none, because they are conditions about
#: live state rather than about a kind. Written as a mapping rather than a flat set so a refusal can say
#: WHICH stop rule names the kind -- "this is a widening" and "this is the budget-exhaustion stop" send
#: an operator to two different places.
STOP_RULE_KIND_SURFACE: dict[str, tuple[str, ...]] = {
    "ambiguous-ownership": ("custody-boundary",),
    "authority-expansion": ("approval", "authority", "stop-rule"),
    "budget-exhaustion": ("budget",),
    "corrupted-evidence": ("artifact",),
    "credential-or-security-boundary-change": ("route-constraint",),
    "expired-validity": (),
    "failed-drift-classification": (),
    "lost-attribution": (),
    "missing-transition-receipt": (),
    "new-destructive-or-outward-effect": ("egress", "removed-edge", "removed-node"),
    "partial-or-unknown-prior-effect": (),
    "publication-push-pr-merge-deployment": ("gate", "terminal-criterion"),
}

TRANSITION_CHECKS: tuple[str, ...] = (
    "closed-key-set",
    "envelope-admissibility",
    "envelope-digest-binding",
    "transition-identity",
    "admission-window",
    "transition-kind",
    "claimed-authority",
    "claimed-effect",
    "declared-tool",
    "declared-egress",
    "proposed-deltas",
    "stop-rules",
    "output-path",
)

RECEIPT_CHECKS: tuple[str, ...] = ("closed-key-set", "receipt-content", "digest")

TRANSITION_RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "admission here is ENVELOPE-relative: the WavePlan and PlanningSnapshot the envelope binds by "
    "digest are not read, so this command cannot say the transition's node, edge, tool, or fallback "
    "exists in that plan, that the plan revision is the one a human approved, or that remaining "
    "node/time/call/token/cost budget covers the proposed act",
    "four of the twelve always-stop conditions -- failed-drift-classification, lost-attribution, "
    "missing-transition-receipt, and partial-or-unknown-prior-effect -- are conditions about live "
    "state that no pair of documents can settle, so they are NOT enforced here beyond the occupied "
    "--out path a receipt could not be recorded to",
    "the instant is SUPPLIED through --at; whether that instant is now is the caller's claim, and no "
    "clock in this module checks it",
    "this receipt does not adopt the merged receipt-envelope@1 ancestor form; folding the two is T4's "
    "extension to make in that module's own field set and tests, and it is recorded here rather than "
    "done silently",
    "an admitted transition receipt is EVIDENCE: it records that one envelope admitted one proposal "
    "at one instant, and it authorizes no dispatch, no write, no fan-in, no host permission change, "
    "and no outward effect",
)

RECEIPT_RESIDUALS = (
    "the digest is re-derivation, not a boundary against a same-OS-user forger",
    "a verified receipt is the receipt it claims to be; whether the envelope and transition its two "
    "digests name still exist, and whether the act it records ever happened, are separate questions "
    "this command does not ask",
)

TRANSITION_CONSEQUENCE = {
    VERDICT_ADMITTED: (
        "the supplied envelope is admissible against its own closed schema, it is the envelope the "
        "transition binds, the supplied instant falls strictly inside its validity window, and every "
        "claimed class, declared tool, declared egress, and proposed count is inside the corresponding "
        "allowlist or limit; the sealed receipt records that admission, and it authorizes no dispatch, "
        "no write, no fan-in, and no outward effect"
    ),
    VERDICT_REFUSED: (
        "the transition was NOT admitted and nothing was dispatched; a sealed receipt records the "
        "refusal and its named reasons at the supplied instant, because a refusal that left no record "
        "would be indistinguishable from a transition nobody proposed"
    ),
}

RECEIPT_CONSEQUENCE = {
    VERDICT_VERIFIED: (
        "the sealed receipt re-derives its own digest and carries the closed "
        "autonomous-transition-receipt@1 field set, so it is the receipt it claims to be; what its two "
        "digests bind is not read here"
    ),
    VERDICT_REFUSED: (
        "the supplied document is not a receipt this derivation produced, so nothing about the "
        "admission it appears to record is established"
    ),
}

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

    The key is excluded BY NAME, so the derivation does not depend on where an encoder puts it, and
    every command here runs the same function over the same body. It is deliberately not
    envelope-specific: the envelope, the proposed transition, and the receipt are three documents in
    this file and a second derivation for any of them would be a second answer to one question.
    """
    body = {key: value for key, value in document.items() if key != DIGEST_KEY}
    return hashlib.sha256(canonical_bytes(body)).hexdigest()


def _reject_nonfinite(token: str) -> Any:
    """`json` accepts `NaN`, `Infinity`, and `-Infinity` by default; no honest artifact carries one."""
    raise InputError(f"the supplied document carries the non-finite JSON constant {token}")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Refuse a repeated JSON key instead of silently keeping the last one.

    `json.loads` keeps the last value for a repeated key, so a body carrying two `tool_allowlist`
    arrays parses to whichever the writer put second. That is a document with two meanings, and
    picking one of them would also give the one digest two possible values.
    """
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise InputError(f"the supplied document repeats the JSON key {key!r}, so it has two meanings")
        seen[key] = value
    return seen


def _assert_finite(value: Any, where: str) -> None:
    """Refuse a non-finite float that no constant token announced.

    `parse_constant` catches the `NaN`/`Infinity` spellings and nothing else: the literal `1e400` is
    an ordinary JSON number that overflows to `inf` during parsing without passing through that hook.
    It has to be refused because `canonical_bytes` runs with `allow_nan=False`, so an infinity
    reaching the digest derivation would raise out of this module as a traceback instead of being
    classified.

    The walk is ITERATIVE. Nesting depth is whoever supplied the document's choice, and a recursive
    walk would trade a classified refusal for a `RecursionError` on exactly the hostile input this
    check exists for.
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
    for a supplied path may be never, so a directory mistake exits 2 promptly while a FIFO mistake
    would hang forever. `Path.stat()` follows a symlink to its target, which is the question this
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

    Reasons are held PER CHECK GROUP so the result can say which part of the envelope is unmet, and
    the flat `reasons` list is generated from the same store, so the two can never disagree.

    `slugs` is per COMMAND rather than global: the envelope commands answer one closed question and
    `admit-transition` answers another, and a shared slug set would put a group in every result that
    only one command can ever fill. The order is the order reasons are reported in.
    """

    def __init__(self, slugs: tuple[str, ...] = CHECKS) -> None:
        self.slugs = slugs
        self.groups: dict[str, list[str]] = {slug: [] for slug in slugs}

    def note(self, slug: str, reason: str) -> None:
        self.groups[slug].append(reason)

    def reasons(self) -> list[str]:
        flat: list[str] = []
        for slug in self.slugs:
            flat.extend(self.groups[slug])
        return flat

    def document(self) -> list[dict[str, Any]]:
        return [{"met": not self.groups[slug], "reasons": self.groups[slug], "slug": slug} for slug in self.slugs]

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
        if command in ("verify", "verify-receipt"):
            return VERDICT_VERIFIED
        if command == "admit-transition":
            return VERDICT_ADMITTED
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
    """An id quoted back into refusals, receipts, and approvals, so its characters are bounded."""
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
    """A YYYY-MM-DDTHH:MM:SSZ instant that is also a real calendar instant.

    The grammar and the calendar are two different questions: `2026-13-45T99:00:00Z` matches the
    shape and names no moment. Both are checked here because the window comparison below orders these
    strings lexically, and a string that is not a real instant would order fine and mean nothing.
    `strptime` reads no clock.
    """
    value = _text(assessment, slug, container, key, what)
    if value is None:
        return None
    if not _TIME.match(value):
        assessment.note(slug, f"{what} {value!r} is not a YYYY-MM-DDTHH:MM:SSZ instant")
        return None
    if _parse_instant(value) is None:
        assessment.note(
            slug,
            f"{what} {value!r} has the shape of an instant but names no calendar moment, so nothing "
            "can be ordered against it",
        )
        return None
    return value


def _parse_instant(value: str) -> datetime.datetime | None:
    """The one place an instant string becomes a comparable moment. No clock, no local timezone."""
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.UTC)
    except ValueError:
        return None


def _digest_value(assessment: Assessment, slug: str, value: Any, what: str) -> str | None:
    if not isinstance(value, str) or not _HEX64.match(value):
        assessment.note(
            slug,
            f"{what} is not 64 lowercase hexadecimal characters (found {value!r}), so it cannot be a "
            "sha256 content digest",
        )
        return None
    return value


def _integer(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str, *, low: int, high: int
) -> int | None:
    """A bounded integer. Booleans are excluded BY TYPE: `true` is a mistake, not the number 1."""
    value = container.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        assessment.note(slug, f"{what} is not an integer (found {value!r})")
        return None
    if value < low or value > high:
        assessment.note(
            slug,
            f"{what} is {value}, outside the admitted range {low}..{high}; a bounded envelope cannot "
            "state an unbounded number",
        )
        return None
    return value


def _boolean(assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str) -> bool | None:
    """A real JSON boolean. `"true"`, `1`, and `null` are each a different kind of not-said."""
    value = container.get(key)
    if not isinstance(value, bool):
        assessment.note(
            slug,
            f"{what} is not a JSON boolean (found {value!r}); a posture this envelope does not state "
            "in a boolean is not stated",
        )
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
            f"{what} is not the closed key set {sorted(keys)}: missing {missing}, unexpected {extra}; "
            "every field of this envelope is required, so an absence refuses rather than defaults",
        )
        return None
    return value


def _string_list(
    assessment: Assessment, slug: str, container: dict[str, Any], key: str, what: str, *, allow_empty: bool
) -> list[str] | None:
    """An ascending set of non-empty strings. `allow_empty` is per field and never a global default.

    Empty is admitted exactly where empty is the MOST RESTRICTIVE reading of the field, and refused
    where it would make the envelope silent instead of narrow.
    """
    value = container.get(key)
    if not isinstance(value, list):
        assessment.note(slug, f"{what} is not a JSON array (found {value!r})")
        return None
    if not value and not allow_empty:
        assessment.note(
            slug,
            f"{what} is empty, and an empty list here states nothing rather than stating a narrower "
            "envelope",
        )
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
            "here would be a permission spelled in prose",
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


# ---- the closed schema, one check group per named property -----------------------------------------


def check_key_set(assessment: Assessment, document: dict[str, Any], command: str) -> None:
    """The closed schema itself: exactly these keys, no more and no fewer.

    `define` and `verify` differ by exactly one key, and the difference is checked in both directions:
    a body handed to `define` may NOT carry a derived digest, and a document handed to `verify` MUST.
    """
    expected = set(SEALED_KEYS) if command == "verify" else set(BODY_KEYS)
    present = set(document)
    for key in sorted(expected - present):
        assessment.note(
            "closed-key-set",
            f"the envelope carries no {key}, which the closed auto-envelope@1 schema requires of every "
            "envelope; bounded auto mode is default-off, so an absent field refuses rather than "
            "defaulting to a permissive value",
        )
    for key in sorted(present - expected):
        if command == "define" and key == DIGEST_KEY:
            assessment.note(
                "closed-key-set",
                "the body handed to define already carries a digest, which is DERIVED from the body and "
                "never supplied: accepting one would give the single load-bearing value a second "
                "origin, and a sealed envelope fed back in would nest one",
            )
            continue
        assessment.note(
            "closed-key-set",
            f"the envelope carries the unknown field {key!r}; auto-envelope@1 is a closed schema, so a "
            "field this version cannot honour is refused rather than ignored",
        )
    schema = document.get("schema")
    if "schema" in document and schema != ENVELOPE_SCHEMA:
        assessment.note(
            "closed-key-set",
            f"the envelope declares schema {schema!r}, not {ENVELOPE_SCHEMA}, so which field set and "
            "which digest derivation it is about is not established",
        )


def check_identity(assessment: Assessment, document: dict[str, Any]) -> tuple[str | None, str | None]:
    slug = "identity-and-instant"
    envelope_id = _identifier(assessment, slug, document, "envelope_id", "the envelope's envelope_id")
    stated_at = _instant(assessment, slug, document, "stated_at", "the envelope's stated_at")
    return envelope_id, stated_at


def check_bound_plan(assessment: Assessment, document: dict[str, Any]) -> dict[str, Any] | None:
    """The two digests and the one revision this envelope is FOR.

    Issue 16: approval is "for one exact WavePlan revision", so the revision number is part of the
    binding rather than a label -- an envelope that named only a digest could be read as covering
    whatever revision that digest turns out to be.
    """
    slug = "bound-plan"
    bound = _closed_object(assessment, slug, document, "bound_plan", BOUND_PLAN_KEYS, "the envelope's bound_plan")
    if bound is None:
        return None
    plan_digest = _digest_value(assessment, slug, bound.get("plan_digest"), "bound_plan.plan_digest")
    snapshot_digest = _digest_value(assessment, slug, bound.get("snapshot_digest"), "bound_plan.snapshot_digest")
    revision = _integer(
        assessment, slug, bound, "plan_revision", "bound_plan.plan_revision", low=1, high=2**31 - 1
    )
    if plan_digest is None or snapshot_digest is None or revision is None:
        return None
    if plan_digest == snapshot_digest:
        assessment.note(
            slug,
            "bound_plan names one digest for both the WavePlan and the PlanningSnapshot; two different "
            "documents cannot share a content digest, so one of the two bindings is wrong",
        )
        return None
    return {"plan_digest": plan_digest, "plan_revision": revision, "snapshot_digest": snapshot_digest}


def check_authority(assessment: Assessment, document: dict[str, Any]) -> list[str] | None:
    """An ascending PREFIX of the ladder, stopping at or below the auto-mode ceiling.

    Not `_string_list`: the ladder's order is the ladder's, not the alphabet's
    (`owned-worktree-write` sorts before `read-only-advisory`), so an ascending-set check would
    refuse the only correct spelling.
    """
    slug = "authority-ladder"
    admitted = document.get("allowed_authority_classes")
    if not isinstance(admitted, list) or not admitted or not all(isinstance(name, str) for name in admitted):
        assessment.note(
            slug,
            f"the envelope's allowed_authority_classes is not a non-empty array of strings (found "
            f"{admitted!r}); an envelope that admits no authority at all is not narrow, it is unstated",
        )
        return None
    if _closed_vocabulary(assessment, slug, list(admitted), AUTHORITY_CLASSES, "allowed_authority_classes") is None:
        return None
    if list(admitted) != list(AUTHORITY_CLASSES[: len(admitted)]):
        assessment.note(
            slug,
            f"the envelope allows the authority classes {list(admitted)}, which is not a prefix of the "
            f"ladder {list(AUTHORITY_CLASSES)}; the ladder is ordered, so a gap in it would admit a "
            "wider authority while refusing a narrower one it rests on",
        )
        return None
    ceiling_index = AUTHORITY_CLASSES.index(AUTO_AUTHORITY_CEILING)
    above = [name for name in admitted if AUTHORITY_CLASSES.index(name) > ceiling_index]
    if above:
        assessment.note(
            slug,
            f"the envelope allows the authority classes {above}, which are above the bounded auto-mode "
            f"ceiling {AUTO_AUTHORITY_CEILING!r}: issue 16 says auto mode 'cannot add or widen ... "
            "integration authority ... or outward effects', and those gates are 'non-delegable even "
            "when the envelope predicts them', so no approval of this envelope could grant them",
        )
        return None
    return list(admitted)


def check_effects(assessment: Assessment, document: dict[str, Any], admitted: list[str] | None) -> list[str] | None:
    """The closed effect vocabulary, minus the non-delegable members, cross-checked against the ladder."""
    slug = "effect-classes"
    effects = _string_list(
        assessment, slug, document, "allowed_effect_classes", "the envelope's allowed_effect_classes", allow_empty=False
    )
    if effects is None:
        return None
    if _closed_vocabulary(assessment, slug, effects, EFFECT_CLASSES, "allowed_effect_classes") is None:
        return None
    forbidden = [name for name in effects if name in NON_DELEGABLE_EFFECTS]
    if forbidden:
        assessment.note(
            slug,
            f"allowed_effect_classes names {forbidden}, which issue 16 lists among the effects that "
            "'always stop' and are 'non-delegable even when the envelope predicts them'; an envelope "
            "cannot preauthorize them, so naming one is refused rather than sealed and later ignored",
        )
        return None
    if admitted is not None and AUTO_AUTHORITY_CEILING not in admitted:
        needs_write = [name for name in effects if name in WRITE_EFFECTS]
        if needs_write:
            assessment.note(
                slug,
                f"allowed_effect_classes names {needs_write} while allowed_authority_classes stops at "
                f"{admitted[-1]!r}: the effect would be the write authority the ladder withheld, so the "
                "two fields describe two different envelopes",
            )
            return None
    return effects


def check_route_constraints(assessment: Assessment, document: dict[str, Any]) -> dict[str, bool] | None:
    """A closed BOOLEAN posture. No provider, model, or route string appears in this schema at all.

    Route identity is the RuntimeAssignment's, and it is resolved per dispatch against a live adapter
    readback (AGENTS.md: "resolved is recorded only after adapter readback"). A provider string frozen
    into an envelope hours earlier would be a second, stale origin for that fact, so this document
    states only the POSTURE: every autonomous dispatch must present a resolved assignment, and the
    envelope may not move the route family the plan admitted.
    """
    slug = "route-constraints"
    routes = _closed_object(
        assessment, slug, document, "route_constraints", ROUTE_CONSTRAINT_KEYS, "the envelope's route_constraints"
    )
    if routes is None:
        return None
    resolved = _boolean(
        assessment, slug, routes, "require_resolved_assignment", "route_constraints.require_resolved_assignment"
    )
    fallback = _boolean(
        assessment, slug, routes, "allow_fallback_selection", "route_constraints.allow_fallback_selection"
    )
    family = _boolean(
        assessment, slug, routes, "allow_route_family_change", "route_constraints.allow_route_family_change"
    )
    if resolved is None or fallback is None or family is None:
        return None
    if resolved is not True:
        assessment.note(
            slug,
            "route_constraints.require_resolved_assignment is false; a dispatch whose RuntimeAssignment "
            "is requested, inherited, unresolved, or incomplete stops BEFORE spawn, so an envelope that "
            "waives the requirement is preauthorizing a dispatch that cannot happen",
        )
        return None
    if family is not False:
        assessment.note(
            slug,
            "route_constraints.allow_route_family_change is true; issue 16 says auto mode 'cannot add or "
            "widen ... model/provider/route families', so this posture is fixed at false and a change of "
            "family needs a new plan, admission, PlanDiff, and human approval",
        )
        return None
    return {
        "allow_fallback_selection": fallback,
        "allow_route_family_change": family,
        "require_resolved_assignment": resolved,
    }


def check_egress(assessment: Assessment, document: dict[str, Any]) -> str | None:
    """`none` is the whole vocabulary of auto-envelope@1, and both lists must be empty to say so."""
    slug = "egress-allowlist"
    egress = _closed_object(
        assessment, slug, document, "egress_allowlist", EGRESS_KEYS, "the envelope's egress_allowlist"
    )
    if egress is None:
        return None
    posture = _member(assessment, slug, egress, "posture", EGRESS_POSTURES, "egress_allowlist.posture")
    destinations = _string_list(
        assessment, slug, egress, "destinations", "egress_allowlist.destinations", allow_empty=True
    )
    data_classes = _string_list(
        assessment, slug, egress, "data_classes", "egress_allowlist.data_classes", allow_empty=True
    )
    if posture is None or destinations is None or data_classes is None:
        return None
    if destinations or data_classes:
        assessment.note(
            slug,
            f"egress_allowlist declares posture {posture!r} while naming destinations {destinations} and "
            f"data classes {data_classes}; auto-envelope@1 expresses exactly one egress posture, and a "
            "named destination beside it is a permission the posture denies",
        )
        return None
    return posture


def check_tools(
    assessment: Assessment, document: dict[str, Any], admitted: list[str] | None, posture: str | None
) -> list[str] | None:
    """The tool-class allowlist. Empty is admitted: nothing allowed is the narrowest envelope there is."""
    slug = "tool-allowlist"
    tools = _string_list(
        assessment, slug, document, "tool_allowlist", "the envelope's tool_allowlist", allow_empty=True
    )
    if tools is None:
        return None
    if _closed_vocabulary(assessment, slug, tools, TOOL_CLASSES, "tool_allowlist") is None:
        return None
    refused = False
    if admitted is not None and AUTO_AUTHORITY_CEILING not in admitted:
        needs_write = [name for name in tools if name in WRITE_TOOLS]
        if needs_write:
            assessment.note(
                slug,
                f"tool_allowlist names {needs_write} while allowed_authority_classes stops at "
                f"{admitted[-1]!r}: the tool would be the write authority the ladder withheld",
            )
            refused = True
    if posture == "none":
        needs_egress = [name for name in tools if name in EGRESS_TOOLS]
        if needs_egress:
            assessment.note(
                slug,
                f"tool_allowlist names {needs_egress} while egress_allowlist.posture is 'none': the "
                "tool's only purpose is the egress this envelope forbids",
            )
            refused = True
    return None if refused else tools


def check_graph_changes(assessment: Assessment, document: dict[str, Any]) -> list[str] | None:
    """Which of the compiler's sixteen PlanDiff change kinds an autonomous transition may cause."""
    slug = "graph-change-allowlist"
    changes = _string_list(
        assessment, slug, document, "graph_change_allowlist", "the envelope's graph_change_allowlist", allow_empty=True
    )
    if changes is None:
        return None
    if _closed_vocabulary(assessment, slug, changes, CHANGE_KINDS, "graph_change_allowlist") is None:
        return None
    forbidden = [name for name in changes if name in NON_DELEGABLE_CHANGE_KINDS]
    if forbidden:
        assessment.note(
            slug,
            f"graph_change_allowlist names {forbidden}, which are outside issue 16's closed "
            f"inside-the-envelope list {list(AUTONOMOUS_CHANGE_KINDS)}: auto mode 'cannot add or widen "
            "write paths, worktree custody, permissions, model/provider/route families, credential "
            "slots, egress destinations or data classes, budgets, acceptance or terminal criteria, "
            "authoritative gates, review independence, integration authority, destructive actions, or "
            "outward effects', and a decomposition must preserve its declared outputs",
        )
        return None
    return changes


def check_concurrency(assessment: Assessment, document: dict[str, Any]) -> dict[str, int] | None:
    """Bounded concurrency, and recursion pinned OFF."""
    slug = "concurrency-and-recursion"
    limits = _closed_object(
        assessment, slug, document, "concurrency_limits", CONCURRENCY_KEYS, "the envelope's concurrency_limits"
    )
    if limits is None:
        return None
    concurrent = _integer(
        assessment,
        slug,
        limits,
        "max_concurrent_nodes",
        "concurrency_limits.max_concurrent_nodes",
        low=1,
        high=MAX_CONCURRENT_NODES_CEILING,
    )
    # The upper bound here is deliberately WIDE, and the pin below is what refuses a raised count. A
    # range error would be the truthful shape of the check and the wrong sentence to hand an operator:
    # "1 is outside 0..0" reads as a typo, while the doctrine reason says which separate capability
    # they reached for. A negative count has no doctrine, so the range still owns that side.
    generations = _integer(
        assessment,
        slug,
        limits,
        "max_recursion_generations",
        "concurrency_limits.max_recursion_generations",
        low=0,
        high=2**31 - 1,
    )
    if concurrent is None or generations is None:
        return None
    if generations != MAX_RECURSION_GENERATIONS:
        assessment.note(
            slug,
            f"concurrency_limits.max_recursion_generations is {generations}; recursive execution is a "
            "SEPARATE capability, and issue 16 says bounded auto mode 'is independent of ... the "
            "optional recursive-execution profile' and that 'enabling one does not enable, approve, "
            "weaken, or configure another', so an envelope may only state 0 here",
        )
        return None
    return {"max_concurrent_nodes": concurrent, "max_recursion_generations": generations}


def check_retry(assessment: Assessment, document: dict[str, Any], changes: list[str] | None) -> dict[str, Any] | None:
    """Bounded retry counts, proof-of-no-effect pinned on, and agreement with the change allowlist."""
    slug = "retry-policy"
    policy = _closed_object(assessment, slug, document, "retry_policy", RETRY_KEYS, "the envelope's retry_policy")
    if policy is None:
        return None
    attempts = _integer(
        assessment,
        slug,
        policy,
        "max_attempts_per_node",
        "retry_policy.max_attempts_per_node",
        low=1,
        high=MAX_ATTEMPTS_PER_NODE_CEILING,
    )
    total = _integer(
        assessment,
        slug,
        policy,
        "max_total_retries",
        "retry_policy.max_total_retries",
        low=0,
        high=MAX_TOTAL_RETRIES_CEILING,
    )
    proven = _boolean(
        assessment, slug, policy, "require_proven_no_effect", "retry_policy.require_proven_no_effect"
    )
    if attempts is None or total is None or proven is None:
        return None
    refused = False
    if proven is not True:
        assessment.note(
            slug,
            "retry_policy.require_proven_no_effect is false; issue 16 admits a preapproved retry only "
            "'when the prior attempt is proven no-effect or the owning read-only policy admits it', and "
            "'partial or unknown prior effect' always stops, so this posture is fixed at true",
        )
        refused = True
    retries_allowed = attempts > 1
    if retries_allowed and total < 1:
        assessment.note(
            slug,
            f"retry_policy admits {attempts} attempts per node while capping total retries at {total}: "
            "the per-node allowance could never be spent, so the two numbers describe two different "
            "envelopes",
        )
        refused = True
    if not retries_allowed and total > 0:
        assessment.note(
            slug,
            f"retry_policy admits one attempt per node while budgeting {total} total retries: a retry "
            "the per-node limit forbids cannot be drawn from a total, and an unspendable budget reads "
            "as an allowance",
        )
        refused = True
    # The BICONDITIONAL, both directions named: a retry is one of the sixteen PlanDiff change kinds, so
    # an envelope that budgets retries without allowing the change kind has preauthorized a transition
    # the compiler would refuse, and one that allows the kind without a budget has allowed nothing.
    if changes is not None:
        listed = "retry" in changes
        if retries_allowed and not listed:
            assessment.note(
                slug,
                f"retry_policy admits {attempts} attempts per node while graph_change_allowlist does not "
                "name 'retry': every autonomous graph change 'produces a new immutable WavePlan revision "
                "and PlanDiff', so a retry the allowlist omits could never be recorded",
            )
            refused = True
        if listed and not retries_allowed:
            assessment.note(
                slug,
                "graph_change_allowlist names 'retry' while retry_policy admits one attempt per node: "
                "the allowed change kind can never occur, so the allowlist entry states a permission the "
                "policy denies",
            )
            refused = True
    if refused:
        return None
    return {
        "max_attempts_per_node": attempts,
        "max_total_retries": total,
        "require_proven_no_effect": proven,
    }


def check_validity_window(
    assessment: Assessment, document: dict[str, Any], stated_at: str | None
) -> dict[str, str] | None:
    """Two real instants, strictly ordered, not retroactive, and bounded in duration."""
    slug = "validity-window"
    window = _closed_object(
        assessment, slug, document, "validity_window", WINDOW_KEYS, "the envelope's validity_window"
    )
    if window is None:
        return None
    not_before = _instant(assessment, slug, window, "not_before", "validity_window.not_before")
    not_after = _instant(assessment, slug, window, "not_after", "validity_window.not_after")
    if not_before is None or not_after is None:
        return None
    start, end = _parse_instant(not_before), _parse_instant(not_after)
    if start is None or end is None:  # unreachable: `_instant` already parsed both
        assessment.note(slug, "validity_window carries an instant that cannot be ordered")
        return None
    refused = False
    if start >= end:
        assessment.note(
            slug,
            f"validity_window.not_before {not_before} is not strictly before not_after {not_after}; a "
            "zero-width or inverted window authorizes nothing while looking like it authorizes "
            "something",
        )
        refused = True
    elif (end - start).total_seconds() > MAX_VALIDITY_SECONDS:
        assessment.note(
            slug,
            f"validity_window spans {int((end - start).total_seconds())} seconds, beyond the "
            f"{MAX_VALIDITY_SECONDS}-second bound; approval is 'for one exact WavePlan revision', and a "
            "grant that outlives the revision it was approved for is a standing grant",
        )
        refused = True
    if stated_at is not None:
        stated = _parse_instant(stated_at)
        if stated is not None and start < stated:
            assessment.note(
                slug,
                f"validity_window.not_before {not_before} precedes the envelope's stated_at {stated_at}: "
                "an envelope cannot be retroactively valid for a period before it existed",
            )
            refused = True
    return None if refused else {"not_after": not_after, "not_before": not_before}


def check_checkpoints(assessment: Assessment, document: dict[str, Any]) -> list[dict[str, Any]] | None:
    """One entry per checkpoint kind, ascending, covering the four every transition must recheck."""
    slug = "checkpoints"
    entries = document.get("checkpoints")
    if not isinstance(entries, list) or not entries:
        assessment.note(
            slug,
            f"the envelope's checkpoints is not a non-empty array (found {entries!r}); an envelope with "
            "no checkpoint never rechecks anything, which is the unbounded shape this schema exists to "
            "make unrepresentable",
        )
        return None
    kinds: list[str] = []
    for index, entry in enumerate(entries):
        where = f"checkpoints at position {index}"
        if not isinstance(entry, dict):
            assessment.note(slug, f"{where} is not a JSON object (found {entry!r})")
            return None
        checkpoint = _closed_object(assessment, slug, {"entry": entry}, "entry", CHECKPOINT_KEYS, where)
        if checkpoint is None:
            return None
        kind = _member(assessment, slug, checkpoint, "kind", CHECKPOINT_KINDS, f"{where}'s kind")
        disposition = _boolean(
            assessment, slug, checkpoint, "requires_human_disposition", f"{where}'s requires_human_disposition"
        )
        if kind is None or disposition is None:
            return None
        kinds.append(kind)
    if kinds != sorted(kinds) or len(set(kinds)) != len(kinds):
        assessment.note(
            slug,
            f"checkpoints names the kinds {kinds}, which is not a strictly ascending set; a repeat would "
            "be one obligation stated twice with two dispositions, and a reordering would give one "
            "envelope two digests",
        )
        return None
    missing = [kind for kind in MANDATORY_CHECKPOINT_KINDS if kind not in kinds]
    if missing:
        assessment.note(
            slug,
            f"checkpoints omits {missing}; issue 16 says 'every transition rechecks remaining budgets, "
            "current evidence, drift, and the narrower authority inherited by children', so an envelope "
            "missing one of those four is not the envelope that section describes",
        )
        return None
    return [{"kind": entry["kind"], "requires_human_disposition": entry["requires_human_disposition"]} for entry in entries]


def check_stop_rules(assessment: Assessment, document: dict[str, Any]) -> list[str] | None:
    """All twelve always-stop conditions, enumerated in the bytes a human approves."""
    slug = "stop-rules"
    rules = _string_list(assessment, slug, document, "stop_rules", "the envelope's stop_rules", allow_empty=False)
    if rules is None:
        return None
    if _closed_vocabulary(assessment, slug, rules, STOP_RULE_KINDS, "stop_rules") is None:
        return None
    missing = [kind for kind in STOP_RULE_KINDS if kind not in rules]
    if missing:
        assessment.note(
            slug,
            f"stop_rules omits {missing}; each named condition 'always stops' and is non-delegable, so "
            "the twelve are not selectable. They are a field rather than a constant because the writer "
            "must enumerate them in the bytes a human approves, and completing a partial list here "
            "would be the default-permissive behavior this schema refuses",
        )
        return None
    return list(rules)


def check_digest(assessment: Assessment, document: dict[str, Any], command: str, expect: str | None) -> str | None:
    """Re-derive the one digest. A recorded digest its own content does not derive is a refusal.

    For `define` there is nothing recorded yet, so the derivation happens once the body is otherwise
    admitted (in `derive_command`) and this group carries only the `--expect-digest` comparison. For
    `verify` the recorded value is the whole point.
    """
    slug = "digest"
    derived: str | None = None
    if command == "verify":
        recorded = _digest_value(assessment, slug, document.get(DIGEST_KEY), "the envelope's digest")
        derived = document_digest(document)
        if recorded is not None and recorded != derived:
            assessment.note(
                slug,
                f"the envelope records digest {recorded} which its own content does not re-derive "
                f"({derived}): the document has been edited since it was sealed, or the digest was "
                "written by something other than this derivation",
            )
    if expect is not None and derived is not None and expect != derived:
        assessment.note(
            slug,
            f"--expect-digest {expect} is not this envelope's content digest {derived}, so the supplied "
            "document is not the envelope the caller meant to bind",
        )
    return derived


# ---- admit-transition: the envelope-relative admission of ONE proposed action ----------------------


def assess_envelope(document: dict[str, Any]) -> tuple[Assessment, dict[str, Any]]:
    """Re-run the WHOLE closed envelope schema, and collect the fields admission compares against.

    An allowlist read out of an inadmissible envelope is not an allowlist, so `admit-transition` does
    not trust the supplied envelope until it has earned the same verdict `verify` would give it. The
    reasons land in their own `Assessment` and are folded into one group of the transition's result, so
    an operator sees which half of the pair is at fault.

    Every value in the returned mapping is the WELL-FORMED value or None. None means "this field cannot
    be reasoned about", and each membership check below stays silent rather than comparing against a
    field it cannot trust.
    """
    inner = Assessment()
    check_key_set(inner, document, "verify")
    envelope_id, stated_at = check_identity(inner, document)
    check_bound_plan(inner, document)
    admitted = check_authority(inner, document)
    effects = check_effects(inner, document, admitted)
    check_route_constraints(inner, document)
    posture = check_egress(inner, document)
    tools = check_tools(inner, document, admitted, posture)
    changes = check_graph_changes(inner, document)
    concurrency = check_concurrency(inner, document)
    retry = check_retry(inner, document, changes)
    window = check_validity_window(inner, document, stated_at)
    check_checkpoints(inner, document)
    stops = check_stop_rules(inner, document)
    check_digest(inner, document, "verify", None)
    # The two lists beside the posture are read from the envelope's own bytes, and only once its egress
    # group is met: `check_egress` proves both are empty, so reading them here cannot import a value
    # that check refused.
    egress: dict[str, Any] | None = None
    if posture is not None and not inner.groups["egress-allowlist"]:
        stated = document.get("egress_allowlist")
        if isinstance(stated, dict):
            egress = {
                "data_classes": list(stated["data_classes"]),
                "destinations": list(stated["destinations"]),
                "posture": posture,
            }
    return inner, {
        "admitted": admitted,
        "changes": changes,
        "concurrency": concurrency,
        "effects": effects,
        "egress": egress,
        "envelope_id": envelope_id,
        "retry": retry,
        "stops": stops,
        "tools": tools,
        "window": window,
    }


def fold_envelope_reasons(assessment: Assessment, inner: Assessment) -> None:
    """Carry the envelope's own reasons into the transition's result, each still naming its group.

    Folded rather than merged: the transition's result has one group for "the envelope this admission
    was asked against is itself inadmissible", and the envelope's group slug is preserved inside the
    sentence so nothing is lost by the flattening.
    """
    for slug in inner.slugs:
        for reason in inner.groups[slug]:
            assessment.note(
                "envelope-admissibility",
                f"the supplied envelope is itself inadmissible ({slug}): {reason}",
            )


def check_transition_key_set(assessment: Assessment, transition: dict[str, Any]) -> None:
    """The closed proposal schema: exactly the ten required keys, and NO supplied digest."""
    slug = "closed-key-set"
    expected = set(TRANSITION_BODY_KEYS)
    present = set(transition)
    for key in sorted(expected - present):
        assessment.note(
            slug,
            f"the transition carries no {key}, which the closed {TRANSITION_SCHEMA} field set requires "
            "of every proposal; default-off means an absent field refuses rather than defaulting to a "
            "permissive value",
        )
    for key in sorted(present - expected):
        if key == DIGEST_KEY:
            assessment.note(
                slug,
                "the transition already carries a digest, which is DERIVED from the proposal and never "
                "supplied: a proposal arrives unsealed, and accepting a digest would give the value the "
                "receipt binds a second origin",
            )
            continue
        assessment.note(
            slug,
            f"the transition carries the unknown field {key!r}; {TRANSITION_SCHEMA} is a closed schema, "
            "so a field this version cannot honour is refused rather than ignored",
        )
    schema = transition.get("schema")
    if "schema" in transition and schema != TRANSITION_SCHEMA:
        assessment.note(
            slug,
            f"the transition declares schema {schema!r}, not {TRANSITION_SCHEMA}, so which field set it "
            "is about is not established",
        )


def check_envelope_binding(
    assessment: Assessment, transition: dict[str, Any], derived: str, envelope_id: str | None
) -> None:
    """The binding itself: the transition must name the digest the supplied envelope actually has.

    This is the check that makes the pair a PAIR. Without it the admission would be a comparison
    against whichever envelope the caller happened to pass, and the receipt's two digests would record
    a binding nobody established. The id is compared as well, because two 64-character digests differ
    in a way no human reads and the refusal has to be legible.
    """
    slug = "envelope-digest-binding"
    bound = _closed_object(
        assessment, slug, transition, "bound_envelope", BOUND_ENVELOPE_KEYS, "the transition's bound_envelope"
    )
    if bound is None:
        return
    claimed = _digest_value(assessment, slug, bound.get("envelope_digest"), "bound_envelope.envelope_digest")
    claimed_id = _identifier(assessment, slug, bound, "envelope_id", "bound_envelope.envelope_id")
    if claimed is not None and claimed != derived:
        assessment.note(
            slug,
            f"the transition binds envelope digest {claimed}, but the supplied envelope's own content "
            f"digests to {derived}: this proposal was written against a different envelope, so nothing "
            "in it can be admitted against this one",
        )
    if claimed_id is not None and envelope_id is not None and claimed_id != envelope_id:
        assessment.note(
            slug,
            f"the transition binds envelope_id {claimed_id!r} while the supplied envelope calls itself "
            f"{envelope_id!r}; one of the two names the wrong envelope",
        )


def check_transition_identity(
    assessment: Assessment, transition: dict[str, Any], at: str
) -> None:
    """The proposal's own id and instant, and the one ordering `--at` makes checkable.

    A proposal stated AFTER the moment it is admitted is refused: the admission would be recording a
    decision about a document that did not yet exist, and the receipt would bind an instant earlier
    than the proposal it names.
    """
    slug = "transition-identity"
    _identifier(assessment, slug, transition, "transition_id", "the transition's transition_id")
    stated_at = _instant(assessment, slug, transition, "stated_at", "the transition's stated_at")
    if stated_at is None:
        return
    stated, moment = _parse_instant(stated_at), _parse_instant(at)
    if stated is not None and moment is not None and stated > moment:
        assessment.note(
            slug,
            f"the transition is stated at {stated_at}, after the admission instant {at}: a proposal "
            "cannot be admitted before it was made, so the pair of instants is refused rather than "
            "reordered",
        )


def check_admission_window(assessment: Assessment, at: str, window: dict[str, str] | None) -> None:
    """`--at` must fall STRICTLY inside the envelope's validity window; both edges refuse.

    Nothing in this family says whether the window is closed, half-open, or open at its ends, and
    default-off resolves that silence one way: on a boundary instant the window is not demonstrably
    open, so the answer is a named refusal rather than a guess that happens to be permissive. The two
    edges get two reasons because they send an operator to two different places -- too early means wait
    or re-approve, too late means the `expired-validity` stop has fired and the grant is spent.
    """
    slug = "admission-window"
    if window is None:
        return
    moment = _parse_instant(at)
    start, end = _parse_instant(window["not_before"]), _parse_instant(window["not_after"])
    if moment is None or start is None or end is None:  # unreachable: all three were parsed already
        assessment.note(slug, "the admission instant or the envelope's window cannot be ordered")
        return
    if moment <= start:
        assessment.note(
            slug,
            f"the admission instant {at} is not strictly after the envelope's not_before "
            f"{window['not_before']}: the window is not demonstrably open at its own boundary, and "
            "default-off refuses rather than reading the silence permissively",
        )
    if moment >= end:
        assessment.note(
            slug,
            f"the admission instant {at} is not strictly before the envelope's not_after "
            f"{window['not_after']}: the 'expired-validity' stop rule has fired, and an expired grant "
            "cannot be renewed by admitting one more transition under it",
        )


def check_transition_kind(
    assessment: Assessment, transition: dict[str, Any], changes: list[str] | None
) -> str | None:
    """The kind, against the compiler's sixteen and then against THIS envelope's allowlist."""
    slug = "transition-kind"
    kind = _member(assessment, slug, transition, "kind", CHANGE_KINDS, "the transition's kind")
    if kind is None or changes is None:
        return kind
    if kind not in changes:
        assessment.note(
            slug,
            f"the transition's kind {kind!r} is not in the envelope's graph_change_allowlist "
            f"{changes}; an unlisted change is refused, and rephrased prose, agent confidence, "
            "apparent urgency, a passing local check, or unused budget cannot make it permissible"
            + (
                "; an envelope that lists no graph change admits no transition at all"
                if not changes
                else ""
            ),
        )
    # The KIND is returned even when it was just refused, which is the one place this module hands a
    # rejected value onward on purpose. `check_kind_stop_rules` asks a different question about the same
    # string -- "does a carried always-stop condition name this kind" -- and returning None here would
    # silence that group for exactly the twelve widenings it exists to catch, leaving a check no test
    # could ever kill. Two true statements about one mistake, in two groups, each naming its own rule.
    return kind


def check_claimed_authority(
    assessment: Assessment, transition: dict[str, Any], admitted: list[str] | None
) -> None:
    """The claimed authority class, against the envelope's ladder prefix."""
    slug = "claimed-authority"
    claimed = _member(
        assessment, slug, transition, "claimed_authority_class", AUTHORITY_CLASSES,
        "the transition's claimed_authority_class",
    )
    if claimed is None or admitted is None:
        return
    if claimed not in admitted:
        assessment.note(
            slug,
            f"the transition claims authority class {claimed!r}, which the envelope's "
            f"allowed_authority_classes {admitted} does not admit; auto mode cannot add or widen "
            "authority, so a claim above the approved prefix is refused rather than narrowed",
        )


def check_claimed_effect(
    assessment: Assessment, transition: dict[str, Any], effects: list[str] | None
) -> None:
    """The claimed effect class, against the envelope's effect allowlist."""
    slug = "claimed-effect"
    claimed = _member(
        assessment, slug, transition, "claimed_effect_class", EFFECT_CLASSES,
        "the transition's claimed_effect_class",
    )
    if claimed is None:
        return
    if claimed in NON_DELEGABLE_EFFECTS:
        assessment.note(
            slug,
            f"the transition claims effect class {claimed!r}, which always stops and is 'non-delegable "
            "even when the envelope predicts them'; no envelope can preauthorize it, so the claim is "
            "refused independently of any allowlist",
        )
        return
    if effects is not None and claimed not in effects:
        assessment.note(
            slug,
            f"the transition claims effect class {claimed!r}, which the envelope's "
            f"allowed_effect_classes {effects} does not admit; an unlisted effect is refused",
        )


def check_declared_tool(
    assessment: Assessment, transition: dict[str, Any], tools: list[str] | None
) -> None:
    """The one declared tool class, against the envelope's tool allowlist.

    ONE tool class per transition, deliberately. An action needing two capability classes is two
    proposals or a decomposition, and each gets its own receipt. There is therefore no spelling for "no
    tool": a transition that declared none could not be checked against the allowlist at all, and an
    envelope whose `tool_allowlist` is empty admits no transition -- which is the correct reading of an
    envelope that allows no capability.
    """
    slug = "declared-tool"
    declared = _member(
        assessment, slug, transition, "declared_tool", TOOL_CLASSES, "the transition's declared_tool"
    )
    if declared is None or tools is None:
        return
    if declared not in tools:
        assessment.note(
            slug,
            f"the transition declares tool class {declared!r}, which the envelope's tool_allowlist "
            f"{tools} does not admit; an unlisted capability is refused"
            + (
                "; an envelope that lists no tool class admits no transition, because every proposal "
                "declares exactly one"
                if not tools
                else ""
            ),
        )


def check_declared_egress(
    assessment: Assessment, transition: dict[str, Any], egress: dict[str, Any] | None
) -> None:
    """The declared egress, against the envelope's posture and its two (empty) lists.

    There is no posture EQUALITY comparison here on purpose: `EGRESS_POSTURES` has exactly one member,
    so the vocabulary check above already proves the declared posture is the envelope's, and a second
    comparison would be code no test could ever kill. The subset checks are the live half, and they are
    live precisely because the envelope's lists are empty -- every named destination or data class is
    outside them.
    """
    slug = "declared-egress"
    declared = _closed_object(
        assessment, slug, transition, "declared_egress", EGRESS_KEYS, "the transition's declared_egress"
    )
    if declared is None:
        return
    posture = _member(assessment, slug, declared, "posture", EGRESS_POSTURES, "declared_egress.posture")
    destinations = _string_list(
        assessment, slug, declared, "destinations", "declared_egress.destinations", allow_empty=True
    )
    data_classes = _string_list(
        assessment, slug, declared, "data_classes", "declared_egress.data_classes", allow_empty=True
    )
    if posture is None or destinations is None or data_classes is None or egress is None:
        return
    for field, values, allowed in (
        ("destinations", destinations, egress["destinations"]),
        ("data_classes", data_classes, egress["data_classes"]),
    ):
        outside = [value for value in values if value not in allowed]
        if outside:
            assessment.note(
                slug,
                f"declared_egress.{field} names {outside}, which the envelope's egress_allowlist."
                f"{field} {allowed} does not admit under posture {posture!r}; auto mode cannot add or "
                "widen egress destinations or data classes",
            )


def check_proposed_deltas(
    assessment: Assessment,
    transition: dict[str, Any],
    concurrency: dict[str, int] | None,
    retry: dict[str, Any] | None,
) -> None:
    """The four proposed after-counts, each against the envelope's own ceiling for it.

    The ranges here are deliberately WIDE and the envelope's limit is what refuses a raised number.
    Phase A's lesson applies unchanged: "3 is outside 1..2" reads as a typo, while "3 exceeds the
    envelope's max_attempts_per_node 2" names the limit the writer walked past. A NEGATIVE count has no
    limit to exceed, so the range still owns that side.
    """
    slug = "proposed-deltas"
    deltas = _closed_object(
        assessment, slug, transition, "proposed_deltas", DELTA_KEYS, "the transition's proposed_deltas"
    )
    if deltas is None:
        return
    observed: dict[str, int | None] = {}
    for key, low in (
        ("attempts_for_node_after", 1),
        ("concurrent_nodes_after", 1),
        ("recursion_generations_after", 0),
        ("total_retries_after", 0),
    ):
        observed[key] = _integer(
            assessment, slug, deltas, key, f"proposed_deltas.{key}", low=low, high=2**31 - 1
        )
    limits: list[tuple[str, int, str]] = []
    if concurrency is not None:
        for key, limit_key in (
            ("concurrent_nodes_after", "max_concurrent_nodes"),
            ("recursion_generations_after", "max_recursion_generations"),
        ):
            limits.append((key, concurrency[limit_key], f"concurrency_limits.{limit_key}"))
    if retry is not None:
        for key, limit_key in (
            ("attempts_for_node_after", "max_attempts_per_node"),
            ("total_retries_after", "max_total_retries"),
        ):
            limits.append((key, retry[limit_key], f"retry_policy.{limit_key}"))
    # Every over-limit count earns its own reason. Four raised numbers are four separate mistakes, and
    # reporting only the first would send an operator back for a second run to find the next.
    for key, limit, where in limits:
        value = observed.get(key)
        if value is None or value <= limit:
            continue
        extra = ""
        if key == "recursion_generations_after":
            extra = (
                "; recursive execution is a SEPARATE capability, and enabling bounded auto mode does "
                "not enable, approve, weaken, or configure it"
            )
        assessment.note(
            slug,
            f"proposed_deltas.{key} is {value}, which exceeds the envelope's {where} {limit}; auto mode "
            f"cannot add or widen a limit the approved envelope narrowed{extra}",
        )


def check_kind_stop_rules(assessment: Assessment, kind: str | None, stops: list[str] | None) -> None:
    """A kind that one of the envelope's carried stop rules NAMES is refused, whatever the allowlist says.

    Independent of `transition-kind` on purpose: that group answers "this envelope did not list it",
    while this one answers "no envelope could list it, because the condition always stops". For a valid
    envelope the two overlap completely -- the twelve widenings cannot reach a graph-change allowlist --
    and the redundancy is what keeps a later widening of one from silently spending the other.
    """
    slug = "stop-rules"
    if kind is None or stops is None:
        return
    naming = [rule for rule in stops if kind in STOP_RULE_KIND_SURFACE.get(rule, ())]
    if naming:
        assessment.note(
            slug,
            f"the transition's kind {kind!r} is named by the always-stop condition(s) {sorted(naming)} "
            "this envelope carries; each of those stops is non-delegable, so the transition is refused "
            "for human disposition rather than admitted",
        )


def check_output_path(assessment: Assessment, out: str | None) -> Path | None:
    """`--out` may not exist and needs a real parent directory.

    An occupied path is a REFUSAL of the transition, not just of the write: `missing-transition-receipt`
    is one of the twelve always-stop conditions, so a transition whose receipt cannot be recorded is
    refused rather than admitted with an unrecorded receipt beside it. The receipt that records THAT
    refusal still reaches stdout, which is this command's authoritative channel.
    """
    slug = "output-path"
    if out is None:
        return None
    target = Path(out)
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
            f"the --out path {target} already exists; this command overwrites nothing, and a receipt "
            "that cannot be recorded is the 'missing-transition-receipt' stop, so the transition is "
            "refused rather than admitted against an unwritten record",
        )
        return None
    if not target.parent.is_dir():
        assessment.note(
            slug,
            f"the --out path {target} has no existing directory to be written into, so the sealed "
            "receipt would have nowhere to land",
        )
        return None
    return target


def seal_receipt(at: str, envelope: str, transition: str, verdict: str, reasons: list[str]) -> dict[str, Any]:
    """Build the one sealed receipt. Six body keys, one derived digest, nothing restated."""
    body: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "at": at,
        "envelope_digest": envelope,
        "transition_digest": transition,
        "verdict": verdict,
        "reasons": list(reasons),
    }
    sealed = dict(body)
    sealed[DIGEST_KEY] = document_digest(body)
    return sealed


def derive_transition_command(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], Path | None]:
    """Admit or refuse ONE proposed transition against ONE sealed envelope at ONE supplied instant.

    The envelope digest bound into the receipt is the one DERIVED from the supplied document, never the
    one the transition claims: the receipt records the envelope this admission actually ran against, so
    a mismatch is a refusal with a truthful receipt rather than a receipt that repeats the claim.
    """
    envelope = load_document(args.envelope, "sealed auto envelope")
    transition = load_document(args.transition, "proposed transition")
    at = args.at

    assessment = Assessment(TRANSITION_CHECKS)
    check_transition_key_set(assessment, transition)
    inner, facts = assess_envelope(envelope)
    fold_envelope_reasons(assessment, inner)
    derived_envelope = document_digest(envelope)
    check_envelope_binding(assessment, transition, derived_envelope, facts["envelope_id"])
    check_transition_identity(assessment, transition, at)
    check_admission_window(assessment, at, facts["window"])
    kind = check_transition_kind(assessment, transition, facts["changes"])
    check_claimed_authority(assessment, transition, facts["admitted"])
    check_claimed_effect(assessment, transition, facts["effects"])
    check_declared_tool(assessment, transition, facts["tools"])
    check_declared_egress(assessment, transition, facts["egress"])
    check_proposed_deltas(assessment, transition, facts["concurrency"], facts["retry"])
    check_kind_stop_rules(assessment, kind, facts["stops"])
    target = check_output_path(assessment, args.out)

    verdict = assessment.verdict("admit-transition")
    reasons = assessment.reasons()
    # Derived over the proposal AS SUPPLIED, admitted or not: the receipt has to name the exact bytes
    # that were refused, or a later audit could not tell which proposal the refusal was about.
    derived_transition = document_digest(transition)
    receipt = seal_receipt(at, derived_envelope, derived_transition, verdict, reasons)
    result = {
        "schema": TRANSITION_RESULT_SCHEMA,
        "command": args.command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": TRANSITION_CONSEQUENCE[verdict],
        "receipt": receipt,
        "receipt_digest": receipt[DIGEST_KEY],
        "envelope_digest": derived_envelope,
        "transition_digest": derived_transition,
        "wrote": None,
        "checks": assessment.document(),
        "reasons": reasons,
        "residuals": list(TRANSITION_RESIDUALS),
    }
    return result, receipt, target


# ---- verify-receipt: the sealed receipt, re-derived --------------------------------------------------


def check_receipt_key_set(assessment: Assessment, document: dict[str, Any]) -> None:
    slug = "closed-key-set"
    present = set(document)
    expected = set(RECEIPT_SEALED_KEYS)
    for key in sorted(expected - present):
        assessment.note(
            slug,
            f"the receipt carries no {key}, which the closed {RECEIPT_SCHEMA} field set requires; a "
            "receipt missing one of its six facts records an admission nobody can read",
        )
    for key in sorted(present - expected):
        assessment.note(
            slug,
            f"the receipt carries the unknown field {key!r}; {RECEIPT_SCHEMA} is closed, so a field "
            "this version cannot honour is refused rather than ignored",
        )
    schema = document.get("schema")
    if "schema" in document and schema != RECEIPT_SCHEMA:
        assessment.note(
            slug,
            f"the receipt declares schema {schema!r}, not {RECEIPT_SCHEMA}, so which field set and "
            "which digest derivation it is about is not established",
        )


def check_receipt_content(assessment: Assessment, document: dict[str, Any]) -> None:
    """The receipt's own five facts, and the ONE coherence between two of them.

    `verdict == "admitted"` and `reasons == []` are the same claim said twice, so a receipt where they
    disagree is refused in both directions: an admitted receipt carrying reasons and a refused receipt
    carrying none each record two different outcomes at once.
    """
    slug = "receipt-content"
    _instant(assessment, slug, document, "at", "the receipt's at")
    _digest_value(assessment, slug, document.get("envelope_digest"), "the receipt's envelope_digest")
    _digest_value(assessment, slug, document.get("transition_digest"), "the receipt's transition_digest")
    verdict = _member(
        assessment, slug, document, "verdict", (VERDICT_ADMITTED, VERDICT_REFUSED), "the receipt's verdict"
    )
    reasons = document.get("reasons")
    if not isinstance(reasons, list) or not all(isinstance(entry, str) and entry for entry in reasons):
        assessment.note(
            slug,
            f"the receipt's reasons is not an array of non-empty strings (found {reasons!r}), so what "
            "it records cannot be read",
        )
        return
    if verdict is None:
        return
    if verdict == VERDICT_ADMITTED and reasons:
        assessment.note(
            slug,
            f"the receipt records the verdict {VERDICT_ADMITTED!r} while naming {len(reasons)} "
            "reason(s); an admission with reasons is two outcomes recorded at once",
        )
    if verdict == VERDICT_REFUSED and not reasons:
        assessment.note(
            slug,
            f"the receipt records the verdict {VERDICT_REFUSED!r} while naming no reason; a refusal "
            "that names nothing tells an operator neither what was refused nor what to change",
        )


def derive_receipt_command(args: argparse.Namespace) -> dict[str, Any]:
    """Re-derive one sealed receipt's digest and refuse when its own content does not produce it."""
    document = load_document(args.receipt, "sealed autonomous-transition receipt")
    assessment = Assessment(RECEIPT_CHECKS)
    check_receipt_key_set(assessment, document)
    check_receipt_content(assessment, document)
    derived = document_digest(document)
    recorded = _digest_value(assessment, "digest", document.get(DIGEST_KEY), "the receipt's digest")
    if recorded is not None and recorded != derived:
        assessment.note(
            "digest",
            f"the receipt records digest {recorded} which its own content does not re-derive "
            f"({derived}): the document has been edited since it was sealed, or the digest was written "
            "by something other than this derivation",
        )
    expect = getattr(args, "expect_digest", None)
    if expect is not None and expect != derived:
        assessment.note(
            "digest",
            f"--expect-digest {expect} is not this receipt's content digest {derived}, so the supplied "
            "document is not the receipt the caller meant to bind",
        )
    verdict = assessment.verdict(args.command)
    admitted = verdict == VERDICT_VERIFIED
    return {
        "schema": TRANSITION_RESULT_SCHEMA,
        "command": args.command,
        "verdict": verdict,
        "exit_code": EXIT_OK,
        "consequence": RECEIPT_CONSEQUENCE[verdict],
        "receipt": dict(document) if admitted else None,
        "receipt_digest": derived if admitted else None,
        "envelope_digest": document.get("envelope_digest") if admitted else None,
        "transition_digest": document.get("transition_digest") if admitted else None,
        "wrote": None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RECEIPT_RESIDUALS),
    }


def write_receipt(target: Path, sealed: dict[str, Any]) -> bool:
    """Write the sealed receipt EXCLUSIVELY. A losing race costs the delivery, never an existing file.

    `"xb"` is `O_CREAT|O_EXCL`, so this cannot clobber a file that appeared between the check above and
    this write. There is no `fsync`: this module imports no `os`, which is a property Phase A's tests
    pin and this command does not spend for a convenience copy. The receipt on STDOUT is the
    authoritative channel -- `--out` is the same bytes, written for a caller that wants them on disk --
    so what is at risk on a sudden power loss is the copy, not the evidence.
    """
    payload = canonical_bytes(sealed)
    try:
        with target.open("xb") as handle:
            handle.write(payload)
            handle.flush()
    except OSError as exc:
        report_input_error(
            f"cannot write the --out path {target}: {exc}; the receipt was derived and its file may be "
            "absent or incomplete, so treat that path as unusable evidence and read the receipt from "
            "stdout instead"
        )
        return False
    return True

def derive_command(args: argparse.Namespace) -> dict[str, Any]:
    """Load the supplied document, validate it against the closed schema, then seal or verify.

    The check order is the CHECKS order, and it matters in exactly one way: a cross-field check runs
    after both fields it compares, and it stays silent when either field already has its own named
    reason. One mistake earns one reason.
    """
    command = args.command
    if command == "define":
        document = load_document(args.body, "auto-envelope body")
    else:
        document = load_document(args.envelope, "auto envelope")

    assessment = Assessment()
    check_key_set(assessment, document, command)
    envelope_id, stated_at = check_identity(assessment, document)
    bound_plan = check_bound_plan(assessment, document)
    admitted = check_authority(assessment, document)
    check_effects(assessment, document, admitted)
    check_route_constraints(assessment, document)
    posture = check_egress(assessment, document)
    check_tools(assessment, document, admitted, posture)
    changes = check_graph_changes(assessment, document)
    check_concurrency(assessment, document)
    check_retry(assessment, document, changes)
    window = check_validity_window(assessment, document, stated_at)
    check_checkpoints(assessment, document)
    check_stop_rules(assessment, document)
    derived = check_digest(assessment, document, command, getattr(args, "expect_digest", None))

    verdict = assessment.verdict(command)
    sealed: dict[str, Any] | None = None
    digest: str | None = None
    if verdict == VERDICT_DEFINED:
        # Sealed only once the body is fully admitted: an inadmissible envelope is unrepresentable in
        # the emitted document rather than emitted with a warning beside it.
        digest = document_digest(document)
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
        "envelope": sealed,
        "digest": digest,
        # Republished ONLY for an admitted envelope, and only the four facts a consumer needs before it
        # decides whether to open the document at all. A refusal republishes nothing, so no consumer can
        # read a partially admitted envelope out of one.
        "envelope_id": envelope_id if sealed is not None else None,
        "bound_plan": bound_plan if sealed is not None else None,
        "allowed_authority_classes": admitted if sealed is not None else None,
        "validity_window": window if sealed is not None else None,
        "checks": assessment.document(),
        "reasons": assessment.reasons(),
        "residuals": list(RESIDUALS),
    }


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
    advisory_stderr()(f"auto-envelope.py: {message}\n")


def emit_result(result: dict[str, Any], wrote: Path | None = None) -> int:
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
    # A file that outlives a nonzero exit is the one effect a consumer could otherwise be surprised by,
    # so when --out already succeeded every failure message below says so.
    written = f"; the sealed receipt WAS written to {wrote}" if wrote is not None else "; nothing was written"
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
    "one JSON object, or the arguments themselves are unusable; 1 an unexpected internal failure, "
    "INCLUDING a stdout that cannot receive the one result document, because an envelope sealed and not "
    "delivered is not a success. Implementation Decision 9's 3 and 4 do not apply: no command here "
    "causes an effect it could refuse before, and the one optional write is exclusive-create and "
    "all-or-nothing, so there is no partial effect to admit."
)

TRANSITION_EPILOG = (
    "Exit codes: 0 a receipt was derived, an admission and a refusal alike; 2 a supplied file cannot be "
    "read as one JSON object, or the arguments themselves are unusable -- including an --at that is not "
    "this family's YYYY-MM-DDTHH:MM:SSZ instant, which is the QUESTION being unusable rather than the "
    "answer being refused; 1 a derived receipt that could not be DELIVERED, meaning --out failed or "
    "stdout could not receive the one result document. A refusal is a RESULT at 0: it happens before "
    "anything is written, so there was no effect to refuse before, and --out is exclusive-create and "
    "all-or-nothing, so there is no partial effect to admit either."
)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(
        prog="auto-envelope.py",
        description=(
            "Define, validate, and digest the AutoEnvelope -- the last link in the planning artifact "
            "chain MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope -- and "
            "admit or refuse ONE proposed autonomous transition against one sealed envelope at one "
            "supplied instant. Read-only apart from the optional --out receipt copy, offline, "
            "clock-free, and subprocess-free: it does not enable bounded auto mode, dispatch anything, "
            "change a host permission, or authorize any act."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    define = commands.add_parser(
        "define",
        description=(
            "Validate one envelope BODY against the closed auto-envelope@1 schema and emit the sealed "
            "document: the body plus exactly one added key, `digest`. The body may not carry a digest, "
            "and nothing is normalized, so the digested bytes are the bytes the caller wrote. EVERY "
            "field is required: bounded auto mode is default-off, so an absent field refuses rather "
            "than defaulting to a permissive value. A refused body is not sealed at all."
        ),
        epilog=EPILOG,
    )
    define.add_argument(
        "--body",
        required=True,
        help=f"the unsealed {ENVELOPE_SCHEMA} body to validate and seal",
    )
    verify = commands.add_parser(
        "verify",
        description=(
            "Re-derive one SEALED envelope's digest from its own content and refuse when the two "
            "disagree. --expect-digest is the binding a later approval, transition check, or audit "
            "uses. Whether the bound plan and snapshot are current, and whether the validity window is "
            "open right now, are separate checks this command does not run."
        ),
        epilog=EPILOG,
    )
    verify.add_argument(
        "--envelope",
        required=True,
        help=f"the SEALED {ENVELOPE_SCHEMA} document to read",
    )
    verify.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the envelope's content digest is exactly this 64-character sha256",
    )
    admit = commands.add_parser(
        "admit-transition",
        description=(
            "Ask whether one SEALED auto-envelope@1 admits one UNSEALED autonomous-transition@1 "
            "proposal at the instant --at names, and emit a sealed autonomous-transition-receipt@1 "
            "either way. The envelope is re-validated against its whole closed schema first, because an "
            "allowlist read out of an inadmissible envelope is not an allowlist. Every admission check "
            "is a membership test against a list the envelope already wrote down, so an unlisted kind, "
            "authority class, effect class, tool class, egress destination, or raised count refuses by "
            "name. --at must fall STRICTLY inside the validity window: on a boundary instant the window "
            "is not demonstrably open. An admitted receipt is evidence and authorizes no dispatch."
        ),
        epilog=TRANSITION_EPILOG,
    )
    admit.add_argument(
        "--envelope",
        required=True,
        help=f"the SEALED {ENVELOPE_SCHEMA} document this admission is asked against",
    )
    admit.add_argument(
        "--transition",
        required=True,
        help=f"the UNSEALED {TRANSITION_SCHEMA} proposal to admit or refuse",
    )
    admit.add_argument(
        "--at",
        required=True,
        help=(
            "the YYYY-MM-DDTHH:MM:SSZ instant the admission is asked at; supplied, never read from a "
            "clock, and recorded verbatim in the receipt"
        ),
    )
    admit.add_argument(
        "--out",
        default=None,
        help=(
            "also write the sealed receipt to this path, which must not exist; stdout remains the "
            "authoritative channel and carries the same bytes either way"
        ),
    )
    verify_receipt = commands.add_parser(
        "verify-receipt",
        description=(
            "Re-derive one SEALED autonomous-transition-receipt@1 digest from its own content and refuse "
            "when the two disagree, so a receipt found on disk is checked by the derivation that wrote "
            "it. Whether the envelope and transition its two digests name still exist, and whether the "
            "act it records ever happened, are separate questions this command does not ask."
        ),
        epilog=TRANSITION_EPILOG,
    )
    verify_receipt.add_argument(
        "--receipt",
        required=True,
        help=f"the SEALED {RECEIPT_SCHEMA} document to read",
    )
    verify_receipt.add_argument(
        "--expect-digest",
        dest="expect_digest",
        default=None,
        help="refuse unless the receipt's content digest is exactly this 64-character sha256",
    )
    args = parser.parse_args(argv)
    expect = getattr(args, "expect_digest", None)
    if expect is not None and not _HEX64.match(expect):
        report_input_error(
            f"--expect-digest {expect!r} is not 64 lowercase hexadecimal characters, so no envelope "
            "could ever match it"
        )
        return EXIT_INPUT
    # An --at that is not this family's instant is the QUESTION being unusable, not the answer being
    # "refused": there is no moment to compare the window against, so no receipt could honestly be
    # sealed at it. Checked here, before any file is read.
    at = getattr(args, "at", None)
    if at is not None and (not _TIME.match(at) or _parse_instant(at) is None):
        report_input_error(
            f"--at {at!r} is not a YYYY-MM-DDTHH:MM:SSZ calendar instant, so there is no moment to ask "
            "the envelope's validity window about"
        )
        return EXIT_INPUT
    try:
        if args.command == "admit-transition":
            result, receipt, target = derive_transition_command(args)
            if target is not None:
                # Written BEFORE the result document, following this family: a consumer that reads a
                # result naming an `out` path must be able to open it, or the result is not delivered.
                if not write_receipt(target, receipt):
                    return EXIT_INTERNAL
                result["wrote"] = str(target)
            return emit_result(result, target)
        if args.command == "verify-receipt":
            return emit_result(derive_receipt_command(args))
        result = derive_command(args)
    except InputError as exc:
        report_input_error(str(exc))
        return EXIT_INPUT
    return emit_result(result)


if __name__ == "__main__":
    raise SystemExit(main())
