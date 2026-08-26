"""The closed ``ccodex`` lifecycle grammar: three mutating verbs that only ever hand off.

This module covers exactly the grammar/dispatch boundary. It does not test lifecycle behavior,
because the per-verb modules own that: ``scripts/ccodex_sdlc_install.py``, ``ccodex_sdlc_update.py``,
and ``ccodex_sdlc_uninstall.py`` each have their own refusal ladder and their own suite. What must
hold here is that a mutating verb parses, resolves ONE named module path, and refuses BY NAME at
exit 3 before any effect when that module is absent -- never an exit-1 traceback.

THE VERBS ARE TOP-LEVEL NOW (ratified decision 1, agentic-sdlc-7a2b). ``ccodex sdlc <verb>`` and
``ccodex bundle <verb>`` are both retired at the dispatcher, so every vector below is typed the way
an operator types it: ``ccodex install --scope user --agent claude``. Two consequences run through
this file. First, ``--host`` left the OPERATOR grammar and was replaced by ``--agent``, while the
vector this reader FORWARDS to a per-verb module is still ``['--host', <agent>]`` -- one fact with
one operator spelling and one module ABI, asserted in both places rather than assumed to agree.
Second, the per-verb modules are owned by other waves and still name themselves ``ccodex sdlc
<verb>`` in their own refusals, so the assertions on their stderr state what the product emits.

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
#: The committed, self-locating dispatcher, driven as a real process. This suite used to drive the
#: reader directly under ``-I -B`` from ``run_dispatcher``, because ``bin/ccodex`` refuses an
#: untrusted root and the trust it wants is scoped to the REAL operator ``HOME`` -- a fact an
#: isolated test ``HOME`` can never carry without a persistent operator mutation. The subprocess-seam
#: harness closed that gap with a recording stub ``mise`` standing at exactly that boundary, so the
#: grammar tests below now reach their decisions through the same argv path an operator does.
#: ``seam.stub_dispatcher_environment`` is IMPORTED rather than re-implemented: a second copy of the
#: stub would be a second opinion about which routes the dispatcher can build.
#:
#: The SHADOW-checkout tests keep their own direct invocation (``run_reader``) and say why in place:
#: their subject is which per-verb modules exist in a synthetic tree, and the dispatcher self-locates
#: its root as the parent of its own ``bin/``, so it can only ever address the real checkout.
DISPATCHER_SCRIPT = ROOT / "bin" / "ccodex"
SEAM_HARNESS = ROOT / "tests" / "seam_harness.py"

_seam_spec = importlib.util.spec_from_file_location("lifecycle_grammar_seam_harness", SEAM_HARNESS)
assert _seam_spec and _seam_spec.loader
seam = importlib.util.module_from_spec(_seam_spec)
sys.modules[_seam_spec.name] = seam
_seam_spec.loader.exec_module(seam)

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


#: The scope every vector in this file drives. `--scope` is required on all four selector verbs and
#: has no default, and `project` PARSES but is refused by name at exit 3 until the wave that wires
#: it, so `user` is the only scope that can reach a per-verb module today.
USER_SCOPE = ("--scope", "user")
# Every mutating verb carries an explicit scope AND an explicit agent, and BOTH planes appear so a
# vector set that only ever spelled `claude` could not pass while the codex arm was broken. The agent
# is last in each vector, which is what `vector[-1]` reads below.
MUTATING_VECTORS = (
    ("install", *USER_SCOPE, "--agent", "claude"),
    ("install", *USER_SCOPE, "--agent", "codex"),
    ("update", *USER_SCOPE, "--agent", "claude"),
    ("update", *USER_SCOPE, "--agent", "codex"),
    ("uninstall", *USER_SCOPE, "--agent", "claude"),
    ("uninstall", *USER_SCOPE, "--agent", "codex"),
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
# The six reader usage lines, pinned as literals rather than derived from the function under test.
# A refactor that reflows them is a change to a shipped grammar surface and must fail here. They are
# SIX now, not five, and every one of them changed: the front-door wave dropped the `sdlc` word,
# retired `inspect` as a fourth spelling of a read, and gave the four selector verbs the two
# selectors they require. `recover`'s two forms collapsed onto one line.
READER_USAGE_LINES = (
    "usage: ccodex install   --scope user|project --agent claude|codex [--project PATH]"
    " [--mode auto|link|copy] [--dry-run]",
    "       ccodex status    --scope user|project --agent claude|codex [--project PATH] [--json]",
    "       ccodex update    --scope user|project --agent claude|codex [--project PATH]",
    "       ccodex uninstall --scope user|project --agent claude|codex [--project PATH] [--dry-run]",
    "       ccodex doctor    [--json]",
    "       ccodex recover   --dry-run [--json] | --apply <plan-sha256>",
)
#: One approved plan digest, spelled the only way the grammar admits it: 64 lowercase hex.
PLAN_DIGEST = "5" * 64
# `parse_command` returns an `Invocation` NamedTuple of SIX fields now -- the original four plus the
# parsed `scope` and `agent` -- so an expected value is a six-tuple and a read's two trailing slots
# are `None`. A NamedTuple compares equal to a plain tuple of the same length, which is what keeps
# these expectations readable without importing the class.
READER_FORMS = (
    (("status", *USER_SCOPE, "--agent", "claude"), ("status", False, False, None, "user", "claude")),
    (
        ("status", *USER_SCOPE, "--agent", "codex", "--json"),
        ("status", False, True, None, "user", "codex"),
    ),
    (("doctor",), ("doctor", False, False, None, None, None)),
    (("doctor", "--json"), ("doctor", False, True, None, None, None)),
    (("recover", "--dry-run"), ("recover", True, False, None, None, None)),
    (("recover", "--dry-run", "--json"), ("recover", True, True, None, None, None)),
    # The mutating form: never a dry run, never a report, and it carries the approved digest in the
    # same fourth slot that `install` uses for its explicit agent.
    (("recover", "--apply", PLAN_DIGEST), ("recover", False, False, PLAN_DIGEST, None, None)),
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
#: What each mutating verb answers when a read-only flag rides along. The admitted set is closed PER
#: VERB rather than shared -- only `install` takes `--mode`, and only `install` and `uninstall` take
#: `--dry-run` -- so the refusal enumerates that verb's own flags and the three literals differ. One
#: shared f-string here would have hidden exactly the drift this pins.
UNADMITTED_JSON_REFUSAL = {
    "install": "ccodex install does not take --json; it accepts"
    " --scope --agent --project --mode --dry-run",
    "update": "ccodex update does not take --json; it accepts --scope --agent --project",
    "uninstall": "ccodex uninstall does not take --json; it accepts"
    " --scope --agent --project --dry-run",
}


@unittest.skipIf(
    os.name == "nt",
    "grammar refusals are asserted against the committed bash ccodex dispatcher, whose "
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
        """Drive the SHADOW checkout's own reader copy directly, under the route it is exec'd on.

        Direct on purpose, and not a gap the seam harness could close: these cases own which per-verb
        modules EXIST, which means planting and withholding them in a synthetic tree, and
        ``bin/ccodex`` self-locates its distribution root as the parent of its own ``bin/`` -- it can
        only ever address the real checkout, whose three modules all ship. ``-I -B`` is the exact
        shape ``run_sdlc_python`` execs, and ``isolated=False`` is how the one runtime-admission case
        below hands the reader an interpreter the dispatcher never would.
        """
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
        """An isolated per-test query plane plus the stub toolchain the real dispatcher needs.

        See the module note: the environment is an ALLOWLIST built by the seam harness rather than
        ``os.environ`` plus overrides, so no inherited tool root or state root can re-enter the route
        and make a refusal describe the developer's machine. The two extras are this file's own:
        ``CODEX_HOME`` because the codex plane's module reads it, and a poisoned ``PYTHONPATH`` the
        reader's own ``-I`` isolation must ignore on every one of these runs.

        The state root is deliberately NOT created -- ``stub_dispatcher_environment`` leaves it
        absent -- which is what lets the tests below observe that a grammar refusal wrote nothing
        rather than spending that observation on their behalf.
        """
        query_home = root / "query-home"
        query_state = root / "query-state"
        environment = seam.stub_dispatcher_environment(
            root,
            home=query_home,
            state=query_state,
            extra={
                "CODEX_HOME": str(query_home / ".codex"),
                "PYTHONPATH": str(root / "poisoned-pythonpath"),
            },
        )
        return DISPATCHER_SCRIPT, environment, query_state

    def run_dispatcher(
        self, dispatcher: Path, environment: dict[str, str], *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        """Drive one ``ccodex`` invocation through the committed dispatcher, as an operator does."""
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
            verb, agent = vector[0], vector[-1]
            with self.subTest(verb=verb, agent=agent), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                shadow = self.make_shadow_reader(root)
                marker = root / f"{verb}-{agent}-ran.json"
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
                # THE ASYMMETRY, OBSERVED AT ITS ONE SEAM. The operator typed `--agent`; what
                # arrives at the module is `--host`, because the four per-verb modules admit exactly
                # that ABI and are owned by other waves. `main` builds this vector in one place, so
                # this equality is what would fail if the operator spelling ever leaked through.
                self.assertEqual(forwarded, ["--host", agent])

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
                    # The loader names the verb the way an operator invoked it -- the `sdlc` word is
                    # gone from every message this reader owns, and survives only inside the per-verb
                    # modules' own refusals.
                    self.assertIn(f"ccodex {verb} is unavailable in this distribution", completed.stderr)
                    self.assertIn(str(shadow / "scripts" / MUTATING_MODULES[verb]), completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    self.assertNotIn("ReportInvariantError", completed.stderr)
            # Positive control: the identical harness reports 0 once the module exists, so the
            # exit-3 refusals above are the missing module and not a broken invocation.
            marker = root / "control.json"
            self.write_module(shadow, "update", self.marker_module(marker))
            control = self.run_reader(shadow, "update", *USER_SCOPE, "--agent", "claude")
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

            linked = self.run_reader(shadow, "update", *USER_SCOPE, "--agent", "claude")

            self.assertEqual(linked.returncode, 3, linked.stderr)
            self.assertIn("ccodex update is unavailable in this distribution", linked.stderr)
            self.assertFalse(marker.exists())
            # Positive control: the same bytes at a physical path do run, so the refusal is about
            # the link and not about the module's contents.
            link.unlink()
            shutil.copy2(real, link)
            physical = self.run_reader(shadow, "update", *USER_SCOPE, "--agent", "claude")
            self.assertEqual(physical.returncode, 0, physical.stderr)
            self.assertTrue(marker.is_file())

    def test_an_unadmitted_runtime_refuses_before_the_module_is_resolved(self) -> None:
        """DRIVEN DIRECTLY, and the interpreter is the whole subject.

        The dispatcher cannot be made to hand the reader a bad runtime: ``run_sdlc_python`` resolves
        the pinned managed CPython and execs it under ``-I -B``, which is precisely the shape this
        case has to violate. Routing it through ``bin/ccodex`` would assert nothing about the
        admission, so the unisolated invocation stays this suite's own.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = self.make_shadow_reader(root)
            marker = root / "install-ran.json"
            self.write_module(shadow, "install", self.marker_module(marker))

            unadmitted = self.run_reader(
                shadow, "install", *USER_SCOPE, "--agent", "claude", isolated=False
            )

            self.assertEqual(unadmitted.returncode, 3, unadmitted.stderr)
            self.assertIn("ccodex install requires its bound isolated Python 3.12.11", unadmitted.stderr)
            self.assertNotIn("Traceback", unadmitted.stderr)
            self.assertFalse(marker.exists(), "an unadmitted runtime must refuse before any module runs")
            # Positive control: with -I -B the very same module is entered.
            admitted = self.run_reader(shadow, "install", *USER_SCOPE, "--agent", "claude")
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

                completed = self.run_reader(shadow, "uninstall", *USER_SCOPE, "--agent", "claude")

                self.assertEqual(completed.returncode, expected, completed.stderr)
                self.assertIn(fragment, completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
        with tempfile.TemporaryDirectory() as temp:
            # Positive controls: an admitted exit class is forwarded verbatim and silently, so the
            # exit-4 classifications above are decisions and not a blanket rewrite of every result.
            for returned in (0, 3):
                shadow = self.make_shadow_reader(Path(temp) / f"case-{returned}")
                self.write_module(shadow, "uninstall", f"def main(argv):\n    return {returned}\n")
                forwarded = self.run_reader(shadow, "uninstall", *USER_SCOPE, "--agent", "claude")
                self.assertEqual(forwarded.returncode, returned, forwarded.stderr)
                self.assertEqual(forwarded.stderr, "")

    # ---- grammar errors ----------------------------------------------------------------------

    def test_reader_grammar_and_its_usage_lines_are_pinned_byte_for_byte(self) -> None:
        rendered = reader.usage()
        self.assertEqual(rendered.splitlines()[: len(READER_USAGE_LINES)], list(READER_USAGE_LINES))
        for arguments, expected in READER_FORMS:
            with self.subTest(arguments=arguments):
                self.assertEqual(reader.parse_command(list(arguments)), expected)
        for invalid in (
            # `inspect` IS RETIRED, so the two spellings this matrix used to admit are grammar errors
            # now. They stay here rather than being deleted, and that is the point: a retired read
            # verb must be refused by name, never quietly resolved to one of the two reads that
            # replaced it (`status` per selected plane, `doctor` for the whole box).
            ("inspect",),
            ("inspect", "--json"),
            # `--host` left the OPERATOR grammar with the same wave. It survives only as the ABI this
            # reader forwards to a module, which the dispatch test above observes at that seam, so
            # typing it is an unknown argument even on a verb whose module admits it.
            ("status", *USER_SCOPE, "--agent", "claude", "--host", "claude"),
            # A selector verb with neither selector, and a read verb with a flag it does not take.
            ("status",),
            ("doctor", "--dry-run"),
            ("doctor", "--json", "--json"),
            ("recover", "--json", "--dry-run"),
            ("recover", "--dry-run", "--dry-run"),
            *REFUSED_RECOVER_FORMS,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(reader.UsageError):
                    reader.parse_command(list(invalid))
        # The reader's own unknown-verb arm, pinned on its MESSAGE and not merely on the raise. It is
        # unreachable through `bin/ccodex` -- the dispatcher enumerates the six lifecycle verbs and
        # answers `unknown command` itself before the reader is reached -- so this is the only place
        # the reader's half of that refusal is checked, and the retired `inspect` is the token that
        # reaches it.
        with self.assertRaises(reader.UsageError) as retired:
            reader.parse_command(["inspect", "--json"])
        self.assertEqual(str(retired.exception), "unknown ccodex verb: 'inspect'")
        # Positive control for the whole matrix above: the one admitted mutating spelling parses,
        # so those refusals are the grammar's verdicts and not `parse_command` refusing everything.
        self.assertEqual(
            reader.parse_command(["recover", "--apply", PLAN_DIGEST]),
            ("recover", False, False, PLAN_DIGEST, None, None),
        )
        # A digest is not an agent and an agent is not a digest: the shared forwarded slot never lets
        # one verb's argument reach the other's module. Index access still reads that slot after the
        # 4-tuple became a six-field `Invocation`, which is why these pins survived unchanged.
        self.assertEqual(reader.parse_command(["install", *USER_SCOPE, "--agent", "claude"])[3], "claude")
        self.assertEqual(reader.parse_command(["install", *USER_SCOPE, "--agent", "codex"])[3], "codex")
        self.assertEqual(reader.parse_command(["uninstall", *USER_SCOPE, "--agent", "codex"])[3], "codex")
        with self.assertRaises(reader.UsageError):
            reader.parse_command(["install", *USER_SCOPE, "--agent", PLAN_DIGEST])
        # `status` is the selector verb that READS, so it forwards nothing: its agent reaches the
        # report rather than a module ABI, and an empty forwarded slot is what keeps the two classes
        # of selector verb distinct.
        self.assertIsNone(reader.parse_command(["status", *USER_SCOPE, "--agent", "claude"])[3])

    def test_the_committed_dispatcher_forwards_the_closed_grammar_and_writes_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for vector in MUTATING_VECTORS:
                verb = vector[0]
                with self.subTest(verb=verb, agent=vector[-1]):
                    completed = self.run_dispatcher(dispatcher, environment, *vector)
                    self.assertEqual(completed.returncode, 3, completed.stderr)
                    if verb in ABSENT_MODULES:
                        self.assertIn(
                            f"ccodex {verb} is unavailable in this distribution", completed.stderr
                        )
                        self.assertIn(str(ROOT / "scripts" / MUTATING_MODULES[verb]), completed.stderr)
                    else:
                        # The shipped module itself refuses pre-effect, in its own name -- and that
                        # name is still the RETIRED `ccodex sdlc <verb>`, deliberately: the per-verb
                        # modules belong to other waves and keep the `--host` ABI this reader
                        # forwards. The assertion states what the product emits rather than what the
                        # front door is now called, so the day a module renames itself this is what
                        # fails and names the rename. The loader's absence refusal appearing here
                        # would instead mean dispatch never reached the module.
                        self.assertIn(f"error: ccodex sdlc {verb} ", completed.stderr)
                        self.assertNotIn("is unavailable in this distribution", completed.stderr)
                    self.assertNotIn("Traceback", completed.stderr)
                    self.assertEqual(completed.stdout, "")
            # Positive control: the same dispatcher still serves a reader verb end to end. `doctor`
            # stands where `inspect` used to: it is the whole-box read that absorbed that spelling.
            control = self.run_dispatcher(dispatcher, environment, "doctor", "--json")
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertEqual(json.loads(control.stdout)["command"]["verb"], "doctor")
            self.assertFalse(query_state.exists())

    def test_the_dropped_verb_family_and_an_unknown_argument_are_grammar_errors(self) -> None:
        """The dropped family is refused ONE LAYER OUT now, and that is where this test moved with it.

        Every vector here used to be a ``ccodex sdlc <name>`` answered by the reader's own
        ``unknown ccodex sdlc verb`` arm. The dispatcher enumerates the six lifecycle verbs itself
        now, so ``ccodex profiles`` never reaches the reader at all and that arm is unreachable from
        this surface -- it is asserted in-process instead, on ``inspect``, in the grammar test above.
        The claim is unchanged: a dropped verb family is exit 2 and names the surface it is not on,
        never a silent no-op. The argument-level half that still does reach the reader is asserted
        underneath, so both parsers stay covered by this one test.
        """
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for vector, fragment in (
                (("profiles",), "error: unknown command profiles"),
                (("profiles", "list"), "error: unknown command profiles"),
                (("profile",), "error: unknown command profile"),
                (("refresh",), "error: unknown command refresh"),
                (("follow",), "error: unknown command follow"),
            ):
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("usage: ccodex <command>", completed.stderr)
                    self.assertIn(fragment, completed.stderr)
            # A bare invocation is the dispatcher's own usage refusal, not a default verb.
            bare = self.run_dispatcher(dispatcher, environment)
            self.assertEqual(bare.returncode, 2, bare.stderr)
            self.assertEqual(bare.stdout, "")
            self.assertIn("usage: ccodex <command>", bare.stderr)
            # The half that still reaches the READER: a dropped flag on a verb that does exist.
            unknown_argument = self.run_dispatcher(
                dispatcher, environment, "install", "--profile", "claude"
            )
            self.assertEqual(unknown_argument.returncode, 2, unknown_argument.stderr)
            self.assertIn("unknown ccodex install argument: '--profile'", unknown_argument.stderr)
            # The reader's usage block, read off a real refusal rather than off `--help`: `ccodex
            # --help` is the DISPATCHER's document now, and the reader's own grammar is published
            # only beside an exit-2 error. A vector whose refusal echoes no caller token is chosen on
            # purpose, so the negative assertions below cannot match text the test itself supplied.
            usage_block = self.run_dispatcher(dispatcher, environment, "install")
            self.assertEqual(usage_block.returncode, 2, usage_block.stderr)
            for named in (
                "usage: ccodex install   --scope user|project --agent claude|codex",
                "       ccodex update    --scope user|project --agent claude|codex",
                "       ccodex uninstall --scope user|project --agent claude|codex",
            ):
                self.assertIn(named, usage_block.stderr)
            # The dropped vocabulary, `--host` included: the operator grammar publishes none of it,
            # even though the vector this reader forwards still spells the flag.
            for dropped in ("profile", "refresh", "inspect", "--host"):
                self.assertNotIn(dropped, usage_block.stderr)
            # Positive control for those four absences: the same document is what was searched, and
            # it really does carry the neighbouring verb.
            self.assertIn("update", usage_block.stderr)
            self.assertFalse(query_state.exists())

    def test_dispatcher_help_names_the_lifecycle_verb_table_and_no_dropped_verb_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))

            completed = self.run_dispatcher(dispatcher, environment, "--help")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            # The six verbs at the TOP level, spelled with the selectors the four that take them
            # require. `sdlc <inspect|status|doctor>` is gone from this document entirely.
            for named in (
                "install --scope <user|project> --agent <claude|codex> [--project PATH]",
                "status --scope <user|project> --agent <claude|codex> [--project PATH] [--json]",
                "update --scope <user|project> --agent <claude|codex> [--project PATH]",
                "uninstall --scope <user|project> --agent <claude|codex> [--project PATH] [--dry-run]",
                "doctor [--json]",
                "recover --dry-run [--json]",
                "recover --apply <plan-sha256>",
            ):
                self.assertIn(named, completed.stdout)
            # Positive control for the negative assertions below: the retired namespaces are NAMED
            # as retired in this same document, so their absence from the verb table is a migration
            # rather than a deletion an operator has to discover by typing the old spelling.
            self.assertIn(
                "`ccodex bundle <verb>` and `ccodex sdlc <verb>` are refused at exit 2",
                completed.stdout,
            )
            self.assertNotIn("sdlc install --host", completed.stdout)
            self.assertNotIn("sdlc <inspect|status|doctor>", completed.stdout)
            self.assertNotIn("profile", completed.stdout)
            self.assertNotIn("refresh", completed.stdout)
            self.assertFalse(query_state.exists())

    def test_every_mutating_verb_requires_both_selectors_and_names_which_half_was_wrong(self) -> None:
        """All three verbs, and BOTH selectors: a bare mutating verb would have to pick a plane.

        Before the codex arm, `update` and `uninstall` took no arguments and each module named its own
        single plane. With two planes live that omission is the cross-agent defect at the grammar layer,
        so the agent selector is required everywhere. Ratified decision 1 added the scope selector for
        the same reason one level out: a run that guessed its root would touch a repository nobody
        named. Neither has a default and neither has a wildcard, and every refusal below is proven per
        verb because a matrix that only ever spelled `install` would pass with `update` broken.
        """
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            per_verb = []
            for verb in ("install", "update", "uninstall"):
                per_verb.extend(
                    (
                        ((verb,), f"ccodex {verb} requires an explicit --scope user|project; there is no default scope"),
                        # The scope is checked FIRST, so an agent-only invocation is still refused for
                        # the selector it is missing rather than for the one it supplied.
                        ((verb, "--agent", "claude"), f"ccodex {verb} requires an explicit --scope user|project"),
                        ((verb, "--scope"), f"ccodex {verb} --scope was supplied without a value"),
                        ((verb, "--scope", ""), f"unsupported ccodex {verb} scope: ''"),
                        ((verb, "--scope", "all"), f"unsupported ccodex {verb} scope: 'all'"),
                        ((verb, "--scope=user", "--agent", "claude"), f"ccodex {verb} spells --scope as two arguments"),
                        ((verb, *USER_SCOPE), f"ccodex {verb} requires an explicit --agent claude|codex; there is no default agent"),
                        ((verb, *USER_SCOPE, "--agent"), f"ccodex {verb} --agent was supplied without a value"),
                        ((verb, *USER_SCOPE, "--agent", ""), f"unsupported ccodex {verb} agent: ''"),
                        ((verb, *USER_SCOPE, "--agent", "all"), f"unsupported ccodex {verb} agent: 'all'"),
                        ((verb, *USER_SCOPE, "--agent", "*"), f"unsupported ccodex {verb} agent: '*'"),
                        ((verb, *USER_SCOPE, "--agent", "gemini"), f"unsupported ccodex {verb} agent: 'gemini'"),
                        ((verb, *USER_SCOPE, "--agent=claude"), f"ccodex {verb} spells --agent as two arguments"),
                        ((verb, *USER_SCOPE, "--agent", "claude", "--json"), UNADMITTED_JSON_REFUSAL[verb]),
                        ((verb, *USER_SCOPE, "--agent", "codex", "extra"), f"unknown ccodex {verb} argument: 'extra'"),
                        ((verb, "--profile", "claude"), f"unknown ccodex {verb} argument: '--profile'"),
                        # One selector, twice: a repeated flag is refused rather than resolved to
                        # whichever copy came last, which is how `--scope user --scope project` would
                        # otherwise reach a plane the operator also asked not to.
                        ((verb, *USER_SCOPE, "--scope", "project", "--agent", "claude"), f"ccodex {verb} accepts one --scope: '--scope'"),
                        # The module ABI is not an operator flag on any of the three.
                        ((verb, *USER_SCOPE, "--agent", "claude", "--host", "claude"), f"unknown ccodex {verb} argument: '--host'"),
                    )
                )
            for vector, fragment in per_verb:
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    # ONE usage document serves the whole verb table, so every verb's grammar error
                    # reprints the same first line; there is no per-verb usage block to assert on.
                    self.assertIn("usage: ccodex install", completed.stderr)
                    self.assertIn(fragment, completed.stderr)
            # Positive control, on BOTH planes: an admitted spelling is NOT a grammar error. Each
            # reaches its shipped module and refuses there pre-effect, which is what makes the exit-2s
            # above attributable to the spelling rather than to the plane being unreachable.
            for verb in ("install", "update", "uninstall"):
                for agent in ("claude", "codex"):
                    with self.subTest(admitted=(verb, agent)):
                        admitted = self.run_dispatcher(
                            dispatcher, environment, verb, *USER_SCOPE, "--agent", agent
                        )
                        self.assertEqual(admitted.returncode, 3, admitted.stderr)
                        self.assertIn(f"error: ccodex sdlc {verb}", admitted.stderr)
                        self.assertNotIn("usage: ccodex install", admitted.stderr)
            self.assertFalse(query_state.exists())

    def test_a_control_character_in_a_refused_argument_cannot_forge_an_output_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, _query_state = self.make_dispatcher(Path(temp))
            forged = "claude\nerror: ccodex install completed"

            # The scope is supplied so the run reaches the AGENT check: a scopeless invocation is
            # refused for its missing selector and never echoes the forged token at all, which would
            # make this case pass without exercising any escaping.
            completed = self.run_dispatcher(
                dispatcher, environment, "install", *USER_SCOPE, "--agent", forged
            )

            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertIn("\\n", completed.stderr)
            # The forged text survives only INSIDE one escaped token. What must not happen is a
            # line of this command's own output that the caller wrote: no rendered line may begin
            # with the injected sentence, and the raw newline must never reach the stream.
            self.assertNotIn(forged, completed.stderr)
            for line in completed.stderr.splitlines():
                self.assertFalse(
                    line.startswith("error: ccodex install completed"),
                    f"a caller argument forged an output line: {line!r}",
                )
            # Positive control: an ordinary value is still rendered plainly, so the escaping above
            # is escaping and not a blanket refusal to echo the caller's token.
            plain = self.run_dispatcher(
                dispatcher, environment, "install", *USER_SCOPE, "--agent", "gemini"
            )
            self.assertIn("unsupported ccodex install agent: 'gemini'", plain.stderr)
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
        # The two closed verb sets the front-door wave decided, pinned so a fourth spelling of a read
        # cannot come back and a selector verb cannot lose its selectors: `inspect` is gone from the
        # reader vocabulary, and `status` is the selector verb that reads one named plane.
        self.assertEqual(reader.READER_VERBS, ("status", "doctor", "recover"))
        self.assertEqual(reader.SELECTOR_VERBS, ("install", "status", "update", "uninstall"))
        self.assertEqual(reader.LIFECYCLE_AGENTS, ("claude", "codex"))
        # The three re-expressions of one agent vocabulary, pinned against each other: the reader's
        # grammar tuple, the closed host-plane table it is a copy of, and the receipt family's own
        # `HOSTS`, which is what a sealed body's `scope.agent` is checked against. Widening one and not
        # the others is what this equality exists to fail on.
        planes = load_module("lifecycle_grammar_host_planes", ROOT / "scripts" / "ccodex_sdlc_host_planes.py")
        receipts = load_module(
            "lifecycle_grammar_receipts", ROOT / "scripts" / "distribution_activation_receipt.py"
        )
        self.assertEqual(reader.LIFECYCLE_AGENTS, planes.AGENTS)
        self.assertEqual(tuple(sorted(receipts.HOSTS)), planes.AGENTS)
        self.assertEqual(reader.LIFECYCLE_AGENT_CHOICE, "claude|codex")
        self.assertEqual(reader.LIFECYCLE_SCOPES, ("user", "project"))
        self.assertEqual(reader.LIFECYCLE_SCOPE_CHOICE, "user|project")
        # ONE FACT, TWO SPELLINGS, both named here so neither can drift alone: the operator types
        # `--agent`, and the vector `main` builds for a per-verb module is `--host`. The dispatch test
        # observes that translation at its single seam; this pins the two constants it translates
        # between, so renaming either without the other fails in the vocabulary test rather than
        # silently forwarding an ABI no module admits.
        self.assertEqual(reader.AGENT_FLAG, "--agent")
        self.assertEqual(reader.FORWARDED_AGENT_FLAG, "--host")


if __name__ == "__main__":
    unittest.main()
