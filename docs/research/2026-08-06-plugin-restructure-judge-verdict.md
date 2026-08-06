All probes removed. Here is my judgment.

---

# ADVERSARIAL JUDGMENT + FINAL BLUEPRINT

## Part 1 — What I refuted

### R1. THE PLANES DO NOT COLLIDE. Executed, definitive.
I ran the real installer into a throwaway HOME, then installed the plugin into the *same* HOME, and computed the path-set intersection:

```
direct paths: 19   plugin paths: 551   INTERSECTION: 0
```

Direct plane writes `$HOME/.claude/{skills,agents,commands}/<bare-name>`. Plugin plane writes only `$HOME/.claude/plugins/{cache,installed_plugins.json,known_marketplaces.json}`. A live session with **both installed** enumerated 14 distinct agents (7 bare + 7 `agentic-sdlc:claude:sdlc-*`), 8 distinct commands, and reported *"No exact identifier appears twice."*

I also ran the worst case both designs only asserted — identical skill **name** in both planes:
> `collide-probe` → `USER_UUU` (user dir); `shadowplug:collide-probe` → `PLUGIN_PPP` (plugin). Both load; bare name resolves to user.

**Verdict: `marketplace_overlap()`'s block protects against nothing.** Both designs got this right; the exclusivity doctrine in README/AGENTS is simply false. I confirmed the block is real (exit 1, `claude skills dir: NO`, 19 skip messages) and that deleting it yields exit 0 with 8 skills + 7 agents + 4 commands + 8 codex skills.

### R2. Design B's central premise — the frozen cache — is WRONG for this repo's install path.
B built its entire `plugin/` restructure on "the cache is a whole-directory copy." The copy exists (8.9 MB, 29 root entries incl. `tests/`, `.pytest_cache/`, `.seeds/`), but **the runtime does not read it**. I mutated only the source tree:

```
source: MUTATED_ZZZ_QQ9   cache: ORIGINAL_AAA
live session → (1) MUTATED_ZZZ_QQ9   (2) /tmp/judge-drift/src/skills/drift-probe/SKILL.md
```

Independently corroborated: `CLAUDE_PLUGIN_ROOT` resolved to `/tmp/judge-schema/src/` — the **source**, not the cache. Design A's C2 is confirmed; **B's "content drift is a genuinely new failure mode" is false for directory sources**, which is the only install path that works today (see R7).

### R3. Design B's Step 4 breaks the gate. Executed.
I performed B's exact `git mv skills agents commands policy plugin/` and ran the real validator:

```
ERROR: invalid runtime receipt policy: .../skills/model-tier-rightsizing/policy/runtime-assignment-receipt-v1.json
ERROR: invalid normative managed role contract: .../policy/runtime-assignment-normative-contract-v1.json
ERROR: policy/role-manifest.v1.json: missing versioned role-contract manifest
```

Blast radius measured: **66** path literals in `validate_bundle.py`, **24** in `test_preflight_capabilities.py`, plus `validate_managed_role_contract` asserting `count == 14` and a **path-keyed sha256 dict** (`SOURCE_PINNED_PROTECTED_ROLE_CONTENT_SHA256`). B admits this is "one large atomic commit that cannot be split" — and its stated payoff (fixing `--strict`) is worthless per R4. **Reject B's restructure.**

### R4. `claude plugin validate` is in NO GATE. Both designs over-weighted `--strict`.
```
rg 'plugin validate' mise.toml lefthook.yml .github/workflows/ scripts/ tests/  →  only a message string
```
`--strict` failing is cosmetic. B's whole `plugin/` move exists to satisfy a check nothing enforces. (Confirmed both invocation forms differ as B described, and non-strict exits 0 / strict exits 1 — B's nuance was correct, but the conclusion doesn't follow.)

### R5. BOTH designs' proposed model-pin gate BREAKS THE BUILD. New finding, neither caught it.
Both said "add the same two `result.error` branches" from `validate_agents` to `validate_skills`. I did exactly that:

```
ERROR: model-tier-rightsizing: static model is forbidden
validate-bundle: 1 error(s)
```

