# opencodex Qualification Canary — Executed Evidence

**Date:** 2026-08-07 · **Verdict: QUALIFIED WITH CONDITIONS** for the non-Anthropic
split-plane route only, and **only when every dispatched model ID is drawn from the
gateway's own `/v1/models` catalog in bare or `openai/`-prefixed form**. Three of the
memo's predicted hazards were reproduced live; one of them (§6.1) is materially worse
than the memo predicted and must be enforced in the `RuntimeAssignment` validator, not
documented as advice.

**Executed against:** `docs/research/2026-08-05-gateway-selection-memo.md` §4, under the
verdict frame of `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`
Decision item 5. Closes the "canary remains unrun" gate that ADR-0005 left open.

**Standing boundary, restated up front.** This memo is **evidence for a conductor, never
authorization.** Qualifying a route does not authorize any push, publication, PR mutation,
merge, deployment, credential mutation, or other outward effect; each still requires
explicit operation-specific authorization. Per `docs/adr/0003`, routing an Anthropic
subscription credential through this or any gateway **remains prohibited**, and nothing
below relaxes that.

---

## 1. What was run, and what was deliberately not run

**Authorization scope.** The operator explicitly authorized this canary, including a small
number of real requests billed to their Codex OAuth account. 14 real requests were sent,
each capped at `max_tokens: 32` with a trivial prompt (one exception: the thinking-budget
probe in §5.7 needed `max_tokens: 2048` to carry a 1024-token thinking budget).

**Memo Probe B was NOT run, by design.** Probe B is the subscription-OAuth passthrough
test — the make-or-break test for memo requirement (2). ADR-0003 Decision item 3 already
resolved that question on authorization grounds and made Probe B moot; ADR-0005 records it
as such. No Anthropic or Claude subscription credential was routed, included, or present
in any request in this canary. Every request was served by the gateway's configured
`openai` provider via Codex OAuth. **Probe B is not "pending" — it is closed as prohibited.**

**Memo Probe A was re-scoped.** The memo's Probe A is a negative control on the inbound
`sk-ant-` credential gate, which only has meaning on the passthrough path. Since that path
is prohibited, the probe was re-scoped to the observable question that survives: *does the
gateway's inbound credential handling affect routing on the permitted path at all?*
(Answer in §5.6: no, and that is itself a finding.)

**Environment note — deviation from the memo's §4 step 0.** The memo scripts an isolated
throwaway `HOME` and a from-scratch `npm install -g`. This canary instead ran against the
**already-running, already-installed gateway the operator started** (PID 2474885, port
10100, uptime 7118s at first probe, config `~/.opencodex/config.json`), because ADR-0005
has since made this the default pinned install and the qualification question is about
*that* deployment, not a synthetic one. Consequence: the canary made **no** persistent
`mise trust`, shell-alias, global-config, or credential mutation, but it also did **not**
prove the memo's isolated-install path. The only files this canary created are under
`/tmp/ocx-canary-logs/` plus this memo.

---

## 2. Ground truth channel

Attribution came from the memo's designated **only admissible** source, not from response
bodies:

```
mise -C <repo> exec -- ocx observe logs --follow --jsonl
```

Captured to `/tmp/ocx-canary-logs/ocx.jsonl` as a background process, started **before**
any probe traffic. The stream replays history, so every probe below is identified by an
exact `requestId` and was read past a recorded line watermark (first probe began at line
202). 218 total request lines were captured; 14 are this canary's.

Each line carries `requestedModel`, `resolvedModel`, `provider`, `status`, `attempts`, and
a `routeDecision` object with `routeKind`, `candidates[]`, and `selected.reason`. That
object is what makes per-request attribution real rather than inferred.

---

## 3. Pre-traffic contract assertions

The memo's §2 configuration contract was asserted against the live config **before** any
traffic. All four required-empty conditions hold:

