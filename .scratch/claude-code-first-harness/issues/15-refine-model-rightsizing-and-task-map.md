# Refine `/sdlc-rightsize` and the model-task map

Type: grilling
Status: resolved
Blocked by: 06, 07
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What exact discovery, research, evaluation, calibration, and refresh process should
`/sdlc-rightsize` use to turn available native-Claude and qualified OCX routes into an
evidence-backed model-task map? Define the semantic task taxonomy, provider/model/effort/context
mapping, confidence and constraint fields, authorization and egress boundary, qualification
inputs, fallback ranking, operator overrides, artifact lifecycle, and failure behavior.

## Observed current truth

The selected checkout already owns the paired Sol/Fable, Terra/Opus, and Luna/Sonnet calibration,
the bounded evaluator, `model-task-map/v2`, and exact receipt-admission boundary. The globally
installed `model-tier-rightsizing` skill currently resolves to another checkout that still carries
the older Claude-only tier table. Treat that mismatch as installation/repository drift for the
later truth-reconciliation task; it is not desired product policy and does not amend this ticket's
selected-checkout evidence.

## Decisions

### Capability, evaluation, consequence, and route taxonomy

Rightsizing uses four layers. `CapabilityDemand` records provider-neutral task facts.
`EvaluationClass` supplies a stable benchmark and qualification bucket. `WrongOutputClass`
determines the semantic tier. Only then may current evidence select an exact route.

The evaluation classes are `mechanical_redo`, `deterministic_gated_change`,
`evidence_extraction`, `repository_discovery`, `semantic_implementation`, `semantic_review`,
`integration_reconcile`, and `scale_setting_or_load_bearing_judgment`. The last replaces v2's
misleading `authority_or_frontier`; models may analyze authority boundaries but never hold
authority. Version 2 remains readable, and the rename plus `CapabilityDemand` binding enters a
versioned v3 migration rather than an in-place rewrite.

`WrongOutputClass` is `redo`, `retry`, `degrade`, or `derail`, mapping respectively to mechanical
floor, capable volume, judgment workhorse, or frontier. A real complete control may lower the
class; importance or confidence alone cannot. A role has no fixed class or tier. One node has one
primary evaluation class plus cross-cutting risk tags. If it genuinely spans multiple classes,
split it into separately checked artifacts. Qualification remains class-specific and never
transfers from implementation to review or load-bearing judgment.

After classification, the map still hard-filters context, transport, identity, semantic control,
local qualification, and runtime admission before recommending an exact route.

### Exact-route discovery and candidate admission

`discover` is read-only and makes no inference calls. It reads only the selected distribution's
bound ccodex/OCX tools, raw served catalog, configured-provider registry, checked runtime policy,
and PII-stripped Claude subscription status. It never reads or prints credential values, email,
organization identity, or unrelated provider configuration, and it never repairs, syncs,
restarts, configures, or authenticates a provider.

An exact route tuple records transport surface and kind, provider and lane, wire/API form,
authentication and billing basis, region or endpoint identity where relevant, exact requested
model ID, effort and context form, tool compatibility, and identity-readback basis. The route ID
digests the whole tuple. Nominally identical models on different routes qualify separately.

Keep registry presence, configured state, running-catalog membership, correlated route probe,
class qualification, runtime-policy admission, and published support independent. Never emit a
model-wide `available` boolean. Registry-only and configured-but-unserved providers are diagnostic,
not selectable; report exact activation guidance without mutation. Live OCX rows and usable
Claude-subscription passthrough form the candidate universe, but passthrough is not fabricated as
an OCX provider. Aliases, family guesses, host defaults, and free-text IDs remain blocked until
they resolve to an exact route.

Mined evidence may prioritize an exact catalog candidate for probing but cannot make it
selectable. Probes require a separately approved live plan, use synthetic data by default, and run
only as direct bounded evaluator canaries. Ambiguous identity limits or blocks qualification.
Discovery failure returns partial diagnostics and blocked candidates rather than silently choosing
a default source set.

### Class-qualified evaluation and promotion

