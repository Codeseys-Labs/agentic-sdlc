# agentic-sdlc capability surface — SHIPPED vs DESIGNED vs ABSENT, judged against the source doctrine in AGENTS.md/README.md/SKILL.md/references and the prior-art harvest memos, with test-mapped evidence for every claim.


# agentic-sdlc capability surface: SHIPPED / DESIGNED / ABSENT

Verified 2026-08-05 against a live repo state (branch `release/offline-observer-rc`, HEAD `ada5ecd`) with an uncommitted PRIME-custody worktree (`skills/agentic-sdlc/tools/activation-planner.py`, `instruction-generator.py`, `tests/test_activation_transaction.py`, `tests/test_prime_candidate_custody.py`) layered on top of the last commit. Full suite: `python3 -m pytest tests/ -q` → **399 passed, 10 skipped, 705 subtests passed** (3m01s). This report distinguishes code-that-runs-with-a-test (SHIPPED) from prose-only doctrine (DESIGNED) from nothing at all (ABSENT), per the docs/progress snapshot's own self-assessment, which this review corroborates and refines with fresh execution evidence.

## 1. Bundle install / distribution lifecycle — SHIPPED

- `mise run bundle:install|status|uninstall` etc. described in `README.md:141-297`.
- Evidence: `tests/test_install_skill_bundle.py` (22 tests: symlink install, migrate-state dry-run/apply, ownership conflicts, Windows junction fallback described but tested via mocked paths), `tests/test_run_all_hosts.py` (36 tests for WSL/native-Windows dual-host reporting).
- Verdict: SHIPPED. This is the most mature, most heavily tested surface in the repo (170+ combined assertions across `test_install_skill_bundle.py` + `test_run_all_hosts.py`).

## 2. Offline repository inspection (`offline-inspect.py`) — SHIPPED, narrow scope

- `skills/agentic-sdlc/tools/offline-inspect.py` (275 lines). `--help` exposes exactly one flag: `--target TARGET`. No subcommands, no writes, no subprocess calls (confirmed by reading the file: stdlib-only, `--target` is the sole surface).
- Executed live: `python3 offline-inspect.py --target <repo>` → deterministic JSON: `{"schema":"agentic-sdlc/offline-inspect@1","items":[...],"preview_readiness":{"state":"READY","reason":"no_refusals"}}` with an explicit `"excluded-surfaces"` item whose `scope` lists `["PRIME apply","workflow overlay","gateway","routing","Seeds","archives","V7","config","queue mutation"]` — the tool itself declares its own boundary in-band.
- Evidence: `tests/test_offline_observer_rc.py` (8 tests: refuses malformed `.git`, adopts valid linked worktree gitfiles, detects stale AGENTS.md/CLAUDE.md bodies for merge, preserves atimes, deterministic copy/install/status/uninstall round-trip).
- Verdict: SHIPPED and exactly as advertised — this is the "offline observer" the RC branch is named for, and it is the one component the progress snapshot calls "Complete."

## 3. PRIME activation transaction (`activation-planner.py` + `instruction-generator.py`) — SHIPPED for `plan`/`status`/`recover`; `apply` SHIPPED but far more heavily tested than documented

This is the single biggest finding of this review, and it **corrects** the 2026-07-21 progress snapshot, which is now stale relative to the uncommitted worktree.

