# Feature-by-Feature Review: agentic-sdlc vs pi-lab, judged against both projects' source corpora

**Scope:** agentic-sdlc `release/offline-observer-rc` @ `ada5ecd` + uncommitted worktree, against pi-lab (`19775798`) and siblings `pi-agentic-sdlc-skills`, `pi-dynamic-fractal-workflows`, `pi-bedrock-mantle`, `bedrock-mantle-frontier-bundle`, `pi-lab-doc-skills`, plus the 13 memos in `docs/research/` and pi-lab's 23 ADRs.
**Method:** every load-bearing claim re-executed in this pass. Full agentic-sdlc suite: **399 passed, 10 skipped, 706 subtests, 179s**. Also executed: pi-lab `bun test` on 6 suites, `bun run secrets`, `pi-dynamic-fractal-workflows` `npx tsx --test` on 4 suites, `pi-bedrock-mantle` `bun test`, `pi-agentic-sdlc-skills` selftest + a live `chargePass` refusal, `claude plugin validate --strict` on three targets, the research-OS generator into a scratch dir, and a clean clone of HEAD.

---

## 1. Verdict up front

agentic-sdlc decisively leads pi-lab on **distribution and provenance**: four host manifests installed by one 82-test installer with v1→v2 ownership-state migration (`scripts/install_skill_bundle.py:1196,1300,1329,2613`), a Node/Bun-pinned Seeds acquisition chain that fails closed on the wrong interpreter (`skills/agentic-sdlc/tools/seeds-launcher.mjs` — executed: `expected 22.22.3, got 26.6.0`, exit 2), and real CI on three OSes (`.github/workflows/validate.yml:27`) against pi-lab's **zero CI, zero armed hooks, and its own admission that it "has never delivered a capability to anybody"** (`pi-lab/docs/assessment/20260727/README.md`). It trails pi-lab on **every mechanism that must actually refuse something at runtime**: pi-lab's siblings ship an executed pass-budget counter holding agentic-sdlc's *own* integers (`pi-agentic-sdlc-skills/extensions/sdlc-mission.ts:540` — executed: frame pass 2 → `REFUSED`), a 598-line tested budget/depth ledger (`pi-dynamic-fractal-workflows/src/frame-ledger.ts`, 46 tests pass), a 9-case executed fail-closed worktree-isolation suite against agentic-sdlc's 227-line self-labelled *non-executable* spec, receipt-vouching that closes two reproduced exploits (`pi-lab/src/core/receipt-vouch.ts`, 20 tests), and a secrets gate that is an actual leaf of its authoritative `check` (`pi-lab/scripts/check.ts:510`) where agentic-sdlc's is pinned but wired nowhere (`mise.toml:98-100` `depends = ["validate","test","self-test"]`). Both fall short of their own sources on three axes: the gateway (agentic-sdlc's memo designed Probes A–F, never ran them; the working harness sits unintegrated in `bedrock-mantle-frontier-bundle/config/gateway.qualification.example.yaml`; the cost premise is ToS-blocked), **effort/context readback honesty** — where agentic-sdlc's code does the *opposite* of its doctrine (`receipt_admission.py:357-362` requires observed == requested, so a pure request echo validates and an honest divergence is refused) — and the mission loop's end-to-end path, which cannot run because Seeds is read-only by construction (`seeds-launcher.mjs:866-870`). The single most under-reported fact: **agentic-sdlc's strongest capability is not committed on any branch** — `git log --all -- skills/agentic-sdlc/tools/activation-planner.py tests/test_activation_transaction.py` is empty; a fresh clone of HEAD has a 441-line planner exposing `choices=["plan"]`. And the newest finding in this pass: the uncommitted refactor **silently broke the tracked `/sdlc-init` runbook** — `commands/sdlc-init.md:20`'s documented invocation now dies in argparse.

---

## 2. Master parity matrix

Verdict codes: **A▲** agentic-sdlc ahead · **P▲** pi-lab (or a pi-lab sibling) ahead · **=** parity · **⊥** both short of sources. **†** = a verifier overturned the crosswalk's verdict and this row uses the corrected one. Grades: SHIPPED = running code with a test that exercises it; DESIGNED = prose/doctrine only; ABSENT.

### Orchestration

