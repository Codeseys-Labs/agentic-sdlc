# Verify the current companion-library contracts

Type: research
Status: resolved
Blocked by: none
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

Using the current first-party repositories and published package metadata, what are the supported
installation, update, removal, licensing, namespace, runtime-dependency, and selection-surface
contracts of HyperResearch, Everything Claude Code, mattpocock/skills, and SimpleEnglish? Distinguish
facts this harness may safely automate from facts that require explicit operator choice or a new
onboarding decision.

Asset: `../research/companion-library-contracts.md`

## Answer

[Companion-library contracts](../research/companion-library-contracts.md) preserves the
own-front-door, explicit-operator lifecycle boundary. mattpocock/skills remains a reasonable
one-channel optional companion; ECC should use its Claude plugin while its documented npm setup
is unreleased; HyperResearch needs explicit profile/runtime choices and a bespoke rendered-file
removal plan. SimpleEnglish is a low-surface candidate, but adding it requires a separate closed-
catalog onboarding decision rather than silent inclusion.
