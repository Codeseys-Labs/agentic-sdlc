from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
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


def set_environment(case: unittest.TestCase, name: str, value: str | None) -> None:
    """Set or clear one environment variable for the duration of one test.

    Subprocess-driven cases inherit `os.environ`, so the plane selection has to live
    there rather than in a patched module global.
    """
    previous = os.environ.get(name)

    def restore() -> None:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous

    case.addCleanup(restore)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value


def use_state_plane(case: unittest.TestCase, root: Path) -> Path:
    """Point the ccodex XDG state plane inside the case's own temporary tree.

    Never inherit the operator's real `XDG_STATE_HOME`: the plane is a write
    destination, and it must share the target's filesystem.
    """
    state_home = root / "state"
    set_environment(case, "XDG_STATE_HOME", str(state_home))
    set_environment(case, ap.PLANE_SELECTION_ENV, None)
    return state_home


def plane_root(target: Path, state_home: Path | None = None) -> Path:
    """Derive the plane path independently of the engine, so layout is asserted."""
    home = Path(os.environ["XDG_STATE_HOME"]) if state_home is None else Path(state_home)
    return home / "ccodex" / "activation" / hashlib.sha256(str(target).encode("utf-8")).hexdigest()


def pointer_name(root: Path) -> str:
    """Derive the plane pointer's filename independently of the engine."""
    return f"plane.{hashlib.sha256(str(root).encode('utf-8')).hexdigest()}.json"


def plane_receipts(target: Path) -> Path:
    return plane_root(target) / "receipts"


def plane_transactions(target: Path) -> Path:
    return plane_root(target) / "transactions"


def select_repo_local_plane(case: unittest.TestCase) -> None:
    set_environment(case, ap.PLANE_SELECTION_ENV, ap.PLANE_REPO_LOCAL)


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def stamp(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


class ActivationTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_home = use_state_plane(self, Path(self.tmp.name))
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
        operation_dir = next((plane_transactions(target)).iterdir())
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
        self.assertEqual((operation_dir / "stage" / "0000.payload").read_bytes(), b"EXTERNAL SUBSTITUTION\n")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((plane_receipts(self.target)).glob("*.json")), [])

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
        operation_dir = next((plane_transactions(self.target)).iterdir())
        self.assertEqual((operation_dir / "stage" / "0000.payload").read_bytes(), b"EXTERNAL SUBSTITUTION\n")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((plane_receipts(self.target)).glob("*.json")), [])

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
                operation_dir = next((plane_transactions(target)).iterdir())
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
        """A root anchor is legacy state in the default plane, and it is still never hidden.

        The classification moved from `foreign-state` to the named legacy refusal, because
        the engine no longer writes anchors here at all; the Git-visibility assertion is
        unchanged and is what stops a forged anchor from being suppressed.
        """
        forged = self.target / (".agentic-sdlc.intent." + "0" * 32 + ".json")
        forged.write_text("{}\n")
        os.chmod(forged, 0o600)
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        visible = subprocess.run(["git", "-C", str(self.target), "status", "--porcelain=v2", "-z"], check=True, capture_output=True, env=environment).stdout
        self.assertIn(forged.name.encode() + b"\0", visible)

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn(ap.LEGACY_STATE_REASON, result["reasons"])

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
                transaction = plane_transactions(target) / operation["operation_id"]
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
        receipts = list((plane_receipts(self.target)).glob("*.json"))
        self.assertEqual(len(receipts), 1)

        no_op = self.plan()
        self.assertEqual(no_op["entries"], [])
        result, code = self.apply(no_op)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "no-op")
        self.assertEqual(len(list((plane_receipts(self.target)).glob("*.json"))), 1)
        # The no-op audit is plane state for the same reason the receipt is: it records the
        # consumed grant, the Git observation, and every existing receipt digest.
        self.assertEqual(len(list(plane_root(self.target).glob("noop.*.json"))), 1)
        # The target keeps exactly ONE machine-local file: the pointer naming the plane that
        # holds the state, which is the only witness that survives renaming this checkout. No
        # journal, no receipt, and no anchor is in the tree, which is what "the plane is not in
        # the repository" means. Both applies name the same plane, so there is one pointer.
        self.assertEqual(sorted(item.name for item in self.target.glob(".agentic-sdlc*")), [".agentic-sdlc"])
        self.assertEqual(sorted(item.name for item in (self.target / ".agentic-sdlc").iterdir()), [pointer_name(plane_root(self.target))])
        self.assertEqual(stat.S_IMODE((self.target / ".agentic-sdlc" / pointer_name(plane_root(self.target))).stat().st_mode), 0o600)

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
        (plane_transactions(self.target) / operation["operation_id"] / "stage" / "foreign").write_text("foreign")
        inspected, code = ap.recover_inspect_command(self.target)
        self.assertEqual(code, 4)
        self.assertTrue((plane_transactions(self.target) / operation["operation_id"] / "stage" / "foreign").exists())

    def test_symlinked_target_local_receipts_are_refused_without_outside_write(self) -> None:
        """`receipts/` in the worktree is legacy state now, so the refusal is by NAME.

        It is refused before any custody question is asked, which is the point: the engine
        neither adopts nor follows it, and the symlink's destination stays untouched.
        """
        plan = self.plan()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        state = self.target / ".agentic-sdlc"
        state.mkdir(mode=0o700)
        (state / "receipts").symlink_to(outside, target_is_directory=True)

        result, code = self.apply(plan)

        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn(ap.LEGACY_STATE_REASON, result["reasons"])
        self.assertTrue((state / "receipts").is_symlink())
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
        operation_path = next((plane_transactions(self.target)).glob("*/operation.json"))
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
        self.assertEqual(list((plane_receipts(self.target)).glob("*.json")), [])

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
        operation_dir = next((plane_transactions(self.target)).iterdir())
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

    def test_malformed_plane_receipt_blocks_admission_and_never_dirties_the_worktree(self) -> None:
        """A malformed receipt still blocks admission, and the plane never touches Git.

        Before the plane it had to stay VISIBLE to Git; now the receipt is not in the tree
        at all, so the invariant is the reverse one -- a foreign receipt cannot dirty the
        worktree. The untracked decoy proves the observation channel really does report
        untracked paths, so the absent `.agentic-sdlc/` record is a fact rather than a
        silent `git status` failure.
        """
        receipts = plane_receipts(self.target)
        receipts.mkdir(mode=0o700, parents=True)
        os.chmod(receipts.parent, 0o700)
        os.chmod(receipts, 0o700)
        receipt = receipts / ("7" * 32 + ".json")
        receipt.write_bytes(ap.canonical_bytes({"schema": ap.RECEIPT_SCHEMA}))
        os.chmod(receipt, 0o600)
        (self.target / "decoy-untracked.txt").write_text("decoy\n")
        environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        visible = subprocess.run([
            "git", "-C", str(self.target), "status", "--porcelain=v2", "-z",
        ], check=True, capture_output=True, env=environment).stdout

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertIn(b"? decoy-untracked.txt\0", visible)
        self.assertNotIn(b".agentic-sdlc", visible)
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
                transactions = list((plane_transactions(target)).iterdir())
                self.assertEqual(len(transactions), 1)
                self.assertEqual(list((plane_receipts(target)).glob("*.json")), [])

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
        operation = next((plane_transactions(self.target)).iterdir())
        self.assertFalse((operation / "commit.json").exists())
        self.assertEqual(list((plane_receipts(self.target)).glob("*.json")), [])
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
        operation_dir = plane_transactions(self.target) / operation["operation_id"]
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
        self.assertEqual(len(list((plane_receipts(self.target)).glob("*.json"))), 1)

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
        operation = next((plane_transactions(self.target)).iterdir())
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
        operation_dir = plane_transactions(self.target) / operation["operation_id"]
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
        self.assertFalse((plane_transactions(self.target) / operation["operation_id"] / "rollback.json").exists())

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
        self.assertFalse((plane_transactions(self.target) / operation["operation_id"] / "rollback.json").exists())

    def test_receipt_directory_swap_during_finish_preserves_external_directory(self) -> None:
        plan = self.plan()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self.plan_file), "--manifest", str(self.manifest), "--grant", str(self.grant(plan)),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="receipt"))
        self.assertEqual(crashed.returncode, 97)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        self.assertEqual(inspect_code, 3, inspected)
        operation = inspected["operation"]
        receipts = plane_receipts(self.target)
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
                self.assertEqual(list((plane_receipts(target)).glob("*.json")), [])

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
                operation_dir = next((plane_transactions(target)).iterdir())
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
        # MEASURED as exit 1 `effect: none` before this class was closed, and that was the worst
        # of the six instances because it needs no concurrent external mutation at all: the
        # replace exchange has ALREADY put the new bytes at `AGENTS.md`, and the refusal comes
        # from the following move of the exchanged prestate into an occupied `backup/`. Exit 1
        # promises an internal failure before any admitted effect. The product was live.
        self.assertEqual(stale_code, 4, stale)
        self.assertEqual(stale["status"], "effect-unknown")
        self.assertEqual(stale["effect"], "effect_unknown")
        self.assertEqual(stale["reasons"], ["publication compare-and-swap failed"], stale)
        self.assertIn("renamed 0000.payload onto AGENTS.md (flags 2)", stale["admitted_effects"], stale)
        # The effect the ledger names, observed independently of the ledger: live holds the
        # planned bytes and not the committed original, so `effect_unknown` is a statement about
        # this tree and not an artifact of the reporting change.
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), plan["entries"][0]["desired"]["sha256"])
        self.assertNotEqual(output.read_bytes(), b"# original\n")
        operation_dir = next((plane_transactions(self.target)).iterdir())
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
                operation_dir = next((plane_transactions(target)).iterdir())
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
        operation, _ = ap.load_canonical_json(operation_dir / "operation.json", "operation")
        commit, _ = ap.load_canonical_json(operation_dir / "commit.json", "commit")
        receipt, _ = ap.load_canonical_json(plane_receipts(self.target) / f"{operation['operation_id']}.json", "receipt")
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
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
        operation_dir = plane_transactions(self.target) / operation["operation_id"]
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
        operation_dir = plane_transactions(self.target) / operation["operation_id"]
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
        operation_dir = plane_transactions(self.target)
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
        self.assertEqual(len(list((plane_transactions(self.target)).iterdir())), 1)
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
        discard = plane_transactions(self.target) / operation["operation_id"] / "discard" / "0000.payload"
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
        operation_dir = next((plane_transactions(self.target)).iterdir())
        self.assertEqual((operation_dir / "progress.json").read_bytes(), expected_foreign["raw"])
        successor, _ = ap.load_canonical_json(operation_dir / "progress.json.next", "successor")
        self.assertEqual(successor["phase"], "staged")
        self.assertFalse((operation_dir / "commit.json").exists())
        self.assertEqual(list((plane_receipts(self.target)).glob("*.json")), [])

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
                operation_dir = next((plane_transactions(target)).iterdir())
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
                operation_dir = next((plane_transactions(self.target)).iterdir())
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
                operation_dir = next((plane_transactions(target)).iterdir())
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


