# Agentic SDLC Recovery and Expansion Plan

Updated 2026-07-14 from the complete session transcript, current repository state, `[1m]` multi-agent audit, primary jj/Mermaid documentation, and the user's confirmed reversals.

## Context

The repository spent most of its recent effort making global distribution safe across Claude Code, Codex, WSL, macOS, and Windows. That work landed at `origin/main@9432b2c`, but several product decisions were deferred or reversed against the user's original direction. The user has now confirmed the new baseline:

- remove CAO completely rather than retain tombstones;
- make **Agentic SDLC** and `agentic-sdlc` canonical locally and publicly;
- eventually rename the GitHub repository to `Codeseys-Labs/agentic-sdlc` under a separate outward-operation gate;
- research and enable jj now as an explicit opt-in substrate while Git remains the interop, integration, CI, and forge authority;
- consolidate the seven delivery roles and 17 Research OS roles through shared contracts without collapsing separation of powers;
- build a Mermaid family with one umbrella/router skill and one real skill for every documented diagram type;
- finish the immediate backlog, then resume the complete capability and Evolutionary Core roadmap.

The transcript audit parsed 16,126 JSONL records and recovered exactly 30 genuine human messages. It confirmed that the omitted requests include the product rename, jj, DWL/tiered mega-loops, HyperResearch, CCP/ccodex, Mermaid per-type skills, Git/worktree/rebase/squash/stacked-PR knowledge, toolchain/security skills, hierarchical instructions, model rightsizing and `[1m]`, Seeds, and attribution-free change writing.

## Fixed invariants

- Mise remains the only user-installed bootstrap prerequisite.
- `mise run check` remains the repository gate.
- TDD: every behavior change begins with a failing test.
- One writer per worktree; one conductor owns Seeds and disposition; one integrator has fan-in WIP 1.
- Seeds is the queue of record, not an authorization channel.
- Git remains the compatibility, candidate, integration, receipt, CI, branch, and forge authority.
- jj is opt-in and never mixed with a Git worktree in one assignment.
- Reviewers, critics, researchers, adapters, and packs remain advisory.
- No shipped/public/runtime CAO files, flags, commands, profiles, references, or tombstones remain. A private validator denylist and focused negative fixtures may name CAO solely to prevent regression; they are not installable compatibility surfaces.
- Commit, PR, and squash artifacts contain no model/agent attribution unless explicitly requested for that artifact.
- Context-heavy transcript, repository-wide research, planning, synthesis, and adversarial review agents use exact `[1m]` model IDs. Narrow mechanical workers may be unsuffixed.
- Dynamic workflows are the default for substantive work: decompose before dispatch, fan independent discovery/research/implementation/review across right-sized agents, use pipelines so verification starts as each item completes, and reserve the conductor for cross-item decisions and synthesis. Do not concentrate a whole wave in one mega-agent when the work has separable artifacts. Parallel writers always use separate worktrees and one integrator still owns fan-in.
- Workflow routing is explicit: Sol `high/xhigh` for derail-class decisions, Terra `xhigh/max` for contained judgment and implementation, Luna `high/xhigh` for deterministic-gated volume.
- Push, PR creation/mutation, merge, local checkout-directory rename, trust/config changes, and GitHub repository rename require separate operation-specific approval.

## Superseded plan premises

1. The old public compatibility slug is no longer retained for a release. `agentic-sdlc` becomes canonical; `agentic-sdlc-orchestrator` survives only in private migration/dedup logic and focused tests.
2. CAO retirement tombstones are replaced by complete deletion.
3. jj refusal is replaced by immediate research and bounded opt-in enablement.
4. Mermaid per-type references are replaced by one umbrella/router plus one installable skill for every documented type.
5. Previously deferred capability bundles enter the active roadmap, while promotion into Core still requires conformance evidence.
6. Installer ownership state gains an explicit v2→v3 migration so the identity cutover cannot create duplicate installed skills.

Still valid: Evolutionary Core, Git interoperability, one-writer/one-integrator authority, bounded delegation, immutable evidence, separate publication authority, and no public pack ABI before portability proof.

## Current baseline

