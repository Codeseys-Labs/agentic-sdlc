# Agentic SDLC Orchestrator

Reusable, provider-native operating kit for project-scale agentic software delivery across
Codex, Claude Code, and other skill-capable hosts. CAO and cmux are optional adapters;
tmux is never a baseline requirement.

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

The baseline shape:

```text
Agent entrypoint (Codex, Claude Code, or another capable host)
  -> provider-native roles/subagents/workflows (or direct execution)
  -> Seeds queue
  -> git worktrees
  -> tests/review
  -> squash/rebase/PR

Optional adapters:
  + CAO for explicitly selected durable or mixed-engine sessions
  + cmux for an already-active view/event layer
  + tmux only when an optional adapter uses it
```

**Baseline invariant:** one capable host can run the full Frame -> Ship loop. Never install,
start, or enable CAO, cmux, or tmux merely to use this bundle; their absence never blocks
or weakens the native path.

## Contents

- `skills/agentic-sdlc-orchestrator/`: the flagship, provider-native orchestration skill
  for any skill-capable CLI agent. CAO workers can also consume it when that optional
  adapter is selected.
- `skills/codex-research-os/`: vendored research-team OS — a repo-scaffolding installer
  (`scripts/install_research_os.py`) that bootstraps a 17-role research organization
  (director + specialists), claim/experiment ledgers, greenfield/brownfield workflows,
  schemas, and Make validation gates into any target repo. Pairs with the flagship's
  `references/research-team.md` (the distilled principles).
- `skills/model-tier-rightsizing/`: the four-tier model policy for fleets — frontier =
  solo scale-setters, judgment-workhorse = un-gated judgment, capable-volume = the
  gated-parallel default, mechanical = gate-checked floor. Decision ladder
  (derail/degrade/retry), alias plumbing, quota-aware concurrency math, worked quota
  table (re-derive per account). Pairs with `references/tiered-orchestration.md`.
- `skills/cmux-event-bus-messaging/`: optional cmux-only event-bus pub/sub pattern (publish via
  `cmux log --source msg:<topic>`, subscribe via `cmux events` with replay/resume, the
  claim-check pattern, both race gotchas). Pairs with `references/cmux-integration.md`
  and `scripts/cmux-bus.sh`.
- `skills/repo-toolchain-gates/`: the standard local gate stack — mise (pinned toolchain
  incl. CI-parity linter pins + task-runner; `mise run check` = THE gate), lefthook
  (pre-commit/pre-push enforcement, installed via mise `[tools]`), betterleaks (secrets
  gate incl. full-history scans). Includes the two verified worktree facts: hooks ARE
  shared into worktrees, mise trust is NOT. Pairs with `references/seeds-worktrees.md`.
- `skills/stacked-prs/`: the tool-agnostic stacked-PR methodology — ship a chain of small
  dependent PRs instead of one fat branch (small-batch rationale, stack structure,
  bottom-up merge, the restack discipline, when NOT to stack). The PR-landing strategy for
  dependent Seeds in a wave.
