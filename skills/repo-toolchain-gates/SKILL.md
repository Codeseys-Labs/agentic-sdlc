---
name: repo-toolchain-gates
description: |
  Standard local gate stack for SDLC repos: mise (pinned toolchain + task-runner gates),
  lefthook (git-hook enforcement), betterleaks (secrets gate). Use when: (1) setting up or
  auditing a repo so `mise run check` is THE gate every agent (implementer/reviewer/
  integrator/critic) runs; (2) local lint passes but CI fails — linter version drift between
  [tools] pin and the CI action; (3) wiring pre-commit/pre-push hooks that workers can't
  skip; (4) running waves in git worktrees where hooks fire but mise tools error "config not
  trusted"; (5) adding a secrets gate to hooks + CI. Covers CI-parity pinning, lefthook via
  mise [tools], {staged_files}/stage_fixed, worktree hook sharing vs per-path mise trust,
  betterleaks git-history scans.
author: Claude Code
version: 1.0.1
date: 2026-07-10
---

# Repo Toolchain + Gates (mise · lefthook · betterleaks)

## Problem

The bundle's doctrine is gates-as-executables: every role agent runs the same gate command
and trusts its exit code. That needs three things a bare repo lacks — a pinned toolchain
(same versions locally, in CI, and in every worker), one canonical gate command, and
enforcement that fires even when a worker forgets. mise + lefthook + betterleaks is the
verified stack for all three.

## The shape

```
mise.toml   [tools]  → pins EVERYTHING: language, uv, linters, lefthook
            [tasks]  → fmt / vet / lint / test / … and ONE aggregate:
            [tasks.check]  depends = ["fmt","vet","lint","test",…]   ← THE gate
lefthook.yml           → pre-commit = fast staged-file subset; pre-push = heavier subset
betterleaks            → secrets gate: lefthook command + CI step + pre-publish history scan
```

`mise run check` is the single gate string agents need. The cartographer discovers it; the
implementer runs it before reporting done; the integrator re-runs it on the integration
branch; CI runs the same tasks. Hooks are a *subset* of check (fast, staged-files-only) —
never the other way around.

## mise: the rules that matter

- **Pin linters to the exact CI version, in `[tools]`, with a comment naming the CI file.**
  A real wave shipped locally-green/CI-red precisely because golangci-lint wasn't pinned to
  the version the CI action used. Bump both together:
  ```toml
  [tools]
  # Pinned to match .github/workflows/ci.yml golangci-lint-action version.
  golangci-lint = "2.12.2"
  lefthook = "2.1.10"
  ```
- **Install lefthook via `[tools]`, not brew/npm** — the hook manager itself is then
  version-pinned and present in CI and every worker without a separate install step.
- **A `setup` task owns bootstrap**: `run = ["uv sync --all-extras --dev", "lefthook install"]`.
- Python repos: reuse the existing uv venv via `[env] _.python.venv = {path=".venv"}` —
  never let mise create a parallel one.
- Task args use the `usage` spec, not Tera `arg()`/`option()` (deprecated).

## lefthook: the patterns that matter

- `{staged_files}` + `stage_fixed: true` for auto-fixers (ruff format etc.) — the fix is
  re-staged, the commit proceeds.
- `glob:`/`exclude:` per command; `parallel: true` for independent checks.
- pre-commit = seconds (staged files only). pre-push = the heavier subset (unit tests,
  full-repo secrets scan). The FULL gate stays `mise run check`.
- `assert_lefthook_installed: true` makes a missing install loud instead of silent.
- Bypass exists (`--no-verify`, `LEFTHOOK=0`) — hooks are a guardrail for humans and
  workers, not a security boundary. CI re-runs the same gates.

## betterleaks: the secrets gate

gitleaks-compatible fork (drop-in: same rules format, same flags) with live-credential
`--validation` and faster scans. Two modes:

- `betterleaks dir .` — working tree (lefthook pre-push / CI step).
- `betterleaks git .` — FULL git history. Run before making any repo public or handing a
  bundle to another machine; HEAD-only scans miss secrets deleted in later commits.

Exit code is the gate: 0 clean, 1 leaks. Wire as a lefthook pre-push command and a CI step;
pair with a repo-specific sweep (internal hostnames etc.) which generic rules won't catch.

## Worktree waves: the two propagation facts (verified 2026-07-05)

1. **`.git/hooks` IS shared.** A worktree's `.git` file points into the main repo's
   gitdir; `core.hooksPath`/hooks resolve there. One `lefthook install` in the main repo →
   hooks fire in every wave worktree. Do NOT re-install per worktree.
2. **mise trust is NOT shared.** Trust is keyed on the config file's absolute path; a fresh
   `git worktree add` is untrusted even when the main repo is trusted. Consequence: hooks
   fire (fact 1) but any hook command resolved through mise shims errors with
   "config not trusted" — hooks work in main, fail in the worktree. Fix: add
   `mise trust <worktree-path>` to the wave-creation checklist, right next to codex
   dir-trust (same per-absolute-path pattern; see the flagship skill's
   seeds-worktrees reference).

## Verification

- `mise run check` exits non-zero on a planted lint error (prove the gate falsifiable the
  day it ships).
- `git commit` in a worktree fires pre-commit (plant a staged `.py` with a lint error).
- `betterleaks git .` exits 1 on a planted AWS key in a test commit (then drop the commit).

## Notes

- The upstream bundle demonstrates the distinction directly: mise manages the lefthook
  binary, while repository activation is separate. A lefthook binary does nothing
  until hooks are configured and installed.
- See also (in the flagship `agentic-sdlc-orchestrator` skill): the seeds-worktrees
  reference (config propagation into worktrees), the sdlc-loop reference (where gates sit
  in the loop), and the bundle's validate-bundle.sh (a worked example of a repo-specific
  gate script).

## References

- mise docs: https://mise.jdx.dev (tools, tasks, trust)
- lefthook docs: https://lefthook.dev (config reference)
- betterleaks: https://betterleaks.com (gitleaks-compatible; `--validation`)