| Feature | Sources prescribe | pi-lab | agentic-sdlc | V |
|---|---|---|---|---|
| 7-phase loop shape | ECC-observed anchors, but pi-lab's own `skills/house/loop-design/SKILL.md:11` disclaims all enforcement † | DESIGNED, standalone portable skill, off the load path (ADR-0008) | DESIGNED, `references/deep-work-loop.md:14` exact string; `tests/test_deep_work_loop.py:127` asserts the literal | = |
| Stop conditions externally adjudicated | pi-lab loop-design | DESIGNED | DESIGNED + honestly cited: `deep-work-loop.md:178` "(adapted from pi-lab's loop-design skill)" | = |
| **WIP caps (impl≤3/research≤2/integration≤1/critique≤1/nesting≤2)** | No external standard; both projects' own doctrine | **SHIPPED, same axis, same integers** †: `pi-agentic-sdlc-skills/schemas/frame.schema.json` — `impl` max 3, `waveSize` max 3, `integration` `{"const":1}`, `critique` max 1, `nesting` max 2; runtime fan-out `chains/sdlc-wave.chain.json:30,42` `maxItems:3`; drift check executed → `ok caps-agree [EXECUTED] 7 caps match` | **ABSENT as code**: `rg -ln "WIP\|nesting\|pass_budget\|backflow\|delegation_depth" scripts/ skills/*/scripts/ skills/agentic-sdlc/tools/` → **zero hits**. Numbers live only in `commands/sdlc-mission.md:31` | P▲† |
| **Backflow pass budgets (global≤6, frame≤1, discover/research/plan≤2, act≤3)** | agentic-sdlc's own `commands/sdlc-mission.md:39-41` | **SHIPPED, dedicated counter** †: `extensions/sdlc-mission.ts:540` `PASS_BUDGETS = {global:6,frame:1,discover:2,research:2,plan:2,act:3}` — character-identical; `chargePass` persists before delegation. Executed: `frame allowed=true pass 1/1` → `frame allowed=false REFUSED: frame budget 1 exhausted` | DESIGNED, and worse than claimed: `rg "≤" tests/*.py` matches **nothing** — no test asserts any of the integers | P▲† |
| Bounded delegation depth | `pi-dynamic-fractal-workflows/src/workflow-capability-contract.ts:349` "depth cap (default 3, ceiling 5)" | SHIPPED: `config.ts:50,57`; `DEPTH_CAP_EXCEEDED` non-retryable (`workflow-tool.ts:39`); 18/18 pass incl. "request for depth 99 is CLAMPED" | DESIGNED: `mission-loop.md:56`; `test_deep_work_loop.py:180` regexes `delegation.{0,80}(cap\|bound)` — never the number | P▲ |
| Budget ledger / no-superset / wind-down reserve | `frame-ledger.ts`; `capability-map.md` calls it the ecosystem's most mature asset | SHIPPED, 598 L: `createChildLedger:290` `grant: Math.min(clampGrant(...), parent.grant)`; `windDownReserveThreshold:493`; 28 tests + red guard "nothing outside shrinkGrant() assigns to a grant". Executed 46/46 with depth suite | ABSENT as code; DESIGNED as prose | P▲ |
| Mission/backlog-zero doctrine | Original to agentic-sdlc | Byte-identical copy †: `diff` exit 0 vs `pi-agentic-sdlc-skills/skills/agentic-sdlc-orchestrator/references/mission-loop.md` — but wired to the enforcement above | **Author** (`084a373`, 2026-07-04 vs `7abc400`, 2026-07-25), SHIPPED as prose, 109 L, 8-class taxonomy + priority formula. Cannot run: Seeds mutation admits no verb | =† (agentic-sdlc authored; pi-lab enforced) |
| Worktree wave / git hygiene | `pi-lab-doc-skills/skills/git-hygiene/SKILL.md` (99 L) | SHIPPED as prose | SHIPPED as prose, verbatim: `seeds-worktrees.md:127,132,145,154,163` (branch-before-first-edit, one-commit-per-step, `cp -al` hardlink, stagger the gates) | = |
| **Fail-closed worktree isolation tests** | `tests/worktree-isolation-failclosed.test.ts` | SHIPPED, 374 L. **Executed: 9/9 pass, 13.9 s** (occupied branch, non-git cwd, throwing observer, mid-flight abort, timeout) † (9 cases, not 18) | DESIGNED, self-labelled: `references/worktree-failclosed-tests.md:7` "nothing here is executable — it is a specification a future implementer turns into real Python tests." `fd worktree tests/` → nothing | P▲ |
| Fan-in / integration authority | Both corpora's doctrine | SHIPPED as a **structural** refusal †: `schemas/integration.schema.json:22` `"pushed": {"const": false}` — "the schema refuses to represent a push"; `declinedOutwardOps` + `gateHashReasserted` required; integrator is a non-parallel step | DESIGNED, broadest coverage + doc-lint: `sdlc-wave.md:47-55`, `tiered-orchestration.md:50-53`, `tests/test_authority_corrections.py`. No code gates a real merge | P▲† on mechanism; A▲ on breadth |
| Model-tier routing wired into loop phases | agentic-sdlc's own doctrine | DESIGNED-as-antipattern †: all 9 `pi-agentic-sdlc-skills/agents/*.md:5` carry hard `model:` pins (`bedrock-mantle/openai.gpt-5.6-sol` etc.) — the opposite discipline | SHIPPED as a repeated hard gate across 5 files + 41-test contract suite | A▲ |

### Model routing

| Feature | Sources prescribe | pi-lab | agentic-sdlc | V |
|---|---|---|---|---|
| `resolved`/`inherited`/`unresolved` model-identity gate | Nothing external; pi-lab's `driven-agents.md:143` admits the analogous auth problem is unsolved | ABSENT (`rg "resolution_state"` → 0 hits) | **SHIPPED as a fail-closed refusal** (not a tri-state enum †): `receipt_admission.py:420` `if receipt["resolution_state"] != "resolved"`. Executed plants: `inherited`→refused, `unresolved`→refused, `model_readback_status=unavailable`→refused, `resolved_model_id=gpt-4`→refused with 2 errors. `inherited`/`unresolved` exist only in prose | A▲† |
| Three-rung route qualification (catalog-only/route-probed/role-qualified) | `pi-lab/docs/route-ledger/route.schema.json:130-137` (pre-existing enum) | SHIPPED schema + **populated data** (17 probed-positive, 4 negative, 1 unprobed — recounted †), 8-test invariant. **But inert**: `pi-lab/scripts/lib/capability-crosswalk.ts:337` "`docs/route-ledger/*` is read by no code" | DESIGNED: `model-routing-calibration.md:227-240` reproduces the vocabulary verbatim; no ledger file, no writer | P▲ on data only † |
| Precedence `observed > declared > mined` | `right-sizing-design.md:152-172` | DESIGNED †: `rg -nw "mined"` over pi-lab `src/ scripts/ schemas/` → **zero** | DESIGNED (`model-routing-calibration.md:209-220`) | =† (both designed) |
| **Effort/context readback honesty** | Memo Probe F: no candidate gateway satisfies the readback bar (`gateway-selection-memo.md:100-112`); AGENTS.md:95 "requested values never become readback" | DESIGNED, unresolved | **DESIGNED, and the code inverts it** †. `receipt_admission.py:357-362`: `if evidence[value_key] != top_level: errors.append(...)`. Executed: a receipt whose "observed" values are a copy of the request → `errors: []`, exit 0, digest `1450e0b1…` = `sha256({"effort":"high"})` (derivable by anyone holding the request); an **honest divergent** readback (`observed_effort: medium` vs requested `high`) is **rejected**. The anti-copy test (`tests/test_runtime_contract_validation.py:1158-1172`) passes only on a misspelled field (`request_bytes_sha256` vs `readback_bytes_sha256`) — a shape rejection, not provenance | ⊥† |
| Multi-provider routing extension | Not memo-prescribed (memo is about an HTTP OAuth gateway) | SHIPPED: `pi-bedrock-mantle/extensions/mantle/*.ts` 1,026 L. **Executed: 107 pass, 506 expect(), 9 files** † (not 34), incl. `no-unverified-widening.test.ts` | ABSENT (`rg -in gateway AGENTS.md README.md` → exit 1) | P▲ |
| Gateway qualification harness | Memo Probes A–F, unrun | Out of scope by verdict (`right-sizing-design.md:703-726`, with three falsifiable reopen conditions) | Exists in a sibling, unintegrated: `bedrock-mantle-frontier-bundle/config/gateway.qualification.example.yaml` (60 L, credential-scrubbed, `switch-project:false`, `request-retry:0`) driven by `scripts/qualify-cohort:271` + `tests/test-gateway-offline.sh` | ⊥ |
| Dynamic multi-model Workflow policy | **No source prescribes it** — so "both short of sources" was void † | ABSENT from installable surface | ABSENT from installable surface; the 199-line 12-invariant policy lives in `bedrock-mantle-frontier-bundle/config/dynamic-workflow-routing.md` | =† (both absent; no source gap) |
| Gateway-mandatory policy stance | Memo's own addendum: ToS-blocked, "a decision for you" | Resolved "no", with falsifiability | **Self-contradictory across layers**: committed `AGENTS.md`/`README.md` = zero gateway mentions; untracked `SESSION-HANDOFF.md:65,79,96` + `docs/progress/…snapshot.md:34,81,115,151` = "gateway required for normal inference", self-flagging the README conflict at `:81` | ⊥ |
| Static model pins forbidden in neutral roles | Per-repo-profile memo; pi-lab's own right-sizing design | ABSENT/inverted † (9/9 agents pinned) | SHIPPED: `tests/test_model_tier_rightsizing.py:371-377` parses frontmatter/TOML and asserts `"model" not in metadata`; 22 tests / 287 subtests pass. **But the skill-side half of this gate is uncommitted** — `git show HEAD:scripts/validate_bundle.py` `validate_skills` (lines 386-400) has no model-pin check | A▲ |
| Toolchain-version pin as a runtime refusal | Not source-prescribed | n/a | SHIPPED: executed, `seeds-launcher.mjs` refuses Node 26.6.0, exit 2 | A▲ (narrow) |

