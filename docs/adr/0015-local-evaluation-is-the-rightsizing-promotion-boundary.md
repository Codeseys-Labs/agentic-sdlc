# ADR-0015: Local evaluation is the rightsizing promotion boundary

- **Status:** Accepted
- **Date:** 2026-08-12
- **Supersedes:** the `gateway | native-bedrock` output assumption in the original model-task-map contract
- **Amends:** the qualification doctrine in `skills/model-tier-rightsizing/references/model-routing-calibration.md`

## Context

The first `/sdlc-rightsize` design classified eight task classes and emitted a static map from a
live gateway catalog plus one native canary. That was enough to reject dead aliases, but not to
answer whether an exact route was effective or economical for the operator's actual task class.
It also modeled provider planes too coarsely. ADR-0014 now places routed OCX models and native
Claude subscription passthrough in one Claude Code gateway session with different discovery,
authentication, billing, and attribution semantics.

Published model evaluations add useful candidate evidence. DeepSWE reports autonomous patching
success and task economics. Artificial Analysis exposes coding, terminal, repository-Q&A,
long-context, instruction-following, and agent evaluations. CursorBench measures ambiguous
multi-file work and publishes cost/step data; Cursor's routing work also shows that model-switch
cache misses and planner-caused worker cost matter. Prime Intellect's `verifiers` work provides a
strong evaluation decomposition and validation discipline. None of these sources runs the exact
operator account, gateway, context form, task pack, or target harness. A leaderboard score cannot
prove route liveness or production suitability.

At the same time, a local benchmark runner could easily become a second worker scheduler, leak
repository data, consume unbounded subscription quota, or promote a model without the runtime
receipt admission boundary. The feature therefore needs a narrow measurement authority and an
explicit non-authority boundary.

## Decision

Local target-representative evaluation is the only path that may advance an exact route from
`route-probed` to task-class-scoped `role-qualified`.

The repository adds one stdlib evaluator owned by `model-tier-rightsizing`. It:

1. discovers live configured OCX routes and PII-stripped Claude subscription capability;
2. validates a closed `rightsize-run-spec/v1`;
3. renders a no-call plan and authorization digest;
4. runs only an explicitly approved, bounded serial evaluation through the existing `ccodex`
   launcher;
5. correlates each result with gateway attribution;
6. grades outputs with closed deterministic verifiers;
7. records non-sensitive evidence, measured per-task-class Pareto fronts, and separately filtered
   dispatch fronts;
8. renders one v2 recommendation trio.

The exact evaluation identity is:

```text
taskset × harness × runtime × model settings × exact route
```

The built-in harness-smoke pack cannot promote. Qualification requires a digest-bound
representative pack, at least five held-out tasks per selected class, at least three attempts per
task, 90% accepted attempts, a 95% Wilson lower bound of at least 0.70, zero route/identity
failures, and zero critical-task failures. Authority/frontier cases are critical. These are
minimum evidence rules, not a universal assurance claim.

Published benchmarks are `mined` evidence. They may nominate and order candidates for local
evaluation. They cannot establish liveness, raise a qualification rung, prove context, fill a
frontier slot, alter runtime admission, or authorize work. Precedence remains:

```text
observed > declared > mined
```

The generated map replaces `provider_plane` with an exact route record: transport, route kind,
provider, auth basis, billing basis, full model ID, effort, and context request form. The two
current route kinds are `gateway-routed-provider` and
`gateway-claude-subscription-passthrough`.

Context is a hard feasibility constraint. The evaluator chooses the smallest certified request
form that fits expected input, output reserve, and margin. `[1m]` is not a quality tier and a
request never proves served context.

Subscription marginal cost is unknown, not zero. API-equivalent cost, quota consumption, and
usage-credit possibility remain separate fields. Missing Pareto values make candidates
incomparable; they do not become zero.

## Authority boundary

The evaluator is not a production launcher. A matching authorization digest permits only the
concrete evaluation calls shown by `plan`. It grants no authority to:

- dispatch workflow roles or subagents;
- mutate the target repository, Seeds, worktrees, gateway/provider configuration, trust, or
  global settings;
- update `runtime-assignment-receipt-v1.json`;
- merge, publish, deploy, or perform another outward operation.

A map route is a dispatchable *recommendation* only when it is locally role-qualified and the
checked-in runtime receipt policy already admits the exact tuple. The external authenticated
harness still validates one concrete `RuntimeAssignment` immediately before every separately
authorized production spawn.

## Safety and privacy

The evaluator runs task fixtures in temporary copies with safe mode, no session persistence, no
fallback, no Bash/web/subagents/workflows, ordinary `dontAsk` permissions, and a closed tool list.
It never grants model access to the real target. Target-content packs require explicit data-egress
acknowledgement. Fable and Claude extended-context selections require explicit usage-credit
acknowledgement.

Generated artifacts retain task/input/output/request digests, closed attribution excerpts,
metrics, and verifier verdicts. They never retain raw prompts, completions, transcripts,
repository content, credentials, PII, secret-shaped values, or mutable absolute paths.

## Independent complexity review

A Muse-only adversarial review challenged the design from architecture, security, product,
documentation, and test perspectives, then ran both deletion pressure and a safety-preservation
rebuttal. The accepted simplification was to remove the unconfined external-command verifier and
keep the v1 verifier vocabulary deterministic; duplicate policy loading and unused evidence fields
were also removed. A general sandbox, provider SDK, evaluator framework, scheduler, and additional
receipt layer remain deliberately absent.

The review rejected removing exact identity correlation, separate consent, redaction, budgets,
bounded copied-fixture execution, qualification thresholds, atomic evidence replacement, or
runtime-authority separation. Those controls are not presentation complexity: together they answer
whether a measurement was attributable, authorized, private, bounded, reproducible, and unable to
self-authorize production work. Shortening the evaluator by deleting one of those properties would
change its contract rather than simplify its implementation.

## Consequences

### Positive

- New ccodex models can be evaluated without silently joining a production tier.
- Model selection can account for reliability, cost per accepted result, token/cache behavior,
  latency, steps, context, quota, and route failures.
- Claude subscription economics remain honest without inventing per-call dollar charges.
- Interactive choices are replayable through a canonical non-interactive run spec.
- Benchmark refresh and local evaluation are reviewable, versioned, and independently stale.

### Costs and limitations

- Qualification consumes real provider or subscription capacity and must be explicitly approved.
- Five tasks × three attempts is only a minimum; close or high-impact decisions may need more.
- Semantic tasks are only as good as their immutable expected evidence and independent controls;
  an LLM judge alone is not sufficient.
- Cross-filesystem three-file replacement cannot be transactional; outputs are constrained to one
  target and staged before replacement, with digests detecting partial or edited state.
- The evaluator does not infer effective effort/context when the transport does not expose it.

## Rejected alternatives

1. **Prompt-only map generation.** Rejected because it cannot guarantee deterministic parsing,
   safe replacement, reproducible metrics, or route identity.
2. **Published-leaderboard routing.** Rejected because harness and route mismatch would allow
   mined evidence to overrule local failure.
3. **One global weighted model score.** Rejected because task classes, controls, and metric
   semantics differ; weights conceal authority decisions and missing data.
4. **Automatic qualification during repository gates.** Rejected because it consumes quota,
   sends data outward, is nondeterministic, and would make network/provider state a bootstrap or
   gate prerequisite.
5. **Evaluator as a general worker scheduler.** Rejected because the repository deliberately has
   no production launcher and because it would bypass `RuntimeAssignment` admission.
