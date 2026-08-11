#!/bin/bash
# opencodex-claude.sh — launcher and supervisor for the pinned opencodex gateway (`ocx`).
#
# Purpose: run Claude Code pointed at the local opencodex proxy so that BOTH kinds of model are
# usable in ONE session. The gateway decides per request (server/claude-messages.ts): a genuine
# `claude*`/`anthropic*` id that no alias or modelMap claims is forwarded VERBATIM to
# api.anthropic.com carrying Claude Code's own login, while `gpt-*`, `muse/*`, and the
# `claude-ocx-*` alias family route to their own providers on their own credentials.
# Subcommands: ensure | launch | launch-ultracode | status | restart | configure.
#
# ADR-0014 REPLACED THE SPLIT PLANE. Until 2026-08-11 this script did the opposite: `launch`
# isolated CLAUDE_CONFIG_DIR, scrubbed every ANTHROPIC_*/CLAUDE_*/AWS_* variable, and REFUSED
# when a subscription credential was reachable, because ADR-0003 read Anthropic's policy as
# prohibiting subscription routing outright. Two findings retired that reading:
#
#   * Anthropic's own gateway documentation describes this exact configuration. Setting only
#     ANTHROPIC_BASE_URL, with NO gateway credential, "doesn't replace the subscription...  a
#     saved claude.ai login remains the active credential, so its usage limits and billing
#     apply", and such gateways "must forward the OAuth capability in anthropic-beta" — which
#     opencodex does, stripping only hop-by-hop headers plus host/content-length/
#     accept-encoding/x-opencodex-api-key/origin. (code.claude.com/docs/en/llm-gateway)
#   * The prohibition that does exist is narrower than ADR-0003 assumed: it forbids THIRD-PARTY
#     DEVELOPERS offering claude.ai login or routing "on behalf of their users", not an operator
#     routing their own credential through their own local hop.
#     (code.claude.com/docs/en/legal-and-compliance)
#
# So the scrub, the isolated plane, the four subscription refusals, the session-inheritance
# call, the `session` verbs, and the separately named `claude-subscription` escape hatch are all
# GONE. Anthropic still "doesn't support routing Claude Code to non-Claude models through any
# gateway", so the routed half remains unsupported-but-permitted: no Anthropic credential is
# used for those turns. See docs/adr/0014.
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
# WHAT THIS SCRIPT DELIBERATELY DOES NOT DO
#   * It never reads, copies, prints, or persists a credential. Claude Code holds its own login
#     and `ocx claude` passes it to the gateway; this wrapper only checks for NAMES and PREFIXES
#     that would silently defeat the route (see assert_gateway_route_is_effective).
#   * It does not verify which model actually served a request. The canary in
#     docs/research/2026-08-05-gateway-selection-memo.md §4 is the qualification gate and is
#     still unrun. A healthy gateway proves reachability, never model identity — and the routed
#     branch RE-LABELS its reply with the requested model, so the response body is inadmissible
#     as evidence. Only the gateway's own request log distinguishes the branches.
#   * A healthy `status` is evidence, not authorization. Exit 0 means the proxy answered an
#     identity-checked health probe at that moment. It grants no authority for any outward
#     effect.
#   * It does NOT isolate the operator's Codex state. `ocx ensure`/`start` rewrite ~/.codex
#     (pointing Codex's openai provider at the proxy) and `ocx stop` restores it — an upstream
#     side effect this wrapper surfaces rather than hides.
#   * `launch` now uses the GLOBAL ~/.claude config dir, so `ocx claude` writes its `ocx-*.md`
#     roster agents and gateway model cache there. That cache write is load-bearing, not
#     incidental: Claude Code only refreshes it while holding a credential, so without the
#     pre-write the /model picker would never list the routed ids.
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
# No isolated config root any more (ADR-0014): `launch` uses the operator's own ~/.claude, which
# is what lets Claude Code present its existing login to the gateway. assets/claude/
# session-inheritance.sh still exists and is still used by scripts/muse-claude.sh, which keeps
# its own plane; this launcher no longer sources it because there is nothing to inherit into.
state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
log_dir="$state_home/agentic-sdlc/ocx-logs"
# Bound on how long a just-started gateway may take to answer an identity-checked probe.
# `ocx ensure` already waits internally (8s); this is the wrapper's own outer bound, so a
# hung or half-up start is capped rather than inherited.
readiness_timeout_seconds=15
readiness_poll_seconds=1

