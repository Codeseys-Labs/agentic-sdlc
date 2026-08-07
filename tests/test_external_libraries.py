from __future__ import annotations

import importlib.util
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


def make_home(names: tuple[str, ...] = (), links: dict[str, str] | None = None) -> Path:
    """Build a throwaway home whose skills dir holds exactly ``names`` plus ``links``."""
    temporary = tempfile.TemporaryDirectory()
    home = Path(temporary.name) / "home"
    skills = home / ".claude" / "skills"
    skills.mkdir(parents=True)
    for name in names:
        (skills / name).mkdir()
    for name, target in (links or {}).items():
        (skills / name).symlink_to(target)
    make_home.cleanups.append(temporary)
    return home


make_home.cleanups = []  # type: ignore[attr-defined]


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

    def test_ecc_is_blocked_on_version_and_unenumerable_surface(self) -> None:
        check = MODULE.precheck(MODULE.ECC, self.config(make_home()))
        self.assertTrue(check.refused)
        self.assertIn("2.2.0", check.refusal)
        self.assertIn("284", check.refusal)

    def test_ecc_acknowledgement_alone_does_not_clear_the_block(self) -> None:
        check = MODULE.precheck(
            MODULE.ECC, self.config(make_home(), acknowledge_ecc_surface=True)
        )
        self.assertTrue(check.refused)

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
        self.assertIn("npx ecc-universal setup", result.stdout)
        self.assertIn("uv tool install hyperresearch", result.stdout)
        self.assertIn("284", result.stdout)
        self.assertIn("Nothing below is installed by `bundle:install`", result.stdout)

    def test_install_is_dry_run_by_default_and_runs_nothing(self) -> None:
        result = self.run_cli("install", "mattpocock")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("No library was installed and no command was run", result.stdout)

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

    def test_refused_library_exits_nonzero_without_running_a_front_door(self) -> None:
        result = self.run_cli("install", "ecc")
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stdout)

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

    def test_uninstall_refuses_when_no_removal_front_door_exists(self) -> None:
        result = self.run_cli("uninstall", "ecc")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no uninstall front door is wired", result.stdout)

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


class IsolationFromInstallPathTests(unittest.TestCase):
    """No verb here may be reachable from bundle:install, setup, or any gate leaf."""

    def test_no_install_or_gate_task_depends_on_a_libraries_task(self) -> None:
        config = tomllib.loads((ROOT / "mise.toml").read_text(encoding="utf-8"))
        tasks = config["tasks"]
        library_tasks = {name for name in tasks if name.startswith("libraries:")}
        self.assertEqual(
            library_tasks, {"libraries:list", "libraries:install", "libraries:status"}
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

        for root_task in ("setup", "check", "bundle:install", "test", "self-test"):
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

    def test_no_static_model_or_effort_pin(self) -> None:
        block = re.match(r"^---\n(.*?)\n---", SKILL.read_text(encoding="utf-8"), re.DOTALL)
        assert block
        for forbidden in ("model:", "model_reasoning_effort:"):
            self.assertNotIn(forbidden, block.group(1))


if __name__ == "__main__":
    unittest.main()
