# Agentic SDLC Orchestrator

Reusable, provider-native operating kit for project-scale agentic software delivery across
Codex, Claude Code, and other skill-capable hosts. cmux is an optional view/event layer;
tmux is never a baseline requirement.

**Install it.** [mise](https://mise.jdx.dev) is the only bootstrap prerequisite. Read
`mise.toml` before step 2 — that step authorizes whatever it says at that moment:

```bash
git clone https://github.com/Codeseys-Labs/agentic-sdlc.git && cd agentic-sdlc
mise trust ./mise.toml          # persistent, per-path, and needs your explicit approval
mise --locked install           # 12 pinned tools, ~1.3 GB
mise run bundle:install         # skills, agents, and commands for this host
mise run operator-tools:install # optional: puts `ccodex` on your PATH
```

Then `mise run bundle:status` should report `N ok, 0 conflict, 0 absent`. Full walkthrough with
the reasoning behind each step: [Quickstart from a clean clone](#quickstart-from-a-clean-clone).
Every command with what it does: [`ccodex` — the operator dispatcher](#ccodex-the-operator-dispatcher)
and [the task table](#install-and-run-the-bundle). Verified from nothing on a fresh
`ubuntu:24.04` container against the public remote — `docs/research/2026-08-08-fresh-host-install-verification.md`
records the transcript, including two defects it found.

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
`scripts/bump-version.sh <x.y.z>` writes all of them; `--check` gates drift in CI — the
validator reports a disagreeing manifest as an error, so the gate and CI fail closed on drift.

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

**The rule on third-party skill libraries has two parts, and the distinction between them is
the whole point: this bundle never *vendors* a foreign library's bytes, and it can *invoke* a
library's own installer on explicit request.**

- **Never vendored.** No foreign library's bytes are copied into this repository's tree. That
  is what would trigger a `NOTICE` donor obligation under ADR-0001, drag another licence into
  this distribution, freeze one snapshot of somebody else's catalog, and put entries this
  bundle did not author onto its own selection surface. Foreign *ideas* enter here by exactly
  one path: an adapted `references/*.md` file with a root `NOTICE` donor entry landed in the
  same change, re-expressed in this bundle's own prose rather than copied.
- **Installable on request, from a closed catalog.** `libraries:list`, `libraries:status`, and
  `libraries:install` support exactly `mattpocock/skills`, ECC (`affaan-m/ECC`), and
  hyperresearch through each library's *own* front door. Unlisted libraries—including gstack—are
  operator-owned foreign state until separately verified and onboarded; these tasks do not adopt,
  inspect for ownership, migrate, or remove them. Running a supported third party's installer
  copies nothing here: the bytes land in the
  operator's home, written by the library's own code, under its own name and licence, exactly
  as if the operator had typed the command. So no donor obligation attaches. These tasks are
  opt-in and collision-checked, and **no gate leaf, `contributor:setup`, deprecated `setup`,
  or `bundle:install` path reaches them** — `check`'s dependency closure is `validate`, `test`,
  `self-test`, `secrets`, and `contributor:setup` contains only `bundle:install` plus
  `hooks:install`. Installation is therefore a deliberate choice, never a side effect.

The installer's ownership model is what makes the two coexist: an entry this bundle does not
own is classified `foreign` and preserved rather than replaced. Decisions and evidence:
`docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md` (the
opt-in mechanism) and
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md` (the
no-vendoring rule it refines), plus `skills/external-skill-libraries/`.

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
- `skills/dispatching-exact-ocx-models/`: exact-route dispatch seam after rightsizing resolves a
  `RuntimeAssignment`. It distinguishes generated `ocx-*` Agent types from Workflow `agent()`
  injection, checks model-visible tool compatibility, and requires verified post-run identity.
- `skills/reviewing-overengineering/`: independent complexity/deletion audit for one immutable
  plan or diff. It pairs deletion pressure with a safety-preservation rebuttal and classifies work
  as essential safety complexity, accidental complexity removable now, or speculative deferral.
  Ponytail may complement it but is never required.
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
- `commands/sdlc-{init,frame,wave,mission,rightsize}.md`: Claude Code slash commands —
  `/sdlc-init` activates Agentic SDLC inside a repository without reinstalling global
  capabilities. It establishes a reviewed tracked Git baseline, Seeds queue,
  mise/lefthook/betterleaks gate stack, per-worktree trust policy, cross-host `AGENTS.md`
  guidance, and CI parity. It is a reviewed runbook: claims of idempotence or Git-wave readiness
  require observed evidence; it preserves existing project policy and stops on ambiguity. `/sdlc-frame` frames one run,
  `/sdlc-wave` runs one Seeds-backed Git-worktree wave, `/sdlc-mission` runs an
  autonomous backlog-zero mission with concurrent critique and bounded backflow, and
  `/sdlc-rightsize` discovers the operator's live OCX routes plus usable Claude-subscription
  passthrough, asks only environment-relevant source/model/task/budget questions, and produces a
  regenerable v2 `.agentic-sdlc/rightsize/model-task-map.json` + `.md` + `.evidence.json` trio. Published
  benchmarks nominate candidates; only an explicitly approved, bounded target-local evaluation
  can recommend `role-qualified`, and the checked-in runtime receipt policy still separately
  controls production admission. `mise run rightsize:evaluate -- plan ...` is read-only;
  `evaluate` consumes provider/subscription capacity only with its exact displayed authorization
  digest. Neither a benchmark, local evaluation, nor map authorizes dispatch (see
  `skills/model-tier-rightsizing/references/model-task-map-schema.md`,
  `docs/adr/0015-local-evaluation-is-the-rightsizing-promotion-boundary.md`, and
  `skills/model-tier-rightsizing/references/workflow-prompt-budget.md`).
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

## First task: a small hello world

After the bundle is installed, start with one small, local change rather than a mission or a
multi-worker plan. Three terms are enough for the first pass: **Seeds** is the project's durable
work queue; a **Frame** is the short plan for one task; and a **Wave** is the reviewed worktree
execution of ready Seeds.

1. In the target project, if its Seeds queue is absent, route to
   [`/sdlc-init`](commands/sdlc-init.md) and stop. It is a reviewed activation runbook: it
   establishes evidence for the Git baseline, queue, gates, and guidance, or stops on a conflict.
   Do not use Frame or Wave to improvise activation.
2. Frame one observable task, for example:

   ```text
   /sdlc-frame Add a hello command that prints "hello" and one test for it.
   ```

   The Frame records the done condition, scope, required gate, review point, queue state, and any
   outward operation that would need separate explicit approval.
3. If a certified delegation route is available, run the ready task through
   [`/sdlc-wave`](commands/sdlc-wave.md). Every actual worker or model spawn still requires a
   conductor-supplied certified `RuntimeAssignment`; an inherited, unresolved, or unverified route
   stops before dispatch.
4. If no certified delegation route exists, the Frame may choose **exactly one** bounded,
   non-delegated conductor execution instead. It runs in one clean, dedicated Git worktree with
   the same framed scope, acceptance criteria, gate, snapshot review, and conductor-only queue
   reconciliation as a Wave. It has zero workers, zero model spawns, and no `RuntimeAssignment`
   claim. It is not a convenience fallback: stop rather than execute when the task needs another worker,
   another direct pass or retry, parallel work, or cannot be bounded and reviewed.
5. Review the stable diff, run the named gate, and reconcile findings before describing the task as
   complete. A gate, review, queue state, or local status never authorizes a push, PR mutation,
   merge, publication, deployment, or another outward effect.

The detailed command flow lives in [`/sdlc-frame`](commands/sdlc-frame.md) and
[`/sdlc-wave`](commands/sdlc-wave.md); both route an absent queue back to
[`/sdlc-init`](commands/sdlc-init.md).

## Install and run the bundle

The commands below describe the **current** checkout-backed distribution. A versioned,
self-contained GitHub release is the agreed next distribution boundary, with
`mise use -g github:Codeseys-Labs/agentic-sdlc` as the primary quick install and this managed
checkout retained for customization, contribution, gates, and release building. That quick path is
not available yet: the repository has no release artifact for mise to resolve. The exact proposed
contract, payload split, activation boundary, and implementation sequence are recorded in
[`docs/plans/2026-08-14T163833Z-Install-UX.md`](docs/plans/2026-08-14T163833Z-Install-UX.md).
Do not present the planned command as working until its release workflow and clean-host tests land.

### Managed fetch, without cloning by hand

If you would rather not choose a directory or track where the tree lives,
`scripts/bootstrap-agentic-sdlc.sh` fetches this repository into a managed location and then
stops, printing the remaining commands instead of running them. Download it, read it, then run
it — in that order, because it is a script that clones:

```bash
curl -fsSL -o bootstrap-agentic-sdlc.sh \
  https://raw.githubusercontent.com/Codeseys-Labs/agentic-sdlc/main/scripts/bootstrap-agentic-sdlc.sh
less bootstrap-agentic-sdlc.sh
bash bootstrap-agentic-sdlc.sh --dry-run
bash bootstrap-agentic-sdlc.sh
```

`--dry-run` prints the exact `git clone` it would run and creates nothing. `--remote <git-url>`
selects the exact Git remote (rather than relying only on `AGENTIC_SDLC_REMOTE`), and `--ref`
selects its branch or tag. The managed clone lands in
`${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc`, reported by `--print-path` and overridable
with `AGENTIC_SDLC_HOME`; the resolved commit is recorded in
`${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc/bootstrap-receipt.json`. Its final handoff
prints the receipt, checkout commit, reviewed files, exact trust/toolchain commands, an explicit
Claude-or-Codex install choice, and the status verification command. Removing both paths removes
everything the script created. Re-running is idempotent: it reports the existing clone's ref and
commit, refuses rather than clobbering an unexpected remote, a dirty tree, or a ref mismatch, and
fetches only under `--update`. `--help` documents each of those flags without running a tool.

The script requires mise and git and installs neither, so it adds no bootstrap prerequisite. It
deliberately does not trust the config, resolve the toolchain, or install bundle entries: those
stay separate approvals against a tree you have read, and it prints them as steps 2 through 5
below. HTTPS authenticates the transport, not the contents — nothing here verifies a signature
over the fetched commit, so read the tree before trusting it. `docs/adr/0011` records why the
clone is managed rather than eliminated: the tasks still come from a tree on disk, because every
task command and installed symlink resolves against one. For a genuinely tree-free install of the
plugin payload alone, see the marketplace plane below.

### Quickstart from a clean clone

Five steps, in order, from an empty directory. Step 3 is a persistent mutation with its own
approval gate; steps 2 and 3 are what a fresh clone otherwise fails on. The managed fetch above
replaces step 1 only.

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

4. Resolve the locked toolchain. `mise.lock` pins **12 tools** — `uv`, `node`, `npm`, `bun`,
   `lefthook`, `jq`, `ripgrep`, `fd`, `gh`, `betterleaks`, `opencodex`, and `seeds-cli` — for
   roughly 1.3 GB and about 30 seconds on a warm network. mise ships `auto_install` enabled, so
   skipping this step does not avoid the cost: the first `mise run <task>` installs all 12
   without prompting.

   ```bash
   mise --locked install
   ```

5. Choose an install plane explicitly. Claude entries go under the configured Claude home
   (`~/.claude` by default); Codex entries go under the configured Codex home (`~/.codex` by
   default, or `CODEX_HOME`). `--agent` applies to install, status, and uninstall. To use
   non-default roots, pass `--claude-home <path>` and `--codex-home <path>` after `--`.

   ```bash
   mise run bundle:install -- --agent claude
   # or: mise run bundle:install -- --agent codex
   # inspect both configured planes without writing: mise run bundle:status
   ```

   A detected Claude marketplace install is reported once as a Claude-plane conflict and blocks
   only direct Claude installation; Codex continues. Use either the marketplace or direct
   installation for Claude, not both. Foreign or changed entries are preserved with a reason and
   a retry instruction; never delete a reported path merely to make the installer green.

6. Optional, and a separate approval: put the `ccodex` dispatcher on your `PATH`, so the
   installed bundle is usable without `mise` in front of every command. This writes into
   `${XDG_BIN_HOME:-$HOME/.local/bin}` and only when that directory already exists and is on
   `PATH` — see [the dispatcher section](#ccodex-the-operator-dispatcher):

   ```bash
   mise run operator-tools:install
   ```

Each bundle lifecycle action ends in a terminal summary. `mise run bundle:status` reports only
entries already present in the lifecycle ownership record: either `no owned entries for this host`
or an `N ok, M conflict, K absent` summary. It does not inventory unowned names in a configured
collection. Before installation, or when a path may have been installed through another checkout,
use `mise run bundle:install -- --agent <claude|codex> --dry-run`; that read-only preview discovers
an occupied unowned destination, reports it as preserved, and never adopts, overwrites, or removes
it. Install and uninstall summaries separately name installed/removed, preserved, planned, and
conflict counts. `mise run check` runs the authoritative gate. Each command's exit code and output
are evidence about that run only; neither authorizes any outward effect.

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
Node `22.23.2`. Both bootstrap and inspect reject any other executing Node. Bootstrap rejects
nested, staged, dirty, untracked, or ignored distribution content, then alone runs reviewed
`mise --locked install`. That install isolates HOME, mise config/data/cache, hooks, npmrc, and
registry selection from ambient values. Only the reviewed root `mise.toml`/adjacent lock, the
fixed official npm registry, npm backend, and private empty configs select acquisition. It
resolves exact config-free Node `22.23.2`, Bun `1.4.0`, and Seeds `npm:@os-eco/seeds-cli@0.5.15`
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
<exact-node-22.23.2-root>/bin/node <installed-flagship>/tools/seeds-launcher.mjs bootstrap --distribution <exact-clean-git-root>
```

After explicit bootstrap, read-only Seeds operations use `inspect --target <target>` against only
the active receipt. Inspect never installs, networks, calls mise, or repairs state. It allows only
`--version`, `prime`, `ready [--format json]`, and `blocked [--format json]`; all other input fails
before exact Bun starts. Exact Node uses `shell:false` to invoke only absolute recorded Bun and entry
paths. Bun receives `--config=<trusted-empty-file>`, `--no-env-file`, and `--no-install`; its
allowlisted environment isolates target `bunfig`, `.env`, package configuration, ambient `BUN_*`,
`NODE_OPTIONS`, npm/mise overrides, and unreviewed Seeds debug settings. PATH contains only the
independently recorded Git directory, with system/global Git config isolation.

Queue mutation uses `record` with `--queue-writer conductor`. A repository with no `.seeds` node may
use only `--expect-queue absent init`; the launcher rejects existing/partial/file/symlink/redirected
surfaces, snapshots `.gitattributes`, and refuses non-UTF-8 or exact-line/substr-match-ambiguous
prestates before mutation. It invokes exact pinned `init --json` and verifies exactly the five
initializer files plus only the precise missing merge-union append. Existing queues require an
exact sha256 and admit only verified create/update deltas. Standalone claim, close, delete, prune,
disposition, sync, and other mutation forms remain forbidden. The prerequisite checker exposes
separate exact-runtime inspect, init, and record front doors; the skill and
`references/seeds-worktrees.md` define their unambiguous contracts.

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
| `operator-tools:install` / `operator-tools:status` / `operator-tools:retire-aliases` / `operator-tools:uninstall` | Manage `ccodex` and its statusline support in an existing Unix PATH; explicitly retire only unchanged owned historical aliases. |
| `operator-tools:self-test` | Exercise the operator-command lifecycle in an isolated home. |
| `claude:statusline:status` / `claude:statusline:activate` / `claude:statusline:deactivate` | Inspect or explicitly manage only Claude Code's `statusLine` fields. |
| `ocx:launch` / `ocx:ultracode` | Launch Claude Code through the gateway using your own `~/.claude` login — native Claude models on your subscription, gateway models on their own providers — normally or with session-only Ultracode. Ordinary permissions are the default; a first `--yolo` is the explicit unsafe bypass profile. |
| `ocx:status` / `ocx:restart` / `ocx:configure` | Report opencodex gateway reachability, restart it cleanly, or configure providers through their own login flows. |
| `libraries:list` / `libraries:status` | List the installable external skill libraries with their front doors and surface cost, or report which are already present in this home. Read-only. |
| `libraries:install` | Install explicitly named external skill libraries through their own front doors; dry run unless `--yes`. Vendors nothing into this tree, and no gate leaf, `contributor:setup`, or deprecated `setup` path reaches it. |
| `libraries:migrate` | De-duplicate a name another channel holds for the same upstream: retire that channel's copies through its own removal path, then install. Dry run unless `--yes`; names at least one library, never migrates everything. |
| `mermaid:provision` | Provision the pinned Linux x64 Mermaid browser runtime. Downloads a pinned browser, so it is an explicit operator step and never a gate leaf. |
| `mermaid:linux-test` | Run the bounded Linux Mermaid renderer tests; they skip with named reasons when the runtime is absent. |
| `rightsize:evaluate` | Explicit non-gate rightsizing CLI: discover, plan, evaluate after digest-bound approval, or deterministically render prior evidence. Live evaluation may consume provider/subscription capacity and send the selected task-pack data outward. |
| `validate` | Run the portable bundle validator alone (the pre-commit hook's subset). |
| `test` | Run the installer test suite. |
| `self-test` | Exercise install/status/uninstall in an isolated home. |
| `secrets` | Scan tracked plus nonignored-untracked regular files with the pinned scanner and tracked extend-only config. Symlinks and paths beneath symlinked parents are not followed; ignored runtime state stays out, and history remains a separate consented step. |
| `check` | Run the authoritative validation, tests, self-test, and secrets gate. Last measured on Linux: the `test` leaf ran 765 tests in 322s (`OK (skipped=13)`), while `validate` and `secrets` each finished in under 2s, so the suite dominates and 15 minutes is a reasonable budget — more on a loaded host, since gate runs contend for CPU and I/O. Treat both numbers as stale-by-design: the count grows with the suite, the clock varies by host, and the gate's verdict is the evidence. |
| `hooks:install` | Install the checked-in lefthook hooks. |
| `contributor:setup` | Install the configured bundle planes plus this repository's Git hooks. |
| `setup` | One-release deprecated forwarder to `contributor:setup`. |

A normal Unix install uses symlinks. On Windows, automatic mode uses directory junctions
for directories and file symlinks for files. When the host cannot create those links, it
falls back to copies. Strict link mode does not use that fallback. The installer records
per-entry ownership in the platform state directory (`XDG_STATE_HOME` on Unix,
`LOCALAPPDATA` on Windows). Lifecycle operations use that record to distinguish bundle
entries from user files. Write-capable lifecycle commands are serialized per state file.
Ownership is BYTE identity: a record carries the digest of the bytes this lifecycle published, and
nothing else identifies the destination. There is no birth-timestamp or device/inode requirement, so
there is no minimum libc and no filesystem that has to expose `statx` birth time — a host where
`cp -r` works can install. See "Ownership and lifecycle rules" below for what that costs.

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
approval never covers it. A separate Unix operator-tools plane can then install its existing executable surface into
`${XDG_BIN_HOME:-$HOME/.local/bin}`, and only when that physical user-owned directory is already
on `PATH`. After that explicit operation-specific approval, it never creates shell aliases or edits
PATH: if the directory is absent from PATH, the refusal names the directory and tells you to update
your shell configuration, start a new shell, and retry:

```bash
mise run operator-tools:install
mise run operator-tools:status
```

### `ccodex` — the operator dispatcher

`ccodex` is the whole daily use surface without mise in the way. Plain `claude` remains the direct
Anthropic-routed CLI; `ccodex launch` adds the gateway to that same login, so one session serves
both catalogs — native claude ids pass through to Anthropic on your subscription and gateway ids
route to their own providers (ADR-0014). It is not a separate non-Anthropic-only route. Fresh
operator-tools installs no longer create `ocx-launch` or `ocx-ultracode`. Existing lifecycle-owned
copies remain recognized and can be retired explicitly with `mise run operator-tools:retire-aliases`;
changed, foreign, and adopted copies are preserved. Every gateway command remains reachable as
`ccodex ocx <verb>`, the low-level compatibility form; `ccodex --help` prints the surface at any time.

**Gateway plane** — running one Claude Code session that can reach both catalogs:

| Command | What it does |
|---|---|
| `ccodex ensure` | Ensure the gateway is healthy without launching Claude Code. |
| `ccodex launch [--yolo] [claude args...]` | Ensure the gateway is healthy — start it if down, restart once if half-up — then launch Claude Code in the caller's current workspace through the distribution's pinned gateway toolchain, using your own `~/.claude` login. Native claude models pass through to Anthropic on your subscription while gateway models route to their own providers, in one session. Fails closed if the gateway never becomes healthy, and refuses (exit 3) when exported, persistent, or explicit `--settings` configuration would silently defeat the route. Accepted Claude arguments are forwarded unchanged. A first `--yolo` is consumed by ccodex and explicitly selects Claude Code's permission-bypass mode; it is unsafe outside an isolated, disposable environment. Use `-- --yolo` only to forward that spelling literally. |
| `ccodex launch --model <id>` | Pick any id in the running gateway's live catalog, including a namespaced one: `--model muse/muse-spark-1.2`. Run `ccodex models` for the list. |
| `ccodex ultracode [--yolo] [claude args...]` | The same fail-closed launch path with session Ultracode applied. Ordinary permissions remain the default. A first `--yolo` explicitly selects the same unsafe permission-bypass mode as `ccodex launch --yolo`; this is the ccodex equivalent of the historical `ccode-ultracode` alias. Ultracode owns the session `--settings` value and refuses a competing setting. |
| `ccodex status` | Read-only supervision view: pid, port, uptime, healthy/down, log location, configured providers each compared against the LIVE catalog, whether anything exported here or in the settings documents Claude Code reads for `env` would defeat the gateway route — the check NAMES the documents it read and what it did not read — and the attribution log command. Exit 0 means the gateway answered an identity-checked probe at that moment — evidence, not authorization. |
| `ccodex restart` | Stop the gateway cleanly, then ensure it is back up. Fails closed on an unclean stop. Interrupts in-flight turns in every routed session, and `ocx` rewrites shared `~/.codex` config as part of its lifecycle. |

**Providers and models** — what a launched session can actually pick:

| Command | What it does |
|---|---|
| `ccodex providers` | Configured providers, and which are LIVE in the running gateway. A provider in the config file is **not** live until synced and restarted — check here rather than trusting an add's success message. |
| `ccodex models` | The running gateway's flat live catalog. Muse models appear as ordinary namespaced entries, not as a separate plane. |
| `ccodex set-fast-model [<exact-model-id\|->]` | With no argument, choose a Claude Code family or a model in the gateway's live OCX catalog, or clear the override to use the normal subscription Haiku slot. One argument preserves the exact noninteractive path; `-` clears. The write goes through OpenCodex and is **not** Auto mode's permission classifier. Claude families are entitlement-checked when used; only the OCX rows are proven live when the menu is built. |
| `ccodex configure` | With no arguments, print the admitted configuration surface in detail. |
| `ccodex configure provider add\|edit\|remove\|set-default <name> ...` | Reviewed provider mutation for non-Anthropic providers. Writes the **config file only** — see [the key sequence below](#adding-a-provider-that-needs-an-api-key). |
| `ccodex configure account add-key <name>` | Store a provider API key, read **only** from piped stdin. |
| `ccodex configure account list\|current <name>` | Masked credential inspection. |
| `ccodex configure help <verb>` | Inspect the upstream `ocx` surface without running it. |

**Experimental non-Claude Auto fallback, per launch only.** Claude Code exposes no supported
`classifierModel` setting. The only documented indirect experiment is to exclude Sonnet 5 from one
launch, which makes current Claude Code fall back to the session model when that route is otherwise
eligible:

```bash
auto_settings='{"availableModels":["gpt-5.6-sol"]}'
ccodex launch --model gpt-5.6-sol --permission-mode auto --settings "$auto_settings"
```

Use the same exact routed ID in both places and keep all inline settings in that one document.
`availableModels` constrains session, subagent, workflow, skill, and advisor selection for the
whole launch—not only Auto—and routed GPT/Muse Auto support is undocumented. This recipe is not an
identity claim; a real claim needs a separately approved bounded canary with request-correlated
gateway attribution. See
[`docs/research/2026-08-12-claude-code-auto-mode-controls.md`](docs/research/2026-08-12-claude-code-auto-mode-controls.md).

**Installed-bundle lifecycle** — managing what is installed, without mise:

| Command | What it does |
|---|---|
| `ccodex bundle install\|status\|uninstall` | Install, inspect, or remove this host's bundle entries. `status` always ends in one terminal line: `no owned entries for this host`, or `N ok, M conflict, K absent`. |
| `ccodex libraries list\|status` | List installable external skill libraries with their front doors and surface cost, or report which are already in this home. Read-only. |
| `ccodex libraries install <name> [--yes]` | Install a named external library through **its own** front door. Dry run unless `--yes`; vendors nothing into this tree. |
| `ccodex libraries migrate <name> [--yes]` | Retire another channel's copies of the same upstream through that channel's own removal path, then install. Dry run unless `--yes`. |
| `ccodex statusline status\|activate\|deactivate` | Inspect or explicitly manage only Claude Code's `statusLine` fields. Inactive until you activate it. |
| `ccodex version` | This command's resolved repository root and runtime dependencies. |

**Help, and how to reach the wrapped tool's help.** `ccodex <verb> --help` prints that verb's own
help and **runs nothing** — no gateway, no session state, no constructed settings. To reach the
help of the tool *behind* a launch verb, end this command's options with `--`:

```bash
ccodex launch --help                # this verb's help; prepares nothing, launches nothing
ccodex launch -- --help             # `--` forwards verbatim: Claude Code's OWN help
ccodex launch -- --print "prompt"   # any Claude Code argument, through a prepared session
                                     # Claude Code's own help, only if gateway is already healthy
```

`providers` and `models` are the two exceptions: they take no options of their own, so they run
the query rather than printing a help page, and `models` exits 1 when the gateway is down because
an unanswerable query is a failure rather than a refusal.

**Exit codes**, uniform across every route: `0` ok · `1` failure or unhealthy · `2` usage ·
`3` refused, meaning a boundary declined the operation rather than failing at it.

Only the **use** surface is installed. The maintenance tasks — `test`, `validate`, `check`,
`secrets`, `self-test`, `mermaid:*`, `hooks:install` — are deliberately absent, because they
belong to working *on* this repository rather than to using what it installed; run those with
`mise run <task>` inside the checkout. One owned dispatcher rather than a dozen named commands
means one ownership record, one place a new verb appears, and no PATH namespace land-grab.

**A shell function or alias named `ccodex` will shadow this command.** Bash resolves functions
and aliases before `PATH`, so a leftover definition silently wins and the installed dispatcher is
never reached — the symptom is `ccodex --help` printing the *wrapped tool's* help instead of the
table above. Diagnose with `type ccodex`: it must report a **file** under
`${XDG_BIN_HOME:-$HOME/.local/bin}`, not a function or alias. `which ccodex` is not enough, since
it reports the file that a function is hiding.

### Adding a provider that needs an API key

`provider add` writes the provider's SHAPE only. **It accepts no key** — it has no `--api-key`
flag and it does not read stdin, so a key piped to it is silently dropped and every later request
fails with `401 invalid_api_key` while the routing itself looks correct in the attribution log.
The key goes in through a different verb, and the gateway must already be running when it does.
Verified end to end on a fresh host (2026-08-08):

```bash
# 1. the provider's shape. No key here.
ccodex configure provider add muse --adapter openai-responses \
  --base-url https://api.meta.ai/v1 --default-model muse-spark-1.2

# 2. the gateway must be UP before a key can be stored.
ccodex ensure

# 3. the key, read only from piped stdin -- never argv, which `ps` exposes host-wide.
printf '%s' "$YOUR_KEY" | ccodex configure account add-key muse --label my-key

# 4. a restart puts the key into the running routing table.
ccodex restart

# 5. confirm, then use it.
ccodex providers                    # muse should be LIVE, not merely configured
ccodex launch --model muse/muse-spark-1.2
```

After step 3 the provider carries `apiKey` and `apiKeyPool`; before it, only `adapter`, `baseUrl`,
and `defaultModel`. Check with `ccodex providers` rather than trusting step 1's success message.

Two upstream notes. `ocx sync` — which the post-mutation notice names — needs Codex installed and
reports `Codex config not found` on a host without it; the gateway still starts and still routes,
so the restart path above is sufficient. And `ocx ensure` may log
`Provider model discovery ... failed with HTTP 401 [fallback=configured]` for a key-authenticated
provider: that is ocx not sending the key on its discovery probe, it is harmless, and the
configured model id is used instead.

**Reasoning models need a real token budget.** `muse-spark-1.2` spent 163 of 176 completion tokens
on reasoning for a two-word answer. A `max_tokens` that looks generous for the visible reply
returns `content: null` with `finish_reason: "length"` — which reads exactly like a broken
credential and is not. Size the budget for the reasoning trace.

**The repository clone is required, but repository-scoped mise is not part of daily installed
`ccodex` use.** `ccodex` remains a thin, owned entry point rather than a self-contained copy: its
launcher and Python lifecycle scripts live in the checkout, while `operator-tools:install` resolves
the reviewed `ocx`, `jq`, and `uv` pins once and renders their absolute executable paths into the
installed dispatcher. Launch and Ultracode invoke that bound `ocx` directly from the caller's physical current
workspace; the checkout selects code and runtime identity, not the project Claude works on. A moved
checkout may be selected with `AGENTIC_SDLC_ROOT`, but moving or replacing the mise tool store
requires an explicit `mise run operator-tools:install` refresh from the reviewed distribution.
Ordinary commands never silently re-resolve, install, or update those tools. Direct execution of
source launchers retains a repository-scoped mise fallback for development and maintenance.
Python-backed bundle, library, and statusline routes use the same install-bound
`uv`; caller PATH cannot substitute it.

No shell startup file or PATH value is edited. Every launch route delegates to
`scripts/opencodex-claude.sh`, so identity-checked supervision and the route-integrity
refusals remain mandatory, including validation of every explicit `--settings` value before the
gateway starts. The ADR-0005 credential refusal, the environment scrub, and the
separate Claude config dir are GONE from this launcher (ADR-0014): it uses your own `~/.claude`
so Claude Code can present its existing login to the gateway. `ccodex ultracode` refuses a
competing `--settings`; on either launch form, `--yolo` refuses competing permission controls.
Launch/restart still carries
opencodex's documented shared `~/.codex`
configuration side effect.

### Muse Spark is a provider, not a plane

There is no muse launcher and no `muse:*` task. Muse Spark is one provider registered in the
gateway, exactly like the openai/codex provider, and the running gateway serves a **single flat
catalog** in which its models appear as ordinary namespaced ids. Verified 2026-08-07 against the
live gateway: `GET /v1/models` returned ten entries — seven `gpt-*` ids plus
`muse/muse-spark-1.1`, `muse/muse-spark-1.2`, and `muse/muse-spark-1.2-contributor`. So a session
launched with `ccodex launch` selects a muse model the same way it selects a gpt one, per request
or through the `/model` picker. Run `ccodex models` to see exactly what a launched session can
pick; that view reads the gateway's live catalog rather than the configured list, because the two
disagree and only the live one answers the question. Adding a provider goes through the reviewed
configure route with muse as the worked example — nothing about it is special-cased in code.

### Which login a launch uses

`ccodex launch` uses your OWN `~/.claude` — configuration, plugins, agents, and login. That is
what lets Claude Code present its existing claude.ai session to the gateway, which is the whole
point of the route (ADR-0014). One session then serves both catalogs, because the gateway decides
per request: a genuine `claude*`/`anthropic*` id that no alias or `modelMap` claims is forwarded
verbatim to `api.anthropic.com` on your subscription, and every gateway id routes to its own
provider on that provider's credential. No Anthropic credential is used for the routed turns.

Anthropic's [gateway documentation](https://code.claude.com/docs/en/llm-gateway) describes this
configuration: with `ANTHROPIC_BASE_URL` set and **no** gateway credential, "a saved claude.ai
login remains the active credential, so its usage limits and billing apply", and such gateways
"must forward the OAuth capability in `anthropic-beta`" — which opencodex does, stripping only
hop-by-hop headers plus `host`, `content-length`, `accept-encoding`, `x-opencodex-api-key`, and
`origin`. The same page states Anthropic "doesn't support routing Claude Code to non-Claude models
through any gateway", so the routed half is permitted but unsupported. The restriction in
[legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) binds third-party
developers routing "on behalf of their users", not an operator routing their own credential
through their own local hop.

Until 2026-08-11 this launcher did the opposite — isolated config dir, full `ANTHROPIC_*`/
`CLAUDE_*`/`AWS_*` scrub, and four refusals aimed at keeping a subscription credential out of
scope. That machinery, the `ccodex session` verbs, and the separately named
`ccodex claude-subscription` route are all gone. `scripts/muse-claude.sh` still keeps its own
isolated plane, so ADR-0010's inheritance and environment-variable policy still govern **it**, and
ADR-0014 changed nothing inside `assets/claude/session-inheritance.sh`. That helper did change on
2026-08-18, for ADR-0010's own Amendment A: the `CLAUDE_*` allow-by-name half is now implemented and
is `scripts/muse-claude.sh`'s only scrub, so a deliberately-set inert flag such as
`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` survives the deny sweep by name (Amendment A.1).

**Three route-integrity refusal channels remain, for billing honesty rather than prohibition.** A
launch exits 3 when the gateway route would not actually be used. None edits anything to fix it:
changing a persistent settings file is a mutation that needs explicit operation-specific approval
for that exact path, so the launcher reports the blocker and stops instead.

| Refused | Why it matters |
|---|---|
| A provider-routing key — `CLAUDE_CODE_USE_BEDROCK`/`USE_VERTEX`/`USE_FOUNDRY`, `AWS_BEARER_TOKEN_BEDROCK`, `ANTHROPIC_BEDROCK_BASE_URL`, `ANTHROPIC_VERTEX_BASE_URL` — exported **or** in a persistent settings `env`, or an `apiKeyHelper` there | It outranks the gateway. Under Bedrock the client consults `ANTHROPIC_BEDROCK_BASE_URL` and never `ANTHROPIC_BASE_URL`, so the session bills the cloud account while the launcher prints a gateway banner. Measured on a real host on 2026-08-10: the request never reached a local capture listener and was still answered. |
| An `sk-ant-api*` Console key in `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` | It satisfies opencodex's bare `sk-ant-` passthrough gate, so it takes the **same** native branch and bills API credits while looking like subscription traffic. The prefix is the only distinguishing signal. |
| An explicit `--settings` value that is missing, not one JSON object or a readable file containing one, or carries either blocker above | Claude merges selected settings after the process environment. A local two-listener probe on 2026-08-13 showed selected `env.ANTHROPIC_BASE_URL` taking every request away from the gateway. Every occurrence is inspected before gateway startup; accepted arguments are forwarded unchanged. |

An `sk-ant-oat*` login is accepted — carrying it is the point. The checks inspect the minimum needed
names, prefixes, and selected settings bytes; no credential value or selected settings path is
printed, copied, or persisted. `ccodex status` reports persistent/exported blockers; launch-time
`--settings` values are checked only on that launch.

Keep a cloud-provider route in a per-command wrapper of your own rather than in the global
settings document, so the two do not fight. `ocx claude` writes its `ocx-*.md` roster agents and
the gateway model cache into `~/.claude`; that cache write is load-bearing rather than incidental,
because Claude Code only refreshes it while holding a credential, so without it the `/model`
picker would never list the routed ids.

**Help is never a side-effecting operation.** `ccodex <verb> --help` prints that verb's own help
and prepares nothing — it starts no gateway and writes nothing. To reach the help of the tool
*behind* a launch verb, end the wrapper's options with `--` (`ccodex launch -- --help`).

Mutating your global Claude settings still requires explicit operation-specific approval for that
exact file, and no launcher does it: the global document is read, never written, copied, or linked.


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

### Ownership and lifecycle rules

Inspect ownership, then act:

```bash
mise run bundle:status
mise run bundle:install -- --agent claude --dry-run
mise run check
```

**Ownership is byte identity.** An ownership record names its destination, its mode, and the digest
of the bytes this lifecycle published there. A destination you MODIFIED is refused and preserved,
because your content changes the tree digest or the link target. A destination you replaced with a
byte-identical copy of the bundle's own payload is treated as owned and will be removed by
`bundle:uninstall` — that is a deliberate, bounded weakening (the bytes removed are the bundle's own),
and it is what lets the installer run on filesystems that expose no birth timestamp. AGENTS.md
records the full doctrine.

The installer admits exactly one ownership schema. A document written by another generation is
refused by name — it tells you the version it found and the remedy, which is to remove the state file
and reinstall — and its bytes are never rewritten. There is no `--migrate-state` flag: the physical
identity witnesses and the transaction journal those older documents carried no longer exist, so
there is nothing a migration could faithfully convert. Diagnose an unowned destination with
`bundle:install -- --agent <claude|codex> --dry-run` and resolve its ownership deliberately.

Crash consistency is one armed `pending` transition: a write records what it intends durably, moves
the bytes, then commits, and a later run resolves it by comparing the live bytes to the recorded
before/after. Bytes matching neither are reported and preserved. A copy-mode tree swap is a
rename-aside pair rather than one atomic replace, so an interruption inside it can park the previous
tree in a named `.<name>.old-*` sibling; every such leftover is named in the report for you to remove
by hand and is never deleted for you.

Linux and macOS require their supported namespace durability barriers; failures stop the operation.
macOS uses `F_FULLFSYNC` for the state document and directory fsync for namespace changes; staged
copy content is not fsynced tree-wide, so a copy-mode install is process-crash consistent rather than
power-loss durable. Native Windows supports process-crash recovery but does not claim
sudden-power-loss durability for namespace transitions. Concurrent external mutation of managed paths
during a write command is unsupported; detected content changes are preserved and reported as
conflicts.

Collection directories are never replaced, and a collection replaced with a link is refused by name
rather than followed. An exact legacy bundle link or byte-identical copy may be adopted into
ownership. Foreign entries, retargeted links, and modified copies are preserved and reported as
conflicts. Uninstall removes only owned entries and leaves conflicts and foreign files in place.

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
