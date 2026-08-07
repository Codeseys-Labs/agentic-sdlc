# Muse Spark Qualification — Executed Evidence

**Date:** 2026-08-07 · **Verdict: QUALIFIED WITH CONDITIONS** as a *route* — direct, no
gateway — and **explicitly NOT qualified for any tier placement**. Transport, admission,
fail-closed behavior, three surfaces, and the context-window arithmetic are all executed
evidence. Task fit is not: every probe was a one-word smoke prompt, so the route is admitted
at `route-probed` and is **tier-unproven**.

**Executed against:** the probe structure of
`docs/research/2026-08-07-opencodex-qualification-canary.md` §4–§5 (explicit-ID resolution,
per-request selection across distinct IDs, fail-closed dead routes, token counting, readback
honesty, independent attribution), extended with streaming, tool-calling, effort-vocabulary,
and context-ceiling probes. Decision recorded in
`docs/adr/0007-muse-spark-direct-route.md`.

**Standing boundary, restated up front.** This memo is **evidence for a conductor, never
authorization.** Qualifying a route does not authorize any push, publication, PR mutation,
merge, deployment, credential mutation, or other outward effect; each still requires explicit
operation-specific authorization. Per `docs/adr/0003`, routing an Anthropic subscription
credential through this or any third-party endpoint **remains prohibited**, and nothing below
relaxes that.

---

## 1. What was run, and what was deliberately not run

**Authorization scope.** The operator supplied a temporary Meta API key for this
qualification and stated it would be rotated afterwards. Roughly 60 real requests were sent,
each with a trivial prompt. Output budgets were ≤800 tokens except for a deliberate
budget-ceiling bisection whose requests were all **rejected at HTTP 400 and therefore billed
nothing**.

**Credential handling.** The key lived only in the probe environment and in a mode-0600 file
outside the repository. It appears in **no** file in this repository — not in this memo, not
in the launcher, not in a test, not in a fixture. Every command below is quoted with the value
replaced by `$MODEL_API_KEY`. The launcher never accepts a credential on the command line,
because argv is world-readable via `ps`.

**The subscription-passthrough question does not arise here, and that is the point.** The
canary had to close Probe B as prohibited because a gateway *can* forward a subscription OAuth
token. This route has no such mechanism to decline: Muse Spark is a non-Anthropic model
authenticating with its own provider-issued key, which is precisely the carve-out ADR-0003
item 2 preserves. No Anthropic or Claude credential was present in any request.

**Not run, by design:** any large-context request. The 1M window claim was tested at the
*admission boundary* only (see §5.8), which is free because rejections cost nothing. Whether
quality holds across a filled window is untested and remains a vendor claim.

---

## 2. Ground truth channel — and its weakness, stated first

The canary's designated admissible attribution source was the gateway's own JSONL log, read
out-of-band and correlated by `requestId`. **This route has no equivalent.** What exists:

| Candidate channel | Present? | Independent of the request? |
|---|---|---|
| Response body `model` field | yes | **no — it echoes the request** |
| Provider/model response header | **no** | — |
| Attribution / observe log | **no** | — |
| `GET /v1/responses/<id>` stored record | yes, `/v1/responses` only | no — same field, same vendor |
| Usage / audit surface | **no** (`/v1/usage`, `/v1/organization/usage`, `/v1/audit_logs`, `/v1/logs` → 404) | — |
| `x-request-id` response header | yes | correlates a request; carries no model identity |

So the response body is the **only** identity channel, and §6.2 says plainly what that
weakens relative to the gateway route. Every "PASS" on identity below should be read with
that ceiling in mind.

**Served catalog** (`GET /v1/models`, HTTP 200), 3 IDs: `muse-spark-1.2-contributor`,
`muse-spark-1.2`, `muse-spark-1.1`. Per-model metadata is only
`{id, object, created, owned_by}` — no context, limit, or effort fields, so the catalog cannot
be used to derive capability.

---

## 3. Verdict per probe

