# ADR-0019 — Require fresh human authorization for every effect

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `AGENTS.md`, `VISION.md`, `skills/agentic-sdlc/SKILL.md`

## Context

This product creates plans, candidates, reviews, test results, route evidence, receipts, and queue
updates. Each is useful evidence, but none answers whether a mutation may occur now against the
current target. Treating a green gate, accepted ADR, reviewer verdict, or agent recommendation as
permission would let stale or substituted evidence authorize a different effect.

Current instructions already repeat “evidence is not authority,” and ADR-0004 protects operator-
gated adoption. The resolved workflow contract extends the same boundary to repository writes,
fan-in, provider calls, trust changes, publication, and all external systems.

## Considered options

- **Let successful gates and reviews authorize the next step.** Rejected because those artifacts do
  not bind current target prestate, scope, or human intent.
- **Approve an entire mission once and let agents broaden it.** Rejected because discoveries and
  drift can silently change routes, egress, budget, candidate identity, or effect.
- **Bind fresh human grants to exact operations and evidence.** Chosen because stale or changed
  inputs become visible and require disposition before effect.

## Decision

1. Every effect requires a current operation-specific human authorization bound to the exact plan
   digest, target, prestate, scope, routes, egress, budgets, evidence, and named effect.
2. A changed bound value expires or supersedes the grant. No agent, reviewer, conductor, gate,
   queue record, ADR, receipt, or model output may create or broaden authority.
3. Fan-in and outward publication are separate authorization boundaries. A fan-in grant never
   implies push, PR mutation, merge, deployment, release, credential use, or external messaging.
4. Auto mode may consume only transitions already named in an approved bounded envelope. It cannot
   bypass host permission controls or create a new mission root.
5. Controls are labeled mechanical, observed, or advisory. Documentation never promotes an
   advisory request or observed outcome into a fail-closed guarantee.

This decision unblocks common approval and effect-state schemas. It does not itself authorize any
implementation, queue mutation, integration, or publication.

## Consequences

- Positive: every mutation can be traced to a human grant over the exact state it changed.
- Positive: independent review and tests retain their proper role as evidence rather than becoming
  accidental permission channels.
- Negative: material drift and every outward effect add explicit human stops, even when automation
  is otherwise capable of continuing.
- Negative: auto mode is less autonomous than systems that treat a broad initial prompt as durable
  permission.
- **Confirmation:** review effectful command paths for a digest-bound grant and run `mise run check`.
  The gate proves conformance tests only and remains non-authorizing.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Relates-To | ADR-0004 | ADR-0004 is the existing self-improvement instance; this record governs a broader product authority boundary without narrowing it. |
| Relates-To | ADR-0016 | Explicit yolo remains a host permission profile and never supplies product effect authority. |
| Relates-To | ADR-0015 | Evaluation authorization remains limited to the exact approved evaluation plan. |
| Part-Of | ADR-0028 | This record decides the effect-authority boundary inside the Claude Code-first product initiative. |

## Compliance

- Every effectful product command names the authorization it consumes and the exact effect it may perform.
- A gate, review, queue status, receipt, or ADR never changes an approval state by itself.
- Changed scope, target, evidence, route, egress, or budget requires a new human disposition.
- Fan-in and publication consume different grants.

## Reversal condition

If the operator adopts a formally delegated authority system that can prove equivalent identity,
scope, expiry, non-broadening, and revocation semantics for a named effect class, the product owner
re-examines only that class.
