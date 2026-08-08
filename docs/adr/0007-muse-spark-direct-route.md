# ADR-0007 — Meta's Muse Spark is admitted on two routes: as an opencodex provider (primary) and as a direct gateway-free route (fallback), qualified as a route and placed in no tier

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Filename note:** this record is `0007-muse-spark-direct-route.md`, which reflects
  an earlier and narrower decision (direct route only). The filename is retained so
  existing references keep resolving; the title and Decision below are authoritative.
  Renaming is a separate mechanical change, not a decision.
- **Relates to:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md`
  (Decision item 2 is the carve-out both routes sit inside),
  `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`
  (the gateway this record's primary path now uses),
  `docs/research/2026-08-07-muse-spark-qualification.md` (the executed evidence:
  §1–§7 direct with conditions M1–M8, §8 gateway with conditions G1–G7),
  `docs/research/2026-08-07-opencodex-qualification-canary.md` (conditions C1–C8,
  which the gateway route inherits),
  `skills/model-tier-rightsizing/references/model-routing-calibration.md`

## Context

ADR-0003 rejected subscription-passthrough-for-cost on authorization grounds and,
in the same Decision, preserved a second legitimate purpose in item 2: reaching
**non-Anthropic models via each provider's own API credential** "sits fully
within the supported authentication model and is not gated by this ADR."
ADR-0005 then took that carve-out and built it on a gateway — opencodex holding
Codex OAuth, with Claude Code pointed at a localhost proxy.

Meta's Muse Spark can be reached **either** way, and both were executed rather than
assumed.

**Direct.** `api.meta.ai` serves `POST /v1/messages` natively, in Anthropic wire
format, authenticating with Meta's own API key. Verified live: `stop_reason:
end_turn`, content `[redacted_thinking, text]`, correct SSE event sequence,
working single and parallel `tool_use`, and a served `count_tokens`. Both
`Authorization: Bearer` and `x-api-key` are accepted. So an operator can point
`ANTHROPIC_BASE_URL` straight at Meta and get a working Claude Code process with
no gateway in the path at all.

**Through the gateway.** Muse Spark can also be registered as an ordinary
opencodex provider — `ocx provider add muse --adapter openai-responses --base-url
https://api.meta.ai/v1 --default-model muse-spark-1.2` — after which it is one
more provider in the existing gateway, selectable per request, and covered by the
gateway's own attribution log and the existing supervised launcher. Verified live:
all three catalog IDs resolve independently with `routeKind: "explicit-provider"`,
and the log records `provider: "muse"` with a `resolvedModel` recorded separately
from the caller's requested string.

**An earlier draft of this record decided only the direct route and rejected the
gateway one.** That was wrong on the evidence, and the correction is the substance
of this revision. The rejection rested on the gateway's `default-provider`
fallthrough hazard and its restart-durability gap — both real — while
undervaluing the one thing the gateway has that the direct route structurally
cannot have. The decisive facts, all from the executed qualification:

1. **Identity observability differs in kind, and only the gateway route can satisfy
   the canary's C2.** The direct route has no attribution log, no provider/model
   response header, and no usage or audit surface (all 404). The response body's
   `model` field is the only identity channel and it is an **echo of the request**,
   so a match is consistent both with a truthful report and with a server that
   echoes without checking; these probes cannot separate those (qualification §6.2).
   The gateway route has a genuinely independent channel, and it **proved** its
   independence: for `muse/muse-spark-1.2` the body echoes
   `muse/muse-spark-1.2` while the log records `resolvedModel: muse-spark-1.2`
   (§8.2). The disagreement is what establishes that the log is a real observation
   rather than a replay of the request. No wrapper can manufacture that channel on
   the direct route — there is nothing to read.
2. **The gateway's hazards are mechanically checkable; the direct route's
   limitation is not.** Registering a provider does **not** make it live: between
   `ocx provider add` and `ocx sync` + a gateway restart, requests naming the new
   provider's model are classified `routeKind: "default-provider"` and attempted
   and billed against the default provider, with the attribution log naming the
   wrong provider (§8.1). Separately and permanently, only the provider's
   *configured default model* resolves when requested bare: `muse-spark-1.1` — a
   real, served ID — requested without the `muse/` prefix is routed to **Codex**
   (§8.2). Both are detectable and both are now detected; §8.4 and Decision item 4
   record how. The direct route's missing channel cannot be repaired at all.
