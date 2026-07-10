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
   If codex workers will run: pre-trust each worktree path in ~/.codex/config.toml.
4. Launch provider-native role agents or subagents by default. Use CAO `assign`/`--async`
   only when the optional adapter was explicitly selected and is already healthy. Each
   worker prompt must carry: Seed id + acceptance criteria, absolute worktree path, files
   in scope, gates to run, artifact report path.
5. If cmux is already active, optionally publish wave status. Open a `tmux attach` viewer
   only for an existing CAO/tmux-backed worker session; native workers require neither
   cmux nor tmux.
6. Collect artifact reports. Review each worktree (diff + gates, not summaries) —
   use the sdlc-reviewer agent where available.
7. Reconcile: convert findings to Seeds, close verified Seeds, run `sd sync`,
   squash/rebase accepted branches per repo policy, remove merged worktrees
   (`git worktree remove`).
8. Report: wave summary — Seeds closed/blocked, gates run, worktrees merged/kept,
   findings carried forward.
