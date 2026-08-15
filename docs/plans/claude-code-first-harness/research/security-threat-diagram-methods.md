# Security threat-diagram methods: STRIDE, DFDs, and the ambiguous STARLORD request

**Research status:** complete — decision-sufficient primary-source review, 2026-08-14

## Question and gated decision

**Question.** Can an optional first-party draw.io skill family safely cover the requested
"STRID", data-flow diagrams, and "STARLORD", perhaps with security-focused agent personas?
What are the exact names, owners, data models, validation opportunities, product boundaries,
and provenance constraints?

**Decision gated.** Whether these capabilities belong as lazy references beneath the generic
draw.io umbrella, as an optional specialized security skill/library, as a security
persona/workflow, or outside the proposed family.

## Evidence labels

- **Verified** — observed in the cited first-party source, original paper/repository, or local
  repository control at the inspected revision.
- **Documented** — asserted by the owner in official documentation, but not reproduced here.
- **Inferred** — a bounded product recommendation derived from verified/documented facts; it is
  not an upstream guarantee.

## Recommendation

**Ship a narrow security-DFD authoring reference under the generic draw.io umbrella; keep STRIDE
analysis in a separately selectable threat-modeling workflow; do not claim STARLORD support.
Do not add permanent security personas in the first stage. Confidence: high (0.92) for the
STRIDE spelling/ownership and product split; high (0.88) for the DFD semantic floor; medium
(0.72) that the 2017 IEEE prototype is the requester's intended STARLORD, because the spelling
matches but the originating reference was not supplied.**

The safe placement is:

| Requested capability | Terminology verdict | Initial product placement | Why |
|---|---|---|---|
| `STRID` | Treat as a likely truncation/typo of **STRIDE**, subject to requester confirmation. No primary security source inspected defines a distinct `STRID` method. | **Specialized security threat-modeling workflow**, with a lazy STRIDE reference inside it; the draw.io umbrella only authors/validates its visual artifact. | STRIDE is threat enumeration and mitigation work, not a canvas notation. Microsoft requires diagram, threat identification, mitigation, and mitigation validation, and warns STRIDE is not a substitute for attacker thinking. |
| Security DFD | **Data-flow diagram (DFD)** specialized for threat modeling; five semantic element classes are useful: process, data store, external entity/actor, directed data flow, and trust boundary/zone change. | **Lazy reference beneath the generic draw.io umbrella**, invoked by the security workflow. | It shares draw.io XML/security/render machinery with every other editable diagram, but adds a compact typed graph and validator profile. |
| `STARLORD` | One exact primary-source candidate exists: **“STARLORD: Linked Security Data Exploration in a 3D Graph”** (Leichtnam, Totel, Prigent, Mé; IEEE VizSec 2017). The paper does not expand the name as an acronym. It is an interactive cyber-event exploration prototype, not STRIDE, not a DFD method, and not a threat-modeling standard. Whether this is what the requester meant remains unresolved. | **No product surface now.** If the paper is confirmed, treat it as a separate cyber-analytics research/prototype workflow, not a draw.io reference and not an agent persona. | Its load-bearing behavior is ingestion, graph normalization, clustering, 3D force-directed visualization, interactive inspection, and human interpretation. A static editable canvas can preserve a snapshot but cannot honestly claim STARLORD behavior. |
| Security-focused runtime agents | Distinct from threat actors or “threat personas” represented in a threat model. | **Task-specific workflow roles using the existing cartographer/researcher/critic/reviewer surfaces first.** Consider a persistent security role only after recurrence and a stable artifact contract are demonstrated. | The security decision needs independent challenge and human risk ownership; a persona does not create semantic validity and must not approve its own model. |

## Concise staged recommendation

1. **Stage 0 — normalize names and claims.** Spell the Microsoft method `STRIDE`; record
   `STRID` as unresolved user wording, not a new method. Ask for the originating STARLORD link
   before doing any STARLORD-specific design. Do not expand STARLORD into invented words.
2. **Stage 1 — add only a lazy security-DFD profile to the draw.io umbrella.** Use simple native
   geometry plus explicit machine metadata, not copied Microsoft/OWASP/custom-library bytes.
   Validate the typed graph and its binding to an editable, uncompressed `.drawio` file. This
   stage may claim “editable security-focused DFD” and “repository-schema validated,” not
   “threat model complete.”
3. **Stage 2 — introduce an optional `threat-modeling` workflow only when this repository's
   top-level-skill admission gate is satisfied.** The workflow owns scoping, asset/use-case
   discovery, DFD construction, STRIDE coverage, threat/mitigation ledger, independent review,
   and human acceptance. The draw.io skill remains an artifact backend. Start with task-specific
   role prompts, not new permanent personas.
