# Evidence Discipline (claim admission, not claim promotion)

Use this reference before a worker, role, or the conductor states a finding, a number, a
verdict, or a capability claim that another agent will act on **without re-deriving it**.
This governs **whether a claim may be made at all** — a different question from
`references/research-team.md`'s evidence ladder, which tracks how far an already-admitted
claim has been promoted (idea → conjecture → … → proved), and from
`../change-writing/references/evidence-order.md`, which ranks evidence sources when
authoring commit/PR text. All three compose: a claim must first clear admission (here),
then it may be tracked for promotion (research-team.md), then it may be cited in a message
(evidence-order.md).

The target is traceability, not confidence: a reader must be able to retrace a claim to a
source without trusting the agent that wrote it.

## The anti-inflation rule

**A class is assigned once, at the moment of retrieval, by the agent that retrieved the
artifact. Nobody may raise it later. An unretrieved source is a gap, never a fact.**

A downstream worker, reviewer, or the conductor may reuse a prior agent's text. It may not
reuse a prior agent's class. Reusing the text while re-deriving the class is how a
second-hand relay quietly becomes a first-hand fact three hops later — restate the class as
`primary-claim` about the prior agent's reading, note that the underlying artifact was not
re-read this pass, and re-read it directly whenever the claim is load-bearing (a load-bearing
claim is one where the decision changes if the claim is false).

## The five evidence classes

Assign exactly one class per claim, not per source — one source can carry two classes for
two different claims it makes.

| Class | Assign it when | Typical failure it blocks |
|---|---|---|
| `primary-artifact` | You read the code, the file, the log, or the byte stream yourself, at a named path, commit, or line range. | Describing a mechanism from a summary of it. |
| `primary-claim` | An author states something about their own work or their own run. | Treating a builder's self-report as an independent measurement. |
| `vendor-doc` | The vendor documents its own product, and you read the page in full (not an excerpt). | Promoting a search snippet to documentation; sub-class a partial read as `vendor-doc-snippet`. |
| `author-claim` | A third party asserts something about somebody else's system. | Repeating a characterization as if it were a verified mechanism. |
| `community-report` | Aggregated third-party reporting with no artifact behind it. | Counting reposts of the same post as independent corroboration. |

Sub-class a partial retrieval rather than rounding up (e.g. `vendor-doc-snippet` for a
search-excerpt-only read). A named sub-class is cheaper to defend later than an argument
over whether the class was earned.

## Disposition-row discipline

Write one disposition row per source **before** writing the finding it supports, and
include the sources that failed to retrieve in the same table as the ones that succeeded.
Each row records:

1. The identifier or URL.
2. Retrieved: `yes`, `partial`, or `no`.
3. The retrieval method, exactly enough to repeat it.
4. The class actually reached — never the class hoped for.
5. The author, and the author's relation to the thing described.
6. For a `partial`, the pages or ranges that failed.

Keep the gap register in the artifact that needed it, not in a separate backlog, and let it
stay embarrassing:

- **not-retrieved** — the artifact exists and you did not reach it.
- **partial** — you reached part of it; name the part you did not.
- **negative finding** — you reached the corpus and the thing is absent (different from a
  gap: a gap says you failed to reach an artifact that exists; a negative finding says you
  reached the search space and found nothing there).
- **staleness** — the fact was true against a version you can name, and may no longer hold.

Never reconstruct across a gap. A plausible sentence standing in a gap's place is
indistinguishable from a retrieved fact a few reads later, and that is exactly the failure
this discipline exists to block.

## A receipt is not a control when author and verifier are the same agent

Treat this as a hard rule on your own closures, submissions, and verdicts:

1. Never cite your own prose as evidence for your own claim.
2. Cite a commit, a `file:line`, a command result, or another externally reachable
   artifact instead.
3. Make the citation reachable from the artifact of record (default branch, run log, or
   equivalent) — not only from your own response.
4. Let a different actor read the citation before the claim is treated as closed.

A closure, a "FIXED", a "verified", or a green status written by the same agent that
performed the work is a self-report, not an independent control — it belongs at
`primary-claim`, never at a class that implies independent verification. This is the same
failure `references/worktree-integration.md`'s Hazard 3 names for merges ("worktree-green ≠
main-green"; never push a merge whose gate you have not personally re-run) and that
`references/mission-loop.md` names for the queue ("no closing anything without acceptance
evidence — gates run, output pasted"): a status is a claim about a mechanism, and the class
on that claim decides whether a reader may act on it without redoing the check.

The structural version of the same defect is a state model where the receipt and the
mechanism it attests to are both writable by the same actor — a forger who can write one can
write the other. In-band authority is not a boundary; the fix is to remove the
self-declared field rather than adding a second one that can be forged the same way.

## Phrasings to refuse, and what to write instead

| Refuse | Write instead |
|---|---|
| "Verified." | "`[EXECUTED] <command>` → `<output>`." |
| "The code does X." | "`<path>:<line>` does X (`primary-artifact`)." |
| "Measured at N." | "N, measured by `<actor>` on `<target>` (class)." |
| "Fixed at `<sha>` (merged)." | "Fixed at `<sha>`, ancestor of `<branch>`, control at `<path>:<line>`." |
| "Best practice is X." | "`<vendor page>` recommends X (`vendor-doc`). No measurement published." |
| "Sources agree." | "N independent sources, M vendor-side, listed by row." |
| "Read-only." | "Read-only where dispatch enforces it. Name the enforcement point." |

## What this is not

This is prose and claim-admission discipline for every advisory submission in this bundle's
roles — cartographer findings, reviewer verdicts, researcher briefs, critic seeds, and the
conductor's own recorded evidence. It is **not a mechanism**: nothing here is checked at
dispatch, wired to a gate leaf, or enforced by any runtime, and a skill body cannot enforce
anything about the agent reading it. Do not describe this reference as a control — that
would reproduce the exact defect the receipt-vs-control rule names above. Roles and verdicts
remain advisory submissions regardless of the evidence class attached; a well-classed claim
is still not authorization for an outward effect (push, publication, PR mutation, merge,
deployment).

## Cross-links

- `references/research-team.md` — the evidence **ladder** (claim promotion over time:
  idea → conjecture → … → proved). This file owns the class on a single claim at the moment
  it is made; research-team.md owns how far an admitted claim has since been promoted. Do
  not restate one doctrine in the other.
- `../change-writing/references/evidence-order.md` — the six-step ladder for choosing which
  evidence to cite when *authoring* a commit/PR message, plus the omit-or-placeholder rule.
  That reference assumes the claim already cleared admission; this file is the admission
  gate upstream of it.
- `references/worktree-integration.md` — Hazard 3 (verify by artifact and re-gate on main,
  never by "done") is this file's receipt-vs-control rule applied to fan-in.
- `references/mission-loop.md` — "no closing anything without acceptance evidence" is this
  file's receipt-vs-control rule applied to the Seeds queue.
