# Adversarial critique — Design B (`ccodex` as one compiled Bun 1.4 binary with the payload inside it)

**Target:** `/tmp/asdlc-research/.research-out/design-b-bun-rewrite.md` (956 lines)
**Reviewer posture:** hostile but honest. Every claim below is either **[measured]** by a command I
ran on this host, cited to `path:line` in the checkout, or marked as inference.
**Host used for verification:** macOS 26.6.1 arm64; `claude` **2.1.241**; `mise` **2026.8.12**;
checkout at HEAD `e0fbf92`, `.version-bump.json` = `0.7.4`. No `mise` task was run; the config was
left untrusted.

**One-line verdict:** REJECT as an architecture; ADOPT two of its ideas immediately, which is what
the document itself effectively concedes in §9.2.

---

## 0. What I verified myself (so the rest can be weighed)

| # | Check | Result |
|---|---|---|
| V1 | `bin/ccodex:169-187` in this checkout | **[measured]** `run_sdlc_python()` already `exec`s the pinned interpreter with `-I -B`. The defect B's whole supersession argument rests on is **already fixed in source**; only unreleased. |
| V2 | `.github/workflows/` | **[measured]** only `validate.yml`, `real-key-testing.yml`. No release workflow. Confirms B's Install-UX-step-7 claim. |
| V3 | `validate.yml` matrix | **[measured]** `mise run check` runs on `blacksmith-2vcpu-ubuntu-2404`, `blacksmith-6vcpu-macos-latest`, **`blacksmith-2vcpu-windows-2025`**. Native Windows is a *gated* platform today. |
| V4 | `mise.lock` bun pins | **[measured]** all four of B's targets are digest-pinned (`macos-arm64 c669e97f…`, `macos-x64 1d0211b8…`, `linux-x64 2d03fb5f…`, `linux-arm64 4b1a332e…`) — B's appendix understates its own evidence. **But the pin is over the `.zip`, not over the extracted `bun` binary.** |
| V5 | `assets/claude/statusline-command.sh` | **[measured]** 167 lines; resolves `jq` via `command -v jq` (line 7) from **ambient PATH**; contains **zero** occurrences of `mise`; **37** jq-process call sites. |
| V6 | `scripts/manage_claude_statusline.py:318-322` + `install_operator_tools.py:101-103` | **[measured]** `statusLine.command` is a shlex-quoted absolute path to an **owned copy** in `${XDG_BIN_HOME:-~/.local/bin}` — i.e. prune-proof by construction. |
| V7 | `plugin/` | **[measured]** symlink tree containing `output-styles -> ../output-styles` **and** `workflows -> ../workflows` (no `hooks`). |
| V8 | `claude plugin install --help` on 2.1.241 | **[measured]** `-s, --scope <scope>  Installation scope: user, project, or local (default: "user")`. Project scope — B's Phase 5, "the one genuinely new capability" — **already exists natively in the host**. |
| V9 | `claude plugin validate ./plugin --strict` | **[measured]** **exit 1** (three symlink warnings promoted to errors). `README.md:213-215` is false. Design C's correction is right; this is a build-step fix, not a plane to delete. |
| V10 | `README.md:857-866` | **[measured]** the repo's own record states the marketplace channel delivers the output style, observed as `agentic-sdlc:BLUF`. |
| V11 | Release payload size | **[measured]** `policy/release-candidate.v1.json` payload = **3.24 MiB uncompressed** (~1 MB gzipped). |
| V12 | `cosign` presence | **[measured]** not installed on this host; not a `mise.toml` pin anywhere in the repo. |
| V13 | `mise.toml:6-12` | **[measured]** `github.slsa = false`, `github.github_attestations = false` — the ADR-0002 rate-limit mitigation, applied to the *repo's* config only. |

---

## 1. The document is self-refuting as a decision, and says so

§9.2 scores **0 of 3** of ADR-0031's conjunctive revisit triggers as met, concedes facts 1–4 outright
or by topology, and states plainly: *"ADR-0032 cannot honestly be written now."* §6 Phase 1 lists
**nine** measurements of which **four** (Gatekeeper, `--asset` at scale, durability primitives,
own-path resolution) are flagged UNVERIFIED and any one of which "ends this design." §11 Q1 concedes
the operator's own platform may be unreachable for a release cycle.