Cause: in `validate_agents`, `metadata` is a **dict** (`parse_frontmatter_metadata`) so `"model" in metadata` is a key test. In `validate_skills`, `metadata` is a **raw string** (`frontmatter()`), so `"model" in metadata` is a *substring* match that hits `name: model-tier-rightsizing`. Copying the line is a false positive. The correct form is line-anchored:

```python
for forbidden in ("model", "model_reasoning_effort"):
    if re.search(rf"^{forbidden}:", metadata, re.MULTILINE):
        result.error(f"{label}: static {forbidden} is forbidden")
```
Verified: baseline `0 error(s)`, and it still catches a real pin (`vendor/skills/vendored-tdd: static model is forbidden` ×2).

### R6. Gate coverage of `vendor/` — A's measurement was right, and I confirmed the asymmetry.
- `validate_skills` globs only `skills/*/SKILL.md` → a vendored SKILL.md with `model: opus` **and** a missing reference produced **`0 error(s)`**.
- Whole-tree scans **do** reach vendor: bad `.py` → `Python source failed to compile: vendor/lib/bad.py`; AWS URL → `possible secret or internal hostname found`. **Adding `vendor/` to `.gitignore` does NOT exempt it** (retested, same 2 errors).

### R7. Remote install is genuinely blocked — I tested what both designs left unverified.
`gh`: `{"isPrivate":true,"visibility":"PRIVATE"}`, zero releases. The 8 local tags are **NOT on the remote** (`git ls-remote --tags` → empty) — a correction to fact 8 in both directions. I attempted the private remote add:
```
✘ Failed to add marketplace: HTTPS authentication failed... could not read Username
```
And `claude plugin marketplace add .` → `Invalid marketplace source format` (absolute path works). **A's §6 was right; B's "credentialed clone works" is unproven and the HTTPS path fails.**

### R8. Schema verification against official docs — one invented element, one missed feature.
Fetched `code.claude.com/docs/en/plugins-reference` + `/hooks`. Confirmed: `skills` is `string|array` and **"Adds to the default"**; `hooks` is `string|array|object`; top-level `description` in hooks.json is valid **for plugins only**; `agents` **"replaces default"** and rejects directories (executed: `"./agents/claude/"` and `["./agents/claude/"]` → `agents: Invalid input`; omitting it loads `schemaplug:claude:probe-role`).

- **A's `"skills": ["./skills/","./vendor/skills/"]`** — valid, and I installed it: `Skills (3) first-a, probe-cmd, vend-b`. Docs note a **marketplace-root exception** where declaring subdirs *replaces* the default scan; listing both roots explicitly is correct under either semantics.
- **A's custom `"hooks": "./claude-hooks/hooks.json"`** — valid; fired: `HOOKFIRED root=/tmp/judge-schema/src/`.
- **B's `"deny"`-vs-`"ask"` reasoning is correct** and doctrinally superior to A's exit-2 deny.
- **Both missed the `if` field** (`"if": "Bash(git push:*)"`), which does matcher-time filtering in the harness — strictly better than shell string-matching.
- **A's exit-2 hook is a doctrine violation:** exit 2 makes the hook *decide*. Doctrine says only an authorized human authorizes outward effects. `permissionDecision: "ask"` routes to the human. **B wins the hook design.**

### R9. Hook latency: A's "~1ms" is wrong.
Measured 100 invocations: **467 ms → ~4.7 ms per Bash call.** Still acceptable, but ~5× A's claim. Correcting it matters because `if`-gating removes the cost from non-git Bash calls entirely.

### R10. Third-party safety.
- mattpocock/skills: pinned-SHA fetch with **no auth, no npx** → `HEAD=8b36d4fb...`; `LICENSE` = `MIT License / Copyright (c) 2026 Matt Pocock`; 35 SKILL.md.
- **hyperresearch is NOT vendorable**: 14/14 agents carry static `model:`, **11** skills carry unresolved `{{...}}`/`{hpr_path}`, and **no LICENSE/NOTICE exists** in the local install. Both designs excluded it; I confirm and add the license blocker.
- **ECC: no resolvable license on any candidate repo.** Not redistributable. **USER DECISION, blocking.**
- Repo has **no LICENSE** and declares `"license": "UNLICENSED"` — a blocker for shipping MIT content alongside it.

