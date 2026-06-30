#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v cao >/dev/null 2>&1; then
  echo "error: cao is not on PATH" >&2
  exit 1
fi

skill_dir="$repo_root/skills/agentic-sdlc-orchestrator"
if [ ! -f "$skill_dir/SKILL.md" ]; then
  echo "error: skill not found at $skill_dir" >&2
  exit 1
fi

cao skills add "$skill_dir" --force

for profile in "$repo_root"/cao-profiles/*.md; do
  [ -e "$profile" ] || continue
  cao install "$profile"
done

echo "installed agentic-sdlc-orchestrator CAO skill and profiles"
