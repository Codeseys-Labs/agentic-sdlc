# Define operator observability and receipt experience

Type: prototype
Status: resolved
Blocked by: 06, 07, 08, 11
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What should `ccodex sdlc status`, `doctor`, workflow progress, route qualification, wave journals,
and final receipts show to let an operator understand installed ownership, selected versus active
versions, requested versus effective runtime identity, costs and egress, graph progress, approvals,
failures, recovery state, and completion evidence? Prototype concise human output plus stable
machine-readable forms without leaking credentials, private prompts, or telemetry by default.

## Decisions

### Canonical local observability spine

`ccodex sdlc status` is the canonical read-only overview. It derives one current snapshot from
the installed distribution and ownership receipts, the physical current repository and its
activation state, the selected workflow/wave artifacts, route and runtime-assignment evidence,
approval and effect receipts, and completion or recovery state. It does not start a process,
contact a provider, repair drift, refresh evidence, acquire trust, mutate a queue, or infer health
from package presence. Outside an activated repository it still reports the installed plane and
labels repository and workflow state `not-selected` rather than treating absence as corruption.

The concise human view is BLUF-first: overall report validity, current mode and scope, the most
important blocked or degraded dimensions, active work and last proven effect, evidence freshness,
and one bounded next command. Installed versus selected versus active versions; configured versus
live routes; requested versus independently observed runtime identity; and main-session,
classifier, generic-worker, and named-workflow lanes remain separate facts. Client integrations
also remain separate; no status in one client is generalized to another.

`ccodex sdlc doctor` is the offline read-only diagnostic expansion. It explains missing,
contradictory, stale, foreign, partial, or unknown evidence and proposes exact follow-up checks,
but it does not repair, restart, synchronize, authenticate, probe, qualify, trust, install, or
remove anything. Any later networked diagnostic or mutation uses a separately named plan/apply
operation with its own declared egress and approval; `doctor` intent is never authority.

`ccodex sdlc inspect <run|wave|route|receipt> <id>` exposes the detailed local evidence behind one
summary item. Route inspection links to the canonical `ccodex routes` facts, and receipt inspection
links to its owning lifecycle artifact; neither copies or promotes evidence into a second source
of truth. Private prompts, model output, credentials, account identity, reversible credential
encodings, and sensitive upstream journals are not made observable merely because they exist.

Human output and `--json` are two renderings of the same closed, versioned semantic record. The
machine form is not scraped from prose, and the human form cannot omit a blocker that exists in
the record. Successful query execution exits successfully even when the record reports blocked,
degraded, partial, unsupported, or unhealthy dimensions; report validity and observed health are
separate. Schema or input errors, clean refusals, partial effects, and internal failures retain
their already defined exit meanings.

Version 1 adds no telemetry database, duplicated event warehouse, daemon, hosted dashboard, or
default egress. Canonical local artifacts remain the source of truth and the observability spine
is a disposable projection over them. An optional future view may consume the stable machine
record, but it cannot become required for workflow progress, admission, recovery, or completion.

### Typed receipts, effect journals, and correlation

Evidence uses a small family of typed, immutable terminal receipts rather than one universal log:
distribution and activation lifecycle; route and credential lifecycle; probe and qualification;
workflow, wave, and node attempt; integration and completion; and incident or recovery. Each kind
has an independently versioned closed payload plus a common envelope for receipt kind and ID,
producer and schema versions, physical subject and scope, typed ancestor references, plan and
approval digests where applicable, start and close times, terminal status, effect state, blockers,
bounded next action, redaction profile, artifact/evidence references, and integrity digest. A
receipt records evidence and never grants approval, admission, completion, or outward authority.

Before the first admitted local mutation, process effect, model/provider call, or external
revocation, the owner durably opens a content-minimized append-only effect journal bound to the
approved plan and prestate. Each admitted stage appends its attempt identity, exact target or
route, observed effect boundary, usage/budget facts where applicable, result class, and referenced
evidence without copying prompts, model output, source bodies, credentials, account identity, or
reversible encodings. Concurrency is serialized by the owning lifecycle; readers never rewrite a
journal to make it appear complete.

