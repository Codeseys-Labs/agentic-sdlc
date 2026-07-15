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

## Four semantic tiers and eligible pairs

The six exact primary IDs form three peer pairs inside four semantic tiers. Pair membership
expresses a failure class, not a global provider preference or an equivalence-score claim.
Choose within a pair by task fit, the value of an independent vendor perspective, current
quota, correlated-error risk, and verified transport. A workflow uses only the models its
artifacts need; artificial one-of-each representation wastes tokens and can weaken review
independence.

| Semantic tier | Wrong-output consequence | Eligible exact pair | Requested effort | Required gate or control |
|---|---|---|---|---|
| Frontier | Derail / settled truth | `gpt-5.6-sol` or `claude-fable-5` | Sol `high`/`xhigh`; Fable `xhigh`/`max` | Solo or bounded; independent re-derivation; conductor adjudicates |
| Judgment workhorse | Contained silent degradation | `gpt-5.6-terra` or `claude-opus-4-8` | Terra `xhigh`/`max`; Opus `high`/`xhigh` | Explicit acceptance criteria and independent immutable-candidate review |
| Capable volume | Gated visible retry | `gpt-5.6-luna` or `claude-sonnet-5` | Luna `high`/`xhigh`; Sonnet `high`/`xhigh` | Compiler, tests, schema, diff, evidence check, or deterministic verifier |
| Mechanical floor | Cheap fully checked redo | Cheapest certified route from `gpt-5.6-luna` or `claude-sonnet-5` | `low`/`medium` after route-specific certification | Complete deterministic check; retry or escalate on any mismatch |

The mechanical tier is a cost-and-gate selection within the capable-volume class, not a
seventh primary model. Historical `claude-haiku-4-5` and `gpt-5.3-codex-spark` evidence may
support a fallback after the exact route is recertified, but neither belongs to the six-primary
set. A mechanical task without a complete deterministic check moves back to capable volume
or judgment workhorse.

### Fable eligibility constraint

Fable is eligible only for a certified, bounded frontier/adversarial packet; it never settles truth or replaces the Sol peer. Its packet must be independently re-derived, must
name its assumptions and counterexamples, and remains advisory to the conductor. Settled-truth work stops or reduces scope if no certified peer is available. This boundary is semantic as
well as capacity control: a Fable answer can attack a conclusion but cannot be silently
promoted into that conclusion.

## Exact dispatch and requested effort

Every dispatching Workflow consumer must receive an exact bare ID certified by the active
transport. It must stop before dispatch when that certification or adapter readback is
unresolved; a provider-neutral static role definition does not select a model. Bare Claude
tier aliases are unsafe in the current path because settings expand them to
provider-qualified IDs that ccodex rejects. This calibration does not change settings,
trust, or configuration.

| Consequence lane | Eligible primary exact IDs | Selection condition | Requested effort | Complement | Required gate or control |
|---|---|---|---|---|---|
| Derail / settled truth | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol when it must form the advisory frame or settled-truth derivation; choose Fable only when it is the certified bounded adversarial packet and Sol remains the peer. | Sol `high`, `xhigh`; Fable `xhigh`, `max` | The non-selected member supplies a distinct frame or counterexample artifact. | Re-derivation; conductor adjudicates the advisory recommendation. |
| Contained silent-degrade | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for the semantic candidate or synthesis; choose Opus when it reviews an immutable semantic delta or produces a separately certified judgment artifact. | Terra `xhigh`, `max`; Opus `high`, `xhigh` | The non-selected member reproduces the candidate or reviews the immutable delta. | Explicit acceptance criteria and independent review. |
| Deterministic-gated volume | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the member with verified transport, task fit, and the less-correlated evidence path when the same deterministic gate catches failure. | Luna `high`, `xhigh`; Sonnet `high`, `xhigh` | The non-selected member checks stable evidence or produces deterministic receipts. | Compiler, tests, schema, diff, or deterministic verifier. |
| Cheap fully checked redo | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the cheapest certified member only when a complete deterministic check makes every wrong result cheap to repeat. | `low`, `medium` after route-specific certification | The other capable-volume member is a fallback only while the same complete check remains. | Complete deterministic check; retry or escalate on any mismatch. |

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

