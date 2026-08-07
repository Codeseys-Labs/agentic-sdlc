#!/bin/bash
# opencodex-claude.sh — split-plane launcher and supervisor for the pinned opencodex
# gateway (`ocx`).
#
# Purpose: run a SECOND Claude Code process pointed at the local opencodex proxy, for
# non-Anthropic-model work, while the operator's native Claude Code session and config are
# left untouched. Subcommands: launch | launch-ultracode | status | restart | configure.
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
#     off to ocx's own interactive login flows; this script never handles the secret. It does
#     WARN when a key is passed as `--api-key` on the command line, because argv is
#     world-readable via `ps` for the life of the call -- see cmd_configure's help text for the
#     stdin-only alternative.
#   * `configure` does NOT make a provider mutation take effect. Writing a provider into the
#     config file does not put it in the running gateway's catalog: `ocx sync` plus a gateway
#     restart is required, and in the window between, a request naming the new provider's model
#     falls through to the DEFAULT provider (see print_sync_required_notice). This wrapper
#     reports that gap mechanically and refuses to close it silently, because `ocx sync`
#     rewrites shared ~/.codex config and is its own authorized operation.
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
usage: opencodex-claude.sh <launch|launch-ultracode|status|restart|configure> [args...]

  launch [claude args...]   Ensure the gateway is healthy (start it if down, restart once if
                            half-up), then launch a second Claude Code process through it
                            with an isolated CLAUDE_CONFIG_DIR and no Anthropic subscription
                            credential in scope. Fails closed if the gateway never becomes
                            healthy.
  launch-ultracode [args...]  Apply the session-only {"ultracode":true} setting, then use the
                            same fail-closed launch path. This convenience route refuses a
                            competing --settings argument and permission-bypass flags.
  status                    Supervision view: pid, port, uptime, healthy/down, log location,
                            configured providers, attribution stream. Also compares each
                            CONFIGURED provider against the running gateway's LIVE catalog and
                            warns NOT-LIVE for any that is configured but not served. Exit 0
                            healthy.
  restart                   Stop the gateway cleanly if running, then ensure it is back up
                            and healthy. Fails closed on an unclean stop.
  configure [ocx args...]   Interactive passthrough to opencodex's own provider
                            login/config commands. Prints the command before running it. After
                            an admitted provider add/edit/remove it prints the required
                            `ocx sync` + restart sequence, because a configured provider is NOT
                            live until then and requests fall through to the default provider
                            in the meantime.

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
# The trailing `|| true` is load-bearing: under `set -o pipefail` a refused /healthz makes the
# pipeline exit nonzero, which -- inside the `uptime="$(...)"` assignment in cmd_status and
# under `set -e` -- would abort the whole status report over a missing cosmetic field.
gateway_uptime_seconds() {
  local port="$1"
  command -v curl >/dev/null 2>&1 || return 0
  { curl -fsS --max-time 3 "http://127.0.0.1:${port}/healthz" 2>/dev/null \
    | sed -n 's/.*"uptime":\([0-9]*\).*/\1/p' | head -1; } || true
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

# --- configured-vs-live provider reconciliation -------------------------------------------
#
# A provider written into ~/.opencodex/config.json is NOT thereby in the running gateway's
# routing table. The two facts have separate sources and this is the only honest way to tell
# them apart:
#   * CONFIGURED: `ocx provider list --json` .configured[].name -- reads the config file.
#   * LIVE:       the running gateway's own `GET /v1/models` -- reads the process's catalog.
# A provider present in the first and absent from the second is NOT-LIVE. That state is not
# cosmetic: a request naming its model does not error, it is classified
# `routeKind: "default-provider"` and forwarded to whichever provider is default, which bills
# and attempts against the wrong upstream. That is the canary's C1/C5 fail-open condition
# reached through configuration drift rather than through a typo.
#
# Both readers degrade to silence rather than to a false verdict: no jq, no curl, or an
# unparseable payload yields "unknown", never "live" and never "NOT-LIVE".

configured_provider_names() {
  command -v jq >/dev/null 2>&1 || return 1
  ocx provider list --json 2>/dev/null \
    | jq -r '(.configured // []) | .[] | select(.name != null) | .name' 2>/dev/null
}

# Model IDs the RUNNING gateway serves. Namespaced as `<provider>/<model>` for a custom
# provider, bare for the default one, so the provider segment is what identifies liveness.
live_catalog_model_ids() {
  local port="$1"
  [ -n "$port" ] || return 1
  command -v curl >/dev/null 2>&1 || return 1
  command -v jq >/dev/null 2>&1 || return 1
  curl -fsS --max-time 5 "http://127.0.0.1:${port}/v1/models" 2>/dev/null \
    | jq -r '(.data // []) | .[] | select(.id != null) | .id' 2>/dev/null
}

# Names with at least one model served under `<name>/`. The default provider serves bare IDs,
# so it is reported live whenever the catalog answers at all -- its own liveness is already the
# health probe's subject and misreporting it as NOT-LIVE would be the false alarm this check
# exists to avoid.
live_provider_names() {
  local port="$1" catalog
  catalog="$(live_catalog_model_ids "$port")" || return 1
  [ -n "$catalog" ] || return 1
  printf '%s\n' "$catalog" | sed -n 's|^\([^/][^/]*\)/.*|\1|p' | sort -u
}

# Prints one `<name>` per configured-but-not-served provider. Exit 1 means the comparison could
# not be made (missing tool, gateway down, unparseable payload) -- deliberately distinct from
# exit 0 with no output, which means every configured provider is live.
not_live_providers() {
  local port="$1" configured live default_name name
  configured="$(configured_provider_names)" || return 1
  [ -n "$configured" ] || return 1
  live="$(live_provider_names "$port")" || return 1
  default_name="$(command -v jq >/dev/null 2>&1 \
    && ocx provider list --json 2>/dev/null \
      | jq -r '(.configured // []) | map(select(.isDefault == true)) | (first | .name) // ""' 2>/dev/null || true)"
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    [ "$name" = "$default_name" ] && continue
    printf '%s\n' "$live" | grep -qxF "$name" || printf '%s\n' "$name"
  done <<<"$configured"
}

# Printed after every admitted provider mutation. The sequence is NOT run for the operator:
# `ocx sync` rewrites shared ~/.codex state and a restart interrupts in-flight turns, so each
# is its own authorized operation rather than a side effect of a configuration edit.
print_sync_required_notice() {
  local route="$1"
  cat <<EOF

NOT LIVE YET: \`ocx $route\` wrote the provider to the config file. It is NOT in the running
gateway's routing table until BOTH of these run:

  mise -C $root exec -- ocx sync
  scripts/opencodex-claude.sh restart

Until then a request naming this provider's model does NOT fail closed. It is classified
\`routeKind: "default-provider"\` and forwarded to the DEFAULT provider, so it is attempted and
billed against the wrong upstream while the attribution log records the wrong provider.

Neither step is run for you: \`ocx sync\` rewrites shared ~/.codex config and a restart
interrupts in-flight turns, so both are separately authorized operations.

Confirm the provider went live before dispatching anything to it:
  scripts/opencodex-claude.sh status
EOF
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
  local path key
  for path in "$credentials" "$claude_json"; do
    [ -e "$path" ] || [ -L "$path" ] || continue
    [ -f "$path" ] && [ ! -L "$path" ] && [ -r "$path" ] \
      || refuse "a Claude credential source is linked, unreadable, or not a regular file ($path)"
  done
  for path in "$credentials" "$claude_json"; do
    [ -f "$path" ] || continue
    key=claudeAiOauth
    [ "$path" = "$claude_json" ] && key=oauthAccount
    grep -q "$key" "$path" 2>/dev/null \
      && refuse "the isolated Claude state carries a subscription OAuth marker ($path)"
  done
}

assert_proxy_marker_mode() {
  local mode
  mode="$(ocx config get claudeCode.authMode 2>/dev/null | tr -d '[:space:]' || true)"
  case "$mode" in
    ""|auto|proxy) return 0 ;;
    subscription) refuse "opencodex claudeCode.authMode is explicitly subscription; set it to proxy before using this split plane" ;;
    *) refuse "opencodex claudeCode.authMode is unreadable or unrecognized ($mode)" ;;
  esac
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
  assert_proxy_marker_mode
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
  # Forwarded Claude arguments can contain inline settings and secrets. Never echo raw argv.
  printf '  command   : mise -C %s exec -- ocx claude [forwarded arguments withheld]\n\n' "$root"
  # ocx claude re-checks liveness itself and then execs `claude` with stdio inherited. With
  # every ANTHROPIC*/CLAUDE* slot scrubbed and no reachable subscription credential, its auth
  # resolver lands on proxy markerMode -- the supported shape.
  ocx claude "$@"
}

cmd_launch_ultracode() {
  local argument previous=""
  for argument in "$@"; do
    case "$argument" in
      --settings|--settings=*)
        printf 'REFUSED: launch-ultracode owns the session --settings value; use ordinary launch for a custom settings document\n' >&2
        return 3
        ;;
      --dangerously-skip-permissions|--permission-mode=bypassPermissions)
        printf 'REFUSED: launch-ultracode never bypasses permissions; use ordinary launch for an explicitly chosen risk profile\n' >&2
        return 3
        ;;
      bypassPermissions)
        if [ "$previous" = "--permission-mode" ]; then
          printf 'REFUSED: launch-ultracode never bypasses permissions; use ordinary launch for an explicitly chosen risk profile\n' >&2
          return 3
        fi
        ;;
    esac
    previous="$argument"
  done
  cmd_launch --settings '{"ultracode":true}' "$@"
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

  printf '\n== configured vs LIVE catalog ==\n'
  local stale stale_status=0
  stale="$(not_live_providers "${port:-}")" || stale_status=$?
  if [ "$stale_status" -ne 0 ]; then
    printf '  unknown : could not compare (gateway down, or jq/curl unavailable). A configured\n'
    printf '            provider is NOT proven live by appearing in the list above.\n'
  elif [ -z "$stale" ]; then
    printf '  ok      : every configured provider is served by the running gateway\n'
  else
    printf '  NOT-LIVE: configured but NOT in the running gateway catalog:\n'
    printf '            %s\n' $stale
    printf '            A request naming one of these does NOT fail closed -- it is classified\n'
    printf '            routeKind: "default-provider" and billed against the DEFAULT provider.\n'
    printf '            Fix: mise -C %s exec -- ocx sync, then this script'"'"'s restart.\n' "$root"
  fi

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

normalize_identifier() {
  LC_ALL=C tr '[:upper:]_.' '[:lower:]--' <<<"$1" | tr -d '[:space:]'
}

anthropic_identifier() {
  case "$(normalize_identifier "$1")" in
    anthropic|anthropic-apikey|anthropic-key|anthropic-claude|claude|claude-ai) return 0 ;;
    *) return 1 ;;
  esac
}

endpoint_host() {
  local value authority host
  value="$(LC_ALL=C tr '[:upper:]' '[:lower:]' <<<"$1")"
  case "$value" in http://*|https://*) ;; *) return 1 ;; esac
  authority="${value#*://}"; authority="${authority%%/*}"; authority="${authority##*@}"
  host="${authority%%:*}"; host="${host%.}"
  [ -n "$host" ] && printf '%s' "$host"
}

anthropic_endpoint_argument() {
  local argument value host next_value=false
  for argument in "$@"; do
    if $next_value; then
      value="$argument"; next_value=false
    else
      case "$(normalize_identifier "$argument")" in
        --base-url|--endpoint|--auth-url) next_value=true; continue ;;
        --base-url=*|--endpoint=*|--auth-url=*) value="${argument#*=}" ;;
        *) continue ;;
      esac
    fi
    host="$(endpoint_host "$value" || true)"
    case "$host" in anthropic.com|*.anthropic.com|claude.ai|*.claude.ai) return 0 ;; esac
  done
  return 1
}

explicit_non_anthropic_endpoint_argument() {
  local argument value host next_value=false found=false
  for argument in "$@"; do
    if $next_value; then
      value="$argument"; next_value=false
    else
      case "$(normalize_identifier "$argument")" in
        --base-url|--endpoint) next_value=true; continue ;;
        --base-url=*|--endpoint=*) value="${argument#*=}" ;;
        *) continue ;;
      esac
    fi
    found=true; host="$(endpoint_host "$value" || true)"
    [ -n "$host" ] || return 1
    case "$host" in anthropic.com|*.anthropic.com|claude.ai|*.claude.ai) return 1 ;; esac
  done
  $found
}

known_non_anthropic_provider() {
  case "$(normalize_identifier "$1")" in
    cursor|xai|command-code|kimi|kiro|openai-apikey|umans|opencode-go|neuralwatt|openrouter|cline-pass|cline|orcarouter|bizrouter|groq|google|google-vertex|google-antigravity|azure-openai|ollama|vllm|lm-studio|deepseek|cerebras|deepinfra|hyperbolic|baseten|commandcode|together|fireworks|firepass|moonshot|huggingface|nvidia|venice|zai|zhipu-bigmodel|nanogpt|synthetic|siliconflow|qwen-cloud|tencent-coding-plan|volcengine|volcengine-coding-plan|volcengine-agent-plan|qianfan|alibaba|alibaba-token-plan|alibaba-token-plan-intl|parallel|zenmux|litellm|ollama-cloud|mistral|minimax|minimax-cn|kimi-code|opencode-zen|vercel-ai-gateway|opencode-free|xiaomi|kilo|mimo-free|cloudflare-ai-gateway|cloudflare-workers-ai|github-copilot|gitlab-duo|openai) return 0 ;;
    *) return 1 ;;
  esac
}

configured_provider_class() {
  local provider="$1" config result
  config="$(ocx config show --json 2>/dev/null)" || return 2
  command -v jq >/dev/null 2>&1 || return 2
  result="$(jq -r --arg provider "$provider" '
    ($provider | ascii_downcase) as $wanted
    | (.providers // {} | to_entries | map(select((.key | ascii_downcase) == $wanted)) | first | .value) as $p
    | if $p == null then "absent" else
        (($p.baseUrl // $p.baseURL // $p.endpoint // "") | ascii_downcase) as $url
        | if ($url | test("^https?://([^/]+\\.)?(anthropic\\.com|claude\\.ai)(:[0-9]+)?(/|$)"))
          then "anthropic" else "other" end
      end
  ' 2>/dev/null <<<"$config")" || return 2
  case "$result" in anthropic) return 0 ;; other) return 1 ;; absent) return 3 ;; *) return 2 ;; esac
}

provider_allowed_for_mutation() {
  local provider="$1" status
  anthropic_identifier "$provider" && return 1
  configured_provider_class "$provider"; status=$?
  case "$status" in
    0|2) return 1 ;;
    1) return 0 ;;
    3) known_non_anthropic_provider "$provider" ;;
    *) return 1 ;;
  esac
}

refuse_configuration() {
  refuse "opencodex configuration route refused ($1); this split plane admits only reviewed non-Anthropic provider operations"
}

# `ocx provider add` accepts `--api-key <value>`, and argv is world-readable via `ps` for the
# life of the call -- on a shared host any other user can read the key. This WARNS rather than
# refuses, because upstream `provider add` has no stdin or env alternative for the key (verified:
# no --api-key-stdin flag and no apiKeyEnv field exist), so refusing would block the only
# non-interactive way to register a key-authenticated provider. The warning names the two-step
# alternative instead. The flag NAME is printed; the value never is.
warn_argv_credential() {
  local argument
  for argument in "$@"; do
    case "$(normalize_identifier "$argument")" in
      --api-key|--api-key=*|--auth-token|--auth-token=*|--token|--token=*)
        cat >&2 <<'EOF'
WARNING: a credential passed on the command line is readable by every process on this host via
`ps` for the life of the call, and may be recorded in your shell history.

Prefer the two-step form, which reads the key ONLY from piped stdin:
  scripts/opencodex-claude.sh configure provider add <name> --adapter <a> --base-url <url>
  printf '%s\n' "$YOUR_KEY_ENV_VAR" | mise exec -- ocx account add-key <name>

Continuing, because upstream `provider add` offers no stdin or environment alternative for
--api-key. The value is not printed or logged by this wrapper.

EOF
        return 0
        ;;
    esac
  done
}

# An unrecognized route is not a credential-boundary event. Printing the ADR-0003 notice for
# a typo teaches the reader that the boundary fires at random, so it gets its own message that
# names the admitted routes instead.
refuse_unknown_route() {
  printf '\nREFUSED: `ocx %s` is not an admitted configuration route.\n\n' "$1" >&2
  cat >&2 <<'EOF'
This wrapper admits a reviewed subset of the upstream surface, so an unrecognized or new
upstream route fails closed rather than passing through unreviewed.

Read-only inspection:
  account list [provider] | account current <provider>
  provider list | provider show | provider presets | provider selected
  models list | models show | config show | config get | config validate
  help <verb>                     (also: bare `account`, `provider`, `models`, `config`)

Reviewed mutations (non-Anthropic providers only):
  login <provider> | logout <provider>
  account login|reauth|code|cancel|use|remove|add-key <provider> ...
  provider add|edit|update|remove|set-default <provider> ...
  provider test <provider>        (read-only reachability check)

Inspect the full upstream surface without running it:
  mise exec -- ocx help <verb>
EOF
  exit 3
}

cmd_configure() {
  require_ocx
  if [ "$#" -eq 0 ]; then
    printf 'Reviewed opencodex provider configuration. This wrapper never prints secret argv.\n\n'
    printf 'Supported: inspected non-Anthropic login/account/provider mutations and masked\n'
    printf 'provider/account/config inspection. Interactive setup, GUI, arbitrary config\n'
    printf 'mutation/import/export, and unknown future routes fail closed.\n\n'
    printf 'A provider add/edit/remove writes the CONFIG FILE only. It is not in the running\n'
    printf 'gateway until `ocx sync` plus a restart; until then requests naming it fall through\n'
    printf 'to the DEFAULT provider. This route prints that sequence after a successful\n'
    printf 'mutation, and `status` reports any configured-but-NOT-LIVE provider.\n\n'
    printf 'Pass a key via piped stdin (`ocx account add-key <name>`) rather than --api-key\n'
    printf 'where possible: argv is readable by every process on this host via ps.\n\n'
    printf 'Run `mise -C %s exec -- ocx help <verb>` to inspect the upstream surface.\n' "$root"
    return 0
  fi

  local verb subcommand provider route mutates_providers=false
  verb="$(normalize_identifier "${1:-}")"
  subcommand="$(normalize_identifier "${2:-}")"
  route="$verb${subcommand:+ $subcommand}"
  case "$verb $subcommand" in
    "help "|"--help "|"-h "|"help "*|"provider list"|"provider show"|"provider presets"|"provider selected"|"account list"|"account current"|"models list"|"models show"|"config show"|"config get"|"config validate")
      ;;
    # A bare inspection verb prints its own usage and reads nothing it should not. Refusing it
    # sent readers to the credential notice for what is really a help request.
    "account "|"provider "|"models "|"config ")
      ;;
    "init "|"setup "|"gui "|"config set"|"config unset"|"config import"|"config export")
      refuse_configuration "unbounded-route"
      ;;
    "login "*|"logout "*)
      provider="${2:-}"
      provider_allowed_for_mutation "$provider" || refuse_configuration "anthropic-or-unclassifiable-provider"
      ;;
    "provider add")
      provider="${3:-}"
      anthropic_identifier "$provider" && refuse_configuration "anthropic-provider"
      anthropic_endpoint_argument "${@:4}" && refuse_configuration "anthropic-endpoint"
      provider_allowed_for_mutation "$provider" || explicit_non_anthropic_endpoint_argument "${@:4}" \
        || refuse_configuration "anthropic-or-unclassifiable-provider"
      mutates_providers=true
      ;;
    "provider edit"|"provider update"|"provider remove"|"provider set-default")
      provider="${3:-}"
      provider_allowed_for_mutation "$provider" || refuse_configuration "anthropic-or-unclassifiable-provider"
      anthropic_endpoint_argument "${@:4}" && refuse_configuration "anthropic-endpoint"
      mutates_providers=true
      ;;
    # `provider test` reads a provider's reachability and writes nothing, so it takes no sync
    # notice. It is admitted for non-Anthropic providers only, on the same rule as the
    # mutations, because it makes a live call using that provider's stored credential.
    "provider test")
      provider="${3:-}"
      provider_allowed_for_mutation "$provider" || refuse_configuration "anthropic-or-unclassifiable-provider"
      ;;
    "account login"|"account reauth"|"account code"|"account cancel"|"account use"|"account remove"|"account add-key"|"account alias"|"account rename")
      provider="${3:-}"
      provider_allowed_for_mutation "$provider" || refuse_configuration "anthropic-or-unclassifiable-provider"
      ;;
    *) refuse_unknown_route "$route" ;;
  esac
  warn_argv_credential "$@"
  printf 'about to run an approved opencodex configuration route (%s)\n\n' "$route"
  local status=0
  ocx "$@" || status=$?
  # The notice is printed on success only. After a failed mutation there may be nothing to sync,
  # and telling an operator to sync a write that did not land would be a false instruction.
  if [ "$status" -eq 0 ] && $mutates_providers; then
    print_sync_required_notice "$route"
  fi
  return "$status"
}

case "${1:-}" in
  launch) shift; cmd_launch "$@" ;;
  launch-ultracode) shift; cmd_launch_ultracode "$@" ;;
  status) shift; cmd_status "$@" ;;
  restart) shift; cmd_restart "$@" ;;
  configure) shift; cmd_configure "$@" ;;
  -h|--help|help) usage ;;
  "") usage >&2; exit 2 ;;
  *) printf 'error: unknown subcommand %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac
