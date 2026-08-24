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

**Installable on request, from a closed catalog.** `libraries:list`, `libraries:status`, and
`libraries:install` support exactly `mattpocock/skills`, ECC (`affaan-m/ECC`), and hyperresearch
through each library's own front door. Unlisted libraries—including gstack—are operator-owned
foreign state until separately verified and onboarded; these tasks do not adopt, inspect for
ownership, migrate, or remove them. Invoking a supported third party's installer copies nothing
here: the bytes land in the operator's home,
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
  roadmap lanes. Qualification is a DURABLE verdict, not a transient computation: its
  `scripts/route_qualification.py` issues immutable per-cell generations from recorded attempt
  evidence through the evaluator's own shared floor predicate (never a second scoring copy),
  and `admit` is the free pure query a conductor runs before writing a resolved assignment —
  it transforms no store, refuses through closed named reasons (quarantined cell, missing or
  ambiguous generation, unqualified, expired, floor-policy drift, and the identity family
  including default-provider fallthrough), and names a required quarantine rather than
  applying one. A verdict's freshness is checked arithmetic over caller-supplied instants, not
  observed elapsed time; `policy/route-qualification-v1.json` records that limit.
- `skills/dispatching-exact-ocx-models/` — exact-route handoff after rightsizing. It distinguishes
  generated `ocx-*` Agent definitions from Workflow call-site injection, checks route/tool
  compatibility, and refuses results without correlated provider/model receipt evidence.
- `skills/reviewing-overengineering/` — independent complexity/deletion audit for an immutable
  plan or diff. It applies deletion pressure plus a safety-preservation rebuttal and requires any
  remediated candidate to be reviewed again. Ponytail is optional, never a dependency.
- `skills/sdlc-threat-model/` — STRIDE-shaped threat enumeration over one scoped subject (one
  diff, one subsystem, or one trust boundary) bound as an immutable snapshot. It returns
  classified, evidence-graded findings as seed-shaped recommendations for conductor capture;
  risk disposition stays human-only (ADR-0026). Advisory and never a gate leaf: it attacks,
  never fixes, never scans beyond the bound subject, consumes no CVE feeds, and files no seeds
  itself.
- `agents/` — eight global SDLC role agents (cartographer, planner, implementer, reviewer, researcher,
  critic, integrator, and documentarian — the read-only documentation worker that proposes
  evidence-linked doc refreshes for conductor capture) in Claude `.md` and Codex `.toml` forms,
  plus the repo-scoped research roster under `agents/codex/research/`.
- `commands/` — `/sdlc-init` activates repository-specific DevEx, tracked baseline,
  gates, trust, and shared guidance; `/sdlc-frame`, `/sdlc-wave`, and `/sdlc-mission`
  run the delivery loop. `/sdlc-rightsize` is the user-facing Claude Code command that loads
  the `model-tier-rightsizing` skill and writes a regenerable model-task map for certified
  dispatch; `model-tier-rightsizing` itself remains a skill, not a slash command. Other hosts
  invoke the flagship skill with the same intents. Global installation and per-repository
  activation are separate lifecycle planes.
- `workflows/` — Claude Code Dynamic Workflow documents, installed as ordinary owned bytes into
  `<claude-home>/.claude/workflows/` by the same lifecycle that owns skills, agents, and commands:
  same ownership records, staging, refresh, migration, and modified/foreign preservation. Codex
  owns no record of them. Installing, refreshing, adopting, or removing one never runs it, never
  enables it, and never reloads a host — enabling or executing the real overlay is a separately
  authorized user-configuration effect. The shipped `sdlc-wave-scout` is a read-only two-stage
  scout that proposes a wave graph and refuses before dispatch until the conductor supplies a
  resolved `RuntimeAssignment` per stage, because the distributed bytes carry no model or effort
  pin. Adding one = adding `workflows/<name>.js` whose first line is `// workflow: <name>` and
  whose first STATEMENT is the host-required pure-literal `export const meta = {...}` declaring
  the same name plus a description (no variables, calls, spreads, or interpolation; only comments
  and blank lines before it); the validator checks both pairings, the lowercase-slug name, the
  meta literal's closed shape, module-free parseability, the absence of a static model/effort
  pin, and the absence of user-specific paths. The home-plane collection is NOT a name-discovery
  surface: the host's Workflow name registry reads only a project's own `.claude/workflows/`,
  once at session start (live measurement 2026-08-24, recorded on agentic-sdlc-4d2b), so the
  installed bytes stay undiscovered until the separately authorized per-repo
  `claude:workflows:activate` (`scripts/manage_claude_workflows.py`) copies one owned installed
  workflow into a target repository's `.claude/workflows/<name>.js` under a receipt — a copy,
  never a symlink, so the enabled entry is self-contained repo bytes carrying no user-specific
  path. Activate refuses an absent, unowned, or digest-drifted installed source and an occupied
  foreign destination; deactivate removes only a copy still byte-identical to its receipt;
  foreign and modified files are preserved and reported. Enablement takes effect at the target's
  next session, and the manager's output says so.
