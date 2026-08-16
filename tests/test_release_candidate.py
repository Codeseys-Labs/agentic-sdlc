"""Regression tests for the unpublished release-candidate seam."""
from __future__ import annotations

import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts" / "release_candidate.py"
POLICY_PATH = ROOT / "policy" / "release-candidate.v1.json"
EXECUTION_POLICY_PATH = ROOT / "policy" / "release-candidate-execution.v1.json"


def load_candidate_module():
    spec = importlib.util.spec_from_file_location("release_candidate_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


candidate = load_candidate_module()


def write_file(path: Path, data: bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    os.chmod(path, mode)


def miniature_policy() -> dict[str, object]:
    policy = copy.deepcopy(candidate.load_policy(POLICY_PATH))
    policy["payload"] = {
        "files": ["LICENSE", "NOTICE", "policy/release-candidate.v1.json", "scripts/release_candidate.py"],
        "trees": ["assets"],
    }
    candidate.validate_policy(policy)
    return policy


def fake_runtime(directory: Path, script: bytes = b"not-a-runtime\n") -> Path:
    root = directory / "runtime-source"
    write_file(root / "bin" / "python3.12", script, 0o755)
    write_file(root / "lib" / "python3.12" / "LICENSE.txt", b"runtime license\n")
    return root


def test_snapshot(directory: Path, policy: dict[str, object]) -> candidate.SourceSnapshot:
    source = directory / "source"
    files: dict[str, tuple[int, bytes]] = {
        "LICENSE": (0o100644, b"license committed\n"),
        "NOTICE": (0o100644, b"notice committed\n"),
        "assets/one.txt": (0o100644, b"asset\n"),
        "policy/release-candidate.v1.json": (0o100644, candidate.canonical_json(policy).encode("ascii")),
        "scripts/release_candidate.py": (0o100644, b"# committed test script\n"),
    }
    for path, (mode, data) in files.items():
        write_file(source / path, data, mode & 0o777)
    return candidate.source_snapshot_for_testing(source, files)


def host_snapshot(directory: Path, policy_override: dict[str, object] | None = None) -> tuple[candidate.SourceSnapshot, dict[str, object], bytes]:
    policy = copy.deepcopy(policy_override) if policy_override is not None else candidate.load_policy(POLICY_PATH)
    policy_bytes = candidate.canonical_json(policy).encode("ascii")
    payload = policy["payload"]
    assert isinstance(payload, dict)
    files: dict[str, tuple[int, bytes]] = {}
    for path in payload["files"]:
        assert isinstance(path, str)
        files[path] = (0o100644, f"host file {path}\n".encode("ascii"))
    for tree in payload["trees"]:
        assert isinstance(tree, str)
        files[f"{tree}/placeholder.txt"] = (0o100644, f"tree {tree}\n".encode("ascii"))
    files["policy/release-candidate.v1.json"] = (0o100644, policy_bytes)
    files["scripts/release_candidate.py"] = (0o100644, b"# packaged script\n")
    source = directory / "host-source"
    for path, (mode, data) in files.items():
        write_file(source / path, data, mode & 0o777)
    return candidate.source_snapshot_for_testing(source, files), policy, policy_bytes


def executable_snapshot(directory: Path) -> tuple[candidate.SourceSnapshot, dict[str, object]]:
    policy = copy.deepcopy(candidate.load_policy(POLICY_PATH))
    authored = [
        "LICENSE",
        "NOTICE",
        "assets/launchers/ccodex.in",
        "policy/ccodex-sdlc-read-report.v2.json",
        "policy/release-candidate-execution.v1.json",
        "policy/release-candidate.v1.json",
        "scripts/ccodex_sdlc.py",
        "scripts/ccodex_sdlc_readonly.py",
        "scripts/install_operator_tools.py",
        "scripts/install_skill_bundle.py",
        "scripts/release_candidate.py",
    ]
    policy["payload"] = {
        "files": ["LICENSE", "NOTICE"],
        "trees": ["assets", "candidate-support", "policy", "scripts"],
    }
    candidate.validate_policy(policy)
    files: dict[str, tuple[int, bytes]] = {}
    for relative in authored:
        source = ROOT / relative
        data = source.read_bytes()
        files[relative] = (0o100755 if source.stat().st_mode & 0o100 else 0o100644, data)
    files["policy/release-candidate.v1.json"] = (
        0o100644,
        candidate.canonical_json(policy).encode("ascii"),
    )
    files["candidate-support/placeholder.txt"] = (0o100644, b"candidate support\n")
    source = directory / "source"
    for relative, (mode, data) in files.items():
        write_file(source / relative, data, mode & 0o777)
    return candidate.source_snapshot_for_testing(source, files), policy


def candidate_report_policy_mutations() -> list[tuple[str, dict[str, object]]]:
    original = json.loads((ROOT / "policy" / "ccodex-sdlc-read-report.v2.json").read_text())
    mutations: list[tuple[str, dict[str, object]]] = []
    for key in original:
        changed = copy.deepcopy(original)
        changed.pop(key)
        mutations.append((f"top-level-{key}", changed))
    for key in original["canonical_serialization"]:
        changed = copy.deepcopy(original)
        changed["canonical_serialization"].pop(key)
        mutations.append((f"canonical-{key}", changed))
    for key in original["field_vocabularies"]:
        changed = copy.deepcopy(original)
        changed["field_vocabularies"][key].append("drift")
        mutations.append((f"field-vocabulary-{key}", changed))
    for key in original["vocabularies"]:
        changed = copy.deepcopy(original)
        changed["vocabularies"][key].append("drift")
        mutations.append((f"value-vocabulary-{key}", changed))
    for key, value in (
        ("schema_version", "drift"),
        ("report_schema_version", "drift"),
        ("report_top_level_fields", [*original["report_top_level_fields"], "drift"]),
    ):
        changed = copy.deepcopy(original)
        changed[key] = value
        mutations.append((f"identity-{key}", changed))
    return mutations


def build_for_test(directory: Path, *, host: bool = False, runtime_script: bytes = b"not-a-runtime\n") -> Path:
    if host:
        snapshot, policy, _ = host_snapshot(directory)
    else:
        policy = miniature_policy()
        snapshot = test_snapshot(directory, policy)
    runtime = fake_runtime(directory, runtime_script)
    output = directory / "output"
    output.mkdir()
    with mock.patch.object(candidate, "_staging_runtime_canary"):
        return candidate.build_candidate(output, snapshot=snapshot, policy=policy, runtime_root=runtime)


def write_raw_archive(path: Path, member: tarfile.TarInfo, *, format: int) -> None:
    with path.open("xb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=format) as packed:
                packed.addfile(member, io.BytesIO(b"x" * member.size) if member.size else None)


def ustar_member_offsets(raw: bytes) -> dict[str, int]:
    result: dict[str, int] = {}
    offset = 0
    while raw[offset:offset + 512] != b"\0" * 512:
        header = raw[offset:offset + 512]
        name = header[:100].split(b"\0", 1)[0].decode("ascii")
        prefix = header[345:500].split(b"\0", 1)[0].decode("ascii")
        name = f"{prefix}/{name}" if prefix else name
        if header[156:157] == b"5" and name.endswith("/"):
            name = name[:-1]
        result[name] = offset
        size = int(header[124:136].strip(b" \0") or b"0", 8)
        offset += 512 + ((size + 511) // 512) * 512
    return result


def rewrite_ustar_checksum(raw: bytearray, offset: int) -> None:
    header = raw[offset:offset + 512]
    header[148:156] = b" " * 8
    header[148:156] = f"{sum(header):06o}\0 ".encode("ascii")
    raw[offset:offset + 512] = header


def make_git_repo(root: Path, policy: dict[str, object]) -> None:
    write_file(root / "LICENSE", b"license committed\n")
    write_file(root / "NOTICE", b"notice committed\n")
    write_file(root / "assets" / "one.txt", b"asset\n")
    write_file(root / "policy" / "release-candidate.v1.json", candidate.canonical_json(policy).encode("ascii"))
    write_file(root / "scripts" / "release_candidate.py", b"# committed script\n")
    for arguments in (
        ["git", "init", "-q", str(root)],
        ["git", "-C", str(root), "add", "."],
        ["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "initial"],
    ):
        completed = subprocess.run(arguments, check=False, capture_output=True, text=True)
        if completed.returncode:
            raise AssertionError(completed.stderr)


class PolicyAndPlatformTests(unittest.TestCase):
    def test_shipped_policy_is_strict_canonical_and_has_preallocation_bound(self) -> None:
        policy = candidate.load_policy(POLICY_PATH)
        self.assertEqual(POLICY_PATH.read_bytes(), candidate.canonical_json(policy).encode("ascii"))
        limits = policy["limits"]
        assert isinstance(limits, dict)
        self.assertGreater(limits["max_uncompressed_bytes"], limits["max_total_bytes"])

    def test_candidate_v2_runtime_policy_is_exactly_closed_in_every_dimension(self) -> None:
        clean = json.loads((ROOT / "policy" / "ccodex-sdlc-read-report.v2.json").read_text())
        candidate.validate_candidate_report_policy(clean)
        for label, changed in candidate_report_policy_mutations():
            with self.subTest(label=label), self.assertRaises(candidate.CandidateError) as raised:
                candidate.validate_candidate_report_policy(changed)
            self.assertEqual(raised.exception.code, "candidate-report-policy")

    def test_manifest_rejects_promotion_and_requires_unverified_build_observation(self) -> None:
        manifest = candidate.valid_manifest_fixture()
        manifest["support_tier"] = "certified"
        with self.assertRaises(candidate.CandidateError) as raised:
            candidate.validate_manifest(manifest, candidate.load_policy(POLICY_PATH))
        self.assertEqual(raised.exception.code, "manifest-label")
        manifest = candidate.valid_manifest_fixture()
        manifest["build_observation"] = {"runtime_canary": {"state": "trusted"}}
        with self.assertRaises(candidate.CandidateError):
            candidate.validate_manifest(manifest, candidate.load_policy(POLICY_PATH))

    def test_platform_classifier_distinguishes_native_wsl2_and_wsl1(self) -> None:
        self.assertEqual(candidate._linux_platform_kind("6.6.1", "Linux version 6.6.1"), "native")
        self.assertEqual(candidate._linux_platform_kind("5.15.153.1-microsoft-standard-WSL2", "Linux version 5.15.153.1-microsoft-standard-WSL2"), "wsl2")
        self.assertEqual(candidate._linux_platform_kind("4.4.0-19041-Microsoft", "Linux version 4.4.0-19041-Microsoft"), "wsl1")
        with mock.patch.object(candidate.sys, "platform", "linux"), mock.patch.object(candidate.platform, "machine", return_value="x86_64"):
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._require_linux_x64(lambda path: "4.4.0-Microsoft" if path.name == "osrelease" else "Microsoft")
        self.assertEqual(raised.exception.code, "platform-unsupported")

    def test_exact_cli_grammar_rejects_abbreviations_before_effects(self) -> None:
        self.assertEqual(candidate.main(["build", "--out", "/tmp/not-read"]), 2)
        self.assertEqual(candidate.main(["verify", "--arch", "/tmp/not-read"]), 2)
        self.assertEqual(
            candidate.main(
                ["run-readonly", "--arch", "/tmp/not-read", "--", "sdlc", "inspect"]
            ),
            2,
        )

    def test_run_readonly_parser_admits_only_the_closed_sdlc_grammar(self) -> None:
        archive = Path(f"/tmp/agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz")
        admitted = (
            ["sdlc", "inspect"],
            ["sdlc", "inspect", "--json"],
            ["sdlc", "status"],
            ["sdlc", "doctor", "--json"],
            ["sdlc", "recover", "--dry-run"],
            ["sdlc", "recover", "--dry-run", "--json"],
        )
        for command in admitted:
            with self.subTest(command=command):
                parsed = candidate.parse_args(
                    ["run-readonly", "--archive", str(archive), "--", *command]
                )
                self.assertEqual(parsed.action, "run-readonly")
                self.assertEqual(parsed.command, command)

        refused = (
            ["sdlc", "recover"],
            ["sdlc", "recover", "--json", "--dry-run"],
            ["sdlc", "install"],
            ["status"],
            ["sdlc", "inspect", "--json", "extra"],
        )
        for command in refused:
            with self.subTest(command=command):
                with self.assertRaises(SystemExit):
                    candidate.parse_args(
                        ["run-readonly", "--archive", str(archive), "--", *command]
                    )
        with self.assertRaises(SystemExit):
            candidate.parse_args(["run-readonly", "--archive", str(archive), "sdlc", "inspect"])

    def test_non_linux_public_verify_refuses_before_archive_admission(self) -> None:
        for host in ("darwin", "win32"):
            with self.subTest(host=host), mock.patch.object(candidate.sys, "platform", host):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.verify_archive(Path("/tmp/not-an-archive.tar.gz"))
            self.assertEqual(raised.exception.code, "platform-unsupported")

    def test_exit_four_prints_only_a_resolvable_retained_witness_locator(self) -> None:
        private = Path(tempfile.mkdtemp(prefix=".release-candidate-run-", dir="/tmp"))
        try:
            retained = candidate._retain_process_group_witness(private)
            refusal = candidate.CandidateError("execution-group-unknown-effect", retained)
            stderr = io.StringIO()
            hostile_archive = Path(
                f"/tmp/archive-parent-credential-canary/agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz"
            )
            with (
                mock.patch.object(candidate, "run_readonly", side_effect=refusal),
                mock.patch.object(candidate.sys, "stderr", stderr),
                mock.patch.dict(
                    os.environ,
                    {
                        "HOME": "/home/credential-canary",
                        "TMPDIR": "/tmp/tmpdir-credential-canary",
                        "XDG_STATE_HOME": "/tmp/xdg-credential-canary",
                    },
                    clear=False,
                ),
            ):
                result = candidate.main(
                    [
                        "run-readonly",
                        "--archive",
                        str(hostile_archive),
                        "--",
                        "sdlc",
                        "inspect",
                    ]
                )
            self.assertEqual(result, 4)
            prefix = (
                "release-candidate: execution-group-unknown-effect "
                "effect_state=unknown witness_locator="
            )
            self.assertTrue(stderr.getvalue().startswith(prefix), stderr.getvalue())
            locator = Path(stderr.getvalue().removeprefix(prefix).strip())
            self.assertEqual(locator, private / "effect-state.json")
            self.assertEqual(
                json.loads(locator.read_text()),
                {
                    "cleanup": "retained",
                    "effect_state": "unknown",
                    "reason": "process-group-nonconvergence",
                    "schema_version": "release-candidate-effect-witness/v1",
                },
            )
            self.assertTrue(locator.is_file())
            self.assertFalse(locator.is_symlink())
            self.assertNotIn("credential-canary", stderr.getvalue())
        finally:
            candidate._cleanup_run_private(private)

        private = Path(tempfile.mkdtemp(prefix=".release-candidate-run-", dir="/tmp"))
        try:
            retained = candidate._retain_process_group_witness(private)
            Path(retained.locator).write_text("same-inode-tamper\n")
            stderr = io.StringIO()
            arguments = [
                "run-readonly",
                "--archive",
                f"/tmp/agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz",
                "--",
                "sdlc",
                "inspect",
            ]
            with (
                mock.patch.object(
                    candidate,
                    "run_readonly",
                    side_effect=candidate.CandidateError(
                        "execution-group-unknown-effect", retained
                    ),
                ),
                mock.patch.object(candidate.sys, "stderr", stderr),
            ):
                self.assertEqual(candidate.main(arguments), 4)
            self.assertNotIn("witness_locator=", stderr.getvalue())
            self.assertNotIn("same-inode-tamper", stderr.getvalue())
        finally:
            candidate._cleanup_run_private(private)

    def test_success_and_failures_without_valid_retained_evidence_print_no_locator(self) -> None:
        archive = Path(f"/tmp/agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz")
        arguments = [
            "run-readonly", "--archive", str(archive), "--", "sdlc", "inspect"
        ]
        for label, outcome, expected_code in (
            ("success", 0, 0),
            ("ordinary-refusal", candidate.CandidateError("execution-runtime-mismatch"), 3),
            ("unknown-without-witness", candidate.CandidateError("run-stage-unknown-effect"), 4),
        ):
            stderr = io.StringIO()
            patch = (
                mock.patch.object(candidate, "run_readonly", return_value=outcome)
                if isinstance(outcome, int)
                else mock.patch.object(candidate, "run_readonly", side_effect=outcome)
            )
            with self.subTest(label=label), patch, mock.patch.object(candidate.sys, "stderr", stderr):
                self.assertEqual(candidate.main(arguments), expected_code)
            self.assertNotIn("witness_locator=", stderr.getvalue())

        private = Path(tempfile.mkdtemp(prefix=".release-candidate-run-", dir="/tmp"))
        try:
            retained = candidate._retain_process_group_witness(private)
            witness = Path(retained.locator)
            witness.unlink()
            witness.symlink_to("/etc/passwd")
            stderr = io.StringIO()
            with (
                mock.patch.object(
                    candidate,
                    "run_readonly",
                    side_effect=candidate.CandidateError(
                        "execution-group-unknown-effect", retained
                    ),
                ),
                mock.patch.object(candidate.sys, "stderr", stderr),
            ):
                self.assertEqual(candidate.main(arguments), 4)
            self.assertNotIn("witness_locator=", stderr.getvalue())
            self.assertNotIn("/etc/passwd", stderr.getvalue())
        finally:
            candidate._cleanup_run_private(private)


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"}, "candidate build needs Linux x64")
class BuildTests(unittest.TestCase):
    def test_two_builds_are_byte_identical_ustar_and_private_staging_is_cleaned(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            first = build_for_test(directory / "one")
            second = build_for_test(directory / "two")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with gzip.open(first, "rb") as handle:
                raw_tar = handle.read()
            self.assertEqual(raw_tar[257:263], b"ustar\x00")
            self.assertEqual(raw_tar[263:265], b"00")
            self.assertNotIn(b"\x00x", raw_tar[:1024])
            self.assertEqual(sorted(item.name for item in first.parent.iterdir()), [first.name])

    def test_build_uses_committed_git_objects_and_final_recheck_refuses_drift(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            source = directory / "source"
            make_git_repo(source, policy)
            snapshot = candidate.admit_source(source)
            write_file(source / "LICENSE", b"working-tree drift\n")
            runtime = fake_runtime(directory)
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"), self.assertRaises(candidate.CandidateError) as raised:
                candidate.build_candidate(output, snapshot=snapshot, runtime_root=runtime)
            self.assertEqual(raised.exception.code, "source-drift")
            self.assertEqual(list(output.iterdir()), [])
            with mock.patch.object(candidate, "_staging_runtime_canary"), mock.patch.object(candidate, "_final_source_recheck"):
                archive = candidate.build_candidate(output, snapshot=snapshot, runtime_root=runtime)
            with tarfile.open(archive, "r:gz") as packed:
                member = next(item for item in packed if item.name.endswith("/LICENSE"))
                handle = packed.extractfile(member)
                assert handle is not None
                self.assertEqual(handle.read(), b"license committed\n")

    def test_poisoned_path_git_uv_and_mise_cannot_replace_admitted_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            source = directory / "source"
            make_git_repo(source, policy)
            poison = {"PATH": "/poison", "GIT_DIR": "/poison/git", "GIT_WORK_TREE": "/poison/work", "UV_CACHE_DIR": "/poison/uv", "MISE_CONFIG_ROOT": "/poison/mise"}
            with mock.patch.dict(os.environ, poison, clear=False):
                snapshot = candidate.admit_source(source)
                runtime = candidate._resolve_base_runtime(candidate.load_policy(POLICY_PATH))
            self.assertEqual(snapshot.git.path, Path("/usr/bin/git"))
            self.assertTrue(snapshot.git.version.startswith("git version "))
            self.assertEqual(len(snapshot.git.sha256), 64)
            self.assertTrue((runtime / "bin" / "python3.12").is_file())

    def test_post_link_sync_failure_rolls_back_exact_destination(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            snapshot = test_snapshot(directory, policy)
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"), mock.patch.object(candidate, "_sync_directory", side_effect=OSError("injected")):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.build_candidate(output, snapshot=snapshot, policy=policy, runtime_root=fake_runtime(directory))
            self.assertIn(raised.exception.code, {"archive-publish", "archive-unknown-effect"})
            self.assertEqual(list(output.iterdir()), [])

    def test_link_success_then_destination_lstat_failure_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            snapshot = test_snapshot(directory, policy)
            output = directory / "output"
            output.mkdir()
            original_lstat = Path.lstat

            def fail_destination_lstat(path: Path):
                if path.parent == output and path.name.startswith("agentic-sdlc-candidate-"):
                    raise OSError("injected destination lstat failure")
                return original_lstat(path)

            with mock.patch.object(candidate, "_staging_runtime_canary"), mock.patch.object(Path, "lstat", fail_destination_lstat):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.build_candidate(output, snapshot=snapshot, policy=policy, runtime_root=fake_runtime(directory))
            self.assertEqual(raised.exception.code, "archive-publish")
            self.assertEqual(list(output.iterdir()), [])

    def test_stage_cleanup_failure_is_unknown_effect_and_exit_four(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            snapshot = test_snapshot(directory, policy)
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary", side_effect=candidate.CandidateError("runtime-canary")), mock.patch.object(candidate, "_remove_stage", side_effect=OSError("injected cleanup failure")):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.build_candidate(output, snapshot=snapshot, policy=policy, runtime_root=fake_runtime(directory))
            self.assertEqual(raised.exception.code, "stage-unknown-effect")
            self.assertEqual(candidate._failure_exit_code(raised.exception.code), 4)
            self.assertEqual(list(output.iterdir()), [next(path for path in output.iterdir() if path.name.startswith(".release-candidate-stage-"))])

    def test_real_base_runtime_relocates_and_canaries_during_build_only(self) -> None:
        policy = candidate.load_policy(POLICY_PATH)
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            runtime = candidate._resolve_base_runtime(policy)
            private = directory / "candidate" / "runtime" / "python"
            private.parent.mkdir(parents=True)
            candidate._copy_runtime_tree(runtime, private, policy)
            candidate._staging_runtime_canary(directory / "candidate", policy)

    def test_local_executable_git_config_cannot_run_during_admission_or_build(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            source = directory / "source"
            make_git_repo(source, policy)
            marker = directory / "git-config-executed"
            helper = directory / "config-helper"
            write_file(helper, f"#!/bin/sh\nprintf x > {marker}\ncat\n".encode("ascii"), 0o755)
            for key, value in (("core.fsmonitor", str(helper)), ("diff.external", str(helper)), ("diff.marker.textconv", str(helper))):
                completed = subprocess.run(["git", "-C", str(source), "config", key, value], check=False, capture_output=True)
                self.assertEqual(completed.returncode, 0)
            snapshot = candidate.admit_source(source)
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                candidate.build_candidate(output, snapshot=snapshot, runtime_root=fake_runtime(directory))
            self.assertFalse(marker.exists())

    def test_clean_filter_is_neither_executed_nor_trusted_for_source_admission(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            policy = miniature_policy()
            source = directory / "source"
            make_git_repo(source, policy)
            write_file(source / "target", b"committed\n")
            write_file(source / ".gitattributes", b"target filter=evil\n")
            completed = subprocess.run(["git", "-C", str(source), "add", "target", ".gitattributes"], check=False, capture_output=True)
            self.assertEqual(completed.returncode, 0)
            completed = subprocess.run(["git", "-C", str(source), "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-qm", "attributes"], check=False, capture_output=True)
            self.assertEqual(completed.returncode, 0)
            marker = directory / "clean-filter-executed"
            helper = directory / "clean-helper"
            write_file(helper, f"#!/bin/sh\nprintf x > {marker}\n".encode("ascii"), 0o755)
            completed = subprocess.run(["git", "-C", str(source), "config", "filter.evil.clean", str(helper)], check=False, capture_output=True)
            self.assertEqual(completed.returncode, 0)
            os.utime(source / "target", None)
            snapshot = candidate.admit_source(source)
            self.assertFalse(marker.exists())
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                candidate.build_candidate(output, snapshot=snapshot, runtime_root=fake_runtime(directory))
            self.assertFalse(marker.exists())
            write_file(source / "target", b"working-tree drift\n")
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.admit_source(source)
            self.assertEqual(raised.exception.code, "source-dirty")
            self.assertFalse(marker.exists())


class RawPreflightTests(unittest.TestCase):
    def _archive_name(self) -> str:
        return f"agentic-sdlc-candidate-{'a' * 64}-linux-x64.tar.gz"

    def test_pax_and_gnu_metadata_bombs_refuse_before_tarfile(self) -> None:
        root = self._archive_name().removesuffix(".tar.gz")
        policy = candidate.load_policy(POLICY_PATH)
        for archive_format in (tarfile.PAX_FORMAT, tarfile.GNU_FORMAT):
            with self.subTest(archive_format=archive_format), tempfile.TemporaryDirectory() as raw:
                archive = Path(raw) / self._archive_name()
                member = tarfile.TarInfo(f"{root}/{'x' * 160}")
                member.type = tarfile.REGTYPE
                member.mode = 0o644
                member.size = 1
                member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.mtime = 0
                write_raw_archive(archive, member, format=archive_format)
                plain = Path(raw) / "candidate.ustar"
                plain.write_bytes(gzip.decompress(archive.read_bytes()))
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate._preflight_ustar(plain, policy, root)
                self.assertEqual(raised.exception.code, "archive-ustar")

    def test_uncompressed_ceiling_rejects_before_tarfile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / self._archive_name()
            with archive.open("xb") as target:
                with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0) as compressed:
                    compressed.write(b"x" * 2048)
            private = Path(raw) / "private"
            private.mkdir()
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._inflate_gzip(archive, private, 1024)
            self.assertEqual(raised.exception.code, "archive-uncompressed")

    def test_inflater_never_materializes_beyond_remaining_budget_plus_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = directory / "bounded.tar.gz"
            with archive.open("xb") as target:
                with gzip.GzipFile(filename="", mode="wb", fileobj=target, mtime=0, compresslevel=9) as compressed:
                    compressed.write(b"\0" * (2 * 1024 * 1024))
            calls: list[tuple[int, int]] = []
            original_factory = candidate.zlib.decompressobj

            class ObservedInflater:
                def __init__(self, inner):
                    self.inner = inner

                @property
                def eof(self):
                    return self.inner.eof

                @property
                def unused_data(self):
                    return self.inner.unused_data

                @property
                def unconsumed_tail(self):
                    return self.inner.unconsumed_tail

                def decompress(self, data: bytes, max_length: int = -1) -> bytes:
                    if max_length < 1:
                        raise AssertionError("unbounded decompression result")
                    result = self.inner.decompress(data, max_length)
                    calls.append((max_length, len(result)))
                    return result

            private = directory / "private"
            private.mkdir()
            with mock.patch.object(candidate.zlib, "decompressobj", side_effect=lambda **kwargs: ObservedInflater(original_factory(**kwargs))):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate._inflate_gzip(archive, private, 1024)
            self.assertEqual(raised.exception.code, "archive-uncompressed")
            self.assertTrue(calls)
            self.assertTrue(all(maximum <= 1025 and result <= maximum for maximum, result in calls))

    def test_outer_gzip_header_is_fixed_and_rejects_recompression_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = build_for_test(directory, host=True)
            policy = candidate.load_policy(POLICY_PATH)
            limits = policy["limits"]
            assert isinstance(limits, dict)
            accepted = directory / "accepted"
            accepted.mkdir()
            candidate._inflate_gzip(archive, accepted, limits["max_uncompressed_bytes"])
            payload = gzip.decompress(archive.read_bytes())
            for label, filename, mtime in (("filename", "candidate.ustar", 0), ("mtime", "", 1)):
                with self.subTest(label=label):
                    recompressed = directory / f"{label}.tar.gz"
                    with recompressed.open("xb") as target:
                        with gzip.GzipFile(filename=filename, mode="wb", fileobj=target, mtime=mtime, compresslevel=9) as compressed:
                            compressed.write(payload)
                    private = directory / f"private-{label}"
                    private.mkdir()
                    with self.assertRaises(candidate.CandidateError) as raised:
                        candidate._inflate_gzip(recompressed, private, limits["max_uncompressed_bytes"])
                    self.assertEqual(raised.exception.code, "archive-gzip")

    def test_root_and_every_header_field_are_bound_before_tarfile(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = build_for_test(directory, host=True)
            policy = candidate.load_policy(POLICY_PATH)
            original = bytearray(gzip.decompress(archive.read_bytes()))
            offsets = ustar_member_offsets(original)
            root = next(name for name in offsets if name.endswith("-linux-x64"))

            root_regular = bytearray(original)
            root_offset = offsets[root]
            root_regular[root_offset + len(root)] = 0
            root_regular[root_offset + 156] = ord("0")
            rewrite_ustar_checksum(root_regular, root_offset)
            plain = directory / "root-regular.ustar"
            plain.write_bytes(root_regular)
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._archive_admission(plain, f"{root}.tar.gz", policy, POLICY_PATH.read_bytes())
            self.assertEqual(raised.exception.code, "archive-root")

            root_link = bytearray(original)
            root_link[root_offset + len(root)] = 0
            root_link[root_offset + 156] = ord("2")
            root_link[root_offset + 157:root_offset + 257] = b"child\0" + b"\0" * 94
            rewrite_ustar_checksum(root_link, root_offset)
            plain = directory / "root-link.ustar"
            plain.write_bytes(root_link)
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._archive_admission(plain, f"{root}.tar.gz", policy, POLICY_PATH.read_bytes())
            self.assertEqual(raised.exception.code, "archive-root")

            for label, changed in (("regular-link", 157), ("device-field", 329), ("unused-padding", 500)):
                with self.subTest(label=label):
                    tampered = bytearray(original)
                    offset = offsets[f"{root}/LICENSE"]
                    tampered[offset + changed] = ord("x")
                    rewrite_ustar_checksum(tampered, offset)
                    plain = directory / f"{label}.ustar"
                    plain.write_bytes(tampered)
                    with self.assertRaises(candidate.CandidateError) as raised:
                        candidate._preflight_ustar(plain, policy, root)
                    self.assertEqual(raised.exception.code, "archive-metadata")

            tampered = bytearray(original)
            offset = offsets[f"{root}/LICENSE"]
            size = int(tampered[offset + 124:offset + 136].strip(b" \0"), 8)
            tampered[offset + 512 + size] = ord("x")
            plain = directory / "data-padding.ustar"
            plain.write_bytes(tampered)
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._preflight_ustar(plain, policy, root)
            self.assertEqual(raised.exception.code, "archive-metadata")


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"}, "candidate verify needs Linux x64")
class VerifyTrustBoundaryTests(unittest.TestCase):
    def test_verify_never_executes_malicious_self_consistent_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            marker = directory / "runtime-executed"
            script = f"#!/bin/sh\nprintf x > {marker}\nexit 0\n".encode("ascii")
            archive = build_for_test(directory, host=True, runtime_script=script)
            host, _, _ = host_snapshot(directory / "verify-host")
            with mock.patch.object(candidate.subprocess, "run", side_effect=AssertionError("archive runtime executed")):
                digest = candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(digest, hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertFalse(marker.exists())

    def test_changed_embedded_policy_and_self_consistent_docs_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            changed_policy = candidate.load_policy(POLICY_PATH)
            limits = changed_policy["limits"]
            assert isinstance(limits, dict)
            limits["max_entries"] = 9999
            candidate.validate_policy(changed_policy)
            snapshot, selected_policy, _ = host_snapshot(directory / "changed-policy", changed_policy)
            output = directory / "changed-output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                archive = candidate.build_candidate(output, snapshot=snapshot, policy=selected_policy, runtime_root=fake_runtime(directory / "changed-runtime"))
            host, _, _ = host_snapshot(directory / "verify-host")
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(raised.exception.code, "archive-policy")

            snapshot, policy, policy_bytes = host_snapshot(directory / "docs")
            root = directory / "candidate-root"
            root.mkdir()
            candidate._copy_authored_payload(snapshot, policy, root)
            (root / "runtime").mkdir()
            candidate._copy_runtime_tree(fake_runtime(directory / "docs-runtime"), root / "runtime" / "python", policy)
            write_file(root / "docs" / "extra.md", b"self-consistent but forbidden\n")
            manifest = candidate._build_manifest(snapshot, policy, root, policy_bytes)
            write_file(root / "manifest.json", candidate.canonical_json(manifest).encode("ascii"))
            docs_archive = directory / f"agentic-sdlc-candidate-{manifest['candidate_id']}-linux-x64.tar.gz"
            candidate._write_ustar_archive(root, manifest, docs_archive, policy)
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.verify_archive(docs_archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(raised.exception.code, "archive-layout")

    def test_runtime_executable_must_be_regular_0755_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot, policy, policy_bytes = host_snapshot(directory / "candidate-source")
            root = directory / "candidate-root"
            root.mkdir()
            candidate._copy_authored_payload(snapshot, policy, root)
            (root / "runtime").mkdir()
            candidate._copy_runtime_tree(fake_runtime(directory / "runtime"), root / "runtime" / "python", policy)
            os.chmod(root / "runtime" / "python" / "bin" / "python3.12", 0o644)
            manifest = candidate._build_manifest(snapshot, policy, root, policy_bytes)
            write_file(root / "manifest.json", candidate.canonical_json(manifest).encode("ascii"))
            archive = directory / f"agentic-sdlc-candidate-{manifest['candidate_id']}-linux-x64.tar.gz"
            candidate._write_ustar_archive(root, manifest, archive, policy)
            host, _, _ = host_snapshot(directory / "verify-host")
            with mock.patch.object(candidate.subprocess, "run", side_effect=AssertionError("candidate runtime executed")):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(raised.exception.code, "archive-layout")

    def test_verify_cleanup_failure_is_unknown_effect_and_exit_four(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = build_for_test(directory, host=True)
            host, _, _ = host_snapshot(directory / "verify-host")
            with mock.patch.object(candidate.shutil, "rmtree", side_effect=OSError("injected cleanup failure")):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(raised.exception.code, "verify-stage-unknown-effect")
            self.assertEqual(candidate._failure_exit_code(raised.exception.code), 4)

    def test_public_verify_uses_committed_host_policy_not_dirty_expansion(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            committed_policy = candidate.load_policy(POLICY_PATH)
            host = directory / "host"
            make_git_repo(host, committed_policy)
            expanded = copy.deepcopy(committed_policy)
            payload = expanded["payload"]
            assert isinstance(payload, dict)
            trees = payload["trees"]
            assert isinstance(trees, list)
            trees.append("docs")
            trees.sort()
            candidate.validate_policy(expanded)
            snapshot, selected_policy, _ = host_snapshot(directory / "candidate-source", expanded)
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                archive = candidate.build_candidate(output, snapshot=snapshot, policy=selected_policy, runtime_root=fake_runtime(directory / "runtime"))
            write_file(host / POLICY_PATH.relative_to(ROOT), candidate.canonical_json(expanded).encode("ascii"))
            with mock.patch.object(candidate, "source_root_for_script", return_value=host):
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate.verify_archive(archive, temp_parent=directory)
            self.assertEqual(raised.exception.code, "source-dirty")

    def test_verify_pins_admitted_fd_against_path_substitution_and_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = build_for_test(directory, host=True)
            original_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            host, _, _ = host_snapshot(directory / "verify-host")
            displaced = directory / "displaced.tar.gz"

            def substitute() -> None:
                archive.rename(displaced)
                archive.write_bytes(b"replacement bytes")

            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host, _after_pin_copy=substitute)
            self.assertEqual(raised.exception.code, "archive-mutated")
            self.assertEqual(archive.read_bytes(), b"replacement bytes")

            archive.unlink()
            displaced.rename(archive)
            self.assertEqual(candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host), original_digest)

            def mutate_same_inode() -> None:
                with archive.open("r+b") as handle:
                    handle.seek(0)
                    handle.write(b"x")
                    handle.flush()
                    os.fsync(handle.fileno())

            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host, _after_pin_copy=mutate_same_inode)
            self.assertEqual(raised.exception.code, "archive-mutated")

    def test_concatenated_gzip_member_is_not_a_candidate_container(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            archive = build_for_test(directory, host=True)
            with archive.open("ab") as target:
                with gzip.GzipFile(filename="unbound-second-member", mode="wb", fileobj=target, mtime=1, compresslevel=9):
                    target.write(b"")
            host, _, _ = host_snapshot(directory / "verify-host")
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=host)
            self.assertEqual(raised.exception.code, "archive-gzip")


@unittest.skipUnless(sys.platform == "linux" and os.uname().machine in {"x86_64", "amd64"}, "candidate execution needs Linux x64")
class RunReadonlyTrustBoundaryTests(unittest.TestCase):
    def test_signal_recorded_during_spawn_handoff_is_forwarded_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            dispatcher = directory / "dispatcher"
            write_file(
                dispatcher,
                (
                    "#!/usr/bin/bash\n"
                    "trap 'exit 0' TERM INT HUP\n"
                    "while :; do read -r -t 1 _ || :; done\n"
                ).encode("utf-8"),
                0o755,
            )
            policy = json.loads(EXECUTION_POLICY_PATH.read_text())
            policy["limits"]["max_seconds"] = 1
            real_popen = candidate.subprocess.Popen

            def spawn_then_signal(*args: object, **kwargs: object) -> subprocess.Popen[bytes]:
                process = real_popen(*args, **kwargs)
                os.kill(os.getpid(), signal.SIGTERM)
                return process

            started = time.monotonic()
            with mock.patch.object(candidate.subprocess, "Popen", side_effect=spawn_then_signal):
                result, stdout, stderr, _process_id = candidate._supervise_candidate(
                    dispatcher, [], {}, policy
                )
            self.assertEqual(result, 128 + signal.SIGTERM)
            self.assertEqual(stdout, b"")
            self.assertEqual(stderr, b"")
            self.assertLess(time.monotonic() - started, 0.75)

    def test_leader_exit_does_not_hide_a_term_ignoring_same_group_descendant(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            descendant_pid_path = directory / "descendant.pid"
            dispatcher = directory / "dispatcher"
            write_file(
                dispatcher,
                (
                    "#!/usr/bin/bash\n"
                    "(\n"
                    "  trap '' TERM\n"
                    f"  printf '%s\\n' \"$BASHPID\" > '{descendant_pid_path}'\n"
                    "  exec 1>&-\n"
                    "  exec 2>&-\n"
                    "  while :; do :; done\n"
                    ") &\n"
                    "exit 0\n"
                ).encode("utf-8"),
                0o755,
            )
            policy = json.loads(EXECUTION_POLICY_PATH.read_text())
            started = time.monotonic()
            try:
                with self.assertRaises(candidate.CandidateError) as raised:
                    candidate._supervise_candidate(dispatcher, [], {}, policy)
                self.assertEqual(raised.exception.code, "execution-descendant")
                self.assertLess(time.monotonic() - started, 5)
                descendant_pid = int(descendant_pid_path.read_text().strip())
                with self.assertRaises(ProcessLookupError):
                    os.kill(descendant_pid, 0)
            finally:
                if descendant_pid_path.exists():
                    descendant_pid = int(descendant_pid_path.read_text().strip())
                    try:
                        os.kill(descendant_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_supervision_has_no_pre_child_blocking_transfer(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            dispatcher = directory / "dispatcher"
            write_file(dispatcher, b"#!/usr/bin/bash\nprintf '{}\\n'\n", 0o755)
            policy = json.loads(EXECUTION_POLICY_PATH.read_text())
            with mock.patch.object(
                candidate,
                "_write_all",
                side_effect=AssertionError("legacy pre-child blocking pipe was used"),
            ):
                result, stdout, stderr, process_id = candidate._supervise_candidate(
                    dispatcher, [], {}, policy
                )
            self.assertEqual(result, 0)
            self.assertEqual(stdout, b"{}\n")
            self.assertEqual(stderr, b"")
            self.assertGreater(process_id, 0)

    def test_supervision_bounds_child_output_and_converges_without_hanging(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            dispatcher = directory / "dispatcher"
            write_file(
                dispatcher,
                b"#!/usr/bin/bash\nfor ((i=0; i<4096; i++)); do printf x; done\n",
                0o755,
            )
            policy = json.loads(EXECUTION_POLICY_PATH.read_text())
            policy["limits"]["max_child_output_bytes"] = 1024
            started = time.monotonic()
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate._supervise_candidate(dispatcher, [], {}, policy)
            self.assertEqual(raised.exception.code, "execution-child-output")
            self.assertLess(time.monotonic() - started, 5)

    def test_public_bridge_emits_one_candidate_v2_record_and_cleans_every_ephemeral_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot, _policy = executable_snapshot(directory / "repository")
            repository = snapshot.root
            for arguments in (
                ["/usr/bin/git", "init", "-q", str(repository)],
                ["/usr/bin/git", "-C", str(repository), "add", "."],
                [
                    "/usr/bin/git", "-C", str(repository), "-c", "user.name=test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "candidate",
                ],
            ):
                completed = subprocess.run(arguments, capture_output=True, text=True, check=False)
                self.assertEqual(completed.returncode, 0, completed.stderr)
            output = directory / "output"
            output.mkdir()
            temporary = directory / "temporary"
            temporary.mkdir()
            xdg = directory / "must-not-exist-xdg"
            poison = directory / "poison"
            poison.mkdir()
            marker = directory / "ambient-tool-executed"
            for name in ("python", "python3", "uv", "mise", "git", "curl", "ccodex"):
                write_file(
                    poison / name,
                    f"#!/usr/bin/bash\nprintf '%s' '{name}' >> '{marker}'\nexit 91\n".encode("utf-8"),
                    0o755,
                )
            environment = {
                **os.environ,
                "ALL_PROXY": "http://credential-canary.invalid",
                "ANTHROPIC_API_KEY": "credential-canary",
                "CODEX_HOME": str(directory / "poisoned-codex-home"),
                "HOME": str(directory / "poisoned-home"),
                "HTTPS_PROXY": "http://credential-canary.invalid",
                "MISE_CONFIG_ROOT": str(directory / "poisoned-mise"),
                "PATH": str(poison),
                "PYTHONPATH": str(directory / "poisoned-python"),
                "TMPDIR": str(temporary),
                "UV_CACHE_DIR": str(directory / "poisoned-uv"),
                "XDG_STATE_HOME": str(xdg),
            }
            script = repository / "scripts" / "release_candidate.py"
            self.assertTrue(script.is_file())
            python = candidate._resolve_base_runtime(_policy) / "bin" / "python3.12"
            build = subprocess.run(
                [str(python), "-I", "-B", str(script), "build", "--output", str(output)],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            archive = next(output.glob("*.tar.gz"))
            verify = subprocess.run(
                [str(python), "-I", "-B", str(script), "verify", "--archive", str(archive)],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(verify.returncode, 0, verify.stderr)
            direct_private = directory / "direct-private"
            direct_private.mkdir()
            source = candidate.admit_source(repository)
            host_policy, host_policy_bytes = candidate._policy_from_snapshot(source)
            limits = host_policy["limits"]
            assert isinstance(limits, dict)
            pinned, archive_digest = candidate._pin_archive(
                archive, direct_private, limits["max_archive_bytes"]
            )
            raw_archive = candidate._inflate_gzip(
                pinned, direct_private, limits["max_uncompressed_bytes"]
            )
            manifest, members, manifest_raw = candidate._archive_admission(
                raw_archive, archive.name, host_policy, host_policy_bytes
            )
            direct_root = candidate._manual_extract(
                raw_archive, manifest, members, manifest_raw, host_policy, direct_private
            )
            direct = subprocess.run(
                [
                    str(direct_root / "runtime" / "python" / "bin" / "python3.12"),
                    "-I", "-B", str(direct_root / "scripts" / "ccodex_sdlc.py"),
                    "--candidate-observation-v1", "inspect", "--json",
                ],
                env={"HOME": str(directory / "direct-home"), "LANG": "C", "LC_ALL": "C", "PATH": ""},
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            self.assertEqual(direct.returncode, 3)
            self.assertIn("candidate subordinate observation refused", direct.stderr)
            runtime = candidate._resolve_base_runtime(host_policy)
            authored_digest, runtime_digest = candidate._authenticate_executable_candidate(
                manifest, source, host_policy, runtime
            )
            execution_policy, _execution_policy_raw = candidate.load_execution_policy(source)
            _bash, bash_digest = candidate._trusted_bash(execution_policy)
            dispatcher, dispatcher_digest = candidate._render_candidate_dispatcher(direct_root)
            forged_admission = candidate._admission_record(
                direct_root,
                archive_digest,
                manifest,
                execution_policy,
                ["sdlc", "inspect", "--json"],
                dispatcher_digest,
                bash_digest,
                authored_digest,
                runtime_digest,
            )
            read_fd, write_fd = os.pipe()
            os.write(write_fd, candidate.canonical_json(forged_admission).encode("ascii"))
            os.close(write_fd)
            try:
                constructed = subprocess.run(
                    [str(dispatcher), "sdlc", "inspect", "--json"],
                    env={
                        "CCODEX_CANDIDATE_ADMISSION_FD": str(read_fd),
                        "HOME": str(directory / "constructed-home"),
                        "LANG": "C",
                        "LC_ALL": "C",
                        "PATH": "",
                    },
                    pass_fds=(read_fd,),
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            finally:
                os.close(read_fd)
            self.assertEqual(constructed.returncode, 0, constructed.stderr)
            subordinate = json.loads(constructed.stdout)
            self.assertEqual(
                subordinate["schema_version"], "ccodex-sdlc-candidate-observation/v1"
            )
            self.assertEqual(subordinate["authority"], "unadmitted-subordinate")
            self.assertNotIn("admission", subordinate)
            candidate._cleanup_run_private(direct_private)
            human = subprocess.run(
                [
                    str(python), "-I", "-B", str(script), "run-readonly",
                    "--archive", str(archive), "--", "sdlc", "inspect",
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            machine = subprocess.run(
                [
                    str(python), "-I", "-B", str(script), "run-readonly",
                    "--archive", str(archive), "--", "sdlc", "inspect", "--json",
                ],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            self.assertEqual(human.returncode, 0, human.stderr)
            self.assertEqual(machine.returncode, 0, machine.stderr)
            report = json.loads(machine.stdout)
            self.assertEqual(report["schema_version"], "ccodex-sdlc-read-report/v2")
            self.assertNotIn("authority", report)
            self.assertEqual(
                {
                    key: report["distribution"][key]
                    for key in (
                        "lifecycle", "publication", "public_channel", "support_tier",
                        "release_claim", "provenance", "sbom", "licensing",
                        "release_topology_adr_status",
                    )
                },
                {
                    "lifecycle": "ephemeral",
                    "publication": "unpublished",
                    "public_channel": None,
                    "support_tier": "unsupported",
                    "release_claim": "none",
                    "provenance": "unverified",
                    "sbom": "absent",
                    "licensing": "incomplete",
                    "release_topology_adr_status": "proposed",
                },
            )
            self.assertEqual(report["admission"]["schema_version"], "release-candidate-execution-admission/v1")
            self.assertEqual(report["future_dimensions"]["activation"], "unsupported")
            self.assertEqual(report["future_dimensions"]["waves"], "unsupported")
            for value in (
                "ephemeral/unpublished",
                "public_channel=null",
                "ADR-0021 proposed",
                "host-finalized",
            ):
                self.assertIn(value, human.stdout)
            self.assertNotIn("credential-canary", human.stdout + machine.stdout + human.stderr + machine.stderr)
            self.assertFalse(marker.exists())
            self.assertFalse(xdg.exists())
            self.assertEqual(list(temporary.iterdir()), [])

            with mock.patch.object(
                candidate,
                "_supervise_candidate",
                side_effect=candidate.CandidateError("execution-group-unknown-effect"),
            ), self.assertRaises(candidate.CandidateError) as raised:
                candidate.run_readonly(
                    archive,
                    ["sdlc", "inspect", "--json"],
                    temp_parent=directory,
                    _host_snapshot=source,
                    _runtime_root=runtime,
                )
            self.assertEqual(raised.exception.code, "execution-group-unknown-effect")
            self.assertEqual(candidate._failure_exit_code(raised.exception.code), 4)
            retained = list(directory.glob(".release-candidate-run-*"))
            self.assertEqual(len(retained), 1)
            witness_path = retained[0] / "effect-state.json"
            self.assertEqual(Path(raised.exception.witness_locator), witness_path)
            self.assertTrue(witness_path.is_file())
            self.assertFalse(witness_path.is_symlink())
            witness = json.loads(witness_path.read_text())
            self.assertEqual(
                witness,
                {
                    "cleanup": "retained",
                    "effect_state": "unknown",
                    "reason": "process-group-nonconvergence",
                    "schema_version": "release-candidate-effect-witness/v1",
                },
            )
            candidate._cleanup_run_private(retained[0])

    def test_self_consistent_substituted_runtime_is_structural_but_not_executable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            snapshot, policy = executable_snapshot(directory / "snapshot")
            marker = directory / "malicious-runtime-executed"
            malicious = fake_runtime(
                directory / "malicious-runtime",
                f"#!/usr/bin/bash\nprintf x > '{marker}'\nexit 0\n".encode("utf-8"),
            )
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                archive = candidate.build_candidate(
                    output, snapshot=snapshot, policy=policy, runtime_root=malicious
                )
            self.assertEqual(
                candidate.verify_archive(archive, temp_parent=directory, _host_snapshot=snapshot),
                hashlib.sha256(archive.read_bytes()).hexdigest(),
            )
            actual_runtime = candidate._resolve_base_runtime(policy)
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.run_readonly(
                    archive,
                    ["sdlc", "inspect", "--json"],
                    temp_parent=directory,
                    _host_snapshot=snapshot,
                    _runtime_root=actual_runtime,
                )
            self.assertEqual(raised.exception.code, "execution-runtime-mismatch")
            self.assertFalse(marker.exists())
            self.assertFalse(any(path.name.startswith(".release-candidate-run-") for path in directory.iterdir()))

    def test_self_consistent_substituted_reader_refuses_before_candidate_execution(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            host, policy = executable_snapshot(directory / "host")
            files = dict(host.test_blobs or {})
            marker = directory / "malicious-reader-executed"
            files["scripts/ccodex_sdlc.py"] = (
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('x')\n".encode("utf-8")
            )
            source = directory / "substituted" / "source"
            substituted_files: dict[str, tuple[int, bytes]] = {}
            for relative, data in files.items():
                mode = host.entries[relative].mode
                substituted_files[relative] = (mode, data)
                write_file(source / relative, data, mode & 0o777)
            substituted = candidate.source_snapshot_for_testing(
                source,
                substituted_files,
                commit=host.commit,
                tree=host.tree,
                epoch=host.epoch,
            )
            output = directory / "output"
            output.mkdir()
            with mock.patch.object(candidate, "_staging_runtime_canary"):
                archive = candidate.build_candidate(
                    output,
                    snapshot=substituted,
                    policy=policy,
                    runtime_root=fake_runtime(directory / "runtime"),
                )
            with self.assertRaises(candidate.CandidateError) as raised:
                candidate.run_readonly(
                    archive,
                    ["sdlc", "doctor"],
                    temp_parent=directory,
                    _host_snapshot=host,
                    _runtime_root=candidate._resolve_base_runtime(policy),
                )
            self.assertEqual(raised.exception.code, "execution-payload-mismatch")
            self.assertFalse(marker.exists())

    def test_cleanup_uncertainty_is_exit_four_and_named_unknown_effect(self) -> None:
        self.assertEqual(candidate._failure_exit_code("run-stage-unknown-effect"), 4)
        self.assertEqual(candidate._failure_exit_code("execution-orphan-unknown-effect"), 4)


if __name__ == "__main__":
    unittest.main()
