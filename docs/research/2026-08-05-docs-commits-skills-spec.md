# Implementation spec: three documentation/communication skills for `agentic-sdlc`

Status: design-complete, read-only pass. No files written. Every rule below is either quoted from a fetched primary source or verified by execution in this environment (commands and outputs cited inline).

---

## 0. Verification log (what is fact vs. what is inherited claim)

| Claim | How verified | Result |
|---|---|---|
| CC v1.0.0 has 16 numbered rules; license CC BY 3.0 | WebFetch `https://www.conventionalcommits.org/en/v1.0.0/` | Confirmed, rules 1–16 quoted verbatim; footer says "Creative Commons - CC BY 3.0" |
| `@commitlint/config-conventional` defaults | WebFetch of `@commitlint/config-conventional/src/index.ts` (master) | **Harvest was wrong**: `header-max-length` is **100**, not 72. Full table in §2.4 |
| commitlint usable without install | `npx -y -p @commitlint/cli@20 -p @commitlint/config-conventional@20 commitlint < msg` | Works. `@commitlint/cli@20.5.3`. `feat: add thing.` → exit 1 `subject-full-stop`; `feat(scope): add thing` → exit 0; `merge: land …` → exit 1 `type-enum`. `--edit <file>` **fails outside a git root**: `TypeError: Could not find git root` |
| ASD-STE100 shape + license | WebFetch `asd-ste100.org/about_STE.html`, `asd-ste100.org/faq.html`, Wikipedia | 53 rules / 9 sections; ~900 approved + ~1200 unapproved words; "© Copyright 2026 STEMG - All Rights Reserved"; **"Simplified Technical English, ASD-STE100, is a Copyright and a Trademark of ASD, Brussels, Belgium. All rights reserved. European Union Trade Mark No. 017966390."**; ASD/STEMG "DO NOT endorse or certify" products declaring themselves "fully compliant" and such providers have "no authorization to use the ASD logo, copyright or trademark" |
| oh-my-mermaid license | `gh api repos/oh-my-mermaid/oh-my-mermaid` + raw LICENSE | MIT, "Copyright (c) 2025 oh-my-mermaid", 2125 stars |
| Mermaid parse traps | Executed `npx -y @mermaid-js/mermaid-cli@11.16.0 -i x.mmd -o x.svg` per case (Node v26.6.0) | 9 confirmed, 3 **refuted** — table in §4.5 |
| `mmdc` pinnability here | `mise registry \| rg mermaid` | Only `mermaid-ascii` exists in the registry. `@mermaid-js/mermaid-cli` is npm-backend only |
| Cross-skill `references/` path in a SKILL.md breaks the validator | Copied repo to `/tmp/vtest`, appended `` `../change-writing/references/commit.md` `` to `skills/stacked-prs/SKILL.md`, ran validator | `ERROR: stacked-prs: missing references/commit.md` → **hard constraint**, see §1.2 |
| This repo's real commit convention | `git log --pretty=%s -300` (89 subjects) + scripted commitlint simulation | 37/89 (42%) would fail `config-conventional`; last 30: 8/30 (27%). Offenders: 30 no-type-prefix, `merge:`×4, `prereqs:`, `G1:`, `G2:`, 2 type-case. Zero subjects >100 chars; 21 >72 |
| Claude trailer is live in-tree | `git log -12 --pretty='%h\|%s\|%(trailers…)'` | All 12 recent commits carry `Co-Authored-By: Claude <noreply@anthropic.com>` — which `skills/change-writing/references/attribution-policy.md` default-denies. Flagged in §5.2 |

---

## 1. Repo constraints that bind all three skills

### 1.1 What the validator actually enforces per skill

`scripts/validate_bundle.py:386-401` (`validate_skills`) — auto-discovers `skills/*/SKILL.md`, so **no manifest, installer, or task edit is needed to add a skill**. It enforces exactly four things:

1. frontmatter `name` == directory name;
2. `description` present;
3. `len(description) <= 1024`;
4. every regex match of `\breferences/[A-Za-z0-9._-]+\.md` **anywhere in the SKILL.md body** resolves to a real file under that skill's own directory.

### 1.2 Trap: no cross-skill `references/…md` path may appear in a `SKILL.md`

The reference check is a bare regex over the whole file and resolves relative to the skill's own dir. `` `../change-writing/references/commit.md` `` matches `references/commit.md` and then fails. Verified above.

**Rules for all three new skills:**
- In `SKILL.md`, cite sibling skills **only** as `../change-writing/SKILL.md` (no `references/` segment).
- Deep cross-skill paths are legal inside `references/*.md` files (the check only scans `SKILL.md`); `skills/change-writing/references/pull-request.md:9` already does this and validation passes.

### 1.3 Trap: use `description: >-`, not a plain multi-line scalar

`metadata_value` (`scripts/validate_bundle.py:365-383`) returns only the **first line** unless the value is one of `{"|", ">", "|-", ">-"}` or `[|>][+-]?[1-9]`. `change-writing/SKILL.md` uses a plain multi-line scalar, so its 1024-char cap is currently only checked against line 1 while the agent sees the whole folded string.

Use `description: >-` with indented continuation lines and **no blank lines inside the block** (a blank line makes YAML emit `\n` while the validator joins with `" "`, producing a benign but avoidable mismatch). `>-` gives byte-accurate cap enforcement and exact YAML-folded semantics.

Frontmatter keys: `name` + `description` **only**. Do not add `version:`/`date:`/`author:` — `.version-bump.json` does not target `SKILL.md` files, so an in-skill version is unmanaged drift (`repo-toolchain-gates` and `cmux-event-bus-messaging` carry that drift today; do not copy it).

### 1.4 Trap: the toolchain and hook graph are frozen — no tool pins, no new hooks

- `validate_mise` asserts `config["tools"] == {uv, lefthook, node, bun, npm:@os-eco/seeds-cli}` **exactly** (`:1081-1089`) and `sha256(mise.lock) == MISE_LOCK_SHA256` (`:1124`). `tests/test_gate_graph.py:33-70` re-freezes `LOCKED_TOOLCHAIN` with per-platform sets.
  → **Adding `[tools."npm:@mermaid-js/mermaid-cli"]` requires regenerating the lock, updating `MISE_LOCK_SHA256`, and editing `LOCKED_TOOLCHAIN` + `TOOLCHAIN_MUTATIONS` in the same commit.** Out of scope; `mmdc` stays advisory `npx`.
