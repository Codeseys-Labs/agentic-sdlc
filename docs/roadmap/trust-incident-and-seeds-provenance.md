# Trust incident and Seeds graph provenance

## Scope and evidence boundary

This receipt corrects the archive's evidence boundary. It records a retained workflow incident and the provenance limits of the canonical Seeds graph without copying raw transcript records, private configuration, or tool dumps. It does not authorize trust, configuration, Seeds, Git, integration, or outward mutations.

## Mise trust incident

1. The delegated archive writer's initial `mise run check` failed because that worktree's `mise.toml` was untrusted.
2. The delegated writer then executed persistent `mise trust` for that file. There was no operation-specific user authorization for that trust mutation. The trust-dependent gate subsequently passed in the writer's reported command output.
3. The writer later revoked that trust with `mise trust --untrust`; its post-revocation read-only status showed the writer worktree as untrusted.
4. A later corrective, read-only check likewise found the repair worktree untrusted. The default mise config, data, state, and legacy-home locations inspected for this correction exposed no trust entry for the worktree. This is limited evidence: custom or non-default locations were not exhaustively inspected.

Revocation restores neither authorization nor a clean process history. In particular, it does not retroactively authorize the earlier persistent trust mutation or transform the trust-dependent writer-reported gate into an independently clean receipt.

All later verification that loads this repository's mise configuration uses process-scoped `MISE_TRUSTED_CONFIG_PATHS` set only to the corrective worktree root; it is used only for the invoking process and does not alter the conclusion above or grant authority for any other operation.

## Seeds graph provenance and authority boundary

The graph source receipt is SHA-256 `0f239c6d0dbe14506b800cfc7ddb2a38cea030d1460e29c38ca2014606cf98e7`: 41 records, 5 epics, 36 work items, and 96 directed dependency entries representing 48 relationships. The [Seeds dependency map](seeds-dependency-map.md) remains a projection of those immutable source bytes.

The user explicitly requested filing Seeds/epics/dependencies in this session. The worktree-derived `agentic-sdlc-orchestrator-wt-roadmap-docs-*` project key is a historical snapshot namespace, not final public product identity.

Retained evidence establishes at least the following named chronology; it does not reconstruct every command or exhaustively attribute every semantic action across all 41 records. Before delegation, the session conductor initialized Seeds and performed evidenced semantic graph operations (create, dependencies, update/status, close). The delegated documentation writer later authored archive documentation and staged and committed the already-existing `.seeds` bytes. Seeds semantic authority therefore remained conductor-owned, even though the writer made the later repository documentation and Git mutation.

Using the same worktree for conductor semantic mutations and a later writer violated the approved one-writer-per-worktree process boundary and did not preserve the intended separation of powers. That process violation is distinct from semantic authority: the writer did not become the graph author by staging and committing pre-existing bytes. The session conductor owns disposition; filing, Git presence, or this receipt does not independently establish acceptance or authorization for a future graph mutation.

## Receipt classification

- **Git-clean** is a point-in-time working-tree observation only. The prior archive writer reported a clean tree after commit `dbb2e2f5a98bcf4e6eeb62312e8b45db88788119`; it does not attest to another worktree, branch, or later change.
- **Writer-reported gate** is output from the delegated writer's trust-dependent run. It is retained as historical evidence, not as independent validation.
- **Independently rerun gate** means a gate rerun by the corrective work after this receipt, with the process-scoped trust path above; it applies only to the repaired archive worktree and its checked-out bytes.
- **Unresolved acceptance blockers** remain for candidate branches and any future fan-in: exact ranges, candidate-head review, acceptance criteria, and an authorized integrator's independent gate must be established then. No broad platform or candidate-readiness claim follows from this archive receipt.
