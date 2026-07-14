# Superseded plan (recovered)

> **Archive status:** best recoverable copy of the plan immediately superseded by the approved recovery-and-expansion rewrite. It is retained as a historical reference, not current direction.
>
> **Provenance:** reconstructed from the direct `Write` payload at 2026-07-12T17:16:15Z and the successful direct `Edit` payloads that followed it in the local session record. The final successful edit was at 2026-07-12T17:32:19Z. Failed edits were excluded. The later direct `Write` at 2026-07-14T04:44:52Z replaced this plan with the current approved plan.
>
> **Limitations:** this is a reconstruction of tool payloads, not an independently versioned file snapshot. It intentionally excludes session metadata, tool output, model commentary, user-message quotations, and the source generator attribution to preserve the archive’s attribution-free policy. Its historical repository/branch/owner references may be stale.

---

# Design and Implementation Plan: Agentic SDLC Evolutionary Core

Branch: `feat/mise-cross-host-installer`
Repo: `baladithyab/agentic-sdlc-orchestrator`
Status: DRAFT — awaiting approval
Mode: Builder

## Context

The repository has grown from one orchestration skill into a bundle of Claude/Codex commands, role agents, research roles, installation scripts, and SDLC doctrine. The installation work exposed the larger opportunity: make **Agentic SDLC** an open, provider-portable platform that can reliably carry bounded work from initialization through an independently verified pull request.

The product should eventually support provider packs, Deep Work Loop/HyperResearch, CCP/ccodex, Git/jj substrates, security/toolchain packs, Mermaid guidance, and generated hierarchical instructions. It should not freeze those ideas into a public kernel ABI before one end-to-end path is demonstrably reliable.

The recommended architecture is an **Evolutionary Core**: complete distribution safety, build a narrow Golden Wave reliability kernel, prove it with Claude Code, prove portability with Codex, then promote interfaces only after conformance evidence exists.

## Product Definition

### Name and compatibility

- Public product and documentation name: **Agentic SDLC**.
- Keep `agentic-sdlc-orchestrator` as the canonical compatibility slug for the first migration release so existing links, plugin IDs, commands, and automation continue to resolve.
- Add `agentic-sdlc` as an alias/redirect where supported; never install two independently owned copies of the same payload.
- Deprecate legacy names in status output and documentation before changing canonical on-disk IDs.
- Flip the canonical slug only after duplicate-install detection, rollback, and host-by-host upgrade tests pass.

### Narrowest useful wedge: Golden Wave

```text
install → init → frame → 1–3 isolated workers → review
        → sequential integration → full gate → PR → clean uninstall
```

Public run shapes remain **Frame**, **Wave**, and **Mission**. Sol/Terra/Luna are provider/model bindings, not product modes.

### Initial non-goals

- Universal provider runtime or arbitrarily recursive workflows.
- Stable public third-party pack ABI before two real adapters pass conformance.
- Concurrent integration or multiple merge owners.
- jj as a hard dependency or replacement for Git interoperability.
- Bundling CCP, DWL, HyperResearch, Mermaid, or every tool into Core.
- A daemon, database, or event bus when files plus Git provide sufficient durability.

## Architectural Premises

1. Git is the interoperability baseline.
2. One write-capable worker owns one workspace; one integrator owns fan-in.
3. Review immutable candidates, not worker claims; recompute Git and gate evidence.
4. Mutable run state lives under the Git common directory so all worktrees share one authority.
5. Checked-in `.sdlc/` expresses repository intent; mutable `.git/sdlc/` records local execution.
6. Seeds starts as queue authority behind a thin projection, not as permanent public kernel ABI.
7. Provider adapters remain internal until proven; unsupported capabilities fail explicitly.
8. Core sees capability profiles, never provider model names. Certified Claude profiles may bind Sol/Terra/Luna (and `[1m]` client context where supported), but direct Claude is the Milestone 3 baseline and no Core path requires CCP.
9. Large workflow artifacts are disk-backed; typed returns remain small. Persist only a redacted `PromptSpec` (template/version, input artifact hashes, secret references, rendered-prompt hash), never credentials or unrestricted raw prompts. Delegation is capped at conductor → bounded coordinator/worker → leaf.
10. Recovery is a core feature: transitions are replayable, fenced, and reconcilable.

