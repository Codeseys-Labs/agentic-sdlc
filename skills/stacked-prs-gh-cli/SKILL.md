---
name: stacked-prs-gh-cli
description: |
  Use when managing dependent GitHub pull requests with plain `gh` and git, especially when
  a parent changes or merges, a child must change base, a branch is being rewritten, or
  governance/check evidence is incomplete.
---

# Stacked PRs with plain `gh` + git

Use GitHub's explicit base-branch fields; `gh` has no stack command. Every outward mutation
requires operation-specific authorization and fresh readback. Missing governance data,
unsupported fields, or HTTP 403 is UNKNOWN, never approval.

## Create and record boundaries

```sh
git switch main && git switch -c feat-a
# commit A
git push -u origin feat-a
gh pr create --base main --head feat-a --title 'A'

git switch -c feat-b
# commit B
git push -u origin feat-b
gh pr create --base feat-a --head feat-b --title 'B'
```

Before each PR, save old boundaries: PR number, branch, base/head names, local tip, and
remote OID. Query `gh pr view <pr> --json baseRefName,headRefName,state,statusCheckRollup`
and record the exact result. A target/base/head/state drift invalidates the candidate; stop,
re-query, re-gate, and re-review.

## Parent merge, abandonment, or rename

Do not assume a forge changes a child base. After the parent operation:

1. Re-query the parent result and identify each **immediate child** from open PR data.
2. Explicitly retarget each immediate child, one at a time, with
   `gh pr edit <child-pr> --base <verified-replacement-base>`.
3. Re-query `baseRefName`, `headRefName`, and `state` for each child.
4. For a squash merge, save the old parent boundary and restack the child with
   `git rebase --onto origin/<new-base> <saved-parent-branch> <child-branch>` so only the
   child's commits replay. Cascade the restack through every descendant in top-down order.
5. Run required gates and obtain fresh review for every rewritten or retargeted PR. Do not
   merge or delete while any layer is stale.

A child still using a branch as its base keeps that branch alive. Before deletion, re-query
all open PRs and `baseRefName`; do not delete a branch while any open PR still uses it as a
base. If the query is incomplete, absent, unsupported, or returns HTTP 403, governance is
UNKNOWN and deletion stops. Perform a final race check immediately before deletion: re-read
open-child usage, PR base/head/state, remote OID, required checks, and governance.

## Restack and exact rewrite lease

For each rewritten branch, save its remote OID immediately before the rewrite, rebase, inspect
the diff, gate, and review. Push only with the exact saved-boundary lease:

```sh
git push --force-with-lease=refs/heads/<branch>:<saved-remote-oid> origin <branch>
```

Never use `--force`, an unqualified lease, or a stale saved OID. A lease failure or changed
readback is a stop: preserve evidence, re-query, and start a new authorized candidate.

## Verification checklist

- `gh pr view <pr> --json baseRefName,headRefName,state,statusCheckRollup` matches the saved
  boundary and intended new base.
- `gh pr checks <pr> --required` is interpreted with repository policy; no checks, absent
  evidence, unsupported governance fields, and HTTP 403 are UNKNOWN, not success.
- `gh pr diff <pr>` contains only the intended layer after restack.
- Every descendant is re-gated and re-reviewed after a parent rewrite or squash.
- The final race check passes immediately before any branch deletion.
