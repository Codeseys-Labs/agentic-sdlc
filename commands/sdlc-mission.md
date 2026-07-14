---
name: sdlc-mission
description: Run an autonomous backlog-zero mission — reconstruct state, classify the queue, loop waves with concurrent critique until zero milestone-blocking work or a bound trips
---

Run a MISSION with the agentic-sdlc-orchestrator loop. Goal/scope: $ARGUMENTS

Load the `agentic-sdlc-orchestrator` skill, then `references/mission-loop.md` and
`references/tiered-orchestration.md`. Operate as the conductor:

1. **Reconstruct state** (no shared-context assumptions): repo agent instructions,
   roadmap/status, tracker + `sd prime`/`sd ready`/`sd blocked`, ADR index, CI docs,
   branch/dirty-tree state, latest commit. Document the baseline.
2. **Audit + classify** every open item: ACTIVE_MILESTONE / BLOCKED_* / POST_MILESTONE /
   OUT_OF_SCOPE / DUPLICATE / INVALID, with rationale. Priority =
   (impact × severity × unblocks × confidence) / effort. Only ACTIVE_MILESTONE executes.
3. **Research** only load-bearing unknowns (delegated research pipeline, synthesize before
   acting). New ideas become classified Seeds, not detours.
4. **Plan the wave**: load `model-tier-rightsizing`, then define workstreams with owner
   role, worktree, scope, gates, rollback, caller-injected certified exact model ID, and
   requested effort. Provider-neutral roles do not select models; stop before dispatch when
   identity or adapter readback is unresolved. Scale-setter outputs are advisory
   recommendations for conductor adjudication and do not authorize outward effects.
5. **Execute** via `/sdlc-wave` semantics: provider-native workers in worktrees by
   default. Use provider-native background or persistent tasks for bounded work. WIP caps: impl ≤3,
   research ≤2, integration ≤1, critique ≤1, nesting ≤2.
6. **Concurrent critique**: one standing review team audits each wave's SQUASH-MERGED
   snapshot (never live worktrees) and returns advisory findings. The conductor alone
   adjudicates whether findings become Seeds; reviewer or critic output is not acceptance
   or authority.
7. **Reconcile + loop**: an authorized integrator alone performs an already-authorized,
   merge-base-validated fan-in; re-gate on main, close only with evidence, fold in blocking
   seeds, re-prioritize, and start the next wave. Backflow (re-entering an earlier phase) is
   a recommendation for the conductor, scoped, within budgets (global passes ≤6; Frame ≤1,
   Discover/Research/Plan ≤2, Act ≤3 re-entries).
8. **Terminate honestly**: done = zero ACTIVE_MILESTONE + critique reports zero blocking +
   tracker clean + final checkpoint (evidence, remaining non-blocking backlog,
   assumptions). A tripped bound = an honest stop with exact blockers + resume hints —
   never claimed completion.

Non-negotiables: no force-push/history-rewrite on shared branches; no secrets; no CI
mutation from a dirty checkout; no closing without acceptance evidence; no chat-only
TODOs; no cross-platform claims from single-platform proof; seeds-first for every
discovery — never fix inline. Push, publication, PR mutation, merge, deployment,
credential, and evidence-store operations each require explicit operation-specific approval;
local status, gates, reviewer labels, and conductor choices never grant it.