3. **Fail-closed behavior favors the direct route, but narrowly.** On the direct
   route every non-catalog ID — a bogus version, a `claude-*` ID, a `meta/`-prefixed
   form, a case variant — is refused **404 `model_not_found`** by the provider that
   owns the models, with no second router that could rewrite a target (§5.3). On
   the gateway route a `muse/`-prefixed unknown ID is refused 404, but an
   unprefixed one falls through. This is a real advantage for the direct route and
   it is why that route is kept, not why it is preferred: a prefix rule (G2) closes
   the gap, whereas no rule closes the identity gap.

Two configuration facts shaped the launchers rather than the decision, and they
are **opposites**, which is itself a hazard. The vendor documents
`https://api.meta.ai/v1` as the base URL. An Anthropic-shaped client appends
`/v1/messages` itself, so the direct route must use `https://api.meta.ai` **without**
the suffix — the doubled path answers **401 with a fully valid credential**, so
misconfiguration presents as a bad key. The gateway's `openai-responses` adapter
appends only `/responses`, so the provider's `baseUrl` there must **keep** the
`/v1`. Copying either form into the other produces that same misleading 401.

## Considered options

1. **Admit Muse Spark as an opencodex provider as the primary path, and keep the
   direct route as a gateway-free fallback (chosen).** Buys the independent
   attribution channel and per-request selection, reuses the existing supervised
   launcher and its ADR-0003 refusals, and accepts two hazards that are
   mechanically checkable and now checked. Keeps the no-process path available for
   when no gateway is wanted.
2. **Admit the direct route only, and reject the gateway route.** This was the
   earlier decision and it is now rejected. It trades away the only channel that
   can satisfy canary C2 in exchange for avoiding hazards that a status check and a
   prefix rule handle. It also duplicates supervision-free launching effort that
   the ocx wrapper already provides, and it leaves `model_identity_basis`
   permanently unable to rest on an independent observation.
3. **Admit the gateway route only, and delete `scripts/muse-claude.sh`.** Rejected.
   The direct route is real, executed, and has properties the gateway route does
   not: no running process, no port, no sync step, no shared-`~/.codex` mutation,
   no loopback exposure, and uniform 404 refusal of every non-catalog ID. Deleting
   a working authorization-clean route to reduce surface area would remove the
   fallback that covers exactly the case where the gateway is unavailable.
4. **Do nothing; keep Codex-OAuth and Bedrock only.** Rejected as leaving a
   working, authorization-clean route unusable for no benefit. Declining would also
   mean not recording the hazards found — which are the durable value here
   regardless of whether anyone dispatches to these models.
5. **Admit a route AND place it in a capability tier.** Rejected on evidence
   grounds; see Decision item 6. This was the tempting option and the one the
   evidence does not support, on either route.

## Decision

1. **Muse Spark is admitted on two routes, and both are ADR-0003-clean.** Each is a
   non-Anthropic model authenticating with its **own** provider-issued credential —
   ADR-0003 Decision item 2 verbatim. Nothing about either involves an Anthropic
   subscription credential, so the prohibition in item 1 is not engaged and is not
   relaxed. The distinction has never been whether a gateway is present; it is
   *whose credential authenticates the request*. A direct route with a replayed
   subscription token would be just as prohibited as a gateway one, and a gateway
   route with Meta's own key is as clean as a direct one.

2. **The gateway route is the primary path.** Muse Spark is registered as an
   ordinary opencodex provider and reached through the existing gateway and the
   existing `scripts/opencodex-claude.sh` launcher. It is preferred for three
   reasons, in order of weight: it inherits a per-request attribution channel that
   is independently observed and therefore satisfies canary C2 (§8.2), which the
   direct route structurally cannot; it inherits per-request model selection across
   all three catalog IDs alongside the other configured providers; and it inherits
   an already-reviewed supervised launcher with `CLAUDE_CONFIG_DIR` isolation and
   the ADR-0003 refusals, rather than needing a parallel implementation of each.
   It also inherits the gateway's costs, which are accepted rather than dismissed:
   the `~/.codex` rewrite on `ensure`/`start`, the loopback admission exposure
   (anything reaching the port can spend the Meta key without presenting a
   credential — canary C8), and the restart-durability gap that `ocx status` itself
   reports as "AT RISK after restart".

