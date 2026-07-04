# CAO Operations (trial-verified)

Use this reference when launching, monitoring, or debugging CAO sessions. Everything here
was verified live against CAO v2.2.0 on macOS with Claude Code + Codex on Amazon Bedrock
(2026-07-04); mechanisms cited from source where non-obvious.

## Install / bootstrap

```bash
uv tool install --python 3.13 "git+https://github.com/awslabs/cli-agent-orchestrator.git@main"
cao init                      # seeds builtin skills + DB
cao install <profile> --provider <claude_code|codex|...>
cao-server                    # REQUIRED before launch/ops; localhost:9889
```

`uv tool install --python 3.13` matters when the system Python is < 3.10.

## Environment inheritance (Bedrock et al.)

- Workers inherit env from the shell that starts **`cao-server`** (and `cao launch`).
- `--env KEY=VALUE` exists but **BLOCKS `CLAUDE`/`CODEX_`/`__MISE_` prefixes** (issue #248);
  only `AWS_`/`CAO_`/`KIRO_`/`MISE_` prefixes pass through the inherited slice.
- Therefore: export provider env (e.g. `CLAUDE_CODE_USE_BEDROCK=1 AWS_PROFILE=...`) in the
  shell that starts `cao-server`. Codex reads its own `~/.codex/config.toml` as-is.

## Per-worker model

Profiles carry an optional `model:` frontmatter field; the claude_code provider forwards it
as `claude --model <value>` (`providers/claude_code.py`). Model aliases (`opus`/`sonnet`/
`haiku`) resolve through the user's Claude Code settings to concrete Bedrock ids. Verified:
three concurrent workers each pinned to a different model from three profile files.

The codex provider forwards `profile.model` as `codex --model <value>` the same way.

## Nested orchestration

A worker whose profile has `role: supervisor` can delegate further — CAO imposes **no depth
cap** (verified: top supervisor → mid-tier lead → developer, 3 terminals, artifact produced).
Depth is bounded only by your prompts. Keep one macro conductor at the top; give mid-tier
leads explicit, narrow worker lists.

## Timeouts and long-running work

**CAO timeouts stop the CALLER waiting; they never kill the agent.** On timeout the
`handoff` tool returns a "timed out" result; `kill_session` is only called from explicit
shutdown paths. Agents live in detached tmux and run to completion regardless (verified
with a worker that outlived its caller).

| Layer | Bounds | Long-running guidance |
|---|---|---|
| `--async` launch / `assign` primitive | nothing — returns immediately | **Use this for long work.** Poll `cao session status` or read the result file. |
| `handoff` / blocking `session send` | how long the caller blocks (default 600s) | `timeout` arg has NO upper cap (`gt=0` only); 86400 accepted. |
| `server.mcp_request_timeout`, `server.provider_init_timeout`, `server.startup_prompt_handler_timeout` | HTTP round-trips to cao-server | Raise via `cao config set server.<key> <secs>`; persists to `~/.aws/cli-agent-orchestrator/settings.json`. |

Recommended baseline: `mcp_request_timeout 1800`, `provider_init_timeout 180` (see codex
gotcha below).

## Codex-provider gotchas

1. **Raise the init timeouts.** Codex backend init (e.g. Bedrock mantle) can exceed CAO's
   30s defaults → launch fails `Failed to connect to cao-server ... Read timed out`, the
   half-started session's tmux backend dies, and the API DB keeps a **stale `processing`**
   status (diagnose: `tmux ls` says "no server running" while `cao session list` shows
   processing). Fix: `cao config set server.mcp_request_timeout 180` (or higher) +
   `server.provider_init_timeout 180`.
2. **Pre-trust the working directory** in `~/.codex/config.toml`
   (`projects.'<path>'.trust_level = 'trusted'`), or the worker hangs forever on codex's
   directory-trust prompt. CAO's `--yolo` covers tool approvals, NOT dir-trust. (Answering
   `1` once in the tmux pane also auto-adds the entry.)
3. **Same agent name + different `--provider` OVERWRITES the profile** — provider is
   per-named-agent. Use distinct names (e.g. `codex_dev` vs `developer`) to mix engines in
   one fleet. Mixed-engine sessions (Claude supervisor + Claude dev + codex worker) verified.

## Headless / non-TTY drive

`cao launch` ends by attaching tmux; from a non-TTY (agent tool, CI) that attach fails
`open terminal failed: not a terminal` — **the session is still created and runs**. Drive
headlessly instead:

```bash
cao launch --agents <profile> --provider <p> --headless --async --auto-approve \
  --working-directory <dir> --session-name <name> "<task>"
cao session send <name> "<message>"      # blocking; run in bg for long turns
cao session status <name>                # conductor status + last response
cao session list                         # all sessions
tmux capture-pane -t cao-<name> -p       # raw pane when status is ambiguous
```

Status semantics: `completed` tracks the agent's conversational TURN, not shell
subprocesses it started — a `sleep 90 && write file` can land after `completed` shows.
The artifact/file is the source of truth.

## Teardown order

`cao shutdown --all` talks to `cao-server` — run it **while the server is up**, THEN kill
the server. If the server dies first, sessions orphan and need `tmux kill-session -t
cao-<id>` by hand.

## Ops-from-an-agent (`cao-ops-mcp`)

`cao-ops-mcp-server` (stdio MCP) exposes 10 typed tools to an outside primary agent:
`list_profiles`, `get_profile_details`, `install_profile`, `launch_session`,
`send_session_message`, `get_terminal_status`, `get_terminal_output`, `list_sessions`,
`get_session_info`, `shutdown_session`. It REQUIRES `cao-server` running and does not
start it — wire it with a bootstrap wrapper in the client's MCP config:

```json
{ "cao-ops-mcp": { "command": "bash", "args": ["-c",
  "if ! curl -s -m 1 http://localhost:9889/ >/dev/null 2>&1; then <PROVIDER_ENV> nohup cao-server >>$HOME/.aws/cli-agent-orchestrator/logs/cao-server-mcp.log 2>&1 & sleep 2; fi; exec cao-ops-mcp-server" ] } }
```

Replace `<PROVIDER_ENV>` with your provider env (e.g. `AWS_PROFILE=... CLAUDE_CODE_USE_BEDROCK=1`).
The curl guard makes it idempotent. This is what lets the macro conductor drive fleets as
typed MCP tool calls instead of shell.
