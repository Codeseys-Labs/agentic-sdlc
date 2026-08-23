# ADR-0029 — Ported libraries are a second external-library catalog class, onboarded through a recipe rather than a front door; pstack is the first member

- **Status:** accepted
- **Date:** 2026-08-20
- **Deciders:** operator (decision, recorded 2026-08-20 as `agentic-sdlc-408a`); agent (evidence and drafting)
- **Refines:** `docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md`
  — adds a second catalog class alongside 0009's front-door class. Nothing in 0009 changes:
  its closed three-row catalog (`mattpocock/skills`, ECC, hyperresearch), its
  `libraries:list`/`libraries:status`/`libraries:install`/`libraries:migrate` mechanism, its
  collision precheck, its dry-run-by-default rule, and its no-credential/no-vendoring
  boundaries all stand exactly as written. This record narrows nothing about 0009's own class;
  it names a structurally different class that 0009 never addressed.
- **Relates to:** `docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md`
  (the no-vendoring rule this record also stays inside of),
  `docs/adr/0001-mit-license-and-root-notice-attribution.md` (the `NOTICE` donor register this
  record does not need to write into),
  `skills/external-skill-libraries/SKILL.md` (the skill surface this record adds a section to),
  `skills/external-skill-libraries/references/porting-a-foreign-plugin.md` (the recipe this
  record's second class points at, executed once already and generalized from that run),
  `docs/progress/2026-08-19-pstack-claude-code-port.md` (the executed record the recipe
  generalizes from)

## Context

ADR-0009 closed the external-library catalog to exactly three names —
`mattpocock/skills`, `affaan-m/ECC`, and `hyperresearch` — each reachable because each
publishes its own installable front door (a marketplace plugin, an npm-distributed CLI, or a
PyPI-distributed CLI) that this bundle's `install_external_libraries.py` can invoke without
copying a single byte into this repository. That mechanism assumes a front door exists.

`pstack` (`github.com/cursor/plugins/tree/main/pstack`, Lauren Tan / "poteto") does not have
one. It is a Cursor-native workflow plugin: its manifest lives at
`.cursor-plugin/plugin.json` rather than `.claude-plugin/plugin.json`, and its skills are
written against Cursor-only runtime primitives with a hard cross-plugin dependency on
`cursor-team-kit`. There is no `claude plugins install pstack`, and no npm or PyPI package
targeting this host — no upstream command this bundle's front-door mechanism could invoke at all. Forcing
it into ADR-0009's mechanism would misdescribe what actually happens: there is nothing to run,
only dozens of foreign files to read and rewrite by hand.

The operator decided (`agentic-sdlc-408a`, closed 2026-08-20) that pstack should be onboardable
anyway — judged on par with `mattpocock/skills` in capability terms, worth admitting despite
having no front door. That decision already names the mechanism: execute
`skills/external-skill-libraries/references/porting-a-foreign-plugin.md`, the recipe this
bundle already ships, generalized from one executed port recorded first-person in
`docs/progress/2026-08-19-pstack-claude-code-port.md`. That recipe's own Section 9 already
states, in its own words, that a port "does not make the port an installable catalog entry in
this bundle" and "is never proposed as a fourth row" of ADR-0009's catalog — this record is
the doctrine that makes that boundary explicit at the ADR level rather than leaving it stated
only inside one reference file, and it is the doctrine `agentic-sdlc-5ebc` (closed 2026-08-20)
already relied on when it closed the "gather evidence from pristine HEAD, never the ported
tree" practice as encoded in that same recipe's checklist item 9.

What the recipe does not yet encode is a **recorded commit pin**: neither
`porting-a-foreign-plugin.md` nor the executed progress record it generalizes from names the
exact upstream commit the port was read against. This record adds that requirement going
forward — verified here as a gap, not claimed as already mechanized — so that "pristine
upstream HEAD" is a provenance fact tied to one commit rather than a moving target.

## Considered options

- **Add pstack as a fourth row in ADR-0009's closed front-door catalog.** Rejected: the whole
  premise of that catalog is a real upstream front door that
  `install_external_libraries.py` can invoke; pstack has none. Adding a row with no front door
  would either fabricate one or quietly redefine what a "front door" means for every other row,
  neither of which is honest.
- **Refuse pstack, on par with any other unlisted library under ADR-0009's 2026-08-10
  amendment ("an unlisted library ... is outside every ownership or support claim").**
  Rejected by explicit operator decision in `agentic-sdlc-408a`: the operator judged pstack
  worth admitting, not left as unverified foreign state.
- **Build a new installer-task automation that performs the port mechanically (a
  `libraries:port`-shaped task).** Rejected for this record. Automating file-by-file manifest
  relocation, primitive substitution, and validator round-tripping is a materially larger and
  differently-shaped surface than invoking a front door, and deciding whether to build it is a
  separate future decision — bundling it here would smuggle an implementation choice into a
  catalog-taxonomy decision.
- **Onboard pstack by executing the existing manual recipe against pristine upstream HEAD,
  landing the result in the operator's own plugin tree (chosen).** Costs an operator's own
  read-and-rewrite pass per port, same as the one already executed and recorded. Buys pstack
  access without vendoring a byte into this repository and without adding any new installer
  surface.

## Decision

1. **The external-library catalog now has two classes, not one.** *Front-door libraries*
   (`mattpocock/skills`, ECC, hyperresearch) install through upstream's own published front
   door, exactly as ADR-0009 decided — unchanged by this record. *Ported libraries* onboard by
   executing the shipped porting recipe against upstream, because no front door exists to
   invoke.

2. **`pstack` is the first, and as of this record the only, ported-class member.** Onboarding
   it means running `skills/external-skill-libraries/references/porting-a-foreign-plugin.md`'s
   checklist against a pristine read of upstream HEAD at
   `github.com/cursor/plugins/tree/main/pstack` — never against a working copy the port has
   already modified, per that recipe's own checklist item 9.

3. **Every execution of the recipe records the exact upstream commit it read pristine HEAD
   from.** This is a new requirement this record adds, not a restatement of something the
   recipe or the executed progress record already contains — verified above as a gap. The pin
   is what lets a later reader tell which upstream state a given port actually reflects, and
   what a re-port re-reads against to detect drift.

4. **The ported result lands in the operator's own home, under the operator's own ownership,
   exactly as the 2026-08-19 executed port did** (`~/.claude/local-plugins/pstack-src/pstack/`,
   registered through a local marketplace the operator points at their own checkout). It is
   never proposed as, or treated as, an entry in ADR-0009's closed front-door catalog, and it
   is never staged, copied, or symlinked into this repository. Upstream bytes never enter this
   repository under this decision, exactly as ADR-0001 and ADR-0008 already require for the
   front-door class.

5. **Re-porting on a later upstream change is a recipe re-run against the new pristine HEAD,
   with a new recorded commit pin — never a channel update.** There is no update mechanism to
   subscribe to, because there is no channel; the recipe's checklist item 7 (bump the version
   string on every reinstall during a session) already covers the mechanical half of this
   inside one session, and this record extends the same discipline across sessions via the
   commit pin.

