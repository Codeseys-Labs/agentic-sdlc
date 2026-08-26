---
name: sdlc-init
description: Safely activate Agentic SDLC inside a new or existing repository — tracked VCS baseline, Seeds, pinned gates, trust, shared agent guidance, and CI — ending Git-wave-ready
---

Initialize the current directory (or the path in $ARGUMENTS) as an Agentic SDLC project using
this **reviewed runbook**. It is a host procedure, not a deterministic activation engine:
inspect, propose, apply only approved changes, verify the result, and stop on ambiguity.
This is the **project activation plane**. Global skills, commands, agents, and scripts are
installed separately by `mise run lifecycle:install`; do not install or mutate global agent
homes here.

Idempotency is a claim requiring observed evidence, not an implementation assumption: inspect,
adopt, or surgically merge. Never overwrite an existing `mise.toml`, `lefthook.yml`,
`AGENTS.md`, `CLAUDE.md`, CI workflow, `.seeds/`, or VCS configuration. If an existing file
cannot be merged without changing unrelated policy, report the conflict and stop before
claiming wave readiness.

**Two verbs cover the tooled part of this runbook**, both in
`skills/agentic-sdlc/tools/instruction-generator.py`: `classify --target` for the repository class
and `apply --target --manifest --entry` for the one marked instruction block. Everything else in
this file — substrate selection, Seeds proof, trust decisions, gate falsifiability, CI parity,
`wave_ready` — is conductor work performed and evidenced as reviewed manual steps, never claimed
as a tool guarantee. Read `--help` before invoking either verb.

`apply` prints a unified diff and writes only when the same invocation carries `--yes`: within
the `--yes` invocation, the diff printed is exactly the bytes written. The documented loop below
is two invocations — review, then re-run with `--yes` — and nothing binds them mechanically, so
approval attaches to the diff the `--yes` invocation re-prints, not to the earlier one.
Without `--yes` it shows the diff and refuses at exit 3,
having written nothing; a symlink or any non-regular node at the target refuses at exit 2, as does
an entry whose parent directory does not exist in the target, because this tool creates no
directory; a target already carrying the rendered block reports `no-op`, which is the idempotence
proof.
Approval of a diff is not authorization for any other effect.

1. **Preflight and snapshot**
   - Load `agentic-sdlc` and the `repo-toolchain-gates` skill.
   - Resolve the target repository, then record `git status --short`, tracked/untracked
     files, current branch/HEAD, remotes, existing task runner, hooks, CI, instruction
     files, and language/toolchain manifests.
   - Run the maintained prerequisite checker from the reviewed distribution checkout. Its
     `agentic_sdlc_seeds`, `agentic_sdlc_seeds_init`, and `agentic_sdlc_seeds_record` front doors
     resolve exact Node and delegate to the installed receipt-bound launcher. Use the read-only
     `Seeds(<target>, <args...>)` shorthand only for inspection; use the explicit conductor
     front doors for queue initialization or an existing-queue record. Missing, unpinned, untrusted,
     or ambiguous required capability fails closed; missing optional cmux or tmux
     never triggers implicit installation. `mise` is the only bootstrap prerequisite and the
     managed-tool bootstrap, not the sole readiness prerequisite; repository tools are pinned
     through it, while repository readiness still requires verified Git, gates, trust, and
     selected adapters. A dispatching consumer later needs a caller-injected certified exact
     model ID, **explicit requested effort**, and requested context form; a provider-neutral role
     does not select one and must stop before inherited or unresolved dispatch. Record
     requested/resolved/inherited/unresolved state, and the selected adapter and its
     capability/model readback; record resolved provider/model/effort/context only after adapter
     readback, or record inherited/unresolved when the adapter cannot prove the resolved
     provider/model.
   - If the repository is dirty, do not commit, stage, or absorb pre-existing changes.
     Produce the activation proposal and ask the user to commit/stash/select an explicit
     activation worktree before write steps.

