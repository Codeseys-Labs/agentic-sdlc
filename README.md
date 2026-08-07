# Agentic SDLC Orchestrator

Reusable, provider-native operating kit for project-scale agentic software delivery across
Codex, Claude Code, and other skill-capable hosts. cmux is an optional view/event layer;
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

Adding a skill means adding a `skills/<name>/SKILL.md` directory. The installer, validator, and
all distribution planes pick it up automatically. Never hand-edit one manifest's version.
`scripts/bump-version.sh <x.y.z>` writes all of them; `--check` reports drift in CI.

The baseline shape:

```text
Agent entrypoint (Codex, Claude Code, or another capable host)
  -> provider-native roles/subagents/workflows (or direct execution)
  -> Seeds queue
  -> git worktrees
  -> tests/review
  -> squash/rebase/PR

Optional adapters:
  + cmux for an already-active view/event layer
  + tmux only when an optional adapter uses it
```

**Capability-negotiated baseline:** a host may run the native Frame -> Ship loop only after the
required Git, Seeds, gate, trust, and selected-adapter capabilities are present, pinned where
applicable, and verified. Missing, untrusted, unpinned, or ambiguous required capability
fails closed. An unselected optional adapter does not block the native path. Never install,
start, or enable cmux or tmux merely to use this bundle.

## Contents