Rename v2's `role-qualified` state to `class-qualified` in v3 because qualification belongs to an
`EvaluationClass`, not permanently to a role. Evaluation depth is `probe`, `pilot`, or
`qualification`; a refresh is another qualification run rather than a weaker fourth depth. The
qualification identity binds task pack, harness, runtime, model settings, exact route, and class.

Task packs are versioned and digest-bound, with at least five distinct held-out tasks per selected
class and three attempts per task. They declare hidden or immutable expected results, tools,
context and output needs, sensitivity, criticality, and verifier. Include gold, no-op, malformed,
and known-failure fixtures where applicable. Target content needs egress approval, evaluation uses
isolated copies, and the model receives no unbounded shell, web, worker, workflow, or fallback
surface.

Promotion requires at least 90% accepted attempts, a two-sided 95% Wilson lower bound of 0.70,
zero transport or identity failures, and zero critical-task failures. Every
`scale_setting_or_load_bearing_judgment` task is critical. High-variance or high-consequence packs
may require more evidence.

Verifier strength matches the class: exact/schema/diff/compiler checks for mechanical work;
immutable evidence and coverage for extraction/discovery; executable gates and acceptance
criteria for implementation/integration; seeded findings, false-positive and omission controls,
and independent adjudication for review; independent re-derivation plus human rubric adjudication
for load-bearing judgment. An LLM judge alone never qualifies a route.

The evaluator renders an exact no-call plan and authorization digest before live calls, runs
serially by default for clean attribution, and uses a separately approved pack for concurrency.
It records transport, identity, verifier, task, timeout, malformed, empty, and budget failures
separately. Qualification never mutates target, configuration, production pairs, or runtime
policy. `class-qualified` plus exact runtime-policy admission may make a route dispatchable in the
map; neither authorizes spawn.

### Pareto fronts, complements, fallbacks, and overrides

Each class has a `measured_pareto_front` over compatible local evidence and a
`dispatch_pareto_front` that additionally requires class qualification, runtime admission,
context fit, tools, and policy. Hard filters run before comparison. Maximize the locally observed
accepted-rate lower bound, minimize route/identity failure, and minimize one operator-selected
dimension: observed cost, tokens/quota, or wall time. Retain all other metrics. Never emit one
weighted global score; missing values remain incomparable. Subscription marginal cost is `null`,
with API-equivalent cost and quota recorded separately. Confidence remains structured attempts,
intervals, failures, pack, harness, freshness, and provenance rather than one number.

`primary` is one exact dispatchable route. `complement` produces a distinct artifact or independent
control and never exists for vendor tokenism. `fallback` is an ordered, preapproved exact route
that preserves class, gate, sensitivity, tools, and authority boundary.

Retry the same route once only for an eligible transient or malformed-output failure. Reduce
concurrency before switching on capacity pressure. Identity mismatch or default-provider
fallthrough stops and quarantines the route. Cross routes only within the approved egress and
budget envelope and only to class-qualified, admitted alternatives. Never silently weaken effort,
context fit, controls, or consequence class. Escalate upward when semantic uncertainty survives a
gate; otherwise decompose or stop.

Operator preferences may restrict providers, routes, spend, quota, latency, context, egress, or
vendor diversity and may select a non-Pareto but dispatchable route with rationale. They cannot
promote, bypass identity/admission, recast mined evidence, force a lower tier, or create an
unapproved fallback. Preserve the evidence-ranked baseline and declared override separately.

### Product surface and native-Claude route coverage

`/sdlc-rightsize` is Claude Code's interactive front end. It gathers bounded operator choices,
explains the proposed calls and consequences, invokes the deterministic rightsizing control
plane, and presents the plan for approval. It never delegates or uses an ordinary workflow worker
as the evaluator. `ccodex sdlc rightsize` is the installed cross-host control plane for ordinary
native Claude and OCX-backed routes, using the release-bound tools. `mise run rightsize:evaluate`
remains a contributor-checkout compatibility entry point, not the installed product boundary.

