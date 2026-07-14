# Six-model routing calibration

**Calibration ID:** `six-tier-2026-07-14`

**Record date:** 2026-07-14

**Scope:** current Workflow/ccodex transport and the approved Agentic SDLC roadmap

**Claim boundary:** transport and three-lens smoke evidence; not a total ranking and not production proof

This is the sole authored generation-specific routing matrix. The sibling `SKILL.md`
owns stable blast-radius doctrine. Other skills link here rather than copying model, effort,
quota, or roadmap tables.

Keep four facts separate:

1. **Requested dispatch:** exact model ID, effort, and context form sent by the client.
2. **Resolved readback:** model, effort, provider, and context behavior independently
   exposed by the active adapter or upstream telemetry.
3. **Task-local smoke result:** whether one bounded lens contract received a correct
   answer, received a wrong answer, or never received an answer because the harness failed.
4. **Production recommendation:** a provisional policy based on blast radius, gates,
   authority, inherited operational evidence, and the approved roadmap.

## Exact dispatch and requested effort

Every dispatching Workflow consumer must receive an exact bare ID certified by the active
transport. It must stop before dispatch when that certification or adapter readback is
unresolved; a provider-neutral static role definition does not select a model. Bare Claude
tier aliases are unsafe in the current path because settings expand them to
provider-qualified IDs that ccodex rejects. This calibration does not change settings,
trust, or configuration.

| Consequence lane | Exact model ID | Requested effort | Complement | Required gate or control |
|---|---|---|---|---|
| Derail / settled truth | `gpt-5.6-sol` | `high`, `xhigh` | `claude-fable-5` at `max` searches a bounded assumptions packet | Re-derivation; conductor adjudicates the advisory recommendation |
| Contained silent-degrade | `gpt-5.6-terra` | `xhigh`, `max` | `claude-opus-4-8` at `high`, `xhigh` reviews an immutable semantic delta | Explicit acceptance criteria and independent review |
| Deterministic-gated volume | `gpt-5.6-luna` | `high`, `xhigh` | `claude-sonnet-5` at `high`, `xhigh` checks stable evidence | Compiler, tests, schema, diff, or deterministic verifier |
| Bounded adversarial specialist | `claude-fable-5` | `max` | `gpt-5.6-sol` at `xhigh` receives the counterexample artifact | Bounded packet; advisory analysis only; conductor adjudicates |
| Semantic-review specialist | `claude-opus-4-8` | `high`, `xhigh` | `gpt-5.6-terra` at `xhigh`, `max` reproduces the candidate | Immutable candidate and named acceptance criteria |
| Gated-verification specialist | `claude-sonnet-5` | `high`, `xhigh` | `gpt-5.6-luna` at `high`, `xhigh` produces deterministic receipts | Same deterministic gate remains required |

The complete requested effort vocabulary accepted by the smoke transport was:

- `low`
- `medium`
- `high`
- `xhigh`
- `max`

All production effort bands above are recommendations and inherited roadmap policy. They
are explicitly **provisional and requested-only** until representative evaluation and
upstream telemetry expose the effective effort. Smoke acceptance at all five values does
not establish an effort-quality curve.

### Current unsafe alias behavior

The original run requested aliases. Settings expanded each alias before ccodex validation,
and all 15 cells per model (five efforts times three lenses) failed transport:

| Alias requested | Settings-expanded request | Observed result | Required exact replacement |
|---|---|---|---|
| `fable` | `global.anthropic.claude-fable-5` | HTTP 400 unknown model | `claude-fable-5` |
| `opus` | `us.anthropic.claude-opus-4-8` | HTTP 400 unknown model | `claude-opus-4-8` |
| `sonnet` | `global.anthropic.claude-sonnet-5` | HTTP 400 unknown model | `claude-sonnet-5` |

This is configuration/transport evidence, not evidence that the Claude models are
unavailable or incapable. Exact bare Claude IDs later completed. An alias becomes safe
only after its outbound request and transcript readback match the intended exact model in
the active session.

### Requested versus resolved effort

The harness accepted `low`, `medium`, `high`, `xhigh`, and `max`, but resolved effort is
not exposed in the available transcript readback. A success token that repeats prompt text
proves neither upstream receipt nor effective reasoning effort. Receipt fields must remain:

```yaml
requested_effort: low|medium|high|xhigh|max
resolved_effort: unknown
resolved_effort_evidence: unavailable_in_transcript
```

Never copy requested effort into resolved effort. Reclassify it only when proxy/upstream
request or response telemetry independently exposes the resolved value.

### `[1m]` boundaries

Observed `[1m]` requests read back the base GPT model ID. The suffix is a client-side
context/compaction control in this path; it does not name a different upstream model, does
not prove an upstream 1M context window, and does not increase intelligence.

- `gpt-5.6-sol[1m]` read back as `gpt-5.6-sol`.
- `gpt-5.6-terra[1m]` read back as `gpt-5.6-terra`.
- `gpt-5.6-luna[1m]` read back as `gpt-5.6-luna`.

Base-model readback also does not prove compaction or context handling occurred. Verify
that behavior through client telemetry and a representative task that actually reaches the
compaction boundary. Use `[1m]` only for transcript-, corpus-, or repository-heavy GPT
assignments; otherwise prefer bounded disk-backed artifacts. Exact Claude `[1m]` forms
were not separately certified, so keep Claude work to compact packets and immutable deltas
until those request forms pass.

## Deterministic smoke evidence: 80 / 10 / 0

Receipt `agentic-sdlc-six-tier-smoke/v1` preserves 90 cells: six models, five requested
efforts, and three independent lenses (mechanical selection, contained path review, and
queue-authority reasoning). Its adjudication is:

- **80 task-local passes**: the received answer passed only its own deterministic lens.
- **10 harness-inconclusive cells**: prompt/context failure occurred before a task answer;
  this is not a model-quality failure.
- **0 observed task-local model failures**: no received answer missed its own contract.

The 10 inconclusive cells are Fable (6) and Sonnet (4). They must not be relabeled null
model answers or used to infer a monotonic effort curve. Three recovered Terra authority
cells used `[1m]` request forms and establish task-local availability for those recovered
shapes only; they do not supersede missing base-form transport cells.

These are easy, synthetic smoke lenses. The evidence makes no comparative intelligence,
latency, cost, reliability, quota, provider placement, total-ranking, or production-proof
claim. Numeric judge scores were discarded because judges mixed scales and sometimes
penalized a response for not answering other independent lenses.

## Blast-radius production routing

| Wrong-output consequence | Exact model ID | Requested effort | Complement | Required control |
|---|---|---|---|---|
| Cheap deterministic retry | `gpt-5.6-luna` | `high` | `claude-sonnet-5` at `high` checks evidence rather than repeating the task | Exact comparison, schema, or bounded retry |
| Visible compiler/test/gate failure | `gpt-5.6-luna` | `high`, `xhigh` | `claude-sonnet-5` at `high`, `xhigh` checks the stable result | Compiler, tests, diff, or deterministic verifier |
| Silent candidate degradation | `gpt-5.6-terra` | `xhigh`, `max` | `claude-opus-4-8` at `high`, `xhigh` reviews the semantic delta | Immutable candidate and independent acceptance review |
| Run derailment or settled truth | `gpt-5.6-sol` | `high`, `xhigh` | `claude-fable-5` at `max` attacks a bounded assumptions packet | Re-derivation; conductor records the stop/go disposition |
| Trust, credentials, authority, or data-loss boundary | `gpt-5.6-sol` | `xhigh` | `claude-fable-5` searches a bounded packet; `claude-opus-4-8` reviews implementation semantics | Conductor adjudicates; fail closed and demand concrete evidence |
| Outward or irreversible operation | Human authorization | Not a model dispatch | Models may recommend only | Separate operation-specific human approval |

No model grants queue, fan-in, publication, or user authority. The conductor alone
adjudicates and mutates Seeds; only an authorized integrator performs an already-authorized
fan-in; humans authorize outward actions.

## Agentic SDLC phase routing

