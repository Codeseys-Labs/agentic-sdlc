# ADR-0025 — Compile execution from immutable planning artifacts

- **Status:** superseded by ADR-0030
- **Date:** 2026-08-22
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `commands/sdlc-frame.md`, `skills/agentic-sdlc/references/deep-work-loop.md`

## Context

The current Frame emits a short prose plan. Large or resumed work needs stronger continuity: the
system must distinguish the operator's mission, the observed repository snapshot, the compiled
wave plan, later plan changes, and the bounded autonomy grant. If these remain one mutable document
or chat thread, drift can be hidden as “continuation” and auto mode can broaden itself without a
new approval.

The operator selected plan-first behavior, explicit drift correction, human-gated execution by
default, and an optional bounded auto mode. A deterministic compiler is the boundary between
deliberative planning and effectful workflow execution.

## Considered options

- **Execute directly from the latest conversational plan.** Rejected because the input is mutable,
  difficult to digest, and cannot distinguish approved intent from later agent interpretation.
- **Give auto mode broad permission to keep the mission moving.** Rejected because it lets the
  system redefine scope, routes, budgets, or authority when evidence changes.
- **Compile immutable typed planning generations and diff them explicitly.** Chosen because every
  execution and continuation can bind to one reviewed generation.

## Decision

1. Mission intent, repository snapshot, compiled wave plan, plan difference, and bounded auto grant
   are separate immutable, versioned artifacts.
2. A deterministic read-only compiler produces an execution candidate from admitted inputs. The
   compiler makes no model call, repository mutation, queue mutation, or external effect.
3. Admission binds the exact artifact digests. Changed input, plan, queue, route, budget, target, or
   evidence creates a new generation and invalidates prior execution approval.
4. Drift is classified as evidence refresh, plan correction, scope change, or authority change.
   Only the first two may remain within a previously approved boundary when their policy says so;
   scope and authority changes return for human disposition.
5. Human approval is the default. Auto mode operates only inside an explicit `AutoEnvelope` with
   closed transitions, limits, pause conditions, and expiry. It never selects permission bypass.
6. Resume revalidates bound state and continues from durable artifacts. It never invents missing
   progress, approvals, effects, or model identity from chat history.

This decision unblocks planning schemas and the compiler interface. It does not authorize
execution or imply that the current Frame command already emits these artifacts.

## Consequences

- Positive: plan review, execution, drift, and continuation become independently inspectable and
  reproducible.
- Positive: auto mode is a bounded transition policy rather than a vague autonomy setting.
- Negative: every meaningful plan change creates a new generation and may require another human
  review even when the intended outcome is unchanged.
- Negative: durable planning artifacts add schema migration and retention obligations.
- **Confirmation:** conformance is not yet mechanically checkable because the compiler does not
  exist. The current confirmation is independent ADR and specification review against the four
  Compliance assertions below; the implementation proposal records the missing executable checks.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0019 | Plan admission and auto envelopes cannot create or broaden human authority. |
| Depends-On | ADR-0022 | Repository activation supplies the admitted repository contract and local readiness inputs. |
| Depends-On | ADR-0024 | The compiled plan is the immutable input to one bounded Dynamic Workflow wave. |
| Part-Of | ADR-0028 | This record decides plan compilation inside the Claude Code-first product initiative. |

## Compliance

- The compiler has no write, network, model, queue, or credential capability.
- Every execution names exact planning-generation digests.
- Scope or authority drift always stops for human disposition.
- Resume reports missing or stale evidence and never fabricates continuity.

## Reversal condition

If three independently reviewed plan corrections within one release retain the same mission scope
but are refused solely because the artifact generations invalidate one another, the planning owner
re-examines the generation boundaries, not the human-authority rule.
