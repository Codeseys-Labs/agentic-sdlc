# ADR status vocabulary, transitions, and supersession

Self-contained: the status values, what each means, the legal transitions, the acceptance bar,
and the exact supersession sequence. You do not need the parent `SKILL.md` open to use this.

## The five status values

| Status | Meaning | Is it a constraint? |
|---|---|---|
| `proposed` | Written, under review, not yet decided. | No. A proposed record constrains nothing. |
| `accepted` | Decided and in force. Immutable except for its status line. | Yes — this is the only status that constrains. |
| `rejected` | Considered and decided against. Kept, never deleted. | No, but it is evidence: it records that this option was examined. |
| `deprecated` | Was in force, no longer applies, and nothing replaced it. | No. Historical context only. |
| `superseded by ADR-NNNN` | Was in force, replaced by a specific newer record. | No. The named replacement is the constraint. |

Two values that look reasonable and are not in the set: "draft" (that is `proposed`) and
"obsolete" (that is `deprecated`, or `superseded by` if something replaced it). Do not invent a
sixth value. If a record genuinely does not fit these five, that mismatch is itself worth a note
in the record rather than a new vocabulary entry.

## Transitions are one-way

```
proposed ──> accepted ──> deprecated
    │             │
    │             └──────> superseded by ADR-NNNN
    └──────> rejected
```

Every legal move, and nothing else:

- `proposed → accepted` — the decision is made and the acceptance bar below is met.
- `proposed → rejected` — the decision went the other way. The record stays; it now documents
  the option that was examined and declined.
- `proposed → proposed` — review produced comments. The record stays proposed with those
  comments assigned to named people. This is a normal, common outcome, not a failure.
- `accepted → superseded by ADR-NNNN` — a newer accepted record replaces it.
- `accepted → deprecated` — it no longer applies and nothing replaced it (the situation went
  away rather than being re-decided).

**Illegal, and why:** `accepted → proposed` (you cannot un-decide; write a superseding record),
`rejected → accepted` (the reconsideration is a new record that may cite the rejected one),
`superseded → accepted` (resurrect by writing a new record, not by editing an old one), and any
transition that skips `accepted` on the way to `superseded` or `deprecated` — a record that was
never in force has nothing to supersede.

## The acceptance bar

`proposed → accepted` requires all five, in writing, inside the record:

1. **Evidence** — the Context section's claims are backed by paths, commands, versions, or
   measurements, and inherited claims are marked as inherited rather than presented as verified.
2. **Criteria** — the decisive driver is named. A reader can tell which force settled it.
3. **Agreement** — the named deciders have actually decided. An agent-drafted record is not
   accepted because drafting finished; a human decides.
4. **Documentation** — at least two considered options with specific rejection reasons, at least
   one negative consequence, a Confirmation, and a Reversal Condition.
5. **Review** — the review protocol in `review-and-antipatterns.md` ran, and every comment is
   either resolved or explicitly carried as an assigned action point.

Elapsed time is not on this list. A record does not become accepted because nobody objected for
a week; silence is not agreement. If review cannot be convened, the honest state is `proposed`
with the blocker named.

## What immutability forbids, and what it does not

**After a record reaches `accepted`, the only edit to that file is its status line** (and, when
superseded, the pointer to the replacement).

Forbidden: rewriting Context because better evidence arrived; adding an option that was thought
of later; softening a negative consequence; adding a dated "Update:" section; correcting the
Decision because the implementation drifted. Each of those is a new decision wearing the old
record's clothes, and each destroys the thing an ADR exists for — a reader being able to tell
what was known and decided *at that time*.

Permitted: the status line change; a typo or broken-link fix that changes no claim; adding this
record's ID to the *index*; and other records citing it.

The failure this rule prevents is specific and common: a record that accumulates updates becomes
a changelog, and a changelog cannot answer "what did we decide, and what did we know when we
decided it?" — which is the only question ADRs are good at.

## Supersession, in order

Superseding is two records and one index entry, in one change, in this sequence:

1. **Write the replacement** as `proposed`. Its Context explains what changed since the original
   — new evidence, a new constraint, a cost that landed. Its Relationships table (or Relates-to
   line at lower tiers) records `Supersedes: ADR-NNNN`.
2. **Review the replacement** on its own merits, through the full protocol. A supersession is not
   a lighter-weight change; it is a decision, and it gets a decision's review.
3. **Accept the replacement.** Only now does it constrain anything.
4. **Flip the old record's status** to `superseded by ADR-MMMM`, changing nothing else in that
   file.
5. **Rebuild the index** so both records show their current status.

**Order matters, and this is the rule most often broken.** Flipping the old status while the
replacement is still `proposed` leaves a window where *neither* record is in force: the old one
says it has been replaced, the new one says it has not been decided. Anyone reading during that
window has no authoritative answer. Keep the old record in force until the new one is.

Steps 1 through 5 land as one change. Commit or PR text comes from `../change-writing/SKILL.md`.

## Partial supersession

A replacement that overrides only part of an older record is a common real case and a trap. Do
not mark the old record `superseded by` — most of it is still in force, and that status would
wrongly retire the rest.

Instead: the new record's Relationships table carries `Refines: ADR-NNNN` with a note naming
exactly which part it narrows, and the old record stays `accepted`. If the overridden part is
large enough that the remainder no longer stands coherently on its own, that is the signal to
supersede fully and restate the surviving parts in the replacement.

## Deprecation without replacement

Use `deprecated` when the decision stopped applying because its context disappeared — a
dependency was dropped, a subsystem was deleted, a constraint was lifted. The record's status
line changes and nothing else. Add nothing explaining why; if the reason is worth recording, it
is worth its own record, and that record cites this one.

## Reading records by status

When loading ADRs as context for a review or a plan: **only `accepted` records are
constraints.** Load `proposed`, `rejected`, `deprecated`, and `superseded` records as history —
they explain how the current state came to be, and they are frequently the fastest way to find
out that an idea was already examined and declined. Treating a non-accepted record as binding is
the single most common ADR misuse, and it produces confident arguments from records that were
explicitly not adopted.

A record's status is evidence about its own standing. It is never authorization for an outward
effect: an `accepted` status permits nothing to be pushed, merged, published, or deployed.
