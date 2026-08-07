#!/bin/bash
# opencodex-claude.sh — split-plane launcher and supervisor for the pinned opencodex
# gateway (`ocx`).
#
# Purpose: run a SECOND Claude Code process pointed at the local opencodex proxy, for
# non-Anthropic-model work, while the operator's native Claude Code session and config are
# left untouched. Subcommands: launch | status | restart | configure.
#
# ENSURE-UP: `launch` and `restart` own the gateway lifecycle rather than merely attaching.
# Supervision is DELEGATED to opencodex's own verbs (`ocx ensure` starts-if-down, waits, and
# is idempotent under its pidfile + identity-checked liveness; `ocx restart` = stop + ensure;
# `ocx stop` stops cleanly), because reimplementing spawn/pidfile/port discovery next to a
# tool that already does it with an identity-checked /healthz probe would be a second,
# weaker supervisor.
#
# FAIL-CLOSED: no ocx verb's exit code is ever accepted as the health verdict. `ocx health`
# is re-probed after every supervision step and is the only verdict, so Claude Code is never
# launched against a dead or half-up gateway; a gateway that will not come healthy within the
# bounded wait aborts the launch with a named reason and a nonzero exit.
#
# WHAT THIS DELIBERATELY DOES NOT DO
#   * No Anthropic-subscription passthrough. docs/adr/0003 rejects routing Claude
#     subscription OAuth through any third-party process: the mechanism works, the
#     authorization does not. `ocx claude` on its own does NOT enforce that — read
#     src/cli/claude.ts and src/claude/auth-mode.ts in the installed package: its auth
#     resolver treats a readable subscription credential, AND an unreadable one, as
#     `subscription` markerMode and forwards the operator's own OAuth to the proxy. This
#     wrapper therefore forces the supported shape structurally rather than trusting that
#     default: it isolates CLAUDE_CONFIG_DIR, scrubs every ANTHROPIC*/CLAUDE* variable out
#     of the child environment, and REFUSES (exit 3) when a subscription credential would
#     still be reachable. Non-Anthropic providers authenticating with their own credentials
#     (Codex OAuth, provider API keys, via `configure`) are the supported path.
#   * Launching is not route qualification. The canary in
#     docs/research/2026-08-05-gateway-selection-memo.md §4 (probes A, C, D, E, F) is the
#     qualification gate for trusting which model actually served a request; it is still
#     unrun. A healthy gateway proves reachability, never model identity.
#   * A healthy `status` is evidence, not authorization. Exit 0 means the proxy answered an
#     identity-checked health probe at that moment. It grants no authority for any outward
#     effect.
#   * This does NOT isolate the operator's Codex state. Isolation here covers CLAUDE_CONFIG_DIR
#     only. `ocx ensure`/`start` also rewrite ~/.codex (pointing Codex's openai provider at the
#     proxy) and `ocx stop` restores it — an upstream side effect this wrapper surfaces rather
#     than hides, because a supervision call therefore mutates shared Codex config.
#   * No credential is read, written, printed, or forwarded by this script. `configure` hands
#     off to ocx's own interactive login flows; this script never handles the secret.
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Isolated Claude Code config root for the gateway-routed process. Keeping it out of
# ~/.claude is what makes this a SECOND plane: ocx syncs its own `ocx-*.md` roster agents
# and gateway model cache into the effective config dir, so sharing the native one would
# mutate the operator's live session state.
state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
isolated_config_dir="$state_home/agentic-sdlc/ocx-claude"
log_dir="$state_home/agentic-sdlc/ocx-logs"
# Bound on how long a just-started gateway may take to answer an identity-checked probe.
# `ocx ensure` already waits internally (8s); this is the wrapper's own outer bound, so a
# hung or half-up start is capped rather than inherited.
readiness_timeout_seconds=15
readiness_poll_seconds=1

