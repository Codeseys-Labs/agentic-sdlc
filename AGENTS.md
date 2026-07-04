# Agentic SDLC Orchestrator — agent instructions

This repo is a multi-skill, multi-host agent bundle (an "open plugin"): one `skills/`
tree in the cross-host Agent Skills format, thin per-host manifests, and a symlink
installer. Codex, Gemini CLI, OpenCode, and other AGENTS.md-aware hosts: read this file
as the router.

## What this bundle provides

- `skills/agentic-sdlc-orchestrator/` — the flagship skill: project-scale agentic SDLC
  (CAO fleet orchestration, Seeds queue, git worktree waves, mission/backlog-zero
  doctrine, tiered orchestration, evidence-graded research teams, optional cmux view
  layer). Start at its `SKILL.md`; read `references/*.md` on demand only.
- `skills/codex-research-os/` — repo-scaffolding installer for a 17-role research
  organization with claim ledgers and review gates.
- `agents/` — seven global SDLC role agents (cartographer, planner, implementer, reviewer, researcher,
  critic, integrator) in Claude `.md` and Codex `.toml` forms, plus the repo-scoped
  research roster under `agents/codex/research/`.
- `commands/` — `/sdlc-frame`, `/sdlc-wave`, `/sdlc-mission` (Claude Code slash
  commands; other hosts: invoke the flagship skill with the same intents).
- `cao-profiles/` — CAO supervisor/worker profile templates.

## Working on THIS repo

- Run `./scripts/validate-bundle.sh` before any commit — it gates frontmatter,
  name==dirname, the Codex 1024-char description cap, broken references, TOML/JSON
  parses, shell syntax, manifests, and secrets.
- Run `./scripts/install-skill-bundle.sh self-test` after installer changes.
- Version bumps: `./scripts/bump-version.sh <version>` updates every manifest in one
  shot; `--check` reports drift. Never hand-edit a single manifest's version.
- Adding a skill = adding `skills/<name>/SKILL.md` (name must equal the directory
  name; description ≤1024 chars). The installer/validator/planes pick it up
  automatically.
- Keep skills host-agnostic: no user-specific paths, no provider credentials, no
  internal hostnames. Host-specific detail belongs in per-host manifests or the
  installer.

## Installing this bundle

`./scripts/check-agentic-sdlc-prereqs.sh` then `./scripts/install-skill-bundle.sh`
(symlinks; `status`/`uninstall`/`self-test` subcommands). Claude Code alternative:
`claude plugin marketplace add <this repo>` — pick ONE path per machine, not both.
