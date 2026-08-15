# Research draw.io agent diagram workflows

Type: research
Status: resolved
Blocked by: none
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Using the linked Matheus Costa article and current first-party draw.io/diagrams.net repositories,
documentation, formats, exporters, and licences, what can an agent safely author, validate,
preview, render, and maintain as editable draw.io diagrams? Verify the article's Kiro/Agent Skills
workflow, XML or compressed-format boundary, libraries/templates, diagram types, headless export,
security and embedded-content risks, deterministic checks, source/render provenance, and
cross-platform runtime requirements. Compare this with Agentic SDLC's Mermaid skill and renderer
boundary, then identify evidence-backed inputs for a sister umbrella-plus-diagram-type skill family.

Asset: `../research/drawio-agent-diagram-workflows.md`

## Answer

[The draw.io workflow research](../research/drawio-agent-diagram-workflows.md) supports one
optional umbrella authoring surface with lazy diagram-type references, not one top-level skill per
generic diagram type. Canonical source is bounded uncompressed `.drawio` XML admitted by hardened
parsing, pinned XSD, semantic/reference/style/external-content checks, and visual review. Keep the
source beside any derived export. Browser preview is explicit egress; desktop export is technically
available but not a certified renderer until pinned, sandboxed, measured, and provenance-tested.
Domain-heavy specializations such as AWS may later earn siblings through distinct inputs, icon
registries, layout semantics, validators, recurrence, and maintenance ownership.
