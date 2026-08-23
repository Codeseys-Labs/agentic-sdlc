# Define the first-party threat-modeling workflow

Type: grilling
Status: resolved
Blocked by: 07, 11, 17, 24
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Should Agentic SDLC ship a separately selectable first-party `threat-modeling` workflow, and what
evidence earns that top-level surface? Define its selector, scope and asset discovery, typed
security DFD handoff, methodology profiles, threat-and-mitigation ledger, coverage semantics,
adversarial review, verification, sensitive-data handling, drift detection, human risk ownership,
artifact backends, interoperability claims, lifecycle, acceptance tests, and retirement policy.
Start with task-specific roles. Treat permanent personas as a separate promotion decision, and do
not turn STRIDE coverage, a validator, or an agent verdict into a security-completeness claim.

Research input:
[Security threat-diagram methods](../research/security-threat-diagram-methods.md).

## Answer

### Top-level admission and selector

Ship `threat-modeling` in the core distribution as an optional task-selected first-party skill. It
earns a top-level row through a distinct selector, necessary multi-stage sequencing, a stable
input/output contract, an explicit author-to-reviewer handoff, and a live cross-repository use
case. It requires no draw.io renderer, gateway, external provider, or third-party skill library.

Select it when work must identify design threats, analyze assets or trust boundaries, produce or
update a reviewed threat-and-mitigation ledger, or verify proposed mitigations against a scoped
system model. An approved repository policy may recommend it for qualifying security-sensitive
changes, but activation is not security approval.

Reject diagram-only DFD authoring in favor of `drawio-diagrams` or Mermaid. Reject generic secure
code review in favor of reviewer or critic lenses. Vulnerability scanning, dependency scanning,
incident response, forensics, penetration testing, red-team execution, compliance audit,
organizational risk scoring, and residual-risk acceptance remain separate capabilities or human
responsibilities. A completed workflow never means that the system is secure.

### Workflow DAG and authority separation

The workflow is `Admit -> Discover -> Model -> Enumerate -> Propose -> Challenge -> Human triage
-> Implement separately -> Verify -> Handoff`.

1. **Admit:** record the system/version, purpose, scope, exclusions, data sensitivity, human risk
   owner, evidence sources, method, budget, and stop conditions. Missing scope blocks the run. A
   missing risk owner permits analysis but blocks risk disposition.
2. **Discover:** `security-evidence` maps assets, use cases, actors, trust zones, data, controls,
   dependencies, code, IaC, and unknowns with provenance.
3. **Model:** `threat-model-author` creates the typed system model and security DFD. Mermaid,
   draw.io, or a nonvisual graph may be the artifact backend.
4. **Enumerate:** apply the selected methodology profile. Start with STRIDE plus an independent
   abuse-case pass. Every considered item records `applicable`, `not_applicable`, or `deferred`
   with rationale.
5. **Propose:** create traceable threat records and mitigation candidates. Emit typed Seed
   proposals without queue mutation. Do not invent priority, effectiveness, or acceptance.
6. **Challenge:** an independent reviewer or critic attacks scope, trust assumptions, coverage,
   abuse cases, stale evidence, and controls. The author cannot review or repair inside this node.
7. **Human triage:** the human risk owner prioritizes, accepts, rejects, defers, or requests
   revision. No agent crosses this gate.
8. **Implement separately:** approved mitigations become ordinary authorized SDLC workstreams.
   Threat modeling remains analysis-only by default.
9. **Verify:** `mitigation-verifier` checks implemented controls against explicit verification
   conditions and current evidence. Code presence or a passing test is not automatically enough.
10. **Handoff:** record unresolved threats, accepted risk, deferred work, evidence digests, model
    freshness, review disposition, verification state, and drift triggers.

Author/reviewer revision loops are bounded and return to human triage when limits are reached. No
workflow state authorizes push, merge, deployment, publication, or risk acceptance.

### Bounded stage fan-out and single-owner fan-in

Parallelism is optional and proportional to scope. Admit may gather parallel advice, but the
conductor records one scope and a human approves it. Discover partitions repository, IaC,
identity, data, dependency, and operational evidence. Model may compare independent candidates or
disjoint system slices, but one author owns the canonical graph. Enumerate partitions elements,
boundaries, STRIDE categories, and abuse-case lenses. Propose partitions threat clusters without
assigning priority. Challenge runs independent attacker, coverage, privacy, supply-chain, and
operations lenses. Human triage remains one non-delegable gate. Implementation uses ordinary
isolated workstreams, verification partitions controls, and one documentarian owns the canonical
handoff.

The conductor or compiled workflow owns spawning by default. Recursive worker spawning requires
the separately approved recursive-execution profile. Every worker receives a disjoint partition or
named lens, exact `RuntimeAssignment`, immutable inputs, and one `RoleSubmission`. No two agents
write the same canonical artifact or share a worktree. Candidates remain immutable; a designated
synthesizer performs deterministic fan-in and preserves conflicts, minority findings, and unknowns
rather than voting them away. Retries do not count as independent review.