- Authoritative base: `origin/main@9432b2c05a20f56e7b893215c90032b7881365bd`.
- Do not integrate from stale local `main@fa9c249`, the tree-equivalent historical feature head `bfee320`, or old installer/knowledge worktrees.
- Seeds toolchain: `feat/seeds-toolchain@30f749c`, clean and gated.
- Seeds execution: `feat/seeds-execution-contract@db0e860`, clean and gated, but audit found two remaining bare calls.
- Current remote: `https://github.com/Codeseys-Labs/agentic-sdlc-orchestrator.git`.
- Existing reusable machinery:
  - installer state, locking, atomic persistence, migration, transactions, and recovery in `scripts/install_skill_bundle.py` (`read_state_document`, `validate_state`, `write_state`, `persist_state`, `installer_lock`, `known_state_documents`, `stage_candidate`, `transaction_record`, `classify_recovery`, `execute_recovery`, `recover_transactions`, `transactional_create/replace/delete`, `digest`, `entry_record`, `entry_matches_record`);
  - dynamic payload discovery in `discover_entries()`;
  - exact gate graph in `mise.toml` and `scripts/validate_bundle.py`;
  - shared role submission fields and one-integrator doctrine in existing Claude/Codex role definitions;
  - stacked-PR and worktree safety knowledge in `skills/stacked-prs*` and flagship references.

## Dependency graph

```text
S1 Seeds toolchain
  └─ S2 exact Seeds execution/all-surface enforcement
       └─ Seeds review + authorized fan-in
            └─ C1 complete CAO deletion
                 └─ I atomic state-v3 + agentic-sdlc identity cutover
                      ├─ local checkout-directory cutover [separate approval]
                      └─ independent capability lanes
                                     ├─ A1 change writing → A2 sdlc-init → A3 instructions
                                     ├─ R1 role contracts → R2 DWL / R3 HyperResearch
                                     ├─ G1 Git flow / G2 security gates
                                     ├─ J1 jj certification → J2 opt-in implementation
                                     └─ M0 Mermaid foundation → M1..M5 types → M6 router → M7 conformance
                                          └─ capability wiring/integration
                                               └─ Evolutionary Core M2 → Claude M3 → portability M4
                                                    ├─ CCP/ccodex promotion
                                                    ├─ jj Core-substrate certification
                                                    └─ first-party pack lifecycle
```

## Wave 0: finish and integrate Seeds

### S1: retain the accepted pinned toolchain

Branch `feat/seeds-toolchain@30f749c`, based on `9432b2c`:

- Node `22.22.3`, Bun `1.3.10`, `npm:@os-eco/seeds-cli@0.5.14`;
- npm backend and exact reviewed `mise.lock` digest;
- runtime install must preserve lock bytes;
- canonical regeneration applies only to exact maintenance mise `2026.4.27`;
- document that the npm lock proves version/backend, not tarball or transitive integrity.

### S2: close the exact execution contract

Continue `feat/seeds-execution-contract@db0e860` with one TDD repair commit:

- replace `sd sync` in `skills/agentic-sdlc-orchestrator/references/sdlc-loop.md` with `Seeds(<target>, sync)`;
- replace Research Director `sd ready`/claim/create authority in `agents/codex/research/research_director.toml` with exact Seeds inspection and a typed `SeedProposal`; only the conductor mutates Seeds;
- replace the short `OWNED_DOCS` allowlist in `tests/test_preflight_capabilities.py` with recursive coverage of commands, all skills/references, Claude/Codex roles, Research OS roles/templates, README, and root policy;
- preserve POSIX and process-scoped Windows argv/cwd/environment behavior:

```text
MISE_NPM_PACKAGE_MANAGER=npm mise --no-config --cd <target> exec \
  node@22.22.3 bun@1.3.10 npm:@os-eco/seeds-cli@0.5.14 -- sd <args>
```

Run focused preflight tests, native Windows probe, full tests, and `mise run check`.

### Fan-in

Create `integration/seeds-0.5.14` from `9432b2c`. The sole integrator validates and lands exact ranges `9432b2c..30f749c` (S1) and `30f749c..db0e860` plus the final S2 repair commit, never the full overlapping S2 branch twice. Recompute each range after the repair, inspect merge-base footprint/commit count, and re-gate after each. No later wave begins until the integrated result has independent review and a clean full-gate receipt. Push/PR/merge are separate later approvals.

## Wave 1: remove CAO completely

Branch `remove/cao` from the accepted Seeds integration SHA.

Delete:

