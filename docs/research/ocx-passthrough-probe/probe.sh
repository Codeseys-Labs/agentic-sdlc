#!/bin/bash
# Probe steps to run INSIDE the container. Read it before running it; it makes real requests
# against whatever credential you logged in with, and a billed request is a billed request.
#
# ponytail: linear script, no arg parsing, no config. It is a one-shot experiment, not a tool.
set -uo pipefail

step() { printf '\n=== %s\n' "$1"; }

step '0. assert the isolation invariant (this is the whole reason for the container)'
# Any hit here means the result would be confounded and the run is void.
for name in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN AWS_BEARER_TOKEN_BEDROCK \
            CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_BASE_URL; do
  if [ -n "${!name:-}" ]; then printf 'VOID: %s is set in this container\n' "$name"; exit 3; fi
done
# settings.json env is the channel that silently bypassed ANTHROPIC_BASE_URL on the host.
# Absent is the cleanest possible state (no settings document to carry a routing key at all),
# so it counts as zero keys; only a file that EXISTS and is non-empty or unparseable voids the run.
if [ -f ~/.claude/settings.json ]; then
  env_keys="$(jq -r '(.env // {}) | keys | length' ~/.claude/settings.json 2>/dev/null || echo unknown)"
else
  env_keys=0
fi
[ "$env_keys" = "0" ] || { printf 'VOID: ~/.claude/settings.json env is not empty or unparseable (%s keys)\n' "$env_keys"; exit 3; }
# A stored API key satisfies opencodex's bare sk-ant- passthrough gate and would bill credits
# while looking like subscription traffic. It must be absent, not merely unused.
if jq -e '.primaryApiKey' ~/.claude.json >/dev/null 2>&1; then
  printf 'VOID: ~/.claude.json .primaryApiKey exists\n'; exit 3
fi
printf 'clean: no credential or provider-routing key in scope\n'

step '1. log in interactively — THIS STEP NEEDS A HUMAN'
# There is no way to automate this: OAuth is a browser consent flow by design.
# Run `claude` and use /login, or `claude setup-token`. Open the printed URL on the HOST browser;
# the container publishes the callback port so the redirect lands back here.
printf 'run: claude   then /login   (or: claude setup-token)\n'
printf 'then confirm the credential is OAuth-shaped, NOT an API key:\n'
printf '  jq -r "has(\\"claudeAiOauth\\")" ~/.claude/.credentials.json   # must print true\n'
read -r -p 'press enter once /login has completed and the above prints true: ' _

step '2. verify it is really a subscription credential'
jq -r 'if has("claudeAiOauth") then "claudeAiOauth: PRESENT" else "claudeAiOauth: ABSENT -> not a subscription login" end' \
  ~/.claude/.credentials.json
# Prefix only. Never print the token. sk-ant-oat = OAuth; sk-ant-api = API key (would bill credits).
jq -r '.claudeAiOauth.accessToken // "" | "prefix: " + .[0:11] + " len: " + (length|tostring)' \
  ~/.claude/.credentials.json

step '3. start the gateway and prove passthrough config state'
ocx ensure >/tmp/gw.log 2>&1 || true
sleep 3
ocx health || { printf 'gateway unhealthy; see /tmp/gw.log\n'; exit 1; }
# Absent is the accepted state: 2.11.1 treats nativePassthrough as on unless === false
# (src/server/claude-messages.ts:106) and defaults the target to api.anthropic.com (:320).
ocx config get claudeCode.nativePassthrough 2>&1 || true
ocx config get claudeCode.anthropicBaseUrl   2>&1 || true
# The credential must NOT be inside ocx — that is the distinction being tested.
printf 'ocx-held anthropic account (must be empty/absent):\n'
ocx account list 2>&1 | grep -i anthropic || printf '  none — good, ocx holds no Anthropic credential\n'

step '4a. NATIVE request through the gateway'
# One short prompt: cheapest thing that still exercises the branch.
ANTHROPIC_BASE_URL=http://127.0.0.1:10100 claude -p 'reply with the single word: native' \
  --model claude-opus-4-6 </dev/null 2>&1 | head -5

step '4b. VERIFY the branch — the response body is NOT admissible'
# A routed reply is re-labelled with the REQUESTED model (claude-messages.ts:789,802,849), so the
# body can say claude-opus-4-6 while GPT answered. provider=="anthropic-native" is set only on the
# native branch (:313) and is the only trustworthy discriminator.
curl -s http://127.0.0.1:10100/api/requests 2>/dev/null \
  | jq -r '.[0:5][] | "\(.model // "?")  provider=\(.provider // "?")  status=\(.status // "?")"' \
  2>/dev/null || printf 'check the dashboard at http://127.0.0.1:10100/ for the provider column\n'

