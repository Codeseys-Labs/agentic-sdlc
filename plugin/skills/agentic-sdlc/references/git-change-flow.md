# Git change-flow router

Use this reference when any question about worktree/stacked-PR change flow arises — as a
cartographer, implementer, integrator, or reviewer. It is a **dispatch table only**: it names the
one authoritative site for each rule and sends you there in a single hop. It contains **no doctrine
of its own** and no command strings; re-teaching a rule here would fork a second copy that drifts.

**Base:** written against the post-rename flagship path `skills/agentic-sdlc/` (the Wave-2 identity
cutover renamed the flagship skill directory). This router consumes that rename result and names
only post-rename paths; every path below is under `skills/agentic-sdlc/`, `skills/stacked-prs/`, or
`skills/stacked-prs-gh-cli/`.

## Two skills, one split — both are load-bearing, keep both

- `skills/stacked-prs/SKILL.md` — the topology and safety **methodology** (forge-agnostic): stack
  shape, one-writer-per-layer, boundary snapshots, restack cascade, leases, governance-UNKNOWN.
- `skills/stacked-prs-gh-cli/SKILL.md` — the same doctrine expressed in raw `gh` + `git`
  **mechanics**: `gh pr create/edit/view --json`, `gh pr checks --required`, `gh pr diff`, the
  restack-lease sequence, and a verification checklist.

The safety-doctrine sentences are duplicated across the two skills **deliberately**. That
duplication is conformance-required: `tests/test_pr_safety_doctrine.py` iterates BOTH skills and
asserts EACH independently carries the full doctrine, so neither may be demoted to a compat alias
of the other (the gh-cli skill has proven independent trigger value — see
`test_pr_safety_doctrine.py`). Do not merge them; do not delete either `SKILL.md`.

## Dispatch table — situation → authoritative site

Each row names the single site that OWNS the rule. Read the rule there; do not restate it elsewhere.

| Change-flow rule | Authoritative site |
|---|---|
| One-writer ownership per layer/branch | `skills/stacked-prs/SKILL.md` § Stacked pull requests (intro + Normal shape) |
| Worktree substrate (in-workspace `.worktrees/<seed-id>-<slug>/`, never a sibling) | `skills/agentic-sdlc/references/seeds-worktrees.md` § Worktree substrate |
| Worktree lifecycle steps + per-step refusal/recovery (create, gate, review, integrate, reconcile, clean up) | `skills/agentic-sdlc/references/worktree-lifecycle.md` |
| Boundary snapshot (branch, tip, PR#, base/head, remote OID) | `skills/stacked-prs/SKILL.md` § Safety doctrine; mechanics form in `skills/stacked-prs-gh-cli/SKILL.md` § Create and record boundaries |
| Recovery refs / pre-op tags (pre-squash tag, reset to prev-main) | `skills/agentic-sdlc/references/worktree-integration.md` § Hazard 3 + § Squash-scope discipline |
| Rebase boundary (replays only the child) | `skills/stacked-prs/SKILL.md` § Safety doctrine; mechanics in `skills/stacked-prs-gh-cli/SKILL.md` § Parent merge, abandonment, or rename |
| Squash scope (merge-base→tip delta, count before squash) | `skills/agentic-sdlc/references/worktree-integration.md` § Squash-scope discipline |
| Clean-apply is not semantic correctness | `skills/agentic-sdlc/references/worktree-integration.md` § Hazard 4 |
| Merge-base footprint (validate vs merge-base, not the other HEAD) | `skills/agentic-sdlc/references/worktree-integration.md` § Hazard 1 |
| Stack topology + restacking cascade (bottom-up, old/new-parent maps) | `skills/stacked-prs/SKILL.md` § Safety doctrine; mechanics in `skills/stacked-prs-gh-cli/SKILL.md` § Restack and exact rewrite lease |
| Exact remote-OID lease (never plain force, never unqualified lease) | `skills/stacked-prs/SKILL.md` § Safety doctrine + § Rewrite discipline; mechanics in `skills/stacked-prs-gh-cli/SKILL.md` § Restack and exact rewrite lease |
| Child-PR deletion check (re-query all open PR bases; UNKNOWN is not approval) | `skills/stacked-prs/SKILL.md` § Safety doctrine; mechanics in `skills/stacked-prs-gh-cli/SKILL.md` § Parent merge, abandonment, or rename |
| Re-gating / fresh review after any rewrite or retarget | `skills/stacked-prs/SKILL.md` § Safety doctrine; re-gate ON MAIN in `skills/agentic-sdlc/references/worktree-integration.md` § Hazard 3 |
| Final race check immediately before every mutation | `skills/stacked-prs/SKILL.md` § Safety doctrine; mechanics in `skills/stacked-prs-gh-cli/SKILL.md` § Restack and exact rewrite lease + § Verification checklist |

## Effect-idempotency cross-reference

A killed worker whose outward effect (a `git push`, PR create/comment, or Seeds sync) may already
have landed must **reconcile the outward target** — the merge-base, the commit SHA, and the PR
state — before any retry. A journal or local-success record is not proof the effect did NOT land;
`skills/agentic-sdlc/references/seeds-worktrees.md` § Seeds Queue states that a verified local
result still does not authorize an outward effect. The mechanism is the final-race-check invariant
above (re-read the saved OID / PR state / open-child / checks / governance before acting), not a new
ledger.

## Never-force invariant

Deletion and rewrite pushes use the exact saved-OID lease documented at the authoritative sites
above. Plain `git push --force` and unqualified leases are forbidden by the doctrine; this router
never introduces force-push language, and `tests/test_pr_safety_doctrine.py` guards the skills that
own the lease commands.
