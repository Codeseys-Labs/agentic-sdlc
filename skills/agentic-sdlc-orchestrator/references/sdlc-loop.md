# SDLC Loop

Use this reference when the task needs a full research, plan, implementation, review, and verification loop.

## Phase Gates

Frame:
- State the exact done condition.
- Read repo intent docs, roadmap, ADRs, and current queue state.
- Decide whether the run is direct, one CAO handoff, a worktree wave, or a full CAO/DWL loop.
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
- Emit workstreams with owner role, target worktree, dependencies, files in scope, gates, and rollback.
- Convert every actionable finding into a Seed before Act.
- Mark workstreams that require Claude Code dynamic workflows.

Act:
- Give each worker one bounded workstream and a worktree path.
- Require tests and an artifact report.
- Use serial chains only when one workstream consumes another's output.

Review:
- Review diffs and stable snapshots, not only summaries.
- Use multiple lenses: correctness, tests, security/safety, UX/docs when relevant, and queue alignment.
- Convert review findings into Seeds, then decide whether they block ship.

Reconcile:
- Run gates from the root and from affected packages as needed.
- Close or update Seeds only after acceptance evidence is verified.
- Run `sd sync` when the repo uses Seeds and queue state changed.

Ship:
- Squash/rebase worktree branches into an integration branch.
- Preserve a clear commit message tying work to Seeds.
- Open a PR if the repo expects review; otherwise commit locally and report gates.

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
