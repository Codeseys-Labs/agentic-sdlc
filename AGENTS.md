# Agentic SDLC Orchestrator — agent instructions

This repo is a multi-skill, multi-host agent bundle (an "open plugin"): one `skills/`
tree in the cross-host Agent Skills format, thin per-host manifests, and a symlink
installer. Codex, Gemini CLI, OpenCode, and other AGENTS.md-aware hosts: read this file
as the router.

## What this bundle provides

**Third-party skill libraries: never vendored, installable on request.** Keep the two halves
distinct, because they are what separate a licence obligation from a convenience.

**Never vendored.** No foreign library's bytes are copied into this repository's tree. Copying
them is what triggers the `NOTICE` donor obligation under ADR-0001, drags another licence into
this distribution, and puts entries this bundle did not author onto its own selection surface.
Foreign *ideas* enter by exactly one path: an adapted `references/*.md` with a root `NOTICE`
donor entry landed in the same change, re-expressed rather than copied.

**Installable on request.** `libraries:list`, `libraries:status`, and `libraries:install` run a
named library's own front door — `mattpocock/skills`, ECC (`affaan-m/ECC`), and hyperresearch.
Invoking a third party's installer copies nothing here: the bytes land in the operator's home,
written by the library's own code, under its own name and licence. No donor obligation attaches,
because this bundle is not a donee. The tasks are opt-in, collision-checked, and reached by no
gate leaf and no `contributor:setup`, deprecated `setup`, or `bundle:install` path, so installing
is a deliberate choice and never a side effect. The installer's ownership model keeps the two
coexisting: an entry this bundle does not own is classified `foreign` and preserved rather than
replaced. See
`docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md`,
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md` (the no-vendoring
rule 0009 refines), `skills/external-skill-libraries/`, and
`skills/agentic-sdlc/references/skill-authoring.md`.

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
  run the delivery loop. `/sdlc-rightsize` is the user-facing Claude Code command that loads
  the `model-tier-rightsizing` skill and writes a regenerable model-task map for certified
  dispatch; `model-tier-rightsizing` itself remains a skill, not a slash command. Other hosts
  invoke the flagship skill with the same intents. Global installation and per-repository
  activation are separate lifecycle planes.

## Working on THIS repo

- Run `mise run check` before any commit — it is the authoritative repository gate. It uses
  mise-managed uv/Python to validate name==dirname, the Codex 1024-char description cap,
  broken references, TOML/JSON parses, shell syntax, manifests, and secret-shaped strings in
  tracked text, then runs the installer tests, the lifecycle self-test, and the pinned
  working-tree secrets scan (`mise run secrets` = `betterleaks dir .` with `--config` pinned at
  the tracked extend-only `.config/betterleaks.toml`, so a drop-in config or `GITLEAKS_CONFIG*`
  variable cannot silently replace the ruleset). Full git-history
  scanning stays a separate, explicitly consented pre-publish step. A passing gate
  is evidence only; it does not authorize an outward effect.
- Run `./scripts/install-skill-bundle.sh self-test` after installer changes.
- Version bumps: `./scripts/bump-version.sh <version>` updates every manifest in one
  shot; `--check` exits 1 on drift, and the validator raises a disagreeing manifest as an error,
  so the gate and CI both fail closed on it. Never hand-edit a single manifest's version.
- Adding a skill = adding `skills/<name>/SKILL.md` (name must equal the directory
  name; description ≤1024 chars). The installer/validator/planes pick it up
  automatically.
- Keep skills host-agnostic: no user-specific paths, no provider credentials, no
  internal hostnames. Host-specific detail belongs in per-host manifests or the
  installer.

## Linux Mermaid renderer boundary

Diagram rendering is a Linux x64-only advisory surface, never a bootstrap prerequisite and
never a gate leaf. `mise run check` must stay green on a host that has never provisioned it:
`mermaid:provision` and `mermaid:linux-test` are deliberately absent from `check`, from
`lefthook.yml`, and from CI, and the bounded `tests_linux` suite skips with named reasons when
the runtime receipt, `bwrap`, or the pinned browser is unavailable. Provisioning downloads a
pinned browser, so it stays an explicit operator step.

Two limits in `policy/mermaid-renderer-linux-v1.json` are **resource-availability ceilings
calibrated to the pinned chrome-headless-shell 150.0.7871.24, not output-size controls**, and
ADR-0006 records their measurement: `max_rss_bytes` is 1,610,612,736 (1.5 GiB) against a
measured worst-case summed process-tree RSS near 690 MiB, and `max_output_file_bytes` is
67,108,864 (64 MiB) applied as `RLIMIT_FSIZE`, which the kernel charges against every file the
sandboxed browser writes — profile, GPU and Dawn caches, fontconfig caches, logs — about 2.5 MB
of bookkeeping per render. Do not retighten `max_output_file_bytes` toward an SVG-shaped
number; at 512 KiB the browser dies mid-session as an opaque puppeteer `Connection closed`.
SVG size is bounded independently by `max_raw_bytes` and `max_final_bytes`, enforced at four
points across the wrapper and the sanitizer. A browser pin bump re-opens both calibrations:
re-measure rather than assume. Rendering itself stays advisory and is never a gate leaf, so
these ceilings govern whether a render can run, never whether any verdict holds.

Callers may invoke only `scripts/render_mermaid_linux.py <definition> <final-svg>`. Direct
`mmdc`, raw SVG, caller-supplied Mermaid/Puppeteer configs, profiles, cache paths, and launch
flags are all forbidden: the wrapper owner-generates every config, requires `/usr/bin/bwrap`
with network denial, and fails closed when provenance or sandbox admission fails. macOS and
Windows rendering are uncertified — the wrapper returns its explicit unsupported-platform exit
code rather than claiming renderer support. The validator pins the supply chain by digest
(`package-lock.json` and `policy/mermaid-renderer-linux-v1.json` bytes, plus the browser
hashes), so loosening the sanitizer allowlist or the sandbox limits fails the gate.

## Installing this bundle

mise 2026.4.27+ is the only bootstrap prerequisite. It is the managed-tool bootstrap, not the
sole readiness prerequisite. It pins uv, consumes the checked-in cross-platform `mise.lock`, and
uv supplies Python 3.12.11 for all authoritative Python entrypoints. Git, a verified Seeds
distribution, supported trust behavior, repository gates, and any selected adapter remain
runtime-readiness capabilities, not additional bootstrap prerequisites. Missing, unpinned,
untrusted, or ambiguous capability means the checkout is not Git-ready. Trust is scoped to each
absolute config path: every linked worktree must review and trust its own `mise.toml`, and
`MISE_PARANOID=1` fails closed until that explicit trust step. Persistent `mise trust`,
Codex/global config, shell-alias, and credential mutations each require explicit
operation-specific user approval. Process-scoped `mise --no-config` test execution is allowed
without persisting trust. Never make permanent Windows environment/trust/config changes.

From a clean clone the order is: clone, review `mise.toml` and `mise.lock`, obtain explicit
operation-specific approval and run `mise trust ./mise.toml` for that exact reviewed config path,
`mise --locked install`, then choose a plane with `mise run bundle:install -- --agent claude` or
`mise run bundle:install -- --agent codex` (or install both). Claude's configured root is the
selected `--claude-home` plus `.claude`; Codex's is `--codex-home` or `CODEX_HOME`. Status,
`--dry-run`, and `--help` are read-only. A Claude marketplace overlap is reported once per Claude
plane and blocks only direct Claude installation, so a selected Codex plane still proceeds.
Without the trust step every later `mise` command in the repository exits with `config files are not trusted`. Resolving the lock downloads
roughly 1.3 GB across the 13 pinned tools in about 30 seconds; mise ships `auto_install` enabled,
so skipping the explicit install step does not avoid the cost — the first `mise run <task>`
installs all 13 without prompting. `mise run check` last measured 654 tests in 814s with
`OK (skipped=13)` on Linux, its `validate` and `secrets` leaves each under 2s, so budget about 15
minutes and expect longer on a loaded host. Both figures go stale by design — the count grows
with the suite and the clock varies by host — and the gate's verdict is the evidence.

`scripts/bootstrap-agentic-sdlc.sh` replaces the clone step only, for an operator who would rather
not choose or track a directory. It fetches into
`${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc` (override `AGENTIC_SDLC_HOME`, discover with
`--print-path`), accepts an explicit `--remote <git-url>` and `--ref`, records
remote/ref/resolved-commit in a receipt under `XDG_STATE_HOME` outside the clone, then stops with a
verify/first-use handoff: receipt and checkout commit, the two reviewed files, trust/toolchain,
explicit plane selection, and post-install status. It requires mise and git, installs neither, and
so adds no bootstrap prerequisite. It never trusts a config, resolves a toolchain, or installs
bundle entries; `--dry-run`, `--print-path`, and `--help` create nothing; an unexpected remote,
dirty tree, ref mismatch, or non-fast-forward each refuse by name at exit 3 rather than clobbering.
The clone is managed, not eliminated: every task command and installed symlink resolves against a
tree on disk, so do not describe this as a clone-free bundle install. HTTPS authenticates the
transport, not the contents, and no signature over the fetched commit is verified. See `docs/adr/0011` and
`docs/research/2026-08-07-clone-free-install.md`, which record that mise's experimental `git::`
task includes cannot serve this repository: they clone into a cache anyway, parse targets against
the task-file schema, carry no `[tools]`, and run tasks in the caller's directory.

To acquire Seeds from an exact clean Git distribution root, run the installed flagship
`tools/seeds-launcher.mjs bootstrap --distribution <distribution-root>` under Node 22.22.3.
Bootstrap and inspect both reject any other executing Node. Bootstrap rejects nested, staged,
dirty, untracked, or ignored distribution content, then explicitly invokes reviewed
`mise --locked install` with isolated HOME, mise config/data/cache, hooks, npmrc files, and fixed
official registry/npm backend. Ambient npm/mise config cannot select acquisition. It resolves only
config-free exact roots, validates Node 22.22.3, Bun 1.3.10, and the
`npm:@os-eco/seeds-cli@0.5.15` package/bin/layout; the released package's string `engines.bun` is
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

Record is the conductor's queue write and the only mode that mutates a queue. An absent queue has
one exact form: `--queue-writer conductor --expect-queue absent init`. It inherits receipt, hash,
exact-runtime, and environment admission; rejects every existing/partial/file/symlink/redirected
`.seeds`; snapshots `.gitattributes`; refuses non-UTF-8 or exact-line/substr-match-ambiguous
prestates before mutation; invokes exact pinned `init --json`; and admits only the closed five-file
`.seeds` surface plus the precise missing merge-union append. A failed child after either
surface moves is an unknown effect; no movement is a clean refusal. Existing queues require
`--expect-queue <sha256>` and admit only create or update, never removal, pruning, closing, claiming,
syncing, or another standalone mutation. After the write the launcher admits only the prestate plus
the requested delta. A moved queue, unrequested field, rewritten/reordered neighbour, queue-file
surface change, or plan transition beyond the owner's status and timestamp is refused. A prestate
the writer would silently rewrite is refused before it starts. The queue's own lock stays the
writer's. A verified record is evidence, never authorization for push, publication, PR mutation,
merge, deployment, or any other outward effect.

Before spawn, the conductor supplies a certified `RuntimeAssignment` with requested
model/effort/context values; `resolution_state` must be `resolved`. Exact model/effort request
injection is mandatory and immutable. The requested model tier and the resolved provider/model
are separate facts. Requested model selection is recorded as resolved, inherited, or unresolved,
and it is never proof. `resolved_provider` and `resolved_model_id` require verified model
identity. An independently observed provider/model source may be unavailable only for an
unambiguous exact-ID mapping backed by immutable request/model evidence, and resolved is recorded
only after adapter readback. Effective effort/context readback may be honestly unavailable, and
requested values never become readback. Requested, inherited, unresolved, or incomplete
assignments stop before dispatch and therefore stop before spawn. The selected host or launcher
must inject the exact requested model and effort. If it cannot inject both, return one
SeedProposal, not a dispatch. Prompt prose does not enforce a Codex model or effort.
Provider-neutral roles contain no static model or effort pin and never recommend host-default
model selection as policy.

- `bundle:install`, `bundle:status`, `bundle:uninstall`
- `bundle:install:claude`, `bundle:install:codex`
- `bundle:install:all-hosts`, `bundle:status:all-hosts`
- `operator-tools:install`, `operator-tools:status`, `operator-tools:retire-aliases`,
  `operator-tools:uninstall`, `operator-tools:self-test`
- `claude:statusline:status`, `claude:statusline:activate`, `claude:statusline:deactivate`
- `ocx:launch`, `ocx:ultracode`, `ocx:status`, `ocx:restart`, `ocx:configure`
  Muse Spark has no tasks of its own: it is one provider registered in the gateway, whose models
  appear in the single flat live catalog as namespaced ids, so
  `ocx:launch -- --model muse/muse-spark-1.2` selects one exactly as a gpt id is selected. It is a
  row in a provider list, never a plane (ADR-0007 amendment, ADR-0010)
- `mermaid:provision`, `mermaid:linux-test` — explicit Linux x64 renderer steps, never gate leaves
- `libraries:list`, `libraries:status`, `libraries:install`, `libraries:migrate` — external skill
  libraries through their own front doors, opt-in and dry-run without `--yes`; `migrate` retires
  another channel's copies of the same upstream through that channel's own removal path before
  installing. Never gate leaves, and reached by no `contributor:setup`, deprecated `setup`, or
  `bundle:install` path
- `research-os:install` (`--target` required, no implicit current-directory scaffold), `validate`,
  `test`, `self-test`, `secrets`, `check`, `hooks:install`, `contributor:setup`, `setup` (the
  one-release deprecated forwarder)

That list is every task `mise tasks` reports; re-run `mise tasks` and re-diff it against this
list whenever a task is added or renamed, because a stale list here reads as an authoritative
inventory. `mise run bundle:status` always ends with one
terminal line — either `no owned entries for this host` or an `N ok, M conflict, K absent`
summary — so a silent exit 0 is a defect, not a clean host.

Operator tools are an explicit Unix lifecycle plane, not part of plugin or ordinary bundle
installation. They install only `ccodex` plus its packaged statusline support command into an
existing user-owned PATH directory and never edit shell startup files or PATH. The statusline
remains inactive until the operation-specific `claude:statusline:activate` command; it owns only
`statusLine.type` and `statusLine.command` and preserves conflicts. Historical `ocx-launch` and
`ocx-ultracode` names remain recognized in v1/v2 ownership state and pending transitions, but
fresh installs neither require nor recreate them. `operator-tools:retire-aliases` removes only
unchanged removable owned copies through the crash-consistent unlink lifecycle; modified,
foreign, and adopted copies are preserved and reported. `ccodex ultracode` enables session
Ultracode without bypassing permissions and refuses competing settings or bypass flags. Native
Windows statusline/operator-tool activation is not certified and fails closed.
`operator-tools:status` reports a never-installed desired command as `absent` and reserves
`unmanaged` for a desired file that exists but is not owned; historical aliases are never
reported as required or absent.

Both launchers' Claude config dir is selectively separate, not isolated in every respect
(ADR-0010). Inert per-session data — history, project transcripts, todos, shell snapshots, file
history — is shared with `~/.claude` by symlink. Mutating global Claude settings still requires
explicit operation-specific approval and no launcher does it: the plane-local `settings.json` a
launcher constructs lives in its own state directory, and the global file is read, never written,
copied, or linked. Only the global `statusLine` stanza is inherited, because that `env` block can
carry a live credential and copying it would also re-point the child away from
its verified route. Credentials never cross: the constructed document is asserted credential-free
before it is written, credential and plane-owned stores stay private, inheritance runs only after
every credential assertion, and it is fail-soft and never destructive. Do not cite config-dir
isolation as evidence that no session data is shared. An entry whose plane copy already holds its
own data is NOT inherited, and that is permanent until an operator migrates it: a launch never
moves plane data, `status` reports how many entries are actually shared, and `ccodex session
adopt --migrate` moves the blocking copy to a timestamped in-plane backup before linking. Never
run that migration on an operator's behalf without explicit operation-specific approval, and do
not read a skipped entry as inheritance working. Verb-level `--help` prints the launcher's own
help and prepares nothing; `--` forwards the remaining arguments verbatim to the wrapped tool.

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
lefthook's validate pre-commit and test/self-test/secrets pre-push subsets; hooks are best-effort
convenience, not release authority. The Bash installer is a mise-backed compatibility wrapper retaining
positional `status`, `uninstall`, `self-test`, and legacy `--copy`.
For Claude, use either direct install or the marketplace, never both; marketplace
overlap blocks only Claude. No local status, gate, reviewer label, or conductor choice grants
authority for push, publication, PR mutation, merge, deployment, credential, or other outward
effect; each requires explicit operation-specific authorization.
