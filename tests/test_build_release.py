"""The release builder's three load-bearing properties: determinism, refusal, and allowlist scope.

Every fixture repository is built with an isolated Git environment (``GIT_CONFIG_GLOBAL`` at
``os.devnull``, ``GIT_CONFIG_NOSYSTEM=1``, a pinned ``HOME``) so the operator's own hooks,
``commit.gpgsign``, and template dir cannot decide whether these assertions hold.

That isolation does NOT cover ``core.autocrlf``, and this docstring used to claim it did: on
windows-2025 autocrlf was active anyway -- git warned ``LF will be replaced by CRLF`` and
``git archive`` emitted CRLF for a working tree that was already LF -- so the archived bytes these
assertions compare were decided by host config after all (agentic-sdlc-5ce7). Neutralizing the two
config FILES leaves the repository-local config ``git init`` writes, and which source the runner used
is not observable from a Linux host. The fixture therefore pins eol the way the real repository does,
with a ``.gitattributes`` rule: attributes beat every config source, so this one is a guarantee
rather than a hope.

The environment channel that same investigation named is now closed rather than disclosed:
``git_environment`` drops every inherited ``GIT_*``, so ``GIT_CONFIG_COUNT`` with its
``GIT_CONFIG_KEY_n``/``GIT_CONFIG_VALUE_n`` pairs and ``GIT_CONFIG_PARAMETERS`` cannot override the
neutralized files any more (agentic-sdlc-3960). ``GitEnvironmentIsolationTest`` proves it against a
measured ambient control, because an absence assertion with no sensitivity control proves nothing.
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
from unittest import mock


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
    """A hermetic git environment: no INHERITED ``GIT_*`` at all, then the names this fixture needs.

    Every inherited ``GIT_*`` is dropped rather than enumerated, because ``GIT_CONFIG_GLOBAL`` and
    ``GIT_CONFIG_NOSYSTEM`` neutralize the two config FILES and nothing else: ``GIT_CONFIG_COUNT``
    with its ``GIT_CONFIG_KEY_n``/``GIT_CONFIG_VALUE_n`` pairs, and the ``GIT_CONFIG_PARAMETERS``
    channel ``git -c`` propagates through, each override files from any source, so an ambient one
    decided whether this module's determinism assertions held (agentic-sdlc-3960). The load-bearing
    ``GIT_*`` names here are the ones this helper sets ITSELF, applied after the drop; an enumeration
    would have to grow with every channel git adds. ``GitEnvironmentIsolationTest`` is the proof,
    with the ambient-channel sensitivity control that assertion needs.
    """
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
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
    # `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` used to be popped here by name; the blanket
    # `GIT_*` drop above covers them, and a leaked `GIT_DIR` pointing a fixture's `git init` at this
    # repository is the reason that list existed. `XDG_CONFIG_HOME` is not a `GIT_*` name and still is
    # not one: git reads `$XDG_CONFIG_HOME/git/config` when no `GIT_CONFIG_GLOBAL` is set, and
    # dropping it keeps that true of a future edit that stops setting the global file.
    environment.pop("XDG_CONFIG_HOME", None)
    return environment


class BuilderFixture(unittest.TestCase):
    """One committed fixture repository carrying every allowlisted root plus paths outside it.

    ``git archive`` refuses a pathspec that matches nothing, so the fixture is generated FROM the
    shipped allowlist rather than from a hand-written list that would silently drift from it.

    Every write here passes ``newline="\\n"`` on purpose. These constants are what the digest and
    archived-bytes assertions compare against, so a fixture whose on-disk bytes differ from its own
    constant is comparing two different documents: ``write_text`` defaults to the platform's line
    separator, which put CRLF on disk on windows-2025 and failed the manifest digest and the
    head-anchor claim with ``b'licence\\r\\n' != b'licence\\n'`` (agentic-sdlc-5ce7). A release
    archive's bytes are the subject here, so the fixture states its own.
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
        # `.gitattributes` is the ONE allowlisted payload file whose comment-shaped stub is not
        # inert: the real repository pins its bytes with exactly this rule, and a fixture that
        # stubs it out is a repository with no eol policy, so whatever `core.autocrlf` the host's
        # git carries decides the archived bytes instead. That is the second CRLF source behind
        # these two claims on windows-2025 -- disk bytes were already LF and `git archive` still
        # emitted CRLF (agentic-sdlc-5ce7). Attributes beat config from any source, which matters
        # because where the runner's autocrlf comes from is not observable from here.
        generated[".gitattributes"] = "* text=auto eol=lf\n"
        for relative, text in {**generated, **self.PAYLOAD, **self.OUTSIDE}.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
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
        (self.repo / "LICENSE").write_text("edited\n", encoding="utf-8", newline="\n")
        with self.assertRaises(builder.Refusal) as raised:
            self.build(Path(self.temporary.name) / "dist")
        self.assertIn("is dirty", str(raised.exception))
        self.assertIn("LICENSE", str(raised.exception))

    def test_an_untracked_file_is_refused(self) -> None:
        (self.repo / "scripts" / "scratch.py").write_text("scratch\n", encoding="utf-8", newline="\n")
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
        (self.repo / "LICENSE").write_text("edited\n", encoding="utf-8", newline="\n")
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


