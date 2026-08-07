# Reviewing an ADR: the protocol, the checklist, and the named failures

Self-contained: how to run an ADR review, what to check, and the recurring failure shapes on
both sides of the table. Use it when reviewing someone else's record, and when auditing your own
draft before submitting it.

## Roles

Three roles, and conflating them is where most bad reviews start.

- **Author** — drafts the record. May be an agent.
- **Deciders** — actually make the decision. Humans. Named in the record.
- **Owner** — keeps the record moving: convenes the review, tracks unresolved comments, flips
  the status when the bar is met. Often but not always the author. Where no owner is named, a
  record that stalls in `proposed` stalls silently and forever, which is the most common way ADR
  practice dies in a repository.

## The review protocol

1. **Silent read, 10 to 15 minutes.** Everyone reads the record and writes comments down. No
   discussion yet. Reading aloud or discussing first collapses independent judgment into the
   first opinion voiced.
2. **The owner reads out each comment** in turn, and the author responds. Every comment gets
   spoken; none is quietly dropped for time.
3. **Outcome, one of three:**
   - `accepted` — the bar in `lifecycle-states.md` is met.
   - stays `proposed` **with named action points assigned to named people**. Not a rejection; a
     specific list of what is missing.
   - `rejected` **with the reason recorded in the record itself**. The record stays in the
     directory; a rejected decision that was examined is valuable evidence.
4. **Time box it.** 30 to 45 minutes, fewer than ten participants, one to three read-out cycles.
   A review that needs more than three cycles is usually reviewing a record that should be split.

Most decisions are reversible. Spending an hour of a full room on a two-way-door decision is its
own failure — check the tier before convening anyone.

## The seven-question checklist

Run these in order. The first "no" is usually the whole review.

1. **Is this problem worth an ADR at all?** Or is it a one-liner, a design-doc paragraph, or an
   implementation detail wearing a decision's clothes?
2. **Are the options viable, and is an obvious one missing?** Name the missing one out loud. A
   plausible option absent from the list is the most damaging review finding available, because
   it means the comparison was never really made.
3. **Are the decision drivers distinct and non-overlapping?** Three restatements of "it should
   be maintainable" are one driver, not three.
4. **When drivers conflict, is the priority stated?** Every real decision trades something off.
   A record where all drivers point the same way is describing a non-decision.
5. **Does the rationale actually follow from the drivers?** Check the link, not the vibe. A
   sound-looking conclusion that does not follow from the stated forces means the real reason is
   unstated.
6. **Are the consequences reported objectively?** Specifically: is there a real negative, and is
   it a real one rather than a decorative one?
7. **Is the outcome actionable and traceable — with a Confirmation and a Reversal Condition that
   name observable things?**

## Creation anti-patterns

Failures in the drafting. Each entry gives the tell, so it can be spotted in a read rather than
argued about.

| Anti-pattern | Tell |
|---|---|
| **Retrospective rationalization** | The record was written after the code shipped and reads as a defence. Options section contains only the option taken plus obvious losers. |
| **Wishful thinking** | Consequences are all positive, or the negative one is "requires some initial setup". |
| **Sales pitch** | Adjectives about the chosen option ("modern", "robust", "industry-standard") in place of measurements. |
| **Free lunch** | Claims a benefit with no corresponding cost. Every real architectural choice costs something; find it or the decision is not understood. |
| **Straw option** | An "alternative" nobody would have chosen, present only to make the count reach two. Rule 2 is about genuine consideration, not arithmetic. |
| **Tunnel vision** | Exactly one option, or one option plus "do nothing". |
| **Rushed record** | Written in the same minute as the decision, with placeholder Context. The record is cheap; the missing reasoning is not. |
| **Specification in disguise** | Full schemas, config blocks, or API contracts in the body. The decision is buried in an implementation. Violates hard rule 9. |
| **Mega-record** | Several decisions in one file, usually visible in an "and" in the title. |
| **Novel** | Pages of narrative where a reader needs one screen. Length is not rigour; a long record buries the decision it was written to expose. |
| **Pseudo-accuracy** | Precise-looking numbers with no source — "improves throughput by 40%" with nothing behind it. Either cite the measurement or state the expectation as an expectation. |
| **Changelog drift** | Dated "Update:" sections appended to an accepted record. Violates hard rule 7; supersede instead. |
| **Stale record as gospel** | An accepted record cited as binding years after its Context stopped being true. This is what Reversal Conditions exist to prevent, and it is why a record without one is dangerous rather than merely incomplete. |
| **Wiki record** | The decision lives somewhere editable-in-place with no history. An ADR's value is that its version is fixed; a mutable page is not an ADR. |

## Review anti-patterns

Failures in the reviewing. These are harder to name in the moment and do more damage, because a
bad review produces a record that everyone believes was checked.

| Anti-pattern | Tell |
|---|---|
| **Pass-through** | "Looks good to me" on a record with one option and no negative consequence. The review added no information. |
| **Copy edit** | Every comment is about grammar and formatting; nothing about whether the decision is sound or the options were real. |
| **Excursion** | The review becomes a design discussion about the chosen option's implementation. Note it and move on — the record is about the choice, not the build. |
| **Bikeshedding** | Extended debate on the cheapest, most reversible aspect while the expensive irreversible one goes unexamined. |
| **Self-review** | The author is also the only reviewer, or the deciders are exactly the authors. Independence is a property of who reviewed, not of how carefully. |
| **Power play** | The decision is settled by seniority rather than by the recorded drivers. If that happens, the honest record says the driver was a stakeholder's call — which is legitimate, and much better than an invented technical rationale. |
| **Offended response** | The author treats findings as attacks. The record is the subject, not the author. |
| **Groundhog Day** | The same objection is raised in successive reviews because the response was never written into the record. If a comment recurs, the fix belongs in the record's text. |

## Author's obligations

Before submitting: the two options are genuinely considered; every rejection reason is specific
enough to be disagreed with; there is a real negative consequence; every factual claim is cited
by path, command, version, or measurement, or explicitly marked as inherited or unverified; the
Confirmation names something real; the Reversal Condition names an observable event. Where
evidence for a claim is missing, **omit the claim** or leave an explicit placeholder — never fill
the gap with plausible prose.

## Reviewer's obligations

Read the record before the discussion. Check the decision, not the prose. Name a missing option
if you can think of one. Say plainly when a claim is unsupported. Do not repair what you find —
a reviewer who rewrites the record has become its author and destroyed the independence that
made the review worth anything. Findings go back to the author; work that outlives the review
leaves as one typed `SeedProposal` for conductor triage.

A review verdict is advisory evidence. It records what was found; it authorizes nothing — not a
merge, not a publication, and not the status flip, which needs the full acceptance bar in
`lifecycle-states.md`.

## Reviewing code against an accepted record

An accepted record that nothing ever checks is inert. When a reviewer finds a change that
violates one, the move is to link the record and ask the *code* to change — not to quietly amend
the record to match what was built. Amending an accepted record to fit new code is supersession
without review, and it converts every past decision into a description of the present.

If the record is genuinely wrong, that is a superseding record (see `lifecycle-states.md`), not
an edit. If the code is wrong and cannot be fixed now, the gap is tracked work with the record
cited — an accepted record does not retroactively make non-conforming code compliant.
