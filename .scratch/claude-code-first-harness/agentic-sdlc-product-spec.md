# Build the Claude Code-first Agentic SDLC product

## Problem Statement

Experienced Claude Code users can assemble skills, subagents, model gateways, repository tooling,
worktrees, trackers, review practices, and safety rules, but the result is difficult to install,
keep coherent, and carry across multiple rounds of work. Existing harnesses often optimize prompts
or model access while leaving repository hygiene, ownership, evidence, recovery, and human
authority as unrelated conventions.

The user needs one opinionated harness that can safely activate greenfield or brownfield Git
repositories, plan and execute bounded Claude Code Dynamic Workflow waves, select fit-for-purpose
models, preserve work across sessions, and make every result explainable. Native Claude subscription
use must be sufficient. Multiple providers should be available through an optional, explicit,
qualified routing profile without turning a gateway into the product or silently changing
credentials, billing, routes, or fallbacks.

The current repository already contains strong lifecycle, ownership, Seeds, worktree, routing,
rightsizing, Mermaid, gate, and refusal primitives. It does not yet compose them into the complete
Claude Code-first product. Its public descriptions also disagree about whether Claude Code or a
provider-neutral multi-host bundle is primary. Users therefore cannot follow one stable path from
release acquisition to a reviewed native-Claude result, and maintainers cannot make a stable
release claim from the current checkout-backed surface.

## Solution

Deliver Agentic SDLC as a Claude Code-first, evidence-driven SDLC harness for greenfield and
brownfield repositories. Agentic SDLC Core will complete one native-Claude journey using the
operator's paid Claude Code account. It will require no gateway, external provider, companion
library, hosted service, renderer, or product telemetry.

Package one operator CLI named `ccodex`. Its `sdlc` namespace will inspect, install, diagnose,
update, recover, and remove exact Agentic SDLC releases. Its `routes` namespace will manage the
optional routed-model profile through OCX. Installing the CLI will not activate Claude Code,
modify a repository, trust configuration, start a gateway, configure a provider, install a
companion library, or launch a session.

Within an activated repository, `/sdlc-init` will assess existing operating contracts and produce
a digest-approved activation plan. A deterministic planning compiler will turn immutable mission
and repository evidence into one bounded WavePlan. One approved wave will execute as one
artifact-driven Claude Code Dynamic Workflow DAG. Every writer will have exclusive worktree
custody, every model call will have an exact RuntimeAssignment and independent identity evidence,
reviews will consume immutable candidates, and one separately authorized integrator will perform
serial fan-in.

Typed effect journals and immutable receipts will support local read-only status, diagnosis,
inspection, recovery, usage certainty, and terminal handoff. Evidence will never grant authority.
Agentic SDLC will ship no product telemetry, retain credentials and sensitive bodies in their
owning planes, and require operation-specific human authorization for every effect.

The product will also ship one evidence-preserving writing profile, an eighth permanent
documentarian role, Mermaid, one optional `drawio-diagrams` umbrella, and a separately selectable
first-party threat-modeling workflow. External libraries will remain unvendored, opt-in companions
installed through their own front doors.

## User Stories

