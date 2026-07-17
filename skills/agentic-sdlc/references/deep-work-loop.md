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
- **Judgment lane** — for un-gated work whose error could pass ordinary gates and silently
  weaken an artifact. Require explicit acceptance criteria and independent review of an
  immutable candidate.
- **Volume lane** — for gated fan-out where a compiler, test, schema, diff, or evidence check
  makes a wrong answer visible. This is the default for cross-checked parallel work.

A `[1m]`-style long-context marker records client context-window and compaction behavior and is
not an intelligence, effort-compliance, or upstream-capacity claim. Route by the blast-radius
lane, never by the presence of a `[1m]` marker.

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
