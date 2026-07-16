#!/usr/bin/env bash
# Compatibility wrapper for the Python lifecycle installer. Prefer `mise run bundle:*`.
#
# Legacy forms retained:
#   install-skill-bundle.sh [--copy] [installer options]
#   install-skill-bundle.sh status|uninstall|self-test [installer options]
set -euo pipefail

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
    mise -C "$repo_root" run bundle:install -- ${args[@]+"${args[@]}"}
    core_exit=$?
    ;;
  status)
    mise -C "$repo_root" run bundle:status -- ${args[@]+"${args[@]}"}
    core_exit=$?
    ;;
  uninstall)
    mise -C "$repo_root" run bundle:uninstall -- ${args[@]+"${args[@]}"}
    core_exit=$?
    ;;
  self-test)
    mise -C "$repo_root" run self-test -- ${args[@]+"${args[@]}"}
    core_exit=$?
    ;;
esac

exit "$core_exit"
