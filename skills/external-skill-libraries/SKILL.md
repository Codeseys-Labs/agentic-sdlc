---
name: external-skill-libraries
description: |
  Install a THIRD PARTY's skill library (ECC, mattpocock/skills, hyperresearch) through that
  library's OWN front door, opt-in and never automatically. Use when: (1) someone asks to
  install, add, update, remove, or check an external/foreign skill library or marketplace
  plugin; (2) a skill name appears twice or the wrong copy loads, and you need the
  collision/duplicate-channel diagnosis; (3) deciding whether a foreign catalog is worth its
  always-on selection-surface cost. Covers the per-library front door and its evidence, the
  first-writer-wins name rule, dry-run-by-default with an explicit --yes, and why this bundle
  never copies upstream bytes (so no NOTICE obligation). NOT for authoring or admitting a
  skill into THIS bundle — the `agentic-sdlc` skill's skill-authoring reference owns whether a
  skill should exist at all, and adapting a foreign IDEA into this repo's own prose. This
  skill installs foreign libraries wholesale into a home; it never vendors, never adapts, and
  admits nothing to this repository.
---

# External Skill Libraries

Install a third party's skill library by running **that library's own installer**, as an
explicit operator step. Read this when a library is wanted, when a name collides, or when
someone asks whether a catalog is worth its cost.

The tool is `scripts/install_external_libraries.py`, wired as three mise tasks:

```bash
mise run libraries:list      # what is available, its front door, its cost, what is detected
mise run libraries:status    # what is already present in this home
mise run libraries:install   # refuses without an explicit library name
```

`install` and `uninstall` take **explicitly named libraries only**. There is deliberately no
verb that installs everything, and none of these verbs is reachable from `bundle:install`,
`bundle:install:claude`, `bundle:install:codex`, `setup`, or any gate leaf.

## The distinction that makes this safe

**Invoking a third party's own installer is not vendoring.** No bytes from any library enter
this repository, so no `NOTICE` donor obligation attaches and no upstream licence text
travels with anything here. Each library writes into the operator's own home, under its own
names, by its own code.

That is the whole difference from the vendoring question, which is settled separately and
stays settled: this bundle still ships only its own skills, agents, and commands, and a
foreign **idea** still enters this repository only as an adapted `references/*.md` file with
a `NOTICE` donor entry. See `docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md`,
which supersedes in part the blanket "never install" position in
`docs/adr/0008-third-party-skill-libraries-are-the-operators-own-install.md`.

Two costs survive the distinction, and they are why this skill exists rather than a one-line
instruction to run the installer:

1. **Selection-surface pressure.** Every skill a library adds is a row an agent reasons over
   on every turn it selects a skill. This is the cost that does not show up in any diff.
2. **Name collision.** Skill names are one flat namespace per home. First writer holds the
   name; the loser's entry is silently not the one that loads.

## The three libraries, honestly costed

| Library | Surface | Channel | Front door |
|---|---|---|---|
| `mattpocock` | 25 skills | plugin (namespaced) | `claude plugins install mattpocock-skills` |
| `ecc` | 284 skills, 67 agents, 94 shims | flat `~/.claude/skills/` | `npx ecc-universal setup` |
| `hyperresearch` | 17 skills + 14 agents, rendered | flat, `hyperresearch`-prefixed | `uv tool install hyperresearch` |

**ECC's 284-skill surface is the headline.** Against this bundle's 9 skills that is a ~31×
multiplication of what a selector must reason over, in exchange for a firing rate nobody has
measured for any individual entry. It writes flat into `~/.claude/skills/<skill-name>/` — the
same namespace this bundle's entries occupy — so every one of the 284 names is a
first-writer-wins claim. It is gated behind `--acknowledge-ecc-surface` **and**
`--names-from`, because its surface cannot be enumerated offline and a precheck that cannot
run must not report a pass. A second, independent block also stands: ECC's own README
requires `ecc-universal` 2.2.0 or newer for the guided commands while npm's `latest` serves
2.1.0, so the documented front door is newer than the published artifact.

