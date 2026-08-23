# Agentic SDLC Product

Agentic SDLC is a Claude Code-first opinionated delivery harness. It adds lifecycle, workflow,
routing, repository-hygiene, and evidence controls without replacing the host coding agent.

## Language

**Agentic SDLC**:
The product and methodology: a Claude Code-first, evidence-driven SDLC harness for greenfield and
brownfield repositories whose primary execution substrate is Dynamic Workflows.
_Avoid_: General multi-host framework, replacement coding-agent runtime

**Agentic SDLC Core**:
The sufficient native-Claude product path, including owned activation and workflow contracts,
that requires no gateway, external provider, or companion library.
_Avoid_: Crippled edition, all first-party profiles, routed-model profile

**Dynamic Workflow**:
Claude Code's JavaScript orchestration primitive for coordinating bounded agents and their
artifacts. Agentic SDLC uses it as the primary execution substrate.
_Avoid_: Generic workflow, background agent

**Companion host**:
A non-Claude host that consumes portable skills and shared contracts where its capabilities
permit. A companion host is not promised equal feature parity with Claude Code.
_Avoid_: Peer host, fully supported host

**Companion library**:
An external skill or agent library that remains outside Agentic SDLC ownership and uses its own
installation, update, and removal lifecycle through an explicit operator action.
_Avoid_: Bundled library, vendored dependency

**Compatibility tuple**:
The exact Agentic SDLC release, host/version, OS/architecture/runtime boundary, installation plane,
capability evidence, and optional profile/dependency combination evaluated for support.
_Avoid_: Supported platform, latest-compatible, provider-wide support

**Minimum compatibility requirement**:
The lowest host version and feature prerequisites eligible to run one Agentic SDLC surface,
subject to current capability admission rather than an exact-version allowlist.
_Avoid_: Certified tuple, maximum version, works on every newer release

**Support tier**:
The evidence classification of one compatibility tuple as certified, capability-qualified,
experimental, or unsupported.
_Avoid_: Marketing maturity, host parity, installation success

**Release channel**:
The operator-selected stable or preview stream whose exact Agentic SDLC release is resolved and
pinned through mise.
_Avoid_: Source branch, support tier, moving latest tag

**Deprecation window**:
The published interval in which a stable surface warns, preserves compatibility, and provides a
replacement before its named removal release.
_Avoid_: Silent removal, indefinite support, emergency safety refusal

**Repository activation**:
The assess-plan-apply `/sdlc-init` process that makes an individual repository ready for Agentic
SDLC work. Assessment and planning are read-only; an exact digest-approved plan may add owned
baseline entries or preserve and integrate around existing repository contracts.
_Avoid_: Full cleanup, global bundle installation

**Greenfield activation**:
Repository activation where no established guidance, toolchain, tracker, hook, or CI contract
occupies the relevant surfaces. Application-code age does not determine this classification.
_Avoid_: New repository, empty repository

**Brownfield activation**:
Repository activation where at least one relevant operating-contract surface already exists. It
uses minimum-compatible integration and durable hygiene waves rather than immediate replacement.
_Avoid_: Old codebase, mandatory cleanup

**Repository guidance contract**:
The host-neutral operating instructions whose canonical source is `AGENTS.md`. An owned
`CLAUDE.md` projects the same contract for Claude Code; pre-existing foreign guidance is preserved
until explicitly reconciled.
_Avoid_: Competing canonical instruction files, silent guidance merge

**Authoritative queue**:
The single durable work tracker admitted for an activated repository. Seeds is the greenfield
default until the operator selects another adapter that proves the required identity, dependency,
acceptance, evidence, and concurrency contract.
_Avoid_: Seeds-only product, parallel shadow queues, chat TODOs

**Architecture Decision Record**:
A durable record of a significant, hard-to-reverse choice, its context, and rejected alternatives.
Greenfield repositories use a MADR-compatible lifecycle; brownfield repositories may retain an
existing convention that preserves equivalent lifecycle and relationship evidence.
_Avoid_: Status report, implementation plan, record of every small choice

**Domain glossary**:
The repository's canonical definitions for meaningful domain terms, normally recorded in
`CONTEXT.md` and created only when terms need durable clarification.
_Avoid_: Empty scaffold, general documentation index