usage() {
  cat <<'EOF'
usage: opencodex-claude.sh <launch|status|restart|configure> [args...]

  launch [claude args...]   Ensure the gateway is healthy (start it if down, restart once if
                            half-up), then launch a second Claude Code process through it
                            with an isolated CLAUDE_CONFIG_DIR and no Anthropic subscription
                            credential in scope. Fails closed if the gateway never becomes
                            healthy.
  status                    Supervision view: pid, port, uptime, healthy/down, log location,
                            configured providers, attribution stream. Exit 0 healthy.
  restart                   Stop the gateway cleanly if running, then ensure it is back up
                            and healthy. Fails closed on an unclean stop.
  configure [ocx args...]   Interactive passthrough to opencodex's own provider
                            login/config commands. Prints the command before running it.

exit codes: 0 ok · 1 failure/unhealthy · 2 usage · 3 refused (subscription-OAuth boundary)
EOF
}

ocx() {
  mise -C "$root" exec -- ocx "$@"
}

require_ocx() {
  if ! command -v mise >/dev/null 2>&1; then
    printf 'error: mise is required to resolve the pinned opencodex build\n' >&2
    exit 1
  fi
  if ! ocx --version >/dev/null 2>&1; then
    printf 'error: pinned opencodex is not installed; run `mise install` in %s\n' "$root" >&2
    exit 1
  fi
}

refuse() {
  printf '\nREFUSED: %s\n' "$1" >&2
  cat >&2 <<'EOF'
docs/adr/0003 rejects routing Claude subscription OAuth through a third-party gateway.
Anthropic's own legal-and-compliance documentation scopes subscription OAuth to ordinary
use of native Anthropic applications and does not permit third parties to route requests
through Free/Pro/Max plan credentials. The mechanism works; the authorization does not.

The supported path is a non-Anthropic provider authenticating with its own credential:
  scripts/opencodex-claude.sh configure
EOF
  exit 3
}

# --- gateway supervision -----------------------------------------------------------------
#
# `ocx health` is the ONLY health verdict: it is the single verb whose exit code reflects an
# identity-checked /healthz probe (`ocx status` and `ocx observe logs` both exit 0 with the
# proxy down, and `ocx ensure` exits 0 WITHOUT starting anything when codexAutoStart is
# disabled -- a fail-open path this wrapper closes by never trusting an ensure exit code).
gateway_healthy() {
  ocx health >/dev/null 2>&1
}

gateway_health_json() {
  ocx health --json 2>/dev/null || true
}

# Best-effort scalar out of ocx's own {"ok":…,"pid":…,"port":…} health payload. Parsing is
# deliberately tolerant: a missing value degrades the status display, never the verdict.
health_field() {
  local field="$1" json="$2"
  printf '%s' "$json" | sed -n "s/.*\"$field\":\([0-9]*\).*/\1/p" | head -1
}

configured_port() {
  ocx config get port 2>/dev/null | tr -d '[:space:]' | grep -E '^[0-9]+$' || true
}

# Uptime is a nicety, so it is read straight from /healthz and only when a fetcher exists.
gateway_uptime_seconds() {
  local port="$1"
  command -v curl >/dev/null 2>&1 || return 0
  curl -fsS --max-time 3 "http://127.0.0.1:${port}/healthz" 2>/dev/null \
    | sed -n 's/.*"uptime":\([0-9]*\).*/\1/p' | head -1
}

# True when something gateway-shaped exists but is not answering a healthy identity probe:
# a live pidfile process or a bound port. That is the "half-up" case (stale pidfile, wedged
# or foreign listener) which a single restart is allowed to resolve.
gateway_half_up() {
  local pid_file="$HOME/.opencodex/ocx.pid" pid port
  if [ -f "$pid_file" ]; then
    pid="$(tr -d '[:space:]' < "$pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  port="$(configured_port)"
  if [ -n "$port" ] && command -v curl >/dev/null 2>&1; then
    # Any answer at all on the port, healthy or not, counts as half-up.
    curl -fsS --max-time 2 "http://127.0.0.1:${port}/healthz" >/dev/null 2>&1 && return 0
  fi
  return 1
}

