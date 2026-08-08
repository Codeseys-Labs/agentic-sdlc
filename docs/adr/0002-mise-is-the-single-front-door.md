# ADR-0002 — mise is the single front door; no second bootstrap prerequisite

- **Status:** accepted
- **Date:** 2026-08-06
- **Deciders:** operator (decision), agent (evidence and mechanism)
- **Relates to:** `skills/repo-toolchain-gates/SKILL.md`, `mise.toml`

## Context

`AGENTS.md` already states that "mise 2026.4.27+ is the only bootstrap
prerequisite," but that sentence had never been recorded as a decision with
its own enforcing evidence — it was assertable and, until this ADR, silently
re-litigable on every session that touched the toolchain. `mise` provisions
`uv`, `lefthook`, `node`, `bun`, and the pinned convenience tools; `uv` in turn
supplies Python 3.12.11 for every authoritative entrypoint
(`scripts/validate_bundle.py`, `scripts/install_skill_bundle.py`); and
`mise run check` is the byte-pinned authoritative gate
(`depends = ["validate", "test", "self-test", "secrets"]`). Every install,
gate, and task in this bundle is reachable from one tool.

The concrete incident that forced this decision to be explicit, rather than
merely convenient, is recorded in `skills/repo-toolchain-gates/SKILL.md` and
in `mise.toml`'s own inline comments: betterleaks is not in the mise tool
registry, so pinning it required naming a backend explicitly
(`[tools."github:betterleaks/betterleaks"]`). That backend's default behavior
calls the GitHub release API at install time to fetch SLSA provenance and
artifact attestations. Unauthenticated, that call is rate-limited to a hard
install failure — which would have made a `GITHUB_TOKEN` a second bootstrap
prerequisite alongside mise, silently, for anyone installing on a fresh
machine with no token in the environment. This was measured, not assumed:
`mise.toml`'s `[settings]` block sets `github.slsa = false` and
`github.github_attestations = false` specifically to keep that install path
credential-free, relying instead on the reviewed per-platform SHA-256
checksums already recorded in `mise.lock` as the integrity control.

An earlier revision of `repo-toolchain-gates/SKILL.md` had also claimed
betterleaks could not be pinned at all because it was absent from the mise
registry — corrected 2026-08-05: registry membership only supplies a default
backend, and any backend can be named explicitly. The generalized lesson kept
in that skill file: "not in the registry" is never by itself a reason a tool
stays unpinned; check `mise backends` first.

## Decision

1. **mise is the single front door for install, gates, and tasks.** No
   second bootstrap prerequisite (a second package manager, a required
   environment token, a required network credential, or — added by the
   2026-08-07 amendment below — a required system package) may be introduced by
   any tool pin, task, or hook in this bundle.
2. **A pin must not smuggle in a second prerequisite.** Before committing any
   new `[tools]` entry, the install path must be verified on a machine with
   no credentials in the environment. The betterleaks incident is the
   enforcing example: the fix was not to abandon the pin, but to disable the
   specific unauthenticated-API-call behavior (`github.slsa`,
   `github.github_attestations`) and substitute the checksum-based integrity
   control mise already provides via `mise.lock`.
3. **Registry absence is not a reason to leave a tool unpinned.** `github:`,
   `npm:`, and `http:` backends are all available to name explicitly; a tool
   "not in the registry" only lacks a *default* backend.
4. **Never fabricate a pin.** A version must be resolved from the real
   distribution and recorded as what was actually resolved. A tool that
   genuinely cannot be pinned is declared unpinned with the stated reason,
   never a placeholder number.

## Consequences

- Positive: one command (`mise run check`) is the authoritative gate on every
  host this bundle installs to; `AGENTS.md`'s bootstrap claim now has an
  enforcing test (`tests/test_gate_graph.py::test_betterleaks_is_pinned_locked_and_wired`)
  rather than only prose.
- Negative: every new external tool pin now carries a mandatory
  no-credentials-environment install check before it can be committed, which
  is friction against the alternative of accepting a "just export a token"
  shortcut. That friction is the point — it is what keeps the prerequisite
  count at one.
- Negative: `github.slsa = false` and `github.github_attestations = false`
  mean this bundle relies on reviewed checksums rather than live upstream
  attestation for that one tool. A repo that already provisions a token
  everywhere may reasonably choose the opposite trade-off; this bundle does
  not, because it must work with zero ambient credentials.
- **Confirmation:** run `mise run check` — the four-task dependency chain
  (`validate`, `test`, `self-test`, `secrets`) it enforces is a real command in
  this repository, not a hypothetical fitness function.

## Amendment — 2026-08-07: a pin's blast radius is the install command, not the gate

