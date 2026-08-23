# Repository truth reconciliation for the Claude Code-first product contract

**Audit date:** 2026-08-15
**Repository:** `agentic-sdlc`
**Observed branch:** `feat/ccodex-rightsizing-controls`
**Observed commit:** `24c4b1113789260d6d73ddb133430b4ae8af329d`

## BLUF

The repository has a strong safety and delivery substrate, but it does not yet ship the complete
Claude Code-first product described by the resolved Wayfinder decisions. Existing lifecycle
ownership, external-library isolation, Seeds custody, worktree doctrine, route evidence,
rightsizing, Mermaid, gates, and adversarial tests should be retained and composed. The missing
product layer is the versioned `ccodex sdlc` distribution and control plane, the owned Dynamic
Workflow implementation, deterministic mission and planning artifacts, bounded auto/drift
handling, a unified observability spine, and the newly selected documentation and security
capabilities.

The public truth is also inconsistent. `VISION.md` says Claude Code is primary, while `README.md`,
`AGENTS.md`, and every current host manifest still lead with a provider-native multi-host bundle.
Those declarations must not be changed in isolation. The implementation specification must first
name the executable replacement surface and its migration, then update all claims together.

## Audit boundary and evidence order

This was a read-only product reconciliation. It did not edit code, ADRs, README, VISION, manifests,
installers, tests, or `.seeds/issues.jsonl`. The only pre-existing untracked paths were `.scratch/`
and `CONTEXT.md`; they remain planning custody rather than shipped product evidence.

Use evidence in this order when two surfaces disagree:

1. Executed code and focused tests establish current behavior.
2. The newest accepted ADR controls a decision and its supersession relationships.
3. Current operator and agent instructions describe intended use, but a claim is not executable
   merely because it appears in `README.md`, `AGENTS.md`, a skill, or a command runbook.
4. The resolved Wayfinder tickets and `CONTEXT.md` define the chosen product target, not current
   implementation.
5. Dated research nominates facts and designs; it does not ship or certify them.
6. Seeds records historical roadmap state. An open or closed Seed is neither current-behavior proof
   nor authority to mutate the queue.

Classifications below mean:

- **Satisfied:** a current owned surface and direct evidence already meet the resolved contract.
- **Strong partial:** the load-bearing substrate exists, but product composition or acceptance
  evidence is incomplete.
- **Partial:** some useful surface exists, but a material portion of the contract is absent.
- **Contradictory:** a current claim or behavior conflicts with the resolved contract.
- **Absent:** no owned current product surface was found after exact-name and concept searches.
- **Historical only:** the statement exists only as dated research, a superseded ADR, or queue text.

## Current-truth delta

