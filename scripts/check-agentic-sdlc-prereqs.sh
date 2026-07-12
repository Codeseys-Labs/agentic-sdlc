#!/bin/bash
# Preflight for the agentic-sdlc-orchestrator kit.
# Required: git, gh, and sd (Seeds queue).
# The current skill-capable host is detected informationally because not every provider
# exposes a stable CLI executable name.
# Optional enhancements: tmux (adapter backend) and cmux (active view/event layer).
# Native orchestration remains fully supported when optional enhancements are absent.
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
opt tmux "session/view backend skipped; native orchestration is unaffected"
opt cmux "view/event adapter skipped; native orchestration is unaffected"

# cmux is usable only when both its CLI and an active workspace are already present.
if command -v cmux >/dev/null 2>&1 && [ -n "${CMUX_WORKSPACE_ID:-}" ]; then
  printf 'optional: active cmux view/event adapter detected\n'
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
