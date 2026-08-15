# Define the branding, positioning, and compatibility promise

Type: grilling
Status: resolved
Blocked by: 01, 03, 05, 06, 08
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

How should the product name and describe itself relative to Claude Code, gstack, oh-my-* harnesses,
and partner libraries? Set the supported Claude Code versions, platform and host tiers, stability
levels, deprecation policy, release channels, and claims the documentation must avoid.

## Decisions

### Brand architecture and canonical descriptor

The product and methodology are named **Agentic SDLC**. Its canonical short descriptor is:
“A Claude Code-first, evidence-driven SDLC harness for greenfield and brownfield repositories.”
Longer descriptions may say that it adds opinionated repository activation and hygiene, bounded
Dynamic Workflow execution, model rightsizing and optional routing, durable evidence, and explicit
human authority boundaries. They must not turn those components into a claim that every installed
repository, model, route, platform, or companion is automatically ready or supported.

**Agentic SDLC Core** is the native-Claude product path. After separately approved activation, it
runs through ordinary Claude Code and the operator's own Claude account without requiring OCX, an
external provider, or a companion library. “Core” names the sufficient first journey and owned
workflow contract, not a deliberately crippled edition or every first-party optional capability.

**`ccodex`** is the installable operator CLI and distribution front door, not a second product
brand. Its `sdlc` namespace acquires, activates, inspects, updates, recovers, and removes Agentic
SDLC-owned lifecycle state; its route and launch surfaces control the optional routed-model
profile. Installing `ccodex` alone neither activates the core nor starts or configures a gateway.

The canonical optional term is **routed-model profile**. It uses `ccodex` with the OCX gateway to
make exact qualified routes available to the same Agentic SDLC core. OCX is the gateway dependency
and route implementation, not the product, an owned provider, or a universal compatibility
promise. “Multi-provider” always means the published exact-route contract, never every provider or
model an upstream catalog happens to expose.

External skill and agent catalogs are **companion libraries**. They remain outside Agentic SDLC
ownership and distribution, install only on explicit request through their own front doors, and
retain their own names, licences, support, update, and removal contracts. First-party adaptations
of ideas are separately attributed work and do not make the donor library bundled or endorsed.

Other hosts are **companion hosts**: they may consume portable skills and shared contracts where
current capabilities prove them, but receive no equal-parity promise with Claude Code Dynamic
Workflows. gstack, oh-my-* projects, and everything-claude-code are category comparisons for an
opinionated installable harness or optional library ecosystem only. Documentation claims no API,
configuration, lifecycle, plugin, command, format, or behavioral compatibility; endorsement;
lineage; replacement; or migration path unless separately verified and published.

Agentic SDLC is not described as an official Anthropic or Claude Code product, a Claude Code
replacement, a provider of models or credentials, a universal model gateway, a generic autonomous
agent runtime, or a guarantee that installed agents will complete arbitrary work. Product prose
names Anthropic, Claude Code, OCX/OpenCodex, providers, and companion projects as independent
parties and keeps support evidence attached to exact versions and surfaces.

### Compatibility requirements, exact evidence tuples, and support tiers

The compatibility matrix certifies exact tuples, not brands or broad platform names. A tuple binds
the Agentic SDLC release and manifest digest; host and exact version; OS, architecture, and relevant
runtime boundary such as native or WSL; acquisition and activation plane; capability-canary
identity; and the exact optional profile plus dependency versions when selected. Core, routed
models, operator tools/statusline, Mermaid and draw.io rendering, Research OS, and companion-host
adapters have independent rows and cannot inherit one another's support state.

Every row has one tier. `certified` means the published complete journey, offline gates, and
required live host/profile canaries pass for that exact tuple. `capability-qualified` means named
portable skills or contracts passed their bounded capability checks but full Claude Code feature
parity is not promised. `experimental` is an explicit opt-in with known missing evidence or
controls and no ordinary release-support promise. `unsupported` makes no operational claim and
causes safety-dependent actions to fail closed; read-only status and diagnostics may still explain
the blocker.

