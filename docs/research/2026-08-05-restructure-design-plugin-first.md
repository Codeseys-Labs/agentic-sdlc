# Plugin-first restructure blueprint for <repo>. Read-only on the repo (proposals only, no writes). All plugin-mechanics claims were executed live against `claude` CLI 2.1.223 in throwaway HOMEs under /tmp (all removed); all current-behavior claims are cited to file:line in the real repo. Two inherited "established facts" were overturned by execution and the design is built on the corrected facts.

> **Two inherited facts were overturned by execution.** They change the design materially, so they lead. Everything after is built on the corrected facts.

## 0. Corrections to the briefing (executed, not argued)

**C1 — Agents DO load from `agents/claude/*.md` via the plugin. The "Agents (0)" fact is a `details`-command reporting gap, not a discovery failure.**
The PLUGIN CAPABILITIES investigation concluded agents "will NOT auto-discover from `agents/claude/*.md`" and recommended flattening to `agents/*.md` or adding an `"agents"` override. Both recommendations are wrong and the second is impossible.

I installed the **real repo** as a plugin into a throwaway HOME and asked a live session to enumerate its Task-tool subagent types:
```
agentic-sdlc:claude:sdlc-cartographer
agentic-sdlc:claude:sdlc-critic
agentic-sdlc:claude:sdlc-implementer
agentic-sdlc:claude:sdlc-integrator
agentic-sdlc:claude:sdlc-planner
agentic-sdlc:claude:sdlc-researcher
agentic-sdlc:claude:sdlc-reviewer
agentic-sdlc:codex:research:README
```
All 7 Claude agents load, namespaced `agentic-sdlc:<subdir>:<name>`. `claude plugin details` reported `Agents (0)` for the same install — `details` only counts the flat `agents/*.md` tier; the runtime loader recurses one level and encodes the subdir into the namespace. **`details` output is not a discovery oracle.** This kills the flatten-`agents/` restructure entirely: `agents/claude/` + `agents/codex/` co-location is already correct and already works.

Corollary confirmed the same way: the `"agents"` manifest key **cannot** point at a directory. Every directory form is rejected by the manifest schema:
| form | result |
|---|---|
| `"agents": "./agents/claude/"` | `Validation errors: agents: Invalid input` → install fails |
| `"agents": ["./agents/claude"]` | `agents: Invalid input` → install fails |
| `"agents": ["./agents/claude/probe-agent.md"]` | installs, but **Agents (0)** and the agent does NOT load |
| no `agents` key at all | **works** — auto-discovery loads it |
So the only working configuration is the one the repo already has: **omit the `agents` key and let auto-discovery recurse.** Any "fix" here is a regression.

**C2 — `claude plugin validate --strict` on the repo *directory* already passes. Only the `plugin.json`-path invocation fails.**
```
$ claude plugin validate --strict .
Validating marketplace manifest: .../.claude-plugin/marketplace.json
✔ Validation passed

$ claude plugin validate --strict .claude-plugin/plugin.json
Validating plugin: .../CLAUDE.md            ⚠ CLAUDE.md at the plugin root is not loaded as project context
Validating agent: .../agents/codex/research/README.md   ⚠ No frontmatter block found
✘ Validation failed (--strict treats warnings as errors)
```
The two arguments validate **different things**: a directory arg validates only the marketplace manifest; a `plugin.json` arg walks the plugin's components. `README.md:130`'s claim ("Both manifests pass `claude plugins validate --strict`") is therefore *half* true and specifically misleading, not simply false — it is true for the invocation form most people type and false for the one that actually inspects components.

The `CLAUDE.md` warning is **unfixable in place** and it collides with a frozen gate: `scripts/validate_bundle.py:1240-1242` *requires* root `CLAUDE.md` to start with `@AGENTS.md`, and `tests/test_gate_graph.py` byte-pins that. You cannot delete `CLAUDE.md` to satisfy `--strict` without breaking `mise run check`. **This single conflict is the strongest argument for the restructure below** (§1: a subdirectory plugin root), and it is not resolvable by editing files — only by moving the plugin root.

