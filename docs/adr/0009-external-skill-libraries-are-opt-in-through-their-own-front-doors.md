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
and the reason installation must be a deliberate choice rather than a side effect of `setup`.
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

1. **Install a library automatically as part of `bundle:install` / `setup` (what the operator
   asked for as the ideal).** Rejected, and this is the one place this record declines the
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
   `mise.toml` dependency closure of `setup`, `check`, `bundle:install`, `test`, and
   `self-test` and fails if any of them reaches a `libraries:*` task, and it fails if any other
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

## Reversal condition

Reopened by an observable change in either direction.

**Toward stricter.** If any library named here changes licence away from MIT, or if a
supply-chain incident is observed in one of their distribution channels, that library's row is
removed and this record re-examined — including whether the remaining rows' front doors share
the compromised channel. If a front door begins requiring a credential in the environment, it
is removed rather than accommodated: Decision item 7's no-credential property is not
negotiable against convenience.

**Toward looser on ECC specifically.** If npm publishes `ecc-universal` 2.2.0 or newer, the
version block in Decision item 6 clears on its own. The surface block does not: 284 entries
still require both the acknowledgment and an enumerated name list, and that requirement is
about proportionality rather than about the version.

**Toward automatic installation.** If a future operator decision asks for a library to be
installed by `bundle:install` or `setup`, that reopens Decision item 2 in a new record rather
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
