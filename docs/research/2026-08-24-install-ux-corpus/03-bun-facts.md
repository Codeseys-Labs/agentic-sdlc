# Bun 1.4.x as a platform for a compiled, self-updating, payload-embedding CLI

**Scope.** This note answers (a)–(g) below with live-sourced citations (Bun docs at
bun.com/docs, bun.com/blog, GitHub oven-sh/bun issues/PRs fetched via `gh api`/`gh pr view`/`gh issue view`,
and web search for third-party prior art). It was written **after** reading the repo's own
`docs/research/2026-08-23-bun-cli-capability-survey.md` (hereafter "the survey") in full, and is
structured as a **verify/extend/correct** pass against it, not a duplicate. Facts already
established by the survey are cited by section reference rather than re-derived; new facts,
corrections, and prior art specific to self-update and cross-platform subprocess reliability
(which the survey does not cover) are the bulk of the new material here.

**As of this research (2026-08-24, one day after the survey's 2026-08-22 snapshot):** Bun
**1.4.0** remains the only released 1.4.x build — `gh api repos/oven-sh/bun/releases` shows no
`bun-v1.4.1`+ tag, and `https://registry.npmjs.org/-/package/bun/dist-tags` returns
`{"latest":"1.4.0","canary":"1.4.0-canary.20260824.1"}` — so the survey's core findings (the
open digest-pinning PR, the unreleased macOS-signing fix, etc.) are **unchanged** in their
release-status as of writing. Everything below layers on top of that baseline.

---

## (a) `bun build --compile`: cross-compile targets, and building all of them from macOS

**The 8 documented targets** (survey §2.1 already has these; confirmed unchanged against the
live docs page and the `CompileBuildOptions`/`CompileTarget` type references fetched today):

| `--target` | OS | Arch | Libc |
|---|---|---|---|
| `bun-darwin-x64` | macOS | x64 | – |
| `bun-darwin-arm64` | macOS | arm64 | – |
| `bun-linux-x64` | Linux | x64 | glibc |
| `bun-linux-arm64` | Linux | arm64 | glibc |
| `bun-linux-x64-musl` | Linux | x64 | musl |
| `bun-linux-arm64-musl` | Linux | arm64 | musl |
| `bun-windows-x64` | Windows | x64 | – |
| `bun-windows-arm64` | Windows | arm64 | – |

