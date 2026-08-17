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
   capability loaded twice, from two channels, drifting apart. Two routes out: `migrate` (below)
   when the other channel provably serves the same upstream, or `--allow-duplicate-channel` once
   the operator accepts the duplication deliberately, because it is a real cost and not a defect.

5. **Surface not enumerable → refuse, unless the cost is acknowledged and the skip is labelled.**
   A precheck that cannot run is not a precheck that passed — that part never bends. What
   changed is the consequence: a library whose surface cannot be listed offline is refused by
   default, but where the operator has acknowledged the surface cost explicitly, it proceeds with
   the check reported as `precheck: SKIPPED, not passed`, in those words, on the plan and again
   after the install. Requiring `--names-from` unconditionally would have made ECC unreachable;
   printing nothing would have let a skipped check read as a clean one. `--names-from` remains
   available and turns the skip into a real comparison.

## Migration: proving two channels serve one upstream

Rule 4 has a route out that rule 2 does not, and the difference is provenance. A flat-channel
collision is a stranger holding the name. A duplicate-channel collision *may* be the same
upstream arriving by a different road — in which case removing the other copy loses no
capability at all. But "may be" is not evidence, and this is the one place the tool removes
anything, so the bar is the other channel's own record.

**Presence is not provenance.** That sentence appears twice in this file for a reason: the same
directory listing that proves a name is taken says nothing about who put it there. So `migrate`
reads the competing channel's own lock file — `$XDG_STATE_HOME/skills/.skill-lock.json` when that
variable is set, `~/.agents/.skill-lock.json` otherwise, matching how that channel resolves it —
and per occupied name compares the recorded `source` and `sourceUrl` against the library's
upstream. What it does with the answer:

| Lock says | Verdict |
|---|---|
| Same `source` **and** same `sourceUrl` | proven, eligible for removal |
| Different `source` | not proven — a different library |
| Same `source`, different `sourceUrl` | not proven — a label is not an identity |
| No entry for that name | not proven — occupied but unattributable |
| No lock file / unreadable / stale schema version | proof **unavailable** → refuse outright |

Anything unproven is left exactly where it is, and a single unproven name refuses the whole
migration rather than half-completing it. A library with no recorded upstream identifier can
never be migrated, because there is nothing to prove sameness against.

**Removal goes through the other channel's own front door**, never through this tool:
`npx -y skills@latest remove --global --agent claude-code --yes <names…>`. The `--agent` scope is
load-bearing rather than cosmetic. Without it that command targets every agent in its registry —
deleting the canonical `~/.agents/skills/<name>`, every other agent's link, and the lock entry —
which on a multi-host home is a real capability loss for every host that was not the problem.
Scoped to one agent it removes only the Claude Code path and leaves the rest intact.

**Ordering is the safety property.** Remove, then re-run the precheck against the real
filesystem, then install. A removal that exits nonzero stops the migration. So does a removal
that exits zero while names remain occupied — a partial removal, which is the more dangerous
case precisely because it looks like success. Installing over a still-occupied name is the
silent loss this entire file exists to prevent, so it never happens on an unverified assumption.

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
- A **skip** is not a pass, and nothing renders the two alike. `precheck: SKIPPED, not passed`
  means no comparison happened: names this library takes from another writer would not have been
  reported, before or after the install.
- A **refusal on an accepted caveat is not silence.** Where the operator has overruled a refusal,
  the underlying fact is recorded as a caveat and printed on every plan. Overruled means accepted
  in the open, never deleted.
- A **refusal in a dry run exits 0**, and that is not leniency. A dry run was asked to describe
  what would happen; "a real install would refuse, because X" is a correct, complete answer, so
  the run succeeded at its job. The same refusal under `--yes` exits 1, because there something
  was supposed to change and did not. Before this split, a dry run on a machine without the
  front-door tools failed, which made the repository gate pass on a developer host with `claude`
  on PATH and fail on a clean one — the refusal was being reported as though the tool had broken.

## Why a missing front-door tool is a precheck fact, not a precheck failure

`shutil.which` is the only thing that decides whether a front door is reachable, and it reads the
PATH of whoever is running. That makes it the one input to this file's rules that varies by host
rather than by evidence. Two consequences worth stating, because both have already caused a bug:

1. **Report it, don't fail on it, unless something was actually being attempted.** A dry run on a
   machine with no `claude`, no `npx`, and nothing installed should describe all three libraries
   accurately and exit 0.
2. **Test it by stubbing, not by stripping PATH.** Emptying PATH to the interpreter's own
   directory is not enough: a tool installed alongside the interpreter (`~/.local/bin/claude` next
   to `~/.local/bin/uv`) walks straight back in and the missing-tool branch never runs. Stub
   `shutil.which` to `None` instead, and assert the paired opposite — a real `--yes` run must still
   exit nonzero — so the leniency cannot spread.
- **Installing is not endorsing**, and **a successful install is evidence, not
  authorization.** It authorizes no push, no publication, no merge, no deployment, and no
  further install.

## The cost a precheck cannot catch

Collision is mechanical and checkable. **Selection-surface pressure is neither.** Every skill a
library adds is a row an agent must reason over on every turn it selects a skill, and no check
can tell whether an entry's share of that attention tracks its share of the sessions it fires
in. Against a bundle of 12 skills, a 284-entry catalog is a ~24× multiplication of the
surface in exchange for a firing rate nobody has measured for any individual entry. That
arithmetic goes stale as soon as either side's count changes, so recompute it against the
actual tree at decision time rather than reusing a number from this file.
