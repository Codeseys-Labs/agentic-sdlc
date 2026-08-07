#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install a named third-party skill library through that library's OWN front door.

This is an explicit, separate operation. `bundle:install`, `bundle:install:claude`,
`bundle:install:codex`, `setup`, and every gate leaf reach none of these verbs, and this
module is imported by nothing in the install path. Adding a library to an agent's
always-loaded selection surface is the operator's decision, taken once, in the open.

The distinction that makes this safe: **invoking a third party's own installer is not
vendoring.** No bytes from any library land in this repository, so no `NOTICE` donor
obligation attaches and no upstream licence text travels with anything here. What the
libraries write, they write into the operator's own home, under their own names, by their
own code. This module only decides *whether to run their front door*, prints exactly what
that would do, and refuses when the result would collide.

Two costs survive that distinction, and they are the whole reason this module exists:

1. **Selection-surface pressure.** Every skill a library adds is a row an agent must reason
   over on every turn it selects a skill. One library here declares 284 of them.
2. **Name collision.** A skill name is a single flat namespace per home. Whoever writes a
   name first holds it, and the loser's entry is silently not the one that loads.

What this deliberately does NOT do:

- **No credential handling.** No token is read, written, stored, forwarded, or accepted as
  an argument. A front door that needs one is the operator's to authenticate separately.
- **No network trust claim.** This module makes no network request of its own; the front
  door subprocess does, under its own package manager's integrity model. Nothing here
  verifies a tarball, a signature, or a transitive dependency, and nothing here should be
  read as having done so.
- **No ownership of foreign files.** Anything a library writes belongs to that library.
  `uninstall` runs the library's own documented removal path or refuses; it never deletes a
  path this module did not see the library's own installer create.
- **Installing is not endorsing.** A library listed here is reachable, not recommended.
  Licence, provenance, and content review remain the operator's.
- **A successful install is evidence, not authorization.** It authorizes no push, no
  publication, no merge, no deployment, and no further install.

Precedent for the ownership model: `scripts/install_skill_bundle.py` classifies an entry it
does not own at a managed path as `foreign` and **preserves** it rather than replacing it
(see `container_status` / `artifact_payload_status`). That makes coexistence the default in
one direction — a foreign entry survives this bundle's install. This module covers the
reverse direction, which that classifier cannot: a foreign entry that *takes a name first*
blocks the entry that wanted it, silently and from the other side. Refusing the colliding
library up front is the only place that failure can be caught.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import subprocess
import sys


class ExternalLibraryError(RuntimeError):
    """A fail-closed refusal with a named reason."""


@dataclass(frozen=True)
class Library:
    """A third-party skill library, its front door, and its measured cost.

    Every field is evidence re-read from the library's own repository or registry, not
    inferred. `names` is the exact set the library will write; an empty `names` means the
    surface could not be enumerated offline, which is a refusal rather than a guess.
    """

    key: str
    origin: str
    licence: str
    version: str
    # Where the library's entries land, which decides what a collision even means:
    #   "home-skills" -> one flat directory per name, first writer holds the name.
    #   "plugin"      -> plugin-namespaced, so a bare-name clash duplicates rather than blocks.
    channel: str
    front_door: tuple[str, ...]
    front_door_source: str
    requires: tuple[str, ...]
    names: tuple[str, ...] = ()
    catalog_size: int = 0
    enumeration: str = ""
    uninstall: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    blocked: str = ""
    acknowledgement: str = ""
    extra_agents: tuple[str, ...] = field(default_factory=tuple)
    # A prefix every name this library writes carries. Where one exists, an occupied name
    # under it is attributable to this library's own earlier install, so the precheck reads
    # it as a reinstall rather than as a foreign occupant. Attribution by name shape is an
    # inference from the naming scheme, never a provenance claim about the bytes on disk.
    name_prefix: str = ""

    @property
    def surface(self) -> int:
        return self.catalog_size or len(self.names)

    def owns(self, name: str) -> bool:
        return bool(self.name_prefix) and name.startswith(self.name_prefix)


