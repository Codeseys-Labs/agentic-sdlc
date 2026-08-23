# Define planning workflows, drift correction, and bounded auto mode

Type: grilling
Status: resolved
Blocked by: 07
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

How should read-only planning workflows investigate, diagnose, research, critique, and compile a
versioned wave graph; detect and correct drift between mission, plan, repository, and artifacts;
and proceed under an optional preauthorized auto-mode envelope? Define plan schemas and diffs,
admission checks, replanning triggers, autonomous transitions, hard human gates, audit evidence,
pause/resume behavior, and the boundary from bounded autonomy to permission bypass.

## Decisions

### Planning artifact chain and deterministic compiler

Planning has four canonical immutable artifacts. `MissionContract` records the durable objective,
success and terminal criteria, non-goals, constraints, authority ceiling, and mission-level stop
conditions. `PlanningSnapshot` records observed current state and its evidence independently from
desired state. `WavePlan` is one versioned candidate execution DAG for a bounded wave. `PlanDiff`
is the semantic delta from the last approved revision or, for the first wave, from no prior plan.
Every artifact has a stable identity, schema version, content digest, producer, provenance, and
typed references to its inputs.

The snapshot binds the physical repository/worktree identity; admitted commit, tree, dirty-state,
and custody summaries; queue and dependency state; selected distribution and activation receipts;
host capabilities; route and rightsizing evidence; applicable policies and ADRs; active or retained
wave artifacts; and named unknowns. Sensitive source, issue, prompt, credential, and model-output
bodies stay in their owning plane and enter the snapshot only as admitted typed references and
digests. Historical vision, desired behavior, and stale documentation are labeled as claims and
cannot populate observed current state without current evidence.

A planning workflow is read-only relative to the target repository, queue, configuration,
credentials, providers, integrations, and outward systems. It may write only owned artifacts in
the mission planning workspace. Cartographer, researcher, diagnostic, planner, documentarian, and
critic nodes may investigate in parallel and submit typed evidence or recommendations; none edits
the candidate graph directly or settles truth by role label.

One deterministic plan compiler consumes the MissionContract, admitted PlanningSnapshot, selected
typed submissions, repository policy, and execution-profile limits. It validates schemas,
provenance, evidence conflicts, graph acyclicity, dependencies, custody exclusivity, capability
feasibility, and closed authority/resource bounds, then emits the WavePlan and PlanDiff. It does
not call a model, choose among contradictory facts, repair the repository, mutate a queue, resolve
a runtime route, grant approval, or execute a node.

Every executable node declares a stable node ID, bounded objective, role/capability demand and
wrong-output class, typed input references and output schema, dependency edges, owner and worktree
or advisory-artifact custody, permitted reads/writes and effect class, required RuntimeAssignment
shape, egress, node and shared budgets, gates and approvals, retry/fallback/stop rules, review and
integration requirements, terminal dispositions, and Seed-proposal behavior. An exact runtime
route remains unresolved until the separate pre-spawn contract admits it; a planning preference
or model-task recommendation is not a RuntimeAssignment.

The PlanDiff names every added, removed, or changed node, edge, artifact, custody boundary,
authority, route constraint, egress declaration, budget, gate, approval, retry, stop rule, and
terminal criterion, together with its evidence and consequence. Reordering or prose changes that
do not alter semantics are identified separately. A change never mutates an approved WavePlan in
place; it produces a new revision and digest.

Compilation stops on missing or contradictory load-bearing evidence, ambiguous ownership,
unbounded effects, cyclic dependencies, infeasible custody, unsupported capability, or an
unresolved required policy choice. The result is a diagnostic and bounded evidence request or
Seed proposal, not an assumed executable node. A compiled or even admitted WavePlan remains
evidence only; operation-specific human approval and runtime admission are separate prerequisites
for execution.

### Drift taxonomy and boundary checks

