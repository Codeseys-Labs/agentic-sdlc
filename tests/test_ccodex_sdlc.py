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


ROOT = Path(__file__).parents[1]
OPERATOR_SCRIPT = ROOT / "scripts" / "install_operator_tools.py"
spec = importlib.util.spec_from_file_location("ccodex_sdlc_operator_tools", OPERATOR_SCRIPT)
assert spec and spec.loader
operator_tools = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = operator_tools
spec.loader.exec_module(operator_tools)

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


class CcodexSdlcTests(unittest.TestCase):
    def make_shadow_reader(self, root: Path) -> Path:
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

    def make_dispatcher(self, root: Path) -> tuple[Path, dict[str, str], Path]:
        runtime = root / "runtime"
        runtime.mkdir()
        for name in ("ocx", "jq", "uv"):
            executable = runtime / name
            executable.write_text("#!/bin/sh\nexit 0\n")
            executable.chmod(0o755)
        install_home = root / "install-home"
        config = operator_tools.Config(
            ROOT,
            install_home,
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

    def operator_state_path(self, environment: dict[str, str]) -> Path:
        return Path(environment["XDG_STATE_HOME"]) / "agentic-sdlc-operator-tools" / "state.json"

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

    def test_inspect_json_is_a_read_only_checkout_development_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, query_state = self.make_dispatcher(Path(temp))

            completed = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertEqual(report["schema_version"], "ccodex-sdlc-read-report/v1")
            self.assertEqual(report["command"]["verb"], "inspect")
            self.assertEqual(report["checkout"]["plane"], "checkout-development")
            self.assertEqual(report["checkout"]["version"], "0.7.4")
            self.assertIsNone(report["checkout"]["public_channel"])
            self.assertEqual(report["checkout"]["certification_claim"], "none")
            self.assertTrue(report["runtime"]["isolated"])
            self.assertEqual(report["runtime"]["state"], "admitted")
            self.assertFalse(query_state.exists())

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
        with tempfile.TemporaryDirectory() as temp:
            dispatcher, environment, _query_state = self.make_dispatcher(Path(temp))
            state_path = self.operator_state_path(environment)
            command_path = Path(environment["XDG_BIN_HOME"]) / "ccodex"
            state = {
                "version": 2,
                "entries": {},
                "pending": {
                    "operation": "install",
                    "path": str(command_path),
                    "before": None,
                    "after": {
                        "path": str(command_path),
                        "digest": "0" * 64,
                        "removable": "true",
                    },
                },
            }
            state_path.parent.mkdir(parents=True)
            state_path.write_text(json.dumps(state, sort_keys=True))
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
            self.assertFalse(state_path.with_name("lock").exists())

    def test_public_reader_types_malformed_symlinked_and_foreign_operator_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            state_path = self.operator_state_path(environment)
            state_path.parent.mkdir(parents=True)
            state_path.write_text('{"version":2,"entries":{},"entries":{},"pending":null}')
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
            state_path = self.operator_state_path(environment)
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
            dispatcher, environment, query_state = self.make_dispatcher(root)
            foreign = Path(environment["XDG_BIN_HOME"]) / "ccodex"
            foreign.parent.mkdir(parents=True)
            foreign.write_text("foreign dispatcher")

            foreign_result = self.run_dispatcher(dispatcher, environment, "sdlc", "doctor", "--json")

            self.assertEqual(foreign_result.returncode, 0, foreign_result.stderr)
            foreign_report = json.loads(foreign_result.stdout)
            self.assertEqual(foreign_report["overall"]["state"], "degraded")
            self.assertIn("foreign-entry", {finding["code"] for finding in foreign_report["findings"]})
            self.assertFalse(query_state.exists())

    def test_hostile_state_values_are_redacted_from_json_and_human_reports(self) -> None:
        canaries = {
            "operator-version": "AK" + "IA" + "0" * 16,
            "operator-duplicate": "sk" + "-ant-api-duplicate-canary",
            "operator-pending": "gh" + "p_pending-canary",
            "operator-record": "xox" + "b-record-canary",
            "bundle-version": "AK" + "IA" + "1" * 16,
            "bundle-transition": "sk" + "-ant-api-transition-canary",
        }

        def operator_version(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.operator_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"version": canary, "entries": {}, "pending": None}))

        def operator_duplicate(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.operator_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(f'{{"version":2,"{canary}":"{canary}","{canary}":"{canary}"}}')

        def operator_pending(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.operator_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "version": 2,
                        "entries": {},
                        "pending": {"operation": "install", "path": canary, "before": None, "after": None},
                    }
                )
            )

        def operator_record(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.operator_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"version": 2, "entries": {canary: {}}, "pending": None}))

        def bundle_version(root: Path, environment: dict[str, str], canary: str) -> None:
            path = self.bundle_state_path(environment)
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"version": canary, "entries": {}, "pending": None}))

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
            "operator-version": operator_version,
            "operator-duplicate": operator_duplicate,
            "operator-pending": operator_pending,
            "operator-record": operator_record,
            "bundle-version": bundle_version,
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

    def test_missing_and_wrong_bound_interpreters_refuse_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, query_state = self.make_dispatcher(root)
            original = dispatcher.read_text()
            marker = "installed_sdlc_python='"
            self.assertIn(marker, original)
            missing = root / "missing-python"
            dispatcher.write_text(original.replace(f"installed_sdlc_python='{Path(sys.executable)}'", f"installed_sdlc_python='{missing}'"))
            dispatcher.chmod(0o755)

            missing_result = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")

            self.assertEqual(missing_result.returncode, 3)
            self.assertIn("ccodex sdlc Python 3.12.11 interpreter is unavailable", missing_result.stderr)
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
            dispatcher.write_text(original.replace(f"installed_sdlc_python='{Path(sys.executable)}'", f"installed_sdlc_python='{wrong}'"))
            dispatcher.chmod(0o755)

            wrong_result = self.run_dispatcher(dispatcher, environment, "sdlc", "inspect", "--json")

            self.assertEqual(wrong_result.returncode, 3, wrong_result.stderr)
            report = json.loads(wrong_result.stdout)
            self.assertEqual(report["runtime"]["state"], "refused")
            self.assertEqual(report["overall"]["exit_class"], "safe-refusal")
            self.assertIn("runtime-admission-refused", {item["code"] for item in report["findings"]})
            self.assertFalse(query_state.exists())

    def test_top_level_gateway_status_route_remains_the_gateway_route(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dispatcher, environment, _query_state = self.make_dispatcher(root)
            launcher = root / "shadow-root" / "scripts" / "opencodex-claude.sh"
            launcher.parent.mkdir(parents=True)
            launcher.write_text("#!/bin/sh\nprintf 'GATEWAY-STATUS:%s\\n' \"$1\"\n")
            launcher.chmod(0o755)
            environment["AGENTIC_SDLC_ROOT"] = str(launcher.parents[1])

            completed = self.run_dispatcher(dispatcher, environment, "status")

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, "GATEWAY-STATUS:status\n")

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

    def test_generated_dispatcher_does_not_fall_back_to_poisoned_external_tools(self) -> None:
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
    def test_generated_dispatcher_has_no_effectful_syscalls_or_external_tool_fallbacks(self) -> None:
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
                    str(dispatcher),
                    "sdlc",
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
                # Bash probes /dev/tty read/write while initializing the dispatcher. That failed
                # probe neither targets a filesystem state surface nor writes any bytes; every
                # other write-capable open remains prohibited.
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


if __name__ == "__main__":
    unittest.main()
