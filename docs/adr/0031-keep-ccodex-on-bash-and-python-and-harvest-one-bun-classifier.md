# ADR-0031 — Keep ccodex on bash and Python; harvest one Bun-compiled classifier

- **Status:** accepted
- **Date:** 2026-08-23
- **Deciders:** operator (directed the evaluation and the documentation of its outcome); agent
  (measurement and drafting)
- **Relates to:** `docs/research/2026-08-22-overengineering-audit.md` (the Bun spike's raw
  measurements live in the adjacent `.json`),
  `docs/research/2026-08-23-bun-cli-capability-survey.md` (the Bun 1.4+ capability reference for
  any future migration), `scripts/opencodex-claude.sh`, ADR-0020 (the jq exact-dependency rule this
  decision's one harvest retires), ADR-0021 (the mise-fronted distribution topology this decision
  leaves unchanged)

## Context

The proposal was to rewrite `ccodex` — installer, updater, and launcher — as a single Bun-compiled
CLI, on the premise that Bun's built-in cross-platform APIs would remove the shell-script tax and
the need for platform-specific handling. The premise was evaluated by building, not arguing: a
590-line spike ported the launcher's security core (the settings-bypass classifier, the jq
resolver, the argv assertions, the env allowlist) to Bun, compiled it for twelve targets, and
measured it against the shipping bash on 2026-08-22, on Bun 1.4.0. A parallel surface map traced
what a full port would actually have to carry.

Five measured facts decided it.

**The motivating defect is not a bash defect.** The Windows argv corruption behind 34 CI failures
reproduced identically against the compiled Bun binary: PowerShell 5.1's CreateProcess marshalling
strips embedded double quotes for every native executable, so the binary received
`{ultracode:true}` exactly as the bash path did. Going native additionally enters MSYS2 path
mangling (`/usr/bin:/bin` rewritten to Windows paths) that a `.sh` file invoked by bash never
sees. The fix is quoting at the PowerShell crossing, in any language (seed `agentic-sdlc-7123`).

