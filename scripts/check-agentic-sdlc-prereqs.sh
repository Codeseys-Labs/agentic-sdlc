#!/bin/bash
# Preflight and reusable Seeds launcher for the agentic-sdlc-orchestrator kit.
# Required bootstrap: mise. Required runtime capabilities: git and exact Seeds via mise.
# Set AGENTIC_SDLC_GITHUB_REQUIRED=1 only for an authorized GitHub operation; then gh is required.
# Optional enhancements: tmux (adapter backend) and cmux (active view/event layer).
set -euo pipefail

AGENTIC_SDLC_SEEDS_VERSION=0.5.14
AGENTIC_SDLC_SEEDS_TOOL="npm:@os-eco/seeds-cli@${AGENTIC_SDLC_SEEDS_VERSION}"
AGENTIC_SDLC_NODE_TOOL=node@22.22.3
AGENTIC_SDLC_BUN_TOOL=bun@1.3.10

# The exact Node 22.22.3 runtime executes this literal program after mise has acquired
# the pinned package. It accepts the target and original Seeds argv as distinct values; it
# never invokes a shell to parse any of them. Native Windows cannot directly spawn a .cmd file
# without a shell, so the program starts the exact sd.cmd through ComSpec's argv interface while
# Node itself retains shell:false. Mise prepends only the selected exact tuple to PATH, so the
# first matching executable is the exact Seeds executable provided to this invocation.
AGENTIC_SDLC_SEEDS_TRAMPOLINE=$(cat <<'EOF'
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const [target, ...args] = process.argv.slice(1);
const isWindows = process.platform === 'win32';
const executableName = isWindows ? 'sd.cmd' : 'sd';
const executable = process.env.PATH.split(path.delimiter)
  .map((entry) => path.join(entry, executableName))
  .find(fs.existsSync);
if (!target || !fs.existsSync(target) || !fs.statSync(target).isDirectory() || !executable) {
  process.stderr.write('MISSING: exact Seeds trampoline inputs\n');
  process.exitCode = 2;
} else {
  const command = isWindows ? process.env.ComSpec : executable;
  const commandArgs = isWindows ? ['/d', '/s', '/c', executable, ...args] : args;
  const child = spawn(command, commandArgs, {
    cwd: target,
    shell: false,
    stdio: 'inherit',
    windowsHide: true,
  });
  let spawnError = false;
  child.once('error', (error) => {
    spawnError = true;
    process.stderr.write(`MISSING: exact Seeds executable: ${error.message}\n`);
    process.exitCode = 2;
  });
  child.once('close', (code, signal) => {
    if (spawnError) return;
    if (signal) {
      process.kill(process.pid, signal);
    } else {
      process.exitCode = code === null ? 1 : code;
    }
  });
}
EOF
)

# POSIX acquisition state is created only directly under fixed /var/tmp. It never follows
# TMPDIR, TEMP, TMP, the requested target, or ancestry controlled by that target.
agentic_sdlc_seeds_exec() (
  if [ "$#" -lt 2 ]; then
    printf 'usage: agentic_sdlc_seeds_exec <target> <command> [args...]\n' >&2
    return 2
  fi
  seeds_target=$1
  shift
  if ! seeds_target=$(cd -- "$seeds_target" && pwd -P); then
    printf 'MISSING:  Seeds target %s is not a directory\n' "$1" >&2
    return 2
  fi
  old_umask=$(umask)
  umask 077
  if ! seeds_neutral_dir=$(mktemp -d /var/tmp/agentic-sdlc-seeds.XXXXXX); then
    umask "$old_umask"
    printf 'MISSING:  neutral temporary directory for Seeds acquisition\n' >&2
    return 2
  fi
  umask "$old_umask"
  seeds_user_config=$seeds_neutral_dir/npm-user.config
  seeds_global_config=$seeds_neutral_dir/npm-global.config
  if ! : >"$seeds_user_config" || ! : >"$seeds_global_config"; then
    rm -rf -- "$seeds_neutral_dir"
    printf 'MISSING:  neutral npm config files for Seeds acquisition\n' >&2
    return 2
  fi
  cleanup_seeds_neutral() {
    rm -rf -- "$seeds_neutral_dir"
  }
  trap 'cleanup_seeds_neutral' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM

  # env -i removes every inherited NPM_CONFIG_* spelling, including scoped registry variables
  # that cannot be represented as shell identifiers. The reviewed values and distinct empty
  # config files are the only npm configuration exposed to mise/npm acquisition.
  if [ -z "${MISE_DATA_DIR:-}" ] || [ -z "${MISE_CACHE_DIR:-}" ]; then
    printf 'MISSING:  isolate MISE_DATA_DIR and MISE_CACHE_DIR before exact Seeds acquisition\n' >&2
    return 2
  fi
  seeds_env=(
    env -i
    "PATH=$PATH"
    "HOME=${HOME:-}"
    "MISE_DATA_DIR=$MISE_DATA_DIR"
    "MISE_CACHE_DIR=$MISE_CACHE_DIR"
    'NPM_CONFIG_REGISTRY=https://registry.npmjs.org/'
    "NPM_CONFIG_USERCONFIG=$seeds_user_config"
    "NPM_CONFIG_GLOBALCONFIG=$seeds_global_config"
    'NPM_CONFIG_STRICT_SSL=true'
    'MISE_NPM_PACKAGE_MANAGER=npm'
  )
  "${seeds_env[@]}" mise --no-config --cd "$seeds_neutral_dir" exec \
    "$AGENTIC_SDLC_NODE_TOOL" "$AGENTIC_SDLC_BUN_TOOL" "$AGENTIC_SDLC_SEEDS_TOOL" \
    -- node -e "$AGENTIC_SDLC_SEEDS_TRAMPOLINE" "$seeds_target" "$@"
)