- The progress snapshot (`docs/progress/2026-07-21-product-progress-snapshot.md:17,84`) states: *"Safe PRIME activation: Preview only... the public CLI exposes only `plan`. There is no supported transactional apply → verify → recover journey."* That was true as of the `ada5ecd` commit (`scripts/activation_planner.py` at that point was a compatibility loader, and the canonical module was not yet present in that shape).
- Current uncommitted reality is materially more advanced. Live `--help` execution shows FOUR subcommands: `plan`, `apply`, `status`, `recover {inspect,finish,rollback}`. Live `status --target <repo>` returns a typed `agentic-sdlc/activation-result@2` schema with fields `approval_authenticated`, `effect`, `legal_recovery`, `operation_digest`, `plan_digest`, `receipt_digest`.
- `skills/agentic-sdlc/tools/activation-planner.py` is 2948 lines — this is not a stub; `apply` is fully implemented (grant-gated, CAS-based, crash-recoverable).
- Evidence: `tests/test_activation_planner.py` (7 tests, mostly compatibility-shim assertions) is the *old*, thin test file. The real coverage is `tests/test_activation_transaction.py` — **1824 lines, 40 test methods** — an adversarial suite covering: crash-durable custody binding, legacy-witness rejection, substituted-stage rejection on create/replace, private-namespace substitution rejection, live-product-drift rejection, forged-root-anchor handling, crash-after-publish rollback for both create and replace, hostile-git-environment redirection resistance, grant replay/expiry refusal, symlink attacks (private receipts, generator symlinks, transaction-directory symlink swaps, cleanup-directory symlink swaps), mount-boundary refusal, malformed-rollback/receipt handling, concurrent-apply-during-recovery refusal, `porcelain v2` path-with-spaces exactness, and same-content substitution-preserves-inode checks. Plus `tests/test_prime_candidate_custody.py` (291 lines) for custody handoff.
- Verdict: **SHIPPED**, and understated by the checked-in progress doc. The `apply` path is not "preview only" in the current tree — it is a fully implemented, adversarially tested transactional engine. However, this work is **uncommitted** (`git status --short` shows `skills/agentic-sdlc/tools/activation-planner.py` etc. as `??`), so it is SHIPPED-IN-WORKTREE, not SHIPPED-ON-`release/offline-observer-rc`. `commands/sdlc-init.md:19-27` still documents this apply→verify→recover journey in prose consistent with the newer code, meaning the doctrine was written ahead of (or alongside) the code landing — the commands/README have not yet been reconciled to declare `apply` non-preview, and `SESSION-HANDOFF.md`/the progress snapshot are dated 2026-07-21, predating this worktree's apply implementation.
- `instruction-generator.py` (200 lines): "Pure one-output renderer for the P2 activation transaction" per its own `--help`. Verified pure via `tests/test_instruction_generator.py` (4 tests: render is pure and does not dereference pointer, replace preserves foreign text with exact no-op output, closed-manifest rejects unknown/duplicate/bad paths, malformed-marker rejection).

## 4. Seeds queue integration (`seeds-launcher.mjs`) — SHIPPED for `bootstrap`/`inspect` read-only subset; write-mutation (`init`/`create`/`update`/`dep`) ABSENT

- `skills/agentic-sdlc/tools/seeds-launcher.mjs` (929 lines). Live `--help`-equivalent (any invalid argv) prints: `usage: seeds-launcher.mjs bootstrap --distribution <reviewed-distribution> | inspect --target <repository> (--version | prime | ready [--format json] | blocked [--format json])`. This is the full verb surface — confirmed by reading the argv grammar at lines 862-870 and 916-917: `inspect` accepts *only* `--version`, `prime`, `ready [--format json]`, `blocked [--format json]`.
- Live run in this environment: `node --version` → `v26.6.0`; running the launcher fails closed with `launcher Node version mismatch: expected 22.22.3, got 26.6.0` — this is itself evidence the version pin is mechanically enforced, not just documented (SKILL.md:33 and README.md:172 both assert exact Node 22.22.3/Bun 1.3.10 pinning; the tool refused to run under Node 26).
- Evidence: `tests/test_seeds_launcher.py` — 18 tests covering locked-tuple bootstrap/publish, git-probe isolation from repo/global config and hooks, rejection of nested/dirty/untracked distribution trees, wrong-Node rejection for both bootstrap and inspect, rejection of package execution controls and recursively nested package-control files, rejection of nested package-metadata/symlink controls, environment-filtering before exact Bun invocation, read-only git adapter enforcement, drift rejection (git adapter, receipt, launcher hash), exact exit-code/signal preservation, and one real (non-mocked) locked-tuple bootstrap+inspect test against hostile ambient config.
- Verdict: SHIPPED for the read-only `prime`/`ready`/`blocked` subset. The progress snapshot's claim — *"There is no admitted conductor mutation seam for `init`/`create`/`update`/`dep` with CAS/readback"* (`docs/progress/...md:17`) — is **confirmed still true** by the grammar check above: those verbs are not in the accepted argv list at all, so this is not merely undocumented, it is mechanically refused. This is DESIGNED (SKILL.md and README describe `Seeds(<target>,<args>)` as if general) but the *installed launcher itself* is narrower than the doctrine's shorthand implies — a real gap between prose and shipped verb surface, not just an omission.

