# Six-model routing calibration

**Calibration ID:** `six-tier-2026-07-14`

**Record date:** 2026-07-14

**Scope:** current Workflow/ccodex transport and the approved Agentic SDLC roadmap

**Claim boundary:** transport and three-lens smoke evidence; not a total ranking and not production proof

This is the sole authored generation-specific routing matrix. The sibling `SKILL.md`
owns stable blast-radius doctrine. Other skills should link here rather than copy model,
effort, quota, or roadmap tables.

Keep four facts separate:

1. **Requested dispatch:** exact model ID, effort, and context form sent by the client.
2. **Resolved readback:** model, effort, provider, and context behavior independently
   exposed by the active adapter or upstream telemetry.
3. **Task-local smoke result:** whether one bounded lens contract received a correct
   answer, received a wrong answer, or never received an answer because the harness failed.
4. **Production recommendation:** a provisional policy based on blast radius, gates,
   authority, inherited operational evidence, and the approved roadmap.

## Exact dispatch and requested effort

Every Workflow agent must carry one exact ID. Bare Claude tier aliases are unsafe in the
current path because settings expand them to provider-qualified IDs that ccodex rejects.
Do not edit user settings as part of applying this policy.

| Lane | Exact request ID | Current purpose | Provisional production effort band |
|---|---|---|---|
| Derail / settled truth | `gpt-5.6-sol` | Frame, authority, cross-system invariants, final stop/go | `high`, `xhigh` |
| Contained silent-degrade | `gpt-5.6-terra` | Implementation, investigation, synthesis, integration semantics | `xhigh`, `max` |
| Deterministic-gated volume | `gpt-5.6-luna` | Fixtures, receipts, transforms, compiler/test/diff-gated work | `high`, `xhigh` |
| Bounded adversarial specialist | `claude-fable-5` | Counterexample search over a small trust/authority assumptions packet | `max` |
| Semantic-review specialist | `claude-opus-4-8` | Immutable-candidate review and ungated contained micro-decisions | `high`, `xhigh` |
| Gated-verification specialist | `claude-sonnet-5` | Evidence checks, citation coverage, stable-result verification, volume | `high`, `xhigh` |

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
latency, cost, reliability, quota, provider-placement, total-ranking, or production-proof
claim. Numeric judge scores were discarded because judges mixed scales and sometimes
penalized a response for not answering other independent lenses.

## Blast-radius production routing

| Wrong-output consequence | Primary route | Complement | Required control |
|---|---|---|---|
| Cheap deterministic retry | `gpt-5.6-luna@high` | `claude-sonnet-5@high` checks evidence rather than repeating the task | Exact comparison, schema, or bounded retry |
| Visible compiler/test/gate failure | `gpt-5.6-luna@high|xhigh` | `claude-sonnet-5@high|xhigh` checks the stable result | Compiler, tests, diff, or deterministic verifier |
| Silent candidate degradation | `gpt-5.6-terra@xhigh|max` | `claude-opus-4-8@high|xhigh` reviews the semantic delta | Immutable candidate and independent acceptance review |
| Run derailment or settled truth | `gpt-5.6-sol@high|xhigh`, normally solo | `claude-fable-5@max` attacks a bounded assumptions packet | Re-derivation and explicit stop/go record |
| Trust, credentials, authority, or data-loss boundary | `gpt-5.6-sol@xhigh` owns the decision | Fable counterexample search; Opus implementation-semantic review | Fail closed and demand concrete evidence |
| Outward or irreversible operation | Human authorization | Models may recommend only | Separate operation-specific approval |

No model grants queue, fan-in, publication, or user authority. The conductor alone mutates
Seeds; only the integrator executes an already authorized fan-in; every outward operation
retains its own explicit authorization gate.

## Agentic SDLC phase routing

| Phase | Primary route | Complement | Context and gate |
|---|---|---|---|
| Frame | Sol `high`; `xhigh` at trust/authority boundaries | Fable `max` attacks load-bearing assumptions only | Sol `[1m]` only for transcript/repository-heavy frames |
| Discover | Terra `xhigh`, partitioned by area | Sonnet `high` checks citations and omissions | Terra `[1m]` for repository-wide readers |
| Research | Terra `xhigh|max` synthesizes | Sonnet extracts; Sol decides load-bearing unknowns | `[1m]` only for long corpora |
| Plan | Sol `xhigh` | Fable `max` attacks multiplier assumptions | `[1m]` when repository-wide evidence is consumed |
| Act, contained | Terra `xhigh`; `max` for interacting constraints | Opus reviews immutable candidate decisions | Unsuffixed unless artifact-heavy |
| Act, deterministic-gated | Luna `high|xhigh` | Sonnet checks stable evidence | Unsuffixed by default |
| Review, semantic | Opus `high|xhigh` | Terra reproduces and classifies findings | Claude `[1m]` only after exact route certification |
| Review, trust/authority | Sol `xhigh` | Fable `max` searches a bounded packet for counterexamples | Sol owns the recommendation |
| Reconcile | Terra `xhigh` prepares dispositions | Sonnet validates evidence links | Conductor alone records Seeds mutations |
| Integrate | Terra `max`; integrator WIP 1 | Luna re-runs gates; Opus reviews fan-in semantics | Re-gate on integration head |
| Ship recommendation | Sol `xhigh` | Luna/Sonnet validate receipts | User separately authorizes outward action |