### Historical rejected alias evidence

The original run requested aliases. Settings expanded each alias before ccodex validation,
and all 15 cells per model (five efforts times three lenses) failed transport. These are
historical rejection examples, not affirmative executable syntax:

| Alias requested | Settings-expanded request | Observed result | Required exact replacement |
|---|---|---|---|
| `fable` | `global.anthropic.claude-fable-5` | HTTP 400 unknown model | `claude-fable-5` |
| `opus` | `us.anthropic.claude-opus-4-8` | HTTP 400 unknown model | `claude-opus-4-8` |
| `sonnet` | `global.anthropic.claude-sonnet-5` | HTTP 400 unknown model | `claude-sonnet-5` |
| `haiku` | no accepted current ccodex alias receipt | not certified as executable | use a separately certified exact fallback only |

This is configuration/transport evidence, not evidence that the Claude models are
unavailable or incapable. Exact bare Claude IDs later completed. An alias becomes safe
only after its outbound request and transcript readback match the intended exact model in
the active session. Do not write bare aliases or provider-qualified aliases in executable
`model` fields; historical rejection examples above are retained solely to prevent that
regression.

### Requested versus effective effort

The harness accepted `low`, `medium`, `high`, `xhigh`, and `max`, but effective effort is
not exposed in the available transcript readback. A success token that repeats prompt text
proves neither upstream receipt nor effective reasoning effort. The v1 receipt fields remain:

```yaml
requested_effort: low|medium|high|xhigh|max
effort_readback_status: unavailable
effort_readback_evidence:
  source_kind: transport_readback
  status: unavailable
  schema: runtime-assignment-readback/v1
```

Never copy requested effort into effective readback. Reclassify it only when proxy/upstream
request or response telemetry independently exposes the effective value.

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

| Wrong-output consequence | Eligible primary exact IDs | Selection condition | Requested effort | Complement | Required control |
|---|---|---|---|---|---|
| Cheap deterministic retry | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the cheaper certified member when exact comparison, schema, or bounded retry catches every mismatch. | `high`, or `low`/`medium` only after route certification | The non-selected member checks evidence rather than repeating the task. | Exact comparison, schema, or bounded retry. |
| Visible compiler/test/gate failure | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the member with verified transport and a distinct evidence path when compiler, tests, diff, or verifier makes failure visible. | `high`, `xhigh` | The non-selected member checks the stable result. | Compiler, tests, diff, or deterministic verifier. |
| Silent candidate degradation | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra when producing the candidate; choose Opus only for a separately certified immutable semantic review. | Terra `xhigh`, `max`; Opus `high`, `xhigh` | The non-selected member reviews the semantic delta or reproduces the candidate. | Immutable candidate and independent acceptance review. |
| Run derailment or settled truth | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory frame or truth derivation; choose Fable only as the certified bounded assumptions attacker with Sol as peer. | Sol `high`, `xhigh`; Fable `xhigh`, `max` | The non-selected member provides the re-derivation or bounded counterexample packet. | Re-derivation; conductor records the stop/go disposition. |
| Trust, credentials, authority, or data-loss boundary | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol to analyze the authority boundary; choose Fable only for certified bounded adversarial counterexamples, never to settle the boundary. | Sol `xhigh`; Fable `xhigh`, `max` | The non-selected member attacks assumptions or reviews implementation semantics. | Conductor adjudicates; fail closed and demand concrete evidence. |

Outward or irreversible operations require human authorization, not a model dispatch. Models
may recommend only; separate operation-specific human approval remains required.

No model grants queue, fan-in, publication, or user authority. The conductor alone
adjudicates and mutates Seeds; only an authorized integrator performs an already-authorized
fan-in; humans authorize outward actions.

## Agentic SDLC phase routing