**"One cross-platform CLI" inverts into five platform binaries.** `bun build --compile` emits a
separate 61–85 MB executable per target — roughly 350 MiB per five-platform release against one
120 KB script — with no armv7 or 32-bit target at all, in a tree named `custom-pi-setup`; musl
builds do not run on glibc hosts; and macOS signing regressed in 1.4.0 (the Rust-rewritten signer
produces binaries SIGKILL'd on macOS 27, oven-sh/bun#39764), so a real release needs its own
Developer ID and notarization where the script needs none. `strip`, present in ordinary release
tooling, destroys the binary while leaving `--version` answering exit 0.

**The supply chain fails this repository's own bar.** Cross-compile target runtimes are fetched
from a hardcoded `registry.npmjs.org` with **no checksum verification at all** in 1.4.0 (read from
`src/options_types/compile_target.rs` at tag `bun-v1.4.0`), and nothing pins their digests, making
more than 99.99% of the bytes operators would execute unpinned, in a repository whose validator
pins a browser download by hash (ADR-0006). `bunfig.toml` and `.npmrc` registry settings are not
honored on that path (oven-sh/bun#25713, open). Bun itself shipped 1.4 as its first release after a
Zig-to-Rust rewrite, and the signing regression above came from that rewrite.

**Compiled output is not reproducible.** Three back-to-back `bun build --compile` runs over
identical input produced identical-size binaries with pairwise-distinct sha256 digests, first
differing byte at offset 82,481,180 in the embedded-graph tail. This repository treats build
determinism as a control it will not trade away — rank 3 of the demolition kept `git archive`
specifically so a digest-named artifact keeps meaning what it says — and a compiled Bun artifact
cannot offer it. A digest can only ever be pinned over the shipped bytes; rebuild-and-compare
verification is impossible by construction.

**The tax being avoided does not exist.** One `ccodex sdlc install` crosses exactly one runtime
seam: bash `exec`s once into one mise-pinned Python interpreter, which loads every sibling by
exact path. mise, already the sole bootstrap prerequisite, supplies that interpreter invisibly.
The launcher's 2,025 bash lines are ~60 security-judgment functions plus 835 lines of measured
forensics comments that any port carries verbatim; the honest line saving measured at ~400. The
read-only enforcement in `ccodex_sdlc_readonly.py` patches the Python stdlib and has no Bun
equivalent short of a process-isolation redesign. Most `sdlc` tests call `module.main()`
in-process, so a language swap orphans the suite that would have to prove the swap.

The startup argument also failed: the compiled binary started 2.8x slower than bash parsing all
2,025 lines (24 ms vs 8.7 ms). Where Bun won decisively was the settings gate itself: one execve
and an in-process JSON parse against six uncached `mise exec -- jq` spawns, 130 ms → 24 ms, with
the two-regex-engine (ERE vs Oniguruma) agreement burden and ADR-0020's whole jq-resolution
problem retired, plus argv observability that turned a mechanism-unknown CI failure into a
ten-minute diagnosis.

## Decision

1. `ccodex` stays bash-plus-Python. No full or partial rewrite of the installer, updater, or
   launcher into Bun (or Go — the parallel idea of building an orchestrator TUI on the Go
   "agent-manager" pattern is retired with this record; that capability class is served by
   operator-installed external tools such as `pingdotgg/t3code`, adopted, if at all, through their
   own front doors per ADR-0009/ADR-0029, never vendored).
2. One harvest is approved: the settings-bypass classifier as a Bun-compiled helper invoked by the
   existing bash launcher, after the demolition ranks land and the surface stabilizes.
   Preconditions, all mandatory, each measured in the survey's harvest checklist:
   build against an out-of-band-verified runtime via `--compile-executable-path`, pinned by a
   digest this repository owns; oven-sh/bun#36173, if it lands, verifies only registry-supplied
   `dist.integrity` metadata (survey §3.4), so a compromised registry satisfies it and it never
   substitutes for the caller-owned pin; pin the helper's sha256 over the
   **shipped** bytes and never promise rebuild-and-compare; build with
   `--no-compile-autoload-dotenv --no-compile-autoload-bunfig`, because both autoloads default ON
   and a default-built helper would ingest a working-directory `.env` or `bunfig.toml` in violation
   of the environment-allowlist contract; scrub `BUN_BE_BUN` and `BUN_OPTIONS` from the helper's
   child environment, because the first turns the pinned helper into the full `bun` CLI and the
   second splices argv from the environment; resolve the embedded-runtime licensing obligation
   (every compiled binary carries JavaScriptCore under LGPL plus ICU data) against ADR-0001's
   NOTICE posture before shipping; keep the launcher's refusal exit contract (0 clean, 2 usage,
   3 refused, never 1 for a refusal); port the 835 forensics comments verbatim; print the argv
   received on refusal paths; never ship through a packaging path that runs `strip`.
3. The capability reference for any future reconsideration is
   `docs/research/2026-08-23-bun-cli-capability-survey.md`, maintained as a dated snapshot, not a
   living promise.

## Revisit triggers

Reopen this decision only when all three hold, re-verified at that time, not assumed:

1. Bun pins or verifies its compile-target runtime downloads by digest. The exact thing to watch
   is oven-sh/bun#36173, which would check the downloaded tarball against registry `dist.integrity`
   before extraction; it was open and unmerged as of 2026-08-23, and it deliberately leaves a
   caller-supplied `BUN_COMPILE_TARGET_TARBALL_URL` unverified.
2. The post-demolition `ccodex` surface has been stable for at least one release.
3. The `sdlc` namespace is tested through its subprocess seam (argv in, receipts and exit codes
   out), so a language swap is a provable refactor rather than a bet. This is the C3 deepening
   candidate from the 2026-08-22 architecture review, and it is worth doing on its own merits.

A future evaluation should also re-measure, not inherit: binary sizes and startup (1.4 improved
both), the macOS signing state (the arm64 ad-hoc signature bug was fixed on `main` by
oven-sh/bun#39837 two days after 1.4.0 shipped, so it is in no release as of this record), the
armv7 gap, the `strip` behavior, and compile reproducibility. The survey's own gaps table carries
every fact its fetchers could not resolve, marked UNKNOWN with what would resolve it.

## Rejected alternatives

- **Full Bun single-binary ccodex.** Rejected on the four measured facts above. It would have
  shipped the same Windows bug in a 350 MiB unpinned artifact with an unowned macOS signature.
- **Go rewrite around the agent-manager orchestrator pattern.** Rejected without a spike: it
  shares every distribution cost of the compiled-binary path (per-platform artifacts, signing,
  supply chain) while adding a language this repository does not otherwise carry, and the
  orchestrator capability it targeted is available as maintained external prior art
  (claude-squad, Conductor, t3code).
- **Rewriting only the Python `sdlc` namespace in Bun, keeping bash.** Rejected as the worst of
  both: it keeps the bash surface, adds the compile supply chain, and discards the import-based
  test suite — while the Python runtime it removes is one mise already pins invisibly.

## Consequences

- The Windows CI fix proceeds at the real crossing (seed `agentic-sdlc-7123`), independent of any
  language choice.
- The classifier harvest is a bounded follow-up with its preconditions recorded here; nothing else
  about the distribution topology (ADR-0021: mise → versioned release → one `ccodex` CLI →
  per-host install) changes.
- Anyone re-proposing a Bun or Go rewrite starts from this record and the survey, and must show
  which measured fact changed.
