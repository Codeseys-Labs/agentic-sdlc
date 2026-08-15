# ADR-0018 — Keep sensitive product state in its owning plane

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `AGENTS.md`, `commands/sdlc-rightsize.md`, `scripts/gate_receipt.py`

## Context

Agentic SDLC crosses distribution, Claude host, routing, repository, local evidence, and external
system boundaries. Those planes have different owners, credentials, retention rules, and outward
effects. A shared “agent session” boundary would let a convenient implementation copy credentials,
source, prompts, provider data, or issue bodies into receipts and logs that outlive their purpose.

Current code already preserves important fragments of this boundary: external libraries keep their
own front doors, gateway launch reads but does not copy credential values, and rightsizing excludes
raw prompts and completions. The product contract needs one default that governs every new surface.

## Considered options

- **Centralize all state for complete replay and analytics.** Rejected because one compromise or
  retention mistake would expose every plane and because replay value does not justify credential
  or private-content duplication.
- **Let each feature choose its own privacy behavior.** Rejected because inconsistent defaults are
  hard to audit and silently turn optional features into egress channels.
- **Keep values in their owning planes and exchange minimized typed evidence.** Chosen because it
  supports recovery and explanation without making Agentic SDLC a new credential or content store.

## Decision

1. Each product plane retains custody of its credentials, sensitive content, configuration, and
   external retention choices.
2. Plane crossings use declared egress: destination, purpose, data classes, call or cost budget,
   and external retention boundary are reviewed before transmission.
3. Durable operational evidence contains only the minimum typed facts needed for identity,
   recovery, accounting certainty, and traceability. Raw credentials, prompts, completions,
   transcripts, source bodies, and secret-shaped values are excluded.
4. Agentic SDLC ships no product telemetry. External host and provider telemetry remains a named
   third-party boundary.
5. Active, partial, unknown-effect, and incident evidence is retained while recovery or audit needs
   it. Normal terminal evidence follows published bounded retention defaults; history is preserved
   unless a separately designed purge contract is later approved.

This decision unblocks shared journal and receipt schemas. It does not prove that every current
script conforms and authorizes no data transmission.

## Consequences

- Positive: credentials and private content do not become duplicated product-owned state.
- Positive: recovery, accounting, and incident handling can share typed metadata without sharing
  sensitive bodies.
- Negative: some diagnoses cannot be reconstructed from product receipts alone and require the
  operator to inspect the owning host or provider plane.
- Negative: every new networked feature must declare data classes and retention instead of relying
  on a broad online-mode consent.
- **Confirmation:** run `mise run secrets` and review generated schemas and network call sites
  against the exclusions in this record. No current single command proves all egress behavior.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Relates-To | ADR-0014 | ADR-0014 is an existing credential-custody example; this record makes no change to its gateway contract. |
| Relates-To | ADR-0015 | ADR-0015 is an existing minimized-evidence example; this record does not narrow its evaluator contract. |
| Relates-To | ADR-0009 | External libraries remain a distinct operator-owned plane using their own front doors. |
| Part-Of | ADR-0028 | This record decides the data-custody boundary inside the Claude Code-first product initiative. |

## Compliance

- No product-owned artifact stores credential values or secret-shaped material.
- Every product network transmission has a declared destination, purpose, data class, and budget.
- Unknown usage or cost is labeled, never converted to zero.
- No ordinary command transmits Agentic SDLC analytics or diagnostics to a product telemetry service.

## Reversal condition

If a required recovery or regulatory obligation is demonstrated to be impossible with minimized
typed evidence, the product owner re-examines the affected data class and plane; convenience or
analytics alone does not trigger reversal.
