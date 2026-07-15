# Seeds, Worktrees, and PR Flow

Use this reference when converting the plan into parallel implementation work.

## Exact Seeds execution contract

Mise is the only bootstrap prerequisite. From a reviewed distribution checkout, bootstrap the
pinned tools once with `mise -C <distribution-root> install`. Thereafter, resolve the npm package
from a newly-created empty, config-free operating-system temporary directory, delete that
directory after execution, then use this exact POSIX command to execute `sd` in `<target>`:

```bash
NPM_CONFIG_REGISTRY=https://registry.npmjs.org/ NPM_CONFIG_USERCONFIG=/dev/null NPM_CONFIG_GLOBALCONFIG=/dev/null MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <neutral-temp> exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sh -c 'cd "$1" && shift && exec sd "$@"' agentic-sdlc-seeds <target> <args>
```

`<neutral-temp>` is not the target. Before launching, clear every inherited `NPM_CONFIG_*`
variable, including scoped registries, then set `NPM_CONFIG_REGISTRY` to
`https://registry.npmjs.org/`, user/global config to `/dev/null`, and strict SSL. `--no-config`
prevents target or ambient mise configuration from changing any runtime. The wrapper changes to
`<target>` only after mise has acquired the package and preserves every argument boundary; do not
assemble a shell command string or resolve an ambient `sd` from `PATH`. npm validates
registry-published tarball integrity metadata, but neither that behavior nor a version pin is a
claim that the pin authenticates the tarball or transitive dependency graph.

On native Windows use process-scoped variables and fresh empty temp files for npm config, restore
all prior variables (including every cleared `NPM_CONFIG_*` value), and preserve the target and
argument arrays:

```powershell
$previousSeedsEnvironment = @{}
$previousNpmConfigEnvironment = @{}
$neutralNpmConfig = [IO.Path]::GetTempFileName()
$neutralGlobalNpmConfig = [IO.Path]::GetTempFileName()
foreach ($variable in Get-ChildItem Env:NPM_CONFIG_*) {
  $previousNpmConfigEnvironment[$variable.Name] = $variable.Value
}
foreach ($name in @('MISE_NPM_PACKAGE_MANAGER', 'NPM_CONFIG_REGISTRY', 'NPM_CONFIG_USERCONFIG', 'NPM_CONFIG_GLOBALCONFIG', 'NPM_CONFIG_STRICT_SSL')) {
  $previousSeedsEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
try {
  Get-ChildItem Env:NPM_CONFIG_* | Remove-Item -ErrorAction SilentlyContinue
  $env:MISE_NPM_PACKAGE_MANAGER = 'npm'
  $env:NPM_CONFIG_REGISTRY = 'https://registry.npmjs.org/'
  $env:NPM_CONFIG_USERCONFIG = $neutralNpmConfig
  $env:NPM_CONFIG_GLOBALCONFIG = $neutralGlobalNpmConfig
  $env:NPM_CONFIG_STRICT_SSL = 'true'
  $neutralDirectory = [IO.Path]::Combine([IO.Path]::GetTempPath(), [IO.Path]::GetRandomFileName())
  [IO.Directory]::CreateDirectory($neutralDirectory) | Out-Null
  & mise --no-config --cd $neutralDirectory exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sh -c 'cd "$1" && shift && exec sd "$@"' agentic-sdlc-seeds $target @seedsArgs
} finally {
  Remove-Item -LiteralPath $neutralDirectory -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $neutralNpmConfig, $neutralGlobalNpmConfig -Force -ErrorAction SilentlyContinue
  Get-ChildItem Env:NPM_CONFIG_* | Remove-Item -ErrorAction SilentlyContinue
  foreach ($name in $previousNpmConfigEnvironment.Keys) {
    Set-Item "Env:$name" $previousNpmConfigEnvironment[$name]
  }
  foreach ($name in $previousSeedsEnvironment.Keys) {
    if ($null -eq $previousSeedsEnvironment[$name]) {
      Remove-Item "Env:$name" -ErrorAction SilentlyContinue
    } else {
      Set-Item "Env:$name" $previousSeedsEnvironment[$name]
    }
  }
}
```

Do not make permanent trust or config changes for this execution. Preflight verifies exact
version 0.5.14 and that the resolved executable is separator-bounded beneath mise's exact npm
installation root; Windows path comparison normalizes separators and ignores case. Wrong,
missing, or ambiguous version/provenance fails closed.

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
