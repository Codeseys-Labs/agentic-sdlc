---
name: sdlc-frame
description: Frame an agentic SDLC run — define done, read queue/repo state, pick the run shape, set caps
---

Run the FRAME phase of the agentic-sdlc-orchestrator loop for: $ARGUMENTS

1. Load the `agentic-sdlc-orchestrator` skill if not already loaded.
2. State the exact done condition for this run. If $ARGUMENTS is ambiguous, ask one
   clarifying question before proceeding.
3. Prime state:
   - `sd prime` + `sd ready --format json` + `sd blocked --format json` (if Seeds present)
   - `git status --short` (dirty tree → plan worktrees; never write in a dirty checkout)
   - Read repo intent docs (README, ADRs, roadmap) relevant to the task.
4. Detect environment: `CMUX_WORKSPACE_ID` (cmux view layer), `command -v cao` +
   `curl -s -m1 localhost:9889/` (CAO available/running), provider env.
5. Decide the run shape (direct / one handoff / worktree wave / full loop) and set caps:
   max workers, max worktrees, max review rounds, stop conditions.
6. Emit the frame as a short plan: done condition, run shape, caps, phase list, and the
   first delegation. Do not start implementing until the frame is acknowledged.
