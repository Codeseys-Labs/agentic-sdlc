# Delegation Planes (per-provider decision matrices)

Use this reference when choosing HOW to delegate a workstream — before choosing WHO
(profile/role). The wrong plane wastes tokens, hides results, or causes write conflicts.

Provider-native delegation is the complete baseline only after required capability and trust
probes succeed. It is a mechanism, not authority; cmux is an optional view/event layer. Never install or
enable cmux to satisfy an ordinary delegation need. Missing, unpinned, untrusted, or ambiguous required
capability fails closed.

## Claude Code entrypoint

| Situation | Plane | Why |
|---|---|---|
| Result needed in THIS conversation (research, review, analysis) | **Subagent** (Agent tool, `run_in_background`) | Pushes final message back automatically; cheapest; no polling |
| Deterministic multi-phase fan-out (map → verify → synthesize) | **Workflow tool** | Scripted pipeline/parallel; per-stage models; replayable |
| True parallel implementation across disjoint files, peer messaging | **Agent Team** (TeamCreate/SendMessage/TaskCreate) | Independent sessions + task list; ~3-6× cost — use only when subagents' one-way reporting is insufficient |

Key subagent/team facts (verified):
- Parallel subagents are safe read-only; parallel WRITERS conflict — use worktrees or a team
  with explicit file ownership.
- Team orchestration-file race: multiple teammates editing one shared plan/orchestration file
  corrupt it — only the LEAD writes it (lead-only reservation pattern); workers message the
  lead instead.
- Teams need `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.

## Codex entrypoint

| Situation | Plane | Why |
|---|---|---|
| Result needed in THIS session | **Role subagents** (prompt-driven, `~/.codex/agents/*.toml`) | In-process; gated by `features.multi_agent`, `agents.max_threads`/`max_depth` |
| Iterate-until-done on one task | **`codex exec resume --last` loop** | Native session continuity |
| Long headless one-shot | **`codex exec`** (`-o <file>` for clean output, `< /dev/null`, trusted dir) | The worker unit |

Codex role subagents remain the default. Its `max_depth` may be low, so flatten the plan,
cap nesting, and route peer communication through the conductor.

## Cost/independence ladder (cheap → expensive)

direct execution → provider-native subagent/role → provider-native workflow/team


Pick the LOWEST rung that satisfies: (a) where the result must land, (b) write-parallelism
needs, (c) lifetime beyond the conversation, (d) engine mixing.

## Universal rules

- The conductor alone adjudicates and mutates the queue (Seeds); an authorized integrator
  alone performs an already-authorized fan-in. Roles, status, gate results, and
  reviewer/critic labels are advisory; they do not authorize outward effects. Humans alone
  authorize push, publication, PR mutation, merge, deployment, credential, and evidence-store
  operations.
- Write-capable workers get their own worktree; read-only workers can share. The substrate is
  in-workspace `<repo>/.worktrees/<seed-id>-<slug>/` — the canonical rule lives in
  `references/seeds-worktrees.md` § Worktree substrate and the step-by-step lifecycle in
  `references/worktree-lifecycle.md`; do not improvise a location or a cleanup sequence here.
- Long-running: use the selected host's native background/persistent mechanism plus
  artifact files. Never hold a blocking call open for hours.
- Results land in FILES at assigned artifact paths; chat summaries are hints, not evidence.
- Before a dispatching consumer launches work, load `model-tier-rightsizing`; classify the
  artifact into frontier, judgment workhorse, capable volume, or mechanical floor, then choose
  within the eligible Sol/Fable, Terra/Opus, or Luna/Sonnet pair by task fit, independent
  perspective, quota, and verified transport. Its caller must inject a certified exact model
  ID **and explicit requested effort** for every worker. A provider-neutral static role
  definition does not select a model; stop before dispatch if identity or adapter readback is
  unresolved. Never rely on host-default selection or force all six models into a run.