## Approved roadmap family lanes

Each complement produces an orthogonal artifact rather than duplicating the whole task.
Every route below remains provisional/requested-only under the effort-readback boundary.

| Roadmap lane | Primary assignment | Complementary assignment | Gate or escalation |
|---|---|---|---|
| S1 Seeds toolchain retention | Luna `high` verifies pins, lock bytes, and receipts | Sonnet `high` checks evidence-to-claim coverage | Terra `xhigh` only for semantic drift |
| S2 Seeds execution contract | Terra `xhigh` implements exact invocation and recursive coverage | Sol `xhigh` decides queue authority; Opus `xhigh` reviews stable diff | Null or mismatch fails closed |
| Seeds fan-in | Terra `max` as sole integrator | Luna `high` re-gates exact ranges | Sol `xhigh` only for stop/go ambiguity |
| Wave 1 CAO deletion | Terra `xhigh` implementation | Luna `high` negative inventory; Opus `high` removed-surface review | Any shipped/runtime residue blocks |
| Wave 2 state-v3 identity cutover | Sol `xhigh` fixes migration invariants; Terra `max` implements | Luna `xhigh` crash matrix; Opus `xhigh` ownership/recovery review | Fail closed on foreign ownership |
| Claude marketplace/plugin plane | Terra `xhigh` isolated migration fixtures | Opus `xhigh` checks supported-operation boundary | Never edit opaque state |
| Local checkout rename gate | Sol `xhigh` recommendation only | Luna `high` verifies pre/post receipts | Human approval before mutation |
| GitHub repository rename gate | Sol `xhigh` recommendation only | Sonnet `high` inventories post-authorization evidence | Human approval; model never authorizes |
| A1 change-writing | Terra `xhigh` implementation | Opus `high` evidence/attribution review; Luna `high` fixtures | Output-only contract |
| A2 Git-default sdlc-init | Terra `max` implementation | Sol `xhigh` defaults/refusals; Opus `xhigh` safety; Luna `high` fixtures | Dry-run and no-write cancellation |
| A3 hierarchical instructions | Terra `xhigh` generator | Sonnet `high` conformance; Opus `high` marker/ownership review | Preserve foreign prose |
| R1 shared role contracts | Sol `xhigh` separation-of-powers decisions; Terra `xhigh` manifest | Fable `max` attacks authority packet; Luna `high` projections | Fable advisory; conductor decides |
| R2 bounded Deep Work Loop | Sol `xhigh` bounds/backflow; Terra `xhigh` implementation | Opus `xhigh` recursion/authority review; Luna `high` tests | No second queue or unbounded recursion |
| R3 HyperResearch/Research OS | Terra `max` ownership/recovery and synthesis | Sonnet evidence extraction; Opus crash review; Sol load-bearing unknowns | Typed `SeedProposal`, no queue mutation |
| G1 Git change-flow family | Terra `xhigh` consolidation | Opus `xhigh` rebase/squash/stack review; Luna `high` fixtures | Stable commit and merge-base evidence |
| G2 toolchain/security | Terra `max` implementation | Sol trust ruling; Opus semantic security review; Luna falsifiability | Exact gate argv/status/log digest |
| J1 jj certification | Sol `[1m]@xhigh` frame/final ruling; Terra `[1m]@xhigh` semantic research | Luna `high` fixture matrix; Fable `max` data-loss attack | Official docs and immutable Git handoff |
| J2 jj implementation | Terra `max` implementation | Opus `xhigh` handoff/recovery review; Luna `xhigh` fixtures | Conflict-free exact Git OID |
| A2j jj init amendment | Terra `xhigh` implementation | Sonnet `high` explicit-selection/receipt check | Only after J1/J2 certification |
| M0a Mermaid browser ADR/spike | Terra `[1m]@xhigh` research; Sol `xhigh` dependency decision | Opus browser/dependency review; Luna host/offline matrix | Stop before M1 without portable provider |
| M0b Mermaid security foundation | Terra `max` implementation | Opus `xhigh` malicious-SVG review; Luna parser/render matrix | Strict allowlist and bounded resources |
| M1 structural Mermaid skills | Luna `xhigh` gated writer in one worktree | Sonnet `high` checks docs/citations/fixtures | One writer and pipeline reviewer |
| M2 planning Mermaid skills | Luna `xhigh` gated writer in one worktree | Sonnet `high` checks docs/citations/fixtures | One writer and pipeline reviewer |
| M3 quantitative Mermaid skills | Luna `xhigh` gated writer in one worktree | Sonnet `high` checks docs/citations/fixtures | One writer and pipeline reviewer |
| M4 technical Mermaid skills | Luna `xhigh` gated writer in one worktree | Sonnet `high` checks docs/citations/fixtures | One writer and pipeline reviewer |
| M5 conceptual Mermaid skills | Luna `xhigh` gated writer in one worktree | Sonnet `high` checks docs/citations/fixtures | One writer and pipeline reviewer |
| M6 Mermaid router | Terra `xhigh` ambiguity/selection implementation | Sonnet `high` exact-one inventory | Reject unsupported/ambiguous requests |
| M7 Mermaid conformance | Luna `xhigh` full matrix | Opus malicious-output semantics; Sol `high` final ruling | Exactly one router plus 30 skills |
| Release hardening | Terra `max` implementation | Luna cross-platform fixtures; Opus semantics; Sol promotion recommendation | Publication separately authorized |
| Evolutionary Core M2 | Sol `xhigh` kernel contracts; Terra `max` implementation | Luna crash suite; Opus immutable-candidate review | Deterministic receipt/idempotent reconcile |
| Claude Golden Wave M3 | Sol `xhigh` adapter/authority contract; Terra `max` implementation | Opus semantics; Sonnet conformance; Fable bounded attack | Exact Claude ID/effort/context readback |
| Portability M4 | Sol `xhigh` portability ruling; Terra `max` adapters/packs | Luna common fault suite; Opus assumptions; Sonnet conformance | No public ABI before three adapters |
| CCP/ccodex certification | Terra `[1m]@max` proxy/package analysis; Sol `xhigh` final decision | Luna lifecycle; Fable credential attack; Opus implementation review | Exact version/checksum/readback |
| Final family wiring | Terra `xhigh` bounded inventory-only edits | Sonnet `high` cross-link/inventory verification | No unrelated family co-mingling |