Admission records WIP, token and cost limits, routes, content egress, and stop conditions. Phase
barriers admit required artifacts before dependent work starts. Sensitive evidence restricts
fan-out to approved routes. Exceeding a limit produces a partial evidence-backed handoff instead of
silently expanding the graph.

### Durable artifact authority

Each scoped threat model has one logical artifact set whose storage plane is selected separately
from its schema:

- `model-manifest.json` owns model identity, schema, system/version, scope, exclusions, methods,
  sensitivity, owners, workflow state, and artifact digests.
- One canonical topology source—`system.drawio`, `system.mmd`, or `system-model.json`—owns stable
  element IDs, typed topology, flows, trust zones, and backend-specific layout.
- `threat-ledger.json` owns coverage dispositions, threats, affected elements, assumptions,
  proposed mitigations, accountable owners, verification conditions, status, and linked Seed
  proposals. It contains no agent-created risk acceptance.
- `risk-dispositions.json` contains only human-recorded priority, deferment, rejection, acceptance,
  rationale, accountable identity, policy reference, and time. Threat authors and reviewers cannot
  write it.
- `evidence-index.json` owns evidence IDs, exact pointers or digests, class, freshness,
  sensitivity, and gaps. Source material is referenced instead of copied unless retention is
  explicitly approved.
- `reviews/<review-id>.json` and `verification/<verification-id>.json` are immutable records bound
  to exact model and ledger digests.
- `handoff.md` is a BLUF human view linking canonical IDs and unresolved actions. It is derived
  communication rather than machine authority.

Machine records use versioned JSON Schemas and deterministic serialization. Records carry stable
IDs, input digests, creation time, role, runtime receipt, sensitivity, and evidence strength where
relevant. Cross-artifact references expose drift. Partial stages persist valid incomplete
artifacts and blockers. Markdown does not duplicate canonical threat facts, agent transcripts are
not the durable model, and rendered visuals remain derived from the selected editable topology
source.

### Model and method profiles

A `model profile` defines the typed system representation. A `method profile` defines how analysis
interrogates that model. Version 1 ships `security-dfd-v1` as the initial model profile,
`stride-v1` as the initial enumeration method, and `adversarial-abuse-case-v1` as a mandatory
independent challenge profile.

Each profile declares its exact ID and version, primary-source provenance and adaptation notice,
selector and scope, inputs and evidence, coverage units, applicability rules, output schema,
stable IDs, machine checks, limitations and unsafe claims, independent-review requirement,
fixtures, maintainer, refresh process, and retirement policy.

Every in-scope element/category pair records `applicable`, `not_applicable`, `deferred`, or
`out_of_scope`. A missing record is `not_evaluated` and blocks a mechanical-coverage claim.
`applicable` links threat IDs or records `no_threat_identified` with rationale; that phrase means
only that this run found none. `not_applicable` requires rationale. `deferred` requires an owner and
re-entry trigger. `out_of_scope` cites the approved boundary. Validators check structure and
references, never analytical truth. Reports show counts and gaps without a quality, security, or
completeness score.

Multiple profiles may analyze one model, and findings retain profile provenance after deduplication
or cross-linking. Future privacy, attack-tree, PASTA, STPA-Sec, or other methods require separate
primary-source research and profile admission. STARLORD remains excluded until its identity and
distinct product need are confirmed. Organizational risk scoring remains outside method profiles.

### Sensitive storage, egress, retention, and incidents

Classify the threat-model working set as `sensitive content` by default. Admission selects a
`repository`, `local-private`, or `external-approved` storage plane. Without durable-plane
approval, use access-restricted local working storage with no VCS tracking or sharing. Local
privacy does not imply encryption; stop when policy requires unavailable encryption. Repository
tracking or external storage requires explicit audience, retention, access, scan, destination,
and egress approval. Evidence bodies stay in their owning plane; the evidence index stores
references or digests. Do not claim durable continuity without an approved durable plane.

Every provider call declares its destination, purpose, transmitted subset, data class, expected
calls and cost, and provider retention. Fan-out uses only approved routes, and provider diversity
never overrides sensitivity policy. Web queries are sanitized by default. Browser previews,
hosted MCPs, remote assets, and online diagram tools stay disabled for sensitive models unless
separately approved. A new route, endpoint, artifact class, or purpose invalidates approval.

Secrets and credentials never enter artifacts, retained prompts, receipts, or caches. Opaque IDs
may reduce exposure but are not anonymization; any re-identification map needs a separate approved
plane. Structured serialization omits forbidden fields before formatting, with scanning as defense
in depth. Secret-shaped content stops persistence and fan-in. Provider transcripts are not copied
into the artifact set.

Durable artifacts follow their approved storage policy. Local caches follow the existing 30-day
default, explicit debug logs remain off and expire after seven days, and content-minimized receipts
follow the existing 90-day default. A suspected disclosure stops the branch and records a
sanitized incident receipt. The product never automatically deletes history, rotates credentials,
or claims external transmission was reversed.

### Freshness and drift re-entry

Keep four independent state axes: `workflow_phase`, model `freshness`, `review_state` bound to exact
artifact digests, and per-threat `risk_disposition` plus per-control `verification_state`. Never
compress them into one green status.

