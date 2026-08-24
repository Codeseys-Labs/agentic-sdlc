# STRIDE lenses over one scoped subject

Read this reference when running the lens pass of `sdlc-threat-model`. STRIDE — spoofing,
tampering, repudiation, information disclosure, denial of service, elevation of privilege — is
Microsoft's threat-classification method, re-expressed here against this repository's own trust
boundaries; no foreign text is copied. Each lens below states what the letter means for the
kinds of boundaries this bundle actually has, a worked example anchored in a named,
already-documented residual window, and the question the lens asks of any subject. The worked
examples exist so a first run has calibrated instances rather than textbook prose: each one is
a residual the repository's doctrine *names and accepts* — the honest shape a finding takes
when a window cannot be closed — not an open defect to re-report.

## The scope rule

Everything below assumes the run already bound exactly one subject — one diff, one subsystem,
or one trust boundary — as an immutable snapshot, with the producer, lens actor, date, and
budget recorded. Lenses fire per subject element, never per repository. Every subject
element × lens pair ends in exactly one of: `applicable`, `not_applicable` with rationale,
`deferred` with owner and re-entry trigger, or `out_of_scope` citing the approved boundary. A
missing pair is `not_evaluated` and blocks any coverage claim; `no_threat_identified` states
only that this run found none. Claims in a finding carry one of the five evidence classes from
the `agentic-sdlc` skill's evidence-discipline reference: `primary-artifact`, `primary-claim`,
`vendor-doc`, `author-claim`, `community-report`, sub-classing partial retrievals.

## S — Spoofing: which names are resolved rather than bound?

In this bundle the identities that matter are tool and model identities more than user logins.
Anything looked up by *name* at use time — a binary on PATH, a provider id in a catalog, a key
in a config document — is an impersonation surface for whoever can write ahead of the resolver.

**Worked example — the jq/mise substitution residual (ADR-0020, recorded in AGENTS.md).**
`ccodex`'s launch refusals depend on a `jq` parse of settings documents adjacent to
credentials, so a direct source-checkout launch never looks up a `jq` NAME: it resolves through
the pinned `mise -C <root> exec -- jq` route, and `$AGENTIC_SDLC_JQ` is admitted only as an
absolute path or the literal pinned sentinel. The residual is stated rather than hidden: that
pinned route locates `mise` itself on PATH, because mise is the documented sole bootstrap
prerequisite and is not itself pinned — so a substituted `mise` governs that parse exactly as
it governs `ocx`, and a substituted `jq` answering "clean" would suppress every settings
refusal. One name was bound; the name in front of it stayed resolved, and the doctrine says so.

**Same lens, model identity.** A `RuntimeAssignment`'s `resolved_model_id` requires verified
readback precisely because a gateway *claiming* an identity is a spoofing surface: requested
values never become readback, and a healthy launch is not model-identity evidence.

**The lens question.** Enumerate every name the subject resolves at use time — PATH lookups,
provider and model ids, config keys, registry and package names — and for each one ask: who can
write ahead of the resolver, and what does the system believe after they do?

## T — Tampering: what invariant holds inside each multi-step mutation?

Integrity checks run at a point in time; mutations take intervals. The lens looks for the
interval between check and use, and between the steps of any write sequence, and asks which
same-UID actor — including a crash — can interleave there.

**Worked example — the Seeds receipt's same-UID TOCTOU window (AGENTS.md).** The launcher's
receipt "detects ordinary drift, not a same-UID TOCTOU racer": hashes are checked at admission
and the exact Bun/entry is executed after, so a same-UID process can swap the bytes in the
interval. The doctrine accepts and names the window rather than claiming to close it — the
honest form of a tampering finding whose mitigation is out of reach.

**Worked example — the rename-aside interval (AGENTS.md installer doctrine).** A copy-mode tree
swap is a rename-aside *pair*, not one atomic replace, so an interruption inside it can park
the previous tree in a named `.<name>.old-*` sibling; every such leftover is named in the
report for the operator and never deleted on their behalf, and staged copy content is
process-crash consistent rather than power-loss durable. Here the interleaving actor is a
crash, not an attacker, but the lens is identical: the invariant is suspended mid-sequence, and
the design's honesty is to name the interval and report leftovers instead of guessing.

**The lens question.** For every write sequence crossing the subject boundary, state the
invariant at each intermediate step, name the interval between each check and its use, and name
which same-UID actor (attacker, concurrent process, or crash) could interleave there.

## R — Repudiation: can a dispute be decided from artifacts alone?

The canonical statement is the receipt-vs-control rule in the `agentic-sdlc` skill's
evidence-discipline reference: a receipt writable by the same actor as the mechanism it attests
is forgeable by construction, and the fix is to *remove* the self-declared field — never to add
a second field forgeable the same way.

