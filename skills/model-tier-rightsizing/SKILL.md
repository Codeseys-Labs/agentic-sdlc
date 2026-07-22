---
name: model-tier-rightsizing
description: |
  Pick the right Claude model tier (Fable 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5)
  for each agent in a workflow or subagent fan-out under real quota constraints.
  Use when: (1) choosing per-agent `model:` overrides, (2) a frontier-tier
  fan-out crawls or 429s (frontier TPM can be ~150x smaller than the workhorse
  lane), (3) deciding if "best model for everything" is viable, (4) picking the
  model for review/research/menial agents, (5) setting the workhorse-vs-volume
  boundary for a fleet.
  Encodes the FOUR-tier policy: frontier = scale-setters (solo),
  judgment-workhorse = un-gated judgment + widest-lane throughput reserve,
  capable-volume = the default for gated/cross-checked parallel work,
  mechanical = gate-checked menial floor. Includes a worked quota table from a
  real Bedrock account (re-derive per account) and quota-aware concurrency math.
author: Claude Code
version: 2.0.0
date: 2026-07-05
---

# Model-Tier Rightsizing for Dynamic Workflows

## Problem

"Use the most intelligent model for everything" fails at the quota layer, not
the capability layer. On Bedrock, frontier-tier models ship with token-per-
minute (TPM) ceilings orders of magnitude below the workhorse tiers — a
6-agent parallel fan-out on Fable 5 self-throttles into sequential-or-worse
wall-clock, while the same fan-out on Opus 4.8 or Sonnet 5 runs unconstrained.
The capability delta between tiers is real but much smaller than the quota
delta, so the marginal intelligence of each tier must be spent where it is
load-bearing, not sprayed across a fleet.

Since Sonnet 5 (Claude 5 family) became available on Bedrock, the old two-way
"Opus=workhorse, Sonnet=menial" split is obsolete: Sonnet 5 carries
near-workhorse judgment at Sonnet-class quota and lower cost, and Haiku 4.5
takes over the mechanical floor.

## Context / Trigger Conditions

- Writing a `Workflow` script and choosing `model:` per `agent()` call
- A multi-agent fan-out is slow, flapping with 429/ServiceUnavailable, or
  agents complete one-at-a-time despite `parallel()`
- User says "use the best model for the workflow" or "why not Fable for all?"
- Choosing the model for review panels, research sweeps, verification passes
- Deciding whether a fleet needs Opus 4.8 or whether Sonnet 5 suffices

## The measured quota reality (worked example: one real Bedrock account, us-east-1, 2026-07-05 — RE-DERIVE PER ACCOUNT)

Live query: `aws service-quotas list-service-quotas --service-code bedrock
--region us-east-1`. The binding rows for Claude Code traffic:

| Quota | Fable 5 | Opus 4.8 | Sonnet 5 | Haiku 4.5 |
|---|---|---|---|---|
| TPM (cross-region) | **200K** | **30M** | **6M** | 5M |
| TPM (global cross-region) | 500K | 30M | 6M | 5M |
| Tokens/day (global CRIS) | 720M | 43.2B | 8.64B | 7.2B |
| Tokens/day (model invocation, 2x for CRIS) | 144M | 21.6B | 4.32B | 3.6B |
| RPM | (TPM-bound) | (TPM-bound) | (TPM-bound) | 10K |

**Headlines:** Opus 4.8 has 150x Fable's per-minute budget; Sonnet 5 has 30x.
Fable's 200K TPM is roughly ONE busy agent (a file-heavy agent burns 50-150K
tokens/min on cache misses). Opus's 30M saturates only past ~100 concurrent
heavy agents; Sonnet 5's 6M handles ~20-60; Haiku's 5M similar but cheaper.

Also remember model-level guardrails: Fable 5 is a Covered Model (mandatory
provider_data_share retention — see `bedrock-fable5-data-retention-gate`) and
carries stricter refusal/safety behavior on dual-use content; day-one capacity
can flap independent of quota (see `bedrock-new-model-503-vs-config-bug`).

## The four-tier policy

| Tier | Model | Use for | Concurrency budget |
|---|---|---|---|
| **Frontier** | `fable` (1M ctx) | Scale-setters and depth-multipliers ONLY: the Frame/decompose, the Plan whose `workstreams[]` sizes the fleet, the final Verdict, feasibility derivations downstream treats as settled truth. The MAIN LOOP of an interactive session. | **1, maybe 2**. Never in a fan-out. |
| **Judgment workhorse** | `opus` (Opus 4.8) | Parallel work whose output is **un-gated or hard to gate**: final synthesis/drafting, surgical patchers, dense/unfamiliar-code comprehension where a misread poisons downstream, long-horizon implementation with many interacting constraints, the highest-stakes critic lenses. Also the **throughput reserve**: when a Sonnet-5 fleet would saturate 6M TPM, spill to Opus's 30M lane. | Dozens in parallel. |
| **Capable volume** | `sonnet` (Sonnet 5) | **The default for structured parallel work** that is gated, cross-checked, or evidence-disciplined: codebase cartography/mapping, review lenses that must cite file:line, adversarial verification votes, research fetch+digest, reconcile-to-green (compiler/test-gated), mid-complexity implementation with tests, triage. Claude-5-family reasoning at roughly half-to-two-thirds Opus cost. | ~20-60 heavy parallel agents (6M TPM). |
| **Mechanical** | `haiku` (Haiku 4.5) | Menial tasks where the schema/gate does the thinking: file inventories, format conversion, log scanning, dedup passes, structured extraction, golden regeneration. Anything whose wrong answer is a visible failure + retry. | ~20-50 parallel (5M TPM), cheapest lane. |