# ---------------------------------------------------------------------------
# Verified library facts. Re-read each library's own docs before editing a row:
# a guessed flag is worse than a gap, because a guess runs.
# ---------------------------------------------------------------------------

MATTPOCOCK = Library(
    key="mattpocock",
    origin="https://github.com/mattpocock/skills",
    licence="MIT",
    version="1.2.3",
    channel="plugin",
    # README "Installation (30-second setup)" -> "Claude Code": `claude plugins install
    # mattpocock-skills`. The same section states it is already in the official marketplace,
    # so there is deliberately no `marketplace add` step here to add.
    front_door=("claude", "plugins", "install", "mattpocock-skills"),
    front_door_source="mattpocock/skills README, 'Installation (30-second setup)' -> Claude Code",
    requires=("claude",),
    # .claude-plugin/plugin.json `skills`, 25 entries, basenames in declared order.
    names=(
        "ask-matt",
        "diagnosing-bugs",
        "grill-with-docs",
        "triage",
        "improve-codebase-architecture",
        "setup-matt-pocock-skills",
        "tdd",
        "to-spec",
        "to-tickets",
        "wayfinder",
        "implement",
        "prototype",
        "research",
        "domain-modeling",
        "codebase-design",
        "code-review",
        "resolving-merge-conflicts",
        "wizard",
        "grill-me",
        "grilling",
        "handoff",
        "teach",
        "to-questionnaire",
        "wait-what",
        "writing-for-agents",
    ),
    enumeration=(
        "gh api repos/mattpocock/skills/contents/.claude-plugin/plugin.json "
        "--jq '.content' | base64 -d"
    ),
    uninstall=("claude", "plugins", "uninstall", "mattpocock-skills"),
    notes=(
        "Cheapest of the three by an order of magnitude: 25 entries, versioned, with a"
        " read-only managed update path.",
        "Plugin-namespaced, so a bare-name clash duplicates a capability rather than"
        " blocking an install. Its own README names that hazard: 'Pick one — installing"
        " both leaves you with every skill twice.'",
        "The editable alternative front door is `npx skills@latest add mattpocock/skills`,"
        " which writes flat files the operator owns. It is NOT wired here: it is the"
        " channel that competes for flat names, and it prompts interactively for which"
        " skills and which agents to take.",
        "Its own post-install step is `/setup-matt-pocock-skills`, once per repository.",
    ),
)

ECC = Library(
    key="ecc",
    origin="https://github.com/affaan-m/ECC",
    licence="MIT",
    version="2.1.0",
    channel="home-skills",
    # README "Guided setup (recommended)" -> `npx ecc-universal setup`.
    front_door=("npx", "ecc-universal", "setup"),
    front_door_source="affaan-m/ECC README, 'Install ECC' -> 'Guided setup (recommended)'",
    requires=("npx",),
    # 284 directories under skills/. Deliberately NOT embedded: the list is large, it moves,
    # and a stale embedded copy would make the precheck confidently wrong. Supply it with
    # --names-from instead, which is why this row is blocked rather than merely warned about.
    names=(),
    catalog_size=284,
    enumeration="gh api repos/affaan-m/ECC/contents/skills --paginate --jq '.[].name'",
    uninstall=(),
    notes=(
        "The headline cost. Self-reported as 284 skills, 67 agents, and 94 command shims"
        " against this bundle's 9 skills.",
        "Its manual install writes each skill flat to `~/.claude/skills/<skill-name>/` —"
        " the same single namespace this bundle's own entries occupy, so every one of the"
        " 284 names is a first-writer-wins claim.",
        "Its README warns against stacking install methods: 'Installing ECC twice into the"
        " same harness can duplicate skills, commands, hooks, or configuration.'",
        "Uninstall is repo-local (`node scripts/uninstall.js --dry-run`, then without the"
        " flag) and requires a clone, so no uninstall front door is wired here.",
    ),
    blocked=(
        "two independent unresolved facts. (1) Version: ECC's own README requires"
        " `ecc-universal` 2.2.0 or newer for the guided commands, and the npm `latest`"
        " dist-tag serves 2.1.0 — the documented front door is newer than the published"
        " artifact, so `setup` is not known to exist in what npm would fetch. (2) Surface:"
        " 284 names cannot be enumerated without network, so the collision precheck cannot"
        " run and would have to be skipped rather than passed"
    ),
    acknowledgement=(
        "ECC adds 284 entries to an always-loaded selection surface. Pass --acknowledge-ecc-surface"
        " together with --names-from <file> (see the enumeration command in `list`) to proceed"
    ),
)