| Contract assertion | Observed | Result |
|---|---|---|
| Zero `combos` entries | `ocx combo list` → `No combos configured.`; `jq .combos` → `null` | **PASS** |
| `subagentModelFallback` empty | `null` | **PASS** |
| `model_fallback` empty | `[]` | **PASS** |
| No provider with `disabled: true` | only provider is `openai`, `disabled` unset | **PASS** (vacuously) |

Configured providers: **`openai` only** (`adapter=openai-responses`, `codexAccountMode:
"pool"`, `authMode: "forward"`, one `codex` account, plan label `pro`). The `anthropic` and
`anthropic-apikey` providers appear in the 69-entry available registry but are **not
configured and not logged in** — consistent with ADR-0005 item 4 and ADR-0003.

This matters for reading §6.1: the worst finding below occurs *with a clean contract*. It
is not a misconfiguration.

**Served catalog** (`GET /v1/models`, HTTP 200), 7 IDs: `gpt-5.6-sol`, `gpt-5.6-terra`,
`gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex-spark`.

---

## 4. Verdict per probe

| Probe | Question | Verdict |
|---|---|---|
| A — ordinary completion | Explicit model ID resolves exactly, end to end? | **PASS** |
| B — subscription passthrough | — | **NOT RUN — closed as prohibited** (ADR-0003) |
| C — fail-closed dead route | Dead route errors with no silent substitution? | **PASS on outcome, with a hazard in the mechanism** (§6.1) |
| D — `count_tokens` | Endpoint Claude Code calls responds? | **PASS, with an attribution gap** (§6.3) |
| E — readback honesty | Requested vs response-body vs log `resolvedModel` agree? | **CONDITIONAL** — one systematic mismatch (§6.2) |
| F — inbound credential gate | Does inbound bearer affect the permitted path? | **PASS (no-op confirmed)** — finding, not failure (§5.6) |
| G — per-request/concurrent pinning | Distinct pins resolve independently, no cross-talk? | **PASS** |
| H — effort injection readback | Is effective effort observable? | **FAIL on readback** (§6.4) |
| I — roster route ID | Does the shipped `claude-*` alias resolve? | **PASS functionally, HAZARD confirmed** (§6.1) |

**Blockers under the memo's frame.** The memo's absolute blockers were B and E. B is moot
by ADR-0003. E passes only *conditionally*: attribution is observable per-request and
per-request pinning is exact, but the response body's `model` field is **not** a truthful
readback surface (§6.2), which is why the overall verdict is QUALIFIED WITH CONDITIONS
rather than QUALIFIED.

---

## 5. Executed evidence

All requests: `POST http://127.0.0.1:10100/v1/messages`, headers `content-type:
application/json` and `anthropic-version: 2023-06-01` — i.e. Anthropic Messages format,
exactly what a launched Claude Code process sends.

### 5.1 Probe A — ordinary completion

Request:
```json
{"model":"gpt-5.6-terra","max_tokens":32,"messages":[{"role":"user","content":"Say the word canary and nothing else."}]}
```
Response, HTTP 200:
```json
{"id":"msg_9077cff5358746beabf083bf9bcdd8c2","type":"message","role":"assistant","content":[{"type":"text","text":"canary"}],"model":"gpt-5.6-terra","stop_reason":"end_turn","usage":{"input_tokens":15,"output_tokens":6}}
```
Attribution line:
```json
{"requestId":"ocx-msilknla-65","requestedModel":"gpt-5.6-terra","resolvedModel":"gpt-5.6-terra","model":"gpt-5.6-terra","provider":"openai","status":200,"attempts":null,"routeKind":"native","reason":"native-family","candidates":[{"provider":"openai","model":"gpt-5.6-terra","eligible":true,"exclusions":[]}]}
```
Requested, response-body, and log `resolvedModel` all name `gpt-5.6-terra`. One eligible
candidate, no exclusions, `attempts: null` (no retry/hop). **PASS.**