## 5. Instruction/agent-guidance merge (AGENTS.md/CLAUDE.md marker blocks) — SHIPPED

- `commands/sdlc-init.md:5,110-116` describes marker-based merge (`<!-- agentic-sdlc:start -->`/`end`).
- Evidence: `tests/test_offline_observer_rc.py:205-236` — adopts only canonical instruction content + Claude preamble, marks stale bodies/wrong preamble for merge, preserves access times on reads. `tests/test_instruction_generator.py:45-59` — replace preserves foreign text with exact no-op output when nothing changed.
- Verdict: SHIPPED (render/merge logic), tested at the unit level; the `sdlc-init` runbook's end-to-end orchestration of this into a live repo is DESIGNED (a reviewed runbook, explicitly not "a deterministic activation engine" per its own frontmatter and AGENTS.md's own characterization).

## 6. Gateway-routed / mixed-model Workflow overlay — ABSENT

- README.md and AGENTS.md describe a `RuntimeAssignment` contract, `resolution_state`, exact model-ID injection requirements at length (README.md:150-163, AGENTS.md throughout).
- The progress snapshot is explicit and this review found nothing to contradict it: *"Required gateway routing: Canary proven, not productized... Mixed-model Dynamic Workflows: Designed, not distributed. No installed Workflow overlay or fixed DRIVE Workflow ships in the current bundle."* No gateway launcher, no `RouteQualification` type, no Workflow-overlay installer exists under `scripts/`, `skills/`, or `tools/` (confirmed by the full `fd`/`ls` sweep of `skills/agentic-sdlc/tools/` — only 4 tools exist: `offline-inspect.py`, `activation-planner.py`, `instruction-generator.py`, `seeds-launcher.mjs`, none of which touch a gateway).
- Verdict: ABSENT as shipped code. DESIGNED as contract/doctrine (`RuntimeAssignment` fields are enforced in *prose* across every command/reference file and validated as *doctrine consistency* by `tests/test_runtime_contract_validation.py`, but that test validates that the documents agree with each other, not that a running gateway exists).

## 7. Managed target-local worktrees (`.worktrees/`) — DESIGNED, not shipped; commands still prescribe sibling dirs (partially superseded by newer reference doc)

- Progress snapshot: *"Current commands still prescribe sibling worktrees rather than managed target-local `.worktrees/`... See `commands/sdlc-wave.md:14`."*
- Verified: `commands/sdlc-wave.md:14` (current, live file) still reads: `git worktree add ../<repo>-wt-<seed-id> -b work/<seed-id>-<slug>` — sibling-directory pattern, exactly as the snapshot describes. This claim is **confirmed still accurate**, not stale.
- However, `skills/agentic-sdlc/references/worktree-failclosed-tests.md` (227 lines, untracked, new since the snapshot) is a fail-closed *test-design contract* for isolated worktree dispatch — it explicitly states in its own SKILL.md pointer (line 180-184) that it is "A future implementer's spec, not evidence that this repo already runs isolated dispatch." This is honest self-labeling: DESIGNED, explicitly flagged as not-yet-shipped by its own text.
- Verdict: DESIGNED only. `commands/sdlc-wave.md` has not been updated to the target-local pattern the newer reference anticipates.

## 8. Mission loop / backlog-zero doctrine (`mission-loop.md`, `/sdlc-mission`) — DESIGNED, doctrine-consistency-tested, no execution engine

