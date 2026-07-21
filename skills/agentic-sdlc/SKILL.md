---
name: agentic-sdlc
description: This skill should be used when the user asks to frame, plan, execute, review, or drive a project-scale agentic SDLC run, including Seeds-backed worktree waves, backlog-zero missions, multi-agent implementation, or concurrent critique. The baseline uses the current host's native agent and subagent capabilities and requires no cmux or tmux. cmux is an optional non-load-bearing view/event layer only when already active or explicitly requested.
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
untrusted, or ambiguous required capability fails closed. Add cmux only when it is already active and useful for visibility or event messaging. Never
install, start, or enable cmux or tmux merely to run this skill. Use Seeds as the
queue of record. Mise is the only bootstrap prerequisite: from a reviewed distribution checkout, run the installed
flagship tool `seeds-launcher.mjs bootstrap --distribution <distribution-root>` under Node
`22.22.3`. Bootstrap requires an exact clean Git distribution root: it rejects any nested checkout
path or distribution whose tracked, staged, untracked, or ignored content differs from the exact
`HEAD` tree. Bootstrap alone runs the
reviewed `mise --locked install` with only that root `mise.toml`/adjacent lock, fresh private
mise data/cache/home, fixed official npm registry, distinct empty npmrc files, and hooks/config
environment disabled; ambient HOME, npmrc/registry, and mise config/data/cache cannot select
acquisition. It then resolves exact config-free roots and atomically publishes an active tuple
receipt. It verifies the executing Node and recorded Node are exactly `22.22.3`, Bun `1.3.10`,
the exact `@os-eco/seeds-cli@0.5.14` package/bin/layout, permits only the real package's benign
string `engines.bun` compatibility declaration, rejects actual Bun/config/TypeScript/macro/preload
controls, and records a trusted empty Bun configuration, the exact Git root/commit/tree plus
`mise.toml`/`mise.lock`, and typed tree/file hashes. It retains the preceding receipt for explicit
rollback. The receipt establishes an execution integrity boundary against ordinary accidental
drift, not tarball/transitive authenticity and not a same-UID TOCTOU attacker racing verification
and execution. npm version/backend and a lock do not authenticate a tarball or its transitives.

After an explicit successful bootstrap, `Seeds(<target>, <args...>)` is implemented by
`seeds-launcher.mjs inspect --target <target> <args...>` under the exact recorded and currently
executing Node `22.22.3`.
`inspect` never installs, invokes mise, networks, discovers replacement tooling, repairs state,
or accepts ambient provenance. It loads and validates only the active receipt and recorded
current hashes, accepts only `--version`, `prime`, `ready [--format json]`, and
`blocked [--format json]`, and rejects every other form before Bun starts. Node has `shell:false`
and invokes the exact recorded absolute Bun/entry pair with `--config=<trusted-file>`,
`--no-env-file`, and `--no-install`; the child gets only a short environment allowlist. Its PATH
is only the separately resolved and recorded Git directory, with portable system/global Git config
isolation. Target `bunfig`, `.env`, package config, ambient `BUN_*`, `NODE_OPTIONS`, npm/mise
overrides, and unreviewed Seeds debug variables have no execution effect.

## Repo Location

This skill is maintained in a private repository; the clone location varies
per machine. Locate the checkout by searching for this skill's directory
(`skills/agentic-sdlc/`) rather than assuming a fixed path or forge name.

When this skill refers to bundled scripts, use the repo copies:

- `<repo>/scripts/check-agentic-sdlc-prereqs.sh`

## Offline activation preview

From an installed copy of this skill, run:

```text
<installed-skill>/tools/offline-inspect.py --target <path>
```

The command is deterministic, offline, read-only, and Python-standard-library only. It inspects
local filesystem structure without subprocesses, providers, credentials, environment discovery,
network access, repairs, or target writes. Its `READY` / `NOT_READY` result is **preview readiness
only**: it does not establish Git-wave readiness or authorize activation. The explicit `skip` item
excludes PRIME apply, workflow overlay, gateway, routing, Seeds, archives, V7, config, and queue
mutation.

## First Moves

1. Prime the project state:
   - Run `Seeds(<target>, prime)`.
   - Inspect `Seeds(<target>, ready --format json)`, `Seeds(<target>, blocked --format json)`, and repo docs/ADRs/roadmap.
   - Check `git status --short` before planning worktrees.
2. Detect the host-native execution plane first:
   - Inventory direct execution, role agents/subagents, background delegation, and native
     result or messaging channels available in the current host.
   - Treat those capabilities as candidates, not proof of readiness: probe required
     capability, trust, and adapter/model readback before selecting the path. Missing,
     unpinned, untrusted, or ambiguous capability is a fail-closed stop.
   - Probe cmux only when `command -v cmux` succeeds and `CMUX_WORKSPACE_ID` is set. If
     either check fails, skip cmux silently. tmux is never part of the baseline probe.
