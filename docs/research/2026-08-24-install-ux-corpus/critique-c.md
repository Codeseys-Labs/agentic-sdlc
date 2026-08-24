# Adversarial critique — Design C (LEAN / native-channels-first)

**Target:** `/tmp/asdlc-research/.research-out/design-c-lean.md` (902 lines)
**Reviewer stance:** hostile but honest. Every `[measured]` claim below was executed by me on this
host against **Claude Code 2.1.241** (the same version design C measured), in an isolated
`CLAUDE_CONFIG_DIR` — the operator's real `~/.claude/settings.json` was verified untouched
afterwards. Where I could not establish something I say so.
**Read for context:** reports 01–05 and designs A and B, in full.

---

## 0. Summary judgement in one paragraph

Design C found the single most valuable fact in the entire research corpus, and I verified it:
report 04's "workflows and output-styles have no plugin schema, therefore the custom installer is
NECESSARY" is **wrong**, and design A is currently building on that error. But design C then
over-collects on the win. Its headline prerequisite claim is **false as printed** (its own commands
shell out to `git clone`), its Phase 0 gate **cannot pass as specified** (the inventory arithmetic
is wrong and two of the six component kinds it claims are not disclosed by the host at all), one of
its Phase 0 prescriptions **produces a hook load error**, and it chose the expensive integrity
mechanism (archive + zip + determinism gate + a host-floor bump) over a cheaper one that is
**measured working and fail-closed on this host** and that design C itself cites in passing and
never evaluates. It also creates the one collision class its thesis claims to delete, relabels
rather than reduces state ownership while outsourcing the repo's #1 invariant to a vendor schema
that versions itself, and sequences a 32,000-line demolition by deleting the tests first.

---

## 1. What I independently verified in design C's favour (concede these first)

These are not courtesies; they are the load-bearing facts and they hold.

| Claim | Status | My measurement |
|---|---|---|
| `workflows`, `outputStyles`, `hooks` are recognized `plugin.json` fields | **CONFIRMED** | Added `workflows`/`outputStyles`/`hooks` → `claude plugin validate --strict` exit 0, no warning. Added `totallyBogusFieldXYZ`/`banana` → `⚠ Unknown field 'totallyBogusFieldXYZ'. Claude Code ignores it at load time.` ×2, exit 1. The validator *does* flag unknown fields, so silence on those three is positive evidence. |
| `claude plugin validate ./plugin --strict` → exit 1 today, so `README.md:216-217` is false | **CONFIRMED** | Exit 1, three symlink warnings (skills, agents, commands). Non-strict → exit 0. `claude plugin validate . --strict` → exit 0. |
| Three native install scopes exist | **CONFIRMED** | `-s, --scope <scope>  Installation scope: user, project, or local (default: "user")` on `install` and `uninstall`; `update` additionally accepts `managed`. |
| Fail-closed digest verification is real and refuses by name | **CONFIRMED, twice** | `archive` + wrong `sha256` → `Plugin archive integrity check failed … expected sha256 000…, got edeb1d97…. The archive was not installed.` `github` + wrong 40-char `sha` → `SHA pin verification failed: expected HEAD to be 5bd912e8…, got e04d1bd2…. Refusing to install.` |
| The host record is richer than the receipt it replaces | **CONFIRMED** | `list --json` returns `id/version/scope/enabled/installPath/installedAt/lastUpdated`, and (unnamed by design C) an `errors[]` array. |
| Versions live side by side; rollback is selection | **CONFIRMED** | After uninstall 0.7.4 → install 0.7.5, `plugins/cache/<mkt>/<plugin>/` contains **both** `0.7.4/` and `0.7.5/`. |

**Design A is factually wrong where design C is right.** `design-a-evolutionary.md:434` proposes
deleting `plugin/workflows` and `plugin/output-styles` because "the Claude plugin schema has no
field for either (report 04 §a); the manifest currently over-claims", and `:697` repeats the 0%
figures. Both rest on report 04's error. Whatever plan ships must not carry that deletion.

---

## 2. Cross-platform / prerequisite claims that are false as written

### 2.1 `git` is required by every command block the design prints

