# Mission Loop (backlog-zero operating doctrine)

Use this reference when the assignment is a MISSION ("drive the backlog to zero",
"reach the milestone", "keep going until done") rather than a single task. It extends
`references/sdlc-loop.md` with the autonomous-run discipline: classification, seeds-first,
WIP caps, priority math, and an honest definition of done.

## Mission framing

- The backlog (roadmap + tracker + Seeds) is the goal. **"Done" = zero unresolved
  MILESTONE-BLOCKING work — not zero possible future ideas.** Chasing literal-zero backlog
  is an anti-pattern; ideas are infinite.
- Start from the repo, not chat memory: read agent instructions (AGENTS.md/CLAUDE.md),
  roadmap/status docs, ADR index, tracker state, CI docs, latest commit. Reconstruct state;
  don't assume shared context.
- State assumptions and continue. Pause only when genuinely blocked or before an
  irreversible/destructive action.

## Classification (every item, every finding)

Every backlog item and every new discovery gets exactly one class. Classification and priority
are advisory conductor records, not execution authority:


`ACTIVE_MILESTONE` | `BLOCKED_CI` | `BLOCKED_DESIGN` | `BLOCKED_DEPENDENCY` |
`POST_MILESTONE` | `OUT_OF_SCOPE` | `DUPLICATE` | `INVALID`

Only `ACTIVE_MILESTONE` enters execution. Everything else is recorded durably WITH
rationale — never silently dropped, never silently executed.

Priority within the active queue: `(impact × severity × unblocks × confidence) / effort`.
Execute by milestone impact, not raw "ready" order.

## Seeds-first (the no-inline-fixes rule)

Discoveries NEVER get fixed inline. Return a seed-shaped recommendation first; the
macro conductor validates, classifies, and durably records accepted items:

```
{title, type, severity, blocking?, found_by, source, evidence, acceptance, class, rationale}
```

Then the conductor decides: blocking → the active queue at its priority; non-blocking →
classified + recorded. Workers and the critique team submit recommendations and never
mutate Seeds directly. The conductor is the sole queue writer. A finding that exists only
in an uncaptured response is lost work.

The conductor's durable write goes through the launcher's `record` mode, which admits
exactly two queue verbs and no others. It inherits every `inspect` admission — the same
active receipt, the same exact hashes, the same exact Bun entry, the same allowlisted child
environment — and adds two conditions. First, compare-and-swap: the conductor names the
exact queue sha256 it classified against, and a queue that moved since then is refused with
both digests named rather than silently overwriting a concurrent write. Second, readback:
after the write the launcher re-reads the queue and verifies the observed post-state equals
the prestate plus exactly the requested delta — nothing else added, removed, reordered, or
edited — and refuses while naming what diverged. The seam also requires the sole-writer
acknowledgement `--queue-writer conductor`, so a role agent reaching for it casually is
refused rather than quietly promoted. The underlying queue's own lock stays the queue
writer's; this seam adds none. A verified record is the conductor's own evidence and still
authorizes no push, PR, merge, deployment, or other outward effect.

## WIP caps (bound the fan-out)

| Track | Cap |
|---|---|
| Implementation workers | ≤ 3 |
| Research tracks | ≤ 2 |
| Integration/reconcile | ≤ 1 |
| Critique/review team | ≤ 1 |
| Delegation nesting depth | ≤ 2 |

When WIP is full: do NOT start new work — swarm the oldest blocked or nearest-done item.
On merge conflict between workers: sequence and re-plan, don't fight it in parallel.

## The concurrent critique team

Run ONE provider-native background review agent or team in parallel with execution. This remains a provider-native review session. It
audits **stable snapshots** (the squash-merged commit of
each wave), never live worktrees. It returns classified seed-shaped recommendations in
real time; the conductor decides which blocking findings re-enter the active queue and
persists the rest. Critique lenses:
correctness, regression, security/secrets, edge cases, tests, docs, CI/workflow changes,
platform-claim evidence, tracker/ADR hygiene.

## Non-negotiables (mission-wide)

- No force-push / history rewrite on shared branches. No touching secrets or committing
  credentials. No CI/release mutation from a dirty checkout unless isolated + approved.
- No closing multi-platform work from single-platform evidence (CI is the authority;
  cross-platform claims need cross-platform runs or an explicit recorded waiver).
- No chat-only TODOs — tracker/Seeds or it didn't happen.
- No closing anything without acceptance evidence (gates run, output pasted).
- No unbounded scope: new findings are triaged, not auto-executed.

## Drift classes (the four-outcome doctrine)

This section is the single canonical definition of plan drift for the mission loop. Drift is any
observed difference between current state and a load-bearing commitment the mission runs under —
a sealed MissionContract field, an approval invariant, worktree custody, an authoritative gate
verdict, or queue state. `tools/mission-contract.py` makes `hard-stop-drift` one of the four
non-waivable stop conditions in every sealed contract; this table is what that token means.
ADR-0025 and issue 16 originated these rules and are cited as history only; the operative
definition is this one.

| Class | Meaning | Mission response |
|---|---|---|
| `compatible` | The change is unrelated or explicitly tolerated, and every affected invariant still holds. | Continue; record the observation. |
| `revalidation-required` | Plan semantics are unchanged, but a freshness, identity, capability, or admission fact must be renewed — an approval's validity, a model readback, the queue digest the conductor classified against. | Renew the named fact and continue only when it renews cleanly; otherwise escalate one class. |
| `replan-required` | A plan-bound fact changed: the workstream set or its ordering, declared constraints or budgets, retries, route constraints, custody boundaries, declared egress, gates or policies, required artifacts, terminal criteria. | Stop the affected work and produce a new plan revision for approval; never edit the approved plan in place. |
| `hard-stop` | Continuation would cross an authority, ownership, security, credential, destructive/outward-effect, or unknown-effect boundary. | Stop and return to a human with the blocker named. This class is the contract's non-waivable `hard-stop-drift` stop condition. |

Rules over the classes:

- **Severity is a max-fold** over the semantic order `compatible < revalidation-required <
  replan-required < hard-stop` (deliberately not the alphabetical order of the same strings).
  The outcome for a set of observed changes is the maximum severity among them: one hard-stop
  among a hundred compatible changes is a hard-stop.
- **Ambiguous classification is `hard-stop`, never `compatible`.** A change the conductor cannot
  interpret unambiguously — an unknown change kind, a subject the mission does not name, an
  observation about some other plan — is classified hard-stop rather than tolerated.
- **No downgrade.** No acknowledgement, retry, old approval, or unaffected gate downgrades a
  stop. An approval invalidated by drift is renewed by a human, never by re-reading it.
- **Drift never repairs.** Detection never resets, rebases, checks out, stashes, overwrites,
  removes, reauthenticates, reroutes, or rewrites a queue. The classification is evidence; the
  response is a separate bounded decision.
- **Scope and authority drift always routes to a human.** It is never reclassified downward,
  whatever else in the observed set is compatible; the contract carries it as the non-waivable
  `scope-change-required` and `authority-expansion-required` stop conditions.

Change kinds that always stop, named against what exists at HEAD: a change to any sealed
MissionContract field (objective, scope and non-goals, constraints, authority classes or ceiling,
completion contract, stop conditions) is at minimum `replan-required`, and `hard-stop` when it
expands authority or scope; an approval invariant no longer holding is `revalidation-required`
until renewed; a worktree custody conflict, an authoritative gate verdict flipping under the
mission, or the queue moving away from the digest the conductor classified against each stop the
affected work before the next wave is planned.

## The wave loop

```
reconstruct state → audit+classify queue → research (only load-bearing unknowns)
→ plan wave → execute in worktrees → critique snapshot (concurrent)
→ reconcile: merge/discard, close-with-evidence, fold in seeds, re-prioritize
→ next wave
```

Termination: a full wave yields zero new BLOCKING seeds AND the critique team confirms
nothing open — or a wave/pass cap trips. **Hitting a cap without done is an honest stop,
not a failure**: report exact remaining blockers + resume hints; never claim completion.

## Item / mission "done"

Item done = acceptance criteria pass + gates green (or waiver recorded) + docs/tracker
updated + stable snapshot + no blocking critique finding.

Mission done = zero `ACTIVE_MILESTONE` remaining + all blockers passed/waived/reclassified
+ critique reports zero blocking + tracker clean + a final checkpoint recording evidence,
remaining non-blocking backlog, and assumptions.

## Anti-patterns

Infinite zero-backlog chasing · broad dirty branches · overlapping worker write scopes ·
vague worker prompts (see the native delegation contract in
`references/delegation-planes.md`) · implementing from partial research · toolchain churn (respect
the repo's mise/uv/bun choices; changing toolchains needs an ADR) · local-only proof for
platform claims · review findings that never become Seeds.
