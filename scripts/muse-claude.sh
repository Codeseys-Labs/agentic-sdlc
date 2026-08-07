#!/bin/bash
# muse-claude.sh — direct-route launcher for Meta's Muse Spark models.
#
# Purpose: run a SECOND Claude Code process pointed straight at Meta's Anthropic-shaped
# endpoint, authenticating with Meta's OWN API key, while the operator's native Claude Code
# session and config are left untouched. Subcommands: launch | status | probe.
#
# NO GATEWAY. Unlike scripts/opencodex-claude.sh, there is no local proxy to supervise:
# api.meta.ai serves `POST /v1/messages` natively (verified — see
# docs/research/2026-08-07-muse-spark-qualification.md §5.3). ANTHROPIC_BASE_URL points at
# Meta directly. This is ADR-0003-clean for the same reason ADR-0003 item 2 carves out: a
# non-Anthropic model authenticating with its own provider-issued credential. No Anthropic
# subscription credential is involved, forwarded, or replayed.
#
# FAIL-CLOSED: reachability is never assumed from configuration. `launch` re-probes the live
# catalog AND runs one tiny real completion before exec'ing Claude Code, because each failure
# mode below is silent in a different way and none of them is visible at config time:
#   * A wrong base URL returns 401, not 404 (verified: /v1/v1/messages with a VALID key
#     answers 401). Claude Code appends /v1/messages itself, so a base URL of
#     ".../v1" -- the form the vendor documents for SDK use -- yields a 401 that is
#     indistinguishable from a bad credential. The probe distinguishes them by asserting the
#     catalog first, so an operator is never sent to rotate a key that was fine.
#   * Claude Code's built-in default model IDs are claude-* and 404 here (model_not_found).
#     The model slots below are therefore mandatory, not cosmetic.
#   * A too-small output budget returns HTTP 200 with an EMPTY content array, because
#     reasoning tokens are billed against max_tokens before any visible text (verified at
#     both 32 and 128). A liveness check that only asserted HTTP 200 would pass against a
#     route that cannot emit text at all, so the probe asserts non-empty text.
#
# WHAT THIS DELIBERATELY DOES NOT DO
#   * No credential is written, printed, or logged. The key is read from the environment or
#     from a file OUTSIDE this repository, is never echoed, and is never persisted here.
#     Passing it as a command-line argument is refused: argv is world-readable via ps.
#   * No Anthropic subscription passthrough. Same boundary as the ocx launcher and the same
#     refusals (exit 3): ADR-0003 forbids routing Claude subscription OAuth through a
#     third-party endpoint, and pointing ANTHROPIC_BASE_URL elsewhere while a subscription
#     credential is in scope is exactly that shape. The scrub plus these checks make the
#     supported shape structural rather than trusted.
#   * A passing probe is evidence, not authorization, and it is not a capability claim. It
#     proves the exact requested ID answered at that moment. It says nothing about task fit;
#     per the qualification memo the route is tier-UNPROVEN.
#   * No tier is pinned into any provider-neutral role. The model slots here configure one
#     operator-launched client process; they are not a role definition.
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Isolated Claude Code config root, mirroring the ocx launcher: a direct-route process syncs
# its own session state, and sharing ~/.claude would mutate the operator's live session.
state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
isolated_config_dir="$state_home/agentic-sdlc/muse-claude"

# Base URL WITHOUT the /v1 suffix. Claude Code appends /v1/messages itself; see the header.
muse_base_url="${MUSE_BASE_URL:-https://api.meta.ai}"
# Catalog IDs verified present on 2026-08-07. The catalog is re-probed at every launch rather
# than trusted from this list, because catalog membership is the admission check.
muse_default_model="${MUSE_MODEL:-muse-spark-1.2}"
muse_default_small_model="${MUSE_SMALL_MODEL:-muse-spark-1.1}"
# Output budget floor. Reasoning tokens are charged against max_tokens BEFORE visible text, so
# a small budget yields HTTP 200 with empty output. 600 was the smallest budget observed to
# complete a trivial prompt; 128 did not. This is a floor for the probe, not a tuned value.
probe_max_tokens=600
probe_timeout_seconds=45