Third finding from the same probe: `agents/codex/research/README.md` does not merely warn — **it becomes a live pseudo-agent** (`agentic-sdlc:codex:research:README` in the enumeration above). It is a real runtime defect, not a cosmetic validator nit.

---

## 1. Target repo tree

The decisive constraint, executed: **the plugin cache is a whole-directory copy of the plugin root, symlinks are not followed, and `../` escapes are schema-rejected.**

- Installing the repo as-is copied **8.8 MB** and 29 root entries into the cache — including `tests/`, `scripts/`, `docs/`, `.github/`, `.worktrees/`, `repro-tmp/`, `tmp-test/`, `.seeds/`, `.pytest_cache/`.
- A symlink at `plugin/skills/shared-skill -> ../../../skills/shared-skill` copied as a **dangling symlink**: `cat` → unreadable, skill silently absent from the inventory. **Sharing one skill tree between planes via symlink is impossible.**
- `"skills": ["./skills/", "../skills/"]` → `skills[1]: Path contains ".." which could be a path traversal attempt`. **Reaching up out of the plugin root is impossible.**

Therefore the plugin root must **contain** everything it ships, and the only lever for keeping it clean is *where the plugin root is*. Verified working: a plugin root in a **subdirectory**, declared via the marketplace's `source`.

```
agentic-sdlc/                          # repo root = dev/gate plane ONLY; never a plugin root
├── CLAUDE.md                          # @AGENTS.md — REQUIRED by validate_bundle.py:1240-1242.
│                                      #   Now OUTSIDE the plugin root, so --strict stops seeing it. Fixes C2.
├── AGENTS.md                          # cross-host router (Codex/Gemini/OpenCode read this)
├── README.md  mise.toml  mise.lock  lefthook.yml  .version-bump.json
├── .claude-plugin/
│   └── marketplace.json               # CATALOG ONLY. source: "./plugin"  (relative-path form, verified)
├── plugin/                            # ◄── THE CLAUDE PLUGIN ROOT. Everything here is cache-copied.
│   ├── .claude-plugin/plugin.json     #   the ONLY file in this dir (docs rule; repo already complies)
│   │                                  #   omit "agents"/"commands" keys — auto-discovery is the only
│   │                                  #   working form (C1). Declare only:
│   │                                  #   "skills": ["./skills/", "./vendor/skills/"]
│   ├── skills/<name>/SKILL.md         # 8 first-party skills. PLUGIN + DIRECT (shared, see below)
│   ├── vendor/skills/<prefixed>/      # vendored third-party skills, SEPARATE declared root (§4)
│   ├── agents/claude/sdlc-*.md        # 7 roles → agentic-sdlc:claude:sdlc-* (C1: works, keep nesting)
│   ├── agents/codex/sdlc-*.toml       # inert for Claude; consumed by the Codex direct plane
│   ├── agents/codex/research/*.toml   # 17 research roles
│   │   └── (README.md → MOVED OUT to docs/, see §5 step 2 — it becomes a pseudo-agent)
│   ├── commands/sdlc-{init,frame,wave,mission}.md
│   ├── hooks/hooks.json               # PLUGIN-ONLY. Claude Code hooks (§3)
│   ├── hooks-handlers/*.sh            # named scripts, never inline node -e
│   └── policy/*.json                  # runtime-assignment + role manifest (validator reads these)
├── scripts/                           # gate/installer plane — NOT shipped to Claude. -8.8MB→small
├── tests/  docs/  .github/            # dev plane only
├── .codex-plugin/plugin.json          # host manifest; "skills": "./plugin/skills/" (path update)
├── .agents/plugins/marketplace.json   # host manifest
├── gemini-extension.json              # contextFileName: AGENTS.md (root, unchanged)
├── LICENSE                            # NEW — blocks vendoring until it exists (memo §4)
├── THIRD-PARTY-NOTICES.md             # NEW — per-item upstream URL + pinned SHA + license
└── vendor.lock.json                   # NEW — pinned third-party sources (§4)
```

