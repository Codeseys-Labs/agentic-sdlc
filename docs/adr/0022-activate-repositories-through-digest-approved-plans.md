# ADR-0022 — Activate repositories through digest-approved plans

- **Status:** accepted
- **Note:** amended 2026-08-22 (see the amendment at the end of this record). Decision items 1, 2,
  3, and 7 no longer bind: the transaction engine, the tracked `.agentic-sdlc/repo.toml`, the
  machine-local activation receipt, and the write-ready/remediation-ready terminal vocabulary are
  deleted, and the files named in **Relates to** below no longer exist. Items 4, 5, and 6 stand and
  are now carried by `skills/agentic-sdlc/tools/instruction-generator.py`. The **Compliance** and
  **Confirmation** clauses referring to a plan digest, a reviewed plan, or a remediation-ready state
  read as historical prose and must not be cited as current requirements.
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `commands/sdlc-init.md`, `skills/agentic-sdlc/tools/activation-planner.py`, `tests/test_activation_planner.py`, `tests/test_activation_transaction.py`

## Context

Global bundle installation does not make a repository safe for agent work. Greenfield repositories
need an operating baseline, while brownfield repositories already have guidance, trackers,
toolchains, hooks, CI, work, and ownership that must not be overwritten. The current `/sdlc-init`
runbook preserves these concerns, and the activation planner provides transactions for one reviewed
manifest entry. The runbook explicitly says that full greenfield, Seeds, trust, Git, readiness, and
CI composition remain conductor work (`commands/sdlc-init.md:19-41`).

The product needs one portable activation intent and one machine-local evidence boundary without
pretending either is authority or replacing foreign repository contracts.

## Considered options

- **Spray one standard scaffold into every repository.** Rejected because it overwrites brownfield
  policy and confuses file presence with readiness.
- **Keep activation as a conversational runbook.** Rejected because a prose plan cannot be replayed,
  digest-approved, transactionally applied, or independently read back.
- **Assess, compile, approve, apply, and verify a repository-specific plan.** Chosen because it
  preserves existing state while making each owned effect exact and recoverable.

## Decision

1. `/sdlc-init` is an assess-plan-approve-apply-readback lifecycle. Assessment and planning are
   deterministic, offline where possible, and read-only.
2. A tracked `.agentic-sdlc/repo.toml` records portable intent for guidance, queue, decisions,
   gates, worktrees, CI, and writing policy. It is not ownership or machine-readiness proof.
3. A machine-local activation receipt binds the physical checkout or worktree to the approved plan,
   owned paths, hashes, tool identities, and trust state.
4. Greenfield means no relevant operating-contract surface is occupied. Brownfield means at least
   one is occupied. Repository age does not decide the class.
5. Seeds is the default authoritative queue until the operator selects a tracker adapter that
   proves equivalent identity, dependency, acceptance, evidence, and concurrency contracts.
6. `AGENTS.md` is canonical host-neutral guidance. An owned `CLAUDE.md` projects it; foreign
   guidance is preserved until explicit reconciliation.
7. Activation ends as **write-ready**, **remediation-ready**, or refused. Remediation-ready admits
   only named hygiene waves and never claims the repository gate passes.

This decision unblocks a product-level activation compiler and two journey tests. It does not make
the current runbook deterministic or authorize repository writes, trust changes, or queue mutation.

## Consequences

- Positive: greenfield setup and brownfield integration share one explainable lifecycle without
  erasing their differences.
- Positive: portable intent remains reviewable in Git while ownership and trust stay machine-local.
- Negative: activation requires more assessment and conflict handling than copying a template.
- Negative: some brownfield repositories remain in bounded remediation for multiple waves before
  normal delivery can begin.
- **Confirmation:** run the activation planner's focused tests and `mise run check`, then review one
  clean greenfield and one occupied brownfield installed-byte journey. Current tests cover pieces,
  not this complete contract.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0019 | Activation effects require an exact current human grant and cannot be authorized by the plan itself. |
| Depends-On | ADR-0020 | Tool, tracker, trust, and path capabilities need exact admission before write-ready. |
| Relates-To | ADR-0002 | The activated repository uses one pinned `mise run check` gate when that contract is selected. |
| Part-Of | ADR-0028 | This record decides repository activation inside the Claude Code-first product initiative. |

## Compliance

- Assessment and plan commands make no target or user-configuration mutation.
- Apply consumes the exact reviewed plan digest and refuses changed prestate.
- Foreign guidance, tracker state, toolchain files, hooks, CI, and user work are preserved by default.
- Remediation-ready never appears as gate-passing or ready for normal delivery.

## Reversal condition

If installed-byte evidence shows that one manifest and receipt pair cannot represent both
greenfield and brownfield activation without destructive normalization, the activation owner
re-examines the shared lifecycle boundary.

