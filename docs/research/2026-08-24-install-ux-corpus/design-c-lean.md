# Design C — LEAN / NATIVE-CHANNELS-FIRST

**Proposal for:** Codeseys-Labs/agentic-sdlc install architecture
**Written against:** checkout `/tmp/asdlc-research`, v0.7.4, HEAD `e0fbf92`
**Date:** 2026-08-24
**Host measured against:** Claude Code **2.1.241** (`claude --version`, run on this host)

Every claim below is either cited to `path:line` in the checkout, quoted from a live
`code.claude.com/docs` fetch on 2026-08-24, or **[measured]** by a command I ran. Claims I could
not establish are marked **UNVERIFIED** with the reason.

---

## 1. Thesis

The entire conflict-resolution machinery of this installer — the ten-row conflict vocabulary, the
byte-identity ownership doctrine, the adopted/preserved/retargeted/modified taxonomy, the
marketplace-overlap refusal, the six independent state stores, the crash-consistent pending slot
replicated across two substrates, and the 11,188 lines of receipt machinery layered on top — exists
because `bundle:install` writes into `~/.claude/skills/`, `~/.claude/agents/`,
`~/.claude/commands/`, `~/.claude/workflows/` and `~/.claude/hooks/`: **five namespaces the operator
also owns and writes to.** Claude Code's plugin system does not write there at all; it copies a
digest-verified archive into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, a
namespace nothing but that plugin ever occupies. The collision surface is not managed by the lean
design — it is *deleted*, and with it every mechanism that existed to survive a collision. So the
lean proposal is: for the Claude plane, ship nothing but the artifact and let the host install it;
delete `install_skill_bundle.py`'s Claude half, all five `ccodex_sdlc_*` modules, both
receipt-schema modules, `manage_claude_hooks.py`, `manage_claude_workflows.py` and
`bootstrap-agentic-sdlc.sh`; shrink `ccodex` to the four things no native channel does (login-shell
PATH for the gateway, the Codex role-TOML roster, the two `statusLine` settings keys, and gateway
supervision); and answer the operator's four points by *narrowing scope* rather than by adding
mechanism — P1's dependency question stops mattering because the Claude-first core needs no
toolchain at all, P2 is delivered by two `claude plugin` commands with three scopes instead of one,
P3's answer is "ccodex is fit for it but should not be asked to do it", and P4's premise disappears
because after the deletion there is nothing left for a compiled binary to pack. Net arithmetic:
**~32,000 lines deleted against ~255 added**, one bootstrap prerequisite instead of two, two state
stores instead of six, two commands instead of five, zero PATH edits, and a payload whose integrity
is checked fail-closed by the host against a `sha256` the operator can re-derive from three
independent published places.

---

## 1b. The evidence correction that licenses this design

Report 04 concluded that the plugin channel covers "approximately 60%" of the bundle and that the
custom installer is "NECESSARY" because workflows and output-styles have "no plugin schema."
**That conclusion rests on three factual errors.** I checked each against the live documentation and
against Claude Code 2.1.241 on this host. Correcting them is what makes the maximal-deletion case
arguable at all, so the corrections come before the design.

| Report 04 claim | Status | Evidence |
|---|---|---|
| Workflows: "NOT part of the plugin manifest schema. No plugin field, no autodiscovery." **0% coverage. Severity: CRITICAL.** | **WRONG.** `workflows/` is a documented plugin root directory and `workflows` is a documented `plugin.json` field: *"Custom workflow script files or directories (replaces default `workflows/`)"*. The install-tab docs separately list *"plugins that contribute a theme, output style, monitor, or workflow"* as a recognized class. | `code.claude.com/docs/en/plugins-reference` and `/discover-plugins`, fetched 2026-08-24 |
| Output-styles: "NO PLUGIN SUPPORT. Not mentioned in the plugin schema; no autodiscovery mechanism." **0%.** | **WRONG twice.** The reference lists `output-styles/` as a supported component and `outputStyles` as a manifest field. And the repo's **own README already records the observed behaviour**: *"The bundled output style appears as `agentic-sdlc:BLUF`, taking its name from the file's frontmatter rather than its filename"* (`README.md:860-862`). | docs as above; `README.md:860-862` |
| "The `/bundle:install` script handles ALL 34 components" / plugin covers 60% | **Understates the plugin channel by two more components.** `bin/` = *"Executables added to the Bash tool's `PATH` while the plugin is enabled"*, and `hooks/hooks.json` with `${CLAUDE_PLUGIN_ROOT}` substitution is first-class. | `code.claude.com/docs/en/plugins` component table |

Two further facts report 04 did not surface, both load-bearing:

- **Three install scopes exist natively**, exceeding the operator's request for "user or project
  local": `claude plugin install <p>@<m> --scope user|project|local` — **[measured]**
  `claude plugin install --help` on 2.1.241 prints
  `-s, --scope <scope>  Installation scope: user, project, or local (default: "user")`.
  `--scope project` writes `.claude/settings.json` (committed, team-shared); `--scope local` writes
  `.claude/settings.local.json` (personal, in-repo).
- **A fail-closed checksum pin exists.** The `archive` plugin source type takes a `sha256` field:
  *"Claude Code verifies every download against it and refuses the install on a mismatch"*, error
  `Plugin archive integrity check failed`. It *"works without git or npm on the user's machine."*
  (Requires Claude Code ≥ 2.1.224.) Git-based plugin sources additionally take `sha`, a full 40-char
  commit pin, and *"when both `ref` and `sha` are set, the `sha` is the effective pin."*

And one defect I found in the current tree while checking this:

> **[measured] `README.md:216-217` is false on Claude Code 2.1.241.** It claims *"The marketplace
> manifest and `plugin/` both pass `claude plugin validate --strict`."* Run in the checkout:
> `claude plugin validate ./plugin --strict` → **exit 1**; `claude plugin validate ./plugin` →
> exit 0; `claude plugin validate . --strict` → exit 0. The three warnings that `--strict` promotes
> to errors are all the same one, once per component directory:
> *"This directory is a symlink and nothing in it was read — component directories are read without
> following symlinks. A session loading this plugin does follow it, so validate the real directory
> separately."*
>
> So the native channel **works at runtime today but cannot be gated in CI today**, because
> `plugin/` is a directory of symlinks (`plugin/{skills,agents,commands,output-styles,workflows}` →
> `../…`, `git ls-files -s plugin/` shows five `120000` mode entries). Phase 0 below fixes this by
> *building* a dereferenced plugin tree — which is also exactly the artifact an `archive` source
> with a `sha256` needs. One change, two problems.

Finally, report 04's claim that the mise `github:` backend "cannot distribute tree structures" is
also wrong as stated: the repo already publishes tarball releases and `README.md:266-276` documents
`[tools."github:Codeseys-Labs/agentic-sdlc"]` installing a release *tree* whose `bin/ccodex` is the
exposed command. That plane stays — it is just no longer on the Claude-first critical path.