usage() {
  cat <<'EOF'
usage: muse-claude.sh <launch|status|probe> [claude args...]

  launch [claude args...]   Verify the route live (catalog + tiny real completion), then
                            launch a second Claude Code process against Meta's endpoint with
                            an isolated CLAUDE_CONFIG_DIR and no Anthropic subscription
                            credential in scope. Fails closed if either check fails.
  status                    Report configuration, credential SOURCE (never its value), the
                            isolated config dir, and the live route verdict. Exit 0 healthy.
  probe                     Route verification only; never launches Claude Code.

credential: read from $MODEL_API_KEY, or from the file named by $MUSE_API_KEY_FILE, or from
            ~/.muse/api-key. Never read from inside this repository, never echoed, never
            accepted as a command-line argument.

exit codes: 0 ok · 1 failure/unreachable · 2 usage · 3 refused (subscription-OAuth boundary)
EOF
}

fail_closed() {
  printf '\nFAIL-CLOSED: %s\n' "$1" >&2
  printf 'Claude Code was NOT launched: routing it at an unverified endpoint would produce\n' >&2
  printf 'connection errors, 404 model_not_found, or silently empty responses.\n\n' >&2
  printf 'Diagnose with:\n' >&2
  printf '  scripts/muse-claude.sh status\n' >&2
  printf '  qualification evidence: docs/research/2026-08-07-muse-spark-qualification.md\n' >&2
  exit 1
}

refuse() {
  printf '\nREFUSED: %s\n' "$1" >&2
  cat >&2 <<'EOF'
docs/adr/0003 rejects routing Claude subscription OAuth through a third-party endpoint.
Anthropic's own legal-and-compliance documentation scopes subscription OAuth to ordinary use
of native Anthropic applications. Pointing ANTHROPIC_BASE_URL at another provider while a
subscription credential is in scope is that prohibited shape. The mechanism works; the
authorization does not.

The supported path is this one: a non-Anthropic model authenticating with its OWN
provider-issued API key, with every ANTHROPIC*/CLAUDE* slot scrubbed first.
EOF
  exit 3
}

# --- credential acquisition ---------------------------------------------------------------
#
# Resolution order is environment first, then an explicitly named file, then a conventional
# path. Every source is outside this repository by construction: a path that resolves inside
# the repo is refused outright, so a key can never be committed by way of this launcher.
# Only the SOURCE is ever reported; the value is never printed, logged, or exported anywhere
# except the child process environment.
credential_source=""
muse_key=""

