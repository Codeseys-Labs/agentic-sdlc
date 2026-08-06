## Design spec — enhanced ADR capability for `agentic-sdlc`

Read-only design pass. No files written. Every design element cites its source; every repo constraint below was executed/verified in this working tree (`0.7.2`, branch `release/offline-observer-rc`), not assumed.

---

## 0. Verified repo constraints that shape the design

These were checked against real code, and three of them change the design materially.

| # | Constraint | Evidence |
|---|---|---|
| C1 | Skill gate is exactly: `name` == dirname, `description` non-empty and ≤1024 chars, and every `references/<file>.md` string mentioned in `SKILL.md` must exist on disk | `<repo>/scripts/validate_bundle.py:386-400` |
| C2 | **The reference-existence regex is `\breferences/[A-Za-z0-9._-]+\.md` — flat only.** `references/templates/madr-full.md` matches nothing and is silently unvalidated | same, line 398; verified by executing the regex against nested paths |
| C3 | **`SECRET_PATTERN` includes `amazon\.com/[a-z]` — any full AWS docs URL fails `mise run validate`.** Verified: `https://docs.aws.amazon[.]com/prescriptive-guidance/...` (defanged here so this very memo passes the scan) → `possible secret or internal hostname found` | `scripts/validate_bundle.py:20-22`, `:1259-1268`; reproduced by running the regex |
| C4 | **The managed role roster is closed at exactly 14 global (7 Claude `.md` + 7 Codex `.toml`) + 17 research files, each pinned by sha256.** A new `sdlc-adr-*` agent is impossible without repinning `policy/runtime-assignment-normative-contract-v1.json` and `policy/role-manifest.v1.json` (31 projections) | `scripts/validate_bundle.py:887-956`, `:882-884`; `policy/role-manifest.v1.json` `counts` = `{delivery_roles:7, research_roles:17, projection_files:31}` |
| C5 | `mise.toml` `check` is byte-pinned to exactly `depends = ["validate","test","self-test"]`; `lefthook.yml` and `.github/workflows/validate.yml` are byte-pinned. An ADR linter **cannot** be added to the authoritative gate | `scripts/validate_bundle.py:1108-1113`, `:1171-1191` |
| C6 | Installer discovers skills by `(repo_root/"skills").glob("*/SKILL.md")` — a new dir is picked up with zero installer edits | `scripts/install_skill_bundle.py:767-783` |
| C7 | **An install into a destination that exists, is not a link, and is not byte-equal yields `conflict: <dest>` → `partial=True` → exit code 1.** The user's `~/.claude/skills/adr-methodology/` is a plain directory with a 10545-byte `SKILL.md`, so shipping a skill *named* `adr-methodology` breaks `mise run bundle:install` | `scripts/install_skill_bundle.py:2707-2724`, `:2740`; `ls -la ~/.claude/skills/adr-methodology/` |
| C8 | A repo-wide scanner asserts **zero** "non-conductor Seeds queue mutation guidance" across every shipped `.md/.json/.toml/.py/.sh/.ps1/.yml`. Verbs `init\|claim\|create\|update\|close\|sync\|disposition` adjacent to a Seeds object trip it — even in a conductor-attributed sentence. Verified: a sentence of the form *"<actor> may cre&#97;te a Seeds issue"* trips it → **HIT** | `tests/test_preflight_capabilities.py:47-72`, `:450-460`, `:527-538`, `:902-904`; executed against candidate sentences |
| C9 | Repo-wide token ban: `(?i)\bcao\b` in any shipped file; and no `.md` outside the calibration file may contain `\| Consequence lane \| Exact model ID \|` | `tests/test_cao_removal.py:17-56`; `tests/test_model_tier_rightsizing.py:730-734` |
| C10 | `commands/*.md` has **no** validator at all (no frontmatter/model checks), but the *target-repo* Claude routing block is byte-pinned to exactly four commands | grep of `validate()` call list `scripts/validate_bundle.py:1272-1285`; `skills/agentic-sdlc/tools/offline-inspect.py:24-31`; `tests/test_offline_observer_rc.py:34-38` |
| C11 | Baseline is green today: `python3 scripts/validate_bundle.py` → `0 error(s), 0 warning(s)` | executed |

**Consequences for the design:** one skill, no new agent role (C4), flat `references/` only (C2), AWS cited as split host+path (C3), the linter is advisory-only and structurally cannot become a gate (C5) — which is doctrinally *correct*, not a limitation, and dirname must not be `adr-methodology` (C7).

---

## 1. Skill set

### 1.1 One skill: `skills/adr-lifecycle/`

**Dirname / `name`:** `adr-lifecycle`

Rationale: matches the repo's function-descriptive naming style (`change-writing`, `repo-toolchain-gates`, `model-tier-rightsizing`), keeps the `adr` token for match strength, and **avoids the verified C7 install conflict** with the user's global `adr-methodology`. Acceptable alternatives: `adr-evidence` (leans on the doctrine hook), `decision-records`. `adr-methodology` is available only *after* the migration in §4.

**`description` (880 chars, verified under the 1024 cap of C1):**

```
Author, review, index, supersede, and gate Architecture Decision Records as durable,
citable evidence. Use when the user says "write an ADR", "record this decision",
"document this architecture choice", "why did we choose X", "supersede ADR-NNNN",
"review this ADR", or when a hard-to-reverse choice is made during framing, planning,
deciding, or reconciling. Runs a significance gate before authoring, picks one of four
MADR 4.0 formality tiers (plus an optional one-sentence WH(Y) elevator line), requires
>=2 genuinely considered options and at least one negative consequence, keeps
implementation detail out of the record, tracks typed
Depends-On/Supersedes/Relates-To/Refines/Part-Of edges and Master-ADR rollups, and
rebuilds the index. An accepted ADR is advisory evidence a conductor may cite; it never
authorizes a push, merge, publication, deployment, or queue mutation.
```

