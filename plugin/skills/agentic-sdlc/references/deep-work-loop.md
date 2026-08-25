# Deep Work Loop (bounded tiered mega-loop)

Use this reference when a single bounded workstream needs the full seven-phase deep-work
shape — sustained framing, mapping, deciding, acting, verifying, critiquing, and
reconciling on ONE unit of work — rather than a whole backlog-zero mission. It consolidates
the loop *shape* in one place and, like the `references/git-change-flow.md` router, carries
**no doctrine of its own** for effort routing, delegation limits, backflow budgets, or
fan-in mechanics: each of those is owned by exactly one authoritative site, named below in a
single hop. Re-teaching a rule here would fork a second copy that drifts.

## The loop shape

```
frame → map/research → decide → act → verify → critique → reconcile
```

- **Frame:** state the exact done condition, constraints, queue state, and allowed blast
  radius. One frame per loop; a settled frame is re-derived and adjudicated by the conductor,
  never silently by a worker (`references/tiered-orchestration.md` owns why scale-setting
  work stays singular).
- **Map/research:** assign read-only mapping with file/line evidence, and resolve only
  load-bearing external unknowns. The full phase gates live in `references/sdlc-loop.md`.
- **Decide:** pick the run shape and the workstream cut, and route effort (below). This is a
  recommendation the conductor adjudicates, not an execution grant.
- **Act:** give each write-capable worker one bounded workstream in its own worktree with an
  artifact and a stop condition. Delegation planes are owned by `references/delegation-planes.md`.
- **Verify:** run the gates that make a wrong answer visible; a null, malformed, truncated,
  or transport-rejected result is failure, not a pass.
- **Critique:** attack stable snapshots on multiple lenses and return classified, seed-shaped
  recommendations. The critique lens never fixes what it finds.
- **Reconcile:** turn every finding into a typed `SeedProposal` for the conductor, run gates
  from the root, and record evidence. Backflow to an earlier phase is bounded (below).

Each phase emits artifacts and recommendations. Nothing in the loop acquires the user's
authority, mutates the queue, or performs an outward effect on its own.

## Artifacts and recommendations only (authority discipline)

- **Seeds: `SeedProposal` only.** Every actionable finding leaves the loop as a typed
  `SeedProposal` for conductor adjudication. The conductor is the sole queue writer; the
  conductor alone mutates Seeds after acceptance evidence is verified. Workers and critique
  lenses never write the queue directly, and the loop keeps **no second queue** of its own —
  a finding that lives only in an uncaptured response is lost work.
- **No publication or integration authority.** The loop never merges, publishes, pushes, or
  deploys, and never mutates the queue itself. An authorized integrator alone performs an
  already-authorized fan-in; humans alone authorize push, publication, PR mutation, merge,
  deployment, credential, and evidence-store operations. A recommendation, gate, or route
  never authorizes an outward action. The worktree fan-in mechanics themselves are owned by
  `references/git-change-flow.md` and `references/worktree-integration.md`.
- **Bounded delegation depth.** Delegation nests to an explicit cap — no unbounded recursive
  delegation. Give each tier a named worker list, keep nesting to one mid-tier at most, and
  respect the WIP caps in `references/mission-loop.md`. Recursion without a bound is a hard stop.

## Effort routing (defer to the model-tier doctrine)

Before any dispatch, load the model-tier-rightsizing skill (`../model-tier-rightsizing/SKILL.md`)
and route by wrong-output blast radius, not task prestige. This reference names the three
operating lanes and defers every exact ID, effort band, and quota fact to that skill and to
`references/tiered-orchestration.md`; it copies no routing matrix.

- **Frontier lane** — solo for scale-setters. A frame, plan, authority analysis,
  cross-system invariant, or final stop/go recommendation runs as a single bounded packet,
  never an unbounded fan-out.
- **Judgment lane** — for un-gated work where a wrong answer can slip past ordinary gates and
  quietly degrade the result. Apply the judgment-tier bar the model-tier skill owns: explicit
  acceptance criteria plus an independent immutable-candidate review.
- **Volume lane** — for gated fan-out where a compiler, test, schema, diff, or evidence check
  makes a wrong answer visible. This is the default for cross-checked parallel work.

A `[1m]`-style long-context marker records client context-window and compaction behavior and is
not an intelligence, effort-compliance, or upstream-capacity claim. Route by the blast-radius
lane, never by the presence of a `[1m]` marker.

## Context discipline: spend the window on purpose