### Verdict
**Design A wins.** Its no-move / single-source-of-truth finding is correct and executed; B's restructure is built on a refuted premise (R2), breaks the gate (R3), for a non-gate payoff (R4). **Graft from B:** the `ask`-not-`deny` hook decision, the `hooks:install` naming split, the license-blocks-vendoring sequencing, and the `mcpServers`-is-unpinnable argument. **Correct in both:** R5 (the substring bug), R9 (latency), R7/R8 nuances.

---

## Part 2 — FINAL BLUEPRINT

### Target tree (6 new files, 1 move, 0 tree moves)

```
agentic-sdlc/
├── .claude-plugin/plugin.json     [P] + "skills":["./skills/","./vendor/skills/"]
│                                      + "hooks":"./claude-hooks/hooks.json"
│                                      NO "agents"/"commands" keys (auto-discovery only)
├── .claude-plugin/marketplace.json[P] unchanged ("source":"./" is correct)
├── skills/            (8)      [P+D] SAME BYTES, both planes. Zero duplication.
├── agents/claude/     (7)      [P+D] DO NOT MOVE. Loads as agentic-sdlc:claude:sdlc-*
├── agents/codex/**             [D]   .toml inert for Claude
│   └── research/README.md      ✗ MOVED → docs/codex-research-roster.md
├── commands/          (4)      [P+D] /agentic-sdlc:sdlc-*
├── claude-hooks/               [P]   NEW — plugin-only (not "hooks/": naming collision)
│   ├── hooks.json
│   └── guard-outward-effect.sh
├── vendor/                     [P]   NEW — plugin plane only
│   ├── sources.json  .digests.json  NOTICES.md
│   └── skills/vendored-<name>/SKILL.md
├── scripts/vendor_skills.py    [R]   NEW
├── LICENSE  THIRD-PARTY-NOTICES.md   NEW (blocking prerequisite)
└── mise.toml/mise.lock/lefthook.yml/.github  [R] UNTOUCHED — no [tools] entry added
```

Sharing is literal: no file copied, mirrored, or generated twice (R2 — the runtime reads the source tree).

### Exact file contents

**`claude-hooks/hooks.json`** — every key verified against docs; `if` added (R8)
```json
{
  "description": "Advisory guardrail for outward and destructive git operations. Best-effort convenience only: it never authorizes an outward effect, never records evidence, and never substitutes for `mise run check` or an authorized integrator.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "if": "Bash(git *) or Bash(gh *)",
            "timeout": 10,
            "command": "bash \"${CLAUDE_PLUGIN_ROOT:-.}/claude-hooks/guard-outward-effect.sh\""
          }
        ]
      }
    ]
  }
}
```

