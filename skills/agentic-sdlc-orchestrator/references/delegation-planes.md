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

- One conductor owns the queue (Seeds), merges, and evidence-backed recommendations — regardless of plane.
- Roles, status, gate results, and reviewer/critic labels are advisory; they do not authorize
  outward effects. The integrator is the only delegated mutation executor during fan-in and
  never acquires user authority. Push, publication, PR mutation, merge, deployment,
  credential, and evidence-store operations each require explicit operation-specific approval.
- Write-capable workers get their own worktree; read-only workers can share.
- Long-running: use the selected host's native background/persistent mechanism plus
  artifact files. Never hold a blocking call open for hours.
- Results land in FILES at assigned artifact paths; chat summaries are hints, not evidence.
- Requested semantic model tier and resolved provider/model are different facts. Record the
  resolved value only after adapter readback; otherwise record inherited or unresolved.