Operational Claude Code compatibility is governed by published minimum requirements plus current
capability admission, not an exact-version allowlist. Agentic SDLC Core requires at least Claude
Code `2.1.154`, the documented Dynamic Workflows introduction point. An optional profile may name a
higher minimum when it depends on a later host behavior. Meeting a minimum makes the host eligible
for assessment; it does not prove the required capabilities, support tier, route, or successful
journey.

A host at or above the applicable minimum is not refused merely because its exact version is newer
or absent from the certification table. Before safety-dependent use, the product records `claude
--version` and runs the versioned capability checks required by the selected core/profile. A pass
may admit that local tuple as `capability-qualified`; a complete published journey and reviewed
canary evidence are still required for `certified`. Failure blocks only the capability-dependent
surface and reports the missing behavior. A version below the applicable minimum cannot execute
that surface, while read-only diagnosis and independently portable contracts may remain usable.

Exact versions remain tested reference points and regression evidence. Each release tests the
current stable-channel nomination and, when feasible, the current latest-channel nomination plus
other high-value boundary versions. A successful exact row does not create a maximum version, and
a failing or vulnerable version may be denied by a separately evidenced exclusion. Agentic SDLC
sets no general Claude Code maximum unless a known incompatibility or safety defect justifies one.

Linux x64 and WSL2 Linux x64 are the first full-tuple certification targets. WSL remains a Linux
runtime row with separately named Windows interop exclusions; it is not evidence for native
Windows. macOS and native Windows earn certified rows only after their own installation,
lifecycle, filesystem identity/durability, credential-front-door, Dynamic Workflow, pause/resume,
and optional-profile canaries pass. Official vendor platform support is an input to eligibility,
not proof that Agentic SDLC certified that platform.

Every published row includes first-supported and last-verified Agentic SDLC releases, exact test
and canary identities, verification date, known exclusions, and downgrade/failure behavior. A
runtime capability canary may admit the current local session under an already published policy,
but a private one-off result does not silently edit the public matrix. Adding or promoting a row
requires reviewed evidence in a release change; removal follows the deprecation policy rather than
quiet disappearance unless an emergency safety issue requires immediate refusal.

Documentation avoids “cross-platform,” “works on Claude Code,” “supports Windows/macOS/Linux,”
“always compatible with latest,” and equal-parity claims without the exact tuple or a direct matrix
link. Current vendor versions, platform requirements, and update-channel facts must be refreshed
from primary sources before each release; dated research is nomination evidence, not permanent
compatibility truth.

### Initial minimum and reference-version nominations

The first Core compatibility requirement is Claude Code `>=2.1.154` with Dynamic Workflows
effectively enabled and the selected runtime's required workflow, permission, artifact, agent,
pause/resume, and stop behaviors passing their capability canaries. `>=2.1.154` is a minimum
eligibility statement, not a promise that every later release behaves identically. Later
behavior-specific floors belong to the optional profile that needs them rather than silently
raising unrelated Core requirements.

The primary-source snapshot dated 2026-08-15 nominates `2.1.224` from Anthropic's `stable` channel
and `2.1.233` from `latest` as exact reference versions. The first full certification tranche
tests Agentic SDLC Core with the operator's native Claude subscription on Linux x64 and WSL2 Linux
x64 through the native Linux installer. The stable nomination is the primary release reference;
the latest nomination is the preview/regression reference. Neither is a hard compatibility ceiling
or a certification until the full tuple passes.

macOS, ARM64, native Windows, WSL1, musl Linux, alternative Claude installation planes, and the
routed-model profile remain separate candidates. Official vendor eligibility does not promote
them. Native Windows and WSL1 require distinct treatment because their documented sandbox boundary
differs from WSL2. npm installation is not a first-tranche target because Anthropic marks that
installation path deprecated.

The release process re-resolves the moving `stable` and `latest` channel values immediately before
testing and records the exact version before canary execution and in the terminal receipt. A
mid-run version change invalidates the canary. Channel movement creates a new regression candidate,
not a reason to reject an already compatible newer runtime or to rewrite prior evidence.

