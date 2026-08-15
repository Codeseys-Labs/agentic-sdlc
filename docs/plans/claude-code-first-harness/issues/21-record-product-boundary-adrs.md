# Record the cross-cutting product-boundary ADRs

Type: task
Status: resolved
Blocked by: 13
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Using the resolved Wayfinder decisions and repository-truth delta, run the ADR significance and
readiness gates, split each qualifying product boundary into one decision per record, relate or
supersede existing records without editing accepted bodies, select honest lifecycle states, and
rebuild the ADR index. At minimum assess separate records for product-plane/privacy defaults,
authorization and evidence strength, supply-chain/tool trust, installation topology, repository
activation, documentation and evidence defaults, Dynamic Workflow execution, and threat-modeling
authority and artifact boundaries. Preserve the current dirty ADR work and emit typed Seed
proposals for implementation gaps rather than treating records as authorization or proof.

## Significance and readiness assessment

The eleven child records below pass the significance gate: each constrains a cross-cutting interface,
accepts a named safety, operability, or portability cost, or governs an external dependency. The
operator is the human decider through the resolved Wayfinder decisions; the repository-truth audit
provides current evidence; at least two real options and a concrete negative consequence exist for
each. Extended tier is appropriate because the records form a related product-boundary graph.

The child count also clears the ADR lifecycle's multi-record initiative threshold. ADR-0028
therefore owns only the registry, scope boundary, and sequencing view; it does not merge child
decisions or substitute its status for theirs.

| Planned ADR | Result | Reason |
|---|---|---|
| Claude Code primary host and native Core | Qualifies | Governs product identity, execution substrate, host parity, and the optional OCX relationship; it replaces ADR-0005's default-OpenCodex topology. |
| Product-plane and privacy defaults | Qualifies | Governs credential custody, sensitive content, egress, telemetry, and retention across every surface. |
| Authorization and evidence strength | Qualifies | Governs every mutation and outward effect and prevents advisory claims from becoming permission. |
| Supply-chain and tool trust | Qualifies | Governs external dependencies and exact executable/provenance boundaries across installation and dispatch. |
| Versioned mise release and `ccodex sdlc` topology | Qualifies, stays proposed | Expensive distribution boundary, but ADR-0011's observable supersession condition has not fired because no release artifact exists. |
| Repository activation | Qualifies | Defines the cross-repository manifest, plan, receipt, readiness, and brownfield-preservation interface. |
| Documentation and evidence defaults | Qualifies | Cross-cuts human and agent communication, licences, traceability, and high-consequence review. |
| Dynamic Workflow execution | Qualifies | Defines the primary execution graph, isolation, fan-in, recursion, and completion authority. |
| Planning, drift, and bounded auto mode | Qualifies | Defines immutable execution inputs and the only permitted autonomy envelope. |
| Threat-modeling authority and artifacts | Qualifies | Adds a security-sensitive first-party workflow while keeping human risk ownership. |
| Compatibility admission and claims | Qualifies | Governs external host versions, exact tuples, platform/profile separation, support tiers, and minimum-plus-capability admission. |
| Product-boundary initiative | Qualifies | Eleven interdependent child records need one registry and explicit critical-path sequence without becoming a mega-record. |

The current ADRs already cover local rightsizing promotion (ADR-0015), external libraries
(ADR-0008/0009), gateway login and route integrity (ADR-0014), and explicit permission bypass
(ADR-0016). Those choices need relationships and specification details, not duplicate records.

## Typed implementation proposals

These are advisory `SeedProposal` records for later conductor triage. They do not create, update,
claim, close, or reorder the repository's Seeds queue.