## Recommended Architecture

```text
/sdlc-* commands and future `sdlc` CLI
                    │
                    ▼
        Golden Wave reliability kernel
  run state · leases/fencing · path containment
  immutable candidates · independent Git evidence
  review · bounded repair · sequential integration
  repository gates · recovery/salvage · receipts
                    │
             internal adapters
       deterministic fake / Claude / Codex
                    │
           Git worktree substrate
        (jj workspace substrate later)
```

### Intent and execution state

Create only the files the kernel needs:

```text
.sdlc/
  config.toml     # schema, default adapter, limits
  gates.toml      # named commands/timeouts; no secrets
  packs/          # internal manifests, after Milestone 3

<git-common-dir>/sdlc/
  runs/<run-id>/
    spec.json
    journal.jsonl
    assignments/  candidates/  evidence/
    reviews/      gates/       receipts/
  leases/
  integration.lock
```

- Version every persisted document; reject unknown versions.
- Write snapshots atomically and journal monotonic transitions.
- Never persist credentials, complete prompts, or provider auth state.
- Leases use process identity plus random fence tokens; stale owners cannot commit later transitions.
- Resolve all owned paths beneath approved repository/worktree roots.
- Use a simple exclusive file/lock-directory protocol with reconciliation, not a database.

### Candidate boundary

A worker claim becomes reviewable only after Core records assignment/criteria IDs, workspace and merge base, exact commit/tree, independently observed changed paths, gate commands/results/artifact hashes, and the current lease/fence identity. Candidates are immutable; repair creates a linked successor candidate.

### Private versioned contracts

Start these as internal validators/data structures, not a public SDK:

- `RunSpec`
- `Assignment`
- `WorkspaceRef`
- `CapabilitySnapshot`
- `CandidateRef`
- `GateResult`
- `ReviewVerdict`
- `IntegrationReceipt`

Invariants belong in validators and transition functions, not prose alone.

### State machine

```text
planned → leased → running → candidate_ready → reviewed
       → accepted → integrating → integrated
integrated → gating → receipted | gate_failed
integrated → ungated

running → timed_out | cancelled | retry_exhausted | abandoned
reviewed → rejected | repair_requested
repair_requested → leased → running
integrating → integration_conflict | interrupted
integration_conflict → reconciling | failed
accepted | integrating | integrated | gating → interrupted → reconciling
reconciling → leased | running | candidate_ready | accepted | failed | salvaged
```

Only conductor/integrator code advances integration states. Every transition validates predecessor state, candidate identity, and fence token. Preview policy allows one bounded repair round. Milestone 2 must ship a closed reconciliation/outcome table. `receipted` is validated success (exit 0). `rejected`, `retry_exhausted`, `gate_failed`, `integration_conflict`, `timed_out`, `cancelled`, and `abandoned` are explicit non-success outcomes (exit 1) with a mandatory `RunOutcome` artifact and preserved recovery pointers. `failed` is unrecoverable/corrupt execution (exit 2) with an error record. `salvaged` means useful immutable candidates/evidence were retained but no integration success is claimed (exit 1). An explicitly gate-less run ends `ungated` (exit 1), never `receipted`, cannot be certified, and is not auto-published. The table defines automatic recovery, operator actions, cleanup ownership, and terminal artifact for every state.

