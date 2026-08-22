# Define provider onboarding and route-control UX

Type: prototype
Status: resolved
Blocked by: 06, 08, 11
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What exact `ccodex routes` interaction should discover providers, explain credential ownership and
data egress, invoke each provider's approved login flow, inspect readiness, qualify exact routes,
refresh or revoke configuration, and recover from partial setup without exposing credential values
or conflating reachable, tested, qualified, and supported states? Prototype the native-Claude-only
starting state, one successful provider onboarding, refusal paths, and removal handoff.

## Observed current truth

The selected checkout has no canonical `ccodex routes` command yet. Its installed surface exposes
`ccodex providers`, `ccodex models`, gateway `status`, and a reviewed `ccodex configure`
passthrough to a bounded subset of OpenCodex account/provider/config verbs. Non-Anthropic provider
mutation is admitted; Anthropic mutation, unbounded setup/GUI/config import-export, and unknown
upstream verbs fail closed.

A successful provider add, edit, or remove currently writes the OpenCodex configuration file only.
The wrapper prints—but deliberately does not execute—the required `ocx sync` and `ccodex restart`
sequence because sync rewrites shared Codex configuration and restart interrupts routed sessions.
Until both occur, a request naming a configured-but-not-live provider may fall through to the
default provider rather than fail closed. `ccodex status` already compares configured providers
with the running gateway catalog and reports `NOT-LIVE` or `unknown`; `provider test` is a live
credentialed reachability call, not proof of configuration, qualification, or support.

OpenCodex can read keys from stdin through `account add-key`, while its provider-add surface may
require an argv key. The current wrapper warns and redacts output but still forwards that form,
which leaves a host process-list exposure. The product contract instead says credentials stay in
each provider's approved store, unrelated credentials are scrubbed, and credential lifecycle is a
hard human gate. Claude subscription login remains Claude-owned and is never onboarded as an OCX
provider.

OpenCodex package installation, provider configuration, gateway lifecycle, Claude model-picker
state, and persistent integrations for other clients are separate effects. Integration status and
history must be inspected per client; an OpenCodex journal can contain reversible credential
material and is sensitive. The new product UX must compose the reviewed lower-level tools without
claiming that package presence or one successful mutation configured every client or produced a
qualified route.

## Decisions

### Canonical surface and dimensional readiness

`ccodex routes` is the canonical operator-facing route-control surface. `routes list`, `show`,
and `status` are read-only and do not start, sync, restart, authenticate, qualify, or repair the
gateway. Later lifecycle operations live under the same noun as `routes configure`, `qualify`,
`refresh`, `revoke`, and `recover`. The existing `ccodex configure` remains a low-level
compatibility surface during migration, but product documentation and generated guidance lead
with `ccodex routes`.

Route status is a dimensional matrix, never one `ready` or `available` boolean. It reports
provider recognition; credential custody and observed acceptance without values; configuration
presence and drift; gateway health; exact running-catalog membership; correlated route probe;
class qualification; runtime-policy admission; and published support as independent facts with
their evidence source, observation time, and blocker. Missing or unreadable evidence is `unknown`,
not false and not inferred from a neighboring dimension.

Native Claude is a separate route family, not an OCX provider row. The default native-only view is
a successful product state: core mode is usable through ordinary `claude`, routed mode is
`not-activated`, and no external-provider setup is demanded. PII-stripped Claude login status may
be shown, but login presence does not prove an exact native route, entitlement, model identity, or
qualification. A gateway that is down because routed mode was never activated is also not an
error.

`routes list` inventories release-known provider profiles plus separately labeled operator-defined
configuration. `routes show` explains one provider and its exact route rows. `routes status`
focuses on observed local state and closes with exact blockers and the next bounded command. Query
completion and route health remain separate: a valid report exits successfully even when every
routed candidate is absent, blocked, stale, or unsupported.

### Provider profiles and the operator-defined lane

The distribution ships a versioned, digest-bound catalog of first-party provider profiles. A
profile contains only reviewed non-secret onboarding metadata: canonical provider ID and model
namespace, admitted adapters, endpoint and region rules, approved authentication front doors,
credential-store owner, billing and external-retention disclosures, platform constraints, and
sync/restart requirements. It means guided onboarding for that provider shape is supported; it is
not a provider-wide model, route, qualification, or runtime-admission promise.