1. As an experienced Claude Code user, I want one installable Agentic SDLC product, so that I do not have to assemble and maintain a private harness.
2. As a solo developer, I want native Claude subscription use to complete the Core journey, so that optional routing is not a prerequisite.
3. As a small-team technical lead, I want one shared repository contract, so that agent and human work remains consistent across sessions.
4. As an operator, I want `ccodex` to be the only product command added to PATH, so that the installed surface is small and collision-resistant.
5. As an operator, I want to inspect an exact release before activation, so that I can review its identity, contents, provenance, and compatibility.
6. As an operator, I want installation and repository activation to be separate operations, so that acquiring the product does not mutate a project.
7. As an operator, I want stable and preview releases installed side by side, so that evaluating a preview cannot overwrite stable state.
8. As an operator, I want explicit update, downgrade, rollback, and channel-change operations, so that ordinary commands never update silently.
9. As an operator, I want uninstall to remove only unchanged owned entries, so that foreign or modified work is preserved.
10. As an operator, I want interrupted lifecycle operations to expose exact recovery state, so that partial effects are not reported as success.
11. As an operator, I want read-only status and doctor commands, so that diagnosis never starts a gateway, authenticates, trusts, or repairs anything.
12. As an operator, I want machine and human status views derived from the same record, so that automation does not scrape or disagree with prose.
13. As a greenfield repository owner, I want `/sdlc-init` to establish guidance, tracking, decisions, gates, hooks, CI, and hygiene tooling, so that the repository starts with a maintainable operating contract.
14. As a brownfield repository owner, I want `/sdlc-init` to preserve existing policy and tooling, so that activation does not replace working local conventions.
15. As a brownfield maintainer, I want activation to produce a remediation-ready state when known gate failures remain, so that improvement can proceed honestly in bounded waves.
16. As a repository owner, I want greenfield and brownfield to be classified by occupied contract surfaces, so that repository age does not drive unsafe assumptions.
17. As a repository owner, I want a read-only activation plan before writes, so that I can review every proposed create, merge, adopt, skip, or refusal.
18. As a repository owner, I want activation approval bound to the exact plan digest and prestate, so that drift invalidates stale consent.
19. As a repository owner, I want a tracked portable repository manifest, so that shared intent is visible without pretending to prove machine readiness.
20. As an operator, I want local activation evidence stored outside the repository, so that machine ownership and trust state do not pollute portable project policy.
21. As a multi-host team, I want `AGENTS.md` to be canonical guidance, so that host-neutral instructions have one source of truth.
22. As a Claude Code user, I want an owned `CLAUDE.md` projection of canonical guidance, so that Claude receives the same repository contract.
23. As a repository with foreign guidance, I want it preserved until explicit reconciliation, so that activation does not silently choose an instruction channel.
24. As a repository owner, I want Seeds as the greenfield tracker default, so that durable work does not live only in chat.
25. As a repository using another tracker, I want an adapter contract, so that Agentic SDLC does not force a second shadow queue.
26. As a repository owner, I want `mise run check` to be the authoritative pinned gate, so that local agents and CI use the same verdict surface.
27. As a repository owner, I want mise, lefthook, and betterleaks integrated with current project behavior, so that hygiene is enforced without spraying a generic scaffold.
28. As a mission owner, I want durable mission intent separate from an individual wave, so that a long objective can progress through reviewed increments.
29. As a planner, I want repository and policy evidence captured in an immutable PlanningSnapshot, so that the compiled plan has recoverable inputs.
30. As a planner, I want a deterministic read-only compiler, so that plan generation itself cannot mutate code, queues, credentials, or external systems.
31. As an operator, I want a versioned WavePlan with exact artifacts, routes, budgets, and limits, so that execution matches what I reviewed.
32. As an operator, I want a PlanDiff for every revised plan, so that drift cannot hide inside a conversational continuation.
33. As an operator, I want scope, authority, route, egress, and budget drift classified separately, so that only admissible corrections continue automatically.
34. As an operator, I want human approval to be the default planning gate, so that agents do not broaden work from their own findings.
35. As an advanced operator, I want an explicit bounded AutoEnvelope, so that selected internal transitions can continue without granting open-ended autonomy.
36. As an operator, I want auto mode to stop on scope or authority expansion, so that automation cannot create new permission.
37. As an operator, I want auto mode independent from `--yolo`, so that bounded replanning never disables host permissions.
38. As an operator, I want pause and resume to revalidate durable state, so that a later session cannot invent missing progress or effects.
39. As a mission owner, I want one Dynamic Workflow wave to represent one bounded DAG, so that the execution boundary remains reviewable.
40. As a mission owner, I want finite configurable concurrency, node, depth, call, time, and cost caps, so that execution cannot become unbounded.
41. As a cautious operator, I want recursive spawning disabled by default, so that child workflows do not silently multiply scope or spend.
42. As an advanced operator, I want a canary-qualified recursive profile, so that bounded investigation and planning may self-progress inside one approved envelope.
43. As a conductor, I want each node to declare inputs, outputs, authority, tools, assignment, and stop rules, so that downstream admission is explicit.
44. As a conductor, I want nodes to exchange schema-validated artifacts instead of hidden chat context, so that handoffs remain inspectable and resumable.
45. As an implementer, I want one exclusive write set and worktree, so that parallel agents cannot overwrite each other.
46. As a reviewer, I want immutable candidate inputs and no repair tools, so that review remains independent evidence.
47. As a critic, I want to inspect the integrated snapshot and file findings without editing it, so that completion challenge stays independent.
48. As an integrator, I want to be the sole fan-in executor, so that accepted work reaches the integration base serially and traceably.
49. As an integrator, I want rebase-then-squash as the default fan-in, so that each accepted workstream lands as one re-admitted unit.
50. As a repository owner, I want integrated gates rerun after fan-in, so that green worktrees do not imply a green combined result.
51. As a conductor, I want every model spawn to receive an exact RuntimeAssignment, so that a role or prompt cannot silently select a default model.
52. As a conductor, I want requested model, effort, context, provider, and observed identity stored separately, so that requested values never masquerade as readback.
53. As a conductor, I want unresolved or uninjectable assignments to stop before spawn, so that unsupported routing does not become best effort.
54. As a workflow author, I want one versioned RoleSubmission contract, so that all role outputs have stable verdict and evidence fields.
55. As a workflow author, I want capability-demand routing instead of permanent provider pins, so that roles can use fit-for-purpose exact routes.
56. As a documentation owner, I want a permanent `sdlc-documentarian` role, so that evidence-preserving documentation has a clear author.
57. As a security workflow owner, I want specialist responsibilities to begin as task roles or review lenses, so that the permanent selector surface grows only with evidence.
58. As an operator, I want native Claude to be a first-class rightsizing route, so that gateway use is not assumed.
59. As an operator, I want native Claude and gateway Claude passthrough treated as different exact routes, so that transport and billing evidence remains honest.
60. As an operator, I want rightsizing to classify capability demand and wrong-output consequence before choosing a model, so that model tier follows task risk.
61. As an evaluator, I want class-specific immutable task packs and appropriate verifiers, so that route qualification reflects actual work rather than a leaderboard.
62. As an evaluator, I want a no-call plan and authorization digest before live evaluation, so that provider cost and data egress are explicit.
63. As an operator, I want published benchmarks to nominate candidates but never qualify them, so that target-local failure overrides mined reputation.
64. As an operator, I want measured and dispatch Pareto fronts instead of one weighted model score, so that missing or incomparable evidence stays visible.
65. As an operator, I want provider, cost, quota, latency, context, and egress preferences to restrict admitted routes, so that local constraints are respected without fabricating qualification.
66. As an operator, I want qualifications to expire and refresh explicitly, so that stale model evidence cannot dispatch indefinitely.
67. As an operator, I want identity mismatch or default-provider fallthrough to quarantine the exact route/class cell, so that one failure does not poison unrelated routes.
68. As an operator, I want immutable rightsizing generations with an atomic current selection, so that failed refreshes cannot replace the last complete evidence.
69. As an operator, I want `ccodex routes` to start in a successful native-only state, so that optional providers are not presented as missing Core prerequisites.
70. As an operator, I want route list, show, and status to be read-only, so that inventory does not start or repair OCX.
71. As an operator, I want provider readiness shown as independent dimensions, so that configured, live, probed, qualified, admitted, and supported do not collapse into one boolean.
72. As an operator, I want provider onboarding to render an exact plan before configuration, so that credentials, egress, restart, sync, and client effects are reviewable.
73. As an operator, I want credentials acquired only through provider or OCX front doors, so that `ccodex` never copies or accepts secret values.
74. As a Codex subscriber, I want an `openai-codex` profile using an explicit OCX OAuth slot, so that ChatGPT-subscription routing is separate from native Codex and API-key profiles.
75. As an operator, I want Muse as a second-provider API-key example, so that the onboarding contract proves more than one credential and namespace shape.
76. As an operator, I want every exact route bound to one opaque credential slot, so that account rotation cannot silently serve a different entitlement.
77. As an operator, I want route probe and semantic qualification to be separate operations, so that transport success cannot promote a model for work.
78. As an operator, I want route refresh, credential refresh, probe refresh, and qualification refresh separated, so that one layer cannot renew another layer's evidence.
79. As an operator, I want route disable, credential revocation, and provider removal separated, so that local admission, external credentials, and configuration have distinct effects.
80. As an operator, I want partial onboarding and removal to remain disabled until recovery, so that an incomplete provider cannot silently reenter dispatch.
81. As an operator, I want removing the last provider to return to a healthy native-only state, so that routing remains optional and reversible.
82. As an operator, I want non-Claude routing labeled as Anthropic-unsupported even when Agentic SDLC qualifies it, so that upstream support status is not hidden.
83. As an operator, I want each effect journal opened before the first effect, so that crashes cannot erase the last proven boundary.
84. As an operator, I want immutable typed receipts rather than a universal log, so that each lifecycle preserves only relevant evidence.
85. As an operator, I want partial and unknown effects preserved rather than rewritten as none, so that recovery does not invent rollback.
86. As an operator, I want typed correlation among mission, wave, node, attempt, route, slot, approval, artifact, and receipt, so that evidence graphs do not overload one identifier.
87. As an operator, I want usage and cost labeled exact, lower-bound, unpriced, missing, or stale, so that unknown never appears as zero.
88. As a Claude subscriber, I want subscription marginal monetary cost reported as unknown, so that the product does not invent a billed per-call charge.
89. As an operator, I want main, classifier, generic-agent, and named-workflow usage separated, so that nested activity is not double counted.
90. As an operator, I want approval state shown separately from gates and recommendations, so that evidence cannot render itself as granted authority.
91. As an operator, I want failure output to lead with effect state and last proven stage, so that the next safe action is clear.
92. As an operator, I want a redacted incident receipt for possible exposure, so that containment evidence does not repeat the sensitive material.
93. As an operator, I want recovery assessment to be read-only by default, so that viewing a failure never retries an effect.
94. As a mission owner, I want wave outcomes limited to accepted, remediation-progress, blocked, aborted, failed, or unknown-effect, so that terminal language cannot manufacture success.
95. As a mission owner, I want acceptance to require exact artifacts, reviews, fan-in, gates, budgets, egress, approvals, and adversarial disposition, so that process completion alone is insufficient.
96. As a conductor, I want discoveries emitted as typed Seed proposals, so that findings can survive without mutating the configured queue automatically.
97. As a repository owner, I want only the conductor's admitted queue-write operation to record selected proposals, so that workers and reviewers cannot mutate durable work state.
98. As a human author, I want BLUF handoffs, so that the decision, failure, or requested action appears first.
99. As a documentation reviewer, I want countable clarity checks that preserve claim strength, so that concise prose does not become overconfident prose.
100. As a documentation owner, I want a narrow attributed SimpleEnglish adaptation, so that useful clarity mechanics enter without vendoring another skill surface.
101. As a legal-conscious maintainer, I want no ASD-STE100 conformance, certification, dictionary, or logo claim, so that the product remains honest about public rule shapes.
102. As a diagram author, I want Mermaid for concise parseable diagrams, so that readable text remains authoritative.
103. As a diagram author, I want one optional `drawio-diagrams` umbrella, so that editable canvas work is available without dozens of overlapping selectors.
104. As a diagram maintainer, I want canonical editable draw.io source preserved, so that a render never replaces the maintained artifact.
105. As a diagram maintainer, I want unsupported foreign content classified before mutation, so that imports are not silently normalized or destroyed.
106. As a security architect, I want security DFD authoring separated from threat analysis, so that a diagram is not mistaken for a threat-model verdict.
107. As a security owner, I want a separately selectable threat-modeling workflow, so that analysis has an owned staged artifact and review contract.
108. As a threat-model author, I want versioned system-model and method profiles, so that coverage and drift are reproducible.
109. As a threat-model reviewer, I want independent STRIDE and abuse-case challenge, so that one author cannot certify their own coverage.
110. As a human risk owner, I want only humans to record risk disposition, so that an agent cannot accept organizational risk.
111. As a mitigation verifier, I want exact conditions and current control evidence, so that implemented does not imply verified.
112. As a security owner, I want threat-model content sensitive by default, so that repository or external storage requires explicit audience, retention, and egress approval.
113. As a threat-model maintainer, I want freshness, review, disposition, and verification as independent axes, so that one green status cannot hide stale analysis.
114. As a release engineer, I want minimum feature requirements plus current capability admission, so that tested versions are evidence rather than a hard maximum.
115. As a user on a newer Claude Code version, I want capability qualification instead of automatic refusal, so that moving releases do not need version-only updates.
116. As a release engineer, I want platform, installation, Core, and optional-profile support as separate tuples, so that evidence does not transfer across unlike environments.
117. As a release engineer, I want stable to require one certified Core tuple, so that stable never means only that packaging succeeded.
118. As a preview user, I want preview isolated from stable ownership, so that incomplete profiles cannot overwrite stable state.
119. As a maintainer, I want visible deprecation and prior-schema readers, so that retained evidence and recovery do not break silently.
120. As a companion-host user, I want portable skills and contracts where capabilities prove them, so that I benefit without receiving an unverified parity promise.
121. As an external-library user, I want companion catalogs installed only through their own front doors, so that upstream ownership and licences remain intact.
122. As a repository owner, I want no product telemetry, so that local SDLC work does not create an analytics egress channel.
123. As a credential owner, I want values to remain in Claude, OCX, provider, or external-system custody, so that Agentic SDLC does not become another secret store.
124. As an operator, I want explicit declared egress before network transmission, so that endpoint, purpose, data class, budget, and retention are reviewable.
125. As an operator, I want bounded evidence retention and no version-one purge command, so that recovery history is preserved until a real deletion contract exists.
126. As a supply-chain reviewer, I want every bundled executable and policy digest-bound with SBOM and NOTICE data, so that an exact release is independently inspectable.
127. As a security reviewer, I want runtime commands to avoid ambient PATH and silent downloads, so that caller state cannot substitute unreviewed tools.
128. As a release engineer, I want one exact installed-byte greenfield journey and one brownfield journey, so that the product proves both intended starting states.
129. As a release engineer, I want malformed, stale, conflict, crash, redaction, and unknown-effect fixtures, so that the stable claim includes negative behavior.
130. As a maintainer, I want current multi-host and gateway-required claims migrated only with executable replacements, so that documentation never runs ahead of the product.

