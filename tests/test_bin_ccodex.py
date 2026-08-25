"""The self-locating ``bin/ccodex`` dispatcher: extract-and-run, and its fail-closed boundary.

The archive fixture reuses ``test_build_release``'s isolated Git environment and generates its
payload FROM the shipped allowlist, then plants the REAL ``bin/ccodex``, ``mise.toml``,
``mise.lock``, and ``scripts/opencodex-claude.sh`` bytes so what is extracted and executed is
what a release ships.

NO TRUST IS GRANTED ANYWHERE IN THIS MODULE. The untrusted-config refusal runs REAL mise with
``HOME`` and every ``MISE_*`` root pointed at empty scratch directories (the seeds-launcher
suite's isolation shape), so the extracted tree's config is untrusted regardless of host state;
the dispatcher's probe closes stdin, so mise cannot answer its own trust prompt, and this suite
never runs ``mise trust``. The tool-free assertions run under an allowlist PATH holding only the
handful of base utilities the dispatcher may use -- a positive isolation, not a stripped one --
so ``version``/``--help`` passing genuinely proves no mise, uv, jq, or ocx was needed.
"""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).parents[1]
BIN_CCODEX = ROOT / "bin" / "ccodex"
POLICY_PATH = ROOT / "policy" / "release-candidate.v1.json"
VALIDATOR_PATH = ROOT / "scripts" / "validate_bundle.py"
BUILDER_PATH = ROOT / "scripts" / "build_release.py"

# Real bytes planted over the fixture's comment-shaped stubs: the dispatcher under test, the
# toolchain config its trust boundary names, and the launcher its launch family execs.
REAL_PAYLOAD_FILES = ("bin/ccodex", "mise.toml", "mise.lock", "scripts/opencodex-claude.sh")

# Which of those this repository records as 100755. The fixture has to set the index mode
# EXPLICITLY: a Windows filesystem carries no executable bit, so `shutil.copy2` cannot bring one
# across and `git add` then records 100644, which made the archive's own mode assertion read 0o664
# on windows-2025 (agentic-sdlc-5ce7). Asserting a release property against a mode the host's
# filesystem happened to supply was the defect; the real repository's mode is the fact.
EXECUTABLE_PAYLOAD_FILES = ("bin/ccodex", "scripts/opencodex-claude.sh")

# `bin/ccodex` is a bash script, and Windows resolves an interpreter from the PE header rather
# than a shebang, so `CreateProcess` on it raises `[WinError 193] %1 is not a valid Win32
# application` -- the 9 errors these three classes contributed on windows-2025 (agentic-sdlc-5ce7).
# Reaching it through Git Bash would not rescue the claims either: their isolation is a
# `os.symlink`-built allowlist PATH of POSIX utilities and a `mise trust` remedy string, and
# native Windows operator-tool activation is uncertified (AGENTS.md). ArchiveShapeTest keeps
# running here, because the archive's shape is platform-independent and reads no executable bit.
DISPATCHER_IS_POSIX_SHELL_SKIP_REASON = (
    "bin/ccodex is a POSIX shell dispatcher that Windows cannot execute directly (WinError 193), "
    "and its operator-tools plane is uncertified on native Windows (agentic-sdlc-5ce7)"
)

# The additional real bytes the isolated sdlc exec proof needs: the reader whose runtime
# admission is the assertion, the siblings it loads by absolute path, and the two policies it
# reads. Everything on this list is stdlib-only, so the reader runs under `-I -B` with no venv.
READER_PAYLOAD_FILES = (
    "scripts/ccodex_sdlc.py",
    "scripts/ccodex_sdlc_readonly.py",
    "scripts/install_operator_tools.py",
    "scripts/install_skill_bundle.py",
    "scripts/distribution_activation_receipt.py",
    "scripts/ccodex_sdlc_host_planes.py",
    "policy/ccodex-sdlc-read-report.v1.json",
    "policy/release-contract.v1.json",
)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _load(BUILDER_PATH, "build_release_for_bin_ccodex_test")
validator = _load(VALIDATOR_PATH, "validate_bundle_for_bin_ccodex_test")

POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
STEM = f"agentic-sdlc-{POLICY['manifest']['product_version']}"


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


class ExtractedTreeFixture(unittest.TestCase):
    """Build the archive from a policy-generated fixture repo, then extract it once per test."""

    real_payload_files: tuple[str, ...] = REAL_PAYLOAD_FILES

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        base = Path(self.temporary.name)
        home = base / "home"
        home.mkdir()
        repo = base / "repo"
        repo.mkdir()
        environment = git_environment(home)

        def git(*arguments: str) -> None:
            completed = subprocess.run(
                ["git", "-C", str(repo), *arguments],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

        git("init", "--quiet", "--initial-branch", "main")
        generated = {name: f"# {name}\n" for name in POLICY["payload"]["files"]}
        generated |= {f"{tree}/placeholder.txt": f"# {tree}\n" for tree in POLICY["payload"]["trees"]}
        # Stub entries keep the tool-needing verbs' dispatch about the TOOLCHAIN boundary: the
        # dispatcher's own missing-entry refusal must not fire first.
        for entry in (
            "ccodex_sdlc.py",
            "install_skill_bundle.py",
            "install_external_libraries.py",
            "manage_claude_statusline.py",
        ):
            generated[f"scripts/{entry}"] = "raise SystemExit(0)\n"
        # Pin eol the way the real repository does, rather than leaving it to whatever
        # `core.autocrlf` the host's git carries. This fixture plants REAL repository bytes, and on
        # windows-2025 git reported converting them -- `warning: in the working copy of 'mise.lock',
        # LF will be replaced by CRLF` -- so the extracted tree held bytes the checkout does not.
        # No assertion here compares them today, which is exactly why it was invisible; the
        # dispatcher under test is a shell script, where a stray CR is not cosmetic.
        generated[".gitattributes"] = "* text=auto eol=lf\n"
        for relative, text in generated.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        for relative in self.real_payload_files:
            source = ROOT / relative
            destination = repo / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        (repo / "policy" / "release-candidate.v1.json").write_bytes(builder.canonical(POLICY))
        git("add", "--all")
        for relative in EXECUTABLE_PAYLOAD_FILES:
            if relative in self.real_payload_files:
                git("update-index", "--chmod=+x", relative)
        git("commit", "--quiet", "--no-verify", "-m", "fixture")

        built = builder.build(repo, base / "dist")
        archive = built["archive"]
        assert isinstance(archive, Path)
        with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive.read_bytes()))) as tar:
            self.archive_members = {member.name: member for member in tar.getmembers()}
            # filter="tar" keeps the members' own modes; the archive was built by this test, so
            # the extraction-safety concerns the data filter guards against do not apply.
            tar.extractall(base / "extract", filter="tar")
        self.extracted = Path(os.path.realpath(base / "extract" / STEM))
        self.ccodex = self.extracted / "bin" / "ccodex"

    def toolless_path(self) -> str:
        """An allowlist PATH: only the base utilities the dispatcher's tool-free verbs may use."""
        scratch = Path(self.temporary.name) / "toolless-bin"
        scratch.mkdir(exist_ok=True)
        for tool in ("bash", "cat", "dirname", "realpath"):
            resolved = shutil.which(tool)
            if resolved and not (scratch / tool).exists():
                os.symlink(resolved, scratch / tool)
        return str(scratch)

    def toolless_environment(self) -> dict[str, str]:
        return {
            "PATH": self.toolless_path(),
            "HOME": str(Path(self.temporary.name) / "home"),
        }

    def untrusted_mise_environment(self) -> dict[str, str]:
        """Real host PATH (mise reachable), every mise root pointed at empty scratch state.

        The environment is an ALLOWLIST, not os.environ minus a blocklist: mise auto-trusts
        configs when it detects CI, and that detection reads more than the CI variable —
        GITHUB_ACTIONS on the real runner made these refusal tests read the fixture root as
        trusted and pass a verb that must refuse (reproduced locally by exporting it). Only
        PATH crosses from the host; everything else is scratch.
        """
        environment = {"PATH": os.environ.get("PATH", "")}
        environment |= {
            "HOME": str(Path(self.temporary.name) / "home"),
            "MISE_DATA_DIR": str(Path(self.temporary.name) / "mise-data"),
            "MISE_STATE_DIR": str(Path(self.temporary.name) / "mise-state"),
            "MISE_CACHE_DIR": str(Path(self.temporary.name) / "mise-cache"),
            "MISE_CONFIG_DIR": str(Path(self.temporary.name) / "mise-config"),
        }
        return environment

    def run_ccodex(self, arguments: list[str], environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.ccodex), *arguments],
            env=environment,
            cwd=self.temporary.name,
            capture_output=True,
            text=True,
            check=False,
        )