| Phase | Eligible primary exact IDs | Selection condition | Requested effort and context | Complement | Gate or control |
|---|---|---|---|---|---|
| Frame | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory frame; choose Fable only as the certified bounded adversarial assumptions packet. | Sol `high`; `xhigh` at trust or authority boundaries; `[1m]` only for transcript or repository-heavy frames; Fable `max` bounded packet | The non-selected member re-derives or attacks multiplier assumptions. | Re-derive; conductor adjudicates the recommendation. |
| Discover | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for dense mapping; choose Opus when an immutable semantic candidate needs independent review. | Terra `xhigh`; `[1m]` for repository-wide readers; Opus `high`, `xhigh` | The non-selected member checks citations and omissions. | Partitioned scope and evidence inventory. |
| Research | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for synthesis; choose Opus for a certified semantic review of the evidence packet. | Terra `xhigh`, `max`; `[1m]` only for long corpora; Opus `high`, `xhigh` | Luna/Sonnet can extract; Sol analyzes load-bearing unknowns. | Conductor adjudicates unknown disposition. |
| Plan | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory plan; choose Fable only to attack certified bounded multiplier assumptions. | Sol `xhigh`; `[1m]` when repository-wide evidence is consumed; Fable `max` bounded packet | The non-selected member returns the plan or counterexample artifact. | Advisory plan; conductor alone mutates Seeds. |
| Act, contained | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to implement interacting constraints; choose Opus to review immutable candidate decisions. | Terra `xhigh`; `max` for interacting constraints; Opus `high`, `xhigh` | The non-selected member produces candidate or review. | Unsuffixed unless artifact-heavy. |
| Act, deterministic-gated | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the member with verified transport and independent evidence when the deterministic gate remains complete. | `high`, `xhigh` | The non-selected member checks stable evidence. | Unsuffixed by default; same deterministic gate. |
| Review, semantic | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Opus for semantic review; choose Terra to reproduce and classify an immutable candidate. | Opus `high`, `xhigh`; Terra `xhigh`, `max`; Claude `[1m]` only after exact route certification | The non-selected member supplies review or reproduction. | Immutable candidate and acceptance criteria. |
| Review, trust or authority | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for authority analysis; choose Fable only to search a certified bounded counterexample packet. | Sol `xhigh`; Fable `max` bounded packet | The non-selected member supplies authority analysis or counterexamples. | Advisory analysis; conductor adjudicates. |
| Reconcile | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to reconcile semantic evidence; choose Opus to review the immutable reconciliation candidate. | Terra `xhigh`; Opus `high`, `xhigh` | Sonnet validates evidence links. | Conductor alone records Seeds mutations. |
| Integrate | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to integrate; choose Opus to review fan-in semantics after the integration head is immutable. | Terra `max`; Opus `high`, `xhigh` | Luna re-runs gates; the non-selected judgment member reviews or integrates. | Authorized integrator only; re-gate on integration head. |
| Ship recommendation | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for promotion analysis; choose Fable only as a certified bounded adversarial receipt packet. | Sol `xhigh`; Fable `xhigh`, `max` bounded packet | Luna/Sonnet validate receipts. | Human separately authorizes outward action. |

## Approved roadmap family lanes

Each complement produces an orthogonal artifact rather than duplicating the whole task.
Every route below remains provisional/requested-only under the effort-readback boundary.

