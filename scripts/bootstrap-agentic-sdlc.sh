#!/usr/bin/env bash
# Fetch this bundle into a managed location so the operator never clones by hand.
#
# Usage: bootstrap-agentic-sdlc.sh [--dry-run] [--update] [--remote <git-url>]
#                                  [--ref <ref>] [--print-path]
#
# Fetch this bundle into a managed location and stop. --remote selects the exact
# Git remote (default: https://github.com/Codeseys-Labs/agentic-sdlc.git) and is
# refused when it carries credentials in its userinfo; --ref selects the branch
# or tag (default: main). --update permits a fast-forward update of an exact
# clean managed clone. --dry-run and --print-path write nothing.
#
# This script never trusts a config, installs a toolchain, installs bundle entries,
# edits PATH, or verifies a signature over the fetched commit. Review the tree and
# make each later approval separately; the printed handoff names exact checks.
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

# A remote's userinfo is a credential channel, and every consumer of the value keeps
# it: git writes the URL verbatim into the clone's .git/config and exposes it in its
# own argv, this script records it in the receipt and prints it in the handoff, and a
# later run reads it back out of the clone and echoes it again. Refuse rather than
# redact — a partial redaction still leaks — and never echo the value while refusing.
remote_carries_userinfo() {
  local url=$1 scheme authority userinfo
  case "$url" in
    *://*)
      scheme=${url%%://*}
      authority=${url#*://}
      authority=${authority%%/*}
      case "$authority" in
        *@*) userinfo=${authority%%@*} ;;
        *) return 1 ;;
      esac
      ;;
    # scp-style [user@]host:path. The colon this pattern requires after the '@' is
    # the host:path separator, so a path that merely contains '@' is not userinfo.
    *@*:*) scheme=ssh; userinfo=${url%%@*} ;;
    *) return 1 ;;
  esac
  # SSH takes a username and never a secret, so 'git@host' stays an ordinary remote in
  # both the scp-style and the ssh:// spelling; only a password-shaped userinfo is a
  # credential there. Every other transport treats userinfo as a credential channel,
  # where even a lone username can be the whole token.
  case "$scheme" in
    ssh|git+ssh|ssh+git) case "$userinfo" in *:*) return 0 ;; esac ;;
    *) return 0 ;;
  esac
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) dry_run=1; shift ;;
    --update) update=1; shift ;;
    --print-path) print_path=1; shift ;;
    --ref) [ "$#" -ge 2 ] || die '--ref needs a value'; ref="$2"; shift 2 ;;
    --remote) [ "$#" -ge 2 ] || die '--remote needs a value'; remote="$2"; shift 2 ;;
    -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

# Refuse before the value reaches output, the receipt, git's argv, or the clone config.
if remote_carries_userinfo "$remote"; then
  die '--remote carries credentials in its userinfo, which this run would record in the receipt and in the clone config; pass a credential-free URL and let a Git credential helper or an SSH key hold the secret' 3
fi

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
  requested_commit="$(git -C "$managed_home" rev-parse --verify "$ref^{commit}" 2>/dev/null || true)"
  [ -n "$current_commit" ] ||
    die "managed path has a .git directory but no resolvable HEAD: $managed_home"
  # A clone recorded before this refusal existed still holds the secret in its config.
  if remote_carries_userinfo "${current_remote:-}"; then
    die "managed clone origin carries credentials in its userinfo; move or remove it first: $managed_home" 3
  fi

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
    if [ -n "$requested_commit" ]; then
      [ "$current_commit" = "$requested_commit" ] ||
        die "managed clone HEAD '$current_commit' does not match the requested ref '$ref'; re-run with --update only after reviewing that ref" 3
    elif [ "$current_ref" != "$ref" ]; then
      die "managed clone is on '${current_ref:-<detached>}' and the requested ref '$ref' is not available locally; re-run with --update only after reviewing that ref" 3
    fi
    note 'nothing to do: the managed clone is present, clean, and matches the requested ref. Re-run with --update to fetch.'
  elif [ "$dry_run" -eq 1 ]; then
    note "dry run: would fetch '$ref' and fast-forward only."
  else
    # Do not repeat the clone's shallow boundary here. Fetching one new tip at
    # depth 1 can create a second shallow root and make an ordinary branch
    # advance look unrelated to its own managed clone.
    git -C "$managed_home" fetch origin "$ref"
    fetched_commit="$(git -C "$managed_home" rev-parse --verify 'FETCH_HEAD^{commit}')"
    if [ "$current_ref" = "$ref" ]; then
      git -C "$managed_home" merge --ff-only FETCH_HEAD ||
        die "'$ref' does not fast-forward onto the managed clone; resolve it manually" 3
    elif [ "$current_ref" = HEAD ] && [ "$current_commit" = "$fetched_commit" ]; then
      : # An exact tag checkout is already current and remains detached by design.
    else
      die "managed clone is on '${current_ref:-<detached>}' at '$current_commit', not the requested '$ref' at '$fetched_commit'; select the intended ref manually" 3
    fi
    current_commit="$(git -C "$managed_home" rev-parse HEAD)"
    note "updated to $current_commit"
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
# the clone so recording it never makes the tree dirty. Encode JSON here rather than
# interpolating input into JSON syntax; mise and Git remain the only prerequisites.
json_string() {
  local value=$1 character index
  printf '"'
  for ((index = 0; index < ${#value}; index += 1)); do
    character=${value:index:1}
    case "$character" in
      '"') printf '\\"' ;;
      '\') printf '\\\\' ;;
      $'\b') printf '\\b' ;;
      $'\f') printf '\\f' ;;
      $'\n') printf '\\n' ;;
      $'\r') printf '\\r' ;;
      $'\t') printf '\\t' ;;
      [[:cntrl:]]) die 'remote, ref, and managed path may not contain other control characters' ;;
      *) printf '%s' "$character" ;;
    esac
  done
  printf '"'
}

mkdir -p -- "$state_home"
{
  printf '{\n  "remote": '
  json_string "$remote"
  printf ',\n  "ref": '
  json_string "$ref"
  printf ',\n  "commit": '
  json_string "$current_commit"
  printf ',\n  "path": '
  json_string "$managed_home"
  printf ',\n  "recorded_by": "bootstrap-agentic-sdlc.sh"\n}\n'
} >"$receipt.tmp"
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
case "$remote" in
  https://*)
    note 'Transport was authenticated by HTTPS. That authenticates the connection, not the'
    note 'contents: nothing here verifies a signature over the commit above. Read the tree'
    note 'before you trust it.'
    ;;
  ssh://*|git@*:*)
    note 'Transport used SSH. Its host/key authentication does not verify a signature over'
    note 'the fetched commit. Read the tree before you trust it.'
    ;;
  *)
    note 'The selected transport does not establish HTTPS authentication. Nothing here verifies'
    note 'a signature over the fetched commit. Read the tree before you trust it.'
    ;;
esac
note ''
note "Verify this managed fetch before first use:"
note "  remote/commit receipt: $receipt"
note "  current checkout:      $(git -C "$managed_home" rev-parse HEAD)"
note "  review source + lock:  $managed_home/mise.toml and $managed_home/mise.lock"
note ''
note "First-use handoff, each command needs its own approval (trust is persistent):"
note ''
note "  1. Review the two files that trust authorizes:"
note "       \$EDITOR $managed_home/mise.toml"
note "       \$EDITOR $managed_home/mise.lock"
note "  2. Trust that exact reviewed config path (currently: $trust_state):"
note "       mise trust $managed_home/mise.toml"
note "  3. Resolve the locked toolchain:"
note "       mise -C $managed_home --locked install"
note "  4. Inspect the install surface and choose a plane:"
note "       mise -C $managed_home tasks"
note "       mise -C $managed_home run bundle:install -- --agent claude"
note "       mise -C $managed_home run bundle:install -- --agent codex"
note "  5. Verify the selected plane after installation:"
note "       mise -C $managed_home run bundle:status"
note ''
note 'To remove everything this script created:'
note "  rm -rf $managed_home $state_home"
note ''
note 'This bootstrap reports evidence about this run only. It authorizes nothing.'
