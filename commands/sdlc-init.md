---
name: sdlc-init
description: Safely activate Agentic SDLC inside a new or existing repository — tracked VCS baseline, Seeds, pinned gates, trust, shared agent guidance, and CI — ending Git-wave-ready
---

Initialize the current directory (or the path in $ARGUMENTS) as an Agentic SDLC project using
this **reviewed runbook**. It is a host procedure, not a deterministic activation engine:
inspect, propose, apply only approved changes, verify the result, and stop on ambiguity.
This is the **project activation plane**. Global skills, commands, agents, and scripts are
installed separately by `mise run bundle:install`; do not install or mutate global agent
homes here.

Idempotency is a claim requiring observed evidence, not an implementation assumption: inspect,
adopt, or surgically merge. Never overwrite an existing `mise.toml`, `lefthook.yml`,
`AGENTS.md`, `CLAUDE.md`, CI workflow, `.seeds/`, or VCS configuration. If an existing file
cannot be merged without changing unrelated policy, report the conflict and stop before
claiming wave readiness.

**Plan before apply.** The canonical planner is
`skills/agentic-sdlc/tools/activation-planner.py`; `scripts/activation_planner.py` is a
compatibility loader that delegates to it. Read `--help` before invoking: the verb set and
required arguments are narrower than this runbook once described, and a stale invocation dies in
argument parsing rather than doing anything.

Verified surface (2026-08-06): `plan`, `apply`, `status`, `recover`. `plan` requires
`--target`, `--manifest`, and `--entry` — it plans **one** named entry from a reviewed manifest,
not a whole-repository profile. There is **no `--profile` flag and no `deactivate` verb**; the
module's own help states it "deliberately supports no greenfield, readiness, Seeds, trust, Git,
or multi-file activation behavior," and it is Linux-only and single-entry by construction. Treat
any broader activation — substrate profile selection, Seeds proof, trust decisions, `wave_ready`
— as **not implemented**: it must be performed and evidenced by the conductor as reviewed manual
steps, and must not be claimed as a planner guarantee.

The plan writes nothing and records, per item, the proposed `create|adopt|merge|refuse|skip`
action and whether each choice was `explicit`, `defaulted`, or `derived`. Cancellation at the
confirmation step performs zero writes. Apply-phase writes go through the same tool's contracts,
with instruction files rendered by the marker-aware `instruction-generator.py`, and a run that
reaches the write phase records a receipt; refused, cancelled, and stopped runs write nothing at
all, including no receipt. Rerunning against an activated tree must produce an empty
`created`/`merged` result (observed idempotence). A procedural grant is a same-user, single-use
record — it is not an authenticated approval, and no planner output authorizes an outward effect.

1. **Preflight and snapshot**
   - Load `agentic-sdlc` and the `repo-toolchain-gates` skill.
   - Resolve the target repository, then record `git status --short`, tracked/untracked
     files, current branch/HEAD, remotes, existing task runner, hooks, CI, instruction
     files, and language/toolchain manifests.
   - Run the maintained prerequisite checker from the reviewed distribution checkout. It defines
     `Seeds(<target>, <args...>)` as the exact, config-independent mise contract in
     `agentic-sdlc` and verifies version/provenance; use that shorthand for every
     Seeds operation below. Missing, unpinned, untrusted,
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
   - No `.git` → `git init -b main`.
   - Ask one question only when not derivable: greenfield or existing code?
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
   - Run `Seeds(<target>, init)` only when `.seeds/` is absent. Preserve existing queue/configuration.
   - Convert starting intent into 1–3 bounded Seeds, or derive them from accepted TODOs /
     issues. Never invent priority or silently import every TODO.
   - Record whether `.seeds/` is tracked or intentionally local according to repository
     policy. Never leave the queue empty while claiming Wave readiness.

4. **Merge the repository gate stack**
   - Existing `mise.toml`: parse and preserve its tools/tasks; propose only missing pinned
     tools and tasks. New file: pin the detected language toolchain, linters, `lefthook`,
     and `betterleaks`; create fmt/lint/test tasks that match the repository, one aggregate
     `check`, and a `setup` task. Never add speculative tools.
   - Git substrate: merge a marked Agentic SDLC block into `lefthook.yml`; pre-commit is the
     fast staged-file subset, pre-push includes tests and the working-tree secrets scan
     (`betterleaks dir .` with `--config` pinned at a tracked extend-only config, never the bare
     form — a drop-in config or `GITLEAKS_CONFIG*` variable otherwise replaces the ruleset). Preserve all
     foreign hooks. `setup` installs lefthook.
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
   - `AGENTS.md` is the cross-host canonical project policy. Create or append only inside
     `<!-- agentic-sdlc:start -->` / `<!-- agentic-sdlc:end -->` markers. Include project
     intent, `mise run check`, Git-worktree substrate, Seeds commands, worktree ownership,
     and the global doctrine pointer.
   - `CLAUDE.md` remains thin: preserve existing content, add the same marked block only
     when absent, and import/reference `AGENTS.md` plus Claude-specific command routing.
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

7. **Commit and receipt**
   - Re-run inventory and show exactly created, adopted, merged, skipped, and conflicted
     items. A rerun with no repository changes is the idempotency proof.
   - Commit only the enumerated activation files as one atomic commit after user approval.
     Never include the user’s pre-existing changes.
   - Report tracked-baseline evidence, gate fail→pass proof, initial Seeds, trust actions,
     remaining conflicts, and `/sdlc-frame <first milestone>` as the next step.
   - Claim **Git-wave-ready** only when observed evidence shows: clean tracked baseline,
     non-empty Seeds queue, `mise run check` passes, guidance/CI agree, required capability
     and worktree trust are verified, and any selected adapter/model is read back. This local
     claim does not authorize push, publication, PR mutation, merge, deployment, credentials,
     or another outward effect; each operation needs explicit operation-specific approval.
