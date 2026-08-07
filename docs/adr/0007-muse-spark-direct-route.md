# ADR-0007 — Meta's Muse Spark is admitted as a direct, non-gateway provider route, qualified as a route but placed in no tier

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Relates to:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md`
  (Decision item 2 is the carve-out this route sits inside),
  `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`
  (the gateway route this one is deliberately *not* modeled on),
  `docs/research/2026-08-07-muse-spark-qualification.md` (the executed evidence
  and its eight binding conditions),
  `skills/model-tier-rightsizing/references/model-routing-calibration.md`

## Context

ADR-0003 rejected subscription-passthrough-for-cost on authorization grounds and,
in the same Decision, preserved a second legitimate purpose in item 2: reaching
**non-Anthropic models via each provider's own API credential** "sits fully
within the supported authentication model and is not gated by this ADR."
ADR-0005 then took that carve-out and built it on a gateway — opencodex holding
Codex OAuth, with Claude Code pointed at a localhost proxy.

Meta's Muse Spark changes the shape of the available options, and the change was
resolved firsthand rather than assumed. **`api.meta.ai` serves
`POST /v1/messages` natively**, in Anthropic wire format, authenticating with
Meta's own API key. Verified live: `stop_reason: end_turn`, content
`[redacted_thinking, text]`, correct SSE event sequence, working single and
parallel `tool_use`, and a served `count_tokens`. Both `Authorization: Bearer`
and `x-api-key` are accepted.

That means an operator can point `ANTHROPIC_BASE_URL` straight at Meta with a
Meta credential and get a working Claude Code process **with no gateway in the
path at all**. The question this record answers is whether to admit that shape,
given that this bundle's only existing non-Anthropic route runs through a proxy
whose qualification produced eight conditions largely *about* the proxy.

Two facts make the direct shape materially different from the gateway shape, and
both come from the executed qualification rather than from the vendor:

1. **Fail-closed is the provider's own property here, not a contingency.** The
   canary's sharpest finding (§6.1 there) was that the gateway did not reject
   unknown model strings: they were classified `routeKind: "default-provider"`,
   forwarded verbatim, and refused by whichever upstream happened to be default —
   so safety depended on the provider roster staying as it was. On this route
   every non-catalog ID (`muse-spark-9.9-does-not-exist`, `claude-opus-5`,
   `meta/muse-spark-1.2`, and a case variant of a real ID) is refused **404
   `model_not_found`** by the provider that owns the models. There is no second
   router that could rewrite a target.
2. **Identity observability is strictly worse.** The gateway had an attribution
   log recording `resolvedModel` independently of the caller's requested string —
   which is exactly how the alias echo and the dated-snapshot suppression were
   caught. This route has no attribution log, no provider/model response header,
   and no usage or audit surface (all 404). The response body's `model` field is
   the only identity channel, and it is an **echo of the request**.

So the two routes trade off against each other rather than one dominating: the
direct route removes a whole class of routing hazard and removes a whole class of
observability at the same time. Fact 2 is the load-bearing one for this decision,
because it cannot be fixed by a wrapper — there is no second channel to read.

A third fact shaped the launcher rather than the decision: the vendor documents
`https://api.meta.ai/v1` as the base URL, but an Anthropic-shaped client appends
`/v1/messages` itself, and the resulting `/v1/v1/messages` answers **401 with a
fully valid credential**. Misconfiguration therefore presents as a bad key.

## Considered options

1. **Admit the route directly, with no gateway (chosen).** Point
   `ANTHROPIC_BASE_URL` at `https://api.meta.ai` with Meta's own key, behind a
   fail-closed launcher. Cleanest authorization story, fewest moving parts, no
   shared-config side effects — and it accepts the weaker identity channel as a
   recorded limitation.
2. **Route Muse Spark through the existing opencodex gateway.** Rejected. It
   would buy back the attribution log, which is a real gain, but at a cost that
   is not worth it here: it reintroduces the `default-provider` fallthrough
   hazard that the direct route structurally does not have (canary §6.1), makes
   this route's safety contingent on the gateway's provider roster (canary C6),
   adds a supervised process whose restart durability is already a known gap
   (canary §6.6), and inherits the side effect that `ocx ensure`/`start` rewrite
   shared `~/.codex` state. It also adds a second party to a credential path
   that does not need one. Trading a structural guarantee for a log is the wrong
   direction when the provider already refuses unknown IDs.
3. **Do nothing; keep Codex-OAuth and Bedrock only.** Rejected as leaving a
   working, authorization-clean route unusable for no benefit. The operator asked
   for it, the evidence supports admitting it as a *route*, and declining would
   also mean not recording the hazards found — which are the durable value here
   regardless of whether anyone dispatches to it.
4. **Admit the route AND place it in a capability tier.** Rejected on evidence
   grounds; see Decision item 4. This was the tempting option and the one the
   evidence does not support.

## Decision

