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
#     and `ocx claude` passes it to the gateway; this wrapper only checks NAMES, value PREFIXES,
#     and base-URL or model-id SHAPES that would silently defeat the route, and never echoes a
#     base URL because one can carry userinfo credentials (see assert_gateway_route_is_effective).
#     A model id is not a credential, so a refused one IS named.
#   * It does not verify which model actually served a request. The qualification gate is the
#     canary in docs/research/2026-08-05-gateway-selection-memo.md §4 (probes A, C, D, E, F).
#     Whether that canary has been run, and its verdict, is recorded evidence this comment does
#     not restate and cannot assert as a static fact — see
#     docs/research/2026-08-07-opencodex-qualification-canary.md and ADR-0005 Decision item 5 for
#     the current disposition. A healthy gateway proves reachability, never model identity — and
#     the routed branch RE-LABELS its reply with the requested model, so the response body is
#     inadmissible as evidence. Only the gateway's own request log (`ocx observe logs --jsonl`,
#     the `resolvedModel` field correlated by `requestId`) distinguishes the branches.
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
#     reports that gap mechanically and refuses to close it silently, because a `sync` that
#     rewrites shared ~/.codex config is its own authorized operation.
#   * By opencodex 2.28.0 (absent in 2.11.1), a sync is not always a ~/.codex config write. With the Codex integration
#     turned off, or with an external `model_provider` owning `config.toml`, the sync is
#     CATALOG-ONLY: it reports a `CodexSyncResult` status of `catalog-only` and leaves
#     config.toml, the journal, and history untouched (it may still refresh the catalog and
#     models-cache files under ~/.codex), and a `validateOnly` injection preflight fails a bad config before any
#     partial rewrite. That narrows the blast radius; it does not move the authorization. This
#     wrapper cannot tell which of the two branches a given host will take without running the
#     sync, so it keeps printing the sequence and still never runs it: a sync that WOULD rewrite
#     ~/.codex needs its own explicit approval.
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# The jq route is resolved once per process and cached HERE, so it is initialized here too: a
# lowercase `resolved_jq` inherited from the environment would otherwise be a third, unadmitted
# route that outranks both admitted ones.
resolved_jq=""
caller_working_dir="$(pwd -P)"
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

Plain `claude` talks to Anthropic directly and does not involve this gateway, so no gateway
model is selectable there. `ccodex launch` is the route that puts both catalogs in one session.
EOF
      ;;
    launch|launch-ultracode)
      local operator_verb=ultracode ultra=$'\n\nSession Ultracode is applied.'
      if [ "$1" = launch ]; then
        operator_verb=launch; ultra=''
      fi
      cat <<EOF
usage: ccodex $operator_verb [--yolo] [claude args...]
       opencodex-claude.sh $1 [--yolo] [claude args...]

Ensure the gateway is healthy (start it if down, restart once if half-up), then launch Claude
Code through it in the caller's current workspace using your OWN ~/.claude configuration and
login. The distribution checkout selects the pinned toolchain, not the project Claude works on.
Fails closed if the gateway never becomes healthy.${ultra}

Both kinds of model work in this one session (ADR-0014). A genuine claude/anthropic id that no
alias or modelMap claims passes through verbatim to Anthropic on your own subscription; every
gateway id routes to its own provider on that provider's credential. This wrapper never reads
your credential -- it only refuses when something would silently defeat the route.

