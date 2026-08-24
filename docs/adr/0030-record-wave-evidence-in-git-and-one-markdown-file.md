# ADR-0030 — Record wave evidence in Git and one markdown file

- **Status:** accepted
- **Date:** 2026-08-22
- **Note:** amended 2026-08-23 (see the amendment at the end of this record). The six-outcome
  wave vocabulary the deleted `wave-verdict.py` carried is restored to the operative doc
  surfaces; every deletion this record decided stands.
- **Deciders:** operator (ratification of the demolition plan recorded as `agentic-sdlc-3c90`); agent (evidence and drafting)
- **Relates to:** `skills/agentic-sdlc/SKILL.md`, `commands/sdlc-wave.md`,
  `docs/evidence/waves/TEMPLATE.md`, `skills/agentic-sdlc/references/readiness-composition.md`,
  `docs/research/2026-08-22-overengineering-audit.md`

## Context

ADR-0025 decided that wave execution binds to immutable typed planning generations, and eight tools
were built to implement it: `wave-plan-compiler`, `wave-plan-admission`, `wave-submission`,
`wave-journal`, `wave-verdict`, `sdlc-observability-projection`, `drift-classifier`, and
`auto-envelope`. Measured at 2026-08-22, that machinery was 35,820 tracked lines — 16,288 of tool
source and 19,532 of tests — and the record of what it delivered is short.

One wave has ever been recorded: `wave-f83f-w1` on 2026-08-21, which produced 28 committed JSON
artifacts totalling 462 lines to describe commit `8958d6c`, a 62-line bugfix. That wave was executed
to satisfy its own exit artifact, not because a wave needed it. `sdlc-observability-projection.py`
(1,928 lines of source, 3,657 of tests) never produced output at all: no document carrying
`agentic-sdlc/observability-projection@2` exists anywhere in `docs/` or `.seeds/`, and the
`projection.json` in the one wave's directory carries `agentic-sdlc/wave-journal-projection@1`,
written by a different tool.

Nothing invokes any of it. `mise.toml`, `lefthook.yml`, `.github/workflows/`, `commands/`,
`workflows/`, `agents/`, `policy/`, and `scripts/validate_bundle.py` contain zero references to the
eight module names; the only consumers were seven lines of `skills/agentic-sdlc/SKILL.md` prose and
one line of `references/readiness-composition.md` instructing an agent to run them.

It also cost more than it returned. Seeds `agentic-sdlc-b284` and `agentic-sdlc-e8a9` measured
`wave-journal.py`'s Linux-only `renameat2` as the largest macOS failure cluster in CI run
32554149554 — 172 occurrences rising to roughly 238 once every fixture built on journal init
inherited it across four suites — because a host that can never hold the syscall received an exit 4
"effect unknown" over bytes that were never staged. That specific escalation was repaired in this
tree before this record: the capability probe now runs in `_publish` before the first byte is
staged, and the affected tests skipped on a libc symbol probe. The honest residual was therefore not
238 live failures but a Linux-only module, six capability skips, and the maintenance stream that
produced them; six of the stack's nineteen closed seeds existed only to close residuals its own
adversarial reviews had raised against it.

The deciding argument is what the machinery could not answer. `wave-verdict.py`'s own RESIDUALS
conceded that its artifact condition "hashes declared artifacts in the target tree as it is now; no
Git snapshot, commit, or merge-base is verified" and that "freshness is underivable: a stale but
internally consistent artifact set derives its state by construction." Git already supplies
content-addressed, ordered, authored, tamper-evident history over exactly those facts. The stack
rebuilt a weaker version beside it: nothing locks, concurrency is documented as unsupported, the
hash chain is detection rather than prevention, and it is explicitly not safe against a same-UID
racer — which is the only adversary that matters, because the conductor being audited is that user.

## Considered options

- **Keep the stack and port its Darwin primitive.** Rejected because it pays platform-portability
  work on 35,820 lines with one recorded use, no gate consumer, and no answer to the freshness
  question the same lines concede they cannot answer. Polishing a subsystem scheduled for deletion
  is the cost without the capability.
- **Delete the stack and build a ~120-line derivation script that parses the markdown and prints
  accepted/blocked.** Rejected for now because it would be a second mechanization with one wave of
  evidence behind it. It becomes worth writing when a second wave exists and reading the file by eye
  has actually failed.