## Complementary vendor roles

Use cross-vendor calls for different artifacts, not duplicated votes:

1. **Sol decides; Fable attacks.** Sol sees full evidence and owns the frame or stop/go
   recommendation. Fable receives only assumptions, authority edges, or trust boundaries
   and returns counterexamples; it does not write a second plan or own authority.
2. **Terra implements or synthesizes; Opus reviews the delta.** Terra owns the worktree or
   synthesis. Opus reviews an immutable candidate, merge-base footprint, and named
   micro-decisions; it does not reimplement the feature.
3. **Luna builds deterministic evidence; Sonnet checks coverage.** Luna owns fixtures,
   inventories, transforms, and receipts. Sonnet checks whether stable evidence supports
   each claim and whether citations are complete; it does not regenerate the matrix.
4. **The conductor adjudicates.** Distinct Maps, ResearchBriefs, SeedProposals, Candidates,
   ReviewFindings, and IntegrationReports remain submissions, never authority grants.

## Fallback and escalation

1. Treat null, malformed, truncated, missing, or transport-rejected output as failure.
2. Inspect the transcript; distinguish transport/harness failure from an answered task;
   apply bounded provider backoff and retry the same exact model/effort once.
3. On 429 or overload, reduce concurrency. Do not lower effort, gate strength, or
   blast-radius class merely to make pressure disappear.
4. Never fall back from an exact Claude ID to the unsafe aliases in this session.
5. A gated lane may cross Luna↔Sonnet only while the same deterministic gate remains.
6. A contained semantic lane may cross Terra↔Opus only against an immutable candidate and
   explicit acceptance criteria.
7. There is no automatic Sol→Fable authority fallback. Fable is a bounded advisory
   attacker. If Sol is unavailable for a derail/authority decision, stop or reduce scope.
8. Escalate Luna/Sonnet to Terra/Opus when gates pass but semantic uncertainty remains.
9. Escalate Terra/Opus to Sol when the unknown affects authority, credentials, data loss,
   cross-system invariants, workstream sizing, or stop/go.
10. If Sol and the advisory attacker disagree, re-enter scoped discovery/research/plan;
    never majority-vote an authority decision.
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
- Capture upstream resolved-effort telemetry for Sol `high|xhigh`, Terra `xhigh|max`, and
  Luna `high|xhigh`, base and `[1m]`.
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