HYPERRESEARCH = Library(
    key="hyperresearch",
    origin="https://github.com/jordan-gibbs/hyperresearch",
    licence="MIT",
    version="0.10.0",
    channel="home-skills",
    # PyPI README documents `pip install hyperresearch && hyperresearch install`. uv is
    # already a pinned tool in this repo, so `uv tool install` is used instead of pip: it
    # adds no prerequisite (ADR-0002) and keeps the CLI off the ambient interpreter.
    front_door=("uv", "tool", "install", "hyperresearch"),
    front_door_source="hyperresearch PyPI README, 'Install'; uv substituted for pip per ADR-0002",
    requires=("uv",),
    names=(
        "hyperresearch",
        "hyperresearch-1-decompose",
        "hyperresearch-2-width-sweep",
        "hyperresearch-3-contradiction-graph",
        "hyperresearch-4-loci-analysis",
        "hyperresearch-5-depth-investigation",
        "hyperresearch-6-cross-locus-reconcile",
        "hyperresearch-7-source-tensions",
        "hyperresearch-8-corpus-critic",
        "hyperresearch-9-evidence-digest",
        "hyperresearch-10-triple-draft",
        "hyperresearch-11-synthesize",
        "hyperresearch-12-critics",
        "hyperresearch-13-gap-fetch",
        "hyperresearch-14-patcher",
        "hyperresearch-15-polish",
        "hyperresearch-16-readability-audit",
    ),
    extra_agents=(
        "hyperresearch-corpus-critic",
        "hyperresearch-depth-critic",
        "hyperresearch-depth-investigator",
        "hyperresearch-dialectic-critic",
        "hyperresearch-draft-orchestrator",
        "hyperresearch-fetcher",
        "hyperresearch-instruction-critic",
        "hyperresearch-loci-analyst",
        "hyperresearch-patcher",
        "hyperresearch-polish-auditor",
        "hyperresearch-readability-recommender",
        "hyperresearch-source-analyst",
        "hyperresearch-synthesizer",
        "hyperresearch-width-critic",
    ),
    enumeration="hyperresearch install --help  # --global writes the entry skill + agents to ~/.claude/",
    uninstall=("uv", "tool", "uninstall", "hyperresearch"),
    name_prefix="hyperresearch",
    notes=(
        "NOT a skill library: it is a CLI that RENDERS skills and agents into a home or a"
        " project at install time. Installing the tool writes nothing; its own"
        " `hyperresearch install` verb does.",
        "Every name it writes is `hyperresearch`-prefixed, so its collision surface against"
        " this bundle is structurally empty rather than merely observed to be empty.",
        "Its rendered agent files carry static `model:` frontmatter, which"
        " `scripts/validate_bundle.py` rejects for agent files. That is a reason never to"
        " vendor its output; it is not a reason not to run its renderer in a home, where"
        " this repository's validator has no jurisdiction.",
        "`uv tool uninstall` removes the CLI only. Files its `install` verb already"
        " rendered into a home or project stay where they are, by design.",
    ),
)

LIBRARIES: dict[str, Library] = {
    library.key: library for library in (MATTPOCOCK, ECC, HYPERRESEARCH)
}


@dataclass(frozen=True)
class Config:
    repo_root: Path
    home: Path
    assume_yes: bool = False
    acknowledge_ecc_surface: bool = False
    allow_duplicate_channel: bool = False
    names_from: Path | None = None

    @property
    def skills_dir(self) -> Path:
        return self.home / ".claude" / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.home / ".claude" / "agents"

    @property
    def plugins_state(self) -> Path:
        return self.home / ".claude" / "plugins" / "installed_plugins.json"


def absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(os.fspath(path))))


def bundle_skill_names(repo_root: Path) -> tuple[str, ...]:
    """This bundle's own skill names, discovered the way the installer discovers them."""
    return tuple(
        sorted(skill.parent.name for skill in (repo_root / "skills").glob("*/SKILL.md"))
    )


def present_names(directory: Path) -> tuple[str, ...]:
    """Entry names already occupying a home directory, links included.

    A symlink counts. An entry another installer symlinked into place holds the name just
    as firmly as a real directory does, and treating it as absent is exactly the mistake
    that produces a silent loss.
    """
    if not directory.is_dir():
        return ()
    try:
        return tuple(sorted(entry.name for entry in directory.iterdir()))
    except OSError as exc:
        raise ExternalLibraryError(f"cannot inspect {directory}: {exc}") from exc


def describe_occupant(directory: Path, name: str) -> str:
    path = directory / name
    if path.is_symlink():
        try:
            return f"link -> {os.readlink(path)}"
        except OSError:
            return "link"
    return "directory" if path.is_dir() else "file"


def load_names_override(path: Path) -> tuple[str, ...]:
    """Read an operator-supplied name list produced by a library's own enumeration."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExternalLibraryError(f"cannot read name list {path}: {exc}") from exc
    names = tuple(
        sorted({line.strip().strip('",') for line in text.splitlines() if line.strip()})
    )
    if not names:
        raise ExternalLibraryError(f"name list is empty: {path}")
    return names


@dataclass(frozen=True)
class Precheck:
    library: Library
    names: tuple[str, ...]
    bundle_collisions: tuple[str, ...]
    home_collisions: tuple[tuple[str, str], ...]
    new_names: tuple[str, ...]
    reinstalls: tuple[str, ...] = ()
    refusal: str = ""

    @property
    def refused(self) -> bool:
        return bool(self.refusal)


def precheck(library: Library, config: Config) -> Precheck:
    """Compare what a library will write against what already holds those names.

    Refuses on the library's own recorded blockers first, then on an unenumerable surface,
    then on a collision with a name this bundle installs. A collision inside the operator's
    home is reported but does not by itself refuse a plugin-channel library, because a
    plugin does not compete for the flat namespace.
    """
    names = library.names
    if config.names_from is not None:
        names = load_names_override(config.names_from)

    if library.blocked and not (
        library.key == "ecc" and config.acknowledge_ecc_surface and config.names_from
    ):
        reason = library.blocked
        if library.acknowledgement:
            reason = f"{reason}. {library.acknowledgement}"
        return Precheck(library, names, (), (), (), refusal=reason)

    if not names:
        return Precheck(
            library,
            names,
            (),
            (),
            (),
            refusal=(
                f"the {library.surface} names {library.key} writes could not be enumerated"
                " offline, so the collision precheck cannot run. Enumerate them with the"
                " command shown by `list`, then pass --names-from <file>"
            ),
        )

    bundle = set(bundle_skill_names(config.repo_root))
    occupied = set(present_names(config.skills_dir))
    bundle_collisions = tuple(sorted(name for name in names if name in bundle))
    # An occupied name under the library's own prefix is its own earlier install being
    # refreshed. Counting that as a collision would refuse every upgrade.
    reinstalls = tuple(
        sorted(name for name in names if name in occupied and library.owns(name))
    )
    home_collisions = tuple(
        (name, describe_occupant(config.skills_dir, name))
        for name in names
        if name in occupied and not library.owns(name)
    )
    new_names = tuple(sorted(name for name in names if name not in occupied))

    refusal = ""
    if bundle_collisions:
        refusal = (
            f"{len(bundle_collisions)} name(s) collide with skills this bundle installs:"
            f" {', '.join(bundle_collisions)}. Whichever installer writes a name first holds"
            " it, and the other entry silently is not the one that loads"
        )
    elif library.channel == "home-skills" and home_collisions:
        refusal = (
            f"{len(home_collisions)} name(s) are already occupied in {config.skills_dir}"
            f" by something this library did not write, and it writes flat into that"
            f" directory: {', '.join(name for name, _ in home_collisions)}"
        )
    elif home_collisions and not config.allow_duplicate_channel:
        # A plugin channel cannot lose a name, so this is not a blocked install — it is a
        # doubled capability, which upstream names as its own failure mode. Refusing is the
        # only point at which it is still cheap to notice.
        refusal = (
            f"{len(home_collisions)} of this library's {len(names)} skill name(s) are"
            f" already present in {config.skills_dir} through a different channel, so"
            " installing the plugin would load the same capability twice. Upstream's own"
            " README: 'Pick one — installing both leaves you with every skill twice.'"
            " Remove the other channel's copies first, or pass"
            " --allow-duplicate-channel to accept the duplication deliberately"
        )
    return Precheck(
        library,
        names,
        bundle_collisions,
        home_collisions,
        new_names,
        reinstalls,
        refusal,
    )


def front_door_available(library: Library) -> str:
    missing = [tool for tool in library.requires if shutil.which(tool) is None]
    return ", ".join(missing)


def render_plan(check: Precheck, config: Config) -> list[str]:
    """Print exactly what will run, from where, at what version, and at what cost."""
    library = check.library
    lines = [
        f"library:      {library.key}",
        f"origin:       {library.origin}",
        f"licence:      {library.licence} (upstream's own; no bytes enter this repository)",
        f"version:      {library.version}",
        f"front door:   {' '.join(library.front_door)}",
        f"  documented: {library.front_door_source}",
        f"working dir:  {config.repo_root}",
        f"writes to:    {config.skills_dir}"
        if library.channel == "home-skills"
        else f"writes to:    {config.home / '.claude' / 'plugins'} (plugin-namespaced)",
    ]
    surface = f"adds {library.surface} skill(s) to the selection surface"
    if library.extra_agents:
        surface += f" and {len(library.extra_agents)} agent file(s)"
    lines.append(f"cost:         {surface}")
    if check.names:
        detail = (
            f"of those:     {len(check.new_names)} name(s) not currently present,"
            f" {len(check.home_collisions)} occupied by another writer"
        )
        if check.reinstalls:
            detail += f", {len(check.reinstalls)} its own prior install"
        lines.append(detail)
    missing = front_door_available(library)
    lines.append(
        f"front-door tool: {'MISSING -> ' + missing if missing else 'present'}"
    )
    for note in library.notes:
        lines.append(f"note:         {note}")
    if library.uninstall:
        lines.append(f"uninstall:    {' '.join(library.uninstall)}")
    else:
        lines.append(
            "uninstall:    none wired; upstream's removal path needs a clone of its"
            " repository"
        )
    return lines


def report_collisions(check: Precheck, config: Config) -> list[str]:
    lines: list[str] = []
    for name, kind in check.home_collisions:
        lines.append(f"  occupied: {name} ({kind})")
    if check.bundle_collisions:
        lines.append(
            f"  collides with this bundle: {', '.join(check.bundle_collisions)}"
        )
    return lines


def command_list(config: Config) -> tuple[int, list[str]]:
    bundle = bundle_skill_names(config.repo_root)
    occupied = present_names(config.skills_dir)
    lines = [
        "External skill libraries reachable through their own front doors.",
        "Nothing below is installed by `bundle:install`, `setup`, or any gate.",
        "",
        f"this bundle installs {len(bundle)} skill(s): {', '.join(bundle)}",
        f"{config.skills_dir} currently holds {len(occupied)} entr(ies)",
        "",
    ]
    for library in LIBRARIES.values():
        check = precheck(library, config)
        state = "blocked" if check.refused else "installable"
        detected = detect(library, config)
        lines.append(f"{library.key}  [{state}]  detected: {detected}")
        lines.extend(f"  {line}" for line in render_plan(check, config))
        if library.enumeration:
            lines.append(f"  enumerate:    {library.enumeration}")
        if check.refused:
            lines.append(f"  REFUSED:      {check.refusal}")
        lines.append("")
    lines.append(
        "Installing is not endorsing, and a successful install is evidence, not"
        " authorization."
    )
    return 0, lines


def detect(library: Library, config: Config) -> str:
    """Report whether a library's entries are already present, without networking."""
    if library.channel == "plugin":
        state = config.plugins_state
        if state.is_file():
            try:
                if "mattpocock-skills" in state.read_text(encoding="utf-8"):
                    return "plugin recorded installed"
            except OSError:
                return "unknown (plugin state unreadable)"
        occupied = set(present_names(config.skills_dir))
        overlap = [name for name in library.names if name in occupied]
        if overlap:
            return (
                f"{len(overlap)}/{len(library.names)} of its skill names already occupied"
                " by another channel"
            )
        return "not detected"
    occupied = set(present_names(config.skills_dir))
    names = library.names
    if not names:
        return "unknown (surface not enumerable offline)"
    overlap = [name for name in names if name in occupied]
    if len(overlap) == len(names):
        return f"all {len(names)} skill name(s) present"
    if overlap:
        return f"{len(overlap)}/{len(names)} skill name(s) present"
    return "not detected"


