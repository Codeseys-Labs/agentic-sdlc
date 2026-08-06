from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from scripts import activation_planner as ap


SCRIPT = ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py"


def git(target: Path, *args: str) -> None:
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_CONFIG_GLOBAL": "/dev/null", "LC_ALL": "C", "LANG": "C"})
    subprocess.run(["git", "-C", str(target), *args], check=True, capture_output=True, env=environment)


def init_repo(target: Path) -> None:
    git(target, "init", "-b", "main")
    git(target, "config", "user.name", "test")
    git(target, "config", "user.email", "test@example.invalid")
    (target / "tracked.txt").write_text("tracked\n")
    git(target, "add", "tracked.txt")
    git(target, "commit", "-m", "seed")


def manifest(path: str = "AGENTS.md") -> dict:
    return {
        "schema": "agentic-sdlc/instruction-manifest@2",
        "marker": {"start": "<!-- agentic-sdlc:start -->", "end": "<!-- agentic-sdlc:end -->"},
        "doctrine_pointer": "literal only",
        "outputs": [{"path": path, "kind": "root_agents", "prefix": "", "sections": [{"key": "intent", "body": "exact"}]}],
    }


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class ActivationTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))
        self.plan_file = Path(self.tmp.name) / "plan.json"

    def plan(self) -> dict:
        plan, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, plan)
        self.plan_file.write_bytes(ap.canonical_bytes(plan["plan"]))
        return plan["plan"]

    def grant(self, plan: dict, *, expired: bool = False) -> Path:
        instant = now()
        serial = getattr(self, "grant_serial", 0)
        self.grant_serial = serial + 1
        grant = {
            "schema": ap.GRANT_SCHEMA,
            "grant_id": ("f" if expired else "1") * 31 + ("e" if expired else format(serial, "x")),
            "operation": "apply",
            "target": {"path": str(self.target), "root_dev": self.target.stat().st_dev, "root_ino": self.target.stat().st_ino},
            "plan_digest": ap.digest_record(plan),
            "operation_id": None,
            "operation_digest": None,
            "decision": None,
            "issued_at": stamp(instant - timedelta(minutes=20) if expired else instant),
            "expires_at": stamp(instant - timedelta(minutes=1) if expired else instant + timedelta(minutes=5)),
        }
        path = Path(self.tmp.name) / ("expired.json" if expired else "grant.json")
        path.write_bytes(ap.canonical_bytes(grant))
        return path

    def apply(self, plan: dict, **kwargs) -> tuple[dict, int]:
        return ap.apply_command(self.plan_file, self.manifest, self.grant(plan, **kwargs))

    def _stage_crash(self, target: Path, manifest_path: Path, plan_path: Path, grant_path: Path) -> dict:
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(manifest_path), "--grant", str(grant_path),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="stage"))
        self.assertEqual(crashed.returncode, 97)
        operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
        operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
        progress, _ = ap.load_canonical_json(operation_dir / "progress.json", "progress")
        self.assertIsNotNone(progress["staged_custody"])
        self.assertEqual(progress["staged_custody"], ap.custody_identity(progress["staged_identity"]))
        staged, staged_identity = ap.read_stable_file(operation_dir / "stage" / "0000.payload", "staged")
        self.assertEqual(staged_identity, progress["staged_identity"])
        self.assertEqual(len(staged), operation["entry"]["desired"]["size"])
        self.assertEqual(staged_identity["sha256"], operation["entry"]["desired"]["sha256"])
        inspected, code = ap.recover_inspect_command(target)
        self.assertEqual(code, 3, inspected)
        self.assertEqual(inspected["legal_recovery"], ["finish", "rollback"])
        self.assertEqual(inspected["operation"]["operation_id"], operation["operation_id"])
        return operation

    def test_stage_crash_durably_binds_custody_and_fresh_finish_or_rollback(self) -> None:
        for decision in ("finish", "rollback"):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                instant = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("a" if decision == "finish" else "b") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                grant_path = root / "apply-grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                operation = self._stage_crash(target, manifest_path, plan_path, grant_path)
                recovery = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("c" if decision == "finish" else "d") * 32,
                    "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": decision,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                recovery_path = root / "recovery.json"
                recovery_path.write_bytes(ap.canonical_bytes(recovery))
                result, code = (ap.recover_finish_command if decision == "finish" else ap.recover_rollback_command)(target, recovery_path)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["status"], "committed" if decision == "finish" else "rolled-back")
                if decision == "finish":
                    self.assertTrue((target / "AGENTS.md").is_file())
                else:
                    self.assertFalse((target / "AGENTS.md").exists())

    def test_recovery_inspect_rejects_legacy_staged_witness_without_durable_custody(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="stage"))
        self.assertEqual(crashed.returncode, 97)
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        progress, _ = ap.load_canonical_json(operation_dir / "progress.json", "progress")
        progress["staged_identity"] = None
        progress["staged_custody"] = None
        operation_path = operation_dir / "operation.json"
        operation, _ = ap.load_canonical_json(operation_path, "operation")
        progress["sequence"] += 1
        operation_dir.joinpath("progress.json").write_bytes(ap.canonical_bytes(progress))

        inspected, code = ap.recover_inspect_command(self.target)

        self.assertEqual(code, 4, inspected)
        self.assertEqual(inspected["status"], "effect-unknown")
        self.assertTrue((operation_dir / "stage" / "0000.payload").exists())
        self.assertEqual(operation["operation_id"], operation_dir.name)

    def test_create_publication_rejects_substituted_stage_and_restores_witness(self) -> None:
        plan = self.plan()
        operation = {"value": None}
        external = Path(self.tmp.name) / "external-create-stage"
        external.write_bytes(b"EXTERNAL SUBSTITUTION\n")
        globals_ = ap.publish_create.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def substitute_before_move(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "0000.payload" and destination == "AGENTS.md":
                injected = True
                stage_path = Path(os.readlink(f"/proc/self/fd/{source_fd}")) / source
                os.replace(external, stage_path)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = substitute_before_move
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertFalse((self.target / "AGENTS.md").exists())
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        self.assertEqual((operation_dir / "stage" / "0000.payload").read_bytes(), b"EXTERNAL SUBSTITUTION\n")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_replace_publication_rejects_substituted_stage_and_restores_witness(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        external = Path(self.tmp.name) / "external-replace-stage"
        external.write_bytes(b"EXTERNAL SUBSTITUTION\n")
        globals_ = ap.publish_replace.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def substitute_before_exchange(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "0000.payload" and destination == "AGENTS.md" and flags == 2:
                injected = True
                stage_path = Path(os.readlink(f"/proc/self/fd/{source_fd}")) / source
                os.replace(external, stage_path)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = substitute_before_exchange
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.read_bytes(), b"# original\n")
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        self.assertEqual((operation_dir / "stage" / "0000.payload").read_bytes(), b"EXTERNAL SUBSTITUTION\n")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_status_final_observation_rejects_private_namespace_substitution(self) -> None:
        for component in ("operation", "operation.json", "stage", "backup", "discard"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                instant = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "e" * 31 + format(("operation", "operation.json", "stage", "backup", "discard").index(component), "x"),
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                grant_path = root / "grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                result, code = ap.apply_command(plan_path, manifest_path, grant_path)
                self.assertEqual(code, 0, result)
                operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
                outside = root / f"outside-{component}"
                outside.mkdir()
                victim = outside / "victim"
                victim.write_bytes(b"outside final-status victim\n")
                globals_ = ap.status_command.__globals__
                original = globals_["_validate_terminal_live_binding"]
                injected = False

                def substitute_after_live(active_target: Path, operation: dict, commit: dict, receipt: dict) -> None:
                    nonlocal injected
                    original(active_target, operation, commit, receipt)
                    path = operation_dir if component == "operation" else operation_dir / component
                    retained = operation_dir.with_name(operation_dir.name + ".retained") if component == "operation" else operation_dir / f"{component}.retained"
                    os.rename(path, retained)
                    path.symlink_to(outside if component != "operation.json" else victim, target_is_directory=component != "operation.json")
                    injected = True

                globals_["_validate_terminal_live_binding"] = substitute_after_live
                try:
                    status, status_code = ap.status_command(target)
                finally:
                    globals_["_validate_terminal_live_binding"] = original

                self.assertTrue(injected)
                self.assertEqual(status_code, 4, status)
                self.assertEqual(status["status"], "effect-unknown")
                self.assertEqual(victim.read_bytes(), b"outside final-status victim\n")

    def test_terminal_status_rejects_live_product_drift(self) -> None:
        plan = self.plan()
        result, code = self.apply(plan)
        self.assertEqual(code, 0, result)

        (self.target / "AGENTS.md").write_text("replaced after commit\n")

        status, code = ap.status_command(self.target)
        self.assertEqual(code, 4, status)
        self.assertEqual(status["status"], "effect-unknown")

    def test_forged_root_anchor_remains_foreign_git_state(self) -> None:
        forged = self.target / (".agentic-sdlc.intent." + "0" * 32 + ".json")
        forged.write_text("{}\n")
        os.chmod(forged, 0o600)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        visible = subprocess.run(["git", "-C", str(self.target), "status", "--porcelain=v2", "-z"], check=True, capture_output=True, env=environment).stdout
        self.assertIn(forged.name.encode() + b"\0", visible)

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_crash_after_publish_rolls_back_create_and_replace(self) -> None:
        for existing in (None, b"# original\n"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                if existing is not None:
                    output = target / "AGENTS.md"
                    output.write_bytes(existing)
                    git(target, "add", "AGENTS.md")
                    git(target, "commit", "-m", "original")
                input_manifest = root / "manifest.json"
                input_manifest.write_bytes(ap.canonical_bytes(manifest()))
                planned, code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                instant = now()
                apply_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("3" if existing is None else "4") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                apply_grant_path = root / "apply-grant.json"
                apply_grant_path.write_bytes(ap.canonical_bytes(apply_grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(input_manifest), "--grant", str(apply_grant_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
                self.assertEqual(crashed.returncode, 97)
                inspected, inspect_code = ap.recover_inspect_command(target)
                self.assertEqual(inspect_code, 3, inspected)
                self.assertIn("rollback", inspected["legal_recovery"])
                operation = inspected["operation"]
                recovery_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("5" if existing is None else "6") * 32,
                    "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": "rollback",
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                recovery_path = root / "rollback-grant.json"
                recovery_path.write_bytes(ap.canonical_bytes(recovery_grant))
                rolled_back, rollback_code = ap.recover_rollback_command(target, recovery_path)
                self.assertEqual(rollback_code, 0, rolled_back)
                self.assertEqual(rolled_back["status"], "rolled-back")
                output = target / "AGENTS.md"
                self.assertEqual(output.exists(), existing is not None)
                if existing is not None:
                    self.assertEqual(output.read_bytes(), existing)
                baseline = ap.capture_git_observation(target)
                self.assertEqual(baseline["porcelain_v2_z_base64"], "")
                transaction = target / ".agentic-sdlc" / "transactions" / operation["operation_id"]
                self.assertEqual(list((transaction / "stage").iterdir()), [])
                discard = transaction / "discard" / "0000.payload"
                self.assertTrue(discard.is_file())
                _, discarded_identity = ap.read_stable_file(discard, "retained rollback discard")
                self.assertEqual(discarded_identity["sha256"], operation["entry"]["desired"]["sha256"])
                if existing is None:
                    self.assertEqual(list((transaction / "backup").iterdir()), [])
                else:
                    self.assertEqual(list((transaction / "backup").iterdir()), [])
                status, status_code = ap.status_command(target)
                self.assertEqual(status_code, 0, status)
                self.assertEqual(status["status"], "inactive")
                inspect, inspect_code = ap.recover_inspect_command(target)
                self.assertEqual(inspect_code, 0, inspect)
                self.assertEqual(inspect["status"], "inactive")
                replay, replay_code = ap.recover_rollback_command(target, recovery_path)
                self.assertEqual(replay_code, 1, replay)
                self.assertEqual(replay["status"], "refused")

    def test_hostile_git_environment_cannot_redirect_product_observation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "repo"
            target.mkdir()
            init_repo(target)
            input_manifest = root / "manifest.json"
            input_manifest.write_bytes(ap.canonical_bytes(manifest()))
            hostile = dict(os.environ)
            hostile.update({
                "GIT_DIR": str(target / ".git" / "not-a-repository"),
                "GIT_WORK_TREE": str(root),
                "GIT_INDEX_FILE": str(root / "hostile.index"),
                "GIT_CONFIG_GLOBAL": str(root / "hostile.gitconfig"),
                "GIT_CONFIG_SYSTEM": str(root / "hostile-system.gitconfig"),
                "GIT_CEILING_DIRECTORIES": "/",
                "GIT_OBJECT_DIRECTORY": str(root / "hostile-objects"),
                "GIT_ALTERNATE_OBJECT_DIRECTORIES": str(root / "hostile-alternates"),
            })
            completed = subprocess.run([
                sys.executable, str(SCRIPT), "plan", "--target", str(target), "--manifest", str(input_manifest), "--entry", "AGENTS.md",
            ], check=False, capture_output=True, env=hostile)

        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "planned")

    def test_happy_create_status_and_noop_audit(self) -> None:
        plan = self.plan()
        result, code = self.apply(plan)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "committed")
        output = self.target / "AGENTS.md"
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o644)
        receipts = list((self.target / ".agentic-sdlc" / "receipts").glob("*.json"))
        self.assertEqual(len(receipts), 1)

        no_op = self.plan()
        self.assertEqual(no_op["entries"], [])
        result, code = self.apply(no_op)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "no-op")
        self.assertEqual(len(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json"))), 1)
        self.assertEqual(len(list(self.target.glob(".agentic-sdlc.noop.*.json"))), 1)

    def test_grant_replay_and_expiry_are_refused(self) -> None:
        plan = self.plan()
        result, code = self.apply(plan, expired=True)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "refused")
        grant = self.grant(plan)
        result, code = ap.apply_command(self.plan_file, self.manifest, grant)
        self.assertEqual(code, 0)
        result, code = ap.apply_command(self.plan_file, self.manifest, grant)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "refused")

    def test_strict_json_and_substitution_rejected_before_anchor(self) -> None:
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text('{"schema":"agentic-sdlc/instruction-manifest@2", "x":1}\n')
        result, code = ap.plan_command(self.target, bad, "AGENTS.md")
        self.assertEqual(code, 2)
        plan = self.plan()
        changed = manifest()
        changed["outputs"][0]["sections"][0]["body"] = "changed"
        self.manifest.write_bytes(ap.canonical_bytes(changed))
        result, code = self.apply(plan)
        self.assertEqual(code, 1)
        self.assertFalse(any(self.target.glob(".agentic-sdlc.intent.*")))

    def test_primary_clean_index_and_unsafe_paths_refused(self) -> None:
        index = self.target / ".git" / "index"
        before = index.read_bytes()
        self.plan()
        self.assertEqual(index.read_bytes(), before)
        (self.target / "outside").symlink_to("/tmp")
        bad_manifest = Path(self.tmp.name) / "bad-parent.json"
        bad_manifest.write_bytes(ap.canonical_bytes(manifest("outside/x.md")))
        result, code = ap.plan_command(self.target, bad_manifest, "outside/x.md")
        self.assertEqual(code, 1)
        self.assertIn(result["status"], {"refused", "unsupported"})
        (self.target / "outside").unlink()
        (self.target / "untracked").write_text("no\n")
        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "refused")

    def test_replace_uses_cas_and_prestate_substitution_is_stale(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_text("# existing\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "existing")
        plan = self.plan()
        output.write_text("changed outside transaction\n")
        result, code = self.apply(plan)
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(output.read_text(), "changed outside transaction\n")

    def test_crash_recovery_finish_rollback_and_unknown_preserves_witnesses(self) -> None:
        plan = self.plan()
        env = dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish")
        completed = subprocess.run([sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan))], env=env)
        self.assertEqual(completed.returncode, 97)
        inspected, code = ap.recover_inspect_command(self.target)
        self.assertEqual(code, 3, inspected)
        operation = inspected["operation"]
        recovery = self._recovery_grant(operation, "finish")
        result, code = ap.recover_finish_command(self.target, recovery)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "committed")

        # An unexpected witness has no safe automatic outcome and is retained.
        (self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"] / "stage" / "foreign").write_text("foreign")
        inspected, code = ap.recover_inspect_command(self.target)
        self.assertEqual(code, 4)
        self.assertTrue((self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"] / "stage" / "foreign").exists())

    def test_symlinked_private_receipts_are_refused_without_outside_write(self) -> None:
        plan = self.plan()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        state = self.target / ".agentic-sdlc"
        state.mkdir(mode=0o700)
        (state / "receipts").symlink_to(outside, target_is_directory=True)

        result, code = self.apply(plan)

        self.assertEqual(code, 1, result)
        self.assertIn(result["status"], {"foreign-state", "refused"})
        self.assertEqual(list(outside.iterdir()), [])

    def test_generator_symlink_is_refused_before_any_marker_executes(self) -> None:
        tool_dir = Path(self.tmp.name) / "tools"
        tool_dir.mkdir()
        planner = tool_dir / "activation-planner.py"
        planner.write_bytes((ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py").read_bytes())
        marker = Path(self.tmp.name) / "generator-executed"
        attacker = Path(self.tmp.name) / "attacker.py"
        attacker.write_text(f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n")
        (tool_dir / "instruction-generator.py").symlink_to(attacker)
        planner_globals = ap._load_generator.__globals__
        previous = planner_globals["__file__"]
        planner_globals["__file__"] = str(planner)
        try:
            with self.assertRaises(ap.ActivationError):
                ap._load_generator()
        finally:
            planner_globals["__file__"] = previous
        self.assertFalse(marker.exists())

    def test_commit_receipt_and_cleanup_crashes_require_finish(self) -> None:
        for failpoint in ("commit", "receipt", "cleanup"):
            with self.subTest(failpoint=failpoint), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                input_manifest = root / "manifest.json"
                input_manifest.write_bytes(ap.canonical_bytes(manifest()))
                planned, code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                instant = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("a" if failpoint == "commit" else "b" if failpoint == "receipt" else "c") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                grant_path = root / "grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(input_manifest), "--grant", str(grant_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT=failpoint))
                self.assertEqual(crashed.returncode, 97)
                inspected, inspection_code = ap.recover_inspect_command(target)
                self.assertEqual(inspection_code, 3, inspected)
                self.assertEqual(inspected["legal_recovery"], ["finish"])
                operation = inspected["operation"]
                recovery = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("d" if failpoint == "commit" else "e" if failpoint == "receipt" else "f") * 32,
                    "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": "finish",
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                recovery_path = root / "recovery.json"
                recovery_path.write_bytes(ap.canonical_bytes(recovery))
                completed, finish_code = ap.recover_finish_command(target, recovery_path)
                self.assertEqual(finish_code, 0, completed)
                self.assertEqual(completed["status"], "committed")

    def test_recovery_rejects_tampered_operation_before_classification(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        operation_path = next((self.target / ".agentic-sdlc" / "transactions").glob("*/operation.json"))
        operation, _ = ap.load_canonical_json(operation_path, "operation")
        operation["unexpected"] = True
        operation_path.write_bytes(ap.canonical_bytes(operation))

        result, code = ap.recover_inspect_command(self.target)

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")

    def test_post_publish_unrelated_change_is_effect_unknown_without_receipt(self) -> None:
        plan = self.plan()
        original = ap.write_commit
        planner_globals = original.__globals__

        def inject(operation_dir: Path, operation: dict, poststate: dict, target: Path) -> dict:
            (self.target / "external-change").write_text("outside transaction\n")
            return original(operation_dir, operation, poststate, target)

        planner_globals["write_commit"] = inject
        try:
            result, code = self.apply(plan)
        finally:
            planner_globals["write_commit"] = original

        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_mount_boundary_is_refused_when_second_mount_is_available(self) -> None:
        mount_root = Path("/dev/shm")
        if not mount_root.is_dir() or os.stat(mount_root).st_dev == os.stat("/").st_dev:
            self.skipTest("no second mount fixture")
        with tempfile.TemporaryDirectory(dir=mount_root) as directory:
            target = Path(directory) / "repo"
            target.mkdir()
            init_repo(target)
            result, code = ap.plan_command(target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "unsupported")

    def test_malformed_rollback_witness_is_effect_unknown_not_terminal(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        rollback = operation_dir / "rollback.json"
        rollback.write_bytes(ap.canonical_bytes({}))
        os.chmod(rollback, 0o600)

        status, status_code = ap.status_command(self.target)
        inspected, inspect_code = ap.recover_inspect_command(self.target)

        self.assertEqual(status_code, 4, status)
        self.assertEqual(status["status"], "effect-unknown")
        self.assertEqual(inspect_code, 4, inspected)
        self.assertEqual(inspected["status"], "effect-unknown")
        self.assertTrue((self.target / "AGENTS.md").exists())

    def test_malformed_receipt_stays_visible_and_blocks_private_state_admission(self) -> None:
        state = self.target / ".agentic-sdlc"
        receipts = state / "receipts"
        state.mkdir(mode=0o700)
        receipts.mkdir(mode=0o700)
        os.chmod(state, 0o700)
        os.chmod(receipts, 0o700)
        receipt = receipts / ("7" * 32 + ".json")
        receipt.write_bytes(ap.canonical_bytes({"schema": ap.RECEIPT_SCHEMA}))
        os.chmod(receipt, 0o600)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        visible = subprocess.run([
            "git", "-C", str(self.target), "status", "--porcelain=v2", "-z",
        ], check=True, capture_output=True, env=environment).stdout

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertIn(b"? .agentic-sdlc/\0", visible)
        self.assertNotEqual(code, 0, result)
        self.assertIn(result["status"], {"foreign-state", "effect-unknown"})

    def test_new_apply_refuses_create_and_replace_while_publish_recovery_is_active(self) -> None:
        for existing in (None, b"# original\n"):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                if existing is not None:
                    output = target / "AGENTS.md"
                    output.write_bytes(existing)
                    git(target, "add", "AGENTS.md")
                    git(target, "commit", "-m", "original")
                input_manifest = root / "manifest.json"
                input_manifest.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                first_plan = planned["plan"]
                first_plan_path = root / "first-plan.json"
                first_plan_path.write_bytes(ap.canonical_bytes(first_plan))
                instant = now()
                first_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("8" if existing is None else "9") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(first_plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                first_grant_path = root / "first-grant.json"
                first_grant_path.write_bytes(ap.canonical_bytes(first_grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(first_plan_path), "--manifest", str(input_manifest), "--grant", str(first_grant_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
                self.assertEqual(crashed.returncode, 97)

                changed = manifest()
                changed["outputs"][0]["sections"][0]["body"] = "second operation"
                input_manifest.write_bytes(ap.canonical_bytes(changed))
                second, second_code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(second_code, 0, second)
                second_plan = second["plan"]
                second_plan_path = root / "second-plan.json"
                second_plan_path.write_bytes(ap.canonical_bytes(second_plan))
                second_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("a" if existing is None else "b") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(second_plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                second_grant_path = root / "second-grant.json"
                second_grant_path.write_bytes(ap.canonical_bytes(second_grant))

                result, code = ap.apply_command(second_plan_path, input_manifest, second_grant_path)

                self.assertEqual(code, 3, result)
                self.assertEqual(result["status"], "recovery-required")
                transactions = list((target / ".agentic-sdlc" / "transactions").iterdir())
                self.assertEqual(len(transactions), 1)
                self.assertEqual(list((target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_replace_publication_mismatch_restores_external_writer_and_preserves_witnesses(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        globals_ = ap.publish_replace.__globals__
        original = globals_["_renameat2_at"]
        external = Path(self.tmp.name) / "external-publish"
        external.write_bytes(b"external publication\n")
        injected = False

        def replace_before_exchange(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and flags == 2 and destination == "AGENTS.md":
                injected = True
                os.replace(external, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_before_exchange
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.read_bytes(), b"external publication\n")
        operation = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        self.assertFalse((operation / "commit.json").exists())
        self.assertEqual(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json")), [])
        self.assertTrue((operation / "stage" / "0000.payload").exists())

    def test_replace_rollback_mismatch_restores_external_writer_without_rollback_record(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        globals_ = ap.rollback_replace.__globals__
        original = globals_["_renameat2_at"]
        external = Path(self.tmp.name) / "external-rollback"
        external.write_bytes(b"external rollback\n")
        injected = False

        def replace_before_exchange(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and flags == 2 and source == "AGENTS.md":
                injected = True
                os.replace(external, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_before_exchange
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.read_bytes(), b"external rollback\n")
        operation_dir = self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"]
        self.assertFalse((operation_dir / "rollback.json").exists())
        self.assertTrue((operation_dir / "backup" / "0000.payload").exists())

    def test_transaction_directory_symlink_swap_preserves_outside_victim(self) -> None:
        plan = self.plan()
        outside = Path(self.tmp.name) / "outside-transaction"
        outside.mkdir()
        victim = outside / "operation.json"
        victim.write_bytes(b"outside operation witness\n")
        for name in ("grants", "stage", "backup", "discard"):
            (outside / name).mkdir()
        globals_ = ap._make_layout.__globals__
        original = globals_["_mkdir_new_at"]
        swapped = False

        def swap_after_private_layout(parent_fd: int, name: str) -> int:
            nonlocal swapped
            fd = original(parent_fd, name)
            if not swapped and name == "discard":
                operation_dir = Path(os.readlink(f"/proc/self/fd/{parent_fd}"))
                swapped = True
                shutil.rmtree(operation_dir)
                operation_dir.symlink_to(outside, target_is_directory=True)
            return fd

        globals_["_mkdir_new_at"] = swap_after_private_layout
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_mkdir_new_at"] = original

        self.assertTrue(swapped)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(victim.read_bytes(), b"outside operation witness\n")

    def test_cleanup_directory_symlink_swap_preserves_outside_victim(self) -> None:
        plan = self.plan()
        outside = Path(self.tmp.name) / "outside-cleanup"
        outside.mkdir()
        victim = outside / "victim"
        victim.write_bytes(b"outside cleanup victim\n")
        globals_ = ap._commit_operation.__globals__
        original = globals_["publish_receipt"]
        swapped = False

        def swap_before_cleanup(operation_dir: Path, operation: dict, commit: dict, target: Path) -> dict:
            nonlocal swapped
            receipt = original(operation_dir, operation, commit, target)
            backup = operation_dir / "backup"
            os.rmdir(backup)
            backup.symlink_to(outside, target_is_directory=True)
            swapped = True
            return receipt

        globals_["publish_receipt"] = swap_before_cleanup
        try:
            result, code = self.apply(plan)
        finally:
            globals_["publish_receipt"] = original

        self.assertTrue(swapped)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(victim.read_bytes(), b"outside cleanup victim\n")
        self.assertEqual(len(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json"))), 1)

    def test_receipt_publication_rechecks_live_product_before_terminal_success(self) -> None:
        plan = self.plan()
        external = Path(self.tmp.name) / "external-after-receipt"
        external.write_bytes(b"external bytes after receipt\n")
        globals_ = ap._commit_operation.__globals__
        original = globals_["publish_receipt"]
        injected = False

        def replace_after_receipt(operation_dir: Path, operation: dict, commit: dict, target: Path) -> dict:
            nonlocal injected
            receipt = original(operation_dir, operation, commit, target)
            os.replace(external, self.target / "AGENTS.md")
            injected = True
            return receipt

        globals_["publish_receipt"] = replace_after_receipt
        try:
            result, code = self.apply(plan)
        finally:
            globals_["publish_receipt"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), b"external bytes after receipt\n")
        operation = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        progress, _ = ap.load_canonical_json(operation / "progress.json", "progress")
        self.assertNotEqual(progress["phase"], "committed")

    def test_create_rollback_restores_finite_external_replacement(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        output = self.target / "AGENTS.md"
        external = Path(self.tmp.name) / "external-create-rollback"
        external.write_bytes(b"external create rollback\n")
        globals_ = ap._renameat2_at.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def replace_before_discard(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "AGENTS.md" and destination == "0000.payload":
                injected = True
                os.replace(external, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_before_discard
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.read_bytes(), b"external create rollback\n")
        operation_dir = self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"]
        self.assertFalse((operation_dir / "rollback.json").exists())

    def test_same_content_create_rollback_substitution_preserves_external_inode(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        output = self.target / "AGENTS.md"
        external = Path(self.tmp.name) / "same-content-create"
        external.write_bytes(output.read_bytes())
        external_ino = external.stat().st_ino
        globals_ = ap.rollback_create.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def replace_before_discard(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "AGENTS.md" and destination == "0000.payload":
                injected = True
                os.replace(external, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_before_discard
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.stat().st_ino, external_ino)
        self.assertFalse((self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"] / "rollback.json").exists())

    def test_same_content_replace_rollback_substitution_preserves_external_inode(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        external = Path(self.tmp.name) / "same-content-replace"
        external.write_bytes(output.read_bytes())
        external_ino = external.stat().st_ino
        globals_ = ap.rollback_replace.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def replace_before_exchange(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and flags == 2 and source == "AGENTS.md":
                injected = True
                os.replace(external, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_before_exchange
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.stat().st_ino, external_ino)
        self.assertFalse((self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"] / "rollback.json").exists())

    def test_receipt_directory_swap_during_finish_preserves_external_directory(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="receipt"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        receipts = self.target / ".agentic-sdlc" / "receipts"
        outside = Path(self.tmp.name) / "outside-receipts"
        outside.mkdir()
        victim = outside / "receipt-victim"
        victim.write_bytes(b"external receipt victim\n")
        moved = receipts.with_name("receipts-retained")
        globals_ = ap._validate_recovery_grant.__globals__
        original = globals_["_consume_grant"]
        swapped = False

        def swap_after_grant(operation_dir: Path, grant: dict, target: Path) -> None:
            nonlocal swapped
            original(operation_dir, grant, target)
            os.rename(receipts, moved)
            receipts.symlink_to(outside, target_is_directory=True)
            swapped = True

        globals_["_consume_grant"] = swap_after_grant
        try:
            result, code = ap.recover_finish_command(self.target, self._recovery_grant(operation, "finish"))
        finally:
            globals_["_consume_grant"] = original

        self.assertTrue(swapped)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(victim.read_bytes(), b"external receipt victim\n")
        self.assertEqual(list(outside.glob("*.json")), [])

    def test_terminal_namespace_substitutions_are_not_successful(self) -> None:
        for component in ("stage", "backup", "discard", "operation.json"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                input_manifest = root / "manifest.json"
                input_manifest.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                transaction_plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(transaction_plan))
                instant = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "e" * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(transaction_plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                grant_path = root / "grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                outside = root / f"outside-{component}"
                outside.mkdir()
                victim = outside / "victim"
                victim.write_bytes(b"outside terminal victim\n")
                globals_ = ap._commit_operation.__globals__
                original = globals_["publish_receipt"]
                swapped = False

                def swap_before_terminal(operation_dir: Path, operation: dict, commit: dict, active_target: Path) -> dict:
                    nonlocal swapped
                    receipt = original(operation_dir, operation, commit, active_target)
                    path = operation_dir / component
                    retained = operation_dir / f"{component}.retained"
                    os.rename(path, retained)
                    if component == "operation.json":
                        path.symlink_to(victim)
                    else:
                        path.symlink_to(outside, target_is_directory=True)
                    swapped = True
                    return receipt

                globals_["publish_receipt"] = swap_before_terminal
                try:
                    result, code = ap.apply_command(plan_path, input_manifest, grant_path)
                finally:
                    globals_["publish_receipt"] = original

                self.assertTrue(swapped)
                self.assertEqual(code, 4, result)
                self.assertEqual(result["status"], "effect-unknown")
                self.assertEqual(victim.read_bytes(), b"outside terminal victim\n")

    def test_porcelain_v2_paths_with_spaces_are_exact_and_do_not_hide_unrelated_changes(self) -> None:
        tracked_record = b"1 .M N... 100644 100644 100644 0123456789012345678901234567890123456789 0123456789012345678901234567890123456789 tracked AGENTS.md"
        rename_record = b"2 R. N... 100644 100644 100644 0123456789012345678901234567890123456789 0123456789012345678901234567890123456789 R100 renamed AGENTS.md"
        raw = tracked_record + b"\0? untracked AGENTS.md\0! ignored AGENTS.md\0" + rename_record + b"\0original AGENTS.md\0"
        parsed = ap.parse_porcelain_v2_z(raw)
        self.assertEqual(parsed[0].paths, (b"tracked AGENTS.md",))
        self.assertEqual(parsed[1].paths, (b"untracked AGENTS.md",))
        self.assertEqual(parsed[2].paths, (b"ignored AGENTS.md",))
        self.assertEqual(parsed[3].paths, (b"renamed AGENTS.md", b"original AGENTS.md"))

        for tracked in (True, False):
            with self.subTest(tracked=tracked), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                unrelated = target / ("tracked AGENTS.md" if tracked else "untracked AGENTS.md")
                if tracked:
                    unrelated.write_bytes(b"baseline\n")
                    git(target, "add", unrelated.name)
                    git(target, "commit", "-m", "track space path")
                input_manifest = root / "manifest.json"
                input_manifest.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, input_manifest, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                transaction_plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(transaction_plan))
                instant = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("c" if tracked else "d") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(transaction_plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
                }
                grant_path = root / "grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                globals_ = ap._commit_operation.__globals__
                original = globals_["write_commit"]

                def mutate_unrelated(operation_dir: Path, operation: dict, poststate: dict, current_target: Path) -> dict:
                    unrelated.write_bytes(b"mutated after publish\n")
                    return original(operation_dir, operation, poststate, current_target)

                globals_["write_commit"] = mutate_unrelated
                try:
                    result, code = ap.apply_command(plan_path, input_manifest, grant_path)
                finally:
                    globals_["write_commit"] = original

                self.assertEqual(code, 4, result)
                self.assertEqual(result["status"], "effect-unknown")
                self.assertEqual(list((target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_consumed_apply_grant_remains_recoverable_after_expiry(self) -> None:
        for decision in ("finish", "rollback"):
            with self.subTest(decision=decision), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                issued = now()
                apply_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("a" if decision == "finish" else "b") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                apply_path = root / "apply.json"
                apply_path.write_bytes(ap.canonical_bytes(apply_grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(manifest_path), "--grant", str(apply_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
                self.assertEqual(crashed.returncode, 97)
                operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
                operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
                advanced = issued + timedelta(minutes=6)

                class AdvancedDateTime(datetime):
                    @classmethod
                    def now(cls, tz=None):
                        return advanced if tz is not None else advanced.replace(tzinfo=None)

                globals_ = ap._validate_private_state.__globals__
                original_datetime = globals_["datetime"]
                globals_["datetime"] = AdvancedDateTime
                try:
                    inspected, inspect_code = ap.recover_inspect_command(target)
                    self.assertEqual(inspect_code, 3, inspected)
                    self.assertIn(decision, inspected["legal_recovery"])
                    recovery = {
                        "schema": ap.GRANT_SCHEMA, "grant_id": ("c" if decision == "finish" else "d") * 32,
                        "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                        "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": decision,
                        "issued_at": stamp(advanced), "expires_at": stamp(advanced + timedelta(minutes=5)),
                    }
                    recovery_path = root / "recovery.json"
                    recovery_path.write_bytes(ap.canonical_bytes(recovery))
                    result, code = (ap.recover_finish_command if decision == "finish" else ap.recover_rollback_command)(target, recovery_path)
                finally:
                    globals_["datetime"] = original_datetime
                self.assertEqual(code, 0, result)
                self.assertEqual(result["status"], "committed" if decision == "finish" else "rolled-back")

    def test_recover_finish_preserves_unbound_backup_after_stale_replace_publication(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        external = Path(self.tmp.name) / "external-backup"
        external.write_bytes(b"external backup payload\n")
        external_inode = external.stat().st_ino
        globals_ = ap.publish_replace.__globals__
        original = globals_["_renameat2_at"]
        injected = False

        def substitute_before_backup(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "0000.payload" and destination == "0000.payload" and flags == 1:
                injected = True
                backup_path = Path(os.readlink(f"/proc/self/fd/{destination_fd}")) / destination
                os.replace(external, backup_path)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = substitute_before_backup
        try:
            stale, stale_code = self.apply(plan)
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(stale_code, 1, stale)
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
        backup = operation_dir / "backup" / "0000.payload"
        self.assertEqual(backup.stat().st_ino, external_inode)
        self.assertEqual(backup.read_bytes(), b"external backup payload\n")
        result, code = ap.recover_finish_command(self.target, self._recovery_grant(operation, "finish"))
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(backup.stat().st_ino, external_inode)
        self.assertEqual(backup.read_bytes(), b"external backup payload\n")

    def test_cleanup_live_replacement_never_returns_committed(self) -> None:
        plan = self.plan()
        external = Path(self.tmp.name) / "external-during-cleanup"
        external.write_bytes(b"external cleanup replacement\n")
        globals_ = ap._commit_operation.__globals__
        original = globals_["_cleanup_private_artifacts"]
        injected = False

        def replace_after_cleanup(operation_dir: Path, operation: dict, target: Path) -> None:
            nonlocal injected
            original(operation_dir, operation, target)
            os.replace(external, target / "AGENTS.md")
            injected = True

        globals_["_cleanup_private_artifacts"] = replace_after_cleanup
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_cleanup_private_artifacts"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), b"external cleanup replacement\n")

    def test_status_rejects_regular_operation_and_record_replacements(self) -> None:
        for component in ("operation", "operation.json"):
            with self.subTest(component=component), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                issued = now()
                grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": ("e" if component == "operation" else "f") * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                grant_path = root / "grant.json"
                grant_path.write_bytes(ap.canonical_bytes(grant))
                applied, applied_code = ap.apply_command(plan_path, manifest_path, grant_path)
                self.assertEqual(applied_code, 0, applied)
                operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
                replacement = root / f"replacement-{component}"
                if component == "operation":
                    shutil.copytree(operation_dir, replacement, copy_function=shutil.copy2)
                    for copied in replacement.rglob("*"):
                        os.chmod(copied, 0o700 if copied.is_dir() else 0o600)
                    os.chmod(replacement, 0o700)
                else:
                    shutil.copy2(operation_dir / "operation.json", replacement)
                    os.chmod(replacement, 0o600)
                globals_ = ap.status_command.__globals__
                original = globals_["_operation_dirs"]
                injected = False

                def replace_after_admission(active_target: Path, binding=None):
                    nonlocal injected
                    directories = original(active_target, binding)
                    if not injected:
                        injected = True
                        if component == "operation":
                            retained = operation_dir.with_name(operation_dir.name + ".retained")
                            os.rename(operation_dir, retained)
                            os.rename(replacement, operation_dir)
                        else:
                            os.replace(replacement, operation_dir / "operation.json")
                    return directories

                globals_["_operation_dirs"] = replace_after_admission
                try:
                    status, status_code = ap.status_command(target)
                finally:
                    globals_["_operation_dirs"] = original

                self.assertTrue(injected)
                self.assertEqual(status_code, 4, status)
                self.assertEqual(status["status"], "effect-unknown")

    def test_terminal_seal_preserves_substituted_backup_and_refuses_committed_status(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        external = Path(self.tmp.name) / "external-sealed-backup"
        external.write_bytes(b"external backup substitution\n")
        external_inode = external.stat().st_ino
        globals_ = ap._cleanup_private_artifacts.__globals__
        original = globals_["_private_payload_at"]
        injected = False

        def substitute_after_custody(parent_fd: int, name: str, private, label: str):
            nonlocal injected
            raw, identity = original(parent_fd, name, private, label)
            if not injected and name == "0000.payload" and label == "sealed terminal backup":
                injected = True
                os.replace(external, Path(os.readlink(f"/proc/self/fd/{parent_fd}")) / name)
            return raw, identity

        globals_["_private_payload_at"] = substitute_after_custody
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_private_payload_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        backup = operation_dir / "backup" / "0000.payload"
        self.assertEqual(backup.stat().st_ino, external_inode)
        self.assertEqual(backup.read_bytes(), b"external backup substitution\n")
        status, status_code = ap.status_command(self.target)
        self.assertNotEqual(status_code, 0, status)
        self.assertNotEqual(status["status"], "committed")

    def test_replace_apply_retains_receipt_bound_sealed_backup(self) -> None:
        output = self.target / "AGENTS.md"
        original_bytes = b"# original\n"
        output.write_bytes(original_bytes)
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()

        result, code = self.apply(plan)

        self.assertEqual(code, 0, result)
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
        commit, _ = ap.load_canonical_json(operation_dir / "commit.json", "commit")
        receipt, _ = ap.load_canonical_json(self.target / ".agentic-sdlc" / "receipts" / f"{operation['operation_id']}.json", "receipt")
        progress, _ = ap.load_canonical_json(operation_dir / "progress.json", "progress")
        backup = operation_dir / "backup" / "0000.payload"
        _, identity = ap.read_stable_file(backup, "sealed backup")
        self.assertEqual(backup.read_bytes(), original_bytes)
        self.assertEqual(backup.stat().st_nlink, 1)
        self.assertEqual(commit["terminal_evidence"]["backup"]["identity"], identity)
        self.assertEqual(receipt["terminal_evidence"], commit["terminal_evidence"])
        self.assertEqual(progress["terminal_evidence"], commit["terminal_evidence"])
        self.assertIsNone(commit["terminal_evidence"]["discard"])
        self.assertEqual(list((operation_dir / "stage").iterdir()), [])
        self.assertEqual(list((operation_dir / "discard").iterdir()), [])
        status, status_code = ap.status_command(self.target)
        self.assertEqual(status_code, 0, status)
        self.assertEqual(status["status"], "committed")

    def test_terminal_status_rejects_retained_backup_substitution(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        applied, applied_code = self.apply(plan)
        self.assertEqual(applied_code, 0, applied)
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        backup = operation_dir / "backup" / "0000.payload"
        replacement = Path(self.tmp.name) / "same-content-external-backup"
        replacement.write_bytes(backup.read_bytes())
        replacement_inode = replacement.stat().st_ino
        os.replace(replacement, backup)

        status, status_code = ap.status_command(self.target)

        self.assertEqual(status_code, 4, status)
        self.assertEqual(status["status"], "effect-unknown")
        self.assertEqual(backup.stat().st_ino, replacement_inode)

    def test_create_rollback_retains_exact_discarded_desired_evidence(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]

        result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))

        self.assertEqual(code, 0, result)
        operation_dir = self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"]
        rollback, _ = ap.load_canonical_json(operation_dir / "rollback.json", "rollback")
        progress, _ = ap.load_canonical_json(operation_dir / "progress.json", "progress")
        discard = operation_dir / "discard" / "0000.payload"
        _, identity = ap.read_stable_file(discard, "sealed discarded payload")
        self.assertEqual(discard.stat().st_nlink, 1)
        self.assertEqual(identity["mode"], operation["entry"]["desired"]["mode"])
        self.assertEqual(identity["size"], operation["entry"]["desired"]["size"])
        self.assertEqual(identity["sha256"], operation["entry"]["desired"]["sha256"])
        self.assertEqual(rollback["terminal_evidence"]["discard"]["identity"], identity)
        self.assertEqual(progress["terminal_evidence"], rollback["terminal_evidence"])
        status, status_code = ap.status_command(self.target)
        self.assertEqual(status_code, 0, status)
        self.assertEqual(status["status"], "inactive")

    def test_replace_rollback_retains_exact_discarded_desired_evidence(self) -> None:
        output = self.target / "AGENTS.md"
        output.write_bytes(b"# original\n")
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "original")
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]

        result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))

        self.assertEqual(code, 0, result)
        operation_dir = self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"]
        rollback, _ = ap.load_canonical_json(operation_dir / "rollback.json", "rollback")
        progress, _ = ap.load_canonical_json(operation_dir / "progress.json", "progress")
        discard = operation_dir / "discard" / "0000.payload"
        _, identity = ap.read_stable_file(discard, "sealed discarded payload")
        self.assertEqual(discard.stat().st_nlink, 1)
        self.assertEqual(identity["mode"], operation["entry"]["desired"]["mode"])
        self.assertEqual(identity["size"], operation["entry"]["desired"]["size"])
        self.assertEqual(identity["sha256"], operation["entry"]["desired"]["sha256"])
        self.assertEqual(rollback["terminal_evidence"]["discard"]["identity"], identity)
        self.assertEqual(progress["terminal_evidence"], rollback["terminal_evidence"])
        status, status_code = ap.status_command(self.target)
        self.assertEqual(status_code, 0, status)
        self.assertEqual(status["status"], "inactive")

    def test_progress_successor_substitution_preserves_temp_and_refuses_effect_unknown(self) -> None:
        plan = self.plan()
        operation_dir = self.target / ".agentic-sdlc" / "transactions"
        external = Path(self.tmp.name) / "substituted-progress.json"
        external.write_bytes(b'{"substituted":true}\n')
        globals_ = ap.write_progress.__globals__
        original = globals_["_write_new_at"]
        injected = False

        def substitute_before_progress_rename(parent_fd: int, name: str, record: dict) -> tuple[bytes, dict]:
            nonlocal injected
            written = original(parent_fd, name, record)
            if not injected and name == "progress.json.next":
                injected = True
                temp = Path(os.readlink(f"/proc/self/fd/{parent_fd}")) / name
                os.replace(external, temp)
            return written

        globals_["_write_new_at"] = substitute_before_progress_rename
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_write_new_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        directory = next(operation_dir.iterdir())
        progress, _ = ap.load_canonical_json(directory / "progress.json", "progress")
        self.assertEqual(progress["phase"], "setup")
        self.assertEqual((directory / "progress.json.next").read_bytes(), b'{"substituted":true}\n')
        self.assertFalse((directory / "commit.json").exists())

    def test_rollback_terminal_progress_rechecks_finite_live_replacement(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        external = Path(self.tmp.name) / "external-after-rollback-progress"
        external.write_bytes(b"external live replacement after terminal progress\n")
        globals_ = ap.write_progress.__globals__
        original = globals_["write_progress"]
        injected = False

        def replace_after_terminal_progress(operation_dir: Path, progress: dict, target: Path | None = None) -> None:
            nonlocal injected
            original(operation_dir, progress, target)
            if progress["phase"] == "rolled-back":
                injected = True
                os.replace(external, self.target / "AGENTS.md")

        globals_["write_progress"] = replace_after_terminal_progress
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["write_progress"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual((self.target / "AGENTS.md").read_bytes(), b"external live replacement after terminal progress\n")

    def test_committed_owner_refuses_different_effectful_successor_without_supersession(self) -> None:
        first_plan = self.plan()
        first_result, first_code = self.apply(first_plan)
        self.assertEqual(first_code, 0, first_result)
        first_status, first_status_code = ap.status_command(self.target)
        self.assertEqual(first_status_code, 0, first_status)
        self.assertEqual(first_status["status"], "committed")
        self.assertEqual(first_status["operation_id"], first_result["operation_id"])

        changed = manifest()
        changed["outputs"][0]["sections"][0]["body"] = "different exact content"
        self.manifest.write_bytes(ap.canonical_bytes(changed))
        second, second_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(second_code, 1, second)
        self.assertEqual(second["status"], "unsupported")
        self.assertEqual(len(list((self.target / ".agentic-sdlc" / "transactions").iterdir())), 1)
        final_status, final_status_code = ap.status_command(self.target)
        self.assertEqual(final_status_code, 0, final_status)
        self.assertEqual(final_status["status"], "committed")
        self.assertEqual(final_status["operation_id"], first_result["operation_id"])

    def test_create_rollback_preserves_newest_finite_replacement_and_retains_first(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        output = self.target / "AGENTS.md"
        first = Path(self.tmp.name) / "first-live-replacement"
        second = Path(self.tmp.name) / "second-live-replacement"
        first.write_bytes(b"first finite replacement A\n")
        second.write_bytes(b"second finite replacement B\n")
        first_inode = first.stat().st_ino
        second_inode = second.stat().st_ino
        globals_ = ap.rollback_create.__globals__
        original = globals_["_renameat2_at"]
        moves = 0

        def replace_twice(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal moves
            if source == "AGENTS.md" and destination == "0000.payload":
                moves += 1
                os.replace(first, output)
            elif source == "0000.payload" and destination == "AGENTS.md" and flags == 1:
                moves += 1
                os.replace(second, output)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = replace_twice
        try:
            result, code = ap.recover_rollback_command(self.target, self._recovery_grant(operation, "rollback"))
        finally:
            globals_["_renameat2_at"] = original

        self.assertEqual(moves, 2)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(output.stat().st_ino, second_inode)
        self.assertEqual(output.read_bytes(), b"second finite replacement B\n")
        discard = self.target / ".agentic-sdlc" / "transactions" / operation["operation_id"] / "discard" / "0000.payload"
        self.assertEqual(discard.stat().st_ino, first_inode)
        self.assertEqual(discard.read_bytes(), b"first finite replacement A\n")
        self.assertFalse((discard.parent.parent / "rollback.json").exists())

    def test_progress_destination_substitution_survives_and_never_commits(self) -> None:
        plan = self.plan()
        globals_ = ap.write_progress.__globals__
        original = globals_["_renameat2_at"]
        injected = False
        expected_foreign = {"raw": b""}

        def substitute_destination_before_exchange(source_fd: int, source: str, destination_fd: int, destination: str, flags: int) -> None:
            nonlocal injected
            if not injected and source == "progress.json.next" and destination == "progress.json" and flags == 2:
                injected = True
                current_raw, _ = ap._read_stable_at(destination_fd, destination, "current progress")
                foreign = ap._canonical_load_bytes(current_raw, "current progress")
                foreign["reasons"] = ["foreign destination witness"]
                expected_foreign["raw"] = ap.canonical_bytes(foreign)
                foreign_path = Path(self.tmp.name) / "foreign-progress-destination"
                foreign_path.write_bytes(expected_foreign["raw"])
                os.chmod(foreign_path, 0o600)
                os.replace(foreign_path, Path(os.readlink(f"/proc/self/fd/{destination_fd}")) / destination)
            original(source_fd, source, destination_fd, destination, flags)

        globals_["_renameat2_at"] = substitute_destination_before_exchange
        try:
            result, code = self.apply(plan)
        finally:
            globals_["_renameat2_at"] = original

        self.assertTrue(injected)
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
        self.assertEqual((operation_dir / "progress.json").read_bytes(), expected_foreign["raw"])
        successor, _ = ap.load_canonical_json(operation_dir / "progress.json.next", "successor")
        self.assertEqual(successor["phase"], "staged")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json")), [])

    def test_missing_or_malformed_active_progress_is_effect_unknown_without_consuming_recovery_grant(self) -> None:
        for tamper in ("missing", "malformed"):
            with self.subTest(tamper=tamper), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                issued = now()
                apply_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "a" * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                apply_path = root / "apply.json"
                apply_path.write_bytes(ap.canonical_bytes(apply_grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(manifest_path), "--grant", str(apply_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="stage"))
                self.assertEqual(crashed.returncode, 97)
                operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
                operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
                progress = operation_dir / "progress.json"
                if tamper == "missing":
                    progress.unlink()
                else:
                    progress.write_bytes(b"{not canonical}\n")
                    os.chmod(progress, 0o600)
                recovery = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "b" * 32,
                    "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": "finish",
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                recovery_path = root / "recovery.json"
                recovery_path.write_bytes(ap.canonical_bytes(recovery))

                status, status_code = ap.status_command(target)
                inspect, inspect_code = ap.recover_inspect_command(target)
                result, code = ap.recover_finish_command(target, recovery_path)

                self.assertEqual(status_code, 4, status)
                self.assertEqual(status["status"], "effect-unknown")
                self.assertEqual(inspect_code, 4, inspect)
                self.assertEqual(inspect["status"], "effect-unknown")
                self.assertEqual(code, 4, result)
                self.assertEqual(result["status"], "effect-unknown")
                self.assertEqual(sorted(item.name for item in (operation_dir / "grants").iterdir()), ["0001.json"])

    def test_terminal_progress_tuple_tampering_is_never_terminal(self) -> None:
        committed_mutations = {
            "direction": "rollback",
            "effect": "effect_unknown",
            "receipt_state": "absent",
        }
        for field, replacement in committed_mutations.items():
            with self.subTest(terminal="committed", field=field):
                plan = self.plan()
                result, code = self.apply(plan)
                self.assertEqual(code, 0, result)
                operation_dir = next((self.target / ".agentic-sdlc" / "transactions").iterdir())
                progress_path = operation_dir / "progress.json"
                progress, _ = ap.load_canonical_json(progress_path, "progress")
                progress[field] = replacement
                progress_path.write_bytes(ap.canonical_bytes(progress))
                os.chmod(progress_path, 0o600)

                status, status_code = ap.status_command(self.target)
                inspected, inspect_code = ap.recover_inspect_command(self.target)

                self.assertEqual(status_code, 4, status)
                self.assertEqual(status["status"], "effect-unknown")
                self.assertEqual(inspect_code, 4, inspected)
                self.assertEqual(inspected["status"], "effect-unknown")
                progress_path.write_bytes(ap.canonical_bytes({**progress, field: {"direction": "apply", "effect": "committed", "receipt_state": "published"}[field]}))

        rolled_back_mutations = {
            "direction": "apply",
            "effect": "committed",
            "receipt_state": "published",
        }
        for field, replacement in rolled_back_mutations.items():
            with self.subTest(terminal="rolled-back", field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "repo"
                target.mkdir()
                init_repo(target)
                manifest_path = root / "manifest.json"
                manifest_path.write_bytes(ap.canonical_bytes(manifest()))
                planned, plan_code = ap.plan_command(target, manifest_path, "AGENTS.md")
                self.assertEqual(plan_code, 0, planned)
                plan = planned["plan"]
                plan_path = root / "plan.json"
                plan_path.write_bytes(ap.canonical_bytes(plan))
                issued = now()
                apply_grant = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "c" * 32,
                    "operation": "apply", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                apply_path = root / "apply.json"
                apply_path.write_bytes(ap.canonical_bytes(apply_grant))
                crashed = subprocess.run([
                    sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(manifest_path), "--grant", str(apply_path),
                ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
                self.assertEqual(crashed.returncode, 97)
                operation_dir = next((target / ".agentic-sdlc" / "transactions").iterdir())
                operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
                recovery = {
                    "schema": ap.GRANT_SCHEMA, "grant_id": "d" * 32,
                    "operation": "recover", "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
                    "plan_digest": None, "operation_id": operation["operation_id"], "operation_digest": ap.digest_record(operation), "decision": "rollback",
                    "issued_at": stamp(issued), "expires_at": stamp(issued + timedelta(minutes=5)),
                }
                recovery_path = root / "recovery.json"
                recovery_path.write_bytes(ap.canonical_bytes(recovery))
                rolled_back, rollback_code = ap.recover_rollback_command(target, recovery_path)
                self.assertEqual(rollback_code, 0, rolled_back)
                progress_path = operation_dir / "progress.json"
                progress, _ = ap.load_canonical_json(progress_path, "progress")
                progress[field] = replacement
                progress_path.write_bytes(ap.canonical_bytes(progress))
                os.chmod(progress_path, 0o600)

                status, status_code = ap.status_command(target)
                inspected, inspect_code = ap.recover_inspect_command(target)

                self.assertEqual(status_code, 4, status)
                self.assertEqual(status["status"], "effect-unknown")
                self.assertEqual(inspect_code, 4, inspected)
                self.assertEqual(inspected["status"], "effect-unknown")

    def _recovery_grant(self, operation: dict, decision: str) -> Path:
        instant = now()
        grant = {
            "schema": ap.GRANT_SCHEMA,
            "grant_id": "2" * 32,
            "operation": "recover",
            "target": {"path": str(self.target), "root_dev": self.target.stat().st_dev, "root_ino": self.target.stat().st_ino},
            "plan_digest": None,
            "operation_id": operation["operation_id"],
            "operation_digest": ap.digest_record(operation),
            "decision": decision,
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        path = Path(self.tmp.name) / "recovery.json"
        path.write_bytes(ap.canonical_bytes(grant))
        return path


if __name__ == "__main__":
    unittest.main()
