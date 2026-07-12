---
name: agentic-sdlc-orchestrator
description: This skill should be used when the user asks to frame, plan, execute, review, or drive a project-scale agentic SDLC run, including Seeds-backed worktree waves, backlog-zero missions, multi-agent implementation, or concurrent critique. The baseline uses the current host's native agent and subagent capabilities and requires no CAO, cmux, or tmux. CAO is an optional adapter only when the user explicitly selects durable or mixed-engine sessions; cmux is an optional non-load-bearing view/event layer only when already active or explicitly requested.
---

# Agentic SDLC Orchestrator

Use this skill to run a repeatable, project-generic implementation loop. The skill is
policy and coordination guidance, not an actor, credential, permission grant, evidence
store, Git executor, or validator:

`Agent entrypoint -> provider-native delegation (or direct execution) -> Seeds queue -> worktrees -> tests/review -> squash/rebase -> PR`

Roles submit findings or candidate changes. Reviewer and critic labels are recommendations;
they never authorize an outward effect. One macro conductor records evidence and keeps the
queue; only the integrator may execute an already authorized fan-in mutation, and the
integrator never acquires the user's authority.

Keep the active host session as the macro conductor and use its native delegation tools by
default. The full Frame -> Ship loop is available only after required Git, Seeds, gate,
trust, and selected-adapter capabilities are probed and verified. Missing, unpinned,
untrusted, or ambiguous required capability fails closed. Add CAO only when the user
explicitly selects durable or mixed-engine CAO sessions and CAO is already available. Add
cmux only when it is already active and useful for visibility or event messaging. Never
install, start, or enable CAO, cmux, or tmux merely to run this skill. Use Seeds as the
queue of record. Global distribution (`mise` → pinned `uv` → pinned Python installer) is
separate from project activation: use `/sdlc-init` (or the same intent on non-Claude hosts)
to establish a tracked Git baseline, Seeds, repository gates, trust, and shared `AGENTS.md`
guidance before the first Frame/Wave.

## Repo Location

This skill is maintained in the private repo `baladithyab/agentic-sdlc-orchestrator`.
Clone location varies per machine (e.g. `~/Documents/DevBox/agentic-sdlc-orchestrator` on
macOS, `/mnt/e/CS/github/agentic-sdlc-orchestrator` on WSL). If absent:
`gh repo clone baladithyab/agentic-sdlc-orchestrator`.

When this skill refers to bundled scripts, use the repo copies:

- `<repo>/scripts/check-agentic-sdlc-prereqs.sh`
- `<repo>/scripts/install-cao-kit.sh` (optional CAO adapter only)

## First Moves

1. Prime the project state:
   - Run `sd prime`.
   - Inspect `sd ready --format json`, `sd blocked --format json`, and repo docs/ADRs/roadmap.
   - Check `git status --short` before planning worktrees.
2. Detect the host-native execution plane first:
   - Inventory direct execution, role agents/subagents, background delegation, and native
     result or messaging channels available in the current host.
   - Treat those capabilities as candidates, not proof of readiness: probe required
     capability, trust, and adapter/model readback before selecting the path. Missing,
     unpinned, untrusted, or ambiguous capability is a fail-closed stop.
   - Probe `cao` only after the user explicitly selects CAO for durable or mixed-engine
     sessions. Select it only when installed and healthy; otherwise stay native.
   - Probe cmux only when `command -v cmux` succeeds and `CMUX_WORKSPACE_ID` is set. If
     either check fails, skip cmux silently. tmux is never part of the baseline probe.
3. Decide the run shape:
   - Small fix: handle directly or use one provider-native role/subagent after capability
     checks pass.
   - Multi-file implementation: use provider-native workers in a Seeds-backed worktree wave.
   - Unclear architecture: discover -> research if needed -> plan -> act -> review.
   - Large backlog-zero work: bounded waves with continuous Seeds reconciliation.
   - Durable or mixed-engine work: use healthy CAO only after the user explicitly selects it.
4. Run `scripts/check-agentic-sdlc-prereqs.sh` from the repo root for local checks. Missing
   optional adapters must not block the run. Load `references/cao-profiles.md` or
   `references/cmux-integration.md` only after selecting the corresponding adapter.
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

- Prefer the host's native roles, subagents, workflows, teams, or background tasks. Keep
  direct execution for work too small to justify delegation.
- Require every delegated worker to return a structured report for conductor capture. A
  write-capable worker may also maintain its assigned artifact; for a read-only worker, the
  conductor persists the captured submission. Treat messages, status, and summaries as
  advisory notifications, not acceptance evidence or authority.
- For long-running work, use the host's native background or persistent-task mechanism and
  durable artifact files. Do not hold one blocking call open indefinitely.
- When CAO has been explicitly selected, use `handoff` only for bounded blocking results
  and `assign`/`--async` for parallel or long-running lanes. CAO timeout and tmux details
  belong in `references/cao-operations.md`, not the native baseline.