def command_status(config: Config) -> tuple[int, list[str]]:
    lines = [f"home: {config.home}", ""]
    for library in LIBRARIES.values():
        lines.append(f"{library.key}: {detect(library, config)}")
        if library.extra_agents:
            present = set(present_names(config.agents_dir))
            found = [
                name for name in library.extra_agents if f"{name}.md" in present or name in present
            ]
            lines.append(
                f"  agents: {len(found)}/{len(library.extra_agents)} present in"
                f" {config.agents_dir}"
            )
    lines.append("")
    lines.append("Detection reads the filesystem only. It proves presence, not provenance.")
    return 0, lines


def run_front_door(command: tuple[str, ...], config: Config) -> tuple[int, list[str]]:
    try:
        completed = subprocess.run(
            list(command),
            cwd=config.repo_root,
            check=False,
        )
    except OSError as exc:
        raise ExternalLibraryError(
            f"front door failed to start ({' '.join(command)}): {exc}"
        ) from exc
    if completed.returncode != 0:
        return completed.returncode, [
            f"front door exited {completed.returncode}: {' '.join(command)}",
            "Nothing here retries. A network failure, an authentication prompt, and a"
            " refused install are different causes with the same exit code; read the"
            " front door's own output above.",
        ]
    return 0, [f"front door completed: {' '.join(command)}"]


