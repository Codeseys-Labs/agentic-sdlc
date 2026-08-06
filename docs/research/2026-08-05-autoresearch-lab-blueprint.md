## Judgment

| Criterion | A (minimalist) | B (evidence-first) | Why |
|---|---|---|---|
| Doctrine compliance | **2** | **5** | A's 10 new `agents/claude/lab-*.md` + `agents/codex/lab-*.toml` files are a hard gate failure, worse than A estimated. `scripts/validate_bundle.py:907-910` requires `global_spec.count == 14` **and** the on-disk glob to equal the source constant `SOURCE_PINNED_GLOBAL_PATHS`; `policy/role-manifest.v1.json` roles must equal `DELIVERY_ROLE_IDS \| RESEARCH_ROLE_IDS` (`:727`) with `kind` ∈ {delivery, research} (`:855`) — there is no `"lab"` kind. And `DELIVERY_ROLE_IDS` is derived by `filename[len("sdlc-"):-len(".md")]` (`:288`), so adding `lab-adversary.md` to `CLAUDE_GLOBAL_ROLE_FILENAMES` yields the role id `"dversary"`. A's roster needs validator surgery plus defeating `test_bundle_validator_source_pins_global_roster_despite_coordinated_repin`. B ships zero agent files and zero pin churn. |
| Claude-native fit | **4** | **4** | A is crisper on cost (per-loop subagents; Workflow only for variance calibration and post-stall sweeps; explicitly rejects Cron). B is right that the ledger is a shared file → lead-only writer, and correct to use a Workflow for `investigate → record → review → gate`. Complementary. |
| Host-agnostic fallback | **5** | **3** | A's insight is the stronger one and is verifiable: the CANNOTs are enforced by **artifact ordering**, not process separation, so a one-agent host still produces a correct lab — and the gate *records* that independence was textual rather than structural. |
| Migration cost | **2** | **5** | A's "phase 1" already touches the normative contract, the role manifest, validator constants, and `PROTECTED_REVIEWER_PATHS`. B is purely additive. Both also missed that `tests/test_model_tier_rightsizing.py:74-83` **pins `skills/codex-research-os/SKILL.md`, `references/operating-model.md`, `references/agent-roster.md` by path** and asserts each satisfies `_assert_research_dispatch_boundary` — A's 5-line retirement stub fails that test. |
| Keeps improving easily | **3** | **5** | A's honest answer is "the human edits `program.md`". B's lesson record (`{trigger, observation, proposed_change, target}`, never self-applied, gate-loosening lessons need adversarial review) is the same instinct made durable and doctrine-safe. |

**Winner: B.** Base = B's evidence spine, additive migration, and lesson loop. Grafted from A: the three-owner file model as the *whole* state model, harness immutability as a digest invariant, the append-only trial ledger, the nine-step loop, the executable invariant list replacing the substring gate, artifact-ordering as the host-agnostic guarantee, the stall rule, the two-plane autonomy split, and the ratchet pilot. B's four skills collapse to two (A's minimalism applied to B's content).

**Corrections both designs need (verified in source):**
- B's tool table is unimplementable as written: charters inherit the *pinned* role's allow-list. `sdlc-critic` has only `Read, Glob, Grep` — no Bash, no web. So `novelty_auditor→sdlc-critic` and `counterexample_hunter→sdlc-critic (Bash)` are wrong. Prior-art/novelty work must run on `sdlc-researcher` (the only role with `WebFetch/WebSearch`); anything needing `Edit` must run on `sdlc-implementer`.
- A overstated one cost: new `mise` tasks do **not** require validator edits. `validate_mise` only errors on `REQUIRED_TASKS - set(tasks)` (`:1071`) and pins the `run`/`run_windows` strings of `TASK_COMMANDS` keys. Extra tasks are free.
- B's §2.3 tripwire is real (`ROLE_MANIFEST_WEB_SIGNAL`, `:609`) but inert here, since no research TOML is edited.

---

# FINAL BLUEPRINT — Autoresearch Lab for `agentic-sdlc`

Wave 1 is additive: 2 new skills, 1 rewritten-in-place skill, 0 new agent files, 0 pinned digests touched, 0 deletions. `mise run check` stays green.

## 1. Skills

### 1.1 `skills/autoresearch-lab/` (new)

`name: autoresearch-lab`. Description (**1006 chars**, measured; cap 1024):

> Run a bounded, self-improving research lab in a repository: a human-owned program file, an immutable scoring harness the probe cannot edit, an append-only trial ledger, and a ratchet that advances only on reviewed evidence. Use when asked to create, install, operate, resume, or refine a standing or continuous research effort: hypothesis generation, prior-art and novelty audits, baselines, experiments, ablations, falsification, formalization, replication and adversarial review, claim promotion or demotion, negative-result memory, metric ratchets, stalled search, or cross-session continuation. Roles are narrow and advisory: producers never review their own claims, reviewers never repair what they find, writers never originate claims, and no role edits the harness that scores it. Trial writes and gate results are evidence, never authorization; every merge, push, publication, deployment, or queue mutation leaves the lab as one typed SeedProposal for conductor triage and an authorized integrator.

