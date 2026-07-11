---
name: sdlc-init
description: Bootstrap a new or existing project onto the agentic-sdlc system — VCS, Seeds queue, gate stack, trust, CLAUDE.md wiring — ending wave-ready
---

Initialize the current directory (or the path in $ARGUMENTS) as an agentic-sdlc project.
Idempotent: skip anything already present and say so. End state = a repo where
`/sdlc-frame` can immediately plan a worktree/workspace wave.

1. Load the `agentic-sdlc-orchestrator` skill. Resolve its maintained repository checkout
   from the skill's Repo Location section and run
   `<repo>/scripts/check-agentic-sdlc-prereqs.sh` when available. If the checkout is not
   present, inspect the required host tools directly and continue. Stop only for missing
   baseline requirements; CAO, cmux, and tmux are optional and must never block init or
   trigger installation/enabling.

2. VCS baseline:
   - No `.git` → `git init -b main` and make an initial commit (empty is fine).
   - Ask ONE question if not derivable: greenfield or existing code? For greenfield,
     scaffold README.md stub before the initial commit.
   - jj is opt-in: select it only when the user explicitly requests it or repository
     documentation/config already declares it. Binary availability alone is never
     consent. When selected and the repo has no submodules/LFS, run
     `jj git init --colocate`, then `jj bookmark track main --remote=origin` IF a remote
     exists. Per `references/jj-vcs.md`: workspaces replace worktrees, hooks won't fire
     on jj commits, and worker prompts must say "commit with jj, no add/stage step".

3. Seeds queue of record: `sd init` if `.seeds/` absent. Then convert the project's
   starting intent into first Seeds: for greenfield, one Seed per bootstrap milestone;
   for existing code, ask the user for (or derive from TODO/issues) 1-3 initial Seeds.
   Never leave the queue empty — an empty queue makes `/sdlc-wave` a no-op.

4. Gate stack (`skills/repo-toolchain-gates/`):
   - Write `mise.toml`: `[tools]` pinning the project's language toolchain + linters at
     CI-parity versions (+ `lefthook` if git-substrate; + `jj` when the repo supports the
     optional jj substrate), tasks for fmt/lint/test, and `[tasks.check]` depending on all
     of them. A jj pin manages only the binary; never initialize `.jj/` implicitly.
     `mise trust` the repo.
   - Git substrate only: `lefthook.yml` (pre-commit = fast staged-file subset,
     pre-push = heavier subset) + `lefthook install`. Colocated jj → SKIP lefthook,
     note that `mise run check` + CI carry the gates.
   - Secrets gate: wire `betterleaks dir .` into pre-push (or the check task under jj).
   - Prove the gate falsifiable: plant a trivial failure, watch `mise run check` fail,
     revert. A gate that has never failed is theater.

5. Trust + config propagation (workers will spawn from this repo):
   - Codex present → add the project root to `~/.codex/config.toml` trust.
   - Note in CLAUDE.md that every future worktree/workspace path needs codex + mise
     trust at wave creation (`references/seeds-worktrees.md`).

6. Project CLAUDE.md (create or append a marked section, never clobber):
   - One-line project intent.
   - The gate command (`mise run check`) and the substrate (git worktrees | jj
     workspaces).
   - Queue of record: Seeds (`sd ready` before starting work).
   - Pointer: "orchestration doctrine lives in the global agentic-sdlc-orchestrator
     skill — do not duplicate it here."
   - If jj: the hooks-don't-fire fact and the commit-with-jj worker rule.

7. CI stub (ask before creating if the remote/CI provider is ambiguous): a workflow
   that runs the SAME tasks as `mise run check` — local gate == CI gate, no drift.

8. Commit the bootstrap as one atomic commit; report: what was created vs skipped,
   the gate proof (step 4), the initial Seeds, and the suggested next step —
   `/sdlc-frame <first milestone>`.
