# ADR-0001 — MIT license, with a root NOTICE as the attribution ledger

- **Status:** accepted
- **Date:** 2026-08-06
- **Deciders:** operator (decision), agent (evidence and drafting)
- **Relates to:** the vendoring backlog blocked on this decision (see Context)

## Context

`.claude-plugin/plugin.json` already declares `"license": "MIT"`, and a root
`LICENSE` carrying the standard MIT grant exists in this working tree. Neither
fact was ever recorded as a decision — both simply appeared. Meanwhile
`docs/research/2026-08-05-vendoring-install-ux-memo.md` §4 found the missing
half of the picture: **"this repo has no `LICENSE`/`NOTICE` and declares
`"license": "UNLICENSED"`, so attribution has nowhere to land yet. That is the
real prerequisite"** for landing any near-verbatim MIT-licensed material from
the mattpocock skills library or ECC (`affaan-m/ECC`). That memo's backlog
items #7–#10 and #13 (TDD reference, debugging-loop, code-review two-axis
material, merge-conflict discipline, git-guardrails hook) are each MIT-derived
and each blocked until an attribution surface exists.

The sibling `pi-lab` repository already answered this question for itself: its
root `NOTICE` file (added 2026-08-03, "a new precedent in this repository")
records, per donor, the upstream repository, the exact commit pinned, the full
MIT permission notice reproduced verbatim, and — separately from the license
question — who actually originated the idea being carried across. Its own
stated rule: *"a permissive licence settles whether text may be reused. It
says nothing about who thought of the thing."* That structure is sound and
this bundle should not reinvent a different one.

## Decision

1. **This repository's license is MIT**, matching the already-declared
   manifest value. This ADR is the decision record for that fact; it does not
   itself create `LICENSE` — that file is landed by a parallel, separately
   tracked change.
2. **A root `NOTICE` file is the attribution ledger**, structured after
   pi-lab's precedent: one entry per donor, naming the exact repository, the
   commit or release pinned, the license and its required permission-notice
   text reproduced verbatim, what was copied vs. paraphrased vs. reimplemented,
   and — as a distinct field — who originated the underlying idea when the
   donor itself names a further upstream source. `NOTICE` is landed by the
   same parallel change that adds `LICENSE`; this ADR authorizes neither file's
   content, only the shape both must take once written.
3. **Idea-origin and copyright-holder are answered separately in every entry.**
   A donor's MIT grant settles reuse of its text; it never settles who first
   had the idea. An entry that conflates the two is non-conforming.

## Consequences

- Backlog items gated on "no attribution surface exists" become unblocked once
  `NOTICE` lands with a conforming entry for each donor whose material is
  actually carried across — this ADR does not itself unblock them; the NOTICE
  entry per donor does.
- Every future near-verbatim MIT reuse must add one `NOTICE` entry in the same
  commit as the vendored content, mirroring pi-lab's own house rule ("adding a
  donor to this file" checklist).
- `NOTICE` is prose, not code; it carries no gate dependency and must not be
  wired into `mise run check` as a new requirement — this ADR does not create
  a second bootstrap or gate prerequisite.
- **Confirmation:** the eventual `LICENSE` + `NOTICE` pair should be checked by
  running `mise run check` (the repository's authoritative gate) and observing
  no new error class from `scripts/validate_bundle.py`'s secrets/policy scan
  over the new files.

## Reversal condition

If the bundle's license is ever changed away from MIT, or if a donor's grant
is later found incompatible with continued reuse, this ADR is superseded, not
edited — a new ADR records the change and updates `NOTICE` accordingly.

This record is evidence for a conductor to cite; it authorizes no push,
publication, license change, or other outward effect on its own.