### Evidence, authorization, gates

| Feature | Sources prescribe | pi-lab | agentic-sdlc | V |
|---|---|---|---|---|
| Evidence-class anti-inflation rule | `pi-lab/skills/house/evidence-discipline/SKILL.md:27` | DESIGNED (tracked) | DESIGNED (`references/evidence-discipline.md:18-20`, word-for-word) — **untracked** | =† (pi-lab's is landed) |
| **Receipt-vouching against re-derived manifest authority** | `receipt-vouch.ts` header names two reproduced exploits with commits | SHIPPED, 327 L: `:224-225` `payload-entry-unaccounted` completeness check. Executed: 72 pass across vouch + live-profile + journal | ABSENT as a pass. `activation-planner.py:1795` re-derives `manifest_sha256` on **apply only**; `_recover`(2695)→`classify_recovery`(2449)→`_load_operation`(2428) authorize finish/rollback from the target's own private records + a grant, never re-reading the manifest — the exact "receipt is its own authority" shape pi-lab's module exists to refuse | P▲ |
| Key-level settings ownership + multiset reversal | **ADR-0020:81 / ADR-0022:197**, not ADR-0001 † | SHIPPED, 785 L: `live-profile.ts:34` 4-key allowlist; `:695-698` "REMOVE THE RECORDED MULTIPLICITY, NOT EVERY MATCH… reproduced end-to-end with `[p, p]`"; 34+8 tests | Different problem (path-level, not key-level). `rg "multiset\|multiplicity\|Counter" scripts/install_skill_bundle.py` → nothing † | ≠ (not comparable) |
| Single-use, expiring procedural grants | agentic-sdlc's own doctrine | ABSENT (its analog is a typed `--acknowledge-payload-change` digest, no consumed state) | SHIPPED: `GRANT_SCHEMA:36`, `scan_grant_ledger:1773` "procedural grant already consumed", `_consume_grant:1519`; `test_grant_replay_and_expiry_are_refused:441`. **Uncommitted** | A▲ |
| Transactional apply → status → recover | pi-lab ADR-0012 | SHIPPED + **field evidence**: `docs/dogfood/2026-07-31-two-foreign-projects.md:35,40` — byte-for-byte restore, "six refusals provoked, all exit 2"; 18+5 tests | SHIPPED, denser adversarial: 51 tests (17 forgery/substitution/symlink, 4 distinct symlink attacks at :514,528,810,843), executed green in 36.7 s. Zero field evidence. **Uncommitted** | =† (pi-lab: shipped+field; agentic-sdlc: denser but uncommitted) |
| Gate receipts (self-hashing, argv+toolchain-bound) | agentic-sdlc's own spec | Narrower analog that **runs**: scanner-identity attestation printed inside the gate | SHIPPED as a library, 80 L, 4 tests — **zero producers** †: `rg "gate_receipt\|build_receipt" --glob '!tests/**'` → the module and one SKILL.md. Not in `mise.toml`, `lefthook.yml`, or CI | P▲† (a running control beats an uncalled library) |
| **Secrets-scanner qualification + gate-chain membership** | pi-lab ADR-0006/0009/0014: absolute-path resolution, byte digest, version proven by spawn, exit 78 identity / 75 timeout | SHIPPED and sophisticated; **and it is a leaf of the authoritative gate** † (`scripts/check.ts:510` → `bun run secrets`; executed: `betterleaks 1.7.0 … no leaks found`). 32+15 tests (ADR-0006's "43" is stale †). No armed hook, no CI | Pinned only, **not gated**: worktree `mise.toml:34` `[tools."github:betterleaks/betterleaks"]` 1.7.3 + `mise.lock:150-171` per-platform checksums, but `[tasks.check]:98-100` excludes it and `lefthook.yml` (11 L) wires only validate/test/self-test. `skills/repo-toolchain-gates/SKILL.md:97` says so honestly. **The pin itself is uncommitted** (`git show HEAD:mise.toml \| rg betterleaks` → nothing). No runtime artifact-identity re-qualification | P▲† |
| CI existence | — | **ABSENT**: no `.github`, no `lefthook.yml`, `core.hooksPath` unset | SHIPPED: `.github/workflows/validate.yml:27` `mise run check`, 3 OSes, on push+PR | A▲ |
| Evidence-is-never-authorization in code | Both doctrines | One live judgement against an external document (`vouchEntry`) | One **tautology** †: `approval_authenticated: False` validated `is not False` at `activation-planner.py:952,969,1002,1584`, constructed at `:1486,2209` — no code path ever sets `True`, so it forbids nothing an attacker wants | P▲† |
| Install/ownership state machine (v1→v2, foreign/owned/conflict) | agentic-sdlc's own AGENTS.md | No comparable problem | SHIPPED, committed, green: `install_skill_bundle.py:427,472,1196,1300,1329,1494`; 82 tests. **The one row where SHIPPED is fully earned** | A▲ |

### Skills & distribution

| Feature | Sources prescribe | pi-lab | agentic-sdlc | V |
|---|---|---|---|---|
| Agent-Skills conformance gate | agentskills.io; AGENTS.md | Not the same standard | SHIPPED at HEAD (name==dirname, ≤1024, ref-existence — `validate_bundle.py:414-436`; executed `0 error(s), 0 warning(s)`; `install-skill-bundle.sh self-test` → `self-test passed`). Semantic model-pin ban is **uncommitted** † | A▲ |
| Skill admission/promotion/retirement doctrine | `pi-lab/skills/house/skill-authoring-standard/SKILL.md` (459 L, four-gate at :134, ≥2-of-5 at :181) | DESIGNED, landed | DESIGNED, faithful port (`references/skill-authoring.md`, 181 L), self-disclaiming at `:9`, **untracked** † | =† (pi-lab's landed) |
| **Description-byte selection budget as a gate leaf** | ADR-0008: a *generated*, gate-asserted figure that caught a real two-wave merge collision | SHIPPED: `docs/skill-loading-path.md:55` `total \| 22 \| 15528`; byte-identity leaf `tests/unit/skill-loading-path.test.ts:170` `expect(committed).toBe(renderMatrix(rows))`; executed 17 pass | ABSENT. `skill-authoring.md` §5 explicitly declines to publish a corpus figure. I measured what's missing: **3,563 bytes across 8 skills** | P▲ |
| **Vendoring prerequisite (LICENSE/NOTICE)** | Every vendoring memo names it as blocking | **SHIPPED** †: `LICENSE` 1,079 B MIT + `NOTICE` 20,187 B with a full donor record (`NOTICE:45-58`: ECC pinned `0c1d7be9…`, MIT, `LICENSE` blob `b832b6f6…`, harvested-file blob) and **one shipped attributed derivation**, `skills/house/loop-design/references/external-anchors-and-loop-shape.md` (9,807 B) | **ABSENT**: `ls LICENSE NOTICE` → both missing; `.claude-plugin/plugin.json:8` `"license": "UNLICENSED"`. 0 of 6 memo-specced skills exist (`ls skills/` → the same 8) | P▲† |
| Plugin/direct-install plane coexistence | agentic-sdlc's coexistence memo | No analog | SHIPPED, committed: `install_skill_bundle.py:2613` blocks per-Claude-plane only (`entry.agent == "claude" and claude_blocked`) | A▲ |
| Cross-host manifests | Agent-Skills cross-host goal | Explicit non-goal (one runtime) | SHIPPED: `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`, `gemini-extension.json` (`contextFileName: AGENTS.md`), bare tree; `tests/test_run_all_hosts.py` 8 tests | A▲ |
| doctor/repair split, idempotent status | ECC pattern | `pi doctor` returns `unhealthy` but does not set an exit code (`src/cli.ts:601-611` returns without touching `process.exitCode`); one real field drift catch | `bundle:status` inspects without rewriting; 82 installer tests. No `doctor`/`repair` split | A▲ (mixed: pi-lab has the field catch) |
| Hooks (PreToolUse guardrail) | mattpocock MIT skill; `judge-verdict.md:136-180` hand-executed a working `ask`-only hook | Not evaluated | ABSENT: no `hooks/`, no `hooks.json`, no `vendor/` | ⊥ |
| MCP servers | Both agentic-sdlc designs **reject** shipping `.mcp.json`; pi-lab ADR-0021 independently says zero default servers | Recorded as an ADR | Correctly ABSENT, matching its sources — a clean evidence-backed non-feature | A▲ (declines well) |
| Decision records | Both corpora | **23 ADRs** | **0**. `fd -t d -i adr` → nothing. An ADR skill was *specced* (`2026-08-05-adr-skill-spec.md`, 330 L) and never built | P▲ |

### Research / docs skills *(no crosswalk was delivered for this domain — these rows are my own first-hand checks; see §8)*

| Feature | Sources prescribe | pi-lab | agentic-sdlc | V |
|---|---|---|---|---|
| Research-team claim ledger | `autoresearch-lab-blueprint.md` (311 L spec) | DESIGNED in prose | **SHIPPED as a generator**: `skills/codex-research-os/scripts/install_research_os.py` (1,155 L). Executed into a scratch dir → Makefile + 10 scripts; planted an incomplete claim → `validate_claims.py` exit **1** with `ERROR: C1: missing assumptions, claim, claim_type, counterevidence, evidence, last_updated, owner_agent, validation_required`. 12 launcher tests pass | A▲ |
| Evidence ladder / claim rungs | Both | pi-lab's evidence-discipline house skill | DESIGNED in-repo (`references/research-team.md:18-34`, 114 L); the executable ledger only exists in *generated target* repos | = |
| Commit / PR / docs writing skills | `docs-commits-skills-spec.md` (547 L, 6 skills specced) | `skills/commits/conventional-commits`, `skills/docs/adr-authoring`, `pi-lab-doc-skills/{git-hygiene,diagrams,ste100,adr-authoring}` | `skills/change-writing` + 6 references (commit, pull-request, squash, draft-review, evidence-order, attribution-policy), 10 prose-only tests. 0 of 6 specced skills built | P▲ on breadth; = on the committed core |
| Seeds as a live queue | Both | 830 issues in `.seeds/issues.jsonl` | **18** | P▲ |

---

## 3. Shipped vs designed reality check — the honest count

I classified all 23 test files by whether they import/execute code or only read markdown.

| Class | Tests | Files |
|---|---|---|
| Exercises code only | **207** | 8 |
| Exercises code **and** asserts on prose | **125** | 7 |
| **Asserts on prose only — no code runs** | **77** | 8 |

**Genuinely SHIPPED (running code + a test that exercises it):**

1. **Bundle installer + ownership state machine** — `scripts/install_skill_bundle.py`, 82 tests, committed, green, plus `install-skill-bundle.sh self-test` passing and CI on 3 OSes. The most solid thing in the repo.
2. **Seeds bootstrap/inspect launcher** — `skills/agentic-sdlc/tools/seeds-launcher.mjs`, 18 tests, committed. Executed: refuses Node 26.6.0; grammar at `:866-870` admits exactly `--version | prime | ready [--format json] | blocked [--format json]`; `tests/test_seeds_launcher.py:451` plants `"create"` and asserts refusal.
3. **Offline inspector** — `tools/offline-inspect.py` (275 L), 8 tests. Executed: emitted a one-line canonical JSON preview with `adopt`/`merge`/`skip` and wrote nothing.
4. **Bundle validator + role manifest** — `validate_bundle.py` + `policy/role-manifest.v1.json` (24 roles), 35 RED-first mutation tests that prove the manifest cannot become a bypass channel.
5. **Receipt admission validator** — `receipt_admission.py`, 462 L, committed, stdlib-only, genuinely fails closed on `resolution_state`/`model_readback_status`/`resolved_model_id` (executed plants above). **Caveat: zero non-test callers**, and its readback binding is inverted (§7).
6. **Research-OS generator** — 1,155 L, produces a working claim/experiment validator (executed, exit 1 on a bad claim).
7. **Cross-host manifests + all-hosts runner** — 4 manifests, 8 tests.
8. **Activation transaction** — 2,948 L, 51 tests, executed green: single-use grants, replay/expiry refusal, crash-after-publish rollback for create and replace, 4 symlink-attack scenarios, same-content substitution preserving external inode. **Not committed on any branch.**
9. **Instruction generator** — 200 L, 4 tests. Also uncommitted.
10. **Gate receipt library** — 80 L, 4 tests, committed — but **no producer anywhere**, so it is shipped code that nothing calls.

**DOCTRINE ONLY (no code, however confidently written):**

- Every numeric bound in the mission loop. `rg -ln "WIP|nesting|pass_budget|backflow|delegation_depth"` over `scripts/`, `skills/*/scripts/`, `skills/agentic-sdlc/tools/` → **zero hits**. No counter, no query, nothing reports current WIP.
- Backflow, wind-down, resource floor, global pass ceiling.
- The concurrent critique team auditing squash-merged snapshots.
- Worktree waves, git hygiene, hardlinked deps, staggered gates — all prose.
- Fail-closed worktree isolation — a 227-line spec that says at `:7` it is not executable.
- Evidence-class discipline, skill-authoring admission/promotion/retirement.
- Effort/context readback honesty (and the code contradicts it).
- Route provenance (`declared`/`mined`/`observed`) and the three qualification rungs — vocabulary with no ledger.
- The `inherited`/`unresolved` half of the RuntimeAssignment tri-state (only `resolved` exists in code).
- The gateway, in its entirety.
- 5 of 8 skills are pure prose: `cmux-event-bus-messaging` (108 L), `stacked-prs` (72 L), `stacked-prs-gh-cli` (91 L), `repo-toolchain-gates` (108 L), `change-writing` (69 L + 6 refs). `scripts/cmux-bus.sh` is referenced by two docs and has **zero tests** (`rg -ln cmux tests/` → nothing).

**The blunt summary:** four to six real vertical slices, of which the two most impressive (activation transaction, instruction generator) do not exist outside this working directory. 19% of the suite proves prose is self-consistent — a legitimate and unusual discipline that catches exactly the "STALE INSTRUCTIONS / UNWIRED CAPABILITY" class pi-lab's repo-hygiene skill names, but it is not behavioral coverage and should never be counted as such. And the doctrine layer is where agentic-sdlc is strongest *and* where it is furthest from executable: the repo currently states more enforceable-sounding numbers than any other artifact in either project, and enforces none of them.

---

## 4. Gap ledger, ranked

Harvest-memo numbers refer to `docs/research/2026-08-05-pi-lab-harvest-memo.md` items 1–43; vendoring-memo numbers to `2026-08-05-vendoring-install-ux-memo.md` items 1–22.

### G1 — Commit the work. *(Not in either backlog. Value: extreme. Effort: minutes.)*
`git log --all -- skills/agentic-sdlc/tools/activation-planner.py tests/test_activation_transaction.py` → empty. `git show HEAD:scripts/activation_planner.py` → 441 L, `choices=["plan"]` (line 429). A clean clone confirmed it. Also uncommitted: the model-pin ban in `validate_skills`, the betterleaks pin + lock, `evidence-discipline.md`, `skill-authoring.md`, `worktree-failclosed-tests.md`, and all 13 research memos. **pi-lab solved this trivially — everything it ships is committed and pushed.** Smallest change: `git add`. Nothing else in this ledger matters until this is done, because every parity claim above is currently a claim about one developer's filesystem.

### G2 — The `/sdlc-init` runbook is broken by the uncommitted refactor. *(New in this pass; overlaps harvest #1 but is a regression, not a gap.)* Value: high. Effort: small.
`commands/sdlc-init.md` is **tracked and unmodified**, and documents four things the working-tree tool no longer does:
- `:20` — `python scripts/activation_planner.py plan --target <path> [--profile git]`. Executed in the working tree: `activation-planner.py plan: error: the following arguments are required: --manifest, --entry`. Executed in a clean clone of HEAD: emits a valid `agentic-sdlc/activation@1` plan.
- `:30` — "ends by writing `.agentic-sdlc/activation-receipt.json`". The new tool writes `.agentic-sdlc/receipts/<32-hex>.json` (`activation-planner.py:163`).
- `:31-35` — the receipt "records baseline inventory, Seeds queue proof, the reversible gate fail→pass proof, per-path trust decisions, and `wave_ready`". None of those fields exist; `:8` of the new module states it "deliberately supports no greenfield, readiness, Seeds, trust, Git, or multi-file activation behavior." HEAD's version *did* have them (`scripts/activation_planner.py:189-191,368`).
- `:35` — "Deactivation uses the same helper (`deactivate`, dry-run first)". `rg deactivat` over `skills/agentic-sdlc/tools/ scripts/` → nothing; and `tests/test_activation_planner.py:49` now *asserts* `deactivate` is absent from `--help`.

**Smallest closing change:** rewrite `commands/sdlc-init.md:20-35` against the actual CLI in the same commit as G1, or keep the old flags as a documented compatibility surface. Right now the flagship activation command's own runbook cannot be followed.

### G3 — Port the pass-budget counter, not the ledger. *(Supersedes harvest #19's framing.)* Value: high. Effort: small.
The harvest memo pointed at 598 lines of TypeScript (`frame-ledger.ts`) as the target. The far smaller and exactly-shaped port is `pi-agentic-sdlc-skills/extensions/sdlc-mission.ts:540-593` (~55 lines) plus `schemas/frame.schema.json` — which already hold **agentic-sdlc's own integers**, byte-for-byte with `commands/sdlc-mission.md:31,39-41`. `rg "chargePass|PASS_BUDGETS|frame.schema" docs/research/2026-08-05-pi-lab-harvest-memo.md` → zero hits, so this is an unrecorded gap. Smallest change: a stdlib Python module under `skills/agentic-sdlc/tools/` that persists `{passes: {...}}` and refuses past a cap, plus one test that asserts the *numbers* (today `rg "≤" tests/*.py` matches nothing). Do not try to instrument the host's Task tool; make it the conductor's own tracking artifact, as pi-lab does.

### G4 — Wire the secrets scanner and qualify the binary at run time. *(Harvest #20; not in the vendoring memo.)* Value: high. Effort: small then medium.
`[tasks.check]` (`mise.toml:98-100`) depends on `validate, test, self-test`. `lefthook.yml` (11 lines) wires validate/test/self-test. CI runs only `mise run check`. So betterleaks has never screened a commit or push in this repo. `skills/repo-toolchain-gates/SKILL.md:97` discloses this honestly and `tests/test_gate_graph.py:416` keeps the disclosure true — good hygiene, but the gate is still absent. pi-lab solved both halves: `scripts/check.ts:510` makes `secrets` a leaf (executed: real scan, exit 0), and ADR-0006 adds run-time identity qualification with exit 78 (identity) / 75 (timeout) after two real incidents (a 1.6.1-vs-declared-1.7.0 silent pass; an `ETIMEDOUT` indistinguishable from clean). Smallest change: add a `secrets` task and put it in `check`'s `depends`. Then wrap the invocation in a qualification shim reusing `gate_receipt.py`'s digest machinery — which also gives that orphaned library its first caller.

### G5 — Fix the readback binding; it is a correctness bug, not a grading nit. *(Not in any backlog.)* Value: high. Effort: small.
See §7/D1. `receipt_admission.py:357-362` makes a request echo validate and an honest divergence refuse. Smallest change: bind `readback_bytes_sha256` to the transport's response bytes rather than `sha256({"effort": requested})`, and allow `evidence[value_key] != top_level` while recording the divergence — that is the only shape in which readback can carry information. Also rename `request_bytes_sha256` → `readback_bytes_sha256` in the mutant at `tests/…:1166` so the anti-copy test actually tests copying.

### G6 — Seeds mutation seam. *(Harvest #3, unchanged and still correct.)* Value: high. Effort: medium.
`mission-loop.md:34-46` makes "seeds-first, never fix inline, the conductor is the sole queue writer" the load-bearing rule of the whole mission doctrine, and `seeds-launcher.mjs:866-870` admits no mutation verb; `tests/test_seeds_launcher.py:451` plants `create` and asserts refusal. So a conductor following the doctrine has nowhere to record a classified finding. Corroborating scale: 18 issues here vs 830 in pi-lab. Smallest change: add `create`/`update` with the CAS + readback discipline `activation-planner.py` already demonstrates, rather than inventing a second pattern.

### G7 — LICENSE + NOTICE. *(Vendoring memo's own stated prerequisite; harvest #28.)* Value: high (unblocks ~12 backlog items at once). Effort: trivial.
`ls LICENSE NOTICE` → both absent; `plugin.json:8` `"license": "UNLICENSED"`. pi-lab shipped both, with a per-donor record naming exact commits and blob SHAs (`NOTICE:45-58`) and one attributed derivation on disk. Every vendoring item (#2, #3, #5–#13, #16, #20) is categorically blocked until attribution has somewhere to land. Smallest change: two files plus a one-word manifest edit.

### G8 — Make `claude plugin validate --strict` true or delete the claim. *(Vendoring memo #1; already diagnosed twice and still unfixed.)* Value: high. Effort: trivial.
Executed: `.claude-plugin/plugin.json` → exit 1, two warnings (`root: CLAUDE.md at the plugin root is not loaded as project context`; `agents/codex/research/README.md: No frontmatter block found`). `marketplace.json` alone → pass. Bare `.` → pass (it validates only the marketplace manifest). `README.md:130` claims both pass. Smallest change: move `agents/codex/research/README.md` to `docs/codex-research-roster.md` (the judge-verdict's own recommendation), decide about root `CLAUDE.md`, then re-run — and wire the validator into `validate_bundle.py` so it cannot regress.

### G9 — One executable worktree fail-closed test. *(Harvest #11.)* Value: medium-high. Effort: small for the first case.
pi-lab's suite is 374 L / 9 cases and runs (executed: 9/9, 13.9 s). agentic-sdlc has the spec and no tests (`fd worktree tests/` → nothing). Since this repo bundles no dispatcher, the achievable analog is a Python test that plants git-level preconditions (occupied branch, dirty/non-git target) against `commands/sdlc-wave.md:14`'s `git worktree add ../<repo>-wt-<seed-id> -b work/<seed-id>-<slug>` and asserts non-zero exit with no orphaned branch. Converts one spec entry from designed to shipped without porting all 227 lines.

### G10 — Vouch the recover path against the manifest. *(Harvest #7, re-scoped.)* Value: medium-high. Effort: small.
The memo said "adapt receipt-vouching to the commit/rollback path." The specific reachable gap: `_recover`→`classify_recovery`→`_load_operation` never re-read the manifest, so a finish/rollback is authorized entirely from records inside the target's own private state plus a grant. Smallest change: re-derive `manifest_sha256` in `classify_recovery` exactly as `apply` does at `:1795`, and add one test where the manifest changed between apply and recover.

### G11 — A generated description-byte budget leaf. *(Not in either backlog; ADR-0008 is the prescription.)* Value: medium. Effort: small.
No aggregate exists; `validate_bundle.py` only checks per-skill ≤1024. I measured 3,563 B across 8 skills. pi-lab's byte-identity leaf caught a real two-branch merge collision (ADR-0008:46-52). `skill-authoring.md` §5's objection ("a static number goes stale") is answered by generating it, which is what ADR-0008 does. Smallest change: sum the frontmatter descriptions into a generated file and assert byte-identity with the checked-in copy.

### G12 — Author the ADRs the memos already decided. *(Related to harvest #40 and the ADR spec memo.)* Value: medium. Effort: small each.
0 ADRs vs 23. At least four decisions are already made and unrecorded, and several are being re-litigated across sessions: licence/visibility, MCP-zero-default-servers, selection-budget position, mise-as-front-door. The specced ADR skill (330 L) is unbuilt. Smallest change: four short MADR records; they cost less than the memo pages already spent re-deriving them.

### G13 — Resolve the gateway stance in a tracked file. *(Harvest #2, partially superseded.)* Value: medium. Effort: trivial for the decision, large for the build.
Committed docs mention no gateway; untracked `SESSION-HANDOFF.md:185` says "Gateway is required for normal inference," and `progress-snapshot:81` self-flags the conflict with README. Meanwhile the memo's own addendum found the subscription-passthrough premise ToS-blocked, and pi-lab reached a clean "no" with three falsifiable reopen conditions. Smallest change: record the downgrade to "optional, ToS-blocked for the cost use case" as an ADR (see G12), or delete the ambition until a human rules. Note `progress-snapshot:34`'s canary claim ("CLIProxyAPI routed `gpt-5.6-sol` successfully") predates the addendum and is not evidence for the mechanism the ambition needs.

### G14 — Point the dangling single-authority reference. *(Not in any backlog.)* Value: low. Effort: trivial.
`deep-work-loop.md:220-222` routes readers to `references/tiered-orchestration.md` for "the global pass ceiling and per-phase re-entry budgets." `rg "≤" tiered-orchestration.md` → **NONE**; `:62-67` says only "respects a global pass ceiling, per-phase re-entry budgets, and a resource floor." The numbers live solely in `commands/sdlc-mission.md:39-41`. This is exactly the "fork a second copy that drifts" failure `deep-work-loop.md:9` claims to prevent.

---

## 5. Where agentic-sdlc exceeds both pi-lab and the sources

**Load-bearing originals:**

1. **The four-plane cross-host manifest set under one installer.** No source and no pi-lab artifact prescribes shipping Claude + Codex + Gemini + bare-skills-tree from one skill tree with per-plane status/uninstall and a per-plane marketplace exclusivity guard (`install_skill_bundle.py:2613`). pi-lab targets exactly one runtime by design. This is real shipped breadth, committed, tested, and CI-verified on three OSes — and it is the single largest capability neither pi-lab nor any external source has.
2. **The Seeds acquisition/inspection provenance chain.** `seeds-launcher.mjs` resolves only config-free exact Git roots, invokes reviewed `mise --locked install` with isolated HOME/npmrc/registry, validates Node 22.22.3 + Bun 1.3.10 + the exact package layout, records commit/tree/tool hashes with a prior receipt for rollback, and then starts the child with `shell:false`, an allowlisted env, and a PATH limited to a separately recorded Git directory. 18 tests; executed refusal on the wrong Node. There is no pi-lab analog and no external prescription at this level of paranoia. Its own honest caveats (same-UID TOCTOU, npm-lock ≠ tarball integrity) are stated in the doctrine.
3. **Single-use, consumed procedural grants.** pi-lab's nearest primitive is a typed digest acknowledgement string with no consumed state; agentic-sdlc's grant is bound to `operation_id`/`operation_digest`/`decision`, ledgered, and refused on replay — proven by execution. Strictly stronger against replay.
4. **Doctrine-consistency testing as a first-class discipline.** 77 tests whose only job is to keep prose from drifting from its own rules, plus doc-lints that *preserve honesty about gaps* (`test_gate_graph.py:416` asserts the betterleaks doctrine text matches the actual non-wiring; `test_activation_planner.py:49` asserts a retired verb stays retired). Neither pi-lab nor any source does this systematically. It is why this repo's docs, where they are wrong, are wrong in *narrow, findable* ways.
5. **The research-OS generator.** 1,155 lines that emit a Makefile, 10 scripts, and a claim schema whose validator actually refuses an underspecified claim (executed). The `autoresearch-lab-blueprint` memo specced a lab; this ships a lab factory. pi-lab has research doctrine and no generator.

**Speculative or not yet load-bearing:**

6. **`gate_receipt.py`'s general-purpose, toolchain-digest-bound receipt.** Elegant (binds argv + captured-output digest + `mise.lock` bytes + a self-digest), honest about being tamper-*detection* not a security boundary — and called by nothing. Generality with no consumer is potential, not capability.
7. **`approval_authenticated: False`.** Clever in intent — make "this record is not authorization" a type-level fact — but no code path ever sets `True`, so it is a constant, not a control. The schema-exactness check is what actually rejects a forged record.
8. **The "critique team audits squash-merged snapshots, never live worktrees" rule.** No antecedent found in either corpus. Genuinely novel as an operational pattern; today it is one paragraph with no tool or test. Note pi-lab's fork ships it as a *role* with a read-only toolset — more than a paragraph, on doctrine agentic-sdlc authored first.
9. **The `resolved`/`inherited`/`unresolved` vocabulary.** The `resolved` gate is real code; the other two states exist only in prose and greps. `skills/model-tier-rightsizing/SKILL.md:107` is admirably explicit that "this repository supplies no host launcher. An external authenticated harness is the sole admission and spawn authority" — so the invention is a contract awaiting a counterparty.
10. **The citation-verification rule** (`deep-work-loop.md:145-148`) — a real, actionable discipline with no source antecedent, enforced only by convention, and honest that "a citation-checking script narrows the search; it does not replace a human spot check." This review followed it, and it caught several of the errors above.

---

## 6. Source-verdict contradictions

**ECC licence — pi-lab is right; agentic-sdlc was wrong twice and has already self-corrected once.**
`docs/research/2026-08-06-plugin-restructure-judge-verdict.md:93` and `:262`: *"ECC: no resolvable license on any candidate repo. Not redistributable. USER DECISION, blocking."* pi-lab `NOTICE:53-56` records: *"Licence MIT, Copyright (c) 2026 Affaan Mustafa, root LICENSE, 1071 bytes, blob b832b6f6…"* at pin `0c1d7be9…`, with the note (`:46-49`) that the repo redirects from `affaan-m/everything-claude-code` — which is exactly why a search for the old name looked unresolvable. Evidence favours pi-lab decisively. agentic-sdlc's `2026-08-05-vendoring-install-ux-memo.md:3-22` already carries the correction and the right procedural lesson ("check `pi-lab/docs/research/` before declaring an external source unresolvable"), but the judge-verdict memo still states the wrong conclusion in two places and no ADR records the resolution.

**hyperresearch — the two projects evaluated different objects; the residual disagreement favours pi-lab's caution.**
pi-lab's `docs/research/20260727/DISPOSITIONS.md:84` rejects **`hyperresearch-pi@0.1.6`**, a third-party *Pi wrapper*, on five observed defects — chiefly `:90`, an unpinned `pip install hyperresearch` at extension startup resolved from ambient PATH, and `:93`, writes to `~/.pi/agent/` plus a recursive delete with no ownership check. Its `hyperresearch.md:5` verdict on the capability is **FORK-EDIT, do not SOURCE or BUILD from zero**. agentic-sdlc's `judge-verdict.md:92` rejects the **locally rendered install of upstream `jordan-gibbs/hyperresearch`** on different grounds: 14/14 agents carry static `model:`, 11 skills carry unresolved placeholders, no LICENSE in the local install. `2026-08-06-hyperresearch-per-repo-profile.md` then resolves the model-pin objection via upstream's own `[profile.<name>]` mechanism, and `:110-125` cross-checks pi-lab honestly, conceding pi-lab is "more cautious" and "raises control costs I did not examine." Both agree upstream is MIT Python 0.10.0. Net: the apparent conflict is 80% resolved and mostly an object confusion; the live residue is control cost (billing lane, tool scope, concurrency, output volume), where pi-lab's evidence is better. The per-repo memo's `uvx --from hyperresearch==0.10.0 --python 3.12.11` answers pi-lab's single strongest objection.

**ECC's loop-design provenance — pi-lab is right and agentic-sdlc's citation chain is a hair too generous.**
The orchestration crosswalk claimed ECC "prescribes a *checkable* loop shape." pi-lab's own `skills/house/loop-design/SKILL.md:11` (frontmatter) says *"No loop described here is installed by pi-lab. This skill grants no permission and enforces nothing,"* and `NOTICE:103-104` insists on crediting *"ECC only as the place pi-lab observed them; never state or imply that ECC authored"* — the ideas trace to Wiener/Anatoli/Osmani. agentic-sdlc's `deep-work-loop.md:178` gets the attribution right ("adapted from pi-lab's loop-design skill"); the crosswalk's paraphrase did not. Verifier-corrected; the PARITY verdict survives.

**mattpocock — no contradiction, but pi-lab already staged the discipline.** Only agentic-sdlc evaluated it in depth (vendoring items 2, 3, 7–10, 12, 13, 20, 21). pi-lab's `docs/adr/0016`:80,257 disposes `mattpocock/skills` as `deferred` pending *"licence check, exact pin, isolated load proof"* — precisely the three-step gate agentic-sdlc's memos assume but have no LICENSE/NOTICE to satisfy.

**MCP — full agreement, independently reached.** Both agentic-sdlc restructure designs (`restructure-design-plugin-first.md:203`, `plugin-restructure-recommendation.md:94`) reject shipping `.mcp.json`; pi-lab ADR-0021 independently concludes "zero default servers." The only asymmetry: pi-lab recorded it as a decision, agentic-sdlc left it in memos.

---

## 7. Doc-vs-code drift

**D1 — `AGENTS.md:95` ("requested values never become readback") is contradicted by the only code that implements it.** *(Most serious. The code is wrong, not just the doc.)*
`skills/model-tier-rightsizing/scripts/receipt_admission.py:357-362`:
```python
top_level = receipt["requested_effort"] if name == "effort" else receipt["requested_context_form"]
if evidence[value_key] != top_level:
    errors.append(f"{name} readback evidence does not bind the top-level {name} value")
expected = {"effort": top_level} if name == "effort" else {"context_form": top_level}
if evidence["readback_bytes_sha256"] != sha256_json(expected):
    errors.append(f"{name} readback evidence digest does not bind the top-level {name} value")
```
Executed: a receipt whose "observed" effort/context are copies of the request validates with `errors: []`, and its digest is `1450e0b1f50c56ac3c83d60ff41f209994e0a69d269e89427dc2051e31662448` = `sha256({"effort":"high"})`, computable by anyone holding the request. Executed: an **honest divergent** readback (`observed_effort="medium"` against `requested_effort="high"`) is rejected by `construct_receipt` itself — the schema cannot represent a transport that downgraded the effective effort, which is the single case readback exists to detect. The test that appears to prove the opposite (`tests/test_runtime_contract_validation.py:1158-1172`) passes only on a misspelled field name.

**D2 — `commands/sdlc-init.md:20,30-35` documents a CLI, a receipt path, five receipt fields, and a `deactivate` verb that the working tree does not have.** Full detail in G2. All four verified by execution against both the working tree and a clean clone of HEAD.

**D3 — `README.md:130`: "Both manifests pass `claude plugins validate --strict`."** Executed: `plugin.json` → exit 1 with two warnings-as-errors. `marketplace.json` alone and bare `.` → pass. Diagnosed in `plugin-coexistence-finding.md` and `vendoring-install-ux-memo.md:34`; still in the committed README.

**D4 — `commands/sdlc-mission.md:31,39-41` and `references/mission-loop.md:56` state nine specific integers in imperative runbook voice, with no counter, no query, and no test.** Indistinguishable in tone from step 5's Seeds instruction, which does correspond to real (read-only) tool behavior. A reader cannot tell from the document that `pi-dynamic-fractal-workflows`' depth cap throws `DEPTH_CAP_EXCEEDED` while `mission-loop.md:56`'s "≤ 2" has no refusal path at all.

**D5 — `deep-work-loop.md:220-222` points at `references/tiered-orchestration.md` as the authoritative site for numeric budgets that file does not contain.** See G14.

**D6 — `README.md:70` lists betterleaks inside "the standard local gate stack" alongside "`mise run check` = THE gate."** True as a pin, false as a gate: `mise.toml:98-100` excludes it. `skills/repo-toolchain-gates/SKILL.md:97` states the truth; the README does not carry the qualifier. Also `commands/sdlc-init.md:91` instructs activating repos to "wire the secrets gate into `mise run check` and CI" — advice this repo does not follow itself.

**D7 — `docs/progress/2026-07-21-product-progress-snapshot.md:33` ("the public CLI exposes only `plan`") is accurate about HEAD and stale only relative to uncommitted work.** Filing this as a doc overclaim inverts the relationship — verified by running HEAD's planner in a clean clone. This document is the most honest artifact in the set, and it is itself untracked.

**D8 — `README.md:139` and `skills/cmux-event-bus-messaging/SKILL.md:92` advertise `scripts/cmux-bus.sh` (pub/sub/seq).** The file exists; `rg -ln cmux tests/` → no test anywhere. Shipped by file existence only.

---

## 8. What remains unverified

- **A fifth crosswalk was specified but not delivered.** My input contained four complete domain crosswalks (orchestration, model-routing, evidence-authz, skills-distribution), and the skills-distribution verification is **truncated mid-sentence** at `"README.md:130": "Bo`. The research/docs-skills rows in §2 are therefore **my own first-hand checks in this pass**, not a reviewed crosswalk, and they are shallower than the other four: I executed the research-OS generator and its claim validator and inventoried `change-writing`, but I did not read the 547-line docs-commits spec or the 330-line ADR spec against pi-lab's `skills/commits/` and `skills/docs/` line by line. Treat that domain as sampled, not surveyed.
- **`bedrock-mantle-frontier-bundle` and `pi-ecosystem-research` are largely unexamined by me.** I read the qualification YAML (60 L) and confirmed `dynamic-workflow-routing.md` is 199 L with 12 invariants and a driver at `scripts/qualify-cohort:271`, but I did not evaluate the 6-rung promotion ladder, HMAC-sealed admission, or `model-registry.json`'s 14-state observation taxonomy (harvest #9, #16). Their crosswalk grades are inherited.
- **pi-lab's ADR-0012 recoverable-publication mechanism** — I confirmed the named test files exist (`live-apply-journal.test.ts` 18 tests, `live-apply-recovery.test.ts` 5) and executed the journal suite, but not the fault-injection integration suite against `dist/cli.js`. Its "byte-for-byte reversal, six refusals all exit 2" field claim is read from `docs/dogfood/2026-07-31-two-foreign-projects.md:35,40`, not reproduced.
- **`mise run check` was not executed as the aggregate gate.** I ran `python3 scripts/validate_bundle.py` (0 errors), `./scripts/install-skill-bundle.sh self-test` (passed), and `python3 -m pytest tests/` (399 passed) individually. I did not run `mise run check` itself, so I have not verified that the aggregate task binds those three exactly as `mise.toml:98-100` declares.
- **The Windows/macOS half of the installer is untested by me.** `run_all_hosts.py`, junction fallback, `LOCALAPPDATA` state, and the WSL→native handoff have 8 + 82 tests that pass on Linux; the platform-specific branches were not exercised. CI claims 3 OSes; I did not inspect a CI run.
- **Whether pi-lab's route-ledger data was ever produced by a real invocation** — the statuses say `route-probed-positive`, and `capability-crosswalk.ts:337` says nothing reads the file, but I found no writer and did not trace the 17 positive rows to a transcript. "Populated" is verified; "measured" is not.
- **No claim here about production behavior of anything.** Both projects' strongest artifacts are validated by their own tests and, in pi-lab's case, one dogfood run on two foreign repos. Neither has delivered a wave, a mission, or an activation to a third party. Every "SHIPPED" grade above means "code runs and a test covers it," never "this has worked for a user."
- **Read-only compliance:** no file was written in either repo, no git-mutating command was run, and the only writes were to `/tmp` scratch paths (`/tmp/headclone`, `/tmp/ros`, `/tmp/cpx`) for execution checks.
