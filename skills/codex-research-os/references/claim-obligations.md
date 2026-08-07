# Typed obligations: making a claim's rung depend on records, not on its author's own prose

Self-contained: the defect in the shipped review gate, the schema change that fixes it, the
resolution rules, and the demotion triggers. You do not need `SKILL.md` open to use this.

This is a **design refinement for the generated research layer**, not a description of what the
installer emits today. The shipped gate behaves as described in §1 right now. Read §5 for what is
built versus what is designed.

## 1. The defect, reproduced

The generated `scripts/check_review_gates.py` decides whether a claim may hold a promoted rung by
**substring-matching a free-text field the claim's own author writes**. It concatenates the
claim's `evidence`, `review_evidence`, `counterevidence`, and `artifact_paths` into one lowercased
string, then asks whether words like `replication`, `adversarial`, or `review` appear in it.

The consequence, executed and confirmed on 2026-08-07 against the shipped generator logic:

```yaml
claim_type: empirical
status: experimentally_supported
importance: high
evidence:
  - "replication pending"
  - "no adversarial review yet"
  - "prior art unclear"
```

This claim **passes both the replication gate and the adversarial-review gate**. The first
string contains `replication`; the second contains both `adversarial` and `review`. The gate
reports no errors and exits clean.

Every one of those three strings says, in plain English, that the review has *not* happened. The
gate cannot tell, because it is matching characters in a field the constrained party controls.

This is the general failure of a control whose input is writable by the party it constrains:
a self-declared authority field. The gate is not weak — it is satisfiable by construction, and
the more carefully an author words their honest caveats, the more reliably it passes.

## 2. The fix: obligations that point at records

Replace the free-text check with **typed obligations**. A rung becomes reachable only when every
obligation required at or below it is `resolved`, and resolution is decided by comparing fields
across two separate files rather than by reading one field.

```yaml
claim:
  id: clm-0001
  revision: 3                    # bumped on any edit to the claim text
  owner_agent: theorist
  claim_type: empirical          # unchanged from the shipped enum
  status: untested               # unchanged from the shipped enum
  evidence:                      # kept for human context; the gate no longer reads it
    - "see experiment exp-0004"
  obligations:
    - kind: replication
      status: unresolved
      review_id: rev-0007
      required_for_rung: experiment_support
```

`kind` is one of: `replication`, `novelty`, `adversarial`, `baseline`, `formalization`, `safety`,
`data_lineage`.

`status` is one of: `unresolved`, `resolved`, `failed`, `waived`.

The `evidence` field stays, because human context is genuinely useful. What changes is that the
gate stops treating it as proof. A claim author may write whatever is true there; it moves no
rung.

## 3. Resolution rules

An obligation is `resolved` only when **all five** hold. Any one failing means unresolved, and
unresolved fails closed.

1. **The review exists.** `review_id` resolves to an actual review record on disk. A dangling ID
   is a failure, not a warning — this is the check that makes the whole scheme non-forgeable,
   because it is the one an author cannot satisfy by typing.
2. **The verdict accepts.** The review's `verdict` is in the accepting set for that obligation
   kind. A review that exists and says `reject` resolves nothing.
3. **Independence holds.** `review.author_role != claim.owner_agent`. A claim's own owner cannot
   discharge its obligations. Self-review is a schema error, not a weak result.
4. **The artifact matches**, for empirical kinds: the review's recorded artifact digest equals the
   digest of the frozen scoring harness the trial ran against. A review of a different harness
   than the one that produced the number is not a review of that number.
5. **The revision matches.** `review.claim_revision == claim.revision`.

Rule 5 is the one that does the most work over time, and it deserves its own statement: **editing
a claim's text after review auto-demotes it.** Bump `revision`, and every obligation whose review
cited the old revision stops matching. This mechanizes "downgrade fast" — it makes silent drift
between what was reviewed and what is claimed impossible rather than merely discouraged.

## 4. Waivers, and why they must be loud

`waived` exists because real work sometimes proceeds without a review that cannot be obtained.
Two conditions, both mandatory:

- The waiver carries a reference to a recorded human authorization. A waiver an agent granted
  itself is not a waiver.
- The waiver appears in **every** rollup and status report that shows the claim. It is never
  silently absorbed into a green count.

A waiver that does not show up in the summary is indistinguishable from a resolved obligation,
which recreates the original defect one level up.

## 5. The evidence ladder and its obligation matrix

The ladder is unchanged from `operating-model.md`:

```
idea -> conjecture -> small-case support -> experiment support -> replication support
     -> adversarially reviewed -> formally specified -> formally proved / robustly reproduced
```