Plain \`claude\` talks to Anthropic directly and does not involve this gateway at all, so no
gateway model is selectable there. This route is the one that puts both catalogs in one session.
EOF
      [ "$1" = launch-ultracode ] && cat <<'EOF'

This route owns the session --settings value, so it refuses a competing --settings argument,
including when --yolo is selected.
EOF
      cat <<'EOF'

Wrapper option (must be first; use `-- --yolo` to forward a literal `--yolo`):
  --yolo                    Start with Claude Code permission checks bypassed. This is equivalent
                            to --dangerously-skip-permissions and disables Auto's classifier.
                            It is unsafe outside an isolated, disposable environment.

Common arguments, forwarded to Claude Code unchanged after preflight:
  --model <id>              Any id in the running gateway's live catalog, including a
                            namespaced one: --model muse/muse-spark-1.2. See `ccodex models`.
  --settings <file-or-json> A JSON object or readable JSON-object file. Ordinary launch checks
                            every occurrence for route-bypassing settings, then forwards accepted
                            arguments unchanged. A later literal `--` ends Claude option parsing.

Config dir: your global ~/.claude. `ocx claude` writes its ocx-*.md roster agents and the
gateway model cache there. That cache write is what puts the routed ids in the /model picker,
because Claude Code only refreshes it while holding a credential.

Claude.ai cloud connectors are off by default in this gateway route because some flatten to
tool names longer than a provider's 64-character ceiling, causing the whole request to fail
before inference. Local, project, and plugin MCP servers remain available. Opt in explicitly
for a compatible model/session with:
  ENABLE_CLAUDEAI_MCP_SERVERS=true ccodex launch

Refused (exit 3) when the route would not actually be used:
  * a CLAUDE_CODE_USE_BEDROCK-style provider-routing variable, exported or enabled in a settings
    `env` block (either outranks this gateway's base URL; a "0"/"false"/empty value counts as off
    and is allowed),
  * an ANTHROPIC_BASE_URL pointing anywhere but this host's loopback gateway, exported OR in a
    settings `env` block (an exported one is PRESERVED into the session; a settings one REPLACES
    what this route sets -- both measured),
  * a cloud-provider model id in ANTHROPIC_DEFAULT_SONNET_MODEL, ANTHROPIC_DEFAULT_OPUS_MODEL,
    ANTHROPIC_DEFAULT_HAIKU_MODEL, ANTHROPIC_DEFAULT_FABLE_MODEL, ANTHROPIC_SMALL_FAST_MODEL, or
    ANTHROPIC_MODEL, exported or in a settings `env` block: a Bedrock region or `anthropic.`
    publisher prefix, or a Vertex publisher path or @<date> suffix (leading/trailing whitespace
    around the id does not defeat this check). That slot picks which id serves a whole model
    family, so the gateway serves that family from the DEFAULT provider instead of Anthropic
    (executed 2026-08-20: the session 400d). A plain claude-* alias is fine, and so is a gateway id
    such as muse/muse-spark-1.2,
  * an apiKeyHelper, or an sk-ant-api* Console key in ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN (it
    takes the same native branch but bills API credits, not your subscription),
  * any explicit --settings value that is empty, not one JSON object or a readable file containing
    one, or carries one of the route blockers above. Its bytes and path are never printed.

EXACTLY these persistent documents are checked, because these are the ones Claude Code was measured to read
for `env`:
  ~/.claude/settings.json
  ./.claude/settings.json          (relative to the directory you launch from)
  ./.claude/settings.local.json    (same)
NOT checked, and so not vouched for: ~/.claude/settings.local.json (measured as NOT read for
`env`), a .claude directory in a PARENT of the launch directory (measured as having no effect),
and enterprise managed policy (/etc/claude-code/managed-settings.json and its drop-in directory,
the platform equivalents, and the WSL registry policy chain) -- that channel is administrator-
owned and its effect on `env` could not be verified here, so this route neither refuses on it nor
claims it is clean.

On a routed launch Claude Code prints `[claude-code:unrecognized_model]` for the gateway id. That
line is cosmetic SDK-registry noise -- the id is absent from the client's own model-metadata
table -- and it is NOT a routing failure: receipt-verified 2026-08-20, the same turn reached its
provider with routeKind explicit-provider and status 200.

Which upstream actually served a turn is answered by a FRESH provider-naming receipt for that
turn, never by this wrapper's output. `ocx observe logs --jsonl` is a bounded rolling window:
rows appear and disappear and tail order is not time order, so re-query, sort by timestamp, and
read an absent row as UNKNOWN rather than as proof that nothing routed.

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
whether anything exported here or in the settings documents Claude Code reads for `env` would
defeat the gateway route, and the attribution log stream command. Takes no arguments.

The route check NAMES the documents it read and names what it did not read, so an `ok` there is
a statement about those documents rather than about every channel that can carry a routing key.

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
runs it for you: a sync can rewrite shared ~/.codex config and a restart interrupts
in-flight turns, so each is separately authorized. By opencodex 2.28.0 (absent in 2.11.1)
the sync is catalog-only -- leaving config.toml, the journal, and history untouched, though
it may still refresh the catalog and models-cache files under ~/.codex -- when the Codex
integration is off or an external `model_provider` owns `config.toml`. A sync that WOULD rewrite ~/.codex still
needs its own approval, and this route cannot tell the two branches apart without
running it.

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
  launch [--yolo] [claude args...]  Ensure the gateway is healthy (start it if down, restart once if
                            half-up), then launch Claude Code through it using your own
                            ~/.claude configuration and login. Native claude models pass
                            through to Anthropic on your subscription; gateway models route to
                            their own providers -- both in one session. Fails closed if the
                            gateway never becomes healthy, and refuses (exit 3) when a
                            provider-routing key, a non-loopback ANTHROPIC_BASE_URL, a
                            cloud-provider model id in a default/small-fast model slot, or a
                            Console API key would silently defeat the route. `launch --help`
                            names the settings documents that check reads.
  launch-ultracode [--yolo] [args...]  Apply the session-only {"ultracode":true} setting, then
                            use the same fail-closed launch path. This convenience route refuses
                            a competing --settings argument. On either launch route, an explicit
                            first --yolo enables Claude Code's permission-bypass mode.
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
  if [ -n "${AGENTIC_SDLC_OCX:-}" ]; then
    "$AGENTIC_SDLC_OCX" "$@"
  else
    mise -C "$root" exec -- ocx "$@"
  fi
}

# An installed ccodex injects the exact ocx executable bound by operator-tools installation, so
# daily launch neither re-evaluates repo-scoped mise nor changes cwd. Direct checkout use keeps a
# mise fallback, but resolves the executable first and then starts it from the caller workspace.
launch_ocx_claude() {
  local executable="${AGENTIC_SDLC_OCX:-}"
  if [ -z "$executable" ]; then
    executable="$(mise -C "$root" which ocx 2>/dev/null || true)"
  fi
  [ -n "$executable" ] && [ -x "$executable" ] || {
    printf 'error: the pinned opencodex executable is unavailable\n' >&2
    exit 1
  }
  "$executable" claude "$@"
}

# TWO ADMITTED ROUTES, IN THIS ORDER, AND NO jq NAME IS EVER RESOLVED FROM AMBIENT PATH.
#
#   1. $AGENTIC_SDLC_JQ -- the exact executable operator-tools bound at install time (see
#      assets/launchers/ccodex.in, which exports it). Highest, because it IS the reviewed binding.
#      Admitted only as an ABSOLUTE path or the literal pinned sentinel; see the guard below.
#   2. the repository's pinned route, `mise -C "$root" exec -- jq` (mise.toml, jq = 1.8.2).
#
# RESIDUAL, STATED RATHER THAN HIDDEN: the pinned route locates `mise` itself on ambient PATH,
# because mise is this repository's documented sole bootstrap prerequisite and is not itself
# pinned -- a substituted `mise` therefore still governs this parse, exactly as it governs `ocx()`,
# `require_ocx`, and `launch_ocx_claude`. What this resolver closes is the jq-specific channel: no
# jq NAME is looked up, and the pin is not skipped in favour of an ambient copy.
#
# UNTIL 2026-08-21 THIS PREFERRED `$(type -P jq)` OVER THE PIN and only reached the pinned route
# when PATH had none, so a source-checkout launch parsed trust-relevant JSON with whatever binary
# the caller's PATH happened to name. That is the substitution ADR-0020 forbids -- "a
# readiness-dependent executable is never selected from ambient PATH without an admitted exact
# identity" -- and this is a trust boundary, not a convenience: this jq classifies the settings
# documents that decide whether a launch is refused, and it reads a provider config and a gateway
# catalog that sit next to credentials. A caller-supplied `jq` that answers `clean` suppresses
# every settings refusal in this file. So no jq NAME is ever resolved: the binding is used as an
# exact absolute path or the pinned route is taken, which also retires the `command -v jq`
# recursion hazard the old probe existed to dodge.
#
# NO SILENT SUBSTITUTION EITHER WAY (ADR-0020 decision 4). A bound-but-broken $AGENTIC_SDLC_JQ does
# NOT quietly fall back to the pinned route, and an unresolvable pinned route does NOT fall back to
# anything: the surface that needed jq blocks with a named reason, and refreshing the binding stays
# an explicit `operator-tools:install` lifecycle step.
jq() {
  if [ -z "${resolved_jq:-}" ]; then
    resolved_jq="${AGENTIC_SDLC_JQ:-mise}"
    # AN ADMITTED EXACT IDENTITY IS AN ABSOLUTE PATH (install_operator_tools.py binds one:
    # "pinned runtime executables are deliberately absolute") or the pinned sentinel. A bare NAME
    # is neither: `AGENTIC_SDLC_JQ=gojq` sends this trust-boundary parse straight back through
    # ambient PATH, and `AGENTIC_SDLC_JQ=jq` re-enters THIS function until the shell dies -- a
    # death that `$(bypassing_settings_document_and_key)` reads as `clean`. A relative path
    # resolves against the caller-controlled launch directory. Each becomes the unadmitted
    # sentinel, so every consumer takes its own named fail-closed branch.
    case "$resolved_jq" in
      mise|/*) ;;
      *) resolved_jq=unadmitted ;;
    esac
  fi
  case "$resolved_jq" in
    mise) mise -C "$root" exec -- jq "$@" ;;
    unadmitted) return 127 ;;
    *) "$resolved_jq" "$@" ;;
  esac
}

# True only when the RESOLVED route above actually executes jq. Callers use this instead of
# `command -v jq`, which now always succeeds (the function above shadows it) and so no longer
# answers the question -- and instead of any name probe, which would answer a different question
# than "does the admitted binary run here".
#
# DELIBERATELY UNCACHED, on ADR-0020 decision 2: configuration is not execution proof, so each
# consumer re-verifies at the moment it needs the tool rather than trusting one earlier answer.
# That also keeps the check honest across a mid-run change to the bound executable.
#
# A false answer means the admitted route is absent, unresolvable, not executable, or quarantined.
# Every consumer below then either REFUSES BY NAME or degrades to an explicitly `unknown` display;
# none of them may read it as "nothing to report".
jq_available() {
  jq --version >/dev/null 2>&1
}

require_ocx() {
  if [ -n "${AGENTIC_SDLC_OCX:-}" ]; then
    [ -x "$AGENTIC_SDLC_OCX" ] || {
      printf 'error: the installed pinned opencodex executable is unavailable; refresh operator tools from the reviewed distribution\n' >&2
      exit 1
    }
  elif ! command -v mise >/dev/null 2>&1; then
    printf 'error: mise is required for direct checkout use of the pinned opencodex build\n' >&2
    exit 1
  fi
  if ! ocx --version >/dev/null 2>&1; then
    printf 'error: pinned opencodex is not installed; run `mise --locked install` in %s\n' "$root" >&2
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
or Vertex in a per-command wrapper of your own and leave the settings documents Claude Code reads
on every launch clean.

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
# Both readers degrade to silence rather than to a false verdict: an unrunnable admitted jq route,
# no curl, or an unparseable payload yields "unknown", never "live" and never "NOT-LIVE". This is a
# DISPLAY, so a named `unknown` is the honest degrade here rather than a refusal -- and `cmd_status`
# prints that reason out loud, because an operator who reads nothing reads it as agreement.

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

# The `<provider>/` prefixes present in a catalog listing supplied on stdin. ONE definition on
# purpose: `not_live_providers` (a status display) and the launch-time model admission below must
# agree byte for byte on what "the running gateway serves this provider" means, and two spellings
# of that sed would be free to drift into disagreeing about a launch.
catalog_provider_prefixes() {
  sed -n 's|^\([^/][^/]*\)/.*|\1|p' | sort -u
}

# Names with at least one model served under `<name>/`. The default provider serves bare IDs,
# so it is reported live whenever the catalog answers at all -- its own liveness is already the
# health probe's subject and misreporting it as NOT-LIVE would be the false alarm this check
# exists to avoid.
live_provider_names() {
  local port="$1" catalog
  catalog="$(live_catalog_model_ids "$port")" || return 1
  [ -n "$catalog" ] || return 1
  catalog_provider_prefixes <<<"$catalog"
}

# The configured DEFAULT provider's name. Exit 1 when it cannot be read at all, and that status is
# load-bearing rather than cosmetic: the default provider serves BARE model ids, so it never appears
# in the `<name>/` set live_provider_names builds, and a silently-empty default name therefore
# reports the default provider itself as NOT-LIVE -- the exact false alarm this comparison exists to
# avoid. An empty STRING with exit 0 is a different fact (no default is configured) and is kept.
# This is why the read is not wrapped in `|| true` any more: swallowing an unavailable jq or a failed
# provider read here degraded the comparison to a WRONG verdict instead of to `unknown`.
default_provider_name() {
  jq_available || return 1
  ocx provider list --json 2>/dev/null \
    | jq -r '(.configured // []) | map(select(.isDefault == true)) | (first | .name) // ""' 2>/dev/null
}

# Prints one `<name>` per configured-but-not-served provider. Exit 1 means the comparison could
# not be made (missing tool, gateway down, unparseable payload) -- deliberately distinct from
# exit 0 with no output, which means every configured provider is live.
not_live_providers() {
  local port="$1" configured live default_name name
  configured="$(configured_provider_names)" || return 1
  [ -n "$configured" ] || return 1
  live="$(live_provider_names "$port")" || return 1
  default_name="$(default_provider_name)" || return 1
  while IFS= read -r name; do
    [ -n "$name" ] || continue
    [ "$name" = "$default_name" ] && continue
    printf '%s\n' "$live" | grep -qxF "$name" || printf '%s\n' "$name"
  done <<<"$configured"
}

# --- selected-model admission ---------------------------------------------------------------
#
# The router's fail-open, refused HERE rather than reported after the fact. Read in the installed
# opencodex 2.28.0 source, not inferred: `routeModelInternal` (src/router.ts:541) takes the
# provider prefix of a `<provider>/<model>` id at src/router.ts:626, tests it against the
# CONFIGURED providers at :630, and when that test fails it DISCARDS the negative result -- the
# `if` has no `else`, and `provName` leaves scope at :650 without ever being compared to the
# provider that ends up selected. Control reaches :685, which returns
# `routeKind: "default-provider"` and passes the caller's string on VERBATIM, bogus prefix
# included. The credential precondition is local to the ALREADY-selected provider, so on a host
# whose default provider is credentialed the request is attempted and BILLED against the wrong
# upstream while the attribution log records the wrong provider. Three such rows sit in this
# host's own gateway store from the last seven days (`mise run usage:report`, misroutes line), so
# this is a live alarm rather than a hypothetical. Upstream owns the router; this wrapper owns
# whether OUR launch hands it an id it will silently misroute.
# docs/research/2026-08-24-gateway-default-provider-misroute.md carries the upstream-facing report.
#
# The rule is deliberately NARROW, because a broad one refuses legitimate routes:
#   * NO SLASH is never refused. Those ids take the router's other, legitimate paths -- the bare
#     OpenAI family (src/router.ts:652-658), the configured defaultModel (:660-665), the vendor
#     patterns that serve `claude-*` (:667-668), and the static models list (:670-677). A live
#     catalog need carry no bare `claude*` row at all (this host's does not), so refusing bare ids
#     would refuse the native Anthropic passthrough this whole route exists to preserve.
#   * An EXACT catalog id is never refused whatever its shape. That covers an alias -- the catalog
#     emits `m.alias` in PLACE of the namespaced form -- and the two-slash routed ids `/v1/models`
#     really serves, such as `openrouter/~anthropic/claude-fable-latest`.
#   * A LIVE prefix is never refused: a provider serving at least one `<name>/` row is live, so a
#     model of its own that this listing does not enumerate still routes to it.
#   * The DEFAULT provider's own name is never refused. It serves BARE ids, so it is absent from the
#     `<name>/` prefix set by construction, while the router matches it by name and routes there
#     explicitly -- `openai/gpt-5.5` on a host whose default is `openai` is a working selection, and
#     an earlier draft of this check refused it. Verified against this host's live catalog.
#   * `policy/<id>` is never refused. Routing profiles resolve at src/router.ts:555, BEFORE the
#     prefix branch, and an unknown profile ALREADY fails closed upstream with
#     NoEligiblePolicyCandidateError -- so this check has nothing to add and no business refusing.
#
# LIMIT, stated rather than hidden: a configured COMBO alias carrying a slash (one optional
# segment, src/combos/types.ts:27) also resolves before the prefix branch, and this check does not
# read the combo table, so such an alias WOULD be refused here. No combo is configured on this
# host and none appears anywhere in this repository; where one is, pass the resolved id instead.

# Classifies ONE caller-supplied model id against the running gateway's live catalog. Prints
# `<verdict><tab><detail>` and exits 0 when the id must NOT be launched; exits 1 when it is
# admissible. `unreadable` is a refusal and not a pass, for the same reason an unverifiable
# `--settings` value is: a check that cannot run has established nothing, and guessing here is
# what puts the request on the wrong account.
unlaunchable_model_id() {
  local requested="$1" port="$2" catalog prefix configured
  case "$requested" in
    # A LEADING slash is not this branch upstream either: the router guards on `slash > 0`, so an
    # id whose first character is `/` never reaches the prefix test and this check claims no
    # jurisdiction over it. Keeping the shapes identical is what stops the two from disagreeing.
    /*) return 1 ;;
    */*) ;;
    *) return 1 ;;
  esac
  prefix="${requested%%/*}"
  [ "$prefix" = policy ] && return 1
  command -v curl >/dev/null 2>&1 || { printf 'unreadable\tno curl is available to read it'; return 0; }
  jq_available || { printf 'unreadable\tthe admitted jq route could not be run'; return 0; }
  catalog="$(live_catalog_model_ids "$port")" \
    || { printf 'unreadable\tthe gateway at 127.0.0.1:%s did not serve it' "${port:-unknown}"; return 0; }
  [ -n "$catalog" ] \
    || { printf 'unreadable\tthe gateway at 127.0.0.1:%s served an empty catalog' "${port:-unknown}"; return 0; }
  # Here-strings rather than pipes into `grep -q`: under `set -o pipefail` a matching `grep -q`
  # can SIGPIPE the writer and make a SUCCESSFUL search report failure.
  grep -qxF "$requested" <<<"$catalog" && return 1
  grep -qxF "$prefix" <<<"$(catalog_provider_prefixes <<<"$catalog")" && return 1
  # The DEFAULT provider serves BARE ids, so it never appears as a `<name>/` prefix in the catalog
  # -- but the router still matches it by name at src/router.ts:630 and routes there EXPLICITLY,
  # never through the fallthrough this check exists to stop. Refusing `<default>/model` would refuse
  # a working selection, and it is the same false alarm `not_live_providers` already exempts the
  # default provider from. Its own residual comes along: this reads the CONFIG file, so a default
  # changed there but not yet loaded by the running gateway is admitted by a name the process does
  # not have. `owned_by` in the catalog is not a substitute -- it carries the upstream VENDOR
  # (a `muse` provider's rows report `meta`) and is hardcoded to `openai` for native rows.
  [ "$prefix" = "$(default_provider_name || true)" ] && return 1
  # Only reached on the refusal branch, so the happy path adds no `ocx` call. The distinction is
  # worth one read: configuration drift and a typo are the same misroute with different remedies.
  configured="$(configured_provider_names 2>/dev/null || true)"
  if grep -qxF "$prefix" <<<"$configured"; then
    printf 'not-live\t%s' "$prefix"
    return 0
  fi
  printf 'unknown\t%s' "$prefix"
}

# The FIRST `--model` value in the forwarded arguments, or exit 1 for none. Scanning stops at a
# literal `--` exactly as assert_forwarded_settings_are_effective does. That is not a hole for the
# wrapper's own separator: `strip_forwarding_separator` has already consumed a LEADING `--` before
# cmd_launch runs, so what this scans is Claude's own argument vector. A LATER `--` ends Claude's
# option parsing, past which `--model` is a positional argument rather than a model selection, so
# there is nothing there for this check to be right about.
forwarded_model_argument() {
  local -a arguments=("$@")
  local index=0 argument
  while [ "$index" -lt "${#arguments[@]}" ]; do
    argument="${arguments[$index]}"
    case "$argument" in
      --) return 1 ;;
      --model)
        index=$((index + 1))
        [ "$index" -lt "${#arguments[@]}" ] || return 1
        [ -n "${arguments[$index]}" ] || return 1
        printf '%s' "${arguments[$index]}"
        return 0
        ;;
      --model=*)
        [ -n "${argument#--model=}" ] || return 1
        printf '%s' "${argument#--model=}"
        return 0
        ;;
    esac
    index=$((index + 1))
  done
  return 1
}

# Separate from `refuse` because the epilogue there is about a setting that outranks the gateway's
# base URL, which is a different hazard with a different remedy. Same exit 3: a boundary declined
# the operation before any effect.
refuse_misroute() {
  printf '\nREFUSED: %s\n' "$1" >&2
  cat >&2 <<'EOF'
The gateway does not fail closed on this. Its router takes the provider prefix, finds no provider
of that name, discards that result, and forwards your model string VERBATIM to whichever provider
is DEFAULT -- tagged `routeKind: "default-provider"`. The credential check that follows belongs to
that default provider, not to the one you named, so where the default is credentialed the request
is answered and BILLED against the wrong account while the attribution log records the wrong
provider. Launching would make that silent; this refusal makes it loud.

Pick an id the running gateway actually serves:
  ccodex models            the live catalog, which is what a launched session can pick from
  ccodex status            configured providers vs the ones the running gateway serves

A bare id is never refused here: native `claude-*` ids pass through to Anthropic on your own
subscription, and this check governs only a namespaced `<provider>/<model>` selection.
EOF
  exit 3
}

# Runs AFTER ensure_gateway_up, and that ordering is a deliberate trade rather than an oversight.
# The checks in assert_gateway_route_is_effective run BEFORE any gateway is started so a refused
# launch leaves no proxy the operator did not ask for. This check cannot: its whole subject is what
# the RUNNING gateway serves, and there is no catalog to read until one is up. So a launch refused
# here may leave a healthy gateway behind -- `launch` was going to ensure one anyway, and `ccodex
# status` reports it. What it does not leave behind is a misrouted, billed request.
assert_selected_model_is_served() {
  local port="$1"
  shift
  local requested result verdict detail
  requested="$(forwarded_model_argument "$@")" || return 0
  result="$(unlaunchable_model_id "$requested" "$port")" || return 0
  verdict="${result%%$'\t'*}"
  detail="${result#*$'\t'}"
  case "$verdict" in
    unreadable)
      refuse_misroute "--model $requested names the provider \`${requested%%/*}\`, and the running gateway's live catalog could not be read to check it ($detail); an unverifiable selection stops the launch rather than passing as served" ;;
    not-live)
      refuse_misroute "--model $requested names the provider \`$detail\`, which is CONFIGURED but is not in the running gateway's catalog, so the gateway does not serve it -- run \`ocx sync\` and then \`ccodex restart\` to publish it, each as its own authorized step, and confirm with \`ccodex status\`" ;;
    unknown)
      refuse_misroute "--model $requested names the provider \`$detail\`, and the running gateway serves no provider of that name" ;;
  esac
}

