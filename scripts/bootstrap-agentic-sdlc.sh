#!/usr/bin/env bash
# Fetch this bundle into a managed location so the operator never clones by hand.
#
#   bootstrap-agentic-sdlc.sh [--dry-run] [--update] [--ref <ref>] [--print-path]
#
# This script fetches and reports. It never trusts a config, never installs a
# toolchain, and never installs bundle entries: those are separate approvals the
# operator gives afterwards, against a tree they have read. It prints the exact
# remaining commands instead of running them.
#
# Requires mise and git. Neither is installed here; a missing one is a named exit.
set -euo pipefail

readonly DEFAULT_REMOTE='https://github.com/Codeseys-Labs/agentic-sdlc.git'
readonly DEFAULT_REF='main'

remote="${AGENTIC_SDLC_REMOTE:-$DEFAULT_REMOTE}"
ref="${AGENTIC_SDLC_REF:-$DEFAULT_REF}"
managed_home="${AGENTIC_SDLC_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/agentic-sdlc}"
state_home="${XDG_STATE_HOME:-$HOME/.local/state}/agentic-sdlc"
receipt="$state_home/bootstrap-receipt.json"

dry_run=0
update=0
print_path=0

die() {
  printf 'error: %s\n' "$1" >&2
  exit "${2:-2}"
}

note() {
  printf '%s\n' "$1"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --update) update=1; shift ;;
    --print-path) print_path=1; shift ;;
    --ref) [ "$#" -ge 2 ] || die '--ref needs a value'; ref="$2"; shift 2 ;;
    --remote) [ "$#" -ge 2 ] || die '--remote needs a value'; remote="$2"; shift 2 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

if [ "$print_path" -eq 1 ]; then
  printf '%s\n' "$managed_home"
  exit 0
fi

for tool in git mise; do
  command -v "$tool" >/dev/null 2>&1 ||
    die "$tool is required and was not found on PATH"
done

# What this run would do, before it does any of it. A dry run stops here.
note 'agentic-sdlc bootstrap'
note "  remote        : $remote"
note "  ref           : $ref"
note "  managed clone : $managed_home"
note "  receipt       : $receipt"
note ''

existing=0
if [ -e "$managed_home" ]; then
  [ -d "$managed_home" ] ||
    die "managed path exists and is not a directory: $managed_home"
  if [ -d "$managed_home/.git" ]; then
    existing=1
  elif [ -n "$(ls -A -- "$managed_home" 2>/dev/null)" ]; then
    die "managed path exists, is not a git clone, and is not empty: $managed_home"
  fi
fi

if [ "$existing" -eq 1 ]; then
  current_remote="$(git -C "$managed_home" remote get-url origin 2>/dev/null || true)"
  current_commit="$(git -C "$managed_home" rev-parse HEAD 2>/dev/null || true)"
  current_ref="$(git -C "$managed_home" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  [ -n "$current_commit" ] ||
    die "managed path has a .git directory but no resolvable HEAD: $managed_home"

  note 'existing managed clone found:'
  note "  origin : ${current_remote:-<none>}"
  note "  ref    : ${current_ref:-<detached>}"
  note "  commit : $current_commit"
  note ''

  # Refuse rather than clobber. Each refusal names what it saw.
  [ "$current_remote" = "$remote" ] ||
    die "managed clone points at '$current_remote', not '$remote'; move or remove it first" 3
  if ! git -C "$managed_home" diff --quiet HEAD 2>/dev/null ||
     [ -n "$(git -C "$managed_home" status --porcelain 2>/dev/null)" ]; then
    die "managed clone has uncommitted or untracked changes; resolve them first: $managed_home" 3
  fi
  if [ "$update" -eq 0 ]; then
    note 'nothing to do: the managed clone is present and clean. Re-run with --update to fetch.'
  else
    [ "$current_ref" = "$ref" ] ||
      die "managed clone is on '$current_ref', not the requested '$ref'; check it out first" 3
    if [ "$dry_run" -eq 1 ]; then
      note "dry run: would fetch '$ref' and fast-forward only."
    else
      git -C "$managed_home" fetch --depth 1 origin "$ref"
      git -C "$managed_home" merge --ff-only FETCH_HEAD ||
        die "'$ref' does not fast-forward onto the managed clone; resolve it manually" 3
      current_commit="$(git -C "$managed_home" rev-parse HEAD)"
      note "updated to $current_commit"
    fi
  fi
else
  if [ "$dry_run" -eq 1 ]; then
    note "dry run: would run 'git clone --depth 1 --branch $ref $remote $managed_home'."
    note 'dry run: would record the resolved commit, then stop and print the remaining steps.'
    exit 0
  fi
  mkdir -p -- "$(dirname -- "$managed_home")"
  git clone --depth 1 --branch "$ref" -- "$remote" "$managed_home"
  current_commit="$(git -C "$managed_home" rev-parse HEAD)"
  current_ref="$ref"
  note ''
  note "cloned $ref at $current_commit"
fi

if [ "$dry_run" -eq 1 ]; then
  note 'dry run: would record the resolved commit, then stop and print the remaining steps.'
  exit 0
fi

# The receipt records what was fetched, for audit and reproduction. It lives outside
# the clone so recording it never makes the tree dirty.
mkdir -p -- "$state_home"
printf '{\n  "remote": "%s",\n  "ref": "%s",\n  "commit": "%s",\n  "path": "%s",\n  "recorded_by": "bootstrap-agentic-sdlc.sh"\n}\n' \
  "$remote" "${current_ref:-$ref}" "$current_commit" "$managed_home" >"$receipt.tmp"
mv -- "$receipt.tmp" "$receipt"

trust_state='unknown'
if trust_line="$(mise -C "$managed_home" trust --show 2>/dev/null)"; then
  case "$trust_line" in
    *untrusted*) trust_state='untrusted' ;;
    *trusted*) trust_state='trusted' ;;
  esac
fi

note ''
note "recorded $receipt"
note ''
note 'Transport was authenticated by HTTPS. That authenticates the connection, not the'
note 'contents: nothing here verifies a signature over the commit above. Read the tree'
note 'before you trust it.'
note ''
note "Remaining steps, each its own approval (config trust is a persistent mutation):"
note ''
note "  1. Review the two files that trust authorizes:"
note "       \$EDITOR $managed_home/mise.toml"
note "       \$EDITOR $managed_home/mise.lock"
note "  2. Trust that exact reviewed config path (currently: $trust_state):"
note "       mise trust $managed_home/mise.toml"
note "  3. Resolve the locked toolchain:"
note "       mise -C $managed_home --locked install"
note "  4. Install this host's bundle entries:"
note "       mise -C $managed_home run bundle:install"
note ''
note 'To remove everything this script created:'
note "  rm -rf $managed_home $state_home"
note ''
note 'This bootstrap reports evidence about this run only. It authorizes nothing.'
