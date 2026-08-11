# ADR-0003 — gateway stance downgraded: optional for non-Anthropic models, not a subscription-cost mechanism

- **Status:** accepted
- **Note:** the gateway-is-optional stance stands; the subscription-routing prohibition below does
  NOT. ADR-0014 replaces it against Anthropic's current gateway and legal-and-compliance
  documentation. This record is not a constraint on that point. Decision item 5 in particular reads
  as live normative prose about a route that no longer exists: ADR-0014 DELETED
  `ccodex claude-subscription`, so item 5's present-tense obligations — that it "must retain that
  warning in its help", refuse ambiguity, require one explicit full native unmapped `--model`, and
  never start/restart/configure a gateway — bind nothing and must not be cited as current
  requirements. Its closing citation of ADR-0013 as the complete admission contract is likewise
  historical: ADR-0013 is itself superseded by ADR-0014. Item 5's non-reversal reasoning is
  preserved as the record of why the escape hatch did not weaken the then-current refusals.
- **Date:** 2026-08-06
- **Deciders:** operator (decision), agent (evidence and drafting)
- **Relates to:** `docs/research/2026-08-05-gateway-selection-memo.md` and its
  2026-08-05 addendum; `docs/adr/0013-explicit-unsupported-claude-subscription-passthrough.md`

## Context

`docs/research/2026-08-05-gateway-selection-memo.md` evaluated three gateway
candidates (opencodex, CLIProxyAPI, claude-code-proxy) against six
requirements, the load-bearing one being requirement (2): pass through the
user's own Claude subscription credential so gateway-routed traffic bills
against subscription usage rather than a metered API key. The memo's original
verdict adopted opencodex conditionally, gated on an unrun canary (its §4,
Probes A–F).

**A post-workflow addendum to that same memo reversed the cost premise.**
Three pieces of evidence, read directly against Claude Code's own published
documentation, establish this:

1. **The technical mechanism does work, but silently.** Claude Code's
   `llm-gateway` documentation states that setting only `ANTHROPIC_BASE_URL`
   without a gateway credential does not replace the subscription: requests
   still route through the gateway, a saved subscription login remains the
   active credential, and its usage limits and billing apply. The companion
   `llm-gateway-protocol` documentation adds that the `anthropic-beta` header
   carries an OAuth capability the upstream requires — stripping it fails
   those requests outright, and Claude Code "never suppresses" it.
2. **Gateway mode and subscription mode are not mutually exclusive** — they
   become exclusive only once an explicit gateway credential is set, at which
   point that credential replaces the subscription login for that session and
   bills per token to the credential owner.
3. **The enforcement clause is the blocker, independent of the mechanism
   working.** Claude Code's `legal-and-compliance` documentation states that
   subscription OAuth is "intended exclusively for purchasers of Claude Free,
   Pro, Max, Team, and Enterprise subscription plans" to support "ordinary use
   of Claude Code and other native Anthropic applications"; that developers
   "should use API key authentication"; that Anthropic "does not permit
   third-party developers to offer [subscription] login or to route requests
   through Free, Pro, or Max plan credentials on behalf of their users"; and
   that Anthropic "reserves the right to take measures to enforce these
   restrictions and may do so without prior notice." Anthropic's consumer
   terms of service separately forbid sharing account credentials, and its
   automated-access carve-out is scoped to API keys only.

The addendum's own framing: *"The architecture works; the authorization does
not."* The supported way to put a gateway in front of Claude Code is an
explicit gateway credential, which bills per token by design — and doing that
eliminates the cost-efficiency premise the entire gateway evaluation was built
on. Per `AGENTS.md`, a passing canary is evidence only; here the evidence is
that the mechanism functions while the policy forbids the use case it would
have served.

pi-lab independently reached a structurally similar, but narrower, verdict for
its own runtime (`docs/research/wayfinder/right-sizing-design.md`): a bundled
gateway stays out of scope for Pi, with an explicit falsifiability clause —
"What would reopen it" — naming three measured conditions and stating plainly
that none of them reopens the gateway question today. That repo's
subscription-cost finding is distinct from this repo's ToS finding, but both
land in the same place: a bundled gateway is not the mechanism for the cost
problem it looks like it solves.

## Decision