- `cao-profiles/`;
- `scripts/install-cao-kit.sh`;
- flagship CAO reference files;
- `tests/test_cao_retirement.py`.

Remove `INSTALL_CAO` handling from `scripts/install-skill-bundle.sh`, CAO-specific inventories/validation from `scripts/validate_bundle.py`, and every CAO mention from public/runtime source.

Replace tombstone tests with a negative removed-surface contract proving that a planted CAO-named path, flag, executable reference, profile, install path, or runtime command fails validation. Git history is excluded. Never delete unknown legacy files from user homes; report them as foreign/manual cleanup.

Acceptance: zero CAO shipped paths/references/behavior, falsifiable negative validator, unchanged lifecycle ownership safety, full gate green.

## Wave 2: one atomic `agentic-sdlc` identity cutover PR

After CAO deletion, create one bounded identity PR. It may contain internal commits for schema/phase-machine preparation, source/manifests rename, migration activation, and tests, but only the cumulative final head is reviewed, landed, installed, or released. No intermediate identity commit is deployable and no stacked child exposes a half-renamed system.

Primary files are `scripts/install_skill_bundle.py`, `tests/test_install_skill_bundle.py`, the flagship skill directory, command/role/cross-skill routing, manifests, validator, and focused identity tests.

Generalize the migration pipeline so v1 can normalize directly to v3 in memory and v2 requires explicit `--migrate-state`. Keep the state root `agentic-sdlc-installer/state.json` and `IDENTITY_VERSION = "stat-v2"`. Reuse the existing installer lock, transaction, atomic-write, identity, digest, and recovery machinery; add a persisted rename migration record with old/new keys and records, staged candidate, backup, phase, and rollback witness.

In the same cumulative PR, rename `skills/agentic-sdlc-orchestrator/` to `skills/agentic-sdlc/`; update frontmatter, command/role/cross-skill routing, and Claude/Codex/Agents/Gemini/OpenAI manifests; keep `/sdlc-*` command names. Do not publish a fictional forge URL; optional homepage/repository fields remain omitted until the separately authorized GitHub rename.

Activate v2→v3 only in this final renamed-source tree. Under `installer_lock()`, recover transactions, recognize the old slug only through a private alias map, refuse occupied new targets, create/verify the new destination first, retire the exact old destination second, atomically swap ownership records, retain a rollback witness until cleanup, and make every crash phase retry-idempotent.

Use **mode-specific old ownership witnesses** plus one new-source witness:

1. Old copy: recompute the old destination content and require it to equal the v2 `digest`; this proves the copy still contains the old installer-owned bytes.
2. Old symlink/junction: require exact recorded link-object identity, exact recorded target text/path, destination kind, agent/kind/name/key consistency, and approved collection/root containment. If the cumulative source rename has made the recorded target absent, do not dereference it and do not recompute the old source digest; treat the persisted v2 digest as immutable provenance only. If the target still exists, its digest may be rechecked as defense in depth but cannot replace link-object ownership.
3. New source/stage: freshly compute `new_source_digest` from `skills/agentic-sdlc`, store it in the staged candidate and v3 record, and revalidate source plus staged destination during every recovery pass immediately before final state publication.

The migration never requires the intentionally changed new source to equal the old digest. The POSIX fixture explicitly renames/removes the old source so the owned old link is dangling, then proves migration by link-object identity/target/provenance and new-stage digest. The native Windows fixture does the same for a junction. Copies continue to require live old-content hashing.

TDD covers POSIX links, Windows junctions, copies, changed new frontmatter/routing, modified old entries, foreign new targets, verified duplicates, every publish/backup/state/cleanup crash boundary, idempotent retry, one-step v1→v3, newer/downgrade refusal, dry-run no writes, and rollback witness behavior. The old public slug is allowed only in private migration/dedup denylist constants and focused fixtures; it is absent from shipped names, prompts, roles, commands, docs, manifests, destination guidance, and tasks.

### Separate Claude marketplace/plugin plane

Direct-installer ownership migration must not edit Claude's opaque plugin state. Use only supported `claude plugin marketplace list/remove/add`, `claude plugin list`, and `claude plugin uninstall/install` operations in isolated homes. Define old-only, new-only, both, modified cache, interruption, scope, and direct-installer-overlap cases. If the CLI cannot prove a safe automated migration, fail closed with exact manual commands and preserve plugin data via `--keep-data` where applicable. Never infer marketplace ownership from the direct-installer state.