- `validate_gate_graph:1171-1185` byte-compares `lefthook.yml` against a literal string. `tests/test_gate_graph.py:81` mutates `run: mise run self-test` → `run: mise run check` and requires failure.
  → **A `commit-msg:` hook cannot be added to this repo's `lefthook.yml`** without editing the frozen literal in `validate_bundle.py` **and** `tests/test_gate_graph.py`.
- `tests/test_gate_graph.py::test_no_second_task_runner` additionally asserts **every** `run:` line in `lefthook.yml`/CI starts with `mise `. A raw `run: npx commitlint --edit {1}` would fail even if the byte-freeze were relaxed.
- `[tasks.check]` is frozen to exactly `["validate","test","self-test"]` (`:1108-1113`, plus `test_check_depends_unchanged_unless_secrets_added`).

**Consequence, stated as doctrine in the skills themselves:** commitlint/`mmdc`/prose-lint wiring is a **recipe for target repos**, mirroring the existing honest posture of `skills/repo-toolchain-gates/SKILL.md` ("advisory / opt-in, not wired — and honestly so", with `test_betterleaks_wiring_matches_doctrine` enforcing that the claim matches reality). Copy that posture verbatim in shape, and note per `AGENTS.md`: hooks are "best-effort convenience, not release authority".

### 1.5 Model-routing calibration: do not touch

`skills/model-tier-rightsizing/references/model-routing-calibration.md:218-226` already reserves rows `M0a`–`M7` for a 30-skill Mermaid family + router, and `tests/test_model_tier_rightsizing.py:149-157` asserts those **exact row names and tiers**. The single `mermaid-diagrams` skill specified here is a *subset consumer* of the `M1`/`M4` volume-tier rows. **Make zero edits to the calibration table or that test** — an edit would break a frozen contract to describe work that isn't happening.

---

## 2. Skill 1 — `skills/conventional-commits/`

