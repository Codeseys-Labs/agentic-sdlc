# Bun CLI capability survey — reference for ccodex (2026-08-22)

**Status: reference material only.** This document supports ADR-0031 (in progress), which records the
decision **NOT to rewrite ccodex in Bun**. Nothing here is a recommendation to migrate. It exists so
that if the named revisit triggers fire, a future migration author does not have to re-do the
survey from scratch.

**Consumer:** ccodex (bash launcher + Python `sdlc` namespace). Any migration must preserve these
language-independent contracts:

- exit codes: `0` ok / `1` failure / `2` usage / `3` refused-before-effect / `4` admitted-partial-or-unknown-effect
- digest-as-approval: dry-run renders a sha256; apply re-derives and refuses on mismatch
- XDG state/data layout with receipt files named `<verb>-<operation-id>-<instant>.json`
- sealed receipts hashed over canonical bytes
- symlink-based install lifecycle with refuse-to-clobber-by-digest
- refusals never print credential values
- environment-allowlist child spawn
- deterministic git-archive release artifacts verified by manifest re-hashing

**Method.** Synthesized from nine fetcher reports (releases, compile, supplychain, shell, fsio,
builtins, ffi-compat, windows, tooling) gathered 2026-08-22, **plus two on-host corpora**: the
spike workspace `/tmp/bun-cli-spike` (a small CLI built with `bun build --compile` on Bun 1.4.0,
with cross-target artifacts under `dist/`, tests under `test/`, and `bench.sh`) and the fsio
measurement scripts/logs `/tmp/fsio/t*.mjs`, `strace.log`, `s*.log`. Claims marked **[measured]**
were executed on Bun 1.4.0 (rev `34cbb9a4`), Linux x64 (WSL2, ext4), some under `strace` with
Node v26.6.0 as control; where possible each names its artifact path. **Both `/tmp` corpora are
ephemeral** — a future author should archive or re-run them (the spike scripts are small; re-run
is cheap). Nothing was run on macOS or native Windows. Every claim keeps its citation. Where
fetchers conflicted, the conflict is stated and the primary source preferred. Every unresolved
fact is marked **UNKNOWN**.

---

## 1. Executive summary