### Separate local directory and GitHub rename gates

After the accepted cumulative identity-cutover head is stable, request explicit approval before renaming `/mnt/e/CS/github/agentic-sdlc-orchestrator` to `/mnt/e/CS/github/agentic-sdlc`. First record every worktree path/OID/branch/dirty state, remote, installer-state digest, installed link target, and trust path. Never clean, delete, or force-remove a dirty worktree; the currently dirty bridge worktree must be preserved on its branch with its untracked inventory.

Move the main worktree manually from the parent directory, then run `git worktree repair` from the new main path and verify every linked worktree in both directions. Transactionally retarget every exact owned WSL/Windows link, junction, or copy from the new source root through the v3 installer. Verify Git refs/hooks/common-dir, bundle status/dry-run, native Windows state, and `mise run check`. Recovery is move-back plus `git worktree repair` plus v3 retarget-back while the recorded rollback witnesses remain valid.

The outward GitHub rename to `Codeseys-Labs/agentic-sdlc` is later and separately authorized. Before it, inventory repository ID, target-name availability, default branch, protections, releases, open PRs, marketplace entries, integrations, and redirects. Rename only the repository, verify by repository ID/redirect/permissions/CI, then update remote and manifest URLs in a separate authorized change. The old name may be unrecoverable, so do not treat this as a reversible local edit.

## Wave 3: immediate backlog and capability lanes

All lanes use separate worktrees from the accepted identity anchor. Central README/flagship wiring is reserved for one integration PR.

### A1: standalone `change-writing` skill

Implement the already approved design in `~/.gstack/projects/codeseys/codeseys-feat-mise-cross-host-installer-design-20260713-035802.md`.

One globally installable, output-only skill supports commit, PR, squash, and draft-review modes. Repository policy/history and verified diff/gate evidence win. It never stages, commits, pushes, creates/edits PRs, merges, or deploys. It omits unsupported claims and prohibits model/tool attribution, `Co-Authored-By`, generated-by text, and badges unless explicitly requested for the current artifact. Add falsifiable clean/forbidden fixtures and route the flagship and stacked-PR guidance to it without duplicating Git operations.

### A2: Git-default `/sdlc-init` hardening

Keep a reviewed procedure, not a second kernel. Add mandatory dry-run `ActivationPlan`, explicit `--profile git`, optional interactive selection when a TTY is available, deterministic `git` default for non-TTY/headless use, cancellation/no-write behavior, prompt fixtures, and receipt recording of whether a choice was explicit or defaulted. Add per-item `create|adopt|merge|refuse|skip`, baseline inventory, exact Seeds calls, non-empty queue proof, reversible gate fail→pass fixture, trust planning, CI parity, marked `AGENTS.md`/thin `CLAUDE.md`, `ActivationReceipt`, rerun/no-diff idempotence proof, and rollback/deactivation. No global install or unrelated user-config mutation.

Do not expose `jj-colocated` here yet. A post-J1/J2 child amendment adds that profile only after its compatibility report and immutable Git handoff pass.

### A3: hierarchical instruction generator

One manifest and marker-aware generator manages root `AGENTS.md`, thin root `CLAUDE.md`, subtree `AGENTS.md`, and `.claude/rules/*.md`. Dry-run first; preserve hand-authored content; adopt only exact marked sections; refuse malformed/duplicate markers; validate generated output; enforce hard guarantees in gates rather than duplicated prose.

### R1: shared role/artifact contracts

Consolidation means shared machinery, not collapsing duties. Add one versioned internal manifest for all seven delivery and 17 research roles: role ID, phase, purpose, read/write scope, artifacts accepted/produced, workspace ownership, model lane/effort/context, delegation limit, and queue/fan-in/publication authority.

Standard artifacts include `Map`, `ResearchBrief`, `SeedProposal`, `Candidate`, `ReviewFinding`, and `IntegrationReport`, while retaining current submission fields. Generate or validate Claude/Codex projections only after conformance fixtures exist.

Preserve separation:

- integrator remains the only fan-in executor;
- planner/director do not implement or disposition Seeds;
- critic/adversarial reviewer attack but never fix;
- reviewer recommends but does not authorize;
- synthesis writer cannot originate unsupported claims;
- experimentalist cannot approve its own experiment;
- Research OS remains repo-scoped and selectable, not 17 global agents.

