# Design A — Evolutionary Inversion, No Rewrite

**Assignment.** One complete installer-architecture proposal for `Codeseys-Labs/agentic-sdlc`
(checkout `/tmp/asdlc-research`, v0.7.4, HEAD `e0fbf92`), arguing the strongest available case for:
keep bash + Python per ADR-0031; let mise acquire the versioned release and put `bin/ccodex` on
PATH; make `ccodex` the one front door for the bundle lifecycle at user **and** project scope,
built on the receipts machinery that already exists; shrink the mise task surface to
contributor-only.

**Inputs.** All five research reports read in full
(`.research-out/01-installer-lifecycle.md`, `02-decision-corpus.md`, `03-bun-facts.md`,
`04-claude-plugin-channel.md`, `05-receipts-machinery.md`), plus direct reads of `mise.toml`,
`bin/ccodex`, `scripts/install_skill_bundle.py`, `scripts/ccodex_sdlc*.py`,
`policy/release-candidate.v1.json`, `policy/release-contract.v1.json`, `plugin/`,
`docs/adr/0021`, `docs/adr/0031`. Claims I could not execute are marked **UNVERIFIED**.
No `mise` task was run; the config was left untrusted.

---

## 1. Thesis

The operator's layering is right and is already ~80% built; what blocks it is not a missing
mechanism but **two of everything** — two `ccodex` dispatchers, two bundle front doors, two
acquisition bootstraps, six state stores, forty-four mise tasks — and the fix is subtraction, not a
rewrite. mise already acquires a checksum-pinned release whose archive carries `bin/ccodex`,
`mise.toml` **and** `mise.lock` (`policy/release-candidate.v1.json` payload list, live-verified in
report 05 §b), so one explicit `mise trust` makes the acquired tree resolve its own twelve pinned
tools lazily from its own lock — which is the operator's "mise installs the deps and the CLI",
achieved without a `[tools]`-import mechanism that provably cannot exist (report 02: ADR-0011:156,
plan:56, clone-free research:100-104). That makes `install_operator_tools.py` (1,135 lines),
`assets/launchers/ccodex.in` (509 lines), its 1,660-line test file, its state store, its five mise
tasks, its three declared dispatcher divergences and its entire `HostPreconditionError` exit-3
PATH class **dead weight to be removed before any layer is added**, because their only job was
getting `ccodex` onto PATH without mise. With one dispatcher and one Python route
(`python3.12.11 -I -B`, deleting `run_python`) the exit-3 defect that currently breaks every
`ccodex sdlc` verb in the only downloadable artifact (report 05 §b) disappears structurally rather
than by patch, and `ccodex bundle {install,status,uninstall,update,recover}` + `ccodex doctor`
becomes the single front door over the *existing* receipt chain — closing report 05's missing
GitHub-download→acquisition-receipt bridge by calling the 333-line producer that already exists and
is called by nobody. Project scope then costs almost nothing new: `Config.state_root` is already a
tested seam (`install_skill_bundle.py:118,129,134`, exercised by `self_test`), the ledger is already
keyed by absolute destination and already retains-but-does-not-select records for a different
configured root (invariant 39, test `:411`), so `--scope project` is a resolved root plus a
copy-only rule plus a per-scope activation pointer — and it *subsumes* `manage_claude_workflows.py`
(542 lines + 520 test lines + a state store + three tasks), which report 01 §E.3 already calls "the
template a general project scope would follow." Net: about **−5,000 lines, four state stores instead
of six, one dispatcher instead of two, one front door instead of two, ~11 mise tasks instead of 44,
payload untouched**, every ADR honored, ADR-0031 honored by not reopening it (report 03 changed no
measured fact ADR-0031 relied on and added an *open* Windows defect spawning Rust-compiled
executables, i.e. `uv`), and one accepted-record supersession (ADR-0011 → ADR-0021) plus one
amendment to a *proposed* record whose namespace spelling is the only thing I contradict.

---

## 2. End-state UX: exact commands a fresh operator types

Two properties to notice before the transcripts: the sequence is **identical on both hosts**, and
the count is **four commands plus one review**. The "cross-platform abstraction" the operator wanted
from a compiled binary is obtained here by shipping no compiled artifact at all — a source archive
of authored bytes has no per-platform matrix (contrast ADR-0031 fact 2: 61–85 MB × 5 targets,
no armv7, a live macOS signing regression).

`--scope` and `--agent` are **required, with no default and no wildcard**, per the product spec's
own rule that "Every host and scope is selected explicitly… there is no wildcard `--all` lifecycle
operation" (`docs/plans/claude-code-first-harness/issues/08-…:56-57`). That single change deletes
report 01 §D.1 (the README headline installing both planes while Quickstart insists you choose)
rather than documenting around it.

### 2a. Fresh macOS host (Apple Silicon)

```bash
# 0 — the ONE bootstrap prerequisite (ADR-0002). Nothing below adds a second.
curl https://mise.run | sh
exec $SHELL -l                              # your own shell activation of mise; not ours to write

# 1 — ACQUIRE. One versioned release, one artifact, sha256-pinned in your mise lock.
#     This installs bin/ccodex onto PATH and does nothing else: no host mutation,
#     no trust, no toolchain, no Claude config (ADR-0021 item 3, plan:3-8).
mise use -g github:Codeseys-Labs/agentic-sdlc@1.0.0

# 2 — REVIEW, then TRUST. The one step no script in this product ever performs for you
#     (invariant 27). `ccodex version` needs no tools and prints this exact line.
ccodex version
less "$(mise where github:Codeseys-Labs/agentic-sdlc)/mise.toml"     # 12 pinned tools, ~1.3 GB
mise trust "$(mise where github:Codeseys-Labs/agentic-sdlc)/mise.toml"

# 3 — PREFLIGHT. Read-only: host + version, capabilities, every state store, and every
#     destination that would collide. Writes nothing, locks nothing.
ccodex doctor

# 4 — INSTALL, explicitly scoped and explicitly hosted. All-or-nothing.
ccodex bundle install --scope user --agent claude

# 5 — VERIFY.
ccodex bundle status --scope user
```

Then, each a **separate** effect with its own grant (ADR-0019), none of them implied by step 4:

```bash
ccodex statusline activate                                   # writes 2 keys in settings.json
ccodex hooks activate --hook session-start-routing-primer    # wires 1 hook into settings.json
cd ~/code/my-project && ccodex bundle install --scope project --agent claude
ccodex ensure                                                # optional gateway (ADR-0003/0017)
```

Upgrade — no self-updater, by decision (ADR-0021:24-26,41; plan:82; ADR-0020 item 4):

```bash
mise use -g github:Codeseys-Labs/agentic-sdlc@1.1.0     # side-by-side; 1.0.0 stays installed
ccodex bundle update --scope user --agent claude         # receipted, blocks on any drift
# rollback == select the earlier version and refresh:
mise use -g github:Codeseys-Labs/agentic-sdlc@1.0.0 && ccodex bundle update --scope user --agent claude
```

### 2b. Fresh `ubuntu:24.04` container (non-root operator)