class TrackedRepositoryManifestTests(unittest.TestCase):
    """ADR-0022 decision 2 tracks `.agentic-sdlc/repo.toml` as portable repository intent.

    The engine owns `.agentic-sdlc/` as its private namespace, so this one public tracked
    file is admitted by exact name and exact shape. Privacy stays enforced where private
    data lives: `receipts/` and `transactions/` remain strictly 0700. The state root drops
    to a no-foreign-write check because Git records no directory mode, so a fresh clone
    materializes the root at the umask default.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_home = use_state_plane(self, Path(self.tmp.name))
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))

    def _state(self) -> Path:
        state = self.target / ".agentic-sdlc"
        state.mkdir(exist_ok=True)
        return state

    def _track_manifest(self, *, body: str = "schema = 1\n", mode: int = 0o755, file_mode: int = 0o644) -> Path:
        """Modes are always set explicitly: inheriting the ambient umask made these
        cases pass at umask 022 and fail at umask 002."""
        state = self._state()
        path = state / "repo.toml"
        path.write_text(body)
        git(self.target, "add", "--force", ".agentic-sdlc/repo.toml")
        git(self.target, "commit", "-m", "repository contract manifest")
        os.chmod(path, file_mode)
        os.chmod(state, mode)
        return path

    def _plan(self) -> tuple[dict, int]:
        return ap.plan_command(self.target, self.manifest, "AGENTS.md")

    def test_tracked_manifest_is_admitted(self) -> None:
        self._track_manifest()

        result, code = self._plan()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "planned")

    def test_tracked_manifest_is_admitted_under_a_private_root(self) -> None:
        self._track_manifest(mode=0o700)

        result, code = self._plan()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "planned")

    def test_unknown_private_state_path_is_still_refused(self) -> None:
        (self._state() / "stray.json").write_text("{}\n")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_symlinked_manifest_is_refused(self) -> None:
        state = self._state()
        (state / "repo.toml").symlink_to(self.target / "tracked.txt")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_manifest_directory_is_refused(self) -> None:
        (self._state() / "repo.toml").mkdir()

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_umask_002_clone_shape_is_admitted(self) -> None:
        """Git records no mode, so a clone at umask 002 yields 0775/0664. Refusing
        group-write here refused ordinary clones on RHEL-family hosts and CI images."""
        self._track_manifest(mode=0o775, file_mode=0o664)

        result, code = self._plan()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "planned")

    def test_other_writable_state_root_is_refused(self) -> None:
        self._track_manifest(mode=0o757)

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_other_writable_manifest_is_refused(self) -> None:
        self._track_manifest(file_mode=0o646)

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_hardlinked_manifest_is_refused(self) -> None:
        """Pins st_nlink. The link must live OUTSIDE the state root: a link inside it
        trips `unknown private state path` first, so the nlink clause is never reached and
        the test passes even with that clause deleted."""
        path = self._track_manifest()
        os.link(path, self.target / "decoy-hardlink.txt")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn(f"unsafe {ap.REPO_MANIFEST_NAME}", result["reasons"])

    def test_regular_file_at_the_state_root_is_refused(self) -> None:
        """Pins the expected-type clause. Without it a file named `.agentic-sdlc` passes
        the predicate and then raises an uncaught NotADirectoryError from iterdir()."""
        (self.target / ".agentic-sdlc").write_text("not a directory\n")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe private state root", result["reasons"])

    def test_manifest_on_a_foreign_mount_is_refused(self) -> None:
        """Pins _private_identity_matches on the manifest, which a bind-mounted substitute
        inode defeats. Only non-directories get the wrong mount id, so the state root still
        passes and this fails for the manifest's own clause rather than the root's."""
        self._track_manifest()
        # `scripts/activation_planner.py` is a compat loader that copies references into
        # its own globals, so the canonical module must be patched, not the loader.
        planner = ap._module
        original = planner._mount_id_fd
        self.addCleanup(setattr, planner, "_mount_id_fd", original)
        planner._mount_id_fd = lambda fd: original(fd) + (0 if stat.S_ISDIR(os.fstat(fd).st_mode) else 1)

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn(f"unsafe {ap.REPO_MANIFEST_NAME}", result["reasons"])

    def test_extended_acl_on_the_state_root_is_refused(self) -> None:
        """Group bits double as the ACL mask, so allowing group-write means the ACL must
        be detected directly. Refused fail-closed, read-only grants included."""
        if shutil.which("setfacl") is None:
            self.skipTest("setfacl unavailable")
        self._track_manifest()
        state = self.target / ".agentic-sdlc"
        done = subprocess.run(["setfacl", "-m", f"u:{os.geteuid()}:rwx", str(state)], capture_output=True)
        if done.returncode != 0:
            self.skipTest("filesystem does not support POSIX ACLs")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")

    def test_dirty_tracked_manifest_stays_visible_to_git(self) -> None:
        """The projection must not hide the manifest, or a dirty tree passes the clean check."""
        path = self._track_manifest()
        path.write_text("schema = 1\nedited = true\n")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn("Git worktree is not clean", result["reasons"])

    def test_untracked_manifest_is_refused(self) -> None:
        """Only a tracked manifest is portable intent; an untracked one is foreign state."""
        self._state()
        (self.target / ".agentic-sdlc" / "repo.toml").write_text("schema = 1\n")

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertIn(result["status"], {"foreign-state", "refused"})


class RightsizeArtifactDirectoryTests(unittest.TestCase):
    """ADR-0015 renders its model-task-map trio into `.agentic-sdlc/rightsize/`.

    Before this carve-out the engine's closed whitelist refused every ADR-0015 output as
    `unknown private state path`, so running `/sdlc-rightsize` with its own documented
    default made activation status refuse in an already-activated repository.

    The directory is admitted as a *cloneable* node, not an exact-0700 private one, for the
    same reason ADR-0022 gave the state root and `repo.toml`: the reviewed writer creates it
    at the ambient umask (`skills/model-tier-rightsizing/scripts/rightsize.py:1829`) and Git
    records no mode, so a clone materializes 0755/0644 at umask 022 and 0775/0664 at umask
    002. It also stays VISIBLE to the Git projection, because it is a human-readable
    recommendation a reader may commit rather than machine-local private state -- unlike
    `receipts/` and `transactions/`, which `.gitignore` ignores and which keep exact 0700.

    Names inside are open, because `--output` is operator-chosen and the writer strands
    `.<name>.<pid>.tmp` siblings on a crash. Custody is not open: every node inside is proven
    non-symlink, expected-type, caller-owned, not other-writable, ACL-free, single-linked
    when a file, and on the bound mount, recursively.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_home = use_state_plane(self, Path(self.tmp.name))
        self.target = Path(self.tmp.name) / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = Path(self.tmp.name) / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))

    def _state(self, *, mode: int = 0o755) -> Path:
        """Modes are always explicit: inheriting the ambient umask makes these cases pass at
        umask 022 and fail at umask 002."""
        state = self.target / ".agentic-sdlc"
        state.mkdir(exist_ok=True)
        os.chmod(state, mode)
        return state

    def _activate(self) -> Path:
        """The already-activated shape whose refusal is the severity of this defect.

        Activation state lives in the ccodex plane now, so the activated shape is a plane
        entry beside an untouched public `.agentic-sdlc/`. That is also the coexistence
        this class exists to protect: the plane and the tracked public root are separate.
        """
        plane = plane_root(self.target)
        plane.mkdir(mode=0o700, parents=True)
        os.chmod(plane, 0o700)
        for name in ("receipts", "transactions"):
            (plane / name).mkdir(exist_ok=True)
            os.chmod(plane / name, 0o700)
        return self._state()

    def _rightsize(self, *, mode: int = 0o755, file_mode: int = 0o644, name: str = "model-task-map.json") -> Path:
        state = self._state()
        directory = state / "rightsize"
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text("{}\n")
        os.chmod(path, file_mode)
        os.chmod(directory, mode)
        return path

    def _status(self) -> tuple[dict, int]:
        """Status isolates the custody clause: it never calls `_require_clean`, so an
        untracked artifact cannot mask a `foreign-state` refusal as `refused`."""
        return ap.status_command(self.target)

    def _plan(self) -> tuple[dict, int]:
        return ap.plan_command(self.target, self.manifest, "AGENTS.md")

    def test_rightsize_artifact_in_an_activated_repository_is_admitted(self) -> None:
        self._activate()
        self._rightsize()

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_rightsize_artifact_without_activation_is_admitted(self) -> None:
        self._rightsize()

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_empty_rightsize_directory_is_admitted(self) -> None:
        directory = self._state() / "rightsize"
        directory.mkdir()
        os.chmod(directory, 0o755)

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_unknown_private_state_path_beside_rightsize_is_still_refused(self) -> None:
        """The regression guard for the carve-out's width: exactly one new name, not a hole.
        `rightsize/` present and valid must not license a sibling the engine does not own."""
        self._activate()
        self._rightsize()
        (self._state() / "junk.json").write_text("{}\n")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unknown private state path", result["reasons"])

    def test_moved_evals_name_gained_no_privilege(self) -> None:
        """Task packs moved OUT to `evaluations/` in the target. The old
        `.agentic-sdlc/evals/` spelling must stay foreign, or the move is cosmetic and the
        hand-edited corpus creeps back into the private root."""
        self._activate()
        self._rightsize()
        evals = self._state() / "evals"
        evals.mkdir()
        (evals / "change-writing-v1.json").write_text("{}\n")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unknown private state path", result["reasons"])

    def test_task_pack_custody_outside_the_private_root_does_not_affect_activation(self) -> None:
        """The payoff of the data-kind split, pinned. A task pack is the part an operator
        hand-edits most, so the exact defects that refuse inside `rightsize/` -- world-write
        and a symlink -- must be none of activation's business out here. If a later change
        widens the walk beyond the private root, this goes red."""
        self._activate()
        self._rightsize()
        packs = self.target / "evaluations"
        packs.mkdir()
        pack = packs / "change-writing-v1.json"
        pack.write_text("{}\n")
        os.chmod(pack, 0o646)
        (packs / "leak.json").symlink_to("/etc/passwd")

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_unknown_name_inside_rightsize_is_admitted(self) -> None:
        """Names inside are OPEN by decision: `--output` is operator-chosen and may name a
        subdirectory, the saved run spec is a sibling, and a crashed render strands
        `.<name>.<pid>.tmp`."""
        self._activate()
        self._rightsize(name="anything-the-operator-chose.json")
        self._rightsize(name="rightsize-run.json")
        self._rightsize(name=".model-task-map.json.4242.tmp")
        dated = self._state() / "rightsize" / "2026-08-17"
        dated.mkdir()
        (dated / "model-task-map.json").write_text("{}\n")
        os.chmod(dated / "model-task-map.json", 0o644)
        os.chmod(dated, 0o755)

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_rightsize_at_umask_002_clone_shape_is_admitted(self) -> None:
        """Pins the cloneable-mode decision. An exact-0700 rule refuses ordinary clones on
        RHEL-family hosts and CI images, and refuses what the reviewed writer itself creates."""
        self._activate()
        self._rightsize(mode=0o775, file_mode=0o664)

        result, code = self._status()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "inactive")

    def test_symlinked_rightsize_directory_is_refused(self) -> None:
        state = self._state()
        outside = Path(self.tmp.name) / "elsewhere"
        outside.mkdir()
        (state / "rightsize").symlink_to(outside)

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize", result["reasons"])

    def test_regular_file_named_rightsize_is_refused(self) -> None:
        """Pins the expected-type clause. Without it a file named `rightsize` passes the
        predicate and then raises an uncaught NotADirectoryError from iterdir()."""
        (self._state() / "rightsize").write_text("not a directory\n")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize", result["reasons"])

    def test_other_writable_rightsize_directory_is_refused(self) -> None:
        self._rightsize(mode=0o757)

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize", result["reasons"])

    def test_other_writable_artifact_inside_rightsize_is_refused(self) -> None:
        self._rightsize(file_mode=0o646)

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_symlinked_artifact_inside_rightsize_is_refused(self) -> None:
        """The load-bearing control for an open namespace: a symlink is the only way this
        subtree could redirect custody outward, and refusing it also keeps the walk loop-free."""
        self._rightsize()
        (self._state() / "rightsize" / "escape.json").symlink_to(self.target / "tracked.txt")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_hardlinked_artifact_inside_rightsize_is_refused(self) -> None:
        """Pins st_nlink. The second link lives OUTSIDE the state root, or the extra name
        inside would be walked as an ordinary admitted entry and the clause never reached."""
        path = self._rightsize()
        os.link(path, self.target / "decoy-hardlink.json")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_nested_directory_inside_rightsize_is_validated(self) -> None:
        """Pins the recursion: a bad node one level down must not be admitted because its
        parent was fine."""
        self._rightsize()
        nested = self._state() / "rightsize" / "2026-08-17"
        nested.mkdir()
        (nested / "model-task-map.json").write_text("{}\n")
        os.chmod(nested / "model-task-map.json", 0o646)
        os.chmod(nested, 0o755)

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_fifo_inside_rightsize_is_refused(self) -> None:
        """Pins the expected-type clause on artifacts: only regular files and directories."""
        self._rightsize()
        os.mkfifo(self._state() / "rightsize" / "pipe.json", 0o644)

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_extended_acl_inside_rightsize_is_refused(self) -> None:
        """Group bits double as the POSIX.1e mask, so allowing group-write means the ACL must
        be detected directly. Refused fail-closed, read-only grants included."""
        if shutil.which("setfacl") is None:
            self.skipTest("setfacl unavailable")
        path = self._rightsize()
        done = subprocess.run(["setfacl", "-m", f"u:{os.geteuid()}:rw", str(path)], capture_output=True)
        if done.returncode != 0:
            self.skipTest("filesystem does not support POSIX ACLs")

        result, code = self._status()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe rightsize artifact", result["reasons"])

    def test_uncommitted_rightsize_artifact_stays_visible_to_git(self) -> None:
        """Pins the projection decision. Hiding it would let activation proceed against a tree
        carrying an uncommitted artifact; visible means it obeys the engine's ordinary
        clean-tree rule, which the reader clears by committing or ignoring the file."""
        self._rightsize()

        result, code = self._plan()

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn("Git worktree is not clean", result["reasons"])

    def test_committed_rightsize_artifact_is_admitted_by_plan(self) -> None:
        """The artifact is tracked-capable: identical evidence re-renders byte-identically,
        which only matters for a committed file. A clean tree carrying it must still plan."""
        path = self._rightsize()
        git(self.target, "add", "--force", ".agentic-sdlc/rightsize/model-task-map.json")
        git(self.target, "commit", "-m", "rightsize model-task map")
        os.chmod(path, 0o644)
        os.chmod(path.parent, 0o755)

        result, code = self._plan()

        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "planned")