### 5.2 Probe B — per-request selection, back to back

Two sequential requests pinning different IDs. Response bodies returned `gpt-5.4-mini`/`"1"`
and `gpt-5.3-codex-spark`/`"2"`, both HTTP 200. Attribution:
```json
{"requestId":"ocx-msill1xj-66","requestedModel":"gpt-5.4-mini","resolvedModel":"gpt-5.4-mini-2026-03-17","model":"gpt-5.4-mini","status":200,"attempts":null,"reason":"native-family"}
{"requestId":"ocx-msill33b-67","requestedModel":"gpt-5.3-codex-spark","resolvedModel":"gpt-5.3-codex-spark","model":"gpt-5.3-codex-spark","status":200,"attempts":null,"reason":"native-family"}
```
Each resolved to its own pin. No session stickiness. **PASS** — and note the first line's
`resolvedModel` is a *dated snapshot* (`-2026-03-17`) that the response body does not
report; see §6.2.

### 5.3 Probe C — fail-closed dead routes

Four dead-route requests, each returning **HTTP 400** with an explicit Anthropic-shaped
error object and **no** substituted content:

| Requested `model` | HTTP | `resolvedModel` | `routeKind` |
|---|---|---|---|
| `gpt-9.9-does-not-exist` | 400 | `null` | `native` |
| `anthropic/claude-opus-5` | 400 | `null` | `default-provider` |
| `claude-opus-5` (bare) | 400 | `null` | `default-provider` |
| `notaprovider/gpt-5.6-terra` | 400 | `null` | `default-provider` |
| `gpt-5.1-codex` (real-looking, not in catalog) | 400 | `null` | `native` |

Representative body:
```json
{"type":"error","error":{"type":"invalid_request_error","message":"upstream error (400): {\"detail\":\"The 'anthropic/claude-opus-5' model is not supported when using Codex with a ChatGPT account.\"}"}}
```
Attribution for the two `claude-*` attempts:
```json
{"requestId":"ocx-msillln1-69","requestedModel":"anthropic/claude-opus-5","resolvedModel":null,"model":"anthropic/claude-opus-5","provider":"openai","status":400,"attempts":null,"routeKind":"default-provider","reason":"default-provider"}
{"requestId":"ocx-msillls3-6a","requestedModel":"claude-opus-5","resolvedModel":null,"model":"claude-opus-5","provider":"openai","status":400,"attempts":null,"routeKind":"default-provider","reason":"default-provider"}
```
`attempts` is `null` on **every** dead route: **no fallback hop fired anywhere in this
canary.** No `claude-*` request was ever answered by a model. Outcome is fail-closed.

