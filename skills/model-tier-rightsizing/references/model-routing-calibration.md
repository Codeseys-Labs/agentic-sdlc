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

Every dispatching Workflow consumer must receive an exact model request form certified by the
active transport. It must stop before dispatch when that certification or adapter readback is
unresolved; a provider-neutral static role definition does not select a model. **For an OCX
Ultracode Workflow, every explicit `model` passed to `agent()` is the exact `[1m]` request
form.** The exact `[1m]` model/effort/context tuple must be certified, admitted in the active
served catalog, and readable through required immutable request and identity evidence before the
call. An uncertified, unadmitted, unreadable, or ambiguous exact form must stop before dispatch
and return one `SeedProposal`; base/unsuffixed syntax is never a fallback. Preserve a provider prefix in the
marked form — for example, the syntax is `muse/muse-spark-1.2[1m]`, but it is not currently
certified or admitted and therefore must stop before dispatch. Bare Claude tier aliases are unsafe in the current path
because settings expand them to provider-qualified IDs that ccodex rejects. This calibration does
not change settings, trust, or configuration.

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
compaction boundary. Outside OCX Ultracode Workflow mode, use `[1m]` only for
transcript-, corpus-, or repository-heavy GPT assignments and otherwise prefer bounded
disk-backed artifacts. In OCX Ultracode Workflow mode, the marker is mandatory on **every**
explicit `agent()` model request instead: an uncertified Claude or Muse `[1m]` tuple stops before
dispatch rather than reverting to an unsuffixed compact packet. At this calibration date, the
listed policy certifies `[1m]` tuples only for the GPT primary IDs. Exact Claude `[1m]` forms
were not separately certified and remain unadmitted until those request forms pass.

## Context windows

Served models have genuinely different context windows, and no single layer both knows every
window and can apply it per model. This section is the sole owner of the per-model numbers;
other references point here rather than restating them.

### Per-model windows and their shared-versus-separate shape

| Exact model ID | Gateway-computed | Provider-documented | Input/output shape | Source status |
|---|---:|---:|---|---|
| `gpt-5.6-sol` | 372000 | 1050000 API / 272000 subscription | separate: 922000 in + 128000 out | provider-documented; gateway value disagrees |
| `gpt-5.6-terra` | 372000 | 1050000 API / 272000 subscription | separate: 922000 in + 128000 out | provider-documented; gateway value disagrees |
| `gpt-5.6-luna` | 372000 | 1050000 API / 272000 subscription | separate: 922000 in + 128000 out | provider-documented; gateway value disagrees |
| `gpt-5.5` | 272000 | 1050000 API / 272000 subscription | total and output published; input unknown | provider-documented, partial |
| `gpt-5.4` | 1000000 | 1050000 API / 272000 subscription default | total and output published; input unknown | provider-documented, partial |
| `gpt-5.4-mini` | unknown | 400000 API | separate: 272000 in + 128000 out | provider-documented; gateway has no value |
| `gpt-5.3-codex-spark` | 100000 | 128000 announcement only | unknown | announcement only; no API model page |
| `muse-spark-1.2` | unknown | 1048576 measured | **shared** input+output pool | measured by bisection |
| `muse-spark-1.2-contributor` | unknown | 1048576 measured | **shared** input+output pool | measured by bisection |
| `muse-spark-1.1` | unknown | unknown | presumed shared, unmeasured | unknown |

A blank is recorded as `unknown`, never inferred from a sibling model. Four served models
have no gateway-computed window at all, which is conservative for compaction and also means
no per-model floor can be computed for them.

The gateway-computed value for the 5.6 family is **above** the provider's current
subscription catalog. That direction is the dangerous one: it aims a session past the real
ceiling rather than short of it. Treat the lower provider number as the operating limit for
5.6 work until the two agree.

### The shared input/output hazard

Two provider shapes are in play and they are not interchangeable. The GPT family publishes an
input window plus a **separate** output reservation that sums to the advertised total. Muse
Spark has **one shared pool** of exactly 1048576 tokens, measured by bisection: for a given
input, `max_output_tokens = 1048576 − counted_input` is admitted and one more is refused.

On a shared pool, input and output compete directly, so a large input silently shrinks the
output allowance. Starvation there is not an error: an insufficient output budget returns a
successful HTTP status with empty content while reasoning tokens are still billed, because
reasoning is charged before any visible text. Consequences for dispatch:

- A liveness or health check that asserts only a successful status is worthless on a shared-
  pool route. Assert non-empty output text.
- The distinguishing signal is the response's own completion/stop field, not the status code.
- Reasoning consumption on trivial prompts was observed spanning roughly 48–499 tokens, so an
  output budget below roughly 600 risks an empty completion for a one-word answer. A real task
  needs its expected output plus that reasoning allowance.
- Above the window the failure class can change to throttling rather than an invalid-request
  refusal, so a retry-on-throttle client can retry a request that can never succeed.

### Layer ownership: the gateway owns the number, the session owns a floor

The client's context and compaction controls are **per session, process-wide** — one value
for the whole process regardless of which model answers a given request. Agent and subagent
definitions carry no context field, and no settings key maps a model to a window. So a session
that switches models, or fans out subagents across models in one process, cannot hold a
per-model window at the session layer.

The gateway can. Therefore:

- **Configure the gateway, not the session, whenever the gateway can hold the fact.** A
  gateway setting applies to every client and survives a new process; a session variable
  applies to one process and is easy to forget.
- **The session-level compaction floor must be safe for the smallest model reachable in that
  session**, never the largest. Tuning a floor upward for one large model both wastes nothing
  and breaks nothing only when the session is genuinely single-model; otherwise it pushes the
  compaction net behind a smaller model's real limit.
- **Raising the floor can silently disqualify mid-size models** from extended-context marking,
  because marking requires the model's window to be at least the floor. A floor is two-sided.
- An over-window request can surface as an opaque upstream refusal rather than a recoverable
  one, because a gateway that rewrites the upstream error text defeats wording-matched
  automatic compact-and-retry. Manual compaction is then the only recovery.