# Printed after every admitted provider mutation. The sequence is NOT run for the operator: a
# sync can rewrite shared ~/.codex state and a restart interrupts in-flight turns, so each is its
# own authorized operation rather than a side effect of a configuration edit.
#
# By opencodex 2.28.0 (absent in 2.11.1) the write half is CONDITIONAL: with the Codex integration
# off, or with an external `model_provider` owning `config.toml`, the sync reports a
# `CodexSyncResult` status of `catalog-only` and leaves config.toml, the journal, and history
# untouched (it may still refresh the catalog and models-cache files under ~/.codex), and a
# `validateOnly` injection preflight fails a
# bad config before any partial rewrite. Which branch a host takes is not knowable from here
# without running the sync, so the notice keeps naming the ~/.codex exposure: the narrower branch
# lowers the blast radius, never the authorization.
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

Neither step is run for you: a \`sync\` can rewrite shared ~/.codex config and a restart
interrupts in-flight turns, so both are separately authorized operations. By opencodex
2.28.0 (absent in 2.11.1) the sync is catalog-only when the Codex integration is off or an
external model_provider owns config.toml -- config.toml, the journal, and history stay
untouched, though the catalog and models-cache files under ~/.codex may still refresh; a sync that WOULD rewrite ~/.codex
still needs its own approval.

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
# What remains guards five SILENT failures that would otherwise be indistinguishable from
# success, which matters more now that this is the default rather than a named escape hatch:
#
#   1. An ENABLED provider-routing switch, exported or in a settings.json `env` block,
#      OUTRANKS ANTHROPIC_BASE_URL. Under CLAUDE_CODE_USE_BEDROCK the client consults
#      ANTHROPIC_BEDROCK_BASE_URL instead, so the gateway is bypassed entirely and the turn
#      bills the cloud account while this wrapper prints a gateway banner. Measured on a real
#      host on 2026-08-10: the request never reached a local capture listener and was still
#      answered. This is not a theoretical hazard.
#   2. ANTHROPIC_BASE_URL in a settings `env` block REPLACES the base URL this launch sets, so a
#      foreign address there silently becomes the destination. Measured on 2026-08-11 with two
#      loopback listeners: the settings value won every request. See
#      settings_document_bypassing_key_name, which also records why the earlier "the child env
#      outranks it" reading was backwards.
#   3. An EXPORTED foreign ANTHROPIC_BASE_URL SURVIVES into the child and wins. This was an open
#      question until 2026-08-11; it is now MEASURED, twice, and the measurement is recorded at
#      exported_base_url_is_foreign because it is the whole justification for that refusal.
#   4. An `sk-ant-api*` Console key satisfies opencodex's bare `sk-ant-` passthrough gate
#      (hasAnthropicNativeCredential in server/claude-messages.ts), so it takes the SAME
#      native branch and bills API credits while looking like subscription traffic. The
#      prefix is the only thing separating the two.
#   5. A cloud-provider-shaped id in one of the six MODEL SLOTS -- `ANTHROPIC_MODEL`, an
#      `ANTHROPIC_DEFAULT_*_MODEL` tier slot, or `ANTHROPIC_SMALL_FAST_MODEL` -- re-points a
#      whole model family without touching any switch above: EXECUTED 2026-08-20 with
#      CLAUDE_CODE_USE_BEDROCK unset and ANTHROPIC_DEFAULT_SONNET_MODEL exporting
#      `global.anthropic.claude-sonnet-5[1m]`, `launch` proceeded and the session 400d at the Codex
#      upstream because the gateway does not read that id as native passthrough and fell through to
#      the DEFAULT provider. See $model_slot_overrides.
#
# Names, prefixes, and base-URL or model-id SHAPES only: no credential value is read, printed,
# copied, or persisted, and a base URL is never echoed because it can carry userinfo credentials.
# A model id carries no secret, so a refused one is named rather than withheld.

# ONE list per class, shared by the exported-environment check and the settings-document check
# below. The two lists drifted apart once already -- the settings side was missing entries the
# env side had, so the SAME variable refused a launch from the shell and passed silently from the
# file -- and feeding both channels from one array is what stops that recurring. Every name here
# is `[A-Z_]` by construction, which is why json_name_array can quote them without escaping.
#
# BOOLEAN switches are read with TRUTHINESS: "", "0" and "false" mean not enabled. Measured
# against Claude Code 2.1.227 on 2026-08-11: with CLAUDE_CODE_USE_BEDROCK=0 the traffic still went
# to ANTHROPIC_BASE_URL, so refusing on mere presence stopped a launch that works -- and `=0` is
# exactly how an operator disables a switch inherited from a profile or a wrapper.
routing_boolean_switches=(
  CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
  CLAUDE_CODE_USE_ANTHROPIC_AWS CLAUDE_CODE_USE_ANTHROPIC_GOOGLE_CLOUD
  CLAUDE_CODE_USE_MANTLE
)
# ENDPOINT and CREDENTIAL slots are read by VALUE, not as booleans: any non-empty value is
# meaningful, an empty one is not, and `=0` there is a nonsense endpoint rather than "off". So
# truthiness would be the wrong rule for these, and presence alone the wrong rule for the ones
# above. Until 2026-08-11 the two classes shared one rule and the two channels disagreed about
# which -- the exported side tested non-emptiness, the settings side tested key presence -- so
# `CLAUDE_CODE_USE_BEDROCK=0` refused a launch that demonstrably works, and refused it differently
# depending on where the operator had written it.
routing_endpoint_slots=(
  AWS_BEARER_TOKEN_BEDROCK ANTHROPIC_BEDROCK_BASE_URL ANTHROPIC_VERTEX_BASE_URL
  ANTHROPIC_AWS_BASE_URL ANTHROPIC_GOOGLE_CLOUD_BASE_URL ANTHROPIC_BEDROCK_MANTLE_BASE_URL
)
# The AWS / Google-Cloud entries were absent until 2026-08-11 and are a MEASURED bypass, not a
# speculative one: with CLAUDE_CODE_USE_ANTHROPIC_AWS=1 the client demanded AWS_REGION and nothing
# reached a local capture listener -- it had left the ANTHROPIC_BASE_URL path before the gateway
# was ever consulted. On a host that already exports AWS_REGION (common) that turn bills the cloud
# account under a gateway banner. All twelve names above appear in 2.1.227's own provider table.
#
# CLAUDE_CODE_USE_MANTLE was that list's last unmeasured neighbour and is now IN it, on evidence
# rather than on its position in the table. Measured on 2026-08-11 against 2.1.227, base URL
# pointed at a loopback capture listener throughout: with the switch alone the client never
# contacted that listener at all and hung resolving AWS credentials; with AWS_REGION and a dummy
# bearer it reported "Enable Opus 5 in Amazon Bedrock (Mantle)" and then `401 Invalid bearer
# token` from AWS; with ANTHROPIC_BEDROCK_MANTLE_BASE_URL pointed at a SECOND listener every
# POST /v1/messages went there. So the switch ALONE defeats this route and needs no companion
# variable to do it -- the client's own provider resolver returns "mantle" for a truthy
# CLAUDE_CODE_USE_MANTLE independently of CLAUDE_CODE_USE_BEDROCK, and only "firstParty" consults
# ANTHROPIC_BASE_URL. A companion variable is what makes mantle SUCCEED, not what makes it bypass.
#
# One neighbour in that table stays deliberately excluded: CLAUDE_CODE_USE_GATEWAY was measured as
# STILL honouring ANTHROPIC_BASE_URL (the client's own message says its on-ramp REQUIRES that
# variable plus ANTHROPIC_AUTH_TOKEN), so it does not defeat this route and refusing it would be a
# false positive.