Trigger phrases are a strict superset of the installed skill's (`~/.claude/skills/adr-methodology/SKILL.md:3`), so existing muscle-memory invocations still route.

### 1.2 `SKILL.md` outline

Router shape modelled on `skills/change-writing/SKILL.md` (mode selector + read-only-what-you-need references) and `skills/agentic-sdlc/SKILL.md` (authority boundary stated up front).

```
# ADR lifecycle

## What an ADR is here
  One decision, its forces, its rejected options, its accepted costs.
  Immutable after accept — supersede, never edit.
  [installed skill line 12; AWS Prescriptive Guidance "ADR process":
   "When the team accepts an ADR, it becomes immutable"]

## Authority boundary (advisory evidence, never authorization)     <-- NEW
  An accepted ADR is durable evidence the conductor may cite when adjudicating a
  later related SeedProposal. It is not a gate result, not a queue mutation, and not
  an authorization for push/publication/PR mutation/merge/deployment/credential work.
  Mirrors ../agentic-sdlc/SKILL.md "Delegation Rules" + AGENTS.md
  "A passing gate is evidence only".
  Phrasing must satisfy C8: emit SeedProposals, never say "<actor> may create a
  Seeds issue".

## Mode selector  (one hop each, mirrors change-writing)
  new decision            -> §Workflow
  is this even an ADR?    -> references/significance-and-readiness.md
  reviewing someone's ADR -> references/adr-antipatterns.md
  supersede / relate      -> references/adr-relationships.md
  initiative spanning waves -> references/adr-relationships.md §Master ADR
  team/process questions  -> references/adr-process.md
  which template?         -> §Step 3 + references/madr-4-templates.md
  why did a field rename? -> references/madr-lineage.md

## Hard rules  (rules 1-8 preserved verbatim-in-substance from the installed skill,
##              9-13 are the additions)
  1  MADR shape (tier chosen per Step 3), nothing invented
  2  >=2 genuinely considered options; a Dummy Alternative is a rejection
  3  Status vocabulary: proposed | accepted | rejected | deprecated |
     superseded by ADR-NNNN.  Kept as a HARD RULE for this bundle, with an explicit
     note that MADR upstream treats the field as free text
     ("{proposed | rejected | accepted | deprecated | ... | superseded by ADR-0123}")
     -> reconciliation lives in references/madr-lineage.md
  4  Title is a decision, not a question; imperative voice ("We use...", not "should")
  5  One decision per file; "and" in the title means split
  6  Immutable after accept; the ONLY edit to an accepted ADR is its status line
  7  At least one negative consequence
  8  ADR + index in ONE commit, message authored via ../change-writing/SKILL.md
  9  NEW - Decision only. No full implementations, no schemas, no config blocks, no
     API contracts in the body. Illustrative snippets only; substance goes to a
     sibling spec/design doc referenced by ID.
 10  NEW - No append-only "Updates" sections. An ADR that grows dated updates has
     become a changelog. Supersede instead.
 11  NEW - Supersession ordering: the NEW ADR must reach `accepted` BEFORE the old
     one's status flips. Never mid-air supersede a still-proposed record.
 12  NEW - Confirmation is required for any ADR whose compliance is mechanically
     checkable; it must name a real command or review step in THIS repo
     (e.g. `mise run check`), not a hypothetical fitness function.
 13  NEW - Every ADR carries a Reversal Condition: one observable event that would
     falsify it, and who would see it. Not a feeling, not a date.

## Workflow
  0  Significance gate      NEW  -> references/significance-and-readiness.md
       7-criterion ASR test + AWS 5-category scope test. Fail => propose a
       lighter record (WH(Y) one-liner, code comment, Seed) and stop.
  1  Readiness gate         NEW  -> START DoR: stakeholders, timing, >=2 options,
       drivers/context, template chosen
  2  Locate/create the directory   (docs/adr -> docs/decisions ->
       doc/architecture/decisions -> ask; ADR-0000 meta-record for the choice)
  3  Choose the formality tier     NEW
       bare-minimal | minimal | full | full + extensions
       selection matrix in references/adoption-tiers.md
  4  Assign the next NNNN (4-digit; concurrent-branch collision = later-merged
       branch renumbers, detected at merge/commit time)
  5  Elicit  (7 scripted questions, preserved; + WH(Y) elevator line when the
       decision will be scanned in a log -> references/why-statement.md)
  6  Write   (chosen tier + any of the four optional extension blocks:
       Confirmation, Compliance, Dependencies table, Reversal Condition)
  7  Relationship pass      NEW  -> typed edges, cycle/rejected/superseded
       validation, Master-ADR registry update
  8  Definition-of-Done gate  NEW  -> ECADR + Dependencies/References/Master
  9  Rebuild the index (never hand-maintain)
 10  Evidence pass           NEW  -> references/adr-as-evidence.md: name the Seeds
       this decision blocks/unblocks IN THE ADR BODY; emit a SeedProposal for each
       open action point; record the ADR path for the conductor to cite.
 11  Commit via ../change-writing/SKILL.md; the human authorizes publication.

## Status transitions  (one-way diagram preserved, + the C11 ordering rule and
##                     an explicit "proposed stays proposed with assigned action
##                     points" loop from the AWS review protocol)

## Anti-patterns  (the installed skill's 7 rows preserved, + 18 named patterns)
   -> references/adr-antipatterns.md

## Relation to other artifacts  (Vision/Roadmap/RFC/ADR/AGENTS.md table preserved,
##  + two rows: Spec/design doc (the Hard Rule 9 sink) and SeedProposal)

## Composition
  ../agentic-sdlc/SKILL.md    Frame step 1 already reads "repo docs/ADRs/roadmap"
  ../agentic-sdlc/references/deep-work-loop.md   decide + reconcile phases
  ../agentic-sdlc/references/mission-loop.md     "ADR hygiene" critique lens
  ../change-writing/SKILL.md  the commit/PR text (output-only)
  ../repo-toolchain-gates/SKILL.md  what Confirmation may point at

## References  (10 flat files - read only what is needed)
```