```bash
# Image setup — host capabilities the product requires and never installs (plan:141-147).
# Done as root before the operator's session; `ccodex doctor` observes them, never provides them.
apt-get update && apt-get install -y curl ca-certificates git
# Claude Code itself, per Anthropic's own instructions. It is the host, not our payload.

# Operator session — byte-identical to macOS:
curl https://mise.run | sh
exec $SHELL -l
mise use -g github:Codeseys-Labs/agentic-sdlc@1.0.0
ccodex version
less "$(mise where github:Codeseys-Labs/agentic-sdlc)/mise.toml"
mise trust "$(mise where github:Codeseys-Labs/agentic-sdlc)/mise.toml"
ccodex doctor
ccodex bundle install --scope user --agent claude
ccodex bundle status --scope user
```

### 2c. Contributor (the other, unchanged plane)

```bash
git clone https://github.com/Codeseys-Labs/agentic-sdlc.git && cd agentic-sdlc
mise trust ./mise.toml
mise run check                                            # validate + test + self-test + secrets
ccodex bundle install --scope user --agent claude --mode link    # links, because editability is
                                                                # this plane's whole point
```

### 2d. Notes and honesty markers on §2

- `mise where github:Codeseys-Labs/agentic-sdlc` is presented as the documented spelling for the
  install root. Whether `mise where` accepts a backend-qualified tool name is **UNVERIFIED** (no
  mise command was run). `ccodex version` already prints `distribution root : <path>` and the exact
  `mise trust <root>/mise.toml` line (`bin/ccodex:322-330`), so the fallback needs no new code. A
  phase check pins whichever form works.
- The macOS transcript is the **post-Phase-6** state. Today the receipts plane refuses on Darwin
  outright: `SUPPORTED_SYSTEM = "Linux"` is hardcoded in four separate modules
  (`ccodex_sdlc_install.py:219-220`, `_update.py:205-206`, `_uninstall.py:129`, `_recover.py:69-70`),
  and `policy/release-candidate.v1.json` declares `manifest.platform = "linux-x64"` for an archive
  that contains no compiled bytes. Phase 6 centralizes the gate and earns the darwin-arm64 tuple row
  with its own evidence, because ADR-0027 grants no inheritance.
- `mise use -g github:…` without an exact version does **not** resolve today (prerelease exclusion +
  `minimum_release_age`, ADR-0011:182-195). Phase 1 cuts a non-prerelease tag; until then the
  version is mandatory and `--prerelease` is required.
- An operator whose *global* mise settings leave `github.slsa` / `github.github_attestations` on may
  hit the exact unauthenticated GitHub rate-limit failure ADR-0002 was written about (`mise.toml:6-12`).
  The documented remedy is the settings toggle, never a token — a credential must not become a
  second prerequisite (ADR-0002:45-49).

---

## 3. Component / layer diagram

```
LAYER 0  PREREQUISITE ─ exactly one, forever (ADR-0002:45-49)
  mise >= <min_version>                                        mise.toml:1
  host capabilities OBSERVED, never installed: git, curl, claude   plan:141-147
        │
LAYER 1  ACQUIRE ─ one plane, one artifact, one integrity control
  mise use -g github:Codeseys-Labs/agentic-sdlc@<version>
    → release tree (git-archive of clean HEAD + manifest.json)  build_release.py:202-287
    → bin/ccodex exposed on PATH by mise's own bin detection    ADR-0011:182-195
    → integrity: sha256 in the operator's mise lock            report 04 §f
  SIDE PLANE (preview only): Claude plugin marketplace          §7d below
        │
LAYER 2  TRUST ─ operator-only, once per absolute config path, never scripted (inv. 27)
  mise trust <root>/mise.toml
    → afterwards mise auto-installs the 12 pinned tools LAZILY from the acquired
      tree's own mise.lock, on the first tool-needing verb     bin/ccodex:114-137, 26-27
        │
LAYER 3  ONE FRONT DOOR ─ ccodex (one file, one dispatcher, one Python route)
  ┌ readers (no lock, no write) ─────────────────────────────────────────────┐
  │ ccodex doctor [--json]     host+version, capabilities, ALL FOUR state    │
  │                            stores, and every colliding destination       │
  │ ccodex bundle status --scope <s> [--json]      the ownership ledger      │
  │ ccodex version             tool-free; prints root + the trust command   │
  └──────────────────────────────────────────────────────────────────────────┘
  ┌ bundle lifecycle (0/1/2/3/4, receipted, all-or-nothing) ────────────────┐
  │ ccodex bundle install --scope user|project --agent claude|codex          │
  │   1 ADMIT     re-hash the root against its own manifest.json →          │
  │               seal one acquisition receipt (auto; no manual bridge)     │
  │   2 COMPAT    payload's release-contract vs OBSERVED `claude --version` │
  │   3 CLASSIFY  every entry absent|owned|foreign|modified BEFORE a write; │
  │               any foreign/modified ⇒ refuse the whole run at exit 3     │
  │   4 ACTIVATE  transactional copy (link only for checkout+user scope)    │
  │   5 SEAL      distribution-activation receipt, THEN move the scope's    │
  │               active pointer — receipt before pointer, never reversed   │
  │ ccodex bundle uninstall | update | recover --dry-run|--apply <sha256>   │
  └─────────────────────────────────────────────────────────────────────────┘
  ┌ host-config activation — SEPARATE grants, settings.json only ───────────┐
  │ ccodex statusline status|activate|deactivate                            │
  │ ccodex hooks      status|activate|deactivate --hook <name>              │
  └─────────────────────────────────────────────────────────────────────────┘
  ┌ neighbours, unchanged ──────────────────────────────────────────────────┐
  │ ccodex libraries …   third parties through their own front doors (0009) │
  │ ccodex ensure|launch|ultracode|status|restart|configure|models|providers │
  │                       optional gateway plane, never a gate (ADR-0003)   │
  └─────────────────────────────────────────────────────────────────────────┘
        │
LAYER 4  CONTRIBUTOR ─ checkout only; nothing here is ever on an operator's PATH
  mise run check | validate | test | self-test | secrets
  mise run release:build | hooks:install (lefthook) | contributor:setup
  mise run mermaid:provision | mermaid:linux-test | test:all-hosts
```

Five layers down from eight (report 01 §A.2). Two things vanished as *layers*: the PATH surface
(mise owns PATH now) and the separately-authorized-activation layer (its two survivors moved into
Layer 3 as sibling verbs; its workflow member was absorbed by project scope).

**What did not move, deliberately.** Trust stays an operator act. Acquisition, trust, bundle
activation, settings activation and launch stay **five distinct effects with five distinct grants**
(ADR-0019:28-33; ADR-0021 item 3; ADR-0011:92-97). The convergence in this design merges *front
doors*, never grants: `ccodex bundle install` still cannot activate a statusline, wire a hook, start
OCX, launch Claude Code or trust a config. That is the precise line report 02 §d.1 says was
litigated three times, and this design stays on the decided side of it.

---

## 4. The ownership / state data model (named before mechanisms)

### 4.1 One sentence per document

There are exactly **two questions** worth persisting, so there are two families of document:

| Question | Family | Answers with |
|---|---|---|
| *Which bytes on disk do we own, where, and are they still ours?* | **ownership ledger** | one JSON document, keyed by absolute destination |
| *Which sealed artifact authorized these bytes, and what did that effect actually do?* | **receipt chain** | acquisition receipt → activation receipt → per-scope active pointer |

Everything else in today's six stores is either a duplicate of one of these two or scaffolding no
reader reads.

### 4.2 The ownership ledger

```
path   <XDG_STATE_HOME|~/.local/state>/agentic-sdlc-installer/state.json   mode 0600
lock   installer.lock (sibling, flock/msvcrt)
shape  { "version": 4, "entries": { <abs-destination>: <record> }, "pending": <slot>|null }
```

