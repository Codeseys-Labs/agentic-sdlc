# Tiered Orchestration (model tiers, backflow, and the CAO/cmux hierarchy)

Use this reference when composing a full mission run — assigning MODEL TIERS to stages,
bounding BACKFLOW (later stages re-entering earlier phases), and choosing WHICH
orchestration layer runs each piece. Distilled from a proven tiered deep-work-loop
practice (multi-million-token runs); remade here for the bundle's CAO/cmux stack.

## The multiplier principle (where the frontier model goes)

Agents are not interchangeable. Reserve the scarcest/strongest tier for
**scale-setters** — decisions that multiply:

- **Frame/Decompose** (multiplies FORWARD: every later token is spent inside this frame)
- **Plan** (its `workstreams[]` IS the worker fleet's work list)
- **Verdict** (multiplies BACKWARD: gates whether a whole extra round happens)
- **Mid-loop triage rulings** (patch-vs-redo; one wrong call = N workers of rework)

**Litmus test:** does this agent's output appear in a later stage's work list, loop bound,
or branch condition — or will later stages treat it as settled truth without re-deriving?
If yes → scale-setter: run it SOLO on the strongest tier. If its output is one input among
peers to a synthesis → the workhorse tier. Budget ~2–4 scale-setter points per loop;
more than that, collapse them (one judge over panel outputs beats N frontier critics).

Everything else splits two ways:
- **Judgment volume** (code comprehension, implementation, reviews, drafts): the strong
  workhorse tier, 3–8 parallel.
- **Mechanical glue** (reconcile builds, inventories, formatting, gate re-runs): the cheap
  tier — anything fully checked by a compiler/test/diff, where wrong = visible = retry.

Secondary test: if this agent is wrong, does the run **derail** (frontier), **degrade**
(workhorse), or just **retry** (cheap)?

In the bundle, tier assignment is concrete: CAO profiles carry `model:` frontmatter
(per-worker pinning, see `references/cao-operations.md`); Claude Workflow stages carry
`model:` per agent() call; codex roles carry `model`/`model_reasoning_effort` in the TOML.
The full four-tier policy — quota math, the decision ladder ("if this agent is wrong, does
the run derail / degrade / just retry?"), alias plumbing, and concurrency budgets — ships
as the sibling skill `skills/model-tier-rightsizing/` (re-derive its worked quota table per
account).

## Scale-setter survival rules

1. **Small in, small out.** Never interpolate huge upstream state into a frontier prompt —
   persist artifacts to disk, have the agent Read them; ask for a SMALL decision object
   (verdict + pointers), with big artifacts Written to disk incrementally.
2. **Fallback ladder, never a bare throw.** A scale-setter that stalls or errors must not
   kill a long run: retry once, then substitute the workhorse tier. Keep the STRUCTURE
   (solo scale-setter points) even when the model behind them changes.
3. **Interactive runs:** the conductor session already runs on the strong tier — pull the
   highest-stakes verdicts into the main loop (read the disk artifacts, decide yourself)
   instead of spawning a frontier agent.

## The layer map (which mechanism runs which piece)

The bundle offers FIVE nested delegation layers. Assign by lifetime + visibility need:

| Layer | Runs | Use for |
|---|---|---|
| **Conductor** (interactive session or CAO macro-orchestrator profile) | frame, plan adoption, verdicts, Seeds/merge ownership | All scale-setter decisions |
| **Provider-native fan-out** (Claude Workflow/subagents; codex role subagents) | in-conversation phases: discovery, review panels, research | Work whose results the conductor consumes THIS turn |
| **CAO sessions** (supervisor→worker, mixed engines) | long-lived waves, the CONCURRENT CRITIQUE TEAM, cross-CLI fleets | Work that outlives the turn or mixes engines; drive via cao-ops-mcp tools or `assign`/`--async` |
| **CAO workers' own subagents** (a worker profile with role: supervisor, or a Claude worker running its own Workflow) | nested sub-fan-out inside one bounded workstream | Depth ≤ 2 from the conductor; give mid-tier leads explicit worker lists |
| **cmux** (view layer + event bus) | watching any of the above; non-agent notifications | Never load-bearing; see `references/cmux-integration.md` |

Rule of thumb: **phases the conductor must judge run provider-native (fast, in-context);
waves and standing teams run on CAO (durable, observable); cmux watches.**
The practical delegation ceiling is ~3 real levels — coordination quality runs out before
mechanism does.

## The research stage: delegate to a pipeline, don't inline it

When Research is more than a quick lookup, run it as a dedicated research pipeline
(e.g. a hyperresearch-style skill chain, or the bundle's `sdlc-researcher` workers)
via ONE orchestrating agent — never inline a multi-step research procedure into a single
worker prompt (long procedures get compacted away mid-run; routers/skill-chains exist to
load each step fresh). Research tiering: cheap tier for volume (fetch/sweep/per-topic
digestion), workhorse for judgment (synthesis, adversarial critique). Research rarely
needs the frontier tier — its quality is bounded by source coverage and synthesis
discipline; spend the frontier on the PLAN that consumes the report.

## Backflow: bounded re-entry into earlier phases

A verdict often reveals an EARLIER phase was insufficient (plan missed a workstream;
discovery skipped a subsystem; a claim is unsupported). **Backflow** = the verdict emits a
`reenter` directive naming the earlier phase + a SCOPED sub-task; the loop re-enters that
phase narrowly, then flows forward again. This is what makes the loop a loop.

Guardrails (so "keep going until done" stays bounded):

1. **Three independent stops:** a global pass ceiling (~6), a per-phase re-entry budget
   (Frame ≤1, Discover/Research/Plan ≤2, Act ≤3), and a resource floor. Any trip ends
   the loop.
2. **Only the Verdict emits backflow.** Workers report concerns; the verdict decides
   whether a concern earns a re-entry. One emitter keeps the loop analyzable.
3. **Re-entry is scoped, additive** — "re-dive ONLY subsystem X"; prior artifacts stay.
4. **Ceiling-hit without done = honest stop**: report state + resume hints. Never fake
   completion. ("Loop until done" means "until done OR a bound proves non-convergence.")

In CAO terms: the conductor holds the backflow cursor; re-entry = launching scoped
workers back into an earlier phase's profile (`assign`, async), folding their artifacts
into the accumulated state before re-running the forward phases as cheap re-validation.

## Iteration shape: chained runs vs one mega-run

- **Default: one run per loop ITERATION, conductor between iterations.** The
  between-iteration decision (re-scope? re-research? ship?) is a forward multiplier — it
  belongs to the conductor. Each completed iteration is a durable checkpoint + a steering
  point for the human.
- **One mega-run** (backflow controller inside): headless/cron missions, well-trodden
  shapes, explicit fire-and-forget. Delegate ship authority to the final verdict
  (commit-never-push) and keep the honest-exit contract.
- **Hybrid scout trick:** do cheap discovery inline FIRST (list files, find seams) so the
  run's prompts reference real names instead of spending their first phase rediscovering.

## Worker-lifecycle patterns at scale (10+ workers)

- **Write-as-you-go:** every worker prompt requires writing findings/output to its
  artifact file INCREMENTALLY, not accumulating in context and writing at the end —
  the #1 stall cause at scale is workers running out of budget before writing.
- **Escalating nudge → replace:** an idle worker with no artifact gets one nudge; still
  nothing → spawn a replacement scoped to the missing artifact; never block a wave on a
  zombie.
- **Salvage before relaunch:** a dead worker's worktree may hold real work — inspect,
  verify, keep what passes gates (see `references/worktree-integration.md`).