Lease acquisition uses an atomic same-filesystem directory create. The creator writes a complete record to a sibling temporary file, fsyncs where the platform supports it, then atomically renames it into the newly acquired directory; an empty/partial directory is never a valid lease and is handled only by serialized reconciliation. Its record contains a random fence token, host/process identity, boot identity and process-start identity where exposed, workspace identity, and last-renewed monotonic observation. Time alone never proves staleness: takeover first acquires a separate atomic reconciliation lock, compares the last complete record, verifies process/boot identity and workspace state, then writes a new fence token. Local NTFS/APFS/ext4-style filesystems are the initial support target; network/shared filesystems are unsupported until their atomicity semantics pass the matrix. Platform-specific probes sit behind one tested stdlib interface; unsupported identity checks require explicit operator takeover rather than guessing.

### Review, gates, and integration policy

- A reviewer must be a separate execution from the writer and receives the immutable candidate plus acceptance criteria, not the writer’s mutable workspace. The same provider may review only as a separate role/session; certified profiles state whether cross-model review is available.
- `ReviewVerdict` contains reviewer identity/profile, candidate ID, criterion-level decisions, findings with evidence, and `accept | repair | reject`. Any blocking criterion requests repair or rejects; Core never infers acceptance from prose.
- Initial integration strategy is a clean 3-way apply/cherry-pick of the accepted candidate onto a clean integration branch owned by the integrator. Preconditions include unchanged target head, candidate ancestry/merge-base evidence, clean worktree, and allowed-path footprint. Conflicts create `integration_conflict`; no worker resolves them in place. Rollback restores the recorded pre-integration ref, then revalidates it.
- Gate precedence is: explicit `.sdlc/gates.toml`; otherwise a detected existing repository authority such as `mise run check`; otherwise initialization requires the user to choose a command or explicitly record no gate. Gate commands are argv arrays, never shell strings. Core never invents language-specific commands. An explicit no-gate choice produces only the `ungated` outcome described above. Receipts record the exact argv, cwd, sanitized environment fingerprint, timeout, exit result, log digest, and candidate/integration identity.
- Running repository gates executes repository code. Consent is bound to repository identity/common-dir/root plus the digest of gate policy and exact argv. Any executable-policy change invalidates consent and re-prompts; noninteractive execution fails closed. Trusting orchestration metadata never implies consent to run repository commands. Execution uses argv-only subprocesses, a scrubbed allowlist environment, output/time/size limits, symlink-safe artifact access, and redaction before persistence or publication.

### Adapter boundary

Adapters accept a versioned request (`request_id`, `attempt_id`, `assignment`, immutable input artifact references, capability/profile ID, deadline, cancellation token, workspace reference, fence token) and return a versioned result (`request_id`, `attempt_id`, provider run ID, status, artifact references/hashes, timing/usage metadata, typed error). Dispatch itself is write-ahead: `dispatch_intent → started(provider_run_id or supervised process identity) → completed`. Intent is durably recorded before spawn. An adapter may redispatch only when the provider offers a queryable idempotency key or Core’s supervised local process record proves no process/provider run started; an indeterminate attempt is never blindly replayed and requires reconciliation/operator action. Replaying a started request/attempt is observational; a retry creates a new attempt under the current fence while retaining lineage. Status and errors are closed enums; unknown values fail closed. Adapters may start/resume/cancel one bounded assignment, collect provider metadata/artifact pointers, and report capabilities. Cancellation is cooperative until the deadline, then Core terminates the owned process tree and records `cancelled` or `timed_out`; a late result with an old fence token is evidence only and cannot transition the run. They never decide acceptance, integration, queue disposition, publication, or final success. Core owns leases, Git evidence, candidates, reviews, gates, integration, recovery, and receipts.

