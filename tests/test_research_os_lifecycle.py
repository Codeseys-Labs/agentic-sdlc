from __future__ import annotations

from contextlib import contextmanager
import errno
import hashlib
import importlib.util
import json
import os
import socket
import stat
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "skills" / "codex-research-os" / "scripts" / "install_research_os.py"
SPEC = importlib.util.spec_from_file_location("research_os_installer_lifecycle", SCRIPT)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)

SKILL = SCRIPT.parents[1] / "SKILL.md"
OPERATING_MODEL = SCRIPT.parents[1] / "references" / "operating-model.md"


def read_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and not any(part.startswith(".research-os-") for part in path.relative_to(root).parts)
    }


def content_files(root: Path) -> dict[str, str]:
    tree = read_tree(root)
    tree.pop(installer.MANIFEST_REL, None)
    return tree


def expected_state_path(state_root: Path, target: Path) -> Path:
    physical = os.path.normcase(str(target.resolve()))
    key = hashlib.sha256(os.fsencode(physical)).hexdigest()
    return state_root / "agentic-sdlc-research-os" / key / "state.json"


@contextmanager
def isolated_state() -> Path:
    with tempfile.TemporaryDirectory(prefix="research-os-state-") as directory:
        root = Path(directory)
        env = {
            "XDG_STATE_HOME": str(root),
            "LOCALAPPDATA": str(root),
        }
        with mock.patch.dict(os.environ, env, clear=False):
            yield root


def private_payloads(root: Path) -> list[Path]:
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and any(part.startswith(".research-os-") for part in path.relative_to(root).parts)
    ]


