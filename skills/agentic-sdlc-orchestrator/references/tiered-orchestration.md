# Tiered orchestration

Use this reference when composing a mission run. It integrates model-neutral mission
structure with the canonical routing policy; it does not restate a routing matrix.

Before dispatch, load the [model-tier-rightsizing skill](../../model-tier-rightsizing/SKILL.md)
and its [canonical calibration](../../model-tier-rightsizing/references/model-routing-calibration.md).
The caller must inject a certified exact model ID and requested effort; provider-neutral
role definitions are allowed only when they do not dispatch. Stop before dispatch while that
identity is unresolved. Record provider, model, effort, and context as resolved only after adapter
readback. A recommendation, gate, or route never authorizes an outward action.

For concrete Claude Code Dynamic Workflow routing across providers, context windows,
compaction policies, and fast modes, read
[`claude-code-multi-model-routing.md`](claude-code-multi-model-routing.md).

## Mission integration

Keep scale-setting work singular: a frame, plan, authority analysis, cross-system invariant,
or final stop/go recommendation that later work treats as settled must be re-derived and
adjudicated by the conductor. Keep candidate-degradation work bounded by explicit acceptance
criteria and immutable-candidate review. Keep deterministic work behind its same verifier;
do not lower a class or control merely to recover capacity. If the certified same-class route
is unavailable, stop or reduce scope.

Every delegated workstream has a bounded artifact, owner, stop condition, wrong-output
class, exact requested identity, requested effort/context, evidence gate, and predeclared
fallback. Null, malformed, truncated, missing, or transport-rejected output is failure.

The conductor adjudicates advisory Maps, ResearchBriefs, SeedProposals, Candidates,
ReviewFindings, and IntegrationReports, and alone mutates Seeds. An authorized integrator
alone performs an already-authorized fan-in. Humans alone authorize outward or irreversible
actions.

## Capability ladder

Use provider-native roles, subagents, workflows, teams, or background tasks for delegated
work after capability, trust, and transport certification. Use an optional view/event adapter
only when it is already active and never as a load-bearing requirement. Write-capable workers
use separate worktrees; read-only workers can share. Keep results in assigned artifact files.

## Bounded backflow

A verdict may recommend one scoped re-entry to an earlier phase when evidence reveals a gap.
The conductor decides whether to re-enter, preserves previous artifacts, and respects a global
pass ceiling, per-phase re-entry budgets, and a resource floor. Ceiling-hit without completion
is an honest stop with state and resume hints.

## Iteration and lifecycle

Default to one loop iteration at a time with the conductor between iterations. Use a bounded
headless run only for an explicit shape; its final verdict remains a recommendation. Workers
write artifacts incrementally, receive one bounded nudge before replacement, and have their
worktree artifacts inspected before any relaunch or authorized integration.
