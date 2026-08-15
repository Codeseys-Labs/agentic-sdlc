# ADR-0017 — Make Claude Code the primary product host

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `VISION.md`, `README.md`, `AGENTS.md`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`

## Context

The current repository presents two incompatible product identities. `VISION.md:3` says Claude Code
is the primary target. `README.md:3-5`, `AGENTS.md:3-6`, and the current host manifests instead lead
with a provider-native multi-host bundle. Claude Code is also the only current primary host with the
Dynamic Workflow substrate selected for the product journey. Treating every host as a peer makes
the first journey ambiguous and turns portable skills into an equal-parity promise the repository
has not proven.

The operator chose a native-Claude Core that succeeds without a gateway. `ccodex` remains the
operator CLI, and OCX supplies an optional routed-model profile. Other capable hosts retain portable
skills and shared contracts without inheriting Claude Code feature claims.

## Considered options

- **Keep a provider-neutral multi-host product.** Rejected because it hides the primary execution
  substrate and creates a parity obligation across unlike host capabilities.
- **Replace Claude Code with a new general agent runtime.** Rejected because it duplicates the host,
  enlarges the trust surface, and abandons Dynamic Workflows rather than using them.
- **Make Claude Code primary while preserving companion-host contracts.** Chosen because it gives
  Core one executable journey without discarding portable authored skills.

## Decision

1. **Agentic SDLC** is the product and methodology. Its canonical descriptor is “A Claude
   Code-first, evidence-driven SDLC harness for greenfield and brownfield repositories.”
2. **Agentic SDLC Core** runs through ordinary Claude Code and the operator's own Claude account. It
   requires no gateway, external provider, or companion library.
3. **`ccodex`** is the operator CLI, not a second product brand. OCX is an optional routing
   dependency used only by the routed-model profile.
4. Other hosts are companion hosts. They may consume proven portable contracts but receive no
   equal-parity promise with Claude Code Dynamic Workflows.

This decision unblocks one Core acceptance journey and a coherent claim migration. It does not
make the current provider-native descriptions conforming and authorizes no implementation or
publication effect.

## Consequences

- Positive: product, CLI, gateway dependency, companion hosts, and companion libraries have
  distinct names and support obligations.
- Positive: the first release can optimize one complete Claude Code journey before expanding host
  capability rows.
- Negative: non-Claude hosts no longer receive implied peer status, even where many portable skills
  work unchanged.
- Negative: current manifests, README, agent router, examples, and help require a coordinated claim
  migration after the executable Core surface exists.
- **Confirmation:** review every owned public claim against this record and run `mise run check`.
  The current gate validates manifests but does not yet validate the product vocabulary; a pass is
  partial evidence only.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Refines | ADR-0005 | Narrows only ADR-0005's default-install and normal-product posture: OCX becomes optional, while ADR-0005's still-live launcher, supervision, qualification, and non-authority constraints remain in force unless separately replaced. |
| Refines | ADR-0003 | The accepted optional-gateway stance becomes the named routed-model profile beneath a native-Claude Core. |
| Relates-To | ADR-0014 | The optional routed launch continues to preserve the operator's Claude login under ADR-0014. |
| Part-Of | ADR-0028 | This record decides the product-host boundary inside the Claude Code-first product initiative. |

## Compliance

- Owned product prose names Agentic SDLC as the product and `ccodex` as its operator CLI.
- Core installation and execution do not require OCX or an external provider credential.
- Non-Claude hosts are described through exact portable capabilities, not equal host parity.
- Multi-provider claims identify the exact optional routed-model profile and evidence boundary.

## Reversal condition

If a non-Claude host independently implements and passes the complete published Core journey with
the same workflow, artifact, pause, review, and authority semantics, the product owner re-examines
whether primary-host asymmetry still serves the product.
