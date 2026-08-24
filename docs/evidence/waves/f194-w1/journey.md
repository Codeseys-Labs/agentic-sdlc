# f194-w1 — installed-byte acceptance journey (executed record)

One contiguous container run on 2026-08-24 (04:15:43Z–04:15:53Z, 10 s of container wall time)
executed the full release-archive-plane journey the V3/V58 wave frame names: deterministic build →
placement bridge → sealed acquisition receipt → `ccodex sdlc install --host claude` copy-activation
→ receipt-vs-disk reachability → reader read-back → three classify/apply fixtures driven from the
activated plane's bytes → receipt-directed uninstall. Every step reached its named success or its
named refusal; the raw transcript is `transcript.log` in this directory and the script that
produced it is `journey-track.sh`. Line references below are into `transcript.log`.

This record discharges seed `agentic-sdlc-f194`'s re-scoped acceptance (installed-byte classify
plus apply on one greenfield and one brownfield fixture, end to end). It PARTIALLY evidences seed
`agentic-sdlc-d5` — fresh installed bytes, one disposable downstream repository, receipts — while
three of d5's legs remain unmet here: the journey did not run on this repository itself ("dogfood
twice"), no admitted queue/route/mission surface was used (no `.seeds` queue existed anywhere in
this run), and the fixture commits were operator-proxy-approved shown diffs, not independently
reviewed. d5 must not be closed on this record. It is evidence only: nothing here authorizes
push, publication, PR mutation, merge, deployment, or any other outward effect.

## Execution environment

Disposable Docker container from image `asdlc-fresh:latest`
(`sha256:dd188f37ea7e392f37094cedfa18a6e39d29634927ad58eed69553aec041b8b3`, built 2026-08-23), user
`op` (uid 1001), `HOME=/home/op`. The operator's real `~/.claude` and host configuration were never
touched; every plane below is container-local. The primary checkout was mounted read-only at `/src`
and the journey cloned from it inside the container.

| tool | version | transcript line |
|---|---|---|
| Claude Code CLI (baked in image) | 2.1.241 — above the 2.1.154 contract floor, no reinstall needed | 10 |
| mise | 2026.8.11 linux-x64 | 9 |
| git | 2.43.0 | 6 |
| python3 (fixture/verifier driver) | 3.12.3 | 7 |
| uv (mise-pinned) | 0.12.5; supplied CPython 3.12.11 for all authoritative entrypoints | 30, 34 |

Container network was enabled: the only download the run needed was uv fetching CPython 3.12.11
(31.1 MiB, line 34); everything else was prewarmed in the image.

## Step-by-step verdicts

| # | Step | Verdict | Evidence (transcript lines) |
|---|---|---|---|
| S0 | Environment observation | pass — `claude --version` = 2.1.241 ≥ 2.1.154 floor | 2–17 |
| S1 | `git clone --no-local /src`, pinned checkout | pass — HEAD `6c30728677c4e122bf294a887c62fbb63a1b05c5`, `git status --porcelain` empty | 19–24 |
| S2 | Container-local `mise trust` + `mise --locked install` | pass — all tools already installed (prewarmed) | 26–30 |
| S3 | `mise run release:build` | pass — `dist/agentic-sdlc-0.7.3.tar.gz`, 230 entries, archive sha256 `563b4618b292685f655f210c357c409dee8220111fd6f409609eed573d1c6013`; `SHA256SUMS` names the same digest | 32–51 |
| S4 | Placement bridge, verbatim per Install-UX §"Pre-release candidate placement" | pass — extracted under `$XDG_DATA_HOME/agentic-sdlc/acquisition/candidates/<archive-sha256>/root`; `manifest.json` present, `source.commit` = the pinned commit, `source.tree` `cedb2d25be10b8e9a2c4cccf9cf2f877a4e77d59` | 53–81 |
| S5 | `scripts/write_acquisition_receipt.py` | pass — sealed `release-candidate-acquisition-receipt/v1`, terminal phase `installed-unselected`, `selection`/`activation` both `absent`; receipt sha256 `82ab22a643897e8c5a240344b52437ebe661b49430de4a323035843534ee3b3b` | 83–95 |
| S6 | `mise run operator-tools:install` (ccodex, checkout plane) | pass — `ccodex` + `agentic-sdlc-statusline` installed, 0 conflicts | 97–107 |
| S7 | `ccodex sdlc status --json` pre-install | pass — exit 0; `bundle.state: "absent"`, zero entries | 109–114 |
| S8 | `ccodex sdlc install --host claude` | pass — exit 0, "effect complete, terminal activated"; 26 entries all `absent -> installed`; `distribution-activation@1` receipt sha256 `8172f0a9eb4552b8e12af5c58c86e670c42f5eeaafa617571b3d9f73b764b4fc`; `active-receipt.json` pointer names it | 116–174 |
| S9 | Reachability: receipt inventory vs on-disk digests | pass — 26/26 `MATCH` using `install_skill_bundle.digest`; all five commands present, `digest_match=True` each | 212–244 |
| S10 | `inspect`/`status`/`doctor` `--json` + human `status` on the plane | pass — all exit 0, overall `healthy`, 26 owned bundle entries | 246–272 |
| S11 | Three fixtures from the ACTIVATED plane's generator | pass — details below | 274–438 |
| S12 | `ccodex sdlc uninstall` | pass — exit 0, 26 removed, terminal receipt `retired` (sha256 `f513307e5e1e232f1738c27c3e0f2b72338cb2a2aad62f2e12576ac4c3dc1991`); all five commands and every skill absent afterward | 440–519 |
| S13 | Final sweep | pass — state/data planes hold exactly the receipts, journals, plans, and candidate root | 526–549 |