| Product area | Classification | Current repository truth | Required specification delta |
|---|---|---|---|
| Product name and host priority | **Contradictory** | `VISION.md:3` calls Claude Code the primary target. `README.md:3-5,25-37`, `AGENTS.md:3-6,36-42`, `.claude-plugin/plugin.json:3-5`, `.codex-plugin/plugin.json:2-11`, `.agents/plugins/marketplace.json:2-9`, and `gemini-extension.json:2-4` instead present a provider-native multi-host kit. | Make **Agentic SDLC** the Claude Code-first product and `ccodex` its operator CLI. Keep portable companion-host contracts without equal-parity language. Update every owned claim surface through one tested claim-linting change. |
| Native-Claude Core journey | **Partial** | `/sdlc-frame`, `/sdlc-wave`, and `/sdlc-mission` document Frame-to-Ship behavior, and the flagship skill defines the phase loop (`skills/agentic-sdlc/SKILL.md:148-164`). They remain runbooks and orchestration guidance, not a versioned owned Core journey. | Specify one installed native-Claude journey from assessment through one reviewed admitted wave. Bind the Dynamic Workflow, artifacts, receipts, refusal states, and terminal handoff to executable acceptance tests. |
| Distribution and `ccodex` lifecycle | **Strong partial** | Transactional ownership, conflict preservation, install/status/uninstall, operator-tool lifecycle, host planes, and recovery tests exist. Current `ccodex` is a thin checkout-bound dispatcher (`assets/launchers/ccodex.in:18-29`) whose USE surface is gateway, catalog, bundle, libraries, statusline, and version (`:47-91,247-362`). `README.md:263-270` correctly says the planned versioned mise release does not exist. | Package a versioned mise-resolved release with stable/preview identities. Add `ccodex sdlc` acquire/activate/status/update/recover/remove without making install imply activation, routing, companion install, trust, or config mutation. Preserve current ownership and crash-recovery invariants. |
| Repository activation and hygiene | **Strong partial** | `/sdlc-init` separates global installation from repository activation and documents preservation, Seeds, gates, trust, and receipts. The canonical activation planner has `plan/apply/status/recover`, but the runbook admits it plans one manifest entry and does not itself provide greenfield, readiness, Seeds, trust, Git, or full activation (`commands/sdlc-init.md:19-41`). Transaction and recovery tests exist. | Define `.agentic-sdlc/repo.toml`, local activation receipts, full assessed greenfield/brownfield plans, exact digest approval, write-ready versus remediation-ready results, tracker adapters, canonical `AGENTS.md`, CI parity, and cross-platform behavior. Reuse the existing transaction engine rather than inventing another lifecycle. |
| Dynamic Workflow ownership and graph execution | **Absent as a product surface** | Commands and skills describe workers and waves, and `skills/agentic-sdlc/SKILL.md:181-197` discusses Claude workers and exact dispatch. No owned Workflow implementation or installed overlay was found. The historical queue still has open `agentic-sdlc-g1`, “Ship the bounded Workflow overlay lifecycle” (`.seeds/issues.jsonl:8`). | Specify the first owned Dynamic Workflow DAG, its plugin location and lifecycle, immutable stage artifacts, bounded fan-out, one fan-in owner, exact runtime assignment, configurable caps, optional default-off recursive profile, pause/stop/resume behavior, and adversarial completion review. |
| Mission planning, drift correction, and bounded auto mode | **Absent** | No current product file defines `MissionContract`, `PlanningSnapshot`, `WavePlan`, `PlanDiff`, or `AutoEnvelope`; exact-name searches found no shipped surface. Existing Frame output is a short prose plan (`commands/sdlc-frame.md:43-46`). | Specify versioned schemas and a deterministic read-only compiler. Admit execution only from digest-bound artifacts; classify drift; require human approval by default; allow only explicit bounded auto envelopes; and preserve evidence-based pause/resume without permission bypass or invented continuity. |
| SDLC role roster | **Partial** | Seven roles ship in Claude and Codex forms: cartographer, planner, implementer, reviewer, researcher, critic, and integrator (`AGENTS.md:60-62`; `README.md:162-177`). Research OS separately carries 17 repo-scoped research roles. | Add the eighth permanent role, `sdlc-documentarian`, with the common versioned submission contract and no approval authority. Document the proposed security task roles as workflow-local roles and review lenses; do not promote them to permanent selectors without evidence. |
| Model rightsizing | **Strong partial** | The rightsizing skill, exact OCX dispatch seam, v2 map schema, bounded evaluator, route attribution, approval digest, and extensive tests exist (`AGENTS.md:45-56,223-249`; `commands/sdlc-rightsize.md:1-132`). | Evolve the map around capability demands, wrong-output consequences, exact class qualification, immutable generations, Pareto recommendations, refresh/quarantine, and release-offline acceptance. Preserve the rule that qualification does not authorize dispatch and a runtime receipt still controls admission. |
| Provider onboarding and route control | **Partial** | Current `ccodex` exposes `providers`, `models`, `configure`, `launch`, `status`, and `restart` (`assets/launchers/ccodex.in:51-73,247-323`). ADR-0014 and launcher tests preserve the operator's Claude login and fail closed on route-bypass and billing-confusion conditions. There is no `ccodex routes` lifecycle. | Add a native-only-successful `ccodex routes` surface with dimensional readiness, credential-slot references, staged digest approval, qualification handoff to rightsizing, quarantine/recovery/removal, no silent fallback, and no history purge. Keep OCX optional to Core. |
| Observability and receipt experience | **Partial** | Lifecycle status, gateway status, activation status, runtime-assignment policy, and a tested self-hashing gate-receipt library exist. The receipt itself states it is tamper detection, not a same-user security boundary (`scripts/gate_receipt.py:2-7,35-80`). The generic gate receipt is not wired into `mise run check`; no unified operator spine was found. | Specify one read-only local projection over typed effect journals and immutable receipts. Cover dimensional readiness, DAG progress, exact-or-labeled usage/cost, egress, approval, recovery, and terminal handoff without creating a second truth store or telemetry. Wire receipts only where they have a real consumer. |
| Documentation and communication | **Strong partial** | A BLUF output style ships (`output-styles/bluf.md:1-14`). The technical-writing clarity reference already has honest ASD-derived public rule shapes, countable checks, evidence-preserving rewrites, and no compliance claim (`skills/change-writing/references/technical-writing-clarity.md:10-52,65-80,114-137`). | Add the five narrowly adapted SimpleEnglish ideas and exact donor notice in one change. Apply BLUF to A2H/A2A handoffs, use the documentarian plus independent high-consequence review, and keep prose lint advisory unless a repository explicitly promotes a proven subset. |
| Mermaid and draw.io diagrams | **Partial** | Mermaid authoring, a Linux x64 advisory renderer, sandbox policy, provisioning, receipts, tests, and ADR-0006 exist. No owned draw.io skill or lifecycle was found. | Keep Mermaid core-shipped. Add one core-shipped optional `drawio-diagrams` umbrella with lazy family references, strict editable-source custody, preservation inspection, asset manifests, and platform-specific advisory rendering. Do not create a selectable skill for every generic diagram type. |
| Threat modeling | **Absent** | No first-party threat-modeling skill, STRIDE profile, threat ledger, risk-disposition artifact, or mitigation-verification workflow was found outside research/planning material. | Add a separately selectable native-first threat-modeling workflow. Keep security DFD authoring under draw.io guidance, analysis separate from the diagram, risk disposition human-owned, mitigation verification independent, storage sensitive by default, and model/method profiles versioned and drift-aware. |
| Security, credentials, telemetry, and authority | **Strong partial** | Current doctrine repeatedly separates evidence from authority; launch keeps credentials in their owning front doors; `--yolo` is explicit, off by default, conflict-checked, and visible (`ADR-0016:44-55`); external state is preserved. No product telemetry path was found. | Consolidate the six product planes, declared-egress records, data minimization, approval states, incident receipts, control-strength labels, retention defaults, and outward-effect gates into shared schemas and tests. Do not weaken current refusal behavior. |
| Seeds, worktrees, review, and fan-in | **Strong partial** | The flagship skill has a receipt-bound conductor-only Seeds seam (`skills/agentic-sdlc/SKILL.md:56-85`), target-local worktree doctrine, independent reviews, and sole-integrator authority. Worktree, Seeds, role, review, and authority tests exist. | Compose these pieces into the executable Core wave. Add write-custody artifacts, rebase-then-squash admission, exact pre/post fan-in evidence, human disposition, and end-to-end greenfield/brownfield journey tests. Preserve tracker adapter neutrality with Seeds as the default. |
| External companion libraries | **Satisfied** | The closed catalog, own-front-door install, no-vendoring rule, collision checks, preservation of foreign state, and separation from gates are explicit (`README.md:67-95`; `AGENTS.md:10-34`) and implemented with tests. | Carry this contract into the release/package design. Do not fold companion bytes or automatic installation into Core or `ccodex sdlc`. New libraries need separate verification and onboarding. |
| ADRs and domain language | **Partial** | Sixteen indexed ADRs exist; ADR-0013 is correctly marked superseded by ADR-0014 (`docs/adr/README.md:3-20`). ADR-0008 is only “accepted in part.” The Wayfinder product decisions are not yet recorded in durable ADRs, and the new domain glossary exists only in untracked `CONTEXT.md`. | Ticket 21 must record only significant, hard-to-reverse product boundaries, with explicit relationships to existing ADRs. The specification must identify canonical domain terms, superseded claim language, and any migration rather than rewriting history. |
| Compatibility, release channels, and claims | **Absent as release machinery; research complete** | Current manifests agree on version `0.7.3`, but their descriptions carry the old provider-native claim. The repository has no versioned mise release artifact (`README.md:263-270`) and no stable/preview compatibility matrix or claim lint. Dated primary-source research nominates Claude Code 2.1.224 stable and 2.1.233 latest, and documents Dynamic Workflows at 2.1.154+ (`research/claude-code-version-platform-support-2026-08-15.md:10-29`). | Implement minimum eligibility plus current capability admission, not an exact-version ceiling. Test exact stable/latest references, keep platform/profile rows independent, add stable/preview release contracts, SemVer plus schema versions, deprecation readers, negative claim tests, and at least one certified Core tuple before stable release. |
| Test and release evidence | **Strong substrate, incomplete journey** | The repository has 41 top-level Python test modules covering lifecycle, activation, worktrees, Seeds, routes, rightsizing, receipts, roles, Mermaid, external libraries, and authority. The authoritative gate is documented as `mise run check` (`AGENTS.md:73-84`). No tests exist for the new plan artifacts, `ccodex sdlc`, `ccodex routes`, observability spine, draw.io, threat modeling, documentarian, or compatibility claim matrix. | Preserve focused negative and crash tests. Add tracer-bullet tests around the first native-Claude journey before expanding optional profiles. A green gate remains evidence, never installation, fan-in, publication, or deployment authority. |