- **Delete the stack, keep the rules, and read the evidence out of Git.** Chosen because every fact
  the stack derived is already recorded by something the repository trusts for other purposes, and
  because the four load-bearing rules are stronger as rules a reader enforces than as checks the
  audited party may decline to invoke.

## Decision

1. A wave's evidence is one markdown file, `docs/evidence/waves/<wave-id>.md`, copied from
   `docs/evidence/waves/TEMPLATE.md`. It records the node table (node, role, resolved model id,
   disposition, commit, reviewed-by), the operator's verbatim dated approval as a blockquote, the
   integration commit, and the `self_digest` of the gate receipt produced on the merged head.
2. The wave-effect readings are Git's own: `git log --format='%H %s' <base>..<branch>` for what a
   node did, `git show --stat <integration-commit>` for the declared outputs anchored to a commit, a
   `scripts/gate_receipt.py` receipt recorded on the merged head, and the two-line reading that the
   reviewer is not the implementer and that the approval's date precedes the integration commit's
   committer date. `commands/sdlc-wave.md` step 8 names all four.
3. The four rules are doctrine in `skills/agentic-sdlc/SKILL.md` under Wave Acceptance Rules: no
   self-review; approval is dated before the fan-in; the gate passes on the merged snapshot; a
   worker summary is never acceptance evidence. They are the surviving content of ADR-0019's
   approval-before-effect doctrine at the wave surface.
4. The eight tools and their eight test modules are removed. The six named by ADR-0024 and ADR-0025
   go on the record above; `drift-classifier.py` and `auto-envelope.py` go with them, decided here
   rather than left orphaned, on this evidence: `drift-classifier.py classify` requires a sealed
   `agentic-sdlc/wave-plan@1`, whose only producer in the repository was `wave-plan-compiler.py`;
   and the only reader of either tool's output — `agentic-sdlc/drift-classification@1` and
   `agentic-sdlc/auto-envelope@1` — was `sdlc-observability-projection.py`. With the six removed,
   one tool cannot be given a valid input and neither has a consumer. `auto-envelope.py` is not
   deleted for consuming a drift classification: its `admit-transition` inputs are both
   caller-authored, and its `failed-drift-classification` stop rule is recorded in its own docstring
   as a residual it cannot settle. It is deleted because it is the sole implementation of ADR-0025
   decisions 4 and 5, which this record supersedes, and because nothing reads what it writes.
5. `docs/evidence/waves/f83f-w1/` stays as committed bytes. It remains readable JSON; it stops being
   re-derivable, and that is accepted.
6. Nothing here becomes a gate leaf. A complete wave evidence file is evidence only.

## Consequences

- Positive: the wave-effect question that mattered — is this evidence about the tree that was
  actually merged — is answered against a commit instead of against the tree as it happens to be.
- Positive: 35,820 lines leave the repository, including the largest producer of the macOS
  capability-skip surface and its own residual-generating maintenance stream.
- Negative: the repository loses its only mechanical answer to "was the approval recorded before the
  merge, and was the reviewer a different node than the implementer?" Those become rules a reader
  enforces. Against a same-UID forger the strength is unchanged, because the forger could write the
  JSON chain too; against ordinary drift and haste it is weaker, and a reader has to actually look.
- Negative: the two artifacts in `docs/evidence/waves/f83f-w1/` that the deleted tools derived can no
  longer be regenerated from their inputs.
- Negative: a hand-written record can be left incomplete in a way a required CLI argument could not.
  The template answers this only by naming `unknown` as the honest value for a blank.
- **Confirmation:** `mise run check` (its `validate` leaf enforces the skill's own reference
  integrity) plus review of the four named readings against one real wave's evidence file. Whether a
  wave's four rules actually held is a review reading, not a mechanical check, and this record does
  not claim otherwise.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Supersedes | ADR-0025 | Immutable typed planning generations, the deterministic compiler, digest-bound admission, drift classification, and the AutoEnvelope are withdrawn; the plan-review intent they served is met by the recorded plan plus Git's own history. One rule is NOT withdrawn: decision 4's requirement that scope and authority changes return for human disposition is ADR-0019 doctrine, and `mission-contract.py`'s four non-waivable stop conditions still carry it. Citations of ADR-0025 for that rule remain correct as its origin. |
