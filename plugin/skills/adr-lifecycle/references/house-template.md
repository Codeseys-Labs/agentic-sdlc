# The house ADR template, its four tiers, and every field's meaning

This file is self-contained: it holds the template, the tier-selection matrix, the exact meaning
of every field, and where this house format deliberately departs from convention. You do not
need the parent `SKILL.md` open to use it.

The shape descends from the MADR (Markdown Architectural Decision Records) family and from the
Y-statement form for the one-line tier. Both are credited as idea sources; nothing here is a copy
of either project's template text, and the field set below is this bundle's own, derived from the
records already in this repository's `docs/adr/`. Match those records when in doubt — a
consistent directory beats a more fashionable template.

## Tier selection

Pick by the weight of the decision, not by how much you feel like writing.

| Tier | Use when | Contains |
|---|---|---|
| **One-line** | The choice is real but marginal: cheap to reverse, no external dependency, no cross-cutting effect. Too small for a file, too real to lose. | A single sentence, in the code comment or design doc where it lives. Form below. |
| **Minimal** | A genuine decision with a small blast radius. Reversible within a release. | Title, status, date, deciders, Context, Decision, Consequences. |
| **Standard** | The default for anything clearing the significance gate. | Minimal, plus Considered Options with per-option rejection reasons, plus Confirmation and Reversal Condition. |
| **Extended** | Cross-cutting, expensive to reverse, or contested. Constrains work others must build against. | Standard, plus a typed relationships block, and Compliance where the constraint is mechanically assertable. |

Escalate a tier when you find yourself writing around a missing section. Never de-escalate a
record that already exists at a higher tier — that is a rewrite of history, not a simplification.

### The one-line form

Six slots, in one sentence:

> In the context of *&lt;situation&gt;*, facing *&lt;concern&gt;*, we chose *&lt;option&gt;* over
> *&lt;the main alternative&gt;*, to achieve *&lt;benefit&gt;*, accepting *&lt;cost&gt;*.

If any of the six slots cannot be filled, the decision is not yet made — or it needs a real
file. The most commonly skipped slot is the last one, and it is the one that makes the sentence
a decision rather than an announcement.

## The house template (Standard tier)

```markdown
# ADR-NNNN — <the decision, stated imperatively>

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Deciders:** <who decided, and in what capacity>
- **Relates to:** <paths, other ADR files, or prior records; omit if genuinely none>

## Context

What forces this decision now. The constraints, the evidence, and what breaks if nothing is
decided. Cite specifics by path, command, version, or measurement — not "for performance
reasons".

## Considered options

- **<Option A>** — what it is, and why it was rejected. Be specific: the cost, limit, or
  conflict that ruled it out.
- **<Option B>** — same.
- **<Option chosen>** — named here too, so the comparison is visible in one place.

## Decision

What was decided, numbered when it has parts. Written as settled fact in the present tense
("mise is the single front door"), not as intent ("we will use mise").

## Consequences

- Positive: <what this buys, concretely>
- Negative: <what this costs — at least one, always>
- **Confirmation:** <the real command or review step that checks conformance, or an honest
  statement that conformance is not mechanically checkable>

## Reversal condition

The one observable event that would falsify this decision, and who would see it.
```

Extended tier adds, before Reversal condition:

```markdown
## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-NNNN | <why> |

## Compliance

<Assertions a reviewer or a check can evaluate, one per line, each phrased so its violation is
visible in a diff or a command's output.>
```

## Field meanings, exactly

**Title.** `ADR-NNNN — <decision>`. Imperative and settled. A title ending in a question mark
means the record was written before the decision was made. A title containing "and" usually
means two records.

**Status.** One of `proposed`, `accepted`, `rejected`, `deprecated`, `superseded by ADR-NNNN`.
Transitions are one-way; the rules live in `lifecycle-states.md`. Note that upstream MADR treats
this field as free text — this bundle deliberately closes the vocabulary so the value is
machine-readable, and says so out loud rather than implying upstream agrees.

**Date.** The date the status last changed, not the date drafting started. On acceptance, this
becomes the acceptance date.

**Deciders.** Who actually decided, and in what capacity. Where an agent drafted and a human
decided, say both and distinguish them — the human is the decider, the agent is the drafter.
Never list a model or tool as a decider. Attribution rules are owned by
`../change-writing/SKILL.md` and this field does not override them.

**Relates to.** Untyped pointers for context. Typed edges (Depends-On, Supersedes, Refines,
Part-Of) belong in the Extended tier's Relationships table, where they carry validation rules.

**Context.** The forces, with evidence. This is the section a future reader actually needs: it
must explain why the decision was necessary well enough that someone who disagrees can tell what
would have changed the answer. Verified facts get cited by path, command, or measurement.
Inherited claims get named as inherited.

**Considered options.** At least two, each genuinely on the table, each with its specific
rejection reason. "Rejected as too complex" is not a reason; "rejected because it requires
regenerating a locked toolchain hash in the same commit" is. An option nobody would have picked
does not count toward the two.

**Decision.** Settled, present tense, numbered when it has parts. Rule 9 of the parent skill
binds here: no schemas, no config blocks, no API contracts, no implementations. If the decision
needs those to be understood, they live in a sibling design doc that this record cites by path.

**Consequences.** Both directions, and the negative one is mandatory. A record listing only
benefits documents an announcement, not a decision. Be concrete about what got worse or slower
or more constrained — that is the sentence a future reader will need when the cost lands.

**Confirmation.** The real command or review step in *this* repository that checks conformance.
`mise run check` is a legitimate confirmation; "a future fitness function" is not. Where
conformance genuinely is not mechanically checkable, say that plainly — an honest "not
mechanically checkable; enforced at review" beats an invented check. Note that a passing
confirmation is evidence of conformance only; it never authorizes an outward effect.

**Reversal condition.** One observable event that would falsify the decision, plus who would
see it. "We will revisit in six months" is a calendar reminder, not a reversal condition. "If a
re-runnable per-change benchmark is built and measured for this bundle" is one, because someone
can tell whether it happened.

**Compliance (Extended only).** Assertions phrased so a violation is visible. Each line should
survive being handed to a reviewer with no other context.

## Where this house format departs from convention

Three deliberate divergences, stated so a reader who knows the upstream conventions does not
"fix" them:

1. **The status vocabulary is a closed set**, where upstream MADR leaves the field free-text.
   Closed wins here because the value is read by tooling and by other records.
2. **A typed relationships table** at the Extended tier, where the MADR project's own decision
   record rejected tables in favour of prose links. Machine-readable edges are the doctrine in
   this bundle, and the cost — a table that some renderers handle imperfectly — is accepted
   knowingly.
3. **Reversal condition is mandatory at Standard tier and above**, which no surveyed upstream
   template requires. It exists because an ADR with no falsifier becomes permanent by default,
   and permanence-by-default is how a stale record turns into unquestioned policy.
