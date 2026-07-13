# Seeds, Worktrees, and PR Flow

Use this reference when converting the plan into parallel implementation work.

## Seeds Queue

Use Seeds as the authoritative dynamic queue for recommendations and acceptance tracking;
they are not an authorization or execution channel:

```bash
sd prime
sd ready --format json
sd blocked --format json
```

Create or update Seeds for:

- Original requested work.
- Discovered bugs.
- Review findings.
- Missing tests/docs.
- Blockers that need human approval or external credentials.

Do not close a Seed from an agent message, reviewer label, gate status, or conductor choice alone.
Verify current files, gates, and acceptance criteria; a verified local result still does not
authorize an outward effect.

## Wave Selection

Choose a wave from ready Seeds:

- Prefer independent Seeds with disjoint file ownership.
- Keep broad architecture, CI, generated code, and shared contract changes separate.
- If the main checkout is dirty, only inspect it or do narrow safe work there. Use clean worktrees for write-capable workers.
- Cap parallel worktrees based on repo risk and machine capacity. Three to five is usually enough.

## Worktree Pattern

Recommended branch naming:

```bash
git worktree add ../<repo>-wt-<seed-id> -b work/<seed-id>-<slug>
```

Worker prompt must include:

- Seed id and acceptance criteria.
- Worktree absolute path.
- Files/directories in scope.
- Commands to run.
- Explicit instruction to avoid unrelated changes.
- Artifact path for the worker report.

After worker completion:

1. Inspect `git status --short` and `git diff`.
2. Run targeted gates in the worktree.
3. Commit the worktree branch if accepted.
4. Rebase onto the integration branch.
5. Squash merge or cherry-pick into the integration branch according to repo policy.

## PR Flow

Before opening a PR:

- Run final gates from the integration branch.
- Run `sd sync` if Seeds changed.
- Confirm the integration branch diff matches the intended Seeds.
- Include Seeds ids and test evidence in the PR body.
- Confirm explicit operation-specific authorization for PR creation or mutation; gates,
  status, and recommendations do not grant it.

Do not force-push or rewrite shared branches without explicit user approval.

**Dependent Seeds → stacked PRs, not one fat branch.** When Seed B builds on Seed A, land
them as a stack (A's PR base main, B's base A, merge bottom-up) rather than merging both
into one mega-branch or blocking B until A merges. Independent Seeds in the same wave land
as parallel PRs. Mechanics: the `stacked-prs` skill (methodology) and `stacked-prs-gh-cli`
(raw gh/git, incl. the squash-merge restack gotcha).

## Config propagation into new worktrees

`git worktree add` copies TRACKED files only. Untracked project config that workers may
depend on does NOT follow:

- `.claude/settings.local.json` (permission allowlists, hooks) — absent in the worktree;
  workers fall back to user-level settings. Copy it in if the wave needs project hooks.
- `.mcp.json` — if gitignored, worker sessions in the worktree see NO project MCP servers.
  Copy or symlink it into each worktree when workers need those servers.
- Codex per-path dir-trust — trust is keyed on the absolute path; every NEW worktree path
  must be added to `~/.codex/config.toml` (`projects.'<path>'.trust_level='trusted'`) or
  codex workers hang on the trust prompt. Batch-add when creating the wave.
- mise per-path trust — same pattern: a fresh worktree is untrusted even when the main repo
  is trusted, so git hooks (which ARE shared from the main repo's gitdir) fail on any
  mise-shimmed command with "config not trusted". Run `mise trust <worktree-path>` per
  worktree. Missing, unpinned, untrusted, or ambiguous required capability fails closed;
  do not let workers bypass the repository gate. Full gate stack:
  `skills/repo-toolchain-gates/`.

Wave-creation checklist: create worktree → copy untracked config the workers need →
trust the path for codex AND mise → then launch.

## Worker substrates and optional viewers

- Launch provider-native workers by default after capability and trust probes pass. Give every
  write-capable worker one worktree, its absolute path, and an artifact report path. Never
  share a write worktree.
- Codex workers on any substrate need each new worktree path trusted in
  `~/.codex/config.toml`; batch-add trust entries when creating the wave.
- When cmux is already active, optionally publish wave status. Attach a
  native workers require neither cmux nor tmux.

## Salvage Rules

If a worker dies:

- Inspect the worktree before relaunching.
- If the worktree has useful changes, verify the diff and gates yourself.
- Commit only after scope and acceptance are confirmed.
- If two independent workers hit the same test failure, verify clean base before blaming either worker.
