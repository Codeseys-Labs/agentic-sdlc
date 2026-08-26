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
from unittest import mock


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
# `os.symlink`-built allowlist PATH of POSIX utilities that native Windows cannot resolve the same
# way. ArchiveShapeTest keeps running here, because the archive's shape is platform-independent
# and reads no executable bit.
DISPATCHER_IS_POSIX_SHELL_SKIP_REASON = (
    "bin/ccodex is a POSIX shell dispatcher that Windows cannot execute directly (WinError 193), "
    "and the fixtures build a symlinked POSIX allowlist PATH (agentic-sdlc-5ce7)"
)

# The additional real bytes the isolated sdlc exec proof needs: the reader whose runtime
# admission is the assertion, the siblings it loads by absolute path, and the two policies it
# reads. Everything on this list is stdlib-only, so the reader runs under `-I -B` with no venv.
READER_PAYLOAD_FILES = (
    "scripts/ccodex_sdlc.py",
    "scripts/ccodex_sdlc_readonly.py",
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
    """A hermetic git environment: no INHERITED ``GIT_*`` at all, then the names this fixture needs.

    Every inherited ``GIT_*`` is dropped rather than enumerated, because ``GIT_CONFIG_GLOBAL`` and
    ``GIT_CONFIG_NOSYSTEM`` neutralize the two config FILES and nothing else: ``GIT_CONFIG_COUNT``
    with its ``GIT_CONFIG_KEY_n``/``GIT_CONFIG_VALUE_n`` pairs, and the ``GIT_CONFIG_PARAMETERS``
    channel ``git -c`` propagates through, each override files from any source, so an ambient one
    decided whether this module's assertions held (agentic-sdlc-3960). The load-bearing ``GIT_*``
    names here are the ones this helper sets ITSELF, applied after the drop; an enumeration would
    have to grow with every channel git adds. ``GitEnvironmentIsolationTest`` is the proof, with the
    ambient-channel sensitivity control that assertion needs.
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
    # `GIT_*` drop above covers them. `XDG_CONFIG_HOME` is not a `GIT_*` name and still is not one:
    # git reads `$XDG_CONFIG_HOME/git/config` when no `GIT_CONFIG_GLOBAL` is set, and dropping it
    # keeps that true of a future edit that stops setting the global file.
    environment.pop("XDG_CONFIG_HOME", None)
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

    #: The base utilities the dispatcher may use. NOT a tool list: mise, uv, jq and ocx are exactly
    #: what an allowlist PATH must withhold, which is what makes a passing tool-free verb evidence.
    BASE_UTILITIES = ("bash", "cat", "dirname", "realpath")

    def toolless_path(self, extra: tuple[str, ...] = ()) -> str:
        """An allowlist PATH: only the base utilities the dispatcher's tool-free verbs may use.

        ``extra`` names further base utilities a specific route needs (the catalog readers use ``tr``
        and ``grep``). It keeps its own scratch directory, so widening one route's allowlist cannot
        quietly widen the tool-free verbs' one.
        """
        suffix = f"-{'-'.join(extra)}" if extra else ""
        scratch = Path(self.temporary.name) / f"toolless-bin{suffix}"
        scratch.mkdir(exist_ok=True)
        for tool in self.BASE_UTILITIES + extra:
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
        # `status` is the ONE name the gateway plane and the lifecycle share, and the selectors are
        # what pick the lifecycle read: a bare `ccodex status` is still the gateway verb, so the argv
        # here carries `--scope`/`--agent` to reach the Python-backed route whose toolchain boundary
        # is the subject.
        completed = self.run_ccodex(
            ["status", "--scope", "user", "--agent", "claude", "--json"],
            self.toolless_environment(),
        )
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
        completed = self.run_ccodex(
            ["status", "--scope", "user", "--agent", "claude", "--json"], environment
        )
        self.assert_trust_refusal(completed)
        # Before any effect: the probe resolved no tool, so nothing was installed.
        self.assertFalse((Path(environment["MISE_DATA_DIR"]) / "installs").exists())

    def test_a_launch_family_verb_on_an_untrusted_root_refuses_naming_the_remedy(self) -> None:
        self.assert_trust_refusal(self.run_ccodex(["ensure"], self.untrusted_mise_environment()))

    def test_a_shared_uv_runner_verb_on_an_untrusted_root_refuses_naming_the_remedy(self) -> None:
        """RE-ANCHORED from `bundle status` (agentic-sdlc-7a2b W3a): same route, surviving verb.

        The claim is that the SHARED `run_python` route -- the one every non-lifecycle Python verb
        takes -- reaches the same trust boundary as the launch family and the lifecycle's own
        interpreter route, so all three fail closed rather than one of them slipping past. `ccodex
        bundle status` was the spelling that carried it, and `ccodex bundle` is now a refusal that
        never reaches a tool, so the verb has to change for the route to still be observed.
        `libraries list` is that verb: it is the surviving reader on `run_python`, and it is also what
        `policy/release-smoke.v1.json` picked as its shared-uv-runner control for the same reason.
        """
        self.assert_trust_refusal(
            self.run_ccodex(["libraries", "list"], self.untrusted_mise_environment())
        )

    def test_a_retired_namespace_never_reaches_the_toolchain_preflight(self) -> None:
        """The negative control for the three tests above: these arms resolve no tool at all.

        `bundle` and `sdlc` sit UPSTREAM of `require_toolchain`, so an untrusted root -- the exact
        state that turns every verb above into an exit-3 refusal -- must not change what they say.
        Without this, re-anchoring the shared-runner claim onto `libraries` would leave "the retired
        spelling answers before the boundary" resting on nothing: an arm that fell through to the
        preflight would print the trust remedy instead of the migration, and the operator would be
        told to trust a config for a spelling that will never work again.
        """
        environment = self.untrusted_mise_environment()
        for argv, replacement in (
            (["bundle", "status"], "ccodex status --scope user --agent <claude|codex>"),
            (["sdlc", "status"], "ccodex status --scope user --agent <claude|codex>"),
        ):
            with self.subTest(argv=argv):
                completed = self.run_ccodex(argv, environment)
                self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
                self.assertIn("is retired", completed.stderr)
                self.assertIn(replacement, completed.stderr)
                self.assertNotIn("not trusted", completed.stderr)
                self.assertNotIn("mise is not on PATH", completed.stderr)
        self.assertFalse((Path(environment["MISE_DATA_DIR"]) / "installs").exists())


@unittest.skipIf(os.name == "nt", DISPATCHER_IS_POSIX_SHELL_SKIP_REASON)
@unittest.skipUnless(
    sys.version_info[:3] == (3, 12, 11),
    "the isolated sdlc exec proof hands the suite's own interpreter to the REAL reader, whose"
    " runtime admission demands exactly 3.12.11 (the repository gate runs the suite under it)",
)
class IsolatedSdlcExecTest(ExtractedTreeFixture):
    """Post-trust shape of the lifecycle verbs: resolve the pinned interpreter, exec it `-I -B`.

    The verb is spelled top-level (`ccodex status --scope user --agent claude`) because `ccodex sdlc
    <verb>` is retired at exit 2 upstream of the toolchain; the ROUTE under test is unchanged --
    `run_sdlc_python`, reached now from the `install|update|uninstall|doctor|recover` table and from
    this `status` selector branch rather than from one `sdlc)` arm.

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

    #: The lifecycle read, spelled once. Its selectors are what route `ccodex status` to the reader
    #: instead of to the gateway supervision verb of the same name.
    LIFECYCLE_STATUS_ARGV = ["status", "--scope", "user", "--agent", "claude", "--json"]

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

    def test_status_is_admitted_through_the_direct_isolated_exec(self) -> None:
        environment, log = self.stub_mise_environment(fresh_tree=False)
        completed = self.run_ccodex(self.LIFECYCLE_STATUS_ARGV, environment)
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
        completed = self.run_ccodex(self.LIFECYCLE_STATUS_ARGV, environment)
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


@unittest.skipIf(os.name == "nt", DISPATCHER_IS_POSIX_SHELL_SKIP_REASON)
@unittest.skipUnless(
    shutil.which("jq"),
    "the catalog projection under test IS a jq program, so a real jq must serve the pinned"
    " `mise exec -- jq` route; a stub answering it would test the stub's idea of the program",
)
class GatewayCatalogFixture(ExtractedTreeFixture):
    """A stubbed gateway for the two verbs that read its live catalog.

    THE GATEWAY IS A FIXTURE, NOT AN ASSUMPTION. Nothing here contacts a real gateway or a real
    network: the stub ``mise`` answers the trust probe, serves the pinned ``jq`` route from a real jq,
    and answers ``ocx``; the stub ``curl`` serves a catalog constant for ``/v1/models`` and exits 22
    for everything else, which is what an unreachable gateway looks like. The seed that closes the
    preflight (agentic-sdlc-3135) named the ABSENCE of exactly this fixture as the reason the check
    could not be ported into this harness, so it is built here rather than borrowed.
    """

    #: Shape copied from the real `GET /v1/models`: bare native rows, a namespaced routed row, and a
    #: two-slash routed row of the kind OpenRouter ids actually take.
    CATALOG = {
        "data": [
            {"id": "gpt-5.5"},
            {"id": "muse/muse-spark-1.2"},
            {"id": "openrouter/~anthropic/claude-fable-latest"},
        ]
    }
    #: `openai` is DEFAULT and serves BARE ids, so it is absent from the catalog's prefix set by
    #: construction -- the exemption that stops `openai/gpt-5.5` from being a false refusal.
    #: `cerebras` is configured but unpublished; `muse` is both configured and live.
    PROVIDERS = {
        "configured": [
            {"name": "openai", "isDefault": True},
            {"name": "muse"},
            {"name": "cerebras"},
        ]
    }

    def setUp(self) -> None:
        super().setUp()
        base = Path(self.temporary.name)
        # Named before any stub is planted, so the "nothing was written" assertions read the same
        # absent file whether or not a test ever reaches the stubs.
        self.mise_log = base / "gateway-mise-argv.log"
        self.write_log = base / "small-fast-writes.log"
        self.curl_log = base / "curl-argv.log"

    def gateway_environment(self) -> dict[str, str]:
        """A PATH whose ``mise`` and ``curl`` are stubs, and whose only real tool is jq via mise."""
        base = Path(self.temporary.name)
        stub_bin = base / "gateway-stub-bin"
        stub_bin.mkdir(exist_ok=True)
        root = str(self.extracted)
        mise = stub_bin / "mise"
        mise.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$MISE_ARGV_LOG\"\n"
            f"case \"$*\" in '-C {root} tasks') exit 0 ;; esac\n"
            'while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done\n'
            '[ "${1:-}" = -- ] && shift\n'
            'case "${1:-}" in\n'
            '  jq) shift; exec "$TEST_REAL_JQ" "$@" ;;\n'
            "  ocx) shift ;;\n"
            "  *) printf 'unexpected pinned tool: %s\\n' \"${1:-}\" >&2; exit 97 ;;\n"
            "esac\n"
            'case "$*" in\n'
            "  'config get port') printf '%s\\n' \"$STUB_PORT\"; exit 0 ;;\n"
            "  'provider list --json') printf '%s\\n' \"$STUB_PROVIDERS_JSON\"; exit 0 ;;\n"
            "  'claude config set --small-fast-model '*)\n"
            "    printf '%s\\n' \"$*\" >> \"$STUB_WRITE_LOG\"; exit 0 ;;\n"
            "  *) printf 'unexpected ocx argv: %s\\n' \"$*\" >&2; exit 97 ;;\n"
            "esac\n",
            encoding="utf-8",
            newline="\n",
        )
        mise.chmod(0o755)
        curl = stub_bin / "curl"
        curl.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "printf '%s\\n' \"$*\" >> \"$CURL_ARGV_LOG\"\n"
            'for argument in "$@"; do\n'
            '  case "$argument" in\n'
            "    */v1/models)\n"
            '      [ -n "${STUB_CATALOG_JSON:-}" ] || exit 22\n'
            "      printf '%s\\n' \"$STUB_CATALOG_JSON\"; exit 0 ;;\n"
            "  esac\n"
            "done\n"
            "exit 22\n",
            encoding="utf-8",
            newline="\n",
        )
        curl.chmod(0o755)
        real_jq = shutil.which("jq")
        assert real_jq is not None  # guarded by the class-level skipUnless
        return {
            # `tr` and `grep` are the base utilities the port probe and the refusal branch use, so
            # they join the allowlist on their own scratch directory. There is still no jq, ocx, uv,
            # or real mise on this PATH, and no ambient `/usr/bin`: a route that needs a tool this
            # fixture did not name fails here rather than borrowing the developer's machine.
            "PATH": f"{stub_bin}{os.pathsep}{self.toolless_path(('tr', 'grep'))}",
            "HOME": str(base / "home"),
            "TEST_REAL_JQ": real_jq,
            "MISE_ARGV_LOG": str(self.mise_log),
            "STUB_WRITE_LOG": str(self.write_log),
            "CURL_ARGV_LOG": str(self.curl_log),
            "STUB_PORT": "10100",
            "STUB_CATALOG_JSON": json.dumps(self.CATALOG),
            "STUB_PROVIDERS_JSON": json.dumps(self.PROVIDERS),
        }

    def unreadable_gateway_environment(self, **overrides: str) -> dict[str, str]:
        """The same stubs with the catalog unreadable: curl exits 22, as for a gateway that is down.

        ``STUB_PORT=""`` overrides the other unreadable cause, an ocx reporting no configured port.
        """
        environment = self.gateway_environment()
        environment |= {"STUB_CATALOG_JSON": "", **overrides}
        return environment

    def written_ids(self) -> list[str]:
        if not self.write_log.exists():
            return []
        return [
            line.split("--small-fast-model ", 1)[1]
            for line in self.write_log.read_text(encoding="utf-8").splitlines()
            if "--small-fast-model " in line
        ]

    def assert_isolated_home_is_untouched(self) -> None:
        """Nothing in this verb writes to a home directory, admitted or refused.

        The whole family routes its one mutation through `ocx`, which is a stub here, so a stray file
        under the fixture's own `HOME` would mean the dispatcher created state of its own -- exactly
        what an isolated fixture home exists to detect.
        """
        home = Path(self.temporary.name) / "home"
        self.assertEqual(sorted(entry.name for entry in home.iterdir()), [])

    def assert_wrote(self, completed: subprocess.CompletedProcess[str], identifier: str) -> None:
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(self.written_ids(), [identifier])
        self.assert_isolated_home_is_untouched()

    def assert_refused_without_writing(
        self, completed: subprocess.CompletedProcess[str], *expected: str
    ) -> None:
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        for fragment in expected:
            self.assertIn(fragment, completed.stderr)
        # The refusal's whole point: the operator's configuration was NOT touched.
        self.assertEqual(self.written_ids(), [])
        self.assert_isolated_home_is_untouched()