- `skills/stacked-prs-gh-cli/`: the same with ONLY plain `gh` + git — no gt/spr/ghstack.
  gh has no `stack` command (v2.95); GitHub's primitives are `--base` targeting + native
  auto-retarget-on-merge. Covers the squash-merge `--onto` restack gotcha and
  `--force-with-lease` safety. Pairs with `stacked-prs` and the jj-vcs reference.
  - `references/sdlc-loop.md` — phase gates, backflow, done criteria.
  - `references/seeds-worktrees.md` — Seeds queue, native worktree waves, PR flow, and
    optional worker/view adapters.
  - `references/cao-profiles.md` — optional CAO adapter profiles + launch pattern.
  - `references/cao-operations.md` — optional, **trial-verified** CAO operations. Load only
    after selecting an active CAO path.
  - `references/cmux-integration.md` — optional cmux view/event integration. Load only when
    cmux is already active or explicitly requested.
  - `references/delegation-planes.md` — native-first per-provider decision matrices plus
    optional durable/mixed-engine adapters.
  - `references/worktree-integration.md` — fan-in hazards: merge-base footprint, placeholder
    traps, re-gate-on-main, clean-apply ≠ semantic correctness, squash-scope discipline.
  - `references/mission-loop.md` — the autonomous **backlog-zero doctrine**: 8-class
    milestone classification (only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes,
    WIP caps, priority math, the concurrent critique team, honest definition of done.
  - `references/tiered-orchestration.md` — **model-tier assignment** (the multiplier
    principle: frontier tier only on solo scale-setters — frame/plan/verdict), a native-first
    capability ladder with optional adapters, **bounded backflow**, chained iterations,
    and worker lifecycle at scale.
  - `references/research-team.md` — **evidence-graded research teams** for standing
    research efforts: the evidence ladder (promote slowly, downgrade quickly), role
    separation-of-powers (attacker ≠ fixer, writer ≠ originator), one-loop discipline
    with a recorded next-action, greenfield/brownfield loops, the cheapest-decisive-
    experiment rule, gates-as-executables (no decorative model pins).
  - `references/jj-vcs.md` — **jj (Jujutsu) as the wave substrate** (verified on 0.43):
    colocated adoption (CI sees plain git), workspaces as agent-grade worktrees with
    op-log audit + stale detection, never-failing fan-in (conflicts = committed state),
    auto-snapshot (uncommitted-work loss impossible) + `jj undo`; gotchas: git hooks
    don't fire, `description("x")` exact-match trap, headless identity, snapshot
    swallows non-gitignored secrets.
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
- `commands/sdlc-{init,frame,wave,mission}.md`: Claude Code slash commands —
  `/sdlc-init` (bootstrap a new/existing project onto the system: VCS incl. optional
  jj colocation, Seeds queue, mise/lefthook/betterleaks gate stack with falsifiability
  proof, trust, CLAUDE.md wiring — ends wave-ready), `/sdlc-frame` (frame one run),
  `/sdlc-wave` (one Seeds-backed worktree wave), `/sdlc-mission` (autonomous
  backlog-zero mission with concurrent critique and bounded backflow).
- `.claude-plugin/{plugin.json,marketplace.json}`: the repo doubles as a Claude Code
  plugin/marketplace — `claude plugin marketplace add <path-or-git-url>` then
  `claude plugin install agentic-sdlc-orchestrator@agentic-sdlc` is an alternative to
  symlinks. Both manifests pass `claude plugins validate --strict`.
- `cao-profiles/`: optional CAO adapter templates for macro orchestration, planning,
  implementation, review, and nested dynamic workflows.
- `scripts/check-agentic-sdlc-prereqs.sh`: native-baseline preflight plus informational
  checks for optional adapters. Missing CAO, cmux, or tmux never fails it.
- `scripts/install-skill-bundle.sh`: **one-shot global install for every native agent CLI
  present** (Claude Code skill+agents+commands, Codex skill+role TOMLs). Optional CAO
  mirroring requires the explicit `INSTALL_CAO=1` opt-in. Symlinks by default; `--copy`
  to copy. Never clobbers non-symlink files.
- `scripts/validate-bundle.sh`: pre-commit/CI gate — SKILL.md frontmatter, name==dirname,
  the 1024-char Codex description cap (silent-skip trap), broken references, TOML/JSON
  parses, shell `bash -n`, plugin manifest validation, secret/internal-hostname sweep.
- `scripts/cmux-bus.sh`: optional cmux-only event-bus helper (pub/sub/seq).
- `scripts/install-cao-kit.sh`: optional CAO-only adapter install (skill + profiles).

## Install (all agents, one command)

The native baseline requires `git`, `gh`, `sd` (Seeds), and any skill-capable host.
CAO, cmux, and tmux are not baseline tools and are never installed or enabled implicitly.

This upstream repository's root `mise.toml` manages exact versions of both
`lefthook` (`2.1.10`) and `jj` (`0.43.0`). `mise install` makes both CLIs reproducible
across contributor machines. That manages tool availability only: hooks still require a
`lefthook.yml` plus `lefthook install`, and jj remains opt-in until a clone explicitly runs
`jj git init --colocate`. On Windows, the checked-in mise tasks route the bundle's Bash
scripts through Git Bash with `scripts/run-git-bash.ps1`; they never select the WSL
`bash.exe` launcher accidentally.

```bash
mise install                               # install pinned upstream lefthook + jj CLIs
mise run check                             # full local gate (or run the two scripts below directly)
./scripts/check-agentic-sdlc-prereqs.sh
./scripts/install-skill-bundle.sh          # native hosts; never enables optional adapters
./scripts/install-skill-bundle.sh status   # link health per target (exit 1 on broken)
./scripts/install-skill-bundle.sh uninstall # removes owned symlinks; preserves copies/adapters
./scripts/install-skill-bundle.sh self-test # verifies symlink removal/copy preservation safely
```

**Pick ONE Claude Code install path per machine** — either the symlink install above OR
the marketplace path (`claude plugin marketplace add <repo>` + `claude plugin install
agentic-sdlc-orchestrator@agentic-sdlc`), never both: dual-installing registers the skill
twice (bare + plugin-namespaced). The symlink path live-updates with `git pull`; the
marketplace path copies into Claude's plugin cache and updates via `claude plugin update`.

**After `git pull`, symlinked native skill planes update automatically.** Existing
copy-mode destinations are deliberately not overwritten; remove or move only the
bundle-owned copy you intend to refresh, then rerun with `--copy`. If you explicitly
maintain a CAO mirror, refresh it separately with
`INSTALL_CAO=1 ./scripts/install-skill-bundle.sh`.

This installs into:

| Agent | Destination | Notes |
|---|---|---|
| Claude Code | `~/.claude/skills/agentic-sdlc-orchestrator` | symlink |
| Codex | `$CODEX_HOME/skills/agentic-sdlc-orchestrator` (default `~/.codex/skills`) | symlink; NOT `~/.agents/skills` (docs are wrong). Codex silently skips skills whose `description:` exceeds 1024 chars — the installer warns. |
| Optional CAO adapter | CAO skill store + `cao-profiles/*` | explicit opt-in only: `INSTALL_CAO=1`; never selected by detection alone |

cmux needs no bundle setup. Its optional integration activates only when the cmux CLI and
`CMUX_WORKSPACE_ID` are already present or the user explicitly requests it.

## Run (native baseline)

Invoke the skill directly from any installed host:

```text
Use $agentic-sdlc-orchestrator to frame this task and run a bounded,
Seeds-backed worktree wave using the host's native agents.
```

The conductor uses direct execution or provider-native roles, subagents, workflows, teams,
and background tasks. This is the complete path; CAO, cmux, and tmux are not setup steps.

### Optional CAO adapter

Use this only when CAO was explicitly selected and is already installed for durable or
mixed-engine sessions. Start `cao-server` with the provider environment in the same shell,
then launch the optional macro profile:

```bash
cao launch --agents codex-macro-orchestrator --provider codex --headless --yolo \
  --session-name agentic-sdlc-demo \
  --working-directory '/absolute/path/to/project' \
  'Use $agentic-sdlc-orchestrator to run a bounded worktree wave with the selected CAO adapter.'
```

For CAO-specific environment inheritance, timeouts, and tmux-backed session behavior, load
`references/cao-operations.md`. Do not apply those requirements to native runs.

## UX From Codex

Native Codex skill use is the baseline and complete path. `install-skill-bundle.sh`
installs the skill into `$CODEX_HOME/skills/`, so a normal Codex session can run the full
loop with provider-native roles and subagents.

If the optional CAO adapter is explicitly selected, opt into its separate mirror with
`INSTALL_CAO=1 ./scripts/install-skill-bundle.sh`. That mirror is an integration detail,
not a prerequisite or a second setup step for ordinary Codex use.

## Optional integration status

The native provider path is the supported baseline. Optional CAO mechanics were
trial-verified 2026-07-04 on macOS + Amazon Bedrock (CAO v2.2.0), including per-worker model
pinning, mixed-engine fleets, and long-running semantics. Optional cmux view/event patterns
were also trial-verified. These adapters remain templates; validate them on the target
repository before using them for unattended runs.
