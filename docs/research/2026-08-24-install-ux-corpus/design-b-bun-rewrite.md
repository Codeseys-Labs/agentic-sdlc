# Design B — `ccodex` as one compiled Bun 1.4 binary with the payload inside it

**Assignment:** argue the full Bun 1.4 rewrite as well as it can be argued.
**Author's posture:** this is an advocacy document with an honest evidence ledger. Section 10 states
plainly which of ADR-0031's five measured facts this design overturns (one), which it dissolves by
changing the build topology rather than by contesting the measurement (two), and which it concedes
and pays for (two). It also states that **zero of ADR-0031's three conjunctive revisit triggers are
satisfied as of 2026-08-24**, so this proposal is a *conditional target with a decisive first
experiment*, not something that can be adopted this week. Anyone who reads only the thesis and skips
section 10 is misreading the document.

Repo state assumed throughout: `/tmp/asdlc-research`, HEAD `e0fbf92`, `.version-bump.json` = `0.7.4`.
Citations are `path:line` from that checkout, or `report NN` for the five research reports in
`.research-out/`.

---

## 1. Thesis

Today's architecture pushes a **source tree** through a **binary distribution channel** and then
spends roughly twenty thousand lines of bash and Python proving, at run time, that the interpreter
which arrived is the interpreter it wanted — and report 05 live-verified that this proof *fails on
the only artifact an operator can actually download*, because `v0.7.3`/`v0.7.4`'s `bin/ccodex`
routes `ccodex sdlc *` through `uv run --script` while `scripts/ccodex_sdlc.py:454-471` demands
`python3.12.11 -I -B`, so every receipts-gated verb exits 3. The fix for that class of defect is not
a better dispatcher; it is to **stop shipping a program that has to go find its own runtime**. This
design makes `ccodex` one natively-compiled Bun 1.4 executable per certified platform tuple with the
entire payload (13 skills, 8 Claude agents, 8 Codex agents, 5 commands, 1 workflow, 1 hook, 1
output-style, `policy/`) embedded as ~1.9 MB of assets inside a ~64–90 MB carrier, distributed
through the one channel mise's `github:` backend was actually built for — a per-platform binary with
a lockable checksum — and materialised by `ccodex install --host claude --scope user|project`. The
payoff is not lines of code (ADR-0031 measured that saving at ~400 and it is right); it is
**deletions of whole layers**: the payload arriving *inside* the verified binary deletes the entire
acquisition plane (`write_acquisition_receipt.py`, the candidates directory, the manual placement
bridge, `installed-unselected`, `selection: "absent"`, the unread `channels` object) because the
binary's own sha256 *is* the acquisition identity; having no interpreter to acquire deletes
`runtime_admission()`, the uv-managed-CPython lookup, the `jq`-admission machinery and its exit-127
sentinel, and the two-dispatcher divergence; having no PATH file to install deletes
`install_operator_tools.py`, its second state schema, its alias vocabulary, and the
`HostPreconditionError` that today forces edit-rc → new-shell → re-run in the middle of an install.
Six state stores collapse to one document; four acquisition planes to one; two installers to one;
and a fresh operator's use-plane cost falls from ~1.3 GB of mise toolchain plus a `mise trust` on a
tree they did not clone to a single file they can checksum by hand. The price is real and is stated
in full: a non-reproducible carrier (contained by keeping `git archive` + `manifest.json` as the
payload's independently re-derivable digest chain), per-tuple signing and notarisation obligations
under ADR-0027, and a new ADR that supersedes ADR-0031 item 1 — which cannot honestly be written
until the experiments in Phase 1 come back green.

---

## 2. End-state UX — the exact commands a fresh operator types

Version shown as `0.9.0`, the first release of this architecture. Every command below is
non-interactive, prints its own next step, and is idempotent.

### 2.1 Fresh macOS host (Apple Silicon, macOS 27, no Homebrew assumptions)

```bash
# 0. one bootstrap prerequisite, unchanged (ADR-0002)
curl -fsSL https://mise.run | sh
eval "$(~/.local/bin/mise activate zsh)"

# 1. acquire the operator CLI  (one binary, checksum-locked by mise's github: backend)
mise use -g "github:Codeseys-Labs/agentic-sdlc@0.9.0"

# 2. prove what you got, before you let it write anything
ccodex verify
#   ccodex 0.9.0  darwin-arm64  certified
#   binary  sha256:9f2c…              (compare against the signed SHA256SUMS in the release)
#   payload candidate_id:4ab1…        (re-derivable: git archive v0.9.0 | ccodex verify --manifest -)
#   entries 37 embedded, 37 re-hashed, 0 mismatched
#   host    claude 2.1.161 observed   (>= 2.1.154 minimum, ADR-0027)

# 3. activate into the user plane — the only effectful command in this sequence
ccodex install --host claude --scope user
#   installed: 13 skills, 8 agents, 5 commands, 1 workflow, 1 hook, 1 output-style
#   37 ok, 0 conflict, 0 foreign, 0 modified
#   receipt sealed: installation_id sha256:71de…
#   next: `ccodex activate statusline` and `ccodex activate hook session-start-routing-primer`
#         each is a separate authorization; installing never enables (ADR-0019)
```

Optional, each a separately-authorized effect:

```bash
ccodex activate statusline                                 # writes settings.json statusLine.{type,command}
ccodex activate hook session-start-routing-primer          # writes settings.json hooks entry
ccodex activate workflow sdlc-wave-scout --scope project   # copies into $PWD/.claude/workflows/
ccodex status                                              # one answer for every plane, lock-free
```

The gateway plane stays a separate, optional program the operator installs through its own front
door (section 9):

```bash
mise use -g "npm:@bitkyc08/opencodex@2.28.0"
ccodex gateway status        # refuses by name if ocx is absent; `ocx health` is the only verdict
```

### 2.2 Fresh Ubuntu container (`ubuntu:24.04`, non-root, only `curl` + `ca-certificates`)

Two routes. Route A keeps mise as the single front door; route B is the documented no-mise fallback
that makes the use plane depend on nothing but "a way to download a file". Route B is what makes
this design honest about ADR-0002: it *removes* prerequisites rather than adding one.

```bash
# ---- Route A: mise (primary) --------------------------------------------------
curl -fsSL https://mise.run | sh
eval "$(~/.local/bin/mise activate bash)"
mise use -g "github:Codeseys-Labs/agentic-sdlc@0.9.0"
ccodex verify
ccodex install --host claude --scope user

# ---- Route B: review-before-trust download (no mise, no curl|bash) -----------
cd "$(mktemp -d)"
curl -fsSLO https://github.com/Codeseys-Labs/agentic-sdlc/releases/download/v0.9.0/ccodex-linux-x64
curl -fsSLO https://github.com/Codeseys-Labs/agentic-sdlc/releases/download/v0.9.0/SHA256SUMS
curl -fsSLO https://github.com/Codeseys-Labs/agentic-sdlc/releases/download/v0.9.0/SHA256SUMS.sig
cosign verify-blob --certificate-identity-regexp '^https://github\.com/Codeseys-Labs/agentic-sdlc/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  --signature SHA256SUMS.sig SHA256SUMS
sha256sum -c SHA256SUMS --ignore-missing
install -m 755 ccodex-linux-x64 ~/.local/bin/ccodex
~/.local/bin/ccodex verify
~/.local/bin/ccodex install --host claude --scope user
```

Note what is *absent* from both routes and is present today: no `git clone`; no `mise trust` of a
config you did not write (`README.md:332-338`, `bin/ccodex:111-137`); no `mise --locked install` of
12 pinned tools at ~1.3 GB (`README.md:344-352`); no `operator-tools:install` and therefore no
"the bin dir must already be on PATH" refusal that forces edit-rc → new-shell → re-run
(`install_operator_tools.py:181-190`, report 01 §D.2); no `uv python find --offline
--no-python-downloads 3.12.11` whose failure message names a command that does not fix it (report 01
§D.3); and no choice between `ccodex bundle install` and `ccodex sdlc install` — there is one verb
(report 05 §c).

### 2.3 Project scope

```bash
cd ~/src/my-repo
ccodex install --host claude --scope project
#   refuses at exit 3 if $PWD is not a repository root (no `.git` present)
#   copies, never links: a repo-committed entry must be self-contained
#   receipt is home-local, keyed by (host, scope, root) — nothing lands in your git index
#   next: git add .claude/  (or add it to .gitignore; ccodex writes neither)
ccodex status --scope project
ccodex uninstall --host claude --scope project
```

### 2.4 Update and self-update

```bash
# mise-installed: ccodex refuses to be its own second update authority (ADR-0021:24-26)
ccodex update --self --to 0.9.1
#   refused (exit 3): this copy was acquired through mise. run:
#     mise use -g "github:Codeseys-Labs/agentic-sdlc@0.9.1" && ccodex install --host claude --scope user
mise use -g "github:Codeseys-Labs/agentic-sdlc@0.9.1"
ccodex install --host claude --scope user     # converges owned entries; unchanged entries print `unchanged:`

# curl-installed: the approval IS the digest (the repo's own idiom, ccodex_sdlc.py:52-58)
ccodex update --self --to 0.9.1 --expect sha256:1c77…
#   stages a sibling temp file, verifies the digest, runs the staged binary's own `verify`,
#   then one rename(2). any failure leaves the current binary untouched.
```

---

## 3. Component / layer diagram

```
                      ┌──────────────────────────────────────────────────┐
BUILD PLANE           │  contributor checkout  (git clone + mise trust)  │
(unchanged, and the   │  mise --locked install  → bun 1.4.0 pinned by    │
 only place the       │      mise.lock:31-33 sha256 c669e97f…            │
 1.3 GB toolchain     │  mise run check   (gates, tests, secrets)        │
 still exists)        │  mise run release:build                          │
                      └───────────────────┬──────────────────────────────┘
                                          │
                    ┌─────────────────────┴──────────────────────┐
                    │                                            │
        ┌───────────▼────────────┐              ┌────────────────▼───────────────┐
        │ PAYLOAD (reproducible) │              │ CARRIER (not reproducible)     │
        │ git archive @ tag      │              │ per-target NATIVE build:       │
        │ scripts/build_release  │──manifest──▶ │  bun build --compile           │
        │   .py:202-287          │  embedded    │    --compile-executable-path   │
        │ manifest.json:         │              │      $(mise where bun)/bin/bun │
        │  per-file sha256,      │              │    --asset payload/            │
        │  candidate_id          │              │    --no-compile-autoload-dotenv│
        │ ~1.9 MB uncompressed   │              │    --no-compile-autoload-bunfig│
        │ (skills 1552K, agents  │              │  → 64–90 MB, 4 certified       │
        │  256K, commands 48K,   │              │    tuples, no cross-compile     │
        │  policy 44K, wf 8K,    │              │    download of any runtime     │
        │  hook 4K, styles 4K)   │              │  → codesign + notarize (macOS) │
        └────────────────────────┘              └────────────────┬───────────────┘
                                                                 │
                                    ┌────────────────────────────▼─────────────────────┐
DISTRIBUTION                        │ GitHub release: 4 binaries + SHA256SUMS(+.sig)   │
(the channel and the artifact       │   consumed by  mise use -g github:…@X.Y.Z         │
 shape finally agree)               │            or  curl + sha256sum -c  (route B)    │
                                    └────────────────────────────┬─────────────────────┘
                                                                 │
   ┌─────────────────────────────────────────────────────────────▼──────────────────────────────┐
   │                              ONE BINARY, ONE PROCESS                                       │
   │                                                                                             │
   │  argv parser (closed grammar) ──▶ exit ladder 0/1/2/3/4  ·  --json on every reader           │
   │      │                                                                                      │
   │      ├── READ PLANE      verify · status · inspect · doctor · recover --dry-run              │
   │      │     no lock, no write, import-graph-isolated from the write plane (§8.3)              │
   │      │                                                                                      │
   │      ├── WRITE PLANE     install · update · uninstall · activate {statusline|hook|workflow}  │
   │      │     recover --apply <digest> · update --self --to <v> --expect <sha256>               │
   │      │        │                                                                             │
   │      │        └── transactional substrate: one armed pending slot, O_EXCL|O_NOFOLLOW,        │
   │      │            fsync (F_FULLFSYNC on darwin via bun:ffi fcntl), rename(2), parent fsync   │
   │      │                                                                                      │
   │      ├── EMBEDDED PAYLOAD  /$bunfs/root/payload/{skills,agents,commands,workflows,hooks,     │
   │      │                     output-styles,policy}  +  manifest.json                          │
   │      │                                                                                      │
   │      └── GATEWAY FRONT DOOR  gateway {status|launch|configure|set-fast-model|models}         │
   │            in-process settings-bypass classifier (the ADR-0031-approved harvest, now         │
   │            in-process rather than a spawned helper) → spawns operator-installed `ocx`        │
   │            by ABSOLUTE path only; `ocx health` is the only verdict                          │
   └──────────┬───────────────────────────────────┬───────────────────────────┬──────────────────┘
              │                                   │                           │
   ┌──────────▼──────────┐        ┌───────────────▼──────────────┐  ┌─────────▼─────────────────┐
   │ HOST PLANE          │        │ ONE STATE DOCUMENT           │  │ FOREIGN, NOT OWNED        │
   │ ~/.claude/…  (user)  │        │ $XDG_STATE_HOME/agentic-sdlc │  │ `claude` (version read)   │
   │ <repo>/.claude/…     │        │   /state.json  mode 0600     │  │ `ocx` (optional, absolute)│
   │   (project)          │        │ + receipts/  + active ptr    │  │ Claude settings.json      │
   │ ~/.codex/…  (companion,│      │ ONE schema, no migration     │  │   (read; written only by  │
   │   uncertified)        │      │ (§4)                         │  │    `ccodex activate`)     │
   └─────────────────────┘        └──────────────────────────────┘  └───────────────────────────┘
```

Layers that exist today and do **not** appear above: LAYER 0's trust step, LAYER 2's 12-tool
toolchain, LAYER 4's PATH surface, LAYER 5's four separate mise activation tasks, LAYER 7's
contributor forwarders on the use plane, the second `ccodex` dispatcher, the acquisition-candidate
directory, and the Claude self-marketplace plane (report 01 §A.2, §A.5; report 04 §b).

---

## 4. The ownership / state data model — named before any mechanism

This is the core data shape. Everything in sections 5–7 is derived from it; if this shape is wrong
the rest of the design is wrong.

### 4.1 One document, one schema, no migration

```
$XDG_STATE_HOME/agentic-sdlc/            (Windows: %LOCALAPPDATA%\agentic-sdlc\ — uncertified)
  state.json                 mode 0600   schema "agentic-sdlc-state/1"      ← the only mutable doc
  state.lock                             flock; taken only by the write plane
  receipts/<installation_id>.json        create-only, O_EXCL|O_NOFOLLOW, immutable once sealed
  active/<host>.<scope>.<root-hash>.json atomic pointer to one sealed receipt
  pending.json                           at most one armed transition, ever
```

`state.json` is derived, small, and rebuildable from `receipts/` — that is deliberate: the receipts
are the ledger, `state.json` is the index. Today the relationship is inverted (the bundle's
`state.json` v4 is authoritative and the receipts are an *additional* plane bolted on top, report 05
§c), which is exactly why an uninstall can leave `state.json` claiming 26 owned entries while the
activation receipt correctly says `retired` (report 05 FINDING-1, seed `agentic-sdlc-42ec`). One
ledger, one index, and that contradiction cannot be expressed.

### 4.2 The three records

```jsonc
// Installation — one per (host, scope, root); sealed, never edited
{
  "schema": "agentic-sdlc-installation/1",
  "installation_id": "<sha256 over the canonical bytes of everything below>",
  "host": "claude",                       // "claude" | "codex"  (codex uncertified, ADR-0017)
  "scope": "user",                        // "user" | "project"  — always explicit, never detected
  "root": "/home/op/.claude",             // absolute; for project scope, "<repo>/.claude"
  "source": {                             // ← replaces the ENTIRE acquisition plane
    "release_version": "0.9.0",
    "candidate_id": "<sha256 of the embedded payload inventory>",
    "binary_sha256": "<sha256 of the running executable's own bytes>",
    "target_tuple": "darwin-arm64",
    "support_tier": "certified"           // ADR-0027; never inherited across tuples
  },
  "host_observed": { "program": "claude", "version": "2.1.161", "path": "/usr/local/bin/claude" },
  "entries": [ /* Entry[] */ ],
  "effect_state": "complete",             // complete | partial | unknown
  "terminal_phase": "activated",          // activated | activated-partial | retired
  "derived_from": "<installation_id | null>",
  "sealed_at": "2026-08-24T18:03:11Z"
}

// Entry — one per materialised destination
{
  "collection": "skills",                 // skills|agents|commands|workflows|hooks|output-styles
  "name": "adr-lifecycle",
  "destination": "/home/op/.claude/skills/adr-lifecycle",
  "node": "dir",                          // dir | file  — a kind's node type is load-bearing
  "mode": "copy",                         // copy ONLY. link is deleted from the model entirely.
  "prestate": "absent",                   // absent | owned | foreign | modified
  "disposition": "created",               // created | refreshed | unchanged | preserved | removed
  "content_sha256": "<digest>",
  "removable": true
}

// Binding — a settings.json mutation, which is NOT a file we own
{
  "collection": "bindings",
  "name": "statusline",                   // statusline | hook:<name>
  "destination": "/home/op/.claude/settings.json#/statusLine",
  "prestate": "absent",
  "disposition": "bound",                 // bound | unbound | preserved
  "bound_value_sha256": "<digest of the exact JSON subtree we wrote>",
  "removable": true
}
```

### 4.3 What this shape deletes, and why the deletion is safe

| Deleted concept | Where it lives today | Why the new shape does not need it |
|---|---|---|
| Acquisition receipt (`release-candidate-acquisition-receipt/v1`) | `write_acquisition_receipt.py:222-301` (333 lines) | Its whole job is to prove "these bytes are a verified release candidate". The bytes are *inside a binary whose sha256 the operator checked against a signed SHA256SUMS*. `source.binary_sha256` + `source.candidate_id` carry the same claim with no second document, no `--root`/`--archive` bridging recipe (`docs/plans/2026-08-14T163833Z-Install-UX.md:195-219`), and no candidates directory. |
| `terminal_phase: "installed-unselected"` | `write_acquisition_receipt.py:83-92` | A dead-end state nothing ever transitioned out of (report 05 §a). |
| `selection: "absent"` | same | A schema field with no producer that ever wrote any other value (report 05 §a). |
| `channels` object | `policy/release-contract.v1.json:59-78` | Never read by any code (report 05 §b). Delete now, per "do not preserve throwaway compatibility states". |
| `policy/ccodex-sdlc-read-report.v2.json` | dormant, digest-pinned only | Unwired scaffold for a report shape that does not exist; `validate_bundle.py:1699`'s comment claiming it is parsed is false (report 05 §b). |
| Operator-tools state (`schema 2`, accepts `1`) | `install_operator_tools.py:84-89` | No PATH files are installed, so there is nothing to own. |
| Statusline / hooks / workflows receipt stores (3 stores) | `manage_claude_statusline.py:61`, `manage_claude_hooks.py:72`, `manage_claude_workflows.py:82-91` | Become `Binding` and `Entry` rows in the one document, keyed by destination exactly as `manage_claude_workflows` already keys by `(workflow, destination)` (report 01 §E.3) — that key generalises to `(host, scope, root)` and is the whole project-scope mechanism. |
| Bootstrap receipt | `bootstrap-agentic-sdlc.sh:27-29` | The managed-clone acquisition plane is deleted (§5). |
| `mode: "link"` / `"junction"` | `install_skill_bundle.py:857-870`, `:845-855` | The release plane must copy so `mise prune` cannot break Claude's entries (`docs/plans/…:185`); the contributor plane keeps links but the contributor plane is a checkout, not an installation. One mode means the `auto`/`link`/`copy` selector, the junction path, the cmd.exe-metacharacter rejection (`:824-834`), the retarget disposition, and the "exact legacy link" adoption branch all disappear. |
| `legacy_state_path` and the second-document refusal | `install_skill_bundle.py:132-135`, `:233-247`, `:1307-1318` | There is one location. The spurious-fire hazard at `<repo>/.local/state` under `--claude-home <repo>` (report 01 §E.2) cannot occur because `--claude-home` is deleted and `--scope project` derives its root from `$PWD` while state stays home-local by construction, not by a `Path.home()`-vs-`config.home` accident pinned by `tests/test_install_skill_bundle.py:819`. |

### 4.4 Invariants of the shape that are kept, deliberately

- **Ownership is byte identity and nothing else.** No birth-time witness, no dev/inode token
  (`install_skill_bundle.py:8-15`). The overengineering audit measured 20/20 btime collisions on the
  CI runner (`docs/research/2026-08-22-overengineering-audit.md:16-19`); adding a witness that
  carries no information is exactly the addition this design refuses. The documented weakening
  stands and is restated in `ccodex verify --explain`: a modified destination is refused and
  preserved; a byte-identical operator recopy *is* removed by uninstall.
- **Digest is a length-prefixed, node-typed, sorted stream** so a boundary splice cannot forge a
  sibling header (`install_skill_bundle.py:700-727`), and a dir kind cannot match a file kind's
  digest (`:927-932`).
- **Exactly one armed pending slot**, with commit/abort decided by comparing *live* bytes to the
  armed `before`/`after` (`install_skill_bundle.py:1069-1177`).
- **Foreign and modified destinations are preserved and named, never adopted or overwritten**
  (ADR-0021:41-42; `ccodex_sdlc_install.py:39-45`).
- **The collection boundary is asserted before the destination is read**
  (`install_skill_bundle.py:631-654`).
- **Idempotency, strengthened.** Today a copy-mode entry is "refreshed unconditionally on every run"
  (`install_skill_bundle.py:431-437`, report 01 §B.4) — so two identical installs produce two
  different receipts. In the new model `install` is convergent: an entry whose live digest already
  equals the payload digest gets `disposition: "unchanged"`, and a re-run over an unchanged host
  produces a receipt whose `installation_id` is **bit-identical** to the previous one. `ccodex
  install` twice in a row is provably a no-op, and that property is a test.

---

## 5. What gets DELETED from the current tree

Measured line counts from this checkout. "Replaced" means the invariant survives, re-expressed in
TypeScript; "deleted" means the concept itself goes away.

### 5.1 Deleted outright — the concept goes away

| Path | Lines | Why it goes away |
|---|---:|---|
| `assets/launchers/ccodex.in` | 509 | No rendered second dispatcher. The binary *is* the PATH surface; there is nothing to substitute at install time, so the six install-time bindings (`@PINNED_BASH@`, `@PINNED_OCX@`, `@PINNED_JQ@`, `@PINNED_UV@`, `@PINNED_NODE@`, `@PINNED_SDLC_PYTHON@`) and the "unsubstituted placeholder is fatal" invariant (`install_operator_tools.py:362-369`) have no referent. |
| `scripts/install_operator_tools.py` | 1,135 | Nothing to install onto PATH. Deletes: state schema v2, the alias sub-vocabulary (`:685-753`), `HostPreconditionError` and the PATH precondition (`:181-190`) — i.e. report 01 §D.2's edit-rc → new-shell → re-run loop — the bash-candidate closed list, the `mise -C … which` resolutions, and the `--offline --no-python-downloads` CPython lookup whose remedy message names a command that does not install a Python (report 01 §D.3). |
| `bin/ccodex` | 335 | One dispatcher, not two. Deletes the three declared divergences (`bin/ccodex:9-22`), the `mise -C <root> exec` per-call resolution, the untrusted-config probe, and `uv python install 3.12.11`. |
| `scripts/ccodex_sdlc_readonly.py` | 225 | The CPython stdlib monkey-patch has no Bun equivalent and its own docstring says it is "not an adversarial same-UID sandbox" (`:1-8`). Replaced by a build-time import-graph boundary (§8.3) — stronger before shipping, weaker at run time; the trade is stated. |
| `scripts/write_acquisition_receipt.py` | 333 | §4.3. |
| `scripts/bootstrap-agentic-sdlc.sh` | 280 | Acquisition plane 2 (managed clone) exists because "the tree is a run-time dependency" (ADR-0011:38-52). It is not, once the payload is in the binary. ADR-0011's reversal condition fires here. |
| `.claude-plugin/marketplace.json` + `plugin/` symlink tree | small | Acquisition plane 4 is **mutually exclusive with the bundle install by code** — `marketplace_overlap()` blocks the entire Claude plane (`install_skill_bundle.py:939-955`) — and it silently delivers ~60% of the payload, omitting the workflow and the output-style entirely (report 04 §d). Two planes that cannot coexist, one of which is a silent partial, is a defect surface. The overlap *refusal* stays (Claude Code users can still install other people's marketplaces); the repo stops publishing itself as one. |
| `policy/ccodex-sdlc-read-report.v2.json`, `channels` in `policy/release-contract.v1.json` | — | Dormant scaffolding with no reader (report 05 §b). |
| `--claude-home` / `--home` side door | in `install_skill_bundle.py:1794-1802` | Replaced by `--scope project`, which has a repo-root guard, a scope-keyed receipt, and no `Path.home()`-vs-`config.home` split (report 01 §E.2). |
| `mise` tasks `bundle:*`, `operator-tools:*`, `claude:statusline:*`, `claude:hooks:*`, `claude:workflows:*`, `setup`, `contributor:setup`'s bundle leg | ~14 task blocks | The use plane is a binary; mise tasks are for working *on* the repo. Also removes the README's "Five steps"/six-items contradiction and the headline-installs-both-planes vs Quickstart-choose-explicitly contradiction (report 01 §D.1) by deleting one of the two sequences. |

### 5.2 Replaced — invariant survives, implementation is rewritten

| Path | Lines | Disposition |
|---|---:|---|
| `scripts/install_skill_bundle.py` | 1,848 | Transactional substrate, digest, ownership test, conflict vocabulary, pending slot → TypeScript. Its standalone CLI (`ccodex bundle …`) is deleted; there is one front door (report 05 §c's open fork is closed by convergence, not by documenting the split). |
| `scripts/ccodex_sdlc.py` | 1,816 | Grammar, exit ladder, read-report policy → TypeScript. `runtime_admission()` (`:454-471`) and `load_lifecycle_module()`'s sibling-loading (`:487-520`) are **deleted**, not ported (§8.1). |
| `scripts/ccodex_sdlc_install.py` / `_update.py` / `_uninstall.py` / `_recover.py` | 1,999 / 2,581 / 1,391 / 926 | Classification, compatibility check, copy-activation, receipt sealing, digest-gated recover → TypeScript. The four duplicated `SUPPORTED_PLATFORM` literals (report 05 §d.5) collapse to one build-time constant per target tuple. |
| `scripts/distribution_activation_receipt.py` | 1,917 | Receipt schema + closed effect/phase matrices → TypeScript; merged with the deleted acquisition schema into one `Installation` type (§4.2). This is where the largest honest line reduction lives: two receipt families with a `derived-from` edge between them become one document. |
| `scripts/manage_claude_statusline.py` / `_hooks.py` / `_workflows.py` | 574 / 522 / 542 | Become `ccodex activate {statusline|hook|workflow}` over the `Binding`/`Entry` rows. The statusline *program* becomes `ccodex statusline`, so `statusLine.command` points at the binary and the separate `agentic-sdlc-statusline` file, its ownership record, and its receipt store all disappear. |
| `scripts/opencodex-claude.sh` | 2,681 | The security core (route-integrity classifier, env classification, three settings-document classes, refusal exits) ports in-process. The 835 lines of measured forensics comments port **verbatim** (ADR-0031:80-96 precondition). The `jq()` admission machinery and its exit-127 `unadmitted` sentinel (`:431-493`) are **deleted** — this is the one seam ADR-0031 measured Bun winning decisively: 6 uncached `mise exec -- jq` spawns at 130 ms → one in-process parse at 24 ms (ADR-0031:67-71), and it retires ADR-0020's whole jq-resolution problem and the ERE-vs-Oniguruma two-regex-engine agreement burden. |

**Kept unchanged and load-bearing:** `scripts/build_release.py` (308) — it is the reproducibility
anchor and the reason the payload's digest chain survives the carrier's non-determinism (§7.3).
`policy/release-contract.v1.json`'s compatibility block, read from the *payload*, not the reader
(`ccodex_sdlc_install.py:938-1009`). `scripts/validate_bundle.py`, gates, tests, lefthook — all
contributor plane.

### 5.3 Honest accounting

~19,600 lines of shell + Python implementation are deleted or replaced. The TypeScript that replaces
them is estimated at **8,000–11,000 lines** (receipts/ownership core ~5k, gateway security core ~1.2k
plus 835 verbatim comment lines, grammar/readers ~1.5k, payload/asset layer ~0.5k, FFI + platform
shims ~0.3k). So the net line delta is a modest deletion, **not** the dramatic one the operator's
proposal implies — ADR-0031 measured the launcher's honest saving at ~400 lines and that measurement
stands. The deletions that matter are structural and countable a different way:

- acquisition planes: **4 → 1**
- installers with independently reachable CLIs: **2 → 1**
- state stores: **6 (+1 foreign read) → 1**
- receipt schema families: **2 with a cross-family ancestor edge → 1**
- separately-authorized activation tasks: **5 mise tasks → 4 verbs of one binary** (still 4 separate
  grants — ADR-0019 is honoured, not folded)
- runtime dependencies of the use plane: **uv, CPython 3.12.11 exact, node, jq, mise, bash → none**
  (`claude` is a host, not a dependency; `ocx` is optional)
- fresh-operator use-plane bytes: **~1.3 GB → one 64–90 MB file**
- `install_skill_bundle.py`'s install-mode selector: **3 modes → 1**

---

## 6. Migration path in verifiable phases

Every phase ends in a check that can be run and that fails loudly. Phases 0 and 1 produce value even
if the rewrite is then abandoned — that is deliberate, because the honest state of the evidence (§10)
is that Phase 1 might come back red.

### Phase 0 — Test the `sdlc` namespace through its subprocess seam (Python only, no Bun)

This is ADR-0031's revisit trigger 3, which the ADR itself calls "worth doing on its own merits", and
it is the single precondition without which this whole design is a bet rather than a refactor. Today
70 of 71 test files call `module.main()` in-process (measured: `grep -rl '\.main(' tests/*.py`), so a
language swap orphans the suite that would have to prove the swap (ADR-0031:57-65).

Build `tests/seam/` — a harness that drives `ccodex <verb>` as a **subprocess**: argv in; stdout
lines, `--json` documents, exit code, and the byte content of every receipt out. Port the invariant
set from report 01 §C (52 invariants) and the appendix's 78 `test_install_skill_bundle.py` cases into
seam assertions. Every assertion reads *output*, never a bare exit code — the methodological rule the
fresh-host verification established (`docs/research/2026-08-08-fresh-host-install-verification.md:249-260`).

**Check:** `mise run test:seam` is green against the *current Python implementation*, on Linux x64 and
macOS arm64, and `mise run check` still passes. A mutation test proves the harness has teeth: revert
`main@cd3fd3d` (the dispatcher fix) and the seam suite must go red on every `sdlc` verb with
`runtime-admission-refused` — the defect report 05 found live in `v0.7.3`/`v0.7.4` must be a *test
failure*, not a field report.

### Phase 1 — The decisive measurement gate (no production code)

Nine measurements. **Any single red result ends this design**, and the report of that red result is
the deliverable. Run all of them on Bun 1.4.x as pinned in `mise.lock`, on real hardware, and record
them in `docs/research/<date>-bun-1.4-gate.md`.

1. **macOS Gatekeeper end-to-end.** Compile natively on macOS 27 arm64; `codesign --force --timestamp
   --options runtime --sign "Developer ID Application: …"`; `xcrun notarytool submit`; staple; then
   run the stapled binary on a *clean* macOS 27 machine that has never seen it. This tests whether
   re-signing overwrites Bun 1.4.0's regressed ad-hoc arm64 signature (oven-sh/bun#39764, fixed on
   `main`, in **no release** as of 2026-08-24 — report 03 §d) and therefore whether the SIGKILL is
   bypassed by an obligation we already have. **UNVERIFIED and the highest-risk item in the design.**
2. **`process.execPath` from inside a compiled binary.** Report 03 §f records that `process.argv[0]`
   is the literal string `"bun"` inside a compiled binary (oven-sh/bun#32851, still open). The design
   needs its own absolute path twice: to write `statusLine.command`, and to stage a self-update.
   Measure `process.execPath`, `Bun.main`, and `/proc/self/exe`/`_NSGetExecutablePath` fallbacks.
3. **`--asset` directory embedding at our scale.** Embed the real payload (37 entries, ~1.9 MB,
   nested skill trees), read every file back via `node:fs` from `/$bunfs/root/`, re-hash, compare to
   `manifest.json`. Report 03 §b documents a *silent* exit-0-with-no-output cliff at 8+ files in the
   older glob-entrypoint mechanism (oven-sh/bun#25078/#20821, fixed by #25859) and explicitly flags
   whether an analogous cliff exists in the new `--asset` path as **UNVERIFIED for 1.4.0**. Also
   confirm the documented symlink-skipping does not silently drop payload (it will not, once
   `plugin/`'s symlinks are gone — §5.1).
4. **Durability primitives.** `Bun.write` is measured non-atomic, non-durable, symlink-following and
   mode-ignoring (survey §4.2 / ADR-0031's citation), so the substrate must use `node:fs` with
   `O_EXCL|O_NOFOLLOW`. macOS needs `F_FULLFSYNC`, which `node:fs` does not expose: prove a
   `bun:ffi` `dlopen(libc).fcntl(fd, 51, 0)` shim works from a compiled binary, and that a
   parent-directory fsync is reachable. Then run the crash-consistency matrix from
   `tests/test_install_skill_bundle.py` `PendingTransitionTests` (`:1584`–`:1816`) against it.
5. **Exit-code and signal fidelity per target.** Assert 0/1/2/3/4 survive the compiled boundary, and
   that a refusal is never 1. Report 03 §f/the survey name three defects in this area (#26674,
   #39787 Windows silent exit-0, #35296 macOS signal table). Windows is out of the certified set
   (§7.1), which retires #39787 for us.
6. **Subprocess reliability for `claude` and `ocx`.** Resolve **absolute paths only**; use
   `Bun.spawnSync`, never `Bun.$` (report 03 §g: the confirmed lost-wakeup hang capturing git output,
   #26580, and a third-party report of bare-name `$PATH` lookup failing *only* from compiled
   binaries, gstack#931). Measure 2,000 consecutive `claude --version` captures for zero hangs.
7. **Startup latency on the statusline path.** ADR-0031 measured compiled-Bun startup at 24 ms vs
   bash's 8.7 ms — a 2.8× regression — but measured the settings gate at 130 ms → 24 ms. The
   statusline renders on every prompt, so measure end-to-end statusline render time against today's
   `bash + jq` script. If the binary is not faster here, the one place users feel latency has
   regressed and that is a design finding.
8. **Native-build supply chain.** Verify that `bun build --compile
   --compile-executable-path $(mise where bun)/bin/bun` with **no `--target`** performs zero network
   requests (run under a network-denied sandbox) and that the embedded runtime bytes equal the
   mise.lock-verified bun (§7.2).
9. **Licensing.** Resolve the embedded JavaScriptCore (LGPL) + ICU obligation against ADR-0001's
   NOTICE posture — an ADR-0031 precondition, and `NOTICE` is already 44 KB.

**Check:** all nine recorded with `[measured]` values, and a one-page verdict naming which of
ADR-0031's five facts the results move. If item 1 or 3 or 4 is red, this design is dead and the
document says so.

### Phase 2 — Read plane in Bun, differentially proven, shipping nothing

Implement `verify`, `status`, `inspect`, `doctor`, `recover --dry-run` in TypeScript. Ship no binary.
Run the Phase-0 seam harness against **both** implementations over a corpus of synthesised state
documents (healthy, armed-pending, malformed, foreign, modified, racy, symlinked) and diff the
`--json` documents byte-for-byte.

**Check:** for every fixture, `python … --json` and `bun … --json` produce **identical canonical
bytes** and identical exit codes, including for the hostile-state fixtures that
`ReadOnlyProjectionTests` (`tests/test_install_skill_bundle.py:1293`, `:1330`, `:1367`) covers. Any
divergence is a bug in the new implementation, decided in favour of Python.

### Phase 3 — Write plane in Bun behind a differential oracle

Implement `install`, `update`, `uninstall`, `activate *`, `recover --apply`. For every seam scenario,
run Python and Bun against two pristine throwaway homes and throwaway state roots (the shape
`bundle self-test` already uses, `install_skill_bundle.py:1740-1758`) and compare: the full file tree
(paths, modes, node types, digests), the sealed receipt bytes modulo the two fields that legitimately
differ (`source.binary_sha256`, `sealed_at`), stdout line-for-line, and the exit code.

**Check:** zero divergences across the full scenario matrix on linux-x64 and darwin-arm64, plus a
crash-injection run (SIGKILL at each of the ~12 points the pending-slot tests already enumerate) where
*both* implementations recover to the same state and each can recover a transaction the *other* armed
— proving the on-disk format is genuinely one format, not two.

### Phase 4 — Cut over; delete the Python

Publish `0.9.0` as four native binaries + signed `SHA256SUMS`. Add the tagged-release CI job that
Install-UX step 7 has owed since 2026-08-14 and that does not exist today (`.github/workflows/`
contains only `real-key-testing.yml` and `validate.yml`). Then delete §5.1 and §5.2 in one commit —
not behind a flag, not with a compatibility shim. The legacy-state importer is a **one-shot** program
(`ccodex-import-legacy-state`, Python, ~150 lines) that reads the six old stores, writes one
`state.json` + one sealed receipt per plane, and is **deleted in the same release that ships it**.
That is the "do not preserve throwaway compatibility states" principle taken literally: the target
architecture contains exactly one schema and refuses any other by name with the remedy "reinstall",
which is the doctrine the current tree already chose (`install_skill_bundle.py:266-289`).

**Check:** on a fresh `ubuntu:24.04` container and a fresh macOS 27 host, run §2's literal command
sequences with nothing pre-seeded, non-root, credential-free — and assert on *output*, not exit
codes. Additionally: an operator upgrading from `0.7.4` runs the importer and then `ccodex status`
reports the same owned inventory the old six-store fan-out reported, proven by comparing against a
pre-upgrade `--json` capture.

### Phase 5 — Project scope (the one genuinely new capability)

`--scope project` with the repo-root guard, copies-only, home-local receipts keyed by
`(host, scope, root)`. Follows `manage_claude_workflows.py`'s worked template (report 01 §E.3), and
respects ADR-0022's rejected option "spray one standard scaffold into every repository" by requiring
`--scope project` explicitly, per repo, with a printed diff.

**Check:** two repositories installed at project scope plus one user-scope install coexist; each
uninstalls independently without touching the others; the state document names all three; nothing is
written inside `.git`; and `ccodex install --scope project` outside a repo root refuses at exit 3.

### Phase 6 — `update --self` (last, on purpose)

Only after a full release cycle of Phase 4 shipping. mise-installed copies **refuse** and print the
mise command — no second update authority (ADR-0021:24-26). curl-installed copies require
`--to <version> --expect <sha256>`, stage a sibling temp file, verify the digest, execute the staged
binary's own `verify`, then one `rename(2)`.

**Check:** on POSIX, a self-update under `kill -9` at each of five injection points always leaves
either the old or the new binary fully functional, never a half-written file — guaranteed by
construction since the only mutation is a single rename (report 03 §e).

---

## 7. Supply-chain story

### 7.1 The certified target set is four, not eight — deliberately

ADR-0027 makes OS/arch/acquisition-plane separate tuple rows with **no inheritance** (`:38-45`), so
each extra target is an evidence obligation, not a free win. ADR-0031 fact 2 counted "one CLI inverts
into five platform binaries, ~350 MiB per release". That fact is **conceded**, and paid for by buying
fewer tuples:

| Target | Tier at 0.9.0 | Why |
|---|---|---|
| `bun-linux-x64` (glibc) | **certified** | The repo's existing certification boundary (`docs/plans/…:259`). |
| `bun-darwin-arm64` | **certified** *iff* Phase 1 item 1 is green | The operator's own host; blocked on the signing gate. |
| `bun-linux-arm64` (glibc) | capability-qualified | Cheap: same libc, native runner available. |
| `bun-darwin-x64` | capability-qualified | Bun does not ad-hoc-sign x64 Mach-O at all; ours is Developer-ID signed anyway. |
| `*-musl`, `bun-windows-*`, armv7/32-bit | **not shipped** | musl builds do not run on glibc hosts (ADR-0031:33-40); Windows drags oven-sh/bun#32011 (open, unresolved: spawning Rust-compiled `.exe` hangs — and `uv.exe` is exactly that profile), Authenticode ordering (#20109/#22960), and SmartScreen reputation with no publisher whitelist (report 03 §d). **armv7 and 32-bit do not exist at the type level in Bun** and never will be discharged by waiting. Windows operators use WSL2, which is what the repo already certifies. |

Release weight: 4 × ~64–90 MB ≈ **280–340 MB per release**, against 120 KB of bash today. That is the
real cost. It buys the removal of ~1.3 GB from every *operator's* machine, which is the number a
fresh operator experiences.

### 7.2 Zero cross-compile downloads: the answer to ADR-0031 fact 3

ADR-0031's third measured fact is the strongest of the five: `bun build --compile` fetches
cross-compile target runtimes from a hardcoded `registry.npmjs.org` with **no checksum verification
at all**, making >99.99% of executed bytes unpinned; oven-sh/bun#36173 is still open as of
2026-08-24 (report 03), and even merged it only checks registry-supplied `dist.integrity`, so a
compromised registry satisfies it (ADR-0031:80-96).

This design does not argue with that measurement. It **removes the code path**:

- Build each target **natively on that target's own OS/arch runner**. Never pass `--target`. Bun does
  not download a runtime for the host target.
- Pass `--compile-executable-path "$(mise where bun)/bin/bun"` explicitly, so the embedded runtime is
  the exact binary this repository already digest-pins: `mise.lock:31-33` pins `macos-arm64`
  `sha256:c669e97f6164e1c96e0701748db98dfa77492908cbd8394c7557134a735de381`, `:15-17` pins
  `linux-x64` `sha256:2d03fb5f…`, `:7-9` pins `linux-arm64` `sha256:4b1a332e…`, all from
  `github.com/oven-sh/bun/releases/download/bun-v1.4.0/…`. **The repo already owns the digest pin
  ADR-0031's harvest precondition demands** — it is `bun = "1.4.0"` at `mise.toml:18` plus
  `mise.lock`, and it is verified by mise on install, fail-closed.
- Assert the absence of network access during compile (Phase 1 item 8), and assert the embedded
  runtime's digest by extracting it from the compiled output and comparing to `mise.lock`.
- Build flags, all mandatory, all from ADR-0031:80-96:
  `--no-compile-autoload-dotenv --no-compile-autoload-bunfig` (both default ON; a default build
  ingests a working-directory `.env`/`bunfig.toml` in violation of the environment-allowlist
  contract), and **never** a packaging path that runs `strip` (it destroys the binary while
  `--version` still answers 0).
- At run time, scrub `BUN_BE_BUN` and `BUN_OPTIONS` from the process env before any work and from
  every child's env. Report 03 corrects the survey here: `BUN_OPTIONS` argv-splicing was fixed in Bun
  1.2.23 (PR #26346, issue #21496 closed `COMPLETED`), so the residual is "ambient runtime-flag
  control", not arbitrary argv injection — narrower, but `BUN_BE_BUN=1` full-CLI takeover remains
  open and undiminished, so the scrub stays mandatory.

Net: the unpinned fraction of executed bytes goes from >99.99% to **~0%**, using a pin the repository
already maintains. This is the single strongest supply-chain claim in the design, and it is a
*topology* change, not a hoped-for upstream fix.

### 7.3 The split digest chain: the answer to ADR-0031 fact 4

Compiled output is measurably non-reproducible: three identical-input builds, pairwise-distinct
sha256, first difference at offset 82,481,180 (ADR-0031:48-56). The ADR ties this to a control the
repository "will not trade away", and notes correctly that waiting cannot fix it.

This design does not claim to fix it. It **confines** it, by splitting the chain at the layer where
reproducibility is load-bearing:

```
REPRODUCIBLE (unchanged)                       NOT REPRODUCIBLE (new, bounded)
git tag v0.9.0                                 ccodex-<target>            (carrier)
  └ git archive (build_release.py:202-287)       └ digest over SHIPPED bytes only,
      └ manifest.json: per-file sha256,              published in signed SHA256SUMS
        candidate_id = sha256(inventory)            never rebuild-and-compare
              │                                            │
              └──────── embedded, and re-derivable ────────┘
                        by the operator at any time:
   git archive v0.9.0 | ccodex verify --manifest -   ⟹  candidate_id matches
```

What the operator can still prove, independently of the binary: **that the payload inside binary X is
exactly the payload of tag v0.9.0.** `ccodex verify` re-hashes every embedded entry against the
embedded `manifest.json` and prints `candidate_id`; `git archive` at the tag plus
`build_release.py --manifest-only` produces the same `candidate_id` from source. So the question that
actually matters — *what bytes are you about to put in my `~/.claude`?* — remains answerable by
rebuild-and-compare. Only the question *were these 82 MB of runtime produced from these inputs?*
becomes digest-over-shipped-bytes.

**This is a genuine trade and it needs its own recorded decision.** ADR-0031 says so explicitly:
reopening on the determinism axis "requires either Bun becoming reproducible or an explicit,
separately recorded decision to trade that control away — which is a different ADR". The proposed
ADR-0032 must make that trade in its own words, bounded to the carrier, with §7.3's split as the
mitigation.

### 7.4 Signing, Gatekeeper, notarisation

- **Order is fixed by upstream design, not style:** compile first, sign last. Bun *strips* any
  pre-existing Authenticode section before writing its own `.bun` section, because post-compile
  `signtool` signing previously corrupted the payload by appending bytes after Bun's
  `[u64 length][payload]` trailer (oven-sh/bun#20109, fixed by #22960 in Bun 1.2.23 — report 03 §d).
  Anything that appends trailing bytes after signing re-creates that failure.
- **macOS:** each darwin binary is `codesign --force --timestamp --options runtime`-signed with a
  Developer ID Application certificate, submitted to `notarytool`, and stapled — in a CI job separate
  from the compile job, mirroring opencode's verified `sign-cli-windows` shape (report 03 §d). This
  is an obligation we have regardless of Bun (`curl`-downloaded binaries hit Gatekeeper), and it is
  the mechanism by which Bun 1.4.0's regressed ad-hoc arm64 signature is *replaced* rather than
  worked around. **Phase 1 item 1 must prove it.** If re-signing does not clear the macOS-27 SIGKILL,
  darwin-arm64 is not shippable until a Bun 1.4.1+ carries #39837, and `mise.toml`'s pin must move
  first (Bun ships no backports — report 03 §f).
- **Windows:** not in the certified set, so no Authenticode certificate, no Azure Trusted Signing
  subscription, and no SmartScreen-reputation problem is taken on at 0.9.0.
- **Both:** `SHA256SUMS` is signed with cosign keyless (GitHub Actions OIDC), so the operator verifies
  a signature bound to this repository's workflow identity, not to a long-lived key someone has to
  hold. GitHub build provenance attestation is emitted for each artifact.

### 7.5 What the operator reviews before trusting

Exactly four things, in this order, and each is a single command:

1. **The signature over the digest list** — `cosign verify-blob … SHA256SUMS` (or, on the mise path,
   mise's own fail-closed checksum verification against the lockfile entry).
2. **The digest of the bytes they downloaded** — `sha256sum -c SHA256SUMS --ignore-missing`.
3. **The payload's provenance, independently of the binary** — `ccodex verify` prints `candidate_id`;
   `git archive v0.9.0 | ccodex verify --manifest -` re-derives it from the tag.
4. **What it is about to write** — `ccodex install --host claude --scope user --dry-run` lists every
   destination, its prestate (`absent`/`owned`/`foreign`/`modified`), and the exact digest, taking no
   lock and writing nothing. This also fixes report 01 §D.5: today `bundle:status` *structurally
   cannot* see an unowned collision and the operator must know to run `install --dry-run` instead; in
   the new model `verify` and `status` both report unowned collisions in the configured collections.

What the operator is **not** asked to do, and is asked to do today: `mise trust` a `mise.toml` they
did not write, inside a release tree they did not clone, as a precondition for the first tool-needing
verb (`bin/ccodex:111-137`, `README.md:270-272`).

---

## 8. Addressing the three named hard problems

### 8.1 The Python lifecycle modules' invariants: reimplemented, wrapped, or deleted

Report 05 §d names five implications for any compiled rewrite. Answering each directly:

| Report 05 finding | Disposition | How |
|---|---|---|
| **d.1** `runtime_admission()` requires CPython exactly `3.12.11` **and** `-I -B` on every verb (`ccodex_sdlc.py:454-471`); a frozen/compiled binary reproducing neither is refused at exit 3 by design — the exact failure live-verified against `v0.7.4`. | **DELETED** | The invariant it protects is "the bytes executing this lifecycle are the reviewed bytes". A compiled binary answers that with its own digest, not with an interpreter interrogation. Replaced by `assert_self_identity()`: on every mutating verb, re-hash the embedded `manifest.json` inventory and refuse at exit 3 if any entry mismatches, and record `source.binary_sha256` in the receipt. This is strictly stronger (it covers the *payload*, which `runtime_admission` never checked) and it cannot be broken by a dispatcher, because there is no dispatcher. |
| **d.2** Sibling-loading by absolute non-symlink path (`importlib.util.spec_from_file_location`, never `sys.path`), whose refuse-on-absence gives a stripped distribution a named exit-3 refusal rather than a crash. | **DELETED, invariant re-expressed** | A monolithic binary cannot be "missing a file". The *observable* invariant — an incomplete distribution refuses by name rather than crashing — becomes the embedded-manifest completeness assertion above, which fires before any effect and names the missing/mismatched entry. |
| **d.3** `ccodex_sdlc_readonly.py` enforces read-only by monkey-patching `os`/`io`/`builtins.open`/`subprocess`/`shutil`/`Path` write primitives; no Bun equivalent short of a process-isolation redesign. | **REPLACED, with a stated loss** | Two mechanisms, both build-time. (a) **Import-graph boundary:** all write primitives live in one module (`src/fs/mutate.ts`); reader entry points may not reach it, enforced by a dependency-graph test that walks `bun build --analyze` output and fails the gate on any edge. (b) **Type-level capability:** readers receive a `ReadOnlyFs` interface; `MutatingFs` is constructible only inside the write plane's entry. **The honest loss:** the Python guard is a *run-time* trap that catches a mistake in a shipped binary; the replacement catches it before shipping and not after. The guard's own docstring already disclaims being an adversarial same-UID sandbox (`:1-8`), so the class of adversary is unchanged — but a reader defect that slipped past the gate would be unmitigated at run time, and that is a real regression. Recorded, not hidden. |
| **d.4** `recover --apply <digest>` re-derives the plan and refuses on mismatch, which is safe under a binary upgrade but means plan derivation must be byte-identical between the dry-run and the apply. | **PRESERVED, and hardened** | Plan derivation is pure and versioned: the derived plan document carries `derivation_version`. A digest approved by binary A and applied by binary B with a different `derivation_version` refuses by name ("the approval was rendered by a different plan derivation") instead of silently mismatching. Also: no timestamps in derived plans, pinned by a test. |
| **d.5** The Linux-x86_64 platform gate is duplicated across four files with two different spellings and no single source of truth. | **DELETED (centralised)** | One build-time constant per target tuple (`TARGET_TUPLE`, `SUPPORT_TIER`), injected by `--define` at compile, surfaced by `ccodex verify`. ADR-0027's no-inheritance rule becomes a data field instead of four literals someone must remember to edit. |

The 52 invariants catalogued in report 01 §C map as follows. **Preserved verbatim in behaviour**
(re-expressed in TypeScript, each pinned by a Phase-0 seam test): #1–#13 (fail-closed state and
record refusals, collection boundary, post-publish validation, `rename_absent`, marketplace overlap),
#20–#24 (gateway health verdict, settings refusals, `set-fast-model` provider refusal), #27–#34
(never runs `mise trust` — trivially, since there is no config to trust; installing never runs or
enables; no PATH edits; no shell aliases; the read-never-write posture toward global settings
documents; maintenance verbs stay off the use surface; libraries never vendored; help is never
effectful), #35–#41 (dry-run writes nothing and takes no lock, lock-free `status`, locator-based
projection, retained records for an earlier configured root, digest-as-approval), #42–#44 (self-tests
as gate leaves), #45–#49 (unresolved path spelling, private 0700 staging beside the destination,
leftovers named-never-deleted, the one-derivation-point exit vocabulary). **Deleted with their
subject:** #14–#19 (operator-tools template/bash/PATH/Windows/bin-dir refusals), #25–#26 (the PATH
precondition and its before-the-lock ordering), #46 (junction metacharacters), #50–#52 (the
one-file-on-PATH doctrine, `AGENTIC_SDLC_ROOT`, the pinned-node PATH prepend and its named
`npm`/`npx` consequence). **Strengthened:** #21 (`jq` never from ambient PATH → there is no `jq`),
#28 (installing a hook never enables it → `activate hook` is a separate verb with a printed diff),
and idempotency (§4.4).

**Test-suite carry-over.** The 11,512 lines across `test_install_skill_bundle.py`,
`test_operator_tools.py`, `test_ccodex_sdlc*.py`, and `test_lifecycle_exit_conformance.py` are not
ported line-by-line and are not thrown away. Phase 0 converts their *assertions* — which are about
argv, printed lines, receipt bytes, and exit codes — into a language-neutral seam harness that runs
against the Python implementation first. That harness is then the differential oracle in Phases 2–3,
and the acceptance criterion is byte-identical output from both implementations. ADR-0031's fact 5
observed that "a language swap orphans the suite that would have to prove the swap"; Phase 0 is the
de-orphaning, it is the ADR's own trigger 3, and it has standalone value.

### 8.2 Signing / Gatekeeper

Covered in §7.4. The three load-bearing points: compile-then-sign is mandatory upstream behaviour,
not preference; our Developer ID signature replaces Bun's regressed ad-hoc one and is the proposed
route around oven-sh/bun#39764 without waiting for a release that does not exist; and this claim is
**UNVERIFIED** and is Phase 1's first and highest-risk gate.

### 8.3 The opencodex gateway half — it stays outside the binary

**Decision: outside. The gateway *program* is never embedded; the gateway *supervision logic* comes
in-process.**

Why outside:

- ADR-0005 puts `npm:@bitkyc08/opencodex` 2.28.0 in the **convenience tier**: no gate consumes it,
  absence degrades DX only, and its integrity surface is "version+backend only, no tarball hash and
  no transitive integrity" — accepted *precisely because* nothing in the gate graph depends on it
  (`docs/adr/0005-…:213-222`). Embedding an unhashable transitive npm tree into a binary whose whole
  supply-chain story is "~0% unpinned bytes" (§7.2) would destroy that story for a component ADR-0017
  calls optional and used only by the routed-model profile.
- `ocx` is a `#!/usr/bin/env node` script (`install_operator_tools.py:334-339`), so embedding it
  means embedding Node as well as Bun. Its own postinstall lays down an 89 MB `bun` 1.3.14
  (`mise.toml:66-67` comment) — a *third* Bun runtime on the operator's disk.
- ADR-0002's blast-radius rule: a pin's failure exits the whole install. Keeping the gateway on its
  own front door means a gateway problem can never break `ccodex install`.

Why the logic comes inside:

- `scripts/opencodex-claude.sh`'s 2,681 lines are mostly *refusals*: route-integrity classification
  over env vars, three classes of settings document, and explicit `--settings` values, exiting 3
  before the gateway starts (`:565-582`, `:981-1648`). That is the exact component ADR-0031 approved
  harvesting to Bun and measured winning: 130 ms of six uncached `mise exec -- jq` spawns → 24 ms
  in-process (ADR-0031:67-71). This design differs from the approved harvest only in that the
  classifier is a *function in the one binary* rather than a helper spawned by a bash launcher —
  which removes a process boundary rather than adding one, and removes the pinned-helper-digest
  problem entirely (the helper's digest is the binary's digest).

The resulting boundary, precisely:

```
ccodex gateway {status|launch|launch-ultracode|restart|configure|models|set-fast-model}
  ├ in-process: settings-bypass classifier, env allowlist, argv assertions, refusal exits (0/2/3),
  │             argv echoed on refusal paths, 835 forensics comments ported verbatim
  ├ resolves `ocx` by ABSOLUTE path only: $AGENTIC_SDLC_OCX (must be absolute) or an operator-named
  │   path; NEVER a bare-name $PATH lookup (report 03 §g#1), NEVER an ambient selection (ADR-0020)
  ├ reads back `ocx --version` and refuses if it is not the version the operator declared
  └ `ocx health` is the ONLY health verdict; no ocx verb's exit code is ever accepted (ADR-0005:143-157)
```

If `ocx` is absent, every gateway verb refuses at exit 3 naming the install command, and **no other
verb is affected** — which is a strict improvement on today, where `operator-tools:install` refuses
to install anything at all unless the entire gateway toolchain including the 2.28.0 npm package
resolves first (report 01 §D.3).

---

## 9. ADR engagement: what this supersedes, and the honest evidence ledger

### 9.1 The records this design touches

| Record | Status | This design's relationship |
|---|---|---|
| **ADR-0031** (accepted 2026-08-23): "`ccodex` stays bash-plus-Python. No full or partial rewrite of the installer, updater, or launcher into Bun (or Go)." | Accepted | **Superseded in item 1 by a new ADR-0032.** Cannot be amended; ADR-0031 imposes a burden of proof on re-proposers ("must show which measured fact changed", `:141`) and three conjunctive revisit triggers. §9.2 discharges that burden explicitly and incompletely. |
| **ADR-0021** (proposed): versioned mise release, one `ccodex`, "no self-updater in the first release", "the release must package private runtime dependencies without depending on a prunable release root" | Proposed | **Honoured and completed.** This design is the first thing that actually *packages* the runtime — the plan's undone step 5 (`docs/plans/…:56-78`) — because the runtime is the carrier. ADR-0021's rejected "self-updating standalone binary… creates a second update authority before the receipt-backed lifecycle is proven" is honoured by Phase 6 being last, by mise-installed copies **refusing** to self-update, and by curl-installed copies requiring an operator-named digest. `install --host claude` remains a **separate** command from acquisition, so item 3 ("installing `ccodex` does not activate a repository, trust configuration, …") stands. |
| **ADR-0002** (accepted): mise is the single front door; no second bootstrap prerequisite | Accepted | **Honoured, and strengthened.** mise remains the primary front door and remains the *only* prerequisite. The design *removes* prerequisites (uv, node, jq, an exact CPython, `bash`), and shrinks `mise --locked install`'s blast radius on the use plane to zero because the use plane no longer reads `[tools]`. `git` is not added as a dependency — the project-scope guard checks for `.git`'s presence, spawning nothing. Route B (curl) is documented as a fallback, not a second prerequisite; `curl` is already a decided host capability (`docs/plans/…:141-147`). |
| **ADR-0011** (accepted): a remote bootstrap manages the clone instead of eliminating it | Accepted | **Its reversal condition fires.** ADR-0011's core reason is "the tree is a run-time dependency — every Python entrypoint anchors on `Path(__file__).resolve().parents[1]`" (`:38-52`). Embedding the payload removes the run-time tree, so "the clone cannot be eliminated" stops being true. ADR-0011's own supersession clause requires archive builder + release workflow + copy activation + clean-host tests + first release; Phases 4's CI job is the missing one. |
| **ADR-0019** (accepted): fresh authorization per effect | Accepted | **Honoured.** Acquisition, activation, statusline binding, hook binding, and workflow activation remain five separate operator acts. Nothing is folded. `--dry-run` prints the exact effect; `recover --apply` and `update --self` are digest-bound. |
| **ADR-0020** (accepted): exact verified dependencies; ordinary commands never silently resolve/install/update/fall back | Accepted | **Honoured, and its hardest open problem retired.** The jq-resolution problem (`:66-67` forbids ambient-PATH selection of a readiness-dependent executable; the canonical defect is the fresh-host `jq` incident) disappears because there is no jq. `update --self` is a separate reviewed lifecycle operation with a named version and a named digest — item 4 is satisfied by construction, not by promise. |
| **ADR-0027** (accepted): per-tuple compatibility evidence, no inheritance | Accepted | **Honoured, and paid for.** Four targets, two certified, tiers as data (`source.support_tier`), and the honest statement that "cross-platform" buys no tier. |
| **ADR-0017** (accepted): `ccodex` is the operator CLI, not a second product brand | Accepted | **Honoured, with a named tension.** A signed, notarised, self-updating multi-platform binary is more product-shaped than a rendered bash script. The mitigation is scope discipline: the binary gains no capability the current surface lacks except project scope; maintenance verbs stay off it (`bin/ccodex:95-97`); it does not become an agent runtime. |
| **ADR-0022** (amended): repository activation via digest-approved plans | Amended | **Respected.** Project scope is not a revival of the deleted `.agentic-sdlc/repo.toml`/activation-planner/machine-local-receipt machinery (items 1,2,3,7 no longer bind). It is per-repo, explicit, diff-printed, copies-only file placement — the surviving `apply --target … --yes` shape. |

### 9.2 The evidence ledger against ADR-0031's five measured facts — stated honestly

| ADR-0031 fact | Status as of 2026-08-24 | This design's answer |
|---|---|---|
| **1. The motivating defect is not a bash defect.** The Windows argv corruption reproduced *identically* in the compiled binary; going native additionally enters MSYS2 path mangling. | **UNCHANGED. Not overturned.** | **Conceded entirely.** This design does not claim Bun fixes the PowerShell crossing, and it does not ship Windows at all. The motivating benefit ADR-0031 measured at zero is *not* claimed here. The claimed benefit is different: deletion of the interpreter-acquisition layer and of the acquisition plane. |
| **2. "One cross-platform CLI" inverts into N platform binaries; ~350 MiB/release vs 120 KB; no armv7; macOS signing regressed; `strip` is a landmine.** | **UNCHANGED.** Bun 1.4.0 is still the only 1.4.x release; #39764's fix is in no release (report 03). | **Conceded and paid for.** 4 targets not 8 (~280–340 MB), armv7 abandoned explicitly, `strip` banned in CI, and the macOS signature owned by us (Developer ID + notarisation) rather than by Bun's ad-hoc signer. Phase 1 item 1 is the gate; if red, darwin-arm64 does not ship. |
| **3. Supply chain fails this repo's own bar:** cross-compile runtimes fetched from a hardcoded npm registry with no checksum verification; >99.99% of executed bytes unpinned; #36173 open. | **UNCHANGED upstream** (#36173 still open, report 03). | **Dissolved by topology, not by argument.** Native per-target builds never touch that code path; `--compile-executable-path $(mise where bun)/bin/bun` embeds the runtime this repo *already* digest-pins in `mise.lock:7-37`. Unpinned fraction → ~0%. Phase 1 item 8 proves zero network activity during compile. This is the one place where the design genuinely improves on what ADR-0031 evaluated, because ADR-0031's spike cross-compiled twelve targets. |
| **4. Compiled output is not reproducible** (3 builds, pairwise-distinct sha256). | **UNCHANGED, and unfixable by waiting** — ADR-0031 says so. | **Not contested; confined and traded, requiring its own recorded decision.** The payload keeps `git archive` + `manifest.json` and stays independently re-derivable from the tag (§7.3); only the carrier becomes digest-over-shipped-bytes. ADR-0032 must make that trade explicitly. **This is the largest unresolved objection to the design.** |
| **5. The tax being avoided does not exist:** one runtime seam, mise supplies the interpreter invisibly, ~400 lines saved, 2.8× slower startup, in-process test suite orphaned. | **PARTIALLY OVERTURNED — one measured fact changed, on 2026-08-24, after ADR-0031 was written.** | This is the only fact this design claims moved, and the claim is precise: **that seam was not invisible.** Report 05 live-verified against the published `v0.7.3`/`v0.7.4` artifacts that `bin/ccodex` routed `ccodex sdlc *` through `uv run --script` (no `-I -B`), which `ccodex_sdlc.py:454-471` refuses by name, so **every `ccodex sdlc` verb — including the receipts-gated install — exits 3 on the only artifact an operator can download**, and the researcher independently reproduced `sys.flags.isolated/no_user_site/dont_write_bytecode` all false under that invocation. The fix (`main@cd3fd3d`, seed `agentic-sdlc-dca4`) landed and closed the same day and is **unreleased**. So the first two public releases of this product shipped with the receipts lifecycle wholly inoperative because a bash dispatcher constructed the wrong interpreter invocation. ADR-0031's "mise, already the sole bootstrap prerequisite, supplies that interpreter invisibly" is now falsified by a shipped, live-verified defect. The other components of fact 5 stand: the ~400-line saving is right (§5.3 concedes it), startup is still 2.8× slower than bash (mitigated only where jq spawns dominate — §6 Phase 1 item 7 measures the statusline case), and the orphaned-suite problem is real and is what Phase 0 exists to fix. |

**The three conjunctive revisit triggers, scored:**

| Trigger | Status | What would close it |
|---|---|---|
| 1. Bun pins or verifies compile-target runtime downloads by digest (#36173) | **NOT MET** (open, unmerged) | This design argues the trigger is **satisfiable a different way**: it is not needed if the design never downloads a compile-target runtime. That is a re-framing, and a reviewer is entitled to reject it and insist on the literal trigger. Phase 1 item 8 is the evidence that the re-framing is real. |
| 2. Post-demolition `ccodex` surface stable for at least one release | **NOT MET** | The demolition ranks (~75,500 lines across five ranked deletions, `docs/research/2026-08-22-overengineering-audit.md:21-31`) have not landed, and `v0.7.4`'s dispatcher required a same-day fix. Nothing in this design can substitute for waiting. |
| 3. `sdlc` tested through its subprocess seam | **NOT MET** (measured: 70 of 71 test files call `module.main()` in-process) | **Phase 0.** This is the one trigger this design can close by doing work, and it has standalone value. |

**Verdict, stated plainly: 0 of 3 triggers are met today, and only one of five measured facts has
moved.** Therefore ADR-0032 cannot honestly be written now. What can be written now is a **decision
to run Phase 0 and Phase 1**, whose combined output is (a) trigger 3 closed, (b) the re-measurement
ADR-0031 demands and forbids inheriting, and (c) a go/no-go on the four items (macOS Gatekeeper,
`--asset` at scale, durability primitives, own-path resolution) that would each independently kill
the design. If Phase 1 comes back green and the demolition lands one release, all three triggers are
met and the supersession is arguable on the record rather than on ambition.

**The single decisive experiment**, if only one can be run: Phase 1 item 1. Compile natively on macOS
27 arm64, sign with a Developer ID, notarise, staple, and run it on a clean macOS 27 host. If a
signed-and-notarised Bun 1.4.0 arm64 binary is still SIGKILL'd, then the operator's own primary
platform is unreachable until an unreleased upstream fix ships, and every other argument in this
document is moot for the next release cycle.

---

## 10. Explicit tradeoffs vs the status quo

| Dimension | Status quo (v0.7.4) | This design | Verdict |
|---|---|---|---|
| Fresh-operator commands to a working Claude plane | 5 documented (README `:11-15`) but the Quickstart says "Five steps" and lists six, and the two disagree on `--agent` (report 01 §D.1) | 3 (`mise use -g`, `verify`, `install`) | **Better** |
| Use-plane bytes on the operator's disk | ~1.3 GB of mise toolchain + release tree; auto_install fires on the first `mise run` (`README.md:344-348`) | one 64–90 MB file | **Much better for the operator** |
| Release weight | 120 KB of bash + a ~2 MB source tarball | 280–340 MB across 4 targets | **Much worse** (ADR-0031 fact 2, conceded) |
| `mise trust` of a config the operator did not write | Required before the first tool-needing verb, even on the release plane (`bin/ccodex:111-137`) | Not required; no config is read | **Better** |
| PATH mid-install interruption | `operator-tools:install` refuses unless the bin dir is already on PATH → edit rc, new shell, re-run (report 01 §D.2) | No PATH file installed; mise shims or a single `install -m 755` | **Better** |
| Runtime dependencies of the use plane | uv, an exact CPython 3.12.11 acquired as a side effect of an unrelated task, node, jq, bash, mise | none | **Better** |
| Interpreter-acquisition failure class | Live defect in both published releases: every `sdlc` verb exits 3 (report 05, live-verified) | Structurally impossible | **Better** — and this is the design's core claim |
| Front doors for "install the bundle" | 2 (`ccodex bundle install`, `ccodex sdlc install`), sharing one ownership ledger but only one producing receipts (report 05 §c) | 1 | **Better** |
| State stores to answer "what is on this machine" | 6, of which the aggregate reader projects 2 (report 01 §D.4) | 1, fully projected | **Better** |
| Acquisition receipt plane + manual placement bridge | Required by `install`/`update`; the GitHub-download → receipt bridge is a manual shell recipe labelled temporary | Deleted; the binary's digest is the acquisition identity | **Better** |
| Build reproducibility of the shipped artifact | `git archive` → byte-reproducible from a tag | Carrier not reproducible; payload still is (§7.3) | **Worse**, bounded; needs its own ADR |
| Supply-chain pinning of executed bytes | ~100% pinned (mise.lock + git archive) | ~100% pinned *if* native builds are used; >99.99% unpinned if anyone ever passes `--target` | **Equal, conditional on a CI discipline that must be enforced by a test** |
| Platform coverage claims | Linux x64/WSL certified; macOS unproven for the `sdlc` machinery (Linux-x86_64 gate duplicated in 4 files) | 2 certified tuples incl. darwin-arm64, gate centralised — **conditional on the signing experiment** | **Better if green, no change if red** |
| Windows | Refused first, before `Path.home()` is evaluated | Not shipped; WSL2 only | **Equal** |
| armv7 / 32-bit | Works (bash + Python) | Impossible (no Bun target) | **Worse** — an absolute capability loss, unfixable |
| macOS Gatekeeper / notarisation obligation | none (scripts) | Developer ID cert, notarytool, stapling, per release | **Worse** (new recurring cost and a new secret to hold) |
| Startup latency, ordinary verb | bash 8.7 ms | ~24 ms | **Worse** (2.8×, ADR-0031 measured) |
| Statusline render latency | bash + up to 6 uncached `mise exec -- jq` spawns ≈ 130 ms | one in-process parse ≈ 24 ms | **Better** — the one latency users actually feel |
| Read-only enforcement for reader verbs | Run-time stdlib monkey-patch (`ccodex_sdlc_readonly.py`) | Build-time import-graph + type boundary | **Worse at run time, better before shipping** |
| Test suite | 55,763 lines, 70/71 files calling `main()` in-process | Same invariants via a language-neutral subprocess seam + a differential oracle | **Better structurally, and a large one-time cost** |
| Idempotency of `install` | Copy entries refreshed unconditionally every run | Convergent; a re-run over an unchanged host reproduces a bit-identical receipt | **Better** |
| Project scope | No first-class support; `--claude-home <repo>` works mechanically with a user-global state document and a spurious legacy-state hazard | First class, explicit, repo-root-guarded, scope-keyed receipts | **Better** |
| Output-style delivery | Ships in the release payload (`policy/release-candidate.v1.json` `payload.trees`) but is **not discovered by `install_skill_bundle.discover_entries()`** — verified: no `output-styles` reference in the installer. Neither channel installs it. | A first-class collection | **Better**, and it closes a gap report 04 mis-attributed to the custom installer |
| Contributor workflow | clone + `mise trust` + `mise --locked install` + `mise run check` | Unchanged | **Equal** (deliberately) |
| Language count in the repo | bash + Python | bash (gates) + Python (gates/tests) + TypeScript, until Phase 4 completes, then bash + Python (contributor) + TypeScript (product) | **Worse during migration; roughly equal after** |
| ADR debt | — | One supersession (ADR-0031 item 1), one determinism trade, ADR-0021 promoted, ADR-0011 reversed | **Worse** — and it must be paid before, not after |

---

## 11. Open questions

1. **Does a Developer-ID-signed, notarised, stapled Bun 1.4.0 arm64 binary run on macOS 27?** The
   whole design's viability on the operator's own platform rests on re-signing displacing Bun's
   regressed ad-hoc signature (oven-sh/bun#39764, fixed on `main`, in no release). **UNVERIFIED.**
   Phase 1 item 1. If red: does the project pin an unreleased Bun from `main` (violating "exact
   verified execution dependencies" in spirit — a `main` build has no release digest to pin), or wait
   for a 1.4.1 that may never come, given Bun ships no backports?
2. **Can a compiled binary reliably learn its own absolute path?** Needed for `statusLine.command`
   and for self-update staging. `process.argv[0]` is the literal `"bun"` inside a compiled binary and
   the fix (#32851) is open. `process.execPath` is untested here. **UNVERIFIED.**
3. **Is there an asset-count or size cliff in the 1.4.0 `--asset` code path?** The older mechanism had
   a *silent* exit-0 cliff at 8 files. 37 entries with nested trees is well past that count in the old
   mechanism's terms. **UNVERIFIED for 1.4.0.**
4. **Is `F_FULLFSYNC` reachable from Bun on Darwin?** The receipts substrate's durability barrier
   depends on it (`install_skill_bundle.py:507-540`). Proposed answer is a `bun:ffi` `fcntl` shim.
   Untested.
5. **Does the determinism trade survive review?** §7.3 confines non-reproducibility to the carrier and
   keeps the payload re-derivable, but ADR-0031 frames build determinism as a control the repository
   "will not trade away". If the answer is a flat no, this design cannot proceed in any form and the
   correct alternative is the approved harvest plus a thinner Python installer.
6. **Who holds the Apple Developer ID and the cosign identity, and what happens when the certificate
   expires?** A signing key is a new operational obligation with no current owner and no rotation
   story. It also creates a release-blocking single point of failure the current bash artifact does
   not have.
7. **Does `mise use -g "github:org/repo@X.Y.Z"` digest-pin for a *global* install?** mise's `github:`
   backend locks per-platform checksums in a project `mise.lock`; whether a global install records or
   verifies a checksum is unconfirmed, and the repo has already disabled `github.slsa` and
   `github.github_attestations` globally to avoid rate limits (`mise.toml:6-12`). If the global path
   has no local pin, route B (curl + signed `SHA256SUMS`) is the *stronger* integrity path and the
   README should say so — which is an awkward outcome for "mise is the single front door".
8. **What is the actual compiled size with the payload embedded, and does `--asset` compress?** The
   payload is ~1.9 MB uncompressed (measured), which should be noise against 64–90 MB, but total
   release weight is the design's biggest concession and deserves a measurement rather than an
   estimate.
9. **Should the Codex plane (`--host codex`, 21 entries today) be certified, deprecated, or left
   uncertified?** ADR-0017 gives companion hosts no parity promise. Keeping the code path costs
   little; certifying it costs an ADR-0027 tuple row per platform.
10. **Does deleting the self-marketplace strand existing users?** Anyone who installed via
    `claude plugin install agentic-sdlc@agentic-sdlc` has a Claude-managed plugin cache the binary
    will refuse to co-install with (`marketplace_overlap()`). The migration story for those operators
    is "uninstall the plugin, then `ccodex install`" — and nothing today measures how many such
    installs exist.
11. **How does the read-only guarantee get re-established at run time?** The import-graph boundary is
    a build-time control. If a reader defect ever ships, there is no run-time trap. Is a separate
    unprivileged child process for readers worth the second process boundary — and does that
    re-introduce the own-path problem from question 2?
12. **Is the ~8–11k-line TypeScript estimate right?** If it lands closer to 15k, the design is a
    lateral move in code volume that buys structural deletions and pays a signing, determinism, and
    armv7 cost — which is a materially weaker trade than §10 claims.

---

## Appendix — measurements taken for this document

Run against `/tmp/asdlc-research` at HEAD `e0fbf92` on 2026-08-24. No `mise` task was executed; the
config was left untrusted.

- Payload tree sizes (`du -sk`): `skills` 1552 KB, `agents` 256 KB, `commands` 48 KB, `policy` 44 KB,
  `workflows` 8 KB, `hooks` 4 KB, `output-styles` 4 KB → **~1.9 MB** of payload to embed.
- Implementation line counts (`wc -l`): `install_skill_bundle.py` 1848, `ccodex_sdlc.py` 1816,
  `ccodex_sdlc_install.py` 1999, `_update.py` 2581, `_uninstall.py` 1391, `_recover.py` 926,
  `distribution_activation_receipt.py` 1917, `write_acquisition_receipt.py` 333,
  `install_operator_tools.py` 1135, `ccodex_sdlc_readonly.py` 225, `opencodex-claude.sh` 2681,
  `bootstrap-agentic-sdlc.sh` 280, `bin/ccodex` 335, `assets/launchers/ccodex.in` 509,
  `manage_claude_{statusline,hooks,workflows}.py` 574/522/542, `build_release.py` 308 (kept).
- Test suite: 71 files, 55,763 lines; **70 of 71 files call `.main(` in-process** (`grep -rl`), which
  is the measured basis for ADR-0031 fact 5's orphaned-suite claim and for Phase 0.
- `mise.lock` digest-pins bun 1.4.0 per platform, including `macos-arm64`
  `sha256:c669e97f6164e1c96e0701748db98dfa77492908cbd8394c7557134a735de381` (`:31-33`), `linux-x64`
  `sha256:2d03fb5f…` (`:15-17`), `linux-arm64` `sha256:4b1a332e…` (`:7-9`) — the repo-owned build-time
  runtime pin §7.2 depends on.
- `mise.toml:18` pins `bun = "1.4.0"`; `mise.toml:69-71` pins `npm:@bitkyc08/opencodex` 2.28.0 whose
  postinstall lays down a second, 89 MB bun 1.3.14.
- `.github/workflows/` contains only `real-key-testing.yml` and `validate.yml` — **no release
  workflow**, confirming Install-UX step 7 is undone.
- `install_skill_bundle.discover_entries()` (`:596-618`) globs skills/agents/commands/workflows/hooks
  only; **`output-styles` appears in `policy/release-candidate.v1.json`'s `payload.trees` but in no
  installer code path** — so the output-style ships and is never installed by either channel. This
  corrects report 04's claim that the custom installer "installs output-styles into correct scope".
- `plugin/` is a tree of symlinks (`skills -> ../skills`, `agents -> ../agents/claude`, …), which
  matters because `bun build --asset` embeds regular files and **skips symlinks** (report 03 §b): the
  embed must target the real trees, and the plugin layout must be synthesised, not embedded.