- `hooks/` — agent-CLI hook scripts (Claude Code first), installed as ordinary owned bytes into
  `<claude-home>/.claude/hooks/` by the same lifecycle and under the same preservation rules as
  workflows; Codex owns no record of them. That directory is not an auto-discovery surface —
  hooks run only from settings configuration — so installing, refreshing, adopting, or removing
  one never runs it and never enables it, and no `bundle:*` path ever touches `settings.json`.
  Wiring one in is the separately authorized, operation-specific `claude:hooks:activate`
  (`scripts/manage_claude_hooks.py`), whose ownership unit is ONE `hooks.<Event>` array element
  recorded in a receipt: activate appends exactly that element and refuses an absent, unowned, or
  digest-drifted hook file; deactivate removes only a deep-equal element; foreign and modified
  elements are preserved and reported. There is deliberately no plugin-channel `hooks/hooks.json`,
  because plugin hooks auto-enable when the plugin is enabled. The shipped
  `session-start-routing-primer` is repo-gated: in a repository with a regular non-symlink
  `.seeds/issues.jsonl` AND the `/sdlc-init` AGENTS.md marker it emits a fixed reviewed
  situation→skill routing card (≤2 KiB, never interpolating repository content); anywhere else it
  exits 0 with zero bytes of stdout, injecting nothing. Adding one = adding `hooks/<name>.sh`
  whose line 2 is `# hook: <name>` plus `# hook-event:`/`# hook-matcher:` headers from the
  validator's closed vocabulary, POSIX-sh-parseable, within the 4096-byte cap.

## Working on THIS repo

- Run `mise run check` before any commit — it is the authoritative repository gate. It uses
  mise-managed uv/Python to validate name==dirname, the Codex 1024-char description cap,
  broken references, TOML/JSON parses, shell syntax, manifests, and secret-shaped strings in
  tracked text, then runs the installer tests, the lifecycle self-test, and the pinned
  Git-visible secrets scan. `mise run secrets` selects tracked files plus nonignored untracked
  files, rejects symlinks and any selected path beneath a symlinked parent rather than following
  them outside the repository, then calls betterleaks with the tracked extend-only
  `.config/betterleaks.toml` on every batch; ignored runtime state is excluded but a force-tracked
  ignored path remains covered, and no drop-in config or `GITLEAKS_CONFIG*` variable can replace
  the ruleset. Full git-history
  scanning stays a separate, explicitly consented pre-publish step. A passing gate
  is evidence only; it does not authorize an outward effect.
- Run `./scripts/install-skill-bundle.sh self-test` after installer changes.
- Version bumps: `./scripts/bump-version.sh <version>` updates every manifest declared in
  `.version-bump.json` in one shot; `--check` exits 1 on drift, and the validator raises a
  disagreeing manifest as an error, so the gate and CI both fail closed on it. Never hand-edit a
  single manifest's version. The bump is NOT the whole transition, and the remainder is deliberate:
  `policy/release-contract.v1.json`, `policy/release-candidate.v1.json`'s `product_version`, and
  `scripts/ccodex_sdlc.py`'s `EXPECTED_CHECKOUT["version"]` are a REVIEWED edit rather than bump
  targets, because moving the contract silently would let a routine bump ship a mislabeled archive.
  What the gate owes you is the complete list, and it now names each of the three by file with its
  own error, so a forgotten one fails closed at `mise run validate` instead of surfacing later as
  dozens of reader assertions quoting the version being REPLACED (agentic-sdlc-3174). Every other
  `0.7.x` string in the tree — AGENTS.md's and README.md's container-proof sentences, ADR-0011's
  first-release note, the validator's transition comment — is dated evidence about one specific
  release and must NOT move with a bump.
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

