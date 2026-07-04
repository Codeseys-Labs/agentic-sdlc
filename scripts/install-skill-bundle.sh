#!/usr/bin/env bash
# Install the agentic-sdlc-orchestrator skill bundle globally for every CLI agent
# present on this machine. Idempotent; re-run after pulling updates.
#
#   Claude Code -> ~/.claude/skills/agentic-sdlc-orchestrator/   (symlink to repo)
#   Codex       -> $CODEX_HOME/skills/agentic-sdlc-orchestrator/ (symlink; default ~/.codex)
#   CAO         -> cao skills add + cao-profiles/ install         (only if `cao` on PATH)
#
# Symlinks keep installs live-updating with `git pull`. Pass --copy to copy instead
# (for machines where the repo clone is temporary).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skill_src="$repo_root/skills/agentic-sdlc-orchestrator"
[ -f "$skill_src/SKILL.md" ] || { echo "error: skill not found at $skill_src" >&2; exit 1; }

mode="link"
[ "${1:-}" = "--copy" ] && mode="copy"

install_into() {
  local dest_parent="$1" label="$2"
  local dest="$dest_parent/agentic-sdlc-orchestrator"
  mkdir -p "$dest_parent"
  rm -rf "$dest"
  if [ "$mode" = "link" ]; then
    ln -s "$skill_src" "$dest"
  else
    cp -R "$skill_src" "$dest"
  fi
  echo "✓ $label: $dest ($mode)"
}

# Link one file/dir into a parent, replacing prior symlink; hard-stop on real dirs we don't own.
link_item() {
  local src="$1" dest_parent="$2" label="$3"
  local dest="$dest_parent/$(basename "$src")"
  mkdir -p "$dest_parent"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    echo "  ! SKIP $label: $dest exists and is not a symlink (won't clobber)"; return 0
  fi
  rm -f "$dest"
  if [ "$mode" = "link" ]; then ln -s "$src" "$dest"; else cp -R "$src" "$dest"; fi
  echo "  ✓ $label: $dest"
}

# Claude Code (user-level: skill + role agents + slash commands)
if [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1; then
  install_into "$HOME/.claude/skills" "Claude Code skill"
  for a in "$repo_root"/agents/claude/*.md; do
    [ -e "$a" ] || continue; link_item "$a" "$HOME/.claude/agents" "Claude agent $(basename "$a" .md)"
  done
  for c in "$repo_root"/commands/*.md; do
    [ -e "$c" ] || continue; link_item "$c" "$HOME/.claude/commands" "Claude command /$(basename "$c" .md)"
  done
else
  echo "- Claude Code not detected; skipped"
fi

# Codex ($CODEX_HOME/skills — NOT ~/.agents/skills; docs are wrong about that path)
codex_home="${CODEX_HOME:-$HOME/.codex}"
if [ -d "$codex_home" ] || command -v codex >/dev/null 2>&1; then
  install_into "$codex_home/skills" "Codex skill"
  # Codex caps skill description: at 1024 chars — warn if over (silently skipped otherwise).
  desc_len=$(awk '/^description:/{f=1} f&&/^---$/{exit} f' "$skill_src/SKILL.md" | wc -c | tr -d ' ')
  [ "$desc_len" -gt 1024 ] && echo "  ! WARNING: description ${desc_len} chars > Codex 1024 cap — skill will be silently skipped by Codex" || true
  for t in "$repo_root"/agents/codex/*.toml; do
    [ -e "$t" ] || continue; link_item "$t" "$codex_home/agents" "Codex role $(basename "$t" .toml)"
  done
else
  echo "- Codex not detected; skipped"
fi

# CAO (skill + profiles), only if installed
if command -v cao >/dev/null 2>&1; then
  cao skills add "$skill_src" --force
  for profile in "$repo_root"/cao-profiles/*.md; do
    [ -e "$profile" ] || continue
    cao install "$profile"
  done
  echo "✓ CAO: skill + $(ls "$repo_root"/cao-profiles/*.md | wc -l | tr -d ' ') profiles"
else
  echo "- CAO not detected; skipped (install: uv tool install --python 3.13 'git+https://github.com/awslabs/cli-agent-orchestrator.git@main')"
fi

echo "done. cmux integration activates automatically when CMUX_WORKSPACE_ID is set — no install step."