**This bundle installs only its own skills, agents, and commands, and never fetches,
renders, or installs a third-party skill library.** No task or installer path in it reaches
a foreign catalog — hyperresearch, ECC (`affaan-m/ECC`), `mattpocock/skills`, or any other.
A library the operator wants is the operator's own install, through that library's own front
door; this bundle's installer classifies those foreign entries as `foreign` and preserves
them, so the two coexist safely. Foreign ideas enter here only as an adapted
`references/*.md` with a root `NOTICE` donor entry. Decision and evidence:
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md`.

- `skills/agentic-sdlc/`: the flagship, provider-native orchestration skill
  for any skill-capable CLI agent.
- `skills/codex-research-os/`: vendored research-team OS — a repo-scaffolding installer
  (`scripts/install_research_os.py`) that bootstraps a 17-role research organization
  (director + specialists), claim/experiment ledgers, greenfield/brownfield workflows,
  schemas, and Make validation gates into any target repo. Pairs with the flagship's
  `references/research-team.md` (the distilled principles).
- `skills/model-tier-rightsizing/`: first-class model-routing skill. Load it before any
  model dispatch. Its four-tier policy pairs exact Sol/Fable for frontier derail work,
  Terra/Opus for judgment-workhorse silent-degrade work, and Luna/Sonnet for capable-volume
  visible-retry work; the mechanical floor selects the cheapest certified fully gated route.
  The canonical calibration records exact IDs, explicit requested effort, transport hazards,
  evidence boundaries, complements, controls, quotas, and roadmap lanes. Selection is by task
  fit, independent perspective, quota, and verified transport—not provider preference or
  artificial all-six representation. The flagship hands off through
  `references/tiered-orchestration.md`.
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
  gh has no `stack` command (v2.95); GitHub's primitives are `--base` targeting + explicit
  retarget/requery/restack. Covers the squash-merge `--onto` restack gotcha and
  `--force-with-lease` safety. Pairs with `stacked-prs`.
  - `references/sdlc-loop.md` — phase gates, backflow, done criteria.
  - `references/seeds-worktrees.md` — Seeds queue, native worktree waves, PR flow, optional
    worker/view adapters, and the canonical in-workspace `.worktrees/<seed-id>-<slug>/`
    substrate rule (never a sibling directory).
  - `references/worktree-lifecycle.md` — one wave worktree end to end, each step with its
    refusal and recovery: create, gate, review, integrate (squash-preferred, and why),
    reconcile through the conductor-only record seam, clean up. Includes the executed Git
    facts behind those refusals.
  - `references/cmux-integration.md` — optional cmux view/event integration. Load only when
    cmux is already active or explicitly requested.
  - `references/delegation-planes.md` — native-first per-provider decision matrices plus
    optional durable/mixed-engine adapters.
  - `references/worktree-integration.md` — fan-in hazards: merge-base footprint, placeholder
    traps, re-gate-on-main, clean-apply ≠ semantic correctness, squash-scope discipline.
  - `references/mission-loop.md` — the autonomous **backlog-zero doctrine**: 8-class
    milestone classification (only ACTIVE_MILESTONE executes), seeds-first no-inline-fixes,
    WIP caps, priority math, the concurrent critique team, honest definition of done.
  - `references/tiered-orchestration.md` — model-tier assignment, honest provider/model
    resolution, the native-first capability ladder with optional adapters, bounded backflow,
    and worker lifecycle at scale.
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
  critic concurrent, researchers on demand. Provider-neutral role definitions contain no static
  model/effort pin, never dispatch, and consume a conductor-supplied certified
  `RuntimeAssignment` with a certified exact model ID. `resolution_state` must be `resolved`.
  Exact model/effort request injection is mandatory and immutable. `resolved_provider` and
  `resolved_model_id` require verified model identity; independently observed provider/model
  source may be unavailable only for a unique exact-ID mapping backed by immutable request/model
  evidence. Effective effort/context readback may be honestly unavailable; requested values never
  become readback. If the assignment is requested, inherited, unresolved, incomplete, or cannot
  inject both requested model and effort, the conductor stops before dispatch and returns one
  SeedProposal. Prompt prose does not enforce a Codex model or effort.
- `agents/codex/research/`: the 17-role research-team TOMLs (repo-scoped reference
  copies — NOT globally installed; see its README; scaffolded per-repo by
  codex-research-os).
- `commands/sdlc-{init,frame,wave,mission}.md`: Claude Code slash commands —
  `/sdlc-init` activates Agentic SDLC inside a repository without reinstalling global
  capabilities. It establishes a reviewed tracked Git baseline, Seeds queue,
  mise/lefthook/betterleaks gate stack, per-worktree trust policy, cross-host `AGENTS.md`
  guidance, and CI parity. It is a reviewed runbook: claims of idempotence or Git-wave readiness
  require observed evidence; it preserves existing project policy and stops on ambiguity. `/sdlc-frame` frames one run,
  `/sdlc-wave` runs one Seeds-backed Git-worktree wave, and `/sdlc-mission` runs an
  autonomous backlog-zero mission with concurrent critique and bounded backflow.
- `.claude-plugin/{plugin.json,marketplace.json}`: the repo doubles as a Claude Code
  plugin/marketplace — `claude plugin marketplace add <path-or-git-url>` then
  `claude plugin install agentic-sdlc@agentic-sdlc` is an alternative to
  symlinks. The marketplace source may be this repository's public Git URL, so no clone
  is required first; see [Install as a Claude Code plugin](#install-as-a-claude-code-plugin).
  `plugin/` is the marketplace entry's `source`: a directory holding only the plugin
  manifest plus symlinks to `skills/`, `agents/claude/`, `commands/`, and
  `output-styles/`. It exists because Claude Code discovers agents only in a plugin
  root's own `agents/`, and this repo nests the Claude roster one level down under
  `agents/claude/`; installing from the repo root therefore finds the skills but zero
  agents. Claude Code dereferences within-marketplace symlinks when it copies a plugin
  into its cache, so the installed copy is real files. The marketplace manifest and
  `plugin/` both pass `claude plugin validate --strict`; validating the repo root as a
  plugin passes non-strict only (strict flags two deliberate repo files — the root
  `CLAUDE.md` and the Codex roster README — as plugin warnings).
- `scripts/check-agentic-sdlc-prereqs.sh`: native-baseline preflight plus informational
  checks for optional adapters. Missing cmux or tmux never fails it.
- `scripts/install-skill-bundle.sh`: **one-shot global install for every native agent CLI
  present** (Claude Code skill+agents+commands, Codex skill+role TOMLs). Symlinks by default; `--copy`
  to copy. Never clobbers non-symlink files.
- `scripts/validate-bundle.sh`: pre-commit/CI gate — SKILL.md frontmatter, name==dirname,
  the 1024-char Codex description cap (silent-skip trap), broken references, TOML/JSON
  parses, shell `bash -n`, plugin manifest validation, secret/internal-hostname sweep.
- `scripts/cmux-bus.sh`: optional cmux-only event-bus helper (pub/sub/seq).

## Install and run the bundle

### Quickstart from a clean clone

Five steps, in order, from an empty directory. Step 3 is a persistent mutation with its own
approval gate; steps 2 and 3 are what a fresh clone otherwise fails on.

1. Clone the repository and enter it. Obtaining the source needs Git, which stays a
   runtime-readiness capability rather than a second bootstrap prerequisite:

   ```bash
   git clone https://github.com/Codeseys-Labs/agentic-sdlc.git
   cd agentic-sdlc
   ```

2. Review the two files that step 3 authorizes: `mise.toml` (the pinned toolchain and every
   task command) and `mise.lock` (per-platform source URLs and SHA-256 checksums). Read them
   before trusting them; the trust decision covers whatever they say at that moment.

3. Trust the reviewed config. This is a persistent per-path mutation. It requires explicit
   operation-specific approval for that exact config path; a general clone, run, or
   implementation approval never covers it:

   ```bash
   mise trust ./mise.toml
   ```

   Skipping this step is the first-run failure: every later `mise` command in the repository
   exits with `config files are not trusted`. To validate without persisting anything, use
   `mise --no-config --cd . exec ...` instead of trusting.

4. Resolve the locked toolchain. The first run downloads roughly 1.3 GB across the 13 pinned
   tools and takes about 30 seconds on a warm network. mise ships `auto_install` enabled.
   Skipping this step does not avoid the cost: the first `mise run <task>` installs all 13
   without prompting.

   ```bash
   mise --locked install
   ```

5. Install this host's bundle entries:

   ```bash
   mise run bundle:install
   ```

Then `mise run bundle:status` reports ownership as either `no owned entries for this host` or an
`N ok, M conflict, K absent` summary. `mise run check` runs the authoritative gate. Each
command's exit code and output are evidence about that run only; neither authorizes any outward
effect.

**Mise 2026.4.27 or newer is the only bootstrap prerequisite.** It is the managed-tool bootstrap,
not the sole readiness prerequisite. The checked-in `mise.toml` pins `uv`. `mise.lock` records
source URLs and SHA-256 checksums for Linux, macOS, and Windows. `uv` supplies Python `3.12.11`
for every authoritative Python entrypoint. Git, a verified Seeds distribution, supported trust
behavior, repository gates, and the selected adapter remain runtime-readiness capabilities, not
additional bootstrap prerequisites. Resolve and record the actual provider/model only when the
adapter proves it; otherwise record inherited or unresolved.

Every v1 dispatch receipt uses exactly `requested_model_id`, `requested_effort`,
`requested_context_form`, request-injection evidence, resolved provider/model identity evidence,
and effective effort/context readback status plus evidence. Request-injection evidence binds
canonical exact requested model/effort/context bytes, adapter identity/version/config digest, and
request-byte digest. It validates internal consistency only: it never proves external injection,
no-bypass enforcement, or spawned-worker identity. Effective effort/context may be `unavailable`
when the transport does not expose them; requested values never become readback. An external
harness calls receipt admission immediately before spawn and correlates its digest. It remains
responsible for injection, no-bypass, and spawn identity; this repository supplies no host
launcher. Only an admitted, certified tuple can reach spawn. Exact Claude `[1m]` forms remain
denied pending tuple-specific policy evidence; base Claude eligibility and calibration-supported
GPT `[1m]` tuples remain. A passing local status or gate never authorizes push, publication, PR
mutation, merge, deployment, credential, or other outward effect.

The flagship skill ships the portable Node-stdlib `tools/seeds-launcher.mjs`. From an exact clean
Git distribution root, run its explicit `bootstrap --distribution <distribution-root>` mode under
Node `22.22.3`. Both bootstrap and inspect reject any other executing Node. Bootstrap rejects
nested, staged, dirty, untracked, or ignored distribution content, then alone runs reviewed
`mise --locked install`. That install isolates HOME, mise config/data/cache, hooks, npmrc, and
registry selection from ambient values. Only the reviewed root `mise.toml`/adjacent lock, the
fixed official npm registry, npm backend, and private empty configs select acquisition. It
resolves exact config-free Node `22.22.3`, Bun `1.3.10`, and Seeds `npm:@os-eco/seeds-cli@0.5.14`
roots. It accepts the released package's benign string `engines.bun` compatibility metadata
while rejecting actual config/macro/preload controls. It atomically publishes an exact Git
commit/tree and tool-hash receipt. The Seeds lock proves the exact version and npm backend, not
tarball or transitive dependency integrity. Neither that claim nor the receipt closes a same-UID
TOCTOU race between validation and execution.

Before any persistent `mise trust` operation—including the bootstrap below—obtain explicit
operation-specific approval for the exact reviewed config path. The same gate applies to
persistent Codex/global config edits, shell aliases, and credential writes; a general run or
implementation approval is insufficient. Process-scoped validation may instead use
`mise --no-config --cd <repo> exec ...` without persisting trust.

Bootstrap the repository and inspect the available lifecycle tasks:

```bash
mise -C <distribution-root> tasks
<exact-node-22.22.3-root>/bin/node <installed-flagship>/tools/seeds-launcher.mjs bootstrap --distribution <exact-clean-git-root>
```

After explicit bootstrap, Seeds operations from any target use `inspect --target <target>` against
only the active receipt. Inspect never installs, networks, calls mise, or repairs state. It allows
only `--version`, `prime`, `ready [--format json]`, and `blocked [--format json]`; all other input
fails before exact Bun starts. Exact Node uses `shell:false` to invoke only absolute recorded Bun
and entry paths. Bun receives `--config=<trusted-empty-file>`, `--no-env-file`, and `--no-install`;
its allowlisted environment isolates target `bunfig`, `.env`, package configuration, ambient
`BUN_*`, `NODE_OPTIONS`, npm/mise overrides, and unreviewed Seeds debug settings. PATH contains
only the independently recorded Git directory, with system/global Git config isolation. The skill
and `references/seeds-worktrees.md` define the unambiguous `Seeds(<target>, <args...>)` shorthand.

Mise trust is scoped to each absolute config path. Every linked worktree needs separate
explicit operation-specific approval before trusting its reviewed `mise.toml`, after reviewing
the diff. `MISE_PARANOID=1` deliberately rejects an untrusted worktree. After that approval,
apply `MISE_PARANOID=1 mise trust <worktree>/mise.toml`, then rerun the command. Locked
resolution fails closed when the current platform is absent from `mise.lock`.

Every task this repository defines, so `mise tasks` never reveals an undocumented one:

| Task | Purpose |
|---|---|
| `bundle:install` / `bundle:status` / `bundle:uninstall` | Install, inspect, or remove entries for the current host. |
| `bundle:install:claude` | Install only the Claude Code plane on the current host. |
| `bundle:install:codex` | Install only the Codex plane on the current host. |
| `bundle:install:all-hosts` | Install the current host and, from WSL, the native Windows host too. |
| `bundle:status:all-hosts` | Report current-host and native-Windows state when run from WSL. |
| `research-os:install` | Scaffold the repo-scoped research OS through pinned uv/Python; pass installer arguments after `--`. `--target` is required, so there is no implicit current-directory scaffold. |
| `operator-tools:install` / `operator-tools:status` / `operator-tools:uninstall` | Explicitly manage the Unix statusline and anywhere opencodex launch commands in an existing user PATH. |
| `operator-tools:self-test` | Exercise the operator-command lifecycle in an isolated home. |
| `claude:statusline:status` / `claude:statusline:activate` / `claude:statusline:deactivate` | Inspect or explicitly manage only Claude Code's `statusLine` fields. |
| `ocx:launch` / `ocx:ultracode` | Launch the supervised split plane normally or with session-only Ultracode and ordinary permissions. |
| `ocx:status` / `ocx:restart` / `ocx:configure` | Report opencodex gateway reachability, restart it cleanly, or configure providers through their own login flows. |
| `muse:launch` / `muse:status` / `muse:probe` | Drive the Muse Spark fallback direct route: launch it, report its configuration and reachability, or probe its catalog plus one tiny completion without launching. The primary route stays `ocx:launch`. |
| `mermaid:provision` | Provision the pinned Linux x64 Mermaid browser runtime. Downloads a pinned browser, so it is an explicit operator step and never a gate leaf. |
| `mermaid:linux-test` | Run the bounded Linux Mermaid renderer tests; they skip with named reasons when the runtime is absent. |
| `validate` | Run the portable bundle validator alone (the pre-commit hook's subset). |
| `test` | Run the installer test suite. |
| `self-test` | Exercise install/status/uninstall in an isolated home. |
| `secrets` | Scan the working tree with the pinned scanner and the tracked extend-only config. History scanning stays a separate consented step. |
| `check` | Run the authoritative validation, tests, self-test, and secrets gate: about 7 minutes, 572 tests as last measured. The count grows with the suite; the gate's verdict, not the count, is the evidence. |
| `hooks:install` | Install the checked-in lefthook hooks. |
| `setup` | Bootstrap the pinned toolchain and repository setup (`bundle:install` plus `hooks:install`). |

A normal Unix install uses symlinks. On Windows, automatic mode uses directory junctions
for directories and file symlinks for files. When the host cannot create those links, it
falls back to copies. Strict link mode does not use that fallback. The installer records
per-entry ownership in the platform state directory (`XDG_STATE_HOME` on Unix,
`LOCALAPPDATA` on Windows). Lifecycle operations use that record to distinguish bundle
entries from user files. Write-capable lifecycle commands are serialized per state file.
Linux lifecycle mutation requires glibc 2.28+ and a filesystem exposing `statx` birth time.
Unsupported identity or no-replace primitives fail closed rather than weakening ownership
authority.

```bash
mise run bundle:install
mise run bundle:status
mise run check
```

The native Windows path runs the ordinary current-host task; it does not invoke WSL. When
`bundle:install:all-hosts` or `bundle:status:all-hosts` is run from WSL, it runs the WSL
current-host lifecycle first and then invokes the native Windows mise task. The two host
summaries remain separate, and the native task's arguments and exit code are preserved.

### Optional statusline and anywhere opencodex commands

The Claude/Codex bundle installer and the plugin do not own shell aliases, PATH, or global
Claude settings. Installing into a PATH directory is a persistent user-environment mutation.
It requires explicit operation-specific approval for that exact directory; a general install
approval never covers it. A separate Unix operator-tools plane can then install three executable
copies into `${XDG_BIN_HOME:-$HOME/.local/bin}`, and only when that physical user-owned
directory is already on `PATH`:

```bash
mise run operator-tools:install
ocx-launch                 # supervised ordinary split-plane launch
ocx-ultracode              # supervised launch with session Ultracode; no permission bypass
mise run operator-tools:status
```

No shell startup file or PATH value is edited. Both launch commands delegate to
`scripts/opencodex-claude.sh`, so ADR-0005 credential refusal, environment scrubbing, isolated
Claude config, and identity-checked supervision remain mandatory. `ocx-ultracode` refuses
competing `--settings` and permission-bypass flags instead of silently copying a dangerous
alias. Launch/restart still carries opencodex's documented shared `~/.codex` configuration side
effect.

The packaged statusline is offline, uses approximate built-in model-family prices only for its
advisory subagent breakdown, and is not activated by installation. Changing global Claude
settings requires explicit operation-specific approval for that exact settings file:

```bash
mise run claude:statusline:activate -- --dry-run
mise run claude:statusline:activate
mise run claude:statusline:status
mise run claude:statusline:deactivate
```

Activation verifies the exact owned executable and mutates only `statusLine.type` and
`statusLine.command`; unrelated settings are preserved. A foreign statusline or later operator
edit is preserved and reported as a conflict. This initial surface supports Linux, WSL, and
macOS; native Windows activation fails with a named unsupported verdict.

### Safe migration and lifecycle rules

Use the installer to inspect v1 ownership before explicitly migrating it:

```bash
mise run bundle:status
mise run bundle:install -- --migrate-state --dry-run
mise run bundle:install -- --migrate-state
mise run bundle:status
mise run check
```

`status` and ordinary lifecycle commands never rewrite v1 state and block mutation while a
known v1 document is outstanding. `--migrate-state --dry-run` validates every record from the
operator state path and the configured home's distinct legacy path without changing files or
state. The write-enabled command converts all exact, structurally valid records—including
mixed-agent and historical-home records—into one central v2 document. Migration is state-only:
it does not install, refresh, or otherwise reconcile current bundle entries. A distinct legacy
source is retired only after the central v2 write is durable and the source is rechecked. Retry
is idempotent if retirement was interrupted. Migration fails closed on changed object types,
conflicting records, changed sources, or unsafe roots.

Linux and macOS require their supported filesystem durability barriers; failures stop the
operation. macOS uses `F_FULLFSYNC` for file content and directory fsync for namespace changes.
Native Windows uses handle-bound, no-replace renames and supports process-crash recovery, but
does not claim sudden-power-loss durability for namespace transitions. Concurrent external
mutation of managed paths during a write command is unsupported; detected identity or content
changes are preserved and reported as conflicts.

Collection directories are never replaced. An exact legacy bundle link or byte-identical
copy may be adopted into ownership. Foreign entries, retargeted links, and modified copies
are preserved and reported as conflicts. Owned copies are refreshed only while they remain
unchanged from the last recorded bundle content; user modifications are never overwritten.
Uninstall removes only owned entries and leaves conflicts and foreign files in place.

For Claude Code, choose exactly one distribution plane per machine. Use either the direct
bundle install or the Claude marketplace install (`claude plugin marketplace add` followed
by `claude plugin install`). Marketplace overlap blocks only the Claude plane; other host
planes can still be managed. Do not register both, because the same skill would appear once
as a bare skill and again under the plugin namespace.

### Install as a Claude Code plugin

This is the alternative Claude plane described above, and it needs no clone, no mise, and no
toolchain trust step, because a marketplace source may be a Git URL. Two commands, from any
directory:

```bash
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git
claude plugin install agentic-sdlc@agentic-sdlc
```

The first command writes an `extraKnownMarketplaces` entry to user settings and clones the
catalog; the second copies `plugin/` into the versioned plugin cache and writes
`enabledPlugins`. Claude Code then serves the skills under their own names and the seven SDLC
roles under the plugin namespace (`agentic-sdlc:sdlc-planner` and its six peers). The bundled
output style appears as `agentic-sdlc:BLUF`, taking its name from the file's frontmatter rather
than its filename. Confirm what a given install actually contributes with
`claude plugin details agentic-sdlc@agentic-sdlc`, which prints the component inventory and a
per-session token estimate.

Add `--sparse .claude-plugin plugin skills agents commands output-styles` to the
`marketplace add` command to limit the catalog clone to the directories the plugin needs. The
installed plugin is identical either way; only the cached catalog is smaller.

This plane installs context and roles. It does not install the repository gate, the pinned
toolchain, the Seeds launcher, or anything on `PATH`, so it is not a substitute for the bundle
install when you intend to develop this repository or run its waves.

To remove both records:

```bash
claude plugin uninstall agentic-sdlc@agentic-sdlc
claude plugin marketplace remove agentic-sdlc
```

Installing a plugin is an install-time decision about your own machine, not authorization for
any outward effect the plugin's guidance later describes.

### Hooks

`hooks:install` installs the lefthook subsets from this repository: pre-commit runs
`mise run validate`; pre-push runs `mise run test`, `mise run self-test`, and
`mise run secrets`. These hooks are best-effort convenience only; `mise run check` remains the
complete local gate and the command CI mirrors.

### Compatibility wrapper and optional adapters

`scripts/install-skill-bundle.sh` remains a compatibility wrapper for existing automation.
It requires mise and invokes the pinned uv/Python installer. It forwards supported arguments
and retains positional `status`, `uninstall`, and `self-test` plus legacy `--copy` behavior.
cmux and tmux are never prerequisites.

The native host path is available only after capability probes and trust checks succeed:

```text
Use $agentic-sdlc to frame this task and run a bounded,
Seeds-backed worktree wave using the host's native agents.
```

A capability probe or local status is evidence about that run only; it does not grant
authority for an outward effect. Push, tag, PR, merge, deployment, ruleset, credential, and
external evidence-store operations each require explicit operation-specific authorization.

Use the native Frame/Wave/Mission flow. cmux remains an independent view/event layer only
when it is already active or explicitly requested; tmux is never required. Adapter capability
and model resolution must be read back; configuration alone is not proof.

## Run (native baseline)

Native host agents, provider-native roles, subagents, workflows, teams, and background tasks
are the supported execution mechanisms after capability and trust verification. cmux and tmux
are optional integrations, not setup steps or hidden dependencies.
