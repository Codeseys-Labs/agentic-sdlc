# Configuring ccodex and the ocx gateway

Use this reference when helping an operator configure `ccodex` and the ocx gateway behind it:
onboarding a provider, verifying it went live, proving a routed turn, pinning an OpenRouter
upstream, reading attribution, and launching Claude Code through the gateway. Every checkable
claim carries the command, the `file:line`, or the measurement date that makes it re-checkable.
Line numbers were verified against the checkout on 2026-08-23 and drift as the script changes;
re-grep the named function rather than trusting a stale line. `ccodex configure` and
`ccodex ocx configure` are the same route; the wrapper's own help calls `ccodex ocx <verb>` the
long form (`ccodex --help`, verified 2026-08-23). This document uses the long form throughout.

## The two planes

There are two configuration planes. Do not conflate them.

**The reviewed plane** is `ccodex ocx configure ...`. It admits a reviewed subset of the
upstream surface and fails closed on everything else
(`cmd_configure`, `scripts/opencodex-claude.sh:1909`). The admitted routes, from the case arm at
`scripts/opencodex-claude.sh:1930-1969`:

- Read-only inspection: `account list|current`, `provider list|show|presets|selected`,
  `models list|show`, `config show|get|validate`, and `help <verb>`. A bare `account`,
  `provider`, `models`, or `config` prints usage and mutates nothing
  (`scripts/opencodex-claude.sh:1935`).
- Reviewed mutations, non-Anthropic providers only: `login|logout <provider>`,
  `account login|reauth|code|cancel|use|remove|add-key|alias|rename`,
  `provider add|edit|update|remove|set-default`.
- `provider test <name>` is admitted as read-only reachability, but it makes a live call using
  that provider's stored credential (comment at `scripts/opencodex-claude.sh:1958-1960`).

`config set|unset|import|export`, `init`, `setup`, and `gui` are refused by name as
`unbounded-route` at exit 3 (`scripts/opencodex-claude.sh:1937-1939`; the `refuse` helper exits 3
at `scripts/opencodex-claude.sh:482-499`). Any unrecognized or new upstream route is also
refused at exit 3, with a message naming the admitted routes
(`refuse_unknown_route`, `scripts/opencodex-claude.sh:1885-1907`).

**The upstream plane** is the raw ocx CLI, reached as
`mise -C <checkout> exec -- ocx <args>` (the wrapper prints this form itself,
`scripts/opencodex-claude.sh:1922`). It is an operator-only escape hatch. An agent must not use
it without explicit operator authorization, with one narrow exception named under
"Read attribution" below. To inspect the upstream surface without running it:
`ccodex ocx configure help <verb>`.

## Onboard a provider

Order matters. The sequence below was measured in single contiguous runs on 2026-08-23, once in
a fresh container and once on this host.

1. `ccodex ensure` (gateway healthy, no Claude Code launch).
2. `ccodex ocx configure provider add <name> --adapter <adapter> --base-url <url> [--default-model <id>]`.
3. `ccodex restart` (operator approval required; it interrupts in-flight turns).
4. Pipe the key via stdin:

   ```sh
   grep '^KEY_NAME=' <envfile> | cut -d= -f2- | \
     ccodex ocx configure account add-key <name> --label <label>
   ```

**The restart is the publish step.** A `provider add` writes the config file only
(`ccodex ocx configure --help`, verified 2026-08-23). Measured 2026-08-23: the live catalog grew
7 to 420 ids (container) and 10 to 423 ids (host) only after `ccodex restart`. Running `add-key`
before the restart fails with "unknown provider" (measured 2026-08-23).

**Why step 4 is last.** `add-key` validates the provider against what the RUNNING gateway serves,
not against the config file, so before the restart it reports the provider as *unknown* rather than
as configured-but-unpublished — for a name `provider list` showed as configured one command earlier.
It also needs the gateway UP: against a stopped proxy it fails "Proxy not reachable" and persists
nothing. Both are upstream opencodex behavior, reproduced 2026-08-23 against the raw pinned binary
(`mise -C <checkout> exec -- ocx account add-key`), and neither ordering constraint appears in the
configure help, so the message is the only signal an operator gets and it names the wrong cause.

