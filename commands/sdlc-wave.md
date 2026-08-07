---
name: sdlc-wave
description: Run one Seeds-backed worktree wave — select ready Seeds, spawn workers in worktrees, review, reconcile
---

Run ONE implementation wave of the agentic-sdlc loop. Scope: $ARGUMENTS

1. Load the `agentic-sdlc` skill (and its `references/seeds-worktrees.md`).
2. Select the wave: using the loaded skill's exact Seeds shorthand, pick independent Seeds from
   `Seeds(<target>, ready --format json)` with disjoint
   file ownership (cap 3-5). Broad architecture / CI / shared-contract changes get
   their own serial wave.
3. Create one worktree per write-capable worker, in-workspace under the gitignored
   `.worktrees/` substrate the loaded skill's `references/seeds-worktrees.md` owns:
   `git -C <repo> worktree add <repo>/.worktrees/<seed-id>-<slug> -b work/<seed-id>-<slug> <base>`
   Verify the target path does not exist before running this: git creates the `-b` branch
   before checking the path, so a refusal on an occupied path strands an orphan branch
   (executable proof: `tests/test_worktree_failclosed.py`). If that happens, delete the
   stranded branch (`git branch -d work/<seed-id>-<slug>`) before retrying. The full
   create/gate/review/integrate/reconcile/clean-up lifecycle, with the refusal and recovery
   case for each step, lives in the loaded skill's `references/worktree-lifecycle.md`; follow
   it there rather than improvising the remaining steps.
   Persistent `mise trust` and `~/.codex/config.toml` mutation are separate operations:
   obtain explicit operation-specific user approval for each exact worktree path before
   applying either after reviewing its checked-in config. Without that approval, use only a
   certified process-scoped test route such as `mise --no-config --cd <worktree> exec ...`,
   or stop. Missing, unpinned, untrusted, or ambiguous required capability fails closed; do
   not let workers bypass the repository gate.
4. Load `model-tier-rightsizing` before launching a model-dispatching worker. Classify each
   assignment into the four semantic tiers and choose within the eligible Sol/Fable,
   Terra/Opus, or Luna/Sonnet pair by task fit, independent perspective, quota, and verified
   transport. The conductor must supply a conductor-supplied certified `RuntimeAssignment`
   with a certified exact model ID before spawn. `resolution_state` must equal `resolved`;
   `request_injection_status` and `model_readback_status` must equal `verified`;
   `resolved_provider` and `resolved_model_id` must be non-unknown.
   The canonical receipt has exactly the policy-derived 16 fields: `schema_version`, requested
   model/effort/context, injection status/evidence, resolution/provider/model/basis/readback,
   and effort/context status/evidence; it has no `*_source` projections. Closed evidence binds
   its model/provider/effort/context values and digests to top-level receipt values. Validation
   proves only canonical internal consistency; the external authenticated harness alone admits
   and spawns. Requested, inherited, unresolved, or unverified model-identity assignments stop
   before dispatch and spawn, returning one advisory SeedProposal. Effective effort and context
   may be unavailable when the transport cannot expose them.
   Never copy requested effort or context into resolved/readback fields, and never require
   impossible effective readback after request injection and model identity are verified.
   Prompt prose does not enforce a model or effort. Do not use host-default selection or
   artificial all-six representation. Each worker prompt may carry the certified assignment
   as an audit copy, but receipts—not the prompt—are the enforcement boundary. It must also
   carry: Seed id + acceptance criteria, absolute worktree path, files in scope, gates to run,
   artifact report path, and requested context form.
5. If cmux is already active, optionally publish wave status. Native workers require neither
   cmux nor tmux.
6. Collect artifact reports. Review each worktree (diff + gates, not summaries) —
   use the sdlc-reviewer agent where available.
7. Reconcile: return findings as advisory SeedProposals for conductor adjudication. Only the
   conductor may authorize queue mutations; workers emit typed `SeedProposal` records and never
   execute create/claim/update/close/sync actions. A worker claim or report is never authority to
   accept, close, or mark work done. The conductor alone mutates Seeds, applying verified,
   operation-specific policy through the exact loaded-skill contract, squash/rebase accepted
   branches per repo policy, and removing merged worktrees (`git worktree remove`). An authorized
   integrator alone may perform an already-authorized fan-in after re-gating. Worker, reviewer,
   critic, Seed, gate, or local status claims never grant authority. Push, PR, merge, deletion,
   and other outward effects require explicit operation-specific human approval.
8. Report: wave summary — Seeds closed/blocked, gates run, worktrees merged/kept,
   findings carried forward.
