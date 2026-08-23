# ADR-0023 — Adopt one evidence-preserving documentation profile

- **Status:** accepted
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `output-styles/bluf.md`, `skills/change-writing/references/technical-writing-clarity.md`, `NOTICE`

## Context

Human-to-agent, agent-to-human, and agent-to-agent work must remain concise enough to act on and
specific enough to audit. The repository already ships a BLUF output style and a countable-clarity
reference based on publicly supportable ASD-STE100 rule shapes. The latter correctly excludes the
licensed dictionary and rejects compliance, conformance, and certification claims. Separate or
duplicated writing skills would create overlapping selectors and drifting rule surfaces.

The operator also selected nearby evidence pointers, purposeful diagrams, independent review for
high-consequence documents, and a narrow re-expression of five SimpleEnglish ideas rather than a
vendored companion.

## Considered options

- **Let each role choose its own prose style.** Rejected because verdicts, handoffs, and procedures
  become inconsistent and harder to parse across workflow stages.
- **Vendor SimpleEnglish or reproduce the full ASD-STE100 standard.** Rejected because it duplicates
  the current profile, imports foreign lifecycle/licence obligations, and could imply unsupported
  conformity.
- **Maintain one first-party BLUF and countable-clarity profile with traceable claims.** Chosen
  because it improves actionability while preserving technical meaning and evidence strength.

## Decision

1. Human-facing and workflow-handoff prose leads with the outcome, decision, failure, or requested
   action, then includes only the evidence needed to act.
2. New or materially revised prose uses the repository's countable sentence, paragraph, noun-
   cluster, instruction, voice, list, and terminology checks without changing claim strength.
3. Five SimpleEnglish ideas enter as a narrow first-party adaptation with exact donor notice:
   condition-first commands, explicit referents, direct verbs, punctuation and abbreviation audit
   flags, and located meaning-preserving rewrite candidates.
4. Substantive claims carry an evidence class and nearby recoverable source pointer. Provenance
   never becomes correctness or authority.
5. A different role reviews high-consequence documentation for clarity and evidence preservation.
6. Prose tooling remains advisory unless a target repository explicitly promotes a proven subset.
   No score establishes technical correctness or writing quality.

This decision unblocks a single documentation role and review contract. It does not authorize
automatic brownfield rewrites or claims of ASD-STE100 conformance.

## Consequences

- Positive: human and machine handoffs share a short, predictable verdict shape.
- Positive: documentation improvements preserve evidence strength instead of polishing uncertainty
  into confidence.
- Negative: authors must perform countable audits and terminology checks that add time to
  high-consequence documents.
- Negative: the profile cannot offer a full controlled vocabulary without licensed material and a
  project term list.
- **Confirmation:** run `mise run check`, the writing-profile tests, and an independent
  documentation review. The current gate does not judge factual correctness.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Refines | ADR-0001 | Re-expressed foreign ideas require exact donor attribution without vendoring donor bytes. |
| Relates-To | ADR-0008 | Foreign libraries remain upstream; adapted ideas enter only through the established NOTICE path. |
| Depends-On | ADR-0019 | A document, review, or cited claim remains evidence and never authorizes an effect. |
| Part-Of | ADR-0028 | This record decides the documentation profile inside the Claude Code-first product initiative. |

## Compliance

- Owned handoffs place the bottom line in the first stable summary field or sentence.
- Clarity edits preserve technical meaning, uncertainty, and evidence strength.
- No owned surface claims ASD-STE100 compliance, certification, conformance, or a reconstructed dictionary.
- A high-consequence document is not authored and accepted solely by the same role.

## Reversal condition

If independent review identifies meaning changed by a mandatory profile rewrite in two accepted
product artifacts, the documentation owner re-examines the failing rule subset and its application
boundary.
