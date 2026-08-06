## Per-claim verdicts

### Row: Agent-Skills format conformance — graded "AGENTIC-SDLC AHEAD / SHIPPED"
**REFUTED (partially).** The `validate_skills` code the analyst read is real and its test is real, but **the model-pin half is not committed.** Working tree `scripts/validate_bundle.py:410-436` matches the analyst's quote. `git show HEAD:scripts/validate_bundle.py` shows `validate_skills` at **HEAD lines 386-400 with no model-pin check at all**:
```
396-        elif len(description) > 1024:
398-        for reference in sorted(set(re.findall(...
```
`git show HEAD:tests/test_runtime_contract_validation.py | rg -c "validate_skills"` → **0 matches**. `git status --porcelain` → ` M scripts/validate_bundle.py`, ` M tests/test_runtime_contract_validation.py`.
Corrected verdict: name==dirname / description cap / ref-existence = **SHIPPED at HEAD** (verified: `python3 scripts/validate_bundle.py` → `0 error(s), 0 warning(s)`; `./scripts/install-skill-bundle.sh self-test` → `self-test passed`). Semantic model-pin ban = **UNCOMMITTED WORKING-TREE CHANGE**, not shipped.

### Row: Skill admission/retirement doctrine — graded "PARITY / agentic-sdlc SHIPPED, adapted"
**REFUTED.** Two independent defects.
1. `skills/agentic-sdlc/references/skill-authoring.md` is **doctrine prose in a references file**, and it says so itself at line 9: *"Nothing here is enforced by any script in this repository unless a section says otherwise."* Per the review rule, that is DESIGNED.
2. `git ls-files --error-unmatch skills/agentic-sdlc/references/skill-authoring.md` → **UNTRACKED**. It is not in any commit.
pi-lab side CONFIRMED: `skills/house/skill-authoring-standard/SKILL.md` is 459 lines and real (four-gate test at `:134`, `≥2-of-5` at `:181`), and pi-lab's own file is equally non-enforcing (`:11` `not-claimed: "no enforcement by this file. It refuses nothing."`).
Corrected verdict: **PARITY at the doctrine level, but agentic-sdlc's copy is DESIGNED and uncommitted while pi-lab's is DESIGNED and landed** → PI-LAB SLIGHTLY AHEAD.

### Row: Selection-budget / description-byte gate — graded "PI-LAB AHEAD"
**CONFIRMED**, and pi-lab's artifact was executed. `bun test tests/unit/skill-loading-path.test.ts` → **17 pass, 0 fail**. `docs/skill-loading-path.md:55` → `| **total** | **22** | **15528** | — |`. The byte-identity leaf is live at `tests/unit/skill-loading-path.test.ts:154`: `expect(committed).toBe(renderMatrix(rows))`, plus `:142` asserting the ADR quotes the current measurement.
agentic-sdlc side CONFIRMED absent: `rg -c "1024" scripts/validate_bundle.py` → **2**, both inside `validate_skills` per-skill. No aggregation anywhere. I computed what the missing number would be using the repo's own helpers: **3092 description bytes across 8 skills**. No generator, no gate leaf.

### Row: Vendoring / licensing gate — graded "BOTH SHORT OF SOURCES"
**REFUTED — this is the most consequential error.** The analyst asserted "pi-lab vendors nothing either; neither project has landed the licensing prerequisite." Both halves are false:
- pi-lab has `LICENSE` (21 lines, MIT, `Copyright (c) 2026 Baladithya Balamurugan`) **and** `NOTICE` (354 lines) at root, with a fully-formed donor record: `NOTICE:45-85` pins `affaan-m/ECC` at `0c1d7be9a750627fb2a6534c78a998cc46d03f9c`, blob SHA of the harvested file, and reproduces the MIT permission notice verbatim.
- pi-lab **did land a derived artifact**: `skills/house/loop-design/references/external-anchors-and-loop-shape.md` exists, opening with the provenance header naming the ECC pin and blob.
- The analyst's claim of a "disjoint set / no mattpocock/ECC/hyperresearch overlap" is also false: `docs/research/20260727/DISPOSITIONS.md:21` — *"Net shortlist: one target advances (ECC, narrowed to doctrine text)"*; `:15` disposes hyperresearch; `docs/adr/0016-...md:80,257` disposes **mattpocock/skills** (*"licence check, exact pin, isolated load proof; stage `deferred`"*).
- Also: the analyst's cited path `docs/assessment/20260727/DISPOSITIONS.md` does not exist. The real path is `docs/research/20260727/DISPOSITIONS.md`.
agentic-sdlc side CONFIRMED: `ls LICENSE NOTICE` → both absent; `.claude-plugin/plugin.json:8` → `"license": "UNLICENSED"`; `ls skills/` → exactly 8 dirs, none of the 6 memo-designed skills.
Corrected verdict: **PI-LAB AHEAD** (licensing prerequisite landed, one donor derivation shipped, overlapping candidates already adjudicated).