The supported distribution for customization, contribution, gates, and release building remains
this managed checkout. A quick install exists as prerelease evidence, EXACT-VERSION ONLY
(container-proven 2026-08-24 against v0.7.4): a mise config carrying
`[tools."github:Codeseys-Labs/agentic-sdlc"]` with `version = "0.7.4"` and `prerelease = true`
resolves the published prerelease, and the installed tree's `bin/ccodex` is the single exposed
command — `ccodex version`/`--help` answer tool-free, the first tool-needing verb refuses at
exit 3 naming the `mise trust <tree>/mise.toml` remedy, and after that explicit reviewed step
`ccodex bundle install --agent claude` activates the plugin (proven: 27 entries, five commands
digest-matched, receipted uninstall reading clean). The UNVERSIONED
`mise use -g github:Codeseys-Labs/agentic-sdlc` does not resolve a prerelease (prerelease listing
exclusion plus mise's built-in `minimum_release_age` filter while a release is young) and stays
unclaimed. The release tree carries no `.git`, so gates, Seeds bootstrap, and `ccodex sdlc`
copy-activation stay on the managed checkout and the operator-tools plane. Payload, activation
boundary, and limits are recorded in `docs/plans/2026-08-14T163833Z-Install-UX.md`; ADR-0011 as
amended 2026-08-24 carries the executed evidence.

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
roughly 1.3 GB across the 12 pinned tools in about 30 seconds; mise ships `auto_install` enabled,
so skipping the explicit install step does not avoid the cost — the first `mise run <task>`
installs all 12 without prompting. `mise run check` last measured 2186 tests in 400s with
`OK (skipped=13)` on Linux, its `validate` and `secrets` leaves each under 2s, so budget about 10
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
bundle entries; `--dry-run`, `--print-path`, and `--help` create nothing; a credential-bearing
remote, an unexpected remote, dirty tree, ref mismatch, or non-fast-forward each refuse by name at
exit 3 rather than clobbering. Userinfo is a credential channel that every consumer keeps, so a
`--remote` carrying a secret there is refused before the value reaches output, the receipt, Git's
argv, or the clone's config, and the refusal names the option rather than echoing any part of the
URL; an existing managed clone's origin must be READ to detect one, so that value is inspected but
never echoed — the refusal lands before the line that would have printed the remote — while
`git@host:org/repo.git` and `ssh://git@host/org/repo.git` remain ordinary SSH remotes.
The clone is managed, not eliminated: every task command and installed symlink resolves against a
tree on disk, so do not describe this as a clone-free bundle install. HTTPS authenticates the
transport, not the contents, and no signature over the fetched commit is verified. See `docs/adr/0011` and
`docs/research/2026-08-07-clone-free-install.md`, which record that mise's experimental `git::`
task includes cannot serve this repository: they clone into a cache anyway, parse targets against
the task-file schema, carry no `[tools]`, and run tasks in the caller's directory.

To acquire Seeds from an exact clean Git distribution root, run the installed flagship
`tools/seeds-launcher.mjs bootstrap --distribution <distribution-root>` under Node 22.23.2.
Bootstrap and inspect both reject any other executing Node. Bootstrap rejects nested, staged,
dirty, untracked, or ignored distribution content, then explicitly invokes reviewed
`mise --locked install` with isolated HOME, mise config/data/cache, hooks, npmrc files, and fixed
official registry/npm backend. Ambient npm/mise config cannot select acquisition. It resolves only
config-free exact roots, validates Node 22.23.2, Bun 1.4.0, and the
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
- `claude:hooks:status`, `claude:hooks:activate`, `claude:hooks:deactivate` — inspect or
  explicitly wire installed agent hooks into the operator's Claude settings, one hook and one
  owned array element at a time (`-- --hook <name>`, never "all"); never gate leaves, unreachable
  from `bundle:install`, and each activation is its own operation-specific settings mutation
- `claude:workflows:status`, `claude:workflows:activate`, `claude:workflows:deactivate` —
  inspect or explicitly enable installed workflows for one target repository, one owned copied
  file at a time (`-- --workflow <name> --target <repo>`, never "all"); activation copies the
  owned installed bytes into the target's `.claude/workflows/`, refuses foreign or drifted
  state, and states that the change takes effect at the target's next session; never gate
  leaves, unreachable from `bundle:install`, and each activation is its own operation-specific
  per-repo mutation
- `ocx:launch`, `ocx:ultracode`, `ocx:status`, `ocx:restart`, `ocx:configure`
- `rightsize:evaluate` — explicit model-rightsizing discovery/plan/evaluate/render surface; never a
  gate leaf. `plan` makes no model calls. `evaluate` requires the plan's exact authorization digest
  after the operator reviews routes, target-data egress, attempts, provider/subscription capacity,
  budgets, outputs, and stop conditions. It emits advisory v2 map/evidence artifacts and never
  dispatches workflow roles or changes runtime receipt policy.
  `ocx:launch` runs Claude Code through the gateway using the operator's OWN `~/.claude` login, so
  ONE session serves both catalogs: a genuine `claude*`/`anthropic*` id that no alias or `modelMap`
  claims is forwarded verbatim to `api.anthropic.com` on that subscription, while every gateway id
  routes to its own provider on that provider's credential. Anthropic's gateway documentation
  describes this shape — base URL set, no gateway credential, `anthropic-beta` forwarded — as
  preserving the subscription's limits and billing. It also states that routing Claude Code to
  NON-Claude models through any gateway is unsupported, so the routed half is
  permitted-but-unsupported; no Anthropic credential is used for those turns. The isolated plane,
  the environment scrub, the subscription refusals, the `session` verbs, and the separately named
  `claude-subscription` route are all GONE (ADR-0014 supersedes ADR-0013 and amends ADR-0003).
  `launch` still refuses (exit 3) when the route would not actually be used: a provider-routing key
  (`CLAUDE_CODE_USE_BEDROCK`-class, exported or in a persistent settings `env`), an
  `apiKeyHelper`, an `sk-ant-api*` Console key, a cloud-provider-shaped model id (Bedrock or
  Vertex form) in `ANTHROPIC_DEFAULT_{SONNET,OPUS,HAIKU,FABLE}_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`,
  or `ANTHROPIC_MODEL`, or an explicit `--settings` value that is uncheckable
  or carries the same blocker — the provider switch bypasses the gateway entirely, the Console
  key takes the same native branch but bills API credits, and a cloud-provider id in a model slot
  re-points that model family to the gateway's default provider instead of Anthropic (a plain
  `claude-*` alias or a gateway id in those slots stays fine). Every selected settings value is inspected
  before gateway startup, then accepted arguments are forwarded unchanged. An `sk-ant-oat*` login
  is accepted; no credential value or selected settings path is printed. ACCEPTED IS NOT REQUIRED:
  no predicate anywhere looks for a login, because the wrapper reads no credential at all, so a
  MISSING or expired login is not in the exit-3 set and a no-login host is not treated as a route
  that would not be used. Measured 2026-08-23 in a fresh container with no Claude login and no
  provider credentials: every settings predicate passed, the gateway STARTED — a real effect —
  and `claude` was exec'd, so the first routed turn failed downstream at exit 1 with a provider
  `401` naming the gateway's DEFAULT provider rather than Anthropic. Do not read the exit-3 contract
  as covering an unauthenticated host: every exit-3 refusal here is a route, billing, or
  permission-control condition the wrapper can see WITHOUT reading a credential, and a login's
  absence is not one of them. A healthy launch is still
  not model-identity evidence.
  `launch` and `ultracode` ALSO refuse (exit 3) a `--model` whose `<provider>/` prefix the RUNNING
  gateway does not serve, checked against its own `GET /v1/models` after the health probe, because
  the router does not fail closed on it: it computes the prefix, finds no provider of that name,
  discards that result, and forwards the id verbatim to the DEFAULT provider as
  `routeKind: "default-provider"`, so the turn is billed to the wrong account while attribution
  records the wrong provider. A configured-but-unpublished prefix refuses separately and names the
  `ocx sync` + `ccodex restart` publish step. A BARE id is never refused — native `claude-*`
  passthrough needs no catalog row — nor is an exact catalog id or `policy/<id>`; an unreadable
  catalog refuses rather than passing as served. The check needs a live catalog, so unlike the
  settings refusals it necessarily runs after the gateway is ensured. `ccodex set-fast-model <id>`
  carries the same rule with a deliberately WEAKER contract: an unserved prefix refuses, but an
  unreadable catalog WARNS and still writes, because configuring that slot with the gateway down is
  legitimate. This is a caller-side mitigation on those surfaces, not a fix — only the router can
  make the misroute fail closed for every client. See
  `docs/research/2026-08-24-gateway-default-provider-misroute.md`.
  `ocx:configure` admits only reviewed non-Anthropic provider/account routes, and a mutation there
  writes the CONFIG FILE only: the wrapper prints `ocx sync` plus `ccodex restart` and
  runs neither, because until the provider is published a request naming it is classified
  `routeKind: "default-provider"` and billed against the DEFAULT provider instead of failing
  closed. THE RESTART IS THE PUBLISH STEP, and the notice names both because that is what the
  notice says rather than what the gateway needs: measured 2026-08-23 on a fresh host with NO Codex
  installed and `ocx sync` never run, the restart alone took the live catalog from 7 ids serving
  none of the new provider to 420 serving 413 of it, and a routed turn then billed that provider's
  own credential. So the order is `ccodex ensure`, `provider add`, `ccodex restart`, then
  `account add-key`, and add-key LAST is not cosmetic: it validates the provider against the
  RUNNING gateway rather than against the config file, so run before the restart it fails
  `unknown provider` for a provider `provider list` showed as configured one command earlier, and
  with the proxy down it fails `Proxy not reachable`. Both constraints are upstream behavior,
  reproduced against the raw pinned binary, and neither appears in the configure help.
  By opencodex 2.28.0 (absent in 2.11.1) the sync is not always a `~/.codex` config write — with the Codex
  integration off, or an external `model_provider` owning `config.toml`, it reports a
  `CodexSyncResult` status of `catalog-only`, leaving `config.toml`, the journal, and history untouched (the catalog and models-cache files under `~/.codex` may still refresh), and a `validateOnly`
  injection preflight fails a bad config before any partial rewrite. That narrows the blast radius,
  not the authorization: a sync that WOULD rewrite shared `~/.codex` still requires its own
  explicit approval, and which branch a host takes is not knowable without running it. A provider
  absent from the config file is admitted only by name against the registry roster the wrapper
  pins (2.28.0 adds `chutes`, `featherless`, `nous`, `novita`, `xiaomi-mimo`); an unlisted name is
  refused, never admitted by absence.
  The general config plane stays unadmitted with EXACTLY ONE narrow exception, and the closed list
  is `config set`/`config unset` of `providers.<name>.modelOpenRouterRouting` and nothing else.
  It exists because config is that field's only route: `openai-chat` composes OpenRouter's
  outbound `provider` payload from configuration alone (`src/adapters/openai-chat.ts:116-117`) and
  a caller-supplied `provider` in the request body is dropped by `CHAT_PASSTHROUGH_FIELDS`, while
  `provider add|edit` carries no routing flag and the management PATCH mask has no
  `openRouterRouting` entry. Verified live 2026-08-23 end-to-end, not merely transmitted: the same
  `openrouter/openai/gpt-oss-120b` turn served from Amazon Bedrock unpinned and from Cerebras once
  the pin was live, a control model on the same provider still answered from Alibaba, and the unset
  returned routing to the baseline. Admission is by shape, not by trust: exactly three dotted
  segments with a plain-identifier provider (no wildcard, no deeper path), that provider already
  stored under that EXACT case-sensitive key on the `openai-chat` adapter with the canonical
  `https://openrouter.ai/api/v1` baseUrl, an exact argument count so no unreviewed flag rides
  along, and a payload validated against upstream's own `openRouterRoutingConfigError` rules
  (exact-model keys; each value carrying at least one of `order`, `only`, `allowFallbacks`; 1-64
  unique nonblank trimmed slugs; boolean `allowFallbacks`) before it is forwarded. Every other
  config path — `providers.<name>.apiKey`, `baseUrl`, the sibling default `openRouterRouting`, any
  top-level key — is still refused as `unbounded-route`, and `config import`/`config export` plus
  `init`/`setup`/`gui` are untouched. The publish step for a pin is `ccodex restart` ALONE and the
  wrapper prints it without running it: `startServer` calls `loadConfig()` once
  (`src/server/index.ts:497`), so the running process serves its startup snapshot, and there is no
  `ocx sync` here because the value is read from the gateway's own provider config rather than
  republished into `~/.codex`. An unpublished pin does not misroute to the default provider — the
  provider is already live — it reaches OpenRouter unpinned, which is the state the pin exists to
  prevent. A refused configuration route now explains the CONFIG plane instead of reprinting the
  ADR-0014 launch-route text: it names the exact refused verb and lists the admitted alternatives,
  while the provider-boundary refusals keep the launch-route body, where it is on topic.
  Muse Spark has no tasks of its own: it is one provider registered in the gateway, whose models
  appear in the single flat live catalog as namespaced ids, so
  `ocx:launch -- --model muse/muse-spark-1.2` selects one exactly as a gpt id is selected. It is a
  row in a provider list, never a plane (ADR-0007 amendment, ADR-0010)