The wrapper prints `ocx sync` plus restart after a successful mutation and runs neither
(`scripts/opencodex-claude.sh:1976-1980`). Measured 2026-08-23: `ocx sync` was not needed for
gateway routing; restart alone published the provider. Sync concerns the Codex-integration half
and is catalog-only in opencodex 2.28.0 when that integration is off
(`ccodex ocx configure --help`; the same fact is in AGENTS.md's `ocx:configure` bullet). A sync
that would rewrite shared `~/.codex` still needs its own explicit approval.

Keys move only through pipes, never argv. Argv is readable by every process on the host via
`ps`, and the wrapper warns when it sees a credential-shaped flag
(`warn_argv_credential`, `scripts/opencodex-claude.sh:1860-1880`). A successful `add-key` echoes
a fingerprint id such as "added API key 58d4e3cd", never the value (measured 2026-08-23). A
credential path inside the repository is refused at exit 3 before the value is read
(`refuse_in_repo_credential_path`, `scripts/opencodex-claude.sh:1833-1856`).

## Verify the provider went live

**The silent misroute trap** (seed `agentic-sdlc-fa32`, in `.seeds/issues.jsonl`): a request
naming an un-onboarded provider prefix does not fail closed. The router classifies it
`routeKind: "default-provider"` and forwards it to the default provider, billed against the
wrong upstream. Observed error shape (measured 2026-08-23): "The 'openrouter/...' model is not
supported when using Codex with a ChatGPT account."

So confirm liveness before dispatching to a new provider:

- `ccodex status` ends with a terminal summary and reports restart-safety, configured-vs-live
  agreement, launch-route reachability, and the attribution stream command. Look for
  `configured vs LIVE catalog: ok` (verified 2026-08-23 on this host).
- `ccodex models` prints the flat live catalog, one id per line with a two-space indent. Count a
  provider's ids with `ccodex models | grep -c '^  <provider>/'` (413 openrouter ids on this
  host, 2026-08-23).
- `ccodex providers` shows configured providers and which are live.
- Health probe: `curl http://127.0.0.1:10100/v1/models` (default port 10100; returned 423 ids on
  this host, 2026-08-23). The config lives at `~/.opencodex/config.json` per `ccodex status`.

`ccodex restart` reports "Restart safety: AT RISK" when no background service is installed
(observed 2026-08-23 in `ccodex status`); the gateway still survives ordinary restarts.

## Prove a routed turn

A 200 is not proof the turn produced anything. qwen3.7-flash and the whole Muse Spark family
reason before answering, so a small completion budget returns HTTP 200 with
`finish_reason: length` and `content: null`. Give probe turns
`max_tokens`/`max_completion_tokens` of at least about 2048 (measured 2026-08-23: 32 fails,
2048 passes). Then verify identity from attribution, not from the request you sent; see
"Read attribution" below and `skills/dispatching-exact-ocx-models/SKILL.md` for the
receipt discipline.

## Pin an OpenRouter upstream provider

OpenRouter fronts multiple serving providers per model. A caller-supplied `provider` body field
does not reach OpenRouter: the openai-chat adapter copies only whitelisted fields, and
`provider` is not on the list (`CHAT_PASSTHROUGH_FIELDS`, opencodex 2.28.0
`src/adapters/openai-chat.ts:50-74`, read from the installed package on 2026-08-23).

The working mechanism is gateway config: `providers.openrouter.modelOpenRouterRouting`, a map
keyed by exact model id with `only`, `order`, and `allowFallbacks` fields
(`src/providers/openrouter-routing.ts:3,70-76`). The adapter injects it per request
(`src/adapters/openai-chat.ts:116-117`). It requires the openai-chat adapter and the canonical
`https://openrouter.ai/api/v1` baseUrl (`src/providers/openrouter-routing.ts:62-63`).

Live-proven 2026-08-23: pinning
`{"openai/gpt-oss-120b":{"only":["cerebras"],"allowFallbacks":false}}` plus a restart moved the
served provider from Amazon Bedrock to Cerebras; an unpinned control model (qwen) was
unaffected; `config unset` plus restart reverted to baseline.

**ccodex admits no route to set this today.** `config set` is refused as `unbounded-route`
(`scripts/opencodex-claude.sh:1937`). Seed `agentic-sdlc-c508` proposes a narrow reviewed route;
seed `agentic-sdlc-4518` records that the current refusal prints launch-route boilerplate that
does not match a configure refusal (the shared `refuse` text at
`scripts/opencodex-claude.sh:482-499` is written for launches). Both seeds are in
`.seeds/issues.jsonl`. The operator-only route, on the upstream plane and with explicit operator
authorization, is:

```sh
mise -C <checkout> exec -- ocx config set providers.openrouter.modelOpenRouterRouting '<json>'
ccodex restart
```

Revert with `config unset` plus restart.

## Read attribution

`ccodex` does not admit `ocx observe`; it exits 2 with "unknown ccodex ocx verb: observe"
(verified 2026-08-23). The attribution stream is:

```sh
mise -C <checkout> exec -- ocx observe logs --follow --jsonl
```

It shows per-request provider, model, and `routeKind`. This is the one upstream-plane command an
agent may run unaided, because it is read-only and `ccodex status` itself prints it as the
attribution stream (verified 2026-08-23). `routeKind: "default-provider"` means the router did
not recognize the target; treat it as an alarm, not a route
(`skills/dispatching-exact-ocx-models/SKILL.md`).

For OpenRouter pins there is a second witness: OpenRouter's response `provider` field passes
back to the client, so one turn reading `response.provider` verifies a pin
(measured 2026-08-23).

## Launch Claude Code through the gateway

AGENTS.md's `ocx:launch` bullet is the doctrine of record for the launch route; do not restate
it from memory. The operational facts an agent needs:

- `ccodex launch` refuses at exit 3 when a setting would silently defeat the route: a
  provider-routing switch such as an exported `CLAUDE_CODE_USE_BEDROCK`, an `apiKeyHelper`, an
  `sk-ant-api*` Console key, or a cloud-provider-shaped model id in an `ANTHROPIC_*` model slot
  (AGENTS.md, `ocx:launch` bullet). `ccodex status` reports the same detection without
  launching; on this host it showed "BYPASSED: CLAUDE_CODE_USE_BEDROCK is exported"
  (observed 2026-08-23).
- Scrub the environment for one launch instead of editing anything persistent:

  ```sh
  env -u CLAUDE_CODE_USE_BEDROCK -u AWS_BEARER_TOKEN_BEDROCK -u AWS_REGION ccodex launch
  ```

- An `sk-ant-oat*` subscription login is accepted (AGENTS.md, `ocx:launch` bullet).
- A healthy launch is not model-identity evidence. `ccodex status` ends by saying exactly that
  (verified 2026-08-23); identity comes from attribution.

`ccodex set-fast-model [<exact-id|->]` selects Claude Code's Haiku/background small-fast slot
from current Claude families or the live catalog; `-` clears; a completed selection is a
persistent operator mutation, while help and cancellation are not
(`ccodex set-fast-model --help`, verified 2026-08-23).

## Cheap test models

From the pricing survey measured 2026-08-23:

- `openrouter/qwen/qwen3.7-flash`: $0.03/M input, $0.13/M output. Cheap probe default.
- `muse/muse-spark-1.2-contributor`: $0.10/M input, $0.20/M output, direct at
  `api.meta.ai/v1` only; the contributor tier is not priced on OpenRouter.

Two cautions on the contributor id. The discount is a training-data grant: Meta trains on
prompts and completions sent to it, so never route repository content or anything sensitive
through the contributor tier without an explicit operator decision. And the muse provider's
`defaultModel` is the expensive `muse-spark-1.2` (`ccodex status` shows
`muse [custom] adapter=openai-responses model=muse-spark-1.2`, verified 2026-08-23), so name the
contributor id explicitly on every call. All three muse ids appear in the live catalog as
ordinary namespaced entries (`ccodex models | grep '^  muse/'`, verified 2026-08-23).

`ccodex ocx configure provider selected <name> [--set <model,model...>] [--clear]` curates a
provider's selected models. The bare form prints usage at exit 0 and mutates nothing
(verified 2026-08-23).

## Refusal map

Exit codes, from `ccodex --help` (verified 2026-08-23): 0 ok, 1 failure, 2 usage, 3 refused
before any effect, 4 admitted partial or unknown effect (`sdlc` lifecycle verbs only).

| Input | Result | Evidence |
|---|---|---|
| Unknown `ccodex ocx` verb (e.g. `observe`) | exit 2, "unknown ccodex ocx verb" | verified 2026-08-23 |
| `configure config set\|unset\|import\|export`, `init`, `setup`, `gui` | exit 3, `unbounded-route` | `scripts/opencodex-claude.sh:1937-1939` |
| Unknown configure route | exit 3, names the admitted routes | `scripts/opencodex-claude.sh:1885-1907` |
| Configure mutation naming an Anthropic provider or endpoint | exit 3 | `scripts/opencodex-claude.sh:1940-1968` |
| Credential or config path inside the repository | exit 3 | `scripts/opencodex-claude.sh:1833-1856` |
| `launch` with a route-defeating setting present | exit 3 | AGENTS.md `ocx:launch` bullet; `scripts/opencodex-claude.sh:482-499` |
| Request naming an un-onboarded provider prefix | NOT refused; misroutes to the default provider | seed `agentic-sdlc-fa32`, measured 2026-08-23 |

The last row is the dangerous one. Everything else fails closed; that one fails open onto the
wrong bill.

## Boundaries

**An agent may do unaided (read-only):** `ccodex status`, `ccodex providers`, `ccodex models`,
`ccodex version`, any `--help`, the configure inspection routes (`provider
list|show|presets|selected`, `account list|current`, `models list|show`,
`config show|get|validate`), the `curl` health probe, and the attribution stream
(`ocx observe logs`, the one sanctioned upstream-plane read).

**Needs explicit operator approval, each operation separately:** every configure mutation
(`provider add|edit|update|remove|set-default`, `login|logout`, any `account` mutation including
`add-key`), `provider test` (it spends a live call on the stored credential), `ccodex restart`,
`ocx sync`, a completed `set-fast-model` selection, launching Claude Code, and any other
upstream-plane `ocx` invocation, including `config set` for pins. A gate or a healthy status is
evidence, never authorization.

**Never done:** printing or echoing a key value (pipe via stdin; the wrapper never prints secret
argv, `scripts/opencodex-claude.sh:1912`), passing a credential on argv when a stdin route
exists, storing a credential under the repository tree, hand-editing
`~/.opencodex/config.json`, or claiming model identity from a healthy launch or a request-side
model name.