Publication is a separate post-receipt state machine: `publication_planned → branch_pushing → branch_pushed → pr_creating → published`, with `publication_failed` and `publication_reconciling`. Versioned `PublicationRequest`, `PublicationResult`, and `PublicationReceipt` include request/attempt IDs, receipt ID, remote/forge identity, branch/ref, and a forge-visible idempotency marker (run/receipt ID in branch/PR metadata). Intent is persisted before push or PR creation. On restart, reconciliation queries the remote branch and PR marker before retrying, so a crash after a successful side effect does not duplicate it. Kernel success ends with a validated integration branch and receipt. Publication uses user-owned forge authentication without copying credentials; missing remote/auth/supported forge returns a successful branch-only kernel outcome plus instructions, not false kernel failure.

Implement a deterministic fake first, including scripted success, timeout, crash, stale completion, malformed output, and retry. Claude and Codex must later pass the same transition/fault suite.

## Milestone 1 — Distribution, Identity, and Safety

### Integrate existing isolated work

Create a clean integration branch/worktree from current `origin/main`, then use one integrator:

1. Integrate core installer commit `02befde8f9d4897bdb544156d00a147e83abc043`.
2. Inspect and finish the bridge worktree changes in `mise.toml`, `scripts/run-windows-mise.ps1`, and `scripts/install-skill-bundle.sh`; validate and commit the lane.
3. Integrate tooling commit `a352ffa5bc729a777a84bab528e98a8b831a85de`.
4. Integrate docs commit `7ebd7e8ff41d25267d016e3002e3f94f7aaf76e5`.
5. Reconcile cross-lane CLI/task names and rerun all gates on the assembly.

Review each commit’s merge-base footprint before applying it. Do not push without explicit authorization.

### Installer contract

Retain the stdlib-only chain:

```text
mise → pinned uv → uv-managed Python 3.12.11 → installer
```

Operations:

```text
install | status | uninstall | self-test
--agent all|claude|codex
--mode auto|link|copy
--dry-run
--home PATH
--codex-home PATH
```

Requirements:

- Before any destination mutation, append and durably flush a transaction intent containing transaction ID, plane, target, prior target kind/link target/content digest, staged/backup paths, and intended ownership. Then prepare and verify the staged entry, perform the platform-specific replace, append the commit marker, and update ownership state. Recovery uses intent+commit markers to finish or restore every crash window, including “target changed but ownership not appended.”
- Files and links use same-directory temporary entries and atomic replace where the OS guarantees it. Unix directories use rename with a same-filesystem backup. Windows non-empty directory/junction replacement is a recoverable two-rename sequence under the plane transaction lock; if either rename is unavailable (sharing/permission/filesystem semantics), leave the original untouched and report degraded copy/conflict rather than claiming atomicity. Fsync directory metadata where supported; on platforms without a durability primitive, document crash-consistent recovery rather than power-loss durability.
- Classify ownership as `created`, `adopted-link`, `preexisting-identical`, or `refreshed-copy`. `created` and unchanged `refreshed-copy` entries are removable; adopted/pre-existing entries are retained on uninstall unless the installer saved and can atomically restore their exact prior provenance.
- Stage each destination replacement beside its target, verify it, atomically swap it, and append ownership state. On interruption, the next lifecycle command reconciles staged/backup entries before new work. `--agent all` is per-plane transactional: a Claude conflict may produce partial status while the independent Codex plane still completes; within one plane, failed changes roll back to the recorded pre-install state.
- Never replace `skills`, `agents`, or `commands` collection roots.
- Adopt only exact legacy links or byte-identical copies; preserve foreign, retargeted, and modified entries.
- Refresh only unmodified owned copies.
- Unix: symlink then copy. Windows directory: junction then copy. Windows file: symlink then copy.
- Version and atomically write per-host ownership state; dry-run writes nothing.
- Detect direct-Claude/marketplace conflict per plane without blocking unrelated Codex work.
- WSL invokes native Windows through absolute System32 PowerShell and native `mise.exe`; it never makes Linux links in Windows homes.

### Bootstrap, release, and compatibility contract

