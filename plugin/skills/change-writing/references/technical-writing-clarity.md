# Countable clarity rules for prose a reader must act on

Self-contained: a mechanical self-audit for documentation, runbooks, error messages, and
instruction text. You do not need `SKILL.md` open to use it.

Use it when writing or revising a README, a CONTRIBUTING file, an ADR or design-doc body, a
runbook or procedure, an error or log message, a release note, a pull-request body, or the
instruction text of a skill — and when a reviewer calls a document unclear, wordy, or ambiguous.

## Provenance and limits — read this first

The rule *shapes* below are restated from the publicly documented structure of ASD-STE100
(Simplified Technical English), a controlled-language standard maintained by ASD's Simplified
Technical English Maintenance Group. The standard has two parts: a set of writing rules grouped
into sections, and a controlled dictionary of approved and not-approved words with alternatives.

Four constraints on how this file may be used, and they are not negotiable:

1. **This is not the standard, and it does not reproduce it.** Only publicly documented rule
   shapes are restated here, in this bundle's own words. No rule text is quoted, and the
   dictionary — the licensed half of the standard — is not reproduced, summarized, or partially
   reconstructed anywhere.
2. **Never claim compliance, conformance, or certification.** ASD-STE100 is a copyright and a
   registered trademark of ASD, and the maintenance group endorses and certifies nothing. Do not
   write "STE compliant", "STE certified", or "ASD-STE100 conformant" about any artifact, and do
   not use the associated logo or trademark. The honest phrasing is "checked against public
   clarity rule shapes".
3. **The word-count figures below come from public secondary summaries**, not from the standard's
   own body text. Treat them as the widely published shape of the rule, which is what makes them
   useful as a self-audit threshold — not as quoted normative text.
4. **Do not create an approved-word list** or a not-approved-to-approved mapping table in this
   repository. That is precisely the licensed material, and reconstructing it piecemeal is the
   same act as copying it.

This file's status is **STE-inspired**, and that is the strongest status it can ever have.
Conformance to ASD-STE100 is a certification statement against a licensed aerospace specification
with its own controlled dictionary. Nothing in this repository can support that claim. The product
specification records that as an explicit non-goal in its out-of-scope list
(`docs/plans/claude-code-first-harness/agentic-sdlc-product-spec.md`). The release contract
enforces the same boundary: `policy/release-contract.v1.json` lists the `asd_conformance` category
under `claim_lint.forbidden_claims`. Release-claim text that asserts conformance therefore fails
`mise run validate`. An edit that drifts this file toward a conformance claim is wrong even when it
satisfies every rule below. Delete the claim, not this paragraph.

## Two rule classes, and they are not equal

**Countable rules** are mechanically checkable by reading and counting. They are this file's real
product, and every one of them is in the table below.

**Judgment rules** need the licensed dictionary or a human. Flag them; never fake them. In
particular:

- Whether a specific word is in the approved dictionary. This file cannot know, and neither can
  any checker that lacks a licensed copy.
- Whether a domain term qualifies as a legitimate technical term. The standard's own mechanism for
  project jargon is that a project *declares* its technical terms. So the correct answer when this
  comes up is "declare a project term list", never "guess".
- Whether the chosen technical name is the *right* name for the thing. A checker can tell you a
  sentence is long. It cannot tell you that you named the wrong component.

Stating this split is what keeps the file honest: it makes the gap visible instead of implying
mechanical coverage the rules do not have.

## First move: classify the text

The caps and the required mood differ by type, so classify before writing.

| Type | What it is | Mood |
|---|---|---|
| **Procedural** | Steps a reader performs | Imperative, active, always |
| **Descriptive** | Explanation a reader understands | Active by default; simple present |
| **Safety** | A warning or caution | Command first, then the explanation |
| **Message** | Error, log, or CLI output | Imperative; state cause and next action |

## The countable rules