### 2.1 Dirname
`conventional-commits` (matches the standard's own name; the term is not trademark-restricted; CC BY 3.0 permits reuse with attribution).

### 2.2 Description (860 chars, verified)

```yaml
---
name: conventional-commits
description: >-
  Use when a commit message must conform to Conventional Commits v1.0.0, or when a candidate
  message must be judged against it: picking the type and scope, deciding whether the change is
  breaking, writing the `!` marker versus a `BREAKING CHANGE:` footer, formatting footer tokens,
  mapping type to a SemVer bump, or predicting whether commitlint `config-conventional` would
  reject the subject. Also use when a repo asks to wire commitlint into a lefthook `commit-msg`
  hook. This skill teaches the spec and its tooling divergences and returns text or a verdict
  only; it never stages, commits, amends, pushes, or rebases. Author the actual message with
  `../change-writing/SKILL.md`, whose repo-native-convention-wins and attribution rules both
  still apply: Conventional Commits applies only where it is already the repository's convention
  or the declared fallback.
---
```

Trigger tuning rationale: fires on *conformance judgment* verbs ("does this pass", "is this conventional", "what type", "is this breaking", "commitlint", "commit-msg hook"), **not** on bare "write a commit message" — that must keep routing to `change-writing`, per `tests/test_change_writing.py::test_repo_policy_wins_over_conventional_commits`.

### 2.3 `SKILL.md` outline with operative rules inlined

```
# Conventional Commits v1.0.0 conformance

## What this skill is not          (~6 lines)
  - Not the message author. Load ../change-writing/SKILL.md for the words, the evidence
    ladder, and attribution.
  - Not an actor: never runs git add/commit/push/rebase or gh pr create/edit/merge.
  - Not a mandate. A detected repo-native convention wins. This skill applies when CC IS the
    repo convention, or when change-writing's evidence ladder has reached its
    generic-convention rung (its last resort).

## Decide first: does CC apply here?   (3-question gate)
  1. Does history/policy already use `type(scope): subject`? → conform to the LOCAL dialect
     (including local types), not to commitlint's enum.
  2. Does the repo run a CC linter (commitlint config, hook, release-please/semantic-release)?
     → the linter's rules, not the spec, are the operative constraint. Read §Tooling divergence.
  3. Neither? → CC is a fallback only; say so when proposing it.

## The grammar (single normative block, quoted verbatim, attributed CC BY 3.0)
  <type>[optional scope][!]: <description>
  <BLANK LINE>
  [optional body]
  <BLANK LINE>
  [optional footer(s)]

## The 16 rules, applied            (each rule + the mistake it prevents)
## Type selection decision table    (diff shape → type; ties → split the commit)
## Scope selection rules
## Breaking change: `!` vs footer   (the rule-13 subtlety)
## Footer token grammar             (the 3 mistakes agents make)
## SemVer mapping
## Self-check before proposing text  (7-item checklist)
## Tooling divergence: spec vs commitlint  → references/commitlint-rules.md
## Wiring commitlint in a target repo      → references/hook-wiring.md
## Edge cases (FAQ-derived)                → references/faq-decisions.md
## References
```

**Operative rules that MUST be inlined in `SKILL.md`** (an agent must be able to apply CC without opening a reference):

*The 16 rules, condensed to applicable form (quote-and-apply; attribute "Conventional Commits v1.0.0, CC BY 3.0"):*
1. Type prefix is a noun, then optional scope, optional `!`, then a **required** `: ` (colon **and** space).
2. `feat` MUST be used when the commit adds a new feature.
3. `fix` MUST be used when the commit is a bug fix.
4. Scope is a noun in parentheses naming a codebase section: `fix(parser):`.
5. Description immediately follows `: `.
6. Body begins **one blank line after** the description.
7. Body is free-form, any number of newline-separated paragraphs.
8. Footers come one blank line after the body: `Token: value` or `Token #value`.
9. Footer tokens use `-` for whitespace (`Reviewed-by`, `Acked-by`) — this is what separates footers from a multi-paragraph body.
10. A footer value may contain spaces and newlines; parsing stops at the next valid token/separator pair.
11. Breaking changes MUST appear in the type/scope prefix **or** in a footer.
12. As a footer: uppercase `BREAKING CHANGE`, then `: `, then description.
13. In the prefix: `!` immediately before the `:`.
14. Types other than `feat`/`fix` MAY be used (`docs: update ref docs`).
15. Units of information are case-insensitive to implementors **except** `BREAKING CHANGE`, which MUST be uppercase.
16. `BREAKING-CHANGE` is synonymous with `BREAKING CHANGE` as a footer token.

*The five failures this skill exists to stop* (state each as a rule with the wrong/right pair):
- Missing blank line before body or footers → parsers read the body as the description, or a footer as body prose.
- `Reviewed by: x` (space in token) instead of `Reviewed-by: x` → not a footer (rule 9).
- `breaking change:` lowercased → not a breaking change (rule 15).
- `feat!: …` where the **description does not state the break** → with `!` the description *is* the breaking-change text; if it does not describe the break, add the footer too. Canonical spec example: `feat!: drop support for Node 6` + `BREAKING CHANGE: use JavaScript features not available in Node 6.`
- Trailing period on the subject → spec-legal, commitlint-illegal (`subject-full-stop`). Verified: `feat: add thing.` → exit 1.

*Type-selection table (behavioral, not vibes):*

| Diff shape | Type |
|---|---|
| New user-reachable capability, new public API/CLI/flag | `feat` (MINOR) |
| Corrects wrong behavior a user could hit | `fix` (PATCH) |
| Docs/comments/README only | `docs` |
| Behavior-preserving restructure | `refactor` |
| Tests only | `test` |
| Measurable perf change, no behavior change | `perf` |
| Formatting/whitespace only | `style` |
| Build system, deps, packaging | `build` |
| CI config/workflows | `ci` |
| Reverts an earlier commit | `revert` (see FAQ: the spec deliberately leaves revert semantics to tooling authors) |
| None of the above / repo chores | `chore` |
| **Two of the above apply** | Split the commit. FAQ: "Go back and make multiple commits whenever possible." |

*SemVer mapping (exact, from the spec FAQ):* `fix` → PATCH, `feat` → MINOR, `BREAKING CHANGE` in any type → MAJOR.

*Self-check (7 items, all mechanically checkable without tooling):* type in the repo's accepted set · lowercase type · scope is a parenthesised noun or absent · `: ` present · description non-empty, imperative, no trailing period · blank line before body and before footers · footer tokens hyphenated except `BREAKING CHANGE`.

### 2.4 `references/` manifest

| File | Vendored / linked | Contents | License posture |
|---|---|---|---|
| `references/commitlint-rules.md` | **Rewritten**, values quoted | The 12 `config-conventional` defaults **as verified from source**: `type-enum` error/always `[build, chore, ci, docs, feat, fix, perf, refactor, revert, style, test]`; `type-case` error/always `lower-case`; `type-empty` error/never; `subject-empty` error/never; `subject-full-stop` error/never `"."`; `subject-case` error/**never** `[sentence-case, start-case, pascal-case, upper-case]`; `header-max-length` error/always **100**; `header-trim` error/always; `body-max-line-length` 100; `footer-max-line-length` 100; `body-leading-blank` **warning**; `footer-leading-blank` **warning**. Plus the divergence table: the spec imposes **no** type enum (rule 14 permits any noun) and **no** length limit; severity `0/1/2` = off/warn/error; a warning does not fail the run | Rule *names and numbers* are factual config values; MIT (commitlint) — no code copied |
| `references/hook-wiring.md` | Original | Target-repo recipe (see §2.5). Must open with the honesty paragraph: this bundle's own `lefthook.yml` is byte-frozen by `validate_bundle.py::validate_gate_graph` and `tests/test_gate_graph.py`, so **no `commit-msg` hook is wired here**; hooks are best-effort convenience, bypassable via `--no-verify`/`LEFTHOOK=0`, and never release authority | n/a |
| `references/faq-decisions.md` | Quoted + attributed | The six FAQ answers verified above, each turned into a decision: initial dev phase ("proceed as if you've already released the product") · multi-type → split · SemVer mapping · wrong type: `git rebase -i` **pre-release**, post-release it just means "that commit will be missed by tools" · contributors need not comply ("If you use a squash based workflow … lead maintainers can clean up the commit messages as they're merged") · reverts left to tooling authors | CC BY 3.0 — include a one-line attribution footer: *"Quoted rule and FAQ text: Conventional Commits v1.0.0, https://www.conventionalcommits.org/en/v1.0.0/, licensed CC BY 3.0."* |

Do **not** add a `references/spec.md` wholesale copy. The 16 rules belong inline in `SKILL.md` (an agent applying CC needs them in the first read, not a second hop).

### 2.5 Tool backing

**Self-check with no install (primary path, verified):**
```bash
printf '%s\n' "$MSG" | npx -y -p @commitlint/cli@20 -p @commitlint/config-conventional@20 commitlint
# exit 0 = clean, exit 1 = violations printed with rule names
```
Record the two verified caveats: `commitlint --edit <file>` **requires a git root** (`TypeError: Could not find git root`), and stdin mode is the portable form for judging a candidate message that is not yet a commit.

**Target-repo `commit-msg` wiring (for `references/hook-wiring.md`, not for this repo):**
```yaml
# lefthook.yml — target repo only
commit-msg:
  commands:
    commitlint:
      run: npx --no-install commitlint --edit {1}
```
`{1}` is lefthook's first-git-hook-argument template — "shorthand for the 1-st git hook argument" — which for `commit-msg` is the commit-message file. Verified against `evilmartians/lefthook/docs/configuration/run.md`, whose own example is `commit-msg: commands: multiple-sign-off: run: 'test $(grep -c "^Signed-off-by: " {1}) -lt 2'`. lefthook is already `[tools] lefthook = "2.1.10"` here, so the *manager* is pinned even where the linter is not.

**Local `type-enum` extension the recipe must teach** (backed by this repo's own history): a repo whose history contains `merge:` must extend the enum or the hook rejects its own convention:
```js
export default {
  extends: ["@commitlint/config-conventional"],
  rules: { "type-enum": [2, "always", ["build","chore","ci","docs","feat","fix","perf","refactor","revert","style","test","merge"]] },
};
```
Out of scope, name explicitly: commitizen (interactive wizard — an agent needs the rules, not a prompt), release-please/semantic-release (motivation only, never invoked by the skill).

### 2.6 Coexistence

- **`change-writing` (in-repo, load-bearing).** `references/commit.md:13-23` states verbatim: "Conventional Commits is only a fallback when no repo-native convention is detectable — never a mandate layered on top of an established local style", and `references/evidence-order.md` puts "Generic convention" at rung **6 of 6**. `tests/test_change_writing.py::test_repo_policy_wins_over_conventional_commits` enforces this. The new skill **must not** re-litigate it; its "What this skill is not" section restates the subordination. Prior research reached the same verdict (`docs/research/2026-08-05-pi-lab-harvest-memo.md:108`: "Not a new skill"). This spec knowingly reverses that to a *narrow* skill and must say so in one line: the reversal is justified only because conformance judgment (types, breaking-change markers, footer grammar, SemVer, linter prediction) is a distinct concern from message authorship, and the reversal costs `change-writing` no authority.
- **Optional two-line delta into `change-writing/references/commit.md`** (recommended, honors the memo): add a pointer — "When Conventional Commits is the operative convention, `../conventional-commits/SKILL.md` owns spec conformance." A `references/`-free pointer is safe there (reference files are not scanned), but the pointer text should still avoid a deep path for consistency.
- **This repo's own history.** 42% of 89 subjects (27% of the last 30) would fail `config-conventional`, on `merge:`, `prereqs:`, `G1:`/`G2:`, and 30 no-prefix subjects. The skill must state this as the worked example of why *repo-native wins*: this repo's dialect is CC-**shaped** with a local `merge:` type, and CC-conformance advice that rejected `merge:` here would be wrong.
- **Claude Code's trailer rule — flag, do not resolve.** The active `Co-Authored-By: Claude <noreply@anthropic.com>` instruction and all 12 recent commits conflict with `change-writing/references/attribution-policy.md` (which default-denies exactly that token) and with the `ATTRIBUTION_DENY` regexes in `tests/test_change_writing.py:33-40`. The new skill's only statement: `Co-Authored-By` is a **grammatically valid** CC footer (rules 8–9); whether it is **permitted** is decided solely by `../change-writing/SKILL.md`'s attribution policy. Adding any opinion here forks the normative source.
- **Global/plugin skills** `commit-commands:commit`, `commit-commands:commit-push-pr`, `universal-commit` all *perform* commits. One line: those act; this one judges text and never acts.

### 2.7 Gate work

New `tests/test_conventional_commits.py`, mirroring `tests/test_change_writing.py`:
- frontmatter `name == "conventional-commits"`, description ≤1024 **measured through the same `_frontmatter`/`_metadata_value` helpers**;
- all 16 rule numbers present in `SKILL.md`; `BREAKING CHANGE` appears uppercase; the `!`-before-`:` rule present;
- subordination assertions: `SKILL.md` matches `/fallback/i`, contains `../change-writing/SKILL.md`, and matches `/repo.*(win|beat|override)/is`;
- authority assertions copied from `test_authority_boundary_declared`: contains `git add`, `git commit`, `git push`, `gh pr create/edit/merge`, and does **not** match `\b(run|execute)\s+`?git\s+(add|commit|push)`;
- **no cross-skill `references/` path in `SKILL.md`**: `assertNotRegex(text, r"\.\./[a-z-]+/references/")` — cheap guard against the §1.2 trap for all three skills;
- commitlint table fidelity: `header-max-length` row says `100`, and `assertNotIn("header-max-length", …72…)`;
- honesty: `SKILL.md`/`hook-wiring.md` must not claim a wired hook in *this* repo — assert `lefthook.yml` contains no `commit-msg` while the skill matches `/not wired|advisory|target repo/i` (the `test_betterleaks_wiring_matches_doctrine` pattern).

---

## 3. Skill 2 — `skills/technical-writing-clarity/` (better dirname than `asd-ste100`)

### 3.1 Dirname: recommend `technical-writing-clarity`

Reject `asd-ste100`. Two independent reasons:

1. **Trademark/endorsement.** "ASD-STE100" is a registered EU trademark (No. 017966390) and copyright of ASD, Brussels. The FAQ specifically calls out providers that "declare to be ASD-STE100 'fully compliant'" as unendorsed and unauthorized to use the trademark. A skill *directory named after the trademark* is the highest-risk form: it reads as a licensed/endorsed implementation, and `name == dirname` propagates that string into every host's skill list.
2. **Trigger fit.** Agents write docs; nobody asks for "STE100". A dirname that names the *job* triggers at the right moments; the standard is credited in body text and description.

Alternates if a different flavor is wanted: `doc-clarity-rules`, `plain-technical-english`. Avoid `simplified-technical-english` (the phrase itself is trademarked in this context).

### 3.2 Description (878 chars, verified)

```yaml
---
name: technical-writing-clarity
description: >-
  Use when writing or revising prose a reader must act on: README, CONTRIBUTING, ADR and
  design-doc bodies, runbooks and procedures, error and log messages, release notes, PR bodies,
  and SKILL.md instruction text. Also use when asked to simplify, tighten, de-jargon, or
  disambiguate documentation, or when a reviewer calls a doc unclear or wordy. Applies the
  publicly documented ASD-STE100 Simplified Technical English rule shapes as a countable
  self-audit: 20-word procedural and 25-word descriptive sentence caps, one instruction per
  sentence, six sentences per paragraph, multi-word nouns of at most three words, the approved
  verb-form set, active voice by default, no dropped subjects or articles, and one term per
  concept. It restates public rule shapes only, reproduces no part of ASD's copyrighted
  dictionary, and never claims STE compliance, conformance, or certification.
---
```

### 3.3 `SKILL.md` outline with operative rules inlined

```
# Technical writing clarity (public STE rule shapes)

## Provenance and limits (first section, non-negotiable)
  - ASD-STE100 is a two-part standard: Part 1 = 53 writing rules in 9 sections
    (Words; Multi-word nouns; Verbs; Sentences; Procedural writing; Descriptive writing;
    Safety instructions; Punctuation and word count; Writing practices). Part 2 = a controlled
    dictionary of ~900 approved words and ~1200 not-approved words with alternatives.
    Current: Issue 9, released 2025-01-15 by ASD/STEMG.
  - This skill restates PUBLICLY DOCUMENTED RULE SHAPES from asd-ste100.org's public pages and
    Wikipedia's article. It does NOT reproduce the dictionary, does not reproduce rule text, and
    is NOT the standard. ASD-STE100 is a copyright and trademark of ASD (EUTM 017966390).
    ASD/STEMG endorse and certify nothing. Never write "STE compliant", "STE certified",
    "ASD-STE100 conformant", or use the ASD logo. Say "checked against public STE rule shapes".
  - Two rule classes, and they are not equal:
      COUNTABLE   — mechanically checkable, this skill's real product.
      JUDGMENT    — needs the licensed dictionary or a human. Flag, never fake.
  - Sentence-length figures (20/25) are cited from public secondary summaries, not verified
    against the Issue 9 body text. Treat as the widely published shape, not a quoted rule.

## First moves: classify the text type
  Procedural (steps a reader performs) | Descriptive (explanation) | Safety/warning |
  Message string (error/log/CLI) — the caps and mood differ per type.

## The countable rules  ← the operative table, inlined
## The judgment rules   ← what a checker cannot decide
## Apply while writing  (per-sentence loop, not a post-hoc pass)
## Self-audit pass      (5 mechanical passes with what to count)
## SDLC artifact profiles → references/artifact-profiles.md
## Rewrite patterns      → references/rewrite-patterns.md
## Optional lint backing → references/lint-tools.md
## Coexistence
## References
```

**Countable rules table (inline, verbatim-quotable from Wikipedia, CC BY-SA 4.0 with attribution):**

| Rule | Limit | How to count | Text type |
|---|---|---|---|
| Sentence length | "no more than 20 words in instructions (procedures) and 25 words in descriptive texts" | words per terminal punctuation | both |
| Paragraph length | "Do not write more than six sentences in each paragraph" + "Write only one topic per paragraph" | sentences per paragraph | descriptive |
| Multi-word nouns | "Do not write multi-word nouns that have more than three words" | consecutive nouns; break the 4th with a preposition — *runway light connection resistance* → *resistance of the runway light connection* | both |
| One instruction per sentence | one imperative per sentence; split compound steps | count imperatives | procedural |
| Verb forms | permitted: infinitive, imperative, simple present, simple past, simple future, past participle **as adjective only**; no complex auxiliary chains | scan for auxiliary stacks (*will have been …*) | both |
| `-ing` | only as a technical noun or a noun modifier, never as a present-participle verb | scan `\w+ing\b` | both |
| Voice | "Use the active voice. In descriptive writing, one should use the passive voice only when the agent is unknown." | scan `be + VERB-ed` | procedural = always active |
| Completeness | "Do not omit parts of the sentence (e.g. verb, subject, article) to make the text shorter" | check subject + verb + article present | both |
| Vertical lists | "Use vertical lists for complex text" | any sentence with ≥3 coordinated items | both |
| One term per concept | one word, one meaning, one part of speech: pick *start* and never alternate with *begin/commence/initiate* for style | build a term list for the doc, grep each variant | both |
| Safety instructions | command first, explanation second | first clause is the imperative | safety |

**Judgment rules (flag, never fabricate):** whether a specific word is in the ~900-word approved dictionary (the dictionary is licensed — the skill cannot know); whether a domain term qualifies as an STE "technical noun"/"technical verb" (STE's own extension mechanism for project jargon — the correct answer here is "declare a project term list", not "guess"); whether the chosen technical name is the *right* one. Adopt `clean-writing-lint`'s own honest framing: a checker cannot tell you whether a noun is the right technical name.

**The apply-while-writing loop (this is what makes it a skill, not a summary):** before emitting each paragraph — pick the text type → write one instruction per sentence in the imperative → count words against the type's cap → count nouns in each compound → check for `be + VERB-ed` and `-ing` verbs → confirm subject/verb/article present. After the draft, run the five self-audit passes (sentence lengths; paragraph sentence counts; noun clusters; verb-form/voice scan; term-consistency grep) and report counts, not vibes.

### 3.4 `references/` manifest

| File | Vendored / linked | Contents | License posture |
|---|---|---|---|
| `references/artifact-profiles.md` | Original | Per-artifact profile: README/CONTRIBUTING · ADR body (pairs with the global `adr-methodology` skill, which owns MADR structure) · runbook/procedure · PR body (pairs with `../change-writing/SKILL.md`, which owns content and evidence) · error/log message (imperative + cause + next action, ≤1 sentence) · `SKILL.md` instruction text (this bundle's own dogfooding target) | n/a |
| `references/rewrite-patterns.md` | Original examples | Before/after pairs, one per countable rule, all authored here — **no examples copied from any STE source** | Original prose only |
| `references/lint-tools.md` | Linked, not vendored | `clean-writing-lint` / `cwlint` (npm, **MIT**, latest `0.1.0`, bin `cwlint`; "Lint prose for AI slop. Checks the machine-checkable subset of Simplified Technical English…") for sentence length / passive voice / banned words, masking code fences first; `HendrikLuedemann/S1000D-STE100-Tool-Suite` (**MIT**, Python/PowerShell — builds word lists **from the licensed Issue 9 PDF at run time on the user's own copy**, which is why it is linked and never vendored); prior art to read, not copy: `JuanMarchetto/doc-standards-skill` (**MIT**), `NikolaRHristov/STE-Code` (**MIT**, Issue 9 adapted to code-domain docs). Note `mvillere/clean-writing-system` has **no repo LICENSE (NOASSERTION)** even though the published npm package declares MIT → consume the package, copy nothing from the repo. Posture: **no linter is pinned or wired**; all invocations are advisory `npx`/`uvx` at use time, per §1.4 | Each entry carries its verified SPDX id |

**Do not create** `references/dictionary.md`, an approved-word list, or a not-approved→approved mapping table. That is the licensed half of the standard.

### 3.5 Tool backing

Advisory only, no pin, no hook in this repo:
```bash
npx -y clean-writing-lint@0.1.0 <paths> --max-score <n>   # exit 1 above threshold; CI-gateable in a TARGET repo
```
The primary product is the **manual countable self-audit**, which needs no tooling and no network. Per the harvest memo, pi-lab's real TS checker is not being ported; start with the checklist.

### 3.6 Coexistence

- **Reverses a recorded verdict — say so.** `docs/research/2026-08-05-pi-lab-harvest-memo.md:86,112` says "skip, unless demanded … Narrow ASD-STE100 aerospace/defense fit, poor match for agentic-sdlc's general SDLC audience." The reversal is justified in one line in `SKILL.md`: this skill ships the *general countable-clarity* subset for any SDLC doc, and explicitly does **not** ship the aerospace framing, the `ste100.config.json` convention, or the dictionary that made the port narrow.
- **Zero in-repo overlap** (verified: no doc-style skill exists). Adjacent, non-overlapping: `change-writing` (commit/PR/squash *content and evidence*, not sentence mechanics) · global `adr-methodology` (MADR structure, not prose) · global `document-generate`/`document-release` (what to write and when to publish, not clarity). One line each.
- **Dogfooding note worth stating:** these rules apply to this bundle's own `SKILL.md` and `references/*.md` prose. Do not retro-edit existing skills in the landing commit — that is a separate, reviewable change.

### 3.7 Gate work

New `tests/test_technical_writing_clarity.py`:
- frontmatter/name/description-cap + the §1.2 no-cross-skill-`references/` guard;
- **license guard (the important one):** `SKILL.md` + all references must NOT match `/(?i)(STE|ASD-STE100)[- ]?(compliant|certified|conformant)/`, must NOT contain an approved/not-approved word-list table (assert absence of any `references/dictionary*.md` file and of a `not.?approved.*→` mapping pattern), and MUST contain the trademark/copyright acknowledgment plus "does not reproduce" language;
- every countable rule's number is present (`20`, `25`, `six`/`6`, `three`/`3`) and each countable row names *how to count*;
- the countable-vs-judgment split is declared, and the 20/25 figures carry the "public secondary summaries, not verified against Issue 9" hedge;
- the advisory-tooling honesty guard: no linter appears in `mise.toml`/`lefthook.yml` while the skill claims one is wired.

---

## 4. Skill 3 — `skills/mermaid-diagrams/`

### 4.1 Dirname
`mermaid-diagrams` (as requested; distinct from the user's global `diagram` skill).

### 4.2 Description (896 chars, verified)

```yaml
---
name: mermaid-diagrams
description: >-
  Use when an SDLC artifact needs a Mermaid diagram, or when an existing `.mmd` file or
  ```mermaid block must be scoped, corrected, or split: architecture and dependency views in
  ADRs, request and data flow in design docs, state machines, sequence views in PR bodies and
  reviews, ER views for schema changes. Teaches one perspective per diagram, the
  leaf-versus-group recursion that sets depth, mandatory why-labelled edges, node-count caps,
  diagram-type selection, and the parse traps agents actually hit: lowercase `end`, reserved
  node IDs (`class`, `style`, `graph`, `subgraph`), `o`/`x`-prefixed IDs silently becoming
  circle and cross edges, unquoted labels with parentheses or commas, and unbalanced sequence
  activation inside `alt`/`else`. Authoring and correctness only; rendering, export, and
  Excalidraw conversion stay with the host's own diagram skill. No renderer is pinned in this
  repo.
---
```

### 4.3 `SKILL.md` outline

```
# Mermaid diagram authoring for SDLC artifacts

## Scope boundary (first)
  Authoring + syntax correctness + scope discipline. NOT rendering/export/conversion — the
  host's own `diagram` skill owns the render-and-deliver pipeline. If it is loaded, this skill
  supplies step 1 (the source) and hands off.

## Step 1 — Pick ONE perspective          ← the stolen idea, credited
## Step 2 — Pick the diagram type          (selection table)
## Step 3 — Set depth: leaf or group       (the recursion rule)
## Step 4 — Author the source              (the 7 authoring rules)
## Step 5 — Avoid the parse traps          (verified table, inline)
## Step 6 — Verify by rendering            (advisory, unpinned)
## Where the source lives                   (.mmd in git vs inline fence)
## References
```

**Step 1 — perspective catalog (the single best idea in oh-my-mermaid; MIT, credit it).** One diagram answers one question. Name the perspective before drawing:

`overall-architecture` (what exists and how pieces relate) · `request-lifecycle` (how a request enters and is handled end to end) · `data-flow` (where data comes from, transforms, lands) · `dependency-map` (what depends on what, what is shared) · `external-integrations` (what the system connects to and why) · `state-transitions` (how state changes and what triggers it) · `route-page-map` (page structure and navigation) · `command-surface` (command hierarchy and dispatch) · `extension-points` (extension architecture and registry) · `pipeline` (stage topology) · `orchestration` (publisher/subscriber/broker topology) · `storage` (DB, cache, queue, object store topology).

Rule: **if you cannot name the perspective, you are drawing a picture, not answering a question.** Two perspectives in one diagram → two diagrams.

**Step 2 — diagram-type selection table:**

| Question | Type |
|---|---|
| What are the parts and how do they connect? | `flowchart` / `graph` |
| Who calls whom, in what order, over time? | `sequenceDiagram` |
| What states exist and what triggers transitions? | `stateDiagram-v2` |
| What entities and relations does the schema hold? | `erDiagram` |
| What types and inheritance exist? | `classDiagram` |
| Sequence of work over calendar time? | `gantt` |
| Branch/merge topology of a change? | `gitGraph` |
| Idea decomposition with no edges to justify? | `mindmap` |
| System context / container boundaries? | `C4Context`/`C4Container` — **experimental, syntax can change**; prefer a labelled flowchart with subgraphs for anything durable |
| Cloud/CI topology? | `architecture-beta` (v11.1+) — 5 built-in icons only; treat as unstable |

**Step 3 — the leaf-or-group recursion (oh-my-mermaid's decision rule, restated):** for each node ask *does this contain distinct internal components worth their own diagram?* **Yes** → it is a group: write a child diagram and recurse. **No** (single file, trivial wrapper, external system) → it is a leaf: stop, and write its description. Group element IDs are kebab-case and **match the child directory or section name** (`main-process`, `data-store`), so the diagram tree mirrors the filesystem and stays navigable. **Every node gets a description; never ship an undocumented node.**

**Step 4 — the 7 authoring rules:**
1. **Every edge carries a meaningful label**: `A -->|"why this connection exists"| B`. An unlabelled edge asserts a relationship without saying what it is.
2. **Two-line node labels**: `element["Display Name\nrelative/file/path"]` — every node is traceable to a source location.
3. `graph LR` by default; `graph TD` for hierarchies. Direction keywords: `TB`/`TD`, `BT`, `LR`, `RL`.
4. **Node cap ≈ 15.** Past that, split by perspective or push detail into a child diagram.
5. Semantic `classDef` palette, consistent across a family — entry / external / store / concern. Use `classDef`, **not external CSS**: per Mermaid's docs, "Applying styles to Mermaid nodes via external CSS does not work reliably" because Mermaid's internal styles win on specificity. Pair dark fills with light strokes so the diagram survives both GitHub themes.
6. Cross-diagram links by name/`@ref` rather than duplicating a subtree in two diagrams.
7. `.mmd` files committed to git are the diffable source of truth; inline ```` ```mermaid ```` fences are for prose that must render in place.

### 4.4 `references/` manifest

| File | Vendored / linked | Contents | License posture |
|---|---|---|---|
| `references/perspectives.md` | **Rewritten from MIT source** | The 12 perspectives expanded: when each applies, what its nodes and edges represent, its stop condition, worked node/edge sets | oh-my-mermaid is **MIT (c) 2025 oh-my-mermaid** (verified). MIT permits copying with notice; still **re-derive the wording** and carry an attribution line: *"Perspective catalog and leaf/group recursion adapted from oh-my-mermaid (MIT, https://github.com/oh-my-mermaid/oh-my-mermaid)."* Claim no affiliation. Vendor no code |
| `references/syntax-traps.md` | Original, execution-verified | The §4.5 table with the exact reproducer, observed exit code/output, and the fix per trap; a dated verification line: *"Verified against @mermaid-js/mermaid-cli 11.16.0 on 2026-08-05."* | Original |
| `references/diagram-types.md` | Original + doc facts | Per-type minimal skeleton, direction/shape/edge syntax, and stability caveats (C4 experimental; `architecture-beta` new) | Mermaid docs are freely citable; paraphrase, do not bulk-copy |
| `references/render-verify.md` | Linked | Advisory `npx` render check, `mmdc` flag subset (`-i`, `-o`, `-t default\|dark\|forest\|neutral`, `-b`, `-c`, `-w/-H/-s`, `-q`, `-p`), the `base`-theme-only-via-config/frontmatter caveat, `PUPPETEER_EXECUTABLE_PATH` for reusing a system Chromium; the pin refusal with its reason (§4.6) | mermaid-cli MIT |

### 4.5 Verified parse traps — table for `references/syntax-traps.md`

Executed here with `@mermaid-js/mermaid-cli@11.16.0`. **Only ship rows marked CONFIRMED as facts.**

| Trap | Reproducer | Observed | Fix |
|---|---|---|---|
| lowercase `end` as node ID | `graph LR` / `a[Start] --> end[Finish]` | **exit 1** — CONFIRMED | Capitalize (`End`, `END`) or wrap. In sequence diagrams, enclose with `()`, `""`, `{}`, `[]` |
| reserved word `class` as node ID | `class[Class] --> B` | **exit 1** — CONFIRMED | Rename/suffix (`class-node`) |
| reserved word `style` as node ID | `style[S] --> B` | **exit 1** — CONFIRMED | Rename |
| reserved word `graph` as node ID | `graph[G] --> B` | **exit 1** — CONFIRMED | Rename |
| reserved word `subgraph` as node ID | `subgraph[S] --> B` | **exit 1** — CONFIRMED | Rename |
| `o`-prefixed ID after `---` | `graph LR` / `A---oB` | **exit 0, silently wrong** — node label renders as `B`, edge gets `circleEnd` marker — CONFIRMED | Space (`A --- oB` → label `oB`, no circle marker — CONFIRMED) or capitalize (`OB` — CONFIRMED clean) |
| `x`-prefixed ID after `---` | `A---xB` | **exit 0, silently wrong** — label `B`, `crossEnd` marker — CONFIRMED | Space or capitalize |
| unquoted label with `(` and `,` | `A[Label with (parens), and commas] --> B` | **exit 1** — CONFIRMED; quoted form `A["…"]` → exit 0 | Always quote labels containing `(`, `)`, `,`, `;`, `:` |
| unbalanced sequence activation in both `alt` branches | `A->>+B: go` / `alt` … `B-->>-A: ok` / `else` … `B-->>-A: nope` / `end` | **exit 1**, `Error: Trying to inactivate an inactive participant (B)` — CONFIRMED | Deactivate **after** the block closes, not inside each branch |
| misspelled frontmatter config key | `--- config: flowchart: diagramPaddingx: abc ---` | **exit 0** — silently ignored, no diagnostic — CONFIRMED | Never assume config took effect; verify visually |
| ~~`click` as node ID~~ | `click[C] --> B` | **exit 0 — REFUTED**, do not ship | — |
| ~~`default` as node ID~~ | `default[D] --> B` | **exit 0 — REFUTED** | — |
| ~~edge label beginning with `o`~~ | `A -->\|ok\| B` | **exit 0 — REFUTED** in 11.16.0; the harvest claim does not reproduce | — |
| ~~`%%{init}%%` inside a `%%` comment~~ | `%% %{init: {"theme":"dark"}}%%` | **exit 0 — REFUTED** | — |

Also confirmed clean (safe to teach): `---\ntitle: …\n---` frontmatter, `config:` frontmatter, nested-free `subgraph … end` blocks, and the v11.3+ `A@{ shape: rect, label: "…" }` form.

### 4.6 Tool backing

```bash
npx -y @mermaid-js/mermaid-cli@11.16.0 -i diagram.mmd -o /tmp/diagram.svg   # exit 1 = parse error
```
Two honest statements the skill must carry:
- **Not pinned, with the reason.** `@mermaid-js/mermaid-cli` is absent from the mise registry (verified: `mise registry | rg mermaid` returns only `mermaid-ascii`), and an `npm:`-backend `[tools]` entry would require regenerating the SHA-frozen `mise.lock` plus the frozen `LOCKED_TOOLCHAIN` table (§1.4). Advisory `npx` at use time, matching `repo-toolchain-gates`' betterleaks Option B. Never fabricate a version.
- **Exit code ≠ good diagram.** A clean parse still permits spaghetti dagre routing and silently-ignored config. Look at the rendered output, or hand off to whichever render skill is loaded. The `o`/`x` and misspelled-key traps are exactly the class of bug that passes the parser and fails the reader.

### 4.7 Coexistence

- **User's global `diagram` skill (gstack).** It already owns English→mermaid→triplet (`.mmd` + `.excalidraw` + SVG/PNG) via an offline browser bundle, and already states flowchart preferences (`graph LR` pipelines, `graph TD` hierarchies, 5–15 nodes) and its flowchart-only Excalidraw limitation. **Split:** `mermaid-diagrams` owns perspective/depth/edge-semantics/type-choice/trap-avoidance (its step "Author the diagram"); `diagram` owns render/convert/deliver. The description's closing sentence encodes this so both can be installed without selection-budget conflict. Global `dataviz` is charts/statistical viz — no overlap; one line.
- **Harvest memo caution honored.** `docs/research/2026-08-05-pi-lab-harvest-memo.md:83,113-114` flagged mermaid content as low-priority and told us to check the global skills first, and `:126` refused a `[tools]` pin. Both are satisfied and cited in the skill.
- **Routing calibration.** Rows `M0a`–`M7` in `skills/model-tier-rightsizing/references/model-routing-calibration.md` pre-reserve a 30-skill family; this is one skill and is a **subset consumer** of the `M1`/`M4` volume-tier rows. **No calibration or test edit** (§1.5) — state that in the skill so a later reader does not "fix" the apparent gap.
- **In-repo hooks.** Add a one-line pointer from `skills/agentic-sdlc/references/sdlc-loop.md` (or the ADR-producing path) — "diagrams in ADRs/design docs: `../../mermaid-diagrams/SKILL.md`" — but keep any deep path **out of** `SKILL.md` files (§1.2).

### 4.8 Gate work

New `tests/test_mermaid_diagrams.py`:
- frontmatter/name/description-cap + the no-cross-skill-`references/` guard;
- all 12 perspective names present in `references/perspectives.md`; the leaf-vs-group rule present in `SKILL.md`;
- the mandatory-edge-label rule and node cap present;
- **anti-regression on refuted claims**: assert `syntax-traps.md` does **not** teach `click`/`default` as reserved IDs, and does **not** claim an `o`-initial edge label or a directive-inside-comment breaks parsing;
- attribution guard: `perspectives.md` contains the oh-my-mermaid MIT attribution line and no "affiliated/official" claim;
- pin-honesty guard: `mise.toml` contains no `mermaid` while `render-verify.md` matches `/advisory|not pinned|npx/i`;
- optional, guarded by `shutil.which("npx")` and `unittest.skipUnless` (offline-safe, matching `test_gate_graph.py`'s `skipUnless(shutil.which("mise"))` idiom): a fixture pair under `tests/fixtures/mermaid-diagrams/{bad,good}/` where each documented trap fixture fails and its fix passes. **Keep this skipped-by-default and never on the `check` path** — `mise run check` must stay offline.

---

## 5. Cross-cutting

### 5.1 Coexistence matrix

| New skill | Defers to | On what | Must never |
|---|---|---|---|
| `conventional-commits` | `change-writing` | message text, evidence ladder, attribution, repo-native-wins | Present CC as a mandate; author the final message; run any git/gh command |
| `conventional-commits` | `repo-toolchain-gates` | mise/lefthook/gate doctrine, worktree trust facts | Re-teach hook mechanics or claim a wired gate |
| `technical-writing-clarity` | `change-writing` | commit/PR *content* and evidence | Rewrite an evidence claim into prettier prose that asserts more than the evidence |
| `technical-writing-clarity` | global `adr-methodology` | MADR structure, option count | Impose sentence caps on quoted material, code, or CLI transcripts |
| `mermaid-diagrams` | global `diagram` | render, export, Excalidraw | Ship a second render pipeline or pin a renderer |
| all three | `agentic-sdlc` flagship | authority: no push/publish/merge/deploy | Grant or imply outward-effect authority |

### 5.2 License register (all verified this session)

| Source | License | Use here |
|---|---|---|
| conventionalcommits.org v1.0.0 spec + FAQ | **CC BY 3.0** | Quote rules and FAQ verbatim **with attribution line**. Safe |
| commitlint / `config-conventional` | MIT | Restate rule *names and default values* (facts). Copy no code |
| lefthook docs | project docs | Paraphrase; `{1}` template is a factual API |
| oh-my-mermaid `omm-scan` | **MIT (c) 2025 oh-my-mermaid** | Ideas + attributed adaptation. Re-derive wording, vendor no code, claim no affiliation |
| mermaid.js docs / mermaid-cli | MIT project | Paraphrase syntax facts; quote the two short gotcha sentences with attribution |
| **ASD-STE100 (Issue 9) spec + dictionary** | **🚫 BLOCKED** — copyright + EU trademark 017966390, ASD Brussels; free-of-charge but request-gated; ASD/STEMG endorse/certify nothing | **Fallback (mandatory):** restate only publicly documented rule *shapes* from `asd-ste100.org` public pages + Wikipedia (CC BY-SA 4.0, attributed). **No dictionary. No rule text. No compliance/certification/conformance claim. No logo or trademark use. Dirname is not the trademark.** Countable-vs-judgment split makes the gap explicit instead of faking it |
| Wikipedia "Simplified Technical English" | CC BY-SA 4.0 | Quotable with attribution; note share-alike applies to *substantial verbatim* reuse — prefer short quotes plus original tables |
| `clean-writing-lint` (npm) | MIT, v0.1.0 | Link and invoke; vendor nothing |
| `mvillere/clean-writing-system` (repo) | **NOASSERTION** | Do not copy from the repo; consume only the MIT-declared npm package |
| `S1000D-STE100-Tool-Suite`, `STE-Code`, `doc-standards-skill` | MIT (all verified) | Cite as prior art / optional tooling; vendor nothing in this pass |

### 5.3 Landing plan

Three commits, each independently gated (`mise run check`), each honoring this repo's own dialect (`feat: …`, ≤72-char subject preferred, `Co-Authored-By` per the active repo instruction, which `change-writing`'s policy independently governs):

1. `feat: add conventional-commits conformance skill` — `skills/conventional-commits/{SKILL.md,references/{commitlint-rules,hook-wiring,faq-decisions}.md}` + `tests/test_conventional_commits.py` + the two-line pointer in `skills/change-writing/references/commit.md`.
2. `feat: add technical-writing-clarity skill` — `skills/technical-writing-clarity/{SKILL.md,references/{artifact-profiles,rewrite-patterns,lint-tools}.md}` + `tests/test_technical_writing_clarity.py`.
3. `feat: add mermaid-diagrams authoring skill` — `skills/mermaid-diagrams/{SKILL.md,references/{perspectives,syntax-traps,diagram-types,render-verify}.md}` + `tests/test_mermaid_diagrams.py` (+ optional skipped fixtures).

Then one docs commit adding the three bullets to `README.md` § Contents (no test asserts the list, so it is safe but should not be forgotten) — and, if the flagship should route to them, a single line each in `skills/agentic-sdlc/SKILL.md` § References using `../<skill>/SKILL.md` form only.

**No changes to:** `mise.toml`, `mise.lock`, `lefthook.yml`, `.github/workflows/validate.yml`, `.version-bump.json`, any `*plugin.json`/`marketplace.json`, `scripts/install_skill_bundle.py`, `scripts/validate_bundle.py`, or `skills/model-tier-rightsizing/**`. Skill discovery is glob-based (`validate_bundle.py:387`, `install_skill_bundle.py:770`), so three directories and three tests are the whole diff.

### 5.4 Pre-flight checklist for the implementer

1. `description: >-`, no blank lines in the block, ≤1024 chars measured with `validate_bundle.frontmatter`/`metadata_value` — not with `len()` on the YAML source.
2. `grep -n '\.\./[a-z-]+/references/' skills/*/SKILL.md` must return nothing.
3. Every `references/x.md` named in a `SKILL.md` must exist before running the validator.
4. `python3 scripts/validate_bundle.py --root .` then `mise run check`.
5. Confirm no new skill claims a wired hook, a pinned linter/renderer, STE compliance, or authority to run a git/gh mutation.
