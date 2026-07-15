# Seeds, Worktrees, and PR Flow

Use this reference when converting the plan into parallel implementation work.

## Exact Seeds execution contract

Mise is the only bootstrap prerequisite. From a reviewed distribution checkout, bootstrap the
pinned tools once with `mise -C <distribution-root> install`. Thereafter, use the exact pinned
Node `22.22.3` as an argv-safe trampoline. Mise acquires the tuple
`node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14` from neutral state; Node receives the
absolute target and original `Seeds` argument array separately, sets only the child's `cwd` to
the target, and runs the exact mise-provided executable with `shell: false` and inherited stdio.
Never join a command string, invoke `sh`, Git Bash, or select an ambient `sd` from `PATH`.

On POSIX, create private neutral state directly beneath fixed `/var/tmp` with `mktemp -d` after
`umask 077`. Do not derive the root from inherited `TMPDIR`, `TEMP`, or `TMP`; do not place it in
the target or target-controlled ancestry. Create two distinct empty files in that directory and
pass them as `NPM_CONFIG_USERCONFIG` and `NPM_CONFIG_GLOBALCONFIG`. Before acquisition, scrub
every inherited `NPM_CONFIG_*` variable, including scoped registries, then set only:

```text
NPM_CONFIG_REGISTRY=https://registry.npmjs.org/
NPM_CONFIG_STRICT_SSL=true
NPM_CONFIG_USERCONFIG=<neutral>/npm-user.config
NPM_CONFIG_GLOBALCONFIG=<neutral>/npm-global.config
MISE_NPM_PACKAGE_MANAGER=npm
```

Use `env -i` so those are the only npm settings. The launcher removes the entire neutral
directory on ordinary exit and traps `HUP`, `INT`, and `TERM` to remove it before preserving the
signal-derived failure. `--no-config` prevents target or ambient mise configuration from changing
the runtime; the target's `.npmrc` cannot affect acquisition.

On native Windows, `[IO.Path]::GetTempPath()` is the OS-selected writable temporary-root
boundary, independent of the target and all target-controlled ancestors. Create a random private
directory directly below it. The PowerShell launcher below makes two distinct empty config files,
scrubs all inherited `NPM_CONFIG_*` values, invokes the same exact tuple and Node trampoline, and
uses `try`/`finally` for every success/failure cleanup path. On Windows, Node cannot directly
spawn `.cmd` with `shell: false`; its Windows branch invokes `ComSpec` with the exact `sd.cmd`
path and an argv array while `shell` remains false. This is not a Git Bash/MSYS path.

```powershell
$previousSeedsEnvironment = @{}
$previousNpmConfigEnvironment = @{}
$neutralRoot = [IO.Path]::Combine([IO.Path]::GetTempPath(), [IO.Path]::GetRandomFileName())
[IO.Directory]::CreateDirectory($neutralRoot) | Out-Null
$neutralNpmConfig = [IO.Path]::GetTempFileName()
$neutralGlobalNpmConfig = [IO.Path]::GetTempFileName()
if ($neutralNpmConfig -eq $neutralGlobalNpmConfig) { throw 'distinct npm config files required' }
Move-Item -LiteralPath $neutralNpmConfig -Destination (Join-Path $neutralRoot 'npm-user.config')
Move-Item -LiteralPath $neutralGlobalNpmConfig -Destination (Join-Path $neutralRoot 'npm-global.config')
$neutralNpmConfig = Join-Path $neutralRoot 'npm-user.config'
$neutralGlobalNpmConfig = Join-Path $neutralRoot 'npm-global.config'
foreach ($variable in Get-ChildItem Env:NPM_CONFIG_*) { $previousNpmConfigEnvironment[$variable.Name] = $variable.Value }
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
  $nodeTrampoline = @'
const fs = require('node:fs'); const path = require('node:path'); const { spawn } = require('node:child_process');
const [target, ...args] = process.argv.slice(1); const executable = process.env.PATH.split(path.delimiter).map(entry => path.join(entry, process.platform === 'win32' ? 'sd.cmd' : 'sd')).find(fs.existsSync);
const child = spawn(process.platform === 'win32' ? process.env.ComSpec : executable, process.platform === 'win32' ? ['/d', '/s', '/c', executable, ...args] : args, { cwd: target, shell: false, stdio: 'inherit', windowsHide: true });
child.once('error', error => { console.error(error.message); process.exitCode = 2; }); child.once('close', (code, signal) => { if (signal) process.kill(process.pid, signal); else process.exitCode = code ?? 1; });
'@
  & mise --no-config --cd $neutralRoot exec node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- node -e $nodeTrampoline $target @seedsArgs
} finally {
  Remove-Item -LiteralPath $neutralRoot -Recurse -Force -ErrorAction SilentlyContinue
  Get-ChildItem Env:NPM_CONFIG_* | Remove-Item -ErrorAction SilentlyContinue
  foreach ($name in $previousNpmConfigEnvironment.Keys) { Set-Item "Env:$name" $previousNpmConfigEnvironment[$name] }
  foreach ($name in $previousSeedsEnvironment.Keys) {
    if ($null -eq $previousSeedsEnvironment[$name]) { Remove-Item "Env:$name" -ErrorAction SilentlyContinue }
    else { Set-Item "Env:$name" $previousSeedsEnvironment[$name] }
  }
}
```

npm validates registry-published tarball integrity metadata, but neither that behavior nor a
version pin authenticates the tarball or transitive dependency graph. Preflight verifies exact
version 0.5.14 and separator-bounded provenance beneath mise's exact npm installation root;
Windows path comparison normalizes separators and ignores case. Wrong, missing, or ambiguous
version/provenance fails closed.

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
