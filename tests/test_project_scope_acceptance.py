"""gh #11 acceptance 5-8 for project scope, executed in throwaway git repositories.

WHY THIS IS A TEST AND NOT A TRANSCRIPT. The four acceptance items are properties of the shipped
modules, not of one session: "three live pointers", "A's uninstall leaves B and the user plane
byte-identical", "no symlink under a project's `.claude`", and "a refused root writes nothing". A
transcript proves them once, on the machine that ran it; a test proves them on every gate, and the
transcript this suite's own assertions produce is reproducible by re-running it.

THE REPOSITORIES ARE REAL, built by real `git init` and `git commit`, because the ladder that admits
them reads `.git` metadata and a fabrication would prove this file's idea of a repository. The
ACQUISITION is the install suite's own fixture, reused rather than re-invented for the reason that
suite records: a second fabricator would drift from the shape the product admits, and this file would
then prove something about the copy.

EVERY NEGATIVE IS MEASURED, not assumed. "Byte-identical" is a digest over every node's content, link
target, and type; "nothing was written" is that digest plus an mtime witness pinned to the TARGET root
(audit W-h: a check pointed at the source root would pass while a partial write dirtied the
destination), and each one carries the positive control that the same measurement moves when a real
activation runs.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ccodex_sdlc_install as install  # noqa: E402
from scripts import ccodex_sdlc_uninstall as uninstall  # noqa: E402
from scripts import distribution_activation_receipt as receipts  # noqa: E402
from scripts import install_skill_bundle as bundle  # noqa: E402


def _load(path: Path, name: str) -> object:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


#: The install suite owns the acquisition fixture: one real candidate payload tree, one real manifest,
#: and one really sealed acquisition receipt.
install_suite = _load(ROOT / "tests" / "test_ccodex_sdlc_install.py", "project_acceptance_install_suite")

GIT = shutil.which("git")
GIT_SKIP = unittest.skipIf(GIT is None, "a real git is required to build project-root fixtures")
WINDOWS_SKIP = unittest.skipIf(os.name == "nt", "the project-scope plane is certified on Linux only")


def digest_tree(root: Path) -> dict[str, str]:
    """Every node under `root`, by content, link target, or type. The unit of "byte-identical"."""
    snapshot: dict[str, str] = {}
    if not root.exists():
        return snapshot
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            snapshot[relative] = f"symlink:{os.readlink(path)}"
        elif stat.S_ISDIR(mode):
            snapshot[relative] = "dir"
        elif stat.S_ISREG(mode):
            snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            snapshot[relative] = f"special:{stat.S_IFMT(mode)}"
    return snapshot


def tree_digest(root: Path) -> str:
    """One sha256 over that snapshot, so a transcript can quote a single comparable value."""
    return hashlib.sha256(json.dumps(digest_tree(root), sort_keys=True).encode("utf-8")).hexdigest()


def newer_than(root: Path, marker_ns: int) -> list[str]:
    """Every path under `root` modified after the marker: `find <root> -newer <marker>`, in Python.

    Done here rather than by shelling out because the comparison has to be nanosecond-precise: a
    coarse-clock host would make a second-granularity `find` answer "nothing changed" for a write that
    landed in the same second as the marker (this project's own coarse-clock lesson).
    """
    if not root.exists():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.lstat().st_mtime_ns > marker_ns
    )


@GIT_SKIP
@WINDOWS_SKIP
class ProjectScopeAcceptance(unittest.TestCase):
    """One operator plane, one user activation, and two independent project activations."""

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="project-scope-acceptance-")
        self.addCleanup(self._temp.cleanup)
        self.temp = Path(self._temp.name).resolve()
        self.fixture = install_suite.build_fixture(self.temp / "fixture")
        self.activation = self.fixture.state_home / "agentic-sdlc" / "activation"
        self.pointers = self.activation / "active" / "claude"

    # ---- fixtures -------------------------------------------------------------------------------

    def git_environment(self) -> dict[str, str]:
        """Hermetic git: no ambient config, no ambient identity, and no inherited `GIT_*`.

        This process runs inside a worktree of the repository under test, so a leaked `GIT_DIR` would
        point a fixture's `git init` at the real checkout.
        """
        passthrough = {
            name: value
            for name, value in os.environ.items()
            if not name.startswith("GIT_") and name in ("PATH", "LANG", "LC_ALL", "TMPDIR")
        }
        return {
            **passthrough,
            "HOME": str(self.temp),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }

    def git(self, repo: Path, *arguments: str) -> None:
        completed = subprocess.run(
            [str(GIT), *arguments],
            cwd=str(repo),
            env=self.git_environment(),
            capture_output=True,
            check=False,
            text=True,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)

    def repository(self, name: str) -> Path:
        repo = self.temp / name
        repo.mkdir(parents=True)
        (repo / "README.md").write_text(f"{name}\n", encoding="utf-8")
        self.git(repo, "init", "-q", "-b", "main", ".")
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "fixture")
        return repo

    # ---- drivers --------------------------------------------------------------------------------

    def install_plane(self, *, scope: str, project: Path | None, instant: str) -> tuple[int, str]:
        """Run the shipped install module exactly as the dispatcher does, on this fixture's plane."""
        config = dataclasses.replace(
            self.fixture.config, scope_kind=scope, observed_instant=instant
        )
        argv = ["--host", "claude"]
        if scope != "user":
            argv += ["--scope", scope]
        if project is not None:
            argv += ["--project", str(project)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(install, "default_config", lambda: config))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = install.main(argv)
        return code, out.getvalue() + err.getvalue()

    def retire_plane(self, *, scope: str, project: Path | None, instant: str) -> tuple[int, str]:
        """Run the shipped uninstall module through its own entry point, on the same plane."""
        config = uninstall.Config(
            scripts_dir=ROOT / "scripts",
            home=self.fixture.home,
            state_root=self.fixture.installer_state_root,
            activation_root=self.activation,
            codex_home=self.fixture.config.codex_home,
            host="claude",
            platform_system="Linux",
            stated_at=instant,
        )
        argv = ["--host", "claude"]
        if scope != "user":
            argv += ["--scope", scope]
        if project is not None:
            argv += ["--project", str(project)]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(uninstall, "default_config", lambda _bundle: config))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = uninstall.main(argv)
        return code, out.getvalue() + err.getvalue()

    def pointer_for(self, root: Path) -> Path:
        """The keyed pointer filename, derived here rather than read back from the writer."""
        key = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:16]
        return self.pointers / f"project-{key}.json"

    def ledger(self) -> dict[str, dict[str, object]]:
        document = json.loads(
            (self.fixture.installer_state_root / "agentic-sdlc-installer" / "state.json").read_text(
                encoding="utf-8"
            )
        )
        return document["entries"]

    # ---- acceptance 5, 6, 7 ---------------------------------------------------------------------

    def test_three_live_pointers_then_one_projects_retirement_leaves_the_others_untouched(self) -> None:
        """gh #11 acceptance 5, 6 and 7, in one sequence because they are one operator story."""
        first, second = self.repository("project-a"), self.repository("project-b")

        user = self.install_plane(scope="user", project=None, instant="2026-08-25T10:00:00Z")
        one = self.install_plane(scope="project", project=first, instant="2026-08-25T10:01:00Z")
        two = self.install_plane(scope="project", project=second, instant="2026-08-25T10:02:00Z")

        for label, (code, report) in (("user", user), ("project-a", one), ("project-b", two)):
            with self.subTest(activation=label):
                self.assertEqual(0, code, report)

        # ACCEPTANCE 5: THREE LIVE POINTERS, one per (agent, scope, root), and no pre-keyed pointer.
        self.assertEqual(
            sorted(
                [
                    "user.json",
                    self.pointer_for(first).name,
                    self.pointer_for(second).name,
                ]
            ),
            sorted(path.name for path in self.pointers.iterdir()),
        )
        self.assertFalse((self.activation / "active-receipt.json").exists())
        # Each pointer's receipt states its own scope, and the two project keys differ.
        for root in (first, second):
            body = json.loads(self.pointer_for(root).read_text(encoding="utf-8"))["body"]
            self.assertEqual({"agent": "claude", "kind": "project", "root": str(root)}, body["scope"])
            # COPIES FORCED, per ROW, which is where copy-only actually binds bytes: the body carries no
            # policy field to trust, so every row this run published records `copy` or the receipt
            # family refuses the body.
            published = [entry for entry in body["entries"] if entry["disposition"] != "preserved"]
            self.assertTrue(published, "a project activation that published nothing proves nothing here")
            self.assertEqual({"copy"}, {entry["mode"] for entry in published})
            self.assertEqual(
                "validated",
                receipts.derive(
                    "validate",
                    json.loads(self.pointer_for(root).read_text(encoding="utf-8")),
                    "the project activation",
                )["verdict"],
            )
        self.assertNotEqual(self.pointer_for(first).name, self.pointer_for(second).name)
        user_body = json.loads((self.pointers / "user.json").read_text(encoding="utf-8"))["body"]
        self.assertEqual({"agent": "claude", "kind": "user"}, user_body["scope"])

        # ACCEPTANCE 7: NO SYMLINK ANYWHERE under either project's plane -- `find <repo>/.claude -type l`
        # empty -- because a committed entry must be self-contained and a link embeds a user-specific
        # absolute path. The user plane is where links are still admissible, and it is not asserted here.
        for root in (first, second):
            with self.subTest(root=root.name):
                links = [
                    path.relative_to(root).as_posix()
                    for path in (root / ".claude").rglob("*")
                    if path.is_symlink()
                ]
                self.assertEqual([], links)
                self.assertTrue((root / ".claude" / "agents").is_dir())

        # ACCEPTANCE 6: retiring ONE project leaves the other project and the user plane byte-identical.
        before_second = tree_digest(second / ".claude")
        before_user = tree_digest(self.fixture.home / ".claude")
        before_pointer = self.pointer_for(second).read_bytes()

        code, report = self.retire_plane(
            scope="project", project=first, instant="2026-08-25T10:10:00Z"
        )

        self.assertEqual(0, code, report)
        self.assertEqual(before_second, tree_digest(second / ".claude"), "project B moved")
        self.assertEqual(before_user, tree_digest(self.fixture.home / ".claude"), "the user plane moved")
        self.assertEqual(before_pointer, self.pointer_for(second).read_bytes(), "B's pointer moved")
        # POSITIVE CONTROL: the retired project's own plane DID move, so the two equalities above are
        # about the boundary rather than about a retirement that did nothing.
        self.assertEqual([], [path for path in (first / ".claude").rglob("*") if path.is_file()])
        # ... and its ownership rows left with its bytes, so the next status reads no conflict.
        remaining = self.ledger()
        self.assertTrue(remaining, "the surviving planes keep their rows")
        for key in remaining:
            self.assertFalse(
                key.startswith(f"{first}{os.sep}"), f"a retired row survived: {key}"
            )
        for root in (second, self.fixture.home):
            self.assertTrue(
                any(key.startswith(f"{root}{os.sep}") for key in remaining),
                f"{root} lost rows it still owns",
            )

    def test_the_workflow_kind_is_deferred_at_project_scope_and_still_published_at_user_scope(self) -> None:
        """§4.3's window rule, measured on a payload that really carries a workflow.

        `manage_claude_workflows` keeps its receipts in its OWN store and writes no installer ownership
        row, so a repository whose operator already enabled a workflow would present this activation an
        unowned byte-identical destination -- which §3.7's adoption arm would take as removable, leaving
        two authorities over one file and a later project uninstall removing bytes the manager's receipt
        still claims. The deferral keeps exactly one path authoritative until W5 deletes the manager.

        BOTH DIRECTIONS, because a deferral that was really a deletion would pass a one-sided check: the
        same payload's workflow IS published at user scope, on the same plane, in the same test.
        """
        payload = {
            **install_suite.PAYLOAD_FILES,
            "workflows/sdlc-wave-scout.js": "// workflow: sdlc-wave-scout\nexport const meta = {};\n",
        }
        self.fixture = install_suite.build_fixture(self.temp / "with-workflow", payload=payload)
        self.activation = self.fixture.state_home / "agentic-sdlc" / "activation"
        self.pointers = self.activation / "active" / "claude"
        repo = self.repository("deferred")

        project = self.install_plane(scope="project", project=repo, instant="2026-08-25T13:00:00Z")
        user = self.install_plane(scope="user", project=None, instant="2026-08-25T13:01:00Z")

        self.assertEqual(0, project[0], project[1])
        self.assertEqual(0, user[0], user[1])
        # DEFERRED at project scope: no destination, no inventory row, and the report says so by name.
        self.assertFalse((repo / ".claude" / "workflows").exists())
        self.assertIn("deferred at this scope: workflow", project[1])
        self.assertIn("claude:workflows:activate", project[1])
        body = json.loads(self.pointer_for(repo).read_text(encoding="utf-8"))["body"]
        self.assertEqual(
            [], [entry for entry in body["entries"] if entry["entry_name"].startswith("workflows/")]
        )
        # PUBLISHED at user scope, from the same payload: the deferral is scoped, not a deletion.
        self.assertTrue((self.fixture.home / ".claude" / "workflows" / "sdlc-wave-scout.js").is_file())
        # ONE TABLE, read by both verbs: a second copy in either would be two places to widen.
        self.assertEqual(("workflow",), bundle.PROJECT_DEFERRED_KINDS)
        self.assertNotIn("PROJECT_DEFERRED_KINDS = (", (ROOT / "scripts" / "ccodex_sdlc_install.py").read_text(encoding="utf-8"))
        self.assertNotIn("PROJECT_DEFERRED_KINDS = (", (ROOT / "scripts" / "ccodex_sdlc_update.py").read_text(encoding="utf-8"))
        self.assertTrue(
            (ROOT / "scripts" / "manage_claude_workflows.py").is_file(),
            "the deferral's whole reason is that the manager still ships; W5 deletes both together",
        )

    # ---- §2.2 items 6 and 7: the two states a root can leave its pointer in ----------------------

    def test_a_vanished_root_retires_its_records_only_and_a_re_run_reports_the_end_state(self) -> None:
        """§2.2 item 6 (audit B6): the records-only retirement, and what a second one reads as.

        The pathology this closes is ADR-0022's own -- an evidence record with no reader is a
        write-only artifact -- so what is asserted is that the records really go: the pointer, the
        ownership rows under that root, and a sealed retirement naming what it retired. The bytes are
        beyond reach by construction, and the moved-aside copy proves none were touched.
        """
        repo = self.repository("moved-away")
        self.assertEqual(0, self.install_plane(scope="project", project=repo, instant="2026-08-25T14:00:00Z")[0])
        pointer = self.pointer_for(repo)
        self.assertTrue(pointer.is_file())
        elsewhere = self.temp / "elsewhere"
        shutil.move(str(repo), str(elsewhere))
        moved = digest_tree(elsewhere / ".claude")
        self.assertTrue(moved, "the fixture must carry real bytes for 'none were touched' to mean anything")

        code, report = self.retire_plane(
            scope="project", project=repo, instant="2026-08-25T14:10:00Z"
        )

        self.assertEqual(0, code, report)
        self.assertIn("retired", report)
        # THE RECORDS WENT: the pointer is gone, and so are the rows no other verb would have selected.
        self.assertFalse(pointer.exists(), "the pointer of a vanished root survived its retirement")
        self.assertIn("retired the pointer", report)
        self.assertEqual({}, {
            key: row for key, row in self.ledger().items() if key.startswith(f"{repo}{os.sep}")
        })
        # THE EVIDENCE IS SEALED, and it says honestly that nothing was removed from disk.
        retirement = json.loads(
            next(
                path
                for path in sorted((self.activation / "receipts").glob("*.json"))
                if json.loads(path.read_text(encoding="utf-8"))["body"]["operation"] == "uninstall"
            ).read_text(encoding="utf-8")
        )
        body = retirement["body"]
        self.assertEqual("retired", body["terminal_phase"])
        self.assertEqual("complete", body["effect_state"])
        self.assertEqual("activation-receipt", body["prestate_evidence"])
        self.assertEqual(1, len(retirement["ancestors"]), "receipt evidence names exactly one ancestor")
        self.assertEqual({"absent"}, {entry["prestate"] for entry in body["entries"]})
        self.assertEqual({"preserved"}, {entry["disposition"] for entry in body["entries"]})
        self.assertEqual(
            "validated", receipts.derive("validate", retirement, "the retirement")["verdict"]
        )
        # NO BYTES WERE TOUCHED: the copy that moved with the root is byte-identical.
        self.assertEqual(moved, digest_tree(elsewhere / ".claude"))

        # A RE-RUN REPORTS THE REQUESTED END STATE, rather than a refusal an operator has to decode.
        again, report = self.retire_plane(
            scope="project", project=repo, instant="2026-08-25T14:20:00Z"
        )

        self.assertEqual(3, again, report)
        self.assertIn("unresolvable-project-root", report)
        self.assertIn("ALREADY TRUE", report)
        # POSITIVE CONTROL: the same command against a root that still has its pointer is admitted, so
        # the refusal above is about the retired records and not about project scope refusing outright.
        live = self.repository("still-here")
        self.assertEqual(0, self.install_plane(scope="project", project=live, instant="2026-08-25T14:30:00Z")[0])
        self.assertEqual(
            0, self.retire_plane(scope="project", project=live, instant="2026-08-25T14:40:00Z")[0]
        )

    def test_a_pointer_that_outlived_its_repository_refuses_until_the_operator_chooses(self) -> None:
        """§2.2 item 7 (re-review R4), with the positive control that restoring the root un-blocks it.

        Records-only would be WRONG here and that is the whole distinction: the root exists, so real
        bytes may still sit under `<root>/.claude`, and retiring the records would strand them. The
        refusal therefore names both remedies and performs neither.
        """
        repo = self.repository("de-gitted")
        self.assertEqual(0, self.install_plane(scope="project", project=repo, instant="2026-08-25T15:00:00Z")[0])
        before = digest_tree(repo / ".claude")
        pointer = self.pointer_for(repo)
        shutil.rmtree(repo / ".git")

        code, report = self.retire_plane(
            scope="project", project=repo, instant="2026-08-25T15:10:00Z"
        )

        self.assertEqual(3, code, report)
        self.assertIn("pointer-outlived-root", report)
        # BOTH REMEDIES, because this verb refuses to choose between them.
        self.assertIn("restore that root's git metadata", report)
        self.assertIn("remove the directory entirely", report)
        self.assertIn("Nothing was removed", report)
        # AND NOTHING WAS: neither the bytes nor the pointer nor the rows moved.
        self.assertEqual(before, digest_tree(repo / ".claude"))
        self.assertTrue(pointer.is_file())
        self.assertTrue(
            any(key.startswith(f"{repo}{os.sep}") for key in self.ledger()),
            "a refusal retired ownership rows",
        )
        self.assertEqual([], sorted((self.activation / "receipts").glob("uninstall-*.json")))

        # POSITIVE CONTROL: restoring the git metadata makes the ordinary retirement proceed, so the
        # refusal was about the missing metadata and not about a plane that could not be retired.
        self.git(repo, "init", "-q", "-b", "main", ".")

        code, report = self.retire_plane(
            scope="project", project=repo, instant="2026-08-25T15:20:00Z"
        )

        self.assertEqual(0, code, report)
        self.assertEqual([], [path for path in (repo / ".claude").rglob("*") if path.is_file()])
        self.assertNotIn("pointer-outlived-root", report)

    # ---- acceptance 8 ---------------------------------------------------------------------------

    def test_a_refused_root_writes_nothing_into_the_target_it_was_pointed_at(self) -> None:
        """gh #11 acceptance 8: `forbidden-root` and `unsafe-node`, each measured at the TARGET root."""
        hostile = self.temp / "hostile"
        hostile.mkdir()
        os.mkfifo(hostile / ".git")
        (hostile / "keep.txt").write_text("keep\n", encoding="utf-8")
        # The operator's own home, made a git repository so the refusal is about the BOUNDARY and not
        # about the metadata: without this, `forbidden-root` and `not-a-git-project` would be
        # indistinguishable on this fixture.
        self.git(self.fixture.home, "init", "-q", "-b", "main", ".")

        cases = (
            ("forbidden-root", self.fixture.home),
            ("unsafe-node", hostile),
        )
        for reason, target in cases:
            with self.subTest(refusal=reason):
                before = digest_tree(target)
                marker = self.temp / f"marker-{reason}"
                marker.write_text("marker\n", encoding="utf-8")
                marker_ns = marker.lstat().st_mtime_ns

                code, report = self.install_plane(
                    scope="project", project=target, instant="2026-08-25T11:00:00Z"
                )

                self.assertEqual(3, code, report)
                self.assertIn(reason, report)
                self.assertIn("Nothing was written", report)
                # NOTHING WROTE INTO THE TARGET, measured two ways: no node's content, type, or link
                # changed, and no node is newer than the marker taken immediately before the run.
                self.assertEqual(before, digest_tree(target), f"{reason} wrote into the target")
                self.assertEqual([], newer_than(target, marker_ns), f"{reason} touched the target")
                self.assertFalse((target / ".claude" / "agents").exists())
                self.assertFalse(self.pointers.exists(), "a refused root left a pointer")

        # POSITIVE CONTROL for both measurements: an ADMITTED root on the same plane, with the same
        # marker technique, moves both -- so the equalities above are the refusals and not a harness that
        # cannot see a write.
        admitted = self.repository("admitted")
        marker = self.temp / "marker-admitted"
        marker.write_text("marker\n", encoding="utf-8")
        marker_ns = marker.lstat().st_mtime_ns
        before = digest_tree(admitted)

        code, report = self.install_plane(
            scope="project", project=admitted, instant="2026-08-25T11:30:00Z"
        )

        self.assertEqual(0, code, report)
        self.assertNotEqual(before, digest_tree(admitted))
        self.assertNotEqual([], newer_than(admitted, marker_ns))

    # ---- §3.7 adoption and its double recoverability --------------------------------------------

    def test_a_committed_byte_identical_payload_is_adopted_as_removable_and_then_removed(self) -> None:
        """§3.7 with the N4 line: the teammate's fresh clone, and what its uninstall can undo.

        The fixture is exactly the case §3.7 exists for -- a repository that COMMITTED its own
        `<repo>/.claude/**` payload -- built by installing once, committing the result, and retiring the
        records so the next install meets bytes it owns no row for.
        """
        repo = self.repository("committed")
        first = self.install_plane(scope="project", project=repo, instant="2026-08-25T12:00:00Z")
        self.assertEqual(0, first[0], first[1])
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-q", "-m", "commit the project payload")
        committed = digest_tree(repo / ".claude")

        # Retire the RECORDS only, by hand, leaving the committed bytes exactly where they are: this is
        # what a teammate's fresh clone looks like -- the payload present, and no ownership row for it.
        state_path = self.fixture.installer_state_root / "agentic-sdlc-installer" / "state.json"
        document = json.loads(state_path.read_text(encoding="utf-8"))
        document["entries"] = {
            key: row for key, row in document["entries"].items() if not key.startswith(f"{repo}{os.sep}")
        }
        state_path.write_text(json.dumps(document), encoding="utf-8")
        self.pointer_for(repo).unlink()
        for sealed in sorted((self.activation / "receipts").glob("*.json")):
            sealed.unlink()

        code, report = self.install_plane(
            scope="project", project=repo, instant="2026-08-25T12:10:00Z"
        )

        self.assertEqual(0, code, report)
        # ADOPTED, not refused as a foreign collision and not overwritten: the bytes are untouched.
        self.assertEqual(committed, digest_tree(repo / ".claude"), "an adoption wrote to the plane")
        self.assertIn("adopted as removable", report)
        # THE DOUBLE RECOVERABILITY IS PRINTED (audit N4), not merely true.
        self.assertIn("a committed copy is restorable from its index", report)
        self.assertIn("git status", report)
        # Every adopted row is REMOVABLE, which is the whole point: on the shared user home the same
        # bytes would be adopted `removable: False` and could never be retired.
        rows = {key: row for key, row in self.ledger().items() if key.startswith(f"{repo}{os.sep}")}
        self.assertTrue(rows)
        for key, row in rows.items():
            with self.subTest(row=key):
                self.assertIs(True, row["removable"])
                self.assertEqual("copy", row["mode"])
        # And the receipt states the adoption honestly: owned prestate, nothing published.
        body = json.loads(self.pointer_for(repo).read_text(encoding="utf-8"))["body"]
        for entry in body["entries"]:
            with self.subTest(entry=entry["entry_name"]):
                self.assertEqual("owned", entry["prestate"])
                self.assertEqual("preserved", entry["disposition"])
                self.assertIsNone(entry["mode"], "an adoption published nothing, so it names no mode")
        self.assertEqual("validated", receipts.derive("validate", json.loads(
            self.pointer_for(repo).read_text(encoding="utf-8")
        ), "the adoption receipt")["verdict"])

        # THE UNINSTALL CAN NOW REMOVE THEM, and the two halves of the adoption each buy one path: the
        # `owned` PRESTATE is what makes the receipted rung remove the entry (that rung reads the
        # receipt's inventory, never the ledger's flag), and `removable: True` is what makes the
        # ledger-driven rung remove the row. Both are asserted, because a rung that lost its half would
        # otherwise be covered by the other.
        code, report = self.retire_plane(
            scope="project", project=repo, instant="2026-08-25T12:20:00Z"
        )

        self.assertEqual(0, code, report)
        self.assertEqual([], [path for path in (repo / ".claude").rglob("*") if path.is_file()])
        retirement = json.loads(
            next(
                path
                for path in sorted((self.activation / "receipts").glob("*.json"))
                if json.loads(path.read_text(encoding="utf-8"))["body"]["operation"] == "uninstall"
            ).read_text(encoding="utf-8")
        )["body"]
        self.assertEqual("retired", retirement["terminal_phase"])
        self.assertEqual(
            {"removed"},
            {entry["disposition"] for entry in retirement["entries"]},
            "an adopted entry the receipt called owned must be REMOVED, not preserved",
        )
        self.assertEqual({}, {
            key: row for key, row in self.ledger().items() if key.startswith(f"{repo}{os.sep}")
        })
        # AND GIT AGREES the removal is recoverable: the deletion is visible to `git status`, which is
        # the second of the two records the printed line promises.
        status = subprocess.run(
            [str(GIT), "status", "--porcelain"],
            cwd=str(repo),
            env=self.git_environment(),
            capture_output=True,
            check=True,
            text=True,
        ).stdout
        self.assertTrue(
            [line for line in status.splitlines() if line.strip().startswith("D") and ".claude/" in line],
            f"git status shows no deletion to restore: {status!r}",
        )
        # ... and the index really does restore them, which is the claim the line makes.
        self.git(repo, "checkout", "--", ".claude")
        self.assertEqual(committed, digest_tree(repo / ".claude"))