`SKILL.md` sections (target ≤260 lines; everything deeper is a reference):

1. **The three owners** — `lab/program.md` (human's only lever), `lab/harness/` (immutable during a run, digest-recorded), `lab/workspace/` (probe sandbox). A probe that edits its own judge is **void**, detected by digest, not by prose.
2. **Two planes.** *Inner ratchet*: probes iterate inside a scratch worktree with no human prompt, bounded by trial count + wall-clock. *Outer fan-in*: the only place results touch a durable branch, a rung promotion, or a queue — conductor records, authorized integrator executes. Karpathy's `NEVER STOP` is honoured inside the sandbox and rejected at the boundary. **Continuous ≠ unbounded**: continuity lives in `lab/state/next_action.md`.
3. **Preconditions — refuse to start.** (a) a named oracle command printing one scalar + direction; (b) a reproduced baseline with the command and commit that produced it; (c) a variance figure from ≥2 identical runs; (d) per-trial wall-clock and max-trials budget; (e) a kill criterion plus its instrument; (f) a conductor-supplied certified `RuntimeAssignment` with `resolution_state: resolved`. Any gap → emit exactly one `SeedProposal` and STOP.
4. **Decision flow** — no `lab/` → install; `lab/` present → read `program.md` + `next_action.md` + status rollup, run ONE loop; corpus-shaped question → host research pipeline (hyperresearch where installed) or `sdlc-researcher`, never duplicated here; claim bookkeeping → `research-claim-ledger`.
5. **One loop** — §3.
6. **The ratchet + exploration reserve.** Accept-on-improvement, `git reset` on regression, **every** probe recorded including discards. Fix for the known monotonic-search defect: a fixed fraction of probes are *exploration probes* whose accept criterion is information gain (a rung moved, an obligation discharged, an assumption falsified), not metric improvement. **Stall rule**: after N non-improving trials (N from `program.md`, default 5) the next probe must change a *different named axis*; the stall is recorded in `next_action.md`.
7. **Role charters** — §2, plus the CANNOT table.
8. **Runtime assignment** — the exact 16-field canonical block, byte-identical, exactly once.
9. **Authority boundary** — §6 flags.

`references/` (5, each must exist or `validate_bundle.py:399` errors):
`lab-anatomy.md` (three owners, digest freeze, void conditions, `lab/` tree) · `loop-shapes.md` (greenfield + brownfield, migrated verbatim in substance from `codex-research-os/references/operating-model.md:43-67`, plus ratchet and exploration shapes) · `role-boundaries.md` (charters → pinned roles → tool allow-lists → obligation kinds → CANNOTs) · `host-planes.md` (§3.2-3.3) · `continuity.md` (`next_action.md` contract, negative-result memory, lesson records).

### 1.2 `skills/research-claim-ledger/` (new)

`name: research-claim-ledger`. Description (**854 chars**):

> Define and enforce the evidence spine of a research effort: claim records, typed obligations, independent review records, and the promote-slowly, demote-fast evidence ladder. Use when adding, auditing, promoting, demoting, or gating a research claim; designing or repairing claim, experiment, or review schemas; resolving which reviews a claim still owes; or replacing prose review rules with executable checks. Every rung above idea requires resolved obligations that reference real review records carrying verdicts and artifact digests; a keyword found in the author's own free-text evidence is not evidence. Producer and reviewer identity must differ, and unresolved, stale, self-reviewed, or unknown obligations fail closed. Gate results are advisory evidence for the conductor and never authorize a merge, publication, deployment, or queue mutation.

**The defect this skill exists to fix (verified, and the highest-value change in the whole area).** `skills/codex-research-os/scripts/install_research_os.py:602-610` defines `evidence_text()` as the lowercased concatenation of the claim's own `evidence`, `review_evidence`, `counterevidence`, `artifact_paths`. `:828-835` then gates on substring presence:

```python
if ctype in {"empirical","benchmark"} and status in {...} and "replication" not in ev: ...
if important and status not in {...} and not any(x in ev for x in ("adversarial","review")): ...
```

A claim author writes their own `evidence` list. `evidence: ["replication pending", "no adversarial review yet"]` **passes both gates** — the second string contains "adversarial" and "review". The gate is satisfiable with a string by the very agent it constrains.

**The fix — typed obligations.** A rung is reachable only when every obligation `required_for_rung` at-or-below it is `resolved`:

```yaml
claim:
  id: clm-0001
  revision: 3                 # bumped on any claim-text edit
  owner_agent: theorist
  claim_type: empirical       # 8 values, unchanged from :503
  status: untested            # 10 values, unchanged from :504
  evidence: [...]             # human context; the gate no longer trusts it
  obligations:
    - kind: replication        # replication|novelty|adversarial|baseline|formalization|safety|data_lineage
      status: unresolved       # unresolved|resolved|failed|waived
      review_id: rev-0007
      required_for_rung: experiment_support
```

Resolution requires **all** of: the `review_id` resolves to a file in `lab/ledger/reviews/`; its `verdict` is in the accepting set for that kind; `review.author_role != claim.owner_agent`; for empirical kinds `review.artifact_digest == lab/state/harness.lock` digest; and `review.claim_revision == claim.revision` — so editing a claim after review **auto-demotes** it. "Downgrade fast", mechanized. `waived` requires a recorded human-authorization reference and is surfaced in every rollup, never silently.

Ladder preserved verbatim: `idea → conjecture → small-case support → experiment support → replication support → adversarially reviewed → formally specified → formally proved / robustly reproduced`.

`references/`: `claim-schema.md` · `evidence-ladder.md` (per-rung obligation matrix, demotion triggers) · `gate-catalogue.md` (every check, exact failure message, the substring anti-pattern it replaces) · `independence.md` (role→obligation-kind authority map; self-review is a schema error).

### 1.3 `skills/codex-research-os/` — rewritten in place, **not** renamed, **not** deleted

Renaming costs 14+ files including `TASK_COMMANDS:59`, `PACKAGED_POLICY_DIR:66`, and 16 test path references; `IDENTITY_SKILL_RENAMES` (`install_skill_bundle.py:33`) is a closed one-entry map whose in-code comment calls it "the ONLY sanctioned in-code appearance of the retired public slug".

New `SKILL.md` = retirement router **plus the retained dispatch-boundary block**. Description (**419 chars**):

> Retired scaffolding installer, superseded by autoresearch-lab and research-claim-ledger. It remains only to install or migrate an already-scaffolded repo-scoped research tree, to host the packaged runtime-assignment policy copies, and to redirect existing references. Use autoresearch-lab to run a research lab loop, and research-claim-ledger for claim, obligation, and gate design. Do not start new work in this skill.

⚠️ **Non-obvious constraint:** this file is pinned in `RESEARCH_CONSUMERS` (`tests/test_model_tier_rightsizing.py:77`) and must keep satisfying `_assert_research_dispatch_boundary` (`:447-454`) — i.e. it must retain the `conductor-supplied certified RuntimeAssignment` / `resolution_state` must equal `resolved` / requested-inherited-unresolved → stop + `SeedProposal` / inject model+effort / immutable-unavailable-readback prose. Same for `references/operating-model.md` and `references/agent-roster.md` (`:77-79`, and `:637-642` requires `operating-model.md` to pass `_assert_research_runtime_role_contract`). **Migrate their content, never their runtime block.**

## 2. Agent roster

### 2.1 Wave 1 — zero new agent files

A lab role = **(pinned generic role) + (skill-supplied charter)**. The pinned file supplies the runtime block, the authority fields, and the eight-heading submission contract; the charter supplies the CANNOT and the obligation kind. Charters live in `autoresearch-lab/references/role-boundaries.md`.

**Every charter must be tool-compatible with its host role's frontmatter allow-list** (verified from `agents/claude/*.md`):

| Pinned role | Allow-list | Write? | Web? |
|---|---|---|---|
| `sdlc-cartographer` | Bash, Read, Glob, Grep, Write | new files | no |
| `sdlc-planner` | Bash, Read, Glob, Grep, Write | new files | no |
| `sdlc-researcher` | Bash, Read, Glob, Grep, Write, WebFetch, WebSearch | new files | **yes** |
| `sdlc-implementer` | Bash, Read, Write, Edit, Glob, Grep | full | no |
| `sdlc-reviewer` | Bash, Read, Glob, Grep | no | no |
| `sdlc-critic` | Read, Glob, Grep | no | no |
| `sdlc-integrator` | Bash, Read, Glob, Grep, Write, Edit | full | no |

| Charter | Host role | Outputs | Discharges | CANNOT |
|---|---|---|---|---|
| lab_director | conductor (not an agent) | assignment, `next_action.md`, ≤1 `SeedProposal` | — | do the research; mutate the queue; approve a claim; edit `program.md` or the harness |
| repo_cartographer | `sdlc-cartographer` | Map → `lab/memory/repo_map.md`, build/test/bench commands | `baseline` (discovery half) | modify code; infer unsupported claims |
| theorist | `sdlc-planner` | ResearchBrief: ≥5 independent hypotheses incl. one long-shot, each with falsifier + cheapest decisive trial, ranked on cost-per-bit | — | run the trial; approve or promote its own claims |
| literature_scout | `sdlc-researcher` | corpus, source grades (verified/documented/inferred) | — | declare novelty |
| **novelty_auditor** | **`sdlc-researcher`** (not critic — critic has no web) | novelty review record + prior-art matrix; default `unknown_novelty` | `novelty` | generate hypotheses; mark novel without a prior-art matrix |
| experimentalist / benchmark_engineer / ablationist / formalizer | `sdlc-implementer`, own worktree | experiment record, run log path, metric extraction, harness digest readback | `baseline`, partial `experiment_support`, `formalization` | edit `lab/harness/**` or `lab/program.md`; grade the result; declare publication readiness |
| counterexample_hunter | `sdlc-implementer` (needs Bash+Edit in workspace) | counterexamples + search-space coverage statement | contributes to `adversarial` | claim "no counterexample exists" absolutely |
| data_engineer | `sdlc-reviewer` (Bash read-only) | split/leakage/lineage audit | `data_lineage` | change research claims |
| replication_reviewer | `sdlc-reviewer` (advisory_only) | verdict: reproducible / probably / under-specified / not / invalid; N-run variance figure | `replication` | review its own experiments; fix what it finds |
| adversarial_reviewer | `sdlc-reviewer` (advisory_only) | verdict: accept / weak_accept / needs_repair / reject / falsified, over 5 fixed axes: oracle validity, noise, leakage, prior-art occupancy, safety | `adversarial` | fix what it finds; authorize anything. Its **prior-art axis** is fed by a `sdlc-researcher` submission, since reviewer has no web |
| safety_reviewer | `sdlc-critic` (advisory_only) | destructive-op / credential / unbounded-spend findings | `safety` | authorize anything |
| synthesis_writer | `sdlc-researcher` | report from ledger + reviews only, rungs shown, negatives in the body | — | originate claims; raise a rung; hide a negative; publish anywhere |
| knowledge_librarian | `sdlc-cartographer` | journal, lesson records, resume context | — | change claim status; self-apply a lesson |
| ratchet advance | `sdlc-integrator` | IntegrationReport | — | advance without explicit per-advance authorization |

Independence is enforced at **two** layers: `sdlc-reviewer`/`sdlc-critic` are in `ROLE_MANIFEST_ADVISORY_ONLY_ROLES` (`validate_bundle.py:293`) where `advisory_only=true` is mandatory, and the ledger rejects `review.author_role == claim.owner_agent`. All outputs map into the closed artifact set `{Map, ResearchBrief, SeedProposal, Candidate, ReviewFinding, IntegrationReport}` (`:262`) — **do not invent a seventh**.

### 2.2 Wave 2 (optional, separately authorized) — first-class lab agents

Only if charters prove insufficient. Frontmatter sketches:

```yaml
---
name: sdlc-lab-runner            # MUST keep the sdlc- prefix: DELIVERY_ROLE_IDS is derived by
description: >-                  # filename[len("sdlc-"):-len(".md")] (validate_bundle.py:288)
  Executes exactly one research probe inside a dedicated worktree against a frozen
  harness it may not edit; records the metric and the harness digest; grades nothing.
tools: [Bash, Read, Write, Edit, Glob, Grep]
disallowedTools: [WebFetch, WebSearch]   # required: a workflow-spawned subagent does not
---                                       # inherit the host's filter
# body: exact 16-field RUNTIME MODEL ASSIGNMENT block, verbatim, exactly once
# body: ## STRUCTURED SUBMISSION with the eight headings
# body: CANNOT list incl. "never edits lab/harness/** or lab/program.md"
# NO model:, NO model_reasoning_effort:  (validate_bundle.py:1040-1043)
```

```yaml
---
name: sdlc-lab-adversary
description: Attacks the last probe and any claim it supports across oracle validity,
  noise, leakage, prior-art occupancy, and safety; recommends a rung; repairs nothing.
tools: [Bash, Read, Glob, Grep]
disallowedTools: [Write, Edit]
---
# body: must contain verbatim "You never decide release status, authorize a mutation,
#       merge, push, or edit code." (REVIEWER_NO_OUTWARD_AUTHORITY, :117)
# body must NOT match REVIEWER_OUTWARD_AUTHORITY_PATTERN (:118)
```

Same-commit cost, which is why this is gated: bump `managed_roles.global.count` and edit `SOURCE_PINNED_GLOBAL_PATHS` / `CLAUDE_GLOBAL_ROLE_FILENAMES` / `CODEX_GLOBAL_ROLE_FILENAMES` in validator source; add manifest SHA-256s to the normative contract; add role entries + `counts.projection_files` to `policy/role-manifest.v1.json` (`kind` must be `"delivery"` for anything in `DELIVERY_ROLE_IDS`); add the adversary to `PROTECTED_REVIEWER_PATHS` + `SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256` + `ROLE_MANIFEST_ADVISORY_ONLY_ROLES`; update `tests/test_role_manifest.py`, `tests/test_role_submissions.py`, `tests/test_runtime_contract_validation.py`. **This is a doctrine change, not a feature.**

## 3. The loop

### 3.1 Numbered protocol (host-independent)

| # | Step | Owner | Artifact | Authorization |
|---|---|---|---|---|
| 0 | **PRECONDITION** — oracle, baseline, variance, budgets, kill criterion + instrument, certified `RuntimeAssignment` (`resolution_state == resolved`) | director | — | any gap → one `SeedProposal`, **STOP before dispatch and therefore before spawn** |
| 1 | **FREEZE** — record `lab/harness/**` digest into `lab/state/harness.lock` | director | harness.lock | editing the harness mid-run = a **new run**, human-authorized 🔒 |
| 2 | **SELECT** — one highest-leverage uncertainty; claim ids; probe kind; budget; exploration-vs-ratchet probe | director | assignment | — |
| 3 | **HYPOTHESIZE** — ≥5 independent hypotheses incl. one long-shot, each with falsifier + cheapest decisive trial; recommend one on cost-per-bit | theorist | ResearchBrief | — |
| 4 | **PRE-REGISTER** — metric name, direction, comparison baseline, success/failure criteria, budget, written **before** the run. A post-hoc metric change is a new probe id | director + prober | experiment record | — |
| 5 | **PROBE** — corpus-shaped → pipeline; experiment-shaped → worktree probe: edit only in-scope files, commit, run oracle under wall-clock budget with `> run.log 2>&1`, extract only the metric lines into context, append one line to `trials.jsonl`. Crash → ≤2 bounded repairs, then record `failed`. Re-verify the harness digest; mismatch ⇒ **probe void** | prober | Candidate + trial line | never touches anything outside `lab/` 🔒 |
| 6 | **LEDGER** — write claim/experiment/review-obligation records, obligations `unresolved`. Single writer (lead-only reservation) | director | ledger diff | — |
| 7 | **REVIEW** — independent reviewers discharge obligations in parallel; `author_role != owner_agent`; adversary runs all 5 axes | reviewers | ReviewFinding | verdicts are recommendations, never acceptance |
| 8 | **GATE** — run the gate set; output is **evidence**, exit code is not permission | director | gate receipt | — |
| 9 | **RATCHET / DISCARD** — advance only if metric moved in the pre-registered direction **and** gate passed **and** adversary verdict ∈ {accept, weak_accept} **and** explicit per-advance authorization exists. Otherwise discard the commit — **the trial line stays** | `sdlc-integrator` | IntegrationReport | 🔒 **human authorization required for every advance** |
| 10 | **CHECKPOINT** — append a lesson record; write `next_action.md`; ≤1 `SeedProposal` for work outliving the lab | director + librarian | next_action.md | lessons **never** self-apply 🔒; a gate-loosening lesson additionally needs adversarial review |

Steps 2-8 repeat inside the trial budget with no human prompt (inner ratchet). Steps 9-10 run at most once per session, so the authority boundary is not a per-iteration tax.

### 3.2 Claude Code mapping

- **0-2, 8, 10** — conductor executes directly (cheapest rung of `references/delegation-planes.md`).
- **3** — one `sdlc-planner` subagent (theorist charter), read-only.
- **5, corpus** — parallel read-only `sdlc-researcher` subagents (safe).
- **5, experiment** — **exactly one writer, in its own worktree** (`EnterWorktree`); `lab/harness/**` read-only to it. Parallel writers conflict.
- **5→6→7→8 as a Workflow** when the fan-out is deterministic: `investigate` (parallel) → `record` (**single writer**, ledger is a shared file) → `review` (parallel, independent) → `gate` (Bash). Per-stage `agent()` calls each carry an explicit conductor-supplied `RuntimeAssignment`; **no `model:` literal appears in any lab file** — lane family lives in policy, the exact ID arrives at dispatch.
- **7** — one read-only reviewer subagent per obligation kind, `run_in_background`; may overlap the next loop's step 3.
- **9** — `sdlc-integrator`, WIP cap 1, only with explicit authorization.
- **Two cases where a Workflow earns its keep even for a single probe:** variance calibration (N identical oracle runs, once per lab, feeds step 0) and a post-stall multi-axis sweep (K worktrees → one synthesize, only after the stall rule has fired twice).
- **Anti-patterns, stated explicitly in `host-planes.md`:** no Agent Team for the ledger (documented orchestration-file race); no `CronCreate`/unattended scheduler (it would advance state with no conductor present — the exact violation the two-plane split exists to prevent). "Continuous" means resumable from `next_action.md`.
- WIP caps: prober ≤1, theorist ≤1, reviewers ≤1 per kind, nesting ≤2.

### 3.3 Host-agnostic fallback

- **Codex:** the 17 pinned `agents/codex/research/*.toml` already are the roster; `research_director` coordinates and is the only Seeds-read-only inspector via the exact `Seeds(<target>, prime | ready --format json | blocked --format json)` contract. `max_depth` may be 1 → keep the plan flat, route peer messaging through the conductor.
- **Any AGENTS.md host with no delegation at all:** one agent plays the charters **sequentially, in writing**. This works because the CANNOTs are enforced by **artifact ordering**, not process separation: the brief must exist as a file before the probe commit exists; a review must cite trial ids already present in the append-only ledger; the writer may cite only what is already written. The gate verifies the ordering after the fact **and records that independence was textual rather than structural** — yes in evidence, no in independence, and the receipt says which.
- **What never degrades on any host:** harness immutability, append-only trials, obligation resolution with `author_role != owner_agent`, the conductor-records step, integrator-only ratchet advance, and the `RuntimeAssignment` precondition.

## 4. Gates — the seven executable invariants

Replace `check_review_gates.py`'s substring logic. Each is a few lines of stdlib Python over `lab/`:

1. **Harness immutability** — `lab/harness/**` digest identical across every commit referenced by every trial line in this run; mismatch ⇒ probe void, result discarded, incident recorded.
2. **Program custody** — `lab/program.md` not modified by any probe commit.
3. **Append-only ledger** — every previously recorded trial line byte-identical and in the same position; the only diff is appended lines.
4. **Baseline + variance present** — baseline scalar with its command and commit, plus a variance figure from ≥2 identical runs. No improvement claim without it.
5. **Rung ⇒ resolved obligations by id** — `experiment_support` ⇒ ≥1 trial id; `replication_support` ⇒ ≥2 trial ids at the same commit with a within-variance delta; `adversarially reviewed` ⇒ a review record whose `author_role != owner_agent`, whose `artifact_digest` matches `harness.lock`, and whose `claim_revision == claim.revision`; novelty ⇒ a populated prior-art matrix.
6. **Negatives retained** — no `failed`, `worse`, `void`, or `falsified` line ever removed; ledger trial count ≥ count implied by the scratch branch history.
7. **Ratchet legitimacy** — every advance commit on the durable branch maps to a trial line satisfying all four step-9 conditions and was executed by the integrator. A pass is **evidence for** the conductor, not authorization for the next advance.

`review-gates-legacy` is kept as **advisory warnings only** for already-installed target repos; deleting it would break their `make research-check`. Legacy/new disagreement is a first-class reported finding.

## 5. Migration checklist

### Wave 1 — additive, no deletions, no pin edits
- [ ] `skills/autoresearch-lab/SKILL.md` + the 5 `references/*.md` (every `references/x.md` string in SKILL.md must resolve — `validate_bundle.py:399`).
- [ ] `skills/research-claim-ledger/SKILL.md` + the 4 `references/*.md`.
- [ ] `skills/codex-research-os/SKILL.md` → retirement router, **retaining** the dispatch-boundary prose (`tests/test_model_tier_rightsizing.py:77`, `:447`).
- [ ] `references/operating-model.md` — migrate the ladder into `research-claim-ledger/references/evidence-ladder.md` and the loop shapes into `autoresearch-lab/references/loop-shapes.md`. **Keep the file and its runtime block** (`:78`, `:637-642`); delete only the 20-directory layout section.
- [ ] `references/agent-roster.md` — **keep** (pinned at `:79`); add a pointer to the charter table.
- [ ] `skills/codex-research-os/policy/*.json` — **byte-identical, untouched** (`PACKAGED_POLICY_DIR:66` byte-compares them; `tests/test_runtime_contract_validation.py:22-23` reads them by path). New skills *reference*, never copy.
- [ ] `scripts/install_research_os.py` — **extend in place**, do not fork. Emit `revision` + `obligations` + `lab/` tree + the new gate scripts behind a `--lab` flag. Keep the task name `research-os:install` exactly (`REQUIRED_TASKS:34`, `TASK_COMMANDS:59`). Generated gate scripts must use the pinned mise/uv launcher (`test_generated_makefile_uses_mise_uv_python`).
- [ ] `agents/codex/research/*.toml` (17) + `agents/codex/research/README.md` — **unchanged bytes**; README gains a pointer only if it still passes `_assert_research_dispatch_boundary` (`:76`).
- [ ] `mise.toml` — optionally add `lab:check`; **no validator edit needed** (extra tasks are unconstrained). Do **not** touch `check.depends` (`tests/test_gate_graph.py:376`).
- [ ] Prose updates: `AGENTS.md`, `README.md`, `skills/agentic-sdlc/SKILL.md`, and `skills/agentic-sdlc/references/research-team.md:9-16` (repoint "the full implementation ships IN this bundle as `skills/codex-research-os/`" → `skills/autoresearch-lab/`; reconcile its 8-role table with the charter table). `README.md` and `research-team.md` are both in `RESEARCH_CONSUMERS` — keep their dispatch-boundary prose intact.
- [ ] New tests: `tests/test_autoresearch_lab.py` (name==dirname, description ≤1024, references exist, obligation-gate exploit fixtures fail closed, legacy-gate exploit fixture is *shown* to pass). Add the two new SKILL.md paths to `RESEARCH_CONSUMERS` in the same commit — a strengthening test edit.
- [ ] Prose tripwires, verified from the scanners: never write a literal `sd <action>` (`SD_COMMAND`, `tests/test_preflight_capabilities.py:78`); never place a Seeds mutation verb adjacent to a Seeds object — `create/claim/update/close/sync/disposition/init` next to `Seeds issues|items|records|states|queues` in **either** order trips `SEEDS_ACTION_FIRST`/`SEEDS_ACTION_SUBJECT_FIRST` (`:63-72`), and the lab's vocabulary is full of the word *claim*, so grep before committing; never emit the string `| Consequence lane ​| Exact model ID |` in any `.md` but the calibration file (`tests/test_model_tier_rightsizing.py:730`); avoid `aws[.]dev/`, `[.]a2z[.]com` (defanged here) (`SECRET_PATTERN:250`).
- [ ] `./scripts/bump-version.sh <version>` — never hand-edit one manifest.
- [ ] Gate order: `mise run validate` → `test` → `self-test` → `check`. `./scripts/install-skill-bundle.sh self-test` only if the installer changed (it should not).

### Wave 2 — trigger-gated, separate authorized commits
- [ ] First-class lab agent files (§2.2) — trigger: charters demonstrably insufficient, with named evidence.
- [ ] Claude projections for research roles — requires changing `expected_hosts` (`:856`), `counts.projection_files` 31→48, 17 new manifest entries, `_role_manifest_web_required` extension. **A doctrine change to the "research roles are Codex-only" invariant; propose and authorize on its own.**
- [ ] Retire the 17 TOMLs / delete `skills/codex-research-os/` — trigger: pilot has run **and** no in-repo or downstream consumer references `agents/codex/research/`. One commit: delete TOMLs; drop `research-os:install` from `mise.toml` + `REQUIRED_TASKS` + `TASK_COMMANDS`; update `managed_roles.research`; regenerate `policy/role-manifest.v1.json` counts + `generated_from.normative_contract_sha256`; update `SOURCE_PINNED_RESEARCH_PATHS`, `RESEARCH_ROLE_IDS`, `PROTECTED_REVIEWER_PATHS`, `SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256`, `RESEARCH_DIRECTOR_*`; repoint `PACKAGED_POLICY_DIR`; rewrite `tests/test_research_os_launcher.py`; fix count assertions in `tests/test_role_manifest.py` and `tests/test_runtime_contract_validation.py`; fix `RESEARCH_CONSUMERS` and `tests/test_preflight_capabilities.py:916`. `mise run check` is the arbiter. Note `test_f4_coordinated_repin_authority_grab_still_fails` exists specifically to make coordinated repins hard.

## 6. Install path — no installer changes

`discover_entries` (`install_skill_bundle.py:770`) globs `skills/*/SKILL.md`; there is **no pinned skill count anywhere**. Adding two directories with valid `SKILL.md` files is the entire integration.

```
mise run bundle:install            # this host                        🔒 namespace mutation
mise run bundle:install:claude
mise run bundle:install:codex
mise run bundle:install:all-hosts  # WSL first, then native Windows, reported separately
mise run bundle:status
mise run research-os:install -- --target /path/to/repo --project-name "Name" --lab --dry-run
mise run research-os:install -- --target /path/to/repo --project-name "Name" --lab
```

Unix symlinks; Windows automatic mode tries junctions/file symlinks then copies (strict link mode has no fallback). Ownership state under `XDG_STATE_HOME` / `LOCALAPPDATA`. For Claude use direct install **or** the marketplace, never both. Target-repo install stays conservative: create-missing, skip-existing, never overwrite project instructions, `--force` only to intentionally replace generated files. `mise trust` is per-absolute-config-path: a linked worktree must trust its own `mise.toml`, and `MISE_PARANOID=1` fails closed until it does.

## 7. Pilot mission

### Pilot 1 (mandatory, wave 1) — the lab's first claim is about the gate it replaces

Deliberate choice: the subject and the machinery are the same thing, so a weak gate cannot hide, and the `codex-research-os` failure mode (structurally verified, never behaviourally run) cannot repeat.

**`clm-0001`** — *"`check_review_gates.py` can be satisfied by a claim author with no independent review, because it substring-matches the author's own free-text evidence."* `claim_type: implementation`, `importance: high`, `status: untested`.

**Bounds, declared before starting:** 1 claim, 3 probes, 3 obligations, 1 loop, ends at a written `next_action.md`. No repo mutation outside `lab/`. No push, no PR, no queue mutation. Harness = the two gate scripts + fixtures, digest-frozen before probe 1, re-verified after probe 3. The prober may not edit either gate — the digest check makes that a void probe rather than an argument.

| Probe | Pre-registered prediction | Metric |
|---|---|---|
| `prb-0001` exploit | fixture claim `importance: high`, `claim_type: empirical`, `status: experimentally_supported`, `evidence: ["replication pending","no adversarial review yet","prior art unclear"]` → legacy gate **exit 0** | `gate_exit_code`, boolean, pre-registered |
| `prb-0002` control | same fixture, obligation gate → **non-zero**, naming all three unresolved obligations | `gate_exit_code` + count of named obligations |
| `prb-0003` independence | fixture with a review whose `author_role == owner_agent` → new gate **rejects**, legacy **accepts** | `gate_exit_code` per gate |

**Obligations to discharge:** `replication` (independent re-run of all three probes under a `replication_reviewer` charter on `sdlc-reviewer`), `adversarial` (attack the claim: is `importance: high` reachable in practice? does any installed ledger depend on legacy behaviour?), `safety` (fixtures touch no credentials, no destructive ops, bounded runtime).

**Pilot pass criteria — all eight in writing:**
1. Three probes recorded with pre-declared metrics, including any that falsify the claim.
2. Obligations resolve only via records with `author_role != owner_agent`; hand-editing an evidence string cannot promote the claim.
3. `clm-0001` reaches `experimentally_supported` **only** after `replication` + `adversarial` resolve; mutating the claim text afterwards auto-demotes via revision mismatch (verify deliberately).
4. Deliberate harness tamper in a probe commit → invariant 1 fires, probe recorded void.
5. Precondition refusal works: run once with no baseline and once with an unresolved `RuntimeAssignment`; both must stop before dispatch and emit exactly one `SeedProposal`.
6. Legacy and new gate results both recorded; the disagreement is the headline, not a footnote.
7. One lesson record proposing a gate change, **not applied**, carried as a conductor decision.
8. `next_action.md` alone resumes a cold session — verify by actually resuming. `mise run check` green. Zero unauthorized outward effects.

**Falsification condition — the pilot is honest only if this can happen:** if `prb-0001` exits non-zero, `clm-0001` is `falsified`, the evidence stays recorded, and the obligation redesign loses its primary justification. Record it; do not retry into agreement.

### Pilot 2 (follow-on, exercises the metric ratchet) — trigger: Pilot 1 complete

*Reduce `mise run check` wall-clock on `agentic-sdlc` without weakening a single check.* Real agent-independent oracle, brownfield, and a fake win is detectable. `lab/harness/` prints three numbers — `seconds:`, `checks_passed:`, `assertions:`. **Metric: minimize `seconds` subject to `checks_passed` and `assertions` ≥ baseline**; a trial lowering either is `void`, not an improvement. In-scope: the `mise.toml` task graph, `scripts/validate_bundle.py`, `tests/`. Out of scope: every `policy/*.json`, every `agents/**` file, every pinned hash or version. 6 min/trial, 8 trials, one session. Stall rule: after 3 non-improving trials change axis (parallelism / redundant work / test discovery / uv invocation). Kill: 8 trials with no ≥10% improvement, instrumented by the `seconds` column. **Precondition Workflow: 3 identical baseline runs; if variance exceeds the target improvement the pilot stops at step 0, and that is a PASS for the design.** A verdict of "the gate is already near its floor, here is the variance figure proving 8 more trials wouldn't help" is a full success.

## 8. Human authorization boundaries 🔒

Every one is operation-specific; none is granted by a green gate, a reviewer verdict, a metric improvement, or a conductor decision.

1. **Ratchet advance / fan-in** onto any durable branch — `sdlc-integrator` executing an **already-authorized** mutation, per advance (step 9).
2. **Push, PR create/update, merge, publication, deployment, release, version bump.** The lab never publishes; the autoresearch self-publishing anecdote is explicitly out of scope.
3. **Seeds queue mutation** (create/claim/update/close/sync/disposition) — conductor-only; the lab emits at most one typed `SeedProposal` and never self-files.
4. **Editing `lab/program.md`** — the human's only lever. Agents propose; the conductor decides; the change is a recorded diff.
5. **Editing `lab/harness/**` mid-run** — forbidden; a harness change starts a **new run** with a new digest and a new baseline.
6. **Waiving an obligation** — requires a recorded human-authorization reference and appears in every rollup.
7. **Applying a lesson record**, especially any that loosens a gate — never self-applied; gate-loosening lessons additionally require adversarial review.
8. **Writing anywhere outside `lab/`** in a target repo, and running the lab against a repo other than the one authorized.
9. **Probes with spend, credentials, network writes, or destructive filesystem effects** — safety obligation plus explicit authorization; the default prober has no web access.
10. **`mise trust`** for each absolute config path, including every linked worktree's own `mise.toml` (`MISE_PARANOID=1` fails closed until then).
11. **Persistent config/credential mutation** — `~/.codex/config.toml`, `settings.json`, shell aliases, credential stores. Never make permanent Windows environment/trust/config changes. Process-scoped `mise --no-config` execution is allowed without persisting trust.
12. **`bundle:install` / `bundle:uninstall` / `--migrate-state`** — namespace and ownership-state mutation on the operator's home.
13. **Wave-2 doctrine changes** — new global agent files, research-role Claude projections, retiring the 17 TOMLs, any coordinated repin of a pinned digest.
14. **Any unattended/scheduled invocation** — not authorized; continuity is resumption from `next_action.md`, never a resident loop.

**Where this design deliberately rejects its inspiration.** Upstream `program.md` says *"NEVER STOP … do NOT pause to ask the human … You are autonomous."* Correct for its context: one editable file, one scalar, a frozen judge, a git ratchet, and a blast radius of one throwaway training run. Here the loops touch a real repository, a shared queue, and a claim ledger whose promoted claims are consumed as evidence by downstream delivery work. So the lab keeps the loop shape, the three-owner split, cheap-probe economics, fixed budgets, log-redirection discipline, and the ratchet — and replaces "never stop" with **bounded continuity**, **evidence ratchet rather than metric-only ratchet**, **pre-registration as a schema field rather than an instruction**, and **independence as a field comparison**. Self-improving ≠ self-authorizing.