Design C's §2a (`:105-107`) says: *"Preconditions: Claude Code installed and authenticated.
**Nothing else.** No mise, no git, no clone…"* §2e (`:196-200`) says the container needs
*"ca-certificates and Claude Code; `git` is not required"* and calls this *"the cleanest possible
compliance with ADR-0002 … it **removes** the one ADR-0002 was written to protect."* The §8 table
row (`:741`) scores *"Bootstrap prerequisites for the Claude plane: Claude Code only — **win**"*.

**[measured] False for the printed command.** With a PATH containing only `bash`, `sh`, `node` and
the real `claude` binary (no `git`):

```
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git
→ rc=1
✘ Failed to add marketplace: Failed to clone marketplace repository:
  Command failed with ERR_STREAM_PREMATURE_CLOSE: git -c core.sshCommand=… clone --depth 1
  --recurse-submodules --shallow-submodules -- https://github.com/…/agentic-sdlc.git …
```

`claude plugin marketplace add --help` corroborates: `--sparse <paths...>  Limit checkout to
specific directories **via git sparse-checkout**`.

The git-free route does exist — I measured it — but design C never prints it and it does not work
with the repo's current catalog:

```
claude plugin marketplace add https://raw.githubusercontent.com/…/v0.7.4/.claude-plugin/marketplace.json
→ rc=0   (no git on PATH; downloads and validates the JSON)
claude plugin install agentic-sdlc@agentic-sdlc
→ rc=1   ✘ Source path does not exist: …/plugins/marketplaces/agentic-sdlc/plugin
```

So the git-free path requires **both** the URL catalog form **and** the archive/github plugin
source. Design C hedges this in Q2 (`:845-847`) and a Phase 1 parenthetical (`:559-561`) — but the
thesis, the four UX blocks, and the tradeoff-table *verdict* all assert the unhedged version.
ADR-0002's 2026-08-07 amendment classes a **required system package** as a second bootstrap
prerequisite (report 02, `docs/adr/0002:88-91`), so this is not a cosmetic overstatement: it
inverts the design's single strongest ADR claim.

### 2.2 The archive source refuses non-https and loopback, so the "offline" checks are not offline

**[measured]** `archive` with `url: http://127.0.0.1:8731/plugin.zip`:

```
✘ … This plugin's marketplace entry is invalid: source.url: Archive URLs must use https://
  and must not point at a loopback, link-local, or cloud-metadata host
```

Consequences design C does not account for:

- Phase 1 CHECK 3 (`:564-566`) — *"flip one hex character of the `sha256` in a local copy of the
  catalog; install must refuse"* — cannot be run against a local fixture. It needs a real public
  https artifact and network egress. Design C's own rule, *"a fail-closed control that has not been
  observed failing closed is not a control"*, therefore applies to a check it cannot make into a
  gate.
- §2f (`:202-208`) is headed *"CI / **offline** verification of what landed"* but the mechanism it
  verifies can only be exercised online.
- Q10 (`:883-888`) already concedes that `--strict` validation needs `claude` in CI. Combined,
  the new CI prerequisites are **Claude Code + network egress** — an uncounted cost against a
  design whose headline is "one prerequisite, removed".

---

## 3. Phase 0 cannot pass its own gate, and one of its instructions is a defect

### 3.1 CHECK 3's expected inventory is measurably wrong, and 2 of 6 kinds are undisclosed

Phase 0 CHECK 3 (`:536-538`) requires `claude plugin details` to enumerate *"**13 skills, 5
commands, 8 agents, 1 hook, 1 output style, 1 workflow** — the exact inventory report 01 §A.3
measured."*

**[measured]** installing a dereferenced build of `plugin/` (plus `hooks/`) from a local
marketplace, `claude plugin details` prints:

```
Component inventory
  Skills (18)  adr-lifecycle, …, sdlc-frame, sdlc-init, sdlc-mission, sdlc-rightsize, sdlc-wave, …
  Agents (8)   sdlc-planner, …
  Hooks (1)    SessionStart  (harness-only — no model context cost)
  MCP servers (0)
  LSP servers (0)
```

Three things fall out:

1. **Commands are folded into Skills.** 18 = 13 skills + the 5 `commands/*.md`
   (`sdlc-frame`, `sdlc-init`, `sdlc-mission`, `sdlc-rightsize`, `sdlc-wave` all appear in the
   Skills list). There is no `Commands (5)` line. The check as written fails on arithmetic.