- Source installs run from a checked-out tagged repository: install mise through its official platform path, verify `mise --version` against the support matrix, then run `mise trust` and `mise run bundle:install`. Release automation publishes a source archive, SHA-256 manifest, and GitHub artifact attestation from one pinned release workflow. Verification checks subject digest plus repository, GitHub Actions issuer, exact release workflow identity, expected `refs/tags/<version>`, and the tag’s commit SHA (using `gh attestation verify` plus policy checks against the attestation JSON), then checks the manifest; any mismatch fails closed. Offline installation requires the archive, manifest, attestation bundle, certificate/transparency evidence, expected tag/SHA, and the repository-owned verification policy captured while online; the same subject/workflow/ref/issuer checks run without network. Do not invent a curl-pipe-shell bootstrap.
- Pin mise’s uv plugin/tool version, uv, and Python in repository configuration. Cached/offline operation is supported only when mise/uv/Python and the verified source archive are already present; proxies use mise/uv’s documented environment configuration.
- Version ownership/run schemas and provide explicit forward migration. Older binaries must refuse newer schemas without mutation. Upgrade tests cover previous-supported → current and failed-upgrade rollback from saved state/entry backups; no silent downgrade writes.
- Publish a versioned matrix covering minimum/tested mise, uv, Python, Git, PowerShell, OS/architecture, WSL interop, filesystem/case behavior, Windows long paths, and symlink/junction privilege. Each tuple is `supported`, `degraded-copy`, or `unsupported`.
- Preview and stable releases are tagged artifacts. Promotion requires clean install, upgrade from the previous supported release, rollback/uninstall, artifact-integrity verification, and retained CI receipts. Provider credentials are never placed in CI for required hermetic gates; scheduled certification uses scoped secret stores.

### Identity and policy

- Update public prose to Agentic SDLC while retaining compatibility IDs.
- Add migration/rollback and duplicate-install tests before canonical-slug change.
- Publish truthful support, security, contribution, and license documents.
- Make root `AGENTS.md` the canonical shared policy and root `CLAUDE.md` a thin import plus Claude-specific rules. Defer hierarchy generation to its later pack.

### Exit gate

- Direct bootstrap validator, unit tests, self-test, and `mise run check` pass.
- Isolated WSL and native Windows install/status/refresh/uninstall pass.
- Real-home dry-runs show no foreign overwrite.
- WSL Claude, WSL Codex, Windows Claude, and Windows Codex installations are inventoried and verified.
- Uninstall removes only owned entries.
- CI covers Ubuntu, macOS, Windows, and a bootstrap lane.

## Milestone 2 — One-Item Deterministic Reliability Kernel

### Build sequence

1. Add a minimal stdlib Python `sdlc` walking skeleton in the first kernel PR: thin versioned contracts/journal, direct `Assignment`, fake execution, immutable candidate, synthetic independent review, clean integration, one configured gate, and canonical receipt. Reuse installer path, atomic-write, digest, and exit conventions where suitable. Later PRs harden rather than postpone these layers.
2. Implement Git discovery, common-dir resolution, containment, and capability detection.
3. Define field-level schemas, canonical JSON/prompt rendering, stable IDs/hashes, strict validation errors, and golden fixtures for every internal contract. Retain immutable prompt template and non-secret input artifacts content-addressed within the run bundle. On restart, resume the recorded provider run when possible; otherwise rerender and require the saved prompt hash to match. A mismatch or rotated secret reference creates a new fenced attempt or requires operator intervention, never silent continuation.
4. Prototype and test Unix/Windows process identity and atomic lock-directory primitives, then implement journal, run locking, leases, and fencing behind one interface.
5. Implement one workspace lifecycle: claim, execute, capture immutable candidate, release.
6. Derive candidate evidence independently from Git.
7. Record review verdict, integrate sequentially, run the full repository gate, emit `IntegrationReceipt`.
8. Reconcile every active state at startup with explicit resume/salvage/failure outcomes.
9. After the direct-assignment fault suite passes, add the Seeds-to-`Assignment` projection without coupling kernel schema to Seeds storage.