class HeadAnchorTest(BuilderFixture):
    """agentic-sdlc-4b0f: the recorded source is ONE derivation from ONE commit, not three reads.

    A settled repository answers ``rev-parse HEAD``, ``rev-parse HEAD^{tree}``, and ``git archive
    HEAD`` for the same commit, so a builder that reads the reference three times looks correct in
    every ordinary test here. These drive the window where it is not: the head moves after the
    commit has been recorded. The dirty-tree refusal does not close that window, because a commit
    landing in another worktree on the same repository moves ``HEAD`` without leaving anything to
    report as dirty.
    """

    def _move_the_head(self) -> str:
        """Land a commit whose tree really differs from the fixture's, and return it."""
        (self.repo / "LICENSE").write_text("relicensed\n", encoding="utf-8", newline="\n")
        self.git("add", "LICENSE")
        self.git("commit", "--quiet", "--no-verify", "-m", "moved")
        moved = self.git("rev-parse", "HEAD").strip()
        self.assertNotEqual(moved, self.commit)
        return moved

    def test_a_head_that_moves_between_the_reads_cannot_split_the_recorded_pair(self) -> None:
        real, moved = builder.git, []

        def moving(root: Path, *arguments: str) -> str:
            answer = real(root, *arguments)
            if arguments == ("rev-parse", "HEAD") and not moved:
                # The commit has just been recorded. Moving the head HERE is the whole test: it is
                # the only point at which a second independent read would answer differently.
                moved.append(self._move_the_head())
            return answer

        with mock.patch.object(builder, "git", moving):
            commit, tree = builder.require_clean(self.repo)

        self.assertEqual(moved, [self.git("rev-parse", "HEAD").strip()], "the head did not actually move")
        self.assertEqual(commit, self.commit)
        # The tree belongs to the commit that was RECORDED, not to the one that replaced it.
        self.assertEqual(tree, self.git("rev-parse", f"{self.commit}^{{tree}}").strip())
        # POSITIVE CONTROL: the head really did move to a commit with a DIFFERENT tree, so the
        # equality above is not two spellings of one value.
        self.assertNotEqual(tree, self.git("rev-parse", f"{moved[0]}^{{tree}}").strip())

    def test_the_archive_bytes_come_from_the_recorded_commit_and_not_from_head(self) -> None:
        prefix = "fixture/"
        allowlist = [*POLICY["payload"]["files"], *POLICY["payload"]["trees"]]
        moved = self._move_the_head()

        def licence_archived_from(commit: str) -> bytes:
            destination = Path(self.temporary.name) / f"{commit}.tar"
            builder.archive_tar(self.repo, prefix, allowlist, destination, commit)
            with tarfile.open(destination) as tar:
                extracted = tar.extractfile(f"{prefix}LICENSE")
                assert extracted is not None
                return extracted.read()

        # HEAD sits at `moved`, so a builder that archived `HEAD` would serve the edited licence for
        # the recorded commit too, and the manifest would name a source the bytes do not come from.
        self.assertEqual(licence_archived_from(self.commit), b"licence\n")
        # POSITIVE CONTROL: the commit argument really is what selects the content, so the assertion
        # above is about the pin and not about a fixture carrying only one version of the file.
        self.assertEqual(licence_archived_from(moved), b"relicensed\n")


#: TWO payloads through the count channel, because one value has to carry each half of the claim.
#: ``commit.gpgsign=true`` is VISIBLY FATAL -- a commit exits 128 on ``gpg failed to sign the data``
#: (or on an absent gpg), so a fixture that let it through would not merely differ, it would die, and
#: every ``BuilderFixture`` in this module commits. ``fixture.countchannel`` is the unambiguous
#: READABLE probe: no real gitconfig sets that name, so finding it can only mean the injected channel
#: was honoured, where ``commit.gpgsign`` could also have come from the host's own config.
#: ``GIT_CONFIG_PARAMETERS`` is the third channel, the one ``git -c`` propagates through; it is
#: measured because it survives file isolation identically and the seed's named list omitted it.
INJECTED_GIT_CONFIG_CHANNEL = {
    "GIT_CONFIG_COUNT": "2",
    "GIT_CONFIG_KEY_0": "commit.gpgsign",
    "GIT_CONFIG_VALUE_0": "true",
    "GIT_CONFIG_KEY_1": "fixture.countchannel",
    "GIT_CONFIG_VALUE_1": "yes",
    "GIT_CONFIG_PARAMETERS": "'fixture.parameterschannel=yes'",
}
CHANNEL_PROBES = ("fixture.countchannel", "fixture.parameterschannel")