**Shared vs duplicated — the honest answer: SHARED for skills/agents/commands, and the sharing mechanism is `plugin/` being the single on-disk home that BOTH planes read.**

There is exactly one copy of each skill in git. The direct installer symlinks *out of* `plugin/skills/<name>`; the plugin cache copies *from* it. This requires a one-line change per root in the installer's discovery (`scripts/install_skill_bundle.py:767-783` currently globs `repo_root/"skills"`, `repo_root/"agents"/"claude"`, `repo_root/"commands"`, `repo_root/"agents"/"codex"` — all become `repo_root/"plugin"/...`).

Duplication is thereby avoided **in git**, but *not* at runtime: the plugin install is a frozen copy, the direct install is a live symlink. That is an irreducible property of the platform (the cache is a copy), and it is the real cost of goal (a) — see §6.

`hooks/` and `.mcp.json` are the only genuinely plugin-exclusive components; nothing in the direct plane can consume them (`scripts/install_skill_bundle.py:788` maps only `skill`/`agent`/`command` to collections).

---

## 2. Plane model

| Plane | Owns | Reads from | Serves |
|---|---|---|---|
| **Claude plugin** (primary) | skills, agents, commands, **hooks**, (MCP) | `plugin/` copied to cache | Claude Code only |
| **Direct installer** (fallback) | skills, agents, commands | `plugin/` symlinked to `~/.codex`, `~/.claude` | Codex, Gemini, OpenCode + Claude-without-plugin |
| **Gate plane** | `mise run check` | repo root | neither; evidence only |

### The exclusivity fix

The EXCLUSIVITY investigation's conclusion is correct and I confirmed the mechanism by reading it: `marketplace_overlap()` (`scripts/install_skill_bundle.py:1447-1463`) tests only for the *presence* of a directory or a substring in a manifest — it never compares a single entry name against anything that could collide. At `scripts/install_skill_bundle.py:2613` it sets `claude_blocked`, and `:2621-2625` then `continue`s past **every** Claude entry with `partial = True`. Net: exit 1, zero Claude components.

Because the plugin cache and `~/.claude/skills` are disjoint paths, and because plugin components are namespaced (`agentic-sdlc:sdlc-init` vs bare `sdlc-init`), no collision exists to protect against. I additionally proved namespacing is collision-proof for the *worst* case: a bare `~/.claude/skills/tdd` and a plugin shipping `skills/tdd/` coexisted, and a live session enumerated both as distinct.

**Change 1 — delete the block** (`scripts/install_skill_bundle.py:2613`, `:2621-2625`):
```python
# DELETE at :2613
claude_blocked = config.agent in {"all", "claude"} and marketplace_overlap(config.home)
# DELETE at :2621-2625
if entry.agent == "claude" and claude_blocked:
    partial = True
    messages.append(f"marketplace overlap: {destination}")
    continue
```
Nothing else in `_install` needs to change: the per-entry authority checks (`:2624` `assert_safe_collection`), conflict detection (`:2631-2640`), and transaction journaling already handle every real write hazard, and they are orthogonal to plugin presence.

**Change 2 — add an advisory note to `status()`** (`scripts/install_skill_bundle.py:2750`, which today never calls `marketplace_overlap` — verified: the only two call sites are `:1346` and `:2613`). Insert before the return at `:2774`:
```python
if config.agent in {"all", "claude"} and marketplace_overlap(config.home):
    messages.append(
        "note: a Claude Code plugin for this bundle is also installed; its components are"
        " namespaced `agentic-sdlc:<name>` and are not managed here. Uninstalling this plane"
        " does not remove them, and the plugin's cached copy does not track this worktree."
    )
```
This is a message, not a verdict — it must not flip the exit code, because presence of a plugin is not a defect. This closes the uninstall-ambiguity gap the exclusivity investigation correctly flagged as newly-exposed.

**Change 3 — keep `:1346-1352` as-is.** It is already advisory (appends a message during `--migrate-state`, never blocks), so it needs at most a wording refresh to drop the "not migrated" implication of exclusivity.

### Test changes

