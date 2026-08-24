# Fresh-host install verification — Docker, from the public remote, with live credentials

- **Date:** 2026-08-08
- **Status:** executed. 32 of 33 scripted assertions passed on the first run; the one failure was
  a defect in the test, not the product. Two real product defects were found afterwards, by
  pushing past the scripted assertions into the muse gateway path. Defect 1 (`jq`) is fixed and
  regression-tested in the same change as this record; defect 2 is a documentation gap, closed by
  the sequence written below.
- **Host:** `ubuntu:24.04` container, non-root `ubuntu` user, nothing pre-installed but
  `curl`, `git`, `ca-certificates`, then mise and a fresh Claude Code.
- **Commit under test:** `6551020`, cloned from `https://github.com/Codeseys-Labs/agentic-sdlc.git`
  over the public network — not a bind-mount of the working tree, so this exercises what a
  stranger gets.
- **Credentials:** real Bedrock bearer token and real muse API key, supplied at run time through
  a mode-600 `--env-file` outside the repository. Neither is baked into the image, written into
  the tree, or echoed by any assertion.

## What this verifies, and what it does not

Verified: the documented install path works from nothing on a host that has never seen this
bundle; the operator PATH plane (`ccodex`) works without mise; the 2026-08-07 help fix holds on
a fresh install; the Bedrock credential reaches a real Anthropic model on the native plane; the
muse credential reaches muse through the gateway with correct attribution; and both planes serve
on the same host at the same time.

Not verified: native Windows or macOS, the interactive TTY paths (every model call here is
`--print`), long-run stability, or anything about the Seeds bootstrap, which this run does not
exercise. A green run is evidence, never authorization for an outward effect.

## The install path that works

Every command below was executed in the order shown. Steps 1–6 are the whole install; steps 7+
are the muse gateway provider, which is optional and is where both defects live.

```bash
# 0. prerequisites: mise, and Claude Code if you want the native plane too.
curl -fsSL https://mise.run | sh
curl -fsSL https://claude.ai/install.sh | bash

# 1. clone.
git clone https://github.com/Codeseys-Labs/agentic-sdlc.git && cd agentic-sdlc

# 2. review mise.toml and mise.lock, then trust THAT EXACT PATH.
#    Skipping this makes every later mise command exit 'config files are not trusted'.
mise trust ./mise.toml

# 3. resolve the pinned toolchain (~1.3 GB, 13 tools, about 30s on a warm network).
mise --locked install

# 4. install the bundle (skills, agents, commands, both host planes).
mise run bundle:install
mise run bundle:status          # expect: '38 ok, 0 conflict, 0 absent'

# 5. install the operator PATH plane (ccodex and friends).
mise run operator-tools:install

# 6. confirm it works WITHOUT mise on PATH -- that is the point of the plane.
ccodex --help
```

Measured results on the fresh host:

| step | result |
| --- | --- |
| mise | `2026.8.3 linux-x64` |
| Claude Code | `2.1.226` |
| `mise --locked install` | ok; `uv 0.11.17`, `node v22.22.3`, `npm 10.8.1`, `bun 1.3.10`, `ocx 2.10.2` |
| `bundle:status` | `38 ok, 0 conflict, 0 absent` |
| installed surface | 10 skills, 7 agents, 4 commands |
| `operator-tools:install` | historical result: `ccodex`, `ocx-launch`, `ocx-ultracode`, `agentic-sdlc-statusline`; ADR-0010's 2026-08-10 amendment makes fresh installs `ccodex` + `agentic-sdlc-statusline` only |
| `claude plugin validate ./plugin` | `✔ Validation passed` |
| `mise run validate` | green |

Two facts worth keeping because they are easy to get wrong. **`uv` must stay reachable on the
operator's PATH** even though mise need not: the dispatcher's Python entrypoints run through it.
And **the untrusted-config refusal was asserted positively** — `mise run check` before
`mise trust` does refuse by name, so the trust step is load-bearing rather than ceremonial.

## Credential verification

**Bedrock, native plane.** `claude -p 'Reply with exactly: BEDROCK_OK' --model
global.anthropic.claude-opus-5[1m]` returned `BEDROCK_OK`. The token travels in the environment
only; nothing was written into the tree.

**muse, direct.** Both APIs answered `MUSE_OK` with `finish_reason: "stop"`:

- `POST /chat/completions` — 176 completion tokens, **163 of them reasoning**
- `POST /responses` — the operator's stated primary; the response carries
  `reasoning: {"effort": "high"}`

**A budget hazard that will bite anyone who tests this the obvious way.** The first scripted
assertion FAILED with `max_tokens: 16`: the model spent all 16 on reasoning, returned
`content: null` with `finish_reason: "length"`, and the assertion read that as a broken
credential. It was not — the token was fine and the request was billed. **muse-spark-1.2 is a
reasoning model; a token budget that would be generous for a two-word answer from a
non-reasoning model returns null content instead.** Size `max_tokens` / `max_output_tokens` for
the reasoning trace, not for the visible answer. 512 was ample for a 2-token reply.