| Probe | Question | Verdict |
|---|---|---|
| A — ordinary completion | Explicit model ID resolves exactly, end to end? | **PASS** |
| B — per-request selection | Distinct IDs resolve independently, back to back? | **PASS** (3/3 distinct IDs) |
| C — fail-closed dead route | Non-catalog ID errors with no silent substitution? | **PASS — and stronger than the gateway** (§5.3) |
| D — `count_tokens` | Endpoint Claude Code calls responds? | **PASS, with a large constant offset** (§6.4) |
| E — readback honesty | Requested vs reported model agree? Independent channel? | **CONDITIONAL — agrees always, but no independent channel** (§6.2) |
| F — auth negative control | Does a bad/absent credential fail closed? | **PASS** |
| G — concurrent distinct pins | Distinct pins resolve independently, no cross-talk? | **PASS** |
| H — effort injection + readback | Is effort accepted? Is effective effort observable? | **PASS on request, FAIL on readback** (§6.3) |
| I — streaming | Does the SSE path resolve identically? | **PASS, with a thinking-block gap** (§5.6) |
| J — tool calling | Do single and parallel tool calls work? | **PASS** |
| K — context window | Is the 1M claim checkable cheaply? | **PASS — measured exactly, and it is SHARED** (§5.8) |
| L — budget starvation | What happens when the output budget is too small? | **HAZARD CONFIRMED — HTTP 200, empty output** (§6.1) |

**Blockers.** None absolute. The verdict is QUALIFIED WITH CONDITIONS rather than QUALIFIED
for two reasons: there is no attribution channel independent of the request (§6.2), and a
too-small output budget produces a successful-looking empty response (§6.1).

---

## 4. Surfaces

All three documented surfaces answer. They are not interchangeable — the effort parameter of
each is rejected by the others.

| Surface | HTTP | Output shape | Effort channel |
|---|---|---|---|
| `POST /v1/responses` | 200 | `[reasoning, message]`; reasoning `summary` always empty | `reasoning.effort` |
| `POST /v1/messages` | 200 | `[redacted_thinking, text]`; `stop_reason: end_turn` | `thinking.budget_tokens` |
| `POST /v1/chat/completions` | 200 | `choices[].message`; `reasoning_tokens` billed, never exposed | none accepted |

`{"reasoning":{"effort":"minimal"}}` on `/v1/messages` → **400** `unknown parameter
"reasoning"`. `thinking` on `/v1/messages` requires `budget_tokens ≥ 1024` **and**
`budget_tokens < max_tokens`, so thinking mode has a hard floor above 1024 output tokens.
`/v1/completions` and `/v1/embeddings` → 404; `POST /v1/responses/<id>` → 405.

Both auth forms work on `/v1/messages`: `Authorization: Bearer $MODEL_API_KEY` and
`x-api-key: $MODEL_API_KEY`.

---

## 5. Executed evidence

### 5.1 Probe A — ordinary completion

```
POST https://api.meta.ai/v1/responses
{"model":"muse-spark-1.2-contributor","input":[{"role":"user","content":"Reply with only the word alpha."}],
 "max_output_tokens":600,"reasoning":{"effort":"low"}}
```
HTTP 200, `status: completed`, `model: muse-spark-1.2-contributor`, output blocks
`[reasoning, message]`, text `alpha`, usage
`{input_tokens:14, output_tokens:189, reasoning_tokens:178}`. **PASS.**

Note the ratio: 178 of 189 output tokens were reasoning, for a one-word answer. That ratio is
what makes §6.1 a hazard rather than a footnote.

### 5.2 Probe B — per-request selection across three IDs

Sequential requests pinning each catalog ID, each asked for a distinct word:

| Requested | Reported `model` | Text | reasoning_tokens |
|---|---|---|---:|
| `muse-spark-1.2-contributor` | `muse-spark-1.2-contributor` | `alpha` | 178 |
| `muse-spark-1.2` | `muse-spark-1.2` | `beta` | 154 |
| `muse-spark-1.1` | `muse-spark-1.1` | `gamma` | 144 |