Fix the existing Research Director authority leak first. Standardize the cartography schema while preserving delivery-map versus research-memory purposes. Treat provider web/write capabilities as explicit runtime capabilities, not assumed parity.

### R2: bounded Deep Work Loop/tiered mega-loop

Consolidate existing mission/tier doctrine into `frame → map/research → decide → act → verify → critique → reconcile`. It emits artifacts/recommendations only; no second queue, integration, publication, or unbounded recursive delegation. Apply exact Sol/Terra/Luna effort routing and `[1m]` only to context-heavy agents, recording it as client context/compaction behavior rather than intelligence.

### R3: HyperResearch and Research OS hardening

HyperResearch runs only when external evidence is load-bearing and returns versioned sources, claims, counterevidence, uncertainty, decision impact, and next action. Harden `skills/codex-research-os/scripts/install_research_os.py` with a generator-owned inventory manifest, per-file ownership markers/digests, dry-run parity, same-directory backup/recovery, partial-install reconciliation, exact-owned replacement only, and permanent refusal to overwrite foreign or modified files. `--force` never broadens ownership. Add crash, rollback, idempotence, removed-template, and modified-foreign fixtures, plus R1 role conformance and `SeedProposal` rather than queue mutation.

### G1: Git change-flow knowledge family

Consolidate, do not duplicate, existing worktree and stacked-PR guidance for one-writer ownership, branches/recovery refs, rebase boundaries, squash scope, clean apply versus semantic correctness, stack topology/restacking, exact remote-OID leases, child-PR deletion checks, merge-base footprints, and re-gating. Keep one `stacked-prs` router; move raw `gh` mechanics to a reference/compatibility alias if conformance tests show no independent trigger value.

### G2: toolchain/security hardening

Extend `repo-toolchain-gates` without another task runner: mise pins, lefthook as a gate subset, betterleaks working-tree hook/CI checks, approved history scans, per-path worktree trust, identical CI gate graph, exact receipt argv/status/log digest, and non-secret falsifiability fixtures.

## Wave 4: jj opt-in using worktree + `[1m]` workflow

### J1: research/certification lane

Use an isolated Git worktree and official jj docs first. Primary-source facts already verified for jj 0.43.0:

- colocated jj automatically imports/exports Git refs on each jj command;
- mutating Git and jj may be mixed but official docs recommend mostly read-only Git due to detached HEAD, divergence, IDE/background-fetch, and unsupported Git in-progress states;
- Git hooks, `.gitattributes`, Git worktrees, submodules, partial clones, Git LFS, and mature shallow-clone deepening are unsupported;
- use native `jj workspace`, not `git worktree`, for jj assignments;
- conflicted jj commits are not ordinary Git-interoperable candidates;
- `jj op log`, `jj undo`, `jj op revert`, `jj op restore`, and `jj workspace update-stale` provide recovery evidence.

Primary sources:

- https://docs.jj-vcs.dev/latest/git-compatibility/
- https://docs.jj-vcs.dev/latest/operation-log/
- https://docs.jj-vcs.dev/latest/working-copy/
- https://docs.jj-vcs.dev/latest/conflicts/

Run bounded agents: Sol `[1m]` frame/final ruling, Terra `[1m]` semantic and test analysis, Luna mechanical fixture matrix, Sol `[1m]` adversarial data-loss/authority review. Produce `JjCompatibilityReport`, `JjFixtureResult`, `JjDecisionRecord`, and `SeedProposal`.

Certification covers colocation, Git-visible conflict-free candidates, bookmarks/refs, native workspaces, mandatory explicit gate because hooks do not fire, conflict rejection, no concurrent mutating Git/jj, op-log/stale recovery, unsupported feature refusal, headless identity, teardown without deleting `.jj` or shared Git data, and forge operations remaining Git/`gh` responsibilities. Select and prove an isolation architecture; default to a dedicated colocated clone plus native jj workspaces so existing registered Git worktrees are never mixed into the jj assignment.

The immutable handoff contract is: worker resolves all jj conflicts; exports an exact bookmark/ref; records the conflict-free Git commit OID and jj operation ID; conductor verifies that OID with read-only Git; the Git integrator fetches the exact local ref/OID into its isolated Git integration worktree and recomputes the footprint/gates. Unsupported Git worktrees, submodules, LFS, partial clones, `.gitattributes`-dependent semantics, and unsupported shallow states fail closed.