| Roadmap lane | Eligible primary exact IDs | Selection condition | Requested effort and context | Complementary assignment | Gate or escalation |
|---|---|---|---|---|---|
| S1 Seeds toolchain retention | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the more independent evidence path when checks are deterministic. | `high` | The non-selected member checks evidence-to-claim coverage; Terra analyzes semantic drift. | Terra at `xhigh` recommends disposition. |
| S2 Seeds execution contract | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for contract synthesis; choose Opus for immutable stable-diff review. | Terra `xhigh`; Opus `xhigh` | Sol analyzes queue evidence; the non-selected judgment member reviews or synthesizes. | Null or mismatch fails closed; conductor adjudicates Seeds action. |
| Seeds fan-in | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to integrate; choose Opus only to review the immutable fan-in candidate. | Terra `max`; Opus `xhigh` | Luna re-gates exact ranges; Sol analyzes stop/go ambiguity. | Authorized integrator only; conductor adjudicates. |
| Wave 1 CAO deletion | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for removal implementation; choose Opus for removed-surface review. | Terra `xhigh`; Opus `high` | Luna inventories residues. | Any shipped or runtime residue blocks. |
| Wave 2 state-v3 identity cutover | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for cutover implementation; choose Opus for recovery review of the immutable candidate. | Terra `max`; Opus `xhigh` | Sol analyzes migration invariants; Luna runs crash matrix. | Fail closed on foreign ownership; conductor adjudicates. |
| Claude marketplace/plugin plane | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for supported operation work; choose Opus for opaque-boundary review. | Terra `xhigh`; Opus `xhigh` | The non-selected member produces the separate semantic artifact. | Never edit opaque state. |
| Local checkout rename gate | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory rename frame; choose Fable only for certified bounded adversarial receipt review. | Sol `xhigh`; Fable `max` bounded packet | Luna verifies pre/post receipts. | Human approval before mutation. |
| GitHub repository rename gate | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for authority analysis; choose Fable only to attack a certified bounded authorization packet. | Sol `xhigh`; Fable `max` bounded packet | Sonnet inventories post-authorization evidence. | Human approval; model never authorizes. |
| A1 change-writing | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for writing; choose Opus for immutable evidence and attribution review. | Terra `xhigh`; Opus `high` | Luna builds fixtures. | Output-only contract. |
| A2 Git-default sdlc-init | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for implementation; choose Opus for the certified safety review. | Terra `max`; Opus `xhigh` | Sol analyzes defaults and refusals; Luna builds fixtures. | Dry-run and no-write cancellation. |
| A3 hierarchical instructions | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for instruction work; choose Opus for markers and ownership review. | Terra `xhigh`; Opus `high` | Sonnet checks conformance. | Preserve foreign prose. |
| R1 shared role contracts | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for contracts; choose Opus for stable-diff semantic review. | Terra `xhigh`; Opus `xhigh` | Sol analyzes separation of powers; Fable attacks a bounded authority packet; Luna projects fixtures. | All analysis advisory; conductor adjudicates. |
| R2 bounded Deep Work Loop | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for loop implementation; choose Opus for bounded-recursion review. | Terra `xhigh`; Opus `xhigh` | Sol analyzes bounds and backflow; Luna tests. | No second queue or unbounded recursion. |
| R3 HyperResearch/Research OS | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for bounded orchestration; choose Opus for crash-recovery semantic review. | Terra `max`; Opus `xhigh` | Sonnet extracts evidence; Sol analyzes load-bearing unknowns. | Typed `SeedProposal`; conductor alone mutates Seeds. |
| G1 Git change-flow family | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for change-flow work; choose Opus for rebase, squash, and stack review. | Terra `xhigh`; Opus `xhigh` | Luna builds fixtures. | Stable commit and merge-base evidence. |
| G2 toolchain/security | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for semantic implementation; choose Opus for semantic security review. | Terra `max`; Opus `high` | Sol analyzes trust evidence; Luna tests falsifiability. | Exact gate argv, status, and log digest. |
| J1 jj certification | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for certification synthesis; choose Opus for immutable handoff review. | Terra `[1m]` at `xhigh`; Opus `xhigh` | Sol analyzes framing; Luna builds fixture matrix; Fable attacks data-loss assumptions. | Official docs and immutable Git handoff; conductor adjudicates. |
| J2 jj implementation | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for implementation; choose Opus for handoff and recovery review. | Terra `max`; Opus `xhigh` | Luna builds fixtures. | Conflict-free exact Git OID. |
| A2j jj init amendment | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for amendment work; choose Opus for an immutable semantic review if the gate no longer catches risk. | Terra `xhigh`; Opus `high` | Sonnet checks explicit selection and receipt. | Only after J1/J2 certification. |
| M0a Mermaid browser ADR/spike | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for ADR/spike synthesis; choose Opus for browser-dependency review. | Terra `[1m]` at `xhigh`; Opus `xhigh` | Sol analyzes dependency evidence; Luna builds host/offline matrix. | Stop before M1 without portable provider; conductor adjudicates. |
| M0b Mermaid security foundation | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for foundation implementation; choose Opus for malicious-SVG semantic review. | Terra `max`; Opus `xhigh` | Luna builds parser/render matrix. | Strict allowlist and bounded resources. |
| M1 structural Mermaid skills | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the strongest deterministic document/fixture evidence path. | `xhigh` | The non-selected member checks docs, citations, and fixtures. | One writer and pipeline reviewer. |
| M2 planning Mermaid skills | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the strongest deterministic document/fixture evidence path. | `xhigh` | The non-selected member checks docs, citations, and fixtures. | One writer and pipeline reviewer. |
| M3 quantitative Mermaid skills | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the strongest deterministic document/fixture evidence path. | `xhigh` | The non-selected member checks docs, citations, and fixtures. | One writer and pipeline reviewer. |
| M4 technical Mermaid skills | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the strongest deterministic document/fixture evidence path. | `xhigh` | The non-selected member checks docs, citations, and fixtures. | One writer and pipeline reviewer. |
| M5 conceptual Mermaid skills | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the strongest deterministic document/fixture evidence path. | `xhigh` | The non-selected member checks docs, citations, and fixtures. | One writer and pipeline reviewer. |
| M6 Mermaid router | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for router synthesis; choose Opus for semantic review of exact-one routing. | Terra `xhigh`; Opus `high` | Sonnet inventories exact-one routing. | Reject unsupported or ambiguous requests. |
| M7 Mermaid conformance | `gpt-5.6-luna` or `claude-sonnet-5` | Choose Luna for deterministic conformance; choose Sonnet for a separately certified gated evidence pass. | `xhigh` | Opus reviews malicious output semantics; Sol analyzes final evidence. | Exactly one router plus 30 skills; conductor adjudicates. |
| Release hardening | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for hardening synthesis; choose Opus for immutable release-semantic review. | Terra `max`; Opus `high` | Luna builds cross-platform fixtures; Sol recommends promotion. | Publication separately authorized by humans. |
| Evolutionary Core M2 | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for core implementation; choose Opus for immutable candidate review. | Terra `max`; Opus `xhigh` | Sol analyzes kernel contracts; Luna runs crash suite. | Deterministic receipt and idempotent reconcile. |
| Claude Golden Wave M3 | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for adapter work; choose Opus for semantics review after exact Claude readback. | Terra `max`; Opus `xhigh` | Sol analyzes adapter/authority; Sonnet checks conformance; Fable attacks bounded assumptions. | Exact Claude ID, effort, and context readback. |
| Portability M4 | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for portability implementation; choose Opus for immutable assumptions review. | Terra `max`; Opus `xhigh` | Sol analyzes portability; Luna runs common fault suite; Sonnet checks conformance. | No public ABI before three adapters. |
| CCP/ccodex certification | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for certification; choose Opus for implementation semantics review. | Terra `[1m]` at `max`; Opus `xhigh` | Sol analyzes package evidence; Luna checks lifecycle; Fable attacks credential assumptions. | Exact version, checksum, and readback. |
| Final family wiring | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for wiring; choose Opus for an immutable semantic review when conformance evidence is incomplete. | Terra `xhigh`; Opus `high` | Sonnet verifies cross-links and inventory. | No unrelated family co-mingling. |

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