Each resolved to its own pin with no session stickiness and **no dated-snapshot divergence**
of the kind the gateway showed (`gpt-5.4-mini` → `gpt-5.4-mini-2026-03-17`). **PASS.**

### 5.3 Probe C — fail-closed dead routes

Every non-catalog ID was refused by the provider with **HTTP 404** and no substituted content:

| Requested `model` | HTTP | Error |
|---|---|---|
| `muse-spark-9.9-does-not-exist` | 404 | `model_not_found` |
| `claude-opus-5` | 404 | `model_not_found` |
| `meta/muse-spark-1.2` (provider-prefixed) | 404 | `model_not_found` |
| `muse-spark-1.2-CONTRIBUTOR` (case variant) | 404 | `model_not_found` |

On `/v1/messages` the same class fails the same way: `claude-opus-5` → 404 `Model not found or
access denied`.

**This is materially stronger than the gateway route**, and for a structural reason. The
canary's §6.1 finding was that fail-closed there was the *upstream's* property: unknown strings
got `routeKind: "default-provider"` and were forwarded verbatim, so safety was contingent on
whichever provider happened to be default. Here there is no second router and no
default-provider fallthrough — the provider that owns the models is the one refusing. The
catalog-membership rule (canary C1) still applies, but as a caller-side pre-check that produces
a better error, not as the only thing standing between a typo and an unintended model. **PASS.**

### 5.4 Probe F — auth negative controls

| Credential presented | HTTP |
|---|---|
| none | 401 |
| `Bearer muse-negative-control-not-a-real-credential` (literal placeholder) | 401 `invalid_api_key` |
| `x-api-key: sk-ant-placeholder-not-a-real-credential` (literal placeholder) | 401 |

Both placeholders are literal strings, not redactions of credentials. Unlike the gateway's
loopback admission — which ignored the inbound bearer entirely and served the request anyway —
this endpoint authenticates every call. **PASS.**

### 5.5 Probe D — `count_tokens`

`POST /v1/messages/count_tokens` → HTTP 200 `{"input_tokens":168}` for a 25-character message.
It responds and it varies with input length, so the surface Claude Code calls routinely is
served. But the value carries a large constant offset — see §6.4, where that offset turns out
to be load-bearing for §5.8.

### 5.6 Probe I — streaming

`/v1/messages` with `"stream":true` and `Accept: text/event-stream` returned HTTP 200 with the
correct Anthropic event sequence: `message_start`, `content_block_start`,
`content_block_delta`, `content_block_stop`, `message_delta`, `message_stop`. Text delta
`streamed`. The only model string anywhere in the stream is `"model":"muse-spark-1.2"` — no
mid-stream rewrite.

`/v1/responses` streams its own event vocabulary (`response.created`,
`response.in_progress`, `response.output_item.added`, `response.output_text.delta`,
`response.content_part.done`, `response.completed`), same single model string.

**PASS with a gap:** the `/v1/messages` stream contains **no thinking or redacted_thinking
block at all**, while the terminal `message_delta` still reports `thinking_tokens: 186`. A
consumer reconstructing the turn from the stream sees a bill for reasoning it never received —
consistent with the non-streaming `redacted_thinking`, but worth knowing before a client tries
to render or cache thinking blocks from this route.

### 5.7 Probes G and J — concurrency and tool calling

Three concurrent requests pinning all three IDs, each asked for a distinct word, returned
correctly paired results — `muse-spark-1.2-contributor`/`alpha`,
`muse-spark-1.2`/`beta`, `muse-spark-1.1`/`gamma`. Zero cross-talk. **PASS.**

Tool calling on `/v1/messages` with a trivial one-parameter schema: `stop_reason: tool_use`,
content `[redacted_thinking, text, tool_use]`, and a well-formed
`tool_use` block with `{"city":"Paris"}`. Parallel calls in one turn: **2** `tool_use` blocks,
Paris and Tokyo. `/v1/responses` reports `parallel_tool_calls: true` by default. **PASS.**