The deterministic CLI owns `discover`, `status`, `plan`, `evaluate`, and `render`; `plan
--refresh` constructs a replacement-calibration plan rather than weakening refresh into an
implicit update. A dry run stops after the no-call plan. Evaluation never spawns workflow roles
and never changes provider configuration, runtime policy, Seeds, trust, or a production target.

Version 3 distinguishes `native-claude-subscription`,
`gateway-claude-subscription-passthrough`, and `gateway-routed-provider` route kinds. Native
Claude is a first-class candidate, not an assumed baseline. A native candidate becomes
dispatchable only when the selected host can inject the exact requested model and effort and the
run yields sufficient correlated identity evidence. Otherwise it is an `unresolved-native-route`
and remains non-dispatchable. A native route and a gateway passthrough to the same Claude model
are separate exact routes with separate evidence.

Before a live call, the authorization digest binds the target, discovered catalog and selected
routes, task pack and attempts, providers and target-data egress, subscription or usage-credit
capacity, monetary/token/time/call budgets, output locations, benchmark policy, evaluator
version, and stop conditions. Any change invalidates approval. An approved evaluation run
produces evidence only; it grants no authority to dispatch production work or mutate an outward
system.

### Shared routing intent and immutable local evidence

Portable repository policy and measured machine-local evidence are separate authorities. A
tracked rightsizing section in `.agentic-sdlc/repo.toml` may declare provider-neutral constraints,
preferences, selected optimization objective, sensitivity and egress limits, and versioned task
pack references. It never asserts that an exact live route is configured, qualified, admitted, or
available. Exact provider credentials, subscription state, route measurements, and qualification
claims remain operator-, target-, host-, and toolchain-specific local evidence.

The authoritative local store lives under the ccodex XDG state plane and is keyed by stable target
and host identities. Each approved evaluation writes one immutable
`generations/<calibration-id>/` containing the v3 map, rendered explanation, evidence summary, and
closed generation manifest. Only after every artifact and digest validates does an atomic small
`current` manifest select that generation. An incomplete or failed generation never replaces the
last complete one. Generated artifacts are immutable; an edited artifact is `modified` and
non-dispatchable rather than silently re-signed. Operator overrides belong in portable policy or
the approved run specification, while the evidence-ranked baseline and effective override remain
separate in the generated map.

The v3 map binds its schema and taxonomy, calibration and target identities, environment,
distribution/tool, policy, catalog, task-pack, evaluator, benchmark, and evidence digests. It
records the approved run specification; exact route registry and independent evidence states;
class recommendations; structured confidence; measured and dispatch Pareto fronts; baseline and
effective override; blockers, staleness, kill state, and authority limits. Evidence records
metrics, verifier results, identity receipts, and content digests, but never credentials, PII, raw
prompts or completions, transcripts, repository content, or mutable absolute paths.

An explicit export may publish a sanitized immutable generation for review or CI comparison. It
cannot become dispatchable on another host unless all required environment and policy digests
match and that host independently satisfies runtime admission. Version 2 remains readable and
may be converted structurally, but migration cannot manufacture v3 class qualification,
identity evidence, or freshness.

### Refresh, expiry, and quarantine

A qualification certificate is current for at most 30 days. Repository policy may require a
shorter interval but cannot extend that safety maximum. `status` is a read-only comparison of the
selected immutable generation with current discovery, policy, and environment facts; it makes no
model calls and reports each affected route/class cell as `current`, `refresh_due`, `expired`,
`invalid`, `quarantined`, `modified`, or `unresolved` rather than reducing the map to one healthy
boolean.

An identity mismatch, selected-route removal, critical regression, explicit revocation, or change
to the exact qualification identity immediately invalidates and quarantines only the affected
cell. A qualification-identity change includes its route tuple, task pack, harness, runtime,
settings, class, verifier, or load-bearing policy digest. Unrelated catalog additions do not
invalidate existing cells. Pricing, quota, observed latency, new candidates, mined-evidence
updates, and compatible catalog growth mark affected cells `refresh_due`; a still-current cell
may remain eligible until its expiry unless repository policy is stricter.

