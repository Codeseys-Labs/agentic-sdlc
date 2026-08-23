# Model-rightsizing benchmark and economics research

**Captured:** 2026-08-12
**Purpose:** support `/sdlc-rightsize` candidate nomination and local evaluation design
**Evidence class:** `mined` unless a row is explicitly labeled as local `observed` evidence

## Executive conclusion

No public leaderboard can directly choose a production route. The transferable unit is not a
model name but:

```text
taskset × harness × runtime × model settings × exact route
```

Public results are useful for deciding which live exact route deserves local evaluation and which
metrics a local task pack should collect. They are not useful as one universal weighted score.
DeepSWE and CursorBench are the strongest direct coding priors for the currently listed models.
Artificial Analysis is most valuable when its component evaluations are kept separate. Prime
Intellect contributes the cleanest evaluation architecture and task-validation discipline, not a
single universal model ranking. Official Anthropic sources are authoritative for upstream context,
API-equivalent pricing, and subscription semantics, but not for the exact gateway/client tuple.

The production rule is therefore:

```text
observed > declared > mined
```

Only target-representative local evidence may recommend moving an exact route to
`role-qualified`. Runtime receipt admission remains separate and no evidence grants outward
authority.

## Evaluation and economic dimensions worth retaining

A useful local record needs more than benchmark score and list price:

- accepted successes and attempts, task-normalized pass@1, and a confidence interval;
- transport versus identity versus task/verifier failure;
- non-cached input, cache-read, cache-write, reasoning, visible output, and total tokens;
- cost per attempt and observed cost per accepted result;
- tokens and wall time per attempt and per accepted result;
- first-output latency, active wall time, and agent/tool steps;
- context exhaustion and effective context/effort readback when independently exposed;
- quota pressure, possible usage-credit consumption, and billing basis;
- harness, task-pack, runtime, effort, context form, and exact route identity;
- semantic control: deterministic verifier, immutable criteria, independent review, or
  re-derivation.

Mean and median must remain distinct. Missing values are not zero. An actual subscription call may
have unknown marginal dollars while still consuming scarce rolling quota. API-equivalent cost is
useful for comparison but is not the subscriber's bill.

## DeepSWE v1.1