### The decision ladder (route on blast radius, not task prestige)

Per agent, ask: *"if this agent's output is wrong, what happens?"*

1. **The run derails** (wrong frame, wrong plan, wrong ship verdict, wrong
   "settled truth") → **Fable**, solo.
2. **The artifact degrades in ways no gate catches** (a synthesis nobody
   re-reads sources against, a patch nobody diffs semantically, a subtle
   misread of dense code every downstream agent inherits) → **Opus 4.8**.
3. **A gate/verifier/synthesis catches it** (findings get adversarially
   verified, code gets compiled+tested, maps get cross-checked by consumers,
   votes get majority-ruled) → **Sonnet 5**. This is most fan-out work.
4. **It's just a retry** (inventory, extraction, formatting) → **Haiku 4.5**.

The Opus-vs-Sonnet-5 boundary is the new judgment call, and the question is
not "how hard is the task" but **"is there a downstream check?"** A review
lens whose findings face 2-skeptic verification is Sonnet 5 work even when
the subject matter is hard — the verification IS the quality floor. The
verifiers themselves can also be Sonnet 5 when they vote in panels
(majority-rules is the check); a SOLO verifier with kill authority leans
Opus. When in doubt on a big fan-out: start Sonnet 5, escalate the
judgment-heavy subset to Opus.

Refinement (the multiplier principle, see [[deep-work-loop-tiered]]):
frontier-tier work sits at the points whose output sets the SCALE of
downstream stages — the beginning (forward multiplier: the frame everything
inherits), the end (backward multiplier: the verdict that gates a whole
re-round), and mid-loop gates whose output later stages `.map(...)` over or
branch on. Litmus test: if the agent's output becomes a work list, loop
bound, or stop/go condition downstream, it's a Fable candidate; if it's one
input among peers to a synthesis, it's Opus/Sonnet-5 per the ladder above.

Second refinement (depth multipliers): a stage whose conclusions downstream
consumes as **settled truth** — mathematical-feasibility derivations,
killshot analyses, novelty adjudications — is frontier work even though its
output is neither a work list nor a branch condition. Route the JUDGMENT
half to Fable via the split pattern: Opus/Sonnet-5 analysts draft the volume
in parallel → ONE solo Fable re-derives the load-bearing claims and signs.

## The alias plumbing (how one settings edit re-tiers everything)

In Bedrock mode, Claude Code's `model:` values are **tier aliases** resolved
through `~/.claude/settings.json` env vars:

```json
"ANTHROPIC_DEFAULT_FABLE_MODEL":  "global.anthropic.claude-fable-5[1m]",
"ANTHROPIC_DEFAULT_OPUS_MODEL":   "us.anthropic.claude-opus-4-8[1m]",
"ANTHROPIC_DEFAULT_SONNET_MODEL": "global.anthropic.claude-sonnet-5[1m]",
"ANTHROPIC_DEFAULT_HAIKU_MODEL":  "global.anthropic.claude-haiku-4-5-20251001-v1:0"
```

- Always write `model: 'sonnet'` / `'opus'` / `'haiku'` / `'fable'` in
  Workflow scripts and agent definitions — never concrete model IDs. When a
  new model generation lands, ONE settings edit retroactively upgrades every
  script, skill, and subagent definition that used the alias (proven
  2026-07-05: pointing the sonnet alias at Sonnet 5 upgraded the entire
  hyperresearch pipeline and all workflow templates for free).
- Omitting `model:` inherits the main-loop model — usually Fable in an
  interactive session. **Omitting `model:` on a fan-out therefore silently
  runs N Fable agents against a 200K TPM pool** — the most common way this
  failure ships. Always set the tier explicitly on parallel agents.
- `ANTHROPIC_SMALL_FAST_MODEL` (harness auxiliary calls — bash-output
  summarization etc.) stays Haiku: high-volume, low-stakes.
- Mid-flight re-tier of a running Workflow: `TaskStop` → edit the persisted
  script's `model:` values → relaunch with `{scriptPath, resumeFromRunId}`;
  completed agents replay from cache, the remainder runs on the new tier
  (proven live 2026-07-05 on a 61-agent review).

## Applying it in Workflow scripts

