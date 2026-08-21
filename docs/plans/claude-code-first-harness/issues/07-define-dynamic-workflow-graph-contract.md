# Define the Dynamic Workflow execution and graph contract

Type: grilling
Status: resolved
Blocked by: 01, 02, 06
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What execution contract turns Claude Code Dynamic Workflows into this harness's primary engine?
Set the graph-engineering vocabulary, decomposition boundary, model and effort routing, worker and
review roles, state and artifact handoffs, concurrency and nesting limits, retry and stop rules,
human gates, and the evidence required to call a workflow result complete.

## Answer

### Graph boundary and vocabulary

One Dynamic Workflow execution represents one bounded **wave**, not an entire mission. A mission
is the durable objective across waves; a wave is one reviewed execution DAG with a terminal
condition; a workstream is an independently owned scope; a node is one bounded agent task with
declared inputs, outputs, runtime assignment, authority, and stop rule; an edge is an artifact or
verdict dependency; a gate is an automated admission check or human approval; a receipt records
what ran and what it produced; and a Seed carries durable follow-up beyond the wave.

### Roles, authority, and routing

The main Claude Code session is the conductor. It owns the mission, presents the wave graph,
obtains approvals, and records the final verdict. Cartographers, researchers, and planners are
read-only advisory nodes. Implementers own isolated workstreams and worktrees. Reviewers inspect
immutable workstream results and never repair them. One already-authorized integrator performs
fan-in after accepted reviews. A critic audits the integrated snapshot and files findings rather
than editing it. The workflow executes only the approved graph; scripts and workers cannot widen
authority or impersonate human approval.

Every executable node requires a resolved `RuntimeAssignment` before spawn. Semantic task tier
and exact provider/model ID remain separate facts. The exact model, effort, and context request is
injected; routed nodes require current qualification; and effective route identity is verified
afterward. Roles have no permanent provider preference or hidden model pin. An unresolved or
uninjectable assignment stops before spawn and becomes a Seed proposal.

`/sdlc-rightsize` supplies a versioned advisory model-task map to graph compilation. The map
records task buckets and capability requirements; exact provider/model/effort/context
recommendations; qualification evidence; cost, quota, latency, tool, and context constraints;
confidence; qualified fallbacks; and observed-versus-inferred facts. Discovery and planning are
read-only. Active evaluation requires explicit authorization. The map informs the conductor but
never replaces exact per-node resolution.

### State, continuation, and graph expansion

Nodes exchange declared, schema-validated artifacts and verdicts rather than hidden conversation
context. A wave journal records each node's inputs, outputs, assignment, timestamps, result, and
evidence. Work products remain in isolated worktrees; advisory artifacts remain in the mission
workspace. A downstream node starts only after dependency artifacts pass admission.

In-session state may resume only within Claude Code's supported boundary. Cross-session
continuation reconstructs a new wave from durable artifacts and Seeds; it never claims to resume
lost in-memory execution.

The default mode runs a reviewed static DAG with recursive spawning disabled. An optional
first-party recursive-execution profile works under ordinary `claude` or `ccodex`; it is not a
multi-provider feature. It is version-gated by a nesting canary because Claude Code documents
generic subagent nesting but not a separate Dynamic Workflow nesting guarantee. The operator
preapproves scope, authority, depth, node, time, cost, and retry budgets. Children inherit narrower
permissions and remaining budgets. Recursive investigation, diagnosis, research, planning, and
conditional execution may continue only inside that envelope; anything else becomes a Seed.

Execution limits are configurable policy, not immutable constants. Agentic SDLC ships defaults of
four concurrent nodes, 64 total nodes per wave, and recursion off; the recursive child generation
cap is raisable. Users may set a global execution profile, and repositories may narrow or
explicitly override it. Each wave records its effective limits before approval. `ccodex` applies
the same policy and may lower it for provider, quota, or transport constraints. No configuration
may exceed capabilities verified for the active Claude Code version, and unbounded execution is
invalid. Recursive execution remains separately default-off even when numeric limits are raised.

### Retry, planning, and approval

Read-only nodes may retry transient failures within their declared budgets. Write-capable nodes
may retry only when evidence proves the prior attempt had no effect; an unknown effect stops the
workstream. Route mismatch, missing evidence, failed admission, authority expansion, repository
drift, conflict, or exhausted budget stops the affected branch. Independent branches continue
only when the approved graph says they remain valid. Resumption rechecks inputs, repository state,
route qualification, and remaining authority.

A first-class read-only planning workflow may use planner, cartographer, researcher, and critic
nodes to produce a versioned wave graph. Drift correction compares the mission, prior plan,
repository state, and retained artifacts, then emits a visible plan diff and re-admits the graph.
By default, a human approves every new or materially revised plan.

Optional bounded auto mode requires the user to preapprove scope, authority, routes, budgets,
permitted plan changes, and stop conditions. It may replan and proceed only inside that envelope.
Repository drift, new outward effects, credential changes, destructive actions, security-boundary
changes, or expanded authority always stop for human approval. Auto mode is traceable and is
never permission bypass or YOLO mode.

Before wave launch, the user approves the objective, graph, authority, routes, egress, budgets,
fallbacks, and limits. Fan-in requires accepted workstream reviews and integrator authority in the
approved plan. Push, PR mutation, merge, deployment, credential change, publication, or another
outward effect always requires separate operation-specific approval. A gate is evidence, not an
authority grant.

### Completion and adversarial review

A wave is complete only when every required node has an admitted success, approved skip, or
explicit blocked disposition; runtime receipts contain no unexplained substitution; declared
artifacts validate and match the recorded repository state; workstream reviews are accepted;
fan-in was authorized; the admitted gate contract passes on the integrated snapshot; budgets,
retries, plan revisions, and approvals are traceable; and the conductor records the verdict. A
normal delivery wave requires the authoritative repository gate to pass. A remediation-progress
wave instead requires its focused gates to pass and the exact global failure baseline not to
worsen; it ends as `remediation-progress`, not `repository gate-passing` or write-ready. Workflow-process
completion alone is not a product-success verdict.

An adversarial critic classifies completion blockers separately from future improvement.
Acceptance-criteria violations, safety regressions, corrupted evidence, and failed authoritative
gates block completion and require a newly reviewed remediation workstream. Non-blocking
complexity, maintainability, documentation, and enhancement findings become prioritized Seeds.
Every finding carries severity, evidence, affected artifact, recommended disposition, and
rationale. The critic advises; the conductor owns classification and verdict. A wave may complete
with future Seeds but never with unresolved blocking findings.