## Implementation Decisions

1. **Product identity.** Agentic SDLC is the product and methodology. `ccodex` is its operator CLI.
   Claude Code is the primary product host. Other hosts are companions with capability-specific,
   not equal-parity, claims.
2. **Core sufficiency.** Agentic SDLC Core must complete the first journey through ordinary Claude
   Code and the operator's paid Claude account. OCX, external providers, renderers, companions, and
   hosted services are optional.
3. **Primary acceptance seam.** The highest product seam is one exact installed-byte journey:
   acquire release -> inspect -> activate Claude -> activate repository -> compile plan -> approve
   and run one native-Claude wave -> review -> authorized fan-in -> terminal receipt. Greenfield and
   brownfield variants share this seam.
4. **Distribution target.** Publish exact self-contained releases through mise. Keep source
   checkouts as development/customization planes. The release-topology ADR remains proposed until
   real clean-host evidence exists, but the target is settled for implementation.
5. **Release channels.** Stable and preview are exact side-by-side selections. Stable contains no
   experimental profile or default permission bypass. Version one has no self-updater.
6. **Lifecycle separation.** CLI acquisition, Claude activation, repository activation, provider
   onboarding, companion installation, renderer provisioning, trust, and launch are distinct
   operations with independent receipts and approvals.
7. **Ownership.** Lifecycle mutation adopts only exact eligible prior owned state. Foreign,
   modified, conflicting, or ambiguous entries are preserved and reported. Removal proves unchanged
   ownership before deletion.
