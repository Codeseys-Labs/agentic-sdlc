# Define the first user and first successful journey

Type: grilling
Status: resolved
Blocked by: none
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Who is the first user this harness is opinionated for, what problem brings that user to it, and
what exact install-to-reviewed-result journey must succeed before the product can claim value?
Set one primary persona, one starting state, one observable outcome, and explicit non-goals.

## Answer

The primary user is an experienced solo developer or small-team technical lead who already uses
a paid Claude Code account on real Git repositories, wants access to multiple model providers,
and values rigorous multi-session delivery without assembling and maintaining the harness.

The starting repository may be greenfield or brownfield. `/sdlc-init` is the repository entry
point: for greenfield work it installs and validates the opinionated repository tooling; for
brownfield work it assesses the existing condition, establishes a baseline, and plans iterative
hygiene waves rather than demanding an immediate full cleanup.

The minimum successful journey is: install Agentic SDLC, activate the repository with
`/sdlc-init`, then complete one reviewed work wave under its admitted gate contract, with traceable
decisions and durable follow-up work. For a greenfield repository that first wave establishes the
tooling and reaches write-ready. For a brownfield repository it may complete the first prioritized
remediation slice with a `remediation-progress` verdict while honestly remaining short of global
write-readiness. This follows an
orientation-to-triage-to-incremental-improvement progression rather than treating setup as the
whole product value.

The first journey does not require complete brownfield cleanup, installation of optional
companion libraries, support for every provider, feature parity on companion hosts, automatic
commit/push/PR/merge actions, or proof of the entire long-running SDLC lifecycle in one session.

**Spec-alignment decision, 2026-08-24.** The minimum journey above abbreviates the primary
acceptance seam of the [product specification](../agentic-sdlc-product-spec.md), and that seam is
authoritative for what completing it means: acquire the release, inspect it, activate Claude,
activate the repository, compile a plan, approve and run one native-Claude wave, review, authorized
fan-in, and a terminal receipt (Implementation Decision 3, whose greenfield and brownfield variants
share that seam). Establishing the tooling on a greenfield repository and finishing the first
prioritized remediation slice on a brownfield one are intermediate milestones inside that seam, not
alternative places to declare success: the greenfield journey must reach a reviewed activation
commit and one accepted Core wave, while the brownfield journey may land with named remediation
Seeds and a non-worsening `remediation-progress` wave (Testing Decision 4).

The `write-ready` and `write-readiness` naming in this answer is historical. ADR-0022 as amended
2026-08-22 retired the write-ready/remediation-ready terminal vocabulary, and Implementation
Decisions 12 and 17 carry that retirement; bounded hygiene work is tracked as Seeds instead.
Complete brownfield write-readiness in the first successful journey stays out of scope, so the
terminal state of that first wave is one of the six wave outcomes (Implementation Decision 61) —
an honest `accepted` or an intended `remediation-progress` for a journey that succeeds — rather
than a readiness label.
