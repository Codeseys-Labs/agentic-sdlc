# Decision corpus: what is already decided that binds or contradicts an install-UX redesign

- **Repo:** `/tmp/asdlc-research` (public `Codeseys-Labs/agentic-sdlc`, v0.7.4, HEAD `e0fbf92`)
- **Date of this reading:** 2026-08-24
- **Method:** every document named in the task was read in full. Current-state claims are grounded
  in tracked files (`mise.toml`, `bin/ccodex`, `scripts/build_release.py`,
  `scripts/ccodex_sdlc_install.py`, `policy/release-candidate.v1.json`, `README.md`,
  `.github/workflows/`). No `mise` task was run; the config was left untrusted.
- **Reading rule applied throughout:** ADR status is load-bearing. `ADR-0021` and `ADR-0028` are
  **proposed** (`docs/adr/0021-...:3`, `docs/adr/0028-...:3`); `ADR-0025` is **superseded by
  ADR-0030** (`docs/adr/0025-...:3`); `ADR-0022` items 1, 2, 3, 7 **no longer bind**
  (`docs/adr/0022-...:4-10`); `ADR-0005` items 2, 4, 7 are **superseded by ADR-0014**
  (`docs/adr/0005-...:4-35`). A proposed child "is not presented as a current product constraint"
  (`docs/adr/0028-...:112`).

---

## (a) Per-document operative decision and its stated reasons

### ADR-0002 — mise is the single front door; no second bootstrap prerequisite (accepted, 2026-08-06)

**Operative decision.** mise is the single front door for install, gates, and tasks, and **no
second bootstrap prerequisite** — second package manager, required env token, required network
credential, or (per the 2026-08-07 amendment) **required system package** — may be introduced by
any tool pin, task, or hook (`docs/adr/0002-...:45-49`, `:88-91`). Every new `[tools]` pin must be
verified on a machine with no credentials in the environment before commit (`:50-56`), registry
absence is never a reason to leave a tool unpinned (`:57-59`), and a version must never be
fabricated (`:60-63`).

**Stated reasons.** The betterleaks pin's default `github:` backend called the GitHub release API
at install time and was rate-limited to hard failure unauthenticated, which would have made
`GITHUB_TOKEN` a silent second prerequisite; the fix was `github.slsa = false` /
`github.github_attestations = false` plus `mise.lock` checksums (`:23-34`). The amendment adds the
measured `unzip` incident: `mise --locked install` exited 1 on `debian:13-slim` because the mermaid
pin's transitive puppeteer postinstall needed a zip archiver (`:93-108`), establishing that **a
pin's blast radius is the documented bootstrap command, not the gate graph** (`:110-116`). The pin
was removed rather than accommodated because it was redundant and was writing an unreviewed 420 MB
tree including a browser outside every digest the repo checks (`:118-136`). Screening rule for the
next pin: a postinstall that extracts an archive or downloads a browser is suspect; the
disqualifying property is **needing a tool mise does not provide**, not running install-time code
(`:142-151`). Enforcement is a named `NPM_BACKED_TOOLS` allowlist in `scripts/validate_bundle.py`
plus must-fail mutations in `tests/test_gate_graph.py`; it catches an unreviewed pin being added,
not an already-reviewed upstream growing a hostile postinstall, and the minimal-image check remains
a mandated human step (`:153-161`).

### ADR-0005 — opencodex installed by default (accepted 2026-08-06, partly superseded)

**Operative decision (as it survives).** `npm:@bitkyc08/opencodex` is pinned and installed by
default in the **convenience tier** — no gate consumes it, absence degrades DX only
(`docs/adr/0005-...:123-127`); the launcher owns the gateway lifecycle and fails closed, with
`ocx health` the only accepted verdict (`:143-157`); installing and launching are **not** route
qualification (`:169-176`). Items 2, 4, and 7 (single entry point script, the subscription-OAuth
code enforcement, the separate `claude-subscription` route) are superseded by ADR-0014
(`:4-35`).

**Stated reasons.** The npm backend needed no credential, so the pin added no second bootstrap
prerequisite — the same class as the existing npm pins (`:68-72`, `:213-217`) — but its integrity
surface is **version+backend only**, no tarball hash and no transitive integrity, accepted only
because nothing in the gate graph consumes it (`:218-222`). Upstream's default auth mode was the
opposite of this bundle's boundary, so adoption without a wrapper would make the prohibited route
the easy route (`:73-86`). Two upstream fail-open behaviors (`ocx ensure` exiting 0 without
starting; `ocx status` exiting 0 with the proxy down) forced re-probing rather than inheriting
verdicts (`:98-109`). Enforcement is fail-closed checks, explicitly **not a sandbox** against the
same OS user (`:223-228`).

### ADR-0011 — a remote bootstrap manages the clone instead of eliminating it (accepted, 2026-08-07)

**Operative decision.** Ship `scripts/bootstrap-agentic-sdlc.sh`, a stdlib-shell script that
fetches the repo into a managed location (`${XDG_DATA_HOME}/agentic-sdlc`, override
`AGENTIC_SDLC_HOME`), writes a receipt outside the clone, and then **stops and prints** the
remaining commands rather than running them (`docs/adr/0011-...:80-97`). It never trusts a config,
resolves a toolchain, or installs bundle entries — those stay three separate operator approvals
(`:92-97`); re-runs are idempotent and fail closed at exit 3 on wrong remote, dirty tree, ref
mismatch, non-fast-forward, or occupied non-git path (`:99-103`).

**Stated reasons.** Two executed facts: mise's experimental `git::` task includes **clone anyway**
into an unreviewable cache, parse this repo's `mise.toml` as a task-file schema (rejecting
`[settings]`/`[tools]`), carry tasks only (never `[tools]`), and resolve task commands against the
caller's cwd (`:20-36`); and the tree is a **run-time** dependency — every Python entrypoint
anchors on `Path(__file__).resolve().parents[1]` with no override, default installs are symlinks
into the tree with absolute source paths re-verified via `os.path.samefile`, and PATH launchers bake
an absolute in-tree exec target (`:38-52`). Hence "the clone cannot be eliminated, but the
*operator's* act of cloning can be" (`:54-55`). Rejected: `git::` includes, `mise use -g` plus a
separate fetch (installs tools with nothing to run), `curl | bash` as primary, and a bare two-liner
(`:57-77`). Honest negatives: the clone-free claim is narrow; HTTPS authenticates transport not
contents; the receipt detects drift, not a same-UID attacker (`:120-130`).

