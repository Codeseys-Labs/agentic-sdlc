# ADR-0021 — Distribute Agentic SDLC as a versioned mise release

- **Status:** proposed
- **Date:** 2026-08-15
- **Deciders:** operator (decision through the resolved Wayfinder review); agent (evidence and drafting)
- **Relates to:** `README.md`, `assets/launchers/ccodex.in`, `docs/plans/2026-08-14T163833Z-Install-UX.md`

## Context

The current operator CLI is a thin entry point into a required checkout
(`assets/launchers/ccodex.in:18-29`). `README.md:263-270` correctly states that the agreed versioned
mise release is not available because no release artifact exists. ADR-0011 therefore remains the
accepted current installation topology and explicitly requires a new superseding ADR only after an
archive builder, release workflow, copy activation, clean-host tests, and first release exist.

The operator has nevertheless selected the target topology: mise resolves a versioned release,
installs `ccodex`, and `ccodex sdlc` owns the Agentic SDLC lifecycle. Global acquisition remains
separate from repository activation, routing, companion libraries, trust, and provider setup.

## Considered options

- **Keep the managed checkout as the only operator installation.** Rejected as the target because
  daily use remains coupled to repository location and contributor tooling.
- **Use a self-updating standalone binary.** Rejected for the first release because it creates a
  second update authority before the receipt-backed lifecycle is proven.
- **Publish exact release artifacts resolved by mise.** Chosen because mise already owns version
  selection while the payload can keep explicit activation and recovery boundaries.

## Decision

1. The primary operator distribution is a versioned, self-contained release acquired and selected
   through mise. Source checkouts remain the customization, contribution, gate, and release-building
   plane.
2. The release installs one operator CLI, `ccodex`. Its `sdlc` namespace acquires, activates,
   inspects, updates, recovers, and removes Agentic SDLC-owned lifecycle state.
3. Installing `ccodex` does not activate a repository, trust configuration, install a companion
   library, configure a provider, start OCX, or launch Claude Code.
4. Stable and preview releases resolve to exact side-by-side identities. Update, downgrade,
   rollback, channel change, and removal are explicit receipt-backed operations. The first release
   has no self-updater.
5. Existing foreign or modified destinations are preserved and reported. Removal proves ownership
   and unchanged identity before deletion.

This record stays proposed until ADR-0011's own observable supersession condition fires. It is a
target decision for specification, not a claim that the release exists.

## Consequences

- Positive: operators receive a small versioned USE surface without carrying repository
  maintenance tasks on PATH.
- Positive: exact stable and preview identities make rollback and compatibility evidence
  reproducible.
- Negative: the release must package private runtime dependencies and copy or project activated
  payloads without depending on a prunable release root.
- Negative: the managed-checkout and release planes coexist, which increases lifecycle and test
  matrix cost.
- **Confirmation:** conformance is not currently mechanically checkable because the target release
  does not exist. The current review step is to compare this record with `README.md:263-270`,
  `assets/launchers/ccodex.in:18-29`, and ADR-0011; that review is why the status remains proposed.

## Relationships

| Relationship | ADR | Note |
|---|---|---|
| Depends-On | ADR-0002 | mise remains the operator-selected acquisition and version-resolution front door. |
| Supersedes | ADR-0011 | Once accepted after the named release evidence exists, the versioned artifact becomes primary while the managed checkout remains a contributor plane. |
| Relates-To | ADR-0009 | Companion-library lifecycle stays outside ordinary product acquisition and activation. |
| Part-Of | ADR-0028 | This proposed record decides future distribution topology inside the Claude Code-first product initiative. |

## Compliance

- `ccodex` installed from a release does not require the source checkout for ordinary USE commands.
- Install, repository activation, routed-model setup, companion libraries, and launch are separate operations.
- Ordinary commands never follow a moving release or update silently.
- Uninstall removes only unchanged lifecycle-owned entries and preserves all foreign state.

## Reversal condition

If clean-host evidence shows that mise cannot install and retain a self-contained exact release
without hidden checkout or update coupling, the distribution owner re-examines the release backend
before this record can become accepted.