`routes list` reconciles four sources without collapsing them: the release profile catalog, the
pinned OCX registry, operator configuration, and the running gateway catalog. Each row preserves
source and version. An upstream registry entry is an observed tool capability, not a product
profile. A configured provider is not live, and a live catalog route is not thereby qualified or
supported. Native Claude subscription access remains a separate route family and cannot be
created, shadowed, or relabeled as an OCX provider profile.

Users may define an `operator-defined` provider through an explicit advanced lane. Its non-secret
profile lives in the ccodex XDG configuration plane; credentials remain in the selected provider
or OCX-owned store. The plan requires an explicit provider namespace, adapter, endpoint and
region, credential method, billing basis, retention disclosure, and model-discovery behavior.
No value is inferred from a model name. An operator-defined route may be configured, probed, and
locally qualified, but it inherits no published-support or runtime-admission claim; those remain
separate evidence and policy decisions.

External endpoints require HTTPS with normal certificate verification. Explicit loopback or
local-runtime endpoints may use local HTTP only when the plan classifies them as local, binds the
exact address, and proves no external egress claim. Redirects, endpoint changes, private-network
targets outside that declared local case, credential-bearing URLs, and Anthropic-subscription
impersonation fail closed. Catalog discovery never downloads a mutable profile or silently
updates itself; built-in profile changes arrive only in a verified product release.

### Plan-apply-resume onboarding lifecycle

`ccodex routes configure <provider>` begins with read-only assessment and renders an exact
`route-onboarding-plan/v1`; it does not mutate merely because the interactive command was
selected. Noninteractive use separates `routes plan configure` from `routes apply
--authorization-digest <digest>`. A dry run stops after the plan, and there is no implied or
agent-supplied `--yes` path around approval.

The plan binds the provider profile and tool versions, target host identity, prestate hashes,
namespace, adapter, endpoint and region, credential front door and owner, declared egress,
billing and external retention, exact non-secret configuration delta, sync and per-client
integration effects, gateway restart and in-flight-session interruption, catalog and probe
checks, rollback limits, stage budgets, stop conditions, and output receipts. Any change makes
the authorization digest unusable.

Configuration, credential acquisition, sync, restart, live-catalog verification, and probing are
separately named stages. One main-session approval may authorize the exact bounded stage sequence,
but the provider's interactive credential step and acceptance of a currently detected session
interruption remain hard human gates. Each stage rechecks its admitted prestate and durably writes
a content-minimized receipt before the next begins. A stage never treats an earlier intent,
prompt, or partial receipt as authority to continue.

This is a resumable lifecycle, not a false cross-system transaction. Once an external credential
store, OpenCodex config, shared client integration, or gateway process changes, later failure is a
`partial-onboarding` effect. The current stage and known/unknown effects are recorded; the system
does not claim rollback, silently delete credentials, restore drifted configuration, repeat a
credential operation, or restart again. Recovery re-admits every completed receipt and current
prestate, then offers only exact remaining stages or an explicit compensating plan.

A configured or credentialed provider remains `staged-not-live` until the planned sync, restart,
and running-catalog verification all succeed. `ccodex launch`, route qualification, and generated
fallback selection refuse its namespace during that window, independently of the gateway's own
default-provider fallthrough behavior. Completion establishes configuration and exact live
catalog facts only; the optional route probe, class qualification, runtime admission, and
published support remain separate.

### Credential custody and authentication front doors

`ccodex routes` never accepts a credential value in command arguments, URLs, prompt text,
repository files, profile documents, plans, journals, receipts, or generated commands. It also
never copies a provider credential into Claude configuration or an Agentic SDLC-owned store.
Provider profiles admit only pinned provider/OCX front doors that keep the value in that
provider's approved credential store.

Browser OAuth and device-code stages first show the official destination, requested scopes,
credential owner, callback behavior, and provider retention, then execute the pinned upstream
flow after the hard human gate. API keys or other bearer material pass directly from hidden TTY
input or stdin to the provider-owned process; ccodex does not parse, buffer, echo, or persist the
value. The child environment is an allowlist with unrelated credential variables removed. Shell
history, argv, process-list-visible flags, credential-bearing URLs, and temporary plaintext files
are forbidden channels.

