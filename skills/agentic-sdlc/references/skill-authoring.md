# Skill Authoring (admission, promotion, and retirement)

Use this reference when deciding whether a candidate earns its own `SKILL.md` in this
bundle rather than a section of an existing skill or a `references/*.md` file, when writing
or revising a `SKILL.md`'s `name`/`description`, or when a skill is being retired. Adapted
from pi-lab's `skill-authoring-standard` and `lesson-extraction` house skills, with the pi
runtime mechanics (model-invocation flags, package-declaration wiring, host-specific byte
quirks) stripped and replaced by this bundle's own mechanical gate (below). Nothing here is
enforced by any script in this repository unless a section says otherwise; `mise run check`
enforces only the mechanical floor in Section 1.

## 1. The admission floor (this repo's hard mechanical rules)

These are the non-negotiable, mechanically-checked rules from `AGENTS.md`'s "Working on
THIS repo" section. A candidate that fails any one of these does not get a `SKILL.md`,
full stop — no judgement call is possible here:

- **Agent Skills format.** `skills/<name>/SKILL.md`, and `name` in the YAML frontmatter
  MUST equal the directory name.
- **Description ceiling.** The frontmatter `description` MUST be ≤1024 characters. This is
  a hard cap enforced by the validator, not a target to approach.
- **Host-agnostic, always.** No user-specific absolute paths, no provider credentials, no
  internal hostnames, no lab-specific paths or seed IDs in the published artifact. Cite
  provenance as a repo-relative or project-name reference only (e.g. "adapted from
  pi-lab's evidence-discipline skill"), never as a local filesystem path.
- **No new top-level skills without explicit instruction.** Prefer adding or extending a
  `references/*.md` file under an existing skill (most often `skills/agentic-sdlc/`) over
  creating a new `skills/<name>/` directory. A new top-level skill is the most expensive
  outcome available and needs the four-gate test in Section 3 to justify it.
- **`references/*.md` files are loaded on demand.** Each one must be focused and
  self-contained: a reader who has only that file and nothing else must be able to act.
  Do not require the reader to also hold the parent `SKILL.md` open to make sense of a
  reference.
- **Evidence is never authorization.** A skill body may describe gates, receipts, and
  verdicts, but must never state or imply that a passing gate, a role's verdict, or a
  conductor's record *authorizes* an outward effect (push, PR, merge, deploy, credential
  use). Roles and verdicts are advisory submissions only.
- **No static model or effort pins in provider-neutral roles.** A skill body must not
  recommend a specific model or host-default model selection as policy. Model and effort
  selection comes from a conductor-supplied `RuntimeAssignment` at dispatch time.

Run `mise run check` after any skill addition or edit — it is the authoritative gate for
name/dirname parity, the description cap, broken `references/*.md` links, and the other
mechanical checks. A passing gate is evidence that the mechanical floor holds; it is not
evidence that the candidate should exist at all (that is Sections 2–3).

## 2. Audit what is already loaded before adding a skill

**Rule. Before drafting a new skill or reference, check what the bundle already carries.
A capability that duplicates something already loaded is worse than one that duplicates
nothing — it costs description bytes and produces two records that can silently drift
apart.**

Read, in order, before writing a word of the candidate:

1. This skill's own `SKILL.md` — the phase order, delegation rules, and the References
   list. A candidate that only restates one of those sections is not a candidate.
2. Every existing `references/*.md` under the same skill. `git-change-flow.md` is a worked
   example of the outcome: it exists because two skills' worth of doctrine already covered
   the ground, so it ships as a **dispatch table** pointing at the authoritative site
   rather than a third copy of the doctrine.
3. Sibling skills in the bundle (`change-writing`, `model-tier-rightsizing`,
   `stacked-prs`, `stacked-prs-gh-cli`, `repo-toolchain-gates`, `codex-research-os`,
   `cmux-event-bus-messaging`) and `AGENTS.md` itself, for a rule that already has an
   owner.

The check that ends the audit is mechanical, not a feeling: name the file and the section
that already covers the ground, or say plainly that none does. "Already covered by:
nothing" is a legitimate and useful answer — it is what licenses the candidate to proceed
to Section 3. A retired sibling project's own postmortem states the general form of this
failure plainly: a duplicate that reproduces something the host (or, here, a sibling
skill) already provides serves no one, no matter how well-built it is. Check what already
exists before building a second copy of it.

## 3. The four-gate admission test

