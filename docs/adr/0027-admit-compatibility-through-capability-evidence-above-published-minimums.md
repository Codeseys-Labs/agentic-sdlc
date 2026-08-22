# ADR-0027 — Admit compatibility through capability evidence above published minimums

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `README.md`, `AGENTS.md`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`

## Context

Claude Code release channels move, platform behavior differs, and Dynamic Workflow semantics have
changed after their introduction. An exact tested set is useful release evidence but becomes a hard
ceiling if the product refuses every newer version not yet listed. A broad `>=` claim has the
opposite defect: it treats vendor eligibility as proof that every required workflow, permission,
pause, artifact, filesystem, and optional-profile behavior works.

Anthropic's [Dynamic Workflows documentation](https://code.claude.com/docs/en/workflows) records
Claude Code 2.1.154 or later as the feature floor. Anthropic's official
[`stable`](https://downloads.claude.ai/claude-code-releases/stable) and
[`latest`](https://downloads.claude.ai/claude-code-releases/latest) endpoints returned 2.1.224 and
2.1.233 on 2026-08-15. Those exact values are dated reference points, not permanent support facts.

## Considered options

- **Support only exact allowlisted Claude Code versions.** Rejected because moving host releases
  would turn untested-newer into unsupported even when all required capabilities pass.
- **Claim compatibility with every version above one minimum.** Rejected because later host,
  platform, installation, and profile changes can break load-bearing behavior.
- **Use published minimum eligibility plus current capability admission.** Chosen because it keeps
  minimum requirements useful without converting them into unverified compatibility claims.

## Decision

1. Each product surface publishes a minimum host and feature requirement. Agentic SDLC Core starts
   at Claude Code 2.1.154 with Dynamic Workflows effectively enabled; optional profiles may require
   higher feature floors.
2. Meeting a minimum makes a tuple eligible for assessment. Safety-dependent use still requires
   the selected surface's current versioned capability canaries.
3. Exact Agentic SDLC release, host version, OS and architecture, runtime boundary, acquisition
   plane, capability evidence, and optional profile versions form one compatibility tuple.
4. Every tuple is `certified`, `capability-qualified`, `experimental`, or `unsupported`. Core and
   optional profiles, platforms, installation methods, renderers, and companion hosts never inherit
   one another's tier.
5. Exact stable and latest nominations are regression references. They create no general maximum;
   only a known incompatibility or safety defect justifies an explicit exclusion.
This decision unblocks compatibility-matrix and claim-linting specifications. It does not certify
the dated reference versions or any platform tuple.

## Consequences

- Positive: newer hosts can become locally capability-qualified without a release that merely adds
  their version number.
- Positive: support claims stay attached to exact platform, installation, and profile evidence.
- Negative: release preparation needs both offline matrix gates and separately authorized live
  capability journeys.
- Negative: users may see a vendor-supported host labeled experimental or unsupported until this
  product's own evidence exists.
- **Confirmation:** conformance is not yet mechanically checkable because the compatibility matrix
  and admission fixtures do not exist. The current confirmation is independent ADR and
  specification review against the four Compliance assertions below; the implementation proposal
  records the missing executable checks.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0017 | Compatibility claims distinguish the Claude Code Core from companion-host capabilities. |
| Depends-On | ADR-0020 | Capability admission requires exact host, runtime, route, and profile identity evidence. |
| Relates-To | ADR-0015 | Rightsizing qualification remains independent from host/profile compatibility certification. |
| Part-Of | ADR-0028 | This record decides compatibility admission inside the Claude Code-first product initiative. |

## Compliance

- An unlisted newer host is not refused solely because it is absent from the tested reference set.
- Meeting a minimum never becomes a certified or provider-wide support claim by itself.
- Platform, architecture, installation, Core, and optional-profile evidence remain separate rows.
- Owned prose avoids blanket latest, cross-platform, provider-wide, model-wide, and host-parity claims.

## Reversal condition

If Claude Code introduces a vendor-enforced exact compatibility API that fully reports every
load-bearing Core capability and proves stable across the supported platforms, the release owner
re-examines whether independent capability canaries remain necessary.
