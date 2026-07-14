# Tiered Orchestration (blast radius, backflow, and a native-first capability ladder)

Use this reference when composing a full mission run: assigning semantic model lanes to
stages, bounding backflow (later stages re-entering earlier phases), and choosing which
orchestration layer runs each piece. This file owns model-neutral mission structure. The
installable sibling skill `skills/model-tier-rightsizing/` owns routing doctrine, and its
`references/model-routing-calibration.md` is the canonical generation-specific authority.
This flagship reference does not duplicate a model, effort, quota, or roadmap matrix.

## Blast-radius routing

Agents are not interchangeable, and a selected lane is a request rather than proof of the
provider/model actually used. Route by what happens when an answer is wrong:

- **Scale-setting:** a frame, plan, authority ruling, cross-system invariant, or final
  stop/go decision can derail the run because later stages branch on it or consume it as
  settled truth. Keep it solo, require re-derivation, and use the strongest certified
  decision lane.
- **Silent degradation:** implementation, synthesis, or semantic review can be plausible
  while weakening an artifact beyond ordinary gate coverage. Use a certified judgment
  lane, explicit acceptance criteria, and independent review of an immutable candidate.
- **Visible retry:** a compiler, test, schema, deterministic comparison, or evidence check
  catches failure. Use a certified gated-volume lane and retry or escalate.
- **Mechanical redo:** fully checked inventories, extraction, and formatting can use the
  least expensive certified lane whose errors are visible and cheap to repeat.

The scale-setter litmus is structural: does the output define a later work list, loop bound,
branch condition, authority edge, or truth that consumers will not re-derive? If so, keep
that point singular. Collapse excess scale-setting candidates into one judge over bounded
panel artifacts rather than spawning a top-lane panel.

Every delegated call carries an exact model ID and requested effort/context supported by
the active transport. Record resolved provider/model/effort/context only after adapter
readback; otherwise record inherited, unknown, or unresolved. A route, verdict, or gate
never authorizes an outward effect.

Load the model-tier-rightsizing skill and its canonical calibration before dispatch. It
contains current exact IDs, transport hazards, effort evidence, context boundaries,
fallbacks, quota evidence, and per-roadmap lanes; do not infer those from generic lane
names here.

## Scale-setter survival rules

1. **Small in, small out.** Never interpolate huge upstream state into a decision-lane prompt —
   persist artifacts to disk, have the agent Read them; ask for a SMALL decision object
   (verdict + pointers), with big artifacts Written to disk incrementally.
2. **Fallback ladder, never a bare throw.** A scale-setter that stalls or errors must not
   kill a long run: retry once, then use a same-class certified fallback from the canonical
   calibration. Keep the STRUCTURE (solo scale-setter points) when transport changes. If no
   same-class route is certified, stop or reduce scope rather than silently weakening it.
3. **Interactive runs:** the conductor session may already occupy the certified decision
   lane — pull the highest-stakes verdicts into the main loop (read the disk artifacts,
   decide there) instead of spawning another scale-setter.

## The capability ladder (which mechanism runs which piece)

The baseline has two complete layers; optional adapters add visibility:

| Layer | Runs | Use for |
|---|---|---|
| **Conductor** (interactive host session) | frame, plan adoption, verdict recommendations, Seeds/merge ownership | All scale-setting decisions; no outward authority |
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
load each step fresh). Route research by the canonical calibration: use the gated-volume
lane for checked fetch/sweep/extraction and the judgment lane for synthesis or adversarial
critique. External research quality is often bounded by source coverage and evidence
discipline; spend the strongest decision lane on the PLAN that consumes the report.

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