| Test | Action |
|---|---|
`tests/test_install_skill_bundle.py:556` `test_marketplace_overlap_skips_only_claude` | **Rewrite + rename** → `test_marketplace_presence_does_not_block_claude_install`. Invert: plant the fake marketplace dir, assert `exit_code == 0` and `(config.home/".claude"/"skills"/"example").exists()` is **True** alongside the existing Codex assertion. This test currently pins exactly the behavior being deleted.
`tests/test_install_skill_bundle.py:505` `test_marketplace_skip_does_not_validate_unused_claude_collections` | **Rewrite.** It plants a marketplace dir *and* a hostile symlinked `~/.claude/skills` collection, then asserts `external` stays empty **because Claude was skipped**. Once the skip is gone the installer will reach that collection, and `assert_safe_collection` (`:797-799`, "collection root must not be a link") is what must now reject it. Drop the marketplace precondition entirely and assert the `InstallerError`/conflict path directly — the collection-safety property is real and unrelated to plugins, so it must survive, but it must be tested standalone.
`tests/test_install_skill_bundle.py:2326` `test_migrate_state_reports_marketplace_overlap_fail_closed` | **Leave.** It exercises the advisory `:1346` path; "fail_closed" there refers to the rename being skipped, not to blocking an install. Re-read after the change to confirm no shared helper moved.
New | `test_status_reports_plugin_coexistence_without_failing` — plant the marketplace dir, assert the note appears in `messages` **and** `exit_code == 0`.
Docs, same commit | `README.md:279-283` and the `AGENTS.md` "use either direct install or the marketplace, never both; marketplace overlap blocks only Claude" clause both state the **opposite** of the new invariant and must be rewritten, or the tests will pin behavior the docs contradict.

---

## 3. Hooks to ship

Executed end-to-end before proposing any of this. In a throwaway HOME I installed a probe plugin with `hooks/hooks.json`, ran a live session, and confirmed:
- `SessionStart` and `PreToolUse` both fired; `details` reported `Hooks (2) ... (harness-only — no model context cost)`.
- **`${CLAUDE_PLUGIN_ROOT}` was populated correctly** (`/tmp/.../mkt/nestplug`) at both callsites. The reported issue #42564 did not reproduce on CLI 2.1.223 — but I keep the `:-` fallback anyway, since one negative observation does not disprove an open intermittent bug.
- A `PreToolUse` deny genuinely prevented execution. The real payload:
  `{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{"command":"echo FORBIDDEN_TOKEN",...},"permission_mode":"default",...}`
  and the session reported the command never ran.

**Ship exactly one hook.** Justification bar: it must enforce something the repo currently states only in prose, and must not fire on every turn.

`plugin/hooks/hooks.json`:
```json
{
  "description": "Advisory guardrails for the agentic-sdlc bundle. Best-effort convenience only: no hook here grants, records, or withholds authority for any outward effect, and no hook verdict is release evidence.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT:-$CLAUDE_PROJECT_DIR/plugin}/hooks-handlers/guard-outward-effect.sh\""
          }
        ]
      }
    ]
  }
}
```
`plugin/hooks-handlers/guard-outward-effect.sh` reads the payload on stdin, matches `.tool_input.command` against destructive/outward-effect patterns (`git push`, `git reset --hard`, `git clean -f`, `git branch -D`, `git checkout .`, `gh pr merge`, `gh release create`), and on match emits:
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask",
 "permissionDecisionReason":"agentic-sdlc: outward effect or destructive git op. Advisory only — this hook does not authorize it; explicit operation-specific user authorization is still required."}}