| Phase | Exact model ID | Requested effort and context | Complement | Gate or control |
|---|---|---|---|---|
| Frame | `gpt-5.6-sol` | `high`; `xhigh` at trust or authority boundaries; `[1m]` only for transcript or repository-heavy frames | `claude-fable-5` at `max` analyzes load-bearing assumptions | Re-derive; conductor adjudicates the recommendation |
| Discover | `gpt-5.6-terra` | `xhigh`; `[1m]` for repository-wide readers | `claude-sonnet-5` at `high` checks citations and omissions | Partitioned scope and evidence inventory |
| Research | `gpt-5.6-terra` | `xhigh`, `max`; `[1m]` only for long corpora | `claude-sonnet-5` extracts; `gpt-5.6-sol` analyzes load-bearing unknowns | Conductor adjudicates unknown disposition |
| Plan | `gpt-5.6-sol` | `xhigh`; `[1m]` when repository-wide evidence is consumed | `claude-fable-5` at `max` attacks multiplier assumptions | Advisory plan; conductor alone mutates Seeds |
| Act, contained | `gpt-5.6-terra` | `xhigh`; `max` for interacting constraints | `claude-opus-4-8` reviews immutable candidate decisions | Unsuffixed unless artifact-heavy |
| Act, deterministic-gated | `gpt-5.6-luna` | `high`, `xhigh` | `claude-sonnet-5` checks stable evidence | Unsuffixed by default; same deterministic gate |
| Review, semantic | `claude-opus-4-8` | `high`, `xhigh`; Claude `[1m]` only after exact route certification | `gpt-5.6-terra` reproduces and classifies findings | Immutable candidate and acceptance criteria |
| Review, trust or authority | `gpt-5.6-sol` | `xhigh` | `claude-fable-5` searches a bounded packet for counterexamples | Advisory analysis; conductor adjudicates |
| Reconcile | `gpt-5.6-terra` | `xhigh` | `claude-sonnet-5` validates evidence links | Conductor alone records Seeds mutations |
| Integrate | `gpt-5.6-terra` | `max` | `gpt-5.6-luna` re-runs gates; `claude-opus-4-8` reviews fan-in semantics | Authorized integrator only; re-gate on integration head |
| Ship recommendation | `gpt-5.6-sol` | `xhigh` | `gpt-5.6-luna`, `claude-sonnet-5` validate receipts | Human separately authorizes outward action |

## Approved roadmap family lanes

Each complement produces an orthogonal artifact rather than duplicating the whole task.
Every route below remains provisional/requested-only under the effort-readback boundary.

