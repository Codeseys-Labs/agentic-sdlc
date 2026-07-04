# Agentic SDLC Orchestrator

Reusable Codex + Claude Code + CAO operating kit for project-scale agentic software delivery.

**Architecture: an open plugin — the multi-host pattern, since no unified plugin standard
exists (verified 2026-07).** The portable layer is the `skills/` tree (the
[Agent Skills](https://agentskills.io) format, natively read by Claude Code, Codex, Gemini
CLI, OpenCode, Cursor, Goose, Kiro, and ~40 hosts) + a root `AGENTS.md` router (read by
Codex/Gemini/OpenCode). On top sit THIN per-host manifests, all version-locked by
`scripts/bump-version.sh`:

| Host | Manifest |
|---|---|
| Claude Code | `.claude-plugin/{plugin,marketplace}.json` |
| Codex CLI | `.codex-plugin/plugin.json` + `.agents/plugins/marketplace.json` |
| Gemini CLI | `gemini-extension.json` (contextFileName → AGENTS.md) |
| OpenCode / Goose / Kiro / others | pure skills-tree discovery via the symlink installer |

Adding a skill = adding a `skills/<name>/SKILL.md` dir; the installer, validator, and all
distribution planes pick it up automatically. Never hand-edit one manifest's version —
`scripts/bump-version.sh <x.y.z>` writes all of them; `--check` gates drift in CI.

The intended shape:

```text
Agent entrypoint (Codex or Claude Code)
  -> CAO fleet/session bus
  -> Codex, Claude Code, and other CLI workers (per-worker model pinning, nested supervisors)
  -> Seeds queue
  -> git worktrees
  -> tests/review
  -> squash/rebase/PR
  [+ cmux as optional view layer & event bus when CMUX_WORKSPACE_ID is set]
```

## Contents

- `skills/agentic-sdlc-orchestrator/`: the flagship orchestration skill for any
  skill-capable CLI agent (Claude Code, Codex, CAO workers).
- `skills/codex-research-os/`: vendored research-team OS — a repo-scaffolding installer
  (`scripts/install_research_os.py`) that bootstraps a 17-role research organization
  (director + specialists), claim/experiment ledgers, greenfield/brownfield workflows,
  schemas, and Make validation gates into any target repo. Pairs with the flagship's
  `references/research-team.md` (the distilled principles).
  - `references/sdlc-loop.md` — phase gates, backflow, done criteria.
  - `references/seeds-worktrees.md` — Seeds queue, worktree waves, PR flow, worktrees×CAO×cmux.
  - `references/cao-profiles.md` — bundled CAO profile roles + launch pattern.
  - `references/cao-operations.md` — **trial-verified** CAO ops: env inheritance (Bedrock),
    per-worker `model:` pinning, nested supervisors (no depth cap), timeouts & long-running
    work (`assign`/`--async` — timeouts never kill agents), codex trust/timeout gotchas,
    headless drive, teardown order, `cao-ops-mcp` wiring.
  - `references/cmux-integration.md` — cmux as view layer + event bus (detection,
    `tmux attach` viewer workspaces, pub/sub with replay + its two race gotchas, sidebar
    dashboard). Auto-skipped when not inside cmux.
  - `references/delegation-planes.md` — per-provider decision matrices (Claude subagent vs
    Workflow vs Agent Team vs CAO; Codex role subagents vs exec-loops vs CAO; cost ladder).
  - `references/worktree-integration.md` — fan-in hazards: merge-base footprint, placeholder
    traps, re-gate-on-main, clean-apply ≠ semantic correctness, squash-scope discipline.
  - `references/mission-loop.md` — the autonomous **backlog-zero doctrine**: 8-class
    milestone classification (only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes,
    WIP caps, priority math, the concurrent critique team, honest definition of done.
  - `references/tiered-orchestration.md` — **model-tier assignment** (the multiplier
    principle: frontier tier only on solo scale-setters — frame/plan/verdict), the 5-layer
    conductor→provider-native→CAO→nested→cmux delegation map, **bounded backflow**
    (verdict-only re-entry with three independent stops), chained-iterations vs mega-run,
    worker lifecycle at scale (write-as-you-go, nudge→replace, salvage).
  - `references/research-team.md` — **evidence-graded research teams** for standing
    research efforts: the evidence ladder (promote slowly, downgrade quickly), role
    separation-of-powers (attacker ≠ fixer, writer ≠ originator), one-loop discipline
    with a recorded next-action, greenfield/brownfield loops, the cheapest-decisive-
    experiment rule, gates-as-executables (no decorative model pins).
- `agents/claude/sdlc-*.md` + `agents/codex/sdlc-*.toml`: seven role agents in both CLI
  forms (symlinked globally) — **cartographer** (read-only Discover mapper), planner,
  implementer, reviewer, **researcher** (bounded unknown-resolution), **critic** (standing
  snapshot-only critique team), **integrator** (the only merging agent). Full loop wiring:
  cartographers (parallel, per area) → planner → implementers → reviewers → integrator,
  critic concurrent, researchers on demand. Model intentionally unset — inherits the
  user's default.
- `agents/codex/research/`: the 17-role research-team TOMLs (repo-scoped reference
  copies — NOT globally installed; see its README; scaffolded per-repo by
  codex-research-os).
- `commands/sdlc-{frame,wave,mission}.md`: Claude Code slash commands — `/sdlc-frame`
  (frame one run), `/sdlc-wave` (one Seeds-backed worktree wave), `/sdlc-mission`
  (autonomous backlog-zero mission with concurrent critique and bounded backflow).
- `.claude-plugin/{plugin.json,marketplace.json}`: the repo doubles as a Claude Code
  plugin/marketplace — `claude plugin marketplace add <path-or-git-url>` then
  `claude plugin install agentic-sdlc-orchestrator@agentic-sdlc` is an alternative to
  symlinks. Both manifests pass `claude plugins validate --strict`.
- `cao-profiles/`: CAO profile templates for macro orchestration, planning, implementation,
  review, and Claude Code nested dynamic workflows.
- `scripts/check-agentic-sdlc-prereqs.sh`: preflight — required/recommended/optional tools,
  cao-server health, CAO timeout sanity, codex dir-trust check for the current repo.
- `scripts/install-skill-bundle.sh`: **one-shot global install for every agent CLI present**
  (Claude Code skill+agents+commands, Codex skill+role TOMLs, CAO skill+profiles). Symlinks
  by default (live-updates with `git pull`); `--copy` to copy. Never clobbers non-symlink files.
- `scripts/validate-bundle.sh`: pre-commit/CI gate — SKILL.md frontmatter, name==dirname,
  the 1024-char Codex description cap (silent-skip trap), broken references, TOML/JSON
  parses, shell `bash -n`, plugin manifest validation, secret/internal-hostname sweep.
- `scripts/cmux-bus.sh`: generic cmux event-bus pub/sub helper (pub/sub/seq) used by the
  cmux integration reference.
- `scripts/install-cao-kit.sh`: CAO-only install (skill + profiles).

## Install (all agents, one command)

```bash
./scripts/check-agentic-sdlc-prereqs.sh
./scripts/install-skill-bundle.sh          # Claude Code + Codex + CAO, auto-detected
./scripts/install-skill-bundle.sh status   # link health per target (exit 1 on broken)
./scripts/install-skill-bundle.sh uninstall
./scripts/install-skill-bundle.sh self-test # install→status→uninstall in a throwaway HOME
```

**Pick ONE Claude Code install path per machine** — either the symlink install above OR
the marketplace path (`claude plugin marketplace add <repo>` + `claude plugin install
agentic-sdlc-orchestrator@agentic-sdlc`), never both: dual-installing registers the skill
twice (bare + plugin-namespaced). The symlink path live-updates with `git pull`; the
marketplace path copies into Claude's plugin cache and updates via `claude plugin update`.

**After `git pull`, re-run the installer** — the symlink planes update automatically, but
the CAO plane COPIES (skill store + profiles) and goes stale otherwise.

This installs into:

| Agent | Destination | Notes |
|---|---|---|
| Claude Code | `~/.claude/skills/agentic-sdlc-orchestrator` | symlink |
| Codex | `$CODEX_HOME/skills/agentic-sdlc-orchestrator` (default `~/.codex/skills`) | symlink; NOT `~/.agents/skills` (docs are wrong). Codex silently skips skills whose `description:` exceeds 1024 chars — the installer warns. |
| CAO | CAO skill store + `cao-profiles/*` | only if `cao` on PATH |

cmux integration needs no install — the skill activates it when `CMUX_WORKSPACE_ID` is set.

## Run

Start CAO with your provider env exported in the SAME shell (workers inherit it; CAO's
`--env` flag blocks `CLAUDE*`/`CODEX_*` prefixes, so inheritance is the only path):

```bash
# example: Amazon Bedrock
AWS_PROFILE=<profile> CLAUDE_CODE_USE_BEDROCK=1 cao-server
```

Launch a macro conductor (Codex entrypoint shown; a Claude Code entrypoint works the same
with `--provider claude_code`):

```bash
cao launch --agents codex-macro-orchestrator --provider codex --headless --yolo \
  --session-name agentic-sdlc-demo \
  --working-directory '/absolute/path/to/project' \
  'Use $agentic-sdlc-orchestrator to frame the task, prime Seeds, and run a bounded CAO/DWL worktree wave.'
```

Long-running runs: launch with `--async` (or have the conductor use CAO `assign`) — CAO
timeouts only stop the caller waiting; detached tmux agents run to completion regardless.

## UX From Codex

There are two skill planes:

1. Native Codex skill use. `install-skill-bundle.sh` symlinks the skill into
   `$CODEX_HOME/skills/` so a normal Codex session understands
   `Use $agentic-sdlc-orchestrator ...` before CAO is involved.
2. CAO session skill use. CAO installs the skill into its own store and injects a CAO-only
   skill catalog into CAO-launched Codex/Claude/etc. workers. Those workers load the full
   skill body with `mcp__cao-mcp-server__load_skill`, not Codex's native `Skill(...)`.

For direct Claude Code use outside CAO, the bundle installer covers `~/.claude/skills/`.
For Claude Code launched by CAO, the CAO skill plane is enough as long as the profile
includes `cao-mcp-server`.

## Status

Core CAO mechanics trial-verified 2026-07-04 on macOS + Amazon Bedrock (CAO v2.2.0):
per-worker model pinning, nested supervisors, mixed Claude+Codex fleets, long-running
semantics, codex provider gotchas, cmux attach/view and event-bus patterns. Profiles remain
templates — validate on your repository before trusting a full unattended run.
