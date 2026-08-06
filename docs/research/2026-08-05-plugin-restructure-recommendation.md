# Restructure recommendation: plugin plane + automated vendoring

**Date:** 2026-08-05 · **Status:** design complete, nothing implemented · **Basis:** two
independent design passes (`2026-08-05-restructure-design-plugin-first.md`,
`…-single-source.md`), plus conductor verification of every load-bearing claim by execution.
Where a design and an execution disagreed, the execution wins and the disagreement is recorded.

## Recommendation in one line

**Yes — ship the plugin in addition to the direct install, with the plugin root moved to a
`plugin/` subdirectory.** Coexistence is already safe (no filesystem collision, distinct
namespaces); a subdirectory root additionally fixes a `--strict` failure that is otherwise
unfixable; and the plugin plane is the only way to ship Claude Code hooks.

## The four facts that decide the design

**1. Plugin and direct install do not collide.** Verified — see
`2026-08-05-plugin-coexistence-finding.md`. Plugin components live under
`~/.claude/plugins/cache/…` and are namespaced (`agentic-sdlc:<skill>`); the direct installer
writes bare names into `~/.claude/{skills,agents,commands}`. The exclusivity in
`scripts/install_skill_bundle.py:1447` is a **policy** choice, and today it costs the whole
Claude plane: with a marketplace present, a direct install reports `marketplace overlap` on all
**19** Claude entries, installs **zero** Claude skills, and exits 1 (reproduced).

**2. Agents already load correctly through the plugin — my earlier reading was wrong.** All 7
load as `agentic-sdlc:claude:sdlc-*`; the runtime loader recurses one level and namespaces by
subdirectory. `claude plugin details` reports `Agents (0)` because it counts only the flat
`agents/*.md` tier. **So do not flatten `agents/` — that would be a regression**, and the
manifest `agents` key cannot point at a directory in any form. Method note worth keeping:
enumerate subagent types in a live session; `details` is not a discovery oracle.

> **SUPERSEDED IN PART, 2026-08-06.** The workflow's adversarial judge completed after this was
> written and refuted two of its points; a third was refuted by my own follow-up. See
> `2026-08-06-plugin-restructure-judge-verdict.md`. Net change: **do not move the tree.**
> - Fact 4's "the cache is a copy, so the plugin root must contain what it ships" is **inert for
>   a directory-source marketplace** — the runtime reads the *source tree* (I verified: mutating
>   only the source changed what a live session saw). The copy is wasted disk, not a drift risk.
> - Fact 3's `plugin/` subdirectory move is **not worth it**: `claude plugin validate` appears in
>   **no gate** (verified: zero hits across `mise.toml`, `lefthook.yml`, `.github/workflows/`,
>   `scripts/`, `tests/`), so the `--strict` failure it fixes is cosmetic. The judge executed the
>   `git mv` and the real validator then emitted 3 hard errors, with a measured blast radius of
>   66 path literals in `validate_bundle.py` and 24 in `test_preflight_capabilities.py`.
> - The model-pin gate recommended below had a **latent false positive**, now fixed and tested
>   (see the note under "Two real defects").
>
> Still standing unchanged: coexistence is safe, agents already load, ship one `ask` hook, no
> MCP, don't vendor hyperresearch as agents, licensing is a blocker.

**3. A subdirectory plugin root passes `--strict` cleanly; the current layout cannot.**
`scripts/validate_bundle.py:1240-1242` *requires* root `CLAUDE.md` to begin with `@AGENTS.md`,
while plugin `--strict` warns on exactly that file — mutually exclusive at one directory. I built
a probe repo with the plugin root at `repo/plugin/` and `CLAUDE.md` at `repo/`: install
succeeded, the skill loaded, and `claude plugin validate --strict repo/plugin/.claude-plugin/plugin.json`
returned **`✔ Validation passed`** (after adding `author`, which the real manifest already has).

