# `npx skills` lifecycle research for harness installation design

- **Question.** What lifecycle does the current first-party CLI invoked as `npx skills`
  actually implement, and which parts should a Claude-Code-first Agentic SDLC harness adapt or
  reject?
- **Decision gated.** Whether the Wayfinder harness should model installation, update, removal,
  host projection, locking, and recovery on this CLI, delegate any of those operations to it, or
  retain Agentic SDLC's receipt-backed, explicit-approval, own-front-door contract.
- **Artifact scope.** Primary-source review on 2026-08-14. No package was executed and no product
  code, tickets, map, or host configuration was changed. Registry metadata and the published
  tarball were inspected; upstream source was read at the package's exact `gitHead`.

## Recommendation

**Adapt the discovery model and the canonical-store/host-projection shape; reject the mutation,
ownership, update, and consent semantics. Confidence: high.**

The name resolves today to the npm package **`skills@1.5.22`**, whose `skills` and `add-skill`
bins both enter `bin/cli.mjs`; npm metadata points to **`vercel-labs/skills`**, records
`gitHead` **`a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5`**, and publishes matching registry integrity,
signatures, and a provenance attestation. The same commit is first-party tag/release `v1.5.22`.
([verified: npm package metadata](https://registry.npmjs.org/skills/1.5.22),
[verified: exact package source](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/package.json#L1-L15),
[verified: first-party release](https://github.com/vercel-labs/skills/releases/tag/v1.5.22))

That identity does **not** make bare `npx skills` hermetic. npm documents that an unversioned
package name can match a local project dependency, otherwise it may be fetched into npm's cache;
install confirmation is assumed in non-TTY/CI contexts. `npx skills@latest` avoids a local
unversioned match but selects a mutable dist-tag; `npx skills@1.5.22` names this reviewed release
but still does not create an Agentic SDLC receipt. ([documented: npm exec/npx resolution,
prompting, and cache behavior](https://docs.npmjs.com/cli/v11/commands/npm-exec/))

For Agentic SDLC, treat this CLI as:

1. **A useful reference implementation** for source discovery, a declarative host registry,
   explicit skill/host/scope selectors, and a canonical copy projected to multiple agents.
2. **A permissible foreign front door only for an exact, operator-authorized, preflighted action**
   where Agentic SDLC has independently proved the competing channel's source identity. Do not
   infer ownership from the CLI's lock or from path presence alone.
3. **Not a lifecycle substrate** for harness-owned entries. Bare invocation, automatic agent
   consent, overwrite/remove-by-name, mutable restore/update, default telemetry, and non-atomic
   recovery all conflict with this repository's contract.

## Verified lifecycle

### 1. Discovery and source resolution

The CLI exposes two distinct discovery planes:

- `skills find [query]` searches the first-party `https://skills.sh/api/search` service and can
  filter by GitHub owner. A noninteractive query prints results; interactive use supplies an
  fzf-like selector. ([verified: search endpoint and result handling](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/find.ts#L16-L18),
  [verified: query request](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/find.ts#L86-L115))
- `skills add <source> --list` resolves and fetches one source, discovers its valid skills, then
  exits without installing. Sources include GitHub shorthand and URLs, GitLab, generic Git/SSH,
  local paths, HTTP(S) well-known indexes, direct `SKILL.md` URLs, and archives. A source may carry
  a subpath, a skill selector, and an optional ref. ([documented: formats and list mode](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L28-L93),
  [verified: parser types](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/types.ts#L103-L110),
  [verified: parser dispatch](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/source-parser.ts#L272-L480))

Repository discovery is convention-based: root `SKILL.md`, known agent skill containers, and
Claude plugin manifests are searched. Known containers are walked to a bounded depth of three;
`--full-depth` broadens the search, and a recursive fallback is used when standard locations find
nothing. ([documented: discovery rules](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L377-L470))

**Harness disposition:** adapt the staged resolver and bounded-by-default discovery. Keep source
type, normalized URL, requested ref, resolved commit/content digest, and selected skill paths as
separate receipt fields. Do not adopt aliases or fallback-to-generic-Git without displaying the
fully resolved source before approval.

### 2. Source, skill, target, scope, and mode selection

Interactive add chooses skills, target agents, project versus global scope, symlink versus copy,
then displays an installation summary and asks once for confirmation. Noninteractive add supports
explicit `--skill`, `--agent`, `--global`, `--copy`, and `--yes`; `--all` expands to every skill,
every registered agent, and `--yes`. If no skills are selected explicitly, `--yes` selects every
discovered skill. If no agent is detected, `--yes` targets every registered agent.
([documented: add options and examples](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L50-L109),
[verified: `--all` and automatic agent mode](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1066-L1084),
[verified: selection defaults](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1292-L1321),
[verified: no-agent `--yes` expansion](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1433-L1463))

The most important consent behavior is not in the README: when the CLI detects that it is running
inside an AI agent, it sets `options.yes = true` and auto-selects that agent plus universal agents.
Removal does the same. This converts contextual detection into mutation authorization.
([verified: add behavior](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1073-L1084),
[verified: remove behavior](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/remove.ts#L61-L71))

**Harness disposition:** adapt explicit selectors and the human-readable summary, but require a
reviewable plan digest and operation-specific approval. Agent detection may suggest a target; it
must never imply `--yes`. Reject `--all` as a harness API because the host registry and source
surface both grow over time.

### 3. Supported coding-agent hosts and projection model

Release 1.5.22 has **76 agent IDs** in its closed TypeScript registry, including Claude Code,
Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Pi, and Universal. Each record owns a display
name, project skills path, optional global path, and detector. The README renders the same mapping;
for example, Claude uses `.claude/skills` / `~/.claude/skills`, while Codex uses project
`.agents/skills` / global `~/.codex/skills`. ([verified: exact 76-ID type union](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/types.ts#L1-L77),
[documented: host/path table](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L243-L318),
[verified: Claude and Codex path resolution](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/agents.ts#L143-L151))

In symlink mode, the CLI copies each skill into a canonical `.agents/skills/<name>` directory and
projects it into agent-native locations. Copy mode instead writes independent trees. Failed
symlinks silently fall back to copies and are reported afterward. ([verified: canonical target and
installation modes](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L265-L360),
[verified: symlink-to-copy fallback](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L391-L404))

**Harness disposition:** adapt the data-driven host registry and canonical-store/projection split.
Record the exact selected hosts and actual projection mode per entry. Do not allow a fallback from
link to copy to change the ownership/durability model without being part of the approved plan and
receipt.

### 4. Install, list, remove, update, and the two lock files

The public command set is `add`, `use`, `list`, `find`, `remove`, `update`, and `init`, plus
experimental restore/sync commands. `list` inventories disk state across agent paths and can emit
JSON. ([documented: command set](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L111-L228),
[verified: experimental commands](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/cli.ts#L105-L169))

There are two tracking documents:

- Global schema v3 is `$XDG_STATE_HOME/skills/.skill-lock.json`, falling back to
  `~/.agents/.skill-lock.json`. Per skill it stores source/type/URL, optional ref/path, a folder
  hash, timestamps, and optional plugin/well-known metadata. ([verified: schema and path](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/skill-lock.ts#L8-L75))
- Project schema v1 is checked-in `skills-lock.json`; entries store source/type, optional ref/path,
  a computed SHA-256 content hash, and limited target metadata. Keys are sorted on write to reduce
  merge conflicts. ([verified: project schema](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/local-lock.ts#L5-L60),
  [verified: deterministic write](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/local-lock.ts#L102-L123))

These are update manifests, not reproducible locks. Refs are optional; bare installs track the
source's moving default. `experimental_install` re-fetches each recorded source through `runAdd`
but does not compare fetched content with the recorded `computedHash`. Update compares the saved
folder hash/digest to current upstream, then invokes `add ... -y` to overwrite changed skills.
([verified: restore re-fetch](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/install.ts#L18-L81),
[verified: global change detection and re-add](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L546-L590),
[verified: noninteractive update mutation](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L667-L713))

Update does not record or replay the original host set or copy/symlink mode: those fields are absent
from both lock schemas, and update re-enters `add` without either selector. It can therefore change
where and how a skill is projected based on the environment at update time. ([verified: lock field
sets](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/skill-lock.ts#L15-L40),
[inferred from update argv](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L690-L704))

**Harness disposition:** adapt deterministic, human-readable project intent and per-entry source
metadata. Replace both lock semantics with exact resolved identity, bytes/tree digests, selected
hosts/mode, expected prestate, and a receipt that restore verifies before any movement. Update must
be plan-only until separately approved; update detection is evidence, not authority.

### 5. Ownership and collisions

This is the strongest rejection. Add checks only whether a destination exists, prints
`overwrites:`, and then recursively removes and recreates the directory. It does not compare the
occupant with the lock source, content hash, symlink identity, or installer channel. In symlink
mode it also removes an existing agent path whose target differs. ([verified: presence-only check](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L532-L562),
[verified: overwrite summary](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1603-L1666),
[verified: recursive replacement](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L155-L170),
[verified: existing target deletion](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L224-L258))

Remove scans canonical and every known agent directory by folder name, resolves requested names
against folders and lock keys, and deletes the selected paths. The default unscoped removal targets
all 76 registered agents. A lock entry is useful metadata but is not required to authorize deletion;
an untracked directory with the requested name is eligible. ([verified: disk and lock scan](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/remove.ts#L78-L128),
[verified: all-agent default](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/remove.ts#L178-L185),
[verified: recursive deletion](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/remove.ts#L216-L300))

**Harness disposition:** reject completely. Presence is a collision, not ownership. Preserve any
foreign, modified, retargeted, unrecorded, or ambiguously attributed path. Removal must go through
the owning channel's exact verb only after the channel's own record and current path identity both
match the approved receipt.

### 6. Dry-run and noninteractive behavior

There is no `--dry-run` for add, remove, or update. `add --list` is a useful read-only source
enumeration, but it does not resolve the final target/mode/overwrite plan. `list --json` inventories
installed state. `-y` skips CLI prompts; outer `npx -y` separately skips npm's package-fetch prompt.
([verified: complete option surface](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/cli.ts#L105-L172),
[documented: npm's separate prompt](https://docs.npmjs.com/cli/v11/commands/npm-exec/))

Noninteractive update auto-selects project scope when it detects project skills, otherwise global.
Update immediately installs detected changes; only deletion of skills removed upstream is skipped
in noninteractive mode. That deletion restraint is worth adapting. ([verified: scope auto-detection](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L114-L165),
[verified: noninteractive deletion skip](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L256-L288))

**Harness disposition:** expose a real dry-run that resolves exact package/source identity,
destinations, occupancies, movements, and receipt delta without writing lock/history state. Require
the plan digest for execution. Keep noninteractive mode as a presentation mode, never an approval
mode.

### 7. Security and trust

The upstream has meaningful input hardening that should be adapted:

- skill names, subpaths, and output paths are constrained against traversal;
- terminal control sequences are removed from untrusted metadata;
- direct downloads have byte/file/extracted-size ceilings, archive paths are validated, zip CRCs
  are checked, and archive links are refused;
- Git `ext::` is refused, clone protocols are allowlisted, clone time is bounded, and update child
  processes receive argv directly with `shell: false`.

([verified: name/path safety](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L44-L78),
[verified: terminal sanitization](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/sanitize.ts#L1-L64),
[verified: download limits and traversal checks](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/download-source.ts#L10-L77),
[verified: Git controls](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/git.ts#L9-L16),
[verified: shell-free update](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L690-L704))

The trust boundary remains much weaker than Agentic SDLC's. Git cloning deliberately inherits the
caller's environment and permits ambient aliases, askpass, credential helpers, config paths,
hooks paths, filters, proxies, SSH commands, and other Git controls. Authentication failures may
fall back through `gh` and SSH, and update hash lookup may read `GITHUB_TOKEN`, `GH_TOKEN`, or invoke
`gh auth token`. ([verified: ambient Git allowances](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/git.ts#L104-L167),
[verified: auth fallbacks](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/git.ts#L235-L297),
[verified: token discovery](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/skill-lock.ts#L136-L179))

Security assessments are advisory and fail open: an unavailable audit is silently skipped, and a
high/critical result does not block `-y`. The final warning says installed skills run with full
agent permissions, but it appears after mutation. ([verified: advisory audit handling](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1695-L1724),
[verified: post-install warning](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L2026-L2038))

**Harness disposition:** adapt the parsers, bounds, sanitizers, no-shell subprocesses, and explicit
posture that skill content is executable authority. Reject ambient credential/config discovery,
fail-open audit as a trust decision, and any claim that HTTPS or registry integrity authenticates
the selected skill bytes without a reviewed immutable source receipt.

### 8. Telemetry

Telemetry is on by default unless `DISABLE_TELEMETRY` or `DO_NOT_TRACK` is set. Events are sent as
query parameters to `https://add-skill.vercel.sh/t` and can include CLI version, detected agent,
source, selected skill names, target agent IDs, global scope, repository-relative skill paths,
install URL, search query, success/failure counts, and caller-provided metadata.
([verified: event schema and endpoint](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/telemetry.ts#L1-L60),
[verified: enablement and transmission](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/telemetry.ts#L73-L89),
[verified: request construction](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/telemetry.ts#L138-L189))

There is a primary-source contradiction: the README says telemetry is automatically disabled in
CI, but the code's `isEnabled()` does not test CI; it adds `ci=1` to the event instead. Therefore
the documented CI claim is false for 1.5.22 unless an opt-out variable is also present.
([documented: README claim](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/README.md#L500-L517),
[verified: effective code](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/telemetry.ts#L73-L89))

More seriously, the separate security-audit request to `https://add-skill.vercel.sh/audit` is not
gated by telemetry opt-out or repository privacy. It sends the normalized repository and selected
skill slugs before the installation confirmation; private-GitHub filtering is applied later only
to the install telemetry event. ([verified: audit request](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/telemetry.ts#L94-L136),
[verified: pre-confirmation audit dispatch](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1371-L1379),
[verified: later privacy gate](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1810-L1829))

**Harness disposition:** reject default telemetry and all unapproved metadata egress. A read-only
plan must list every intended remote endpoint and data class. Security lookups are network actions,
not a consent exemption; private source identifiers must never be sent to a third party by default.

### 9. CLI self-update

The CLI has **no self-update mechanism**. `skills update` updates installed skills, not the npm
package, and the command dispatcher contains no version check or package-manager invocation for
self-upgrade. The effective CLI version is therefore selected by npm/npx resolution and cache
behavior. ([verified: command dispatcher](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/cli.ts#L301-L400),
[documented: npm cache controls](https://docs.npmjs.com/cli/v11/commands/npm-exec/#a-note-on-caching))

**Harness disposition:** do not add invisible self-update. Keep tool acquisition separate from
skill lifecycle; pin the exact CLI artifact, record registry integrity/source commit, and require a
new review and approval to change it.

### 10. Failure and recovery

Useful behaviors include bounded clone time, named authentication diagnostics, temp-directory
cleanup, per-item result reporting, shell-free update subprocesses, conservative skipping of
upstream deletion in noninteractive mode, and a nonzero update exit status when any update fails.
([verified: clone diagnostics and cleanup](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/git.ts#L235-L310),
[verified: update failure exit](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/update.ts#L986-L1005))

The mutation path is not transactional or crash-consistent:

- each destination is recursively removed before the replacement is copied;
- skills and targets are processed sequentially with no prestate snapshot or rollback;
- lock files are ordinary `writeFile` writes with no mutex, atomic replace, backup, or fsync;
- corrupt JSON and older schemas are silently treated as empty;
- lock-write failures are swallowed after installation;
- add and remove print per-item failures but do not set a failing process status for partial
  failures, while experimental restore catches source failures and continues.

([verified: destructive replace](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/installer.ts#L155-L170),
[verified: sequential mutation](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1726-L1777),
[verified: non-atomic lock write and empty-on-error](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/skill-lock.ts#L77-L120),
[verified: swallowed lock-write failure](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L1844-L1885),
[inferred: add returns after logging partial failures without setting failure status](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/add.ts#L2026-L2042),
[inferred: remove does the same](https://github.com/vercel-labs/skills/blob/a4d243c3d4f86cdf9385dd1b6a0733f6937e70b5/src/remove.ts#L319-L360))

**Harness disposition:** adapt granular diagnostics, but require exact prestate rechecks, durable
receipt publication, atomic no-replace transitions, explicit partial/unknown-effect states, and
rollback receipts. A lock update is part of success, not optional bookkeeping.

## Adapt / reject matrix

| Upstream pattern | Decision | Agentic SDLC form |
|---|---|---|
| Bounded standard-location discovery plus explicit full-depth escape hatch | **Adapt** | Keep bounded default; receipt every resolved source and selected path. |
| Declarative 76-host registry with project/global destinations | **Adapt narrowly** | Closed reviewed host set; operator selects exact hosts; unknown host stops. |
| Canonical `.agents/skills` store with host projections | **Adapt** | One owned canonical artifact; projection identity/mode recorded and rechecked. |
| `add --list`, `list --json`, explicit skill/agent selectors | **Adapt** | Compose into a true no-write plan with exact destinations and collisions. |
| Deterministic project manifest with content hashes | **Adapt and strengthen** | Intent plus immutable source/artifact digest, expected prestate, and receipt verification. |
| Path/archive/terminal sanitization and shell-free subprocesses | **Adapt** | Preserve limits and add closed environment/credential admission. |
| Noninteractive upstream-deletion skip and per-item update failure status | **Adapt** | Destructive drift never auto-removes; partial failure is explicit nonzero/unknown effect. |
| Bare `npx skills` / mutable `@latest` | **Reject** | Exact reviewed package/version/integrity/source receipt. |
| AI-agent detection implies `--yes` | **Reject** | Detection may prefill a plan only; approval remains operation-specific. |
| `--all` means all discovered skills and all current/future hosts | **Reject** | Closed explicit selections; no wildcard mutation authority. |
| Presence-based overwrite and remove-by-name | **Reject** | Foreign/unproven occupants are preserved; removal requires ownership proof. |
| Hash-as-update-signal and re-fetch-on-restore without hash admission | **Reject** | Restore exact bytes or refuse; update is a separate reviewed version transition. |
| Silent empty lock on corruption/version drift; lock write may fail open | **Reject** | Fail closed, preserve evidence, provide explicit migration/recovery. |
| Advisory audit failure and default metadata egress | **Reject** | No unapproved network/telemetry; trust checks and their inputs appear in the plan. |
| Ambient Git/`gh` credentials and configuration | **Reject** | Closed subprocess environment and separately authorized authentication. |
| In-place sequential delete/copy without rollback | **Reject** | Atomic staged movement, prestate validation, durable receipt, known recovery state. |

## Rejected alternatives

1. **Make `npx skills@latest add` the harness installer.** Rejected: mutable CLI identity,
   floating source defaults, default egress, no exact dry-run, and no ownership protection.
2. **Treat `skills-lock.json` as a reproducible dependency lock.** Rejected: hashes detect change
   but restore does not admit against them, refs are optional, targets/mode are incomplete, and
   invalid files silently become empty state.
3. **Trust its overwrite warning as collision handling.** Rejected: a warning followed by recursive
   deletion is not preservation, and `-y`/agent detection bypasses the confirmation.
4. **Use `skills update` as unattended maintenance.** Rejected: it fetches and overwrites content
   immediately and may change host/mode projections based on the current environment.
5. **Rely on the built-in security audit as approval.** Rejected: it is advisory, fail-open,
   independently sends metadata, and does not authenticate the fetched source or content.
6. **Implement a generic Agentic SDLC delete equivalent to `skills remove`.** Rejected: removal by
   flat name can erase foreign state. Continue using the owning front door only after independent
   source-and-path proof.

## Open risks

- **Upstream drift.** `latest`, the 76-host registry, destination paths, and schemas are dated facts.
  Re-resolve registry metadata and compare the exact source commit before implementation.
- **Package provenance consumption.** npm publishes integrity, signatures, and a provenance
  attestation for 1.5.22, but this review did not verify the attestation chain or npm's effective
  policy on this host. The harness must not claim provenance merely because metadata advertises it.
- **Same-UID races and durability.** The upstream has no concurrency or sudden-power-loss contract;
  filesystem behavior across Unix symlinks and Windows junction/copy fallback needs its own harness
  proof.
- **Private-source egress.** The audit request's lack of privacy/telemetry gating is source-verified
  and should be treated as a disclosure hazard, not merely a documentation defect.
- **Exact commit refs.** The parser stores refs, but clone uses shallow `--branch`; this review did
  not establish a portable raw-commit-SHA install interface across every source type. Do not claim
  arbitrary commit pin support without the experiment below.

## Cheapest decisive experiment before adapting executable behavior

No experiment is needed for the recommendation. If implementation wants to accept raw Git commit
SHAs as an immutable source selector, the cheapest decisive experiment is a disposable HOME and
temporary repository containing one skill: invoke the exact reviewed CLI package against GitHub,
GitLab, generic HTTPS Git, and SSH using a raw commit SHA; capture clone argv, resolved HEAD,
destinations, lock bytes, and exit status; then repeat restore offline. Accept a source form only if
it resolves the exact commit and the restore verifies the same bytes without default-branch access.

## Seed proposals (out of scope; not investigated)

- **Upstream telemetry/CI contradiction:** report that 1.5.22 sends telemetry in CI unless an
  opt-out environment variable is present, contrary to its README.
- **Private-source audit egress:** ask upstream to privacy-gate and telemetry-opt-out-gate the audit
  request before sending repository and skill identifiers.
- **Collision/ownership mode:** propose a `--fail-if-exists` / expected-source precondition and an
  ownership-scoped remove path instead of recursive presence-based replacement.
- **True `--dry-run --json`:** request a target-complete mutation plan including canonical paths,
  projections, overwrites, mode fallbacks, lock delta, and network endpoints.
- **Lock and recovery contract:** investigate atomic lock persistence, concurrent writers, partial
  failure exit codes, backup/rollback, and exact-hash restore as a separate upstream design effort.

## Evidence boundary

All external evidence is primary: the official npm registry record and tarball, the first-party
GitHub repository/tag/release at the package's exact `gitHead`, and official npm CLI documentation.
`verified` means observed in current package metadata or source; `documented` means the first-party
README/docs state it; `inferred` is a narrow consequence of verified control flow and is labelled.
The review stops here because additional sources would not change the recommendation.
