# Research Team (evidence-graded multi-agent research)

Use this reference when the mission's Research phase is itself a PROJECT — sustained
investigation with claims, experiments, and reviews — rather than a bounded lookup.
For a bounded research question, a delegated research pipeline (see
`references/tiered-orchestration.md`) is enough; this reference is for standing research
efforts.

**The full implementation ships IN this bundle** as the sibling skill
`skills/codex-research-os/` — its `scripts/install_research_os.py` scaffolds the complete
repo-native OS into any target repo (17 role TOMLs incl. director/scout/novelty-auditor/
theorist/counterexample-hunter/formalizer/experimentalist/benchmark-and-data-engineers/
ablationist/replication-and-adversarial-reviewers/synthesis-writer/librarian/safety,
plus ledgers, workflows, schemas, and Make gates). Use the installer for a standing
effort; use this reference for the distilled principles when composing a smaller roster
by hand.

## The evidence ladder (claim lifecycle)

Every claim carries a rung, tracked in a ledger (`research/claims/` or Seeds metadata):

```
idea → conjecture → small-case support → experiment support → replication support
     → adversarially reviewed → formally specified → proved / robustly reproduced
```

**Promote slowly, downgrade quickly** — a failed assumption, baseline, reproduction, or
novelty check drops the claim immediately. The critique team grades findings against the
ladder, not just blocking/non-blocking.

Ledger invariants (machine-checkable; wire into gates):
- No meaningful untracked claims — ledger or it didn't happen (the research twin of
  seeds-first).
- No improvement claim without a baseline (or an explicit baseline plan).
- No novelty claim without a novelty review; no empirical promotion without a
  replication review; no important synthesis without an adversarial review.
- Negative results are RECORDED, never discarded — they're the cheapest future-work
  filter the team owns.

## Role boundaries (separation of powers)

Roles are narrow, and each carries an explicit CANNOT — no agent approves its own work:

| Role | Does | Does NOT |
|---|---|---|
| director (conductor) | assigns loops, enforces gates, owns next-action | do the research itself |
| literature scout | maps prior art | declare novelty |
| novelty auditor | checks occupancy vs prior art | generate hypotheses |
| theorist | proposes hypotheses/mechanisms | approve them |
| experimentalist | designs/runs experiments, logs evidence | declare publication-readiness |
| replication reviewer | re-runs/verifies | fix what it finds |
| adversarial reviewer | attacks claims | fix them |
| synthesis writer | summarizes VALIDATED evidence only | introduce new claims |

Compose the roster to fit — a small effort might collapse to
scout / theorist-experimentalist / adversarial-reviewer / synthesizer — but keep the
CANNOTs: the attack role never fixes; the writing role never originates; the proposing
role never approves. Map onto the bundle's planes: roles = provider-native role agents
(see `agents/`) by default; the
director = the conductor; reviews = the concurrent critique team graded by the ladder.

## The one-loop discipline

Each research loop does ONE meaningful unit of work: director picks the unit → assigns a
specialist → specialist produces artifacts → validation gates run → memory/ledger updated
→ **ends with a concrete recorded next-action**. The next-action file is the resume point
across sessions/machines — a research mission interrupted anywhere restarts by reading it.
(This is the mission-loop's checkpoint discipline applied per-loop instead of per-wave.)

## Greenfield vs brownfield loops

- **Greenfield** (broad new area): define area → generate ideas → score each on novelty ×
  feasibility × falsifiability × impact × cost → scout literature → audit novelty → pick
  ONE candidate → run the *cheapest decisive* experiment or proof check → review →
  kill / iterate / pivot / promote.
- **Brownfield** (existing code/papers/benchmarks): map the repo → find build/test/bench
  commands → reproduce or define the baseline FIRST → inventory existing claims
  conservatively → find gaps → cheapest decisive test → compare to baseline →
  replication + adversarial review → update ledgers.

The shared spine: **the cheapest decisive experiment** — always ask "what is the least
work that could kill or promote this claim?" before designing anything bigger.

## Gates as executables, not prose

Encode the invariants as runnable checks (Makefile targets or scripts) the conductor runs
before any synthesis ships:
- `validate-claims` — ledger entries well-formed, every promoted claim has its required
  reviews.
- `review-gates` — flags: promoted empirical claims without replication review;
  proof-like claims without formalization; novelty claims without novelty review.
- `validate-agents` — role configs contain only known keys, names match files, and any
  explicit `model` pins are ALLOWLISTED. **No decorative model pins**: by default omit
  `model` so roles inherit the host's configured default — a pinned model that doesn't
  exist on the host fails silently or 404s.

This mirrors the bundle's validate-bundle.sh philosophy: silent failure modes get a
gate, not a guideline.

## Wiring into the mission loop

In `references/mission-loop.md` terms: a standing research effort is ONE research track
(WIP cap: ≤2), run by a provider-native director/supervisor. Its claims ledger is the research twin of the
Seeds queue; its review gates are the critique team's rubric; its next-action file is the
checkpoint. Research findings that imply code work
become Seeds; code findings that imply research questions become ledger ideas. The two
queues cross-pollinate but never merge.