- `mermaid:provision`, `mermaid:linux-test` — explicit Linux x64 renderer steps, never gate leaves
- `usage:report` — advisory read-only usage projection over the local evidence stores
  (`~/.opencodex/usage.jsonl` — the only file read in that credential-adjacent directory —
  Claude transcripts, and `stats-cache.json`) per
  `docs/plans/2026-08-24-usage-accounting-design.md`: billing-axis × measurement-label lanes,
  subscription cost always unpriced (an undeclared billing kind fails toward not-pricing),
  default output dollar-free, refusals emitted in the output itself, and no cross-store total
  because the two stores overlap unprovably and count input tokens in incompatible units.
  Opt-in `--estimates <snapshot>` quotes the gateway's own figure verbatim for declared
  api-key lanes only, each labeled a list-rate estimate, not a bill. Never a gate leaf:
  absent from `check`, `lefthook.yml`, and CI, and a report authorizes nothing
- `release:build` — build the deterministic unpublished-candidate archive of the committed HEAD
  tree into `dist/` (`scripts/build_release.py`). `scripts/write_acquisition_receipt.py` is the
  sole producer of the acquisition receipt `ccodex sdlc install`/`update` admit; placement of a
  built archive under `$XDG_DATA_HOME/agentic-sdlc/acquisition/candidates` is documented in
  `docs/plans/2026-08-14T163833Z-Install-UX.md`. A built archive is evidence of what was archived,
  never a release or a publication
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
summary — so a silent exit 0 is a defect, not a clean host. Status inventories lifecycle-owned
records, not every unowned name in a configured collection. Use `bundle:install -- --agent
<claude|codex> --dry-run` to detect an occupied unowned destination without adopting, overwriting,
or deleting it.