### J2: implementation lane

Pin the certified jj version through mise. Add `jj-colocated` as a child amendment to the hardened `/sdlc-init` only after J1 passes. It requires explicit selection and compatibility probes; no implicit headless default. Never mix workspace types within one assignment. Export only conflict-free Git-visible candidates through the immutable handoff above; record jj operation IDs as supplemental evidence; keep integration, receipts, CI, push, and PR in Git; never assume hooks ran; disabling the profile preserves `.jj` and user data.

## Wave 5: Mermaid skill family

Official Mermaid 11.16.0 currently documents exactly 30 diagram types. Implement one umbrella/router plus 30 real top-level skills, not reference-only pages.

### M0a: dependency/browser ADR and fresh-host spike

Before adding diagram skills, select and prove a locked Node/npm dependency graph, exact `mermaid` and `@mermaid-js/mermaid-cli` versions, and an offline-capable browser provider on Linux, macOS, and Windows. The repository currently has no JS manifest or browser adapter, so do not assume `mermaid.render()` works in bare Node or that `mmdc` will not download an unpinned Chromium. Prefer the already shared gstack browser only when it is a declared available adapter; required repository CI needs its own pinned, reviewed provider/config.

The spike must produce a deterministic DOM/render wrapper, trusted generated browser config, clean-environment install receipt, network-off render, and bounded resource/time behavior. If no portable provider passes, stop before M1.

### M0b: versioned validator/security foundation

Pin full `mermaid` and `@mermaid-js/mermaid-cli` through mise/npm using M0a's certified graph; do not use Mermaid Tiny because it omits Mindmap, Architecture, KaTeX, and lazy loading.

Validation uses current APIs:

1. `mermaid.initialize({startOnLoad:false, securityLevel:"strict"})`;
2. `mermaid.detectType(definition)`;
3. `await mermaid.parse(definition)`;
4. `await mermaid.render(id, definition)`;
5. `await mermaid.run(...)` for browser integration;
6. `mmdc -i input.mmd -o output.svg` smoke.

`mermaid.init` is forbidden because it is deprecated. Use isolated temporary directories, bounded input/output/time, no untrusted init/Puppeteer config or network assets, deterministic IDs, and parse the generated SVG before accepting it: allowlist elements, attributes, and URL protocols; reject scripts, event handlers, `foreignObject`, external resources, and unsafe links. Strict is the default; sandbox is separately evaluated because official docs still call it beta.

Primary sources:

- https://mermaid.js.org/intro/
- https://mermaid.js.org/config/usage.html
- https://mermaid.js.org/config/setup/mermaid/interfaces/Mermaid.html
- https://github.com/mermaid-js/mermaid-cli

### M1–M5: 30 per-type skills

Each skill gets its own directory/frontmatter, official identifier/aliases, use and anti-use cases, syntax, minimal valid and representative invalid fixture, `detectType` expectation, parse/render test, accessible title/description guidance, experimental warning when applicable, and primary-doc citation.

- M1 structural: Flowchart, Swimlanes, Sequence, Class, State, Entity Relationship.
- M2 planning: User Journey, Gantt, Timeline, Kanban, Requirement, Mindmap.
- M3 quantitative: Pie, Quadrant, Sankey, XY Chart, Radar, Treemap.
- M4 technical: GitGraph, C4, Block, Packet, Architecture, Event Modeling.
- M5 conceptual: ZenUML, Venn, Ishikawa, Wardley, Cynefin, TreeView.

Run these five sibling worktrees in bounded parallel, one writer each, all based on M0.

### M6 router and M7 conformance

After one integrator assembles M1–M5, add a router that selects exactly one official type, links to every installed type skill, rejects ambiguity/unsupported requests, and never invents syntax. Conformance asserts one router plus exactly 30 skills, inventory matches official docs, valid fixtures detect/parse/render, invalid fixtures fail, CLI smoke passes, malicious fixtures produce no unsafe SVG, and `mise run check` includes the family.

## Dynamic workflow execution pattern

Every substantive wave begins with a small Sol `[1m]` decomposition agent that emits independent artifact/worktree items and dependencies. Use `pipeline()` by default so each item's reviewer/verifier starts when that item completes; use a barrier only for real cross-item deduplication, shared architecture choice, or fan-in. Route repository-wide reading and synthesis to Terra/Sol `[1m]`, contained implementation to Terra, and fixture/gate matrices to Luna. Give every agent an exact model and effort, bounded prompt, explicit artifact, file ownership, and stop condition.

