# Compare the current boundaries of opinionated coding-agent harnesses

Type: research
Status: resolved
Blocked by: none
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Using only current first-party repositories, documentation, manifests, and installers, how do
gstack, oh-my-opencode, oh-my-pi, and Everything Claude Code define their product boundary? Compare
installation, updates, ownership, configuration mutation, skills and agents, model routing,
workflow orchestration, safety controls, and the minimum successful user journey. Identify patterns
worth adapting and boundaries this product should deliberately reject.

Asset: `../research/opinionated-harness-boundaries.md`

## Answer

[Opinionated harness boundary research](../research/opinionated-harness-boundaries.md) recommends
a narrow lifecycle-and-workflow layer over Claude Code. Adapt explicit ownership receipts,
preflight and one chosen install path, a small recognizable first workflow, main-session approval
gates, and observed runtime identity. Reject replacement runtimes, silent configuration takeover
or auto-update, default telemetry, and permission-bypass defaults.
