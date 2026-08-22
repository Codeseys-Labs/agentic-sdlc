# ADR-0026 — Keep threat analysis separate from human risk ownership

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `skills/agentic-sdlc/references/evidence-discipline.md`, `VISION.md`

## Context

Agentic SDLC can use agents to build system models, enumerate threats, challenge coverage, propose
mitigations, and verify current controls. Those outputs can improve security work, but they cannot
decide business impact, risk tolerance, legal obligations, or acceptance of residual harm. A
security data-flow diagram is also only one analysis input; presenting it as the threat model would
hide dispositions, evidence, assumptions, and unresolved work.

The operator selected a native-first first-party threat-modeling workflow, versioned method and
model profiles, bounded stage fan-out, sensitive-by-default storage, human disposition, and
independent mitigation verification.

## Considered options

- **Use only an external companion or general reviewer.** Rejected because Core would have no owned
  artifact, storage, profile, or human-disposition contract for security-sensitive work; external
  companions may still complement the owned boundary.
- **Treat a generated security diagram as the threat-model verdict.** Rejected because geometry
  cannot safely own all threats, dispositions, controls, verification, assumptions, and residual
  risk.
- **Let a security agent score and accept risk.** Rejected because model output has no business,
  legal, or organizational authority and numeric scores imply unsupported precision.
- **Ship a typed first-party workflow with human risk disposition.** Chosen because automation can
  expand and test evidence inside an owned storage and profile lifecycle while people retain
  accountable risk ownership.

## Decision

1. Threat modeling is a separately selectable first-party workflow. A security DFD may be authored
   through the draw.io capability, but it is an analysis input rather than the complete model.
2. The workflow binds scoped system evidence to typed model, threat-ledger, review, mitigation, and
   verification artifacts. Model and method profiles are versioned and provenance-bearing.
3. Agents may propose prioritization, mitigation, deferment, rejection, or acceptance. Only a human
   records risk disposition under a named policy.
4. Mitigation verification is independent evidence against named current artifacts and conditions.
   It neither accepts risk nor proves universal control effectiveness.
5. Storage is sensitive by default. Local, tracked repository, and external storage are separate
   approved planes with declared audience, retention, and egress.
6. Unsupported, retired, or stale profiles stop with migration guidance. The workflow never
   substitutes another method or claims complete coverage.

This decision unblocks the threat-ledger and profile specifications. It does not assert that the
current repository ships a threat-modeling skill or that any analyzed system is secure.

## Consequences

- Positive: parallel security analysis can improve coverage without obscuring who owns residual
  risk.
- Positive: independent mitigation verification separates “implemented” from “shown effective for
  these conditions.”
- Negative: a workflow cannot close high-risk findings autonomously, so human security ownership
  remains a scheduling dependency.
- Negative: versioned profiles and sensitive storage add migration, access, and retention work.
- **Confirmation:** conformance is not yet mechanically checkable because the workflow does not
  exist. The current confirmation is independent ADR and specification review against the four
  Compliance assertions below; the implementation proposal records the missing executable checks.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0018 | Threat-model content remains in an approved sensitive storage and egress plane. |
| Depends-On | ADR-0019 | Agent analysis and verification never create human risk disposition or effect authority. |
| Relates-To | ADR-0023 | Threat-model prose and handoffs use the same evidence-preserving documentation profile. |
| Relates-To | ADR-0024 | The workflow uses bounded stage fan-out and immutable fan-in artifacts. |
| Part-Of | ADR-0028 | This record decides threat-model authority and artifacts inside the Claude Code-first product initiative. |

## Compliance

- No agent-authored field records human risk acceptance.
- A security DFD is never labeled as the complete threat model or a security verdict.
- Every mitigation-verification result names the exact control artifacts and verification conditions.
- Missing or stale profiles stop; no silent method substitution occurs.

## Reversal condition

If an accountable organization adopts a formally delegated machine risk-disposition authority with
auditable policy, identity, revocation, and liability semantics, the security owner re-examines
only the disposition boundary for that organization.