**Sources:** [leaderboard](https://deepswe.datacurve.ai/) ·
[paper](https://arxiv.org/html/2607.07946)

The August 7, 2026 v1.1 release contains 113 tasks from 91 repositories across five languages and
21 models. Models run through a common mini-swe-agent harness with approximately four rollouts per
task in the paper. The source publishes pass@1 with uncertainty, cost, output tokens, wall time,
and agent steps; timeout and context exhaustion are failures.

Representative rows captured for currently relevant candidates:

| Configuration | pass@1 | Cost/task | Output tokens | Steps |
|---|---:|---:|---:|---:|
| Claude Opus 5 max | 74% ±4 | $11.84 | 118K | 99 |
| GPT-5.6 Sol max | 73% ±3 | $8.39 | 60K | 61 |
| Claude Fable 5 max | 70% ±4 | $21.63 | 119K | 88 |
| GPT-5.6 Terra max | 70% ±3 | $3.96 | 72K | 76 |
| GPT-5.6 Luna max | 67% ±4 | $0.61 | 73K | 102 |
| GPT-5.5 xhigh | 67% ±6 | $7.23 | 46K | 82 |
| Claude Opus 4.8 max | 59% ±2 | $13.22 | 135K | 120 |
| Muse Spark 1.2 xhigh | 55% ±2 | $3.70 | 99K | 101 |
| Claude Sonnet 5 max | 54% ±4 | $26.40 | 214K | 268 |

**Applicable:** `deterministic_gated_change`, `semantic_implementation`, and parts of
`integration_reconcile` with a patch oracle.

**Not established:** planning quality, interactive clarification, independent semantic review,
authority boundaries, route liveness, subscription economics, or context behavior outside the
benchmark harness. Binary reward has no partial credit and close confidence intervals overlap.
Use rows to select pilot candidates, never to assign a production tier.

## Artificial Analysis Coding Agent Index v1.3

**Source:** [Coding Agent Index](https://artificialanalysis.ai/agents/coding-agents)

The index combines DeepSWE, Terminal-Bench v2, and SWE-Atlas-QnA with equal component weight. It
runs three attempts per task and reports task-normalized pass@1, input/cache/output tokens,
cache-hit rate, API cost per task, active-agent wall time, and harness comparisons. The site also
plots token, cost, and time Pareto fronts.

This is valuable because its three components correspond to different rightsizing roles:

- DeepSWE → autonomous repository implementation;
- Terminal-Bench → deterministic terminal/system work and reconciliation;
- SWE-Atlas-QnA → repository discovery and evidence extraction.

The aggregate can hide a model that is excellent for one role and weak for another, so the local
flow should consume component evidence rather than copy the composite. Harness identity is part of
the result. Its active-agent wall time includes harness work and is not interchangeable with the
general Intelligence Index's estimated decode time.

## Artificial Analysis Intelligence Index v4.1.1

**Source:** [model benchmark and methodology](https://artificialanalysis.ai/models)

The current index combines GDPval-AA v2, tau3-Banking, Terminal-Bench v2.1, SciCode, Humanity's
Last Exam, GPQA Diamond, CritPt, AA-Omniscience, and AA-LCR. Captured top illustrative rows were
Claude Opus 5 max/xhigh at 63, Claude Fable 5 **with fallback** at 62, and Claude Opus 5 high plus
GPT-5.6 Sol max at 61.

The fallback row is not an exact-model tuple and is inadmissible as route evidence. The composite
should not choose an SDLC route: its domains, verifiers, and failure consequences differ. Its
cost/task estimate is still methodologically useful because it includes non-cached input, cache
hits, cache writes, reasoning, and answer/output pricing.

The Intelligence Index time metric is a weighted decode-time estimate derived from output-token
counts and output speed. It excludes time to first token and other agent/harness overhead. Do not
merge it with Coding Agent Index active wall time.

### Applicability of the broader Artificial Analysis catalog

| Evaluation | Relevance | Rightsizing use | Important limitation |
|---|---|---|---|
| Coding Agent Index | direct | implementation, terminal, repository understanding | inspect components; aggregate hides role fit |
| DeepSWE | direct | repository patching | fixed harness and binary reward |
| Terminal-Bench v2.1 | direct | deterministic gated work, system tasks, reconcile | terminal workload, not semantic review |
| SWE-Atlas-QnA | direct | evidence extraction and repository discovery | question answering, not mutation |
| AA-LCR | direct | long-document extraction/discovery/review | 10K–100K inputs do not prove 1M behavior |
| IFBench | direct | mechanical and schema/instruction-constrained work | narrow instruction-following signal |
| ITBench-AA | direct | Kubernetes diagnosis, evidence, review, reconcile | infrastructure-specific |
| AA-Omniscience | direct-supporting | hallucination/knowledge reliability for review/frontier | not coding or route qualification |
| AA-Briefcase | direct-supporting | long-horizon document, spreadsheet, memo work | professional knowledge work, not repository patching |
| GDPval-AA v2 | workload-dependent | broad semantic judgment and agent work | 44 occupations/9 industries dilute repo specificity |
| tau3-Banking | workload-dependent | knowledge navigation, tool use, authority/guardrails | banking domain |
| AutomationBench-AA | workload-dependent | SaaS completion and guardrail behavior | simulated applications |
| EnterpriseOps-Gym-AA | workload-dependent | stateful enterprise workflows and final-state grading | enterprise state model |
| APEX-Agents-AA | workload-dependent | long-horizon cross-application planning/integration | not source-repository specific |
| AA-AnalystAgent | workload-dependent | spreadsheets/documents/quantitative extraction | analyst workload |
| SciCode | domain-specific | scientific repositories | poor general-SDLC transfer |
| Harvey LAB-AA | domain-specific | legal review/authority documents | legal workload only |
| MMMU-Pro | domain-specific | image/rich multimodal extraction | irrelevant for text-only work |
| HLE, GPQA, CritPt | narrow prior | frontier knowledge/reasoning nomination | no direct coding or route evidence |
| MMLU-Pro, Global-MMLU-Lite | narrow prior | general/multilingual knowledge when target matches | weak SDLC specificity |
| MATH-500, AIME 2025 | narrow prior | deterministic mathematical tasks | competition math only |
| LiveCodeBench | narrow prior | algorithmic coding | not multi-file repository agency |
| Terminal-Bench Hard | legacy | historical terminal comparison | prefer current Terminal-Bench |
| tau2-Bench Telecom | narrow prior | domain tool/guardrail behavior | telecom-specific and superseded for broad use |

The right policy is per-evaluation filtering by target task class, not averaging every available
Artificial Analysis score.

## CursorBench 3.2 and routing economics

**Sources:** [current results](https://cursor.com/evals) ·
[methodology](https://cursor.com/blog/cursorbench) ·
[agent swarm economics](https://cursor.com/blog/agent-swarm-model-economics)

CursorBench uses ambiguous multi-file tasks sourced from real Cursor sessions and publishes score,
average API-equivalent cost per task, tokens, steps, and model/effort configuration. Representative
current rows:

| Configuration | Score | Cost/task |
|---|---:|---:|
| Grok 4.6 Extra High | 70.8% | $2.81 |
| Fable 5 Max | 70.5% | $17.32 |
| Opus 5 Max | 70.0% | $8.23 |
| GPT-5.6 Sol Max | 67.2% | $5.69 |
| GPT-5.6 Terra Max | 64.9% | $2.31 |
| Opus 4.8 Max | 62.3% | $5.77 |
| Sonnet 5 Max | 61.5% | $4.30 |
| GPT-5.6 Luna Max | 61.1% | $0.39 |
| GPT-5.6 Luna High | 56.8% | $0.16 |
| GPT-5.6 Luna Low | 37.6% | $0.03 |

Cursor warns that small score differences may not be statistically meaningful. The rows are most
applicable to `repository_discovery`, `semantic_implementation`, `semantic_review`, and
`integration_reconcile`; they do not certify this operator's route.

Cursor's router research is more important than its exact private threshold. It first predicts
whether a price-efficient model is sufficient, then chooses a frontier model only when credible
uplift clears a one-sided threshold. Offline policies are validated on held-out data and then
online. User correction/continuation are production proxies. Model switches are charged for cache
misses.

The swarm-economics work adds a role-level lesson: workers consume most tokens, but a cheap planner
can cause expensive downstream execution. Planner and worker costs must therefore be attributed to
the role that caused them, not only to the model that emitted the tokens. Independent review
lenses can add value; duplicating one universal reviewer often adds correlated cost instead.

The local implementation adopts the principles—sufficiency first, uplift threshold, held-out
evidence, switching cost, role-level economics—but not Cursor's workload-specific threshold or
private outcome proxy.

## Prime Intellect / PrimeLabs research

**Sources:** [verifiers v1](https://www.primeintellect.ai/blog/verifiers-v1) ·
[hosted evaluations](https://www.primeintellect.ai/blog/hosted-evaluations) ·
[FrontierSWE](https://www.primeintellect.ai/blog/frontier-swe) ·
[scaling agentic RL](https://www.primeintellect.ai/blog/scaling-agentic-rl)

The strongest transferable result is architecture:

```text
evaluation = taskset × harness × runtime × model settings
```

`verifiers v1` separates the taskset, harness, runtime, API dialect, and typed trace. It supports
OpenAI Chat/Responses and Anthropic Messages, compaction and subagent branches, isolated runtimes,
and evaluation-time interception. The local evaluator adopts the decomposition while remaining
stdlib-only and using the existing reviewed launcher.

Prime's validation discipline is directly useful:

- gold-patch validation;
- no-op validation;
- repeated retries to identify flaky tasks;
- hiding grading material until scoring;
- retaining exclusions for audit.

FrontierSWE is an ultra-long-horizon specialist benchmark: the published work describes roughly 11
hours per task on average and a very low solve rate. It can inform an opt-in frontier pack but is
too expensive and sparse for ordinary qualification. Prime's terminal, SWE, and search/deep-
research task inventory can inspire future role-specific packs; no dependency or hosted task is
adopted by default.

No authoritative Prime source found in this research supplied one broadly comparable current
leaderboard covering every ccodex-listed model. Treating the framework as methodology is more
honest than inventing a Prime universal model ranking.

## Claude subscription, pricing, and context

**Sources:** [Claude Code models](https://code.claude.com/docs/en/model-config) ·
[Claude Code costs](https://code.claude.com/docs/en/costs) ·
[model overview](https://platform.claude.com/docs/en/about-claude/models/overview) ·
[API pricing](https://platform.claude.com/docs/en/about-claude/pricing) ·
[plans](https://claude.com/pricing)

Fable 5, Opus 5, and Sonnet 5 have 1M upstream context and 128K synchronous output maxima in the
captured official model documentation. This does not certify an exact gateway/client request form.
A gateway session may budget a base form conservatively, and client auto-compaction or explicit
one-million-token selection changes behavior. A requested suffix or upstream product page is not
served-context readback.

Subscription usage draws from rolling limits shared across Claude surfaces. Depending on plan,
Fable or extended-context use may consume usage credits. Claude Code's API-equivalent dollars are
not necessarily the subscriber's actual bill. Consequently the map records:

```json
{
  "billing_basis": "claude-subscription",
  "marginal_cost_usd": null,
  "api_equivalent_cost_usd": 8.23,
  "quota_consumption": "unavailable",
  "usage_credits_possible": true
}
```

Model switching can cause cache misses; Pareto economics should therefore use locally observed
cache-read/write tokens and should charge switching effects rather than comparing list prices
alone.

## Context selection

Context is first a constraint:

```text
required = expected peak input + output reserve + safety margin
```

Choose the smallest exact certified request form that fits. A model that natively exposes one
million tokens may use its base ID; Muse's 1,048,576-token shared pool also has no `[1m]` suffix.
`[1m]` is a request/client-accounting form and remains separate from model ID in JSON. It is never
a quality reward and must not be selected unless needed and certified on the exact route tuple.
AA-LCR's 10K–100K documents support long-context candidate nomination but cannot certify 1M use.

## Pareto policy

The local evaluator constructs a separate front per task class after filtering route identity,
semantic control, context fit, qualification, and runtime admission. It maximizes local success
lower bound and minimizes route/identity failure plus one selected efficiency dimension. It also
retains all other available metrics for inspection.

Observed cost per accepted result is:

```text
sum(actual compatible observed attempt cost) / accepted successes
```

The same arithmetic applies to tokens and wall time. Zero successes means unavailable, not
infinity or zero. A modeled `mean cost / pass rate` may be shown only as explicitly modeled when
independent retry assumptions are stated; the current local evaluator prefers actual repeated
attempts and does not manufacture retry independence.

A route missing a cost metric cannot dominate a fully measured route on cost, nor be declared free.
It can remain non-dominated as incomparable, with the missing dimension named.

## Sources not suitable for direct route selection

- marketing rank or vendor family labels without exact task/harness evidence;
- benchmark composites with automatic model fallback;
- stale or legacy benchmark versions when a current component is available;
- registry presence or product announcement without live route evidence;
- API pricing used as subscription marginal billing;
- model-level context maximum used as exact input/output or client accounting proof;
- algorithmic or science scores applied to repository work without a matching workload;
- any benchmark score used to fill `authority_or_frontier` without local critical cases and
  independent re-derivation.

## Implementation implications

1. Keep the static consequence tiers as incumbent production policy, not the candidate universe.
2. Discover candidates from the live configured environment and Claude subscription state.
3. Ask the operator which sources, models, task classes, objective, context demand, and budgets to
   include; normalize every answer into a replayable spec.
4. Show an exact no-call plan and obtain operation-specific approval before provider traffic.
5. Use deterministic or independently controlled local task packs for promotion.
6. Preserve raw benchmark data as versioned `mined` evidence and refresh it separately from local
   map rendering.
7. Never let a benchmark, local evaluation, generated map, or passing repository gate authorize
   production spawn or outward action.
