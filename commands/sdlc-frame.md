---
name: sdlc-frame
description: Frame an agentic SDLC run — define done, read queue/repo state, pick the run shape, set caps
---

Run the FRAME phase of the agentic-sdlc-orchestrator loop for: $ARGUMENTS

1. Load the `agentic-sdlc-orchestrator` skill if not already loaded.
2. State the exact done condition for this run. If $ARGUMENTS is ambiguous, ask one
   clarifying question before proceeding.
3. Prime state using the exact `Seeds(<target>, <args...>)` shorthand defined by the loaded
   orchestrator skill (never an ambient executable):
   - `Seeds(<target>, prime)` + `Seeds(<target>, ready --format json)` +
     `Seeds(<target>, blocked --format json)` (if Seeds present)
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
   Stop before dispatch if identity or adapter readback is unresolved. Do not force all six
   models into the run.
6. Decide the run shape (direct / native role or subagent / worktree wave / native provider delegation) and set caps:
   max workers, max worktrees, max review rounds, stop conditions.
7. Emit the frame as a short plan: done condition, run shape, caps, phase list, capability
   and model-resolution evidence (resolved only after adapter readback; otherwise
   unresolved), outward operations requiring explicit operation-specific approval,
   and the first delegation. Do not start implementing until the frame is acknowledged.
