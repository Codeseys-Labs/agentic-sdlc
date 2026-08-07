# Worktree lifecycle (in-workspace `.worktrees/`)

Use this reference to run one wave worktree end to end: create, gate, review, integrate,
reconcile the queue, clean up. Every step below states the exact command, the refusal it can
hit, and the recovery that restores a clean state. It is the single owner of those commands;
the substrate naming rule it implements is owned by `references/seeds-worktrees.md` §
Worktree substrate, and the fan-in hazards it defers to are owned by
`references/worktree-integration.md`.

Everything marked *verified* below was executed against throwaway fixture repositories on
Git 2.43.0 (Linux). Exit codes and message text are Git-version specific; re-verify the two
fail-open cases (create-strands-a-branch, squash-then-delete) before relying on them under a
different Git.

Nothing here authorizes an outward effect. A green gate, a clean diff, a reviewer label, a
verified queue record, and a local squash are all evidence. Push, publication, PR creation or
mutation, merge into a shared branch, deployment, and credential use each require explicit
operation-specific human authorization, and an authorized integrator alone performs an
already-authorized fan-in.

## The substrate, in one line

One worktree per write-capable worker at `<repo>/.worktrees/<seed-id>-<slug>/`, on branch
`work/<seed-id>-<slug>`, with `.worktrees/` gitignored end to end. Never a sibling
`../<repo>-<something>` directory: a sibling lands outside the workspace root, so it escapes
the repository's own ignore rules, escapes the tree scanners that exclude `.worktrees`, and
escapes any sandbox that confines an agent to the project directory. `references/seeds-worktrees.md`
§ Worktree substrate carries the canonical statement and the wave-selection rules; this file
carries the mechanics.

## Step 1 — create (one writer per worktree)

The conductor creates the worktree and hands it to exactly one write-capable worker. Two
writers in one tree is not a smaller version of this pattern; it is the failure this pattern
exists to prevent.

```sh
REPO=$(git -C <repo> rev-parse --show-toplevel)
BR="work/<seed-id>-<slug>"
WT="$REPO/.worktrees/<seed-id>-<slug>"

# Preconditions, both of them, before the add.
test -e "$WT" && { echo "refuse: target path occupied"; exit 1; }
git -C "$REPO" show-ref --verify --quiet "refs/heads/$BR" \
  && { echo "refuse: branch occupied"; exit 1; }

git -C "$REPO" worktree add "$WT" -b "$BR" <base>
```

Use `git -C "$REPO"` with an absolute `$WT`, never a bare relative path — but for the reason
below, not the one it is easy to assume. Under `git -C "$REPO"`, Git changes directory
**first**, so a relative `$WT` resolves against `$REPO`, not against the caller's cwd: run from
`<repo>/sub/deeper`, `git -C "$REPO" worktree add .worktrees/<id> -b <br> <base>` lands at
`<repo>/.worktrees/<id>`, which is the intended path (verified).

The hazard is that the surrounding shell does **not** get that `-C`. The `test -e "$WT"`
precondition above, every `git -C "$WT" ...` command in Steps 3 and 6, and the worker prompt's
path all resolve `$WT` against the caller's own cwd. From a subdirectory the precondition
silently checks a path that does not exist while the `add` targets one that does — the guard and
the command disagree, and `git -C ".worktrees/<id>" status` fails outright with
`fatal: cannot change to '.worktrees/<id>': No such file or directory` (both verified). An
absolute `$WT` makes every one of those consumers agree regardless of where the wave is driven
from, which is why the rule stands.

Add `--lock --reason "wave writer <seed-id>"` when another agent may run `git worktree prune`
while this writer is live: a locked entry is skipped by prune even when its directory is
momentarily absent (verified). The cost is an explicit `unlock` in Step 6.

