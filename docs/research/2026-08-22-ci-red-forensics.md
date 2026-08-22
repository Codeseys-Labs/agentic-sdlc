# CI red forensics: the 17 ubuntu failures are three newer-kernel dependencies

Date: 2026-08-22. Scope: the `blacksmith-2vcpu-ubuntu-2404` leg of `validate.yml` at the head of
`feat/ccodex-rightsizing-controls`, red with `failures=4, errors=13, skipped=17` while the same
3657-test suite at the same commit is green locally (`skipped=13`). Diagnosis produced by a
read-only forensics pass; every causal claim below was reproduced on the local host by simulating
the CI-side environmental fact, with exact-matching assertion messages. Seed of record:
`agentic-sdlc-df5f`.

## Summary

All 17 CI-only results reduce to three mechanisms. Each is product code silently depending on
filesystem behavior this development host's kernel (6.18.33.2, WSL2) provides and the Ubuntu
24.04 runner does not. Two fail **open** at trust boundaries on CI; one escapes as a raw
traceback although a working fallback already exists two lines above the failing call. None is
caused by anything on this branch: mechanisms A and B2 landed after the last green CI run and
have never passed CI on Linux; mechanism B1's code and test are byte-identical to a commit where
CI was green.

## Mechanism A — 13 errors + 2 failures (15 of 17)

Every error in `tests/test_research_os_lifecycle.py` is the same traceback:
`FileNotFoundError: [Errno 2] No such file or directory: 'payload'` at
`skills/codex-research-os/scripts/install_research_os.py` `_link_fd` (called from `_stage_file`).

`_link_fd` invokes `linkat(fd, "", dirfd, "payload", AT_EMPTY_PATH)` via ctypes. `man 2 linkat`
states verbatim that `AT_EMPTY_PATH` without `CAP_DAC_READ_SEARCH` fails `ENOENT`. The local
host runs uid 1000 with `CapEff: 0000000000000000` and the call succeeds anyway (newer-kernel
relaxation, probed directly on `/tmp` and the repository filesystem); CI's unprivileged `runner`
gets exactly that `ENOENT`. The `O_TMPFILE` fallback in `_stage_file` guards only the **open**;
the `_link_fd` call sits outside the try/except, so when `linkat` is the unavailable primitive
there is no fallback at all and the `ENOENT` escapes as a traceback — worse than either falling
back or refusing by name.

The 2 failures are this mechanism in disguise:
`test_cleanup_namespace_swap_preserves_foreign_replacement` and
`test_manifest_stage_swap_is_refused_and_recovery_conflicts` wrap the call in
`with self.assertRaises(Exception)`, which the environmental `FileNotFoundError` satisfies; the
tests then assert on artifacts that were never staged and report a misleading `[] is not true`.

Owner: product code (`install_research_os.py`), plus a test-owned tightening of the two
`assertRaises(Exception)` sites to the specific expected exception. Fix shape: gate the
`O_TMPFILE` branch on a process-wide `linkat AT_EMPTY_PATH` capability probe so incapable hosts
deterministically take the named `O_CREAT|O_EXCL` staging branch that already exists. A
`/proc/self/fd` path-based fallback was considered and rejected: it re-introduces path resolution
at a boundary the file deliberately keeps descriptor-only.

## Mechanism B1 — 1 failure (deferred; fix blocked on runner probe data)

`tests/test_install_skill_bundle.py` `test_owned_copy_requires_recorded_type_and_object_identity`
expects exit 1 for a deleted-and-recreated owned tree and CI observes exit 0. The ownership
witness is `stat-v2:<st_dev>:<st_ino>:<statx btime>`. Instrumented locally: after
`remove_path` + `copy_item`, `st_dev` and `st_ino` are **identical** (ext4 reuses the inode;
observed `2096:2400434` both times), so btime is the only discriminator, and it differed locally
by 27.8 ms. Patching the btime source to a constant reproduces CI's exact `AssertionError: 0 != 1`.

This is the ownership trust boundary failing open: a present-but-non-discriminating btime
classifies a replaced tree as still owned and silently removes it, where the documented doctrine
is to fail closed when stable physical identity is unavailable. The content digest recorded per
entry cannot substitute — a byte-identical re-copy defeats it.

B1 is **not** a code regression: the test body and every discriminating function
(`stat_birth_identity`, `stat_identity`, `identity_matches`, `copy_record_identity_matches`,
`entry_matches_record` in `scripts/install_skill_bundle.py`) are byte-identical to the last green
CI commit. With a non-discriminating btime the verdict collapses to whether the filesystem
happened to reuse the inode — a coin flip — so B1 reads as nondeterministic on CI; the flake is
the symptom of the too-weak witness.