(https://bun.com/docs/bundler/executables, fetched 2026-08-24; matches
`docs/bundler/executables.mdx` on `main`.) `-baseline`/`-modern` suffixes are accepted for
backward compatibility and resolve to the single x64 binary — this is now also stated in
`docs/installation.mdx`: *"Bun ships a single x64 binary per platform... there is no separate
'baseline' download to choose... The `-baseline` release assets and `@oven/bun-*-x64-baseline`
npm packages are kept as aliases... for backward compatibility with older install scripts"*
(https://bun.com/docs/installation, fetched 2026-08-24) — this matches and slightly sharpens the
survey's §2.1 measured byte-identity finding.

**Can you cross-compile from macOS to all 8?** Yes, with no host-OS restriction documented or
found in source history. The feature's origin PR, **#10477** ("Support cross-compilation in
`bun build --compile`", merged into what shipped as **Bun v1.1.5**, 2024-04-26 —
https://github.com/oven-sh/bun/blob/... via https://bun.com/blog/release-notes/bun-v1.1.5) shows
examples building Linux, Windows, and macOS targets with no host-platform gating in the flag
parsing, and the release notes explicitly advertise the cross-host matrix as the point of the
feature: *"Build a macOS CLI tool on a Linux machine, or a Windows CLI tool on a Macbook Pro...
Your CI/CD pipeline can build a CLI tool for all platforms without needing to maintain multiple
build machines"* (https://bun.com/blog/release-notes/bun-v1.1.5). The only asymmetry is the one
the survey already documents (§2.10): Windows metadata flags other than `--windows-hide-console`
(icon, title, publisher, version, description, copyright) require the Windows API and so cannot
be set **when cross-compiling to Windows from any non-Windows host** — this is a target-side
restriction, not a "can't build *from* macOS" restriction; building macOS or Linux targets *from*
macOS has no analogous restriction. Historically (2023, pre-cross-compile), Jarred-Sumner
described building for macOS specifically as "harder" than Linux
(https://github.com/oven-sh/bun/issues/3473) — that comment predates #10477/1.1.5 and is now
**stale**; current docs and the merged PR show no such asymmetry survives in the shipped feature.
Ad-hoc macOS code-signing (survey §2.7) is also host-independent: the signer is Bun's own Rust
code operating on the Mach-O bytes it just wrote (`src/exe_format/macho.rs`), so a Linux or
Windows host produces an ad-hoc-signed arm64 macOS binary exactly as a macOS host would (subject
to the 1.4.0 signing regression already covered by the survey, unrelated to host OS).

**Minimum Bun version for cross-compile at all: 1.1.5** (2024-04-26). This is a concrete
build-time floor beyond what the survey states.

---

## (b) Asset embedding: `--asset`, `Bun.embeddedFiles`, limits, and `$bunfs` at runtime

The survey's §2.3/§2.4 (the `--asset` flag, `/$bunfs/` semantics, `Bun.embeddedFiles` excluding
bundled source) is accurate and is the primary source; this section adds verified limits and one
**correction-relevant nuance** about *which* embedding mechanism a limit applies to.

**Two different embedding mechanisms exist, with different failure modes:**

1. **`--asset <dir>` (new in 1.4.0, PR #36302)** — embeds a directory tree under its own path,
   read back via `node:fs`/`Bun.file()` at the embedded relative path. Confirmed unchanged from
   the survey: *"Pass `--asset` multiple times to embed several directories... Bun embeds only
   regular files; it skips symlinks and empty subdirectories inside the tree"*
   (https://bun.com/docs/bundler/executables, fetched 2026-08-24). **No documented numeric size
   limit** for this path was found in docs or issues as of 2026-08-24 (UNVERIFIED beyond
   "undocumented" — the survey already flags directory-tree limits as unmeasured; this pass adds
   no counter-evidence and no confirmation of a hard limit).

2. **The older "list files as extra bundler entrypoints" pattern** (`bun build --compile
   entry.ts ./assets/*`, pre-dating `--asset`) has a **real, silent, size-class bug**: embedding
   **8 or more** files this way makes the compiled binary **exit 0 with no output and no error** —
   filed twice independently as https://github.com/oven-sh/bun/issues/25078 (2025-11-25, exact
   repro: 7 files work, an 8th breaks it) and https://github.com/oven-sh/bun/issues/20821
   (same symptom, same threshold, includes a `strings` diff of the "OK" vs "KO" binaries showing
   the 8th asset's string table entry lands in the wrong position). **Fixed**: PR
   https://github.com/oven-sh/bun/pull/25859 ("fix(bundler): fix --compile with 8+ embedded
   files"), **merged 2026-01-06** (`gh pr view 25859` → `mergedAt: 2026-01-06T23:05:01Z`) — well
   before the 1.4.0 cut (2026-08-20), so this specific bug should not reproduce on 1.4.0. It is
   included here because it is a concrete, previously-shipped example of an **asset-count cliff
   causing silent failure**, which is the risk class to test for before trusting any embedding
   path at scale, including the newer `--asset` flag (not independently re-tested against 1.4.0
   in this pass — flagged **UNVERIFIED for 1.4.0** whether an analogous cliff exists in the
   `--asset` code path, since it is a different implementation than the one #25859 patched).

**Import-attribute embedding** (`import x from "./f" with { type: "file" }`) is the third
mechanism, unaffected by the 8-file bug (it embeds via the module graph, not the entrypoint-glob
path); survey §2.3 already covers its `--asset-naming` rewrite and `sqlite`/`.node` variants.

**`$bunfs` at runtime**: survey §2.4 is accurate (mmap from the binary's own section, not
extracted to disk, except native `.so`/`.node` dlopen targets which extract fresh per launch and
leak — survey §2.4, issue #40076). One addition: the real-world `opencode` build script
demonstrates the OS-conditional root path a build script needs when it also does the embed at
build time for worker-thread files: `bunfsRoot = item.os === "win32" ? "B:/~BUN/root/" :
"/$bunfs/root/"` (https://github.com/anomalyco/opencode/blob/57ce1b9c/packages/opencode/script/build.ts,
fetched via search 2026-08-24) — corroborating the survey's §2.4 citation of the Windows prefix
`B:\~BUN\`/`B:/~BUN/` from a second, independent real-world consumer.

---

## (c) Binary size and startup latency

No new vendor numbers exist beyond the survey's §2.5 (vendor blog table: linux-x64 77.0 MB,
Linux startup 5.1 ms vs Node's higher baseline, etc., and the survey's own **measured** spike
sizes: linux-x64 82,547,912 B / darwin-arm64 63.9 MB / darwin-x64 70.7 MB / musl 76.3 MB /
windows-x64 88.8 MB). This pass finds no contradicting or updated data (still 1.4.0-only) and
adds one independent, non-vendor confirmation of the general shape of the size floor: a
third-party blog walkthrough of shipping a personal CLI as a compiled Bun binary says plainly
*"the binary carries its own runtime... no runtime to manage"* with no separate size complaint
(https://sethdavis.tech/til/shipping-a-cli-as-a-single-bun-binary, undated, low-authority
source — cited only as color, not as a numeric data point) — consistent with, not contradicting,
the survey's ~60–90 MB floor. **No new startup-latency measurement was found or performed in this
pass; treat the survey's §2.5 vendor numbers and its measured-floor discussion as current.**

---

## (d) Code signing: macOS Gatekeeper and Windows Authenticode

Survey §2.6–§2.7 is the primary source (Authenticode stripped from PE before injection; ad-hoc
signing of `arm64` Mach-O only, `darwin-x64` unsigned by Bun; the live 1.4.0 macOS-27 SIGKILL
regression, fixed on `main` but in no release as of writing — **still true as of 2026-08-24**,
confirmed by re-checking: `gh issue view 39764` → `closedAt: 2026-08-22T01:33:41`, and no 1.4.1
release exists to carry the fix). This section adds the **why** behind the Authenticode-stripping
design and a **live-verified Windows-signing corruption history** the survey doesn't mention.

**Why Authenticode is stripped, not just "happens to be stripped":** an earlier version of Bun
did *not* strip it, and signing a compiled Windows executable **after** compiling (the only
documented order, since Bun's own signing is macOS-only) corrupted the binary — filed as
https://github.com/oven-sh/bun/issues/20109 ("Bun Single-File Executables Breaking when signed on
windows", 2025-05-31): running `signtool sign` on a `--compile` output made it stop working, with
a maintainer confirming the difference was in bytes `signtool` appended, i.e. `signtool`'s
Authenticode signature block, appended after Bun's `[u64 length][payload]` trailer (survey §2.6),
broke Bun's own offset math for finding its embedded payload. **Fixed** by
https://github.com/oven-sh/bun/pull/22960 ("feat(windows): implement authenticode stripping for
--compile"), merged 2025-09-26, shipped in **Bun v1.2.23**. The fix direction Bun chose was to
make its own writer *strip any pre-existing Authenticode section* before writing the `.bun`
section (survey §2.6's "Authenticode is stripped before injection" is this same fact, now dated
and root-caused) — meaning the safe, and only supported, order for a Windows CLI author is
**compile first, sign last**, and re-signing after any further modification to the binary risks
recreating #20109's failure mode if that modification also appends trailing bytes after Bun's
own trailer. **No 1.4-era recurrence was found** (`gh api search/issues` for
`windows signtool compile created:>2026-06-01` returned zero results as of 2026-08-24) — absence
of evidence, not proof the Rust-port regression pattern (survey §2.11) spared this path.

**Windows Gatekeeper-equivalent (SmartScreen) is a separate, non-Bun concern the CLI author must
handle regardless of what Bun does:** per Microsoft's own current guidance
(https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation,
updated 2026-05-06), an **unsigned** `.exe` triggers the "Windows protected your PC" SmartScreen
block requiring "Run anyway"; a **validly signed** (OV/EV) but new/low-download-volume `.exe`
**also** triggers a (different) SmartScreen warning until the file/publisher accumulates
download-reputation — *"EV certificates no longer bypass SmartScreen... this behavior no longer
exists"* (same source). There is **no manual whitelist mechanism** for ordinary publishers; only
Microsoft Store distribution or accumulated reputation avoids the prompt. This means signing a
Bun-compiled Windows binary is necessary-but-not-sufficient to avoid a user-facing warning on
first release — a fact independent of Bun and unaddressed by the survey. The one Bun-adjacent
real-world data point for how a Bun-compiled CLI actually gets signed for Windows in production:
`opencode`'s release pipeline signs the cross-compiled Windows artifacts via **Azure Trusted
Signing** (Microsoft's current cloud code-signing service, formerly "Trusted Signing", starting
at $9.99/mo, no hardware token) in a dedicated `sign-cli-windows` CI job that downloads the
Bun-compiled `.exe`, signs it, and verifies with `Get-AuthenticodeSignature`
(https://deepwiki.com/anomalyco/opencode/8-build-and-release,
`.github/workflows/publish.yml:120-194`, fetched 2026-08-24) — i.e. exactly the "compile on any
host, sign as a distinct later CI step" order #22960 requires.

**macOS**: survey §2.7 is unchanged and current; nothing found today alters it. The documented
`codesign --entitlements` path for JIT permission remains the only first-party guidance, and Bun
performs no notarization automation (survey's "UNKNOWN" here stands — nothing found either way).

---

## (e) Self-update patterns for compiled Bun binaries

**This entire topic is absent from the survey** — it covers `bun upgrade` only tangentially
(§3.6: no signature verification, open FR #39464). This section is new material.

### What `bun upgrade` itself does (the closest first-party analog)

`bun upgrade` "downloads and installs the latest stable version of Bun, replacing the currently
installed version" (https://bun.com/docs/guides/util/upgrade, fetched 2026-08-24) — no mention of
signature or checksum verification anywhere in the current docs (consistent with survey §3.6's
open FR #39464). Bun's own historical engineering record on **why self-replacing a running
Windows binary is hard** is directly reusable prior art:
- https://github.com/oven-sh/bun/pull/9696 (merged 2024-03-31) — Bun originally spawned a
  detached subprocess to delete the old binary after the parent exited; on Windows this created a
  visible console window that "steals user focus", so Bun's own team **removed** that behavior
  and settled for leaving the old binary on disk (best-effort, not deleted) rather than fight the
  Windows child-process-window problem, explicitly citing *"the new behavior is equal to what
  some other software does, for example `deno upgrade`"* — a maintainer-endorsed statement that
  **leaving a stale old-binary file behind on Windows is accepted practice**, not a defect to
  engineer away.
- https://github.com/oven-sh/bun/issues/27961 ("Windows `cp` panics when overwriting a running
  exe") — a **general Windows fact**, not Bun-specific: attempting to overwrite (even via `cp`,
  i.e. write-then-rename-equivalent) a currently-running `.exe`'s file hits `EBUSY`; Bun's own
  shell (`Bun.$`) originally panicked instead of surfacing this as a normal error (fixed by
  https://github.com/oven-sh/bun/pull/27963). The underlying OS behavior — **a running `.exe` on
  Windows cannot be deleted or overwritten in place** — is the reason every cross-platform
  self-update implementation below needs a Windows-specific branch.

### The general, cross-platform, ecosystem-standard pattern (Rust `self-replace` crate, the
canonical reference implementation of this exact problem outside Bun)

https://docs.rs/self-replace/latest/self_replace/ (fetched 2026-08-24) documents the mechanism in
full, and every Bun-specific implementation found below reproduces the same shape:
- **POSIX (macOS/Linux):** *"you can usually not directly write into an executable, but you can
  swap it out... For deleting, the file is just unlinked, for replacing a new file is placed
  right next to the current executable and an atomic move with `rename` is performed."* — i.e.
  the running process keeps its already-open inode; the *next* invocation of the path picks up
  the new file. This is the same mechanism ccodex-adjacent atomic-write recipes already rely on
  (survey §4.2's `O_EXCL|O_NOFOLLOW`+fsync+rename recipe) applied to the binary itself.
- **Windows:** *"when an executable launches it can be renamed, but it cannot be unlinked... we
  first move our executable aside... create a copy of our own executable first [and] open that
  copied executable with `FILE_FLAG_DELETE_ON_CLOSE`... spawn it and wait for our own shut
  down."* The crate documents three alternatives the ecosystem has tried and their downsides
  (spawning a batch file to self-delete: racy; waiting for the *new* binary to clean up the old
  one on its own next launch: leaves files lingering; `MoveFileEx(MOVEFILE_DELAY_UNTIL_REBOOT)`:
  privileged, requires a reboot to actually take effect) — there is **no clean, immediate,
  unprivileged Windows self-delete**, only workarounds with tradeoffs.

### Real, verified Bun-specific implementations of this pattern

All of the following were confirmed to exist as real repositories/code via `gh api` /
`curl -I` HTTP 200 checks against GitHub during this research pass (2026-08-24):

1. **`opencode`** (https://github.com/anomalyco/opencode) — the most mature and highest-profile
   real-world example of a Bun-`--compile`d CLI shipping a self-update command. `opencode
   upgrade [target]` (https://opencode.ai/docs/cli/, fetched 2026-08-24) does **not** do a raw
   same-process binary rename. It **detects the original install method**
   (`packages/opencode/src/installation/index.ts`, fetched via search 2026-08-24: checks
   `process.execPath` against known install paths, then shells out to `npm list -g` /
   `brew list --formula` / etc. to disambiguate) and delegates the actual replace to that
   method's own tool: `npm install -g opencode-ai@<target>`, `brew upgrade <formula>`, `choco
   upgrade opencode --version=<target> -y`, `scoop install opencode@<target>`, or — for the
   plain `curl`-installed binary case — **re-downloads and re-runs its own install shell script**
   (`https://opencode.ai/install`, piped to `bash`/`sh` with `VERSION=<target>` in the child's
   env) rather than performing an in-process rename. This is a deliberate, verified design
   choice: the running compiled binary never tries to replace itself directly; it always spawns
   a separate, purpose-built process (a package manager or an install script) to do that, sidestepping
   the Windows running-exe-lock problem entirely by construction (the package manager or install
   script handles it, using its own established convention, e.g. Chocolatey requiring an elevated
   shell — surfaced by `opencode upgrade` as *"Please run the terminal as Administrator and try
   again"* when `choco` reports the specific stderr string for that case).
2. **`upgradr`** (https://github.com/evantahler/upgradr, npm package, extracted from a real
   production bot `botholomew` — verified via a real commit hash
   `5c542d602f153530a8000351599f1858ebf3270f` and PR history) — a small, general-purpose
   self-update library for Bun/Node CLIs with **four auto-detected install methods**: `npm`/`bun`
   global install (delegate to that package manager), a **compiled release binary** ("downloaded
   + swapped in place, with `sudo` fallback"), and `local-dev` (no-op). Its documented binary-swap
   contract: download the GitHub-release asset named `<binaryName>-<os>-<arch>[.exe]`, and its
   README's CI example shows the exact `bun build --compile` → `gh release upload` pipeline a
   consuming repo needs to produce compatible artifacts.
3. Smaller, less-established but independently real (`gh api repos/<owner>/<repo>` returned 200
   with real IDs) examples of the same rename-over-self recipe, useful as **worked code**, not as
   evidence of wide adoption: `heyphat/pinestack`'s `pinerun` CLI
   (`packages/pinerun/src/upgrade.ts`) and `garrytan/gbrain`'s `src/core/binary-self-update.ts`.
   Both independently converge on the same shape: download to a **temp file in the same directory
   as the target** (same filesystem ⇒ atomic `rename`), fsync, chmod +x, run a `--version` smoke
   test on the *staged* binary before swapping, then `renameSync(staged, target)` on POSIX; on
   Windows, `renameSync(target, target + ".old")` first (moving the running exe's name aside is
   legal even though deleting it is not — matches the `self-replace` crate's model) then
   `renameSync(staged, target)`, with best-effort (non-fatal) cleanup of the `.old` file
   afterward. Every failure branch in both implementations leaves the **original** binary
   untouched — there is no half-written-binary state possible by construction, because the swap
   is a single `rename(2)`/`MoveFileExW`, never an in-place overwrite.

### Synthesis: the pattern that is actually safe to build on, cited end-to-end

1. **Never overwrite in place.** Download to a sibling temp file on the *same filesystem* as the
   target (so the final step is a single atomic rename, not a cross-device copy) —
   this is the same durability discipline the survey's §4.2 already establishes for receipts,
   now applied to the binary itself.
2. **Verify before swapping**, not after: either a checksum against a published manifest (every
   real example that publishes one — `mandu`, `gbrain`'s smoke-test pattern) or, at minimum, a
   `--version`/smoke-test execution of the staged file before it becomes the live binary. This
   mirrors the survey's own §6 harvest-checklist stance (a digest can only be checked against
   *shipped* bytes, never rebuilt) — self-update inherits the identical non-reproducibility
   constraint the survey documents for `--compile` output (survey §2.5), so **checksum-of-shipped-artifact**, not
   rebuild-and-compare, is the only verification model available here too.
3. **POSIX:** `rename(2)` over the running binary's path is safe — the running process keeps its
   already-open inode (survey's own atomic-rename discipline, §4.2, applies directly); the *next*
   launch of that path picks up the new bytes.
4. **Windows:** rename the running `.exe` aside first (`target` → `target.old.<pid>`), then move
   the new binary into `target`'s name; clean up the `.old` file best-effort (it may still be
   memory-mapped by the exiting process and fail to delete — non-fatal, matches the accepted
   practice Bun's own team settled on in #9696).
5. **Prefer delegating to the original install channel over a raw binary swap when one exists**
   (`opencode`'s design) — it pushes the OS-specific hard parts (elevation, package-manager
   locking, Windows exe-lock) onto tooling that already solved them, and is the only approach in
   this survey verified in a large, actively-maintained real CLI.

**Gap not resolved by any source found:** no example converts the survey's digest-as-approval /
sealed-receipt contract into the self-update flow itself (e.g. writing a signed receipt of *which*
binary sha256 is currently live, refusing to run if the on-disk binary doesn't match the last
recorded good digest). This would need to be built, not borrowed — **UNKNOWN / not prior art,
flagged as a genuine gap**, not something this research found solved elsewhere.

---

## (f) Maturity/risk: open `--compile` issues, breaking-change cadence, and version floors

**Open `--compile`-relevant issues**: survey §2.12's watchlist is current (spot-checked
`#39800`, `#38771`, `#39354` all still `open` via `gh issue view` on 2026-08-24). Two additions
found in this pass that belong on that watchlist:

- **https://github.com/oven-sh/bun/pull/32851** ("bun build --compile: read NODE_ENV at runtime,
  set argv[0] to the executable path") — **still OPEN, unmerged** as of 2026-08-24 (re-verified;
  survey already cites it as open in §2.4, unchanged). It fixes two real, currently-shipping
  bugs: `process.env.NODE_ENV` is frozen at the **build machine's** value inside a compiled
  binary rather than read at runtime (wrong for any target that isn't `--target=browser`), and
  `process.argv[0]` is the **literal string `"bun"`**, not a usable path, inside a compiled
  binary (`argv: ["bun", "/$bunfs/root/app"]`) — so `spawn(process.argv[0], ...)` inside a
  compiled binary that expects to re-exec itself does not work today. Partial mitigation shipped
  separately (below).
- **`BUN_OPTIONS` argv-splicing — corrected from the survey.** The survey (§2.1, §6, and the gaps
  table §5) presents this as live and unresolved: *"`BUN_OPTIONS` is read at runtime and injected
  into argv (issue #21496)... one env var can splice attacker-controlled argv from the
  environment."* **This is fixed as of Bun v1.2.23** (well before 1.4.0): PR
  https://github.com/oven-sh/bun/pull/26346 ("fix(compile): apply BUN_OPTIONS env var to
  standalone executables"), merged 2026-01-23, closes issue #21496 with `stateReason: COMPLETED`
  (`gh issue view 21496` re-checked 2026-08-24). The fix's own description: *"args from
  `BUN_OPTIONS` were incorrectly passed through to `process.argv` instead of being parsed as Bun
  runtime options (`process.execArgv`)"* — i.e. `BUN_OPTIONS` content is now consumed as Bun
  **runtime flags** (things like `--cpu-prof`) rather than leaking into the compiled app's own
  `argv`, closing the specific argv-splicing vector the survey worried about. **The residual risk
  is narrower than the survey states, but not zero**: `BUN_OPTIONS` can still alter a pinned
  compiled binary's runtime behavior via legitimate Bun CLI flags (profiling, exec-argv, etc.) —
  an ambient-environment-control surface, just not an arbitrary-argv-injection one. This is a
  **direct correction** to the survey's §2.1/§5/§6 characterization and should be flagged if this
  survey is revised: `BUN_BE_BUN=1` (full-CLI takeover) remains unaddressed and is still accurately
  described by the survey as open.

**Breaking-change cadence.** Bun does not follow strict semver in the sense of "breaking changes
only at major version bumps" — 1.4.0 itself is the clearest evidence: it is nominally a "minor"
bump from 1.3.x but ships alongside a **482–572-line dedicated migration guide**
(`docs/upgrade-to-1.4.mdx`, added by PR https://github.com/oven-sh/bun/pull/36463, refreshed by
https://github.com/oven-sh/bun/pull/39445) cataloging **~40–50 distinct user-visible behavior
changes** (lockfile version bumps, TOML strictness, JSX runtime defaults, shell glob semantics,
`fetch`/`Bun.serve` header handling, and more — the tracking issue
https://github.com/oven-sh/bun/issues/28792, "List of breaking changes for 1.4", closed
`COMPLETED` after the release, is the authoritative reconciled list). The 1.4 announcement itself
states the release "fixes over 2,900 issues" and rewrites the entire runtime from Zig to Rust
(https://bun.com/blog/bun-v1.4) — a rewrite of this scope inherently reintroduces
previously-fixed bugs, which the survey's §2.11 already documents as an observed pattern (the
mode-000 `ftruncate` regression, the macOS ad-hoc-signing regression). Historically, Bun's own
team explicitly declined strict semver on the record: *"We will do SemVer versioning once Windows
builds happen regularly... I think the Node policy of backporting fixes to older versions is
unlikely for a long time (if ever) for us though. We are a small team. Instead, we would prefer
to avoid breaking changes"* (Jarred-Sumner, https://github.com/oven-sh/bun/issues/6438,
2023 — **old**, cited only to show the team's stated policy has not changed in kind: there is
still, as of 1.4.0 in 2026, no `bun-v1.3.15` backport lineage; the fix stream lands only in the
next minor). **Practically**: expect every `1.x → 1.(x+1)` upgrade to carry a real, documented
breaking-change list on the order of dozens of items, and expect **no backported patch releases**
for the version you pin — a defect discovered against `1.4.0` gets fixed in `1.4.1`-or-later or
on `main`/canary, not in a `1.4.0`-compatible patch (consistent with the survey's own observation,
§1, that 129+ PRs merged in the 2 days after 1.4.0 shipped, none of them released).

**Minimum Bun version at BUILD time vs. zero-runtime-deps at USE time.**
- **Build time** is feature-gated and cumulative: cross-compilation at all needs **≥1.1.5**
  (https://bun.com/blog/release-notes/bun-v1.1.5); macOS codesign support needs **≥1.2.4** (survey
  §2.7, docs); `BUN_BE_BUN`/full-CLI-mode needs **≥1.2.16** (docs, survey §2.4); directory-tree
  `--asset` embedding needs **≥1.4.0** (survey §2.3, PR #36302). A build pipeline targeting the
  full feature set described in this note (cross-compile + codesign + directory assets) needs
  **Bun ≥1.4.0** at build time, full stop.
- **Use time is genuinely zero-dependency**, confirmed by the current docs' own framing, not just
  the survey's paraphrase: *"The result is a single file you can deploy anywhere without
  installing Node.js, Bun, or any dependencies"* (https://bun.com/docs/bundler/executables,
  fetched 2026-08-24) — the compiled binary embeds "a copy of the Bun runtime" (same page), so end
  users need **no Bun install of any version**. This is unambiguous and was the original design
  intent from the first cross-compile release (https://bun.com/blog/release-notes/bun-v1.1.5:
  *"Build your app on your development machine and deploy it to a different platform without
  needing to install Bun on the target machine"*).

---

## (g) Subprocess spawning from a compiled binary: git, `claude`, `uv`, cross-platform

**This is the area with the most new, concrete, and actionable findings not in the survey.**
The survey's §4.7 covers `node:child_process` compat and the general `Bun.spawn` explicit-env
measurement; it does not test spawning specifically **from inside a `--compile`'d binary**, nor
does it look at git/uv-shaped Rust-compiled targets. Findings below fill exactly that gap.

### A real, reported PATH-lookup difference specific to compiled binaries (third-party, unconfirmed by Bun)

https://github.com/garrytan/gstack/issues/931 (real repo/issue, confirmed via `gh api`,
filed 2026-04-09, still open) reports that `Bun.spawn(['bun', ...])` (bare command name, relying
on `$PATH` lookup) fails with `Executable not found in $PATH: "bun"` **only from inside a
`bun build --compile`'d binary**, on macOS Apple Silicon, even though the exact same
`Bun.spawnSync(['bun', '--version'])` call succeeds when run via the plain `bun` runtime in the
identical shell environment (`env -i ... PATH=...`) — the reporter explicitly isolated this to
"the compiled binary's PATH-lookup primitive," not a missing `bun` or misconfigured `$PATH`. The
filed, applied workaround is to **never rely on bare-name `$PATH` lookup from a compiled binary**
— resolve an absolute path at runtime instead (their patch tries `$BUN_INSTALL/bin/<name>`, then
known install locations, falling back to the bare name only as a last resort). **Important
caveat**: this is filed against a third-party project's own repo, not against `oven-sh/bun`
directly, and no Bun maintainer has triaged or root-caused it — treat as a **credible,
reproducible community report**, not a confirmed-and-tracked upstream defect. **Actionable
regardless of root cause**: for any subprocess a compiled CLI must launch reliably (git, `claude`,
`uv`), resolve an absolute path rather than depending on `$PATH` lookup inside the compiled
binary, exactly as this workaround does.

### A confirmed, root-caused, and (recently) fixed intermittent hang spawning `git` via `Bun.$`

https://github.com/oven-sh/bun/issues/26580 ("Bun Shell hangs with `git show` command, `spawnSync`
from `node:child_process` succeeds") — filed 2026-01-29 against Bun 1.3.x, and **very thoroughly
characterized** by a second reporter (2026-07-25) who reproduced it with `git ls-files` and
`git show`, ~150 KB–1 MB of captured stdout, piped (non-TTY) stdout, on Linux/WSL2:
- Occurs roughly **once per 150–200 runs** non-interactively, worse under CPU load, **never**
  observed with a TTY stdout.
- Autopsy: the child process fully exits and is reaped, its output is fully drained at the kernel
  level, yet the `await $\`...\`` promise **never resolves** — a lost-wakeup class bug in Bun
  Shell's internal event dispatch, not a subprocess-side problem.
- **Confirmed workaround, verified across 1700+ consecutive runs on the same buggy Bun version**:
  use `Bun.spawnSync` (or `Bun.spawn` + manually reading `proc.stdout`) instead of the `Bun.$`
  template-literal shell — i.e. the bug is specific to the **shell/`Bun.$`** capture path, not to
  `Bun.spawn`/`node:child_process` themselves.
- **Fixed on `main` by 2026-08-07** (`gh issue view 26580`: closed `COMPLETED`; maintainer
  `robobun` confirmed *"Using [the] minimized case... on current main we saw ten consecutive
  clean runs (about 120 iterations) with no hang"* where 1.3.9/1.3.14 reliably hung within a
  dozen iterations) — **13 days before the 1.4.0 tag** (2026-08-20), so this fix is very likely
  included in 1.4.0, though not independently re-verified byte-for-byte against the 1.4.0 release
  artifact in this pass (flagged **UNVERIFIED-for-1.4.0-specifically**, high confidence it's
  included given the timeline).
- **Actionable takeaway independent of whether the fix landed**: prefer `Bun.spawn`/
  `Bun.spawnSync` over `Bun.$` when capturing git output programmatically in a CLI that must be
  reliable — this was true on every affected version and costs nothing on a fixed one.

A related, **already-fixed** git-specific stdin bug is worth naming for completeness:
https://github.com/oven-sh/bun/issues/10080 ("stdin redirection hangs on macOS") includes a report
of exactly this CLI's shape of problem — *"I believe that I'm experiencing this for a
'git-remote-customprotocol' helper. I tried it as both a bun invocation and as a **compiled
binary**. Piping to it via `cat` works. When `git` pipes to it, it hangs on reading from stdin...
this failure is on macOS. It works perfectly well on linux."* — confirmed fixed in **Bun
1.2.16** (PR #20152), reporter confirmed working in a follow-up comment. Long since fixed,
included well before 1.4.0; cited only as evidence that macOS-specific stdin-from-git hangs are a
recurring bug *class* for Bun, now with two independent instances (this one and, differently
shaped, #26580) both eventually fixed — worth a regression test if this CLI pipes data to/from
git on macOS.

### Windows: spawning Rust-compiled native executables — an open, unresolved, directly-on-point bug

**https://github.com/oven-sh/bun/issues/32011** ("child_process cannot spawn native Windows
executables (Rust-compiled) on Windows — hangs / ETIMEDOUT") — filed 2026-06-09 against Bun
1.3.14, **still `open`, labeled only `bug`/`needs triage`** (no maintainer diagnosis found as of
2026-08-24). The reporter's repro is exact and directly on-point for this question: spawning a
**Rust-compiled `.exe`** (`uv` itself is written in Rust, making this issue's repro shape a direct
proxy for the target scenario) via `execFileSync`/`spawnSync` **hangs and then throws
`ETIMEDOUT`**; the same call **works** with `shell: true` or wrapped in `cmd /c`. This is the
single most concrete, most on-point, and **least resolved** risk found in this entire research
pass for question (g): as of 2026-08-24 there is an **open, unfixed** Bun bug that reproduces
specifically when spawning a Rust-compiled native Windows executable directly (no shell), which
is exactly `uv.exe`'s binary profile. **No evidence found that this is fixed on `main` or
scheduled** — unlike #26580 and #10080 above, this one has no closing commit, no linked PR, and
no maintainer triage comment as of writing. **Practical mitigation available today, at a cost**:
the reporter's own repro shows `shell: true` (or an explicit `cmd /c` wrapper) avoids the hang —
but wrapping in a shell reintroduces the arg-quoting and stdio-pipe risks documented immediately
below, so this is a real tradeoff, not a free fix.

**A second, independent, real-world data point about `cmd /c` wrapping specifically for `uv`/`uvx`
on Windows under Bun spawn** (https://github.com/thedotmack/claude-mem/issues/2425, confirmed real
via `gh api`, filed 2026-05-11 against a Claude Code plugin's Bun-based worker, closed after a fix
landed in that project): a worker that wrapped `uvx` in `cmd.exe /c` on Windows hit two compounding
failures — (1) `uvx` is not on `cmd.exe`'s **inherited** PATH because Astral's `uv` installer adds
`%USERPROFILE%\.local\bin` to the **User**-level PATH only, and the reporter found Bun-spawned
`cmd.exe` "does not always inherit" that; and (2) even once found, `cmd /c` "does not reliably
forward inherited stdin/stdout pipes... for long-running stdio servers" — the specific case here
was an MCP stdio server dying in 19–23 ms. The verified fix in that project was to **drop the
`cmd.exe /c` wrapper entirely and spawn `uvx.exe` directly by absolute path**, after which the
same server connected reliably. **Caveat**: this is filed against a third-party plugin, not
`oven-sh/bun`, and PATH-inheritance-only-at-User-level-not-System-level is a general Windows
environment-variable-scope fact, not necessarily a Bun-specific defect — but the compounding
interaction with a shell wrapper is a directly relevant, reproduced failure mode for exactly the
"spawn `uv`/`uvx` from a Bun-based tool on Windows" scenario this question asks about.

### Synthesis for (g)

Combining the confirmed cases above, the risk-reducing pattern that is actually evidenced by real
bug reports (not merely theorized) is:
1. **Resolve absolute paths for every subprocess target** (`git`, `claude`, `uv`/`uvx`) rather
   than relying on bare-name `$PATH` lookup — motivated independently by the gstack compiled-binary
   report and the claude-mem Windows-PATH-inheritance report.
2. **Use `Bun.spawn`/`Bun.spawnSync` over `Bun.$` for anything whose output must be reliably
   captured**, especially git — motivated by the confirmed (if apparently fixed) #26580 hang.
3. **On Windows specifically, do not assume direct (no-shell) spawning of a Rust-compiled `.exe`
   like `uv`/`uvx` is reliable as of Bun 1.3.14/1.4.0-timeframe** — issue #32011 is open,
   unresolved, and its repro shape is exactly this. Budget for either a `cmd /c`/`shell:true`
   fallback (with its own documented stdio-pipe caveats from the claude-mem case) or an explicit
   test-before-ship gate on the pinned Bun version against the actual `uv.exe`/`claude.exe`
   binaries this CLI will spawn, on real Windows (not WSL2) — this is squarely a
   CLI-contract-subprocess-test item the survey's own revisit-trigger #3 (§6) already calls for,
   and this finding sharpens *why* that trigger matters specifically for this CLI's dependency
   set.
4. `Bun.spawn`'s general contract for stdio, env, and cwd (survey §4.7's measured explicit-env
   full-replacement finding, and the documented `SpawnOptions` shape reconfirmed against
   https://bun.com/docs/runtime/child-process today) is otherwise unchanged and is the right
   primitive to build on — the risk is concentrated in **PATH resolution** and **Windows native-exe
   spawning**, not in the general spawn API surface.

---

## Corrections and additions to the survey (summary)

| Survey claim | Status after this pass |
|---|---|
| §2.1/§5/§6: `BUN_OPTIONS` "injected into argv" as a live, unresolved risk for a pinned helper | **Corrected**: fixed in Bun 1.2.23 (PR #26346, issue #21496 closed `COMPLETED` 2026-01-23) — `BUN_OPTIONS` content is now parsed as Bun runtime flags, not spliced into the app's own `argv`. `BUN_BE_BUN` remains an open, undiminished risk exactly as the survey states. |
| §2.4: PR #32851 (`argv[0]` fix) "open" | **Confirmed still open** as of 2026-08-24, unchanged. |
| §2.7: 1.4.0 macOS-27 SIGKILL regression, fixed on `main`, in no release | **Confirmed unchanged**: still no 1.4.1+ release as of 2026-08-24. |
| §3.4: digest-pinning PR #36173 open, unmerged | **Confirmed still open**, unmerged, as of 2026-08-24. |
| (not covered) cross-compile host restrictions | **New**: no macOS-host restriction found or documented; cross-compile available from any host since Bun v1.1.5 (2024-04-26). |
| (not covered) Windows Authenticode-stripping rationale | **New**: stripping exists because post-compile `signtool` signing previously corrupted the payload (#20109, fixed by #22960 in Bun v1.2.23) — "compile first, sign last" is a hard requirement, not a style choice. |
| (not covered) self-update patterns | **New section (e)** — no prior coverage in the survey at all. |
| (not covered) subprocess reliability specifically from `--compile`'d binaries, and git/Rust-exe-specific bugs | **New section (g)** — the survey's §4.7 covers `node:child_process` generally but not this. |

---

## Remaining UNVERIFIED / UNKNOWN after this pass

- Whether the `--asset` directory-embedding code path (1.4.0-new) has an asset-count or size
  cliff analogous to the fixed 8-file bug in the older glob-entrypoint embedding path — not
  retested against 1.4.0 in this pass.
- Whether https://github.com/oven-sh/bun/issues/32011 (Windows Rust-exe spawn hang) reproduces
  specifically against `uv.exe`/`claude.exe` on Bun 1.4.0 — only the reporter's minimal repro was
  examined; no independent reproduction was run in this pass (no Windows host available).
- Whether the #26580 Bun-Shell-hangs-on-git-capture fix is present in the exact 1.4.0 release
  artifact byte-for-byte (high confidence yes, given the 13-day gap between the "fixed on main"
  confirmation and the 1.4.0 tag cut, but not independently confirmed against the tag).
- No documented numeric size/count limit for `--asset` was found either confirming or denying a
  limit exists; treat as genuinely undocumented, not as "no limit."
- Whether Bun's own `bun upgrade` gained any checksum/signature verification in 1.4 specifically
  (docs show none as of 2026-08-24; the open FR, survey §3.6/https://github.com/oven-sh/bun/issues/39464,
  remains open).