2. **There is no output-style line and no workflow line at all.** The bytes land — I confirmed
   `output-styles/` and `workflows/` in `plugins/cache/<mkt>/<plugin>/<version>/` — but the host's
   own inventory does not name them. So design C's central §1b claim, *"Net corrected coverage for
   the Claude plane: **6 of 6** component kinds"* (`:93`), is **4 of 6 confirmed and 2 of 6
   unconfirmed** on the version design C measured against.
3. **§7.2 item 5 breaks for those two kinds.** The supply-chain review checklist leans on
   *"`claude plugin details` — the host's own inventory of what will be contributed"* (`:699-701`).
   For the output style and the workflow the host contributes nothing to that inventory, so the
   operator has no pre-install disclosure of either. That is the same "installed inert / invisible"
   complaint design C levels at the status quo (D.7), relocated rather than deleted.

Q1 (`:837-843`) is design C's own name for this, marked UNVERIFIED and *"Phase 0's real risk."* I
could not close it either — `claude --help` exposes no way to list workflows or output styles
(only `--safe-mode` mentions them as things it disables) and `plugin details` does not report
them. So the design's largest claimed correction is, for two of six kinds, still an open bet, and
the host provides no instrument to settle it. Note in fairness: `README.md:860-862`'s recorded
observation of `agentic-sdlc:BLUF` is real evidence for output styles specifically; there is no
comparable evidence for the workflow, which is exactly the component report 04 called CRITICAL.

### 3.2 Phase 0's `hooks` manifest field produces a load error

Phase 0 (`:521-528`) instructs: *"add the `hooks`, `workflows`, `outputStyles` component fields to
`plugin.json`."*

**[measured]** With `"hooks": "./hooks/hooks.json"` present, `claude plugin validate --strict`
passes (exit 0) and `claude plugin install` exits 0 — and then `claude plugin list --json` carries:

```json
"errors": [
  "Hook load failed: Duplicate hooks file detected: ./hooks/hooks.json resolves to
   already-loaded file …/plugin/hooks/hooks.json. The standard hooks/hooks.json is loaded
   automatically, so manifest.hooks should only reference additional hook files."
]
```

Removing the field clears the error and the SessionStart hook still loads via autodiscovery. So the
prescription is wrong, and — worse — **Phase 1 CHECK 2 (`:562`) would go green over it**: it asserts
only `.enabled == true` and the expected `version`. A design whose whole argument is "the host's
record is a better receipt than ours" ships a check that ignores the field of that record which
reports failures.

### 3.3 A verified silent-partial-install class that no check in the design detects

**[measured]** the *same* repo at the *same* commit, installed two ways:

| Plugin source | Result |
|---|---|
| git-clone marketplace (`marketplace add <git url>#v0.7.4`, plugin `source: "./plugin"`) | rc=0, symlinks dereferenced into the cache, `Skills (17)  Agents (8)` |
| `source: {"source":"github","repo":"…","sha":"e04d1bd2…","path":"./plugin"}` | rc=0, **`Agents (0)`** — the tarball fetch does not follow `plugin/agents → ../agents/claude` |

Both exit 0. No warning either way. Design C's Phase 0 dereferenced build *fixes the cause* and
deserves credit for it — but the design contains no check that would catch this class, because
CHECK 2 looks at `.enabled` and CHECK 3's expected inventory is itself wrong (§3.1). Every check
that matters here must assert the component inventory, against a *measured* baseline.

---

## 4. The verified over-engineering finding: the entire zip/determinism plane is avoidable

Design C's §1b (`:68-69`) notes, correctly and in passing: *"Git-based plugin sources additionally
take `sha`, a full 40-char commit pin, and when both `ref` and `sha` are set, the `sha` is the
effective pin."* It then never evaluates that option and commits the whole design to
`archive` + `sha256`.

**[measured] the `github` source with a `sha` works on 2.1.241, honours `path`, and refuses
fail-closed by name:**

```
source: {"source":"github","repo":"Codeseys-Labs/agentic-sdlc","sha":"0000…0000"}
→ rc=1  SHA pin verification failed: expected HEAD to be 0000…, got e04d1bd2…. Refusing to install.

source: {"source":"github","repo":"…","sha":"e04d1bd2…","path":"./plugin"}
→ rc=0  installed
```

That is ADR-0020-grade digest pinning over content the repo *already* publishes, and it costs
nothing new. What choosing `archive` instead costs, measured:

- **A second release artifact in a different format.** `archive` requires a **zip**:
  ```
  url: …/releases/download/v0.7.4/agentic-sdlc-0.7.4.tar.gz  (correct sha256)
  → rc=1  ✘ … invalid zip data
  ```
  So `build_release.py`'s existing deterministic `git archive` tarball **cannot be reused**. A new
  zip builder is mandatory.
- **A blocking unknown that would not otherwise exist.** Q3 (`:848-851`) — is the zip
  byte-reproducible? — and Phase 0 CHECK 2 (`:533-535`) exist only because of this choice. Under a
  `github`+`sha` pin, the reproducibility question dissolves: the pin is over a git commit, and
  `git archive` determinism is already a control the repo holds.
- **A host-floor bump.** §8 (`:754`) records the minimum Claude Code version rising 2.1.154 →
  **2.1.224** as a *"loss"* requiring a new ADR-0027 tuple row. It is a loss incurred to buy the
  archive source specifically.
- **~40 lines that are not ~40 lines.** §5.5 budgets *"`build_release.py`: deterministic plugin zip
  + SHA256SUMS row ~40"*. A byte-reproducible zip needs explicit `ZipInfo` construction, fixed
  `date_time`, fixed `compress_type`, sorted entries, and correct `external_attr` — the last of
  which is load-bearing, because `hooks/hooks.json`'s command execs
  `"${CLAUDE_PLUGIN_ROOT}"/hooks/<name>.sh` **directly** and therefore needs the executable bit to
  survive the round trip. Whether it does is untested and appears in no check.

A lazy senior engineer reads §1b, notices the `sha` pin, deletes Phase 0's zip builder, Phase 1's
`SHA256SUMS` row, Phase 0 CHECK 2, Q3, and the 2.1.224 floor row, and keeps the fail-closed
refusal. Design C had the cheaper mechanism in hand and walked past it.

---

## 5. The design's headline UX already ships; the deliverable is only the deletion

**[measured]** against the current public tag, with no new code whatsoever:

```
claude plugin marketplace add https://github.com/Codeseys-Labs/agentic-sdlc.git#v0.7.4   → rc=0
claude plugin install agentic-sdlc@agentic-sdlc --scope user                              → rc=0
  Skills (17)  Agents (8)   installPath …/cache/agentic-sdlc/agentic-sdlc/0.7.4
```

The `#<ref>` syntax is accepted and recorded as `{"source":"git","url":…,"ref":"v0.7.4"}` in
settings. `README.md:846-870` already documents this as a supported plane.

This matters for cost/benefit framing. §2a presents "**Two commands**" as the design's headline
win against today's five. But two commands is *today's* state on an existing, documented,
working plane. The real proposal is: make that plane the *only* Claude plane and delete 32,005
lines. That is a legitimate and possibly correct proposal — but the UX section, the §8 verdict
column (11 rows scored **win**), and the friction-deletion list in §2a (`:120-129`) all bank
credit for an outcome the operator can have this afternoon by editing the README and deleting
`marketplace_overlap()`. The genuinely new value is (a) the fail-closed digest pin — obtainable
more cheaply (§4) — and (b) the deletion, whose risks are understated (§7, §8).

---

## 6. The thesis over-claims: the conflict machinery is retained, and a new collision is created

### 6.1 Codex keeps every mechanism the thesis says is deleted

§1 (`:16-26`) claims the ten-row conflict vocabulary, byte-identity ownership doctrine,
adopted/preserved/retargeted taxonomy, crash-consistent pending slot and six state stores exist
*only* because `bundle:install` writes into five `~/.claude` namespaces the operator also owns, and
that *"the collision surface is not managed by the lean design — it is **deleted**, and with it
every mechanism that existed to survive a collision."*

`$CODEX_HOME/skills/` and `$CODEX_HOME/agents/` are namespaces the operator also owns. Design C's
own §5.2 concedes the consequence: `install_skill_bundle.py` survives at **~900 lines** with
**~1,000 test lines**, and the v5 ledger (`:318-331`) still carries `mode`, `digest`, `removable`
and a `pending` slot. So the conflict vocabulary, the byte-identity doctrine, the transactional
publish primitives, the lock and the state schema are all **retained** — halved, not deleted. The
thesis sentence is false; the arithmetic table is honest. Those two should agree.