### Fault suite

Stage fault coverage rather than blocking the first vertical slice on the full matrix: (A) transition legality/validator tests, (B) deterministic crash points around journal/snapshot/receipt boundaries, then (C) platform-specific process, filesystem, Git mutation, fencing race, and integration recovery tests. Use real temporary Git repositories and subprocesses for duplicate resume, stale late worker, PID disappearance/reuse, corrupt/unknown state, moved candidate branch, out-of-policy path, gate timeout/failure/signal, integration conflict/interruption, interrupted receipt write, and idempotent reconciliation.

### Exit gate

One deterministic assignment reaches a reproducible receipt. Every injected interruption resumes safely or produces an explicit recoverable outcome. Stale workers cannot mutate current state or be accepted. Reconciliation/finalization is idempotent.

## Milestone 3 — Claude Code Golden Wave Preview

1. Add a Claude adapter for one exact certified direct-Claude Code/version/model/OS tuple; CCP is not a prerequisite.
2. Map capability discovery into `CapabilitySnapshot`; fail clearly on unsupported requests.
3. Use native Claude delegation as baseline. Dynamic Workflow may exist inside one bounded assignment, never own the project queue or integration.
4. Put model routing in the certified Claude profile, outside Core. Where the environment exposes them, bind Sol `[1m]` to frame/plan/settled-truth/final verdict, Terra `[1m]` to implementation/research/review, and Luna `[1m]` only to mechanically gated work. A direct Anthropic profile uses its certified native model IDs; CCP-specific aliases/suffix behavior belongs only to the later CCP profile.
5. Exchange disk artifacts plus small typed pointers; cap depth, retries, and review passes.
6. Schedule 1–3 non-overlapping assignments, one writer/worktree each.
7. Review exact immutable commits, allow one repair successor, then integrate sequentially.
8. Re-run the complete repository gate and create one receipt/PR.
9. Reconcile provider crash, missing summary, orphan workspace, late completion, and salvageable candidate.

Publish exact support tuples rather than claiming universal compatibility.

### Exit gate

At least three fixture repositories and one unrelated repository complete Golden Waves, with evidence for a clean run, worker crash, review repair, integration conflict, and conductor restart. No success exists without a reproducible receipt and PR/branch identity.

## Milestone 4 — Portability Proof and Pack Boundary

### 4A: Codex conformance

Add a Codex adapter implementing the same internal operations and fault suite. Run fake, Claude, and Codex through one conformance harness. Make capability matrices machine-readable and fail closed.

### 4B: contract falsification

Build a third minimal adapter prototype to expose hidden two-provider assumptions; it need not ship. Revise internal contracts until the prototype requires no provider-specific kernel authority.

### 4C: internal pack experiments

Only after 4A/4B, introduce internal first-party manifests for already-existing capabilities: identity, version, requirements, owned files, lifecycle hooks, and conformance declaration. Publish fixture repositories, scripted doubles, lifecycle/fault tests, and receipt validation as a conformance kit. Promote only interfaces stable across these implementations; keep the remainder experimental.

### Exit gate

Claude and Codex pass the same Golden Wave/recovery suite. The third prototype requires no unexamined kernel-authority changes. Pack install/update/rollback/uninstall proves ownership. Only then consider a versioned public pack ABI.

## Non-Normative Roadmap: First-Party Packs After Portability Proof

The following are direction and graduation gates, not Core requirements or Milestone 1–4 implementation scope. Core has no dependency on any of them.

### CCP/ccodex

Pin exact proxy version/checksum; bind loopback only; disable traffic logging; keep authentication user-initiated and outside repos/prompts/artifacts; enforce model allowlist and certified tuples; document that `[1m]` is a Claude client context/compaction request stripped before CCP upstream routing; provide start/status/stop/update/rollback/uninstall and orphan-process tests. Never copy credentials. CCP is promoted but not silently installed with Core.