class ActivationStatePlaneTests(unittest.TestCase):
    """Receipts and recovery journals live in the ccodex XDG state plane (ADR-0018).

    A receipt binds owned paths, hashes, tool identities and trust state, which is
    operator-plane data rather than repository data, so it belongs under
    `${XDG_STATE_HOME:-~/.local/state}/ccodex/` keyed per physical clone or worktree
    (`CONTEXT.md`, product-spec Implementation Decision 11, issues/09).

    `.agentic-sdlc/` keeps exactly its tracked public surface -- `repo.toml` and
    `rightsize/` -- and every other name in it stays foreign state.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state_home = use_state_plane(self, self.root)
        self.target = self.root / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))

    def _apply(self, target: Path | None = None) -> tuple[dict, int]:
        target = self.target if target is None else target
        planned, code = ap.plan_command(target, self.manifest, "AGENTS.md")
        if code != 0:
            return planned, code
        plan = planned["plan"]
        plan_path = self.root / "plan.json"
        plan_path.write_bytes(ap.canonical_bytes(plan))
        instant = now()
        serial = getattr(self, "serial", 0)
        self.serial = serial + 1
        grant = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "3" * 31 + format(serial, "x"), "operation": "apply",
            "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
            "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        grant_path = self.root / "grant.json"
        grant_path.write_bytes(ap.canonical_bytes(grant))
        return ap.apply_command(plan_path, self.manifest, grant_path)

    def _legacy(self, *names: str) -> Path:
        state = self.target / ".agentic-sdlc"
        state.mkdir(mode=0o700, exist_ok=True)
        os.chmod(state, 0o700)
        current = state
        for name in names:
            current = current / name
            current.mkdir(mode=0o700, exist_ok=True)
            os.chmod(current, 0o700)
        return current

    def test_receipt_lands_in_the_xdg_plane_and_the_target_keeps_only_a_plane_pointer(self) -> None:
        result, code = self._apply()

        self.assertEqual(code, 0, result)
        receipts = sorted(plane_receipts(self.target).glob("*.json"))
        self.assertEqual(len(receipts), 1, receipts)
        record, _ = ap.load_canonical_json(receipts[0], "receipt")
        self.assertEqual(ap.digest_record(record), result["receipt_digest"])
        self.assertTrue((plane_transactions(self.target) / result["operation_id"] / "progress.json").is_file())
        # The receipt, the journal, and every anchor are outside the tree. What the tree keeps
        # is exactly one pointer NAMING the plane -- machine-local, 0600, and the only reason a
        # rename of this checkout cannot hide the receipt that already exists.
        self.assertEqual(sorted(item.name for item in self.target.glob(".agentic-sdlc*")), [".agentic-sdlc"])
        pointer = self.target / ".agentic-sdlc" / pointer_name(plane_root(self.target))
        self.assertEqual(sorted(item.name for item in (self.target / ".agentic-sdlc").iterdir()), [pointer.name])
        self.assertEqual(stat.S_IMODE(pointer.stat().st_mode), 0o600)
        recorded, _ = ap.load_canonical_json(pointer, "plane pointer")
        self.assertEqual(recorded, {"schema": ap.PLANE_POINTER_SCHEMA, "plane": str(plane_root(self.target))})
        # POSITIVE CONTROL for the negative assertions above: the two names the tree must NOT
        # hold are exactly the ones that exist in the plane instead.
        self.assertTrue(plane_receipts(self.target).is_dir())
        self.assertTrue(plane_transactions(self.target).is_dir())
        for name in ("receipts", "transactions"):
            self.assertFalse((self.target / ".agentic-sdlc" / name).exists())

    def test_recovery_journal_survives_removal_of_the_checkout(self) -> None:
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(self._staged_plan()), "--manifest",
            str(self.manifest), "--grant", str(self._staged_grant()),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        journal = next(plane_transactions(self.target).iterdir())
        self.assertTrue((journal / "progress.json").is_file())

        shutil.rmtree(self.target)

        self.assertFalse(self.target.exists())
        self.assertTrue((journal / "progress.json").is_file())
        progress, _ = ap.load_canonical_json(journal / "progress.json", "progress")
        self.assertEqual(progress["phase"], "staged")

    def _staged_plan(self) -> Path:
        planned, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, planned)
        self._plan_document = planned["plan"]
        path = self.root / "staged-plan.json"
        path.write_bytes(ap.canonical_bytes(planned["plan"]))
        return path

    def _staged_grant(self) -> Path:
        instant = now()
        grant = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "5" * 32, "operation": "apply",
            "target": {"path": str(self.target), "root_dev": self.target.stat().st_dev, "root_ino": self.target.stat().st_ino},
            "plan_digest": ap.digest_record(self._plan_document), "operation_id": None, "operation_digest": None,
            "decision": None, "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        path = self.root / "staged-grant.json"
        path.write_bytes(ap.canonical_bytes(grant))
        return path

    def test_plane_key_separates_sibling_checkouts_and_a_linked_worktree(self) -> None:
        sibling = self.root / "sibling"
        linked = self.target / ".worktrees" / "wave"
        keys = {ap._plane_root(self.target), ap._plane_root(sibling), ap._plane_root(linked)}

        self.assertEqual(len(keys), 3, keys)
        self.assertEqual(ap._plane_root(self.target), plane_root(self.target))
        self.assertTrue(str(ap._plane_root(self.target)).startswith(str(self.state_home / "ccodex" / "activation")))

    def test_target_local_receipts_are_refused_by_name_and_preserved(self) -> None:
        legacy = self._legacy("receipts") / ("4" * 32 + ".json")
        legacy.write_bytes(ap.canonical_bytes({"schema": ap.RECEIPT_SCHEMA}))
        os.chmod(legacy, 0o600)
        self.assertTrue(legacy.is_file())

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn(ap.LEGACY_STATE_REASON, result["reasons"])
        self.assertTrue(legacy.is_file())

    def test_target_local_transactions_are_refused_by_name_and_preserved(self) -> None:
        legacy = self._legacy("transactions", "0" * 32)
        self.assertTrue(legacy.is_dir())

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn(ap.LEGACY_STATE_REASON, result["reasons"])
        self.assertTrue(legacy.is_dir())

    def test_legacy_root_anchor_and_audit_are_refused_by_name_and_preserved(self) -> None:
        for name in (f".agentic-sdlc.intent.{'1' * 32}.json", f".agentic-sdlc.noop.{'2' * 32}.json"):
            with self.subTest(name=name):
                legacy = self.target / name
                legacy.write_bytes(ap.canonical_bytes({"schema": "legacy"}))
                os.chmod(legacy, 0o600)
                try:
                    result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

                    self.assertEqual(code, 3, result)
                    self.assertEqual(result["status"], "refused")
                    self.assertIn(ap.LEGACY_STATE_REASON, result["reasons"])
                    self.assertTrue(legacy.is_file())
                finally:
                    legacy.unlink()

    def test_repo_local_override_keeps_the_state_in_the_target(self) -> None:
        select_repo_local_plane(self)

        result, code = self._apply()

        self.assertEqual(code, 0, result)
        self.assertEqual(len(list((self.target / ".agentic-sdlc" / "receipts").glob("*.json"))), 1)
        self.assertFalse(plane_root(self.target).exists())

    def test_unknown_plane_selection_is_a_grammar_refusal(self) -> None:
        set_environment(self, ap.PLANE_SELECTION_ENV, "somewhere-else")

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 2, result)
        self.assertEqual(result["status"], "refused")

    def test_relative_state_home_is_refused_rather_than_silently_relocated(self) -> None:
        set_environment(self, "XDG_STATE_HOME", "relative/state")

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(code, 2, result)
        self.assertEqual(result["status"], "refused")

    def test_cross_device_plane_is_refused_before_any_effect(self) -> None:
        mount_root = Path("/dev/shm")
        if not mount_root.is_dir() or os.stat(mount_root).st_dev == os.stat(self.target).st_dev:
            self.skipTest("no second mount fixture")
        # Positive control: the identical operation commits on a same-device plane.
        control, control_code = self._apply()
        self.assertEqual(control_code, 0, control)
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "control")
        with tempfile.TemporaryDirectory(dir=mount_root) as foreign:
            set_environment(self, "XDG_STATE_HOME", foreign)

            result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

            self.assertEqual(code, 3, result)
            self.assertEqual(result["status"], "refused")
            self.assertIn(ap.PLANE_DEVICE_REASON, result["reasons"])
            self.assertEqual(list(Path(foreign).iterdir()), [])

    def test_symlinked_plane_receipts_are_refused_without_writing_outside(self) -> None:
        outside = self.root / "outside-plane-receipts"
        outside.mkdir()
        plane = plane_root(self.target)
        plane.mkdir(mode=0o700, parents=True)
        (plane / "receipts").symlink_to(outside, target_is_directory=True)
        # Positive control: the decoy is reachable and the identical apply succeeds once
        # the same name is an ordinary directory, so the refusal comes from the symlink
        # guard rather than from a missing path.
        result, code = self._apply()
        self.assertNotEqual(code, 0, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe private receipts", result["reasons"])
        self.assertEqual(list(outside.iterdir()), [])

        (plane / "receipts").unlink()
        (plane / "receipts").mkdir(mode=0o700)
        control, control_code = self._apply()

        self.assertEqual(control_code, 0, control)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_plane_root_is_refused_without_writing_outside(self) -> None:
        """The key directory itself is a redirect vector, not only its children.

        The refusal arrives from the ancestor walk rather than from the key directory's own
        custody check, because `O_NOFOLLOW` on the walk sees the link first. Both guards
        exist; this is the one that fires, and it fires before any effect.
        """
        outside = self.root / "outside-plane-root"
        outside.mkdir()
        plane = plane_root(self.target)
        plane.parent.mkdir(mode=0o700, parents=True)
        plane.symlink_to(outside, target_is_directory=True)

        result, code = self._apply()

        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertIn(ap.PLANE_ANCESTOR_REASON, result["reasons"])
        self.assertEqual(list(outside.iterdir()), [])
        # Positive control: the same operation commits once the name is a real directory.
        plane.unlink()
        control, control_code = self._apply()
        self.assertEqual(control_code, 0, control)
        self.assertEqual(list(outside.iterdir()), [])

    def test_plane_root_requires_exact_0700(self) -> None:
        """The engine is the only writer of the key directory, so it is held to 0700.

        The tracked `.agentic-sdlc/` cannot be, because Git materializes it at the caller's
        umask; nothing materializes this one but this engine.
        """
        result, code = self._apply()
        self.assertEqual(code, 0, result)
        plane = plane_root(self.target)
        self.assertEqual(stat.S_IMODE(plane.stat().st_mode), 0o700)
        os.chmod(plane, 0o750)

        observed, observed_code = ap.status_command(self.target)

        self.assertNotEqual(observed_code, 0, observed)
        self.assertEqual(observed["status"], "foreign-state")
        self.assertIn("unsafe private state plane", observed["reasons"])

    def test_symlinked_plane_ancestor_is_refused_before_the_plane_exists(self) -> None:
        """With no plane entry yet, the ancestor walk is the only guard there is.

        Skipping a non-`ENOENT` ancestor instead of refusing it would compare the device of
        a directory that is not the one `mkdir` would land in.
        """
        mount_root = Path("/dev/shm")
        if not mount_root.is_dir() or os.stat(mount_root).st_dev == os.stat(self.target).st_dev:
            self.skipTest("no second mount fixture")
        with tempfile.TemporaryDirectory(dir=mount_root) as foreign:
            self.state_home.mkdir(mode=0o700, parents=True)
            (self.state_home / "ccodex").symlink_to(foreign, target_is_directory=True)
            self.assertTrue((self.state_home / "ccodex").is_dir())

            result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

            self.assertEqual(code, 3, result)
            self.assertEqual(result["status"], "refused")
            self.assertIn(ap.PLANE_ANCESTOR_REASON, result["reasons"])
            self.assertEqual(list(Path(foreign).iterdir()), [])

    def test_plane_receipts_keep_the_exact_0700_rule(self) -> None:
        result, code = self._apply()
        self.assertEqual(code, 0, result)
        receipts = plane_receipts(self.target)
        self.assertEqual(stat.S_IMODE(receipts.stat().st_mode), 0o700)
        os.chmod(receipts, 0o750)

        observed, observed_code = ap.status_command(self.target)

        self.assertNotEqual(observed_code, 0, observed)
        self.assertEqual(observed["status"], "foreign-state")

    def test_shared_plane_ancestors_keep_their_operator_owned_modes(self) -> None:
        self.state_home.mkdir(mode=0o755, parents=True)
        (self.state_home / "unrelated").mkdir(mode=0o755)

        result, code = self._apply()

        self.assertEqual(code, 0, result)
        self.assertEqual(stat.S_IMODE(self.state_home.stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE((self.state_home / "unrelated").stat().st_mode), 0o755)
        self.assertEqual(stat.S_IMODE(plane_root(self.target).stat().st_mode), 0o700)

    def test_forged_plane_anchor_is_refused(self) -> None:
        """The anchor moved into the plane, so the forgery threat moved with it."""
        plane = plane_root(self.target)
        plane.mkdir(mode=0o700, parents=True)
        forged = plane / f"intent.{'0' * 32}.json"
        forged.write_text("{}\n")
        os.chmod(forged, 0o600)

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertNotEqual(code, 0, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("invalid activation anchor", result["reasons"])
        self.assertTrue(forged.is_file())

    def test_unknown_name_in_the_plane_root_is_refused(self) -> None:
        """The plane root's whitelist is as closed as the repository root's."""
        plane = plane_root(self.target)
        plane.mkdir(mode=0o700, parents=True)
        stray = plane / "stray.json"
        stray.write_text("{}\n")

        result, code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertNotEqual(code, 0, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unknown state plane path", result["reasons"])
        self.assertTrue(stray.is_file())

    def test_other_writable_plane_ancestor_is_refused(self) -> None:
        """An other-writable shared ancestor can rename this key away and substitute one.

        No mode on the key directory can prevent that, so EVERY shared ancestor is checked,
        not just the innermost. Positive control: the same tree at 0700 reports committed.
        """
        control, control_code = self._apply()
        self.assertEqual(control_code, 0, control)
        ancestors = {
            "state plane home": self.state_home,
            "state plane ccodex": self.state_home / "ccodex",
            "state plane activation": self.state_home / "ccodex" / "activation",
        }
        for label, ancestor in ancestors.items():
            with self.subTest(ancestor=label):
                clean, clean_code = ap.status_command(self.target)
                self.assertEqual(clean_code, 0, clean)
                self.assertEqual(clean["status"], "committed")
                self.assertEqual(stat.S_IMODE(ancestor.stat().st_mode), 0o700)
                os.chmod(ancestor, 0o757)
                try:
                    result, code = ap.status_command(self.target)

                    self.assertNotEqual(code, 0, result)
                    self.assertEqual(result["status"], "foreign-state")
                    self.assertIn(f"unsafe {label}", result["reasons"])
                finally:
                    os.chmod(ancestor, 0o700)

    def test_target_path_with_dot_dot_components_is_refused(self) -> None:
        indirect = Path(str(self.target.parent) + "/./repo/../repo")

        result, code = ap.plan_command(indirect, self.manifest, "AGENTS.md")

        self.assertEqual(code, 2, result)
        self.assertEqual(result["status"], "refused")


class ActivationPlaneSwitchTests(unittest.TestCase):
    """MOVING a plane must never turn an admitted partial effect into `inactive`.

    Three spellings of the same move, all covered here, because two of them were found as
    fresh instances of the first one's defect:

      * SELECTION. The plane is chosen from the environment and no record can bind the plane
        it was written into -- with the selection moved, the engine would never open that
        record. Observed: crash an apply AFTER publication in the default plane, then select
        `AGENTIC_SDLC_ACTIVATION_STATE=repo-local`, and the engine reported `inactive` with
        `effect: none` at exit 0 over a published product with an unresolved journal, and
        permitted a second apply. It was reachable through the engine's OWN documented remedy
        for a cross-device plane, which is what made a recorded comment insufficient.
      * RELOCATION. `XDG_STATE_HOME` or `HOME` moved to a directory the environment no longer
        names is the same move without touching the selection.
      * RENAME. The plane key is the digest of the absolute target path, so renaming the
        checkout resolves a fresh empty plane while the old one still holds the journal for a
        product that is still published in the renamed tree. This is the ordinary operation of
        the three, and the first fix for the selection defect introduced it: it reported exit
        0 `inactive` where the pre-plane engine had reported exit 4 `effect-unknown`, which
        made a confident "nothing here" out of an honest "I cannot tell".

    Two mechanisms close them, both before any journal or product effect.
    `_assert_unselected_planes_empty` probes every plane this invocation did not select, and
    `_record_plane_pointer` writes a machine-local pointer into the checkout -- before the
    plane receives any record -- so that the plane the state went into stays exactly nameable
    from inside the directory a rename moves.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state_home = use_state_plane(self, self.root)
        self.target = self.root / "repo"
        self.target.mkdir()
        init_repo(self.target)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))
        self.serial = 0

    def _documents(self, target: Path | None = None) -> tuple[Path, Path]:
        """Plan and grant for one apply, produced under the CURRENT plane selection."""
        target = self.target if target is None else target
        planned, code = ap.plan_command(target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, planned)
        plan = planned["plan"]
        serial = self.serial
        self.serial = serial + 1
        plan_path = self.root / f"plan-{serial}.json"
        plan_path.write_bytes(ap.canonical_bytes(plan))
        instant = now()
        grant = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "7" * 31 + format(serial, "x"), "operation": "apply",
            "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
            "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        grant_path = self.root / f"grant-{serial}.json"
        grant_path.write_bytes(ap.canonical_bytes(grant))
        return plan_path, grant_path

    def _crash_after_publish(self, target: Path | None = None) -> None:
        """Publish the product, then die before the commit witness lands."""
        target = self.target if target is None else target
        plan_path, grant_path = self._documents(target)
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(self.manifest),
            "--grant", str(grant_path),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="publish"))
        self.assertEqual(crashed.returncode, 97)
        self.assertTrue((target / "AGENTS.md").is_file(), "the product must be published for this to be a partial effect")

    def _unresolved_journal(self, transactions: Path) -> Path:
        journal = next(transactions.iterdir())
        progress, _ = ap.load_canonical_json(journal / "progress.json", "progress")
        self.assertEqual(progress["phase"], "staged", progress)
        return journal

    def _assert_still_unresolved(self, journal: Path) -> None:
        progress, _ = ap.load_canonical_json(journal / "progress.json", "progress")
        self.assertEqual(progress["phase"], "staged", progress)

    def _finish(self, target: Path | None = None) -> tuple[dict, int]:
        """Recover the transaction in the plane that actually owns it."""
        target = self.target if target is None else target
        inspected, code = ap.recover_inspect_command(target)
        self.assertEqual(code, 3, inspected)
        self.assertEqual(inspected["status"], "recovery-required")
        instant = now()
        recovery = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "b" * 32, "operation": "recover",
            "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
            "plan_digest": None, "operation_id": inspected["operation_id"],
            "operation_digest": inspected["operation_digest"], "decision": "finish",
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        path = self.root / "recovery.json"
        path.write_bytes(ap.canonical_bytes(recovery))
        return ap.recover_finish_command(target, path)

    def _assert_recorded_plane_refusal(self, result: dict, code: int) -> None:
        """A plane no environment variable names any more: this checkout moved."""
        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["reasons"], [ap.RECORDED_PLANE_REASON], result)

    def _assert_unselected_plane_refusal(self, result: dict, code: int, label: str) -> None:
        self.assertEqual(code, 3, result)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["reasons"], [f"{ap.UNSELECTED_PLANE_REASON}: {label}"], result)

    def test_repo_local_selection_refuses_while_the_default_plane_holds_an_unresolved_journal(self) -> None:
        """The exact reported reproduction, with its own before/after positive control."""
        # POSITIVE CONTROL, on this same target under this same selection: with the default
        # plane empty the repo-local selection reports `inactive` at exit 0. The refusals
        # below therefore come from the default plane's state, not from the selection being
        # broken or from a missing path.
        select_repo_local_plane(self)
        control, control_code = ap.recover_inspect_command(self.target)
        self.assertEqual(control_code, 0, control)
        self.assertEqual(control["status"], "inactive")
        self.assertEqual(control["effect"], "none")

        set_environment(self, ap.PLANE_SELECTION_ENV, None)
        self._crash_after_publish()
        journal = self._unresolved_journal(plane_transactions(self.target))

        select_repo_local_plane(self)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        observed, status_code = ap.status_command(self.target)
        planned, plan_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self._assert_unselected_plane_refusal(inspected, inspect_code, ap.PLANE_LABEL_DEFAULT)
        self._assert_unselected_plane_refusal(observed, status_code, ap.PLANE_LABEL_DEFAULT)
        self._assert_unselected_plane_refusal(planned, plan_code, ap.PLANE_LABEL_DEFAULT)
        # A refused plan cannot become a second apply, and nothing was written into the newly
        # selected repo-local plane: no `receipts/`, no `transactions/`, no root-level anchor or
        # audit. The state root itself exists, holding only the pointer the crashed DEFAULT-plane
        # apply wrote before it created its plane -- which is what makes the refusal above
        # survive a rename, and is asserted exactly rather than by absence.
        self.assertEqual(sorted(item.name for item in self.target.glob(".agentic-sdlc*")), [".agentic-sdlc"])
        self.assertEqual(sorted(item.name for item in (self.target / ".agentic-sdlc").iterdir()), [pointer_name(plane_root(self.target))])
        self._assert_still_unresolved(journal)

        # And the operator is not stranded: the plane that owns the journal still recovers.
        set_environment(self, ap.PLANE_SELECTION_ENV, None)
        completed, finish_code = self._finish()

        self.assertEqual(finish_code, 0, completed)
        self.assertEqual(completed["status"], "committed")

    def test_default_selection_refuses_a_repo_local_crash_journal_before_any_effect(self) -> None:
        """The reverse direction, demonstrated against a real crashed journal.

        This one is refused by `LEGACY_STATE_REASON` from `_validate_repository_state_root`,
        which runs first and names the same surface. Asserting the reverse direction here
        keeps the property under test end to end rather than trusting which of the two
        guards happens to fire.
        """
        select_repo_local_plane(self)
        self._crash_after_publish()
        journal = self._unresolved_journal(self.target / ".agentic-sdlc" / "transactions")

        set_environment(self, ap.PLANE_SELECTION_ENV, None)
        inspected, inspect_code = ap.recover_inspect_command(self.target)
        observed, status_code = ap.status_command(self.target)
        planned, plan_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        for result, code in ((inspected, inspect_code), (observed, status_code), (planned, plan_code)):
            self.assertEqual(code, 3, result)
            self.assertEqual(result["status"], "refused")
            self.assertEqual(result["effect"], "none")
            self.assertEqual(result["reasons"], [ap.LEGACY_STATE_REASON], result)
        self.assertFalse(plane_root(self.target).exists())
        self._assert_still_unresolved(journal)

        select_repo_local_plane(self)
        completed, finish_code = self._finish()

        self.assertEqual(finish_code, 0, completed)
        self.assertEqual(completed["status"], "committed")

    def test_setting_the_state_home_refuses_while_the_fallback_plane_holds_state(self) -> None:
        """Setting `XDG_STATE_HOME` after a plane was written under the fallback is a switch.

        `$HOME/.local/state` is the one other plane the ENVIRONMENT can name exactly, so it is
        probed even when the variable is set. A state home moved to a THIRD directory, which
        neither variable names any more, is covered separately by the pointer the checkout
        itself carries -- see
        `test_a_state_home_moved_to_a_third_directory_is_still_named_by_the_pointer`.
        """
        home = self.root / "home"
        (home / ".local" / "state").mkdir(parents=True)
        set_environment(self, "HOME", str(home))
        # POSITIVE CONTROL: with the fallback plane empty, this exact selection reports
        # `inactive` at exit 0.
        control, control_code = ap.recover_inspect_command(self.target)
        self.assertEqual(control_code, 0, control)
        self.assertEqual(control["status"], "inactive")

        set_environment(self, "XDG_STATE_HOME", None)
        self._crash_after_publish()
        fallback = plane_root(self.target, home / ".local" / "state")
        journal = self._unresolved_journal(fallback / "transactions")

        set_environment(self, "XDG_STATE_HOME", str(self.state_home))
        inspected, inspect_code = ap.recover_inspect_command(self.target)

        self._assert_unselected_plane_refusal(inspected, inspect_code, ap.PLANE_LABEL_DEFAULT)
        self.assertFalse(plane_root(self.target, self.state_home).exists())
        self._assert_still_unresolved(journal)

    def test_a_no_op_audit_alone_is_state_a_plane_switch_cannot_step_over(self) -> None:
        """A plane can hold state with no `receipts/` and no `transactions/` at all.

        `_apply_noop` creates only the key directory and one `noop.<id>.json`, and an apply
        interrupted at the `setup` failpoint leaves only `intent.<id>.json`. Probing just the
        two directories would step over both. The audit is the grant ledger: `scan_grant_ledger`
        reads only the SELECTED plane's audits, so a switch would let an already-consumed
        procedural grant be replayed.
        """
        # The product already matches the manifest render, so this apply is a no-op audit.
        plan_path, grant_path = self._documents()
        published, published_code = ap.apply_command(plan_path, self.manifest, grant_path)
        self.assertEqual(published_code, 0, published)
        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "product")
        plan_path, grant_path = self._documents()
        audited, audited_code = ap.apply_command(plan_path, self.manifest, grant_path)
        self.assertEqual(audited_code, 0, audited)
        self.assertEqual(audited["status"], "no-op")
        # Reduce the plane to audit-only state, so the directory probe cannot see it.
        plane = plane_root(self.target)
        shutil.rmtree(plane / "receipts")
        shutil.rmtree(plane / "transactions")
        audits = sorted(item.name for item in plane.iterdir())
        self.assertEqual(audits, [f"noop.{audited['operation_id']}.json"], audits)

        select_repo_local_plane(self)
        observed, status_code = ap.status_command(self.target)

        self._assert_unselected_plane_refusal(observed, status_code, ap.PLANE_LABEL_DEFAULT)

        # A RENAME must not step over it either, and for the same grant-ledger reason. The plane
        # holds one audit and no directories at all, so this is also the case that shows the probe
        # does not depend on `receipts/` or `transactions/` being there to look at.
        set_environment(self, ap.PLANE_SELECTION_ENV, None)
        renamed = self.root / "repo-renamed"
        self.target.rename(renamed)
        try:
            after_rename, after_code = ap.status_command(renamed)
            planned, plan_code = ap.plan_command(renamed, self.manifest, "AGENTS.md")
        finally:
            renamed.rename(self.target)

        self._assert_recorded_plane_refusal(after_rename, after_code)
        self._assert_recorded_plane_refusal(planned, plan_code)
        self.assertEqual(sorted(item.name for item in plane.iterdir()), audits)

    def test_the_probe_never_claims_no_effect_over_a_published_product(self) -> None:
        """The guard is an admission check, and it must not become a post-publish refusal.

        `write_commit` captures the poststate through `capture_git_observation`, which reaches
        `validate_internal_status_records` -> `_validate_private_state` AFTER the product is
        published. A refusal raised from there was reported by `apply_command` as `refused`
        with `effect: none` over published bytes -- the exact class this project keeps
        relearning. That was MEASURABLY true of `LEGACY_STATE_REASON` at the same site, and the
        case immediately below now closes it at `apply_command`'s handler. This test remains the
        narrower property, and it is not made redundant by that fix: the probe must still not
        RUN here at all, because a refusal that is honestly reported is still a refusal, and
        this one would refuse an activation that has already succeeded.

        The two halves are each other's control: the identical injection BEFORE the apply is
        a clean exit-3 refusal, and DURING the apply it is not a refusal at all.
        """
        home = self.root / "home"
        (home / ".local" / "state").mkdir(parents=True)
        set_environment(self, "HOME", str(home))
        fallback = plane_root(self.target, home / ".local" / "state")

        def plant_fallback_state() -> None:
            (fallback / "transactions").mkdir(mode=0o700, parents=True)

        # HALF ONE, the control: planted before admission, this is a clean refusal.
        plant_fallback_state()
        refused, refused_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
        self._assert_unselected_plane_refusal(refused, refused_code, ap.PLANE_LABEL_DEFAULT)
        shutil.rmtree(fallback)

        # HALF TWO: the same state appears between publication and the commit witness.
        plan_path, grant_path = self._documents()
        original = ap.write_commit
        planner_globals = original.__globals__

        def inject(operation_dir: Path, operation: dict, poststate: dict, target: Path) -> dict:
            plant_fallback_state()
            return original(operation_dir, operation, poststate, target)

        planner_globals["write_commit"] = inject
        try:
            result, code = ap.apply_command(plan_path, self.manifest, grant_path)
        finally:
            planner_globals["write_commit"] = original

        self.assertTrue((self.target / "AGENTS.md").is_file())
        self.assertTrue((fallback / "transactions").is_dir(), "the injection must have happened")
        self.assertEqual(code, 0, result)
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["effect"], "committed")

    def test_a_post_publication_refusal_is_never_reported_as_a_clean_refusal(self) -> None:
        """THE MEASURED SIXTH INSTANCE, at the site the case above named and left open.

        `_validate_private_state` is reachable AFTER publication -- `write_commit` ->
        `capture_git_observation` -> `validate_internal_status_records` -- and
        `LEGACY_STATE_REASON` fires there for a repo-local `receipts/` or `transactions/` that
        appears inside the window. MEASURED on the unmodified engine:

            control, no injection      -> 0 committed  effect=committed  published=True
            repo-local state injected  -> 3 refused    effect=none       published=True

        Exit 3 is a clean refusal BEFORE any journal or product effect. `AGENTS.md` was on disk,
        the journal was complete, and the operator was told nothing had happened. Per Decision 9
        that is a 4.

        THREE arms, because the fix must be a derivation and not a blanket answer:

          * CONTROL ONE, positive, on the observation channel: with no injection the same apply
            commits at 0 with `effect: committed`, so the exit-4 arm below is not the fixture
            refusing for some unrelated reason.
          * CONTROL TWO, positive, on the guard's own reason BEFORE any effect: the identical
            injection planted before the apply is still a clean exit-3 refusal naming
            `LEGACY_STATE_REASON`, with an empty ledger. A change that made every refusal
            `effect_unknown` would fail here.
          * THE CASE: the same injection inside the window is exit 4 `effect-unknown` with
            `effect: effect_unknown`, the SAME reason -- so the refusal still comes from the
            guard it names and not from a broken fixture -- and an `admitted_effects` ledger
            that names the publication rename.
        """
        # CONTROL ONE.
        control_plan, control_grant = self._documents()
        control, control_code = ap.apply_command(control_plan, self.manifest, control_grant)
        self.assertEqual(control_code, 0, control)
        self.assertEqual(control["effect"], "committed")
        self.assertTrue((self.target / "AGENTS.md").is_file())

        # Back to an unactivated tree, keeping the pointer the first apply wrote: the state
        # plane's own records are what a fresh apply must not find, and the injected
        # `.agentic-sdlc/receipts` below is a target-local surface, not a plane one.
        shutil.rmtree(plane_root(self.target))
        (self.target / "AGENTS.md").unlink()

        def inject_repo_local_state() -> None:
            (self.target / ".agentic-sdlc" / "receipts").mkdir(mode=0o700, parents=True, exist_ok=True)

        # CONTROL TWO, on the same command with the same documents: no surface hands out a plan
        # once the injected state is present, so the documents are captured while the tree is
        # clean and the state is planted between the plan and the apply.
        clean_plan, clean_grant = self._documents()
        inject_repo_local_state()
        before, before_code = ap.apply_command(clean_plan, self.manifest, clean_grant)
        self.assertEqual(before_code, 3, before)
        self.assertEqual(before["status"], "refused")
        self.assertEqual(before["effect"], "none")
        self.assertEqual(before["reasons"], [ap.LEGACY_STATE_REASON], before)
        self.assertEqual(before["admitted_effects"], [])
        self.assertFalse((self.target / "AGENTS.md").exists(), "a clean refusal must publish nothing")
        shutil.rmtree(self.target / ".agentic-sdlc" / "receipts")

        # THE CASE. The plan and grant are captured while the tree is clean, because no surface
        # hands out a plan once the injected state is present.
        plan_path, grant_path = self._documents()
        original = ap.write_commit
        planner_globals = original.__globals__

        def inject(operation_dir: Path, operation: dict, poststate: dict, target: Path) -> dict:
            inject_repo_local_state()
            return original(operation_dir, operation, poststate, target)

        planner_globals["write_commit"] = inject
        try:
            result, code = ap.apply_command(plan_path, self.manifest, grant_path)
        finally:
            planner_globals["write_commit"] = original

        self.assertTrue((self.target / ".agentic-sdlc" / "receipts").is_dir(), "the injection must have happened")
        self.assertTrue((self.target / "AGENTS.md").is_file(), "the product is published; a clean refusal would be a lie")
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(result["effect"], "effect_unknown")
        self.assertEqual(result["reasons"], [ap.LEGACY_STATE_REASON], result)
        self.assertIn("renamed 0000.payload onto AGENTS.md (flags 1)", result["admitted_effects"], result)

    def _pointer(self, target: Path, root: Path | None = None) -> Path:
        return target / ".agentic-sdlc" / pointer_name(plane_root(target) if root is None else root)

    def _all_surfaces(self, target: Path) -> list[tuple[dict, int]]:
        """Every read surface plus the one that gates a second apply."""
        return [
            ap.status_command(target),
            ap.recover_inspect_command(target),
            ap.plan_command(target, self.manifest, "AGENTS.md"),
        ]

    def test_renaming_the_checkout_refuses_instead_of_reporting_inactive(self) -> None:
        """THE REPORTED REGRESSION. A rename moved the plane out of reach of the key.

        The plane key is the digest of the absolute target path, so after a rename the engine
        resolved a fresh, empty plane. It reported `inactive` with `effect: none` at exit 0 --
        MEASURED, on all three surfaces -- and admitted a second apply that committed over a
        published product whose first journal was still unresolved. The pre-plane engine
        answered exit 4 `effect-unknown` for the same rename, because the journal travelled
        inside the tree and failed `_bind_operation_target`.

        The pointer the checkout carries is what makes the old plane nameable again. Both
        controls matter: a renamed checkout with NOTHING in its plane still reports `inactive`
        at exit 0, and the plane that owns the journal still recovers once the name is back.
        """
        # POSITIVE CONTROL ONE: renaming a checkout that has no activation state at all is not
        # a refusal. Without this, a guard that refuses every renamed target would pass.
        clean = self.root / "clean-renamed"
        self.target.rename(clean)
        for result, code in self._all_surfaces(clean):
            self.assertEqual(code, 0, result)
            self.assertIn(result["status"], {"inactive", "planned"})
        clean.rename(self.target)

        self._crash_after_publish()
        journal = self._unresolved_journal(plane_transactions(self.target))
        original_plane = plane_root(self.target)
        self.assertTrue(self._pointer(self.target).is_file(), "the crash must have left a pointer to its plane")

        renamed = self.root / "repo-renamed"
        self.target.rename(renamed)

        self.assertTrue((renamed / "AGENTS.md").is_file(), "the product travels with the rename")
        self.assertNotEqual(plane_root(renamed), original_plane, "the rename must change the key")
        self.assertFalse(plane_root(renamed).exists(), "the new key names nothing")
        for result, code in self._all_surfaces(renamed):
            # Its own reason, not the selection one: no environment variable names this plane
            # any more, so the refusal has to tell the operator that the checkout moved rather
            # than that a selection changed.
            self._assert_recorded_plane_refusal(result, code)
        # No plan means no second apply, and the orphaned journal is untouched and still owned
        # by the plane it was written into.
        self._assert_still_unresolved(journal)
        self.assertEqual(sorted(item.name for item in (renamed / ".agentic-sdlc").iterdir()), [pointer_name(original_plane)])

        # POSITIVE CONTROL TWO: recovery stays reachable. Renaming back restores the key, and
        # the transaction finishes in the plane that owns it.
        renamed.rename(self.target)
        completed, finish_code = self._finish()

        self.assertEqual(finish_code, 0, completed)
        self.assertEqual(completed["status"], "committed")

    def test_a_rename_cannot_step_over_a_plane_holding_only_a_setup_anchor(self) -> None:
        """The pointer lands BEFORE the plane, so no plane record can outlive its name.

        Crashing at the `setup` failpoint leaves a plane whose only content is
        `intent.<id>.json` -- no `receipts/`, no `transactions/`, nothing published. Writing the
        pointer any later than the plane root would leave that anchor nameless after a rename,
        and this is the input that distinguishes the two orders.
        """
        plan_path, grant_path = self._documents()
        crashed = subprocess.run([
            sys.executable, str(SCRIPT), "apply", "--plan", str(plan_path), "--manifest", str(self.manifest),
            "--grant", str(grant_path),
        ], env=dict(os.environ, AGENTIC_SDLC_FAILPOINT="setup"))
        self.assertEqual(crashed.returncode, 97)
        original_plane = plane_root(self.target)
        anchors = sorted(item.name for item in original_plane.iterdir())
        self.assertEqual(len(anchors), 1, anchors)
        self.assertTrue(anchors[0].startswith("intent."), anchors)
        self.assertFalse((self.target / "AGENTS.md").exists(), "nothing is published at the setup failpoint")

        renamed = self.root / "repo-renamed"
        self.target.rename(renamed)
        observed, status_code = ap.status_command(renamed)

        self._assert_recorded_plane_refusal(observed, status_code)
        self.assertEqual(sorted(item.name for item in original_plane.iterdir()), anchors)

    def test_a_state_home_moved_to_a_third_directory_is_still_named_by_the_pointer(self) -> None:
        """The residual gap the previous round left open, closed and demonstrated.

        Neither `XDG_STATE_HOME` nor `$HOME` names the old plane any more, so the environment
        alone cannot describe it. The pointer inside the checkout can, exactly.
        """
        third = self.root / "third-state-home"
        third.mkdir()
        # POSITIVE CONTROL: with the original plane empty, this exact relocation is `inactive`.
        set_environment(self, "XDG_STATE_HOME", str(third))
        control, control_code = ap.status_command(self.target)
        self.assertEqual(control_code, 0, control)
        self.assertEqual(control["status"], "inactive")

        set_environment(self, "XDG_STATE_HOME", str(self.state_home))
        self._crash_after_publish()
        journal = self._unresolved_journal(plane_transactions(self.target))
        original_plane = plane_root(self.target, self.state_home)

        set_environment(self, "XDG_STATE_HOME", str(third))
        observed, status_code = ap.status_command(self.target)

        self._assert_recorded_plane_refusal(observed, status_code)
        self.assertFalse(plane_root(self.target, third).exists())
        self.assertTrue(self._pointer(self.target, original_plane).is_file())
        self._assert_still_unresolved(journal)

    def _crash_around_the_plane_root(self, *, after: bool) -> None:
        """Crash an apply in the window between the pointer and the plane root, either side.

        `after=False` leaves a pointer naming a root that does not exist; `after=True` leaves
        the same pointer naming a root that exists and is EMPTY. Those are the two sides of the
        distinction this class now draws, and the injection is the only way to reach them
        because the pointer is deliberately written before the plane root.
        """
        plan_path, grant_path = self._documents()
        original = ap._mkdir_plane_root
        planner_globals = original.__globals__

        def die_around_the_plane(plane, root, target_fd):
            if after:
                os.close(original(plane, root, target_fd))
            raise ap.ActivationError("refused", "injected crash at the plane root", 3)

        planner_globals["_mkdir_plane_root"] = die_around_the_plane
        try:
            refused, refused_code = ap.apply_command(plan_path, self.manifest, grant_path)
        finally:
            planner_globals["_mkdir_plane_root"] = original

        # Exit 4, and it is derived rather than injected: the double raises a code-3 `refused`,
        # which is exactly what a raise site may no longer decide for itself. The pointer is on
        # disk by the time it fires, so `_report_failure` escalates the refusal and NAMES the
        # pointer as the effect already admitted. Asserting the named effect rather than only the
        # code is what keeps this from passing on a blanket "everything is 4" answer.
        self.assertEqual(refused_code, 4, refused)
        self.assertEqual(refused["status"], "effect-unknown")
        self.assertEqual(refused["effect"], "effect_unknown")
        self.assertEqual(refused["reasons"], ["injected crash at the plane root"], refused)
        self.assertIn(f"wrote private metadata {pointer_name(plane_root(self.target))}", refused["admitted_effects"], refused)
        self.assertTrue(self._pointer(self.target).is_file(), "the pointer must precede the plane root")
        self.assertEqual(plane_root(self.target).exists(), after)
        self.assertFalse((self.target / "AGENTS.md").exists())

    def _assert_unresolved_plane_effect_unknown(self, result: dict, code: int) -> None:
        """A plane this checkout RECORDED that nothing can resolve: cannot tell, not `inactive`."""
        self.assertEqual(code, 4, result)
        self.assertEqual(result["status"], "effect-unknown")
        self.assertEqual(result["reasons"], [ap.RECORDED_PLANE_UNRESOLVED_REASON], result)
        # The residual this case used to record as a closed SET is gone. `status` and
        # `recover inspect` reported `effect_unknown` here while `plan` and `apply` reported
        # `none`, and both were true -- the disagreement existed only because each handler
        # decided the effect for itself. All four now derive it at one point, so the exact value
        # is asserted. `admitted_effects` is present and empty on every one of them, which is the
        # positive control that the wider `effect_unknown` comes from the raise site's own
        # observation of a plane nothing can resolve and NOT from anything this command did.
        self.assertEqual(result["effect"], "effect_unknown", result)
        self.assertEqual(result["admitted_effects"], [], result)

    def test_a_pointer_to_a_plane_that_never_materialized_does_not_strand_the_target(self) -> None:
        """A pointer is not itself evidence of state: an empty plane probes clean.

        The pointer is written before the plane root, so a crash in that window leaves a
        pointer naming a plane that does not exist. Nothing was published and no journal was
        written, so `inactive` is the honest answer and the next apply must be admitted -- the
        opposite failure to the one this class's other cases fixed, and the reason the probe
        reads the plane instead of trusting the pointer's existence.

        The scope of that is exactly "where the pointer's root is the one this invocation also
        resolves". Once the checkout MOVES, the same pointer names a root nothing can resolve,
        and the engine can no longer prove the plane was never written -- see
        `test_a_recorded_plane_root_that_cannot_be_resolved_is_effect_unknown_not_inactive`,
        which is the other half of this input.
        """
        self._crash_around_the_plane_root(after=False)

        observed, status_code = ap.status_command(self.target)
        plan_path, grant_path = self._documents()
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)

        self.assertEqual(status_code, 0, observed)
        self.assertEqual(observed["status"], "inactive")
        self.assertEqual(applied_code, 0, applied)
        self.assertEqual(applied["status"], "committed")

    def test_a_recorded_plane_root_that_resolves_and_is_empty_stays_inactive(self) -> None:
        """THE SIDE THAT MUST NOT MOVE. A resolvable empty recorded root is provably absent.

        The crash window between the plane root and its first record leaves an EXISTING empty
        key directory. After a rename no environment variable names it, so it is reached only
        through the pointer -- and the engine can still list it and see that nothing is there.
        That is a proof of absence, so it stays `inactive` at exit 0 and the retry is admitted.

        Its own control is the assertion that the root exists and is empty: without it, this
        test would pass for the wrong reason the moment the fixture stopped creating the root.
        """
        self._crash_around_the_plane_root(after=True)
        recorded = plane_root(self.target)
        self.assertEqual(sorted(item.name for item in recorded.iterdir()), [], "the recorded root must resolve and be empty")

        renamed = self.root / "repo-renamed"
        self.target.rename(renamed)
        try:
            surfaces = self._all_surfaces(renamed)
        finally:
            renamed.rename(self.target)
        plan_path, grant_path = self._documents()
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)

        for result, code in surfaces:
            self.assertEqual(code, 0, result)
            self.assertIn(result["status"], {"inactive", "planned"})
        self.assertEqual(applied_code, 0, applied)
        self.assertEqual(applied["status"], "committed")

    def test_a_recorded_plane_root_that_cannot_be_resolved_is_effect_unknown_not_inactive(self) -> None:
        """THE REPORTED CASE, and it is the ordinary arrangement rather than an exotic one.

        ONE `mv` of a home directory holding BOTH the checkout and the state plane -- a checkout
        under `$HOME` and the plane under `$HOME/.local/state`, which is the common layout. The
        pointer's recorded ABSOLUTE root then names a path that no longer exists, while the
        state itself moved with the home into a root the new key does not name and no pointer
        records. MEASURED before the fix: `inspect`, `status`, and `plan` all reported
        `inactive`/`planned` with `effect: none` at exit 0, and a second apply was admitted over
        the published product while the first journal stayed unresolved. HEAD answered exit 4
        `effect-unknown` for the same operation, and that was the honest answer.

        Both controls are here, because a change that makes everything `effect-unknown` is not a
        fix: a never-activated checkout carries no pointer and is still `inactive` at exit 0
        after the same move, and moving the home BACK lets `recover finish` complete.
        """
        home = self.root / "home"
        (home / ".local" / "state").mkdir(parents=True)
        set_environment(self, "HOME", str(home))
        set_environment(self, "XDG_STATE_HOME", None)
        moved_home = self.root / "moved-home"

        # POSITIVE CONTROL ONE: no pointer, so the identical move is not `effect-unknown`.
        clean = home / "clean"
        clean.mkdir()
        init_repo(clean)
        home.rename(moved_home)
        set_environment(self, "HOME", str(moved_home))
        for result, code in self._all_surfaces(moved_home / "clean"):
            self.assertEqual(code, 0, result)
            self.assertIn(result["status"], {"inactive", "planned"})
        moved_home.rename(home)
        set_environment(self, "HOME", str(home))

        target = home / "repo"
        target.mkdir()
        init_repo(target)
        # Captured BEFORE the crash, because afterwards no surface will hand out a plan. Rewriting
        # its paths gives the plan the moved location would have produced -- `mv` preserves
        # dev/ino -- so `apply` can be driven directly rather than only shown to be unreachable.
        stale_plan, _ = self._documents(target)
        self._crash_after_publish(target)
        recorded = plane_root(target, home / ".local" / "state")
        journal = self._unresolved_journal(recorded / "transactions")
        self.assertTrue(self._pointer(target, recorded).is_file())

        home.rename(moved_home)
        set_environment(self, "HOME", str(moved_home))
        moved = moved_home / "repo"
        moved_journal = moved_home / ".local" / "state" / "ccodex" / "activation" / recorded.name / "transactions" / journal.name

        self.assertTrue((moved / "AGENTS.md").is_file(), "the product travels with the home")
        self.assertFalse(recorded.exists(), "the recorded plane root no longer resolves")
        self.assertFalse(plane_root(moved, moved_home / ".local" / "state").exists(), "the new key names nothing")
        self.assertTrue((moved_journal / "progress.json").is_file(), "the journal moved with the home, into a root nothing names")
        for result, code in self._all_surfaces(moved):
            self._assert_unresolved_plane_effect_unknown(result, code)
        # And `apply` itself, driven with a plan the moved location would accept. The grant path
        # below does not exist, which is the point: the answer lands before any grant is read, so
        # no fresh effect is admitted on any input.
        moved_plan = self.root / "moved-plan.json"
        moved_plan.write_bytes(stale_plan.read_bytes().replace(str(home).encode(), str(moved_home).encode()))
        attempted, attempted_code = ap.apply_command(moved_plan, self.manifest, self.root / "no-such-grant.json")
        self._assert_unresolved_plane_effect_unknown(attempted, attempted_code)
        self.assertFalse(plane_root(moved, moved_home / ".local" / "state").exists())
        self._assert_still_unresolved(moved_journal)

        # POSITIVE CONTROL TWO: the operator is not stranded. Moving the home back restores both
        # halves at once, and the transaction finishes in the plane that owns it.
        moved_home.rename(home)
        set_environment(self, "HOME", str(home))
        completed, finish_code = self._finish(target)

        self.assertEqual(finish_code, 0, completed)
        self.assertEqual(completed["status"], "committed")

    def test_an_unreadable_candidate_plane_is_refused_rather_than_read_as_empty(self) -> None:
        """"Cannot tell" is not absence. `Path.exists()` would have said it was.

        The probe walks planes the operator owns, and a directory it cannot read is the exact
        state that must not become `inactive`. Two fixtures, because an unreadable plane root and
        an unreadable ANCESTOR of one fail at different points and a reader should not have to
        assume the second follows from the first:

          * the plane root at 0o100: traversable but not readable, so the listing itself fails;
          * `ccodex` at 0o000: neither, so the listing fails one level higher up.

        Positive control: the same trees readable are `inactive` at exit 0. A plane root that
        exists and IS readable and empty stays `inactive` too -- see
        `test_a_pointer_to_a_plane_that_never_materialized_does_not_strand_the_target` -- so this
        is a refusal about not being able to look, never about the plane being empty.
        """
        if os.geteuid() == 0:
            self.skipTest("root ignores the permission bits this case depends on")
        home = self.root / "home"
        fallback_home = home / ".local" / "state"
        fallback_plane = plane_root(self.target, fallback_home)
        fallback_plane.mkdir(mode=0o700, parents=True)
        set_environment(self, "HOME", str(home))

        for label, node, mode in (("plane root", fallback_plane, 0o100), ("ancestor", fallback_home / "ccodex", 0o000)):
            with self.subTest(fixture=label):
                control, control_code = ap.status_command(self.target)
                self.assertEqual(control_code, 0, control)
                self.assertEqual(control["status"], "inactive")

                os.chmod(node, mode)
                try:
                    observed, status_code = ap.status_command(self.target)
                    planned, plan_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")
                finally:
                    os.chmod(node, 0o700)

                for result, code in ((observed, status_code), (planned, plan_code)):
                    self.assertEqual(code, 3, result)
                    self.assertEqual(result["status"], "refused")
                    self.assertEqual(result["effect"], "none")
                    self.assertEqual(result["reasons"], [f"{ap.PLANE_PROBE_REASON}: {ap.PLANE_LABEL_DEFAULT}"], result)

    def test_a_pointer_is_admitted_only_under_private_custody(self) -> None:
        """The whitelist widened by one engine-owned family, not by one relaxed rule.

        A pointer is held to the private rule -- exact 0600, single link, not a symlink -- and
        not to the cloneable rule the two Git-materialized public names get. A committed copy
        of a pointer materializes at the caller's umask and is refused by name here, which is
        why `.gitignore` records that it is never committed.
        """
        plan_path, grant_path = self._documents()
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)
        self.assertEqual(applied_code, 0, applied)
        pointer = self._pointer(self.target)

        # POSITIVE CONTROL: at 0600 this exact pointer is admitted and status is committed.
        control, control_code = ap.status_command(self.target)
        self.assertEqual(control_code, 0, control)
        self.assertEqual(control["status"], "committed")

        for mode in (0o644, 0o700, 0o400):
            with self.subTest(mode=oct(mode)):
                os.chmod(pointer, mode)
                try:
                    observed, status_code = ap.status_command(self.target)
                finally:
                    os.chmod(pointer, 0o600)
                self.assertNotEqual(status_code, 0, observed)
                self.assertEqual(observed["status"], "foreign-state")
                self.assertIn("unsafe private plane pointer", observed["reasons"])

        link = self.target / ".agentic-sdlc" / pointer_name(self.root / "elsewhere")
        link.symlink_to(pointer)
        try:
            observed, status_code = ap.status_command(self.target)
        finally:
            link.unlink()

        self.assertNotEqual(status_code, 0, observed)
        self.assertEqual(observed["status"], "foreign-state")
        self.assertIn("unsafe private plane pointer", observed["reasons"])

    def test_a_forged_pointer_cannot_name_a_plane_its_filename_does_not_bind(self) -> None:
        """The filename is the digest of the recorded plane, so neither half moves alone.

        Without the binding, renaming a pointer -- or planting one under a name in the family --
        would let an arbitrary directory be presented as this checkout's plane, and a pointer
        could be retargeted away from the plane that actually holds the journal.
        """
        state = self.target / ".agentic-sdlc"
        state.mkdir(mode=0o700)
        elsewhere = self.root / "elsewhere"
        cases = {
            "plane pointer does not bind its plane": (
                pointer_name(elsewhere),
                {"schema": ap.PLANE_POINTER_SCHEMA, "plane": str(plane_root(self.target))},
            ),
            "invalid plane pointer": (
                pointer_name(elsewhere),
                {"schema": ap.PLANE_POINTER_SCHEMA, "plane": "relative/plane"},
            ),
        }
        for reason, (name, body) in cases.items():
            with self.subTest(reason=reason):
                forged = state / name
                forged.write_bytes(ap.canonical_bytes(body))
                os.chmod(forged, 0o600)
                try:
                    observed, status_code = ap.status_command(self.target)
                finally:
                    forged.unlink()

                self.assertNotEqual(status_code, 0, observed)
                self.assertEqual(observed["status"], "foreign-state")
                self.assertIn(reason, observed["reasons"])

        # A name in the family that is not canonical JSON at all is refused too.
        stray = state / f"{ap.PLANE_POINTER_PREFIX}{'0' * 64}.json"
        stray.write_text("{}\n")
        os.chmod(stray, 0o600)
        observed, status_code = ap.status_command(self.target)
        self.assertNotEqual(status_code, 0, observed)
        self.assertEqual(observed["status"], "foreign-state")
        self.assertIn("invalid plane pointer", observed["reasons"])
        stray.unlink()

        # POSITIVE CONTROL: with the forgeries gone, an ordinary apply writes its own pointer
        # into this same state root and is admitted.
        plan_path, grant_path = self._documents()
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)
        self.assertEqual(applied_code, 0, applied)
        self.assertEqual(sorted(item.name for item in state.iterdir()), [pointer_name(plane_root(self.target))])

    def test_the_pointer_never_dirties_the_engines_git_projection(self) -> None:
        """It is machine-local state, so it is suppressed -- and only it is.

        Left visible, the pointer would be a permanent untracked record that fails
        `_require_clean` on every apply after the first, so the engine would break its own
        repository. The control is the same test's second half: an ordinary untracked file at
        the repository root DOES refuse, so the suppression is exactly one name wide.
        """
        plan_path, grant_path = self._documents()
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)
        self.assertEqual(applied_code, 0, applied)
        pointer = self._pointer(self.target)
        self.assertTrue(pointer.is_file())
        # The human's own `git status` still shows it: nothing is hidden from Git itself, and
        # this repository ignores it by name instead.
        raw = subprocess.run(["git", "-C", str(self.target), "status", "--porcelain", "--untracked-files=all"], capture_output=True, check=True).stdout.decode()
        self.assertIn(".agentic-sdlc/", raw)

        git(self.target, "add", "AGENTS.md")
        git(self.target, "commit", "-m", "product")
        second, second_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertEqual(second_code, 0, second)
        self.assertEqual(second["plan"]["git"]["filtered_internal"], [f".agentic-sdlc/{pointer.name}"])

        (self.target / "unrelated.txt").write_text("dirty\n")
        refused, refused_code = ap.plan_command(self.target, self.manifest, "AGENTS.md")

        self.assertNotEqual(refused_code, 0, refused)
        self.assertEqual(refused["reasons"], ["Git worktree is not clean"], refused)

    def test_an_unsafe_existing_plane_ancestor_is_refused_before_the_plane_is_created(self) -> None:
        """The ancestor check has to run BEFORE the first `mkdir`, not after it.

        `_validate_plane_records` reaches `_assert_plane_ancestors` only when the plane root
        already exists, so on the CREATING path -- the only path that writes under an
        unvalidated ancestor -- the check used to run after `_mkdir_plane_root` had already
        made `ccodex/`, `activation/`, and the key directory beneath an other-writable home.
        Positive control: the same apply at 0700 commits and creates exactly those directories.
        """
        self.state_home.mkdir(parents=True)
        # chmod, not the `mkdir` mode: the umask would have masked the other-write bit off and
        # the case would then assert nothing.
        os.chmod(self.state_home, 0o757)
        self.assertTrue(stat.S_IMODE(self.state_home.stat().st_mode) & 0o002)

        plan_path, grant_path = self._documents()
        refused, refused_code = ap.apply_command(plan_path, self.manifest, grant_path)

        self.assertNotEqual(refused_code, 0, refused)
        self.assertEqual(refused["status"], "foreign-state")
        self.assertIn("unsafe state plane home", refused["reasons"])
        self.assertEqual(sorted(item.name for item in self.state_home.iterdir()), [], "nothing may be created under an unsafe ancestor")
        self.assertFalse((self.target / "AGENTS.md").exists())
        # `effect: none` here is now DERIVED from an empty effect ledger rather than asserted
        # about a pointer that had already been written. The earlier revision of this case pinned
        # the opposite -- pointer present, `effect: none` -- on the argument that a pointer holds
        # no operation, grant, receipt, or payload. That argument does not survive this class's
        # own evidence: a pointer changes what every later invocation REPORTS about this target,
        # because with one a moved checkout is exit 4 `effect-unknown` where without one it is
        # `inactive` at 0 (see `test_a_recorded_plane_root_that_cannot_be_resolved_...`). So the
        # pointer write is an admitted effect, and the fix is to refuse BEFORE it rather than to
        # reclassify the refusal: `_make_layout` now asserts the plane's ancestors before writing
        # the pointer. `admitted_effects` is the positive control on the channel -- it is present
        # and empty, so `effect: none` is a derived statement about a ledger this result carries,
        # not the absence of a field.
        self.assertFalse(self._pointer(self.target).exists(), "no pointer may precede the ancestor check")
        self.assertEqual(refused["effect"], "none")
        self.assertEqual(refused["admitted_effects"], [])
        self.assertFalse(plane_root(self.target).exists())

        os.chmod(self.state_home, 0o700)
        applied, applied_code = ap.apply_command(plan_path, self.manifest, grant_path)

        self.assertEqual(applied_code, 0, applied)
        self.assertTrue(plane_receipts(self.target).is_dir())

    def test_a_crash_in_one_checkout_never_refuses_another(self) -> None:
        """The probe is keyed per target, so it does not refuse the whole state home.

        A shared plane holds one entry per checkout; a sibling's unresolved journal is not
        this target's business, in either selection.
        """
        sibling = self.root / "sibling"
        sibling.mkdir()
        init_repo(sibling)
        self._crash_after_publish(sibling)
        self._unresolved_journal(plane_transactions(sibling))

        for selection in (None, ap.PLANE_REPO_LOCAL):
            with self.subTest(selection=selection or "default"):
                set_environment(self, ap.PLANE_SELECTION_ENV, selection)
                inspected, inspect_code = ap.recover_inspect_command(self.target)
                observed, status_code = ap.status_command(self.target)

                self.assertEqual(inspect_code, 0, inspected)
                self.assertEqual(inspected["status"], "inactive")
                self.assertEqual(status_code, 0, observed)
                self.assertEqual(observed["status"], "inactive")


