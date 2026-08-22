# pstack: porting cursor/plugins/pstack to a Claude Code plugin

2026-08-19

## Why

Asked whether `https://github.com/cursor/plugins/tree/main/pstack` — a Cursor-native
workflow plugin by Lauren Tan ("poteto") — could be installed globally as a Claude
Code plugin. Research established it could not, as-is: its manifest lived at
`.cursor-plugin/plugin.json` (Claude Code needs `.claude-plugin/plugin.json`), and its
skills were written against Cursor-only runtime primitives (`Task`/`subagent_type`,
`AskQuestion`, `/loop`, Cursor plan mode, `/create-skill`) with a hard cross-plugin
dependency on `cursor-team-kit` (`/deslop`, `control-cli`, `control-ui`). Decision: port
it rather than leave it unusable, since most of the mismatch was mechanical or had a
real Claude Code equivalent.

Everything below happened in a separate scratch workspace, not in this repository —
this doc is a record for future reference, not a change to this repo's own tooling.

## Where everything lives

- **Source checkout (sparse clone of `cursor/plugins`):**
  `~/.claude/local-plugins/pstack-src/` (git repo; `pstack/` and `cursor-team-kit/`
  checked out via `git sparse-checkout`)
- **The ported plugin:** `~/.claude/local-plugins/pstack-src/pstack/`
- **Local marketplace registration:** `pstack-local`, added via
  `claude plugin marketplace add ~/.claude/local-plugins/pstack-src/pstack --scope user`
- **Installed plugin:** `pstack@pstack-local`, `claude plugin install ... --scope user`,
  currently version `0.15.2`, cached at `~/.claude/plugins/cache/pstack-local/pstack/0.15.2/`

## What changed, in order

### 1. Manifest relocation and fix

- Moved `.cursor-plugin/plugin.json` → `.claude-plugin/plugin.json`.
- Dropped the `agents: "./agents/"` field — `claude plugin validate` caught this as a
  real schema error (Claude Code's `agents` field wants file paths, not a directory
  string; only `skills` accepts a directory). Both `skills/` and `agents/` are Claude
  Code's default auto-discovered folders anyway, so the fields were redundant on top
  of being wrong-shaped.
- Dropped `category`/`tags` from `plugin.json` (they belong on the marketplace entry,
  not the plugin manifest — `claude plugin validate` flagged this as a warning) and
  added them to `.claude-plugin/marketplace.json`'s plugin entry instead.
- Added `.claude-plugin/marketplace.json`, a single-plugin marketplace that
  self-references its own directory (`"source": "./"`), so the same directory serves
  as both the plugin and its own local marketplace.

### 2. Cursor-primitive substitution (~24 files)

Mechanical renames applied across `poteto-mode`, its playbooks, `how`, `swarm`,
`interrogate`, `reflect`, `setup-pstack`, `why`, `automate-me`, `no-comments`, README,
and the docs guide:

| Cursor | Claude Code |
|---|---|
| `AskQuestion` | `AskUserQuestion` |
| `Task` (tool name) | `Agent` |
| `subagent_type: generalPurpose` | `subagent_type: general-purpose` |
| `environment: "cloud"` / `"local"` | `isolation: "remote"` / omitted (default) |
| "Cursor" in prose (editor/product sense) | "Claude Code", or the closest real analog |

Two cross-plugin dependencies got real substitutes instead of stubs, once it became
clear their source (`cursor-team-kit`, same monorepo) was itself portable:

- **`deslop`, `control-cli`, `control-ui`** — copied verbatim from `cursor-team-kit`
  into `pstack/skills/`. All three were already editor-agnostic (tmux/PTY/Playwright
  harnesses, no Cursor coupling), so no rewriting was needed, just relocation.
- **`create-skill`** — no source existed to port (Cursor's is a native built-in with
  no file-based implementation), so this one was authored from scratch, matching
  pstack's own terse skill-authoring voice.