**Always user-global, in every scope.** This is the one place I keep a decision report 01 §E.2 calls
a trap, and I keep it deliberately: `state_directory()` uses `Path.home()`, not `config.home`
(`install_skill_bundle.py:220-230`, pinned by `tests/test_install_skill_bundle.py:819`). The right
reading is that this was correct all along and only the *legacy* mirror was wrong. One ledger per
machine is what makes `ccodex doctor` able to answer "what is on this box" in one read, and the key
is an absolute destination, so a user-scope entry and forty project-scope entries cannot collide.

**Record — unchanged closed seven-field set** (`install_skill_bundle.py:76`, built `:873-889`,
validated `:348-390`):

```
{ "agent": "claude"|"codex",
  "kind":  "skill"|"agent"|"command"|"workflow"|"hook"|"statusline"|"output-style",
  "name":  <basename>, "source": <absolute>, "mode": "copy"|"link"|"junction",
  "digest": <64 lowercase hex>, "removable": bool }
```

Two rows added to `entry_collection`'s kind→collection table and **nothing else**, honoring that
module's own rule that "a kind is added here and nowhere else" (`:60-62`):

- `statusline` → `<root>/.claude/statusline/agentic-sdlc-statusline` — this is how the statusline
  stops being a second lifecycle. The record's grandparent is still literally `.claude`, so the
  existing validator (`:372-379`) needs no change.
- `output-style` → `<root>/.claude/output-styles/<name>.md` — closing a real coverage hole:
  `grep -rn 'output-styles' scripts/*.py mise.toml` returns **zero hits**, so `output-styles/bluf.md`
  ships in the archive and in `plugin/` today and is installed by nothing. (Whether Claude Code
  auto-discovers `~/.claude/output-styles/*.md` is **UNVERIFIED**; if it needs a settings key, the
  activation belongs in `ccodex statusline`'s merged settings module, not here.)

**No `scope` field, on purpose.** Scope is derivable from the record's own key relative to the
resolved root of the invocation, and that is exactly the selection rule the module already
implements — records for a different configured root are *retained and left unselected*, never
reinterpreted as a conflict (`:1572-1577`, tests `:411`, `:1490`). Adding a field to store a
derivable fact would be the addition this design exists to avoid.

**No schema bump, no migration.** Admitting two more kinds widens the accepted set; every existing
v4 document stays valid. The hard refusal of any non-current schema with no `--migrate-state` stays
exactly as it is (`:266-289`; tests `:367,1192,1216,1232`) — it is the right posture and it costs
nothing while no release has published a document.

**One deletion inside the ledger:** `legacy_state_path` / `legacy_state_directory` and the
second-document refusal (`:132-135`, `:233-247`, `:1307-1318`, test `:1249`) are **removed**. That
check exists to catch a home-relative document written by an installer generation that never
shipped — a textbook throwaway compatibility state. It is also the mechanism that makes
`--claude-home <repo>` fatal-by-accident (report 01 §E.2 item 2: `legacy_state_path` becomes
`<repo>/.local/state/…` and any file there makes every command exit 2). Deleting ~30 lines and one
test removes both the dead compatibility state *and* the only structural blocker to project scope.

### 4.3 The receipt chain

```
<state>/agentic-sdlc/acquisition/receipts/<archive-sha256>.json     release-candidate-acquisition-receipt/v2
<state>/agentic-sdlc/activation/receipts/<operation-id>.json        distribution-activation@2
<state>/agentic-sdlc/activation/active/<scope-id>.json              the pointer, one per scope
<state>/agentic-sdlc/activation/{plans,journals}/                   unchanged
```

- `scope-id` = `user` for user scope, `project-<sha256(resolved-root)[:16]>` for a project. This
  replaces the single `ACTIVE_RECEIPT_NAME = "active-receipt.json"`
  (`ccodex_sdlc_install.py:211`) because a machine with four project installs has four live
  activations and one file cannot name them. Call sites: `replace_active_pointer` in install /
  update / uninstall plus the reader's pointer read — five places, all named.
- `activation_scope` gains `"claude-project"` beside today's `"claude-home"`
  (`ccodex_sdlc_install.py:1375,1651`), plus a `project_root` field on the project value only.
- `selection` is **deleted** from the acquisition receipt. Report 05 §a establishes it is a schema
  field permanently pinned to `"absent"` with no producer that ever writes anything else; the
  install/update verbs already implement selection by *refusing ambiguity*. Deleting an unread field
  is the same move ADR-0022's amendment made against its own machine-local receipt (70 records in
  151 orphan directories, no reader — ADR-0022:100-108) and ADR-0025's compiler. This is the one
  breaking receipt change, which is why it is grouped with `activation_scope` into a **single**
  schema step (v1→v2) rather than two.
- `channels` is **deleted** from `policy/release-contract.v1.json:59-78`, and
  `policy/ccodex-sdlc-read-report.v2.json` is deleted with its digest pin
  (`validate_bundle.py:274-276`) and pin test (`tests/test_ccodex_sdlc.py:555-561`). Neither is read
  by any code path today (report 05 §b), and `validate_bundle.py:1699`'s comment claiming
  `ccodex_sdlc.py` parses both documents is simply false. Rollback and channel-change are removed as
  *promises* too (§8, ADR-0021 amendment): mise's side-by-side installs already give rollback by
  selection, so a second mechanism would be a second update authority.
- **What is now always true and is not true today:** every bundle install produces a receipt.
  Report 05 §c's central finding is that the *proven-working* front door (`ccodex bundle install`) is
  the receipt-less one, so an operator's install has no evidence trail. One front door over the
  admission chain ends that split without deleting either implementation.

### 4.4 Host-config activation receipts (the merge)

```
<state>/agentic-sdlc-claude-settings/receipts/<settings-digest-key>.json
```

`manage_claude_statusline.py` (574) and `manage_claude_hooks.py` (522) are two modules with two
receipt stores doing one thing: owning a key inside a Claude `settings.json` so that
`deactivate` can restore exactly what was there before. They merge into one module with one receipt
schema keyed by `(settings document, key path)`. Their invariants transfer verbatim: the global
settings document is read, never copied or linked (`README.md:775-776`); activation mutates only the
named keys (`README.md:790-793`); installing never activates (invariants 28, 29); each activation is
its own grant. The measurable win is that the aggregated reader can finally see them —
`ccodex sdlc inspect` today projects **two of six** stores and `grep -c 'statusline|manage_claude'
scripts/ccodex_sdlc.py` is **0** (report 01 §D.4).

### 4.5 Store accounting

| # | Today (report 01 §B.2) | Target |
|---|---|---|
| 1 | bundle `state.json` v4 | **kept**, +2 kinds, −legacy mirror |
| 2 | operator-tools `state.json` v2 | **deleted** (module deleted) |
| 3 | statusline `receipt.json` | merged → 4 |
| 4 | claude-hooks dir | merged → 4 |
| 5 | claude-workflows receipts | **deleted** (project scope subsumes it) |
| 6 | `ccodex sdlc` acquisition + activation | **kept**, per-scope pointer, schema v2 |
| 7 | bootstrap receipt | **deleted** (script deleted, Phase 7) |
| — | foreign skills-CLI lock | unchanged, read-only, not ours |

Six own stores → **four**, and all four are projected by one reader.

### 4.6 Idempotence, stated as a rule

