from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "install_external_libraries.py"
SKILL = ROOT / "skills" / "external-skill-libraries" / "SKILL.md"


def load_module():
    """Import the installer as a module so the precheck can be driven from fixtures.

    The script is a uv single-file script, not a package member, so it is loaded by path.
    """
    spec = importlib.util.spec_from_file_location("install_external_libraries", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered before exec because @dataclass resolves string annotations through
    # sys.modules[cls.__module__]; without this the decorator raises on the first class.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def make_home(
    names: tuple[str, ...] = (),
    links: dict[str, str] | None = None,
    lock: dict[str, dict] | None = None,
    lock_version: int = 3,
) -> Path:
    """Build a throwaway home whose skills dir holds exactly ``names`` plus ``links``.

    ``lock`` writes the competing channel's own lock file at the path that channel resolves,
    which is the only thing the migration path will accept as provenance.
    """
    temporary = tempfile.TemporaryDirectory()
    home = Path(temporary.name) / "home"
    skills = home / ".claude" / "skills"
    skills.mkdir(parents=True)
    for name in names:
        (skills / name).mkdir()
    for name, target in (links or {}).items():
        (skills / name).symlink_to(target)
    if lock is not None:
        agents = home / ".agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / ".skill-lock.json").write_text(
            json.dumps({"version": lock_version, "skills": lock}), encoding="utf-8"
        )
    make_home.cleanups.append(temporary)
    return home


make_home.cleanups = []  # type: ignore[attr-defined]


def matt_lock(*names: str) -> dict[str, dict]:
    """A lock file recording ``names`` against mattpocock's real upstream identifiers."""
    return {
        name: {
            "source": MODULE.MATTPOCOCK.lock_source,
            "sourceType": "github",
            "sourceUrl": MODULE.MATTPOCOCK.lock_source_url,
            "pluginName": "mattpocock-skills",
        }
        for name in names
    }


# The subset of mattpocock's declared names used to stand in for "another channel already holds
# these". Taken from the real row so the fixture cannot drift from what the library declares.
OCCUPIED_SAMPLE = MODULE.MATTPOCOCK.names[:3]


# The agent files upstream hyperresearch 0.10.0 actually renders, RECORDED rather than derived.
# Recorded by executing `hyperresearch install --global` in a container on 2026-08-20 against
# `hyperresearch v0.10.0` (`hyperresearch --version`), then `ls ~/.claude/agents | grep
# hyperresearch` — 16 files, listed here in that command's sorted order.
#
# This fixture exists because that front door exposes NO verb that enumerates what it renders:
# `hyperresearch --help` at 0.10.0 lists install/setup/init/status/sync/search/... and nothing
# that lists agents, and `install --help` has no --dry-run, so there is no oracle to derive the
# expected set from at status time. A hardcoded list is therefore the only offline source, and it
# drifted two files behind this SAME upstream version once already (hyperresearch-browser-fetcher
# and hyperresearch-cite-checker were missing, so `status` reported a truthful 14/14 against a
# directory holding 16). The next drift must fail a named test instead of under-reporting
# silently. When it does: re-run the install, re-`ls`, re-record BOTH this tuple and the version
# named in this comment and in the row's own comment, and never reconcile by editing one side.
RECORDED_HYPERRESEARCH_AGENTS = (
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
)
RECORDED_HYPERRESEARCH_VERSION = "0.10.0"