class ArchiveShapeTest(ExtractedTreeFixture):
    def test_the_archive_carries_bin_ccodex_as_an_executable(self) -> None:
        # `git archive` emits its fixed executable mode 0o775 (rwxrwxr-x) for every 100755 blob;
        # the load-bearing fact is the executable bits surviving into the extracted tree.
        member = self.archive_members[f"{STEM}/bin/ccodex"]
        self.assertTrue(member.isfile())
        self.assertEqual(member.mode, 0o775)
        self.assertTrue(os.access(self.ccodex, os.X_OK))

    def test_the_manifest_inventories_bin_ccodex(self) -> None:
        with tarfile.open(
            fileobj=io.BytesIO(
                gzip.decompress((Path(self.temporary.name) / "dist" / f"{STEM}.tar.gz").read_bytes())
            )
        ) as tar:
            extracted = tar.extractfile(f"{STEM}/manifest.json")
            assert extracted is not None
            manifest = json.loads(extracted.read().decode("utf-8"))
        rows = {str(row["path"]): row for row in manifest["inventory"]}
        self.assertEqual(rows["bin/ccodex"]["type"], "file")
        self.assertEqual(rows["bin/ccodex"]["mode"], 0o775)


@unittest.skipIf(os.name == "nt", DISPATCHER_IS_POSIX_SHELL_SKIP_REASON)
class ToolFreeVerbsTest(ExtractedTreeFixture):
    def test_version_runs_from_the_extracted_tree_with_no_tools_and_no_trust(self) -> None:
        completed = self.run_ccodex(["version"], self.toolless_environment())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn(str(self.extracted), completed.stdout)
        self.assertIn("self-located", completed.stdout)

    def test_help_runs_from_the_extracted_tree_with_no_tools_and_no_trust(self) -> None:
        completed = self.run_ccodex(["--help"], self.toolless_environment())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("usage: ccodex <command>", completed.stdout)

    def test_a_launch_verbs_own_help_is_answered_without_tools(self) -> None:
        # The launcher owns verb-level help and prints it tool-free; the dispatcher must forward
        # the question instead of refusing it at the toolchain boundary.
        completed = self.run_ccodex(["launch", "--help"], self.toolless_environment())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("usage: ccodex launch", completed.stdout)

    def test_a_tool_needing_verb_without_mise_refuses_at_exit_three_naming_mise(self) -> None:
        completed = self.run_ccodex(["sdlc", "status", "--json"], self.toolless_environment())
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("mise is not on PATH", completed.stderr)


