#!/usr/bin/env bash
# Preflight for the agentic-sdlc-orchestrator kit.
# Required: git, gh, tmux, and at least ONE agent CLI (claude or codex).
# Recommended: cao (fleet control), sd (Seeds queue).
# Optional: cmux (view layer — auto-detected at runtime via CMUX_WORKSPACE_ID).
set -euo pipefail

missing=0

req() {
  if command -v "$1" >/dev/null 2>&1; then printf 'ok:       %s\n' "$1"
  else printf 'MISSING:  %s (required)\n' "$1" >&2; missing=1; fi
}
rec() {
  if command -v "$1" >/dev/null 2>&1; then printf 'ok:       %s\n' "$1"
  else printf 'warn:     %s not found (%s)\n' "$1" "$2"; fi
}

req git
req gh
req tmux

# At least one agent CLI
if command -v claude >/dev/null 2>&1 || command -v codex >/dev/null 2>&1; then
  command -v claude >/dev/null 2>&1 && printf 'ok:       claude\n'
  command -v codex  >/dev/null 2>&1 && printf 'ok:       codex\n'
else
  printf 'MISSING:  need at least one agent CLI (claude or codex)\n' >&2; missing=1
fi

rec cao "fleet control disabled — install: uv tool install --python 3.13 'git+https://github.com/awslabs/cli-agent-orchestrator.git@main'"
rec sd  "Seeds queue disabled — worktree waves will lack a queue of record"
rec cmux "view layer disabled — runs fine without it"

# cmux runtime state (presence of the binary != being inside cmux)
if [ -n "${CMUX_WORKSPACE_ID:-}" ]; then
  printf 'ok:       inside cmux (CMUX_WORKSPACE_ID set) — view layer + event bus available\n'
fi

# CAO server + trial-verified operational checks
if command -v cao >/dev/null 2>&1; then
  if curl -sf -m 2 http://localhost:9889/sessions >/dev/null 2>&1; then
    printf 'ok:       cao-server http://localhost:9889\n'
  else
    printf 'warn:     cao-server not responding (start it with provider env exported: e.g. CLAUDE_CODE_USE_BEDROCK=1 AWS_PROFILE=... cao-server)\n'
  fi
  # codex-provider preflight: CAO default 30s init timeouts are too short for slow
  # backends (e.g. Bedrock mantle) — launch dies "Read timed out" + stale processing.
  t="$(cao config get server.mcp_request_timeout 2>/dev/null || echo 30)"
  if [ "${t:-30}" -lt 180 ] 2>/dev/null; then
    printf 'warn:     server.mcp_request_timeout=%s (<180). codex workers on slow backends can fail launch. Fix: cao config set server.mcp_request_timeout 180 (and provider_init_timeout 180)\n' "$t"
  else
    printf 'ok:       cao timeouts (mcp_request_timeout=%s)\n' "$t"
  fi
fi

# codex dir-trust preflight: workers hang on the trust prompt in untrusted dirs.
if command -v codex >/dev/null 2>&1 && [ -f "${CODEX_HOME:-$HOME/.codex}/config.toml" ]; then
  cwd_target="$(pwd)"
  if grep -qF "$cwd_target" "${CODEX_HOME:-$HOME/.codex}/config.toml" 2>/dev/null; then
    printf 'ok:       codex trusts %s\n' "$cwd_target"
  else
    printf 'warn:     codex does NOT trust %s — codex workers here hang on the trust prompt. Add projects trust_level=trusted in ~/.codex/config.toml\n' "$cwd_target"
  fi
fi

exit "$missing"