1. **The Muse Spark direct route is admitted, and it is ADR-0003-clean.** It is a
   non-Anthropic model authenticating with its own provider-issued credential —
   ADR-0003 Decision item 2 verbatim. Nothing about it involves an Anthropic
   subscription credential, so the prohibition in item 1 is not engaged and is
   not relaxed. The distinction is not that no gateway is present; it is *whose
   credential authenticates the request*. A direct route with a replayed
   subscription token would be just as prohibited as a gateway one.
2. **`scripts/muse-claude.sh` is the only supported entry point**, with
   subcommands `launch`, `status`, and `probe` (wired as the `muse:launch`,
   `muse:status`, `muse:probe` mise tasks). It runs Claude Code under an isolated
   `CLAUDE_CONFIG_DIR` beneath `XDG_STATE_HOME`, so the operator's native
   `~/.claude` state is never mutated — the same isolation the ocx launcher
   established, for the same reason. Unlike that launcher it supervises nothing,
   because there is no local process to supervise.
3. **The launcher verifies the route live and fails closed, and each check exists
   for a failure observed in the qualification.** `launch` runs a catalog probe
   **then** a tiny real completion before exec'ing Claude Code:
   - The catalog probe is the admission check and it also localizes a base-URL
     error, because an unknown path answers 401 exactly like a bad credential. A
     401 is reported with **both** causes named, so an operator is never sent to
     rotate a key that was fine.
   - The completion probe asserts **non-empty text**, not HTTP 200, because
     reasoning tokens are charged against the output budget before any visible
     text: at `max_tokens` 32 and 128 the route returns **HTTP 200 with an empty
     content array**. A 200-only check would pass against a route that cannot
     emit a word. Verified by shrinking the probe budget in a scratch copy and
     confirming the named refusal.
   - Catalog membership is matched whole, so `muse-spark-1.2` is not satisfied by
     `muse-spark-1.2-contributor`.
4. **The route is qualified as a route and placed in NO tier.** Per
   `docs/research/2026-08-07-muse-spark-qualification.md`, every probe was a
   one-word smoke prompt or a two-city tool call. Under the calibration's own
   ladders the route sits at `route-probed` and never `role-qualified`; transport
   and admission are `exact-route-live` while every capability claim is
   `vendor-hypothesis`; documented positioning is `mined`, which may propose a
   reconsideration and can never raise a rung or fill a scale-setter slot. **No
   eligible pair is amended and no phase, blast-radius, or roadmap row is
   changed.** The route may be selected only for work whose failure a complete
   deterministic check catches, as a recorded experiment. It is ineligible for
   frontier and judgment-workhorse work, and `xhigh` is its ceiling because the
   provider's own effort vocabulary (`none`, `minimal`, `low`, `medium`, `high`,
   `xhigh`, enumerated by the provider in a 400) contains **no `max`**.
   Promotion requires the A0–A6 ladder with paired isolation and utility arms and
   a real task-fit comparison, not a repeat of these smoke probes.
5. **No static model or effort pin is added to any provider-neutral role.** The
   model slots in the launcher configure one operator-launched client process;
   they are not a role definition. Provider-neutral roles keep no model pin, and
   a conductor still supplies a resolved `RuntimeAssignment` before any dispatch.
6. **Identity and effort evidence rules for this route are recorded in the
   calibration, and they are narrower than the gateway's.** A
   `RuntimeAssignment` here sets `observed_identity_source:
   adapter_response_readback` and carries **neither** gateway field, because
   there is no attribution log to point into and no served catalog digest
   requirement that a second router made necessary. `model_identity_basis` must
   record that identity rests on an exact-ID request, a whole-match catalog
   pre-check, and a matching response echo — **not** on an independent
   observation channel, because none exists. `effort_readback_status` is
   `unavailable`: the response echoes the requested `reasoning.effort` back
   verbatim, which is the requested value returning and must never be bound as
   readback.
7. **The credential never enters this repository, and the launcher enforces
   that.** It is read from `MODEL_API_KEY`, or a file named by
   `MUSE_API_KEY_FILE`, or `~/.muse/api-key`. A credential path that resolves
   **inside the repository is refused outright**, so a key cannot be committed by
   way of this launcher. It is passed to `curl` through a config file on stdin
   rather than argv, because argv is world-readable via `ps`, and a credential
   supplied as a command-line argument is refused (exit 3). No subcommand ever
   prints the value.
8. **The same subscription boundary as the ocx launcher applies, for the same
   reason.** Pointing `ANTHROPIC_BASE_URL` at a third party while a subscription
   credential is in scope is the shape ADR-0003 prohibits, so the launcher
   scrubs every `ANTHROPIC*`/`CLAUDE*` variable from the child environment (a
   prefix scrub, because routing flags like `CLAUDE_CODE_USE_BEDROCK` and
   per-tier model slots are leak paths too) and refuses with exit 3 when a
   subscription credential would still be reachable: an `sk-ant-oat*` token in
   the environment, a `claudeAiOauth` entry in the isolated dir, an
   `oauthAccount` in the sibling `.claude.json`, or a `Claude Code-credentials`
   keychain item on macOS. An `sk-ant-api*` developer key is a different
   credential class and is scrubbed rather than refused.

## Consequences

