#!/bin/sh
# hook: session-start-routing-primer
# hook-event: SessionStart
# hook-matcher: startup|resume|clear
#
# SessionStart routing primer for agentic-sdlc-activated repositories.
#
# Gate: BOTH predicates must hold, or this hook exits 0 with ZERO bytes of
# stdout (empty stdout on exit 0 injects nothing into the session):
#   1. .seeds/issues.jsonl under the project root is a regular, non-symlink
#      file -- the queue surface only /sdlc-init and the conductor-write
#      launcher create. .seeds alone could be a foreign Seeds queue.
#   2. AGENTS.md carries the /sdlc-init activation marker. The marker alone
#      could be a copied template.
# `compact` and `fork` matchers are deliberately absent: a compacted session
# keeps a summary of the primer and a fork inherits its parent's context.
#
# The card below is fixed reviewed bytes emitted through a quoted heredoc.
# No repository content -- branch names, seed titles, AGENTS.md text -- is
# ever interpolated into the emitted context, so an activated repository
# cannot smuggle prompt text through this hook. Gate errors degrade to
# silence at exit 0; this hook never blocks a session and never exits 2.

root="${CLAUDE_PROJECT_DIR:-$PWD}"
queue="$root/.seeds/issues.jsonl"

[ -f "$queue" ] || exit 0
[ -L "$queue" ] && exit 0
grep -q 'agentic-sdlc:start' "$root/AGENTS.md" 2>/dev/null || exit 0

cat <<'ROUTING_CARD'
[agentic-sdlc routing primer: this repository is SDLC-activated]
When the situation on the left arises, invoke the skill on the right via the
Skill tool before improvising:
- framing a run, "what next", backlog triage -> agentic-sdlc (/sdlc-frame)
- executing a planned wave in git worktrees -> agentic-sdlc (/sdlc-wave)
- mission / backlog-zero loop -> agentic-sdlc (/sdlc-mission)
- any dispatch naming a model or effort value -> model-tier-rightsizing
- exact ocx route handoff after rightsizing -> dispatching-exact-ocx-models
- commit message, PR title/body, squash text -> change-writing
- a durable architectural decision just settled -> adr-lifecycle
- "simplify" or line-count pressure on a plan or diff -> reviewing-overengineering
- gate setup, or local-green/CI-red toolchain drift -> repo-toolchain-gates
- dependent changes need separate, stacked PRs -> stacked-prs
- stacked PRs with plain gh and git tooling only -> stacked-prs-gh-cli
- scaffolding a research organization in a repository -> codex-research-os
- installing third-party skill libraries -> external-skill-libraries
Verdicts are advisory; a passing gate is evidence, never authorization for an
outward effect (push, publication, PR mutation, merge, deploy).
ROUTING_CARD
exit 0