Plan drift is any observed difference between current state and a load-bearing MissionContract,
PlanningSnapshot, approved WavePlan, admitted artifact, or approval invariant. The classifier has
four closed outcomes. `compatible` means the change is unrelated or explicitly tolerated and all
affected invariants still hold. `revalidation-required` means plan semantics are unchanged but one
or more freshness, identity, capability, or admission facts must be renewed. `replan-required`
means graph semantics or a plan-bound invariant changed. `hard-stop` means continuation would cross
an authority, ownership, security, credential, destructive/outward-effect, or unknown-effect
boundary. Ambiguous classification is `hard-stop`, never compatible.

Drift is checked against fresh bounded observations before plan approval, every node dispatch,
the first write in a workstream, fan-in, each integrated gate, any recursive graph expansion, and
resume after interruption or session loss. The check compares the current physical repository and
worktree, dirty/custody state, queue dependencies, policies and decisions, toolchain and host
capabilities, routes and qualification, approval validity, input artifact digests, budgets, egress,
and prior effect state with the exact invariants referenced by the plan. It creates evidence only
and does not install a watcher or claim detection between those boundaries.

A compatible change is recorded with its evidence and affected-invariant analysis; it neither
rewrites the approved snapshot nor expands the plan. Revalidation pauses only the affected graph
frontier, obtains a new PlanningSnapshot observation and the required admission evidence, and may
continue without a new plan approval only when the semantic digest is unchanged and the existing
approval explicitly remains valid under refreshed evidence. Otherwise it becomes replan-required.

Replan-required drift produces a new PlanningSnapshot, immutable WavePlan revision, and PlanDiff.
Examples include changes to mission or terminal criteria, nodes or edges, repository base or
owned paths, dependencies, custody, required artifacts, policies or gates, capability demands,
route constraints, egress, budgets, retries, fallback, integration, or review. The prior revision
remains historical and cannot execute new work after supersession. Human approval is the default
for the new digest; bounded auto-mode handling is a separate later decision.

Hard-stop drift immediately prevents the affected dispatch or mutation and records the last
proven safe state, stopped and still-valid branches, effect state, blocker, and required human
disposition. It includes foreign or ambiguous ownership, credential or security-boundary change,
new destructive or outward effect, authority expansion, corrupted evidence, and any partial or
unknown prior effect. No acknowledgement, retry, old approval, or unaffected gate can downgrade
the stop.

Independent branches may continue only when the approved graph permits it and their inputs,
custody, authority, routes, budgets, and terminal validity are unaffected. Drift detection never
repairs, resets, rebases, checks out, stashes, overwrites, removes, reauthenticates, reroutes, or
rewrites a queue. Any such response is a separately planned and approved operation.

### Plan admission and approval lifecycle

Each WavePlan revision has exactly one lifecycle state: `draft`, `compiled`, `admitted`,
`approved`, `active`, `terminal`, or `superseded`. States are monotonic except that failed checks
leave the plan in its prior state with new diagnostic evidence; no state is inferred from a file's
presence, a user prompt, an agent claim, or activity in another revision. The immutable artifact
never changes in place as its lifecycle advances; typed receipts bind transitions to its digest.

`draft` is incomplete planning work. `compiled` means the deterministic compiler proved closed
schema, references, graph structure, and bounded declarations; it does not prove present
feasibility or permission. `admitted` means a separate current-state check proved snapshot
freshness, physical target and custody identity, dependency and artifact availability, applicable
policy and ADR consistency, host/tool capability, route constraints and qualification, budgets and
declared egress, gates and review/fan-in requirements, fallbacks and stop conditions, approval
requirements, and absence of an unresolved prior effect.

Admission is read-only and produces a content-minimized receipt or exact blockers. It does not
repair, install, authenticate, trust, reserve a route, create a worktree, mutate a queue, or grant
authority. A missing exact RuntimeAssignment for an executable node does not become a default;
where route resolution is deliberately deferred to pre-spawn, admission instead proves the node's
closed resolution requirements and that at least one current candidate can satisfy them without
claiming which route will execute.

Before approval, the human view presents the objective, semantic PlanDiff, repository and custody
scope, graph and parallelism, writes and outward effects, routes and egress, budgets, fallbacks,
hard gates, completion contract, and every named unknown. `approved` requires an operation-specific
human receipt bound to the exact WavePlan revision and digest, admitted PlanningSnapshot and
policy identities, physical targets, authority, routes/constraints, egress, budgets, and validity
conditions. Passing admission, an agent recommendation, or approval of another revision cannot
substitute.

