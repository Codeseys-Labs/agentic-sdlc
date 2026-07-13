# Agentic SDLC Orchestrator — agent instructions

This repo is a multi-skill, multi-host agent bundle (an "open plugin"): one `skills/`
tree in the cross-host Agent Skills format, thin per-host manifests, and a symlink
installer. Codex, Gemini CLI, OpenCode, and other AGENTS.md-aware hosts: read this file
as the router.

## What this bundle provides

- `skills/agentic-sdlc-orchestrator/` — the flagship skill: provider-native,
  project-scale agentic SDLC with Seeds, git worktree waves, mission/backlog-zero
  doctrine, tiered orchestration, and evidence-graded research teams. Roles and verdicts
  are advisory submissions; the conductor records evidence, and only an authorized
  integrator executes an already authorized fan-in mutation. cmux is an optional independent
  view/event layer; tmux is never a baseline requirement. Start at its `SKILL.md`; read
  `references/*.md` on demand only.
- `skills/codex-research-os/` — repo-scaffolding installer for a 17-role research
  organization with claim ledgers and review gates.
- `agents/` — seven global SDLC role agents (cartographer, planner, implementer, reviewer, researcher,
  critic, integrator) in Claude `.md` and Codex `.toml` forms, plus the repo-scoped
  research roster under `agents/codex/research/`.
- `commands/` — `/sdlc-init` activates repository-specific DevEx, tracked baseline,
  gates, trust, and shared guidance; `/sdlc-frame`, `/sdlc-wave`, and `/sdlc-mission`
  run the delivery loop (Claude Code slash commands; other hosts invoke the flagship skill
  with the same intents). Global installation and per-repository activation are separate
  lifecycle planes.
- `cao-profiles/` — retained one-release CAO compatibility tombstones; use native Frame/Wave/Mission.

## Working on THIS repo

- Run `mise run check` before any commit — it is the authoritative repository gate. It uses
  mise-managed uv/Python to validate name==dirname, the Codex 1024-char description cap,
  broken references, TOML/JSON parses, shell syntax, manifests, and secrets. A passing gate
  is evidence only; it does not authorize an outward effect.
- Run `./scripts/install-skill-bundle.sh self-test` after installer changes.
- Version bumps: `./scripts/bump-version.sh <version>` updates every manifest in one
  shot; `--check` reports drift. Never hand-edit a single manifest's version.
- Adding a skill = adding `skills/<name>/SKILL.md` (name must equal the directory
  name; description ≤1024 chars). The installer/validator/planes pick it up
  automatically.
- Keep skills host-agnostic: no user-specific paths, no provider credentials, no
  internal hostnames. Host-specific detail belongs in per-host manifests or the
  installer.

## Installing this bundle

mise 2026.4.27+ is the managed-tool bootstrap, not the sole readiness prerequisite. It pins
uv, consumes the checked-in cross-platform `mise.lock`, and uv supplies Python 3.12.11 for
all authoritative Python entrypoints. Git, a documented Seeds distribution, supported trust
behavior, and any selected adapter must be present and verified; missing, unpinned, untrusted,
or ambiguous capability means not Git-ready. Trust is scoped to each absolute config path:
every linked worktree must review and trust its own `mise.toml`; `MISE_PARANOID=1` fails closed
until that explicit trust step. The requested model tier and resolved provider/model are
separate facts: record resolved only after adapter readback, otherwise inherited or unresolved.

- `bundle:install`, `bundle:status`, `bundle:uninstall`
- `bundle:install:claude`, `bundle:install:codex`
- `bundle:install:all-hosts`, `bundle:status:all-hosts`
- `research-os:install`, `test`, `self-test`, `check`, `hooks:install`, `setup`

`/sdlc-init` is a reviewed runbook, not a deterministic activation engine. It must stop on
ambiguous ownership, conflicts, unsupported capability, or missing evidence; do not claim
idempotence or Git-wave readiness from intent alone.

Unix installs use symlinks. Windows automatic mode tries directory junctions and file
symlinks, then falls back to copies; strict link mode has no fallback. Ownership state lives
under `XDG_STATE_HOME` on Unix or `LOCALAPPDATA` on Windows. Write commands serialize on that
state file and fail closed when stable physical identity or atomic no-replace primitives are
unavailable; Linux lifecycle mutation requires glibc 2.28+ and `statx` birth-time support. Status
inspects every known v1 document without rewriting it, and ordinary lifecycle commands block
while one is outstanding. `bundle:install -- --migrate-state --dry-run` previews an exact,
state-only conversion; `bundle:install -- --migrate-state` merges all exact records from the
operator and configured-home legacy paths into central v2 without installing or refreshing
bundle entries. A distinct legacy source is retired only after durable v2 persistence and an
exact recheck. Linux/macOS persistence-barrier failures stop mutation; native Windows provides
handle-bound process-crash recovery but does not claim sudden-power-loss durability for namespace
transitions. Concurrent external mutation of managed paths during a write command is unsupported.
Exact legacy links and byte-identical copies can be adopted; foreign, retargeted, and modified
entries are preserved, while unchanged owned copies may refresh.

Native Windows runs the current-host task normally. From WSL, all-host tasks run WSL first,
then invoke native Windows mise and report the two hosts separately. `hooks:install` installs
lefthook's validate pre-commit and test/self-test pre-push subsets; hooks are best-effort
convenience, not release authority. The Bash installer is a mise-backed compatibility wrapper retaining
positional `status`, `uninstall`, `self-test`, legacy `--copy`, and retired `INSTALL_CAO=1`
which exits 2 before native installation. For Claude, use either direct install or the marketplace, never both; marketplace
overlap blocks only Claude. No local status, gate, reviewer label, or conductor choice grants
authority for push, publication, PR mutation, merge, deployment, credential, or other outward
effect; each requires explicit operation-specific authorization.
