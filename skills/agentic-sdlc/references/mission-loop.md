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
