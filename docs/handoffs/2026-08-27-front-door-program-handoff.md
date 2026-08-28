# Handoff: the front-door program's orchestrating session (2026-08-27)

**Status:** dated snapshot of one session's end state, written for the next session. Facts below
were verified on 2026-08-27 and go stale by design; the queue (`.seeds/issues.jsonl`) is the
live record and always wins a disagreement with this document.

**Session:** 2026-08-27. **Workspace:** `/home/codeseys/DevBox/custom-pi-setup/agentic-sdlc` (primary checkout, branch `main`, clean, no worktrees, no running agents or gates; the .worktrees/ leftovers were archived to ~/.local/state/agentic-sdlc/stale-worktrees-20260826/ and removed).
**Written by:** the 158-hour orchestrating session, at its deliberate end. The queue is the handoff; this document is only the map to it.

## What this program is

Make agentic-sdlc honestly installable behind one `ccodex` front door, driven by GitHub issues #8-#17 (filed by the operator's other-device agent after failing to install from the docs). The program is COMPLETE through its ratified train: front-door verbs, project scope, v2 receipts, operator-tools demolition, decision-debt closeout, CI cross-platform repair, and the v0.7.6 release.

## Current state (verified 2026-08-27, morning)

- `main` = `17a56e1` locally and on origin; tag `v0.7.6` = same commit.
- **v0.7.6 prerelease is published with verified bytes**: https://github.com/Codeseys-Labs/agentic-sdlc/releases/tag/v0.7.6, archive sha256 `efa321f5e60e01e2b9dc17b6b3cf26fd51af6466b81575d06cbf865e2130deb7`, digest-matched between CI's build and an independent local deterministic build. All tag checks green including asset attach.
- CI on main: Linux + macOS green. Windows leg red with known test-fixture platform holes (seed `agentic-sdlc-1729` carries the verbatim failure list) plus the d208 attestation red, now behind a named skip landed at `84bc24a` (first post-skip Windows run will confirm).
- Seeds queue: 35 open / 212 closed in `.seeds/issues.jsonl`.

## Where the durable records live (do not reconstruct from chat)

- **Queue:** `.seeds/issues.jsonl` — every open seed now carries its ruling/disposition in its description. Read it before choosing work.
- **Plan of record:** `docs/plans/2026-08-25-front-door-unification.md` (annotated DONE with dated execution corrections per wave).
- **Evidence:** `docs/evidence/2026-08-26-project-scope-clean-host.md` (executed clean-host transcript), `docs/research/2026-08-24-gateway-default-provider-misroute.md`.
- **Doctrine:** `AGENTS.md` (authoritative, re-diffed 37/37 against mise tasks), ADRs 0009/0010/0021/0028/0029/0030/0031 (amended dated this window).
- **Session memory:** `~/.claude/projects/-home-codeseys-DevBox-custom-pi-setup-agentic-sdlc/memory/MEMORY.md` — read the index; the operational lessons (gate protocol, mutation hazards, outward-filing rule) live there.

## Standing constraints the next agent MUST inherit

1. `mise run check` before any commit; run it via the harness's background task (never shell `&`); read the verdict in a SEPARATE command from any push.
2. Seeds queue writes ONLY through the receipt-bound launcher: `~/.local/share/agentic-sdlc-seeds-distribution/skills/agentic-sdlc/tools/seeds-launcher.mjs record --target <repo> --queue-writer conductor --expect-queue <sha256 of .seeds/issues.jsonl> (create ...|update <id> --status/--description/...)` under Node `~/.local/share/mise/installs/node/22.23.2/bin/node`. NOTE seed 1727: if a distribution carrying commit `98b566c`'s launcher bytes is ever installed there, the seam refuses on hash drift until re-bootstrapped (operator step).
3. Every new `.worktrees/*` worktree needs its own `mise trust <worktree>/mise.toml` (conductor does it) before its gates mean anything.
4. Never `git stash` (repo-global, shared across worktrees); file-copy snapshots for mutation checks, and clear `__pycache__`/use `PYTHONDONTWRITEBYTECODE` around mutations (seed f244's stale-pyc hazard).
5. Every test invoking installer/ccodex CLIs passes isolated homes even when a refusal is expected, and asserts temp roots stay empty (`tests/installer_cli_safety.py` is the house guard).
6. Outward effects (push, tag, release, filing issues anywhere) need explicit operation-specific approval, with the LITERAL destination (owner/repo) named in the approval question. Check the target's issue template first.
7. Subagent briefs end with an explicit "REPORT via SendMessage to main" paragraph, or agents idle silently.
8. `gh issue view` is broken on this repo (Projects-classic GraphQL); use `gh api repos/Codeseys-Labs/agentic-sdlc/issues/N --jq .body`.
9. `mise run test` accepts no path argument; narrow with `uv run --python 3.12.11 --with pyyaml==6.0.3 python -m unittest tests.<module>` (seed f1c7).

## Ready-to-dispatch work (rulings already recorded in each seed)

- `agentic-sdlc-1779`: collapse validate_release_contract (operator override GRANTED, sequenced-after-cut condition now satisfied by v0.7.6). Takes 32a2's channels item.
- `agentic-sdlc-1729`: Windows fixture-hole wave (verbatim list in seed); consider pricing a pre-push Windows smoke in the same wave.
- `agentic-sdlc-f498`: record-remove-name for project-retirement empty dirs.
- `agentic-sdlc-e561`: mint-next-free-instant for same-second receipt collisions.
- `agentic-sdlc-3440`: ONE reviewed escaping wave owning both statusline sanitization and the refusal-channel double-escape (sites named in seed).
- `agentic-sdlc-8dca` remainder: generalize the CLI-safety guard beyond test_install_skill_bundle.
- `agentic-sdlc-bc33`: docs residue sweep (seven measured items listed in seed).
- `agentic-sdlc-ed19`: DESIGN pass — operator-owned skill archives through the bundle's own acquisition plane (craft-skills; catalog route refused by ADR-0029 + live guards; do not fight that refusal).

## Needs the operator (do not start without them)

- Guided fresh-session lane (seeds d5 + c005): live clean-host install dogfood on their machine, then Claude Code canary runs for the first certified Core tuple (unblocks 60f0). This was the operator's chosen next engagement.
- d0ab/f3ca plugin-channel reconciliation design (carries 6dca's marketplace-statusline acceptance criterion).
- 95e6 report-scope dimension (post-train reviewed policy wave).

## Suggested skills (call via the Skill tool)

- `agentic-sdlc` — the flagship orchestration doctrine; load before any Frame/Wave/Mission work.
- `mattpocock-skills:grilling` (or the operator's `grilling`) — for the guided install lane and any design fork put to the operator.
- `pstack:how` — before touching the installer/receipt planes; the subsystem is dense and the ADRs are load-bearing.
- `change-writing` — commit/PR/squash text (repo convention: imperative subject + seed id in parens, dense evidence body).
- `model-tier-rightsizing` — before any model dispatch in waves.
- `superpowers:verification-before-completion` — the house rule in skill form: evidence before assertions, always.

No credentials, tokens, or personal data appear in this document or the referenced artifacts.
