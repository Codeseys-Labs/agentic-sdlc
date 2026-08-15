# Find the path to a Claude Code-first Agentic SDLC product

Label: wayfinder:map
Status: resolved

## Destination

A decision-complete product and architecture brief for Agentic SDLC as a Claude Code-first
opinionated harness, ready to hand to `/to-spec`. It settles every product and architecture
choice needed before specification; it does not implement the product.

## Notes

- Claude Code is the primary product host because Dynamic Workflows are the execution substrate.
  Other capable hosts consume portable skills and shared contracts without an equal-parity promise.
- Treat the current repository, accepted ADRs, and verified code as brownfield evidence. Separate
  current behavior from dated research, stale queue entries, and desired behavior.
- Consult `/grilling` and `/domain-modeling` for human decisions, `/research` for external facts,
  and the repository's ADR lifecycle when a resolved trade-off warrants a durable record.
- Preserve the current safety posture: evidence is not authority; foreign bytes are not vendored;
  partner libraries use their own front doors; unrelated dirty work is not touched.
- Prefer BLUF and the repository's countable clarity rules in human-facing artifacts.
- This map uses the local-Markdown tracker because the existing Seeds queue has no active admitted
  conductor-write receipt. Migrating the map later is tracker administration, not a product decision.

## Decisions so far

<!-- Empty at charting. Resolved ticket answers are indexed here by name. -->