**Authoritative gate**:
The single repository command, `mise run check`, whose pinned integrated result is required before
Agentic SDLC may call a repository snapshot gate-passing. Hooks and partial tasks are supporting
evidence, not substitutes.
_Avoid_: CI-only gate, passing pre-commit hook, arbitrary test command

**Repository activation diff**:
The reviewed unified diff `instruction-generator.py apply` prints for one marked instruction block,
approved and written in the same invocation. Its durable record is the repository's own Git
history; there is no tracked contract manifest and no machine-local activation receipt.
_Avoid_: Proof of activation, readiness claim, ownership evidence

**Write custody**:
The exclusive assignment of one write-capable workstream to one owner, branch, and worktree, with
existing user work inventoried and preserved before mutation.
_Avoid_: Shared worker checkout, implicit ownership of dirty paths

**Rebase-then-squash fan-in**:
The default integration strategy: the authorized integrator rebases an accepted workstream onto
the current integration base, re-admits the changed identity and delta, then squash-merges it as
one traceable unit before integrated review.
_Avoid_: Worker merge, unreviewed rebase, outward default-branch merge

**Write-ready**:
The repository state in which portable intent and local receipt agree, custody and trust are
admitted, guidance and queue are usable, and `mise run check` passes. Normal delivery waves may
write only from this state.
_Avoid_: Activated, configured, remediation-ready

**Remediation-ready**:
A constrained brownfield state with exact known gate failures but no blocking credential,
ownership, trust, or target-path conflict. Only named hygiene waves may write, and their honest
verdict is `remediation-progress` until the repository becomes write-ready.
_Avoid_: Gate-passing, normal delivery ready, accepted failure waiver

**Product plane**:
One bounded ownership and authority surface: distribution lifecycle, Claude host, routing,
repository, local evidence, or an external system. Crossing planes requires a declared data and
authority contract.
_Avoid_: Trust zone shared merely because one agent invoked it

**Operational evidence**:
Content-minimized receipt data such as hashes, versions, route IDs, timestamps, result classes,
counts, approval digests, and artifact references. It proves lifecycle or workflow facts without
copying secret or sensitive bodies.
_Avoid_: Transcript copy, base64 secret, raw prompt or source body

**Evidence receipt**:
An immutable typed terminal record of an operation's proven scope, result, effect state, and
evidence references. It records facts but grants no approval, admission, or outward authority.
_Avoid_: Transcript, mutable log, authorization token

**Effect journal**:
A content-minimized append-only record opened before an admitted effect and retained as recovery
evidence while the operation is active, partial, or unknown.
_Avoid_: Final receipt, transcript, proof of rollback

**Credential custody**:
The provider or host plane that owns a credential's value and lifecycle. Agentic SDLC may observe
a readiness state or invoke an approved front door, but it does not copy or become custodian of
Claude or external-provider credentials.
_Avoid_: Credential availability, shared credential store, encoded credential receipt

**Declared egress**:
A preapproved network transmission contract naming destination, purpose, data classes, call/cost
budget, and external retention boundary. A changed endpoint, data class, or purpose requires new
approval.
_Avoid_: Anonymous telemetry exemption, implicit online mode

**Main usage**:
Top-level non-delegated model usage in the operator session, with answer-producing and background
or classifier lanes kept distinct.
_Avoid_: All session usage, agent usage, provider total

**Agent usage**:
Usage owned by standalone subagent roots or workflow-owned roots, including nested attempts once
under their owning root.
_Avoid_: Main usage, double-counted nested usage, host all-entry total

**Accounting certainty**:
The evidence quality of a usage or cost value: exact, lower-bound, unpriced, missing-usage, or
stale.
_Avoid_: Unknown as zero, estimated charge as billed cost, confidence score

**Operation-specific approval**:
Human authorization bound to an exact plan digest, scope, routes, egress, budgets, and validity
conditions. Evidence, agent output, or approval of another operation cannot substitute for it.
_Avoid_: General consent, passing gate, subagent approval

**Approval state**:
The digest-bound lifecycle classification of one approval requirement as missing, pending,
granted, declined, expired, or superseded.
_Avoid_: Gate result, agent recommendation, chat acknowledgement

**Redacted incident receipt**:
A content-minimized terminal record of possible credential, private-content, or undeclared-egress
exposure that supports containment without reproducing the suspected material.
_Avoid_: Incident transcript, external report, proof of exposure absence