2. **Establish a trustworthy Git wave base**
   - No `.git` → `git init -b main`. Do this first: the classifier below classifies
     repositories and refuses a directory that is not one.
   - **Derive the class before asking.** Run the read-only
     `skills/agentic-sdlc/tools/instruction-generator.py classify --target <absolute path>`. It
     writes nothing and answers at exit 0 with one of three verdicts, each carrying `ask: true`:
     `brownfield` when it names an occupied guidance, queue, decision, toolchain, hook, CI, or
     `.agentic-sdlc` surface, read in Git's index and on disk; `greenfield` when nothing is
     occupied, the repository holds at most one commit, and `git status --porcelain` is clean;
     `refuse-and-ask` otherwise, with each reason named. An unusable `--target` — not absolute,
     not a directory, not a Git repository, or not that repository's ROOT — refuses at exit 2
     instead of guessing a class. The root is required because occupancy is read at the supplied
     directory while commit count and cleanliness are repository-wide, and a subdirectory would
     answer one verdict over two scopes.
   - **`brownfield` is the only verdict that settles the question by itself**, because it is a
     positive observation of something that is there. On `refuse-and-ask`, ask the
     greenfield-or-existing-code question and QUOTE the named reasons — the human needs to know
     what the classifier saw. `greenfield` is a **proposal**, not a licence to write: it is
     precisely the verdict that would authorize a baseline, so it still requires the confirmation
     in the next bullet before you propose one.
   - The verdict is **advisory evidence, not a decision**. It reports what is on disk and in the
     index, claims no readiness, ownership, trust, route, or tool identity, and authorizes no
     write. Two occupied surfaces leave no trace in either place — a hosted tracker such as
     GitHub Issues, Jira, or Linear, and a forge-side required check — so `greenfield` is bounded
     by what Git can see rather than proven against the forge. Confirm both with the user before
     proposing a baseline, and record the verdict with its evidence rather than restating it as a
     fact about the project.
   - Greenfield: create a minimal README intent and commit it.
   - Existing code: inventory ignored, tracked, and untracked product files. Never make an
     empty commit and call the project wave-ready. Require the user to approve the initial
     tracked baseline because Git worker worktrees contain tracked files only. Secret-scan
     and review that baseline before committing.
   - Existing Git repository: preserve its branch/history policy. Do not create an
     activation commit until the pre-activation tree is clean and every activation diff is
     explicitly enumerated.
   - **Supported Wave substrate is Git worktrees.** Keep activation and Waves on Git
     worktrees; this runbook neither initializes nor promotes another VCS substrate.

3. **Seeds queue of record**
   - Initialize only through `agentic_sdlc_seeds_init <target>`, which invokes the exact launcher
     form `record --target <target> --queue-writer conductor --expect-queue absent init`. This is
     allowed only when `.seeds` has no filesystem node at all and the target is the queue-owning
     root, not a linked worktree/submodule redirect. Any existing directory, partial surface,
     file, symlink, or non-regular `.gitattributes` is a conflict: inspect and preserve it; do not
     treat it as permission to repair or overwrite. The launcher snapshots `.gitattributes` and refuses a
     non-UTF-8 file or a prestate whose exact-line classification disagrees with the pinned
     initializer's substring behavior before any write. It invokes exact pinned Seeds initialization
     with JSON output and admits only the closed five-file `.seeds`
     surface plus the precise missing `merge=union` line append. A failed child after either
     surface moves is an unknown effect requiring inspection; no movement is a clean refusal.
   - Convert starting intent into 1–3 bounded Seeds, or derive them from accepted TODOs /
     issues. Never invent priority or silently import every TODO.
   - Record whether `.seeds/` is tracked or intentionally local according to repository
     policy. Never leave the queue empty while claiming Wave readiness.

