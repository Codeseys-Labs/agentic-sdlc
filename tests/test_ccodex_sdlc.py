from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
#: The real reader, driven directly under -I -B (gh #10 phase 4 deleted the rendered
#: assets/launchers/ccodex.in template and the install_operator_tools.py plane that rendered it).
#: There is no install step any more: the committed bin/ccodex resolves the "sdlc" route's pinned
#: interpreter at run time through `mise -C <root> exec`, which requires this checkout's own
#: mise.toml to be trusted under the REAL operator HOME -- a fact an isolated test HOME can never
#: carry without a persistent trust mutation. Driving scripts/ccodex_sdlc.py directly, exactly as
#: bin/ccodex's own run_sdlc_python resolves and execs it, sidesteps that boundary; the boundary
#: itself is proven elsewhere (tests/test_bin_ccodex.py, tests/test_ccodex_seam.py).
READER_SCRIPT = ROOT / "scripts" / "ccodex_sdlc.py"
DISPATCHER_SCRIPT = ROOT / "bin" / "ccodex"
#: The reader loaded IN-PROCESS, for the unit-level `retired_store_findings` coverage below. Every
#: subprocess-driven test above still exercises the real file at its own real physical path; this
#: import is a second, in-process view of the identical bytes for a function this file's other
#: tests have no reason to fork a process to reach.
reader_spec = importlib.util.spec_from_file_location("ccodex_sdlc_reader", READER_SCRIPT)
assert reader_spec and reader_spec.loader
reader = importlib.util.module_from_spec(reader_spec)
sys.modules[reader_spec.name] = reader
reader_spec.loader.exec_module(reader)

BUNDLE_SCRIPT = ROOT / "scripts" / "install_skill_bundle.py"
bundle_spec = importlib.util.spec_from_file_location("ccodex_sdlc_bundle", BUNDLE_SCRIPT)
assert bundle_spec and bundle_spec.loader
bundle = importlib.util.module_from_spec(bundle_spec)
sys.modules[bundle_spec.name] = bundle
bundle_spec.loader.exec_module(bundle)

VALIDATOR_SCRIPT = ROOT / "scripts" / "validate_bundle.py"
validator_spec = importlib.util.spec_from_file_location("ccodex_sdlc_validator", VALIDATOR_SCRIPT)
assert validator_spec and validator_spec.loader
validator = importlib.util.module_from_spec(validator_spec)
sys.modules[validator_spec.name] = validator
validator_spec.loader.exec_module(validator)


