# Product Progress Snapshot — 2026-07-21

> **Status record, not authorization.** This document describes the product at the release identity below. It does not make a Seed ready, qualify a route, authorize an effect, or permit fan-in, push, release, or deployment.

## Release identity and evidence boundary

- Branch: `release/offline-observer-rc`
- Commit: `ada5ecd1ad3e2c9d6318cb869eeba045376d32bf`
- Tree: `783eecb964cd3ce923ed2623ec956d26c7b490f5`
- Snapshot date: 2026-07-21

The percentages below are product judgment, not machine-derived proof. Shipped release bytes, committed code on other refs, frozen/uncommitted candidate work, and architecture evidence are distinct categories. Failed agents—including `vision-gap-map`—contributed no evidence to this assessment.

## Bottom line

We are at the end of foundation-building and the beginning of the actual product.

Roughly:

- Offline observer release milestone: **100%**
- Reusable foundations and contracts: **55–65%**
- Complete user-visible vision: **25–30%**
- Production-ready PRIME → DRIVE journey: **not yet available**

The project is finally installable and useful, but what users can use today is an installer plus trustworthy offline inspection, not yet the full Agentic SDLC control system.

## Capability matrix

| Vision capability | Current position | Reality |
|---|---|---|
| Portable bundle installation | Strong | Skills, agents, and commands install, report status, update, migrate, and uninstall while preserving foreign files. |
| Offline repository inspection | Complete | The installed observer deterministically emits `create`/`adopt`/`merge`/`refuse`/`skip`, changes nothing, and uses no inference or subprocesses. See `skills/agentic-sdlc/SKILL.md:65`. |
| Safe PRIME activation | Shipped, narrowly (updated 2026-08-06) | Was "preview only" when this snapshot was written, and accurate then. The canonical `skills/agentic-sdlc/tools/activation-planner.py` now exposes `plan`, `apply`, `status`, and `recover` with 51 tests covering single-use grants, replay/expiry refusal, crash-after-publish rollback, and symlink-attack scenarios. Deliberately narrow: Linux-only, one entry per plan, and no greenfield/readiness/Seeds/trust/Git behavior. A procedural grant is a same-user single-use record, not an authenticated approval. |
| Required gateway routing | Canary proven, not productized | CLIProxyAPI/`claude-code-proxy` routed `gpt-5.6-sol` successfully and failed closed against a dead endpoint. The installed product does not yet enforce, qualify, or own this route. |
| Mixed-model Dynamic Workflows | Designed, not distributed | Model policy and `RuntimeAssignment` exist. No installed Workflow overlay or fixed DRIVE Workflow ships in the current bundle. |
| Seeds integration | Read-only subset | Pinned bootstrap and `prime`/`ready`/`blocked` inspection exist. There is no admitted conductor mutation seam for `init`/`create`/`update`/`dep` with CAS/readback. See `skills/agentic-sdlc/tools/seeds-launcher.mjs:868`. |
| Managed target-local worktrees | Not shipped | Current commands still prescribe sibling worktrees rather than managed target-local `.worktrees/`. See `commands/sdlc-wave.md:14`. |
| DRIVE execution | Doctrine and manual primitives | Roles, runbooks, review rules, and integration guidance exist. No deterministic mission engine performs immutable handoffs, fixed roles, review barriers, and serial WIP-1 integration. |
| Typed evidence/contracts | Partial | `RuntimeAssignment` and role contracts ship. `RouteQualification`, effect-operation, fixed-mission, `AttemptRecord`, and complete effect journals remain outside this release. |
| Human authorization boundaries | Strong doctrine, weak enforcement | The rules are well specified, but no complete effect engine binds and consumes single-use grants for fan-in and shipping. |
| Self-hosting | Partial proof | The repository produced and verified its observer milestone, but not through the envisioned installed PRIME → DRIVE loop. |
| Cross-host/release proof | Incomplete | Lifecycle code supports multiple hosts, but there is no accepted end-to-end cross-host conformance release candidate. |
| Historical archive and V7 | Frozen candidate/evidence only | Large implementation candidates exist outside the current release bytes. They require fresh custody, review, and slice-scoped promotion before they can count as product. |

## What is genuinely usable today

```text
install bundle
→ run installed offline inspection
→ receive deterministic preview and readiness
→ prove zero repository effects
→ inspect bundle status
→ uninstall safely
→ retain foreign files
```

That journey passed:

- 8/8 focused offline-observer tests;
- 389 passed, 10 skipped in the full process-scoped gate;
- 5/5 fresh Docker lifecycle assertions;
- gateway negative and live controls; and
- zero observer network calls and child-process launches.

This is a real product slice, not a mock. Users can also manually use the packaged role agents, runbooks, gate tooling, and Git doctrine. That remains an expert-operated kit rather than the promised control system.

### Evidence classification

