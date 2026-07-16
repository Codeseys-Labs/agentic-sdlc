#!/bin/bash
# Preflight and installed Seeds launcher adapter for the agentic-sdlc-orchestrator kit.
# Mise remains the sole bootstrap prerequisite. The installed flagship launcher is the only
# runtime authority: it admits a locked tuple during bootstrap and inspects its receipt later.
# No ambient node, bun, sd, git, npm, or mise configuration supplies an execution fallback.
set -euo pipefail

AGENTIC_SDLC_SEEDS_VERSION=0.5.14
AGENTIC_SDLC_NODE_TOOL=node@22.22.3
AGENTIC_SDLC_BUN_TOOL=bun@1.3.10
AGENTIC_SDLC_SEEDS_TOOL="npm:@os-eco/seeds-cli@${AGENTIC_SDLC_SEEDS_VERSION}"
AGENTIC_SDLC_LAUNCHER="${AGENTIC_SDLC_LAUNCHER:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../skills/agentic-sdlc-orchestrator/tools" && pwd -P)/seeds-launcher.mjs}"

agentic_sdlc_exact_node() (
  child_status=2
  cleanup() { :; }
  # Establish cleanup before resolving or spawning any executable. The installed launcher owns
  # state; this guard preserves the wrapper's exact child status on every exit path.
  trap 'cleanup' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  if [ "$#" -lt 1 ]; then
    printf 'usage: agentic_sdlc_exact_node <launcher-args...>\n' >&2
    return 2
  fi
  if ! command -v mise >/dev/null 2>&1; then
    printf 'MISSING: mise (sole bootstrap prerequisite)\n' >&2
    return 2
  fi
  if ! node_root=$(mise --no-config where "$AGENTIC_SDLC_NODE_TOOL" 2>/dev/null); then
    printf 'MISSING: exact Node root from mise\n' >&2
    return 2
  fi
  case "${OS:-}" in
    Windows_NT) exact_node="$node_root/node.exe" ;;
    *) exact_node="$node_root/bin/node" ;;
  esac
  if [ ! -f "$exact_node" ]; then
    printf 'MISSING: exact Node executable beneath %s\n' "$node_root" >&2
    return 2
  fi
  # $@ is passed as separate argv values. Node runs the installed launcher without a shell.
  set +e
  "$exact_node" "$AGENTIC_SDLC_LAUNCHER" "$@"
  child_status=$?
  set -e
  cleanup
  trap - EXIT
  return "$child_status"
)

# Compatibility shell functions retain the documented Seeds(<target>, <args...>) notation while
# delegating all validation and execution to the installed receipt contract.
agentic_sdlc_seeds() {
  if [ "$#" -lt 2 ]; then
    printf 'usage: agentic_sdlc_seeds <target> <allowed-sd-command> [args...]\n' >&2
    return 2
  fi
  seeds_target=$1
  shift
  agentic_sdlc_exact_node inspect --target "$seeds_target" "$@"
}

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0
fi

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
req mise
if [ "${AGENTIC_SDLC_GITHUB_REQUIRED:-0}" = "1" ]; then req gh
else rec gh "GitHub publication adapter skipped; local Git orchestration is unaffected"; fi
if [ ! -f "$AGENTIC_SDLC_LAUNCHER" ]; then
  printf 'MISSING: installed flagship Seeds launcher %s\n' "$AGENTIC_SDLC_LAUNCHER" >&2
  missing=1
elif ! agentic_sdlc_exact_node inspect --target "$(pwd -P)" --version >/dev/null 2>&1; then
  printf 'MISSING: valid locked active Seeds tuple receipt (bootstrap explicitly from reviewed distribution)\n' >&2
  missing=1
else
  printf 'ok:       locked Seeds %s active receipt\n' "$AGENTIC_SDLC_SEEDS_VERSION"
fi

host_found=0
for host_cli in claude codex gemini; do
  if command -v "$host_cli" >/dev/null 2>&1; then printf 'ok:       %s host CLI\n' "$host_cli"; host_found=1; fi
done
if [ "$host_found" -eq 0 ] && [ "${AGENTIC_SDLC_HOST_READY:-0}" = "1" ]; then
  printf 'ok:       current skill-capable host declared (AGENTIC_SDLC_HOST_READY=1)\n'
elif [ "$host_found" -eq 0 ]; then
  printf 'warn:     no known host CLI found; continue from the current skill-capable host or set AGENTIC_SDLC_HOST_READY=1\n'
fi
opt tmux "session/view backend skipped; native orchestration is unaffected"
opt cmux "view/event adapter skipped; native orchestration is unaffected"
if command -v cmux >/dev/null 2>&1 && [ -n "${CMUX_WORKSPACE_ID:-}" ]; then printf 'optional: active cmux view/event adapter detected\n'; fi
exit "$missing"