Operator tools are an explicit Unix lifecycle plane, not part of plugin or ordinary bundle
installation. They install only `ccodex` plus its packaged statusline support command into an
existing user-owned PATH directory and never edit shell startup files or PATH. The statusline
remains inactive until the operation-specific `claude:statusline:activate` command; it owns only
`statusLine.type` and `statusLine.command` and preserves conflicts. Historical `ocx-launch` and
`ocx-ultracode` names remain recognized in v1/v2 ownership state and pending transitions, but
fresh installs neither require nor recreate them. `operator-tools:retire-aliases` removes only
unchanged removable owned copies through the crash-consistent unlink lifecycle; modified,
foreign, and adopted copies are preserved and reported. `ccodex ultracode` enables session
Ultracode with ordinary permissions by default. A first `--yolo` on either `ccodex launch` or
`ccodex ultracode` is an explicit unsafe opt-in to Claude Code permission bypass; it is consumed
by the wrapper, cannot be combined with another permission-mode control, and does not weaken the
gateway-health or billing-honesty refusals. `-- --yolo` forwards the spelling literally.
`ccodex set-fast-model [<exact-model-id|->]` delegates to OpenCodex's existing configuration API
for Claude Code's Haiku/background small-fast slot. Bare invocation offers current Claude families
(entitlement checked when used), the gateway's live OCX catalog, and clear-to-normal-Haiku; one
argument preserves exact noninteractive selection and `-` clears. A completed choice is a
persistent operator mutation and is not an Auto-mode classifier selector. Native Windows
statusline/operator-tool activation is not certified and fails closed.
`operator-tools:status` reports a never-installed desired command as `absent` and reserves
`unmanaged` for a desired file that exists but is not owned; historical aliases are never
reported as required or absent.