| Refusal | What Git does | Recovery |
|---|---|---|
| Target path exists and is non-empty | Exit 128, `fatal: '<path>' already exists` — **but the `-b` branch was already created**, so a bare retry now hits the occupied-branch case for an unrelated reason (verified; pinned by `tests/test_worktree_failclosed.py`) | `git -C "$REPO" branch -d "$BR"`, then confirm `git worktree list --porcelain` and `git branch --list --format='%(refname)'` are byte-identical to the pre-attempt state, then choose a free path |
| Target path exists and is empty | Git **accepts** it (exit 0, verified) | Refuse anyway if you did not create that directory — an empty directory you did not make may be another agent's in-flight target. The `test -e` precondition above is deliberately stricter than Git |
| Branch already exists | Exit 255, `fatal: a branch named '<br>' already exists`; no directory created, worktree and branch lists unchanged (verified) | Inspect the branch before touching it (`git log --oneline <base>..$BR`, `git diff <base>...$BR`) — it may be a crashed predecessor's work worth salvaging. Then either resume in a fresh worktree on that branch or pick a new seed-scoped slug |
| Branch already checked out in another worktree | Exit 128, `fatal: '<br>' is already used by worktree at '<path>'` (verified) | Use that worktree, or branch a fresh child from it. Do not `--force` a second checkout of one branch |
| Path registered but missing (a predecessor's `rm -rf`) | Exit 128, `fatal: '<path>' is a missing but already registered worktree` (verified) | `git -C "$REPO" worktree prune`, then re-add. Do **not** use `add -f` to paper over it — that leaves the stale registration in place |
| Target is not inside a repository | Git reports it is not a working tree | Resolve `$REPO` with `rev-parse --show-toplevel` first and stop if that fails; never fall back to the caller's cwd |

The worker prompt must carry: the Seed id and acceptance criteria, the **absolute** worktree
path, the files and directories in scope, the exact gate commands, the artifact report path,
and an explicit instruction to make no unrelated change.

## Step 2 — gate inside the worktree

The worker runs the repository's own gate command inside its own worktree. Any agent that
runs a gate — implementer, reviewer, or critic — gets its own checkout, because a gate writes
build output and plants and restores fixtures, and two gate runs sharing one tree overwrite
each other undetected.

Run gate invocations **one at a time** even when the worktrees were created in parallel: gate
runs contend for CPU and I/O, and a suite with a hang or timeout detector fails on a loaded
host for a reason that is not in the code under test.

| Refusal | Recovery |
|---|---|
| Hooks fire but a shimmed gate command errors "config not trusted" — `.git/hooks` IS shared into a new worktree while per-absolute-path toolchain trust is NOT. Both facts, and the two allowed routes, are owned by `../../repo-toolchain-gates/SKILL.md` § Worktree waves; read them there rather than re-deriving them | Take the process-scoped route that runs the gate without persisting trust, or obtain explicit operation-specific user approval for that one exact reviewed config path. `references/seeds-worktrees.md` § Config propagation into new worktrees owns the approval wording |
| A gate depends on untracked project config that `worktree add` did not copy (it copies tracked files only) | Copy in only the approved untracked config the workers actually need, and record what you copied. Never widen the copy set to make an unexplained failure disappear |
| Gate red | The worktree does not advance. Return the exact failing command and output; findings become advisory `SeedProposal` records for the conductor. A red gate is not a candidate for `--no-verify` |
| Gate green | Evidence only. It does not close a Seed, does not authorize a fan-in, and does not survive the move to the integration branch — see Step 4 |

Stage paths by name inside a shared repository. `git add -A` and `git commit -a` sweep every
modified path in the tree, including fixtures a concurrent gate run planted; they are safe
only inside a path that is itself gitignored end to end.

## Step 3 — review

Review the diff and the gate transcript from a stable snapshot, never the worker's summary.
Three commands own three different questions, and only the first is in this file:

```sh
git -C "$WT" status --porcelain     # did the worker leave anything uncommitted?
git -C "$WT" diff HEAD              # uncommitted content, if any
git -C "$REPO" log --oneline <base>..$BR
```

For the true contribution and the out-of-scope check, compute the **merge-base** footprint:
`references/worktree-integration.md` § Hazard 1 owns those exact commands, and a
`<integration>..$BR` diff without a merge-base is the specific wrong answer it names. Do not
restate them here or re-derive them from memory.

| Refusal | Recovery |
|---|---|
| Uncommitted content in the worktree at review time | Decide before anything else whether it is real work or gate debris. Commit real work to `$BR` by name; delete debris deliberately. Reviewing a dirty tree makes the later `worktree remove` refuse (Step 6) for reasons nobody can reconstruct |
| Footprint includes paths outside the Seed's declared scope | Return the out-of-scope list as advisory findings; do not silently accept the extra files, and do not hand-edit them out of the branch on the worker's behalf |
| The worker reports done but the gate transcript is missing | Treat it as not run. A claim of green with no command output is not evidence |

## Step 4 — integrate

**This repository prefers squash for a wave worktree branch, rebase only for restacking a
dependent child, and a merge commit only for landing an integration branch that already
carries separately reviewed commits.** The reason is the fan-in hazard set:
`references/worktree-integration.md` § Squash-scope discipline shows that `git merge --squash`
replays exactly the merge-base→tip delta, so one Seed collapses into exactly one reviewable,
revertible commit whose scope you can count before you run it — while Hazard 2 shows that a
wave whose deliverables are split across worktrees is *assembly*, not merge, and a blind
`git merge <branch>` of the wiring worktree ships its dead placeholder copies. A squash whose
scope you verified first is the only one of the three that makes both hazards checkable in
advance. Rebase is reserved for the parent-landed case because it rewrites the child's
commits and every descendant must then be re-gated and re-reviewed. This repository's history
carries a handful of `merge:` commits, all of them integration-branch landings, not
single-worktree fan-ins.

```sh
git -C "$REPO" status --porcelain                       # must be empty
git -C "$REPO" rev-list --count <integration>..$BR      # scope, before anything else
git -C "$REPO" merge --squash "$BR"
git -C "$REPO" commit                                   # one Seed, one message, reason in the body
```

Before the squash, work through the four owned hazards in order — merge-base footprint
(Hazard 1), placeholder-trap assembly (Hazard 2), re-gate on the integration branch
(Hazard 3: worktree-green is not integration-green), semantic invariants after any 3-way
apply (Hazard 4) — plus § Squash-scope discipline for the pre-squash tag. Author the squash
and commit text via `../../change-writing/SKILL.md` (output-only).

| Refusal | What Git does | Recovery |
|---|---|---|
| Integration tree dirty on a path the squash also touches | Exit 1, `error: Your local changes ... would be overwritten by merge` and nothing lands (verified) | Commit or stash the unrelated change first. Note the worse sibling case: when the dirt does **not** overlap, the squash **succeeds** and leaves the unrelated modification sitting beside the staged result (verified) — which is why the `status --porcelain` precondition is unconditional, not just for overlaps |
| You want a clean tree to integrate from, so you try a second worktree on the integration branch | Exit 128, `fatal: '<branch>' is already used by worktree at '<path>'` (verified) — one branch, one checkout | Commit the workspace and integrate there, or make a `--detach` snapshot worktree at the integration tip for read-only verification |
| Commit count far larger than the work you remember | — | STOP. The branch carries un-landed history that a squash would flatten. Tag the pre-squash tip and confirm scope with the user before proceeding (§ Squash-scope discipline owns the tag) |
| Re-gate on the integration branch is red | — | The merge is wrong even if the worker swore green. § Hazard 3 owns the reset-to-prior-tip recovery and the "send the worker the exact failing tests" follow-up |

## Step 5 — reconcile the queue (conductor-only record seam)

Workers and reviewers inspect queue state and emit typed `SeedProposal` records; they never
execute a queue write. The conductor's durable write is one seam:

```sh
DIGEST=$(sha256sum "$REPO/.seeds/issues.jsonl" | cut -d' ' -f1)
<exact-node> <installed-skill>/tools/seeds-launcher.mjs record \
  --target "$REPO" --queue-writer conductor --expect-queue "$DIGEST" \
  update <id> --status <status>
```

Run it at the **queue-owning root**, never from inside `.worktrees/<seed-id>-<slug>/`. The
seam refuses a linked-worktree or submodule target by design, because such a target's queue
write redirects to another root. `references/seeds-worktrees.md` § Seeds Queue owns the
execution contract for the launcher itself (bootstrap, receipt, `inspect` admission).

| Refusal | Recovery |
|---|---|
| The target is a linked worktree (`.git` is a file, not a directory) | Re-run at the root that owns the queue. Detect it first: `[ "$(git -C "$WT" rev-parse --git-dir)" != "$(git -C "$WT" rev-parse --git-common-dir)" ]` is true inside a linked worktree |
| Compare-and-swap refusal: the queue digest moved between classification and write | Re-read the queue, re-classify the decision against the **new** state, recompute the digest, and re-run. Never retry with the stale digest and never widen the write to force it through |
| Readback divergence: the post-state is not the prestate plus exactly the requested delta | Stop and inspect the named divergence. The seam refuses rather than accepting an unrequested field, a rewritten neighbouring record, or an added or removed queue file |
| A worker asks you to close a Seed because it reported done | Refuse. Verify current files, gates, and acceptance criteria yourself. A worker claim, a reviewer label, a gate status, or a conductor preference is never sufficient |

A verified record is the conductor's own evidence. It authorizes no push, PR, merge,
deployment, or other outward effect.

## Step 6 — clean up

Order is load-bearing: nested children first, then the worktree, then prune, then the branch.

```sh
git -C "$REPO" worktree unlock "$WT"     # only if created with --lock
git -C "$REPO" worktree remove "$WT"
git -C "$REPO" worktree prune
git -C "$REPO" diff --stat <integration> "$BR"   # empty output = content landed
git -C "$REPO" branch -d "$BR"                   # or -D, see the table
```

| Refusal | What Git does | Recovery |
|---|---|---|
| Directory is dirty (modified **or** untracked content) | Exit 128, `fatal: '<path>' contains modified or untracked files, use --force to delete it` (verified for both cases) | Do not reach for `--force` first. Inspect (`git -C "$WT" status --porcelain`, `git -C "$WT" diff`), salvage anything real as a commit on `$BR` or into an artifact file, then `remove --force`. `--force` on an uninspected dirty worktree is silent work loss |
| Worktree is locked | Exit 128, `fatal: cannot remove a locked working tree; use 'remove -f -f' to override or unlock first` — a **single** `--force` is also refused (verified) | `worktree unlock "$WT"` then remove, or `remove -f -f` when you own the lock and have inspected the tree |
| The branch is checked out in a live worktree | `branch -d`/`-D` exit 1, `error: cannot delete branch '<br>' used by worktree at '<path>'` (verified) | Remove the worktree first. Branch deletion is always the last step |
| Someone deleted the directory with `rm -rf` | The registration survives: `worktree list --porcelain` marks the entry `prunable` / `gitdir file points to non-existent location`, and re-adding that path fails "missing but already registered" (verified) | `git worktree prune` removes exactly those dead registrations — it removes no live worktree and deletes no branch. A **locked** missing entry is not pruned at all (verified, exit 0, nothing removed) until `worktree unlock` |
| Removing a worktree that itself contains a nested worktree | `remove` on the parent **succeeds** (exit 0) and deletes the parent directory and the child's directory with it, but the **child stays registered** and is marked `prunable` (verified). Nothing errors at this point, which is what makes it easy to miss. The `fatal: '<path>' is not a working tree` message comes from re-running `remove` against the now-deleted **parent** path (exit 128) — not from the child, whose own `remove` still exits 0 (both verified) | Remove children bottom-up first. If it already happened, `git worktree prune` alone clears the orphaned child registration (verified: exit 0, child entry gone, no other entry touched) — a second `remove` on the parent is not the recovery and only produces the misleading fatal. Then check for a stranded child branch: prune deletes no branch, so `work/<child>` survives and needs Step 6's content check before `branch -d`/`-D` (verified) |
| Branch is unmerged | `branch -d` exit 1, `error: the branch '<br>' is not fully merged` (verified) | If the work has not landed, keep the branch and record why. If it has, use the content check below |
| Branch was **squash**-merged and `-d` still refuses | Expected: a squash creates no merge edge, so `-d` refuses, `git branch --merged <integration>` omits the branch, and `git cherry -v` reports every commit as `+` / unlanded — all three verified. None of them is a squash-landed detector | The check that works is content equivalence: `git diff --stat <integration> "$BR"` producing **empty** output. Empty diff **plus** a green re-gate on the integration branch is the evidence for `branch -D`. Anything else: keep the branch |

Two things never to run in a workspace with a live wave:

- `git clean -xdff`. A single `-xdf` **skips** a nested worktree (`Skipping repository .worktrees/<id>`); the double force **deletes** it (verified), taking the writer's uncommitted work with it.
- `git worktree remove`/`prune` against an entry you do not own. `git worktree list` is repo-wide; filter to the `.worktrees/` prefix you created and leave every other entry alone.

## The harness's own `.claude/worktrees/`

The Claude Code harness creates its own agent worktrees under `.claude/worktrees/` in this
repository, alongside the wave's `.worktrees/`. Both directories are gitignored, and both are
excluded from this repo's tree scanners — `tests/test_preflight_capabilities.py` excludes
`.worktrees` and `.claude` from the shipped-surface walk (a linked worktree is another
commit's tree, and every root-relative exemption breaks one level down), and
`tests/test_cao_removal.py` skips the same two prefixes for the same reason.

The consequence for this lifecycle: `git worktree list` shows **both** families in one
output, so ownership is by path prefix, not by "whatever the list returned". Never prune,
remove, or unlock an entry under `.claude/worktrees/`; a wave owns exactly the
`.worktrees/<seed-id>-<slug>/` paths it created. The same rule protects the reverse case —
a harness-side cleanup must not reach into `.worktrees/`.

## Verified Git facts (executed, Git 2.43.0, Linux)

1. **`worktree add` works inside a gitignored path.** `git worktree add .worktrees/<id> -b <br>`
   inside a repo whose `.gitignore` contains `.worktrees/` succeeds, and the main workspace's
   `git status --porcelain --untracked-files=all` stays empty. Without that ignore rule the
   nested worktree shows up as `?? .worktrees/` and `git add -A` stages it as an embedded
   repository (`warning: adding embedded git repository`, a gitlink in the index) — which is
   why the ignore rule is part of the substrate, not a convenience.
2. **A linked worktree's `.git` is a file**, containing `gitdir: <repo>/.git/worktrees/<id>`.
   `rev-parse --git-dir` and `--git-common-dir` differ inside it and match in the main
   workspace — that inequality is the portable "am I in a linked worktree" test.
3. **`-b` runs before the path check.** An occupied target path refuses *after* creating the
   branch, stranding an orphan. Verifying the path first is the fix, and deleting the
   stranded branch is the recovery. `tests/test_worktree_failclosed.py` pins this fail-open
   behavior so that a future Git that fixes it makes the test fail loudly rather than leaving
   the guard in place forever.
4. **An occupied branch refuses cleanly** (exit 255): no directory is created and the
   worktree and branch lists are unchanged.
5. **An existing empty directory is accepted.** Git's own precondition is weaker than this
   lifecycle's; the `test -e` guard is deliberate.
6. **A dirty caller does not leak into the new worktree.** With staged, unstaged, and
   untracked changes in the workspace, the new worktree checks out the committed content, has
   an empty `status --porcelain`, and the caller's dirt is untouched.
7. **Nesting works and inherits the ignore rule.** A worktree created from inside a linked
   worktree lands at `<parent>/.worktrees/<id>`, is matched by the same root `.gitignore`
   rule (`check-ignore -v` reports `.gitignore:1:.worktrees/`), and registers as a third
   peer in the repo-wide list. Removing the parent succeeds silently and leaves the child
   registered and `prunable`; `prune` alone clears that orphan, and the child's branch survives
   it. Step 6's nested-worktree row owns the recovery and the message attribution.
8. **`worktree prune` is registration-only.** After a manual `rm -rf`, prune removes the dead
   registration and nothing else; it never deletes a branch or a live worktree, and it skips
   locked entries.
9. **Squash-merge leaves no merge edge**, so `branch -d`, `branch --merged`, and `git cherry`
   all still report the branch as unlanded. `git diff --stat <integration> <branch>` returning
   empty is the check that reflects reality.
10. **Restack after a squash works cleanly**: with parent `A` squashed into the integration
    branch, `git rebase --onto <integration> <A> <child>` replays exactly the child's own
    commits and leaves the child tree clean. `references/git-change-flow.md` routes to the
    owner of the lease and cascade mechanics for the push side of that operation.
11. **Squash into a dirty tree**: aborts (exit 1) when the dirty path overlaps the incoming
    change; succeeds and mixes the unrelated modification into the resulting working tree
    when it does not.
12. **One branch, one checkout.** A second `worktree add` on a branch already checked out
    elsewhere is refused, including the integration branch — there is no "clean second copy
    of main" without detaching.

## Pointers

- `references/seeds-worktrees.md` — the canonical substrate statement, wave selection, the
  Seeds execution contract, config propagation into new worktrees, and salvage rules.
- `references/worktree-integration.md` — the four fan-in hazards and squash-scope discipline
  this file's Step 4 defers to.
- `references/git-change-flow.md` — the dispatch table for every stacked-PR and rewrite rule
  (leases, restack cascade, deletion checks); it names the one authoritative site per rule.
- `references/worktree-failclosed-tests.md` — the fail-closed test-design contract for an
  isolation mechanism, including the planted-violation cases behind fact 3 above.
- `../../repo-toolchain-gates/SKILL.md` § Worktree waves — the owner of the shared-hooks and
  per-path-trust propagation facts referenced in Step 2.