# A THIRD CLASS, and neither a boolean nor an endpoint: these six carry a MODEL ID, and they
# choose which id serves a whole model family for the session.
#
# EXECUTED 2026-08-20, which is why this is a refusal rather than a note. With
# CLAUDE_CODE_USE_BEDROCK unset -- so every switch above read as off and every check above passed --
# and ANTHROPIC_DEFAULT_SONNET_MODEL and its siblings still exporting Bedrock-shaped ids
# (`global.anthropic.claude-sonnet-5[1m]` and kin), `launch` PROCEEDED and the session 400d at the
# Codex upstream: the gateway does not recognize a `global.anthropic.*` id as native Anthropic
# passthrough, so it fell through to the DEFAULT provider. The operator asked for Sonnet on their
# subscription and got whichever provider is default, under a gateway banner.
#
# REFUSE, NOT WARN, and the refusal text says why: one of these variables changes which upstream
# serves those slots as surely as a routing switch does. A warning on the channel that silently
# re-points a whole model family is the fail-open shape every check in this section exists to
# close, and the failure it produces -- an upstream 400, or worse a quietly substituted model --
# names none of these variables.
#
# A MODEL ID IS NOT A CREDENTIAL. Unlike a base URL, a token, or a settings path, these refusals
# may NAME the value: hiding it would leave the operator guessing which of six slots to fix, and
# there is nothing secret in `us.anthropic.claude-opus-4-5-v1:0`.
#
# ANTHROPIC_MODEL and ANTHROPIC_DEFAULT_FABLE_MODEL joined the four above once MEASURED, not on a
# guess: `skills/model-tier-rightsizing/references/workflow-prompt-budget.md` records
# `effectiveModelEnv()` (`src/claude/context-windows.ts`) injecting `ANTHROPIC_MODEL` and
# `ANTHROPIC_DEFAULT_OPUS/SONNET/FABLE/HAIKU_MODEL` as the SAME tier-slot set -- so both are the
# identical hazard class as the original four and a cloud-shaped id in either re-points that
# family exactly as it would in ANTHROPIC_DEFAULT_SONNET_MODEL.
model_slot_overrides=(
  ANTHROPIC_DEFAULT_SONNET_MODEL ANTHROPIC_DEFAULT_OPUS_MODEL ANTHROPIC_DEFAULT_HAIKU_MODEL
  ANTHROPIC_DEFAULT_FABLE_MODEL ANTHROPIC_SMALL_FAST_MODEL ANTHROPIC_MODEL
)
# ONE pattern for BOTH channels, on the same rule as $loopback_base_url_pattern above: bash `=~`
# here and jq's `test()` in the settings program must not be able to disagree about which id is
# cloud-provider-shaped. Everything in it is POSIX-ERE / Oniguruma common ground -- anchors,
# alternation, escaped dots, a negated class, a bounded repeat -- so the two engines classify the
# same fixtures identically.
#
# GROUNDED IN THE IDS THE REFUSALS ALREADY KNOW rather than in a guess about model naming: the
# region-prefixed Bedrock inference profiles (`global.`/`us.`/`eu.`/`apac.`/GovCloud on
# `anthropic.`), the bare Bedrock publisher form (`anthropic.claude-*`), and the two Vertex
# spellings (a `publishers/anthropic/` or `projects/<p>/locations/...` path, and the `@<date>`
# pinned-version suffix). A plain alias -- `claude-sonnet-5`, `claude-haiku-4-5` -- matches none of
# them, and neither does a gateway id such as `muse/muse-spark-1.2`; both stay fine, because a
# routed id in the small-fast slot is a legitimate use of this route.
#
# TRIMMED before either engine tests the shape. MEASURED: with a single leading space,
# `ANTHROPIC_DEFAULT_SONNET_MODEL=' global.anthropic.claude-sonnet-5[1m]'` launched clean, because
# every `^`-anchored alternative in the pattern above anchors immediately and a leading space
# defeats it while the id is still, in every way that matters to the upstream, the same
# cloud-provider id. Leading AND trailing whitespace are stripped -- trailing matters too, because
# the last alternative anchors on `$` -- and ONLY whitespace is stripped: internal spelling is
# untouched, so a genuinely malformed id (one with embedded whitespace) still fails to match and
# is treated as an ordinary, non-cloud-shaped value rather than papered over.
cloud_provider_model_id_pattern='^(global|us|eu|apac|us-gov-west-1|us-gov-east-1)\.anthropic\.|^anthropic\.claude|^publishers/anthropic/|^projects/[^/]+/locations/|@[0-9]{8}$'

# ONE trim for BOTH engines, on the same rule as $cloud_provider_model_id_pattern above: bash
# stripping leading/trailing whitespace one way while jq's `sub()` strips it another would let the
# two channels disagree about the same exported-vs-settings value. Bash's own parameter-expansion
# idiom (POSIX `[:space:]`, no subprocess) on this side; `sub("^\\s+";"")`/`sub("\\s+$";"")` on the
# jq side below -- both remove ONLY leading/trailing runs, never anything internal.
trim_whitespace() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

# Truthiness for the boolean switches only. Case- and whitespace-insensitive so ` False ` is not
# read as enabled. Non-boolean slots never reach this function.
switch_is_enabled() {
  local value
  value="$(LC_ALL=C tr '[:upper:]' '[:lower:]' <<<"${1:-}" | tr -d '[:space:]')"
  case "$value" in ""|0|false) return 1 ;; esac
  return 0
}

# A JSON array of variable NAMES for the jq program below. Safe without escaping precisely because
# every element is one of the `[A-Z_]` literals above -- it is not a general-purpose encoder.
json_name_array() {
  local out="" name
  for name in "$@"; do out="$out,\"$name\""; done
  printf '[%s]' "${out#,}"
}

# ONE loopback matcher for BOTH base-URL channels. The exported check and the settings-document
# check must not be able to disagree about which address is this host's own gateway, so the pattern
# is defined once and consumed twice: by bash `=~` below and by jq's `test()` in the settings
# program. Verified to classify the same ten fixtures identically in both engines, which is the
# property that matters -- POSIX ERE and Oniguruma agree on this subset (escaped dots, an escaped
# bracket pair, alternation, an optional port, an anchored tail), and nothing in it is
# engine-specific. `http://` only: an https URL to a plaintext local hop is not the route this
# launch prepares, and the optional `([^/@]*@)?` group is what stops `http://127.0.0.1@elsewhere`
# from reading as loopback.
loopback_base_url_pattern='^http://([^/@]*@)?(127\.0\.0\.1|localhost|\[::1\])(:[0-9]+)?(/|$)'

# True when the value names something OTHER than this host's loopback gateway. Empty is not foreign:
# it names no destination at all, so opencodex's own setDefault fills in the live gateway.
base_url_is_foreign() {
  local value
  value="$(LC_ALL=C tr '[:upper:]' '[:lower:]' <<<"${1:-}")"
  [ -n "$value" ] || return 1
  [[ "$value" =~ $loopback_base_url_pattern ]] && return 1
  return 0
}