`ccodex` has NO private plane (ADR-0014). Its `launch` and `ultracode` resolve the launcher from
the distribution checkout and directly execute the absolute `ocx` path bound by the last explicit
`operator-tools:install`; the same install binds `jq` and `uv` for catalog/config and Python-backed
routes, so ordinary installed use does not invoke repository-scoped mise or substitute caller-PATH
copies. That property did not hold for the ONE tool no absolute path can pin: the pinned `ocx` is a
`#!/usr/bin/env node` script, so the kernel resolves its interpreter by NAME from the child's PATH,
and a host where node existed only inside mise's install tree killed every gateway verb while the
bound ocx sat there executable — with a diagnostic blaming an install that had already succeeded
(agentic-sdlc-21f4). The install therefore binds the pinned `node` too and the dispatcher puts its
directory FIRST, which makes the name resolve to the reviewed interpreter rather than to whatever
the caller has; the consequence to know is that the same directory's `npm`/`npx`/`corepack` also
precede the caller's for every child, including a launched Claude Code. When nothing is bound, the
launcher reads ocx's shebang and names the unreachable interpreter instead of the install.

A DIRECT source-checkout launch carries no such binding and therefore resolves `jq` through
the pinned `mise -C <root> exec -- jq` route: no `jq` NAME is ever looked up, and `$AGENTIC_SDLC_JQ`
is admitted only as an absolute path or the literal pinned sentinel, so a bare or relative binding
is refused instead of resolved through ambient PATH. That `jq` classifies
the settings documents a refusal depends on and reads a provider config and gateway catalog adjacent
to credentials, so under ADR-0020 it is an exact dependency, and a substituted copy answering
`clean` would suppress every settings refusal. The residual is stated rather than hidden: that
pinned route locates `mise` itself on PATH, because mise is the documented sole bootstrap
prerequisite and is not itself pinned, so a substituted `mise` still governs this parse exactly as
it governs `ocx`. A bound-but-broken `$AGENTIC_SDLC_JQ` does not fall
back to the pin either — the surface that needed it blocks by name (exit 3 for a launch refusal,
`unknown` for the advisory catalog comparison), and rebinding stays an explicit
`operator-tools:install`. Claude Code therefore starts in the caller's physical current workspace. A reviewed toolchain refresh requires a
separate explicit operator-tools reinstall; ordinary commands never silently re-resolve, install, or
update tools. They use the operator's own `~/.claude` — configuration, plugins, agents, and login —
which is what lets Claude Code present its existing session to the gateway. `ocx claude` therefore
writes its `ocx-*.md` roster agents and
the gateway model cache into that global dir; the cache write is load-bearing, because Claude Code
only refreshes it while holding a credential and the `/model` picker would otherwise never list the
routed ids. There are no `ccodex session` verbs and no constructed plane-local `settings.json`.