```
Exit 0 with no output otherwise. Uses `ask`, not `deny`: doctrine says the human authorizes outward effects, so the hook must **route to the human**, never substitute for them. `deny` would make the hook an authority (it would decide), which is exactly what doctrine forbids.

**Cost:** one `bash` fork per Bash call only. Matcher-scoped, so Read/Edit/Grep/Task turns pay nothing.

**Explicitly rejected:**
- **`SessionStart`** — the obvious candidate (inject Seeds `ready`/`blocked` state). Rejected: `AGENTS.md` requires Seeds inspection go through the exact pinned `mise --no-config ... sd` contract under a verified receipt. A hook that runs it unprompted at every session start would spend seconds of latency, and worse, would present ambient Seeds output as context — the precise "never accept ambient Seeds provenance" failure the doctrine names. The conductor must invoke it deliberately.
- **`PostToolUse` running `mise run validate`** — the tempting "auto-gate on edit." Rejected on two doctrinal grounds: `mise run check` is the *authoritative* gate and a partial hook-run would masquerade as it, and a passing gate is evidence, never authorization. `lefthook` pre-commit (`lefthook.yml`, byte-pinned by `scripts/validate_bundle.py:1216-1229`) already covers this at the right moment. Also: multi-second latency on every write.
- **`PreToolUse` on `mcp_tool`/`Task`** — nothing to enforce.

**Naming hazard to fix in the same commit:** `mise.toml:105` `hooks:install` runs `lefthook install` = **git** hooks. `plugin/hooks/` = **Claude Code** hooks. `README.md:284-290` documents the former under a bare `### Hooks` heading. Rename the heading to `### Git hooks (lefthook)` and add `### Claude Code hooks (plugin plane)`. Do **not** rename the `hooks:install` task — it is in `REQUIRED_TASKS` (`scripts/validate_bundle.py:26-40`) and its run string is pinned; renaming costs a validator+test change for zero benefit.

## 3b. MCP — ship nothing