**Mechanical control**:
A safety property enforced at a process, filesystem, network, argument, identity, or transaction
boundary and covered by adversarial tests.
_Avoid_: Prompt instruction, warning, observed outcome

**Observed evidence**:
An independently measured post-execution fact. It may detect substitution or failure but cannot
retroactively authorize an action.
_Avoid_: Requested value, mechanical guarantee

**Advisory control**:
A behavior requested through prompts, documentation, warnings, role definitions, or review policy.
It must not be presented as enforced.
_Avoid_: Fail-closed protection, verified runtime fact

**Sensitive content**:
Non-credential material such as source, prompts, model output, private URLs, paths, identities, and
issue bodies whose storage and transmission remain confined to an owning plane and declared egress.
_Avoid_: Public metadata, safe receipt body

**Product telemetry**:
Usage or diagnostic data transmitted by Agentic SDLC for product analytics. The first release has
none; external platforms' own telemetry remains a separately disclosed boundary.
_Avoid_: Local metrics, approved task egress, provider telemetry

**BLUF communication**:
A human or agent message that states its outcome, decision, failure, or requested action first,
then supplies only the evidence needed to act. Machine-readable handoffs place this bottom line in
a stable summary field.
_Avoid_: Preamble, hidden verdict, evidence-free compression

**Countable-clarity profile**:
The product's controlled-writing default for new or materially revised prose. It uses measurable
sentence, paragraph, noun-cluster, instruction, voice, list, and terminology rules while preserving
technical meaning and evidence strength.
_Avoid_: ASD-STE100 conformance, automatic brownfield rewrite, prose quality score

**SimpleEnglish adaptation**:
Five re-expressed clarity ideas added to the incumbent first-party profile with exact donor
provenance: condition-first commands, explicit referents, direct verbs, punctuation/localization
audit flags, and located meaning-preserving rewrite candidates.
_Avoid_: Vendored skill, copied vocabulary table, separate output style

**Public clarity rule shapes**:
The maximum useful subset of publicly supportable ASD-STE100-inspired mechanics that fits software
writing, requires no licensed dictionary, and preserves technical meaning and evidence strength.
_Avoid_: ASD-STE100 compliance, reconstructed dictionary, rule-count maximization

**Documentation review pass**:
An independent clarity review for high-consequence artifacts that reports countable violations,
terminology drift, ambiguity, and meaning-preserving rewrite candidates without deciding technical
correctness or changing evidence strength.
_Avoid_: Technical approval, automatic rewrite, prose-linter verdict

**Prose check**:
An advisory mechanical report of named clarity rules, locations, counts, and meaning-preserving
rewrite candidates. A target repository may explicitly promote a proven subset, but a score never
establishes writing quality or technical correctness.
_Avoid_: Default gate, ASD-STE100 verdict, automatic rewrite authority

**Traceable claim**:
A substantive statement whose evidence class and nearby source pointer let a reader recover its
origin. Provenance does not make the claim correct or authorize an action.
_Avoid_: Decorative citation, approval by reference

**Core-shipped optional capability**:
A first-party skill and safe source-authoring surface distributed with Agentic SDLC but selected
only for matching tasks. Heavy preview, render, or export runtimes remain separately provisioned.
_Avoid_: External companion, always-on rule, automatic runtime install

**Canvas diagram**:
An editable visual whose spatial composition, shape library, layers, or later graphical editing is
part of the required artifact. Concise text diagrams remain a different artifact class.
_Avoid_: Any diagram, rendered image, prettier Mermaid

**Diagram reference pack**:
Lazy guidance for one visual family beneath a diagram umbrella. It adds authoring and review
rules without becoming a separately selectable skill or owning a new lifecycle.
_Avoid_: Diagram skill, plugin, independent profile

**Security DFD**:
A typed data-flow model of processes, stores, external actors, directed flows, and trust changes.
It is an analysis input and visual artifact, not a complete threat model or security verdict.
_Avoid_: Architecture picture, completed threat model, STRIDE diagram

**Threat-modeling workflow**:
A separately selectable security analysis process that binds scoped system evidence to threats,
mitigations, verification, and independent challenge. People retain risk ownership.
_Avoid_: Security diagram, automated security approval, risk-acceptance agent