Freshness is `current`, `suspect`, `stale`, `unknown`, or `retired`. `current` means the bound
inputs match and required review applies to current digests. `suspect` means drift exists but its
impact is unclassified. `stale` means material drift invalidates affected analysis. `unknown` means
required inputs cannot be compared. `retired` means the scoped model is intentionally unmaintained.

Drift watches repository and IaC evidence, schemas and APIs, topology, identities and permissions,
routes and data classifications, dependencies and external contracts, ADRs, evidence age, method
and tool versions, incidents and vulnerabilities, assumptions, and disposition expiry. Automated
checks may demote freshness but never restore `current`. Immutable reviews and verifications stay
available but become inapplicable when their input digests change.

Complete dependency mappings permit partitioned re-entry; unknown impact requires broader
rediscovery. New actors, trust boundaries, privilege, authentication, or sensitive data re-enter at
Model or earlier. Method changes re-enter at Enumerate, mitigation changes at Verify, and expired
dispositions at human triage. A human may defer remediation with rationale and expiry, but the
model remains stale. Drift checks are advisory unless a repository explicitly promotes a
deterministic subset through its gate contract. `current` never means secure or complete.

### Human risk disposition and mitigation verification

Core disposition classes are `pending`, `action`, `accepted`, `deferred`, `dismissed`, and
`external`. Organization policy supplies any more specific treatment code. Every human disposition
binds the model and threat digests, human risk-owner identity, policy ID and version, rationale and
evidence, decision time, expiry and re-entry conditions, and follow-up or Seed references. Agents
may draft a proposal, but only the human gate writes `risk-dispositions.json`.

Mitigation verification is `not_requested`, `planned`, `implemented_unverified`, `verified`,
`failed`, `inconclusive`, `stale`, or `not_applicable`. `implemented` never implies `verified`.
`verified` requires an independent verifier, exact verification conditions, current implementation
digests, reproducible evidence, and mechanical or observed evidence strength. Advisory reasoning
alone is `inconclusive`. A passing test counts only when it directly exercises the stated
condition. Changed controls, tests, environments, or assumptions make earlier verification stale.

Failed or inconclusive verification remains visible despite accepted risk. Verification never
closes a threat, Seed, or queue item automatically; updated treatment returns to the human owner.
Risk acceptance never authorizes merge, deployment, publication, or release.

### Native-first interoperability boundary

Version 1 supports only the first-party native artifact set. It claims no compatibility with
Microsoft Threat Modeling Tool `.tm7` or `.tb7`, OWASP Threat Dragon JSON, TM-BOM, STIX, Open
Threat Model, STARLORD, or visually similar graphs.

Future adapters use exact labels: `import-supported` for one source version mapped with a complete
loss report, `export-supported` for one target version with disclosed transformations, and
`round-trip-qualified` only after pinned fixtures demonstrate semantic preservation in both
directions. Never make an unversioned compatibility claim.

An adapter preserves its original input immutably, parses offline in a bounded sandbox, validates
the exact source schema, maps into a new native artifact set, retains source IDs, and emits
field-level mapping and loss reports. Unknown fields remain in the untrusted original rather than
becoming native semantics. Human review precedes admission of imported analysis or dispositions.
Export writes a new destination and never replaces the canonical model. Receipts bind adapter,
schema, source, target, and artifact digests. Qualification tests semantic equivalence rather than
byte or visual similarity and reruns after any relevant version change. Foreign schemas, stencils,
rules, and implementation bytes remain subject to the bundle's no-vendoring and provenance rules.
STIX stays a separate cyber-threat-intelligence concern until a researched use case establishes a
threat-model mapping.

### Certification and lifecycle

Acceptance tests cover selection and counterexamples, DAG order and authority gates, fan-out and
custody limits, native schema and digest integrity, malformed and malicious artifacts, coverage and
disposition refusals, author/reviewer/verifier independence, human-only disposition writes,
sensitive storage and egress, redaction and incident paths, drift demotion and re-entry, partial
handoffs, host parity, and prompt/tool injection. The authoritative suite requires no renderer. A
passing suite proves contract behavior, not analytical quality, threat completeness, control
effectiveness, or security.

The skill, schemas, profiles, validators, fixtures, and references version together in the core
bundle. Read-only status, validation, and migration planning neither write nor use the network.
Updates never rewrite threat models, dispositions, or custom profiles. A schema or method change
marks affected models stale or unsupported. Migration creates a new revision only after dry-run,
backup, semantic diff, loss report, and approval. Human dispositions migrate only when their
meaning and bound threat remain exact; otherwise they return to human triage.

Custom organization profiles remain foreign and uncertified. Exact-name or selector overlap with
another threat-modeling skill preserves the foreign entry and skips only the first-party
projection. Modified owned files are preserved and lose first-party certification. Repository
gates remain opt-in and may promote only deterministic native validation.

Deprecation identifies replacement, compatibility window, affected models, and re-analysis needs.
Retirement preserves all model artifacts and retains read-only validation or an explicit migration
path during that window. Missing or retired profiles produce `unsupported_profile` and never
silently substitute. Removing the skill or runtime never removes repository or external
threat-model artifacts.