- `references/mission-loop.md` (109 lines) and `commands/sdlc-mission.md` (52 lines) describe an 8-class milestone taxonomy, WIP caps, priority formula, concurrent critique.
- Evidence: `tests/test_authority_corrections.py` (25 tests) and `tests/test_deep_work_loop.py` (11 tests) check that the mission-loop and deep-work-loop *documents* are internally consistent (advisory-only language, no bare `sd` mutation guidance, subject-agnostic authority guard, bounded delegation depth cap stated, effort-routing lanes named) — these are **prose-linting tests**, not tests of a running mission engine. No `mission_engine.py` or equivalent exists under `tools/`.
- Verdict: DESIGNED. The progress snapshot's characterization — *"DRIVE execution: Doctrine and manual primitives... No deterministic mission engine performs immutable handoffs, fixed roles, review barriers, and serial WIP-1 integration"* — remains accurate. `/sdlc-mission` is a slash-command prompt, not an engine; it delegates the actual work to the host's native subagent primitives at runtime, with no bundled orchestration code.

## 9. Model-tier-rightsizing routing — DESIGNED (policy) + SHIPPED (validation of policy self-consistency)

- `skills/model-tier-rightsizing/SKILL.md` (145 lines) and `references/model-routing-calibration.md` define the four-tier Sol/Fable, Terra/Opus, Luna/Sonnet, mechanical-floor scheme.
- Evidence: `tests/test_model_tier_rightsizing.py` (18 tests) — checks the calibration document's internal consistency (no static pins in provider-neutral roles, tiered-orchestration reference exists, research-team doc integration point named). This is doctrine-consistency testing, not a routing *engine* — there is no code that actually resolves a model ID at runtime; that remains "the caller/host must inject" per the doctrine.
- Verdict: DESIGNED, with SHIPPED self-consistency tests (the tests prove the doctrine doesn't contradict itself; they do not prove a working router exists).

## 10. Role agents (Claude `.md` × 7, Codex `.toml` × 24) — SHIPPED as artifacts, DESIGNED as enforced roles

- Confirmed counts: `agents/claude/*.md` = 7 (`sdlc-cartographer/critic/implementer/integrator/planner/researcher/reviewer`); `agents/codex/*.toml` = 24 total = 7 `sdlc-*.toml` + 17 under `agents/codex/research/`. These exactly match the counts stated in the task prompt.
- Evidence: `tests/test_role_manifest.py` + `tests/test_role_submissions.py` (43 combined tests) validate agent-file structure/manifest fields and that role outputs are typed `SeedProposal`-shaped submissions, not direct mutations.
- Verdict: SHIPPED as installable artifacts with structural tests; DESIGNED as *behavior* — the agents are prompt files interpreted by the host's native agent runtime; there is no bundled code that enforces the cartographer→planner→implementer→reviewer→integrator pipeline sequencing at runtime. Sequencing is asserted in prose (SKILL.md:193-198) and checked only for textual consistency, not executed by any harness in this repo.

## 11. Gate stack (mise/lefthook/betterleaks) — SHIPPED

- `skills/repo-toolchain-gates/SKILL.md` (263 lines) describes `mise run check` as authoritative.
- Evidence: `tests/test_gate_graph.py` + `tests/test_gate_receipts.py` (20 tests) plus the live full-suite run itself (`mise`-managed pytest invocation implied by AGENTS.md, executed here directly via `python3 -m pytest` — 399 passed/10 skipped/705 subtests passed) is itself proof the gate stack runs and passes.
- Verdict: SHIPPED — this is the one capability domain independently corroborated by actually running it during this review, not just reading its test file.

## 12. Change-writing / stacked-PR / cmux skills — SHIPPED as skill content, ABSENT as executable tooling

- `skills/change-writing`, `skills/stacked-prs`, `skills/stacked-prs-gh-cli`, `skills/cmux-event-bus-messaging` are pure-prose skills (69, 72, 91, 108 lines respectively) with no `tools/` subdirectory each.
- Evidence: `tests/test_change_writing.py` (8 tests including fixture-based "invented claim" detection and "forbidden fixtures" detection — this is the one prose-only skill with a runnable fixture-detection test, i.e. it tests a *linter* the skill instructs an agent to run mentally, not a shipped CLI), `tests/test_pr_safety_doctrine.py` (3 tests, cross-skill consistency), `tests/test_git_change_flow_router.py` (6 tests, router-doc consistency).
- Verdict: SHIPPED as reviewed, tested doctrine text; ABSENT as any installed executable (no `change-writing.py`, no `stacked-prs` CLI — these skills are pure guidance for the host's native LLM to follow, by design, per their own SKILL.md text).

## 13. jj VCS support — ABSENT (explicitly retired)

- `references/jj-vcs.md` is 4 lines — "a one-release refusal pointer" per SKILL.md:174. `tests/test_jj_retirement.py` (5 tests) confirms no `jj init` in any public task graph, jj is not a mise tool, no active jj guidance anywhere, and no wave-readiness overclaim tied to jj.
- Verdict: Correctly ABSENT and mechanically enforced as absent (a "retirement" test suite that fails if jj creeps back in) — an unusual but real form of shipped-ness: shipped *absence*.

## 14. Research-team / codex-research-os — SHIPPED as installer, DESIGNED as full 17-role operating doctrine

- `skills/codex-research-os/SKILL.md` (83 lines) + `scripts/install_research_os.py` scaffolds the 17-role TOML roster (`agents/codex/research/`) into a target repo.
- Evidence: `tests/test_research_os_launcher.py` (12 tests) — verifies every rendered build file is scanned, generated research-director literal guidance has no mutation leak, all generated roles use the certified `RuntimeAssignment` boundary, generated agent validator rejects static pins/runtime mutants/director-launcher/authority mutants, pinned research installer task runs `--help`, installer is standalone with packaged policy snapshots.
- Verdict: SHIPPED for the scaffolding/installer mechanics (well-tested against mutation/injection attacks on the generated files); DESIGNED for the actual "17-role research organization operating" claim — no test spins up 17 live agents and observes claim-ledger behavior; the tests check generated *artifacts*, not a running research org.

## Corrections to prior documentation

1. The `docs/progress/2026-07-21-product-progress-snapshot.md` claim that PRIME activation "exposes only `plan`" is **stale** relative to the current (uncommitted) worktree, which has a fully implemented, 40-test-covered `apply`/`status`/`recover` transaction engine. This is a genuine capability advance since that snapshot was written, not yet reflected in README.md, AGENTS.md, or `commands/sdlc-init.md`'s framing (though `sdlc-init.md`'s prose already describes apply/receipt/idempotence behavior consistent with the new code — the doc and code are in front of the snapshot together, but the snapshot itself is what's out of date).
2. The snapshot's claim about Seeds mutation absence (`init`/`create`/`update`/`dep`) is **confirmed still accurate** by direct grammar inspection of `seeds-launcher.mjs` (only `--version`/`prime`/`ready`/`blocked` accepted).
3. The snapshot's claim about sibling-vs-target-local worktrees is **confirmed still accurate**: `commands/sdlc-wave.md:14` is unchanged.
4. The gateway/Workflow-overlay absence claim is **confirmed still accurate**: no gateway code exists anywhere in `skills/`, `scripts/`, or `tools/`.

## Authorization/evidence boundaries: mechanical vs prose

- **Mechanically enforced**: Node version pin (seeds-launcher refuses non-22.22.3 at runtime, observed live in this review), Seeds verb allowlist (grammar rejects unlisted verbs before any execution), activation-transaction grant/CAS/crash-recovery (40 adversarial tests), jj absence (retirement test suite), generated-role-file mutation/pin rejection (research-os validator tests), gate-stack pass/fail (`mise run check` / pytest itself).
- **Prose-only (stated, not mechanically enforced by this repo's code)**: "roles/verdicts are advisory, only an integrator may fan-in," "human authorizes push/publication/merge/deployment," the entire mission-loop 8-class taxonomy and WIP-cap enforcement, model-tier selection at dispatch time (the doctrine says a "caller must inject" a certified `RuntimeAssignment" — this repo has no code that itself performs or blocks that injection; it only lints that the *doctrine text* says the right thing). This matches the project's own repeated self-description ("evidence is never authorization... roles/verdicts are advisory submissions") but it is worth being explicit: those authority boundaries are enforced by convention and doc-consistency tests, not by a running access-control system.