### Release channels, versioning, and deprecation

Agentic SDLC publishes two public channels: `stable` and `preview`. A source checkout, branch,
commit, or locally modified distribution is a development build, not a third supported channel.
Every channel selection resolves to an exact release identity and digest through mise; no task,
launcher, status check, or ordinary command silently follows a moving tag, switches channels, or
updates an installed distribution.

`stable` requires the complete core release gate, a migration/recovery story, and at least one
current certified primary compatibility tuple. Stable defaults contain no experimental profile or
permission bypass. `preview` is explicit opt-in for release candidates or incomplete optional
profiles, installs side by side, keeps separate ownership receipts and support labels, and cannot
overwrite or migrate stable-owned state without a new reviewed plan and approval. “Experimental”
is a support tier within a release, not another channel.

Public Agentic SDLC releases, CLI commands and flags, manifests, configuration, machine envelopes,
receipts, and checked-in policy schemas use Semantic Versioning. Each artifact also carries its own
schema version where independent compatibility is required; the product version cannot substitute
for that schema identity. Release notes name added, changed, deprecated, removed, security-blocked,
and migrated surfaces plus compatibility-matrix changes and known evidence gaps.

A stable command, flag, configuration field, artifact shape, or behavior receives at least one
feature-release deprecation window with a visible warning, documented replacement, dry-run or
read-only migration preview where state is involved, and explicit removal release. Stable readers
retain read-only compatibility for the prior two stable schema generations. Compatibility may be
longer when retained evidence or recovery depends on it; unsupported old evidence is reported as
unreadable and preserved rather than rewritten or dropped.

An actively unsafe behavior may refuse immediately without waiting for the normal window. That
exception requires a named security or correctness advisory, exact affected tuples, refusal and
effect semantics, a bounded recovery or downgrade path, and release evidence; it does not permit
silent deletion, destructive migration, or retroactive claims that prior effects were absent.
Experimental surfaces may change faster, but their release notes still name the break and they
cannot mutate stable-owned state by surprise.

Upgrade, downgrade, rollback, and channel change are explicit lifecycle operations over side-by-
side exact releases. They assess current ownership, compatibility, receipts, pending effects, and
schema support before mutation and preserve the prior usable selection until the new transition
closes. The first release has no self-updater; mise remains the operator-selected acquisition and
version-selection boundary.

### Release acceptance

The positioning and compatibility gate validates the canonical product names, descriptor, third-
party independence statements, prohibited claims, support-tier vocabulary, channel labels,
Semantic Versioning surfaces, deprecation metadata, compatibility readers, and matrix links across
all owned documentation, manifests, help, examples, and generated guidance. A stable release is
invalid without at least one current certified Agentic SDLC Core tuple; otherwise the candidate
remains preview.

Version-admission fixtures cover below-minimum, exact-minimum, tested-reference, unlisted-newer,
known-incompatible, and profile-specific-higher-floor cases. Below-minimum versions block only the
dependent surface. At-minimum and newer versions require the applicable capability admission. An
unlisted newer version can become locally capability-qualified without editing the published
matrix, while exact certified rows retain stronger public evidence. No fixture or default may turn
the tested reference set into a hard maximum.

Platform and installation fixtures keep native Linux, WSL2, WSL1, macOS architectures, native
Windows shells, glibc/musl, and each acquisition plane separate. Core and optional profiles never
inherit certification from one another. Negative documentation tests reject blanket latest,
cross-platform, provider-wide, model-wide, host-parity, endorsement, replacement, official-
product, bundled-companion, and universal-gateway language unless an exact verified statement
supports it.

Offline gates consume a checked-in, dated vendor-evidence snapshot and make no release-channel
network call. An explicit release-preparation step re-reads primary-source Claude Code channel,
platform, feature-floor, and installation facts; changed input creates a reviewed matrix candidate
and cannot silently rewrite certification. Live capability and complete-journey canaries remain
separately admitted operational evidence. Deprecation, upgrade, downgrade, rollback, and emergency
refusal fixtures prove preservation, effect-aware exits, and no destructive or silent migration.
