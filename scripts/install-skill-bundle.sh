#!/usr/bin/env bash
# Compatibility wrapper for the Python lifecycle installer. Prefer `mise run bundle:*`.
#
# Legacy forms retained:
#   install-skill-bundle.sh [--copy] [installer options]
#   install-skill-bundle.sh status|uninstall|self-test [installer options]
#   INSTALL_CAO=1 install-skill-bundle.sh [legacy install options]
set -euo pipefail

retirement_message='CAO has been retired; use native Frame/Wave/Mission instead.'

if [ "${INSTALL_CAO:-0}" = "1" ]; then
  printf '%s\n' "$retirement_message" >&2
  exit 2
fi

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v mise >/dev/null 2>&1; then
  printf '%s\n' 'error: mise is required; install it, then run mise run bundle:install.' >&2
  exit 2
fi

command=install
if [ "${1:-}" = "status" ] || [ "${1:-}" = "uninstall" ] || [ "${1:-}" = "self-test" ]; then
  command="$1"
  shift
fi

args=()
if [ "${1:-}" = "--copy" ]; then
  args+=(--mode copy)
  shift
fi
args+=("$@")

case "$command" in
  install)
    mise -C "$repo_root" run bundle:install -- "${args[@]}"
    core_exit=$?
    ;;
  status)
    mise -C "$repo_root" run bundle:status -- "${args[@]}"
    core_exit=$?
    ;;
  uninstall)
    mise -C "$repo_root" run bundle:uninstall -- "${args[@]}"
    core_exit=$?
    ;;
  self-test)
    mise -C "$repo_root" run self-test -- "${args[@]}"
    core_exit=$?
    ;;
esac

exit "$core_exit"
