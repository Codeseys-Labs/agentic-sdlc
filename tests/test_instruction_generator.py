from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import instruction_generator as gen


MARKER = {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"}

#: The canonical tool, invoked as a subprocess so a CLI-level test observes the real process
#: exit code, stdout, and stderr rather than an in-process exception.
TOOL = ROOT / "skills" / "agentic-sdlc" / "tools" / "instruction-generator.py"


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(TOOL), *args],
        capture_output=True,
        text=True,
        timeout=30,
    )


def manifest() -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@2",
        "marker": MARKER,
        "doctrine_pointer": "literal text; this is never opened",
        "outputs": [{
            "path": "AGENTS.md",
            "kind": "root_agents",
            "prefix": "# Local policy\n\n",
            "sections": [{"key": "intent", "body": "Keep this local."}],
        }],
    }


def nested_manifest() -> dict:
    """The same manifest with a NESTED entry path, which the `subtree_agents` kind admits."""
    document = manifest()
    document["outputs"][0]["path"] = "sub/dir/AGENTS.md"
    document["outputs"][0]["kind"] = "subtree_agents"
    return document


class InstructionGeneratorTests(unittest.TestCase):
    def test_render_selected_is_pure_and_does_not_dereference_pointer(self) -> None:
        calls: list[str] = []

        def reader(path: str):
            calls.append(path)
            self.assertEqual(path, "AGENTS.md")
            return {"kind": "absent", "identity": None}, None

        rendered = gen.render_selected(manifest(), "AGENTS.md", reader)
        self.assertEqual(calls, ["AGENTS.md"])
        self.assertEqual(rendered["action"], "create")
        self.assertIn("literal text; this is never opened", rendered["content"].decode())
        self.assertIn(MARKER["start"], rendered["content"].decode())

    def test_replace_preserves_foreign_text_and_exact_output_is_noop(self) -> None:
        old = b"# Foreign\n\n"

        def reader(_: str):
            return {"kind": "regular", "identity": {"placeholder": True}}, old

        first = gen.render_selected(manifest(), "AGENTS.md", reader)
        self.assertEqual(first["action"], "replace")

        def rendered_reader(_: str):
            return {"kind": "regular", "identity": {"placeholder": True}}, first["content"]

        second = gen.render_selected(manifest(), "AGENTS.md", rendered_reader)
        self.assertEqual(second["action"], "no-op")
        self.assertEqual(second["content"], first["content"])

    def test_closed_manifest_rejects_unknown_duplicate_and_bad_paths(self) -> None:
        bad = manifest()
        bad["unexpected"] = True
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)
        bad = manifest()
        bad["outputs"].append(dict(bad["outputs"][0]))
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)
        bad = manifest()
        bad["outputs"][0]["path"] = "../escape"
        with self.assertRaises(gen.GeneratorError):
            gen.validate_manifest(bad)

    def test_locate_marked_block_rejects_malformed_markers(self) -> None:
        with self.assertRaises(gen.GeneratorError):
            gen.render_selected(
                manifest(), "AGENTS.md", lambda _: ({"kind": "regular", "identity": {}}, b"<!-- agentic-sdlc:start -->\n")
            )

    def test_missing_manifest_refuses_at_exit_2_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist.json"
            self.assertFalse(missing.exists())
            result = _run_cli(["plan", "--manifest", str(missing), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_INPUT)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn(str(missing), result.stderr)

    def test_malformed_manifest_still_refuses_at_exit_2(self) -> None:
        """Positive control: the pre-existing refusal path for a bad manifest stays intact."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "manifest.json"
            bad.write_text("not json", encoding="utf-8")
            result = _run_cli(["plan", "--manifest", str(bad), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_INPUT)
            self.assertEqual(result.stdout, "")
            self.assertIn("invalid canonical manifest", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_plan_cli_happy_path_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_bytes(gen._canonical(manifest()))
            result = _run_cli(["plan", "--manifest", str(manifest_path), "--entry", "AGENTS.md"])
            self.assertEqual(result.returncode, gen.EXIT_OK)
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema"], "agentic-sdlc/instruction-render@2")
            self.assertEqual(payload["path"], "AGENTS.md")
            self.assertEqual(payload["action"], "create")


def _fixture_git_environment(home: Path) -> dict[str, str]:
    """A git environment that reads no user, system, or ambient configuration.

    Every inherited `GIT_*` variable is dropped, both config planes are pointed at the null device,
    and `HOME`/`XDG_CONFIG_HOME` are pinned inside the fixture, so a developer's own git config
    cannot make these fixtures pass or fail. Identity is supplied by environment rather than by
    writing a config file, so `commit` needs no config plane at all.
    """
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
            "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
            "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
            "LC_ALL": "C",
        }
    )
    return environment


class _Fixture:
    def __init__(self, parent: str) -> None:
        self.root = Path(tempfile.mkdtemp(dir=parent))
        self.repository = self.root / "repo"
        self.repository.mkdir()
        self.home = self.root / "home"
        (self.home / ".config").mkdir(parents=True)
        self.environment = _fixture_git_environment(self.home)

    def git(self, *arguments: str) -> None:
        done = subprocess.run(
            ["git", *arguments],
            cwd=self.repository,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if done.returncode != 0:
            raise AssertionError(f"fixture git {arguments!r} failed: {done.returncode} {done.stderr!r}")

    def init(self) -> None:
        self.git("init", "-b", "main")

    def commit(self, message: str, **files: str) -> None:
        for name, body in files.items():
            path = self.repository / name.replace("__", "/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-m", message)

    def manifest(self) -> Path:
        path = self.root / "manifest.json"
        path.write_bytes(gen._canonical(manifest()))
        return path

    def apply(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return _run_cli(
            ["apply", "--target", str(self.repository), "--manifest", str(self.manifest()), "--entry", "AGENTS.md", *extra]
        )

    def apply_document(self, document: dict, entry: str, *extra: str) -> subprocess.CompletedProcess[str]:
        path = self.root / "supplied-manifest.json"
        path.write_bytes(gen._canonical(document))
        return _run_cli(["apply", "--target", str(self.repository), "--manifest", str(path), "--entry", entry, *extra])

    def classify(self) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = _run_cli(["classify", "--target", str(self.repository)])
        return result, json.loads(result.stdout) if result.stdout else {}


class ApplyVerbTests(unittest.TestCase):
    def test_apply_refuses_without_yes_and_prints_the_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            target = fixture.repository / "AGENTS.md"
            refused = fixture.apply()
            self.assertEqual(refused.returncode, gen.EXIT_REFUSED)
            self.assertIn("+# Local policy", refused.stdout)
            self.assertIn(f"+{MARKER['start']}", refused.stdout)
            self.assertIn("--yes", refused.stderr)
            self.assertFalse(target.exists())

            approved = fixture.apply("--yes")
            self.assertEqual(approved.returncode, gen.EXIT_OK)
            self.assertTrue(target.is_file())
            self.assertIn(MARKER["end"], target.read_text(encoding="utf-8"))
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_apply_refuses_a_symlinked_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            outside = fixture.root / "outside.md"
            outside.write_text("# not ours\n", encoding="utf-8")
            target = fixture.repository / "AGENTS.md"
            target.symlink_to(outside)

            refused = fixture.apply("--yes")
            self.assertEqual(refused.returncode, gen.EXIT_INPUT)
            self.assertIn("refusing target", refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertTrue(target.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "# not ours\n")

            target.unlink()
            target.write_text("# ours\n", encoding="utf-8")
            approved = fixture.apply("--yes")
            self.assertEqual(approved.returncode, gen.EXIT_OK)
            self.assertFalse(target.is_symlink())
            self.assertIn("# ours", target.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "posix", "os.mkfifo is POSIX-only")
    def test_apply_refuses_a_fifo_at_the_target_and_does_not_hang(self) -> None:
        """A non-regular node must be refused at `EXIT_INPUT`, and a FIFO is the kind that decides it.

        Opening a FIFO for reading blocks until a writer arrives, which here would be never, so the
        refusal has to be reached without a blocking open. The spawn is bounded by `_run_cli`'s
        30-second timeout and the timeout is turned into a named failure: drop `O_NONBLOCK` from
        `read_target` and this test does not merely fail, it times out.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            target = fixture.repository / "AGENTS.md"
            os.mkfifo(target)
            try:
                refused = fixture.apply("--yes")
            except subprocess.TimeoutExpired:
                self.fail("apply blocked on the FIFO at AGENTS.md instead of refusing it")
            self.assertEqual(refused.returncode, gen.EXIT_INPUT)
            self.assertIn("refusing target", refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertTrue(stat.S_ISFIFO(os.lstat(target).st_mode))

            # POSITIVE CONTROL: a REGULAR file at the same path is written, so the refusal above is
            # about the node's KIND and not about the fixture or the entry.
            target.unlink()
            target.write_text("# ours\n", encoding="utf-8")
            approved = fixture.apply("--yes")
            self.assertEqual(approved.returncode, gen.EXIT_OK)
            self.assertIn(MARKER["end"], target.read_text(encoding="utf-8"))

    def test_apply_refuses_a_directory_at_the_target(self) -> None:
        """A directory descriptor cannot become a readable file object, so the kind check must run on
        the RAW descriptor: move it back after the wrap and this refusal escapes as an uncaught
        `IsADirectoryError` traceback at exit 1 instead."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            target = fixture.repository / "AGENTS.md"
            target.mkdir()

            refused = fixture.apply("--yes")
            self.assertEqual(refused.returncode, gen.EXIT_INPUT)
            self.assertIn("refusing target", refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertNotIn("IsADirectoryError", refused.stderr)
            self.assertTrue(target.is_dir())
            self.assertEqual(list(target.iterdir()), [])

            # POSITIVE CONTROL: the same path as a regular file applies, so the assertion is about
            # the node's kind.
            target.rmdir()
            target.write_text("# ours\n", encoding="utf-8")
            approved = fixture.apply("--yes")
            self.assertEqual(approved.returncode, gen.EXIT_OK)
            self.assertIn(MARKER["end"], target.read_text(encoding="utf-8"))

    def test_apply_refuses_a_nested_entry_whose_parent_directory_is_absent(self) -> None:
        """`subtree_agents` admits a nested path, and this tool creates no directory, so an absent
        parent is a refusal that names it rather than a `FileNotFoundError` out of `mkstemp`."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            entry = "sub/dir/AGENTS.md"

            refused = fixture.apply_document(nested_manifest(), entry, "--yes")
            self.assertEqual(refused.returncode, gen.EXIT_INPUT)
            self.assertIn("is not an existing directory", refused.stderr)
            self.assertNotIn("Traceback", refused.stderr)
            self.assertFalse((fixture.repository / "sub").exists())

            # POSITIVE CONTROL: the same nested entry writes once its parent exists, so the refusal
            # is about the missing directory and not about the nested path itself.
            (fixture.repository / "sub" / "dir").mkdir(parents=True)
            approved = fixture.apply_document(nested_manifest(), entry, "--yes")
            self.assertEqual(approved.returncode, gen.EXIT_OK)
            written = (fixture.repository / entry).read_text(encoding="utf-8")
            self.assertIn(MARKER["end"], written)

    def test_apply_round_trips_an_existing_marked_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            target = fixture.repository / "AGENTS.md"
            stale = f"# Foreign policy\n\nkeep me\n\n{MARKER['start']}\n## intent\nstale body\n{MARKER['end']}\n\ntrailing text\n"
            target.write_text(stale, encoding="utf-8")

            first = fixture.apply("--yes")
            self.assertEqual(first.returncode, gen.EXIT_OK)
            written = target.read_text(encoding="utf-8")
            self.assertIn("# Foreign policy", written)
            self.assertIn("keep me", written)
            self.assertIn("trailing text", written)
            self.assertIn("Keep this local.", written)
            self.assertNotIn("stale body", written)

            second = fixture.apply("--yes")
            self.assertEqual(second.returncode, gen.EXIT_OK)
            self.assertIn("no-op", second.stdout)
            self.assertEqual(target.read_text(encoding="utf-8"), written)

            unapproved = fixture.apply()
            self.assertEqual(unapproved.returncode, gen.EXIT_OK)
            self.assertEqual(target.read_text(encoding="utf-8"), written)


class ClassifyVerbTests(unittest.TestCase):
    def test_occupied_surface_on_disk_or_in_the_index_is_brownfield(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"README.md": "# intent\n"})
            (fixture.repository / "AGENTS.md").write_text("# existing guidance\n", encoding="utf-8")

            result, document = fixture.classify()
            self.assertEqual(result.returncode, gen.EXIT_OK)
            self.assertEqual(document["verdict"], "brownfield")
            self.assertEqual(document["occupied"], ["AGENTS.md"])
            self.assertTrue(document["ask"])
            self.assertIn("AGENTS.md", " ".join(document["reasons"]))

    def test_a_tracked_surface_absent_from_the_working_tree_is_still_brownfield(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"mise.toml": "[tools]\n"})
            (fixture.repository / "mise.toml").unlink()

            _, document = fixture.classify()
            self.assertEqual(document["verdict"], "brownfield")
            self.assertEqual(document["occupied"], ["mise.toml"])

    def test_a_neighbouring_tracked_path_does_not_occupy_a_nested_surface(self) -> None:
        """A tracked `docs/README.md` is not an occupied `docs/adr`, and a real ADR is.

        Verified by mutation: the verdict flips to brownfield only when BOTH the `ls-files`
        pathspec and the exact-or-child prefix match are removed, so either half alone answers
        this and the second-half assertion is the positive control that occupancy still fires.
        """
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"docs__README.md": "# docs\n"})

            _, document = fixture.classify()
            self.assertEqual(document["occupied"], [])
            self.assertEqual(document["verdict"], "greenfield")

            fixture.commit("adr", **{"docs__adr__0001-x.md": "# one\n"})
            _, occupied = fixture.classify()
            self.assertEqual(occupied["verdict"], "brownfield")
            self.assertEqual(occupied["occupied"], ["docs/adr"])

    def test_one_clean_commit_with_nothing_occupied_proposes_greenfield(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"README.md": "# intent\n"})

            result, document = fixture.classify()
            self.assertEqual(result.returncode, gen.EXIT_OK)
            self.assertEqual(document["verdict"], "greenfield")
            self.assertEqual(document["reasons"], [])
            self.assertTrue(document["ask"])

    def test_an_unborn_head_still_proposes_greenfield(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()

            _, document = fixture.classify()
            self.assertEqual(document["verdict"], "greenfield")

    def test_history_or_a_dirty_tree_refuses_and_asks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"README.md": "# intent\n"})
            fixture.commit("second", **{"src__main.py": "print(1)\n"})

            _, document = fixture.classify()
            self.assertEqual(document["verdict"], "refuse-and-ask")
            self.assertIn("2 commits", " ".join(document["reasons"]))

            dirty = _Fixture(tmp)
            dirty.init()
            dirty.commit("baseline", **{"README.md": "# intent\n"})
            (dirty.repository / "scratch.txt").write_text("uncommitted\n", encoding="utf-8")
            _, second = dirty.classify()
            self.assertEqual(second["verdict"], "refuse-and-ask")
            self.assertIn("not clean", " ".join(second["reasons"]))

    def test_a_subdirectory_of_a_repository_is_refused_rather_than_mixing_two_scopes(self) -> None:
        """Occupancy is read at `--target`; commit count and cleanliness are repository-wide. From a
        subdirectory those are two different scopes in one verdict, so the root is required."""
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            fixture.init()
            fixture.commit("baseline", **{"AGENTS.md": "# existing guidance\n"})
            fixture.commit("second", **{"src__main.py": "print(1)\n"})

            below = _run_cli(["classify", "--target", str(fixture.repository / "src")])
            self.assertEqual(below.returncode, gen.EXIT_INPUT)
            self.assertEqual(below.stdout, "")
            self.assertIn("not a repository root", below.stderr)
            self.assertNotIn("Traceback", below.stderr)

            # POSITIVE CONTROL: the SAME repository answers from its root, so the refusal is about
            # the supplied directory and not about the fixture.
            result, document = fixture.classify()
            self.assertEqual(result.returncode, gen.EXIT_OK)
            self.assertEqual(document["verdict"], "brownfield")
            self.assertEqual(document["occupied"], ["AGENTS.md"])

    def test_a_directory_that_is_not_a_repository_refuses_at_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = _Fixture(tmp)
            result, _ = fixture.classify()
            self.assertEqual(result.returncode, gen.EXIT_INPUT)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("Traceback", result.stderr)

    def test_the_three_way_ask_by_default_policy_is_stated_in_help(self) -> None:
        result = _run_cli(["--help"])
        self.assertEqual(result.returncode, 0)
        for phrase in ("brownfield", "greenfield", "refuse-and-ask", "asks the operator"):
            self.assertIn(phrase, result.stdout)


