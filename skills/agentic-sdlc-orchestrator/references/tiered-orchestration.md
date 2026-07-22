# Tiered Orchestration (model tiers, backflow, and a native-first capability ladder)

Use this reference when composing a full mission run — assigning MODEL TIERS to stages,
bounding BACKFLOW (later stages re-entering earlier phases), and choosing WHICH
orchestration layer runs each piece. Distilled from a proven tiered deep-work-loop
practice (multi-million-token runs); adapted here for a provider-native baseline with
optional durability and view adapters.

For concrete Claude Code Dynamic Workflow routing across providers, context windows,
compaction policies, and fast modes, read
[`claude-code-multi-model-routing.md`](claude-code-multi-model-routing.md).

## The multiplier principle (where the frontier model goes)

Agents are not interchangeable, and model tier is a requested semantic, not proof of the
provider/model actually used. Reserve the scarcest/strongest tier for **scale-setters** —
decisions that multiply. Record resolved provider/model only after adapter readback; otherwise
record inherited or unresolved. A tier choice, verdict, or gate result never authorizes an
outward effect.

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

In the bundle, tier assignment starts with native host configuration: Claude Workflow
stages carry `model:` per agent() call, and Codex roles carry
`model`/`model_reasoning_effort` in TOML.
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

## The capability ladder (which mechanism runs which piece)

The baseline has two complete layers; optional adapters add durability or visibility:

| Layer | Runs | Use for |
|---|---|---|
| **Conductor** (interactive host session) | frame, plan adoption, verdict recommendations, Seeds/merge ownership | All scale-setter decisions; no outward authority |
| **Provider-native fan-out** (roles, subagents, workflows, teams, background tasks) | discovery, research, implementation waves, review panels, critique | All delegated work within the host's supported lifetime |
| **Optional cmux adapter** | view/event layer for already-active sessions | Never load-bearing; no installation or enablement step |

Rule of thumb: **keep phases and waves provider-native. Use cmux only for visibility when it
is already active.** The practical delegation ceiling is about three real levels; coordination quality
runs out before mechanism does.

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

The conductor holds the backflow cursor. Re-entry launches a scoped provider-native worker,
folds its artifact into accumulated state, then re-runs forward phases as cheap
re-validation. A verdict or backflow directive is advisory and does not grant
permission for an outward operation.

## Iteration shape: chained runs vs one mega-run

- **Default: one run per loop ITERATION, conductor between iterations.** The
  between-iteration decision (re-scope? re-research? ship?) is a forward multiplier — it
  belongs to the conductor. Each completed iteration is a durable checkpoint + a steering
  point for the human.
- **One mega-run** (backflow controller inside): headless/cron missions, well-trodden
  shapes, explicit fire-and-forget. Treat the final verdict as a recommendation only;
  ship, commit, push, and every other outward effect still require operation-specific
  authorization. Keep the honest-exit contract.
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
