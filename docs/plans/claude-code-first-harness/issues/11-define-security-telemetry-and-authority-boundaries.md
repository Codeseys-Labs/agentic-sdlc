# Define the security, credential, telemetry, and authority boundaries

Type: grilling
Status: resolved
Blocked by: 06, 07, 08, 09
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What data, credentials, logs, receipts, workflow artifacts, and usage telemetry may each product
plane read, write, retain, or transmit? Define the threat model, privacy defaults, redaction,
consent, recovery, human authorization points, and which controls are mechanical versus advisory.

## Answer

### Planes and threat model

Agentic SDLC recognizes six separate ownership and authority planes: distribution/lifecycle,
Claude host, OCX routing, repository, local evidence, and external systems such as providers,
companion installers, MCPs, CI, Git hosts, and web services. No plane gains authority because an
agent invoked it. Cross-plane reads, writes, and transmissions require a declared least-privilege
contract.

Repository content, model output, tools, plugins, and external libraries are potentially hostile.
Credentials, reversible encodings, prompts, source, paths, private identifiers, and artifacts are
sensitive by default. The product defends against accidental disclosure, prompt injection,
foreign-state collision, partial mutation, route substitution, stale evidence, and unapproved
egress. It does not claim protection from compromised OS/root access, a malicious already-trusted
runtime binary, or provider retention outside its control.

The lifecycle plane reads release manifests, selected host destinations, and its own XDG evidence;
it writes only approved owned activations and local receipts. It does not read Claude credentials
or repository content without an operation that explicitly requires them. Claude continues to own
login, settings, transcripts, and host behavior. The repository owns sanitized durable work
artifacts. Local evidence owns content-minimized receipts, never copied transcripts.

### Data classification and credential custody

Data has four classes:

- **secrets** — tokens, keys, cookies, credential helpers, and raw auth responses; these never
  enter Agentic SDLC logs, receipts, artifacts, or caches;
- **sensitive content** — source, prompts, model output, private URLs, paths, identities, and issue
  bodies; these remain in the owning plane and transmit only under declared egress;
- **operational evidence** — hashes, versions, route IDs, timestamps, result classes, counts,
  approval digests, and artifact references; this is normal receipt content; and
- **public content** — explicitly public material, still subject to a declared destination and
  purpose.

Receipts use hashes and references rather than bodies. Base64 and similar reversible encodings are
not redaction. Claude transcripts are not duplicated. Tracked journals are sanitized and
secret-free. XDG evidence is private to the user. Caches are disposable and never prove ownership,
qualification, or authority.

Claude Code exclusively owns its subscription login. External-provider credentials remain
operator-owned in each provider's approved store. `ccodex routes configure` may invoke that front
door but never intercepts, copies, migrates, or persists values. A routed process receives only the
selected provider's credential scope, with unrelated credential variables scrubbed. Claude
credentials never reach non-Claude providers, and external-provider credentials never enter
`~/.claude`. Status reports readiness categories without credential fragments. Credential
creation, replacement, migration, revocation, and deletion require separate hard human gates.

### Telemetry, egress, and routing data

The first release has no Agentic SDLC usage telemetry. Local metrics are not transmitted.
`status`, offline `doctor`, planning, receipt inspection, and recovery planning never use the
network. Every online operation discloses destination, purpose, data classes, expected calls/cost,
and external retention before approval. Model calls, qualification, security lookups, update
checks, library discovery, and source resolution are all egress. A workflow envelope may approve
repeated calls only within named routes, data classes, and budgets; a new endpoint, class, or
purpose invalidates approval. External platforms' own telemetry is disclosed, not relabeled as
product telemetry. Future product telemetry requires a separate explicit opt-in decision.

OCX binds only to local transport. It processes request and response bodies in memory and persists
none. Logs contain redacted operational evidence only. Each request goes to its exact approved
provider endpoint with bounded sizes, timeouts, retries, and response limits. Qualification uses
synthetic canary data by default; repository data requires separate egress approval. Provider-side
retention is disclosed. Gateway health proves connectivity, not identity, privacy, or billing.

### Authorization and evidence strength

