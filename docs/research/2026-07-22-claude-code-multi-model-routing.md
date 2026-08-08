# Claude Code multi-model routing

Status: design reference, researched 2026-07-22 — **PARTIALLY SUPERSEDED** by
`2026-08-05-gateway-selection-memo.md` (read it first).

**Name-reuse note (2026-08-07).** The `ccodex` command name used by the design below now names
this bundle's operator dispatcher for the opencodex gateway plane — see
`docs/adr/0010-gateway-plane-inherits-inert-session-data-and-the-statusline-stanza.md`
(Amendment C). **Only the name is reused. The subscription-passthrough premise described in this
document was not adopted**; ADR-0003 declared it ToS-blocked, and the retired implementation's
state and cache were removed before the name was claimed. Do not read the shipped `ccodex` as an
implementation of anything below.

What the newer memo supersedes here, and why:

- **Gateway choice.** This document names CLIProxyAPI the preferred lightweight
  local gateway. The 2026-08-05 memo's cloned-source review found CLIProxyAPI
  extracts, stores, and replays the user's claude.ai OAuth token rather than
  passing it through, and ships default-on client-identity disguise
  (`cloak.mode: auto`). The adopted gateway candidate is opencodex; CLIProxyAPI
  is a documented fallback only.
- **Authentication framing.** This document treats subscription-OAuth-through-a-
  proxy as "experimental, requires operator approval." The newer memo's addendum
  records that Anthropic's terms scope subscription OAuth exclusively to native
  Anthropic applications and do not permit routing plan credentials through
  third parties. That is a stated policy prohibition, not an operator-approvable
  risk tier.

The supersession is scoped to those two areas. The launcher/profile design
(`ccodex`), the route-registry schema, the context-class and compaction
material, the Dynamic Workflow inheritance rules, and the qualification
checklist below stand as design reference. This record is provenance from the
pre-divergence remote line (commit 532e984), retargeted here because it is a
dated design memo, not installed skill content. It authorizes nothing.

Use this reference when a mission mixes Claude, OpenAI, Bedrock, or other
providers through Claude Code Dynamic Workflows. It defines where model choice,
authentication, context limits, compaction, fast modes, and workflow isolation
belong. It also records the decision boundary between CLIProxyAPI, LiteLLM, and a
thin `ccodex` launcher.

This is an integration design, not a claim that every route named below has been
qualified. Provider behavior, subscription terms, and model limits drift. A route
must pass the qualification checks in this document before production use.

## Executive decision

Use three distinct layers:

1. **Claude Code Dynamic Workflows** decide which model performs each phase or
   agent and which agents receive worktrees.
2. **CLIProxyAPI** is the preferred lightweight local gateway for protocol
   translation, supported OAuth/API accounts, aliases, load balancing, and request
   shaping.
3. **`ccodex`** should be a thin, profile-aware launcher for the real `claude`
   executable. It selects a provider/authentication/context-policy envelope,
   validates it, prepares an isolated Claude configuration directory, and then
   launches Claude Code.

Do not make CLIProxyAPI the source of truth for Claude Code's context management.
The proxy can select routes and transform payloads, but Claude Code owns the active
conversation, its context estimate, and automatic compaction. Conversely, do not
make a Dynamic Workflow responsible for provider credentials or process-wide
compaction settings: workflows do not expose those as per-agent fields.

The resulting boundary is:

```text
model registry
  |-- generates --> CLIProxyAPI aliases and payload policy
  |-- generates --> ccodex launch profiles
  `-- validates ---> workflow model references

ccodex profile
  |-- provider, endpoint, auth reference
  |-- default model
  |-- admitted context and compaction envelope
  |-- fast/priority eligibility
  `-- isolated CLAUDE_CONFIG_DIR
          |
          v
     one Claude Code process
          |
          `-- Dynamic Workflow
                |-- phase/agent model IDs
                |-- worktree choices
                `-- fresh or forked agent contexts
```

The unit of process isolation is the **provider/auth/context-policy envelope**, not
the individual model. Models that safely share an envelope should remain in one
process and use Dynamic Workflow model selection. Start another Claude Code process
only when provider authentication, base URL, terms, or context/compaction policy
cannot safely be shared.

## CLIProxyAPI versus LiteLLM

Both can present model endpoints, but they optimize for different jobs.

| Concern | CLIProxyAPI | LiteLLM Proxy and management CLI |
|---|---|---|
| Best fit | Local, developer-controlled multi-account bridge | Organization-wide model gateway and control plane |
| Primary strength | OAuth/API account support, protocol compatibility, aliases, exclusions, load balancing, request shaping | Central model and credential management, virtual keys, users, teams, budgets, and governance |
| Local setup | Smaller and closer to the desired Claude Code bridge | Heavier service and administrative surface |
| Claude/Codex launch helpers | Use `ccodex` to own the launch contract | `lite claude`, `lite codex`, and `lite opencode` are built in |
| Context truth | Must come from the registry and route qualification | Also requires explicit, verified model metadata and client policy |
| Recommendation here | Default local gateway candidate | Adopt when governance is load-bearing |

Choose CLIProxyAPI first for this bundle's local multi-provider experimentation.
Choose LiteLLM when teams, centrally issued keys, budgets, audit controls, or a
shared production gateway are requirements rather than future possibilities.

LiteLLM's `lite claude` behavior is useful precedent for `ccodex`: it prepares
`ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` and removes a stray
`ANTHROPIC_API_KEY` that would otherwise take precedence. The launcher proposed
here adds explicit context, compaction, provider, and workflow checks around that
basic pattern.

Security note: Anthropic's current LLM gateway documentation warns that LiteLLM
PyPI versions 1.82.7 and 1.82.8 were compromised. Do not install those versions;
rotate credentials if they were used. Treat dependency integrity as part of the
gateway qualification gate.

### Where `raine/claude-code-proxy` fits

`raine/claude-code-proxy` is a narrower, purpose-built Anthropic-compatible bridge
for using Claude Code with Codex/ChatGPT, Kimi, Grok, or Cursor subscriptions. It
already demonstrates several parts of this design: proxy-owned OAuth stores, routing
by requested model ID, OpenAI priority service through a `-fast` alias, token-count
support, Windows artifacts, and a loopback-first server. It can be the easiest path
when those four subscription backends are the entire requirement.

It is not the full control plane proposed here. Its documentation explicitly leaves
cross-app profiles, mid-session base URL/auth changes, settings rewrites, and IDE or
Desktop launch wiring to another tool. It does not provide the desired native Claude
subscription or direct Bedrock envelope. That makes it strong prior art for
`ccodex`, and a viable specialized gateway adapter, but CLIProxyAPI remains the more
general candidate for a model registry spanning multiple provider/account types.

The proxy's documented context recipe appends `[1m]` to non-Claude model IDs, strips
the suffix at the proxy, and separately caps `CLAUDE_CODE_AUTO_COMPACT_WINDOW` at
the actual subscription limit. This is a deliberate compatibility workaround, not
proof that the upstream model has a 1M context. Prefer
`CLAUDE_CODE_MAX_CONTEXT_TOKENS` for unrecognized model IDs on current Claude Code,
plus an exact auto-compact window. If the workaround is retained for a qualified
route, model it as proxy-specific behavior and test it against every Claude Code
upgrade.

## What CLIProxyAPI can and cannot own

The current CLIProxyAPI example configuration supports:

- OAuth model aliases and provider-specific `models[].alias` mappings;
- display names and model exclusion lists;
- default, override, and filter payload rules;
- multiple accounts and load-balancing behavior; and
- compatible endpoints for Codex, Claude Code, Gemini, Grok, and other clients.

Payload rules can create named service variants. For example, an OpenAI priority
alias can inject `service_tier: priority`, and a reasoning alias can inject a
specific `reasoning.effort`. These are gateway policies, not context-window facts.

CLIProxyAPI does not automatically give Claude Code a trustworthy per-model
context table. Model discovery and a successful request prove neither the admitted
prompt size nor correct compaction. The reviewed example configuration also does
not expose a first-class AWS Bedrock/SigV4 provider block, so direct Bedrock access
should remain a separate Claude Code profile until a specific bridge is implemented
and qualified.

### Gateway model discovery is not capability discovery

Claude Code can query `/v1/models` at startup when
`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` and `ANTHROPIC_BASE_URL` points to an
Anthropic Messages gateway. This requires Claude Code v2.1.129 or later. It does not
run for Bedrock or Vertex pass-through endpoints, and it is disabled by default.

Only model IDs beginning with `claude` or `anthropic` are added to the picker.
Discovery returns IDs and optional display names; it does not communicate a trusted
context window, compaction policy, billing mode, or feature contract. Do not rename
GPT routes to fake `claude-*` IDs merely to pass the filter. Expose nonmatching IDs
through an explicit custom model option or workflow configuration and validate them
against the registry.

## Authentication and billing boundaries

Authentication is part of a profile, not just a secret string.

### Native Claude subscription

The safe default for Claude subscription usage is the native Claude Code login.
Anthropic describes subscription-included usage as designed for its native apps,
including Claude Code. Setting `ANTHROPIC_API_KEY` takes precedence over the logged-
in subscription and causes API billing.

CLIProxyAPI advertises Claude OAuth support, so a proxied Claude OAuth route may be
technically functional. That is not enough to make it the default. Anthropic's
current authentication and Agent SDK guidance distinguishes native subscription
use from third-party developer authentication. Third-party products should use an
API key or supported cloud provider unless Anthropic has approved the login flow.
Routing that misrepresents client identity or circumvents subscription limits is
not an acceptable design.

Therefore:

- keep native Claude Code subscription login as the baseline;
- treat Claude subscription OAuth through CLIProxyAPI as experimental;
- require explicit operator approval plus current terms and billing evidence before
  enabling it; and
- never silently fall back from subscription use to `ANTHROPIC_API_KEY` billing.

`claude setup-token` and `CLAUDE_CODE_OAUTH_TOKEN` are supported Claude Code/Agent
SDK mechanisms. They are not automatically credentials for an arbitrary proxy.

### OpenAI/Codex and other providers

Provider OAuth and API-key routes should name their billing and quota domain in the
registry. A working token is insufficient: qualification must record whether quota
is subscription-based, API-metered, cloud-account-metered, or separately rate
limited. This is especially important for fast or priority service variants.

### Bedrock

Bedrock belongs in a direct Claude Code provider profile unless an explicit proxy
adapter supports AWS authentication and request semantics. Its AWS credentials,
region, model IDs, feature availability, and billing envelope differ from a local
CLIProxyAPI OAuth route. Do not inherit gateway authentication assumptions into a
Bedrock workflow.

## Claude Code context and compaction controls

Claude Code's relevant environment controls are process-wide:

- `CLAUDE_CODE_MAX_CONTEXT_TOKENS` sets the maximum context Claude Code should
  assume. In Claude Code v2.1.193 and later it applies directly to unrecognized
  model IDs; for recognized Claude model IDs it applies only when
  `DISABLE_COMPACT` is set.
- `CLAUDE_CODE_AUTO_COMPACT_WINDOW` controls the capacity at which automatic
  compaction operates, capped by the actual model context Claude Code believes is
  available.
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` changes the proactive compaction threshold and
  applies to the main thread and subagents.
- `DISABLE_COMPACT` disables automatic compaction and changes how the maximum-
  context override is interpreted for recognized Claude models.
- `CLAUDE_CONFIG_DIR` isolates settings, sessions, plugins, and credentials. It is
  the clean boundary between launcher profiles on both Windows and Unix-like hosts.

Settings can contain an `env` block that overrides inherited shell variables.
`ccodex` must inspect the effective configuration, not merely set process variables
and assume they won. Each profile should receive its own `CLAUDE_CONFIG_DIR`, or the
launcher should fail if project/user settings would override authoritative profile
values.

Do not set every route to the largest known window. If Claude Code believes a small
route has a larger context than the provider accepts, it can delay compaction until
requests fail. The admitted route limit is the authority.

### The `[1m]` selector

`[1m]` is a Claude-specific extended-context selector. Claude Code recognizes and
strips the suffix before the request reaches the provider. It should be used only
for a supported Claude model on a provider that actually offers the extended
window.

It is not generic model metadata. Never append `[1m]` to GPT, Codex Spark, or an
arbitrary CLIProxyAPI alias. For non-Claude aliases, declare the admitted context in
the registry and launch the appropriate process envelope. A specialized proxy may
use the suffix as a tested local hint and strip it upstream, as
`raine/claude-code-proxy` does, but that workaround belongs to that route's adapter
contract and must be paired with an exact lower auto-compaction cap.

### Nominal versus admitted context

Store both values:

- **nominal context** is the provider's documented maximum for the underlying
  model; and
- **admitted context** is the largest input envelope the exact client, proxy,
  account, region, feature set, and payload combination has qualified.

The admitted value always wins. For example, a vendor may document a roughly
one-million-token model while a particular proxy route is deliberately admitted at
372K. That route belongs in the 512K policy class but must launch with its 372K
limit, not the class ceiling or vendor maximum.

## Dynamic Workflow inheritance

Dynamic Workflows already provide the right model-selection granularity. A phase or
agent can specify a model ID and a worktree. This avoids a separate OS process for
every model.

Important inheritance rules:

- a normal subagent starts with a fresh, isolated context;
- a forked agent inherits the parent conversation at the fork point;
- model values may be an alias, full model ID, or inherited selection;
- `CLAUDE_CODE_SUBAGENT_MODEL` is a process-wide override and can supersede the
  model declared by a workflow or agent definition;
- worktrees isolate files and Git state, not authentication or context policy; and
- workflow agent definitions do not provide per-agent environment, context-window,
  or compaction fields.

Consequently, agents in a single Claude Code process inherit the process's provider,
endpoint, authentication, maximum-context assumption, and proactive compaction
threshold. Their actual conversations remain separate, but their policy envelope is
shared.

Do not set `CLAUDE_CODE_SUBAGENT_MODEL` in a mixed-model `ccodex` profile. It defeats
workflow-level model routing. Reserve it for deliberately homogeneous runs.

### When a second process is justified

Start another Claude Code process when any of these differ incompatibly:

- provider or base URL;
- credential/billing/terms boundary;
- required configuration directory;
- context ceiling or compaction policy; or
- a feature such as Claude fast mode that is not valid for the other routes.

This is normally one process per **context cohort and provider envelope**, not one
process per workflow agent. Dynamic Workflows should continue to allocate models
and worktrees within each compatible cohort.

## The `ccodex` launcher

`ccodex` should remain thin. It is not another model proxy, workflow engine, or
credential store. Its job is to make the launch contract deterministic.

Recommended commands:

```text
ccodex profiles
ccodex resolve <profile> [--workflow <path>]
ccodex doctor <profile> [--workflow <path>]
ccodex workflow-check <workflow> [--profile <profile>]
ccodex run <profile> [--workflow <path>] [-- <claude arguments>]
```

`resolve` prints the non-secret effective configuration. `doctor` tests the gateway,
authentication mode, model discovery/corroboration, context admission, compaction
settings, and billing/terms policy. `workflow-check` verifies every model reference
against the selected profile. `run` executes only after the same checks pass.

A profile should own:

- provider type and base URL;
- authentication **reference** and billing mode, never the secret itself;
- default model and permitted model aliases;
- admitted context and context class;
- automatic-compaction mode and threshold;
- fast/priority feature eligibility;
- isolated `CLAUDE_CONFIG_DIR`;
- environment variables to scrub; and
- the registry/config fingerprint that was qualified.

Before launch, scrub conflicting provider variables, especially
`ANTHROPIC_API_KEY` when native subscription use is intended. Print the selected
provider, model, billing mode, admitted context, compaction threshold, and fast-mode
state without printing secrets.

`ccodex` should resolve to the real `claude` executable at the end. Keeping it thin
makes the native Claude Code experience complete even when CLIProxyAPI is absent.

## Single model registry

Maintain one reviewed registry and generate all downstream representations from it.
Hand-maintained copies will drift.

Minimum route fields:

```yaml
routes:
  - id: gpt-5.3-codex-spark
    provider: cliproxyapi
    upstream_model: gpt-5.3-codex-spark
    nominal_context_tokens: 128000
    admitted_context_tokens: 128000
    context_class: c128
    soft_assignment_tokens: 80000
    compaction_mode: bounded-agent
    billing_mode: provider-subscription-or-api
    auth_profile: codex-oauth
    fast_mode: intrinsic
    allowed_roles: [cartographer, researcher, reviewer]
    overflow_route: gpt-5.6-sol
    qualification_fingerprint: pending
```

The exact values above are illustrative until route qualification records them.
The registry should also record:

- display name and aliases;
- text/image/tool capabilities;
- maximum output reserve;
- allowed workflow phases and SDLC roles;
- judgment tier and blast-radius ceiling;
- regional/account restrictions;
- terms approval state;
- quota and priority-service domain;
- last-qualified client, proxy, and configuration versions; and
- failover policy.

Generate from the registry:

1. CLIProxyAPI alias, exclusion, and payload-policy fragments;
2. `ccodex` profiles;
3. workflow model-reference validation data;
4. human-readable route tables; and
5. qualification fixtures and expected fingerprints.

## Context classes and model right-sizing

Use context classes to make assignments understandable without pretending every
member has the same exact ceiling:

| Class | Class ceiling | Intended work |
|---|---:|---|
| `c128` | 128K | bounded reconnaissance, targeted research, narrow reviews |
| `c256` | 256K | medium implementation/review packets with controlled evidence |
| `c512` | 512K | broad planning, integration, or routes admitted between 256K and 512K |
| `c1m` | 1M+ | mission conductor, deep synthesis, large-repository integration |

Always launch and admit against the route's exact limit, not the bucket ceiling.
Buckets are scheduling labels.

Right-size on two independent axes:

1. **Judgment and blast radius** — how difficult, ambiguous, or consequential is
   the decision?
2. **Expected context footprint** — how many tokens will the agent actually need?

A short wall-clock task can consume a large context through repository reads and
tool output. A long-running but repetitive task may remain small. Therefore “short
agent” must mean a bounded predicted context footprint, not few turns or minutes.

Estimate:

```text
startup instructions
+ workflow/agent prompt
+ inherited context (zero for fresh agents)
+ expected file and tool results
+ response and handoff reserve
+ retry/escalation reserve
+ safety margin
```

`maxTurns` is not a token cap. Bound tool breadth, file scope, output form, and
handoff size as well.

### Recommended SDLC allocation

- Use `c128`/`c256` routes for fresh, bounded cartography, targeted research,
  narrow implementation, and independent review packets.
- Use `c512` for wide repository planning, multi-workstream review, and integration
  that may need substantial evidence.
- Reserve `c1m` for the mission conductor or synthesis stages whose core job is to
  retain cross-wave state.
- Assign the strongest judgment tier required by the task even if a smaller model
  would fit the tokens. Context capacity is not a substitute for reasoning quality.
- Prefer fresh subagents for bounded work; forks pay the inherited-context cost and
  should be chosen deliberately.

### Mixed-context workflows

Smaller-context agents can safely participate in a large mission when their packets
are bounded and the long-context conductor owns durable state and compaction.

Do not rely on a global large-window compaction threshold to protect small routes in
the same process. If the process envelope is larger than a route's admitted window,
one of these must happen:

1. constrain the agent so it cannot approach the smaller limit;
2. use the smallest admitted context as the process-wide floor; or
3. move the route to a separate context-cohort process.

The registry's `soft_assignment_tokens` should be lower than the admitted maximum.
At the soft limit, the agent returns a structured handoff instead of continuing
blindly:

```yaml
status: needs_escalation
reason: predicted_context_overflow
completed:
  - bounded findings already verified
remaining:
  - unresolved work with exact evidence pointers
recommended_route: gpt-5.6-sol
```

The orchestrator may retry on the declared overflow route, preserving the concise
handoff rather than the entire subagent transcript.

## Fast, priority, and Spark modes

These mechanisms are not interchangeable.

### Claude `/fast`

Claude Code fast mode is a session mode for supported Opus releases, not a separate
model. Current documentation says it uses usage credits from the first token, may
switch the session to the supported Opus model, and is unavailable through Bedrock,
Vertex AI, Microsoft Foundry, or the Claude Platform AWS integration.

Treat it as explicit per-session opt-in. A `ccodex` profile that permits `/fast`
must name the supported native route and billing behavior. Disable it for GPT,
CLIProxyAPI non-Claude aliases, and Bedrock profiles.

### OpenAI priority processing

OpenAI priority service is a request payload policy. CLIProxyAPI can expose a named
alias that injects `service_tier: priority`, provided the account and endpoint
support it. Record its separate cost/quota semantics; do not label it as Claude
`/fast`.

### GPT-5.3-Codex-Spark

GPT-5.3-Codex-Spark is a distinct text-only, low-latency model with a documented
128K context window and separate usage limits. It is well suited to bounded,
interactive agent packets, not to inheriting a one-million-token conductor policy.
Place it in `c128`, enforce a conservative soft assignment, and escalate rather
than waiting for a global large-window compaction trigger.

Current OpenAI documentation also lists GPT-5.6 model variants with roughly a
1.05M-token context and 128K maximum output. Those are natural candidates for a
long-context class, but the exact CLIProxyAPI route still uses its admitted limit.

## Qualification and observability

Every configured route must be corroborated end to end. Record:

1. model requested by the workflow;
2. model sent by Claude Code;
3. alias resolved by the gateway;
4. upstream model/provider/account selected;
5. model reported in the response, when available; and
6. context and billing policy used for the request.

A route is qualified only when these agree with the registry and admission tests.
Test at least:

- ordinary completion and tool use;
- near-soft-limit and near-admitted-limit requests;
- compaction behavior;
- unsupported-feature rejection;
- auth expiration and account rotation;
- overflow escalation;
- gateway restart and configuration reload; and
- billing/quota attribution.

Bind qualification to a fingerprint of client version, proxy version, relevant
configuration, provider, model, and account class. A changed fingerprint makes the
route unqualified until the relevant checks rerun.

No silent fallback is allowed. If a requested route is missing, unauthorized,
overloaded, over context, or unsupported, return a typed failure or use only an
explicitly declared overflow route. Silent substitution destroys cost, capability,
and evidence guarantees.

## Common failure modes

| Failure | Consequence | Prevention |
|---|---|---|
| One global 1M setting for all models | Small routes fail before Claude Code compacts | Use exact admitted limits, bounded agents, or separate context cohorts |
| Appending `[1m]` to arbitrary aliases | Invalid or misleading model selection | Restrict the suffix to supported Claude routes |
| Treating `/v1/models` as capability discovery | IDs appear valid without context or feature proof | Registry plus admission tests |
| Setting `CLAUDE_CODE_SUBAGENT_MODEL` globally | Dynamic Workflow model choices are ignored | Leave it unset for mixed-model workflows |
| Assuming worktrees isolate runtime policy | Agents share provider/auth/context settings | Separate processes by incompatible envelope |
| Passing `ANTHROPIC_API_KEY` during subscription use | Unexpected API charges | Scrub conflicting variables and print billing mode |
| Proxying Claude subscription OAuth by default | Terms, identity, or billing exposure | Native baseline; explicit experimental approval |
| Treating `maxTurns` as token safety | Tool output still overflows a small route | Estimate footprint and cap scope/output |
| Silent model fallback | False evidence and uncontrolled cost | Requested/sent/resolved/corroborated audit join |
| Hand-maintaining aliases and profiles | Context and auth policy drift | Generate both from one registry |

## Delivery sequence

Implement in this order:

1. **Registry schema and validator** — include exact/admitted context, judgment tier,
   auth, billing, terms, capabilities, overflow, and qualification fingerprint.
2. **CLIProxyAPI generator** — aliases, exclusions, and payload policy only for
   supported gateway routes.
3. **`ccodex resolve` and `doctor`** — no launch yet; prove effective settings,
   secret scrubbing, route identity, and admission behavior.
4. **`ccodex run`** — isolated configuration directory and deterministic handoff to
   the real Claude executable.
5. **Workflow checker** — reject unknown, incompatible, unqualified, or oversized
   route assignments before a mission starts.
6. **Bounded-agent escalation contract** — structured handoff and explicit overflow
   routes.
7. **Observability join** — requested, sent, resolved, and corroborated model plus
   context and billing envelope.
8. **Optional LiteLLM adapter** — only if centralized governance becomes a real
   requirement.

Native Claude Code must remain a complete execution path throughout. The gateway
and launcher are adapters, not prerequisites for the core Agentic SDLC lifecycle.

## Acceptance criteria

The design is ready for production implementation only when:

- one registry generates gateway and launcher configuration;
- workflows cannot reference an absent or unqualified model;
- context policy uses the exact admitted route limit;
- small-route agents have bounded assignments and tested escalation;
- incompatible provider/auth/context envelopes launch separately;
- subscription versus API/cloud billing is explicit before launch;
- `/fast`, priority processing, and Spark are represented as different mechanisms;
- `[1m]` is accepted only for qualified Claude routes;
- no settings `env` block can silently override the selected profile;
- no silent model or billing fallback exists; and
- evidence joins the requested, sent, resolved, and corroborated route identities.

## Primary sources

- Claude Code [Dynamic Workflows](https://code.claude.com/docs/en/workflows)
- Claude Code [subagents](https://code.claude.com/docs/en/sub-agents)
- Claude Agent SDK [TypeScript reference](https://code.claude.com/docs/en/agent-sdk/typescript)
- Claude Code [environment variables](https://code.claude.com/docs/en/env-vars)
- Claude Code [model configuration](https://code.claude.com/docs/en/model-config)
- Claude Code [LLM gateway configuration](https://code.claude.com/docs/en/llm-gateway)
- Claude Code [worktrees](https://code.claude.com/docs/en/worktrees)
- Claude Code [fast mode](https://code.claude.com/docs/en/fast-mode)
- Claude Code [authentication](https://code.claude.com/docs/en/authentication)
- Anthropic support [Claude account login](https://support.claude.com/en/articles/13189465-log-in-to-your-claude-account)
- Claude [Agent SDK overview](https://code.claude.com/docs/en/agent-sdk)
- LiteLLM [management CLI](https://docs.litellm.ai/docs/proxy/management_cli)
- [CLIProxyAPI repository](https://github.com/router-for-me/CLIProxyAPI)
- CLIProxyAPI [example configuration](https://github.com/router-for-me/CLIProxyAPI/blob/main/config.example.yaml)
- [`raine/claude-code-proxy`](https://github.com/raine/claude-code-proxy)
- OpenAI [Introducing GPT-5.3-Codex-Spark](https://openai.com/index/introducing-gpt-5-3-codex-spark/)
- OpenAI API [model catalog](https://developers.openai.com/api/docs/models)
- OpenAI API [latest-model guide](https://developers.openai.com/api/docs/guides/latest-model)