def command_install(keys: list[str], config: Config) -> tuple[int, list[str]]:
    if not keys:
        raise ExternalLibraryError(
            "name at least one library. There is deliberately no verb that installs every"
            " library at once"
        )
    unknown = [key for key in keys if key not in LIBRARIES]
    if unknown:
        raise ExternalLibraryError(
            f"unknown librar(ies): {', '.join(unknown)}."
            f" Known: {', '.join(LIBRARIES)}"
        )
    lines: list[str] = []
    failed = False
    for key in keys:
        library = LIBRARIES[key]
        check = precheck(library, config)
        lines.append(f"=== {key} ===")
        lines.extend(render_plan(check, config))
        lines.extend(report_collisions(check, config))
        if check.refused:
            failed = True
            lines.append(f"REFUSED: {check.refusal}")
            lines.append("")
            continue
        missing = front_door_available(library)
        if missing:
            failed = True
            lines.append(
                f"REFUSED: front-door tool not found on PATH: {missing}. This module"
                " installs no tool of its own"
            )
            lines.append("")
            continue
        if not config.assume_yes:
            lines.append(
                "DRY RUN: nothing was run. Re-run with --yes to invoke the front door"
                " above."
            )
            lines.append("")
            continue
        code, output = run_front_door(library.front_door, config)
        lines.extend(output)
        if code:
            failed = True
        lines.append("")
    if not config.assume_yes:
        lines.append(
            "Dry run is the default. No library was installed and no command was run."
        )
    return (1 if failed else 0), lines


