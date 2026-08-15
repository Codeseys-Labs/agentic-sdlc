# SimpleEnglish content-gap analysis

## Question and gated decision

**Question.** At the current upstream revision, what does `AminBlg/SimpleEnglish`
add beyond this repository's core clarity profile, and does that value justify an
external companion, a first-party adaptation, or no product role?

**Decision gated.** Choose one of three product positions:

1. keep SimpleEnglish only as an optional external companion;
2. re-express a specifically bounded set of ideas in one existing first-party
   reference, with an exact donor record; or
3. give SimpleEnglish no product role.

**Artifact.** `docs/plans/claude-code-first-harness/research/simpleenglish-content-gap-analysis.md`

## Recommendation

Choose **option 2**, but harvest only five named ideas into the existing
`skills/change-writing/references/technical-writing-clarity.md`; do not add a
SimpleEnglish skill, output style, prompt, rule-number catalog, vocabulary table,
or installer path.

The five ideas are:

1. put a prerequisite or condition before the action that depends on it;
2. expand contractions and make referents explicit, including a noun after an
   otherwise ambiguous demonstrative;
3. express actions with direct verbs instead of action nouns;
4. audit semicolons and Latin abbreviations as ambiguity/localization hazards,
   without making either an unconditional correctness failure; and
5. when reviewing prose, pair each counted violation with its location and a
   meaning-preserving candidate rewrite.

This is the smallest option that captures the real gap. The incumbent reference
already owns sentence mechanics, loads on demand, and covers most of the upstream
structural rules. Extending it creates no new selection row. The five additions
strengthen its procedure and audit without importing the upstream package's strict
dictionary claims or always-on behavior. [inferred from the exhaustive comparison
below and the local incumbent-first rule at
`skills/agentic-sdlc/references/skill-authoring.md:47-73,107-127,226-230`]

Any implementation of option 2 must add the SimpleEnglish donor and the upstream
origin claim to `NOTICE` in the same change, reproduce the required MIT grant there,
and repeat the provenance statement in the adapted reference. This report does not
make those product edits. [verified:
`skills/agentic-sdlc/references/skill-authoring.md:129-151`;
`NOTICE:324-343`]