**Threat model**:
A scope-bound, evidence-linked account of a system model, threats, dispositions, mitigations,
verification, assumptions, and unresolved risk. It is never proof that the system is secure.
_Avoid_: Security DFD, vulnerability scan, security approval

**Stage fan-out**:
Bounded parallel work inside one admitted workflow stage, divided by disjoint scope or named lens.
Immutable candidates return to one designated fan-in owner.
_Avoid_: Shared artifact writing, recursive autonomy, majority-vote truth

**Threat ledger**:
The canonical agent-authored record of threat coverage, scenarios, proposed mitigations, owners,
verification conditions, and unresolved work for one scoped model.
_Avoid_: Human risk acceptance, vulnerability scan output, narrative handoff

**Risk disposition**:
A human-owned decision to prioritize, reject, defer, or accept a recorded threat under a named
policy. Agent analysis and review may inform but never create it.
_Avoid_: Agent recommendation, threat status, automated score

**Mitigation verification**:
Independent evidence that one current control satisfies named verification conditions for bound
artifacts. It does not accept risk, close work, or prove universal effectiveness.
_Avoid_: Implemented control, passing unrelated test, security approval

**Round-trip qualified**:
Version-specific evidence that an interoperability adapter preserves defined native semantics in
both directions across pinned fixtures, with accounted loss.
_Avoid_: Compatible, file opened, visually similar

**Unsupported profile**:
A threat model references a missing, retired, or unqualified model or method profile. Processing
stops with migration guidance instead of substituting another profile.
_Avoid_: Stale model, automatic upgrade, best-effort fallback

**Model profile**:
A versioned contract for the typed system representation that a threat-modeling method analyzes.
It defines structure and validation without asserting security.
_Avoid_: Diagram theme, method profile, renderer schema

**Method profile**:
A versioned, provenance-bearing analysis method applied to an admitted system model. It defines
questions and mechanical coverage, not risk priority or threat completeness.
_Avoid_: Risk policy, model profile, security certification

**Mechanical coverage**:
Evidence that every required profile unit has an explicit structured disposition. It says nothing
about whether the analysis found every real threat.
_Avoid_: Complete threat model, quality score, secure system

**Threat-model storage plane**:
The approved location, audience, access, retention, and egress boundary for one threat-model
artifact set. Local storage, repository tracking, and external storage are separate choices.
_Avoid_: Default repository path, implicit sharing, encrypted by assumption

**Threat-model freshness**:
The relationship between a model revision and its bound current inputs. Automation may detect
loss of freshness but cannot restore it without the required workflow and review.
_Avoid_: Security status, last-modified time, passing drift check

**Canonical diagram source**:
The editable canvas representation that owns a diagram's maintained content and binds every
derived view. An editable export remains a derivative, not a replacement source.
_Avoid_: Preview, rendered image, embedded-image metadata

**Method sidecar**:
A machine-readable semantic record bound to a diagram when a method has facts that visual
geometry cannot safely own. Stable references and digests expose drift between the pair.
_Avoid_: Render receipt, duplicate diagram, unbound metadata

**Render receipt**:
A provenance record that binds a derived visual to its canonical source and rendering context.
It proves the recorded derivation, not visual quality or factual correctness.
_Avoid_: Approval, source file, correctness verdict

**Strict authoring**:
The source policy for new or owned canvas diagrams. It admits only the bounded, deterministic
subset that the product can preserve, inspect, and validate without external content.
_Avoid_: Full draw.io compatibility, best-effort cleanup, renderer validation

**Preservation inspection**:
Read-only classification of an existing canvas artifact before ownership or mutation. Unsupported
content stays intact and blocks editing until an explicit resolution path is approved.
_Avoid_: Import, normalization, automatic repair

**Renderer certification**:
A platform-specific evidence contract for one exact rendering runtime and its isolation,
resources, inputs, outputs, and receipts. Vendor support for a platform is not certification.
_Avoid_: Application detected, export succeeded, cross-platform claim

**Diagram asset manifest**:
The provenance and admission record for a non-primitive stencil, icon, template, font, or shape
library. It identifies exact bytes and permitted use without transferring ownership.
_Avoid_: Remote asset search, mutable library URL, blanket renderer licence

**Domain diagram specialization**:
A separately selectable diagram capability whose domain workflow, semantics, validation, and
maintenance contract materially exceed the generic canvas umbrella.
_Avoid_: Diagram reference pack, icon theme, generic diagram type