## Contradictions and stale declarations that need explicit disposition

### 1. Multi-host product language conflicts with the adopted Claude Code-first position

`VISION.md:3` already states the desired priority, but the README, root agent router, plugin
manifests, Gemini manifest, and marketplace descriptions do not. This is not a request to delete
portable host support. The specification must distinguish:

- Claude Code-first product and Dynamic Workflow execution;
- portable companion-host skills and contracts;
- independently certified host/profile tuples; and
- surfaces that remain experimental or unsupported.

### 2. The current checkout-backed installer is not the adopted release UX

The checkout, mise tasks, Python lifecycle, and symlink/copy projections are real. A self-contained
versioned release acquired through mise, stable/preview side-by-side selection, and the `ccodex
sdlc` namespace are not. The current README already discloses this gap. The implementation should
reuse lifecycle internals, not relabel the present clone-bound dispatcher as complete.

### 3. The command documents exceed the canonical activation planner's present scope

`/sdlc-init` is honest about the gap: its planner handles one reviewed manifest entry, while the
broader runbook still assigns repository assessment, Seeds, trust, Git, readiness, and CI work to
the conductor. The new specification needs one product-level plan that composes those concerns
without claiming the incumbent entry planner already does so.

### 4. Historical queue entries do not cleanly match current code or the adopted target

