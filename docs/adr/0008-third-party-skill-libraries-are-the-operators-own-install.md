# ADR-0008 — A third-party skill library is never vendored into this bundle; its bytes stay upstream and adaptation requires a NOTICE donor entry

- **Status:** accepted — **in part.** Read the next line before treating any part of this
  record as a constraint.
- **Refined in part by:** `docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md`,
  which overrides **Decision item 1** (no task installs a third-party skill library) and
  **Considered option 3** (which rejected exactly the `libraries:*` tasks 0009 adds). Those two
  no longer bind: this bundle now ships opt-in `libraries:list`/`libraries:status`/`libraries:install`
  tasks that invoke a named library's own front door. **Everything else here still binds** — in
  particular Decision item 2 (foreign bytes are never vendored; adaptation plus a `NOTICE` donor
  entry is the only inbound path), Decision item 3 (a library is installed through its own front
  door and the installer preserves the result), Decision item 5 (project-scoped naming), reasons
  1 and 3 of item 4 (selection surface, silent name collision), and ADR-0002's
  bootstrap-prerequisite count, which 0009 also does not raise. Per
  `skills/adr-lifecycle/references/lifecycle-states.md` § Partial supersession this record stays
  `accepted` rather than flipping to `superseded by`, because most of it remains in force; the
  status is annotated instead so no reader takes item 1 as current.