**But the mechanism is not the gateway's router** — see §6.1. `routeKind:
"default-provider"` means the gateway did not recognize the target and forwarded the
literal string to `openai`, where the *upstream* rejected it. The 400 is OpenAI's, not
opencodex's.

Positive control that provider-prefix parsing does work when the provider is configured:
```json
{"requestId":"ocx-msilm92d-6b","requestedModel":"openai/gpt-5.6-terra","resolvedModel":"gpt-5.6-terra","status":200,"routeKind":"explicit-provider","reason":"explicit-provider-namespace"}
```
`openai/gpt-5.6-terra` gets `routeKind: "explicit-provider"` and strips the namespace
correctly. So the router distinguishes *configured* from *unknown* prefixes — it just
doesn't reject the unknown ones. **PASS on the letter of requirement (5)** in this
configuration, conditional on §6.1.

### 5.4 Probe D — `count_tokens`

```
POST /v1/messages/count_tokens  {"model":"gpt-5.6-terra","messages":[...]}
→ HTTP 200  {"input_tokens":17}
```
**PASS.** Claude Code's token-counting call is served. Attribution gap in §6.3.

### 5.5 Probe E1 — streaming SSE path

Claude Code streams, so the streaming path was probed separately with `"stream": true`
(`gpt-5.6-luna`). HTTP 200, correct event sequence (`message_start`,
`content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`,
`message_stop`, `ping`), text delta `"stream"`. The only model string across all SSE
events is `"model":"gpt-5.6-luna"` — no mid-stream rewrite. Attribution:
```json
{"requestId":"ocx-msilnc7b-6e","requestedModel":"gpt-5.6-luna","resolvedModel":"gpt-5.6-luna","status":200,"attempts":null,"transportPhase":"terminal_sse"}
```
**PASS.** Streaming resolves identically to non-streaming.

### 5.6 Probe F — inbound credential is a no-op on this path

A deliberately invalid non-Anthropic-shaped placeholder bearer (`Bearer
canary-negative-control-not-a-real-credential` — a literal string, not a credential of any
kind) was sent with an otherwise valid request. Result: **HTTP 200, served normally.**
```json
{"requestId":"ocx-msilnipa-6f","requestedModel":"gpt-5.6-terra","resolvedModel":"gpt-5.6-terra","status":200,"admissionKind":"loopback","surface":"claude"}
```
The gateway ignored the inbound bearer entirely and served the request from its own stored
Codex OAuth. `admissionKind: "loopback"` on all 218 captured lines: loopback admission
does not authenticate callers.

**This is a finding, not a failure.** It means (a) the inbound credential cannot influence
routing on the permitted path, so there is no credential-confusion risk *here*; and (b)
**anything that can reach port 10100 can spend the operator's Codex quota.** The gateway's
only access control on this path is that it binds loopback. That is an acceptable posture
for a single-operator localhost deployment and an unacceptable one for anything else.

### 5.7 Probe G — concurrent distinct pins

Three requests dispatched concurrently (`&` + `wait`) pinning `gpt-5.6-sol`,
`gpt-5.4-mini`, `gpt-5.3-codex-spark`, prompted to reply `alpha`/`beta`/`gamma`. Every
response paired the right word with the right model — `gpt-5.6-sol`/`alpha`,
`gpt-5.4-mini`/`beta`, `gpt-5.3-codex-spark`/`gamma`. Three distinct `requestId`s, each
`attempts: null`, each `resolvedModel` matching its pin, `conversationId: null` on all
three (no shared session state):
```json
{"requestId":"ocx-msilo2xt-6g","requestedModel":"gpt-5.6-sol","resolvedModel":"gpt-5.6-sol","status":200,"attempts":null,"conversationId":null}
{"requestId":"ocx-msilo2xx-6h","requestedModel":"gpt-5.4-mini","resolvedModel":"gpt-5.4-mini-2026-03-17","status":200,"attempts":null,"conversationId":null}
{"requestId":"ocx-msilo2y0-6i","requestedModel":"gpt-5.3-codex-spark","resolvedModel":"gpt-5.3-codex-spark","status":200,"attempts":null,"conversationId":null}
```
**PASS. Zero cross-talk, zero `attempts[]` length > 1** — the memo's Probe E no-go
conditions are both absent.

### 5.8 Probe H — effort injection

A `model:effort` suffix (`gpt-5.6-terra:high`) is **not** a supported convention here —
HTTP 400, `resolvedModel: null`. The catalog instead advertises per-model
`reasoning_efforts` (`low`/`medium`/`high`/`xhigh`/`max`, plus `ultra` on `gpt-5.6-sol`
and `gpt-5.6-terra`) with a per-model default.

Anthropic-native `thinking.budget_tokens: 1024` **is** honored as the effort channel:
```json
{"requestId":"ocx-msilol5x-6l","requestedModel":"gpt-5.6-terra","resolvedModel":"gpt-5.6-terra","status":200,"requestedEffort":"low","responseServiceTier":"default"}
```
The gateway mapped a 1024-token thinking budget to `requestedEffort: "low"`. **The request
side is observable; the readback side is not** — see §6.4.

### 5.9 Probe I — the shipped roster alias

ADR-0005 item 2 records that a `launch` writes opencodex's roster agents into the isolated
`CLAUDE_CONFIG_DIR`. Five exist at
`~/.local/state/agentic-sdlc/ocx-claude/agents/ocx-gpt-5-*.md`, and their frontmatter
confirms the memo's roster hazard verbatim:
```
model: "claude-ocx-native--gpt-5.6-terra"
description: "... NOTE: this agent's real model is pinned by the opencodex proxy — the
  `model` argument is ignored. Pass model: \"haiku\" as a placeholder ..."
