# Session Handoff — 2026-07-21

> **Dated record, partially superseded.** Tracked 2026-08-06 as history, not current policy.
> The "Gateway is required for normal inference" boundary below is superseded by
> `docs/adr/0003-gateway-stance-downgraded-to-optional.md` (gateways are optional; the
> subscription-passthrough premise is ToS-blocked). The repository path below also predates
> the current checkout location. Everything else reads as a snapshot of 2026-07-21 state.

## Resume here

```bash
cd <repo>
```

This ext4 checkout is the sole active repository. Do **not** resume normal Git or mutation work under `/mnt/e`; that DrvFS checkout previously produced EIO/SIGBUS. `/mnt/e` is preservation/future batch-publication storage only.

## Exact repository state

- Branch: `release/offline-observer-rc`
- HEAD: `ada5ecd1ad3e2c9d6318cb869eeba045376d32bf`
- Tree: `783eecb964cd3ce923ed2623ec956d26c7b490f5`
- Upstream: gone; local branch/objects/refs are preserved.
- No commit, push, PR, merge, release, deployment, or `/mnt/e` synchronization was performed.

Current uncommitted write set:

```text
.gitattributes
.seeds/.gitignore
.seeds/config.yaml
.seeds/issues.jsonl
.seeds/plans.jsonl
.seeds/templates.jsonl
docs/progress/2026-07-21-product-progress-snapshot.md
SESSION-HANDOFF.md
```

`SESSION-HANDOFF.md` was added at the user’s request after the roadmap write set was verified. Treat it as intentional handoff state, not as part of the original seven-file roadmap write set.

## What was completed

### Dated progress snapshot

Created:

```text
docs/progress/2026-07-21-product-progress-snapshot.md
```

It preserves the user-supplied assessment:

- offline observer milestone: 100%;
- reusable foundations/contracts: 55–65%;
- complete user-visible vision: 25–30%;
- production PRIME → DRIVE journey: not available;
- capability matrix, verified lifecycle, overclaims, frozen candidate categories, three-slice path, and strategic milestone.

The document explicitly distinguishes product judgment, shipped bytes, frozen candidates, and external/session evidence. It is non-authorizing.

### Deterministic Seeds roadmap

Created a Git-native Seeds 0.5.14-compatible queue without using ambient CLI mutation:

- 18 fixed-ID issues;
- 22 unique bidirectional, acyclic dependencies;
- exactly one ready issue: `agentic-sdlc-p1`;
- 17 blocked issues;
- milestone: `agentic-sdlc-m0`;
- serial epics:
  1. `agentic-sdlc-p0` — Complete PRIME;
  2. `agentic-sdlc-g0` — Productize gateway-owned execution;
  3. `agentic-sdlc-d0` — Complete one bounded DRIVE mission.

Every description has `Objective`, `Acceptance`, and `Authority boundary` sections. Seeds remains state, never authorization.

### Host task-list reorganization at handoff time

The prior host session recorded the following task state. Task IDs are session-local and may be remapped after context restoration; match by title and dependencies rather than assuming the same numeric IDs still exist.

- `#2` was archived as the superseded architecture study.
- `#4` was the active roadmap-publication task.
- `#324–#327` were retained as inactive historical candidate lanes.
- New active serial coordination tasks were:
  - `#556` Execute Complete PRIME slice;
  - `#557` Execute gateway-owned slice, blocked by `#556`;
  - `#558` Execute bounded DRIVE slice, blocked by `#557`;
  - `#559` Assess installed product-path milestone, blocked by `#558`.
- `#497` remained pending until final acceptance/reconciliation.
- Historical agent tasks were not deleted or falsely completed.

## Verification completed

### Queue structure and compatibility

Passed:

- 18 records / 22 edges;
- exact fixed IDs/titles/types/priorities/labels;
- raw JSONL parsing;
- dependency symmetry and acyclicity;
- exact ready set `agentic-sdlc-p1`;
- transitive PRIME → gateway → DRIVE → milestone gating;
- all 18 `show` readbacks;
- all 18 `dep list` readbacks;
- credential-pattern scan: no matches.

Resolved config-free pinned tuple:

```text
Node 22.22.3
Bun 1.3.10
@os-eco/seeds-cli 0.5.14
```

Pinned read-only CLI results:

```text
list: 18
ready: 1 (agentic-sdlc-p1)
blocked: 17
doctor: pass=12, warn=0, fail=0
```

### Repository gates

Passed:

```text
validate-bundle: 0 errors, 0 warnings
focused offline observer: 8/8
full unit suite: 389 passed, 10 skipped
lifecycle self-test: passed
```

The first full-suite attempt had three environment-only failures because nested tests invoked untrusted `mise.toml`. No persistent trust was added. The accepted rerun used only:

```text
MISE_TRUSTED_CONFIG_PATHS=<repo>/mise.toml
```

in the process environment and passed 389/10 plus self-test.

### Evidence hashes rechecked

```text
e70f9ff617941fbe87388aa88bb42ac64a21d83319a83429b7dc731460d009f5  <home>/agentic-sdlc-offline-observer-rc-evidence/manifest.json
4c570ec8134486fa3245639d6c74526e0787810c9a45824b4648116905f44286  <home>/agentic-sdlc-offline-observer-rc-verification/devbox-docker-journey.json
da8f17347ea9a068c6b6204fba1c57fb494dd0e0aa79c55f75972ad5e1cb6efa  <home>/agentic-sdlc-offline-observer-rc-verification/devbox-docker-journey.provenance.json
```

## Late teammate results and evidence status

After this handoff was first written, delayed teammate messages arrived:

- `seeds-backlog-explorer`, `vision-gap-map`, and `roadmap-cold-review` all failed before substantive work because their transport rewrote the requested model to unsupported `us.anthropic.claude-opus-4-8`. They contributed **zero evidence or review coverage**. Do not wait for or cite them.
- `backlog-plan-designer` completed advisory planning and correctly warned not to use ambient `<bun-home>/bin/sd`; this implementation already used exact Bun 1.3.10 plus the mise-managed Seeds 0.5.14 entry for all compatibility checks.
- That planner later proposed a different 16-record/15-edge linear graph and extra `docs/roadmap.md`. Those suggestions arrived after the user-approved 18-record/22-edge graph was published and verified. They were not applied: the accepted graph already has exactly one ready issue and strict serial slice gates while preserving useful within-slice parallelism. Treat the alternative as unaccepted advice, not a migration instruction.
- The independent Codex outside-voice plan review did run successfully before implementation; its findings were incorporated by switching from ambient CLI mutations to deterministic Git-native publication.

## Pending before declaring the task done

1. No cold-review result is pending: `roadmap-cold-review` failed before execution and contributes zero evidence. If a new independent review is desired, launch it through a verified exact model route rather than resuming that failed agent.
2. Recheck the final write set, including this handoff file.
3. Leave `agentic-sdlc-p1` / “Execute Complete PRIME slice” as the next ready product implementation tranche; host task numbers may be remapped after restoration.
4. Do not commit unless the user separately requests it.

## Fast resume commands

```bash
cd <repo>
git status --short --branch -uall
```

The supported Seeds inspection path requires an explicit successful bootstrap and active tuple
receipt before `Seeds(<target>, ready --format json)` or
`Seeds(<target>, blocked --format json)`. This checkout currently has no active receipt, so do not
substitute ambient or direct Seeds execution. The accepted pinned readbacks are recorded above;
repeat bootstrap only with the required operation-specific approval.

For full gates without persistent trust mutation:

```bash
cd <repo>
UV=<mise-data>/installs/uv/0.11.17/uv-x86_64-unknown-linux-musl/uv
MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" "$UV" run --python 3.12.11 --with pyyaml==6.0.3 python -m unittest discover -s tests
MISE_TRUSTED_CONFIG_PATHS="$PWD/mise.toml" "$UV" run --python 3.12.11 --script scripts/install_skill_bundle.py self-test
```

## Controlling boundaries

- Gateway is required for normal inference.
- No direct/provider-native Claude fallback; provider-native Claude is diagnosis/recovery-only.
- Workflow selectors must use the exact approved `[1m]` forms with explicit effort.
- Credentials/management keys must not enter repositories, prompts, receipts, logs, or literal command arguments.
- Seeds is never authorization.
- One writer per checkout/write set; one serial integrator.
- Preserve foreign/dirty/historical work; no reset, clean, stash, prune, or discard.
- No push, PR, main merge, release, deployment, or `/mnt/e` batch sync is authorized.
