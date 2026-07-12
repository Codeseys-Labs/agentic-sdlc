---
name: stacked-prs
description: |
  Use when dependent changes need separate, reviewable pull requests and a lower layer
  changes, merges, is retargeted, or is restacked while descendants remain open.
---

# Stacked pull requests

A stack is a chain of small, dependent PRs. Each PR has one logical change and targets the
branch immediately below it. Independent changes are parallel PRs, not a stack. Merge and
restack bottom-up; a child is not ready merely because its parent changed.

## Safety doctrine

- Save **old boundaries** before any rewrite: branch name, local tip, base, head, PR number,
  and saved remote OID. A candidate becomes invalid if the target/base/head or PR state drifts;
  stop, re-query, and re-gate. target drift invalidates the candidate.
- Never rely on a platform retargeting a PR. After a parent merges, is abandoned, or is
  renamed, explicitly retarget each immediate child to the verified replacement base.
- After each retarget, re-query `baseRefName`, `headRefName`, and PR `state`; then cascade the
  restack through every descendant in top-down order. Re-gate and re-review every rewritten
  PR. A squash merge requires dropping the old parent range (for example, `git rebase
  --onto origin/main <saved-parent-branch> <child>`), not replaying it.
- Before deleting any branch, re-query all open PRs and their `baseRefName`. Do not delete a branch while any open PR still uses it as a base. If evidence is absent, stale, or HTTP
  403, governance is UNKNOWN: do not treat UNKNOWN as approval.
- Take a final race check immediately before every deletion or rewrite: re-read remote OID,
  PR base/head/state, open-child usage, required checks, and governance. Any changed value
  invalidates the candidate and requires a fresh boundary and review.

## Normal shape

```
main <- feat-a (PR 1) <- feat-b (PR 2) <- feat-c (PR 3)
```

Create each PR against the immediate parent. Keep the stack shallow (usually 2–4 layers),
keep a stack map in each PR, and merge only bottom-up. A child PR remains open while its
parent is reviewed; that is not permission to remove the parent branch.

## Rewrite discipline

For every rewritten branch, save its current remote OID, perform the rebase, inspect the
result, run the required gates, obtain fresh review, and update the saved boundary. Push only
with the exact lease form:

```sh
git push --force-with-lease=refs/heads/<branch>:<saved-remote-oid> origin <branch>
```

Never substitute an unqualified lease or `--force`. A lease failure is a stop, not a retry.