**Worked examples.** The bootstrap receipt lands under `XDG_STATE_HOME` *outside the clone*, so
the clone cannot rewrite its own provenance. ADR-0030 moved wave evidence into git history — an
append-only store a worker cannot quietly rewrite. And the credential-URL refusal in the
bootstrap script is ordered to land *before* the line that would have echoed the remote,
preserving the record without leaking the value it records.

**The lens question.** For each mutation on the subject boundary, name who writes the record of
it, whether the mutator can rewrite that record, and whether a later reader could reconstruct
what happened without trusting any single agent's prose.

## I — Information disclosure: enumerate the sinks, then check the ordering

Secrets rarely leak through the channel that was guarded; they leak through the second sink
nobody enumerated — the receipt, the argv, the error text, the cache. The lens is an
enumeration followed by an ordering check.

**Worked example — the userinfo channel (bootstrap script, AGENTS.md).** A `--remote` URL's
userinfo is a credential channel that *every consumer keeps*: stdout, the receipt, Git's argv,
the clone's config. The refusal therefore names the option and fires before the value reaches
any of them; and where an existing origin must be READ to detect a credential, the value is
inspected but never echoed — the refusal lands before the line that would have printed it.

**Worked example — selective inheritance (ADR-0010).** The muse-claude plane inherits only the
global `statusLine` stanza and deliberately not the `env` block, because `env` can carry a live
credential and copying it would also re-point the child off its verified route.

**Worked example — the scan surface as a boundary.** The secrets gate selects tracked plus
nonignored untracked files and refuses symlinks and any selected path beneath a symlinked
parent rather than following them outside the repository: the scanner's own traversal is a
disclosure surface, bounded by refusal.

**The lens question.** List every sink a secret-adjacent value on the subject can reach —
output, receipts, argv, configs, error text, caches — and verify the ordering: the refusal
fires before the first sink, not after the value has already landed in one.

## D — Denial of service: budgets, ceilings, and designed refusal versus exhaustion

Availability threats in an agentic repository come in two shapes: resource exhaustion (often
self-inflicted) and controls so miscalibrated they deny their own surface. The lens also has to
tell *designed* unavailability apart from accidental unavailability, because this doctrine uses
fail-closed refusals deliberately.

**Worked example — the Mermaid ceilings (ADR-0006, `policy/mermaid-renderer-linux-v1.json`).**
`max_rss_bytes` and the `RLIMIT_FSIZE`-applied `max_output_file_bytes` are
resource-availability ceilings calibrated to the pinned browser, not output-size controls, and
the recorded failure runs in the self-inflicted direction: retightening `max_output_file_bytes`
toward an SVG-shaped number kills the browser mid-session as an opaque puppeteer
`Connection closed`. A control misclassified as an output bound becomes a DoS of one's own
surface — which is why the doctrine says a browser pin bump re-opens both calibrations:
re-measure rather than assume. SVG size is bounded independently, at the right layer.

**Operational sibling.** One unbounded whole-disk search has exhausted a host's RAM in this
project's recorded history: fan-out without a bounded search surface is the characteristic
agentic DoS shape, and every dispatched worker's search surface is bounded for that reason.

**Designed refusal is not an outage.** `MISE_PARANOID=1` failing closed until explicit trust
and a launch refusing at exit 3 are deliberate unavailability with a name and a remedy; a hang
or an opaque crash is not. The two must be distinguishable to an operator reading the output.

**The lens question.** Does every loop, fan-out, render, and retry on the subject carry a
budget and a stop condition; is every ceiling calibrated against a measurement rather than an
assumption; and is each deliberate refusal distinguishable from a hang?

## E — Elevation of privilege: can evidence be spent as authorization?

In this repository, privilege means authority for outward effects — push, publication, PR
mutation, merge, deployment, credential use. The canonical elevation is not a setuid binary; it
is a green gate, a reviewer verdict, or a conductor record leaking into that authority. The
doctrine repeats the boundary at every layer: a passing gate is evidence only, and no local
status, gate, reviewer label, or conductor choice grants authority for an outward effect.

**Worked examples.** A first `--yolo` is an explicit, wrapper-consumed unsafe opt-in to one
permission bypass that deliberately does *not* weaken the gateway-health or billing-honesty
refusals — privilege boundaries compose rather than inherit, and consent to one is not consent
to the next. Git hooks are best-effort convenience, never release authority. And this skill's
own output contract is the same rule applied to itself: a findings report, however severe,
authorizes nothing, and the human-only disposition gate exists so that no agent's drafted
disposition becomes a risk acceptance by transcription.

**The lens question.** Trace each verdict, receipt, gate result, or status the subject produces
to every effect it could later be cited for, and confirm that an authorization step exists at
each such effect that no agent can perform.

## After the lenses

Findings, coverage rows, and the structured submission follow the output contract in
`SKILL.md`. Six lenses run to completion are still one run on one snapshot on one date: they
support the coverage table's rows, never a security-completeness claim.
