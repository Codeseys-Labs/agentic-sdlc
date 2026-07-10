# CAO Profiles

This is an optional adapter reference. Load it only after the user has explicitly selected
CAO. Nothing in the baseline SDLC loop depends on CAO, cmux, or tmux.

Use this reference when installing or selecting the CAO profiles bundled with this repo.

## Install

From the repo root:

```bash
./scripts/install-cao-kit.sh
```

This installs:

- The `agentic-sdlc-orchestrator` skill into CAO.
- Profile templates from `cao-profiles/`.

The script requires `cao` on PATH. Start `cao-server` separately before launching sessions.

CAO-launched Codex/Claude workers load CAO skills with the `mcp__cao-mcp-server__load_skill` tool, not provider-native `Skill(...)`. Profiles that need CAO skills should include `cao-mcp-server`.

## Profiles

`codex-macro-orchestrator`

- Provider: Codex.
- Role: entrypoint conductor.
- Use for project framing, Seeds queue ownership, CAO delegation, worktree routing, final verification, and PR/commit preparation.
- Should remain the only actor that closes Seeds and integrates branches.

`codex-planner`

- Provider: Codex.
- Role: planner/decomposer.
- Use for architecture plans, Seeds dependency graph proposals, gates, and rollback plans.

`codex-implementer`

- Provider: Codex.
- Role: bounded implementation worker.
- Use inside a dedicated worktree for one Seed or one workstream.

`codex-reviewer`

- Provider: Codex.
- Role: review worker.
- Use for snapshot/diff review. Prefer read-only Codex profiles if configured locally.

`claude-ultracode-workflow`

- Provider: Claude Code.
- Role: nested dynamic workflow worker.
- Use when one bounded workstream benefits from Claude Code subagents or dynamic workflows.
- Keep its scope narrow: one Seed, one subsystem, or one workstream. It reports back to the Codex macro conductor.

## Launch Pattern

```bash
cao-server

cao launch --agents codex-macro-orchestrator --provider codex --headless --yolo \
  --session-name agentic-sdlc-<slug> \
  --working-directory '/absolute/path/to/project' \
  "Use $agentic-sdlc-orchestrator to frame this project task, prime Seeds, and run a bounded worktree wave with the selected CAO adapter."
```

Use `CAO_ENABLE_WORKING_DIRECTORY=true` when workers need explicit worktree paths through MCP tools.

## Profile Safety

- CAO defaults can bypass approvals in non-interactive sessions. Use named Codex/Claude profiles with non-interactive read-only or workspace-write policies when possible.
- Never expose secrets in profile prompts.
- Keep provider-specific credentials in the provider's normal auth store, not this repo.