| Roadmap lane | Primary exact model ID | Requested effort and context | Complementary assignment | Gate or escalation |
|---|---|---|---|---|
| S1 Seeds toolchain retention | `gpt-5.6-luna` | `high` | `claude-sonnet-5` at `high` checks evidence-to-claim coverage | `gpt-5.6-terra` at `xhigh` analyzes semantic drift and recommends disposition |
| S2 Seeds execution contract | `gpt-5.6-terra` | `xhigh` | `gpt-5.6-sol` at `xhigh` analyzes queue evidence; `claude-opus-4-8` at `xhigh` reviews stable diff | Null or mismatch fails closed; conductor adjudicates Seeds action |
| Seeds fan-in | `gpt-5.6-terra` | `max` | `gpt-5.6-luna` at `high` re-gates exact ranges | Authorized integrator only; `gpt-5.6-sol` at `xhigh` analyzes stop/go ambiguity for conductor adjudication |
| Wave 1 CAO deletion | `gpt-5.6-terra` | `xhigh` | `gpt-5.6-luna` at `high` inventories residues; `claude-opus-4-8` at `high` reviews removed surface | Any shipped or runtime residue blocks |
| Wave 2 state-v3 identity cutover | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes migration invariants; `gpt-5.6-luna` at `xhigh` runs crash matrix; `claude-opus-4-8` at `xhigh` reviews recovery | Fail closed on foreign ownership; conductor adjudicates |
| Claude marketplace/plugin plane | `gpt-5.6-terra` | `xhigh` | `claude-opus-4-8` at `xhigh` checks supported-operation boundary | Never edit opaque state |
| Local checkout rename gate | `gpt-5.6-sol` | `xhigh` | `gpt-5.6-luna` at `high` verifies pre/post receipts | Human approval before mutation |
| GitHub repository rename gate | `gpt-5.6-sol` | `xhigh` | `claude-sonnet-5` at `high` inventories post-authorization evidence | Human approval; model never authorizes |
| A1 change-writing | `gpt-5.6-terra` | `xhigh` | `claude-opus-4-8` at `high` reviews evidence and attribution; `gpt-5.6-luna` at `high` builds fixtures | Output-only contract |
| A2 Git-default sdlc-init | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes defaults and refusals; `claude-opus-4-8` at `xhigh` reviews safety; `gpt-5.6-luna` at `high` builds fixtures | Dry-run and no-write cancellation |
| A3 hierarchical instructions | `gpt-5.6-terra` | `xhigh` | `claude-sonnet-5` at `high` checks conformance; `claude-opus-4-8` at `high` reviews markers and ownership | Preserve foreign prose |
| R1 shared role contracts | `gpt-5.6-terra` | `xhigh` | `gpt-5.6-sol` at `xhigh` analyzes separation of powers; `claude-fable-5` at `max` attacks authority packet; `gpt-5.6-luna` at `high` projects fixtures | All analysis advisory; conductor adjudicates |
| R2 bounded Deep Work Loop | `gpt-5.6-terra` | `xhigh` | `gpt-5.6-sol` at `xhigh` analyzes bounds and backflow; `claude-opus-4-8` at `xhigh` reviews recursion; `gpt-5.6-luna` at `high` tests | No second queue or unbounded recursion |
| R3 HyperResearch/Research OS | `gpt-5.6-terra` | `max` | `claude-sonnet-5` extracts evidence; `claude-opus-4-8` reviews crash recovery; `gpt-5.6-sol` analyzes load-bearing unknowns | Typed `SeedProposal`; conductor alone mutates Seeds |
| G1 Git change-flow family | `gpt-5.6-terra` | `xhigh` | `claude-opus-4-8` at `xhigh` reviews rebase, squash, and stack; `gpt-5.6-luna` at `high` builds fixtures | Stable commit and merge-base evidence |
| G2 toolchain/security | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes trust evidence; `claude-opus-4-8` reviews semantic security; `gpt-5.6-luna` tests falsifiability | Exact gate argv, status, and log digest |
| J1 jj certification | `gpt-5.6-terra` | `[1m]` at `xhigh` | `gpt-5.6-sol` at `[1m]`, `xhigh` analyzes framing; `gpt-5.6-luna` at `high` builds fixture matrix; `claude-fable-5` at `max` attacks data-loss assumptions | Official docs and immutable Git handoff; conductor adjudicates |
| J2 jj implementation | `gpt-5.6-terra` | `max` | `claude-opus-4-8` at `xhigh` reviews handoff and recovery; `gpt-5.6-luna` at `xhigh` builds fixtures | Conflict-free exact Git OID |
| A2j jj init amendment | `gpt-5.6-terra` | `xhigh` | `claude-sonnet-5` at `high` checks explicit selection and receipt | Only after J1/J2 certification |
| M0a Mermaid browser ADR/spike | `gpt-5.6-terra` | `[1m]` at `xhigh` | `gpt-5.6-sol` at `xhigh` analyzes dependency evidence; `claude-opus-4-8` reviews browser dependency; `gpt-5.6-luna` builds host/offline matrix | Stop before M1 without portable provider; conductor adjudicates |
| M0b Mermaid security foundation | `gpt-5.6-terra` | `max` | `claude-opus-4-8` at `xhigh` reviews malicious SVG; `gpt-5.6-luna` builds parser/render matrix | Strict allowlist and bounded resources |
| M1 structural Mermaid skills | `gpt-5.6-luna` | `xhigh` | `claude-sonnet-5` at `high` checks docs, citations, and fixtures | One writer and pipeline reviewer |
| M2 planning Mermaid skills | `gpt-5.6-luna` | `xhigh` | `claude-sonnet-5` at `high` checks docs, citations, and fixtures | One writer and pipeline reviewer |
| M3 quantitative Mermaid skills | `gpt-5.6-luna` | `xhigh` | `claude-sonnet-5` at `high` checks docs, citations, and fixtures | One writer and pipeline reviewer |
| M4 technical Mermaid skills | `gpt-5.6-luna` | `xhigh` | `claude-sonnet-5` at `high` checks docs, citations, and fixtures | One writer and pipeline reviewer |
| M5 conceptual Mermaid skills | `gpt-5.6-luna` | `xhigh` | `claude-sonnet-5` at `high` checks docs, citations, and fixtures | One writer and pipeline reviewer |
| M6 Mermaid router | `gpt-5.6-terra` | `xhigh` | `claude-sonnet-5` at `high` inventories exact-one routing | Reject unsupported or ambiguous requests |
| M7 Mermaid conformance | `gpt-5.6-luna` | `xhigh` | `claude-opus-4-8` reviews malicious output semantics; `gpt-5.6-sol` at `high` analyzes final evidence | Exactly one router plus 30 skills; conductor adjudicates |
| Release hardening | `gpt-5.6-terra` | `max` | `gpt-5.6-luna` builds cross-platform fixtures; `claude-opus-4-8` reviews semantics; `gpt-5.6-sol` recommends promotion | Publication separately authorized by humans |
| Evolutionary Core M2 | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes kernel contracts; `gpt-5.6-luna` runs crash suite; `claude-opus-4-8` reviews immutable candidate | Deterministic receipt and idempotent reconcile |
| Claude Golden Wave M3 | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes adapter and authority contract; `claude-opus-4-8` reviews semantics; `claude-sonnet-5` checks conformance; `claude-fable-5` attacks bounded assumptions | Exact Claude ID, effort, and context readback |
| Portability M4 | `gpt-5.6-terra` | `max` | `gpt-5.6-sol` at `xhigh` analyzes portability evidence; `gpt-5.6-luna` runs common fault suite; `claude-opus-4-8` reviews assumptions; `claude-sonnet-5` checks conformance | No public ABI before three adapters |
| CCP/ccodex certification | `gpt-5.6-terra` | `[1m]` at `max` | `gpt-5.6-sol` at `xhigh` analyzes package evidence; `gpt-5.6-luna` checks lifecycle; `claude-fable-5` attacks credential assumptions; `claude-opus-4-8` reviews implementation | Exact version, checksum, and readback |
| Final family wiring | `gpt-5.6-terra` | `xhigh` | `claude-sonnet-5` at `high` verifies cross-links and inventory | No unrelated family co-mingling |