### 5.8 Probe K — the 1M context window, measured

The claim is checkable cheaply because **oversized requests are refused at 400 and cost
nothing**, so a bisection over the budget ceiling is free. Two bisections, run with different
input sizes, is what makes the result meaningful:

| Input | `count_tokens` | Largest accepted `max_output_tokens` | Smallest refused | Sum |
|---|---:|---:|---:|---:|
| `"x"` (trivial) | 165 | 1048411 | 1048412 | **1048576** |
| `"hi"` (trivial) | 165 | 1048411 | 1048412 | **1048576** |
| ~9.7k-token filler | 9765 | 1038811 | 1038812 | **1048576** |

Every row sums to exactly `2^20 = 1048576` with **zero remainder**. Confirmed as a predictive
oracle: for a given input, `max_output_tokens = 1048576 − count_tokens` is accepted and one
more is refused, in both directions, twice.

Two findings, both of which change how the window should be described:

1. **The window is exactly 1,048,576 tokens and it is a SHARED input+output budget.** It is
   not "1M input plus some output." A caller cannot request a large output *and* supply a large
   input; they compete. This is measured, not claimed.
2. **The vendor claim that remains unmeasured is the useful one.** Nothing here shows quality
   holds across a filled window, or that a 900k-token prompt is attended to. Only the
   *admission arithmetic* was measured. Record the window as measured; record window
   *usefulness* as `vendor-hypothesis`.

