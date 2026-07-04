---
name: agentic-sdlc-orchestrator
description: Coordinate a project-scale agentic SDLC loop across Codex, Claude Code, CAO, Seeds (`sd`), git worktrees, tests, and PRs — with optional cmux as view layer/event bus when CMUX_WORKSPACE_ID is set. Use when an agent should act as the entrypoint/macro conductor while CAO launches Codex, Claude Code, or other CLI workers for discovery, research, planning, implementation, review, testing, backlog-zero, or repeatable multi-agent project execution. Covers per-worker model pinning, nested supervisors, long-running work via assign/--async (timeouts never kill agents), codex trust/timeout gotchas, and cao-ops-mcp wiring.
---

# Agentic SDLC Orchestrator

Use this skill to run a repeatable, project-generic implementation loop:

`Codex entrypoint -> CAO fleet/session bus -> Codex/Claude/other CLI workers -> Seeds queue -> worktrees -> tests -> squash/rebase -> PR`

Keep Codex as the macro conductor. Use CAO for durable cross-CLI sessions. Use Claude Code when a bounded workstream benefits from native subagents or dynamic workflows. Use Seeds as the queue of record.

## Repo Location

This skill is maintained in the private repo `baladithyab/agentic-sdlc-orchestrator`.
Clone location varies per machine (e.g. `~/Documents/DevBox/agentic-sdlc-orchestrator` on
macOS, `/mnt/e/CS/github/agentic-sdlc-orchestrator` on WSL). If absent:
`gh repo clone baladithyab/agentic-sdlc-orchestrator`.

When this skill refers to bundled scripts, use the repo copies:

- `<repo>/scripts/check-agentic-sdlc-prereqs.sh`
- `<repo>/scripts/install-cao-kit.sh`

## First Moves

1. Prime the project state:
   - Run `sd prime` if the repo uses Seeds.
   - Inspect `sd ready --format json`, `sd blocked --format json`, and repo docs/ADRs/roadmap.
   - Check `git status --short` before planning worktrees.
2. Detect the environment:
   - `test -n "$CMUX_WORKSPACE_ID"` → inside cmux: use it as the view layer and event bus
     (see `references/cmux-integration.md`). Absent → skip all cmux steps; nothing depends on it.
   - `command -v cao` + `curl -s -m1 localhost:9889/` → CAO available/running.
   - Provider env (e.g. Bedrock) must be exported in the shell that starts `cao-server`
     (see `references/cao-operations.md`, Environment inheritance).
3. Decide the run shape:
   - Small fix: Codex handles it directly or uses one CAO handoff.
   - Multi-file implementation: CAO workers plus a Seeds-backed worktree wave.
   - Unclear architecture: discover -> research if needed -> plan -> act -> review.
   - Large backlog-zero work: bounded waves with continuous Seeds reconciliation.
4. Install or verify CAO profiles from this repo if using CAO:
   - See `references/cao-profiles.md`.
   - Run `scripts/check-agentic-sdlc-prereqs.sh` from the repo root for local checks.
5. Create or update Seeds before implementation. Do not let findings live only in chat.

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
- Use CAO `assign` (or `--async` launch) for parallel lanes; require each worker to write artifacts and call `send_message` when done.
- **Long-running work: always `assign`/`--async`, never `handoff`.** CAO timeouts stop the caller waiting — they never kill the agent (detached tmux runs to completion). Poll `cao session status` or read the worker's artifact file. Blocking tools' `timeout` arg has no upper cap if you must block.
- Use Claude Code workers for nested dynamic workflow execution on one bounded workstream. Do not let a nested Claude workflow own the whole project queue unless explicitly requested.
- Use Codex workers for implementation, refactors, tests, docs, repo inspection, and review when provider-native Claude workflows are not needed.
- Nested orchestration is allowed (a `role: supervisor` worker can delegate further — CAO has no depth cap) but keep it to one mid-tier at most and give each tier an explicit worker list.
- Per-worker model pinning: set `model:` in the profile frontmatter (forwarded as `--model` to claude/codex). Same agent name + different `--provider` OVERWRITES the profile — use distinct names to mix engines.
- Keep one macro conductor responsible for Seeds, worktree ownership, merges, and final claims.
- If inside cmux: surface run state on the sidebar and view workers via `tmux attach` workspaces (`references/cmux-integration.md`). cmux is optional; never block on it.

## References

Read only what is needed:

- `references/sdlc-loop.md`: phase gates, backflow, done criteria.
- `references/seeds-worktrees.md`: Seeds queue, worktree wave, squash/rebase, PR handling.
- `references/cao-profiles.md`: CAO profile roles and install/run commands.
- `references/cao-operations.md`: trial-verified CAO ops — env inheritance, per-worker models, nesting, timeouts/long-running, codex gotchas, headless drive, teardown order, cao-ops-mcp wiring.
- `references/cmux-integration.md`: cmux as view layer + event bus (detection, tmux-attach workspaces, pub/sub with replay, sidebar dashboard). Only when `CMUX_WORKSPACE_ID` is set.
- `references/delegation-planes.md`: per-provider decision matrices — Claude subagent vs Workflow vs Agent Team vs CAO; Codex role subagents vs exec-loops vs CAO; cost ladder; write-conflict rules.
- `references/worktree-integration.md`: fan-in hazards — merge-base footprint (not HEAD diff), placeholder-trap assembly, re-gate-on-main (worktree-green ≠ main-green), clean 3-way apply ≠ semantic correctness, squash-scope discipline.
- `references/mission-loop.md`: the autonomous backlog-zero doctrine — milestone-blocking classification (8 classes, only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes, WIP caps, priority math, concurrent critique team, honest definition of done. Read for MISSION-shaped assignments ("drive the backlog to zero", "keep going until done").
- `references/tiered-orchestration.md`: model-tier assignment (the multiplier principle — frontier tier only on solo scale-setters: frame/plan/verdict), the 5-layer CAO/cmux delegation map, bounded backflow (verdict-only re-entry, three independent stops), chained-iterations vs mega-run, worker-lifecycle at scale (write-as-you-go, nudge→replace, salvage).
- `references/research-team.md`: evidence-graded multi-agent research for standing research efforts — the evidence ladder (promote slowly, downgrade quickly), role separation-of-powers (scout ≠ novelty-judge; attacker ≠ fixer; writer ≠ originator), one-loop discipline with a recorded next-action, greenfield/brownfield loops, cheapest-decisive-experiment rule, gates-as-executables.

Bundled role agents (installed by `scripts/install-skill-bundle.sh`): Claude Code
`agents/claude/sdlc-{planner,implementer,reviewer}.md`; Codex
`agents/codex/sdlc-{planner,implementer,reviewer}.toml`. Slash commands (Claude Code):
`/sdlc-frame`, `/sdlc-wave`, `/sdlc-mission` (autonomous backlog-zero run). Bus helper:
`scripts/cmux-bus.sh` (pub/sub/seq).

## Hard Stops

- Do not run write-capable workers in the user's dirty checkout. Use a clean worktree.
- Do not close Seeds from worker claims alone. Verify files, tests, and acceptance criteria.
- Do not treat CAO native workflow YAML as the execution engine unless the installed CAO version has a shipped run engine.
- Do not recursively launch agents without a bound: cap workers, passes, and review/fix rounds.
- Do not push, force-push, rewrite history, alter secrets, or change CI settings unless the user explicitly authorizes that action.