# MEASURED 2026-08-11 against Claude Code 2.1.227 and the pinned opencodex 2.11.1, because until
# then this was recorded here as an unclosed gap rather than a refusal. Two loopback capture
# listeners, each replying 400 and forwarding nothing:
#
#   * `ANTHROPIC_BASE_URL=http://127.0.0.2:59991` exported, then the REAL `ocx claude` path with a
#     healthy gateway on 127.0.0.1:10100 and a dummy `sk-ant-oat01-` sentinel: HEAD /api/hello,
#     GET /v1/models and POST /v1/messages ALL arrived at :59991. The gateway saw nothing, and
#     `launch` would have printed `routed at : http://127.0.0.1:10100` over it. So the exported
#     channel is a live bypass, exactly like the settings one, and it carries the operator's own
#     login to the foreign address rather than merely failing.
#   * The same run with a stub `claude` confirms WHY: the child environment opencodex built held
#     ANTHROPIC_BASE_URL=http://127.0.0.2:59991 and no gateway value at all. `bin/ocx.mjs` records
#     which Anthropic slots the shell really exported and pairs them with an argv proof, so
#     buildClaudeEnv's provenance strip KEEPS a genuine export; its own `setDefault` then declines
#     to overwrite it ("user wins"), and its stale-value rewrite fires only for a loopback host
#     with a different port.
#   * Control, same harness: with `ANTHROPIC_BASE_URL=http://127.0.0.1:59992` exported -- loopback,
#     different port -- opencodex printed `⚠ Replacing stale opencodex ANTHROPIC_BASE_URL
#     http://127.0.0.1:59992 with http://127.0.0.1:10100`, that listener saw nothing, and the turn
#     reached Anthropic through the gateway (`401 OAuth access token is invalid` for the dummy
#     sentinel). That is why accepting loopback SHAPES here is not a hole: opencodex itself
#     redirects a loopback value to the live gateway.
#
# Residual, stated rather than hidden: a loopback URL with NO port, or with the gateway's own port,
# is not rewritten and is accepted here. That is a wrong local hop, not a cloud account, and the
# port is unknowable before ensure_gateway_up starts something -- the same ordering constraint the
# settings check documents.
exported_base_url_is_foreign() {
  base_url_is_foreign "${ANTHROPIC_BASE_URL:-}"
}

# Claude Code resolves a cloud-provider credential ABOVE its own OAuth, and under Bedrock, Vertex,
# Foundry, Mantle or either Anthropic-on-cloud switch it stops consulting ANTHROPIC_BASE_URL at all.
# Either way the gateway is not in the path, so launching would report a route that does not exist.
gateway_bypassing_env_name() {
  local name
  for name in "${routing_boolean_switches[@]}"; do
    if switch_is_enabled "${!name:-}"; then printf '%s' "$name"; return 0; fi
  done
  for name in "${routing_endpoint_slots[@]}"; do
    if [ -n "${!name:-}" ]; then printf '%s' "$name"; return 0; fi
  done
  # Value-aware, and therefore NOT a member of either array above: any non-empty value is
  # meaningful for an endpoint slot, but a loopback ANTHROPIC_BASE_URL is the route working as
  # intended. Reported last so a cloud switch -- which defeats the route no matter what this
  # variable says -- still names itself first.
  if exported_base_url_is_foreign; then printf 'ANTHROPIC_BASE_URL'; return 0; fi
  return 1
}

# The exported half of the model-slot check, as `<name><tab><value>` for the first slot carrying a
# cloud-provider-shaped id. The VALUE is returned deliberately -- the refusal prints it, because a
# model id is not a credential and naming it is what makes the message actionable. Reported by this
# function rather than by gateway_bypassing_env_name because the two say different things: a
# routing switch means the gateway is not in the path at all, while this means the gateway IS in
# the path and will serve those slots from the wrong upstream.
cloud_shaped_model_slot_env() {
  local name value trimmed
  for name in "${model_slot_overrides[@]}"; do
    value="${!name:-}"
    [ -n "$value" ] || continue
    # $value is what the refusal PRINTS (verbatim, including any stray whitespace, because that is
    # what the operator actually exported); $trimmed is what the SHAPE is tested against, so a
    # leading or trailing space cannot slip an otherwise cloud-shaped id past the anchored pattern.
    trimmed="$(trim_whitespace "$value")"
    [ -n "$trimmed" ] || continue
    if [[ "$(LC_ALL=C tr '[:upper:]' '[:lower:]' <<<"$trimmed")" =~ $cloud_provider_model_id_pattern ]]; then
      printf '%s\t%s' "$name" "$value"
      return 0
    fi
  done
  return 1
}

# ONE sentence for both channels, so the exported and settings refusals cannot drift into
# describing the same hazard differently. The caller supplies how the value was set.
model_slot_refusal_reason() {
  printf '%s' "that variable chooses which id serves a whole model family, so it re-points that family's upstream as surely as a routing switch does: the gateway does not recognize a cloud-provider id as native Anthropic passthrough, so those turns fall through to the DEFAULT provider and are answered -- or 400d -- under a gateway banner. Use a plain claude-* id, or drop the variable and pick the model per session with \`--model\`"
}

