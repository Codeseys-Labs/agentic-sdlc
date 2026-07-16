# SDLC Loop

Use this reference when the task needs a full research, plan, implementation, review, and verification loop.

## Phase Gates

Frame:
- State the exact done condition.
- Read repo intent docs, roadmap, ADRs, and current queue state.
- Decide whether the run is direct, a provider-native delegation, or a worktree wave.
  discovered capabilities as candidates until required probes, trust, and adapter readback
  succeed; missing, unpinned, untrusted, or ambiguous capability fails closed.
- Set caps: worker count, worktree count, max review/fix rounds, and stop conditions.

Discover:
- Assign independent read-only workers by code area or risk lens.
- Require file/line evidence and "unknowns that would change the plan".
- Persist worker findings under a run directory such as `docs/agentic-runs/<date>-<slug>/`.

Research:
- Use HyperResearch only when external knowledge is load-bearing.
- Keep the canonical research query separate from wrapper requirements.
- Feed the final report path into Plan; do not paste large reports into prompts.

Plan:
- Load `model-tier-rightsizing` before planning a dispatch. Classify each workstream into the
  four semantic tiers; choose within the eligible Sol/Fable, Terra/Opus, or Luna/Sonnet pair
  by task fit, independent perspective, quota, and verified transport. Emit workstreams with
  owner role, target worktree, dependencies, files in scope, gates, rollback, caller-injected
  certified exact model ID, **explicit requested effort**, and requested context form.
  Provider-neutral roles do not select models; stop before dispatch when identity or adapter
  readback is unresolved. Record requested, resolved, inherited, and unresolved state
  separately. Roles and verdicts are advisory submissions; do not manufacture all-six usage.
- Return every actionable finding as a SeedProposal for conductor adjudication before Act;
  the conductor alone mutates Seeds.
- Mark workstreams that require Claude Code dynamic workflows.

Act:
- Give each worker one bounded workstream and a worktree path.
- Require tests and an artifact report.
- Use serial chains only when one workstream consumes another's output.

Review:
- Review diffs and stable snapshots, not only summaries.
- Use multiple lenses: correctness, tests, security/safety, UX/docs when relevant, and queue alignment.
- Return review findings as advisory SeedProposals for conductor adjudication.

Reconcile:
- Run gates from the root and from affected packages as needed.
- Turn findings into typed `SeedProposal` records for conductor triage. Only the conductor may
  authorize verified queue mutations under operation-specific policy; worker and reviewer roles
  never execute create/claim/update/close/sync actions.
- The conductor alone mutates Seeds after acceptance evidence is verified. An authorized
  integrator alone may perform an already-authorized fan-in; local status, passing gates,
  worker reports, reviewer recommendations, and conductor choices never grant authority.
- The conductor runs `Seeds(<target>, sync)` using the exact launcher contract in
  `references/seeds-worktrees.md` when the verified queue state changed.

Ship:
- Squash/rebase worktree branches into an integration branch only within the authorized scope.
- Preserve a clear commit message tying work to Seeds.
- Open a PR if the repo expects review; otherwise commit locally and report gates. Push,
  publication, PR mutation, merge, deployment, credential, and evidence-store operations
  require explicit operation-specific authorization.

## Backflow

Use backflow when a later phase invalidates an earlier one:

- Review finds a missed subsystem: re-enter Discover for that subsystem.
- Plan lacks evidence: re-enter Research with a targeted query.
- Act exposes a dependency: re-enter Plan to split or sequence workstreams.
- The done condition was wrong: stop and re-frame with the user if scope grows.

Backflow must be scoped. Add to existing artifacts; do not rerun the whole loop unless the frame is wrong.

## Done Criteria

Do not claim done until:

- Relevant Seeds are closed, blocked with explicit reason, or out-of-scope by user instruction.
- Tests/build/lints that cover the touched area pass or failures are proven pre-existing.
- Review blockers are resolved or intentionally accepted by the conductor with evidence.
- Worktree state is clean except for intentionally uncommitted artifacts.
- PR/commit status matches the repo policy.
