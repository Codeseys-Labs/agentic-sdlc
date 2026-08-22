# ADR-0022 — Activate repositories through digest-approved plans

- **Status:** accepted
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
