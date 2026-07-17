# Agentic SDLC vision

Agentic SDLC is a portable, host-installed software-delivery control system. Claude Code is the primary target; other capable hosts participate through shared contracts rather than host-specific doctrine. It is intended to make disciplined delivery repeatable without treating automation as authority.

```mermaid
flowchart LR
    H[Claude Code primary target\nand capable hosts] --> D[Global distribution\npinned utilities, skills, roles, commands]
    D --> A[Per-project activation\nadapt to repository evidence]
    A --> W[Dynamic workflows\ncertified model and effort routing]
    W --> T[Ignored project-local worktrees\none writer per worktree]
    T --> E[Tests, reviews, and evidence]
    E --> I[One integrator owns fan-in]
    S[Seeds: roadmap and current work] --> W
    R[ADRs and authoritative source text] --> E
    M[Mermaid diagrams\nparseable documentation] --> R
    O[Optional transports\ncertification-dependent] -. only after certification .-> W
    I --> G[Git: integration, receipt, CI, publication]
```

## Distribution and activation

Mise is the only bootstrap prerequisite. A global installation is meant to distribute pinned helper utilities, skills, role agents, commands, validators, and lifecycle tooling. It does not make a repository ready by itself. Per-project activation must inspect and safely adapt to the repository's existing policy, ownership, baseline, and capabilities instead of spraying generic scaffolding or overwriting local work.

## Evidence-led delivery

Substantive workflows decompose work at runtime. Each phase should use the certified model, effort, and context shape appropriate to its decision and verification burden, with identity and routing read back rather than inferred. Independent work may scale into parallel agents when evidence warrants it, but every parallel writer receives its own project-local ignored worktree. Reviews advise; they do not authorize. One integrator owns fan-in.

Seeds records the roadmap, milestones, epics, phases, dependencies, and current work; it is not an authorization channel. ADRs preserve why architecture changed as evidence evolved. Mermaid diagrams make technical documentation intuitive and parseable for people and agents, while their readable source text remains authoritative. Git remains the authority for integration, receipts, CI, and publication.

Optional transports, including CLIProxyAPI and claude-code-proxy, remain aspirational until certified for exact model and effort routing, identity readback, credential safety, and recovery. A configuration or a local success is not certification.

## Self-hosting, learning, and authority

Agentic SDLC is self-hosting: it improves this repository through the same contracts it installs in downstream projects. That recursion is a conformance test, not elevated self-modification authority. The system should learn from verified outcomes and evolve its skills, policies, and plans, while preserving uncertainty and the evidence behind changes.

It must never grant itself permission, bypass gates, overwrite foreign or user data, merge its own work, or hide uncertainty. Outward effects require explicit authorization. Reviews remain advisory, and the integrator's fan-in ownership does not create authority to publish, merge, deploy, or mutate external systems.

## Success criteria

The vision succeeds when a capable host can install the portable control system, activate it safely in a real repository, and produce isolated, evidence-backed candidates through phase-aware routing. Its records and diagrams must explain both current work and architectural decisions; its gates and Git receipts must make outcomes independently checkable. Its behavior on this repository and downstream projects must demonstrate the same boundaries: learning improves future work without weakening human authority, data ownership, or delivery controls.