## The digest chain (each link executed, none inferred)

```
commit 6c30728677c4e122bf294a887c62fbb63a1b05c5  (tree cedb2d25be10b8e9a2c4cccf9cf2f877a4e77d59)
  └─ release:build → dist/agentic-sdlc-0.7.3.tar.gz
       archive sha256 563b4618b292685f655f210c357c409dee8220111fd6f409609eed573d1c6013
       candidate_id   e4d768ca5aa08165abafb2b41b45faf622fa5109d65d16d9e3b296fbfc4e51a6
  └─ placement → $XDG_DATA_HOME/agentic-sdlc/acquisition/candidates/563b4618…/root
  └─ acquisition receipt  (sha256 82ab22a643897e8c5a240344b52437ebe661b49430de4a323035843534ee3b3b)
       …/acquisition/receipts/563b4618….json — terminal installed-unselected
  └─ ccodex sdlc install --host claude → distribution-activation@1 receipt
       (sha256 8172f0a9eb4552b8e12af5c58c86e670c42f5eeaafa617571b3d9f73b764b4fc)
       …/activation/receipts/install-op-dfae3319f628e2262e0af36160184dae-20260824t041550z.json
  └─ 26/26 on-disk digests under /home/op/.claude re-derived and equal to the receipt inventory
  └─ ccodex sdlc uninstall → terminal receipt operation uninstall, effect complete, terminal retired
       (sha256 f513307e5e1e232f1738c27c3e0f2b72338cb2a2aad62f2e12576ac4c3dc1991)
       derived-from: install-op-dfae3319f628e2262e0af36160184dae-20260824t041550z
```

Cross-artifact assertions executed against the committed copies in this directory (all pass): the
archive sha256 appears identically in the acquisition receipt, the install receipt body, and the
uninstall receipt body; the candidate manifest's per-file sha256 for each of the five commands
equals the activation receipt's `content_sha256` for that entry; and the generator the fixtures ran
(`/home/op/.claude/skills/agentic-sdlc/tools/instruction-generator.py`, sha256
`1a5bdb1afae4cbef192fe284c47117cb3804dc00f523e8ca0f2dcf02132a05fb`, line 275) carries exactly the
digest the candidate manifest records for `skills/agentic-sdlc/tools/instruction-generator.py` —
the fixture proof ran the payload's own bytes, chained back to the archive and the commit.

## Five-commands reachability (receipt/digest proof, per the ratified scope: no live session)

Lines 240–244: `sdlc-init`, `sdlc-frame`, `sdlc-wave`, `sdlc-mission`, `sdlc-rightsize` each
present at `/home/op/.claude/commands/<name>.md` with `digest_match=True` against the activation
receipt inventory. The digest function used is the product's own `install_skill_bundle.digest`
(the sole ownership-check definition), not a reimplementation.

## Fixture dispositions (f194's classify/apply proof)

The journey runner acted as operator-proxy for fixture repositories only; each verbatim
confirmation is in the transcript (lines 288, 315, 354, 369, 397). The reviewed
`instruction-manifest@2` the applies used is `instruction-manifest.json` here (canonical JSON,
1366 bytes, authored per `commands/sdlc-init.md` step 5).

**Greenfield** (`git init -b main`, one README commit, clean):
- `classify` → `{"verdict":"greenfield","occupied":[],"reasons":[],"ask":true}` (`classify-greenfield.json`, line 285).
- Two-invocation loop for `AGENTS.md`: apply without `--yes` printed the diff and refused at
  exit 3 having written nothing (target verified absent afterward, lines 289–314); the `--yes`
  re-run re-printed a **byte-identical** diff (verified by `diff`, line 342) and wrote
  `create: AGENTS.md`. Same loop for `CLAUDE.md` (exit 3 → exit 0, lines 343–356).
