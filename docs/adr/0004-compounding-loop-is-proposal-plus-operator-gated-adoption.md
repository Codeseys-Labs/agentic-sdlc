# ADR-0004 — the compounding loop is harness proposal + operator-gated adoption, never unmeasured self-editing

- **Status:** accepted
- **Date:** 2026-08-06
- **Deciders:** operator (decision), agent (evidence and drafting)
- **Relates to:** `pi-lab/docs/plan/v1/ground-harnessx.md`, `AGENTS.md`
  ("A passing gate is evidence only")

## Context

Whether an agentic-SDLC harness may edit its own pipeline, tool registry, or
gate configuration autonomously — a "self-improving harness" — is a decision
that has been re-derived from scratch multiple times across sessions in this
ecosystem, because no record of it existed. The sibling `pi-lab` repository
did the grounding work directly against the strongest available reference
implementation, HarnessX (a published self-evolution harness with a partially
released codebase), and reached a specific, falsifiable line. That grounding
is adopted here rather than re-derived.

**The mechanism, in one sentence** (`ground-harnessx.md` PROPOSED-2): HarnessX's
self-evolution is *an LLM rewriting a declarative harness manifest, constrained
by (a) a fixed, human-committed harness for the evolver itself, (b) structured
per-task traces whose correctness field the evolver cannot author, (c) a set of
deterministic post-flight gates, and (d) an outer loop that re-runs a fixed
benchmark and auto-reverts on measured regression. Remove (d) and it is not
evolution, it is unmeasured self-editing.*

**Why the measured loop does not transfer here, and why the proposal-only
shape does** (PROPOSED-6, PROPOSED-7, PROPOSED-8): HarnessX's outer loop
requires a fixed, binary-verdict task set that can be re-run every round —
its own paper reports 100M–175M tokens and roughly $1,500 per benchmark
experiment to do this. A repository's own development work has no such
re-runnable task distribution: a change, once made, cannot be re-run for
attribution the way a held-out benchmark can. Building the accept/revert
search loop without that oracle would produce exactly the failure mode
PROPOSED-6 names: *"measured self-evolution" degrades to "unmeasured
self-editing."* What *does* transfer, and cheaply: typed per-task run
records, a changeset diff of what the harness proposal would change, a
retro/critique skill, and prediction-before-outcome journal entries — all
inert until an operator adopts them (PROPOSED-8).

**The two numbers that make the boundary non-negotiable, not merely
conservative:**

- **HarnessX Table 6**: the elaborate four-stage AEGIS evolver (Digester →
  Planner → Evolver → Critic) scored 87.4% at 107.8M tokens; a single-agent
  Claude Code SDK evolver scored 86.4% at 123.1M tokens. The 1.0-point gap is
  inside one standard error (~3.3pp at n=103). The paper's own conclusion:
  gains derive primarily from the harness's *infrastructure* — typed
  components enabling isolation, structured traces enabling diagnosis — "rather
  than the evolver's internal architecture." Effort spent on an elaborate
  autonomous evolver, instead of on trace structure and gate determinism, is
  effort spent on the part the evidence says did not matter.
- **The −24.3pp peak-to-final collapse**: HarnessX Table 5, GAIA/GPT-5.4 over
  15 rounds, peaked at 73.8% (round 4) and finished at 49.5% — a drop the
  paper itself attributes to catastrophic forgetting, ruled distinguishable
  from evaluation noise (peak−final exceeds the measured 95% confidence
  interval by nearly 3×). Every headline number the paper and its own README
  report is a **peak**, not a **final**, state. A harness that reports its
  best-ever round rather than its current round can look like it is
  compounding while it is actually regressing.

**The authority bug HarnessX itself commits, and must not be copied**
(`ground-harnessx.md` §5–6): HarnessX's novelty gate refuses to re-propose a
hypothesis whose prior-round outcome was `reverted` — but that outcome field
lives in `memo_path`, a file the evolver itself has write access to. An agent
can edit a prior round's own verdict from `reverted` to `accepted` and walk
straight through the gate meant to stop it — structurally identical to an
authority field being self-declared inside a path the same agent can write.
The one control HarnessX gets right is unrelated to that gate: the
ground-truth answer for each task is withheld entirely from the agent's
context (absence of data, not a flag it could flip).

