# Define the multi-provider support promise

Type: grilling
Status: resolved
Blocked by: 01, 02
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What may the product promise when it says Claude Code can use multiple models from multiple
providers? Define the supported route classes, qualification and freshness rules, Claude
subscription behavior, provider credential ownership, failure and fallback semantics, version
compatibility, and the line between reachable, tested, qualified, and supported.

## Answer

### Promise and route classes

Agentic SDLC distinguishes four evidence levels:

- **reachable** — present in the live OCX catalog and requestable, with no reliability claim;
- **tested** — one bounded canary succeeded against a timestamped runtime combination;
- **qualified** — the exact route passed the required compatibility and identity checks within
  the freshness window; and
- **supported** — Agentic SDLC publishes that currently qualified combination in its compatibility
  matrix and maintains onboarding, diagnostics, and regression coverage for it.

Support applies to an exact route and version combination, not to an entire provider or every
model it exposes.

The supported route classes are:

1. ordinary `claude` using the user's Claude subscription models;
2. Claude passthrough under `ccodex`, forwarding genuine Claude model IDs through the user's same
   subscription; and
3. exact, qualified non-Claude model routes under `ccodex` through the OCX gateway.

The third class is supported by Agentic SDLC but explicitly unsupported by Anthropic as a Claude
Code configuration. `ccodex` therefore means OCX catalog models plus the user's Claude
subscription models in one session. Provider switches or Console API keys that bypass OCX are
refused rather than treated as additional route classes.

### Credential and control-plane boundary

Claude Code continues to own the login in the user's normal `~/.claude` state. Non-Claude
provider credentials remain operator-owned and are managed through OCX or the provider's approved
mechanism. Agentic SDLC never copies, persists, migrates, prints, or silently converts credential
values. It may report credential availability and route readiness without revealing values;
missing or ambiguous credentials fail closed with provider-specific guidance.

`ccodex` is the self-describing control surface for routed models. A session may use it to inspect
the live catalog, effective versions, credential availability, route readiness, compatibility,
qualification receipts, receipt age, and the reason a route is reachable, qualified, stale, or
blocked. Exact command names remain an installation-experience decision.

When qualification is absent or stale, `ccodex` offers an active canary. The canary requires
explicit approval because it can incur provider cost and data egress. `ccodex` orchestrates and
records the test, but a model cannot qualify itself from its own claim; the receipt requires
independent route and model evidence.

### Qualification and failure behavior

A qualification certificate binds the exact provider and model ID, OCX version, Claude Code
compatibility range, required tool surface, and observed route identity. The canary exercises real
workflow dispatch and required tool use rather than accepting a text-only response.

Qualification expires after 30 days or immediately after a material model, provider, gateway, or
Claude Code change. A tested result remains historical evidence, while qualified and supported
require a current certificate. Thirty days is the maximum cached age, not a waiting period: a
session can request an approved refresh at any time. An expired route remains visible as reachable
but is not selected automatically.

The runtime never silently substitutes a model, provider, or native-Claude route. It retries the
same route only under a bounded, predeclared policy. A fallback route must be present in the
reviewed workflow plan, independently qualified, and approved before execution. Otherwise the
affected node stops and reports the route, failure class, attempts, and retained artifacts; the
operator may then retry, choose another qualified route, or continue through native Claude.

### Certificate identity and post-failure route changes

**Spec-alignment decisions, 2026-08-24.** These two decisions constrain the routed-model profile
work — Slice 7 of the [product specification](../agentic-sdlc-product-spec.md), whose scope
carries the rightsizing qualification handoff — and they govern wherever they disagree with the
shorter statements above.

1. **The certificate binds the canonical exact route tuple by reference.** The field list under
   "Qualification and failure behavior" is not the certificate's identity. That identity is the
   exact route identity of Implementation Decision 34 — transport, route kind, provider lane,
   endpoint/region where relevant, credential slot, exact model, effort, context, tools,
   auth/billing basis, and identity readback basis — recorded canonically as the exact route tuple
   in [the rightsizing and task-map answer](15-refine-model-rightsizing-and-task-map.md), whose
   route ID digests the whole tuple, together with the task pack, harness, runtime, settings,
   class, and verifier that a class qualification binds under Implementation Decision 36.
   Re-enumerating those fields here would drift from that tuple, so this answer defers to it
   instead of restating it. Nominally equal models on different tuples qualify separately, so a
   certificate is evidence for its own tuple and class only and can never be read across to
   another entitlement, credential slot, effort, or context.

2. **Continuing through native Claude after a routed failure needs its own approved plan.** Native
   Claude is a distinct credential and support surface (Implementation Decision 47) and a separate
   route family that cannot be created, shadowed, or relabeled as an OCX provider profile
   ([the provider-onboarding answer](19-define-provider-onboarding-and-route-control-ux.md)), so
   selecting it after a stop is a route change rather than a retry. Implementation Decision 51
   admits a change of provider, model, slot, effort, context, or route only through an already
   qualified and approved alternative, and Implementation Decision 39 requires every fallback to
   be exact, qualified, plan-declared, and preapproved. The operator's options after the stop above
   are therefore a bounded same-route retry, an alternative the reviewed plan already predeclared
   and that is currently qualified, or a new approved plan. A native-Claude continuation the plan
   did not predeclare is the last of those, and the node stays stopped until that approval exists.