3. **The direct route remains admitted as the gateway-free fallback, and
   `scripts/muse-claude.sh` is kept.** It is the supported path when no gateway is
   wanted or when the gateway is unavailable, because it requires **no running
   process, no port, no sync step, and no shared-config mutation**, and because it
   refuses every non-catalog ID 404 uniformly. Its identity ceiling is recorded
   rather than papered over: anyone who needs independent per-request attribution
   must use the gateway route. `muse-claude.sh`'s header, `probe`, and `status`
   state that it is the fallback and name the primary path.

4. **The sequencing hazard is mechanically guarded, not documented as advice.** A
   provider written to the config file is not in the running gateway's routing
   table, and the gap fails **open** rather than closed (§8.1). Therefore:
   - After any **successful** admitted `provider add|edit|update|remove|set-default`,
     `scripts/opencodex-claude.sh configure` prints a `NOT LIVE YET` notice naming
     both required steps (`ocx sync`, then the wrapper's own `restart`) and stating
     that requests in the interim are billed against the default provider. It is
     printed only on success, because telling an operator to sync a write that did
     not land is a false instruction.
   - `status` compares every **configured** provider against the **running
     gateway's live catalog** (`GET /v1/models`) and reports any that is configured
     but not served as **NOT-LIVE**. The two facts have separate sources — config
     file versus process catalog — which is what makes the state detectable at all.
     The comparison degrades to `unknown` when the gateway is down or `jq`/`curl`
     are missing, never to a verdict. The default provider is never flagged: it
     serves bare IDs and has no `<name>/` prefix to match.
   - Neither `ocx sync` nor the restart is run on the operator's behalf. `sync`
     rewrites shared `~/.codex` state and a restart interrupts in-flight turns, so
     each is a separately authorized operation, not a side effect of a
     configuration edit.

5. **Dispatches on the gateway route are `muse/`-prefixed.** Only the provider's
   configured default model resolves when requested bare; every other Muse ID —
   including a valid served one — falls through to the default provider (§8.2).
   This is condition G2 and it is stricter than the direct route's whole-match
   catalog rule (M1), which it replaces for this route: prefix **and** catalog
   membership.

6. **Both routes are qualified as routes and placed in NO tier.** Per the
   qualification memo, every probe on both routes was a one-word smoke prompt or a
   two-city tool call. Adding a second transport to the same models cannot
   establish task fit. Under the calibration's own ladders both sit at
   `route-probed` and never `role-qualified`; transport and admission are
   `exact-route-live` while every capability claim is `vendor-hypothesis`;
   documented positioning is `mined`, which may propose a reconsideration and can
   never raise a rung or fill a scale-setter slot. **No eligible pair is amended and
   no phase, blast-radius, or roadmap row is changed.** Either route may be selected
   only for work whose failure a complete deterministic check catches, as a recorded
   experiment. Both are ineligible for frontier and judgment-workhorse work, and
   `xhigh` is the ceiling because the provider's own effort vocabulary (`none`,
   `minimal`, `low`, `medium`, `high`, `xhigh`, enumerated by the provider in a 400)
   contains **no `max`**. Promotion requires the A0–A6 ladder with paired isolation
   and utility arms and a real task-fit comparison, not a repeat of these smoke
   probes.

7. **No static model or effort pin is added to any provider-neutral role.** The
   model slots in either launcher configure one operator-launched client process;
   they are not a role definition. Provider-neutral roles keep no model pin, and a
   conductor still supplies a resolved `RuntimeAssignment` before any dispatch.

8. **Identity and effort evidence rules differ per route, and the receipt records
   which route was used.** This is the practical consequence of item 1's two shapes
   and it must not be averaged:
   - **Gateway route:** `resolved_model_id` comes **only** from the attribution
     log's `resolvedModel`, correlated by `requestId`. The response body is
     **inadmissible** because it echoes the caller's `muse/`-prefixed alias (§8.2).
     `observed_identity_source` is the gateway attribution log and the gateway
     fields apply. This is condition G3 and it **supersedes** M2 for this route.
   - **Direct route:** `observed_identity_source` is
     `adapter_response_readback`, carrying **neither** gateway field, because there
     is no attribution log to point into. `model_identity_basis` must record that
     identity rests on an exact-ID request, a whole-match catalog pre-check, and a
     matching response echo — **not** on an independent observation channel,
     because none exists.
   - **Both:** `effort_readback_status` is `unavailable`. On the direct route the
     response echoes the requested `reasoning.effort` verbatim, which is the
     requested value returning and must never be bound as readback. On the gateway
     route `usage.reasoningOutputTokens` is real consumption telemetry but is not a
     value in the policy's effort vocabulary, so it does not satisfy readback
     either.

