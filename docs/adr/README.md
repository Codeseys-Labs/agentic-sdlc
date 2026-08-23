# Architecture Decision Records

Only the closed lowercase lifecycle values in the ADR lifecycle are canonical. ADR-0008 and
ADR-0015 predate that rule and carry noncanonical metadata in their accepted bodies. The index
labels those raw states as legacy debt instead of silently normalizing them; this rebuild does not
edit either accepted record or infer a stronger status.

| ID | Title | Status | Date |
|---|---|---|---|
| [ADR-0001](0001-mit-license-and-root-notice-attribution.md) | MIT license, with a root NOTICE as the attribution ledger | accepted | 2026-08-06 |
| [ADR-0002](0002-mise-is-the-single-front-door.md) | mise is the single front door; no second bootstrap prerequisite | accepted | 2026-08-06 |
| [ADR-0003](0003-gateway-stance-downgraded-to-optional.md) | gateway stance downgraded: optional for non-Anthropic models, not a subscription-cost mechanism | accepted | 2026-08-06 |
| [ADR-0004](0004-compounding-loop-is-proposal-plus-operator-gated-adoption.md) | the compounding loop is harness proposal + operator-gated adoption, never unmeasured self-editing | accepted | 2026-08-06 |
| [ADR-0005](0005-opencodex-installed-by-default-for-split-plane-routing.md) | opencodex is installed by default for split-plane non-Anthropic routing, with the subscription boundary enforced in the launcher | accepted | 2026-08-06 |
| [ADR-0006](0006-mermaid-sandbox-resource-limits.md) | Two Mermaid sandbox limits are recalibrated as resource-availability ceilings for the pinned browser, and the output-size controls stay put | accepted | 2026-08-07 |
| [ADR-0007](0007-muse-spark-direct-route.md) | Meta's Muse Spark is admitted on two routes: as an opencodex provider (primary) and as a direct gateway-free route (fallback), qualified as a route and placed in no tier | accepted | 2026-08-07 |
| [ADR-0008](0008-third-party-skill-libraries-are-the-operators-own-install.md) | A third-party skill library is never vendored into this bundle; its bytes stay upstream and adaptation requires a NOTICE donor entry | legacy noncanonical: `accepted in part` | 2026-08-07 |
| [ADR-0009](0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md) | An external skill library is installable on request through its OWN front door, opt-in and collision-checked; this bundle still never vendors a foreign byte | accepted | 2026-08-07 |
| [ADR-0010](0010-gateway-plane-inherits-inert-session-data-and-the-statusline-stanza.md) | A gateway-launched Claude Code session inherits inert session data and the statusLine stanza; settings.json is constructed key-by-key and never copied, because the global file carries a live credential | accepted | 2026-08-07 |
| [ADR-0011](0011-remote-bootstrap-manages-the-clone-instead-of-eliminating-it.md) | a remote bootstrap manages the clone instead of eliminating it | accepted | 2026-08-07 |
| [ADR-0012](0012-context-window-accommodation.md) | Per-model context windows are owned by the gateway, the session carries one conservative floor, and the recorded truth lives in the calibration table | accepted | 2026-08-07 |
| [ADR-0013](0013-explicit-unsupported-claude-subscription-passthrough.md) | explicit unsupported Claude subscription passthrough is a bounded operator escape hatch | superseded by ADR-0014 | 2026-08-10 |
| [ADR-0014](0014-gateway-launch-preserves-the-operators-own-claude-login.md) | the gateway launch preserves the operator's own Claude login, and the split plane is retired | accepted | 2026-08-11 |
| [ADR-0015](0015-local-evaluation-is-the-rightsizing-promotion-boundary.md) | Local evaluation is the rightsizing promotion boundary | legacy noncanonical: `Accepted` | 2026-08-12 |
| [ADR-0016](0016-yolo-is-an-explicit-permission-profile.md) | Make yolo an explicit permission profile on both ccodex launch forms | accepted | 2026-08-12 |
| [ADR-0017](0017-make-claude-code-the-primary-product-host.md) | Make Claude Code the primary product host | accepted | 2026-08-15 |
| [ADR-0018](0018-keep-sensitive-product-state-in-its-owning-plane.md) | Keep sensitive product state in its owning plane | accepted | 2026-08-15 |
| [ADR-0019](0019-require-fresh-human-authorization-for-every-effect.md) | Require fresh human authorization for every effect | accepted | 2026-08-15 |
| [ADR-0020](0020-admit-only-exact-verified-execution-dependencies.md) | Admit only exact verified execution dependencies | accepted | 2026-08-15 |
| [ADR-0021](0021-distribute-agentic-sdlc-as-a-versioned-mise-release.md) | Distribute Agentic SDLC as a versioned mise release | proposed | 2026-08-15 |
| [ADR-0022](0022-activate-repositories-through-digest-approved-plans.md) | Activate repositories through digest-approved plans | accepted | 2026-08-15 |
| [ADR-0023](0023-adopt-one-evidence-preserving-documentation-profile.md) | Adopt one evidence-preserving documentation profile | accepted | 2026-08-15 |
| [ADR-0024](0024-execute-each-wave-as-one-artifact-driven-dynamic-workflow.md) | Execute each wave as one artifact-driven Dynamic Workflow | accepted | 2026-08-15 |
| [ADR-0025](0025-compile-execution-from-immutable-planning-artifacts.md) | Compile execution from immutable planning artifacts | superseded by ADR-0030 | 2026-08-22 |
| [ADR-0026](0026-keep-threat-analysis-separate-from-human-risk-ownership.md) | Keep threat analysis separate from human risk ownership | accepted | 2026-08-15 |
| [ADR-0027](0027-admit-compatibility-through-capability-evidence-above-published-minimums.md) | Admit compatibility through capability evidence above published minimums | accepted | 2026-08-15 |
| [ADR-0028](0028-organize-the-claude-code-first-product-boundary-as-one-initiative.md) | Organize the Claude Code-first product boundary as one initiative | proposed | 2026-08-15 |
| [ADR-0029](0029-ported-libraries-are-a-second-external-library-catalog-class.md) | Ported libraries are a second external-library catalog class | accepted | 2026-08-20 |
| [ADR-0030](0030-record-wave-evidence-in-git-and-one-markdown-file.md) | Record wave evidence in Git and one markdown file | accepted | 2026-08-22 |
| [ADR-0031](0031-keep-ccodex-on-bash-and-python-and-harvest-one-bun-classifier.md) | Keep ccodex on bash and Python; harvest one Bun-compiled classifier | accepted | 2026-08-23 |