| Rule | Threshold | How to count | Applies to |
|---|---|---|---|
| Sentence length | At most 20 words in procedures; at most 25 in descriptive text | Words between terminal punctuation marks | Both |
| Paragraph length | At most 6 sentences, and one topic per paragraph | Sentences per paragraph | Descriptive |
| Compound nouns | At most 3 words in a row acting as one noun | Count consecutive nouns; break the fourth with a preposition | Both |
| One instruction per sentence | Exactly one | Count imperative verbs; split compound steps | Procedural |
| Verb forms | Infinitive, imperative, simple present, simple past, simple future; past participle as an adjective only | Scan for stacked auxiliaries — "will have been processed" | Both |
| Descriptive tense | Simple present, unless the sentence states a real past event or a real future change | Scan descriptive text for "will", "was", "were", and other past or future forms; keep each only for an actual time fact | Descriptive |
| `-ing` words | Only as a noun or a noun modifier, never as a present-participle verb | Scan every word ending in `-ing` | Both |
| Voice | Active. Passive only in descriptive text, and only when the actor is genuinely unknown | Scan for a form of "be" followed by a past participle | Procedural: always active |
| Completeness | Do not drop the subject, the verb, or the article to shorten a sentence | Check each sentence has all three | Both |
| Vertical lists | Use a list for complex or coordinated material | Any sentence with three or more coordinated items | Both |
| One term per concept | One word, one meaning, one part of speech | Build a term list for the document; grep each variant, then grep each term for hits that mean something else | Both |
| Safety order | The command comes first, the explanation second | Check the first clause is the imperative | Safety |

### The compound-noun rule, worked

This is the rule that produces the biggest legibility gain and the one writers resist most,
because long noun stacks feel precise. They are not — they are ambiguous, because the reader has
to guess which noun modifies which.

- Four nouns deep: "runway light connection resistance"
- Broken with a preposition: "the resistance of the runway light connection"

The second is longer and unambiguous. Length is not the metric; recoverable meaning is.

### One term per concept, worked

Pick one word per concept and never vary it for style. If the document says *start*, it says
*start* every time — never *begin*, *launch*, *initiate*, or *kick off* as synonyms. Synonym
variation is a virtue in prose and a defect in instructions, because the reader cannot tell
whether a different word means a different thing.

The mechanical check: list the document's concepts, then grep each variant. Every hit on a synonym
is either an error or an undeclared second concept.

### One meaning per word, worked

The same rule, run in the other direction: one term per concept, and one concept per term. A word
that means two things in one document turns every occurrence into a guess.

- Overloaded: "check" as the repository gate ("run the check") and "check" as the verb to verify
  ("check the receipt").
- Split: keep "check" for the gate; write "verify the receipt".

The mechanical check reuses the term list: grep each term and read every hit. A hit that means
something else is either an error or a missing second term. Check the part-of-speech clause the
same way. When one term serves as both a noun and a verb for different things, rename one of the
two uses.

## Apply while writing, not afterwards

The rules are cheap during composition and expensive as a rewrite pass. Before emitting each
paragraph:

1. Classify the text type.
2. Write one instruction per sentence, imperative for procedures.
3. Count the words against the type's cap.
4. Count consecutive nouns in each compound.
5. Scan for "be" plus a past participle, and for `-ing` used as a verb.
6. In descriptive text, keep the simple present unless the sentence states a real time fact.
7. Confirm the subject, verb, and article are all present.

## The self-audit pass

After a draft, five mechanical passes. Report **counts**, not impressions — "four sentences over
the cap, longest 34 words" is actionable; "a bit wordy" is not.

1. **Sentence lengths.** Every sentence, against its type's cap. List the offenders with counts.
2. **Paragraph sentence counts.** Anything over six, and anything covering two topics.
3. **Noun clusters.** Every run of three or more consecutive nouns; flag the fours and up.
4. **Verb form and voice.** Every stacked auxiliary, every `-ing` verb, every passive in
   procedural text, and every past or future form in descriptive text that states no real time
   fact.