@unittest.skipUnless(
    hasattr(os, "O_NOFOLLOW"),
    "the simulation removes os.O_NOFOLLOW, which this platform already lacks",
)
class ReadTargetNoFollowFallbackTests(unittest.TestCase):
    """`read_target` on a platform without `O_NOFOLLOW` (Windows), simulated by removing the flag:
    the symlink refusal is the security-preservation control and must survive the fallback, and a
    regular file must still read so the fallback is not refusing everything. In-process rather
    than through `_run_cli`, because a subprocess would re-import an untouched `os`."""

    def without_nofollow(self):
        saved = os.O_NOFOLLOW

        class _Restore:
            def __enter__(self_inner) -> None:
                delattr(os, "O_NOFOLLOW")

            def __exit__(self_inner, *exc_info: object) -> None:
                os.O_NOFOLLOW = saved  # ALWAYS restore.

        return _Restore()

    def test_a_symlinked_target_is_still_refused_without_the_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.md"
            outside.write_text("# not ours\n", encoding="utf-8")
            target = Path(tmp) / "AGENTS.md"
            target.symlink_to(outside)
            with self.without_nofollow():
                with self.assertRaises(gen.GeneratorError) as raised:
                    gen.read_target(target)
            self.assertIn("refusing target", str(raised.exception))
            self.assertIn("symbolic link", str(raised.exception))

    def test_a_regular_file_still_reads_without_the_flag(self) -> None:
        # Positive control: the fallback refuses the symlink above, not every target.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "AGENTS.md"
            target.write_text("# ours\n", encoding="utf-8")
            with self.without_nofollow():
                prestate, content = gen.read_target(target)
        self.assertEqual(prestate["kind"], "regular")
        self.assertEqual(content, b"# ours\n")


if __name__ == "__main__":
    unittest.main()