Approval does not start the wave. Immediately before launch, the conductor rechecks admission,
approval validity, and drift. Only after those checks pass does it durably open the wave effect
journal and dispatch the first admitted node; that transition makes the revision `active`. Failure
before the journal opens leaves effect state `none` and the plan approved but inactive. A later
replan marks the older nonterminal revision `superseded`; it cannot launch or dispatch additional
work.

The wave-outcome receipt moves an active revision to `terminal` with its truthful verdict.
Credential change, destructive action, publication, push, PR mutation, merge, deployment, and
other non-delegable outward effects retain their separate approval gates even when named in an
approved wave. Wave approval may establish that those gates will be encountered; it never grants
them in advance.

### Default-off bounded auto-mode envelope

Agentic SDLC bounded auto mode is disabled by default and enabled only by operation-specific human
approval for one exact WavePlan revision. Global or repository preferences may propose an auto
profile, but they cannot activate it or carry approval into another wave. The resulting immutable
`AutoEnvelope` binds the plan and PlanningSnapshot digests, physical targets and custody, allowed
authority/effect classes, route constraints and fallbacks, egress, tools, graph-change allowlist,
concurrency and recursive-execution limits, retry policy, node/time/call/token/cost budgets,
validity conditions, checkpoints, and stop rules.

Inside the envelope, the conductor may dispatch already approved runnable nodes; perform a
preapproved retry when the prior attempt is proven no-effect or the owning read-only policy admits
it; reorder independent nodes without changing dependencies; add bounded read-only investigation,
diagnosis, research, planning, or critique nodes; decompose a node while preserving its declared
outputs, custody, authority, egress, gates, reviews, and terminal criteria; and select only an exact
qualified fallback already admitted by the plan. Every transition rechecks remaining budgets,
current evidence, drift, and the narrower authority inherited by children.

Each autonomous graph change produces a new immutable WavePlan revision and PlanDiff before more
work runs. The compiler and admission checks must prove that the change matches a closed
AutoEnvelope rule; the conductor records a typed autonomous-transition receipt. Rephrased prose,
agent confidence, apparent urgency, a passing local check, or unused budget cannot make an
unlisted change permissible. Ambiguity stops for human disposition.

Auto mode cannot add or widen write paths, worktree custody, permissions, model/provider/route
families, credential slots, egress destinations or data classes, budgets, acceptance or terminal
criteria, authoritative gates, review independence, integration authority, destructive actions,
or outward effects. Credential or security-boundary change, foreign or ambiguous ownership,
corrupted evidence, new destructive or outward effect, publication/push/PR/merge/deployment,
authority expansion, and partial or unknown prior effect always stop. Those gates are
non-delegable even when the envelope predicts them.

Bounded auto mode is independent of Claude Code's native permission Auto mode, its background
classifier, the optional recursive-execution profile, OCX Ultracode, and `--yolo`. Enabling one
does not enable, approve, weaken, or configure another. In particular, AutoEnvelope approval never
changes host permissions or bypasses a permission prompt, while `--yolo` never expands the graph,
budgets, approval envelope, route admission, or hard-stop rules.

The operator may pause, narrow, or revoke the remaining envelope at any time. No configuration may
widen an active envelope without a new WavePlan, admission, PlanDiff, and human approval. Budget
exhaustion, expired validity, lost attribution, failed drift classification, or missing transition
receipt prevents new dispatch and leaves a truthful blocked or recovery state rather than falling
back to ordinary autonomous behavior.

### Pause, stop, emergency interruption, and resume

`pause` is a cooperative control operation, not a process-kill synonym. Once its durable request is
recorded, the conductor dispatches no new node and the wave becomes `pausing`. Active nodes are
asked to reach their declared safe checkpoint or terminal boundary, persist admitted artifacts,
and close their current effect observations. Read-only work may finish when that is the cheapest
safe boundary; an effectful node cannot be reported paused merely because output stopped.

The wave becomes `paused` only when no node is running and every attempted effect has a recorded
state and evidence reference. A paused wave may still carry a partial or unknown-effect blocker;
`paused` describes execution inactivity, not safety, success, or resumability. The pause receipt
names incomplete nodes, retained worktrees and artifacts, remaining budgets, last proven effects,
unknowns, and the exact checks required before resume.

`stop` prevents new dispatch and cooperatively settles active nodes in the same way, then closes
the wave with the evidence-supported `aborted`, `blocked`, `failed`, or `unknown-effect` outcome.
It does not delete artifacts, undo writes, remove worktrees, release foreign state, or invent
rollback. A terminal wave cannot resume; later work requires a new WavePlan revision or wave.

Forced interruption is a separately named emergency action with an explicit warning. It may end
local processes immediately, but it cannot prove that filesystem, provider, credential, network,
or other external effects stopped. Every interrupted effectful attempt becomes `unknown-effect`
unless independent post-interruption evidence closes it; process exit and code 130 are not
no-effect evidence. Unaffected durable artifacts remain preserved.

`resume` reconstructs execution from the MissionContract, latest admitted WavePlan revision,
PlanningSnapshot, effect journals, typed receipts, artifact digests, and queue references. It never
claims to restore lost model, agent, shell, or Claude Code in-memory context. Before any new
dispatch it takes a fresh PlanningSnapshot, runs drift classification and plan admission, verifies
approval and AutoEnvelope validity, rechecks custody and budgets, and resolves and admits every
RuntimeAssignment again.

An attempt repeats only when the prior evidence proves no effect or the exact approved retry policy
admits the observed terminal class. Resume never fills a missing artifact from conversation
memory, silently restarts an effectful node, renews an expired approval, or reuses stale runtime
identity. Changed semantics create a new PlanDiff and approval; partial/unknown effect or hard-stop
drift requires human disposition first.

No background daemon or login task automatically resumes a paused, interrupted, or blocked wave.
Budget or validity expiry, host restart, session loss, or route recovery leaves durable status for
an operator-triggered resume assessment; it does not turn inactivity into cancellation or grant
fresh authority.

### Release acceptance

The planning and bounded-auto release gate is deterministic and offline. Golden schema and
round-trip fixtures cover MissionContract, PlanningSnapshot, WavePlan, PlanDiff, AutoEnvelope,
admission and approval receipts, autonomous-transition receipts, pause evidence, and terminal
handoffs. Identical admitted inputs must compile to the same semantic plan and digest without a
model call; prose-only differences remain distinguishable from semantic changes.

Adversarial compiler and admission fixtures cover duplicate IDs, cycles, dangling references,
overlapping custody, unbounded effects or budgets, unsupported capabilities, missing or
contradictory evidence, stale or mismatched approvals, corrupted artifacts, unresolved routes,
partial/unknown prior effects, and every ambiguous drift case. Ambiguity fails closed. No-effect
tests prove planning, compilation, diff, drift classification, and admission do not mutate the
repository, queue, configuration, credentials, providers, trust, or external systems.

A closed transition matrix proves every autonomous dispatch, retry, reorder, decomposition,
read-only graph addition, and fallback stays inside the exact AutoEnvelope. Negative cases prove
that custody, permissions, routes, egress, budget, acceptance/gates, security, credentials,
destructive actions, and outward effects cannot widen through unused capacity, prose, recursion,
native permission Auto mode, Ultracode, or `--yolo`. Every admitted autonomous graph change has a
new PlanDiff and typed transition receipt.

Fault injection covers pause during read-only and effectful nodes, journal and receipt failure,
cooperative stop, forced interruption, host or session loss, stale route evidence, budget expiry,
and resume with changed repository, custody, approval, artifact, or effect state. Resume cannot
dispatch before a fresh snapshot, drift check, admission, approval/AutoEnvelope validation, and
RuntimeAssignment resolution. Version-pinned Claude Dynamic Workflow and supported-platform
canaries remain separate operational evidence for host claims, never ordinary offline gate
prerequisites.
