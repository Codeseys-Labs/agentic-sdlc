# ADR-0014 — the gateway launch preserves the operator's own Claude login, and the split plane is retired

- **Status:** accepted
- **Date:** 2026-08-11
- **Deciders:** operator (authorized decision), agent (evidence and implementation)
- **Supersedes:** `docs/adr/0013-explicit-unsupported-claude-subscription-passthrough.md` (retired;
  the route it created is deleted)
- **Amends:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md` (its subscription-routing
  prohibition no longer governs), `docs/adr/0010-gateway-plane-inherits-inert-session-data-and-the-statusline-stanza.md`
  (now scoped to `scripts/muse-claude.sh` only), `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`
  (there is no longer a split plane to route into)

## Context

ADR-0003 prohibited routing Anthropic subscription OAuth through the gateway, and everything
downstream was built to enforce that structurally: `launch` isolated `CLAUDE_CONFIG_DIR`, scrubbed
every `ANTHROPIC_*`/`CLAUDE_*`/`AWS_*` variable out of the child environment, and refused (exit 3)
whenever a subscription credential remained reachable. ADR-0010 then had to reintroduce inert
session data by symlink so the isolated plane was not blank, and ADR-0013 added a separately named
`claude-subscription` escape hatch for operators who wanted the native login anyway.

That structure cost three code paths and produced a launcher that could not do the one thing the
gateway is actually good at: serve BOTH catalogs in one session. It also rested on a reading of
Anthropic's policy that turned out to be wrong.

**Anthropic documents this exact configuration.** `code.claude.com/docs/en/llm-gateway`, under
"Subscriptions and gateways": "Setting only that variable, without a gateway credential, doesn't
replace the subscription. Requests still route through the gateway, but a saved claude.ai login
remains the active credential, so its usage limits and billing apply. Gateways that pass this
traffic on to Anthropic must forward the OAuth capability in `anthropic-beta`." The same page
scopes it broadly: "Any gateway that exposes a supported API format works. Anthropic doesn't
endorse, maintain, or audit third-party gateway products".

**The prohibition that exists is narrower than ADR-0003 assumed.**
`code.claude.com/docs/en/legal-and-compliance`: "Anthropic does not permit third-party developers
to offer Claude.ai login or to route requests through Free, Pro, or Max plan credentials **on
behalf of their users**." That governs a developer shipping a product on other people's
subscriptions. It does not describe an operator routing their own credential through their own
local hop, which the gateway page then describes approvingly.

**opencodex already implements the documented shape.** Verified in the pinned 2.11.1 source:
`server/claude-messages.ts:105-111` takes the native branch only when `nativePassthrough !== false`,
the model matches `/^(claude|anthropic)/i`, the inbound bearer starts with `sk-ant-`, and
`resolveInboundModel(model) === model`; the forward at `:300-342` strips only hop-by-hop headers
plus `host`/`content-length`/`accept-encoding`/`x-opencodex-api-key`/`origin`, leaving
`anthropic-beta`, `authorization`, and the body untouched. `cli/claude.ts:133` injects the proxy
marker token ONLY when `markerMode === "proxy"`, and `:115` injects an admission key only when one
is configured — so with a detected login, neither fires and Claude Code keeps its own OAuth.
`cli/claude.ts:286` pre-writes the gateway model cache, which is what puts the routed ids in the
`/model` picker at all, because Claude Code only refreshes that cache while holding a credential.

**Measured, not assumed.** In a clean container with a deliberately fake `sk-ant-oat01-…` token,
the same request produced `"OAuth access token is invalid."` (Anthropic's own error vocabulary,
i.e. the request reached `api.anthropic.com`) with passthrough at its default, and
`"OpenAI account pool has no usable account credential"` (opencodex's own error, i.e. rerouted to
the default provider) with `nativePassthrough: false`. Two errors from two different systems.
That container had no `~/.opencodex/config.json`, no `anthropic` provider, and no `ocx account
login`, which establishes that passthrough requires no credential onboarded into opencodex. See
`docs/research/ocx-passthrough-probe/RESULTS.md`.

## Decision

1. **`launch` and `launch-ultracode` use the operator's own `~/.claude`.** No isolated config dir,
   no environment scrub, no subscription refusals. Claude Code presents its existing login to the
   gateway; native claude models pass through verbatim on the operator's subscription and gateway
   models route to their own providers, in one session.

2. **Delete the split-plane machinery.** Removed: `scrub_anthropic_env`,
   `subscription_shaped_env`, `assert_isolated_dir_has_no_subscription`,
   `assert_no_keychain_subscription`, `assert_proxy_marker_mode`, `inherit_session_state_if_available`,
   `require_session_helper`, the `isolated_config_dir` and `session_inheritance` variables, and the
   `session status` / `session adopt` verbs. `assets/claude/session-inheritance.sh` REMAINS: it is
   still used by `scripts/muse-claude.sh`, which keeps its own plane and its own tests.

3. **Delete the `claude-subscription` route.** ADR-0013's escape hatch existed because the ordinary
   route refused what it allowed. The ordinary route no longer refuses it, so a second, narrower,
   single-native-model spelling is dead weight. `ocx:claude-subscription` is removed from
   `mise.toml` and from the validator's task inventory.

4. **Keep route-integrity checks, for billing honesty rather than prohibition.** `launch` refuses
   (exit 3) when the route would not actually be used:
   - a provider-routing key — `CLAUDE_CODE_USE_BEDROCK`/`USE_VERTEX`/`USE_FOUNDRY`,
     `AWS_BEARER_TOKEN_BEDROCK`, `ANTHROPIC_BEDROCK_BASE_URL`, `ANTHROPIC_VERTEX_BASE_URL` —
     exported OR present in the global `settings.json` `env` block, or an `apiKeyHelper` there.
     Under Bedrock the client consults `ANTHROPIC_BEDROCK_BASE_URL` and never
     `ANTHROPIC_BASE_URL`, so the gateway is bypassed while the wrapper prints a gateway banner.
     Measured on a real host on 2026-08-10: the request never reached a local capture listener and
     was still answered.
   - an `sk-ant-api*` Console key in `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`. It satisfies
     opencodex's bare `sk-ant-` gate, so it takes the SAME native branch and bills API credits
     while looking like subscription traffic. The prefix is the only distinguishing signal.
   An `sk-ant-oat*` token is explicitly ACCEPTED — carrying it is the point.

5. **Names and prefixes only.** No check reads, prints, copies, or persists a credential value.

6. **State the residual limits plainly rather than claiming approval.** Anthropic "doesn't support
   routing Claude Code to non-Claude models through any gateway", so the routed half is
   permitted-but-unsupported: no Anthropic credential is used for those turns. Enforcement history
   through 2026 has been unilateral and has reversed direction more than once. This record is
   evidence, not authorization, and it grants no authority for any outward effect.

### 2026-08-13 amendment — selected settings are the third route-integrity channel

Claude Code 2.1.229 was measured with two loopback listeners: the process environment named the
local gateway listener while an explicit inline `--settings` object set
`env.ANTHROPIC_BASE_URL` to the other listener. Every request reached the selected-settings
listener. Decision item 4 therefore has a third current check: ordinary launch validates every
`--settings <file-or-json>` and `--settings=<file-or-json>` occurrence before gateway startup. The
value must be one JSON object or a readable file containing one, and it must not contain the same
provider-routing, base-URL, helper, or Console-key blockers above. Accepted argv remains unchanged;
settings bytes and paths are inspected but never printed, copied, or persisted. A later literal
`--` ends Claude's option parsing and therefore the scan, as a separate two-listener probe confirmed.

### 2026-08-13 amendment — distribution root and caller workspace are separate

An installed `ccodex` resolves this launcher from the agentic-sdlc distribution checkout. The old
`mise -C <distribution> exec -- ocx claude` also changed the child working directory, so a launch
invoked from another repository started Claude Code in the distribution checkout instead. Using a
second mise working-directory option was tested and rejected: it made mise resolve configuration in
the caller workspace, where the distribution's OpenCodex pin was absent. Operator-tools installation
now resolves the reviewed `ocx`, `jq`, and `uv` pins once, writes their absolute paths into `ccodex`, and
installed launch invokes the bound `ocx` directly. That keeps the distribution identity separate
from Claude Code's physical current directory without depending on ambient PATH or daily mise
activation. A reviewed toolchain change requires a separate explicit operator-tools reinstall;
ordinary launch never silently resolves, installs, or updates tools. Direct source-checkout use keeps
a repository-scoped mise fallback. This applies equally to ordinary and Ultracode launches and
preserves argument boundaries, global `~/.claude` use, gateway supervision, and route-integrity
checks.

## Consequences

- Positive: one launch route instead of three, and it does what the gateway is for. Roughly 370
  lines of scrub/isolation/refusal machinery and 35 tests of removed behavior are gone.
- Positive: the three route-integrity channels catch failures that otherwise print a gateway
  banner while bypassing the gateway or charging Console API credits.
- Negative: `ocx claude` writes its `ocx-*.md` roster agents and gateway model cache into the
  operator's global `~/.claude`. That is a real side effect the isolated plane used to prevent; it
  is now accepted deliberately, and the model-cache write is load-bearing for the picker.
- Negative: the credential-free-by-construction property is gone. Nothing structurally prevents a
  future stored credential from reaching the gateway; the prefix check is the only guard, and it
  distinguishes classes of `sk-ant-` token by prefix rather than by proof.
- Negative: ADR-0010's env-policy classification no longer applies to this launcher. Its helper is
  exercised only through `scripts/muse-claude.sh` and `tests/test_muse_claude.py` now, so a
  regression in the classes this launcher used to assert would surface there or not at all.
- Testing: the launcher harness writes one exact-line OCX trace and asserts both positive routing
  and pre-gateway refusal against its contents, so an appended argument cannot satisfy a substring
  assertion and an unwritten side log cannot make a refusal pass vacuously. The selected-settings
  cases cover both syntaxes, inline and file documents, every bypass class, invalid/uncheckable
  values, redaction, repeated occurrences, and Claude's later literal `--` boundary. Operator-tools
  tests remove ambient mise/ocx, inject hostile PATH/override values, and prove the bound OCX, jq,
  and uv paths run from the caller workspace or fail with named refresh guidance when stale.

## Reversal condition

Revisit if Anthropic changes the gateway documentation to exclude subscription logins, narrows
"any gateway", withdraws the base-URL-without-credential behavior, or begins rejecting verbatim
relays. Re-opening this does not automatically restore the isolated plane: a new decision must
state the revised boundary.