The current six-primary pair policy is the production default. Preserve these older GPT
fallback observations as historical compatibility evidence; re-certify their current
transport and keep the same blast-radius controls before use:

- Derail-class history: `gpt-5.6-sol` → `gpt-5.5` → `gpt-5.4`; if none is certified,
  stop or explicitly reduce scope.
- Contained-degrade history: `gpt-5.6-terra` → `gpt-5.5` → `gpt-5.4`.
- Visible-retry history: `gpt-5.6-luna` → `gpt-5.4-mini` → `gpt-5.3-codex-spark`
  only for a sufficiently bounded, fully verified artifact.
- Cheap-mechanical history: `gpt-5.6-luna` → `gpt-5.3-codex-spark` →
  `gpt-5.4-mini`; historical `claude-haiku-4-5` remains a possible recertified mechanical
  fallback, not a seventh primary.

These rows are evidence, not a host-default fallback chain. Never cross downward unless a
real verifier changes the failure into a visible retry.

1. Treat null, malformed, truncated, missing, or transport-rejected output as failure.
2. Inspect the transcript; distinguish transport/harness failure from an answered task;
   apply bounded provider backoff and retry the same certified exact model/effort once.
3. On 429 or overload, reduce concurrency. Do not lower effort, gate strength, or
   blast-radius class merely to make pressure disappear.