Every lifecycle operation must be a **no-op with no write and no new receipt** when the live state
already equals the requested state:

- `install` where every planned entry classifies `owned` **and** digest-equal: no bytes move, no
  receipt is sealed, the pointer is untouched, exit 0 with `up to date: <candidate-id>`. This
  requires changing today's unconditional refresh — `install_skill_bundle.py:430-437` deliberately
  allows a `refresh` whose `before == after` "because a copy-mode entry is refreshed on every run."
  That is a mechanism artifact, not a requirement, and it is why report 01 §B.4 lists
  `refreshed:` as unconditional. Making install genuinely convergent removes writes, removes
  receipt noise, and makes "did anything change?" answerable from the exit line.
- `uninstall` of an absent-but-unrecorded entry: reports `absent:`, retires the record, writes
  nothing else.
- `statusline activate` when the exact owned bytes are already the live `statusLine.command`:
  no-op, exit 0. (Today `exact_owned_statusline()` already refuses unless the exact owned bytes are
  installed — `install_operator_tools.py:557-565` — which is the harder half of this.)
- `doctor`, `status`, `--dry-run` and `recover --dry-run`: lock-free and writeless, unchanged
  (invariants 35–38).

### 4.7 Exit ladder, unified

The converged verb adopts the full ladder, which the receipt-less side does not have today
(report 01 §D.6: any single conflict makes install exit 1 while 48 entries land fine):

| code | meaning | when |
|---|---|---|
| 0 | ok / no-op | everything requested is true |
| 1 | unexpected internal failure | never a refusal |
| 2 | grammar / schema / input | missing `--scope`, unknown kind |
| 3 | **refused before any effect** | classify found any foreign/modified entry; untrusted config; unobservable host; wrong platform tuple |
| 4 | admitted partial or unknown effect | an effect started and did not complete; names `ccodex bundle recover` |

The decisive change is that a pre-write collision is now **exit 3 with nothing written**, not exit 1
after a partial install. That is what makes `ccodex bundle status`'s answer meaningful, and it comes
from adopting `update`'s existing block-before-write discipline (`ccodex_sdlc_update.py:36-42`,
`BLOCK_SENTENCE` at `:229`) for `install` as well.

---

## 5. What gets DELETED from the current tree

Ordered by size. Payload (`skills/`, `agents/`, `commands/`, `workflows/`, `hooks/`,
`output-styles/`) is **untouched** throughout.

| Path / thing | Lines | Why it can go |
|---|---:|---|
| `tests/test_operator_tools.py` | 1,660 | tests a deleted module |
| `scripts/install_operator_tools.py` | 1,135 | its only job was putting `ccodex` on PATH without mise; mise now does that |
| `assets/launchers/ccodex.in` | 509 | the second dispatcher; its six install-time bindings and pinned shebang exist only because it is not inside the tree |
| `scripts/manage_claude_workflows.py` | 542 | `--scope project` is the general case of its special case |
| `tests/test_manage_claude_workflows.py` | 520 | ditto |
| `tests/test_bootstrap_agentic_sdlc.py` | 408 | tests a deleted acquisition plane |
| `scripts/bootstrap-agentic-sdlc.sh` | 280 | ADR-0011's managed clone; superseded by the mise release plane (Phase 7) |
| `manage_claude_{hooks,statusline}.py` merge | ~1,096 → ~600 | two modules, two stores, one job |
| `tests/test_manage_claude_{hooks,statusline}.py` merge | 760 → ~500 | ditto |
| `bin/ccodex: run_python()` | ~12 | one Python route replaces two; deletes the divergence class behind the shipped exit-3 defect |
| `bin/ccodex`: interactive `set-fast-model` selector (from `ccodex.in:297-354`) | ~60 | never ported; the one-argument form works and the refusal already names the remedy (`bin/ccodex:255-259`) |
| `legacy_state_path` + `legacy_state_directory` + second-document refusal + test | ~40 | throwaway compatibility state for a generation that never shipped; also the project-scope trap |
| `policy/ccodex-sdlc-read-report.v2.json` + its digest pin + pin test | ~60 | dormant scaffolding; `validate_bundle.py:1699`'s claim that it is parsed is false |
| `channels` block in `policy/release-contract.v1.json:59-78` | ~20 | no code reads it; `public_channel` is hard-pinned `null` everywhere |
| `selection` field in the acquisition receipt | ~10 | permanently `"absent"`; no producer ever writes another value |
| `plugin/workflows` and `plugin/output-styles` symlinks | 2 | the Claude plugin schema has no field for either (report 04 §a); the manifest currently over-claims |
| `scripts/install-skill-bundle.sh`, `scripts/validate-bundle.sh` | 53 | compatibility wrappers for a shell entry point nothing needs once `ccodex` is the front door |
| `mise run setup` deprecated forwarder | ~4 | a forwarder to a forwarder |
| 33 of 44 `[tasks…]` blocks | ~165 | §5b |
| `HostPreconditionError` exit-3 class, `validate_bin_dir`, PATH-membership refusal | (in the 1,135) | there is no bin dir left to validate |
| `ccodex sdlc` as an operator-facing spelling | (grammar only) | one namespace; the four per-verb modules survive behind `ccodex bundle` |

**Estimated net: ≈ −5,000 tracked lines** against 151,263 today (`git ls-files | xargs wc -l`).
Additions are small and enumerated in §6.

### 5b. mise tasks: 44 → 11

**Deleted** (their capability moves to `ccodex`, or the capability is deleted):
`bundle:install`, `bundle:status`, `bundle:uninstall`, `bundle:install:claude`,
`bundle:install:codex`, `bundle:install:all-hosts`, `bundle:status:all-hosts`,
`operator-tools:{install,status,retire-aliases,uninstall,self-test}`,
`libraries:{list,install,status,migrate}`, `claude:statusline:{status,activate,deactivate}`,
`claude:hooks:{status,activate,deactivate}`, `claude:workflows:{status,activate,deactivate}`,
`ocx:{launch,ultracode,status,restart,configure}`, `research-os:install`, `setup`.

**Kept, contributor-only:** `check`, `validate`, `test`, `self-test`, `secrets`, `release:build`,
`hooks:install`, `contributor:setup`, `mermaid:provision`, `mermaid:linux-test`, `test:all-hosts`.

Two side effects worth naming. First, `README.md:463`'s claim that the task table lists "Every task
this repository defines" becomes true again — it currently omits eight (report 01 §D.8). Second,
`assets/launchers/ccodex.in:23`'s "There are 36 mise tasks" is deleted along with the file, so the
stale count cannot drift a third time.

**Preserved gate topology:** `check = validate + test + self-test + secrets` (`mise.toml:154-156`)
and "no gate leaf reaches an opt-in installer" (invariant 32) are unchanged. Both self-tests stay
gate leaves; `bundle self-test` keeps running install→status→uninstall in a throwaway home *and* a
throwaway state root (`install_skill_bundle.py:1740-1758`) — the very seam that makes project scope
cheap. The `operator-tools self-test` leaf is deleted with its module, so `check` loses one leaf and
gains a project-scope leaf in Phase 4.

---

## 6. Migration path in verifiable phases

Each phase is independently landable, ends in a stated check, and leaves the tree shippable.
"Container check" means a disposable `ubuntu:24.04` with only curl, git, ca-certificates, mise and
Claude Code, run as non-root against the public remote — the method
`docs/research/2026-08-08-fresh-host-install-verification.md` established, whose methodological rule
also applies: **every assertion reads output, never a bare exit code** (`:249-260`).

