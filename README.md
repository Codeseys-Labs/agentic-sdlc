# Agentic SDLC Orchestrator

Reusable Codex + Claude Code + CAO operating kit for project-scale agentic software delivery.

The intended shape:

```text
Codex entrypoint
  -> CAO fleet/session bus
  -> Codex, Claude Code, and other CLI workers
  -> Seeds queue
  -> git worktrees
  -> tests/review
  -> squash/rebase/PR
```

## Contents

- `skills/agentic-sdlc-orchestrator/`: installable skill for Codex/CAO-compatible agents.
- `cao-profiles/`: CAO profile templates for macro orchestration, planning, implementation, review, and Claude Code nested dynamic workflows.
- `scripts/check-agentic-sdlc-prereqs.sh`: local prerequisite check.
- `scripts/install-cao-kit.sh`: installs the skill and profiles into CAO.

## Install Into CAO

```bash
./scripts/check-agentic-sdlc-prereqs.sh
./scripts/install-cao-kit.sh
```

Start CAO separately:

```bash
cao-server
```

Launch a Codex macro conductor:

```bash
cao launch --agents codex-macro-orchestrator --provider codex --headless --yolo \
  --session-name agentic-sdlc-demo \
  --working-directory '/absolute/path/to/project' \
  'Use $agentic-sdlc-orchestrator to frame the task, prime Seeds, and run a bounded CAO/DWL worktree wave.'
```

## Status

Initial scaffold. Treat profiles as templates until validated on a real repository with CAO, Codex, Claude Code, Seeds, and tmux installed.
