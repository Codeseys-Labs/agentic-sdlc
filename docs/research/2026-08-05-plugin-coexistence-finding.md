# Plugin and direct install do not collide — the exclusivity is policy, not mechanism

**Date:** 2026-08-05 · **Status:** verified by execution and inspection · **Bearing:** decides
whether "install as a plugin *in addition to* the global install" is a conflict to resolve or a
restriction to lift.

## The claim under test

`README.md:280` and `AGENTS.md` state: *"For Claude, use either direct install or the
marketplace, never both; marketplace overlap blocks only Claude."* The installer enforces it:
`scripts/install_skill_bundle.py:1447` `marketplace_overlap()` scans
`~/.claude/plugins/{marketplaces,cache}` for `agentic-sdlc` / `agentic-sdlc-orchestrator` and
the two manifests, and at `:2613` sets `claude_blocked`, which at `:2621-2625` marks every
Claude-plane entry `marketplace overlap: <destination>`, sets `partial = True`, and `continue`s
past it. Net effect: **exit code 1 and zero Claude skills installed.**
`tests/test_install_skill_bundle.py:556` pins exactly that behaviour — Claude skills absent,
Codex skills present, exit 1.

## What is actually true

Plugin-provided components and directly-installed components **never occupy the same
filesystem paths**, and Claude Code **namespaces** plugin skills so they cannot shadow global
ones either.

Evidence:

1. An installed plugin's skills live under
   `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/skills/` — confirmed at
   `~/.claude/plugins/cache/claude-plugins-official/huggingface-skills/1.0.17/skills`.
2. Those skills are **not** symlinked or copied into `~/.claude/skills/` — searching that
   directory for `hf-cli`/`huggingface` returns nothing.
3. Plugin agents are likewise absent from `~/.claude/agents/`: that directory contains the 14
   `hyperresearch-*` agents (globally installed) and **zero** agents from any installed plugin.
4. The skill namespace proves the separation from the consuming side. In this session's
   available-skills list, globally installed skills appear bare (`hyperresearch`,
   `adr-methodology`, `tdd`) while plugin-provided ones appear qualified
   (`huggingface-skills:hf-cli`, `superpowers:brainstorming`, `ponytail:ponytail`).
   An agentic-sdlc plugin would therefore expose `agentic-sdlc:<skill>`, distinct from a
   direct install's bare `<skill>`.

The direct installer writes only to `~/.claude/{skills,agents,commands}` and `~/.codex/…`
(verified by installing into a throwaway `--home`). The plugin cache is a disjoint subtree.

## Consequence

`marketplace_overlap()` does not prevent a filesystem collision, because there is none to
prevent. It encodes a **policy** choice — presumably against a skill being double-loaded under
two names, or against ambiguous ownership of one logical entry. Whatever the original reason,
the mechanism it protects against does not exist, and the cost is concrete: with the plugin
installed, `mise run bundle:install` cannot install any Claude skill and reports exit 1.

Two real risks survive and should be handled deliberately rather than by blanket exclusion:

- **Duplicate presentation.** The same skill reachable as both `<skill>` and
  `agentic-sdlc:<skill>` spends selection budget twice and can confuse a router. This argues
  for choosing one plane per component *by default*, not for failing closed.
- **Ownership ambiguity on uninstall.** If both planes are active, `bundle:uninstall` must not
  claim to have removed a capability the plugin still provides. The state file already tracks
  per-entry ownership, so this is reportable rather than fatal.

## Recommendation

Relax the block to a **per-component, reported** condition rather than a Claude-plane-wide
failure, and let the two planes divide by capability:

| Component | Plane | Why |
|---|---|---|
| skills, agents, commands | either (operator's choice, default direct) | both planes can carry them; namespacing keeps them distinguishable |
| Claude Code hooks, MCP config | **plugin only** | the symlink installer writes no `settings.json`, no hooks, no MCP — verified zero matches for `settings.json\|SessionStart\|PreToolUse\|mcp` in `scripts/install_skill_bundle.py`. This is capability the plugin plane uniquely has |
| Codex / other hosts | direct install only | plugins are Claude-specific |

Downgrading `marketplace overlap` from a blocking condition to a warning requires updating
`tests/test_install_skill_bundle.py:556`, which currently asserts exit 1 and absent Claude
skills. That test is pinning the old policy, so it must change in the same commit — and the
change should be an explicit policy decision recorded in `AGENTS.md`/`README.md`, not a quiet
edit, since the current doctrine text says the opposite.

## Live plugin install: what actually gets discovered (executed 2026-08-05)

Installed the plugin from a **local filesystem path** into an isolated `HOME` (the private
GitHub remote is not required for this):

```
claude plugin marketplace add /path/to/agentic-sdlc     # ✔ added (Source: Directory)
claude plugin install agentic-sdlc@agentic-sdlc          # ✔ installed (scope: user)
claude plugin details agentic-sdlc@agentic-sdlc
```

Result — **`Skills (12)`, `Agents (0)`, `Hooks (0)`**, projected always-on cost **~1,092 tokens
per session**:

- The 12 "skills" are the 8 real skills **plus the 4 commands** (`sdlc-frame`, `sdlc-init`,
  `sdlc-mission`, `sdlc-wave`), which the loader picked up from the root-level `commands/`.
- **`Agents (0)` is a reporting artifact, NOT a discovery failure — corrected 2026-08-05.**
  My first reading of this was wrong. I had concluded from `Agents (0)` (reproduced twice) plus
  the flat-`agents/` layout of every other installed plugin that this repo's host-nested
  `agents/claude/*.md` was invisible to the plugin loader, and that a restructure was needed.
  A workflow agent refuted it by asking a **live session** to enumerate its Task-tool subagent
  types instead of trusting the `details` command. I then reproduced that result independently
  in a fresh isolated `HOME`:

  ```
  agentic-sdlc:claude:sdlc-cartographer   agentic-sdlc:claude:sdlc-planner
  agentic-sdlc:claude:sdlc-critic         agentic-sdlc:claude:sdlc-researcher
  agentic-sdlc:claude:sdlc-implementer    agentic-sdlc:claude:sdlc-reviewer
  agentic-sdlc:claude:sdlc-integrator     agentic-sdlc:codex:research:README
  ```

  All 7 Claude agents load, namespaced `agentic-sdlc:<subdir>:<name>` — the runtime loader
  **recurses one level and encodes the subdirectory into the namespace**, while
  `claude plugin details` counts only the flat `agents/*.md` tier. **`claude plugin details` is
  not a discovery oracle; enumerate subagent types in a live session instead.** The existing
  `agents/claude/` + `agents/codex/` co-location is already correct and already works, so
  flattening `agents/` would be a regression, not a fix. The same agent verified that the
  manifest `agents` key cannot point at a directory at all (`"./agents/claude/"` and
  `["./agents/claude"]` both fail schema validation; a single-file entry installs but does not
  load) — omitting the key and relying on auto-discovery is the only working configuration.
- **`agentic-sdlc:codex:research:README` is a live pseudo-agent bug.** The same recursion turns
  `agents/codex/research/README.md` — a plain README with no frontmatter — into a loadable
  subagent. This is the file `claude plugin validate --strict` already warns about, so the
  warning has a real runtime consequence, not a cosmetic one. Fix by giving it frontmatter or
  moving it out of any tree the loader scans.
- **`Hooks (0)`** because no `hooks/hooks.json` exists yet. Adding one at the repo root is all
  that is needed; the plugin cache is a literal copy of the repo root, so no extra plumbing.

Two costs worth knowing before committing to the plugin plane:

1. **The entire repo is copied into the plugin cache — 8.8 MB**, including `docs/`,
   `SESSION-HANDOFF.md`, `mise.toml`/`mise.lock`, `lefthook.yml`, `.github/`, and `policy/`.
   **But the copy is inert for a directory-source marketplace — corrected 2026-08-06.** I set up
   a probe plugin, installed it, then mutated **only the source tree** and asked a live session
   which body it saw:

   ```
   cache marker:  MARKER_ORIGINAL_AAA
   source marker: MARKER_MUTATED_ZZZ
   live session → MARKER_MUTATED_ZZZ
   ```

   The runtime reads the **source tree**, not the cache (corroborated separately by
   `CLAUDE_PLUGIN_ROOT` resolving to the source directory). So the 8.8 MB is wasted disk, not a
   staleness or drift hazard, and edits to a directory-sourced plugin take effect without
   reinstalling. `claude plugin marketplace add --sparse <paths...>` still exists if the disk
   cost matters. This also removes the main argument for restructuring the tree to slim the
   payload.
2. **~1,092 always-on tokens** added to every session, on top of whatever the direct install
   already costs. If both planes carry the same skills, that always-on cost is paid twice for
   the same capability — the strongest practical argument for dividing components by plane
   rather than duplicating them.

Also confirmed from `claude plugin install --help`: plugins support a `userConfig` schema
(`--config <key=value>`, validated against the manifest, same path as `/plugin configure`),
which is a real mechanism for operator-tunable settings the symlink installer has no equivalent
for.

## Also true, and unrelated to coexistence

`claude plugin validate --strict` behaves differently depending on the argument, and this is
what makes `README.md:130`'s claim misleading rather than simply false:

- `claude plugin validate --strict .` (directory) validates **only the marketplace manifest** —
  and **passes**.
- `claude plugin validate --strict .claude-plugin/plugin.json` **walks the plugin's components**
  — and **fails** on two warnings-as-errors: `CLAUDE.md` at plugin root is not loaded as project
  context, and `agents/codex/research/README.md` has no frontmatter.

So the claim is true for the invocation most people type and false for the one that actually
inspects components. Reword it to name the invocation rather than deleting it.

**The `CLAUDE.md` warning cannot be fixed in place — it is a direct conflict with the frozen
gate.** `scripts/validate_bundle.py:1240-1242` *requires* a root `CLAUDE.md` beginning with
`@AGENTS.md` (verified: it does), and `tests/test_gate_graph.py` pins that. Deleting or moving
`CLAUDE.md` to satisfy plugin `--strict` breaks `mise run check`. The two requirements are
mutually exclusive at the repo root, which means the only resolutions are: accept the strict
warning permanently, or move the **plugin root** into a subdirectory so the plugin's root and
the repo's root are no longer the same directory. That is a genuine architectural decision, not
a lint fix.
`.claude-plugin/marketplace.json` also sets `"source": "./"`, a local path — usable with a
filesystem marketplace add, but not a remote install path while the GitHub repo is private
with no releases.
