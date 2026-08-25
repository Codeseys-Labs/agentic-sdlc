"""The closed ``ccodex sdlc`` lifecycle grammar: three mutating verbs that only ever hand off.

This module covers exactly the grammar/dispatch boundary. It does not test lifecycle behavior,
because no lifecycle behavior exists yet: ``scripts/ccodex_sdlc_install.py``,
``ccodex_sdlc_update.py``, and ``ccodex_sdlc_uninstall.py`` are separate tickets. What must hold
today is that a mutating verb parses, resolves ONE named module path, and refuses BY NAME at exit 3
before any effect when that module is absent -- never an exit-1 traceback.

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
#: The committed, self-locating dispatcher (gh #10 phase 4 deleted the rendered
#: assets/launchers/ccodex.in template and its install_operator_tools.py renderer). There is no
#: install step any more: this file IS the dispatcher a real checkout ships, so the grammar tests
#: below drive it directly rather than rendering a synthetic copy.
DISPATCHER_SCRIPT = ROOT / "bin" / "ccodex"

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


def load_module(name: str, path: Path):
    """Load one shipped module by absolute path, for the cross-module vocabulary pins below."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Every mutating verb carries an explicit host, and BOTH planes appear so a vector set that only ever
# spelled `claude` could not pass while the codex arm was broken.
MUTATING_VECTORS = (
    ("install", "--host", "claude"),
    ("install", "--host", "codex"),
    ("update", "--host", "claude"),
    ("update", "--host", "codex"),
    ("uninstall", "--host", "claude"),
    ("uninstall", "--host", "codex"),
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


@unittest.skipIf(
    os.name == "nt",
    "grammar refusals are asserted against the installed bash ccodex dispatcher, whose "
    "lifecycle writes through the POSIX-only durable-write plane (os.open O_DIRECTORY "
    "fsync barriers); native Windows fails closed by name at the CLI",
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
        """An isolated per-test query plane for the ``ccodex sdlc`` grammar, no install step.

        gh #10 phase 4 deleted the rendered ``assets/launchers/ccodex.in`` template and its
        install-time ``ocx``/``jq``/``uv``/interpreter binding along with it: the committed
        ``bin/ccodex`` self-locates its root and resolves ``sdlc``'s pinned interpreter at RUN time
        through ``mise -C <root> exec``, which in turn requires this exact root's ``mise.toml`` to
        be trusted under the REAL operator ``HOME`` -- a fact this suite's isolated ``HOME`` can
        never carry without a persistent trust mutation. ``run_dispatcher`` therefore drives the
        reader directly, under the same ``-I -B`` isolation the installed dispatcher's own
        ``run_sdlc_python`` route resolves and execs, over exactly this isolated environment; the
        toolchain-resolution boundary itself is proven elsewhere (``tests/test_bin_ccodex.py``,
        ``tests/test_ccodex_seam.py``), not duplicated here.
        """
        query_home = root / "query-home"
        query_state = root / "query-state"
        environment = os.environ.copy()
        environment.update(
            {
                "HOME": str(query_home),
                "XDG_STATE_HOME": str(query_state),
                "CODEX_HOME": str(query_home / ".codex"),
                "PYTHONPATH": str(root / "poisoned-pythonpath"),
            }
        )
        return DISPATCHER_SCRIPT, environment, query_state

    def run_dispatcher(
        self, dispatcher: Path, environment: dict[str, str], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        """Drive one ``ccodex`` invocation, routed the way ``bin/ccodex`` itself would route it.

        A leading ``sdlc`` is this suite's OWN entire subject and is driven directly against the
        real reader under ``-I -B`` (see ``make_dispatcher``); every other route in this file is
        tool-free (``--help``, ``version``) and is answered by the real committed ``dispatcher``
        itself with no toolchain involved, so it is driven exactly as an operator would type it.
        """
        if arguments and arguments[0] == "sdlc":
            return subprocess.run(
                [str(Path(sys.executable)), "-I", "-B", str(READER_SCRIPT), *arguments[1:]],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
        return subprocess.run(
            [str(dispatcher), *arguments],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

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
                self.assertEqual(forwarded, ["--host", vector[2]])

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
            control = self.run_reader(shadow, "update", "--host", "claude")
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

            linked = self.run_reader(shadow, "update", "--host", "claude")

            self.assertEqual(linked.returncode, 3, linked.stderr)
            self.assertIn("ccodex sdlc update is unavailable in this distribution", linked.stderr)
            self.assertFalse(marker.exists())
            # Positive control: the same bytes at a physical path do run, so the refusal is about
            # the link and not about the module's contents.
            link.unlink()
            shutil.copy2(real, link)
            physical = self.run_reader(shadow, "update", "--host", "claude")
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

                completed = self.run_reader(shadow, "uninstall", "--host", "claude")

                self.assertEqual(completed.returncode, expected, completed.stderr)
                self.assertIn(fragment, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
        with tempfile.TemporaryDirectory() as temp:
            # Positive controls: an admitted exit class is forwarded verbatim and silently, so the
            # exit-4 classifications above are decisions and not a blanket rewrite of every result.
            for returned in (0, 3):
                shadow = self.make_shadow_reader(Path(temp) / f"case-{returned}")
                self.write_module(shadow, "uninstall", f"def main(argv):\n    return {returned}\n")
                forwarded = self.run_reader(shadow, "uninstall", "--host", "claude")
                self.assertEqual(forwarded.returncode, returned, forwarded.stderr)
                self.assertEqual(forwarded.stderr, "")

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
        self.assertEqual(reader.parse_command(["install", "--host", "codex"])[3], "codex")
        self.assertEqual(reader.parse_command(["uninstall", "--host", "codex"])[3], "codex")
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
            for named in (
                "ccodex sdlc install --host claude|codex",
                "ccodex sdlc update --host claude|codex",
                "ccodex sdlc uninstall --host claude|codex",
            ):
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
            for named in (
                "sdlc install --host <claude|codex>",
                "sdlc update --host <claude|codex>",
                "sdlc uninstall --host <claude|codex>",
            ):
                self.assertIn(named, completed.stdout)
            # Positive control for the two negative assertions: the dispatcher's help really is the
            # document being searched, and it really does carry the sdlc reader lines beside them.
            self.assertIn("sdlc <inspect|status|doctor> [--json]", completed.stdout)
            self.assertIn("sdlc recover --dry-run [--json]", completed.stdout)
            self.assertNotIn("profile", completed.stdout)
            self.assertNotIn("refresh", completed.stdout)
            self.assertFalse(query_state.exists())

    def test_every_mutating_verb_requires_an_explicit_host_and_names_which_half_was_wrong(self) -> None:
        """All three verbs, not just install: a bare mutating verb would have to pick a plane.

        Before the codex arm, `update` and `uninstall` took no arguments and each module named its own
        single plane. With two planes live that omission is the cross-agent defect at the grammar layer,
        so the selector is required everywhere and the refusals below are proven per verb.
        """
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            per_verb = []
            for verb in ("install", "update", "uninstall"):
                per_verb.extend(
                    (
                        ((verb,), f"ccodex sdlc {verb} requires an explicit --host claude|codex; there is no default host"),
                        ((verb, "--host"), f"ccodex sdlc {verb} --host was supplied without a host value"),
                        ((verb, "--host", ""), f"unsupported ccodex sdlc {verb} host: ''"),
                        ((verb, "--host", "all"), f"unsupported ccodex sdlc {verb} host: 'all'"),
                        ((verb, "--host", "*"), f"unsupported ccodex sdlc {verb} host: '*'"),
                        ((verb, "--host", "gemini"), f"unsupported ccodex sdlc {verb} host: 'gemini'"),
                        ((verb, "--host=claude"), f"ccodex sdlc {verb} spells its host as two arguments"),
                        ((verb, "--host", "claude", "--json"), f"ccodex sdlc {verb} accepts exactly --host claude|codex: '--json'"),
                        ((verb, "--host", "codex", "extra"), f"ccodex sdlc {verb} accepts exactly --host claude|codex: 'extra'"),
                        ((verb, "--profile", "claude"), f"unknown ccodex sdlc {verb} argument: '--profile'"),
                    )
                )
            for vector, fragment in per_verb:
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, "sdlc", *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("usage: ccodex sdlc", completed.stderr)
                    self.assertIn(fragment, completed.stderr)
            # Positive control, on BOTH planes: an admitted spelling is NOT a grammar error. Each
            # reaches its shipped module and refuses there pre-effect, which is what makes the exit-2s
            # above attributable to the spelling rather than to the plane being unreachable.
            for verb in ("install", "update", "uninstall"):
                for agent in ("claude", "codex"):
                    with self.subTest(admitted=(verb, agent)):
                        admitted = self.run_dispatcher(
                            dispatcher, environment, "sdlc", verb, "--host", agent
                        )
                        self.assertEqual(admitted.returncode, 3, admitted.stderr)
                        self.assertIn(f"error: ccodex sdlc {verb}", admitted.stderr)
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
            plain = self.run_dispatcher(dispatcher, environment, "sdlc", "install", "--host", "gemini")
            self.assertIn("unsupported ccodex sdlc install host: 'gemini'", plain.stderr)
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
        self.assertEqual(reader.LIFECYCLE_HOSTS, ("claude", "codex"))
        # The three re-expressions of one host vocabulary, pinned against each other: the reader's
        # grammar tuple, the closed host-plane table it is a copy of, and the receipt family's own
        # `HOSTS`, which is what a sealed body's `scope.agent` is checked against. Widening one and not
        # the others is what this equality exists to fail on.
        planes = load_module("lifecycle_grammar_host_planes", ROOT / "scripts" / "ccodex_sdlc_host_planes.py")
        receipts = load_module(
            "lifecycle_grammar_receipts", ROOT / "scripts" / "distribution_activation_receipt.py"
        )
        self.assertEqual(reader.LIFECYCLE_HOSTS, planes.AGENTS)
        self.assertEqual(tuple(sorted(receipts.HOSTS)), planes.AGENTS)
        self.assertEqual(reader.LIFECYCLE_HOST_CHOICE, "claude|codex")


if __name__ == "__main__":
    unittest.main()
