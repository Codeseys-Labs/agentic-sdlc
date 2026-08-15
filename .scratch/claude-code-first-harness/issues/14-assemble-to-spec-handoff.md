# Assemble the decision handoff for `/to-spec`

Type: task
Status: resolved
Blocked by: 13, 21
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Assemble the resolved ticket answers and repository-truth delta into one decision-complete product
and architecture brief. Preserve links to the ticket that owns each decision, state residual
assumptions and explicit non-goals, and verify that no unresolved choice remains before handing the
brief to `/to-spec`.

## Answer

The decision-complete handoff is
[`to-spec-handoff.md`](../to-spec-handoff.md). It defines the product, first journey, scope,
ownership vocabulary, architecture planes, operator surfaces, activation contract, planning and
Dynamic Workflow artifacts, role/custody model, rightsizing and route admission, evidence and
authority rules, privacy and supply chain, documentation/diagram/security capabilities,
compatibility, repository migration, tracer-bullet sequence, release acceptance, implementation
discovery, assumptions, non-goals, and ticket ownership.

Closure checks found no unresolved product or architecture choice. The remaining unknowns are
bounded implementation discoveries that `/to-spec` may resolve without changing a product
boundary. ADR-0021 remains proposed until the versioned release and clean-host evidence exist;
ADR-0028 remains proposed with an in-progress rollup naming ADR-0021. Those are truthful evidence
states, not missing decisions.

The handoff preserves a direct link to every decision-owning ticket and the repository-truth audit.
All local Markdown targets resolve. Every prerequisite ticket is resolved. No product code,
provider configuration, companion install, trust state, Seeds queue, publication, or outward
system was changed.

The next operation is:

```text
/to-spec .scratch/claude-code-first-harness/to-spec-handoff.md
```