class EffectLedgerDerivationTests(unittest.TestCase):
    """Every mutating step admits its effect, and no refusal after one is a clean refusal.

    This class exists because targeted review does not find this defect class. Six instances of
    it have landed in this project across five surfaces, twice as the fix for the previous one,
    and every raise site is a fresh chance to reintroduce it: 312 `ActivationError` raises are
    reachable from `apply_command` and the recover verbs. Reviewing them one at a time is what
    failed. So instead of one case per raise site, these cases pin the two halves of the
    derivation that make every raise site safe at once:

      * `test_every_mutating_step_admits_its_effect_in_order` pins the exact ordered ledger of a
        complete apply, in both plane selections and for the no-op audit. Deleting ANY `_admit`
        from any primitive changes that list, so an unadmitted mutating step is a test failure
        rather than a defect waiting for the raise site that reaches it.
      * `test_a_refusal_after_any_admitted_effect_is_never_a_clean_refusal` injects a refusal
        after each admission in turn -- a code-3 `refused`, the exact thing a raise site may no
        longer decide -- and requires the report to escalate. It is a sweep over the whole
        program, not a sample of it.

    Neither case asserts "something refused". They assert the ledger's contents and the exact
    escalated classification, because a blanket answer in either direction passes an assertion
    that only counts refusals.
    """

    EXPECTED_DEFAULT = [
        "created directory <target>/.agentic-sdlc",
        "created private metadata plane.<digest>.json",
        "created state plane ancestor <home>",
        "created state plane ancestor ccodex",
        "created state plane ancestor activation",
        "created private directory <digest>",
        "created private metadata intent.<id>.json",
        "created private directory receipts",
        "created private directory transactions",
        "created private directory <id>",
        "created private directory grants",
        "created private directory stage",
        "created private directory backup",
        "created private directory progress-history",
        "created private directory discard",
        "renamed intent.<id>.json onto operation.json (flags 1)",
        "created private metadata progress.json",
        "created private metadata 0001.json",
        "created the staged payload",
        "renamed 0000.payload.next onto 0000.payload (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000000.json (flags 1)",
        "renamed 0000.payload onto AGENTS.md (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000001.json (flags 1)",
        "created private metadata commit.json",
        "created private metadata receipt.json.next",
        "renamed receipt.json.next onto <id>.json (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000002.json (flags 1)",
    ]
    # The repo-local override is the same journal without the plane pointer or the plane's
    # operator-owned ancestors, because that plane IS the target's own subdirectory. It is kept
    # as a second expected list rather than derived from the first, so that a change which
    # quietly moves an effect from one selection to the other cannot pass both.
    EXPECTED_REPO_LOCAL = [
        "created private directory .agentic-sdlc",
        "created private metadata .agentic-sdlc.intent.<id>.json",
        "created private directory receipts",
        "created private directory transactions",
        "created private directory <id>",
        "created private directory grants",
        "created private directory stage",
        "created private directory backup",
        "created private directory progress-history",
        "created private directory discard",
        "renamed .agentic-sdlc.intent.<id>.json onto operation.json (flags 1)",
        "created private metadata progress.json",
        "created private metadata 0001.json",
        "created the staged payload",
        "renamed 0000.payload.next onto 0000.payload (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000000.json (flags 1)",
        "renamed 0000.payload onto AGENTS.md (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000001.json (flags 1)",
        "created private metadata commit.json",
        "created private metadata receipt.json.next",
        "renamed receipt.json.next onto <id>.json (flags 1)",
        "created private metadata progress.json.next",
        "renamed progress.json.next onto progress.json (flags 2)",
        "renamed progress.json.next onto 00000000000000000002.json (flags 1)",
    ]
    EXPECTED_FIRST_NOOP = [
        "created directory <target>/.agentic-sdlc",
        "created private metadata plane.<digest>.json",
        "created state plane ancestor <home>",
        "created state plane ancestor ccodex",
        "created state plane ancestor activation",
        "created private directory <digest>",
        "created <plane>/noop.<id>.json",
    ]

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes(ap.canonical_bytes(manifest()))
        self.serial = 0
        # One scratch activation, only to capture the exact bytes the manifest renders. A target
        # already holding them plans as a no-op, which is the one way to reach `_apply_noop`
        # without a prior effectful apply having already created the plane.
        scratch = self._target("scratch")
        scratch_result, scratch_code = self._apply(scratch)
        self.assertEqual(scratch_code, 0, scratch_result)
        self.rendered = (scratch / "AGENTS.md").read_bytes()

    def _target(self, name: str) -> Path:
        """A fresh repository under a fresh state plane home, both inside this case's tree."""
        home = self.root / f"state-{name}"
        set_environment(self, "XDG_STATE_HOME", str(home))
        target = self.root / name
        target.mkdir()
        init_repo(target)
        return target

    def _documents(self, target: Path) -> tuple[Path, Path, dict]:
        planned, code = ap.plan_command(target, self.manifest, "AGENTS.md")
        self.assertEqual(code, 0, planned)
        plan = planned["plan"]
        serial = self.serial
        self.serial = serial + 1
        plan_path = self.root / f"plan-{serial}.json"
        plan_path.write_bytes(ap.canonical_bytes(plan))
        instant = now()
        grant = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "5" * 30 + format(serial, "02x"), "operation": "apply",
            "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
            "plan_digest": ap.digest_record(plan), "operation_id": None, "operation_digest": None, "decision": None,
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        grant_path = self.root / f"grant-{serial}.json"
        grant_path.write_bytes(ap.canonical_bytes(grant))
        return plan_path, grant_path, plan

    def _apply(self, target: Path, *, hook=None) -> tuple[dict, int]:
        """One apply, optionally with the engine's own admission seam wrapped.

        The seam is `_admit` itself, in the planner's globals. Wrapping it is what makes this a
        sweep rather than a sample: it observes and interrupts EVERY mutating step, including any
        added later, without a test-only hook in the engine.
        """
        plan_path, grant_path, _ = self._documents(target)
        planner_globals = ap._admit.__globals__
        original = planner_globals["_admit"]
        if hook is not None:
            planner_globals["_admit"] = lambda effect: hook(original, effect)
        try:
            return ap.apply_command(plan_path, self.manifest, grant_path)
        finally:
            planner_globals["_admit"] = original

    def _normalize(self, effect: str, target: Path) -> str:
        """Strip the one-run identities so the ledger can be asserted as an exact ordered list."""
        home = Path(os.environ["XDG_STATE_HOME"])
        text = effect.replace(str(plane_root(target)), "<plane>").replace(str(target), "<target>")
        text = re.sub(rf"\b{re.escape(home.name)}\b", "<home>", text)
        text = re.sub(r"\b[0-9a-f]{64}\b", "<digest>", text)
        return re.sub(r"\b[0-9a-f]{32}\b", "<id>", text)

    def _sequence(self, target: Path) -> tuple[list[str], dict, int]:
        recorded: list[str] = []

        def record(original, effect):
            recorded.append(effect)
            return original(effect)

        result, code = self._apply(target, hook=record)
        return [self._normalize(item, target) for item in recorded], result, code

    def _noop_target(self, name: str) -> Path:
        target = self._target(name)
        (target / "AGENTS.md").write_bytes(self.rendered)
        git(target, "add", "AGENTS.md")
        git(target, "commit", "-m", "already rendered")
        return target

    def test_every_mutating_step_admits_its_effect_in_order(self) -> None:
        """The exact ledger of a complete apply, which is what makes every admission required.

        A step that mutates the tree without admitting is invisible to `_report_failure`, so the
        next refusal downstream of it reports a clean 3 over its effect. That is the whole
        defect, and it cannot be found by reading raise sites. Here it is found by the shape of
        the ledger: this list is the closed inventory of what one apply does, in order.
        """
        target = self._target("default")
        default, result, code = self._sequence(target)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["effect"], "committed")
        self.assertEqual(default, self.EXPECTED_DEFAULT)
        # The SAME inventory read off the result the command actually returns, in its revised
        # wording. Two assertions rather than one, because `admit` and `revise` are separate
        # steps and only the second one proves an effect's outcome was recorded: deleting a
        # `revise` leaves a "created" entry for a file that was written, and this catches it.
        self.assertEqual(
            [self._normalize(item, target) for item in result["admitted_effects"]],
            [item.replace("created private metadata", "wrote private metadata").replace("created the staged payload", "wrote the staged payload") for item in self.EXPECTED_DEFAULT],
        )

        select_repo_local_plane(self)
        local_target = self._target("local")
        repo_local, local_result, local_code = self._sequence(local_target)
        self.assertEqual(local_code, 0, local_result)
        self.assertEqual(repo_local, self.EXPECTED_REPO_LOCAL)
        set_environment(self, ap.PLANE_SELECTION_ENV, None)

        # The no-op audit path writes its own smaller journal, and it is the ONE apply shape
        # whose first effect is the plane pointer with no transaction behind it.
        noop = self._noop_target("noop")
        audit, audit_result, audit_code = self._sequence(noop)
        self.assertEqual(audit_code, 0, audit_result)
        self.assertEqual(audit_result["status"], "no-op")
        self.assertEqual(audit_result["effect"], "audit_only")
        self.assertEqual(audit, self.EXPECTED_FIRST_NOOP)

    def test_a_refusal_after_any_admitted_effect_is_never_a_clean_refusal(self) -> None:
        """A refusal injected after EACH admission in turn, over the whole apply.

        The injected error is `refused` at code 3 -- Decision 9's "clean refusal BEFORE any
        journal or product effect" -- raised at a point where that is false by construction. Not
        one of these may be reported as 3, or as 1 or 2, and each must carry the ledger.

        POSITIVE CONTROL, and it is the same control the class needs against a blanket answer:
        the uninjected apply asserted in the case above commits at 0, and every injection here
        is asserted to carry a NON-EMPTY ledger whose length matches the injection point, so a
        change that reported 4 unconditionally would not satisfy the length.
        """
        for selection in (None, ap.PLANE_REPO_LOCAL):
            expected = self.EXPECTED_DEFAULT if selection is None else self.EXPECTED_REPO_LOCAL
            set_environment(self, ap.PLANE_SELECTION_ENV, selection)
            for index in range(len(expected)):
                with self.subTest(selection=selection or "default", after=index, effect=expected[index]):
                    state = {"count": 0}

                    def hook(original, effect, state=state, index=index):
                        token = original(effect)
                        state["count"] += 1
                        if state["count"] == index + 1:
                            raise ap.ActivationError("refused", f"injected after admission {index}", 3)
                        return token

                    target = self._target(f"sweep-{selection or 'default'}-{index}")
                    result, code = self._apply(target, hook=hook)
                    self.assertNotIn(code, {1, 2, 3}, result)
                    if code == 0:
                        # An intermediate handler absorbed the injection and the operation
                        # genuinely completed. That is a truthful terminal claim, not a defect.
                        self.assertEqual(result["effect"], "committed", result)
                        continue
                    self.assertEqual(code, 4, result)
                    self.assertEqual(result["status"], "effect-unknown", result)
                    self.assertEqual(result["effect"], "effect_unknown", result)
                    self.assertGreaterEqual(len(result["admitted_effects"]), index + 1, result)
                    # The entry at the injection point is the one the ledger has NOT yet
                    # revised: the raise lands between `admit` and `revise`, which is exactly
                    # the window where an effect is true and its outcome is not yet known.
                    self.assertEqual(self._normalize(result["admitted_effects"][index], target), expected[index], result)
        set_environment(self, ap.PLANE_SELECTION_ENV, None)

    def test_the_result_renderer_has_no_default_effect(self) -> None:
        """The structural half of the fix, pinned structurally because no input can reach it.

        `_result`'s `effect` parameter used to default to `"none"`, and that default is what let
        one `except` clause answer for 312 raise sites. Restoring it changes no current behaviour
        -- every call site passes the argument -- so there is no distinguishing INPUT and no
        ordinary test can hold the line. What the default actually costs is paid by the NEXT
        result added: without it, omitting the effect is a `TypeError` at the call, and with it
        the omission silently claims no effect. So the signature itself is the assertion.

        `_report_failure` is asserted to be the only place a refusal's effect is settled, by the
        same reasoning: a second such site is how the class came back twice before.
        """
        import inspect

        signature = inspect.signature(ap._result)
        effect = signature.parameters["effect"]
        self.assertIs(effect.default, inspect.Parameter.empty, "`effect` must have no default")
        self.assertIs(effect.kind, inspect.Parameter.KEYWORD_ONLY)
        source = Path(ap.__file__).read_text() if not ap.__file__.endswith("activation_planner.py") else (ROOT / "skills" / "agentic-sdlc" / "tools" / "activation-planner.py").read_text()
        # Every `except ActivationError` in a command handler must delegate; a handler that
        # renders its own `_result` is a second decision point, which is the defect's shape.
        self.assertEqual(source.count("def _report_failure("), 1)
        self.assertEqual(source.count("_report_failure("), 1 + 6, "plan, apply, status, inspect, finish, rollback, and the definition")

    def test_an_inactive_target_keeps_its_reason_on_every_command_but_inspect(self) -> None:
        """`recover inspect` alone answers `inactive` with no reason; the others keep theirs.

        Suppressing the reason by STATUS rather than by command would drop `recover finish`'s
        explanation of why it did nothing. The two arms are each other's control.
        """
        target = self._target("inactive")
        instant = now()
        grant = {
            "schema": ap.GRANT_SCHEMA, "grant_id": "9" * 32, "operation": "recover",
            "target": {"path": str(target), "root_dev": target.stat().st_dev, "root_ino": target.stat().st_ino},
            "plan_digest": None, "operation_id": "a" * 32, "operation_digest": "b" * 64, "decision": "finish",
            "issued_at": stamp(instant), "expires_at": stamp(instant + timedelta(minutes=5)),
        }
        path = self.root / "inactive-recovery.json"
        path.write_bytes(ap.canonical_bytes(grant))

        finished, finish_code = ap.recover_finish_command(target, path)
        inspected, inspect_code = ap.recover_inspect_command(target)

        self.assertEqual(finish_code, 0, finished)
        self.assertEqual(finished["status"], "inactive")
        self.assertEqual(finished["effect"], "none")
        self.assertEqual(finished["reasons"], ["no unique active transaction"], finished)
        self.assertEqual(inspect_code, 0, inspected)
        self.assertEqual(inspected["status"], "inactive")
        self.assertEqual(inspected["effect"], "none")
        self.assertEqual(inspected["reasons"], [], inspected)
        for result in (finished, inspected):
            self.assertEqual(result["admitted_effects"], [], result)

    def test_a_no_op_apply_refuses_an_unsafe_plane_home_before_writing_a_pointer(self) -> None:
        """`_apply_noop` takes the same order as `_make_layout`, and for the same reason.

        The audit path creates the pointer and the plane root exactly as the effectful path does,
        so it needs the ancestor check in front of the pointer too. Without it the refusal lands
        after a pointer write and is honestly exit 4 -- correct, but worse for the operator than
        refusing before writing anything.
        """
        target = self._noop_target("unsafe")
        home = Path(os.environ["XDG_STATE_HOME"])
        home.mkdir(parents=True)
        os.chmod(home, 0o757)
        self.assertTrue(stat.S_IMODE(home.stat().st_mode) & 0o002)

        result, code = self._apply(target)

        self.assertEqual(code, 1, result)
        self.assertEqual(result["status"], "foreign-state")
        self.assertIn("unsafe state plane home", result["reasons"])
        self.assertEqual(result["effect"], "none")
        self.assertEqual(result["admitted_effects"], [], result)
        self.assertFalse((target / ".agentic-sdlc").exists(), "no pointer may precede the ancestor check")
        self.assertEqual(sorted(item.name for item in home.iterdir()), [])

        # POSITIVE CONTROL: the same no-op apply at 0700 completes, so the refusal above came
        # from the mode and not from an unrelated break in the fixture.
        os.chmod(home, 0o700)
        allowed, allowed_code = self._apply(target)
        self.assertEqual(allowed_code, 0, allowed)
        self.assertEqual(allowed["status"], "no-op")
        self.assertEqual(allowed["effect"], "audit_only")


if __name__ == "__main__":
    unittest.main()
