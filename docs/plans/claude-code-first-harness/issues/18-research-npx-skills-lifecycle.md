# Research the `npx skills` lifecycle for installation inspiration

Type: research
Status: resolved
Blocked by: none
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Using the current first-party repository, documentation, package metadata, and source code for the
CLI invoked as `npx skills`, what installation-lifecycle patterns should inform `ccodex sdlc`?
Verify discovery, source and target selection, agent/host support, install and removal, update and
locking, ownership and collision behavior, trust/security boundaries, dry-run/noninteractive
operation, telemetry, and self-update behavior. Separate patterns worth adapting from behaviors
that conflict with Agentic SDLC's receipt-backed, own-front-door, explicit-approval contract.

Asset: `../research/npx-skills-cli-lifecycle.md`

## Answer

[The first-party lifecycle review](../research/npx-skills-cli-lifecycle.md) finds that the current
`skills@1.5.22` CLI is useful inspiration for bounded source discovery, a declarative host
registry, canonical storage with host projections, explicit selectors, deterministic manifests,
and input sanitization. It is not suitable as Agentic SDLC's lifecycle authority: AI-agent
detection can imply consent, add/remove use presence-based recursive overwrite/delete without
ownership proof, restore/update are mutable and non-transactional, there is no true dry-run,
telemetry is default-on, and security-audit egress is not governed by telemetry opt-out.
