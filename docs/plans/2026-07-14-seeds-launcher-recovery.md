# Receipt-Based Seeds Launcher Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship the portable receipt launcher with fail-closed acquisition, distribution, package, interpreter, authority-scanner, and native-Windows contracts.

**Architecture:** The installed Node-stdlib launcher has two modes. `bootstrap` is the only acquiring mode: exact Node 22.22.3 admits one exact clean Git distribution, invokes the reviewed locked mise config in an isolated acquisition environment, validates the exact Node/Bun/Seeds tuple, and writes a versioned hash receipt. `inspect` is offline and receipt-only: exact Node 22.22.3 validates current hashes and executes the exact absolute Bun/package entry with a finite read-only grammar and allowlisted runtime environment.

**Tech Stack:** Node.js 22.22.3 stdlib, mise 2026.4.27+, Bun 1.3.10, @os-eco/seeds-cli 0.5.14, Python 3.12 unittest, native Windows and POSIX.

---

### Task 1: Reproduce the released-package and admission defects

**Files:**
- Modify: `tests/test_seeds_launcher.py`
- Create: `tests/fixtures/seeds-cli-0.5.14/package.json`

**Steps:**
1. Copy the byte-for-byte `package.json` from the real mise-installed `@os-eco/seeds-cli@0.5.14` into the fixture directory.
2. Make launcher fixtures consume that metadata so benign `engines.bun` is exercised.
3. Add failing executable cases for ambient npm/mise config isolation, nested distribution roots, dirty/staged/untracked/ignored trees, and a non-22.22.3 launcher process.
4. Run `mise exec uv@0.11.17 -- uv run --python 3.12.11 python -m unittest tests.test_seeds_launcher` and verify each new case fails for the intended missing control.

### Task 2: Harden bootstrap and interpreter admission

**Files:**
- Modify: `skills/agentic-sdlc-orchestrator/tools/seeds-launcher.mjs`
- Test: `tests/test_seeds_launcher.py`

**Steps:**
1. Permit only a string-valued `engines.bun` compatibility declaration; retain recursive rejection of Bun config, TypeScript config, macro, and preload controls.
2. Require `process.versions.node === 22.22.3` in bootstrap and inspect.
3. Require the distribution argument to equal the physical Git top level and require `HEAD` tree, index, tracked worktree, untracked, and ignored surfaces to be exact and clean before mise runs.
4. Resolve mise once, then invoke `mise --locked install` with only the reviewed root config/lock plus private HOME, data/cache, distinct empty npmrc files, fixed official registry/npm backend, disabled hooks/config environment, and a finite system/mise PATH. Resolve exact tuple roots with `mise --no-config where` under the same environment.
5. Record the exact Git commit and tree along with existing typed hashes.
6. Run the focused launcher tests and a real clean Linux bootstrap followed by offline `inspect --version`; expect `0.5.14`.

### Task 3: Close plural authority and native-Windows test gaps

**Files:**
- Modify: `tests/test_preflight_capabilities.py`
- Modify: `tests/test_seeds_launcher.py`

**Steps:**
1. Add a failing scanner fixture for Seeds issues, items, records, states, queues, and queue-states.
2. Extend only the finite Seeds object grammar to accept singular and plural forms, retaining existing topic false-positive exclusions and authority exceptions.
3. Add an executable `os.name == "nt"` fixture that runs real native Node/mise/Git, bootstraps the locked tuple under hostile ambient config, inspects `--version`, and asserts native receipt paths/layout.
4. Run the focused scanner and launcher suites on Linux and native Windows.

### Task 4: Align executable documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `skills/agentic-sdlc-orchestrator/SKILL.md`
- Modify: `skills/agentic-sdlc-orchestrator/references/seeds-worktrees.md`
- Replace: `docs/plans/2026-07-14-seeds-launcher-recovery.md`

**Steps:**
1. Document exact Node 22.22.3 as the executing process in both modes.
2. Document exact clean Git root/tree binding and rejection of nested/dirty/staged/untracked/ignored distributions.
3. Document isolated reviewed mise/npm acquisition and the narrow `engines.bun` compatibility exception.
4. Keep the honest lock-integrity and same-UID TOCTOU limitations unchanged.
5. Describe the receipt launcher only; remove the superseded Bash temp trampoline, ComSpec `sd.cmd`, and transient wrapper design.

### Task 5: Verify and commit one cumulative successor

**Files:**
- Verify all changed files above.

**Steps:**
1. Run focused launcher/scanner tests.
2. Run the authoritative Linux `mise run check` and `./scripts/install-skill-bundle.sh self-test`.
3. Run native Windows `mise run check` and confirm the executable Windows launcher fixture is not skipped.
4. Run `git diff --check`, review the cumulative diff and exact scope, and confirm no trust/config/outward mutation.
5. Commit locally with a concise Conventional Commit subject and `Co-Authored-By: Claude <noreply@anthropic.com>` trailer. Do not push or merge.
