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

## Amendment — 2026-08-26: one top-level verb family with explicit scope, and the grant unit is a plane

Ratified by the operator 2026-08-25 (gh #8, gh #11); executed by the agentic-sdlc-7a2b wave train and
recorded here at its close. The amendment text was drafted in
`docs/plans/2026-08-25-front-door-unification.md` §5 and lands verbatim on its two items, with one
item added for a semantic change §5 named but did not draft.

**The status stays `proposed`, deliberately.** gh #8 acceptance 2 asks for `accepted`, and that is
not this wave's to give: this record's own Decision section says it "stays proposed until ADR-0011's
own observable supersession condition fires", and the condition ADR-0011 states requires a **new
superseding ADR** rather than an edit — which no wave of this train wrote. So what changed is the
record's content, not its lifecycle state, and ADR-0028's registry and rollup are unaffected on the
axis they measure. Amending a proposed child is cheap for exactly the reason ADR-0028 states: "A
proposed child is not presented as a current product constraint."

**Item 2 is replaced.** The release installs one operator CLI, `ccodex`. The Agentic SDLC
lifecycle is owned by its **top-level** verbs — `install`, `status`, `update`, `uninstall`,
`doctor`, `recover` — with `--scope user|project` and `--agent claude|codex` required on the four
lifecycle verbs, no default and no wildcard. There is no `sdlc` and no `bundle` operator namespace:
both historical spellings are retained only as refusals naming the replacement invocation. Every
install seals an activation receipt; the receipt and pointer plane is keyed by
(agent, scope, root); project scope is copy-only. Acquisition, trust, bundle activation, settings
activation, and launch remain five distinct effects with five distinct grants.

**Item 4 is replaced.** Stable and preview releases resolve to exact side-by-side identities.
Update and removal are explicit receipt-backed operations selected per (agent, scope, root).
`downgrade`, `rollback`, and `channel change` are **not** operations of this lifecycle: rollback
is the operator selecting an earlier exact release through mise's side-by-side installs and then
running an explicit `update`; channel selection is version selection. A second mechanism for any
of the three would be the same "second update authority" this record already rejects for a
self-updater. The first release under this amendment still has no self-updater.

**Item 2's grant UNIT is a plane, not a file, and that is a loss this record owns rather than
absorbs.** The project-scope verb places the whole selected agent plane's payload set into
`<repo>/.claude/…` under one activation receipt, where the retired per-file workflows enabler
(`claude:workflows:activate`, deleted 2026-08-25) placed exactly one file per authorized command.
The doctrine is preserved at the operation level — enablement is still a separately authorized
per-repo step, reached by no gate, `lifecycle:*`, or setup path, with its own explicit selectors and
its own grant — and what is genuinely lost is per-entry granularity. A per-entry selection flag is
deliberately **not** designed in: there is no demonstrated need beyond the one shipped workflow, and
if one appears it is an additive flag rather than a schema change. The compensating control is
consent at the point of the wider grant: `commands/sdlc-init.md` was rewritten in the same wave so
the operator confirms they want the plane before the verb runs, because a command whose blast radius
grew from one file to one plane must ask a question the narrower one did not have to.

**Two citations in this record's own Context are now dead**, and are corrected here rather than
edited above, because the sentences are dated evidence about the tree as it stood on 2026-08-15:
`assets/launchers/ccodex.in` was deleted by gh #10 phase 4 along with the whole operator-tools PATH
plane, so its `:18-29` anchor and the `Relates to` entry naming it point at nothing. The surviving
statement of the same fact is `bin/ccodex`, which is committed, self-locating, and exposed directly
by mise's `github:` backend — which is what removed the reason a rendered launcher existed.
`README.md:263-270` has also moved with the release work; read the README's current install and
retirement sections instead of the anchor.

### Confirmation, restated

Conformance is now partly mechanical, where the 2026-08-15 text could only offer a review: the
top-level verb table and the retired spellings' refusals are pinned by
`tests/test_lifecycle_exit_conformance.py` and the subprocess-seam harness, the keyed pointer plane
and v2 receipt bodies by `tests/test_ccodex_sdlc_*`, and the whole-box store roster by
`tests/test_ccodex_sdlc_state_stores.py`. What remains a review rather than a test is the item this
record is really about — that a versioned release is the primary distribution — and that is what
keeps the status `proposed`.