| Proposal id | Type | Suggested title | Depends on | Acceptance boundary |
|---|---|---|---|---|
| `adr-0017-implementation` | `SeedProposal` | Migrate the product to a tested Claude Code-first Core | ADR-0017 accepted | One installed native-Claude journey passes and all owned claims distinguish Core, `ccodex`, OCX, and companion hosts. |
| `adr-0018-implementation` | `SeedProposal` | Implement product-plane data and privacy schemas | ADR-0018 accepted | Typed egress, retention, redaction, accounting-certainty, incident, and evidence fixtures prove no credential/raw-content persistence or product telemetry. |
| `adr-0019-implementation` | `SeedProposal` | Implement digest-bound approval and effect-state admission | ADR-0019 accepted | Every effectful surface consumes the exact current grant; stale, broadened, cross-effect, and evidence-as-authority cases refuse. |
| `adr-0020-implementation` | `SeedProposal` | Unify exact dependency and capability admission | ADR-0020 accepted | Tools, hosts, routes, models, renderers, and profiles use exact identities, named unknowns, explicit refresh, and no silent fallback. |
| `adr-0021-implementation` | `SeedProposal` | Build and prove the versioned mise release | ADR-0021 proposed | A self-contained exact stable/preview lifecycle, schema readers, deprecation, and clean-host tests pass; only then may ADR-0021 be accepted and ADR-0011 superseded. |
| `adr-0022-implementation` | `SeedProposal` | Compose full greenfield and brownfield activation | ADR-0022 accepted | Installed-byte assess/plan/apply/readback/recover journeys produce truthful write-ready, remediation-ready, conflict, and unknown-effect results. |
| `adr-0023-implementation` | `SeedProposal` | Ship the evidence-preserving documentation profile | ADR-0023 accepted | The documentarian, independent review, narrow SimpleEnglish adaptation, donor notice, BLUF handoff schema, and negative ASD-claim tests pass. |
| `adr-0024-implementation` | `SeedProposal` | Ship the first native-Claude Dynamic Workflow wave | ADR-0024 accepted | One bounded artifact DAG proves exact dispatch, isolated custody, pause/stop, immutable review, adversarial disposition, and authorized serial fan-in. |
| `adr-0025-implementation` | `SeedProposal` | Implement immutable planning and bounded auto mode | ADR-0025 accepted | Deterministic artifacts, drift classes, stale-plan refusals, closed auto transitions, and evidence-based resume pass without effect capability in the compiler. |
| `adr-0026-implementation` | `SeedProposal` | Ship the first-party threat-modeling workflow | ADR-0026 accepted | Versioned model/method profiles, sensitive storage, human disposition, independent mitigation verification, and stale/unsupported profile refusals pass. |
| `adr-0027-implementation` | `SeedProposal` | Implement compatibility admission and claim gates | ADR-0027 accepted | Minimum/newer/exclusion fixtures, independent platform/profile rows, claim lint, and one certified Core tuple pass. |
| `legacy-adr-status-normalization` | `SeedProposal` | Reconcile legacy ADR-0008 and ADR-0015 lifecycle metadata | Independent lifecycle review | A new reviewed record or permitted status-only correction resolves each noncanonical value without rewriting either accepted body or strengthening a partial decision by inference. |

## Answer

The significance and readiness gate produced eleven child decisions plus one initiative record.
Independent review initially blocked acceptance on over-broad supersession, reversed relationship
semantics, mixed decisions, hypothetical confirmations, transient evidence, and the missing
initiative rollup. The records were narrowed and reviewed again. The final independent review was
clear for the following dependency-ordered lifecycle transitions:

- **Accepted:** ADR-0017 through ADR-0020 and ADR-0022 through ADR-0027.
- **Proposed:** ADR-0021, because no versioned release artifact or clean-host lifecycle evidence
  exists and ADR-0011 remains the accepted current topology.
- **Proposed, rollup in progress:** ADR-0028, because its live child registry names ADR-0021 as the
  one proposed child.

ADR-0017 now refines only ADR-0005's default-install and normal-product posture; it does not retire
the older record's still-live launcher, supervision, qualification, or non-authority controls.
ADR-0021 carries the sole new `Supersedes` edge, but no status change occurs until it becomes
accepted. ADR-0005 and ADR-0011 were not edited.

The rebuilt index also labels ADR-0008 and ADR-0015's inherited noncanonical lifecycle metadata as
legacy debt rather than silently normalizing or strengthening it. The typed implementation and
metadata proposals above remain advisory; `.seeds/issues.jsonl` was not changed.

Validation evidence:

- all 28 ADR files appear in the rebuilt index;
- every ADR-0017 through ADR-0027 status matches ADR-0028's current child registry;
- all relationship targets exist, all eleven children carry `Part-Of: ADR-0028`, and the
  `Depends-On` graph has no cycle;
- `python3 -m unittest tests.test_adr_lifecycle` passes 26 tests;
- `python3 scripts/validate_bundle.py` reports zero errors and warnings; and
- `git diff --check` passes for the planning and ADR surfaces.

These records are decision evidence. They do not make absent product code conforming and authorize
no queue mutation, implementation, install, trust, inference, fan-in, publication, or deployment.