`plan --refresh` selects only cells whose state or operator selection requires new evidence, then
renders a new exact authorization digest. It never reuses an earlier approval for changed calls,
data, routes, budgets, or outputs. Version 3 performs no background model calls or silent
auto-refresh. A failed refresh leaves the last complete generation selected, but status continues
to enforce that generation's real expiry or invalidity; an expired, invalid, quarantined,
modified, or unresolved cell remains historical and cannot dispatch. If no current qualified and
admitted route remains, the workflow stops, decomposes, or requests a newly approved evaluation.

Mined benchmark evidence has an independent 90-day maximum age and refreshes when its pinned
source revision or extraction policy changes. When stale, it is excluded from candidate ordering
and remains provenance-only history. Its expiry never invalidates locally observed
qualification. Refresh preserves the previous and replacement generations for comparison rather
than rewriting the old evidence.

### Curated research ingress

`discover`, `status`, and `evaluate` never browse the web. The release carries a digest-bound
research index: primary provider documentation supplies declared model, context, tool, region,
retention, price, and quota claims, while methodologically transparent independent benchmarks
may supply mined candidate evidence. Every claim binds its source and retrieval date, exact
model/version where the source exposes one, methodology and harness, task-class fit, licence, and
stored artifact digest. A citation without retained claim provenance is not admissible research
evidence.

Preserve contradictory claims as separate records with scope and provenance; never average them
into a provider-wide or global model score. Numeric results are comparable only inside a
compatible benchmark, harness, model configuration, and evaluation version. Cross-benchmark
normalization may explain differences but cannot create a ranking or fill a missing result.
Provider-declared facts may establish conservative feasibility constraints. Mined results may
nominate or order an already discovered exact candidate for an approved local evaluation.
Neither evidence class proves live route identity, qualifies a class, establishes runtime
admission, or substitutes for target-representative observed evidence.

An operator may add an explicitly selected, sanitized evidence bundle to a plan. The bundle is
schema-validated, content- and source-digest-bound, included in the authorization digest, and
subject to the same provenance and expiry rules; importing it performs no network or model call.
Unbounded scraping, implicit web research, mutable URLs as evidence, credentialed source access,
and benchmark terms that forbid the intended storage or use are out of scope. Retraction,
unverifiable provenance, licence conflict, or source-integrity failure quarantines that research
claim and removes it from candidate ordering, without invalidating independent local
qualification.

### Post-call effects, exits, and quarantine

Command completion and route health are independent facts. Query commands return success when
they produce a valid closed report even if it reports no current generation or only blocked
cells. A valid no-call plan, deterministic render, or fully closed evaluation result also returns
exit 0; a completed evaluation may truthfully be `not-qualified`. Invalid command or input grammar
returns exit 2. A policy, precondition, or authorization refusal before the first live call returns
exit 3 and proves `effect_state: none`. An interrupted, failed, or quarantined run after at least
one live call returns exit 4. An unexpected internal failure returns exit 1 and must not be
misreported as a clean refusal.

Before the first call, the evaluator durably opens a redacted append-only effect journal bound to the
authorization digest. After every attempted call it records the exact route ID, attempt and
request correlation, usage and budget observations, verifier/failure class, and effect state,
without retaining forbidden content. Terminal state distinguishes `completed`,
`completed-not-qualified`, `refused-before-call`, `failed-after-call`, `interrupted-after-call`,
and `completed-quarantined`. At a proven terminal boundary it finalizes an immutable rightsizing
run receipt bound to the journal digest; otherwise the journal remains the recovery evidence. A
post-call outcome is never described as `refused`, and an
unprovable post-call effect is `unknown`, not `none`.

Only a fully closed qualifying replacement generation may advance `current`. An incomplete or
nonqualifying refresh remains historical and preserves the prior pointer. This preservation does
not hide adverse evidence: an observed identity mismatch or critical-task regression durably
writes a quarantine record for the affected exact route/class cell before terminal exit. Status
and dispatch admission apply that record over any older generation. Capacity, budget, ordinary
transport, and noncritical quality failures do not manufacture quarantine, although they remain
visible in the receipt or open journal and may make qualification fail.

