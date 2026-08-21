"""``ccodex sdlc recover --apply <plan-sha256>``: the one mutating recover form (agentic-sdlc-baaa).

THE APPROVAL IS THE DIGEST, so these tests measure exactly that: the dry-run assessment renders the
digest of the plan it derived and writes nothing; the apply form re-derives that plan from verified
journal and receipt state and either resumes, rolls back, or refuses BY NAME.  Every negative
assertion carries a positive control, because a refusal that would also fire on a healthy host
proves nothing about the boundary it claims to defend.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
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
LAUNCHER_TEMPLATE = ROOT / "assets" / "launchers" / "ccodex.in"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The reader is loaded for its constants and its grammar only. Its projection entry points install a
# process-wide read-only guard that would block this harness's own writes, so every end-to-end check
# below runs the reader as a subprocess instead.
reader = _load("recover_apply_reader", ROOT / "scripts" / "ccodex_sdlc.py")
recover = _load("recover_apply_module", ROOT / "scripts" / "ccodex_sdlc_recover.py")
bundle = _load("recover_apply_bundle", ROOT / "scripts" / "install_skill_bundle.py")
operator_tools = _load("recover_apply_operator_tools", ROOT / "scripts" / "install_operator_tools.py")
dar = _load("recover_apply_receipts", ROOT / "scripts" / "distribution_activation_receipt.py")

#: One well-formed digest that is not the digest of any plan this suite derives.
FOREIGN_DIGEST = hashlib.sha256(b"a plan no host derives").hexdigest()
#: Every malformed ``--apply`` spelling. `\d` would admit the Arabic-Indic digit, so a digest spelled
#: in it is pinned here as a REFUSAL rather than read as the same value.
MALFORMED_DIGESTS = (
    "",
    "5" * 63,
    "5" * 65,
    "5" * 63 + "g",
    "5" * 63 + "F",
    "٩" * 64,
    "5" * 63 + "\n",
    " " + "5" * 63,
    "0x" + "5" * 62,
)


def tree_hash(*roots: Path) -> str:
    """One digest over every path, mode, and byte under the given roots: did anything move?"""
    digest = hashlib.sha256()
    for root in roots:
        for path in sorted(root.rglob("*") if root.exists() else []):
            item = path.lstat()
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(f"{item.st_mode:o}".encode("ascii"))
            if path.is_symlink():
                digest.update(os.readlink(path).encode("utf-8"))
            elif path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


class RecoverApplyHarness(unittest.TestCase):
    """One installed dispatcher over a private home, plus planted interrupted journal state."""

    def make_dispatcher(self, root: Path) -> tuple[Path, dict[str, str]]:
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
        environment = os.environ.copy()
        environment.update(
            {
                "AGENTIC_SDLC_ROOT": str(ROOT),
                "HOME": str(query_home),
                "XDG_BIN_HOME": str(root / "query-bin"),
                "XDG_STATE_HOME": str(root / "query-state"),
                "CODEX_HOME": str(query_home / ".codex"),
                "PYTHONPATH": str(root / "poisoned-pythonpath"),
            }
        )
        return config.bin_dir / "ccodex", environment

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

    def observed_roots(self, environment: dict[str, str]) -> tuple[Path, ...]:
        return (
            Path(environment["HOME"]),
            Path(environment["XDG_STATE_HOME"]),
            Path(environment["XDG_BIN_HOME"]),
        )

    def bundle_config(self, environment: dict[str, str]):
        return bundle.Config(
            ROOT,
            Path(environment["HOME"]),
            Path(environment["CODEX_HOME"]),
            "auto",
            True,
            "all",
            Path(environment["XDG_STATE_HOME"]),
        )

    def bundle_state_path(self, environment: dict[str, str]) -> Path:
        return self.bundle_config(environment).state_path

    # ---- planted journal state ---------------------------------------------------------------

    def planted_entry(
        self, root: Path, environment: dict[str, str], name: str
    ) -> tuple[Path, dict[str, object], Path]:
        """Install one exact skill payload at its configured destination and record it."""
        config = self.bundle_config(environment)
        source = root / "bundle-source" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: fixture\n---\n", encoding="utf-8")
        entry = bundle.Entry("claude", "skill", name, source)
        destination = bundle.destination_for(entry, config)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        record = bundle.entry_record(
            entry,
            "copy",
            # The configured ROOT of a claude entry is the operator's home, not the collection above
            # the destination: an identity taken from the wrong directory makes every layout read as
            # a conflict, which would make a recovery test pass while recovering nothing.
            bundle.stat_identity(bundle.configured_root(entry, config)),
            bundle.stat_identity(destination.parent),
            installed_path=destination,
        )
        return destination, record, source

    def armed_create(
        self, destination: Path, record: dict[str, object], stage: Path | None
    ) -> dict[str, object]:
        container = stage or destination.parent / f".{destination.name}.stage-opaque"
        return {
            "operation": "create",
            "phase": "armed",
            "key": str(destination),
            "destination": str(destination),
            "old_record": None,
            "old_owned": False,
            "new_record": record,
            "stage_container": str(container),
            "stage_payload": str(container / "payload"),
            "stage_identity": bundle.stat_identity(container)
            if container.exists()
            else bundle.stat_identity(destination.parent),
            "backup_container": None,
            "backup_payload": None,
            "backup_identity": None,
        }

    def write_journal(self, environment: dict[str, str], transactions: dict[str, object]) -> Path:
        path = self.bundle_state_path(environment)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": 3, "entries": {}, "transactions": transactions}), encoding="utf-8"
        )
        return path

    def plant_finalizable_transaction(
        self, root: Path, environment: dict[str, str]
    ) -> tuple[Path, Path]:
        """An armed create whose destination is already exact: recovery FINALIZES it."""
        destination, record, _source = self.planted_entry(root, environment, "finalize-fixture")
        journal = self.write_journal(
            environment, {str(destination): self.armed_create(destination, record, None)}
        )
        return destination, journal

    def plant_rollbackable_transaction(
        self, root: Path, environment: dict[str, str]
    ) -> tuple[Path, Path, Path]:
        """An armed create that never published: the staged candidate is rolled back and removed.

        The record is built from the STAGED payload, which is what the real transaction records: a
        publish is a rename, so the payload's identity is the identity the destination would have
        had.  Building it from a destination that never existed would make the layout read as a
        conflict and the rollback below would prove nothing.
        """
        config = self.bundle_config(environment)
        name = "rollback-fixture"
        source = root / "bundle-source" / name
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: fixture\n---\n", encoding="utf-8")
        entry = bundle.Entry("claude", "skill", name, source)
        destination = bundle.destination_for(entry, config)
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = destination.parent / f".{destination.name}.stage-opaque"
        stage.mkdir()
        shutil.copytree(source, stage / "payload")
        record = bundle.entry_record(
            entry,
            "copy",
            bundle.stat_identity(bundle.configured_root(entry, config)),
            bundle.stat_identity(destination.parent),
            installed_path=stage / "payload",
        )
        journal = self.write_journal(
            environment, {str(destination): self.armed_create(destination, record, stage)}
        )
        return destination, stage, journal

    def plant_operator_tools_pending(
        self, environment: dict[str, str], *, live: bytes | None
    ) -> tuple[Path, Path]:
        """An interrupted operator-tools install: the recorded file either arrived or it did not."""
        bin_dir = Path(environment["XDG_BIN_HOME"])
        bin_dir.mkdir(parents=True, exist_ok=True)
        command = bin_dir / "ccodex"
        payload = b"#!/bin/sh\nexit 0\n"
        if live is not None:
            command.write_bytes(live)
            command.chmod(0o755)
        state = (
            Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc-operator-tools" / "state.json"
        )
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "version": 2,
                    "entries": {},
                    "pending": {
                        "operation": "install",
                        "path": str(command),
                        "before": None,
                        "after": {
                            "path": str(command),
                            "digest": hashlib.sha256(payload).hexdigest(),
                            "removable": "true",
                        },
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return state, command

    # ---- the dry-run digest ------------------------------------------------------------------

    def plan_digest_from_dry_run(
        self, dispatcher: Path, environment: dict[str, str]
    ) -> tuple[str, subprocess.CompletedProcess[str]]:
        completed = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = [line for line in completed.stderr.splitlines() if line.startswith("recovery plan ")]
        self.assertEqual(len(lines), 1, completed.stderr)
        prefix = "recovery plan sha256 "
        self.assertTrue(lines[0].startswith(prefix), lines[0])
        digest = lines[0][len(prefix) : len(prefix) + 64]
        self.assertTrue(recover.is_plan_digest(digest), lines[0])
        self.assertIn(f"ccodex sdlc recover --apply {digest}", lines[0])
        return digest, completed


class RecoverApplyGrammarTests(RecoverApplyHarness):
    def test_every_malformed_apply_spelling_is_a_grammar_error_at_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            before = tree_hash(*self.observed_roots(environment))
            for value in MALFORMED_DIGESTS:
                with self.subTest(digest=value):
                    completed = self.run_dispatcher(
                        dispatcher, environment, "sdlc", "recover", "--apply", value
                    )
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertIn("64-character lowercase hexadecimal", completed.stderr)
                    self.assertEqual(completed.stdout, "")
                    self.assertNotIn("Traceback", completed.stderr)
            for vector in (
                ("recover", "--apply"),
                ("recover", "--apply", FOREIGN_DIGEST, "--json"),
                ("recover", "--apply", FOREIGN_DIGEST, FOREIGN_DIGEST),
                ("recover", f"--apply={FOREIGN_DIGEST}"),
                ("recover", "--dry-run", "--apply", FOREIGN_DIGEST),
                ("recover", "--json", "--apply", FOREIGN_DIGEST),
                ("recover", "--apply", FOREIGN_DIGEST, "--dry-run"),
            ):
                with self.subTest(vector=vector):
                    completed = self.run_dispatcher(dispatcher, environment, "sdlc", *vector)
                    self.assertEqual(completed.returncode, 2, completed.stderr)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn("usage: ccodex sdlc", completed.stderr)
            # Positive control: the SAME dispatcher admits the well-formed spelling and reaches the
            # module, which refuses on its own evidence (exit 3) rather than as a usage error.
            control = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", FOREIGN_DIGEST
            )
            self.assertEqual(control.returncode, 3, control.stderr)
            self.assertIn("ccodex sdlc recover --apply refused before any effect", control.stderr)
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))

    def test_a_supplied_but_unusable_digest_is_named_and_never_echoed_unescaped(self) -> None:
        # Distinguishing not-supplied from supplied-but-missing, and escaping an argv-derived value
        # before it reaches a line: a bare newline would forge a line of this command's own output.
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            missing = recover.main(["--apply"])
        self.assertEqual(missing, 3)
        self.assertIn("was supplied without the plan digest it approves", stderr.getvalue())
        rendered = recover.escape_display("a\nb\rc\td\x1b[2Je\x7f")
        self.assertEqual(rendered, "a\\nb\\rc\\td\\x1b[2Je\\x7f")
        for value in ("a\nb", "\x1b[2J" + "5" * 60):
            with self.subTest(value=value):
                message = f"{recover.show(value)}"
                self.assertNotIn("\n", message)
                self.assertNotIn("\x1b", message)
        # Positive control: an ordinary value is NOT mangled by the same escaper.
        self.assertEqual(recover.escape_display(FOREIGN_DIGEST), FOREIGN_DIGEST)

    def test_the_escaper_agrees_character_for_character_with_the_receipt_family(self) -> None:
        probe = "".join(chr(code) for code in range(0, 0x80)) + "ünïcødé"
        self.assertEqual(recover.escape_display(probe), dar.escape_display(probe))
        # Positive control: the comparison above is a measurement, not two empty strings.
        self.assertIn("\\x00", recover.escape_display(probe))

    def test_candidate_mode_refuses_the_apply_form_twice_and_runs_no_module(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            projection, marker = self.make_candidate_projection(root)
            refused = subprocess.run(
                [str(projection), "sdlc", "recover", "--apply", FOREIGN_DIGEST],
                env={"HOME": str(root / "home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(refused.returncode, 2, refused.stderr)
            self.assertIn("candidate ccodex admits only read-only sdlc inspection", refused.stderr)
            self.assertFalse(marker.exists())
            # Positive control: the closed allowlist admits the read-only form, so the refusal above
            # is the apply FORM being declined and not the candidate profile refusing everything.
            control = subprocess.run(
                [str(projection), "sdlc", "recover", "--dry-run"],
                env={"HOME": str(root / "home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertTrue(marker.exists())

            # The reader refuses the same vector a second time when invoked directly, so a caller
            # that bypasses the launcher cannot reach the module either.
            direct = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(ROOT / "scripts" / "ccodex_sdlc.py"),
                    "--candidate-observation-v1",
                    "recover",
                    "--apply",
                    FOREIGN_DIGEST,
                ],
                env={"HOME": str(root / "home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(direct.returncode, 3, direct.stderr)
            self.assertIn("candidate ccodex sdlc admits only read-only inspection", direct.stderr)
            self.assertIn("recover --apply is a mutating lifecycle verb", direct.stderr)
            self.assertEqual(direct.stdout, "")

    def make_candidate_projection(self, root: Path) -> tuple[Path, Path]:
        """Render the candidate read-only profile of the dispatcher over a stub interpreter."""
        rendered = (
            LAUNCHER_TEMPLATE.read_text(encoding="utf-8")
            .replace("@CANDIDATE_READONLY_PROFILE@", "true")
            .replace("@CANONICAL_LAUNCHER@", "''")
            .replace("@CANONICAL_ROOT@", "''")
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
            ["/usr/bin/bash", "-n", str(dispatcher)], capture_output=True, text=True, check=False
        )
        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        (projection / "scripts" / "ccodex_sdlc.py").write_text("# stub reader\n", encoding="utf-8")
        marker = root / "candidate-interpreter-ran"
        interpreter = projection / "runtime" / "python" / "bin" / "python3.12"
        interpreter.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{marker}'\nexit 0\n")
        interpreter.chmod(0o755)
        return dispatcher, marker


class RecoverPlanDerivationTests(RecoverApplyHarness):
    def test_the_plan_is_canonical_and_refuses_non_finite_values(self) -> None:
        plan = {"b": [2, 1], "a": {"z": None, "y": True}}
        rendered = recover.canonical_document(plan)
        self.assertEqual(rendered, '{"a":{"y":true,"z":null},"b":[2,1]}\n')
        self.assertEqual(
            recover.plan_digest(plan), hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        )
        for hostile in (float("1e400"), float("nan"), float("-inf")):
            with self.subTest(value=hostile):
                with self.assertRaises(ValueError):
                    recover.canonical_document({"value": hostile})
        # Positive control: the same serializer accepts an ordinary float, so the refusals above are
        # about non-finiteness and not about floats.
        self.assertEqual(recover.canonical_document({"value": 1.5}), '{"value":1.5}\n')

    def test_a_plan_digest_is_exactly_sixty_four_lowercase_hexadecimal_characters(self) -> None:
        self.assertTrue(recover.is_plan_digest("0123456789abcdef" * 4))
        for rejected in (*MALFORMED_DIGESTS, None, 5, b"5" * 64, "5" * 64 + " "):
            with self.subTest(value=rejected):
                self.assertFalse(recover.is_plan_digest(rejected))

    def test_the_dry_run_renders_the_digest_and_changes_nothing_at_all(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            self.plant_finalizable_transaction(root, environment)
            before = tree_hash(*self.observed_roots(environment))

            digest, human = self.plan_digest_from_dry_run(dispatcher, environment)
            machine = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--dry-run", "--json"
            )

            self.assertEqual(machine.returncode, 0, machine.stderr)
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))
            # stdout stays byte-for-byte the assessment it already was, in BOTH forms: the digest is
            # an approval token on stderr, never a field of the byte-pinned v1 report.
            report = json.loads(machine.stdout)
            self.assertEqual(report["recovery"]["state"], "proposed")
            self.assertNotIn(digest, machine.stdout)
            self.assertNotIn(digest, human.stdout)
            self.assertIn(digest, machine.stderr)
            # Determinism: the same state derives the same approval token.
            again, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            self.assertEqual(digest, again)

    def test_the_digest_moves_when_the_state_moves(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, journal = self.plant_finalizable_transaction(root, environment)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            document = json.loads(journal.read_text(encoding="utf-8"))
            document["transactions"][str(destination)]["phase"] = "abort-cleanup"
            journal.write_text(json.dumps(document), encoding="utf-8")

            moved, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            self.assertNotEqual(digest, moved)

            # And it moves for a journal edit no recovery ITEM reflects: an ownership record is state
            # too, so the plan's own byte digest of the journal is what makes the approval specific
            # rather than merely descriptive of the transactions it happens to list.
            document["transactions"][str(destination)]["phase"] = "armed"
            neighbour, record, _source = self.planted_entry(root, environment, "unrelated-neighbour")
            document["entries"] = {str(neighbour): record}
            journal.write_text(json.dumps(document), encoding="utf-8")
            relocated, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            self.assertNotEqual(digest, relocated)
            self.assertNotEqual(moved, relocated)

    def test_a_clean_host_offers_no_digest_to_approve(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)

            completed = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(
                "recovery plan: nothing to recover, so no plan digest is offered", completed.stderr
            )
            # Positive control: the same line DOES carry a digest once there is something to recover.
            self.plant_finalizable_transaction(root, environment)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            self.assertTrue(recover.is_plan_digest(digest))

    def test_an_absent_derivation_module_is_named_and_never_assumed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = root / "shadow"
            (shadow / "scripts").mkdir(parents=True)
            (shadow / "policy").mkdir()
            for relative in (
                "policy/ccodex-sdlc-read-report.v1.json",
                "policy/release-contract.v1.json",
                "scripts/ccodex_sdlc.py",
                "scripts/ccodex_sdlc_readonly.py",
                "scripts/install_operator_tools.py",
                "scripts/install_skill_bundle.py",
            ):
                shutil.copy2(ROOT / relative, shadow / relative)
            completed = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(shadow / "scripts" / "ccodex_sdlc.py"),
                    "recover",
                    "--dry-run",
                ],
                env={
                    "HOME": str(root / "home"),
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PATH": "",
                    "XDG_STATE_HOME": str(root / "state"),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(
                "recovery plan: unavailable (the recovery plan derivation is absent from this"
                " distribution)",
                completed.stderr,
            )
            # Positive control: the same shadow reader WITH the module present states a plan again.
            shutil.copy2(ROOT / "scripts" / "ccodex_sdlc_recover.py", shadow / "scripts")
            control = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(shadow / "scripts" / "ccodex_sdlc.py"),
                    "recover",
                    "--dry-run",
                ],
                env={
                    "HOME": str(root / "home"),
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PATH": "",
                    "XDG_STATE_HOME": str(root / "state"),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(control.returncode, 0, control.stderr)
            self.assertIn("recovery plan: nothing to recover", control.stderr)
            self.assertNotIn("unavailable", control.stderr)

    def test_a_drifted_plan_schema_declines_the_digest_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = root / "shadow"
            (shadow / "scripts").mkdir(parents=True)
            (shadow / "policy").mkdir()
            for relative in (
                "policy/ccodex-sdlc-read-report.v1.json",
                "policy/release-contract.v1.json",
                "scripts/ccodex_sdlc.py",
                "scripts/ccodex_sdlc_readonly.py",
                "scripts/ccodex_sdlc_recover.py",
                "scripts/install_operator_tools.py",
                "scripts/install_skill_bundle.py",
            ):
                shutil.copy2(ROOT / relative, shadow / relative)
            drifted = shadow / "scripts" / "ccodex_sdlc_recover.py"
            drifted.write_text(
                drifted.read_text(encoding="utf-8").replace(
                    'PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-recovery-plan@1"',
                    'PLAN_SCHEMA = "agentic-sdlc/ccodex-sdlc-recovery-plan@2"',
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(shadow / "scripts" / "ccodex_sdlc.py"),
                    "recover",
                    "--dry-run",
                ],
                env={
                    "HOME": str(root / "home"),
                    "LANG": "C",
                    "LC_ALL": "C",
                    "PATH": "",
                    "XDG_STATE_HOME": str(root / "state"),
                },
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn(
                "recovery plan: unavailable (the recovery plan derivation names another plan schema)",
                completed.stderr,
            )


class RecoverApplyExecutionTests(RecoverApplyHarness):
    def test_the_exact_digest_resumes_a_planted_interrupted_transaction_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, journal = self.plant_finalizable_transaction(root, environment)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertIn("plan re-derived from verified journal and receipt state", applied.stdout)
            self.assertIn("bundle: recovered:", applied.stdout)
            self.assertIn("authorizes no push, publication, merge, or deployment", applied.stdout)
            document = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(document["transactions"], {})
            self.assertIn(str(destination), document["entries"])
            self.assertTrue((destination / "SKILL.md").is_file())
            # The plan is spent: the same digest no longer describes this host.
            replay = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )
            self.assertEqual(replay.returncode, 3, replay.stderr)
            self.assertIn("found nothing to recover", replay.stderr)
            after = self.run_dispatcher(dispatcher, environment, "sdlc", "recover", "--dry-run")
            self.assertEqual(after.returncode, 0, after.stderr)
            self.assertIn("nothing to recover", after.stderr)

    def test_the_exact_digest_rolls_back_an_armed_create_that_never_published(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, stage, journal = self.plant_rollbackable_transaction(root, environment)
            self.assertTrue((stage / "payload" / "SKILL.md").is_file())
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertIn("bundle: recovered:", applied.stdout)
            document = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(document["transactions"], {})
            self.assertEqual(document["entries"], {})
            self.assertFalse(stage.exists())
            self.assertFalse(destination.exists())

    def test_a_stale_digest_refuses_by_name_and_touches_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, journal = self.plant_finalizable_transaction(root, environment)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            document = json.loads(journal.read_text(encoding="utf-8"))
            document["transactions"][str(destination)]["phase"] = "abort-cleanup"
            journal.write_text(json.dumps(document), encoding="utf-8")
            before = tree_hash(*self.observed_roots(environment))

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("is not the plan this host's state derives", refused.stderr)
            self.assertIn("the state moved after the approval", refused.stderr)
            self.assertIn("Nothing was touched", refused.stderr)
            self.assertEqual(refused.stdout, "")
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))
            # Positive control: the digest the moved state DOES derive is admitted, so the refusal
            # above is about staleness and not about this host being unrecoverable.
            fresh, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            self.assertNotEqual(fresh, digest)
            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", fresh
            )
            self.assertIn(applied.returncode, (0, 1), applied.stderr)
            self.assertNotIn("is not the plan this host's state derives", applied.stderr)

    def test_a_foreign_digest_nobody_derived_refuses_before_any_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            self.plant_finalizable_transaction(root, environment)
            before = tree_hash(*self.observed_roots(environment))

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", FOREIGN_DIGEST
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("is not the plan this host's state derives", refused.stderr)
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))

    def test_nothing_to_recover_refuses_rather_than_reporting_a_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            before = tree_hash(*self.observed_roots(environment))

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", FOREIGN_DIGEST
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("found nothing to recover on this host", refused.stderr)
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))

    def test_a_classified_conflict_is_preserved_named_and_reported_as_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, record, _source = self.planted_entry(root, environment, "conflict-fixture")
            foreign = destination / "SKILL.md"
            foreign.write_text("---\nname: foreign\n---\n", encoding="utf-8")
            journal = self.write_journal(
                environment, {str(destination): self.armed_create(destination, record, None)}
            )
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            payload_before = foreign.read_bytes()

            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(applied.returncode, 1, applied.stderr)
            self.assertIn("interrupted conflict", applied.stdout)
            self.assertIn("preserved state is never overwritten or deleted", applied.stdout)
            self.assertEqual(foreign.read_bytes(), payload_before)
            document = json.loads(journal.read_text(encoding="utf-8"))
            self.assertIn(str(destination), document["transactions"])

    def test_the_operator_tools_plane_is_rolled_back_through_its_own_machinery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            state, command = self.plant_operator_tools_pending(environment, live=None)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertIn("operator-tools: recovered abort:", applied.stdout)
            document = json.loads(state.read_text(encoding="utf-8"))
            self.assertIsNone(document["pending"])
            self.assertEqual(document["entries"], {})
            self.assertFalse(command.exists())

    def test_an_operator_tools_conflict_is_preserved_named_and_reported_as_attention(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            state, command = self.plant_operator_tools_pending(
                environment, live=b"#!/bin/sh\n# a foreign file nobody recorded\n"
            )
            before_state = state.read_bytes()
            before_command = command.read_bytes()
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(applied.returncode, 1, applied.stderr)
            self.assertIn("operator-tools: preserved conflict:", applied.stdout)
            self.assertEqual(state.read_bytes(), before_state)
            self.assertEqual(command.read_bytes(), before_command)
            # Positive control: the same plane with the recorded content live DOES commit, so the
            # preservation above is the conflict boundary and not an inability to recover at all.
            command.write_bytes(b"#!/bin/sh\nexit 0\n")
            fresh, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            # The live file is part of what the plan observed, so replacing it moves the digest: an
            # approval granted against a foreign file cannot be spent on the recorded one.
            self.assertNotEqual(fresh, digest)
            committed = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", fresh
            )
            self.assertEqual(committed.returncode, 0, committed.stderr)
            self.assertIn("operator-tools: recovered commit:", committed.stdout)
            self.assertIn(str(command), json.loads(state.read_text(encoding="utf-8"))["entries"])

    def test_unverifiable_receipt_evidence_refuses_and_preserves_the_recorded_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            self.plant_finalizable_transaction(root, environment)
            plane = (
                Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc" / "activation" / "receipts"
            )
            plane.mkdir(parents=True)
            receipt = plane / f"{hashlib.sha256(b'unsealed').hexdigest()}.json"
            receipt.write_text('{"schema_version":"not-a-receipt"}\n', encoding="utf-8")
            sealed_before = receipt.read_bytes()
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            before = tree_hash(*self.observed_roots(environment))

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("activation-receipt://", refused.stderr)
            self.assertIn("this host's evidence", refused.stderr)
            self.assertEqual(receipt.read_bytes(), sealed_before)
            self.assertEqual(before, tree_hash(*self.observed_roots(environment)))
            # Positive control: with no unverifiable evidence recorded, the SAME host recovers, so
            # the refusal above is the receipt gate and not a broken apply.
            receipt.unlink()
            fresh, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            applied = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", fresh
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)

    def test_an_unrecognised_neighbour_in_the_receipts_plane_is_named_not_interpreted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            self.plant_finalizable_transaction(root, environment)
            plane = (
                Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc" / "activation" / "receipts"
            )
            plane.mkdir(parents=True)
            (plane / "operator-notes.json").write_text("{}\n", encoding="utf-8")
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("activation-receipt://unrecognised-", refused.stderr)
            self.assertIn("preserved and refused rather than interpreted", refused.stderr)
            # The unrecognised NAME is never republished, only its opaque locator.
            self.assertNotIn("operator-notes", refused.stderr)

    def test_a_symlinked_journal_is_reported_instead_of_followed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment = self.make_dispatcher(root)
            destination, journal = self.plant_finalizable_transaction(root, environment)
            digest, _ = self.plan_digest_from_dry_run(dispatcher, environment)
            elsewhere = root / "elsewhere.json"
            elsewhere.write_bytes(journal.read_bytes())
            journal.unlink()
            journal.symlink_to(elsewhere)

            refused = self.run_dispatcher(
                dispatcher, environment, "sdlc", "recover", "--apply", digest
            )

            self.assertEqual(refused.returncode, 3, refused.stderr)
            self.assertIn("journal://bundle/state", refused.stderr)
            self.assertIn("symlinked", refused.stderr)
            self.assertEqual(refused.stdout, "")
            self.assertTrue(journal.is_symlink())


class RecoverApplyBoundaryTests(RecoverApplyHarness):
    def test_an_uncertified_platform_refuses_by_name(self) -> None:
        with self.assertRaises(recover.Refusal) as refused:
            recover.admit_platform(system="Darwin", machine="arm64")
        self.assertIn("resumes an activated Linux plane and is certified only there", str(refused.exception))
        self.assertIn("'Darwin'", str(refused.exception))
        with self.assertRaises(recover.Refusal) as architecture:
            recover.admit_platform(system="Linux", machine="riscv64")
        self.assertIn("linux-x64", str(architecture.exception))
        # Positive control: the certified pair is admitted by the same function.
        self.assertIsNone(recover.admit_platform(system="Linux", machine="x86_64"))
        self.assertIsNone(recover.admit_platform(system="Linux", machine="AMD64"))

    def test_the_read_only_guard_blocks_this_module_by_name_before_any_effect(self) -> None:
        guard = _load("recover_apply_guard_probe", ROOT / "scripts" / "ccodex_sdlc_readonly.py")
        sys.modules["_ccodex_sdlc_readonly_guard"] = guard
        try:
            guard._INSTALLED = True
            with self.assertRaises(recover.Refusal) as refused:
                recover.refuse_read_only_guard()
            self.assertIn("already installed the read-only guard", str(refused.exception))
            # Positive control: the same check passes when the guard is not installed.
            guard._INSTALLED = False
            self.assertIsNone(recover.refuse_read_only_guard())
        finally:
            sys.modules.pop("_ccodex_sdlc_readonly_guard", None)

    def test_an_interrupted_apply_reports_an_unknown_effect_at_exit_four(self) -> None:
        original = recover.run

        def interrupted(argv, ledger, **kwargs):
            ledger["moved"] = True
            raise KeyboardInterrupt()

        def clean(argv, ledger, **kwargs):
            raise KeyboardInterrupt()

        try:
            recover.run = interrupted
            self.assertEqual(recover.main(["--apply", FOREIGN_DIGEST]), 4)
            # Positive control: the SAME interrupt before anything moved is a clean refusal, so the
            # exit 4 above is the recorded effect and not the exception's type.
            recover.run = clean
            self.assertEqual(recover.main(["--apply", FOREIGN_DIGEST]), 3)
        finally:
            recover.run = original

    def test_a_module_returning_no_admitted_exit_class_reads_as_an_unknown_effect(self) -> None:
        original = recover.run
        captured = io.StringIO()
        try:
            recover.run = lambda argv, ledger, **kwargs: (True, ["a bool is not an exit class"])
            with contextlib.redirect_stdout(captured):
                self.assertIs(recover.main(["--apply", FOREIGN_DIGEST]), True)
        finally:
            recover.run = original
        # The dispatcher, not the module, is what refuses a non-int class, and it does so by name.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = root / "shadow"
            (shadow / "scripts").mkdir(parents=True)
            (shadow / "policy").mkdir()
            for relative in (
                "policy/ccodex-sdlc-read-report.v1.json",
                "policy/release-contract.v1.json",
                "scripts/ccodex_sdlc.py",
                "scripts/ccodex_sdlc_readonly.py",
                "scripts/install_operator_tools.py",
                "scripts/install_skill_bundle.py",
            ):
                shutil.copy2(ROOT / relative, shadow / relative)
            (shadow / "scripts" / "ccodex_sdlc_recover.py").write_text(
                "def main(argv):\n    return True\n", encoding="utf-8"
            )
            completed = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(shadow / "scripts" / "ccodex_sdlc.py"),
                    "recover",
                    "--apply",
                    FOREIGN_DIGEST,
                ],
                env={"HOME": str(root / "home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 4, completed.stderr)
            self.assertIn(
                "ccodex sdlc recover --apply returned no admitted exit class", completed.stderr
            )

    def test_an_absent_module_refuses_the_apply_form_by_its_own_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shadow = root / "shadow"
            (shadow / "scripts").mkdir(parents=True)
            (shadow / "policy").mkdir()
            for relative in (
                "policy/ccodex-sdlc-read-report.v1.json",
                "policy/release-contract.v1.json",
                "scripts/ccodex_sdlc.py",
                "scripts/ccodex_sdlc_readonly.py",
                "scripts/install_operator_tools.py",
                "scripts/install_skill_bundle.py",
            ):
                shutil.copy2(ROOT / relative, shadow / relative)
            completed = subprocess.run(
                [
                    str(Path(sys.executable)),
                    "-I",
                    "-B",
                    str(shadow / "scripts" / "ccodex_sdlc.py"),
                    "recover",
                    "--apply",
                    FOREIGN_DIGEST,
                ],
                env={"HOME": str(root / "home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 3, completed.stderr)
            self.assertIn(
                "ccodex sdlc recover --apply is unavailable in this distribution", completed.stderr
            )
            self.assertIn("ccodex_sdlc_recover.py", completed.stderr)
            self.assertEqual(completed.stdout, "")

    def test_a_journal_that_moved_between_approval_and_lock_refuses_inside_the_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _dispatcher, environment = self.make_dispatcher(root)
            destination, journal = self.plant_finalizable_transaction(root, environment)
            config = bundle.Config(
                ROOT,
                Path(environment["HOME"]),
                Path(environment["CODEX_HOME"]),
                "auto",
                False,
                "all",
                Path(environment["XDG_STATE_HOME"]),
            )
            plan = {
                "items": [{"component": "bundle", "path": "bundle-transaction://claude/skill/1"}],
                "journal": [
                    {
                        "component": "bundle",
                        "digest": "0" * 64,
                        "locator": "journal://bundle/state",
                        "state": "present",
                    }
                ],
            }
            ledger = {"moved": False}
            with self.assertRaises(recover.Refusal) as refused:
                recover.resume_bundle(bundle, config, plan, ledger)
            self.assertIn("changed between the approval and the lock", str(refused.exception))
            self.assertFalse(ledger["moved"])
            # Positive control: the same call with the journal's real digest recorded proceeds.
            plan["journal"][0]["digest"] = hashlib.sha256(journal.read_bytes()).hexdigest()
            messages, partial = recover.resume_bundle(bundle, config, plan, ledger)
            self.assertTrue(ledger["moved"])
            self.assertFalse(partial, messages)
            self.assertEqual(
                json.loads(journal.read_text(encoding="utf-8"))["transactions"], {}
            )
            self.assertIn(str(destination), json.loads(journal.read_text(encoding="utf-8"))["entries"])

    def test_an_operator_tools_state_swapped_between_derivation_and_the_lock_refuses(self) -> None:
        """``resume_operator_tools`` mirrors ``resume_bundle``'s own lock-time byte recheck.

        The plan derived at T0 records the operator-tools journal's exact digest. If the live state
        moves AFTER that derivation and BEFORE the lock is taken at T1, the mismatch is refused by
        name rather than acted on -- the same race ``resume_bundle`` already declines for the bundle
        journal (agentic-sdlc-cd9f).
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _dispatcher, environment = self.make_dispatcher(root)
            state, command = self.plant_operator_tools_pending(environment, live=None)
            operator_config = operator_tools.Config(
                ROOT,
                Path(environment["HOME"]),
                Path(environment["XDG_BIN_HOME"]),
                Path(environment["XDG_STATE_HOME"]),
                False,
                False,
            )
            before = state.read_bytes()
            plan = {
                "items": [{"component": "operator-tools", "path": str(command)}],
                "journal": [
                    {
                        "component": "operator-tools",
                        "digest": hashlib.sha256(before).hexdigest(),
                        "locator": "journal://operator-tools/state",
                        "state": "present",
                    }
                ],
            }
            real_lock = operator_tools.lifecycle_lock

            @contextlib.contextmanager
            def swap_then_lock(config):
                # The race this recheck defends against: the plan was derived over ``before``, and
                # the live state moves AFTER that derivation but BEFORE the lock is taken here.
                state.write_bytes(before + b"\n")
                with real_lock(config):
                    yield

            ledger = {"moved": False}
            with mock.patch.object(operator_tools, "lifecycle_lock", swap_then_lock):
                with self.assertRaises(recover.Refusal) as refused:
                    recover.resume_operator_tools(operator_tools, operator_config, plan, ledger)
            self.assertIn("changed between the approval and the lock", str(refused.exception))
            self.assertFalse(ledger["moved"])
            # Nothing was touched beyond the planted swap itself.
            self.assertEqual(state.read_bytes(), before + b"\n")
            self.assertFalse(command.exists())

            # Positive control: with the state UNSWAPPED, the exact same plan resumes under the real
            # lock, so the refusal above is the recheck and not an inability to resume at all.
            state.write_bytes(before)
            messages, partial = recover.resume_operator_tools(
                operator_tools, operator_config, plan, ledger
            )
            self.assertTrue(ledger["moved"])
            self.assertFalse(partial, messages)
            self.assertIn("operator-tools: recovered abort:", messages[0])
            document = json.loads(state.read_text(encoding="utf-8"))
            self.assertIsNone(document["pending"])
            self.assertEqual(document["entries"], {})

    def test_the_reader_maps_the_apply_form_onto_its_own_named_module(self) -> None:
        self.assertEqual(
            reader.lifecycle_module_path("recover"),
            ROOT / "scripts" / "ccodex_sdlc_recover.py",
        )
        self.assertEqual(sorted(reader.LIFECYCLE_VERBS), ["install", "uninstall", "update"])
        self.assertEqual(
            sorted(reader.LIFECYCLE_MODULES), ["install", "recover", "uninstall", "update"]
        )
        self.assertEqual(reader.RECOVERY_PLAN_SCHEMA, recover.PLAN_SCHEMA)