### Row: Plugin/direct-install plane coexistence — graded "AGENTIC-SDLC AHEAD / SHIPPED"
**CONFIRMED.** `scripts/install_skill_bundle.py:2613` reads exactly `claude_blocked = config.agent in {"all", "claude"} and marketplace_overlap(config.home)` and `:2621` reads `if entry.agent == "claude" and claude_blocked:`. Per-plane, as claimed. This code **is** at HEAD (`install_skill_bundle.py` is not in `git status`).

### Row: Claimed plugin-manifest validation status — graded "BOTH SHORT OF SOURCES"
**CONFIRMED as a defect, but mis-verdicted.** `README.md:130`: *"Both manifests pass `claude plugins validate --strict`."* Executed with `claude` 2.1.223:
- `claude plugin validate --strict .claude-plugin/plugin.json` → **exit 1**, 2 warnings (CLAUDE.md-at-root; `agents/codex/research/README.md` no frontmatter). Plural form `claude plugins validate --strict .claude-plugin/plugin.json` → also **exit 1**.
- `.claude-plugin/marketplace.json` → **exit 0, passed**.
So exactly one of the "both" passes. Frontmatter absence re-confirmed: `rg -n "^---" agents/codex/research/README.md` → no matches (file opens `# Research role TOMLs...`).
Bonus finding the analyst missed: **`.agents/plugins/marketplace.json` also fails** — `claude plugin validate --strict .agents/plugins/marketplace.json` → exit 1, `owner: Invalid input: expected object, received undefined`.
Corrected verdict: this is not "BOTH SHORT OF SOURCES" (pi-lab has no analog, so there is no shared shortfall) — it is **AGENTIC-SDLC DOC DEFECT, no source comparison applies**.

### Row: Hooks (PreToolUse guardrail) — graded "BOTH SHORT OF SOURCES"
**CONFIRMED absent, verdict mis-labeled.** `fd -H "hooks.json"` → nothing. `fd -H -t d "vendor|claude-hooks"` → nothing. `fd "guard-outward-effect"` → nothing. The memo content is real: `docs/research/2026-08-06-plugin-restructure-judge-verdict.md:131-180` carries the exact JSON and shell, and `:82` records live firing (`HOOKFIRED root=/tmp/judge-schema/src/`) plus `:89` measured latency (4.7 ms/call). **But that memo file is UNTRACKED** — the entire `docs/research/` tree is `?? docs/research/` in `git status`. pi-lab genuinely has no analog, so "BOTH short" is wrong.
Corrected verdict: **AGENTIC-SDLC DESIGNED-NOT-SHIPPED; no pi-lab comparison exists.**

### Row: MCP — graded "ABSENT by design / AGENTIC-SDLC AHEAD"
**REFUTED on the pi-lab column ("N/A — no MCP analog surveyed").** pi-lab has a full ADR **and an executable gate**: `docs/adr/0021-mcp-adapter-mediated-support-zero-default-servers.md` (*"pi-lab ships zero default MCP servers"*), enforced by `src/core/live-profile.ts:331` `MERGED_LIST_KEYS` plus `tests/unit/mcp-default-refusal.test.ts`, which I executed: **25 pass, 0 fail**.
agentic-sdlc side CONFIRMED: rejection reasoning at `docs/research/2026-08-05-plugin-restructure-recommendation.md:94` and `2026-08-05-restructure-design-plugin-first.md:203`; only `.mcp.json` hits are those docs plus the `seeds-worktrees.md:200` caveat.
Corrected verdict: **PI-LAB AHEAD** — both reached the same "zero default servers" position, but pi-lab's is an accepted ADR with a passing enforcement test; agentic-sdlc's lives only in untracked research memos.

