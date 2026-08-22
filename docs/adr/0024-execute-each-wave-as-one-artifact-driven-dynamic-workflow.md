# ADR-0024 — Execute each wave as one artifact-driven Dynamic Workflow

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `skills/agentic-sdlc/SKILL.md`, `commands/sdlc-wave.md`, `skills/agentic-sdlc/references/sdlc-loop.md`

## Context

The current skill and slash commands describe discovery, research, planning, isolated worktrees,
review, critique, integration, and reconciliation, but no owned installed Dynamic Workflow executes
that graph. Chat-only orchestration loses identity and continuation state. A free recursive worker
tree can also multiply cost, writers, and scope beyond the wave the operator reviewed.

Claude Code Dynamic Workflows are the selected primary substrate because they can represent bounded
agents, dependencies, artifacts, approval pauses, and results inside the host. Exact route, model,
effort, and effective identity still require independent runtime evidence.

## Considered options

- **Keep orchestration entirely in prompts and chat.** Rejected because phase state, dependencies,
  artifact identity, and stop conditions remain advisory and hard to resume safely.
- **Build a replacement scheduler outside Claude Code.** Rejected because it duplicates the host
  runtime and expands credentials, permissions, and lifecycle ownership.
- **Install one bounded Dynamic Workflow per approved wave.** Chosen because it uses the host's
  native execution graph while preserving Agentic SDLC artifacts and authority boundaries.

## Decision

1. One approved wave executes as one artifact-driven Dynamic Workflow DAG with one top-level
   mission root and one shared budget, WIP, concurrency, depth, deadline, and call envelope.
2. Stages may fan out across disjoint scopes or named lenses. Every writer has exclusive write
   custody in one target-local ignored worktree; immutable candidates return to one designated
   fan-in owner.
3. Every actual model spawn receives a resolved exact runtime assignment with explicit model and
   effort injection. Requested values remain separate from observed provider and model evidence.
4. Recursive spawn is off by default. A separately selected profile may enable canary-qualified
   bounded recursion while all descendants remain inside the top-level envelope.
5. Review and critique consume stable immutable snapshots and submit advisory findings. Only the
   authorized integrator performs an already authorized serial fan-in.
6. Completion requires acceptance evidence, qualifying gates, disposition of blocking findings,
   and an adversarial review. Future work is recorded separately and does not prevent an honest
   terminal verdict unless it blocks the framed acceptance criteria.

This decision unblocks the first Core workflow implementation. It does not make the current prose
commands executable and authorizes no spawn, worktree, inference, fan-in, or publication.

## Consequences

- Positive: workflow state and artifact dependencies can survive pauses and become independently
  inspectable.
- Positive: parallel agents scale within one visible envelope instead of creating unbounded roots.
- Negative: Claude Code becomes the primary execution dependency for the complete Core journey.
- Negative: work that cannot fit one bounded DAG must be reframed into more than one human-approved
  wave.
- **Confirmation:** conformance is not yet mechanically checkable because the owned Workflow does
  not exist. The current confirmation is independent ADR and specification review against the four
  Compliance assertions below; the implementation proposal records the missing canary and
  installed-byte Core-wave checks.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0017 | Claude Code is the primary host whose Dynamic Workflow substrate runs Core. |
| Depends-On | ADR-0019 | Workflow progress, reviews, and gates remain non-authorizing evidence. |
| Depends-On | ADR-0020 | Every host, workflow, model, and route dependency needs exact admission evidence. |
| Relates-To | ADR-0015 | Rightsizing may recommend a route, but dispatch still requires a concrete runtime assignment. |
| Part-Of | ADR-0028 | This record decides wave execution inside the Claude Code-first product initiative. |

## Compliance

- A wave has exactly one top-level mission root and one shared bounded envelope.
- No two write-capable nodes own the same write set or worktree.
- Recursive spawn is disabled unless an explicit qualified profile and envelope admit it.
- Review output cannot mutate the candidate, queue, or approval state.

## Reversal condition

If Claude Code removes Dynamic Workflows or cannot pass the published Core graph, pause, artifact,
and identity canaries at the minimum supported boundary, the workflow owner re-examines the primary
execution substrate.