9. **The credential never enters this repository, on either route.** For the direct
   route the launcher enforces it: the key is read from `MODEL_API_KEY`, a file
   named by `MUSE_API_KEY_FILE`, or `~/.muse/api-key`; a credential path resolving
   **inside the repository is refused outright**; it is passed to `curl` through a
   config file on stdin rather than argv, because argv is world-readable via `ps`;
   and a credential supplied as a command-line argument is refused (exit 3). For the
   gateway route the key is held by opencodex in its own config, and
   `opencodex-claude.sh configure` **warns** when a key is passed as `--api-key` on
   the command line — naming the flag, never the value — and points at the
   stdin-only `ocx account add-key` form. It warns rather than refuses because
   upstream `provider add` offers no stdin or environment alternative for that flag,
   so refusing would block the only non-interactive registration path.

10. **The same subscription boundary applies on both routes, for the same reason.**
    Pointing a client at a third party while a subscription credential is in scope
    is the shape ADR-0003 prohibits, so both launchers scrub every
    `ANTHROPIC*`/`CLAUDE*` variable from the child environment (a prefix scrub,
    because routing flags like `CLAUDE_CODE_USE_BEDROCK` and per-tier model slots
    are leak paths too) and refuse with exit 3 when a subscription credential would
    still be reachable: an `sk-ant-oat*` token in the environment, a `claudeAiOauth`
    entry in the isolated dir, an `oauthAccount` in the sibling `.claude.json`, or a
    `Claude Code-credentials` keychain item on macOS. An `sk-ant-api*` developer key
    is a different credential class and is scrubbed rather than refused.

## Consequences

- Positive: **an authorization-clean non-Anthropic route now exists in a shape whose
  model identity is independently observable.** The gateway route satisfies canary
  C2, which no direct route to this provider can, and it does so with proof rather
  than assertion — the log disagreed with the response body, which is what
  demonstrates the log is not derived from the request (§8.2).
- Positive: Muse Spark is now **one more provider in the existing gateway** rather
  than a competing launcher. It inherits per-request selection across all three
  catalog IDs, the attribution log, `CLAUDE_CONFIG_DIR` isolation, and the
  ADR-0003 refusals from code that was already reviewed, instead of a parallel
  implementation of each.
- Positive: the fallback path remains available with **no gateway, no supervised
  process, no port, and no shared-config side effect**, and on it fail-closed
  behavior is the provider's own property: every non-catalog ID is refused 404 by
  the provider that owns the models, so the canary's C6-style condition has no
  analogue there.
- Positive: the 1M context claim was **measured rather than accepted**, and
  measuring it was free because oversized requests are refused at 400. The window
  is exactly 1,048,576 tokens and is a **shared** input+output budget:
  `count_tokens + max_output_tokens = 2^20` exactly, confirmed at two very
  different input sizes and predictive in both directions. That is a stronger
  statement than the vendor's, and it corrects the natural misreading that 1M is
  an input allowance with output on top.
- Negative: **a configured provider is not a live provider, and the gap fails
  open.** Between `provider add` and `sync` + restart, a dispatch is attempted and
  billed against the default provider while the attribution log names the wrong
  provider — the canary's C1/C5 fail-open reached through a routine successful
  configuration command rather than through a typo. Guarded per Decision item 4,
  which converts a silent failure into a printed instruction and a `NOT-LIVE`
  status line, but not eliminated: the window still exists between the two
  authorized steps.
- Negative: **only the configured default model resolves bare on the gateway
  route**, so a valid served ID like `muse-spark-1.1` requested without the `muse/`
  prefix is routed to Codex. Addressed by the prefix rule (Decision item 5) rather
  than by a mechanism, because the gateway offers none.
- Negative: **the two routes require opposite base-URL forms** —
  `https://api.meta.ai` without `/v1` for the direct route, `https://api.meta.ai/v1`
  with it for the gateway provider — and getting either wrong produces a **401 with
  a fully valid credential**. The failure mode is an operator rotating a good key to
  fix a URL. Recorded in both launchers and in the calibration.
- Negative: **identity observability on the fallback route cannot be wrapped away.**
  The response body is the only channel and it echoes the request. The mitigation is
  structural (non-catalog IDs are refused 404 and there is no intermediate router)
  and is recorded as an argument from absence, not as a positive identity
  observation.