And the pivot on whether even that survives is filed as an unrun experiment: **Q4** (`:857-862`) —
does Codex CLI's native channel carry `agents/codex/*.toml`? — is described as *"the single largest
remaining deletion and it is one experiment away."* Presenting `−32,005` as settled arithmetic while
the largest remaining term is an unmeasured maybe is exactly the epistemic move design C criticises
report 04 for.

### 6.2 `~/.claude/settings.json` becomes a two-writer document — the one collision the thesis forbids

Design C keeps the statusline as *"the **only** surviving custom Claude-side activation"* (§8,
`:753`; §4.1, `:281`), which means writing `statusLine.type` and `statusLine.command` into
`~/.claude/settings.json`. **[measured]** the host writes `enabledPlugins` and
`extraKnownMarketplaces` into that same document, and does so again on marketplace refresh.

So after the deletion there is exactly one shared namespace left, it is a single JSON document, and
both parties read-modify-write it — one of them in the background. That is a lost-update class.
Repo invariant **#30** ("the bundle installer owns no global Claude settings; the global settings
document is read, never written, copied, or linked", `README.md:775-776`) was the control that made
this impossible, and §4.4 (`:373`) lists #30 under *"deleted because the thing they protect is
deleted."* The thing it protected is not deleted; it went from one writer to two. No mechanism,
check, or open question in the design addresses it.

Phase 4 (`:607-621`) then adds a **third** writer to a settings document (`<target>/.claude/settings.json`)
— see §8.2.

---

## 7. State ownership: a relabel, not a reduction, and invariant #1 is outsourced

§4.1's table (`:278-287`) declares *"**Six stores become two.**"* **[measured]**, the host owns at
minimum four artifacts:

```
settings.json                       → enabledPlugins, extraKnownMarketplaces
plugins/installed_plugins.json      → { "version": 2, "plugins": { "<id>": [ {scope, installPath, version, installedAt, lastUpdated} ] } }
plugins/known_marketplaces.json     → { "<mkt>": { source, installLocation, lastUpdated } }
plugins/cache/<mkt>/<plugin>/<ver>/ → the payload, side-by-side per version
```

Counting all of that as "one owner" is a presentational choice, not a deletion. Two harder
consequences the design does not name:

1. **Invariant #1 is outsourced to a schema that versions itself.** Repo invariant #1 — *"one
   ownership schema, no migration, no `--migrate-state`; a document with any other `version` is
   refused by name"* (`install_skill_bundle.py:266-289`) — is listed in §4.4 as surviving
   unchanged. But the authoritative record for the Claude plane is now
   `installed_plugins.json` with `"version": 2`, a vendor document that will migrate itself
   silently on a host upgrade and that the repo cannot refuse, cannot pin, and cannot gate. The
   design's own doctrine has been moved outside the design's reach.
2. **`ccodex doctor` becomes a parser of undocumented vendor output.** §4.2 (`:310-314`) prices the
   replacement for 11,188 lines of receipts at *"**~60 lines** in `ccodex doctor`"* (later ~120 in
   §5.5): read `installPath` from `claude plugin list --json`, re-hash against `manifest.json`.
   That JSON carries no schema version and no documented stability guarantee. ADR-0020's *"read back
   effective identity where exposed"* is then satisfied only against an unpinned surface — the same
   substitution class the `jq`-on-PATH defect (report 02, fresh-host verification `:164-175`)
   established as forbidden. §7.3 (`:729-732`) names vendor-schema dependence as *"the design's one
   genuine structural risk"* but scopes it to the **component** schema. The **state** and
   **CLI-JSON** schemas are the sharper exposure and go unnamed.

---

## 8. Redundant components a lazy senior engineer would delete

### 8.1 Phase 0's zip plane — see §4. Replace with a `github`+`sha` pin.

### 8.2 Phase 4 re-implements the host primitive Phase 1 just bought

Design C's answer to project scope is `claude plugin install --scope project` — measured real, and
the design is right that this subsumes `manage_claude_workflows.py`. Phase 4 (`:607-621`) then adds
an `instruction-generator.py` output kind that hand-writes `extraKnownMarketplaces` +
`enabledPlugins` into `<target>/.claude/settings.json`, with a diff-and-`--yes` ceremony.