# Run exact Seeds from the target repository without loading that repository's or ambient
# mise/npm configuration. npm's registry integrity metadata and strict TLS apply to acquisition;
# pinning alone does not authenticate the tarball or its transitives.
agentic_sdlc_seeds() {
  if [ "$#" -lt 1 ]; then
    printf 'usage: agentic_sdlc_seeds <target> [sd args...]\n' >&2
    return 2
  fi
  seeds_target=$1
  shift
  agentic_sdlc_seeds_exec "$seeds_target" "$@"
}

# Sourcing this script exposes only the launcher; executing it runs preflight.
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
if [ "${AGENTIC_SDLC_GITHUB_REQUIRED:-0}" = "1" ]; then
  req gh
else
  rec gh "GitHub publication adapter skipped; local Git orchestration is unaffected"
fi

# Verify version and separator-bounded provenance inside the exact mise execution environment.
# command -v on the ambient shell is intentionally not accepted as Seeds evidence.
if command -v mise >/dev/null 2>&1; then
  seeds_target=$(pwd)
  if ! seeds_version=$(agentic_sdlc_seeds "$seeds_target" --version 2>/dev/null); then
    printf 'MISSING:  exact Seeds %s through mise (required)\n' "$AGENTIC_SDLC_SEEDS_VERSION" >&2
    missing=1
  elif [ "$seeds_version" != "$AGENTIC_SDLC_SEEDS_VERSION" ]; then
    printf 'MISMATCH: Seeds version %s; required %s\n' "$seeds_version" "$AGENTIC_SDLC_SEEDS_VERSION" >&2
    missing=1
  elif ! seeds_root=$(mise --no-config where "$AGENTIC_SDLC_SEEDS_TOOL" 2>/dev/null); then
    printf 'MISSING:  Seeds provenance root from mise (required)\n' >&2
    missing=1
  elif ! seeds_executable=$(if [ "${OS:-}" = "Windows_NT" ]; then printf '%s/sd.cmd\n' "$seeds_root"; else printf '%s/bin/sd\n' "$seeds_root"; fi); then
    printf 'MISSING:  Seeds executable from exact mise environment (required)\n' >&2
    missing=1
  else
    # Normalize Windows separators and case. The trailing slash makes containment separator-bounded.
    normalized_root=$(printf '%s' "$seeds_root" | tr '\\' '/' | tr '[:upper:]' '[:lower:]')
    normalized_executable=$(printf '%s' "$seeds_executable" | tr '\\' '/' | tr '[:upper:]' '[:lower:]')
    case "$normalized_executable" in
      "$normalized_root"/*) printf 'ok:       Seeds %s (%s)\n' "$seeds_version" "$seeds_executable" ;;
      *)
        printf 'MISMATCH: Seeds provenance %s is outside %s\n' "$seeds_executable" "$seeds_root" >&2
        missing=1
        ;;
    esac
  fi
fi

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
  cwd_target=$(pwd)
  if grep -qF "$cwd_target" "${CODEX_HOME:-$HOME/.codex}/config.toml" 2>/dev/null; then
    printf 'ok:       codex trusts %s\n' "$cwd_target"
  else
    printf 'warn:     codex does NOT trust %s — codex workers here hang on the trust prompt. Add projects trust_level=trusted in ~/.codex/config.toml\n' "$cwd_target"
  fi
fi

exit "$missing"
