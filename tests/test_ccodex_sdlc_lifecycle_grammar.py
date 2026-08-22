"""The closed ``ccodex sdlc`` lifecycle grammar: three mutating verbs that only ever hand off.

This module covers exactly the grammar/dispatch boundary. It does not test lifecycle behavior,
because no lifecycle behavior exists yet: ``scripts/ccodex_sdlc_install.py``,
``ccodex_sdlc_update.py``, and ``ccodex_sdlc_uninstall.py`` are separate tickets. What must hold
today is that a mutating verb parses, resolves ONE named module path, and refuses BY NAME at exit 3
before any effect when that module is absent -- never an exit-1 traceback, and never a silent
widening of what the read-only candidate projection admits.

Every negative assertion here carries a positive control in the same test: an absence proves
nothing unless the same harness is shown to detect the presence.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
import unittest


ROOT = Path(__file__).parents[1]
READER_SCRIPT = ROOT / "scripts" / "ccodex_sdlc.py"
GUARD_SCRIPT = ROOT / "scripts" / "ccodex_sdlc_readonly.py"
LAUNCHER_TEMPLATE = ROOT / "assets" / "launchers" / "ccodex.in"

OPERATOR_SCRIPT = ROOT / "scripts" / "install_operator_tools.py"
_operator_spec = importlib.util.spec_from_file_location("lifecycle_grammar_operator_tools", OPERATOR_SCRIPT)
assert _operator_spec and _operator_spec.loader
operator_tools = importlib.util.module_from_spec(_operator_spec)
sys.modules[_operator_spec.name] = operator_tools
_operator_spec.loader.exec_module(operator_tools)

_reader_spec = importlib.util.spec_from_file_location("lifecycle_grammar_reader", READER_SCRIPT)
assert _reader_spec and _reader_spec.loader
reader = importlib.util.module_from_spec(_reader_spec)
sys.modules[_reader_spec.name] = reader
_reader_spec.loader.exec_module(reader)

_guard_spec = importlib.util.spec_from_file_location("lifecycle_grammar_guard", GUARD_SCRIPT)
assert _guard_spec and _guard_spec.loader
guard = importlib.util.module_from_spec(_guard_spec)
sys.modules[_guard_spec.name] = guard
_guard_spec.loader.exec_module(guard)

MUTATING_VECTORS = (
    ("install", "--host", "claude"),
    ("update",),
    ("uninstall",),
)
MUTATING_MODULES = {
    "install": "ccodex_sdlc_install.py",
    "update": "ccodex_sdlc_update.py",
    "uninstall": "ccodex_sdlc_uninstall.py",
}
# The real checkout's per-verb module inventory, pinned explicitly: all three per-verb modules now
# ship (install agentic-sdlc-bfe9, uninstall agentic-sdlc-bbfe, update agentic-sdlc-b711), so this
# tuple is EMPTY and every mutating verb must refuse in its own module's name rather than through the
# loader's absence path. Absent-module refusals stay covered forever through the shadow checkout,
# which plants its own modules and can therefore withhold one.
ABSENT_MODULES: tuple[str, ...] = ()
# The five reader usage lines, pinned as literals rather than derived from the function under test.
# A refactor that reflows them is a change to a shipped grammar surface and must fail here. The
# fifth line is `recover`'s one mutating form (agentic-sdlc-baaa): the four read forms above it are
# unchanged, because the dry-run assessment stays byte-for-byte what it already was.
READER_USAGE_LINES = (
    "usage: ccodex sdlc inspect [--json]",
    "       ccodex sdlc status [--json]",
    "       ccodex sdlc doctor [--json]",
    "       ccodex sdlc recover --dry-run [--json]",
    "       ccodex sdlc recover --apply <plan-sha256>",
)
#: One approved plan digest, spelled the only way the grammar admits it: 64 lowercase hex.
PLAN_DIGEST = "5" * 64
READER_FORMS = (
    (("inspect",), ("inspect", False, False, None)),
    (("inspect", "--json"), ("inspect", False, True, None)),
    (("status",), ("status", False, False, None)),
    (("status", "--json"), ("status", False, True, None)),
    (("doctor",), ("doctor", False, False, None)),
    (("doctor", "--json"), ("doctor", False, True, None)),
    (("recover", "--dry-run"), ("recover", True, False, None)),
    (("recover", "--dry-run", "--json"), ("recover", True, True, None)),
    # The mutating form: never a dry run, never a report, and it carries the approved digest in the
    # same fourth slot that `install` uses for its explicit host.
    (("recover", "--apply", PLAN_DIGEST), ("recover", False, False, PLAN_DIGEST)),
)
#: Every recover spelling that is a grammar error, so exit 2 is proven per spelling and not once.
# `\d` would admit the Arabic-Indic digit, which is why an explicitly non-ASCII digest is pinned
# here: it must be REFUSED, not read as the same value.
REFUSED_RECOVER_FORMS = (
    ("recover",),
    ("recover", "--json"),
    ("recover", "--apply"),
    ("recover", "--apply", ""),
    ("recover", "--apply", "5" * 63),
    ("recover", "--apply", "5" * 65),
    ("recover", "--apply", "5" * 63 + "g"),
    ("recover", "--apply", ("5" * 63).upper() + "A"),
    ("recover", "--apply", "٩" * 64),
    ("recover", "--apply", "5" * 63 + "\n"),
    ("recover", "--apply", PLAN_DIGEST, "--json"),
    ("recover", "--apply", PLAN_DIGEST, PLAN_DIGEST),
    ("recover", f"--apply={PLAN_DIGEST}",),
    ("recover", "--dry-run", "--apply", PLAN_DIGEST),
    ("recover", "--apply", PLAN_DIGEST, "--dry-run"),
    ("recover", "--json", "--apply", PLAN_DIGEST),
)


class CcodexSdlcLifecycleGrammarTests(unittest.TestCase):
    # ---- harness -----------------------------------------------------------------------------

    def make_shadow_reader(self, root: Path) -> Path:
        """A physical checkout containing only the reader and its guard, so module presence is ours."""
        shadow = root / "shadow-checkout"
        for relative in (
            "policy/ccodex-sdlc-read-report.v1.json",
            "policy/release-contract.v1.json",
            "scripts/ccodex_sdlc.py",
            "scripts/ccodex_sdlc_readonly.py",
            "scripts/install_operator_tools.py",
            "scripts/install_skill_bundle.py",
        ):
            destination = shadow / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, destination)
        return shadow

    def write_module(self, shadow: Path, verb: str, body: str) -> Path:
        path = shadow / "scripts" / MUTATING_MODULES[verb]
        path.write_text(body, encoding="utf-8")
        return path

    def marker_module(self, marker: Path) -> str:
        return (
            "import json\n"
            "from pathlib import Path\n"
            "\n\n"
            "def main(argv):\n"
            f"    Path({str(marker)!r}).write_text(json.dumps(argv), encoding='utf-8')\n"
            "    return 0\n"
        )

    def run_reader(
        self, shadow: Path, *arguments: str, isolated: bool = True, home: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        flags = ["-I", "-B"] if isolated else []
        return subprocess.run(
            [str(Path(sys.executable)), *flags, str(shadow / "scripts" / "ccodex_sdlc.py"), *arguments],
            env={
                "HOME": str(home or (shadow.parent / "reader-home")),
                "LANG": "C",
                "LC_ALL": "C",
                "PATH": "",
                "XDG_STATE_HOME": str(shadow.parent / "reader-state"),
            },
            capture_output=True,
            text=True,
            check=False,
        )

    def make_dispatcher(self, root: Path) -> tuple[Path, dict[str, str], Path]:
        runtime = root / "runtime"
        runtime.mkdir()
        for name in ("ocx", "jq", "uv"):
            executable = runtime / name
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
        config = operator_tools.Config(
            ROOT,
            root / "install-home",
            root / "bin",
            root / "installer-state",
            False,
            False,
            runtime / "ocx",
            runtime / "jq",
            runtime / "uv",
            Path(sys.executable),
        )
        installed, messages = operator_tools.install(config)
        self.assertEqual(installed, 0, messages)
        query_home = root / "query-home"
        query_state = root / "query-state"
        environment = os.environ.copy()
        environment.update(
            {
                "AGENTIC_SDLC_ROOT": str(ROOT),
                "HOME": str(query_home),
                "XDG_BIN_HOME": str(root / "query-bin"),
                "XDG_STATE_HOME": str(query_state),
                "CODEX_HOME": str(query_home / ".codex"),
                "PYTHONPATH": str(root / "poisoned-pythonpath"),
            }
        )
        return config.bin_dir / "ccodex", environment, query_state

    def run_dispatcher(
        self, dispatcher: Path, environment: dict[str, str], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(dispatcher), *arguments],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def make_candidate_projection(self, root: Path) -> tuple[Path, Path]:
        """Render the candidate read-only profile of the dispatcher over a stub interpreter."""
        # The interpreter comes from the installer's own resolver, never from a literal path: this
        # harness used to render `#!/usr/bin/bash` and then check its syntax with `/usr/bin/bash -n`,
        # which is a path macOS does not have -- so on macOS the test errored with FileNotFoundError
        # against the interpreter instead of measuring the grammar it exists to measure.
        interpreter = operator_tools.bash_interpreter()
        rendered = (
            LAUNCHER_TEMPLATE.read_text(encoding="utf-8")
            .replace("@CANDIDATE_READONLY_PROFILE@", "true")
            .replace("@CANONICAL_LAUNCHER@", "''")
            .replace("@CANONICAL_ROOT@", "''")
            .replace("@PINNED_BASH@", str(interpreter))
            .replace("@PINNED_OCX@", "''")
            .replace("@PINNED_JQ@", "''")
            .replace("@PINNED_UV@", "''")
            .replace("@PINNED_SDLC_PYTHON@", "''")
        )
        self.assertNotIn("@CANDIDATE_", rendered)
        self.assertNotIn("@PINNED_", rendered)
        projection = root / "candidate"
        (projection / "bin").mkdir(parents=True)
        (projection / "scripts").mkdir()
        (projection / "runtime" / "python" / "bin").mkdir(parents=True)
        dispatcher = projection / "bin" / "ccodex"
        dispatcher.write_text(rendered, encoding="utf-8")
        dispatcher.chmod(0o755)
        syntax = subprocess.run(
            [str(interpreter), "-n", str(dispatcher)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        (projection / "scripts" / "ccodex_sdlc.py").write_text("# stub reader\n", encoding="utf-8")
        marker = root / "candidate-interpreter-ran"
        interpreter = projection / "runtime" / "python" / "bin" / "python3.12"
        interpreter.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{marker}'\nexit 0\n")
        interpreter.chmod(0o755)
        return dispatcher, marker

    # ---- dispatch ----------------------------------------------------------------------------

    def test_each_mutating_verb_dispatches_to_its_own_named_module_with_the_admitted_vector(self) -> None:
        for vector in MUTATING_VECTORS:
            verb = vector[0]
            with self.subTest(verb=verb), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                shadow = self.make_shadow_reader(root)
                marker = root / f"{verb}-ran.json"
                self.write_module(shadow, verb, self.marker_module(marker))
                # Negative control: every OTHER module stays absent, so a passing run proves the
                # reader resolved this verb's own module path rather than any sibling.
                for other in MUTATING_MODULES.values():
                    if other != MUTATING_MODULES[verb]:
                        self.assertFalse((shadow / "scripts" / other).exists())

                completed = self.run_reader(shadow, *vector)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(completed.stderr, "")
                self.assertTrue(marker.is_file(), completed.stdout)
                forwarded = json.loads(marker.read_text(encoding="utf-8"))
                self.assertEqual(forwarded, ["--host", "claude"] if verb == "install" else [])

    def test_absent_module_refuses_by_name_at_exit_three_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = self.make_shadow_reader(root)
            for vector in MUTATING_VECTORS:
                verb = vector[0]
                with self.subTest(verb=verb):
                    completed = self.run_reader(shadow, *vector)

                    self.assertEqual(completed.returncode, 3, completed.stderr)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn(f"ccodex sdlc {verb} is unavailable in this distribution", completed.stderr)
                    self.assertIn(str(shadow / "scripts" / MUTATING_MODULES[verb]), completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    self.assertNotIn("ReportInvariantError", completed.stderr)
            # Positive control: the identical harness reports 0 once the module exists, so the
            # exit-3 refusals above are the missing module and not a broken invocation.
            marker = root / "control.json"
            self.write_module(shadow, "update", self.marker_module(marker))
            control = self.run_reader(shadow, "update")
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertTrue(marker.is_file())

    def test_a_symlinked_module_is_refused_before_it_can_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = self.make_shadow_reader(root)
            marker = root / "linked-ran.json"
            real = root / "elsewhere-ccodex_sdlc_update.py"
            real.write_text(self.marker_module(marker), encoding="utf-8")
            link = shadow / "scripts" / MUTATING_MODULES["update"]
            link.symlink_to(real)

            linked = self.run_reader(shadow, "update")

            self.assertEqual(linked.returncode, 3, linked.stderr)
            self.assertIn("ccodex sdlc update is unavailable in this distribution", linked.stderr)
            self.assertFalse(marker.exists())
            # Positive control: the same bytes at a physical path do run, so the refusal is about
            # the link and not about the module's contents.
            link.unlink()
            shutil.copy2(real, link)
            physical = self.run_reader(shadow, "update")
            self.assertEqual(physical.returncode, 0, physical.stderr)
            self.assertTrue(marker.is_file())

    def test_an_unadmitted_runtime_refuses_before_the_module_is_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = self.make_shadow_reader(root)
            marker = root / "install-ran.json"
            self.write_module(shadow, "install", self.marker_module(marker))

            unadmitted = self.run_reader(shadow, "install", "--host", "claude", isolated=False)

            self.assertEqual(unadmitted.returncode, 3, unadmitted.stderr)
            self.assertIn("ccodex sdlc install requires its bound isolated Python 3.12.11", unadmitted.stderr)
            self.assertNotIn("Traceback", unadmitted.stderr)
            self.assertFalse(marker.exists(), "an unadmitted runtime must refuse before any module runs")
            # Positive control: with -I -B the very same module is entered.
            admitted = self.run_reader(shadow, "install", "--host", "claude")
            self.assertEqual(admitted.returncode, 0, admitted.stderr)
            self.assertTrue(marker.is_file())

    def test_post_import_outcomes_are_admitted_unknown_effects_rather_than_clean_refusals(self) -> None:
        cases = (
            ("import-raises", "raise RuntimeError('module body failed')\n", 4, "failed while loading"),
            ("no-main", "value = 1\n", 4, "exposes no callable main(argv)"),
            ("main-not-callable", "main = 3\n", 4, "exposes no callable main(argv)"),
            (
                "main-raises",
                "def main(argv):\n    raise ValueError('mid-flight')\n",
                4,
                "failed inside its module",
            ),
            (
                "main-returns-text",
                "def main(argv):\n    return 'ok'\n",
                4,
                "returned no admitted exit class",
            ),
            (
                "main-returns-out-of-range",
                "def main(argv):\n    return 5\n",
                4,
                "returned no admitted exit class",
            ),
            (
                "main-returns-bool",
                "def main(argv):\n    return True\n",
                4,
                "returned no admitted exit class",
            ),
        )
        for label, body, expected, fragment in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as temp:
                shadow = self.make_shadow_reader(Path(temp))
                self.write_module(shadow, "uninstall", body)

                completed = self.run_reader(shadow, "uninstall")

                self.assertEqual(completed.returncode, expected, completed.stderr)
                self.assertIn(fragment, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
        with tempfile.TemporaryDirectory() as temp:
            # Positive controls: an admitted exit class is forwarded verbatim and silently, so the
            # exit-4 classifications above are decisions and not a blanket rewrite of every result.
            for returned in (0, 3):
                shadow = self.make_shadow_reader(Path(temp) / f"case-{returned}")
                self.write_module(shadow, "uninstall", f"def main(argv):\n    return {returned}\n")
                forwarded = self.run_reader(shadow, "uninstall")
                self.assertEqual(forwarded.returncode, returned, forwarded.stderr)
                self.assertEqual(forwarded.stderr, "")

    # ---- candidate projection ----------------------------------------------------------------

    def test_candidate_dispatcher_refuses_every_mutating_verb_and_still_admits_readers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, marker = self.make_candidate_projection(root)
            for vector in MUTATING_VECTORS:
                with self.subTest(verb=vector[0]):
                    completed = subprocess.run(
                        [str(dispatcher), "sdlc", *vector],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("candidate ccodex admits only read-only sdlc inspection", completed.stderr)
                    self.assertEqual(completed.stdout, "")
                    self.assertFalse(marker.exists(), "a refused candidate vector must not reach the interpreter")
            # Positive control: the same rendered dispatcher does admit each read-only vector and
            # reaches the projected interpreter, so the refusals above are verb-specific.
            for reader_vector in (
                ("inspect",),
                ("inspect", "--json"),
                ("status",),
                ("status", "--json"),
                ("doctor",),
                ("doctor", "--json"),
                ("recover", "--dry-run"),
                ("recover", "--dry-run", "--json"),
            ):
                with self.subTest(reader=reader_vector):
                    completed = subprocess.run(
                        [str(dispatcher), "sdlc", *reader_vector],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(marker.is_file())
            forwarded = marker.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(forwarded), 8)
            for line in forwarded:
                self.assertIn("--candidate-observation-v1", line)
            self.assertTrue(any(line.endswith("--candidate-observation-v1 inspect") for line in forwarded))
            self.assertTrue(
                any(line.endswith("--candidate-observation-v1 recover --dry-run --json") for line in forwarded)
            )

    def test_candidate_reader_invoked_directly_also_refuses_mutating_verbs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = self.make_shadow_reader(root)
            for verb, extra in (("install", ("--host", "claude")), ("update", ()), ("uninstall", ())):
                with self.subTest(verb=verb):
                    marker = root / f"{verb}-ran.json"
                    self.write_module(shadow, verb, self.marker_module(marker))

                    refused = self.run_reader(shadow, "--candidate-observation-v1", verb, *extra)

                    self.assertEqual(refused.returncode, 3, refused.stderr)
                    self.assertIn("candidate ccodex sdlc admits only read-only inspection", refused.stderr)
                    self.assertIn(f"{verb} is a mutating lifecycle verb", refused.stderr)
                    self.assertEqual(refused.stdout, "")
                    self.assertFalse(marker.exists())
            # Positive control: the candidate flag itself is not what refuses. A reader verb gets
            # past this gate and is declined later, by the candidate discriminator, with its own
            # distinct message.
            control = self.run_reader(shadow, "--candidate-observation-v1", "inspect", "--json")
            self.assertEqual(control.returncode, 3, control.stderr)
            self.assertIn("candidate subordinate observation refused", control.stderr)
            self.assertNotIn("mutating lifecycle verb", control.stderr)

    # ---- grammar errors ----------------------------------------------------------------------

    def test_reader_grammar_and_its_usage_lines_are_byte_for_byte_unaffected(self) -> None:
        rendered = reader.usage()
        self.assertEqual(rendered.splitlines()[: len(READER_USAGE_LINES)], list(READER_USAGE_LINES))
        for arguments, expected in READER_FORMS:
            with self.subTest(arguments=arguments):
                self.assertEqual(reader.parse_command(list(arguments)), expected)
        for invalid in (
            ("inspect", "--dry-run"),
            ("status", "--host", "claude"),
            ("doctor", "--json", "--json"),
            ("recover", "--json", "--dry-run"),
            ("recover", "--dry-run", "--dry-run"),
            *REFUSED_RECOVER_FORMS,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(reader.UsageError):
                    reader.parse_command(list(invalid))
        # Positive control for the whole matrix above: the one admitted mutating spelling parses,
        # so those refusals are the grammar's verdicts and not `parse_command` refusing everything.
        self.assertEqual(
            reader.parse_command(["recover", "--apply", PLAN_DIGEST]),
            ("recover", False, False, PLAN_DIGEST),
        )
        # A digest is not a host and a host is not a digest: the shared fourth slot never lets one
        # verb's argument reach the other's module.
        self.assertEqual(reader.parse_command(["install", "--host", "claude"])[3], "claude")
        with self.assertRaises(reader.UsageError):
            reader.parse_command(["install", "--host", PLAN_DIGEST])

    def test_installed_dispatcher_forwards_the_closed_grammar_and_writes_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for vector in MUTATING_VECTORS:
                verb = vector[0]
                with self.subTest(verb=verb):
                    completed = self.run_dispatcher(dispatcher, environment, "sdlc", *vector)
                    self.assertEqual(completed.returncode, 3, completed.stderr)
                    if verb in ABSENT_MODULES:
                        self.assertIn(
                            f"ccodex sdlc {verb} is unavailable in this distribution", completed.stderr
                        )
                        self.assertIn(str(ROOT / "scripts" / MUTATING_MODULES[verb]), completed.stderr)
                    else:
                        # The shipped module itself refuses pre-effect, in its own name; the
                        # loader's absence refusal appearing here would mean dispatch never
                        # reached it.
                        self.assertIn(f"error: ccodex sdlc {verb} ", completed.stderr)
                        self.assertNotIn("is unavailable in this distribution", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    self.assertEqual(completed.stdout, "")
            # Positive control: the same dispatcher still serves a reader verb end to end.
            control = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertEqual(json.loads(control.stdout)["command"]["verb"], "inspect")
            self.assertFalse(query_state.exists())

    def test_unknown_verbs_the_dropped_profiles_family_and_refresh_are_grammar_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for vector, fragment in (
                (("profiles",), "unknown ccodex sdlc verb: 'profiles'"),
                (("profiles", "list"), "unknown ccodex sdlc verb: 'profiles'"),
                (("profile",), "unknown ccodex sdlc verb: 'profile'"),
                (("refresh",), "unknown ccodex sdlc verb: 'refresh'"),
                (("follow",), "unknown ccodex sdlc verb: 'follow'"),
                ((), "ccodex sdlc needs inspect"),
                (("install", "--profile", "claude"), "unknown ccodex sdlc install argument: '--profile'"),
            ):
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, "sdlc", *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("usage: ccodex sdlc", completed.stderr)
                    self.assertIn(fragment, completed.stderr)
            help_output = self.run_dispatcher(dispatcher, environment, "sdlc", "--help")
            self.assertEqual(help_output.returncode, 0, help_output.stderr)
            for named in ("ccodex sdlc install --host claude", "ccodex sdlc update", "ccodex sdlc uninstall"):
                self.assertIn(named, help_output.stdout)
            self.assertNotIn("profile", help_output.stdout)
            self.assertNotIn("refresh", help_output.stdout)
            # Positive control for the negative substring assertions above: the same reader would
            # have surfaced a `profiles` verb here, and this is what its absence is measured against.
            self.assertIn("update", help_output.stdout)
            self.assertFalse(query_state.exists())

    def test_dispatcher_help_names_the_three_lifecycle_verbs_and_no_dropped_verb_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))

            completed = self.run_dispatcher(dispatcher, environment, "--help")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            for named in ("sdlc install --host claude", "sdlc update", "sdlc uninstall"):
                self.assertIn(named, completed.stdout)
            # Positive control for the two negative assertions: the dispatcher's help really is the
            # document being searched, and it really does carry the sdlc reader lines beside them.
            self.assertIn("sdlc <inspect|status|doctor> [--json]", completed.stdout)
            self.assertIn("sdlc recover --dry-run [--json]", completed.stdout)
            self.assertNotIn("profile", completed.stdout)
            self.assertNotIn("refresh", completed.stdout)
            self.assertFalse(query_state.exists())

    def test_install_requires_an_explicit_claude_host_and_names_which_half_was_wrong(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for vector, fragment in (
                (("install",), "requires an explicit --host claude; there is no default host"),
                (("install", "--host"), "--host was supplied without a host value"),
                (("install", "--host", ""), "unsupported ccodex sdlc install host: ''"),
                (("install", "--host", "codex"), "unsupported ccodex sdlc install host: 'codex'"),
                (("install", "--host", "all"), "unsupported ccodex sdlc install host: 'all'"),
                (("install", "--host", "*"), "unsupported ccodex sdlc install host: '*'"),
                (("install", "--host=claude"), "spells its host as two arguments: --host claude"),
                (("install", "--host", "claude", "--json"), "accepts exactly --host claude: '--json'"),
                (("install", "--host", "claude", "extra"), "accepts exactly --host claude: 'extra'"),
                (("update", "--json"), "ccodex sdlc update accepts no arguments: '--json'"),
                (("update", "--host", "claude"), "ccodex sdlc update accepts no arguments: '--host'"),
                (("uninstall", "--host", "claude"), "ccodex sdlc uninstall accepts no arguments: '--host'"),
                (("uninstall", "--dry-run"), "ccodex sdlc uninstall accepts no arguments: '--dry-run'"),
            ):
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, "sdlc", *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("usage: ccodex sdlc", completed.stderr)
                    self.assertIn(fragment, completed.stderr)
            # Positive control: the one admitted spelling is NOT a grammar error. It reaches the
            # shipped install module and refuses there pre-effect, which is what makes the exit-2s
            # above attributable to the spelling rather than to the verb being unreachable.
            admitted = self.run_dispatcher(dispatcher, environment, "sdlc", "install", "--host", "claude")
            self.assertEqual(admitted.returncode, 3, admitted.stderr)
            self.assertIn("ccodex sdlc install refused before any effect", admitted.stderr)
            self.assertNotIn("usage: ccodex sdlc", admitted.stderr)
            self.assertFalse(query_state.exists())

    def test_a_control_character_in_a_refused_argument_cannot_forge_an_output_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, _query_state = self.make_dispatcher(Path(temp))
            forged = "claude\nerror: ccodex sdlc install completed"

            completed = self.run_dispatcher(dispatcher, environment, "sdlc", "install", "--host", forged)

            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("\\n", completed.stderr)
            # The forged text survives only INSIDE one escaped token. What must not happen is a
            # line of this command's own output that the caller wrote: no rendered line may begin
            # with the injected sentence, and the raw newline must never reach the stream.
            self.assertNotIn(forged, completed.stderr)
            for line in completed.stderr.splitlines():
                self.assertFalse(
                    line.startswith("error: ccodex sdlc install completed"),
                    f"a caller argument forged an output line: {line!r}",
                )
            # Positive control: an ordinary value is still rendered plainly, so the escaping above
            # is escaping and not a blanket refusal to echo the caller's token.
            plain = self.run_dispatcher(dispatcher, environment, "sdlc", "install", "--host", "codex")
            self.assertIn("unsupported ccodex sdlc install host: 'codex'", plain.stderr)
            self.assertNotIn("\\n", plain.stderr)

    # ---- the reader keeps borrowing no writer authority ---------------------------------------

    def test_the_read_only_guard_still_blocks_its_anticipated_mutator_names(self) -> None:
        adapter = ModuleType("lifecycle_grammar_fake_adapter")
        for name in ("install", "uninstall", "write_state", "durable_unlink", "readonly_projection"):
            setattr(adapter, name, lambda name=name: name)
        # Positive control BEFORE blocking: every one of these names is reachable, so the failures
        # after blocking are the guard's work rather than a missing attribute.
        for name in ("install", "uninstall", "write_state", "durable_unlink", "readonly_projection"):
            self.assertTrue(callable(getattr(adapter, name)))
        guard.block_lifecycle_mutators(adapter)
        for name in ("install", "uninstall", "write_state", "durable_unlink"):
            with self.subTest(name=name):
                with self.assertRaises(guard.ReadOnlyViolation):
                    getattr(adapter, name)()
        self.assertEqual(adapter.readonly_projection(), "readonly_projection")

    def test_the_reader_holds_no_lifecycle_module_of_its_own(self) -> None:
        for verb, module_name in MUTATING_MODULES.items():
            with self.subTest(verb=verb):
                path = reader.lifecycle_module_path(verb)
                self.assertEqual(path, ROOT / "scripts" / module_name)
                if verb in ABSENT_MODULES:
                    self.assertFalse(
                        path.exists(),
                        "this verb's per-verb module is a separate, not-yet-landed ticket",
                    )
                else:
                    self.assertTrue(
                        path.exists(),
                        "a shipped per-verb module went missing; dispatch would silently regress"
                        " to the absence refusal",
                    )
        self.assertEqual(sorted(reader.LIFECYCLE_VERBS), ["install", "uninstall", "update"])
        self.assertEqual(reader.LIFECYCLE_HOSTS, ("claude",))


if __name__ == "__main__":
    unittest.main()
