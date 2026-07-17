# Agentic SDLC vision

Agentic SDLC is a portable, host-installed software-delivery control system. Claude Code is the primary target; other capable hosts participate through shared contracts rather than host-specific doctrine. It is intended to make disciplined delivery repeatable without treating automation as authority.

```mermaid
flowchart LR
    H[Claude Code primary target\nand capable hosts] --> D[Global distribution\npinned utilities, skills, roles, commands]
    D --> A[Per-project activation\nadapt to repository evidence]
    A --> W[Dynamic workflows\ncertified model and effort routing]
    W --> T[Ignored project-local worktrees\none writer per worktree]
    T --> E[Tests, reviews, and evidence]
    E --> I[One integrator is the sole\nfan-in mutation executor]
    S[Seeds: roadmap and current work] --> W
    ADR[ADRs: decision rationale] --> E
    R[Authoritative source text\nand contracts] --> E
    M[Mermaid diagrams\nparseable documentation] --> R
    O[Optional transports\ncertification-dependent] -. only after certification .-> W
    I --> G[Git: integration, receipt, CI,\nsystem of record and evidence authority]
    G --> PG[Single conjunctive publication prerequisite:\nqualifying Git/CI/review evidence AND\none explicit operation-specific human authorization]
    PG --> P[Publication]
```

## Distribution and activation

Mise is the only bootstrap prerequisite. A global installation is meant to distribute pinned helper utilities, skills, role agents, commands, validators, and lifecycle tooling. It does not make a repository ready by itself. Per-project activation must inspect and safely adapt to the repository's existing policy, ownership, baseline, and capabilities instead of spraying generic scaffolding or overwriting local work.

## Evidence-led delivery

Substantive workflows decompose work at runtime. Each phase should use the certified model, effort, and context shape appropriate to its decision and verification burden, with identity and routing read back rather than inferred. Independent work may scale dynamically into parallel agents only under one finite root-assigned envelope of budgets, concurrency/WIP caps, and delegation-depth limits, inherited and atomically charged across the entire delegation tree; no child may reset, replenish, fork around, or raise it. Evidence must warrant the work, and every parallel writer receives its own project-local ignored worktree. Reviews advise; they do not authorize. One integrator is the sole fan-in mutation executor.

Seeds records the roadmap, milestones, epics, phases, dependencies, and current work; it is not an authorization channel. ADRs preserve the rationale for architectural decisions as evidence evolves; authoritative source text and contracts define the current requirements and interfaces. Mermaid diagrams make technical documentation intuitive and parseable for people and agents, while their readable source text remains authoritative. Git is the system of record and evidence authority for integration, receipts, CI, and publication evidence, but it does not authorize those effects: publication passes only through the mandatory gate where Git evidence and explicit human, operation-specific authorization meet.

Optional transports, including CLIProxyAPI and claude-code-proxy, remain aspirational until certified for exact model and effort routing, identity readback, credential safety, and recovery. A configuration or a local success is not certification.

## Self-hosting, learning, and authority

Agentic SDLC is self-hosting: it improves this repository through the same contracts it installs in downstream projects. That recursion is a conformance test, not elevated self-modification authority. The system should learn from verified outcomes and evolve its skills, policies, and plans, while preserving uncertainty and the evidence behind changes.

It must never grant itself permission, bypass gates, overwrite foreign or user data, merge its own work, or hide uncertainty. Every outward effect requires explicit human, operation-specific authorization. A conductor may only disposition internal queues and proposals, then delegate an already-human-authorized bounded fan-in to the sole integrator; it cannot originate, infer, self-issue, or execute that mutation authority. Reviews remain advisory, and the integrator's fan-in ownership does not create authority to publish, merge, deploy, or mutate external systems.

## Success criteria

The vision succeeds when a capable host can install the portable control system, activate it safely in a real repository, and produce isolated, evidence-backed candidates through phase-aware routing. Its records and diagrams must explain both current work and architectural decisions; its gates and Git receipts must make outcomes independently checkable. Its behavior on this repository and downstream projects must demonstrate the same boundaries: learning improves future work without weakening human authority, data ownership, or delivery controls.