If the pinned upstream tool cannot accept a credential without an exposed channel, guided
onboarding refuses before reading the value. It may print a non-secret manual provider-owned
handoff and later re-assess masked status, but it never degrades to `--api-key`, asks an agent to
handle the value, or claims custody over what the operator does outside the product. The current
low-level compatibility route's warning-and-forward behavior is not the desired `ccodex routes`
contract.

Multiple provider accounts are represented by opaque local credential-slot IDs. A slot selects a
provider-owned record without embedding an email, organization, account number, key fragment, or
secret-derived hash in product output. Status records only `absent`, `present-unverified`,
`accepted`, `needs-interaction`, `expired-or-revoked`, or `unknown`, plus a bounded evidence source
and time. It never inventories unrelated accounts.

Testing acceptance is a separately disclosed live-egress stage in the onboarding plan. Success
means only that the selected provider accepted that credential at that time. It does not prove a
model exists, identify the served route, grant class qualification or runtime admission, or
publish support. Claude subscription login, OAuth material, entitlement, refresh, and revocation
remain entirely Claude-owned and outside this provider lifecycle.

### Client scope and namespace preservation

Provider onboarding targets the Claude-through-ccodex gateway surface by default. It does not
enable, refresh, adopt, or rewrite OpenCodex integrations for Codex, Hermes, OpenCode, Pi, or
another client. The plan reads their bounded integration status only to identify collision and
shared-sync effects; existing foreign or previously configured integrations remain separately
owned and unchanged.

Adding a provider preserves the gateway's current default provider. Every added non-primary
provider model remains under its explicit provider namespace. Onboarding creates no bare-model
alias, combo, failover pool, fallback rule, account rotation, or default-provider change.
Multiple providers therefore coexist as separately addressable route families, and each exact
model/effort/context route later earns its own probe, qualification, and runtime admission.

Before sync, the plan inventories every client configuration and journal the pinned OCX operation
would read or write. If gateway refresh cannot occur without rewriting another client's state,
the default onboarding plan stops at that boundary and presents the additional per-client
mutation for separate operation-specific approval. Declining it leaves an honest
`staged-not-live` provider; the product does not broaden the original approval, invoke a generic
setup command, or describe package installation as integration consent.

`ccodex launch` admits a namespaced route only when that exact ID is in the running catalog and no
active route-control quarantine or lifecycle blocker applies. Removal, credential loss, stale
configuration, or an unknown ID therefore cannot retarget the request to the default provider,
even if the underlying gateway would do so. A mismatch stops before the Claude session or model
can send that request.

### Successful external-provider prototype

The native-only starting view reports ordinary Claude as usable, routed mode as
`not-activated`, an intentionally stopped gateway as expected, and no external provider as
configured. It offers `ccodex routes show <profile>` rather than treating optional provider setup
as remediation.

Muse is the worked API-key-backed external-provider journey. `ccodex routes configure muse`
first renders a no-call plan naming the `openai-responses` adapter,
`https://api.meta.ai/v1`, the `muse/*` namespace, provider-owned credential slot, egress and
retention disclosure, no default or other-client change, and the configure/authenticate/sync/
restart/catalog-verification stages. The authorization view states explicitly that onboarding
does not perform a route probe, qualification, runtime admission, or launch.

After the approved credential and lifecycle stages, success reports the profile as recognized,
credential acceptance as observed, non-secret configuration as current, gateway as healthy, and
each exact `muse/*` catalog row independently. Probe remains `not-run`; qualification and runtime
admission remain `none`; published support remains `onboarding-profile-only`. The terminal BLUF is
`configuration-complete; no route is qualified`, followed by the bounded next command, such as
`ccodex routes qualify muse/muse-spark-1.2`.

If another client would change, a live session would be interrupted without approval, the secret
cannot use a safe front door, or the provider is not present in the post-restart catalog, this
prototype does not reach success. It stops in a clean refusal or receipt-backed partial state and
names the exact resume or compensation operation.

### Codex-subscription primary journey and gateway-native routes

The primary routed onboarding journey is native Claude to the first-party
`openai-codex` provider profile; Muse remains the worked second-provider, API-key-backed journey.
`openai-codex` and `openai-api` are different profiles, credential owners, billing bases, and
qualification targets. OpenAI's official Codex documentation establishes that native Codex can
use `Sign in with ChatGPT` for subscription access and that its usage follows the ChatGPT
workspace plan. It does not establish that an OCX gateway is OpenAI-supported, so Agentic SDLC
states that transport claim only from its own pinned-tool conformance evidence.

