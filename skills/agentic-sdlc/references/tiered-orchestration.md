# Tiered orchestration

Use this reference when composing a mission run. It integrates model-neutral mission
structure with the canonical routing policy; it does not restate a routing matrix.

Before dispatch, load the [model-tier-rightsizing skill](../../model-tier-rightsizing/SKILL.md)
and its [canonical calibration](../../model-tier-rightsizing/references/model-routing-calibration.md).
The four semantic tiers are frontier, judgment workhorse, capable volume, and mechanical
floor. Their eligible primary pairs are Sol/Fable, Terra/Opus, and Luna/Sonnet; choose within
a pair by task fit, independent perspective, quota, and verified transport. Never apply a
global provider preference or artificial all-six representation.

Before any spawn, the conductor supplies a conductor-supplied certified `RuntimeAssignment`
with a certified exact model ID. Its `resolution_state` must equal `resolved`;
`request_injection_status` and `model_readback_status` must equal `verified`; and
`resolved_provider` and `resolved_model_id` must be non-unknown. The request side records
closed `request_injection_evidence` proving the exact requested model, effort, and context;
closed `model_readback_evidence` proving resolved provider/model; and closed effort/context
readback evidence when verified. The canonical receipt has exactly the policy-derived 16 fields
and no `*_source` projections. Validation proves only canonical internal consistency; the
external authenticated harness alone admits and spawns. Provider-neutral roles consume the
assignment and never dispatch. Requested, inherited, unresolved, incomplete, or unverified
model-identity assignments stop before spawn and return one `SeedProposal` for conductor adjudication.

Effective readback is separate from immutable request injection. Record
`effort_readback_status` and `context_readback_status` as `verified` with bound evidence when
exposed, or `unavailable` when the transport cannot expose effective effort or context behavior. Never copy requested values into resolved or
readback fields, and never require impossible effective readback after request injection and
model identity are verified. Prompt prose does not enforce a model or effort; an assignment
carried in a prompt is an audit copy only. `[1m]` is independent: use only a
transport-certified exact form for context-heavy work, and never infer intelligence, upstream
context capacity, compaction, or effort compliance from its request or base-ID readback. A
recommendation, gate, or route never authorizes an outward action.

Context footprint is a second scheduling axis alongside model tier: a route's admitted
context, compaction behavior, and inheritance across fresh-versus-forked agents constrain
which work an assignment can carry, independent of intelligence tier. Served models have
genuinely different windows, some provider windows are a shared input/output pool rather than
separate reservations, and client-side context and compaction controls are per session rather
than per model — so a mixed-model process carries one floor that must suit its smallest
reachable window. The
[canonical calibration](../../model-tier-rightsizing/references/model-routing-calibration.md)
Context windows section is the sole owner of the per-model numbers, the shared-pool hazard,
and the layer-ownership rule; consult it before sizing a context-heavy assignment rather than
carrying a window number here. A requested context form is a request and never proof of the
served window. The dated design notes
docs/research/2026-07-22-claude-code-multi-model-routing.md and
docs/research/2026-08-05-gateway-selection-memo.md in this repository record earlier
material; they are not installed with this skill and authorize no route.

## Mission integration

Keep scale-setting work singular: a frame, plan, authority analysis, cross-system invariant,
or final stop/go recommendation that later work treats as settled must be re-derived and
adjudicated by the conductor. Keep candidate-degradation work bounded by explicit acceptance
criteria and immutable-candidate review. Keep deterministic work behind its same verifier;
do not lower a class or control merely to recover capacity. If the certified same-class route
is unavailable, stop or reduce scope.

Every delegated workstream has a bounded artifact, owner, stop condition, wrong-output
class, exact requested identity, explicit requested effort/context, evidence gate, and
predeclared fallback. Every executable `agent()` carries both `model` and `effort`; the same
rule applies when a host encodes those values outside the prompt for a named workflow or
subagent. Null, malformed, truncated, missing, or transport-rejected output is failure.

The conductor adjudicates advisory Maps, ResearchBriefs, SeedProposals, Candidates,
ReviewFindings, and IntegrationReports, and alone mutates Seeds. An authorized integrator
alone performs an already-authorized fan-in. Humans alone authorize outward or irreversible
actions.

## Capability ladder

Use provider-native roles, subagents, workflows, teams, or background tasks for delegated
work after capability, trust, and transport certification. Use an optional view/event adapter
only when it is already active and never as a load-bearing requirement. Write-capable workers
use separate worktrees; read-only workers can share. Keep results in assigned artifact files.
Worktree location and lifecycle are not decided here: `references/seeds-worktrees.md`
§ Worktree substrate owns the in-workspace `.worktrees/<seed-id>-<slug>/` rule and
`references/worktree-lifecycle.md` owns the create-through-clean-up commands.

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
