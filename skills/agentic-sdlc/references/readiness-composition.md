# Readiness composition

Pre-effect readiness is not one tool's job. It is a documented composition of two
surfaces, each owning exactly one dimension, read in this order.

## 1. `ccodex sdlc doctor` — host and install state

What it answers: whether this host's checkout-development ownership state (bundle
entries, operator-tools entries, checkout plane/version/certification claim) and this
run's runtime execution admission (interpreter identity and isolation) are legible and
consistent — read-only, without installing, updating, uninstalling, following, or
changing anything; `recover` stays proposal-only and requires the literal `--dry-run`
safeguard.

What it cannot answer: it observes no target repository's Git state, no Seeds queue, and
no wave plan or mission contract, so it cannot say whether a specific repository is
Git-wave ready or whether a specific wave effect may proceed.

## 2. The Git-anchored wave-effect read — `/sdlc-wave` step 8

What it answers: whether the wave's declared work is actually in the tree that was merged,
and whether the two authority conditions held. Four readings, each against something that
already exists: `git log --format='%H %s' <base>..<branch>` for what the node did,
`git show --stat <integration-commit>` for the declared outputs anchored to a commit, a
`scripts/gate_receipt.py` receipt produced on the MERGED head, and a two-line reading that
the reviewer is not the implementer and that the operator's dated approval precedes the
integration commit's committer date. The wave's own file under `docs/evidence/waves/`
records all four.

There is deliberately no sealed-document admission gate here. The tool family that once
held one (`wave-plan-compiler`, `wave-plan-admission`, `wave-journal`, `wave-verdict`,
`wave-submission`, `sdlc-observability-projection`) was removed by
`docs/adr/0030-record-wave-evidence-in-git-and-one-markdown-file.md`: it could not answer
whether its evidence described the tree as it is now, which is the one question this
dimension exists to answer, and Git answers it in one command. The sealed
planning-snapshot surface that once fed it is likewise gone: repository activation now
ends in reviewed diffs and Git history rather than a terminal-state document (ADR-0022
amendment), so this read has exactly the two anchors above — the host read and Git itself.

What it cannot answer: whether the merged tree is still the current head at the moment a
later effect runs, and whether the recorded approval was authentic rather than
self-minted. Both are properties of a live repository and a live operator, not of any
artifact a reader holds, and the second is the reason the no-self-review and
approval-before-fan-in rules live in `../SKILL.md` as rules rather than as a check the
audited party may decline to run.

## Standing sentence

A passing result from either of these surfaces — `doctor`'s clean read or a complete wave
evidence file — is evidence only. Neither one,
alone or composed, authorizes push, publication, PR mutation, merge, deployment,
credential change, or any other outward effect. Only an explicit, operation-specific
human or conductor authorization does that.

## No unified guard

`agentic-sdlc-9857` decided against building a unifying "readiness guard" tool
that would wrap or multiplex the surfaces above. Readiness stays a documented
composition, read in the fixed order above, rather than a single verb. A multiplexer
would have no unique authority of its own: each dimension already has exactly one
surface that owns it, and a wrapper could only ever re-report what that surface already
says — the same one-capability-one-front-door argument that formally dropped the
`ccodex sdlc` profiles surface (`agentic-sdlc-c990`) rather than adding a generic verb
over state that already had a receipt-backed mutation path. Composing the two reads
above, in order, and reading the wave file's blanks honestly, is the
readiness check; no additional tool sits over them.