| Evidence | Classification |
|---|---|
| RC manifest `<home>/agentic-sdlc-offline-observer-rc-evidence/manifest.json` — SHA-256 `e70f9ff617941fbe87388aa88bb42ac64a21d83319a83429b7dc731460d009f5` | Sealed external release provenance for the exact commit/tree and 143-path archive. |
| Docker report `<home>/agentic-sdlc-offline-observer-rc-verification/devbox-docker-journey.json` — SHA-256 `4c570ec8134486fa3245639d6c74526e0787810c9a45824b4648116905f44286` | Sealed external 5/5 lifecycle report. |
| Docker provenance `<home>/agentic-sdlc-offline-observer-rc-verification/devbox-docker-journey.provenance.json` — SHA-256 `da8f17347ea9a068c6b6204fba1c57fb494dd0e0aa79c55f75972ad5e1cb6efa` | Sealed external provenance for that Docker run. |
| Focused 8/8, full 389/10, gateway live/dead, and syscall controls | Preserved session acceptance observations tied to the exact release identity; not installed product files and not route/effect authorization. |

## Where current claims overreach

Three current surfaces imply more than the executable product delivers:

1. ~~`/sdlc-init` describes apply, receipts, deactivation, and Git-wave readiness, but the activation CLI supports only `plan`.~~ **Resolved 2026-08-06 in the opposite direction from what this line assumed:** `apply`/`status`/`recover` now exist, and it was the *runbook* that had drifted — it documented a `--profile` flag, a `deactivate` verb, an `activation-receipt.json` path, and receipt fields (baseline inventory, Seeds proof, gate fail→pass, trust decisions, `wave_ready`) that the narrowed tool does not provide. `commands/sdlc-init.md` is corrected against the verified CLI, and the broader activation journey is now stated as conductor-evidenced manual work rather than a planner guarantee.
2. README and skill doctrine still make provider-native execution the baseline (`README.md:3`, `README.md:29`, `skills/agentic-sdlc/SKILL.md:12`). That conflicts with the controlling requirement that the gateway is mandatory and provider-native Claude is diagnosis/recovery-only.
3. Worktree instructions still create sibling directories instead of managed target-local `.worktrees/` (`commands/sdlc-wave.md:14`).

These are product-capability and security-posture gaps, not documentation nits.

## Where the unfinished work lives

Five preserved candidate/evidence categories can inform future work, but each category may overlap shipped foundations; only its unintegrated bytes remain candidates:

- archive and vision relocation;
- additional typed contracts beyond the shipped `RuntimeAssignment` and role contracts;
- Workflow overlay lifecycle;
- PRIME/readiness; and
- Seeds/worktree hardening.

At the time of this assessment, the unintegrated candidates in those categories were based on another branch or frozen outside the current release, some with uncommitted work, and had not reached final integrated acceptance. Their Git objects/refs and recovery evidence are preserved, but none of those candidate bytes is present in `release/offline-observer-rc`. Shipped foundations named elsewhere in this snapshot remain shipped. The vision is not starting from zero; the preserved candidates simply cannot be counted as shipped progress.

## Shortest path to the vision

Do not restart the mega blocker loop. Finish three vertical product slices, serially.

### 1. Complete PRIME

```text
install
→ inspect
→ explicit approval
→ transactional apply
→ readback verification
→ status/recovery
```

Promote only the required PRIME/readiness and target-local worktree changes. This converts the observer into safe activation. PRIME owns a fail-closed handoff contract for later gateway execution; it does not productize the gateway itself.

### 2. Productize gateway-owned execution

Ship:

- Workflow overlay installation;
- the required CLIProxyAPI launcher;
- separate `RouteQualification`;
- exact selector/effort admission; and
- dead-gateway refusal with no provider-native fallback.

This turns the successful gateway canary into normal product behavior.

### 3. Complete one bounded DRIVE mission

Start with one deliberately narrow mission:

```text
frame
→ create/update Seeds through a lawful CAS seam
→ create 1–2 target-local worktrees
→ implement
→ immutable independent review
→ serial integration
→ reconcile Seeds
→ stop before shipping
→ request separate shipping authorization
```

Then dogfood that exact installed journey on this repository and one disposable downstream repository.

## Strategic assessment

The largest risk is no longer missing architecture. It is mistaking reviewed candidate work for an integrated product.

The next milestone should not be “close V7” or “finish all contracts.” It should be:

> A fresh user installs Agentic SDLC, safely PRIME-activates a repository, completes one gateway-routed DRIVE mission, and reaches a reviewed local commit without hidden effects.

Once that passes, the project will move from roughly 30% of the vision to around 70% in one coherent step.

**STATUS: DONE_WITH_CONCERNS**

The offline foundation is real and strong. PRIME, gateway ownership, Seeds mutation, DRIVE, and separate shipping authorization remain the critical unshipped path.