```
`cache/gateway-models.json` shows the whole alias namespace is `claude-`-prefixed:
`claude-ocx-native--gpt-5.6-terra`, `...--gpt-5.4-mini`, `...--gpt-5.4[1m]`, and so on.

Requesting that alias directly:
```json
{"model":"claude-ocx-native--gpt-5.6-terra","max_tokens":32,"messages":[{"role":"user","content":"Reply with only the word roster."}]}
```
→ **HTTP 200**, body:
```json
{"content":[{"type":"text","text":"roster"}],"model":"claude-ocx-native--gpt-5.6-terra","stop_reason":"end_turn"}
```
Attribution:
```json
{"requestId":"ocx-msilpotv-6m","requestedModel":"gpt-5.6-terra","resolvedModel":"gpt-5.6-terra","model":"gpt-5.6-terra","provider":"openai","status":200,"routeKind":"native","reason":"native-family"}
```
Functionally correct: an OpenAI model served it. **But the response body told the caller it
was `claude-ocx-native--gpt-5.6-terra` while the log recorded `gpt-5.6-terra`, and the log
never recorded the inbound alias at all** (`grep -c 'claude-ocx-native' ocx.jsonl` → `0`).
This is the sharpest edge found. See §6.1 and §6.2.

---

## 6. Findings

### 6.1 HAZARD CONFIRMED — fail-closed here is the upstream's property, not the gateway's

The memo predicted that prefix-pattern matching "ignores the provider `disabled` flag" and
concluded that "never emit a bare model ID" must become validator-enforced. **The live
behavior is a generalization of that prediction, and it is broader:** any model string the
gateway does not recognize — including `anthropic/claude-opus-5`, bare `claude-opus-5`, and
`notaprovider/gpt-5.6-terra` — is **not rejected by the router**. It gets `routeKind:
"default-provider"` and is forwarded verbatim to the default provider, which is `openai`.

Today that is safe *only because* the sole configured provider is a Codex account that
refuses unknown model names. The fail-closed outcome in §5.3 is **OpenAI's 400, not
opencodex's throw.** Two consequences:

1. **The memo's contract item "never emit a bare `claude-*` ID; always `anthropic/claude-…`"
   is wrong in this deployment.** Both forms behave identically — both fall through to
   `default-provider`. The prefixed form buys nothing. The rule that actually holds is
   stricter: **only dispatch IDs present in `GET /v1/models`, bare or `openai/`-prefixed.**
2. **The safety is contingent on the provider roster.** If a second provider is ever
   configured, or `defaultProvider` changes to one with a permissive model namespace, the
   same unknown-string fallthrough could resolve somewhere unintended — and it would do so
   with `routeKind: "default-provider"`, which is the log signature to alarm on.

**Required enforcement** (ADR-0005 item 5's open gate, now specified): the
`RuntimeAssignment` validator must reject any `resolved_model_id` not in the live
`/v1/models` catalog, rather than trusting a prefix convention. Prefix rules do not
discriminate here; catalog membership does.

### 6.2 FINDING — the response-body `model` field is not a truthful readback surface

Requirement (6) asked whether resolved model identity is reported back. Two distinct
mismatches, both systematic:

- **Alias echo (§5.9).** Request `claude-ocx-native--gpt-5.6-terra` → body says
  `claude-ocx-native--gpt-5.6-terra`; log says `gpt-5.6-terra`. The body echoes the
  caller's own string. A client reading only the body would record a `claude-*` model
  identity for a request served by OpenAI. This is exactly the confusion the doctrine's
  readback requirement exists to prevent — and the shipped roster agents use this alias
  form by default.
- **Snapshot suppression (§5.2, §5.7).** Request `gpt-5.4-mini` → body says
  `gpt-5.4-mini`; log says **`gpt-5.4-mini-2026-03-17`**. The log carries a more specific
  truth than the body. Reproduced twice, in sequential and concurrent probes.
- **Prefix stripping (§5.3).** Request `openai/gpt-5.6-terra` → body says
  `openai/gpt-5.6-terra`; log says `gpt-5.6-terra`.

Confirming the memo's §1 row (6): **no provider/model response header exists.** `curl -D -`
on every probe shows no `x-opencodex-provider`, `x-opencodex-model`, or
`x-opencodex-resolved-model`. (`X-OpenCodex-API-Key` appears only inside
`Access-Control-Allow-Headers`, which is a CORS request-header allowlist, not a readback.)

**Doctrine consequence.** The memo's §2 contract — treat `ocx observe logs --jsonl` as the
*only* admissible `resolved_model_id` evidence, with the response `model` merely
corroborating — is **confirmed as necessary, and must be strengthened.** The body is not
corroborating; in the alias case it actively disagrees. A `RuntimeAssignment` for a
gateway-routed model may set `resolved_model_id` **only** from the log's `resolvedModel`,
correlated by `requestId`. Sourcing it from the response body would record a false
identity.

This resolves memo Probe F's open question in the direction the memo flagged as the bad
branch: log correlation is the *only* available readback, so whether it clears the
doctrine's "resolved only after adapter readback" bar is a policy call the conductor must
make explicitly. It is an out-of-band asynchronous stream correlated by ID, not an
in-band adapter readback on the response itself.

### 6.3 FINDING — `count_tokens` is an unattributed surface

`grep -c 'count_tokens' ocx.jsonl` → `0`. The successful count_tokens call emitted **no**
attribution line. So a surface Claude Code calls routinely is invisible to the only
admissible attribution channel. Low severity (it returns a token count, not model output,
and cannot silently substitute a *model*), but it means "every request is attributable" is
false as stated — it holds for `/v1/messages` only.

### 6.4 FINDING — effective effort readback is unavailable

`requestedEffort` is recorded. **`effectiveEffort` appears zero times in 218 captured
lines**, and no `context`/`window` field exists anywhere in the schema. Per AGENTS.md,
"effective effort/context readback may be honestly unavailable, and requested values never
become readback" — so this is a *permitted* honest gap, not a violation. The correct
handling: a `RuntimeAssignment` for a gateway-routed model records the requested effort as
requested and **must not** claim effort readback. `requestedEffort: "low"` is the
gateway's own mapping of a thinking budget, which is evidence about the request, not about
what the upstream did.

### 6.5 NOT REPRODUCED — combo failover hops

The memo's top-ranked hazard (`combo/*` defaults to `strategy: failover`, hopping on
401/403/404/408/429/5xx) **did not fire and could not fire**: zero combos are configured
(§3), and `attempts` is `null` on all 14 canary requests including all five 400s. This
hazard is absent-by-configuration, not disproven. It returns the moment a combo is added,
so the §3 contract assertion must stay a pre-dispatch check rather than a one-time
observation.

### 6.6 Observation — restart safety

`opencodex-claude.sh status` reports `Restart safety: AT RISK after restart (no viable
background service; run 'ocx service install')` and `Codex autostart shim is not
installed.` Not a routing finding and out of this canary's scope, but it means the
qualified route does not survive a host restart without operator action. Installing a
background service is a persistent system mutation and was **not** performed.

---

## 7. Overall verdict

**QUALIFIED WITH CONDITIONS** — for the non-Anthropic split-plane route (Codex OAuth via
the `openai` provider) on `POST /v1/messages`, streaming and non-streaming.

Against the three-part frame:

1. **Explicit model IDs resolve exactly — YES, for catalog IDs.** All 9 successful probes
   resolved `requestedModel` → `resolvedModel` with the requested target, `attempts: null`,
   single eligible candidate, no exclusions. Per-request selection is independent
   sequentially (§5.2) and concurrently (§5.7).
2. **Attribution is observable per-request — YES for `/v1/messages`, NO for
   `count_tokens`.** `requestId` + `resolvedModel` + `routeDecision` give genuine
   per-request attribution with candidate sets and selection reasons. It is an out-of-band
   log stream, not an in-band header (§6.2).
3. **Dead routes fail closed with no silent substitution — YES in outcome, CONTINGENT in
   mechanism.** Five dead routes → five HTTP 400s, zero fallback hops, zero `claude-*`
   answers. But unknown IDs are rejected by the *upstream* after `default-provider`
   fallthrough, not by the gateway's router (§6.1).

**Binding conditions.** Qualification holds only while all of these hold:

- **C1.** Every dispatched model ID is present in the live `GET /v1/models` catalog, bare
  or `openai/`-prefixed. Validator-enforced by catalog membership, **not** by prefix
  convention (§6.1 supersedes the memo's "always `anthropic/`-prefix" advice).
- **C2.** `resolved_model_id` is sourced **only** from the log's `resolvedModel`,
  correlated by `requestId`. The response body's `model` field is not admissible — it
  echoes caller aliases and suppresses dated snapshots (§6.2).
- **C3.** Effort is recorded as *requested*, never as readback (§6.4).
- **C4.** The §3 contract assertions (zero combos, empty fallbacks, no disabled provider)
  are re-checked before dispatch, not inherited from this memo (§6.5).
- **C5.** `routeKind: "default-provider"` in the attribution log is treated as an
  **alarm**, not a normal outcome — it means the router did not recognize the target.
- **C6.** Provider roster stays `openai`-only, or C1's catalog check is re-derived. Adding
  a provider invalidates the §6.1 contingency analysis.
- **C7.** No Anthropic subscription credential is routed. Non-negotiable per ADR-0003;
  independent of this canary's outcome.
- **C8.** The gateway stays bound to loopback. Anything reaching port 10100 can spend the
  operator's Codex quota without presenting a credential (§5.6).

**What this does not qualify.** Subscription passthrough (prohibited, not tested). The
memo's isolated-install path (not exercised). Any provider other than `openai`. Any
non-`/v1/messages` surface beyond the `count_tokens` liveness check. Restart durability
(§6.6). And per the standing boundary: **it authorizes nothing.** It is evidence a
conductor may cite when constructing a `RuntimeAssignment`, and every outward effect still
requires its own explicit authorization.

---

## 8. Reproduction

- Attribution capture: `/tmp/ocx-canary-logs/ocx.jsonl` (218 lines; canary requests are
  the 14 lines from watermark 202, `requestId` prefix `ocx-msil`). Ephemeral — not
  committed.
- Canary `requestId`s: `…-65` (A), `…-66`/`…-67` (per-request), `…-68`/`…-69`/`…-6a`/`…-6c`/`…-6d`
  (dead routes), `…-6b` (explicit-provider control), `…-6e` (streaming), `…-6f` (bearer
  no-op), `…-6g`/`…-6h`/`…-6i` (concurrent), `…-6j`/`…-6k`/`…-6l` (effort), `…-6m` (roster
  alias).
- Gateway: opencodex 2.10.2, PID 2474885, port 10100, config `~/.opencodex/config.json`.
- Background observe process was terminated at teardown. No credential value appears in
  this memo; the §5.6 bearer is a literal placeholder string, not a redaction of one.