Every brief that dispatches a worker sets a corpus budget before that worker opens a package,
archive, or generated file. Inspect the manifest and export/entry-point list first; never read
a tarball, bundled, minified, or `dist` artifact wholesale. Use targeted search with a small
number of surrounding lines, cap how much of any one source file gets read in one pass, and
locate the symbol before reading only that region of a large file. Obtaining an artifact does
not authorize dumping it whole into context.

Before dispatch, the brief author records: the corpus bound and read plan; which tools are
actually granted and reachable from that invocation path; the real permission/write boundary
(not prose asking the worker not to write); and the model, concurrency, budget, and timeout
assumptions the brief relies on. If any of these is unavailable or unmeasured, rebrief, add an
operator-mediated prerequisite, or mark the run blocked — do not guess and proceed.

This is the same objective the skill-loading format itself follows, at three levels of
disclosure (the pattern is adapted from pi-lab's context-budget skill):

- **Level 1 — metadata.** The `name`/`description` frontmatter loads every session, for every
  installed skill. Budget it as always-on spend: every trigger phrase added to a description
  is billed in every session, forever.
- **Level 2 — instructions.** The skill body (a `SKILL.md`, or a reference file like this one
  once loaded) is read on activation. Keep it small enough to read in one pass; move detail
  that needs a load condition rather than a signpost into level 3.
- **Level 3 — resources.** Files under `references/` load only when a task calls for them, and
  stay unbounded only because the agent has filesystem access. Give each level-3 reference a
  named load condition ("read this when X"), never a bare "see references/ for details".

Target the smallest high-signal set, never the most complete one. Minimal is not the same as
short — a worker starved of a fact it needed has failed too. The discipline is cutting
redundancy, never a prerequisite.

## Operational discipline, each rule earned by an incident

These are execution-level rules for how a worker inside any phase behaves. They govern conduct
within a bounded workstream, not delegation limits, backflow budgets, or fan-in mechanics —
those stay owned by the sites named elsewhere in this file.

1. **File-first, always.** Every worker writes its complete artifact to a named path before
   replying, and replies briefly, naming that path. A worker whose final turn ends without a
   reply (a dropped connection, a truncated turn, a transport error) loses everything not
   already written to disk. Measure a fan-out by artifacts produced, not by replies received.
2. **Set an explicit wall-clock timeout on every dispatch.** A default timeout tuned for a
   short task will not fit a long build; size it from the shape of the work, not from the
   platform default. A timeout detects no-progress; it is not a spend budget and does not
   itself bound cost.
3. **A flag is a switch, not a boundary.** Never accept an env var, config flag, or
   self-declared record field as a safety boundary. A real boundary is something a worker
   cannot itself author: an operator's commit, a recorded probe, an out-of-band gate, or the
   absence of the code path. When a switch is found standing in for a boundary, delete it
   rather than hardening it — a hardened switch is still a switch.
4. **Prove a control by watching it fail.** A control seen only passing is not evidence. Plant
   a violation, observe the refusal, revert, and name the exact seam exercised (the policy
   function, the resolver, the runner's real error path, the reporting channel). A passing
   unit-level probe proves only that unit; the real runner and the operator-visible result
   remain unproven until exercised end to end.
5. **Test with realistic material, not the textbook example.** A gate tested only against a
   canonical placeholder value can look armed while allowlisting exactly the case it exists to
   catch.
6. **One writer per working tree.** Give each concurrent lane its own repository or durable
   worktree, and state in its brief what it must not touch. Two lanes pointed at the same tree
   produce interleaved, unreviewable commits; the worktree/fan-in mechanics themselves belong
   to `references/git-change-flow.md` and `references/worktree-integration.md`.
7. **Check whether another repository or manifest pins what you are about to change** before
   committing a change with cross-repository blast radius. A change that is locally correct
   can still turn a downstream gate red.
8. **Commit after each logical step**, not only at the end. A worker that times out or is
   interrupted mid-workstream should still leave behind everything it had already finished.
9. **Act stays adversarial toward its own plan.** Instruct an implementing worker to refuse a
   wrong step in the plan it was handed and record the correction, rather than execute a plan
   step it can show is unreachable or wrong.
10. **Verify every reviewer citation before acting on it.** If a reviewer cites `file:line`,
    check the file exists and the line says what was claimed before treating the finding as
    real. A citation-checking script narrows the search; it does not replace a human spot
    check, and its own false-positive rate should be stated rather than assumed to be zero.
11. **The conductor — never a worker — allocates finding IDs.** Workers propose
    `PROPOSED-n`-style provisional labels; only the single queue-owning site mints a durable
    ID, matching the "conductor is the sole queue writer" rule above.
12. **Tag every claim with an evidence class** (a listing asserts it, an implementation was
    read with a citation, a command ran and was observed) and mark anything important but
    unestablished as an explicit gap rather than upgrading a guess into a stated fact.
13. **Audit your own repository before surveying the wider ecosystem.** A survey that skips
    capability already present locally will re-discover, at cost, what a `git log` or a local
    doc already recorded.
14. **Bind a tool policy for a read-only role, then verify enforcement on the resolved role** —
    that write, edit, and equivalent mutation tools are actually unavailable to it. A policy
    declared in a prompt or a manifest field is not proof that the runtime enforces it; only
    an observed refusal is.
15. **Classify an empty or truncated worker result before re-firing it.** Re-dispatching an
    identical retry against an unclassified empty result burns spend against the wrong cause.
    The specific taxonomy of causes is host- and runtime-specific; for this bundle's own hosts,
    that taxonomy must be re-derived from observed Task-tool failures on the actual host in
    use, not borrowed from another runtime's internals. Do not invent one here — record it as
    an open gap until it is measured on this host.

Measure your own fleet before quoting anyone else's numbers back at it: cost, empty-result
rate, and timeout rate all rise monotonically with every wave run, so any absolute figure
quoted in prose is stale the moment the next wave runs. Keep a regenerable measurement script,
where one exists for this bundle, as the source of truth rather than a transcribed table.

## Stop conditions are externally adjudicated, never self-graded

A loop's stop condition must be supplied and adjudicated externally — never by the worker's own
judgment, and never by a self-reported status string it authored. This is the strongest
convergent finding across independent sources on loop termination (adapted from pi-lab's
loop-design skill): a worker asked to grade its own completion tends to confidently praise its
own output, and a destructive or irreversible effect gated on a worker's self-reported status
is a switch, not a boundary — the same failure named in the operational-discipline rules above,
recurring at the loop-termination layer.

This governs loops with a verifiable exit criterion, which is the case this whole reference
addresses. A short, one-off task that a worker judges complete or blocked on its own is a
separate, narrower case and is not what this rule constrains.

Two things follow:

- **Every loop needs a written kill criterion before any code runs**, not only an iteration
  cap. State the measured threshold at which the loop is retired rather than tuned, name the
  metric and the window, and — this is the part most often missing — **name the instrument
  that measures it**. A kill criterion with no named instrument is decoration: one that is
  never evaluated cannot retire anything.
- **Never widen a threshold just to keep a loop running.** Escalation — stopping and handing
  the loop to the conductor for adjudication, or to a human — is the intended behavior when a
  bound is hit, not a symptom to route around.

Bound every loop on all three axes, not a success predicate alone: an iteration/pass ceiling, a
wall-clock ceiling, and a spend ceiling checked before a dispatch fires, not only after it
returns. A ceiling hit without completion is an honest stop with resume hints — see "Backflow
is bounded" below — never a silent failure, and never grounds for a worker to declare itself
done anyway.

## Integration points

- **Seeds** — the loop touches the queue only through advisory `SeedProposal` values; the
  phase-gate and reconcile contracts are in `references/sdlc-loop.md`, and the autonomous
  backlog framing is in `references/mission-loop.md`.
- **The sdlc roles** — the macro conductor owns loop control: it holds the frame, adjudicates
  every advisory Map/ResearchBrief/SeedProposal/Candidate/ReviewFinding, and keeps the queue.
  Role composition and the native-first capability ladder are owned by
  `references/tiered-orchestration.md`.
- **The git change flow** — every worktree/stacked-PR question routes through the
  `references/git-change-flow.md` router in a single hop.

## Backflow is bounded

A verdict may recommend one scoped re-entry to an earlier phase; the conductor decides
whether to re-enter, preserves prior artifacts, and respects the global pass ceiling and
per-phase re-entry budgets defined in `references/tiered-orchestration.md`. A ceiling hit
without completion is an honest stop with resume hints, not a silent failure.

`skills/agentic-sdlc/tools/pass-budget.py` is the executable form of this bounded-backflow
doctrine: a conductor-owned ledger, not a host enforcement mechanism, that charges a phase
and the global counter together, persists the charge before the caller can act on the answer,
and returns a named refusal once a ceiling (global 6; frame 1; discover 2; research 2; plan 2;
act 3) is exhausted. The refusal is advice the conductor must choose to obey — the tool cannot
itself stop a delegation the conductor makes anyway.