**Selection conflict**:
An effective host exposes another capability whose trigger materially overlaps an owned selector,
making agent routing ambiguous even when their names differ.
_Avoid_: Exact-name collision only, automatic replacement, harmless duplicate

**Diagram retirement**:
Removal of an owned diagram selector or runtime while preserving maintained artifacts and a
documented read or migration path.
_Avoid_: Delete diagrams, silent schema abandonment, foreign-plugin removal

**Role agent**:
A permanently selectable agent definition with one recurring graph responsibility, a stable
artifact contract, and a distinct least-privilege boundary.
_Avoid_: Persona, subject expert, prompt style

**Task role**:
A workflow-local responsibility assigned to one graph node for a bounded mission. It gathers
promotion evidence without adding a permanent selector.
_Avoid_: Role agent, global persona, installed specialist

**Review lens**:
A named perspective applied within an existing independent review responsibility. It does not
create a new agent identity or authority boundary.
_Avoid_: Reviewer persona, approval, separate workflow

**SDLC documentarian**:
The permanent role agent that authors evidence-preserving documentation within a declared
documentation scope. A different role performs high-consequence documentation review.
_Avoid_: Technical decision-maker, documentation approver, general implementer

**Human risk owner**:
The person accountable under an organization's policy for threat priority and residual-risk
acceptance. No role agent, workflow verdict, or validator can substitute for that ownership.
_Avoid_: Threat-model author, security reviewer, agent approval

**Core role roster**:
The small set of permanently selectable role agents available to ordinary Agentic SDLC missions.
Task roles and optional specialist rosters do not enter this surface.
_Avoid_: Every specialist, Research OS roster, workflow node inventory

**RoleSubmission**:
The common conductor-capturable envelope through which every role reports scope, findings,
evidence, recommendation, blockers, unknowns, and its proposed next action.
_Avoid_: Authority grant, role-specific artifact, unstructured completion claim

**Role certification**:
Versioned evidence that one first-party role selects correctly, preserves its custody and
authority boundaries, emits its contract, and remains equivalent across supported hosts.
_Avoid_: Model qualification, prompt quality, successful single run

**Modified role**:
An installed first-party role projection whose content no longer matches its ownership receipt.
It is preserved during updates and no longer carries first-party certification.
_Avoid_: Custom role, foreign role, safe to overwrite

**First successful journey**:
Installation followed by repository activation and one reviewed wave under its admitted gate
contract, with traceable decisions and durable follow-up work. Brownfield remediation may end as
`remediation-progress` without claiming global write-readiness.
_Avoid_: Setup completed, repository fully cleaned

**Core installation**:
The Agentic SDLC surface that completes the first successful journey through ordinary Claude Code
and a native Claude account. It is route-aware but requires no gateway, external provider, or
companion library.
_Avoid_: Minimal installer, all available profiles

**First-party profile**:
An optional Agentic SDLC-owned capability with an explicit, receipt-backed lifecycle separate
from core activation. Examples include routed models, Research OS, operator UI, Linux Mermaid
rendering, and companion-host adapters.
_Avoid_: Companion library, automatic feature

**Routed-model profile**:
The optional first-party execution mode in which `ccodex launch` activates the OCX gateway for one
session so qualified non-Claude provider routes can be used by the same Agentic SDLC core. The
installed `ccodex` CLI alone does not start OCX or configure providers.
_Avoid_: Core requirement, replacement Claude runtime

**OCX gateway**:
The independent OpenCodex routing dependency used by the optional routed-model profile for exact
qualified routes.
_Avoid_: Agentic SDLC product, model provider, universal compatibility layer

**ccodex**:
The packaged operator CLI and distribution front door. Its `sdlc` namespace manages Agentic SDLC
lifecycle; its `routes` and launch surfaces manage optional OCX-routed sessions.
_Avoid_: Agentic SDLC product name, automatically active gateway

**Distribution acquisition**:
Installing and selecting an exact versioned `ccodex` release through mise. Acquisition makes the
operator CLI available but does not activate Claude entries, OCX, providers, profiles, or external
libraries.
_Avoid_: Core activation, product setup complete

**Core activation**:
The separately approved `ccodex sdlc install --host claude` operation that copies receipt-owned
Agentic SDLC entries from the reviewed distribution into the Claude host plane.
_Avoid_: Distribution acquisition, marketplace coexistence

