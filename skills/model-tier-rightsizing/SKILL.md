---
name: model-tier-rightsizing
description: |
  Route workflow agents by wrong-output blast radius and verification strength. Use when
  a caller must inject a certified exact model ID and requested effort into a bounded
  dispatch, preserve a high-impact recommendation lane, or stop after null output,
  semantic uncertainty, throttling, missing readback, or unresolved transport identity.
  Stable doctrine stays here; generation-specific routing stays in one canonical reference.
---

# Model-tier rightsizing

Route the consequence of a wrong answer, not task prestige or marketing rank.

## Dispatch ladder

The stable policy has four tiers and three eligible primary pairs. A pair declares the
eligible route family; the row-specific selection condition decides which exact member can
run. Do not convert this into a provider default or a requirement to spend tokens on both.

1. **Frontier / derail:** `gpt-5.6-sol` or `claude-fable-5`. Sol carries an advisory
   frame, scale-setting recommendation, or candidate settled-truth derivation. Fable is
   eligible only for a certified bounded frontier/adversarial packet that independently
   re-derives assumptions or supplies counterexamples; it never settles truth, replaces a
   Sol peer, or runs as an unbounded fan-out. Its use also requires the current transport to
   certify the applicable retention, refusal, and capacity constraints. Settled-truth work
   stops or reduces scope if no certified peer is available.
2. **Judgment workhorse / degrade:** `gpt-5.6-terra` or `claude-opus-4-8`.
   An error may pass ordinary gates and silently weaken an artifact. Choose Terra for the
   semantic candidate or synthesis, and Opus for an immutable-delta review or another
   certified independent judgment artifact. Require explicit acceptance criteria and
   independent review of an immutable candidate.
3. **Capable volume / retry:** `gpt-5.6-luna` or `claude-sonnet-5`. A compiler, test,
   schema, deterministic comparison, evidence check, or diff makes a wrong answer visible.
   Choose the member that has the better verified transport, task fit, and independent
   perspective for the bounded artifact. This is the default for gated and cross-checked
   fan-out.
4. **Mechanical floor / redo:** use the cheapest certified member of the capable-volume
   pair when a complete deterministic check makes the result cheap to repeat. Historical
   Haiku/Spark evidence may justify a recertified fallback, but those models are not part of
   the six-primary set.

A task moves down only when a real gate changes its failure from silent damage to a
visible retry. Importance alone never moves it up. Choose inside each pair by task fit,
independent perspective, verified transport, current quota, and correlated-error risk.
There is no global provider preference and no requirement to spend tokens on all six.

## Required dispatch contract

Every delegated call or named-workflow worker consumes one provider-neutral
`RuntimeAssignment` and must state:

- a caller-injected **exact model ID** certified by the active transport; never dispatch
  from an inherited/default model or unverified alias;
- an explicit requested effort and context form, kept separate from independently observed
  provider, model identity, effective effort, and effective context telemetry;
- immutable request-injection evidence: `request_injection_status: verified`, a non-unknown
  `request_injection_source`, and non-unknown `request_injection_evidence` proving the exact
  model and effort sent by the launcher or adapter;
- independent model-identity evidence: non-unknown `resolved_provider` and
  `resolved_model_id`, `model_readback_status: verified`, a non-unknown
  `model_readback_source`, and a non-unknown `model_readback_evidence`. An independently
  observed provider/model source may honestly be `unavailable_in_transport` only when the exact
  ID maps uniquely under the versioned policy and immutable request/model evidence verifies
  identity;
- `effort_readback_status` and `context_readback_status`, each `verified` with independent
  evidence when exposed or `unavailable` with explicit source/evidence markers when the
  transport cannot expose effective effort or context behavior;
- one bounded artifact, owner, stop condition, and wrong-output class;
- the gate or independent reviewer that detects failure; and
- the fallback and escalation action before work starts.

A provider-neutral static role definition does not select a model. `resolution_state` must
equal `resolved`. Requested, inherited, unresolved, or unverified model-identity assignments
stop before dispatch. Exact request injection is mandatory and immutable. Request injection
and effective readback are different evidence classes: never copy requested values into
resolved or readback fields, and never require impossible effective effort or context readback
after request injection and model identity are verified. A requested value, host default,
alias, or echoed prompt text is not resolution evidence.

## Receipt admission boundary

`skills/model-tier-rightsizing/scripts/receipt_admission.py` validates one concrete
`RuntimeAssignment` request receipt against the versioned
`policy/runtime-assignment-receipt-v1.json`. The v1 receipt fields are exactly:
`schema_version`, `requested_model_id`, `requested_effort`, `requested_context_form`,
`request_injection_status`, `request_injection_evidence`, `resolution_state`,
`resolved_provider`, `resolved_model_id`, `model_readback_status`,
`model_identity_basis`, `model_readback_evidence`, `effort_readback_status`,
`effort_readback_evidence`, `context_readback_status`, and `context_readback_evidence`.

It rejects duplicate JSON members and arbitrary provenance strings. Each evidence field is a
policy-enumerated structured object with `source_kind`, `status`, and `schema`; request
injection evidence also binds adapter ID/version/config digest and the SHA-256 of canonical
bytes for the exact requested model, effort, and context tuple. `verified` means only that
this internal schema and digest consistency check passed. It never claims external injection,
readback, or spawn identity occurred. Effective effort and context remain `unavailable` when
the transport does not expose them; requested values never become readback.

The policy admits only certified requested tuples. Claude base tuples remain eligible; exact
Claude `[1m]` forms are denied until tuple-specific policy evidence exists. GPT `[1m]` forms
remain eligible only where calibration supports that tuple. It emits deterministic
admitted/denied JSON with a canonical JSON SHA-256 digest. It is stdlib-only.

This repository supplies no host launcher. An external harness must call admission immediately
before spawn, correlate the digest with immutable spawn evidence, and remain responsible for
no-bypass enforcement, request injection, and spawned-worker identity. Unsupported native host
paths fail closed until a host integration exists; do not replace that failure with a host
default, adapter class, scheduler, retries, journal, queue, daemon, or Evolutionary Core.

An executable Workflow call pins both fields on every worker; the second vendor is used
only when it produces a distinct artifact:

```js
const candidate = await agent(implementationPrompt, {
  model: 'gpt-5.6-terra', effort: 'xhigh', schema: Candidate,
})
const review = await agent(reviewPrompt(candidate), {
  model: 'claude-opus-4-8', effort: 'high', schema: ReviewFinding,
})
```

Do not omit either field on direct subagents, named workflows, retry workers, or reviewers.
If a host's API separates model/effort assignment from the role prompt, the dispatch receipt
must still carry the same requested values and the adapter readback state.

## Fallback discipline

Treat null, malformed, truncated, missing, or transport-rejected output as failure.
Classify transport failure versus task-output failure, apply bounded backoff, and retry the
same certified cell once. Reduce fan-out on capacity pressure, but do not silently weaken
the blast-radius class or gate. A fallback may cross lanes only when the same class and
control predicate remain true. If no certified route exists, stop or decompose into smaller
verifiable artifacts.

## Canonical calibration

Load the [canonical calibration](references/model-routing-calibration.md) before dispatch.
It is the sole human reference for current exact IDs, requested effort bands, alias
behavior, context boundaries, smoke evidence, quotas, roadmap-family lanes, vendor
complements, fallbacks, rerun triggers, and auditable receipts. Do not copy its matrices
here; recalibrate the reference when transport, lineup, telemetry, or representative results
change.