## Amendment — 2026-08-22: the transaction engine is deleted; the three-way verdict and the one-invocation write survive

The reversal condition above never fired, because the engine never ran on a repository. This
amendment retires decision items 1, 2, 3, and 7 and re-homes items 4 and 6 in
`skills/agentic-sdlc/tools/instruction-generator.py`. Deleted in the same change:
`activation-planner.py`, `repository-classifier.py`, `repository-contract.py`,
`repository-contract-writer.py`, `planning-snapshot.py`, `activation-result.py`, the
`scripts/activation_planner.py` loader, and their seven test modules — 21,766 lines whose single
deliverable was one marker-delimited markdown block. Three measured facts decided it.

**The machine-local receipt (item 3) never had a reader.** Its entire production history is 70
records in 151 orphan directories under the operator's own
`${XDG_STATE_HOME:-~/.local/state}/ccodex/activation/`, every one keyed to a `/tmp/tmpXXXXXXXX/repo`
test fixture that no longer exists. No tool, task, gate, hook, CI job, or skill ever read one back:
this repository has no `.agentic-sdlc/` directory and no `repo.toml`, so the tool that activates
repositories never activated the repository that ships it. An evidence record with no reader is not
a control; it is a write-only artifact whose recovery machinery (plane pointers, progress journal,
stage/backup/discard payloads, three `recover` verbs) existed only to bridge two invocations.

**Approve-and-write in one invocation removes the window the plan digest was closing.** Item 1's
digest sealed a plan so that a later `apply` could prove the approved bytes were the written bytes.
That gap is created by the two-invocation shape itself. `apply --target --manifest --entry` now
renders against the live target, prints the unified diff, and writes only when the same invocation
carries `--yes`: there is no plan document to go stale, no single-use grant to replay, and no
approved-then-changed interval to defend. The two residuals it keeps are the ones that survive the
collapse — `O_NOFOLLOW` on the read so a planted symlink at the target refuses at exit 2, and
temp-plus-`os.replace` in the same directory with the parent fsynced, so a crash leaves the old
bytes or the new ones and never a truncation. The statx mount-id binding, the descriptor-relative
parent walk from `/`, and the other-writable and nlink checks are dropped: they defended against a
local attacker who already holds write access inside the repository being handed to coding agents,
and who could simply edit `AGENTS.md` instead.

**The classifier refused every ordinary clone, and nobody noticed because nobody ran it.**
`repository-classifier.py` hand-parsed the Git object store — loose refs, `packed-refs`, raw zlib
objects, entry modes — with no subprocess, so it could claim "provably empty" without trusting git.
Its own prose conceded the gap — "packed history is refused rather than inspected" — and that
concession was the defect: a `git gc`'d repository, which is every ordinary clone, returned
`refuse-and-ask` with "commit ... is not a loose object; packed, absent, and alternate objects are
not walked offline". The replacement asks git. `classify --target` runs `git ls-files -z` over the
contract surfaces plus a working-tree existence check, then `git rev-list --count HEAD` and
`git status --porcelain`, in a constructed environment where no ambient `GIT_*` variable and no
system or global config can change the answer. Packfiles, alternates, and every ref backend git
supports are read correctly because git reads them.

**What is deliberately preserved.** Item 4's class definition, in 25 lines instead of 1,269:
`brownfield` when a guidance, queue, decision, toolchain, hook, CI, or `.agentic-sdlc` surface is
occupied in the index or on disk, and it is named; `greenfield` only when nothing is occupied, the
repository holds at most one commit, and the working tree is clean; `refuse-and-ask` otherwise, each
reason named. All three carry `ask: true`, because **ask-by-default is the policy this record is
protecting** — `greenfield` is a proposal, never a licence to write, and a verdict is advisory
evidence that authorizes nothing. Item 6 is unchanged: `AGENTS.md` stays canonical host-neutral
guidance, `CLAUDE.md` projects it, and foreign guidance outside the markers is preserved byte for
byte. Item 5 (Seeds as the default authoritative queue) is untouched by this amendment.

**What is honestly lost.** There is no longer a replayable plan artifact, no independent machine
readback after a write, and no `remediation-ready` state; a brownfield repository's bounded hygiene
work is now tracked as Seeds, not as a terminal activation state. The rejected option "keep
activation as a conversational runbook" is still rejected: the replacement is deterministic, prints
its diff, refuses without approval, and its evidence is the repository's own Git history rather than
prose. `commands/sdlc-init.md` remains a reviewed runbook for everything around the two verbs, and
it may not claim tool-guaranteed idempotence or wave readiness.

- **Confirmation:** run `tests/test_instruction_generator.py` (the `apply` refusal, symlink, and
  round-trip cases and the `classify` three-way cases, each verified by mutation) and
  `mise run check`. A brownfield fixture must name its occupied surface, and a clean single-commit
  fixture must still ask.