### jj substrate

Remain Git-conformant. Add colocated jj workspaces only after Git recovery tests pass. Preserve Git-visible candidates/receipts and account for auto-snapshot, op-log, committed conflict state, headless identity, and Git hooks not firing. Require `mise run check`/CI independently.

### DWL and HyperResearch

Contribute orchestration/research policy, not a second queue authority. Keep Frame/Wave/Mission public. Cap nested delegation; nested workflows cannot integrate or disposition Seeds. Graduate after artifact, cancellation, crash, and limit behavior passes conformance.

### Toolchain/security

Expose mise/lefthook/betterleaks and repository gates as declarative opt-in capabilities. Prefer existing tools over wrapper skills. Put hard guarantees in hooks/settings/CI and receipt evidence.

### Mermaid

Use one router skill with per-type references. Pin Mermaid and use `detectType` → `parse` → render with strict security for untrusted input. Validate published diagrams in CI.

### Instruction generation

Use one manifest to generate/validate root `AGENTS.md`, thin `CLAUDE.md`, subtree `AGENTS.md`, and `.claude/rules/*.md` path rules. Preserve hand-authored sections with generated markers; enforce hard rules in hooks/CI.

### Research OS scaffolder

Install the 17-role Codex research roster per repository, never globally. Integrate through assignments/artifacts, not direct kernel state mutation.

## Delivery Doctrine

- One branch/worktree (or later jj workspace) per assignment; one writer each; one integrator per run.
- Parallel PRs for independent changes; stacked PRs only for dependencies, normally 2–4 deep, landed bottom-up.
- After squash-merged parents, restack descendants and rerun full gates.
- Use `--force-with-lease`, never blind force.
- Worker-green is not integration-green: inspect merge-base footprint and re-gate assembled state.
- Keep commits bisectable: rename, behavior, tests, generated output, and docs remain logical units.

Suggested core stack after Milestone 1:

1. `core-one-item-walking-skeleton` (thin contracts, journal, fake run, candidate, review, gate, receipt)
2. `core-workspace-leases-and-fencing`
3. `core-fault-and-reconciliation-hardening`
4. `candidate-review-integration-receipt-hardening`
5. `claude-golden-wave-preview`
6. `codex-portability-conformance`

Do not stack later packs behind this chain.

## Dated Repository Baseline (2026-07-12)

- Target repository and `origin/main`: `fa9c249e806bae92fad9c673a4bfc0b91cd09edd` on `feat/mise-cross-host-installer`.
- Core commit `02befde8...`: 2 new files, 669 lines (`scripts/install_skill_bundle.py`, `tests/test_install_skill_bundle.py`).
- Tooling commit `a352ffa5...`: `.github/workflows/validate.yml`, `lefthook.yml`, `mise.toml`, `scripts/validate-bundle.sh` (141 additions/183 deletions).
- Docs commit `7ebd7e8f...`: `AGENTS.md`, `README.md` (102 additions/71 deletions).
- Bridge worktree is uncommitted and currently modifies `mise.toml` and `scripts/install-skill-bundle.sh`, adds `scripts/run-windows-mise.ps1`, and also contains untracked copies of the core installer/tests. Before committing, compare those untracked files byte-for-byte with `02befde8`; discard only proven duplicates from the bridge commit. The known assembly conflict is `mise.toml` between bridge and tooling; resolve task names against the installer CLI, never accept one lane wholesale.
- Observed gate authorities: `scripts/validate-bundle.sh`, Python `unittest`, installer `self-test`, and `mise run check`. Milestone 1 must make `mise run check` compose the other authoritative gates without requiring a prior global installation.

## Verification Strategy

