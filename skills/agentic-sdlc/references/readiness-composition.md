# Readiness composition

Pre-effect readiness is not one tool's job. It is a documented composition of three
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

## 2. `planning-snapshot.py capture` — observed repository state, with named unknowns

What it answers: the observed git-and-filesystem state of one repository at one instant,
sealed into a `agentic-sdlc/planning-snapshot@1` document with exactly one added key
(`digest`); any dimension it could not observe is named in `unknowns` rather than guessed
or silently omitted, and the head is re-read immediately before sealing so the document
names the head that was still current at seal time.

What it cannot answer: it observes no host or install state (that is doctor's dimension)
and decides nothing about whether a wave plan may proceed against what it captured — a
sealed snapshot is an observation, not a verdict.

## 3. `wave-plan-admission.py admit` — the wave-effect gate

What it answers: whether a sealed `WavePlan` is admitted against the caller-supplied
fresh planning snapshot and mission contract — issue 16's `admitted` lifecycle state,
distinct from the compiler's `compiled` state. Six of issue 16's eleven readiness
dimensions are decidable from the sealed documents it reads and run as checks; the
other five, plus six partial refinements of checks that do run, are named in the
report's own `deferred_dimensions` list rather than reported as met.

What it cannot answer: it observes no repository itself (freshness of the fresh
snapshot is the caller's claim, not something this tool verifies independently), calls
no model, resolves no runtime route, and reads no environment variable. `admitted` is
not `approved`: no dispatch, write, or other outward effect follows from an admission
report by itself.

## Standing sentence

A passing result from any of these three surfaces — `doctor`'s clean read, a sealed
planning snapshot, or an admitted wave-plan report — is evidence only. None of the three,
alone or composed, authorizes push, publication, PR mutation, merge, deployment,
credential change, or any other outward effect. Only an explicit, operation-specific
human or conductor authorization does that.

## No unified guard

`agentic-sdlc-9857` decided against building a fourth, unifying "readiness guard" tool
that would wrap or multiplex the three surfaces above. Readiness stays a documented
composition, read in the fixed order above, rather than a single verb. A multiplexer
would have no unique authority of its own: each dimension already has exactly one
surface that owns it, and a wrapper could only ever re-report what that surface already
says — the same one-capability-one-front-door argument that formally dropped the
`ccodex sdlc` profiles surface (`agentic-sdlc-c990`) rather than adding a generic verb
over state that already had a receipt-backed mutation path. Composing the three calls
above, in order, and reading `unknowns` and `deferred_dimensions` honestly, is the
readiness check; no additional tool sits over them.