8. **Read-only commands.** Help, inspect, status, doctor, dry-run, and recovery assessment must not
   acquire writer authority, contact providers, trust, repair, refresh, authenticate, or mutate.
9. **Effect-aware exits.** New lifecycle and control surfaces use: 0 for a valid query or closed
   requested result; 1 for unexpected internal failure; 2 for grammar/schema/input error; 3 for
   clean refusal before effect; and 4 after an admitted partial or unknown effect.
10. **Repository manifest.** Track portable repository intent in one versioned
    RepositoryContractManifest. Do not use it as ownership, tool, trust, route, or readiness proof.
11. **Local activation evidence.** Store exact machine-local activation ownership, hashes, physical
    identity, tool versions, and trust state under the `ccodex` XDG state plane.
12. **Activation compiler.** `/sdlc-init` performs read-only assessment and planning, exact digest
    approval, transactional apply, readback, and recovery. It returns write-ready,
    remediation-ready, or a truthful non-success/effect state.
13. **Greenfield and brownfield.** Classify by occupied operating-contract surfaces rather than
    code age. Brownfield behavior uses minimum-compatible integration and iterative hygiene waves.
14. **Guidance authority.** `AGENTS.md` is canonical. Claude guidance is an owned projection.
    Preserve foreign guidance until explicit reconciliation.
15. **Queue adapter.** Seeds is the default authoritative queue. Any alternate tracker must prove
    stable identity, dependencies, acceptance, evidence links, concurrency, and one conductor
    writer. No shadow queue is allowed.
16. **Decision records.** Use a MADR-compatible lifecycle for greenfield repositories. Preserve an
    equivalent brownfield convention. Accepted ADRs remain evidence, never authority.
17. **Gate contract.** `mise run check` is the single authoritative repository gate. Hook and
    partial-task results cannot substitute for it. Brownfield remediation uses exact non-worsening
    baselines until write-ready.
18. **Planning artifacts.** Define independently versioned MissionContract, PlanningSnapshot,
    WavePlan, PlanDiff, and AutoEnvelope schemas. Use deterministic canonical serialization and
    immutable generations.
19. **Planning compiler capabilities.** The compiler has no model, network, credential, queue,
    write, or external-effect capability. It consumes exact evidence and emits a candidate only.
20. **Drift taxonomy.** Keep evidence refresh, plan correction, scope change, and authority change
    separate. Scope and authority changes always require human disposition.
21. **Auto mode.** Default off. An AutoEnvelope names closed transitions, scope, routes, egress,
    budgets, retry/call/depth/time limits, pause conditions, and expiry. It never selects `--yolo`
    or creates a second mission root.
22. **Dynamic Workflow boundary.** One approved wave is one Claude Code Dynamic Workflow DAG. A
    mission spans waves. Cross-session continuation compiles a new wave from durable artifacts.
23. **Execution defaults.** Ship defaults of four concurrent nodes, 64 total nodes, and one
    recursive child generation. Keep every limit configurable, finite, recorded, and bounded by
    verified host capability. Recursive execution remains separately disabled by default.
24. **Node contract.** Every node declares inputs, output schema, authority, tools, work ownership,
    RuntimeAssignment, stop rule, and RoleSubmission destination.
25. **Runtime assignment.** Resolve exact provider/model, requested effort and context, transport,
    tool surface, and route evidence before spawn. Requested and observed fields remain distinct.
26. **Retry.** Read-only nodes may retry eligible transient failures within budget. Write nodes may
    retry only after proving no prior effect. Unknown effect stops.
