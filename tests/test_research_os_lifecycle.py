from __future__ import annotations

from contextlib import contextmanager
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
                with self.assertRaises(Exception):
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
                    foreign = stage.payload.with_name("foreign")
                    foreign.write_text("FOREIGN TEMP RACE\n", encoding="utf-8")
                    os.replace(foreign, stage.payload)
                return real_publish(stage, destination, *args, **kwargs)

            with mock.patch.object(installer, "_publish_staged_file", side_effect=swap_manifest_stage):
                with self.assertRaises(Exception):
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


if __name__ == "__main__":
    unittest.main()
