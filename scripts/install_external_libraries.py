#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install a named third-party skill library through that library's OWN front door.

This is an explicit, separate operation. `bundle:install`, `bundle:install:claude`,
`bundle:install:codex`, `contributor:setup`, its deprecated `setup` forwarder, and every gate
leaf reach none of these verbs, and this module is imported by nothing in the install path.
Adding a library to an agent's
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
- **No deletion, ever, by this module.** `migrate` de-duplicates a name held by a *different
  channel serving the same upstream*, and it does so by invoking that channel's own `remove`
  front door. There is no `rm` here, no `unlink`, and no path this module touches directly. A
  name it cannot prove is the same upstream — from that channel's own lock file — is left
  exactly where it is.
- **No door it did not evaluate.** Where a library has a second legitimate front door in a
  different channel, that door is PRINTED with its exact command, its observed grammar, and its
  prerequisite — never invoked. The collision precheck that ran belongs to the channel of the
  door this module runs; installing through the other one would install behind a precheck that
  never looked at its namespace.
- **Installing is not endorsing.** A library listed here is reachable, not recommended.
  Licence, provenance, and content review remain the operator's.
- **A successful install is evidence, not authorization.** It authorizes no push, no
  publication, no merge, no deployment, and no further install.

Exit codes distinguish *describing* from *doing*, because a dry run and a real install are
different operations that were previously sharing one exit path:

- **0** — the operation did what it was asked to do. For a dry run that includes describing a
  refusal: "these 21 names are occupied", or "`claude` is not on PATH, so a real install would
  refuse". The description is the deliverable, and it succeeded. Nothing ran, nothing changed,
  and the reason is on stdout.
- **1** — a real (`--yes`) operation was asked to change something and could not: a refused
  precheck, a missing front-door tool, or a front door that exited nonzero.
- **2** — the invocation itself was unusable: no library named, an unknown library, an
  unreadable name list. That is a usage error rather than a description or an attempt.

The practical consequence is that `install <lib>` without `--yes` exits 0 on any machine,
including one with no `claude`, no `npx`, and no installed tools, because "the front door is
missing" is a fact it reports rather than a failure it suffered. Reading a nonzero dry-run exit
as "the tool broke" was the confusion this split removes.

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
import json
import os
from pathlib import Path
import shlex
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
    # An unresolved *fact* that makes a library unsafe to run at all — not a cost, and not
    # overridable by any flag. No row currently sets this: ECC's version gap used to, and the
    # operator accepted that gap, so it moved to `caveats`. The mechanism stays because the
    # next library that cannot be honestly run needs somewhere to say so, and the difference
    # between "expensive" (acknowledgement) and "unsafe" (blocked) must not collapse.
    blocked: str = ""
    # A COST the operator can accept with an explicit flag. Never an unresolved fact.
    acknowledgement: str = ""
    extra_agents: tuple[str, ...] = field(default_factory=tuple)
    # A prefix every name this library writes carries. Where one exists, an occupied name
    # under it is attributable to this library's own earlier install, so the precheck reads
    # it as a reinstall rather than as a foreign occupant. Attribution by name shape is an
    # inference from the naming scheme, never a provenance claim about the bytes on disk.
    name_prefix: str = ""
    # The exact `source` string a competing channel's own lock file records for this same
    # upstream. This is the ONLY thing that licenses a migration: a name occupied by a
    # different channel serving the *same* upstream is de-duplication, and a name occupied by
    # anything else is a foreign entry that stays where it is. A library with no value here
    # can never be migrated, because there is nothing to prove sameness against.
    lock_source: str = ""
    lock_source_url: str = ""
    # The observed grammar of a SECOND, independent front door that reaches the same upstream
    # without an authenticated Claude Code session. Empty means this library has one door only.
    # The package spec that door takes is `lock_source`, reused rather than duplicated so the two
    # cannot drift apart: the `skills` CLI's own lock records exactly the string its `add` accepts.
    cli_alternative: str = ""
    # Caveats that survive an accepted install: recorded, printed, and never silently dropped.
    caveats: tuple[str, ...] = field(default_factory=tuple)

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
    # mattpocock-skills`. The same section states it is already in the official marketplace, so
    # there is no `marketplace add` step here to add — but "already listed" is only true of an
    # AUTHENTICATED session. Executed 2026-08-20 on a logged-out Claude Code 2.1.238:
    # `claude plugin marketplace list` prints "No marketplaces configured" (exit 0) and this
    # front door fails not-found-in-any-configured-marketplace. `claude plugin|plugins` are the
    # same command, so the plural spelling here is the CLI's own alias, not a guess.
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
    # What `npx skills` records for this same upstream, read from a real lock file rather than
    # assumed: source "mattpocock/skills", sourceUrl the .git clone URL.
    lock_source="mattpocock/skills",
    lock_source_url="https://github.com/mattpocock/skills.git",
    # Observed by running the CLI itself, not read from a README. `npx -y skills@latest --help`
    # (skills CLI 1.5.23, executed 2026-08-20 in a container with no Claude Code login) prints
    # `add <package>` under "Manage Skills", and under "Add Options": `-g, --global`,
    # `-a, --agent <agents>`, `-s, --skill <skills>` ("use '*' for all skills"), `-y, --yes`.
    # There is no per-subcommand help — `add --help` reprints the same page — so that page is
    # the whole grammar this door is built from.
    cli_alternative=(
        "`npx -y skills@latest --help` (skills CLI 1.5.23): `add <package>` with Add Options"
        " -g/--global, -a/--agent <agents>, -s/--skill <skills>, -y/--yes"
    ),
    notes=(
        "Cheapest of the three by an order of magnitude: 25 entries, versioned, with a"
        " read-only managed update path.",
        "Plugin-namespaced, so a bare-name clash duplicates a capability rather than"
        " blocking an install. Its own README names that hazard: 'Pick one — installing"
        " both leaves you with every skill twice.'",
        "TWO doors, and they differ in what they need rather than in what they fetch. The"
        " marketplace door above needs an authenticated Claude Code session; the `skills` CLI"
        " door needs none. The CLI door is PRINTED, never invoked here: it writes flat names"
        " the operator owns into the same directory this bundle's own entries occupy, so it is"
        " the channel that competes for those names, and the plugin-channel precheck that ran"
        " above is not the flat-channel one that door would need. When that channel already"
        " holds the names, the `migrate` verb retires them through its own `remove` path first.",
        "Its own post-install step is `/setup-matt-pocock-skills`, once per repository.",
    ),
)