27. **Permanent roles.** Ship cartographer, planner, implementer, reviewer, researcher, critic,
    integrator, and `sdlc-documentarian`. Maintain Claude and portable-host representations from one
    semantic contract.
28. **Role routing.** Roles have no static provider preference. Route each node by CapabilityDemand,
    EvaluationClass, WrongOutputClass, exact current route evidence, and independent perspective.
29. **Security specialists.** Begin security responsibilities as task roles and review lenses.
    Promote a permanent role only after recurring graph responsibility, distinct least privilege,
    stable artifacts, and cross-repository evidence.
30. **Work custody.** Assign every writer one branch, one target-local ignored worktree, and one
    disjoint write set. Inventory and preserve user work before mutation.
31. **Review custody.** Reviewers and critics consume immutable candidates and cannot repair them.
    Retries do not count as independent review.
32. **Fan-in.** One separately authorized integrator rebases an accepted candidate onto the current
    base, re-admits its identity and delta, squash-applies one traceable unit, and re-runs integrated
    gates. Fan-in grants do not grant publication.
33. **Rightsizing taxonomy.** Version three uses CapabilityDemand, eight EvaluationClasses, and
    WrongOutputClass values `redo`, `retry`, `degrade`, and `derail`. Roles do not own tiers.
34. **Exact route identity.** Include transport, route kind, provider lane, endpoint/region where
    relevant, credential slot, exact model, effort, context, tools, auth/billing basis, and identity
    readback basis. Nominally equal models on different tuples qualify separately.
35. **Rightsizing discovery.** Discovery is local and read-only. It does not make model calls,
    authenticate, repair, restart, configure, or read credential values or account identity.
36. **Qualification.** A class qualification binds task pack, harness, runtime, settings, exact
    route, class, and verifier. Use at least five distinct held-out tasks, three attempts each,
    90% accepted attempts, a 95% Wilson lower bound of 0.70, zero identity/transport failures, and
    zero critical-task failures as the minimum promotion floor.
37. **Verifier strength.** Match verifier type to task class. An LLM judge alone cannot qualify a
    route. Load-bearing judgment requires independent re-derivation and human rubric disposition.
38. **Pareto selection.** Apply hard context, tool, identity, qualification, runtime, egress, and
    authority filters before Pareto comparison. Never emit one global weighted score or convert
    missing cost into zero.
39. **Overrides and fallbacks.** Preserve the evidence-ranked baseline separately. Overrides may
    restrict or select admitted routes but cannot promote, weaken consequence class, or invent a
    fallback. Every fallback is exact, qualified, plan-declared, and preapproved.
40. **Rightsizing evidence.** Store immutable local generations and atomically select a complete
    current generation. Keep edited, incomplete, failed, stale, quarantined, or unresolved cells
    visible and non-dispatchable.
41. **Freshness.** Exact route/class qualification is current for at most 30 days. Mined benchmark
    evidence is current for at most 90 days. Material identity changes invalidate immediately.
42. **Route-control surface.** `ccodex routes` owns list, show, status, configure, probe, qualify,
    refresh, credential lifecycle, disable, remove, and recover. Retain low-level compatibility
    aliases for one deprecation release only.
43. **Native-only state.** No routed provider and an intentionally stopped gateway is a healthy
    Core state, not a warning requiring remediation.
44. **Provider profiles.** Ship a digest-bound, non-secret profile catalog. A profile proves guided
    onboarding only, not model support or qualification. Keep operator-defined profiles separate
    and unsupported by default.
45. **Onboarding plan.** Bind provider/tool versions, host and prestate, namespace, adapter,
    endpoint/region, credential owner/front door, egress, billing/retention, config delta, client
    effects, restart, catalog verification, rollback limits, budgets, and receipts.
46. **Credential custody.** Never accept credentials in arguments, URLs, prompts, plans, receipts,
    logs, or output. Invoke only provider/OCX front doors. Store opaque slot IDs, not account
    identity or secret-derived labels.
47. **Primary routed examples.** Use `openai-codex` as the ChatGPT-subscription routed journey and
    Muse as the API-key second-provider journey. Keep `openai-codex`, `openai-api`, native Codex,
    and native Claude as distinct credential and support surfaces.
48. **Gateway-native IDs.** Admit bare `gpt-*` IDs only through exact running-catalog membership,
    unambiguous profile mapping, selected slot, and correlated OpenAI attribution. Never use family
    guessing or default-provider classification.
49. **Probe versus qualification.** Probe proves only exact transport, credential acceptance,
    catalog membership, injection, and correlated identity. Qualification delegates to the one
    rightsizing evaluator and remains class-specific.
50. **Route layers.** Configuration refresh, credential refresh/revocation, probe refresh,
    qualification refresh, disable, and removal are different lifecycle operations. One cannot
    renew or imply another.
51. **No silent fallback.** Same-route retries are bounded. Changing provider, model, slot, effort,
    context, or route requires an already qualified and approved alternative. Default-provider
    fallthrough is a quarantine event.
52. **Upstream support disclosure.** State that Anthropic does not support routing Claude Code to
    non-Claude models through a gateway, even where Agentic SDLC supports an exact qualified tuple.
53. **Product planes.** Separate distribution, Claude host, routing, repository, local evidence,
    and external-system ownership. Each crossing declares data, identity, retention, and authority.
54. **Evidence classes.** Label controls as mechanical, observed, or advisory. A required property
    that cannot be enforced or observed makes its feature unsupported; prompts never upgrade it.
55. **Effect journals.** Open an append-only minimized journal before the first admitted mutation,
    process effect, provider/model call, or external revocation. Retain it as recovery authority
    through crashes and unknown effects.
56. **Receipt family.** Use typed immutable terminal receipts with a common envelope and
    independently versioned payloads. Receipt existence never implies success or authority.
