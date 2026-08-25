# Front-door unification — one lifecycle verb family over (host, scope, root)

- **Seed:** agentic-sdlc-7a2b
- **Date:** 2026-08-25 (v2, same day — revised per the operator grill and the independent
  deletion audit; §10 records every finding's disposition. §§2–5 are ratified with the named
  edits applied; §6 and §7 are re-cut. Re-review verdict: RATIFY; its six wave-local residuals
  R1–R6 and the conductor's sequencing ruling are absorbed in the third commit — §10 records
  where each landed.)
- **Written against:** this worktree at `cfced8f` (v0.7.5). Every `file:line` below was re-read at
  this commit on this date; where an issue or corpus line number has drifted, the current number is
  used and the drift is listed in §1. Audit claims this revision builds on were independently
  re-verified against the tree, not inherited.
- **Specs of record:** gh #11 (the unification), gh #8 (the umbrella decision record), gh #10 (the
  dispatcher consolidation, sequenced here), gh #13 (the Bun rejection whose G1/G2 harvest this plan
  consumes), `docs/research/2026-08-24-install-ux-corpus/` (especially `05-receipts-machinery.md`,
  `design-c-lean.md`, `critique-c.md`), and ADR-0021 (amended in §5).
- **Status:** DESIGN. Nothing in this document is implemented, and a merged design authorizes
  nothing; each wave in §6 carries its own gate and its own authorization.

## 0. Ratified constraints (operator, 2026-08-25)

This design works **within** the following decisions, not around them:

1. **Top-level verbs.** `ccodex install | status | update | uninstall | doctor | recover`, with
   `--scope user|project` and `--agent claude|codex` required on the four lifecycle verbs — no
   default, no wildcard. The `bundle` and `sdlc` spellings become refusals naming the new verb.
   (This supersedes issue #11's open "which family spelling survives" question: neither survives as
   a namespace; the verbs move to the top level.) Note what decision 1 implies and the tree does
   not yet provide: `--agent codex` must be admissible through the **receipted** lifecycle, and
   today that plane is claude-only at five verified layers (§6, wave WX).
2. **Receipt/pointer plane keyed by (host, scope, root)** — in this repo's vocabulary,
   (agent, scope-kind, resolved root).