def command_uninstall(keys: list[str], config: Config) -> tuple[int, list[str]]:
    if not keys:
        raise ExternalLibraryError("name at least one library to uninstall")
    unknown = [key for key in keys if key not in LIBRARIES]
    if unknown:
        raise ExternalLibraryError(f"unknown librar(ies): {', '.join(unknown)}")
    lines: list[str] = []
    failed = False
    for key in keys:
        library = LIBRARIES[key]
        lines.append(f"=== {key} ===")
        if not library.uninstall:
            failed = True
            lines.append(
                "REFUSED: no uninstall front door is wired for this library. Its own"
                " removal path is the only supported one, and this module never deletes a"
                " path it did not see that path's own installer create."
            )
            lines.append("")
            continue
        missing = front_door_available(library)
        if missing:
            failed = True
            lines.append(f"REFUSED: front-door tool not found on PATH: {missing}")
            lines.append("")
            continue
        lines.append(f"would run: {' '.join(library.uninstall)}")
        lines.append(
            "scope: only what the library's own uninstall path removes. Files it rendered"
            " into a home or a project earlier are not this module's to delete."
        )
        if not config.assume_yes:
            lines.append("DRY RUN: nothing was run. Re-run with --yes.")
            lines.append("")
            continue
        code, output = run_front_door(library.uninstall, config)
        lines.extend(output)
        if code:
            failed = True
        lines.append("")
    return (1 if failed else 0), lines


def parse_args(argv: list[str]) -> argparse.Namespace:
    # Shared options are attached to the top-level parser AND to every subparser, with
    # SUPPRESS defaults so a value given before the verb is not clobbered by a subparser's
    # own default. Without this, `install mattpocock --yes` is an "unrecognized arguments"
    # error and `--yes install mattpocock` silently reverts to a dry run.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--home", type=Path, default=argparse.SUPPRESS)
    common.add_argument(
        "--yes",
        action="store_true",
        default=argparse.SUPPRESS,
        help="actually invoke the front door printed by the dry run",
    )
    common.add_argument(
        "--acknowledge-ecc-surface",
        action="store_true",
        default=argparse.SUPPRESS,
        help="acknowledge that ECC adds 284 entries to an always-loaded selection surface",
    )
    common.add_argument(
        "--allow-duplicate-channel",
        action="store_true",
        default=argparse.SUPPRESS,
        help="proceed when another channel already provides the same skill names",
    )
    common.add_argument(
        "--names-from",
        type=Path,
        default=argparse.SUPPRESS,
        help="file of skill names a library will write, one per line, from its own enumeration",
    )
    parser = argparse.ArgumentParser(
        prog="install_external_libraries.py",
        parents=[common],
        description=(
            "Install a named third-party skill library through its own front door."
            " Dry run by default; never invoked by bundle:install or setup."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "list", parents=[common], help="what is available, its front door, and its cost"
    )
    install = subparsers.add_parser(
        "install", parents=[common], help="install explicitly named libraries"
    )
    install.add_argument("libraries", nargs="*")
    subparsers.add_parser(
        "status", parents=[common], help="what is already present in the target home"
    )
    uninstall = subparsers.add_parser(
        "uninstall", parents=[common], help="run a library's own removal path"
    )
    uninstall.add_argument("libraries", nargs="*")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    names_from = getattr(args, "names_from", None)
    config = Config(
        repo_root=Path(__file__).resolve().parents[1],
        home=absolute(getattr(args, "home", None) or Path.home()),
        assume_yes=getattr(args, "yes", False),
        acknowledge_ecc_surface=getattr(args, "acknowledge_ecc_surface", False),
        allow_duplicate_channel=getattr(args, "allow_duplicate_channel", False),
        names_from=absolute(names_from) if names_from else None,
    )
    try:
        if args.command == "list":
            code, messages = command_list(config)
        elif args.command == "status":
            code, messages = command_status(config)
        elif args.command == "install":
            code, messages = command_install(args.libraries, config)
        else:
            code, messages = command_uninstall(args.libraries, config)
    except ExternalLibraryError as exc:
        print(f"fatal: {exc}", file=sys.stderr)
        return 2
    for message in messages:
        print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