4. **Merge the repository gate stack**
   - Existing `mise.toml`: parse and preserve its tools/tasks; propose only missing pinned
     tools and tasks. New file: pin the detected language toolchain, linters, `lefthook`,
     and `betterleaks`; create fmt/lint/test tasks that match the repository, one aggregate
     `check`, and a `contributor:setup` task. Never add speculative tools.
   - Git substrate: merge a marked Agentic SDLC block into `lefthook.yml`; pre-commit is the
     fast staged-file subset, pre-push includes tests and the working-tree secrets scan
     (`betterleaks dir .` with `--config` pinned at a tracked extend-only config, never the bare
     form — a drop-in config or `GITLEAKS_CONFIG*` variable otherwise replaces the ruleset). Preserve all
     foreign hooks. `contributor:setup` installs lefthook.
   - Wire the secrets gate into `mise run check` and CI. Run `betterleaks git .` only after
     explicit consent when history scanning is appropriate (public release/migration), and
     never plant a credential-shaped value in durable history to test it.
   - Persistent `mise trust <repo-path>` is a separate state mutation. After showing the
     exact task/config diff, obtain explicit operation-specific user approval for that exact
     path before running it. A general activation approval is insufficient; process-scoped
     validation may use `mise --no-config --cd <repo-path> exec ...` without persisting trust.
   - Prove falsifiability with a reversible, non-secret temporary fixture that is never
     committed; observe `mise run check` fail, restore the fixture, then require a clean
     pass.

5. **Shared agent guidance**
   - `AGENTS.md` is the cross-host canonical project policy. Write it only through
     `skills/agentic-sdlc/tools/instruction-generator.py apply --target <absolute path>
     --manifest <reviewed manifest> --entry AGENTS.md`, which renders one manifest entry inside
     `<!-- agentic-sdlc:start -->` / `<!-- agentic-sdlc:end -->` markers, preserves every byte
     outside them, and splices in place when the block already exists. Review the printed diff,
     then re-run the same command with `--yes` to write it. The `--yes` invocation re-renders
     against the live target and manifest and re-prints the diff of exactly the bytes it writes;
     confirm that re-printed diff matches the one reviewed, because no digest binds the two
     invocations. Step 7's enumerated `git diff` before the atomic activation commit is the
     byte-exact approval artifact. Include project intent,
     `mise run check`, Git-worktree substrate, Seeds commands, worktree ownership, and the global
     doctrine pointer.
   - `CLAUDE.md` remains thin: the same `apply` with `--entry CLAUDE.md`, preserving existing
     content and referencing `AGENTS.md` plus Claude-specific command routing.
   - Never duplicate the full orchestration doctrine into the repository.

6. **Trust propagation and CI parity**
   - Trust the main project path for Codex only when Codex is present and explicit
     operation-specific user approval covers that exact user-config mutation.
   - Record that every future Wave worktree requires separate operation-specific approval
     for persistent `mise trust <worktree>` and Codex path-trust config before workers start;
     Git hooks themselves remain shared. The absence of approval is a stop or a reason to use
     a certified process-scoped no-config gate, never permission to mutate user config.
   - Detect the forge/CI provider. If ambiguous, ask before creating a workflow. CI invokes
     the same `mise run check`; it does not reimplement the gate.
   - Optional workflow enablement: if this repository wants the shipped wave scout discoverable
     by name, run `mise run claude:workflows:activate -- --workflow sdlc-wave-scout --target
     <repo>` from the distribution checkout. The manager copies the owned installed bytes into
     the target's `.claude/workflows/` and refuses an absent, unowned, or drifted installed
     source and an occupied foreign destination — treat any refusal as a stop to inspect, never
     as permission to clear the path by hand. Enablement takes effect at the target's next
     Claude Code session (the Workflow name registry is read at session start). The placed file
     is repo-visible: include it in the activation commit only with the same explicit approval
     as every other enumerated activation file.

7. **Commit and evidence**
   - Re-run inventory and show exactly created, adopted, merged, skipped, and conflicted
     items. A rerun with no repository changes, and `apply` reporting `no-op`, is the
     idempotency proof. The evidence is the Git history and the printed diffs; no machine-local
     activation receipt is written or read.
   - Commit only the enumerated activation files as one atomic commit after user approval.
     Never include the user’s pre-existing changes.
   - Report tracked-baseline evidence, gate fail→pass proof, initial Seeds, trust actions,
     remaining conflicts, and `/sdlc-frame <first milestone>` as the next step.
   - Claim **Git-wave-ready** only when observed evidence shows: clean tracked baseline,
     non-empty Seeds queue, `mise run check` passes, guidance/CI agree, required capability
     and worktree trust are verified, and any selected adapter/model is read back. This local
     claim does not authorize push, publication, PR mutation, merge, deployment, credentials,
     or another outward effect; each operation needs explicit operation-specific approval.