6. **This record creates no installer-task automation.** No `mise` task, no addition to
   `install_external_libraries.py`, and no change to `libraries:list`/`status`/`install`/
   `migrate` follows from this decision. Whether the port should ever be automated is an
   explicitly separate future decision, not implied or pre-authorized here.

7. **This record refines ADR-0009; it does not supersede it.** ADR-0009's decision items,
   its closed catalog, and its mechanism stay exactly as accepted. This record only names a
   second, disjoint class that 0009's front-door mechanism structurally cannot serve, because
   that class has no front door to invoke in the first place.

## Consequences

- Positive: pstack becomes onboardable without violating this bundle's no-vendoring rule and
  without adding a fourth row to a catalog whose whole shape assumes a front door that pstack
  does not have.
- Positive: future onboarding requests for a library with no Claude Code front door now have a
  named class and a named recipe to be judged against, instead of being silently refused under
  ADR-0009's "unlisted library" clause or forced into a catalog row that misdescribes them.
- Positive: no new installer-task surface is created, so `mise run check`'s dependency-closure
  guarantee that no gate leaf reaches a `libraries:*` task (ADR-0009 Decision item 2) is
  untouched by this record — there is no ported-class task to reach.
- Negative: the ported class has exactly one member and no installer mechanism at all; today's
  practical effect of this record is naming and permission, not new automation. Onboarding a
  second ported library still means writing (or reusing) a recipe-shaped read-and-rewrite pass
  by hand.
- Negative: the recorded-commit-pin requirement this record adds (Decision item 3) is not
  mechanically enforced by anything in this repository — `porting-a-foreign-plugin.md` is a
  discipline document with an unenforced checklist, and this record adds one more line to that
  checklist's spirit without adding a check. Compliance rests on the operator actually writing
  the pin down in whatever record accompanies a future port, the same way the 2026-08-19 port's
  own progress record rests on the operator having written it honestly.
- Negative: this record's own commit-pin requirement is unverified against the one port that
  has actually happened — the 2026-08-19 execution predates this decision and recorded no pin,
  so it does not retroactively satisfy Decision item 3. A future re-port is the first execution
  this record's new requirement actually binds.
- **Confirmation:** `uv run --python 3.12.11 --with pyyaml --script scripts/validate_bundle.py`
  reports 0 errors and 0 warnings over this record and the `skills/external-skill-libraries/`
  section it accompanies. Whether a given future port actually recorded its commit pin and read
  from a pristine checkout is not mechanically checkable by this repository, which never sees
  the operator's own plugin tree; it is enforced at review of whatever record documents that
  port, the same way `porting-a-foreign-plugin.md`'s own checklist is enforced at review today.
  A passing gate is evidence of conformance only and authorizes no port, install, push,
  publication, merge, deployment, or other outward effect.

## Reversal condition

**Toward automation.** If a future operator decision asks for pstack's port (or any ported
library's port) to be performed or refreshed by a `mise` task rather than by hand, that reopens
Decision item 6 in a new record rather than being implemented as a quiet task addition under
this one.

**Toward a front-door reclassification.** If pstack (or `cursor/plugins` generally) ever
publishes an actual Claude-Code-targeting front door upstream, that is an observable event that
reopens whether pstack belongs in ADR-0009's closed front-door catalog instead of the ported
class — a new record decides that move, rather than this one being read as having already
made it.

**Toward stricter.** If a future port is executed without recording the commit pin Decision
item 3 requires, or is executed by citing a modified working copy for an upstream claim rather
than a pristine read, that is a defect in how the recipe was followed, not evidence this
record's requirement was wrong — the recipe's own checklist item 9 already names the second
failure mode.

This record is evidence for a conductor to cite; it authorizes no port, install, vendoring
pass, dependency addition, push, publication, merge, deployment, or other outward effect on its
own.