```js
// Main-loop session model is Fable (the orchestrator IS the frontier work).
// Gated/cross-checked fan-outs get Sonnet 5; un-gated judgment gets Opus;
// mechanical stages get Haiku.
const maps = await parallel(AREAS.map(a => () =>
  agent(a.prompt, { label: `map:${a.key}`, schema: MAP, model: 'sonnet' })))     // consumers cross-check
const reviews = await parallel(LENSES.map(l => () =>
  agent(l.prompt, { label: `rev:${l.key}`, schema: S, model: 'sonnet' })))       // verified downstream
const synthesis = await agent(synthPrompt, { model: 'opus', schema: DOC })       // un-gated, one-shot
const inventory = await agent(listPrompt, { model: 'haiku', schema: LIST })      // retry-safe
const verdict  = await agent(verdictPrompt, { model: 'fable', schema: VERDICT }) // scale-setter, SOLO
```

## Quota-aware concurrency math

```
safe_parallel_agents ≈ TPM / (per-agent tokens-per-minute)
per-agent t/min ≈ 30-150K for file-heavy agents (cache-miss reads dominate)

Fable 5:    200K / 100K ≈ 2   → solo work only
Opus 4.8:    30M / 100K ≈ 300 → fan out freely; spillover lane
Sonnet 5:     6M / 100K ≈ 60  → the default fleet lane
Haiku 4.5:    5M / 100K ≈ 50  → mechanical sweeps
```

Daily ceilings matter for long sessions: Fable's 144M tokens/day is reachable
by a single all-day ultracode session; Sonnet 5's 4.32B by a very heavy
multi-workflow day (a single 61-agent review burned 9M); Opus's 21.6B is not.

## Verification

- Re-pull current values before relying on the table (quotas are adjustable
  and change): `aws service-quotas list-service-quotas --service-code bedrock
  --region <region>` and grep QuotaName for the model.
- A correctly-tiered workflow shows parallel agents completing in overlapping
  wall-clock, no 429s, and `budget.spent()` growing linearly.
- Spot-check the resolved model in the subagent transcripts:
  `grep -ho '"model":"[^"]*"' <transcript-dir>/agent-*.jsonl | sort | uniq -c`.

## Examples

- **Sonnet-5 fleet, live-proven (2026-07-05, aws-autoresearch holistic
  architecture review, run wf_497ea95a-e7f):** 61 agents / 9.05M subagent
  tokens / 2h12m — 8 cartographers + 10 review lenses + 2-skeptic adversarial
  verification per critical/high finding + completeness critic, ALL on
  Sonnet 5, orchestrated by the Fable main loop. Zero throttling; 16/21
  critical-high findings survived verification with file:line evidence,
  including a genuine CRITICAL security find (an unsanitized write path
  bypassing a prompt-injection defense). The adversarial-verification layer
  is what made Sonnet 5 sufficient for the lens work — the check was
  structural, not per-agent brilliance. Mid-run the whole fleet was re-tiered
  from inherited-model to pinned `model: 'sonnet'` via stop→edit→resume with
  the completed prefix cached.
- **Opus fan-out precedent (2026-06-11, dcperf-automation bench-cli review):**
  6-dimension review + adversarial verification, all reviewers
  `model: 'opus'` while the Fable main loop orchestrated. Correct at the
  time (pre-Sonnet-5); today the same shape runs the lenses on Sonnet 5 and
  keeps Opus for the un-gated synthesis.

## Notes

- The policy is account-specific in its NUMBERS but general in its SHAPE:
  frontier tier is always the scarce lane; the capable-volume tier is always
  where fleet parallelism lives; the mechanical floor is always the cheapest
  gate-checked lane. Re-derive the table per account/region.
- TPM quotas are `Adjustable: true` — if Fable-tier fan-out is genuinely
  needed, file a quota increase rather than burning the default.
- Cost ordering (per token): Fable > Opus 4.8 > Sonnet 5 > Haiku 4.5. On big
  fan-outs the Sonnet-5-first + Opus-escalation pattern is both the cheaper
  AND the higher-throughput choice; verify relative prices per region before
  cost-justifying an exception.
- See also: [[deep-work-loop-tiered]] (the full loop-shaped application of
  this policy: per-stage tier table, solo-Fable rule, resume-with-retiering),
  [[agentic-batch-parallel-throttles-on-shared-model-quota]] (the general
  shared-quota trap), [[bedrock-fable5-data-retention-gate]] (Fable account
  gating), [[bedrock-new-model-503-vs-config-bug]] (day-one capacity vs
  config flapping).
- For a second scheduling axis — model context footprint — and the boundary
  between Dynamic Workflows, CLIProxyAPI, and process-wide Claude Code compaction,
  see the flagship skill's "Claude Code multi-model routing" reference.

## References

- AWS Service Quotas, service-code `bedrock` (live query beats this cache)
- https://platform.claude.com/docs/en/api/rate-limits (first-party tiers)