@unittest.skipIf(
    os.name == "nt",
    "the ccodex sdlc lifecycle writes through the POSIX-only durable-write plane "
    "(os.open O_DIRECTORY fsync barriers) behind a bash dispatcher; native Windows fails "
    "closed by name at the CLI",
)
class CcodexSdlcTests(unittest.TestCase):
    def make_dispatcher(self, root: Path) -> tuple[Path, dict[str, str], Path]:
        """An isolated per-test query plane for the ``ccodex sdlc`` reader, no install step.

        See the module-level note on ``READER_SCRIPT``/``DISPATCHER_SCRIPT``: ``run_dispatcher``
        drives the reader directly under ``-I -B`` for the "sdlc"-prefixed vectors this file
        exercises, so no synthetic ``ocx``/``jq``/``uv``/interpreter binding is rendered here.
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

        A leading ``sdlc`` is this suite's own subject and is driven directly against the real
        reader under ``-I -B``; the toolchain-resolution boundary above it is proven elsewhere
        (``tests/test_bin_ccodex.py``, ``tests/test_ccodex_seam.py``), not duplicated here.
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

    def bundle_state_path(self, environment: dict[str, str]) -> Path:
        return Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc-installer" / "state.json"

    def valid_bundle_record(
        self, root: Path, environment: dict[str, str], name: str, *, home: Path | None = None
    ) -> tuple[Path, dict[str, object]]:
        configured_home = home or Path(environment["HOME"])
        config = bundle.Config(
            ROOT,
            configured_home,
            Path(environment["CODEX_HOME"]),
            "copy",
            True,
            "all",
            Path(environment["XDG_STATE_HOME"]),
        )
        source = root / "bundle-source" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: fixture\n---\n")
        entry = bundle.Entry("claude", "skill", name, source)
        destination = bundle.destination_for(entry, config)
        destination.parent.mkdir(parents=True)
        destination.mkdir()
        (destination / "SKILL.md").write_text("---\nname: fixture\n---\n")
        record = bundle.entry_record(entry, "copy", installed_digest=bundle.digest(destination))
        shutil.rmtree(destination)
        return destination, record

    def valid_install_transition(self, destination: Path, record: dict[str, object]) -> dict[str, object]:
        return bundle.pending_slot("install", str(destination), None, record)

    def foreign_bundle_record(
        self, root: Path, environment: dict[str, str], name: str
    ) -> tuple[Path, dict[str, object]]:
        """A recorded entry whose live bytes drifted from the digest this lifecycle published.

        Built on ``valid_bundle_record``'s own construction so the destination is a real,
        config-derived path, but the destination is left ON DISK with DIFFERENT content instead
        of being removed: ``entry_matches_record`` recomputes the live digest, which no longer
        equals the recorded one, so the projection's entry state is "foreign".
        """
        destination, record = self.valid_bundle_record(root, environment, name)
        destination.mkdir(parents=True)
        (destination / "SKILL.md").write_text("---\nname: replaced-after-recording\n---\n")
        return destination, record

    def test_inspect_json_is_a_read_only_checkout_development_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))

            completed = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["schema_version"], "ccodex-sdlc-read-report/v1")
            self.assertEqual(report["command"]["verb"], "inspect")
            self.assertEqual(report["checkout"]["plane"], "checkout-development")
            self.assertEqual(report["checkout"]["version"], "0.7.5")
            self.assertIsNone(report["checkout"]["public_channel"])
            self.assertEqual(report["checkout"]["certification_claim"], "none")
            self.assertTrue(report["runtime"]["isolated"])
            self.assertEqual(report["runtime"]["state"], "admitted")
            self.assertFalse(query_state.exists())

    def test_every_read_only_verb_reports_exactly_one_bundle_state_path(self) -> None:
        """`bundle.state_paths` carries ONE path, and the report still validates carrying it.

        The retired home-relative mirror was the only thing that could put a second entry in this
        list, and `field_vocabularies.bundle` in `policy/ccodex-sdlc-read-report.v1.json` still
        declares `state_paths`, so the field survives its second value. A report that fails
        `validate_report` never reaches stdout, which is why exit 0 plus parseable JSON is the
        validation assertion here.

        gh #10 phase 4 deleted the operator-tools plane and its `operator_tools` top-level report
        field with it: `report_top_level_fields` is now exactly `bundle`'s neighbours (see
        `test_validator_pins_both_ccodex_report_policies_by_digest` for the closed list), and
        `_exact_keys` in `validate_report` refuses ANY extra key -- so the absence asserted below
        is enforced structurally, not merely by this one test happening not to look for it.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            expected = str(self.bundle_state_path(environment))
            for verb in ("status", "doctor", "inspect"):
                with self.subTest(verb=verb):
                    machine = self.run_dispatcher(dispatcher, environment, "sdlc", verb, "--json")

                    self.assertEqual(machine.returncode, 0, machine.stderr)
                    report = json.loads(machine.stdout)
                    self.assertEqual(report["bundle"]["state_paths"], [expected])
                    self.assertNotIn("operator_tools", report)
                    # Positive control: the same membership test DOES catch a field that is really
                    # there, so the absence above is a fact about this report and not a check that
                    # would pass over any key at all.
                    self.assertIn("bundle", report)

    def test_all_read_only_verbs_and_renderer_parity_share_one_semantic_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            for verb, suffix in (("inspect", ()), ("status", ()), ("doctor", ()), ("recover", ("--dry-run",))):
                with self.subTest(verb=verb):
                    human = self.run_dispatcher(dispatcher, environment, "sdlc", verb, *suffix)
                    machine = self.run_dispatcher(dispatcher, environment, "sdlc", verb, *suffix, "--json")

                    self.assertEqual(human.returncode, 0, human.stderr)
                    self.assertEqual(machine.returncode, 0, machine.stderr)
                    report = json.loads(machine.stdout)
                    self.assertEqual(report["command"]["verb"], verb)
                    self.assertEqual(report["command"]["dry_run"], verb == "recover")
                    self.assertIn(
                        f"ccodex sdlc {verb}: {report['overall']['state']}",
                        human.stdout,
                    )
                    self.assertIn(f"recovery: {report['recovery']['state']} (no effects)", human.stdout)
                    for finding in report["findings"]:
                        self.assertIn(finding["message"], human.stdout)
                    for proposal in report["recovery"]["proposals"]:
                        self.assertIn(proposal["path"], human.stdout)
            self.assertFalse(query_state.exists())

    def test_pending_recovery_blocker_has_human_json_parity_without_state_mutation(self) -> None:
        """Re-anchored onto the bundle plane (gh #10 phase 4 deleted the operator-tools store).

        The subject -- human/JSON parity plus zero mutation around a blocked pending recovery --
        survives unchanged; only the substrate that can still carry a pending transition moved.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            destination, record = self.valid_bundle_record(root, environment, "pending-parity-fixture")
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "version": bundle.STATE_VERSION,
                        "entries": {},
                        "pending": self.valid_install_transition(destination, record),
                    },
                    sort_keys=True,
                )
            )
            before = state_path.read_bytes()

            human = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run")
            machine = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run", "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            self.assertEqual(report["overall"]["state"], "blocked")
            self.assertEqual(report["recovery"]["state"], "proposed")
            self.assertIn("pending-recovery", {finding["code"] for finding in report["findings"]})
            for finding in report["findings"]:
                self.assertIn(finding["message"], human.stdout)
            for proposal in report["recovery"]["proposals"]:
                self.assertIn(proposal["path"], human.stdout)
            self.assertEqual(state_path.read_bytes(), before)
            self.assertFalse(state_path.with_name("installer.lock").exists())

    def test_public_reader_types_malformed_symlinked_and_foreign_bundle_evidence(self) -> None:
        """Re-anchored onto the bundle plane; the "foreign dispatcher" sub-case has no successor.

        gh #10 phase 4 deleted the operator-tools store this test used to type malformed,
        symlinked, and foreign evidence against; malformed and symlinked survive unchanged onto
        the bundle's own `agentic-sdlc-installer/state.json`, which the reader still reads through
        the identical `_readonly_read_file`/`_readonly_json_document` path. The retired sub-case
        was about a `ccodex` command file the operator-tools installer owned on PATH -- a concept
        that left with the plane, since the committed `bin/ccodex` carries no install-time
        ownership record at all -- so it is replaced with the bundle plane's own equivalent
        conflict: a recorded entry whose live bytes drifted from what was published, which the
        projection reports as "foreign" and the report as `owned-entry-conflict`.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"version":4,"entries":{},"entries":{},"pending":null}')
            malformed_before = state_path.read_bytes()

            malformed = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")

            self.assertEqual(malformed.returncode, 0, malformed.stderr)
            malformed_report = json.loads(malformed.stdout)
            self.assertEqual(malformed_report["overall"]["state"], "unreadable")
            self.assertIn("state-malformed", {finding["code"] for finding in malformed_report["findings"]})
            self.assertEqual(state_path.read_bytes(), malformed_before)

        if not hasattr(os, "symlink"):
            self.skipTest("symlinks are required")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            external = root / "external-state"
            external.write_text("{}")
            state_path.symlink_to(external)

            symlinked = self.run_dispatcher(dispatcher, environment, "sdlc", "status", "--json")

            self.assertEqual(symlinked.returncode, 0, symlinked.stderr)
            symlinked_report = json.loads(symlinked.stdout)
            self.assertEqual(symlinked_report["overall"]["state"], "blocked")
            self.assertIn("state-symlinked", {finding["code"] for finding in symlinked_report["findings"]})
            self.assertTrue(state_path.is_symlink())

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            destination, record = self.foreign_bundle_record(root, environment, "foreign-fixture")
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {"version": bundle.STATE_VERSION, "entries": {str(destination): record}, "pending": None},
                    sort_keys=True,
                )
            )
            foreign_before = state_path.read_bytes()

            foreign_result = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

            self.assertEqual(foreign_result.returncode, 0, foreign_result.stderr)
            foreign_report = json.loads(foreign_result.stdout)
            self.assertEqual(foreign_report["overall"]["state"], "degraded")
            self.assertIn("owned-entry-conflict", {finding["code"] for finding in foreign_report["findings"]})
            self.assertEqual(foreign_report["bundle"]["entries"][0]["state"], "foreign")
            # The reader is read-only: the drifted entry is reported, never repaired or overwritten.
            self.assertEqual(state_path.read_bytes(), foreign_before)

    def test_hostile_state_values_are_redacted_from_json_and_human_reports(self) -> None:
        """Re-anchored onto the bundle plane: three sub-cases, not six.

        gh #10 phase 4 deleted the operator-tools store, so the four `operator-*` sub-cases lost
        their subject. `operator-version` and `operator-pending` were exactly the shapes
        `bundle-version` and `bundle-transition` already cover on the surviving plane, so nothing
        is lost by dropping them rather than doubling them. `operator-duplicate` and
        `operator-record` tested a DIFFERENT structural position -- a canary that could only leak
        through a document-level PARSE failure, never through a validated field -- and that
        position survives here as `bundle-malformed`: `_readonly_json_document` raises on a
        duplicate top-level key and the caller reports the FIXED literal "bundle state is
        malformed", so the canary cannot reach either report by construction, whether it names a
        duplicate key or a duplicate entries record.
        """
        canaries = {
            "bundle-version": "AK" + "IA" + "0" * 16,
            "bundle-malformed": "sk" + "-ant-api-malformed-canary",
            "bundle-transition": "gh" + "p_transition-canary",
        }

        def bundle_version(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.bundle_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"version": canary, "entries": {}, "pending": None}))

        def bundle_malformed(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.bundle_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(f'{{"version":{bundle.STATE_VERSION},"{canary}":"{canary}","{canary}":"{canary}"}}')

        def bundle_transition(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.bundle_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "version": bundle.STATE_VERSION,
                        "entries": {},
                        "pending": {"operation": "install", "path": canary, "before": None, "after": None},
                    }
                )
            )

        scenarios = {
            "bundle-version": bundle_version,
            "bundle-malformed": bundle_malformed,
            "bundle-transition": bundle_transition,
        }
        for name, builder in scenarios.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                dispatcher, environment, _query_state = self.make_dispatcher(root)
                canary = canaries[name]
                builder(root, environment, canary)

                human = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor")
                machine = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

                self.assertEqual(human.returncode, 0, human.stderr)
                self.assertEqual(machine.returncode, 0, machine.stderr)
                self.assertIn(json.loads(machine.stdout)["overall"]["state"], {"blocked", "unreadable"})
                self.assertNotIn(canary, machine.stdout)
                self.assertNotIn(canary, human.stdout)

    def test_valid_current_bundle_entry_uses_an_opaque_public_locator(self) -> None:
        canary = "sk" + "-ant-api-valid-entry-canary"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            destination, record = self.valid_bundle_record(root, environment, canary)
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "version": bundle.STATE_VERSION,
                        "entries": {str(destination): record},
                        "pending": None,
                    }
                )
            )

            human = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor")
            machine = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            self.assertEqual(report["bundle"]["state"], "degraded")
            self.assertEqual(
                report["bundle"]["entries"],
                [{"name": "claude-skill-1", "path": "bundle-entry://claude/skill/1", "state": "absent"}],
            )
            self.assertEqual(report["bundle"]["findings"][0]["path"], "bundle-entry://claude/skill/1")
            self.assertNotIn(canary, machine.stdout)
            self.assertNotIn(canary, human.stdout)

    def test_valid_current_bundle_transition_uses_an_opaque_public_locator(self) -> None:
        canary = "gh" + "p_valid-transition-canary"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            destination, record = self.valid_bundle_record(root, environment, canary)
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "version": bundle.STATE_VERSION,
                        "entries": {},
                        "pending": self.valid_install_transition(destination, record),
                    }
                )
            )

            human = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run")
            machine = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run", "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            self.assertEqual(report["bundle"]["state"], "blocked")
            self.assertEqual(report["recovery"]["state"], "proposed")
            self.assertEqual(
                report["bundle"]["recovery"],
                [
                    {
                        "action": "lifecycle-dry-run",
                        "component": "bundle",
                        "path": "bundle-transition://claude/skill/1",
                        "state": "pending",
                    }
                ],
            )
            self.assertNotIn(canary, machine.stdout)
            self.assertNotIn(canary, human.stdout)

    def test_old_home_bundle_transition_is_not_current_projection_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            destination, record = self.valid_bundle_record(root, environment, "old-only", home=root / "old-home")
            state_path = self.bundle_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "version": bundle.STATE_VERSION,
                        "entries": {},
                        "pending": self.valid_install_transition(destination, record),
                    }
                )
            )

            human = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor")
            machine = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            self.assertEqual(report["bundle"]["state"], "absent")
            self.assertEqual(report["bundle"]["entries"], [])
            self.assertEqual(report["bundle"]["findings"], [])
            self.assertEqual(report["bundle"]["recovery"], [])
            self.assertEqual(report["overall"]["state"], "absent")
            self.assertIn("bundle: absent", human.stdout)

    def test_closed_grammar_rejects_effectful_or_ambiguous_recovery_spellings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))
            invalid = (
                ("sdlc",),
                ("sdlc", "recover"),
                ("sdlc", "recover", "--json"),
                ("sdlc", "recover", "--json", "--dry-run"),
                ("sdlc", "recover", "--dry-run", "--dry-run"),
                ("sdlc", "inspect", "--dry-run"),
                ("sdlc", "follow"),
                ("sdlc", "install"),
            )
            for arguments in invalid:
                with self.subTest(arguments=arguments):
                    completed = self.run_dispatcher(dispatcher, environment, *arguments)
                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("usage: ccodex sdlc", completed.stderr)
            self.assertFalse(query_state.exists())

    def test_wrong_or_unisolated_interpreters_refuse_before_any_report_is_trusted(self) -> None:
        """``runtime_admission()``'s own refusal ladder, driven directly.

        gh #10 phase 4 deleted the rendered ``assets/launchers/ccodex.in`` template entirely, so
        there is no more install-time ``installed_sdlc_python='...'`` marker to substitute a
        missing or wrong interpreter into -- that whole mechanism (and its "missing interpreter"
        refusal) left with the rendering plane. What survives is ``runtime_admission()`` itself,
        which this test drives directly with (a) the pinned interpreter missing its own isolation
        flags and (b) a genuinely different interpreter under full isolation. ``-B`` is kept on
        the unisolated invocation specifically so it writes no ``.pyc`` into this checkout's own
        ``scripts/`` directory -- it alone still forces ``sys.flags.isolated`` False, which is the
        one fact this sub-case needs.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, query_state = self.make_dispatcher(root)

            unisolated = subprocess.run(
                [str(Path(sys.executable)), "-B", str(READER_SCRIPT), "inspect", "--json"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(unisolated.returncode, 3, unisolated.stderr)
            unisolated_report = json.loads(unisolated.stdout)
            self.assertEqual(unisolated_report["runtime"]["state"], "refused")
            self.assertFalse(unisolated_report["runtime"]["isolated"])
            self.assertEqual(unisolated_report["overall"]["exit_class"], "safe-refusal")
            self.assertIn(
                "runtime-admission-refused", {item["code"] for item in unisolated_report["findings"]}
            )
            self.assertFalse(query_state.exists())

            wrong = next(
                (
                    candidate
                    for candidate in (
                        Path("/usr/local/bin/python3"),
                        Path("/usr/bin/python3"),
                        Path(shutil.which("python3", path="/usr/local/bin:/usr/bin:/bin") or "/missing"),
                    )
                    if candidate.is_file()
                    and os.access(candidate, os.X_OK)
                    and subprocess.run(
                        [str(candidate), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
                        capture_output=True,
                        text=True,
                        check=True,
                    ).stdout.strip()
                    != "3.12.11"
                ),
                None,
            )
            self.assertIsNotNone(wrong, "a wrong interpreter is required to test runtime admission")

            wrong_result = subprocess.run(
                [str(wrong), "-I", "-B", str(READER_SCRIPT), "inspect", "--json"],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(wrong_result.returncode, 3, wrong_result.stderr)
            report = json.loads(wrong_result.stdout)
            self.assertEqual(report["runtime"]["state"], "refused")
            self.assertEqual(report["overall"]["exit_class"], "safe-refusal")
            self.assertIn("runtime-admission-refused", {item["code"] for item in report["findings"]})
            self.assertFalse(query_state.exists())

            # Positive control: the SAME reader, under the SAME pinned interpreter this suite runs
            # on, is admitted -- so the two refusals above are about the interpreter and not about a
            # report that refuses unconditionally.
            admitted = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")
            self.assertEqual(admitted.returncode, 0, admitted.stderr)
            self.assertEqual(json.loads(admitted.stdout)["runtime"]["state"], "admitted")

    def test_validator_pins_both_ccodex_report_policies_by_digest(self) -> None:
        """The structural re-derivation collapsed to a digest; the predicate got stronger.

        Both descriptors are parsed by `scripts/ccodex_sdlc.py` on every invocation, which is
        where malformed input must fail. What this pass owes is drift detection in the checkout,
        so the mutations below are the ones the old 85-line structural walk covered — a widened
        vocabulary, a dropped field, a trailing byte — plus the two cases it could not express:
        an unrelated byte anywhere in the document, and a symlinked policy.
        """
        clean = validator.Validation()
        validator.validate_ccodex_sdlc_report_policies(ROOT, clean)
        self.assertEqual(clean.errors, [])

        relatives = (
            "policy/ccodex-sdlc-read-report.v1.json",
            "policy/ccodex-sdlc-read-report.v2.json",
        )
        self.assertEqual(
            sorted(validator.CCODEX_SDLC_REPORT_POLICY_SHA256), sorted(relatives)
        )

        for relative in relatives:
            original = json.loads((ROOT / relative).read_text())
            mutations: list[tuple[str, str]] = [
                ("trailing-byte", (ROOT / relative).read_text() + " "),
                ("duplicate-member", '{"schema_version":"one","schema_version":"two"}\n'),
            ]
            for key in original:
                changed = copy.deepcopy(original)
                changed.pop(key)
                mutations.append((f"dropped-{key}", json.dumps(changed, separators=(",", ":"), sort_keys=True) + "\n"))
            for key, value in original.items():
                if isinstance(value, list):
                    changed = copy.deepcopy(original)
                    changed[key] = [*value, "drift"]
                    mutations.append((f"widened-{key}", json.dumps(changed, separators=(",", ":"), sort_keys=True) + "\n"))
                if isinstance(value, dict):
                    for inner, inner_value in value.items():
                        if not isinstance(inner_value, list):
                            continue
                        changed = copy.deepcopy(original)
                        changed[key][inner] = [*inner_value, "drift"]
                        mutations.append((f"widened-{key}.{inner}", json.dumps(changed, separators=(",", ":"), sort_keys=True) + "\n"))
            self.assertGreater(len(mutations), 10, relative)
            for label, text in mutations:
                with self.subTest(policy=relative, label=label), tempfile.TemporaryDirectory() as temp:
                    root = Path(temp)
                    policy_path = root / relative
                    policy_path.parent.mkdir(parents=True)
                    policy_path.write_text(text)
                    drift = validator.Validation()
                    validator.validate_ccodex_sdlc_report_policies(root, drift)
                    self.assertTrue(
                        any("bytes differ from the reviewed ccodex report contract" in error for error in drift.errors),
                        f"{relative} {label}: {drift.errors}",
                    )

            with self.subTest(policy=relative, label="symlinked"), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                policy_path = root / relative
                policy_path.parent.mkdir(parents=True)
                policy_path.symlink_to(ROOT / relative)
                linked = validator.Validation()
                validator.validate_ccodex_sdlc_report_policies(root, linked)
                # The absent sibling policy also reports "missing or linked", so the assertion
                # must name THIS relative or it would pass with the is_symlink branch deleted.
                self.assertTrue(
                    any(
                        error.startswith(f"{relative}: ") and "missing or linked" in error
                        for error in linked.errors
                    ),
                    linked.errors,
                )

    def test_the_reader_does_not_fall_back_to_poisoned_external_tools(self) -> None:
        """The reader loads every sibling by absolute path and never shells out by name.

        Driven directly rather than through a rendered dispatcher (gh #10 phase 4 deleted that
        rendering plane): ``run_dispatcher`` strips the leading ``sdlc`` and execs the real
        ``scripts/ccodex_sdlc.py`` under ``-I -B``, so a poisoned ``PATH`` still proves the same
        claim it always did -- nothing in the reader's own code resolves ``ocx``/``mise``/``uv``/
        ``curl``/``git``/``claude``/``seeds``/``node`` by name, and its read-only guard blocks
        ``subprocess`` outright.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, query_state = self.make_dispatcher(root)
            sentinel_bin = root / "sentinel-bin"
            sentinel_bin.mkdir()
            marker = root / "external-tool-ran"
            for name in ("ocx", "mise", "uv", "curl", "git", "claude", "seeds", "node"):
                executable = sentinel_bin / name
                executable.write_text(f"#!/bin/sh\nprintf '{name}\\n' >> '{marker}'\nexit 91\n")
                executable.chmod(0o755)
            environment["PATH"] = f"{sentinel_bin}:/usr/bin:/bin"

            completed = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")
            self.assertFalse(query_state.exists())

    def test_read_only_guard_rejects_filesystem_locks_processes_and_sockets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            probe = f"""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys

guard_path = Path({str(ROOT / 'scripts' / 'ccodex_sdlc_readonly.py')!r})
spec = importlib.util.spec_from_file_location('probe_guard', guard_path)
assert spec and spec.loader
guard = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = guard
spec.loader.exec_module(guard)
guard.install()
root = Path({str(root)!r})
attempts = [
    lambda: open(root / 'write', 'w'),
    lambda: (root / 'mkdir').mkdir(),
    lambda: os.open(root / 'open', os.O_CREAT | os.O_WRONLY),
    lambda: os.rename(root / 'old', root / 'new'),
    lambda: os.unlink(root / 'unlink'),
    lambda: os.symlink(root / 'target', root / 'link'),
    lambda: os.write(1, b'x'),
    lambda: os.fsync(1),
    lambda: subprocess.run([sys.executable, '-c', 'raise SystemExit(0)']),
    lambda: socket.socket(),
]
try:
    import fcntl
except ImportError:
    pass
else:
    attempts.append(lambda: fcntl.flock(0, fcntl.LOCK_EX))
for attempt in attempts:
    try:
        attempt()
    except guard.ReadOnlyViolation:
        continue
    raise AssertionError('guard permitted an effectful operation')
print('guard blocked every attempted effect')
"""

            completed = subprocess.run(
                [str(Path(sys.executable)), "-I", "-B", "-c", probe],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, "guard blocked every attempted effect\n")
            self.assertEqual(list(root.iterdir()), [])

    @unittest.skipUnless(
        sys.platform.startswith("linux") and shutil.which("strace"),
        "Linux strace is unavailable; portable sentinel coverage remains active",
    )
    def test_the_reader_has_no_effectful_syscalls_or_external_tool_fallbacks(self) -> None:
        """The real reader's own syscall trace, driven directly: no bash layer, no mise, no child.

        gh #10 phase 4 deleted the rendered dispatcher this trace used to cover, along with the
        install-time plane that rendered it. What this test proves is scoped to exactly what
        ``run_dispatcher`` drives for every ``sdlc`` vector in this file -- the real
        ``scripts/ccodex_sdlc.py`` under ``-I -B`` -- so the trace covers the one process this
        suite's other assertions exercise, with no bash-initialization noise to except.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _dispatcher, environment, query_state = self.make_dispatcher(root)
            sentinel_bin = root / "sentinel-bin"
            sentinel_bin.mkdir()
            marker = root / "external-tool-ran"
            for name in ("ocx", "mise", "uv", "curl", "git", "claude", "seeds", "node"):
                executable = sentinel_bin / name
                executable.write_text(f"#!/bin/sh\nprintf '{name}\\n' >> '{marker}'\nexit 91\n")
                executable.chmod(0o755)
            environment["PATH"] = f"{sentinel_bin}:/usr/bin:/bin"
            trace = root / "ccodex-sdlc.strace"
            completed = subprocess.run(
                [
                    str(shutil.which("strace")),
                    "-f",
                    "-qq",
                    "-o",
                    str(trace),
                    "-e",
                    "trace=open,openat,creat,mkdir,mkdirat,rename,renameat,renameat2,unlink,unlinkat,fsync,fdatasync,flock,fcntl,connect,socket,socketpair,execve",
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(READER_SCRIPT),
                    "doctor",
                    "--json",
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(marker.exists(), marker.read_text() if marker.exists() else "")
            self.assertFalse(query_state.exists())
            syscalls = trace.read_text()
            effectful: list[str] = []
            for line in syscalls.splitlines():
                # No bash layer remains to probe /dev/tty, but the exception is kept harmlessly in
                # case the calling harness's own stdio is ever a pty passed through.
                if "O_RDWR" in line and '"/dev/tty"' not in line:
                    effectful.append(line)
                if any(token in line for token in ("O_WRONLY", "O_CREAT", "O_TRUNC", "O_APPEND")):
                    effectful.append(line)
                if any(
                    token in line
                    for token in (
                        "mkdir(",
                        "mkdirat(",
                        "rename(",
                        "renameat(",
                        "renameat2(",
                        "unlink(",
                        "unlinkat(",
                        "fsync(",
                        "fdatasync(",
                        "flock(",
                        "F_SETLK",
                        "F_SETLKW",
                        "connect(",
                        "socket(",
                        "socketpair(",
                    )
                ):
                    effectful.append(line)
            self.assertFalse(effectful, "\n".join(effectful))
            for name in ("ocx", "mise", "uv", "curl", "git", "claude", "seeds", "node"):
                self.assertNotIn(f'{sentinel_bin}/{name}",', syscalls)


class RetiredOperatorToolsStoreFindingTests(unittest.TestCase):
    """``retired_store_findings`` is now the ONLY producer of the ``operator-tools`` finding.

    Unit-level and in-process, over the real ``reader``/``bundle`` modules loaded by absolute
    path at module scope above -- the same admission shape the reader itself uses to load its own
    optional siblings. ``Path.home()`` and ``state_root_for`` both read the process environment
    rather than taking an injected location, so isolation here is ``HOME``/``XDG_STATE_HOME``
    patched through ``mock.patch.dict`` for the duration of one call, exactly as this module's
    other isolated-HOME tests isolate a subprocess's environment instead.
    """

    def test_an_absent_store_is_silent_and_a_present_store_is_named_with_its_remedy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            state = Path(temp) / "state"
            home.mkdir()

            with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_STATE_HOME": str(state)}, clear=False):
                absent = reader.retired_store_findings(bundle)
            self.assertEqual(absent, [])

            store = state / reader.RETIRED_OPERATOR_TOOLS_STORE
            store.mkdir(parents=True)
            (store / "state.json").write_text('{"version":2,"entries":{},"pending":null}')

            with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_STATE_HOME": str(state)}, clear=False):
                present = reader.retired_store_findings(bundle)

            # Positive control for the absence assertion above: the SAME lookup, over a host that
            # DOES carry the leftover store, is not silent -- so the empty list above is a fact
            # about an absent store, not a function that always answers empty.
            self.assertEqual(len(present), 1)
            finding = present[0]
            self.assertEqual(finding["code"], "foreign-state")
            self.assertEqual(finding["component"], "operator-tools")
            self.assertIn(reader.RETIRED_OPERATOR_TOOLS_REMEDY, finding["message"])
            self.assertIn(str(store), finding["path"])

    def test_a_store_replaced_by_a_dangling_symlink_is_still_named_without_being_followed(self) -> None:
        """``lstat`` sees the leftover even when it no longer resolves to real content."""
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            state = Path(temp) / "state"
            home.mkdir()
            state.mkdir()
            store = state / reader.RETIRED_OPERATOR_TOOLS_STORE
            store.symlink_to(state / "nowhere")

            with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_STATE_HOME": str(state)}, clear=False):
                findings = reader.retired_store_findings(bundle)

            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["path"], str(store))


if __name__ == "__main__":
    unittest.main()
