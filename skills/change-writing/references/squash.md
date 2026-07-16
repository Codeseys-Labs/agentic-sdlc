# Squash message

A squash message describes a branch's **final, user-meaningful delta** as a single logical change —
not its development diary.

## Synthesize the final delta, exclude the diary

- Describe the net effect of the branch against its base, as if authored in one commit.
- **Exclude** intermediate churn: "fix typo", "address review", "wip", reverted experiments, and
  commits that cancel each other out. The reader wants what the merged change does, not how it was
  developed.
- Keep the subject imperative and repo-native (see `commit.md` for prefix detection; Conventional
  Commits only as a fallback).
- The body explains motivation and consequences of the final state, drawn from the verified
  merge-base footprint, not a concatenation of the per-commit subjects.

This skill authors the squash **text** only. It never runs the squash, rebase, or merge — those
operations, and the base-branch topology around them, belong to the caller and to the stacked-PR
skills. Route claims through `evidence-order.md`; apply `attribution-policy.md`.