**Reachable route**:
An exact provider/model route that appears in the live OCX catalog and can be requested. Reachable
is a discovery fact, not a reliability or support claim.
_Avoid_: Available model, supported model

**Qualified route**:
An exact provider/model and runtime combination with a current certificate from real workflow and
tool-use canaries plus independent route-identity evidence.
_Avoid_: Reachable route, model self-report

**Supported route**:
A currently qualified route combination published in the Agentic SDLC compatibility matrix with
maintained onboarding, diagnostics, and regression coverage.
_Avoid_: Entire supported provider, every catalog model

**Exact route tuple**:
The complete transport, provider, wire, authentication, billing, endpoint, model, effort, context,
tool, and identity-readback request being discovered or qualified.
_Avoid_: Model name, provider family, alias

**Route evidence state**:
One separately recorded fact about registry, configuration, live catalog, probe, class
qualification, runtime admission, or published support for an exact route.
_Avoid_: Available model, combined readiness boolean, provider-wide status

**Route readiness matrix**:
The independent provider-recognition, credential, configuration, gateway, catalog, probe,
qualification, admission, and support facts shown for one route-control scope.
_Avoid_: Ready provider, available model, combined health score

**Native-only starting state**:
A successful installation where the core runs through ordinary Claude Code while routed mode is
not activated and no external provider is required.
_Avoid_: Incomplete setup, broken gateway, default OCX provider

**Provider profile**:
A release-bound non-secret description of one reviewed provider onboarding shape, including its
namespace, transport, credential front door, endpoint rules, and disclosures.
_Avoid_: Supported provider, configured provider, model catalog

**Operator-defined provider**:
A user-owned non-secret provider profile outside the release catalog that gains no qualification,
runtime-admission, or published-support claim merely from being configured.
_Avoid_: Supported custom provider, inferred provider, bundled profile

**Route onboarding plan**:
A digest-bound ordered provider-lifecycle change that declares its configuration, credential,
egress, sync, interruption, verification, recovery, and evidence effects before mutation.
_Avoid_: Setup wizard intent, provider profile, route qualification

**Partial onboarding**:
A provider lifecycle where at least one external or local stage took effect but the admitted
terminal state was not reached, requiring receipt-backed resume or explicit compensation.
_Avoid_: Clean refusal, successful configuration, automatic rollback

**Credential slot**:
An opaque local selector for one provider-owned credential record that reveals neither the
credential nor the person's account or organization identity.
_Avoid_: API key alias, email address, credential copy

**Credential acceptance state**:
The bounded observation that one credential slot is absent, present but unverified, accepted,
needs interaction, expired or revoked, or unknown; it is not route evidence.
_Avoid_: Valid provider, qualified route, account inventory

**Client-scoped route onboarding**:
A provider lifecycle whose default mutation authority is limited to Claude-through-ccodex and
does not imply configuration of another OpenCodex client.
_Avoid_: Global OCX setup, package-install consent, all-client synchronization

**Namespaced route**:
An exact gateway model route whose provider segment is explicit and whose admission cannot fall
through to the gateway's default provider.
_Avoid_: Bare model ID, alias, provider default

**Configuration-complete provider**:
A provider whose admitted credential, non-secret configuration, gateway activation, and exact
catalog verification stages completed; its routes may still be unprobed and unqualified.
_Avoid_: Ready provider, qualified route, supported provider

**Codex-subscription route**:
An exact OpenAI route through ccodex that uses a separate OCX-held ChatGPT/Codex OAuth grant and
whose subscription billing remains distinct from native Codex login and OpenAI API-key usage.
_Avoid_: Native Codex session, OpenAI API route, Claude subscription route

**Gateway-native route**:
A bare exact model ID that the running gateway catalog and correlated attribution bind to one
fixed provider under versioned policy.
_Avoid_: Native Claude route, bare alias, default-provider fallthrough

**Single-slot route**:
An exact route whose authentication and billing identity is bound to one opaque provider-owned
credential slot from planning through post-call attribution.
_Avoid_: Provider account pool, interchangeable credentials, provider-wide route

**Credential-pool route**:
A separately versioned route whose admitted set of credential slots and deterministic selection
policy are part of its identity and evidence contract.
_Avoid_: Automatic account rotation, implicit quota fallback, single-slot route