So what is actually on the table for adoption today is Phases 0 and 1: a subprocess test harness and
a research report. Both are available **under ADR-0031 unchanged** — trigger 3 is the ADR's own
"worth doing on its own merits" item, and the re-measurement obligation is the ADR's own. Neither
requires this document, and neither is evidence for it. A 956-line advocacy document whose adoptable
content is a subset of the status quo's existing roadmap is not an architecture proposal; it is a
well-written research plan wearing an architecture's clothes.

That is not a rhetorical point. If this design is "adopted," the concrete near-term effect on the
repo is: build a differential-oracle harness against a Python implementation you intend to delete,
and hold every other install-architecture decision hostage to a signing experiment on unreleased
upstream code. Meanwhile the actual defects — no release workflow (V2), a released artifact no gate
exercises, six state stores, two front doors — go unfixed for another cycle.

## 2. The one fact that moved is a 20-line dispatcher bug, and B's own remedy for it is language-independent

B's entire claim to overturn ADR-0031 fact 5 is report 05's live-verified finding that `v0.7.3`/
`v0.7.4` exit 3 on every `ccodex sdlc` verb. **[V1]** That fix is already in this checkout
(`bin/ccodex:169-187`), landed and closed the same day. What shipped broken was not the language; it
was an artifact that **no gate ever executed** — because there is no release workflow **[V2]** and
because 70 of 71 test files call `module.main()` in-process.

Both causes are addressed by things B itself schedules independently of Bun: Phase 0 (the seam
harness) and Phase 4's CI release job. So the honest reading of the moved fact is: *cut releases from
CI and test the artifact through its argv seam.* B converts a release-engineering failure into a
language argument, and then claims the failure class is "structurally impossible" under a binary
(§10). It is not. The isomorphic failure under B is: ship a darwin-arm64 binary whose notarization
ticket is stale, or whose `mise` asset selection picks the wrong file (§8 below), and every verb dies
on the only artifact an operator can download — with a 90 MB re-download as the remedy instead of a
20-line patch. The structural cause ("we publish artifacts our gates do not run") survives the
rewrite intact.

## 3. `assert_self_identity()` is circular, and B calls it "strictly stronger"

§8.1 deletes `runtime_admission()` and replaces it with: on every mutating verb, re-hash the embedded
payload against the **embedded** `manifest.json`, refusing on mismatch. B asserts this is *"strictly
stronger (it covers the payload, which `runtime_admission` never checked)."*

It is strictly *weaker*, in both directions:

- **Against an adversary:** the manifest and the payload live in the same carrier section-space.
  Anyone who can rewrite the embedded payload can rewrite the embedded manifest. The check has no
  adversary it can survive.
- **Against no adversary:** it is redundant with the carrier's own sha256, which §7.5 step 2 already
  has the operator verify against a signed `SHA256SUMS`.
- **What it lost:** `runtime_admission()` verified something *external to the artifact* — that the
  interpreter executing the reviewed bytes was the exact reviewed interpreter. That is a real claim
  about the runtime environment. `assert_self_identity()` makes no claim about anything outside
  itself.

The genuinely load-bearing check in §7.3 is the *operator-driven* one: `git archive v0.9.0 | ccodex
verify --manifest -`. That is non-circular because one side comes from the tag. Keep that; delete
`assert_self_identity()`. A lazy senior engineer flags this on first read.

## 4. The four-step "review before trust" ritual requires the two things §2.2 advertises deleting

§2.2 boasts: *"Note what is absent … no `git clone`."* §7.5 then lists "exactly four things" the
operator reviews, of which:

- **Step 1** is `cosign verify-blob …`. **[V12]** `cosign` is not installed on a fresh host, is not
  pinned anywhere in this repo, and route B's literal command block (§2.2) never installs it. On a
  container with "only `curl` + `ca-certificates`" that line cannot execute. The design's own
  "exact commands a fresh operator types" section is broken at its first integrity step.
- **Step 3** is `git archive v0.9.0 | ccodex verify --manifest -` — which needs `git` **and a clone
  of the repository**. The design's payload-provenance proof is only available to an operator who
  does the exact thing §2.2 celebrates removing.
