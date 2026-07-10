#!/bin/bash
# Preflight for the agentic-sdlc-orchestrator kit.
# Required: git, gh, and sd (Seeds queue).
# The current skill-capable host is detected informationally because not every provider
# exposes a stable CLI executable name.
# Optional enhancements: cao (durable/mixed-engine sessions), tmux (adapter backend),
# cmux (active view/event layer), and jj (workspace substrate). Native orchestration
# remains fully supported when every optional enhancement is absent.
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
opt() {
  if command -v "$1" >/dev/null 2>&1; then printf 'optional: %s available\n' "$1"
  else printf 'optional: %s not found (%s)\n' "$1" "$2"; fi
}

req git
req gh
req sd

# Known agent CLIs are useful evidence, but execution may already be inside another
# skill-capable native host. AGENTIC_SDLC_HOST_READY=1 makes that context explicit.
host_found=0
for host_cli in claude codex gemini; do
  if command -v "$host_cli" >/dev/null 2>&1; then
    printf 'ok:       %s host CLI\n' "$host_cli"
    host_found=1
  fi
done
if [ "$host_found" -eq 0 ] && [ "${AGENTIC_SDLC_HOST_READY:-0}" = "1" ]; then
  printf 'ok:       current skill-capable host declared (AGENTIC_SDLC_HOST_READY=1)\n'
elif [ "$host_found" -eq 0 ]; then
  printf 'warn:     no known host CLI found; continue from the current skill-capable host or set AGENTIC_SDLC_HOST_READY=1\n'
fi
opt cao  "durable cross-CLI adapter skipped; native orchestration is unaffected"
opt tmux "session/view backend skipped; native orchestration is unaffected"
opt cmux "view/event adapter skipped; native orchestration is unaffected"

# jj version + colocated-repo detection (an unusable optional binary never fails preflight)
if command -v jj >/dev/null 2>&1; then
  ver="$(jj --version 2>/dev/null | head -1 || true)"
  if [ -n "$ver" ]; then
    printf 'optional: jj version: %s\n' "$ver"
    root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    if [ -d "$root/.jj" ]; then
      printf 'optional: colocated jj repo detected at %s\n' "$root"
      printf 'note:     git hooks do NOT fire on jj commits — mise run check + CI carry the gates (see references/jj-vcs.md)\n'
    fi
  else
    printf 'optional: jj command is present but unusable; git worktrees remain available\n'
  fi
else
  printf 'optional: jj not found; git worktrees remain the default substrate\n'
fi

# cmux is usable only when both its CLI and an active workspace are already present.
if command -v cmux >/dev/null 2>&1 && [ -n "${CMUX_WORKSPACE_ID:-}" ]; then
  printf 'optional: active cmux view/event adapter detected\n'
fi

# Inspect CAO-specific health only when its optional server is already running.
if command -v cao >/dev/null 2>&1; then
  if curl -sf -m 2 http://localhost:9889/sessions >/dev/null 2>&1; then
    printf 'optional: active cao-server detected at http://localhost:9889\n'
    # CAO default 30s init timeouts can be too short for slow backends.
    t="$(cao config get server.mcp_request_timeout 2>/dev/null || echo 30)"
    if [ "${t:-30}" -lt 180 ] 2>/dev/null; then
      printf 'note:     CAO adapter timeout=%s; raise it only if this run selects CAO on a slow backend\n' "$t"
    else
      printf 'optional: CAO adapter timeout configured (mcp_request_timeout=%s)\n' "$t"
    fi
  else
    printf 'optional: cao is installed but inactive; native orchestration remains fully supported\n'
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