A candidate earns its own `SKILL.md` only by clearing all four gates. Failing any one
means it lands as a section of an existing skill, or as a `references/*.md` file instead.

**Gate 1 — selection.** Can the description alone (frontmatter, under the 1024-character
cap, no embedded procedure) tell a selector to choose this skill and reject its nearest
neighbor? Write the description before the body. If the description needs the body to
make sense, the candidate is a section of whatever skill already owns that ground. Where
two skills are close enough that a human reader could not confidently say which applies
first, put an explicit counterexample in both descriptions, each naming the other — this
repo's `git-change-flow.md` router and the `stacked-prs` / `stacked-prs-gh-cli` split are
the worked example of naming the neighbor rather than merging into it.

**Gate 2 — proportionality.** Does the corpus have room for one more entry on the
selection surface, and does this entry's share of attention track its share of the
sessions it will actually fire in? A skill that fires in one session a month should not
cost a month's worth of always-on description bytes. Prefer a `references/*.md` file
(zero extra selection-surface cost) over a new top-level skill whenever the candidate's
firing rate does not clearly justify the heavier form.

**Gate 3 — trigger existence today.** Does the situation this candidate addresses exist in
this repository or this bundle **right now** — not plausibly, not after some future
capability lands? A capability with no live trigger is not ready to be a skill; write it
down as a reference with a named promotion trigger instead, and promote it later when the
trigger actually fires.

**Gate 4 — always-on vs. task-shaped.** Is this a per-turn rule rather than a task? A rule
that must apply on every turn belongs in `AGENTS.md` or the calling role's own prompt,
where it is actually always on. A skill loads only on selection; a per-turn rule expressed
as a skill fires late, or not at all.

### The ≥2-of-5 promotion test

A `references/*.md` file needs zero conditions — it costs no selection-surface row and no
extra description bytes, so it is always the cheaper default. Promoting a reference (or a
brand-new idea) into its own `SKILL.md` needs **at least two** of the following five to be
true:

1. **Recurs** across sessions or across repositories, not once in one run.
2. **Needs specific sequencing** that a single paragraph inside a host skill cannot carry
   without becoming its own sub-document.
3. **Failures repeat** because a gate or a check keeps getting skipped when the material
   is buried inside a larger file.
4. **Has a stable input/output contract** — a caller can name what it takes and what it
   returns without reading the whole bundle.
5. **Benefits from an explicit handoff** — a separate selection surface changes how (or
   whether) a downstream agent picks it up, versus leaving it folded into a host skill's
   body.

Clearing one of the five is a preference. Clearing two or more is the argument that
justifies the heavier form — write which two (or more), explicitly, in the change that
adds the skill, so a later reviewer can check the argument rather than re-deriving it.

## 4. A foreign skill library is never vendored, and installable only on request

**Rule, in two parts. This bundle never copies a third-party library's bytes into its own
tree. It can invoke that library's own installer, on the operator's explicit request,
through a task no gate and no setup path reaches.** Vendoring and invoking look adjacent
and are not the same act, and conflating them is the mistake this section exists to
prevent.

**Why vendoring stays closed.** Copying foreign bytes into `skills/` puts another party's
content in this repository's distribution: it triggers the root `NOTICE` donor obligation,
drags a licence along, freezes one snapshot of a catalog that keeps moving, and puts
entries this bundle did not author onto its own selection surface as things it ships.
Foreign material therefore enters by exactly one path: an **adapted `references/*.md` file
with a donor entry added to the root `NOTICE` in the same change**. Ideas are re-expressed
in this bundle's own prose and vocabulary; bytes are not copied. A near-verbatim copy is
not an adaptation and this path does not admit it. Follow `NOTICE`'s own "Adding a donor to
this file" checklist, and repeat the provenance statement in a header inside the derived
file.

**Why invoking is open, and how it stays safe.** Running a third party's own installer
copies nothing here. The bytes land in the operator's home, written by the library's own
code, under its own name and licence, exactly as if the operator had typed the command —
so no donor obligation attaches, because this bundle is not a donee. Three properties keep
that from becoming vendoring by another route, and each is load-bearing:

- **Explicit and opt-in.** The `libraries:*` tasks are invoked deliberately and dry-run
  without `--yes`. No gate leaf and no `contributor:setup`, deprecated `setup`, or
  `lifecycle:install` path reaches them, so an install is never a side effect of setting up this
  repository.
