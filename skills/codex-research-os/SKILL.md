---
name: codex-research-os
description: Bootstrap and operate a Codex-native autonomous research operating system in a repository. Use when a user asks to create, install, formalize, package, reuse, or run a disciplined research team setup with specialist agents, persistent memory, claim ledgers, experiment tracking, literature discovery, ablation workflows, strict review gates, greenfield/brownfield research loops, reusable workflows, or continuation state across projects/repos.
---

# Codex Research OS

## Overview

Use this skill to install or run a portable research organization inside a repo: a director, specialists, persistent ledgers, workflows, review gates, and scripts. It is deliberately repo-native and does not depend on Helios or any external orchestrator.

## Decision Flow

1. If the repo lacks the research OS, install it with `scripts/install_research_os.py`.
2. If the repo already has it, read `research/README.md`, `research/status.md`, and `research/state/next_action.md`, then run one loop.
3. For existing code/papers/benchmarks, use `research/workflows/brownfield_loop.md`.
4. For a broad new research area, use `research/workflows/greenfield_loop.md`.
5. Before final synthesis, run `make validate-claims`, `make validate-experiments`, and `make review-gates`.

## Install

From the bundle root:

```bash
mise run research-os:install -- --target /path/to/repo --project-name "Project Name"
```

Default behavior is conservative:
- create missing files and directories;
- skip existing files;
- do not overwrite project-specific instructions;
- leave historical docs in place;
- create a generic OS layer that future agents adapt.

Use `--force` only when intentionally replacing the generated OS files. Use `--dry-run` to preview.

After install, run in the target repo:

```bash
make status
make validate-agents
make validate-claims
make validate-experiments
make review-gates
```

## Operate

Always run one meaningful unit of work per loop. The director chooses the unit, assigns a specialist, validates output, updates memory, and ends with a concrete next action.

Role boundaries matter:
- literature scout maps prior art but does not declare novelty;
- theorist proposes hypotheses but does not approve them;
- experimentalist logs evidence but does not declare publication readiness;
- adversarial reviewer attacks claims and does not fix them;
- synthesis writer summarizes only validated evidence;
- research director coordinates and enforces gates.

Read `references/operating-model.md` when designing or modifying the OS. Read `references/agent-roster.md` when updating roles or agent prompts.

## Required Invariants

- No meaningful untracked claims: use `research/claims/claims.yaml`.
- No improvement claim without a baseline or explicit baseline plan.
- No novelty claim without novelty review.
- No empirical claim promotion without replication review.
- No important synthesis without adversarial review.
- Negative results stay in memory and experiment logs.
- Every loop updates `research/state/next_action.md`.
- Provider-neutral generated roles omit static `model` and `model_reasoning_effort` pins;
  they do not dispatch. A caller loads `model-tier-rightsizing`, injects a certified exact
  model ID plus **explicit requested effort/context**, records requested/resolved/inherited/
  unresolved state separately, and stops on inherited or unresolved selection. Reject
  host-default policy and unverified aliases.
