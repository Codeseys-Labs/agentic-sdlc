---
name: stacked-prs-gh-cli
description: |
  Create and manage stacked pull requests with ONLY the plain `gh` CLI + git — no
  Graphite/gt/spr/ghstack. Use when: (1) you want a stack of dependent PRs on GitHub and
  have gh but no stacking tool; (2) building each PR on the branch below via
  `gh pr create --base <parent-branch>`; (3) a lower PR got review changes and you must
  rebase + force-push the whole stack; (4) the base PR MERGED and you need to know what
  GitHub retargets automatically vs by hand; (5) confused why `gh pr` has no `stack`
  subcommand ("GitHub supports stacked PRs" — the platform primitive is base-targeting +
  auto-retarget, NOT a gh command). Covers: gh has NO native stack command (v2.95),
  --base per PR, native auto-retarget-on-merge, the squash-merge restack gotcha,
  --force-with-lease safety, gh pr edit --base manual retarget.
author: Claude Code
version: 1.0.0
date: 2026-07-06
---

# Stacked PRs with raw `gh` CLI + git

Methodology and when-to-stack live in the sibling `stacked-prs` skill (see it for the
*why*, structure, and when NOT to stack). This skill is the mechanics with no extra tooling.

## First, the fact that trips everyone

**`gh` has NO `stack` subcommand** (verified gh 2.95.0, 2026-06). "GitHub supports stacked
PRs" is half-true and worth being precise about — GitHub provides two *primitives*, not a
workflow:

1. **Arbitrary base branch:** any PR can target any branch as its base
   (`gh pr create --base <branch>` / `gh pr edit --base <branch>`). That's how you express
   a stack.
2. **Auto-retarget on merge:** when a base branch is merged (and deleted), GitHub
   automatically retargets any open PR that pointed at it to *that branch's* base — so a
   child PR moves up to the grandparent (usually `main`) with no action. Stable GitHub
   behavior since 2020.

Everything else — rebasing the stack after a lower change, keeping child branches current —
is manual. That manual overhead is the entire reason Graphite/gt/spr/jj exist.

## Create a stack

```sh
git switch main && git switch -c feat-a
# … commit layer A …
git push -u origin feat-a
gh pr create --base main --head feat-a --title "A: …"

git switch -c feat-b            # branches OFF feat-a
# … commit layer B …
git push -u origin feat-b
gh pr create --base feat-a --head feat-b --title "B: …"   # base = the branch below

git switch -c feat-c
# … commit layer C …
git push -u origin feat-c
gh pr create --base feat-b --head feat-c --title "C: …"
```

Each PR's diff shows only its own layer, because the base is the branch below — not main.
Add a stack map to each PR body (`gh pr create --body "Stack: #1 ← #2(this) ← #3"`) so
reviewers see the order; gh does not render stacks.

## Review feedback on a lower PR → restack (the core loop)

Feedback lands on `feat-a`. Amend it, then cascade the rebase upward:

```sh
git switch feat-a
# … apply the fix, commit (or amend) …
git push --force-with-lease origin feat-a         # PR #1 updates

git switch feat-b
git rebase feat-a                                 # replay B on the new A
git push --force-with-lease origin feat-b

git switch feat-c
git rebase feat-b
git push --force-with-lease origin feat-c
```

- **Always `--force-with-lease`, never `--force`** — lease aborts if someone else pushed to
  the branch, so you don't clobber a collaborator (or another agent) blindly.
- `git rebase --update-refs` (git ≥ 2.38) can rebase a whole stack held as branches on one
  local line in a single command — but you still force-push each branch. Know your git
  version before relying on it.

## The squash-merge gotcha (the one that corrupts stacks)

The default GitHub merge is **squash**. When `feat-a` squash-merges, main gets ONE new
commit whose hash/content does NOT match any commit on `feat-a`. Now `feat-b` still contains
A's original (pre-squash) commits. If you naively `git rebase main feat-b`, git tries to
replay A's commits that are "already" in main-as-a-squash and you get spurious conflicts or
duplicated changes.

Fix — after the base PR squash-merges, rebase the child ONTO main while DROPPING the old
base commits:

```sh
git fetch origin
git switch feat-b
git rebase --onto origin/main feat-a feat-b       # replay ONLY B's commits onto main
git push --force-with-lease origin feat-b
# GitHub already auto-retargeted PR #2's base main -> confirm with: gh pr view feat-b --json baseRefName
```

`--onto origin/main feat-a feat-b` = "take the commits that are on feat-b but not on feat-a,
and replay them onto origin/main." That skips A's now-squashed commits cleanly. Repeat per
layer as each merges. (Merge-commit or rebase-merge strategies avoid this specific trap but
have their own; squash is the GitHub default, so assume it.)

## Merge order

Bottom-up, always: merge `#1`, let GitHub auto-retarget `#2` to main, restack `#2` onto main
(squash gotcha above), merge `#2`, and so on. Never merge a child before its parent — its
diff would include the parent's unmerged changes.

## Manual retarget (when auto-retarget doesn't fire)

Auto-retarget needs the base branch to be *merged*. If you abandon or rename a base branch,
retarget children by hand:

```sh
gh pr edit <child-pr> --base main
```

## Agentic-wave note

One worktree/workspace per stack layer; commit per layer; the conductor (or `sdlc-integrator`)
opens PRs with `--base` pointing down the stack, then merges bottom-up and re-gates each
layer on its real base (the flagship skill's worktree-integration reference — worktree-green
≠ base-green). If the repo is on jj, skip most of this: `jj` auto-rebases descendants, so
restacking after a lower change is automatic — see the flagship skill's jj-vcs reference.

## Verification

- `gh pr view <child> --json baseRefName` shows the base is the layer below (not main) while
  stacked, and flips to `main` automatically after the parent merges.
- After a restack, `gh pr diff <child>` shows only that layer's changes, no duplicated
  parent hunks (if you see duplicates, you hit the squash gotcha — use `--onto`).

## References

- sibling `stacked-prs` skill — methodology, when-to-stack, anti-fat-branch rationale.
- flagship `agentic-sdlc-orchestrator` skill, jj-vcs reference — jj makes restacking free.
- GitHub auto-retarget: github.blog changelog (2020) "automatically changing base branch".