- **Distribution:** named tests `bootstrap-validate`, `isolated-copy-lifecycle`, `isolated-link-or-junction-lifecycle`, `foreign-entry-preserved`, `owned-entry-refresh`, `all-four-planes-dry-run`, and `owned-only-uninstall`; direct validator, stdlib tests, self-test, `mise run check`, Ubuntu/macOS/Windows CI. A machine-readable inventory must equal discovered payload entries for each plane and report zero unexpected removals.
- **Kernel:** golden contract fixtures plus `one-item-receipt`; transition-table tests; real temporary Git repositories; subprocess fault injection; `restart-every-state`, `stale-fence-rejected`, `integration-conflict-preserved`, and `reconcile-twice-no-change`. A canonical receipt manifest includes every artifact/policy/config digest, repository/common-dir identity, immutable Git object bundle or immutable remote refs, tool/provider tuple, verifier version/argv, and optional attestation. The sanitized content-addressed run bundle is retained with CI/release artifacts according to release policy. “Reproducible receipt” means an independent verifier can validate that bundle, immutable commits, transitions, gate results/log hashes, and integration refs; it does not require a model to regenerate identical output.
- **Providers:** shared fake/Claude/Codex conformance; capability mismatch, timeout, cancellation, late/malformed output, and upgrade tests; exact version tuple in evidence. Required CI is hermetic and fake-backed. Credentialed certification runs at least weekly and before preview/stable promotion; evidence older than 7 days or missing any required clean/crash/timeout/cancel/late-result scenario for a claimed tuple blocks promotion. Retain certification bundles in the tagged workflow run/release artifacts.
- **Adoption:** named fixture repositories for at least Python, JavaScript, and one compiled language, plus one unrelated repository not authored for Agentic SDLC. Each must produce the standard sanitized artifact bundle and pass an independent receipt verifier. Kernel success is branch+receipt; `github-publication` separately verifies idempotent PR creation when auth/remote exist.
- **Security:** traversal/symlink escape, state tampering/version refusal, secret scans over artifacts, safe argv passing, environment scrubbing, untrusted gate consent, output limits, fence races, and CCP lifecycle/auth/binding tests before that pack releases.

## Success Criteria

A user with only mise can install Agentic SDLC, initialize an ordinary Git repository, execute a bounded 1–3 worker Wave through Claude or Codex, inspect immutable evidence/reviews, recover from interruption, and receive a validated integration branch plus reproducible receipt. With a supported forge remote and user authentication, a separate idempotent publication step adds the PR. Uninstall never removes unrelated or merely pre-existing configuration.

Expansion earns promotion only after lifecycle, conformance, recovery, and external-repository evidence. The platform may be broad; Core remains small.

## Immediate Order After Approval

1. Finish, validate, commit, and review the bridge lane.
2. Integrate the four installer lanes with one integrator.
3. Run isolated and real-home dry-runs, then install all four host/tool planes.
4. Complete Milestone 1 identity/policy gaps without changing the canonical compatibility slug.
5. Open the first kernel PR as the one-item walking skeleton (contracts, journal, fake execution, candidate, synthetic review, integration gate, canonical receipt).
6. Do not implement CCP, jj, research, diagram, instruction, or public pack ABI work before their graduation gates.

## What I Noticed About How You Think

- You kept returning to the end-to-end system rather than accepting a narrow installer as the product: “do you see my vision?” The useful translation is a broad destination with evidence-gated releases, not a broad first kernel.
- You challenged sequential execution and asked why multiple agents were not being used. That exposed both the safe pattern, one writer per worktree, and the actual failure modes: oversized prompts, shared roots, and premature fan-out.
- You connected mise, uv, jj, lefthook, DWL, HyperResearch, CCP, Mermaid, and hierarchical instructions as one developer operating system. The constraint that keeps it coherent is that packs contribute capabilities while Core alone owns evidence, integration, and recovery.
- You chose “Evolutionary Core,” preserving the ambition while requiring each expansion to earn permanence through conformance evidence.