# --- help is not a side-effecting operation ------------------------------------------------
#
# THE DEFECT (2026-08-07, reproduced against the INSTALLED command by reading its stdout rather
# than its exit code -- an earlier check that discarded output could not tell "printed usage"
# from "launched Claude Code, which then exited 0"). `launch --help` ran the ENTIRE launch
# preparation before handing `--help` to Claude Code: it mounted session inheritance, constructed
# settings.json inside the isolated dir, and against a healthy gateway would have ensured and
# launched. Top-level `-h`/`--help`/`help` were already correct; the verb level was not.
#
# THE SEMANTIC, chosen deliberately rather than inherited from argument order. A bare `-h` or
# `--help` in the FIRST position after a verb means "explain this command". It does not mean
# "prepare a gateway plane, mount session state, and then ask Claude Code for its help text" --
# nobody types the second thing, and a help request that mutates a config dir is a defect no
# matter how good the text it eventually prints. So the first-position form is intercepted, prints
# this wrapper's own verb help, and exits 0 having touched nothing.
#
# PASS-THROUGH REMAINS POSSIBLE, because a wrapper that can never forward an argument is its own
# defect. `--` ends this wrapper's options in the ordinary POSIX sense: everything after it is
# forwarded verbatim, so `launch -- --help` reaches Claude Code's own help through a real prepared
# session. Only the FIRST argument is inspected, so `launch --model x -- --help` also forwards.
#
# The escape is the leading `--` and nothing else: a heuristic that tried to guess which later
# `--help` was "really" for Claude Code would have to distinguish a flag from a flag's VALUE, and
# guessing wrong either swallows an argument or launches when the operator asked a question.
#
# `configure` is the one route where the bare word `help` is NOT a request for this text: `ocx help
# <verb>` is the documented way to inspect the upstream surface, and it is already an admitted
# read-only route. Intercepting it would break the only route that answers "what can upstream
# actually do", so only the flag spellings are intercepted there.
verb_help_requested() {
  local route="$1" argument="${2:-}"
  case "$argument" in
    -h|--help) return 0 ;;
    help) [ "$route" = configure ] && return 1; return 0 ;;
    *) return 1 ;;
  esac
}

# Strip a single leading `--`. Callers apply it AFTER the help check, so `--` is the thing that
# disables interception rather than something interception has to reason about.
strip_forwarding_separator() {
  [ "${1:-}" = "--" ] && return 0
  return 1
}

# Per-verb help. Names the operator-facing `ccodex` spelling first because that is the installed
# command, then the direct and alias forms, all three of which reach this same code.
verb_usage() {
  case "$1" in
    ensure)
      cat <<'EOF'
usage: ccodex ensure
       opencodex-claude.sh ensure

Ensure the gateway is healthy without launching Claude Code: start it if down, restart once
if half-up, and fail closed if it never becomes healthy. Takes no arguments.

Plain `claude` starts the native Anthropic-routed CLI and does not use this gateway. Use
`ccodex launch` only when you intend the separately configured non-Anthropic gateway plane.
EOF
      ;;
    launch|launch-ultracode)
      local operator_verb=ultracode ultra=$'\n\nSession Ultracode is applied.'
      if [ "$1" = launch ]; then
        operator_verb=launch; ultra=''
      fi
      cat <<EOF
usage: ccodex $operator_verb [claude args...]
       opencodex-claude.sh $1 [claude args...]

Ensure the gateway is healthy (start it if down, restart once if half-up), then launch Claude
Code through it using your OWN ~/.claude configuration and login. Fails closed if the gateway
never becomes healthy.${ultra}

Both kinds of model work in this one session (ADR-0014). A genuine claude/anthropic id that no
alias or modelMap claims passes through verbatim to Anthropic on your own subscription; every
gateway id routes to its own provider on that provider's credential. This wrapper never reads
your credential -- it only refuses when something would silently defeat the route.

