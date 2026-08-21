# Agentic SDLC Claude Code-first product and architecture brief

**Status:** decision-complete; ready for `/to-spec`
**Decision date:** 2026-08-15
**Source map:** [Wayfinder map](map.md)
**Domain language:** [CONTEXT.md](../../CONTEXT.md)
**Current-truth audit:** [repository reconciliation](research/repository-truth-reconciliation-2026-08-15.md)
**Durable decisions:** [ADR index](../../docs/adr/README.md)

## BLUF

Specify **Agentic SDLC** as a Claude Code-first, evidence-driven SDLC harness for greenfield and
brownfield repositories. **Agentic SDLC Core** must complete one native-Claude journey without
OCX, an external provider, or a companion library. **`ccodex`** is the versioned operator CLI and
lifecycle front door. It may add an optional OCX routed-model profile, but OCX never becomes the
product, the Core runtime, or a provider-wide support promise.

Build on the repository's existing lifecycle, ownership, Seeds, worktree, rightsizing, route,
Mermaid, gate, and refusal controls. Add the missing product composition: the versioned release and
`ccodex sdlc` namespace, full repository activation, one owned Dynamic Workflow Core wave,
immutable planning and bounded-auto artifacts, the local observability spine, dimensional route
control, the documentarian, draw.io, and threat modeling. Human authorization remains separate
from evidence at every effect boundary.

## `/to-spec` invocation

```text
/to-spec docs/plans/claude-code-first-harness/to-spec-handoff.md
```