**No `.mcp.json`.** Every capability this bundle needs is already a CLI under a checksum-pinned `mise.lock`: Seeds via the pinned `sd` contract, `gh` (`mise.toml:22`), `rg`/`fd`/`jq`, `betterleaks`, `mermaid-cli`. An MCP server would be strictly worse: it adds a long-lived process, its tool schemas resolve at runtime (unpinnable — confirmed in `details` output: "tool schemas resolved at runtime; not counted"), and it would route Seeds access *around* the exact pinned invocation contract `AGENTS.md` mandates. Shipping an empty or invented server to "use the slot" would be pure liability. Revisit only if a capability appears that genuinely has no CLI form — and then measure it against the MCP-budget rubric already backlogged (memo item #11).

---

## 4. Third-party skill automation

**Verified prerequisite that gates this whole section:** `fd -H -t f 'LICENSE|NOTICE'` at repo root returns nothing, and `.claude-plugin/plugin.json:8` says `"license": "UNLICENSED"`. MIT permits reuse only with the copyright and permission notice preserved. **`LICENSE` + `THIRD-PARTY-NOTICES.md` must land before the first vendored byte.**

**Namespacing rule** (settles the collision problem, and my probes show it's now belt-and-braces):
1. Doctrine/prose extractions → `plugin/skills/agentic-sdlc/references/<topic>.md`. Not skills.
2. Genuinely new freestanding capabilities → `plugin/vendor/skills/asdlc-<capability>/`, **always** the `asdlc-` prefix, **never** the upstream bare name.
The prefix is required for the **direct** plane, where a foreign `~/.claude/skills/tdd` symlink hard-blocks that entry (`scripts/install_skill_bundle.py:767-783` writes `skills/<dirname>` → `~/.claude/skills/<dirname>`; non-owned entries are preserved as conflicts). It is *not* needed for the plugin plane — I proved a plugin `skills/tdd/` coexists fine with a bare `~/.claude/skills/tdd`. Prefix anyway: one rule for both planes, and the operator already has the **entire** mattpocock catalog installed (~23 names), not just the 9 originally flagged.

Verified enabling mechanic: **`"skills"` accepts multiple directory roots.** `"skills": ["./skills/", "./vendor/skills/"]` loaded `flat` + `vend-a` together and passed `--strict`. So first-party and vendored skills stay physically segregated while both load. (Also verified: skill discovery is **not** recursive — `skills/vendor/deep/SKILL.md` was silently ignored at both `details` and runtime. The extra declared root is the *only* way to group them.)

**`vendor.lock.json`** — reviewed manifest, one entry per item:
```json
{
  "note": "Pinned third-party sources. A vendored item is admitted only at an exact commit SHA with a discoverable license at that SHA. Fetch is a reviewed, explicit operation; no gate and no install depends on network access.",
  "sources": [
    {
      "id": "mattpocock-skills",
      "url": "https://github.com/mattpocock/skills.git",
      "sha": "8b36d4fb2635b3c21998dcd8144439c9e5ba7302",
      "license": "MIT",
      "copyright": "Copyright (c) Matt Pocock",
      "items": [
        {"upstream": "skills/engineering/tdd/SKILL.md",
         "target": "plugin/skills/agentic-sdlc/references/tdd.md",
         "mode": "adapt"}
      ]
    }
  ]
}
```
That SHA is live-verified: `git ls-remote https://github.com/mattpocock/skills.git HEAD` → `8b36d4fb2635b3c21998dcd8144439c9e5ba7302`, matching Anthropic's own pin for `mattpocock-skills` in the official catalog. Pinned-SHA-in-manifest is Anthropic's canonical third-party pattern.

**`scripts/vendor_sync.py`** (new, `uv run --script`, same launcher shape as every other entrypoint):
- `--check` (default): recompute each vendored target's SHA-256 against the digest recorded in `THIRD-PARTY-NOTICES.md`; report drift. **Pure-offline, no network.**
- `--fetch <id>`: `git clone --depth 1` + `git checkout <sha>`, verify a license file exists at that SHA, copy declared items, refuse if the resolved SHA ≠ pinned SHA. Explicit, operator-invoked.
- `--update <id> --to <sha>`: rewrite the pin, refetch, re-emit notices, and print a diff for review. Never automatic.

**mise tasks** (extra tasks are free — `validate_mise` only checks `REQUIRED_TASKS` is a *subset* of tasks, `scripts/validate_bundle.py:1095-1096`, and pins run strings for known names only; so this adds **no** `mise.lock`/`expected_tools` churn):
```toml
[tasks."vendor:check"]
description = "Verify vendored third-party content matches its recorded digests"
run = "uv run --python 3.12.11 --script scripts/vendor_sync.py --check"
run_windows = "uv.exe run --python 3.12.11 --script scripts/vendor_sync.py --check"

[tasks."vendor:fetch"]
description = "Fetch one pinned third-party source into the vendor tree (explicit, networked)"
run = "uv run --python 3.12.11 --script scripts/vendor_sync.py --fetch"
run_windows = "uv.exe run --python 3.12.11 --script scripts/vendor_sync.py --fetch"
```
**No bootstrap prerequisite added:** `git` is already required, `uv`/Python come from the existing lock, and `--check` never networks. Do **not** add `vendor:check` to `[tasks.check]` — it is pinned to exactly `["validate","test","self-test"]` (`mise.toml:102`, `scripts/validate_bundle.py` gate-graph checks). Instead put the digest check *inside* `validate_bundle.py` so it runs under `validate` with no task-graph change.

**Rejected mechanisms:** `npx skills add` (documented no ref/sha pinning → violates `mise.toml:4 locked = true` and "never accept ambient provenance"; adds a live network+npx dependency to an offline-capable install; it is also how the colliding names arrived on this machine). Plugin `dependencies` (Claude-only, so useless for the Codex fallback plane, and cross-marketplace deps require an `allowCrossMarketplaceDependenciesOn` allowlist that exists for none of these sources).

**Per-target verdicts (unchanged from the memo, re-confirmed):** hyperresearch's rendered artifacts stay **un-vendored** — all 14 agents carry static `model:` frontmatter that `scripts/validate_bundle.py:1065` rejects outright, ≥8 step skills contain unresolved `{{...}}`/`{hpr_path}` Jinja placeholders, and the pipeline is inert without the external CLI. ECC contributes UX *discipline*, not bulk content; 281 skills of which ~10 are vetted.

**Close the gate gap first.** `validate_skills` (`scripts/validate_bundle.py:410-424`) checks name==dirname, description presence/≤1024, and reference existence — and has **no** model-pin check, unlike `validate_agents` (`:1065-1068`). A vendored `SKILL.md` carrying `model: opus` passes today. Add the same two rejections to `validate_skills` **before** any vendoring lands.

---

## 5. Migration sequence

Each step ends gate-green (`mise run check` → 0). Baseline verified now: `mise run validate` → `0 error(s), 0 warning(s)`.

**Step 1 — Truth-in-docs + gate gap. No moves.**
Fix `README.md:130` to state the two `validate` invocation forms differ (C2). Add `model`/`model_reasoning_effort` rejection to `validate_skills` (`:410-424`). Split the `### Hooks` heading (§3).
*Frozen artifacts:* none. No `mise.lock`, no `expected_tools`, no `test_gate_graph` fixture. Add a `tests/` case for the new skill model-pin rejection.

**Step 2 — Evict the pseudo-agent.**
Move `agents/codex/research/README.md` → `docs/research-roster.md`. This removes the live `agentic-sdlc:codex:research:README` pseudo-agent **and** one of the two `--strict` warnings. Do not "fix" it with frontmatter — a README is not an agent.
*Frozen artifacts:* check `RESEARCH_ROLE_IDS` / `SOURCE_PINNED_RESEARCH_PATHS` (`scripts/validate_bundle.py:122-160`) — they enumerate `*.toml` only, so a `.md` removal should be inert; confirm by running `check`.

**Step 3 — Relax exclusivity (§2). No moves.**
Delete the block; add the `status()` note; rewrite the two tests + add one; rewrite `README.md:279-283` and the `AGENTS.md` clause in the same commit.
*Frozen artifacts:* none.

**Step 4 — Create `plugin/` and move the four component trees.** The one large, atomic step.
`git mv skills agents commands policy plugin/`; add `plugin/.claude-plugin/plugin.json` with `"skills": ["./skills/","./vendor/skills/"]` and **no** `agents`/`commands` keys (C1); repoint `.claude-plugin/marketplace.json` `source` to `"./plugin"`.
Must change in the **same commit**:
- `scripts/install_skill_bundle.py:767-783` — four glob roots → `repo_root/"plugin"/...`
- `scripts/validate_bundle.py` — `validate_skills:411`, `validate_agents:1052,1069`, and the path constants at `:87-90` (`RECEIPT_POLICY_PATH`, `ROLE_MANIFEST_PATH`, `PACKAGED_POLICY_DIR`), plus `SOURCE_PINNED_GLOBAL_PATHS`/`SOURCE_PINNED_RESEARCH_PATHS`/`PROTECTED_REVIEWER_PATHS` (`:143-160`) — these are literal `agents/...` strings
- `mise.toml:85-86` `research-os:install` run strings **and** `TASK_COMMANDS["research-os:install"]` (`scripts/validate_bundle.py:83`) — pinned run strings must move together
- `tests/test_install_skill_bundle.py` `make_repo` (`:42-51`) builds `root/skills`, `root/agents/claude`, … → must build under `root/plugin/`; 54 references to `skills/` in that file need sweeping
- `.codex-plugin/plugin.json:8` `"skills": "./skills/"` → `"./plugin/skills/"`
*Frozen artifacts:* `mise.lock` SHA **unchanged** (no `[tools]` edit); `MISE_LOCK_SHA256` (`:73`) unchanged; `LOCKED_TOOLCHAIN` unchanged. `TASK_COMMANDS` **does** change (research-os path).
Verify with `claude plugin validate --strict plugin/.claude-plugin/plugin.json` → must now pass, since `CLAUDE.md` is outside the plugin root (C2 resolved structurally). I confirmed this exact shape passes `--strict` in a synthetic probe.

**Step 5 — Ship the one hook.**
Add `plugin/hooks/hooks.json` + `plugin/hooks-handlers/guard-outward-effect.sh`. `validate_scripts` (`:1263-1271`) `bash -n`s only `scripts/*.sh`, so extend it to `plugin/hooks-handlers/*.sh` — a hook script that doesn't parse is a silent no-op.
*Frozen artifacts:* none.

**Step 6 — License + notices. No vendored content yet.**
`LICENSE`, `THIRD-PARTY-NOTICES.md`, `vendor.lock.json` (empty `sources`), `scripts/vendor_sync.py`, the two `vendor:*` tasks, and the digest check wired into `validate`. Resolve `plugin.json`'s `"license": "UNLICENSED"` against the new `LICENSE` — they must agree.
*Frozen artifacts:* none (extra tasks are free; `REQUIRED_TASKS` is a subset check at `:1095`).

**Step 7 — First vendored item, as a proof of the pipeline.**
One low-risk item (memo #10, merge-conflict discipline → a subsection of `references/worktree-integration.md`) with its `THIRD-PARTY-NOTICES.md` entry and digest. Prove `vendor:check` catches a deliberate one-byte edit.

**Step 8+ — Backlog drain**, one item per commit, each gate-green.

---

## 6. What this does NOT do

**Blockers that no amount of restructuring removes:**

1. **The private repo with zero releases/tags is still the binding constraint on "one-command install."** `Codeseys-Labs/agentic-sdlc` is private with zero releases and zero tags. The only path that reaches it today is a credentialed clone or `/plugin marketplace add git@github.com:...#<ref>` using the operator's own git credentials. **No anonymous one-command install exists, and none of this blueprint creates one.** `"source": "./plugin"` in `marketplace.json` is a *relative path* — it only works for someone who already has the tree. **User decision required: flip visibility to public, or accept credentialed-clone-only and drop "one-command from a fresh machine" as a goal.**

2. **Content drift between planes is a genuinely new failure mode this design introduces.** The plugin cache is a frozen copy (verified: real file copies, 8.8 MB, byte-identical at install time); the direct install is a live symlink into the worktree. After a `git pull` the direct plane updates instantly and the plugin plane does not until `claude plugin update`. Nothing here detects that. The `status()` note (§2) *discloses* the risk; it does not measure it. A real fix needs a content-hash cross-check against the cache — deliberately out of scope, and it should be a decision, not an assumption.

3. **Third-party marketplace auto-update is OFF by default** (only Anthropic's own marketplaces default on). So "the plugin plane updates itself" is **false** for this repo unless the operator opts in. Documenting subscription semantics we don't have would be the exact stale-claim failure `README.md:130` already made.

4. **`mise run check` remains the only authoritative gate.** The hook is best-effort convenience and uses `ask`, not `deny`, precisely so it cannot become an authority. Neither a passing gate, nor a green hook, nor a clean `status` authorizes push/merge/publish — each needs explicit operation-specific authorization.

5. **Step 4 is one large atomic commit and cannot be split.** `git mv` of four trees plus every pinned path constant plus the test fixture must land together or `check` fails mid-sequence. It is the highest-risk step; the payoff is that it structurally resolves the unfixable `CLAUDE.md` × `--strict` conflict (C2) and drops ~8.8 MB of `tests/`+`scripts/`+`docs/`+`.worktrees/` out of every user's plugin cache.

6. **I did not verify Codex/Gemini/OpenCode still resolve the moved trees.** `.codex-plugin/plugin.json` and `gemini-extension.json` get path edits in step 4, but I could not execute those hosts. **Verify before landing step 4** — the fallback plane is the entire justification for keeping the direct installer.

7. **Left open deliberately:** whether `plugin/` is the right name (`claude-plugin/` would collide confusingly with `.claude-plugin/`); whether the 17 Codex research roles belong in the Claude plugin cache at all (they are inert for Claude and pure payload weight — a second `plugin-codex/` root would shed them, at the cost of a second manifest to keep in version sync); and the `npm.package_manager = "npm"` supply-chain finding (`mise.toml:5`), which is real, independent of this restructure, and should be filed separately.

8. **ECC remains ~271 unvetted skills.** The pipeline in §4 makes vendoring *auditable*; it does not make unread content safe. Every item still needs individual review, and ECC's own README warns against non-canonical mirrors.