@unittest.skipIf(os.name == "nt", DISPATCHER_IS_POSIX_SHELL_SKIP_REASON)
@unittest.skipUnless(shutil.which("mise"), "mise is required for trust-boundary behavior")
class UntrustedConfigRefusalTest(ExtractedTreeFixture):
    def assert_trust_refusal(self, completed: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("not trusted", completed.stderr)
        self.assertIn(f"mise trust {self.extracted}/mise.toml", completed.stderr)
        # The refusal must be the TRUST branch, not the missing-prerequisite branch.
        self.assertNotIn("mise is not on PATH", completed.stderr)

    def test_a_python_backed_verb_on_an_untrusted_root_refuses_naming_the_remedy(self) -> None:
        environment = self.untrusted_mise_environment()
        completed = self.run_ccodex(["sdlc", "status", "--json"], environment)
        self.assert_trust_refusal(completed)
        # Before any effect: the probe resolved no tool, so nothing was installed.
        self.assertFalse((Path(environment["MISE_DATA_DIR"]) / "installs").exists())

    def test_a_launch_family_verb_on_an_untrusted_root_refuses_naming_the_remedy(self) -> None:
        self.assert_trust_refusal(self.run_ccodex(["ensure"], self.untrusted_mise_environment()))

    def test_bundle_status_on_an_untrusted_root_refuses_naming_the_remedy(self) -> None:
        self.assert_trust_refusal(self.run_ccodex(["bundle", "status"], self.untrusted_mise_environment()))


@unittest.skipIf(os.name == "nt", DISPATCHER_IS_POSIX_SHELL_SKIP_REASON)
@unittest.skipUnless(
    sys.version_info[:3] == (3, 12, 11),
    "the isolated sdlc exec proof hands the suite's own interpreter to the REAL reader, whose"
    " runtime admission demands exactly 3.12.11 (the repository gate runs the suite under it)",
)
class IsolatedSdlcExecTest(ExtractedTreeFixture):
    """Post-trust shape of `ccodex sdlc`: resolve the pinned interpreter, exec it `-I -B`.

    Real mise never appears here, on purpose twice over: the trust boundary itself is
    ``UntrustedConfigRefusalTest``'s subject and stays proven there, and granting real trust in a
    scratch plane would auto-install the full pinned toolset. A recording stub ``mise`` stands at
    the probe-and-resolution boundary instead: it answers the trusted probe, answers the
    interpreter resolution with this suite's own interpreter, and logs every argv. What is proven
    end-to-end is therefore the dispatcher's execution shape -- the exact resolution argv, the
    absence of any ``uv run --script`` invocation, and the direct ``-I -B`` exec -- admitted by
    the REAL reader's own runtime admission from the REAL built archive.
    """

    real_payload_files = REAL_PAYLOAD_FILES + READER_PAYLOAD_FILES

    def stub_mise_environment(self, *, fresh_tree: bool) -> tuple[dict[str, str], Path]:
        """A PATH whose only ``mise`` records its argv and stands in for the resolution boundary.

        ``fresh_tree`` simulates a tree whose managed CPython is not yet installed: ``find``
        fails until an explicit ``install`` has recorded its marker, which is exactly what the
        real ``uv python find`` does (it never downloads).
        """
        base = Path(self.temporary.name)
        stub_bin = base / "stub-bin"
        stub_bin.mkdir(exist_ok=True)
        log = base / "mise-argv.log"
        marker = base / "python-installed.marker"
        root = str(self.extracted)
        find_argv = f"-C {root} exec -- uv python find --managed-python 3.12.11"
        install_argv = f"-C {root} exec -- uv python install 3.12.11"
        if fresh_tree:
            find_body = f"[ -e '{marker}' ] || exit 2\n    printf '%s\\n' '{sys.executable}'"
            install_body = f": > '{marker}'"
        else:
            find_body = f"printf '%s\\n' '{sys.executable}'"
            install_body = "printf 'unexpected install: find already answered\\n' >&2; exit 97"
        stub = stub_bin / "mise"
        stub.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            f"printf '%s\\n' \"$*\" >> '{log}'\n"
            'case "$*" in\n'
            f"  '-C {root} tasks') exit 0 ;;\n"
            f"  '{find_argv}')\n    {find_body}\n    ;;\n"
            f"  '{install_argv}')\n    {install_body}\n    ;;\n"
            "  *) printf 'unexpected mise argv: %s\\n' \"$*\" >&2; exit 97 ;;\n"
            "esac\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        environment = {
            "PATH": f"{stub_bin}{os.pathsep}{self.toolless_path()}",
            "HOME": str(base / "home"),
        }
        return environment, log

    def assert_admitted_report(self, completed: subprocess.CompletedProcess[str]) -> dict:
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(report["runtime"]["state"], "admitted")
        self.assertIs(report["runtime"]["isolated"], True)
        self.assertEqual(report["runtime"]["version"], "3.12.11")
        self.assertNotIn(
            "runtime-admission-refused", {finding["code"] for finding in report["findings"]}
        )
        self.assertEqual(report["overall"]["exit_class"], "ok")
        return report

    def test_sdlc_status_is_admitted_through_the_direct_isolated_exec(self) -> None:
        environment, log = self.stub_mise_environment(fresh_tree=False)
        completed = self.run_ccodex(["sdlc", "status", "--json"], environment)
        self.assert_admitted_report(completed)
        self.assertEqual(
            log.read_text(encoding="utf-8").splitlines(),
            [
                f"-C {self.extracted} tasks",
                f"-C {self.extracted} exec -- uv python find --managed-python 3.12.11",
            ],
            "the resolution route must be the trusted probe plus ONE managed-interpreter find;"
            " any other mise invocation (an install with find answered, a `uv run --script`)"
            " is a route regression",
        )

    def test_a_fresh_tree_installs_the_interpreter_once_then_execs_it(self) -> None:
        environment, log = self.stub_mise_environment(fresh_tree=True)
        completed = self.run_ccodex(["sdlc", "status", "--json"], environment)
        self.assert_admitted_report(completed)
        self.assertEqual(
            log.read_text(encoding="utf-8").splitlines(),
            [
                f"-C {self.extracted} tasks",
                f"-C {self.extracted} exec -- uv python find --managed-python 3.12.11",
                f"-C {self.extracted} exec -- uv python install 3.12.11",
                f"-C {self.extracted} exec -- uv python find --managed-python 3.12.11",
            ],
            "a failed find must be followed by exactly one explicit install and one retry",
        )