**muse, through the gateway.** The end state, from the attribution log, which is the only
admissible proof that a model served a request (the response body's `model` field is not):

```json
{"provider":"muse","model":"muse-spark-1.2","requestedModel":"muse/muse-spark-1.2",
 "resolvedModel":"muse-spark-1.2","status":200,"usageStatus":"reported",
 "routeDecision":{"routeKind":"explicit-provider"}}
```

`routeKind: "explicit-provider"` is the load-bearing field: it proves the request did **not**
fall through to the default provider, which is the C1 fail-open hazard this bundle warns about.
`ccodex launch -- --print --model muse/muse-spark-1.2 "..."` printed `GATEWAY_MUSE_OK`.

**Both planes at once.** In the same container, on the same host: muse served a gateway-routed
turn while `claude -p` served a Bedrock turn natively. The planes coexist, as ADR-0003 requires.

## Defect 1 — `jq` was an undeclared runtime dependency of the configure classifier (FIXED)

`scripts/opencodex-claude.sh:975` requires `jq` and returns "unclassifiable" without it:

```bash
config="$(ocx config show --json 2>/dev/null)" || return 2
command -v jq >/dev/null 2>&1 || return 2
```

`configured_provider_class` returning 2 makes `provider_allowed_for_mutation` return 1, which
makes every configure mutation refuse with `anthropic-or-unclassifiable-provider`. On the fresh
host, `ccodex configure account add-key muse` was refused **even though muse was already
configured as a non-Anthropic provider with an `api.meta.ai` base URL.**

`jq` *is* pinned — `mise.toml:34`, `jq = "1.8.2"` — so it is present under `mise exec`. But
`ccodex` is explicitly designed to run **without mise on PATH**, and there `jq` is simply absent.
The two designs contradict each other, and the symptom is a refusal that names the wrong cause:
an operator reads "anthropic-or-unclassifiable-provider" and goes looking at their provider
config, which is correct.

Proven by a controlled A/B on one container, same command, only PATH differing:

| PATH | result |
| --- | --- |
| `~/.local/bin:/usr/bin:/bin` (fresh-host default) | `REFUSED (anthropic-or-unclassifiable-provider)` |
| same, plus `dirname $(mise which jq)` | `about to run an approved opencodex configuration route (account add-key)` |

Severity: this silently blocked every `configure` mutation on a correct fresh install, and the
message misdirected. A fail-closed refusal is right when classification genuinely cannot be done;
reporting a *missing tool* as an *unclassifiable provider* is not.

**Fixed in this run.** `jq` is now resolved exactly the way `ocx` already was — through a shell
function that prefers a PATH `jq` and falls back to `mise -C "$root" exec -- jq`. Every
`configure` route already calls `require_ocx`, which requires mise, so the pinned copy is
reachable wherever classification runs. Two details that matter:

- The resolver probes with `type -P jq`, not `command -v jq`. A shell function named `jq` would
  find *itself* through `command -v` and recurse — the same shadowing mechanic that let a stale
  `ccodex` shell function hide the installed binary on the operator's own host the day before.
- `configured_provider_class` now returns a distinct status 4 for no-jq, and
  `provider_allowed_for_mutation` routes it to a `refuse_missing_jq` that names the tool, the
  pin, and the fix. Collapsing it into the existing "cannot classify" status 2 is what produced
  the misdirecting message; a missing tool and an unreadable config need different sentences.

Verified in the same fresh container, on a PATH with no `jq`: the exact command that was refused
now prints `about to run an approved opencodex configuration route (account add-key)` and the key
persists (`apiKey: <set, 48 chars>`). With mise *also* absent, `require_ocx` catches it first with
its own accurate message, so `refuse_missing_jq` is correctly unreachable in that case.

> **The PATH-first half of that resolver was superseded on 2026-08-21 (seed `agentic-sdlc-6f9d`).**
> Preferring an ambient `jq` over the pin is the substitution ADR-0020 forbids, and this `jq`
> classifies settings documents that decide refusals: `scripts/opencodex-claude.sh` now resolves
> `$AGENTIC_SDLC_JQ` — admitted only as an absolute path or the literal pinned sentinel — and then
> the pinned `mise -C "$root" exec -- jq`. The `type -P` detail above is therefore historical: no
> **jq** NAME is looked up any more, which closes the same recursion hazard by construction, and a
> bare or relative binding is refused rather than resolved. **Residual, stated rather than hidden:**
> the pinned route locates `mise` itself on ambient PATH, because mise is this repository's
> documented sole bootstrap prerequisite and is not itself pinned — a substituted `mise` therefore
> still governs this parse, exactly as it governs `ocx()` and `launch_ocx_claude`. The status-4 /
> `refuse_missing_jq` half of this entry stands, with its message rewritten to name the two
> admitted routes instead of a PATH copy.

**Why the suite never caught it, which is the more transferable finding.**
`tests/test_opencodex_claude.py:107-109` symlinks the *host's* `jq` into the stub bin dir, so
every test in the file ran with `jq` present. The suite agreed with the developer's machine and
disagreed with a fresh install — the same class as the earlier `PATH`-reading tests recorded in
`host-dependent-tests-hide-clean-machine-failures`. Three regression tests now delete the stub
`jq` **and** narrow `PATH` to the stub dir alone, because a first attempt that only deleted the
symlink still found `/usr/bin/jq` through the harness's trailing `/usr/bin:/bin` and passed
against the unfixed launcher. Discrimination was then proven by execution rather than assumed:
the tests **fail** against the reverted launcher and **pass** against the fixed one.

## Defect 2 — the muse setup sequence is longer than documented, and the wrong order fails silently

Three separate things had to be true, and none is currently written down together:

1. **`ocx provider add` accepts no key at all.** It has no `--api-key`, and it does not read
   stdin. A key piped to it vanishes with a success message: the provider lands with
   `["adapter","baseUrl","defaultModel"]` and no `apiKey`. Every later request 401s with
   `errorCode: "invalid_api_key"` while the route itself is correct — the most confusing possible
   failure, because routing looks right in the log.
2. **The key goes in through `ocx account add-key <provider>`,** whose own help says "Add a key
   read only from piped stdin". This is the right shape (argv is world-readable via `ps`), but it
   is a *different verb* from the one that creates the provider.
3. **`account add-key` needs the gateway already running.** Against a stopped gateway it prints
   `Proxy not reachable` and persists nothing.

The working order, verified end to end:

```bash
ccodex configure provider add muse --adapter openai-responses \
  --base-url https://api.meta.ai/v1 --default-model muse-spark-1.2   # shape only
mise exec -- ocx ensure                                              # gateway UP first
printf '%s' "$MUSE_API_KEY" | ccodex configure account add-key muse --label <label>
ccodex restart                                                       # key into the routing table
ccodex launch --model muse/muse-spark-1.2
```

After step 3 the provider carries `["adapter","baseUrl","defaultModel","apiKeyPool","apiKey"]`.

> **The ORDER above was superseded on 2026-08-23 (seed `agentic-sdlc-d353`). Do not copy it.**
> `account add-key` validates the provider against what the RUNNING gateway serves rather than
> against the config file, so a key stored between the `provider add` and a restart fails
> `Error: unknown provider` — measured 2026-08-23 in one clean container, and reproduced against
> the raw pinned binary, so it is upstream behavior rather than the wrapper's. The order that holds
> either way is `ccodex ensure`, `provider add`, `ccodex restart`, then `add-key`; the restart is
> the publish step, and the same run took the live catalog from 7 ids serving none of the new
> provider to 420 serving 413 of it with `ocx sync` never run at all. The sequence above worked
> because its `ensure` came AFTER the provider add and started a gateway that was down — a cold
> start rather than a stale one. Finding 3 above stands unchanged: the gateway must also be up.

## Two upstream observations, neither a defect in this bundle

**`ocx sync` requires Codex installed.** On a host with no `~/.codex/config.toml` it reports
`Codex config not found ... Is Codex installed?` and does not complete. The gateway still starts
and still routes, so this does not block the gateway plane — but the "NOT LIVE YET" notice this
bundle prints after a provider mutation names `ocx sync` as a required step, and on a fresh host
that step cannot succeed. The notice should say so, or name the restart-only path.

**ocx's model discovery does not send the provider key.** `ocx ensure` logs
`Provider model discovery for "muse" failed with HTTP 401 [urlClass=provider-models,
fallback=configured]`. The endpoint and key are both fine: `GET https://api.meta.ai/v1/models`
returns 200 with that key and lists three models. The decisive control is that the **same 401 is
returned when the request is sent with no Authorization header at all** — so this is ocx not
forwarding the credential on the discovery probe. The `fallback=configured` behavior is correct
and harmless: muse still appears in the live catalog as `muse-spark-1.2`.

## Reproducing this

Image and script live outside the repository, in `/tmp/asdlc-docker-test/` on the machine that
ran it, because the credential file must never be near a tracked tree. The image is 5 lines of
`apt-get` plus the two vendor install scripts; the verification script is ~150 lines of
`assert_contains` / `assert_absent` over the commands above.

**The one methodological rule that matters here, learned the hard way twice in this project:**
every assertion reads **output**, never a bare exit code. On any path that ends in a `claude`
process, `exit 0` cannot distinguish "printed usage" from "launched Claude Code, which exited
cleanly" — which is exactly how a side-effecting `--help` passed a verification pass on
2026-08-06. The side-effect assertions here are negative and specific: the string
`preparing gateway-routed Claude Code` must be **absent** from every help form, and present in
`ccodex launch -- --help`.

The same discipline caught a mistake in this run's own reporting: a composite
`cmd; ls <missing-glob>` reported exit 2 and was briefly read as `ccodex session adopt` failing.
`adopt` exits 0. A compound command's exit status belongs to its last element, not to its
subject.

## Conclusion

The documented install path is correct and complete as written, on a fresh host, from the public
remote, for both the bundle and the operator PATH plane. Both live credentials work. The muse
gateway path works but needs two more documented steps than currently stated, and one launcher
defect (`jq`) must be fixed before `configure` mutations are reliable on a host that follows the
bundle's own no-mise-required promise.

This record is evidence for a conductor to cite. It authorizes no push, publication, merge,
deployment, or credential operation.