At a proven terminal boundary, finalization produces an immutable typed receipt bound to the exact
journal digest and terminal observations. If effect is partial or cannot be proved, the journal
remains protected evidence and finalization records `partial` or `unknown`; it cannot manufacture
`none`, rollback, or completion. A crash after effect but before final receipt leaves the journal
as the recovery authority. Finalization does not erase an unknown-effect journal, and retention,
schema migration, provider removal, or uninstall never silently discards it.

Correlation is a typed evidence graph, not one overloaded correlation string. Mission, run, wave,
workstream, node, attempt, route, credential slot, lifecycle operation, approval, artifact, and
receipt identities retain their distinct kinds. Child records name their direct typed ancestors
and referenced evidence; the observability spine derives paths and fan-out without copying the
artifacts. Missing, duplicate, dangling, cyclic where acyclicity is required, or kind-incompatible
references are reported as evidence defects and cannot be repaired by display code.

Requested runtime assignment and independently observed provider/model, effort, context, usage,
and route identity remain separate within every model-calling attempt. Main-session, classifier,
generic-worker, and named-workflow attempts receive distinct attempt and route references even
when they occur in one Claude Code session. No parent receipt may summarize an unverified child
identity as verified merely because the parent selected or requested it.

The observability spine reads supported historical schema versions through read-only compatibility
renderers. Migration writes a new typed artifact or compatibility view with provenance and keeps
the original; it never edits an immutable receipt in place. Unsupported or malformed versions are
`unreadable-evidence`, not absent or healthy, and block any decision that requires their facts.

### Wave progress as a dimensional DAG projection

Wave progress is a read-only projection of the approved graph and its admitted artifacts, not a
percentage, activity counter, confidence score, or completion verdict. Each node keeps execution,
input/admission, review, gate, and effect dimensions separate. The execution dimension records
planned, runnable, running, or terminal; terminal disposition records admitted success,
approved skip, explicit block, failure, or unknown effect. Review and gate results never overwrite
execution state, and activity never upgrades an unadmitted artifact.

The BLUF wave view names the wave and approved revision, execution profile, current graph frontier,
active and runnable nodes, approval and gate waits, blocked dependency chains, retries, remaining
node/time/call/token/cost budgets, and the last proven effect. It lists parallel branches
independently. One blocked branch does not imply that all work stopped, and another branch may
continue only when its dependencies and the approved graph remain valid.

`ccodex sdlc inspect wave <wave-id> --follow` follows only the local wave and effect journals and
their referenced receipts. It opens no provider connection, starts no daemon, acquires no writer
authority, changes no workflow state, and can be interrupted without affecting execution. Follow
ends when the wave reaches a terminal receipt or the reader stops; a stale writer, malformed event,
missing reference, or unknown effect remains visible rather than being smoothed into progress.

Version 1 shows no synthetic percent complete or ungrounded time-to-completion estimate because
parallel nodes have unequal work, review, gate, and effect consequences. A repository may later
display an advisory forecast only from named comparable historical evidence with sample size,
method, uncertainty, and observation date; a forecast never participates in admission or
completion. Raw node counts remain descriptive and never imply proportional work.

Wave completion is derived only from the accepted graph contract: required-node dispositions,
runtime identity, artifact admission, workstream reviews, authorized fan-in, integrated gates,
budgets, approvals, adversarial review, and the conductor's terminal verdict. A fully executed
graph can still be blocked, remediation-progress, or product-unsuccessful; neither a quiet journal
nor all nodes reaching a terminal execution state proves completion.

### Usage, cost, and declared-egress accounting

Operator summaries have two visible top-level usage scopes: `Main` for top-level non-delegated
session calls and `Agents` for standalone subagent roots plus workflow-owned roots. The scopes are
rendered from one atomic evidence snapshot rather than independent counters. Within `Main`, the
answer-producing session and background/classifier lanes remain separate; within `Agents`, generic
subagent and named-workflow ownership remains visible. A call has exactly one owning scope,
attempt, and exact route reference.