3. Decide the run shape:
   - Small fix: handle directly or use one provider-native role/subagent after capability
     checks pass.
   - Multi-file implementation: use provider-native workers in a Seeds-backed worktree wave.
   - Unclear architecture: discover -> research if needed -> plan -> act -> review.
   - Large backlog-zero work: bounded waves with continuous Seeds reconciliation.
4. Run `scripts/check-agentic-sdlc-prereqs.sh` from the repo root for local checks. Missing
   optional adapters must not block the run. Load `references/cmux-integration.md` only when
   cmux is already active or explicitly requested.
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
8. Ship: squash/rebase, sync Seeds, open PR or commit according to repo policy. Before proposing
   any commit, PR, or squash text, load `../change-writing/SKILL.md` to author it; this phase still
   owns the squash/rebase/PR operations and the human still authorizes publication.

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
- Use Claude Code workers for nested dynamic workflow execution on one bounded workstream. Do not let a nested Claude workflow own the whole project queue unless explicitly requested.
- Use Codex workers for implementation, refactors, tests, docs, repo inspection, and review when provider-native Claude workflows are not needed.
- Keep nested orchestration to one mid-tier at most and give each tier an explicit worker list,
  regardless of delegation backend.
- Before any model dispatch, load `../model-tier-rightsizing/SKILL.md`. Classify the
  artifact into the four semantic tiers and choose within the eligible Sol/Fable, Terra/Opus,
  or Luna/Sonnet pair by task fit, independent perspective, quota, and verified transport.
  The caller must inject a certified exact model ID and **explicit requested effort** for
  every worker; provider-neutral role definitions do not select a model. Stop before dispatch
  when identity or adapter readback is unresolved. No host-default policy or artificial
  all-six representation.
- Keep one macro conductor responsible for Seeds adjudication, worktree ownership, and
  evidence-backed recommendations. The conductor alone mutates Seeds; an authorized
  integrator alone performs an already-authorized fan-in. Humans authorize push,
  publication, PR mutation, merge, deployment, credential, and external evidence-store
  operations.
- If already inside cmux, optionally surface run state. Attach a `tmux` viewer only for an
  existing tmux-backed session; never create that dependency for a native run.

## References

Read only what is needed:

- `references/sdlc-loop.md`: phase gates, backflow, done criteria.
- `references/seeds-worktrees.md`: Seeds queue, worktree wave, squash/rebase, PR handling.
- `references/cmux-integration.md`: optional cmux view/event integration. Load only when cmux is already active or explicitly requested.
- `references/delegation-planes.md`: native per-provider decision matrices, cost ladder, and write-conflict rules.
- `references/worktree-integration.md`: fan-in hazards — merge-base footprint (not HEAD diff), placeholder-trap assembly, re-gate-on-main (worktree-green ≠ main-green), clean 3-way apply ≠ semantic correctness, squash-scope discipline.
- `references/mission-loop.md`: the autonomous backlog-zero doctrine — milestone-blocking classification (8 classes, only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes, WIP caps, priority math, concurrent critique team, honest definition of done. Read for MISSION-shaped assignments ("drive the backlog to zero", "keep going until done").
- `references/tiered-orchestration.md`: mission integration, canonical routing handoff,
  native-first capability ladder, bounded backflow, and worker lifecycle at scale.
- `references/deep-work-loop.md`: the bounded seven-phase deep-work loop for ONE workstream
  (frame → map/research → decide → act → verify → critique → reconcile) — artifacts and
  SeedProposals only, no second queue, no publication/integration authority, an explicit
  bounded delegation cap, and single-hop pointers for effort routing and fan-in. Read when a
  single workstream needs the full loop shape rather than a whole backlog-zero mission.
- `../model-tier-rightsizing/SKILL.md`: required router before any model dispatch; its
  canonical calibration is the sole generation-specific routing authority.
- `references/claude-code-multi-model-routing.md`: Claude Code Dynamic Workflow model routing across CLIProxyAPI, LiteLLM, native subscriptions, API/cloud providers, and mixed context classes. Read when defining `ccodex` launch profiles, context/compaction cohorts, fast modes, or route qualification.
- `../change-writing/SKILL.md`: message authoring, output-only — commit, PR, squash, and
  draft-review text. It never stages, commits, pushes, mutates PRs, merges, or deploys.
- `references/research-team.md`: evidence-graded multi-agent research for standing research efforts — the evidence ladder (promote slowly, downgrade quickly), role separation-of-powers (scout ≠ novelty-judge; attacker ≠ fixer; writer ≠ originator), one-loop discipline with a recorded next-action, greenfield/brownfield loops, cheapest-decisive-experiment rule, gates-as-executables.
- `references/jj-vcs.md`: a one-release refusal pointer; Git worktrees are supported and no
  alternate VCS substrate is activated by this bundle.

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
- Do not install, start, or enable cmux or tmux unless the user explicitly requests that environment change.
- Do not recursively launch agents without a bound: cap workers, passes, and review/fix rounds.
- Do not push, force-push, rewrite history, alter secrets, or change CI settings unless the user explicitly authorizes that action.