- Positive: an authorization-clean non-Anthropic route is available with **no
  gateway, no supervised process, no port, and no shared-config side effect**.
  Compared with the ocx path this removes the `default-provider` fallthrough
  hazard, the loopback-admission exposure (anything reaching the port could spend
  the operator's quota), the restart-durability gap, and the `~/.codex` rewrite.
- Positive: fail-closed behavior is the provider's own property rather than a
  contingency on a provider roster, so the canary's C6-style condition ("provider
  roster stays as-is, or re-derive the catalog check") has no analogue here.
- Positive: the 1M context claim was **measured rather than accepted**, and
  measuring it was free because oversized requests are refused at 400. The window
  is exactly 1,048,576 tokens and is a **shared** input+output budget:
  `count_tokens + max_output_tokens = 2^20` exactly, confirmed at two very
  different input sizes and predictive in both directions. That is a stronger
  statement than the vendor's, and it corrects the natural misreading that 1M is
  an input allowance with output on top.
- Negative: **identity observability is weaker than the gateway route's, and this
  cannot be wrapped away.** The response body is the only channel and it echoes
  the request, so a match is consistent both with a truthful report and with a
  server that echoes without checking; these probes cannot separate those. The
  mitigation is structural (no substitution mechanism exists: non-catalog IDs are
  refused 404 and there is no intermediate router) and is recorded as an argument
  from absence, not as a positive identity observation. Anyone who needs
  independent per-request attribution should use the gateway route instead and
  accept its hazards — that is the actual trade.
- Negative: a too-small output budget returns **HTTP 200 with empty output**,
  because reasoning tokens are billed before visible text. This is a live trap for
  any tooling that health-checks on status code alone, and reasoning content is
  never readable (empty `summary` on `/v1/responses`, `redacted_thinking` on
  `/v1/messages`, and the SSE stream omits the thinking block entirely while still
  billing for it). Enforced in the launcher; documented in the calibration.
- Negative: effective effort readback is unavailable, and the echoed
  `reasoning.effort` field is a *more* dangerous shape than the gateway's honest
  silence, because it looks like a readback field. Recorded as `unavailable` with
  the requested value kept as requested, per AGENTS.md's permitted honest gap.
- Negative: an oversized request returns **429** (`rate_limit_exceeded`,
  "reserved capacity") rather than 400, so a client with retry-on-429 would retry
  a request that can never succeed. A 429 on this route is not assumed to be
  throttling until request size is ruled out.
- Negative: the two tiers differ only in observed quota
  (`muse-spark-1.2-contributor` at 100 requests / 3M tokens against 3000 / 4M for
  the others), and the 100-request contributor ceiling is exhaustible in one
  fan-out wave. No output-quality difference between tiers was observed, and none
  was looked for.
- Negative: the credential used for qualification was temporary and the operator
  stated it will be rotated, so the executed evidence is not a durability claim
  about any particular key.
- **Confirmation:** `bash -n scripts/muse-claude.sh` parses;
  `uv run --python 3.12.11 --script scripts/validate_bundle.py` reports 0 errors;
  25 tests in `tests/test_muse_claude.py` pass, none of which requires the
  credential (all run against a stub `curl` and a placeholder key). The launcher
  was exercised live: `probe` and `status` both verify catalog plus completion and
  exit 0; a base URL carrying the vendor-documented `/v1` suffix fails closed and
  names the base-URL cause; a non-catalog model fails closed on the catalog check;
  a 32-token probe budget fails closed with the empty-output reason; a credential
  path inside the repository is refused; a credential on the command line is
  refused (exit 3); a synthetic `sk-ant-oat*` fixture refuses before any network
  call; and no output from any subcommand contains the credential value. A test
  asserts the child environment is scrubbed and repointed — `CLAUDE_CODE_USE_BEDROCK`
  and an inherited `api.anthropic.com` base URL do not survive, and the Meta
  endpoint and model slots do.

## Reversal condition

Reopened by either direction of measured change. **Toward stricter:** if Meta
introduces a routing layer between caller and model — a `default-provider`-style
fallthrough, a silent alias, or any substitution of a requested catalog ID — then
Decision item 1's structural argument in §6.2 of the qualification memo collapses,
and identity evidence on this route must be re-derived before any further use.
**Toward looser:** if Meta publishes a per-request provider/model attribution
channel (a response header or an audit surface), the identity limitation in
Consequences is removed and the calibration's evidence rules for this route should
be re-tightened to bind it. Independently: if `muse-spark-1.2` or
`muse-spark-1.1` leaves the served catalog, or the effort vocabulary or window
arithmetic changes, the qualification's rerun triggers fire. And if ADR-0003's own
reversal condition is ever met, that record — not this one — governs, and this
launcher's refusals must be revisited deliberately in a new record rather than
quietly relaxed.

Any attempt to place this route in a capability tier reopens this record rather
than amending the calibration in place: Decision item 4 is an evidence claim, and
promoting it requires the A0–A6 ladder and a real task-fit comparison.

This record is evidence for a conductor to cite; it authorizes no provider login,
credential configuration, model-routing claim, dispatch, push, publication, merge,
deployment, or other outward effect on its own.