The fix decision (probe-and-refuse threshold design) depends on whether the runner's btime is
constant, coarse (and at what quantum), or fine-grained — a fact only the runner can supply.
`validate.yml` now carries an advisory Linux-only capability probe (never a gate leaf) to report
it. Forward-looking: `install_research_os.py` builds `_fd_identity` from the same
`dev:ino:btime` witness, so fixing mechanism A is expected to expose B1-class behavior inside the
research-os suite as well; fix them together.

## Mechanism B2 — 1 failure

`tests/test_release_candidate.py`
`test_verify_pins_admitted_fd_against_path_substitution_and_mutation` expects `CandidateError`
and CI observes none. `_pin_archive` (`scripts/release_candidate.py`) detects mutation by
re-fstating the descriptor it already pinned and comparing
`(dev, ino, size, mtime_ns, ctime_ns)`. The test's substitution renames the pinned file away and
writes a different file at the path — the pinned inode is untouched; only the path-to-inode
binding changed, which a descriptor re-fstat structurally cannot see. The check passes locally
only by accident: the pinned inode's `ctime_ns` was measured going **backwards** across the
rename (a newer-kernel fine-grained-timestamp artifact, not a mutation signal). Quantizing
ctime/mtime to 1 s reproduces CI's exact result.

Owner: product code. Fix shape: after the pin copy, re-resolve the path and require it to be the
same object (`st_dev`, `st_ino`) as the pinned descriptor, in addition to the existing fd
re-fstat. The wave's adversarial verifier proved that alone is half a fix: the same-inode
content-mutation half of the test also rests on timestamps and stays red under 1 s quantization,
so the landed change adds a timestamp-free content recheck (re-read the pinned descriptor,
compare byte count and sha256 against the pinned copy) and a granularity-independent regression
test that mocks the timestamp components out of `_archive_identity`.

## The four extra CI skips (17 vs 13 local)

Reconstructed by mapping the CI result-character stream position-by-position onto the 3657 test
IDs in discovery order (all 13 E and 4 F land on their expected IDs; eight stray-output anchors
corroborate). The four tests that skip on CI but run locally:

1. `test_ccodex_sdlc_install` dispatch-contract test — CI has no observable Claude Code version.
2. `test_gate_graph` canonical-lock regeneration — requires exact maintenance mise 2026.4.27;
   `jdx/mise-action` installs its own latest (2026.8.10 observed), so the lock-regeneration
   contract is never actually gated in CI. Real toolchain drift, tracked separately.
3. + 4. Two `test_mermaid_renderer` sandbox tests — pinned sandbox binary absent on the runner;
   expected and correct per the ADR-0006 boundary.

None of the four relates to any failure mechanism; they reflect this host being better
provisioned, not a clue.

## Does main share the cause?

Last green run anywhere: `52a7d834` on main, 2026-07-22T20:36:51Z, all three OS jobs green.
Every main run from 2026-07-25 onward is red. Mechanism A's code landed 2026-08-06 (`b0c8bd5`)
and B2's landed 2026-08-16 (`3c01e2f`) — both after the last green run, so neither has ever been
green in CI. Because main's failures predate both, main was already red on ubuntu for at least
one additional cause as of 2026-07-25 that this diagnosis does not identify; the run logs are
expired (the API confirms job conclusions, but `gh run view --log` returns zero bytes for runs
older than the newest).

macOS and Windows are red for different and much broader reasons — Windows reports
`failures=487, errors=418, skipped=155` of 3342; macOS concentrates in the ccodex/acquisition
suites and in Linux-only machinery running without platform skips. Fixing the three ubuntu
mechanisms will not turn the matrix green; those legs are tracked as their own seeds.

## Claims deliberately left unverified

1. The runner's kernel version (the log names Ubuntu 24.04.3, rootfs `ubuntu24-full-x64-012126`,
   glibc 2.39 — no kernel string). The specific kernel versions for the `AT_EMPTY_PATH`
   relaxation and fine-grained inode timestamps were asserted from memory, not from a source read
   during the diagnosis. What was verified: the man-page capability rule, that this host succeeds
   with zero capabilities, and that this host's timestamps are genuinely fine-grained (60 distinct
   `st_mtime_ns` values across 60 files created within 2.31 ms; minimum delta ≈ 24 µs).
2. The runner's actual btime/ctime behavior. The causal shape is proven (degenerate btime
   reproduces B1 exactly; 1 s ctime reproduces B2 exactly; both pass at 10 ms granularity), but
   the runner's real values await the advisory probe.