step '4c. CONNECTION-LEVEL signal that a peer on port 443 was reached (not proof of WHO)'
# grep -E '443' matched any column containing those digits, including an ephemeral local port
# like 44300, and attributed nothing. ss's own filter targets the PEER (dport) side precisely.
# Reverse DNS on the peer is best-effort, not proof: a CDN-fronted IP's PTR record does not
# reliably say "anthropic" — this shows a peer was reached, not who it is.
peers="$(ss -tn state established '( dport = :443 )' 2>/dev/null | tail -n +2)"
if [ -z "$peers" ]; then
  printf 'no established port-443 peer visible\n'
else
  printf '%s\n' "$peers" | head -5 | while read -r _ _ _ peer; do
    peer_ip="${peer%:*}"
    host="$(getent hosts "$peer_ip" 2>/dev/null | awk '{print $2; exit}')"
    printf 'peer %s  reverse-dns: %s\n' "$peer" "${host:-<none>}"
  done
fi

step '5. NEGATIVE CONTROL — passthrough disabled must change the outcome'
# If (4a) and (5) look identical, (4a) proved nothing.
# A restore that only runs on the happy path — or whose own failure is discarded to /dev/null —
# can leave the gateway permanently rerouting native ids away from Anthropic with no signal, on
# an interrupt during this step or on the restoring `config set` itself failing. The trap makes
# the restore run on EXIT/INT/TERM; the readback makes silent restore failure impossible.
restored=0
restore_passthrough() {
  [ "$restored" = 1 ] && return
  restored=1
  ocx config set claudeCode.nativePassthrough true >/dev/null 2>&1
  ocx restart >/dev/null 2>&1
  readback="$(ocx config get claudeCode.nativePassthrough 2>/dev/null)"
  case "$readback" in
    *true*) printf 'restored: claudeCode.nativePassthrough=true (verified)\n' ;;
    # `return 1` here would be invisible: a nonzero return from an EXIT trap does NOT change the
    # script's exit status, so an unverified restore used to leave the whole run exiting 0 while
    # printing VOID. Only an explicit `exit` makes it a failure a caller can see. Re-entry is
    # already blocked by $restored, so the EXIT trap this fires does not loop.
    *) printf 'VOID: restore did NOT take effect (read back: %s) — fix before any other launch through this gateway\n' "$readback"
       exit 3 ;;
  esac
}
trap restore_passthrough EXIT INT TERM

# The DISABLE is verified exactly as strictly as the restore, and BEFORE the billed call. Both
# statuses used to be discarded to /dev/null with no readback while execution fell through to the
# turn below, so step 5 could run against still-ENABLED passthrough and be read as a valid negative
# control — precisely the confound the control exists to rule out. Absent is NOT disabled: 2.11.1
# treats nativePassthrough as on unless it is === false (claude-messages.ts:106), so only a `false`
# readback admits the turn. Stated rather than implied: this proves the CONFIG, and the restart is
# what makes the running gateway adopt it, which is why a failed restart aborts too.
ocx config set claudeCode.nativePassthrough false >/dev/null 2>&1 || {
  printf 'VOID: could not disable claudeCode.nativePassthrough — no control turn is run\n'
  exit 3
}
ocx restart >/dev/null 2>&1 || {
  printf 'VOID: gateway restart failed after disabling passthrough — no control turn is run\n'
  exit 3
}
sleep 3
disabled="$(ocx config get claudeCode.nativePassthrough 2>/dev/null)"
case "$disabled" in
  *false*) printf 'disabled: claudeCode.nativePassthrough=false (verified)\n' ;;
  *) printf 'VOID: passthrough is NOT disabled (read back: %s) — a billed control turn would be confounded, so it is not run\n' "$disabled"
     exit 3 ;;
esac
ANTHROPIC_BASE_URL=http://127.0.0.1:10100 claude -p 'reply with the single word: control' \
  --model claude-opus-4-6 </dev/null 2>&1 | head -5
printf '\nexpected: routed to the default provider or refused — NOT a clean native answer.\n'
restore_passthrough

step 'done'
printf 'Billing check is OUTSIDE this script: claude.ai usage page should show the turns,\n'
printf 'and the Anthropic Console API usage page should show ZERO new requests.\n'
