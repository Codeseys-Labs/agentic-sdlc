# Define the downstream repository activation and hygiene contract

Type: grilling
Status: resolved
Blocked by: 01, 05, 07, 08
Parent: [Find the path to a Claude Code-first Agentic SDLC product](../map.md)

## Question

What does the harness add, adopt, verify, or refuse when activating a greenfield or brownfield
repository? Set the contract for AGENTS guidance, Seeds or another queue, ADR and domain context,
mise, lefthook, betterleaks, CI, worktrees, trust, foreign files, idempotence, recovery, and the
minimum evidence required before a workflow may write.

## Answer

### Assess, plan, and apply

`/sdlc-init` always begins with a read-only assessment and produces a digest-bound activation
plan. Greenfield and brownfield describe the repository's existing operating contract, not the age
of its application code. Greenfield means no established guidance, toolchain, tracker, hook, or CI
contract occupies the relevant surfaces; it receives a proposed complete opinionated baseline.
Brownfield means at least one such contract exists; it receives minimum-compatible integration and
prioritized hygiene waves rather than replacement.

The plan classifies each destination as absent, owned, compatible foreign, conflicting foreign, or
modified owned. It shows exact changes, trust actions, recovery, rollback, egress, and ownership
before mutation. Applying the exact digest requires explicit approval. Foreign or ambiguous state
is preserved; activation never silently adopts, merges, rewrites, or deletes it.

A repeated assessment is read-only and should be deterministic when its inputs are unchanged.
Mutation does not claim intent-level idempotence: it uses exact prestate checks, durable receipts,
and crash-consistent transitions. Interrupted or unknown-effect work stops and requires an explicit
recovery plan rather than silent repair.

### Guidance, queue, decisions, and language

`AGENTS.md` is the canonical host-neutral repository operating contract. An owned `CLAUDE.md` is
its compatibility projection: a symlink where supported or a verified identical copy otherwise.
Claude-specific configuration belongs under `.claude/`, not in competing general guidance.
Existing foreign instructions are preserved; activation records precedence and proposes explicit
reconciliation with a hygiene queue item.

Agentic SDLC defines an authoritative-queue contract rather than requiring one tracker. Seeds is
the greenfield default until the operator selects another adapter. A brownfield tracker remains
authoritative when its adapter proves identity, status, dependencies, acceptance, evidence, and
concurrency behavior. Activation never creates a shadow queue, duplicates existing issues, or
treats chat/TODO memory as durable work. Seeds bootstrap is a separate receipt-backed mutation; an
inadequate existing tracker leaves activation read-only until a migration or compatibility plan is
approved.

Greenfield architecture decisions use `docs/adr/` with a MADR-compatible lifecycle and index.
Brownfield repositories retain an established location, numbering, and template when the adapter
preserves equivalent lifecycle and relationship evidence. An ADR requires a significant,
hard-to-reverse trade-off; it is not a status report. `CONTEXT.md` is the canonical domain glossary
and is created lazily when meaningful terms exist. Existing records are preserved rather than
wholesale reformatted. Plans, queue items, commits, and receipts link to decisions.

Controlled-English, BLUF, SimpleEnglish, and ASD-STE100-inspired documentation rules are decided
by the separate documentation-defaults ticket; activation records the chosen writing profile but
does not claim ASD-STE100 conformance prematurely.

### Repository toolchain and gates

Every activated repository exposes `mise run check` as its authoritative local gate. Mise pins and
composes existing native commands without replacing language package managers. Greenfield
activation proposes pinned mise configuration, lefthook, betterleaks, and appropriate
validate/test/secrets/check tasks. Brownfield activation preserves and wraps existing gates, then
adds missing hygiene through reviewable waves.

Lefthook supplies fast pre-commit and broader pre-push subsets but is not release authority.
Betterleaks uses a tracked, extend-only ruleset; full-history scanning remains separately approved.
CI calls the same pinned authoritative gate rather than maintaining divergent versions. Every
linked worktree reviews and trusts its exact mise config path separately. `/sdlc-init` never
persists trust or changes global mise configuration without operation-specific approval.

### Portable intent and local evidence

The tracked `.agentic-sdlc/repo.toml` records portable intent: schema version, canonical guidance,
queue adapter, ADR/glossary locations, authoritative gate, worktree and integration policy, CI
expectation, and enabled writing/profile rules. It is not proof of local ownership or readiness.

User preferences live under `${XDG_CONFIG_HOME:-~/.config}/ccodex/`; activation receipts and
recovery journals live under `${XDG_STATE_HOME:-~/.local/state}/ccodex/`; disposable catalogs and
downloads live under `${XDG_CACHE_HOME:-~/.cache}/ccodex/`. Claude-owned login, settings, and
plugin entries remain under `~/.claude/`. Each physical clone and linked worktree has a separately
keyed local receipt binding its identity, approved plan, owned paths and hashes, tool versions, and
trust evidence. A fresh clone sees portable intent but must establish its own receipt.

### Work custody and fan-in

Read-only assessment, planning, research, and review need no worktree. Every parallel write-capable
workstream receives one owner, branch, and dedicated worktree; workers never share or mutate
another's checkout. Before planning writes, the conductor inventories dirty, staged, untracked,
ignored, and overlapping paths and preserves user work. Overlap blocks or is explicitly isolated.
A bounded single-owner task may use the current checkout only through an approved no-worker wave.
Repository activation itself is a lifecycle mutation, not an implementation workstream.

The default integration strategy is rebase-then-squash fan-in. One authorized integrator rebases
an accepted workstream onto the current integration base, re-admits and rechecks the changed
identity and delta, then squash-merges it as one traceable unit. The integrated snapshot receives
authoritative gates and adversarial review. Repository policy in `.agentic-sdlc/repo.toml` may
override the strategy; existing branch protection and merge rules always apply. Outward merge to
a protected/default branch requires separate authorization.

### Write admission

Activation distinguishes two honest readiness states:

- **write-ready** — the receipt matches portable intent, custody is clear, guidance and queue are
  admitted, trust is valid, and `mise run check` passes. Normal delivery waves may write.
- **remediation-ready** — exact known brownfield failures are baselined, but the repository is not
  write-ready. Only named hygiene/remediation waves may write.

Credential exposure, ambiguous ownership, unsafe trust, or conflicts in target paths block both
states. A remediation wave addresses only named failures, passes its focused gates, does not worsen
the global failure set, and records exact improvement. Its verdict is `remediation-progress`, never
`repository gate-passing`; push, release, merge, and deployment remain blocked until write-ready.
Every remaining failure is represented in the authoritative queue with ownership and evidence.
