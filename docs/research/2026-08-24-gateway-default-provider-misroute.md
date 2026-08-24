# The gateway silently misroutes an unserved provider prefix to the default provider

**Date:** 2026-08-24
**Subject:** opencodex `2.28.0` (`npm:@bitkyc08/opencodex`), router provider-prefix resolution
**Seed:** `agentic-sdlc-fa32`
**Status:** upstream-facing defect report. Nothing here has been filed, sent, or published. It is
written for the operator to forward to the opencodex maintainer at their discretion.

## Summary

A request whose model id carries a `<provider>/` prefix that the running gateway does not serve is
not refused. The router computes the prefix, tests it against the configured providers, discards the
failed result, and falls through to the default provider with the caller's model string forwarded
**verbatim** — prefix included — tagged `routeKind: "default-provider"`. The credential precondition
runs strictly afterwards and belongs to the already-selected provider, so on a host whose default
provider is credentialed the request is attempted and **billed against an account the caller never
named**, while the attribution record shows the selected provider rather than the requested one.

The honest behavior is a 4xx naming the unknown prefix. The minimal change is an `else` on one
existing branch.

## Mechanism, with citations

Verified by reading the installed bytes. The package ships readable TypeScript under `src/` with no
sourcemaps and no build step for that tree (`package.json` `exports` points Bun at `./src/index.ts`),
so these paths and line numbers correspond directly to the upstream tree.

### 1. The prefix branch discards its own negative result

`src/router.ts`, in `routeModelInternal` (declared `src/router.ts:541`):

```ts
  // 0. Explicit "<provider>/<model>" namespace (e.g. "opencode-go/deepseek-v4-pro").
  //    Only triggers when the prefix matches a CONFIGURED provider, so genuine
  //    slash-containing model ids (e.g. "anthropic/claude-...") fall through when
  //    no such provider exists.
  if (slash > 0) {                                                    // :625
    const provName = modelId.slice(0, slash);                         // :626
    if (provName === LEGACY_CHATGPT_PROVIDER_ID || provName === LEGACY_OPENAI_MULTI_PROVIDER_ID) {
      throw new Error(`No provider configured for model: ${modelId}`);  // :628
    }
    if (hasOwnProvider(config.providers, provName)) {                  // :630
      /* ... routes to provName ... */
    }                                                                 // :649
  }                                                                   // :650
```

`provName` is computed at `:626`, tested at `:630`, and when that test fails the negative result is
silently dropped: the `if` at `:630` has no `else`, and `provName` leaves scope at `:650` without
being referenced again.

Two details make this a defect rather than a design choice. First, the *pattern* of refusing a
named-but-unusable prefix already exists five lines above at `:627-629`, where two legacy provider
ids throw by name — it is simply not applied to the general case. Second, the comment at `:621-624`
documents the fallthrough as serving slash-bearing *native* ids (an OpenRouter `anthropic/claude-…`
referenced without its provider prefix). That is a real case and it is addressed below, but the
current code cannot distinguish it from a typo or from configuration drift, so it treats both as the
former.

### 2. The fallthrough compares nothing

```ts
  if (hasOwnProvider(config.providers, config.defaultProvider)) {                       // :682
    const defaultProv = config.providers[config.defaultProvider];
    if (defaultProv.disabled === true) throw new Error(`Default provider is disabled: ...`);
    return routeResult(config.defaultProvider, defaultProv, modelId, "default-provider", "default-provider");  // :685
  }
```

Between the failed `hasOwnProvider` at `:630` and this return at `:685`, the requested provider name
is never compared to the selected one. The only guards here are whether the default provider is the
legacy ChatGPT id and whether it is configured and enabled — **neither is a function of the requested
model string.**

The third argument at `:685` is `modelId`, the *full* original id including the unmatched prefix, not
`modelId.slice(slash + 1)`. `routeResult` copies it into `RouteResult.modelId`, which is what the
adapter puts on the wire. So `zzz-totally-unconfigured-provider/some-model` reaches the default
provider with the bogus prefix still attached.

### 3. Attribution records the wrong provider

The trace is built from the selected provider (`src/router.ts:701-717`, `selected: { provider:
route.providerName, … }`) and `logCtx.provider = route.providerName`
(`src/server/chat-completions.ts:120`). The requested string survives only as `requestedModel`. So
the record shows which provider was *chosen*, with no signal that the caller named a different one —
`routeKind: "default-provider"` is the only hint, and it is indistinguishable from a legitimate
default-provider selection.

### 4. Provider selection strictly precedes the credential check

This is why the failure text names the wrong provider. The route is settled at
`src/server/chat-completions.ts:116` (`routeModel(config, requestedModel, …)`); the credential is
resolved later by `resolveCodexAuthContext` (`src/codex/auth-context.ts:315`, called from
`src/server/responses/core.ts:1186` and `:640`), and every call site passes
`route.codexAccountMode` — the already-selected provider's account mode. The observed
`401 OpenAI account pool has no usable account credential` is the default message of
`CodexPoolAuthenticationError` (`src/codex/auth-context.ts:116-120`), thrown with no argument at
`:405-408`.

A request for `claude-sonnet-5` on a host with no Anthropic provider configured therefore traces:
bare id, no prefix branch; not a bare OpenAI family id (`src/router.ts:479-482`);
`routeByKnownModelPattern` matches the `claude-sonnet-` pattern but finds no `anthropic*` provider
and deliberately does not fall back (`src/router.ts:726-744`); falls to `:685` and is bound to the
OpenAI default; only then is a credential sought, and the 401 names OpenAI.

**That 401 is evidence of the defect, not a separate bug.** On a host whose default provider *is*
credentialed, the identical path bills silently instead of erroring.

## Live evidence

Measured on the reporting host, not inferred from a fixture:

- **Three requests inside the last seven days** classified `routeKind: "default-provider"` in the
  local gateway store. Reproduce with `mise run usage:report` and read the `misroutes` line:
  `misroutes: 3 default-provider rows`. The reporter is advisory and exits 0; it counts these
  rows, it does not gate on them.
- The mechanism was independently observed in fresh containers on 2026-08-23 (seed
  `agentic-sdlc-fa32`): a dispatch of `zzz-totally-unconfigured-provider/some-model` produced
  `routeDecision: {"routeKind":"default-provider","selected":{"provider":"openrouter","model":"zzz-totally-unconfigured-provider/some-model","reason":"default-provider"}}`
  — the garbage string forwarded verbatim as the model parameter, tagged `default-provider`.

**Not proven end to end, stated plainly:** no run here forced a real upstream `200` on a misrouted
request, because three attempts to credential a provider in-container failed. Every observed
misroute failed at the *default provider's* credential check. The `routeDecision` JSON and the source
above are direct evidence of the routing mechanism; the silent-success outcome is an inference from
that mechanism plus the ordering in §4, and this report does not claim it was observed.

## Why fail-open is the wrong default here

1. **The cost is a charge on an account the caller never named.** This is not a degraded answer or a
   slower path; it is money moving to the wrong upstream. That is the one failure class where a
   caller cannot self-correct after the fact, because the request has already been served.
2. **The signal that something went wrong is absent at the moment it would be useful.** The caller
   receives a normal completion. `routeKind: "default-provider"` appears only in the attribution log,
   afterwards, and is indistinguishable from an intentional default selection.
3. **Configuration drift reaches this path routinely, not just typos.** A provider written to
   `config.json` is not in the running gateway's routing table until a sync and a restart. In that
   window every request naming it is misrouted and billed elsewhere. The condition is invisible to
   the caller and produces no warning.
4. **The existing throws prove refusal is in-model.** `src/router.ts:627-629` and `:688` already
   throw `No provider configured for model: …`. Reaching the same error for the general unmatched
   prefix is consistent with the file's own behavior, not a new policy.

The honest alternative is a 4xx naming the unknown prefix, and **the surface for it already exists
and already expects this exact case.** `routeModel` is called inside a `try` at
`src/server/chat-completions.ts:116`, and the `catch` at `:136-142` handles a routing throw two ways:
`NoEligiblePolicyCandidateError` becomes a `404 invalid_request_error` with the trace attached
(`:137-141`), and anything else falls to a bare comment —

```ts
    /* unknown model: let handleResponses shape the 404 */          // :141
```

So a throw added at the unmatched-prefix branch needs no new error plumbing: it lands in a catch
already written for an unknown model and already resolving to a 404.

## No existing configuration knob makes this fail closed

Checked and negative, so this cannot be deflected to configuration:

- `allowUnknownModel`, `requireExactProvider`, `requireProviderPrefix`, `disableDefaultProvider`,
  `rejectUnknown` as a routing concept: zero hits across `src/`. (`allowFallbacks` in
  `src/types/provider.ts:17` is OpenRouter's own upstream API field; `rejectUnknownArgs` in
  `src/cli/provider.ts:41` is CLI argument parsing.)
- `strict` does occur in `src/` (roughly 210 occurrences), but **not once in `src/router.ts`**, and
  every occurrence elsewhere is zod schema strictness (`.strict()` on config and provider schemas),
  a strict JSON/byte parser (`parseStrictPublicJson`, `decodeStrict`,
  `ensureStrictCatalogFields`), an OpenAI structured-output `strict` field, or prose. None governs
  provider or model resolution. This is stated as a scoped negative rather than a keyword count,
  because the count alone is misleading.
- No `OCX_*` / `OPENCODEX_*` environment variable affects routing or model resolution.
- **Unsetting `defaultProvider` is not an escape hatch.** `src/config.ts:1261` declares it
  `z.string().min(1).default("openai")`, and a `superRefine` at `:1582-1587` raises
  `defaultProvider must exist in providers`. That issue's path is the single segment
  `["defaultProvider"]`, which `salvageConfigCandidate` does not salvage, so `loadConfig()` falls
  back to `getDefaultConfig()` wholesale (`:2261-2262`) and restores `defaultProvider: "openai"`.
  Any config that loads has a `defaultProvider` satisfying `hasOwnProvider` — which makes the throw
  at `:688` unreachable defensive code rather than a reachable control.
- Routing profiles can fail closed (`NoEligiblePolicyCandidateError`, `src/router.ts:47-56`, thrown
  at `:564-566`) but only for a literal `policy/<id>` or an exact configured alias
  (`src/routing/profile.ts:122-136`). They have no notion of an unrecognized prefix.

## Minimal upstream change

Add the missing `else` to the `hasOwnProvider` test at `src/router.ts:630` — equivalently, a guarded
refusal before the block closes at `:650` — mirroring the shape already at `:627-629`, and return a
4xx naming the prefix.

### What must keep working

**Bare, un-prefixed ids are already structurally separate and a check scoped to `slash > 0` cannot
touch them.** Every legitimate bare case is handled after the block closes: bare OpenAI family
(`:652-658`), configured `defaultModel` (`:660-665`), vendor patterns serving `claude-*`
(`routeByKnownModelPattern`, `:667-668`), and the static models list (`:670-677`).

Four slash-bearing cases legitimately survive line 650 today. Three are safe because they resolve
**before** the prefix branch, which is the load-bearing ordering fact for this fix:

| Case | Resolved at | Safe? |
| --- | --- | --- |
| Routing-profile alias (`policy/…`) | `src/router.ts:555` | Yes — before `:625`. `aliasIssues` (`src/routing/profile.ts:176-181`) already rejects an alias whose prefix collides with a configured provider. |
| Combo alias (one optional `/` segment, `src/combos/types.ts:27`) | `src/router.ts:610-619` | Yes — before `:625`. |
| Anthropic native passthrough (`/^(claude\|anthropic)/i` with an `sk-ant-` credential) | `src/server/claude-messages.ts:646`, before `routeModel` at `:683` | Yes — never reaches the router. |
| `claudeCode.modelMap` / Claude aliases | `resolveInboundModel`, `src/claude/inbound.ts:59-88` | Yes — keys are caller-facing model ids, not provider prefixes, and a `native/` prefix is stripped at `:70-73`. |

The fourth is the real hazard and deserves the maintainer's attention:

**A native slash-bearing id referenced without a provider prefix** — the case the comment at
`:621-624` names, e.g. OpenRouter's `anthropic/claude-…` on a host with no `anthropic` provider. It
must reach the `prov.models` scan at `:670-677` to be resolved. **There is already a gap here:** that
loop reads only `prov.models` (static config), whereas `knownModelIdsForProvider` (`:97-127`) is the
union of static config, registry seeds, hint-map keys, the live `/models` cache, and `customModels`.
A **live-discovered** slash id referenced bare therefore already falls through to the default
provider today.

So the recommended form of the fix is not a bare `throw`: **have the new check consult
`knownModelIdsForProvider` across the active providers (or widen the `:670-677` scan to it) before
refusing.** That closes the reported defect and this adjacent gap together, and it avoids converting
a working live-discovery selection on a cold cache into a hard refusal — which is the objection a
naive `else` would rightly attract.

## A secondary finding: `/v1/models` does not let a caller determine a row's provider

This is worth fixing on its own, and it is also why caller-side mitigation is hard enough that it
cannot substitute for the router change.

`GET /v1/models` is the only catalog surface a credential-less local caller can read —
`/api/models` and `/api/catalog` sit behind `requireManagementAuth` (`src/server/index.ts:887`) and
need the admin token. But its rows carry no usable provider identity:

- There is **no `provider` field**. Rows are `{ id, object, created, owned_by, … }`
  (`src/server/index.ts:1078-1119`).
- **`owned_by` is the upstream vendor, not the gateway provider.** Measured on the reporting host,
  the `owned_by` set is `meta`, `openai`, `openrouter` — a provider configured as `muse` reports
  `meta`. And for native rows `owned_by` is the hardcoded literal `"openai"`
  (`nativeModelRow`), whatever the default provider is actually named.
- The provider is therefore only recoverable by **string-splitting `id` on the first slash** — and
  that fails for the default provider, which serves **bare** ids and so appears under no
  `<provider>/` prefix at all. On the reporting host the catalog's prefix set is `{muse,
  openrouter}` while the configured providers are `{openai, muse, openrouter}`; `openai` is the
  default and is invisible.
- The two catalog surfaces also **disagree on id spelling**: `/v1/models` emits the raw
  `${m.provider}/${m.id}` (`src/codex/catalog/aggregation.ts:419`), which is two slashes when the
  native id contains one — `openrouter/~anthropic/claude-fable-latest` — whereas `/api/models`
  emits the one-slash dash-encoded `namespaced` form via `catalogModelSlug`
  (`src/codex/catalog/parsing.ts:600-602`). A caller validating against one and sending the other
  takes a different router path.

Adding a `provider` field to `/v1/models` rows would make a caller-side preflight straightforward.
As it stands, a correct preflight has to special-case the default provider from a *different*
source (the config file), which is exactly what this bundle ended up doing.

## What this bundle changed on its own side

Upstream owns the router; this repository owns whether its own wrappers hand the router an id it will
misroute. `ccodex launch --model <id>` (and `ultracode`, which shares the path) now refuses before
dispatch when a namespaced id's prefix is absent from the running gateway's `GET /v1/models`,
distinguishing an unknown prefix from a configured-but-unpublished one and naming the publish step
for the latter. Bare ids, exact catalog ids, `policy/<id>`, and the default provider's own name are
never refused. An unreadable catalog is a refusal rather than a pass, because a check that could not
run has established nothing. `ccodex set-fast-model <id>` carries the same rule with a weaker
contract — an unserved prefix refuses, an unreadable catalog warns and still writes — because
configuring that slot with the gateway down is a legitimate flow.

Two limits of that mitigation are worth stating to the maintainer, because they are properties of the
gateway rather than of the wrapper:

1. **It cannot run before the gateway is up.** The launcher's other billing-honesty refusals all run
   *before* it starts a proxy, so a refused launch leaves nothing behind. This one cannot: its whole
   subject is what the running gateway serves.
2. **It needs the config file to identify the default provider**, per the secondary finding above,
   which reintroduces exactly the config-versus-running-process gap that causes the unpublished-
   provider case in the first place. A default changed in the config but not yet loaded is admitted
   by a name the running process does not have.

So this is a caller-side mitigation on two surfaces, not a fix. It protects no other client of the
gateway, and it cannot: only the router can make this fail closed for everyone.