Only the main human-facing conductor session supplies approval. Subagents, repository
instructions, model/tool output, receipts, passing gates, and config files cannot approve.
Approval binds an exact plan digest, scope, destinations, routes, data classes, budgets, and
validity conditions; repository or runtime drift invalidates it.

Persistent trust/global config, credential lifecycle, new egress or paid evaluation, installation
and migration, destructive or unknown-effect recovery, outward effects, and permission bypass are
mechanically non-delegable gates. Bounded auto mode may authorize internal replanning and scoped
work in advance but cannot cross them. `--yolo` remains a separate, explicit, visibly reported
session permission profile and does not disable route, billing, credential, ownership, gate,
tool, or egress controls.

Claims use three evidence strengths:

- **mechanical** — enforced at a process, filesystem, network, argument, identity, or transaction
  boundary and covered by adversarial tests;
- **observed** — independently measured after execution but not guaranteed beforehand; and
- **advisory** — prompts, documentation, warnings, roles, or review policy.

Requested values never become enforced or observed through prompt repetition. Required properties
are mechanical where the host permits. If a required property remains advisory, the affected
feature is unsupported or stops. Observation may detect failure but cannot authorize
retroactively. Receipts label evidence strength; tests exercise refusal, malformed input, partial
mutation, substitution, redaction, and unknown-effect paths.

### Retention, redaction, and incidents

Active ownership receipts remain while owned artifacts exist. Pending or unknown-effect journals
remain until resolved. Completed lifecycle/removal receipts and content-minimized qualification
history remain for at least 90 days; qualification is current for 30 days. Version 1 does not
automatically delete that history and exposes no evidence-history prune or purge operation.
Debug logging is off by default; explicit redacted logs expire after seven days. Authority-free
caches expire after 30 days and are size-bounded. Repository artifacts follow repository policy.
Removal and uninstall preserve local history. A future product-managed history-deletion surface
requires a separate privacy, compliance, ownership, and recovery decision.

Structured serializers omit forbidden fields before formatting; regex is defense in depth. If
safe serialization is not provable, logging stops. Secret-shaped model/tool/diff/artifact content
stops the branch before persistence or fan-in. Diagnostics name the class and location without the
value. A sanitized incident receipt records operation, destination, time, and possible exposure
class. The product never automatically rotates credentials, rewrites history, or deletes user
data. It provides provider-specific remediation for separate approval and states honestly when
transmission may already have happened. Betterleaks and the admitted gate contract remain required.

### Supply chain, tools, and external code

Every bundled binary, runtime, plugin, workflow, skill, and policy is versioned and digest-bound in
the release manifest. `inspect` and `doctor` verify checksums, manifest identity, provenance, and
compatibility. Releases include an SBOM and licence/NOTICE inventory. Commands use absolute
packaged tools, never caller-PATH substitutes, mutable `latest`, or silent runtime downloads.
Updates repeat verification. Missing provenance blocks a supported claim.

Skills/plugins are executable authority. External libraries run only through exact displayed
front doors with scrubbed unrelated credentials, declared egress, explicit targets, and approval.
Arbitrary package hooks are denied unless separately reviewed and approved.

Every workflow node declares a minimum tool capability set. Preflight inspects the effective
tool/MCP inventory; installed config is not evidence. Unknown, newly appearing, colliding, or
incompatible tools block or require a revised plan. Claude.ai connectors and external MCPs are
opt-in and cannot be enabled by repository content. Tool definitions/results are untrusted,
bounded, sanitized, and redacted. Network tools require declared egress. Read-only roles exclude
write tools mechanically where supported; an unenforceable required restriction stops or is
explicitly unsupported. Permission bypass does not weaken these harness controls.

### ADR disposition

This boundary is expensive to reverse, cross-cutting, and accepts explicit operability costs, so
it warrants durable ADRs. It must not become one mega-record: product-plane/privacy defaults,
authorization/evidence strength, and supply-chain/tool trust are separable decisions with different
reversal conditions. Numbering, relationships, and supersession wait for the repository-truth
reconciliation so existing accepted ADRs and current dirty ADR work are preserved.
