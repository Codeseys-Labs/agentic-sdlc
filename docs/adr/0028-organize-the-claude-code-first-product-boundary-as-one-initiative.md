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

ADR-0017 through ADR-0027 form one Claude Code-first product-boundary initiative. Each child retains
its own status, evidence, options, consequences, confirmation, and reversal condition. This record
provides only the registry and sequencing view; its rollup is evidence about decision progress,
never product completion or authority.

## Current child registry

| ADR | Current status | Decision |
|---|---|---|
| ADR-0017 | accepted | Claude Code is the primary product host; Core is native Claude and OCX is optional. |
| ADR-0018 | accepted | Sensitive state remains in its owning product plane. |
| ADR-0019 | accepted | Every effect requires fresh operation-specific human authority. |
| ADR-0020 | accepted | Readiness-dependent execution uses exact verified dependencies. |
| ADR-0021 | proposed | A versioned mise release is the future primary distribution topology. |
| ADR-0022 | accepted | Repository activation consumes a digest-approved assessed plan. |
| ADR-0023 | accepted | One evidence-preserving documentation profile governs product prose. |
| ADR-0024 | accepted | One approved wave executes as one artifact-driven Dynamic Workflow. |
| ADR-0025 | accepted | Immutable planning artifacts compile into bounded execution. |
| ADR-0026 | accepted | Threat analysis remains separate from human risk ownership. |
| ADR-0027 | accepted | Compatibility uses capability evidence above published minimums. |

## Current rollup

The initiative is **in progress**: ADR-0021 remains proposed; ADR-0017 through ADR-0020 and ADR-0022
through ADR-0027 are accepted. The child registry is a current generated view, not historical
metadata. Every child status transition rebuilds the registry and this rollup in the same change.
While any child remains proposed, the initiative's closed lifecycle status remains `proposed`.
ADR-0028 can become `accepted` only when every child is accepted. ADR-0021 therefore keeps this
initiative proposed until its release evidence exists.

## Sequencing

1. ADR-0017, ADR-0018, ADR-0019, and ADR-0020 settle the host, data, authority, and dependency
   foundations. They can be reviewed independently.
2. ADR-0022 uses the authority and dependency foundations to define repository activation.
3. ADR-0024 uses the host, authority, and dependency foundations to define the Core wave.
4. ADR-0025 consumes activation and workflow artifacts to define planning, drift, and bounded auto
   mode.
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
- **Confirmation:** review every ADR-0017 through ADR-0027 for one `Part-Of: ADR-0028` edge and
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
