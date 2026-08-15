# Choose the canonical installation, update, and recovery experience

Type: prototype
Status: resolved
Blocked by: 01, 03, 05, 06, 07, 18
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What single Claude-first user journey should acquire, review, configure, update, diagnose, and
remove the harness while preserving its separate approval boundaries? Prototype the command and
interaction shape across the Claude plugin, managed distribution checkout, mise toolchain,
`ccodex`, provider setup, optional profiles, receipts, rollback, and offline status.

Asset: [throwaway installation-lifecycle prototype](../prototypes/install-lifecycle/README.md)

## Answer

The [installation-lifecycle prototype](../prototypes/install-lifecycle/README.md) validated one
packaged operator surface with separate approval planes.

### Product and command boundary

`ccodex` is the installable, self-contained operator CLI for this distribution. Agentic SDLC
remains the Claude Code plugin, workflows, skills, repository contract, and methodology.
`ccodex sdlc` owns Agentic SDLC lifecycle; ordinary `claude` runs the installed core with
subscription models; and `ccodex launch` runs the same core with qualified OCX routes plus those
subscription models.

Installing the CLI does not modify Claude, start OCX, configure a provider, activate an optional
profile, or install an external library.

### Canonical acquisition and activation

The primary path is an exact versioned GitHub release acquired and globally activated through
mise:

```text
mise use -g github:Codeseys-Labs/agentic-sdlc@<version>
ccodex sdlc inspect
ccodex sdlc doctor
ccodex sdlc install --host claude
```

The release contains `ccodex` and its private Agentic SDLC/runtime payload. `inspect` shows the
manifest, checksums, attestation, exact version, and payload. `doctor` is offline and read-only.
Claude activation is a separate approval that installs copied, receipt-owned entries from that
same release, so pruning an older mise version cannot break links.

Normal users need no source checkout or mise trust. A managed checkout remains the explicit
contributor/customization path and requires source review, per-path mise trust, and the locked
toolchain. A pre-existing Claude marketplace copy is preserved as a conflict and cannot coexist
with direct activation. Marketplace-only installation is not presented as the complete product
path because it lacks the operator lifecycle and private runtime payload.

Every host and scope is selected explicitly. Detection may suggest a value but never authorizes a
mutation, and there is no wildcard `--all` lifecycle operation.

### Routed execution and optional surfaces

The release includes the pinned private OCX runtime but does not start it. Provider configuration
uses an explicit `ccodex routes configure <provider>` operation through the provider's approved
credential flow. `ccodex routes status|qualify` exposes the control plane. Each `ccodex launch`
explicitly starts and uses the gateway for that session; ordinary `claude` never starts it.
`/sdlc-init` may detect and explain routing but cannot configure or launch it.

First-party optional capabilities use
`ccodex sdlc profiles list|status|plan|install|remove`. External companions use
`ccodex libraries list|status|plan|install|migrate` and their own front doors. Both require exact
names and disclose surface cost, destinations, collisions, egress, and mutations before approval.
External libraries never become owned profiles or uninstall dependencies.

### Update, rollback, diagnosis, and recovery

Mise alone acquires and selects CLI versions; the first release has no `ccodex` self-updater.
Versions install side by side. `ccodex sdlc status` distinguishes the selected distribution from
activated core/profile versions. After mise selects a new or previous version, the operator must
run `inspect` and `doctor`; `ccodex sdlc refresh` then changes only verified, unchanged owned
entries. Modified or foreign entries are preserved and block refresh. The prior receipt remains
available until the new activation completes durably.

`status` is always offline, read-only, and non-repairing. `doctor` checks payload identity, host
compatibility, receipts, activated versions, collisions, pending transitions, and required
commands without a network by default. Network or provider probes require explicit `--online`.
Recovery first produces a digest-bound plan; applying that exact plan requires separate approval.
Foreign, modified, ambiguous, or unknown-effect state is preserved. Interrupted operations resume
or roll back only from verified journal and receipt state.

### Removal

Optional profiles are removed before the core in explicit dependency order. Core uninstall
removes only verified, unchanged receipt-owned host entries. It never removes provider
credentials, Claude login, user settings, external libraries, repositories, Seeds, ADRs, work
artifacts, or repository hygiene. Removing the CLI/distribution is a separate mise operation after
owned activations are absent. The initial release has no broad `--purge`; final offline status
reports everything removed, preserved, or still requiring attention.

### `npx skills` inspiration boundary

From the [first-party CLI review](../research/npx-skills-cli-lifecycle.md), adapt bounded source
discovery, explicit selectors, a declarative host registry, canonical storage with host-specific
projections, deterministic intent, input sanitization, and granular diagnostics. Reject agent
detection as approval, wildcard mutation, presence-based overwrite/delete, mutable
non-transactional restore/update, false dry-run, ambient credential discovery, default telemetry,
and unapproved audit egress. `npx skills` is inspiration, not Agentic SDLC's lifecycle authority.