Bun **1.4.0** (published 2026-08-20T14:07:21Z, tag target `34cbb9a40b4b`) is the **only** 1.4.x
release as of 2026-08-22 — no point release exists
(https://github.com/oven-sh/bun/releases/tag/bun-v1.4.0; GitHub refs API shows exactly one
`bun-v1.4.*` tag). It is the **first release of the Zig→Rust rewrite**
(https://bun.com/blog/bun-in-rust, https://bun.com/blog/bun-v1.4), and 129 PRs merged to `main`
between 2026-08-20 and 2026-08-22 — an active fix stream, **none of it released** (GitHub search
`repo:oven-sh/bun is:pr is:merged merged:>=2026-08-20`, run 2026-08-22).

The decision recorded in ADR-0031 stands: **ccodex is not rewritten in Bun.** The facts most
load-bearing for that decision, as of this snapshot:

1. **No digest pinning for cross-compiled runtimes.** `bun build --compile --target=<other>`
   downloads the target runtime from a hardcoded `registry.npmjs.org` with **zero checksum
   verification** at the `bun-v1.4.0` tag (grep for `sha512|integrity|checksum` in
   `StandaloneModuleGraph.rs` = 0 matches). The verification PR
   (https://github.com/oven-sh/bun/pull/36173) is open, unmerged. This is directly incompatible
   with ccodex's digest-as-approval and manifest re-hashing contracts (§3).
2. **A live macOS signing regression whose fix is in no release.** 1.4.0 `--compile` output is
   SIGKILL'd before user code on macOS 27 (https://github.com/oven-sh/bun/issues/39764); the fix
   (https://github.com/oven-sh/bun/pull/39837) merged 2026-08-22 — two days **after** 1.4.0
   shipped, so no released artifact contains it (§2.7, §5).
3. **Bun-native file APIs violate the durability/atomicity ccodex receipts require** — `Bun.write`
   is non-atomic, non-durable, follows symlinks, and ignores `mode` **[measured]** (§4.2).
4. **Exit-code and signal semantics of compiled binaries are undocumented**, with observed
   silent-exit-0 (https://github.com/oven-sh/bun/issues/39787) and signal-mangling
   (https://github.com/oven-sh/bun/issues/39354) defects hostile to the 0/1/2/3/4 contract (§2.9, §4.7).

**Revisit triggers (from ADR-0031):**
- compile-target digest pinning exists;
- ccodex's post-demolition surface has been stable for one release;
- CLI-contract subprocess tests exist.

**One approved harvest:** the settings classifier as a **digest-pinned Bun helper** (a single
compiled binary whose bytes ccodex pins by sha256 at install time, exactly as it pins any other
artifact — sidestepping Bun's own missing pinning). Note the pin can only ever cover the shipped
artifact's bytes: compile output is **non-reproducible [measured, §2.5]**, so rebuild-and-compare
verification is off the table. §6 lists the exact facts to re-verify.

**Version-numbering discrepancy (unresolved):** Bun's CI internally builds
`1.4.1-canary.1+246a83ff0` (Buildkite build 103104, via
https://github.com/oven-sh/bun/issues/40037) while the npm `canary` dist-tag is
`1.4.0-canary.20260822.1` (https://registry.npmjs.org/-/package/bun/dist-tags). Which numbering is
authoritative for the next release is **UNKNOWN**.

---

## 2. Compile behavior (`bun build --compile`) — in full

Primary source for documented behavior: https://bun.com/docs/bundler/executables
(https://github.com/oven-sh/bun/blob/main/docs/bundler/executables.mdx).

### 2.1 Targets and flags

- **Targets:** `bun-{linux,darwin,windows}-{x64,arm64}` plus `bun-linux-{x64,arm64}-musl` are the
  8 documented targets (docs). At the **type level** the enum also supports freebsd (x64/aarch64,
  undocumented, npm packages exist) and `-android` libc variants; wasm is
  `is_supported() == false` ("WebAssembly is not supported. Sorry!") —
  `CompileTarget::is_supported()`,
  https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/options_types/compile_target.rs L227–239.
- **CPU baseline:** "On x64, Bun ships a single binary that targets Nehalem (SSE4.2) and selects
  AVX2/AVX-512 code paths at runtime. The `-baseline` and `-modern` target suffixes are still
  accepted for backward compatibility and resolve to the same binary" (executables.mdx L201–203;
  corroborated by https://github.com/oven-sh/bun/issues/39792, closed 2026-08-21). The URL
  builder still fetches a *distinct* `-baseline` npm package with a **different sha512** from the
  plain package (`bun-linux-x64-baseline@1.4.0` vs `bun-linux-x64@1.4.0`, registry packuments) —
  but the **contained binaries are byte-identical [measured]**: the npm-downloaded
  `bun-darwin-x64-v1.4.0` and `bun-darwin-x64-baseline-v1.4.0` runtimes in the research host's
  compile cache (`~/.bun/install/cache/`) both hash sha256
  `ca8a18d0116d7b6b19f53bb0d8c48e487c0757cab4dc3f4f8cc5e43a44cd75d8`. The docs claim of identity
  is **confirmed**; the differing tarball sha512s are packaging-level only. (The
  `bun-linux-aarch64-android-v1.4.0` runtime also downloaded successfully into the same cache
  [measured] — android works beyond the type level.) Platform floors: SSE4.2, macOS 13+,
  Windows 10 1809+; glibc minimum 2.17 since 1.3.13; musl builds published
  (https://bun.com/docs/installation).
- **Rejected with `--compile`:** `--outdir`, `--public-path`, `--target=node`, `--target=browser`
  without HTML entrypoints, `--no-bundle` (docs).
- **Other flags:** `--minify`; `--define`; `--splitting` (runtime-loaded chunks);
  `--compile-exec-argv` → `process.execArgv`; `--compile-autoload-{tsconfig,package-json}`
  (**default false**); `--compile-autoload-{dotenv,bunfig}` (**default true** — compiled binaries
  **autoload a cwd `.env` and `bunfig.toml` by default**; `bun build --help` on 1.4.0 states
  "Enable autoloading of .env files in standalone executable (default: true)" and the same for
  bunfig **[measured]**). A default-built compiled helper therefore ingests ambient env from
  whatever directory it runs in — a direct environment-allowlist violation unless built with
  `--no-compile-autoload-dotenv --no-compile-autoload-bunfig` (§6 harvest checklist). All: docs +
  `bun build --help`.
- **Ambient runtime controls over any compiled binary:** `BUN_OPTIONS` is read at runtime and
  **injected into argv** (https://github.com/oven-sh/bun/issues/21496), and `BUN_BE_BUN=1` makes
  the binary act as the full `bun` CLI (v1.2.16+, docs). For a digest-pinned helper this means
  one env var can repurpose the pinned bytes into an arbitrary runtime, and another can splice
  attacker-controlled argv from the environment. **Whether a compiled binary can disable
  `BUN_OPTIONS`/`BUN_BE_BUN` processing: UNKNOWN** (no flag or doc found; resolvable by testing
  both vars against a compiled binary on the pinned version, and by searching
  `src/runtime/cli` at the tag). Mapped to the §6 harvest checklist.
- **`--sourcemap`** embeds a zstd-compressed sourcemap, decompressed automatically on error
  (executables.mdx L309). **Open defect:** `--compile --sourcemap=inline` leaks **native** memory
  on every thrown error — RSS 19,304 KB → 149,120 KB over ~2.26M requests in 20 s, never
  plateaus; flat ~44 MB with `--sourcemap=none` (Linux x86_64, 1.4.0) —
  https://github.com/oven-sh/bun/issues/39800 (open, no fix in flight found).

### 2.2 Bytecode

- `--bytecode` moves JSC parse work to build time; `tsc` starts 2×; documented scaling: small CLI
  (<100 KB) 1.5–2×, medium-large (>5 MB) 2–4×
  (https://github.com/oven-sh/bun/blob/main/docs/bundler/bytecode.mdx). Explicitly **not
  obfuscation** and **not portable across Bun versions** — mismatched bytecode is *silently
  ignored*, falling back to parsing source (same doc).
- **New in 1.4.0:** `--bytecode --format=esm` (requires `--compile`) enables top-level await,
  `import.meta`, dynamic imports, and code splitting; previously `--bytecode` forced CJS
  (https://github.com/oven-sh/bun/pull/26402, merged 2026-01-30; https://bun.com/blog/bun-v1.4).
  Third-party measurement of the new path: 79.3 ms → 41.1 ms (1.93×) hyperfine
  (https://x.com/alistaiir/status/2017330612382929030 — a tweet, not a docs number).
- Cross-compiled `--bytecode` binaries have a history of segfaulting on the target OS —
  https://github.com/oven-sh/bun/issues/18416 (open since 2025-03-23).

### 2.3 Assets and the virtual filesystem

- **`--asset <path>`** (new in 1.4.0, https://github.com/oven-sh/bun/pull/36302, merged
  2026-07-29): repeatable; embeds a file or directory tree at `/$bunfs/root/<basename>/<relpath>`
  with original filenames (no hash rewrite); errors on collisions; refuses without `--compile`.
  "Bun embeds only regular files; it skips symlinks and empty subdirectories" (docs).
- **`/$bunfs/` semantics** (same PR): `existsSync`/`accessSync`/`statSync`/`lstatSync`/
  `readdirSync` (incl. `withFileTypes`, `recursive`) and `fs.promises.readdir` work on virtual
  dirs; `readdirSync` on an embedded file → `ENOTDIR`; `accessSync(p, W_OK)` → `EACCES`.
- Import attributes: `with { type: "file" }` → path string renamed per `--asset-naming` (default
  `[name]-[hash].[ext]`); `with { type: "sqlite", embed: "true" }` — the embedded DB "is
  read-write. Because the database is stored in memory, all changes are lost when the executable
  exits"; `.node` N-API addons embeddable (docs).
- `Bun.embeddedFiles`: `ReadonlyArray<Blob>`; "excludes bundled source code (`.ts`, `.js`, etc.)
  to help protect your application's source" (executables.mdx L909).

### 2.4 Runtime semantics

- **Virtual FS, not an unpacker.** Prefix is `/$bunfs/` on POSIX, `B:\~BUN\` / `B:/~BUN/` on
  Windows, chosen as 8 bytes for a one-instruction compare
  (https://github.com/oven-sh/bun/blob/main/src/standalone_graph/StandaloneModuleGraph.rs L51–75).
  JS modules are **mmapped from the binary's own section**, not extracted
  (https://github.com/oven-sh/bun/pull/39400).
- **What DOES hit disk:** every dlopen'd embedded native library is extracted **fresh** to
  `$TMPDIR/.<hash>-<index>.so` on each launch and **never unlinked**, even on clean exit —
  https://github.com/oven-sh/bun/issues/40076, closed **`not_planned`** 2026-08-22 (unfixed by
  decision). Real-world example: opencode's ~14 MB `libopentui.so` per launch.
- **Detection:** `Bun.isStandaloneExecutable` (https://github.com/oven-sh/bun/pull/32583; first
  shipped 1.4.0); `false` under `BUN_BE_BUN=1` (https://github.com/oven-sh/bun/pull/32606).
- **argv:** `process.argv` is `["bun", "/$bunfs/root/<name>", ...]` — argv[0] is literally the
  string `"bun"` (https://github.com/oven-sh/bun/issues/21496);
  https://github.com/oven-sh/bun/pull/32851 (open) proposes the executable path instead.
- `cc()` (TinyCC in-process compile) is **not supported** inside `bun build --compile` —
  https://github.com/oven-sh/bun/issues/24752 (open).

### 2.5 Size and startup

- Runtime sizes 1.4 vs 1.3.14 (vendor-measured, https://bun.com/blog/bun-v1.4): linux-x64 77.0 MB
  (was 88.5), linux-arm64 76.8 (87.6), windows-x64 84.8 (93.9), windows-arm64 75.1 (90.2); "macOS
  binaries are about 1 MB larger." Startup: Linux 5.1 ms vs 10.9; Windows 15.5 ms vs 39.0.
- **Size floor:** every compiled binary = full `bun` runtime + bundle.
  https://github.com/oven-sh/bun/pull/32262 (open) measures a stripped linux-x64 `bun` at
  67.13 MB and states the composition: "JSC 22.9 MB + ICU data 23.7 MB + bindings/crypto/codecs ≈
  **57 MB floor**"; a proposed `bun-standalone` reduced runtime saves 7.63 MB (−11.4%), unmerged.
- **Small-CLI compiled sizes on 1.4.0 [measured]** (the spike CLI, `/tmp/bun-cli-spike/dist/`):
  linux-x64 **82,547,912 bytes** (~78.7 MiB); cross-targets from the same source: darwin-arm64
  63,910,514, darwin-x64 70,704,544, linux-x64-musl 76,293,592, windows-x64 88,830,976 bytes.
- **Compile output is NOT deterministic [measured].** Three back-to-back `bun build --compile`
  runs of identical input (`/tmp/bun-cli-spike/dist/repro-{1,2,3}`) produced identical-size
  (82,547,912-byte) binaries with **pairwise-distinct sha256s**; `cmp` puts the first differing
  byte at offset 82,481,180 — in the embedded-graph tail, re-confirmed at patch time. Consequence
  for the digest-pinned-helper harvest: **a digest can only ever be pinned over the shipped
  artifact's bytes; rebuild-and-compare verification is impossible** (§3 contract mapping, §6).
- **Embedded-page RSS:** https://github.com/oven-sh/bun/pull/39400 measured a ~330 MB embedded
  section (~870 modules, `--bytecode`) holding **~135 MB RSS that never went away**; on macOS
  `madvise(MADV_DONTNEED)` does not drop file-backed private pages. That PR did **not** merge, and
  the revert of the ineffective madvise hint (https://github.com/oven-sh/bun/pull/37356) is still
  open — 1.4.0 retains the ineffective hint. Related:
  https://github.com/oven-sh/bun/issues/38771 (open) — any **non-ASCII** module is transcoded to a
  16-bit heap string at startup (RSS ≈ 3 bytes/char instead of 1).

### 2.6 Section layout and payload format

- ELF: `.bun` section "placed by a linker symbol in c-bindings.cpp", expanded in place
  (https://github.com/oven-sh/bun/blob/main/src/exe_format/elf.rs).
- Mach-O: `__BUN` segment / `__BUN,__bun` section with a **16 KiB placeholder**
  (https://github.com/oven-sh/bun/issues/40107).
- PE: `.bun` section; **Authenticode is stripped before injection**
  (https://github.com/oven-sh/bun/blob/main/src/exe_format/pe.rs).
- Payload: `[u64 LE length][payload]` with a 21-byte trailer at `base + 8 + length - 21`
  (https://github.com/oven-sh/bun/pull/31787 — which is itself an open PR about startup segfaults
  on corrupted embedded graphs, ~6,300 Sentry events, 1.3.5→1.3.14, Windows-dominant).
- **Native-build hazard:** a native macOS aarch64 source build (Nix, LLVM Clang 21.1.8) can emit
  segment order `… __BUN, __DATA_DIRTY, __LINKEDIT`, breaking `--compile` once input exceeds the
  16 KiB placeholder — https://github.com/oven-sh/bun/issues/40107 (open; fix in flight
  https://github.com/oven-sh/bun/pull/40109).

### 2.7 Signing (macOS) — regression and per-target behavior

- Bun ad-hoc signs **only `CPU_TYPE_ARM64`**, and only when `BUN_NO_CODESIGN_MACHO_BINARY` is
  unset — **darwin-x64 output is not signed by Bun**
  (https://github.com/oven-sh/bun/blob/main/src/exe_format/macho.rs L291, L516).
- Docs say only "Codesign support requires Bun v1.2.4 or newer"; external `codesign` with
  `--entitlements` (`com.apple.security.cs.allow-jit`) is the documented signing path
  (https://bun.com/docs/bundler/executables). **No notarization automation is documented —
  UNKNOWN.**
- **The 1.4.0 regression:** on macOS 27 (Darwin 27.0.0, beta 26A5406e/26A5416b) arm64, a 1.4.0
  hello-world binary is **SIGKILL'd (exit 137) before any user code**; the same-host 1.3.14
  artifact still runs. Both fail `codesign -v` identically ("invalid signature…",
  `flags=0x20002(adhoc,linker-signed)`); only 1.4.0 is killed. `BUN_NO_CODESIGN_MACHO_BINARY=1`
  and `codesign --remove-signature` also SIGKILL. Working workaround:
  `codesign --force --sign - ./binary` — https://github.com/oven-sh/bun/issues/39764 (dup
  https://github.com/oven-sh/bun/issues/39758), distinct from the 1.3.12 truncated-`SuperBlob`
  line (#29120/#29270/#29306, fixed by https://github.com/oven-sh/bun/pull/29272 in 1.3.13).
- **Fix state — fetchers align once dates are compared.** One fetcher marked shipped-status
  UNKNOWN; the primary evidence resolves it: fixed on `main` by
  https://github.com/oven-sh/bun/pull/39837 ("compile: fix invalid ad-hoc code signature on
  darwin-arm64", merged 2026-08-22T01:33:40Z, sha `5ceb39dd`). 1.4.0 was published 2026-08-20 and
  no later release exists, so **the fix is in no shipped artifact.** The PR names two bugs, both
  **inherited from the Zig version**: (1) `MachoSigner::sign()` hashed the final partial page
  zero-padded to 4096 bytes where Apple hashes it truncated to `codeLimit % 4096` — every signed
  output had one wrong last CodeDirectory slot; (2) `inject()` never `ftruncate`'d the Mach-O
  output, leaving a stale tail past the new smaller signature (the ELF path already truncated).
  New test `test/bundler/compile-macho-codesign.test.ts` **fails on 1.4.0**. Also closed
  long-standing https://github.com/oven-sh/bun/issues/32159.

### 2.8 `strip`

- **No Bun-side documentation or tracker issue exists** — "strip" does not appear in
  executables.mdx (verified by a fetcher). Third-party evidence: Nix `stdenv`'s automatic strip
  phase reduces a `--compile` output back to the plain `bun` binary; fix is `dontStrip` /
  `stdenvNoCC` (https://zenn.dev/gw31415/articles/81afbf1ae77189?locale=en). **First-party
  confirmation [measured]:** the stripped spike binary (`/tmp/bun-cli-spike/dist/spike-stripped`)
  still executes but prints `1.4.0` (the plain bun runtime's version) where the unstripped
  `dist/spike` prints its own `0.0.1-spike` — the payload is destroyed while the binary remains
  runnable, exactly the silent failure mode a packaging pipeline would miss. Bun's release strip
  is applied to the runtime *before* injection (https://github.com/oven-sh/bun/pull/33224).
  **UNKNOWN:** exact per-format mechanism of payload loss; whether `llvm-strip` behaves like GNU
  `strip`. (https://github.com/oven-sh/bun/issues/25051 concerns `bun i -g` shims, not `--compile`.)

### 2.9 Exit and signal behavior of compiled binaries

- **Not documented, but the basic floor holds on Linux [measured]:** the compiled spike returns
  `process.exit(n)` values faithfully — exit 0 on a clean fixture and exit 3 on a refusal fixture
  (`/tmp/bun-cli-spike/bench.sh` lines 48–49; re-run at patch time: `refuse exit=3`,
  `clean exit=0`). Known defects above that floor: an externally delivered `SIGBUS` is converted
  to `SIGILL` (wait status 132 instead of 135) with Bun's crash banner —
  https://github.com/oven-sh/bun/issues/39354 (open, 1.3.14). Historically stdout truncated at
  8192 bytes when spawned from Node `child_process` (https://github.com/oven-sh/bun/issues/28145,
  fixed 2026-03-16). Documented exit-code/flush semantics: **UNKNOWN**.
- **Crash-banner output hygiene: UNKNOWN.** Whether Bun's internal crash banner dumps argv or
  environment (which may carry credentials) is unverified — the refusals-never-print-credentials
  contract's risk surface is error *output*, not just storage. Resolvable by forcing a crash in a
  compiled binary with a sentinel credential in argv/env and grepping the banner.

### 2.10 Windows compile flags

- `--windows-hide-console` was a **silent no-op after the Rust port** until
  https://github.com/oven-sh/bun/pull/36292 (in 1.4.0), which sets `IMAGE_SUBSYSTEM_WINDOWS_GUI`
  and now works when cross-compiling. All other Windows flags (`icon`, `title`, `publisher`, …)
  "depend on Windows APIs" and cannot be used cross-compiling (docs Warning).
  `--windows-icon` embeds only the first icon of a multi-resolution `.ico`
  (https://github.com/oven-sh/bun/issues/32428, open). Whether
  https://github.com/oven-sh/bun/issues/22774 (throws on non-Windows hosts) is stale after #36292
  is **UNVERIFIED on 1.4.0**.

### 2.11 The Rust-port regression pattern (1.4.0)

- https://github.com/oven-sh/bun/issues/40111 (closed completed 2026-08-22): `--compile` fails
  `Error truncating ELF file: EACCES (ftruncate())` when the **cwd** is WSL2 DrvFS (`/mnt/c`) —
  depends on cwd, not source or output path. Fix https://github.com/oven-sh/bun/pull/40112
  ("create the temporary executable with mode 0600, not 000", merged 2026-08-22, commit
  `e5cf9e9`, **unreleased**). The PR text is the clearest statement of the fallout pattern: "The
  Zig version created the file with the same mode 000 but discarded the `ftruncate` error
  (`StandaloneModuleGraph.zig:920`). The Rust port made the error fatal, which exposed the
  mode-000 create." Expect more of this class in the unreleased fix stream.

### 2.12 Compile-relevant open-issue watchlist

| Ref | State | Summary |
|---|---|---|
| [#40107](https://github.com/oven-sh/bun/issues/40107) | open | `__DATA_DIRTY` after `__BUN` breaks `--compile` on native macOS source builds |
| [#39800](https://github.com/oven-sh/bun/issues/39800) | open | `--compile --sourcemap` unbounded native leak per thrown error |
| [#38771](https://github.com/oven-sh/bun/issues/38771) | open | non-ASCII module → 16-bit heap copy instead of mmap |
| [#37356](https://github.com/oven-sh/bun/pull/37356) | open | revert of ineffective madvise hint; #39400 replacement closed unmerged |
| [#31787](https://github.com/oven-sh/bun/pull/31787) | open | startup segfault on corrupted embedded graph (~6,300 Sentry events) |
| [#32262](https://github.com/oven-sh/bun/pull/32262) | open | `bun-standalone` reduced-footprint runtime |
| [#33316](https://github.com/oven-sh/bun/pull/33316) | open | bytecode cache for JS builtins (blocked on oven-sh/WebKit#270) |
| [#39354](https://github.com/oven-sh/bun/issues/39354) | open | SIGBUS→SIGILL in compiled binaries |
| [#39353](https://github.com/oven-sh/bun/issues/39353) | open | selective dependency externalization under `--compile` |
| [#40076](https://github.com/oven-sh/bun/issues/40076) | closed `not_planned` | TMPDIR leak of dlopen'd embedded native libs |
| [#24752](https://github.com/oven-sh/bun/issues/24752) | open | `cc()` unsupported in `--compile` |
| [#18416](https://github.com/oven-sh/bun/issues/18416) | open | cross-compiled `--bytecode` segfaults on target OS |

---

## 3. Supply chain and signing — the pinning gap

This section is the direct collision with ccodex's digest-as-approval and
manifest-re-hashing contracts.

### 3.1 How cross-compile fetches the target runtime (measured from source at tag `bun-v1.4.0`)

- Doc comment in the source: "This downloads and extracts the bun binary for the target platform /
  It uses npm to download the bun binary from the npm registry / It stores the downloaded binary
  into the bun install cache"
  (https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/options_types/compile_target.rs L3–5).
- URL template: `<registry>/@oven/bun-{os}-{arch}{libc}{baseline}/-/bun-…-{version}.tgz`; the
  registry is the **hardcoded literal** `https://registry.npmjs.org` (compile_target.rs L123,
  L126–175). `bunfig.toml` / `.npmrc` registry settings are **not honored** (source; independently
  corroborated by https://github.com/oven-sh/bun/issues/25713, open since 2025-12-27).
- Package `arch` is `aarch64`, not `arm64` (`Architecture::npm_name()`,
  https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/bun_core/env.rs L181–190; live check:
  `@oven/bun-darwin-aarch64` → 200, `@oven/bun-darwin-arm64` → 404).
- Only override: env var `BUN_COMPILE_TARGET_TARBALL_URL`, accepted verbatim if it starts with
  `http://` or `https://` (compile_target.rs L115–121). **Not in the public env-var docs**
  (https://bun.com/docs/runtime/env).
- Cache: `<fetch-cache-dir>/<target-display-string>` (e.g. `bun-linux-x64-v1.4.0`); cache dir
  resolution order `BUN_INSTALL_CACHE_DIR` → bunfig `install.cache.dir` → `$BUN_INSTALL/install/cache/`
  → `$XDG_CACHE_HOME/.bun/install/cache/` → `$HOME/.bun/install/cache/` → `node_modules/.bun-cache`
  (https://github.com/oven-sh/bun/blob/main/src/install/PackageManager/PackageManagerDirectories.rs
  L379–419). **Caveat:** the compile path calls a no-arg `fetch_cache_directory_path()` whose
  comment says the full env-override chain lives elsewhere — whether every override reaches the
  compile path is **UNKNOWN** (PR #36173's repro uses `BUN_INSTALL_CACHE_DIR`, implying that one works).
- Download flow: single `AsyncHTTP` GET, follow redirects, accept only HTTP 200 → gunzip →
  libarchive extract to a random tmpdir → `move_file_z` into the cache
  (https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/standalone_graph/StandaloneModuleGraph.rs).

### 3.2 Checksum verification: NONE in 1.4.0

- **Measured, not inferred:** at tag `bun-v1.4.0`, `StandaloneModuleGraph.rs` contains **zero**
  matches for `sha512|integrity|checksum|dist.integrity`. Failure modes are only HTTP status,
  empty body, gunzip failure, extract failure.
- The registry **publishes digests that go unused**: `@oven/bun-linux-x64@1.4.0` has
  `dist.integrity` and `shasum` (https://registry.npmjs.org/@oven/bun-linux-x64/1.4.0). Bun
  fetches the tarball URL directly, skipping the packument, so it never sees them.
- **TLS is the whole trust story, and it can be switched off with no digest backstop:**
  `reject_unauthorized` follows `NODE_TLS_REJECT_UNAUTHORIZED=0`
  (https://github.com/oven-sh/bun/blob/main/src/dotenv/env_loader.rs L315–323); `HTTP_PROXY` is
  honored. A MITM can substitute the target runtime undetected.

### 3.3 What pins the digest: nothing

- `bun.lock`: **no** — compile runtimes are not project dependencies and get no lockfile entry.
- `package.json`: **no** documented or source-visible field.
- `--target=bun-linux-x64-vX.Y.Z` pins the **version string only**, never bytes; this form is
  itself **undocumented** (compile_target.rs `try_from` L280–296 vs
  https://bun.com/docs/bundler/executables). Worse, malformed version tokens fail silently:
  `-v1.2.3.4.5` builds from the *running* bun with no download, exit 0; `-v1.99999999999999999999.7`
  downloads **1.0.7** (https://github.com/oven-sh/bun/pull/37389, open).
- **The only supply-chain-tight option today:** `--compile-executable-path <path>` / JS
  `executablePath` — "Path to a Bun executable to use for cross-compilation instead of
  downloading" (`src/runtime/cli/Arguments.rs` L440; https://bun.com/docs/bundler/executables).
  Bring-your-own, out-of-band-verified binary; bypasses the network entirely.

### 3.4 The verification PR — the revisit-trigger fact

- https://github.com/oven-sh/bun/pull/36173 — "compile: verify the downloaded target executable
  against the registry integrity" (Jarred-Sumner, opened 2026-07-28, **still OPEN, not merged,
  not draft** as of 2026-08-22). It would check the tarball against `dist.integrity` (fallback
  `dist.shasum`) **before** extraction, fail with a named error leaving the cache empty, honor
  `BUN_CONFIG_REGISTRY`, and deliberately leave `BUN_COMPILE_TARGET_TARBALL_URL` unverified.
  **This is a promise, not shipped behavior.** Note: even merged, it is registry-integrity
  (trust-npm), not a local digest pin; a ccodex-grade pin would still be the caller's job.
- No issue or PR proposes a **lockfile/config digest pin** for compile runtimes (fetcher search).
  Provenance: https://github.com/oven-sh/bun/issues/15601 (`bun publish --provenance`, open since
  2024-12-05) is unrelated to compile downloads; no provenance story for `@oven/bun-*` either.

### 3.5 Lockfile integrity in 1.4 — real, but it does not reach compile runtimes

- Blog, verbatim: "`bun.lock` now records a SHA-512 hash for GitHub and tarball dependencies, the
  same way it always has for npm packages" (https://bun.com/blog/bun-v1.4). Confirmed in
  `src/install/lockfile/bun.lock.rs` (https://github.com/oven-sh/bun/blob/main/src/install/lockfile/bun.lock.rs);
  integrity remains optional for tarball/git deps (malformed values warned and dropped, not fatal).
- Two independent walls keep this away from compile targets: (a) `@oven/bun-*` tarballs are never
  lockfile entries; (b) the compile download path shares no code with `Integrity` at the 1.4.0
  tag (grep = 0). PR #36173 exists precisely to bridge that — proof by construction it cannot today.
- **Do not cite a PR number for the lockfile change** — a doc extraction returned two mutually
  inconsistent links (#25090 is verifiably an unrelated fetch-proxy PR). Backing PR: **UNKNOWN**;
  the blog text and source are the evidence.
- Whether `bun install` **enforces** (vs merely records) the GitHub-dep sha512 on later installs:
  **partially UNKNOWN** (fetcher did not trace the verify call).

### 3.6 Signing of Bun's own distribution

- `bun upgrade` performs **no signature verification of the upgrade payload**; a self-sufficient
  binary trust chain is an open feature request (https://github.com/oven-sh/bun/issues/39464).
- Release assets are plain zips on GitHub (verified via release-assets API); PE Authenticode is
  *stripped* from compiled outputs (§2.6); macOS ad-hoc signing state is §2.7.
- Installer channels and how to pin: install script (`bash -s "bun-vX.Y.Z"`), npm, Homebrew
  (vendor tap + homebrew-core both at 1.4.0), Scoop (1.4.0), winget (`Oven-sh.Bun` 1.4.0 —
  undocumented by Bun but real, https://github.com/microsoft/winget-pkgs/tree/HEAD/manifests/o/Oven-sh/Bun),
  Docker `oven/bun`, mise core plugin (with the documented caveat "Avoid using `bun upgrade` …
  as mise will not be aware of the change", https://mise.jdx.dev/lang/bun.html),
  `oven-sh/setup-bun@v2` (reads `packageManager`, then `engines.bun`, then `latest`).
  Chocolatey: **UNKNOWN**. (All: https://bun.com/docs/installation and per-channel links above.)
- ARM64 ecosystem hazard: `oven-sh/setup-bun` hardcodes ARM64→x64 fallback
  (https://github.com/oven-sh/setup-bun/issues/164); mise downloads `bun-windows-x64.zip` on
  ARM64 → `STATUS_ILLEGAL_INSTRUCTION` (https://github.com/jdx/mise/discussions/7155).

**Contract mapping.** ccodex's digest-as-approval and deterministic-artifact contracts cannot be
delegated to Bun's compile pipeline in 1.4.0: nothing between `registry.npmjs.org` and the output
binary is digest-checked, and the output embeds a runtime ccodex never hashed. The approved
harvest shape (settings classifier) survives only because ccodex pins the *helper binary's* sha256
itself — build with `--compile-executable-path` against an out-of-band-verified runtime, record
the output digest in the manifest, refuse on mismatch at install and at launch. One more hard
limit on that shape: **compile output is not reproducible [measured, §2.5]** — identical inputs
produce byte-distinct binaries — so the deterministic-release-artifact contract can only be
satisfied by hashing the one shipped artifact, never by rebuild-and-compare; manifest re-hashing
verifies the bytes you shipped, not the build.

---

## 4. Per-capability sections

### 4.1 Shell (`Bun.$`)

- In-process bash re-implementation; **does not invoke `/bin/sh`**
  (https://bun.com/docs/runtime/shell, "Security in the Bun shell"). Grammar is one AST enum:
  `Assign`, `Binary` (`&&`/`||`), `Pipeline`, `Cmd`, `Subshell`, `If`, `CondExpr`, `Async`
  (https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/shell_parser/parse.rs L76–89).
- **Injection model (source-verified):** interpolated JS values are spliced as `\x08__bunstr_N`
  refs with recorded byte ranges so "the parser must not reinterpret them (e.g. an `=` inside one
  must not create an env assignment)" (parse.rs L2143–2149, L2217–2220); values are double-quoted
  with `` $`"\ `` backslash-escaped (parse.rs L3956, `escape_8bit` L3979–4010). Arrays interpolate
  as separate escaped words; `${undefined}` becomes the literal text `undefined`
  (https://github.com/oven-sh/bun/blob/bun-v1.4.0/test/js/bun/shell/bunshell.test.ts L113–135).
  Documented non-guarantees: handing to `bash -c` voids protection; **argument injection**
  (`--upload-pack=…`) is the caller's problem (docs, "Security considerations").
- **Missing vs bash:** no job control, traps, `set -e`/`pipefail`, functions, loops, `case`,
  arrays, arithmetic, heredocs, process substitution (absent from AST + builtin registry; open
  requests https://github.com/oven-sh/bun/issues/11805, /10465, /20025). Subshells yes (depth 128),
  `if`/`[[ ]]` yes, background `&` yes (parse.rs).
- **Builtins:** 19 in the 1.4.0 registry (`true false pwd exit basename dirname cd echo export cat
  mv rm which ls mkdir touch cp seq yes`,
  https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/runtime/shell/Builtin.rs L170–198). **The
  docs list is wrong three ways** (omits `export`/`cp`, lists `bun` which is PATH-resolved, not a
  builtin) — prefer source (Cmd.rs L474–495) over https://bun.com/docs/runtime/shell. On POSIX,
  `cat`/`cp` delegate to system binaries unless `BUN_ENABLE_EXPERIMENTAL_SHELL_BUILTINS` is set.
- **1.4 breaking changes:** only glob tokens written literally in the template expand — `?` and
  `[...]` are literal everywhere; interpolated `**/*` now fails `no matches found`
  (https://bun.com/blog/bun-v1.4; https://github.com/oven-sh/bun/pull/31220). Multi-word redirect
  targets rejected (https://github.com/oven-sh/bun/pull/34324). **Docs gap:** the shell docs
  still advertise globs with no mention of the restriction — prefer the blog/PR.
- **Live correctness bug for env handling:** prefix assignment (`FOO=x cmd`) of an *existing* var
  duplicates the environ entry and the child sees the **old** value —
  https://github.com/oven-sh/bun/issues/32202 (open).
- Windows: BatBadBut fail-closed guard — `.bat`/`.cmd` targets with cmd.exe metacharacters in any
  arg are refused by name (Cmd.rs L498–521; whether this predates 1.4: **UNKNOWN**). `Bun.$`
  broken on Windows inside compiled executables — https://github.com/oven-sh/bun/issues/23924 (open).
- Output is buffered and re-echoed, not fd-inherited (shell.d.ts L112); no stdio-inherit/TTY
  passthrough (https://github.com/oven-sh/bun/issues/37233, /33234). Shell performance in 1.4:
  **UNKNOWN** (no published benchmark).
- **Error-output credential hygiene: UNKNOWN.** Whether a thrown `ShellError`'s `message`/stack
  echoes the interpolated command line (which may carry a credential) is unverified — the
  refusals-never-print-credentials contract is about output, and no doc or fetcher measurement
  covers what `ShellError` prints. Resolvable by a unit test: interpolate a sentinel secret, force
  a non-zero exit, assert the sentinel is absent from `message`, `stack`, and default logging.

**What this buys ccodex:** a structurally injection-safe replacement for the bash launcher's
subprocess strings — but the environment-allowlist contract must use `.env(obj)` (a full
replacement map), never `FOO=x` prefixes (#32202), and the missing `set -e`/`pipefail`/trap
semantics mean the exit-code ladder (0/1/2/3/4) has to be enforced in JS, not shell.

### 4.2 fs/io

- **The atomic-receipt recipe works on Linux [measured]:**
  `openSync(tmp, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600)` → `writeSync` → `fsyncSync(fd)` →
  `renameSync` → `openSync(dir, O_RDONLY|O_DIRECTORY)` → `fsyncSync(dirfd)` all succeed
  (strace-verified on 1.4.0 linux x64; scripts and logs at `/tmp/fsio/t*.mjs`, `strace.log`,
  `s*.log` — ephemeral, archive or re-run; the surviving logs show e.g. the O_EXCL refusal
  `openat(... O_WRONLY|O_CREAT|O_EXCL ...) = -1 EEXIST` in `s7.log`).
- **Directory modes: UNKNOWN.** Whether `mkdirSync` respects `{mode}`/umask, and whether the
  recipe's explicit `0o600` was confirmed at the syscall (the surviving strace lines show the
  default `0666` case, not the explicit-mode case), are unverified — live questions given that
  `Bun.write` demonstrably ignores `{mode}` (below) and receipt state dirs are typically `0700`.
  Resolvable by strace'ing `mkdirSync(p, {mode:0o700})` and `openSync(p, 'wx', 0o600)` on the
  pinned Bun.
- **POSIX symlink lifecycle primitives — partially measured.** `readlinkSync`,
  `lstatSync().isSymbolicLink()`, and `realpathSync` behave correctly; `renameSync` onto an
  existing symlink replaces the *link* (verified not-a-symlink afterwards); and
  `O_CREAT|O_EXCL|O_NOFOLLOW` refuses a symlink squatting the temp name with `EEXIST` **without
  creating the link's target** [measured, fsio corpus]. **Still UNKNOWN:** whether `fs.symlink`
  itself refuses an existing destination with `EEXIST` (refuse-to-clobber on link *creation*) and
  whether atomic symlink replacement (symlink-to-temp then rename-over) works — both resolvable
  by a five-line test on the pinned Bun; the install lifecycle should not assume them untested.
- `fsync` is plain `fsync(2)` on all non-Windows targets — **no `F_FULLFSYNC` on macOS**, and no
  Bun API reaches it (**UNKNOWN** if any path exists; no `fcntl` binding found) —
  https://github.com/oven-sh/bun/blob/main/src/runtime/node/node_fs.rs.
- **Windows degradations:** `rename` is `MoveFileExW(MOVEFILE_REPLACE_EXISTING)` via libuv — no
  atomicity claim, no `MOVEFILE_WRITE_THROUGH` (https://github.com/libuv/libuv/blob/v1.x/src/win/fs.c;
  https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw). `O_NOFOLLOW`
  is `#define`d to **0** in libuv's Windows header — open-time symlink refusal is **silently a
  no-op** (https://github.com/libuv/libuv/blob/v1.x/include/uv/win.h). Whether `FlushFileBuffers`
  succeeds on a directory handle: **UNKNOWN (untested)** — treat parent-fsync as unavailable.
  Bun's *own installer* uses `FILE_RENAME_POSIX_SEMANTICS` internally, but `node:fs.rename` does
  not (https://github.com/oven-sh/bun/blob/main/src/sys/windows/mod.rs).
- **`Bun.write` is not atomic, not durable [measured, strace]:** `openat(O_WRONLY|O_CREAT)` →
  `write` → `ftruncate` → `close`; zero fsync, no rename, no `O_EXCL`/`O_NOFOLLOW`/`O_TRUNC`;
  **follows a symlink at the destination**; **ignores `{mode:0o600}`** (produced 0644). Docs are
  silent on all of this (https://bun.com/docs/api/file-io).
- **FileSink silently fails to truncate [measured]:** overwriting a 20-byte file with `"BBB"`
  yields `"BBBAAAAAAAAAAAAAAAAA"`; `.flush()` is a `write(2)`, not fsync (same fetcher run; docs
  claim "flush the buffer to disk").
- **Durable one-shot that works [measured]:** `fs.writeFileSync(p, d, {flush:true})` emits a real
  fsync. But `{flush:true}` is **ignored on the append path** (Node control emits fsync; Bun does
  not) — https://github.com/oven-sh/bun/issues/34914, /34915, both closed **`not_planned`**.
  `fh.sync()` does emit fsync [measured].
- Linux has internal `openat2(RESOLVE_BENEATH)` used for static routes, **not exposed to JS**
  (https://github.com/oven-sh/bun/blob/main/src/sys/lib.rs; https://bun.com/1.4).
- `birthtime` is 0 on Linux filesystems without `STATX_BTIME` (DrvFS, /proc) and degrades
  silently [measured] (https://github.com/oven-sh/bun/blob/main/src/sys/PosixStat.rs).
- `fs.symlink` supports `"junction"` on Windows ("only junctions can be created by non-admin";
  UNC targets skip the junction fallback) — node_fs.rs. Whether Node's vendored junction tests are
  skipped anywhere: **UNKNOWN**.
- `fs.watch {recursive:true}` sees new subtrees [measured]; per-watcher registration cost is
  super-linear (5000 watchers: 74 s vs Node 58 ms, https://github.com/oven-sh/bun/issues/34160).
- Doc status "🟢 98% of Node's fs suite passes" (https://bun.com/docs/runtime/nodejs-apis)
  **conflicts** with the measured divergences above — prefer the measurements; treat the page as
  marketing, not a compat matrix.

**What this buys ccodex:** sealed receipts and refuse-to-clobber are implementable, but **only**
through the `node:fs` recipe (`O_EXCL|O_NOFOLLOW` + fsync + rename + dir-fsync) — never
`Bun.write`, never FileSink, never `appendFile({flush:true})`. On Windows the symlink-refusal and
parent-fsync legs of the contract silently vanish (exactly why ccodex's Windows lifecycle already
fails closed).

### 4.3 SQLite (`bun:sqlite`)

- Most mature Bun-native API; vendor claim "3-6x faster than better-sqlite3" is contested
  (https://github.com/oven-sh/bun/issues/4776, /20662). WAL not default; docs recommend
  `PRAGMA journal_mode = WAL` (https://bun.com/docs/runtime/sqlite). Default `busy_timeout` and
  multi-process guidance: **UNKNOWN**.
- **Receipt-integrity trap 1 (confirmed on 1.4.0):** default named-parameter binding **silently
  binds NULL** for a bare (`p1`) or wrong (`nope`) key — wrong rows, no error; `node:sqlite` and
  `better-sqlite3` throw. Mitigation: `strict: true` —
  https://github.com/oven-sh/bun/issues/39877 (open, filed 2026-08-21 against 1.4.0).
- **Trap 2:** default integers round beyond 53 bits; `safeIntegers: true` returns `bigint` and
  validates 64-bit range (https://bun.com/docs/runtime/sqlite).
- No async API (https://github.com/oven-sh/bun/issues/978), no SQLCipher (/11397), no
  `sqlite3_interrupt` (/31014); Windows long paths fail with `LongPathsEnabled=0` (/33336);
  adjacent `node:sqlite` `close()` leaves the file locked (EBUSY) on Windows after prepare
  (https://github.com/oven-sh/bun/issues/40001, open).

**What this buys ccodex:** nothing the JSON-receipt XDG layout needs — and the silent-NULL default
is precisely the wrong-row failure a digest-as-approval flow cannot tolerate. If ever used for a
receipt index, `strict: true` + `safeIntegers: true` + WAL + explicit `close(true)` are mandatory,
per the docs' own knobs.

### 4.4 Secrets (`Bun.secrets`)

- `get`/`set`/`delete` keyed by `{service, name}`; macOS Keychain, Linux libsecret, Windows
  Credential Manager; **doc-labeled experimental** ("This API is new and experimental. It may
  change") — https://bun.com/docs/runtime/secrets. Introduced 1.2.21
  (https://bun.com/blog/bun-v1.2.21, https://github.com/oven-sh/bun/pull/21973). What 1.4 changed:
  **UNKNOWN** (no 1.4 blog section).
- Threat model is thin: "secrets are accessible by any bun script without password prompt"
  (https://github.com/oven-sh/bun/issues/28071, open) — at-rest protection only, not
  inter-process. Windows values come back with "a null byte after every character"
  (https://github.com/oven-sh/bun/issues/24135, open). No enumerate/list API. Headless/CI
  behavior (Linux secret-service daemon absent): **UNKNOWN, undocumented**.

**What this buys ccodex:** OS-keychain storage would keep credential *values* out of files, which
composes with the refusals-never-print-credentials contract — but the Windows null-byte bug and
undocumented headless behavior mean it cannot yet replace the current env-var/credential-file
handling, and it adds a same-user read surface (#28071) ccodex does not have today.

### 4.5 Hashing (`Bun.CryptoHasher` / `Bun.password` / `Bun.hash`)

- `Bun.CryptoHasher`: 19 algorithms incl. sha256/sha512/sha3/blake2; streaming `.update()`,
  `.digest()` to hex/base64/TypedArray, `.copy()`; HMAC via key arg (14 algorithms), with the
  documented footgun that an HMAC hasher **does not reset after `.digest()`** —
  https://bun.com/docs/runtime/hashing.
- `Bun.password`: argon2id default (memoryCost 65536 KiB, timeCost 2); bcrypt default cost **4**
  (documented; too low — set explicitly); >72-byte passwords SHA-512 pre-hashed (same page).
- **sha256 throughput: UNKNOWN — no official number exists** (checked docs + 1.4 blog). The only
  measurement is third-party and older: ~2.6 GB/s (Apple M2) with Bun "essentially identical to
  Node.js 23" (https://lemire.me/blog/2025/01/11/javascript-hashing-speed-comparison-md5-versus-sha-256,
  predates 1.3/1.4). Do not attribute a speed advantage without re-measuring.
- Non-crypto `Bun.hash` (wyhash, xxHash, …) has no streaming variant
  (https://github.com/oven-sh/bun/issues/19574, open).

**What this buys ccodex:** the digest-as-approval and manifest re-hashing legs are fully served —
streaming sha256 over canonical receipt bytes is a two-line `CryptoHasher` loop, and this is the
core primitive the approved settings-classifier harvest needs. No performance claim should be made
without measurement (UNKNOWN above).

### 4.6 FFI (`bun:ffi`)

- 1.4 reimplements `dlopen`/`linkSymbols`/`CFunction`/`JSCallback` on JavaScriptCore's native FFI;
  TinyCC survives only for `cc()` (https://bun.com/docs/runtime/ffi;
  https://github.com/oven-sh/bun/pull/35246, merged 2026-07-29; measured noop call 2.13 ns → 0.70 ns).
- **Four breaking changes** in 1.4, one load-bearing: "`dlopen()` and the other entry points throw
  `TypeError` when the JIT is disabled" — FFI is now JIT-*dependent*
  (https://bun.com/blog/bun-v1.4). Whether that affects `--compile` binaries or any JIT-off flag:
  **UNKNOWN** (the note names no flag).
- **Stability: none guaranteed.** Verbatim: "`bun:ffi` is experimental… Do not rely on it in
  production… A future version of Bun may add a CLI flag to disable `bun:ffi`" (docs).
- **No struct support** (zero occurrences of "struct" in the 595-line ffi.mdx, grep-verified);
  the documented aggregate pattern is pointer + TypedArray + `read.*` at hand-computed offsets.
  Struct-by-value through `JSCallback` is wrong on ARM64 (HFA not honored) —
  https://github.com/oven-sh/bun/issues/31862 (open).
- **No variadic functions** (https://github.com/oven-sh/bun/issues/12389, open) — so no raw
  `syscall(2)` fallback; `statx`/`renameat2` are reachable only via their non-variadic glibc
  wrappers (glibc 2.28+; whether a given target exports them is not a Bun fact).
- Pointers are JS numbers (52/53-bit); Windows `HANDLE` must be `u64`, not `ptr` (docs).
  `cc()` unsupported under `--compile` (https://github.com/oven-sh/bun/issues/24752).

**What this buys ccodex:** in principle, direct `renameat2(RENAME_NOREPLACE)`/`statx` for the
refuse-to-clobber lifecycle — but an experimental, JIT-dependent, maybe-disableable API is the
wrong foundation for a trust-boundary install path. The honest reading: FFI buys ccodex nothing
it should accept.

### 4.7 Node-compat (the CLI-port surface)

- Blog: "+1,517 tests from the Node.js test suite" (v26.3.0 suite) — https://bun.com/blog/bun-v1.4.
  Per-module deltas (extracted by a fetcher from the blog page's own HTML `title` tooltip
  attributes, format `"node:X — Bun 1.3: A → Bun 1.4: B of N tests (+D)"`, same URL) show the
  gains went to quic/http/fs/tls/http2; **`os`, `path`, `tty`, `readline` have no delta row** —
  the surface a CLI port cares most about got the least new coverage. `child_process` is 105/116
  (91%); the 11 failing tests' identity: **UNKNOWN**.
- **child_process gaps (documented, https://bun.com/docs/runtime/nodejs-compat):** no `http`
  server socket handles over IPC; `serialization:"advanced"` Bun↔Bun only; missing
  `subprocess.channel.ref()/unref()`; can't chain one child's stdout as another's stdio;
  `spawnSync` returns no extra stdio pipes.
- 1.4 fixes relevant to spawn hygiene: `uid`/`gid` honored (setgroups→setgid→setuid, EPERM
  synchronous); `maxBuffer` bounded overshoot ≤64 KB; `stdio:'ignore'` at fd≥3 leaves the fd
  closed "matching Node.js"; piped stdio gets kernel backpressure; `spawnSync` drains to EOF
  (all https://bun.com/blog/bun-v1.4).
- **The load-bearing half of the environment-allowlist contract is empirically pinned
  [measured]:** `Bun.spawn` with an **explicit `env` object is a full replacement map** — an
  end-to-end test spawned `/usr/bin/env` as a real child and asserted the allowlisted var present
  and the secret vars (`SECRET_LEAK`, `ANTHROPIC_API_KEY`) absent from the child's own output
  (`/tmp/bun-cli-spike/test/spike.test.ts`, "the CHILD ITSELF confirms the allowlist"); a
  metacharacter-laden argument (`$(touch …); rm -rf /; \`id\``) **passes literally with no
  shell** (same file, verified the side-effect file was never created). Note this measures
  `Bun.spawn`, Bun's native spawn API — the rest of this section is `node:child_process` compat.
  **Still UNKNOWN:** default env inheritance when *no* `env` option is supplied, and Bun's
  Windows argv quoting (`windowsVerbatimArguments` is wired in source but has no documented
  behavior spec — fetcher code search). Resolvable the same way: a child that prints its environ,
  spawned with no `env` option, on the pinned version.
- **Exit codes / signals:** `process.exitCode` set inside an `'exit'` listener now honored
  (#38229, 1.4). But: `bunx` silently swallows command exit codes
  (https://github.com/oven-sh/bun/issues/26674, open); on Windows a **rejecting** `Bun.file()`
  read fails to hold the event loop — process **exits 0 mid-await, no output, no error** (1.4.0
  regression, https://github.com/oven-sh/bun/issues/39787, open); `Subprocess.kill("SIGUSR1")`
  uses the **Linux signal-number table on macOS**, delivering SIGBUS
  (https://github.com/oven-sh/bun/issues/35296, open); SIGTERM/SIGINT handlers never fire while
  `process.stdin` has a flowing `data` listener on macOS (/30189, open); `process.on("SIGINT")`
  ineffective on Windows (/13040, open).
- `--no-orphans`: Bun exits when its parent dies and recursively SIGKILLs descendants
  (Linux/macOS native, Windows Job Object) — https://bun.com/blog/bun-v1.4.
- `os.userInfo()` reads env vars, not passwd; tty streams extend fs streams, non-TTY fd returns
  `isTTY:false` instead of throwing; `tty.WriteStream.prototype.isTTY` missing contradicts the
  🟢 doc status (https://github.com/oven-sh/bun/issues/29019, open).

**What this buys ccodex:** most of the Python `sdlc` surface would port — but the exit-code
contract (0/1/2/3/4) is exactly where the open defects cluster (silent exit-0, swallowed codes,
wrong signal tables), even though the basic Linux round-trip floor is measured-good (§2.9). The
environment-allowlist spawn contract's explicit-env half is measured-good on `Bun.spawn` (full
replacement map, no shell), but its no-env default and Windows quoting remain documented
**nowhere**. Both areas still need CLI-contract subprocess tests (a named revisit trigger)
before any trust.

### 4.8 Windows

- Vendor numbers (unverified independently): startup 15.5 ms (was 39.0; Node 40.1), peak memory
  16.8 MB; binary 84.8 MB x64 / 75.1 MB arm64; sub-15 ms timers; AppContainer support —
  https://bun.com/blog/bun-v1.4. Minimum Windows 10 1809 (https://bun.com/docs/installation).
- **Bun itself avoids symlinks on Windows by design:** the `.bunx` shim exists because "Symlinks
  are not guaranteed to work on Windows"
  (https://github.com/oven-sh/bun/blob/main/src/install/windows-shim/bun_shim_impl.rs);
  `bun install` uses hardlinks. Whether the 1.4 opt-in global virtual store needs Developer
  Mode / `SeCreateSymbolicLinkPrivilege`: **UNKNOWN** (undocumented either way,
  https://bun.com/blog/bun-v1.4). Developer Mode **is** required to build Bun on Windows and is
  still undocumented (https://github.com/oven-sh/bun/issues/39669 open; docs PR
  https://github.com/oven-sh/bun/pull/39667 open).
- **argv marshalling:** `bun.exe` splits `GetCommandLineW` with MSVC CRT rules, identical to
  node's `wmain` (https://github.com/oven-sh/bun/blob/main/src/bun_core/util.rs, read on `main`,
  not tag-pinned); the `.bunx` shim forwards the raw command-line tail **byte-for-byte with no
  re-quoting** (bun_shim_impl.rs). PowerShell 5.1 quote-stripping: no Bun-side mitigation or
  acknowledgment found; expected to reproduce identically to node (**Bun team position UNKNOWN**).
  argv[0] mode detection is case-sensitive — `bunx.EXE` (as PATHEXT supplies) behaves as `bun`
  (https://github.com/oven-sh/bun/issues/36826, open).
- **Live corruption bug:** CWD drive-letter aliasing (`subst`/junction/Dev Drive) makes the
  isolated linker infinite-loop and `--linker=hoisted` **silently rewrite `bun.lock` workspace
  keys** to absolute paths — committable corruption
  (https://github.com/oven-sh/bun/issues/39357, open). UNC path cases unfixed since 2024-02-23
  (/9071). `fs.rmSync` EFAULT on recursive temp removal (/39708, open); `node:sqlite` EBUSY after
  close (/40001, open); `npm:`-prefixed deps skipped by install (/39771, open).
- ConPTY (`Bun.Terminal`, Windows since 1.3.14): no termios, `setRawMode` records only, output
  re-encoded by the virtual screen, `\r` not translated, SIGWINCH conditional, pre-24H2 close can
  block (https://bun.com/docs/runtime/child-process).
- Windows ARM64 native since 1.3.10 (asset-verified); open crash
  https://github.com/oven-sh/bun/issues/21869.
- 120 open issues carry the `windows` label (GitHub search
  `repo:oven-sh/bun is:issue is:open label:windows`, run 2026-08-22). Notable non-repro:
  https://github.com/oven-sh/bun/issues/39989 (`bun run` hangs invoking `node_modules/.bin`
  binaries on 1.4.0, both Git Bash and PowerShell) closed `not_planned` after robobun could not
  reproduce on Server 2019/PS7 — the repro environments differ on exactly the client-Windows axis.
  MSYS2/Git Bash support statement: none; **largely UNKNOWN**.

**What this buys ccodex:** it doesn't change the standing posture — ccodex's Windows surface
already fails closed, and Bun's own installer refusing to rely on symlinks is independent
confirmation that the symlink-based install lifecycle contract has no clean Windows story in this
runtime either. The `.bunx` byte-for-byte forwarding at least means Bun adds no *new* quoting
layer between a caller and a helper binary.

### 4.9 Tooling (test runner, pm, bunx, TS execution)

- **Reading caveat (from the fetcher, verified against blog badges):** the 1.4 blog is cumulative
  since 1.3 and badges each feature with its true ship version — `--parallel`, `--isolate`,
  `--shard`, `--changed` shipped in **1.3.13** (https://bun.com/blog/bun-v1.3.13); genuinely new
  in 1.4.0 is `--timings`/`--update-timings` (LPT scheduling, #36814,
  https://bun.com/blog/bun-v1.4). The published CLI flag table
  (https://bun.com/docs/cli/test) lists none of these — docs surface is inconsistent.
- **`--parallel` is not yet hardened:** worker killed by JSC GC assertion, full-run abort on
  Linux arm64 (https://github.com/oven-sh/bun/issues/40129, open); deadlock "persists on v1.4.0
  stable" (/39987); `--isolate` hangs after children finish (/39709). Coverage-threshold check
  silently skipped when only the lcov reporter is enabled — documented defect
  (https://bun.com/docs/test/coverage) matching /32118.
- New in 1.4.0: `bun audit fix` / `bun dedupe` / `bun prune` (#38333), `bun pm licenses`,
  `bun pm diff` (https://bun.com/blog/bun-v1.4; https://bun.com/docs/pm/cli/audit etc.).
  `bun audit fix` **rewrites exact pins in `package.json` as `^version`** — an exception to
  "only lockfile changes" (docs). Known bad behavior: `--latest` can downgrade across majors to a
  *more* vulnerable version (https://github.com/oven-sh/bun/issues/39309).
- `bunx`: shebang-honoring (`#!/usr/bin/env node` runs Node unless `--bun`); fork-bombs when
  `BUN_OPTIONS` is set (https://github.com/oven-sh/bun/issues/39377, open); swallows exit codes
  (/26674).
- TS execution: on-the-fly transpile, **no type checking**; `tsconfig.json` from cwd,
  `--tsconfig-override` (https://bun.com/docs/cli/run). **`@types/bun@1.4.0 IS published
  [measured]** — the spike's own `bun install` resolved `"@types/bun": "latest"` to `1.4.0`
  (sha512 recorded in `/tmp/bun-cli-spike/bun.lock`; package cached at
  `~/.bun/install/cache/@types/bun@1.4.0…` with `"version": "1.4.0"`). Issue
  https://github.com/oven-sh/bun/issues/39788 ("not published for 1.4.0") **remains open but is
  stale** — the package shipped after it was filed. Not a blocker for pinning a TS project to
  1.4.0.
- Whether Bun itself enforces `packageManager`/`engines.bun`: **UNKNOWN** (only third-party
  consumers confirmed reading them). AI-agent auto-quiet: `CLAUDECODE=1`/`AGENT=1` hide passing
  output in `bun test` (https://bun.com/docs/test).

**What this buys ccodex:** `bun test --shard/--timings` would be a credible engine for the
CLI-contract subprocess tests the revisit triggers require — once the `--parallel` stability
cluster clears (`@types/bun@1.4.0` exists, measured above). The pm commands touch none of
ccodex's contracts.

---

## 5. Honest gaps table

| Gap | Status | Evidence |
|---|---|---|
| armv7 / any 32-bit compile target | Absent **at the type level** (`Architecture = {X64, Arm64, Wasm}`); also no riscv64/ppc64le/s390x | https://github.com/oven-sh/bun/blob/bun-v1.4.0/src/bun_core/env.rs L174–179 |
| Compile-target digest pinning | Does not exist; verification PR open, unmerged; would be registry-integrity, not a local pin | https://github.com/oven-sh/bun/pull/36173; §3.2–3.4 |
| macOS 27 signing regression (SIGKILL before user code) | Fixed on `main` 2026-08-22 (post-1.4.0); **in no release** | https://github.com/oven-sh/bun/issues/39764; https://github.com/oven-sh/bun/pull/39837 |
| `strip` destroys the compiled payload | Undocumented by Bun; third-party evidence only; per-format mechanism and `llvm-strip` behavior UNKNOWN | https://zenn.dev/gw31415/articles/81afbf1ae77189?locale=en; §2.8 |
| musl | Targets published (`bun-linux-{x64,aarch64}-musl` at 1.4.0 on npm); the musl compile output is **dynamically linked against `/lib/ld-musl-x86_64.so.1` [measured]** (`file` on `/tmp/bun-cli-spike/dist/x-bun-linux-x64-musl`) — it will **not** run on glibc-only hosts; runtime quality otherwise UNKNOWN | §2.1 target matrix; https://registry.npmjs.org |
| `-baseline` npm packages vs docs "same binary" | **RESOLVED [measured]:** contained binaries byte-identical (sha256 `ca8a18d0…`); sha512 delta is packaging-level; docs claim confirmed | §2.1; local compile cache |
| Compile-output determinism | **Non-deterministic [measured]:** identical inputs → identical size, pairwise-distinct sha256; pin shipped bytes only, rebuild-and-compare impossible | §2.5; `/tmp/bun-cli-spike/dist/repro-{1,2,3}` |
| Compiled-binary `.env`/`bunfig` autoload | **Default ON [measured]** (`bun build --help`: "default: true") — ambient env ingestion unless built with `--no-compile-autoload-{dotenv,bunfig}` | §2.1; §6 harvest checklist |
| `BUN_BE_BUN` / `BUN_OPTIONS` vs a pinned helper | One env var repurposes the binary into the full bun CLI; another splices argv from the environment; whether a compiled binary can disable either: UNKNOWN | §2.1; https://github.com/oven-sh/bun/issues/21496 |
| Error-output credential hygiene | UNKNOWN: `ShellError` command-line echo, crash-banner argv/env dump, fs error path contents — none measured; resolvable by sentinel-secret tests | §2.9, §4.1 |
| POSIX symlink lifecycle primitives | readlink/lstat/realpath/rename-over-link correct [measured]; `fs.symlink` EEXIST refusal and atomic symlink-then-rename UNKNOWN | §4.2 |
| Directory modes (`mkdirSync {mode}`, umask, explicit open mode at syscall) | UNKNOWN — live given `Bun.write` ignores `{mode}`; receipt dirs need 0700 | §4.2 |
| Embedded-runtime licensing (JavaScriptCore LGPL, ICU) | Every compiled helper redistributes Bun's runtime incl. JSC and ICU data; NOTICE/donor obligations unresolved — verify licence texts before shipping | §2.5 composition; §6 harvest checklist |
| Next-release version numbering | CI builds `1.4.1-canary.1`; npm canary is `1.4.0-canary.*` — authoritative numbering UNKNOWN | https://github.com/oven-sh/bun/issues/40037; npm dist-tags |
| Exit-code/flush/signal semantics of compiled binaries | Undocumented; SIGBUS→SIGILL observed; but the Linux `process.exit(n)` round-trip floor is measured-good (0 and 3 faithful) | https://github.com/oven-sh/bun/issues/39354; §2.9 |
| Small-CLI compiled binary size on 1.4.0 | **RESOLVED [measured]:** linux-x64 82,547,912 B; darwin-arm64 63.9 MB; darwin-x64 70.7 MB; musl 76.3 MB; windows-x64 88.8 MB | §2.5; `/tmp/bun-cli-spike/dist/` |
| macOS notarization automation | UNKNOWN (none documented) | https://bun.com/docs/bundler/executables |
| `F_FULLFSYNC` on macOS | Not used, no API reaches it (UNKNOWN if any path exists) | node_fs.rs; §4.2 |
| Windows `O_NOFOLLOW` | Silent no-op (`#define 0` in libuv) | https://github.com/libuv/libuv/blob/v1.x/include/uv/win.h |
| Windows directory-handle `FlushFileBuffers` | UNKNOWN (untested; requires write access) | §4.2 |
| `Bun.write` mode/atomicity/symlink behavior | Ignores `mode`, non-atomic, no fsync, follows symlinks [measured]; undocumented | §4.2 |
| FileSink truncation | Overwrites without truncating [measured]; `.flush()` is write(2), not fsync | §4.2 |
| `appendFile({flush:true})` | fsync ignored; closed `not_planned` | https://github.com/oven-sh/bun/issues/34914, /34915 |
| Compile-cache env-override chain | Whether every cache override reaches the compile path: UNKNOWN | compile_target.rs L209 comment; §3.1 |
| `Bun.secrets` in 1.4 / headless CI | 1.4 delta UNKNOWN; headless behavior UNKNOWN; Windows null-byte bug open | §4.4; https://github.com/oven-sh/bun/issues/24135 |
| Official sha256 throughput | UNKNOWN (no vendor number) | §4.5 |
| `Bun.markdown` HTML sanitization | UNKNOWN (no guarantee found; API self-labeled unstable) | https://bun.com/docs/runtime/markdown |
| `bun:sqlite` default `busy_timeout` / multi-process guidance | UNKNOWN | https://bun.com/docs/runtime/sqlite |
| FFI variadics | Unsupported → no `syscall(2)` fallback | https://github.com/oven-sh/bun/issues/12389 |
| `dlopen` JIT requirement × `--compile` / JIT-off flags | UNKNOWN (breaking-change note names no flag) | https://bun.com/blog/bun-v1.4; §4.6 |
| Windows argv quoting / `shell:false` semantics / default env inheritance | Explicit-`env` full-replacement and no-shell literal argv **measured-good on `Bun.spawn`**; no-env-option default inheritance and Windows quoting still UNKNOWN | §4.7; `/tmp/bun-cli-spike/test/spike.test.ts` |
| PowerShell 5.1 quote-stripping position | No Bun-side mitigation found; team position UNKNOWN | §4.8 |
| MSYS2 / Git Bash support statement | None; largely UNKNOWN | §4.8 |
| Global virtual store symlink privilege on Windows | UNKNOWN (undocumented) | https://bun.com/blog/bun-v1.4; §4.8 |
| `@types/bun` for 1.4.0 | **RESOLVED [measured]: published** (resolved from `latest`, sha512 in the spike's `bun.lock`); issue #39788 open but stale | §4.9; `~/.bun/install/cache/@types/bun@1.4.0…` |
| Chocolatey packaging | UNKNOWN | §3.6 |
| `bun upgrade` payload signing | None; open FR | https://github.com/oven-sh/bun/issues/39464 |
| TMPDIR leak of dlopen'd embedded `.so` | Unfixed **by decision** (`not_planned`) | https://github.com/oven-sh/bun/issues/40076 |
| Linux `birthtime` | 0 without `STATX_BTIME`, silent [measured] | §4.2 |
| `bun install` GitHub-dep sha512: enforced or only recorded? | Partially UNKNOWN | §3.5 |
| BatBadBut guard ship version | UNKNOWN whether it predates 1.4 | §4.1 |
| Shell performance in 1.4 | UNKNOWN (no published benchmark) | §4.1 |
| child_process 11 failing Node tests | Identity UNKNOWN | §4.7 |
| Rust-rewrite engineering post | None found beyond the 1.4 announcement | §1 |
| Memory headline vs measured heap | Blog "up to 35% reduction" coexists with heap peaks 1.4–2.6× above Node under sustained allocation — differently-scoped claims, unreconciled | https://bun.com/blog/bun-v1.4; https://github.com/oven-sh/bun/issues/39844 |

---

## 6. Revisit-trigger checklist

ADR-0031 names three triggers plus one approved harvest. Exact facts to re-verify, and where:

### Trigger 1 — compile-target digest pinning exists

- [ ] Is https://github.com/oven-sh/bun/pull/36173 merged? (`gh pr view 36173 -R oven-sh/bun`)
- [ ] Is it **in a shipped release**? Check the release tag's
  `src/standalone_graph/StandaloneModuleGraph.rs` for `integrity`/`sha512` (grep was 0 at
  `bun-v1.4.0`); confirm the release notes at https://bun.com/blog mention it.
- [ ] Does the shipped behavior verify **before extraction** and fail with the named error, and
  does it still leave `BUN_COMPILE_TARGET_TARBALL_URL` unverified (per the PR text)?
- [ ] Even if merged: registry-integrity ≠ local pin. Re-verify whether any lockfile/config
  **digest pin** for compile runtimes now exists (none proposed as of 2026-08-22; re-search
  issues for "compile target integrity/pin").
- [ ] Cross-check the silent wrong-runtime selector: is
  https://github.com/oven-sh/bun/pull/37389 (malformed `-vX.Y.Z` tokens) fixed?

### Trigger 2 — post-demolition ccodex surface stable one release

- ccodex-side (this repo's release history), not a Bun fact. When evaluating, also re-check the
  Bun release baseline: does a 1.4.x point release exist yet
  (https://github.com/oven-sh/bun/releases — none as of 2026-08-22), and does it ship the
  signing fix (#39837 — run `test/bundler/compile-macho-codesign.test.ts` against the release
  artifact; it **fails on 1.4.0**) and the mode-0600 fix
  (https://github.com/oven-sh/bun/pull/40112)?
- [ ] Resolve the version-numbering discrepancy (1.4.1-canary vs 1.4.0-canary.*) at
  https://registry.npmjs.org/-/package/bun/dist-tags vs Buildkite/CI.

### Trigger 3 — CLI-contract subprocess tests exist

- ccodex-side. If Bun is the test engine, first re-verify:
  - [ ] `--parallel` stability: https://github.com/oven-sh/bun/issues/40129, /39987, /39709 closed?
  - [x] `@types/bun` published for the pinned Bun version — **satisfied for 1.4.0 [measured]**
    (the spike installed `@types/bun@1.4.0`; issue
    https://github.com/oven-sh/bun/issues/39788 is open but stale). Re-verify only if the pin
    moves (`npm view @types/bun versions`).
  - [ ] Exit-code fidelity issues: https://github.com/oven-sh/bun/issues/26674 (bunx swallows),
    /39787 (Windows silent exit-0), /35296 (macOS signal table) — all must be closed or worked
    around before the 0/1/2/3/4 contract can be tested *through* Bun.
  - [ ] Env-inheritance/`shell:false` spawn semantics documented or empirically pinned by test —
    the explicit-env full-replacement and no-shell halves are already pinned by
    `/tmp/bun-cli-spike/test/spike.test.ts` [measured]; still needed: the no-env-option default
    and Windows quoting (§4.7 UNKNOWNs).
  - [ ] Error-output hygiene tests: sentinel credential in argv/env must not appear in
    `ShellError` message/stack, the crash banner, or fs error messages (§2.9, §4.1 UNKNOWNs) —
    this, not `Bun.secrets` storage, is the refusals-never-print-credentials risk surface.

### Approved harvest — settings classifier as a digest-pinned Bun helper

- [ ] Build with `--compile-executable-path` against an out-of-band-verified runtime (the only
  supply-chain-tight path, §3.3), or confirm Trigger 1 landed.
- [ ] Record the helper's sha256 in the ccodex manifest; refuse-on-mismatch at install and launch
  (ccodex's existing digest-as-approval machinery — Bun provides `Bun.CryptoHasher` for the
  helper's own re-derivation, §4.5). **The pin covers the shipped artifact's bytes only:
  rebuilds are non-reproducible [measured, §2.5], so rebuild-and-compare verification is
  impossible by construction — never promise it.**
- [ ] Build with `--no-compile-autoload-dotenv --no-compile-autoload-bunfig` — both autoloads
  **default ON [measured]**, and a default-built helper ingests a cwd `.env`/`bunfig.toml`,
  violating the environment-allowlist contract (§2.1).
- [ ] Threat-model the ambient env controls: `BUN_BE_BUN=1` turns the pinned helper into the
  full `bun` CLI and `BUN_OPTIONS` splices argv from the environment (§2.1). The launcher must
  scrub/deny both in the helper's child environment; whether the binary itself can disable them
  is UNKNOWN — re-test on the pinned version.
- [ ] Resolve redistribution/licensing obligations before shipping: every compiled helper embeds
  Bun's runtime including JavaScriptCore (LGPL) and ICU data (§2.5 composition; PR #32262 states
  "JSC 22.9 MB + ICU data 23.7 MB"). Verify the exact licence set from the Bun source tree at
  the pinned tag and record any required notices per this repo's ADR-0001 NOTICE posture —
  UNKNOWN until done.
- [ ] If the helper targets macOS: confirm the shipped Bun contains #39837, or bake the
  `codesign --force --sign -` re-sign step into the release pipeline
  (https://github.com/oven-sh/bun/issues/39764 workaround).
- [ ] If the helper embeds native libs via dlopen: account for the never-deleted
  `$TMPDIR/.<hash>-<index>.so` per launch (https://github.com/oven-sh/bun/issues/40076,
  `not_planned`).
- [ ] Never ship the helper through a packaging path that runs `strip` (§2.8).
- [ ] Do not use `--sourcemap=inline` if the helper throws in loops
  (https://github.com/oven-sh/bun/issues/39800).
- [ ] Helper file writes must use the `node:fs` durable recipe, never `Bun.write`/FileSink (§4.2).

*End of survey. Reference material only; the recorded decision (ADR-0031: no rewrite) stands.*
