#!/usr/bin/env bash
set -euo pipefail

missing=0

check_cmd() {
  local name="$1"
  if command -v "$name" >/dev/null 2>&1; then
    printf 'ok: %s\n' "$name"
  else
    printf 'missing: %s\n' "$name" >&2
    missing=1
  fi
}

check_cmd git
check_cmd gh
check_cmd cao
check_cmd sd
check_cmd tmux
check_cmd codex
check_cmd claude

if command -v cao >/dev/null 2>&1; then
  if curl -sf http://localhost:9889/sessions >/dev/null 2>&1; then
    printf 'ok: cao-server http://localhost:9889\n'
  else
    printf 'warn: cao-server is not responding at http://localhost:9889\n' >&2
  fi
fi

exit "$missing"
