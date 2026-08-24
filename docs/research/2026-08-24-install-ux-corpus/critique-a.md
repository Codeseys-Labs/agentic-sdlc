# Adversarial critique — Design A (Evolutionary Inversion, No Rewrite)

**Target.** `/tmp/asdlc-research/.research-out/design-a-evolutionary.md`
**Reviewer method.** All three designs and all five reports read in full, then every load-bearing
claim in Design A that could be checked was checked against the checkout at
`/tmp/asdlc-research` (v0.7.4, HEAD `e0fbf92`). No `mise` task was run; the config was left
untrusted. Findings below are marked **[verified]** when I read the code or ran a command,
**[reasoned]** when they follow from verified facts, and **[open]** when the design and the
reports disagree and I could not settle it.

**Verdict up front: ADOPT-WITH-CHANGES**, where the changes are large enough to state as a rule:
**adopt Design A's subtractions, reject almost all of its additions.** Justification in §8.

---

## 1. Confirmed factual errors in load-bearing claims

### 1.1 The flagship supply-chain claim is falsified by the repo's own module docstring [verified]

§7a asserts, in bold: "**the release artifact is reproducible, so a digest means what it says**",
and Phase 1's check is:

> A third party runs `git archive` at the tag with the same `policy/release-candidate.v1.json`
> allowlist and gets a sha256 **identical** to the published `SHA256SUMS` line. `mise.lock`'s
> self-pin checksum equals it. […] This check is the whole supply-chain story in one command and
> it is exactly the property ADR-0031 fact 4 says a compiled artifact cannot offer.

`scripts/build_release.py:31-36` says the opposite, in the module's own contract section:

> WHAT THE DIGEST DOES AND DOES NOT PROVE. The tar member bytes are stable across hosts. The
> gzip envelope's bytes depend on the host's zlib build, so ``SHA256SUMS`` names the exact archive
> **this host** produced, and **a rebuild elsewhere may compress the same tar to different bytes**.
> The manifest's per-entry digests are the cross-host identity.

Confirmed mechanically: the archive is gzipped at `build_release.py:273`
(`gzip.GzipFile(..., compresslevel=9, mtime=0)`), and the sha256 in `SHA256SUMS` — the same digest
mise pins — is over the gzip bytes. Three separate defects follow:

1. **The check is wrong on its face.** A plain `git archive` produces **no `manifest.json`**;
   `build_release.py:262-266` appends it as "the single member this process writes". So the tar a
   third party gets differs from the published tar before compression even enters the picture. The
   check as written can never pass.
2. **Even the corrected check (run `build_release.py` at the tag) is not guaranteed to pass**, by
   the module's own statement, because zlib differs across hosts and distros. A fail-closed
   integrity control whose documented failure meaning is "the published bytes are not the tagged
   source" (§7e row 2) will fire on honest third parties. That is worse than having no check.
