# ADR-0020 — Admit only exact verified execution dependencies

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `mise.toml`, `mise.lock`, `AGENTS.md`, `skills/model-tier-rightsizing/policy/runtime-assignment-receipt-v1.json`

## Context

Agentic SDLC delegates work to tools, hosts, models, gateways, package managers, renderers, and
external library installers. A name on `PATH`, a catalog row, a package version, or a successful
request does not prove which bytes or model performed the work. ADR-0002 pins the managed tool
front door, while runtime-assignment and renderer policies already verify narrower identities.
The product needs one rule for every readiness-dependent execution dependency.

## Considered options

- **Trust ambient executables and provider defaults.** Rejected because caller state can substitute
  a different binary, model, registry, configuration, or fallback without changing the command name.
- **Vendor every dependency.** Rejected because it transfers licence, update, credential, and
  maintenance obligations and cannot vendor subscription hosts or provider models.
- **Resolve exact dependencies through their owning front doors and verify effective identity.**
  Chosen because it preserves ownership while making substitution and unsupported uncertainty
  visible.

## Decision

1. Every dependency that carries a gate, lifecycle, dispatch, render, or recovery verdict resolves
   to an exact version or immutable identity through a reviewed front door.
2. Requests and configuration are not execution proof. The product reads back effective binary,
   route, provider, model, effort, context, host capability, or renderer identity where the surface
   exposes it; unavailable facts remain unavailable.
3. Ambiguous, unpinned, stale, quarantined, substituted, or unsupported dependencies block only the
   surface that needs them and produce named diagnostic evidence.
4. Ordinary commands never silently resolve, install, update, replace, or fall back to a different
   dependency. Refresh is a separate reviewed lifecycle operation.
5. Foreign files, libraries, credentials, and configurations remain under their owner's lifecycle.
   Agentic SDLC does not adopt them merely because their names match.

This decision unblocks one capability-admission vocabulary across release, activation, routing,
rendering, and workflow dispatch. Existing version or lock evidence does not retroactively prove
tarball, transitive, or served-model identity.

## Consequences

- Positive: each support and execution claim can identify the exact dependency that produced it.
- Positive: missing optional tools degrade a named capability instead of poisoning unrelated Core
  readiness.
- Negative: installation, release, and live canary work must maintain more identity receipts and
  negative tests than a PATH-based toolchain.
- Negative: some upstreams expose insufficient readback, so useful routes or platforms remain
  experimental or unsupported despite appearing to work.
- **Confirmation:** run `mise run check` and inspect the selected surface's current identity
  receipt or canary. The repository gate cannot substitute for a live route or host readback.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Relates-To | ADR-0002 | ADR-0002 governs the managed-tool front door; this record does not narrow that bootstrap decision. |
| Relates-To | ADR-0015 | ADR-0015 remains the exact route-evaluation rule and an existing example of effective-identity evidence. |
| Relates-To | ADR-0009 | External libraries remain verified through their own front doors and are never adopted from name presence. |
| Part-Of | ADR-0028 | This record decides dependency admission inside the Claude Code-first product initiative. |

## Compliance

- A readiness-dependent executable is never selected from ambient PATH without an admitted exact identity.
- A requested model, effort, context, or provider is never reported as effective readback.
- Fallback and substitution are explicit policy states, never silent runtime conveniences.
- A dependency refresh is an explicit lifecycle operation with before-and-after evidence.

## Reversal condition

If a selected upstream cannot expose an exact identity yet a bounded independent control proves
equivalent non-substitution for that one surface, the product owner re-examines that surface rather
than weakening the product-wide rule.