57. **Typed correlation.** Preserve mission, run, wave, workstream, node, attempt, route, slot,
    lifecycle, approval, artifact, and receipt identity kinds. Reject malformed, dangling,
    duplicate, cyclic, or kind-incompatible references.
58. **Observability.** `ccodex sdlc status`, doctor, and inspect are disposable read-only projections
    over canonical local artifacts. Add no daemon, warehouse, hosted dashboard, or default egress.
59. **Usage accounting.** Separate main, classifier, generic-agent, named-workflow, and descendant
    ownership. Label values exact, lower-bound, unpriced, missing, or stale. Subscription marginal
    cost remains unknown.
60. **Approval lifecycle.** Use `missing`, `pending`, `granted`, `declined`, `expired`, and
    `superseded`. Bind grants to exact plan, scope, target, routes, egress, budgets, evidence, and
    effect. Changed inputs invalidate authority.
61. **Wave outcomes.** Close exactly one of `accepted`, `remediation-progress`, `blocked`, `aborted`,
    `failed`, or `unknown-effect`. Process completion and publication cannot manufacture success.
62. **Authority.** Gates, roles, reviews, ADRs, Seeds, receipts, and observations remain evidence.
    Trust, credentials, paid/egressed calls, mutations, fan-in, push, PR, merge, release, deployment,
    external messages, and permission bypass require applicable human grants.
63. **YOLO boundary.** Keep `--yolo` explicit, first-position, visible, conflict-checked, and off by
    default. It changes Claude host permissions only and does not weaken harness controls.
64. **Telemetry and egress.** Ship no product telemetry. Every network transmission declares
    endpoint, purpose, data classes, budget, and external retention. Changed declarations require
    new approval.
65. **Durable data minimization.** Never retain raw credentials, reversible encodings, prompts,
    completions, transcripts, source bodies, private issue bodies, or account identity in product
    operational evidence.
66. **Retention.** Keep active ownership while artifacts are owned and unresolved journals until
    recovery closes. Default completed operational history to at least 90 days, redacted debug logs
    to seven days, and authority-free caches to 30 days. Add no version-one history purge.
67. **Incidents.** A possible exposure stops the affected branch and writes a redacted local
    incident receipt. Do not auto-rotate credentials, rewrite history, delete user data, transmit
    the incident, or claim external effects were reversed.
68. **Supply chain.** Digest-bind every bundled tool, runtime, plugin, workflow, skill, profile, and
    policy. Include an SBOM and licence/NOTICE inventory. Use packaged absolute tools and no mutable
    latest, ambient PATH substitution, or silent downloads.
69. **Tool admission.** Each node declares its minimum tool/MCP surface. Inspect the effective
    model-visible inventory. Treat definitions/results as untrusted, bounded, sanitized input.
70. **Companion libraries.** Keep the initial closed catalog external and opt-in through each
    upstream front door. Never vendor bytes, install through Core, or treat name presence as
    ownership.
71. **Writing profile.** Apply BLUF and countable clarity to product prose and handoffs. Preserve
    technical meaning, uncertainty, and evidence strength. Keep prose checking advisory by default.
72. **SimpleEnglish adaptation.** Re-express only condition-first commands, explicit referents,
    direct verbs, punctuation/abbreviation flags, and located meaning-preserving rewrites. Land an
    exact donor NOTICE entry with the change.
73. **ASD boundary.** Do not reproduce a controlled dictionary or claim ASD-STE100 compliance,
    conformance, certification, endorsement, or logo rights.
74. **Mermaid.** Keep concise readable diagram source authoritative. Provision/render only through
    the separate exact Linux x64 sandboxed surface. Rendering remains advisory and outside the gate.
75. **Draw.io.** Ship one task-selected `drawio-diagrams` umbrella with lazy reference packs. Use
    strict editable uncompressed XML as canonical source, preservation inspection for foreign
    content, asset manifests, derived renders, and exact renderer receipts.
76. **Threat modeling.** Ship one separate task-selected first-party workflow. A security DFD is an
    input, not the complete threat model or verdict.
77. **Threat artifacts.** Own a model manifest, one canonical topology source, threat ledger,
    human-only risk dispositions, evidence index, immutable reviews/verifications, and BLUF handoff.
78. **Threat profiles.** Start with a typed security DFD model, STRIDE enumeration, and mandatory
    independent abuse-case challenge. Validators prove structure and coverage disposition only,
    never analytical completeness or security.
79. **Risk authority.** Agents may propose treatment. Only a named human risk owner writes
    disposition. Implemented never implies verified; verification is independent and condition-
    bound.
80. **Threat privacy and drift.** Treat content as sensitive by default. Keep storage plane,
    freshness, review state, risk disposition, and verification separate. Stale or unsupported
    profiles stop and never substitute silently.
81. **Compatibility.** Use minimum feature requirements plus current capability admission, not an
    exact-version ceiling or a broad `>=` promise.
82. **Core floor.** Start Core eligibility at Claude Code 2.1.154 with Dynamic Workflows effectively
    enabled and all required behavior canaries passing. Optional profiles may have higher floors.
83. **Reference versions.** Treat the dated stable and latest nominations as regression evidence,
    not certifications or maxima. Refresh moving vendor facts during release preparation.
84. **Support tuples.** Bind exact product release, host/version, OS/architecture/runtime boundary,
    installation plane, capability evidence, and optional profile/dependency versions. Do not let
    one tuple inherit another's result.
85. **Support tiers.** Publish only `certified`, `capability-qualified`, `experimental`, or
    `unsupported`. Stable requires one current certified Core tuple.
86. **Initial certification.** Prioritize Linux x64 and WSL2 Linux x64. Keep macOS, ARM64, native
    Windows, WSL1, musl, alternate installers, and routed profiles separate until proven.
87. **Versioning and deprecation.** Use SemVer for public surfaces and independent schema versions
    for artifacts. Preserve prior-two-stable read-only readers where evidence/recovery requires it.
    Give stable surfaces one feature-release deprecation window unless an explicit safety advisory
    requires immediate refusal.