**Only `scripts/muse-claude.sh` still has a plane**, and ADR-0010 governs it alone: its config dir
is selectively separate rather than isolated in every respect, inert per-session data (history,
project transcripts, todos, shell snapshots, file history) is shared with `~/.claude` by symlink,
and only the global `statusLine` stanza is inherited because that `env` block can carry a live
credential and copying it would also re-point the child away from its verified route. Credentials
never cross: the constructed document is asserted credential-free before it is written,
credential and plane-owned stores stay private, inheritance runs only after every credential
assertion, and it is fail-soft and never destructive. Do not cite config-dir isolation as evidence
that no session data is shared, and do not read a skipped entry as inheritance working.

Mutating global Claude settings still requires explicit operation-specific approval and no launcher
does it: the global file is read, never written, copied, or linked. `ccodex launch` refuses (exit 3)
rather than editing anything when a persistent or explicit settings document would defeat the route
— a provider-routing switch in `env`, an `apiKeyHelper`, an `sk-ant-api*` Console key, or a
cloud-provider-shaped model id in a model slot — `ANTHROPIC_MODEL`, an `ANTHROPIC_DEFAULT_*_MODEL`
tier slot, or `ANTHROPIC_SMALL_FAST_MODEL`. Explicit
`--settings` values must be one JSON object or a readable file containing one; every occurrence is
inspected before gateway startup and accepted argv is forwarded unchanged. An `sk-ant-oat*` login
is accepted wherever it is stored. Verb-level `--help` prints the launcher's own help and prepares
nothing; the leading wrapper `--` is consumed exactly once and every remaining argument, INCLUDING a
later literal `--` and everything after it, reaches `ocx claude` byte-for-byte. What Claude Code
then sees is `ocx claude`'s decision, not the wrapper's, and on opencodex 2.28.0 it is not always a
passthrough: measured 2026-08-23 (agentic-sdlc-c773), `-- --help` answered with ocx claude's own
help and `-- -p '<prompt>'` reached the model as a bare `-p`. Do not describe a later literal `--`
as ending Claude's option parsing — nothing in this repository can make that true, because there is
an extra program between the wrapper and Claude Code. The launch banner therefore prints the
forwarded argument SHAPE (count, option names, a literal `--` in place, values as opaque lengths)
instead of "withheld", so the wrapper's half of the boundary is observable.

