# Define the draw.io diagram skill family

Type: grilling
Status: resolved
Blocked by: 10, 23
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Should Agentic SDLC add an optional first-party draw.io diagram profile alongside Mermaid, and if
so what earns an umbrella skill versus individual diagram-type skills? The umbrella authoring
skill and safe source tooling ship in the core distribution; preview/render/export runtimes remain
separately provisioned. Define selection and
counterexamples, supported diagram types, editable source and rendered artifacts, layout and icon
libraries, validation and sandbox boundaries, provenance, user approval, cross-platform support,
maintenance and retirement, and when a free-form draw.io artifact is preferable to Mermaid or
plain prose without bloating the skill-selection surface.

## Research input

- [Security threat-diagram methods: STRIDE, DFDs, and the ambiguous STARLORD
  request](../research/security-threat-diagram-methods.md)

## Answer

### Activation boundary

Select the draw.io umbrella only when an editable canvas capability is load-bearing. Qualifying
needs include precise spatial layout, domain stencils, layers or multiple pages, free-form
composition, human visual editing, or geometry that Mermaid cannot express clearly.

Use Mermaid when concise text can remain the maintainable source of truth. Use prose or a table
when a visual adds little value. A generic request for a diagram does not select draw.io by itself.
Honor an explicit user format choice when that format is valid for the requested artifact.

The current repository exposes Mermaid as a nested authoring reference rather than a top-level
skill. Repository-truth reconciliation must give the planned Mermaid and draw.io surfaces
consistent packaging and selection semantics.

### Supported families

The umbrella ships lazy authoring references for software architecture and deployment, processes
and workflows, data and domain relationships, network and infrastructure topology, concept and
stakeholder maps, and low-fidelity interfaces or system wireframes. These references are not
separately selectable skills. They share the umbrella's source, validation, security, and
provenance contract.

The initial surface does not claim formal UML, BPMN, electrical, engineering, safety, or regulatory
conformance. A notation-inspired visual is not a standards-conformant model. Formal notation
support requires specialized semantic validation and an accountable maintainer. Sequence, state,
class, and entity-relationship diagrams normally remain Mermaid unless the canvas-diagram selector
applies.

### Security artifact and workflow split

The draw.io umbrella owns a lazy `security-dfd` reference. It authors typed processes, data stores,
external actors, directed flows, trust zones, stable semantic IDs, and structural validation. It
does not decide threat completeness, mitigation effectiveness, priority, or residual risk.

A separately selectable `threat-modeling` workflow owns system scoping, STRIDE coverage, abuse-case
analysis, the threat-and-mitigation ledger, provenance, and independent challenge. Draw.io and
Mermaid are artifact backends selected by the diagram contract; neither owns the security verdict.
Task-specific evidence, author, adversarial-review, and mitigation-verification roles come first.
The persona-roster decision may promote a permanent security persona only after recurrence and a
stable independent contract are proven. A named human owns priority and residual-risk acceptance.

Treat `STRID` as unresolved wording that likely means Microsoft STRIDE; do not mint a `STRID`
method or skill. The only verified STARLORD candidate is a 2017 interactive cyber-event exploration
prototype, not a threat-modeling notation. Make no STARLORD support claim without the originating
reference; if that paper is intended, evaluate it as a separate cyber-analytics capability.

### Artifact authority

Bounded, normalized, uncompressed `.drawio` XML is the canonical source for every canvas diagram.
PNG, SVG, and PDF are derived artifacts even when they embed editable metadata. Each derived
artifact has a receipt that binds it to the source digest, renderer identity, platform, fonts,
libraries, options, and creation time.

Generic diagrams need no semantic sidecar unless their method has facts that visual geometry
cannot safely own. A security DFD binds its `.drawio` typed graph to a machine-readable threat
ledger through stable IDs and mutual digests. The diagram owns typed topology and layout. The
ledger owns threats, dispositions, controls, human owners, and verification evidence. Shared
semantic changes update both in one reviewed change. Digest or reference drift fails validation
and requires explicit reconciliation; human visual edits never trigger a silent ledger rewrite.

A source, sidecar, receipt, or render can establish internal consistency and provenance. None
establishes factual correctness, review approval, threat completeness, or security.

### Source admission and compatibility

`strict-authoring` governs new and Agentic SDLC-owned diagrams. It requires bounded UTF-8,
uncompressed XML, a safe parser, the complete draw.io wrapper, unique and valid graph references,
approved shapes and styles, plain labels, and no remote resources. Validation invokes no renderer,
browser, network, or external library fetch.

`preservation-inspection` governs existing and imported diagrams. It parses and classifies without
rewriting, deleting, normalizing, or silently repairing unsupported content. Bounded compressed
input is read-only compatibility. Conversion to canonical uncompressed source requires explicit
approval. Unknown libraries, HTML labels, embedded files, external references, unsupported
metadata, or ambiguous graph relationships keep the artifact read-only until resolved.

The validator reports parse safety, structural validity, semantic-profile validity,
external-content policy, and visual-review state separately. XSD success alone is insufficient;
semantic IDs, references, containment, styles, libraries, sidecar binding, and external content
need deterministic checks. Meaningful changes still require visual inspection because structural
checks cannot prove legibility or correct meaning.