Nested attempts roll up through their workflow-owned root exactly once. Workflow ownership wins
when a call could appear through both a generic-agent and workflow view. Aggregation sums admitted
leaf observations and never adds a provider or host all-session total over the same calls. Missing
correlation, duplicate ownership, or overlapping provider totals make the affected aggregate
`unknown` or `lower-bound`; display code cannot guess away the overlap.

Authorized budget, observed calls/tokens/time, remaining quota or usage-credit capacity,
provider-reported monetary charge, and price-table estimate are different fields. Each monetary
observation names currency, provider, exact route, billing basis, pricing source/version, and
observation time. Subscription marginal monetary cost is `null`/`unknown`, never free or zero;
API-equivalent price is a separately labeled estimate and cannot become a charge. Quota, rate
limit, subscription allowance, usage credits, and money are not interchangeable units.

Every scope and aggregate carries one certainty state: `exact`, `lower-bound`, `unpriced`,
`missing-usage`, or `stale`. Missing numeric values remain null. Cross-provider output shows a
known subtotal plus named unknown or unpriced components rather than a false grand total. Budget
admission uses the approved units and conservative bounds; later observation cannot retroactively
authorize an over-budget call.

Egress accounting groups admitted attempts by exact route and credential slot, destination,
purpose, transmitted data classes, call count, observed token or byte measure when exposed,
external retention boundary, and approval digest. It contains no credential, account identity,
private URL, prompt, model output, source body, or reversible encoding. Declared egress and
observed transport evidence remain separate: a declaration is not proof that a call occurred,
while observed undeclared or mismatched egress is an incident and cannot be normalized into the
approved total.

Human status and any supported host statusline keep `Main` and `Agents` visually distinct while
using the same atomic machine snapshot. If the host cannot supply exactly-once observations for a
lane, the product reports the appropriate uncertainty state rather than claiming complete live
cost tracking. Accounting stays local and creates no product-telemetry exception.

### Approval, failure, and recovery presentation

Every approval requirement is displayed independently with its authority plane, operation and
scope, plan digest, approval-receipt reference when present, validity conditions, and one state:
`missing`, `pending`, `granted`, `declined`, `expired`, or `superseded`. A hard human approval is
visually and structurally distinct from an automated gate, agent recommendation, reviewer verdict,
or policy admission. No prompt, chat acknowledgement, passing check, requested action, or nearby
approval can be rendered as `granted` without an admissible operation-specific approval receipt.

Declined, expired, and superseded approvals confer no residual authority. A changed plan, scope,
route, egress declaration, budget, target identity, or validity condition produces a new digest
and returns the applicable requirement to `missing`; display code cannot carry the prior state
forward. Human output may omit approver identity for privacy, while the local receipt retains only
the minimum identity or authority-class evidence required by the owning contract.

A failure or interruption leads with result class and effect state, then names the last proven
stage, last known safe state, unresolved or unknown effects, affected branches/routes/artifacts,
stopped and still-valid work, retained journal and receipt references, and one bounded next
command. `none`, `partial`, and `unknown` are never inferred from exit status alone. Internal
failure is not relabeled as policy refusal, and a quiet or missing process is not proof that an
external effect stopped.

Possible credential exposure, reversible credential encoding, undeclared or mismatched egress, or
private-content escape creates a content-minimized redacted incident receipt and blocks the
affected continuation. The view names the operation, affected plane and data class, time window,
possible exposure class, containment state, and incident-response handoff without reproducing the
suspected value or content. It does not transmit the incident or inspect an external account by
default.

Recovery presentation is always a new read-only assessment of current prestate and admitted
evidence. It proposes exact remaining or compensating stages, identifies approvals that remain
valid and those that must be reacquired, and emits a new plan digest. Viewing status, doctor,
failure details, or a recovery plan never retries a call, authenticates, revokes, repairs, resumes
a worker, or mutates state. The default next command is read-only or plan-producing; any apply
command is explicitly labeled with its expected effects and requires its own approval.

### Terminal wave receipt and handoff