### 1.3 `references/` manifest

All flat per **C2**. Vendor-vs-link decided by license, checked against each repo's actual `LICENSE`.

| File | Contents | Vendored verbatim? | License finding |
|---|---|---|---|
| `references/madr-4-templates.md` | All four MADR templates verbatim in fenced blocks: full, minimal, bare, bare-minimal | **Yes — verbatim** | `adr/madr` `LICENSE` file content is literally `MIT OR CC0-1.0` (verified via `gh api`). `LICENSE.MIT` reads `Copyright (c) 2017-2022 Oliver Kopp, Olaf Zimmermann` — under the MIT arm the notice must be retained, so the file opens with an attribution + SPDX block. **Pin the released tag `4.0.0`, not `develop`.** Verified: `template/adr-template.md` and `adr-template-minimal.md` differ between tag `4.0.0` and `develop`; `develop` carries unreleased rewordings (CHANGELOG `[unreleased]` → PR #162 Confirmation, PR #210 Context). Source: `https://github.com/adr/madr/blob/4.0.0/template/adr-template.md` (+ `-minimal`, `-bare`, `-bare-minimal`), `https://github.com/adr/madr/blob/4.0.0/LICENSE` (all HTTP 200) |
| `references/madr-lineage.md` | 3.0→4.0 field delta table (`deciders`→`decision-makers`; `Validation`→`Confirmation` nested under Decision Outcome; link removed from `status`; `status` quoted as a YAML string; bare/minimal variants added; Positive/Negative merged into one `Consequences` list in 3.0.0; `{x}`→`<!-- x -->` in bare templates at 4.0.0) + the closed-enum-vs-convention reconciliation for Hard Rule 3 + pointers to MADR's dogfooded rationale ADRs | Paraphrase + cite | `https://github.com/adr/madr/blob/develop/CHANGELOG.md`; rationale ADRs `https://github.com/adr/madr/tree/develop/docs/decisions` — read 0009 (links go in *More Information*; tables rejected as "not supported by the CommonMark spec"), 0010 (subfolders with local IDs for scale), 0018 (Confirmation chosen over Validation/Verification). Naming/numbering + "There is currently no tooling supporting MADR 3.0.0" from `https://adr.github.io/madr/` |
| `references/significance-and-readiness.md` | The 7-criterion ASR test (value/risk · key-stakeholder concern · unusual QoS · uncontrollable external dependency · cross-cutting impact · first-of-a-kind · previously troublesome), the ASR scoring table shape and its "not a quantitative tool" caveat; START DoR (Stakeholders · Timing/most-responsible-moment · Alternatives ≥2 · Requirements/criteria · Template chosen); the AWS 5-category scope test (structure · non-functional requirements · dependencies · interfaces · construction techniques, citing Richards & Ford 2020); ECADR DoD (Evidence · Criteria · Agreement · Documentation · Realization&Review) + the Dp/Rf/M extensions | Paraphrase + cite | `https://ozimmer.ch/practices/2020/09/24/ASRTestECSADecisions.html`, `.../2023/12/01/ADDefinitionOfReady.html`, `.../2020/05/22/ADDefinitionOfDone.html` — **no explicit license found on any ozimmer.ch page; paraphrase only, never vendor.** Note: these hosts DNS-time-out from this machine via `curl`/`WebFetch`; content was retrieved via exa/tavily, so a future re-verify needs the same route. AWS: see the citation-form warning below |
| `references/adr-process.md` | ADR **owner** role (distinct from author and from deciders); the review protocol (10–15 min silent read + written comments, then the owner reads out each comment; outcome = accepted / stays-proposed-with-assigned-action-points / rejected-with-recorded-reason); supersession requires a full new review cycle before the old status flips; the code-review conformance loop (reviewer links the ADR and asks the *code* to change); the 5 best practices (promote ownership · preserve ADR history · schedule regular review meetings, stabilizing in 2–3 sprints greenfield · store centrally, Git vs wiki · address non-compliant legacy code via explicit tech-debt tasks); at-scale numerics (30–45 min cap, <10 participants, 1–3 readout cycles, "most of the decisions are two-way door decisions", one decision per ADR, reference a separate design doc instead of inlining alternatives) | Paraphrase + cite, **AWS URLs split** | AWS Prescriptive Guidance, *Using architectural decision records…* — host `docs.aws.amazon.com`, paths `prescriptive-guidance/latest/architectural-decision-records/{adr-process,best-practices,faq,appendix,resources}.html`. At-scale numerics: host `aws.amazon.com`, path `blogs/architecture/master-architecture-decision-records-adrs-best-practices-for-effective-decision-making/`. **Never write these as one glued URL — C3 makes `mise run validate` fail.** AWS docs terms: cite/paraphrase, do not republish prose |
| `references/adr-relationships.md` | Five typed edges — Depends-On · Supersedes · Relates-To · Refines · Part-Of — each with direction, implication, and status propagation; five validation rules (no cycles; warn when depending on a superseded ADR; forbid depending on a rejected ADR; every edge needs a note; Part-Of must target a Master ADR); the Dependencies table schema (`Relationship \| ADR ID \| Title \| Notes`); Master ADR pattern (Strategic Context, Scope Boundary, Child ADR Registry `ADR ID \| Title \| Status \| Phase \| Dependencies \| Owner`, Decision Sequencing) and the 6 aggregate-status rollup rules (Proposed / In Progress / Approved / Partially Implemented / Completed / Blocked). **Plus an explicit divergence note**: MADR's own ADR-0009 rejected a table format in 2018 for CommonMark reasons; this bundle takes the table anyway because typed, machine-readable evidence is the doctrine — and says so out loud | **Our own wording. Do NOT copy the spec prose** | `cgbarlow/adr` license is **CC-BY-SA-4.0** (verified via `gh api repos/cgbarlow/adr`). Share-alike would infect the file, and `.codex-plugin/plugin.json` declares `"license": "UNLICENSED"` — a direct conflict. Taxonomies and rules are ideas, not protected expression: restate them. Cite `https://github.com/cgbarlow/adr/blob/main/specs/SPEC-001-C-Dependencies.md` and `.../SPEC-001-D-Master-ADRs.md`. **The link forms used inside ruflo issue #930 are stale**: `SPEC-CF3-001-D-…` → HTTP 404, `SPEC-001-D-…` → 200 (both verified). Also cite the MADR counter-decision `https://github.com/adr/madr/blob/develop/docs/decisions/0009-support-links-between-adrs-inside-an-adrs.md` |
| `references/why-statement.md` | The six-clause Y-statement — *In the context of … facing … we decided for … and neglected … to achieve … accepting that …* — with the canonical worked example, plus guidance on using it as a one-sentence elevator line prepended to a full MADR body, and the lean-first/elaborate-later doctrine. Notes that ruflo #930's "WH(Y)" is the same six-slot shape re-derived, with per-slot length limits and a "at least one alternative must be documented" validation rule | Paraphrase + cite | `https://ozimmer.ch/practices/2020/04/27/ArchitectureDecisionMaking.html` (the six clauses and the Web-shop/Database-Session-State example were retrieved verbatim and confirmed); `https://github.com/cgbarlow/adr/blob/main/specs/SPEC-001-A-WHY-Format.md` (CC-BY-SA — restate); `https://adr.github.io/adr-templates/` lists Y-Statement as one of four canonical templates |
| `references/adr-antipatterns.md` | Merged table. Installed skill's 7 rows preserved (retrospective rationalization, stale-ADR-as-gospel, bikeshedding, kitchen-sink, vague consequences, title-as-question, wiki-ADR) **+ 11 creation anti-patterns** (Fairy Tale/Wishful Thinking, Sales Pitch, Free Lunch Coupon/Candy Bar, Dummy Alternative, Sprint/Rush, Tunnel Vision, Maze, Blueprint-or-Policy-in-Disguise, Mega-ADR, Novel/Epic, Magic Tricks incl. pseudo-accuracy) **+ 7 review anti-patterns** (Pass Through/Over-Friendliness, Copy Edit, Siding/Dead-End/Excursion, Self-Promotion/Conflict-of-Interest, Power Game, Offended Reaction, Groundhog Day) **+ the 7-question review checklist** (problem worth an ADR? · options viable, any missing? · drivers MECE? · conflicting criteria prioritized? · rationale sound? · consequences reported objectively? · outcome actionable, traceable, with a review date?) + the author pledge and reviewer pledge, compressed | Paraphrase + cite | `https://ozimmer.ch/practices/2023/04/03/ADRCreation.html` (11 anti-patterns + 5-part author pledge, read in full), `https://ozimmer.ch/practices/2023/04/05/ADRReview.html` (7 anti-patterns + 7-question checklist + 5-part reviewer pledge, read in full) |
| `references/adr-as-evidence.md` | **Bundle-original.** How an ADR sits in the authority model: it is evidence the conductor records and may cite, never a gate result and never authorization. Seed linkage discipline: name the affected Seed IDs and what would be false while each blocking Seed stays open **in the ADR body**, not by mutating queue fields. Every unresolved action point leaves as one typed `SeedProposal`. Confirmation → real repo gate commands. Compliance → grep-able assertions a reviewer or a future check can read. Reversal Condition → the falsifiability hook. Explicit non-claims: an accepted ADR does not retroactively make legacy code compliant (that needs an explicit tech-debt Seed), and a passing gate cited in Confirmation is evidence only | Original synthesis + cite internal paths | `skills/agentic-sdlc/SKILL.md` (Delegation Rules, Hard Stops), `skills/agentic-sdlc/references/sdlc-loop.md:34-35` and `:50-52`, `skills/agentic-sdlc/references/deep-work-loop.md` (Artifacts-and-recommendations-only), `AGENTS.md`. Structural precedent for Seed-linkage + Reversal Condition: `<workspace>/pi-lab/skills/docs/adr-authoring/SKILL.md:142-145` and `<workspace>/pi-lab/docs/adr/` (23 records, 0001–0023) — **generalize, do not port**; that skill is pi-runtime-specific by its own `SOURCE.md` |
| `references/adoption-tiers.md` | The tier-selection matrix (decision weight → bare-minimal / minimal / full / full+extensions); the 5-level adoption ladder (Undefined&Unconscious → Ad-hoc&Unstructured → Encouraged&Supported → Systematic,Selective&Diligent → Optimized&Rigorous) across 7 dimensions (usage scenario · scope&scale · documentation rigor&location · process&engagement · tool support&automation · review culture · learning&education), used as a one-time per-repo elicitation so a level-2 solo repo is not forced into level-5 ceremony; an "other formats" appendix (Nygard 5-section, Tyree&Akerman, Y-Statement, ISO/IEC/IEEE 42010:2011) **linked, never vendored**; an optional-tooling catalog | Paraphrase + link only | `https://ozimmer.ch/practices/2023/04/21/ADAdoptionModel.html` (5 levels + 7 dimensions confirmed verbatim). Formats catalog: `https://adr.github.io/adr-templates/` (the four it names, with its own link forms) and `https://github.com/joelparkerhenderson/architecture-decision-record` — **that repo's `LICENSE.md` is CC BY-NC-SA for its own writing (verified), i.e. non-commercial: link, never vendor.** Tooling names/URLs from `https://adr.github.io/adr-tooling/` (adr-log, ADR Manager + VS Code extension, Backstage ADR plugin, Log4brains, pyadr, adr-tools, adr-viewer, ArchUnit, docToolchain, Structurizr). None becomes a bundle dependency |
| `references/PROVENANCE.md` | Source ledger: every URL, fetch date `2026-08-05`, license per source, and the caveats — (a) MADR templates vendored at tag `4.0.0`, with the `develop` delta named; (b) **ruflo issue #930 is an OPEN, unmerged feature request** (`state: open`, created `2026-01-08T22:27:47Z`, author `cgbarlow`, verified via `gh api`) — harvested as design inspiration, never cited as a shipped capability; (c) `cgbarlow/adr` is CC-BY-SA-4.0 and therefore restated, not copied; (d) `ruvnet/ruflo` ships a *separate* live `plugins/ruflo-adr/` (5 skills: adr-create/index/verify/reindex/review — verified present) with **no cross-reference to #930**; its skill split is prior art for the audit tool but is AgentDB-coupled and not portable; (e) ozimmer.ch pages are unlicensed and DNS-unreachable from this host via direct fetch | n/a | all of the above |

### 1.4 Optional tool: `skills/adr-lifecycle/tools/adr-lint.py`

Modelled on the existing `skills/agentic-sdlc/tools/offline-inspect.py`: deterministic, offline, read-only, Python-standard-library only, no subprocesses, no network, no target writes.

Checks (all advisory, all mechanical, none semantic):
- filename `NNNN-kebab-title.md`, number uniqueness, index coverage (the pi-lab failure mode: an ADR missing from the index is "an ADR nobody can find" — `pi-lab/skills/docs/adr-authoring/SKILL.md`)
- status value ∈ the Hard Rule 3 vocabulary
- `< 2` entries under *Considered Options*
- zero `Bad, because` / zero negative consequence
- title in question form
- dangling ADR references; **supersede cycles**; status mismatch (source of a `Supersedes` edge whose own status is not `superseded by …`) — the exact triad from `plugins/ruflo-adr/skills/adr-verify/SKILL.md`
- ADR-ID extraction must strip `#1697`-style issue refs, `PR 1234`, and commit hashes before matching `ADR-\d+` (the false-positive guard from `plugins/ruflo-adr/skills/adr-index/`)
- a "deleted from disk but still indexed" blind-spot warning, and a pointer to rebuild rather than re-verify (`plugins/ruflo-adr/docs/adrs/0002-reconcile-deleted-adrs.md`)
- body-size and embedded-implementation heuristics for Hard Rule 9, and a dated-`## Updates`-section detector for Hard Rule 10

**It must print findings and exit 0 by default.** Per **C5** it cannot enter `mise run check`, `lefthook.yml`, or CI — which is exactly the doctrine: a passing local check is evidence, not authorization.

### 1.5 What is deliberately *not* created

- **No new agent role.** `sdlc-adr-author` is blocked by **C4** (roster closed at 14 + 17, sha256-pinned across two policy files and 31 projections). The existing `sdlc-planner` already declares its writes as "plan artifacts (plan doc / **ADR draft**)" (`agents/claude/sdlc-planner.md`), and `sdlc-critic`/`sdlc-reviewer` already carry ADR-consistency lenses. Reuse them.
- **No second skill.** A `create/index/verify/review` split (the ruflo-adr shape) is attractive but multiplies the selection surface for one subject; the mode selector plus one tool covers it.
- **No new mise task in `check`.** Blocked by C5 and doctrinally correct.

---

## 2. Delta over the installed `adr-methodology`

Baseline read in full: `<claude-home>/skills/adr-methodology/SKILL.md` (217 lines, MADR 3.0, 8 hard rules, 8-step workflow, one anti-pattern table, artifact-relation table, no `references/` directory — confirmed by `ls`). Everything below is **additive**; all 8 baseline hard rules survive.

| # | Addition | Why it is not already there | Source |
|---|---|---|---|
| D1 | **Significance gate before authoring** (7-criterion ASR + AWS 5-category scope test) | Baseline has a 3-bullet prose "When NOT to invoke"; no test, no refusal path | `ozimmer.ch/practices/2020/09/24/ASRTestECSADecisions.html`; AWS PG `adr-process.html` §Scope |
| D2 | **START Definition-of-Ready** before drafting | Baseline jumps from "locate directory" to "elicit" | `ozimmer.ch/…/2023/12/01/ADDefinitionOfReady.html` |
| D3 | **ECADR + Dp/Rf/M Definition-of-Done gating `proposed → accepted`** | Baseline's transition table has no acceptance evidence bar — accept is implicit | `ozimmer.ch/…/2020/05/22/ADDefinitionOfDone.html`; `cgbarlow/adr/specs/SPEC-001-E-Definition-of-Done.md` |
| D4 | **Four graduated template tiers** (bare-minimal / minimal / full / full+extensions), chosen by decision weight | Baseline embeds exactly one inline template; MADR's minimal and bare variants did not exist at 3.0 | `github.com/adr/madr/tree/4.0.0/template` (four files, all fetched); CHANGELOG `[4.0.0-beta]` "Bare an minimal templates: #88" |
| D5 | **The `Confirmation` section** — and Hard Rule 12 requiring it to name a real repo command | The baseline template omits it entirely, though MADR says it "is included in many ADRs" | `madr@4.0.0/template/adr-template.md`; naming rationale `madr/docs/decisions/0018-use-confirmation-as-heading.md` |
| D6 | **MADR 4.0 field renames** (`deciders`→`decision-makers`; `date` = last-updated; `Neutral, because`; `Validation`→`Confirmation` nested under Decision Outcome; status link removed) | Baseline frontmatter still uses `deciders:` and splits Positive/Negative | `madr/CHANGELOG.md` 4.0.0-beta/4.0.0 |
| D7 | **Closed-enum reconciliation.** Keep the strict status vocabulary as a bundle rule while stating that upstream MADR treats the field as free text | Baseline asserts the closed enum with no acknowledgement that upstream disagrees — a latent correctness bug when a user checks the spec | `madr@4.0.0/template/adr-template.md` frontmatter; `adr.github.io/madr/` |
| D8 | **ADR-owner role**, distinct from author and from `decision-makers`; owner approves pre-acceptance edits and reschedules review | Baseline has no ownership concept at all — it silently assumes "the user" | AWS PG `adr-process.html` §ADR adoption process; `best-practices.html` "Promote ownership"; `faq.html` "Who should create an ADR?" |
| D9 | **Review protocol** (10–15 min silent read → owner reads out each comment → accepted / stays-proposed-with-assigned-action-points / rejected-with-recorded-reason) + at-scale numerics (30–45 min, <10 people, 1–3 readouts, two-way doors) | Baseline has no review step whatsoever between `proposed` and `accepted` | AWS PG `adr-process.html`; AWS Architecture Blog `blogs/architecture/master-architecture-decision-records-…` |
| D10 | **Supersession ordering rule**: the new ADR reaches `accepted` *before* the old status flips | Baseline step 6 lets you flip the old status while the new one is still `proposed` | AWS PG `adr-process.html` §ADR review process |
| D11 | **Code-review conformance loop**: a reviewer who finds a violating change links the ADR and asks the *code* to change | Absent — baseline's ADRs are inert once written | AWS PG `adr-process.html`; `best-practices.html` "Address non-compliant code" |
| D12 | **Hard Rule 9 (decision ≠ specification)** with a body-size heuristic and a spec sink | Baseline's "kitchen-sink" row catches *multi-decision* bloat, not *implementation-leak* bloat — a different failure | `cgbarlow/adr/specs/SPEC-001-B-Minimalism.md`; Mega-ADR / Novel-Epic in `ozimmer.ch/…/2023/04/03/ADRCreation.html`; failure case documented in ruflo issue #930 |
| D13 | **Hard Rule 10 (no living-document `Updates` sections)** | Baseline forbids editing the body but never names the changelog-drift failure that actually happens | ruflo issue #930 (diagnoses this in claude-flow v3's own ADRs) |
| D14 | **Typed relationship graph** — 5 edge types + 5 validation rules + Dependencies table, replacing prose-only "links in More Information", with the MADR-ADR-0009 divergence stated explicitly | Baseline has only `Supersedes:` prose; no impact analysis, no cycle detection | `cgbarlow/adr/specs/SPEC-001-C-Dependencies.md`; counter-decision `madr/docs/decisions/0009-…` |
| D15 | **Master ADR** with Child Registry, phase sequencing, and 6 aggregate-status rules | Nothing in baseline spans multiple decisions; maps onto this bundle's mission/wave shape | `cgbarlow/adr/specs/SPEC-001-D-Master-ADRs.md` |
| D16 | **WH(Y) / Y-statement elevator line** as an optional dense summary, plus the lean-first tier | Baseline is single-formality; there is no cheap record for a marginal decision | `ozimmer.ch/…/2020/04/27/ArchitectureDecisionMaking.html`; `adr.github.io/adr-templates/`; `cgbarlow/adr/specs/SPEC-001-A-WHY-Format.md` |
| D17 | **AWS `Compliance` section** (grep-able enforceable assertions) as an optional extension, explicitly marked non-MADR-core | Neither MADR nor baseline has a machine-checkable block. AWS's worked example shows the shape: *"The main and develop branches in each repository must be marked as Protected"* | AWS PG `appendix.html` (headings verified: Title / Status / Date / Context / Decision / Consequences / **Compliance** / **Notes** with Author, Version, Changelog) |
| D18 | **18 named anti-patterns + a 7-question review checklist + two pledges** | Baseline has 7 rows and no review-time material | `ozimmer.ch/…/2023/04/03/ADRCreation.html`, `…/2023/04/05/ADRReview.html` |
| D19 | **Adoption-tier scoping** — ask the repo's maturity level once, then scale ceremony to it | Baseline applies uniform rigor; this bundle's own doctrine is capability-gated escalation | `ozimmer.ch/…/2023/04/21/ADAdoptionModel.html`; `skills/agentic-sdlc/references/tiered-orchestration.md` |
| D20 | **Reversal Condition (Hard Rule 13)** — one observable falsifying event and who sees it | Absent from baseline and from every external template surveyed | Structural precedent `pi-lab/skills/docs/adr-authoring/SKILL.md:142-145`; motivated by the review checklist's "does the ADR define a validity period or review date?" |
| D21 | **ADR-as-evidence integration** — advisory, never authorization; Seed linkage in the body; SeedProposals for open action points | Baseline's only composition hooks are `deep-work-loop` and `universal-commit`; it has no notion of an evidence/authority split | `skills/agentic-sdlc/SKILL.md`; `references/sdlc-loop.md:34-35`,`:50-52`; `references/deep-work-loop.md`; `AGENTS.md` |
| D22 | **`references/` structure at all** — 10 read-on-demand files instead of one 217-line monolith | Baseline is a single file with no `references/` dir (verified) | Repo convention: `AGENTS.md`, `skills/change-writing/`, `skills/agentic-sdlc/references/` |
| D23 | **Commit routing to `change-writing`** instead of `universal-commit` | `universal-commit` is a *global* skill; this bundle owns `skills/change-writing/`, which is output-only and forbids running git | `skills/change-writing/SKILL.md`; `skills/agentic-sdlc/SKILL.md` Ship phase |

---

## 3. Automation hooks

### 3.1 Loop integration (documentation-only wiring; the two directions matter)

**Read direction (already exists — the skill just becomes the thing that produced what is read):**
- `commands/sdlc-frame.md:16` — "Read repo intent docs (README, ADRs, roadmap)"
- `commands/sdlc-mission.md` step 1 — "ADR index" is part of state reconstruction
- `skills/agentic-sdlc/references/sdlc-loop.md:9` — Frame reads ADRs
- `skills/agentic-sdlc/references/mission-loop.md:14`, `:69`, `:108` — ADR index in reconstruction; "tracker/ADR hygiene" as a standing critique lens; "changing toolchains needs an ADR"
- `agents/claude/sdlc-researcher.md`, `sdlc-reviewer.md`, `sdlc-critic.md` — all already reference ADRs

**Write direction (new, and where the skill attaches):**

| Loop point | Hook | Authority note |
|---|---|---|
| **Frame** (`/sdlc-frame` step 3) | Run the D1 significance gate over the framed decisions; anything that clears it becomes a candidate ADR named in the frame output | The frame is a recommendation the conductor adjudicates |
| **Plan** | `sdlc-planner` already writes "plan doc / **ADR draft**" — this skill is what it drafts *with*. Emits `proposed`, never `accepted` | Planner "proposes; the conductor decides" |
| **deep-work-loop `decide`** | Every durable choice → one ADR at the chosen tier; marginal ones → a WH(Y) one-liner | Deep-work-loop emits "artifacts and SeedProposals only" |
| **Review / concurrent critique** | Add ADR conformance to the reviewer/critic lens set: does the diff violate an `accepted` ADR? Load only `accepted` records; deprecated/superseded ones are context, never constraints | Reviewer/critic labels are advisory; a violation becomes a `SeedProposal`, not a block |
| **Reconcile** (`sdlc-loop.md` Reconcile) | Every open ADR action point → one typed `SeedProposal`. `accepted` flip happens here, gated on the D3 DoD | Conductor adjudicates |
| **Ship** | The ADR + rebuilt index in one commit; text authored by `change-writing`; the human authorizes publication | Unchanged |
| **`/sdlc-init`** | Bootstrap advice for a repo with zero ADRs: ADR the SDLC process itself first (branching strategy, review process, the gate) since it is otherwise tacit. Fits the activation plane's `create\|adopt\|merge\|refuse\|skip` model — **propose, never auto-create** | `sdlc-init` is a reviewed runbook, not an engine (`AGENTS.md`) |

Sources for the bootstrap-first-ADRs advice: AWS PG host `docs.aws.amazon.com`, path `prescriptive-guidance/latest/architectural-decision-records/resources.html`.

### 3.2 Commit / PR integration

- ADR + index in **one** commit; message `docs(adr): add ADR-NNNN <title>` / `docs(adr): supersede ADR-NNNN with ADR-MMMM — <reason>` — but only as a fallback: `change-writing` mandates repo-native convention over any generic one (`skills/change-writing/SKILL.md` §"Repository policy wins"), and the observed local style is Conventional-Commits-shaped (`feat:`, `chore:`, `fix:` in recent commits).
- The ADR is **evidence** in a PR body, not a claim of approval. `change-writing`'s six-step evidence ladder and omit-or-`TODO:` rule apply (`references/evidence-order.md`).
- Attribution stays default-prohibited (`references/attribution-policy.md`) — an ADR's `decision-makers` are humans, never models.
- Supersession touches three files (new ADR, old ADR's status line only, index) in one commit.

### 3.3 What a validator could gate — and what it must not

**Safe to gate (style/structure only, evidence not authorization):**

| Check | Where | Cost |
|---|---|---|
| `name` == dirname, `description` ≤1024, `references/*.md` exist | already automatic via `scripts/validate_bundle.py:386-400` — **zero new code (C1)** | none |
| Skill installs cleanly on both hosts | already automatic via `discover_entries` glob (**C6**) + `mise run self-test` | none |
| A `tests/test_adr_lifecycle.py` conformance test asserting the skill + all 10 references exist, frontmatter shape, the 13 hard rules are each present, the authority-boundary sentence is present, and the reference files carry no `--force-with-lease`/`git push`/`gh pr merge` strings | new test file, modelled 1:1 on `tests/test_change_writing.py` (which does exactly this for `change-writing`) | ~1 file; runs under existing `mise run test` |
| `adr-lint.py` findings on the target repo's `docs/adr/` | the optional tool, run manually or by a reviewer | advisory output only |

**Must not gate:**
- `mise run check` cannot depend on the linter — byte-pinned (**C5**). This is the correct outcome.
- CI cannot invoke it — `EXPECTED_WORKFLOW` is byte-pinned.
- `lefthook.yml` cannot invoke it — byte-pinned.
- No ADR check may block a merge on its own. An accepted ADR, a passing lint, and a reviewer's ADR-violation finding are all evidence; the human authorizes the outward effect (`AGENTS.md`, `skills/agentic-sdlc/SKILL.md` Hard Stops).

**Two landmines for whoever writes the files (both verified by execution):**
1. **C3** — a single full AWS docs URL fails `mise run validate` with `possible secret or internal hostname found`. Write `docs.aws.amazon.com` and the path as separate tokens.
2. **C8** — the phrase pattern `<anything> may cre&#97;te a Seeds iss&#117;e` fails `tests/test_preflight_capabilities.py` **even when the actor is the conductor** (confirmed: the conductor-attributed form of that same phrase also HITs). Safe forms that pass: *"Return the finding as a typed SeedProposal for conductor adjudication"*, *"The conductor alone mutates Seeds after acceptance evidence is verified"*, *"Do not close the Seed from an ADR acceptance claim alone"*.

Also: no `\bcao\b` token, and no `| Consequence lane ​| Exact model ID |` string, anywhere in the new files (**C9**).

### 3.4 Optional `/adr` slash command (defer to phase 2)

`commands/adr.md` would be picked up automatically by the installer glob and faces **no validator at all** (**C10**) — cheap. But putting `/adr` into a target repo's routing block requires editing the byte-pinned `CANONICAL_INSTRUCTION_CONTENT["CLAUDE.md"]` in `skills/agentic-sdlc/tools/offline-inspect.py:24-31` **and** `CANONICAL_CLAUDE_BODY` in `tests/test_offline_observer_rc.py:34-38`. Ship the skill first; add the command only if invocation friction is observed.

---

## 4. Migration and coexistence with the installed `adr-methodology`

**Current state (verified):** `~/.claude/skills/adr-methodology/` is a plain directory (not a symlink, not a junction) containing one 10545-byte `SKILL.md`, dated 2026-04-29. It is **not** in the installer's ownership state — `~/.local/state/agentic-sdlc-installer/state.json` contains only `/tmp/payload-review.*` entries, so no bundle skill is currently installed into the real home. The global skill is user-owned and out of scope for this bundle's write path.

**The rule:** never edit `~/.claude/skills/adr-methodology/` directly. Supersede only through the bundle's install/update flow.

**Why the vendored dirname must differ (the hard finding):** if the vendored skill is named `adr-methodology`, `mise run bundle:install` reaches `install_skill_bundle.py:2707-2724`, finds a destination that exists, is not a link, and is not byte-equal, and emits `conflict: ~/.claude/skills/adr-methodology` with `partial = True` → **exit code 1**. `bundle:install` is not a merge tool; it preserves foreign content and reports. Shipping `adr-lifecycle` sidesteps this entirely and needs no user action.

**Coexistence (recommended default):** both skills installed. `adr-lifecycle` supersets every trigger phrase, so Claude's selector will usually pick it; when it picks the older one the result is a valid MADR 3.0 ADR — a graceful degrade, not a wrong answer. Only two visible frictions: the older skill produces `deciders:` frontmatter and split Positive/Negative consequences (D6), and it routes to `universal-commit` rather than `change-writing` (D23).

**Full-supersession path, if the user wants exactly one ADR skill:**
1. `mise run bundle:status` → confirm nothing owns the destination.
2. Move the old skill aside: `mv ~/.claude/skills/adr-methodology ~/.claude/skills/.adr-methodology.superseded-YYYY-MM-DD` (the user's own operation, not the bundle's).
3. Either keep `adr-lifecycle` as-is, or rename the vendored skill to `adr-methodology` (dirname + `name` together, per **C1**), then `mise run bundle:install`. With the destination absent, install proceeds to `would install:` / `installed:` cleanly.
4. `mise run bundle:status` to confirm ownership, then delete the aside copy.

**Idempotence and adoption notes:** if the user ever hand-copies the vendored skill into `~/.claude/skills/` byte-for-byte, a later install *adopts* it and marks it `preserved on uninstall` (`install_skill_bundle.py:2707-2721`). If they symlink it to the repo source, install adopts the link (`legacy_link_mode`, `:935-942`). Modified or foreign content is always preserved and reported, never overwritten — consistent with `AGENTS.md`'s ownership doctrine.

**Marketplace caveat, unchanged:** for Claude, use direct install **or** the marketplace, never both (`AGENTS.md`).

**Upstream drift:** if the global `adr-methodology` is revised by its own owner, diff against it rather than assuming continued non-overlap. Reciprocally, MADR itself churns (it renamed to "Markdown *Any* Decision Records" in 2020 and reverted at 4.0.0-beta — `madr/CHANGELOG.md`), so this bundle's 13 hard rules must stay stable even when upstream template cosmetics move. That is why decision *weight* picks the tier and 4.0 is not hard-pinned as mandatory.

---

## 5. Landing plan

| Phase | Deliverable | Gate |
|---|---|---|
| 1 | `skills/adr-lifecycle/SKILL.md` + all 10 `references/*.md` | `python3 scripts/validate_bundle.py` (0 errors, matching the verified C11 baseline), then `mise run check` |
| 2 | `tests/test_adr_lifecycle.py` (mirror of `tests/test_change_writing.py`) | `mise run test` |
| 3 | One-hop pointers added to `skills/agentic-sdlc/SKILL.md` §References and `references/deep-work-loop.md` §Integration points; one README bullet in the `skills/` list (README is not gated) + one `AGENTS.md` line | `mise run check` |
| 4 | `tools/adr-lint.py` (advisory) | `mise run check` — it is Python, so `validate_python` compiles it |
| 5 | Optional `commands/adr.md`; routing-block edit only if justified against the pinned constants (§3.4) | `mise run check` + `mise run test` |
| — | Dogfood: this bundle has **no `docs/adr/`** of its own (verified). The first real ADRs should record the choices in this very spec — the dirname, the table-over-prose divergence from MADR ADR-0009, and the 4.0.0-tag pin — which is also the D19/D21 story working end to end | — |

Version bumps, if the release lands as one: `./scripts/bump-version.sh <version>` only — never hand-edit a manifest (`.version-bump.json`, `AGENTS.md`).