- **No new prerequisite.** A front door invoked by a separate task that nothing in the
  gate's dependency closure depends on adds no bootstrap prerequisite. That is the
  distinction from a *pinned* front door in `[tools]`, which
  `docs/adr/0002-mise-is-the-single-front-door.md` does forbid.
- **Collision-checked before it runs.** Name collision is mechanical and silent: first
  writer holds a name, and the loser's entry simply is not the one that loads, with no
  error at all. The precheck compares against this bundle's own names rather than
  describing the hazard in prose.

Two of Section 3's gate arguments survive unchanged and are why installation is a choice
rather than a default. **Gate 2 (proportionality) is the binding one:** a catalog of a few
hundred foreign entries against this bundle's own handful is a catastrophic
selection-surface failure, buying an enormous multiplication of what a selector must reason
over in exchange for a firing rate nobody has measured. **Gate 3 (trigger existence today)**
disposes of the remainder, and Gate 1 cannot even be attempted for a bulk import — no bulk
description names its nearest neighbor. Those costs land in the operator's home when they
ask for them; they are not this bundle's to impose.

If a genuinely new, non-colliding, freestanding capability ever clears Section 3 on its
own merits, it lands under a project-scoped name (`skills/sdlc-<capability>/` or another
short project prefix), never under an upstream author's bare name. Clearing the gates is
the requirement; the prefix is only the naming rule that applies afterward.

The decisions and their evidence live in
`docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md` (the
opt-in mechanism, the named libraries, and their re-verified front doors) and
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md` (the
no-vendoring rule 0009 refines, with the licence, version, and collision facts). The
`external-skill-libraries` skill owns the operational procedure. Cite them rather than
re-deriving the answer.

## 5. Retire by redirect, never by deletion

**Rule. A retired skill keeps its directory and its trigger surface, and spends its
description routing away from itself, toward its replacement.**

Deletion looks clean and is not: the old name is exactly what an agent or an operator
still reaches for, and a deleted skill produces a silent miss with no signal pointing
anywhere. A redirect answers the reach with the replacement's name.

Three obligations travel with a redirect:

1. **It still costs description bytes.** A redirect entry is charged against the same
   budget as any live skill. If the old name is not actually being reached for anymore,
   delete instead of redirecting — a redirect nobody hits is pure cost.
2. **State the retirement plainly in the frontmatter description and the body opening
   line**, naming the replacement by path (e.g. "Retired — use `skills/<replacement>/`
   instead. Do not invoke this skill for new work."). A gate or a reader that lands here
   must be told where to go in the first sentence, not the last.
3. **Do not describe retired behavior as current.** Update every cross-reference this
   bundle owns (other `SKILL.md` files, `references/*.md` files, `AGENTS.md`) to point at
   the replacement in the same change that retires the old skill — a stale pointer left
   behind a retirement notice is the same failure as a stale pointer left behind a
   deletion, just quieter.

## 6. What this reference does not do

- It does not enforce anything beyond Section 1's mechanical floor, which `mise run
  check` already covers. Sections 2 through 5 are judgement calls for a human reviewer or
  an integrator to weigh, not gate leaves — including Section 4, whose rule is enforced at
  review rather than by any check.
- It does not publish a corpus-wide description-byte budget for this bundle. If that
  number matters for a decision, measure it against the current tree at decision time
  rather than reusing a number written in this file — any such figure goes stale the
  moment another skill or reference lands.
- It does not decide whether a claim inside a candidate skill's body is true, or at what
  evidence class. `references/evidence-discipline.md` owns that question.
- It does not decide how a lesson learned mid-task should be routed to a skill, a
  reference, a fix in `AGENTS.md`, or nowhere. That routing judgement — matching a habit
  to the cheapest destination that actually holds it, and preferring an incumbent-text
  upgrade over a new row whenever an existing file is *almost* right — is upstream of this
  file's admission test; use it before invoking Section 3, and use Section 3 for the
  candidates it produces.

## Cross-links

- `AGENTS.md` — "Working on THIS repo" is the source of Section 1's mechanical floor.
  Read it directly rather than trusting a paraphrase; this file restates it only to give
  the admission floor one page.
- `references/git-change-flow.md` — a worked example of the dispatch-table pattern this
  file's Section 2 recommends over a duplicated third copy of doctrine.
- `references/evidence-discipline.md` — owns whether a claim inside a skill body may be
  stated at all, and at what class; this file never re-derives that vocabulary.
- `references/mission-loop.md` — Seeds-first and the no-inline-fixes rule are the queue
  analogue of this file's "route it, don't fold it into agent memory" stance.
