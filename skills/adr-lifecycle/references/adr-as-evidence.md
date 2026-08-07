# An accepted ADR is evidence, never authorization

Self-contained: where a decision record sits in this bundle's authority model, what its
Confirmation and Reversal Condition must contain to be worth anything, and the explicit
non-claims that keep a record from being mistaken for permission.

## The distinction

A decision record answers *what was decided, on what grounds, and at what cost*. That is
evidence: durable, citable, and useful precisely because it is fixed in time.

Authorization answers *may this effect happen now*. Outward effects — push, publication,
pull-request mutation, merge, deployment, release, credential use — each require explicit
operation-specific authorization from a human. Nothing about a record's content or status
supplies that.

The two are separate planes, and a record that blurs them is worse than no record, because it
gives a later agent a document that looks like a permission slip. Concretely: an `accepted`
status, a passing Confirmation command, a clean review verdict, and a complete relationship graph
are, all four together, still only evidence. They tell a conductor what is known. They do not
tell anyone that something may be shipped.

## What a conductor does with a record

An accepted record is something a conductor **cites** when adjudicating a later related proposal.
Its useful forms:

- *This was already decided, here, on these grounds* — which ends a re-derivation that would
  otherwise consume a session.
- *This option was examined and declined for this specific reason* — which is what `rejected`
  records are for, and the reason they are never deleted.
- *This decision is now suspect because its Reversal Condition fired* — which is the record
  actively earning its keep rather than sitting inert.

What a conductor does not do with a record: treat it as a gate result, treat it as a queue
operation, or treat its acceptance as clearance for the change that implements it.

## Naming affected work in the body

A decision usually blocks or unblocks other work. Record that **in the record's own body**, as
prose naming the affected item and what remains false while it is open. For example: "the
vendoring backlog items that need an attribution surface stay blocked until this record's
`NOTICE` structure exists."

This is a written statement of relationship, and it is the whole mechanism. The record does not
reach into any tracker, and no field anywhere is altered by the act of accepting a record. Where
a queue state should change as a consequence, that departs as exactly one typed `SeedProposal`
for conductor triage, and the conductor alone acts on it after verifying the evidence.

Two specific things a record must never do: assert that a tracked item is now finished because a
decision was accepted, and assert that acceptance discharged an obligation somewhere else. Both
are the same error — reading a record's status as an effect on state outside the record.

## Confirmation: what makes one real

Confirmation exists so a decision is checkable rather than merely stated. It is worth something
only if it names an artifact that exists today.

Real: `mise run check` — it exists and runs. A named review step someone actually performs. A
specific command whose output a reader can compare against the decision. An honest "conformance
is not mechanically checkable; enforced at review", which is a legitimate Confirmation because it
tells the reader exactly how much assurance there is.

Not real: a fitness function that would need to be written. A check that exists in another
repository. A gate that the decision itself proposes adding. A vague "CI will catch this". Each
of those describes a check rather than naming one, and a described check provides no assurance
while looking like it does.

**A passing Confirmation is evidence of conformance and nothing more.** It does not authorize the
change that conforms, and it is not a substitute for review. This matters most when the
Confirmation is a repository gate: a green gate in this bundle is explicitly evidence only.

## Compliance: assertions that survive being read alone

At Extended tier, Compliance lines are assertions phrased so a violation is visible to a reviewer
or a check with no other context. The test: hand one line to someone who has not read the record
and ask whether a given diff violates it. If they cannot tell, the line is a sentiment.

Good shape: a statement of a required state, in the present tense, about a named thing. Bad
shape: an aspiration ("code should be maintainable"), or a restatement of the Decision section in
different words.

## Reversal condition: the falsifiability hook

Every Standard-tier and above record names one observable event that would falsify it, and who
would see it. This is the single field that keeps a decision from becoming permanent policy by
default.

A reversal condition is well-formed when someone can answer "has this happened yet?" without
interpretation. "If a re-runnable per-change benchmark is built and measured for this bundle
specifically" is well-formed — the artifact either exists and has been measured, or it has not.
"If this turns out to be a problem" is not; nothing tells you whether it fired.

Calendar dates are not reversal conditions. "Revisit in six months" produces a review with no
criterion, which produces a rubber stamp. If time genuinely is the trigger, the condition is the
thing time was standing in for — say that instead.

When a reversal condition fires, the record does not automatically become wrong. It becomes
**due for re-examination**, which means a new record that either supersedes it or re-affirms it
with the new evidence recorded. Re-affirmation is a real and valuable outcome.

## Explicit non-claims

Stated plainly, because each of these has been assumed somewhere:

1. **An accepted record does not authorize the change that implements it.** The decision and the
   implementation are separately authorized. A record saying "we use X" does not permit the
   commit that adopts X to be pushed.
2. **An accepted record does not retroactively make existing non-conforming code compliant.**
   That gap is tracked work, cited against the record.
3. **A passing Confirmation is not authorization.** It is evidence of conformance at the moment
   it ran.
4. **A reviewer's verdict is not acceptance.** Acceptance needs the full bar in
   `lifecycle-states.md`, which includes a human decider.
5. **A record's acceptance is not a queue effect.** No tracker field changes because a record was
   accepted; a conductor acts on a proposal, having verified the evidence.
6. **A complete relationship graph and a green rollup are not progress.** They are summaries of
   recorded states.
7. **An agent drafting a record is not a decider.** The named human decides; the draft is
   evidence offered for that decision.

## Where the evidence class matters

A record's Context section will mix things that were verified here from things inherited from
elsewhere. Keep them distinguishable: cite verified facts by path, command, version, or
measurement, and mark inherited claims as inherited, naming the source. A record that presents an
inherited claim as a verified one has laundered its evidence class, and every decision that later
depends on it inherits the error invisibly.

Where a claim's evidence is missing altogether, omit the claim or leave an explicit placeholder.
Plausible prose in place of evidence is the failure this whole discipline exists to prevent — it
is indistinguishable from verified content to every future reader.