4. **Stage 3 — qualify interoperability separately.** Only after fixtures and round-trip tests
   may the product claim compatibility with Microsoft Threat Modeling Tool, OWASP Threat Dragon,
   TM-BOM, or any other format. A visual resemblance is not interchange compatibility.
5. **Stage 4 — handle STARLORD only after identity confirmation.** If the 2017 paper is intended,
   keep it on a separate experimental cyber-analytics track. A 2D draw.io export may be an
   advisory snapshot of a selected graph, but the product must not call that a STARLORD
   implementation.

## 1. Local product constraints

1. **Verified — the generic draw.io decision already prefers one umbrella with lazy references.**
   Canonical authoring is bounded, uncompressed `.drawio` XML; generic validation combines safe
   parsing, pinned XSD, semantic/security checks, and visual review. Per-type siblings require a
   distinct selection trigger, workflow, machine-checkable specialization, recurrence/handoff
   evidence, and provenance ownership
   ([local draw.io research](drawio-agent-diagram-workflows.md)).
2. **Verified — a new top-level skill is deliberately expensive.** This repository requires a
   distinct description-level selector, proportional selection cost, a live trigger, and
   task-shaped behavior. Promotion from a lazy reference requires at least two of recurrence,
   specific sequencing, repeated buried failures, stable input/output contract, or explicit
   handoff benefit
   ([skill-authoring policy](../../../skills/agentic-sdlc/references/skill-authoring.md)).
3. **Verified — foreign bytes are not vendored.** External ideas may be adapted with the
   repository's donor/NOTICE process, but another project's skill, stencil, template, schema, or
   rule corpus is not copied into this bundle merely because its license permits reuse
   ([skill-authoring policy](../../../skills/agentic-sdlc/references/skill-authoring.md),
   [repository instructions](../../../AGENTS.md)).
4. **Inferred — security analysis clears the “different workflow” threshold; security DFD
   drawing alone does not.** A DFD uses the same draw.io file, geometry, source-security, preview,
   and export boundary as other diagrams. STRIDE adds discovery, attacker reasoning, a threat
   ledger, mitigation ownership, validation evidence, and an independent review handoff. That is
   the separation line between the umbrella reference and the optional security workflow.

## 2. `STRID` versus Microsoft STRIDE

### Terminology and ownership

