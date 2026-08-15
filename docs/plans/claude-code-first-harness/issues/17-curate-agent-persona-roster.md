# Curate the first-party agent-persona roster

Type: grilling
Status: resolved
Blocked by: 07
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Which first-party agent personas form the curated Agentic SDLC team beyond the existing
cartographer, researcher, planner, implementer, reviewer, integrator, and critic? Require each
persona to own a distinct graph responsibility, least-privilege tool and mutation boundary,
artifact contract, routing needs, acceptance tests, and retirement/collision policy. Decide when
specialization earns a new persona instead of a skill, prompt variant, or task-specific node.
Explicitly assess a documentation writer/editor persona that applies BLUF, the countable-clarity
profile, public clarity rule shapes, evidence preservation, ADR/document schemas, citations, and
an independent readability audit to high-consequence product and repository artifacts.
Explicitly assess task-specific security evidence, threat-model authoring, adversarial review, and
mitigation-verification roles. Promote a permanent security persona only when recurrence, a stable
artifact contract, an independent-review boundary, tests, and retirement policy justify it. No
agent persona may prioritize or accept residual risk for a human risk owner.

## Answer

### Vocabulary and role-agent admission

`Role agent` is the specification term for a permanently installed, independently selectable
agent definition with a stable graph responsibility, privilege boundary, and artifact contract.
`Persona` is conversational shorthand only. A `task role` is one workflow-local assignment. A
`skill` supplies reusable procedure without owning graph responsibility or authority. A `review
lens` is one perspective used by an existing reviewer or critic.

A new role agent must own a distinct responsibility that recurs across mission types, have stable
input and output schemas, need a distinct least-privilege boundary, and provide material value from
independent dispatch or separation of duties. A skill, lens, or task role must not provide the same
value at lower selection cost. The role also needs routing requirements, fixtures, acceptance
tests, collision handling, and retirement criteria.

Every role stays provider-neutral and receives an exact `RuntimeAssignment` at dispatch. Its
submission remains advisory unless it is the already-authorized integrator performing fan-in. A
role never manufactures human approval or outward authority. Incomplete promotion evidence
defaults to a task role or skill while the workflow gathers recurrence and outcome evidence.

### Documentation role

Add one permanent `sdlc-documentarian` role agent. It owns documentation workstreams across
planning, implementation, release, and maintenance. Inputs are approved decisions, technical
evidence, audience, artifact schema, terminology, and declared file scope. Outputs are a
documentation candidate, nearby evidence links, a claim ledger, prose-check results, and unresolved
meaning questions.

The role applies BLUF, countable clarity, the narrow SimpleEnglish adaptation, public
ASD-STE100-inspired rule shapes, diagram rules, ADR schemas, and repository terminology. It writes
only declared documentation paths in its own worktree. It never changes code, configuration,
queues, decision state, or evidence to simplify prose. It may draft an ADR only from an already
resolved decision and cannot choose, approve, accept, or supersede that decision.

The documentarian preserves quotes, uncertainty, evidence strength, warnings, and required
actions. Mechanical prose results stay advisory. High-consequence artifacts require a different
reviewer or critic using the `documentation` lens; the author never reviews its own work. Do not
add a second permanent documentation-review role. Retire the documentarian if ordinary
implementers plus the documentation skill repeatedly match its quality and handoff value.

### Security task roles and promotion evidence

Start security specialization with workflow-local roles rather than permanent role agents:

- `security-evidence`: an existing cartographer or researcher maps assets, trust boundaries,
  controls, code, IaC, and unknowns without mutation.
- `threat-model-author`: a task role writes only the scoped security DFD and threat ledger.
- `adversarial-security-review`: an independent reviewer or critic applies attacker, abuse-case,
  completeness, and assumption lenses without repairing the model.
- `mitigation-verifier`: a separate task role checks control implementation and verification
  evidence; it cannot mark its own proposal effective.
- `human-risk-owner`: a person, not an agent role, who prioritizes threats and accepts residual
  risk under the organization's policy.

Do not add a broad `security-architect` role agent. It would overlap discovery, research, planning,
review, and human risk ownership. The repo-scoped research `safety_reviewer` remains a research
role and acquires no delivery or risk authority.

The threat-modeling workflow records recurrence, material findings missed by generic roles,
artifact-contract stability, independent-dispatch value, fixtures, and acceptance results. Only
that evidence can later promote `sdlc-threat-modeler` or `sdlc-security-verifier`. Neither
candidate is part of the initial permanent roster.

### Proposed-role ledger

| Name | Classification | Decision | Promotion or retirement signal |
|---|---|---|---|
| `sdlc-documentarian` | Role agent | Add to the initial permanent roster | Retire if an implementer plus skill repeatedly matches its quality and handoff value. |
| `documentation` | Review lens | Apply through an independent reviewer or critic | Reconsider only if it develops a distinct recurring artifact and privilege boundary. |
| `security-evidence` | Task role | Exercise in threat-modeling workflows | Promote only if mapping diverges materially from cartographer/researcher contracts. |
| `threat-model-author` | Task role | Exercise in threat-modeling workflows | Candidate source for `sdlc-threat-modeler` after canary evidence. |
| `adversarial-security-review` | Review lens and task role | Apply through an independent reviewer or critic | Promote only if generic reviewers repeatedly miss material threats. |
| `mitigation-verifier` | Task role | Exercise separately from authoring | Candidate source for `sdlc-security-verifier` after canary evidence. |
| `sdlc-threat-modeler` | Deferred role-agent candidate | Documented, not shipped | Requires recurrence, stable artifacts, tests, and demonstrated independent value. |
| `sdlc-security-verifier` | Deferred role-agent candidate | Documented, not shipped | Requires a stable verification boundary and measurable advantage over reviewer lenses. |
| `security-architect` | Rejected broad role | Do not ship | Reconsider only after decomposing it into non-overlapping responsibilities. |
| `documentation-reviewer` | Rejected duplicate role | Use the `documentation` review lens | Reconsider only if independent review outgrows the reviewer/critic contract. |