### Preview, provisioning, and platform certification

Source authoring and validation are designed for portability, but each operating system earns a
support claim through the same conformance fixtures. Version 1 makes no certified draw.io render or
export claim. The product may detect and explain an operator-installed draw.io Desktop application,
but it does not execute that application as an owned renderer before certification.

Browser preview requires explicit network approval, and sensitive diagrams default to offline-only
handling. Hosted preview or MCP processing requires separate content-egress approval. A future
`drawio:provision` operation is explicit, optional, and absent from bootstrap, ordinary install,
repository gates, hooks, and core readiness.

Linux x64 is the first certification candidate because the repository already owns a hardened
sandbox pattern there. macOS and Windows remain unsupported until they have separate evidence.
Certification requires an exact patched renderer and artifact hashes, private profile, network and
filesystem isolation, resource and timeout ceilings, pinned fonts and libraries, source and output
validation, malicious fixtures, visual review, and render receipts. Preview and export remain
advisory and never become correctness, review, or gate verdicts.

### Asset custody and specialization admission

Core ships only first-party layout rules, style tokens, primitive shapes, and original templates.
It does not vendor third-party stencil, icon, template, or shape-library bytes. Renderer-built-in
assets may be referenced only by reviewed identifiers bound to an exact renderer/library version
and documented licence or trademark constraints.

Operator-supplied libraries remain foreign inputs. Record their path-independent identity, digest,
source, licence, and explicit approval without adopting or redistributing them. Mutable remote
libraries, runtime icon search, external images, remote fonts, and `latest` asset URLs are
forbidden. Color never carries meaning alone. Layout references define spacing, direction,
grouping, edge routing, labels, accessibility, and visual-review checks.

A domain specialization earns a top-level sibling only when it has a distinct selector, a
materially different workflow or artifact contract, machine-checkable domain semantics, repeated
demand or proven handoff value, and an accountable maintainer with provenance, fixtures, refresh,
and retirement procedures. AWS architecture demonstrates the pattern but does not automatically
earn an initial sibling or authorize copying assets. Security threat modeling remains separate
because its distinction is analytical rather than visual.

### Lifecycle, collision, and retirement

The first-party skill is `drawio-diagrams`, parallel to the planned `mermaid-diagrams`. “draw.io”
names the artifact format rather than the product. Core installation includes the skill, but its
selector activates only for matching work.

Install preflight decides on exact names and only reports description overlap, under the rule below.
An official `drawio` skill or equivalent foreign surface is preserved. A name collision becomes
`selection-conflict`; Agentic SDLC skips its selector until the operator chooses a channel, while
unrelated bundle entries continue. No lifecycle operation silently migrates, disables, updates, or
removes a foreign plugin.

Skill instructions, safe source tooling, schemas, and reference packs update together through the
receipt-backed bundle lifecycle. Renderer provisioning and refresh remain a separate approved
lifecycle. Canonical diagrams declare schema and profile versions, and bundle updates never rewrite
them. Schema migration requires dry-run output, backup, semantic diff, visual review, and explicit
approval.

Deprecation names the replacement, compatibility window, last supported release, and migration
path. Retirement removes only unchanged owned selectors and optional owned runtime state. It
preserves repository diagrams, sidecars, renders, receipts, operator libraries, and foreign assets.
Every retired format retains a documented read or migration path rather than becoming silently
unreadable.

### Collision rule: exact name decides, description overlap is deferred

“Materially overlapping selection descriptions” is not a rule. It names no compared field, no
normalization, no comparison, and no threshold, so two implementers would build different
preflights and neither could be shown wrong — and the effect it gates is skipping a first-party
selector the core just installed. Version 1 therefore splits the axis rather than implementing a
phrase.

Exact name decides, and that half is specified now. The compared field is the entry name alone:
the directory name a host records for a skill, which `validate_skills` binds to the skill's own
`name`. Normalization is surrounding-whitespace strip plus case-fold, because a case-only
difference is the same directory on a case-insensitive filesystem. The comparison is equality after
that normalization; there is no distance, score, or threshold. The three cases resolve as: equal
name is `selection-conflict` and skips exactly that selector while every other bundle entry
continues; a different name with an overlapping description is reported to the operator and
classifies nothing; an unrelated entry produces neither a report nor an effect. The preflight ships
with fixtures for those three cases when it is built.

Description overlap stays report-only. No automatic classification, skip, or deferral may follow
from comparing description text until the rule itself exists: the exact normalized fields, the
comparison function, a threshold calibrated against a fixture corpus of real skill descriptions,
and those fixtures passing. No implementation may derive that rule from the phrase “materially
overlapping”.

Specifying it is deferred rather than written here because the calibration input does not exist:
`drawio-diagrams` is unbuilt by decision, so there is no shipped description to measure against and
any threshold chosen today would be invented precision. The report-only default is also the
fail-safe one — a missed overlap costs the operator one visible duplicate selector they can resolve,
while a wrong automatic skip silently withdraws a capability the core installed. Issue 17 carries
the same unspecified phrase for role IDs; the same split applies there and needs the same explicit
specification before any description comparison acquires an effect.