- [Define the first user and first successful journey](issues/01-define-first-user-and-successful-journey.md) — Serve experienced Claude Code users on greenfield or brownfield repositories; `/sdlc-init` leads to one reviewed admitted wave, including honest remediation progress when the whole repository is not yet write-ready.
- [Verify the current Claude Code Dynamic Workflows extension contract](issues/02-verify-dynamic-workflows-extension-contract.md) — Dynamic Workflows are plugin-distributable and version-gated; effective route, model, and effort still require an executed canary with independent evidence.
- [Compare the current boundaries of opinionated coding-agent harnesses](issues/03-compare-opinionated-harness-boundaries.md) — Own a narrow, explicit lifecycle and one first workflow; reject replacement runtimes, silent takeover, default telemetry, and permission-bypass defaults.
- [Verify the current companion-library contracts](issues/04-verify-companion-library-contracts.md) — Keep own-front-door, explicit lifecycle choices; SimpleEnglish needs new onboarding, while ECC npm setup and generic HyperResearch removal are not currently automation-safe.
- [Define the core harness and companion-profile boundary](issues/05-define-core-and-companion-boundary.md) — The core completes a reviewed native-Claude journey; owned profiles are explicit and receipt-backed, `ccodex` activates routed models, and external libraries remain complementary own-front-door companions.
- [Define the multi-provider support promise](issues/06-define-multi-provider-support-promise.md) — `claude` serves subscription models while `ccodex` adds qualified OCX routes; support is exact, current, independently evidenced, operator-credentialed, and never silently falls back.
- [Define the Dynamic Workflow execution and graph contract](issues/07-define-dynamic-workflow-graph-contract.md) — One approved wave is one artifact-driven DAG; exact runtime assignments, configurable bounds, optional canary-gated recursion, bounded auto mode, authoritative fan-in, and adversarial completion evidence govern execution.
- [Research the `npx skills` lifecycle for installation inspiration](issues/18-research-npx-skills-lifecycle.md) — Adapt bounded discovery, explicit selectors, declarative host projection, deterministic intent, and sanitizers; reject implied consent, presence-based overwrite/delete, non-transactional update, false dry-run, and default egress.
- [Choose the canonical installation, update, and recovery experience](issues/08-choose-installation-and-update-experience.md) — A versioned mise release installs the `ccodex` operator CLI; `ccodex sdlc` explicitly activates and maintains the native-Claude core, while routed sessions, profiles, companions, recovery, and removal keep separate receipt-backed approvals.
- [Define the downstream repository activation and hygiene contract](issues/09-define-repository-activation-contract.md) — `/sdlc-init` assesses then applies a digest-approved portable contract, preserves brownfield state, defaults to Seeds and pinned DevEx, enforces isolated custody/fan-in, and distinguishes write-ready from bounded remediation-ready.
- [Define the security, credential, telemetry, and authority boundaries](issues/11-define-security-telemetry-and-authority-boundaries.md) — Six least-privilege planes, credential custody, no product telemetry, declared egress, content-minimized evidence, hard human gates, labeled control strength, bounded retention, and verified supply-chain/tool trust govern every workflow.
- [Compare SimpleEnglish with the core clarity profile](issues/22-compare-simpleenglish-with-core-clarity.md) — The core already owns most mechanics; adapt five narrow ideas with exact donor notice, but add no duplicate skill, output style, vocabulary table, or lifecycle surface.
- [Research draw.io agent diagram workflows](issues/23-research-drawio-agent-diagram-workflows.md) — One optional umbrella with lazy type references is viable for safe editable XML authoring; generic per-type skills and a certified renderer claim are not yet justified.
- [Define the documentation and communication defaults](issues/10-define-documentation-and-communication-defaults.md) — BLUF and countable clarity govern human/agent prose; five SimpleEnglish ideas enter with donor notice, ASD claims stay honest, evidence remains traceable, diagrams stay purposeful, and prose tooling is advisory by default.
- [Define the draw.io diagram skill family](issues/24-define-drawio-diagram-skill-family.md) — Core ships one optional `drawio-diagrams` umbrella with strict editable-source custody, lazy family references, foreign-asset preservation, advisory platform-certified rendering, collision-safe lifecycle, and a separate threat-modeling workflow boundary.
- [Curate the first-party agent-persona roster](issues/17-curate-agent-persona-roster.md) — The core roster freezes at seven existing roles plus `sdlc-documentarian`; all roles use capability-demand routing and a versioned common submission, while documented security task roles must earn any later permanent promotion.
- [Define the first-party threat-modeling workflow](issues/25-define-threat-modeling-workflow.md) — Core ships a native-first, sensitive-by-default threat-modeling DAG with bounded parallel analysis, typed durable artifacts, versioned STRIDE and abuse-case profiles, human-only risk disposition, independent mitigation verification, and drift-aware lifecycle controls.
- [Refine `/sdlc-rightsize` and the model-task map](issues/15-refine-model-rightsizing-and-task-map.md) — Rightsizing maps capability demands and wrong-output consequences to exact class-qualified native or OCX routes through approved local evaluation, immutable evidence generations, structured Pareto recommendations, fail-closed refresh and quarantine, and offline release acceptance.
- [Define provider onboarding and route-control UX](issues/19-define-provider-onboarding-and-route-control-ux.md) — `ccodex routes` starts successfully in native-only mode, adds exact credential-slot-bound providers through digest-approved staged lifecycles, keeps readiness dimensional, delegates qualification to rightsizing, and recovers or removes without secret exposure, silent fallback, invented rollback, or history purge.
- [Define operator observability and receipt experience](issues/20-define-observability-and-receipt-experience.md) — One local read-only observability spine projects typed journals and immutable receipts into dimensional status, DAG progress, exact-or-labeled usage and egress, approval/recovery views, and truthful terminal wave handoffs without telemetry, duplicated truth, secret exposure, or manufactured success.
- [Define planning workflows, drift correction, and bounded auto mode](issues/16-define-planning-drift-and-bounded-auto-mode.md) — Immutable mission, snapshot, plan, diff, and AutoEnvelope artifacts drive a deterministic read-only compiler, four-class drift handling, digest-bound admission and approval, closed bounded-autonomy transitions, and evidence-based pause/resume without permission bypass or invented continuity.
- [Define the branding, positioning, and compatibility promise](issues/12-define-positioning-and-compatibility-promise.md) — Agentic SDLC is the Claude Code-first product, `ccodex` its operator CLI, and OCX an optional routing dependency; minimum feature requirements plus runtime capability admission avoid hard version ceilings, while exact evidence tuples, independent profile/platform tiers, stable/preview channels, deprecation, and claim linting keep support honest.
- [Reconcile current repository truth with the chosen product contract](issues/13-reconcile-repository-truth.md) — Preserve the strong lifecycle, safety, Seeds, worktree, routing, rightsizing, diagram, and test substrate; the missing layer is the versioned `ccodex sdlc` product, owned native-Claude workflow, planning/auto artifacts, observability spine, and selected optional capabilities, while contradictory multi-host claims and historical queue entries require explicit migration rather than silent rewriting.
- [Record the cross-cutting product-boundary ADRs](issues/21-record-product-boundary-adrs.md) — Ten reviewed boundary ADRs are accepted; the versioned-release topology remains proposed behind ADR-0011's evidence condition, and the proposed initiative rollup stays in progress with exact child statuses, typed relationships, legacy-metadata debt, and non-mutating implementation proposals recorded.
- [Assemble the decision handoff for `/to-spec`](issues/14-assemble-to-spec-handoff.md) — The linked product and architecture brief is decision-complete: all prerequisites are resolved, residuals are bounded implementation discoveries, non-goals and release evidence are explicit, and the tracer-bullet sequence is ready for specification.

## Decision closure

No product or architecture choice remains open. The final brief is
[`to-spec-handoff.md`](to-spec-handoff.md). Exact implementation schemas, archive layout, Workflow
calls, XDG paths, usage readback, renderer tuples, and later queue dispositions belong to
`/to-spec` discovery. Any implementation finding that would change a boundary in this map returns
for human decision instead of being silently resolved in code.

## Out of scope

- Implementing product code, changing provider configuration, installing libraries, or publishing
  a release. Those begin only after `/to-spec` and `/to-tickets` produce an approved build plan.
- Equal feature parity for non-Claude hosts. Portable contracts remain in scope; parity does not.
- Automatically installing every external skill library or claiming literal support for every
  model and provider.
- Replacing Claude Code or building a general-purpose model gateway from scratch.
- Modifying or reconciling the current dirty feature-branch work during wayfinding.
- A `ccodex` self-updater. The first release delegates version acquisition and selection to mise;
  self-update may be designed later after the receipt-backed lifecycle is proven.