class PrecheckTests(unittest.TestCase):
    """The collision precheck, driven against fixture homes. No network, no installs."""

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def config(self, home: Path, **overrides: object) -> object:
        return MODULE.Config(repo_root=ROOT, home=home, **overrides)  # type: ignore[arg-type]

    def test_empty_home_admits_the_plugin_library(self) -> None:
        check = MODULE.precheck(MODULE.MATTPOCOCK, self.config(make_home()))
        self.assertFalse(check.refused, check.refusal)
        self.assertEqual(len(check.new_names), len(MODULE.MATTPOCOCK.names))
        self.assertEqual(check.home_collisions, ())

    def test_collision_with_this_bundles_own_skill_name_refuses(self) -> None:
        # The strongest refusal: a foreign name equal to one this bundle installs.
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=("agentic-sdlc", "unrelated-fixture-name"),
        )
        check = MODULE.precheck(library, self.config(make_home()))
        self.assertTrue(check.refused)
        self.assertIn("agentic-sdlc", check.bundle_collisions)
        self.assertIn("collide with skills this bundle installs", check.refusal)

    def test_flat_channel_refuses_when_a_name_is_already_occupied(self) -> None:
        home = make_home(names=("tdd",))
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=("tdd", "fixture-only"),
        )
        check = MODULE.precheck(library, self.config(home))
        self.assertTrue(check.refused)
        self.assertIn("tdd", [name for name, _ in check.home_collisions])
        self.assertIn("already occupied", check.refusal)

    def test_a_symlink_occupies_a_name_just_as_a_directory_does(self) -> None:
        # The operator's real home has flat skill names that are links into another
        # installer's tree; reading a link as absent is the silent-loss bug.
        home = make_home(links={"tdd": "../../.agents/skills/tdd"})
        detail = MODULE.describe_occupant(home / ".claude" / "skills", "tdd")
        self.assertTrue(detail.startswith("link -> "), detail)
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=("tdd",),
        )
        check = MODULE.precheck(library, self.config(home))
        self.assertTrue(check.refused)

    def test_plugin_channel_refuses_duplicate_channel_and_the_override_clears_it(self) -> None:
        home = make_home(names=("tdd", "code-review"))
        config = self.config(home)
        check = MODULE.precheck(MODULE.MATTPOCOCK, config)
        self.assertTrue(check.refused)
        self.assertIn("same capability twice", check.refusal)
        allowed = MODULE.precheck(
            MODULE.MATTPOCOCK, self.config(home, allow_duplicate_channel=True)
        )
        self.assertFalse(allowed.refused, allowed.refusal)

    def test_own_prefix_is_a_reinstall_rather_than_a_collision(self) -> None:
        home = make_home(names=MODULE.HYPERRESEARCH.names)
        check = MODULE.precheck(MODULE.HYPERRESEARCH, self.config(home))
        self.assertFalse(check.refused, check.refusal)
        self.assertEqual(check.home_collisions, ())
        self.assertEqual(len(check.reinstalls), len(MODULE.HYPERRESEARCH.names))

    def test_ecc_is_gated_on_its_surface_cost_not_on_its_version(self) -> None:
        # The version gap is an accepted caveat, not a refusal (operator decision, ADR-0009
        # amendment 2026-08-07). What still gates ECC is the 284-entry surface.
        check = MODULE.precheck(MODULE.ECC, self.config(make_home()))
        self.assertTrue(check.refused)
        self.assertIn("284", check.refusal)
        self.assertIn("--acknowledge-ecc-surface", check.refusal)
        self.assertNotIn("2.2.0", check.refusal)

    def test_ecc_version_gap_survives_as_a_visible_caveat(self) -> None:
        # Overruled does not mean deleted. The gap must still be recorded and printed.
        caveats = " ".join(MODULE.ECC.caveats)
        self.assertIn("2.2.0", caveats)
        self.assertIn("2.1.0", caveats)
        rendered = "\n".join(
            MODULE.render_plan(
                MODULE.precheck(
                    MODULE.ECC,
                    self.config(make_home(), acknowledge_ecc_surface=True),
                ),
                self.config(make_home(), acknowledge_ecc_surface=True),
            )
        )
        self.assertIn("VERSION GAP (accepted)", rendered)

    def test_ecc_acknowledgement_alone_proceeds_with_the_precheck_marked_skipped(self) -> None:
        # The surface cannot be enumerated offline, so requiring --names-from would make ECC
        # unreachable. It proceeds, but the check must report SKIPPED rather than passed.
        config = self.config(make_home(), acknowledge_ecc_surface=True)
        check = MODULE.precheck(MODULE.ECC, config)
        self.assertFalse(check.refused, check.refusal)
        self.assertTrue(check.skipped)
        rendered = "\n".join(MODULE.render_plan(check, config))
        self.assertIn("SKIPPED, not passed", rendered)
        self.assertNotIn("precheck:     passed", rendered)

    def test_a_passed_precheck_never_renders_like_a_skipped_one(self) -> None:
        config = self.config(make_home())
        rendered = "\n".join(
            MODULE.render_plan(MODULE.precheck(MODULE.MATTPOCOCK, config), config)
        )
        self.assertIn("precheck:     passed", rendered)
        self.assertNotIn("SKIPPED", rendered)

    def test_ecc_front_door_is_the_one_the_published_artifact_actually_exposes(self) -> None:
        # The README's `npx ecc-universal setup` has no bin in the published 2.1.0 tarball, so
        # wiring it would guarantee a failure. Pin the verified path instead.
        front_door = " ".join(MODULE.ECC.front_door)
        self.assertNotIn("ecc-universal setup", front_door)
        self.assertIn("-p ecc-universal", front_door)
        self.assertIn("ecc install", front_door)
        # The CLI refuses outright when given no profile, so one must be pinned.
        self.assertIn("--profile", front_door)

    def test_a_blocked_fact_is_not_overridable_by_any_cost_flag(self) -> None:
        # `blocked` means "cannot be honestly run", `acknowledgement` means "expensive". No row
        # sets `blocked` today; the distinction is load-bearing, so it is tested rather than
        # left to rot into something a flag can wave away.
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=("fixture-only",),
            blocked="its published artifact does not contain the documented entrypoint",
        )
        check = MODULE.precheck(
            library,
            self.config(
                make_home(), acknowledge_ecc_surface=True, allow_duplicate_channel=True
            ),
        )
        self.assertTrue(check.refused)
        self.assertIn("does not contain the documented entrypoint", check.refusal)
        self.assertEqual(MODULE.library_state(check), "blocked")

    def test_supported_catalog_is_exact_and_origin_pinned(self) -> None:
        self.assertEqual(
            tuple((library.key, library.origin) for library in MODULE.SUPPORTED_LIBRARIES),
            (
                ("mattpocock", "https://github.com/mattpocock/skills"),
                ("ecc", "https://github.com/affaan-m/ECC"),
                ("hyperresearch", "https://github.com/jordan-gibbs/hyperresearch"),
            ),
        )
        self.assertEqual(tuple(MODULE.LIBRARIES), ("mattpocock", "ecc", "hyperresearch"))

    def test_no_shipped_library_row_is_blocked(self) -> None:
        # The deliverable: all three must be reachable. A `blocked` row would be a dead end.
        for library in MODULE.LIBRARIES.values():
            self.assertEqual(library.blocked, "", library.key)

    def test_unenumerable_surface_refuses_rather_than_passing(self) -> None:
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=(),
            catalog_size=99,
        )
        check = MODULE.precheck(library, self.config(make_home()))
        self.assertTrue(check.refused)
        self.assertIn("could not be enumerated", check.refusal)

    def test_names_from_file_supplies_a_surface_for_the_precheck(self) -> None:
        home = make_home()
        listing = home.parent / "names.txt"
        listing.write_text("alpha-fixture\nbeta-fixture\n", encoding="utf-8")
        names = MODULE.load_names_override(listing)
        self.assertEqual(names, ("alpha-fixture", "beta-fixture"))
        check = MODULE.precheck(
            MODULE.ECC,
            self.config(home, acknowledge_ecc_surface=True, names_from=listing),
        )
        self.assertFalse(check.refused, check.refusal)

    def test_an_empty_names_file_is_a_named_failure(self) -> None:
        home = make_home()
        listing = home.parent / "empty.txt"
        listing.write_text("\n\n", encoding="utf-8")
        with self.assertRaises(MODULE.ExternalLibraryError):
            MODULE.load_names_override(listing)

    def test_bundle_names_are_discovered_from_the_tree_not_hardcoded(self) -> None:
        names = MODULE.bundle_skill_names(ROOT)
        self.assertIn("agentic-sdlc", names)
        self.assertIn("external-skill-libraries", names)
        self.assertEqual(
            len(names), len(list((ROOT / "skills").glob("*/SKILL.md")))
        )


class ProvenanceProofTests(unittest.TestCase):
    """The only thing that licenses a removal: the other channel's own record of the upstream.

    Filesystem presence proves presence, not provenance. Every case here is about what happens
    when that record is missing, stale, or points somewhere else — the answer is always that the
    name is left alone.
    """

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def config(self, home: Path, **overrides: object) -> object:
        return MODULE.Config(repo_root=ROOT, home=home, **overrides)  # type: ignore[arg-type]

    def test_matching_source_and_url_prove_the_same_upstream(self) -> None:
        home = make_home(names=OCCUPIED_SAMPLE, lock=matt_lock(*OCCUPIED_SAMPLE))
        proven, unavailable = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        self.assertEqual(unavailable, "")
        self.assertTrue(all(item.proven for item in proven), proven)
        self.assertEqual(len(proven), len(OCCUPIED_SAMPLE))

    def test_a_different_source_refuses_that_name(self) -> None:
        lock = matt_lock(*OCCUPIED_SAMPLE)
        lock[OCCUPIED_SAMPLE[0]]["source"] = "vercel-labs/skills"
        home = make_home(names=OCCUPIED_SAMPLE, lock=lock)
        proven, _ = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        by_name = {item.name: item for item in proven}
        self.assertFalse(by_name[OCCUPIED_SAMPLE[0]].proven)
        self.assertIn("vercel-labs/skills", by_name[OCCUPIED_SAMPLE[0]].reason)
        self.assertTrue(by_name[OCCUPIED_SAMPLE[1]].proven)

    def test_a_matching_source_with_a_foreign_clone_url_refuses(self) -> None:
        # A short name is not an identity. A different repository can wear the same label.
        lock = matt_lock(*OCCUPIED_SAMPLE)
        lock[OCCUPIED_SAMPLE[0]]["sourceUrl"] = "https://github.com/impostor/skills.git"
        home = make_home(names=OCCUPIED_SAMPLE, lock=lock)
        proven, _ = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        by_name = {item.name: item for item in proven}
        self.assertFalse(by_name[OCCUPIED_SAMPLE[0]].proven)
        self.assertIn("sourceUrl", by_name[OCCUPIED_SAMPLE[0]].reason)

    def test_a_name_missing_from_the_lock_refuses(self) -> None:
        # Occupied on disk, unrecorded in the lock: an unattributable entry, so untouchable.
        home = make_home(names=OCCUPIED_SAMPLE, lock=matt_lock(*OCCUPIED_SAMPLE[1:]))
        proven, _ = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        by_name = {item.name: item for item in proven}
        self.assertFalse(by_name[OCCUPIED_SAMPLE[0]].proven)
        self.assertIn("no entry", by_name[OCCUPIED_SAMPLE[0]].reason)

    def test_no_lock_file_at_all_is_an_unavailable_proof_not_an_empty_one(self) -> None:
        home = make_home(names=OCCUPIED_SAMPLE)
        proven, unavailable = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        self.assertEqual(proven, ())
        self.assertIn("no lock file", unavailable)

    def test_a_stale_lock_schema_version_is_refused_rather_than_read(self) -> None:
        # The channel's own reader discards a lock below its current version, so crediting one
        # would attribute provenance to a document its writer considers void.
        home = make_home(
            names=OCCUPIED_SAMPLE, lock=matt_lock(*OCCUPIED_SAMPLE), lock_version=2
        )
        _, unavailable = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        self.assertIn("schema version 2", unavailable)

    def test_a_corrupt_lock_file_is_refused_by_name(self) -> None:
        home = make_home(names=OCCUPIED_SAMPLE)
        lock_path = home / ".agents" / ".skill-lock.json"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text("{not json", encoding="utf-8")
        _, unavailable = MODULE.prove_same_upstream(
            MODULE.MATTPOCOCK, OCCUPIED_SAMPLE, self.config(home)
        )
        self.assertIn("not valid JSON", unavailable)

    def test_a_library_with_no_recorded_lock_source_can_never_be_migrated(self) -> None:
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="plugin",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=OCCUPIED_SAMPLE,
        )
        home = make_home(names=OCCUPIED_SAMPLE, lock=matt_lock(*OCCUPIED_SAMPLE))
        proven, unavailable = MODULE.prove_same_upstream(
            library, OCCUPIED_SAMPLE, self.config(home)
        )
        self.assertEqual(proven, ())
        self.assertIn("no competing-channel lock source", unavailable)