- One over-window case is **not** upstream at all and must not be recorded as one. A 413 whose
  error type is `input_admission_refused` (new in `2.28.0`; a live `2.11.1` gateway never emits
  it) is opencodex's own input-admission preflight — an inbound token estimate above the route's
  ceiling × 2.5, refused locally before any provider request — so the attempt reaches no
  upstream: its attribution record exists but correlates to no provider serve. Other 413s exist,
  local (buffer and body-size limits) and upstream (Anthropic's own `request_too_large` on the
  passthrough route), so match the error type, never the bare status. `rightsize.py:
  identity_evidence` names the preflight class distinctly from a generic `transport-status`, and
  it is still fail-closed: no receipt, no admitted result. The remedy for the preflight class is
  a smaller packet or a larger-window route, never a retry against the same route and prompt.
- A window at or below the client's documented minimum floor cannot be matched by the floor
  variable at all. Keep such routes to bounded packets.

Where per-model editability exists it is uneven: a routed provider's per-model window map is
operator-settable, while natively-pinned model windows are compiled into the gateway and are
not correctable from configuration. Record the operating number here regardless of which case
applies, so the doctrine does not depend on which lever happened to be available.

### The adopted session floor, and the rule that derives it

The adopted session floor is **272000** tokens.

**The derivation rule matters more than the number, because the number expires when the model
set changes.** The floor is the *smallest real window among the models the operator actually
selects*. It was derived for a selected set of the 5.6 family, Claude 5, and muse 1.2, whose
smallest real window is the 5.6 family's provider-served 272000. Adding a smaller model to that
set obliges lowering the floor: a reader who adds a 100000-token model must lower it, not
inherit 272000. Re-derive on any change to the selected set.

The lower number was chosen over the gateway's compiled 372000 deliberately. At 372000 the
compaction net sits **behind** the model's real ceiling, so the failure mode becomes
provider-side truncation instead of a clean local compaction. 272000 sits inside the real limit
for both the 5.6 family and `gpt-5.5`, and because the client applies `min(believed window,
env)`, a smaller model such as `gpt-5.3-codex-spark` stays accounted at its own 100000 rather
than being pulled up to the floor.

**The default has moved away from the floor, so the floor must be set explicitly.** opencodex
`2.28.0` raises `AUTO_COMPACT_WINDOW_DEFAULT` to **829800** (it was 350000 through `2.11.1`). An
unset compact window therefore now sits far behind every window in the selected set — the exact
truncation-instead-of-compaction failure the 272000 choice exists to avoid — and it also drops the
injected-slot extended-context mark from any sub-1M route, because marking a window below the
compact window is what the predicate refuses. Read on this host 2026-08-20 with a read-only
`ocx config show --json`: `claudeCode.autoCompactWindow` **is** explicitly `272000`, so the
adopted floor is applied here rather than merely documented, and `autoContext` is absent
(default-on). Treat an absent explicit value on any other host as 829800, not as 272000.

**This floor under-uses `gpt-5.4` and the muse models by design.** Both carry roughly 1M, so a
272000 floor leaves most of their window unreachable. That is the accepted cost of one process-
wide value serving a mixed set, not an oversight. The pressure valve is the deliberate
single-model opt-in: a session that will genuinely stay on one large model may raise the value
to that model's own window, accepting that mid-size models go unmarked for the duration. Raising
it as a global default is the error the floor exists to prevent.

