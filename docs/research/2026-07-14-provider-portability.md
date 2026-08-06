# Provider and model portability

Status: dated design reference, researched 2026-07-14 — read alongside
`2026-08-05-gateway-selection-memo.md`, which post-dates this record and adds the
opencodex evaluation, the CLIProxyAPI cloned-source findings, and the ToS addendum. This
record's unique standing content is the raine/claude-code-proxy source comparison (the
newer memo never analyzes raine), the control-plane/data-plane single-translation-owner
model, and the certification contract. Its recommendations sit inside ADR-0003's
carve-out: gateways stay optional, API-key-only, for non-Anthropic models. Ported from
the pre-reconciliation branch line (commit 93ce505) on 2026-08-06.

This record explains how Agentic SDLC can use models across Claude Code and Codex without making one proxy, provider, or model-name convention part of its core contract. It also records the July 14, 2026 primary-source comparison of current portability tools.

This is an explanation and certification reference. It does not install an adapter, approve credentials, authorize network exposure, or certify any candidate. Every trust/configuration change, credential flow, canary, deployment, push, or publication still requires operation-specific authorization.

## Evidence language

- **Verified:** observed in the cited repository source, tests, workflow, or release artifact at the inspected revision. It is not a production assurance or a successful live-provider test.
- **Inferred:** an Agentic SDLC design conclusion drawn from verified observations.
- **Unverified:** not exercised end to end, not exposed by reliable readback, or asserted only by project documentation.

Repository absence claims are time-bound. Provider policies, entitlements, model catalogs, and upstream protocols may change independently.

## The portability boundary

Portability has two planes:

1. A **control plane** manages profiles, routing intent, and client configuration.
2. A **data plane** translates live requests and responses between harness and provider protocols.

One component may implement both, but each request path must have exactly **one translation owner**.

```text
Agentic SDLC assignment
  -> harness adapter: Claude Code or Codex
  -> capability/readback contract
  -> direct provider OR one translation gateway
  -> provider profile and credential
```

Do not blindly chain translators:

```text
Claude Code -> CCS translator -> another Anthropic/OpenAI translator -> provider
```

Nested translation creates competing model maps, duplicate schema loss, ambiguous authentication, and streaming/tool-call failure attribution. CCS and another proxy may coexist side by side or compose through an explicitly tested passthrough boundary, but no direct CCS-to-proxy chain is assumed safe.

Provider-native execution remains available as the baseline and rollback path. An optional adapter must not become a hidden core dependency.

## Model roles, not provider lock-in

The target adapter-certified mapping uses six exact model IDs. It is an additive portability contract proposed by the six-tier policy work, not a claim that the current base has already migrated every role manifest. The current shipped roles may inherit the host default; those runs must record the requested tier/model as inherited or unresolved unless adapter readback proves resolution.

The existing four semantic tiers remain useful: frontier, judgment workhorse, capable volume, and a mechanical floor. The six-ID gateway mapping pairs the first three failure classes across GPT and Claude; the cheapest safely certified model within the capable-volume lane may serve mechanical work.

| Failure class | GPT option | Claude option | Typical work |
|---|---|---|---|
| Derail or settled truth | `gpt-5.6-sol` | `claude-fable-5` | framing, architecture, final verdict, trust-boundary ruling |
| Contained silent degradation | `gpt-5.6-terra` | `claude-opus-4-8` | implementation, investigation, dense synthesis, semantic review |
| Visible retry behind a gate | `gpt-5.6-luna` | `claude-sonnet-5` | search, extraction, fixtures, cartography, structured verification |

Where a host and certified adapter support explicit selection, each subagent and Dynamic Workflow call records an exact requested model and appropriate reasoning effort. Otherwise it records the execution as inherited or unresolved rather than inventing resolution. Add `[1m]` independently for context-heavy recovery, repository-wide reading, planning, synthesis, and adversarial review when that exact suffixed form has been transport-certified. `[1m]` request/readback does not prove upstream context capacity, distinct intelligence, or compaction behavior. A successful effort request does not prove the provider honored it when effective-effort readback is unavailable.

Mixed-family panels are useful when they reduce correlated error. They are not a requirement to include all six models in every workflow.

## Candidate comparison

### Data-plane adapters

| Dimension | `raine/claude-code-proxy` | `1rgs/claude-code-proxy` |
|---|---|---|
| Implementation | Verified Rust/Axum adapter | Verified Python/FastAPI/LiteLLM adapter |
| Inbound surface | Verified Claude Code-oriented `POST /v1/messages`, `POST /v1/messages/count_tokens`, `GET /healthz` | Verified `POST /v1/messages`, `POST /v1/messages/count_tokens`, `GET /` |
| Upstreams | Verified Codex, Kimi, Grok, and Cursor provider modules with proxy-owned login flows | Verified API-key-backed OpenAI, Gemini/Vertex, and Anthropic paths, including custom `OPENAI_BASE_URL` |
| Routing | Explicit provider/model IDs; unknown fixed IDs rejected; `[1m]` stripped before dispatch | Haiku/Sonnet names mapped through process-wide `SMALL_MODEL`/`BIG_MODEL`; some Google selections silently fall back to OpenAI |
| Model readback | CLI `models [--full]`, startup map, and TUI requested/resolved display; adapter evidence only | Responses expose the post-validation mapped identifier and terminal logs show mapping; no dedicated readback endpoint |
| Effort/thinking | Provider-specific effort translation; Codex summaries and selected provider reasoning can become thinking blocks | No observed effort path; thinking forwarded only for direct Anthropic upstreams |
| Tools/streaming | Broader provider-specific translation, but Codex images, hosted-tool limits, partial-stream retry, and general Cursor callbacks have documented gaps | Anthropic-like SSE and tool conversion exist, but structured tool results/images are flattened for some paths and modern semantic coverage is narrow |
| Inbound authentication | None; loopback default `127.0.0.1:18765` | None; default bind `0.0.0.0:8082` is remotely reachable unless network controls intervene |
| Credential boundary | Provider-specific OAuth/token stores separated from official provider CLIs; refresh behavior exists but was not live-tested | Process-wide provider keys from environment or `.env` are shared by all clients |
| Sensitive logging | Normal logs redact tokens; optional traffic logging intentionally retains prompts and tool content | Mapping/request logging exists; no equivalent reviewed lifecycle or sensitive-traffic policy was established |
| Releases/legal | Versioned cross-platform archives with SHA-256 files, MIT license, and locked tests before release builds | No tags/releases, no observed license grant or security policy; rolling main-derived container publication |
| Authenticity | Publisher signing, notarization, SBOM, and SLSA-style provenance were not observed; same-channel SHA-256 is integrity evidence, not publisher authentication | No reviewed immutable release-to-source receipt; workflow actions include mutable references |
| Platform evidence | macOS/Linux/Windows artifacts; no WSL-specific proof | Linux amd64/arm64 containers; native Windows and WSL unverified |
| Current disposition | Lower-burden laboratory candidate for its provider set, still uncertified | Narrow laboratory candidate only when its distinct API-key upstreams justify the higher control burden |

These projects are independent. Raine is not a fork, successor, or functional superset of 1rgs because their upstream and credential models differ.

### Verified raine blockers and discrepancies

- Current `src/server.rs` has no `GET /v1/models`, despite README gateway-discovery guidance. Treat that guidance as stale or forward-looking.
- Model lists and TUI resolution are adapter self-report, not live provider capability attestation.
- No inbound authentication exists. Loopback reduces exposure but does not isolate untrusted local processes.
- `CCP_TRAFFIC_LOG=1` retains sensitive prompts and tool content.
- Cursor does not provide general Claude workspace/tool callback round-trips.
- Retry after a partially emitted stream can duplicate observable tool calls.
- Release archives have SHA-256 files, but publisher signing/notarization was not observed. The installer applies local ad-hoc macOS signing; that is not publisher authenticity.
- The July 2026 Windows path resolver compares Rust's runtime OS value against `win32` rather than `windows`. This Windows path defect makes normal binaries fall through to XDG/home paths instead of the documented `%APPDATA%` and `%LOCALAPPDATA%` paths. Synthetic tests inject `win32`, while release smoke runs only `--version` and cannot detect config/auth/state behavior.
- The analogous `darwin` versus `macos` mismatch is real, but the no-XDG macOS default happens to coincide; behavior diverges when `XDG_CONFIG_HOME` is set.
- WSL login, networking, storage, refresh, request, and teardown behavior remains unverified.

### Verified 1rgs blockers and discrepancies

Observations were pinned to full revision `5e45ba683ded931c1832cfca6468a791c6855e45`.

- No inbound authentication combines with a `0.0.0.0:8082` default bind.
- README's “all Claude clients” statement is unverified. Only Claude Code configuration plus Messages/count-token routes were observed.
- Cross-provider thinking output is not implemented, and OpenAI cleanup flattens structured content, tool results, and images into text on some paths.
- Docker uses `python:latest` and Uvicorn `--reload`; no health endpoint, service manager, update command, or production lifecycle was observed.
- Tests are paid live-integration scripts with lenient structural comparisons, not isolated semantic-conformance CI.
- No tags, releases, license declaration, `SECURITY.md`, Windows/WSL evidence, or versioned image-to-source receipt was observed.
- README and source disagree about the default provider, Vertex authentication, GPT defaults, Gemini model lists, and image tags.
- A successful root response proves process liveness only, not credential validity, entitlement, semantic support, or serving-model identity.

## Control-plane and gateway alternatives

| Project | Best evaluated role | Evidence-qualified note |
|---|---|---|
| [`kaitranntt/ccs`](https://github.com/kaitranntt/ccs) | Profile/runtime control plane with built-in routing | Verified request-time `profile:model` precedence and fixed scenario routes. Do not assume it can directly chain with another Anthropic-to-provider translator. |
| [Claude Code Router](https://github.com/musistudio/claude-code-router) | Extensible multi-provider runtime gateway | Documents provider protocols, rewrites, retries, fallback chains, custom routes/connectors, virtual models, and MCP aggregation. Requires the same conformance and trust evaluation. |
| [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) | Claude/Codex-compatible protocol gateway | Documents cross-format interfaces and configurable upstreams. Multiple-account support does not itself prove safe round-robin failover. |
| [CC Switch](https://github.com/farion1231/cc-switch) | Cross-client configuration UX | Advertises multi-tool profiles and presets. Configuration synchronization does not prove runtime or semantic parity. |
| [LiteLLM](https://github.com/BerriAI/litellm) | General provider translation substrate | Broad provider surface can reduce transport work, but it does not remove the need for Claude Code/Codex semantic and trust-boundary tests. |

## Certification contract

Certification attaches to an exact tuple, never a project name:

```text
adapter revision + artifact hash
provider + upstream model
platform + credential mode
harness + transport
capability subset + effective effort/context evidence
```

### Required capability matrix

A candidate must pass isolated fixtures for:

- non-streaming and streaming text;
- event ordering and terminal semantics;
- images, documents, citations, and structured content;
- single and parallel tools, structured results, and continuation history;
- thinking/reasoning and requested versus effective effort;
- hosted web/search tools and their limits;
- structured output and unsupported-field rejection;
- stop reasons, refusals, pauses, errors, and usage;
- cancellation, timeout, rate limits, reconnect, and partial-stream failure;
- context limits, token counting, and compaction behavior without treating `[1m]` as capacity proof;
- model selection, serving-model provenance, and stale/ambiguous readback;
- credential login, refresh, revocation, isolation, and log redaction;
- installation, update, rollback, crash recovery, and teardown;
- Linux, macOS, native Windows, and WSL as separate targets.

After an observable tool side effect, automatic retry is prohibited unless idempotency is proven.

### Admission and rollback

1. Pin the exact source revision, artifact, and checksum.
2. Bind to loopback and use one dedicated non-production provider identity.
3. Disable sensitive traffic capture.
4. Run the capability matrix without production credentials or repositories.
5. Record requested and resolved model, effort, context, transport, and capability provenance. Mark unavailable fields unresolved rather than inferring them.
6. Compare evidence against an external policy source; the adapter cannot certify itself.
7. If authorized, canary one worker and one allowlisted tuple.
8. Keep the provider-native path intact and rehearse rollback.
9. Revoke credentials and remove adapter state on exit.

A health endpoint, alias, monitor, token estimate, README table, or successful request is insufficient admission evidence by itself.

## Trust boundary

```text
worker
  -> unauthenticated local adapter
  -> shared adapter-owned credential
  -> external provider
```

Threats include caller spoofing, request/response translation tampering, weak audit attribution, credential and traffic-log disclosure, retry/rate-limit denial of service, and elevation through a shared provider account. Remote or multi-user use is blocked until a separately authorized authentication, isolation, policy, and observability boundary is tested.

## Current recommendation

- Keep provider-native Claude Code and Codex execution as the default and rollback path.
- Evaluate a pinned raine release first for Codex/Kimi/Grok/Cursor, on Linux, in an isolated laboratory. Do not certify Windows until the path defect is fixed and the real login/storage/request lifecycle passes natively.
- Evaluate 1rgs only for its distinct OpenAI/Gemini/Anthropic API-key use case, with loopback override, process/key isolation, an immutable image digest, and legal review.
- Treat CCS as a possible control plane, not permission to nest translators.
- Do not promote either proxy into the Agentic SDLC control plane. They are optional egress adapters until tuple-specific evidence proves otherwise.

## Primary sources

### Raine

- [Repository and README](https://github.com/raine/claude-code-proxy)
- [Server routes](https://github.com/raine/claude-code-proxy/blob/main/src/server.rs)
- [Model registry](https://github.com/raine/claude-code-proxy/blob/main/src/registry.rs)
- [Configuration](https://github.com/raine/claude-code-proxy/blob/main/src/config.rs)
- [Path resolver at v0.1.17](https://raw.githubusercontent.com/raine/claude-code-proxy/v0.1.17/src/paths.rs)
- [Release workflow](https://github.com/raine/claude-code-proxy/blob/main/.github/workflows/release.yml)
- [Installer](https://github.com/raine/claude-code-proxy/blob/main/scripts/install.sh)
- [v0.1.17 release](https://github.com/raine/claude-code-proxy/releases/tag/v0.1.17)
- [MIT license](https://github.com/raine/claude-code-proxy/blob/main/LICENSE)

### 1rgs

- [Repository and README](https://github.com/1rgs/claude-code-proxy)
- [Inspected full revision](https://github.com/1rgs/claude-code-proxy/commit/5e45ba683ded931c1832cfca6468a791c6855e45)
- [Server at the inspected revision](https://raw.githubusercontent.com/1rgs/claude-code-proxy/5e45ba683ded931c1832cfca6468a791c6855e45/server.py)
- [Tests at the inspected revision](https://raw.githubusercontent.com/1rgs/claude-code-proxy/5e45ba683ded931c1832cfca6468a791c6855e45/tests.py)
- [Environment example](https://raw.githubusercontent.com/1rgs/claude-code-proxy/5e45ba683ded931c1832cfca6468a791c6855e45/.env.example)
- [Dockerfile](https://raw.githubusercontent.com/1rgs/claude-code-proxy/5e45ba683ded931c1832cfca6468a791c6855e45/Dockerfile)
- [Publish workflow](https://raw.githubusercontent.com/1rgs/claude-code-proxy/5e45ba683ded931c1832cfca6468a791c6855e45/.github/workflows/publish.yml)
- [Releases](https://github.com/1rgs/claude-code-proxy/releases)
- [Tags](https://github.com/1rgs/claude-code-proxy/tags)

### Alternatives and protocol references

- [CCS](https://github.com/kaitranntt/ccs)
- [Claude Code Router](https://github.com/musistudio/claude-code-router)
- [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
- [CC Switch](https://github.com/farion1231/cc-switch)
- [LiteLLM](https://github.com/BerriAI/litellm)
- [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages)
- [Anthropic Models API](https://platform.claude.com/docs/en/api/models)
- [Anthropic streaming](https://platform.claude.com/docs/en/build-with-claude/streaming)
- [Anthropic token counting](https://platform.claude.com/docs/en/build-with-claude/token-counting)
- [Rust `std::env::consts::OS`](https://doc.rust-lang.org/std/env/consts/constant.OS.html)
