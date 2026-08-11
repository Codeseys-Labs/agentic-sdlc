# Native Claude passthrough — measured, not inferred

Date: 2026-08-11. opencodex 2.11.1, Claude Code 2.1.227, node 22.23.2, container `ocx-probe`.
No real subscription credential was used and nothing was billed: every request below carried a
deliberately fake `sk-ant-oat01-FAKE-NOT-A-REAL-TOKEN`.

## The controlled pair

Identical request both times — same fake OAuth-shaped bearer, same `anthropic-beta`, same model
id `claude-opus-4-6`. Only `claudeCode.nativePassthrough` differs.

| `nativePassthrough` | Response | Who answered |
|---|---|---|
| absent (default) | `{"type":"authentication_error","message":"OAuth access token is invalid."}` | **api.anthropic.com** — Anthropic's own error vocabulary |
| `false` | `{"type":"authentication_error","message":"OpenAI account pool has no usable account credential"}` | **opencodex** — routed to the `openai` default provider |

The two errors come from different systems, which is what makes this a proof rather than a
coincidence. A fake token is sufficient: the passthrough gate is a bare `sk-ant-` prefix test
(`src/server/claude-messages.ts:99-103`), so the branch commits before Anthropic ever validates
the credential.

## What this establishes

1. **Passthrough is on by default and reaches Anthropic.** Absent key means enabled
   (`claude-messages.ts:106` tests `=== false`), target defaults to `https://api.anthropic.com`
   (`:320`).
2. **opencodex needs no Anthropic credential onboarded.** The container had *no* `~/.opencodex/config.json`
   at all on the first run, no `anthropic` provider, and no `ocx account login`. It still forwarded
   correctly. This is the user's hypothesis, confirmed.
3. **Disabling passthrough silently reroutes a genuine `claude-*` id to the default provider.** It
   does not refuse. With a working OpenAI pool this would have returned a GPT answer re-labelled
   `claude-opus-4-6` (`:789, :802, :849`) — the silent-wrong-model hazard, now observed rather than
   theorised.

## Separately measured on the host (not in the container)

A local capture listener that never forwards, so again nothing was billed:

- `CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-…` → sent as `Authorization: Bearer` to
  `http://127.0.0.1:…`, with `anthropic-beta: claude-code-20250219,oauth-2025-04-20,…`.
  **There is no anthropic.com host allowlist gating OAuth** — the premise holds.
- `ANTHROPIC_API_KEY=sk-ant-api03-…` → sent as `x-api-key`, no `oauth-2025-04-20` beta.
  Both prefixes satisfy opencodex's `sk-ant-` gate, so an API key takes the *native* branch and
  bills credits while looking like subscription passthrough.
- With the host's real `~/.claude/settings.json` in play, the request **never reached the listener
  at all** and was still answered. The `env` block there carries `CLAUDE_CODE_USE_BEDROCK=1` plus
  `AWS_BEARER_TOKEN_BEDROCK`, which outranks everything and bypasses `ANTHROPIC_BASE_URL`
  entirely. This is why the experiment needs a container: on this host the result would be
  confounded.
- A clean `CLAUDE_CONFIG_DIR` reports `Not logged in · Please run /login`, confirming no
  subscription OAuth exists anywhere on this host (WSL `.credentials.json` and the Windows-side
  copy both hold only `mcpOAuth`).

## Not established here

- Whether a **real** subscription token succeeds. Anthropic may reject subscription OAuth arriving
  from outside its own clients; opencodex's own source says so for its provider path
  (`src/oauth/index.ts:186-188`, "server-side-blocks subscription OAuth outside its own clients
  (Feb 2026)… grade 20, highest ToS risk"). Testing that needs a real interactive login, which is
  a human step by design.
- Whether billing lands on the subscription. Only the claude.ai usage page and the absence of
  Console API usage can show that, after a real request.
