---
name: sdlc-wave
description: Run one Seeds-backed worktree wave — select ready Seeds, spawn workers in worktrees, review, reconcile
---

Run ONE implementation wave of the agentic-sdlc-orchestrator loop. Scope: $ARGUMENTS

1. Load the `agentic-sdlc-orchestrator` skill (and its `references/seeds-worktrees.md`).
2. Select the wave: from `sd ready --format json`, pick independent Seeds with disjoint
   file ownership (cap 3-5). Broad architecture / CI / shared-contract changes get
   their own serial wave.
3. Create one worktree per write-capable worker:
   `git worktree add ../<repo>-wt-<seed-id> -b work/<seed-id>-<slug>`
   Persistent `mise trust` and `~/.codex/config.toml` mutation are separate operations:
   obtain explicit operation-specific user approval for each exact worktree path before
   applying either after reviewing its checked-in config. Without that approval, use only a
   certified process-scoped test route such as `mise --no-config --cd <worktree> exec ...`,
   or stop. Missing, unpinned, untrusted, or ambiguous required capability fails closed; do
   not let workers bypass the repository gate.
4. Load `model-tier-rightsizing` before launching a model-dispatching worker. Classify each
   assignment into the four semantic tiers and choose within the eligible Sol/Fable,
   Terra/Opus, or Luna/Sonnet pair by task fit, independent perspective, quota, and verified
   transport. The caller must inject a certified exact model ID and **explicit requested
   effort**; a provider-neutral role does not select one. Stop before dispatch if identity or
   adapter readback is unresolved. Do not use host-default selection or artificial all-six
   representation. Each worker prompt must carry: Seed id + acceptance criteria, absolute
   worktree path, files in scope, gates to run, artifact report path, requested context form,
   and requested/resolved/inherited/unresolved receipt state.
5. If cmux is already active, optionally publish wave status. Native workers require neither
   cmux nor tmux.
6. Collect artifact reports. Review each worktree (diff + gates, not summaries) —
   use the sdlc-reviewer agent where available.
7. Reconcile: return findings as advisory SeedProposals for conductor adjudication; the
   conductor alone mutates Seeds. An authorized integrator alone may perform an
   already-authorized fan-in after re-gating. Worker, reviewer, critic, Seed, gate, or local
   status claims never grant authority. Push, PR, merge, deletion, and other outward effects
   require explicit operation-specific human approval.
8. Report: wave summary — Seeds closed/blocked, gates run, worktrees merged/kept,
   findings carried forward.