class MigrationTests(unittest.TestCase):
    """The migrate verb: prove, print, require --yes, re-check, and stop on partial removal."""

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def config(self, home: Path, **overrides: object) -> object:
        return MODULE.Config(repo_root=ROOT, home=home, **overrides)  # type: ignore[arg-type]

    def occupied_home(self) -> Path:
        return make_home(
            links={
                name: f"../../.agents/skills/{name}" for name in OCCUPIED_SAMPLE
            },
            lock=matt_lock(*OCCUPIED_SAMPLE),
        )

    def setUp(self) -> None:
        """Pretend every front-door tool is present, whatever this host actually has.

        These tests are about migration ORDERING, not about tool discovery. Letting them read
        the real PATH made them pass on a dev host with `claude` and `npx` installed and fail on
        a clean machine — the same host-dependence that took the repository gate red in a
        container. Tool discovery is asserted deliberately elsewhere, by stubbing the other way.
        """
        self._real_which = MODULE.shutil.which
        MODULE.shutil.which = lambda tool: f"/usr/bin/{tool}"  # type: ignore[assignment]
        self.addCleanup(setattr, MODULE.shutil, "which", self._real_which)

    def test_the_removal_command_is_the_other_channels_own_front_door(self) -> None:
        command = MODULE.removal_command(("alpha", "beta"))
        self.assertEqual(
            command,
            (
                "npx",
                "-y",
                "skills@latest",
                "remove",
                "--global",
                "--agent",
                "claude-code",
                "--yes",
                "alpha",
                "beta",
            ),
        )
        # Scoping to one agent is what keeps the canonical copy and every other agent's link.
        self.assertIn("--agent", command)
        self.assertIn("claude-code", command)

    def test_migrate_is_a_dry_run_without_yes_and_removes_nothing(self) -> None:
        home = self.occupied_home()
        code, lines = MODULE.command_migrate(["mattpocock"], self.config(home))
        output = "\n".join(lines)
        self.assertEqual(code, 0, output)
        self.assertIn("DRY RUN", output)
        self.assertIn("Nothing was removed, and nothing was installed", output)
        # The links must still be there afterwards.
        for name in OCCUPIED_SAMPLE:
            self.assertTrue((home / ".claude" / "skills" / name).is_symlink(), name)

    def test_the_dry_run_prints_the_exact_command_and_the_exact_names(self) -> None:
        home = self.occupied_home()
        _, lines = MODULE.command_migrate(["mattpocock"], self.config(home))
        output = "\n".join(lines)
        self.assertIn("npx -y skills@latest remove --global --agent claude-code --yes", output)
        for name in OCCUPIED_SAMPLE:
            self.assertIn(name, output)
        self.assertIn("exact names:", output)
        # And what it would install afterwards.
        self.assertIn(" ".join(MODULE.MATTPOCOCK.front_door), output)

    def test_migrate_refuses_when_any_occupied_name_is_unproven(self) -> None:
        # Asserted under --yes, where a refusal genuinely is this run's failure. The same
        # refusal described by a dry run exits 0; that split is asserted separately, and
        # pinning the code here rather than the message would have hidden it.
        lock = matt_lock(*OCCUPIED_SAMPLE)
        lock[OCCUPIED_SAMPLE[0]]["source"] = "someone-else/skills"
        home = make_home(names=OCCUPIED_SAMPLE, lock=lock)
        code, lines = MODULE.command_migrate(
            ["mattpocock"], self.config(home, assume_yes=True)
        )
        output = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("NOT PROVEN, left alone", output)
        self.assertIn("stays exactly where it is", output)
        self.assertNotIn("would remove", output)

    def test_migrate_refuses_when_provenance_is_unavailable(self) -> None:
        home = make_home(names=OCCUPIED_SAMPLE)  # occupied, but no lock file
        code, lines = MODULE.command_migrate(
            ["mattpocock"], self.config(home, assume_yes=True)
        )
        output = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("provenance cannot be established", output)
        self.assertIn("proves presence, not provenance", output)

    def test_migrate_with_nothing_occupied_points_at_install_instead(self) -> None:
        code, lines = MODULE.command_migrate(
            ["mattpocock"], self.config(make_home(), assume_yes=True)
        )
        output = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("nothing to migrate", output)

    def test_a_dry_run_migrate_describes_a_refusal_without_failing(self) -> None:
        # Every refusal reason `migrate` can reach, described rather than suffered. This is the
        # host-independent half: none of it depends on which tools happen to be on PATH.
        cases = {
            "unprovable occupant": make_home(
                names=OCCUPIED_SAMPLE,
                lock={
                    **matt_lock(*OCCUPIED_SAMPLE[1:]),
                    OCCUPIED_SAMPLE[0]: {"source": "someone-else/skills"},
                },
            ),
            "no lock file": make_home(names=OCCUPIED_SAMPLE),
            "nothing occupied": make_home(),
        }
        for label, home in cases.items():
            with self.subTest(case=label):
                code, lines = MODULE.command_migrate(["mattpocock"], self.config(home))
                self.assertEqual(code, 0, "\n".join(lines))
                self.assertIn("Nothing was removed", "\n".join(lines))

    def test_migrate_without_a_named_library_refuses(self) -> None:
        with self.assertRaises(MODULE.ExternalLibraryError):
            MODULE.command_migrate([], self.config(make_home()))

    def test_migrate_stops_before_installing_when_removal_fails(self) -> None:
        home = self.occupied_home()
        calls: list[tuple[str, ...]] = []

        def failing_front_door(command, config):  # type: ignore[no-untyped-def]
            calls.append(tuple(command))
            return 1, [f"front door exited 1: {' '.join(command)}"]

        original = MODULE.run_front_door
        MODULE.run_front_door = failing_front_door  # type: ignore[assignment]
        try:
            code, lines = MODULE.command_migrate(
                ["mattpocock"], self.config(home, assume_yes=True)
            )
        finally:
            MODULE.run_front_door = original  # type: ignore[assignment]
        output = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("STOPPED before installing", output)
        # Exactly one call: the removal. The install must never have been attempted.
        self.assertEqual(len(calls), 1, calls)
        self.assertNotIn(MODULE.MATTPOCOCK.front_door, calls)

    def test_migrate_stops_when_removal_succeeds_but_names_are_still_occupied(self) -> None:
        # The partial-removal case: exit code 0, names still there. Installing now would be the
        # silent loss this module exists to prevent.
        home = self.occupied_home()
        calls: list[tuple[str, ...]] = []

        def lying_front_door(command, config):  # type: ignore[no-untyped-def]
            calls.append(tuple(command))
            return 0, ["front door completed"]

        original = MODULE.run_front_door
        MODULE.run_front_door = lying_front_door  # type: ignore[assignment]
        try:
            code, lines = MODULE.command_migrate(
                ["mattpocock"], self.config(home, assume_yes=True)
            )
        finally:
            MODULE.run_front_door = original  # type: ignore[assignment]
        output = "\n".join(lines)
        self.assertEqual(code, 1)
        self.assertIn("STOPPED before installing", output)
        self.assertIn("still occupied", output)
        self.assertEqual(len(calls), 1, calls)

    def test_migrate_installs_only_after_the_precheck_re_run_passes(self) -> None:
        home = self.occupied_home()
        calls: list[tuple[str, ...]] = []

        def removing_front_door(command, config):  # type: ignore[no-untyped-def]
            calls.append(tuple(command))
            # Emulate the other channel actually removing its links.
            if "remove" in command:
                for name in OCCUPIED_SAMPLE:
                    (home / ".claude" / "skills" / name).unlink()
            return 0, ["front door completed"]

        original = MODULE.run_front_door
        MODULE.run_front_door = removing_front_door  # type: ignore[assignment]
        try:
            code, lines = MODULE.command_migrate(
                ["mattpocock"], self.config(home, assume_yes=True)
            )
        finally:
            MODULE.run_front_door = original  # type: ignore[assignment]
        output = "\n".join(lines)
        self.assertEqual(code, 0, output)
        self.assertIn("precheck re-run after removal: passed", output)
        self.assertEqual(len(calls), 2, calls)
        self.assertEqual(calls[1], MODULE.MATTPOCOCK.front_door)

    def test_migration_makes_the_library_reachable_rather_than_a_dead_end(self) -> None:
        home = self.occupied_home()
        config = self.config(home)
        check = MODULE.precheck(MODULE.MATTPOCOCK, config)
        self.assertTrue(check.refused)
        self.assertEqual(len(check.migratable), len(OCCUPIED_SAMPLE))
        self.assertEqual(MODULE.library_state(check), "installable after migration")
        self.assertIn("libraries:migrate", MODULE.reach_command(check))

    def test_a_partly_unprovable_occupancy_is_not_advertised_as_migratable(self) -> None:
        lock = matt_lock(*OCCUPIED_SAMPLE[1:])
        home = make_home(names=OCCUPIED_SAMPLE, lock=lock)
        check = MODULE.precheck(MODULE.MATTPOCOCK, self.config(home))
        self.assertTrue(check.refused)
        self.assertNotEqual(MODULE.library_state(check), "installable after migration")
        self.assertIn("provably the same upstream", check.refusal)

    def test_a_partly_unprovable_occupancy_is_still_not_a_dead_end(self) -> None:
        # `migrate` correctly refuses here, but accepting the duplication is a real route, so
        # reporting "blocked / no route" would be wrong.
        lock = matt_lock(*OCCUPIED_SAMPLE[1:])
        home = make_home(names=OCCUPIED_SAMPLE, lock=lock)
        check = MODULE.precheck(MODULE.MATTPOCOCK, self.config(home))
        self.assertEqual(MODULE.library_state(check), "installable accepting duplication")
        self.assertIn("--allow-duplicate-channel", MODULE.reach_command(check))
        self.assertNotIn("no route", MODULE.reach_command(check))
        # And the route it names must actually work.
        cleared = MODULE.precheck(
            MODULE.MATTPOCOCK, self.config(home, allow_duplicate_channel=True)
        )
        self.assertFalse(cleared.refused, cleared.refusal)

    def test_no_deletion_primitive_appears_anywhere_in_the_module(self) -> None:
        # The removal must always go through the other channel's front door. A direct unlink or
        # rmtree here would be the whole safety argument collapsing.
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in (
            "shutil.rmtree",
            "os.unlink",
            "os.remove",
            ".unlink(",
            "rmdir",
            "rm -rf",
        ):
            self.assertNotIn(forbidden, text, f"{forbidden} must not appear")


