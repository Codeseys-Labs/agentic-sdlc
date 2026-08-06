# Clean-install verification: clone and container

**Date:** 2026-08-06 · **Status:** executed, both probes green · **Closes:** gap **G1** from
`2026-08-06-parity-review-FINAL.md` ("Commit the work… nothing else in this ledger matters until
this is done, because every parity claim above is currently a claim about one developer's
filesystem").

## What was unprovable before

The parity review's sharpest finding was that agentic-sdlc's strongest capability did not exist
outside one working directory: `git log --all -- skills/agentic-sdlc/tools/activation-planner.py
tests/test_activation_transaction.py` was empty, and a clean clone of `ada5ecd` got a 441-line
planner exposing `choices=["plan"]` instead of the 2,948-line transaction with 51 tests.

Six commits now on `release/offline-observer-rc` (`8edcd59`…`eb77add`) land the activation
transaction and its runbook correction, the pinned toolchain and the `validate_skills` model-pin
gate, the ported pi-lab doctrine references, the research corpus, and two custody fixes.

## Probe 1 — clean clone

```
git clone --branch release/offline-observer-rc <repo> /tmp/cloneprobe2
mise trust ./mise.toml && mise run check
```

**Result: `EXIT=0`** — validator clean, self-test passed, `OK (skipped=13)`. The clone resolves
`plan,apply,status,recover` and carries all 409 tests.

**This probe earned its keep by failing first.** The initial clone run errored twice in
`test_prime_candidate_custody`: the attestation names an assessed commit, three candidate commits,
and five frozen `*-v7` refs that were **never pushed** (`git ls-remote --heads origin` lists none
of them), so the suite was asserting local-only repository state and could pass on exactly one
machine. Fixed in `eb77add`: object-dependent checks skip with an explicit reason; everything that
is a property of the record file rather than the object store still runs everywhere. Two earlier
defects came out of the same pass — the verifier had asserted `rev-parse HEAD` still equalled the
assessed commit (so it broke on the next commit), and its fixture under `docs/progress/` was
untracked.

## Probe 2 — bare container, mise as the only prerequisite

`debian:13-slim` + `curl`/`git`/`ca-certificates`, non-root user, no host toolchain, no ambient
node/bun/python, no `~/.claude`, no trust state. The image installs mise, trusts the reviewed
config per-path, then runs `mise --locked install`, `mise run check`, and `mise run bundle:install`.

**Result: `=== PROBE OK ===`, exit 0.**

All nine pinned tools resolved to their locked versions from the checked-in `mise.lock`:

```
uv 0.11.17    lefthook 2.1.10    node v22.22.3    bun 1.3.10    ripgrep 15.2.0
fd 10.4.2     jq-1.8.2           gh 2.97.0        betterleaks 1.7.3
```

`betterleaks` installing with **no `GITHUB_TOKEN` in the environment** is the specific validation
of the `github.slsa = false` / `github.github_attestations = false` decision: the `github:`
backend would otherwise call the release API at install time and fail closed on the
unauthenticated rate limit, which would have made a token a second bootstrap prerequisite.

The gate passed in-container (`OK (skipped=15)`), then `bundle:install` wrote **34 entries** —
8 skills × 2 planes, 7 Claude agents, 7 Codex agent TOMLs, 4 commands — and `bundle:status`
reported **34 `ok:` lines with zero `conflict`/`foreign`/`missing`/`drift`**.

So the AGENTS.md claim *"mise 2026.4.27+ is the only bootstrap prerequisite"* now has an executed
proof on a machine that shares nothing with the author's.

## Skip counts are a portability signal

| Environment | Skips | Why |
|---|---|---|
| Author's working tree | 10 | baseline |
| Clean clone | 13 | +3 custody checks (local-only git objects) |
| Container | 15 | +2 more (no paired native Windows host; no second host plane) |

Rising skips across environments are expected and correct here — each increment names a capability
the environment genuinely cannot verify rather than one that broke. Worth watching as a metric: a
skip that appears without an environmental reason is a test quietly opting out.

## What this does NOT prove

- **Not a remote install.** Both probes clone from the local filesystem path. The GitHub remote is
  private with zero releases and zero pushed tags, so `git ls-remote --tags origin` is empty and
  no anonymous fetch path exists. A true install-from-remote test needs the repo public, or a
  release, or credentials — an operator decision, not a technical gap.
- **Nothing is pushed.** These six commits are local to `release/offline-observer-rc`. Local
  `main` and remote `main` have diverged (local `main` == remote `9994f46` by tree; remote carries
  two further commits, `1d2b3ce` and `532e984`, that this branch does not contain — and the 13
  files "missing" relative to remote `main` are exactly the retired-profile files this branch
  deliberately removed, whose token the removal contract in `tests/test_cao_removal.py` now
  forbids anywhere in the shipped tree, including in prose like this).
  A squash-merge to `main` is therefore not a clean fast-forward and needs an explicit decision.
- **Not a functional test of the agents or skills.** It proves acquisition, gating, installation,
  and lifecycle reporting — not that any orchestration doctrine works.

Secrets: `betterleaks dir .` and `betterleaks git .` are both clean (one negative-control token in
the gateway memo was defanged; it was a probe string, never a credential).

No outward effect was performed. A passing gate and a green container are evidence only.
