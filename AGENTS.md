# Agentic SDLC Orchestrator — agent instructions

This repo is a multi-skill, multi-host agent bundle (an "open plugin"): one `skills/`
tree in the cross-host Agent Skills format, thin per-host manifests, and a symlink
installer. Codex, Gemini CLI, OpenCode, and other AGENTS.md-aware hosts: read this file
as the router.

## Vision and self-hosting

Read [VISION.md](VISION.md) for the durable product intent. Work on this repository must use the same contracts intended for downstream projects: evidence-led activation, isolated writers, advisory review, one integrator for fan-in, and explicit authorization for outward effects.

## What this bundle provides

- `skills/agentic-sdlc/` — the flagship skill: provider-native,
  project-scale agentic SDLC with Seeds, git worktree waves, mission/backlog-zero
  doctrine, tiered orchestration, and evidence-graded research teams. Roles and verdicts
  are advisory submissions; the conductor records evidence, and only an authorized
  integrator executes an already authorized fan-in mutation. cmux is an optional independent
  view/event layer; tmux is never a baseline requirement. Start at its `SKILL.md`; read
  `references/*.md` on demand only.
- `skills/codex-research-os/` — repo-scaffolding installer for a 17-role research
  organization with claim ledgers and review gates.
- `skills/model-tier-rightsizing/` — first-class routing skill for every model-dispatching
  consumer. It owns four semantic tiers: paired Sol/Fable frontier, Terra/Opus judgment
  workhorse, Luna/Sonnet capable volume, and the cheapest certified fully gated mechanical
  floor. Load it before dispatch; choose within a pair by task fit, independent perspective,
  quota, and verified transport—not global provider preference or all-six tokenism. Before
  spawn, the conductor supplies a fully resolved conductor-supplied certified exact model ID
  in a `RuntimeAssignment`; otherwise dispatch stops. Its
  canonical calibration preserves evidence, quotas, complements, fallbacks, controls, and
  roadmap lanes.
- `agents/` — seven global SDLC role agents (cartographer, planner, implementer, reviewer, researcher,
  critic, integrator) in Claude `.md` and Codex `.toml` forms, plus the repo-scoped
  research roster under `agents/codex/research/`.
- `commands/` — `/sdlc-init` activates repository-specific DevEx, tracked baseline,
  gates, trust, and shared guidance; `/sdlc-frame`, `/sdlc-wave`, and `/sdlc-mission`
  run the delivery loop (Claude Code slash commands; other hosts invoke the flagship skill
  with the same intents). Global installation and per-repository activation are separate
  lifecycle planes.

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

mise 2026.4.27+ is the only bootstrap prerequisite; it is the managed-tool bootstrap, not the
sole readiness prerequisite. It pins uv, consumes the checked-in cross-platform `mise.lock`, and
uv supplies Python 3.12.11 for all authoritative Python entrypoints. Git, a verified Seeds
distribution, supported trust behavior, repository gates, and any selected adapter remain
runtime-readiness capabilities, not additional bootstrap prerequisites; missing, unpinned,
untrusted, or ambiguous capability means not Git-ready. Trust is scoped to each
absolute config path: every linked worktree must review and trust its own `mise.toml`, and
`MISE_PARANOID=1` fails closed until that explicit trust step. Persistent `mise trust`,
Codex/global config, shell-alias, and credential mutations each require explicit
operation-specific user approval; process-scoped `mise --no-config` test execution is allowed
without persisting trust. Never make permanent Windows environment/trust/config changes.

To acquire Seeds from an exact clean Git distribution root, run the installed flagship
`tools/seeds-launcher.mjs bootstrap --distribution <distribution-root>` under Node 22.22.3.
Bootstrap and inspect both reject any other executing Node. Bootstrap rejects nested, staged,
dirty, untracked, or ignored distribution content, then explicitly invokes reviewed
`mise --locked install` with isolated HOME, mise config/data/cache, hooks, npmrc files, and fixed
official registry/npm backend. Ambient npm/mise config cannot select acquisition. It resolves only
config-free exact roots, validates Node 22.22.3, Bun 1.3.10, and the
`npm:@os-eco/seeds-cli@0.5.14` package/bin/layout; the released package's string `engines.bun` is
benign while actual config/macro/preload controls remain forbidden. It then atomically records the
exact Git commit/tree, tool hashes, and a prior receipt for rollback. Inspect is separate and never
installs, networks, invokes mise, or repairs: it admits only an active receipt and exact current
hashes, accepts only `--version`, `prime`, `ready [--format json]`, and
`blocked [--format json]`, then Node starts the exact absolute Bun/entry with `shell:false`, a
trusted empty Bun config, and no ambient runtime options. The child environment is an allowlist,
including a PATH limited to a separately recorded Git directory and portable Git config isolation.
Target/ambient Bun, Node, npm, mise, and unreviewed Seeds debug controls have no effect. The
receipt detects ordinary drift, not a same-UID TOCTOU racer. The Seeds lock proves the exact
version and npm backend, not tarball or transitive dependency integrity. Never accept ambient
Seeds provenance.

Before spawn, the conductor supplies a certified `RuntimeAssignment` with requested
model/effort/context values; `resolution_state` must be `resolved`. Exact model/effort request
injection is mandatory and immutable. The requested model tier and the resolved provider/model
are separate facts: requested model selection is recorded as resolved, inherited, or unresolved,
and it is never proof. `resolved_provider` and `resolved_model_id` require verified model
identity; an independently observed provider/model source may be unavailable only for an
unambiguous exact-ID mapping backed by immutable request/model evidence, and resolved is recorded
only after adapter readback. Effective effort/context readback may be honestly unavailable, and
requested values never become readback. Requested, inherited, unresolved, or incomplete
assignments stop before dispatch and therefore stop before spawn. The selected host or launcher
must inject the exact requested model and effort; if it cannot inject both, return one
SeedProposal, not a dispatch. Prompt prose does not enforce a Codex model or effort.
Provider-neutral roles contain no static model or effort pin and never recommend host-default
model selection as policy.

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
positional `status`, `uninstall`, `self-test`, and legacy `--copy`.
For Claude, use either direct install or the marketplace, never both; marketplace
overlap blocks only Claude. No local status, gate, reviewer label, or conductor choice grants
authority for push, publication, PR mutation, merge, deployment, credential, or other outward
effect; each requires explicit operation-specific authorization.