wait_for_health() {
  local waited=0
  while [ "$waited" -lt "$readiness_timeout_seconds" ]; do
    if gateway_healthy; then
      return 0
    fi
    sleep "$readiness_poll_seconds"
    waited=$((waited + readiness_poll_seconds))
  done
  gateway_healthy
}

fail_closed() {
  printf '\nFAIL-CLOSED: %s\n' "$1" >&2
  printf 'Claude Code was NOT launched: routing it at a dead or half-up gateway would\n' >&2
  printf 'silently produce connection errors or unattributable responses.\n\n' >&2
  printf 'Diagnose with:\n' >&2
  printf '  scripts/opencodex-claude.sh status\n' >&2
  printf '  mise -C %s exec -- ocx doctor\n' "$root" >&2
  printf '  gateway start log: %s/gateway.log\n' "$log_dir" >&2
  exit 1
}

# Idempotent by delegation: `ocx ensure` is a no-op against an already-live proxy (verified:
# concurrent ensures leave the pid unchanged and a single listener bound), and `ocx start`
# refuses outright with "Proxy already running". This wrapper adds no competing pidfile.
ensure_gateway_up() {
  if gateway_healthy; then
    printf '  gateway   : already healthy\n'
    return 0
  fi

  mkdir -p "$log_dir"
  if gateway_half_up; then
    printf '  gateway   : present but not answering a healthy probe; restarting once\n'
    # `ocx restart` refuses to re-ensure after an unclean stop, so its own guard is kept.
    if ! ocx restart >>"$log_dir/gateway.log" 2>&1; then
      fail_closed "the gateway was half-up and \`ocx restart\` did not complete cleanly"
    fi
    if ! wait_for_health; then
      fail_closed "the gateway was restarted but did not become healthy within ${readiness_timeout_seconds}s"
    fi
    printf '  gateway   : healthy after restart\n'
    return 0
  fi

  printf '  gateway   : down; starting (log: %s/gateway.log)\n' "$log_dir"
  # The ensure exit code is recorded but never trusted as health -- see gateway_healthy.
  ocx ensure >>"$log_dir/gateway.log" 2>&1 || true
  if ! wait_for_health; then
    fail_closed "the gateway did not become healthy within ${readiness_timeout_seconds}s of starting"
  fi
  printf '  gateway   : healthy\n'
  return 0
}

# --- subscription-OAuth boundary ---------------------------------------------------------

# The two slots opencodex itself treats as parent-exported Anthropic credentials
# (ANTHROPIC_PARENT_ENV_SLOTS in its launcher-context module). Checked BEFORE the scrub,
# because after the scrub there is nothing left to inspect.
subscription_shaped_env() {
  local name value
  for name in ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY; do
    value="${!name:-}"
    # sk-ant-oat* is a subscription OAuth access token. An sk-ant-api* developer API key is
    # a different credential class and is not what ADR-0003 forbids; it is scrubbed rather
    # than refused, so it never reaches the gateway by accident either.
    case "$value" in
      sk-ant-oat*) printf '%s' "$name"; return 0 ;;
    esac
  done
  return 1
}

scrub_anthropic_env() {
  local name
  # Prefix scrub, not an enumerated list: the parent session exports credential slots,
  # per-tier model slots, capability strings, and routing flags (CLAUDE_CODE_USE_BEDROCK
  # among them). Any one of them leaking into the child either re-routes it away from the
  # gateway or carries parent-session identity into it. opencodex re-injects exactly the
  # slots it needs via its own defaults.
  for name in $(compgen -v | grep -E '^(ANTHROPIC|CLAUDE)' || true); do
    unset "$name" || true
  done
}

