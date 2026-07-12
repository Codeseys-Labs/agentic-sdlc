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

## Install and run the bundle

**mise is the sole prerequisite.** The checked-in `mise.toml` pins `uv`; `uv` supplies the
pinned Python `3.12.11` runtime used by the stdlib installer. You do not need to install
Python, uv, Bash, or a host-specific Python environment separately. Optional CAO, cmux, and
tmux adapters are never installed or enabled by setup.

Bootstrap the repository and inspect the available lifecycle tasks:

```bash
mise install
mise tasks
```

The public task surface is intentionally small:

| Task | Purpose |
|---|---|
| `bundle:install` / `bundle:status` / `bundle:uninstall` | Install, inspect, or remove entries for the current host. |
| `bundle:install:claude` | Install only the Claude Code plane on the current host. |
| `bundle:install:codex` | Install only the Codex plane on the current host. |
| `bundle:install:all-hosts` | Install the current host and, from WSL, the native Windows host too. |
| `bundle:status:all-hosts` | Report current-host and native-Windows state when run from WSL. |
| `test` | Run the installer test suite. |
| `self-test` | Exercise install/status/uninstall in an isolated home. |
| `check` | Run the authoritative validation, tests, and self-test gate. |
| `hooks:install` | Install the checked-in lefthook hooks. |
| `jj:init` | Explicitly initialize a colocated jj repository. |
| `setup` | Bootstrap the pinned toolchain and repository setup. |

A normal Unix install uses symlinks. On Windows, automatic mode uses directory junctions
for directories and file symlinks for files; when the host cannot create those links it
falls back to copies. Strict link mode does not use that fallback. The installer records
per-entry ownership in the platform state directory (`XDG_STATE_HOME` on Unix,
`LOCALAPPDATA` on Windows), so lifecycle operations can distinguish bundle entries from
user files.

```bash
mise run bundle:install
mise run bundle:status
mise run check
```

The native Windows path runs the ordinary current-host task; it does not invoke WSL. When
`bundle:install:all-hosts` or `bundle:status:all-hosts` is run from WSL, it runs the WSL
current-host lifecycle first and then invokes the native Windows mise task. The two host
summaries remain separate, and the native task's arguments and exit code are preserved.

### Safe migration and lifecycle rules

Use the installer's dry-run option before migrating an existing installation. The dry-run
sequence is:

1. inspect the current entries and ownership state;
2. report links, copies, adoptions, and conflicts without changing files or state;
3. review the plan, then run the same operation without dry-run;
4. run `bundle:status` (or `bundle:status:all-hosts`) and `check`.

Collection directories are never replaced. An exact legacy bundle link or byte-identical
copy may be adopted into ownership. Foreign entries, retargeted links, and modified copies
are preserved and reported as conflicts. Owned copies are refreshed only while they remain
unchanged from the last recorded bundle content; user modifications are never overwritten.
Uninstall removes only owned entries and leaves conflicts and foreign files in place.

For Claude Code, choose exactly one distribution plane per machine: either the direct
bundle install or the Claude marketplace install (`claude plugin marketplace add` followed
by `claude plugin install`). Marketplace overlap blocks only the Claude plane; other host
planes can still be managed. Do not register both, because the same skill would appear once
as a bare skill and again under the plugin namespace.

### Hooks and jj

`hooks:install` installs the lefthook subsets from this repository: pre-commit runs
`mise run validate`; pre-push runs `mise run test` and `mise run self-test`. `mise run check`
remains the complete local gate and is the command CI mirrors.

`jj:init` is explicit and is not a dependency of `setup`. A colocated jj repository keeps
Git interoperability, but jj commands bypass Git hooks; run `mise run check` (and any
relevant task) explicitly when working through jj.

### Compatibility wrapper and optional adapters

`scripts/install-skill-bundle.sh` remains a compatibility wrapper for existing automation.
It requires mise, invokes the pinned uv/Python installer, forwards supported arguments, and
retains positional `status`, `uninstall`, and `self-test` plus legacy `--copy` behavior.
It does not select CAO automatically. `INSTALL_CAO=1` is an explicit opt-in for the
separate CAO mirror after the native install; CAO, cmux, and tmux are never prerequisites.

The native host path is complete without an adapter:

```text
Use $agentic-sdlc-orchestrator to frame this task and run a bounded,
Seeds-backed worktree wave using the host's native agents.
```

If CAO was explicitly selected and is already installed, use its separate adapter flow and
load `references/cao-operations.md` for CAO-specific behavior. Do not apply CAO, cmux, or
tmux requirements to native runs.

## Run (native baseline)

Native host agents, provider-native roles, subagents, workflows, teams, and background tasks
are the complete supported path. CAO, cmux, and tmux are optional integrations, not setup
steps or hidden dependencies.