`ccodex routes configure openai-codex` invokes the pinned OCX OpenAI/Codex OAuth front door,
which sends the operator through OpenAI's ChatGPT authorization flow. The resulting grant is a
separate credential slot in OCX's account store. ccodex neither imports nor copies native Codex
CLI credentials, treats an existing Codex login as consent, nor writes the grant into Claude's
credential store. An existing OCX slot may be selected by opaque ID only after masked re-admission.

The plan declares credential owner `ocx-openai-account-store` and billing basis
`chatgpt-subscription`. The latter is reported as declared until masked account/plan readback and
an attributed route probe support the exact observation; missing evidence becomes `unknown`, not
API billing and not subscription proof. If no gateway provider exists, the plan may explicitly
establish OpenAI as the initial provider and default. It never silently replaces a different
existing default; that requires a separate exact default-change decision or a supported
non-default route shape.

The OpenAI profile is the narrow exception to the ordinary provider-namespace display rule. OCX
publishes its primary GPT family as bare exact `gpt-*` catalog IDs and records them as provider
`openai`. Such a `gateway-native` route is admissible only when the exact requested ID is in the
running catalog, the versioned profile maps that family unambiguously, and correlated gateway
attribution independently resolves the call to OpenAI. A prefix convention, family guess,
response-body echo, or default-provider classification is insufficient. An unknown bare ID stops
before launch rather than falling through.

Successful onboarding ends with the OpenAI credential accepted, non-secret provider state
current, gateway healthy, and exact GPT catalog rows enumerated. Probe, per-class qualification,
runtime admission, subscription-billing observation, and published support remain independent.
Each exact GPT model/effort/context route earns those states separately before production use.

### Credential-slot route identity

Every ordinary exact route binds one opaque `credential_slot_id` in addition to its transport,
provider, endpoint/region, model, effort, context, tools, authentication, and billing basis. The
slot is part of the route ID, qualification identity, approval digest, runtime assignment, and
post-call attribution requirement. Two slots serving the same nominal model are separate routes;
qualifying one does not qualify the other.

Version 1 defaults to one explicitly selected slot. `openai-codex` selects one OCX OAuth grant;
API-key and other provider profiles select one provider-owned key or account slot. Ordinary route
configuration disables round-robin, fill-first, quota switching, account rotation, and implicit
pool selection. If the pinned gateway exposes multiple eligible accounts but cannot inject and
correlate the selected opaque slot, route resolution stops rather than treating the pool as one
credential.

Throttling, expiry, revocation, or capacity pressure on a slot may retry only within the bounded
same-route policy. Switching to another slot is an exact route change and requires a separately
qualified, runtime-admitted, and preapproved alternative. Status may report provider-supplied
quota windows, reset times, and capacity categories for a slot, but never identity, entitlement
bodies, credential fragments, or secret-derived labels. Missing slot-level evidence is
`unknown`.

A future `credential-pool` route is a distinct versioned route type. Its membership, selection
algorithm, billing/egress implications, correlation evidence, fallback behavior, and qualification
must all be explicit; provider/model equality does not grandfather it. Until the selected gateway
can pin and read back an opaque served-slot identity, that future type is unsupported and
non-dispatchable.

### Route probe and qualification handoff

`ccodex routes probe <exact-route>` is the product's only route-probe verb. It first renders an
approved synthetic canary plan binding the full route tuple and credential slot, running-catalog
snapshot, exact model/effort/context request, provider endpoint, transmitted data class, call/
token/cost/time budgets, attribution source, output receipt, and stop conditions. It invokes the
model directly through the bounded evaluator surface; it never uses a workflow, generic worker,
fallback, configuration mutation, or inherited model.

A successful probe establishes only current credential acceptance, transport reachability,
catalog membership, request injection, and correlated provider/model/slot identity for that exact
route. It moves the route from catalog-only to route-probed and records requested versus effective
effort/context honestly. It does not establish semantic capability, class qualification, runtime
admission, subscription entitlement beyond observed billing evidence, or published support.
Identity mismatch or default-provider fallthrough quarantines the exact cell under the rightsizing
contract.

