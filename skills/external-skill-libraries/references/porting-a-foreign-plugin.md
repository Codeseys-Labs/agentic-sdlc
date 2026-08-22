# Porting a foreign host plugin to Claude Code — a reusable recipe

Generalized from one executed port: a Cursor plugin (`pstack`, from
`github.com/cursor/plugins`) rewritten into a locally installed Claude Code plugin, registered
through a local marketplace the operator points at their own checkout. That run is recorded
first-person in `docs/progress/2026-08-19-pstack-claude-code-port.md`. That record is executed
evidence — the steps below were actually run and their results actually observed, not inferred
from either host's documentation. This artifact re-expresses the pattern in this bundle's own
words and does not quote the ported plugin's own files. Every claim below traces to that
progress record rather than to a live inspection of an operator's plugin checkout: a ported
tree is a working copy that has already diverged from its own upstream by design (edited,
renamed, and added files are the whole point of a port), so it is never a source this bundle
cites for what an upstream host or plugin canonically ships. Where the progress record does not
settle a claim, this artifact marks it UNVERIFIED instead of promoting it.

## Read this first: what kind of operation this is, and what it is not

**This is a porting guide, not a catalog row.** `skills/external-skill-libraries/` and
`docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md` govern a
*closed*, three-entry catalog (`mattpocock/skills`, ECC, hyperresearch) of libraries installable
through their own published front doors, with zero bytes copied into any repository. Porting a
foreign host's plugin is a different shape entirely: it means reading dozens of foreign files,
rewriting the primitives they call, relocating a manifest, and producing a *forked* artifact
that lives in the operator's own plugin tree. Nothing about this recipe is a fourth row for that
catalog, and nothing here should be read as proposing one. A port has no upstream front door
that does the rewriting for you — that is the entire reason it takes a recipe instead of a
one-line install command.