### Initial permanent roster

Freeze the initial global roster at eight role agents: `sdlc-cartographer`, `sdlc-researcher`,
`sdlc-planner`, `sdlc-implementer`, `sdlc-reviewer`, `sdlc-integrator`, `sdlc-critic`, and the new
`sdlc-documentarian`.

The conductor is the main session and authority coordinator, never a spawned role agent. Architect
and ADR-author responsibilities use the planner plus ADR skills. Diagnosis, testing, UX,
dependency, release-writing, and other specialties remain skills, task roles, or review lenses
until promotion evidence exists. The model router is a conductor control-plane skill. Research
OS's specialist roster stays a repo-scoped optional profile rather than entering the global SDLC
selection surface. Legal, compliance, publication, and residual-risk decisions remain with
accountable people.

### Capability-demand routing

Role definitions contain no static provider, model, effort, context, or semantic-tier pin. Every
workflow node supplies a `CapabilityDemand` covering its role and task type, evidence stakes,
reasoning and context needs, required tools and transport, mutation boundary, resource constraints,
and independence requirements. The rightsizing control plane resolves that demand into an exact
`RuntimeAssignment` before dispatch.

Role files may declare capability floors and incompatibilities but never exact model IDs. The same
role may receive different routes for different tasks. Author and reviewer are distinct agent
instances; provider or model diversity is preferred when it materially improves independence, but
the receipt records whether it was achieved rather than fabricating it. Missing, inherited,
ambiguous, or unverified assignments stop before spawn. Post-run provider/model identity evidence
remains mandatory, and resolution failure returns a typed blocker or proposal without fallback.

### Common submission and responsibility matrix

Every role returns one `RoleSubmission` envelope with `role`, `scope`, `findings`, `evidence`,
`recommendation`, `blockers`, `unknowns`, and `next_action`. A blocked role returns the same
envelope. Role-specific artifacts link from it rather than replacing it, and every recommendation
remains advisory.

| Role | Graph responsibility | Role-specific artifact | Maximum mutation |
|---|---|---|---|
| `sdlc-cartographer` | Map one repository area or risk lens. | Evidence-backed repository map. | Mission artifact only. |
| `sdlc-researcher` | Resolve one load-bearing unknown. | Cited decision brief. | Research artifact only; declared network use. |
| `sdlc-planner` | Compile evidence into one executable wave. | Plan candidate and Seed proposals. | Planning artifact only; never the queue. |
| `sdlc-implementer` | Execute one authorized workstream. | Candidate change and gate report. | Assigned files in one dedicated worktree. |
| `sdlc-reviewer` | Inspect one immutable candidate. | Severity-ordered review findings. | No candidate repair; gates only in an isolated review checkout. |
| `sdlc-integrator` | Perform already-authorized fan-in. | Integration report and recovery evidence. | Integration branch only; never push or publish. |
| `sdlc-critic` | Attack the integrated stable snapshot. | Classified recommendations. | Critique artifact only; never fixes or queue writes. |
| `sdlc-documentarian` | Author one evidence-bound documentation scope. | Documentation candidate, claim ledger, and prose report. | Declared documentation paths in one worktree. |

Boundary violations stop the role and enter its evidence rather than triggering self-repair.
Reviewer, critic, and documentarian self-review are forbidden where independence is required. The
conductor validates the envelope and separately captures authorized queue actions. Host adapters
may change syntax but not fields, responsibility, evidence meaning, or authority.

### Certification, customization, collision, and retirement

Every role and `RoleSubmission` declares a `role_contract_version`. Claude and Codex projections
remain semantically equivalent for responsibility, boundaries, fields, and authority language.
Certification covers positive and nearest-neighbor selection, required-input and unresolved-route
refusals, valid and malformed submissions, allowed and forbidden custody actions, evidence and
advisory language, author/reviewer separation, workflow placement and failure, no fallback, and
host-manifest parity.

Tests label control strength honestly: host-enforced tool restrictions are `enforced`, while
prompt-only prohibitions remain `instructed`. Role certification and model-route qualification are
separate facts.

Install preflight audits exact role IDs and materially overlapping descriptions across direct,
plugin, user, and repository channels. Foreign and user-authored roles are preserved. A conflict
blocks only the affected first-party projection until the operator chooses a channel. A modified
owned role becomes `modified`; updates preserve it rather than overwriting it. Repository-local
roles, task roles, and lenses remain custom and never inherit first-party certification.

Breaking contracts require a new version, migration guidance, and a published compatibility
window. Retirement requires usage evidence, deprecation, workflow replacement, and migration
fixtures. Removal deletes only unchanged owned definitions; mission artifacts, submissions,
custom roles, and foreign definitions remain. A workflow that references a missing or retired role
fails compilation with replacement guidance and never substitutes silently.