## Complementary vendor roles

Use cross-vendor calls for different artifacts, not duplicated votes:

1. **`gpt-5.6-sol` analyzes; `claude-fable-5` attacks.** The former receives the full
   evidence and returns an advisory frame or stop/go recommendation. The latter receives
   only assumptions, authority edges, or trust boundaries and returns counterexamples; it
   does not write a second plan or hold authority.
2. **`gpt-5.6-terra` implements or synthesizes; `claude-opus-4-8` reviews the delta.**
   The reviewer receives an immutable candidate, merge-base footprint, and named
   micro-decisions; it does not reimplement the feature.
3. **`gpt-5.6-luna` builds deterministic evidence; `claude-sonnet-5` checks coverage.**
   The checker tests whether stable evidence supports each claim and citations are complete;
   it does not regenerate the matrix.
4. **The conductor adjudicates.** Maps, ResearchBriefs, SeedProposals, Candidates,
   ReviewFindings, and IntegrationReports remain submissions, never authority grants. The
   conductor alone mutates Seeds; an authorized integrator alone performs fan-in; humans
   authorize every outward action.

## Fallback and escalation

1. Treat null, malformed, truncated, missing, or transport-rejected output as failure.
2. Inspect the transcript; distinguish transport/harness failure from an answered task;
   apply bounded provider backoff and retry the same certified exact model/effort once.
3. On 429 or overload, reduce concurrency. Do not lower effort, gate strength, or
   blast-radius class merely to make pressure disappear.
4. Never fall back from an exact Claude ID to the unsafe aliases in this session.
5. A deterministic-gated lane may cross `gpt-5.6-luna` and `claude-sonnet-5` only while
   the same deterministic gate remains.
6. A contained semantic lane may cross `gpt-5.6-terra` and `claude-opus-4-8` only against
   an immutable candidate and explicit acceptance criteria.
7. There is no automatic authority fallback to `claude-fable-5`. It is a bounded advisory
   attacker. If `gpt-5.6-sol` is unavailable for a derail or authority analysis, stop or
   reduce scope.
8. Escalate the deterministic-gated lanes to the contained semantic lanes when gates pass
   but semantic uncertainty remains.
9. Escalate the contained semantic lanes to `gpt-5.6-sol` when the unknown affects
   authority, credentials, data loss, cross-system invariants, workstream sizing, or stop/go.
10. If the advisory analysis and attacker disagree, re-enter scoped discovery, research, or
    plan; never majority-vote an authority decision.