The specification may decide implementation details named under [Residual implementation
discovery](#residual-implementation-discovery). It must return to product decision work if a
proposed design would change a boundary, authority rule, ownership plane, public promise, or
explicit non-goal in this brief.

## Product definition

### Primary user and first value

The first user is an experienced solo developer or small-team technical lead with a paid Claude
Code account and a real Git repository. The repository may be greenfield or brownfield. The user
wants maintainable multi-session delivery and optional multi-provider access without assembling
the harness themselves.

The minimum successful journey is:

1. acquire an exact Agentic SDLC release;
2. inspect it and explicitly activate the Claude host plane;
3. run `/sdlc-init` against one repository;
4. receive an exact write-ready, remediation-ready, or refused activation result;
5. compile and approve one bounded native-Claude wave;
6. execute it with isolated custody, exact runtime evidence, independent review, and adversarial
   completion review; and
7. close one immutable wave outcome with durable follow-up proposals.

A greenfield first wave should reach write-ready. A brownfield first wave may finish one named
hygiene slice as `remediation-progress` while honestly remaining short of global write-readiness.
Complete brownfield cleanup is not a first-journey requirement.

Decision owner: [first user and successful journey](issues/01-define-first-user-and-successful-journey.md).

### Brand and ownership vocabulary

| Term | Meaning |
|---|---|
| **Agentic SDLC** | The Claude Code-first product and methodology. |
| **Agentic SDLC Core** | The sufficient native-Claude journey and owned workflow contract. |
| **`ccodex`** | The installable operator CLI and lifecycle/control front door. |
| **OCX** | The optional gateway dependency behind the routed-model profile. |
| **Routed-model profile** | Exact qualified OCX routes plus Claude subscription models in one `ccodex` session. |
| **Companion host** | A non-Claude host consuming proven portable contracts without equal-parity claims. |
| **Companion library** | An external catalog installed only through its own upstream lifecycle. |

The product is not an official Anthropic product, a Claude Code replacement, a model or credential
provider, a universal gateway, a generic autonomous runtime, or a guarantee that agents complete
arbitrary work. gstack, oh-my-* projects, everything-claude-code, and partner libraries are category
comparisons only. No compatibility, lineage, endorsement, or migration claim follows.

Decision owner: [positioning and compatibility](issues/12-define-positioning-and-compatibility-promise.md); durable boundary: [ADR-0017](../../docs/adr/0017-make-claude-code-the-primary-product-host.md).

## Scope boundary

### Mandatory Core

Core owns:

- exact install, status, update, recovery, and removal behavior with ownership receipts;
- the Claude Code plugin with canonical skills, roles, commands, and Dynamic Workflows;
- `/sdlc-init`, Frame, Wave, Mission, and `/sdlc-rightsize` entry points;
- repository guidance, queue, ADR, gate, hygiene, worktree, review, and fan-in contracts;
- immutable mission, planning, runtime, role, evidence, completion, and follow-up artifacts;
- native-Claude runtime assignment and effective-identity admission;
- local read-only status, doctor, inspect, approval, effect, and recovery presentation; and
- BLUF, countable clarity, Mermaid, draw.io source authoring, and the optional first-party
  threat-modeling workflow.

Core is route-aware but requires no OCX process, external provider credential, companion library,
renderer runtime, hosted service, or product telemetry.

### First-party optional profiles and capabilities

- Routed-model profile through `ccodex` and OCX.
- Default-off bounded recursive-execution profile.
- Research OS.
- Operator statusline/UI activation.
- Explicitly provisioned Mermaid and draw.io render/export runtimes.
- Companion-host adapters.

Core-shipped optional skills such as `drawio-diagrams` and `threat-modeling` are installed and
discoverable but activate only for matching tasks. Heavy runtimes remain separate approved
provisioning operations.

### External companions

The closed first catalog remains `mattpocock/skills`, ECC (`affaan-m/ECC`), and hyperresearch.
External libraries never become Core dependencies or vendored bytes. Agentic SDLC may list, detect,
recommend, collision-check, and invoke an explicitly selected upstream front door. The upstream
owns bytes, licence, updates, removal, and behavior. gstack and unlisted libraries remain foreign
until separately researched and onboarded.

Decision owners: [core and companion boundary](issues/05-define-core-and-companion-boundary.md),
[companion contracts](issues/04-verify-companion-library-contracts.md), and
[`npx skills` lifecycle inspiration](issues/18-research-npx-skills-lifecycle.md).

## Architecture

```mermaid
flowchart TD
    R[Exact stable or preview release] --> C[ccodex operator CLI]
    C --> L[ccodex sdlc lifecycle]
    L --> P[Claude Code plugin and Core]
    P --> A[/sdlc-init assessment and activation]
    A --> PC[Planning compiler]
    PC --> W[One approved Dynamic Workflow wave]
    W --> WT[Isolated target-local worktrees]
    WT --> RV[Independent review and adversarial critique]
    RV --> FI[Separately authorized serial fan-in]
    FI --> O[Typed terminal receipt and local observability]
    C --> RC[ccodex routes]
    RC --> X[Optional OCX routed-model profile]
    X -. exact qualified RuntimeAssignment .-> W
    CL[External companion libraries] -. own-front-door only .-> P
    H[Human grants] -. exact operation authority .-> A
    H -. exact wave authority .-> W
    H -. exact fan-in authority .-> FI
    H -. separate outward authority .-> O
```

### Product planes

| Plane | Owns | May expose | Must not do implicitly |
|---|---|---|---|
| Distribution | Exact release, payload, manifests, packaged tools, lifecycle ownership | Checksums, SBOM, licences, compatibility | Trust config, activate a host, update silently |
| Claude host | User login, Claude configuration, plugins, Dynamic Workflows, session permissions | PII-minimized capability and effective-host evidence | Give Agentic SDLC credential custody |
| Routing | OCX config/process, provider front doors, exact route and slot identity | Dimensional readiness and correlated route evidence | Become required for Core or silently fall back |
| Repository | Source, `AGENTS.md`, queue, ADRs, gates, CI, worktrees, tracked intent | Exact snapshots, artifact pointers, gate evidence | Treat installation as activation or overwrite foreign policy |
| Local evidence | Ownership receipts, activation state, plans, journals, route generations, outcomes | Redacted read-only projections | Become a telemetry warehouse or transcript store |
| External system | Provider, forge, issue tracker, publication/deployment target | Explicit front door and observed response | Inherit authority from a local gate or receipt |

Plane crossings require declared data, identity, retention, and authority contracts. Sensitive state
remains in its owning plane. Decision owners: [security boundary](issues/11-define-security-telemetry-and-authority-boundaries.md), [observability](issues/20-define-observability-and-receipt-experience.md), [ADR-0018](../../docs/adr/0018-keep-sensitive-product-state-in-its-owning-plane.md), and [ADR-0019](../../docs/adr/0019-require-fresh-human-authorization-for-every-effect.md).

## Operator and host surfaces

### Release and lifecycle

The target primary acquisition is an exact self-contained GitHub release selected through mise.
`ccodex` is the only installed PATH command. The current checkout-backed distribution remains the
development, customization, contribution, gate, and release-building plane.

The product namespace is:

```text
ccodex sdlc inspect
ccodex sdlc doctor
ccodex sdlc install --host claude
ccodex sdlc status
ccodex sdlc update
ccodex sdlc recover
ccodex sdlc uninstall
ccodex sdlc rightsize
```

Inspection, doctor, status, help, and dry-run are read-only. Install does not activate a
repository, configure or start OCX, authenticate a provider, install a companion, enable a
statusline, trust configuration, or launch Claude Code. Stable and preview resolve to exact
side-by-side release identities. Update, downgrade, rollback, channel change, and removal are
explicit receipt-backed operations. Version 1 has no self-updater.

The target topology is settled for specification but [ADR-0021](../../docs/adr/0021-distribute-agentic-sdlc-as-a-versioned-mise-release.md) remains `proposed` until an actual release and clean-host lifecycle evidence satisfy ADR-0011's reversal condition. This is an implementation evidence gate, not an unresolved product choice.

Decision owner: [installation, update, and recovery](issues/08-choose-installation-and-update-experience.md).

### Claude commands

- `/sdlc-init` assesses and activates one repository.
- `/sdlc-frame` records one bounded intent and run shape.
- `/sdlc-wave` compiles and runs one approved wave.
- `/sdlc-mission` advances a durable objective through bounded waves.
- `/sdlc-rightsize` is the interactive rightsizing front end.

Other hosts invoke the same portable intents through skills where capability evidence permits; the
slash-command and Dynamic Workflow experience is Claude Code-first.

### Route control

`ccodex routes` is canonical. Read-only verbs are `list`, `show`, and `status`. Lifecycle and live
verbs include `configure`, `plan configure`, `apply`, `probe`, `qualify`, `refresh`, `credentials
refresh`, `disable`, `credentials revoke`, `remove`, and `recover`. The initial state with no OCX
provider is a successful native-only Core state.

Route status is dimensional: provider profile, credential category, configuration, gateway,
running catalog, exact probe, class qualification, runtime admission, and published support remain
separate. `reachable`, `tested`, `qualified`, and `supported` are distinct evidence levels. Query
success means the report is valid, not that a route is healthy.

The primary routed onboarding journey is the first-party `openai-codex` profile. It uses the pinned
OCX OpenAI/Codex OAuth front door and a separate opaque OCX credential slot with declared
`chatgpt-subscription` billing; it never copies or treats a native Codex CLI login as consent. Muse
is the second-provider API-key example. `openai-codex` and `openai-api` remain different profiles,
credential owners, billing bases, and qualification targets. Bare OCX `gpt-*` catalog IDs require
exact running-catalog membership, unambiguous versioned profile mapping, selected-slot identity,
and correlated OpenAI attribution; default-provider fallthrough or response echo is inadmissible.

Agentic SDLC may support exact qualified non-Claude route tuples while stating that Anthropic does
not support routing Claude Code to non-Claude models through a gateway. This residual upstream
status is mandatory disclosure and does not weaken the native-Claude Core.

Decision owners: [multi-provider promise](issues/06-define-multi-provider-support-promise.md) and
[provider onboarding and route UX](issues/19-define-provider-onboarding-and-route-control-ux.md).

## Repository activation and hygiene

`/sdlc-init` is assess -> plan -> approve -> apply -> readback. Assessment and plan are
deterministic, offline where possible, and read-only. Apply consumes the exact reviewed digest and
refuses changed prestate.

- `.agentic-sdlc/repo.toml` is portable tracked intent, never ownership or readiness proof.
- The local activation receipt is XDG state bound to the physical checkout/worktree, exact plan,
  owned paths, hashes, tools, and trust.
- Greenfield means no relevant operating-contract surface is occupied.
- Brownfield means at least one guidance, queue, decision, toolchain, hook, or CI surface is
  occupied. Repository age is irrelevant.
- `AGENTS.md` is canonical guidance. An owned `CLAUDE.md` projects the same contract. Foreign
  guidance is preserved.
- Seeds is the default authoritative queue until an approved adapter proves equivalent identity,
  dependency, acceptance, evidence, and concurrency semantics.
- MADR-compatible ADRs are the greenfield default; equivalent brownfield conventions may remain.
- `mise run check` is the authoritative pinned repository gate. Lefthook and partial tasks are
  supporting evidence.
- mise, lefthook, and betterleaks are the default DevEx/hygiene stack, integrated around current
  project policy rather than sprayed over it.

Activation ends as:

- `write-ready`: full portable and local contract admitted; normal waves may write;
- `remediation-ready`: exact known gate failures, no ownership/trust/credential/path blocker; only
  named hygiene waves may write; or
- refused/partial/unknown-effect with exact recovery evidence.

Decision owner: [repository activation](issues/09-define-repository-activation-contract.md); durable decision: [ADR-0022](../../docs/adr/0022-activate-repositories-through-digest-approved-plans.md).

## Planning, execution, and continuation

### Planning artifact chain

The read-only compiler consumes and emits immutable, versioned artifacts:

```text
MissionContract + PlanningSnapshot -> WavePlan -> PlanDiff -> AutoEnvelope
```

- `MissionContract` owns the durable objective, scope, constraints, authority classes, completion
  contract, and stop conditions.
- `PlanningSnapshot` binds repository, queue, policy, capability, route, and evidence inputs.
- `WavePlan` is the deterministic executable graph candidate.
- `PlanDiff` classifies the change from an admitted prior plan.
- `AutoEnvelope` is an optional, default-off closed transition grant with budgets and expiry.

The compiler has no network, model, write, queue, credential, or effect capability. Execution
binds exact artifact digests. Drift is evidence refresh, plan correction, scope change, or authority
change. Scope and authority change always return for human disposition. Resume revalidates durable
state and never invents missing progress, effects, approval, or runtime identity from chat history.

Decision owner: [planning, drift, and bounded auto](issues/16-define-planning-drift-and-bounded-auto-mode.md); durable decision: [ADR-0025](../../docs/adr/0025-compile-execution-from-immutable-planning-artifacts.md).

### One wave, one DAG

One approved wave is one artifact-driven Dynamic Workflow DAG. It is not the whole mission.
Default limits are four concurrent nodes, 64 total nodes, and recursion off; the recursive child
generation cap is raisable, but limits are configurable and always finite and capability-admitted.
Recursive spawn remains off by default even when numeric caps are raised.

Every node has declared inputs, output schemas, authority, work ownership, exact
`RuntimeAssignment`, stop conditions, and one `RoleSubmission`. Every model call injects exact
model and effort; effective identity is correlated afterward. Requested values never become
observed facts. An unresolved assignment stops before spawn.

Read-only nodes may retry eligible transient failures within budget. A write node retries only
after evidence proves no prior effect. Unknown effect, route mismatch, failed admission, authority
expansion, blocking drift, conflict, or exhausted budget stops the affected branch. Cross-session
continuation creates a new admitted wave from durable artifacts; it does not claim to resume lost
in-memory state.

Decision owner: [Dynamic Workflow graph](issues/07-define-dynamic-workflow-graph-contract.md); durable decision: [ADR-0024](../../docs/adr/0024-execute-each-wave-as-one-artifact-driven-dynamic-workflow.md).

### Roles and custody

The permanent roster is:

1. cartographer;
2. planner;
3. implementer;
4. reviewer;
5. researcher;
6. critic;
7. integrator; and
8. `sdlc-documentarian`.

Roles route by capability demand and wrong-output consequence, not static provider preference.
Security evidence, authoring, attack, privacy, supply-chain, operations, and mitigation-verification
responsibilities begin as workflow-local task roles or review lenses. They need promotion evidence
before becoming permanent selectors.

One writer owns one workstream, branch, and target-local ignored worktree. Worktrees live under
`<repo>/.worktrees/`. Reviews consume immutable candidates and never repair them. The default fan-in
is rebase onto the current integration base, re-admit identity and delta, then squash as one
traceable unit. One authorized integrator performs serial fan-in and re-runs the integrated gate.

Decision owner: [role roster](issues/17-curate-agent-persona-roster.md).

## Model rightsizing and route admission

Rightsizing proceeds in four layers:

```text
CapabilityDemand -> EvaluationClass -> WrongOutputClass -> exact route
```

Evaluation classes are mechanical redo, deterministic gated change, evidence extraction,
repository discovery, semantic implementation, semantic review, integration/reconcile, and
scale-setting or load-bearing judgment. Wrong-output classes are `redo`, `retry`, `degrade`, and
`derail`, which map to mechanical floor, capable volume, judgment workhorse, and frontier. A role
has no permanent tier.

Version 3 requirements:

- native Claude, gateway Claude passthrough, and gateway-routed providers are separate route kinds;
- exact route identity includes provider lane, credential slot, model, effort, context, endpoint or
  region where relevant, tool compatibility, auth/billing basis, and readback basis;
- discovery is read-only and makes no inference call;
- local task packs and deterministic/independent verifiers qualify one evaluation class;
- `class-qualified` never transfers across classes and never authorizes dispatch;
- the measured and dispatch Pareto fronts retain incomparable missing values and avoid a single
  weighted global score;
- operator overrides may restrict or choose among admitted routes but never promote or weaken a
  consequence class;
- current generations are immutable and atomically selected; edited evidence becomes modified and
  non-dispatchable;
- qualification is current for at most 30 days; mined benchmark evidence for at most 90 days;
- identity mismatch, default-provider fallthrough, critical regression, or explicit revocation
  quarantines only the affected route/class cell; and
- version 2 remains readable, but migration cannot manufacture v3 evidence.

Evaluation requires a digest-approved plan and declared egress/capacity. It produces evidence only,
never target mutation, provider configuration, runtime-policy mutation, or production dispatch.

Decision owner: [`/sdlc-rightsize` and model-task map](issues/15-refine-model-rightsizing-and-task-map.md); current related decision: [ADR-0015](../../docs/adr/0015-local-evaluation-is-the-rightsizing-promotion-boundary.md).

## Evidence, observability, and authority

### Evidence family

Use typed immutable terminal receipts rather than one universal log. Families cover distribution
and activation, route and credential lifecycle, probe and qualification, workflow/wave/node,
integration/completion, and incident/recovery.

Before the first admitted mutation, process effect, model/provider call, or external revocation,
the owning lifecycle durably opens a content-minimized append-only effect journal bound to plan and
prestate. A proven terminal boundary closes an immutable receipt bound to the journal digest.
Partial or unknown effect remains visible; a receipt never manufactures `none`, rollback, or
completion. Correlation uses typed mission, run, wave, workstream, node, attempt, route, slot,
approval, artifact, and receipt identities.

### Read-only projection

- `ccodex sdlc status` is the canonical concise local overview.
- `ccodex sdlc doctor` expands missing, contradictory, stale, foreign, partial, or unknown evidence
  without repair.
- `ccodex sdlc inspect <run|wave|route|receipt> <id>` explains one evidence chain without copying it.

Human and `--json` views render the same closed semantic record. A valid report exits successfully
even when dimensions are blocked or degraded. The projection has no daemon, telemetry database,
hosted dashboard, default egress, or workflow authority.

### Approval and terminal states

Approval state is `missing`, `pending`, `granted`, `declined`, `expired`, or `superseded`. It is
bound to exact plan, target, prestate, route, egress, budget, validity, and effect. Any material
change requires a new human grant.

Wave outcomes are exactly:

```text
accepted | remediation-progress | blocked | aborted | failed | unknown-effect
```

`accepted` requires every admitted node disposition, exact runtime evidence, valid artifacts,
reviews, authorized fan-in, integrated gates, budget/accounting, declared egress, adversarial
review, and no blocking finding or unknown effect. Process quietness, all nodes terminal, a receipt,
a partial gate, or successful publication cannot mint acceptance.

Exit semantics shared by new lifecycle/control commands:

- `0`: valid query/report or fully closed requested result, even if health is blocked;
- `1`: unexpected internal failure;
- `2`: command, grammar, schema, or input error;
- `3`: clean refusal before effect; and
- `4`: at least one admitted effect began and the result is partial or unknown.

### Authority

Gates, ADRs, Seeds, plans, receipts, reviewers, critics, agents, and observed results are evidence.
They never authorize effects. Persistent trust, global configuration, credentials, new egress or
paid evaluation, installation/migration, destructive or unknown-effect recovery, fan-in,
publication, push, PR mutation, merge, deployment, and permission bypass retain exact human gates.
Fan-in and outward publication use separate grants.

`--yolo` remains an explicit host permission profile, off by default and visibly reported. It does
not disable route, billing, credential, ownership, tool, egress, gate, or product authority
controls.

Decision owners: [security and authority](issues/11-define-security-telemetry-and-authority-boundaries.md), [observability](issues/20-define-observability-and-receipt-experience.md), and [ADR-0019](../../docs/adr/0019-require-fresh-human-authorization-for-every-effect.md).

## Privacy, retention, and supply chain

- Agentic SDLC ships no product telemetry.
- Credentials remain in Claude, OCX, provider, or external-system custody. The product records
  categories and readiness, never values or reversible encodings.
- Declared egress binds endpoint, purpose, transmitted data classes, calls/cost, and external
  retention. Changed endpoint, purpose, or data class invalidates approval.
- Raw prompts, completions, transcripts, source bodies, private issue bodies, account identity,
  credentials, and secret-shaped material do not enter durable operational evidence.
- Active ownership receipts remain while artifacts are owned. Pending/unknown journals remain
  until resolved. Completed lifecycle and qualification history defaults to at least 90 days;
  qualification freshness is 30 days. Explicit redacted debug logs expire after seven days;
  authority-free caches after 30 days.
- Version 1 has no product-managed history purge. Uninstall preserves local evidence history.
- Suspected exposure creates a redacted local incident receipt and human remediation handoff. The
  product does not auto-rotate credentials, rewrite history, delete user data, or claim an external
  transmission was reversed.
- Every bundled binary, runtime, plugin, workflow, skill, and policy is versioned and digest-bound.
  Releases carry SBOM and licence/NOTICE inventory. Runtime commands use packaged absolute tools,
  not ambient PATH, mutable latest, or silent downloads.
- Tool/MCP definitions and outputs are untrusted. Each node declares a minimum effective tool
  surface; installed configuration alone is not proof. Unenforceable required restrictions make
  the feature unsupported or stop it.

Durable decisions: [ADR-0018](../../docs/adr/0018-keep-sensitive-product-state-in-its-owning-plane.md) and [ADR-0020](../../docs/adr/0020-admit-only-exact-verified-execution-dependencies.md).

## Documentation, diagrams, and threat modeling

### Writing profile

BLUF governs human, agent, delegation, and workflow handoffs. New or materially revised prose uses
countable sentence, paragraph, noun-cluster, instruction, voice, list, and terminology checks while
preserving claim strength. Five SimpleEnglish ideas enter as a narrow attributed adaptation:
condition-first commands, explicit referents, direct verbs, punctuation/abbreviation audit flags,
and located meaning-preserving rewrite candidates.

No surface claims ASD-STE100 compliance, certification, or conformance; no licensed dictionary or
vocabulary table is reconstructed. Prose checking remains advisory unless a target repository
explicitly promotes a proven deterministic subset. A high-consequence document has an independent
clarity/evidence review.

Decision owners: [documentation defaults](issues/10-define-documentation-and-communication-defaults.md), [SimpleEnglish comparison](issues/22-compare-simpleenglish-with-core-clarity.md), and [ADR-0023](../../docs/adr/0023-adopt-one-evidence-preserving-documentation-profile.md).

### Diagrams

Use a diagram only when it materially improves a relationship, sequence, hierarchy, or state view.
Readable source remains authoritative.

- Mermaid is the default concise text diagram surface. Linux x64 rendering remains separately
  provisioned, sandboxed, advisory, and outside the repository gate.
- `drawio-diagrams` is one core-shipped optional umbrella with lazy family references. It is not one
  selectable skill per generic diagram type.
- Canonical draw.io source is strict, editable, uncompressed `.drawio` XML. Renders are derived and
  never replace source. Preserve unsupported/foreign content instead of normalizing it.
- Asset manifests own non-primitive icon/template/font provenance. Remote assets, HTML labels,
  embedded files, and unknown libraries fail strict authoring or require preservation-only handling.
- Renderer support is exact platform/version evidence. Source authoring does not wait for a
  renderer; visual review remains required when a render is produced.
- Security DFD authoring is a draw.io reference family. STRIDE analysis remains a separate
  threat-modeling workflow. `STRID` is treated as likely shorthand for STRIDE, not a new method.
  STARLORD is excluded until a distinct intended method and use case are established.

Decision owners: [draw.io research](issues/23-research-drawio-agent-diagram-workflows.md) and
[draw.io skill family](issues/24-define-drawio-diagram-skill-family.md).

### Threat modeling

Ship `threat-modeling` as a core-distributed, task-selected first-party workflow. Its DAG is:

```text
Admit -> Discover -> Model -> Enumerate -> Propose -> Challenge
      -> Human triage -> Implement separately -> Verify -> Handoff
```

Version 1 owns a typed security model, STRIDE method profile, mandatory independent abuse-case
challenge, threat ledger, evidence index, immutable reviews/verifications, human-only risk
dispositions, and BLUF handoff. A DFD is an input, never the complete threat model. Agents never
accept risk. Implemented never implies verified. A completed workflow never means secure or
complete.

Threat-model content is sensitive by default. Repository, local-private, and external-approved
storage are separate choices. Freshness, review, risk disposition, and mitigation verification are
independent axes. Unsupported/stale profiles stop or re-enter at the correct stage; no method is
silently substituted. Version 1 claims no interoperability with foreign threat-model formats.

Decision owner: [threat-modeling workflow](issues/25-define-threat-modeling-workflow.md); durable decision: [ADR-0026](../../docs/adr/0026-keep-threat-analysis-separate-from-human-risk-ownership.md).

## Compatibility and release policy

- Core minimum eligibility starts at Claude Code `>=2.1.154` with Dynamic Workflows effectively
  enabled. Optional profiles may have higher feature floors.
- Minimum eligibility never certifies every newer version. The product records exact version and
  runs current capability canaries before safety-dependent use.
- An unlisted newer version is not refused merely for missing from the tested table. It may become
  locally `capability-qualified`; public `certified` still needs the complete published journey.
- No general maximum exists. A known incompatibility or safety defect may create an exact exclusion.
- The initial dated references are 2.1.224 stable and 2.1.233 latest. They are nominations, not
  certifications or ceilings.
- Linux x64 and WSL2 Linux x64 are first full-tuple certification targets. macOS, ARM64, native
  Windows, WSL1, musl, alternative installation planes, and routed profiles remain separate rows.
- Support tiers are `certified`, `capability-qualified`, `experimental`, and `unsupported`.
- Core, routed models, operator tools/statusline, Mermaid, draw.io, Research OS, and companion-host
  adapters have independent compatibility tuples.
- Public channels are stable and preview. Stable requires the complete Core release gate,
  migration/recovery, and at least one current certified Core tuple. Preview is explicit,
  side-by-side, and cannot overwrite stable state.
- Public surfaces use SemVer plus independent artifact schema versions. Stable surfaces receive at
  least one feature-release deprecation window and prior-two-stable read-only schema support where
  evidence/recovery needs it. Emergency safety refusal requires an advisory and bounded recovery.
- Release preparation refreshes moving vendor facts from primary sources; offline gates use a
  checked-in dated snapshot.

Decision owner: [positioning and compatibility](issues/12-define-positioning-and-compatibility-promise.md); durable decision: [ADR-0027](../../docs/adr/0027-admit-compatibility-through-capability-evidence-above-published-minimums.md); research: [Claude Code version/platform snapshot](research/claude-code-version-platform-support-2026-08-15.md).

## Current repository migration

Do not rewrite current truth to look complete before the new product surface exists.

1. Preserve the current transactional lifecycle, activation primitives, Seeds launcher, worktree
   controls, rightsizing, routes, Mermaid renderer, gates, and tests.
   The current `0.7.3` manifests and checkout-backed dispatcher are development/brownfield truth,
   not the target versioned-release experience.
2. Add the new product composition around those primitives rather than creating parallel lifecycle,
   evaluator, queue, or evidence engines.
3. Replace provider-native multi-host claims across README, AGENTS, manifests, marketplaces, help,
   examples, and generated guidance only with an executable Core surface and negative claim tests.
4. Keep ADR-0005 and ADR-0011 accepted. ADR-0017 only refines ADR-0005's default-product posture.
   ADR-0021 may supersede ADR-0011 only after its exact release evidence exists.
5. Preserve ADR-0008 and ADR-0015's noncanonical legacy status metadata until a separately reviewed
   lifecycle action resolves it.
6. Do not mutate the current PRIME/DRIVE/gateway Seeds queue during specification. Later authorized
   reconciliation classifies each entry as still valid, satisfied but stale, superseded, or a
   migration source without deleting history.

Decision owner: [repository truth reconciliation](issues/13-reconcile-repository-truth.md). Durable decision graph: [ADR-0028](../../docs/adr/0028-organize-the-claude-code-first-product-boundary-as-one-initiative.md).

## Tracer-bullet build sequence

1. **Release identity and claim floor** — define release/manifest/schema identity, support rows,
   stable/preview semantics, and negative claim fixtures while retaining the checkout plane.
2. **Read-only `ccodex sdlc`** — package the operator CLI and current ownership/recovery substrate;
   ship inspect, status, doctor, and dry-run before mutation.
3. **Versioned lifecycle** — implement install/update/recover/uninstall over exact release payloads,
   stable/preview side-by-side state, foreign preservation, and old-schema readers.
4. **Activation slice** — compose one full greenfield and one brownfield assessed plan, tracked
   repository manifest, local receipt, and write-ready/remediation-ready/refused result.
5. **Native-Claude Core wave** — ship the smallest owned Dynamic Workflow that proves planning,
   exact native runtime assignment, isolated custody, artifacts, pause/stop, review, authorized
   fan-in, integrated gate, adversarial disposition, and terminal receipt.
6. **Planning and observability** — add mission/snapshot/plan/diff/AutoEnvelope schemas, the
   deterministic compiler, effect journals, immutable receipt families, and read-only projections.
7. **Routed-model profile** — add dimensional `ccodex routes`, provider-plan lifecycle, credential
   front-door handling, exact probe, rightsizing qualification handoff, quarantine, recovery, and
   return to native-only state.
8. **Documentation and security capabilities** — add `sdlc-documentarian`, the narrow
   SimpleEnglish adaptation and notice, draw.io source tooling, and the threat-modeling workflow.
9. **Dogfood and release** — run exact installed-byte greenfield and brownfield journeys, refresh
   vendor evidence, reconcile historical Seeds under separate authority, accept ADR-0021 only after
   its evidence condition, and publish stable only with one certified Core tuple.

Every slice includes offline positive, malformed, conflict, stale-prestate, substitution,
redaction, crash, partial-effect, recovery, and non-authority tests proportional to its effects.

## Release acceptance spine

A stable Core release is invalid unless all of these are true:

- exact release identity, SBOM, licences, checksums, and packaged tools verify;
- install/status/update/recovery/removal preserve foreign state and have effect-aware exits;
- one clean greenfield and one occupied brownfield activation journey pass from installed bytes;
- the native-Claude minimum and stable-reference Workflow canaries pass for the exact tuple;
- one complete Core wave reaches an honest `accepted` or intended `remediation-progress` outcome;
- runtime requests and observed identities remain separate and no silent fallback occurs;
- write custody, independent review, authorized serial fan-in, and integrated gates pass;
- status/doctor/inspect are read-only and render the same closed semantic record as JSON;
- secrets, private content, undeclared egress, and incident fixtures remain redacted and fail closed;
- product prose passes canonical vocabulary and prohibited-claim tests; and
- no optional profile, companion, renderer, external provider, permission bypass, or product
  telemetry is enabled by default.

## Residual implementation discovery

These are deliberately left to `/to-spec`; none changes a settled product choice:

1. Exact archive layout, bootstrap shim, private runtime packaging, and executable-relative payload
   resolution for the first mise release.
2. The smallest concrete Dynamic Workflow program and host API calls that prove graph creation,
   approval, agent execution, artifact handoff, pause/stop/resume, and result readback.
3. Exact XDG directory names, file names, canonical JSON/TOML serialization, lock granularity, and
   prior-schema reader implementation.
4. Which Claude Code and OCX fields can independently support exact main, classifier, generic-agent,
   workflow, usage, cost, and cache accounting without double counting.
5. Which existing activation transaction primitives can be composed directly and which need a
   versioned schema migration.
6. The first draw.io renderer/platform tuple worth certifying. Strict source authoring does not
   wait for renderer certification.
7. Exact historical Seed dispositions after the specification emits the new implementation graph.

If discovery shows a required boundary is mechanically impossible, the specification records the
unsupported surface and returns the architectural choice for human review. It does not silently
downgrade the boundary to advisory prose.

## Assumptions

- The primary operator has a paid Claude Code account and can enable Dynamic Workflows where the
  plan requires it.
- Git remains the first release's supported VCS and target-local Git worktrees remain the write
  substrate.
- mise remains the acquisition/version front door; ADR-0021 must still prove the release backend.
- Seeds remains the greenfield queue default, while the adapter contract stays tracker-neutral.
- Linux x64 and WSL2 Linux x64 receive the first complete certification effort.
- External providers, renderers, companions, and hosted integrations are optional and may remain
  unsupported until their exact evidence exists.

## Explicit non-goals

- Replacing Claude Code or building a general-purpose gateway/runtime.
- Equal feature parity across Codex, Gemini CLI, OpenCode, Windows, macOS, or other hosts.
- Supporting every provider, model, route, plugin, MCP, companion library, or threat-model format.
- Vendoring external skill libraries or auto-installing them through Core/setup/gates.
- Automatically cleaning an entire brownfield repository during activation.
- Silent fallback, silent update, silent trust, silent provider configuration, or default telemetry.
- Agent-created authority, risk acceptance, permission bypass, push, PR, merge, release, deploy, or
  external-system mutation.
- A self-updater or product-managed evidence-history purge in version 1.
- A hosted dashboard, event warehouse, or remote observability service.
- Cross-platform draw.io renderer certification in the first slice.
- Security completeness, ASD-STE100 conformance, or STARLORD support claims.
- Implementing product code, changing provider configuration, installing companions, mutating the
  Seeds queue, or publishing a release during this decision handoff.

## Decision ownership index

| Area | Owning ticket |
|---|---|
| First user and journey | [01](issues/01-define-first-user-and-successful-journey.md) |
| Dynamic Workflow extension facts | [02](issues/02-verify-dynamic-workflows-extension-contract.md) |
| Harness category boundaries | [03](issues/03-compare-opinionated-harness-boundaries.md) |
| Companion-library facts | [04](issues/04-verify-companion-library-contracts.md) |
| Core, profiles, companions | [05](issues/05-define-core-and-companion-boundary.md) |
| Multi-provider promise | [06](issues/06-define-multi-provider-support-promise.md) |
| Workflow graph | [07](issues/07-define-dynamic-workflow-graph-contract.md) |
| Install/update/recovery | [08](issues/08-choose-installation-and-update-experience.md) |
| Repository activation | [09](issues/09-define-repository-activation-contract.md) |
| Documentation defaults | [10](issues/10-define-documentation-and-communication-defaults.md) |
| Security/privacy/authority | [11](issues/11-define-security-telemetry-and-authority-boundaries.md) |
| Positioning/compatibility/release | [12](issues/12-define-positioning-and-compatibility-promise.md) |
| Current repository reconciliation | [13](issues/13-reconcile-repository-truth.md) |
| Rightsizing and task map | [15](issues/15-refine-model-rightsizing-and-task-map.md) |
| Planning/drift/auto mode | [16](issues/16-define-planning-drift-and-bounded-auto-mode.md) |
| Permanent role roster | [17](issues/17-curate-agent-persona-roster.md) |
| `npx skills` lifecycle research | [18](issues/18-research-npx-skills-lifecycle.md) |
| Route-control UX | [19](issues/19-define-provider-onboarding-and-route-control-ux.md) |
| Observability/receipts | [20](issues/20-define-observability-and-receipt-experience.md) |
| Durable ADR initiative | [21](issues/21-record-product-boundary-adrs.md) |
| SimpleEnglish adaptation | [22](issues/22-compare-simpleenglish-with-core-clarity.md) |
| draw.io research | [23](issues/23-research-drawio-agent-diagram-workflows.md) |
| draw.io skill family | [24](issues/24-define-drawio-diagram-skill-family.md) |
| Threat modeling | [25](issues/25-define-threat-modeling-workflow.md) |

## Decision-closure verdict

All prerequisite Wayfinder tickets are resolved. The brief contains no pending product or
architecture choice. ADR-0021 and ADR-0028 remain proposed because their lifecycle states depend on
future implementation evidence, not because the target decision is missing. Runtime `unknown`,
`unresolved`, `partial`, and `unsupported` values are deliberate truthful states, not design gaps.

The handoff is ready for `/to-spec`.