### Phase 0 — Remove dead weight before adding anything

Delete: `channels`, `read-report.v2.json` + pin + pin test, `plugin/workflows` and
`plugin/output-styles` symlinks, `mise run setup`, `legacy_state_path` / `legacy_state_directory` /
the second-document refusal / test `:1249`, `install-skill-bundle.sh`, `validate-bundle.sh`. Fix
`validate_bundle.py:1699`'s false comment by deleting the thing it describes.

**Check.** `mise run check` green. `git diff --stat` shows deletions only, no additions. On a host
with an existing install, `mise run bundle:status` output is **byte-identical** before and after
(prove the deletions are inert). `grep -rn 'read-report.v2\|"channels"' -- . ` returns 0 outside
`docs/adr/`.

### Phase 1 — Tagged-release CI, and the operator-verifiable rebuild

Implement the Install-UX plan's undone step 7: `.github/workflows/release.yml` builds via
`scripts/build_release.py` on a tag, publishes `agentic-sdlc-<v>.tar.gz` + `SHA256SUMS`, and cuts
the first **non-prerelease** tag. Add the plan's step 9 self-pin: a
`[tools."github:Codeseys-Labs/agentic-sdlc"]` entry in the checkout's `mise.toml` + `mise.lock`.

**Check.** A third party runs `git archive` at the tag with the same
`policy/release-candidate.v1.json` allowlist and gets a sha256 **identical** to the published
`SHA256SUMS` line. `mise.lock`'s self-pin checksum equals it. `mise use -g
github:Codeseys-Labs/agentic-sdlc@<v>` (no `--prerelease`) resolves — the leg ADR-0011:182-195
measured as failing and left unclaimed. This check is the whole supply-chain story in one command
and it is exactly the property ADR-0031 fact 4 says a compiled artifact cannot offer.

### Phase 2 — One Python route

`bin/ccodex`: delete `run_python()`; every Python entrypoint goes through the renamed
`run_sdlc_python()`, i.e. exact CPython 3.12.11 exec'd directly with `-I -B`. Safe by inspection:
every `scripts/*.py` entrypoint declares `dependencies = []` under `requires-python = ">=3.12"`, so
`uv run --script` was buying nothing except a subprocess layer and a divergence.

**Check.** From a **downloaded release tarball** (not the checkout): `ccodex bundle status` and
`ccodex sdlc status` both exit 0. Today the second exits 3 —
`runtime_admission()` (`ccodex_sdlc.py:454-471`) demands
`sys.flags.isolated`/`no_user_site`/`dont_write_bytecode` all true, which `uv run --script` does not
provide, and report 05 §b live-verified this against the published v0.7.4 `bin/ccodex:138-147`.
`tests/test_bin_ccodex.py` gains one test pinning that exactly one Python route exists
(`grep -c 'uv run --script' bin/ccodex` = 0).

### Phase 3 — Converge the front door; wire the acquisition receipt

Grammar becomes `ccodex bundle {install,status,uninstall,update,recover}` + `ccodex doctor`;
`ccodex sdlc *` is deleted as a spelling while all four per-verb modules survive behind it. `install`
auto-seals the acquisition receipt from the root's own `manifest.json` by calling the existing
`write_acquisition_receipt.py` machinery — deleting the manual "placement bridge" recipe
(`docs/plans/2026-08-14T163833Z-Install-UX.md:195-219`, which labels itself temporary). `install`
adopts `update`'s block-before-write discipline and the 0/1/2/3/4 ladder. `doctor` absorbs
`sdlc inspect|status|doctor` and adds the plan's host-capability preflight (`:149-163`), including the
destination-collision classification that `bundle status` structurally cannot do (report 01 §D.5).
`install` runs `doctor` first and refuses with named remediation (plan `:163`).

**Check.** Container: `ccodex bundle install --scope user --agent claude` on a release root seals an
acquisition receipt whose digest equals `write_acquisition_receipt.py`'s output for the same root,
and an activation receipt whose single `derived-from` names that receipt's `operation_id`. `ccodex
doctor --json` names all four state stores. **Idempotence:** the second identical `install` writes
no bytes, seals no receipt, leaves `activation/active/user.json` mtime and bytes unchanged, and
exits 0. **All-or-nothing:** with one pre-seeded foreign `~/.claude/skills/agentic-sdlc/`, install
exits **3** and `find ~/.claude -newer <marker>` is empty. Uninstall then `ccodex doctor` reports
clean — this is the check that closes report 05's FINDING-1 (`owned-entry-conflict`/`degraded`
immediately after a receipted retirement), whose fixed state the reports disagree about.

### Phase 4 — Project scope

Add `--scope user|project` (required, no default) and `--project PATH`. Project root resolution:
walk up from cwd for a `.git` entry — **no git binary required**, so no new host capability and no
ADR-0002 tension. Refuse (exit 3) a root that is `Path.home()`, the distribution root, inside the
mise install tree, or a subdirectory rather than the repo root (reusing
`instruction_generator.py`'s "`--target` must be the repository root" refusal and
`manage_claude_workflows.py:522-523`'s "refuses a target that resolves to the installed home
plane"). Force `mode=copy` for project scope and refuse `--mode link` there, carrying
`manage_claude_workflows.py:18-23`'s three reasons verbatim: a repo-committed entry must be
self-contained; a link would embed a user-specific absolute path; and a later refresh must not
silently change what the target's sessions execute without new per-repo authorization. Receipt
schema v1→v2 (`activation_scope: "claude-project"` + `project_root`, `selection` deleted); pointer
becomes `activation/active/<scope-id>.json`. Every completed project verb prints the
session-start-snapshot fact (`manage_claude_workflows.py:66-70`). Delete
`manage_claude_workflows.py`, its tests, its store and its three tasks. Add a project-scope leaf to
`bundle self-test`.

**Check.** In a fresh throwaway repo: install `--scope project` creates
`<repo>/.claude/{skills,agents,commands,workflows,hooks}` as **copies** (`find -type l` empty);
`ccodex bundle status --scope project` lists them inside that repo and lists none in a second repo;
uninstall in repo A leaves repo B **and** user scope byte-identical; `--mode link --scope project`
exits 3; `--scope project` from a non-repo directory exits 3 naming the reason; two project installs
plus one user install coexist in one ledger with three live pointers under `activation/active/`.
Then the ADR-0027 tuple row: a committed clean-host journey transcript for project scope, because it
inherits nothing from user scope.

### Phase 5 — One dispatcher; delete the PATH plane

Delete `install_operator_tools.py`, `assets/launchers/ccodex.in`, `tests/test_operator_tools.py`,
the five `operator-tools:*` tasks and the operator-tools store. Add `statusline` and `output-style`
kinds to `entry_collection`. Merge the two settings modules into one with one receipt store; add
`ccodex hooks` to the dispatcher (one `case` arm) beside the existing `ccodex statusline`. Ship a
**transition-only** refusal: `bundle install` refuses at exit 3 if the retired operator-tools store
still exists, naming `mise run operator-tools:uninstall` — which still exists at this point in the
order.

**Check.** Container: `command -v ccodex` resolves to the mise shim; **no file is created in
`~/.local/bin`** at any point; `ccodex statusline activate` sets `statusLine.command` to the
`~/.claude`-owned copy, and after `mise prune` removes the previous release directory the statusline
still resolves (the Install-UX plan's `:185` copy-activation requirement, now proven rather than
asserted). `deactivate` restores the prior `settings.json` **bytes exactly** and leaves every foreign
key untouched (byte compare). `ccodex doctor` shows statusline and hook state, which no aggregated
reader can do today. `grep -rn 'XDG_BIN_HOME\|HostPreconditionError' scripts/` returns 0.

### Phase 6 — macOS

Replace the four hardcoded platform gates with one table referenced by all four modules, and admit
`Darwin` + `arm64`/`x86_64`. Change `policy/release-candidate.v1.json`'s
`manifest.platform` from `"linux-x64"` to a platform-independent value, since the archive contains
no compiled bytes; record the observed platform in the activation receipt instead of asserting it in
the manifest.

**Check.** `grep -rn 'SUPPORTED_SYSTEM\s*=\|SUPPORTED_PLATFORM\s*=' scripts/` returns exactly **one**
definition. A committed transcript under `docs/evidence/` of the full §2a journey on darwin-arm64,
including install → status → uninstall → clean `doctor`. Per ADR-0027 this is a new tuple row with
its own evidence; it inherits nothing from the Linux row and grants nothing to `darwin-x64` or
Windows.

### Phase 7 — Close the decision debt

Supersede ADR-0011 with a new accepted ADR (the plan's step 10; ADR-0011:160-165 requires a new
record, not an edit). Delete `scripts/bootstrap-agentic-sdlc.sh`, its receipt and its tests. Amend
ADR-0021 (§8) and move it to accepted, which by ADR-0028:60-71 unblocks the whole initiative's
status. Rewrite the README quick-path-first.

**Check.** `grep -rn 'bootstrap-agentic-sdlc' --exclude-dir=docs/adr` returns 0. `mise tasks | wc -l`
≤ 12 and every listed task appears in the README table. The README headline block is the four
commands of §2 and the Quickstart's stated count equals its numbered items — closing report 01 §D.1
and §D.8. ADR-0021's status line reads `accepted`, and ADR-0028's registry agrees.

### Phase 8 — Delete the transition state

Remove Phase 5's operator-tools refusal.

**Check.** `grep -rn 'operator-tools' scripts/ bin/ mise.toml` returns 0. `mise run check` green.
This phase exists because the principle is *do not preserve throwaway compatibility states in the
target architecture* — so the one compat state this migration needs has a scheduled deletion date
from the moment it is written.

---

## 7. Supply-chain story

### 7a. The chain the operator can verify, end to end

```
git tag  ──git archive (deterministic, allowlisted)──►  agentic-sdlc-<v>.tar.gz
   │                                                        │
   │  anyone can re-run git archive at the tag and           ├─► SHA256SUMS (published)
   │  compare sha256: REBUILD-AND-COMPARE WORKS              ├─► sha256 pinned in the operator's mise lock
   ▼                                                        ▼
manifest.json  ── per-file sha256 + per-symlink target, candidate_id = sha256(inventory)
   │              build_release.py:202-287; 231/231 re-hashed in the container proof
   ▼
acquisition receipt (v2)  ── re-hashes the placed root against its own manifest IN BOTH
   │                         DIRECTIONS, then seals create-only: O_EXCL + O_NOFOLLOW, fsync,
   │                         read back and compared   write_acquisition_receipt.py:139-198, 271-300
   ▼
activation receipt (v2)   ── per-entry prestate + disposition + content_sha256, resolved_version
   │                         taken from the CANDIDATE'S OWN MANIFEST (version_source:
   │                         "archive-manifest"), never from a request; exactly one derived-from
   │                         ancestor naming the acquisition receipt's operation_id
   ▼
activation/active/<scope-id>.json  ── moved only AFTER the receipt is sealed
```

The load-bearing property is the first arrow: **the release artifact is reproducible, so a digest
means what it says.** ADR-0031 fact 4 measured the alternative — three identical-input
`bun build --compile` runs producing pairwise-distinct sha256, first difference at offset
82,481,180 — and called determinism "a control this repository will not trade away." This design
does not merely avoid trading it; Phase 1 turns it into a published command a stranger can run.

### 7b. Where trust is actually concentrated, stated plainly

Three places, and the design does not pretend otherwise:

1. **`mise trust <root>/mise.toml`.** This is the single largest grant an operator makes: it
   authorizes twelve pinned tools, ~1.3 GB, including `npm:@bitkyc08/opencodex` 2.28.0 whose
   integrity surface is **version+backend only — no tarball hash, no transitive integrity**, accepted
   only because nothing in the gate graph consumes it (ADR-0005:218-222). The review artifacts are
   `mise.toml` and `mise.lock`, which is why step 2 of §2 is a `less` before a `trust`, and why no
   script in this product will ever run `mise trust` (invariant 27, `bin/ccodex:114-137`).
2. **HTTPS authenticates transport, not contents** (ADR-0011:120-130). The `mise.lock` sha256 and the
   `SHA256SUMS` line are the content controls; the deterministic rebuild is the third-party control.
3. **Same-UID adversaries are out of scope, by name.** The ownership test is byte identity and only
   byte identity — no birth-time, no dev/inode witness (`install_skill_bundle.py:914-936`, `:8-15`) —
   with the documented, deliberately weaker consequence that a byte-identical operator recopy *is*
   removed by uninstall while any modification is refused and preserved. The read-only guard
   (`ccodex_sdlc_readonly.py:1-8`) says the same about itself: "not an adversarial same-UID sandbox."
   Keep both disclaimers verbatim; the 2026-08-22 overengineering audit's core criticism was
   machinery "defending adversaries its own docstrings disclaim."

### 7c. Signing

**No code signing, because there is nothing to sign.** This is the clearest structural advantage
over a compiled design and it should be stated as such: no Developer ID, no notarization, no
Authenticode, no Azure Trusted Signing pipeline, no SmartScreen reputation curve, no `strip`
landmine that "destroys the binary while leaving `--version` answering exit 0" (ADR-0031 fact 2).
Report 03 §d adds the corroborating detail that even a correct compiled pipeline requires
compile-first-sign-last as a hard ordering (`oven-sh/bun#20109` → `#22960`, shipped 1.2.23) and that
Microsoft's current rules mean a validly-signed new binary **still** triggers SmartScreen until it
accumulates download reputation — an obligation this design never incurs.

What is added instead, both cheap: **sign the release tag** (`git tag -s`), and attach
`gh attestation` provenance to the archive as an *optional* verification the operator may check.
Neither may become a prerequisite: `mise.toml:6-12` disables `github.slsa` and
`github.github_attestations` precisely because the unauthenticated attestation fetch was rate-limited
to hard failure and "would make `GITHUB_TOKEN` a second bootstrap prerequisite" (ADR-0002:23-34).
So attestations are an *available* control, never a required one — and the documented remedy for a
rate-limited install is the settings toggle, not a token.

### 7d. The Claude plugin marketplace plane, and why it stays a preview

Report 04 measures the native plugin channel at ~60% of the Claude plane: skills, agents and commands
auto-discover; workflows have **no schema field** (0%), output-styles have **no mechanism** (0%),
statusline is limited (30%), and the Codex plane is a separate system. It also records that plugins
pin a git SHA declaratively with **no local checksum verification**, while mise pins and verifies
locally and fails closed. That second fact alone disqualifies the plugin channel as the primary
plane under ADR-0020 item 1 (exact identity through a reviewed front door).

But the 60/40 split is not only a capability gap — it is the right *authorization* boundary, and this
design promotes it to a rule:

> The plugin plane carries only components whose activation grants no automatic execution.

Skills, agents and commands are model-invoked: the operator's turn is the grant. Hooks fire on
events, workflows execute, and a statusline reconfigures the host — those run or reconfigure without
a turn, so they stay on the `ccodex` plane where each gets its own fresh grant (ADR-0019:28-33).
This is why `plugin/workflows` and `plugin/output-styles` are deleted in Phase 0 (they are symlinks
into a schema with no field for them, i.e. the manifest over-claims), why no `hooks.json` is added to
the plugin, and why `marketplace_overlap()`'s fail-closed refusal of the whole Claude plane
(`install_skill_bundle.py:939-955`, `:1328-1342`) is kept unchanged.

### 7e. What the operator reviews before trusting, as a checklist

| # | Artifact | Command | What a failure means |
|---|---|---|---|
| 1 | published archive digest | compare `SHA256SUMS` to the downloaded tarball, or trust the `mise.lock` pin | wrong or tampered artifact; stop |
| 2 | reproducibility (optional, strong) | `git archive` at the tag → sha256 equals #1 | the published bytes are not the tagged source |
| 3 | **`mise.toml` + `mise.lock`** | read them, then `mise trust` | this is the real grant: 12 tools, ~1.3 GB |
| 4 | host + collisions | `ccodex doctor` | a named refusal with the remedy, before anything moves |
| 5 | the exact plan | `ccodex bundle install … --dry-run` | every destination and disposition, no lock, no write |
| 6 | the sealed evidence | `ccodex doctor --json` | acquisition digest, activation receipt, per-entry `content_sha256` |

---

## 8. Explicit tradeoffs vs. the status quo

| Axis | Status quo (v0.7.4) | This design | Honest cost |
|---|---|---|---|
| Acquisition planes | **4** (hand clone, bootstrap script, mise release, marketplace) | **3** (mise release, checkout, marketplace-as-preview) | the managed-clone plane is deleted; anyone scripted against it must switch |
| Commands to a working install | 5 in the README headline, 6 in Quickstart, which disagree on `--agent` | **4 + 1 review**, identical on macOS and Linux | still not a `curl \| bash` one-liner; mise + one trust remain |
| `ccodex` dispatchers | **2**, with 3 declared divergences and 6 install-time bindings | **1**, shipped in the archive, on PATH via mise | the interactive `set-fast-model` selector is deleted, not ported |
| Python routes | 2 (`uv run --script`, and direct `-I -B`) | **1** (`-I -B`) | every entrypoint now demands CPython exactly 3.12.11 (already true in effect) |
| Receipts on an operator install | **none** — the proven path is the receipt-less one (report 05 §c) | **always** | acquisition receipt v1→v2 breaks existing prerelease receipts; remedy is re-acquire |
| Own state stores | **6** | **4** | one merge (settings) and one deletion (operator-tools) touch live state once |
| mise tasks | **44**, 8 undocumented | **11**, all documented | every doc, script and habit naming `mise run bundle:install` breaks deliberately |
| Project scope | none; `--claude-home <repo>` is an undesigned side door whose state does not follow it | **first-class**, copy-only, per-scope pointer, own tuple row | N repos × 28 entries in one ledger; `status` is per-scope, so "everything everywhere" needs `doctor` |
| Partial install | any 1 conflict ⇒ exit 1 with 48 entries landed | **exit 3, nothing written**, or exit 4 with `recover` named | a host with one foreign entry now installs *nothing* until resolved — stricter, and louder |
| Idempotence | copy entries `refreshed:` on **every** run | true no-op when converged | a behavior change some tests pin; enumerated in Phase 3 |
| PATH | product refuses unless `~/.local/bin` is already on PATH (exit 3, 3 operator actions mid-install) | product never touches PATH; **mise** owns it | the operator must have activated mise in their shell — the one prerequisite doing its job |
| macOS | receipts plane hardcoded `Linux` in 4 files; refuses | supported after Phase 6, with its own evidence | until Phase 6 lands, macOS operators are on the receipt-less path |
| Windows | 2 dispatchers, PowerShell helpers, WSL-only claims | unchanged; `test:all-hosts` stays contributor-only | **no** Windows improvement is claimed. Deliberate: report 03 §g found an *open, untriaged* Bun defect hanging on native spawns of Rust-compiled `.exe`s — i.e. `uv` — so the compiled alternative would not have fixed it either |
| Self-update | none | **still none** | upgrade = `mise use -g …@newer` + `ccodex bundle update`; two commands instead of one, and one update authority instead of two |
| Rollback / channels | promised by ADR-0021 item 4, unimplemented, scaffolding unread | **promise deleted**; rollback = select the earlier mise version and refresh | ADR-0021's decision text must be amended down, which is a visible reduction in scope |
| Binary size / release weight | 120 KB of bash + a source archive | unchanged | vs. ADR-0031's measured ~350 MiB per 5-platform compiled release: this axis is a win by not moving |
| Startup latency | bash parse + one runtime seam | marginally **faster** (one fewer `uv run` subprocess per Python verb) | no measurement yet; **UNVERIFIED**, and the honest expectation is "small" |
| Cross-platform abstraction | none | **none gained** | this is the operator's P4 premise, and it is refused: ADR-0031 fact 1 measured the motivating Windows argv defect reproducing *identically* in the compiled binary |
| Supply chain | mise.lock pin + manifest re-hash | same, plus a published rebuild-and-compare check and optional tag signing | vs. a compiled design's >99.99% unpinned executed bytes and non-reproducible output (ADR-0031 facts 3, 4) |
| Lines of code | 151,263 tracked | **≈ −5,000**, payload untouched | one release absorbs a lot of churn; the audit's ranked deletions are complementary, not included here |

### 8b. The three decisions this design engages head-on

**ADR-0031 (accepted, 2026-08-23) — honored, not reopened.** Its burden on a re-proposer is to "show
which measured fact changed" (`:141`), and its three revisit triggers are conjunctive (`:101-112`).
Against report 03, dated one day later: trigger 1 is **false** (#36173 still open and unmerged; even
merged it verifies registry `dist.integrity`, so a ccodex-grade pin stays the caller's job). Trigger 2
is **false** (the surface has not been stable for one release; this proposal is itself the churn).
Trigger 3 is **false** (the `sdlc` namespace is still tested in-process, so a language swap would
orphan the suite that must prove it). Of the five measured facts, **none changed**: the Windows argv
defect is still not a bash defect; sizes are unchanged; the compile-target supply chain is still
unpinned; compile output is still non-reproducible, and report 03 §e confirms that constraint is
*inherited* by self-update, since only checksum-of-shipped-artifact is available; and the tax is
still ~400 real lines. Report 03's one direct correction (`BUN_OPTIONS` argv splicing fixed in
1.2.23) narrows a *hazard*, not a fact — and `BUN_BE_BUN=1` full-CLI takeover remains open. Report 03
also *adds* two facts against P4: an open, untriaged Windows defect hanging on native spawns of
Rust-compiled executables (`uv`'s exact profile), and a compiled-binary-specific PATH-lookup failure
class. The approved harvest — one Bun-compiled settings-bypass classifier invoked by the existing
bash launcher, under ten mandatory preconditions (`:80-96`) — is untouched by this design and remains
available after Phase 5 stabilizes the surface.

**ADR-0002 (accepted) — honored, with the one tension retired rather than argued.** mise stays the
only bootstrap prerequisite. No pin is added. Nothing in `[tools]` grows. Crucially, project scope
does **not** introduce `git` as a required capability: root detection walks for a `.git` entry using
stdlib only, so ADR-0002's system-package prerequisite class (`:88-91`) is never touched. `git` and
`curl` remain host capabilities that `ccodex doctor` *observes* (plan `:141-147`), and the
attestation/rate-limit remedy is a settings toggle, never a credential (`:23-34`).

**ADR-0021 (proposed) — honored in substance, amended in two places.** Items 1, 3 and 5 are adopted
verbatim and are the spine of §3. Two amendments, cheap because ADR-0028:112 states that "a proposed
child is not presented as a current product constraint":

1. **Item 2's namespace becomes `bundle`, not `sdlc`.** Reason: `sdlc` names the product, `bundle`
   names the object being installed; the Install-UX plan already specifies `ccodex bundle install
   --agent claude` verbatim (`:26-32`); AGENTS.md's own current instructions name that verb
   (`AGENTS.md:193-209`); and it is the spelling with executed evidence against the real artifact
   (report 05 §c). Having both is the actual defect — two live front doors over one ownership ledger
   with divergent evidence trails — and this resolves it by deleting a *name*, not an implementation.
2. **Item 4 loses `downgrade`, `rollback` and `channel change` as named operations,** and gains
   **scope** as an explicit axis alongside host. Reason: the promise is unimplemented, its scaffolding
   is unread (`channels` in the contract; `selection` permanently `"absent"`), and mise's
   side-by-side installs already provide rollback by selection — a second mechanism would be the
   "second update authority" the same ADR rejects a self-updater for (`:24-26`).

ADR-0011 is superseded in Phase 7 by a new record, as its own reversal condition requires
(`:160-165`). ADR-0017, ADR-0019, ADR-0020, ADR-0022 (as amended), ADR-0027 and the Install-UX plan
are honored without amendment; the plan's undone steps 5 (packaged runtimes), 7 (release CI), 9
(self-pin) and 10 (supersede) are addressed by Phases 1 and 7 — except **step 5, which this design
declines**: packaging private runtimes duplicates what `mise trust` + the shipped `mise.lock` already
deliver lazily, and the plan itself flags the size problem (~358 MiB browser + ~446 MiB
`node_modules`, `:133-137`). Declining an undone step is a smaller change than performing it.

### 8c. Answering the operator's P3 directly

**Is `ccodex`-cli fit for this? Yes — and it is already doing it.** ADR-0017 makes `ccodex` *the*
operator CLI and "not a second product brand" (`:34-35`); ADR-0021 assigns the lifecycle to it; the
Install-UX plan assigns Claude activation to `ccodex bundle install --agent claude`; and both verbs
exist in `bin/ccodex` today (`:287-295`, `:314-320`). The fitness problem is not the CLI's design or
language — it is that there are **two** of it (a committed self-locating dispatcher and a rendered
PATH dispatcher with six install-time bindings) and **two** of its bundle front door (one proven and
receipt-less, one receipted and currently refused at exit 3 by its own runtime admission in the only
downloadable artifact). Fix the twoness and P1 and P2 fall out. P4's premises — cross-platform
abstraction, performance, packing, self-update — are each measured to be worth zero-or-negative here:
the abstraction does not fix the defect that motivated it, the startup is 2.8× slower, the packing
inverts one artifact into five unsigned 61–85 MB ones with >99.99% unpinned bytes, and the self-update
is a second update authority rejected independently by four records.

---

## 9. Open questions

1. **Does project scope block on a user-scope marketplace overlap?** `marketplace_overlap(home)`
   takes the configured home (`install_skill_bundle.py:939`), so under `--scope project` it reads
   `<repo>/.claude/plugins` and finds nothing — no block. But an enabled user-scope marketplace
   plugin *is* live in that project's sessions, so the operator would carry two copies of 13 skills
   in one context window. Filenames do not collide (plugin components are namespaced), so this is a
   duplication problem, not an ownership one. Options: block in both scopes (fail-closed, current
   spirit), or report a named `overlap:` note under project scope only. **Undecided; needs a measured
   read of what a session actually loads.**
2. **Should project-scope entries be committed or gitignored?** Copies are self-contained, so
   committing is viable and is arguably the point (a repo that carries its own harness). But writing
   `.gitignore` rules into someone's repository is close to ADR-0022's rejected "spray one standard
   scaffold into every repository" (`:29-31`). Proposal: the installer writes payload only, never
   `.gitignore`, and prints both options. Needs the operator's call.
3. **Should `--agent codex` survive at all?** 21 of 49 discovered entries exist for a plane with no
   compatibility row in `policy/release-contract.v1.json` (`compatibility.core.host = "claude-code"`,
   `support_rows = []`) and no parity promise under ADR-0017. Deleting the codex plane would remove a
   whole destination root, the `CODEX_HOME` handling, the repo-root refusal, and ~8 `agents/codex/*.toml`
   installs. **Measure first**, then decide; this design keeps it.
4. **Where do `rightsize:evaluate` and `usage:report` (891 lines) belong?** They are operator-facing
   analysis, not contributor gates and not "working ON the repository," so `bin/ccodex:95-97`'s rule
   does not cleanly place them. Options: `ccodex rightsize` / `ccodex usage` verbs, or keep them as
   contributor tasks. Not guessed here.
5. **Does anything depend on the unconditional refresh?** Making install a true no-op (§4.6) changes
   `install_skill_bundle.py:430-437`'s deliberate allowance. Its stated reason is that a copy-mode
   entry's source cannot be diffed — but the digest *is* the diff, so the allowance looks vestigial.
   Needs a grep of the pending-transition tests before the change lands.
6. **Should a checkout root seal an acquisition receipt at all?** This design says yes, with
   `release_claim: "none"` (a value the schema already pins), so there is one code path. The
   alternative — checkout stays receipt-less and `install` requires `--from-checkout` — is defensible
   and keeps a sealed receipt meaning strictly "a verified release artifact." One behavior vs. one
   stronger meaning.
7. **Does Claude Code auto-discover `~/.claude/output-styles/*.md`?** **UNVERIFIED.** If it needs a
   settings key, the `output-style` kind still belongs in the ledger but its activation belongs in the
   merged settings module.
8. **Does `mise where` accept a backend-qualified tool name** (`mise where
   github:Codeseys-Labs/agentic-sdlc`)? **UNVERIFIED** — no mise command was run. If not, §2's trust
   line uses the root printed by `ccodex version` instead. Phase 1 pins whichever works.
9. **Can the unversioned `mise use -g github:…` form ever be claimed?** It fails today for two
   measured reasons — prerelease exclusion and `minimum_release_age` (ADR-0011:182-195). Phase 1's
   non-prerelease tag should fix the first; the second is a mise setting on the *operator's* side, so
   the honest documented form may have to stay exact-version forever.
10. **What is the ledger's practical ceiling?** One user-global document holding N repos × ~28
    project entries plus user entries, read and rewritten under one lock. Fine at N=10; unmeasured at
    N=100. Needs a number before project scope is advertised for fleets.
11. **Report 05's FINDING-1 status is contradictory in the source material** — §a says uninstall
    retires the ledger rows precisely because seed `agentic-sdlc-42ec` found `status` contradicting
    itself, while §b lists it as filed-not-fixed. Phase 3's check is written to settle it by
    execution rather than by reading.
