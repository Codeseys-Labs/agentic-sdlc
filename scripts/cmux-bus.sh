#!/bin/bash
# cmux-bus.sh — pub/sub messaging over the cmux event bus (generic, no host-specific paths).
#
# cmux has a real event plane: `cmux events` streams newline-delimited JSON with monotonic
# seq numbers, retained replay (--after), durable cursor files, reconnect/resume; every event
# is also appended to ~/.cmuxterm/events.jsonl. There is no free-form "emit JSON" RPC, but
# every `cmux log` call emits a `sidebar.log.appended` event — this wrapper rides that:
# PUBLISH = `cmux log --source msg:<topic>` with a base64 payload (survives quoting);
# SUBSCRIBE = tail `cmux events` filtered to that channel and decode.
#
# USAGE:
#   cmux-bus.sh pub <topic> <message...>
#   cmux-bus.sh sub <topic> [--limit N] [--after SEQ] [--cursor-file F] [--reconnect]
#   cmux-bus.sh sub '*' ...                    # all topics
#   cmux-bus.sh seq                            # print current latest_seq (for --after)
#
# GOTCHAS baked in (verified):
#   * Read the current seq via the ack line (`events | head -1`), NEVER `events --limit 1`
#     — --limit N waits for N real EVENT frames (ack doesn't count) and hangs on an idle bus.
#   * Frames cap at 16KiB: put big payloads in a FILE, publish the path (claim-check).
#   * Capture seq BEFORE spawning workers; subscribe --after <seq>; dedupe (replay re-delivers).
# Exit vocabulary, one derivation point:
#   0  a valid query (--help) or a completed publish/seq/sub
#   2  a grammar error (unknown mode, missing topic/message) -- left exactly as measured
#   3  a clean refusal before any effect: cmux is absent, or this process is not inside cmux
#   6  `pub`'s one real effect (the `cmux log` call) was attempted and failed. Named rather than
#      mirrored: `cmux log`'s own exit status belongs to an arbitrary external CLI and can
#      collide with this wrapper's own clean-refusal 3 (a `cmux log` that itself exits 3 would
#      otherwise be byte-identical to a refusal that never touched the bus at all) -- the same
#      collision gate_receipt.py's exit-code block names for a gate's own exit code, with the
#      same fix: 6 sits outside the reserved 0-4 block precisely so it can report an observed-
#      but-not-passed-through child result. Translated (not merely documented) per the
#      decision9 survey's SP-5 REMEDIATION.
set -u

EXIT_OK=0
EXIT_REFUSED=3
EXIT_PUBLISH_FAILED=6

MODE="${1:-}"; shift 2>/dev/null || true

# The help/no-mode query is a 0-class read of this file's own header and must be reachable
# on a host with no cmux CLI and no CMUX_WORKSPACE_ID -- it asks nothing of either.
case "$MODE" in
  ""|-h|--help|help)
    sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'
    exit "$EXIT_OK"
    ;;
esac

command -v cmux >/dev/null 2>&1 || { echo "cmux-bus: cmux CLI not on PATH." >&2; exit "$EXIT_REFUSED"; }
[ -n "${CMUX_WORKSPACE_ID:-}" ] || { echo "cmux-bus: not inside cmux (CMUX_WORKSPACE_ID unset)." >&2; exit "$EXIT_REFUSED"; }

case "$MODE" in
  pub)
    TOPIC="${1:-}"; shift 2>/dev/null || true
    [ -n "$TOPIC" ] || { echo "cmux-bus pub: need a topic" >&2; exit 2; }
    MSG="$*"
    [ -n "$MSG" ] || { echo "cmux-bus pub: need a message" >&2; exit 2; }
    B64="$(printf '%s' "$MSG" | base64 | tr -d '\n')"
    if ! cmux log --level info --source "msg:$TOPIC" "MSGB64:$B64" >/dev/null 2>&1; then
      echo "cmux-bus pub: cmux log failed" >&2
      exit "$EXIT_PUBLISH_FAILED"
    fi
    ;;
  seq)
    timeout 3 cmux events --no-heartbeat 2>/dev/null | head -1 | python3 -c \
      'import json,sys;print(json.load(sys.stdin).get("resume",{}).get("latest_seq",0))'
    ;;
  sub)
    TOPIC="${1:-}"; shift 2>/dev/null || true
    [ -n "$TOPIC" ] || { echo "cmux-bus sub: need a topic (or '*')" >&2; exit 2; }
    EV_ARGS="--category sidebar --name sidebar.log.appended --no-ack --no-heartbeat"
    for a in "$@"; do EV_ARGS="$EV_ARGS $a"; done
    # shellcheck disable=SC2086
    cmux events $EV_ARGS 2>/dev/null | python3 -u -c '
import sys, json, base64, re
want = sys.argv[1]
pat = re.compile(r"MSGB64:([A-Za-z0-9+/=]+)")
srcpat = re.compile(r"--source (\S+)")
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    try: e = json.loads(line)
    except Exception: continue
    args = e.get("payload", {}).get("args", "")
    m = pat.search(args)
    if not m: continue
    sm = srcpat.search(args)
    source = sm.group(1) if sm else "msg:?"
    topic = source[4:] if source.startswith("msg:") else source
    if want != "*" and topic != want: continue
    try: msg = base64.b64decode(m.group(1)).decode("utf-8", "replace")
    except Exception: continue
    sys.stdout.write("%s\t%s\t%s\n" % (e.get("seq",""), topic, msg))
    sys.stdout.flush()
' "$TOPIC"
    ;;
  *)
    echo "cmux-bus: unknown mode '$MODE' (pub|sub|seq)" >&2; exit 2
    ;;
esac