This is new code that duplicates a host command, in a document the host also writes (§6.2), and it
puts the repo back in the business of editing a settings JSON that invariant #30 forbade it to
write. Its CHECK ("writes **exactly two keys**") is a test of the duplicate, not of the capability.
The whole phase collapses to one README line: *in the repo you want it in, run
`claude plugin marketplace add … --scope project && claude plugin install … --scope project`.*
Delete Phase 4.

### 8.3 The v5 ledger's `command-file` kind and the "operator" host

§4.3 (`:341-343`) folds `install_operator_tools.py`'s three-field record into the bundle ledger as
`kind: "command-file"`, `host: "operator"`. That is two unrelated lifecycles (a Codex roster copier
and a PATH-file installer with its own `HostPreconditionError` exit class, its own alias-retirement
vocabulary, and its own pre-lock precondition ordering) sharing one document, one lock and one
schema version — so a schema change to either now refuses both. The design gives one reason ("rather
than keeping a second document with a second version number and a second lock"). Two documents with
two versions was a *feature* here: the PATH plane and the host plane fail independently today. This
merge buys one fewer store on a slide and costs blast-radius coupling.

### 8.4 The stretch deletion is argued but its replacement is not designed

§5.3 (`:454-463`) proposes deleting `install_external_libraries.py` (1,658 + 1,495 test) because
*"an external Claude library **is** another marketplace."* Its own caveat concedes non-Claude hosts
and non-plugin libraries still need a route. Presenting `−3,153` in the arithmetic block (`:486`) for
a capability with no designed replacement is optimistic accounting; it should not appear in any
total.

---

## 9. Invariant and ADR regressions the design records too generously

### 9.1 The host-version control does not degrade one class — it disappears for the 95% case

§4.4 item 1 (`:380-390`) moves `check_compatibility` from **mechanical → observed**, delivered by
*"the shipped `hooks/hooks.json` SessionStart hook reads `claude --version` and emits a refusal
card, **every session**"*, plus `ccodex doctor`.

Both carriers fail in the case that matters:

- §4.4 item 2 (`:396-401`) praises that same hook because
  `hooks/session-start-routing-primer.sh:7-14` *"exits 0 with zero bytes of stdout unless
  `.seeds/issues.jsonl` is a regular non-symlink file **and** `AGENTS.md` carries the `/sdlc-init`
  activation marker."* Those predicates are false in every un-activated repository — i.e. in
  exactly the fresh-install situation where a below-floor host matters most. The design uses the
  gate as proof of authorization in one paragraph and as a delivery vehicle for a refusal in the
  paragraph above, and the two uses are incompatible.
- `ccodex doctor` requires the mise/gateway plane, which §2c makes **opt-in for gateway users
  only**. The Claude-first operator the design is built for never installs it.

So for the 95% case there is no host-version control at all, mechanical or observed. §8's row
scores this *"loss in force, gain in freshness."* It is a loss in force with no gain, and it lands
on a floor the design simultaneously raises to 2.1.224.

### 9.2 The exit ladder forks, and no repo test can constrain it

**[measured]** both fail-closed host refusals — archive digest mismatch and github `sha` mismatch —
exit **1**. Repo invariant **#49** (contract; conformance-tested at
`tests/test_lifecycle_exit_conformance.py:789-1172`) reserves **1** for *unexpected internal
failure* and **3** for *clean refusal before effect*. Under design C the operator's primary install
command is a host command that returns 1 for the canonical exit-3 case. §4.4 lists #49 among the
28 invariants that *"survive unchanged"* — true of the surviving repo modules, and beside the point,
because the surface it governs is no longer the surface the operator uses. Phase 3 CHECK 3
(`:598-600`) even keeps the conformance scan as a gate over a shrinking module list, which makes the
contract *more* internally enforced and *less* operator-visible at the same time.

### 9.3 ADR-0019 is weakened, then cited as satisfied

§2b (`:146-150`) argues the teammate-must-install rule *"**is** ADR-0019's per-effect fresh grant
implemented by the host."* §8/P2 (`:778-781`) argues *"**acquisition ≠ activation** remains two
commands (`marketplace add`, then `install`), honoring ADR-0021 item 3, ADR-0019's per-effect
grant."*

**[measured]** one `claude plugin install` writes the bytes **and** sets `enabledPlugins: true` —
the hook is live from that single grant. "Two commands" is catalog-add vs install, not place vs
enable. Invariant #28 (installing a hook never enables it) is genuinely traded; §4.4 concedes that
honestly. The design should not then re-cite the same host behaviour as ADR-0019 *compliance*.