# Fail closed against the same sources opencodex's auth detector reads, in the isolated
# dir we control: <config-dir>/.credentials.json (claudeAiOauth) and the sibling
# <config-dir>/../.claude.json (oauthAccount). Key names only -- no value is read.
assert_isolated_dir_has_no_subscription() {
  local credentials="$isolated_config_dir/.credentials.json"
  local claude_json="$isolated_config_dir/../.claude.json"
  if [ -f "$credentials" ] && grep -q 'claudeAiOauth' "$credentials" 2>/dev/null; then
    refuse "the isolated config dir carries a Claude subscription OAuth credential ($credentials)"
  fi
  if [ -f "$claude_json" ] && grep -q 'oauthAccount' "$claude_json" 2>/dev/null; then
    refuse "a subscription OAuth account is reachable next to the isolated config dir ($claude_json)"
  fi
}

# macOS keychain is the one detector source an isolated config dir cannot mask, so it is
# probed rather than assumed. Exit 44 is the documented "item does not exist" status.
assert_no_keychain_subscription() {
  [ "$(uname -s 2>/dev/null || true)" = "Darwin" ] || return 0
  command -v security >/dev/null 2>&1 || return 0
  local status=0
  security find-generic-password -s 'Claude Code-credentials' >/dev/null 2>&1 || status=$?
  if [ "$status" -eq 0 ]; then
    refuse "a Claude Code subscription credential is present in the macOS keychain, which an isolated config dir cannot mask"
  fi
}

# --- subcommands -------------------------------------------------------------------------

cmd_launch() {
  require_ocx
  local offending
  # The credential boundary is checked BEFORE any gateway is started: a refused launch must
  # not leave a proxy running that the operator did not ask for.
  if offending="$(subscription_shaped_env)"; then
    refuse "$offending in this environment holds a subscription OAuth access token (sk-ant-oat*)"
  fi
  scrub_anthropic_env
  mkdir -p "$isolated_config_dir"
  assert_isolated_dir_has_no_subscription
  assert_no_keychain_subscription
  export CLAUDE_CONFIG_DIR="$isolated_config_dir"

  if ! command -v claude >/dev/null 2>&1; then
    printf 'error: the `claude` CLI is not on PATH; opencodex cannot launch it\n' >&2
    exit 1
  fi

  printf 'preparing gateway-routed Claude Code\n'
  ensure_gateway_up
  local json port
  json="$(gateway_health_json)"
  port="$(health_field port "$json")"
  printf '  config dir: %s (isolated; your native ~/.claude is untouched)\n' "$isolated_config_dir"
  printf '  auth      : opencodex proxy owns authentication; no Anthropic subscription credential in scope\n'
  printf '  routed at : http://127.0.0.1:%s\n' "${port:-unknown}"
  printf '  command   : mise -C %s exec -- ocx claude %s\n\n' "$root" "$*"
  # ocx claude re-checks liveness itself and then execs `claude` with stdio inherited. With
  # every ANTHROPIC*/CLAUDE* slot scrubbed and no reachable subscription credential, its auth
  # resolver lands on proxy markerMode -- the supported shape.
  ocx claude "$@"
}