OpenCodex `provider test` remains an expert low-level diagnostic. Its result may be displayed as a
separate reachability observation but cannot mint the closed probe receipt because it does not
necessarily bind the requested model, settings, credential slot, catalog snapshot, and correlated
route identity required by Agentic SDLC.

`ccodex routes qualify <exact-route> --class <evaluation-class>` is a thin user-facing handoff to
`ccodex sdlc rightsize`. It uses the same run-spec, task-pack, thresholds, authorization digest,
post-call effect, immutable generation, expiry, and quarantine contracts; route control owns no
second evaluator or qualification format. Configuration and probe operations cannot qualify as a
side effect. Qualification is per exact route and selected class, and version 1 offers no default
`--all` evaluation.

Status links the route-probe receipt and each class-qualified generation independently, including
their freshness and blockers. A route that is configuration-complete or route-probed but lacks
current class qualification and runtime admission remains non-dispatchable for that class.

### Layer-specific refresh and drift

`ccodex routes refresh <provider>` reconciles only the provider profile, non-secret
configuration, selected client scope, gateway activation, and live catalog. It begins with a
read-only, digest-bound diff across the release profile and tools, operator profile, provider and
client configuration, lifecycle receipts, gateway process, and running catalog. A dry run stops
there. Apply uses the same staged approval, writer lock, receipts, partial-effect state, and
recovery contract as onboarding.

Provider refresh never reauthenticates, probes, qualifies, changes a default, updates a tool, or
selects another credential slot as a side effect. Credential renewal is `routes credentials
refresh <provider> --slot <id>` with its own front-door plan and hard gate. Probe renewal is
`routes probe <exact-route> --refresh`. Class evidence renewal is `routes qualify <exact-route>
--class <evaluation-class> --refresh`, which delegates to rightsizing. One layer's success cannot
renew another layer's timestamp or evidence.

Drift is classified before action. Unrelated compatible catalog growth is benign. A stopped
gateway, missing expected live row, or stale but otherwise matching profile/configuration is
refreshable. Endpoint, adapter, namespace, provider/default mapping, credential slot, client
scope, authentication or billing basis, or exact route-tuple drift is blocking and invalidates
affected probe and qualification evidence. Foreign ownership, unreadable state, ambiguous
prestate, or a modified lifecycle-owned artifact is `conflict` and is preserved rather than
overwritten.

The last valid configuration and evidence remain visible for diagnosis and recovery, but an
expired, invalidated, quarantined, conflicting, or currently non-live route is not dispatchable.
Refresh never rolls back to an older route automatically, rewrites a foreign configuration, or
turns a previously qualified route into a fallback without a new explicit plan.

### Disable, credential revocation, and provider removal

Route shutdown uses three separate operations. `routes disable <provider|route>` immediately
adds a reversible local admission block without deleting configuration, credentials, or history.
`routes credentials revoke <provider> --slot <id>` invokes the provider-owned logout or
revocation front door under its own hard human gate. `routes remove <provider>` removes only the
admitted non-secret provider configuration, then performs the separately approved sync, restart,
and catalog-absence verification stages. Version 1 has no route-history purge command.

Every removal plan inventories active sessions, provider/default mapping, exact routes, fast-model
selection, workflow fallbacks, rightsizing recommendations, shared credential slots, other client
integrations, and partial lifecycle state. The provider or affected routes are disabled before a
destructive external stage so no new dispatch can enter the shrinking surface. Existing sessions
must finish or receive explicit interruption approval.

A default provider cannot be removed until the operator explicitly establishes a replacement or
shuts routed mode down; no alternative is selected automatically. A credential slot cannot be
revoked while another admitted route depends on it. Provider confirmation is required for an
`upstream-revoked` claim. Local logout or slot removal without that proof is reported as
`local-credential-removed; upstream-revocation-unknown`.

Removing `openai-codex` revokes or removes only the selected OCX credential slot and provider
state; it never signs the operator out of native Codex, ChatGPT, or Claude. Removing the final
routed provider returns status to the successful native-only starting state. A partial removal is
receipt-backed and fail-closed; recovery never recreates a revoked credential or chooses a new
default. Historical configuration, probe, qualification, removal, and incident evidence remains
local and inactive for diagnosis. Product-managed deletion is deferred until a concrete need
justifies a separate contract.