5. **Term consistency.** The concept list, with a grep per variant and a grep per term for hits
   that mean something else.

## What these rules must never do

- **Never apply the caps to quoted material, code, CLI transcripts, or command output.** Those are
  reproduced exactly or they are wrong. Mask them before counting.
- **Never let a rewrite change a claim's strength.** This is the important one where this file
  meets the rest of this skill: tightening prose must not turn a hedged statement into a confident
  one, or a specific measurement into a vague one. Clarity edits preserve the evidence class of
  every claim exactly. If a sentence is unclear *because* the underlying evidence is thin, the fix
  is in `evidence-order.md` — omit the claim or mark it — not in the phrasing.
- **Never claim compliance or certification**, per the provenance section above.
- **Never fabricate a dictionary verdict.** "This word is not approved" is a claim this file
  cannot support.

## Rewrite patterns

Worked before/after pairs for the rules that need them. All examples written for this file.

**Sentence over cap → split at the conjunction.**
Before: "If the receipt is missing or the digest does not match the recorded value, the command
stops and reports the mismatch, and no further steps run." (25 words, procedural)
After: "The command stops if the receipt is missing. It also stops if the digest does not match
the recorded value. It reports the mismatch and runs no further steps."

**Two instructions in one sentence → two sentences.**
Before: "Install the tool and then run the check to confirm the version."
After: "Install the tool. Run the check to confirm the version."

**Passive in a procedure → active imperative.**
Before: "The configuration file should be reviewed before the install is started."
After: "Review the configuration file before you start the install."

**`-ing` as a verb → simple present.**
Before: "The validator is checking each reference and is reporting the missing files."
After: "The validator checks each reference and reports the missing files."

**Past or future tense for present behavior → simple present.**
Before: "The validator will reject a broken reference."
After: "The validator rejects a broken reference."
Keep "will" for a real future change and the past for a real past event — "an earlier revision of
this file lacked this rule" — never for how the thing behaves today.

**Dropped article and subject → complete sentence.**
Before: "Missing receipt causes failure."
After: "A missing receipt causes the command to fail."

**Coordinated items → vertical list.**
Before: "The check validates the name, the description length, the reference links, the manifest
parse, and the shell syntax."
After: "The check validates: the name; the description length; the reference links; the manifest
parse; the shell syntax."

**Compound noun over three → break with a preposition.**
Before: "worktree trust configuration path validation"
After: "validation of the trust configuration path for the worktree"

**Error message, restructured.**
Before: "Error: invalid state."
After: "Cannot read the receipt: the file is missing. Run the bootstrap command to create it."
An error message states what failed, why, and what to do next — in that order, in one or two
sentences.

## Optional tooling

Prose linters exist that check the mechanical subset — sentence length, passive voice, banned
words — and can be run at use time without being installed or pinned. Two cautions if one is
used: mask code fences and transcripts before linting, and treat the output as advisory. **No
prose linter is pinned or wired into any gate in this repository**, and a linter score is evidence
about the text rather than a verdict on whether it says the right thing.

The primary product of this file is the manual countable self-audit, which needs no tooling and no
network.

## Neighbours

This file owns **sentence mechanics**. It does not own what a document should claim.

- `evidence-order.md` owns whether a claim may be made at all, and how strongly.
- `commit.md`, `pull-request.md`, and `squash.md` own the content and structure of change
  messages; this file only tightens their prose.
- `attribution-policy.md` owns attribution, and a clarity edit never adds or removes a trailer.
- `../adr-lifecycle/SKILL.md` owns the structure of a decision record; this file applies to its
  prose sections only, and never to its status vocabulary or field names.

Where a clarity rule and a neighbour's rule appear to conflict, the neighbour wins — a well-formed
sentence that misstates the evidence is worse than an awkward sentence that states it correctly.
