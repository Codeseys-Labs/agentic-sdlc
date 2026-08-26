# ADR-0028 — Organize the Claude Code-first product boundary as one initiative

- **Status:** proposed
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `VISION.md`, `README.md`, `AGENTS.md`, `docs/adr/0017-make-claude-code-the-primary-product-host.md`

## Context

The Claude Code-first product boundary spans eleven decisions. They share one outcome but remain
separable: host priority, data custody, effect authority, dependency identity, distribution,
repository activation, documentation, workflow execution, planning, threat modeling, and
compatibility. Without one initiative, a reader can see individual dependencies but not the
sequence that makes an executable Core journey possible.

Combining all eleven choices in one record would create a mega-record whose options and reversal
conditions could not be reviewed independently. Keeping only loose links would hide the critical
path and let a downstream record appear ready while a load-bearing parent remained proposed.

## Scope boundary

This initiative organizes product-boundary decisions. It does not specify schemas, CLI arguments,
renderer implementations, route catalogs, model tiers, tracker migrations, or build tickets. It
does not replace existing ADRs for rightsizing, external libraries, gateway login, or yolo.

## Considered options

- **One combined product ADR.** Rejected because eleven distinct choices would share one status and
  one reversal condition, preventing partial review or later supersession.
- **Independent ADRs with only pairwise links.** Rejected because the release and Core-journey
  sequence would remain implicit across more than five related records.
- **One initiative with separate child records.** Chosen because it exposes scope and sequencing
  while preserving one decision per child.

## Decision

ADR-0017 through ADR-0027, together with every later record that declares a `Part-Of: ADR-0028`
edge (currently ADR-0030), form one Claude Code-first product-boundary initiative. Each child
retains its own status, evidence, options, consequences, confirmation, and reversal condition.
This record provides only the registry and sequencing view; its rollup is evidence about decision
progress, never product completion or authority.

## Current child registry

| ADR | Current status | Decision |
|---|---|---|
| ADR-0017 | accepted | Claude Code is the primary product host; Core is native Claude and OCX is optional. |
| ADR-0018 | accepted | Sensitive state remains in its owning product plane. |
| ADR-0019 | accepted | Every effect requires fresh operation-specific human authority. |
| ADR-0020 | accepted | Readiness-dependent execution uses exact verified dependencies. |
| ADR-0021 | proposed (amended 2026-08-26) | A versioned mise release is the future primary distribution topology; its lifecycle is one top-level verb family over (agent, scope, root), and the project-scope grant unit is a plane rather than a file. |
| ADR-0022 | accepted (amended 2026-08-22) | Repository activation is a classify-then-shown-diff apply lifecycle; the transaction engine, plan digest, machine receipt, and terminal readiness vocabulary are retired. |
| ADR-0023 | accepted | One evidence-preserving documentation profile governs product prose. |
| ADR-0024 | accepted (amended 2026-08-23) | One approved wave is one bounded execution, today as worktree subagents; the Dynamic Workflow DAG substrate is aspirational pending live-host proof. |
| ADR-0025 | superseded by ADR-0030 | Immutable planning artifacts compile into bounded execution — withdrawn; the scope/authority human-disposition rule survives in the sealed mission contract's stop conditions. |
| ADR-0026 | accepted | Threat analysis remains separate from human risk ownership. |
| ADR-0027 | accepted | Compatibility uses capability evidence above published minimums. |
| ADR-0030 | accepted | Wave evidence is recorded in Git and one markdown file per wave; the typed planning stack is withdrawn. |

## Current rollup

The initiative is **in progress**: ADR-0021 remains proposed; ADR-0017 through ADR-0020, ADR-0022
(as amended 2026-08-22), ADR-0023, ADR-0024 (as amended 2026-08-23), ADR-0026, ADR-0027, and
ADR-0030 are accepted; ADR-0025 is superseded by ADR-0030, which carries its surviving rule. The
child registry is a current generated view, not historical metadata. Every child status transition
rebuilds the registry and this rollup in the same change; ADR-0030's landing and ADR-0025's
supersession on 2026-08-22 missed that rule, and this 2026-08-23 rebuild repairs the omission.
While any child remains proposed, the initiative's closed lifecycle status remains `proposed`.
ADR-0028 can become `accepted` only when every child is accepted or superseded by an accepted
successor inside the initiative. ADR-0021 therefore keeps this initiative proposed until its
release evidence exists.

## Sequencing

1. ADR-0017, ADR-0018, ADR-0019, and ADR-0020 settle the host, data, authority, and dependency
   foundations. They can be reviewed independently.