class OwnershipStateTests(unittest.TestCase):
    maxDiff = None

    def test_foreign_state_symlink_is_refused_without_target_mutation(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink fixture unavailable")
        files = {"research/status.md": "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            state_path = expected_state_path(state_root, root)
            state_path.parent.mkdir(parents=True)
            foreign = state_root / "foreign-state.json"
            valid = installer._empty_state(root, installer._path_identity(root))
            foreign.write_text(json.dumps(valid), encoding="utf-8")
            try:
                state_path.symlink_to(foreign)
            except OSError as exc:
                self.skipTest(f"state symlink fixture unavailable: {exc}")

            with self.assertRaises(Exception):
                installer.apply_install(root, files=files)

            self.assertEqual(json.loads(foreign.read_text(encoding="utf-8")), valid)
            self.assertFalse((root / "research/status.md").exists())

    def test_manifest_records_every_owned_file_with_matching_digest(self) -> None:
        files = installer.build_files("example")
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            installer.apply_install(root, files=files)

            manifest_path = root / installer.MANIFEST_REL
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], installer.MANIFEST_SCHEMA)
            self.assertEqual(manifest["state"], "complete")
            self.assertEqual(set(manifest["files"]), set(files))
            self.assertNotIn(installer.MANIFEST_REL, manifest["files"])
            for rel, digest in manifest["files"].items():
                self.assertEqual(digest, installer.content_digest(files[rel]))
                self.assertEqual(digest, installer.path_digest(root / rel))

    def test_unrecorded_preexisting_canonical_file_is_foreign_not_adopted(self) -> None:
        files = {"research/status.md": "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            target = root / "research/status.md"
            target.parent.mkdir()
            target.write_text(files["research/status.md"], encoding="utf-8")
            before_identity = target.stat().st_ino

            dry = installer.apply_install(root, files=files, dry_run=True)
            applied = installer.apply_install(root, files=files)

            self.assertEqual(dry, applied)
            self.assertEqual(applied["research/status.md"], "skipped-foreign")
            self.assertEqual(target.stat().st_ino, before_identity)
            self.assertFalse((root / installer.MANIFEST_REL).exists())
            self.assertFalse(expected_state_path(state_root, root).exists())

    def test_malformed_and_newer_external_state_fail_before_target_mutation(self) -> None:
        for state_bytes in (b"{broken", b'{"version": 999, "entries": {}, "manifest": null, "transactions": {}, "conflicts": {}, "target": {}}'):
            with self.subTest(state=state_bytes), tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                state_path = expected_state_path(state_root, root)
                state_path.parent.mkdir(parents=True)
                state_path.write_bytes(state_bytes)

                with self.assertRaises(Exception):
                    installer.apply_install(root, files={"research/status.md": "CANONICAL\n"})

                self.assertFalse((root / "research/status.md").exists())
                self.assertEqual(state_path.read_bytes(), state_bytes)

    def test_replaced_target_root_identity_fails_closed(self) -> None:
        files = {"research/status.md": "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as parent_directory, isolated_state():
            parent = Path(parent_directory)
            root = parent / "target"
            root.mkdir()
            installer.apply_install(root, files=files)
            retired = parent / "retired"
            root.rename(retired)
            root.mkdir()
            foreign = root / "research/status.md"
            foreign.parent.mkdir()
            foreign.write_text("FOREIGN\n", encoding="utf-8")

            with self.assertRaises(Exception):
                installer.apply_install(root, files=files, force=True)

            self.assertEqual(foreign.read_text(encoding="utf-8"), "FOREIGN\n")
            self.assertEqual((retired / "research/status.md").read_text(encoding="utf-8"), "CANONICAL\n")


class DryRunParityTests(unittest.TestCase):
    maxDiff = None

    def test_cli_returns_nonzero_for_partial_refusal(self) -> None:
        with mock.patch.object(installer, "build_files", return_value={"research/status.md": "CANONICAL\n"}), mock.patch.object(
            installer,
            "apply_install",
            return_value={"research/status.md": "skipped-foreign"},
        ), mock.patch.object(sys, "argv", [str(SCRIPT), "--target", "."]):
            self.assertNotEqual(installer.main(), 0)

    def test_missing_target_refuses_before_any_scaffold_is_planned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("--target", result.stderr)
            self.assertEqual(read_tree(root), {})

    def test_dry_run_writes_nothing_and_matches_apply(self) -> None:
        files = installer.build_files("example")
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            planned = installer.apply_install(root, files=files, dry_run=True)
            self.assertEqual(read_tree(root), {})
            self.assertFalse(expected_state_path(state_root, root).exists())
            self.assertTrue(planned)
            self.assertEqual({state for state in planned.values()}, {"created"})

            applied = installer.apply_install(root, files=files)
            self.assertEqual(applied, planned)

    def test_dry_run_on_installed_tree_is_byte_equal_and_all_unchanged(self) -> None:
        files = installer.build_files("example")
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            installer.apply_install(root, files=files)
            before_tree = read_tree(root)
            state_path = expected_state_path(state_root, root)
            before_state = state_path.read_bytes()

            planned = installer.apply_install(root, files=files, dry_run=True)

            self.assertEqual(read_tree(root), before_tree)
            self.assertEqual(state_path.read_bytes(), before_state)
            self.assertEqual({state for state in planned.values()}, {"unchanged"})

    def test_non_utf8_and_unreadable_leaf_dry_run_apply_parity(self) -> None:
        files = {"research/status.md": "CANONICAL\n"}
        fixtures = (b"\xff\xfe\xfd", b"unreadable")
        for index, payload in enumerate(fixtures):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                target = root / "research/status.md"
                target.parent.mkdir()
                target.write_bytes(payload)
                if index == 1 and os.name != "nt":
                    target.chmod(0)
                try:
                    dry = installer.apply_install(root, files=files, dry_run=True)
                    applied = installer.apply_install(root, files=files)
                finally:
                    if index == 1 and os.name != "nt":
                        target.chmod(0o600)

                self.assertEqual(dry, applied)
                self.assertEqual(applied["research/status.md"], "skipped-foreign")
                self.assertEqual(target.read_bytes(), payload)
                self.assertFalse((root / installer.MANIFEST_REL).exists())
                self.assertFalse(expected_state_path(state_root, root).exists())


class DeterminismTests(unittest.TestCase):
    def _digest_build_files(self, hash_seed: str) -> str:
        program = (
            "import importlib.util, hashlib, json\n"
            f"spec = importlib.util.spec_from_file_location('inst', {str(SCRIPT)!r})\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "files = m.build_files('example')\n"
            "digests = {rel: hashlib.sha256(content.encode('utf-8')).hexdigest() for rel, content in files.items()}\n"
            "print(hashlib.sha256(json.dumps(digests, sort_keys=True).encode('utf-8')).hexdigest())\n"
        )
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        result = subprocess.run([sys.executable, "-c", program], env=env, text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def test_build_files_is_byte_stable_across_hash_seeds(self) -> None:
        self.assertEqual(len({self._digest_build_files(seed) for seed in ("0", "1", "2", "13")}), 1)


class ExactOwnershipLifecycleTests(unittest.TestCase):
    maxDiff = None

    def test_exact_owned_upgrade_and_force_restore(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            target = root / rel
            installer.apply_install(root, files={rel: "VERSION-1\n"})
            identity = target.stat().st_ino

            upgraded = installer.apply_install(root, files={rel: "VERSION-2\n"})
            self.assertEqual(upgraded[rel], "updated")
            self.assertEqual(target.read_text(encoding="utf-8"), "VERSION-2\n")

            target.write_text("USER EDIT\n", encoding="utf-8")
            skipped = installer.apply_install(root, files={rel: "VERSION-2\n"})
            self.assertEqual(skipped[rel], "skipped-modified")
            self.assertEqual(target.read_text(encoding="utf-8"), "USER EDIT\n")

            restored = installer.apply_install(root, files={rel: "VERSION-2\n"}, force=True)
            self.assertEqual(restored[rel], "restored")
            self.assertEqual(target.read_text(encoding="utf-8"), "VERSION-2\n")
            self.assertNotEqual(target.stat().st_ino, identity)

        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            target = root / rel
            installer.apply_install(root, files={rel: "VERSION-1\n"})
            replacement = root / "replacement"
            replacement.write_text("FOREIGN INODE\n", encoding="utf-8")
            os.replace(replacement, target)

            forced = installer.apply_install(root, files={rel: "VERSION-2\n"}, force=True)

            self.assertEqual(forced[rel], "skipped-foreign")
            self.assertEqual(target.read_text(encoding="utf-8"), "FOREIGN INODE\n")

    def test_removed_template_cleanup_and_modified_preservation(self) -> None:
        rel = "research/old.md"
        for variant in ("unchanged", "edited", "replaced"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                target = root / rel
                installer.apply_install(root, files={rel: "OLD CANONICAL\n"})
                if variant == "edited":
                    target.write_text("USER NOTES\n", encoding="utf-8")
                elif variant == "replaced":
                    replacement = root / "replacement"
                    replacement.write_text("FOREIGN REPLACEMENT\n", encoding="utf-8")
                    os.replace(replacement, target)

                actions = installer.apply_install(root, files={})

                if variant == "unchanged":
                    self.assertEqual(actions[rel], "removed")
                    self.assertFalse(target.exists())
                else:
                    self.assertEqual(actions[rel], "skipped-remove-modified")
                    expected = "USER NOTES\n" if variant == "edited" else "FOREIGN REPLACEMENT\n"
                    self.assertEqual(target.read_text(encoding="utf-8"), expected)
                    state = json.loads(expected_state_path(state_root, root).read_text(encoding="utf-8"))
                    self.assertIn(rel, state["entries"])
                    self.assertIn(rel, state["conflicts"])
                    retried = installer.apply_install(root, files={})
                    self.assertEqual(retried[rel], "skipped-remove-modified")
                    self.assertEqual(target.read_text(encoding="utf-8"), expected)


class TransactionSafetyTests(unittest.TestCase):
    maxDiff = None

    def test_interrupted_create_recovery_is_idempotent(self) -> None:
        rel = "research/status.md"
        files = {rel: "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            real_persist = installer._persist_candidate
            interrupted = False

            def crash_after_publish(path, state, candidate, target, identity):
                nonlocal interrupted
                result = real_persist(path, state, candidate, target, identity)
                if (
                    not interrupted
                    and rel in candidate.get("transactions", {})
                    and candidate["transactions"][rel]["phase"] == "committed"
                ):
                    interrupted = True
                    raise OSError("simulated crash after durable ownership commit")
                return result

            with mock.patch.object(installer, "_persist_candidate", side_effect=crash_after_publish):
                with self.assertRaises(OSError):
                    installer.apply_install(root, files=files)

            self.assertEqual((root / rel).read_text(encoding="utf-8"), "CANONICAL\n")
            state_path = expected_state_path(state_root, root)
            interrupted_state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn(rel, interrupted_state["transactions"])

            first = installer.apply_install(root, files=files)
            tree_after_first = read_tree(root)
            state_after_first = state_path.read_bytes()
            second = installer.apply_install(root, files=files)

            self.assertEqual(first[rel], "unchanged")
            self.assertEqual(second, first)
            self.assertEqual(read_tree(root), tree_after_first)
            self.assertEqual(state_path.read_bytes(), state_after_first)

    def test_cleanup_namespace_swap_preserves_foreign_replacement(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            real_inspect = installer._inspect_absolute
            real_publish = installer._publish_staged_file
            published = False
            swapped = False

            def mark_published(*args, **kwargs):
                nonlocal published
                result = real_publish(*args, **kwargs)
                published = True
                return result

            def swap_after_cleanup_check(path: Path):
                nonlocal swapped
                observed = real_inspect(path)
                if published and not swapped and path.name == "witness" and observed.state == "regular-readable":
                    swapped = True
                    original = path.with_name("owned-witness")
                    os.replace(path, original)
                    path.write_text("FOREIGN CLEANUP RACE\n", encoding="utf-8")
                return observed

            with mock.patch.object(installer, "_publish_staged_file", side_effect=mark_published), mock.patch.object(
                installer, "_inspect_absolute", side_effect=swap_after_cleanup_check
            ):
                with self.assertRaises(installer.RecoveryConflict):
                    installer.apply_install(root, files={rel: "CANONICAL\n"})

            foreign = [
                path
                for path in (root / "research").rglob("*")
                if path.is_file() and path.read_bytes() == b"FOREIGN CLEANUP RACE\n"
            ]
            self.assertTrue(foreign)

    def test_partial_stage_write_never_publishes_leaf_and_retry_converges(self) -> None:
        rel = "research/status.md"
        files = {rel: "CANONICAL CONTENT\n"}
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            real_write = installer.os.write
            failed = False

            def partial_then_fail(fd: int, data: bytes) -> int:
                nonlocal failed
                if not failed:
                    failed = True
                    real_write(fd, data[:4])
                    raise OSError("simulated partial stage write")
                return real_write(fd, data)

            with mock.patch.object(installer.os, "write", side_effect=partial_then_fail):
                with self.assertRaises(OSError):
                    installer.apply_install(root, files=files)

            self.assertFalse((root / rel).exists())
            state_path = expected_state_path(state_root, root)
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertFalse(state["transactions"])
            for payload in private_payloads(root):
                self.assertNotEqual(payload.read_bytes(), b"CANO")

            actions = installer.apply_install(root, files=files)
            self.assertEqual(actions[rel], "created")
            self.assertEqual((root / rel).read_text(encoding="utf-8"), files[rel])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn(rel, state["entries"])

    def test_delete_namespace_swap_never_deletes_foreign_replacement(self) -> None:
        rel = "research/old.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            target = root / rel
            installer.apply_install(root, files={rel: "OWNED OLD\n"})
            displaced_owned = root / "owned-displaced-by-racer"
            real_rename = installer._rename_noreplace
            swapped = False

            def swap_then_rename(source, destination, **kwargs):
                nonlocal swapped
                if not swapped and Path(source) == target:
                    swapped = True
                    os.replace(target, displaced_owned)
                    target.write_text("FOREIGN REPLACEMENT\n", encoding="utf-8")
                return real_rename(source, destination, **kwargs)

            with mock.patch.object(installer, "_rename_noreplace", side_effect=swap_then_rename):
                with self.assertRaises(Exception):
                    installer.apply_install(root, files={})

            self.assertEqual(target.read_text(encoding="utf-8"), "FOREIGN REPLACEMENT\n")
            state_path = expected_state_path(Path(os.environ["XDG_STATE_HOME"]), root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn(rel, state["transactions"])
            recoverable = [path for path in private_payloads(root) if path.read_bytes() == b"OWNED OLD\n"]
            self.assertTrue(recoverable, private_payloads(root))

    def test_manifest_destination_swap_is_refused(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            files = {rel: "CANONICAL\n"}
            installer.apply_install(root, files=files)
            manifest = root / installer.MANIFEST_REL
            old_manifest = root / "old-manifest"
            real_publish = installer._publish_manifest

            def swap_then_publish(*args, **kwargs):
                os.replace(manifest, old_manifest)
                manifest.write_text("FOREIGN MANIFEST\n", encoding="utf-8")
                manifest.chmod(0o640)
                return real_publish(*args, **kwargs)

            with mock.patch.object(installer, "_publish_manifest", side_effect=swap_then_publish):
                with self.assertRaises(Exception):
                    installer.apply_install(root, files=files)

            self.assertEqual(manifest.read_text(encoding="utf-8"), "FOREIGN MANIFEST\n")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o640)

    def test_manifest_stage_swap_is_refused_and_recovery_conflicts(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            real_publish = installer._publish_staged_file
            swapped = False

            def swap_manifest_stage(stage, destination, *args, **kwargs):
                nonlocal swapped
                if not swapped and Path(destination) == root / installer.MANIFEST_REL:
                    swapped = True
                    foreign = stage.artifact.payload.with_name("foreign")
                    foreign.write_text("FOREIGN TEMP RACE\n", encoding="utf-8")
                    os.replace(foreign, stage.artifact.payload)
                return real_publish(stage, destination, *args, **kwargs)

            with mock.patch.object(installer, "_publish_staged_file", side_effect=swap_manifest_stage):
                with self.assertRaises(installer.RecoveryConflict):
                    installer.apply_install(root, files={rel: "CANONICAL\n"})

            self.assertFalse((root / installer.MANIFEST_REL).exists())
            canonical_manifests = [
                path for path in private_payloads(root)
                if b"research-os-ownership-manifest/v1" in path.read_bytes()
            ]
            self.assertTrue(canonical_manifests, private_payloads(root))
            state_path = expected_state_path(Path(os.environ["XDG_STATE_HOME"]), root)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertIn("@manifest", state["transactions"])
            dry_state = state_path.read_bytes()
            planned = installer.apply_install(root, files={rel: "CANONICAL\n"}, dry_run=True)
            self.assertEqual(planned[rel], "unchanged")
            self.assertEqual(state_path.read_bytes(), dry_state)

    def test_preexisting_unowned_manifest_is_foreign(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
            root = Path(directory)
            manifest = root / installer.MANIFEST_REL
            manifest.parent.mkdir()
            manifest.write_text("FOREIGN MANIFEST\n", encoding="utf-8")
            manifest.chmod(0o644)

            with self.assertRaises(Exception):
                installer.apply_install(root, files={rel: "CANONICAL\n"})

            self.assertEqual(manifest.read_text(encoding="utf-8"), "FOREIGN MANIFEST\n")
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(manifest.stat().st_mode), 0o644)
            state_path = expected_state_path(state_root, root)
            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                self.assertIsNone(state["manifest"])

    def test_leaf_mutation_during_manifest_publication_cannot_return_success(self) -> None:
        rel = "research/status.md"
        with tempfile.TemporaryDirectory() as directory, isolated_state():
            root = Path(directory)
            target = root / rel
            real_publish = installer._publish_manifest

            def mutate_then_publish(*args, **kwargs):
                target.write_text("FOREIGN AFTER CHECK\n", encoding="utf-8")
                return real_publish(*args, **kwargs)

            with mock.patch.object(installer, "_publish_manifest", side_effect=mutate_then_publish):
                with self.assertRaises(Exception):
                    installer.apply_install(root, files={rel: "CANONICAL\n"})

            self.assertEqual(target.read_text(encoding="utf-8"), "FOREIGN AFTER CHECK\n")
            self.assertFalse((root / installer.MANIFEST_REL).exists())


class SpecialFileAndDescriptorTests(unittest.TestCase):
    def test_windows_lock_initializes_one_byte_before_locking(self) -> None:
        class FakeMsvcrt:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def __init__(self) -> None:
                self.sizes: list[int] = []

            def locking(self, fd: int, mode: int, length: int) -> None:
                self.sizes.append(os.fstat(fd).st_size)
                if mode == self.LK_NBLCK and os.fstat(fd).st_size < 1:
                    raise OSError("cannot lock past EOF")

        fake = FakeMsvcrt()
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with mock.patch.object(installer.os, "name", "nt"), mock.patch.dict(sys.modules, {"msvcrt": fake}):
                with installer._state_lock(state_path):
                    pass
        self.assertGreaterEqual(fake.sizes[0], 1)

    def test_windows_cleanup_does_not_open_directory_with_posix_descriptor(self) -> None:
        artifact = installer.PrivateArtifact(Path("C:/stage"), Path("C:/stage/payload"), Path("C:/stage/witness"), "stat-v2:1:2:3")
        record = {
            "destination_identity": "stat-v2:1:4:5",
            "destination_type": "file",
            "digest": "a" * 64,
            "mode": 0o600,
            "ancestors": [],
        }
        observed = installer.ObservedLeaf("regular-readable", "stat-v2:1:4:5", "a" * 64, 0o666, ())
        with mock.patch.object(installer, "_platform_system", return_value="Windows"), mock.patch.object(
            installer,
            "_artifact_container_exact",
            return_value=True,
        ), mock.patch.object(installer, "_inspect_absolute", return_value=observed), mock.patch.object(
            installer.Path, "exists", return_value=True
        ), mock.patch.object(installer.Path, "iterdir", return_value=[artifact.witness]), mock.patch.object(
            installer,
            "_cleanup_artifact_windows",
        ) as cleanup_windows, mock.patch.object(installer, "_open_verified_directory") as open_directory:
            installer._cleanup_artifact(artifact, record)
        cleanup_windows.assert_called_once()
        open_directory.assert_not_called()

    def test_windows_staged_mode_uses_path_chmod(self) -> None:
        path = Path("C:/stage/payload")
        with mock.patch.object(installer, "_platform_system", return_value="Windows"), mock.patch.object(
            installer.os, "chmod"
        ) as chmod, mock.patch.object(installer.os, "fchmod", create=True) as fchmod:
            installer._set_staged_mode(7, path, 0o600)
        chmod.assert_called_once_with(path, 0o600)
        fchmod.assert_not_called()

    def test_windows_exact_owned_rerun_ignores_posix_mode_projection(self) -> None:
        record = {
            "destination_identity": "stat-v2:1:2:3",
            "destination_type": "file",
            "digest": "a" * 64,
            "mode": 0o600,
            "ancestors": [],
        }
        observed = installer.ObservedLeaf(
            "regular-readable",
            "stat-v2:1:2:3",
            "a" * 64,
            0o666,
            (),
        )
        with mock.patch.object(installer.os, "name", "nt"), mock.patch.object(installer, "_platform_system", return_value="Windows"):
            self.assertTrue(installer._exact_matches(observed, record))

    def _run_fixture(self, fixture: str) -> subprocess.CompletedProcess[str]:
        program = textwrap.dedent(
            f"""
            import importlib.util, os, pathlib, socket, sys, tempfile
            script = pathlib.Path({str(SCRIPT)!r})
            spec = importlib.util.spec_from_file_location('fixture_installer', script)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as state_dir:
                os.environ['XDG_STATE_HOME'] = state_dir
                root = pathlib.Path(root_dir)
                target = root / 'research/status.md'
                target.parent.mkdir()
                sock = None
                if {fixture!r} == 'fifo':
                    os.mkfifo(target)
                elif {fixture!r} == 'socket':
                    sock = socket.socket(socket.AF_UNIX)
                    sock.bind(str(target))
                elif {fixture!r} == 'device':
                    os.mknod(target, 0o600 | 0o20000, os.makedev(1, 3))
                try:
                    result = module.apply_install(root, files={{'research/status.md': 'CANONICAL\\n'}})
                    assert result['research/status.md'] == 'skipped-foreign', result
                finally:
                    if sock is not None:
                        sock.close()
            """
        )
        return subprocess.run([sys.executable, "-c", program], text=True, capture_output=True, timeout=1.0)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unavailable")
    def test_fifo_is_rejected_without_blocking(self) -> None:
        result = self._run_fixture("fifo")
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix sockets unavailable")
    def test_socket_is_rejected_without_blocking(self) -> None:
        result = self._run_fixture("socket")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_parent_dry_run_closes_all_descriptors(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("Linux descriptor accounting fixture")
        program = textwrap.dedent(
            f"""
            import importlib.util, os, pathlib, resource, sys, tempfile
            script = pathlib.Path({str(SCRIPT)!r})
            spec = importlib.util.spec_from_file_location('fd_installer', script)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            resource.setrlimit(resource.RLIMIT_NOFILE, (96, 96))
            with tempfile.TemporaryDirectory() as root_dir, tempfile.TemporaryDirectory() as state_dir:
                os.environ['XDG_STATE_HOME'] = state_dir
                root = pathlib.Path(root_dir)
                files = {{f'missing-{{i}}/leaf.md': 'x\\n' for i in range(180)}}
                before = len(list(pathlib.Path('/proc/self/fd').iterdir()))
                for _ in range(3):
                    actions = module.apply_install(root, files=files, dry_run=True)
                    assert set(actions.values()) == {{'created'}}
                after = len(list(pathlib.Path('/proc/self/fd').iterdir()))
                assert after == before, (before, after)
            """
        )
        result = subprocess.run([sys.executable, "-c", program], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class PathContainmentTests(unittest.TestCase):
    def test_symlinked_component_fails_closed_without_manifest(self) -> None:
        files = {"research/status.md": "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory, isolated_state():
            root = Path(directory)
            outside = Path(outside_directory)
            try:
                (root / "research").symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink fixture unavailable: {exc}")
            sentinel = outside / "status.md"
            sentinel.write_text("OUTSIDE SENTINEL\n", encoding="utf-8")

            with self.assertRaises(OSError):
                installer.apply_install(root, files=files)

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "OUTSIDE SENTINEL\n")
            self.assertFalse((root / installer.MANIFEST_REL).exists())

    def test_symlinked_leaf_fails_closed_without_manifest(self) -> None:
        files = {"research/status.md": "CANONICAL\n"}
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside_directory, isolated_state():
            root = Path(directory)
            outside = Path(outside_directory)
            (root / "research").mkdir()
            sentinel = outside / "sentinel.md"
            sentinel.write_text("OUTSIDE SENTINEL\n", encoding="utf-8")
            try:
                (root / "research/status.md").symlink_to(sentinel)
            except OSError as exc:
                self.skipTest(f"symlink fixture unavailable: {exc}")

            actions = installer.apply_install(root, files=files)

            self.assertEqual(actions["research/status.md"], "skipped-foreign")
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "OUTSIDE SENTINEL\n")
            self.assertFalse((root / installer.MANIFEST_REL).exists())

    def test_invalid_generated_keys_fail_before_any_write(self) -> None:
        invalid_files = [
            {"../escape.md": "CANONICAL\n"},
            {str(Path(tempfile.gettempdir()) / "absolute.md"): "CANONICAL\n"},
            {installer.MANIFEST_REL: "CANONICAL\n"},
            {"research\\status.md": "CANONICAL\n"},
            {"research//status.md": "CANONICAL\n"},
            {"research/./status.md": "CANONICAL\n"},
            {"research/\x00status.md": "CANONICAL\n"},
            {"": "CANONICAL\n"},
        ]
        for files in invalid_files:
            with self.subTest(files=files), tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                with self.assertRaises(ValueError):
                    installer.apply_install(root, files=files)
                self.assertEqual(read_tree(root), {})
                self.assertFalse(expected_state_path(state_root, root).exists())


class HyperResearchDoctrineTests(unittest.TestCase):
    def load_seeds_scanner(self):
        scanner_path = Path(__file__).parents[1] / "tests" / "test_preflight_capabilities.py"
        scanner_spec = importlib.util.spec_from_file_location("seeds_scanner_lifecycle", scanner_path)
        assert scanner_spec and scanner_spec.loader
        scanner = importlib.util.module_from_spec(scanner_spec)
        scanner_spec.loader.exec_module(scanner)
        return scanner

    def test_doctrine_line_present_in_skill_and_operating_model(self) -> None:
        for path in (SKILL, OPERATING_MODEL):
            text = path.read_text(encoding="utf-8")
            with self.subTest(surface=path.name):
                self.assertIn("external evidence is load-bearing", text)
                for element in ("sources", "claims", "counterevidence", "uncertainty", "decision-impact", "next-action"):
                    self.assertIn(element, text)
                self.assertIn("versioned", text)
                self.assertIn("SeedProposal", text)

    def test_doctrine_text_does_not_leak_seeds_mutation_guidance(self) -> None:
        scanner = self.load_seeds_scanner()
        for path in (SKILL, OPERATING_MODEL):
            relative = Path("skills/codex-research-os") / path.relative_to(SKILL.parent)
            violations = scanner.guidance_violations(
                relative,
                list(enumerate(path.read_text(encoding="utf-8").splitlines(), 1)),
                enforce_seeds_authority=True,
            )
            with self.subTest(surface=path.name):
                self.assertEqual(violations, [], "\n".join(violations))


class BirthWitnessSettlementTests(unittest.TestCase):
    """This installer records a `stat-v2` witness and re-verifies it milliseconds later, which is
    exactly the window a coarse birth clock leaves open: CI run 32554149554 (kernel 6.6.141,
    ext4) saw ONE distinct btime across 40 back-to-back creates and repeated an identical
    (inode, btime) pair in 20 of 20 delete-recreate trials. Its generated content is
    deterministic, so a byte-identical replacement at a new inode also satisfies the digest and
    only the physical witness can refuse it. Granularity is forced through the `_linux_statx`
    seam in every test here, never inherited from this host."""

    maxDiff = None

    @contextmanager
    def simulated_birth_clock(self, quantum_seconds: float | None):
        """Force the installer's birth-timestamp source to a chosen granularity.

        A float truncates every birth timestamp to that quantum; `None` freezes it. The quantum's
        boundaries are anchored to the moment this clock is installed, so any operation sequence
        shorter than the quantum provably lands inside the FIRST quantum -- which makes both
        directions deterministic instead of leaving them to where the host's clock happens to
        sit. A simulated clock can only be made coarser than the real one, and coarseness is the
        defect.
        """
        real = installer._linux_statx
        quantum_ns = None if quantum_seconds is None else max(1, int(quantum_seconds * 10**9))
        origin = time.time_ns()

        class _Btime:
            def __init__(self, seconds: int, nanoseconds: int) -> None:
                self.tv_sec = seconds
                self.tv_nsec = nanoseconds

        class _Simulated:
            def __init__(self, source: object, btime: _Btime) -> None:
                self._source = source
                self.stx_btime = btime

            def __getattr__(self, name: str) -> object:
                return getattr(self._source, name)

        def simulated(path: bytes, *, descriptor: int = -100, flags: int = 0):
            result = real(path, descriptor=descriptor, flags=flags)
            if result is None:
                return None
            if quantum_ns is None:
                return _Simulated(result, _Btime(1700000000, 0))
            total = result.stx_btime.tv_sec * 10**9 + result.stx_btime.tv_nsec
            total = origin + ((total - origin) // quantum_ns) * quantum_ns
            return _Simulated(result, _Btime(total // 10**9, total % 10**9))

        with mock.patch.object(installer, "_linux_statx", simulated):
            yield

    @staticmethod
    def replace_byte_identically(target: Path) -> None:
        """Swap in a byte-identical replacement at a new inode, the way the digest cannot see."""
        replacement = target.parent / f"{target.name}.replacement"
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(stat.S_IMODE(target.stat().st_mode))
        os.replace(replacement, target)

    @staticmethod
    def reused_inode_witness(replacement_token: str, recorded_token: str) -> str:
        """The witness a record would carry if a replacement landed on the recorded inode.

        `os.replace` never reuses an inode, so the collision the CI probe measured 20 out of 20
        times has to be modelled rather than raced: the replacement's real device and inode with
        the RECORDED birth timestamp. Once the recorded timestamp is strictly older, this
        forgery stops matching however the allocator behaves.
        """
        version, device, inode, _ = replacement_token.split(":", 3)
        return f"{version}:{device}:{inode}:{installer._identity_generation(recorded_token)}"

    def classify_replaced_leaf(
        self, rel: str, state_root: Path, root: Path
    ) -> tuple[bool, str, str]:
        """Replace an owned leaf byte-identically, then ask the real ownership classifier."""
        record = json.loads(
            expected_state_path(state_root, root).read_text(encoding="utf-8")
        )["entries"][rel]
        self.replace_byte_identically(root / rel)
        root_fd = installer._open_root(root)
        try:
            observed = installer._inspect_leaf(root, root_fd, tuple(rel.split("/")))
        finally:
            if root_fd is not None:
                os.close(root_fd)
        assert observed.identity is not None
        forged = {
            **record,
            "destination_identity": self.reused_inode_witness(
                observed.identity, record["destination_identity"]
            ),
        }
        return (
            installer._exact_matches(observed, forged),
            record["destination_identity"],
            observed.identity,
        )

    @contextmanager
    def settlement_removed(self):
        """Neutralize BOTH settlement seams, which is what "no settlement at all" now means.

        Recording defers (`_defer_identity_witnesses`, which never sleeps) and only the target-root
        witness still settles inline, so a mutation that removes just one of the two leaves the
        other still enforcing. A positive control has to remove both or it proves nothing.
        """
        with mock.patch.object(
            installer, "_settle_identity_witnesses", lambda *a, **k: None
        ):
            with mock.patch.object(
                installer, "_defer_identity_witnesses", lambda *a, **k: True
            ):
                yield

    def test_same_quantum_witness_cannot_discriminate_a_reused_inode(self) -> None:
        """Positive control: with settlement removed the recorded witness is reproducible."""
        rel = "research/status.md"
        with self.simulated_birth_clock(3600.0):
            with self.settlement_removed():
                with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                    root = Path(directory)
                    installer.apply_install(root, files={rel: "CANONICAL\n"})

                    owned, recorded, current = self.classify_replaced_leaf(
                        rel, state_root, root
                    )

                    self.assertEqual(
                        installer._identity_generation(recorded),
                        installer._identity_generation(current),
                    )
                    self.assertTrue(owned)

    def test_a_settled_witness_discriminates_a_reused_inode(self) -> None:
        rel = "research/status.md"
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                installer.apply_install(root, files={rel: "CANONICAL\n"})

                owned, recorded, current = self.classify_replaced_leaf(rel, state_root, root)

                self.assertLess(
                    installer._birth_witness_order(
                        installer._identity_generation(recorded)
                    ),
                    installer._birth_witness_order(
                        installer._identity_generation(current)
                    ),
                )
                self.assertFalse(owned)

    def test_byte_identical_replacement_is_preserved_under_a_coarse_birth_clock(self) -> None:
        rel = "research/status.md"
        with self.simulated_birth_clock(0.5):
            with tempfile.TemporaryDirectory() as directory, isolated_state():
                root = Path(directory)
                target = root / rel
                installer.apply_install(root, files={rel: "CANONICAL\n"})
                self.replace_byte_identically(target)

                removal = installer.apply_install(root, files={})
                self.assertEqual(removal[rel], "skipped-remove-modified")
                self.assertEqual(target.read_text(encoding="utf-8"), "CANONICAL\n")

                overwrite = installer.apply_install(root, files={rel: "NEXT\n"}, force=True)
                self.assertEqual(overwrite[rel], "skipped-foreign")
                self.assertEqual(target.read_text(encoding="utf-8"), "CANONICAL\n")

    def test_owner_lifecycle_works_under_coarse_and_native_birth_clocks(self) -> None:
        rel = "research/status.md"
        for quantum in (0.000000001, 0.5):
            with self.subTest(quantum=quantum), self.simulated_birth_clock(quantum):
                with tempfile.TemporaryDirectory() as directory, isolated_state():
                    root = Path(directory)
                    target = root / rel
                    self.assertEqual(
                        installer.apply_install(root, files={rel: "ONE\n"})[rel], "created"
                    )
                    self.assertEqual(
                        installer.apply_install(root, files={rel: "TWO\n"})[rel], "updated"
                    )
                    self.assertEqual(target.read_text(encoding="utf-8"), "TWO\n")
                    self.assertEqual(installer.apply_install(root, files={})[rel], "removed")
                    self.assertFalse(target.exists())

    def test_recording_refuses_when_the_birth_clock_cannot_discriminate(self) -> None:
        rel = "research/status.md"
        with self.simulated_birth_clock(None):
            with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                with tempfile.TemporaryDirectory() as directory, isolated_state():
                    root = Path(directory)

                    with self.assertRaisesRegex(
                        installer.ResearchOSError, "birth timestamps cannot distinguish"
                    ):
                        installer.apply_install(root, files={rel: "CANONICAL\n"})

                    self.assertFalse((root / rel).exists())

    def test_dry_run_leaves_no_creation_probe(self) -> None:
        rel = "research/status.md"
        with self.simulated_birth_clock(None):
            with mock.patch.object(installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05):
                with tempfile.TemporaryDirectory() as directory, isolated_state():
                    root = Path(directory)

                    actions = installer.apply_install(
                        root, files={rel: "CANONICAL\n"}, dry_run=True
                    )

                    self.assertEqual(actions[rel], "created")
                    self.assertEqual(list(root.iterdir()), [])

    def test_settle_refuses_within_its_bound_and_probes_once_per_round(self) -> None:
        self.assertGreater(installer.BIRTH_SETTLE_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(installer.BIRTH_SETTLE_TIMEOUT_SECONDS, 5.0)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            targets = []
            for index in range(4):
                target = root / f"object-{index}"
                target.mkdir()
                targets.append(target)
            probes = 0
            sleeps = 0
            real_probe = installer._birth_probe_token
            real_sleep = installer.time.sleep

            def counted_probe(path: Path) -> str:
                nonlocal probes
                probes += 1
                return real_probe(path)

            def counted_sleep(seconds: float) -> None:
                nonlocal sleeps
                sleeps += 1
                real_sleep(seconds)

            with self.simulated_birth_clock(None):
                witnesses = [
                    (target, installer._path_identity(target, follow_symlinks=False))
                    for target in targets
                ]
                with mock.patch.object(installer, "_birth_probe_token", counted_probe):
                    with mock.patch.object(installer.time, "sleep", counted_sleep):
                        with mock.patch.object(
                            installer, "BIRTH_SETTLE_TIMEOUT_SECONDS", 0.05
                        ):
                            started = time.monotonic()
                            with self.assertRaisesRegex(
                                installer.ResearchOSError, "cannot distinguish"
                            ):
                                installer._settle_identity_witnesses(
                                    witnesses, probe_dir=root
                                )
                            elapsed = time.monotonic() - started
        self.assertLess(elapsed, 2.0)
        self.assertGreater(probes, 0)
        self.assertEqual(probes, sleeps + 1)

    def test_windows_skips_a_file_id_witness_and_settles_the_timestamp_fallback(self) -> None:
        """A reused Windows file id already differs; the ctime fallback does not, so it settles."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "object"
            target.mkdir()
            probes = 0
            real_probe = installer._birth_probe_token

            def counted_probe(path: Path) -> str:
                nonlocal probes
                probes += 1
                return real_probe(path)

            with mock.patch.object(installer, "_platform_system", lambda: "Windows"):
                with mock.patch.object(installer, "_birth_probe_token", counted_probe):
                    with mock.patch.object(
                        installer, "_windows_file_identity", lambda *a, **k: (1, 2, 0)
                    ):
                        token = installer._path_identity(target, follow_symlinks=False)
                        installer._settle_identity_witnesses(
                            ((target, token),), probe_dir=root
                        )
                        self.assertEqual(probes, 0)
                    with mock.patch.object(
                        installer, "_windows_file_identity", lambda *a, **k: None
                    ):
                        fallback = installer._path_identity(target, follow_symlinks=False)
                        self.assertNotEqual(fallback, token)
                        installer._settle_identity_witnesses(
                            ((target, fallback),), probe_dir=root
                        )
            self.assertGreater(probes, 0)

    def test_wait_count_does_not_grow_with_the_scaffold_file_count(self) -> None:
        """The wait budget must be independent of the file count -- the point of deferring.

        A coarse clock makes every recording site defer, which is the shape that used to cost one
        full birth quantum per file transaction. `_wait_for_settlement` is the only function that
        sleeps, so counting its invocations counts the waits -- and they are counted separately by
        origin, because a run has two: the pre-existing TARGET ROOT still settles inline (with an
        empty ledger), while every witness the run MINTS shares one deferred wait. Only the
        deferred count is the subject here, and it must be exactly one for one file and for
        sixteen alike.
        """
        observed = []
        for count in (1, 4, 16):
            waits: list[int] = []
            real_wait = installer._wait_for_settlement

            def counted_wait(targets):
                # The ledger is only non-empty for the run's single DEFERRED wait; the inline
                # target-root settle runs before anything is enrolled.
                waits.append(installer._SETTLEMENT.deferred)
                return real_wait(targets)

            files = {f"research/note-{index:03d}.md": f"NOTE {index}\n" for index in range(count)}
            with self.simulated_birth_clock(0.25):
                with tempfile.TemporaryDirectory() as directory, isolated_state():
                    root = Path(directory)
                    with mock.patch.object(installer, "_wait_for_settlement", counted_wait):
                        actions = installer.apply_install(root, files=files)
                    self.assertEqual(
                        sorted(set(actions.values())), ["created"], actions
                    )
                    for rel in files:
                        self.assertTrue((root / rel).exists())
            observed.append((count, sum(1 for deferred in waits if deferred), len(waits)))
        # Exactly one deferred wait per run, at every file count. A count of zero would satisfy
        # "constant" trivially, so requiring one is also the positive control for the measurement.
        self.assertEqual([deferred for _, deferred, _ in observed], [1, 1, 1], observed)
        # And the total, inline root settle included, stays constant too.
        self.assertEqual(len({total for _, _, total in observed}), 1, observed)

    def test_an_interrupted_run_leaves_a_witness_a_later_run_will_not_trust(self) -> None:
        """Crash safety: durable after a state write, never settled, never later trusted.

        The interruption lands exactly where it matters -- after the durable writes that make the
        witnesses persistent and before the run's single settle. The root settle runs earlier, with
        an empty ledger, so keying off `deferred` interrupts only the deferred wait.
        """
        rel = "research/status.md"
        with self.simulated_birth_clock(0.25):
            with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                root = Path(directory)
                real_wait = installer._wait_for_settlement

                def interrupt_only_the_deferred_wait(targets):
                    if installer._SETTLEMENT.deferred:
                        raise KeyboardInterrupt("interrupted before the settle")
                    return real_wait(targets)

                with mock.patch.object(
                    installer, "_wait_for_settlement", interrupt_only_the_deferred_wait
                ):
                    with self.assertRaises(KeyboardInterrupt):
                        installer.apply_install(root, files={rel: "CANONICAL\n"})

                # The leaf IS on disk and IS recorded: the interruption came after publication.
                self.assertTrue((root / rel).exists())
                document = json.loads(
                    expected_state_path(state_root, root).read_text(encoding="utf-8")
                )
                self.assertIs(document["entries"][rel]["witness_settled"], False)

        # A later run's ledger is empty, which is what makes the marker bite.
        self.assertEqual(installer._SETTLEMENT.keys, set())
        self.assertFalse(installer._SETTLEMENT.deferred)

    def test_an_unsettled_record_is_non_discriminating_and_never_removed(self) -> None:
        """Invariant: a durably recorded unsettled witness is trusted by no later consumer.

        The marker is asserted at the classifier AND end to end: planning must not call the leaf
        owned, and removal must preserve it. Each has the positive control the repository's
        doctrine requires -- the same record without the marker discriminates and is removed.
        """
        rel = "research/status.md"
        for marked in (True, False):
            with self.subTest(marked=marked):
                with tempfile.TemporaryDirectory() as directory, isolated_state() as state_root:
                    root = Path(directory)
                    installer.apply_install(root, files={rel: "CANONICAL\n"})
                    state_path = expected_state_path(state_root, root)
                    document = json.loads(state_path.read_text(encoding="utf-8"))

                    root_fd = installer._open_root(root)
                    try:
                        observed = installer._inspect_leaf(
                            root, root_fd, tuple(rel.split("/"))
                        )
                    finally:
                        if root_fd is not None:
                            os.close(root_fd)
                    record = document["entries"][rel]
                    if marked:
                        record = {**record, "witness_settled": False}
                    self.assertEqual(
                        installer._exact_matches(observed, record), not marked
                    )

                    if marked:
                        document["entries"][rel]["witness_settled"] = False
                        state_path.write_text(json.dumps(document), encoding="utf-8")

                    removal = installer.apply_install(root, files={})
                    if marked:
                        # Non-discriminating, so the leaf is foreign to removal and preserved.
                        self.assertEqual(removal[rel], "skipped-remove-modified")
                        self.assertEqual(
                            (root / rel).read_text(encoding="utf-8"), "CANONICAL\n"
                        )
                    else:
                        self.assertEqual(removal[rel], "removed")
                        self.assertFalse((root / rel).exists())

    def test_a_probe_that_cannot_be_retired_refuses_by_name(self) -> None:
        """Killing test for the probe-unlink guard: a leftover probe must never be swallowed.

        Without the guard the probe stays behind, and a private container's exactness check reads
        ANY extra child as foreign -- so the failure would resurface later as an unrelated
        "foreign content" complaint about a payload nothing touched.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real_unlink = Path.unlink

            def refuse_probe_unlink(self, *args, **kwargs):
                if self.name.startswith(".birth-probe-"):
                    raise OSError(errno.EPERM, "operation not permitted")
                return real_unlink(self, *args, **kwargs)

            with mock.patch.object(Path, "unlink", refuse_probe_unlink):
                with self.assertRaisesRegex(
                    installer.ResearchOSError, "cannot retire creation probe"
                ):
                    installer._birth_probe_token(root)

            # The refusal named the probe, and the probe is exactly what was left behind.
            leftovers = list(root.glob(".birth-probe-*"))
            self.assertEqual(len(leftovers), 1, leftovers)
            for leftover in leftovers:
                real_unlink(leftover)

            # Positive control: with unlink restored the same call succeeds and retires the probe.
            token = installer._birth_probe_token(root)
            self.assertTrue(installer._identity_token_valid(token))
            self.assertEqual(list(root.glob(".birth-probe-*")), [])


if __name__ == "__main__":
    unittest.main()