Above the window the error class changes: `max_output_tokens: 999999999` returned **429**
`rate_limit_exceeded` ("Output token rate limit exceeded. Try lowering max_output_tokens to
reduce reserved capacity"), not 400. An oversized request can therefore present as throttling,
and a client with retry-on-429 would retry a request that can never succeed.

### 5.9 Probe H — effort vocabulary and readback

The provider enumerated its own vocabulary in a 400, which is stronger evidence than a docs
page:

```
{"error":{"message":"`reasoning.effort`: unknown variant `ultra`, expected one of
 `none`, `minimal`, `low`, `medium`, `high`, `xhigh`","param":"reasoning.effort",
 "type":"invalid_request_error"}}
```

So: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`. **`max` is not in the vocabulary** —
this bundle's calibrated `max` band cannot be expressed on this route. And `none`, though
enumerated, is refused for these models: `"reasoning.effort" does not support "none" with this
model.` All of `minimal`/`low`/`medium`/`high`/`xhigh` were accepted.

Reasoning consumption on an identical trivial prompt, by requested effort:

| Requested | reasoning_tokens |
|---|---:|
| `minimal` | 61 |
| `low` | 201 |
| `medium` | 348 |
| `high` | 147 |
| `xhigh` | 146 |

**This is not an effort-quality curve and must not be read as one.** It is not even monotonic:
`high` and `xhigh` consumed fewer reasoning tokens than `medium` on this prompt. A trivial
one-word prompt gives the model nothing to think harder about, so the numbers mostly reflect
sampling noise. They are recorded to prevent someone inferring a curve from them later.

---

## 6. Findings

### 6.1 HAZARD CONFIRMED — reasoning tokens starve the output budget, and starvation looks like success

The operator's predicted gotcha reproduced, and it is worse than a single data point: it
reproduces across budgets and across both surfaces, and it always returns **HTTP 200**.

`/v1/responses`, trivial prompt, `reasoning.effort: low`:

| `max_output_tokens` | HTTP | `status` | `incomplete_details` | reasoning_tokens | output |
|---:|---:|---|---|---:|---|
| 32 | **200** | `incomplete` | `{"reason":"max_output_tokens"}` | 29 | **`[]` — empty** |
| 128 | **200** | `incomplete` | `{"reason":"max_output_tokens"}` | 125 | **`[]` — empty** |
| 600 | 200 | `completed` | `null` | 210 | `budget` |

`/v1/messages`, `max_tokens: 32`: HTTP **200**, `stop_reason: max_tokens`,
`thinking_tokens: 29`, `content: []` — empty.

Reasoning is billed **before** any visible text, so the entire budget can be consumed with
nothing to show. Three consequences:

1. **Any health check that asserts only HTTP 200 is worthless on this route.** It will pass
   against a route that cannot emit a single word. The check must assert non-empty text. This
   is enforced in `scripts/muse-claude.sh`, not documented as advice — and it was verified by
   shrinking the probe budget to 32 in a scratch copy and confirming the launcher fails closed
   with a named reason.
2. **Budget guidance must cover reasoning, not output.** Observed reasoning consumption on
   trivial prompts spanned 48–499 tokens across efforts and models. A budget under ~600
   risks an empty completion *for a one-word answer*; a real task needs the reasoning
   allowance on top of its expected output.
3. **The distinguishing signal is `status`/`stop_reason`, not the HTTP code.** `incomplete` +
   `{"reason":"max_output_tokens"}` on `/v1/responses`, `stop_reason: max_tokens` on
   `/v1/messages`. A client that ignores those fields cannot tell starvation from a model that
   chose to say nothing.

`reasoning.effort: minimal` reduces consumption (61 tokens) but does **not** eliminate the
charge, and `none` is refused, so there is no way to turn reasoning off on these models.

### 6.2 FINDING — the response body is the only identity channel, which is weaker in kind than the gateway's log

Across every probe, the reported `model` matched the requested ID exactly — no alias echo, no
dated-snapshot suppression, no prefix-stripping divergence. On the canary's own scoring that
looks *better* than the gateway. **It is not better; it is less observable.**

The gateway had two channels that disagreed, and the disagreement is what produced knowledge:
the body echoed `claude-ocx-native--gpt-5.6-terra` while the log recorded `gpt-5.6-terra`. That
route's body is inadmissible *because* an independent record contradicted it. Here there is
only one channel, and it is an **echo of the caller's own request**. A match is therefore
consistent with two different worlds — a truthful report, or a server that echoes the request
string without checking — and these probes cannot distinguish them. The stored record at
`GET /v1/responses/<id>` is a second read of the same assertion from the same vendor, not a
second channel, and it does not exist for `/v1/messages` at all or for `store: false`.

What does the work instead is the **absence of a substitution mechanism**: a non-catalog ID is
refused 404 rather than quietly routed (§5.3), and there is no router between caller and
provider that could rewrite the target. So there is no observed path by which a request for one
catalog ID is served by another while reporting the requested one. That is an argument from
structure, not a positive identity observation, and it must be recorded as such.

**Doctrine consequence.** A `RuntimeAssignment` on this route sets `observed_identity_source`
to `adapter_response_readback` and carries neither gateway field. `model_identity_basis` must
record that identity rests on an exact-ID request, a catalog-membership pre-check, and a
matching response echo — **not** on an independent observation channel, because none exists.

### 6.3 FINDING — effort readback is honestly unavailable, and the echo is a trap

`/v1/responses` returns `reasoning: {"effort": "<requested>"}` in the response body. It
matched the request in all five probes. **This is not readback** — it is the requested value
returning, exactly the class the doctrine forbids promoting ("never copy requested effort into
effective readback"). It is more dangerous than the gateway's honest silence, because it *looks*
like a readback field and a careless implementation would bind it.

The one signal that is genuinely not request-derived: with `reasoning` **omitted**, the
response reports the model's own default. All three models reported `high`. That is real
information about the route (it tells you the default band), and it is still not effective-effort
readback.

`usage.output_tokens_details.reasoning_tokens` is real observed telemetry, but a token count is
not a value in the policy's effort vocabulary, so per the receipt-admission boundary an
out-of-vocabulary observation is `unavailable`, never verified. `/v1/messages` exposes no effort
field at all.

**Correct handling:** `effort_readback_status: unavailable`, with the requested value recorded
as requested. Per AGENTS.md this is a *permitted* honest gap.

### 6.4 FINDING — `count_tokens` carries a ~165-token constant offset, and it is the right oracle anyway

`count_tokens` and billed `input_tokens` disagree systematically:

| Content | `count_tokens` | billed `input_tokens` |
|---|---:|---:|
| `"x"` | 165 | — |
| `"hi"` | 165 | — |
| `"Reply with only the word messages."` | 168 | **14** |
| ~1000-char filler | 365 | — |

A ~163–165 token constant that billing does not charge — presumably a system-prompt or
template overhead the counter includes. Naively this looks like a bug in `count_tokens`.

**It is not, for the purpose that matters.** §5.8 showed `count_tokens` predicts the *admission*
boundary exactly: `1048576 − count_tokens` is accepted and one more is refused. So the two
numbers answer different questions, and both are correct for their own: `count_tokens` is the
**admission** oracle (what the window charges), billed `input_tokens` is the **billing** truth
(what you pay). Use `count_tokens` to decide whether a request fits and `input_tokens` to
account for cost — and never substitute one for the other, which would overstate cost by ~165
tokens per call or understate window pressure by the same.

### 6.5 FINDING — a wrong base URL returns 401, so misconfiguration presents as a bad credential

The vendor documents `https://api.meta.ai/v1` as the base URL for SDK use. An Anthropic-shaped
client appends `/v1/messages` itself, producing `/v1/v1/messages` — which, **with a fully valid
credential**, returns:

| Path | Credential | HTTP |
|---|---|---|
| `/v1/messages` | valid | **200** |
| `/v1/v1/messages` | valid | **401** |
| `/nonsense/path` | valid | 404 |

An unknown path under `/v1/` answers 401, indistinguishable from an invalid key. The failure
mode is an operator rotating a perfectly good credential to fix a URL typo. Two mitigations,
both implemented: `ANTHROPIC_BASE_URL` is recorded as `https://api.meta.ai` **without** the
`/v1` suffix, and the launcher probes the catalog *first* so a 401 is reported with both causes
named rather than blamed on the credential.

### 6.6 Observation — the two tiers differ in quota, not in any observed capability

Rate-limit headers, same key, same moment:

| Model | `x-ratelimit-limit-requests` | `x-ratelimit-limit-tokens` |
|---|---:|---:|
| `muse-spark-1.2-contributor` | **100** | 3,000,000 |
| `muse-spark-1.2` | **3000** | 4,000,000 |
| `muse-spark-1.1` | 3000 | 4,000,000 |

The only observed difference between contributor and standard tiers is quota, and the
contributor ceiling of 100 requests is low enough to exhaust in a single fan-out wave. Nothing
in these probes distinguishes their output quality. Account-, key-, and date-specific.

### 6.7 Observation — no independent attribution surface exists to build one from

`/v1/usage`, `/v1/organization/usage`, `/v1/audit_logs`, `/v1/logs` all 404. `GET /v1/responses`
(list) → 405. `GET /v1/responses/<id>` works for `store: true` (the default) on
`/v1/responses` only; `store: false` → 404, and a `/v1/messages` message ID → 404 on both
`/v1/responses/<id>` and `/v1/messages/<id>`. There is no server-side record to correlate for
the surface an Anthropic-shaped client actually uses. `x-request-id` is present on every
response and is useful for a support conversation, but it carries no model identity.

---

## 7. Overall verdict

**QUALIFIED WITH CONDITIONS** as a direct, non-gateway route on `POST /v1/messages` (streaming
and non-streaming), `POST /v1/responses`, and `POST /v1/chat/completions`, for the three
catalog IDs, authenticating with Meta's own API key.

**NOT QUALIFIED for any tier placement.** Every probe was a one-word smoke prompt or a
two-city tool call. They establish transport, admission, fail-closed behavior, surface shape,
and the window arithmetic. They establish **nothing** about task fit. Under the calibration's
own ladders the route is at `route-probed`, never `role-qualified`; transport and admission are
`exact-route-live` while every capability claim is `vendor-hypothesis`; and documented
positioning is `mined`, which may propose a reconsideration but can never raise a rung or fill
a scale-setter slot. No tier assignment is recorded, no eligible pair is amended, and the
six-primary policy is untouched.

**Binding conditions.** Qualification holds only while all of these hold:

- **M1.** Every dispatched model ID is present in the live `GET /v1/models` catalog, matched
  whole (`muse-spark-1.2` must not be satisfied by `muse-spark-1.2-contributor`). Non-catalog
  IDs are refused 404 by the provider, so this is a better-error pre-check rather than the sole
  barrier (§5.3).
- **M2.** `resolved_model_id` is sourced from the response body with
  `observed_identity_source: adapter_response_readback`, and the receipt records that no
  independent attribution channel exists on this route. The gateway fields
  (`gateway_attribution_log`, `catalog_bytes` pointers) do not apply (§6.2).
- **M3.** Effort is recorded as *requested*; `effort_readback_status` is `unavailable`. The
  response's echoed `reasoning.effort` is never bound as readback (§6.3).
- **M4.** Output budgets account for reasoning tokens, and any liveness check asserts
  **non-empty text**, never HTTP 200 alone. Treat `status: incomplete` /
  `stop_reason: max_tokens` with empty output as failure, not as an answer (§6.1).
- **M5.** `ANTHROPIC_BASE_URL` is `https://api.meta.ai` with **no** `/v1` suffix, and a 401 is
  diagnosed as *either* credential *or* base-URL error before any credential is rotated (§6.5).
- **M6.** The context window is recorded as measured at exactly 1,048,576 tokens **shared**
  between input and output; window *usefulness* stays `vendor-hypothesis`. Requests are sized
  with `count_tokens` (the admission oracle) and cost is accounted with billed `input_tokens`
  (§5.8, §6.4). A 429 is not assumed to be throttling until the request size is ruled out.
- **M7.** The route is selected only for work whose failure a **complete deterministic check**
  catches, and only as a recorded experiment. It is ineligible for frontier or
  judgment-workhorse work; `max` effort is unavailable on it and `xhigh` is its ceiling (§5.9).
  Promotion requires the A0–A6 ladder with paired isolation and utility arms plus a real
  task-fit comparison — not a repeat of these smoke probes.
- **M8.** Meta's own API key authenticates every request. No Anthropic subscription credential
  is present, forwarded, or replayed. Non-negotiable per ADR-0003 and independent of this
  memo's outcome.

**What this does not qualify.** Task fit or tier placement (explicitly out of scope, and the
main open question). Large-context behavior (untested by design). Output quality differences
between the contributor and standard tiers (none observed; none looked for). Sustained
throughput or quota behavior under load. Durability of the temporary credential used here,
which the operator stated will be rotated. And per the standing boundary: **it authorizes
nothing.** It is evidence a conductor may cite when constructing a `RuntimeAssignment`, and
every outward effect still requires its own explicit authorization.

---

## 8. Reproduction

- Endpoint `https://api.meta.ai`; catalog IDs `muse-spark-1.2-contributor`, `muse-spark-1.2`,
  `muse-spark-1.1` as served 2026-08-07.
- Probe bodies are quoted inline above; substitute `$MODEL_API_KEY` from the environment. No
  credential value appears in this memo or anywhere else in this repository, and the §5.4
  bearers are literal placeholder strings, not redactions.
- Re-verify the route without launching a client:
  `mise run muse:probe` (or `scripts/muse-claude.sh probe`).
- Scratch probe artifacts were written under `/tmp/muse-probe/` and are ephemeral, not
  committed.
- Rerun triggers, per the calibration's own list: any change to the served catalog, the effort
  vocabulary, the window arithmetic, the auth forms accepted, or the rate-limit headers; and
  before any attempt to promote this route past `route-probed`.