A second bootstrap prerequisite had already crept in under this ADR's nose, and
this record's silence is what let it stay. The decision above screens pins for
credentials and package managers; it never said anything about a **system
package**, so the reviewer who added `[tools."npm:@mermaid-js/mermaid-cli"]`
had no rule to fail.

**Evidence.** `docs/research/2026-08-07-clone-free-install.md` §4 records a
container run on `debian:13-slim` *without* `unzip`, where `mise --locked
install` exited **1** on both the first and the second run:

```
npm error Failed to set up chrome v151.0.7922.71!
npm error - DefaultProvider: Extraction failed: no zip archiver is available.
npm error   Install `unzip` ... or add the optional `yauzl` dependency.
mise ERROR Failed to install npm:@mermaid-js/mermaid-cli@11.16.0
```

This was **not** the npm-ordering bug that `depends = ["node"]` already fixed:
npm installed cleanly in the first pass and 12 of 13 tools resolved. It was
puppeteer's postinstall, pulled in transitively by the mermaid pin, requiring a
zip archiver the slim image lacks. Adding `unzip` took the same single run to
exit 0.

**The rule this implies.** An "advisory, gate-irrelevant" pin is a
contradiction in terms. `mise --locked install` installs every `[tools]` entry
in one operation, and one entry's failure exits the whole command non-zero — so
a pin's blast radius is the documented bootstrap command, not the gate graph.
Reasoning "no gate consumes `mmdc`, therefore this pin is advisory" measured the
wrong surface. Convenience tier describes what a tool's *absence* costs, never
what its *installation* can break.

**Fix taken: the pin was removed, not accommodated.** Two independent facts made
removal correct rather than a trade-off:

1. **It was redundant.** Nothing resolves `mmdc` through mise.
   `scripts/render_mermaid_linux.py` resolves the renderer out of this repo's own
   `node_modules/@mermaid-js/mermaid-cli`, provisioned by the explicit
   `mermaid:provision` step and digest-pinned via `MERMAID_PACKAGE_LOCK_SHA256`.
   `scripts/provision_mermaid_linux.py` calls `mise --no-config where` for
   exactly two tools — `node` and `npm` — and never for mermaid.
2. **It was actively harmful to provenance.** The removed pin resolved
   puppeteer **25.5.0** and downloaded chrome **151.0.7922.71** into
   `~/.cache/puppeteer`, while the reviewed supply chain pins puppeteer 25.3.0
   and browser build `150.0.7871.24` inside the repo-local
   `.mermaid-runtime/cache`. So the pin was writing an unreviewed 420MB tree,
   including a browser, outside every digest this repo checks. The provisioner
   avoids exactly this with `npm ci --ignore-scripts` and
   `PUPPETEER_SKIP_DOWNLOAD=1`; the mise pin had no such control available —
   mise exposes no setting to suppress npm install scripts (verified against
   `mise settings --all` on 2026.4.27).

Removing it therefore deletes the `unzip` dependency at its source, keeps the
renderer working unchanged, and makes this ADR's claim true again instead of
aspirational.

**How the next pin is screened.** Added to the decision as a fourth prerequisite
class: **a required system package**. Concretely — a pin whose install runs a
postinstall/preinstall script that extracts an archive or downloads a browser is
suspect and must be verified on a minimal image before it is committed, whatever
the gate graph says about it. Postinstall by itself is not disqualifying: the
retained `npm:@bitkyc08/opencodex` pin runs a transitive `bun` 1.3.14 postinstall
that lays down an 89MB binary, but it extracts using Node's built-in
`zlib.unzipSync` and so needs nothing mise did not already install. The
disqualifying property is **needing a tool mise does not provide**, not running
code at install time.

Enforcement is a named allowlist rather than prose:
`scripts/validate_bundle.py` fails the gate on any `npm:`-backend entry in
`mise.toml` absent from the reviewed `NPM_BACKED_TOOLS` set, and
`tests/test_gate_graph.py` pins both re-adding the mermaid pin and adding an
arbitrary unscreened npm pin as must-fail mutations. Stated honestly: that
enforcement catches an **unreviewed pin being added**; it does not detect an
already-reviewed pin's upstream growing a hostile postinstall in a later
version, and it does not execute an install on a minimal image. The
minimal-image check remains a human step this record mandates.

Note for the reader: `docs/adr/0011` records the `unzip` caveat as a live
operational requirement. As of this amendment that caveat is historical — the
cause is removed — and ADR-0011 needs a pointer here.

## Reversal condition

If a future required tool genuinely cannot be pinned without an authenticated
API call at install time — no unauthenticated backend exists, no checksum
substitute is possible — this ADR is superseded, not silently violated: the
new ADR must name the tool, the exact API dependency, and the credential it
requires as a second bootstrap prerequisite.

This record is evidence for a conductor to cite; it authorizes no push,
publication, or other outward effect on its own.
