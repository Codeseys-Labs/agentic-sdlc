"""The front-door train's TERMINAL CHECK: `doctor --json` names every state store the tree has.

gh #8 acceptance 9 is two clauses — "`ccodex doctor --json` names every remaining state store, and
the number of stores it names equals the number the tree actually has" — and the plan
(`docs/plans/2026-08-25-front-door-unification.md` §2.3, audit finding B4) records it as decidable
only at the END of the wave train, because doctor's store roster is co-owned by W3a, D3+D4, and W5.
It is decidable now, and it was NOT satisfied before this wave: measured 2026-08-26 on a fixture host
carrying all six stores, `doctor --json` named THREE of them — `bundle.state_paths` for the ownership
ledger, plus one `foreign-state` finding each for the two leftovers — while the receipt-and-pointer
plane, the statusline receipt, and the hook receipts were named nowhere in the report.

The check has to answer "how many stores does the tree actually have" without asking the reader,
or it would be the reader grading its own homework. `derived_store_names` answers it from the
OWNING MODULES' OWN SOURCE: every string literal shaped like a state-store directory that appears
as a `pathlib` join operand or inside a `*_SEGMENTS`/`*_STORE`/`*_DIRECTORY`/`*_PLANE` constant,
across every module in `scripts/`. So a plane that adds a seventh store fails this file until the
reader's roster names it, which is the property the acceptance actually wants.

Two limits of that derivation, stated rather than hidden:

  * It reads `scripts/`, which is where every store this distribution writes is derived. A store
    introduced from `skills/` or `bin/` would be invisible here; nothing writes one today, and the
    roster comment in the reader is the place a new plane is told to look.
  * It fails CLOSED on a false positive: a path segment literally shaped like `agentic-sdlc-<word>`
    that is not a store would also demand a roster row. Two such literals exist already and are
    harmless because they collapse onto a name that IS a store — `skills/agentic-sdlc/...` in
    `install_skill_bundle.GIT_DETECTOR_RELATIVE` and `instruction_generator._CANONICAL` both spell
    the flagship skill's directory, which is the same token as the receipts plane.

Isolation is the seed-8dca doctrine and is asserted, not assumed: every dispatcher run below gets
the seam harness's allowlist environment with its own home and state root, and the tests that read
an empty host assert the state root is still absent afterwards.
"""

from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).parents[1]
DISPATCHER_SCRIPT = ROOT / "bin" / "ccodex"
READER_SCRIPT = ROOT / "scripts" / "ccodex_sdlc.py"
SEAM_HARNESS = Path(__file__).parent / "seam_harness.py"

seam_spec = importlib.util.spec_from_file_location("state_stores_seam_harness", SEAM_HARNESS)
assert seam_spec and seam_spec.loader
seam = importlib.util.module_from_spec(seam_spec)
sys.modules["state_stores_seam_harness"] = seam
seam_spec.loader.exec_module(seam)

reader_spec = importlib.util.spec_from_file_location("state_stores_reader", READER_SCRIPT)
assert reader_spec and reader_spec.loader
reader = importlib.util.module_from_spec(reader_spec)
sys.modules["state_stores_reader"] = reader
reader_spec.loader.exec_module(reader)

#: A state-store directory name: this distribution's own prefix, optionally followed by hyphenated
#: lowercase words. Written as an explicit class rather than `\w`, for the reason the reader gives
#: about `\d`: a name spelled with a non-ASCII digit would read as the same identity while comparing
#: unequal to it.
STORE_NAME_SHAPE = re.compile(r"^agentic-sdlc(?:-[a-z0-9]+(?:-[a-z0-9]+)*)?$")
#: The constant names whose tuple/string members are path segments rather than prose.
SEGMENT_CONSTANT = re.compile(r"SEGMENTS|STORE|DIRECTORY|PLANE")