**4. Sharing one tree between planes by symlink is impossible.** The plugin cache is a
whole-directory **copy** (8.8 MB today, including `tests/`, `scripts/`, `docs/`, `.github/`);
symlinks copy as dangling, and `"../skills/"` is rejected as path traversal. The plugin root must
*contain* what it ships. Hence: move the shipped trees into `plugin/`, point the installer at
them, and keep dev/gate files outside. One copy in git; the duplication at *runtime* (frozen
cache vs live symlink) is irreducible platform behaviour.

## Plane split

| Component | Plane | Rationale |
|---|---|---|
| skills, agents, commands | both, one source in `plugin/` | namespacing keeps them distinguishable; operator picks per host |
| **Claude Code hooks**, MCP | **plugin only** | the installer writes no `settings.json`/hooks/MCP (verified: zero matches) |
| Codex / Gemini / OpenCode | direct installer only | plugins are Claude-specific |
| `mise run check` | neither | gate is evidence, never authorization |

Relax `marketplace_overlap()` from a Claude-plane-wide skip to a **reported, per-component**
condition. `tests/test_install_skill_bundle.py:556` pins the old behaviour (exit 1, Claude skills
absent) and must change in the same commit — and because `AGENTS.md`/`README.md:280` state the
opposite doctrine, this is an explicit policy change to record, not a quiet edit.

## Hooks: ship exactly one

A `PreToolUse` matcher on `Bash` that flags outward-effect and destructive git operations
(`git push`, `reset --hard`, `clean -f`, `branch -D`, `gh pr merge`, `gh release create`) and
returns `permissionDecision: "ask"`.

**`ask`, never `deny`** — doctrine reserves outward effects for a human, so the hook must *route
to* the human, not decide for them. A `deny` hook would itself become an authority. Cost is one
`bash` fork per Bash call; matcher-scoped, so Read/Edit/Task turns pay nothing. Verified in a
probe: `SessionStart` and `PreToolUse` both fire, `${CLAUDE_PLUGIN_ROOT}` populates, and a
`PreToolUse` decision genuinely gates execution.

Rejected, with reasons: **`SessionStart` injecting Seeds state** — would present ambient Seeds
output as context, the exact "never accept ambient Seeds provenance" failure doctrine names;
**`PostToolUse` running validate** — a partial run would masquerade as the authoritative gate,
and `lefthook` pre-commit already covers it at the right moment.

**Ship no `.mcp.json`.** Every capability is already a checksum-pinned CLI (`sd`, `gh`, `rg`,
`fd`, `jq`, `betterleaks`, `mmdc`). An MCP server adds a long-lived process and unpinnable
runtime tool schemas, and would route Seeds access around the pinned invocation contract.

**Fix the naming collision in the same commit:** `mise.toml` `hooks:install` runs `lefthook
install` = *git* hooks; `plugin/hooks/` = *Claude Code* hooks. `README.md`'s bare `### Hooks`
heading documents only the former. Retitle both; do not rename the task (it is in
`REQUIRED_TASKS` with a pinned run string).

## Vendoring: what is actually installable

**Do not vendor hyperresearch.** Four independent blockers, verified: every one of its 14 agent
files carries a static `model:` pin (`sonnet`/`opus`) — precisely what `validate_bundle.py`
rejects for agents; unrendered template artifacts; a dependency on an external note/vault CLI;
and **no discoverable license or provenance**, which alone blocks redistribution. Correct
integration is to document it as an optional host-provided capability, as
`agents/claude/sdlc-researcher.md` already does.

**The operator already has the full mattpocock catalog installed** (~23 names, not the 9
previously flagged), so vendoring any of them under their original names would hard-block that
install entry. Namespace anything vendored (e.g. `vendor/skills/<upstream>-<name>/`) and keep it
in a **separately declared** skills root.