class FastModelCatalogPreflightTest(GatewayCatalogFixture):
    """``set-fast-model``'s live-catalog preflight, and the ONE arm where it is weaker than launch.

    THE ASYMMETRY IS THE SUBJECT, not an accident to be normalized away. ``assert_selected_model_is_served``
    in ``scripts/opencodex-claude.sh`` refuses an unreadable catalog on the launch path, because a
    launch is about to SEND a request and a check that could not run has established nothing. This verb
    sends none -- it writes a configuration slot, and writing that slot while the gateway is down is
    legitimate -- so an unreadable catalog WARNS and the write still happens. Both halves are asserted,
    and once together, because either alone reads as the other arm being missing.
    """

    # --- refusals: an id the RUNNING gateway is known not to serve --------------------------

    def test_an_unknown_provider_prefix_refuses_before_the_write(self) -> None:
        completed = self.run_ccodex(
            ["set-fast-model", "nosuch/model-1"], self.gateway_environment()
        )
        self.assert_refused_without_writing(
            completed,
            "names the provider `nosuch`",
            "serves no provider of that name",
            "BILLED against the wrong",
        )

    def test_a_configured_but_unpublished_prefix_refuses_naming_the_publish_step(self) -> None:
        """The remedy is what separates configuration drift from a typo, so it is asserted."""
        completed = self.run_ccodex(
            ["set-fast-model", "cerebras/llama-3.3-70b"], self.gateway_environment()
        )
        self.assert_refused_without_writing(
            completed,
            "names the provider `cerebras`",
            "is CONFIGURED but is not in the running gateway's catalog",
            "`ocx sync`",
            "`ccodex restart`",
        )

    # --- admitted ids: no warning, and the write happens ------------------------------------

    def test_every_admitted_shape_reaches_the_write_with_no_warning(self) -> None:
        for identifier, why in (
            ("claude-haiku-4-5-20251001", "a BARE id is the native passthrough this verb exists for"),
            ("haiku", "a Claude family alias carries no slash either"),
            ("-", "the clear must never be checked against a catalog"),
            ("muse/muse-spark-1.2", "an exact catalog row"),
            ("muse/some-model-the-listing-omits", "a LIVE prefix serves models the listing omits"),
            ("openrouter/~anthropic/claude-fable-latest", "a two-slash routed row"),
            ("openai/gpt-5.5", "the DEFAULT provider serves bare ids, so it is never a prefix"),
            ("policy/cheap-background", "a routing profile resolves before the prefix branch"),
        ):
            with self.subTest(identifier=identifier, why=why):
                environment = self.gateway_environment()
                self.write_log.unlink(missing_ok=True)
                completed = self.run_ccodex(["set-fast-model", identifier], environment)
                self.assert_wrote(completed, identifier)
                self.assertNotIn("warning:", completed.stderr)
                self.assertNotIn("refused:", completed.stderr)

    def test_a_bare_id_never_reads_the_catalog_at_all(self) -> None:
        """The negative control for the reads above: no slash means no gateway contact.

        Without this, "a bare id is admitted" would hold even if the check were reading a catalog and
        admitting on some other ground, and a host with no gateway would pay for a probe that cannot
        change the answer.
        """
        environment = self.gateway_environment()
        completed = self.run_ccodex(["set-fast-model", "claude-haiku-4-5-20251001"], environment)
        self.assert_wrote(completed, "claude-haiku-4-5-20251001")
        self.assertFalse(self.curl_log.exists(), "a bare id must contact no gateway")
        self.assertEqual(
            self.mise_log.read_text(encoding="utf-8").splitlines(),
            [
                f"-C {self.extracted} tasks",
                f"-C {self.extracted} exec -- ocx claude config set --small-fast-model"
                " claude-haiku-4-5-20251001",
            ],
            "one trust probe and one write: no port probe, no jq, and no second `tasks`",
        )

    # --- the WEAKER arm: an unreadable catalog warns and still writes -------------------------

    def test_an_unreachable_gateway_warns_and_still_writes(self) -> None:
        completed = self.run_ccodex(
            ["set-fast-model", "nosuch/model-1"], self.unreadable_gateway_environment()
        )
        # Same id the readable-catalog case refuses. ONLY the catalog's readability differs.
        self.assert_wrote(completed, "nosuch/model-1")
        self.assertIn("warning:", completed.stderr)
        self.assertIn("served no catalog", completed.stderr)
        self.assertIn("configuring it while the gateway is down is legitimate", completed.stderr)
        self.assertNotIn("refused:", completed.stderr)

    def test_no_configured_port_warns_and_still_writes(self) -> None:
        completed = self.run_ccodex(
            ["set-fast-model", "nosuch/model-1"], self.unreadable_gateway_environment(STUB_PORT="")
        )
        self.assert_wrote(completed, "nosuch/model-1")
        self.assertIn("no gateway port is configured", completed.stderr)
        self.assertNotIn("refused:", completed.stderr)

    def test_the_weaker_arm_is_the_only_asymmetry_with_the_launch_check(self) -> None:
        """The pair, in one place: readable catalog refuses, unreadable catalog writes.

        This is the assertion a later reviewer needs, because reading either test alone invites
        "normalizing" the warning into the launch side's refusal.
        """
        readable = self.run_ccodex(["set-fast-model", "nosuch/model-1"], self.gateway_environment())
        self.assertEqual(readable.returncode, 3, readable.stdout + readable.stderr)
        self.assertEqual(self.written_ids(), [])
        self.write_log.unlink(missing_ok=True)
        unreadable = self.run_ccodex(
            ["set-fast-model", "nosuch/model-1"], self.unreadable_gateway_environment()
        )
        self.assertEqual(unreadable.returncode, 0, unreadable.stdout + unreadable.stderr)
        self.assertEqual(self.written_ids(), ["nosuch/model-1"])

    # --- the trust boundary still comes FIRST -------------------------------------------------

    def test_the_bare_form_is_refused_before_any_tool_is_resolved(self) -> None:
        completed = self.run_ccodex(["set-fast-model"], self.toolless_environment())
        self.assertEqual(completed.returncode, 3, completed.stdout + completed.stderr)
        self.assertIn("no interactive model selector", completed.stderr)
        self.assertEqual(self.written_ids(), [])
        self.assert_isolated_home_is_untouched()

    def test_a_second_argument_is_a_usage_error_before_any_tool_is_resolved(self) -> None:
        completed = self.run_ccodex(
            ["set-fast-model", "muse/muse-spark-1.2", "extra"], self.toolless_environment()
        )
        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
        self.assertIn("usage: ccodex set-fast-model", completed.stderr)
        self.assertEqual(self.written_ids(), [])
        self.assert_isolated_home_is_untouched()