# The same switches in a settings document, plus two hazards that exist only there. Shell env is
# checked separately above because a settings document is the channel an operator forgets: it is
# read on every launch and survives a clean shell.
#
# THREE DOCUMENTS, not one. Until 2026-08-11 only `$HOME/.claude/settings.json` was read here, while
# `status` printed "nothing in this shell or the global settings document outranks the gateway" --
# true of the document it checked and false as the reassurance it reads like. MEASURED on 2026-08-11
# against 2.1.227, with one loopback listener named in a document and a second exported, per
# document, one launch each:
#
#   ./.claude/settings.json         env.ANTHROPIC_BASE_URL WINS  (POST /v1/messages -> document)
#   ./.claude/settings.local.json   env.ANTHROPIC_BASE_URL WINS  (POST /v1/messages -> document)
#   <global>/settings.json          env.ANTHROPIC_BASE_URL WINS  (every request -> document)
#   <global>/settings.local.json    NOT READ for env             (every request -> exported value)
#
# So the local sibling matters at project scope and not at global scope, which is why the list below
# is asymmetric rather than a tidy pair per directory. In the two project cases the very first
# HEAD /api/hello still went to the exported value and only the POSTs moved -- an early probe
# reaching the gateway is NOT evidence that the session is routed through it.
#
# PROJECT SCOPE IS THE LAUNCH DIRECTORY, exactly. Measured in the same session: a
# `.claude/settings.json` in a PARENT of the launch directory had no effect, with or without a git
# repository at that parent, so this check does not walk upward and must not pretend to.
#
# A FOURTH channel exists and is deliberately NOT claimed: enterprise managed policy
# (`/etc/claude-code/managed-settings.json` plus a `managed-settings.d` drop-in directory on
# Linux, the platform equivalents elsewhere, and on WSL a Windows registry policy chain that no
# POSIX path can express). The one form of it this host could write --
# `CLAUDE_CODE_MANAGED_SETTINGS_PATH` pointing at a document whose `env` carried a routing switch --
# was measured as having NO effect on routing, while the identical switch in a project document did
# divert the traffic. An unverified refusal on an administrator-owned file would hard-stop working
# launches for a guess, so the honest move is the one taken: check the three documents above, and
# have `status` and `launch --help` NAME them instead of implying the whole surface.
#
# Credential slots are matched on VALUE PREFIX, not on name. An `sk-ant-oat*` OAuth token is the
# credential this route exists to carry, so refusing it because of WHERE it is stored would reject
# a working own-login setup that the identical token, exported instead, is allowed to use. Only the
# `sk-ant-api*` Console shape is refused, matching console_key_env_name below. The prefix is read;
# the remainder of the value never is, and neither is ever printed.
#
# ANTHROPIC_BASE_URL IS IN THIS LIST, value-aware. An earlier revision dropped it, claiming Claude
# Code resolves shell environment above settings `env` so a value here is overridden rather than
# obeyed. THAT IS BACKWARDS, and it was a coverage regression justified by a false comment.
# MEASURED on 2026-08-11 against Claude Code 2.1.227 with two loopback listeners -- :59998
# exported and :59999 in settings `env` -- all six POST /v1/messages went to :59999. Settings env
# WINS over the child process environment unless CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST is set, and
# opencodex sets that flag only when it owns an auth token (cli/claude.ts:157-159, guarded by
# `if (env.ANTHROPIC_AUTH_TOKEN)`); its own comment at :68 says so outright -- "on a subscription
# launch Claude Code's settings.env merge can still replace ANTHROPIC_BASE_URL after we return".
# This route injects no token, so the flag is absent and a value here is obeyed.
#
# It is matched by SHAPE rather than against the live port, and that is a deliberate ordering
# choice: any `http://` URL whose host is 127.0.0.1 / localhost / [::1] is benign, anything else
# refuses. The exact port is not known until ensure_gateway_up + gateway_health_json have run, and
# those START the gateway -- resolving it first would leave a proxy running behind a refused launch,
# which is precisely what checking before ensure exists to prevent. Reading `ocx config get port`
# instead would be read-only but can disagree with the port the gateway actually binds, turning a
# config-vs-runtime mismatch into a hard refusal. Residual, stated rather than hidden: a loopback
# URL naming a DIFFERENT local port is accepted here. That is a wrong local hop, not a cloud
# account, and no check in this file can tell the two ports apart without starting something. The
# shape itself comes from $loopback_base_url_pattern, the SAME pattern the exported check uses, so
# the two channels cannot drift into disagreeing about what loopback means.
#
# Three outcomes, not two. "Absent" and "unreadable" are NOT the same as "clean": this is the
# channel an operator forgets, so a check that cannot run must say so rather than report nothing
# found. Prints the offending key name, or the literal `unreadable:<reason>`; returns 1 only when
# the document was genuinely read and held nothing.
#
# ONE PATH PER CALL, and one jq program for every path. The document list lives in
# claude_settings_documents below and is walked by bypassing_settings_document_and_key, so adding a
# document is a list edit rather than a second copy of this program drifting away from the first.
# Read exactly one JSON settings object from stdin and emit one bounded classification: `clean` or
# the first bypassing key. The document bytes never enter a shell variable. `-s` is intentional:
# ordinary jq accepts an empty stream and concatenated JSON values, but neither is one settings
# object. A nonzero status therefore means malformed, empty, multiple, or non-object input.
settings_bypass_classification() {
  jq -ers \
    --arg loopback "$loopback_base_url_pattern" \
    --arg cloudmodel "$cloud_provider_model_id_pattern" \
    --argjson booleans "$(json_name_array "${routing_boolean_switches[@]}")" \
    --argjson slots "$(json_name_array "${routing_endpoint_slots[@]}")" \
    --argjson models "$(json_name_array "${model_slot_overrides[@]}")" '
    if length != 1 or (.[0] | type) != "object"
    then error("not exactly one settings object")
    else .[0]
    end
    | (.env // {}) as $env
    # ONE reader for every slot, and NOT `$env[.] // ""`. The jq `//` operator is false-OR-null,
    # not null-coalescing, so a JSON literal `false` read as ABSENT: `{"env":{"ANTHROPIC_BASE_URL":
    # false}}` reported CLEAN while the identical `"https://evil.example"` refused. That mattered
    # because Claude Code does not drop or reject a non-string here -- MEASURED on 2026-08-11
    # against 2.1.227, whose settings-env filter chain passes values through untouched and then
    # `Object.assign(process.env, ...)` STRINGIFIES them, so `false` arrives in the session and in
    # every child as the string "false". A probe with a blocking UserPromptSubmit hook dumped
    # `AWS_BEARER_TOKEN_BEDROCK=false` and `ANTHROPIC_BEDROCK_BASE_URL=false` from the child
    # environment: SET and non-empty, which is exactly the condition an endpoint slot refuses on.
    # Only `null` is absent, so only `null` becomes "". `tostring` is kept for every present value,
    # which is what keeps a number or boolean comparable against the string tests below.
    | def slot($name): if $env[$name] == null then "" else ($env[$name] | tostring) end;
      ($booleans | map(select(
        (slot(.) | ascii_downcase | gsub("\\s"; "")) as $value
        | $value != "" and $value != "0" and $value != "false"))) as $switches
    | ($slots | map(select(slot(.) != ""))) as $endpoints
    | [ "ANTHROPIC_BASE_URL"
        | select(slot(.) != "")
        | select((slot(.) | ascii_downcase) | test($loopback) | not) ] as $base
    | [ "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"
        | select(slot(.) | startswith("sk-ant-api")) ] as $console
    # The model-slot class, read by SHAPE through the same pattern the exported check uses. Only
    # the NAME crosses back, because this program deliberately never puts document bytes into a
    # shell variable: the settings refusal names the variable and the shape family rather than
    # quoting the value, which is also why the exported channel -- the one that does hold the
    # value -- is the channel that prints it.
    #
    # TRIMMED first, on the same rule trim_whitespace applies to the exported channel: a leading or
    # trailing space in the value a settings document carries must not be able to slip the
    # ^/$-anchored pattern any more than the same space in the shell can. Only leading/trailing
    # whitespace is removed; internal spelling still reaches test($cloudmodel) unmodified.
    | ($models | map(select(
        slot(.) | sub("^\\s+"; "") | sub("\\s+$"; "") | ascii_downcase | test($cloudmodel)
      ))) as $model_slots
    | (if (.apiKeyHelper // null) != null then ["apiKeyHelper"] else [] end) as $helper
    | ($switches + $endpoints + $base + $model_slots + $console + $helper) | first // "clean"
  '
}

settings_document_bypassing_key_name() {
  local settings="$1"
  # A genuinely absent document carries no key. That is a real clean state, not a gap. `-e` follows
  # the symlink, so a DANGLING one counts as absent -- deliberately matching Claude Code, which
  # reads this path and treats ENOENT as no settings at all; hard-stopping a working launch because
  # a dotfile symlink's target moved would refuse a client state that carries no key to begin with.
  [ -e "$settings" ] || return 1
  if [ ! -f "$settings" ] || [ ! -r "$settings" ]; then
    printf 'unreadable:not a readable regular file'; return 0
  fi
  # FAIL CLOSED: an existing document this host cannot classify is `unreadable:`, never `clean`.
  # `launch` turns that into a refusal and `status` prints UNKNOWN, which is the whole point of the
  # three-outcome contract above -- a document that carries a routing switch must not become
  # invisible because the tool that reads it is missing.
  if ! jq_available; then
    printf 'unreadable:the admitted jq route could not be run, so this document cannot be inspected'; return 0
  fi
  local found="" status=0
  found="$(settings_bypass_classification < "$settings" 2>/dev/null)" || status=$?
  if [ "$status" -ne 0 ]; then
    printf 'unreadable:the document could not be parsed as a settings object'; return 0
  fi
  [ "$found" = clean ] && return 1
  printf '%s' "$found"
}

# EXACTLY the documents Claude Code was measured to read for `env`, in that order, and nothing this
# check has not verified. The two project entries are relative to the LAUNCH DIRECTORY because that
# is the directory Claude Code resolves them against -- and because this list is what `status` and
# `launch --help` print, an entry added here without a measurement would become a claim.
#
# DEDUPLICATED, because launching from your home directory makes the project entry the global one:
# `$PWD/.claude/settings.json` and `$HOME/.claude/settings.json` are then the same path, and a list
# that printed it twice would read as two independent documents having been checked.
#
# THE DEDUPE KEY IS THE PHYSICAL SPELLING, not the string this function was handed. Comparing the
# strings collapsed only the case where `$HOME` and `$PWD` are spelled IDENTICALLY, which is the
# one case that needs no help. MEASURED on 2026-08-11 on plain Linux: with a trailing slash on
# `$HOME` and the launch directory set to home, `status` printed
# `checked: <home>//.claude/settings.json` AND `checked: <home>/.claude/settings.json` -- one file,
# listed as two documents verified. A `$HOME` reached through a symlink to the launch directory did
# the same. Real hosts produce both spellings without anyone trying: Fedora Silverblue/CoreOS puts
# `/home` behind a symlink to `/var/home`, a macOS home can sit under a symlinked volume, and a
# trailing slash survives any profile that writes `HOME="$something/"`. No key is read twice into a
# verdict -- the first-match refusal is unaffected -- but `status` overstated the surface it
# inspected, which this file treats as a defect rather than cosmetics.
#
# The two base directories are canonicalized ONCE and the documents are built from the result, so
# the fix does not depend on a document existing. That distinction is load-bearing: the absent case
# is the common one (a fresh machine has no `.claude` at all) and `status` names every `checked:`
# path whether or not the file is there, so a normalisation that resolved the DOCUMENT would fall
# back to the raw spelling exactly when the collision is invisible and list the file twice again.
# An unresolvable base directory keeps its raw spelling, which cannot collide with a resolved one:
# resolution fails only when the directory does not exist or cannot be searched, and such a
# directory is not the launch directory.
#
# RESIDUAL, stated rather than hidden: two genuinely different physical paths that reach one file
# through a document-level symlink, a hardlink, or a bind mount are still listed separately. Each
# is a distinct path Claude Code consults, and listing both overstates nothing.
canonical_directory() {
  local directory="$1" resolved=""
  # `CDPATH=''` so a set CDPATH cannot resolve somewhere else or make `cd` print a path, `-P` and
  # `pwd -P` so the answer is the physical directory, and `--` so a directory named like an option
  # is still a directory. The subshell is the command substitution's own, so nothing leaks.
  resolved="$(CDPATH='' cd -P -- "$directory" 2>/dev/null && pwd -P)" || resolved=""
  [ -n "$resolved" ] || resolved="$directory"
  printf '%s' "$resolved"
}

claude_settings_documents() {
  local document seen="" home_directory launch_directory
  home_directory="$(canonical_directory "$HOME")"
  launch_directory="$(canonical_directory "$PWD")"
  for document in "$home_directory/.claude/settings.json" \
                  "$launch_directory/.claude/settings.json" \
                  "$launch_directory/.claude/settings.local.json"; do
    case "$seen" in *"<$document>"*) continue ;; esac
    seen="$seen<$document>"
    printf '%s\n' "$document"
  done
}

# The first document carrying a bypass, as `<path><tab><key-or-unreadable:reason>`. A tab is safe as
# the separator because the right half is always either a `[A-Za-z]` key name from the lists above or
# this file's own `unreadable:` sentence. Returns 1 only when every document was genuinely read and
# none of them held anything.
bypassing_settings_document_and_key() {
  local document key
  while IFS= read -r document; do
    if key="$(settings_document_bypassing_key_name "$document")"; then
      printf '%s\t%s' "$document" "$key"
      return 0
    fi
  done < <(claude_settings_documents)
  return 1
}

# Classify one explicit `--settings <file-or-json>` value without echoing it. Claude documents JSON
# or a file path, so try a JSON object first; if that is not one cleanly parsed object, inspect an
# existing path. The classifier returns only the source kind, never the path or selected bytes. A
# missing path and invalid inline JSON are intentionally one generic `invalid` result because the CLI syntax cannot tell
# which one the caller meant without guessing from secret-bearing text.
settings_argument_bypassing_key_name() {
  local value="$1" found="" status=0
  if [ -n "$value" ]; then
    # FAIL CLOSED BY NAME, not through the `invalid` door. Without jq neither form can be
    # classified, and the old guard just skipped the inline attempt: an inline JSON object then fell
    # through to the file branch, missed there too, and was reported as "not a valid JSON object or
    # a readable settings file" -- a refusal (so never a bypass) that blamed the operator's value
    # for this host's missing tool. ADR-0020 decision 3 wants the blocked surface to produce NAMED
    # diagnostic evidence, so the reason is the tool. The `-e` file test below deliberately does not
    # run first: a value that is BOTH unparseable and not a path must not be probed as a filename.
    if ! jq_available; then
      printf 'value\tunreadable:the admitted jq route could not be run, so this value cannot be inspected'
      return 0
    fi
    found="$(printf '%s' "$value" | settings_bypass_classification 2>/dev/null)" || status=$?
    if [ "$status" -eq 0 ]; then
      [ "$found" = clean ] && return 1
      printf 'inline\t%s' "$found"
      return 0
    fi
  fi

  if [ -e "$value" ]; then
    if [ ! -f "$value" ] || [ ! -r "$value" ]; then
      printf 'file\tunreadable:not a readable regular file'
      return 0
    fi
    # Re-probed here rather than trusted from the check above, and that is not redundant: the file
    # was `-r` a moment ago and the tool answered a moment ago, and neither fact survives into the
    # open below. test_selected_settings_path_is_redacted_when_the_file_disappears_before_open
    # exercises exactly this window.
    if ! jq_available; then
      printf 'file\tunreadable:the admitted jq route could not be run, so this file cannot be inspected'
      return 0
    fi
    status=0
    found="$(settings_bypass_classification 2>/dev/null < "$value")" || status=$?
    if [ "$status" -ne 0 ]; then
      printf 'file\tunreadable:the file could not be parsed as a settings object'
      return 0
    fi
    [ "$found" = clean ] && return 1
    printf 'file\t%s' "$found"
    return 0
  fi

  printf 'invalid'
}

settings_argument_refusal() {
  local source="$1" offending="$2" label="the selected --settings value"
  [ "$source" = file ] && label="the selected --settings file"
  case "$offending" in
    invalid)
      refuse "the --settings value is not a valid JSON object or a readable settings file" ;;
    unreadable:*)
      refuse "$label could not be checked (${offending#unreadable:}); an unverifiable --settings value stops the launch rather than passing as clean" ;;
    apiKeyHelper)
      refuse "$label defines apiKeyHelper, which outranks your Claude login and bills whatever key it returns; remove it or use a per-command wrapper" ;;
    ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN)
      refuse "$label sets $offending to an sk-ant-api* Console key, which takes the same native passthrough branch and bills API credits rather than your subscription" ;;
    ANTHROPIC_BASE_URL)
      refuse "$label sets ANTHROPIC_BASE_URL in its \`env\` block to an address that is not this host's loopback gateway, and that value REPLACES the one this launch sets, so the session would talk to it instead of the gateway" ;;
    ANTHROPIC_DEFAULT_SONNET_MODEL|ANTHROPIC_DEFAULT_OPUS_MODEL|ANTHROPIC_DEFAULT_HAIKU_MODEL|ANTHROPIC_DEFAULT_FABLE_MODEL|ANTHROPIC_SMALL_FAST_MODEL|ANTHROPIC_MODEL)
      refuse "$label sets $offending in its \`env\` block to a cloud-provider model id (a Bedrock region or \`anthropic.\` publisher prefix, or a Vertex publisher path or @<date> suffix); $(model_slot_refusal_reason)" ;;
    *)
      refuse "$label carries $offending, which routes Claude Code to a cloud provider and bypasses this gateway" ;;
  esac
}