4. Never fall back from an exact Claude ID to the historical rejected aliases in this session.
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
from one Amazon Bedrock account in `us-east-1`, dated 2026-07-05. It is account-, region-,
provider-, and date-specific and may not describe ccodex traffic. Re-query before using it
for fan-out sizing. The provider/account/region/date qualifier applies to every value and
caveat in this section, not to the six-model policy itself.

| Historical Claude lane | Cross-region TPM | Global cross-region TPM | Global CRIS tokens/day | Invocation tokens/day | RPM | Historical fully-gated concurrency |
|---|---:|---:|---:|---:|---:|---|
| Fable 5 | 200K | 500K | 720M | 144M | TPM-bound | 1, maybe 2 bounded agents |
| Opus 4.8 | 30M | 30M | 43.2B | 21.6B | TPM-bound | Dozens in parallel |
| Sonnet 5 | 6M | 6M | 8.64B | 4.32B | TPM-bound | ~20–60 heavy agents |
| Haiku 4.5 | 5M | 5M | 7.2B | 3.6B | 10K | ~20–50 heavy agents |

Historical Fable use on that Bedrock account required mandatory provider_data_share retention,
carried stricter refusal/safety behavior on dual-use content, and could encounter day-one
capacity can flap independently of quota. Those are provider/account/region/date-qualified
operational caveats, not claims about every Fable transport. A Fable 503 on an early-capacity
path can be a capacity symptom rather than a configuration proof; preserve the transport
receipt before reclassifying it.

There is no Sol, Terra, or Luna quota evidence available: no GPT RPM, TPM, daily,
concurrency, or cost limit was measured. Successful parallel completion is not a quota
benchmark. Start with bounded width and record overlap, 429s, latency, and token use.

Semantic caps apply regardless of capacity: one canonical scale-setter at a time, one
bounded adversarial attacker, one writer per worktree, one conductor, integrator WIP 1,
and bounded passes/review-fix rounds.

Historical operational receipts remain useful but do not certify the current transport and
are not deterministic receipts:

- Historical operator note for `wf_497ea95a-e7f` (2026-07-05): a Sonnet-5 fleet completed
  **61 agents / 9.05M subagent tokens / 2h12m** with zero observed throttling in that run.
  Adversarial verification preserved 16/21 critical/high findings, including a real critical
  security finding. Its published linkage is incomplete, so this is retained as a clearly
  downgraded historical claim rather than a current concurrency certification. The structural
  verifier, not a total intelligence claim, justified that gated volume lane.
- Historical operator note for `dcperf-automation` (2026-06-11): an Opus-era
  **6-dimension review + adversarial verification** used the then-current workhorse lane.
  Its published linkage is incomplete, so it is historical rationale for preserving an
  ungated semantic workhorse, not evidence that current work must use the same provider or
  model.

Reproduce representative current workloads before turning either receipt into concurrency,
quality, cost, or quota policy.

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