- Idempotence: re-running the identical `--yes` command reported
  `no-op: AGENTS.md already carries this block` at exit 0 (line 357).
- Activation commit `5c0e2c0` on top of intent commit `e883c88`; post-commit
  `git status --porcelain` empty (lines 358–361).

**Brownfield** (3 commits; pre-existing real `AGENTS.md`, `mise.toml`, `.github/workflows/ci.yml`)
— this fixture is also d5's "one disposable downstream repository":
- `classify` → `brownfield` naming exactly `.github`, `AGENTS.md`, `mise.toml` as occupied
  operating-contract surfaces (`classify-brownfield.json`, line 366).
- Apply refused at exit 3 first (target sha256 verified unchanged after the refusal, line 370);
  the diff is purely additive — the pre-existing three lines kept as context, the marked
  `<!-- agentic-sdlc:start/end -->` block appended (lines 371–395). `--yes` wrote
  `replace: AGENTS.md`; the pre-existing heading and the marked block both verified present
  afterward (lines 398–423). Local commit `066d9fa` (line 425).

**Refuse-and-ask** (2 commits, no contract surfaces, dirty tree):
- `classify` → `refuse-and-ask` with both reasons named: "the repository already has 2 commits"
  and "the working tree is not clean (1 reported entries)" (`classify-refuse-and-ask.json`,
  line 433). The run stopped at the named refusal, as the runbook directs.
- Exit-2 probe: `classify --target <brownfield>/src` refused by name —
  `--target is not a repository root; its root is /home/op/fixtures/brownfield` — at exit 2
  (lines 437–438).

All three verdicts were truthful, both write paths were diff-shown-then-approved, both refusal
paths refused by name without writing, and the fixtures never gained a remote — no push was
possible, let alone performed. No `.seeds` queue exists in any fixture and none was created or
mutated anywhere in the run.

## Uninstall and terminal plane state

`ccodex sdlc uninstall` removed exactly the 26 inventory entries (every row `prestate: owned`,
`disposition: removed` in `activation-receipt-uninstall.json`) and sealed the terminal receipt with
`derived-from` naming the install receipt. Afterward `/home/op/.claude` holds only the empty
collection directories (`agents`, `commands`, `hooks`, `skills`, `workflows` — the lifecycle never
removes collections) plus `backups/` and `downloads/`, which the Claude CLI's own installer created
before the journey began (prestate at lines 11–17); all five commands and all twelve skills are
absent (lines 504–519). The acquisition receipt, both activation-plane receipts, journals, plans,
and the candidate root remain as evidence, exactly as designed (lines 527–547).

## Findings (filed, deliberately not fixed in this workstream)

**FINDING-1 — after a complete, receipted uninstall, the readers report the plane `degraded` with
26 `owned-entry-conflict` findings.** `ccodex sdlc status --json` immediately after the successful
uninstall (exit 0, terminal receipt `retired`, effect `complete`) reports every one of the 26
bundle entries as `state: "absent"` with finding `owned-entry-conflict` / "owned bundle entry is
absent", `bundle.state: "degraded"`, `overall.state: "degraded"` (`status-postuninstall.json`;
transcript lines 520–524). Mechanism: `ccodex sdlc install` reuses `install_skill_bundle`'s
transactional protocol and therefore writes 26 ownership rows into the shared installer state
(`$XDG_STATE_HOME/agentic-sdlc-installer/state.json`); `ccodex sdlc uninstall`'s candidate set is
the receipt inventory and it removes the bytes, but the ownership rows survive it, so the very
next read contradicts the retirement receipt the same plane just sealed. No test pins this seam:
`grep -rn owned-entry-conflict tests/` matches only `tests/test_install_skill_bundle.py:1363`, a
different scenario. Either the uninstall should retire the ownership rows through the same
lifecycle, or the reader should recognize a retirement that derives from the pointed receipt —
which, is a product decision this workstream does not make. Seed-shaped recommendation left for
conductor capture.

**OBSERVATION-2 — `active-receipt.json` still names the retired install receipt after uninstall;
this is design, not a defect.** The pointer survives retirement (transcript lines 479, 490–493)
and the uninstall module's own tests pin the consequences
(`tests/test_ccodex_sdlc_uninstall.py`: "a receipt that already records a retirement is refused",
"an already retired activation refuses a second pass"): the plane's state is the pointer PLUS the
terminal retirement receipt that `derived-from`-names it. Recorded so a later reader does not
misfile this as FINDING-1's cause — FINDING-1 is about the installer ownership state, a different
file.