class DryRunCommandTests(unittest.TestCase):
    """End-to-end verb behavior through the CLI. Nothing reaches the network."""

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def run_cli(self, *arguments: str, home: Path | None = None):
        target = home if home is not None else make_home()
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(target), *arguments],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )

    def test_list_renders_every_library_with_its_front_door_and_cost(self) -> None:
        result = self.run_cli("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ("mattpocock", "ecc", "hyperresearch"):
            self.assertIn(key, result.stdout)
        self.assertIn("claude plugins install mattpocock-skills", result.stdout)
        # Not `npx ecc-universal setup`: that bin does not exist in the published artifact.
        self.assertIn("ecc install --target claude", result.stdout)
        self.assertIn("uv tool install hyperresearch", result.stdout)
        self.assertIn("284", result.stdout)
        self.assertIn("Nothing below is installed by `bundle:install`", result.stdout)

    def test_install_is_dry_run_by_default_and_runs_nothing(self) -> None:
        result = self.run_cli("install", "mattpocock")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("No library was installed and no command was run", result.stdout)

    def run_cli_without_front_door_tools(self, *arguments: str):
        """Run the CLI as a machine with none of the front-door tools installed.

        run_cli inherits the developer's PATH, so a dev host with `claude` and `npx` on it
        never exercises the missing-front-door branch. A container replay from the public
        remote did, and the gate went red there while staying green here. PATH is therefore
        stripped to the interpreter's own directory plus the system ones.
        """
        environment = dict(os.environ)
        environment["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"])
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--home", str(make_home()), *arguments],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=environment,
        )

    def test_dry_run_describing_a_refusal_succeeds_on_a_machine_with_no_front_door(self) -> None:
        # Describing a refusal accurately IS the dry run's job, so it exits 0 even where the
        # front-door tool is absent. Anything else makes an honest answer look like a crash.
        for arguments in (("mattpocock",), ("ecc", "--acknowledge-ecc-surface"), ("hyperresearch",)):
            with self.subTest(library=arguments[0]):
                result = self.run_cli_without_front_door_tools("install", *arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("No library was installed and no command was run", result.stdout)

    def test_a_real_install_still_fails_when_the_front_door_is_absent(self) -> None:
        # The other half of the contract: with --yes a refusal means nothing was installed, so
        # the exit code must say so. This is what keeps the dry-run change above from being a
        # blanket softening.
        result = self.run_cli_without_front_door_tools("install", "hyperresearch", "--yes")
        self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_every_verb_survives_a_machine_with_no_front_door_tool_at_all(self) -> None:
        """The container's condition, asserted per verb rather than only for `install`.

        `shutil.which` is stubbed to None instead of stripping PATH, so the assertion holds even
        on a host where a tool sits in the interpreter's own directory — which is exactly how
        `claude` leaked back in and hid this defect during an earlier check.
        """
        original = MODULE.shutil.which
        MODULE.shutil.which = lambda tool: None  # type: ignore[assignment]
        self.addCleanup(setattr, MODULE.shutil, "which", original)
        home = make_home(
            links={n: f"../../.agents/skills/{n}" for n in OCCUPIED_SAMPLE},
            lock=matt_lock(*OCCUPIED_SAMPLE),
        )
        config = MODULE.Config(repo_root=ROOT, home=home)
        for label, call in (
            ("list", lambda c: MODULE.command_list(c)),
            ("status", lambda c: MODULE.command_status(c)),
            ("install", lambda c: MODULE.command_install(["mattpocock"], c)),
            ("install ecc", lambda c: MODULE.command_install(["ecc"], c)),
            ("install hyperresearch", lambda c: MODULE.command_install(["hyperresearch"], c)),
            ("migrate", lambda c: MODULE.command_migrate(["mattpocock"], c)),
            ("uninstall", lambda c: MODULE.command_uninstall(["hyperresearch"], c)),
        ):
            with self.subTest(verb=label):
                code, lines = call(config)
                self.assertEqual(code, 0, f"{label}:\n" + "\n".join(lines))

    def test_a_real_run_of_every_mutating_verb_fails_with_no_front_door_tool(self) -> None:
        # The paired half, so the test above cannot be satisfied by making everything exit 0.
        original = MODULE.shutil.which
        MODULE.shutil.which = lambda tool: None  # type: ignore[assignment]
        self.addCleanup(setattr, MODULE.shutil, "which", original)
        home = make_home(
            links={n: f"../../.agents/skills/{n}" for n in OCCUPIED_SAMPLE},
            lock=matt_lock(*OCCUPIED_SAMPLE),
        )
        config = MODULE.Config(repo_root=ROOT, home=home, assume_yes=True)
        for label, call in (
            ("install", lambda c: MODULE.command_install(["hyperresearch"], c)),
            ("migrate", lambda c: MODULE.command_migrate(["mattpocock"], c)),
            ("uninstall", lambda c: MODULE.command_uninstall(["hyperresearch"], c)),
        ):
            with self.subTest(verb=label):
                code, lines = call(config)
                output = "\n".join(lines)
                self.assertEqual(code, 1, f"{label}:\n{output}")
                # Every one of these must name the tool rather than failing opaquely.
                self.assertRegex(output, r"not (?:on|found on) PATH")

    def test_no_front_door_ever_runs_during_a_dry_run(self) -> None:
        # The property the exit code is a proxy for. If a dry run ever reached a subprocess, the
        # exit-code semantic would be describing something that already happened.
        calls: list[tuple[str, ...]] = []
        original = MODULE.run_front_door
        MODULE.run_front_door = lambda command, config: (  # type: ignore[assignment]
            calls.append(tuple(command)),
            (0, ["should not happen"]),
        )[1]
        self.addCleanup(setattr, MODULE, "run_front_door", original)
        home = make_home(
            links={n: f"../../.agents/skills/{n}" for n in OCCUPIED_SAMPLE},
            lock=matt_lock(*OCCUPIED_SAMPLE),
        )
        config = MODULE.Config(repo_root=ROOT, home=home)
        MODULE.command_install(["mattpocock"], config)
        MODULE.command_install(["ecc", "hyperresearch"], config)
        MODULE.command_migrate(["mattpocock"], config)
        MODULE.command_uninstall(["hyperresearch"], config)
        self.assertEqual(calls, [], f"a dry run invoked: {calls}")

    def test_dry_run_states_version_destination_and_surface_before_asking(self) -> None:
        result = self.run_cli("install", "mattpocock")
        self.assertIn("version:", result.stdout)
        self.assertIn("writes to:", result.stdout)
        self.assertIn("cost:", result.stdout)
        self.assertIn("front door:", result.stdout)
        self.assertIn("documented:", result.stdout)

    def test_install_without_a_named_library_refuses(self) -> None:
        result = self.run_cli("install")
        self.assertEqual(result.returncode, 2)
        self.assertIn("no verb that installs every library at once", result.stderr)

    def test_unknown_library_refuses_by_name(self) -> None:
        result = self.run_cli("install", "not-a-library")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown librar", result.stderr)

    def test_gstack_is_outside_the_supported_catalog(self) -> None:
        result = self.run_cli("install", "gstack", "--yes")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown librar", result.stderr)
        self.assertIn("gstack", result.stderr)
        self.assertNotIn("front door:", result.stdout)

    def test_refusal_is_reported_without_running_a_front_door(self) -> None:
        # The refusal must be VISIBLE and nothing may run. The exit code is deliberately 0
        # here: this is a dry run, and describing "a real install would refuse, because X" is
        # the dry run succeeding at its job. The nonzero exit belongs to a real --yes install,
        # asserted separately, where a refusal means nothing got installed.
        result = self.run_cli("install", "ecc")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("No library was installed and no command was run", result.stdout)

    def test_a_real_refused_install_exits_nonzero(self) -> None:
        result = self.run_cli("install", "ecc", "--yes")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("REFUSED", result.stdout)

    def test_all_three_libraries_are_reachable_by_a_named_command(self) -> None:
        # The deliverable: no library may be a dead end in `list`.
        result = self.run_cli("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("no route:", result.stdout)
        self.assertNotIn("[blocked]", result.stdout)
        for key in ("mattpocock", "ecc", "hyperresearch"):
            self.assertIn(f"libraries:install -- {key}", result.stdout)

    def test_list_reports_ecc_behind_its_surface_gate_not_as_blocked(self) -> None:
        result = self.run_cli("list")
        self.assertIn("ecc  [installable behind --acknowledge-ecc-surface]", result.stdout)

    def test_list_reports_a_migratable_library_as_installable_after_migration(self) -> None:
        home = make_home(
            names=OCCUPIED_SAMPLE, lock=matt_lock(*OCCUPIED_SAMPLE)
        )
        result = self.run_cli("list", home=home)
        self.assertIn("mattpocock  [installable after migration]", result.stdout)
        self.assertIn("libraries:migrate -- mattpocock", result.stdout)

    def test_ecc_dry_run_behind_its_gate_labels_the_precheck_skipped(self) -> None:
        result = self.run_cli("install", "ecc", "--acknowledge-ecc-surface")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SKIPPED, not passed", result.stdout)
        self.assertIn("VERSION GAP (accepted)", result.stdout)
        self.assertIn("DRY RUN", result.stdout)

    def test_migrate_requires_yes_through_the_cli(self) -> None:
        home = make_home(
            links={n: f"../../.agents/skills/{n}" for n in OCCUPIED_SAMPLE},
            lock=matt_lock(*OCCUPIED_SAMPLE),
        )
        result = self.run_cli("migrate", "mattpocock", home=home)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("Nothing was removed", result.stdout)
        for name in OCCUPIED_SAMPLE:
            self.assertTrue((home / ".claude" / "skills" / name).is_symlink(), name)

    def test_one_refusal_does_not_stop_the_other_named_library(self) -> None:
        result = self.run_cli("install", "ecc", "mattpocock")
        self.assertIn("=== ecc ===", result.stdout)
        self.assertIn("=== mattpocock ===", result.stdout)

    def test_status_reports_detection_without_claiming_provenance(self) -> None:
        result = self.run_cli("status", home=make_home(names=("tdd",)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("proves presence, not provenance", result.stdout)

    def test_uninstall_is_dry_run_and_scoped_to_the_librarys_own_path(self) -> None:
        result = self.run_cli("uninstall", "hyperresearch")
        self.assertIn("uv tool uninstall hyperresearch", result.stdout)
        self.assertIn("DRY RUN", result.stdout)

    def test_ecc_uninstall_runs_its_own_published_removal_verb(self) -> None:
        # The published artifact does expose `ecc uninstall`, so the earlier "no removal path"
        # refusal no longer matches the evidence. Asserted against the recorded row rather than
        # through the CLI, because reaching that line requires `npx` on PATH and this assertion
        # is about what is wired, not about what this host has installed.
        self.assertEqual(
            MODULE.ECC.uninstall,
            ("npx", "-y", "-p", "ecc-universal", "ecc", "uninstall", "--target", "claude"),
        )
        code, lines = MODULE.command_uninstall(
            ["ecc"], MODULE.Config(repo_root=ROOT, home=make_home())
        )
        self.assertEqual(code, 0)
        self.assertIn("DRY RUN", "\n".join(lines))

    def test_uninstall_still_refuses_a_library_with_no_removal_front_door(self) -> None:
        library = MODULE.Library(
            key="fixture",
            origin="https://example.invalid/fixture",
            licence="MIT",
            version="1.0.0",
            channel="home-skills",
            front_door=("true",),
            front_door_source="fixture",
            requires=(),
            names=("fixture-only",),
        )
        original = dict(MODULE.LIBRARIES)
        MODULE.LIBRARIES["fixture"] = library
        try:
            # Under --yes, so the refusal is this run's failure rather than a description.
            code, lines = MODULE.command_uninstall(
                ["fixture"],
                MODULE.Config(repo_root=ROOT, home=make_home(), assume_yes=True),
            )
        finally:
            MODULE.LIBRARIES.clear()
            MODULE.LIBRARIES.update(original)
        self.assertEqual(code, 1)
        self.assertIn("no uninstall front door is wired", "\n".join(lines))

    def test_missing_front_door_tool_fails_closed_with_a_named_reason(self) -> None:
        # PATH is emptied so `claude` cannot resolve; the refusal must name the tool
        # rather than surfacing an opaque subprocess error.
        home = make_home()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--home",
                str(home),
                "install",
                "mattpocock",
                "--yes",
                "--allow-duplicate-channel",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env={"PATH": "", "HOME": str(home)},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("front-door tool not found on PATH", result.stdout)
        self.assertIn("claude", result.stdout)


class SecondFrontDoorTests(unittest.TestCase):
    """mattpocock has TWO legitimate doors, and they differ in prerequisite rather than payload.

    The marketplace door needs an authenticated Claude Code session — executed 2026-08-20 on a
    logged-out Claude Code 2.1.238, `claude plugin marketplace list` prints "No marketplaces
    configured" and the install fails not-found-in-any-configured-marketplace. The `skills` CLI
    door needs no Claude session at all. Nothing here reaches the network: the marketplace state
    is a fixture file and every front door is stubbed.
    """

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def config(self, home: Path, **overrides: object) -> object:
        return MODULE.Config(repo_root=ROOT, home=home, **overrides)  # type: ignore[arg-type]

    def marketplace_home(self, *names: str) -> Path:
        """A home whose Claude plugin state configures exactly ``names`` marketplaces.

        No names writes no file, which is precisely the logged-out shape: the real file is absent
        on a home that has never authenticated, and `marketplace list` reports none.
        """
        home = make_home()
        if names:
            plugins = home / ".claude" / "plugins"
            plugins.mkdir(parents=True, exist_ok=True)
            (plugins / "known_marketplaces.json").write_text(
                json.dumps({name: {"source": f"{name}/source"} for name in names}),
                encoding="utf-8",
            )
        return home

    def stub_which(self, present: tuple[str, ...]) -> None:
        original = MODULE.shutil.which
        MODULE.shutil.which = (  # type: ignore[assignment]
            lambda tool: f"/usr/bin/{tool}" if tool in present else None
        )
        self.addCleanup(setattr, MODULE.shutil, "which", original)

    def test_the_skills_cli_command_is_exactly_the_observed_grammar(self) -> None:
        # Every token here was read off `npx -y skills@latest --help` (CLI 1.5.23), not a README:
        # `add <package>`, then Add Options -g/--global, -a/--agent, -s/--skill ("use '*' for all
        # skills"), -y/--yes. `--agent claude-code` is the same one-host scoping the removal front
        # door uses, so this door cannot fan out across every agent that CLI knows.
        self.assertEqual(
            MODULE.skills_cli_command(MODULE.MATTPOCOCK, "npx"),
            (
                "npx",
                "-y",
                "skills@latest",
                "add",
                "mattpocock/skills",
                "--global",
                "--agent",
                "claude-code",
                "--skill",
                "*",
                "--yes",
            ),
        )

    def test_the_package_spec_is_the_other_channels_own_lock_source(self) -> None:
        # Drift-proofing: the spec `skills add` takes is the same string that channel's lock
        # records, so it is read from `lock_source` rather than duplicated as a second literal.
        command = MODULE.skills_cli_command(MODULE.MATTPOCOCK, "npx")
        self.assertIn(MODULE.MATTPOCOCK.lock_source, command)
        self.assertEqual(command[command.index("add") + 1], MODULE.MATTPOCOCK.lock_source)

    def test_bunx_carries_no_npm_only_flag_and_is_used_when_npx_is_absent(self) -> None:
        # Both runners come from tools this repo already pins, so naming them adds no
        # prerequisite. `bunx skills@latest --version` was executed and reported the same CLI
        # version as npx; bunx has no `-y`, so passing npm's flag to it would be a guess.
        self.stub_which(("bunx",))
        self.assertEqual(MODULE.skills_cli_runner(), "bunx")
        command = MODULE.skills_cli_command(MODULE.MATTPOCOCK, MODULE.skills_cli_runner())
        self.assertEqual(command[0], "bunx")
        self.assertNotIn("-y", command)
        self.assertIn("--yes", command)

    def test_npx_is_preferred_when_both_runners_are_present(self) -> None:
        self.stub_which(("npx", "bunx"))
        self.assertEqual(MODULE.skills_cli_runner(), "npx")

    def test_neither_runner_present_is_reported_missing_rather_than_guessed(self) -> None:
        self.stub_which(())
        self.assertEqual(MODULE.skills_cli_runner(), "")
        report = "\n".join(
            MODULE.cli_alternative_report(MODULE.MATTPOCOCK, self.config(make_home()))
        )
        self.assertIn("MISSING", report)
        self.assertIn("npx", report)
        self.assertIn("bunx", report)

    def test_the_printed_command_quotes_the_glob_the_argv_passes_literally(self) -> None:
        # The argv is literal because nothing here uses a shell. The PRINTED line is pasted into
        # one, where a bare `*` expands against the operator's directory and becomes a different
        # command, so the two representations must differ in exactly this way.
        command = MODULE.skills_cli_command(MODULE.MATTPOCOCK, "npx")
        self.assertIn("*", command)
        self.assertIn("--skill '*'", MODULE.paste_safe(command))

    def test_an_unconfigured_marketplace_directs_at_the_second_door(self) -> None:
        config = self.config(self.marketplace_home())
        report = "\n".join(MODULE.cli_alternative_report(MODULE.MATTPOCOCK, config))
        self.assertIn("marketplaces: NONE configured", report)
        self.assertIn("AUTHENTICATED Claude Code session", report)
        self.assertIn("DIRECTED", report)
        self.assertIn("skills@latest add mattpocock/skills", report)

    def test_a_configured_marketplace_keeps_the_marketplace_door_primary(self) -> None:
        # The paired positive control: the direction above must be a consequence of the empty
        # state rather than something this always prints.
        config = self.config(self.marketplace_home("claude-plugins-official"))
        report = "\n".join(MODULE.cli_alternative_report(MODULE.MATTPOCOCK, config))
        self.assertIn("stays primary", report)
        self.assertNotIn("DIRECTED", report)
        self.assertNotIn("marketplaces: NONE", report)
        # The second door is still named — it is an alternative, not a consolation prize.
        self.assertIn("second door:", report)

    def test_a_corrupt_or_absent_marketplace_file_reads_as_none_configured(self) -> None:
        for label, payload in (
            ("not json", "{not json"),
            ("not an object", "[]"),
        ):
            with self.subTest(case=label):
                home = make_home()
                plugins = home / ".claude" / "plugins"
                plugins.mkdir(parents=True, exist_ok=True)
                (plugins / "known_marketplaces.json").write_text(payload, encoding="utf-8")
                self.assertEqual(
                    MODULE.configured_marketplaces(self.config(home)), ()
                )
                # Read-only: the file the operator's Claude Code owns is never rewritten.
                self.assertEqual(
                    (plugins / "known_marketplaces.json").read_text(encoding="utf-8"), payload
                )

    def test_a_failed_marketplace_install_names_both_the_prerequisite_and_the_other_door(
        self,
    ) -> None:
        # The seed's whole point: a not-found from an empty marketplace must not read as "this
        # library is unreachable". The hint has to carry BOTH halves — why it failed, and the
        # door that does not need what is missing.
        self.stub_which(("claude", "npx"))
        home = self.marketplace_home()
        original = MODULE.run_front_door
        MODULE.run_front_door = lambda command, config: (  # type: ignore[assignment]
            1,
            ["front door exited 1: " + " ".join(command)],
        )
        self.addCleanup(setattr, MODULE, "run_front_door", original)
        code, lines = MODULE.command_install(
            ["mattpocock"], self.config(home, assume_yes=True)
        )
        output = "\n".join(lines)
        self.assertEqual(code, 1, output)
        self.assertIn("install FAILED for mattpocock", output)
        self.assertIn("AUTHENTICATED Claude Code session", output)
        self.assertIn("npx -y skills@latest add mattpocock/skills", output)
        self.assertIn("FLAT names into", output)

    def test_the_failure_hint_is_silent_when_a_marketplace_is_configured(self) -> None:
        # Positive control for the guard: with a marketplace present the failure has some other
        # cause, and inventing the authentication explanation would be a lie.
        self.stub_which(("claude", "npx"))
        home = self.marketplace_home("claude-plugins-official")
        original = MODULE.run_front_door
        MODULE.run_front_door = lambda command, config: (  # type: ignore[assignment]
            1,
            ["front door exited 1: " + " ".join(command)],
        )
        self.addCleanup(setattr, MODULE, "run_front_door", original)
        code, lines = MODULE.command_install(
            ["mattpocock"], self.config(home, assume_yes=True)
        )
        output = "\n".join(lines)
        self.assertEqual(code, 1, output)
        self.assertIn("install FAILED for mattpocock", output)
        self.assertNotIn("AUTHENTICATED Claude Code session", output)
        self.assertNotIn("second door, which needs no Claude Code session", output)

    def test_the_second_door_is_printed_and_never_invoked(self) -> None:
        # The boundary: the precheck that ran is the plugin channel's. This door writes flat
        # names, so invoking it from here would install behind a precheck that never looked at
        # its namespace — exactly the silent loss the module exists to prevent.
        self.stub_which(("claude", "npx"))
        calls: list[tuple[str, ...]] = []
        original = MODULE.run_front_door
        MODULE.run_front_door = lambda command, config: (  # type: ignore[assignment]
            calls.append(tuple(command)),
            (1, ["front door exited 1"]),
        )[1]
        self.addCleanup(setattr, MODULE, "run_front_door", original)
        MODULE.command_install(
            ["mattpocock"], self.config(self.marketplace_home(), assume_yes=True)
        )
        self.assertEqual(calls, [MODULE.MATTPOCOCK.front_door], calls)
        cli_door = MODULE.skills_cli_command(MODULE.MATTPOCOCK, "npx")
        self.assertNotIn(cli_door, calls)

    def test_a_library_with_one_door_prints_no_second_one(self) -> None:
        config = self.config(make_home())
        for library in (MODULE.ECC, MODULE.HYPERRESEARCH):
            with self.subTest(library=library.key):
                self.assertEqual(library.cli_alternative, "")
                self.assertEqual(MODULE.cli_alternative_report(library, config), [])
                self.assertEqual(MODULE.empty_marketplace_hint(library, config), [])

    def test_the_dry_run_shows_both_doors_without_running_either(self) -> None:
        self.stub_which(("claude", "npx"))
        calls: list[tuple[str, ...]] = []
        original = MODULE.run_front_door
        MODULE.run_front_door = lambda command, config: (  # type: ignore[assignment]
            calls.append(tuple(command)),
            (0, ["should not happen"]),
        )[1]
        self.addCleanup(setattr, MODULE, "run_front_door", original)
        code, lines = MODULE.command_install(
            ["mattpocock"], self.config(self.marketplace_home())
        )
        output = "\n".join(lines)
        self.assertEqual(code, 0, output)
        self.assertIn("front door:   claude plugins install mattpocock-skills", output)
        self.assertIn("second door:  npx -y skills@latest add mattpocock/skills", output)
        self.assertIn("DRY RUN", output)
        self.assertEqual(calls, [], f"a dry run invoked: {calls}")


class RecordedAgentSetTests(unittest.TestCase):
    """hyperresearch's agent set is a recorded fixture, because its front door enumerates nothing.

    `hyperresearch --help` at 0.10.0 exposes install/setup/init/status/... and no verb that lists
    what `install --global` renders, and `install --help` has no --dry-run, so there is no offline
    oracle to derive the expected set from at status time. That makes the hardcoded row the only
    source — and it silently drifted two files behind this same upstream version once. These
    tests are the named failure the next drift gets instead of a quiet under-count.
    """

    def tearDown(self) -> None:
        while make_home.cleanups:  # type: ignore[attr-defined]
            make_home.cleanups.pop().cleanup()  # type: ignore[attr-defined]

    def test_the_row_matches_the_set_recorded_from_the_executed_install(self) -> None:
        self.assertEqual(MODULE.HYPERRESEARCH.extra_agents, RECORDED_HYPERRESEARCH_AGENTS)
        self.assertEqual(len(RECORDED_HYPERRESEARCH_AGENTS), 16)
        # The version this set was recorded against must travel with it: a refreshed list under a
        # stale version number would be the same lie in the other direction.
        self.assertEqual(MODULE.HYPERRESEARCH.version, RECORDED_HYPERRESEARCH_VERSION)

    def test_the_two_files_the_stale_list_omitted_are_present(self) -> None:
        # Named explicitly rather than left to the tuple comparison, so the regression this fixes
        # is legible in the failure output rather than as a diff of sixteen strings.
        for name in ("hyperresearch-browser-fetcher", "hyperresearch-cite-checker"):
            self.assertIn(name, MODULE.HYPERRESEARCH.extra_agents, name)

    def test_status_counts_the_whole_recorded_set_when_the_home_holds_it(self) -> None:
        home = make_home()
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        for name in RECORDED_HYPERRESEARCH_AGENTS:
            (agents / f"{name}.md").write_text("", encoding="utf-8")
        code, lines = MODULE.command_status(MODULE.Config(repo_root=ROOT, home=home))
        output = "\n".join(lines)
        self.assertEqual(code, 0, output)
        self.assertIn("agents: 16/16 of the recorded 0.10.0 set present", output)
        self.assertNotIn("does not name", output)

    def test_status_reports_a_prefixed_agent_file_the_recorded_set_does_not_name(self) -> None:
        # The operator-facing half of the fix. A test only fails for whoever runs this gate; an
        # upstream release that adds an agent file changes the surface in a HOME, so status has
        # to notice the residue rather than reporting a complete-looking N/N.
        home = make_home()
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        for name in RECORDED_HYPERRESEARCH_AGENTS:
            (agents / f"{name}.md").write_text("", encoding="utf-8")
        (agents / "hyperresearch-future-role.md").write_text("", encoding="utf-8")
        _, lines = MODULE.command_status(MODULE.Config(repo_root=ROOT, home=home))
        output = "\n".join(lines)
        self.assertIn("1 further hyperresearch-prefixed file(s)", output)
        self.assertIn("hyperresearch-future-role.md", output)
        self.assertIn("the surface is wider than the count above", output)

    def test_an_unrelated_agent_file_is_not_claimed_as_drift(self) -> None:
        # The paired control: the residue check is scoped by the library's own name prefix, so a
        # foreign agent file in the same directory is nobody's drift.
        home = make_home()
        agents = home / ".claude" / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        (agents / "some-other-agent.md").write_text("", encoding="utf-8")
        _, lines = MODULE.command_status(MODULE.Config(repo_root=ROOT, home=home))
        output = "\n".join(lines)
        self.assertNotIn("some-other-agent", output)
        self.assertNotIn("further hyperresearch-prefixed", output)


class IsolationFromInstallPathTests(unittest.TestCase):
    """No verb here may be reachable from bundle:install, setup, or any gate leaf."""

    def test_no_install_or_gate_task_depends_on_a_libraries_task(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tasks = config["tasks"]
        library_tasks = {name for name in tasks if name.startswith("libraries:")}
        self.assertEqual(
            library_tasks,
            {
                "libraries:list",
                "libraries:install",
                "libraries:status",
                "libraries:migrate",
            },
        )
        for name, task in tasks.items():
            if name.startswith("libraries:"):
                continue
            depends = task.get("depends", []) if isinstance(task, dict) else []
            for dependency in depends:
                self.assertNotIn(
                    dependency,
                    library_tasks,
                    f"task {name} must not depend on {dependency}",
                )

    def test_no_libraries_task_is_reachable_transitively_from_setup_or_check(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tasks = config["tasks"]

        def reachable(start: str, seen: set[str]) -> set[str]:
            task = tasks.get(start, {})
            for dependency in task.get("depends", []) if isinstance(task, dict) else []:
                if dependency not in seen:
                    seen.add(dependency)
                    reachable(dependency, seen)
            return seen

        for root_task in (
            "contributor:setup",
            "setup",
            "check",
            "bundle:install",
            "test",
            "self-test",
        ):
            closure = reachable(root_task, set())
            self.assertFalse(
                {name for name in closure if name.startswith("libraries:")},
                f"{root_task} must not reach a libraries task: {closure}",
            )

    def test_the_installer_module_is_imported_by_no_shipped_script(self) -> None:
        # A mention is fine — validate_bundle.py legitimately pins the task command strings.
        # An import is not: it would put these verbs in another script's reach.
        pattern = re.compile(
            r"^\s*(?:import\s+install_external_libraries"
            r"|from\s+install_external_libraries\s+import"
            r"|from\s+scripts(?:\.\w+)*\s+import\s+install_external_libraries)",
            re.MULTILINE,
        )
        for source in sorted((ROOT / "scripts").glob("*.py")):
            if source.name == "install_external_libraries.py":
                continue
            text = source.read_text(encoding="utf-8")
            self.assertIsNone(pattern.search(text), source.name)
            self.assertNotIn("install_external_libraries.py install --yes", text)

    def test_the_installer_makes_no_network_call_of_its_own(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for forbidden in ("urllib", "http.client", "requests", "socket", "ssl"):
            self.assertNotIn(
                f"import {forbidden}", text, f"{forbidden} must not be imported"
            )

    def test_no_credential_surface(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("--api-key", "--token", "getpass", "authorization:"):
            self.assertNotIn(forbidden, text)


class SkillContractTests(unittest.TestCase):
    """The skill's mechanical floor from AGENTS.md, checked here as well as in the gate."""

    def frontmatter_description(self) -> str:
        text = SKILL.read_text(encoding="utf-8")
        block = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        assert block
        metadata = block.group(1)
        match = re.search(r"^description:\s*(.*)$", metadata, re.MULTILINE)
        assert match
        lines = metadata[match.end() :].splitlines()
        if lines and not lines[0]:
            lines = lines[1:]
        continuation: list[str] = []
        for line in lines:
            if not line.strip():
                continuation.append("")
                continue
            if not line.startswith((" ", "\t")):
                break
            continuation.append(line.strip())
        return " ".join(continuation).strip()

    def test_name_equals_directory(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        name = re.search(r"^name:\s*(.*)$", text, re.MULTILINE)
        assert name
        self.assertEqual(name.group(1).strip(), SKILL.parent.name)

    def test_description_is_within_the_hard_cap(self) -> None:
        self.assertLessEqual(len(self.frontmatter_description()), 1024)

    def test_description_names_its_nearest_neighbor(self) -> None:
        # Gate 1 of the four-gate test: the description alone must let a selector reject
        # the neighbor that owns the adjacent ground.
        description = self.frontmatter_description()
        self.assertIn("agentic-sdlc", description)
        self.assertIn("skill-authoring", description)

    def test_skill_declares_the_never_vendor_boundary(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        self.assertIn("never vendors", body)
        self.assertIn("evidence, not authorization", body)

    def test_referenced_files_exist(self) -> None:
        body = SKILL.read_text(encoding="utf-8")
        for reference in sorted(set(re.findall(r"\breferences/[A-Za-z0-9._-]+\.md", body))):
            self.assertTrue((SKILL.parent / reference).is_file(), reference)

    def test_skill_states_both_mattpocock_doors_and_the_authentication_split(self) -> None:
        # The doctrine half of the fix: the row must not read as one door, and it must name the
        # prerequisite that makes the marketplace one fail on a logged-out host.
        body = SKILL.read_text(encoding="utf-8")
        self.assertIn("claude plugins install mattpocock-skills", body)
        self.assertIn("skills@latest add mattpocock/skills", body)
        self.assertIn("authenticated", body)
        self.assertIn("No marketplaces configured", body)
        # And it must not still claim the marketplace needs nothing first.
        self.assertNotIn(
            "already listed, so there is no `marketplace add` step to run first", body
        )

    def test_skill_agent_count_matches_the_recorded_set_in_the_module(self) -> None:
        # The count in prose is the thing that rotted: it said 14 while upstream shipped 16. Tie
        # it to the module's own row so a refresh in one place cannot leave the other stale.
        body = SKILL.read_text(encoding="utf-8")
        self.assertIn(f"{len(MODULE.HYPERRESEARCH.extra_agents)} agents", body)
        self.assertNotIn("17 skills + 14 agents", body)

    def test_no_static_model_or_effort_pin(self) -> None:
        block = re.match(r"^---\n(.*?)\n---", SKILL.read_text(encoding="utf-8"), re.DOTALL)
        assert block
        for forbidden in ("model:", "model_reasoning_effort:"):
            self.assertNotIn(forbidden, block.group(1))


if __name__ == "__main__":
    unittest.main()