reject_in_repo_path() {
  local path="$1" resolved
  resolved="$(CDPATH= cd -- "$(dirname -- "$path")" 2>/dev/null && pwd)" || return 0
  case "$resolved/" in
    "$root"/*) printf 'error: refusing to read a credential from inside the repository (%s)\n' "$path" >&2
               printf 'A credential must never live in a tracked tree. Move it outside %s\n' "$root" >&2
               exit 1 ;;
  esac
}

read_key_file() {
  local path="$1"
  reject_in_repo_path "$path"
  [ -f "$path" ] || return 1
  [ -L "$path" ] && { printf 'error: credential file is a symlink; refusing (%s)\n' "$path" >&2; exit 1; }
  [ -r "$path" ] || { printf 'error: credential file is not readable (%s)\n' "$path" >&2; exit 1; }
  # Whitespace/newline trimmed so an editor-added trailing newline is not sent as part of the
  # bearer token, which would fail as a 401 and read as a bad key.
  muse_key="$(tr -d '\r\n[:space:]' < "$path")"
  [ -n "$muse_key" ] || { printf 'error: credential file is empty (%s)\n' "$path" >&2; exit 1; }
  credential_source="file:$path"
  return 0
}

resolve_credential() {
  if [ -n "${MODEL_API_KEY:-}" ]; then
    muse_key="$MODEL_API_KEY"
    credential_source="environment:MODEL_API_KEY"
    return 0
  fi
  if [ -n "${MUSE_API_KEY_FILE:-}" ]; then
    read_key_file "$MUSE_API_KEY_FILE" && return 0
    printf 'error: MUSE_API_KEY_FILE is set but unusable (%s)\n' "$MUSE_API_KEY_FILE" >&2
    exit 1
  fi
  read_key_file "$HOME/.muse/api-key" && return 0
  printf 'error: no Muse Spark credential found.\n\n' >&2
  printf 'Provide it as MODEL_API_KEY in the environment, or in a file named by\n' >&2
  printf 'MUSE_API_KEY_FILE, or at ~/.muse/api-key (mode 600, outside any repository).\n' >&2
  printf 'This launcher never reads a credential from inside %s\n' "$root" >&2
  exit 1
}

# A credential on the command line is readable by every process on the host via ps, so it is
# refused before anything else runs rather than being quietly accepted.
reject_credential_arguments() {
  local argument
  for argument in "$@"; do
    case "$argument" in
      --api-key|--api-key=*|--auth-token|--auth-token=*|MODEL_API_KEY=*)
        printf 'REFUSED: a credential must not be passed on the command line; argv is visible in ps.\n' >&2
        printf 'Use MODEL_API_KEY in the environment or a credential file instead.\n' >&2
        exit 3
        ;;
    esac
  done
}

# --- subscription-OAuth boundary ----------------------------------------------------------
#
# Same boundary and same sources as the ocx launcher. Checked BEFORE the scrub, because after
# the scrub there is nothing left to inspect, and before any network call, so a refused launch
# sends no traffic.
subscription_shaped_env() {
  local name value
  for name in ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY; do
    value="${!name:-}"
    # sk-ant-oat* is a subscription OAuth access token. An sk-ant-api* developer API key is a
    # different credential class and is not what ADR-0003 forbids; it is scrubbed rather than
    # refused, so it never reaches Meta's endpoint by accident either.
    case "$value" in
      sk-ant-oat*) printf '%s' "$name"; return 0 ;;
    esac
  done
  return 1
}

scrub_anthropic_env() {
  local name
  # Prefix scrub, not an enumerated list: the parent session exports credential slots,
  # per-tier model slots, capability strings, and routing flags (CLAUDE_CODE_USE_BEDROCK among
  # them). Any one leaking into the child either re-routes it away from Meta or carries parent
  # session identity into it. The exact slots this route needs are re-exported afterwards.
  for name in $(compgen -v | grep -E '^(ANTHROPIC|CLAUDE)' || true); do
    unset "$name" || true
  done
}

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

# macOS keychain is the one credential source an isolated config dir cannot mask, so it is
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

# --- route verification -------------------------------------------------------------------
#
# Two checks, in this order, because the first localizes the failure the second cannot. The
# credential is passed as a header inside a curl config file on stdin, never as an argv
# element -- `curl -H "Authorization: Bearer $key"` would expose the key in ps to every user
# on the host for the life of the request. Because the config occupies stdin, a request body
# must come from a real file rather than `@-`; the two would silently contend for stdin and
# curl would send the config as the body, producing a 401 that reads like a bad credential.
curl_muse() {
  local url="$1"
  shift
  command -v curl >/dev/null 2>&1 || fail_closed "curl is required to verify the route"
  printf 'header = "Authorization: Bearer %s"\n' "$muse_key" \
    | curl -sS --max-time "$probe_timeout_seconds" --config - "$url" "$@"
}

# Check 1: catalog membership is the admission check. It also localizes a base-URL error,
# because an unknown path answers 401 exactly like a bad credential does.
verify_catalog() {
  local body status
  body="$(curl_muse "$muse_base_url/v1/models" -w '\n%{http_code}' 2>/dev/null || true)"
  status="${body##*$'\n'}"
  body="${body%$'\n'*}"
  case "$status" in
    200) ;;
    401) fail_closed "the catalog returned 401. Either the credential is invalid OR the base URL is wrong -- an unknown path also answers 401 on this endpoint. Confirm MUSE_BASE_URL is $muse_base_url with NO /v1 suffix (Claude Code appends /v1/messages itself), then confirm the credential." ;;
    "")  fail_closed "the catalog at $muse_base_url/v1/models did not answer within ${probe_timeout_seconds}s" ;;
    *)   fail_closed "the catalog at $muse_base_url/v1/models returned HTTP $status" ;;
  esac
  # Substring matching would let muse-spark-1.2 match muse-spark-1.2-contributor, so the ID is
  # matched with its JSON quotes attached.
  local model
  for model in "$muse_default_model" "$muse_default_small_model"; do
    printf '%s' "$body" | grep -q "\"id\":\"$model\"" \
      || fail_closed "requested model '$model' is NOT in the served catalog. Catalog membership is the admission check; a non-catalog ID answers 404 model_not_found. Served: $(printf '%s' "$body" | grep -o '"id":"[^"]*"' | sed 's/"id":"//;s/"//' | tr '\n' ' ')"
  done
  printf '  catalog   : %s and %s present\n' "$muse_default_model" "$muse_default_small_model"
}

# Check 2: one tiny real completion on the exact surface Claude Code uses. Asserts non-empty
# text, not merely HTTP 200 -- see the header note on empty 200s.
verify_completion() {
  local body status text payload
  # The payload holds no secret -- only the model ID and a fixed prompt -- so a temp file is
  # safe here. It is required because the credential config already owns stdin.
  payload="$(mktemp "${TMPDIR:-/tmp}/muse-probe.XXXXXX")"
  printf '{"model":"%s","max_tokens":%s,"messages":[{"role":"user","content":"Reply with only the word ready."}]}' \
    "$muse_default_model" "$probe_max_tokens" > "$payload"
  body="$(curl_muse "$muse_base_url/v1/messages" \
            -H 'content-type: application/json' -H 'anthropic-version: 2023-06-01' \
            --data-binary @"$payload" -w '\n%{http_code}' 2>/dev/null || true)"
  rm -f "$payload"
  status="${body##*$'\n'}"
  body="${body%$'\n'*}"
  [ "$status" = "200" ] || fail_closed "the completion probe on /v1/messages returned HTTP ${status:-no-response}"
  # Any text block with a non-empty string. A 200 whose content array is empty means the
  # output budget was consumed by reasoning tokens before any text was emitted. This surface
  # emits `{"text":"…","type":"text"}` -- key order is not guaranteed, so the two fields are
  # matched independently rather than as one ordered pattern.
  text="$(printf '%s' "$body" | grep -o '"text":"[^"]\+"' || true)"
  [ -n "$text" ] || fail_closed "the completion probe returned HTTP 200 with EMPTY output text. On this route reasoning tokens are charged against max_tokens before visible text, so a small budget yields an empty 200. The probe used max_tokens=$probe_max_tokens."
  # The response body's model field is the ONLY identity channel on this route (there is no
  # attribution log and no provider/model response header). It is an echo of the request, so
  # a mismatch is a real failure while a match is weak evidence -- see the memo's §6.2.
  printf '%s' "$body" | grep -q "\"model\":\"$muse_default_model\"" \
    || fail_closed "the response reported a different model than requested ($muse_default_model)"
  printf '  completion: exact requested ID answered with non-empty text\n'
}

verify_route() {
  printf 'verifying the Muse Spark route (evidence, not authorization)\n'
  printf '  endpoint  : %s\n' "$muse_base_url"
  printf '  credential: %s (value never printed)\n' "$credential_source"
  verify_catalog
  verify_completion
}

# --- subcommands --------------------------------------------------------------------------

prepare_child_environment() {
  local offending
  if offending="$(subscription_shaped_env)"; then
    refuse "$offending in this environment holds a subscription OAuth access token (sk-ant-oat*)"
  fi
  mkdir -p "$isolated_config_dir"
  assert_isolated_dir_has_no_subscription
  assert_no_keychain_subscription
  scrub_anthropic_env
  # Re-export exactly the slots this route needs, after the scrub. ANTHROPIC_AUTH_TOKEN sends
  # `Authorization: Bearer`, which is verified working on this endpoint; the model slots are
  # mandatory because Claude Code's own defaults are claude-* IDs that 404 here.
  export CLAUDE_CONFIG_DIR="$isolated_config_dir"
  export ANTHROPIC_BASE_URL="$muse_base_url"
  export ANTHROPIC_AUTH_TOKEN="$muse_key"
  export ANTHROPIC_MODEL="$muse_default_model"
  export ANTHROPIC_SMALL_FAST_MODEL="$muse_default_small_model"
}

cmd_launch() {
  reject_credential_arguments "$@"
  resolve_credential
  prepare_child_environment

  if ! command -v claude >/dev/null 2>&1; then
    printf 'error: the `claude` CLI is not on PATH\n' >&2
    exit 1
  fi

  verify_route
  printf '  config dir: %s (isolated; your native ~/.claude is untouched)\n' "$isolated_config_dir"
  printf '  auth      : Meta API key in this process only; no Anthropic subscription credential in scope\n'
  printf '  models    : %s (main), %s (small/fast)\n' "$muse_default_model" "$muse_default_small_model"
  # Forwarded Claude arguments can contain inline settings and secrets. Never echo raw argv.
  printf '  command   : claude [forwarded arguments withheld]\n\n'
  exec claude "$@"
}

cmd_probe() {
  resolve_credential
  verify_route
  printf '\nroute verified. That is evidence, not authorization, and it is not a capability\n'
  printf 'claim: per the qualification memo this route is admitted but TIER-UNPROVEN.\n'
}

cmd_status() {
  printf '== muse spark direct route ==\n'
  printf '  endpoint    : %s\n' "$muse_base_url"
  printf '  main model  : %s\n' "$muse_default_model"
  printf '  small model : %s\n' "$muse_default_small_model"
  printf '  config dir  : %s\n' "$isolated_config_dir"
  if [ -d "$isolated_config_dir" ]; then
    printf '  dir state   : present\n'
  else
    printf '  dir state   : not yet created (created on first launch)\n'
  fi

  printf '\n== credential ==\n'
  if [ -n "${MODEL_API_KEY:-}" ]; then
    printf '  source      : environment:MODEL_API_KEY (value never printed)\n'
  elif [ -n "${MUSE_API_KEY_FILE:-}" ]; then
    printf '  source      : file:%s (value never printed)\n' "$MUSE_API_KEY_FILE"
  elif [ -f "$HOME/.muse/api-key" ]; then
    printf '  source      : file:%s (value never printed)\n' "$HOME/.muse/api-key"
  else
    printf '  source      : NONE FOUND\n'
    printf '\nno credential available; cannot verify the route.\n' >&2
    return 1
  fi

  printf '\n== subscription boundary ==\n'
  local offending
  if offending="$(subscription_shaped_env)"; then
    printf '  state       : REFUSED -- %s holds a subscription OAuth token\n' "$offending"
    printf '\nlaunch would refuse (exit 3) per docs/adr/0003.\n' >&2
    return 1
  fi
  printf '  state       : clear (no sk-ant-oat* token in ANTHROPIC_AUTH_TOKEN/ANTHROPIC_API_KEY)\n'

  printf '\n== live route ==\n'
  resolve_credential
  verify_catalog
  verify_completion
  printf '\nreachable: the exact requested ID answered with non-empty text. That is evidence,\n'
  printf 'not authorization, and it grants no authority for any outward effect. It is also not\n'
  printf 'a capability claim -- the route is admitted but TIER-UNPROVEN.\n'
}

case "${1:-}" in
  launch) shift; cmd_launch "$@" ;;
  status) shift; cmd_status "$@" ;;
  probe) shift; cmd_probe "$@" ;;
  -h|--help|help) usage ;;
  "") usage >&2; exit 2 ;;
  *) printf 'error: unknown subcommand %s\n\n' "$1" >&2; usage >&2; exit 2 ;;
esac