11. If no certified route exists, fail closed and decompose into smaller checked artifacts.

## Quota and concurrency evidence

No quotas were freshly measured for this calibration. The table is **inherited evidence**
from one Bedrock account in `us-east-1`, dated 2026-07-05. It is account-, region-,
provider-, and date-specific and may not describe ccodex traffic. Re-query before using it
for fan-out sizing.

| Historical Claude lane | Cross-region TPM | Global cross-region TPM | Global CRIS tokens/day | Invocation tokens/day |
|---|---:|---:|---:|---:|
| Fable 5 | 200K | 500K | 720M | 144M |
| Opus 4.8 | 30M | 30M | 43.2B | 21.6B |
| Sonnet 5 | 6M | 6M | 8.64B | 4.32B |

There is no Sol, Terra, or Luna quota evidence available: no GPT RPM, TPM, daily,
concurrency, or cost limit was measured. Successful parallel completion is not a quota
benchmark. Start with bounded width and record overlap, 429s, latency, and token use.

Semantic caps apply regardless of capacity: one canonical scale-setter at a time, one
bounded adversarial attacker, one writer per worktree, one conductor, integrator WIP 1,
and bounded passes/review-fix rounds.

## Rerun triggers

Run immediate decisive probes before broadening current policy:

- Repeat exact Fable `max` against a typed authority rubric at least three times; any
  malformed/missing result keeps it advisory-only.
- Probe exact Claude `[1m]` request forms before repository- or transcript-heavy Claude work.
- Capture upstream resolved-effort telemetry for the exact requested bands in the dispatch
  table, both base form and `[1m]` where applicable.
- Re-evaluate production bands on a repository-wide map, RED→GREEN contained change,
  migration/crash task, authority boundary, real compaction event, and bounded parallel
  wave with latency/token/429 telemetry.

Rerun affected cells whenever the proxy/ccodex allowlist or version, Workflow transport,
alias settings, provider/account/region, model generation, effort encoding, `[1m]`
implementation, prompt/rubric/schema, tool permissions, or authority contract changes.
Also rerun on any production-lane malformed/missing output, repeated overload, material
quota change, or repeated representative lane miss.

A production-band change requires repeatability, independent verification, no authority
regression, and a no-worse failure mode. A toy pass never promotes a model or effort.

## Auditable evidence receipts

The canonical deterministic receipt used for the 80/10/0 classification:

| Identifier | SHA-256 / object ID | What it establishes |
|---|---|---|
| `agentic-sdlc-six-tier-smoke/v1`, record 2026-07-14 | `1f413019d765b220284bbedfd5fb580eb0d50a7670b2d55444cf964177c08213` | 90-cell adjudication, 80 pass / 10 harness-inconclusive / 0 observed task-local model failures, limitations |
| `wf_a120305a-ab6` | `988c8c394ba5347e40685364a0a3a7c00ff77d440f37b76894c8ab820a8c9b83` | Original six-model matrix, provider-qualified alias rejection, GPT smoke cells |
| `wf_4baaadfe-431` | `2052144f4e690e2b3ee42cc9775540eaca317db0ade4115c506c6d566577bd1a` | Exact Claude quality cells, recovered Terra cells, preserved judgments and critique |
| `wf_c7260fad-96e` | `929f1c113bd1e351573fcd8d71e912a5d59a66b6381daec9cc7b3014ca3625dd` | Exact Claude transport and resolved base-model identity across five requested efforts |

Approved-roadmap provenance:

- roadmap archive commit `dbb2e2f5a98bcf4e6eeb62312e8b45db88788119`;
- approved-plan Git blob `d6bb02b79a5d3362e4a28e3ae5c43c0f105f8eed`;
- routing-certification Git blob `409f8858bffaec87cfc12b668bb1d11ba6acd1cb`.

Future receipts should include record timestamp, session/run ID, transport/proxy version,
provider/account/region when known, requested model/effort/context, outbound alias
expansion, transcript model, resolved effort or `unknown`, context/fallback signal,
stop reason, usage, prompt/artifact digests, task-local classification, and gate evidence.
Private paths, settings, credentials, and raw transcripts do not belong in this installed
skill; the stable IDs and digests above permit an authorized reviewer with source access to
reconcile the evidence.