## Decision

1. **The evolving agent (harness proposer) may author proposals, journals, and
   ADR drafts autonomously.** This includes retro/critique content, prediction
   journal entries, and changeset-diff summaries of what a change would do.
   All of it is inert until adopted — it is evidence for a human, not a
   mutation of anything the gate depends on.
2. **Pipeline configuration, tool registry entries, and gate configuration
   require an operator commit.** No agent-authored change to
   `mise.toml`'s task graph, `lefthook.yml`, `.github/workflows/`, or any file
   `scripts/validate_bundle.py` treats as gate-defining may land without an
   explicit human commit approving it. This mirrors the "REQUIRES AN OPERATOR
   COMMIT" boundary drawn in `ground-harnessx.md` PROPOSED-6.
3. **Gates and their inputs are untouchable by the agent that benefits from
   them.** The outcome/authority field a promotion decision depends on must
   never be writable by the same agent whose proposal it is judging — the
   fix for HarnessX's own novelty-gate bug. Concretely in this repository:
   `mise run check`'s dependency graph, the frozen `lefthook.yml` bytes, and
   the CI workflow file are not surfaces an agent proposal may modify to make
   its own proposal pass.
4. **This repository's re-runnable oracle is `mise run check`.** It is a
   per-change structural gate (validate/test/self-test/secrets), not a
   fixed re-runnable task distribution with binary per-task verdicts — the
   load-bearing disanalogy `ground-harnessx.md` names as the reason the
   measured accept/revert search loop does not transfer here. `mise run
   check` is nonetheless the real, named, re-runnable check this bundle has,
   and any claim of "this change improved the harness" must be checkable
   against it rather than against an unfalsifiable self-report.
5. **Any metric this bundle reports about its own improvement must report
   FINAL state, never best-so-far.** A round, a proposal, or a session that
   reports its peak result while its current, adopted state is worse is
   making the exact claim the −24.3pp collapse falsifies. Where a change is
   measured at all, the number that ships is the number that is currently
   true, not the best number ever observed.

## Consequences

- Positive: this closes a decision that was otherwise being re-argued from
  first principles in multiple sessions — the record now exists and cites its
  grounding directly.
- Positive: the operator-commit boundary composes with `AGENTS.md`'s existing
  doctrine ("a passing gate is evidence only; it does not authorize an
  outward effect") rather than adding a second, competing authority model.
- Negative: this bundle does not get an autonomous self-improvement loop
  in the HarnessX sense — no auto-revert, no round-scored search, no claim of
  measured compounding progress across sessions. That capability requires a
  re-runnable, binary-verdict task distribution this repository does not have
  and is not proposing to build. `pi-lab`'s own `ground-harnessx.md`
  PROPOSED-9 names the honest place for that loop: a repo with real
  re-runnable test suites of its own, not a user's arbitrary project.
- Negative: proposal-only adoption is slower than autonomous adoption by
  construction — every pipeline/tool/gate change still needs a human in the
  loop. That slowness is the boundary, not a defect in it.
- **Confirmation:** `mise run check` exists and is runnable today; any future
  claim that a harness proposal "improved" this repository must name a
  specific, reproducible before/after result against that command, and must
  state the final observed state rather than a peak intermediate one.

## Reversal condition

This ADR is reopened only if a re-runnable, binary-verdict, per-change task
distribution is built and measured for this bundle specifically — not merely
proposed or benchmarked elsewhere — at which point a new ADR may define a
bounded, gated accept/revert loop against that oracle, citing the measured
task distribution by name. Until that artifact exists and is measured, the
proposal-only boundary in this ADR holds.

This record is evidence for a conductor to cite; it authorizes no pipeline
change, tool-registry change, gate-configuration change, or other outward
effect on its own.