def derived_store_names(scripts: Path) -> dict[str, list[str]]:
    """Every state-store directory name the modules under `scripts/` spell, with where each is spelled.

    Syntax, not text: a bare `grep` for the prefix also matches seed ids inside docstrings
    (`agentic-sdlc-ba1a`), the published statusline command's basename, and a temporary-directory
    prefix, none of which are stores. Requiring the literal to be a `/` operand or a member of a
    path-segment constant is what separates a path from a mention.
    """
    found: dict[str, list[str]] = {}

    def record(value: str, module: Path, line: int, why: str) -> None:
        if STORE_NAME_SHAPE.match(value):
            found.setdefault(value, []).append(f"{module.name}:{line} ({why})")

    for module in sorted(scripts.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                for side in (node.left, node.right):
                    if isinstance(side, ast.Constant) and isinstance(side.value, str):
                        record(side.value, module, side.lineno, "path-join operand")
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if not any(SEGMENT_CONSTANT.search(name) for name in targets):
                    continue
                for member in ast.walk(node.value):
                    if isinstance(member, ast.Constant) and isinstance(member.value, str):
                        record(member.value, module, member.lineno, f"constant {targets}")
    return found


class StateStoreRosterTests(unittest.TestCase):
    """The roster itself: complete, closed, and one spelling of each fact."""

    def test_the_roster_names_every_store_the_tree_spells(self) -> None:
        """THE TERMINAL CHECK. A store the modules write and the roster omits fails here.

        Equality in both directions, not containment: a roster row naming a directory no module ever
        writes is also a defect — it would inflate the count the acceptance asks about with a store
        that does not exist.
        """
        derived = derived_store_names(ROOT / "scripts")
        roster = {directory for directory, _component, _kind, _remedy in reader.STATE_STORES}

        self.assertEqual(
            roster,
            set(derived),
            "the reader's STATE_STORES roster and the stores scripts/ actually writes disagree; "
            f"derived at {json.dumps(derived, indent=2, sort_keys=True)}",
        )
        # The derivation must be doing real work, not returning an empty set that trivially matches
        # an empty roster. Six is what this tree has; the assertion is on the derived side, so a
        # scanner that stopped finding anything fails here rather than passing as agreement.
        self.assertEqual(6, len(derived), sorted(derived))

    def test_the_scanner_sees_a_seventh_store_planted_in_a_module(self) -> None:
        """POSITIVE CONTROL for the derivation, on a copy of a real module, in a temp tree.

        Without this, `test_the_roster_names_every_store_the_tree_spells` could pass forever on a
        scanner that only ever found the six names hard-coded into its own regex.
        """
        with tempfile.TemporaryDirectory() as temp:
            scripts = Path(temp) / "scripts"
            scripts.mkdir()
            (scripts / "planted_plane.py").write_text(
                "from pathlib import Path\n"
                "def receipts_root(state_root: Path) -> Path:\n"
                '    return state_root / "agentic-sdlc-planted-plane"\n',
                encoding="utf-8",
            )
            derived = derived_store_names(scripts)

        self.assertEqual({"agentic-sdlc-planted-plane"}, set(derived))
        self.assertNotIn("agentic-sdlc-planted-plane", {d for d, _c, _k, _r in reader.STATE_STORES})

    def test_the_scanner_ignores_a_mention_that_is_not_a_path(self) -> None:
        """NEGATIVE CONTROL, and the reason the scanner is an AST walk rather than a grep.

        A seed id in a docstring, the statusline command's basename in a plain assignment, and a
        temporary-directory prefix are all `agentic-sdlc`-shaped text that no operator has a store
        for. A text scan would demand roster rows for all three.
        """
        with tempfile.TemporaryDirectory() as temp:
            scripts = Path(temp) / "scripts"
            scripts.mkdir()
            (scripts / "mentions.py").write_text(
                '"""Fixed under seed agentic-sdlc-ba1a, see also agentic-sdlc-cb77."""\n'
                'COMMAND_NAME = "agentic-sdlc-statusline"\n'
                'TEMPORARY_PREFIX = "agentic-sdlc-installer-"\n',
                encoding="utf-8",
            )
            self.assertEqual({}, derived_store_names(scripts))

    def test_the_retired_half_is_derived_from_the_one_roster(self) -> None:
        """One fact, one spelling: a store cannot be live in the roster and retired in the findings.

        `RETIRED_STORES` is a filter over `STATE_STORES`, so this asserts the projection rather than
        a second hand-written list — and it asserts the shape the finding loop relies on, that every
        retired row really carries a remedy.
        """
        expected = tuple(
            (directory, component, remedy)
            for directory, component, kind, remedy in reader.STATE_STORES
            if kind == "retired" and remedy is not None
        )
        self.assertEqual(expected, reader.RETIRED_STORES)
        self.assertEqual(2, len(reader.RETIRED_STORES), reader.RETIRED_STORES)
        for directory, component, remedy in reader.RETIRED_STORES:
            with self.subTest(store=directory):
                self.assertTrue(remedy)
                self.assertLessEqual(len(remedy), reader.MAX_FINDING_MESSAGE_CHARS)
                self.assertIn(component, {"operator-tools", "claude-workflows"})

    def test_every_roster_row_carries_a_closed_kind_and_a_unique_component(self) -> None:
        kinds = {kind for _d, _c, kind, _r in reader.STATE_STORES}
        components = [component for _d, component, _k, _r in reader.STATE_STORES]
        directories = [directory for directory, _c, _k, _r in reader.STATE_STORES]

        self.assertEqual({"live", "retired"}, kinds)
        self.assertEqual(len(components), len(set(components)), components)
        self.assertEqual(len(directories), len(set(directories)), directories)
        for directory, component, kind, remedy in reader.STATE_STORES:
            with self.subTest(store=directory):
                self.assertRegex(directory, STORE_NAME_SHAPE)
                # A live store present on a healthy host is a fact, never something to act on, so it
                # must not carry a remedy; only a deleted plane's leftover does.
                self.assertEqual(kind == "retired", remedy is not None)


class StateStoreReportTests(unittest.TestCase):
    """The report half, driven through the committed dispatcher as an operator drives it."""

    def make_dispatcher(self, root: Path) -> tuple[dict[str, str], Path]:
        state = root / "query-state"
        environment = seam.stub_dispatcher_environment(
            root, home=root / "query-home", state=state
        )
        return environment, state

    def run_dispatcher(self, environment: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(DISPATCHER_SCRIPT), *arguments],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_doctor_json_names_every_store_and_the_count_equals_the_rosters(self) -> None:
        """gh #8 acceptance 9, both clauses, on a host with nothing installed.

        The empty host is the harder case for the acceptance, not the easier one: a roster that only
        reported stores it found would answer "how many does the tree have" with zero here, and the
        count would be a property of the operator's machine instead of the distribution.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment, state = self.make_dispatcher(root)

            machine = self.run_dispatcher(environment, "doctor", "--json")

            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            rows = report["state_stores"]
            self.assertEqual(len(rows), len(reader.STATE_STORES))
            self.assertEqual(
                {row["path"] for row in rows},
                {str(state / directory) for directory, _c, _k, _r in reader.STATE_STORES},
            )
            self.assertEqual({row["state"] for row in rows}, {"absent"})
            # READ-ONLY IS MEASURED: naming a store must not create it, and the state root is the
            # one directory the seam harness deliberately leaves uncreated so this can be asserted.
            self.assertFalse(state.exists(), sorted(p.name for p in root.iterdir()))

    def test_a_populated_host_reads_present_for_exactly_the_stores_it_has(self) -> None:
        """The verdict axis, with both directions live in one run.

        Three planted, three absent — so a projection that hard-coded either verdict fails, and the
        two retired plantings also produce the `foreign-state` findings whose remedies are the other
        half of naming a leftover.
        """
        planted = ("agentic-sdlc-installer", "agentic-sdlc-claude-hooks", "agentic-sdlc-operator-tools")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment, state = self.make_dispatcher(root)
            for directory in planted:
                (state / directory).mkdir(parents=True)

            machine = self.run_dispatcher(environment, "doctor", "--json")

            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            verdicts = {Path(row["path"]).name: row["state"] for row in report["state_stores"]}
            self.assertEqual(len(verdicts), len(reader.STATE_STORES))
            for directory, _component, _kind, _remedy in reader.STATE_STORES:
                with self.subTest(store=directory):
                    self.assertEqual(
                        "present" if directory in planted else "absent", verdicts[directory]
                    )
            # The one planted leftover is still a finding as well as a roster row: the two dimensions
            # are separate, and a roster that swallowed the remedy would drop the operator's recipe.
            self.assertEqual(
                ["operator-tools"],
                [f["component"] for f in report["findings"] if f["code"] == "foreign-state"],
            )

    def test_the_text_rendering_names_the_same_stores_as_the_json(self) -> None:
        """Renderer parity on this field: an operator who never passes `--json` gets the same count."""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment, state = self.make_dispatcher(root)
            (state / "agentic-sdlc").mkdir(parents=True)

            machine = self.run_dispatcher(environment, "doctor", "--json")
            human = self.run_dispatcher(environment, "doctor")

            self.assertEqual(machine.returncode, 0, machine.stderr)
            self.assertEqual(human.returncode, 0, human.stderr)
            report = json.loads(machine.stdout)
            lines = [line for line in human.stdout.splitlines() if line.startswith("state store [")]
            self.assertEqual(len(lines), len(report["state_stores"]))
            for row in report["state_stores"]:
                expected = (
                    f"state store [{row['component']}/{row['kind']}]: {row['state']} ({row['path']})"
                )
                self.assertIn(expected, lines)

    def test_every_read_verb_carries_the_roster_not_doctor_alone(self) -> None:
        """The roster is a whole-box fact, so it is unconditional rather than one verb's field.

        A field present for `doctor` and absent for `status` would be a representable illegal state
        in the exact-key report shape, and the two verbs render ONE semantic record.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment, _state = self.make_dispatcher(root)

            for verb, selectors in (
                ("doctor", ()),
                ("status", ("--scope", "user", "--agent", "claude")),
                ("recover", ("--dry-run",)),
            ):
                with self.subTest(verb=verb):
                    machine = self.run_dispatcher(environment, verb, *selectors, "--json")

                    self.assertEqual(machine.returncode, 0, machine.stderr)
                    report = json.loads(machine.stdout)
                    self.assertEqual(len(report["state_stores"]), len(reader.STATE_STORES))

    def test_a_refused_runtime_still_names_the_roster(self) -> None:
        """The refusal path loads no ownership adapter, and the roster needs none.

        Dropping the field on a refusal would make the acceptance's count conditional on the exit
        class; naming it keeps the one question the operator has on a broken host answerable.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment, state = self.make_dispatcher(root)
            # The dispatcher's own route always builds `-I -B`, so the refusal is provoked where it
            # really lives: the reader run as a plain interpreter, against the same isolated plane.
            refused = subprocess.run(
                [sys.executable, str(READER_SCRIPT), "doctor", "--json"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            report = json.loads(refused.stdout)
            self.assertEqual(report["runtime"]["state"], "refused")
            self.assertEqual(report["overall"]["exit_class"], "safe-refusal")
            self.assertEqual(len(report["state_stores"]), len(reader.STATE_STORES))
            self.assertFalse(state.exists())


class StateStoreValidatorTests(unittest.TestCase):
    """The report validator refuses a roster that under-reports, which is what makes the count binding."""

    def setUp(self) -> None:
        self.policy = reader.load_policy(ROOT)
        self.fields = self.policy["field_vocabularies"]
        self.vocab = self.policy["vocabularies"]
        self.rows = [
            {
                "component": component,
                "kind": kind,
                "path": f"/state/{directory}",
                "state": "absent",
            }
            for directory, component, kind, _remedy in reader.STATE_STORES
        ]
        self.rows.sort(key=lambda row: (row["path"], row["component"]))

    def test_the_clean_roster_validates(self) -> None:
        """The positive control every refusal below needs."""
        reader.validate_state_stores(self.rows, self.fields, self.vocab)

    def test_a_dropped_row_is_refused(self) -> None:
        """The acceptance's own failure mode: a report that names fewer stores than the tree has."""
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_state_stores(self.rows[1:], self.fields, self.vocab)

    def test_a_renamed_component_is_refused(self) -> None:
        mutated = [dict(row) for row in self.rows]
        mutated[0]["component"] = "drift"
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_state_stores(mutated, self.fields, self.vocab)

    def test_an_extra_key_is_refused(self) -> None:
        mutated = [dict(row) for row in self.rows]
        mutated[0]["remedy"] = "delete it"
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_state_stores(mutated, self.fields, self.vocab)

    def test_an_unknown_kind_or_verdict_is_refused(self) -> None:
        for field, value in (("kind", "dormant"), ("state", "healthy")):
            with self.subTest(field=field):
                mutated = [dict(row) for row in self.rows]
                mutated[0][field] = value
                with self.assertRaises(reader.ReportInvariantError):
                    reader.validate_state_stores(mutated, self.fields, self.vocab)

    def test_an_unsorted_or_repeated_roster_is_refused(self) -> None:
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_state_stores(list(reversed(self.rows)), self.fields, self.vocab)
        with self.assertRaises(reader.ReportInvariantError):
            reader.validate_state_stores([self.rows[0], *self.rows], self.fields, self.vocab)


class StateStoreVerdictTests(unittest.TestCase):
    """One `lstat`, three answers, and the reason a leftover finding needs `present` specifically."""

    def test_present_absent_and_a_link_that_is_not_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real = root / "real"
            real.mkdir()
            dangling = root / "dangling"
            dangling.symlink_to(root / "nowhere")

            self.assertEqual("present", reader.state_store_verdict(real))
            self.assertEqual("absent", reader.state_store_verdict(root / "missing"))
            # A store replaced by a link is still a store this reader reports; following it to decide
            # would be following a link out of the state root.
            self.assertEqual("present", reader.state_store_verdict(dangling))

    def test_an_unsearchable_parent_reads_unreadable_and_produces_no_remedy(self) -> None:
        """`unreadable` is not `absent`, and it is not a leftover finding either.

        An `lstat` that fails for anything but `ENOENT` means this reader never established that the
        directory is there, so telling the operator to delete it would be advice about a store nobody
        observed. The roster still records what happened.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            closed = root / "closed"
            closed.mkdir()
            (closed / "agentic-sdlc-operator-tools").mkdir()
            closed.chmod(0o000)
            try:
                verdict = reader.state_store_verdict(closed / "agentic-sdlc-operator-tools")
            finally:
                closed.chmod(0o700)

            if verdict == "present":
                self.skipTest("this filesystem or uid ignores directory permissions")
            self.assertEqual("unreadable", verdict)


if __name__ == "__main__":
    unittest.main()
