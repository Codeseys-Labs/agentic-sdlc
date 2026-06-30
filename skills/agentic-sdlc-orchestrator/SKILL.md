---
name: agentic-sdlc-orchestrator
description: Coordinate a project-scale agentic SDLC loop across Codex, Claude Code, CAO, Seeds (`sd`), git worktrees, tests, and PRs. Use when Codex should act as the entrypoint/macro conductor while CAO launches Codex, Claude Code, or other CLI workers for discovery, research, planning, implementation, review, testing, backlog-zero, or repeatable multi-agent project execution.
---

# Agentic SDLC Orchestrator

Use this skill to run a repeatable, project-generic implementation loop:

`Codex entrypoint -> CAO fleet/session bus -> Codex/Claude/other CLI workers -> Seeds queue -> worktrees -> tests -> squash/rebase -> PR`

Keep Codex as the macro conductor. Use CAO for durable cross-CLI sessions. Use Claude Code when a bounded workstream benefits from native subagents or dynamic workflows. Use Seeds as the queue of record.

## First Moves

1. Prime the project state:
   - Run `sd prime` if the repo uses Seeds.
   - Inspect `sd ready --format json`, `sd blocked --format json`, and repo docs/ADRs/roadmap.
   - Check `git status --short` before planning worktrees.
2. Decide the run shape:
   - Small fix: Codex handles it directly or uses one CAO handoff.
   - Multi-file implementation: CAO workers plus a Seeds-backed worktree wave.
   - Unclear architecture: discover -> research if needed -> plan -> act -> review.
   - Large backlog-zero work: bounded waves with continuous Seeds reconciliation.
3. Install or verify CAO profiles from this repo if using CAO:
   - See `references/cao-profiles.md`.
   - Run `scripts/check-agentic-sdlc-prereqs.sh` from the repo root for local checks.
4. Create or update Seeds before implementation. Do not let findings live only in chat.

## Control Contract

Use this phase order unless the task is clearly smaller:

1. Frame: define done, constraints, repo state, queue state, and allowed blast radius.
2. Discover: assign read-only workers across code areas. Require file/line evidence.
3. Research: use HyperResearch only for external or load-bearing unknowns.
4. Plan: emit workstreams, dependencies, worktree strategy, gates, rollback, and Seeds updates.
5. Act: launch workers in separate worktrees for independent workstreams.
6. Review: review stable branch/worktree snapshots, not only worker summaries.
7. Reconcile: turn findings into Seeds, fix blockers, run gates, and update docs.
8. Ship: squash/rebase, sync Seeds, open PR or commit according to repo policy.

Use backflow when review reveals an earlier phase was weak: re-enter Discover, Research, or Plan with a scoped task instead of restarting the whole run.

## Delegation Rules

- Use CAO `handoff` for blocking tasks whose result gates the next phase.
- Use CAO `assign` for parallel lanes; require each worker to write artifacts and call `send_message` when done.
- Use Claude Code workers for nested dynamic workflow execution on one bounded workstream. Do not let a nested Claude workflow own the whole project queue unless explicitly requested.
- Use Codex workers for implementation, refactors, tests, docs, repo inspection, and review when provider-native Claude workflows are not needed.
- Keep one macro conductor responsible for Seeds, worktree ownership, merges, and final claims.

## References

Read only what is needed:

- `references/sdlc-loop.md`: phase gates, backflow, done criteria.
- `references/seeds-worktrees.md`: Seeds queue, worktree wave, squash/rebase, PR handling.
- `references/cao-profiles.md`: CAO profile roles and install/run commands.

## Hard Stops

- Do not run write-capable workers in the user's dirty checkout. Use a clean worktree.
- Do not close Seeds from worker claims alone. Verify files, tests, and acceptance criteria.
- Do not treat CAO native workflow YAML as the execution engine unless the installed CAO version has a shipped run engine.
- Do not recursively launch agents without a bound: cap workers, passes, and review/fix rounds.
- Do not push, force-push, rewrite history, alter secrets, or change CI settings unless the user explicitly authorizes that action.