**No vendoring, here either.** The source boundary in
`docs/adr/0001-mit-license-and-root-notice-attribution.md` and
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md` — no foreign bytes,
prose, or skill text copied into *this* repository's tree — applies with exactly the same force
to this artifact. This document describes the recipe in this bundle's own words. If a future
editor of this file finds themselves pasting a sentence out of a ported plugin's file to
illustrate a step, that is the signal to stop and re-express it instead: a near-verbatim quote
here would require the same `NOTICE` donor-entry machinery ADR-0001 defines, and that machinery
is out of scope for a recipe doc. The *port itself* (in the operator's own plugin directory, not
this repository) is a different matter — it is a full copy-and-adapt of upstream content into a
new home, under the upstream author's own licence, and it is not this repository's concern
either way, because none of its bytes enter this repository.

## 1. The manifest relocation and the schema errors validation catches

A source host's plugin manifest and Claude Code's are rarely the same shape on disk, and the
first fix is always structural, before any prose substitution:

- **Worked example (pstack, Cursor → Claude Code): the `agents` field type error.** Cursor's
  plugin manifest lived at `.cursor-plugin/plugin.json`; Claude Code's equivalent lives at
  `.claude-plugin/plugin.json`. Moving the file is necessary but not sufficient — the schema
  underneath differs too. The source manifest declared `agents: "./agents/"` — a directory
  string, mirroring how the same manifest's `skills` field points at a folder. Claude Code's own
  manifest validator rejected this: its schema wants `agents` to be an array of individual file
  paths, not a directory string; only `skills` accepts a directory reference. This is the
  load-bearing example because it is a defect a *validator catches and inspection does not* — the
  field looks superficially correct (a real path, pointing at a real directory that really
  contains the agents) and would pass a human read-through. Since `agents/` is one of Claude
  Code's default auto-discovered folders regardless of the manifest, the fix was simply to drop
  the field rather than reformat it.
- The same validator flagged `category`/`tags` in `plugin.json` as a *warning*, not an error —
  those belong on the marketplace entry (`.claude-plugin/marketplace.json`), not the plugin
  manifest. A warning is still worth acting on: those two fields moved to the marketplace
  document's plugin entry instead of being dropped.
- A single-plugin local marketplace is its own small file, and it can legitimately
  self-reference its own directory (`"source": "./"`) — one directory serves as both the plugin
  and the marketplace that registers it. Confirmed in the executed record: the port's own
  `.claude-plugin/marketplace.json` has exactly this shape, with `"source": "./"` and the moved
  `category`/`tags` fields.
- **Operating rule this generalizes to:** always run the target host's own manifest validator
  (`claude plugin validate <path>` for Claude Code) *before* trusting a hand-read of the schema
  docs, whatever the source host was. A schema mismatch that "looks like a directory reference
  should work" is exactly the class of bug a validator exists to catch, and this port found one
  on the very first file it touched.

## 2. The runtime-primitive substitution table, as a pattern

Two hosts expose different names for adjacent runtime concepts. Build a substitution table for
every port; the row set is host-pair-specific, but the pattern generalizes. Restated in this
bundle's own vocabulary — not a copy of either host's API reference — here is the worked
Cursor-to-Claude-Code instance:

| Source-host concept | Claude Code equivalent | Why this is a real substitute, not an approximation |
|---|---|---|
| A question-to-user tool invoked as `AskQuestion` | `AskUserQuestion` | Same runtime role (pause and ask), different literal tool name |
| The dispatch primitive named `Task` | `Agent` | Same runtime role (spawn a subagent), different literal tool name |
| A subagent type value `generalPurpose` | `general-purpose` | Same semantic subagent class, different literal string casing/format the host expects |
| An execution-location hint `environment: "cloud"` / `"local"` | `isolation: "remote"` / field omitted (Claude Code's local default) | Different field *name* and different value vocabulary for the same underlying local-vs-remote execution distinction |
| The source host's own product name, used in prose in the editor/product sense | "Claude Code", or the nearest real analog if the sentence describes an editor-specific behavior | A plain find/replace is wrong whenever the sentence is really describing the source host's own product behavior rather than "whatever editor you're in" — read each hit, don't blind-substitute |

Treat this table as a *starting checklist* for any port into Claude Code, not a closed list — a
different plugin, or a different source host entirely, may reference other host-only primitives
(plan-mode equivalents, other tool names) that this port's plugin didn't happen to use.

## 3. The filesystem-path sweep is a SEPARATE pass, run after the prose pass

The single highest-value finding to carry forward: **a prose/primitive substitution pass does
not touch lowercase filesystem-path conventions.** In the executed port, the primitive-renaming
pass (roughly two dozen files) was believed complete, and a *separate, later* completeness check
surfaced a second gap of comparable size (roughly eighteen more files) — every place the source
material referenced the source host's own dotdir as a literal directory path (rules files,
skills dirs, projects dirs, plugins dirs), none of which the "replace the product name in prose"
pass had reason to catch, because a lowercase path segment like `.cursor/foo/bar` doesn't read
as a capitalized product mention to a substitution pass scanning for those.

Run the path sweep as its own explicit step, searching for the literal lowercase source-host
config directory name (`.cursor/`, or whatever the source host's dotdir is), separately from —
and after — the prose/primitive pass. Concretely, in the executed port this meant mapping:

- `~/.cursor/rules/*.mdc` → the target host's nearest equivalent, *and checking whether the
  target host even has the source mechanism*. Per the executed record, Claude Code has no engine
  that auto-injects an arbitrary plugin-owned file into every conversation the way Cursor's
  always-applied `.mdc` rules do, so the port dropped the "always applied" framing entirely and
  rewrote the affected skills to read the file explicitly on demand instead. Do not map a path
  1:1 if the *mechanism* backing it doesn't exist on the target host; map the path only after
  confirming the mechanism, or state plainly that no mechanism exists.
- `.cursor/skills/` / `~/.cursor/skills/` → `.claude/skills/` / `~/.claude/skills/` — a direct,
  confirmed mapping.
- `~/.cursor/plugins/` → `~/.claude/plugins/` — confirmed against Claude Code's own installed
  plugin cache layout (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`, per the
  executed record).
- `~/.cursor/projects/<slug>/` → `~/.claude/projects/<slug>/`, **and** the slug-construction
  algorithm itself needs independent verification, not just the path prefix. Per the executed
  record, the slug turns a leading `/` into a leading `-` and every subsequent `/` into `-`.
  Applying that rule to a freshly invented path purely for illustration, `/srv/demo/app` turns
  into `-srv-demo-app`; the port corrected this from an earlier draft that had the leading slash
  simply dropped rather than converted to a dash. A path-prefix mapping can be right while an
  inner detail of the same sentence is wrong; check both.
- One illustrative example path with no confirmable target-host equivalent (a source-host
  internal worktree-storage location) was **genericized rather than mapped**, because Claude
  Code's internal worktree-storage convention is not publicly documented. Guessing at an
  undocumented internal path and writing it down as fact would be worse than admitting the
  example is illustrative only.

**Operating rule:** budget two passes, not one — primitive/prose substitution, then an
independent grep for the source host's literal lowercase dotdir path across the whole tree. Do
not assume the first pass's file list is a superset of the second's; in the executed port it was
not.

## 4. The frontmatter trap: a display label becomes a literal slash-command segment

Some source hosts treat a skill's `name:` frontmatter field as a cosmetic display label. Claude
Code, when the skill is packaged inside a *plugin*, treats `name:` as the literal final segment
of the slash command the skill registers as. These are not the same contract, and a name that
looks harmless in the source host can silently break the target host's invocation surface.

**Worked example:** the source plugin's flagship skill had frontmatter `name: Poteto Mode` while
living in a directory named `poteto-mode`. In Cursor this was purely cosmetic. In a Claude Code
plugin it would have registered as `/pstack:Poteto Mode` — a slash-command segment containing a
literal space and capital letters — instead of the expected `/pstack:poteto-mode`. Per the
executed record, the fix was a one-line frontmatter edit to `name: poteto-mode`, matching the
directory name.

The progress record calls out that this was the *only* skill of 51 with a mismatched `name:`,
which is exactly why it is easy to miss — a single outlier surrounded by fifty correct examples
does not get caught by "does the pattern generally look right," only by checking every single
one, or by installing and testing every command's actual invocation surface.

**Operating rule:** treat every skill's frontmatter `name:` as a literal slash-command segment
the moment the skill is packaged in a plugin, and diff it against the directory name for every
single skill — not a sample — before considering a port's manifest pass complete.

## 5. The version-string cache trap

`claude plugin install` and `claude plugin update` key their change-detection on the
`plugin.json` `version` string for a local-path source, **not on file contents**. Editing
source files without bumping the version string produces a silent no-op: the command exits
cleanly, appears to have updated, and the cache still holds the pre-edit bytes.

**Operating rule generalized from the port:** bump the version string as a matter of routine
before every `claude plugin update` call during an active porting session, even for a change
that seems like it should obviously trigger a refresh. Per the executed record, this port needed
multiple version bumps across a single session (a recorded range of `0.14.1` → `0.15.2`) purely
to make edits actually take effect against the installed cache — treat "did I bump the version"
as a standing pre-flight check on every update invocation, not an occasional afterthought. If the
installed behavior after an edit doesn't seem to change, check the version string before
assuming the edit itself was wrong.

## 6. Handling a cross-plugin dependency: three outcomes, never a silent stub

A source plugin frequently depends on sibling skills from another plugin in the same upstream
ecosystem. Three genuinely different resolutions apply, and picking the wrong one either wastes
effort or ships a broken cross-reference:

1. **Substitute from the sibling, when the dependency is genuinely host-agnostic.** If the
   dependency's actual implementation has no source-host-specific coupling — no calls to
   source-host-only tools, no source-host-only path conventions — relocating it into the target
   plugin costs only the move, not a rewrite. In the executed port, three sibling skills (a
   code-cleanup skill and a pair of terminal/browser control-harness skills) turned out to
   already be host-agnostic (tmux/PTY/browser-automation-based, no source-host coupling) once
   inspected, so they were relocated as-is rather than rewritten.
2. **Author from scratch, when the source is a host built-in with no file-based implementation
   at all.** Some source-host-only capabilities (a native "create a skill" flow, in the executed
   port's case) have no upstream file to port — the source host implements the behavior inside
   its own closed runtime. The correct move is to write a fresh implementation matching the
   *voice and contract* of the surrounding ported material, not to search for source that does
   not exist.
3. **Never stub silently.** The wrong move — leaving a cross-reference pointing at a placeholder
   telling the operator to reproduce the missing behavior by hand — was explicitly identified and
   corrected in the executed port: every skill and playbook that referenced the relocated or
   authored-from-scratch dependencies had its cross-references rewired to point at the real
   bundled replacement, rather than left as a dead-end note. A stub that looks like documentation
   but resolves to nothing is worse than an honest gap, because it reads as done.

**Operating rule:** for every cross-plugin reference found in the source material, classify it
into exactly one of these three buckets before writing anything, and if a dependency is left
unresolved, mark it as an open gap in the port's own tracking rather than leaving prose that
implies it works.

## 7. The honest treatment of a capability tier the target host lacks

Some source capabilities depend on a product tier the target host simply does not have at any
price point — not a missing file to port, a missing *product feature*. The correct response is
neither "fake it with the closest thing" nor "silently drop the capability"; it is to document
the real mechanisms that exist, including their honest tradeoffs, and let the operator choose.

**Worked example: the hosted-automations case.** The source ecosystem included an
issue-triage/reproduce-and-fix automation pack whose *logic* (the actual triage and repro-and-fix
skill behavior, plus their reference contracts) turned out to be almost entirely host-agnostic
and portable as-is. The one genuinely non-portable piece was the source host's hosted,
event-triggered, always-on automations backend, with its own setup UI (draft review, approval
flow, editor handoff). The target host has no equivalent product tier: no hosted webhook
listener, no persistent background daemon it ships. Per the executed record, the port's own setup
skill names this gap directly rather than pretending one mechanism is equivalent to the missing
tier, and documents two real, honest alternative mechanisms instead:

- **Scheduled polling via the target host's own cron-style primitive (`CronCreate` in Claude
  Code), as the default.** Costs zero extra infrastructure. Tradeoffs stated plainly rather than
  hidden: delivery latency is capped by how often the poll runs rather than arriving instantly,
  and per the executed record the primitive's own recurring-job window auto-expires after seven
  days, so keeping it running means renewing that window on a recurring basis.
- **A self-hosted, externally-run event listener calling into the target host's CLI in
  headless/print mode.** Genuinely real-time and durable — but the operator must build and host
  that listener process themselves; a plugin cannot ship an always-on service, because a plugin
  is code that runs inside a session, not a standing service outside one.

Both mechanisms are real and both are documented with their real cost, rather than the port
picking one and presenting it as a drop-in replacement for the missing hosted tier.

**Operating rule:** when a source capability depends on a product tier the target host lacks,
name the missing tier explicitly, then document every real mechanism the target host *does*
have that gets partway there, each with its own honest tradeoff — never silently substitute one
mechanism while implying it matches the missing tier's guarantees.

## 8. A checklist a porter can run top to bottom

1. Confirm the target host's manifest location and schema; run its own validator (not a hand
   read of docs) against the relocated manifest, and fix every error and warning it reports —
   the `agents`-field type error above is the reminder that inspection alone will miss real
   schema mismatches.
2. Build (or reuse) a primitive-substitution table for every source-host-only tool name,
   subagent-type value, execution-environment field, and product-name mention in prose. Read
   each prose hit before substituting — the source host's product name used in a sentence
   describing that host's specific behavior needs a different fix than the same name used
   generically.
3. Run a **separate** sweep for the source host's literal lowercase dotdir path (`.cursor/...`
   or equivalent) across the whole tree, after the prose pass, not folded into it. For each hit,
   confirm the *mechanism* exists on the target host before mapping the path; genericize rather
   than guess when it doesn't, and say so.
4. Check every skill's frontmatter `name:` against its own directory name, individually, for
   every skill in the port — not a sample — before treating the manifest pass as done.
5. For every cross-plugin dependency, classify it as (a) portable-as-is from a genuinely
   host-agnostic sibling, (b) author-from-scratch for a host built-in with no file
   implementation, or (c) explicitly unresolved-and-tracked. Never leave a silent stub.
6. For any capability that depends on a product tier the target host lacks entirely, name the
   gap explicitly and document every real mechanism that exists instead, with its own tradeoffs
   — do not fake equivalence.
7. Before every `plugin update`/reinstall during the session, bump the version string in the
   manifest; a version-unchanged reinstall is a silent no-op regardless of file edits.
8. Run the target host's own validator again at the end, then actually install and invoke a
   sample of the ported commands (not just the manifest check) to confirm the frontmatter and
   path fixes hold at runtime, not just on disk.
9. Record what remains unverified, explicitly, rather than implying full parity. An honest "not
   yet exercised end-to-end" line is worth more than silence. When a claim is about what the
   *source* host or plugin canonically ships, source it from a pristine read of the upstream
   material (or from a contemporaneous written record made before any edits), never from the
   working copy the port has since modified.

## 9. What this recipe does NOT make safe

- **It does not make the port an installable catalog entry in this bundle.** ADR-0009's catalog
  is closed to three names reached through their own upstream front doors; a port is a fork that
  lives in the operator's own plugin tree and is never proposed as a fourth row, no matter how
  clean the port turns out.
- **It does not verify upstream licence compliance for you.** The source material's licence
  travels with the fork under the upstream author's own terms; this recipe describes mechanical
  porting steps, not a licence review. Re-check the source licence's obligations independently
  for whatever you port.
- **It does not verify that ported logic is *correct*, only that it is *host-compatible*.** A
  primitive substitution table, a path sweep, and a frontmatter fix get a plugin to load and its
  commands to register with the right names. None of that is evidence that the underlying
  workflow logic behaves the same way it did on the source host — that requires actually running
  the ported skills against real tasks, which is a separate verification effort from this
  recipe's checklist.
- **It does not resolve a capability gap; it only documents it honestly.** Section 7's two
  mechanisms are real substitutes with real costs, not a claim that the target host has reached
  parity with the missing product tier. Treat every "target host lacks X" finding as a permanent
  constraint to communicate, not a problem this recipe solves.
- **It does not exempt the port from this bundle's own no-vendoring boundary should any of its
  material ever be considered for inclusion *inside* this repository.** Everything in this
  recipe describes work happening in the operator's own separate plugin tree, outside this
  repository. If a future editor ever wants to pull an idea from a ported plugin into this
  bundle's own skills, that is a *different* operation — governed by ADR-0001's
  adaptation-plus-`NOTICE` path, not by anything in this artifact — and it starts over from that
  gate, not from "it already worked in the port."
- **It does not make a stale recipe self-updating.** Every fact this artifact draws on was
  checked against one execution, on one date, against one plugin. A different foreign plugin may
  use primitives this table doesn't cover, or a future Claude Code release may change the
  `name:`/slash-command contract this recipe leans on. Re-verify against the target host's
  current behavior rather than trusting this document's specifics to still hold.
- **It does not treat a ported working copy as evidence of what any upstream canonically
  ships.** A port is, by design, a modified fork of its source the moment the first file is
  edited. Any future claim about upstream naming, manifest shape, front door, or licence surface
  belongs to a pristine read of that upstream, not to inspection of a plugin tree this recipe (or
  any port) has already changed.

## Sources

- `docs/progress/2026-08-19-pstack-claude-code-port.md` — the executed, first-person record this
  artifact generalizes from; the sole source for every worked-example claim above.
- `skills/external-skill-libraries/SKILL.md`,
  `skills/external-skill-libraries/references/library-front-doors.md`,
  `skills/external-skill-libraries/references/collision-precheck.md` — the closed-catalog
  install boundary this artifact distinguishes itself from.
- `docs/adr/0001-mit-license-and-root-notice-attribution.md` — the no-vendoring/`NOTICE`
  boundary this artifact stays inside of.
- `docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md`,
  `docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md` — the
  closed-catalog rules this artifact stays inside of.
