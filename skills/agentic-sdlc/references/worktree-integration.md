# Worktree Integration (fan-in)

Use this reference when collecting the output of multiple parallel worktree workers back
onto a shared branch — the fan-in step after an Act wave. Four hazards, all observed live,
plus the squash-scope discipline. Skipping these produces merges that LOOK clean and are
wrong.

## Hazard 1 — validate footprint against the MERGE-BASE, not the other HEAD

A worktree usually branches from an older base than current `main` (housekeeping lands
after spawning). `git diff main..branch` then shows every file `main` advanced on as if
the branch changed it — alarming and wrong.

```sh
MB=$(git merge-base main "$BRANCH")
git diff --name-only "$MB..$BRANCH"                    # the TRUE contribution
git diff --name-only "$MB..$BRANCH" | grep -v '^expected/scope/'   # out-of-scope check
```

`git merge --squash` replays exactly `MB..branch`, so this is what actually lands.

## Hazard 2 — deliverables split across worktrees with a PLACEHOLDER trap

A plan may put real handlers in wt-A/B/C and the WIRING (plus deliberate loud-stub copies
of those handlers) in wt-D. Blind `git merge wt-D` ships the DEAD STUBS. This is assembly,
not merge:

1. Read the plan/conductor's verdict first — it declares the topology.
2. Copy REAL artifacts from their owning worktrees; WIRING from the wiring worktree;
   SKIP the wiring worktree's placeholder copies.
3. Pre-flight the seam: wiring's dispatch keys must equal the real handlers' keys before
   any file moves.
4. If a wiring file drifted on main since merge-base, apply its diff-against-base
   (`git apply --3way`), don't blind-copy.

## Hazard 3 — verify by artifact + re-gate on MAIN, never by "done"

```sh
wc -l path/to/handler                       # 760, NOT the 32-line placeholder
git show HEAD --stat | grep -i node_modules # must be empty
```

Then RE-RUN each stream's gate ON MAIN. **Worktree-green ≠ main-green** — the worktree
tree differs (fixtures, config, deps), or the worker's logic regressed a pre-existing
test it never ran. If the main re-gate is RED, the merge is wrong even if the worker
swore green. Recovery for a bad local squash: `git reset --hard <prev-main-sha>`, confirm
green, send the worker the exact failing tests. Never push a merge whose gate you have
not personally re-run green on main.

## Hazard 4 — a clean 3-way `git apply` is NOT semantic correctness

A clean apply only means no TEXTUAL overlap. Two live failures, both clean, both wrong:

- **Missing entries:** worker (stale base) added a field to the 7 catalog entries it saw;
  main had since added 5 more. Clean apply → those 5 lack the field → runtime KeyError.
  Caught by a semantic COUNT: `grep -c '"new_field"'` vs the entry count.
- **Double declaration:** worker introduced `let sharedValues`; main already had
  `const sharedValues`. Clean apply → duplicate identifier → only the compiler catches it.

Discipline after EVERY 3-way apply of a drifted file: (1) run a semantic invariant
(count the added field across all records; grep duplicate declarations of new
identifiers), (2) typecheck + FULL affected suite on the merged tree.

## Squash-scope discipline (before ANY squash-merge)

`git merge --squash` operates on the merge-base→tip delta, which can be 10–100× what you
remember writing (long prior un-landed history rides along). Before squashing:

```sh
git rev-list --count <target>..<branch>            # commits target actually misses
git rev-list --count --merges <target>..<branch>   # 0 = linear
git log --oneline <target>..<branch>               # eyeball what would collapse
git diff --shortstat <target>..<branch>            # size sanity
```

If the count is far larger than the work you did, STOP — the branch carries un-landed
history; squashing flattens all of it. Tag the pre-squash tip
(`git tag pre-squash-<branch>`) so granular history survives, and confirm scope with the
user.