class ValidatorCoverageTest(unittest.TestCase):
    def test_the_shell_syntax_validator_selects_bin_ccodex(self) -> None:
        self.assertIn("bin/ccodex", validator.SHELL_SYNTAX_PATHS)

    def test_a_syntax_error_in_bin_ccodex_reddens_the_gate(self) -> None:
        """Mutation pair: the intact set passes, then a planted stray `fi` fails by name."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in validator.SHELL_SYNTAX_PATHS:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            intact = validator.Validation()
            validator.validate_operator_tools(root, intact)
            self.assertEqual(intact.errors, [])

            with (root / "bin" / "ccodex").open("a", encoding="utf-8") as handle:
                handle.write("\nfi\n")
            broken = validator.Validation()
            validator.validate_operator_tools(root, broken)
            self.assertTrue(
                any("bin/ccodex" in error for error in broken.errors),
                broken.errors,
            )

    def test_the_candidate_policy_must_require_the_bin_root(self) -> None:
        """Dropping the tree from the payload allowlist must fail the gate, not ship silently."""
        source = POLICY_PATH.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "policy").mkdir()
            target = root / "policy" / "release-candidate.v1.json"

            missing_roots = (
                "policy/release-candidate.v1.json: minimal authored payload roots are missing"
            )
            target.write_text(source, encoding="utf-8")
            intact = validator.Validation()
            validator.validate_release_candidate_policy(root, intact)
            self.assertNotIn(missing_roots, intact.errors)

            stripped_source = source.replace('"bin",', "")
            self.assertNotEqual(stripped_source, source, "the tree must be present to remove")
            target.write_text(stripped_source, encoding="utf-8")
            stripped = validator.Validation()
            validator.validate_release_candidate_policy(root, stripped)
            self.assertIn(missing_roots, stripped.errors)


if __name__ == "__main__":
    unittest.main()