Three host mechanisms in the same surface go entirely unexamined in §7's threat model:

- **`-y/--yes`** is documented as *"Accept the displayed marketplace-declared command without the
  confirmation prompt — a plugin installed by **running a command**, or one whose archive is fetched
  through a **`headersHelper` command**."* So a marketplace entry can carry a command the host
  executes. Design C's own container and CI checks require `-y` (non-TTY).
- **`dependencies`** in `plugin.json` plus **`claude plugin prune|autoremove`** ("Remove
  auto-installed dependencies that are no longer needed") mean plugins transitively auto-install
  other plugins.
- **`--scope managed`** on `update` implies an MDM-owned scope above the operator's.

§7.2's review checklist (`:679-698`) asserts only **file** absences (`package.json`, lockfiles,
`.mcp.json`, `.lsp.json`, `monitors/`, `bin/`, `settings.json`). The larger capability surface is
**manifest fields**, and the design asserts absence of none of them — despite §4.4 quoting the full
field list it read, which includes `dependencies`, `userConfig`, `channels` and `experimental`.

---

## 10. Migration risk a solo maintainer inherits

**Phase 3 deletes the tests first.** `:591`: *"Order: tests first (delete the 15 test files, watch
`mise run check` go green with fewer tests), then the modules they covered, then the narrowings…"*

That order removes 13,229 test lines and *then* performs the narrowings — `install_skill_bundle.py`
1,848 → ~900 with its suite 1,851 → ~1,000, the operator-tools/statusline merge 1,709 → ~600 with
its suites 2,178 → ~700, and `test_lifecycle_exit_conformance.py` 2,488 → ~1,200. The riskiest
edits (surgery on the module that still owns the Codex plane's transactional primitives, crash
consistency, and durability barriers) happen with the regression detector already deleted, and the
detector for the *surviving* code is itself cut by ~45% in the same phase. This is a single-release,
self-reviewed, ~32,000-line demolition on a solo-maintained repository, and design C's risk
inventory (§7.3, four items; §9, twelve questions; §8, six named losses) does not mention sequencing
at all. Invert it: narrow the survivors under full coverage, prove green, delete dead modules, then
delete their tests last.

**Phase 2's migration story is also thinner than it reads.** `:572-587` puts the migration in the
outgoing v0.8.x and makes v0.9.0 refuse a v4 document at exit 3 with a remedy naming *"install
v0.8.x, run `ccodex bundle uninstall --agent claude`, then reinstall."* Reinstalling an older
release to run a deprecation path is a real operator burden, and the design's own §2c makes the mise
plane optional — an operator who took the Claude-only path in v0.8.x has no `ccodex` to run the
remedy with.

---

## 11. Smaller but real

- **`workflows/sdlc-wave-scout.js` is 5,434 bytes**, not the "50+ KB" report 04 asserts and design C
  does not correct. Minor, but design C's whole §1b is a corrections pass and this one was in reach.
- **Phase 1's non-circularity argument** (`:549-552`) — "compute the digest at commit N, write it
  into the catalog, tag N+1; `plugin/` did not change between N and N+1" — is a *convention*, not a
  mechanism. Nothing in the design gates it, and the failure mode (a `plugin/` change slipping into
  N+1) yields a shipped catalog whose digest refuses every install. Under a `github`+`sha` pin the
  problem does not arise.
- **§7.3's catalog-not-pinned limitation gets worse under the git-free route**, which design C needs
  for its container claim: a URL catalog has no `ref` at all, only a URL. The "public tag diff"
  mitigation it leans on (`:711-716`) applies to the git form, not the form that satisfies §2e.
- **Q7 (`channels`) and Q8 (`userConfig`)** are framed as opportunities for further deletion. They
  are equally opportunities for further vendor coupling; the design does not price that direction.
- **§8's row for the receipt trail** says the current trail is *"exit-3 broken against the only
  downloadable artifact."* Report 05 says the fix is on `main@cd3fd3d`, unreleased. Using an
  unreleased-fix state as evidence for deleting the subsystem is rhetorically convenient; the
  honest version is "the subsystem's only reader is its own writer" (ADR-0022 precedent), which
  design C also makes and which is sufficient on its own.