88. **Current-repository migration.** Preserve existing lifecycle and safety primitives. Replace
    provider-neutral claims only with executable product surfaces and negative claim tests.
    Reconcile historical PRIME/DRIVE/gateway queue records later through an authorized conductor
    operation without deleting history.
89. **ADR lifecycle.** Treat ADR-0017 through ADR-0020 and ADR-0022 through ADR-0027 as accepted
    product constraints. Keep the release-topology and initiative ADRs proposed until their stated
    evidence conditions close.

## Testing Decisions

1. Tests assert external behavior and durable artifacts, not private helper structure. A refactor
   that preserves command results, effects, receipts, and refusals should not break a test.
2. The primary release test is the highest existing seam: an exact installed-byte journey from
   release acquisition through one terminal native-Claude wave receipt.
3. Run the primary seam twice: once against an empty greenfield contract surface and once against
   an occupied brownfield surface with preserved foreign guidance, tooling, queue, CI, and dirty
   user work.
4. The greenfield journey must reach write-ready and one accepted Core wave. The brownfield journey
   may reach remediation-ready and a non-worsening `remediation-progress` wave.
5. Release lifecycle tests cover exact identity, checksums, provenance, SBOM/licences, install,
   status, update, preview/stable isolation, downgrade, rollback, interrupted recovery, removal,
   modified-owned conflicts, foreign preservation, and missing release roots.
6. Read-only command tests prove no filesystem writer, provider call, gateway process, trust,
   authentication, queue mutation, repair, or telemetry effect occurs.
7. Activation tests cover greenfield, brownfield, exact plan-digest approval, stale prestate,
   conflict refusal, symlink/special-node/path containment, partial effect, crash recovery,
   idempotent rerun, and truthful readiness states.
8. Activation tests reuse the existing transaction and ownership seams rather than introducing a
   second activation engine.
9. Queue tests reuse the verified conductor-only Seeds launcher seam. They cover exact prestate,
   one-record deltas, worker proposal-only behavior, alternate tracker adapter conformance, and no
   shadow queues.
10. Planning compiler tests run without network or models, compile the same inputs twice, compare
    canonical digests, and reject malformed, missing, duplicated, stale, cyclic, scope-changing,
    or authority-changing inputs.
11. Drift tests cover all four classes and prove that scope/authority drift always stops. Auto mode
    tests prove only listed transitions occur, budgets debit descendants, expiry stops, and YOLO is
    never selected.
12. Dynamic Workflow canaries bind exact Claude Code version, account/provider mode, plugin
    identity, workflow behavior, approval, agent execution, artifacts, pause, stop, resume, and
    result readback.
13. Workflow tests cover DAG barriers, bounded fan-out, configurable caps, default-off recursion,
    qualified recursion, child budget inheritance, no second mission root, and correct blocked-
    branch behavior.
14. RuntimeAssignment tests cover exact model/effort injection, unresolved/inherited assignments,
    identity mismatch, unavailable readback, tool incompatibility, no silent fallback, and the
    distinction between request and observation.
15. Work custody tests cover one writer per worktree, target-local containment, dirty-user-work
    preservation, overlapping write-set refusal, stable candidate sealing, rebase identity change,
    squash scope, sole-integrator fan-in, and integrated re-gating.
16. Review tests prove reviewers/critics cannot mutate candidates or queue state and that a repair
    attempt creates a new authoring pass rather than independent review.
17. Completion tests prove that quiet processes, terminal nodes, passing partial gates, receipt
    existence, publication, or nonblocking future work cannot independently mint acceptance.
18. Rightsizing tests cover the v3 taxonomy, v2 read-only migration, task-pack identity, promotion
    thresholds, verifier classes, confidence intervals, critical failures, Pareto filtering,
    overrides, fallback constraints, immutable generations, refresh, expiry, and quarantine.
19. Rightsizing live tests are separately approved and never gate leaves. Offline release tests use
    synthetic catalogs, routes, attribution, usage, and outputs.
20. Route-control tests cover the successful native-only state, first-party and operator-defined
    profile schemas, onboarding plan invalidation, safe credential front doors, slot identity,
    `openai-codex`, Muse, configured-but-not-live refusal, exact probe, qualification handoff,
    layer-specific refresh, disable, revoke, remove, and recovery.
21. Route negative tests cover unsafe endpoints, credential-bearing URLs, Anthropic impersonation,
    default-provider fallthrough, unselected credential pools, client-scope drift, session
    interruption, partial effects, unknown external revocation, and no automatic replacement.
22. Evidence tests cover every journal/receipt family, canonical digest, schema version,
    finalization, truncation, crash-before/after-effect, unknown-effect retention, typed references,
    invalid cycles, prior-schema rendering, and immutable migration.
23. Observability golden tests render human and JSON views from the same semantic record across
    no-install, native-only, routed, active-wave, blocked, partial, incident, stale, unreadable, and
    terminal states.
24. Accounting tests prove exactly-once lane ownership, descendant rollup, no double counting,
    subscription cost unknown, unpriced components, stale usage, known subtotals, and no retroactive
    budget authority.
25. Approval tests cover every state, plan changes, expiry, supersession, unrelated grants,
    evidence-as-authority attempts, separate fan-in/publication grants, and hard non-delegable gates.
26. Privacy tests inject credentials, reversible encodings, private prompts, model output, paths,
    URLs, issue bodies, and account identity at every serialization boundary. Output must preserve
    the blocking fact without preserving the sensitive body.
27. Supply-chain tests reject ambient PATH substitution, mutable versions, missing digests,
    unsigned or mismatched manifests, unknown tools/MCPs, silent downloads, and licence/NOTICE drift.
28. External-library tests reuse the existing collision and own-front-door lifecycle seam. No Core,
    setup, hook, or gate path may reach a companion installer.
29. Writing tests assert BLUF summary placement, countable-rule reports, claim-strength
    preservation, exact donor notice, and negative ASD compliance/dictionary/logo claims.