- **§2.1 (macOS, the operator's own platform)** gives no digest-verification command at all — only
  the prose "compare against the signed SHA256SUMS in the release." In a section defined as literal
  command blocks, the primary platform's integrity step is a sentence.
- On the **mise route**, integrity reduces entirely to whether a *global* `mise use -g` records and
  verifies a checksum — which B's own Q7 marks unconfirmed. So **neither route has a verified
  integrity chain**, and B concedes the curl route may be the stronger one, which is an awkward
  result for a design whose §9.1 claims ADR-0002 is "honoured, and strengthened."

Add to this the ADR-0002 blast-radius issue B does not connect **[V13]**: the `github:` backend's
unauthenticated release-API calls are *the founding incident of ADR-0002* (betterleaks, rate-limited
to hard failure), which is why this repo disables `github.slsa` and `github.github_attestations`. A
global install is governed by the **operator's** settings, not the repo's. So §7.4's "GitHub build
provenance attestation is emitted for each artifact" is decorative on the primary front door, and a
rate-limited release-API call now fails the *product's own acquisition*, not a linter's.

## 5. Violated repo invariants (each one B claims to honour)

### 5.1 The statusline binding regresses into a prunable path — violating the exact rule §4.3 cites approvingly

**[V6]** Today `statusLine.command` names an **owned copy** in `${XDG_BIN_HOME}`. §5.2 deletes that
copy: *"the statusline program becomes `ccodex statusline`, so `statusLine.command` points at the
binary."* Under `mise use -g`, that binary lives in a version-specific mise install directory. `mise
prune`, or the next `mise use -g …@0.9.1`, then leaves a dangling `statusLine.command` inside a
settings document B's own §4.4 says is read-never-written without a fresh grant.

This is precisely the failure mode the Install-UX plan's copy-activation rule exists to prevent
(*"activation must be copies because version-specific mise directories are prunable"*,
`docs/plans/…:185`) — a rule §4.3 quotes as justification for deleting `mode: "link"`. The design
deletes symlinks-into-a-prunable-tree and then writes a **path** into a prunable tree, which is the
same defect with worse diagnostics. §11 Q2 asks only whether the binary can *learn* its own path, not
whether that path is *stable across versions*. Unaddressed.

### 5.2 "Never edits PATH" becomes "no diagnostic at all"

§5.1 deletes `install_operator_tools.py` including `HostPreconditionError` — report 01's invariant
#25, a *deliberately distinct exit class* reserved for one raise site, and #26, which orders that
check before the lock because the lock is itself an effect. B counts this as a friction deletion
(§10: *"No PATH file installed"*).

But route B's own command block ends in `install -m 755 ccodex-linux-x64 ~/.local/bin/ccodex` and
then invokes `~/.local/bin/ccodex` by absolute path — because `~/.local/bin` may not be on PATH. The
precondition did not disappear; the **named refusal with a remedy** disappeared, and the failure mode
became `command not found`. Deleting a diagnostic is not deleting a problem.

### 5.3 Digest ownership is abandoned exactly where it is load-bearing

§7.3's "split digest chain" keeps `git archive` + `manifest.json` reproducible and concedes
digest-over-shipped-bytes for the carrier only. But the carrier is 95–98% of the shipped bytes and is
**the part that executes**; the payload is inert markdown and JS. ADR-0020 item 1 requires exact
verified identity for *every dependency carrying a gate, lifecycle, dispatch, render or recovery
verdict* — the carrier carries all five. So the confinement is inverted relative to the control's
purpose: reproducibility is preserved for the data and surrendered for the code.

Worse, the preserved half is **not an achievement of this design**. `build_release.py`'s `git archive`
determinism exists today and B keeps it unchanged (§5.2 "Kept unchanged and load-bearing"). So §7.3's
"mitigation" is: status quo for the inert half, control surrendered for the executing half, and one
new ADR to record the surrender. B is honest that this is "the largest unresolved objection." It is
larger than B admits, because of §5.4.

### 5.4 The "~0% unpinned" claim has two holes, one of which is unfixable on the operator's own platform

§7.2 is the strongest argument in the document — dissolve ADR-0031 fact 3 by topology (native
per-target builds, `--compile-executable-path $(mise where bun)/bin/bun`, never `--target`). Two
problems:

1. **[V4]** `mise.lock` pins the bun **`.zip`**, not the extracted executable. Phase 1 item 8 says to
   *"assert the embedded runtime's digest by extracting it from the compiled output and comparing to
   `mise.lock`."* Those are different artifacts. Worse: on darwin, Bun **ad-hoc-signs the Mach-O it
   writes** (report 03 §d / survey §2.7), so the carrier's runtime prefix is *not* byte-equal to the
   pinned bun **by construction** — the very platform whose signing is the design's decisive
   experiment is the one where the digest assertion cannot be made as written.
2. **"Never pass `--target`" is a workflow convention, not a mechanical control.** §10 concedes the
   claim is *"conditional on a CI discipline that must be enforced by a test."* No test running on the
   linux-x64 runner can prove the darwin-arm64 job did not cross-compile. In a repository whose
   ADR-0020 exists precisely because conventions get substituted, the supply-chain headline rests on
   a convention.

### 5.5 The ADR-0031 harvest boundary is inverted, silently

ADR-0031 approves *one* harvest: the settings-bypass classifier as a Bun-compiled helper **invoked by
the existing bash launcher**, under ten preconditions. §8.3 folds it into the same binary as the
write plane and frames this as an improvement: *"removes a process boundary rather than adding one."*

For a component whose entire job is to **refuse**, that is a loss, not a win. It merges the refusal
classifier's address space with the code that holds write authority over `~/.claude` and with the
self-update path. The approved shape's isolation is a feature; B removes it and does not list it as a
tradeoff anywhere in §10.

## 6. Over-engineering: what a lazy senior engineer deletes on sight

### 6.1 The differential oracle (Phases 2–3) — the largest waste in the document

Phases 2 and 3 require: byte-identical canonical `--json` from Python and TypeScript across a fixture
matrix (healthy, armed-pending, malformed, foreign, modified, racy, symlinked); byte-identical sealed
receipts modulo two fields; stdout line-for-line; and crash-injection at ~12 points where **"each
[implementation] can recover a transaction the *other* armed."**

Cross-implementation pending-slot interoperability **has no user**. §6 Phase 4 performs the cutover
*"in one commit — not behind a flag, not with a compatibility shim."* The two implementations never
coexist on any operator's machine, ever. Weeks of work to prove a property the design immediately
discards.

Byte-identical `--json` between CPython and a TypeScript runtime is a false-precision goal that will
consume its own weeks in float formatting, key ordering, unicode escaping and error-string wording —
none of which is a user-visible invariant. And the acceptance rule — *"any divergence is a bug in the
new implementation, decided in favour of Python"* — makes the target a **bug-for-bug re-typing** of
the machinery the repo's own overengineering audit ranks for deletion (~75,500 lines across five
ranked deletions, `docs/research/2026-08-22-overengineering-audit.md:21-31`).

That is the deepest structural objection to Design B: **a rewrite whose acceptance criterion is byte
fidelity to the artifact under review cannot also be the vehicle for simplifying it.** §5.3 concedes
the line delta is "modest, not dramatic"; §11 Q12 concedes it may land at 15k, i.e. lateral or worse.
Designs A and C delete the machinery; B re-types it in a new language, adds a signing obligation, a
determinism trade, an armv7 loss, and a third language for the migration period — and pays for it
with structural deletions (state stores 6→1, front doors 2→1) that **A achieves for ~−5,000 lines and
C for ~−32,000, in the languages already present.** Every one of B's countable structural wins in
§5.3 is available without Bun. Only the in-process JSON parse is not, and ADR-0031 already approved
that.

### 6.2 The one-shot legacy importer, deleted in the release that ships it

§6 Phase 4: a ~150-line Python importer reads all six old stores, writes one `state.json` plus sealed
receipts, and is *"deleted in the same release that ships it."* This is presented as principled
minimalism; it is a trap and a redundancy at once:

- **Redundant:** the target *already* refuses any other schema by name with the remedy "reinstall"
  (§6 Phase 4, quoting `install_skill_bundle.py:266-289`). If "reinstall" is an acceptable remedy,
  the importer buys nothing and should not exist. Ship zero importer.
- **A trap:** an operator on `0.7.4` who upgrades at `0.9.3` has no migration path at all, because the
  only program that could read their state was deleted three releases ago. Their remedy becomes
  hand-reconciling a home that may contain `foreign` and `modified` entries.

Pick one: refuse-and-reinstall (correct, and the repo's existing doctrine) or a supported importer
that lives as long as the schema it reads. Not both.

### 6.3 `bun:ffi` → `dlopen(libc).fcntl(fd, 51, 0)` for F_FULLFSYNC

Phase 1 item 4 proposes reaching macOS's `F_FULLFSYNC` through an FFI shim with a **hardcoded magic
command number**. CPython exposes `fcntl.F_FULLFSYNC` symbolically; the current code uses it
(`install_skill_bundle.py:507-540`) and raises `DurabilityError` and *stops the mutation* if the
barrier fails (`:452-463`).

A wrong or silently-failing constant degrades the durability barrier with no way to read back its
effective identity — the one thing ADR-0020 asks for ("read back effective identity where exposed").
This is a capability regression on the most safety-critical primitive in the system, purchased for
nothing, on the platform B most wants to certify. A lazy senior engineer refuses to hand-roll a
syscall constant to get a guarantee the incumbent language provides by name.

### 6.4 The import-graph gate replacing a run-time guard

§8.1 d.3 replaces `ccodex_sdlc_readonly.py`'s run-time trap with (a) a dependency-graph test that
*"walks `bun build --analyze` output and fails the gate on any edge"* and (b) a `ReadOnlyFs` type
boundary. So: a bespoke static-analysis gate parsing an undocumented output format of a toolchain
that ships **40–50 documented breaking changes per minor with no backport lineage** (report 03 §f).
That is a **new layer added** by a design whose thesis is deleting layers, and B concedes the
run-time guarantee is simply lost (§11 Q11 reopens whether a second process is needed — which would
reintroduce Q2's own-path problem). Type boundaries are free and worth having; the `--analyze` gate is
maintenance debt with a vendor-shaped expiry date.

### 6.5 Dead vocabulary in a design whose thesis is deleting dead vocabulary

§4.1 reserves `%LOCALAPPDATA%\agentic-sdlc\ — uncertified` for Windows, while §7.1 ships **no Windows
binary at all**. That is exactly the `selection: "absent"` / `channels` / `installed-unselected`
pattern B spends §4.3 deleting: schema vocabulary with no producer.

## 7. Internal contradictions (specific)

| # | Contradiction |
|---|---|
| C1 | **Idempotency is stated impossibly.** §4.4: a re-run over an unchanged host *"produces a receipt whose `installation_id` is **bit-identical** to the previous one,"* and *"that property is a test."* But §4.2 puts `sealed_at` **inside** the hashed body, and §6 Phase 3 explicitly excludes `sealed_at` and `source.binary_sha256` as fields that *"legitimately differ."* Also the first install records `disposition: "created"` and the second `"unchanged"`. The claimed test cannot pass as written; the real property is "identical modulo three things," which is not the property claimed. |
| C2 | **Contributor plane declared "Unchanged (Equal, deliberately)"** in §10, while §4.3 deletes `mode: "link"` *"from the model entirely,"* §5.2 rewrites `install_skill_bundle.py` into TypeScript, and §5.1 deletes the `bundle:*` tasks and `contributor:setup`'s bundle leg. **Nothing in the design names what installs a contributor's live edits into their own `~/.claude`.** The edit loop becomes compile-a-64-90 MB-binary-then-install, or nothing. (Design C solves this in one line with `claude --plugin-dir ./plugin`; B does not consider it.) |
| C3 | **"No `git clone`" (§2.2) vs. §7.5 step 3 requiring `git archive v0.9.0`** — see §4 above. |
| C4 | **§7.4 advertises GitHub provenance attestation** as an integrity control while the primary front door's attestation fetching is disabled **[V13]** and governed by the operator's global config, not the repo's. |
| C5 | **"Digest as approval" is equivocated.** In the existing code (`ccodex_sdlc_recover.py:826-853`) the approved digest is *re-derived from live local state* — a self-consistency proof. In §2.4's `update --self --to 0.9.1 --expect sha256:…`, the digest is *quoted from the vendor's release page*, over TLS, with signature verification optional because `cosign` is absent **[V12]**. Same words, different control. |
| C6 | **The statusline latency row is transplanted evidence.** §10 claims *"bash + up to 6 uncached `mise exec -- jq` spawns ≈ 130 ms."* **[V5]** The statusline script resolves `jq` from **ambient PATH** (`command -v jq`, line 7), contains **zero** references to `mise`, degrades gracefully when jq is absent, and has **37** jq-process call sites. The 130 ms / 6-spawn figure is ADR-0031's measurement of the *gateway launcher's settings gate*. The direction of B's claim is probably right and possibly understated — which is the point: the number was taken from another component, and in a tradeoff table that is how a design talks itself into a conclusion. |

## 8. Cross-platform and acquisition claims that are not established

- **The headline command is unmeasured, and it replaces a measured one.** Today's artifact — a tarball
  containing `bin/ccodex`, `mise.toml`, `mise.lock` — is **live-verified** to install through mise's
  `github:` backend (report 05 §b; ADR-0011:182-195). B replaces it with four **bare per-platform
  binaries** plus `SHA256SUMS` and `SHA256SUMS.sig` in one release, and asserts that
  `mise use -g "github:Codeseys-Labs/agentic-sdlc@0.9.0"` then yields a command spelled `ccodex`.
  Nothing in §2, §7 or §11 measures (a) which asset mise's github backend selects from a six-asset
  release, (b) whether `SHA256SUMS` (no platform token) can win the match, or (c) what the installed
  executable is *named*. **[measured]** mise 2026.8.12 exposes `github` as a backend distinct from
  `ubi`/`http`, each with different asset-selection and exe-naming semantics. Q7 asks only about
  digest pinning. **This is the same evidence failure that produced the exit-3 defect B builds its
  case on:** a distribution shape asserted rather than executed.
- **Windows is a green gated platform today, not a hypothetical.** **[V3]** `mise run check` runs on
  `blacksmith-2vcpu-windows-2025`. §10 rates Windows "Equal" on the grounds that it is "refused
  first" — true of `install_operator_tools.py` only. The bundle substrate has junction creation,
  cmd-metacharacter rejection, `LOCALAPPDATA` state selection and a documented process-crash-only
  durability claim, all currently exercised. Dropping the platform deletes real coverage; armv7 is
  conceded as an absolute, unfixable loss.
- **Native macOS-27 runners.** Phase 1 item 1 requires compiling natively on macOS 27 arm64. Hosted
  runner images lag OS releases (this host is 26.6.1). In practice the certified darwin-arm64 build
  runs on the maintainer's own laptop — a release process with a bus factor of one and no CI
  attestation, in a design whose integrity story is "cosign keyless bound to this repository's
  workflow identity."

## 9. Maintenance burden a solo maintainer inherits

Itemized, all new and all recurring:

1. **Apple Developer Program** membership, a Developer ID certificate, a `notarytool` API key held as
   a CI secret, and a rotation story. §11 Q6 concedes there is no owner and no rotation plan. A
   certificate expiry becomes a **release-blocking** event the current bash artifact cannot have.
2. **Notarization is a network dependency on Apple** in every release. Release cadence inherits
   Apple's queue latency and outages.
3. **Four native build runners** plus a separate signing job, per release. Plus a self-hosted macOS
   host for the certified target (§8 above).
4. **Bun's release model.** Report 03: no backport lineage; a defect found against `1.4.0` is fixed in
   `1.4.1`-or-later or on `main`; each minor carries a 480–570-line migration guide with ~40–50
   user-visible behavior changes. Pinning `1.4.0` means living with #39764 (macOS SIGKILL) and #32851
   (`argv[0]`) until a minor bump you must then re-qualify against four tuples.
5. **Three languages during the migration** (bash gates + Python gates/tests + TypeScript product),
   which §10 rates "Worse during migration; roughly equal after."
6. **Two bespoke gates that did not exist:** the `bun build --analyze` import-graph walker (§6.4) and
   the "never `--target`" workflow lint (§5.4).
7. **Release weight 280–340 MB** vs 120 KB, conceded.
8. **Per-operator update cost inverts B's headline.** **[V11]** the payload is 3.24 MiB uncompressed
   (~1 MB gzipped) per version today; B is 64–90 MB per version, and B *relies* on mise's
   side-by-side retention for rollback (§2.4). Three retained versions ≈ **270 MB** vs ≈ 3 MB. And the
   1.3 GB being "saved" is a **shared, one-time** mise toolchain that route A still requires mise for,
   that most mise users already largely have, and that Design A removes from the use plane by shipping
   `mise.toml` + `mise.lock` in the archive (both are in `policy/release-candidate.v1.json`'s
   `payload.files` — verified) or by shrinking the use-plane pin set from 12 to ~4. **B's biggest
   claimed operator win is available without the rewrite, and B's own claim reverses over time.**

## 10. The strategic error: deleting the one plane that makes the rest unnecessary

§5.1 deletes `.claude-plugin/marketplace.json` and the `plugin/` tree, justified as *"it silently
delivers ~60% of the payload, omitting the workflow and the output-style entirely (report 04 §d)."*

That justification is not established, and the repo contradicts part of it:

- **[V7]** `plugin/` carries `output-styles -> ../output-styles` **and** `workflows -> ../workflows`.
  The one component the plugin tree omits is `hooks`.
- **[V10]** `README.md:857-866` records the *observed* delivery of the output style as
  `agentic-sdlc:BLUF` through that exact channel.
- **[V8]** `claude plugin install --scope user|project|local` exists on 2.1.241 — the host natively
  provides the axis B builds from scratch in Phase 5 and calls *"the one genuinely new capability."*
- **[V9]** `claude plugin validate ./plugin --strict` exits 1 today because the component dirs are
  symlinks. That is a **build-step fix** (dereference the tree at release time) — the same build step
  a sha256-pinned archive needs. B correctly notes the symlink fact in its own appendix (for `bun
  --asset`) and then draws the opposite conclusion from it.

B corrected report 04 elsewhere (output-styles are in no installer code path) but adopted its
uncorrected coverage claim to delete an entire acquisition plane. **This is the only deletion in the
document that forecloses a cheaper alternative rather than enabling one.** If the native channel
covers 6 of 6 Claude component kinds with three scopes and a fail-closed vendor-verified digest, then
the 8,000–11,000 lines of TypeScript B proposes to write are being written to reimplement fetch,
verify, place, scope and inventory — five things the host already does. A lazy senior engineer runs
`claude plugin install --scope project` once before agreeing to write any of it.

## 11. What is genuinely good and MUST survive into any final plan

These three should be grafted regardless of which architecture wins. They are language-independent.

### G1 — Phase 0: the language-neutral subprocess seam harness, with its mutation test

*The single best idea in the document.* Drive `ccodex <verb>` as a **subprocess**: argv in; stdout
lines, `--json` documents, exit code, and the byte content of every receipt out. Port report 01 §C's
52 invariants and the 78 `test_install_skill_bundle.py` cases into seam assertions. Every assertion
reads **output, never a bare exit code** (the methodological rule from
`docs/research/2026-08-08-fresh-host-install-verification.md:249-260`).

The mutation test is what makes it teeth-bearing and should be adopted verbatim: **revert
`main@cd3fd3d` and the seam suite must go red on every `sdlc` verb with `runtime-admission-refused`.**
That converts the defect that shipped in both public releases from a field report into a test failure.
This closes ADR-0031's own trigger 3, has standalone value under A, B **and** C, and is the *only*
control that would have caught V1 before publication. Pair it with the release workflow that Install
UX step 7 has owed since 2026-08-14 **[V2]**; a gate that never executes the shipped artifact is not a
gate.

### G2 — The receipts-are-the-ledger / state-is-a-derived-index inversion, plus `Binding` as a first-class record

§4.1's inversion is correct and cheap: `receipts/` is the append-only ledger; `state.json` is a small,
**rebuildable** index; therefore report 05's FINDING-1 (`state.json` claiming 26 owned entries while
the activation receipt correctly says `retired`, seed `agentic-sdlc-42ec`) becomes **inexpressible**
rather than fixed. Today the relationship is inverted and the contradiction is reachable.

Two sub-ideas are as valuable and are B's own:

- **`Binding` as a distinct record type** for `settings.json` mutations, keyed by JSON pointer
  (`…/settings.json#/statusLine`) with a `bound_value_sha256`. This models the honest fact that a
  settings key is *not a file we own* — which is exactly why three separate receipt stores
  (statusline/hooks/workflows) exist today. One record type retires all three.
- **`(host, scope, root)` as the receipt key** — generalising `manage_claude_workflows.py`'s already
  worked `(workflow, destination)` key (report 01 §E.3) — is the whole project-scope mechanism, in any
  language, and is the reason project scope is nearly free.

### G3 — Convergent install, collision-visible readers, and one platform-tuple constant

Three small corrections that fix named defects and cost almost nothing:

- **Convergent install** (§4.4): an entry whose live digest already equals the payload digest gets
  `disposition: "unchanged"` instead of today's unconditional refresh
  (`install_skill_bundle.py:431-437`). Fixes "two identical installs produce two different receipts."
  (State the property honestly as "identical modulo `sealed_at` and observed host version" — see C1.)
- **`verify`/`status` report unowned collisions** in configured collections (§7.5 step 4), retiring
  report 01 §D.5 where the command named `status` *structurally cannot* see a collision and the
  operator must know to run `install --dry-run` instead.
- **One build-time `TARGET_TUPLE` / `SUPPORT_TIER` constant**, surfaced by a reader verb, replacing the
  four duplicated platform literals with two different spellings (report 05 §d.5). ADR-0027's
  no-inheritance rule becomes a data field instead of four literals someone must remember to edit.

Honourable mentions, worth carrying but not unique to B: deleting the dead scaffolding (`channels`,
read-report v2, `installed-unselected`, `selection: "absent"`) — all three designs agree; `--scope`
and `--host` explicit with no wildcard; `--dry-run` as the reviewable fourth step listing every
destination, prestate and digest.

---

## Verdict: **REJECT**

Design B is the most intellectually honest of the three proposals and the least adoptable, and those
two facts are the same fact. It concedes 0 of 3 ADR-0031 triggers met, four independent
design-killing unknowns including the operator's own platform, a net line delta it calls "modest" and
may be lateral, an absolute armv7 loss, a determinism trade requiring its own ADR, and a signing
obligation with no owner — and then asks for a decision it says cannot honestly be recorded. The one
measured fact it claims to have moved is a 20-line dispatcher bug **already fixed in this checkout**
[V1], whose real lesson is that this project publishes artifacts its gates never execute [V2] — a
release-engineering failure that recurs identically under a compiled binary, with a 90 MB
re-download as the remedy instead of a patch. Everything B wins structurally (six state stores to
one, two front doors to one, receipts-as-ledger, project scope, dead-vocabulary deletion) is
available in the languages already present, for a fifth of the effort under Design A and a fraction
under Design C; the only thing genuinely unbuyable elsewhere is the in-process JSON parse, which
ADR-0031 **already approved** as a bash-invoked helper — and B's version of that harvest is worse
than the approved one, because it merges a refusal classifier's address space with the code holding
write authority over `~/.claude`. Meanwhile the design's own review ritual needs `git`, a clone, and
an unpinned `cosign` it never installs [V12]; its headline acquisition command replaces a
live-verified artifact shape with an unmeasured one; its `assert_self_identity()` control is circular
and advertised as "strictly stronger"; its statusline binding writes a version-specific mise path
into a foreign settings document, breaking the very copy-activation rule it quotes; and its Phases
2–3 spend months proving byte-for-byte fidelity to the exact machinery this repository's own audit
ranks for deletion. Reject the architecture, decline to open ADR-0032, keep ADR-0031 intact — and
lift G1 (the subprocess seam harness with the `cd3fd3d` mutation test, plus the missing release
workflow), G2 (receipts-as-ledger with `Binding` records keyed by `(host, scope, root)`), and G3
(convergent install, collision-visible readers, one platform-tuple constant) into whichever design is
adopted, this quarter, in Python.
