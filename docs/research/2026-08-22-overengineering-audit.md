# Overengineering audit — 2026-08-22

Seven-agent audit (five deletion-pressure audits, one Bun CLI spike, one safety-rebuttal
synthesis). The complete structured output, including every per-subsystem replacement design,
risk statement, and the spike's raw measurements, is the adjacent
`2026-08-22-overengineering-audit.json`. The demolition plan is queued as Seed
`agentic-sdlc-3c90` (epic, P1, operator ratification required); the Windows argv mechanism is
Seed `agentic-sdlc-7123`. This file is the dated snapshot of the verdict; the queue is the
living record.

## Verdict

Decisively overengineered. 210,528 tracked lines deliver 4,309 lines of payload (12 SKILL.md
files plus agents/commands/workflows) — a 46:1 machinery-to-payload ratio. The five largest
files are all machinery. 89,515 test lines test the machinery; zero lines test whether a skill
is any good. The diagnosis is precise: disciplined machinery defending adversaries its own
docstrings disclaim (the same-UID racer is declared out of scope in three places) on platforms
where its witnesses measurably carry no information (20/20 btime collisions on the CI runner).
Roughly 3–5k lines are real controls; roughly 75,000 are not.

## Ranked deletions (execute in order; each rank carries its ADR supersession and seed re-dispositions)

| # | Subsystem | Lines back | Replacement | Named survival obligations |
|---|---|---|---|---|
| 1 | Wave/journal/verdict stack (6 tools + tests; drift-classifier/auto-envelope cascade decided in the same ADR) | ~27,500 (+~10,500) | `docs/evidence/waves/<id>.md` template + 4 lines in `commands/sdlc-wave.md` | Four rules into SKILL.md prose; supersede ADR-0025, amend ADR-0024; seeds 8749/4a07/a2f8/3b5e/4d2b |
| 2 | Activation planner + classifier + contract + snapshot + result | ~21,500 | `instruction-generator.py` gains `apply` (~45 lines); ~25-line git three-way classifier | Keep greenfield/brownfield/refuse-and-ask, ask by default; amend ADR-0022; seeds 0ec3/f194/4206 |
| 3 | Release-candidate acquisition engine + run-readonly bridge | ~12,600 | `git archive` builder (~120), tag-release CI job (~30), mise github/http backend in `mise.lock`, receipt shim (~40) in the SAME change | Shim re-hashes resolved root against `manifest.json` (the c5ea877 lesson); keep the honesty disclosures; seeds c1f5/ba1a/db15 close by subject removal |
| 4 | Install-lifecycle witness/settlement/journal/recovery/migration layers | ~6,600 | The `install_operator_tools.py` shape; keep the ~1,530-line core | Update `ccodex_sdlc_install.py:1782` imports; weaken AGENTS.md preservation doctrine from physical to byte identity honestly, same commit; seed 249d closes by deletion |
| 5 | Validator shrink to ~655 lines / 8 checks (LAST — earlier ranks delete policies it validates) | ~7,300 | One file: skills, workflows, agents, manifests, versions, `bash -n`, secrets, reviewer-authority regex | Plus the mermaid supply-chain digest pins (ADR-0006) the audit's own keep-list missed |

Total: ~75,500 lines (~36% of the repository), payload untouched.

## Bun rewrite: no. Harvest one component later.

The spike killed the premise empirically: the Windows argv defect is PowerShell 5.1
CreateProcess marshalling that corrupts argv for every native executable identically — the
compiled Bun binary received the same stripped-quote JSON the bash path did, and a native
binary additionally enters MSYS2 path mangling a `.sh` file is immune to. The rewrite would
have shipped the same bug plus a 370 MiB five-platform artifact (vs 120 KB of bash), an
unpinned compile-runtime supply chain (>99.99% of executed bytes), an unowned macOS signature,
a `strip` landmine that answers `--version` with exit 0 then fails every verb, no armv7 target,
and a 2.8x slower startup than the 2,025-line bash script. The real line saving is ~400,
because 835 bash lines are measured-forensics comments that must be ported verbatim.

The one harvest, after the deletions: the settings classifier as a digest-pinned Bun helper
invoked by the existing bash launcher — 5.3x on the real settings gate (130ms → 24ms), retires
jq and ADR-0020's resolution problem and the two-regex-engine burden, and buys the argv
observability that turned a "mechanism unknown" into a ten-minute diagnosis. The spike archive
is preserved outside the repo (operator state, `bun-cli-spike-20260822.tar.gz`).

## Sequencing

Merge the branch first so demolition reviews against a stable base. The audit recommends an
ordinary merge over a squash because seeds and the forensics doc cite constituent SHAs and
`c5ea877`'s commit message is a trust-boundary evidence record; if squashing, preserve the
branch ref and carry a SHA map in the squash message. The three in-flight platform-polish
worktrees are parked unmerged pending ratification: `5ce7-dirfd` (100% deletion targets),
`5ce7-posix-imports` (~80%), `249d-recovery` (rank-4 subject). Rank 1 alone is the macOS
platform fix (~238 of the macOS CI failures trace to `wave-journal`'s Linux-only `renameat2`,
seeds b284/e8a9). Then the Bun classifier helper, digest-pinned. Then feature branches from a
~135k-line main.
