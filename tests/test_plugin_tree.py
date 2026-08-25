"""`plugin/` publishes real copies of the component trees, and drift in it fails the gate.

Why copies, and why a gate rule rather than a comment: as committed symlinks, the five component
directories cost two defects measured on Claude Code 2.1.245 (agentic-sdlc-d0ab).
`claude plugin validate ./plugin --strict` exited 1 with "This directory is a symlink and nothing
in it was read" for `skills`, `agents`, and `commands` — and never walked `output-styles` or
`workflows` at all, because the manifest declared no field for them.  Worse, a materialisation
carrying only the plugin subtree (what a `github`/`archive` source fetches, reproducible offline
with `git archive HEAD plugin | tar -x`) left every link dangling, and the host installed that at
exit 0 while reporting `Skills (0)  Agents (0)`.  Copies fix both halves and introduce exactly one
new failure mode — a second tree that can go stale — so every test below either proves the copies
equal their sources or proves the checker REFUSES a difference.  A test that only asserted the
tree is currently in sync would pass just as well if the checker were blind.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SYNC_PATH = ROOT / "scripts" / "sync_plugin_tree.py"
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"
MANIFEST = ROOT / "plugin" / ".claude-plugin" / "plugin.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = _load("plugin_tree_sync", SYNC_PATH)
validator = _load("plugin_tree_validator", VALIDATOR_PATH)

def _execute_bit_is_observable() -> bool:
    """Whether this filesystem carries the one mode bit the mirror publishes and compares.

    `sync` reads `stat().st_mode & 0o100` on both sides, and a Windows filesystem never sets it:
    `chmod(path, 0o755)` cannot grant it and `chmod(path, 0o644)` cannot take it away, so the
    fixture cannot establish its own premise and removing the bit is a no-op the checker correctly
    reports as no drift. Measured as `0 is not true` and `0 != 1` on windows-2025
    (agentic-sdlc-5ce7). Git's own record of that bit lives in the INDEX there rather than on disk,
    so reading it would be a different checker rather than a fixed one, and the mirror gate that
    publishes runs on Linux.

    Probed on a real temporary file instead of branching on `os.name`, so a POSIX host that also
    cannot honour the bit is reported the same way and for the same stated reason.
    """
    with tempfile.NamedTemporaryFile(suffix="-execute-bit-probe", delete=False) as handle:
        probe = Path(handle.name)
    try:
        os.chmod(probe, 0o755)
        return bool(os.stat(probe).st_mode & 0o100)
    finally:
        probe.unlink(missing_ok=True)


EXECUTE_BIT_IS_OBSERVABLE = _execute_bit_is_observable()
EXECUTE_BIT_SKIP_REASON = (
    "this filesystem does not carry the owner-execute bit the plugin mirror publishes and "
    "compares, so the drift this asserts cannot be created here (agentic-sdlc-5ce7)"
)


class ShippedTreeTest(unittest.TestCase):
    """Assertions about the tree this repository actually publishes."""

    def test_no_component_directory_is_a_committed_symlink(self) -> None:
        """The durable form of defect (a): a tracked mode-120000 entry under `plugin/`."""
        staged = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--stage", "plugin"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        self.assertTrue(staged, "plugin/ must be tracked")
        links = [line for line in staged if line.startswith("120000 ")]
        self.assertEqual(links, [], "plugin/ must publish files, not symlinks")

    def test_the_shipped_tree_equals_its_sources(self) -> None:
        self.assertEqual(sync.differences(ROOT), [])

    def test_the_tracked_mirror_equals_the_tracked_sources(self) -> None:
        """Git is the oracle here, deliberately: mode and blob per path, read from the index.

        Asking the product what it publishes and then comparing that to itself would pass for any
        walk it implemented.  Comparing two sets git already knows also states the property the
        release archive depends on, since `build_release.py` reads the committed tree.
        """
        index: dict[str, tuple[str, str]] = {}
        for line in subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--stage", "plugin", *(source for _, source in sync.COMPONENTS)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines():
            metadata, path = line.split("\t", 1)
            mode, blob, _ = metadata.split()
            index[path] = (mode, blob)
        for destination, relative in sync.COMPONENTS:
            sources = {
                path[len(relative) + 1 :]: value
                for path, value in index.items()
                if path.startswith(f"{relative}/")
            }
            published = {
                path[len(f"plugin/{destination}") + 1 :]: value
                for path, value in index.items()
                if path.startswith(f"plugin/{destination}/")
            }
            self.assertTrue(sources, relative)
            self.assertEqual(published, sources, destination)

    def test_the_plan_covers_exactly_the_five_component_destinations(self) -> None:
        self.assertEqual(
            {relative.split("/")[1] for relative in sync.plan(ROOT)},
            {destination for destination, _ in sync.COMPONENTS},
        )

    def test_the_manifest_declares_the_two_kinds_no_component_walk_would_find(self) -> None:
        """`output-styles` and `workflows` are not autodiscovered: undeclared, they are unwalked."""
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["outputStyles"], "./output-styles")
        self.assertEqual(manifest["workflows"], "./workflows")
        # A plugin's hooks surface auto-enables with the plugin, which this plane refuses; the
        # field is also measured to produce a `Hook load failed` while install exits 0.
        self.assertNotIn("hooks", manifest)

    def test_the_root_and_plugin_manifests_stay_byte_identical(self) -> None:
        self.assertEqual(
            (ROOT / ".claude-plugin" / "plugin.json").read_bytes(),
            MANIFEST.read_bytes(),
        )


class FixtureTest(unittest.TestCase):
    """Drift and refusal, on a fixture root, so no assertion mutates the real tree."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        for destination, relative in sync.COMPONENTS:
            directory = self.root / relative
            directory.mkdir(parents=True)
            (directory / f"{destination}-entry.md").write_text(f"{destination}\n", encoding="utf-8")
        (self.root / "plugin" / ".claude-plugin").mkdir(parents=True)
        (self.root / "plugin" / ".claude-plugin" / "plugin.json").write_text("{}\n", encoding="utf-8")
        self.executable = self.root / "skills" / "tool.py"
        self.executable.write_text("print('tool')\n", encoding="utf-8")
        os.chmod(self.executable, 0o755)

    def run_sync(self, *arguments: str) -> int:
        """Exit code is the assertion here, so the writer's report is captured, not printed."""
        with io.StringIO() as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return sync.main([*arguments, "--root", str(self.root)])

    def published(self, relative: str) -> Path:
        return self.root / "plugin" / relative

    def test_write_materialises_every_source_file_and_check_then_passes(self) -> None:
        self.assertEqual(self.run_sync("--check"), sync.EXIT_REFUSAL)
        self.assertEqual(self.run_sync("--write"), sync.EXIT_OK)
        self.assertEqual(self.run_sync("--check"), sync.EXIT_OK)
        for destination, _ in sync.COMPONENTS:
            self.assertTrue(self.published(f"{destination}/{destination}-entry.md").is_file())
        # The materialisation above is platform-neutral and stays asserted everywhere; only the
        # mode half is not, so it is guarded rather than skipping the whole claim.
        if EXECUTE_BIT_IS_OBSERVABLE:
            self.assertTrue(os.stat(self.published("skills/tool.py")).st_mode & 0o100)
        self.assertFalse(os.stat(self.published("skills/skills-entry.md")).st_mode & 0o100)

    def test_write_is_idempotent(self) -> None:
        self.run_sync("--write")
        before = {
            path: path.read_bytes()
            for path in sorted((self.root / "plugin").rglob("*"))
            if path.is_file()
        }
        self.assertEqual(sync.materialise(self.root), [])
        after = {
            path: path.read_bytes()
            for path in sorted((self.root / "plugin").rglob("*"))
            if path.is_file()
        }
        self.assertEqual(before, after)

    def test_check_refuses_changed_content_and_write_repairs_it(self) -> None:
        self.run_sync("--write")
        self.published("commands/commands-entry.md").write_text("edited\n", encoding="utf-8")
        drift = sync.differences(self.root)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("plugin/commands/commands-entry.md", drift[0])
        self.assertIn("content differs", drift[0])
        self.assertEqual(self.run_sync("--check"), sync.EXIT_REFUSAL)
        self.assertEqual(self.run_sync("--write"), sync.EXIT_OK)
        self.assertEqual(sync.differences(self.root), [])

    def test_check_refuses_a_missing_copy(self) -> None:
        self.run_sync("--write")
        self.published("agents/agents-entry.md").unlink()
        drift = sync.differences(self.root)
        self.assertEqual(drift, ["plugin/agents/agents-entry.md: missing"])

    @unittest.skipUnless(EXECUTE_BIT_IS_OBSERVABLE, EXECUTE_BIT_SKIP_REASON)
    def test_check_refuses_a_copy_that_lost_its_execute_bit(self) -> None:
        """Git tracks exactly this one mode bit, so a published script must keep it."""
        self.run_sync("--write")
        os.chmod(self.published("skills/tool.py"), 0o644)
        drift = sync.differences(self.root)
        self.assertEqual(len(drift), 1, drift)
        self.assertIn("execute bit differs", drift[0])

    def test_check_refuses_a_file_no_source_tree_publishes(self) -> None:
        self.run_sync("--write")
        self.published("workflows/orphan.js").write_text("// orphan\n", encoding="utf-8")
        drift = sync.differences(self.root)
        self.assertEqual(drift, ["plugin/workflows/orphan.js: published by no source tree"])

    def test_check_refuses_a_symlink_anywhere_under_a_published_tree(self) -> None:
        """The defect itself: a link is what the host reads as an empty component directory."""
        self.run_sync("--write")
        link = self.published("skills/linked.md")
        link.symlink_to(self.root / "skills" / "skills-entry.md")
        self.assertIn("is a symlink", " ".join(sync.differences(self.root)))
        link.unlink()

        shutil.rmtree(self.published("skills"))
        self.published("skills").symlink_to(self.root / "skills", target_is_directory=True)
        drift = sync.differences(self.root)
        self.assertIn("plugin/skills: is a symlink", " ".join(drift))

    def test_write_unlinks_a_component_symlink_without_touching_its_target(self) -> None:
        """The pre-fix shape.  Walking into the link to delete it would delete the source tree."""
        shutil.rmtree(self.published("skills"), ignore_errors=True)
        self.published("skills").parent.mkdir(parents=True, exist_ok=True)
        self.published("skills").symlink_to(self.root / "skills", target_is_directory=True)
        self.assertEqual(self.run_sync("--write"), sync.EXIT_OK)
        self.assertFalse(self.published("skills").is_symlink())
        self.assertTrue((self.root / "skills" / "skills-entry.md").is_file())
        self.assertEqual(sync.differences(self.root), [])

    def test_a_symlink_inside_a_source_tree_is_refused_rather_than_published(self) -> None:
        """Copying through it could publish bytes from outside the repository; skipping it
        silently is the same invisible-omission class the mirror exists to end."""
        (self.root / "skills" / "escape.md").symlink_to(Path("/etc/hostname"))
        with self.assertRaises(sync.PluginTreeError) as raised:
            sync.plan(self.root)
        self.assertIn("skills/escape.md", str(raised.exception))

    def test_a_missing_source_tree_is_refused_by_name(self) -> None:
        shutil.rmtree(self.root / "output-styles")
        with self.assertRaises(sync.PluginTreeError) as raised:
            sync.differences(self.root)
        self.assertIn("output-styles", str(raised.exception))