For multi-file independent implementations, one workflow creates one agent per worktree and never points two writers at the same files. Review agents receive immutable commits and acceptance criteria, not mutable worktrees or writer claims. The main conductor alone updates Seeds, adjudicates findings, decides the next wave, and delegates one accepted fan-in to the integrator. A completeness critic runs after synthesis and can open another bounded fan-out round; no recursive fleet is unbounded.

## Workflow capability certification

Before launching any implementation workflow, run a tiny no-op certification matrix for each exact model/effort/context shape the roadmap depends on: Sol `high`/`xhigh`, Terra `xhigh`/`max`, Luna `high`/`xhigh`, with and without `[1m]` where applicable. Capture requested ID, resolved ID, resolved effort, context/fallback signal, output, and failure behavior. If readback is unavailable or `[1m]` silently falls back on a context-heavy lane, fail closed and use a verified smaller-artifact decomposition rather than assuming capacity.

## Capability PR DAG and integration order

No monolithic capability PR or branch is allowed. Each node below is independently reviewed and gated; only siblings share a base, and integrator WIP remains 1.

```text
identity-anchor
├─ R1 role contracts ─┬─ R2 Deep Work Loop
│                     └─ R3 HyperResearch/Research OS
├─ A1 change writing
├─ A2 Git-only sdlc-init ── A3 instructions
├─ G1 Git flow
├─ G2 toolchain/security
├─ J1 jj certification ── J2 jj implementation ── A2j jj init-profile amendment
└─ M0a browser ADR/spike ── M0b foundation
                              ├─ M1 structural types
                              ├─ M2 planning types
                              ├─ M3 quantitative types
                              ├─ M4 technical types
                              └─ M5 conceptual types
                                   └─ M6 router ── M7 conformance
```

After each branch lands on its parent, restack only its descendants and re-gate. Final flagship/README/manifest wiring is split by family (`roles/research`, `init/git/jj`, `Mermaid`) so no review combines unrelated capability implementations. A small final inventory-only PR may cross-link the already-landed families.

Recommended landing order: R1, A1, A2, A3, R2, R3, G1, G2, J1, J2, A2j, M0a, M0b, M1–M5 assembly, M6, M7, then family wiring. If a node fails, restore its recorded pre-landing SHA, preserve the candidate, and create a `SeedProposal`; never repair opportunistically in the integration worktree.

## Release hardening before Evolutionary Core

After the identity cutover and before capability promotion/Core Milestone 2, add bounded release PRs for:

- version policy and compatibility matrix covering mise/uv/Python/Git/PowerShell/OS/architecture/WSL/filesystem/link privilege plus opt-in jj/Mermaid support states;
- reproducible source archive, SHA-256 manifest, GitHub artifact attestation policy, and offline verification bundle;
- clean install, previous-supported upgrade, v1/v2→v3 migration, rollback/uninstall, direct-versus-marketplace identity migration, and failed-upgrade recovery fixtures;
- Blacksmith Ubuntu/macOS/Windows/bootstrap receipts retained as release evidence;
- `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, and support policy;
- promotion receipt that names exact source SHA, artifacts, verification policy, compatibility claims, and known limitations.

Publication/tag/release creation remains separately authorized.

## Evolutionary Core after capability recovery

### Milestone 2: deterministic one-item kernel

Stack A: minimal versioned contracts/journal, deterministic fake, direct `Assignment`, immutable candidate, synthetic independent review, one argv gate, canonical receipt; then Git discovery/common-dir/containment/independent evidence; then lock directories, process/boot identity, fencing, stale-result rejection, and reconciliation.

Stack B after A lands: criterion-level review, sequential integration, target-head preconditions, rollback ref, full gate, receipt verifier; then complete state/outcome table, crash suite, idempotent reconciliation/salvage, and Seeds-to-Assignment projection without making Seeds storage a public ABI.

Acceptance: one reproducible receipt; every interruption resumes or terminates explicitly; stale workers cannot transition; conflicts preserve candidate and target; reconciliation twice is unchanged; fake CI needs no credentials.

### Milestone 3: Claude Golden Wave

Certified direct-Claude adapter, capability readback, 1–3 isolated assignments, exact model/effort and `[1m]` routing, disk-backed artifacts, one repair successor, provider-crash recovery, then a separate idempotent GitHub publication state machine. Prove on Python, JavaScript, compiled-language, and unrelated fixtures across clean/crash/repair/conflict/restart paths.

### Milestone 4: portability and pack lifecycle

Codex conformance against the same contracts/fault suite; third minimal adapter to falsify hidden assumptions; then versioned internal pack manifests with owned inventory, capability declaration, install/update/rollback/uninstall, and conformance. Only then promote CCP/ccodex or jj into Core and consider a public pack ABI.

CCP later is split into a research/certification Seed and an opt-in implementation Seed. Certification requires exact proxy/package version and checksum, loopback-only binding, no traffic logging, user-managed auth outside repos/artifacts, exact model allowlist and `[1m]` stripping/readback behavior. Implementation covers WSL and native Windows alias inventory (`ccodex` and approved Claude-Code aliases), user-initiated shell/config mutation, start/status/stop/update/rollback/uninstall, orphan-process recovery, credential non-copying, and no silent Core dependency or installation.

## Verification and rollback discipline

Every PR/branch declares Seed IDs, merge base, exact paths, tests observed RED then GREEN, `mise run check`, stable-commit independent review, attribution-free artifact text, rollback boundary, and explicitly unauthorized operations.

Every integration records pre-SHA, candidate tip/base, footprint, commit count, gate output, and post-SHA. On failure, restore pre-SHA, preserve candidate/worktree, file a `SeedProposal`, and do not delete branches/worktrees until reachability and open-child use are checked.

Cross-platform gates:

- focused unit/contract tests;
- full Python suite;
- lifecycle self-test;
- `mise run check` on WSL/Linux and native Windows;
- Blacksmith Ubuntu/macOS/Windows after separately authorized push/PR;
- real-host dry-runs before global installation or identity migration.

Mermaid adds detect/parse/render, CLI, inventory, accessibility, and malicious-SVG tests. jj adds fixture repositories for colocation/workspace/recovery/conflict/Git visibility/unsupported features. Identity adds v1/v2/v3 migration and duplicate-install matrix.

## Authorization checkpoints

Implementation approval covers local worktrees, edits, tests, and local commits only. Later explicit gates are required for:

1. exact local fan-in branches/candidates;
2. push to named remote/branch/OID;
3. PR creation;
4. PR mutation;
5. merge of exact current head/base;
6. local checkout directory rename;
7. mise/Codex/user config or trust mutation;
8. GitHub repository rename from `Codeseys-Labs/agentic-sdlc-orchestrator` to `Codeseys-Labs/agentic-sdlc`.

## Immediate execution order after approval

1. Run the model/effort/`[1m]` certification matrix and record verified routing.
2. Repair the two Seeds escape sites and recursive coverage.
3. Review/integrate/re-gate Seeds locally.
4. Delete CAO completely.
5. Implement and land the single cumulative state-v3 + canonical identity cutover PR, including direct-installer and marketplace planes.
6. Complete release-hardening fixtures/docs; return for approval before local directory or GitHub repository rename.
7. Run the explicit capability PR DAG, including jj certification and Mermaid M0a→M7.
8. Integrate each bounded node once through one integrator and land family wiring separately.
9. Begin Evolutionary Core Milestone 2.

## GSTACK REVIEW REPORT

- Full genuine-user transcript audit: 30 human messages recovered from 16,126 JSONL records with `[1m]` agents.
- Repository/identity/jj/roles/skills audits: complete.
- User decisions: CAO deletion, canonical `Codeseys-Labs/agentic-sdlc`, shared role contracts, jj opt-in, and 30-type Mermaid family confirmed.
- Primary-source checks: jj 0.43.0 Git compatibility/operation log/workspaces/conflicts; Mermaid 11.16.0 inventory/API/security/CLI.
- Adversarial plan review: 13 findings received; migration, worktree repair, marketplace, PR DAG, jj handoff, Research OS ownership, Mermaid browser foundation, interactive init, release hardening, model certification, CCP aliases, CAO denylist, and Seeds ranges incorporated.
- Remaining outward gates: push, PR, merge, trust/config mutation, local directory rename, and GitHub repository rename are not authorized by plan approval.