**mattpocock is cheap by an order of magnitude** — 25 versioned entries through an official
marketplace plugin, already listed, so there is no `marketplace add` step to run first.
Because a plugin is namespaced it cannot *lose* a name; its failure mode is the opposite one,
duplication, which upstream names itself: "Pick one — installing both leaves you with every
skill twice." Its editable npm front door (`npx skills@latest add mattpocock/skills`) is
deliberately **not** wired here — that is the channel that competes for flat names, and it
prompts interactively.

**hyperresearch is not a skill library at all.** It is a CLI that *renders* skills and agents
into a home or a project. Installing the tool writes no skills; its own `hyperresearch
install` verb does (`--global` for the home). Every name it writes is `hyperresearch`-prefixed,
so its collision surface against this bundle is structurally empty rather than merely
observed to be empty. Its rendered agent files carry static `model:` frontmatter, which this
repo's validator rejects for agent files — a reason never to vendor its output, not a reason
to refuse to run its renderer in a home, where this repository's validator has no
jurisdiction.

## The collision rule

Before invoking any front door, enumerate the names the library will write and compare them
against (a) this bundle's own skill names and (b) what already occupies the target home.
Then:

- **Collides with a name this bundle installs** → refuse **that library**, not the whole run.
- **Flat-channel name occupied by another writer** → refuse. The library would lose or clobber.
- **Occupied under the library's own name prefix** → a reinstall, not a collision. Proceed.
- **Plugin-channel name already present via another channel** → refuse as duplication,
  overridable with `--allow-duplicate-channel` once the operator accepts it deliberately.
- **Surface not enumerable** → refuse. A precheck that cannot run is not a precheck that passed.

A symlink counts as occupying a name. An entry another installer linked into place holds the
name just as firmly as a real directory, and reading it as absent is exactly what produces a
silent loss.

The precedent is `scripts/install_skill_bundle.py`, which classifies an entry it does not own
at a managed path as `foreign` and **preserves** it rather than replacing it. That makes
coexistence the default in one direction — a foreign entry survives this bundle's install.
The precheck covers the direction that classifier structurally cannot see: a foreign entry
that took a name *first* blocks the entry that wanted it, from the other side, with no error
for the operator to notice.

## Invocation

Dry run is the default and prints exactly what will run, from where, at what version, and how
many skills it adds. `--yes` is required to invoke anything.

```bash
mise run libraries:install -- mattpocock            # prints the plan, runs nothing
mise run libraries:install -- mattpocock --yes      # invokes the front door
mise run libraries:install -- ecc --acknowledge-ecc-surface --names-from /tmp/ecc-names.txt
```

Enumerate a library's names with the command `libraries:list` prints for it, never by
guessing. `uninstall` runs the library's own documented removal path or refuses; it never
deletes a path it did not see that library's installer create. ECC has no wired uninstall
because its own path is repo-local and needs a clone.

## Standing boundaries

- **This bundle never vendors upstream bytes.** No file from any library is copied into this
  repository, under any name, at any time.
- **No credential handling.** No token is read, written, stored, forwarded, or accepted as an
  argument. A front door needing one is authenticated separately by the operator.
- **No network trust claim.** The tool makes no request of its own. The front-door subprocess
  does, under its own package manager's integrity model. Nothing here verifies a tarball, a
  signature, or a transitive dependency.
- **No new bootstrap prerequisite.** Front doors use tools that are already present or
  already pinned (`uv`); the tool installs no tool of its own and refuses by name when one is
  missing. `mise run check` stays green on a host that has never run any of these tasks.
- **Installing is not endorsing.** A listed library is reachable, not recommended. Licence,
  provenance, and content review remain the operator's.
- **A successful install is evidence, not authorization.** It authorizes no push, no
  publication, no merge, no deployment, and no further install.

## Cross-links

- `references/library-front-doors.md` — the per-library front door with the exact doc line it
  came from, the version facts, and the enumeration command for each surface.
- `references/collision-precheck.md` — the name-collision rules, the installer-ownership
  precedent they build on, and what each refusal means.
- The `agentic-sdlc` skill's `skill-authoring` reference — owns whether a skill should exist
  in **this** bundle, and the adapted-reference path for a foreign idea. This skill never
  admits anything to this repository; that file never installs anything into a home.
- `docs/adr/0009-external-skill-libraries-are-opt-in-through-their-own-front-doors.md` — the
  decision and its evidence.
- `docs/adr/0002-mise-is-the-single-front-door.md` — the prerequisite rule these front doors
  must not raise.
