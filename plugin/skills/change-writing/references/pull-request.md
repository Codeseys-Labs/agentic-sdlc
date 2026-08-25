# Pull-request title and body

A PR describes the whole change a reviewer will merge, scoped to the branch's real footprint.

## Scope: the merge-base footprint, not the HEAD diff

Describe the cumulative delta between the branch and the base branch — the **merge-base footprint**,
**not the HEAD diff** of the last commit and not the raw range that includes commits already on the
base. This matches the fan-in discipline in `../agentic-sdlc/references/worktree-integration.md`:
what the PR proposes to add to the base is the merge-base-to-tip diff, computed against the base's
current tip.

## Title

- One line summarizing the change's effect, following the repository's PR-title convention when one
  is detectable (see `commit.md` for prefix detection); Conventional Commits is only a fallback.

## Body sections

Prefer the repository's PR template when it ships one. Absent a template, a concise default:

- `## Summary` — what changes and why, from the verified diff and stated motivation.
- `## Verification` — only gates and tests the caller actually ran, quoted or referenced concretely.
  No verification evidence → omit the section or leave a `TODO:` placeholder; never claim untested
  passing.
- `## Risks and recovery` — known risks and how to back the change out, when there are real ones;
  omit rather than invent.

Never invent linked issues, reviewers, breaking changes, or user impact. Route every claim through
`evidence-order.md`. Attribution follows `attribution-policy.md`.