ECC = Library(
    key="ecc",
    origin="https://github.com/affaan-m/ECC",
    licence="MIT",
    version="2.1.0",
    channel="home-skills",
    # NOT the README's `npx ecc-universal setup`. That command cannot run: the published
    # 2.1.0 tarball's `bin` map is ecc / ecc-control-pane / ecc-install / ecc-memory-mcp /
    # ecc-plan-canvas, with no `ecc-universal` bin and no `setup` verb anywhere in `ecc`'s
    # command table, so npx exits "could not determine executable to run" regardless of the
    # version gap. `-p ecc-universal ecc` names the package and the real bin separately.
    # `--profile` is mandatory: the CLI refuses with "No install profile, module IDs,
    # included components, or legacy languages were provided" when given none.
    front_door=(
        "npx",
        "-y",
        "-p",
        "ecc-universal",
        "ecc",
        "install",
        "--target",
        "claude",
        "--profile",
        "full",
    ),
    front_door_source=(
        "ecc-universal 2.1.0 published artifact: `ecc --help` command table + `ecc install"
        " --help` usage, verified against the tarball's package.json bin map"
    ),
    requires=("npx",),
    # Deliberately NOT embedded: the list is large, it moves, and a stale embedded copy would
    # make the precheck confidently wrong. Its own front door enumerates it exactly, so
    # --names-from has a real source rather than a guess.
    names=(),
    catalog_size=284,
    # The library's OWN dry run, which lists every destination path it would write. That is a
    # stronger enumeration than a directory listing of the repo: it reflects the resolved
    # profile rather than the whole catalog.
    enumeration=(
        "npx -y -p ecc-universal ecc install --target claude --profile full --dry-run --json"
        " | python3 -c \"import json,re,sys;p=json.load(sys.stdin)['plan'];"
        "print('\\n'.join(sorted({m.group(1) for o in p['operations']"
        " for m in [re.search(r'/[.]claude/skills/([^/]+)/',o['destinationPath'])] if m})))\""
    ),
    # Its own uninstall verb, present in the published artifact and recorded-state scoped.
    uninstall=("npx", "-y", "-p", "ecc-universal", "ecc", "uninstall", "--target", "claude"),
    notes=(
        "The headline cost. Self-reported as 284 skills, 67 agents, and 94 command shims"
        " against this bundle's {bundle_skill_count} skills. A `--profile full --dry-run`"
        " against the published 2.1.0 artifact measures 983 file operations: 280 flat"
        " skill names, 67 agents, 94 commands, 122 rules files, and 170 scripts.",
        "It writes each skill flat to `~/.claude/skills/<skill-name>/` — the same single"
        " namespace this bundle's own entries occupy, so every one of those names is a"
        " first-writer-wins claim.",
        "Its README warns against stacking install methods: 'Installing ECC twice into the"
        " same harness can duplicate skills, commands, hooks, or configuration.' Do not"
        " combine this front door with `/plugin install ecc@ecc`.",
        "`--profile full` is the widest of seven profiles. `ecc catalog profiles --json`"
        " lists the narrower ones (minimal, core, developer, security, research), and"
        " `--profile <name>` on the front door installs a smaller surface for a smaller"
        " cost. Nothing here prefers `full`; it is simply the one whose surface is measured.",
    ),
    # The version gap is an accepted, recorded caveat rather than a refusal (operator
    # decision, ADR-0009 amendment 2026-08-07). It is not silently dropped: it prints in
    # `list`, in every dry run, and before any --yes invocation.
    caveats=(
        "VERSION GAP (accepted): ECC's README documents guided commands requiring"
        " `ecc-universal` 2.2.0 or newer, and npm's `latest` dist-tag serves 2.1.0. The"
        " operator accepted npm `latest`. The README's `npx ecc-universal setup` is NOT the"
        " front door used here, because that bin does not exist in the published 2.1.0"
        " artifact at all; the verified `ecc install` path is used instead. A front-door"
        " failure is therefore reported as a failure and never assumed to be success.",
        "SURFACE (not overruled): 284 declared entries against a selection surface an agent"
        " reasons over on every turn. The --acknowledge-ecc-surface gate stands, because it"
        " is about cost rather than version.",
    ),
    acknowledgement=(
        "ECC adds 284 entries to an always-loaded selection surface. Pass"
        " --acknowledge-ecc-surface to accept that cost. Add --names-from <file> (from the"
        " enumeration command in `list`) to run the collision precheck; without it the"
        " precheck is reported as SKIPPED, never as passed"
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
    # A RECORDED FIXTURE, not a live enumeration, and the difference is why it drifted once
    # already. This front door has no verb that lists what it renders: `hyperresearch --help`
    # at 0.10.0 exposes install/setup/init/status/... and nothing that enumerates agents, and
    # `install --help` has no --dry-run, so there is no offline oracle to derive this from at
    # status time. Recorded by executing `hyperresearch install --global` in a container and
    # listing `~/.claude/agents`: 16 files, hyperresearch v0.10.0, 2026-08-20. It was 14 here
    # against that same 0.10.0 upstream — browser-fetcher and cite-checker were missing, so
    # `status` truthfully reported 14/14 while understating the surface by two files.
    # `tests/test_external_libraries.py` pins this tuple against the same recorded set and
    # names the version, so the next upstream release fails a named test instead of quietly
    # under-reporting; `command_status` additionally reports any prefix-matching agent file this
    # tuple does not name.
    extra_agents=(
        "hyperresearch-browser-fetcher",
        "hyperresearch-cite-checker",
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
        "The agent files are a RECORDED set from an executed 0.10.0 install, not a live"
        " enumeration: this front door exposes no verb that lists what it renders, so `status`"
        " also reports any `hyperresearch`-prefixed agent file the recorded set does not name"
        " rather than counting only what the set already knows about.",
        "Its rendered agent files carry static `model:` frontmatter, which"
        " `scripts/validate_bundle.py` rejects for agent files. That is a reason never to"
        " vendor its output; it is not a reason not to run its renderer in a home, where"
        " this repository's validator has no jurisdiction.",
        "`uv tool uninstall` removes the CLI only. Files its `install` verb already"
        " rendered into a home or project stay where they are, by design.",
    ),
)

# Closed reviewed catalog. A new row is an onboarding decision, not ordinary data entry: ADR-0009
# requires the front door, licence, surface, collision/ownership, credential, and uninstall claims
# to land with coordinated docs and tests. Unknown libraries stay outside every lifecycle verb.
SUPPORTED_LIBRARIES: tuple[Library, ...] = (MATTPOCOCK, ECC, HYPERRESEARCH)
LIBRARIES: dict[str, Library] = {library.key: library for library in SUPPORTED_LIBRARIES}


@dataclass(frozen=True)
class Config:
    repo_root: Path
    home: Path
    assume_yes: bool = False
    acknowledge_ecc_surface: bool = False
    allow_duplicate_channel: bool = False
    names_from: Path | None = None
    state_home: Path | None = None

    @property
    def skills_dir(self) -> Path:
        return self.home / ".claude" / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.home / ".claude" / "agents"

    @property
    def plugins_state(self) -> Path:
        return self.home / ".claude" / "plugins" / "installed_plugins.json"

    @property
    def marketplaces_state(self) -> Path:
        """Where Claude Code records the marketplaces a plugin name can be resolved against.

        Read, never written. This is the offline half of `claude plugin marketplace list`: the
        file is a JSON object keyed by marketplace name, and on a logged-out home it does not
        exist at all, which is the same fact that command reports as "No marketplaces
        configured". Reading it needs no subprocess, no network, and no credential, so the
        empty-marketplace case can be named in a plan rather than only discovered by a failure.
        """
        return self.home / ".claude" / "plugins" / "known_marketplaces.json"

    @property
    def skill_lock(self) -> Path:
        """The competing channel's own lock file, resolved the way that channel resolves it.

        The `skills` CLI reads `$XDG_STATE_HOME/skills/.skill-lock.json` when that variable is
        set and `~/.agents/.skill-lock.json` otherwise. Guessing only the second path would
        make the provenance proof silently unavailable on a host that sets the first, and an
        unavailable proof must refuse rather than fall through to a filesystem guess.
        """
        if self.state_home is not None:
            return self.state_home / "skills" / ".skill-lock.json"
        return self.home / ".agents" / ".skill-lock.json"


# The lock schema version this module knows how to read. The `skills` CLI itself discards a
# lock recording anything lower, so reading one as authoritative would credit provenance to a
# document its own writer considers stale.
SKILL_LOCK_VERSION = 3


@dataclass(frozen=True)
class Provenance:
    """What a competing channel's own lock file says about one occupied name.

    `proven` is true only when that channel recorded this exact name as coming from the
    library's own upstream. Everything else — no lock, an unreadable lock, a lock at an
    unknown schema version, a name absent from it, or a name recorded against a different
    source — is unproven, and unproven means untouched.
    """

    name: str
    proven: bool
    source: str = ""
    source_url: str = ""
    reason: str = ""


def read_skill_lock(config: Config) -> tuple[dict[str, dict], str]:
    """Read the competing channel's lock file. Returns (entries, unavailable_reason).

    Every failure is a *reason*, never an empty dict that reads like "nothing is managed
    there". The difference matters: absent provenance must block a removal, and a silent empty
    result would instead let one proceed.
    """
    path = config.skill_lock
    if not path.is_file():
        return {}, f"no lock file at {path}"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return {}, f"cannot read {path}: {exc}"
    except ValueError as exc:
        return {}, f"{path} is not valid JSON: {exc}"
    if not isinstance(document, dict):
        return {}, f"{path} is not a JSON object"
    version = document.get("version")
    if not isinstance(version, int):
        return {}, f"{path} records no integer schema version"
    if version < SKILL_LOCK_VERSION:
        return {}, (
            f"{path} is at schema version {version}, older than the version"
            f" {SKILL_LOCK_VERSION} this reads; its own writer discards it as stale"
        )
    entries = document.get("skills")
    if not isinstance(entries, dict):
        return {}, f"{path} records no skills object"
    return {
        name: entry for name, entry in entries.items() if isinstance(entry, dict)
    }, ""


def prove_same_upstream(
    library: Library, names: tuple[str, ...], config: Config
) -> tuple[tuple[Provenance, ...], str]:
    """Decide, per name, whether another channel's lock attributes it to the SAME upstream.

    This is the entire licence for a removal. Filesystem presence proves presence, not
    provenance — the precheck says so in as many words — so the *other channel's own record*
    is what is consulted, and a name it does not vouch for is left alone.
    """
    if not library.lock_source:
        return (), (
            f"{library.key} records no competing-channel lock source, so no occupied name"
            " can be proven to be the same upstream"
        )
    entries, unavailable = read_skill_lock(config)
    if unavailable:
        return (), unavailable
    results: list[Provenance] = []
    for name in names:
        entry = entries.get(name)
        if entry is None:
            results.append(
                Provenance(name, False, reason="no entry in the other channel's lock file")
            )
            continue
        source = str(entry.get("source", ""))
        source_url = str(entry.get("sourceUrl", ""))
        if source != library.lock_source:
            results.append(
                Provenance(
                    name,
                    False,
                    source,
                    source_url,
                    reason=(
                        f"lock records source {source!r}, not {library.lock_source!r}"
                    ),
                )
            )
            continue
        # Where the library records a clone URL too, both must agree. A matching short name
        # with a different URL is a different repository wearing the same label.
        if library.lock_source_url and source_url != library.lock_source_url:
            results.append(
                Provenance(
                    name,
                    False,
                    source,
                    source_url,
                    reason=(
                        f"lock records sourceUrl {source_url!r}, not"
                        f" {library.lock_source_url!r}"
                    ),
                )
            )
            continue
        results.append(Provenance(name, True, source, source_url))
    return tuple(results), ""


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


def expected_agent_files(library: Library) -> frozenset[str]:
    """Every directory entry that counts as one of a library's recorded agent entries.

    Both spellings are accepted because `present_names` reports whatever the directory holds: the
    rendered `<name>.md` file, and a bare `<name>` for a layout that uses directories. This is
    the set a prefix-matching entry is measured against to detect upstream drift.
    """
    return frozenset(library.extra_agents) | frozenset(
        f"{name}.md" for name in library.extra_agents
    )


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
    # True when the surface could not be enumerated and the operator accepted proceeding
    # anyway. A skipped precheck is NOT a passed one, and every renderer must say which it
    # was; this flag exists so nothing can print the two the same way.
    skipped: bool = False
    skipped_reason: str = ""
    # Set when the only thing standing between this library and its install is a set of names
    # another channel holds for the same upstream. That is the migration path, and naming it
    # here is what keeps `list` from reporting a dead end.
    migratable: tuple[str, ...] = ()
    # True when the refusal is the plugin-channel duplication one, which --allow-duplicate-channel
    # always clears. Tracked separately from `migratable` because a partly-unprovable occupancy
    # cannot be migrated but is still reachable that way, and reporting it as a dead end would be
    # wrong in exactly the case the operator asked not to be a dead end.
    duplicate_channel: bool = False

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

    if library.blocked:
        reason = library.blocked
        if library.acknowledgement:
            reason = f"{reason}. {library.acknowledgement}"
        return Precheck(library, names, (), (), (), refusal=reason)

    # A library gated on the cost of its surface rather than on any unresolved fact. The gate
    # is the acknowledgement; the enumeration is a separate question answered just below.
    if library.acknowledgement and not (
        library.key == "ecc" and config.acknowledge_ecc_surface
    ):
        return Precheck(library, names, (), (), (), refusal=library.acknowledgement)

    if not names:
        skipped_reason = (
            f"the {library.surface} names {library.key} writes cannot be enumerated without"
            " running its own front door, so no collision comparison was performed"
        )
        # The surface is unenumerable offline and the operator acknowledged the cost. Refusing
        # here would make the library unreachable; pretending the precheck passed would be a
        # lie. So it proceeds with the check explicitly labelled SKIPPED, everywhere it is
        # reported, and the install's own front-door exit code becomes the only success claim.
        if library.key == "ecc" and config.acknowledge_ecc_surface:
            return Precheck(
                library,
                names,
                (),
                (),
                (),
                skipped=True,
                skipped_reason=skipped_reason,
            )
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

    # Which occupied names the other channel's own lock attributes to this same upstream.
    # Only these are candidates for migration; everything else is a foreign entry.
    occupied_names = tuple(name for name, _ in home_collisions)
    provenance, _unavailable = prove_same_upstream(library, occupied_names, config)
    migratable = tuple(sorted(item.name for item in provenance if item.proven))

    refusal = ""
    duplicate_channel = False
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
        duplicate_channel = True
        refusal = (
            f"{len(home_collisions)} of this library's {len(names)} skill name(s) are"
            f" already present in {config.skills_dir} through a different channel, so"
            " installing the plugin would load the same capability twice. Upstream's own"
            " README: 'Pick one — installing both leaves you with every skill twice.'"
        )
        if len(migratable) == len(home_collisions):
            # Not a dead end: every occupant is provably the same upstream arriving by a
            # different road, so de-duplicating is a channel change rather than a capability
            # loss. Say so, and name the verb.
            refusal += (
                f" All {len(migratable)} are provably the same upstream in the other"
                f" channel's own lock file, so `migrate {library.key}` can retire them"
                " through that channel's own removal path and then install. Or pass"
                " --allow-duplicate-channel to accept the duplication deliberately"
            )
        else:
            refusal += (
                f" {len(migratable)} of {len(home_collisions)} are provably the same"
                " upstream; the rest are not, so `migrate` would refuse them. Pass"
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
        migratable=migratable,
        duplicate_channel=duplicate_channel,
    )


def front_door_available(library: Library) -> str:
    missing = [tool for tool in library.requires if shutil.which(tool) is None]
    return ", ".join(missing)


# The prerequisite the marketplace door does not state and cannot check for itself. Executed
# 2026-08-20 on Claude Code 2.1.238 in a container with no login: `claude plugin marketplace list`
# printed "No marketplaces configured" at exit 0, and `claude plugins install mattpocock-skills`
# then failed not-found-in-any-configured-marketplace. Upstream's README says the official
# marketplace needs no `marketplace add`, which holds only once a session is authenticated and
# that marketplace has registered. It is not testable credential-free, which is exactly why it is
# written down rather than left for each operator to rediscover as an opaque not-found.
MARKETPLACE_SESSION_PREREQUISITE = (
    "the marketplace door needs an AUTHENTICATED Claude Code session. The official marketplace"
    " upstream calls pre-listed registers only for a logged-in session: on a logged-out Claude"
    " Code 2.1.238 `claude plugin marketplace list` reports no marketplaces and"
    " `claude plugins install mattpocock-skills` fails not-found-in-any-configured-marketplace."
    " Log in, or add a marketplace yourself, or use the second door, which needs no Claude"
    " Code session at all"
)

# Both runners come from tools this repository already pins — node supplies `npx`, bun supplies
# `bunx` — so naming them adds no bootstrap prerequisite under ADR-0002. npx is preferred only
# because its `-y` suppresses the package-install prompt; `bunx skills@latest --version` was
# executed on the same host and reported the same CLI version, 1.5.23.
SKILLS_CLI_RUNNERS = ("npx", "bunx")


def configured_marketplaces(config: Config) -> tuple[str, ...]:
    """Marketplace names this home has configured. Absent and unreadable both mean none.

    An empty result is a *reported* condition rather than a silent fallthrough: every caller
    prints it, because "no marketplace is configured" is the whole explanation for the
    marketplace door's not-found failure, and swallowing it is what made that failure opaque.
    """
    path = config.marketplaces_state
    if not path.is_file():
        return ()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ()
    if not isinstance(document, dict):
        return ()
    return tuple(sorted(str(name) for name in document))


def skills_cli_runner() -> str:
    """The first pinned runner actually on PATH, or "" when neither is."""
    for runner in SKILLS_CLI_RUNNERS:
        if shutil.which(runner) is not None:
            return runner
    return ""


def skills_cli_command(library: Library, runner: str = "") -> tuple[str, ...]:
    """The `skills` CLI door for a library, built only from that CLI's observed grammar.

    `-s '*' -a claude-code -y` is what makes it noninteractive: without them the CLI prompts for
    which skills and which agents to take. The agent scope is deliberate and matches the removal
    front door's — `--agent claude-code` keeps this pointed at one host's directory instead of
    every agent that CLI knows about. `*` is a literal argument: nothing in this module runs
    through a shell, so it is never word-split or glob-expanded against the caller's directory.
    """
    runner = runner or SKILLS_CLI_RUNNERS[0]
    # npm's `-y` is "run this package without prompting"; bunx has no such flag and needs none.
    prefix = (runner, "-y") if runner == "npx" else (runner,)
    return prefix + (
        "skills@latest",
        "add",
        library.lock_source,
        "--global",
        "--agent",
        "claude-code",
        "--skill",
        "*",
        "--yes",
    )


def paste_safe(command: tuple[str, ...]) -> str:
    """Render a command the operator is expected to RUN THEMSELVES, safely quoted.

    This module never uses a shell, so `--skill *` is a literal argument to it. A printed line is
    different: it exists to be pasted into a shell, where a bare `*` glob-expands against
    whatever directory the operator happens to be in and silently becomes a different command.
    Quoting is therefore part of being honest about what to run, not cosmetic.
    """
    return shlex.join(command)


def cli_alternative_report(library: Library, config: Config) -> list[str]:
    """Report the second door, and say which door this library currently stands behind.

    Both doors reach the same upstream and differ only in prerequisite. The marketplace door
    stays PRIMARY whenever a `claude` binary and at least one configured marketplace are both
    present. Otherwise the operator is directed at the CLI door, with its exact command.

    The CLI door is printed, never invoked. It writes flat names into the same directory this
    bundle's own entries occupy, so it is governed by the flat-channel collision rules rather
    than the plugin-channel ones the precheck just applied. Running it from here would install
    through a precheck that never evaluated its channel — the silent loss this module exists to
    prevent — so the operator runs it, deliberately, or reaches for `migrate` instead.
    """
    if not library.cli_alternative:
        return []
    runner = skills_cli_runner()
    command = paste_safe(skills_cli_command(library, runner))
    missing_runner = "MISSING -> neither " + " nor ".join(SKILLS_CLI_RUNNERS) + " is on PATH"
    lines = [
        f"second door:  {command}",
        f"  observed:   {library.cli_alternative}",
        "  needs:      no Claude Code session. Writes FLAT names into"
        f" {config.skills_dir}, so the plugin-channel precheck above does not cover it."
        " Printed, never invoked here.",
        f"  runner:     {runner or missing_runner}",
    ]
    marketplaces = configured_marketplaces(config)
    if marketplaces:
        lines.append(
            f"marketplaces: {len(marketplaces)} configured in {config.marketplaces_state}"
            f" ({', '.join(marketplaces)}), so the marketplace door above stays primary"
        )
        return lines
    lines.append(
        f"marketplaces: NONE configured in {config.marketplaces_state}, so the marketplace door"
        " above cannot resolve this plugin yet"
    )
    lines.append(f"  prerequisite: {MARKETPLACE_SESSION_PREREQUISITE}")
    lines.append(f"  DIRECTED:   use the second door instead: {command}")
    return lines


def empty_marketplace_hint(library: Library, config: Config) -> list[str]:
    """The hint a failed marketplace install earns when this home configures no marketplace.

    The signature is deliberately the OFFLINE one — a nonzero front-door exit plus zero
    configured marketplaces — rather than a string matched against the front door's own output.
    Matching its prose would mean capturing output the operator is already reading live, and it
    would break the first time upstream rewords the message; the recorded state behind that
    message is the same fact and is readable without touching the subprocess at all.
    """
    if not library.cli_alternative or configured_marketplaces(config):
        return []
    return [
        f"why: {MARKETPLACE_SESSION_PREREQUISITE}",
        "second door, which needs no Claude Code session:"
        f" {paste_safe(skills_cli_command(library, skills_cli_runner()))}",
        f"That door writes FLAT names into {config.skills_dir}, which the plugin-channel"
        f" precheck did not evaluate, so run it yourself — or `libraries:migrate -- {library.key}`"
        " if that channel already holds those names. Nothing here invokes it.",
    ]


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
    # A skipped precheck and a passed one must never render alike. This is the only line that
    # reports precheck state, and it says SKIPPED in words rather than by omission.
    if check.skipped:
        lines.append(f"precheck:     SKIPPED, not passed — {check.skipped_reason}")
        lines.append(
            "              Nothing verified that these names are free. Supply --names-from"
            " <file> to turn this into a real comparison."
        )
    elif check.names and not check.refused:
        lines.append(
            f"precheck:     passed against {len(check.names)} enumerated name(s)"
        )
    missing = front_door_available(library)
    lines.append(
        f"front-door tool: {'MISSING -> ' + missing if missing else 'present'}"
    )
    # A library with two legitimate doors must show both, and say which one it currently stands
    # behind. Printing only the primary is what let a missing prerequisite read as a broken tool.
    lines.extend(cli_alternative_report(library, config))
    for caveat in library.caveats:
        lines.append(f"caveat:       {caveat}")
    # `bundle_skill_count` is a note-text placeholder rather than a literal, so the count a
    # library's cost is measured against is this bundle's actual skill count at run time, not
    # a number that goes stale the next time a skill lands. Plain notes have no `{...}` to
    # substitute, so `.format()` on them is a no-op.
    bundle_skill_count = len(bundle_skill_names(config.repo_root))
    for note in library.notes:
        lines.append(
            f"note:         {note.format(bundle_skill_count=bundle_skill_count)}"
        )
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


def library_state(check: Precheck) -> str:
    """The one-word status in `list`. A library reachable by a documented verb is not blocked.

    "blocked" is reserved for a library with no route at all. A library whose only obstacle is
    a set of names another channel holds for the same upstream has a route — `migrate` — and
    calling that blocked would report a dead end where one does not exist.
    """
    if not check.refused:
        return "installable, precheck SKIPPED" if check.skipped else "installable"
    library = check.library
    if check.migratable and len(check.migratable) == len(check.home_collisions):
        return "installable after migration"
    if check.duplicate_channel:
        # Some occupants are unprovable, so `migrate` refuses — but duplication is still an
        # accepted-cost route, so this is not a dead end.
        return "installable accepting duplication"
    if library.acknowledgement:
        return f"installable behind {surface_gate(library)}"
    return "blocked"


def surface_gate(library: Library) -> str:
    return f"--acknowledge-{library.key}-surface"


def reach_command(check: Precheck) -> str:
    """The exact command that reaches this library from where it currently stands."""
    library = check.library
    if check.refused and check.migratable and len(check.migratable) == len(
        check.home_collisions
    ):
        return f"mise run libraries:migrate -- {library.key}   # then --yes to execute"
    if check.refused and library.acknowledgement:
        return (
            f"mise run libraries:install -- {library.key} {surface_gate(library)}"
            "   # then --yes to execute"
        )
    if check.refused and check.duplicate_channel:
        return (
            f"mise run libraries:install -- {library.key} --allow-duplicate-channel"
            "   # then --yes to execute"
        )
    if check.refused:
        return "no route: resolve the refusal above first"
    return f"mise run libraries:install -- {library.key}   # then --yes to execute"


def command_list(config: Config) -> tuple[int, list[str]]:
    bundle = bundle_skill_names(config.repo_root)
    occupied = present_names(config.skills_dir)
    lines = [
        "External skill libraries reachable through their own front doors.",
        "Nothing below is installed by `bundle:install`, `contributor:setup`, its deprecated `setup` forwarder, or any gate.",
        "",
        f"this bundle installs {len(bundle)} skill(s): {', '.join(bundle)}",
        f"{config.skills_dir} currently holds {len(occupied)} entr(ies)",
        "",
    ]
    for library in LIBRARIES.values():
        check = precheck(library, config)
        state = library_state(check)
        detected = detect(library, config)
        lines.append(f"{library.key}  [{state}]  detected: {detected}")
        lines.extend(f"  {line}" for line in render_plan(check, config))
        if library.enumeration:
            lines.append(f"  enumerate:    {library.enumeration}")
        if check.refused:
            lines.append(f"  REFUSED:      {check.refusal}")
        lines.append(f"  reach it by:  {reach_command(check)}")
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
                f"  agents: {len(found)}/{len(library.extra_agents)} of the recorded"
                f" {library.version} set present in {config.agents_dir}"
            )
            # The count above is true against a recorded set, which is exactly how it once read
            # 14/14 in a home holding 16 files. This front door has no verb that enumerates what
            # it renders, so the only honest drift signal available at status time is the
            # residue: a prefix-matching file the recorded set does not name. Reported rather
            # than dropped, because a total that omits it understates the selection surface.
            expected = expected_agent_files(library)
            unexpected = tuple(
                sorted(
                    entry
                    for entry in present
                    if library.owns(entry) and entry not in expected
                )
            )
            if unexpected:
                lines.append(
                    f"  agents: {len(unexpected)} further {library.name_prefix}-prefixed"
                    f" file(s) present that the recorded {library.version} set does not name,"
                    f" so the surface is wider than the count above: {', '.join(unexpected)}."
                    " Re-record the set against the current upstream."
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
        # A refusal is a *fact about what a real install would do*. Reporting it is the dry
        # run's whole job, so only a real install treats it as this run's own failure.
        if check.refused:
            failed = failed or config.assume_yes
            lines.append(f"REFUSED: {check.refusal}")
            lines.append("")
            continue
        missing = front_door_available(library)
        if missing:
            failed = failed or config.assume_yes
            lines.append(
                f"REFUSED: front-door tool not found on PATH: {missing}. This module"
                " installs no tool of its own"
            )
            if not config.assume_yes:
                # Still say DRY RUN. The run was asked to describe an outcome and it did;
                # omitting the line here made a described refusal look like a different kind
                # of event from a described install.
                lines.append(
                    "DRY RUN: nothing was run. The tool above is missing, so a real --yes"
                    " install would refuse rather than proceed."
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
            # A front door that exits nonzero is a failed install, full stop. This matters most
            # for a library whose documented entrypoint may not exist in the published
            # artifact: the failure must read as a failure rather than as a finished install.
            lines.append(
                f"install FAILED for {key}: the front door did not complete. Nothing here"
                " infers success from having run a command, and no part of this counts as"
                " authorization for any further effect."
            )
            # A door that failed because its prerequisite is unmet must name that prerequisite
            # AND the door that does not need it. Without both halves the operator reads a
            # not-found as "this library is unreachable" and stops at a dead end that isn't one.
            lines.extend(empty_marketplace_hint(library, config))
        elif check.skipped:
            lines.append(
                "front door completed, but the collision precheck was SKIPPED, not passed."
                " Names this library took from another writer would not have been reported."
                f" Compare {config.skills_dir} against the enumeration command in `list`."
            )
        lines.append("")
    if not config.assume_yes:
        lines.append(
            "Dry run is the default. No library was installed and no command was run."
        )
        if any(line.startswith("REFUSED:") for line in lines):
            lines.append(
                "Exit 0: a dry run's job is to describe the outcome, and the refusal above is"
                " that description. A real install (--yes) of the same thing would exit 1."
            )
        # A dry run's job is to DESCRIBE the outcome, so describing a refusal accurately is a
        # success: exit 0, with the refusal on the page. Exiting nonzero here made the honest
        # answer "a real install would refuse, because X" indistinguishable from "this tool
        # broke", and it made the repository gate pass on a machine that happens to have the
        # front-door tools on PATH while failing on a machine that does not — the defect a
        # container replay from the public remote exposed. A real install (--yes) keeps the
        # nonzero exit below, because there the refusal means nothing was installed.
        return 0, lines
    return (1 if failed else 0), lines


# The competing channel's OWN removal front door. Verified against `skills remove --help` and
# its `removeCommand` source. Two scoping decisions are load-bearing:
#   --global      the occupied names are in a home, not a project checkout.
#   --agent claude-code
#                 without it, `remove` targets every agent in its registry: it deletes the
#                 canonical ~/.agents/skills/<name>, every other agent's link to it, and the
#                 lock entry. Scoped to one agent it removes only ~/.claude/skills/<name> and
#                 leaves the canonical copy, the other agents' links, and the lock intact.
#                 De-duplicating a Claude Code name must not take the skill away from Codex.
# Names are appended by the caller. Nothing here shells out through a shell, so no name is
# ever word-split or glob-expanded.
CHANNEL_REMOVAL_FRONT_DOOR = (
    "npx",
    "-y",
    "skills@latest",
    "remove",
    "--global",
    "--agent",
    "claude-code",
    "--yes",
)
CHANNEL_REMOVAL_SOURCE = "`npx -y skills@latest remove --help` (skills CLI 1.5.22)"


def removal_command(names: tuple[str, ...]) -> tuple[str, ...]:
    return CHANNEL_REMOVAL_FRONT_DOOR + tuple(names)


def refusal_exit(config: Config) -> int:
    """The exit code a refusal earns, which depends on what was asked.

    A dry run was asked to *describe* what would happen; a refusal is a valid description, so
    describing one accurately is a success. A real (`--yes`) run was asked to *change* something
    and did not, so the same refusal is that run's failure. Sharing one exit path between the two
    is what made this module's gate pass on a host with the front-door tools on PATH and fail on
    a host without them.
    """
    return 1 if config.assume_yes else 0


def command_migrate(keys: list[str], config: Config) -> tuple[int, list[str]]:
    """Retire another channel's copies of the SAME upstream, then install through this one.

    The ordering is the whole point. Removal runs through the other channel's own front door,
    the precheck is then re-run against the real filesystem, and only a precheck that actually
    passes admits the install. A partial removal stops before installing, because installing
    over a still-occupied name is the silent loss this module exists to prevent.
    """
    if not keys:
        raise ExternalLibraryError(
            "name at least one library to migrate. There is no verb that migrates everything"
        )
    unknown = [key for key in keys if key not in LIBRARIES]
    if unknown:
        raise ExternalLibraryError(
            f"unknown librar(ies): {', '.join(unknown)}. Known: {', '.join(LIBRARIES)}"
        )
    lines: list[str] = []
    failed = False
    for key in keys:
        library = LIBRARIES[key]
        lines.append(f"=== {key} ===")
        code, output = migrate_one(library, config)
        lines.extend(output)
        if code:
            failed = True
        lines.append("")
    if not config.assume_yes:
        lines.append(
            "Dry run is the default. Nothing was removed, and nothing was installed."
        )
    return (1 if failed else 0), lines


def migrate_one(library: Library, config: Config) -> tuple[int, list[str]]:
    lines: list[str] = []
    check = precheck(library, config)
    occupied = tuple(name for name, _ in check.home_collisions)

    if not occupied:
        lines.append(
            "nothing to migrate: no name this library writes is occupied by another writer."
            f" Use `libraries:install -- {library.key}` instead."
        )
        return refusal_exit(config), lines

    provenance, unavailable = prove_same_upstream(library, occupied, config)
    lines.append(f"provenance oracle: {config.skill_lock}")
    lines.append(f"  removal front door documented at: {CHANNEL_REMOVAL_SOURCE}")
    if unavailable:
        lines.append(
            f"REFUSED: provenance cannot be established — {unavailable}. Presence on the"
            " filesystem proves presence, not provenance; without the other channel's own"
            " record that these names are the same upstream, nothing here will remove them."
        )
        return refusal_exit(config), lines

    proven = tuple(item for item in provenance if item.proven)
    unproven = tuple(item for item in provenance if not item.proven)
    for item in proven:
        lines.append(f"  PROVEN same upstream: {item.name} (source {item.source})")
    for item in unproven:
        lines.append(f"  NOT PROVEN, left alone: {item.name} — {item.reason}")

    if unproven:
        lines.append(
            f"REFUSED: {len(unproven)} of {len(occupied)} occupied name(s) cannot be proven"
            f" to be the same upstream as {library.key}. Anything unproven is a foreign entry"
            " and stays exactly where it is, so this migration would be incomplete and is not"
            " attempted. Resolve those names yourself, or accept the duplication with"
            " --allow-duplicate-channel on `install`."
        )
        return refusal_exit(config), lines

    names = tuple(item.name for item in proven)
    command = removal_command(names)
    lines.append("")
    lines.append(f"would remove {len(names)} name(s) via the other channel's own front door:")
    lines.append(f"  {' '.join(command)}")
    lines.append(f"  exact names: {', '.join(names)}")
    lines.append(
        "  scope: --agent claude-code removes only"
        f" {config.skills_dir}/<name>. The canonical copy under"
        f" {config.home / '.agents' / 'skills'}, every other agent's link to it, and the lock"
        " entry all survive, so no other host loses the capability."
    )
    lines.append("  this module runs no rm of its own, and touches no path directly.")
    lines.append("")
    lines.append("then would install:")
    lines.append(f"  {' '.join(library.front_door)}")

    # Both tools are reported before either is acted on, so a dry run on a machine with neither
    # names both rather than stopping at the first one. Under --yes each is a hard stop, because
    # then the run was asked to change something it cannot.
    missing = front_door_available(library)
    npx_missing = shutil.which(CHANNEL_REMOVAL_FRONT_DOOR[0]) is None
    if npx_missing:
        lines.append(
            f"REFUSED: the other channel's removal front door needs"
            f" {CHANNEL_REMOVAL_FRONT_DOOR[0]}, which is not on PATH"
        )
    if missing:
        lines.append(
            f"REFUSED: this library's own front-door tool is not on PATH: {missing}."
            " Removal is not attempted, because a removal whose install cannot follow would"
            " leave the home with neither channel."
        )
    if npx_missing or missing:
        if config.assume_yes:
            return 1, lines
        lines.append("")
        lines.append(
            "DRY RUN: nothing was removed and nothing was installed. The tool(s) named above"
            " are missing, so a real --yes migration would refuse rather than proceed."
        )
        return 0, lines

    if not config.assume_yes:
        lines.append("")
        lines.append(
            "DRY RUN: nothing was removed and nothing was installed. Re-run with --yes to"
            " execute the removal and then the install."
        )
        return 0, lines

    lines.append("")
    code, output = run_front_door(command, config)
    lines.extend(output)
    if code:
        lines.append(
            "STOPPED before installing: the removal front door failed, so the names may still"
            " be occupied. Installing now could silently lose either copy."
        )
        return 1, lines

    # Re-run the precheck against the real filesystem. The removal's exit code says the command
    # succeeded; only a fresh look says the names are actually free.
    after = precheck(library, config)
    still_occupied = tuple(name for name, _ in after.home_collisions)
    if still_occupied:
        lines.append(
            f"STOPPED before installing: {len(still_occupied)} name(s) are still occupied"
            f" after removal: {', '.join(still_occupied)}. The removal reported success, so"
            " this is a partial removal rather than a failure — read the front door's own"
            " output above before retrying."
        )
        return 1, lines
    if after.refused:
        lines.append(
            f"STOPPED before installing: the precheck still refuses — {after.refusal}"
        )
        return 1, lines
    lines.append(
        f"precheck re-run after removal: passed, {len(after.new_names)} name(s) now free"
    )
    code, output = run_front_door(library.front_door, config)
    lines.extend(output)
    if code:
        lines.append(
            "The other channel's copies were removed but this library's front door failed."
            " The home now has neither; re-run the install once the cause above is fixed."
        )
        return 1, lines
    return 0, lines


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
        # Same describing-vs-doing split as `install`: under a dry run a refusal is the
        # description that was asked for, so it does not fail the run.
        if not library.uninstall:
            failed = failed or config.assume_yes
            lines.append(
                "REFUSED: no uninstall front door is wired for this library. Its own"
                " removal path is the only supported one, and this module never deletes a"
                " path it did not see that path's own installer create."
            )
            lines.append("")
            continue
        missing = front_door_available(library)
        if missing:
            failed = failed or config.assume_yes
            lines.append(f"REFUSED: front-door tool not found on PATH: {missing}")
            if not config.assume_yes:
                lines.append("DRY RUN: nothing was run.")
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
            " Dry run by default; never invoked by bundle:install, contributor:setup, or its deprecated setup forwarder."
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
    migrate = subparsers.add_parser(
        "migrate",
        parents=[common],
        help=(
            "retire another channel's copies of the same upstream through that channel's own"
            " removal path, then install through this one"
        ),
    )
    migrate.add_argument("libraries", nargs="*")
    uninstall = subparsers.add_parser(
        "uninstall", parents=[common], help="run a library's own removal path"
    )
    uninstall.add_argument("libraries", nargs="*")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    names_from = getattr(args, "names_from", None)
    home = absolute(getattr(args, "home", None) or Path.home())
    # The competing channel resolves its lock through XDG_STATE_HOME. Honour that only when the
    # target home is the real one; a --home fixture must not read the operator's lock file and
    # conclude anything about a directory it is not looking at.
    state_home = os.environ.get("XDG_STATE_HOME")
    config = Config(
        repo_root=Path(__file__).resolve().parents[1],
        home=home,
        assume_yes=getattr(args, "yes", False),
        acknowledge_ecc_surface=getattr(args, "acknowledge_ecc_surface", False),
        allow_duplicate_channel=getattr(args, "allow_duplicate_channel", False),
        names_from=absolute(names_from) if names_from else None,
        state_home=(
            absolute(Path(state_home))
            if state_home and home == absolute(Path.home())
            else None
        ),
    )
    try:
        if args.command == "list":
            code, messages = command_list(config)
        elif args.command == "status":
            code, messages = command_status(config)
        elif args.command == "install":
            code, messages = command_install(args.libraries, config)
        elif args.command == "migrate":
            code, messages = command_migrate(args.libraries, config)
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
