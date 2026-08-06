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
   environment token, a required network credential) may be introduced by
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

## Reversal condition

If a future required tool genuinely cannot be pinned without an authenticated
API call at install time — no unauthenticated backend exists, no checksum
substitute is possible — this ADR is superseded, not silently violated: the
new ADR must name the tool, the exact API dependency, and the credential it
requires as a second bootstrap prerequisite.

This record is evidence for a conductor to cite; it authorizes no push,
publication, or other outward effect on its own.
