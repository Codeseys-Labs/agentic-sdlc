# Implementation baseline and branch receipts

## Scope of this receipt

This is a curated receipt of baseline facts recorded in the approved plan and observed in this archive worktree. It is not a release receipt, integration receipt, or authorization to mutate remotes, worktrees, trust, or configuration.

## Baseline

| Fact | Receipt |
|---|---|
| Authoritative base | `origin/main@9432b2c05a20f56e7b893215c90032b7881365bd` |
| Archive branch | `docs/roadmap-archive` at `9432b2c05a20f56e7b893215c90032b7881365bd` before this archive commit |
| Remote recorded by approved plan | `https://github.com/Codeseys-Labs/agentic-sdlc-orchestrator.git` |
| Historical local-main warning | Do not integrate from stale local `main@fa9c249`, tree-equivalent historical feature head `bfee320`, or old installer/knowledge worktrees. |

## Known implementation candidate receipts

The following are historical plan statements, not current certification. “Git-clean” describes only the point-in-time writer observation recorded below. “Writer-reported gate” describes the retained writer output and, for the archive writer, depended on an unauthorized persistent trust mutation; neither phrase establishes independent validation, acceptance, or fan-in readiness. See [the trust incident and Seeds graph provenance receipt](trust-incident-and-seeds-provenance.md) for the evidence boundary and unresolved acceptance blockers.

| Candidate | Tip recorded by approved plan | Historical receipt | Intended role |
|---|---|---|---|
| Seeds toolchain | `feat/seeds-toolchain@30f749c` | Approved plan reports a Git-clean observation and a gate pass; neither is independently rerun or certified by this archive correction. | Pin the reviewed Seeds distribution/toolchain. |
| Seeds execution contract | `feat/seeds-execution-contract@db0e860` | Approved plan reports a Git-clean observation and a gate pass, and records two remaining bare-call repairs; neither is independently rerun or certified by this archive correction. | Complete exact Seeds execution enforcement before any future integration review. |
| Archive documentation | `docs/roadmap-archive` from the authoritative base | Historical archive workstream. Its writer-reported gate was trust-dependent; later corrective verification is separately classified in the incident receipt. | Preserve plans, decisions, canonical Seeds, and routing evidence. |

## Planned integration boundary

The approved plan names `integration/seeds-0.5.14` as a future integration branch from `9432b2c`. Its integrator is to validate exact non-overlapping ranges, recompute footprint and commit counts after the final execution repair, independently review the immutable result, and re-run the full gate. This is a planned receipt shape, not evidence that fan-in occurred.

## Archive inputs retained in repository

- [Canonical Seeds store](../../.seeds/issues.jsonl), including all epics, work items, statuses, and direct dependency fields at archive commit time.
- [Merge driver attributes](../../.gitattributes) for the canonical JSONL records.
- [Approved plan](approved-plan.md), [recovered predecessor](superseded-plan.md), and [routing certification](workflow-routing-certification.md).

No raw transcripts, private configuration, credentials, or temporary artifact paths are copied into this repository.