**Route probe**:
An approved bounded synthetic canary that proves current transport and correlated identity facts
for one exact route and credential slot without establishing semantic capability.
_Avoid_: Provider test, class qualification, health check

**Layer-specific refresh**:
Renewal of exactly one provider-configuration, credential, route-probe, or class-qualification
evidence layer without silently renewing or mutating another.
_Avoid_: Update everything, setup repair, implicit requalification

**Blocking route drift**:
A change to exact route identity, credential slot, billing, provider mapping, or client scope that
invalidates affected probe and qualification evidence until explicitly reconciled.
_Avoid_: Compatible catalog growth, refresh due, provider-wide outage

**Class-qualified route**:
An exact route whose target-representative held-out evidence meets the stated thresholds for one
EvaluationClass under one bound task pack, harness, runtime, and model setting.
_Avoid_: Role-qualified model, generally capable model, runtime-admitted route

**Measured Pareto front**:
The non-dominated exact routes under compatible local pilot or qualification evidence before
production admission filters.
_Avoid_: Dispatchable routes, global leaderboard, weighted model score

**Dispatch Pareto front**:
The measured routes that also satisfy class qualification, runtime admission, context, tools, and
current policy for a bounded recommendation.
_Avoid_: Spawn authorization, operator preference, measured front

**Rightsizing control plane**:
The deterministic installed surface that discovers exact routes and plans, evaluates, and renders
evidence-backed maps without dispatching production work or changing route configuration.
_Avoid_: Model router, worker scheduler, evaluation authorization as spawn authority

**Unresolved native route**:
A native Claude candidate whose exact model or effort injection, or correlated identity evidence,
cannot be proved and is therefore non-dispatchable.
_Avoid_: Host default, subscription unavailable, alias fallback

**Shared routing intent**:
Portable provider-neutral constraints, preferences, and evaluation references that guide
rightsizing without claiming an exact route is locally qualified or usable.
_Avoid_: Model-task map, route certificate, host readiness evidence

**Calibration generation**:
One immutable, complete set of locally measured rightsizing artifacts bound to an approved run,
target, host, toolchain, policy, route catalog, and evidence identity.
_Avoid_: Mutable current map, shared routing intent, benchmark leaderboard

**Calibration state**:
The independent lifecycle classification of one calibration or route-class cell as current,
refresh due, expired, invalid, quarantined, modified, or unresolved.
_Avoid_: Available model, overall map health, newest timestamp

**Research evidence**:
Source-bound declared or mined model claims that may constrain feasibility or nominate evaluation
candidates but cannot establish route identity, local qualification, or runtime admission.
_Avoid_: Observed qualification, global model score, provider support claim

**Rightsizing run receipt**:
An immutable terminal evidence receipt binding one approved evaluation and its effect-journal
digest to calls, observed effects, budgets, failures, and final state.
_Avoid_: Qualification certificate, authorization, transcript

**Route quarantine**:
A durable dispatch block on one exact route-class cell caused by current identity mismatch or
critical regression and cleared only by successful current-policy requalification.
_Avoid_: Operator preference, expired certificate, manual acknowledgement

**Protected rightsizing evidence**:
Current-generation dependencies, active quarantine support, and open or unknown-effect run
receipts required for current admission or recovery.
_Avoid_: Inactive history, discovery cache, exported artifact

**Retained route history**:
Content-minimized lifecycle, probe, qualification, removal, and incident evidence that remains
local after provider removal or product uninstall and has no version 1 purge surface.
_Avoid_: Active provider configuration, credential store, disposable cache

**Clean route refusal**:
A route-control stop before any credential, configuration, process, network-canary, or external
revocation effect, recorded with effect state none.
_Avoid_: Partial onboarding, failed-after-effect, rollback

**Route recovery plan**:
A new digest-bound choice of exact remaining or compensating stages derived from admitted receipts
and current prestate after a partial or unknown route lifecycle effect.
_Avoid_: Retry setup, automatic repair, inferred rollback

**Observability spine**:
The local read-only projection that renders lifecycle, route, workflow, approval, effect, and
completion evidence without becoming another source of truth.
_Avoid_: Telemetry database, required dashboard, event warehouse

**Diagnostic report**:
A read-only explanation of missing, contradictory, stale, foreign, partial, or unknown evidence
with bounded follow-up checks and no implied repair authority.
_Avoid_: Health repair, automatic doctor, mutation plan

