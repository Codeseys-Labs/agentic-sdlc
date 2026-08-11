# ADR-0013 — explicit unsupported Claude subscription passthrough is a bounded operator escape hatch

- **Status:** superseded by ADR-0014
- **Date:** 2026-08-10
- **Deciders:** operator (authorized implementation), agent (evidence and implementation)
- **Relates to:** `docs/adr/0003-gateway-stance-downgraded-to-optional.md`,
  `docs/adr/0005-opencodex-installed-by-default-for-split-plane-routing.md`

## Context

Anthropic's published legal-and-compliance guidance restricts third-party routing
through Free, Pro, and Max subscription credentials. The technical mechanism can
work: native Claude Code retains its existing login when it is pointed at a local
gateway without an API/admission credential. That mechanism does not create
provider authorization, a supported entitlement path, or protection from account
action.

The supported split plane remains `ccodex launch` and `ccodex ultracode`, which
use an isolated Claude configuration and refuse subscription OAuth. Those ordinary
routes may supervise OpenCodex with `ocx ensure` and `ocx restart`; upstream lifecycle
commands can mutate shared `~/.codex` state.

An operator nevertheless requested a conspicuous, explicitly invoked route for
attaching a native Claude Code login to OpenCodex's native Anthropic passthrough.
It must not make that use look normal, provider-approved, or equivalent to the
ordinary split plane. It must also avoid handling OAuth values or stores.

OpenCodex 2.11.1 was inspected for the resulting constraints. `ocx claude` can
inject `ANTHROPIC_AUTH_TOKEN` when an admission key exists, so it cannot be used.
Its inbound resolver applies aliases, desktop aliases, exact `modelMap` entries,
and date-stripped `modelMap` entries before native passthrough. Its masked Claude
status does not expose `nativePassthrough`; pinned source documents that setting as
default-enabled unless explicitly false. `ocx config get` distinguishes an absent
path from other failures with `config path not found: <path>`.

## Decision

1. **Expose only a separately named route.** The operator spelling is
   `ccodex claude-subscription`; it maps to the canonical launcher verb
   `launch-claude-subscription`. Its help must prominently say **unsupported**,
   **account-risk**, and **not provider-approved**. Its invocation is informed
   operator choice only, never authorization.

2. **Use native Claude Code directly.** After all checks pass, the route invokes
   plain `claude` with the normal/global Claude configuration and exactly one
   wrapper-set gateway location:
   `ANTHROPIC_BASE_URL=http://127.0.0.1:<verified-port>`. It never calls
   `ocx claude`, sets an admission key, sets `ANTHROPIC_AUTH_TOKEN`, sets
   `ANTHROPIC_API_KEY`, reads OAuth values, reads credential stores, copies
   credentials, or persists credentials.

3. **Refuse ambiguous parent controls before any gateway interaction.** The
   route enumerates exported variable names only and never expands their values.
   It refuses any exported `ANTHROPIC_*`, `AWS_*`, or `CLAUDE_*` name, plus
   `FALLBACK_FOR_ALL_PRIMARY_MODELS` and `NODE_TLS_REJECT_UNAUTHORIZED`. This
   occurs before resolving OpenCodex, asking for masked status, or probing health.

4. **Require an explicit unmapped native model.** Exactly one `--model <id>` or
   `--model=<id>` is required before the route's first `--`; there is no default.
   The wrapper removes only that separator and preserves the original model option
   and every other child argument and boundary. The selected ID must be a full
   official lower-case Claude model ID, not a short alias, namespaced ID, `[1m]`
   variant, `claude-ocx-*`/`claude-ocx2-*` alias, or desktop coded alias. It also
   refuses an exact or date-stripped `modelMap` hit, so the route never silently
   selects a mapped/routed model.

5. **Accept only narrow, masked native-auth evidence.** The route requires
   status to prove `enabled: true`, `authMode: "subscription"`,
   `admissionKeyActive: false`, `authDetectionUnknown: false`, and an
   `authFoundBy` value of exactly `claude-json-oauth`,
   `claude-credentials-file`, or `macos-keychain`. It refuses `exported-env`,
   unknown/missing detectors, and every other status ambiguity.

6. **Bound the configuration invariant to the inspected pin.** A missing scoped
   `claudeCode.nativePassthrough` key is accepted only through the 2.11.1
   source-backed default-on invariant. Explicit `false`, another explicit value,
   or a non-missing config-read failure refuses. A missing
   `claudeCode.anthropicBaseUrl` key is accepted as the official default; an
   explicit official `https://api.anthropic.com` value is accepted, while any
   other explicit value or non-missing read failure refuses.

7. **Attach only to an already-healthy gateway.** This route calls the
   identity-checked health probe only. It never calls `ocx ensure`, `ocx restart`,
   `ocx stop`, provider configuration, or another lifecycle action. An unhealthy
   gateway is an unavailable precondition, not a request to start one.

8. **Retain the ordinary boundary.** Nothing in this route changes the
   subscription refusals, isolated configuration, or normal lifecycle behavior of
   `launch` and `launch-ultracode`.

## Consequences

- Positive: an operator cannot accidentally reach this behavior through the
  ordinary launch routes, a default model, or a mapped alias.
- Positive: all credential-sensitive decisions use variable presence, masked
  status, non-secret scalar configuration, or a health probe; no OAuth secret is
  printed, copied, stored, or intentionally read by repository code.
- Negative: the route remains unsupported and can expose the operator's account
  to enforcement; this ADR neither mitigates that account risk nor claims a
  provider exception.
- Negative: status and source-backed configuration checks are not a sandbox
  against the same OS user or against future upstream behavior. A version change
  reopens this evidence and must be reviewed before relying on the invariant.
- Testing is synthetic only: help must be side-effect free; parent-control
  refusal must occur before any gateway command; healthy-only behavior, exact
  argv forwarding, accepted/missing/error config states, alias/model-map
  refusals, and ordinary-route non-regression must be covered without a live
  OAuth request or global credential/config mutation.

## Reversal condition

This route must be reconsidered if Anthropic publishes an explicit policy change
or written exception that authorizes the use case, or if OpenCodex changes the
status/config/inbound behavior this record relies on. Neither event automatically
makes subscription passthrough a supported ordinary route; a new decision must
state any revised boundary.

This record is evidence only. It authorizes no credential handling, gateway
lifecycle mutation, request, publication, push, or other outward effect.