assert_forwarded_settings_are_effective() {
  local -a arguments=("$@")
  local index=0 argument value result source offending
  while [ "$index" -lt "${#arguments[@]}" ]; do
    argument="${arguments[$index]}"
    case "$argument" in
      --) break ;;
      --settings)
        index=$((index + 1))
        if [ "$index" -ge "${#arguments[@]}" ] || [ -z "${arguments[$index]}" ]; then
          printf 'error: --settings requires a non-empty file-or-json value\n' >&2
          return 2
        fi
        value="${arguments[$index]}"
        ;;
      --settings=*)
        value="${argument#--settings=}"
        if [ -z "$value" ]; then
          printf 'error: --settings requires a non-empty file-or-json value\n' >&2
          return 2
        fi
        ;;
      *) index=$((index + 1)); continue ;;
    esac
    if result="$(settings_argument_bypassing_key_name "$value")"; then
      if [ "$result" = invalid ]; then
        settings_argument_refusal inline invalid
      fi
      source="${result%%$'\t'*}"
      offending="${result#*$'\t'}"
      settings_argument_refusal "$source" "$offending"
    fi
    index=$((index + 1))
  done
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
  local offending document value
  if offending="$(gateway_bypassing_env_name)"; then
    case "$offending" in
      # An exported base URL neither outranks nor replaces anything: opencodex PRESERVES it and
      # never sets its own, so it simply IS the destination. Different sentence, same exit.
      ANTHROPIC_BASE_URL)
        refuse "ANTHROPIC_BASE_URL is exported with an address that is not this host's loopback gateway, and \`ocx claude\` preserves an exported value rather than replacing it, so your Claude login would be sent to that address and the gateway would never see the session; unset it, or set it to http://127.0.0.1:<the port \`ccodex status\` reports>" ;;
      *)
        refuse "$offending is exported and in force, which routes Claude Code to a cloud provider and bypasses the gateway entirely; unset it -- a switch whose value is 0, false, or empty already counts as off -- or set it per command in front of a plain \`claude\` run for that route" ;;
    esac
  fi
  # Checked with the exported switches above rather than after the documents, because it is the same
  # channel: a slot set in this shell. A cloud switch still names itself first, since it defeats the
  # route no matter what any model id says.
  if offending="$(cloud_shaped_model_slot_env)"; then
    value="${offending#*$'\t'}"
    offending="${offending%%$'\t'*}"
    refuse "$offending is exported as $value, a cloud-provider model id (a Bedrock region or \`anthropic.\` publisher prefix, or a Vertex publisher path or @<date> suffix); $(model_slot_refusal_reason)"
  fi
  if offending="$(bypassing_settings_document_and_key)"; then
    document="${offending%%$'\t'*}"
    offending="${offending#*$'\t'}"
    # Name the actual consequence: a settings document carries four different hazards, and
    # "outranks the base URL" is only true of the provider switches. ANTHROPIC_BASE_URL there
    # does not outrank the gateway's base URL, it REPLACES it, which is a different sentence.
    case "$offending" in
      unreadable:*)
        refuse "$document could not be checked (${offending#unreadable:}); that document can silently outrank this gateway, so an unverifiable one stops the launch rather than passing as clean" ;;
      apiKeyHelper)
        refuse "$document defines apiKeyHelper, which outranks your Claude login and bills whatever key it returns; remove it or use a per-command wrapper" ;;
      ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN)
        refuse "$document sets $offending to an sk-ant-api* Console key, which takes the same native passthrough branch and bills API credits rather than your subscription" ;;
      ANTHROPIC_BASE_URL)
        # Measured, not inferred: the settings `env` merge REPLACES the base URL ocx puts in the
        # child process environment, so this address wins and the gateway is never contacted. The
        # value is never printed -- a base URL can carry userinfo credentials.
        refuse "$document sets ANTHROPIC_BASE_URL in its \`env\` block to an address that is not this host's loopback gateway, and that value REPLACES the one this launch sets, so the session would talk to it instead of the gateway; remove the key, or set it to http://127.0.0.1:<the port \`ccodex status\` reports>" ;;
      ANTHROPIC_DEFAULT_SONNET_MODEL|ANTHROPIC_DEFAULT_OPUS_MODEL|ANTHROPIC_DEFAULT_HAIKU_MODEL|ANTHROPIC_DEFAULT_FABLE_MODEL|ANTHROPIC_SMALL_FAST_MODEL|ANTHROPIC_MODEL)
        refuse "$document sets $offending in its \`env\` block to a cloud-provider model id (a Bedrock region or \`anthropic.\` publisher prefix, or a Vertex publisher path or @<date> suffix); $(model_slot_refusal_reason)" ;;
      *)
        refuse "$document carries $offending, which routes Claude Code to a cloud provider and bypasses this gateway; move it to a per-command wrapper instead of a settings document Claude Code reads on every launch" ;;
    esac
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
  local permission_profile="$1"
  shift
  require_ocx
  # Checked BEFORE any gateway is started: a refused launch must not leave a proxy running
  # that the operator did not ask for.
  assert_gateway_route_is_effective
  assert_forwarded_settings_are_effective "$@" || return $?

  if ! command -v claude >/dev/null 2>&1; then
    printf 'error: the `claude` CLI is not on PATH; opencodex cannot launch it\n' >&2
    exit 1
  fi

  # ADR-0012 decision 4: the launchers ship an opinionated 85 only when the operator has not
  # already chosen a value. This used to arrive via the env scrub's capture-then-restore, which
  # ADR-0014 deleted along with the rest of the scrub -- so it is set explicitly here rather than
  # silently lost. One-directional safe: ignored if at or above Claude Code's own default, and
  # compacts earlier (~0.85*272000≈231200) if below it. scripts/muse-claude.sh does the same.
  #
  # CEILING, so the arithmetic above is not always the effect: if the operator's ocx config sets
  # `claudeCode.maxContextTokens`, buildClaudeEnv exports CLAUDE_CODE_MAX_CONTEXT_TOKENS together
  # with DISABLE_COMPACT=1 (cli/claude.ts:167-170), and with compaction disabled outright this 85
  # is INERT -- no percentage of any window applies. The variable is still exported and still
  # visible in the child environment, which is exactly why it reads as active when it is not.
  if [ -z "${CLAUDE_AUTOCOMPACT_PCT_OVERRIDE:-}" ]; then
    export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=85
  fi

  # Claude Code flattens auto-fetched claude.ai connector tools into Anthropic tool names such
  # as `mcp__claude_ai_<connector>__<tool>`. Muse Spark rejects the whole request when any one
  # of those names exceeds its 64-character function-name ceiling, before the model can answer
  # or choose a different tool. Measured on 2026-08-12 with AlphaVantage (68) and Robinhood (65).
  # Keep local/project/plugin MCP servers: this switch gates only auto-fetched claude.ai cloud
  # connectors. Preserve an explicit operator value so a native-Claude or known-compatible
  # gateway session can opt back in with `ENABLE_CLAUDEAI_MCP_SERVERS=true ccodex launch`.
  if [ -z "${ENABLE_CLAUDEAI_MCP_SERVERS+x}" ]; then
    export ENABLE_CLAUDEAI_MCP_SERVERS=false
  fi

  printf 'preparing gateway-routed Claude Code\n'
  ensure_gateway_up
  local json port
  json="$(gateway_health_json)"
  port="$(health_field port "$json")"
  # Before the banner, so a refusal is never printed underneath a report of the session it stopped.
  assert_selected_model_is_served "$port" "$@"
  printf '  config dir: %s (global)\n' "$HOME/.claude"
  printf '              ocx claude writes its roster agents and gateway model cache HERE; this\n'
  printf '              route no longer uses a private plane (ADR-0014 supersedes ADR-0010 here)\n'
  printf '  auth      : your own Claude login is preserved and sent to the gateway. Native claude\n'
  printf '              models pass through verbatim to Anthropic on your subscription; gateway\n'
  printf '              models route to their own providers. This wrapper never reads it.\n'
  printf '  connectors: claude.ai cloud connectors are off by default for gateway compatibility;\n'
  printf '              set ENABLE_CLAUDEAI_MCP_SERVERS=true before launch to opt in explicitly\n'
  if [ "$permission_profile" = yolo ]; then
    printf '  permissions: BYPASSED (--yolo); Auto classifier and ordinary approval checks are off\n'
  else
    printf '  permissions: no ccodex profile selected; forwarded Claude arguments remain authoritative\n'
  fi
  printf '  routed at : http://127.0.0.1:%s\n' "${port:-unknown}"
  # Accepted Claude arguments retain their exact bytes and boundaries. They can still contain
  # settings and secrets, so validation never becomes an excuse to echo raw argv.
  printf '  workspace : %s\n' "$caller_working_dir"
  printf '  command   : pinned ocx claude [forwarded arguments withheld]\n\n'
  # ocx claude re-checks liveness, then execs `claude` with stdio inherited. It injects a marker
  # token ONLY when markerMode resolves to "proxy" (cli/claude.ts:133) or an admission key is
  # configured (:115); with a detected login neither fires, so Claude Code keeps its own OAuth
  # and the native models pass through. It also pre-writes the gateway model cache (:286), which
  # is what puts the routed ids in the /model picker.
  if [ "$permission_profile" = yolo ]; then
    launch_ocx_claude --dangerously-skip-permissions "$@"
  else
    launch_ocx_claude "$@"
  fi
}