The proactive-compaction percentage is **85** as an opinionated default (amended 2026-08-08;
was deliberately left unset pending measurement). It is one-directional — it can only compact
earlier, and a value above the (undocumented) default is silently ignored — so 85 is safe before
measurement: if 85 > default it is a no-op, if 85 < default it compacts at
~0.85×272000≈231200 (`assets/claude/session-inheritance.sh`, which `scripts/muse-claude.sh`
sources, and `scripts/opencodex-claude.sh` directly, export
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85` only when the operator has not already set it). An installer
overrides it per environment with `export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=<1-100>` before
`ccodex launch` — that value wins, because each launcher sets 85 only when the variable is unset.
(`ccodex` sets it directly: ADR-0014 removed the environment scrub it used to be
capture-then-restored across. `scripts/muse-claude.sh` still scrubs and restores, through the
shared helper rather than a private copy since 2026-08-18.) The measurement
procedure that would settle the true default remains recorded in the research memo cited below;
until run, 85 is an opinionated safety margin rather than a settled measurement, and must not
be read as a verified optimum.

### Output budget interacts with the window, and on a shared pool the trade is exact

The client defaults its maximum output tokens to **32000 for model IDs it does not recognize**,
which includes every gateway-served name here, and its own documentation states that raising
that value **reduces the context available before auto-compaction triggers**. So output budget
and input capacity are not independent settings even on a separate-reservation model.

On a shared-pool model the trade is not approximate but arithmetic: input and output draw on one
1048576-token budget, so a long conversation mechanically starves the output allowance. This is
the measured cause of the first shared-pool probe returning empty output with an incomplete
status — the budget was consumed by reasoning tokens before any visible text. For a
shared-pool-heavy session, set the output ceiling explicitly rather than accepting the 32000
default: high enough to clear the observed reasoning floor of roughly 600 tokens plus the task's
expected output, and low enough that it does not eat the input capacity the task needs. Never
raise it toward the window's size on a shared pool; that starves input directly.

### Recording a window the gateway does not know

Four served models have no gateway-computed window: `gpt-5.4-mini` and all three muse entries.
For a routed provider the gateway is still the right home for the fact, through the provider's
per-model window map. The recorded form for the muse provider is:

```json
"modelContextWindows": {
  "muse-spark-1.2": 1048576,
  "muse-spark-1.1": 1048576,
  "muse-spark-1.2-contributor": 1048576
}
```

Two conditions. The value must be the measured 1048576 and not a rounded 1000000, because the
rounded figure is both wrong and changes whether the extended-context marking predicate fires.
And because the pool is shared, recording the window without also setting the output ceiling
reintroduces the starvation hazard above.

This was recorded as a documented step rather than an applied one, and on this host that has
changed: read 2026-08-20 with a read-only `ocx config show --json`, the `muse` provider block
carries exactly this map, all three entries at 1048576. Two things follow. Applying it anywhere
else is still a deliberate mutation requiring the operator's own authorization — one host's
configuration is not a default. And the second condition above is live rather than hypothetical
here: the map is set, so the output ceiling has to be set alongside it or the shared-pool
starvation hazard is a present risk, not a future one.

### Requested context form is a request, never proof of the served window

`requested_context_form` in a `RuntimeAssignment` is a **request**, exactly as
`requested_model_id` and `requested_effort` are. It never proves the served window. This is
the same requested-versus-readback boundary recorded above for effort, applied to context, and
the evidence for it is specific rather than formal:

- extended-context request forms read back the base model ID and prove nothing about the
  upstream window;
- the gateway's own computed window for one model family disagrees with the provider's current
  catalog, so even the gateway's number is a belief;
- four served models have no known window at all; and
- the discovery catalog returns a null window for nearly every entry, so discovery supplies no
  window fact either.

Record `context_readback_status: unavailable` unless transport telemetry independently exposes
effective context behavior, and never copy a requested form into a resolved or readback field.
Reclassify only on independently observed effective context behavior.

Executed evidence and the full probe record:
`docs/research/2026-08-07-context-window-accommodation.md`; the measured shared-pool window is
`docs/research/2026-08-07-muse-spark-qualification.md` §5.8 with the starvation hazard at §6.1.
The decision is `docs/adr/0012-context-window-accommodation.md`. None of these authorizes a
route, a configuration mutation, or any other outward effect.

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

## Route evidence layer: status ladder, observation state, and required fields

The four-tier blast-radius doctrine in `SKILL.md` governs which semantic lane a task
belongs to. Underneath it, every individual route needs its own evidence record, because
"the model is available" is not a fact a single boolean can carry — a route is
provider+lane+wire-format+auth+region+id+thinking-level, and each field can fail
independently. Keep three separate concepts on every route record, never collapsed into one:

1. **A deployment/selection status ladder.** One worked account's ladder ran, from weakest
   to strongest: `blocked` < `quarantined` < `catalog_only` < `direct_text` < `pilot` <
   `qualified`. Deployment status controls whether a route may be selected at all; it is
   evaluated before the four-tier semantic doctrine ever applies. Re-derive your own rung
   set and ordering for your own transport — the load-bearing property is that status is an
   ordered ladder with selection consequences, not the specific rung names.
2. **An observation-state taxonomy, scoped to the exact probe tuple.** This field describes
   only what happened on the one probe actually run — never the whole route, never the whole
   model. One worked catalog recorded: `catalog_only`, `direct_text`, `http_200_empty_text`,
   `legacy_access_denied`, `not_yet_captured`, `pilot`, `route_denied`, and
   `transport_timeout_indeterminate`. An observation state never generalizes past the exact
   account, region, path, and effort tuple it was captured on.
3. **A required-field route contract.** A route record is never reducible to a bare model ID.
   At minimum, carry: the exact route/alias ID, the upstream model ID, surface/lane, wire/API
   family, region, path, deployment status, observation state, whether the route is required
   for startup, whether it is selector-eligible, the minimum status a caller may accept it at,
   the evidence class backing the route claim itself, the evidence class(es) backing any
   capability claim made about it, and named limitations. Forbid a single
   model-wide-availability boolean outright: it hides exactly the account/region/path
   divergence this contract exists to preserve.

Grade every capability claim about a route by how it was obtained, independent of the route's
own deployment status, using six evidence classes strongest to weakest: `exact-route-live`
(the exact alias, upstream, region, API family, path, and client build were exercised);
`exact-model-direct` (the exact upstream was probed directly, but not through the target
tool-loop); `exact-model-benchmark` (a benchmark row names the exact model, but not
necessarily this route or harness); `family-transfer-hypothesis` (a related model nominates a
test only); `vendor-hypothesis` (a vendor claim or model card nominates a test only); and
`catalog-observation` (the exact ID was listed for a captured account/region; invocation is
unproved). A class is never upgraded by repetition — a hundred `vendor-hypothesis` citations
remain `vendor-hypothesis`.

This is a **worked example from one Bedrock/Mantle-lane account**, retained to show the shape
of a real schema; the rung names, observation-state vocabulary, and field list are not a
universal standard. Re-derive your own status ladder, observation-state taxonomy, and
required-field contract for your own transport rather than copying these labels verbatim.

### Gateway routes: catalog membership and log-sourced identity

A route that passes through a gateway carries two extra required fields, both enforced in
`scripts/receipt_admission.py` rather than documented as advice. They come from an executed
qualification canary (`docs/research/2026-08-07-opencodex-qualification-canary.md`, conditions
C1 and C2) against one live gateway deployment, and each replaces a rule that looked safe and
was not.

**Version attribution, because the pin moved from `2.11.1` to `2.28.0`.** Both rules were measured
against a live `2.11.1` gateway on 2026-08-07. A 2026-08-19 diff of the published `2.28.0` tarball
against `2.11.1` re-verified the machine surface they read, so the FIELDS and the alarm are current:
`ocx observe logs --jsonl` still emits the same per-request fields (`requestId`, `requestedModel`,
`resolvedModel`, `provider`, `status`, `routeDecision.selected`), `routeKind` still carries the same
union including `default-provider`, the served `GET /v1/models` catalog keeps its shape, and the
exit codes the wrapper branches on are unchanged. What the diff could NOT verify is any behavior
that requires a live gateway to observe — the response body's alias echo and model relabel, the
dated-snapshot suppression, and effective-context behavior — because the live gateway on this host
was still serving `2.11.1` when the diff was read; the restart that would move it is an explicit
operator step, not part of a pin bump. Those remain `2.11.1` observations, and the `2.28.0`
qualification canary is what re-measures them. Do not restate one as current merely because the
pin advanced.

1. **Catalog membership, not a provider-prefix convention.** The canary requested
   `anthropic/claude-opus-5` and bare `claude-opus-5` and got *identical* behavior: neither was
   refused by the router. Both were classified `routeKind: "default-provider"` and forwarded
   verbatim to the configured default provider, where the upstream rejected them. The
   fail-closed outcome was the upstream's property, not the gateway's, and it holds only while
   that provider happens to refuse unknown names. A prefix therefore discriminates nothing. What
   does discriminate is presence in the gateway's own served `GET /v1/models` catalog, so the
   receipt records the catalog bytes, their digest, and a pointer to the dispatched exact ID
   inside them. Treat `routeKind: "default-provider"` in a gateway's attribution log as an alarm:
   it means the router did not recognize the target.
2. **Identity from the attribution log, never the response body.** The canary requested a
   `claude-`-prefixed roster alias; the response body echoed that alias back while the attribution
   log recorded the OpenAI model that actually served it, and the log never recorded the inbound
   alias at all. The body also suppressed a dated snapshot the log carried (`gpt-5.4-mini` in the
   body against `gpt-5.4-mini-2026-03-17` in the log), and no provider/model response header
   exists on that surface. A client reading only the body would record a false model identity. So
   `resolved_model_id` evidence for a gateway route is sourced only from the attribution record's
   resolved-model field, correlated by request ID, and bound through a pointer — that record names
   the requested model beside the resolved one, and position is the only thing separating them.

Both are gateway-route facts. A direct-adapter route records adapter-sourced identity and neither
field. And per the same canary, effective effort readback on that gateway was honestly
unavailable: a `requestedEffort` the gateway derived from a thinking budget is evidence about the
request, never readback of what the upstream did.

### Muse Spark (Meta) — two routes, one model family

A third model family is admitted alongside Codex-OAuth-via-gateway and Bedrock: Meta's Muse
Spark. It is reachable on **two** routes with **different evidence properties**, and a
`RuntimeAssignment` must record which one was used, because the identity rules differ:

1. **Via the opencodex gateway — the SHIPPED route.** Muse registered as an ordinary provider
   (`ocx provider add muse --adapter openai-responses --base-url https://api.meta.ai/v1
   --default-model muse-spark-1.2`), reached through the existing gateway and launcher.
   Conditions **G1–G7**, plus the canary's C1–C8 which it inherits. Muse is a **provider, not a
   plane**: verified 2026-08-07, the running gateway serves one flat catalog in which its models
   appear as namespaced ids (`muse/muse-spark-1.1`, `muse/muse-spark-1.2`,
   `muse/muse-spark-1.2-contributor`) alongside seven `gpt-*` ids, so a session selects one
   per-request or through the `/model` picker. `ccodex models` prints that live catalog.
2. **Directly, with no gateway — a DOCUMENTED RECIPE, no longer a shipped command.**
   `ANTHROPIC_BASE_URL` pointed at `https://api.meta.ai`. Conditions **M1–M8** still describe it,
   and the recipe still works, but the standalone launcher and its `muse:*` tasks were retired as
   a command surface (ADR-0007 Amendment 2026-08-07). A `RuntimeAssignment` recording this route
   is recording an operator-assembled environment, not a bundle entry point.

Evidence is the executed qualification in
`docs/research/2026-08-07-muse-spark-qualification.md` — §1–§7 for the direct route (verdict
QUALIFIED WITH CONDITIONS, M1–M8) and §8 for the gateway route (QUALIFIED WITH CONDITIONS,
G1–G7) — and the decision record `docs/adr/0007-muse-spark-direct-route.md` (whose filename
predates the two-route decision; its title and Decision are authoritative).

**Why the gateway route is primary.** It has a per-request attribution channel that is observed
**independently of the request string**, and its independence is *proved* rather than assumed
(the body-echo divergence below is a `2.11.1` observation — see the version attribution above):
for `muse/muse-spark-1.2` the response body echoes `muse/muse-spark-1.2` while the log records
`resolvedModel: muse-spark-1.2`. Because a second channel disagrees with the body, the log is
demonstrably not a replay of the request — the same alias-echo divergence the canary found. The
direct route has one channel and it agrees with itself, which distinguishes nothing. So the
gateway route can satisfy canary **C2**; the direct route structurally cannot, and no wrapper
can change that because there is no second channel to read. Prefer the gateway route unless a
gateway process is unwanted or unavailable.

**Base URLs are OPPOSITE on the two routes, and getting it wrong looks like a bad credential.**
The direct route uses `https://api.meta.ai` **without** a `/v1` suffix, because an
Anthropic-shaped client appends `/v1/messages` itself and the doubled path answers **401**, not
404. The gateway provider's `baseUrl` **keeps** the `/v1`, because the `openai-responses` adapter
appends only `/responses`. Copying either form into the other yields a 401 *with a fully valid
credential*, so misconfiguration presents as a key problem on both. This is M5 for the direct
route and **G5 inverts it** for the gateway route.

**Exact IDs, admission, and auth.** The three IDs served on 2026-08-07 were
`muse-spark-1.2-contributor`, `muse-spark-1.2`, and `muse-spark-1.1`. On the **direct** route,
catalog membership in `GET /v1/models` is the admission check, and every non-catalog ID — a
bogus version, a `claude-*` ID, a `meta/`-prefixed form, even a case-variant of a real ID — was
refused **404 `model_not_found`** by the provider itself. There is no default-provider
fallthrough to alarm on there, because there is no second router.

On the **gateway** route that guarantee is weaker in a specific and load-bearing way, and it is
condition **G2**: only the provider's *configured default model* resolves when requested bare.
A `muse/`-prefixed unknown ID is refused 404, but `muse-spark-1.1` — a **real, served ID** —
requested *without* the prefix is classified `routeKind: "default-provider"` and routed to
**Codex**, which refuses it with a message about ChatGPT accounts. So **every dispatch on the
gateway route carries the `muse/` prefix**: prefix *and* catalog membership, not either alone.
A bare ID is not a stylistic choice there; it is a wrong-provider dispatch.

**G1 — a configured provider is not a live provider, and the gap fails OPEN.** `ocx provider
add` writes the config file only. Until `ocx sync` **and** a gateway restart have both run, a
request naming the new provider's model is attempted and billed against the **default**
provider while the attribution log names the wrong provider. This is the canary's C1/C5
fail-open reached through a routine *successful* configuration command rather than through a
typo, so `routeKind: "default-provider"` on a Muse-intended request is an alarm (**G4**) meaning
either this window or a bare ID. Liveness is checkable because the two facts have separate
sources: `ocx provider list` reads the config file, while the running gateway's own
`GET /v1/models` reads the process catalog. `scripts/opencodex-claude.sh status` performs that
comparison and reports **NOT-LIVE** for any configured-but-unserved provider; `configure` prints
the required sequence after a successful mutation. Confirm liveness before dispatching —
`provider add` succeeding is not evidence of it. By opencodex `2.28.0` (absent in `2.11.1`) the sync half can be
**catalog-only**: with the Codex integration off, or an external `model_provider` owning
`config.toml`, it reports a `CodexSyncResult` status of `catalog-only` and leaves `config.toml`,
the journal, and history untouched (the catalog and models-cache files under `~/.codex` may
still refresh). That changes the blast radius of the sync, not G1 — the restart is still required, the
window still fails open, and a sync that WOULD rewrite `~/.codex` still needs its own explicit
approval. Note too that the wrapper admits a not-yet-configured provider by NAME against the
registry roster it pins, so a name it has never heard of is refused rather than admitted by
absence; `2.28.0` added `chutes`, `featherless`, `nous`, `novita`, and `xiaomi-mimo` to that
roster. Related caveats: `ocx provider test` reads
liveness rather than configuration (a failure means "not live", not "not configured"), and
`provider add` performs **no adapter validation**, so a mistyped adapter is stored silently and
must be verified against a live request (**G7**).

Auth on both routes is Meta's **own** API key, accepted as either `Authorization: Bearer` or
`x-api-key`; the gateway's `openai-responses` adapter already sends bearer, so
`--api-key-transport bearer` is rejected as anthropic-adapter-only and is unnecessary. A Claude
subscription credential is never involved on either route; per ADR-0003 item 2 both are the
supported shape, because what matters is whose credential authenticates rather than whether a
proxy is present. Pointing a client's base URL here while a subscription credential is in scope
is the prohibited shape, on either route. Note that the gateway route inherits canary **C8**:
anything reaching the loopback port can spend the Meta key without presenting a credential.

**Three surfaces, with different capabilities.** All three were exercised live:

| Surface | Status | Effort channel | Identity field |
|---|---|---|---|
| `POST /v1/responses` | primary; reasoning + message blocks | `reasoning.effort` | `model`, plus a retrievable stored record |
| `POST /v1/messages` | Anthropic-shaped; `redacted_thinking` + text, tool_use, SSE | `thinking.budget_tokens` (≥1024, and must be **less than** `max_tokens`) | `model` only |
| `POST /v1/chat/completions` | OpenAI-shaped; reasoning billed but not exposed | not accepted | `model` only |

`reasoning` is rejected as an unknown parameter on `/v1/messages`; `thinking` is rejected on
`/v1/responses`. The effort vocabulary the provider itself enumerated in a 400 is `none`,
`minimal`, `low`, `medium`, `high`, `xhigh` — **no `max`**, and `none` is refused for these
models even though it is in the enumeration. `xhigh` is the top usable band here, so a lane whose
calibrated band above is `max` cannot be expressed on this route and must either drop to `xhigh`
deliberately or stay off it.

**HAZARD — reasoning tokens are charged against the output budget, and starvation returns HTTP
200 with empty output.** Executed on `/v1/responses` with a trivial prompt at
`reasoning.effort: low`:

| `max_output_tokens` | HTTP | `status` | `reasoning_tokens` | visible text |
|---:|---:|---|---:|---|
| 32 | 200 | `incomplete` | 29 | **none — empty `output` array** |
| 128 | 200 | `incomplete` | 125 | **none — empty `output` array** |
| 600 | 200 | `completed` | 210 | `budget` |

The same starvation reproduces on `/v1/messages` (`max_tokens: 32` → `stop_reason: max_tokens`,
`thinking_tokens: 29`, empty `content` array). Two consequences. First, **a liveness or health
check that asserts only HTTP 200 is worthless on this route** — it passes against a route that
cannot emit text at all; assert non-empty text. Second, budget guidance must cover reasoning:
observed reasoning consumption on trivial prompts ranged 48–499 tokens across efforts and models,
so a budget under roughly 600 risks an empty completion even for a one-word answer, and the
`incomplete`/`max_tokens` signal is the only distinguishing evidence. Reasoning content itself is
never readable — `/v1/responses` returns a reasoning block with an empty `summary`,
`/v1/messages` returns `redacted_thinking`, and the SSE stream omits the thinking block entirely
while still billing for it.

**Context window: 1,048,576 tokens, and it is a SHARED input+output budget — measured, not
assumed.** The vendor claim is checkable cheaply because rejections cost nothing. With a trivial
input, the largest accepted `max_output_tokens` was 1048407 and 1048463 was refused 400; with a
9765-token input (per `count_tokens`), the boundary moved to exactly 1038811 — and
`9765 + 1038811 = 1048576 = 2^20` with zero remainder. Confirmed as an oracle: for a given input,
`max_output_tokens = 1048576 − count_tokens` is accepted and one more is refused. So the window is
exactly 2^20 and input and output draw on **one** budget; a caller cannot request a large output
and a large input. What remains a **vendor claim not measured** is whether quality holds across a
filled window — only the admission arithmetic was measured, never a large request. Above the
window the failure mode changes: an absurd budget returns **429** (`rate_limit_exceeded`,
"reserved capacity"), not 400, so an oversized request can read as throttling rather than as the
size error it is.

**Identity on the DIRECT route: the response body's `model` field is the ONLY channel, and this
is weaker than the gateway route.** (For the gateway route, identity comes from the attribution
log per G3 — see the two-route comparison at the end of this subsection.)
No provider/model response header exists; there is no attribution log; there is
no usage or audit surface (`/v1/usage`, `/v1/organization/usage`, `/v1/audit_logs`, `/v1/logs` all
404). `GET /v1/responses/<id>` does return a server-side record, but only for `/v1/responses` with
`store: true` (default), never for `/v1/messages`, and it reports the same `model` string from the
same vendor — a second read of one assertion, not an independent channel. Compare the two routes
honestly:

- The **gateway** route has a genuinely independent channel: `resolvedModel` in the attribution
  log, recorded separately from the caller's requested string, which is what caught the alias echo
  and the dated-snapshot suppression. Its response body is *inadmissible* precisely because the log
  disagreed with it.
- The **Muse Spark** route has no such channel, so `model_identity_basis` cannot rest on
  independent observation. What is available is weaker in kind, not merely in quantity: the body's
  `model` is an **echo of the request**. A mismatch is real evidence of failure, and none was ever
  observed across every probe; a match is consistent with a truthful report and with a server that
  echoes without checking, and these probes cannot separate those. The load-bearing mitigation is
  that fabrication has no route to succeed here: a non-catalog ID is refused 404 rather than
  silently substituted, so there is no observed path by which a request for one catalog ID is
  served by a different model while reporting the requested one. That is an argument from the
  absence of a substitution mechanism, not a positive identity observation, and it should be
  recorded as such rather than upgraded.

Consequently a `RuntimeAssignment` on the **direct** route records `adapter_response_readback` as
its `observed_identity_source` and carries **neither** gateway field (`gateway_attribution_log`,
`catalog_bytes` pointers are gateway-route fields). On the **gateway** route the opposite holds
and it is condition **G3**, which **supersedes M2** there: `resolved_model_id` comes **only** from
the attribution log's `resolvedModel` correlated by `requestId`, the response body is
**inadmissible** because it echoes the caller's `muse/`-prefixed alias, `observed_identity_source`
is the gateway attribution log, and the gateway fields do apply. The receipt must record which
route was used; the two rules must never be averaged or substituted for each other.

Effort readback is **honestly unavailable** on both routes:
`/v1/responses` echoes the requested `reasoning.effort` back verbatim in the response — never
record that as readback, it is the requested value returning. The one genuinely
non-request-derived effort signal is the *model default* observable when effort is **omitted**:
all three models reported `high`. `usage.output_tokens_details.reasoning_tokens` is real observed
telemetry about consumption, but it is not an effort value in the policy vocabulary and does not
satisfy effort readback.

**Tier placement: ADMITTED AS ROUTES, TIER-UNPROVEN — on BOTH routes, unchanged by the second
one.** These probes were trivial smoke prompts — one-word answers, a two-city tool call — on the
direct route and again through the gateway. They establish transport, admission, fail-closed
behavior, surface shape, and the budget arithmetic. They establish **nothing** about task fit, and
capability tiering from a handful of smoke probes is exactly the weak evidence this calibration
refuses to promote. **Adding a second transport to the same models cannot raise a rung**: a
smoke probe proves a route carries bytes, never that a model fits a role, so two route-probed
transports are two route-probed transports and not a promotion.

Under the qualification ladder above, each route sits at **`route-probed`** — a live call on
the exact tuple returned a real response — and **not** at `role-qualified` in any role. Under the
evidence-class ladder, the capability claims a reader might want (agentic/coding strength, 1M-context
usefulness) rest on `vendor-hypothesis`; only transport and admission are `exact-route-live`. Per the
three provenance classes, documented positioning is `mined` at best, which may *propose* a routing
reconsideration and can never raise a rung or fill a scale-setter slot. Therefore:

- **No tier assignment is recorded for `muse-spark-1.2-contributor` or `muse-spark-1.2`, on
  either route.** They are not added to any eligible pair, and no phase, blast-radius, or
  roadmap row above is changed. The six-primary pair policy is untouched.
- Either route may be selected only for work whose failure is caught by a **complete
  deterministic check** — the mechanical-floor control predicate — and even then as an explicitly
  recorded experiment, not as a pair member. Both are ineligible for frontier or
  judgment-workhorse work: a frontier slot requires a locally observed `role-qualified` route,
  and `xhigh` is the ceiling.
- Promotion requires the A0–A6 ladder with paired isolation and utility arms, starting at A0
  (which these probes satisfy) and a real task-fit comparison against an incumbent pair member on
  representative work. A single passing run is a toy pass.
- `muse-spark-1.1` is catalog-present and probe-answering; it is recorded as the small/fast slot
  for the launcher only, with no tier claim at all.

**Quota, from response headers rather than a vendor page.** The two tiers expose different
limits, which is the sharpest observed difference between them: `muse-spark-1.2-contributor`
returned `x-ratelimit-limit-requests: 100` with `x-ratelimit-limit-tokens: 3000000`, while
`muse-spark-1.2` and `muse-spark-1.1` returned `3000` and `4000000`. Account-, date-, and
key-specific; re-read the headers before sizing any fan-out. The 100-request contributor ceiling
is low enough to exhaust in one wave, so the contributor tier is unsuitable for fan-out
regardless of capability.

**Choosing between the two routes.** Neither dominates; the properties differ in kind, so this
is the comparison to consult before recording a `RuntimeAssignment`:

| | Gateway (PRIMARY) | Direct (FALLBACK) |
|---|---|---|
| Independent per-request attribution | **yes** — log `resolvedModel`, proved independent by disagreeing with the body | **none** — body echoes the request |
| Canary C2 satisfiable | **yes** | no |
| `observed_identity_source` | gateway attribution log (G3) | `adapter_response_readback` (M2) |
| Non-catalog ID fails closed | prefixed yes (404); **bare falls through to default** | **yes, uniformly** — 404 at the provider |
| Valid non-default ID requested bare | **routed to the wrong provider** | resolves |
| Dispatch form | **`muse/`-prefixed, always** (G2) | bare catalog ID, whole-match (M1) |
| Base URL | `https://api.meta.ai/v1` (**with** `/v1`) | `https://api.meta.ai` (**no** `/v1`) |
| Running process | supervised gateway on a loopback port | none |
| Configuration sequencing hazard | **yes** — sync + restart, fail-open window (G1) | none |
| Shared-config side effect | `ocx sync`/`ensure` rewrite `~/.codex` | none |
| Loopback exposure | **yes** — canary C8 applies | none |
| Cost accounting | gateway reports `price_unmatched`; use billed `input_tokens` | billed `input_tokens` |
| Effort readback | unavailable (`reasoningOutputTokens` is consumption) | unavailable (echo is a trap) |

Prefer the **gateway** route. Its two hazards are mechanically checkable and are checked — the
`NOT-LIVE` status comparison catches G1, the prefix rule catches G2 — whereas the direct route's
missing identity channel cannot be repaired by any wrapper. Since this bundle's whole
`RuntimeAssignment` discipline turns on observed model identity, a route that can satisfy C2 is
worth more than one that structurally cannot, once its hazards are guarded. Use the **direct**
route when no gateway is wanted or the gateway is unavailable, and record its identity ceiling
rather than papering over it.

## Three provenance classes and qualification rungs

A routing *decision* (as opposed to a single capability claim, above) draws on three
provenance classes that must never be merged or averaged into one score:

- **`declared`** — the operator's own stated preference about a route (for example, "prefer
  this route for scale-setter work"). Hand-authored; never written by automation; can never
  by itself raise a route's qualification rung.
- **`mined`** — a benchmark-leaderboard or published-signal view of the wider world. It may
  *propose* that a routing table be reconsidered. It can never raise a route's qualification
  rung, and it can never place a route into a scale-setter (frontier) slot.
- **`observed`** — this account's or host's own measured result from actually invoking the
  route. The only class that may promote a qualification rung, and the only class usable as
  evidence toward a scale-setter assignment.

Reading the three together is a **precedence, not an average**: `observed > declared >
mined`. Averaging would let a published benchmark table outvote a locally measured
gate-failure rate — exactly backwards, and it is how a benchmark ranking quietly becomes
production policy through an averaging step nobody meant to authorize.

A route's qualification state advances through exactly three rungs, independent of the
deployment-status ladder above:

1. **`catalog-only`** — the exact ID appears in a model/route catalog for the account or
   region. No live call has been made.
2. **`route-probed`** — one live call was made on the exact route tuple and returned a real
   response. **A benchmark score is not a live call** and cannot substitute for this rung.
3. **`role-qualified`** — the route has accumulated a minimum number of accepted,
   schema-conformant assignments in the specific role being asked of it. Only a
   measurement/meter process may write this rung; a mined or declared signal may propose
   movement toward it, never grant it.

A route whose lane has never been probed cannot reach `route-probed`, and therefore can never
be selectable for real dispatch, regardless of how strong its catalog or mined evidence
looks. Mining may offer a reordering proposal only among routes already at `route-probed` or
above — it can never manufacture eligibility for a `catalog-only` route. **A benchmark score
never fills a scale-setter slot**: only a locally observed, role-qualified route may occupy
one, per the Frontier-tier doctrine in `SKILL.md`.

### Bounded local evaluator (2026-08-12 amendment)

`/sdlc-rightsize` now delegates deterministic discovery, normalization, measurement, and rendering
to `scripts/rightsize.py`. This is a measurement surface, not a worker launcher. It accepts two
current route kinds:

- `gateway-routed-provider`: an exact live OCX catalog ID with provider-owned auth and billing;
- `gateway-claude-subscription-passthrough`: an exact non-alias Claude ID carried through the same
  loopback gateway using the operator's existing `claude.ai` login.

The older `gateway | native-bedrock` `provider_plane` abstraction is retired from the generated
map. It incorrectly merged auth, billing, discovery source, effort vocabulary, and identity
strength. Every route now records transport, route kind, provider, auth basis, billing basis,
exact model ID, requested effort, and requested context form. A configured provider is not a live
provider; a registry provider is neither. Claude passthrough is deliberately absent from the OCX
provider catalog and uses the checked-in exact-ID set plus `anthropic-native` attribution. Its
requested effort may be admitted by a checked-in exact tuple, but no route-specific effort
vocabulary is called observed unless the transport reports one.

A live evaluation has two phases. `plan` canonicalizes `rightsize-run-spec/v1` and emits an
authorization digest over target identity, raw catalog, selected routes, task pack, benchmark
snapshot, attempts, budgets, egress class, output, and stop conditions. Only a separate explicit
approval permits `evaluate` with that exact digest. A changed input invalidates approval. The
evaluator never changes provider/gateway configuration, trust, global settings, queues, or the
real target and never dispatches an agent role.

The bundled `harness-smoke-v1` pack is a pilot and cannot promote. A qualification pack must be
explicitly target-representative, bind immutable or hidden expected results, provide at least five
distinct held-out tasks per selected class, and run at least three attempts per task. Promotion
requires all of:

- accepted rate at least `0.90`;
- two-sided 95% Wilson lower bound at least `0.70`;
- zero transport or identity failures;
- zero failures on tasks marked critical;
- the normal gate/independent-control predicate for the class.

Every `authority_or_frontier` task is critical. These are minimum admission observations, not a
universal sample-size sufficiency claim; high-variance work should require more tasks. A newly
role-qualified route is still production-blocked until `runtime-assignment-receipt-v1.json`
admits the exact model/effort/context tuple. Evaluation never rewrites that policy.

For each task class, context and semantic controls are hard filters. A measured Pareto front
compares compatible local pilot or qualification evidence; a separately named dispatch front then
hard-filters for task-class `role-qualified` evidence and checked-in runtime admission. A measured
primary may remain explicitly non-dispatchable. Among survivors, Pareto comparison maximizes the
local success lower bound and minimizes route/identity failure plus the selected cost, token/quota,
or wall-time measure. Missing data makes candidates incomparable on that dimension; it is never
zero. Preserve mean and median separately, and compute observed per-accepted economics only from
compatible local attempts:

```text
sum(observed attempt cost|tokens|wall time) / accepted successes
```

The value is unavailable when accepted successes are zero. Subscription marginal cost is `null`,
not `$0`; API-equivalent cost, quota consumption, and possible usage credits are separate facts.
Published benchmark data in `model-benchmark-evidence-2026-08-12.json` remains `mined` and may
order which candidate to measure first. It never enters local metrics or promotes a rung.

Context admission uses expected peak input plus task output reserve and a 10% safety margin. Select
the smallest certified exact form that fits. Keep `requested_model_id` and
`requested_context_form` separate even when Markdown renders `[1m]` as a suffix. A provider's
native million-token base form and Muse's 1,048,576-token shared pool remain `base`; a `[1m]`
request requires an exact certified tuple and never proves served capacity or compaction.

Regenerate the v2 trio when target identity, route catalog, effort/context metadata, task pack,
benchmark snapshot, price provenance, evaluator/policy revision, or local measurements change.
Failed evaluation does not replace a prior map. A complete valid trio may regenerate; partial,
v1, stale-digest, or user-edited output requires `--regenerate --force`, which still cannot
bypass failed route evidence.

## Promotion ladder for a topology or role-substitution change (A0–A6)

Before promoting a change to how models are assigned across roles — adding a new pair
member, letting one role substitute a different model, or moving from a single controller to
a parallel or heterogeneous topology — climb this ladder one rung at a time and re-certify at
each rung rather than jumping straight to the target topology:

| Rung | What is under test |
|---|---|
| A0 | Direct-model sanity floor: does the candidate route answer at all |
| A1 | A matched strong single controller, no topology change yet |
| A2 | The proposed roles executed serially by that same single controller |
| A3 | Isolated contexts per role, still serial and homogeneous |
| A4 | Parallel independent branches, still homogeneous |
| A5 | One heterogeneous role substitution at a time |
| A6 | Independent review against an oracle-only control |

For every rung after A1, run two paired arms, never one:

- an **isolation arm** that holds inputs, model, tools, oracle, retries, and total budget
  fixed, so the rung's own effect is measured in isolation; and
- a **utility arm** that lets the full topology run normally, charging it for orchestration,
  integration, recovery, and human-review time it would actually incur.

Promote the least-complex rung whose held-out lower-confidence-bound effect clears a minimum
useful threshold, or whose quality is non-inferior while cost or latency improves materially.
A single passing run at any rung is a toy pass, not a promotion — it needs the same
repeatability and no-authority-regression bar as any other production-band change under
"Rerun triggers" below.

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
| Frame | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory frame; choose Fable only as the certified bounded adversarial assumptions packet. | Sol `high`; `xhigh` at trust or authority boundaries; Fable `max` bounded packet | The non-selected member re-derives or attacks multiplier assumptions. | Re-derive; conductor adjudicates the recommendation. |
| Discover | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for dense mapping; choose Opus when an immutable semantic candidate needs independent review. | Terra `xhigh`; Opus `high`, `xhigh` | The non-selected member checks citations and omissions. | Partitioned scope and evidence inventory. |
| Research | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for synthesis; choose Opus for a certified semantic review of the evidence packet. | Terra `xhigh`, `max`; Opus `high`, `xhigh` | Luna/Sonnet can extract; Sol analyzes load-bearing unknowns. | Conductor adjudicates unknown disposition. |
| Plan | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for the advisory plan; choose Fable only to attack certified bounded multiplier assumptions. | Sol `xhigh`; Fable `max` bounded packet | The non-selected member returns the plan or counterexample artifact. | Advisory plan; conductor alone mutates Seeds. |
| Act, contained | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to implement interacting constraints; choose Opus to review immutable candidate decisions. | Terra `xhigh`; `max` for interacting constraints; Opus `high`, `xhigh` | The non-selected member produces candidate or review. | Exact `[1m]` is mandatory only in OCX Ultracode Workflow mode. |
| Act, deterministic-gated | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the member with verified transport and independent evidence when the deterministic gate remains complete. | `high`, `xhigh` | The non-selected member checks stable evidence. | Exact `[1m]` is mandatory only in OCX Ultracode Workflow mode; same deterministic gate. |
| Review, semantic | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Opus for semantic review; choose Terra to reproduce and classify an immutable candidate. | Opus `high`, `xhigh`; Terra `xhigh`, `max` | The non-selected member supplies review or reproduction. | Immutable candidate and acceptance criteria. |
| Review, trust or authority | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for authority analysis; choose Fable only to search a certified bounded counterexample packet. | Sol `xhigh`; Fable `max` bounded packet | The non-selected member supplies authority analysis or counterexamples. | Advisory analysis; conductor adjudicates. |
| Reconcile | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to reconcile semantic evidence; choose Opus to review the immutable reconciliation candidate. | Terra `xhigh`; Opus `high`, `xhigh` | Sonnet validates evidence links. | Conductor alone records Seeds mutations. |
| Integrate | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to integrate; choose Opus to review fan-in semantics after the integration head is immutable. | Terra `max`; Opus `high`, `xhigh` | Luna re-runs gates; the non-selected judgment member reviews or integrates. | Authorized integrator only; re-gate on integration head. |
| Ship recommendation | `gpt-5.6-sol` or `claude-fable-5` | Choose Sol for promotion analysis; choose Fable only as a certified bounded adversarial receipt packet. | Sol `xhigh`; Fable `xhigh`, `max` bounded packet | Luna/Sonnet validate receipts. | Human separately authorizes outward action. |

The context column describes non-Ultracode route selection. For an OCX Ultracode Workflow,
every explicit `agent()` `model` argument instead carries the exact `[1m]` form and dispatch
stops if that marked tuple is not certified, admitted, and readable; no phase row permits an
unsuffixed fallback.

## Approved roadmap family lanes

Each complement produces an orthogonal artifact rather than duplicating the whole task.
Every route below remains provisional/requested-only under the effort-readback boundary.

| Roadmap lane | Eligible primary exact IDs | Selection condition | Requested effort and context | Complementary assignment | Gate or escalation |
|---|---|---|---|---|---|
| S1 Seeds toolchain retention | `gpt-5.6-luna` or `claude-sonnet-5` | Choose the certified member with the more independent evidence path when checks are deterministic. | `high` | The non-selected member checks evidence-to-claim coverage; Terra analyzes semantic drift. | Terra at `xhigh` recommends disposition. |
| S2 Seeds execution contract | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for contract synthesis; choose Opus for immutable stable-diff review. | Terra `xhigh`; Opus `xhigh` | Sol analyzes queue evidence; the non-selected judgment member reviews or synthesizes. | Null or mismatch fails closed; conductor adjudicates Seeds action. |
| Seeds fan-in | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra to integrate; choose Opus only to review the immutable fan-in candidate. | Terra `max`; Opus `xhigh` | Luna re-gates exact ranges; Sol analyzes stop/go ambiguity. | Authorized integrator only; conductor adjudicates. |
| Wave 1 legacy-surface removal | `gpt-5.6-terra` or `claude-opus-4-8` | Choose Terra for removal implementation; choose Opus for removed-surface review. | Terra `xhigh`; Opus `high` | Luna inventories residues. | Any shipped or runtime residue blocks. |
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

## Sort static provider-route tables most-expensive-first

Any static table this bundle or a consumer builds that maps a provider/route family to cost,
context window, or other billing-relevant fields (a fallback chain, a hand-typed route
registry, a fabricated-model builder) must sort that family **most-expensive-first**, not by
launch order, alphabetical order, or "put the flagship at index 0." The reason is a specific
failure mode observed in a worked implementation: when an unregistered or typo'd model ID is
still attempted, some model-resolver fallback paths construct a placeholder model that
inherits cost, context window, and max-token fields from the family's first array entry. If
that first entry is the cheapest route, a typo silently under-bills and silently inherits the
smallest context window — the worst possible failure, because it looks like success. If the
first entry is the most expensive route, the same typo fails expensive and visibly, which is
a far safer default than failing cheap and invisibly. Order is therefore a pricing and
safety decision, not cosmetics, and it should carry an inline comment saying so wherever such
a table is authored, plus a unit test asserting the sort order rather than trusting it to
stay correct by convention.

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
