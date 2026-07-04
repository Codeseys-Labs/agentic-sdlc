#!/usr/bin/env bash
# Install the agentic-sdlc-orchestrator skill bundle globally for every CLI agent
# present on this machine. Idempotent; re-run after pulling updates.
#
#   Claude Code -> ~/.claude/skills + ~/.claude/agents + ~/.claude/commands (symlinks)
#   Codex       -> $CODEX_HOME/skills + $CODEX_HOME/agents (symlinks; default ~/.codex)
#   CAO         -> cao skills add + cao-profiles/ install (COPIES — re-run after git pull)
#
# USAGE:
#   install-skill-bundle.sh            # install/refresh (symlink mode)
#   install-skill-bundle.sh --copy     # copy instead of symlink (temporary clones)
#   install-skill-bundle.sh status     # show link health per target, exit 1 if broken
#   install-skill-bundle.sh uninstall  # remove everything this script installed
#   install-skill-bundle.sh self-test  # run install+status+uninstall in a throwaway HOME
#
# Symlink planes live-update with `git pull`; the CAO plane COPIES into its store, so
# re-run this script after pulling to refresh CAO. Don't dual-install: if you use the
# marketplace path (`claude plugin marketplace add`), skip the skills symlink for that
# machine or the skill registers twice (bare + namespaced).
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
skill_src="$repo_root/skills/agentic-sdlc-orchestrator"
[ -f "$skill_src/SKILL.md" ] || { echo "error: skill not found at $skill_src" >&2; exit 1; }

codex_home="${CODEX_HOME:-$HOME/.codex}"

# Everything we own at destinations (uninstall/status walk this list).
owned_targets() {
  echo "$HOME/.claude/skills/agentic-sdlc-orchestrator"
  for a in "$repo_root"/agents/claude/*.md;  do [ -e "$a" ] && echo "$HOME/.claude/agents/$(basename "$a")"; done
  for c in "$repo_root"/commands/*.md;       do [ -e "$c" ] && echo "$HOME/.claude/commands/$(basename "$c")"; done
  echo "$codex_home/skills/agentic-sdlc-orchestrator"
  for t in "$repo_root"/agents/codex/*.toml; do [ -e "$t" ] && echo "$codex_home/agents/$(basename "$t")"; done
}

case "${1:-}" in
  status)
    bad=0
    while IFS= read -r tgt; do
      if [ -L "$tgt" ]; then
        if [ -e "$tgt" ]; then echo "ok:      $tgt"; else echo "BROKEN:  $tgt (dangling symlink)"; bad=1; fi
      elif [ -e "$tgt" ]; then echo "copy:    $tgt (not a symlink — copy mode or foreign file)"
      else echo "absent:  $tgt"; fi
    done < <(owned_targets)
    command -v cao >/dev/null 2>&1 && { cao skills list 2>/dev/null | grep -q agentic-sdlc-orchestrator && echo "ok:      CAO skill store" || echo "absent:  CAO skill store"; }
    exit "$bad"
    ;;
  uninstall)
    while IFS= read -r tgt; do
      if [ -L "$tgt" ]; then rm -f "$tgt"; echo "removed: $tgt"
      elif [ -e "$tgt" ]; then echo "kept:    $tgt (not a symlink — remove manually if desired)"; fi
    done < <(owned_targets)
    echo "note: CAO store entries persist; remove with 'cao skills remove agentic-sdlc-orchestrator' if supported."
    exit 0
    ;;
  self-test)
    tmp_home="$(mktemp -d)"
    echo "self-test in HOME=$tmp_home"
    mkdir -p "$tmp_home/.claude" "$tmp_home/.codex"
    # SKIP_CAO: cao's store is global (not HOME-keyed) — self-test must not touch it.
    HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" SKIP_CAO=1 bash "$0"
    HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" SKIP_CAO=1 bash "$0" status
    HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" SKIP_CAO=1 bash "$0" uninstall
    # after uninstall, status must show nothing broken and nothing owned remaining as symlink
    if HOME="$tmp_home" CODEX_HOME="$tmp_home/.codex" bash "$0" status | grep -q '^ok:.*symlink\|^BROKEN'; then
      echo "self-test FAILED: leftovers after uninstall"; rm -rf "$tmp_home"; exit 1
    fi
    rm -rf "$tmp_home"
    echo "self-test PASSED (install → status → uninstall clean)"
    exit 0
    ;;
esac

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

# CAO (skill + profiles), only if installed. SKIP_CAO=1 skips (self-test: CAO's store is
# global, not HOME-keyed — a sandboxed run must not write it).
if [ -n "${SKIP_CAO:-}" ]; then
  echo "- CAO plane skipped (SKIP_CAO set)"
elif command -v cao >/dev/null 2>&1; then
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
