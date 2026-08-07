# Typed edges between records, the index, and multi-record initiatives

Self-contained: the five relationship types, their validation rules, how to rebuild an index, and
how to structure an initiative that spans several records.

## Why typed edges rather than prose links

A prose link ("see also ADR-0003") records that two records are related but not *how*, so nobody
can answer the question that actually matters at review time: if I change this record, what else
becomes wrong? Typed edges make that answerable. The cost is a table that some Markdown renderers
handle imperfectly, and this bundle accepts that cost knowingly — see the divergence note in
`house-template.md`.

## The five edge types

Each is directed. The direction is stated from the perspective of the record carrying the edge.

| Edge | Meaning | Implication when the target changes |
|---|---|---|
| **Depends-On** | This decision is only valid because the target decision holds. | If the target is superseded or deprecated, this record needs re-examination. It does not auto-demote, but it is now suspect and must be reviewed. |
| **Supersedes** | This record replaces the target entirely. | The target's status becomes `superseded by` this record — after this one is accepted, never before. |
| **Refines** | This record narrows or specializes part of the target, which otherwise stands. | The target stays `accepted`. The note must name exactly which part is narrowed. |
| **Relates-To** | Same subject area, no dependency either way. The weakest edge, and the right one when you are unsure. | None. It is navigational. |
| **Part-Of** | This record is one decision inside a larger named initiative. | The initiative's rollup reflects this record's status. |

Prefer the weakest edge that is true. An over-typed graph — everything marked Depends-On because
it sounds rigorous — produces re-examination noise on every change and gets ignored within a
release, which is worse than prose links.

## Validation rules

Five rules. The first three are errors; the last two are warnings that need a written note.

1. **No cycles.** A Depends-On cycle means the decisions were not actually separable and should
   be one record, or the dependency direction is wrong in at least one of them.
2. **Never depend on a `rejected` record.** A rejected record documents a path not taken; a
   decision resting on it rests on nothing. This is almost always a wrong ID.
3. **Every edge carries a note.** An untyped, unexplained edge is a prose link with extra
   ceremony. One clause naming what the relationship consists of is the minimum.
4. **Depending on a `superseded` record is a warning.** Legal — the dependency may predate the
   supersession — but the record needs review, and the note should say whether the replacement
   changes anything for this record.
5. **Part-Of must target a real initiative record**, not another ordinary record. If the target
   is not an initiative, the edge is probably Depends-On or Refines.

Check these at Step 7 of the workflow, and again at review. They are cheap to verify by reading
and expensive to discover later.

## The index

The index is a generated view, not a hand-maintained document. Rebuild it; never append to it by
hand. Hand-appending is how a record ends up absent from the index, and **an ADR missing from the
index is an ADR nobody can find** — functionally identical to never having written it.

A minimum useful index, one row per record:

```markdown
# Architecture Decision Records

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](0001-kebab-title.md) | <title text> | accepted | 2026-08-06 |
```

Rebuild from the files themselves: read each `NNNN-*.md`, take the title from the `# ` line and
the status and date from the metadata lines, sort by number. Every record in the directory
appears, whatever its status — a `rejected` or `superseded` record that vanishes from the index
takes its evidence with it.

**Two failure modes worth checking for explicitly.** First, a record deleted from disk but still
listed in a hand-maintained index: the index points at nothing, and a rebuild is the fix, not a
one-line correction. Second, an ID-shaped string that is not an ADR reference — issue numbers,
pull-request numbers, and commit hashes all produce false matches when scanning prose for
`ADR-NNNN`. Match the record-ID form specifically, and expect prose to contain other numbers.

## Multi-record initiatives

When one body of work needs several decisions that only make sense together, add one initiative
record. It is an ADR at Extended tier whose subject is the shape of the work rather than a single
technical choice.

It carries:

- **Strategic context** — why this initiative exists, and what it is trying to change.
- **Scope boundary** — what is explicitly *not* in it. This is the section that keeps an
  initiative from absorbing every adjacent decision.
- **A child registry** — one row per member record: ID, title, status, and what it decides.
- **Sequencing** — which child decisions must be settled before which others, and why. This is
  the actual value of the pattern: it makes the dependency order visible before anyone starts.

Each child record carries `Part-Of: ADR-NNNN` back to the initiative.

**Rollup status.** The initiative's own status is derived from its children, and is
information, not a gate:

| Children | Initiative reads |
|---|---|
| All `proposed` | proposed |
| Some `accepted`, some `proposed` | in progress |
| All `accepted` | accepted |
| Any child blocked on an unresolved dependency | blocked, naming the blocker |
| Any child `rejected` in a way that invalidates the plan | needs re-examination |

A rollup is a summary of recorded states. It is not evidence that the work is done, and it
authorizes nothing.

**When not to use this.** Two or three related records do not need an initiative — `Relates-To`
edges are enough. The pattern earns its cost at roughly five or more interdependent decisions
with a real sequencing constraint. Below that it is ceremony that has to be maintained.

## Keeping the graph honest

The edges are only worth having if they are checked. Practical minimum: at review time, read the
edges of the record under review and follow each one far enough to confirm the target exists, has
the status the note assumes, and actually says what the note claims. That is a two-minute check
that catches wrong IDs, silently superseded dependencies, and notes that were true when written
and are not now.

Everything in this file is bookkeeping over evidence. A well-formed graph, a clean index, and a
green rollup are records of what was decided; none of them authorizes a push, merge, publication,
or deployment.
