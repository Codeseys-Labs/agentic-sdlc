# Define the documentation and communication defaults

Type: grilling
Status: resolved
Blocked by: 01, 05, 22, 23
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Which BLUF, countable-clarity, ADR, Mermaid, evidence-citation, and traceability rules are mandatory
product defaults, optional styles, or target-repository choices? Define how they apply without
rewriting quoted evidence, overstating ASD-STE100 conformance, or making prose linters false gates.
Decide whether the SimpleEnglish repository is an optional external tool, an adapted source of
first-party rules with donor notice, or neither, and how controlled-English rewriting applies to
documentation, decisions, and domain language without altering technical meaning.

## Answer

### BLUF across human and agent communication

BLUF is mandatory for prose that asks a reader or downstream agent to decide or act. Interactive
answers, plans, reviews, findings, wave verdicts, handoffs, delegations, status/doctor/refusal and
recovery output, README quickstarts, runbooks, ADR summaries, queue summaries, and release notes
state the outcome, decision, failure, or required action first. Supporting evidence follows only
as needed. Machine-readable handoffs carry the bottom line in a stable summary field.

BLUF does not alter verbatim evidence, code, command output, schemas, licence text, or quotations.
Accuracy, evidence strength, and necessary uncertainty outrank brevity.

### Countable-clarity product profile

The existing countable-clarity profile is the controlled-writing default for new or materially
revised Agentic SDLC-authored documentation, ADR prose, glossary entries, skills, agent prompts,
delegations, and workflow handoffs. Procedures use at most 20 words per sentence, one instruction
per sentence, and imperative active voice. Descriptive text uses at most 25 words per sentence and
six sentences per one-topic paragraph. Noun clusters stop at three words; one term names one
concept; three or more coordinated items become a vertical list; safety/error text leads with the
action and then states cause and recovery.

Rewrites preserve technical meaning, evidence class, qualification, and uncertainty. Code,
commands, schemas, licence text, quotations, transcripts, and other verbatim evidence are masked
from rewriting and counting. Brownfield documentation is never rewritten wholesale: changed prose
uses the profile and existing debt becomes optional hygiene work. Repositories may tune thresholds
in `.agentic-sdlc/repo.toml`; product-owned artifacts keep the product defaults.

### SimpleEnglish and ASD-STE100 boundary

The [content-gap analysis](../research/simpleenglish-content-gap-analysis.md) supports a narrow
first-party adaptation, not another installed skill. Re-express five ideas in the incumbent
clarity reference: put a condition before its dependent command; expand contractions and make
referents explicit; prefer direct verbs to action nouns; flag semicolons and Latin abbreviations
for review; and report each violation's location with a meaning-preserving rewrite candidate. The
implementation change adds exact MIT donor/provenance text to `NOTICE`. It copies no foreign prose,
rule numbers, vocabulary tables, prompts, or output styles and adds no SimpleEnglish installer or
selection row.

The feature is named the **countable-clarity profile**, never Simplified Technical English. It uses
the maximum honest subset of publicly supportable ASD-STE100-inspired rule shapes that improves
software writing without licensed dictionary material, meaning drift, or evidence conflict. The
honest phrase is “checked against public clarity rule shapes.” The product never claims compliance,
conformance, certification, endorsement, or full-standard coverage; never reconstructs the
dictionary; and never uses the ASD logo/trademark as a product/skill/profile name. An operator with
licensed material may configure an external advisory checker; Agentic SDLC does not distribute,
ingest, or attest it.

### Tiered writing and review

Routine messages and small edits use author-applied BLUF plus the countable self-audit.
High-consequence artifacts—ADRs, runbooks, architecture briefs, release guidance, handoffs, and
safety instructions—receive an independent documentation review. The reviewer reports counts,
locations, terminology drift, ambiguous referents, evidence-strength changes, and
meaning-preserving candidates. It does not edit exclusions or decide technical correctness. The
agent-persona roster ticket will decide whether this becomes a permanent documentation
writer/editor persona or a task-specific role.

### Evidence and traceability

Substantive claims distinguish verified, observed, inferred, proposed, and unknown when relevant.
External facts cite primary sources where available; repository facts cite exact files, lines,
receipts, gates, or digests. Citations sit beside their claims. Plans, delegations, handoffs,
reviews, and verdicts reference their mission, queue item, ADR, wave, assignment, artifact, and
gate as applicable. Agent summaries include evidence pointers rather than requiring trust in a
paraphrase. Decorative/obvious statements need no citation. Provenance is not correctness,
approval, or authority.

### Diagrams

Use diagrams only when relationships, sequencing, hierarchy, ownership, or free-form spatial
layout become materially clearer than short prose. Every diagram includes a BLUF caption and
prose/alt text sufficient when rendering is unavailable. Editable source remains canonical;
derived renders are evidence with version/provenance receipts, not the only maintained copy.

Mermaid is the structured text-diagram default. Its authoring guidance ships in core; rendering is
separately provisioned, sandboxed, sanitized, advisory, and never a gate leaf. Brownfield
conventions may replace Mermaid when they retain editable source and equivalent safety.

Draw.io is a core-shipped optional first-party capability for editable canvas geometry, layers,
pages, stencils, icons, and free-form layout. The
[draw.io research](../research/drawio-agent-diagram-workflows.md) supports one umbrella skill with
lazy type references, not generic per-type skill rows. Canonical source is bounded uncompressed
`.drawio` XML. Safe parsing, schema and semantic validation, external-content checks, and visual
review precede use. Browser preview is declared egress. Desktop/render/export remains separately
provisioned and uncertified until pinned, sandboxed, measured, and provenance-tested. Domain-heavy
specializations may earn sibling skills only through distinct inputs, libraries, semantics,
validation, recurrence, and maintenance ownership.

### Prose checking

The self-audit is mandatory for product-authored prose. Automated tools report rules, locations,
counts, and rewrite candidates, never a quality score. They mask all excluded content and remain
advisory/outside `mise run check` by default. A repository may promote a proven low-false-positive
subset through `.agentic-sdlc/repo.toml` only with a clean baseline, pinned deterministic tool,
explicit exclusions, and a reasoned override path. Documentation review blocks acceptance only
when ambiguity changes meaning, safety, evidence, or required action—not because a score failed.
Linter success proves neither technical correctness nor ASD-STE100 conformance.
