"""The release builder's three load-bearing properties: determinism, refusal, and allowlist scope.

Every fixture repository is built with an isolated Git environment (``GIT_CONFIG_GLOBAL`` at
``os.devnull``, ``GIT_CONFIG_NOSYSTEM=1``, a pinned ``HOME``) so the operator's own config -- hooks,
``core.autocrlf``, ``commit.gpgsign``, a template dir -- cannot decide whether these assertions
hold.
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "scripts" / "build_release.py"
POLICY_PATH = ROOT / "policy" / "release-candidate.v1.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _load(MODULE_PATH, "build_release_under_test")

POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
VERSION = POLICY["manifest"]["product_version"]
STEM = f"agentic-sdlc-{VERSION}"


def git_environment(home: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment |= {
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "Fixture",
        "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "Fixture",
        "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        "GIT_AUTHOR_DATE": "2026-01-02T03:04:05+00:00",
        "GIT_COMMITTER_DATE": "2026-01-02T03:04:05+00:00",
    }
    for name in ("XDG_CONFIG_HOME", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        environment.pop(name, None)
    return environment


class BuilderFixture(unittest.TestCase):
    """One committed fixture repository carrying every allowlisted root plus paths outside it.

    ``git archive`` refuses a pathspec that matches nothing, so the fixture is generated FROM the
    shipped allowlist rather than from a hand-written list that would silently drift from it.
    """

    PAYLOAD = {
        "LICENSE": "licence\n",
        "NOTICE": "notice\n",
        "scripts/tool.py": "print('tool')\n",
        "skills/alpha-skill/SKILL.md": "---\nname: alpha-skill\n---\nalpha\n",
        "agents/claude/cartographer.md": "cartographer\n",
        "assets/asset.txt": "asset\n",
        "commands/sdlc-frame.md": "frame\n",
        "workflows/sdlc-wave-scout.js": "// workflow: sdlc-wave-scout\n",
    }
    OUTSIDE = {
        "docs/notes.md": "notes\n",
        "tests/test_thing.py": "assert True\n",
        "SESSION-HANDOFF.md": "handoff\n",
    }

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        self.home = base / "home"
        self.home.mkdir()
        self.repo = base / "repo"
        self.repo.mkdir()
        self.environment = git_environment(self.home)
        self.git("init", "--quiet", "--initial-branch", "main")
        # Comment-shaped stubs: a `.gitignore` whose body was its own name would ignore itself and
        # `git add` would then skip an allowlisted payload file.
        generated = {name: f"# {name}\n" for name in POLICY["payload"]["files"]}
        generated |= {f"{tree}/placeholder.txt": f"# {tree}\n" for tree in POLICY["payload"]["trees"]}
        for relative, text in {**generated, **self.PAYLOAD, **self.OUTSIDE}.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        os.symlink("../skills", self.repo / "plugin" / "skills")
        (self.repo / "policy" / "release-candidate.v1.json").write_bytes(builder.canonical(POLICY))
        self.git("add", "--all")
        self.git("commit", "--quiet", "--no-verify", "-m", "fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()

    def git(self, *arguments: str) -> str:
        completed = subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed.stdout

    def build(self, dist: Path) -> Path:
        built = builder.build(self.repo, dist)
        self.built = built
        archive = built["archive"]
        assert isinstance(archive, Path)
        return archive

    def members(self, archive: Path) -> dict[str, tarfile.TarInfo]:
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive.read_bytes()))) as tar:
            return {member.name: member for member in tar.getmembers()}

    def manifest(self, archive: Path) -> dict[str, object]:
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive.read_bytes()))) as tar:
            extracted = tar.extractfile(f"{STEM}/manifest.json")
            assert extracted is not None
            return json.loads(extracted.read().decode("utf-8"))


class DeterminismTest(BuilderFixture):
    def test_two_builds_of_one_commit_are_byte_identical(self) -> None:
        first = self.build(Path(self.temporary.name) / "dist-a")
        second = self.build(Path(self.temporary.name) / "dist-b")
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(
            (first.parent / "SHA256SUMS").read_text(encoding="utf-8"),
            (second.parent / "SHA256SUMS").read_text(encoding="utf-8"),
        )
        # Positive control: the assertion above is not comparing a file with itself.
        self.assertNotEqual(first, second)

    def test_every_member_carries_the_commit_epoch_and_uid_zero(self) -> None:
        archive = self.build(Path(self.temporary.name) / "dist")
        epoch = int(self.git("log", "-1", "--format=%ct", "HEAD").strip())
        members = self.members(archive)
        self.assertIn(f"{STEM}/manifest.json", members)
        for name, member in members.items():
            with self.subTest(member=name):
                self.assertEqual(member.mtime, epoch)
                self.assertEqual((member.uid, member.gid), (0, 0))

    def test_a_working_tree_mtime_does_not_reach_the_archive(self) -> None:
        """The one substitution that silently voids the digest: bytes taken from the checkout."""
        archive = self.build(Path(self.temporary.name) / "dist")
        epoch = int(self.git("log", "-1", "--format=%ct", "HEAD").strip())
        os.utime(self.repo / "LICENSE", (epoch + 10_000, epoch + 10_000))
        rebuilt = self.build(Path(self.temporary.name) / "dist-again")
        self.assertEqual(archive.read_bytes(), rebuilt.read_bytes())
        self.assertEqual(self.members(rebuilt)[f"{STEM}/LICENSE"].mtime, epoch)

    def test_the_gzip_envelope_records_no_timestamp(self) -> None:
        archive = self.build(Path(self.temporary.name) / "dist")
        header = archive.read_bytes()[:10]
        self.assertEqual(header[:2], b"\x1f\x8b")
        self.assertEqual(header[4:8], b"\x00\x00\x00\x00")


class AllowlistTest(BuilderFixture):
    def test_only_allowlisted_payload_reaches_the_archive(self) -> None:
        archive = self.build(Path(self.temporary.name) / "dist")
        names = {name[len(STEM) + 1 :] for name in self.members(archive) if name != STEM}
        for relative in self.PAYLOAD:
            self.assertIn(relative, names)
        for relative in self.OUTSIDE:
            self.assertNotIn(relative, names)
        self.assertNotIn("docs", names)

    def test_the_manifest_inventories_every_member_with_a_digest(self) -> None:
        archive = self.build(Path(self.temporary.name) / "dist")
        manifest = self.manifest(archive)
        rows = {str(row["path"]): row for row in manifest["inventory"]}  # type: ignore[index]
        self.assertNotIn("manifest.json", rows)
        for relative, text in self.PAYLOAD.items():
            row = rows[relative]
            self.assertEqual(row["type"], "file")
            self.assertEqual(row["sha256"], hashlib.sha256(text.encode()).hexdigest())
        self.assertEqual(rows["plugin/skills"]["type"], "symlink")
        self.assertEqual(rows["plugin/skills"]["target"], "../skills")
        self.assertEqual(rows["skills"]["type"], "dir")
        self.assertEqual(sorted(rows), sorted(str(row["path"]) for row in manifest["inventory"]))  # type: ignore[index]

    def test_the_manifest_carries_the_policy_honesty_disclosures(self) -> None:
        manifest = self.manifest(self.build(Path(self.temporary.name) / "dist"))
        self.assertIsNone(manifest["public_channel"])
        self.assertEqual(manifest["release_claim"], "none")
        self.assertEqual(manifest["support_tier"], "unsupported")
        self.assertEqual(manifest["artifact_kind"], "unpublished-candidate")
        self.assertEqual(manifest["disclosures"], POLICY["disclosures"])
        self.assertEqual(manifest["source"], {"commit": self.commit, "tree": self.git("rev-parse", "HEAD^{tree}").strip()})
        self.assertEqual(len(str(manifest["candidate_id"])), 64)

    def test_the_sums_file_names_the_archive_it_digests(self) -> None:
        dist = Path(self.temporary.name) / "dist"
        archive = self.build(dist)
        digest, name = (dist / "SHA256SUMS").read_text(encoding="utf-8").split()
        self.assertEqual(name, archive.name)
        self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertFalse((dist / f"{STEM}.tar").exists())

    def test_a_missing_allowlist_entry_refuses_rather_than_shipping_a_short_payload(self) -> None:
        self.git("rm", "--quiet", "-r", "workflows")
        self.git("commit", "--quiet", "--no-verify", "-m", "drop workflows")
        with self.assertRaises(builder.Refusal) as raised:
            self.build(Path(self.temporary.name) / "dist")
        self.assertIn("payload allowlist", str(raised.exception))


class RefusalTest(BuilderFixture):
    def test_a_modified_tracked_file_is_refused_by_name(self) -> None:
        (self.repo / "LICENSE").write_text("edited\n", encoding="utf-8")
        with self.assertRaises(builder.Refusal) as raised:
            self.build(Path(self.temporary.name) / "dist")
        self.assertIn("is dirty", str(raised.exception))
        self.assertIn("LICENSE", str(raised.exception))

    def test_an_untracked_file_is_refused(self) -> None:
        (self.repo / "scripts" / "scratch.py").write_text("scratch\n", encoding="utf-8")
        with self.assertRaises(builder.Refusal):
            self.build(Path(self.temporary.name) / "dist")

    def test_a_clean_tree_builds_so_the_refusals_are_not_vacuous(self) -> None:
        self.assertTrue(self.build(Path(self.temporary.name) / "dist").is_file())

    def test_an_entry_count_over_the_policy_ceiling_is_refused(self) -> None:
        limits = dict(POLICY["limits"])
        limits["max_entries"] = 2
        with self.assertRaises(builder.Refusal) as raised:
            builder.enforce_limits(limits, [{"path": "a", "size": 1}] * 3, 10, 10)
        self.assertIn("max_entries", str(raised.exception))

    def test_the_cli_reports_a_refusal_as_exit_three(self) -> None:
        (self.repo / "LICENSE").write_text("edited\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(MODULE_PATH),
                "--root",
                str(self.repo),
                "--dist",
                str(Path(self.temporary.name) / "dist"),
            ],
            env=self.environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, builder.EXIT_REFUSED, completed.stdout + completed.stderr)
        self.assertIn("refused:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