---

## 12. The 2–3 ideas that MUST survive into any final plan (grafting candidates)

**G1 — The report-04 correction, plus the dereferenced plugin build.** Independently verified:
`workflows`, `outputStyles` and `hooks` are recognized manifest fields (the validator flags unknown
fields and stays silent on these three); `claude plugin validate ./plugin --strict` exits 1 today so
`README.md:216-217` is false; and non-clone fetch paths silently drop agents from a symlinked
`plugin/` (measured `Agents (0)` on a `github` source, exit 0, no warning). Building a dereferenced
plugin tree at release time is cheap, fixes a live silent-partial-install bug, and unblocks a CI
gate. This graft is mandatory in *any* plan and it **kills design A's proposal (`design-a:434`,
`:697`) to delete the `plugin/workflows` and `plugin/output-styles` symlinks.**

**G2 — Host-owned, fail-closed digest pinning as the acquisition control — in the `github`+`sha`
form, not the `archive`+`sha256` form.** The refusal is real and named
(`SHA pin verification failed … Refusing to install.`), needs no new artifact, no zip, no
determinism gate, and no 2.1.224 floor. This is what retires `write_acquisition_receipt.py` (333)
and most of `distribution_activation_receipt.py` (1,917) on the ADR-0022 "no independent reader"
precedent — the single best-supported deletion in any of the three designs.

**G3 — Native `--scope user|project|local` as *the* answer to project scope.** Measured on 2.1.241,
across `install`/`uninstall`/`update`. It is three scopes rather than two, needs no `.claude`
grandparent assertion, deletes the `--claude-home` trap report 01 §E.2 documented, and subsumes
`manage_claude_workflows.py` — and it is strictly better than design A's hand-built `--scope
project` and design B's `(host, scope, root)` ledger key. **Take it without Phase 4's redundant
settings writer.**

*(Runner-up worth keeping: replacing the receipt family with `claude plugin list --json` + one
re-hash of `installPath`. Keep it, but guard the parse behind a host-version probe and treat that
JSON as unversioned vendor output — including reading its `errors[]` array, which design C never
mentions and which is the field that would have caught its own Phase 0 defect.)*

---

## 13. Verdict

**ADOPT-WITH-CHANGES.**

Design C is the only one of the three built on a verified correction rather than an inherited
error, and that correction is worth more than either competing design's thesis: the native Claude
channel covers more of the payload than report 04 claimed, its digest verification is genuinely
fail-closed, and three install scopes already exist — which together justify deleting the
`ccodex_sdlc_*` family, both receipt-schema modules and `marketplace_overlap()` on the repo's own
"no independent reader" precedent. But the document as written cannot be executed. Its headline
prerequisite claim is false for the commands it prints (`marketplace add <git url>` shells out to
`git clone`; measured rc=1 without git), so its strongest ADR-0002 argument inverts. Its Phase 0
gate cannot pass as specified: the expected inventory is arithmetically wrong (commands fold into
skills: 18, not 13+5), two of the six component kinds it claims are not disclosed by the host at
all, and the `hooks` manifest field it prescribes produces a `Hook load failed` record that its own
Phase 1 check would not notice. It selected the expensive integrity mechanism — forcing a new zip
artifact, a determinism gate, a blocking unknown, and a host-floor bump — when a measured, cheaper,
equally fail-closed `github`+`sha` pin was already in its own evidence section. It then over-claims
in three places that matter: the conflict machinery is retained for Codex (~900 + ~1,000 lines, with
the pivotal Q4 unrun), "six stores become two" is a relabel that outsources the repo's #1 invariant
to a vendor document carrying its own `"version": 2`, and the design creates the one collision class
its thesis forbids by making `~/.claude/settings.json` a two-writer document. Finally, it sequences
a ~32,000-line demolition by deleting 13,229 test lines *before* narrowing the modules that still
own crash consistency — the single largest unnamed risk in the plan for a solo maintainer. Adopt
G1–G3; delete Phase 4 and Phase 0's zip plane; re-derive the deletion arithmetic only after Q1
(plugin-provided workflows) and Q4 (Codex native channel) are measured rather than asserted; add a
measured component-inventory assertion to every check; name the settings.json two-writer problem and
the host-version-control hole as open defects rather than scored wins; and invert Phase 3 so the
tests die last.
