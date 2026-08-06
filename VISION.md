# Agentic SDLC vision

Agentic SDLC is a portable, host-installed software-delivery control system. Claude Code is the primary target; other capable hosts participate through shared contracts rather than host-specific doctrine. It is intended to make disciplined delivery repeatable without treating automation as authority.

```mermaid
flowchart LR
    H[Claude Code primary target\nand capable hosts] --> D[Global distribution\npinned utilities, skills, roles, commands]
    D --> A[Per-project activation\nadapt to repository evidence]
    A --> W[Dynamic workflows\ncertified model and effort routing]
    W --> T[Ignored project-local worktrees\none writer per worktree]
    T --> E[Exact candidate and qualifying\ntest and review evidence]
    E --> FH[Fresh single-use human grant bound to that exact\ncandidate, evidence, target, and fan-in effect]
    FH --> I[One integrator is the sole\nfan-in mutation executor]
    S[Seeds: roadmap and current work] -. context only .-> W
    ADR[ADRs: decision rationale] -. context only .-> A
    R[Authoritative source text\nand contracts] -. context only .-> A
    M[Mermaid diagrams\nparseable documentation] --> R
    O[Optional transports\ncertification-dependent] -. only after certification .-> W
    I --> G[Exact post-fan-in Git and review evidence\nreceipt, CI, and system of record]
    G --> OH[Separate fresh single-use human grant bound to that exact\nevidence, target, and outward effect]
    OH --> P[Publication or other outward effect]
```

## Distribution and activation

Mise is the only bootstrap prerequisite. A global installation is meant to distribute pinned helper utilities, skills, role agents, commands, validators, and lifecycle tooling. It does not make a repository ready by itself. Per-project activation must inspect and safely adapt to the repository's existing policy, ownership, baseline, and capabilities instead of spraying generic scaffolding or overwriting local work.

## Evidence-led delivery

Substantive workflows decompose work at runtime. Each phase should use the certified model, effort, and context shape appropriate to its decision and verification burden, with identity and routing read back rather than inferred. Independent work may scale dynamically into parallel agents only within one top-level mission envelope: nested workflows cannot declare new roots. Budgets are debited across all descendants, concurrency/WIP slots are reserved and released within the same shared cap, and delegation depth is measured from that top-level root. Evidence must warrant the work, and every parallel writer receives its own project-local ignored worktree. Reviews advise; they do not authorize. The only route to fan-in is serial and mandatory: exact candidate/evidence, then a fresh single-use human grant bound to that exact candidate/evidence/target/fan-in effect, then mutation by the sole integrator.

Seeds records the roadmap, milestones, epics, phases, dependencies, and current work; it is not an authorization channel. ADRs preserve the rationale for architectural decisions as evidence evolves; authoritative source text and contracts define the current requirements and interfaces. Mermaid diagrams make technical documentation intuitive and parseable for people and agents, while their readable source text remains authoritative. Seeds, ADR, source, diagram, and transport edges provide context only and never shortcut either mutation route. Git is the system of record and evidence authority, not effect authority. Each grant is current, single-use, and bound to the exact queue, candidate, evidence, target, and authorized effect; any change to the queue, candidate, evidence, target, or authorized effect invalidates it. After fan-in, the only route to publication or any other outward effect is serial and mandatory: exact post-fan-in Git/review evidence, then a separate fresh single-use human grant bound to that exact evidence/target/outward effect, then the authorized publication or outward effect.

Optional transports, including CLIProxyAPI and claude-code-proxy, remain aspirational until certified for exact model and effort routing, identity readback, credential safety, and recovery. A configuration or a local success is not certification.

## Self-hosting, learning, and authority

Agentic SDLC is self-hosting: it improves this repository through the same contracts it installs in downstream projects. That recursion is a conformance test, not elevated self-modification authority. The system should learn from verified outcomes and evolve its skills, policies, and plans, while preserving uncertainty and the evidence behind changes.

It must never grant itself permission, bypass gates, overwrite foreign or user data, merge its own work, or hide uncertainty. A conductor may disposition internal queues and proposals within the authorized scope, but cannot add, substitute, or broaden work after authorization; changed scope returns for a new human grant. Only the integrator executes authorized fan-in, and that ownership creates no authority to publish, merge, deploy, or mutate external systems.

## Success criteria

The vision succeeds when a capable host can install the portable control system, activate it safely in a real repository, and produce isolated, evidence-backed candidates through phase-aware routing. Its records and diagrams must explain both current work and architectural decisions; its gates and Git receipts must make outcomes independently checkable. Its behavior on this repository and downstream projects must demonstrate the same boundaries: learning improves future work without weakening human authority, data ownership, or delivery controls.
