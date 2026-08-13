# `model-task-map.json` v2 schema

Companion to [`sdlc-rightsize`](../../../commands/sdlc-rightsize.md). The command emits a
three-file recommendation at `<target>/.agentic-sdlc/model-task-map.{json,md}` plus
`model-task-map.evidence.json`. Calibration owns semantic policy, the local evaluator owns
measurement, and the external authenticated harness remains the only runtime admission and
spawn authority.

Links: [SKILL](../SKILL.md) · [calibration](model-routing-calibration.md) ·
[benchmark evidence](model-benchmark-evidence-2026-08-12.json) ·
[prompt budget](workflow-prompt-budget.md)

> A map is a recommendation, not a dispatch receipt or authorization. A selected route is
> dispatchable only when the map records both `role-qualified` local evidence and admission by
> the checked-in `runtime-assignment-receipt-v1.json`; the external harness still injects and
> validates the concrete `RuntimeAssignment` immediately before spawn.

## Artifact trio

| Artifact | Schema | Contents |
|---|---|---|
| `<stem>.json` | `model-task-map/v2` | run specification, route registry, eight recommendations, structured controls |
| `<stem>.md` | rendered v2 | same recommendation, blocked evidence, limitations, regeneration command |
| `<stem>.evidence.json` | `rightsize-evidence/v1` | task/output digests, closed attribution excerpts, local metrics, Pareto inputs |

Raw prompts, output, transcripts, repository content, credentials, PII, secret-shaped values,
and mutable absolute paths are forbidden in all three artifacts.

## Exact route shape

A model name is not a route. Every primary, complement, fallback, and route-registry member has
one closed exact tuple:

```json
{
  "transport_surface": "claude-code-gateway",
  "route_kind": "gateway-routed-provider",
  "provider": "openai",
  "auth_basis": "provider-credential",
  "billing_basis": "api-token",
  "requested_model_id": "gpt-5.6-luna",
  "requested_effort": "high",
  "requested_context_form": "base",
  "route_id": "sha256 of the exact tuple",
  "qualification_state": "role-qualified",
  "runtime_policy_admitted": true,
  "dispatchable_recommendation": true
}
```

Claude subscription passthrough uses:

```json
{
  "transport_surface": "claude-code-gateway",
  "route_kind": "gateway-claude-subscription-passthrough",
  "provider": "anthropic",
  "auth_basis": "operator-claude-login",
  "billing_basis": "claude-subscription",
  "requested_model_id": "claude-opus-4-8",
  "requested_effort": "high",
  "requested_context_form": "base"
}
```

The passthrough route is not an OCX catalog row or a separate provider plane. Registry presence,
configured provider, exact live catalog member, route probe, role qualification, and runtime
policy admission remain distinct facts.

## Top-level map

```json
{
  "schema_version": "model-task-map/v2",
  "calibration_id": "revision|target|catalog|task-pack|benchmark|evidence|evaluator",
  "generated_from_evidence_sha256": "sha256",
  "generated_content_sha256": "sha256",
  "run_spec": {
    "schema_version": "rightsize-run-spec/v1",
    "routes": ["exact route tuple"],
    "task_classes": ["mechanical_redo"],
    "task_pack": "builtin:harness-smoke-v1",
    "evaluation_depth": "pilot",
    "pareto_objective": "api-equivalent-cost",
    "attempts_per_task": 1,
    "budgets": {
      "max_calls": 10,
      "max_wall_seconds": 600,
      "max_api_equivalent_usd": 5
    },
    "expected_peak_input_tokens": 100000,
    "allow_usage_credits": false,
    "target_data_egress_acknowledged": false,
    "output": ".agentic-sdlc/model-task-map.json",
    "regenerate": false,
    "force": false
  },
  "route_registry": [
    {
      "route": "exact route tuple",
      "discovery_state": {
        "catalog_present": true,
        "live": true,
        "effort_vocab": ["low", "medium", "high", "xhigh", "max"],
        "effort_vocab_source": "ocx-live-models",
        "reported_context_tokens": 372000,
        "runtime_policy_admitted": true,
        "blockers": []
      },
      "context_state": {
        "required_tokens_with_margin": 110000,
        "requested_capacity_ceiling": 372000,
        "capacity_source": "ocx-live-models",
        "fits": true,
        "served_context_readback": "unavailable"
      },
      "evaluation_eligible": true,
      "blockers": []
    }
  ],
  "map": {
    "mechanical_redo": {
      "classification": {
        "blast_radius": "local/reversible",
        "determinism_of_gate": "complete",
        "scope_of_mutation": "one bounded artifact",
        "authority_proximity": "none",
        "corpus_size": "small",
        "dependency_fanout": "none"
      },
      "primary": "structured exact route or null",
      "complement": "structured exact route or null",
      "fallback": ["structured exact routes"],
      "measured_pareto_front": ["route sha256"],
      "dispatch_pareto_front": ["role-qualified and runtime-admitted route sha256"],
      "gate": "complete",
      "kill_criteria": "stop on route/identity failure, missing control, budget exhaustion, or unresolved context",
      "status": "recommended"
    }
  },
  "authority_boundary": "recommendation only; not a dispatch receipt or authorization"
}
```