The Seeds queue has 18 records: 17 open and one closed. It represents the earlier PRIME, gateway-
required DRIVE, and installed-overlay plan. Examples:

- `agentic-sdlc-d1` remains open for a conductor-only Seeds mutation seam, while a current
  receipt-bound `record` seam now exists in the flagship skill and launcher contract.
- `agentic-sdlc-g0` says gateway-owned execution is the only normal execution path, which conflicts
  with the adopted native-Claude Core plus optional routed-model profile.
- `agentic-sdlc-g2` says provider-native Claude is diagnosis/recovery-only, which conflicts with
  ADR-0014 and the adopted Core.
- `agentic-sdlc-p4` repeats that gateway-required posture and therefore cannot govern current
  product wording.

Do not silently close, rewrite, or delete these records. After the specification defines the new
implementation graph, an authorized queue-reconciliation operation should classify each record as
still-valid work, satisfied-but-stale state, superseded scope, or a migration source, preserving
its history and relationships.

### 5. Existing ADRs remain evidence; new decisions need relationships, not retroactive edits

ADR-0014 is current for the operator-login gateway shape and supersedes ADR-0013. ADR-0016 is
current for explicit yolo. ADRs 0008 and 0009 jointly express no-vendoring and own-front-door
companions. The product boundary, Claude Code-first host priority, versioned release/`ccodex sdlc`
shape, activation contract, planning artifacts, observability spine, and optional security/diagram
boundaries still need significance-gated records. New ADRs should say which existing records they
amend, refine, relate to, or supersede.

## Authoritative specification inputs

The implementation specification should treat these as inherited constraints rather than reopen
them:

1. Native Claude subscription use is the sufficient Core path. OCX adds optional exact routed
   models; it does not own Core, credentials, or provider-wide support.
2. `ccodex` is the one installable operator CLI. Its SDLC, route, launch, companion, and maintenance
   surfaces remain separate lifecycle and approval planes.
3. Global acquisition and repository activation are distinct. Installation never implies trust,
   activation, provider setup, library installation, or execution.
4. Activation is assess-plan-approve-apply-readback. Greenfield and brownfield are determined by
   occupied contract surfaces, not repository age.
5. Seeds is the default tracker, not the only tracker. One authoritative queue and one conductor
   mutation seam remain mandatory.
6. One approved wave is an artifact-driven DAG. One writer owns each write set and worktree; one
   authorized integrator owns serial fan-in.
7. Every actual model spawn has an exact resolved runtime assignment and post-run identity evidence.
   Requested values do not become observed values.
8. Human authority is operation-specific and digest-bound. Gates, reviews, agents, receipts, and
   queue state never grant outward authority.
9. No product telemetry ships. Egress is declared; sensitive content stays in its owning plane;
   operational evidence is minimized and redacted.
10. External libraries stay unvendored and opt-in through their own front doors.
11. BLUF and countable clarity govern product prose without ASD-STE100 compliance claims or a
    reconstructed dictionary.
12. Mermaid remains core-shipped; draw.io is a core-shipped optional skill; threat modeling is a
    separately selectable first-party workflow.
13. Compatibility uses minimum feature requirements plus current capability admission. Exact
    tested versions are evidence, not a hard maximum.

## Recommended tracer-bullet implementation order

This order minimizes duplicate machinery and exposes contradictions early:

1. **Release identity and claim floor:** define schemas, stable/preview release identity,
   compatibility rows, and negative product-claim tests. Keep the current checkout path as an
   explicit development/customization plane.
2. **`ccodex sdlc` lifecycle:** package the existing ownership/recovery substrate behind the new
   namespace with read-only status first, then assessed install/update/recover/remove.
3. **Repository activation slice:** compose current activation transactions into one greenfield and
   one brownfield assessed plan, repository manifest, local receipt, and truthful write-ready or
   remediation-ready outcome.
4. **Native-Claude Core wave:** ship one bounded Dynamic Workflow using the existing role,
   RuntimeAssignment, Seeds, worktree, review, and fan-in contracts. Prove one small journey before
   autonomous missions or recursive profiles.
5. **Planning and observability:** add mission/snapshot/plan/diff/AutoEnvelope schemas, deterministic
   compiler, effect journals, immutable receipts, and the read-only operator projection around the
   now-real Core execution.
6. **Routed-model profile:** add `ccodex routes`, then integrate current OCX launch and rightsizing
   evidence without making the gateway mandatory or weakening native-only success.
7. **Documentation and security capabilities:** add the documentarian, SimpleEnglish adaptation,
   draw.io umbrella, and threat-modeling workflow as independently selectable, tested surfaces.
8. **Dogfood and release:** run exact installed-byte greenfield and brownfield journeys, reconcile
   the historical Seeds queue under separate authority, record ADRs and compatibility evidence,
   and publish stable only after a certified Core tuple exists.

## Unknowns that belong in specification discovery, not product re-decision

- The exact archive and executable layout of the first mise release.
- Which current activation transaction primitives can be composed without schema migration.
- The smallest Dynamic Workflow tracer bullet that exercises creation, approval, worker execution,
  artifact handoff, pause/stop, independent review, and terminal receipt on the minimum host floor.
- The exact XDG paths and schema-reader migration for side-by-side stable and preview state.
- Which usage/cost fields Claude Code and OCX can independently report for each lane without
  estimating or double counting.
- The first renderer/platform tuples worth certifying for draw.io; source authoring does not wait on
  renderer certification.
- The exact Seed dispositions after the implementation plan exists. The present audit identifies
  contradictions but does not authorize queue mutation.

## Reconciliation verdict

Proceed to ADR recording and `/to-spec` assembly. Do not begin by replacing the installer or
rewriting the whole repository. The specification should preserve the current safety substrate,
name the missing product composition explicitly, and make the native-Claude first journey the
acceptance spine against which every optional profile is independently added.
