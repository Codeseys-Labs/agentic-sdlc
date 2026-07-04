# cmux Integration

Use this reference when `CMUX_WORKSPACE_ID` is set (the session runs inside the cmux
terminal). cmux is the VIEW layer and general event bus; CAO stays the control layer.
If cmux is absent, skip this file — nothing in the loop depends on it.

## Detection

```bash
test -n "$CMUX_WORKSPACE_ID" && echo "in cmux"
```

## Division of Labor (verified)

| Concern | Owner |
|---|---|
| Spawn/route/collect agent fleets, roles, schedules | **CAO** (tmux sessions + MCP) |
| Watch/steer a live worker TUI, sidebar status, notifications, browser panes | **cmux** |
| Non-agent notifications and cross-cutting pub/sub | **cmux event bus** |

## View a CAO worker inside cmux (works, no setup)

CAO workers live in detached tmux sessions named `cao-<session>`. Render any of them as a
cmux workspace:

```bash
cmux new-workspace --name "CAO: <session>" --command "tmux attach -t cao-<session>" --focus false
```

The workspace shows the live agent TUI (interactive — you can type to steer). Close with
`cmux close-workspace --workspace <ref>` (NOT `workspace-action`, which has no close verb).

Richer mirror (`cmux ssh-tmux localhost`, each tmux session→workspace) needs sshd enabled
locally + cmux's "Remote tmux" beta. The plain attach is usually enough.

## cmux event bus (pub/sub with replay)

cmux has a real event plane — `cmux events` streams newline-delimited JSON with monotonic
`seq`, retained replay (`--after <seq>`), durable cursors (`--cursor-file`), `--reconnect`.
Every event also lands in `~/.cmuxterm/events.jsonl`. There is no free-form emit RPC; the
general publish path is that every `cmux log` call emits a `sidebar.log.appended` event:

```bash
# publish (base64 keeps spaces/quotes/newlines intact through the shell-quoted args field)
cmux log --level info --source "msg:<topic>" "MSGB64:$(printf '%s' "$msg" | base64 | tr -d '\n')"
# subscribe
cmux events --category sidebar --name sidebar.log.appended --after "$SEQ" --reconnect
```

Gotchas (both verified the hard way):

1. **Do NOT read the current seq with `cmux events --limit 1`** — `--limit N` waits for N
   real EVENT frames (the ack does not count) and hangs forever on an idle bus. Use:
   `timeout 3 cmux events --no-heartbeat | head -1` and parse `resume.latest_seq` from the ack.
2. **Lost-wakeup:** capture `latest_seq` BEFORE spawning workers, subscribe `--after <seq>`,
   dedupe by id (replay can re-deliver).
3. **Claim-check pattern:** bus frames cap at 16 KiB. Put large output in a FILE; publish
   only `id=<n> status=<ok|err> file=<path>`.

Use the bus for non-agent traffic (progress pings, sidebar status, notify-on-done). Agent
coordination should ride CAO's `handoff`/`assign`/`send_message` instead.

## Sidebar as a run dashboard

```bash
cmux set-status <key> <value> --icon <sf-symbol> --color <#hex>   # status pill
cmux set-progress 0.5 --label "wave 2/4"                          # progress bar
cmux notify --title "Wave done" --body "3/3 seeds closed"          # desktop notification
```

Useful pattern: the conductor sets a pill per wave (`wave=2/4 ⏳`) and notifies when gates
pass, so a human can glance at the sidebar instead of tailing logs.

## Spawning raw CLI workers in cmux (fallback when CAO is absent)

`cmux new-workspace --command "<text>"` TYPES text+Enter into the new workspace's
interactive zsh — shell aliases expand as if hand-typed, so existing `ccode`/`codex`
launchers work unmodified. Collect via the event bus (above) or a result file. This is a
valid no-install fallback for a small fleet, but prefer CAO when installed: structured
`handoff`/`assign`, state tracking, provider profiles.

## Delegation decision matrix (inside cmux, all layers available)

| Situation | Use |
|---|---|
| Results needed in THIS conversation | provider-native subagents (Claude Task/Workflow; Codex role subagents) |
| Durable cross-CLI fleet, roles, mixed engines | CAO |
| Human wants to watch/steer live worker TUIs | CAO + cmux `tmux attach` workspaces |
| Non-agent notifications / cross-cutting events | cmux event bus |
| Tiny fleet, CAO not installed | cmux `new-workspace` + event-bus collection |