**OBSERVATION-3 — frame spelling nit.** The wave frame (step 7) and the dispatch spell the
read-back as `ccodex sdlc status --format json`; the shipped grammar (`usage()` in
`scripts/ccodex_sdlc.py`) is `status [--json]`. The journey used `--json`.

## Deviations from the dispatched procedure (harness-side, named with reasons)

1. **Clone source.** The dispatch said to mount the worktree read-only and `git clone --no-local`
   it. A linked worktree's `.git` is an indirection file
   (`gitdir: <primary>/.git/worktrees/agentic-sdlc-f194-journey`) whose absolute host path does not
   exist inside the container, so that clone cannot work. The journey instead mounted the PRIMARY
   checkout read-only at `/src` and pinned the in-container clone to the exact commit
   `6c30728…` (verified: `git rev-parse HEAD` equality plus empty `git status --porcelain`,
   lines 23–24) — the same tree the worktree held, which is what `release:build` archives.
2. **`safe.directory`.** git 2.43 refuses a repository owned by another uid; the container user is
   `op` (1001) while `/src` is host-owned. Container-local
   `git config --global safe.directory /src` + `/src/.git` admitted the read; the first attempt
   without the second entry failed exactly there and was rerun (this is why the successful run is
   the third container invocation; the first two aborted pre-effect at S1 and at S9 on a verifier
   `sys.modules` import bug in the journey script itself, not in the product).
3. **Harness extension.** The frame assigns WS-A "extends the external fresh-env harness with a
   journey track". Per this workstream's dispatch, file writes were confined to this worktree, so
   the ready-to-place track script is committed here as `journey-track.sh` (it is byte-for-byte the
   script the run executed); copying it to
   `~/.local/state/agentic-sdlc/fresh-env-harness/t6-installed-byte-journey.sh` is a one-command
   operator step left to the conductor.

## Honest boundary — what this proves, and what stays open

Proven, on a credential-free disposable container: the entire release-archive plane at commit
`6c30728` — deterministic build, documented placement, receipt sealing, five-phase copy-activation
against an observed host version, byte-exact reachability of every activated entry including the
five commands, read-only read-back, truthful three-verdict classification, diff-shown two-invocation
apply on greenfield and brownfield with idempotence and named refusals, and receipt-directed
retirement. This is the "credential-free clean environment" evidence class Install-UX step 12
names, for the placement-bridge path.

Open, and NOT claimed by this record:
- **Live canaries.** No logged-in Claude Code session ran `/sdlc-init`; five-commands proof here is
  receipt/digest reachability by ratified scope. The native-Claude minimum + stable-reference
  Workflow canaries (Release Validity bullet 4) remain the separate live-host operator lane.
- **Certified tuple.** `release-contract.v1.json` `support_rows` is `[]`; nothing here changes it.
- **The quick-install leg.** `mise use -g github:Codeseys-Labs/agentic-sdlc` stays impossible
  (zero releases, zero tags); the placement bridge was the acquisition source, as ratified.
- **Checkout-free `ccodex`.** The `ccodex` binary came from the clone's operator-tools plane; the
  journey does not claim a checkout-free ccodex (frame step 4 note).
- **Reader coverage of the activation plane.** The v1 read report the installed reader renders says
  `future_dimensions.activation: "unsupported"`; plane state was therefore proven from the receipts
  and digests directly, not from a reader projection of the activation plane.
- **Adversaries and durability.** Same-UID racers and power-loss durability are out of scope here
  exactly as the modules' own contracts state; the receipt seals catch drift, not forgery.
- **`ccodex sdlc update`** was not exercised (optional extension per the frame; bullet-2 evidence
  for it stays offline-test-only).

## Wall times

The successful container run: 10 s end to end (banner timestamps 04:15:43Z → 04:15:53Z;
`TOTAL-ELAPSED 10s`, line 548). Notable step times: clone 1 s, toolchain 0 s (prewarmed image),
`release:build` 4 s (includes the one 31.1 MiB CPython download), acquisition receipt <1 s,
operator-tools <1 s, `sdlc install` 1 s, fixtures ~1 s, uninstall 1 s. Including the two aborted
attempts and image inspection, total host-side wall for the execution phase was about 4 minutes.

## Reproduction

```
docker run --rm -v <primary-checkout>:/src:ro -v <this-dir>/journey-track.sh:/journey.sh:ro \
  asdlc-fresh:latest bash /journey.sh </dev/null
```

The script is self-contained, refuses forward on any step failure (`JOURNEY-STOP`), and pins the
clone to `6c30728677c4e122bf294a887c62fbb63a1b05c5`; reproducing at a different commit requires
editing `PIN` and expects different digests everywhere downstream of S3.