`/sdlc-init` is a reviewed runbook, not a deterministic activation engine. It must stop on
ambiguous ownership, conflicts, unsupported capability, or missing evidence; do not claim
idempotence or Git-wave readiness from intent alone.

Unix installs use symlinks. Windows automatic mode tries directory junctions and file
symlinks, then falls back to copies; strict link mode has no fallback. Ownership state lives
under `XDG_STATE_HOME` on Unix or `LOCALAPPDATA` on Windows. Write commands serialize on that
state file.

**Ownership is BYTE identity, not physical identity, and that is a deliberate weakening — read both
halves of it.** An ownership record names its destination, its mode, and the digest of the bytes this
lifecycle published there; there is no `statx`/`stat` birth-timestamp witness, no device/inode
ownership token, and no settlement probe anywhere in the installer — the read-only projection's
torn-read guard stats the state file for read stability, and no `stat` result ever justifies a
mutation. So: a destination the operator MODIFIED is still refused, because any content they add,
edit, or retarget changes the tree digest or the link target — status reports a conflict and
install and uninstall preserve it untouched. But a destination the operator replaced with a
BYTE-IDENTICAL copy of the bundle's own payload is now REMOVED by uninstall, where the retired
witness refused it, and the same applies to a recreated link pointing at the same source and to a
configured home the operator re-pointed at a directory holding an identical copy. The harm is
bounded rather than absent: what is removed is byte-for-byte the bundle's own payload, so the
removal destroys no information of the operator's own — what it can defeat is their intent to
keep a copy there, never bytes only they hold. What the
weakening buys is that the installer no longer refuses to run at all on a filesystem exposing no
birth timestamp (NFS, several FUSE and overlay mounts) or on a libc without `renameat2` — there
is no glibc-2.28 or birth-time requirement left. `assert_safe_collection` is the boundary byte
identity cannot substitute for and it is asserted before any destination is read, so a collection
replaced with a link is refused by name rather than followed.

The installer admits exactly ONE ownership schema. A document written by any other generation is
refused by name, naming the version it found and the remedy — remove it and reinstall — and its bytes
are never retrofitted. There is no `--migrate-state` flag and no per-generation reader: the physical
witnesses and the transaction journal those documents carried no longer exist, so there is nothing a
migration could faithfully convert. Crash consistency is one `pending` slot mirrored from
`install_operator_tools.py`: a write arms the intended transition durably, moves the bytes, then
commits, and a later run resolves it by comparing the live bytes to the armed `before`/`after`
records. Bytes matching neither are reported and preserved, never guessed at. A copy-mode tree swap
is a rename-aside pair rather than one atomic replace, so an interruption inside it can leave the
previous tree parked in a named `.<name>.old-*` sibling; every such leftover is NAMED in the report
for the operator to remove by hand and is never deleted on their behalf. Linux/macOS
persistence-barrier failures stop mutation; native Windows provides handle-bound process-crash
recovery but does not claim sudden-power-loss durability for namespace transitions, and staged copy
CONTENT is no longer fsynced tree-wide either, so a copy-mode publication is process-crash consistent
rather than power-loss durable. Concurrent external mutation of managed paths during a write command
is unsupported. Exact legacy links and byte-identical copies can be adopted; foreign, retargeted, and
modified entries are preserved, while unchanged owned copies may refresh. The measured argument for
the weakening is recorded in `docs/research/2026-08-22-ci-red-forensics.md` and quoted in
`docs/research/2026-08-22-overengineering-audit.json` at `result.synthesis`: on the reference CI
runner the retired witness recorded an identical `(inode, btime)` pair in 20 of 20 delete-recreate
trials, so it carried no discriminating information exactly where it was tested. That audit's
`audits[0]` carries the qualitative deletion argument, not the measurement. No ADR governed the
retired layer, so none is superseded here; this paragraph is the doctrine of record.

Native Windows runs the current-host task normally. From WSL, all-host tasks run WSL first,
then invoke native Windows mise and report the two hosts separately. `hooks:install` installs
lefthook's validate pre-commit and test/self-test/secrets pre-push subsets; hooks are best-effort
convenience, not release authority. The Bash installer is a mise-backed compatibility wrapper retaining
positional `status`, `uninstall`, `self-test`, and legacy `--copy`.
For Claude, use either direct install or the marketplace, never both; marketplace
overlap blocks only Claude. No local status, gate, reviewer label, or conductor choice grants
authority for push, publication, PR mutation, merge, deployment, credential, or other outward
effect; each requires explicit operation-specific authorization.
