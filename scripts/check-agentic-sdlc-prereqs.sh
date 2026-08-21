#!/bin/bash
# Preflight and installed Seeds launcher adapter for the agentic-sdlc kit.
# Mise remains the sole bootstrap prerequisite. The installed flagship launcher is the only
# runtime authority: it admits a locked tuple during bootstrap and inspects its receipt later.
# No ambient node, bun, sd, git, npm, or mise configuration supplies an execution fallback.
set -euo pipefail

AGENTIC_SDLC_SEEDS_VERSION=0.5.15
AGENTIC_SDLC_NODE_TOOL=node@22.23.2
AGENTIC_SDLC_BUN_TOOL=bun@1.4.0
AGENTIC_SDLC_SEEDS_TOOL="npm:@os-eco/seeds-cli@${AGENTIC_SDLC_SEEDS_VERSION}"
AGENTIC_SDLC_LAUNCHER="${AGENTIC_SDLC_LAUNCHER:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../skills/agentic-sdlc/tools" && pwd -P)/seeds-launcher.mjs}"

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

# Exact-runtime front doors. Read-only inspection, conductor initialization, and conductor queue
# recording remain distinct so a caller cannot accidentally route a mutating verb through inspect.
agentic_sdlc_seeds() (
  if [ "$#" -lt 2 ]; then
    printf 'usage: agentic_sdlc_seeds <target> <allowed-read-only-command> [args...]\n' >&2
    return 2
  fi
  seeds_target=$1
  shift
  agentic_sdlc_exact_node inspect --target "$seeds_target" "$@"
)

agentic_sdlc_seeds_init() {
  if [ "$#" -ne 1 ]; then
    printf 'usage: agentic_sdlc_seeds_init <target>\n' >&2
    return 2
  fi
  agentic_sdlc_exact_node record --target "$1" --queue-writer conductor --expect-queue absent init
}

agentic_sdlc_seeds_record() (
  if [ "$#" -lt 3 ]; then
    printf 'usage: agentic_sdlc_seeds_record <target> <expected-sha256> <create|update> [args...]\n' >&2
    return 2
  fi
  seeds_target=$1
  expected_queue=$2
  shift 2
  agentic_sdlc_exact_node record --target "$seeds_target" --queue-writer conductor --expect-queue "$expected_queue" "$@"
)

if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  return 0
fi

# Exit vocabulary for the executed (non-sourced) preflight check, kept in one derivation
# point so a later change cannot silently reintroduce Decision 9's 1-versus-5 confusion.
EXIT_OK=0
EXIT_INTERNAL=1
EXIT_USAGE=2
# The check ran to completion and named at least one missing required prerequisite.
# Deliberately outside the reserved 0-4 block, exactly as `scripts/gate_baseline.py`'s
# `EXIT_WORSENED` is: "I checked, and something is missing" is not "I failed to check",
# so it may never collide with EXIT_INTERNAL.
EXIT_MISSING=5

case "${1:-}" in
  --help|-h)
    cat <<'USAGE'
usage: check-agentic-sdlc-prereqs.sh [--help]

Read-only preflight check for the agentic-sdlc kit. Prints each prerequisite's state and
exits:
  0  every required prerequisite is present
  2  an unrecognized argument was supplied (this check takes none besides --help)
  5  the check completed and named at least one MISSING required prerequisite
  1  reserved for a real internal failure of the check itself, never a named outcome
USAGE
    exit "$EXIT_OK"
    ;;
  '') ;;
  *)
    printf 'unknown argument: %s\n' "$1" >&2
    printf 'usage: check-agentic-sdlc-prereqs.sh [--help]\n' >&2
    exit "$EXIT_USAGE"
    ;;
esac

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
if [ "$missing" -eq 0 ]; then
  exit "$EXIT_OK"
else
  exit "$EXIT_MISSING"
fi