### Row: Install UX doctor/repair split — graded "AGENTIC-SDLC AHEAD (mixed)"
**REFUTED in part.** The prescription is real (`docs/research/2026-08-05-vendoring-install-ux-memo.md:50` prescribes new **`bundle:doctor` / `bundle:repair` mise tasks**), and agentic-sdlc has **neither**: `rg -n "bundle:doctor|bundle:repair" mise.toml README.md scripts/` → **no matches**; `rg -n "doctor|repair" scripts/install_skill_bundle.py` → only two error-message strings (`:1588`, `:2329`). pi-lab's `doctor` **is** shipped and tested — `bun test tests/unit/render-doctor.test.ts tests/unit/runbook-doctor-states.test.ts` → **33 pass, 0 fail**; the exit-0-on-unhealthy weakness is confirmed (`src/commands/doctor.ts:472` sets `state: "unhealthy"`; `src/cli.ts:629` shows checkpoint-verify is the **only** command that overrides `process.exitCode`).
Also **test counts are wrong**: analyst said "22 tests" for `test_install_skill_bundle.py`; actual **82 collected / 82 `def test_`**.
Corrected verdict: agentic-sdlc ahead on install-lifecycle test density (82 vs pi-lab's doctor suites), but **pi-lab AHEAD on the specific doctor/repair capability the source prescribes** — agentic-sdlc has no `doctor` verb at all.

### Row: Cross-host support — graded "AGENTIC-SDLC AHEAD / SHIPPED"
**CONFIRMED.** All four manifests read and real: `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` (`"skills": "./skills/"`), `gemini-extension.json` (`"contextFileName": "AGENTS.md"`), README table at `:14-19`. `validate_manifests` at `scripts/validate_bundle.py:1298-1304` parses all five JSON manifests.
**But the test count is wrong:** analyst claims `test_run_all_hosts.py` has "36 tests." Actual: **8 collected, 8 `def test_`**. The 90-passed total (82+8) is correct; the per-file attribution is fabricated.

### Row: Skill-count drift gate leaf — graded "PI-LAB AHEAD"
**CONFIRMED.** Same evidence as the selection-budget row; pi-lab's leaf executes and passes.

### Row: Update/reinstall idempotence — graded "AGENTIC-SDLC AHEAD"
**REFUTED.** `tests/test_activation_transaction.py` is **1824 lines, 51 tests collected (not 40), all passing (51 passed, 32 subtests)** — but `git ls-files --error-unmatch tests/test_activation_transaction.py` → **UNTRACKED**, and so is its subject `skills/agentic-sdlc/tools/activation-planner.py`. An untracked test file is not shipped. The analyst also concedes it tests a different subsystem than the skill installer, which makes it non-comparable to pi-lab's reinstall receipt anyway.
Corrected verdict: **NOT COMPARABLE / agentic-sdlc's cited artifact is uncommitted.**

---

## Single most important error

**The crosswalk grades an uncommitted working tree as "shipped."** Every marquee "SHIPPED" the analyst leans on for agentic-sdlc's wins is either a modified-but-uncommitted file or entirely untracked:

| cited artifact | git state |
|---|---|
| `scripts/validate_bundle.py` semantic model-pin ban (`:426-433`) | ` M` — HEAD's `validate_skills` has **no** model-pin check |
| `tests/test_runtime_contract_validation.py` model-pin tests | ` M` — `validate_skills` appears 0× at HEAD |
| `skills/agentic-sdlc/references/skill-authoring.md` (181 lines) | `??` untracked |
| `tests/test_activation_transaction.py` (1824 lines, 51 tests) | `??` untracked |
| `skills/agentic-sdlc/tools/activation-planner.py` | `??` untracked |
| the entire `docs/research/` source corpus (12 memos) | `??` untracked |

The analyst's own "original invention" bullet — *"memo-prescribed and now confirmed landed (`scripts/validate_bundle.py:426-433`)"* — is the sharpest instance: "landed" is exactly what it is not. And because the *source memos themselves* are untracked, the crosswalk's entire "what the sources prescribe" column rests on files that do not exist in any commit, which means half the "BOTH SHORT OF SOURCES" verdicts are comparing a committed pi-lab against an uncommitted agentic-sdlc.

Runner-up: the vendoring/licensing row inverts reality. pi-lab has a 21-line MIT `LICENSE`, a 354-line `NOTICE` with a pinned+blob-hashed ECC donor record, a landed derived artifact, and prior dispositions on all three of agentic-sdlc's own candidates (ECC, hyperresearch, mattpocock). "Neither project has landed the licensing prerequisite" is simply wrong, and the cited pi-lab path (`docs/assessment/20260727/DISPOSITIONS.md`) does not exist — the file is at `docs/research/20260727/DISPOSITIONS.md`.