3. **Copies forced for project scope.**
4. **Five distinct effects, five distinct grants** (acquisition, trust, bundle activation, settings
   activation, launch — gh #8 decision 6). This design merges front doors, never grants.
5. **The native-plugin-channel outcome (gh #12, partially landed) subtracts work** from this design
   rather than invalidating it (§1, §8 D4).

## 1. What changed since the specs were written (stale-assertion ledger)

The issues and corpus were written against `e0fbf92` (v0.7.4). Verified deltas at `cfced8f`:

| Assertion in the specs/corpus | Status at cfced8f |
|---|---|
| "Nothing gates the published artifact; `.github/workflows/` has only two files" (#8, #13, corpus 05) | **Stale.** `.github/workflows/release.yml` exists; `release:smoke` (`scripts/smoke_release.py`, `policy/release-smoke.v1.json`) executes the shipped archive, and the release workflow's mutation job restores the v0.7.4 route from `.github/mutations/restore-v0.7.4-uv-run-sdlc-route.patch` and requires the smoke to go red. gh #9 is **closed**. Phase 0 of #8 is done; nothing here waits on it. |
| "The dispatcher fix `cd3fd3d` is on main but unreleased" (corpus 05 §b) | **Stale.** v0.7.5 shipped with the gate (`7b7df05`); `EXPECTED_CHECKOUT["version"]` is `0.7.5` (`scripts/ccodex_sdlc.py:37`). |
| "`plugin/` is five symlinks; `claude plugin validate ./plugin --strict` fails; `README.md:212-213` is false" (#8, design-c, critique-c) | **Stale.** `2f3bf30` (gh #12, partial) published `plugin/` as real component bytes gated as a drift-checked mirror (`git ls-files -s plugin/` shows `100644` entries), and `README.md:213-221` now records the history and the passing strict validation. What remains open in #12 is channel adoption, not the build fix. |
| "44 `[tasks` blocks in mise.toml" (#8, #10) | Drifted: **45** at cfced8f. |
| `install_skill_bundle.py` line anchors (#11) | Drifted but substantively intact: `args.agent or "all"` now at `:1851`; the legacy-state refusal wired at `:1329-1337`; adoption message at `:1435`; the `.claude` grandparent assertion at `:378`; `state_directory()` at `:220-230`; `agent_root` at `:301-302`; `marketplace_overlap` at `:959-961`; workflow tasks at `mise.toml:245-255`. All re-verified. |
| "FINDING-1: uninstall leaves 26 `owned-entry-conflict` rows" (corpus 05 §b) | **Fixed at HEAD**: `ccodex_sdlc_uninstall` retires the matching ownership rows (corpus 05 §a itself records the fix, citing agentic-sdlc-42ec). The G2 "receipts as the ledger" inversion is therefore *not* needed to fix a live defect; #11's decision to adopt only the key stands. **Note the corpus contradicts itself**: `05-receipts-machinery.md:81` and `:141` still describe FINDING-1 as filed-not-fixed while §a records the fix; both stale lines are named here so nobody builds on them. |
| Issue #11's "`<family>` is the open decision" | **Superseded** by ratified decision 1: top-level verbs, both spellings retired. |
| Issue #11 Phase-1 check text names `bundle status --json` | **Wrong at any commit**: the bundle CLI has no `--json` flag (`install_skill_bundle.py:1790-1828`); only the sdlc reader does. |

One cross-issue fact **neither issue prices**, found while verifying: `derive_plan`
(`scripts/ccodex_sdlc_recover.py:455-515`) digests **both** the operator-tools journal
(`:470-473`, consumed at `:492`) **and** a `bundle/legacy-state` journal row derived from
`Config.legacy_state_path` (`:476-484`). So the legacy-state deletion this design requires (§3.4,
issue #11 Phase 1) reshapes the recover plan digest on every host, exactly as #10's operator-tools
journal drop does. Both invalidations are one-way by design ("the approval IS the digest",
`scripts/ccodex_sdlc.py:52-58`). Each reshape is **announced in the release that carries it**;
§3.6 has the pricing.

## 2. The verb surface

### 2.1 Grammar

```
ccodex install   --scope user|project --agent claude|codex [--project PATH] [--mode auto|link|copy] [--dry-run]
ccodex status    --scope user|project --agent claude|codex [--project PATH] [--json]
ccodex update    --scope user|project --agent claude|codex [--project PATH]
ccodex uninstall --scope user|project --agent claude|codex [--project PATH] [--dry-run]
ccodex doctor    [--json]
ccodex recover   --dry-run [--json] | --apply <plan-sha256>
```

- `--scope` and `--agent` are required on the four lifecycle verbs, with no default and no
  wildcard. `doctor` and `recover` take **no** selectors: `doctor` is the whole-box read ("what is
  on this machine" spans every scope by definition), and `recover` resumes the one pending slot the
  substrate can carry, which is not a scoped object. **Ratified** (grill answer D1, §8).
- `--mode` is admitted only with `--scope user`. Project scope is copy-only by ratified decision 3;
  `--scope project --mode <anything>` is a grammar refusal (exit 2) **before any filesystem
  resolution**, carrying `manage_claude_workflows.py:18-27`'s three reasons verbatim (a committed
  entry must be self-contained; a link embeds a user-specific absolute path; a later bundle refresh
  must not silently change what a target's sessions execute without new per-repo authorization).
- `--project PATH` is admitted only with `--scope project`; with `--scope user` it is exit 2.
- Exit ladder is the unchanged Decision-9 contract: 0 ok · 1 unexpected failure · 2 grammar/input ·
  3 clean refusal before effect · 4 admitted partial or unknown effect.
- `--agent codex` is grammar from day one but is admitted through the receipted lifecycle only
  once wave WX lands (§6): today `HOSTS = ("claude",)`
  (`distribution_activation_receipt.py:268`), `LIFECYCLE_HOSTS = ("claude",)`
  (`ccodex_sdlc.py:52`), the install module's five host constants
  (`ccodex_sdlc_install.py:153,158,160,226,261`), `ccodex_sdlc_recover.py:59`, and a
  `policy/release-contract.v1.json` that names `codex` zero times all pin the plane to Claude.
  Until WX, `--agent codex` on the receipted verbs refuses by name (`agent-not-yet-receipted`,
  exit 3) naming the wave's seed — never a silent fall-through to the unreceipted path.

### 2.2 Scope resolution (project), stdlib-only

Ordered ladder; every step is a named refusal, never a guess. Adopted from issue #11 unchanged,
with the detector re-verified in this tree:

1. `--project PATH` given → PATH is the candidate root; no walk.
2. Otherwise walk up from cwd to the first directory containing a `.git` entry.
3. Admit the entry using the shape `skills/agentic-sdlc/tools/offline-inspect.py` already
   implements (`git_metadata_directory`, `gitfile_target`, `git_baseline` — the `.git` **directory**
   must hold a regular `HEAD` plus `objects/` and `refs/` under its commondir; a `.git` **file**
   must be exactly one `gitdir: ` line resolved relative to the target; anything else refuses as
   `unsafe-node`). This admits linked worktrees and `GIT_DIR`-relocated checkouts. The detector is
   extracted into a shared module in wave W4 (§6) so the skill tool and the installer consume one
   copy; no `git` subprocess is ever spawned (issue #11's "we will not" list — the
   `instruction-generator.py` refusal is subprocess-backed and is deliberately not reused).
4. Refuse (exit 3, `forbidden-root`) a resolved root that is `Path.home()`, the distribution root,
   inside the mise install tree, or the installed home plane (generalizing
   `manage_claude_workflows.py:522-523`). With `--project PATH`, additionally refuse a PATH that is
   a strict subdirectory of the detected root. A non-git directory refuses by name
   (`not-a-git-project`), not silently.
5. A resolved worktree root is that worktree, not the primary checkout: two linked worktrees of one
   repository are two roots, two pointer files, two independent copies. That is the intended
   semantics of copies-per-root, stated so nobody reads it as a defect.
6. **One deliberate exception, for `uninstall` only** (audit B6): an explicit `--project PATH`
   whose path does **not exist** is admitted iff a pointer exists for
   `sha256(operational_path(PATH))[:16]` — the removal set is then **records only** (pointer,
   receipts-plane retirement seal, ledger rows under that root); there are no bytes to remove and
   none are touched. This is what keeps a moved or deleted project root from stranding its records
   beyond every verb — the ADR-0022 amendment pathology ("an evidence record with no reader is not
   a control; it is a write-only artifact",
   `docs/adr/0022-activate-repositories-through-digest-approved-plans.md:90-107`). The
   `forbidden-root` refusals still apply to the normalized path.
7. **A root that exists but no longer admits as a git project, while a pointer exists for it, is
   its own named state: `pointer-outlived-root`** (re-review R4) — not `not-a-git-project`, which
   reads as a wrong input when the truth is that the pointer outlived its repository (a deleted
   `.git`, a recreated directory). Records-only retirement is wrong here, because real bytes may
   still sit under `<root>/.claude`, so `uninstall` **refuses** with both remedies named: restore
   the root's git metadata and uninstall normally, or remove the directory entirely and then use
   item 6's records-only retirement. Never guessed at in either direction.

### 2.3 Per-verb admission, refusals, effects

Refusal names are stable tokens; every refusal is exit 3 unless marked (2). "Ledger" is the
unchanged v4 ownership document (`install_skill_bundle.py:58`, `STATE_VERSION = 4`); "pointer" and
"receipt" are §3's plane.

**`install`**

| Aspect | Content |
|---|---|
| Admission | selectors valid; project root resolved (project scope); root trusted (dispatcher preflight, `bin/ccodex:114-137`); payload classified (§3.3): release root (manifest.json present, verified both directions) or checkout; for user+claude, `marketplace_overlap` still blocks (`install_skill_bundle.py:959-961`); exactly one admissible payload identity. |
| Refusals | `missing-selector` (2) · `wildcard-selector` (2) · `mode-forbidden-at-project-scope` (2) · `project-flag-without-project-scope` (2) · `unresolvable-project-root` · `unsafe-node` · `not-a-git-project` · `forbidden-root` · `untrusted-root` · `agent-not-yet-receipted` (pre-WX only) · `payload-manifest-mismatch` · `marketplace-overlap` (user+claude only; project scope emits a named `overlap:` advisory line and blocks nothing — ratified, §8 D5) · `foreign-destination` (per entry; all-or-nothing before any write) · `legacy-pointer-ambiguity` (§3.5). |
| Effects | classify → transactional create/refresh/adopt through the existing substrate → **auto-seal** the acquisition evidence for a release root (§3.3, retiring the manual placement-bridge recipe in `docs/plans/2026-08-14T163833Z-Install-UX.md:195-219`; a second install of the same archive **reuses** the existing `<archive-sha256>.json` receipt after re-validating it — receipts are create-only, so reuse-not-overwrite is the only admissible idempotence) → seal one v2 activation receipt → replace the `(agent, scope, root)` pointer, receipt-then-pointer. Exit 0 requires all three (the `ccodex_sdlc_install.py:1905-1917` rule, kept). Project scope prints the session-snapshot sentence (§4). |

**`status`** — read-only. Admits any prestate; reports, per the selected (agent, scope, root):
ledger rows, receipt/pointer presence, `unreceipted (legacy bundle install; re-run install to
seal)` for rows with no receipt, unowned collisions in configured collections (the G3
collision-visible-readers correction from #13 — today `status` structurally cannot see a collision
and the operator must know to run `install --dry-run`), and always one terminal summary line.
Never a refusal beyond grammar (2) and an unresolvable project root (3).

**`update`** — admission: a live activation for the selected (agent, scope, root) — a v2 pointer,
or the legacy pointer for (claude, user) which it migrates first (§3.5) — plus exactly one other
admissible payload identity differing from the active one. A `modified` or `foreign` entry blocks
the whole run before anything moves (the existing `ccodex_sdlc_update.py` rule, kept). Refusals:
`no-activation-for-scope` · `ambiguous-candidate` · `blocked-by-modified-entry`. Effects: refresh,
seal v2 receipt with a `supersedes` ancestor, replace pointer; the prior receipt is retained under
its own id.

**`uninstall`** — admission, in preference order: (i) the `(agent, scope, root)` pointer — removal
candidates come from the receipt's own inventory, an entry is removed only if its recorded prestate
was `absent`/`owned` **and** its live digest still matches; (ii) at **either scope**, when no
pointer exists but ledger rows do: ledger-driven removal exactly as today's proven
`bundle uninstall`, bounded by the same four controls (agent-restricted; rows under the selected
scope's resolved root boundary — the configured home for user scope, the resolved project root for
project scope; live-digest match per row; foreign/modified preserved), **announced** as
`legacy-unreceipted uninstall (no activation receipt for <agent>/<scope>)` and sealing a v2
retirement receipt (§3.2's `prestate_evidence: "ledger"` variant). The project half exists because
"project planes are born receipted" is factually false: today's `--claude-home <repo>` side door
mechanically writes unreceipted ledger rows under a repository root (issue #11's own evidence),
and after wave W1 deletes that flag those rows would otherwise be selected by no verb — the
FINDING-1 defect class this program exists to delete (audit W-f). Path (iii), records-only
retirement of a nonexistent root, is §2.2 item 6; a root that exists but no longer admits as a
git project while its pointer exists refuses `pointer-outlived-root` (§2.2 item 7). Retires the
matching ledger rows in every path (the agentic-sdlc-42ec rule, kept).

**`doctor`** — read-only, no selectors. Names **every** surviving state store by absolute path with
a verdict per store; enumerates every live pointer under `activation/active/`, reporting
`orphaned-root` for a project pointer whose recorded root no longer exists on disk (remedy: the
records-only uninstall, audit B6) and `pointer-outlived-root` for one whose root exists but no
longer admits as a git project (remedy: §2.2 item 7's two options, re-review R4); reports the dispatcher's own path and
whether it is mise-shim-resolved (#10's replacement for the deleted `HostPreconditionError`
diagnostic); reports orphaned legacy stores by name with a remedy line (§3.5, §4.3). Acceptance:
the number of stores it names equals the number the tree has (gh #8 acceptance 9) — a check that
is only decidable **at the end of the wave train**, because doctor's store roster is co-owned by
W3a, D3+D4, and W5 (audit B4); §6 records it as the train's terminal check.

**`recover`** — unchanged contract: `--dry-run` derives the canonical plan and renders its digest;
`--apply <plan-sha256>` re-derives and refuses a moved or stale state by name
(`stale-plan-digest`). What changes is the **plan's content**, twice, priced in §3.6.

### 2.4 How the retired spellings refuse

`bin/ccodex` keeps explicit `bundle)` and `sdlc)` arms whose only behavior is a refusal that names
the exact replacement, with the sub-verb mapped:

```
$ ccodex bundle install --agent claude
error: `ccodex bundle install` is retired. The lifecycle verb is now top-level:
  ccodex install --scope user --agent claude
(exit 2)

$ ccodex sdlc status
error: `ccodex sdlc status` is retired. Read verbs are now top-level:
  ccodex status --scope user --agent <claude|codex>   (per plane)
  ccodex doctor                                        (whole box)
(exit 2)
```

Every sub-verb of both families maps: `bundle install|status|uninstall` →
`install|status|uninstall`; `sdlc install|update|uninstall` → the same top-level verbs;
`sdlc inspect|status|doctor` → `status`/`doctor`; `sdlc recover …` → `recover …` (arguments named
verbatim in the message). **Exit code 2 with the replacement invocation as the message-content
contract — ratified** (grill answer D1, §8): Decision 9 reserves 3 for an operation the system
declines to perform and 2 for an input that is not in the grammar; a retired spelling is a
vocabulary miss, exactly like the existing unknown-command arm (`bin/ccodex:334`), distinguished
only by a message that carries the migration. Tests assert the message, never the bare exit code
(§7).

The `mise.toml` checkout tasks are renamed in the same wave (`bundle:install` →
`lifecycle:install`, etc., thin wrappers over the same entrypoint) so no path — dispatcher, task,
README, AGENTS.md — keeps the retired spelling alive (gh #8 acceptance 2's "the retired spelling
appears in no dispatcher arm" generalized to both spellings).

## 3. The receipt and pointer plane

### 3.1 Layout

```
<state>/agentic-sdlc/acquisition/receipts/<archive-sha256>.json         (unchanged, v1)
<state>/agentic-sdlc/activation/receipts/<operation-id>.json            (v2 bodies from now on)
<state>/agentic-sdlc/activation/active/<agent>/user.json                (pointer, user scope)
<state>/agentic-sdlc/activation/active/<agent>/project-<root-key>.json  (pointer, project scope)
```

`<agent>` ∈ {`claude`, `codex`}; `<root-key>` = `sha256(resolved_root)[:16]`, generalizing the key
`manage_claude_workflows.py:86-91` already works out for one entry kind. The root key lives **only
in the pointer filename** — it is not a receipt-body field (audit W-a; a stored field whose only
function is to be checked against a derivation of another field in the same document is the same
"two spellings of one fact" that §3.2 deletes `activation_scope` for). **The pointer filename is
the admission authority**: `update`/`uninstall` admit exactly the pointer for their own
(agent, scope, root) and nothing else. This is the critique-a §2.3 fix — with `--agent` required
and no wildcard, a per-scope-only pointer would let a codex activation overwrite a claude one and a
subsequent claude uninstall would remove codex bytes. Two agents, two files; N roots, N files.

The ownership ledger stays **one user-global v4 document, unchanged in shape and version**. Scope
is derivable from a record's absolute-destination key relative to a resolved root — records for a
different root are retained and left unselected, never reinterpreted as conflicts
(`install_skill_bundle.py:1591-1597` behavior, kept). The `.claude` grandparent assertion
(`:378`) is already satisfied by `<repo>/.claude/<collection>/<name>`, so the record validator does
not change. `Path.home()`-anchored `state_directory()` (`:220-230`, pinned by
`tests/test_install_skill_bundle.py:819`) is kept: one ledger per machine is what lets `doctor`
answer "what is on this box".

### 3.2 The v2 activation-receipt body — illegal states unrepresentable

The single v1 → v2 break groups **every** receipt-schema change (issue #11's instruction). The
discipline throughout: **one fact, one spelling, closed key sets per variant** — cross-field prose
guards are replaced by shapes that cannot express the disagreement.

```jsonc
// scope: a closed discriminated union. Key sets are EXACT per kind.
// `agent` is the body's ONLY statement of which plane was touched: there is no sibling `host`
// field in v2 (conductor ruling 2026-08-25, §10).
"scope": { "kind": "user",    "agent": "claude" }
"scope": { "kind": "project", "agent": "claude", "root": "/abs/path/to/repo" }
```

1. **`activation_scope` AND `host` are deleted, not extended.** Issue #11 sketched keeping
   `"claude-home"` and adding project spellings beside the new `scope` object. That is two spellings
   of one fact, and a receipt where they disagree is a representable illegal state guarded only by a
   validator clause. The same argument reaches `host`: it and `scope.agent` name one plane, so v2
   carries `scope` alone and readers derive every display string from it — including a
   host-application spelling like `claude-code`, which is a rendering rather than a stored field.
   (The v1 validator's one-lowercase-token `activation_scope` rule and its closed `host` vocabulary
   both stay for v1 documents; v2 has neither field, so a v2 body carrying either is refused by the
   exact key set and there is no agreement check between them to get wrong.)
2. **Key sets closed per kind; the root key is derived, never stored.** A user-scope `scope`
   carrying `root` is refused by exact-key-set comparison, as is a project-scope one missing it.
   `root` must be absolute. `pointer-receipt-disagreement` fires when the pointer's path disagrees
   with the pointed receipt's `scope` on **any** of three axes: agent segment vs `scope.agent`;
   filename shape vs `scope.kind` (a `user.json` pointer aimed at a project-scope receipt, or a
   `project-*` pointer aimed at a user-scope receipt, has no matching segment to compare and is
   refused on the kind axis first — audit N3); and, for project pointers, the filename's root-key
   segment vs `sha256(scope.root)[:16]` recomputed at admission. A hand-moved pointer cannot
   redirect an uninstall.
3. **Mode is enforced where it is real: per inventory row.** Project-scope bodies require every
   inventory row's `mode` to be `copy`; there is **no** body-level `mode_policy` field (audit W-b —
   single-valued on one variant, `scope.kind` already identifies the policy, and the per-row check
   is the control that actually binds bytes). If a second project mode is ever designed, a policy
   field returns with more than one admissible value.
4. **`checkout` is one optional object, not a source union** (audit W-c). The body already states
   "release payload" twice — `archive_sha256` non-null plus the required `derived-from` ancestor —
   so a third `payload_source: release-root` spelling would be the same defect as items 1–2. v2
   adds exactly one optional object:

   ```jsonc
   "checkout": { "commit": "<40hex>" | "unknown", "dirty": true|false }
   ```

   with one invariant, enforced by shape per operation: for `install`/`update`, **exactly one
   `derived-from` ancestor (naming the acquisition receipt) iff `archive_sha256` is non-null, and
   the ancestor is forbidden iff `checkout` is present**. A checkout body with an ancestor, or a
   release body without one, is unrepresentable rather than checked in prose.
5. **What a checkout body must answer honestly** — the v1 constants v2 must generalize, because
   "everything else carries over unchanged" is false for a manifest-less payload (audit W-c):
   - `candidate_id` is `_hex64` and not nullable
     (`distribution_activation_receipt.py:796`): a checkout body carries a digest over the
     **discovered inventory rows plus their `content_sha256` values**, so the field stays exact,
     non-null, and distinct for two different dirty trees. (v2 claimed this could reuse
     `build_release.py`'s `candidate_id` derivation; it cannot — that digest includes the source
     commit and tree, which are undefined for a dirty checkout, and substituting `"unknown"`
     there would collide two different dirty trees. Re-review R2's derivation is the one
     specified.)
   - `archive_sha256` is already `_nullable_hex64` (`:798`) with the sanctioned-unknowns rule
     `null_digest_requires_unknown` (`:1286`) governing null digests: a checkout body records
     `null` under exactly that rule.
   - `resolved_version` may not be null (`:821-832`, seed agentic-sdlc-0faa), and no member of
     `VERSION_SOURCES = ("adapter-readback", "archive-manifest", "request")` (`:284`, `request`
     refused at `:844` region) is admissible for a checkout. v2 adds **one** closed member,
     `"checkout-tree"`: the version read from exactly **one** authoritative file —
     `.version-bump.json`'s own `current` field, the bump driver — never from a request. A
     mid-bump tree with drifted sibling manifests is a legitimate checkout-install state; the
     drift is the gate's business (`bump-version.sh --check`), and the receipt records the driver
     value alone (re-review R6).
6. **The uninstall body gains a closed `prestate_evidence` discriminator** (audit B2):
   `"activation-receipt"` (path i — the single `derived-from` ancestor names the receipt being
   retired, exactly the shipped rule at `ccodex_sdlc_uninstall.py:76-87`) or `"ledger"` (paths
   ii/iii — **zero** ancestors, inventory drawn from the ledger rows the run retired). Without
   this variant the legacy-unreceipted retirement receipt is unrepresentable — the family refuses
   any body whose `derived-from` count is not exactly one
   (`distribution_activation_receipt.py:1419-1424`) — and deleting the legacy path instead would
   force an install before a removal. Ancestor-count-per-evidence is enforced by shape:
   receipt-evidence with zero ancestors and ledger-evidence with one are both refused.
7. Everything else — `operation`, per-entry inventory with
   `prestate`/`disposition`/`content_sha256`, `effect_state`/`terminal_phase` from the closed
   matrices, `supersedes` for update — carries over from v1 unchanged. (`host` was in this list in
   the ratified text and is NOT: item 1 deletes it. The implementation ruling in §10 records why.) The acquisition receipt
   schema (v1, `scripts/write_acquisition_receipt.py:65`) is untouched, including
   `selection: "absent"` — #10 already excluded that field, and this design inherits the exclusion.
8. **Named cost** (audit N6): "v1 receipts admitted read-only forever" (§3.4) means
   `distribution_activation_receipt.py` carries a second body-validator generation beside
   `BODY_SCHEMA` @1's 18-key closed set (`:783-787`). That is defensible for immutable sealed
   evidence — the documents cannot be rewritten to v2 without destroying what they prove — but it
   inverts the ownership ledger's one-schema-no-migration doctrine, and wave W2 owns saying so in
   its change description rather than leaving the inversion implicit.

### 3.3 Every install produces a receipt — including checkout installs

The convergence's core promise is "the receipted admission chain becomes the only path". Two
payload classes exist and the design admits both explicitly rather than leaving the checkout as an
unreceipted side door (which would silently resurrect the two-plane asymmetry this whole issue
exists to delete):

- **Release root** (a `manifest.json` is present at the root): `install` verifies every entry
  against the manifest in both directions and **auto-seals** the acquisition receipt itself,
  byte-compatible with `write_acquisition_receipt.py`'s output for the same root (that module
  remains the schema owner; `install` calls its seal path rather than reimplementing it). An
  existing receipt for the same `<archive-sha256>` is re-validated and reused, never overwritten
  (create-only files, `write_acquisition_receipt.py:93-96` keying). The manual placement-bridge
  recipe is retired, as its own text requests.
- **Checkout** (no `manifest.json`): admitted with the §3.2 item-4 `checkout` object, recording
  the commit when `.git` metadata is readable via the §2.2 detector (never by spawning git) and
  `"unknown"` plus `dirty` honesty otherwise, with `candidate_id`/`resolved_version` answered per
  §3.2 item 5. No acquisition receipt exists and none is faked. A checkout install may use
  `--mode link` at user scope — the contributor live-edit loop — and the receipt records exactly
  that, so "this plane is symlinked into a checkout" becomes a readable fact instead of tribal
  knowledge.

This is the one place this design **adds** vocabulary, and what breaks without it: either checkout
installs stay receipt-less (two doors again, gh #8 acceptance 3 unfalsifiable on the contributor
plane) or contributors lose the symlink loop entirely — and "refuse checkout installs" is not
available anyway, because §2.4 makes the mise checkout tasks thin wrappers over the same
entrypoint. The bound is one optional two-field object, one new closed `version_source` member,
and one inventory-digest derivation reused from the release builder (§9 restates it).

### 3.4 Migration from today's two planes

Today: the **receipt-less bundle ledger** (`bundle install` writes ledger rows only) and the
**receipt-sealed sdlc plane** (v1 receipts plus one pointer file spelled in four places:
`ccodex_sdlc_install.py:211`, `ccodex_sdlc_update.py:197/:465`, `ccodex_sdlc_uninstall.py:267`,
`ccodex_sdlc.py:106/:110`). First-contact rules, none silent:

| Prestate on first contact | Behavior |
|---|---|
| Ledger v4 document | Read as-is. No migration, no version bump. Any other version stays refused by name (existing rule, `install_skill_bundle.py:279-282`). |
| Ledger rows, no receipts (a bundle-installed host) | `status` names the state: `unreceipted (legacy bundle install; re-run install to seal)`. `install` refreshes owned entries and seals — the plane becomes receipted by the same command that always maintained it. `update` refuses `no-activation-for-scope` (there is nothing receipted to update; the message names `install`). `uninstall` takes the announced ledger-driven legacy path (§2.3 path ii) and seals a `prestate_evidence: "ledger"` retirement receipt. |
| Unreceipted ledger rows under a **repository** root (the `--claude-home <repo>` prehistory) | Same as the row above, at project scope: `status --scope project` names them; `install` adopts/refreshes and seals; `uninstall` path (ii) retires them (audit W-f). |
| Legacy pointer `activation/active-receipt.json` | Only (claude, user) can have written it (`ACTIVATION_SCOPE = "claude-home"` everywhere, `ccodex_sdlc_install.py:158`). Read verbs report it as `legacy pointer (migrates on the next lifecycle verb)`. The first mutating verb for (claude, user) re-files it as `active/claude/user.json` **before** its own admission logic runs, prints one line saying so, and removes the old file in the same transaction. |
| Legacy pointer **and** `active/claude/user.json` both present | `legacy-pointer-ambiguity`, exit 3, naming both paths and the remedy (remove one). Never guessed. |
| v1 activation receipts | Admitted **read-only forever** as history (cost named in §3.2 item 8). A v1 receipt that is the *active* statement is admitted by `update`/`uninstall` exactly once — as the outgoing document a v2 seal supersedes/retires. All new seals are v2. There is no receipt rewriting: sealed documents are immutable evidence. |
| A project pointer whose recorded root no longer exists | `doctor` reports `orphaned-root`; `uninstall --scope project --project <path>` performs the records-only retirement (§2.2 item 6). |
| A project pointer whose root exists but no longer admits as a git project | `doctor` reports `pointer-outlived-root`; `uninstall` refuses with the two §2.2 item 7 remedies (re-review R4). |
| Legacy workflow receipts (`agentic-sdlc-claude-workflows/`) | §4.3. |
| Existing byte-identical committed `<repo>/.claude/**` payload (a teammate's fresh clone) | The project-scope adoption rule (§3.7). |

Drift cases: a pointer naming an absent receipt → refuse by name (existing v1 behavior, kept). A
pointer whose path disagrees with its receipt's `scope` on agent, kind, or root key →
`pointer-receipt-disagreement` (§3.2 item 2). A receipt inventory entry whose live digest drifted →
that entry is `kept:`-preserved on uninstall (existing rule) and reported by `status`/`doctor`.

### 3.5 What this deletes, and what breaks without each deletion

Deletion pressure applied; each survivor names its load:

- **DELETED: `legacy_state_path` / `legacy_state_directory` and the second-document refusal**
  (`install_skill_bundle.py:133-134`, `:233-247`, wired `:1329-1337`, pinned by
  `tests/test_install_skill_bundle.py:1290-1307` — the "unexpected state location" test; the
  earlier draft's `:1249` cite was wrong, that line is the newer-schema-refusal test). The legacy
  mirror has **four** consumers, all owned by wave W1: the wired refusal; `derive_plan`'s
  `bundle/legacy-state` journal row (`ccodex_sdlc_recover.py:476-484` — digest reshape, §3.6),
  whose two-journals `PlanUnavailable` branch (`:487-491`) becomes dead code and is deleted with
  it; and the read-only projection (`install_skill_bundle.py:1530` iterates both paths), whose
  output feeds `ccodex_sdlc.py:1486-1489` into the read-report governed by
  `policy/ccodex-sdlc-read-report.v1.json` (`field_vocabularies.bundle` includes `state_paths`) —
  so W1 owes a check that the report still validates and lists exactly one bundle state path
  (audit W-e). The check exists to catch a home-relative document written by a generation that
  never shipped, and under a project root it turns
  `<repo>/.local/state/agentic-sdlc-installer/state.json` — a file an unrelated project
  legitimately owns — into a fatal error on every verb. Without the deletion, project scope
  cannot ship.
- **DELETED: the wildcard agent** (`args.agent or "all"` at `:1851`) and the selector-free
  `mise.toml:78-81` task shape. Without it, the README headline/Quickstart contradiction
  (gh #11 context) survives and decision 1 is violated.
- **DELETED: the four spellings of one pointer filename** — replaced by the keyed plane. Without
  it, ratified decision 2 is unimplementable and the critique-a §2.3 cross-agent uninstall defect
  stays reachable.
- **DELETED: the manual placement-bridge recipe** (auto-seal replaces it). Without auto-seal, the
  "one front door" still requires a documented side-channel shell recipe before its first verb.
- **KEPT: the ownership ledger as a separate document** (not inverted into receipts-as-ledger, #13
  G2's full form). What breaks without it: nothing today — FINDING-1 is fixed — and the inversion
  is a second schema break with no live defect behind it. It stays available; adopting only the key
  is #11's recorded decision.
- **KEPT: the pointer plane, with the B6 remedies rather than deletion.** The audit's ADR-0022
  test — does the record have a reader? — passes here: pointers have three named readers (`update`
  and `uninstall` admission, `doctor` enumeration). The pathology is **stale** records for vanished
  roots, not unread ones; §2.2 item 6 and doctor's `orphaned-root` row are the exits.
- **KEPT: `assert_safe_collection`** unchanged (`install_skill_bundle.py:631` region): its boundary
  follows `config.home`, so pointing the configured root at a project keeps the escape check
  intact. Without it, a collection replaced by a link is followed out of the root.
- **KEPT: the crash-consistent pending slot and v4 record shape.** Without them, project-scope
  writes lose the same interruption story the user plane has.

### 3.6 The recover plan-digest reshape (announced, never silent)

**MEASURED CORRECTION (2026-08-25, wave W1 executed):** reshape #1 does not exist. Both
`derive_plan` callers resolve a state root and pass it, and `legacy_state_path` was
`self.state_root or …`, so the two journal paths were the same file on every host and the old
dedup already collapsed the row — the deleted code was unreachable by any production caller.
W1 measured the digest byte-identical before and after on a fixed fixture
(`c87ce4f4…` both sides), and proved the row was real by forcing the unreachable configuration
on the pre-change tree (`state_root=None`, configured home ≠ operator home → three locators,
digest `fca4bef1…`, and the two-journals `PlanUnavailable` refusal). No approved digest was
invalidated and no release note is owed for W1. One reshape remains — D3+D4's operator-tools
journal deletion — and its digest movement must be **measured, not assumed** (the operator-tools
row is unconditional, so it should move; W1's probe technique applies: one `recover --dry-run`
on a fixed fixture before and after). The paragraph below is retained for that one reshape:

- Each reshape invalidates **every** previously rendered `recover --dry-run` digest on every host,
  including hosts that never had the deleted plane — the digest is derived from the plan document's
  bytes, and the `journal` array's membership is part of those bytes.
- There is deliberately no migration: `recover --apply <old-digest>` refuses as stale **by name**,
  which is the control working, not breaking (`ccodex_sdlc_recover.py:847-853` behavior).
- **The two reshapes are NOT coupled to one release** (audit W-d, reversing v1 of this plan): W1
  and D3+D4 ship independently, and **each** reshape is announced in the release notes of the
  release that carries it — one sentence naming the invalidation and one naming the new `journal`
  membership. Two announcements cost less than serializing two otherwise-independent wave lanes.
- Doctrinal note (audit B6): `recover`'s digest is **not** an approve-then-write authorization
  grant of the kind ADR-0022's amendment deleted. It resumes one already-armed pending transaction,
  and the plan is re-derived from live state at apply time — the digest binds "the state I
  reviewed is the state being acted on", not "this future effect is pre-authorized". The ADR-0022
  amendment (`docs/adr/0022-...:90-107`) is cited here as the reader-existence test applied in
  §3.5, not as a precedent against this mechanism.

### 3.7 Project-scope adoption

For a destination present with no ledger record, today's rule adopts a byte-identical copy as
`removable: False` (`install_skill_bundle.py:1435`) and conflicts otherwise — correct for the
shared user home, fatal for teams: a repo committing its own `<repo>/.claude/**` payload is, on a
teammate's fresh machine, permanently un-uninstallable (bytes match) or un-installable (any byte
differs). Project scope gets its own rule: a destination **byte-identical to the planned source and
inside the resolved project root** is adopted `removable: True` — the project root is the
authorization boundary the user-global home plane does not provide. Anything else stays a named
refusal. This is what makes committing the project payload viable, and committing is the ratified
team posture (§8 D2). Removal of a committed copy is **doubly recoverable** (audit N4): the
uninstall's own receipt records it, and for a git-tracked file `git status` shows the deletion and
the index restores it — project-scope uninstall prints one line saying so ("the project root is a
git repository; a committed copy is restorable from its index").

## 4. Folding in `scripts/manage_claude_workflows.py`

### 4.1 What it is, and what it already proved

The workflows manager is the tree's only designed project-scope path, for one entry kind: it copies
one owned installed workflow into `<target>/.claude/workflows/<name>.js` (copy, never symlink, for
the three reasons §2.1 now carries globally), keys its receipts by (workflow, destination) via
`sha256(destination)[:16]` in the **user's** state root (`:82-91`, store
`agentic-sdlc-claude-workflows/`), refuses the installed home plane as a target (`:522-523`), and
prints the session-start-snapshot sentence on every completed verb (`SESSION_SNAPSHOT_NOTE`,
`:68-71`). It is the working prototype of the (host, scope, root) key.

### 4.2 The fold

`ccodex install --scope project --agent claude` places the **project payload set** — every Claude
entry kind, including `workflows/` and `hooks/` bytes — into `<repo>/.claude/…` as copies, under
one v2 receipt whose inventory rows replace the per-file receipts, with the (claude, project, root)
pointer as the admission key. Two semantic consequences, stated rather than buried:

1. **The grant unit changes from one file to one (agent, root) plane.** The manager enabled one
   workflow per command; the unified verb activates the payload set per explicitly named root. The
   doctrine the manager encoded — enablement is a separately authorized per-repo step — is
   preserved at the operation level: `install --scope project --project <repo>` *is* that step,
   with its own explicit selectors and its own grant, reached by no install/gate/setup path. What
   is genuinely lost is per-entry granularity; a per-entry selection flag is deliberately **not**
   designed in (deletion pressure — no demonstrated need beyond the one shipped workflow; if a real
   need appears, it is an additive flag, not a schema change).
2. **Placing a workflow into a project's `.claude/workflows/` enables it at the next session**,
   because that directory is the host's only discovery surface (measured 2026-08-24,
   agentic-sdlc-4d2b). The hook bytes, by contrast, land inert — settings wiring stays its own
   grant (`claude:hooks:activate`), per ratified decision 4. Every completed project-scope verb
   prints the session-snapshot sentence, carried over verbatim.

The manager's crash story (pending receipt with before/after snapshots) is subsumed by the
substrate's pending slot, which the manager already builds on (`import install_skill_bundle`,
`import manage_claude_statusline` at `:52-53`). Deleted with it: its three `mise.toml:245-255`
tasks and `tests/test_manage_claude_workflows.py`.

### 4.3 Migration of live enabled copies and legacy receipts

- An enabled copy byte-identical to the planned source inside the target root is **adopted
  `removable: True`** by the first project-scope install (§3.7) — the common case, since the
  manager only ever places byte-identical owned copies.
- A copy that drifted (operator-edited) stays a named per-entry refusal, exactly as the manager
  itself would have preserved it.
- The legacy per-file receipts become orphans the moment the new receipt owns the destination.
  They are **evidence, not payload**: nothing breaks by their existence. `doctor` names the store
  (`<state>/agentic-sdlc-claude-workflows/`) with one remedy line ("superseded by project-scope
  activation receipts; remove the directory after verifying `status --scope project`"). Nothing
  deletes them on the operator's behalf. The manager itself is deleted only in wave W5, **after**
  the project-scope verbs are proven, so at every intermediate commit exactly one of the two paths
  is authoritative and both are never live for the same destination (install refuses the
  destination as owned in that window — the ledger row moved with the new install).

## 5. ADR-0021 amendment drafts

ADR-0021 is still `proposed`; per ADR-0028's rule a proposed child is not a current product
constraint, so both amendments are cheap. Draft text, ready to append as a dated amendment section
(the ADR-0022-style pattern):

> ## Amendment (2026-08-25): one top-level verb family with explicit scope
>
> Ratified by the operator 2026-08-25 (gh #8, gh #11).
>
> **Item 2 is replaced.** The release installs one operator CLI, `ccodex`. The Agentic SDLC
> lifecycle is owned by its **top-level** verbs — `install`, `status`, `update`, `uninstall`,
> `doctor`, `recover` — with `--scope user|project` and `--agent claude|codex` required on the
> four lifecycle verbs, no default and no wildcard. There is no `sdlc` and no `bundle` operator
> namespace: both historical spellings are retained only as refusals naming the replacement
> invocation. Every install seals an activation receipt; the receipt and pointer plane is keyed by
> (agent, scope, root); project scope is copy-only. Acquisition, trust, bundle activation,
> settings activation, and launch remain five distinct effects with five distinct grants.
>
> **Item 4 is replaced.** Stable and preview releases resolve to exact side-by-side identities.
> Update and removal are explicit receipt-backed operations selected per (agent, scope, root).
> `downgrade`, `rollback`, and `channel change` are **not** operations of this lifecycle: rollback
> is the operator selecting an earlier exact release through mise's side-by-side installs and then
> running an explicit `update`; channel selection is version selection. A second mechanism for any
> of the three would be the same "second update authority" this record already rejects for a
> self-updater. The first release under this amendment still has no self-updater.

Also in wave W6: ADR-0028's registry row for ADR-0021 is checked for agreement, and a clean-host
project-scope transcript lands under `docs/evidence/` per the ADR-0027 no-inheritance rule (a new
(scope) capability row gets its own evidence; nothing is inherited from the user-scope journeys).

## 6. Workstream decomposition (re-cut, v2)

Each wave is sized for one worktree, ends at `mise run check` green plus its named checks, and
leaves the tree shippable. The concurrency invariant (restated per re-review R1): two waves may
run concurrently only when their owned file sets are disjoint, and **every pair of waves that
touches the same file is connected by an ordering edge — never co-ownership**; the edges are
enumerated after the table. `D*`
waves are gh #10's phases. Changes from v1: W0 is **done**; D2 is serialized out of the parallel
group (audit B3 — it shares `install_skill_bundle.py` and its test file with W1); old-W3 is split
into W3a/W3b with `checkout`-object and uninstall-path work moved into W2 (audit B4); the Codex
receipted arm is its own wave WX (audit B1); W3a owns the release gate's mutation patch (audit
B5); D3+D4 owns three files v1 omitted (audit W-i).

**W0 — DONE.** Subprocess-seam harness: branch `work/agentic-sdlc-7a2b-w0-seam`, commit `5b3eb16`,
gate green at 2268 tests. 21 cases (14 route-sensitive, 7 machine-checked controls); the mutation
lever (`restore-v0.7.4-uv-run-sdlc-route.patch`) executed 14-red/7-green on a scratch tree, and
`RouteRegressionLeverTest` runs the lever on **every** gate. Later waves extend `SEAM_CASES` in
`tests/seam_harness.py` rather than writing a second harness; the harness's verb-coverage
inventory reads the reader's own vocabulary, so **a new verb fails the gate until it has a case**.
Integration point (re-review R3): W0's bytes are already merged to **main** at `73bb1b5` (the
fan-in of `5b3eb16` after a three-leg CI read); this plan branch lands on main after it, so every
wave branched from main carries the harness.

| Wave | Content | Files owned | Depends on | Gate / named checks |
|---|---|---|---|---|
| **D1** | #10 Phase 1: re-point `ccodex_sdlc.py` / `ccodex_sdlc_recover.py` / `manage_claude_statusline.py` from `install_operator_tools` helpers onto the bundle substrate; delete nothing. | those three + touched tests | W0 (done) | check green; `recover --dry-run` digest **byte-identical** before/after (recorded both) |
| **W1** | Ledger hygiene: delete `legacy_state_path`/`legacy_state_directory` and all FIVE consumers (§3.5 — wired refusal, `derive_plan` journal row **and** its now-dead two-journals `PlanUnavailable` branch, read-only projection second path, and `resume_bundle`'s lock-time locator loop, found in execution) + the `:1290-1307` pinning test; delete `args.agent or "all"`; require `--agent`; require-selectors on the mise tasks (the rename is W3a's); fix the README headline block. ~~Recover digest reshape #1~~ — measured nonexistent in execution; see §3.6's dated correction. | `install_skill_bundle.py`, `ccodex_sdlc_recover.py` (journal rows), `mise.toml`, `README.md`, tests | D1 | check green; `grep -rn legacy_state scripts/ tests/` = 0; missing-selector exits 2 naming both; `status` output byte-identical before/after on a populated fixture host; `sdlc status --json`/`doctor --json` still validate against `policy/ccodex-sdlc-read-report.v1.json` and report exactly **one** bundle state path (audit W-e) |
| **W2** | Receipt v2 + pointer plane: the single schema break of §3.2 (scope union, derived-only root key, per-row mode rule, optional `checkout` object with its ancestor invariant, `checkout-tree` version source, uninstall `prestate_evidence` variant), the keyed pointer files, the §3.4/§3.5 migration and drift rules, v1-as-history admission (cost named per §3.2 item 8), and the **legacy-unreceipted uninstall path at both scopes**, scope-parameterized by a root-boundary argument (project root wiring arrives with W4). | `distribution_activation_receipt.py`, `ccodex_sdlc_install.py`, `ccodex_sdlc_update.py`, `ccodex_sdlc_uninstall.py`, `ccodex_sdlc.py` (reader), tests | D1 (shared `ccodex_sdlc.py` — ordering edge, R1); parallel with W1 | check green; claude user-scope pointer lives at the keyed path with migration/ambiguity rules proven; the two-agent pointer check moves to WX (unreachable before it — audit B1) |
| **D2** | #10 Phase 2: statusline into the ledger as one narrow kind, explicit `0o755`, proven by executing the installed file. **Serialized after W1** (audit B3: shares `install_skill_bundle.py` + its test file). | `install_skill_bundle.py` (statusline kind), `manage_claude_statusline.py`, tests | W1 | check green; container: `stat -c %a` = 755 and a synthetic-payload execution prints a status line |
| **WX** | **Codex arm of the receipted plane** (audit B1 — v1's largest hidden wave): extend `HOSTS` (`distribution_activation_receipt.py:268`) and `LIFECYCLE_HOSTS`/grammar (`ccodex_sdlc.py:52`, `:348-358` region); parameterize the install/update/recover host constants (`ccodex_sdlc_install.py:153,158,160,226,261`, `ccodex_sdlc_recover.py:59`); add a codex compatibility row to `policy/release-contract.v1.json` (a REVIEWED contract edit, never a bump target) with its own ADR-0027 capability evidence — including choosing the codex host-version observation command and minimum, with the refuse-on-unobservable rule carried over; retire the pre-WX `agent-not-yet-receipted` refusal. | the five scripts above, `policy/release-contract.v1.json`, `scripts/validate_bundle.py` (contract arm if it pins shape), tests | W1 (shared `ccodex_sdlc_recover.py` — ordering edge, R1), W2 (shared receipt/install modules) | check green; `install --scope user --agent claude` then `--agent codex` leaves **two** pointer files; `uninstall --agent claude` leaves every codex destination byte-identical (sha256 before/after) **EXECUTED 2026-08-25 (ed30342), with corrections:** SEVEN layers widened, not five (update.py and uninstall.py each carried their own claude constants); the mutation that dies is the two-agent suite, NOT the seam case (the seam fixture refuses at payload admission before scope validation — deliberate insensitivity, documented); the vocabulary now lives in THREE deliberately separate places (host_planes.AGENTS canonical, receipt.HOSTS, reader.LIFECYCLE_HOSTS, pinned equal by test) plus frozen HOSTS_V1 that must never widen; two unpriced cross-plane collisions found and fixed (receipt operation-id identity, replaceable journal overwrite — both now agent-keyed); recover plan host field measured digest-byte-identical under rename, its deletion folded into D3+D4 reshape #2 by conductor ruling. |
| **D3+D4** | #10 Phases 3–4 collapsed (**ratified**, §8 D3): deprecate-and-delete the operator-tools plane, `ccodex.in`, its store and tasks, keeping the uninstall-remedy text; **recover digest reshape #2**, announced in its own release (§3.6, decoupled from W1's per audit W-d). Owns the three files v1 omitted (audit W-i): `policy/ccodex-sdlc-read-report.v1.json` (`operator_tools` is an exact-key top-level report field), `scripts/ccodex_sdlc.py` (report assembly/overall-state consumers), and `scripts/validate_bundle.py:275` (the policy digest pin). | `install_operator_tools.py` (delete), `assets/launchers/ccodex.in` (delete), `bin/ccodex` (dispatcher rows), `mise.toml`, the three W-i files, tests | D2, WX (shared `scripts/ccodex_sdlc.py` and `scripts/validate_bundle.py` — ordering edges, R1) | #10's own checks; `recover --apply <pre-reshape digest>` refuses stale by name; the read report validates against the revised pinned policy with no `operator_tools` field |
| **W3a** | Front door, grammar half: top-level verb table in `bin/ccodex` + `ccodex_sdlc.py` grammar (`--scope`/`--agent`), retired-spelling refusal arms (§2.4), the `require_toolchain` exit-class stance (below), **re-derivation of the release gate's mutation patch** (audit B5: the patch is textually anchored to the old `sdlc)` arm with six lines of context, and its own preamble names the re-derive recipe — W3a owns the patch and its preamble), and the new verbs' `SEAM_CASES` entries (the harness fails the gate on an uncased verb by construction). | `bin/ccodex`, `ccodex_sdlc.py` (grammar), `.github/mutations/restore-v0.7.4-uv-run-sdlc-route.patch`, `tests/seam_harness.py` cases, tests | W2, WX, D3+D4 (single dispatcher before the verb-table reshape) | check green; retired spellings answer with messages naming the replacement; **the re-derived mutation patch still turns the surviving route red** via `release:smoke --expect-refusal` naming `runtime-admission-refused` |
| **W3b** | Front door, acquisition half: auto-seal from the root's own `manifest.json` (via `write_acquisition_receipt.py`'s seal path exposed as a library), existing-receipt reuse (§2.3 install effects), checkout-object population, legacy-unreceipted user-scope uninstall wired through the new verbs. | `ccodex_sdlc_install.py` (seal path), `write_acquisition_receipt.py` (library exposure), tests | W3a | check green; `release:smoke` against a freshly built archive; one install on a release root seals acquisition + activation receipts with the correct ancestor; a corrupted-entry root refuses `payload-manifest-mismatch` with the **destination plane** unmodified (audit W-h: `find <configured home> <state root> -newer <marker>` empty — the source root is not what a partial install would dirty) |
| **W4** | Project scope: §2.2 ladder with the detector extracted to a shared module (consumed by both the installer and `offline-inspect.py`), copy forcing, §3.7 adoption with the N4 printed line, project-root wiring for the W2 uninstall path, the B6 remedies (`doctor` `orphaned-root`; records-only uninstall of a nonexistent root), project-scope `overlap:` advisory line (§8 D5). | new shared detector module, `install_skill_bundle.py`, `ccodex_sdlc_install.py`/`_update`/`_uninstall` (scope plumbing), `offline-inspect.py` (consume shared module), tests | W1, W3b (shared `ccodex_sdlc_install.py` — ordering edge, R1; W3b landing first also lets W4's transcripts exercise release-root payloads, not only checkouts) | check green; gh #11 acceptance 5–8 in throwaway repos (three live pointers; A's uninstall leaves B and user byte-identical; `find <repo>/.claude -type l` empty; forbidden-root and unsafe-node refusals with `find <repo> -newer <marker>` empty — pinned to the **target root**, audit W-h) |
| **W5** | Subsume the workflows manager: delete `manage_claude_workflows.py`, its tasks, tests; session-snapshot sentence on project-scope verbs; `doctor` names the orphan store. | `manage_claude_workflows.py` (delete), `mise.toml`, `bin/ccodex` (if any task alias), tests | W4 | check green; `grep -rn 'manage_claude_workflows\|agentic-sdlc-claude-workflows' scripts/ tests/ mise.toml` = 0; project install leaves `<repo>/.claude/workflows/<name>.js` as a copy and prints the sentence |
| **W6** | Decision debt: ADR-0021 amendments (§5), ADR-0028 registry agreement, AGENTS.md/README task-list re-diff, clean-host project-scope transcript under `docs/evidence/`, and the train's **terminal check**: `doctor --json` store count equals the tree's store count (gh #8 acceptance 9 — only decidable here, per §2.3/audit B4). | docs + the terminal check | W5, D3+D4 | check green (docs gate: broken references, secrets); transcript committed; store-count check recorded |

`require_toolchain` stance (W0 finding, decided here for W3a): `bin/ccodex:130-134` currently
exits **1** when the mise probe fails for a non-trust reason — a "failure" class for a state in
which nothing was attempted. W3a reclassifies it to **3**: an unreadable operator config is a
precondition boundary declining before any effect, and class 1 stays reserved for the tool's own
unexpected internal failures. The seam case asserting the old pairing is updated in the same
commit, which is exactly the discipline the harness exists to force.

Lanes: after D1, W1 ∥ W2 (file-disjoint); then D2 ∥ WX (D2 after W1; WX after W1 and W2);
D3+D4 after D2 and WX; then W3a → W3b → W4 → W5 → W6 (W6's D3+D4 dependency is transitive).
The R1 ordering edges, each naming the shared file it resolves: D1→W2 (`ccodex_sdlc.py`),
W1→D2 (`install_skill_bundle.py` + its test file, audit B3), W1→WX (`ccodex_sdlc_recover.py`),
W2→WX (`distribution_activation_receipt.py`, `ccodex_sdlc_install.py`), WX→D3+D4
(`ccodex_sdlc.py`, `scripts/validate_bundle.py`), D3+D4→W3a (`bin/ccodex`, `ccodex_sdlc.py`),
W3b→W4 (`ccodex_sdlc_install.py`); W1's `mise.toml` overlap with D3+D4 is covered transitively
through W1→D2→D3+D4. No file is co-owned by two concurrent waves. Rollback per wave: every wave is a
branch whose tree is shippable at the boundary, and no wave publishes anything — release cutting
stays a separate authorized act. The two digest reshapes (W1, D3+D4) each announce in the release
that carries them (§3.6).

## 7. Test strategy — the mutation check each wave owes (re-cut, v2)

Per this repo's discipline (a test that cannot go red proves nothing; every negative assertion
gets a positive control):

- **W0 (done):** the lever ran 14-red/7-green, and the harness's classification sensitivity is
  itself mutation-tested — `RouteRegressionLeverTest` applies the route mutation on every gate, so
  a harness that stops distinguishing routes fails the gate, not just the wave. One recorded gap
  for later waves: the four lifecycle verbs refuse for **different reasons on Linux vs Darwin**,
  and no single place records both texts (the smoke manifest declares the pairing for `install`
  only) — W3a's seam-case work extends the per-platform expected-text pairing to all four verbs.
- **D1:** re-introduce one `install_operator_tools` import into `manage_claude_statusline.py` → the
  import-freedom test dies. Digest byte-identity check doubles as the no-behavior-change control.
- **W1:** restore `args.agent or "all"` → the exit-2-missing-selector test dies. Restore
  `legacy_state_path` reads → the zero-grep test dies; plant a file at the legacy path in a fixture
  → no verb may fail (positive control that the hazard is gone, not merely renamed); the
  read-report check goes red if `state_paths` reports two entries again (audit W-e).
- **W2:** regress the codex pointer write to `user.json` — staged now, decided at WX (the
  two-agent scenario is unreachable before WX; W2's reachable mutations are:) hand-edit a pointer
  to a receipt with a mismatched root → `pointer-receipt-disagreement` on the root axis; aim a
  `user.json` pointer at a project-scope receipt → refused on the **kind** axis (audit N3); add
  `root` to a user-scope body / drop it from a project body → exact-key-set refusal; seal a
  **checkout body WITH a `derived-from` ancestor → refused** (audit W-g — the release-body-without-
  ancestor direction is vacuous, already unconditionally refused at
  `distribution_activation_receipt.py:1419-1424`); a `prestate_evidence: "ledger"` retirement with
  one ancestor and a `"activation-receipt"` retirement with zero → both refused (both directions
  of §3.2 item 6); a checkout body with non-null `archive_sha256` → refused (item-4 invariant).
- **WX:** re-pin `HOSTS` to `("claude",)` → the codex install seam case dies; remove the codex
  contract row → the codex install refuses by name (and the claude plane is untouched — positive
  control: the claude seam cases stay green under the mutation).
- **D3+D4:** #10's own checks, plus: `recover --apply` of a digest recorded before the reshape
  refuses stale **by name**; a plan rendered after carries only the bundle journal locator; the
  read report validates against the revised pinned policy, and re-adding the `operator_tools`
  top-level field makes the exact-key check die.
- **W3a:** delete the `bundle)` refusal arm → the message-content test (asserts the replacement
  invocation string, not the exit code) dies by falling through to the bare unknown-command text.
  **Patch liveness both ways** (audit B5): the re-derived mutation patch applied to a scratch tree
  turns `release:smoke --expect-refusal` red naming `runtime-admission-refused`; and a
  deliberately stale copy of the old patch must FAIL to apply (the patch's own documented
  fail-toward-red direction). The `require_toolchain` reclassification updates its seam case in
  the same commit. New verbs without `SEAM_CASES` entries fail the gate by the harness's own
  coverage inventory — no separate check needed, and that property is itself the W0-proven
  mechanism.
- **W3b:** corrupt one byte of a release root against its manifest → `payload-manifest-mismatch`
  with the **destination plane** unmodified (audit W-h). Second identical install → the existing
  acquisition receipt is re-validated and reused: assert no new file in `acquisition/receipts/`
  **and** that a tampered existing receipt is refused rather than reused (the direction that can
  go red; v1's "no duplicate receipt" check was near-vacuous given `<archive-sha256>.json`
  create-only keying — audit N5).
- **W4:** remove the `unsafe-node` branch → the fifo-as-`.git` fixture test dies. Point
  `--project` at `Path.home()` → `forbidden-root`, `find <target> -newer <marker>` empty at the
  **target**. Flip the adoption rule's `removable` to False → gh #11 acceptance-8's uninstall test
  dies. A linked-worktree fixture (`.git` file) resolves to the worktree root — and its control: a
  `.git` file with two lines refuses. B6 pair: move a project root aside → `doctor` reports
  `orphaned-root`; `uninstall --project <gone>` retires pointer+rows, seals a
  `prestate_evidence: "ledger"`-or-`"activation-receipt"` retirement as evidence dictates, and a
  re-run reports the requested end state already true. R4 pair: recreate the root **without**
  `.git` → `uninstall` refuses `pointer-outlived-root` and `doctor` names it — with the positive
  control that restoring the git metadata makes the normal uninstall proceed.
- **W5:** re-add a workflow receipt fixture → `doctor` must name the orphan store; delete the
  session-snapshot sentence from the project install output → its content test dies.
- **Cross-cutting:** the seam suite re-runs against the **extracted built archive** via
  `release:smoke` from W3a onward, so the shipped dispatcher — not the checkout — is what the verb
  surface is proven on. Worktree gates run only after the worktree's own `mise trust` is verified
  (a fresh untrusted worktree silently gates the parent tree).

## 8. Ratified decisions record (operator grill, 2026-08-25)

Formerly the open-questions section; every item is now decided and this section is the record.

- **D1 (was Q1) — CONFIRMED as designed:** `doctor`/`recover` take no selectors; retired
  spellings exit 2 with the replacement invocation as the message-content contract.
- **D2 (was Q2) — COMMIT is the documented team posture**, gitignore the solo posture; the
  installer prints both and writes neither (§3.7).
- **D3 (was Q3) — COLLAPSE** #10's deprecation phase into the demolition wave (D3+D4 in §6),
  keeping the uninstall-remedy text.
- **D4 (was Q4) — adopted as recommended:** the Claude user-scope arm's fate under gh #12 is
  decided after #12's remaining measurement; nothing in this train blocks on it, and the arm stays
  agent-parameterized and deletable.
- **D5 (was Q5) — adopted as recommended:** named `overlap:` advisory line at project scope,
  block nothing, measure an actual session's load before ever escalating.
- **D6 (was Q6) — adopted as recommended, partially reopened by audit B6:** the one-hour synthetic
  N=100 ledger probe stays a pre-fleet-advertising step, not a ship blocker; **independent of the
  probe's timing**, B6's named exits for stale records (doctor `orphaned-root`, records-only
  uninstall of a nonexistent root) are in scope now (§2.2 item 6, §2.3), because a pointer for a
  vanished root is a write-only artifact at N=1, not only at N=100.

## 9. Risks

- **Two digest reshapes in flight** (§3.6), now in independent releases (audit W-d). Mitigated by
  per-release announcements and named stale refusals; residual: an operator holding an unapplied
  dry-run digest across either boundary must re-derive, by design.
- **`bin/ccodex` contention** between D3+D4 and W3a, plus the release gate's mutation patch being
  textually anchored to the arm W3a replaces (audit B5). Mitigated by strict serialization, W3a's
  ownership of the patch, and the both-directions patch-liveness check in §7.
- **The `checkout` receipt object is new vocabulary** (§3.3) — the one place this design adds
  rather than deletes. Bound restated per audit W-c: one optional two-field object, one new closed
  `version_source` member (`checkout-tree`), one inventory-digest derivation reused from the
  release builder, and one shape invariant tying the `derived-from` ancestor to `archive_sha256`.
  No new store, no new verb. It is what makes gh #8 acceptance 3 ("every successful install seals
  one activation receipt … on both paths") true rather than aspirational.
- **WX (the Codex receipted arm) carries genuinely new evidence obligations**: a reviewed
  release-contract edit and an ADR-0027 capability row with its own observation command. It is
  scheduled before W3a because decision 1's grammar promises `--agent codex`; if its evidence
  gathering stalls, the pre-WX `agent-not-yet-receipted` refusal (§2.1) keeps the surface honest
  without blocking the rest of the train — W3a would then ship with the refusal in place and WX's
  check moves behind it. **Sequencing ruling (conductor, 2026-08-25): §6's edge holds — W3a
  depends on WX. This fallback is exercised only by an explicit conductor re-sequencing decision
  at that time, never by default.**
- **The v1/v2 dual body validator** (§3.2 item 8) is a deliberate doctrine inversion for sealed
  evidence, named as a W2 cost so it is reviewed as one.
- **Project payload set includes the workflow kind, which project placement enables at next
  session** (§4.2). Stated, receipted, and printed; the alternative (a per-entry selection flag)
  is deliberately deferred under deletion pressure.

## 10. Audit disposition record (v2)

Every finding from the 2026-08-25 deletion audit, its disposition, and where it landed. No finding
was rebutted; each claim acted on was independently re-verified against the tree first.

| Finding | Disposition | Where |
|---|---|---|
| B1 Codex arm hidden wave | adopted | §0.1, §2.1 refusal, wave WX, §9 |
| B2 retirement receipt unrepresentable | adopted (variant, not path deletion) | §3.2 item 6, §2.3 uninstall |
| B3 W1/D2 file collision | adopted | §6: D2 serialized after W1 |
| B4 W3 hides waves | adopted | §6: W3a/W3b split; checkout+uninstall work moved to W2; doctor acceptance named terminal |
| B5 mutation-patch breakage | adopted | W3a owned files + both-directions liveness check (§6, §7) |
| B6 orphaned-root pathology | adopted | §2.2 item 6, §2.3 doctor/uninstall, §3.5 kept-with-remedy, §3.6 ADR-0022 citation + digest/grant distinction, §8 D6 |
| W-a root_key out of the body | adopted | §3.1, §3.2 item 2 |
| W-b delete mode_policy | adopted | §3.2 item 3 (per-row control) |
| W-c collapse payload_source + honest checkout fields | adopted | §3.2 items 4–5, §3.3, §9 |
| W-d decouple the two digest reshapes | adopted | §3.6, §6 lanes |
| W-e third legacy_state reader + dead branch | adopted | §3.5, W1 files/checks |
| W-f legacy uninstall path at project scope | adopted (v1's "born receipted" claim withdrawn) | §2.3 uninstall, §3.4 new row |
| W-g vacuous ancestor check direction | adopted | §7 W2 (checkout-with-ancestor direction) |
| W-h -newer pointed at the source | adopted | §7 W3b/W4 (destination plane; target-root pin) |
| W-i D3+D4's three missing files | adopted | §6 D3+D4 row |
| N1 wrong pinning-test citation (mine) | adopted | §3.5 corrected to `:1290-1307` |
| N2 corpus 05 self-contradiction lines | adopted | §1 ledger row |
| N3 kind-mismatch pointer axis | adopted | §3.2 item 2 |
| N4 double recoverability of committed payload | adopted (stated + printed) | §3.7 |
| N5 near-vacuous duplicate-receipt check | adopted (reuse-and-tamper direction) | §2.3 install effects, §7 W3b |
| N6 second body-validator generation | adopted (named as W2 cost) | §3.2 item 8, §9 |
| N7 vacuous ledger row in §3.4 | left as-is per the note (the row states that nothing happens, which is the point of a first-contact table) | §3.4 |
| W0 completion + findings | absorbed | §6 W0, §7 W0 bullet, W3a stance + seam-case rules |

Re-review residuals (verdict RATIFY, absorbed 2026-08-25, third commit):

| Residual | Disposition | Where |
|---|---|---|
| R1 three surviving file collisions vs the disjointness claim | adopted — every collision resolved by an ordering edge, never co-ownership | §6 invariant restatement, the four new edges (D1→W2, W1→WX, WX→D3+D4, W3b→W4), and the enumerated edge list after the table |
| R2 checkout candidate_id derivation unsupported by build_release.py | adopted — digest over inventory rows plus their content_sha256 values; the false reuse claim retracted in place | §3.2 item 5 |
| R3 W0 integration point unnamed | adopted — main at `73bb1b5` (fan-in of `5b3eb16` after a three-leg CI read) | §6 W0 row |
| R4 existing-but-no-longer-git root strands its pointer | adopted — new named refusal `pointer-outlived-root` with two remedies plus a doctor row; records-only correctly limited to nonexistent roots | §2.2 item 7, §2.3, §3.4, §7 W4 |
| R5 HOSTS cited at :267 | adopted — corrected to `:268`, both occurrences | §2.1, §6 WX row |
| R6 checkout-tree version source named a file set | adopted — exactly one authoritative file: `.version-bump.json`'s `current` field; mid-bump sibling drift stays the gate's business | §3.2 item 5 |

Sequencing ruling: §6's W3a→WX edge holds; §9's stalled-WX fallback fires only on an explicit
conductor re-sequencing decision, never by default (recorded in §9).

Implementation ruling (conductor, 2026-08-25), on W2's finding 1: **delete `host` from the v2 body.**
The ratified §3.2 showed `agent` inside the `scope` union while item 7 listed `host` among the fields
carrying over from v1 — one fact in two spellings joined by a cross-field agreement check, which is
exactly the shape item 1 deletes `activation_scope` for and audit W-a deletes `root_key` for. The
ratified text carrying both was an oversight, and the exact-key-set machinery makes the correction
cheap before the schema lands and expensive after. `BODY_KEYS` (v2) therefore excludes `host`,
`BODY_KEYS_V1` keeps it frozen, the agreement refusal is deleted rather than kept, and every reader
that consumed `body.host` derives the plane from `scope.agent`. §3.2's JSONC and item 7 are corrected
above in the same change. W2's four other implementation resolutions — the not-supplied archive digest
on a checkout body, per-row `mode` nullability, `checkout.dirty` recorded `true` wherever no run
proves the tree clean, and no re-derivation of a checkout `candidate_id` at validation time — are
accepted as landed, each following this section's own logic and each recorded in the module.