`map` always has exactly these eight keys:

1. `mechanical_redo`
2. `deterministic_gated_change`
3. `evidence_extraction`
4. `repository_discovery`
5. `semantic_implementation`
6. `semantic_review`
7. `integration_reconcile`
8. `authority_or_frontier`

If the selected task pack has no compatible local evidence for one class, the key remains and its
status is `blocked-no-compatible-local-evidence`; absence never implies a host default.

## Evidence contract

`rightsize-evidence/v1` records:

- normalized non-sensitive run specification and authorization digest;
- target, catalog, task-pack, benchmark-snapshot, request-tuple, launcher, task-input, and output digests;
- whitelisted gateway attribution fields correlated by `requestId`, plus the count of malformed
  lines in the post-call JSONL snapshot; any nonzero count makes attribution inadmissible;
- accepted/verifier result and failure class;
- input, uncached input, cache-read, cache-write, reasoning, visible output, and total tokens;
- wall time, first-output latency, and model/tool steps;
- cost and quota values with provenance;
- per-task-class summaries and non-dominated route IDs.

Requested effort and context are separate from effective readback. The latter remains
`unavailable` unless the transport independently reports it. A routed OCX row may expose an
`effort_vocab` with `effort_vocab_source: ocx-live-models`. Claude passthrough records an empty
vocabulary with source `unavailable`; checked-in tuple admission may permit the request but is not
observed route vocabulary.

## Qualification and Pareto rules

The local ladder is `catalog-only` → `route-probed` → task-class-scoped `role-qualified`.
`builtin:harness-smoke-v1` can produce pilot evidence only. Qualification requires a fixed,
target-representative pack with at least five distinct held-out tasks in every selected class,
three attempts per task, at least 90% accepted attempts, a 95% Wilson lower bound of at least
0.70, zero route/identity failures, and zero critical-task failures. A newly qualified route
remains production-blocked until runtime policy admits the exact model/effort/context tuple.

The evidence preserves a `measured_pareto_front` over locally observed compatible routes for pilot
and diagnostic comparison. The separately named `dispatch_pareto_front` first hard-filters route
identity, context, semantic control, qualification, and runtime admission. The map may show a
measured primary with `dispatchable_recommendation: false` and a blocked status, but a consumer must
never dispatch it. Both fronts maximize the success lower bound while minimizing route/identity
failure and the selected cost/token/time dimension. Missing values are not zero; they make
candidates incomparable on that dimension. Neither front manufactures one global model score.

For locally repeated attempts:

```text
observed cost per accepted result = sum(compatible observed cost) / accepted successes
```

The result is unavailable at zero successes. Claude-subscription `marginal_cost_usd` is `null`,
never `$0`; separately labeled API-equivalent cost and quota/usage-credit state may be retained.

## Context contract

Context is a hard feasibility constraint, not a Pareto reward. Use expected peak input plus
output reserve and the policy safety margin, then choose the smallest certified form that fits.
`requested_model_id` and `requested_context_form` remain separate in JSON; only Markdown renders
`[1m]` as a suffix. A native 1M-base model and Muse's shared pool remain `base`. An exact `[1m]`
form is eligible only when `runtime-assignment-receipt-v1.json` certifies the tuple; requested
context never proves served context.

## Replacement and consumption

The same canonical evidence renders byte-identical JSON and Markdown. Default creation refuses
an existing artifact. Regeneration requires a complete v2 trio with valid generated-content
digests. A v1 file, partial trio, stale digest, or user edit requires `--regenerate --force`,
which still cannot override failed route evidence.

A consumer may look up a task class only after checking:

```js
const entry = modelTaskMap.map[taskClass];
if (!entry?.primary?.dispatchable_recommendation) {
  throw new Error(`not-admitted: ${taskClass}`);
}
const assignment = {
  requested_model_id: entry.primary.requested_model_id,
  requested_effort: entry.primary.requested_effort,
  requested_context_form: entry.primary.requested_context_form,
};
```

That lookup still does not prove injection or authorize spawn. The authenticated harness must
inject the tuple, preserve immutable request evidence, validate the runtime receipt, and correlate
model identity with spawn evidence immediately before each separately authorized worker.
