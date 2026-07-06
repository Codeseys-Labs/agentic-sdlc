---
name: stacked-prs
description: |
  Stacked pull requests — the tool-agnostic methodology for shipping a chain of small,
  dependent PRs instead of one fat branch. Use when: (1) a change is growing into a large
  multi-concern PR and review is stalling ("this PR is too big", "reviewer fatigue");
  (2) later work depends on earlier unmerged work and you don't want to wait for the first
  to merge; (3) an agentic wave produced several dependent commits that should land as
  separate reviewable units; (4) deciding stack-vs-parallel-PRs (dependent → stack;
  independent → parallel); (5) a lower PR in a stack got review changes and you must
  propagate them up. Covers the small-batch/anti-fat-branch rationale, stack structure,
  bottom-up merge order, the restack discipline, and when NOT to stack. Tool mechanics
  live in sibling skills (stacked-prs-gh-cli) and the jj-vcs reference.
author: Claude Code
version: 1.0.0
date: 2026-07-06
---

# Stacked Pull Requests (methodology)

## Problem: the fat branch

The default habit is one long-lived branch that accumulates a whole feature, then opens as
one giant PR. It fails predictably:

- **Review stalls.** A 1,500-line PR gets rubber-stamped or sits for days. Reviewer
  attention is roughly constant per PR, not per line — so quality drops as size grows.
- **Serial blocking.** Everything in the branch waits on the slowest-to-review part.
- **Merge conflicts compound** the longer the branch diverges from main.
- **Hard to revert / bisect.** One commit (or one squash) mixes unrelated concerns.
- **Feedback is expensive.** A design change near the base forces reworking everything
  layered on top, by hand.

Small batches are the fix — but "just open small PRs" breaks when the pieces DEPEND on each
other. Stacking is how you keep batches small *without* waiting for each to merge first.

## What a stack is

A chain of PRs where each one's base branch is the branch below it, each carrying ONE
logical change:

```
main  ←  feat-a (PR #1, base: main)
          └─ feat-b (PR #2, base: feat-a)
              └─ feat-c (PR #3, base: feat-b)
```

Each PR is independently reviewable; a reviewer sees only that layer's diff, not the whole
feature. Work proceeds on `feat-c` while `feat-a` is still in review.

## The rules

1. **One logical change per PR.** If you can't summarize a PR in one sentence without
   "and", split it. This is the golden rule everything else serves.
2. **Base each PR on the one below**, not on main. That's what makes the diff show only
   the new layer.
3. **Merge bottom-up.** `#1` merges first, then `#2`, then `#3`. Never merge a child before
   its parent.
4. **Changes to a lower PR propagate upward by restacking.** Review feedback lands on
   `feat-a` → amend `feat-a` → rebase `feat-b` (and its descendants) onto the new
   `feat-a` → force-push (with lease). Every tool and the raw-git flow is a variation of
   this one move. See the `stacked-prs-gh-cli` skill (raw gh/git) and the flagship skill's
   jj-vcs reference (jj auto-rebases descendants — restacking is free).
5. **Keep the stack shallow.** 2–4 PRs is the sweet spot. Beyond ~5, restack churn and
   reviewer context-switching cost more than the batching saves — split into sequential
   stacks landed as you go.

## When NOT to stack

- **Independent changes → parallel PRs, not a stack.** If B doesn't need A, base both on
  main and review concurrently. Stacking independent work invents a false dependency and
  serializes the merge.
- **A single atomic change** (a change that is only correct as a whole — e.g. a rename that
  must touch caller and callee together) is ONE PR, not a stack.
- **Reviewers can't follow the split.** If layering makes each PR incomprehensible without
  the others, the boundaries are wrong — re-cut them along genuine logical seams.

## How it wires into agentic waves

The bundle's worktree/workspace waves already produce disjoint-scope commits (see the
flagship skill's seeds-worktrees reference). Stacking is the PR-landing strategy for the
DEPENDENT case: when Seed B builds on Seed A, land them as a stack (A's PR base main, B's base A)
rather than one merged mega-branch or a blocked-until-A-merges wait. Independent Seeds in
the same wave land as parallel PRs. The integrator (see the `sdlc-integrator` agent) merges
bottom-up and re-gates each layer on its actual base.

## Verification

A healthy stack: each PR's diff is small and single-purpose; `#N`'s base is `#N-1`'s branch;
merging `#1` leaves `#2` still reviewable (auto-retargeted to main — see stacked-prs-gh-cli);
reverting any single PR is meaningful in isolation.

## References

- `stacked-prs-gh-cli` skill — the raw `gh` + git mechanics (no native stack command; the
  squash-merge rebase-onto gotcha; native auto-retargeting).
- flagship `agentic-sdlc-orchestrator` skill, jj-vcs reference — jj's change model
  makes stacks first-class (auto-rebase descendants).
- Graphite's stacked-diffs guides (graphite.com/guides) — the methodology's popular
  reference; tool-specific but the principles are general.