**Automation mechanism — pinned fetch script, not `npx skills`.** `npx skills add` has no
version/ref/SHA pinning, fails offline, and adds a live network dependency, which contradicts
`locked = true` and "never accept ambient provenance." A `vendor.lock.json` of per-source pinned
SHAs plus a `uv run` fetch script adds no new runtime (Python is already pinned) and can enforce
"must have a discoverable LICENSE at the pinned SHA before proceeding." Claude Code's plugin
`dependencies` field does support semver pinning, but cross-marketplace deps are blocked unless
the target marketplace is listed in `allowCrossMarketplaceDependenciesOn`, and it is Claude-only
— so it cannot serve a cross-host bundle.

**Blocker: this repo has no `LICENSE` or `NOTICE`, and `plugin.json` says `"license":
"UNLICENSED"`.** Vendoring third-party MIT content requires attribution the repo currently has
nowhere to put. Add `LICENSE` + `THIRD-PARTY-NOTICES.md` before any vendored file lands.

## Two real defects to fix regardless

1. **`agents/codex/research/README.md` becomes a live pseudo-agent** (`agentic-sdlc:codex:research:README`)
   because the loader recurses. Give it frontmatter or move it out of any scanned tree.
2. **`README.md:130` is misleading, not merely false.** `validate --strict .` (directory)
   validates only the marketplace manifest and *passes*; `validate --strict
   .claude-plugin/plugin.json` walks components and *fails*. Name the invocation.
3. **The `validate_skills` model-pin gap — FIXED 2026-08-06, and the obvious fix was a trap.**
   Copying the two `result.error` branches out of `validate_agents` breaks the build. In
   `validate_agents`, `metadata` is a parsed **dict** (`parse_frontmatter_metadata`), so
   `"model" in metadata` is a key test; in `validate_skills` it is the raw frontmatter **string**,
   so the same expression is a *substring* match that fires on the shipped skill's own
   `name: model-tier-rightsizing` (verified: `'model' in frontmatter(...)` → `True`). A
   line-anchored regex removes the false positive but is weaker than the agents gate, which also
   rejects quoted and `\uXXXX`-escaped key forms. The shipped fix parses semantically via
   `parse_frontmatter_metadata`; it catches all four evasion forms (plain, quoted, escaped,
   flow-map) with the baseline at `0 error(s)`. Two negative fixtures added in
   `tests/test_runtime_contract_validation.py`, including one asserting the shipped
   `model-tier-rightsizing` skill does not trip it. `mise run check` exits 0.
4. **`vendor/` would be only partially gated.** `validate_skills` globs `skills/*/SKILL.md`
   only, so a vendored SKILL.md with a model pin *and* a missing reference produced
   `0 error(s)`. Whole-tree scans do reach it (a bad `.py` and an AWS URL under `vendor/` both
   error), and `.gitignore` does **not** exempt it. Any vendoring step must extend the skill
   glob, not assume coverage.

## Decisions that are yours

- **Repo visibility.** Everything above works from a **local-path marketplace** today (verified).
  A remote one-command install needs the repo public or releases cut — it is private with zero
  releases/tags.
- ~~**Whether the `plugin/` move is worth it.**~~ **ANSWERED: no.** Both claimed payoffs
  evaporated — `claude plugin validate` is in no gate (so `--strict` is cosmetic) and the cache
  copy is inert (the runtime reads the source). The judge executed the `git mv` and the real
  validator emitted 3 hard errors, against a blast radius of 66 path literals in
  `validate_bundle.py` plus 24 in `test_preflight_capabilities.py`, in a commit that cannot be
  split. Keep the tree as it is; accept the cosmetic `CLAUDE.md` warning.
- **Licensing.** Adding `LICENSE`/`NOTICE` and choosing this bundle's own license.
- **Which hooks you actually want.** I recommend exactly one; more is available but each costs
  latency on every matching call.

Nothing here is implemented. No outward effect is authorized by this document.