What obligations each rung requires:

| Rung | Requires |
|---|---|
| idea, conjecture | Nothing. These are free, and saying so keeps the cheap rungs cheap. |
| small-case support | At least one recorded trial identifier. |
| experiment support | `baseline` resolved, plus at least one trial identifier. No improvement claim without a baseline and a variance figure. |
| replication support | `replication` resolved: two or more trials at the same commit whose difference falls within the recorded variance. |
| adversarially reviewed | `adversarial` resolved, by an independent author, against the matching harness digest and claim revision. |
| formally specified / proved | `formalization` resolved. |
| any rung, where the claim asserts novelty | `novelty` resolved, with a populated prior-art matrix. Default state is unknown novelty, never novel. |
| any rung, where the work touches data | `data_lineage` resolved. |
| any rung, where a probe has spend, credentials, network writes, or destructive effects | `safety` resolved. |

**Demotion triggers**, each of which drops the claim to the highest rung its remaining resolved
obligations support: the claim text is edited (revision mismatch); the harness digest changes; a
review is withdrawn or its verdict changes; a trial the claim rests on is found void; a
counterexample is recorded.

## 6. Independence is a field comparison, not a promise

The load-bearing property of this whole design is that independence is checked by **comparing two
recorded values**, not by asserting it in prose. `review.author_role != claim.owner_agent` is
either true or false in the files; no wording makes it more or less true.

That is what distinguishes this from the defect in §1. The original gate asked a question whose
answer the constrained party authored. This one asks a question whose answer requires a second
party to have written a second file.

Where a host cannot run separate agents and one agent plays several roles in sequence, the
comparison still functions — the roles are recorded per record, and the ordering is verifiable
after the fact (a review must cite trial identifiers that already exist). But the honest receipt
records that independence was **textual rather than structural**, and says which. Recording the
weaker form accurately is worth more than claiming the stronger one.

## 7. Gate results are evidence

Everything in this file produces evidence. A gate that reports all obligations resolved has
recorded that the required review records exist, come from independent authors, and match the
harness and revision. That is a finding about the ledger's internal consistency.

It is not authorization. No obligation state, rung, verdict, or clean gate run authorizes a merge,
publication, push, deployment, credential use, or queue mutation; each of those needs explicit
operation-specific human authorization. Work that outlives the loop departs as exactly one typed
`SeedProposal` for conductor triage.

Nor is a resolved obligation a claim that the underlying research is correct. It records that a
specific review happened, by someone else, against the right artifact. A rigorous process around
a wrong hypothesis still yields a wrong conclusion — the ladder measures evidential support, not
truth.

## 8. Built versus designed

Stated plainly so no reader mistakes this file for a description of shipped behaviour:

- **Shipped today:** the substring-matching gate in §1, the claim and review schemas in
  `install_research_os.py`, and its ownership and manifest semantics. The defect is live.
- **Designed here, not built:** the `obligations` block, the `revision` field, the five resolution
  rules, the waiver discipline, and the obligation matrix in §5. No generated file emits or
  enforces any of them yet.
- **The migration constraint:** the existing gate must keep running for already-installed target
  repositories, since their generated build files invoke it by name. Introduce obligation checking
  alongside it rather than replacing it in place, and where the two disagree, **report the
  disagreement as a first-class finding** rather than letting either silently win. The
  disagreement is the most informative output available during migration.
- **Ownership semantics are unchanged.** The installer's generator-owned manifest, its refusal to
  overwrite foreign files at generated paths, and its digest-based ownership tracking all continue
  to hold exactly as `operating-model.md` describes. Nothing in this design broadens ownership or
  adopts a foreign file.

## 9. The first claim this should be used on

The natural first subject is the defect in §1 — the machinery and the subject are the same thing,
so a weak gate cannot hide behind an unrelated topic.

The claim: *the shipped review gate can be satisfied by a claim's own author with no independent
review, because it substring-matches the author's free-text evidence.* Three probes settle it: the
exploit fixture from §1 against the current gate (predicted: passes, which is the defect); the
same fixture against obligation checking (predicted: fails, naming each unresolved obligation);
and a fixture whose review author equals the claim owner (predicted: obligation checking rejects,
current gate accepts).

**The falsification condition, which is what makes this honest:** if the exploit fixture *fails*
the current gate, the claim is falsified, the evidence stays recorded, and this redesign loses its
primary justification. Record that outcome; do not retry into agreement. As of the execution in
§1, the exploit passes — but that is one observation of one code path, and it is stated here as
what it is.
