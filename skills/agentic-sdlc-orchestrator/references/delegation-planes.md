# Delegation Planes (per-provider decision matrices)

Use this reference when choosing HOW to delegate a workstream — before choosing WHO
(profile/role). The wrong plane wastes tokens, hides results, or causes write conflicts.

## Claude Code entrypoint

| Situation | Plane | Why |
|---|---|---|
| Result needed in THIS conversation (research, review, analysis) | **Subagent** (Agent tool, `run_in_background`) | Pushes final message back automatically; cheapest; no polling |
| Deterministic multi-phase fan-out (map → verify → synthesize) | **Workflow tool** | Scripted pipeline/parallel; per-stage models; replayable |
| True parallel implementation across disjoint files, peer messaging | **Agent Team** (TeamCreate/SendMessage/TaskCreate) | Independent sessions + task list; ~3-6× cost — use only when subagents' one-way reporting is insufficient |
| Durable cross-CLI fleet, mixed engines, roles, schedules | **CAO** | Sessions survive the conversation; supervisor→worker; typed ops via cao-ops-mcp |
| Human wants to watch/steer live worker TUIs | **CAO + cmux attach** | `cmux new-workspace --command "tmux attach -t cao-<session>"` |

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
| Durable cross-CLI fleet / mixed engines | **CAO** | Same as above |
| Long headless one-shot | **`codex exec`** (`-o <file>` for clean output, `< /dev/null`, trusted dir) | The worker unit |

Codex has NO TeamCreate/Workflow equivalents — its `max_depth` defaults low (subagents
can't spawn subagents unless raised). For anything needing peer messaging or >1 nesting
level, route through CAO instead.

## Cost/independence ladder (cheap → expensive)

subagent → Workflow stage → codex role subagent → CAO worker → Agent Team member

Pick the LOWEST rung that satisfies: (a) where the result must land, (b) write-parallelism
needs, (c) lifetime beyond the conversation, (d) engine mixing.

## Universal rules

- One conductor owns the queue (Seeds), merges, and final claims — regardless of plane.
- Write-capable workers get their own worktree; read-only workers can share.
- Long-running: fire-and-forget (`assign`/`--async`/`run_in_background`) + artifact files;
  never hold a blocking call open for hours (see `references/cao-operations.md`).
- Results land in FILES at assigned artifact paths; chat summaries are hints, not evidence.