Every skill/playbook that referenced these (`poteto-mode`, `orchestrate`, `shipping`,
`autopilot-full`, `automate-me`, `reflect`, the README's skill table) got its
cross-references rewired to point at the real bundled skills instead of a
"no equivalent, do X manually" stub.

### 3. `.cursor/` filesystem path sweep (~18 more files)

A completeness check surfaced a second, separate gap: lowercase `.cursor/...`
filesystem-path conventions that the prose substitution pass never touched (rules
files, skills dirs, projects dirs, plugins dirs). Mapped each to a verified Claude Code
equivalent:

- `~/.cursor/rules/pstack-models.mdc` → `~/.claude/pstack-models.md`, and the
  "always-applied rule" framing dropped — Claude Code has no engine that
  auto-injects an arbitrary plugin-owned file into every conversation the way
  Cursor's `.mdc` rules do, so skills now read this file explicitly on demand
  instead.
- `.cursor/skills/` / `~/.cursor/skills/` → `.claude/skills/` / `~/.claude/skills/`.
- `~/.cursor/plugins/` → `~/.claude/plugins/` (confirmed against the real installed
  cache path).
- `~/.cursor/projects/<slug>/` → `~/.claude/projects/<slug>/`, and the slug algorithm
  description in `recall/SKILL.md` corrected to match Claude Code's real observed
  scheme (leading slash becomes a leading dash, not dropped — confirmed against this
  very session's own transcript paths).
- One illustrative worktree-location example (`.cursor/worktrees/myrepo/x`) was
  genericized rather than mapped, since Claude Code's internal worktree-storage
  convention isn't publicly documented and wasn't worth guessing.

### 4. Benny — the Slack issue-triage/repro automation pack

`automations/benny/` (triage + reproduce-and-fix Slack bot pair) was initially left
out, then added on request. Its actual *logic* — `triage-issue-reports`,
`reproduce-and-fix-issues`, and their reference files (control-adapter contract,
existing-fix verification, feature-map format, routing-map format) — turned out to be
almost entirely editor-agnostic already; moved as-is into `pstack/skills/`.

The one genuinely non-portable piece: Cursor's **Automations editor** — a hosted,
event-triggered, always-on backend with its own setup UI (`/automate`, draft
review/approval, editor handoff). Claude Code has no equivalent product tier at all
(no hosted webhook listener, no persistent background daemon). Rather than fake this,
`setup-benny/SKILL.md` §7 documents two real, honest mechanisms instead:

- **`CronCreate` polling** (default) — zero extra infrastructure, but not real-time
  (latency = poll interval) and capped by `CronCreate`'s 7-day recurring-job
  auto-expiry, needing periodic renewal.
- **A self-hosted Slack-events listener calling `claude -p`** — genuinely real-time and
  durable, but the user builds and hosts the listener process; a plugin can't ship an
  always-on service.

Other real fixes made in the same pass:

- Dropped the original "copy the whole pack into the target repo" step entirely — it
  existed because Cursor's hosted automations couldn't necessarily see the user's
  local plugin cache, a constraint that doesn't apply to Claude Code (any invocation
  already runs from a session that has the global plugin installed).
- `slack.prefer_cursor_actions` config field removed. Claude Code has no native Slack
  integration to prefer, so calling the real Slack Web API
  (`conversations.history`, `conversations.replies`, `chat.postMessage`, `files.info`,
  `chat.update`) via `BENNY_SLACK_BOT_TOKEN` is now the primary path, not a fallback.
- `.cursor/benny/` config/secret paths → `.claude/benny/`.

**Caveat, not yet verified:** Claude Code's own native scheduled-tasks feature won't
fire a `disable-model-invocation: true` skill (both benny skills set this) when that
skill is configured as the task's designated action. This is believed *not* to affect
the `CronCreate` design above, since `CronCreate` enqueues plain prompt text (which the
fired session reads and acts on) rather than assigning a skill as a structured task
action — but this distinction hasn't been tested against a live `CronCreate` job.

### 5. Bugs found and fixed along the way

- **`plugin.json` `agents` field, wrong type** (see §1) — caught by
  `claude plugin validate`, not by inspection.
- **`poteto-mode/SKILL.md` frontmatter `name: Poteto Mode`** — the single skill (of
  51) whose frontmatter `name` didn't match its directory name. In Cursor this was a
  cosmetic display label; in a Claude Code *plugin* skill, `name` becomes the literal
  last segment of the slash command, so this would have registered as
  `/pstack:Poteto Mode` instead of the expected `/pstack:poteto-mode` — pstack's own
  flagship "just use this" skill. Fixed to `name: poteto-mode`.
- **Stale-cache installs** — `claude plugin install`/`update` silently no-ops when
  `plugin.json`'s `version` string hasn't changed, even after real source-file edits,
  because Claude Code uses that string (not file contents) for update detection on a
  local-path source. Required an explicit version bump (`0.14.1` → `0.15.2` across the
  session) before each `claude plugin update pstack@pstack-local` to actually pick up
  changes.
- Confirmed empty leftover directory husks under `automations/` (from `git mv`, no
  files) were harmless — verified the installed cache never carried real duplicate
  files — then deleted them for tidiness.

## Final installed state

`claude plugin validate ~/.claude/local-plugins/pstack-src/pstack` passes clean.
`pstack@pstack-local` is installed at user scope, enabled, version `0.15.2`.

51 skills total, namespaced `/pstack:<name>`:

- **9 auto-invocable + manual** (no `disable-model-invocation`): `control-cli`,
  `control-ui`, `create-skill`, `deslop`, `how`, `setup-pstack`,
  `typescript-best-practices`, `unslop`, `why`.
- **42 manual-only** (`disable-model-invocation: true`, still fully typable by name):
  `poteto-mode`, `architect`, `arena`, `automate-me`, `blast-radius`, `bro`,
  `create-verification-skill`, `figure-it-out`, `interrogate`,
  `maintain-verification-skill`, `no-comments`, `recall`, `reflect`,
  `reproduce-and-fix-issues`, `setup-benny`, `show-me-your-work`, `swarm`, `tdd`,
  `teach`, `technical-writing`, `triage-issue-reports`, and 21 `principle-*` skills.

2 agents (`subagent_type` values, not slash commands): `poteto-agent`, `Comment Sicko`.

Root cause of the "only 9 pstack skills showing up" concern that prompted a re-check:
the "available skills" listing and the `/reload-plugins` skill-count summary only
surface auto-invocable skills. That's expected behavior given pstack's own design
(most of it is meant to be triggered explicitly), not a broken install — confirmed by
enumerating the actual installed cache directly rather than relying on that summary.

## What's still approximate or unverified

- Benny's trigger mechanism (§4) is a genuine engineering substitute for a capability
  tier Claude Code doesn't have, not a 1:1 port — the polling vs. self-hosted-listener
  tradeoff is real and documented in `setup-benny/SKILL.md`, but neither path has been
  exercised end-to-end against a live Slack workspace.
- The `disable-model-invocation` / scheduled-tasks interaction noted in §4 hasn't been
  tested against a real `CronCreate` job.
- Deep internal Claude Code transcript-file layout (exact filenames under
  `~/.claude/projects/<slug>/`) is undocumented; only the root path prefix was fixed
  with confidence, not every inner path detail `recall/SKILL.md` describes.