**`claude-hooks/guard-outward-effect.sh`** — `ask`, not deny (B's win); fails open
```bash
#!/usr/bin/env bash
# Advisory PreToolUse guardrail (Claude Code plugin plane only).
#
# DOCTRINE: this hook routes to the human; it never decides. It emits
# permissionDecision "ask" so the operator authorizes the operation. It is NOT an
# authorization boundary, NOT evidence, and NOT a gate. `mise run check` remains the
# authoritative gate, and a passing gate still authorizes nothing. Fails OPEN on any
# parse difficulty: a guardrail that blocked unparsed input would break unrelated calls.
set -u
input=$(cat 2>/dev/null) || exit 0
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "${cmd:-}" ] || exit 0

reason=""
case $cmd in
  *"push --force"*|*"push -f"*|*"push --delete"*) reason="a force/deleting push" ;;
  *"reset --hard"*)      reason="a hard reset (discards committed and staged work)" ;;
  *"clean -fd"*|*"clean -df"*|*"clean -fx"*) reason="a forced clean (deletes untracked files)" ;;
  *"branch -D"*)         reason="an unmerged branch delete" ;;
  *"update-ref -d"*|*"checkout --orphan"*) reason="ref surgery" ;;
  *"gh pr merge"*)       reason="a pull-request merge" ;;
  *"gh release create"*) reason="a release publication" ;;
esac
[ -n "$reason" ] || exit 0

printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"agentic-sdlc: %s. Advisory only - this hook does not authorize it. Explicit, operation-specific operator authorization is still required. Return a SeedProposal or ask the operator; do not reword to evade this."}}\n' "$reason"
exit 0
```
`jq` is already a pinned `mise.toml` tool; the `|| exit 0` fails open if absent.

**`vendor/sources.json`**
```json
{
  "note": "Pinned third-party skill sources. Exact commit SHAs only: no tags, no branches, no ranges. `mise run vendor:verify` proves vendor/skills matches these pins byte-for-byte OFFLINE; `vendor:sync` is the only writer and the only networked step. Vendored content is plugin-plane only and always renamed with the vendored- prefix.",
  "sources": []
}
```

**mise tasks** (extra tasks are free — `REQUIRED_TASKS` is a subset check; **no `[tools]` entry, so `MISE_LOCK_SHA256` and `LOCKED_TOOLCHAIN` are untouched**)
```toml
[tasks."vendor:sync"]
description = "Re-fetch pinned third-party skills into vendor/skills"
run = "uv run --python 3.12.11 --script scripts/vendor_skills.py sync"
run_windows = "uv.exe run --python 3.12.11 --script scripts/vendor_skills.py sync"

[tasks."vendor:verify"]
description = "Verify vendor/skills matches vendor/sources.json offline"
run = "uv run --python 3.12.11 --script scripts/vendor_skills.py verify"
run_windows = "uv.exe run --python 3.12.11 --script scripts/vendor_skills.py verify"
```
Do **not** add to `[tasks.check]` (byte-pinned to `["validate","test","self-test"]`); reach the gate via `validate_bundle.py`.

### Exact diffs to frozen files

**`scripts/install_skill_bundle.py`**
1. Delete line 2613: `claude_blocked = config.agent in {"all","claude"} and marketplace_overlap(config.home)`
2. Delete lines 2621-2625 (the `if entry.agent == "claude" and claude_blocked:` block)
3. In `status()` (before `return Result(...)` at ~2774) append the advisory note — **must not set `partial`**:
```python
    if config.agent in {"all", "claude"} and marketplace_overlap(config.home):
        messages.append(
            "note: a Claude Code plugin for this bundle is also installed; it is a"
            " separate plane with namespaced components. Uninstalling here does not"
            " remove it (use `claude plugin uninstall agentic-sdlc@<marketplace>`)."
        )
```
4. Line 1346: keep (already advisory); reword to drop the exclusivity implication.

**`scripts/validate_bundle.py`** — dual-root + **line-anchored** pin check (R5)
```python
def validate_skills(root: Path, result: Validation) -> None:
    for base in ("skills", "vendor/skills"):
        for skill in sorted((root / base).glob("*/SKILL.md")):
            directory = skill.parent.name
            label = f"{base}/{directory}" if base != "skills" else directory
            ...  # existing name/description/reference checks, using `label`
            for forbidden in ("model", "model_reasoning_effort"):
                if re.search(rf"^{forbidden}:", metadata, re.MULTILINE):
                    result.error(f"{label}: static {forbidden} is forbidden")
```
Also extend `validate_scripts` to `bash -n claude-hooks/*.sh`, and add `validate_vendor` (shells `vendor_skills.py verify`; asserts every `vendor/skills/<dir>` starts with `vendored-` and appears in `sources.json`) to the `validate()` call list.

**`tests/test_install_skill_bundle.py`** — all executed, 83/83 pass
| Line | Action |
|---|---|
| 556 `test_marketplace_overlap_skips_only_claude` | → `test_marketplace_presence_does_not_block_claude_install`; assert `exit_code == 0` + skills/agents/commands/codex all exist |
| 505 `test_marketplace_skip_does_not_validate_unused_claude_collections` | → `test_install_refuses_symlinked_claude_collection`; drop `marketplace.mkdir()`, use `assertRaisesRegex(..., "collection root must not be a link")` (this is how it now fails — verified) |
| 2326 `test_migrate_state_reports_marketplace_overlap_fail_closed` | Keep; update substring only if reworded |
| new | `test_status_notes_plugin_plane_without_failing` — asserts exit 0 **and** `"separate plane"` |

### Migration sequence — every step gate-green

| Step | Change | Frozen artifacts | Evidence |
|---|---|---|---|
| **1** | `git mv agents/codex/research/README.md docs/codex-research-roster.md` | none (`.md` not in any `*.toml` glob or sha dict) | Kills the live all-tools pseudo-agent `agentic-sdlc:codex:research:README` — a real runtime defect I reproduced |
| **2** | Docs truth-up: `README.md:130` (`--strict`), `:279-283` + AGENTS.md (exclusivity), split `### Hooks` → "Git hooks (lefthook)" + "Claude Code hooks (plugin plane)" | none (only `CLAUDE.md`'s first line is pinned) | Must precede step 3 — docs assert the opposite |
| **3** | Installer Edits 1-4 + 4 test changes | none | **Executed: install exit 0, 8+7+4+8 components; validate `0 error(s)`; 83/83 tests OK** |
| **4** | `plugin.json` += `skills`(2 roots) + `hooks`; ship `claude-hooks/**`; extend `validate_scripts` | `validate_manifests` only parses JSON; `.version-bump.json` targets `.version` only | **Executed: `Skills (3)`, `Hooks (1) PreToolUse`, agent loaded, hook fired** |
| **5** | `LICENSE`, `THIRD-PARTY-NOTICES.md`, `vendor_skills.py`, `sources.json` (**empty**), 2 mise tasks, gate additions | `REQUIRED_TASKS` += 2; `TASK_COMMANDS` += 2 exact run strings; `validate()` += `validate_vendor`. **No `[tools]` → `MISE_LOCK_SHA256`/`LOCKED_TOOLCHAIN`/lefthook/CI all untouched** | Gate lands green before any third-party byte |
| **6** | First vendored content via `vendor:sync` | none (`sources.json` is data) | **Executed: 3 real mattpocock skills renamed `vendored-*` → `0 error(s), 0 warning(s)`** |

Baseline confirmed: `mise run validate` → `0 error(s)`; `mise run test` → **407 tests OK**. (A copied tree shows 4 unrelated mise-*trust* failures — identical in patched and unpatched copies, so not caused by these changes.)

### Decisions that are the USER'S — human authorization boundary

1. **🔒 Repo visibility.** Private + zero releases + tags-not-pushed. I verified the HTTPS remote add **fails** and bare `.` is rejected. Only `claude plugin marketplace add /abs/path` works. Going public / cutting a remote tag is an **outward publication** — requires explicit authorization.
2. **🔒 LICENSE for this repo.** Currently absent, `"license":"UNLICENSED"`. Choosing a license is the user's legal decision and **blocks Steps 5-6**.
3. **🔒 ECC vendoring — BLOCKED.** No resolvable license on any candidate repo. Not redistributable. Recommend harvesting *discipline* as references, not content.
4. **hyperresearch — recommend NOT vendoring.** 14/14 agents static `model:` (gate-rejected), 11 skills unresolved placeholders, no LICENSE in the local install.
5. **Does the guardrail hook ship?** It is the plugin plane's only unique deliverable. If no, ship Step 4's manifest keys without `claude-hooks/`. Note: plugin hooks **cannot be selectively disabled** (only `disableAllHooks` or uninstall) — hence exactly one narrow, fail-open, `ask`-only hook.
6. **Vendored set + `vendored-` prefix.** Prefix makes fact 10's hard-block unreachable; costs verbosity (`agentic-sdlc:vendored-tdd`).
7. **🔒 `mise run vendor:sync` networks** — an explicit, reviewed, operator-invoked step. `vendor:verify` (what CI/the gate runs) is fully offline. No new bootstrap prerequisite: `git` and `uv` already required, **npx rejected** (no SHA pinning; violates `locked = true`).

### Deliberately NOT done
No `.mcp.json` (both designs agreed; MCP tool schemas resolve at runtime = unpinnable, and it would route around the Seeds launcher's receipt contract). No `plugin/` subdirectory move (R2/R3/R4). No `agents/` flatten (loads fine today; would force repinning 7+7+7 policy paths, a path-keyed sha256, and a `count == 14` assertion). No reliance on `claude plugin details` as an acceptance check — it reported `Agents (0)` while a live session enumerated all 7; **use a live session**.