A wave has no terminal classification until the conductor closes an immutable typed wave-outcome
receipt. The closed verdict is exactly one of `accepted`, `remediation-progress`, `blocked`,
`aborted`, `failed`, or `unknown-effect`. Receipt existence proves only that the wave reached a
recorded terminal disposition; it does not imply success, repository readiness, mission
completion, product success, or authority for another operation.

The receipt binds the mission and wave identities, objective, approved graph revision and digests,
execution profile, repository physical identity and admitted pre/post snapshots, node and gate
dispositions, runtime-assignment and observed-identity receipt references, declared artifact
digests, workstream reviews, authorized fan-in, integrated repository gates, approval states,
budgets and accounting certainty, declared and observed egress, adversarial findings and human
dispositions, unresolved blockers, retained incident/recovery evidence, and follow-up proposals.
It references sensitive artifacts by admitted digest and type rather than copying their bodies.

`accepted` is available only when the Dynamic Workflow completion contract closes: every required
node has an admitted disposition; runtime substitutions are explained and admissible; artifacts,
reviews, fan-in, integrated gates, budgets, approvals, and adversarial review satisfy the approved
wave; and no blocking finding or unknown effect remains. A brownfield hygiene wave that advances
an admitted baseline without reaching repository write-readiness uses `remediation-progress`.
Known blockers, operator stop, failed requirements, and unresolved effects use their truthful
non-success verdict rather than a weakened success label.

Discoveries beyond the approved wave are typed Seed proposals in the receipt. They name the
proposed objective, evidence, priority, dependencies, acceptance outline, and originating finding,
but they do not mutate or become entries in the selected repository queue. Only the admitted
conductor queue-write operation may record chosen proposals in Seeds or another configured tracker,
with its own prestate, approval, effect journal, and receipt.

Push, publication, PR creation or mutation, merge, deployment, credential change, and any other
outward effect retain separate operation-specific approvals and typed receipts. A wave-outcome
receipt may reference such an already authorized result but cannot grant or infer it. Conversely,
successful outward publication does not upgrade a blocked or failed wave.

The terminal handoff renders one BLUF human summary and one stable machine record from the same
receipt: verdict and why, delivered and undelivered scope, repository state, completion evidence,
usage/cost/egress certainty, blockers or incidents, follow-up proposals, and one bounded next
command. If finalization fails, the effect journal remains non-terminal recovery evidence and the
observability spine reports the wave as partial or unknown rather than inventing a receipt.

### Release acceptance

The observability release gate is deterministic and offline. Golden fixtures cover every concise
human view, closed machine envelope, receipt kind, terminal verdict, certainty state, and supported
historical schema renderer. Fixtures include no installation, installed-but-unselected,
native-only, healthy and drifted routes, parallel active waves, approval waits, blocked branches,
remediation progress, failed finalization, incidents, malformed or unreadable evidence, and
unknown effects.

No-effect tests prove `status`, `doctor`, `inspect`, and `inspect wave --follow` do not contact a
provider, acquire writer authority, mutate a queue or configuration, repair state, trust a file,
refresh evidence, or create product telemetry. Fault injection covers journal truncation, crashes
before and after effects, finalization failure, concurrent readers and writers, duplicate or
dangling typed references, invalid cycles, stale writers, unsupported schemas, and contradictory
terminal facts. A display or renderer cannot hide or repair the defect it observes.

Adversarial fixtures place credential-shaped strings, reversible encodings, private prompts and
model output, account identity, private URLs and paths, and undeclared-egress evidence at every
input boundary. Human and machine output must remain content-minimized while preserving the
blocking fact and incident handoff. Accounting fixtures prove exactly-once scope ownership,
nested-workflow rollup, uncertainty propagation, subscription cost as unknown, known subtotals
with named unknown components, and no retroactive budget authority.

Completion fixtures prove that process quietness, all nodes terminal, passing partial gates,
receipt existence, outward publication, and non-blocking future Seeds cannot independently mint
`accepted`; the full completion predicate can. Live provider attribution, provider billing,
host-statusline, filesystem-notification, and platform canaries remain separately approved
operational evidence and never repository gate prerequisites. Support claims are limited to the
exact host and platform combinations those canaries currently verify.