**Confidence: high** that the overlap, contradictions, package costs, and licence
consequences are complete for the authorized sources; **medium-high** that the five
ideas merit the donor burden. The upstream benchmarks do not compare SimpleEnglish
against this repository's already-strong clarity profile, so they cannot measure
incremental quality here. [verified: the benchmark baseline receives only the task,
while the skill condition receives the complete upstream skill, in
[the Pi method](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/evals/results/pi-2026-07-31/RESULTS.md#L14-L22)]

## Source boundary and evidence labels

Research date: **2026-08-14**. Upstream `HEAD` resolved to default branch `main` at
commit [`59bf6702197a5aadc96d197ea17f290d8d50dcd3`](https://github.com/AminBlg/SimpleEnglish/commit/59bf6702197a5aadc96d197ea17f290d8d50dcd3).
The local comparison was made against clean tracked copies at repository `HEAD`
`24c4b1113789260d6d73ddb133430b4ae8af329d`.

Only these sources were used:

- the official `AminBlg/SimpleEnglish` repository at the commit above; and
- `skills/change-writing/references/technical-writing-clarity.md`,
  `output-styles/bluf.md`, `NOTICE`, and
  `skills/agentic-sdlc/references/skill-authoring.md` in this repository.

Evidence labels mean:

- **[verified]**: directly present in the pinned upstream tree or the named local file;
- **[documented]**: an upstream author/evaluation claim that this research did not
  independently validate against a source outside the authorized set; and
- **[inferred]**: a comparison, product consequence, or recommendation derived from
  verified/documented evidence.

No foreign prose is reproduced. Rule descriptions below are short independent
paraphrases used only to identify compared behavior.

## Bottom-line comparison

The two profiles share the load-bearing controlled-language mechanics: classify
procedural versus descriptive text, cap sentences at 20/25 words, keep paragraphs to
one topic and six sentences, limit noun stacks, keep one instruction per sentence,
use simple verb forms and active voice, keep grammar complete, use lists, keep one
term per concept, order safety commands before consequences, preserve technical
literals, and run a mechanical audit. [verified: upstream
[classification and core rules](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L25-L58);
local `technical-writing-clarity.md:35-80,102-124`]

The local profile is already stronger in three product-critical ways. It distinguishes
safety and message text from ordinary procedures; it forbids clarity edits from
changing a claim's evidentiary strength; and it explicitly refuses dictionary verdicts
or compliance language without licensed material. [verified:
`skills/change-writing/references/technical-writing-clarity.md:10-33,35-64,126-137`]
The BLUF style independently adds answer-first ordering, minimum sufficient support,
explicit uncertainty plus its resolver, and a shortest-complete default. Upstream's
output style contains none of those response-structure rules. [verified:
`output-styles/bluf.md:6-14`; upstream
[output style](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/output-styles/simple-english.md#L7-L23)]

SimpleEnglish's genuinely additive value is narrower: condition-first procedures,
contraction and referent checks, de-nominalization, several punctuation/localization
checks, and a review result that carries an offending span plus a proposed repair.
[verified: upstream
[Rules 3.7, 4.2, 5.4, 8.1 and general recommendations](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L96-L142),
[punctuation and general recommendations](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L174-L199), and
[check-mode contract](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L25-L36)]

## Exhaustive rule comparison

Status terms: **exact** means the local core already owns the substance; **partial**
means it owns only part; **add** is a useful gap; **exclude** means the idea is
unsupported, disproportionate, or contradicts the local contract. The upstream rule
catalog is verified at
[SKILL.md lines 56-199](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L56-L199).
All local comparisons below are [verified] against the authorized local files; each
product disposition is [inferred].

### Rules 1.1-1.14 — words

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 1.1 | Limit ordinary vocabulary to approved entries and declared technical terms. | The local profile explicitly lacks the licensed dictionary and refuses to guess approval (`technical-writing-clarity.md:35-52`). | **exclude**: a dictionary verdict would break the local provenance boundary. |
| 1.2 | Use an approved word only in its authorized grammatical role. | Local consistency requires one part of speech, but cannot know the dictionary's authorization (`technical-writing-clarity.md:40-49,67-79`). | **partial; exclude strict half**. Keep mechanical consistency only. |
| 1.3 | Use an approved word only in its authorized sense. | One term/one concept overlaps; approval does not (`technical-writing-clarity.md:78,92-100`). | **partial; exclude strict half**. |
| 1.4 | Use dictionary-authorized forms of verbs and adjectives. | The local profile allows only a bounded verb-form set but makes no adjective/dictionary verdict (`technical-writing-clarity.md:73-75`). | **partial; exclude strict half**. |
| 1.5 | Permit project vocabulary as technical nouns. | The local judgment rule tells a project to declare its terms (`technical-writing-clarity.md:43-47`). | **exact**. |
| 1.6 | Permit a non-dictionary word only as a technical noun. | Local intentionally does not classify words by dictionary status (`technical-writing-clarity.md:40-52`). | **exclude**. |
| 1.7 | Do not turn a technical noun into a verb. | Local one-part-of-speech consistency is broader but does not call out noun-to-verb conversion (`technical-writing-clarity.md:78`). | **partial**, but not one of the five: de-nominalization captures the higher-value action rule without a dictionary taxonomy. |
| 1.8 | Use the project's established technical nouns. | The local project-term declaration covers this (`technical-writing-clarity.md:43-47`). | **exact**. |
| 1.9 | Prefer short, clear technical names. | Local says a checker cannot decide whether a name is the right one; BLUF prefers plain words but allows defined technical terms (`technical-writing-clarity.md:48-49`; `output-styles/bluf.md:9`). | **partial; exclude as a hard rule** because naming quality remains judgment. |
| 1.10 | Reject regionalisms, slang, and jargon as technical names. | BLUF prefers plain words and short definitions, but does not ban legitimate domain jargon (`output-styles/bluf.md:9`). | **partial; exclude the blanket ban**. |
| 1.11 | Use one name for one item. | Local one-term/one-concept rule and grep pass are the same behavior (`technical-writing-clarity.md:78,92-100,124`). | **exact**. |
| 1.12 | Permit project vocabulary as technical verbs. | Local permits declared project terms but does not separately classify technical verbs (`technical-writing-clarity.md:43-47`). | **partial; no product gap**. |
| 1.13 | Do not turn a technical verb into a noun. | Local has no explicit de-nominalization rule. | **add through Rule 3.7's general action-as-verb shape**, without importing upstream categories. |
| 1.14 | Use US spelling. | Neither local file sets a dialect. | **exclude**: a global dialect preference is unrelated to ambiguity and can conflict with a document's audience. |

### Rules 2.1-2.2 — multi-word nouns

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 2.1 | Limit a noun stack to three words. | Local has the same cap, counting method, audit, and worked rewrite (`technical-writing-clarity.md:71,81-90,121,171-173`). | **exact**. |
| 2.2 | For a necessarily long technical name, define it once and use a short or hyphenated form afterward. | Local always breaks a four-noun stack with a preposition and requires term consistency (`technical-writing-clarity.md:71,78,81-100`). | **partial**. A declared short form can help, but importing this as a second term risks local synonym drift; no harvest. |

### Rules 3.1-3.7 — verbs

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 3.1 | Use dictionary-authorized verb forms. | Local has no licensed dictionary (`technical-writing-clarity.md:40-52`). | **exclude**. |
| 3.2 | Limit verbs to infinitive, imperative, simple present/past/future, with participles only adjectivally. | Local lists the same allowed set (`technical-writing-clarity.md:73`). | **exact**. |
| 3.3 | Use a past participle only as an adjective. | Local says the same (`technical-writing-clarity.md:73`). | **exact**. |
| 3.4 | Avoid complex auxiliary constructions. | Local flags stacked auxiliaries and lists the simple forms (`technical-writing-clarity.md:73,111,122-123`). | **exact** in substance. |
| 3.5 | Treat `-ing` forms as nouns/modifiers, not finite verb constructions. | Local says and audits the same (`technical-writing-clarity.md:74,111,122-123,157-159`). | **exact**. |
| 3.6 | Prefer active voice; allow descriptive passive only when the actor is unknown. | Local says the same and makes procedural active voice unconditional (`technical-writing-clarity.md:75,122-123,153-155`). | **exact**. |
| 3.7 | State an action with a verb rather than an abstract action noun. | Local does not name nominalization, although its rewrite style often does this. | **add**: harvest as a plain mechanical check, with no dictionary claim. |

The upstream catalog also bans five modal verbs and maps uncertain possibility to a
different modal. [verified:
[SKILL.md lines 108-109](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L108-L109)]
That is not a safe clarity rule here. The local profile requires a rewrite to preserve
each claim's evidence strength, and BLUF requires genuine uncertainty to be stated with
its resolver. Replacing epistemic uncertainty mechanically can strengthen a claim.
[verified: `technical-writing-clarity.md:126-134`; `output-styles/bluf.md:10-12`]
Therefore the modal ban is **excluded**; only unsupported filler or unresolved hedging
is removable. [inferred]

### Rules 4.1-4.5 — sentences

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 4.1 | Keep sentences short and clear. | Local turns this into type-specific countable caps (`technical-writing-clarity.md:65-80`). | **exact**, with the local rule more actionable. |
| 4.2 | Keep complete grammar; expand contractions; retain articles and necessary linking words. | Local requires subject, verb, and article, but does not explicitly check contractions or ambiguous omitted links (`technical-writing-clarity.md:76,111-112,161-163`). | **partial; add** the contraction and explicit-link checks. |
| 4.3 | Use vertical lists for complex material. | Local requires a list for complex or three-plus coordinated items (`technical-writing-clarity.md:77,165-169`). | **exact** in rule; see the local-example seed below. |
| 4.4 | Link related sentences with an explicit transition. | BLUF favors minimum detail, while the local clarity file does not require transitions (`output-styles/bluf.md:8,13`). | **exclude as a universal rule**; add a transition only when the relation would otherwise be ambiguous. |
| 4.5 | Put an article or explicit demonstrative before applicable nouns. | Local requires an article but does not require a noun after a bare demonstrative (`technical-writing-clarity.md:76`). | **partial; add** the explicit-referent portion. |

### Rules 5.1-5.5 — procedures

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 5.1 | Cap procedural sentences, including safety text, at 20 words. | Local has the same procedure cap and applies its safety type separately (`technical-writing-clarity.md:54-80`). | **exact**. |
| 5.2 | Put one instruction in each sentence, except genuinely simultaneous actions. | Local requires exactly one imperative and splits compound steps, without the simultaneous-action exception (`technical-writing-clarity.md:72,107-109,149-151`). | **exact core**; retain the stricter local test. |
| 5.3 | Use the imperative for procedures. | Local says the same (`technical-writing-clarity.md:58-63,107-109`). | **exact**. |
| 5.4 | Place a prerequisite before its dependent command. | Local does this for safety commands but not for ordinary procedural preconditions (`technical-writing-clarity.md:63,79`). | **add**: this is the highest-value gap. |
| 5.5 | Keep notes informative rather than imperative, and use the descriptive cap. | Local classifications do not define an embedded note type. | **partial; no harvest**. A note can be classified descriptive under the existing first move without a special rule. |

### Rules 6.1-6.6 — descriptions

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 6.1 | Introduce one new fact per sentence. | BLUF requires one idea per sentence (`output-styles/bluf.md:10`). | **exact**. |
| 6.2 | Use key phrases to expose logical structure. | BLUF puts the conclusion first and permits a short `Why` line or bullets (`output-styles/bluf.md:7-8`). | **partial, locally stronger for response structure**; no harvest. |
| 6.3 | Cap descriptive sentences at 25 words. | Local has the same cap (`technical-writing-clarity.md:69`). | **exact**. |
| 6.4 | Group related information into paragraphs. | Local requires one topic per paragraph (`technical-writing-clarity.md:70`). | **exact**. |
| 6.5 | Keep one topic in each paragraph. | Local says the same (`technical-writing-clarity.md:70,120`). | **exact**. |
| 6.6 | Cap a descriptive paragraph at six sentences. | Local says and audits the same (`technical-writing-clarity.md:70,120`). | **exact**. |

### Rules 7.1-7.3 — safety text

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 7.1 | Label different classes of personal and equipment risk. | Local has a safety type but no fixed risk taxonomy (`technical-writing-clarity.md:58-64`). | **partial; exclude the imported taxonomy**. Software risk needs its own documented severity semantics rather than aerospace labels by analogy. |
| 7.2 | Lead with the command or prerequisite. | Local requires the safety command first (`technical-writing-clarity.md:63,79`). | **exact**. |
| 7.3 | State the possible harm after the command. | Local requires the explanation second (`technical-writing-clarity.md:63,79`). | **exact**. |

### Rules 8.1-8.7 — punctuation and counting

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 8.1 | Avoid semicolons; split the clauses. | Local has no semicolon check and one worked list rewrite uses semicolons (`technical-writing-clarity.md:165-169`). | **add as an audit flag, not a correctness ban**. A semicolon can hide two ideas, but preserving precise quoted or domain text still wins. |
| 8.2 | Hyphenate words that operate as one unit. | Local limits noun stacks but does not prescribe hyphenation (`technical-writing-clarity.md:71,81-90`). | **unique but low-value**; normal editing judgment suffices. |
| 8.3 | Permit parentheses for a bounded set of uses. | Local has no parentheses rule. | **exclude**: an allowlist adds instruction weight without a demonstrated local failure. |
| 8.4 | Treat a list-introducing colon as a sentence boundary for counting. | Local counts between terminal punctuation and gives no list exception (`technical-writing-clarity.md:69`). | **contradiction; retain local counting** unless an experiment proves the exception reduces false positives. |
| 8.5 | Count all parenthetical content as one word. | Local has no such exception. | **contradiction; exclude** because long parentheticals would evade the clarity cap. |
| 8.6 | Count identifiers, numbers, labels, quotations, and similar technical units as one word. | Local masks code, CLI transcripts, command output, and quotations before counting; it does not merely count them as one (`technical-writing-clarity.md:126-129`). | **contradiction; retain the local exclusion**, which also protects exact literals from rewrite pressure. |
| 8.7 | Count a hyphenated expression as one word. | Local gives no exception. | **unique but low-value**; do not complicate the manual count. |

### Rules 9.1-9.4 — writing practices

| Rule | Upstream behavior, paraphrased | Local comparison | Status and disposition |
|---|---|---|---|
| 9.1 | Restructure a sentence when token-for-token substitution fails. | Local worked patterns split or restructure by rule (`technical-writing-clarity.md:139-179`). | **exact in practice**. |
| 9.2 | Preserve dictionary-authorized meaning and grammatical role. | Local preserves concept/part-of-speech consistency but refuses dictionary verdicts (`technical-writing-clarity.md:40-52,78`). | **partial; exclude strict half**. |
| 9.3 | Replace phrasal verbs with single lexical verbs. | Local does not ban phrasal verbs. | **unique but low-value**; a blanket rewrite can make ordinary software instructions less natural and can change established terms. |
| 9.4 | Keep style and terminology consistent across the document. | Local one-term/one-concept rule and term grep say the same (`technical-writing-clarity.md:78,92-100,124`). | **exact**. |

### General recommendations GR-1 to GR-8

The upstream file presents these after the numbered rules at
[lines 188-199](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L188-L199).

| Recommendation | Local comparison | Status and disposition |
|---|---|---|
| Retain a linking `that` where omission can blur the clause boundary. | Local requires complete grammar but names only subject, verb, and article (`technical-writing-clarity.md:76`). | **add**, generalized as explicit links/referents. |
| Treat ambiguous uses of `with` cautiously. | No local equivalent. | **unique but too vague** for a countable profile. |
| Give every pronoun an unambiguous antecedent. | No explicit local equivalent. | **add** under the explicit-referent idea. |
| Prefer a demonstrative plus a noun over a bare demonstrative. | No explicit local equivalent. | **add** under the explicit-referent idea. |
| Avoid words likely to be false cognates for non-native readers. | BLUF prefers plain words (`output-styles/bluf.md:9`). | **partial; exclude as an unauditable judgment rule**. |
| Replace Latin abbreviations with ordinary words or explicit items. | No local equivalent. | **add as an audit flag**, not a universal failure. |
| Use inclusive language. | Not addressed in the authorized local files. | **valuable but out of this clarity-gap decision**; do not imply SimpleEnglish is the needed owner of a general editorial requirement. |
| Avoid uncertain possessive constructions. | No local equivalent. | **exclude as written**; rewrite only when the possessive is actually ambiguous. |

### Non-numbered vocabulary material

The upstream skill adds a modal-conversion ladder, a long AI-filler substitution
table, exact word/part-of-speech rulings attributed to the controlled dictionary, and
synonym-set rewrites. [verified:
[SKILL.md lines 201-281](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L201-L281)]

- The local profile and BLUF already remove unsupported filler, prefer plain words,
  and keep one term per concept (`technical-writing-clarity.md:78,92-100`;
  `output-styles/bluf.md:9-13`). **Overlap: exact in purpose, upstream broader in
  examples.** [verified]
- The upstream strict word rulings cannot enter this repository. The local file says
  that it must not recreate either an approved-word list or a rejected-to-approved
  mapping and must not fabricate dictionary verdicts
  (`technical-writing-clarity.md:17-33,126-137`). **Contradiction: direct.** [verified]
- Several substitutions can change modality or claim strength. Local doctrine makes
  evidence preservation higher priority than smooth prose
  (`technical-writing-clarity.md:126-134,192-204`). **Contradiction: direct for
  mechanical substitution; judgment-only rewrites remain possible.** [verified/inferred]

## Workflow, reference, and output-style comparison

### Canonical workflow

Upstream requires mode selection, passage classification, vocabulary normalization,
catalog application, a mandatory self-check, and preservation of literals. Its review
mode returns a rule identifier, offending span, and proposed rewrite. [verified:
[SKILL.md lines 25-44](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L25-L44)]

| Step | Local comparison | Disposition |
|---|---|---|
| Pragmatic/strict mode | Local separates countable from dictionary/human judgment and refuses compliance claims (`technical-writing-clarity.md:10-52`). | Do not add modes. The local boundary is more honest and needs no user-selected strictness. |
| Classify each passage | Local classifies four types, adding safety and message behavior (`technical-writing-clarity.md:54-64`). | Already stronger. |
| Normalize vocabulary first | Local builds a document concept list and greps variants, but never makes dictionary rulings (`technical-writing-clarity.md:92-100,114-124`). | Keep local consistency; reject strict vocabulary. |
| Apply rules while drafting | Local has a six-step composition loop (`technical-writing-clarity.md:102-112`). | Already covered. |
| Mandatory self-check | Local checks every sentence/paragraph and reports counts; upstream's short check samples the three longest sentences before an optional full audit. [verified: local `technical-writing-clarity.md:114-124`; upstream [lines 303-312](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L303-L312)] | Local is more complete; add only the new pattern checks. |
| Preserve literals | Both protect code, commands, identifiers, and quotations, but disagree on whether protected material is masked or counts as one word. | Retain local masking (`technical-writing-clarity.md:126-129`). |
| Review report | Local requires actionable counts but not a location-plus-rewrite tuple (`technical-writing-clarity.md:114-124`). | Add location and candidate rewrite while retaining counts and evidence strength. |

### `references/checklist.md`

The upstream checklist searches contractions, perfect constructions, selected modals,
progressive passive, selected `-ing` clauses, semicolons, Latin abbreviations, filler,
and trailing conditions; then audits lengths, noun stacks, instruction count,
classification, voice, conditions, terminology, warnings, completeness, and protected
literals. [verified:
[checklist lines 1-38](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/references/checklist.md#L1-L38)]
The local audit already owns every item except contractions, ordinary condition order,
semicolons, Latin abbreviations, and explicit referents. Its full-document counting is
stronger than upstream's short self-check. The upstream prescribed compliance closing
statement and rule-number report must not be copied; the local profile forbids
certification language and unsupported rule/dictionary authority. [verified: upstream
[check-mode close](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/references/checklist.md#L40-L43);
local `technical-writing-clarity.md:17-33,114-137`]

### `references/use-cases.md`

| Upstream target | Local coverage and decision |
|---|---|
| Errors/CLI output | Exact local message pattern: failure, cause, next action (`technical-writing-clarity.md:63,175-179`). No gap. |
| Runbooks/procedures | Exact through procedural classification, imperative mood, one instruction, cap, and safety order (`technical-writing-clarity.md:54-80`). Add only condition-before-command. |
| Incidents/postmortems | Local permits simple past and requires exact evidence strength; upstream's blanket removal of hedging is unsafe when uncertainty is real (`technical-writing-clarity.md:73,130-134`; `output-styles/bluf.md:12`). No generic harvest. |
| Commits/PRs | Local explicitly delegates content/structure to `commit.md`, `pull-request.md`, and `squash.md` (`technical-writing-clarity.md:192-204`). Reject duplication. |
| Release notes/changelogs | Local scope already includes release notes and applies the same mechanics (`technical-writing-clarity.md:6-8`). No target-specific copy. |
| Agent instructions | Local scope already includes skill instruction text (`technical-writing-clarity.md:6-8`); always-on rules belong in always-on prompts, not a new selectable skill (`skill-authoring.md:102-105`). No new surface. |
| Support/status copy | Descriptive caps plus evidence-preserving facts already cover it. No separate rule. |
| Translation preparation | The asserted quality/cost benefit is not tested against the local core in the authorized evidence. [documented: upstream [use case](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/references/use-cases.md#L54-L56)] No product claim. |
| UI/empty states | A possible future target, but not enough to justify a new profile or rule owner. |
| Marketing/blog/brand exclusion | Local clarity selection does not target those genres; BLUF is a separate response style. No conflict and no new rule. |

The upstream adaptations themselves are verified at
[use-cases.md lines 7-64](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/references/use-cases.md#L7-L64).

### Output style and prompt surfaces

The upstream Claude style preserves coding instructions but applies its condensed
technical-writing rules to documentation, messages, reports, commits, and explanations
in every reply; it excludes code and requested marketing. [verified:
[output style lines 1-23](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/output-styles/simple-english.md#L1-L23)]
The README distinguishes this always-on style from task-selected skill activation.
[documented:
[README lines 102-112](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/README.md#L102-L112)]

The local BLUF style also preserves coding instructions and is always on when selected,
but it governs response structure: answer first, minimum support, plain terminology,
one idea per sentence, resolved hedging, explicit uncertainty, and shortest-complete
output (`output-styles/bluf.md:1-14`). The styles therefore overlap on plain/short
prose but are not substitutes. Running both would add competing rules for uncertainty,
technical literals, and global scope. [verified/inferred]

Upstream also ships a standalone full prompt and a claimed compact prompt. The compact
form omits modes, paragraph limits, audit/report behavior, warnings, detailed counting,
references, and disclaimers. [verified:
[system prompt lines 1-31](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/prompts/system-prompt.md#L1-L31)]
Neither belongs in the product: both duplicate the incumbent reference and BLUF surface.
[inferred]

## Selection, context, and update cost

Measurements below are whitespace words and raw UTF-8 bytes at the pinned revisions;
they are reproducible size proxies, not tokenizer-specific token claims. [verified]

| Surface | Size | When paid | Consequence |
|---|---:|---|---|
| Upstream `SKILL.md` | 3,364 words / 19,768 bytes | When selected | Duplicates most of the 1,902-word local clarity reference and introduces conflicts. |
| Upstream frontmatter | 105 words / 784 bytes | Selection surface in a progressive-disclosure host | Broad triggers overlap change-writing and ordinary readability requests. |
| Upstream skill + both references | 4,469 words / 26,792 bytes | Full audit/use-case load | Most expansion is already locally owned. |
| Upstream output style | 361 words / 2,435 bytes | Every reply while selected | Smaller payload, broader and more conflict-prone scope. |
| Upstream standalone prompt | 436 words / 2,947 bytes | Always-on instruction context | A fifth duplicate if adopted here. |
| Local clarity reference | 1,902 words / 11,586 bytes | On demand under an existing skill | No selection row; already authoritative for mechanics. |
| Local BLUF style | 232 words / 1,382 bytes | Every reply while selected | Owns response order/minimum support, not the rule catalog. |

The upstream repository maintains the same policy across the canonical skill, two
references, output style, standalone prompt, and README summaries. The runtime-capable
surfaces already diverge: strict mode rejects a family of verification verbs while the
condensed surfaces tell the model to choose one, and their list thresholds/exceptions
also differ. [verified:
[canonical mode and vocabulary](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L29-L43),
[canonical strict table](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/skills/simple-english/SKILL.md#L267-L276),
[output-style condensed rule](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/output-styles/simple-english.md#L13-L23), and
[prompt condensed rule](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/prompts/system-prompt.md#L13-L23)]

An external companion delegates future fixes to upstream but exposes operators to
unreviewed behavior changes unless installation is pinned. A first-party adaptation
does the inverse: it stays stable here but requires deliberate comparison when the
donor advances. `NOTICE` explicitly requires a re-resolved commit at each donor update,
not an evergreen version label (`NOTICE:328-329`). [inferred/verified]

## MIT licence and `NOTICE` consequences

Upstream is MIT, copyright 2026 AminBlg. Its grant permits reuse and modification but
requires the copyright and permission notice in copies or substantial portions.
[verified:
[upstream LICENSE lines 1-20](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/LICENSE#L1-L20)]
The exact upstream `LICENSE` blob is **1,064 bytes** at the pinned commit. [verified
measurement]

The legal grant and this repository's stricter provenance policy are separate:

- **External companion only.** If the operator runs upstream's own installer and the
  bytes remain in the operator's home under upstream's name/licence, the bundle is not
  a donee and its root `NOTICE` gets no donor entry. The action must remain explicit and
  opt-in. [verified: `skill-authoring.md:148-174`]
- **First-party adaptation.** Even when no upstream sentence is copied, local policy
  admits foreign ideas only through an adapted `references/*.md` plus a same-change
  root donor entry and destination-file provenance header
  (`skill-authoring.md:129-146`). Because the donor has a different copyright holder,
  the `NOTICE` checklist requires the permission grant verbatim, the resolved commit
  and licence byte size, separate origin/licence answers, and exhaustive IS/IS-NOT
  derivation lists (`NOTICE:324-343`).
- **No product role.** Merely retaining this research report creates no product donor
  surface; it records comparison evidence and copies no foreign prose. [inferred]

For option 2, the future donor entry is exact only if it contains all of these fields:

1. repository `AminBlg/SimpleEnglish` and resolved commit
   `59bf6702197a5aadc96d197ea17f290d8d50dcd3`;
2. MIT, upstream licence blob size 1,064 bytes, copyright 2026 AminBlg, and the required
   permission notice reproduced verbatim in `NOTICE`;
3. origin statement: SimpleEnglish says its controlled-language rules are paraphrased
   from ASD-STE100 Issue 9 and that it reproduces neither specification text nor the
   dictionary; record that as an **upstream author claim about a third party**, not as
   independently verified provenance. [documented:
   [README lines 194-219](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/README.md#L194-L219)]
4. **IS derived:** only the five ideas named in this report, all re-expressed in
   `skills/change-writing/references/technical-writing-clarity.md`;
5. **IS NOT derived:** upstream prose, examples, 53-rule numbering/catalog, dictionary
   rulings and vocabulary tables, pragmatic/strict modes, benchmarks, linter, prompts,
   output style, manifests, installer instructions, and compliance wording; and
6. the same provenance statement in the adapted reference header, including
   unofficial/non-endorsement and no-conformance language.

This report deliberately does not reproduce the MIT grant or draft foreign-derived
product prose; those belong only in an authorized implementation change. [verified
scope]

## Options and decision

| Option | Benefits | Costs/risks | Verdict |
|---|---|---|---|
| **1. Optional external companion only** | Upstream retains its full rule catalog, modes, examples, tests, and future maintenance. No root donor entry if installed independently and explicitly. | Adds a broad selection row and 19.8-26.8 KB activation payload; duplicates the core; strict vocabulary and modality conflict with local evidence rules; four policy surfaces already drift. | **Reject as a bundle product role.** Operators can independently choose it when they explicitly want the upstream product, but this bundle should not select, install, or advertise it as the core's complement. |
| **2. Five named ideas in the incumbent reference + exact donor entry** | Closes the real gaps, creates no new skill/output-style row, keeps one local owner, and can preserve evidence/literal boundaries. | First external donor adds a 1,064-byte MIT grant, provenance header, exact IS/IS-NOT record, and deliberate re-evaluation work. | **Recommend.** The benefit is focused and the cost is bounded/auditable. |
| **3. No product role** | Zero donor, context, selection, and drift cost. | Leaves condition ordering, contraction/referent checks, de-nominalization, and more actionable review output absent. | **Reject.** It discards a small but material improvement that fits the incumbent owner. |

## Adversarial pass and rejected alternatives

- **Benchmark evidence does not prove incremental value over this core.** Upstream
  reports large reductions versus a no-skill baseline, but its regex linter misses
  passive voice/part-of-speech errors, can report false positives, uses one generation
  per cell, and measures its own rule score rather than general writing quality.
  [documented/verified:
  [Claude caveats](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/evals/results/RESULTS.md#L32-L47),
  [Pi caveats](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/evals/results/pi-2026-07-31/RESULTS.md#L37-L45),
  and [linter limits](https://github.com/AminBlg/SimpleEnglish/blob/59bf6702197a5aadc96d197ea17f290d8d50dcd3/evals/ste_lint.py#L1-L17)]
- **Reject copying the 53-rule catalog.** It duplicates the core, adds rule-number
  authority the local profile intentionally avoids, and imports dictionary-adjacent
  claims that the local source says it cannot honestly make.
- **Reject adding a `simple-english` top-level skill.** It fails the incumbent audit and
  proportionality gates: a current owner already covers the ground, while a reference
  adds zero selection cost (`skill-authoring.md:47-100,107-127`).
- **Reject a second always-on output style.** It competes with BLUF on uncertainty,
  scope, and literal counting, and duplicates the upstream policy yet again.
- **Reject mechanical modal substitution.** It can convert uncertainty or advice into
  stronger claims, violating local evidence preservation.
- **Reject using upstream version `1.2.0` as the research pin.** The requested current
  state is the exact `main` commit recorded above; a mutable branch or version label is
  insufficient for reproducibility. [inferred]

## Open risks and cheapest decisive follow-up

1. The upstream paraphrase and selected dictionary rulings were not checked against the
   official ASD publication because that source is outside the authorized boundary.
   Do not restate them as independently verified facts.
2. The five-idea recommendation is based on rule coverage and product economics, not a
   direct core-versus-core-plus-five experiment. If implementation reviewers dispute
   the benefit, the cheapest decisive experiment is eight fixed technical-writing
   prompts run twice with the same model/temperature: current local profile versus the
   current profile plus only the five proposed rules. Blind-score ambiguity, preserved
   claim strength, actionable review output, and total context—not upstream regex
   violations alone.
3. Exact token cost depends on the selected host/model tokenizer; bytes and whitespace
   words are the decision-stable measurements here.
4. Upstream `main` can move. Every claim in this report stays pinned to
   `59bf6702197a5aadc96d197ea17f290d8d50dcd3`.

## Out-of-scope SeedProposals — not recorded by this research task

The explicit task forbids ticket/map mutation, so these are proposals for the conductor
to record, not changes made here:

1. **Reconcile the local vertical-list example.** The rule calls for a vertical list,
   but its worked `After` example remains one semicolon-delimited line
   (`technical-writing-clarity.md:165-169`). Do not fix it as part of a SimpleEnglish
   adaptation without a separate owner decision.
2. **Add a cross-surface semantic-drift test upstream only if external companion support
   is later proposed.** Canonical, output-style, and standalone-prompt rules already
   disagree; this bundle should not adopt responsibility for repairing upstream.
3. **Cross-check exact ASD-STE100 Issue 9 provenance only if a future product claim needs
   official rule or dictionary authority.** Until then, the local public-rule-shapes
   boundary remains sufficient and safer.

## Stop condition

The authorized source set is exhausted, all 53 numbered rules plus GR-1 through GR-8,
both references, the canonical workflow, both condensed instruction surfaces, costs,
drift, contradictions, licence consequences, and all three options are accounted for.
Two more sources inside the permitted set would not change the recommendation. Research
stops here.