**Net corrected coverage for the Claude plane: 6 of 6 component kinds** (13 skills, 5 commands,
8 agents, 1 hook, 1 output style, 1 workflow), leaving exactly three Claude-side residuals the
plugin schema cannot express: the two `statusLine` settings keys, the operator's *login-shell* PATH
(as distinct from the Bash tool's PATH), and a pre-install host-version refusal. All three are
addressed in §4 and §8.

---

## 2. End-state UX: exact commands a fresh operator types

### 2a. Fresh macOS host — Claude-first core (the 95% case)

Preconditions: Claude Code installed and authenticated. **Nothing else.** No mise, no git, no clone,
no `mise trust`, no toolchain, no PATH edit.

```bash
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git#v0.8.0
claude plugin install agentic-sdlc@agentic-sdlc --scope user
```

Then, to see what you just authorized and confirm it landed:

```bash
claude plugin details agentic-sdlc@agentic-sdlc     # component inventory + token cost
claude plugin list --json                           # id, version, scope, enabled, installPath
```

**Two commands.** Compare with today's five (`README.md:11-15`) that the README itself calls
"Five steps" while listing six numbered items (`README.md:316` vs `:320,328,332,344,354,370`) —
report 01's friction D.1 is deleted, not fixed. There is no headline-vs-Quickstart disagreement
about `--agent` because there is no `--agent` (D.1 second half, deleted). There is no PATH
precondition to fail (D.2, deleted). There is no 1.3 GB toolchain and no `opencodex` 2.28.0 npm
install before the first byte of payload (D.3, deleted). There is no `--dry-run`-to-see-collisions
gap because there is no shared namespace to collide in (D.5, deleted). There is no partial-success
exit 1 across 28 entries because there are no 28 entries — the host installs one archive, atomically
(D.6, deleted). Nothing is installed inert: the hook, workflow and output style are live the moment
the plugin is enabled (D.7, deleted).

### 2b. Fresh macOS host — project scope

In the repository you want it in, one command, plus two committed lines so collaborators get the
same catalog:

```bash
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git#v0.8.0 --scope project
claude plugin install agentic-sdlc@agentic-sdlc --scope project
```

`--scope project` writes `.claude/settings.json`, which you commit. Use `--scope local` instead for
`.claude/settings.local.json` (already reserved by `.gitignore:16-17`) when you want it for yourself
in this repo only.

A collaborator who clones that repo, trusts the folder, and runs
`claude plugin install agentic-sdlc@agentic-sdlc` gets it. They must run that one command — the docs
are explicit that as of v2.1.195 a plugin from an external source *"doesn't load until the team
member installs it."* **That is a feature, not a gap:** it is ADR-0019's per-effect fresh grant
implemented by the host. Committing a settings file cannot install software on a teammate's machine.

### 2c. Fresh macOS host — gateway / routed-model profile (opt-in)

Only operators who want OCX routing, `set-fast-model`, or the Codex plane touch mise at all:

```bash
mise use -g github:Codeseys-Labs/agentic-sdlc@0.8.0     # exact version; prerelease per README.md:266-276
ccodex doctor                                            # read-only; one verdict
ccodex launch                                            # routed Claude Code
```

### 2d. Fresh macOS host — contributor

```bash
git clone https://github.com/Codeseys-Labs/agentic-sdlc.git && cd agentic-sdlc
mise trust ./mise.toml            # review first; no script ever runs this (invariant #27)
mise --locked install
claude --plugin-dir ./plugin      # live-edit loop; session-scoped; no install, no ownership record
mise run check
```

Note what replaced the symlink install: `--plugin-dir` is documented to take precedence over the
installed marketplace plugin for that session, so a contributor tests edits without uninstalling
anything. This is strictly better than the current symlink plane, which leaves an ownership record
and an absolute in-tree source path behind (`install_skill_bundle.py:873-889`).

### 2e. Fresh ubuntu container — core

```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
# install Claude Code per its own front door, then as a non-root user:
```

```bash
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git#v0.8.0
claude plugin install agentic-sdlc@agentic-sdlc --scope user
claude plugin list --json
```

Compare with the recorded fresh-host verification, which needed *"curl, git, ca-certificates plus
mise and Claude Code"*, six steps, ~1.3 GB and 13 tools
(`docs/research/2026-08-08-fresh-host-install-verification.md:30-59`). The lean container needs
**ca-certificates and Claude Code**; `git` is not required because the `archive` source *"works
without git or npm on the user's machine"*, and `curl` is only needed by Claude Code's own
installer. **The Claude plane's bootstrap prerequisite count goes from two (mise + Claude Code) to
one (Claude Code)** — and since you cannot use a Claude Code plugin without Claude Code, that one is
not a *second* prerequisite at all. This is the cleanest possible compliance with ADR-0002's
"no second bootstrap prerequisite" rule (`docs/adr/0002-…:45-49`, `:88-91`): the lean design does
not merely avoid adding a prerequisite, it **removes** the one ADR-0002 was written to protect.

### 2f. Fresh ubuntu container — CI / offline verification of what landed

```bash
curl -fsSLO https://github.com/Codeseys-Labs/agentic-sdlc/releases/download/v0.8.0/agentic-sdlc-plugin-0.8.0.zip
sha256sum -c <(grep 'agentic-sdlc-plugin-0.8.0.zip' SHA256SUMS)
unzip -l agentic-sdlc-plugin-0.8.0.zip     # must contain no package.json, lockfile, .mcp.json, bin/
```

---

## 3. Component / layer diagram

```
                        ACQUISITION                      ACTIVATION                  STATE OWNER
                        (who fetches bytes)              (who places them)
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ CLAUDE PLANE  — the product's primary host (ADR-0017)                                         │
│                                                                                               │
│   GitHub release ──── archive source ────► Claude Code ──────► ~/.claude/plugins/cache/       │
│   agentic-sdlc-plugin-<v>.zip             fail-closed          agentic-sdlc/agentic-sdlc/<v>/  │
│   + sha256 in marketplace.json            sha256 check                                        │
│                                                                                               │
│   catalog: .claude-plugin/marketplace.json (git, pinned by #<tag>)                            │
│                                                                                               │
│   carries: 13 skills · 5 commands · 8 agents · hooks/hooks.json · 1 output-style · 1 workflow  │
│   scopes:  --scope user | project | local        (3 settings files, host-owned)                │
│                                                                                    ┌──────────┤
│   agentic-sdlc code in this path:  ZERO LINES AT RUNTIME                            │  HOST    │
│   agentic-sdlc code at build time: build_release.py + validate_bundle.py             │ (Claude) │
└─────────────────────────────────────────────────────────────────────────────────────┴──────────┤
                                                                                                │
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ ccodex — everything native channels cannot do, and nothing else                                │
│                                                                                               │
│   acquisition:  mise use -g github:Codeseys-Labs/agentic-sdlc@<v>   (release tree, bin/ccodex) │
│                 or a contributor checkout                                                     │
│                                                                                               │
│   ┌──────────────────────┬────────────────────────────┬─────────────────────────────────────┐ │
│   │ ccodex doctor        │ ccodex host … --host codex │ ccodex statusline …                 │ │
│   │ READ-ONLY            │ Codex role TOMLs +         │ 1 owned file + 2 settings keys      │ │
│   │ reads:               │ skills tree for hosts      │ (statusLine.type/.command)          │ │
│   │  claude plugin       │ with no native channel     │ ── the ONLY custom Claude-side      │ │
│   │    list --json       │                            │    activation that survives         │ │
│   │  + ccodex ledger     │ ledger: state.json v5      │ ledger: same v5 doc                 │ │
│   │  + re-hash of        │ kinds: {skill, agent}      │                                     │ │
│   │    installPath       │ hosts: {codex, skills-tree}│                                     │ │
│   └──────────────────────┴────────────────────────────┴─────────────────────────────────────┘ │
│                                                                                    ┌──────────┤
│   ┌──────────────────────────────────────────────────────────────────────────────┐ │ ccodex   │
│   │ GATEWAY PLANE (unchanged; never a gate, never a dependency — ADR-0005)        │ │ (2 stores│
│   │ ccodex launch | status | restart | configure | providers | models |           │ │  total)  │
│   │ set-fast-model   ── scripts/opencodex-claude.sh                                │ │          │
│   └──────────────────────────────────────────────────────────────────────────────┘ │          │
└─────────────────────────────────────────────────────────────────────────────────────┴──────────┤
                                                                                                │
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ CONTRIBUTOR PLANE (unchanged)                                                                 │
│   git clone · mise trust · mise --locked install · claude --plugin-dir ./plugin · mise run     │
│   check · mise run release:build · lefthook                                                   │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

Layers, counted: today's stack is **eight** (report 01 §A.2, LAYER 0–7) with **four** independent
acquisition planes and **five** separately-authorized activations. The lean stack is **three**
(host plane / ccodex plane / contributor plane) with **two** acquisition planes and **one**
surviving separately-authorized activation (the statusline).

---

## 4. The ownership / state data model

*Named before the mechanisms, per the design principle. Everything in §5 and §6 follows from this
table; if the table is wrong the rest is wrong.*

### 4.1 Three owners, two ledgers, no third

| Owner | What it owns | Where | Identity of "what is active" | Who verifies |
|---|---|---|---|---|
| **Claude Code (host)** | the entire Claude plane | `~/.claude/plugins/cache/<mkt>/<plugin>/<version>/` + `enabledPlugins` in one of three settings files + `known_marketplaces.json` | `(marketplace, plugin, version, archive sha256)` | the host, fail-closed, before any file lands |
| **ccodex** | Codex roster + skills-tree hosts + the statusline + the PATH file | one `state.json` **v5**, mode `0600`, one sibling `installer.lock` | byte digest per destination (unchanged doctrine) | ccodex |
| **gateway** | `~/.codex`, ocx logs | `$XDG_STATE_HOME/agentic-sdlc/ocx-logs` | `ocx health` (the only verdict — invariant #20) | `ocx` |

**Six stores become two.** Deleted outright: the operator-tools store (folded into the one ledger),
the statusline receipt (same), the hooks receipt store, the workflows receipt store, the
`ccodex sdlc` acquisition + activation receipt planes, and the bootstrap receipt. Report 01's
friction D.4 — *"the aggregated reader projects only two of six stores"* — is resolved by there
being two.

### 4.2 The host-owned record: why it is a better receipt than the one we build

**[measured]** `claude plugin list --json` on this host returns, per plugin:

```json
{ "id": "<plugin>@<marketplace>", "version": "1.0.6489947954", "scope": "user",
  "enabled": true, "installPath": "/Users/…/.claude/plugins/cache/<mkt>/<plugin>/<version>",
  "installedAt": "2026-07-25T00:58:38.509Z", "lastUpdated": "2026-07-25T00:58:38.509Z" }
```

Compare against `distribution-activation-body@1`, which `scripts/distribution_activation_receipt.py`
spends 1,917 lines defining and `scripts/ccodex_sdlc_install.py:1634-1718` seals. The host record
carries **scope** (which our receipt does not model at all — report 05: project scope is
"structurally absent"), **installedAt/lastUpdated** (ours records neither), **enabled** (ours cannot
express installed-but-disabled), and an `installPath` that is a *versioned, side-by-side* directory
— i.e. the "versions live side by side so rollback is selecting the earlier release" property
ADR-0021 promised (`docs/adr/0021-…:38-40`) and report 05 found unimplemented ("no rollback,
downgrade, or channel verb").

What the host record does *not* carry is a re-hash of the live bytes. **That is ~60 lines in
`ccodex doctor`:** read `installPath` from `--json`, re-hash the tree against the published
`manifest.json` for that version, report agreement. That is the entire irreducible value of the
acquisition receipt — 11,188 lines of machinery replaced by a read of a host-authored inventory plus
one digest comparison, and the comparison is now against bytes the host itself verified fail-closed
on the way in.

### 4.3 The ccodex ledger, v5 — closed schema, narrowed

```
{ "version": 5,
  "entries": {
    "<absolute destination>": {
      "host":      "codex" | "skills-tree" | "operator",
      "kind":      "skill" | "agent" | "command-file",
      "name":      <basename>,
      "source":    <absolute str>,
      "mode":      "copy" | "link" | "junction",
      "digest":    <64 lowercase hex>,
      "removable": <bool>
    }, … },
  "pending": <one armed install|refresh|uninstall transition, or null> }
```

Changes from v4 (`install_skill_bundle.py:127-135`, `:76`, `:873-889`):

- `agent` → `host`, and `"claude"` is **not an admissible value.** A v5 document naming host
  `claude` is a refused record. This is the schema-level enforcement that there is no second Claude
  plane, replacing `marketplace_overlap()` (`install_skill_bundle.py:939-955`, `:1328-1342`) — a
  function whose whole job was arbitrating between two Claude planes that no longer both exist.
- Kinds drop from five to three. `command`, `workflow` and `hook` were Claude-only
  (`install_skill_bundle.py:71`, and the workflow/hook rows of report 01 §A.3). `command-file`
  exists only for the statusline script and the `ccodex` launcher, folding in the operator-tools
  store's three-field record (`install_operator_tools.py:380-388`) rather than keeping a second
  document with a second version number and a second lock.
- The record validator's hardcoded `.claude` grandparent assertion
  (`install_skill_bundle.py:377-378`) is deleted with the Claude plane. That assertion is precisely
  what report 01 §E.2 item 3 identified as making project scope express-ible only as
  "a `.claude` dir inside the project" — a constraint that evaporates because project scope is now
  the host's `--scope project`, not a directory we choose.
- **`state_directory()` keeps `Path.home()`** (`install_skill_bundle.py:220-230`, pinned by
  `tests/test_install_skill_bundle.py:819`). The trap report 01 §E.2 documented — a repo-local
  `--claude-home` whose ownership lives in the user's global document, plus a `legacy_state_path`
  that can spuriously resolve to `<repo>/.local/state` — is deleted along with `--claude-home`
  itself. Nothing in v5 takes a repository as a destination root.

### 4.4 Invariants: what survives, what changes class, what goes

Report 01 catalogued 52 deliberate invariants. Under the lean design:

**Survive unchanged (28):** the whole fail-closed refusal family for the surviving planes (#1–5,
#6–9, #11, #12, #15, #16, #19), never-runs-`mise trust` (#27), never-edits-PATH as its own exit-3
`HostPreconditionError` raised before the lock (#25, #26), the gateway's `ocx health`-only verdict
and jq admission (#20, #21, #22, #23), help-is-never-effectful (#34), dry-run writes nothing and
takes no lock (#35–#38), the exit ladder 0/1/2/3/4 as one derivation point per module (#49), the
one-file PATH plane (#50), `AGENTIC_SDLC_ROOT` (#51), the node-PATH-prepend consequence (#52),
`operational_path()` not resolving aliases (#45), private-staging `0700` siblings created beside the
destination (#47), leftover siblings named-never-removed (#48), self-test as a gate leaf (#42–#44).

**Deleted because the thing they protect is deleted (14):** #10 (codex-home-is-repo-root survives;
its `--claude-home` sibling goes), #13 (marketplace overlap), #14 and #17 (the unsubstituted-
placeholder refusal and the executed-assertion that the uv-managed CPython is exactly `3.12.11` —
both exist to protect `@PINNED_SDLC_PYTHON@`, which exists to run the Python entrypoints being
deleted), #28's hook half and workflow half, #29 (the statusline stays; its `exact_owned_statusline`
guard stays — only #29's *inert-until-activated* framing for hooks/workflows goes), #30, #33 partly,
#39, #40, #41, #46.

**Changes class, and must be relabeled rather than quietly dropped (2).** ADR-0019 requires controls
be *labeled* mechanical / observed / advisory (`docs/adr/0019-…:28-40`), not that all be mechanical.
Two controls move down a class:

1. **Host-version compatibility.** `check_compatibility` (`ccodex_sdlc_install.py:938-1009`) observes
   `claude --version` and refuses below `minimum_host_version` (`policy/release-contract.v1.json`:
   `2.1.154`) or on `known_incompatible_host_versions`. **The plugin manifest has no
   minimum-host-version field** — I read the full schema field list
   (`name, displayName, version, description, author, homepage, repository, license, keywords,
   metadata, skills, commands, agents, hooks, mcpServers, outputStyles, lspServers, experimental,
   dependencies, userConfig, channels, defaultEnabled`) and there is no `engines`/`requires`
   equivalent. So this control goes **mechanical → observed**: the shipped `hooks/hooks.json`
   SessionStart hook reads `claude --version` and emits a refusal card, *every session*, and
   `ccodex doctor` refuses to certify. Weaker in force, stronger in kind: today's check runs once at
   install time and is silently stale the moment the operator upgrades or downgrades the host.
2. **Per-hook authorization.** Today wiring a hook into `settings.json` is a separate authorized
   step and `~/.claude/hooks/` is not an auto-discovery surface (`install_skill_bundle.py:305-320`;
   invariant #28). Under the plugin channel, enabling the plugin enables the hook. The grant moves
   from per-hook to per-plugin — but the host *displays the hook inventory before install*
   (`claude plugin details` prints commands, skills, agents, hooks, MCP and LSP servers; the
   interactive **Will install** pane the same), and **the shipped hook already implements per-repo
   opt-in in its own payload**: `hooks/session-start-routing-primer.sh:7-14` exits 0 with zero bytes
   of stdout unless `.seeds/issues.jsonl` is a regular non-symlink file **and** `AGENTS.md` carries
   the `/sdlc-init` activation marker. That gate is the authorization. `manage_claude_hooks.py`'s
   522 lines (plus 386 test lines) are a second, coarser copy of a control the payload already
   carries — which is exactly the "remove dead weight before adding a layer" case.

---

## 5. What gets DELETED from the current tree

### 5.1 Deleted outright

| Path | Lines | Why it goes |
|---|---|---|
| `scripts/ccodex_sdlc.py` | 1,816 | grammar/dispatcher/reader for a lifecycle the host now owns |
| `scripts/ccodex_sdlc_install.py` | 1,999 | acquisition admission + copy-activation → `archive` source + host cache |
| `scripts/ccodex_sdlc_update.py` | 2,581 | → `claude plugin update`, gated by our `version` bump |
| `scripts/ccodex_sdlc_uninstall.py` | 1,391 | → `claude plugin uninstall [--prune]` |
| `scripts/ccodex_sdlc_recover.py` | 926 | resumes one interrupted transaction of a transaction that no longer exists |
| `scripts/ccodex_sdlc_readonly.py` | 225 | stdlib monkey-patching to keep a reader from writing; the reader is now `claude plugin list --json` + one digest read |
| `scripts/write_acquisition_receipt.py` | 333 | replaced by the host's fail-closed `sha256` check |
| `scripts/distribution_activation_receipt.py` | 1,917 | replaced by `claude plugin list --json` (§4.2) |
| `scripts/manage_claude_workflows.py` | 542 | workflows are a plugin component; project scope is `--scope project` |
| `scripts/manage_claude_hooks.py` | 522 | hook is `hooks/hooks.json`; its gate is its authorization (§4.4) |
| `scripts/bootstrap-agentic-sdlc.sh` | 280 | managed the clone; the Claude plane needs no clone |
| `policy/ccodex-sdlc-read-report.v1.json` + `.v2.json` | — | v2 was never read at all (report 05: *"`ccodex_sdlc.py` never opens the v2 file"*, despite `validate_bundle.py:1699` claiming both are parsed every invocation) |
| **15 test files** (`test_ccodex_sdlc*.py` ×7, `test_write_acquisition_receipt.py`, `test_distribution_activation_receipt.py`, `test_manage_claude_hooks.py`, `test_manage_claude_workflows.py`, `test_hook_entry_kind.py`, `test_workflow_entry_kind.py`, `test_bootstrap_agentic_sdlc.py`, `test_install_lifecycle_prototype.py`) | 13,229 | |
| **Subtotal deleted outright** | **≈ 25,761** | |

### 5.2 Narrowed (estimates, marked as such)

| Path | Now | Target | Delta |
|---|---|---|---|
| `scripts/install_skill_bundle.py` | 1,848 | ~900 | −948 |
| `tests/test_install_skill_bundle.py` | 1,851 | ~1,000 | −851 |
| `scripts/install_operator_tools.py` + `scripts/manage_claude_statusline.py` → one module | 1,709 | ~600 | −1,109 |
| `tests/test_operator_tools.py` + `test_manage_claude_statusline.py` + `test_claude_statusline.py` | 2,178 | ~700 | −1,478 |
| `bin/ccodex` + `assets/launchers/ccodex.in` → **one** dispatcher | 844 | ~400 | −444 |
| `tests/test_bin_ccodex.py` | 426 | ~300 | −126 |
| `tests/test_lifecycle_exit_conformance.py` | 2,488 | ~1,200 | −1,288 |
| **Subtotal narrowed** | | | **−6,244** |

The two-dispatcher collapse deserves its own note. Report 01 §A.5 documents three declared
divergences between committed `bin/ccodex` and rendered `assets/launchers/ccodex.in`, and six
install-time absolute bindings in the latter (`@PINNED_BASH@`, `@CANONICAL_ROOT@`,
`@CANONICAL_LAUNCHER@`, `@PINNED_OCX@`, `@PINNED_JQ@`, `@PINNED_UV@`, `@PINNED_NODE@`,
`@PINNED_SDLC_PYTHON@` — `install_operator_tools.py:350-361`). Delete the Python entrypoints and
`@PINNED_UV@` and `@PINNED_SDLC_PYTHON@` go with them, along with the
`uv python find --managed-python --offline --no-python-downloads 3.12.11` lookup whose failure
message names a command that cannot fix it (report 01 friction D.3, UNVERIFIED end-to-end but
structurally sound). Report 05's most important finding — that **every `ccodex sdlc` verb currently
exits 3 against the only downloadable release** because its dispatcher routes through
`uv run --script` without `-I -B`, failing `runtime_admission()` — is deleted rather than fixed: the
exact-CPython-patch-plus-exact-isolation-flags admission gate exists only to protect the modules
being removed.

### 5.3 Stretch deletion (argued, not required)

`scripts/install_external_libraries.py` (1,658) + `tests/test_external_libraries.py` (1,495) =
**−3,153**. It owns no state of its own (report 01 §B.2); it reads Claude's
`installed_plugins.json` / `known_marketplaces.json` and a foreign skills-CLI lock
(`:436-465`) and wraps other people's front doors. Under the lean design, an external Claude library
*is* another marketplace: `claude plugin marketplace add <theirs>`. ADR-0009/ADR-0029's doctrine —
external tools through their own front doors, never vendored — is satisfied *better* by naming the
front door in documentation than by wrapping it in 1,658 lines. **Caveat:** non-Claude hosts and
non-plugin libraries still need a route, so this is proposed as a separate decision, not folded into
the main deletion.

### 5.4 Also retired

- **mise tasks:** `bundle:install:claude`, `bundle:install:all-hosts`/`bundle:status:all-hosts`'
  Claude legs, `claude:hooks:{status,activate,deactivate}`, `claude:workflows:{status,activate,
  deactivate}` (`mise.toml:222-247`). Note these seven were never documented in the README at all
  (report 01 friction D.8) — deleting an undocumented task costs no documentation.
- **`marketplace_overlap()`** and its two call sites and two tests
  (`install_skill_bundle.py:939-955`, `:1328-1342`; `tests/test_install_skill_bundle.py:588,608`).
- **`validate_bundle.py`'s `.sh`-only hook rule** (`:808-813`) whose in-line comment states it *"is
  also what structurally refuses a plugin-channel `hooks.json` in this tree"* — the single most
  literal statement in the codebase that the current design deliberately blocked the native channel.
- **The `--claude-home` / `--home` flag** (`install_skill_bundle.py:1794-1802`) and the
  `state_directory()` / `legacy_state_path` interaction it makes hazardous.

### 5.5 Arithmetic

```
deleted outright          25,761
narrowed                   6,244
                          ------
conservative total        32,005 lines removed
stretch (ext. libraries)   3,153
                          ------
with stretch              35,158

added:
  build_release.py: deterministic plugin zip + SHA256SUMS row     ~40
  .github/workflows/release.yml (Install-UX plan step 7, undone)  ~30
  hooks.json generator + plugin.json component fields             ~25
  validate_bundle.py: assert absent capabilities in built plugin  ~40
  ccodex doctor: read `claude plugin list --json`, re-hash        ~120
                                                                  ----
                                                                  ~255
net                       ≈ −31,750       ratio ≈ 125 : 1
```

**[measured]** The install/lifecycle machinery in this checkout is **37,214 lines** (16,933 script +
20,281 test), excluding the gateway (`opencodex-claude.sh`, 2,681) and external libraries (3,153).
After the conservative deletion it is **~5,200 lines, plus ~255 added ≈ 5,460** — i.e.
**86% of the install machinery deleted**, and against the overengineering audit's 210,528 tracked
lines, ~15% of the repository — consistent with that audit's own rank-3 recommendation to replace
the release-candidate acquisition engine, and using the same lever ADR-0022's 2026-08-22 amendment
already established: *"the machine-local receipt never had a reader… 70 records in 151 orphan
directories… no tool, task, gate, hook, CI job, or skill ever read one back."* The
distribution-activation receipt's only reader is the same module family that writes it. That is the
identical finding, one ADR later.

---

## 6. Migration path in verifiable phases

Each phase ends in a check that can fail. No phase deletes anything whose replacement has not
already passed its own check.

### Phase 0 — Make the native channel strictly valid and checksum-pinnable

Changes: build a **dereferenced** plugin tree at release time (`plugin/` stays as the
`--plugin-dir` dev surface); generate `hooks/hooks.json` from `hooks/*.sh`'s declared headers with
`"command": "\"${CLAUDE_PLUGIN_ROOT}\"/hooks/<name>.sh"`; add the `hooks`, `workflows`,
`outputStyles` component fields to `plugin.json`; emit `dist/agentic-sdlc-plugin-<v>.zip` with fixed
mtimes and sorted entries; add its sha256 to `dist/SHA256SUMS`; extend `validate_bundle.py` to
assert the built tree contains **no** `package.json`, no `bun.lock*`/`package-lock.json`/
`npm-shrinkwrap.json`, no `.mcp.json`, no `.lsp.json`, no `monitors/`, no `bin/`, no `settings.json`.
Delete the `.sh`-only hook rule at `validate_bundle.py:808-813`.

**CHECK (all must hold):**
1. `claude plugin validate dist/plugin --strict` → **exit 0**. *(Today: `claude plugin validate
   ./plugin --strict` → exit 1, **[measured]** on 2.1.241.)*
2. Two builds of the same commit produce **byte-identical** zips (`sha256` equal). This is the
   control ADR-0031 fact 4 says the repo *"will not trade away"*; a zip is only deterministic if
   mtimes and entry order are normalized, so this check is load-bearing, not ceremonial.
3. `claude --plugin-dir dist/plugin` then `claude plugin details` (or `/plugin`) enumerates
   **13 skills, 5 commands, 8 agents, 1 hook, 1 output style, 1 workflow** — the exact inventory
   report 01 §A.3 measured.
4. In a scratch repo containing `.seeds/issues.jsonl` and an `AGENTS.md` activation marker, the
   SessionStart hook emits its card; in a scratch repo without them it emits zero bytes. This is the
   test that `manage_claude_hooks.py` was redundant.

### Phase 1 — Publish the archive-sourced, sha256-pinned entry; prove a zero-mise, zero-git install

Changes: `.github/workflows/release.yml` (Install-UX plan step 7, recorded as **not done**) tags,
builds both archives, uploads them, and writes the archive `sha256` into
`.claude-plugin/marketplace.json`'s plugin entry as an `archive` source. Nothing is deleted.

Note the ordering that makes this non-circular: the plugin zip is built from `plugin/` only, and
`marketplace.json` lives at `.claude-plugin/`, **outside** the zip. So computing the digest at
commit N, writing it into the catalog, and tagging N+1 yields a catalog whose digest still matches
the archive, because `plugin/` did not change between N and N+1.

**CHECK:**
1. Fresh `ubuntu:24.04` container, non-root, with **only** `ca-certificates` and Claude Code — no
   git, no mise, no node:
   `claude plugin marketplace add https://github.com/…/agentic-sdlc.git#v0.8.0` then
   `claude plugin install agentic-sdlc@agentic-sdlc --scope user` → exit 0.
   *(If the marketplace add needs git, use a hosted `marketplace.json` URL; the archive fetch itself
   is documented to need neither git nor npm. Which of the two catalog forms works git-free in a
   container is **UNVERIFIED** and is Phase 1's real risk.)*
2. `claude plugin list --json | jq -e '.[] | select(.id=="agentic-sdlc@agentic-sdlc") | .enabled'`
   → true, with the expected `version`.
3. **Negative test:** flip one hex character of the `sha256` in a local copy of the catalog; install
   must refuse with `Plugin archive integrity check failed`. A fail-closed control that has not been
   observed failing closed is not a control.
4. Record the host floor rising from **2.1.154** to **2.1.224** (`archive` source minimum) as a new
   ADR-0027 compatibility-tuple row. `policy/release-contract.v1.json` already names 2.1.224 as its
   `stable` nomination-regression reference, so the floor moves to a version the contract already
   cites.

### Phase 2 — Retire the old Claude plane, **in the outgoing release**

The design principle "do not preserve throwaway compatibility states in the target architecture" is
satisfied by putting the migration in the version being retired, not the one being shipped. So:

- **v0.8.x (last release of the old shape)** ships `bundle uninstall --agent claude` unchanged, plus
  one deprecation line in its output naming the two `claude plugin` commands. No new code.
- **v0.9.0 (first release of the new shape)** does not accept a v4 state document at all. Its
  refusal names the remedy: *"install v0.8.x, run `ccodex bundle uninstall --agent claude`, then
  reinstall."* This preserves invariant #1 (one schema, no migration, no `--migrate-state`,
  `install_skill_bundle.py:266-289`) rather than weakening it.

**CHECK:** on a host with the old plane installed, `ccodex bundle uninstall --agent claude` → exit 0
and `ccodex bundle status --agent claude` → `no owned entries for this host`; then
`claude plugin install …` lands with zero `conflict:` lines. Then, on that same host, a v0.9.0
`ccodex` reading the surviving v4 document refuses by name at exit 3 with the remedy in the message.

### Phase 3 — Delete

Execute §5. Order: tests first (delete the 15 test files, watch `mise run check` go green with fewer
tests), then the modules they covered, then the narrowings, then the mise tasks, then the README.

**CHECK:**
1. `mise run check` green (= `validate + test + self-test + secrets`, `mise.toml:154-156`).
2. `rg 'ccodex_sdlc|manage_claude_hooks|manage_claude_workflows|marketplace_overlap|write_acquisition_receipt|distribution_activation_receipt'`
   returns hits **only** under `docs/adr/` and `docs/research/` (history, not machinery).
3. `tests/test_lifecycle_exit_conformance.py` still enumerates every surviving module — the exit
   ladder is contract (report 02 constraint 11) and a shrinking module list must not silently drop
   a module from the conformance scan.
4. `ccodex doctor` on a fresh host emits **one** verdict spanning the host plane and the ccodex
   ledger, and `git ls-files | xargs wc -l` is down by at least 30,000.
5. README's task table matches `mise tasks` exactly — the claim at `README.md:463` that it lists
   every task is currently false by eight (report 01 D.8) and this is the phase that makes it true
   by deletion.

### Phase 4 — Project scope, natively

Changes: `commands/sdlc-init.md` teaches the two `--scope project` commands.
`skills/agentic-sdlc/tools/instruction-generator.py` gains one output kind that writes the
`extraKnownMarketplaces` + `enabledPlugins` pair into `<target>/.claude/settings.json` under the
same render-against-live-target, print-the-diff, write-only-with-`--yes` discipline ADR-0022's
amendment converged on (`docs/adr/0022-…:110-120`). **No plan digest, no repo receipt, no
`.agentic-sdlc/repo.toml`** — the machinery that amendment deleted is not resurrected; it is
replaced by a host primitive.

**CHECK:** in a scratch repo, `instruction-generator.py apply --target . --entry
project-plugin-scope --yes` writes **exactly two keys** and `git diff --name-only` shows only
`.claude/settings.json`. Without `--yes`: exit 3, diff printed, nothing written
(`instruction-generator.py:85-92`, `:313-336`). A second repo gets its own independent enablement
with no shared state — the property `--claude-home` could not provide (report 01 §E.2 item 1).

### Phase 5 — ADR bookkeeping

One new ADR, *Distribute the Claude plane through Claude Code's native plugin marketplace*:

- **Supersedes ADR-0011 for the Claude plane** with the full evidence set that ADR-0011's own
  reversal condition demands (`docs/adr/0011-…:160-165`): archive builder ✅ (`build_release.py` +
  Phase 0), release workflow ✅ (Phase 1), copy activation ✅ (the host copies, satisfying the
  "`mise prune` must not break Claude's skills" reason at `docs/plans/…:185` — and satisfying it
  *better*, since the cache is not under a prunable mise directory at all), clean-host tests ✅
  (Phase 1 check 1), first release ✅.
- **Narrows ADR-0021** to non-plugin hosts and **retires its acquisition/activation-receipt items**
  on the ADR-0022-amendment precedent (no independent reader). ADR-0021 is `proposed`
  (`docs/adr/0021-…:3`), and per ADR-0028's own compliance rule *"a proposed child is not presented
  as a current product constraint"* (`:112`) — so this narrows a target, not an obligation.
- **Records the two control reclassifications** of §4.4 explicitly, per ADR-0019's labeling
  requirement.
- **Leaves ADR-0031 entirely untouched.** See §8.
- Records the ADR-0027 tuple row from Phase 1 check 4.

**CHECK:** `mise run validate`'s ADR-lifecycle checks pass; no document cites ADR-0021 as a current
constraint for the Claude plane; ADR-0011's status changes with its named evidence attached.

---

## 7. Supply-chain story

### 7.1 The trust chain, end to end

```
git tag v0.8.0  ──(public, reviewable diff)──►  .claude-plugin/marketplace.json
                                                  └─ source: {archive, url, sha256: <64hex>}
                                                                     │
GitHub release asset  agentic-sdlc-plugin-0.8.0.zip ─────────────────┤
  + dist/SHA256SUMS (same digest, second published location)         │
                                                                     ▼
                                          Claude Code downloads, hashes, and
                                          REFUSES THE INSTALL ON MISMATCH
                                          ("Plugin archive integrity check failed")
                                                                     │
                                                                     ▼
                                    ~/.claude/plugins/cache/agentic-sdlc/agentic-sdlc/0.8.0/
                                                                     │
                        ccodex doctor re-hashes installPath against manifest.json  ◄──┘
```

The same digest appears in **three independently published places** — the tag's
`marketplace.json`, the release's `SHA256SUMS`, and the archive itself — and the operator can
compute a fourth with `sha256sum`. Any disagreement is a stop.

### 7.2 What the operator reviews before trusting, concretely

1. **The tag diff.** `git diff v0.7.4..v0.8.0` on a public repo. The payload is ~25 markdown files,
   one 51-line POSIX shell hook, one 108-line JS workflow, and one JSON hook manifest.
2. **The digest, three ways.** `curl -O` the archive; `sha256sum` it; compare against `SHA256SUMS`
   and against `marketplace.json`'s `sha256` at that tag.
3. **`unzip -l`.** The archive must contain only `.claude-plugin/plugin.json`, `skills/`, `agents/`,
   `commands/`, `hooks/hooks.json`, `output-styles/`, `workflows/`. **Each absent thing is a
   capability deliberately not shipped**, and Phase 0's validator asserts each absence so the review
   is a checklist, not a reading exercise:
   - no `package.json` **and** no lockfile → Claude Code's dependency install *"runs only when the
     plugin's root directory contains both a `package.json` and a supported lockfile"*, and even
     then it runs `npm ci --ignore-scripts` / `bun install --frozen-lockfile --ignore-scripts`. Ship
     neither and **zero package-manager activity occurs at install time.** This is the mechanical
     answer to ADR-0002's amendment concern — *"a postinstall that extracts an archive or downloads
     a browser is suspect"* (`docs/adr/0002-…:142-151`) — and it is stronger than the current
     posture, where `mise --locked install` runs `npm:@bitkyc08/opencodex` 2.28.0 whose integrity
     surface is, by ADR-0005's own admission, *"version+backend only, no tarball hash and no
     transitive integrity"* (`docs/adr/0005-…:218-222`).
   - no `.mcp.json`, no `.lsp.json`, no `monitors/` → no server is registered, nothing is spawned in
     the background.
   - no `bin/` → nothing is added to the Bash tool's PATH.
   - no `settings.json` → no default `agent` or `subagentStatusLine` is imposed.
4. **`hooks/hooks.json` and the one script it names.** This is the *only* thing in the payload that
   executes automatically. It is 51 reviewed lines whose first act is a two-predicate gate, and
   whose emitted card is *"fixed reviewed bytes emitted through a quoted heredoc. No repository
   content… is ever interpolated"* (`hooks/session-start-routing-primer.sh:19-22`).
5. **`claude plugin details agentic-sdlc@agentic-sdlc`** — the host's own inventory of what will be
   contributed, plus a projected per-turn token cost, before enabling.

**Compare the reviewable surface.** Today, trusting the Claude plane means trusting: `mise.toml`'s
12 pins totalling ~1.3 GB, including an npm package with no tarball hash; a `mise trust` grant that
is per-absolute-path and not inherited by linked worktrees (`README.md:457-461`); 21,580 lines of
installer script; and — if you take the marketplace route instead — a git clone at a mutable tag.
Under the lean design the reviewable surface is **smaller than today's installer alone.**

### 7.3 Honest limitations

- **The catalog is not digest-pinned.** Marketplace sources support `ref` (branch/tag) but *not*
  `sha`; only *plugin* sources take `sha`/`sha256`. So a publisher who moves a tag can point the
  catalog at a different archive with a matching digest. The mitigations are: HTTPS + git
  authenticate the transport and the repository, the tag diff is public, the digest is published in
  a second place the same commit produced, and an organization can lock the catalog via managed
  `extraKnownMarketplaces` / `strictKnownMarketplaces`. This is the same honest limitation ADR-0011
  already records — *"HTTPS authenticates transport not contents"* (`:120-130`) — not a new one.
- **Auto-update is a host-owned update authority.** Claude Code refreshes marketplaces and updates
  plugins in the background after session start. Mitigations, in order of strength: third-party and
  local marketplaces have **auto-update disabled by default**; a declared `version` field means
  *"users only receive updates when you change this field"*; `DISABLE_AUTOUPDATER` exists. Whether
  those three together *guarantee* no silent version change is **UNVERIFIED** and is open question
  Q6 — it is the one place ADR-0020 item 4 (*"ordinary commands never silently resolve, install,
  update, replace, or fall back"*, `:36-37`) is at risk. **But note the trade:** the update
  authority is the *host's*, not a second one we built. ADR-0021 rejected a self-updating binary
  because *"it creates a second update authority before the receipt-backed lifecycle is proven"*
  (`:24-26`). Consuming the host's is not creating a second one.
- **Determinism of a zip.** `git archive` is already deterministic; a zip is not unless mtimes and
  ordering are normalized. Phase 0 check 2 makes this a gate, and it must be measured, not assumed.
- **We now depend on a vendor's schema.** If Anthropic changes the plugin component set, we have no
  fallback in the Claude plane. The mitigation is real but partial: the `skills/` tree remains the
  portable layer (`README.md:25-33`) and `install_skill_bundle.py` still exists for hosts with no
  native channel, so the fallback is to widen it back — at the cost of the code we deleted.

---

## 8. Explicit tradeoffs vs the status quo

| Axis | Status quo (v0.7.4) | Lean / native-channels-first | Verdict |
|---|---|---|---|
| Commands to a working Claude plane | 5 (README headline) / 6 (Quickstart), which disagree on `--agent` | **2** | **win** |
| Bootstrap prerequisites for the Claude plane | mise **+** Claude Code (+ git, + `mise trust`) | **Claude Code only** | **win**; strongest ADR-0002 compliance available |
| Bytes before the first skill exists | ~1.3 GB, 12–13 tools, incl. opencodex 2.28.0 → bun 1.3.14 (89 MB) | one plugin zip (~1 MB, **unmeasured**) | **win** |
| PATH edit required | yes, exit-3 `HostPreconditionError`; recovery is edit-rc → new shell → re-run | **none** for core; one file for gateway users only | **win** |
| Who verifies payload integrity | we do, by digesting a tree we cloned over HTTPS | the **host**, fail-closed, against a published `sha256`, before any file lands | **win on mechanism, loss on control** — we no longer own the check |
| Collision handling | 10-row conflict vocabulary, `preserved:` pairs, one conflict → exit 1 across 28 entries | **no shared namespace ⇒ no collisions expressible** | **win** |
| "Am I installed?" | 7 commands across 6 stores; aggregator reads 2 of 6; `status` structurally cannot see a collision | `claude plugin list --json` + `ccodex doctor` over 2 stores | **win** |
| Project scope | none designed; only `manage_claude_workflows --target`, for one kind; `--claude-home` is a trap whose state is user-global | `--scope user|project|local`, **all** components, host-owned state | **win** |
| Update | re-run `bundle:install` (refreshes every copy entry every run) | `claude plugin update`, gated by our `version` bump | **win**, with Q6 risk |
| Rollback / downgrade | none (report 05: no verb exists despite ADR-0021 promising one) | pin an older `version`/`sha256`; the cache is already versioned side-by-side | **win** |
| Contributor edit loop | symlink install into `~/.claude` + ownership record | `claude --plugin-dir ./plugin` (session-scoped, precedence over installed, no record) | **win** |
| Hook authorization granularity | per-hook mise task, hook inert until wired | per-plugin enable; hook self-gates on 2 repo predicates; host displays hook inventory pre-install | **loss in granularity, no loss in effect** — §4.4 |
| Host-version compatibility refusal | mechanical, at install time, once (`check_compatibility`) | **observed**, every session, via the shipped hook + `ccodex doctor` | **loss in force, gain in freshness** — §4.4; requires an ADR-0019 relabel |
| Statusline | installed by `operator-tools:install`, inert until `claude:statusline:activate` | unchanged — the **only** surviving custom Claude-side activation | **neutral** |
| Minimum Claude Code version | 2.1.154 | **2.1.224** (archive source) | **loss**; new ADR-0027 tuple row |
| Windows / macOS for the lifecycle | `ccodex sdlc` is Linux-x86_64-only with the gate duplicated in 4 files | the host handles its own platforms; our Python plane shrinks to Codex-only | **win** |
| Receipt/evidence trail | 2 sealed receipt families, digest-as-approval, ancestor pointers — currently **exit-3 broken against the only downloadable artifact** | host record (`id/version/scope/enabled/installPath/installedAt/lastUpdated`) + our re-hash | **loss in ceremony, win in function**; the current trail's only reader is its own writer |
| `recover --apply <plan-sha256>` | digest-as-approval for one interrupted transaction | gone; the host's install is atomic-per-archive | **loss**, but of a recovery for a transaction that no longer exists |
| Install machinery | **37,214** lines of script + test **[measured]** | **~5,460** | **−86%** |
| Dependence on a vendor surface | none for the Claude plane | the plugin schema; no fallback without re-adding code | **loss** — the design's one genuine structural risk |

### The four proposal points, answered

**P1 — "mise installing the remote should install the deps … and the ccodex cli."** Half is executed
evidence (`mise use -g github:…@0.7.4` installs a release exposing `bin/ccodex`,
`docs/adr/0011-…:182-195`). The other half is refuted three independent ways: a `github:`-backend
tool install *"does not import this repository's `[tools]` table"* (`:156`), remote task includes
*"carry tasks only — never `[tools]`"* (`docs/research/2026-08-07-…:100-104`), and git/curl are
decided as **host capabilities, not bundled** (`docs/plans/…:141-147`), reinforced by ADR-0002's
system-package prerequisite class. **The lean answer dissolves the question rather than solving it:**
the Claude-first core needs *no* deps, so the only place the dep set matters is the contributor
checkout, where `mise trust && mise --locked install` already does exactly what P1 asks. Deps are a
contributor concern, not an operator concern.

**P2 — "ccodex installs agentic-sdlc in its entirety … into user or project local scopes."** Already
decided (ADR-0017, ADR-0021, the Install-UX plan) and partly built. The lean design agrees with the
*goal* and disagrees with the *agent*: the host installs it, in **three** scopes rather than two,
with a fail-closed digest check we could not build ourselves and a versioned side-by-side cache we
never got around to building. Note the constraint the lean design keeps: **acquisition ≠ activation**
remains two commands (`marketplace add`, then `install`), honoring ADR-0021 item 3, ADR-0019's
per-effect grant, and the Install-UX plan's *"we should not do that"* about hidden postinstall
mutation (`:3-8`).

**P3 — "is ccodex-cli not fit for that?"** ccodex is *fit* and should not be *asked*. It is the one
operator CLI (ADR-0017:34-35) and it should own exactly what no host owns: the login-shell PATH, the
gateway, the Codex roster, and two settings keys. Asking it to own the Claude plane means
reimplementing — worse, and against a shared namespace — five things the host already does
fail-closed: fetch, verify, place, scope, and inventory.

**P4 — Bun 1.4 compiled rewrite with embedded payload and self-update.** **ADR-0031 is honored in
full; no evidence is offered to supersede it.** Its Decision item 1 forbids *"no full or partial
rewrite of the installer, updater, or launcher into Bun (or Go)"* (`:75-79`) on five measured facts,
and its consequence puts the burden on a re-proposer to *"show which measured fact changed"*
(`:141`). Nothing has: report 03 confirms 1.4.0 is still the only 1.4.x release, digest-pinning
PR #36173 and argv[0] PR #32851 are still open, and the macOS-27 signing fix is merged but in **no
release**. Report 03 also *adds* two facts against P4 that ADR-0031 did not have: an **open,
untriaged** Bun defect (#32011) hanging on direct native spawns of **Rust-compiled Windows
executables** — which is `uv.exe`'s exact profile — and a third-party report that bare-name `$PATH`
lookup fails specifically from inside `--compile`'d binaries. Report 03's one correction
(`BUN_OPTIONS` argv-splicing was fixed in 1.2.23) does not touch any of ADR-0031's five facts, and
`BUN_BE_BUN` full-CLI takeover remains open.

But the lean design's argument against P4 is not primarily the ADR. **It is that the lean design
deletes P4's premise.** P4 wants a binary that (a) packs the agentic-sdlc payload and (b)
self-updates. After Phase 3 there is nothing left to pack — the payload's channel is the host's own
cache, verified against a digest, and the remaining ccodex is a gateway launcher plus a small Codex
copier. And the update authority P4 wants already exists, in the host, gated by our `version` field
— so building a second one is exactly ADR-0021's rejected *"second update authority"* (`:24-26`),
the Install-UX plan's *"`ccodex` should not grow a second self-updater"* (`:82`), and ADR-0020 item
4. **P4 becomes less attractive under lean, not more.** One incidental note: ADR-0031's revisit
trigger 2 requires *"the post-demolition `ccodex` surface has been stable for at least one
release."* This design **is** the demolition, so it moves that trigger forward rather than
satisfying it.

### Is the loss acceptable for "claude first and for now"?

Yes, and the reason is specific rather than rhetorical. Enumerate everything genuinely lost:
(1) the pre-install mechanical host-version refusal, (2) per-hook rather than per-plugin
authorization, (3) our own digest ownership of Claude-plane bytes, (4) the sealed receipt family,
(5) a rise in the host-version floor from 2.1.154 to 2.1.224, (6) the symlink edit loop.

Of those, (6) is fully recovered and improved by `--plugin-dir`. (3) and (4) are traded for a
fail-closed check *we do not have to write* plus a host-authored inventory that is strictly richer
than the receipt it replaces (§4.2), against a receipt family that report 05 measured as
**currently exit-3 broken against the only artifact an operator can download**. (2) is redundant
with a gate the payload already carries. (1) and (5) are real, small, and each becomes one named ADR
row rather than a silent regression. Six losses, four of which are gains in disguise, against
~32,000 lines deleted, three commands removed from the critical path, one prerequisite removed, and
project scope going from *absent* to *first-class in three flavours*. For "claude first and for now"
that trade is not close.

---

## 9. Open questions

**Blocking (must be answered before Phase 1 ships):**

1. **Q1 — Do plugin-provided `workflows/` work at user scope, or only where the plugin is enabled in
   a project?** The plugins reference lists `workflows` as a component field but gives no discovery
   semantics (*"Specific workflow mechanics are documented in the linked `/docs/en/workflows` page,
   not in this plugin reference"*). Report 04 asserted `/sdlc-wave` and `/sdlc-mission` would fail
   outright; that assertion rested on the now-corrected claim that workflows aren't a plugin
   component, so the *severity* is unestablished either way. **UNVERIFIED — must be measured with
   `claude --plugin-dir dist/plugin` in a scratch repo, both scopes.** This is Phase 0's real risk.
2. **Q2 — Which catalog form works in a container with no git?** The `archive` *plugin* source needs
   no git, but the *marketplace* source may. If `marketplace add <git url>` requires git, the
   git-free path is a hosted `marketplace.json` URL — and URL-based marketplaces have documented
   relative-path limitations. **UNVERIFIED.** Phase 1 check 1.
3. **Q3 — Is the zip byte-reproducible?** Must be measured, not assumed (Phase 0 check 2). If not,
   the sha256 pin still works (it pins *shipped* bytes) but the rebuild-and-compare property
   ADR-0031 fact 4 protects is lost for the plugin archive, which would need its own recorded
   decision.
4. **Q6 — Does `version`-pinning + third-party-auto-update-off + `DISABLE_AUTOUPDATER` actually
   guarantee no silent version change?** ADR-0020 item 4 depends on it. **UNVERIFIED.**

**High-value (would enable further deletion):**

5. **Q4 — Does Codex CLI have an equivalent marketplace install, and does it carry
   `agents/codex/*.toml`?** `.codex-plugin/plugin.json` declares only `"skills": "./skills/"`, and
   `.agents/plugins/marketplace.json` exists with `"source": "./"`. If the Codex channel carries the
   role TOMLs too, **`install_skill_bundle.py` can be deleted entirely** — a further ~1,900 script
   lines and ~1,850 test lines, and the ccodex ledger shrinks to the statusline and the PATH file.
   This is the single largest remaining deletion and it is one experiment away.
6. **Q5 — Does `statusLine.command` resolve through the plugin `bin/` PATH?** The docs say `bin/` is
   added to *"the Bash tool's PATH"*, which is probably not the statusline's execution context. If
   it is, the last owned file disappears and `install_operator_tools.py`'s successor shrinks to the
   two settings keys. **UNVERIFIED.**
7. **Q7 — What does `plugin.json`'s `channels` field mean?** `policy/release-contract.v1.json:59-78`
   defines a `channels` object that report 05 measured as **read by nothing**. If the manifest's
   `channels` is stable/preview selection, the dead policy has a native home and the concept is
   delivered rather than deleted.
8. **Q8 — Can `userConfig` carry provider/gateway configuration?** If so, part of
   `ccodex configure`'s 2,681-line surface has a native, host-validated home
   (`--config <key=value>` is validated against the manifest's schema).

**Design-level, no measurement needed but a decision required:**

9. **Q9 — Does relabelling host-version compatibility from mechanical to observed need its own ADR
   amendment, or does ADR-0019's labeling rule cover it?** My reading is that labeling is sufficient
   and the new ADR records it; a stricter reading would require amending ADR-0027's certification
   language, which says *"safety-dependent use still requires the surface's current versioned
   capability canaries"* — arguably a session-time hook *is* a capability canary, which would make
   the change an improvement rather than a weakening.
10. **Q10 — Is `--strict` validation of the built plugin a `mise run check` leaf?** It requires
    `claude` on the machine running the gate, which would make Claude Code a *contributor*
    prerequisite. Cleanest resolution: `validate_bundle.py` asserts the structural properties
    natively (no symlinks, no `package.json`, component inventory counts) and CI additionally runs
    `claude plugin validate --strict`, so the local gate stays claude-free and CI is stricter — the
    same split `mise run check` vs CI already uses.
11. **Q11 — Do we keep `bundle:install --agent codex` under the name `bundle`, or rename to
    `ccodex host`?** `bundle` becomes a misnomer once it installs one host's roster. Renaming costs
    a README row and an alias-retirement path that `install_operator_tools.py:685-703` already has
    vocabulary for — vocabulary I proposed deleting, which is an argument for renaming *in the same
    release* so the alias machinery is never needed.
12. **Q12 — Does `--sparse` make the catalog clone trivially small once plugins come from an
    `archive` source?** `README.md:866` currently recommends
    `--sparse .claude-plugin plugin skills agents commands output-styles`; with an archive source
    only `.claude-plugin` is needed. Worth measuring, and it is a one-line README change.

**Explicitly out of scope for this design, flagged so it is not assumed:** the gateway plane
(`scripts/opencodex-claude.sh`, 2,681 lines) is untouched. It is the largest single file in the
install-adjacent tree, it is `ADR-0005`-governed convenience tier that no gate consumes, and it is
where the next audit should look. This design does not claim to have simplified it.
