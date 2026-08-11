---
name: sdlc-frame
description: Frame an agentic SDLC run — define done, read queue/repo state, pick the run shape, set caps
---

Run the FRAME phase of the agentic-sdlc loop for: $ARGUMENTS

1. Load the `agentic-sdlc` skill if not already loaded.
2. State the exact done condition for this run. If $ARGUMENTS is ambiguous, ask one
   clarifying question before proceeding.
3. Confirm activation before framing execution. If the target's Seeds queue is absent, route to
   `/sdlc-init` and stop; Frame does not initialize a queue or improvise activation. For an active
   queue, prime state using the exact `Seeds(<target>, <args...>)` shorthand defined by the loaded
   orchestrator skill (never an ambient executable):
   - `Seeds(<target>, prime)` + `Seeds(<target>, ready --format json)` +
     `Seeds(<target>, blocked --format json)`
   - `git status --short` (dirty tree → plan worktrees; never write in a dirty checkout)
   - Read repo intent docs (README, ADRs, roadmap) relevant to the task.
4. Detect provider-native delegation first, but treat it as sufficient only after the
   required capability and trust probes succeed. Record missing, unpinned, untrusted, or
   ambiguous capability as a fail-closed stop. Detect optional cmux only when its CLI and
   `CMUX_WORKSPACE_ID` are already present. Never install, start, or enable cmux or
   tmux during framing.
5. Before any model dispatch, load `model-tier-rightsizing`. Classify each worker as
   frontier, judgment workhorse, capable volume, or mechanical floor; choose within its
   Sol/Fable, Terra/Opus, or Luna/Sonnet pair by task fit, independent perspective, quota,
   and verified transport. A caller must inject a certified exact model ID **and explicit
   requested effort** into every delegation; provider-neutral roles do not select models.
   Stop before dispatch and spawn when the route is missing, inherited, unresolved, or has
   unverified identity or adapter readback. Do not force all six models into the run.
6. Decide the run shape and set caps: a certified native role/subagent/worktree Wave, or the
   direct exception below. Every actual worker or model spawn is delegated execution and therefore
   requires the certified `RuntimeAssignment` in step 5.
   - Select direct only when **no certified delegation route exists** and exactly one ready Seed
     is small, bounded, and reviewable in one clean dedicated Git worktree. This is exactly one
     bounded, non-delegated conductor execution. Set caps to one conductor execution, zero
     workers, zero model spawns, zero `RuntimeAssignment` claims, one scope, one gate, one
     stable-snapshot review, and one conductor-only reconciliation.
   - The direct exception preserves the same framed scope, acceptance criteria, gate, review, and
     reconcile phases as a Wave. Stop instead when the work needs a second direct pass or retry,
     a worker/model, parallel work, unbounded discovery, or review that cannot be independent of
     the executing conductor.
7. Emit the frame as a short plan: done condition, run shape, caps, phase list, capability
   and model-resolution evidence (resolved only after adapter readback; otherwise unresolved;
   `not-applicable` only for the non-delegated direct exception), outward operations requiring
   explicit operation-specific approval, and either the first delegation or the direct-exception
   stop conditions. Do not start implementing until the frame is acknowledged.