2. ADR-0022 uses the authority and dependency foundations to define repository activation.
3. ADR-0024 uses the host, authority, and dependency foundations to define the Core wave.
4. ADR-0025 consumed activation and workflow artifacts to define planning, drift, and bounded auto
   mode; ADR-0030 superseded it and records wave evidence in Git and one markdown file instead.
5. ADR-0023 and ADR-0026 add documentation and threat-model surfaces under the same authority and
   data boundaries.
6. ADR-0027 defines compatibility admission over the host and dependency boundaries.
7. ADR-0021 remains proposed until ADR-0011's release-artifact reversal condition fires; it does not
   block specification of the Core journey in a development checkout.

## Consequences

- Positive: reviewers can follow one critical path without merging independent decisions.
- Positive: one child can remain proposed without making accepted siblings look incomplete or
  silently binding the child.
- Negative: the initiative adds a twelfth record and a current child registry plus rollup that must
  be rebuilt in the same change as every child status transition.
- Negative: the rollup can be mistaken for delivery progress unless every view repeats that ADR
  states are decision evidence only.
- **Confirmation:** review every ADR-0017 through ADR-0027 and ADR-0030 for one
  `Part-Of: ADR-0028` edge and
  compare its dependency edges with the Sequencing section. This is a current, read-only review;
  it authorizes no status or implementation effect.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Relates-To | ADR-0011 | The proposed distribution child remains gated by ADR-0011's observable release condition. |
| Relates-To | ADR-0015 | Existing rightsizing promotion remains outside this initiative and supplies one routing constraint. |

## Compliance

- Every child record carries a `Part-Of: ADR-0028` edge.
- The initiative never substitutes its status for a child record's lifecycle state.
- A proposed child is not presented as a current product constraint.
- The initiative rollup never claims implementation, readiness, release, or effect authority.

## Reversal condition

If the initiative has fewer than five non-superseded child decisions after later consolidation,
the ADR owner re-examines whether pairwise relationships are sufficient and this rollup should be
deprecated.

## Amendment — 2026-08-26: the registry is reconciled with the front-door train, and no status moved

The agentic-sdlc-7a2b wave train (gh #8, gh #11, gh #10) landed the top-level verb family, the v2
activation-receipt body, and the (agent, scope, root) receipt-and-pointer plane, and ADR-0021 carries
a dated amendment for the first and third. This section records the reconciliation, because the rule
above — "Every child status transition rebuilds the registry and this rollup in the same change" —
was written for transitions and left an amendment's registry visibility unstated, which is how
ADR-0022's and ADR-0024's amendment dates came to appear in the registry by convention rather than by
rule. The rule is now read as covering both: a child's registry row states its amendment date.

**What changed:** ADR-0021's row alone, to `proposed (amended 2026-08-26)`, with its decision summary
widened to name the verb family and the plane-sized grant unit. Nothing else.

**What did NOT change, and was verified rather than assumed** (each read against the tree on
2026-08-26, not inherited from the plan):

- **The rollup is unaffected on the axis it measures.** ADR-0021 is still `proposed`, so the
  initiative's closed lifecycle status is still `proposed`, and the "ADR-0021 therefore keeps this
  initiative proposed until its release evidence exists" sentence stands verbatim. An amendment is
  not a transition: the train changed what the child decides, not whether it is decided. ADR-0021's
  own amendment records why `accepted` was not this train's to grant — ADR-0011's supersession
  condition requires a **new** superseding ADR (`docs/adr/0011-...:163`), which no wave wrote.
- **ADR-0022's row does not disagree with the live `recover` plan digest.** The row says the plan
  digest is retired, and the digest the front-door train exercises is a different object: ADR-0022's
  was an approve-then-write authorization over a repository activation, while `recover`'s resumes one
  already-armed pending transaction and is re-derived from live state at apply time. The plan's §3.6
  states the distinction as doctrine; the registry row needed no edit, and editing it would have
  implied a supersession that did not happen.
- **ADR-0027's row does not need widening for the Codex plane.** Wave WX added a codex compatibility
  row to `policy/release-contract.v1.json` with its own capability evidence
  (`docs/evidence/2026-08-25-codex-host-plane.md`), which is ADR-0027's rule being *applied* rather
  than changed. The row states the rule.
- **Every child still carries its `Part-Of: ADR-0028` edge**, ADR-0021's included, so the
  Confirmation section's review remains runnable as written.

**One thing this amendment does not do:** it does not reconcile the registry with the product spec.
`docs/plans/claude-code-first-harness/agentic-sdlc-product-spec.md` Implementation Decision 91 still
enumerates the retired `ccodex sdlc` namespace, and moving it is product-decision work the spec's own
preamble routes back to its owner rather than to a documentation wave. The predicate that blocked
even a compatible addition there was relaxed in the same wave (seed agentic-sdlc-a010), so the edit
is unblocked and outstanding, not unblocked and done.
