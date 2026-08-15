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