@WINDOWS_SKIP
class ProjectScopeSubstrateTest(unittest.TestCase):
    """Two properties of the plumbing that no single operator sequence exercises."""

    def test_the_pointer_key_every_verb_derives_is_the_receipt_familys_own(self) -> None:
        """One filename, three re-expressions, pinned against the family that owns the derivation."""
        root = "/tmp/some/project"
        activation = Path("/state/agentic-sdlc/activation")
        canonical = receipts.pointer_path(activation, "claude", "project", root)

        for module in (install, uninstall):
            with self.subTest(module=module.__name__):
                self.assertEqual(canonical, module._pointer_path(activation, "claude", "project", root))
        # And the user scope, so a widened project arm cannot quietly move the other key.
        self.assertEqual(
            receipts.pointer_path(activation, "claude", "user"),
            install._pointer_path(activation, "claude", "user"),
        )

    def test_the_codex_plane_declares_no_project_collection_and_claude_declares_one(self) -> None:
        """The reviewed layout decision, read from the plane table rather than from a call site."""
        planes = _load(ROOT / "scripts" / "ccodex_sdlc_host_planes.py", "project_acceptance_planes")

        self.assertEqual(".claude", planes.plane_for("claude").project_collection)
        self.assertIsNone(planes.plane_for("codex").project_collection)
        # A plane with no project collection REFUSES to answer a root rather than returning one, so a
        # caller that skipped the check cannot publish at a repository's top level by accident.
        with self.assertRaises(ValueError):
            planes.plane_for("codex").project_root_collection(Path("/repo"))
        self.assertEqual(
            Path("/repo/.claude"), planes.plane_for("claude").project_root_collection(Path("/repo"))
        )

    def test_the_substrate_forces_copies_at_project_scope_by_refusing_the_link_request(self) -> None:
        """Copy-only is enforced at three layers, and this is the one the operator reaches first."""
        self.assertEqual("copy", receipts.PROJECT_MODE)
        self.assertEqual("copy", install.ACTIVATION_MODE)
        # The grammar refuses `--mode` with project scope before any resolution, and the module refuses
        # `link` for this payload class whatever the scope: two independent gates, neither inferred.
        reader = _load(ROOT / "scripts" / "ccodex_sdlc.py", "project_acceptance_reader")
        with self.assertRaises(reader.UsageError):
            reader.parse_command(["install", "--scope", "project", "--agent", "claude", "--mode", "copy"])


if __name__ == "__main__":
    unittest.main()