1. **Documented — the established security mnemonic is six-letter `STRIDE`.** Microsoft defines
   it as Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, and
   Elevation of Privilege. Microsoft describes STRIDE as a common methodology for enumerating
   potential threats and applies it to data-flow-diagram elements
   ([Microsoft Secure by Design](https://www.microsoft.com/en-us/securityengineering/sdl/practices/secure-by-design),
   [Microsoft SDL field guidance](https://www.microsoft.com/en-us/security/blog/2012/08/16/threat-modeling-from-the-front-lines/)).
2. **Verified within the bounded primary-source search — `STRID` is not established as a
   distinct security method.** The inspected Microsoft SDL pages, current training, Microsoft
   Threat Modeling Tool guidance, official OWASP Threat Dragon documentation, and original
   STARLORD paper all use `STRIDE`. Search results containing `STRID` in a security context were
   truncations, line-break artifacts, or misspellings of a six-category discussion, not an owning
   specification. **Inferred:** normalize the user input to `STRIDE?` in discovery and require
   confirmation before persisting it; do not create a `strid` skill, method ID, or compatibility
   claim.
3. **Documented — STRIDE is a component of Microsoft SDL threat modeling, not the entire
   lifecycle.** Microsoft lists five major steps: define security requirements, create an
   application diagram, identify threats, mitigate threats, and validate that mitigations were
   effective. The official tool uses a notation for components, data flows, and security
   boundaries, and manages suggested threats and mitigations
   ([Microsoft SDL threat modeling](https://www.microsoft.com/en-us/securityengineering/sdl/threatmodeling)).
4. **Documented — STRIDE is not a risk-prioritization model.** Microsoft's current training says
   threat modeling provides threats and potential controls but does not prioritize the issues
   ([Microsoft prioritization module](https://learn.microsoft.com/en-us/training/modules/tm-prioritize-your-issues-and-apply-security-controls/)).
   **Inferred:** keep severity, likelihood, business impact, and risk acceptance in a separately
   named organization-owned policy; never manufacture scores from a STRIDE letter.

### What STRIDE requires from the product

The smallest honest STRIDE output is not a page with six colored badges. It is a traceable
analysis record:

- a defined system/version, scope, use cases, assets, assumptions, and responsible owner;
- a DFD whose elements and interactions have stable semantic IDs;
- an explicit consideration/disposition for relevant STRIDE categories on each in-scope element
  or interaction;
- concrete threat scenarios, affected assets/elements, and evidence/rationale;
- mitigation/control, treatment status, accountable owner, and verification evidence; and
- an independent challenge pass plus unresolved/open items.

That product shape follows Microsoft's complete lifecycle and current guidance to involve varied
backgrounds, including developers/testers, product owners, security engineers, and people skilled
at violating assumptions and testing boundaries
([Microsoft Secure by Design](https://www.microsoft.com/en-us/securityengineering/sdl/practices/secure-by-design)).

### Important limitation

**Documented — STRIDE is a prompt for analysis, not a completeness proof.** Microsoft explicitly
warns that it is not a substitute for thinking like an attacker and may miss design flaws that
only adversarial reasoning will reveal
([Microsoft Secure by Design](https://www.microsoft.com/en-us/securityengineering/sdl/practices/secure-by-design)).
The older Microsoft field guidance demonstrates per-element category mappings—for example,
processes receive all six categories and data flows are considered for tampering, information
disclosure, and denial of service—but the current guidance phrases the task as considering
diagram elements and asking which categories apply
([Microsoft field guidance](https://www.microsoft.com/en-us/security/blog/2012/08/16/threat-modeling-from-the-front-lines/)).

**Inferred:** a validator may enforce that every in-scope element/category pair has an explicit
disposition, but it must not assert that the category is applicable or that the recorded threats
are complete. Rule-pack version and provenance must be visible if the product later automates a
per-element matrix.

## 3. Security data-flow diagrams

### Exact model needed

Microsoft's current threat-modeling training defines five useful semantic element classes:

| Element | Required meaning | Minimum useful context | Primary source |
|---|---|---|---|
| Process | A task that receives, modifies, or redirects input to output. | Runtime/technology, privilege, isolation, accepted inputs, validation, authentication, authorization. | [Microsoft process element](https://learn.microsoft.com/en-us/training/modules/tm-create-a-threat-model-using-foundational-data-flow-diagram-elements/2-process-the-task-element) |
| Data store | Temporary or permanent stored data. | Store type/function, read/write principals, encryption/signing and other controls. | [Microsoft data-store element](https://learn.microsoft.com/en-us/training/modules/tm-create-a-threat-model-using-foundational-data-flow-diagram-elements/3-data-store-the-storage-element) |
| External entity / actor | A human, service, process, data store, or system outside the modeled team's direct control. | Internal/external source, actor type, authentication, authorization, control owner. | [Microsoft external-entity element](https://learn.microsoft.com/en-us/training/modules/tm-create-a-threat-model-using-foundational-data-flow-diagram-elements/4-external-entity-the-no-control-element) |
| Data flow | Directed movement of data between elements. | Data description/type, source, destination, protocol, sequence, authentication/authorization and transport controls; normally model responses too. | [Microsoft data-flow element](https://learn.microsoft.com/en-us/training/modules/tm-create-a-threat-model-using-foundational-data-flow-diagram-elements/5-data-flow-the-data-in-transit-element) |
| Trust boundary / trust-zone change | A line or region where the trust level changes as data crosses. | Zone/boundary description and which flows cross it. | [Microsoft trust-boundary element](https://learn.microsoft.com/en-us/training/modules/tm-create-a-threat-model-using-foundational-data-flow-diagram-elements/6-trust-boundary-the-trust-zone-change-element) |

The official draw.io documentation independently confirms that its DFD surface provides entity,
process, data-store, and data-flow shapes, and that its separate threat-modeling library exists
([draw.io DFD documentation](https://www.drawio.com/docs/diagram-types/data-flow-diagrams/),
[draw.io threat-modeling documentation](https://www.drawio.com/docs/diagram-types/threat-modelling/)).
This proves canvas feasibility, not method conformance.

### Machine-checkable semantics

**Inferred — use a two-artifact contract bound by stable IDs, rather than treating colors and
shape names as the model.** The editable `.drawio` file owns geometry, layout, labels, layers,
and the typed system graph. A companion threat ledger owns threats, dispositions, controls,
owners, and verification evidence. Each artifact records the other's digest; both use the same
stable semantic IDs. The validator should fail closed on drift between them.

At minimum, deterministic checks can enforce:

1. **Generic draw.io admission:** bounded uncompressed XML, safe parser, pinned XSD, stable unique
   cell IDs, allowed external-content policy, and the generic source checks already specified by
   the umbrella research.
2. **Typed graph:** every semantic cell has one allowed type; flows have existing typed endpoints
   and explicit direction; trust zones have IDs; every graph element has an explicit scope state.
   Geometry/style alone never assigns type.
3. **Context presence:** required fields by element type; protocol/data classification and
   transport controls on flows; privilege/input/authentication context on processes; storage and
   access-control context on stores; direct-control owner on external entities; descriptions on
   zones/boundaries.
4. **Boundary consistency:** zone membership is explicit; a flow whose endpoints occupy different
   trust zones is marked as a crossing; the visual boundary and semantic zone relationship agree.
   Ambiguous overlapping visual regions fail or require an explicit waiver.
5. **STRIDE coverage:** every in-scope element or interaction has a six-category coverage record
   whose state is `applicable`, `not_applicable`, or `deferred`, with rationale and linked threat
   IDs where applicable. The validator checks coverage, not analytical truth.
6. **Threat ledger integrity:** unique threat/control IDs; existing affected-element references;
   category enum; scenario and impact text; treatment state; owner; timestamps; and no orphaned
   threats or mitigations. A `mitigated` state requires linked control and verification evidence;
   accepted residual risk requires an identified human/organizational owner, never an agent's
   self-approval.
7. **Provenance and drift:** repository/commit or source snapshot, modeled scope/depth, evidence
   inputs, schema/rule-pack versions, creation/review timestamps, and a stale-model signal when
   the bound architecture evidence changes.
8. **Visual advisory checks:** distinguish element types without color alone; labels legible;
   flow direction visible; boundary crossings unambiguous; no clipped/overlapped security labels.
   These remain advisory unless a pinned renderer is separately certified.

OWASP Threat Dragon is first-party implementation evidence that this separation is practical: it
stores diagrams and threat records, supports STRIDE and other categorizations, and uses typed
process/data-store/actor/data-flow/trust-boundary elements
([OWASP Threat Dragon project](https://owasp.org/www-project-threat-dragon/),
[diagram semantics](https://owasp.org/www-project-threat-dragon/docs-2/diagrams/),
[threat records](https://owasp.org/www-project-threat-dragon/docs-2/threats/)). It is not a
drop-in canonical schema: OWASP documents that Threat Dragon v1 and v2 JSON are incompatible,
both are coupled to their graph engines, the loader warns but does not refuse schema-invalid
models, and a new v3 model is planned
([OWASP Threat Dragon schema notes](https://owasp.org/www-project-threat-dragon/docs-2/schema/),
[format roadmap](https://owasp.org/www-project-threat-dragon/)).

**Inferred:** write a small first-party schema and validator for the promised subset rather than
copying Threat Dragon's unstable graph-editor format or claiming import/export compatibility.
Track OWASP's emerging TM-BOM work as a future interoperability candidate only; the official
Threat Dragon page itself describes it as a proof of concept/future direction, not a stable
current interchange guarantee.

## 4. The exact primary-source STARLORD candidate

### Identity and ownership

**Verified — the exact title is “STARLORD: Linked Security Data Exploration in a 3D Graph.”** It
is a four-page short paper by Laetitia Leichtnam, Eric Totel, Nicolas Prigent, and Ludovic Mé,
presented at the 2017 IEEE Symposium on Visualization for Cyber Security, DOI
`10.1109/VIZSEC.2017.8062203`
([author-deposited paper and metadata](https://inria.hal.science/hal-01619234v1),
[official VizSec 2017 program](https://vizsec.org/vizsec2017/)). The paper uses STARLORD as a
proper name and does not define an acronym expansion.

**Unresolved:** no originating link or context was supplied with the request, so the spelling
match does not prove this paper is what the requester meant. No inspected primary source defines
a formal “STARLORD (STAR)” threat-modeling method. Ask for the source before turning this
candidate into product requirements.

### What the paper actually specifies

The original paper describes this pipeline:

1. **Input sources:** static internal infrastructure description; dynamic internal telemetry such
   as IDS, firewall, system/application logs and network captures; and external intelligence such
   as IOCs, CVEs, incident reports, malware databases, IDS rules, and vendor reports.
2. **Graph model:** a model “inspired by STIX,” using STIX-like `Observed Data`, `Indicator`, and
   `Campaign` objects plus observable types such as domain, file, IP address, DNS query, network
   connection, socket address, hostname, and port. The experiment parses Bro IDS logs and OTX
   indicators.
3. **Normalization:** merge duplicate objects and retarget incoming/outgoing relations to the
   retained object.
4. **Selection:** treat all relations as equal/unweighted; apply Louvain community detection;
   select clusters containing an IOC or NIDS alert; then restore direct links between selected
   clusters from the original graph.
5. **Visualization:** persist objects/relationships in a graph database; use a Unity prototype
   with a 3D force-directed layout, color-coded node types, zoom/movement, click-for-details, and
   manual creation of nodes/links for “what if” exploration.
6. **Human analysis:** the analyst follows paths and verifies exact semantics against logs. The
   authors explicitly acknowledge that links have varied semantics and free interpretation can be
   hazardous.
7. **Evidence:** two WannaCry packet-capture case studies. The authors identify disjoint-cluster
   information loss and scalability beyond the tested Bro/IOC inputs as future work.

All seven points are **verified** from the
[author-deposited paper](https://inria.hal.science/hal-01619234/document).

### Why this is not a draw.io method

**Inferred — the essential STARLORD unit is an interactive analysis system, not a diagram
notation.** A draw.io file can depict a small STIX-like graph or preserve a 2D snapshot of selected
clusters. It does not provide heterogeneous log ingestion, object normalization, Louvain
clustering, graph-database queries, 3D occlusion/navigation, interactive detail retrieval, or
analyst verification against raw events. Calling a static graph “STARLORD-compatible” would
collapse nearly every load-bearing part of the paper into a visual resemblance.

The current OASIS standard further cautions against treating “STIX-inspired” as current STIX
conformance: STIX 2.1 is a governed machine-readable CTI language whose nodes, edges, object
types, JSON serialization, normative requirements, and IPR posture are specified by the OASIS CTI
Technical Committee
([OASIS STIX 2.1 standard](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html),
[OASIS ownership FAQ](https://oasis-open.github.io/cti-documentation/faq.html)). The 2017 paper's
small experimental model must not be relabeled “STIX 2.1” without an explicit mapping and
conformance tests.

## 5. Skill, library, and persona boundary

### Lazy draw.io reference: yes, but only for the visual grammar

The generic draw.io umbrella can own a focused `security-dfd` reference that provides:

- selection versus generic architecture diagrams and versus Mermaid;
- the five typed DFD elements and required metadata;
- safe native shapes and layout conventions;
- draw.io XML-to-semantic-ID binding;
- structural/context/boundary validation rules; and
- a handoff contract to a security analysis workflow.

It must stop before asserting threat completeness, risk, mitigation effectiveness, or review
approval. The official draw.io threat-modeling library proves an editor surface exists, but its
documentation says the library was contributed by Michael Henrikson with permission to include it
in draw.io
([draw.io threat-modeling documentation](https://www.drawio.com/docs/diagram-types/threat-modelling/)).
That is not evidence that this repository may extract and redistribute the library. Use simple
first-party geometric shapes or renderer-built-in identifiers after version/provenance checks;
do not vendor the library bytes.

### Specialized security skill/workflow: conditionally yes

The separately selectable unit should be named descriptively, such as `threat-modeling`, not
`stride-diagrams` and not `starlord`. Its selection sentence should fire on a request to identify
design threats, assess trust boundaries, or produce a reviewed threat/mitigation ledger. It should
reject a request that only needs an editable system diagram, which belongs to draw.io.

The workflow's stable contract can be:

- **Inputs:** system scope/version, use cases, assets, architecture/code/IaC evidence, known
  controls, risk owner, requested methodology/profile.
- **Outputs:** editable security DFD; machine-readable threat/mitigation ledger; coverage and
  provenance receipt; open assumptions/unknowns; independent advisory review; human decisions
  still required.
- **Sequence:** scope and evidence -> typed DFD -> STRIDE coverage -> adversarial/abuse-case pass
  -> mitigations and verification plan -> independent review -> human triage/acceptance.

This clears “different workflow” and likely “specific sequencing” plus “stable I/O contract,” but
the local admission policy still requires a live trigger and proportional recurrence before a new
top-level row is shipped. Until those are evidenced, keep it as a planned optional companion or a
lazy reference under the flagship workflow, not an always-visible skill.

### Permanent security personas: defer

Microsoft's guidance supports multiple perspectives and separate review, not one omnipotent
security author: developers/testers, product owners, security analysts/engineers, and
boundary-condition/adversarial testers are all invited, and Microsoft's walkthrough uses a
separate threat review/sign-off meeting
([Microsoft Secure by Design](https://www.microsoft.com/en-us/securityengineering/sdl/practices/secure-by-design),
[Threat Modeling Tool walkthrough](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-getting-started)).

**Inferred:** initially route these responsibilities through existing roles:

- cartographer/researcher: read-only system evidence and scope inventory;
- task-specific threat-model author: bounded write ownership of diagram/ledger only;
- critic/security reviewer: read-only independent assumptions, coverage, and failure-mode audit;
- human product/security owner: priority, residual-risk acceptance, and external effects.

Promote a persistent `security-threat-modeler` or `security-reviewer` persona only when it owns a
distinct recurrent graph responsibility, least-privilege tool boundary, stable artifact contract,
tests, and collision/retirement policy. It must never review or accept its own output. Do not
confuse a runtime agent persona with an attacker/threat persona represented *inside* a threat
model.

STARLORD, if confirmed, would need a cyber-analytics workflow with data-ingestion and interactive
graph tools plus a human analyst; naming a “STARLORD persona” would not supply those capabilities.

## 6. Licensing, trademark, and provenance

1. **draw.io assets are not covered by one blanket permission.** draw.io source is Apache-2.0,
   while its README gives icon sets, templates, and third-party marks separate terms
   ([draw.io README at inspected commit](https://github.com/jgraph/drawio/blob/a1f615b7f5a5237da71de2ce2f057b5fa70b0aeb/README.md)).
   The threat-model library's inclusion permission belongs to draw.io; do not assume it transfers.
2. **Microsoft templates are code/assets under their own terms.** The official
   `microsoft/threat-modeling-templates` repository is MIT-licensed
   ([repository at inspected commit](https://github.com/microsoft/threat-modeling-templates/tree/0ece9c71b6f3710b10d497bd1ef63e57805e7c3e),
   [license](https://github.com/microsoft/threat-modeling-templates/blob/0ece9c71b6f3710b10d497bd1ef63e57805e7c3e/LICENSE)).
   That makes reuse legally inspectable; it does not override this bundle's no-vendoring and
   donor/NOTICE policy, prove draw.io compatibility, or authorize claims of Microsoft endorsement.
3. **OWASP Threat Dragon is Apache-2.0, but adaptation is still provenance-bearing.** Its current
   official repository is Apache-2.0
   ([OWASP repository at inspected commit](https://github.com/OWASP/threat-dragon/tree/ea24a62a605c307741b516c3ee87b7438fe80475),
   [project README](https://github.com/OWASP/threat-dragon/blob/ea24a62a605c307741b516c3ee87b7438fe80475/README.md)).
   Do not copy its schema, rules, text, icons, or examples into this bundle without an explicit
   adaptation/provenance/NOTICE decision and compatibility tests.
4. **The STARLORD paper is not a software distribution license.** The HAL record provides an
   author-deposited paper under HAL's archival authorization, and the paper names a Unity
   prototype, but no inspected first-party source supplies a source repository, versioned data
   schema, code license, or redistributable visual asset pack. The paper is citable evidence, not
   vendorable implementation material
   ([HAL record](https://inria.hal.science/hal-01619234v1)).
5. **STIX has a current standards owner and trademark/IPR policy.** If a future workflow produces
   or consumes STIX, pin the exact OASIS version, validate the mandatory JSON model against the
   normative specification, follow the OASIS IPR/trademark guidance, and say “STIX-inspired” only
   when conformance is not established
   ([STIX 2.1](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html)).
6. **STARLORD is a poor first-party product name even apart from the paper.** Marvel officially
   uses “Star-Lord” for Peter Quill
   ([Marvel character page](https://www.marvel.com/characters/star-lord-peter-quill)).
   This report does not make a legal trademark determination, but the obvious naming collision is
   enough to require legal review and to prefer a descriptive project-owned name. Cite the paper
   by its exact title; do not brand a shipped skill `starlord`.

## 7. Safe claims and explicit exclusions

### Safe after Stage 1 validation exists

- “Authors editable draw.io security data-flow diagrams.”
- “Represents processes, data stores, external entities, directed data flows, and trust-zone
  changes with stable semantic IDs.”
- “Checks repository-defined structure, references, required context, trust-zone crossings, and
  diagram/ledger binding.”
- “Can record STRIDE categories and analysis dispositions” — only if the companion threat ledger
  exists and the workflow was actually run.
- “STRIDE-informed” or “uses Microsoft's STRIDE categories,” with attribution and methodology
  version/provenance.

### Unsafe without separate qualification

- `STRID` as a distinct supported method.
- “Microsoft Threat Modeling Tool compatible,” “OWASP Threat Dragon compatible,” or “TM-BOM
  compatible.”
- “STRIDE-complete,” “all threats found,” “secure,” “certified,” “compliant,” or “validated threat
  model” when only XML/schema/coverage checks passed.
- automatic risk prioritization or severity derived from STRIDE.
- proof that a mitigation is effective merely because it is present or marked mitigated.
- “STARLORD implementation,” “STARLORD-compatible,” or “STIX-compliant” for a 2D graph snapshot.
- security approval, residual-risk acceptance, deployment authority, or another outward effect
  based on an agent persona, validator, or review verdict.

Security diagrams often expose sensitive system topology, assets, trust boundaries, protocols,
and controls. draw.io itself recommends its fully offline Desktop app for threat-model diagrams
([draw.io threat-modeling documentation](https://www.drawio.com/docs/diagram-types/threat-modelling/)).
This reinforces the generic draw.io report's rule that browser preview/hosted processing is an
explicit egress decision, not a default.

## 8. Adversarial pass: limitations and failure modes

1. **Checklist illusion:** six populated STRIDE rows can create false assurance while missing
   abuse cases, compromised dependencies, invalid trust assumptions, cross-feature interactions,
   and domain-specific threats. Countermeasure: mandatory adversarial pass and explicit unknowns;
   never convert coverage into completeness.
2. **Diagram-is-truth illusion:** an internally consistent DFD can be incomplete or stale relative
   to code, IaC, runtime routing, identity policy, and operations. Countermeasure: bind provenance
   to exact evidence/commit and surface drift; require a walkthrough with system owners.
3. **Shape-semantic drift:** users can restyle or replace draw.io shapes while retaining misleading
   colors/icons. Countermeasure: stable explicit type metadata and IDs; style is presentation only.
4. **Boundary geometry ambiguity:** a visual line crossing can differ from actual zone membership.
   Countermeasure: zones and crossing relations are semantic records; the visual must agree.
5. **Auto-generated false positives/negatives:** per-element rules suggest categories but cannot
   judge architecture-specific applicability. Countermeasure: every generated item remains a
   proposal with rationale and reviewer disposition; no silent auto-mitigation.
6. **Risk laundering:** an agent can invent severity or accept residual risk. Countermeasure:
   organization-owned scoring policy and named human risk owner; STRIDE never supplies priority.
7. **Interchange fragility:** visual similarity to Microsoft/OWASP shapes does not make `.drawio`
   files compatible with `.tm7`, `.tb7`, Threat Dragon JSON, or future TM-BOM. Countermeasure:
   claim only repository-native schema until pinned fixture round trips pass.
8. **Sensitive-data egress:** online previews, remote shape libraries, external images/fonts, or
   hosted MCP calls may disclose the architecture. Countermeasure: offline-first source handling,
   no remote assets by default, explicit egress approval, and content redaction profiles.
9. **STARLORD category error:** a 2D network graph can look like the paper while omitting its data
   pipeline and interactive analysis. Countermeasure: prohibit the name from the draw.io support
   matrix; allow only “static graph snapshot” wording.
10. **3D is not automatically clearer:** the STARLORD authors moved from 2D because of crossing
    edges but explicitly acknowledged 3D occlusion; selected-cluster loss and scalability remained
    open. Countermeasure: do not infer a general 3D advantage or production readiness from two
    case studies.

## 9. Rejected alternatives

1. **One top-level `stride-diagrams` skill — rejected.** It mixes a security workflow with an
   artifact backend, makes selection ambiguous, and encourages visual completion to stand in for
   threat analysis.
2. **One top-level DFD skill — rejected initially.** DFD grammar and source handling fit as a lazy
   draw.io reference; Mermaid remains preferable when editable free-form canvas geometry is not
   load-bearing.
3. **A monolithic “advanced security diagrams” catalog — rejected.** DFDs, attack trees, STRIDE,
   cyber-event visual analytics, and standards such as STIX have different owners, inputs,
   semantics, validators, and analyst workflows. A visual theme is not a coherent capability.
4. **Vendor Microsoft's/OWASP's stencils, schemas, and rules — rejected.** Licenses are knowable,
   but this repository's no-vendoring policy, donor obligations, version drift, and unproven
   interchange value make first-party minimal semantics the safer starting point.
5. **Use Threat Dragon JSON as the native schema — rejected.** OWASP documents current version
   incompatibility, graph-engine coupling, warning-only schema admission, and planned redesign.
6. **Call a draw.io graph STARLORD — rejected.** It would be a snapshot of one output, not the
   original system's ingestion/clustering/interactive-analysis method.
7. **Create “security architect” and “STARLORD analyst” permanent personas now — rejected.** The
   first is too broad and collision-prone; the second confuses a tool pipeline with a role. Use
   bounded task roles and independent review until recurrent contracts are observed.

## 10. Open risks, unresolved ambiguity, and cheapest decisive experiments

### Unresolved ambiguity

- **What did the requester mean by `STARLORD`?** The 2017 IEEE paper is the only exact
  primary-source security visualization candidate found. Confirmation requires the originating
  link, author, screenshot, or acronym expansion. Until then, the correct product state is
  `unresolved`, not `supported` or `rejected-as-user-intent`.
- **Was `STRID` deliberate?** Primary security sources support STRIDE. Ask once; default display
  can say “STRIDE (assuming `STRID` was a truncation).”
- **Which risk policy applies?** STRIDE does not answer prioritization. The product cannot design a
  severity/acceptance model without an organization-owned policy choice.
- **Which semantic artifact is canonical in the planned draw.io family?** This report recommends
  bound `.drawio` graph plus threat ledger, but the family specification must settle edit
  ownership, atomic updates, and conflict recovery before implementation.

### Cheapest decisive experiments

1. **Nomenclature canary (cheapest and first):** ask the requester for the STARLORD source and
   whether `STRID` means STRIDE. One answer prevents an entire mis-scoped product branch.
2. **Security-DFD semantic fixture:** author one small `.drawio` model with all five element types,
   two trust zones, one crossing, and a six-category ledger. Deliberately inject dangling flows,
   duplicate IDs, a visual/semantic zone mismatch, missing dispositions, and a false mitigated
   state. The decision is positive only if deterministic checks reject every bad fixture while
   preserving editability. This decides the lazy-reference contract; it does not test threat
   completeness.
3. **Workflow role canary:** run the same bounded system through an author and an independent
   adversarial reviewer. Promote persistent security personas only if the handoff finds material
   omissions that generic critic/reviewer prompts repeatedly miss and the artifact contract
   recurs.
4. **STARLORD track only if confirmed:** do not start by recreating the 2017 Unity prototype.
   First test whether the actual user need is (a) a static selected-cluster snapshot, (b) an
   interactive 2D graph, or (c) the paper's full ingestion/clustering/3D workflow. Those are three
   different products. A draw.io snapshot can answer only (a).

## 11. Out-of-scope discoveries for conductor filing

The assignment forbids Seeds edits, so these are **seed-shaped proposals for the conductor to
file**, not investigated work:

1. **CLASSIFIED / research — Threat-model interchange decision.** Compare a minimal first-party
   ledger with current Microsoft `.tm7/.tb7`, OWASP Threat Dragon v2 JSON, Open Threat Model, and
   the emerging TM-BOM schema. Gate: choose no interoperability claim until pinned round-trip and
   loss accounting fixtures exist.
2. **CLASSIFIED / security — Sensitive diagram handling profile.** Define redaction, local-only
   storage, external-resource denial, egress approval, retention, and derived-render policy for
   security diagrams whose topology is itself sensitive.
3. **CLASSIFIED / product — Security role promotion evidence.** Measure whether task-specific
   author/adversarial-review roles recur and outperform existing reviewer/critic lenses before
   adding a permanent persona row.
4. **CLASSIFIED / research — STARLORD identity follow-up.** Close immediately if the requester
   provides no source or meant the 2017 paper only as inspiration. If confirmed, frame a separate
   cyber-analytics prototype decision rather than extending draw.io scope.

## Primary sources inspected

- Microsoft Security Development Lifecycle threat-modeling and Secure by Design documentation.
- Microsoft Threat Modeling Tool guidance and current Microsoft Learn threat-modeling training.
- Official draw.io DFD and threat-modeling documentation, plus the draw.io repository licensing
  notice at a pinned revision.
- OWASP Threat Dragon project, diagrams, threat, schema, and file-format documentation at the
  current inspected revision `ea24a62a605c307741b516c3ee87b7438fe80475`.
- Leichtnam, Totel, Prigent, and Mé, “STARLORD: Linked Security Data Exploration in a 3D Graph,”
  author-deposited HAL version `hal-01619234v1`, and the official VizSec 2017 program.
- OASIS STIX 2.1 standard and CTI Technical Committee ownership documentation.
- Microsoft threat-modeling template repository at inspected revision
  `0ece9c71b6f3710b10d497bd1ef63e57805e7c3e`.

**Stop condition reached.** Two more sources would not change the recommendation. The only
load-bearing unknown remaining is user intent behind `STARLORD`, and that requires the originating
reference rather than additional open-ended searching.