cmd_status() {
  require_ocx
  local json ok pid port uptime
  json="$(gateway_health_json)"
  pid="$(health_field pid "$json")"
  port="$(health_field port "$json")"
  [ -n "$port" ] || port="$(configured_port)"
  ok=0
  gateway_healthy || ok=$?

  printf '== gateway supervision ==\n'
  if [ "$ok" -eq 0 ]; then
    printf '  state   : healthy\n'
    printf '  pid     : %s\n' "${pid:-unknown}"
    printf '  port    : %s\n' "${port:-unknown}"
    uptime="$(gateway_uptime_seconds "${port:-0}")"
    [ -n "$uptime" ] && printf '  uptime  : %ss\n' "$uptime"
  elif gateway_half_up; then
    printf '  state   : HALF-UP (something is bound or a pid is alive, but no healthy identity probe)\n'
    printf '  port    : %s\n' "${port:-unknown}"
    printf '  hint    : scripts/opencodex-claude.sh restart\n'
  else
    printf '  state   : DOWN\n'
    printf '  port    : %s (configured)\n' "${port:-unknown}"
    printf '  hint    : scripts/opencodex-claude.sh restart   (or `launch`, which ensures it is up)\n'
  fi
  printf '  logs    : %s/gateway.log\n' "$log_dir"

  printf '\n== upstream detail ==\n'
  ocx status 2>&1 | head -12 || true

  printf '\n== configured providers ==\n'
  ocx provider list 2>/dev/null | sed -n '1,/^Available from registry/p' | sed '$d' || printf 'provider list unavailable\n'

  printf '\n== attribution log stream ==\n'
  printf '  mise -C %s exec -- ocx observe logs --follow --jsonl\n' "$root"
  printf '  (requires a running gateway; it prints "Proxy is not running" and exits 0 otherwise)\n'

  if [ "$ok" -ne 0 ]; then
    printf '\nunhealthy: the gateway did not answer an identity-checked health probe.\n' >&2
    return 1
  fi
  printf '\nhealthy: the gateway answered an identity-checked health probe. That is evidence,\n'
  printf 'not authorization, and it says nothing about which model serves a request.\n'
}

cmd_restart() {
  require_ocx
  mkdir -p "$log_dir"
  if gateway_healthy || gateway_half_up; then
    printf 'stopping the gateway\n'
    # A failed stop must not be followed by a start: ocx declines to re-inject shared Codex
    # config it did not cleanly release, and racing it here would defeat that guard.
    if ! ocx stop >>"$log_dir/gateway.log" 2>&1; then
      fail_closed "\`ocx stop\` did not complete cleanly; the gateway was left as-is"
    fi
  else
    printf 'gateway is down; nothing to stop\n'
  fi
  printf 'ensuring the gateway is up\n'
  ensure_gateway_up
  printf '\nrestarted. A healthy gateway is evidence, not authorization.\n'
}

cmd_configure() {
  require_ocx
  if [ "$#" -eq 0 ]; then
    printf 'Interactive opencodex provider configuration. This script runs ocx verbs; it\n'
    printf 'never reads, stores, or forwards a credential itself.\n\n'
    printf 'Supported (non-Anthropic providers only -- see docs/adr/0003):\n'
    printf '  opencodex-claude.sh configure login <provider>    OAuth or API-key login\n'
    printf '  opencodex-claude.sh configure provider list       Providers and registry\n'
    printf '  opencodex-claude.sh configure account list        Accounts and key pools\n'
    printf '  opencodex-claude.sh configure setup               Full interactive setup\n\n'
    printf 'Run `mise -C %s exec -- ocx help <verb>` for the upstream surface.\n' "$root"
    return 0
  fi
  # `ocx login anthropic` / `anthropic-apikey` would attach an Anthropic credential to the
  # gateway. The API-key form is a different credential class than subscription OAuth, but
  # neither is this bundle's use for the gateway, and the OAuth form is the prohibited one.
  case "${1:-} ${2:-}" in
    "login anthropic"|"login anthropic-apikey")
      refuse "\`ocx $1 $2\` would attach an Anthropic credential to the gateway; this split plane routes non-Anthropic models only"
      ;;
  esac
  printf 'about to run: mise -C %s exec -- ocx %s\n\n' "$root" "$*"
  ocx "$@"
}

case "${1:-}" in
  launch) shift; cmd_launch "$@" ;;
  status) shift; cmd_status "$@" ;;
  restart) shift; cmd_restart "$@" ;;
  configure) shift; cmd_configure "$@" ;;
  -h|--help|help) usage ;;
  "") usage >&2; exit 2 ;;
  *) printf 'error: unknown subcommand %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac
