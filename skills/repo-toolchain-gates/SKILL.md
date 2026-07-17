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
  betterleaks git-history scans, self-hashing gate receipts, and the negative-fixture idiom.
author: Claude Code
version: 1.1.0
date: 2026-07-16
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
                          (advisory/opt-in where the tool is not registry-pinnable — see below)
```

`mise run check` is the single gate string agents need. The cartographer discovers it; the
implementer runs it before reporting done; the integrator re-runs it on the integration
branch; CI runs the same tasks. Hooks are a *subset* of check (fast, staged-files-only) —
never the other way around.

**This bundle's own gate graph is the worked example, and it is conformance-frozen.**
`mise.toml`'s `[tasks.check]` depends on exactly `["validate","test","self-test"]`; lefthook
runs `validate` (pre-commit) and `test`+`self-test` (pre-push), a strict subset of `check`; CI
(`.github/workflows/validate.yml`) runs exactly `mise run check` on three OSes with SHA-pinned
`actions/checkout` + `jdx/mise-action`. All three are the SAME graph. The enforcing test is the
contract: `tests/test_gate_graph.py` fails any `[tasks.check]` drift (`test_all_hollowing_mutations_fail`),
any tool-pin drift (`test_toolchain_config_mutations_fail`), any lefthook-superset or unpinned-CI
edit (the `MUTATIONS` table), and any `mise.lock` tamper (`assert_lock_mutation_fails`). Change the
graph only by updating that test in the same commit.

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

## betterleaks: the secrets gate (advisory here — doctrine-vs-wiring reconciliation)

gitleaks-compatible fork (drop-in: same rules format, same flags) with live-credential
`--validation` and faster scans. Two modes:

- `betterleaks dir .` — working tree (lefthook pre-push / CI step).
- `betterleaks git .` — FULL git history. Run before making any repo public or handing a
  bundle to another machine; HEAD-only scans miss secrets deleted in later commits.

Exit code is the gate: 0 clean, 1 leaks. For a repo with a live secrets surface, wire it as a
lefthook pre-push command and a CI step; pair with a repo-specific sweep (internal hostnames etc.)
which generic rules won't catch.

**Wiring status in THIS bundle: advisory / opt-in, not wired — and honestly so.** `betterleaks`
is deliberately NOT in `mise.toml`, `lefthook.yml`, or CI here, for two reasons that would
otherwise let the doctrine claim a gate no `mise run check` runs:

1. **Not registry-pinnable.** `betterleaks` is not published in the mise registry (only `gitleaks`
   is), so it cannot be pinned in `[tools]` for CI-parity the way uv/lefthook/node/bun/seeds-cli
   are. An unpinned brew/npm install would defeat the whole "same version locally, in CI, and in
   every worker" premise of this skill.
2. **The gate graph is conformance-frozen.** `mise.toml`, its SHA-pinned `mise.lock`, `lefthook.yml`,
   and `validate.yml` are byte/SHA-locked by `tests/test_gate_graph.py` and
   `scripts/validate_bundle.py` (`validate_mise`, `validate_gate_graph`). Adding a `[tools]` entry
   or a hook/CI step without regenerating the frozen lock and updating those tests in the same
   commit is a hard failure, by design.

This repo is a skill/installer bundle with **no runtime credentials in-tree**, so a live secrets
gate on every `check` is the wrong altitude anyway. The advisory posture is: run `betterleaks git .`
(a full-history scan) as a **pre-publish** step before making the bundle public, not as a wired
gate. `tests/test_gate_graph.py::test_betterleaks_wiring_matches_doctrine` enforces this: if the
skill ever claims betterleaks is wired, the tool must actually be pinned in `[tools]` and run in CI
or a hook; otherwise the skill must carry this advisory language and the cited reason. A repo that
DOES have a secrets surface and a registry-pinnable scanner should choose Option A — pin it, add a
`[tasks.secrets]` task, run it in pre-push + CI, and (only if it joins `[tasks.check]`) update the
`test_gate_graph.py` check-depends assertion in the same commit.

## Worktree waves: the two propagation facts (verified 2026-07-05)

1. **`.git/hooks` IS shared.** A worktree's `.git` file points into the main repo's
   gitdir; `core.hooksPath`/hooks resolve there. One `lefthook install` in the main repo →
   hooks fire in every wave worktree. Do NOT re-install per worktree.
2. **mise trust is NOT shared.** Trust is keyed on the config file's absolute path; a fresh
   `git worktree add` is untrusted even when the main repo is trusted. Consequence: hooks
   fire (fact 1) but any hook command resolved through mise shims errors with
   "config not trusted" — hooks work in main, fail in the worktree. This behavior is proven
   by `tests/test_gate_graph.py::test_paranoid_mode_requires_per_path_trust` (under
   `MISE_PARANOID=1`, a fresh copied repo's `mise tasks` fails "not trusted", then succeeds
   after `mise trust <path>`). Two routes:
   - **Persistent trust** — `mise trust <worktree-path>` (or `MISE_TRUSTED_CONFIG_PATHS=<path>`)
     mutates user trust config; it is a per-absolute-path change, right next to codex dir-trust,
     and needs explicit operation-specific approval for each exact reviewed path.
   - **Process-scoped, no persistent trust** — `mise --no-config --cd <worktree> exec ...` runs a
     gate without ever writing trust config (see the flagship skill's seeds-worktrees reference).
     Prefer this when a wave should not mutate user trust state to run one gate.

## Verification

- `mise run check` exits non-zero on a planted lint error (prove the gate falsifiable the
  day it ships).
- `git commit` in a worktree fires pre-commit (plant a staged `.py` with a lint error).
- `betterleaks git .` exits 1 on a planted AWS key in a test commit (then drop the commit).

## Negative-fixture gate testing (the falsifiability doctrine)

**Every gate ships an offline fixture per known failure mode; the test asserts the gate fails with
the *specific* expected exit code / diagnostic — a gate with only green tests is unproven.** This
is not aspirational here: `tests/test_gate_graph.py` already IS the harness. It proves each fail
path fires:

- config-hollowing fails with an exact diagnostic — the `MUTATIONS` table + `test_all_hollowing_mutations_fail`,
  each asserting `returncode == 1` AND `assertIn(diagnostic, result.stderr)`.
- toolchain-pin drift fails — `TOOLCHAIN_MUTATIONS` + `test_toolchain_config_mutations_fail`.
- `mise.lock` tamper fails — `assert_lock_mutation_fails`, `test_lock_mutation_fails_through_cli`.
- description-bypass variants fail — `test_folded_description_variants_cannot_bypass_validation`.
- worktree-untrusted mise fails then trust fixes — `test_paranoid_mode_requires_per_path_trust`.

Fixture rules (match the existing `tests/` posture): offline, synthetic, non-secret, and
self-cleaning (`tempfile.TemporaryDirectory`, drop the commit). A secrets fixture uses a documented
**test-pattern/canary** token, never a real credential, and is never used as production evidence.
Reuse the existing helpers (`copied_repo`, `run_validator`, `assert_lock_mutation_fails`,
`isolated_mise_env`) — do not fork a parallel harness.

## Gate receipts (self-describing evidence)

A gate's own evidence should be self-describing and tamper-evident by re-derivation. `scripts/gate_receipt.py`
(stdlib-only) builds a canonical receipt after running a gate. Fields:

- `gate` — the exact task string, e.g. `"mise run check"`.
- `argv` — the exact argv executed (e.g. `["mise","run","check"]`), so the receipt proves *which*
  command ran, not a paraphrase.
- `status` — the integer exit code (0 = pass; the exit code IS the gate).
- `log_digest` — `sha256` of captured combined stdout+stderr bytes (tamper-evident without storing
  the whole log).
- `toolchain_digest` — `sha256` of `mise.lock` bytes at run time, binding the receipt to the exact
  pinned toolchain (catches "green on drifted pins").
- `cwd` — the absolute path the gate ran in, tying the receipt to per-path worktree trust (above).
- `self_digest` — `sha256` of the canonical JSON of every other field.

This makes **worktree-green ≠ main-green** machine-checkable: the integrator's re-gate-on-MAIN
(see the flagship skill's worktree-integration reference) produces one such receipt; a
worktree-green receipt whose `cwd` ≠ main and whose `toolchain_digest` differs from main's is
exactly the failure that reference warns about. `tests/test_gate_receipts.py` covers both the green
path and the negative fixtures (`test_tampered_receipt_field_fails_self_digest`,
`test_toolchain_digest_binds_lock`). This is doctrine + a helper, not a second task runner.

## Tier-1 self-hashing canonical-JSON evidence

Receipts (and any wave/gate-run summary artifact) use the canonical serialization the bundle's
validator already uses (`scripts/validate_bundle.py` `sha256_bytes` + canonical digest binding):

```python
canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
digest = hashlib.sha256(canonical).hexdigest()
```

A self-hashing artifact carries `self_digest` over the canonical form of all *other* fields, so any
consumer re-derives and compares byte-for-byte. **Honesty caveat (carried verbatim into doctrine):
this is tamper *detection* by re-derivation, not a security boundary against the same OS user** —
the same posture `scripts/validate_bundle.py` already documents for its receipt validation. Tier-2
HMAC is explicitly out of scope: the gate stack has no cross-session issuer/verifier split that
would need a keyed MAC, and adding one would over-claim a boundary the code does not enforce.

## Notes

- The upstream bundle demonstrates the distinction directly: mise manages the lefthook
  binary, while repository activation is separate. A lefthook binary does nothing
  until hooks are configured and installed.
- See also (in the flagship `agentic-sdlc` skill): the seeds-worktrees
  reference (config propagation into worktrees), the sdlc-loop reference (where gates sit
  in the loop), and the bundle's validate-bundle.sh (a worked example of a repo-specific
  gate script).

## References

- mise docs: https://mise.jdx.dev (tools, tasks, trust)
- lefthook docs: https://lefthook.dev (config reference)
- betterleaks: https://betterleaks.com (gitleaks-compatible; `--validation`)