- Negative: `ocx provider add` performs **no adapter validation** — a mistyped
  adapter is stored silently and reported verbatim by every inspection surface,
  producing a provider that looks configured and cannot work. Verified in an
  isolated `OPENCODEX_HOME` so the operator's live config was never touched.
  Condition G7 requires verifying the adapter against a live request rather than
  against `provider add` accepting it.
- Negative: `ocx provider test <provider>` reads liveness, not configuration, so a
  failure means "not live" rather than "not configured". The two must not be
  conflated when diagnosing; recorded as a caveat, not a blocker.
- Negative: a too-small output budget returns **HTTP 200 with empty output** on
  either route, because reasoning tokens are billed before visible text (231 of 243
  output tokens on a one-word answer, confirmed independently through the gateway).
  This is a live trap for any tooling that health-checks on status code alone, and
  reasoning content is never readable. Enforced in the direct launcher; documented
  in the calibration.
- Negative: effective effort readback is unavailable on both routes, and the direct
  route's echoed `reasoning.effort` is a *more* dangerous shape than honest silence
  because it looks like a readback field. Recorded as `unavailable` with the
  requested value kept as requested, per AGENTS.md's permitted honest gap.
- Negative: an oversized request returns **429** (`rate_limit_exceeded`, "reserved
  capacity") rather than 400, so a client with retry-on-429 would retry a request
  that can never succeed. A 429 on these routes is not assumed to be throttling
  until request size is ruled out.
- Negative: the gateway has **no price table for Meta models** and reports
  `"cost":{"kind":"unavailable","reason":"price_unmatched"}`. Honest, but it means
  cost accounting on that route comes from billed `input_tokens`, not from the
  gateway.
- Negative: the two tiers differ only in observed quota
  (`muse-spark-1.2-contributor` at 100 requests / 3M tokens against 3000 / 4M for
  the others), and the 100-request contributor ceiling is exhaustible in one
  fan-out wave. No output-quality difference between tiers was observed, and none
  was looked for.
- Negative: the credential used for qualification was temporary and the operator
  stated it will be rotated, so the executed evidence is not a durability claim
  about any particular key.
- **Confirmation:** `bash -n` parses both `scripts/muse-claude.sh` and
  `scripts/opencodex-claude.sh`; `uv run --python 3.12.11 --script
  scripts/validate_bundle.py` reports 0 errors; 25 tests in
  `tests/test_muse_claude.py` and 27 in `tests/test_opencodex_claude.py` pass, none
  of which requires a credential (all run against stub `curl`/`mise` and placeholder
  keys). The gateway route was exercised live against the running gateway: all three
  catalog IDs return HTTP 200 with real text and `provider: "muse"` in the
  attribution log; the pre-sync fail-open, the bare-ID fall-through, and the
  alias-echo divergence were each reproduced and recorded; `status` reports `ok` for
  the live post-sync state and `NOT-LIVE` for a configured-but-unserved provider in
  test. The direct route was exercised live earlier: `probe` and `status` verify
  catalog plus completion and exit 0; a base URL carrying the vendor-documented
  `/v1` suffix fails closed naming the base-URL cause; a non-catalog model fails
  closed on the catalog check; a 32-token probe budget fails closed with the
  empty-output reason; a credential path inside the repository is refused; a
  credential on the command line is refused (exit 3); a synthetic `sk-ant-oat*`
  fixture refuses before any network call; and no output from any subcommand
  contains a credential value. Writing the sequencing guard also surfaced and fixed
  a pre-existing `pipefail` bug that aborted the whole `status` report whenever the
  gateway was down.

## Amendment — 2026-08-07: the standalone direct route is retired as a COMMAND SURFACE; Muse Spark ships as a gateway provider only

**Operator decision, stated explicitly:** "because muse is also a provider it shouldn't have a
separate command entry it should just show up as options available through ccodex command in
configuration or even claude-code model selection usage."

This amends Decision item 3 and narrows item 2. **Nothing in the qualification evidence changes**,
and neither does the tier verdict: Muse Spark remains route-probed and tier-UNPROVEN. What changes
is the shipped shape.

**The enabling fact, verified against the running gateway on 2026-08-07.** `GET /v1/models` on the
live proxy returns **one flat catalog of ten ids** — `gpt-5.6-sol`, `gpt-5.6-terra`,
`gpt-5.6-luna`, `gpt-5.5`, `gpt-5.4`, `gpt-5.4-mini`, `gpt-5.3-codex-spark`,
`muse/muse-spark-1.1`, `muse/muse-spark-1.2`, `muse/muse-spark-1.2-contributor`. Muse models are
ordinary namespaced entries in the same catalog as the gpt ones. A session launched through the
gateway therefore selects a muse model exactly as it selects a gpt one, per request or through the
`/model` picker, with no muse-specific launcher, task, or code path.

**What was verified versus inferred.** Verified: the ten-entry catalog above, read directly from
the running gateway; that `ocx claude` sets `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` with
"user wins" semantics, read from the installed package's `src/cli/claude.ts` (line 143); and that
`ocx models list` reports the **configured** models rather than the live catalog, which is why the
dispatcher's `models` route reads `/v1/models` instead. Inferred, not verified: that Claude Code's
`/model` picker renders those ten entries in a real session — asserting that would require
launching a live session against the gateway, which was out of scope. The catalog the launched
process would read is confirmed; its rendering is not.

**Decision.**

1. **Muse Spark is a provider, not a plane.** The `muse:launch`/`muse:status`/`muse:probe` tasks
   are removed. There is one plane (the gateway) with N providers and M models, reached by one
   dispatcher, rather than one dispatcher per provider. Muse is a row in a provider list.

2. **The standalone direct route is retired as a command surface and preserved as PROSE.** The
   gateway-free recipe still works and still needs no running process, no port, and no sync step,
   so it is kept as a documented fallback recipe in the qualification memo rather than as a
   shipped command. Item 3's *technical* claims stand; only its "and `scripts/muse-claude.sh` is
   kept" clause is retired.

3. **The credential and boundary logic is harvested, not lost.** The retired launcher's
   in-repository credential-path refusal moved into `scripts/opencodex-claude.sh`'s configure
   route, where it now covers any path argument rather than only that launcher's key file. The
   ADR-0003 subscription refusal, the environment scrub, and the catalog-membership admission
   check already existed on the gateway path or were strengthened there.

4. **Adding a provider stays the documented, unspecial-cased path.** `ccodex configure provider
   add muse ...` flows through the existing reviewed allowlist and the `NOT LIVE YET` sequencing
   guard from item 4 above, with muse as the worked example. Nothing about muse is hardcoded.

**Consequence.** A reader who cites item 3 as authority for a shipped muse launcher is citing a
retired clause. The evidence in §1–§7 remains the dated record of what the direct route *does*;
it is no longer a record of what this bundle *ships*.

## Reversal condition

Reopened by either direction of measured change, and the two routes have different
triggers.

**Gateway route.** If the `default-provider` fallthrough is fixed upstream so that
an unprefixed or not-yet-live provider's model is **refused** rather than
re-routed, Decision item 5's prefix rule and item 4's guard become belt-and-braces
and should be re-derived rather than kept by inertia. Conversely, if the
attribution log's independence stops being observable — if the log begins echoing
the caller's alias, or `resolvedModel` disappears — then Decision item 2's primary
reason collapses and the two routes' ordering must be re-decided, not silently
retained. If the restart-durability gap (`ocx status`: "AT RISK after restart")
worsens such that a restart drops the provider config, item 4's window becomes
routine rather than exceptional and the primary path must be reconsidered.

**Direct route.** **Toward stricter:** if Meta introduces a routing layer between
caller and model — a `default-provider`-style fallthrough, a silent alias, or any
substitution of a requested catalog ID — then the structural argument in §6.2 of
the qualification memo collapses, and identity evidence on that route must be
re-derived before any further use. **Toward looser:** if Meta publishes a
per-request provider/model attribution channel (a response header or an audit
surface), the identity limitation is removed, the calibration's evidence rules for
that route should be re-tightened to bind it, and Decision item 2's ordering
becomes an open question again rather than a settled one.

**Both.** If `muse-spark-1.2` or `muse-spark-1.1` leaves the served catalog, or the
effort vocabulary or window arithmetic changes, the qualification's rerun triggers
fire. And if ADR-0003's own reversal condition is ever met, that record — not this
one — governs, and both launchers' refusals must be revisited deliberately in a new
record rather than quietly relaxed.

Any attempt to place either route in a capability tier reopens this record rather
than amending the calibration in place: Decision item 6 is an evidence claim, and
promoting it requires the A0–A6 ladder and a real task-fit comparison.

This record is evidence for a conductor to cite; it authorizes no provider login,
credential configuration, model-routing claim, dispatch, push, publication, merge,
deployment, or other outward effect on its own.