### Refusal, partial effects, and recovery UX

Route-control commands use effect-aware exits. Exit 0 means a valid read-only report or a fully
closed requested lifecycle result; blocked route dimensions may still appear in a successful
query. Exit 2 means command or input grammar error. Exit 3 is a clean refusal before any
credential, configuration, integration, process, network-canary, or external revocation effect.
Exit 4 means at least one admitted stage began and the resulting effect is known partial or
unknown. Unexpected internal failure remains exit 1 and cannot be relabeled as refusal.

Every terminal result has one closed machine envelope and BLUF human rendering: schema and
command, provider/route and plan identity, status, effect state, completed and unstarted stages,
blocked or disabled exact routes, receipt/recovery identity, retained evidence, and one bounded
next command. It contains no credential value, account identity, private endpoint body, prompt,
model output, or reversible encoding. A post-effect outcome is never called `refused`, and an
unprovable effect is `unknown`, not `none`.

Foreign or ambiguous ownership, unsafe credential channels, unsupported endpoints, stale approval,
changed plan input, declined hard gates, or an unadmitted client mutation refuse before effect.
Failed credential acceptance, configuration writes, sync, restart, catalog verification, probe,
or upstream revocation record the last proven boundary. A provider whose sync/restart or catalog
verification did not close remains disabled in `partial-onboarding`; an interrupted removal stays
disabled and cannot silently reappear as configured or absent.

`ccodex routes recover <provider>` is read-only by default. It validates every stage receipt,
current prestate, ownership, gateway identity, credential acceptance category, client-integration
digest, and catalog observation, then proposes either the exact remaining stages or an explicit
compensating plan. Apply requires the new digest and any still-applicable hard gates. Recovery
does not repeat authentication, revocation, config mutation, sync, restart, session interruption,
or live probe from intent alone; it never selects another provider/default/slot or invents
rollback. Unknown external effects remain unknown until independent evidence closes them.

### Release acceptance and compatibility

The route-control release gate is deterministic and offline. Its fixtures cover the closed
first-party profile schema and operator-defined constraints; the successful native-only state;
stable human and versioned machine envelopes; plan-digest invalidation; secret and account-data
redaction; unsafe credential-channel, endpoint, and Anthropic-impersonation refusals; every staged
crash boundary and concurrent-writer refusal; configured-but-not-live fallthrough prevention;
client-scope preservation; one-slot route identity; the `openai-codex` and Muse prototype paths;
probe-versus-qualification separation; layer-specific drift; disable, credential revocation,
removal, and recovery; and the exact exit 0, 1, 2, 3, and 4 meanings. Tests use synthetic state,
catalogs, attribution, and credential-status categories and require no provider credential or
network access.

Live login, catalog, attribution, billing, probe, and revocation canaries remain separate,
explicitly approved operator operations. They may qualify the tested route and release/runtime
combination, but they are never a repository gate leaf and their absence cannot make native-only
use fail. Supported-platform claims name only combinations with current lifecycle, credential-
front-door, gateway, redaction, and recovery evidence; an unverified platform fails closed rather
than inheriting another platform's claim.

For one release, `ccodex providers`, `ccodex models`, and `ccodex status` are deprecated read-only
compatibility entries for `routes list`, `routes show`, and `routes status`. They return the same
versioned facts and cannot authenticate, sync, restart, probe, qualify, repair, or mutate. The
bounded low-level `ccodex configure` surface is also deprecated for one release, but it never
accepts or forwards a credential in an argument, URL, prompt, plan, receipt, or output; a provider
operation whose upstream form cannot use an admitted front door refuses cleanly. Unknown upstream
verbs continue to fail closed. Removal of these compatibility entries requires release notes and
an explicit subsequent lifecycle decision rather than silent disappearance.

The release documentation includes six executable narratives: successful native-only use;
`openai-codex` as the primary routed journey; Muse as the second-provider example; a clean
pre-effect refusal; partial onboarding and digest-bound recovery; and disable, provider-owned
credential revocation, removal, and return to native-only. Each narrative shows the dimensional
status before and after, declared data egress, exact approval gates, effect-aware result, retained
evidence, and one bounded next command without exposing credential or account identity.