3. **The rhetorical asymmetry against Design B collapses to a much smaller one.** Design A's
   strongest argument against a compiled artifact is ADR-0031 fact 4 ("rebuild-and-compare
   verification is impossible by construction"). But Design A's own carrier digest is also
   digest-over-shipped-bytes; what it genuinely has is a re-derivable **per-file manifest**. Design
   B conceded exactly this split honestly ("git archive + manifest.json as the payload's
   independently re-derivable anchor while conceding digest-over-shipped-bytes for the carrier
   only"). Design A claims the stronger property it does not have, and encodes the wrong assertion
   as a phase gate.

**Required change.** Phase 1's check must be: *a third party re-derives every per-file sha256 in
`manifest.json` from `git archive` at the tag and gets a byte-identical inventory*; the carrier
digest is pinned, not reproduced. Say so, and stop claiming artifact-level reproducibility.

### 1.2 "Every `scripts/*.py` entrypoint declares `dependencies = []`" is false [verified]

Phase 2 justifies deleting `run_python` with: "Safe by inspection: every `scripts/*.py` entrypoint
declares `dependencies = []` under `requires-python = \">=3.12\"`, so `uv run --script` was buying
nothing except a subprocess layer and a divergence."

I enumerated every PEP-723 header in `scripts/` and `skills/agentic-sdlc/tools/`. Exactly one is
non-empty: `scripts/validate_bundle.py:4` → `# dependencies = ["pyyaml==6.0.3"]`. That script is
the `validate` gate (`mise.toml:75-76`) and a leaf of `check`. It is reached only through the mise
task, so deleting `run_python` from `bin/ccodex` does not break it — but the stated premise is
false, and two consequences the design claims do not follow:

- **The divergence class is not erased, only hidden.** `uv run --python 3.12.11 --script` survives
  in `mise.toml` for every contributor task (44 today, 11 after §5b — and the 11 kept are exactly
  the ones that use it). "One Python route" is true of `bin/ccodex` only. Phase 2's check
  (`grep -c 'uv run --script' bin/ccodex` = 0) proves a file-local property and is presented as an
  architectural one.
- **uv can never be removed** as a runtime dependency, because pyyaml has to come from somewhere.
  Combined with §1.3 below, uv is load-bearing on the *use* plane too.

### 1.3 Deleting `plugin/output-styles` deletes a capability the repo's own README records as working [verified]

Phase 0 deletes `plugin/workflows` and `plugin/output-styles` "because the Claude plugin schema has
no field for either (report 04 §a); the manifest currently over-claims", and §7d builds an entire
new authorization *rule* on that premise.

`README.md:860-862` records an **observed** fact to the contrary:

> The bundled output style appears as `agentic-sdlc:BLUF`, taking its name from the file's
> frontmatter rather than its filename.

and `README.md:864-865` names `output-styles` as one of the directories `--sparse` must keep
"to limit the catalog clone to the directories the plugin needs". Design C reports it live-verified
both `workflows` and `output-styles` as supported plugin component dirs. Further, "the manifest
over-claims" is doubly wrong: `.claude-plugin/plugin.json` declares **no component fields at all**
(name/description/version/author/license/homepage/repository/keywords only) — the directory tree
*is* the claim.

Two things make this worse than a one-line error:

- **Phase 0's check cannot detect the regression.** Its checks are `git diff --stat` shows deletions
  only, and `mise run bundle:status` byte-identical before and after. `bundle:status` does not read
  the plugin plane at all (report 01 §D.4: `grep -c 'statusline|manage_claude' ccodex_sdlc.py` = 0
  is the same class of blindness). A phase whose whole claim is "prove the deletions are inert"
  ships with a check that is blind to the only plane it touches.
- **It contaminates §4.2 and §7d.** §4.2 adds an `output-style` kind to the ownership ledger on the
  grounds that "`output-styles/bluf.md` ships in the archive and in `plugin/` today and is installed
  by nothing" — while §7d simultaneously deletes the one channel that *does* install it. And §4.2's
  own parenthetical admits the activation mechanism is **UNVERIFIED**. So the design deletes a
  working delivery path for a 1.4 KB file and replaces it with a new lifecycle kind whose activation
  it cannot describe.

### 1.4 The end-state UX omits a mandatory `mise trust` on every upgrade [verified]

`README.md:457-458`: "Mise trust is scoped to each absolute config path." `mise use -g
github:…@1.1.0` installs into a **new versioned directory**, so the new tree's `mise.toml` is at a
new absolute path and is untrusted. `bin/ccodex:121-131`'s `require_toolchain` probes
`mise -C "$root" tasks`, matches `*"not trusted"*`, and **exits 3**.

Design A's §2 upgrade block is:

```bash
mise use -g github:Codeseys-Labs/agentic-sdlc@1.1.0
ccodex bundle update --scope user --agent claude         # receipted, blocks on any drift
```

The second line exits 3 until the operator reviews and trusts the new tree's `mise.toml`. So the
design's two headline properties — "the sequence is **identical on both hosts**, and the count is
**four commands plus one review**" — are false for the upgrade path, which is the path an operator
takes N times for every one time they install. Every version bump costs a full re-review-and-trust
cycle, and the design's §8 row "Self-update: still none | two commands instead of one" is really
four commands plus a diff review.

### 1.5 The command count repeats the exact sin §2 claims to delete [verified against §2 itself]

§2 claims "four commands plus one review" and says that fixing the count "deletes report 01 §D.1
(the README headline installing both planes while Quickstart insists you choose) rather than
documenting around it."

Count §2a after the prerequisite: `ccodex version`, `less …/mise.toml`, `mise trust`, `ccodex
doctor`, `ccodex bundle install`, `ccodex bundle status` = **six commands** across five numbered
steps, of which one (`less`) is the review. Then §2 immediately adds four more, "each a **separate**
effect with its own grant": `statusline activate`, `hooks activate`, project-scope install,
`ccodex ensure`. A realistic first run is ~10 commands. Report 01 §D.1's criticism was precisely
"the headline says 5, the Quickstart says five and lists six." Design A's headline says four and its
own transcript lists six.

---

## 2. Under-specified to the point of being a different project

### 2.1 Phase 3's auto-sealed acquisition receipt cannot be built as described [verified]

Phase 3's marquee deliverable: "`install` auto-seals the acquisition receipt from the root's own
`manifest.json` by calling the existing `write_acquisition_receipt.py` machinery — deleting the
manual 'placement bridge' recipe". §1 calls this "closing report 05's missing
GitHub-download→acquisition-receipt bridge by calling the 333-line producer that already exists and
is called by nobody."

Three verified obstacles, none named in the design:

1. **The receipt is keyed by the archive sha256, which does not exist on a mise-installed tree.**
   `write_acquisition_receipt.py:203` refuses unless exactly one of `--archive` / `--archive-sha256`
   is supplied; `:96` fixes the layout as
   `$XDG_STATE_HOME/…/acquisition/receipts/<archive-sha256>.json`. mise extracts the tarball; the
   `.tar.gz` is not a contract-guaranteed artifact on disk afterwards. So the design's §7a chain
   arrow "acquisition receipt (v2) ← re-hashes the placed root against its own manifest" silently
   assumes an identity value it cannot obtain.
2. **Root admission is hardcoded to the acquisition-candidates layout.**
   `ccodex_sdlc_install.py:738`: `expected = config.acquisition_candidates_dir / archive_sha256 /
   ACQUISITION_CANDIDATE_LEAF`. The module admits *only* that path
   (`ACQUISITION_CANDIDATE_SEGMENTS` at `:204`). Accepting a mise-resolved root therefore means
   either (a) keeping the placement bridge and internalizing it — a second full copy of the payload
   on disk, i.e. the bridge is renamed, not deleted; or (b) re-keying the acquisition receipt on
   `manifest.json`'s `candidate_id`, which changes the receipt's primary key, its path layout,
   `update`'s "identity differs from the active one" comparison (`ccodex_sdlc_update.py`), and every
   test that touches it. Option (b) is not "calling the existing producer"; it is redesigning the
   acquisition identity model. §6 budgets no such work and §5 lists no changes to
   `write_acquisition_receipt.py`.
3. **Auto-sealing hollows out the receipt's meaning.** Today the acquisition receipt is produced by
   a separate, earlier, human/CI act, and `install` admits it as *independent* evidence
   (`admit_acquisition_receipt`, `:631-665`, refusing absence and ambiguity by name). If `install`
   seals its own admission ticket from the same root it is about to activate, the receipt is a
   self-signed certificate: the effect mints the authorization it then consumes. ADR-0019 is explicit
   that "no agent, gate, queue record, ADR, **receipt** or model output may create or broaden
   authority." §9 open question 6 half-notices this ("one behavior vs one stronger meaning") and
   chooses the weaker one. The design claims "every ADR honored"; this is the clearest place it is
   not.

### 2.2 Phase 5's blast radius is far larger than the deletion table admits [verified]

`scripts/install_operator_tools.py` is not only a PATH installer. It is a **live library** to modules
Design A keeps:

- `scripts/ccodex_sdlc.py:1453` — the reader loads it as a sibling and passes it to
  `guard.block_lifecycle_mutators(operator_tools, bundle)` and `recovery_configs(root,
  operator_tools, bundle)`.
- `scripts/ccodex_sdlc_recover.py:823` — `operator_tools = load_sibling("install_operator_tools")`,
  then `build_configs(operator_tools, bundle, …)` and `derive_plan(operator_tools=…,
  operator_config=…, …)`. Its docstring (`:17-21`) makes this structural: "Resume and roll back
  happen ONLY through the reused substrate's own machinery — each substrate's own `recover_pending`
  over its own single `pending` slot (`install_skill_bundle` for the bundle journal,
  **`install_operator_tools` for the operator-tools journal**)."
- `scripts/manage_claude_statusline.py:31` — `import install_operator_tools as operator_tools`
  (this one the design's merge does cover).

Plus at least seven test files beyond the one the design budgets: `tests/test_ccodex_sdlc.py:16,52`,
`tests/test_ccodex_sdlc_install.py:1426`, `tests/test_ccodex_sdlc_recover_apply.py:43,47,519,587,1007,1045`,
`tests/test_ccodex_sdlc_lifecycle_grammar.py:31,132`, `tests/test_lifecycle_exit_conformance.py:101,1454`,
`tests/test_bin_ccodex.py:50`, `tests/test_verification_runbook_contract.py:13,126`,
`tests/test_manage_claude_statusline.py:22,28`.

Two consequences the design never states:

- **`recover` must be partly rewritten**, not merely have a task deleted. Its plan spans two
  journals; removing one changes `derive_plan`'s output bytes — and "**the approval IS the digest**"
  (invariant 41, `ccodex_sdlc.py:52-58`). So Phase 5 silently invalidates every previously rendered
  `recover --dry-run` digest, and changes the meaning of a control the repo treats as authorization.
  Report 05 §d.4 flags exactly this constraint; Design A read report 05 and does not mention it.
- **The line accounting is wrong in the optimistic direction.** §5 books 1,135 + 1,660 as the cost
  and asserts `HostPreconditionError`/`validate_bin_dir` are "(in the 1,135)". The real Phase 5 diff
  also touches `ccodex_sdlc.py`, `ccodex_sdlc_recover.py`, and 7+ test files, and the design offers
  no estimate for that. For a solo maintainer this is the difference between a weekend and a month.

### 2.3 The per-scope activation pointer has no agent axis, but the CLI does [verified]

§4.3 replaces `ACTIVE_RECEIPT_NAME = "active-receipt.json"`
(`ccodex_sdlc_install.py:211`, single file at `:397`) with
`activation/active/<scope-id>.json`, `scope-id ∈ {user, project-<sha256(root)[:16]>}`.

But §2 makes `--agent` **required with no wildcard**, so `--agent claude` and `--agent codex` are two
separate invocations in the same scope. `activation_scope` gains `"claude-project"` beside
`"claude-home"` (§4.3), i.e. the *scope value* encodes the host — yet the **pointer filename does
not**. Failure scenario: `ccodex bundle install --scope user --agent claude` seals receipt A and
writes `active/user.json` → A. Then `--agent codex` seals receipt B and overwrites
`active/user.json` → B. Now `ccodex bundle update --scope user --agent claude` admits the active
receipt (B, a codex activation), and `uninstall --scope user --agent claude` derives its removal
candidate set from "the active receipt's own entry inventory" (report 05 §a) — which is codex's.
The design's own §4.3 rationale ("a machine with four project installs has four live activations and
one file cannot name them") applies verbatim to hosts and is not applied. Pointer keys must be
`(scope, agent)`.

### 2.4 The convergence rule is stated against the wrong comparison [reasoned from verified code]

§4.6: "`install` where every planned entry classifies `owned` **and** digest-equal: no bytes move,
no receipt is sealed, the pointer is untouched, exit 0 with `up to date: <candidate-id>`."

`entry_matches_record` (`install_skill_bundle.py:914-936`) compares
`digest(destination) == record["digest"]`, and `record["digest"]` is `digest(entry.source)` **at
install time** (`entry_record`, `:873-889`). So "classifies `owned` and digest-equal" is a statement
about the *old* record, not the new payload. Read literally against the primitive the design cites
(`:430-437`), `ccodex bundle update` after `mise use -g …@1.1.0` becomes a no-op that prints
"up to date" while the 1.1.0 payload is never activated. A careful implementer would compare against
the planned source digest — but Phase 3's check only exercises "the second **identical** install
writes no bytes", so the check cannot distinguish the correct implementation from the broken one.
Restate the rule as *destination digest equals the planned source digest* and add a
changed-payload leg to the check.

### 2.5 The statusline ledger kind loses the executable bit [verified]

§4.2 claims two kind-table rows and "**nothing else**". `assets/claude/statusline-command.sh` is
mode **100644** in git (`git ls-files -s assets/claude/`). `install_operator_tools.py` writes its
rendered copies at `0o755` explicitly (`:629`, `:637`). The ledger's copy path is
`copy_item` → `shutil.copy2(source, destination, follow_symlinks=False)`
(`install_skill_bundle.py:817-821`), which **preserves the source's 0644**. So the
`~/.claude/statusline/agentic-sdlc-statusline` the design activates as `statusLine.command` is not
executable. Phase 5's check ("`ccodex statusline activate` sets `statusLine.command` to the
`~/.claude`-owned copy") reads settings.json rather than executing the statusline, so it passes
while the feature is broken.

---

## 3. Invariant and ADR violations the design claims not to have

### 3.1 "Readers write nothing / dry-run writes nothing" is broken by the toolchain route [verified]

§3 Layer 3 labels `doctor`, `bundle status` and `version` as "readers (no lock, no write)", and
§4.6 keeps invariants 35–38 ("`--dry-run` writes nothing and takes no lock").

Every Python verb in `bin/ccodex` goes through `run_python` (`:141-150`) or `run_sdlc_python`
(`:169-187`), and **both call `require_toolchain` first** (`:148`, `:174`). `require_toolchain`'s own
refusal text states the consequence: "After that explicit step, the **first tool-needing verb
auto-installs the pinned toolset from the tree's lock**" (`bin/ccodex:131`). `mise.toml:3-4` sets
`locked = true`; the tree pins 12 tools at ~1.3 GB including `npm:@bitkyc08/opencodex` 2.28.0, which
transitively pulls bun. And `run_sdlc_python:176-183` will run **`uv python install 3.12.11`** — a
network download of a CPython build — if the managed interpreter is absent.

So on a fresh host: `ccodex doctor`, or `ccodex bundle install --dry-run`, can trigger a ~1.3 GB
toolchain install plus a CPython download **before** the Python process that honors `--dry-run`
exists. Design A makes this strictly worse than today by routing *all* Python verbs through the
interpreter-provisioning path (Phase 2), where today only the `sdlc` family does. This is:

- a direct contradiction of §3's "readers (no lock, no write)" and of invariant 35's promise;
- **ADR-0020 item 4**: "ordinary commands never silently resolve, install, update, replace, or fall
  back — refresh is a separate reviewed lifecycle operation";
- **ADR-0019**: acquisition is a separate effect needing its own grant, and 1.3 GB of tools arriving
  inside `bundle install` is an unbounded effect the install's authorization never named.

The design's answer would presumably be "`mise trust` was the grant." That is arguable for the tools
in `mise.lock`. It is not arguable for `uv python install 3.12.11`, because **there is no Python in
`[tools]` and no python entry in `mise.lock`** (verified: `grep -n python mise.lock` → 0 hits; the
lock's 12 tool blocks are bun, fd, gh, jq, lefthook, node, npm, ripgrep, uv, betterleaks, and two
npm-backend tools with zero platform rows). Report 01 §D.3 already found this gap from the other
direction.

**This is the design's largest unacknowledged supply-chain hole.** §7a's "chain the operator can
verify, end to end" and §7b's "three places trust is concentrated" both omit the interpreter that
executes 100% of the installer's logic. It is fetched by uv from Astral's python-build-standalone
releases, verified by nothing the design names, and Design A extends its reach from four modules to
every Python verb.

### 3.2 Layer 1's front door depends on an undocumented mise heuristic that has already misfired [verified]

Layer 1 asserts "`bin/ccodex` exposed on PATH by mise's own bin detection". ADR-0011's 2026-08-24
amendment (quoted in report 02) records that "mise exposed the whole `scripts/` directory as the
tool's bin path until `bin/ccodex` was committed." There are 8 executable files in `scripts/`
(`git ls-files -s scripts/ | grep 100755`), so the earlier behavior put 8 commands on the operator's
PATH — a direct violation of invariant 50 ("one file, not N commands… no PATH namespace land-grab").

After Design A, that invariant is enforced by **mise's asset-layout heuristic**, not by the product,
and the design adds no phase check pinning it (Phase 5's check asserts `command -v ccodex` resolves
to the mise shim, not that *nothing else* does). §2d honestly flags `mise where` as UNVERIFIED but
not this. Add a check: after `mise use -g`, the tool contributes exactly one command.

### 3.3 The trust grant is ~30× larger than the use plane needs, and the design never trims it [verified]

§7b correctly names `mise trust <root>/mise.toml` as "the single largest grant an operator makes:
twelve pinned tools, ~1.3 GB, including `npm:@bitkyc08/opencodex` 2.28.0 whose integrity surface is
version+backend only — no tarball hash, no transitive integrity."

What the *use* plane actually needs from that config: uv (for the interpreter), jq, node (because
the pinned `ocx` is `#!/usr/bin/env node`), and opencodex only if the operator wants the optional
gateway. It does not need lefthook, betterleaks, gh, ripgrep, fd, bun, npm, or seeds-cli.

Worse, `policy/release-candidate.v1.json`'s `payload.trees` (verified) excludes `tests/`, while the
archived `mise.toml` defines 44 tasks (`grep -c '^\[tasks' mise.toml` = 44) — and §5b's 11 survivors
(`check`, `validate`, `test`, `self-test`, `secrets`, `release:build`, `hooks:install`,
`contributor:setup`, `mermaid:*`, `test:all-hosts`) are precisely the ones that require `tests/` and
therefore **cannot run from a release tree at all**. So the artifact the operator is told to `less`
and then `mise trust` is a config whose entire visible task surface is inoperable, and whose tool
table is mostly contributor tooling.

A cheap fix the design never considers: build the release with a **release-only `mise.toml`**
carrying the 3–4 runtime pins and zero tasks. The design already edits the release allowlist in
Phase 6, so the marginal cost is near zero, and the payoff is the operator's largest grant shrinking
by an order of magnitude. Its absence is the single clearest sign that "subtraction" was applied to
line counts and not to operator-facing cost.

### 3.4 Project scope on a user-global ledger has a committed-payload trap [reasoned from verified code]

§4.2 keeps the ledger "always user-global, in every scope", and §9 open question 2 proposes that
project-scope copies be committed to the target repository ("a repo that carries its own harness").
Combine that with the design's own all-or-nothing exit 3 (§4.7) and the adoption rules
(report 01 §B.4, `install_skill_bundle.py:1386-1416`):

- Operator A installs `--scope project` at v1.0.0 and commits `<repo>/.claude/**`.
- Operator B clones the repo on a fresh machine. The ledger has **no records** for those paths.
- `ccodex bundle install --scope project --agent claude` at **v1.0.0** → "no record + byte-identical
  copy" → `adopted (preserved on uninstall)`, `removable: False`. Operator B's tooling can never
  uninstall its own payload.
- At **v1.1.0** (any byte differs) → "no record + anything else present" → `conflict:`, and under
  Design A's new rule the **whole run refuses at exit 3 with nothing written**. Operator B's only
  remedy is to hand-delete files their own repository committed.

So the design's headline new capability, combined with its own recommended usage and its own
strictness change, produces a repository that cannot be installed into. Either project scope is
gitignored (and then "a repo that carries its own harness" is abandoned), or adoption needs a
project-scope-specific rule the design does not have. §9 leaves this to "the operator's call"; it is
a design decision, not a preference.

Two further costs of the global ledger, both unpriced: one `installer.lock` serializes every project
on the machine, and a moved/deleted repo leaves ledger records with no reader and no GC — the exact
pathology (70 orphan records, no reader) that ADR-0022's 2026-08-22 amendment cited as grounds for
**deletion**, and which Design A cites approvingly as precedent while re-creating it at N-repo scale.
§9 open question 10 admits the ceiling is "unmeasured at N=100."

### 3.5 Project-root resolution is self-contradictory and excludes non-git projects [verified text]

Phase 4: "Project root resolution: walk up from cwd for a `.git` entry" **and** refuse "a
subdirectory rather than the repo root". Walking up always yields the root, so the subdirectory
refusal can never fire on the walk path; it can only apply to an explicit `--project PATH`, which
the text does not say. Separately: no `.git` ⇒ no project scope at all, so a monorepo subtree, a
worktree with a `.git` *file*, a `GIT_DIR`-relocated checkout, and any non-git project are silently
outside the feature. Avoiding a `git` dependency is right (ADR-0002); pretending `.git`-presence is
the same predicate as "is a project" is not.

---

## 4. The over-engineering pass: what a lazy senior engineer would delete

This is where Design A is weakest, because it is the axis it claims as its thesis.

**Measured baseline.** 151,263 tracked lines (`git ls-files | xargs wc -l`, matches the design's
figure), 57,099 of them tests. The repo's own 2026-08-22 audit measured 210,528 lines and ranked
~75,500 for deletion; ~59k of that has already happened. Design A's answer to the remaining ~151k is
**≈ −5,000, i.e. 3.3%**, with the machinery-to-payload ratio essentially unchanged.

What it keeps, verified by line count:

| Kept module | Lines |
|---|---:|
| `scripts/ccodex_sdlc_update.py` | 2,581 |
| `scripts/ccodex_sdlc_install.py` | 1,999 |
| `scripts/ccodex_sdlc.py` | 1,816 |
| `scripts/install_skill_bundle.py` | 1,848 |
| `scripts/ccodex_sdlc_uninstall.py` | 1,391 |
| `scripts/ccodex_sdlc_recover.py` | 926 |
| **subtotal (+2 receipt-schema modules)** | **~10,600** |

That is ~10,600 lines of lifecycle machinery to place **28 files** for `--agent claude` (report 01
§A.3: 13 skills + 8 agents + 5 commands + 1 workflow + 1 hook). Design A does not merely keep it —
it **extends** it: receipt schema v1→v2, a new `activation_scope` value, per-scope pointers with
five named call sites, two new ledger kinds, a merged settings receipt store, a new `doctor`
projection, and a transition-only refusal with its own scheduled deletion phase.

Specific things a lazy senior engineer strikes on sight:

1. **`ccodex_sdlc_recover.py` (926 lines) becomes redundant against §4.6.** The design makes install
   genuinely convergent ("no-op when the live state already equals the requested state"). Once
   install is idempotent, the answer to "a run was interrupted" is *run it again*. Keeping a
   digest-approved plan compiler for one `pending` slot, in a design that just made re-running free,
   is two mechanisms for one job — and §2.2 above shows Phase 5 has to modify it anyway.
2. **The whole acquisition-receipt plane** fails Design A's own cited test. It quotes ADR-0022's
   amendment approvingly ("70 records in 151 orphan directories, no reader") as licence to delete
   `selection` — then keeps a receipt family whose only reader is *its own* `doctor`, and whose
   independence it destroys in §2.1 by auto-sealing. If the only consumer of the receipt is the tool
   that wrote it, the ADR-0022 precedent says delete it, not version it.
3. **The `output-style` ledger kind**: a new lifecycle kind, a new destination collection, and an
   UNVERIFIED activation mechanism, for **one 1.4 KB file** already delivered by a channel the
   README documents as working (§1.3).
4. **The `statusline` ledger kind + merged settings module (~600 lines)** to own **two keys** in
   `settings.json`. Design A's own §4.4 concedes the two modules "do one thing"; the lazy answer is
   to print the two-line JSON patch and let the operator paste it, which needs zero receipts and
   zero state store.
5. **`--agent codex` (21 of 49 entries)** is questioned in §9 open question 3 and then kept
   ("measure first"). It has no compatibility row (`compatibility.core.host = "claude-code"`,
   `support_rows = []`), no parity promise under ADR-0017, and it doubles the pointer/receipt
   cardinality problem in §2.3. Deleting it is the single largest cheap win available and the design
   defers it.
6. **`ccodex doctor` absorbing collision classification** duplicates `install --dry-run`, which the
   design keeps (§7e row 5). Two commands, one answer.

**Maintenance burden actually inherited.** Nine landable phases, each ending in a disposable-container
proof run as non-root against the public remote; a receipt schema migration; two new ADR-0027 tuple
rows with committed transcripts (darwin-arm64 *and* project scope, since "no tier is inherited");
one ADR supersession requiring a new record plus the full ADR-0011 evidence set; two amendments to a
still-proposed ADR-0021; a README rewrite; and a compat state created in Phase 5 purely so Phase 8
can delete it. For one maintainer, that is months. For 3.3% of the lines and no reduction in the
46:1 machinery-to-payload ratio that the repo's own audit called "decisively overengineered."

---

## 5. Migration and cross-platform risk

- **Phase ordering breaks the accepted decision mid-flight.** Phase 5 deletes the PATH plane and
  Phase 7 deletes `bootstrap-agentic-sdlc.sh` and supersedes ADR-0011 — but ADR-0011 is the
  **current accepted install decision** until Phase 7 lands, and Phase 1's release CI is the
  evidence its reversal condition requires (`ADR-0011:160-165`). Between Phase 5 and Phase 7 the
  tree has deleted mechanisms the binding record still names. Reorder: supersede first, delete second.
- **macOS is a Phase 6 promise sitting behind five phases.** §2a's headline transcript is a fresh
  Apple Silicon host, and §2d honestly admits "the macOS transcript is the **post-Phase-6** state"
  — today four modules hardcode Linux (verified: `ccodex_sdlc_install.py:219-220`,
  `_update.py:205-206`, `_uninstall.py:129`, `_recover.py:69-70`). Note also `PLATFORM =
  "linux-x64"` at `scripts/build_release.py:58`, a fifth site the design's Phase 6 does not name
  (it names only the policy JSON). Credit where due: I checked `mise.lock` and **every
  platform-pinned tool has a `macos-arm64` row** (bun, fd, gh, jq, lefthook, node, ripgrep, uv,
  betterleaks), so `locked = true` will not fail closed on Darwin. That specific risk is clear.
- **Windows: the claim of "unchanged" holds.** I checked — `assets/launchers/ccodex.in` contains
  zero Windows references, and `scripts/run-git-bash.ps1` / `scripts/run-windows-mise.ps1` survive
  the deletions. Deleting `install_operator_tools.py` does remove invariant 18 (native Windows
  refused first, before `Path.home()` is evaluated) with no stated replacement, but nothing on
  Windows worked through that path anyway.
- **Deliberate breakage is broad and unbudgeted.** `--scope`/`--agent` required with no default
  breaks `mise run bundle:install` (`mise.toml:78-81` passes no `--agent`), the self-test leaf, and
  `AGENTS.md:193-209`'s current instructions. 33 deleted tasks break every doc, habit, and CI
  invocation naming them. Receipt v1→v2 invalidates the published prerelease receipts. The design
  names these; it prices none of them.
- **[open] Report 05's FINDING-1.** §9 item 11 correctly identifies that report 05 §a and §b
  contradict each other on whether uninstall retires the ledger rows, and defers to execution in
  Phase 3. That is the right call, but it means Phase 3's headline check ("uninstall then `ccodex
  doctor` reports clean") may be asserting a state that does not exist.

---

## 6. Where the design is right, and honest about itself

Credit, because it changes the verdict:

- The "two of everything" diagnosis is correct and is the best-argued part of any of the three
  designs. Two dispatchers with three declared divergences, two bundle front doors over one ledger
  with divergent evidence trails, four acquisition planes, 44 tasks — all verified.
- Refusing P4 on ADR-0031's own terms (three conjunctive triggers, all false; five measured facts,
  none changed) is correct and correctly reasoned. Report 03 does add an *open* Windows defect
  spawning Rust-compiled executables — `uv`'s exact profile — which strengthens the refusal.
- Its UNVERIFIED markers are placed honestly (`mise where`, output-style autodiscovery, startup
  latency, the unversioned `mise use -g` form), and §9's eleven open questions include the ones that
  actually matter (ledger ceiling, codex plane, the unconditional refresh).
- It correctly identifies that `Config.state_root` exists as a seam (verified at
  `install_skill_bundle.py:118,129,134`) and that the legacy-state mirror is both dead compatibility
  state and the structural blocker to project scope (verified at `:132-135`).

---

## 7. Graft candidates — what MUST survive into any final plan

**7.1 Delete the second dispatcher, the second acquisition bootstrap, and the PATH plane; let mise
own PATH.** `install_operator_tools.py` (1,135) + `assets/launchers/ccodex.in` (509) +
`tests/test_operator_tools.py` (1,660) + `bootstrap-agentic-sdlc.sh` (280) +
`tests/test_bootstrap_agentic_sdlc.py` (408) — all line counts verified. This single move deletes the
`HostPreconditionError` exit-3 class that inserts three operator actions mid-install (report 01
§D.2), the six install-time template bindings, the three declared dispatcher divergences, and the
"drags the entire gateway toolchain to get one file on PATH" defect (report 01 §D.3). It is
independent of every other choice in every design, and both Design B and Design C delete the same
things. Take it first, with §2.2's blast radius (recover, reader, 7 test files, the plan-digest
shape) named and budgeted.

**7.2 Phase 0 in its entirety, minus the plugin symlinks.** Delete `channels`
(`release-contract.v1.json:59-78`), `policy/ccodex-sdlc-read-report.v2.json` + its digest pin +
pin test, `selection` from the acquisition receipt, the legacy-state mirror and second-document
refusal, `mise run setup`, the two shell compatibility wrappers, and the false comment at
`validate_bundle.py:1699`. Every one is verified-unread scaffolding, the deletions are inert, and the
"`bundle:status` byte-identical before and after" check is a genuinely good gate for them. **Do not
delete `plugin/output-styles` or `plugin/workflows`** (§1.3).

**7.3 One exit ladder, and block-before-write for `install`.** Adopting `update`'s discipline
(`ccodex_sdlc_update.py:36-42`, `BLOCK_SENTENCE` at `:229`) so a pre-write collision is **exit 3
with nothing written** instead of exit 1 after 48 of 49 entries landed (report 01 §D.6) is the single
biggest correctness improvement in the document, and it makes `status`'s answer mean something.
Pair it with §2's rule that `--scope` and `--agent` are required with no wildcard, per the product
spec's own "there is no wildcard `--all` lifecycle operation."

**7.4 (runner-up) Release CI + published `SHA256SUMS` + a self-pin in the checkout's `mise.lock`.**
Phase 1's *mechanism* is right and is the plan's undone step 7; only its reproducibility *claim* is
wrong. Restate the check at the per-file-manifest level (§1.1) and keep it.

---

## 8. Verdict

**ADOPT-WITH-CHANGES**, on the understanding that the changes amount to "adopt the subtractions,
reject nearly all the additions." Design A's diagnosis is the most accurate of the three — "two of
everything, fixed by subtraction" is verifiably the shape of the problem, and its refusal of the Bun
rewrite on ADR-0031's own conjunctive-trigger terms is the correct answer to P4. Its Phase 0, its
deletion of the second dispatcher and the PATH plane, and its unification of the exit ladder are
load-bearing improvements that must survive into any final plan regardless of which design wins.
But as a whole it cannot be adopted as written: its flagship supply-chain check is falsified by
`build_release.py:31-36`, its marquee new capability (auto-sealed acquisition receipts) is both
mechanically impossible from a mise-resolved root (`ccodex_sdlc_install.py:738`;
`write_acquisition_receipt.py:203`) and an ADR-0019 violation once achieved, its "readers write
nothing" and "dry-run writes nothing" guarantees are broken by the `require_toolchain` →
`uv python install` route it extends to every verb, its largest deletion has an unnamed blast radius
through `ccodex_sdlc_recover.py` and the digest-as-approval plan shape, its own upgrade transcript
exits 3 for want of a `mise trust`, and its new project scope contains a committed-payload trap that
makes the feature unusable in the very configuration its open questions recommend. Above all it
fails its own thesis: offered a repository its maintainers' audit calls "decisively overengineered"
at 46:1, it proposes −3.3% while *extending* the ~10,600 lines of receipt machinery that place 28
files, and asks a solo maintainer for nine container-proofed phases, two new compatibility tuple
rows, one ADR supersession, two ADR amendments, and a purpose-built compatibility state with a
scheduled deletion date to get there. Take §7's three grafts, price §2.2's blast radius honestly,
and let a leaner design own the layers above them.
