# Collision precheck (what refuses, why, and what each refusal means)

Use this file when a third-party skill library's install is refused, when a skill name appears
twice, when the wrong copy of a skill seems to be loading, or when deciding whether a foreign
catalog can safely land in a home. It is the reasoning behind
`scripts/install_external_libraries.py`'s refusals; the per-library invocations live in this
skill's `library-front-doors.md`.

## The mechanical fact everything rests on

**Skill names are one flat namespace per home.** A Claude Code home discovers skills by
directory name under `~/.claude/skills/`. Two writers wanting the same name do not merge and
do not error — the first writer holds it, and the second writer's entry is simply not the one
that loads. The operator sees no failure. The skill is just not the one they thought.

That is why a precheck exists at all: the failure it prevents is silent, and it is only cheap
to notice *before* an installer runs.

## The ownership precedent, and the gap it leaves

`scripts/install_skill_bundle.py` already handles one direction of this. An entry it does not
own at a managed path is classified `foreign` and **preserved** rather than replaced — see its
`container_status` and `artifact_payload_status`, which return `foreign` for a path whose
identity does not match the recorded one, and its install path, which reports a conflict
instead of clobbering. Coexistence with the operator's other installs is therefore the default
outcome of this bundle's own install, by construction rather than by luck.

**The gap is the reverse direction.** That classifier can see "someone else owns this path, so
I will not touch it." It cannot see "someone else took this name first, so the entry that
wanted it will never land." From the losing side there is nothing to classify — no file, no
conflict, no error. A precheck run before the foreign installer is the only place that failure
is observable.

## The rules, in evaluation order

1. **Collides with a name this bundle installs → refuse that library.**
   Refuse the library, not the whole run: one bad library in a list of three should not stop
   the other two. This bundle's own names are discovered live from `skills/*/SKILL.md`, the way
   the installer discovers them, so the check cannot drift from what actually installs.

2. **Flat-channel name occupied by another writer → refuse.**
   The library writes directly into `~/.claude/skills/<name>/`, and something else already
   holds that name. Either the library loses or it clobbers, and neither is acceptable
   silently.

3. **Occupied under the library's own name prefix → a reinstall, not a collision.**
   Where a library's every name carries a distinctive prefix (hyperresearch's does), an
   occupied name under that prefix is its own earlier install being refreshed. Counting that as
   a collision would refuse every upgrade. Attribution by name shape is an inference from the
   naming scheme, **never a provenance claim about the bytes on disk** — nothing here verifies
   who actually wrote a file.

4. **Plugin-channel name already present through another channel → refuse as duplication.**
   A plugin is namespaced, so it cannot lose a name. Its failure mode is the opposite: the same
   capability loaded twice, from two channels, drifting apart. Overridable with
   `--allow-duplicate-channel` once the operator accepts it deliberately, because the
   duplication is a real cost and not a defect.

5. **Surface not enumerable → refuse.**
   A precheck that cannot run is not a precheck that passed. A library whose names cannot be
   listed offline is refused until they are supplied from its own enumeration command
   (`--names-from`). This is the rule that gates ECC, whose 284 names need a network call to
   list.

6. **Front-door tool missing from PATH → refuse by name.**
   The tool installs no tool of its own. A missing `claude`, `npx`, or `uv` is reported as the
   named cause rather than surfacing as an opaque subprocess failure.

## A symlink occupies a name

An entry another installer symlinked into place holds the name exactly as firmly as a real
directory does. Reading a link as "absent" is precisely the mistake that produces the silent
loss this precheck exists to prevent, so the check treats any entry — directory, file, or link
— as occupying its name, and reports which kind it found along with the link target.

This is not hypothetical. A home managed by a second installer commonly has flat skill
directories that are all links into that installer's own tree, so *every* name it manages
looks like a link rather than a directory.

## What a refusal does and does not mean

- A refusal is about **names and evidence**, never about a library's quality. Nothing here
  reviews content, and a refused library may be perfectly good.
- A refusal is **per library**. Other named libraries in the same invocation are still
  evaluated and reported.
- A **pass** means the names do not collide and the recorded facts held. It is not a claim that
  the library is safe, correctly licensed, or worth its selection-surface cost — those remain
  the operator's judgement.
- **Installing is not endorsing**, and **a successful install is evidence, not
  authorization.** It authorizes no push, no publication, no merge, no deployment, and no
  further install.

## The cost a precheck cannot catch

Collision is mechanical and checkable. **Selection-surface pressure is neither.** Every skill a
library adds is a row an agent must reason over on every turn it selects a skill, and no check
can tell whether an entry's share of that attention tracks its share of the sessions it fires
in. Against a bundle of 9 skills, a 284-entry catalog is a roughly 31× multiplication of the
surface in exchange for a firing rate nobody has measured for any individual entry. That
arithmetic goes stale as soon as either side's count changes, so recompute it against the
actual tree at decision time rather than reusing a number from this file.