Preference overrides and manual acknowledgement cannot clear route quarantine. Only a successful
fresh qualification under the current route, class, policy, harness, and runtime identity clears
it as part of one atomic generation transition. Until then the cell is non-dispatchable; another
independently qualified and preapproved route may still serve the class. Every machine-readable
command result uses a closed envelope containing schema version, command, status, effect state,
target and plan or generation identity where applicable, blockers, and a bounded next action.

### Retention and migration; history deletion deferred

Rightsizing follows the product's local-evidence retention contract. The selected generation and
every artifact it references, active quarantine records and their supporting evidence, and open
or unknown-effect run journals are protected evidence and have no routine expiry. Superseded,
failed, and nonqualifying generations plus completed content-minimized run receipts remain for at
least 90 days and, in version 1, are not automatically deleted. Authority-free discovery caches
expire after 30 days and are size-bounded. Explicit redacted debug logs are off by default and
expire after seven days; these disposable surfaces are not qualification history.

Version 1 has no product-managed evidence-history prune or purge command. Uninstalling ccodex,
removing a provider, migrating a schema, or retiring a skill preserves rightsizing generations,
run receipts, effect journals, quarantine evidence, and published exports. Unknown-effect evidence remains until
the effect is resolved or a warned abandonment is recorded; abandonment does not erase the
history or claim that the external effect was absent. A future history-deletion feature requires
a new decision covering privacy/compliance need, dependency closure, ownership, safe selection,
recovery, and foreign or modified artifacts.

Schema migration writes a new immutable generation or compatibility view and preserves the
original. It validates closed digests and ownership before mutation, reports unsupported fields,
and never upgrades provenance, qualification, freshness, identity, or runtime-admission strength.
Deprecated schemas retain a documented read or explicit migration path for their stated support
window; retirement never makes retained evidence silently unreadable.

### Release acceptance

`mise run check` remains an offline deterministic gate. It never performs a model call, live
provider discovery, authentication, paid evaluation, or other network operation. Closed-schema
and golden tests cover v3 maps, evidence, plans, command envelopes, run receipts, generation
manifests, current selection, quarantine, and research ingress. They reject unknown and duplicate
members, malformed values, digest tampering, forbidden content, cross-target or cross-host reuse,
and any v2 migration that attempts to manufacture stronger evidence.

No-call tests prove that `discover`, `status`, `plan`, and `render` neither invoke a model nor
mutate provider, host, repository, trust, or runtime configuration. Route fixtures cover
ambiguous native identity, gateway default-provider fallthrough, effort and context divergence,
removed catalog rows, configuration/catalog disagreement, stale or modified evidence, and
runtime-policy refusal. Statistical fixtures verify task-pack admission, thresholds, confidence
intervals, Pareto construction, missing-data incomparability, baseline and override separation,
complements, and exact fallback ordering.

Fault-injection and concurrency tests exercise every durable boundary for run receipts,
generations, current selection, quarantine, retention, abandonment, and migration. Tests
prove post-call exit and effect semantics, recovery after partial writes, one-writer behavior,
and preservation of foreign or modified state. Redaction fixtures include credentials, PII,
source and prompt content, model output, transcripts, paths, reversible encodings, and
secret-shaped values. A safe serializer failure stops persistence rather than emitting a partial
record.

Installed `/sdlc-rightsize`, `ccodex sdlc rightsize`, and the contributor `mise` entry point use
the same deterministic engine and release-bound tools and produce the same canonical plan and
artifacts for identical inputs. Installed use does not depend on repository-scoped mise or a
caller-PATH substitute. Live provider canaries are separate, explicitly approved,
cost-and-egress-disclosed certification operations; they are never repository gate leaves or
release prerequisites. A support claim applies only to the exact platform, host/launcher,
transport, provider, route, model, effort, context, tool surface, and evidence tuple that passed
its current conformance contract.