3. Determinism across CI runs — only the newest run's log bodies are retrievable.
4. Whether the runner image changed between 2026-07-22 and now (the leading explanation for B1's
   flip on identical code).

## Addendum 2026-08-22 — the advisory probe ran; unverified items 1 and 2 are now measured

CI run 32554149554 (ubuntu leg) carried the advisory probe. Its results resolve items 1 and 2 of
"Claims deliberately left unverified" above and leave items 3 and 4 open.

- **Kernel (item 1): 6.6.141**, on ext4, with an effective capability set of zero. The zero-`CapEff`
  reading confirms the `linkat(AT_EMPTY_PATH)` `ENOENT` this document attributes to mechanism A: the
  probe observed that `ENOENT` directly on the runner rather than inferring it.
- **Timestamp granularity (item 2): degenerate, at every one of the three timestamps.** Across 40
  back-to-back creates the probe recorded exactly **1 distinct value** for btime, for ctime, and for
  mtime, over windows of **787 µs** and **375 µs**. That bounds the quantum below at ~787 µs; it does
  not measure it from above, so the exact tick is still unknown — only that it exceeds the whole
  creation burst. The local dev host (kernel 6.18) resolves the same burst into ~24 µs deltas and
  never collides, which is why B1 is green locally and red on the runner.
- **The B1 witness collision was reproduced on the runner, not modelled: 20 of 20.** The
  delete-and-recreate trial (create, `statx`, delete, recreate the same name, `statx`) returned an
  **identical `(inode, btime)` pair in 20 of 20 trials**. So on this runner the `stat-v2` witness
  carries no discriminating information at all across a same-name replacement, and a per-entry
  content digest cannot substitute, because a byte-identical re-copy satisfies it.

**Fix shape.** Because btime records CREATION time, a recorded witness can only be reproduced by a
replacement created inside the SAME quantum as the original. So a witness is trusted only once some
object created after it reports a strictly later birth timestamp, which proves the recorded object's
quantum has closed and that every later creation is stamped strictly later at any granularity.

Where that proof is paid matters as much as the proof. Ownership state in both lifecycles is written
durably MANY times per command — `persist_state` arms each transaction's journal and again resolves
it, so an N-entry install performs on the order of 2N durable writes, and the research-os scaffold
writes per file. Blocking for the proof at each of those recording points therefore costs one full
birth quantum per TRANSACTION, which is linear in the entry count: measured at 10, 20 and 40 waits
for 10-, 20- and 40-entry installs under a simulated 0.25 s quantum, 2.57 s / 5.91 s / 10.05 s wall,
extrapolating to tens of seconds on a 1-second-quantum filesystem. That is not an acceptable cost for
a lifecycle command, so recording does not block.

Instead every recording site takes ONE probe and never sleeps. On a filesystem with sub-quantum
granularity that probe proves settlement outright and nothing is deferred at all — the common case,
and free. When it cannot, the witness is persisted CARRYING that fact (`witness_settled: false`,
written in the same atomic state replace as the witness it qualifies) and the command pays a single
bounded wait for everything it deferred, once, immediately before its final state write. Re-measured
in that shape: **one wait for 10, 20, 40 and 44 entries alike**, the wait itself ≤0.63 s under a
simulated 1-second quantum, and a 44-entry install finishing in 2.06 s where the per-transaction
shape extrapolated to ~44 s.

A durably recorded unsettled witness is safe only because no later consumer discriminates on it:
`entry_matches_record`, `record_authority_matches` and `classify_recovery` in the bundle installer,
`_authority_matches` and `_recover_one` in the research-os installer, all fail CLOSED — status
reports a conflict, uninstall and removal preserve, recovery reports and preserves — which is byte for
byte the answer a degenerate clock already produced. An interrupted command therefore cannot leave a
witness a later run silently trusts. Within the command that deferred them the witnesses stay
trusted, because the marker is injected at the state-WRITE boundary and stripped again, for that
process's own keys only, at the state-READ boundary. A host whose birth clock does not advance inside
the bound is still refused by name.

One witness keeps the inline wait: the pre-existing TARGET ROOT the research-os installer records as
`state["target"]["identity"]`. Deferring it would require the marker to live in that stanza, and the
fail-closed reading of an unidentifiable ROOT is to refuse the whole document — including the
crash-recovery retry an interrupted run depends on. Its cost is a constant (one probe, and a wait only
when the operator points at a directory created inside the current quantum, which a long-lived
repository never is) and it does not grow with the scaffold's file count.