class GateWiringTest(unittest.TestCase):
    """The validator must report drift, and must name the command that repairs it."""

    def test_the_gate_rule_is_clean_on_the_shipped_tree(self) -> None:
        result = validator.Validation()
        validator.validate_plugin_tree(ROOT, result)
        self.assertEqual(result.errors, [])

    def test_the_gate_rule_reports_drift_and_the_remedy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(SYNC_PATH, root / "scripts" / "sync_plugin_tree.py")
            for _, relative in sync.COMPONENTS:
                (root / relative).mkdir(parents=True, exist_ok=True)
                (root / relative / "entry.md").write_text("entry\n", encoding="utf-8")
            clean = validator.Validation()
            validator.validate_plugin_tree(root, clean)
            self.assertTrue(clean.errors, "an unmaterialised plugin/ must not read as clean")
            self.assertTrue(any(sync.REMEDY in error for error in clean.errors))

            sync.materialise(root)
            synchronised = validator.Validation()
            validator.validate_plugin_tree(root, synchronised)
            self.assertEqual(synchronised.errors, [])

    def test_the_gate_rule_refuses_a_missing_sync_module(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = validator.Validation()
            validator.validate_plugin_tree(Path(temporary), result)
            self.assertEqual(result.errors, ["scripts/sync_plugin_tree.py is required"])


if __name__ == "__main__":
    unittest.main()