- **Date:** 2026-08-07
- **Deciders:** operator (decision), agent (evidence and drafting)
- **Relates to:** `docs/adr/0001-mit-license-and-root-notice-attribution.md`
  (the `NOTICE` donor register this record's adaptation path writes into),
  `docs/adr/0002-mise-is-the-single-front-door.md`
  (Decision items 1 and 2 — the prerequisite count this record must not raise),
  `skills/agentic-sdlc/references/skill-authoring.md`
  (the four-gate admission test, restated for foreign content in its Section 4, now titled
  "A foreign skill library is never vendored, and installable only on request" to carry
  0009's refinement),
  `scripts/install_skill_bundle.py` (the installer whose ownership model makes
  coexistence work), `NOTICE`,
  `docs/research/2026-08-05-vendoring-install-ux-memo.md`,
  `docs/research/2026-08-05-restructure-design-single-source.md`,
  `docs/research/2026-08-05-restructure-design-plugin-first.md`,
  `docs/research/2026-08-06-hyperresearch-per-repo-profile.md`

## Context

Three third-party skill libraries have been evaluated across five research memos in
this repository over two days, and every memo reached a per-item verdict without ever
recording the general rule those verdicts share. The result is that each new session
re-derives the same answer from the same evidence, and the memo corpus reads as an
unfinished vendoring backlog rather than as a settled policy. This record states the
rule the repository has in fact been following.

**Nothing external is installed today, and that was verified rather than assumed.** A
real install of this bundle writes exactly its own content and nothing else. The
authoritative statement of *what* it writes is the installer's own enumeration —
`discover_entries()` in `scripts/install_skill_bundle.py`, which globs exactly
`skills/*/SKILL.md` (each installed for both the Claude and Codex planes),
`agents/claude/*.md`, `commands/*.md`, and `agents/codex/*.toml`. Read that function
rather than trusting a count here: the count moves with the tree, and a frozen number
in this record is stale the next time a skill lands. Measured at this record's date, it
resolves to 12 skills across two planes plus 7 Claude role agents, 7 Codex role TOMLs,
and 5 commands — 43 entries. `bundle:status` reports every entry `ok:` with zero
`conflict`/`foreign`/`missing`/`drift`, and zero foreign files appear anywhere in the
install (`docs/research/2026-08-06-clean-install-verification.md` records the same
shape at an earlier, smaller skill count). The installer has **no network path at
all** — `scripts/install_skill_bundle.py` contains no HTTP client, no `urllib`, and no
shell-out to a fetcher; it symlinks or copies from this checkout and nothing else. So the decision below is not a new restriction on shipped behavior. It
is a description of shipped behavior, promoted to doctrine so it stops being
re-litigated.

The three libraries, with the facts that matter:

- **hyperresearch** — PyPI package `hyperresearch` 0.10.0, MIT, Jordan Gibbs. It is a
  **CLI that renders** skills and agents into a home directory at install time, not a
  static catalog. Its rendered agents carry static `model:` frontmatter, which
  `validate_agents()` in `scripts/validate_bundle.py` rejects outright with
  `static model is forbidden` — at `:1189-1190` for a Claude `.md` agent and at
  `:1202-1203` for a Codex `.toml` agent. Vendoring its output would also freeze
  one operator's rendered profile — one machine's model map, one machine's paths — as
  this bundle's doctrine, and would ship the unresolved template placeholders the
  renderer leaves behind.
- **ECC** — `affaan-m/ECC`, MIT, Affaan Mustafa; npm package `ecc-universal`, at
  **2.1.0 on npm against 2.2.0 in the repository**. Roughly **282 skills**, and it
  ships its own competing installer.
- **mattpocock** — `mattpocock/skills`, MIT, Matt Pocock. It is an official Claude
  marketplace plugin (`mattpocock-skills`) and is also installable via npm through
  its author's own front door. On this machine **9 of its skill names are already
  occupied by its own installer**.

## Considered options

1. **Vendor the wanted subset into `skills/<upstream-name>/`.** Rejected on the
   name-collision mechanics below and on the proportionality gate. It is also the
   option the memo corpus drifted toward by default, which is why the rule needs to
   be written down rather than left implicit.
2. **Vendor under a project prefix (`skills/sdlc-<capability>/`).** Rejected as a
   general answer. The prefix genuinely defeats collision, and the earlier memos were
   right about that much — but it does not touch the selection-surface cost, which is
   the binding constraint at 282 candidate entries against 12 incumbents, and it does
   not touch the static-model-pin rejection for rendered agent content. A prefix
   solves the third problem of three.
3. **Add a mise task or an installer flag that fetches and installs a library on
   request** (a pinned-SHA fetch script, a `pipx`/`uv tool` pin, a cross-marketplace
   `dependencies` entry). Rejected under ADR-0002: see reason 2 below. Every front
   door these libraries ship requires either a second package manager, a network
   credential, or a pin form that cannot be checksum-locked in `mise.lock`.
4. **Adapt ideas into `references/*.md` with a `NOTICE` donor entry, and leave the
   library itself to the operator's own installer (chosen).** Costs a hand-written
   re-expression per idea, which is slower than copying bytes. Buys a corpus whose
   every entry cleared this bundle's own gates, and an install that never competes
   with the operator's other installs.
5. **Do nothing; leave the per-library verdicts scattered across five memos.**
   Rejected. The re-derivation cost is real and observed: two memos independently got
   ECC's license wrong, and a third re-derived a licensing blocker that had already
   been closed. An unrecorded rule is a rule that gets re-argued.

## Decision

1. **No mise task, installer path, hook, or command in this bundle fetches, renders,
   or installs a third-party skill library.** The installer's reach is this
   checkout's own `skills/`, `agents/`, and `commands/` trees, and it stays that way.
   This is the shipped state, recorded so a later change that adds such a path has to
   supersede this record rather than extend a backlog.

2. **Foreign content enters this repository only as an adapted `references/*.md`
   file, with a `NOTICE` donor entry landed in the same change.** Ideas are
   re-expressed in this bundle's own prose and vocabulary; bytes are not copied. The
   donor entry follows `NOTICE`'s own "Adding a donor to this file" checklist — the
   re-resolved commit, the licence with its grant reproduced where required, the
   origin question answered separately from the licence question, and a what-is /
   what-is-not-derived pair. The same provenance statement goes in a header inside
   the derived file. A near-verbatim copy is not an adaptation and is not admitted by
   this path.

3. **A library the operator wants is installed by the operator, through that
   library's own front door**, and this bundle's installer preserves the result. The
   ownership model already does this: an entry this bundle does not own is classified
   `foreign` and preserved rather than replaced. Coexistence is therefore the default
   outcome and needs no new mechanism — only the discipline of not competing for the
   same names.

4. **Three independent reasons carry this, and each would carry it alone.**

   - **Reason 1 — the four-gate admission test and its proportionality gate.**
     `skills/agentic-sdlc/references/skill-authoring.md:89-94` (Gate 2) asks whether
     the corpus has room for one more entry on the selection surface and whether that
     entry's share of attention tracks its share of the sessions it fires in. Against
     **12 incumbent skills, 282 foreign entries is a catastrophic selection-surface
     failure** — a ~24× multiplication of the surface a selector must reason over, in
     exchange for a firing rate that is unmeasured for every one of them. Gate 3
     (`:96-99`, trigger existence today) disposes of the rest: a capability with no
     live trigger in this repository is not ready to be a skill. Gate 1 (`:80-87`,
     selection) fails too, since a bulk import cannot name its nearest neighbor for
     each of hundreds of descriptions.
   - **Reason 2 — ADR-0002.** Every front door these libraries ship would add a
     second bootstrap prerequisite or break lock doctrine, which ADR-0002 Decision
     item 1 forbids and item 2 requires be checked before any pin is committed.
     hyperresearch's is a Python CLI whose `pipx:`-class backend is version-only in
     the lockfile and therefore cannot be checksum-pinned under this repo's
     `locked = true` doctrine. ECC's and mattpocock's npm front doors add a second
     package manager, and the `npm:` backend contributes no lockfile checksum.
     mattpocock's marketplace front door is Claude-only and needs an operator-approved
     cross-marketplace allowlist entry that does not exist. A pinned-SHA fetch script
     needs network at install time, which the betterleaks incident recorded in
     ADR-0002's Context is the exact shape of hazard that turns into a required token.
   - **Reason 3 — the mechanical name-collision fact.** 9 mattpocock skill names are
     already occupied on this machine **by mattpocock's own installer**. Vendoring
     any of those names would hard-block this bundle's install of that entry: the
     installer classifies a non-owned link at a managed path as `foreign` and
     preserves it, which is correct behavior and which means our entry never lands.
     The failure is silent from the operator's side — the skill simply is not ours —
     and it is caused by us, not by the other library.

5. **Naming, when adaptation is not enough.** If a genuinely new, non-colliding,
   freestanding capability ever clears the four-gate test on its own merits, it lands
   under a project-scoped name (`skills/sdlc-<capability>/` or another short
   project prefix), never under an upstream author's bare name. This is item 2's
   escape hatch and it is narrow: clearing the gates is the requirement, and the
   prefix is only the naming rule that applies afterward.

6. **This record changes no shipped file's behavior.** It is a policy record over an
   already-verified state, and it grants nothing. In particular it does not authorize
   an adaptation: each one still needs its own gate pass, its own `NOTICE` entry, and
   the operator's own decision to take it.

## Consequences

- Positive: the per-library verdicts scattered across five memos now have one rule
  behind them, so the next session cites this record instead of re-deriving the
  answer from the same evidence a sixth time.
- Positive: the operator's existing installs — mattpocock's catalog among them —
  coexist with this bundle by construction rather than by luck, because this bundle
  never claims a name it did not author.
- Positive: every entry on the selection surface stays one that cleared this bundle's
  own gates, which is the property that makes the surface worth reasoning over at
  all.
- Negative: **adapting an idea is strictly slower than copying it.** A useful pattern
  in ECC or mattpocock costs a hand-written re-expression plus a donor entry, and
  some good material will simply not be worth that price and will go unadopted. That
  cost is accepted deliberately; it is the same trade ADR-0002 makes on tool pins.
- Negative: the operator carries the install and update burden for any library they
  want. This bundle offers no convenience path, so a library that falls out of date
  in the operator's home stays out of date until they update it.
- Negative: no mechanical check enforces Decision item 1. A future contributor could
  add a fetching task and the gate would not object.
- **Confirmation:** partly mechanical, partly not, and the split is stated rather
  than papered over. Mechanically: `uv run --python 3.12.11 --script
  scripts/validate_bundle.py` reports 0 errors, and `mise run check` — this repo's
  authoritative gate — stays green over the files this record adds. The absence of a
  fetch path is checkable by inspection today (`scripts/install_skill_bundle.py`
  imports no HTTP client and shells out to no fetcher) but is **not mechanically
  asserted**; Decision item 1 is enforced at review. A passing gate is evidence of
  conformance only and authorizes nothing.

## Reversal condition

Reopened by an observable change in either direction.

**Toward admitting a library.** If a library this bundle actually wants publishes a
front door that installs under `mise.lock` with a real per-platform checksum, no
second package manager, and no credential in the environment — the exact bar ADR-0002
Decision item 2 sets — then reason 2 no longer holds for that library, and Decision
item 1 must be re-decided for it in a new record rather than quietly extended. Reasons
1 and 3 would still have to be cleared separately: a lockable front door says nothing
about selection surface or name collision.

**Toward admitting a subset.** If this bundle's own corpus grows to the point where a
foreign catalog's entries would be a small fraction rather than a ~24× multiplication
of the selection surface, reason 1's arithmetic changes and the proportionality
argument must be recomputed against the tree at that time — not read off the numbers
in this record, which go stale by design.

**Toward stricter.** If a library named here changes licence away from MIT, or if a
supply-chain incident is observed in one of their distribution channels, the
adaptation path in Decision item 2 must be re-examined for material already taken
from that donor, and `NOTICE` updated in the same change.

If Decision item 3's coexistence property ever fails — if the installer begins
replacing rather than preserving a foreign entry at a managed path — that is a defect
in the installer and a reopening of this record's third reason, not a licence to
claim the name.

This record is evidence for a conductor to cite; it authorizes no library install,
vendoring pass, dependency addition, push, publication, merge, deployment, or other
outward effect on its own.