**Two amendments matter to a redesign.** The 2026-08-14 prospective amendment records the operator
selecting a **versioned GitHub release archive** installed with `mise use -g
github:Codeseys-Labs/agentic-sdlc`, noting the GitHub backend installs **one release artifact** and
**does not import this repository's `[tools]` table**, so the archive must carry `ccodex`, the
payload, and its private runtime dependencies, resolve its root relative to its executable, and
**copy** activated host entries so pruning an old mise version cannot break them; ADR-0011 remains
the current install decision until builder, workflow, copy activation, clean-host tests and first
release exist (`:148-165`). The 2026-08-24 amendment records that the prerelease now exists (v0.7.3
tag `4c7f7c2`, archive sha256 `fc820fc2…711349`; `v0.7.4` first carrying `bin/ccodex`), that
container proof re-hashed 231/231 manifest entries and ran a 26/26-digest activation journey, that
the **unversioned `mise use -g` form fails** for two measured reasons (prerelease exclusion and
mise's `minimum_release_age` filter) and stays unclaimed, and that mise exposed the whole `scripts/`
directory as the tool's bin path until `bin/ccodex` was committed (`:182-195`). It also states
ADR-0021 remains proposed because **runtimes are auto-installed from the tree's pins, not packaged,
and its self-contained-artifact legs are unexecuted** (`:201-203`).

### ADR-0017 — Make Claude Code the primary product host (accepted, 2026-08-15)

**Operative decision.** Agentic SDLC is the product ("A Claude Code-first, evidence-driven SDLC
harness…"); **Core runs through ordinary Claude Code and the operator's own account, requiring no
gateway, external provider, or companion library**; **`ccodex` is the operator CLI, not a second
product brand**, and OCX is an optional routing dependency used only by the routed-model profile;
other hosts are companion hosts with no equal-parity promise (`docs/adr/0017-...:32-39`).

**Stated reasons.** The repo presented two incompatible identities (`VISION.md:3` vs
`README.md:3-5`/`AGENTS.md:3-6`), and treating every host as a peer made the first journey ambiguous
and created an unproven parity obligation (`:11-16`). Rejected alternatives: provider-neutral
multi-host (hides the primary substrate, creates parity obligation) and replacing Claude Code with
a new agent runtime (duplicates the host, enlarges trust surface) (`:22-28`). It narrows ADR-0005's
default-install posture to optional while leaving ADR-0005's launcher/qualification constraints in
force (`:63`).

### ADR-0019 — Require fresh human authorization for every effect (accepted, 2026-08-15)

**Operative decision.** Every effect requires a **current, operation-specific** human authorization
bound to the exact plan digest, target, prestate, scope, routes, egress, budgets, evidence and named
effect; a changed bound value expires the grant; no agent, gate, queue record, ADR, receipt or model
output may create or broaden authority; **fan-in and outward publication are separate authorization
boundaries**; auto mode may consume only transitions already named in an approved envelope; controls
are labeled mechanical/observed/advisory (`docs/adr/0019-...:28-40`).

**Stated reasons.** Plans, reviews, gates and receipts are useful evidence but none answers whether
a mutation may occur now against the current target; treating a green gate as permission would let
stale or substituted evidence authorize a different effect (`:10-13`). Compliance requires every
effectful command to name the authorization it consumes and the exact effect it may perform
(`:66-70`).

### ADR-0020 — Admit only exact verified execution dependencies (accepted, 2026-08-15)

**Operative decision.** Every dependency carrying a gate, lifecycle, dispatch, render or recovery
verdict resolves to an **exact version or immutable identity through a reviewed front door**;
requests and configuration are not execution proof (read back effective identity where exposed);
ambiguous/unpinned/substituted dependencies block only the surface that needs them with named
diagnostics; **ordinary commands never silently resolve, install, update, replace, or fall back —
refresh is a separate reviewed lifecycle operation**; foreign files/libraries/credentials stay under
their owner's lifecycle (`docs/adr/0020-...:27-38`).

**Stated reasons.** A name on PATH, a catalog row, a package version, or a successful request does
not prove which bytes or model did the work (`:10-13`). Rejected: trusting ambient executables and
provider defaults (caller state can substitute a binary/model/registry without changing the command
name) and vendoring everything (transfers licence/update/credential obligations and cannot vendor
hosts or models) (`:17-24`). Compliance forbids selecting a readiness-dependent executable from
ambient PATH and forbids silent fallback (`:66-70`).

### ADR-0021 — Distribute Agentic SDLC as a versioned mise release (**proposed**, 2026-08-15)

**Operative decision (target, not current).** The primary operator distribution is a **versioned,
self-contained release acquired and selected through mise**, with source checkouts remaining the
customization/contribution/gate/release-building plane; the release installs **one** operator CLI,
`ccodex`, whose `sdlc` namespace acquires/activates/inspects/updates/recovers/removes lifecycle
state; **installing `ccodex` does not activate a repository, trust configuration, install a
companion library, configure a provider, start OCX, or launch Claude Code**; stable and preview
releases resolve to exact side-by-side identities with receipt-backed update/downgrade/rollback and
**no self-updater in the first release**; existing foreign or modified destinations are preserved
and reported (`docs/adr/0021-...:30-42`).

**Stated reasons.** Daily use is currently coupled to a checkout (`assets/launchers/ccodex.in:18-29`
cited at `:11-12`). Rejected: keeping the managed checkout as the only operator installation, and
**"Use a self-updating standalone binary… Rejected for the first release because it creates a second
update authority before the receipt-backed lifecycle is proven"** (`:22-27`). Named negatives: the
release must package private runtime dependencies without depending on a prunable release root, and
the two planes coexisting increases lifecycle and test-matrix cost (`:52-56`). It stays proposed
until ADR-0011's supersession condition fires (`:44-45`, `:57-59`).

### ADR-0022 — Activate repositories through digest-approved plans (accepted, **amended 2026-08-22**)

**Operative decision (as it survives).** Items 4, 5, 6 stand and are carried by
`skills/agentic-sdlc/tools/instruction-generator.py`: greenfield/brownfield/refuse-and-ask
classification decided by occupied operating-contract surfaces rather than repository age; **Seeds
is the default authoritative queue**; `AGENTS.md` is canonical host-neutral guidance projected into
an owned `CLAUDE.md`, with foreign guidance preserved (`docs/adr/0022-...:4-10`, `:44-51`,
`:134-142`). Items 1, 2, 3, 7 — the transaction engine, the tracked `.agentic-sdlc/repo.toml`, the
machine-local activation receipt, and the write-ready/remediation-ready vocabulary — **are deleted
and must not be cited as current requirements** (`:4-10`, `:90-98`).

**Stated reasons for the amendment (three measured facts).** The machine-local receipt never had a
reader: 70 records in 151 orphan directories keyed to `/tmp` fixtures, and the tool that activates
repositories never activated the repository shipping it (`:100-108`). Approve-and-write **in one
invocation** removes the window the plan digest was closing, so `apply --target --manifest --entry`
renders against the live target, prints the diff, and writes only with `--yes`; only `O_NOFOLLOW`
and temp+`os.replace`+parent-fsync survive (`:110-120`). The hand-rolled classifier refused every
ordinary (`git gc`'d) clone; the replacement asks git in a sanitized environment (`:122-132`).
Honest loss: no replayable plan artifact, no independent machine readback, no `remediation-ready`
(`:143-150`). Ask-by-default is the policy being protected — a verdict authorizes nothing
(`:136-140`).

### ADR-0025 — Compile execution from immutable planning artifacts (**superseded by ADR-0030**)

**Operative decision (historical).** Mission intent, repository snapshot, compiled wave plan, plan
diff and bounded auto grant were to be separate immutable versioned artifacts; a deterministic
read-only compiler with no model/repo/queue/network capability produces an execution candidate;
admission binds exact artifact digests; drift is classified into four kinds with scope and authority
changes returning for human disposition; human approval is the default and auto mode runs only
inside an explicit `AutoEnvelope`; resume revalidates bound state and never invents continuity
(`docs/adr/0025-...:30-43`).

**Stated reasons.** A single mutable plan document or chat thread lets drift hide as "continuation"
and lets auto mode broaden itself without a new approval (`:10-17`). **Status caveat:** superseded
by ADR-0030 (`:3`); per ADR-0028 the surviving rule is the scope/authority human-disposition rule
inside the sealed mission contract's stop conditions (`docs/adr/0028-...:55`). Anyone designing an
install UX around plan digests should note both this supersession and ADR-0022's deletion of the
activation plan digest.

### ADR-0027 — Admit compatibility through capability evidence above published minimums (accepted, 2026-08-15)

**Operative decision.** Each surface publishes a minimum host/feature requirement (Core: Claude Code
2.1.154 with Dynamic Workflows effectively enabled); meeting a minimum makes a tuple **eligible for
assessment only**, with safety-dependent use still requiring the surface's current versioned
capability canaries; **exact Agentic SDLC release, host version, OS and architecture, runtime
boundary, acquisition plane, capability evidence and optional-profile versions form one
compatibility tuple**, tiered `certified` / `capability-qualified` / `experimental` /
`unsupported`, and **no tier is inherited** across Core, profiles, platforms, installation methods,
renderers or companion hosts (`docs/adr/0027-...:32-45`).

**Stated reasons.** An exact tested set becomes a hard ceiling; a broad `>=` claim treats vendor
eligibility as proof that every required behavior works (`:11-15`). Negatives accepted: release prep
needs both offline matrix gates and separately authorized live capability journeys, and a
vendor-supported host may be labeled experimental until this product's own evidence exists
(`:50-56`). Conformance is **not yet mechanically checkable** — the matrix and fixtures do not
exist (`:57-60`).

### ADR-0028 — Organize the Claude Code-first product boundary as one initiative (**proposed**, 2026-08-15)

**Operative decision.** ADR-0017 through ADR-0027 plus later records declaring `Part-Of: ADR-0028`
form one initiative; each child keeps its own status, evidence, options and reversal condition; this
record supplies only the registry and sequencing view and its rollup is "evidence about decision
progress, never product completion or authority" (`docs/adr/0028-...:36-42`). The registry marks
ADR-0021 proposed (`:51`), ADR-0022 amended (`:52`), ADR-0025 superseded (`:55`); the rollup states
**ADR-0021 keeps the whole initiative proposed until its release evidence exists** (`:60-71`), and
sequencing item 7 says ADR-0021 "remains proposed until ADR-0011's release-artifact reversal
condition fires; it does not block specification of the Core journey in a development checkout"
(`:84-85`).

**Stated reasons.** One combined ADR would give eleven choices one status and one reversal
condition; loose pairwise links would hide the critical path and let a downstream record look ready
while a load-bearing parent stayed proposed (`:17-20`, `:26-33`). Explicit compliance rule: **"A
proposed child is not presented as a current product constraint"** (`:112`).

### ADR-0031 — Keep ccodex on bash and Python; harvest one Bun-compiled classifier (accepted, 2026-08-23)

**Operative decision.** `ccodex` **stays bash-plus-Python**; **no full or partial rewrite of the
installer, updater, or launcher into Bun (or Go)** — the Go orchestrator-TUI idea is retired in the
same record, that capability class being served by operator-installed external tools through their
own front doors per ADR-0009/ADR-0029, never vendored (`docs/adr/0031-...:75-79`). **One** harvest
is approved: the settings-bypass classifier as a Bun-compiled helper invoked by the existing bash
launcher, after the demolition ranks land, under ten mandatory preconditions (`:80-96`). The
capability reference for reconsideration is the dated survey (`:97-99`).

**Stated reasons.** Five measured facts, detailed in section (c) below (`:20-71`).

### `docs/plans/2026-08-14T163833Z-Install-UX.md` — the Install-UX plan (record of a future contract)

**Operative content.** A distribution contract in two planes: a primary quick install
`mise use -g github:Codeseys-Labs/agentic-sdlc` yielding a global `ccodex` with no checkout, no
`mise trust`, and no contributor toolchain, followed by an **explicit** second command
`ccodex bundle install --agent claude` (`:14-32`); and the managed checkout retained for
customization, contribution, gates, and release building (`:36-52`). It specifies a self-contained
archive shape with `bin/ccodex` plus `libexec/agentic-sdlc/{assets,agents,commands,policy,scripts,skills,manifests,runtime/{node,python,jq,opencodex,seeds,mermaid}}`, a distribution root resolved
relative to the executable, and **"`ccodex` should not grow a second self-updater"** (`:56-82`).
It splits runtime versus contributor tooling in a table (`:86-102`), refuses to restore the mermaid
mise pin and routes rendering through `ccodex mermaid render` with a Linux-x64-only certification
boundary (`:106-139`), makes **git and curl required host capabilities rather than silently
bundled** with a read-only `ccodex doctor` preflight (`:141-165`), mandates **copy** activation so
`mise prune` cannot break Claude's linked skills (`:168-193`), records a bridging local-acquisition
placement (`:195-219`), gives a 12-step implementation sequence (`:221-243`), and closes with
feasibility evidence and a `DONE_WITH_CONCERNS` verdict limiting the first supported quick install to
Linux x64/WSL (`:245-259`). Its own record status says it describes future behavior and that
ADR-0011 remains the current decision (`:261-267`).

**Stated reasons.** The mise constraint at the top: `mise use -g` installs **and globally
activates**; `mise --locked install` does not activate outside the checkout; and **"Making
`mise --locked install` globally modify PATH or Claude Code configuration would require a hidden
postinstall mutation. We should not do that."** (`:3-8`). A single GitHub-backend tool **cannot
import the repository's `[tools]` table or install transitive mise tools**, which is why the release
must be self-contained (`:56`). Activation must be copies because version-specific mise directories
are prunable (`:185`). Git/curl stay host capabilities because no stable ordinary registry entry
exists, `pkgx:` is experimental and adds another ecosystem, and bundling git drags in TLS,
credential-helper, CA-store and system-configuration concerns (`:143-147`).

### `docs/research/2026-08-23-bun-cli-capability-survey.md` — Bun capability reference (reference only)

**Operative content.** Explicitly "reference material only… supports ADR-0031… the decision **NOT**
to rewrite ccodex in Bun. Nothing here is a recommendation to migrate" (`:3-6`). It enumerates the
language-independent ccodex contracts any migration must preserve: the 0/1/2/3/4 exit ladder,
digest-as-approval, XDG receipts, sealed receipts hashed over canonical bytes, symlink install
lifecycle with refuse-to-clobber-by-digest, refusals never printing credentials,
environment-allowlist child spawn, and deterministic git-archive release artifacts verified by
manifest re-hashing (`:9-18`). Four load-bearing facts: **no digest pinning for cross-compiled
runtimes** (zero `sha512|integrity|checksum` matches at tag `bun-v1.4.0`; verification PR #36173
open) (`:44-52`, `:358-366`, `:386-396`); a **live macOS signing regression fixed only on `main`**,
in no release (`:53-56`, `:236-254`); **Bun-native file APIs violate the durability/atomicity
receipts require** — `Bun.write` non-atomic, non-durable, follows symlinks, ignores `mode`
(`:57-59`, `:527-536`); and **undocumented exit/signal semantics** with observed silent-exit-0 and
signal mangling (`:60-61`, `:270-283`). Compile output is **non-reproducible [measured]** — three
identical-input builds, pairwise-distinct sha256, first difference at offset 82,481,180
(`:197-202`). Compiled-binary sizes measured at 63.9–88.8 MB per target (`:194-196`). Compiled
binaries **autoload cwd `.env` and `bunfig.toml` by default** (`:117-120`) and `BUN_BE_BUN` /
`BUN_OPTIONS` can repurpose the binary or splice argv from the environment (`:121-128`). No armv7 or
any 32-bit target exists at the type level (`:782`). §5's gaps table and §6's revisit-trigger
checklist enumerate everything unresolved (`:780-826`, `:832-908`).

**Stated reasons.** Method is nine fetcher reports plus two on-host corpora, with `[measured]`
claims executed on Bun 1.4.0 rev `34cbb9a4` on Linux x64 (WSL2), nothing run on macOS or native
Windows, and both `/tmp` corpora ephemeral (`:20-30`).

### `docs/research/2026-08-22-overengineering-audit.md` — seven-agent overengineering audit

**Operative content.** Verdict "decisively overengineered": 210,528 tracked lines delivering 4,309
lines of payload (46:1), 89,515 test lines testing machinery and zero testing whether a skill is any
good; roughly 3–5k lines are real controls and roughly 75,000 are not (`:12-19`). Five ranked
deletions totalling ~75,500 lines (~36% of the repository) with payload untouched, each carrying its
ADR supersession and seed re-dispositions (`:21-31`) — rank 3 replaces the release-candidate
acquisition engine with a `git archive` builder (~120 lines), a tag-release CI job (~30 lines), a
mise github/http backend entry in `mise.lock`, and a receipt shim that re-hashes the resolved root
against `manifest.json` (`:27`). **"Bun rewrite: no. Harvest one component later."** (`:34-49`).
Sequencing: merge first, then rank 1 (the macOS platform fix), then the digest-pinned Bun classifier
helper, then feature branches from a ~135k-line main (`:52-62`).

**Stated reasons.** The diagnosis is "disciplined machinery defending adversaries its own docstrings
disclaim… on platforms where its witnesses measurably carry no information (20/20 btime collisions
on the CI runner)" (`:16-19`). For Bun: the spike killed the premise empirically — the Windows argv
defect reproduces identically in the compiled binary, and the rewrite would have shipped that same
bug plus a 370 MiB five-platform artifact versus 120 KB of bash, an unpinned compile-runtime supply
chain (>99.99% of executed bytes), an unowned macOS signature, a `strip` landmine, no armv7, and
2.8× slower startup, for a real saving of ~400 lines (`:34-43`).

### `docs/research/2026-08-08-fresh-host-install-verification.md` — fresh-host install verification

**Operative content.** Executed Docker verification on `ubuntu:24.04` as non-root with only curl,
git, ca-certificates plus mise and Claude Code, against commit `6551020` cloned from the public
remote; 32 of 33 scripted assertions passed, the one failure being a test defect, and two real
product defects found by pushing past the script (`:9-16`). The install path that works is six
steps: mise (+ Claude Code), clone, **review then `mise trust ./mise.toml`**, `mise --locked
install` (~1.3 GB, 13 tools), `mise run bundle:install` / `bundle:status` (expect `38 ok, 0
conflict, 0 absent`), `mise run operator-tools:install`, then `ccodex --help` **without mise on
PATH** (`:30-59`). Two facts flagged as easy to get wrong: **`uv` must stay reachable on the
operator's PATH** because the dispatcher's Python entrypoints run through it, and the
untrusted-config refusal was asserted positively so the trust step is load-bearing, not ceremonial
(`:74-77`). Defect 1: `jq` was an undeclared runtime dependency of the configure classifier —
pinned in `mise.toml` but absent on the no-mise PATH `ccodex` promises — producing a refusal that
named the wrong cause; fixed, and later re-hardened after seed `agentic-sdlc-6f9d` because
preferring an ambient `jq` over the pin is the substitution **ADR-0020 forbids** (`:115-175`).
Defect 2: the muse setup sequence needs more steps than documented and the wrong order fails
silently; the order itself was later superseded (`:187-224`).

**Stated reasons / transferable findings.** The test suite symlinked the host's `jq` into the stub
bin dir, so it agreed with the developer's machine and disagreed with a fresh install (`:177-185`).
The methodological rule: every assertion reads **output**, never a bare exit code, because on any
path ending in a `claude` process `exit 0` cannot distinguish "printed usage" from "launched Claude
Code" (`:249-260`). Not verified: native Windows or macOS, interactive TTY paths, long-run
stability, Seeds bootstrap (`:26-28`).

### `docs/research/2026-08-07-clone-free-install.md` — can this be mise-installed globally without cloning?

**Operative content.** Answer: **no, not for the bundle** — the clone can be managed for the
operator but not eliminated, for structural reasons in this repository rather than a gap in mise
(`:6`). Executed refutations: a plain HTTPS URL in `task_config.includes` resolves **zero tasks and
exits 0** — "the worst failure mode found: it looks like it worked" (`:16-32`); `mise run <url>` is
rejected outright and `MISE_OVERRIDE_CONFIG_FILENAMES=<url>` produced nothing (`:34-40`);
experimental `git::` includes **clone** (6.9 MB working tree with intact `.git` at `19f56f9`),
parse against the **task-file** schema so `[settings]`/`[tools]`/`[tasks.x]` are unknown fields,
**carry tasks only — never `[tools]`**, and run tasks in the caller's cwd (`:42-117`); no backend,
bundle, plugin-repo or registry mechanism applies (`:119-127`). The clone-dependency map records
six `__file__`-anchored entrypoints with no override flag, live symlink pointers plus absolute-path
ownership records, `mise -C "$root"` re-entry at run time, run-time tree reads by the mermaid
renderer, and every task tree-coupled — with **exactly two** genuinely clone-free surfaces: the
installed statusline copy and the Claude marketplace plugin plane (`:128-187`). Container transcript:
`mise --locked install` 0 in one run (13 tools, 104 s), `mise run check` 0 (694 tests, 326 s),
`bundle:install` 0, `bundle:status` `38 ok`, and the installed skill symlink resolving **into** the
managed clone (`:226-264`).

**Stated reasons.** Method was execution, not doc reading (`:5`). Alternatives lost for named
reasons: `git::` includes refuted by execution; `mise use -g` plus fetch gives "a pinned toolchain
with nothing to run"; `curl | bash` executes unread bytes against a review-before-trust posture; a
bare two-liner clobbers or half-updates on re-run (`:189-205`). Integrity stated honestly: HTTPS
authenticates transport not contents, `--depth 1` leaves one commit of history, and the receipt does
not detect a same-UID racer (`:218-223`).

---

## (b) Support / conflict / neutral matrix

Proposal elements, restated compactly:

- **P1** — mise installing the remote installs the deps (lefthook, betterleaks, uv, bun, node/npm,
  seeds, git, …) **and** the `ccodex` CLI.
- **P2** — the `ccodex` CLI installs Agentic SDLC in its entirety (as a plugin / collection of
  agent-CLI artifacts) into the target agent CLI (Claude first), at **user or project-local** scope.
- **P3** — the open question: is this better, or is ccodex-cli not fit for it?
- **P4** — a whole **Bun 1.4 rewrite** of ccodex-cli for cross-platform abstractions, performance,
  a compiled binary that packs all Agentic SDLC files/scripts/plugins into the bundle, plus
  **self-update**.

Legend: **SUPPORTS** = the decision already points this way; **CONFLICTS** = the decision forbids
it, or forbids it in the shape proposed; **NEUTRAL** = no bearing (or bearing only via a status
caveat). Where a cell is mixed, the qualifier is the operative part.

| Decision (status) | P1 mise installs deps + ccodex | P2 ccodex installs everything into Claude (user/project) | P3 is ccodex-cli fit? | P4 Bun 1.4 compiled rewrite + self-update |
|---|---|---|---|---|
| **ADR-0002** mise single front door (accepted) | **SUPPORTS** the "one front door" half (`:45-49`); **CONFLICTS** with `git` in the dep list — a required system package is a second bootstrap prerequisite (`:88-91`, `:142-151`), and with any pin whose install extracts archives/downloads browsers (`:142-151`) | NEUTRAL on scope; **SUPPORTS** keeping activation out of the install command (a pin's blast radius is the bootstrap command, `:110-116`) | **SUPPORTS**: a CLI that performs activation separately is compatible with keeping prerequisite count at one | **CONFLICTS in shape**: a Bun-compiled artifact fetching its own compile-target runtime from `registry.npmjs.org` unverified is the "no checksum substitute" case the reversal condition demands a new ADR for (`:167-173`) |
| **ADR-0005** opencodex by default (accepted, partly superseded) | **SUPPORTS**: opencodex is already a default mise pin in the convenience tier (`:123-127`) | NEUTRAL | NEUTRAL | **CONFLICTS weakly**: the launcher's fail-closed supervision, re-probed health verdicts, and refusal contract must survive any port (`:143-157`) |
| **ADR-0011** managed clone (accepted; 2026-08-14 + 2026-08-24 amendments) | **CONFLICTS as literally stated**: the GitHub backend installs **one artifact** and does **not** import the repo's `[tools]` table (`:156`); remote task/tool composition was refuted by execution (`:20-36`). **SUPPORTS** the "mise installs `ccodex`" half — that is executed evidence as of v0.7.4 (`:182-195`) | **SUPPORTS**: copy activation of host entries is the recorded shape, and host-plane activation is a **separate collision-checked operation** (`:156-157`) | **SUPPORTS**: `ccodex` self-locating from a release tree is executed (`:190-195`) | NEUTRAL on language; **CONFLICTS** with "pack everything into the bin" today: runtimes are auto-installed from the tree's pins, not packaged (`:201-203`) |
| **ADR-0017** Claude Code primary host (accepted) | NEUTRAL | **SUPPORTS**: Claude-first activation with companion hosts receiving no parity promise (`:32-39`) | **SUPPORTS**: `ccodex` is *the* operator CLI and "not a second product brand" (`:34-35`) | **CONFLICTS with the framing**: a compiled multi-platform `ccodex` that becomes its own product surface strains "not a second product brand"; the rejected option "replace Claude Code with a new general agent runtime… duplicates the host, enlarges the trust surface" is the nearest analogue (`:24-26`) |
| **ADR-0019** fresh authorization per effect (accepted) | **CONFLICTS** with any install that also mutates host config: acquisition and activation are separate effects each needing a current operation-specific grant (`:28-33`) | **SUPPORTS** if each write is separately authorized and prestate-bound; **CONFLICTS** with an "installs it in its entirety" single unbounded grant (`:28-33`, `:66-70`) | **SUPPORTS** a CLI whose verbs each name their authorization | **CONFLICTS** with self-update: an updater that follows a moving release is an effect without a fresh grant, and "no… model output may create or broaden authority" (`:30-31`) |
| **ADR-0020** exact verified dependencies (accepted) | **SUPPORTS** pinning every dep through a reviewed front door (`:27-29`); **CONFLICTS** with any leg that resolves a dep from ambient PATH (`:66-67`) | **SUPPORTS**: foreign/modified destinations stay under their owner's lifecycle (`:37-38`) | **SUPPORTS** | **CONFLICTS twice**: "ordinary commands never silently resolve, install, update, replace, or fall back… refresh is a separate reviewed lifecycle operation" (`:36-37`) kills silent self-update; and an unpinnable embedded compile-target runtime fails item 1 (`:27-29`) |
| **ADR-0021** versioned mise release (**proposed**) | **SUPPORTS** the topology (mise resolves a versioned release installing one `ccodex`, `:30-34`); **CONFLICTS** with mise installing the dep set transitively — the release must **package** private runtime deps itself (`:52-54`) | **SUPPORTS** `ccodex sdlc` owning acquire/activate/inspect/update/recover/remove (`:33-35`); **CONFLICTS** with bundling activation into installation: "Installing `ccodex` does not activate a repository, trust configuration, install a companion library, configure a provider, start OCX, or launch Claude Code" (`:36-38`) | **SUPPORTS**: `ccodex` is exactly the intended vehicle | **CONFLICTS head-on**: "Use a self-updating standalone binary. **Rejected** for the first release because it creates a second update authority before the receipt-backed lifecycle is proven" (`:24-26`) and "The first release has no self-updater" (`:41`) |
| **ADR-0022** activation lifecycle (accepted, amended) | NEUTRAL | **SUPPORTS project-local scope conceptually**: repository activation is a real, surviving surface (classify → shown diff → `--yes` apply, `AGENTS.md` canonical + owned `CLAUDE.md`, foreign guidance preserved) (`:110-120`, `:134-142`); **CONFLICTS** with "spray one standard scaffold into every repository" (`:29-31`) and with reviving the deleted plan-digest/receipt machinery (`:4-10`) | **SUPPORTS**: ask-by-default, one-invocation diff-then-write is the current shape a CLI should reuse | NEUTRAL |
| **ADR-0025** immutable planning artifacts (**superseded by ADR-0030**) | NEUTRAL | NEUTRAL (do **not** cite its digest-bound artifacts as a current constraint; `:3` and `docs/adr/0028-...:55`) | NEUTRAL | NEUTRAL; its surviving scope/authority human-disposition rule applies to any redesign that changes scope mid-flight |
| **ADR-0027** capability evidence above minimums (accepted) | **SUPPORTS**: acquisition plane is an explicit tuple axis (`:38-40`) | **SUPPORTS**: installation methods never inherit one another's tier (`:41-43`) | NEUTRAL | **CONFLICTS with the "cross-plat" premise**: each OS/arch/acquisition-plane combination is its own tuple needing its own evidence; "cross-platform abstractions" buys no compatibility tier (`:38-43`, `:74-76`), and the Install-UX plan already limits the first quick install to Linux x64/WSL (`docs/plans/...:137`, `:259`) |
| **ADR-0028** one initiative (**proposed**) | NEUTRAL, with a governance constraint: the target topology's parent (ADR-0021) is proposed, so it is not a current product constraint (`:112`) | NEUTRAL (same caveat) | NEUTRAL | **CONFLICTS procedurally**: ADR-0021 is the record any Bun-packaged distribution would have to amend or supersede, and it cannot be treated as settled while proposed (`:60-71`, `:84-85`) |
| **ADR-0031** keep bash+Python (accepted, 2026-08-23) | NEUTRAL | NEUTRAL — it explicitly leaves "nothing else about the distribution topology (ADR-0021: mise → versioned release → one `ccodex` CLI → per-host install)" changed (`:137-139`) | **SUPPORTS ccodex-as-vehicle**, in its current languages | **CONFLICTS directly and by name**: "No full or partial rewrite of the installer, updater, or launcher into Bun" (`:75-76`), plus three conjunctive revisit triggers (`:101-112`) and an explicit burden on re-proposers to "show which measured fact changed" (`:141`) |
| **Install-UX plan** (2026-08-14, future contract) | **SUPPORTS** the quick-install command shape (`:14-24`); **CONFLICTS** on deps: a GitHub-backend tool "cannot import the repository's `[tools]` table or install transitive mise tools" (`:56`), and **git/curl are required host capabilities, not bundled** (`:141-147`) | **SUPPORTS** strongly: `ccodex bundle install --agent claude` as the explicit second command with collision checks, ownership records, dry run, status, uninstall (`:26-32`), copy activation to survive `mise prune` (`:185`); **CONFLICTS** with folding activation into the install (`:3-8`) | **SUPPORTS**: this plan *is* the ccodex-as-installer design | **CONFLICTS** on self-update: "`ccodex` should not grow a second self-updater" (`:82`); **partially SUPPORTS** the packing idea via `libexec/.../runtime/` (`:56-78`) but bounds it (mermaid browser stays an explicit provision step; ~358 MiB + ~446 MiB would make a "quick" artifact very large, `:133-137`) |
| **Bun survey** (2026-08-23, reference only) | NEUTRAL | NEUTRAL | NEUTRAL | **CONFLICTS**: it is the evidence base *for* the no-rewrite decision (`:3-6`, `:44-61`), and it enumerates the contracts a port must preserve (`:9-18`) plus ~40 UNKNOWNs (`:780-826`) |
| **Overengineering audit** (2026-08-22) | **SUPPORTS** simplification pressure generally, and rank 3 explicitly replaces the acquisition engine with `git archive` + a tag-release CI job + a mise github/http backend entry (`:27`) | **SUPPORTS** shrinking install-lifecycle layers to the `install_operator_tools.py` shape (`:28`) | **SUPPORTS**: fewer, thinner install layers | **CONFLICTS**: "Bun rewrite: no. Harvest one component later." (`:34-49`) |
| **Fresh-host verification** (2026-08-08) | **SUPPORTS** a dep-provisioning front door: the six-step path works from nothing, but needs mise trust + `mise --locked install` (~1.3 GB, 13 tools) (`:30-59`); **CONFLICTS** with "ccodex needs no runtime deps on PATH" — `uv` must stay reachable (`:74-76`) | **SUPPORTS**: `bundle:install` + `bundle:status` (`38 ok`) is the working activation leg (`:50-53`) | **SUPPORTS with a warning**: the `jq` defect is exactly the failure mode of a CLI promising to run without mise while depending on mise-pinned tools (`:115-144`) | **NEUTRAL-to-SUPPORTS**: a self-contained binary would have avoided the `jq`-on-PATH class — but the recorded fix was pinned resolution, not a language change (`:164-175`) |
| **Clone-free install research** (2026-08-07) | **CONFLICTS** with the transitive-deps premise: includes "carry tasks only — never `[tools]`" (`:100-104`), a URL include silently resolves zero tasks at exit 0 (`:16-32`), and no bundle/plugin-repo backend exists (`:119-127`) | **SUPPORTS** the direction: exactly two surfaces are genuinely clone-free today, one of them the Claude marketplace plugin plane (`:176-181`) | **SUPPORTS**: it is the origin of "the bootstrap can be clone-free… the bundle cannot be tree-free" (`:183-184`) | NEUTRAL on language; the `__file__`-anchoring and symlink-ownership coupling it maps (`:128-187`) is the work any packed-binary design must undo |

### Reading of the matrix

- **P1 is half-decided and half-refuted.** "mise installs `ccodex`" is executed evidence
  (`docs/adr/0011-...:182-195`; `README.md:266-272`). "mise installs the deps as part of that" is
  refuted by two independent recorded mechanisms: a `github:`-backend tool install imports no
  `[tools]` table (`docs/adr/0011-...:156`; `docs/plans/...:56`), and remote task includes carry no
  `[tools]` either (`docs/research/2026-08-07-...:100-104`). The two legal routes are (i) **package**
  the runtimes in the archive (ADR-0021's named negative, `docs/adr/0021-...:52-54`; the plan's
  `libexec/.../runtime/` shape, `docs/plans/...:56-78`) or (ii) **resolve them from the acquired
  tree's own pins after an explicit `mise trust`**, which is what ships today (`bin/ccodex:24-27`,
  `:114-137`). `git` in particular is decided the other way: a required host capability with a
  named preflight (`docs/plans/...:141-163`), reinforced by ADR-0002's system-package prerequisite
  class (`docs/adr/0002-...:88-91`).
- **P2 is largely already decided and partly already built** — see (d). The one genuinely new
  element is **project-local scope**: `scripts/install_skill_bundle.py` places Claude entries under
  `<claude-home>/.claude` (`:302`, `:1801`), i.e. user scope only, and the project surface today is
  ADR-0022's `instruction-generator.py` apply path. Nothing forbids project scope; nothing has
  decided it either.
- **P4 is the only element that collides with an accepted decision by name.** ADR-0031's Decision
  item 1 (`:75-79`) forbids exactly the proposed rewrite; ADR-0021 rejects a self-updating
  standalone binary and states the first release has no self-updater (`:24-26`, `:41`); the plan
  says `ccodex` should not grow a second self-updater (`:82`); ADR-0020 item 4 makes refresh a
  separate reviewed lifecycle operation (`:36-37`).

---

## (c) ADR-0031 in detail: why bash+python won, on what evidence, and what would have to change

### The proposal that was evaluated

"Rewrite `ccodex` — installer, updater, and launcher — as a single Bun-compiled CLI, on the premise
that Bun's built-in cross-platform APIs would remove the shell-script tax and the need for
platform-specific handling" (`docs/adr/0031-...:16-18`). This is materially the same proposal as
P4. It was "evaluated by building, not arguing": a **590-line spike** ported the launcher's security
core (settings-bypass classifier, jq resolver, argv assertions, env allowlist) to Bun, compiled it
for **twelve targets**, and was measured against the shipping bash on **2026-08-22, on Bun 1.4.0**,
alongside a surface map of what a full port would carry (`:18-22`).

### The five measured facts that decided it

1. **The motivating defect is not a bash defect** (`:24-31`). The Windows argv corruption behind 34
   CI failures **reproduced identically against the compiled Bun binary**: PowerShell 5.1's
   CreateProcess marshalling strips embedded double quotes for every native executable, so the
   binary received `{ultracode:true}` exactly as the bash path did. Going native **additionally**
   enters MSYS2 path mangling (`/usr/bin:/bin` rewritten to Windows paths) that a `.sh` invoked by
   bash never sees. The fix is quoting at the PowerShell crossing, in any language (seed
   `agentic-sdlc-7123`). *This is the decisive fact: the rewrite's headline benefit was measured to
   be zero for the defect that motivated it, and negative on one axis.*
2. **"One cross-platform CLI" inverts into five platform binaries** (`:33-40`). `bun build
   --compile` emits a separate **61–85 MB** executable per target — roughly **350 MiB per
   five-platform release against one 120 KB script** — with **no armv7 or 32-bit target at all**;
   musl builds do not run on glibc hosts; macOS signing regressed in 1.4.0 (Rust-rewritten signer
   produces binaries SIGKILL'd on macOS 27, oven-sh/bun#39764), so a real release needs its own
   Developer ID and notarization where the script needs none; and `strip`, present in ordinary
   release tooling, **destroys the binary while leaving `--version` answering exit 0**.
3. **The supply chain fails this repository's own bar** (`:42-47`). Cross-compile target runtimes are
   fetched from a hardcoded `registry.npmjs.org` with **no checksum verification at all** in 1.4.0
   (read from `src/options_types/compile_target.rs` at tag `bun-v1.4.0`), and nothing pins their
   digests — making **more than 99.99% of the bytes operators would execute unpinned**, in a
   repository whose validator pins a browser download by hash (ADR-0006). `bunfig.toml` and `.npmrc`
   registry settings are not honored on that path (oven-sh/bun#25713, open). Bun shipped 1.4 as its
   first release after a Zig→Rust rewrite, and the signing regression came from that rewrite.
4. **Compiled output is not reproducible** (`:48-56`). Three back-to-back `bun build --compile` runs
   over identical input produced identical-size binaries with **pairwise-distinct sha256 digests**,
   first differing byte at offset **82,481,180** in the embedded-graph tail. "This repository treats
   build determinism as a control it will not trade away — rank 3 of the demolition kept `git
   archive` specifically so a digest-named artifact keeps meaning what it says — and a compiled Bun
   artifact cannot offer it. A digest can only ever be pinned over the shipped bytes;
   rebuild-and-compare verification is impossible by construction."
5. **The tax being avoided does not exist** (`:57-65`). One `ccodex sdlc install` crosses **exactly
   one runtime seam**: bash `exec`s once into one mise-pinned Python interpreter, which loads every
   sibling by exact path; mise, already the sole bootstrap prerequisite, supplies that interpreter
   invisibly. The launcher's 2,025 bash lines are ~60 security-judgment functions plus **835 lines
   of measured forensics comments that any port carries verbatim**; the honest line saving measured
   at **~400**. The read-only enforcement in `ccodex_sdlc_readonly.py` patches the Python stdlib and
   **has no Bun equivalent short of a process-isolation redesign**. Most `sdlc` tests call
   `module.main()` in-process, so **a language swap orphans the suite that would have to prove the
   swap**.

**The performance argument split.** Startup **failed**: the compiled binary started **2.8× slower**
than bash parsing all 2,025 lines (24 ms vs 8.7 ms) (`:66-67`). Bun **won decisively on one thing**
— the settings gate itself: one execve and an in-process JSON parse against **six uncached `mise
exec -- jq` spawns, 130 ms → 24 ms**, retiring the two-regex-engine (ERE vs Oniguruma) agreement
burden and ADR-0020's whole jq-resolution problem, plus argv observability that turned a
mechanism-unknown CI failure into a ten-minute diagnosis (`:67-71`). That single win is the entire
scope of the approved harvest.

### Corroborating evidence outside the ADR

The audit records the same numbers independently ("370 MiB five-platform artifact (vs 120 KB of
bash)", ">99.99% of executed bytes", "2.8x slower startup", "the real line saving is ~400 because
835 bash lines are measured-forensics comments") and states the spike archive is preserved outside
the repo as `bun-cli-spike-20260822.tar.gz` in operator state
(`docs/research/2026-08-22-overengineering-audit.md:34-49`). The survey supplies the
per-target measured sizes (linux-x64 82,547,912 B; darwin-arm64 63.9 MB; darwin-x64 70.7 MB; musl
76.3 MB; windows-x64 88.8 MB) (`docs/research/2026-08-23-...:194-196`, `:797`), the determinism
measurement (`:197-202`, `:788`), the zero-checksum grep result at the tag (`:358-366`), the
`--compile-executable-path` bring-your-own-runtime escape as "the only supply-chain-tight option
today" (`:380-384`), the default-ON `.env`/`bunfig` autoload (`:117-120`, `:789`), the
`BUN_BE_BUN`/`BUN_OPTIONS` repurposing hazard (`:121-128`, `:790`), the `Bun.write`
non-atomicity/symlink-following/mode-ignoring measurements (`:527-536`, `:802`), the never-unlinked
`$TMPDIR/.<hash>-<index>.so` extraction per launch, closed `not_planned` (`:171-176`, `:819`), and
the armv7/32-bit absence at the type level (`:782`).

### What the decision actually permits

One harvest only: the settings-bypass classifier as a Bun-compiled helper **invoked by the existing
bash launcher**, after the demolition ranks land and the surface stabilizes, under **ten mandatory
preconditions** (`docs/adr/0031-...:80-96`): build against an out-of-band-verified runtime via
`--compile-executable-path` pinned by a repo-owned digest; treat #36173 as registry-integrity only,
never a substitute for a caller-owned pin; pin the helper's sha256 over the **shipped** bytes and
never promise rebuild-and-compare; build with `--no-compile-autoload-dotenv
--no-compile-autoload-bunfig`; scrub `BUN_BE_BUN` and `BUN_OPTIONS` from the helper's child
environment; resolve the embedded-runtime licensing obligation (JavaScriptCore LGPL + ICU data)
against ADR-0001's NOTICE posture before shipping; keep the refusal exit contract (0 clean, 2 usage,
3 refused, never 1 for a refusal); port the 835 forensics comments verbatim; print the argv received
on refusal paths; never ship through a packaging path that runs `strip`. The survey's §6 restates
these as an executable checklist (`docs/research/2026-08-23-...:878-908`).

Also retired in the same record: the **Go** rewrite around the "agent-manager" orchestrator pattern,
rejected without a spike because it shares every distribution cost (per-platform artifacts, signing,
supply chain) while adding a language the repo does not otherwise carry, with the orchestrator
capability available as maintained external prior art (claude-squad, Conductor, t3code)
(`docs/adr/0031-...:76-79`, `:123-128`). And "rewriting only the Python `sdlc` namespace in Bun,
keeping bash" was rejected as **the worst of both** — keeps the bash surface, adds the compile
supply chain, discards the import-based test suite, and removes a Python runtime mise already pins
invisibly (`:129-131`).

### What would have to change for an honest revisit

The ADR names **three conjunctive triggers, re-verified at that time, not assumed**
(`docs/adr/0031-...:101-112`):

1. **Bun pins or verifies its compile-target runtime downloads by digest.** The exact thing to watch
   is oven-sh/bun#36173 (check the downloaded tarball against registry `dist.integrity` before
   extraction); it was **open and unmerged as of 2026-08-23**, and it deliberately leaves a
   caller-supplied `BUN_COMPILE_TARGET_TARBALL_URL` unverified. Even merged, it is trust-npm
   registry integrity, **not** a local digest pin — "a ccodex-grade pin would still be the caller's
   job" (`docs/research/2026-08-23-...:386-396`).
2. **The post-demolition `ccodex` surface has been stable for at least one release.**
3. **The `sdlc` namespace is tested through its subprocess seam (argv in, receipts and exit codes
   out)**, so a language swap is a provable refactor rather than a bet — the C3 deepening candidate
   from the 2026-08-22 architecture review, "worth doing on its own merits."

Plus a re-measurement obligation, explicitly **not** inheritable: binary sizes and startup, the
macOS signing state (#39837 fixed on `main` two days after 1.4.0 shipped, so it is in **no release**
as of the record), the armv7 gap, `strip` behavior, and compile reproducibility
(`docs/adr/0031-...:114-118`). The survey's §6 adds concrete checks: is a 1.4.x point release out at
all, does it ship #39837 (run `test/bundler/compile-macho-codesign.test.ts` against the release
artifact — it **fails on 1.4.0**) and the mode-0600 fix #40112; is the malformed-`-vX.Y.Z`
silent-wrong-runtime selector (#37389) fixed; is `--parallel` stable (#40129, #39987, #39709); are
the exit-code fidelity defects closed (#26674 bunx swallows codes, #39787 Windows silent exit-0,
#35296 macOS signal table); are env-inheritance/Windows-quoting semantics pinned by test; are
error-output credential-hygiene tests in place (`docs/research/2026-08-23-...:832-876`).

**And a burden of proof, stated as a consequence:** "Anyone re-proposing a Bun or Go rewrite starts
from this record and the survey, and **must show which measured fact changed**"
(`docs/adr/0031-...:141`).

Two facts that would *not* by themselves satisfy the triggers, and are worth stating because P4
implies them:

- **Determinism cannot be fixed by waiting.** Non-reproducibility is a measured property of the
  compile output, and the ADR ties it to a control the repo "will not trade away" (`:48-56`).
  Reopening on this axis requires either Bun becoming reproducible or an explicit, separately
  recorded decision to trade that control away — which is a different ADR, not a revisit of this
  one.
- **"Cross-platform" is not a compatibility claim.** ADR-0027 makes OS/arch/acquisition-plane
  separate tuple rows with no inheritance (`docs/adr/0027-...:38-43`); five compiled binaries create
  five new evidence obligations rather than discharging one.

---

## (d) Is the operator's proposal already planned? Yes — most of it, and partly already built

### What the 2026-08-14 Install-UX plan already proposes

| Operator proposal | Already in the plan? | Where |
|---|---|---|
| mise installs `ccodex` from a remote release | **Yes, verbatim** — `mise use -g github:Codeseys-Labs/agentic-sdlc` as the primary quick install, with `ccodex` globally available, caller-workspace preservation, no checkout/trust/contributor toolchain | `docs/plans/...:14-24` |
| mise installs the dep set alongside it | **No — explicitly the opposite.** A GitHub-backend tool cannot import `[tools]` or install transitive mise tools, so the release must be self-contained; **git and curl are required host capabilities**, not bundled, with reasons | `:56`, `:141-147` |
| deps travel with the artifact (uv, bun, node, seeds, jq, ocx, python, mermaid) | **Yes, as packaged private runtimes** under `libexec/agentic-sdlc/runtime/`, with a runtime-vs-contributor split table (uv, lefthook, betterleaks, gh, ripgrep, fd, tests/gates = checkout only) | `:56-78`, `:86-102` |
| `ccodex` installs Agentic SDLC into Claude | **Yes** — `ccodex bundle install --agent claude` as the necessary **second** command, retaining collision checks, ownership records, dry run, status, uninstall | `:26-32` |
| activation survives version pruning | **Yes** — quick-install activation uses **copies**, not links into a version-specific mise directory; checkout mode keeps symlinks | `:185` |
| upgrade path | **Yes** — `mise upgrade …` then `ccodex bundle install --agent claude` to refresh owned host entries; versions live side by side so rollback is selecting the earlier release | `:82`, `:178-184` |
| self-update | **No — explicitly refused**: "`ccodex` should not grow a second self-updater" | `:82` |
| preflight / doctor | **Yes** — `ccodex doctor` verifying OS/arch, git, curl, `claude`, packaged OCX/jq/Python/Seeds/Mermaid identities, writable state dir, Claude host-plane collision status; `ccodex bundle install` runs it first and refuses with named remediation | `:149-163` |
| project-local scope | **Not addressed** | — |
| Bun/compiled binary | **Not addressed** (the plan predates the spike by 8 days) | — |

The plan also fixes boundaries a redesign must not casually reopen: no mermaid mise pin
(`:106-117`), the mermaid browser stays an explicit digest-checked provision step because ~358 MiB
browser + ~446 MiB `node_modules` "makes a 'quick' artifact very large" (`:133-137`), certified
rendering stays Linux x64 only (`:137`), and the first supported quick-install release should be
Linux x64/WSL (`:259`).

### Implementation-sequence status, checked against the tree today

The plan's 12-step sequence (`docs/plans/...:221-243`) versus what exists at HEAD:

| Step | Status | Evidence |
|---|---|---|
| 1. Land the portability patch separately | **UNVERIFIED** (no way to check from HEAD alone) | — |
| 2. Release-archive builder + structural tests | **Done** — `scripts/build_release.py`, `mise.toml:113-116` (`release:build`), payload allowlist in `policy/release-candidate.v1.json:1` | `scripts/build_release.py:10-17` |
| 3. Release-mode `ccodex` on a relative immutable root | **Done** — `bin/ccodex` self-locates (`root` = parent of its own `bin/`) | `bin/ccodex:2-19`, `:31-38` |
| 4. Copy activation, checkout links preserved | **Done** — `ccodex sdlc install --host claude` copy-activates transactionally, classifying `absent`/`owned`/`foreign`/`modified` before writing and preserving+naming foreign/modified entries | `scripts/ccodex_sdlc_install.py:2`, `:39-45` |
| 5. Package private node/OCX/Python/jq/Seeds-Bun/Mermaid | **Not done** — "No interpreter is bundled. `mise.toml`'s pinned uv supplies Python 3.12.11 to every entrypoint, so the archive carries authored bytes only"; ADR-0011's amendment says the same | `scripts/build_release.py:28-29`; `docs/adr/0011-...:201-203` |
| 6. `ccodex doctor` + mermaid routing | **Partial** — `ccodex sdlc doctor` exists as a read-only reader verb; **no `ccodex mermaid` route**, and maintenance tasks incl. mermaid are "deliberately absent" from the dispatcher | `scripts/ccodex_sdlc.py:39`, `bin/ccodex:73`, `:95-96` |
| 7. Tagged-release CI with platform archives, checksums, attestations | **Not done** — only `.github/workflows/{validate.yml,real-key-testing.yml}` exist | `.github/workflows/` |
| 8. Publish the first release | **Done, out of order** — v0.7.3 prerelease then v0.7.4; the amendment states this "amends the Install-UX plan's implementation order (its publish step ran before its steps 3, 5, and 7)" | `docs/adr/0011-...:182-201` |
| 9. Self-release pin in the checkout's locked tool graph | **Not done** — no `Codeseys-Labs` entry in `mise.toml` or `mise.lock` | `mise.toml`, `mise.lock` |
| 10. Supersede ADR-0011 | **Not done** — ADR-0021 is still `proposed` | `docs/adr/0021-...:3`, `docs/adr/0028-...:60-71` |
| 11. README puts the quick path first | **Partial** — README describes the current checkout distribution first and the prerelease quick install as EXACT-VERSION ONLY, with the unversioned form "not claimed to work" | `README.md:266-276` |
| 12. Credential-free clean-environment verification of 9 journeys | **Partial** — container proof on 2026-08-24 (mise `install` of the exact version, 231/231 manifest re-hash, 26/26-digest activation, clean post-uninstall status); the unversioned-`mise use -g` leg measured as failing and left unclaimed | `docs/adr/0011-...:182-195` |

### The answer to P3, from the corpus rather than from opinion

**ccodex-cli is the already-decided vehicle for P2, and is already doing it.** ADR-0017 makes
`ccodex` *the* operator CLI (`:34-35`); ADR-0021 assigns acquire/activate/inspect/update/recover/
remove to `ccodex sdlc` (`:33-35`); the plan assigns Claude activation to `ccodex bundle install
--agent claude` (`:26-32`); and both verbs exist today (`bin/ccodex:67-81`). So "is ccodex-cli fit
for that?" is answered affirmatively for P2 by three records plus shipped code.

**Where the proposal diverges from the decided design, it diverges on three specific points, each
already litigated:**

1. **Making acquisition also perform activation.** Forbidden by ADR-0021 item 3 (`:36-38`), by
   ADR-0019's per-effect grant rule (`:28-33`), and by the plan's opening constraint that making a
   mise install mutate PATH or Claude config "would require a hidden postinstall mutation. We
   should not do that." (`:3-8`). ADR-0002's amendment supplies the mechanical reason: a pin's blast
   radius is the whole `mise install` command, so one entry's postinstall failure exits the whole
   operation non-zero (`:110-116`).
2. **Making mise install the dep set transitively (including `git`).** Refuted mechanically
   (`docs/adr/0011-...:156`; `docs/plans/...:56`;
   `docs/research/2026-08-07-...:100-104`) and decided against for git/curl specifically
   (`docs/plans/...:141-147`). Note also the standing residual: `bin/ccodex` resolves tools through
   `mise -C <root>` and refuses at exit 3 on an untrusted root (`bin/ccodex:114-137`), and the fresh-host
   record's `jq` defect is the canonical instance of a CLI promising no-mise operation while
   depending on mise-pinned tools (`docs/research/2026-08-08-...:115-144`, `:164-175`).
3. **A Bun-compiled, self-packing, self-updating ccodex.** Forbidden by name by ADR-0031 (`:75-79`),
   with self-update independently rejected by ADR-0021 (`:24-26`, `:41`), the plan (`:82`), and
   ADR-0020 item 4 (`:36-37`).

### One genuinely open element

**Project-local scope** (P2's "user or project local scopes"). Nothing in the corpus decides it.
`scripts/install_skill_bundle.py` places Claude entries under `<claude-home>/.claude` with
`--claude-home` defaulting to the current home (`:302`, `:1801`), so today's activation is user
scope. The repository-scoped surface is ADR-0022's surviving classify-then-diff-then-`--yes` apply
over `AGENTS.md`/`CLAUDE.md` with foreign guidance preserved (`docs/adr/0022-...:110-120`,
`:134-142`), and ADR-0022's rejected option "spray one standard scaffold into every repository"
(`:29-31`) is the constraint any project-scope install must respect.

---

## Constraints checklist for any install-UX redesign (derived, with citations)

1. **One bootstrap prerequisite: mise.** No second package manager, env token, network credential,
   or system package, and every new pin verified credential-free on a minimal image before commit
   (`docs/adr/0002-...:45-56`, `:88-91`, `:142-151`).
2. **Acquisition ≠ activation ≠ trust ≠ provider config ≠ launch.** Five separate operations, each
   needing its own current human grant (`docs/adr/0021-...:36-38`; `docs/adr/0019-...:28-33`;
   `docs/adr/0011-...:92-97`; `docs/plans/...:3-8`, `:26-32`).
3. **No silent resolution, install, update, replacement, or fallback in ordinary commands;** refresh
   is a separate reviewed lifecycle operation (`docs/adr/0020-...:36-37`).
4. **No second update authority / self-updater** in the first release
   (`docs/adr/0021-...:24-26`, `:41`; `docs/plans/...:82`).
5. **Copy, don't link, on the release plane;** links stay on the checkout plane because source
   editability is that plane's point (`docs/plans/...:185`; `docs/adr/0011-...:156`).
6. **Exact identities, read back where the surface exposes them;** no ambient-PATH selection of a
   readiness-dependent executable (`docs/adr/0020-...:27-33`, `:66-70`; the `jq` case in
   `docs/research/2026-08-08-...:164-175`).
7. **Deterministic, digest-named release artifacts verified by manifest re-hashing**
   (`scripts/build_release.py:12-17`, `:31-36`;
   `docs/research/2026-08-22-overengineering-audit.md:27`;
   `docs/research/2026-08-23-...:17-18`).
8. **Foreign and modified destinations are preserved and named, never adopted or overwritten**
   (`docs/adr/0021-...:41-42`; `scripts/ccodex_sdlc_install.py:39-45`;
   `docs/adr/0022-...:140-142`).
9. **Per-tuple compatibility evidence; no inheritance across platform, arch, acquisition plane, or
   profile** (`docs/adr/0027-...:38-45`, `:74-76`); the first quick-install scope is Linux
   x64/WSL (`docs/plans/...:137`, `:259`).
10. **`ccodex` is the one operator CLI, Claude Code is the primary host, OCX is optional**
    (`docs/adr/0017-...:32-39`).
11. **Exit-code ladder and refusal semantics are contract**: 0 ok, 1 failure, 2 usage, 3 refused
    before effect, 4 admitted partial/unknown (`bin/ccodex:98-99`;
    `docs/research/2026-08-23-...:11`; `docs/adr/0031-...:93-94`).
12. **Superseding ADR-0011 requires the full named evidence set** (archive builder, release
    workflow, copy activation, clean-host tests, first release) and a **new** ADR rather than an
    edit (`docs/adr/0011-...:160-165`, `:167-176`; `docs/adr/0021-...:44-45`).
13. **A proposed record is not a current constraint** — ADR-0021 and ADR-0028 are proposed, so the
    release topology is a target, not an obligation (`docs/adr/0028-...:60-71`, `:112`).

---

## Flagged as UNVERIFIED / not established by this reading

- **Whether ADR-0021's packaged-runtime legs are feasible at the sizes involved.** The plan itself
  flags ~358 MiB browser + ~446 MiB mermaid `node_modules` as making a "quick" artifact very large
  (`docs/plans/...:133-137`) but no measured total-archive size for a fully packaged runtime tree
  exists in the corpus. UNVERIFIED.
- **Install-UX step 1** ("preserve and land the current uncommitted portability patch separately"):
  cannot be checked from HEAD. UNVERIFIED.
- **Whether `ccodex sdlc install` can consume a mise-resolved release root directly.** The module
  admits only "the exactly acquired local candidate… under the acquisition layout", refusing "no
  checkout payload, no archive payload, no `--from` and no discovery"
  (`scripts/ccodex_sdlc_install.py:22-30`), while the plan's bridging section says to re-point root
  admission at the mise-resolved root when those verbs are next touched (`docs/plans/...:213-219`)
  and ADR-0011's amendment reports a receipted activation journey run "from the downloaded bytes"
  (`:190-192`). Whether the shipped code path today accepts a mise-resolved root without the manual
  bridging placement was **not traced end-to-end** in this reading. UNVERIFIED.
- **ADR-0006, ADR-0009, ADR-0014, ADR-0029, ADR-0030** are load-bearing for several claims above
  (mermaid digest pins; external/ported library front doors; the single launch route that superseded
  ADR-0005 items 2/4/7; wave evidence superseding ADR-0025) but were **outside the assigned reading
  set** and are cited here only as they are quoted inside the documents read. Their own text is
  UNVERIFIED by this pass.
- **Bun-side facts** are all dated 2026-08-22/23 snapshots by the survey's own framing ("maintained
  as a dated snapshot, not a living promise", `docs/adr/0031-...:98-99`). Anything about Bun's
  current state on 2026-08-24 or later is UNVERIFIED here; no network check was performed.
- **The Bun spike corpora** (`/tmp/bun-cli-spike`, `/tmp/fsio`) are recorded as ephemeral
  (`docs/research/2026-08-23-...:27-30`); the spike archive is said to live in operator state
  outside the repo (`docs/research/2026-08-22-overengineering-audit.md:48-49`). Not present in this
  checkout; the measurements cannot be re-derived from the repository. UNVERIFIED by re-execution.
- **Line-number citations into files not read in full** (`assets/launchers/ccodex.in:18-29`,
  `README.md:263-270`, `mise.toml:47-56`, `scripts/provision_mermaid_linux.py:131-139`) are quoted
  as the source documents give them; only the `mise.toml` and `README.md` ranges were spot-checked
  against the current tree, where the README range has drifted to `:266-276`.
