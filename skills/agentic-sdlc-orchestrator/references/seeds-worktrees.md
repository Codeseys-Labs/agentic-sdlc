# Seeds, Worktrees, and PR Flow

Use this reference when converting the plan into parallel implementation work.

## Exact Seeds execution contract

Mise is the only bootstrap prerequisite. The installed flagship skill contains the portable Node
stdlib tool `tools/seeds-launcher.mjs`; first run its explicit bootstrap mode from a reviewed
distribution checkout:

```text
<exact-node-22.22.3-root>/bin/node tools/seeds-launcher.mjs bootstrap --distribution <exact-clean-git-root>
```

The launcher itself must be executing as Node `22.22.3`. The distribution must be an exact clean Git
root: its argument must equal `git rev-parse --show-toplevel`, and `HEAD`, index, tracked
working tree, untracked files, and ignored files must resolve to one exact clean commit tree; nested paths and any live-tree addition or edit
fail before acquisition. Bootstrap alone runs `mise --locked install` with the root's reviewed
`mise.toml` and adjacent `mise.lock` as the only config. It uses private state-owned HOME, mise
data/cache, and two distinct empty npmrc files; pins the official npm registry and npm backend;
disables hooks/config environment; and ignores ambient HOME, npmrc/registry variables, and mise
config/data/cache variables. It then consumes exact roots returned by `mise --no-config where` for
Node `22.22.3`, Bun `1.3.10`, and `npm:@os-eco/seeds-cli@0.5.14`. It validates the version, platform
layout, package name/version, separator-contained `sd` bin entry, and package controls. The released
package's string `engines.bun` compatibility requirement is benign; Bun config, TypeScript config,
macro, preload, and other actual execution-control forms remain forbidden. It creates a trusted
owned empty Bun config and hashes the reviewed distribution tree, exact Git commit and tree,
`mise.toml`, `mise.lock`, every tool tree, package metadata, entry, Git binary, and trusted configs,
then atomically publishes an active versioned receipt under platform state while retaining the
preceding receipt for rollback.

The lock and npm backend establish exact version selection but **do not authenticate the npm
tarball or transitive dependency graph**. The receipt catches ordinary post-bootstrap drift but
cannot close a same-UID TOCTOU race between its checks and spawn.

Thereafter `Seeds(<target>, <args...>)` means exact Node running:

```text
seeds-launcher.mjs inspect --target <target> <args...>
```

`inspect` never installs, calls mise, acquires from a network, discovers ambient tools, repairs a
receipt, or reads target package controls. The process must itself be exact Node `22.22.3`; it
validates only the active receipt and current hashes, then permits precisely `--version`, `prime`,
`ready [--format json]`, and `blocked [--format json]`. Other forms fail before Bun. Exact Node uses `shell:false` solely as
an argv-safe wrapper for the exact absolute Bun executable and exact entry, with target as cwd.
Bun uses `--config=<trusted-empty-file>`, `--no-env-file`, and `--no-install`. Its environment is
an allowlist: `PATH` contains only the separately resolved recorded Git directory, and Git system
and global config are isolated; all `BUN_*`, `NODE_OPTIONS`, npm/mise override variables, and
unreviewed Seeds debug variables are absent. This leaves neither target `bunfig`, `.env`, package
configuration, nor ambient `sd` with execution authority.

POSIX and native Windows wrappers resolve the exact Node root before delegation, establish
cleanup before setup, preserve the immediate child status, clean up, and return that exact status.
They make no persistent Windows environment, trust, or config change.

## Seeds Queue

Only the conductor owns Seeds queue mutations. Workers and reviewers inspect queue state through
`Seeds(<target>, ready --format json)` and emit typed `SeedProposal` records; they never execute
create/claim/update/close/sync actions. The conductor may apply an operation only after verified,
operation-specific policy authorizes it. Seeds remain an authoritative dynamic queue for
recommendations and acceptance tracking, never an authorization channel.

```text
Seeds(<target>, prime)
Seeds(<target>, ready --format json)
Seeds(<target>, blocked --format json)
```

The conductor creates or updates Seeds for:

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
- Confirm the conductor's verified, operation-specific policy before any queue synchronization.
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
- Codex per-path dir-trust — trust is keyed on the absolute path. Adding a new worktree to
  `~/.codex/config.toml` is a persistent user-config mutation: obtain explicit
  operation-specific user approval for each exact path before changing it. Without approval,
  stop or use a certified non-persistent execution plane; do not treat the trust prompt as
  authorization.
- mise per-path trust — same pattern: a fresh worktree is untrusted even when the main repo
  is trusted, so shared git hooks can fail on a mise-shimmed command. Persistent
  `mise trust <worktree-path>` requires explicit operation-specific approval for that exact
  reviewed config path. A process-scoped check may use `mise --no-config --cd <worktree>
  exec ...` without persisting trust. Missing, unpinned, untrusted, or ambiguous required
  capability fails closed; do not bypass the repository gate. Full gate stack:
  `skills/repo-toolchain-gates/`.

Wave-creation checklist: create worktree → copy only approved untracked config the workers
need → request operation-specific approval for each persistent Codex/mise trust mutation or
select a certified process-scoped route → then launch.

## Worker substrates and optional viewers

- Launch provider-native workers by default after capability and trust probes pass. Give every
  write-capable worker one worktree, its absolute path, and an artifact report path. Never
  share a write worktree.
- Codex workers on any substrate require a certified path-trust state. Persistent edits to
  `~/.codex/config.toml` require explicit operation-specific user approval for each path;
  absent that approval, stop or select a certified non-persistent route.
- When cmux is already active, optionally publish wave status. Attach a
  native workers require neither cmux nor tmux.

## Salvage Rules

If a worker dies:

- Inspect the worktree before relaunching.
- If the worktree has useful changes, verify the diff and gates yourself.
- Commit only after scope and acceptance are confirmed.
- If two independent workers hit the same test failure, verify clean base before blaming either worker.