assert_yolo_has_no_competing_permission_control() {
  local argument
  for argument in "$@"; do
    case "$argument" in
      --) break ;;
      --yolo|--dangerously-skip-permissions|--dangerously-skip-permissions=*|--allow-dangerously-skip-permissions|--allow-dangerously-skip-permissions=*|--permission-mode|--permission-mode=*)
        printf 'REFUSED: --yolo owns the session permission mode; remove the competing %s argument\n' "$argument" >&2
        return 3
        ;;
    esac
  done
}

cmd_launch_route() {
  local permission_profile="$1" forward_verbatim="$2"
  shift 2
  if ! $forward_verbatim; then
    local argument
    for argument in "$@"; do
      [ "$argument" = -- ] && break
      if [ "$argument" = --yolo ]; then
        printf 'REFUSED: --yolo is a wrapper option and must be the first argument after the launch verb\n' >&2
        return 3
      fi
    done
  fi
  if [ "$permission_profile" = yolo ]; then
    assert_yolo_has_no_competing_permission_control "$@" || return $?
  fi
  cmd_launch "$permission_profile" "$@"
}

cmd_launch_ultracode() {
  local permission_profile="$1" forward_verbatim="$2"
  shift 2
  local argument previous=""
  for argument in "$@"; do
    [ "$argument" = -- ] && break
    case "$argument" in
      --settings|--settings=*)
        printf 'REFUSED: launch-ultracode owns the session --settings value; use ordinary launch for a custom settings document\n' >&2
        return 3
        ;;
      --dangerously-skip-permissions|--dangerously-skip-permissions=*|--allow-dangerously-skip-permissions|--allow-dangerously-skip-permissions=*|--permission-mode=bypassPermissions)
        if [ "$permission_profile" = yolo ]; then
          printf 'REFUSED: --yolo owns the session permission mode; remove the competing %s argument\n' "$argument" >&2
          return 3
        fi
        printf 'REFUSED: launch-ultracode never bypasses permissions; use ordinary launch for an explicitly chosen risk profile\n' >&2
        return 3
        ;;
      --permission-mode|--permission-mode=*)
        if [ "$permission_profile" = yolo ]; then
          printf 'REFUSED: --yolo owns the session permission mode; remove the competing %s argument\n' "$argument" >&2
          return 3
        fi
        ;;
      --yolo)
        if ! $forward_verbatim; then
          printf 'REFUSED: --yolo is a wrapper option and must be the first argument after the launch verb\n' >&2
          return 3
        fi
        ;;
      bypassPermissions)
        if [ "$previous" = "--permission-mode" ]; then
          if [ "$permission_profile" = yolo ]; then
            printf 'REFUSED: --yolo owns the session permission mode; remove the competing --permission-mode argument\n' >&2
            return 3
          fi
          printf 'REFUSED: launch-ultracode never bypasses permissions; use ordinary launch for an explicitly chosen risk profile\n' >&2
          return 3
        fi
        ;;
    esac
    previous="$argument"
  done
  if [ "$permission_profile" = yolo ]; then
    assert_yolo_has_no_competing_permission_control "$@" || return $?
  fi
  cmd_launch "$permission_profile" --settings '{"ultracode":true}' "$@"
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
    printf '  unknown : could not compare (gateway down, or curl or the admitted jq route could not\n'
    printf '            be run). A configured provider is NOT proven live by appearing in the list\n'
    printf '            above.\n'
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
  local blocker="" document="" slot_value=""
  if blocker="$(gateway_bypassing_env_name)"; then
    case "$blocker" in
      ANTHROPIC_BASE_URL)
        printf '  BYPASSED: ANTHROPIC_BASE_URL is exported with a non-loopback address; a launch would\n'
        printf '            send your Claude login there, not to this gateway (the value is not printed)\n' ;;
      *)
        printf '  BYPASSED: %s is exported; a launch would reach a cloud provider, not this gateway\n' "$blocker" ;;
    esac
  # Same order as assert_gateway_route_is_effective, and here for the same reason `status` names its
  # documents: reporting `ok` on a shell that `launch` refuses would be the reassurance this section
  # exists to stop giving. A model id is not a credential, so the value IS printed.
  elif blocker="$(cloud_shaped_model_slot_env)"; then
    slot_value="${blocker#*$'\t'}"
    blocker="${blocker%%$'\t'*}"
    printf '  MISROUTED: %s is exported as %s, a cloud-provider model id; a launch refuses --\n' "$blocker" "$slot_value"
    printf '            that family would be served by the DEFAULT provider, not by Anthropic\n'
  elif blocker="$(bypassing_settings_document_and_key)"; then
    document="${blocker%%$'\t'*}"
    blocker="${blocker#*$'\t'}"
    case "$blocker" in
      unreadable:*)
        printf '  UNKNOWN : %s could not be checked (%s); a launch refuses rather than assume it is clean\n' "$document" "${blocker#unreadable:}" ;;
      *)
        printf '  BYPASSED: %s in %s outranks the gateway\n' "$blocker" "$document" ;;
    esac
  elif blocker="$(console_key_env_name)"; then
    printf '  MISBILLED: %s holds an sk-ant-api* Console key; native turns would bill credits\n' "$blocker"
  else
    # NAME the documents. The line this replaced said "nothing in this shell or the global settings
    # document outranks the gateway" while reading only one of the three documents Claude Code
    # consults, so it reassured about a surface it had not inspected.
    printf '  ok      : nothing exported in this shell, and no key in the documents below, outranks\n'
    printf '            the gateway route\n'
    while IFS= read -r document; do
      printf '            checked: %s\n' "$document"
    done < <(claude_settings_documents)
    printf '            NOT checked: enterprise managed policy (see `ccodex launch --help`)\n'
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

# The fallback for a provider that is NOT YET in the config file: a registry name upstream ships
# but the operator has not added, so `configured_provider_class` returns absent (3) and there is
# no baseUrl to classify. Every name here is one the upstream registry serves from a
# non-Anthropic endpoint. It is a positive list on purpose -- an unrecognized name is refused,
# not admitted -- so a registry that grows leaves this list narrow rather than wrong, and the
# only cost of a stale entry is a refusal the operator resolves by adding the provider first.
# Read from the opencodex 2.28.0 registry roster; the five names 2.28.0 added over 2.11.1 are
# chutes, featherless, nous, novita, and xiaomi-mimo.
known_non_anthropic_provider() {
  case "$(normalize_identifier "$1")" in
    cursor|xai|command-code|kimi|kiro|openai-apikey|umans|opencode-go|neuralwatt|openrouter|cline-pass|cline|orcarouter|bizrouter|groq|google|google-vertex|google-antigravity|azure-openai|ollama|vllm|lm-studio|deepseek|cerebras|deepinfra|hyperbolic|baseten|commandcode|together|fireworks|firepass|moonshot|huggingface|nvidia|venice|zai|zhipu-bigmodel|nanogpt|synthetic|siliconflow|chutes|featherless|nous|novita|qwen-cloud|tencent-coding-plan|volcengine|volcengine-coding-plan|volcengine-agent-plan|qianfan|alibaba|alibaba-token-plan|alibaba-token-plan-intl|parallel|zenmux|litellm|ollama-cloud|mistral|minimax|minimax-cn|kimi-code|opencode-zen|vercel-ai-gateway|opencode-free|xiaomi|xiaomi-mimo|kilo|mimo-free|cloudflare-ai-gateway|cloudflare-workers-ai|github-copilot|gitlab-duo|openai) return 0 ;;
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
  printf '\nREFUSED: cannot classify this provider because no admitted `jq` route runs on this host.\n\n' >&2
  cat >&2 <<EOF
This is a MISSING TOOL, not a rejected provider. Classification decides whether a configure
mutation targets a non-Anthropic provider (admitted) or an Anthropic one (refused under
ADR-0003), and it cannot be decided without reading the provider config.

Exactly two routes are admitted, and a \`jq\` merely present on PATH is deliberately NOT one of
them (ADR-0020: an execution dependency at a trust boundary is exact or it is refused). Seeing
this means neither admitted route ran. They are, in this order, the exact copy an
operator-tools install bound and this checkout's pinned copy (mise.toml, jq = 1.8.2):

  \$AGENTIC_SDLC_JQ
  mise -C $root exec -- jq

Fix whichever applies -- rebind the installed executables, or resolve the pin in this checkout:

  mise run operator-tools:install
  mise -C $root --locked install

Installing jq with your own package manager does NOT satisfy either route. Then re-run the same
command. Nothing was changed.
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
    # Every route uses one leading wrapper separator to reach Claude Code. For the two launch
    # routes it also disables the wrapper-owned --yolo interpretation, so `-- --yolo` is passed
    # literally while a first `--yolo` is consumed here and translated into Claude's explicit
    # permission-bypass flag.
    forward_verbatim=false
    if strip_forwarding_separator "${1:-}"; then
      shift
      forward_verbatim=true
    fi
    case "$route" in
      ensure) [ "$#" -eq 0 ] || { printf 'error: `ensure` takes no arguments\n' >&2; exit 2; }; cmd_ensure ;;
      launch)
        permission_profile=ordinary
        if ! $forward_verbatim && [ "${1:-}" = --yolo ]; then permission_profile=yolo; shift; fi
        cmd_launch_route "$permission_profile" "$forward_verbatim" "$@"
        ;;
      launch-ultracode)
        permission_profile=ordinary
        if ! $forward_verbatim && [ "${1:-}" = --yolo ]; then permission_profile=yolo; shift; fi
        cmd_launch_ultracode "$permission_profile" "$forward_verbatim" "$@"
        ;;
      status) cmd_status "$@" ;;
      restart) cmd_restart "$@" ;;
      configure) cmd_configure "$@" ;;
    esac
    ;;
  -h|--help|help) usage ;;
  "") usage >&2; exit 2 ;;
  *) printf 'error: unknown subcommand %s\n\n' "$route" >&2; usage >&2; exit 2 ;;
esac