class LiveCatalogDisplayTest(GatewayCatalogFixture):
    """``ccodex models`` renders the SAME projection ``set-fast-model`` checks against.

    The two share one port probe and one jq program as of this change, so the display is covered here
    rather than left to be re-derived: a drift between what ``models`` prints and what
    ``set-fast-model`` admits would send an operator to copy an id the very next command refuses.
    """

    def test_the_display_lists_exactly_the_ids_the_preflight_admits(self) -> None:
        completed = self.run_ccodex(["models"], self.gateway_environment())
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("live catalog served by the gateway at 127.0.0.1:10100", completed.stdout)
        for row in self.CATALOG["data"]:
            self.assertIn(f"  {row['id']}\n", completed.stdout)

    def test_an_unreachable_gateway_is_an_error_here_rather_than_a_warning(self) -> None:
        """The display's contract is unchanged by the preflight sharing its readers."""
        completed = self.run_ccodex(["models"], self.unreadable_gateway_environment())
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertIn("did not serve a catalog", completed.stderr)


class GitEnvironmentIsolationTest(unittest.TestCase):
    """``git_environment`` neutralizes the config ENVIRONMENT channel, not just the config files.

    ``GIT_CONFIG_GLOBAL=/dev/null`` plus ``GIT_CONFIG_NOSYSTEM=1`` disarm the two config FILES and
    nothing else. ``GIT_CONFIG_COUNT`` with its ``GIT_CONFIG_KEY_n``/``GIT_CONFIG_VALUE_n`` pairs, and
    the ``GIT_CONFIG_PARAMETERS`` channel ``git -c`` uses to reach subprocesses, both override files
    from any source -- so an operator or CI runner carrying either decided whether these fixtures'
    assertions held (agentic-sdlc-3960).

    The strip list is "every inherited ``GIT_*``" rather than an enumeration, and the reasoning is
    what makes that safe: the load-bearing ``GIT_*`` names here are the ones the helper sets ITSELF
    (identity, dates, the two config files, the prompt guard), and those are applied AFTER the drop.
    An enumeration would have to grow with every channel git adds, and this class is the proof it
    does not have to.
    """

    #: TWO payloads through the count channel, because one value has to carry each half of the claim.
    #: `commit.gpgsign=true` is VISIBLY FATAL -- a commit exits 128 on `gpg failed to sign the data`
    #: (or on an absent gpg), so a fixture that let it through would not merely differ, it would die.
    #: `fixture.countchannel` is the unambiguous READABLE probe: no real gitconfig sets that name, so
    #: finding it can only mean the injected channel was honoured, where `commit.gpgsign` could also
    #: have come from the host's own config. `GIT_CONFIG_PARAMETERS` is the third channel, the one
    #: `git -c` propagates through; it is measured because it survives file isolation identically and
    #: the seed's named list did not mention it.
    INJECTED = {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "commit.gpgsign",
        "GIT_CONFIG_VALUE_0": "true",
        "GIT_CONFIG_KEY_1": "fixture.countchannel",
        "GIT_CONFIG_VALUE_1": "yes",
        "GIT_CONFIG_PARAMETERS": "'fixture.parameterschannel=yes'",
    }
    PROBES = ("fixture.countchannel", "fixture.parameterschannel")

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

    def commit_in_a_scratch_repo(
        self, environment: dict[str, str], name: str
    ) -> subprocess.CompletedProcess[str]:
        repo = Path(self.temporary.name) / name
        repo.mkdir()
        for arguments in (
            ["init", "--quiet", "--initial-branch", "main"],
            ["commit", "--quiet", "--no-verify", "--allow-empty", "-m", "fixture"],
        ):
            completed = subprocess.run(
                ["git", "-C", str(repo), *arguments],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                return completed
        return completed

    def test_the_helper_drops_the_config_environment_channel(self) -> None:
        with mock.patch.dict(os.environ, self.INJECTED):
            environment = git_environment(self.home)
        # NAMES, never the mapping. `assertNotIn(name, environment)` renders the whole environment
        # into the failure message, and this helper copies `os.environ` -- so the one run that proves
        # a regression would print the host's own API tokens into a CI log. Measured, not theorised:
        # re-admitting the channel during this change did exactly that.
        self.assertEqual(sorted(name for name in self.INJECTED if name in environment), [])

    def test_git_honours_the_channel_ambiently_and_never_through_the_helper(self) -> None:
        """The sensitivity control the absence assertion above needs.

        "The injected key is not visible" proves nothing until the same read is shown to FIND it for a
        known cause, so the ambient environment is measured first. Without that half, a git that had
        stopped honouring these channels entirely would pass this file while the hole stayed open.
        """
        with mock.patch.dict(os.environ, self.INJECTED):
            ambient = dict(os.environ) | {"HOME": str(self.home)}
            isolated = git_environment(self.home)
            for probe in self.PROBES:
                with self.subTest(probe=probe, environment="ambient"):
                    self.assertEqual(self.read_config(ambient, probe), "yes")
        for probe in self.PROBES:
            with self.subTest(probe=probe, environment="isolated"):
                self.assertEqual(self.read_config(isolated, probe), "")
        self.assertEqual(self.read_config(isolated, "commit.gpgsign"), "")

    def test_an_injected_signing_requirement_kills_an_ambient_commit_but_not_a_fixture_one(
        self,
    ) -> None:
        """The behavioural pair, in one test: the channel is fatal ambiently and inert through here.

        The identity variables are supplied to the ambient half too, so its failure is the SIGNING it
        was injected to force rather than an unrelated missing `user.email`.
        """
        identity = {
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        with mock.patch.dict(os.environ, self.INJECTED):
            ambient = dict(os.environ) | identity | {"HOME": str(self.home)}
            isolated = git_environment(self.home)
        exposed = self.commit_in_a_scratch_repo(ambient, "ambient-repo")
        self.assertNotEqual(exposed.returncode, 0, exposed.stdout + exposed.stderr)
        self.assertIn("gpg", (exposed.stdout + exposed.stderr).lower())
        protected = self.commit_in_a_scratch_repo(isolated, "isolated-repo")
        self.assertEqual(protected.returncode, 0, protected.stdout + protected.stderr)


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
            validator.validate_shell_payload(root, intact)
            self.assertEqual(intact.errors, [])

            with (root / "bin" / "ccodex").open("a", encoding="utf-8") as handle:
                handle.write("\nfi\n")
            broken = validator.Validation()
            validator.validate_shell_payload(root, broken)
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