**Wave progress projection**:
A read-only view of one approved wave's graph frontier and separate execution, admission, review,
gate, and effect dimensions.
_Avoid_: Percent complete, activity score, completion verdict

**Qualification certificate**:
Timestamped evidence binding the provider/model ID, OCX version, Claude Code compatibility range,
required tool surface, and independently observed route identity. It expires after 30 days or a
material runtime change and can be refreshed through an approved `ccodex` canary.
_Avoid_: Permanent certification, successful text response

**Mission**:
A durable objective that may require multiple approved waves.
_Avoid_: One workflow run, one agent task

**MissionContract**:
The immutable statement of a mission's objective, success and terminal criteria, non-goals,
constraints, authority ceiling, and stop conditions.
_Avoid_: Mutable backlog, wave plan, user prompt

**PlanningSnapshot**:
An immutable evidence-bound record of observed repository, queue, capability, policy, custody,
route, and retained-artifact state kept separate from desired behavior.
_Avoid_: Vision document, mutable workspace state, plan assumption

**Wave**:
One bounded, reviewed execution DAG with a defined terminal condition and durable handoff.
_Avoid_: Entire mission, unbounded autonomous loop

**WavePlan**:
One immutable versioned candidate DAG for a bounded wave, compiled from a MissionContract,
PlanningSnapshot, admitted evidence, and applicable policy.
_Avoid_: Mission, mutable task list, execution authority

**PlanDiff**:
The evidence-linked semantic delta between a candidate WavePlan and the prior approved revision.
_Avoid_: Text diff, changelog, silent replan

**Plan drift**:
An observed difference between current state and a load-bearing mission, snapshot, approved plan,
artifact, or approval invariant, classified as compatible, revalidation-required, replan-required,
or hard-stop.
_Avoid_: Any repository change, automatic repair trigger, silent replan

**Plan admission state**:
The monotonic lifecycle classification of one immutable WavePlan revision as draft, compiled,
admitted, approved, active, terminal, or superseded.
_Avoid_: Readiness boolean, execution activity, implicit approval

**Wave outcome receipt**:
The immutable terminal evidence record for one wave, carrying an accepted, remediation-progress,
blocked, aborted, failed, or unknown-effect verdict without implying mission or product success.
_Avoid_: Completion certificate, queue write, outward-effect authorization

**Workstream**:
An independently owned scope within a wave, normally implemented in an isolated worktree and
reviewed before fan-in.
_Avoid_: Agent persona, arbitrary task list

**CapabilityDemand**:
The provider-neutral reasoning, context, tool, boundary, resource, and independence needs of one
workflow node before an exact runtime route is chosen.
_Avoid_: Model pin, semantic tier, inherited host default

**EvaluationClass**:
The stable task-shaped bucket used to build representative rightsizing packs and compare exact
routes. It is not a role, model tier, or provider family.
_Avoid_: Semantic tier, role name, benchmark score

**WrongOutputClass**:
The `redo`, `retry`, `degrade`, or `derail` consequence if one node's artifact is wrong under its
actual controls. It determines the semantic tier before route selection.
_Avoid_: Task importance, model rank, confidence label

**RuntimeAssignment**:
The resolved pre-spawn contract for one executable node, separating its semantic task tier from
the exact provider/model, effort, context, qualification, and post-run identity evidence.
_Avoid_: Prompt recommendation, inherited host default

**Recursive-execution profile**:
An optional, default-off first-party workflow mode that admits bounded nested spawning after a
version-pinned capability canary and explicit approval of scope, authority, and resource limits.
_Avoid_: Unlimited recursion, multi-provider mode

**Bounded auto mode**:
A traceable execution policy that may replan and proceed only within a user-preapproved authority
and resource envelope. It does not bypass permissions or non-delegable outward-effect gates.
_Avoid_: YOLO mode, unattended unlimited autonomy

**AutoEnvelope**:
The immutable per-wave approval boundary for bounded auto mode, binding exact plan, custody,
authority, routes, egress, graph changes, resources, validity, and stop conditions.
_Avoid_: Permission mode, recursive-execution profile, standing approval

**Wave pause state**:
The execution-control classification of a wave as pausing or paused, kept separate from safety,
effect state, terminal verdict, and resumability.
_Avoid_: Process stopped, wave complete, safe to resume