class GitEnvironmentIsolationTest(unittest.TestCase):
    """``git_environment`` neutralizes the config ENVIRONMENT channel, not just the config files.

    ``GIT_CONFIG_GLOBAL=/dev/null`` plus ``GIT_CONFIG_NOSYSTEM=1`` disarm the two config FILES and
    nothing else, so an ambient ``GIT_CONFIG_COUNT`` pair or ``GIT_CONFIG_PARAMETERS`` decided whether
    this module's determinism and byte assertions held (agentic-sdlc-3960).

    The strip list is "every inherited ``GIT_*``" rather than an enumeration, and the reasoning is what
    makes that safe: the load-bearing ``GIT_*`` names here are the ones the helper sets ITSELF
    (identity, dates, the two config files, the prompt guard), and those are applied AFTER the drop.
    """

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home"
        self.home.mkdir()

    def read_config(self, environment: dict[str, str], key: str) -> str:
        completed = subprocess.run(
            ["git", "config", "--get", key],
            env=environment,
            cwd=self.temporary.name,
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.stdout.strip()

    def test_the_helper_drops_the_config_environment_channel(self) -> None:
        with mock.patch.dict(os.environ, INJECTED_GIT_CONFIG_CHANNEL):
            environment = git_environment(self.home)
        # NAMES, never the mapping. `assertNotIn(name, environment)` renders the whole environment
        # into the failure message, and this helper copies `os.environ` -- so the one run that proves
        # a regression would print the host's own API tokens into a CI log. Measured, not theorised:
        # re-admitting the channel during this change did exactly that.
        self.assertEqual(
            sorted(name for name in INJECTED_GIT_CONFIG_CHANNEL if name in environment), []
        )

    def test_git_honours_the_channel_ambiently_and_never_through_the_helper(self) -> None:
        """The sensitivity control the absence assertion above needs.

        "The injected key is not visible" proves nothing until the same read is shown to FIND it for a
        known cause, so the ambient environment is measured first. Without that half, a git that had
        stopped honouring these channels entirely would pass this file while the hole stayed open.
        """
        with mock.patch.dict(os.environ, INJECTED_GIT_CONFIG_CHANNEL):
            ambient = dict(os.environ) | {"HOME": str(self.home)}
            isolated = git_environment(self.home)
            for probe in CHANNEL_PROBES:
                with self.subTest(probe=probe, environment="ambient"):
                    self.assertEqual(self.read_config(ambient, probe), "yes")
        for probe in CHANNEL_PROBES:
            with self.subTest(probe=probe, environment="isolated"):
                self.assertEqual(self.read_config(isolated, probe), "")
        self.assertEqual(self.read_config(isolated, "commit.gpgsign"), "")


class InjectedGitConfigChannelBuildTest(BuilderFixture):
    """The whole fixture path under a live injection: it builds, and the archive is unchanged.

    This is the end-to-end half of the claim above, and it is not decorative. ``BuilderFixture.setUp``
    commits, so with the channel reaching git the injected ``commit.gpgsign`` fails that commit at
    exit 128 and every test in this class ERRORS in setUp. Passing is therefore evidence the drop
    happens before git is invoked, on the real fixture rather than on a synthetic mapping.
    """

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ, INJECTED_GIT_CONFIG_CHANNEL)
        patcher.start()
        self.addCleanup(patcher.stop)
        super().setUp()

    def test_the_fixture_repository_never_sees_a_channel_this_process_is_carrying(self) -> None:
        # The channel really is in THIS process's environment; without that the class proves nothing,
        # and `setUp` having reached this point is already the commit surviving a forced signature.
        self.assertEqual(os.environ["GIT_CONFIG_COUNT"], "2")
        for probe in CHANNEL_PROBES:
            with self.subTest(probe=probe):
                self.assertEqual(self.git("config", "--get", "--default", "", probe).strip(), "")
        self.assertEqual(self.git("config", "--get", "--default", "", "commit.gpgsign").strip(), "")
        archive = self.build(Path(self.temporary.name) / "dist")
        self.assertEqual(self.manifest(archive)["source"]["commit"], self.commit)


if __name__ == "__main__":
    unittest.main()