- Use Claude Code workers for nested dynamic workflow execution on one bounded workstream. Do not let a nested Claude workflow own the whole project queue unless explicitly requested.
- Use Codex workers for implementation, refactors, tests, docs, repo inspection, and review when provider-native Claude workflows are not needed.
- Keep nested orchestration to one mid-tier at most and give each tier an explicit worker list,
  regardless of delegation backend.
- Pin models through the current host's role/agent configuration. When CAO is selected,
  profile frontmatter supplies its optional per-worker model mapping.
- Keep one macro conductor responsible for Seeds, worktree ownership, merges, and evidence-backed
  recommendations. The integrator is only the delegated mutation executor during fan-in and
  never acquires user authority. Push, publication, PR mutation, merge, deployment,
  credential, and external evidence-store operations require explicit operation-specific
  authorization.
- If already inside cmux, optionally surface run state. Attach a `tmux` viewer only for an
  existing tmux-backed session; never create that dependency for a native run.

## References

Read only what is needed:

- `references/sdlc-loop.md`: phase gates, backflow, done criteria.
- `references/seeds-worktrees.md`: Seeds queue, worktree wave, squash/rebase, PR handling.
- `references/cao-profiles.md`: optional CAO adapter profiles. Load only when CAO is selected.
- `references/cao-operations.md`: optional, trial-verified CAO operations. Load only for an active CAO path.
- `references/cmux-integration.md`: optional cmux view/event integration. Load only when cmux is already active or explicitly requested.
- `references/delegation-planes.md`: per-provider decision matrices — Claude subagent vs Workflow vs Agent Team vs CAO; Codex role subagents vs exec-loops vs CAO; cost ladder; write-conflict rules.
- `references/worktree-integration.md`: fan-in hazards — merge-base footprint (not HEAD diff), placeholder-trap assembly, re-gate-on-main (worktree-green ≠ main-green), clean 3-way apply ≠ semantic correctness, squash-scope discipline.
- `references/mission-loop.md`: the autonomous backlog-zero doctrine — milestone-blocking classification (8 classes, only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes, WIP caps, priority math, concurrent critique team, honest definition of done. Read for MISSION-shaped assignments ("drive the backlog to zero", "keep going until done").
- `references/tiered-orchestration.md`: model-tier assignment, the native-first capability ladder with optional adapters, bounded backflow, chained iterations, and worker lifecycle at scale.
- `references/research-team.md`: evidence-graded multi-agent research for standing research efforts — the evidence ladder (promote slowly, downgrade quickly), role separation-of-powers (scout ≠ novelty-judge; attacker ≠ fixer; writer ≠ originator), one-loop discipline with a recorded next-action, greenfield/brownfield loops, cheapest-decisive-experiment rule, gates-as-executables.
- `references/jj-vcs.md`: jj (Jujutsu) as the wave substrate (verified on 0.43) — colocated git-compatible adoption, workspaces as agent-grade worktrees (per-workspace `@`, op-log audit, stale detection), never-failing fan-in (conflicts = committed state), auto-snapshot makes uncommitted-work loss impossible, `jj undo` recovery; gotchas: git hooks don't fire, exact-match revset trap, headless identity, snapshot swallows non-gitignored secrets.

Bundled role agents (installed globally by `scripts/install-skill-bundle.sh`), each in
Claude (`agents/claude/*.md`) and Codex (`agents/codex/*.toml`) form:
`sdlc-cartographer` (read-only Discover mapper — file:line evidence, actual gate
commands, unknowns-that-would-change-the-plan), `sdlc-planner`, `sdlc-implementer`,
`sdlc-reviewer`, `sdlc-researcher` (bounded load-bearing-unknown resolution,
stops-when-decided), `sdlc-critic` (the standing critique team — snapshot-only,
classified seeds, attacks-never-fixes), and `sdlc-integrator` (the ONLY merging agent —
merge-base footprints, placeholder-trap assembly, re-gate-on-integration). The full loop
wiring: cartographers (parallel, per area) → planner → implementers (one per worktree)
→ reviewers → integrator, with the critic standing concurrent and researchers on demand. REPO-SCOPED extra roster: `agents/codex/research/` carries the 17-role
research team (see its README — installed per-repo via the codex-research-os scaffolder,
never globally). Slash commands (Claude Code): `/sdlc-init`, `/sdlc-frame`, `/sdlc-wave`,
`/sdlc-mission`. Other hosts invoke the flagship skill with the same activation/frame/wave/mission intents. Optional cmux bus helper: `scripts/cmux-bus.sh` (pub/sub/seq).

## Hard Stops

- Do not run write-capable workers in the user's dirty checkout. Use a clean worktree.
- Do not close Seeds from worker claims alone. Verify files, tests, and acceptance criteria.
- When CAO is selected, do not treat its native workflow YAML as the execution engine unless the installed version has a shipped run engine.
- Do not install, start, or enable CAO, cmux, or tmux unless the user explicitly requests that environment change.
- Do not recursively launch agents without a bound: cap workers, passes, and review/fix rounds.
- Do not push, force-push, rewrite history, alter secrets, or change CI settings unless the user explicitly authorizes that action.