1. **Subscription-passthrough-for-cost is rejected.** It is blocked by
   Anthropic's terms of service, not by a technical limitation — the
   mechanism works, the authorization does not. This bundle does not adopt
   opencodex, CLIProxyAPI, or any other gateway for the purpose of routing
   subscription-authenticated Claude Code traffic through a non-Anthropic
   process to avoid metered billing.
2. **Gateways remain optional, for a different and legitimate purpose: routing
   to non-Anthropic models via each provider's own API key.** A gateway used
   with an explicit, provider-issued API credential — never a passed-through
   or replayed subscription OAuth token — sits fully within the supported
   authentication model and is not gated by this ADR.
3. **The unrun canary in the memo's §4 stays unrun and stays scoped to what it
   was actually testing.** Probes A, C, D, E, and F (fail-closed routing,
   per-subagent pinning, readback admissibility) remain relevant to a
   future API-key-only gateway adoption. Probe B — proving subscription OAuth
   transmission through a gateway — is moot; running it would only re-confirm
   a mechanism this ADR has already declined to use for that purpose.
4. **Falsifiability, following pi-lab's own pattern:** this stance is
   reopened only by a *measured*, not anticipated, condition — specifically,
   a documented change to Anthropic's own `llm-gateway` or
   `legal-and-compliance` policy text that removes the enforcement clause
   quoted above, or an explicit written exception from Anthropic for this
   bundle's use case. A more permissive-sounding gateway product's own
   marketing claims do not satisfy this condition; only Anthropic's
   documentation does.
5. **A separately named escape hatch does not reverse this decision.**
   `ccodex claude-subscription` is an explicit individual operator action,
   implemented only to make its unsupported/account-risk nature conspicuous.
   It is not provider-approved, is not a supported entitlement path, and its
   explicit invocation creates neither authorization nor an exception to the
   restriction above. It must retain that warning in its help and refuse
   ambiguity rather than becoming an ordinary `launch` mode.

   The route does not handle OAuth itself: it reads no credential store or
   token, calls plain `claude` rather than `ocx claude`, and checks only masked
   daemon status plus non-secret config scalars. It requires exactly one explicit
   full native unmapped `--model` before its wrapper `--`, has no default, and
   removes only that separator before forwarding the child argv. It requires an
   already-healthy gateway and must never start/restart/configure one, because
   upstream lifecycle commands mutate shared `~/.codex`. Thus its existence does
   not weaken the ordinary split-plane route's subscription refusals.

   OpenCodex 2.11.1's masked status omits `nativePassthrough`; its pinned source
   documents default-on behavior unless that scalar is explicitly `false`. The
   route checks the scalar directly and treats that source/pin behavior as a
   limited invariant, not a runtime proof or provider authorization. ADR-0013
   specifies the complete admission contract and test obligations.

## Consequences

- Positive: the bundle's documented model-routing stance no longer contains a
  live self-contradiction between "provider-native, gateway-absent" committed
  doctrine and an unresolved "gateway mandatory" ambition recorded elsewhere
  in uncommitted working files — this ADR is the resolution.
- Negative: the cost-efficiency motivation that started the gateway
  evaluation is unmet. No mechanism reviewed here reduces subscription
  metered-billing exposure while staying inside Anthropic's authorization
  model.
- Negative: any future non-Anthropic-model gateway adoption still needs its
  own configuration-contract review (never emit a bare/ambiguous model ID,
  assert failover lists are empty, treat the gateway's own log stream as the
  only admissible resolved-model evidence) — this ADR does not pre-clear
  that work, it only removes the subscription-passthrough branch from
  consideration.
- **Confirmation:** `rg -ni gateway AGENTS.md README.md` returning zero hits
  in the committed tree is the current, correct state this ADR intends to
  preserve — a gateway is not a required component of this bundle's install
  or gate surface, and adding one back is a decision this ADR does not make.

## Reversal condition

Falsifiable per Decision item 4: an explicit, dated change in Anthropic's own
published gateway or legal-and-compliance documentation removing the
enforcement clause cited above, or a written exception naming this bundle's
use case, observed and cited by whoever proposes the reopening.

This record is evidence for a conductor to cite; it authorizes no gateway
adoption, credential configuration, or other outward effect on its own.