30. Mermaid tests retain the existing source/sandbox/sanitizer seam and keep renderer provisioning
    outside the authoritative gate.
31. Draw.io tests cover strict XML parsing, canonical source, semantic IDs/references, external
    content rejection, preservation inspection, assets/licences, derived render receipts, schema
    migration preview, selection collision, and artifact-preserving retirement.
32. Threat-model tests cover selector counterexamples, DAG order, bounded fan-out, canonical
    artifact references, STRIDE and abuse-case coverage dispositions, human-only risk writes,
    author/reviewer/verifier separation, independent verification, sensitive storage, egress,
    drift re-entry, unsupported profiles, and partial handoffs.
33. Compatibility tests cover below minimum, exact minimum, dated references, unlisted newer,
    known incompatible, and higher-profile-floor versions. Tested references must never become a
    maximum allowlist.
34. Platform tests keep Linux, WSL2, WSL1, macOS architectures, native Windows shells, glibc/musl,
    installation planes, Core, and optional profiles in separate evidence rows.
35. Claim tests reject provider-neutral/equal-parity, blanket cross-platform/latest, provider-wide,
    model-wide, official-product, replacement, universal-gateway, bundled-companion, unsupported
    renderer, ASD-conformance, and security-completeness language.
36. Use existing prior art: installer lifecycle and fault tests, activation transaction tests,
    Seeds launcher tests, worktree fail-closed tests, runtime-contract validation, route launcher
    tests, rightsizing evaluator tests, gate receipt tests, Mermaid renderer tests, external-library
    tests, authority correction tests, role submission tests, and ADR lifecycle tests.
37. The authoritative offline gate remains `mise run check`. Live provider, billing, route,
    attribution, host-feature, and platform canaries are separate approved release evidence.
38. A passing gate or canary is evidence only and must never authorize installation, provider
    mutation, fan-in, publication, deployment, or queue mutation.

## Out of Scope

- Replacing Claude Code or building a general-purpose agent runtime.
- Building a model gateway rather than integrating the optional OCX dependency.
- Equal feature parity across Codex, Gemini CLI, OpenCode, Windows, macOS, or every companion host.
- Supporting every provider, model, route, credential type, plugin, MCP, library, renderer, or
  threat-model format.
- Vendoring external skill libraries or installing them through Core, setup, hooks, or gates.
- Automatically cleaning an entire brownfield repository during activation.
- Automatically committing, pushing, opening or mutating PRs, merging, publishing, releasing,
  deploying, changing credentials, or mutating external trackers.
- Treating Auto mode, Dynamic Workflows, reviews, gates, receipts, Seeds, ADRs, or `--yolo` as
  authority.
- Silent model/provider/slot fallback, silent update, silent trust, silent provider setup, silent
  repair, or default telemetry.
- A product-managed evidence-history purge or a self-updater in version one.
- A hosted dashboard, telemetry warehouse, required daemon, or remote observability service.
- Complete brownfield write-readiness in the first successful journey.
- Cross-platform draw.io renderer certification in the first release.
- One selectable skill per generic diagram type.
- Risk acceptance by agents, automated security approval, threat completeness, or proof that a
  system is secure.
- ASD-STE100 compliance, certification, dictionary reconstruction, logo use, or endorsement claims.
- STARLORD support until a distinct intended method and product need are separately established.
- Automatic migration or deletion of historical PRIME/DRIVE/gateway Seeds.
- Modifying product implementation, provider configuration, trust state, installed companions, or
  external systems as part of this specification publication.

## Further Notes

- The canonical descriptor is: “A Claude Code-first, evidence-driven SDLC harness for greenfield
  and brownfield repositories.”
- ADR-0017 through ADR-0020 and ADR-0022 through ADR-0027 are accepted product constraints.
- ADR-0021 remains proposed until a self-contained versioned release and clean-host lifecycle
  evidence exist. ADR-0011 remains the accepted current checkout topology until then.
- ADR-0028 remains proposed with an in-progress rollup because ADR-0021 is its one proposed child.
- The current `0.7.3` checkout, manifests, and dispatcher are brownfield evidence, not the target
  release experience.
- Preserve current lifecycle ownership, activation transactions, Seeds launcher, worktree
  controls, rightsizing evaluator, route launcher, Mermaid renderer, gate stack, and negative tests.
  Build the missing product composition around them rather than creating parallel engines.
- The current repository's provider-neutral multi-host descriptions require a coordinated claim
  migration only after the executable Core surface exists.
- Non-Claude routing through Claude Code may be supported by Agentic SDLC for exact qualified tuples
  while remaining unsupported by Anthropic. Product documentation must state both facts.
- The initial Core host minimum is Claude Code 2.1.154 with Dynamic Workflows effectively enabled.
  The dated reference candidates are 2.1.224 stable and 2.1.233 latest; neither is a certification
  or hard maximum.
- Linux x64 and WSL2 Linux x64 are the first complete certification targets.
- Residual implementation discovery includes release archive layout, exact Dynamic Workflow host
  calls, XDG file layout and locks, usage/readback fields, composition of current activation
  primitives, the first draw.io renderer tuple, and later historical Seed dispositions. These are
  implementation questions, not open product choices.
- The build should proceed in tracer bullets: release identity and claims; read-only `ccodex sdlc`;
  lifecycle mutations; greenfield/brownfield activation; one native-Claude Core wave; planning and
  observability; routed-model profile; documentation/diagram/security capabilities; then dogfood
  and stable release.
- A stable release requires exact installed-byte greenfield and brownfield journeys, one certified
  Core tuple, current compatibility evidence, negative safety tests, truthful claims, and no
  optional routing, companion, renderer, telemetry, or bypass enabled by default.
- This specification is ready for decomposition into implementation tickets. Publishing it does
  not authorize implementation, queue mutation beyond the single spec issue, fan-in, or any
  outward effect.
