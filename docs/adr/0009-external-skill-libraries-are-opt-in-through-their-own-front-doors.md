# ADR-0009 — An external skill library is installable on request through its OWN front door, opt-in and collision-checked; this bundle still never vendors a foreign byte

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and implementation)
- **Supersedes in part:** `docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md`
  — specifically its Decision item 1 (that no task, installer path, hook, or command in this
  bundle installs a third-party skill library) and Considered option 3 (which rejected exactly
  the mise task this record adds). Everything else in 0008 stands and is restated in Decision
  item 5 below.
- **Relates to:** `docs/adr/0002-mise-is-the-single-front-door.md`
  (Decision item 1 — the bootstrap-prerequisite count this record must not raise),
  `docs/adr/0001-mit-license-and-root-notice-attribution.md`
  (the `NOTICE` donor register that this record's no-vendoring property keeps out of scope),
  `skills/agentic-sdlc/references/skill-authoring.md`
  (the four-gate admission test applied to the new skill),
  `scripts/install_skill_bundle.py` (the ownership model the collision precheck extends),
  `skills/external-skill-libraries/` (the skill and its two references),
  `scripts/install_external_libraries.py`, `tests/test_external_libraries.py`

## Context

ADR-0008 recorded a blanket rule: no task, installer path, hook, or command in this bundle
fetches, renders, or installs a third-party skill library. That rule was correct about the
shipped state and correct about three real costs. **The operator has since decided they want
these libraries installable in an automated way** — ideally alongside install, at minimum as an
opt-in operation they can invoke. That is a decision, not a discovery, and it obsoletes the
part of 0008 that forbade the mechanism rather than the harm.

**The distinction 0008 did not draw is between vendoring and invoking.** 0008 evaluated its
options as vendoring shapes — copy the subset, copy under a prefix, or adapt the ideas — and
treated its option 3 (a task that installs a library) as belonging to the same family. It does
not. Copying bytes into `skills/` puts foreign content in this repository's tree, which is what
triggers the `NOTICE` donor obligation under ADR-0001, drags a licence into our distribution,
and puts foreign entries on our own selection surface as things we ship. **Running a third
party's own installer copies nothing here.** The bytes land in the operator's home, written by
the library's own code, under the library's own name and licence, exactly as they would if the
operator typed the command. No donor obligation attaches, because we are not a donee.

That collapses 0008's second reason to nothing for this shape. Reason 2 was ADR-0002: every
front door "would add a second bootstrap prerequisite or break lock doctrine." That is true of a
*pinned* front door — a tool in `[tools]` that `mise install` must resolve before the gate can
run. It is false of a front door invoked by an explicit, separate task that no gate leaf
depends on. Verified rather than assumed: `mise run check` passes with these tasks present, and
its dependency closure (`validate`, `test`, `self-test`, `secrets`) reaches none of them. The
`mermaid:provision` task is the standing precedent for exactly this shape — a task that
provisions something heavyweight, is never a gate dependency, and therefore never became a
prerequisite. Two of the three front doors need a tool already present (`claude`, `npx`) and
the third uses `uv`, which is already pinned; nothing new is added to `[tools]` and nothing is
installed to make an install possible.

0008's other two reasons survive intact and are what this record's mechanism is built around.
**Selection-surface pressure is real and unbounded** — it is the cost that appears in no diff,
and the reason installation must be a deliberate choice rather than a side effect of
`contributor:setup` or its deprecated `setup` forwarder.
**Name collision is mechanical and silent** — first writer holds a name, and the loser's entry
is simply not the one that loads, with no error at all.

The three libraries, with the facts re-verified for this record:

- **mattpocock/skills** — MIT, Matt Pocock. The front door is `claude plugins install
  mattpocock-skills`; it is already in Claude Code's official marketplace, so there is no
  `marketplace add` step. Version 1.2.3. **Its surface is 25 skills, not 5** — the earlier count
  read the five *category* directories (`engineering`, `productivity`, `misc`, `in-progress`,
  `deprecated`) as skills. The authority is `.claude-plugin/plugin.json`'s `skills` array. It is
  still the cheapest of the three by an order of magnitude. Plugin-namespaced, so it cannot lose
  a name; its hazard is duplication, which upstream states itself: "Pick one — installing both
  leaves you with every skill twice." On this machine **21 of its 25 names are already occupied**
  through a different channel — an `npx skills`-managed tree at `~/.agents/skills` symlinked into
  `~/.claude/skills`.
- **ECC** — `affaan-m/ECC`, MIT. **284 skills** (`gh api .../contents/skills --paginate` returns
  284), plus a self-reported 67 agents and 94 command shims. Its manual install writes each
  skill flat to `~/.claude/skills/<skill-name>/`, the same namespace this bundle's 9 entries
  occupy. Its documented guided front door is `npx ecc-universal setup`, and it carries an
  unresolved **version contradiction**: ECC's own README requires `ecc-universal` 2.2.0 or newer
  for the guided commands, while npm's `latest` dist-tag serves 2.1.0. The documented front door
  is newer than the published artifact.
- **hyperresearch** — PyPI 0.10.0, MIT, Jordan Gibbs, `requires-python >=3.11,<3.14`. **Not a
  skill library**: a CLI that *renders* 17 skills and 14 agents into a home or project via its
  own `install` verb (`--global` for the home). Every rendered name is `hyperresearch`-prefixed.
  Its rendered agent files carry static `model:` frontmatter, which
  `scripts/validate_bundle.py` rejects for agent files — decisive against vendoring its output,
  irrelevant to running its renderer in a home, where this repository's validator has no
  jurisdiction. It has no `uninstall` verb (verified: the CLI errors "No such command
  'uninstall'").

## Considered options

1. **Install a library automatically as part of `bundle:install` / `contributor:setup` (or
   its deprecated `setup` forwarder; what the operator asked for as the ideal).** Rejected, and this is the one place this record declines the
   stated preference. Silently adding 284 entries to an always-loaded selection surface as a
   side effect of installing this bundle is the exact failure the whole record exists to
   prevent, and it would make ADR-0002's prerequisite question live again by putting a network
   call in the install path. The opt-in form the operator named as their minimum is delivered
   instead, and it is delivered as a first-class skill and three tasks rather than as a
   grudging fallback.
2. **Opt-in, explicit, per-library installation through each library's own front door, dry-run
   by default, collision-checked (chosen).** Costs an operator gesture per library and a
   maintained table of front-door facts that go stale when upstream changes. Buys automation
   without vendoring, without a prerequisite, and without a silent surface change.
3. **Keep 0008's blanket prohibition.** Rejected: it is now contrary to an explicit operator
   decision, and its second supporting reason does not hold for an invoked front door.
4. **Vendor the wanted subset, with a prefix and `NOTICE` entries.** Rejected again, for
   0008's reasons, which this record does not disturb. It is also strictly worse than option 2
   at the thing the operator actually wants: vendored bytes go stale immediately and carry an
   update burden forever, while a front door delegates updates to the library's own channel.
5. **Pin each library as a `mise` tool so the front door is lock-resolved.** Rejected under
   ADR-0002 Decision item 2, and this is where 0008's reason 2 still bites: the `npm:` backend
   contributes no lockfile checksum, and pinning would put these libraries in the bootstrap
   path — making them prerequisites, which item 1 forbids. Leaving them unpinned and explicit is
   what keeps them out of it.

## Decision

1. **A named external skill library is installable on request, through that library's own
   front door.** `scripts/install_external_libraries.py` provides `list`, `install`, `status`,
   and `uninstall`, wired as `libraries:list`, `libraries:install`, and `libraries:status`.
   `install` and `uninstall` accept **explicitly named libraries only**; there is deliberately
   no verb that installs everything, and a bare `install` is a refusal, not a default.

2. **No gate, install task, or hook reaches any of these verbs, and that is asserted
   mechanically rather than promised in prose.** `tests/test_external_libraries.py` walks the
   `mise.toml` dependency closure of `contributor:setup`, its deprecated `setup`
   forwarder, `check`, `bundle:install`, `test`, and `self-test` and fails if any of them
   reaches a `libraries:*` task, and it fails if any other
   shipped script imports the module. This is the check ADR-0008's own Consequences section
   noted was missing for its Decision item 1 ("no mechanical check enforces Decision item 1"),
   now supplied for the inverted rule.

3. **Dry run is the default; `--yes` is the only thing that runs a command.** The dry run
   prints the exact command, its working directory, the resolved version, the destination, the
   number of skills added, the collision report, and the uninstall path. An installer that
   silently adds 284 entries to someone's always-on surface is the failure mode being designed
   against, so the default had to be the safe one rather than a flag away from it.

4. **A collision precheck runs before any front door, and refuses per library rather than per
   run.** The rules, in order: a name colliding with one this bundle installs refuses; a
   flat-channel name occupied by another writer refuses; a name occupied under the library's
   own prefix is a reinstall and proceeds; a plugin-channel name already served by another
   channel refuses as duplication, overridable with `--allow-duplicate-channel`; an
   unenumerable surface refuses, because a precheck that cannot run is not a precheck that
   passed; a missing front-door tool refuses by name. A **symlink occupies a name** — an entry
   another installer linked into place holds it as firmly as a directory, and reading a link as
   absent is precisely the silent loss being prevented. The precedent is
   `scripts/install_skill_bundle.py`, which classifies a non-owned entry at a managed path as
   `foreign` and preserves it; the precheck covers the direction that classifier structurally
   cannot see, where a foreign entry took the name first.

5. **This bundle still never vendors a foreign byte, and 0008 continues to govern that.**
   Restated so nothing here reads as a relaxation: no file from any library is copied into this
   repository under any name at any time; a foreign **idea** still enters only as an adapted
   `references/*.md` with a `NOTICE` donor entry in the same change, and a near-verbatim copy is
   still not an adaptation; a genuinely new capability still lands under a project-scoped name,
   never an upstream author's bare name; and **no second bootstrap prerequisite is added** —
   ADR-0002 Decision item 1 is untouched. 0008's reasons 1 (selection surface) and 3 (name
   collision) are not overturned; they are the requirements this record's mechanism implements.

6. **ECC is gated behind an explicit acknowledgment of its selection-surface cost, and is
   additionally blocked today on evidence.** Proceeding requires both
   `--acknowledge-ecc-surface` and `--names-from <file>` carrying the names from its own
   enumeration. Two independent facts block it regardless of that acknowledgment: its
   documented front door requires a version npm does not publish (2.2.0 against 2.1.0), and its
   284 names cannot be enumerated offline, so the precheck cannot run. Either alone is
   sufficient to refuse. Both are upstream facts that can change without any change here.

7. **What this deliberately does not do, stated in the module's own docstring so it travels
   with the code.** No credential is read, written, stored, forwarded, or accepted as an
   argument. No network trust claim is made: the tool makes no request of its own, and the
   front-door subprocess operates under its own package manager's integrity model — no tarball,
   signature, or transitive dependency is verified here. No foreign file is owned: `uninstall`
   runs the library's own removal path or refuses, and never deletes a path it did not see that
   library's installer create. **Installing is not endorsing** — a listed library is reachable,
   not recommended.

8. **Failures fail closed with a named reason and nothing retries.** A missing front-door tool,
   a refused precheck, an unexpected version, and a network failure each stop that library by
   name. Nothing retries, because a network failure and a refused install exit
   indistinguishably and mean different things.

9. **A new top-level skill is admitted: `skills/external-skill-libraries/`.** It clears the
   four-gate test on its own merits and names its neighbor in its description — the
   `agentic-sdlc` skill's `skill-authoring` reference owns whether a skill should exist in this
   bundle and how a foreign idea is adapted into it; this skill owns installing foreign
   libraries wholesale into a home and admits nothing to this repository. Under the
   ≥2-of-5 promotion test it clears four: it recurs across sessions and repositories; it has a
   stable input/output contract (named library in, plan or refusal out); its failures repeat
   precisely because the collision rule is the thing that gets skipped; and it benefits from an
   explicit handoff, since "install this library for me" is a request an agent must be able to
   select on directly.

10. **A successful install is evidence, not authorization.** It authorizes no push, no
    publication, no merge, no deployment, no credential use, and no further install.

## Consequences

- Positive: the operator gets the automation they asked for **without** the cost that made
  0008 refuse it. Nothing is vendored, so no `NOTICE` obligation attaches and no upstream
  licence text travels; no `[tools]` entry is added, so no bootstrap prerequisite appears.
- Positive: **the collision hazard is now checked rather than described.** 0008 recorded name
  collision as a reason to refuse; this record turns it into a precheck that runs before any
  installer does, in the one direction where the failure is otherwise invisible.
- Positive: **0008's missing mechanical check now exists in inverted form.** Its Consequences
  section flagged that a future contributor could add a fetching task and no gate would object.
  A test now asserts that no gate or install task reaches these verbs, so the boundary that
  actually matters — not *whether* installation exists, but whether it is *automatic* — is
  enforced by the suite rather than by review.
- Positive: writing the precheck surfaced two facts that no memo had: mattpocock's surface is
  **25 skills, not 5** (the earlier count read category directories as skills), and 21 of those
  names are already occupied on this machine by a different channel. Both are load-bearing and
  both were wrong in the brief this work started from.
- Positive: implementing the documented invocation caught a real defect in it. The first
  parser accepted shared flags only *before* the verb, so `install mattpocock --yes` — the form
  the skill documents — was an "unrecognized arguments" error, and `--yes install mattpocock`
  would have silently reverted to a dry run. Both orders now work and both are tested.
- Negative: **a maintained table of front-door facts goes stale by design.** Every version,
  count, flag, and destination recorded here and in the skill's references is a snapshot of
  someone else's repository. When upstream changes, this bundle is wrong until someone
  re-reads. The mitigation is that each row cites the exact doc line it came from, and each
  library's enumeration command is printed by `list` rather than assumed.
- Negative: **the selection-surface cost is real, unbounded, and uncheckable.** No mechanism
  here can tell whether an entry's share of always-on attention tracks its share of the
  sessions it fires in. The acknowledgment flag makes the cost explicit; it does not make it
  smaller.
- Negative: this record adds a tenth skill to this bundle's own selection surface, which is a
  cost it charges itself under its own Gate 2. Accepted on the four-gate argument in Decision
  item 9, and reversible under Section 5 of the authoring reference (retire by redirect) if the
  firing rate does not materialize.
- Negative: **the two useful libraries are both refused on this machine today** — mattpocock as
  a duplicate channel, ECC on version and enumerability. That is the precheck working rather
  than failing, but it means the automation's immediate practical value here is the diagnosis,
  not an install.
- Negative: no provenance is verified for anything. Detection reads the filesystem and reports
  presence; attribution by name prefix is an inference from a naming scheme, never a claim about
  who wrote the bytes on disk.
- Negative: ECC has no wired uninstall, because its own removal path is repo-local and needs a
  clone. An operator who installs it through this tool cannot remove it through this tool.
- **Confirmation:** `uv run --python 3.12.11 --script scripts/validate_bundle.py` reports 0
  errors and 0 warnings; `python3 -m py_compile scripts/install_external_libraries.py` succeeds;
  34 tests in `tests/test_external_libraries.py` pass, none of which touches the network (the
  precheck is driven against fixture homes, and the missing-tool path runs with an emptied
  `PATH`); `libraries:list` and a dry-run `libraries:install mattpocock` were both executed for
  real against the operator's live home, and the precheck correctly detected all 21 occupied
  names in the `~/.agents/skills` tree, reporting each as a symlink with its target. **No
  library was installed and no front door was invoked.** A passing gate is evidence of
  conformance only and authorizes nothing.

## Amendment — 2026-08-07: two operator decisions, and one upstream fact that outranked both

- **Status:** accepted, same day as the original record.
- **Deciders:** operator (both decisions), agent (evidence and implementation).
- **What changed:** Decision item 1 gains a verb, Decision item 4 gains a migration rule, and
  Decision item 6 is substantially rewritten. Everything else stands, in particular items 2, 3,
  5, 7, 8, and 10 — no gate reaches the new verb, dry run remains the default, nothing is
  vendored, no credential is handled, no bootstrap prerequisite is added, and an install still
  authorizes nothing.

**Operator decision 1: same-upstream de-duplication is allowed, through the other channel's own
removal path.** The original record's duplicate-channel rule refused and stopped there, offering
only `--allow-duplicate-channel`. Against the live home that made mattpocock a dead end: 21 of
its 25 names were already held by `npx skills`, so the only routes were "accept duplication" or
"do it by hand". The operator directed that the occupants be **removed first, then installed
through this bundle**, so the tool must offer that migration rather than only refusing.

`libraries:migrate` implements it, and the safety of the whole thing rests on one distinction:
**presence is not provenance.** A directory listing proves a name is taken and says nothing about
who took it. So the migration's licence to remove comes from the *competing channel's own lock
file* (`$XDG_STATE_HOME/skills/.skill-lock.json`, else `~/.agents/.skill-lock.json`), matching each
occupied name's recorded `source` **and** `sourceUrl` against the library's upstream. Consequences,
stated as refusals because that is what they are:

- A name whose lock entry names a **different** `source` is not touched. Neither is one whose
  `source` matches but whose clone URL does not — a label is not an identity.
- A name **absent** from the lock is not touched. Occupied but unattributable.
- **No lock file, an unreadable one, or one at a schema version the channel's own reader
  discards** refuses the migration outright. An unavailable proof is not a passed one.
- A **single** unproven name refuses the whole migration rather than half-completing it.
- Removal runs the other channel's own verb,
  `npx -y skills@latest remove --global --agent claude-code --yes <names…>`. **This tool contains
  no deletion primitive** — no `rm`, no `unlink`, no path touched directly — and a test asserts
  their absence, because that absence is the argument.
- `--agent claude-code` is load-bearing, not cosmetic. Verified against the CLI's source and in
  fixture homes: a bare `remove --global` targets **every** agent in its registry, deleting the
  canonical `~/.agents/skills/<name>`, every other agent's link, and the lock entry. On a home
  whose lock lists 16 agents that is a capability loss for 15 hosts that were not the problem.
  Scoped to one agent it removes only `~/.claude/skills/<name>` and the rest survives, so the
  change is narrow and re-linkable.
- **Ordering is enforced:** remove, then re-run the precheck against the real filesystem, then
  install. A removal that fails stops the migration. So does a removal that exits **zero while
  names remain occupied** — the partial-removal case, which is more dangerous than an outright
  failure precisely because it looks like success. Installing over a still-occupied name is the
  silent loss the precheck exists to prevent.
- If removal succeeds and the *install* then fails, that is reported plainly: the home has
  neither channel, and the install must be re-run once the named cause is fixed.

**Operator decision 2: ECC's npm `latest` is accepted, and the version gap survives as a
recorded caveat.** The original Decision item 6 refused ECC on two independent facts. The version
fact — README requires 2.2.0+, npm `latest` serves 2.1.0 — is **overruled**: `latest` is accepted.
It is not silently dropped. It is recorded as a `caveat:` line that prints in `list` and on every
dry run, and the install treats a nonzero front-door exit as a **failed install** rather than
inferring success from having run a command. The surface fact stands: `--acknowledge-ecc-surface`
is still required, because it is about cost and the operator did not overrule it.

**The upstream fact that outranked both decisions.** Re-verifying the front door before relying
on it showed that ECC's documented entrypoint **does not exist in the published artifact at
all**. `npx ecc-universal setup` fails with npm's "could not determine executable to run", and
would keep failing at any version: the 2.1.0 tarball declares bins `ecc`, `ecc-control-pane`,
`ecc-install`, `ecc-memory-mcp`, `ecc-plan-canvas` — no `ecc-universal` bin — and `ecc`'s own
command table has no `setup` verb. Accepting `latest` on the recorded front door would therefore
have shipped a guaranteed failure with an accepted-caveat label on it. The wired front door is the
artifact's real one, `npx -y -p ecc-universal ecc install --target claude --profile full`, taken
from `ecc --help` and `ecc install --help`; a profile is mandatory because the CLI refuses without
one. **A README is a claim and the published artifact is the fact**, and where they disagree the
artifact wins — that is the durable rule this episode establishes, beyond ECC.

Two further corrections fell out of the same verification, both making the record more accurate
rather than more permissive:

- **ECC does have a wired uninstall.** The original record said its removal path was repo-local
  and needed a clone. That describes the repository's `scripts/uninstall.js`; the published
  artifact exposes `ecc uninstall --target claude`, scoped to its own recorded install-state and
  supporting `--dry-run`. It is now wired.
- **The surface is enumerable after all, by the library's own dry run.** `ecc install --dry-run
  --json` emits every destination path it would write. Against the resolved `full` profile that is
  983 operations: 280 distinct flat skill names, 67 agents, 94 commands, 122 rules files, 170
  scripts. Upstream's self-reported 67 and 94 match exactly; its 284 skills measure 280 for this
  profile. `--names-from` therefore now has a real source rather than a hand-maintained guess.

**The skipped-precheck decision, and why it is not a loophole.** ECC's surface still cannot be
enumerated without running its front door, so requiring `--names-from` unconditionally would keep
ECC unreachable and defeat the goal. The honest resolution: where the surface cost is
acknowledged, the install proceeds with the check reported as **`precheck: SKIPPED, not passed`**,
in those words, on the plan and again after the front door completes. The rule "a precheck that
cannot run is not a precheck that passed" is unchanged — what changed is that the skip is now
*labelled* rather than converted into a refusal. `--names-from` remains available and turns the
skip into a real comparison; run against the real 280 names it found exactly one genuine
collision (`benchmark`, an unrelated local skill with no lock entry — unattributable, so not
migratable, and correctly refused).

**Decision item 6, as amended.** ECC is gated behind `--acknowledge-ecc-surface` alone. Its
version gap and its skipped precheck are recorded, printed caveats rather than blocks. Its front
door is the published artifact's, not the README's. The `blocked` mechanism from the original
item 6 is retained in the code but set by no library row — it means "cannot be honestly run" as
distinct from "expensive", and a test keeps the two from collapsing into each other.

**Net effect on reachability.** All three libraries are reachable, and `list` prints the exact
command for each: mattpocock as *installable after migration*, ecc as *installable behind
--acknowledge-ecc-surface*, hyperresearch as *installable*. No library reports as blocked, and a
test asserts that. Nothing is auto-invoked: the dependency-closure test still walks
`contributor:setup`, its deprecated `setup` forwarder, `check`, `bundle:install`, `test`, and
`self-test` and fails if any reaches a `libraries:*` task.

**Amendment item: a dry run's exit code describes, it does not attempt.** A container replay from
the public remote found that `mise run check` was RED on a fresh machine while green on the
developer host. Decision item 8 ("failures fail closed with a named reason") had been implemented
as *every* refusal failing the process, which conflated two different operations. The split now
recorded:

- **0** — the operation did what it was asked. For a dry run that includes describing a refusal:
  occupied names, or a front-door tool that is absent so a real install would refuse. The
  description is the deliverable and it succeeded; the reason is printed in full.
- **1** — a real (`--yes`) operation was asked to change something and could not.
- **2** — the invocation itself was unusable (no library named, unknown library, unreadable name
  list). Unchanged.

Decision item 8's fail-closed property is **not** weakened: a real install, migration, or
uninstall with a missing front-door tool or a refused precheck still exits nonzero, and paired
tests assert both halves so the change cannot decay into blanket leniency. A further test asserts
the property the exit code stands for — that no front door is ever invoked during a dry run at
all.

The root cause is worth recording because it generalises: `shutil.which` is the only input to
these rules that varies by **host** rather than by evidence, so any test that reads the ambient
PATH silently tests the developer's machine. Nine of this module's own tests were host-dependent
in exactly that way. Two specific traps: stripping PATH to the interpreter's directory does not
work, because a tool installed beside the interpreter (`~/.local/bin/claude` next to
`~/.local/bin/uv`) walks straight back in — the missing-tool branch then never executes and the
check reports a pass it never performed; and asserting an exit **code** where the behaviour of
interest is a **message** hides semantic changes. Tool presence is now stubbed rather than
inferred from the environment, verified green under both a genuinely clean PATH and the developer
host, and confirmed to fail when the old conflated behaviour is reintroduced.

## Amendment — 2026-08-10: the supported catalog is closed

The reachable catalog is exactly `mattpocock/skills`, ECC (`affaan-m/ECC`), and hyperresearch.
This list is exhaustive, not illustrative. An unlisted library—including gstack—is outside every
`libraries:list`, `libraries:status`, `libraries:install`, `libraries:migrate`, and
`libraries:uninstall` ownership or support claim. Operators remain free to install one through its
own independent path, but this bundle treats the resulting files as foreign state: it does not
adopt them, inspect them to infer ownership, migrate them, or remove them. This exclusion is not a
finding that gstack or another unlisted library is unsafe; it means the project has not verified
and onboarded it.

Adding a fourth row is a new onboarding decision, not routine table maintenance. The same change
must establish and coordinate evidence for the upstream licence, published-artifact front door,
selection-surface cost, name-collision and ownership behavior, credential behavior, removal
semantics, user/agent documentation, and executable tests. `SUPPORTED_LIBRARIES` in
`scripts/install_external_libraries.py` is the code-level closed set, and the tests pin each row's
key and exact upstream origin so neither a fourth library nor a substituted repository can enter
silently.

The repository-local `.gstack/` ignore accommodation is removed with this amendment. Existing
repo-local or global gstack files remain independently owned foreign state and are deliberately
not read, deleted, migrated, staged, or otherwise mutated by this change.

## Reversal condition

Reopened by an observable change in either direction.

**Toward stricter.** If any library named here changes licence away from MIT, or if a
supply-chain incident is observed in one of their distribution channels, that library's row is
removed and this record re-examined — including whether the remaining rows' front doors share
the compromised channel. If a front door begins requiring a credential in the environment, it
is removed rather than accommodated: Decision item 7's no-credential property is not
negotiable against convenience.

**Toward looser on ECC specifically.** Superseded by the 2026-08-07 amendment: there is no
version block left to clear, because the operator accepted npm `latest`. If npm publishes
`ecc-universal` 2.2.0 or newer, re-verify whether a `setup` bin appears in the *artifact* — and if
it does, decide deliberately whether to switch the wired front door to it, rather than assuming
the README's command became correct. The surface acknowledgment does not clear: it is about
proportionality, not about the version. What would relax it is measurement — a per-entry firing
rate showing the 284 rows earn their share of a selector's attention.

**Toward stricter on the migration path.** If the `skills` CLI changes its removal semantics — if
`--agent` stops scoping, if the lock schema changes shape, or if `remove` begins expanding a name
list — the migration's safety argument is invalidated and must be re-derived against the new
behaviour rather than carried forward. The specific properties depended on, each verified against
its source and in fixture homes: `--agent claude-code` leaves the canonical copy, other agents'
links, and the lock entry intact; a lock below schema version 3 is discarded by its own reader;
and names are matched through `sanitizeName` and dropped when unmatched rather than expanded.

**Toward automatic installation.** If a future operator decision asks for a library to be
installed by `bundle:install`, `contributor:setup`, or its deprecated `setup` forwarder, that
reopens Decision item 2 in a new record rather
than being implemented as a task edit — and it must answer the ADR-0002 prerequisite question
for a network call in the install path, which this record avoids rather than solves.

**On the collision model.** If `scripts/install_skill_bundle.py` ever begins replacing rather
than preserving a foreign entry at a managed path, that is a defect in the installer and it
invalidates the precedent Decision item 4 builds on; the precheck's premises must be re-derived
rather than assumed to still hold. Conversely, if skill discovery ever stops being a flat
per-home namespace — if names become scoped by origin — then rules 1, 2, and 3 of the precheck
lose their basis and must be recomputed against the new mechanics, not carried forward by
inertia.

**On the skill's admission.** If `external-skill-libraries` does not actually fire across
sessions, its Gate 2 argument fails retroactively and it should be folded into
`skills/agentic-sdlc/references/` as a reference, following the retire-by-redirect rule rather
than being deleted.

This record is evidence for a conductor to cite; it authorizes no library install, vendoring
pass, dependency addition, credential use, push, publication, merge, deployment, or other
outward effect on its own.