Plain \`claude\` talks to Anthropic directly and does not involve this gateway at all, so no
gateway model is selectable there. This route is the one that puts both catalogs in one session.
EOF
      [ "$1" = launch-ultracode ] && cat <<'EOF'

This route owns the session --settings value, so it refuses a competing --settings argument,
and it never bypasses permissions.
EOF
      cat <<'EOF'

Common arguments, all forwarded to Claude Code:
  --model <id>              Any id in the running gateway's live catalog, including a
                            namespaced one: --model muse/muse-spark-1.2. See `ccodex models`.

Config dir: your global ~/.claude. `ocx claude` writes its ocx-*.md roster agents and the
gateway model cache there. That cache write is what puts the routed ids in the /model picker,
because Claude Code only refreshes it while holding a credential.

Refused (exit 3) when the route would not actually be used: a CLAUDE_CODE_USE_BEDROCK-style
provider-routing variable exported or present in ~/.claude/settings.json `env` (either outranks
this gateway's base URL), or an sk-ant-api* Console key in ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN
(it takes the same native branch but bills API credits, not your subscription).

THIS TEXT IS THIS WRAPPER'S. To reach Claude Code's OWN --help, end this wrapper's options
with `--`, which prepares a real session and forwards everything after it verbatim:
  ccodex launch -- --help
Or run `claude --help` inside a launched session.

exit codes: 0 ok · 1 failure/unhealthy · 2 usage · 3 refused (a boundary declined it)
EOF
      ;;
    status)
      cat <<'EOF'
usage: ccodex status
       opencodex-claude.sh status

Supervision view, read-only: pid, port, uptime, healthy/down, log location, configured
providers, each configured provider compared against the running gateway's LIVE catalog,
the environment-variable policy for THIS shell, session-inheritance coverage, and the
attribution log stream command. Takes no arguments.

Exit 0 means the gateway answered an identity-checked health probe at that moment. That is
evidence, not authorization, and it says nothing about which model serves a request.
EOF
      ;;
    restart)
      cat <<'EOF'
usage: ccodex restart
       opencodex-claude.sh restart

Stop the gateway cleanly if it is running, then ensure it is back up and healthy. Fails
closed on an unclean stop rather than racing opencodex's own guard. Takes no arguments.

A restart interrupts in-flight turns in every session routed through the gateway, and
`ocx` rewrites shared ~/.codex configuration as part of its lifecycle.
EOF
      ;;
    configure)
      cat <<'EOF'
usage: ccodex configure [ocx args...]
       opencodex-claude.sh configure [ocx args...]

Reviewed passthrough to opencodex's own provider login/config commands. A bare `configure`
with no arguments prints the admitted surface in detail; this text explains the route.

Admitted: inspected non-Anthropic login/account/provider mutations, and masked
provider/account/config inspection. Interactive setup, GUI, arbitrary config
mutation/import/export, and unknown future upstream routes fail closed with exit 3.

A provider add/edit/remove writes the CONFIG FILE only. It is NOT in the running gateway
until `ocx sync` plus a restart, and until then a request naming it falls through to the
DEFAULT provider. This route prints that sequence after a successful mutation and never
runs it for you: `ocx sync` rewrites shared ~/.codex config and a restart interrupts
in-flight turns, so each is separately authorized.

Pass a key via piped stdin (`ocx account add-key <name>`) rather than --api-key where
possible: argv is readable by every process on this host via `ps`.

To inspect the UPSTREAM surface without running it:
  ccodex configure help <verb>
EOF
      ;;
  esac
}

usage() {
  cat <<'EOF'
usage: opencodex-claude.sh <ensure|launch|launch-ultracode|status|restart|configure> [args...]

  ensure                    Ensure the gateway is healthy without launching Claude Code.
  launch [claude args...]   Ensure the gateway is healthy (start it if down, restart once if
                            half-up), then launch Claude Code through it using your own
                            ~/.claude configuration and login. Native claude models pass
                            through to Anthropic on your subscription; gateway models route to
                            their own providers -- both in one session. Fails closed if the
                            gateway never becomes healthy, and refuses (exit 3) when a
                            provider-routing key or a Console API key would silently defeat
                            the route.
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

Per-verb help prints this wrapper's own text and runs nothing:
  opencodex-claude.sh launch --help
To reach Claude Code's own --help through a real prepared session, end this wrapper's
options with `--`:
  opencodex-claude.sh launch -- --help

exit codes: 0 ok · 1 failure/unhealthy · 2 usage · 3 refused (the gateway route would not be used)
EOF
}

ocx() {
  mise -C "$root" exec -- ocx "$@"
}

# `jq` resolved the same way `ocx` is, and for the same reason.
#
# THE DEFECT THIS FIXES (2026-08-08, found by a fresh-host container install). Every caller here
# used a bare `jq`, which is absent from the operator's PATH: this command is explicitly designed
# to run WITHOUT mise on PATH, and `jq` arrives only through mise's pinned toolchain
# (`mise.toml`, jq = 1.8.2). A missing `jq` made `configured_provider_class` return
# "unclassifiable", which made every `configure` mutation refuse with
# `anthropic-or-unclassifiable-provider` -- on a host where the provider was correctly configured
# as non-Anthropic. The refusal named the wrong cause, so it sent the operator to inspect a
# provider config that was already right.
#
# Every `configure` route already calls require_ocx, which requires mise, so the pinned `jq` is
# reachable wherever classification runs. A bare `jq` is preferred when present, because an
# operator who installed their own has a working tool and a mise round-trip per call is pure
# latency; the pinned copy is the fallback rather than the first choice.
jq() {
  if [ -z "${resolved_jq:-}" ]; then
    # `type -P` searches the PATH only. `command -v jq` would find THIS FUNCTION and recurse,
    # because a function shadows the name it is probing -- the same shadowing class of bug that
    # made a stale shell function hide the installed `ccodex`.
    resolved_jq="$(type -P jq 2>/dev/null || true)"
    [ -n "$resolved_jq" ] || resolved_jq="mise"
  fi
  if [ "$resolved_jq" = mise ]; then
    mise -C "$root" exec -- jq "$@"
  else
    "$resolved_jq" "$@"
  fi
}

# True when jq is usable at all, by either route. Callers use this instead of `command -v jq`,
# which now always succeeds (the function above shadows it) and so no longer answers the
# question. A host with neither a PATH jq nor a resolvable pinned one still degrades honestly.
jq_available() {
  jq --version >/dev/null 2>&1
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
This route sends Claude Code through the local gateway using your own login, so a setting that
outranks the gateway's base URL would make the launch a no-op that still looks routed. Rather
than print a gateway banner over traffic that never reached it, the launch stops here.

A cloud-provider route is a different command, not a degraded version of this one: keep Bedrock
or Vertex in a per-command wrapper of your own and leave the global settings document clean.

Anthropic's gateway documentation covers this configuration: with ANTHROPIC_BASE_URL set and NO
gateway credential, a saved claude.ai login stays the active credential and its billing applies.
Routing Claude Code to NON-Claude models through any gateway is not supported by Anthropic --
permitted, since no Anthropic credential is used for those turns, but unsupported. See ADR-0014.
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
  jq_available || return 1
  ocx provider list --json 2>/dev/null \
    | jq -r '(.configured // []) | .[] | select(.name != null) | .name' 2>/dev/null
}

# Model IDs the RUNNING gateway serves. Namespaced as `<provider>/<model>` for a custom
# provider, bare for the default one, so the provider segment is what identifies liveness.
live_catalog_model_ids() {
  local port="$1"
  [ -n "$port" ] || return 1
  command -v curl >/dev/null 2>&1 || return 1
  jq_available || return 1
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
  default_name="$(jq_available \
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
  ccodex restart

Until then a request naming this provider's model does NOT fail closed. It is classified
\`routeKind: "default-provider"\` and forwarded to the DEFAULT provider, so it is attempted and
billed against the wrong upstream while the attribution log records the wrong provider.

Neither step is run for you: \`ocx sync\` rewrites shared ~/.codex config and a restart
interrupts in-flight turns, so both are separately authorized operations.

Confirm the provider went live before dispatching anything to it:
  ccodex status
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
  printf '  ccodex status\n' >&2
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

# --- route integrity ---------------------------------------------------------------------
#
# The gateway route is the ORDINARY route now and it deliberately PRESERVES Claude Code's own
# claude.ai login (ADR-0014). Nothing below tries to block that credential -- the previous
# scrub/isolation/refusal machinery existed to prevent exactly what this route now wants, and
# it is gone.
#
# What remains guards two SILENT failures that would otherwise be indistinguishable from
# success, which matters more now that this is the default rather than a named escape hatch:
#
#   1. A provider-routing key in the GLOBAL settings.json `env` block OUTRANKS
#      ANTHROPIC_BASE_URL. Under CLAUDE_CODE_USE_BEDROCK the client consults
#      ANTHROPIC_BEDROCK_BASE_URL instead, so the gateway is bypassed entirely and the turn
#      bills the cloud account while this wrapper prints a gateway banner. Measured on a real
#      host on 2026-08-10: the request never reached a local capture listener and was still
#      answered. This is not a theoretical hazard.
#   2. An `sk-ant-api*` Console key satisfies opencodex's bare `sk-ant-` passthrough gate
#      (hasAnthropicNativeCredential in server/claude-messages.ts), so it takes the SAME
#      native branch and bills API credits while looking like subscription traffic. The
#      prefix is the only thing separating the two.
#
# Names and prefixes only: no credential value is read, printed, copied, or persisted.

# Claude Code resolves a cloud-provider credential ABOVE its own OAuth, and under Bedrock or
# Vertex it stops consulting ANTHROPIC_BASE_URL at all. Either way the gateway is not in the
# path, so launching would report a route that does not exist.
gateway_bypassing_env_name() {
  local name
  for name in CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY \
              AWS_BEARER_TOKEN_BEDROCK ANTHROPIC_BEDROCK_BASE_URL ANTHROPIC_VERTEX_BASE_URL; do
    [ -n "${!name:-}" ] && { printf '%s' "$name"; return 0; }
  done
  return 1
}

# The same keys, plus the credential-producing ones, in the global settings document. Shell env
# is checked separately above because settings.json is the channel an operator forgets: it is
# read on every launch and survives a clean shell.
settings_bypassing_key_name() {
  local settings="$HOME/.claude/settings.json"
  [ -f "$settings" ] || return 1
  jq_available || return 1
  jq -r '
    ((.env // {}) | keys) as $env
    | [ $env[] | select(. == "CLAUDE_CODE_USE_BEDROCK" or . == "CLAUDE_CODE_USE_VERTEX"
        or . == "CLAUDE_CODE_USE_FOUNDRY" or . == "AWS_BEARER_TOKEN_BEDROCK"
        or . == "ANTHROPIC_BEDROCK_BASE_URL" or . == "ANTHROPIC_VERTEX_BASE_URL"
        or . == "ANTHROPIC_API_KEY" or . == "ANTHROPIC_AUTH_TOKEN" or . == "ANTHROPIC_BASE_URL") ]
      as $routing
    | (if (.apiKeyHelper // null) != null then ["apiKeyHelper"] else [] end) as $helper
    | ($routing + $helper) | first // empty
  ' "$settings" 2>/dev/null | head -1 | grep . || return 1
}

# An exported Console key displaces the OAuth login and bills credits on the very same native
# passthrough branch, so it is refused by PREFIX rather than silently accepted.
console_key_env_name() {
  local name value
  for name in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN; do
    value="${!name:-}"
    case "$value" in
      sk-ant-api*) printf '%s' "$name"; return 0 ;;
    esac
  done
  return 1
}

assert_gateway_route_is_effective() {
  local offending
  if offending="$(gateway_bypassing_env_name)"; then
    refuse "$offending is exported, which routes Claude Code to a cloud provider and bypasses the gateway entirely; unset it or use \`ccode\` for that route"
  fi
  if offending="$(settings_bypassing_key_name)"; then
    refuse "$HOME/.claude/settings.json carries $offending, which outranks this route's gateway base URL; move it to a per-command wrapper instead of the global document"
  fi
  if offending="$(console_key_env_name)"; then
    refuse "$offending holds an sk-ant-api* Console key, which takes the same native passthrough branch and bills API credits rather than your subscription"
  fi
}

# --- subcommands -------------------------------------------------------------------------

cmd_ensure() {
  require_ocx
  ensure_gateway_up
  printf '\nhealthy: the gateway answered an identity-checked health probe. That is evidence,\n'
  printf 'not authorization, and it does not launch Claude Code.\n'
}

cmd_launch() {
  require_ocx
  # Checked BEFORE any gateway is started: a refused launch must not leave a proxy running
  # that the operator did not ask for.
  assert_gateway_route_is_effective

  if ! command -v claude >/dev/null 2>&1; then
    printf 'error: the `claude` CLI is not on PATH; opencodex cannot launch it\n' >&2
    exit 1
  fi

  printf 'preparing gateway-routed Claude Code\n'
  ensure_gateway_up
  local json port
  json="$(gateway_health_json)"
  port="$(health_field port "$json")"
  printf '  config dir: %s (global)\n' "$HOME/.claude"
  printf '              ocx claude writes its roster agents and gateway model cache HERE; this\n'
  printf '              route no longer uses a private plane (ADR-0014 supersedes ADR-0010 here)\n'
  printf '  auth      : your own Claude login is preserved and sent to the gateway. Native claude\n'
  printf '              models pass through verbatim to Anthropic on your subscription; gateway\n'
  printf '              models route to their own providers. This wrapper never reads it.\n'
  printf '  routed at : http://127.0.0.1:%s\n' "${port:-unknown}"
  # Forwarded Claude arguments can contain inline settings and secrets. Never echo raw argv.
  printf '  command   : mise -C %s exec -- ocx claude [forwarded arguments withheld]\n\n' "$root"
  # ocx claude re-checks liveness, then execs `claude` with stdio inherited. It injects a marker
  # token ONLY when markerMode resolves to "proxy" (cli/claude.ts:133) or an admission key is
  # configured (:115); with a detected login neither fires, so Claude Code keeps its own OAuth
  # and the native models pass through. It also pre-writes the gateway model cache (:286), which
  # is what puts the routed ids in the /model picker.
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
    printf '  hint    : ccodex restart\n'
  else
    printf '  state   : DOWN\n'
    printf '  port    : %s (configured)\n' "${port:-unknown}"
    printf '  hint    : ccodex ensure   (or `ccodex launch`, which also ensures it is up)\n'
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
    printf '            Fix: mise -C %s exec -- ocx sync, then `ccodex restart`.\n' "$root"
  fi

  # There is no plane to inherit into any more (ADR-0014): `launch` uses the global config dir,
  # so its session data IS the operator's own. What replaced that report is the route check --
  # a bypassing key is the one remaining way a launch can look routed and not be.
  printf '\n== gateway route reachability ==\n'
  local blocker=""
  if blocker="$(gateway_bypassing_env_name)"; then
    printf '  BYPASSED: %s is exported; a launch would reach a cloud provider, not this gateway\n' "$blocker"
  elif blocker="$(settings_bypassing_key_name)"; then
    printf '  BYPASSED: %s in %s/.claude/settings.json outranks the gateway base URL\n' "$blocker" "$HOME"
  elif blocker="$(console_key_env_name)"; then
    printf '  MISBILLED: %s holds an sk-ant-api* Console key; native turns would bill credits\n' "$blocker"
  else
    printf '  ok      : nothing in this shell or the global settings document outranks the gateway\n'
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

# Exit status: 0 anthropic · 1 other · 2 cannot-classify · 3 absent-from-config · 4 no-jq.
# 4 is separated from 2 because the two demand different messages: 2 means the config could not
# be read or parsed, which is genuinely about the provider; 4 means this HOST lacks a tool, which
# is about the installation and is fixable. Collapsing them is what made a missing `jq` report
# itself as an unclassifiable provider.
configured_provider_class() {
  local provider="$1" config result
  config="$(ocx config show --json 2>/dev/null)" || return 2
  jq_available || return 4
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

# Still fail-closed on every genuinely-unclassifiable case. The one behavior change is that a
# missing `jq` now REFUSES BY ITS OWN NAME (exit 4 -> refuse_missing_jq) instead of being reported
# as an unclassifiable provider, which sent operators to inspect a provider config that was
# already correct.
provider_allowed_for_mutation() {
  local provider="$1" status
  anthropic_identifier "$provider" && return 1
  configured_provider_class "$provider"; status=$?
  case "$status" in
    0|2) return 1 ;;
    1) return 0 ;;
    3) known_non_anthropic_provider "$provider" ;;
    4) refuse_missing_jq ;;
    *) return 1 ;;
  esac
}

# A tool this host cannot resolve is not a policy refusal, so it does not borrow the
# subscription-boundary notice. It names the tool, the reason it is normally present, and the fix.
refuse_missing_jq() {
  printf '\nREFUSED: cannot classify this provider because `jq` is unavailable on this host.\n\n' >&2
  cat >&2 <<EOF
This is a MISSING TOOL, not a rejected provider. Classification decides whether a configure
mutation targets a non-Anthropic provider (admitted) or an Anthropic one (refused under
ADR-0003), and it cannot be decided without reading the provider config.

\`jq\` is pinned by this repository (mise.toml, jq = 1.8.2) and is normally resolved through it,
so seeing this means neither a PATH \`jq\` nor the pinned copy could be reached. Fix either:

  mise -C $root --locked install     # resolve the pinned toolchain
  # or install jq through your own package manager

Then re-run the same command. Nothing was changed.
EOF
  exit 3
}

refuse_configuration() {
  refuse "opencodex configuration route refused ($1); this split plane admits only reviewed non-Anthropic provider operations"
}

# HARVESTED from the retired muse direct-route launcher (ADR-0007 amendment): refuse to read a
# credential from a path inside this repository. A key file under a tracked tree is one `git add`
# away from being committed, so the refusal is structural rather than advisory. The retired
# launcher applied this to its own key file; here it applies to any configure argument that names
# a file, which is the same hazard reached through a different route.
refuse_in_repo_credential_path() {
  local argument value resolved
  for argument in "$@"; do
    case "$argument" in
      --*=*) value="${argument#*=}" ;;
      /*|./*|../*) value="$argument" ;;
      *) continue ;;
    esac
    case "$value" in /*|./*|../*) ;; *) continue ;; esac
    resolved="$(CDPATH= cd -- "$(dirname -- "$value")" 2>/dev/null && pwd)" || continue
    case "$resolved/" in
      "$root"/*)
        printf 'REFUSED: a credential or config path inside the repository is not accepted (%s)\n' "$value" >&2
        printf 'A credential must never live in a tracked tree. Move it outside %s\n' "$root" >&2
        exit 3
        ;;
    esac
  done
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
  ccodex configure provider add <name> --adapter <a> --base-url <url>
  printf '%s\n' "$YOUR_KEY_ENV_VAR" | ccodex configure account add-key <name>

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
  refuse_in_repo_credential_path "$@"
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

route="${1:-}"
case "$route" in
  ensure|launch|launch-ultracode|status|restart|configure)
    shift
    # Help before anything else, so an intercepted help request has provably run no assertion,
    # started no gateway, and written nothing. Only the FIRST argument is inspected: a later
    # `--help` may be a forwarded argument or a flag's value, and guessing which would either
    # swallow an operator's argument or launch when they asked a question.
    if verb_help_requested "$route" "${1:-}"; then
      verb_usage "$route"
      exit 0
    fi
    # Every route uses one leading wrapper separator to reach Claude Code.
    strip_forwarding_separator "${1:-}" && shift
    case "$route" in
      ensure) [ "$#" -eq 0 ] || { printf 'error: `ensure` takes no arguments\n' >&2; exit 2; }; cmd_ensure ;;
      launch) cmd_launch "$@" ;;
      launch-ultracode) cmd_launch_ultracode "$@" ;;
      status) cmd_status "$@" ;;
      restart) cmd_restart "$@" ;;
      configure) cmd_configure "$@" ;;
    esac
    ;;
  -h|--help|help) usage ;;
  "") usage >&2; exit 2 ;;
  *) printf 'error: unknown subcommand %s\n\n' "$route" >&2; usage >&2; exit 2 ;;
esac
