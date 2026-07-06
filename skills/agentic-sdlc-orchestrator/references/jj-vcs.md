# jj (Jujutsu) for Agentic Waves — verified integration notes

Use this reference when a repo (or a conductor) wants jj instead of raw git for
worktree-wave mechanics. jj is git-compatible (colocated mode), and several of its core
design choices map DIRECTLY onto failure modes this bundle already documents. All facts
below verified live on jj 0.43.0 (2026-07-05) unless marked docs-only.

## Why jj fits agent fleets (the four structural wins)

1. **Uncommitted-work loss becomes structurally impossible.** Every jj command
   auto-snapshots the working copy into the working-copy commit `@`. There is no
   untracked-but-precious state for a `reset --hard` (or a steward revert) to destroy —
   the exact incident class that killed this bundle's predecessor scripts. Snapshots are
   in the op log even if never described/committed.
2. **`jj undo` / `jj op restore` = repo-state time machine.** The operation log records
   every mutation (with the argv that caused it). An agent that abandons the wrong commit,
   botches a rebase, or force-moves a bookmark is one `jj undo` from recovery — verified:
   `jj abandon` of a needed commit, then `jj undo`, restored it.
3. **Fan-in merges NEVER fail.** Conflicts are first-class committed state, not a blocked
   working tree. Merging two workspaces' conflicting edits produced a *successful* commit
   with `conflict=YES` and materialized markers; writing the resolved file auto-cleared it
   (no `--continue` dance), and descendants auto-rebase. The integrator's job shifts from
   "fight the merge" to "resolve recorded conflicts, then re-gate" — the semantic-
   correctness doctrine in `references/worktree-integration.md` still fully applies.
4. **Workspaces = worktrees with agent-grade semantics.** `jj workspace add ../ws-a
   --name agent-a` gives each worker its own directory AND its own `@`; the op log tags
   which workspace did what (`agent-a@`, `agent-b@` — free audit trail). If a conductor
   rewrites a commit another workspace has checked out, that workspace goes *stale* and
   `jj workspace update-stale` recovers it (with a recovery commit if ops were lost) —
   instead of git's silent divergence. Lock-free concurrency: parallel ops merge as
   3-way view merges rather than corrupting.

Also verified: a 1 MiB snapshot cap refuses accidental build-artifact commits (tunable) —
a guard agents get for free.

## Colocate-first adoption (reversible, CI-invisible)

```sh
jj git init --colocate          # inside an existing git checkout; .jj/ next to .git/
jj bookmark create wave-1 -r <rev>   # bookmarks ARE git branches (git branch sees them)
jj git push --bookmark wave-1        # normal push; remote/CI sees plain git
```

Verified: git log sees jj commits, `git rev-parse HEAD` works for gate scripts, a bare
remote receives pushed bookmarks as ordinary branches. CI and reviewers never know jj is
in play. Rollback = delete `.jj/`. Prefer jj for mutations and git for read-only commands;
background `git fetch` (IDEs) can interleave imports — tolerable, but know it's there.

## The gotchas (each one verified or doc-confirmed)

1. **Git hooks DO NOT fire on jj commits** (verified: a blocking pre-commit hook was
   silently bypassed). lefthook enforcement is git-side only. Consequence for the gate
   stack (`skills/repo-toolchain-gates/`): under jj, `mise run check` + CI ARE the gates —
   which is already the doctrine (hooks were guardrail, never boundary). Wire the check
   task into the conductor's wave checklist instead of relying on commit-time hooks.
2. **Revset `description("x")` is EXACT-match and silently misses.**
   `description("keep-me")` → 0 matches for a commit whose subject is exactly `keep-me`
   (the stored description ends in `\n`). Use `subject("keep-me")` or
   `description(substring:"keep")`. An agent scripting revsets with `description("…")`
   gets empty results that look like "commit doesn't exist".
3. **Auto-snapshot swallows everything not gitignored.** Scratch files, and — worse —
   secrets an agent writes into the tree, get snapshotted into the op log immediately.
   `.gitignore` discipline becomes load-bearing, and full-history secrets scans
   (`betterleaks git .`) matter MORE under jj, not less.
4. **Headless identity:** without `user.name`/`user.email`, commits get an empty identity
   that cannot be pushed. Workers need it via user config, `JJ_CONFIG=<file>`, or
   `--config user.name=… --config user.email=…` per call.
5. **`jj undo` undoes the LATEST op — which may be just a snapshot,** not the mutation you
   meant. Inspect `jj op log` first; use `jj op restore <op-id>` for precision.
6. **Per-path trust still applies to every workspace dir:** codex dir-trust AND mise trust
   are keyed on absolute paths (see `references/seeds-worktrees.md`) — a jj workspace is a
   new path like any worktree. Batch-trust at wave creation, same checklist.
7. **Not supported:** submodules, git-LFS, `.gitattributes`, shallow-clone deepening
   (docs-confirmed). Repos depending on these stay on plain git worktrees.

## Wave mechanics mapping (worktree wave → workspace wave)

| Worktree-wave step | jj equivalent |
|---|---|
| `git worktree add ../w-<seed> -b <branch>` | `jj workspace add ../w-<seed> --name <seed>` |
| worker commits on branch | worker works on its `@`; `jj commit -m …` per increment |
| integrator merge-base footprint check | same doctrine; `jj log -r 'trunk()..<rev>'` for footprint |
| merge conflicts block fan-in | merge always lands; resolve `conflict=YES` commits, then re-gate |
| lost uncommitted work on revert | can't happen (auto-snapshot); recover via op log |
| teardown `git worktree remove` | `jj workspace forget <name>` + delete dir |

Adopt incrementally: colocate one repo, run one wave with workspaces, keep CI untouched.
If the repo needs commit-time hook enforcement or submodules/LFS, stay on git worktrees —
both modes coexist in the same bundle doctrine.