| Refines | ADR-0024 | Narrows decision 6 only: completion still requires acceptance evidence, qualifying gates, disposition of blocking findings, and adversarial review — those are now read from Git and one markdown file rather than derived as a terminal verdict document. Decisions 1 through 5 stand. |
| Depends-On | ADR-0019 | The approval-before-effect rule survives as SKILL.md doctrine; nothing here creates or broadens human authority. |
| Depends-On | ADR-0023 | The one wave's committed artifacts are preserved rather than deleted, as the evidence-preserving profile requires. |
| Part-Of | ADR-0028 | Decided inside the Claude Code-first product initiative, as rank 1 of the demolition plan ratified in `agentic-sdlc-3c90`. |

## Compliance

- No file under `skills/`, `scripts/`, `commands/`, `workflows/`, `agents/`, or `policy/` invokes,
  imports, or instructs running any of the eight removed modules; the three files that still name
  them (`skills/agentic-sdlc/references/readiness-composition.md`,
  `skills/agentic-sdlc/tools/worktree-custody-preflight.py`, `scripts/gate_baseline.py`) name them
  only as removed by this ADR. A fourth, `skills/agentic-sdlc/tools/activation-result.py`, carried
  the same past-tense record until the ADR-0022 amendment deleted it in the same landing.
- Every wave that claims acceptance has a `docs/evidence/waves/<wave-id>.md` naming an integration
  commit and a gate-receipt `self_digest` recorded on that commit.
- No wave evidence file lists the same node as both implementer and reviewer of one workstream.
- Every approval blockquote's date precedes its integration commit's committer date.
- `docs/evidence/waves/f83f-w1/` is unmodified.

## Reversal condition

If three waves within one release record acceptance in the markdown file and a later reader finds
that a rule was violated in a way a sealed document would have refused — a reviewer equal to its
implementer, an approval dated after the merge, or a gate receipt from an unmerged head — the wave
owner rebuilds the mechanical check as the ~120-line derivation over this file, and not as a second
document protocol.

## Amendment — 2026-08-23: the six-outcome wave vocabulary is restored; it was narrowed here without being named

This record deleted `wave-verdict.py` and, with it, silently narrowed the wave-outcome vocabulary
from the six values the product spec closes — `accepted`, `remediation-progress`, `blocked`,
`aborted`, `failed`, `unknown-effect` (Implementation Decision 61 at
`docs/plans/claude-code-first-harness/agentic-sdlc-product-spec.md:361-362`, stories 85 and 94 at
spec:155 and spec:164) — to the three that survived in `skills/agentic-sdlc/SKILL.md`'s Reconcile
step and `docs/evidence/waves/TEMPLATE.md`. The Consequences above name every other loss; this one
went unnamed, and that silence is the defect this amendment repairs. The narrowing was also
incoherent with what this record itself retained: the Relationships table keeps
`mission-contract.py`'s non-waivable `unknown-or-partial-effect` stop condition, so the mission
plane was required to stop on a state the wave plane could no longer record — a wave that died
mid-fan-in had no honest word except `blocked`, indistinguishable from an ordinary
safe-to-remediate block. `CONTEXT.md`'s "Wave outcome receipt" entry kept all six values
throughout, so three surfaces gave three answers.

Restored on 2026-08-23, as vocabulary only: `TEMPLATE.md` gains one wave-level `outcome` field
closed at the six spec values, with the blank case failing closed (an absent outcome is a named
gap, never an assumed `accepted`), and SKILL.md's Reconcile step states the six with the two
load-bearing precedence rules from the deleted docstring — `unknown-effect` dominates and is never
talked down, and an ended state overrides completion evidence. The third precedence rule (two
sealed conductor records disagreeing between `failed` and `aborted` refuse to `blocked`) is
deliberately not restored: it adjudicated between the sealed records of a crashed-and-resumed run,
and that two-record protocol died with the stack this record deleted. Everything else here stands
unchanged: the eight tools stay deleted, nothing becomes a gate leaf, and the ~120-line derivation
script stays behind the reversal condition above.