class RecoveryPlanLineTests(RecoverApplyHarness):
    """``recovery_plan_line`` must render the handled ``unavailable`` line, never a traceback, when
    the optional recovery-plan sibling lies about its own return shape (agentic-sdlc-cd9f)."""

    def line_for(self, root: Path, derive_plan) -> str:
        adapters = (None, operator_tools, bundle)

        def fake_load_recovery_planner(script_path: Path, guard: object) -> tuple[object, None]:
            planner = type("LyingPlanner", (), {"derive_plan": staticmethod(derive_plan)})()
            return planner, None

        with mock.patch.object(reader, "load_recovery_planner", fake_load_recovery_planner):
            return reader.recovery_plan_line(root, adapters)

    def test_a_schema_lying_planner_yields_the_handled_unavailable_line_never_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for lying in (
                # A ``plan`` that is not a mapping at all: ``plan["items"]`` would raise TypeError.
                lambda **kwargs: ("not-a-plan-dict", "d" * 64),
                # A ``plan`` dict whose ``items`` is present but not a list.
                lambda **kwargs: ({"items": "not-a-list"}, "d" * 64),
                # A ``plan`` dict with no ``items`` key at all: ``plan["items"]`` would raise KeyError.
                lambda **kwargs: ({}, "d" * 64),
            ):
                with self.subTest(lying=lying):
                    line = self.line_for(root, lying)
                    self.assertIn("recovery plan: unavailable", line)
                    self.assertNotIn("Traceback", line)

            # Positive control: the SAME harness, given an honestly-shaped plan, renders the real
            # digest line rather than the unavailable fallback -- the guard above is catching the
            # lying shape and not swallowing every plan.
            honest_digest = "e" * 64
            line = self.line_for(
                root, lambda **kwargs: ({"items": [{"component": "bundle", "path": "x"}]}, honest_digest)
            )
            self.assertEqual(
                f"recovery plan sha256 {honest_digest}: approve exactly this plan with"
                f" `ccodex sdlc recover {reader.RECOVER_APPLY_FLAG} {honest_digest}`\n",
                line,
            )


if __name__ == "__main__":
    unittest.main()
